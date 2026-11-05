"""Startup schema upgrade with an automatic backup of the SQLite file."""
from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from app import paths
from app.config import AppConfig
from app.db.engine import SCHEMA_LOCK_KEY, advisory_lock
from app.db.sqlite_snapshot import replace_database, snapshot_engine, snapshot_file


class SchemaTooNewError(RuntimeError):
    """The database was written by a newer build than the one running."""


@dataclass
class MigrationResult:
    from_revision: str | None
    to_revision: str | None
    backup_path: Path | None
    applied: bool


def migrations_dir() -> Path:
    if paths.is_frozen():
        return paths.resource_dir() / "migrations"
    return Path(__file__).resolve().parents[2] / "migrations"


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def head_revision(url: str) -> str | None:
    return ScriptDirectory.from_config(alembic_config(url)).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


def _known_revisions(url: str) -> set[str]:
    return {rev.revision for rev in ScriptDirectory.from_config(alembic_config(url)).walk_revisions()}


def _backup_sqlite(engine: Engine, cfg: AppConfig, tag: str) -> Path | None:
    source = Path(cfg.sqlite_path)
    if cfg.backend != "sqlite" or not source.exists():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = cfg.backup_dir / f"pre-upgrade-{tag}-{stamp}.sqlite3"
    return snapshot_engine(engine, dest)


def _sqlite_current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _drop_stale_batch_tables(connection) -> None:
    """Remove remnants of an interrupted Alembic batch rebuild when safe."""
    tables = {
        row[0]
        for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    for temporary in sorted(name for name in tables if name.startswith("_alembic_tmp_")):
        original = temporary.removeprefix("_alembic_tmp_")
        if original not in tables:
            raise RuntimeError(
                f"دیتابیس پس از مهاجرت ناقص، جدول اصلی {original} را ندارد؛ "
                "نسخه پشتیبان پیش از مهاجرت را بازیابی کنید."
            )
        quoted = temporary.replace('"', '""')
        connection.exec_driver_sql(f'DROP TABLE "{quoted}"')


def _has_stale_batch_tables(engine: Engine) -> bool:
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name GLOB '_alembic_tmp_*' LIMIT 1"
        ).first() is not None


def _run_sqlite_upgrade(engine: Engine, cfg: AppConfig, url: str) -> None:
    alembic_cfg = alembic_config(url)
    with engine.connect() as connection:
        # SQLite must have foreign keys disabled before the transaction starts:
        # Alembic batch migrations rebuild accounts while document_lines and
        # account_tafsili_rules still reference it.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            if enabled:
                raise RuntimeError("SQLite foreign keys could not be disabled for migration")
            connection.commit()
            with connection.begin():
                _drop_stale_batch_tables(connection)
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


def _restore_pre_upgrade_backup(backup: Path, destination: Path) -> None:
    staged = destination.with_name(f".{destination.name}.rollback-{uuid.uuid4().hex}.sqlite3")
    snapshot_file(backup, staged)
    replace_database(staged, destination)


def upgrade_to_head(engine: Engine, cfg: AppConfig) -> MigrationResult:
    url = cfg.database_url()
    head = head_revision(url)
    if cfg.backend != "sqlite":
        with engine.connect() as lock_conn, advisory_lock(lock_conn, SCHEMA_LOCK_KEY):
            inspector = inspect(engine)
            if not inspector.has_table("alembic_version") and not inspector.has_table("documents"):
                current = None
            else:
                current = current_revision(engine)
            if current == head:
                return MigrationResult(current, head, None, False)
            known = _known_revisions(url)
            if current and current not in known:
                raise SchemaTooNewError(
                    f"نسخه ساختار دیتابیس ({current}) از نسخه این برنامه جدیدتر است. "
                    "لطفاً نسخه جدیدتر برنامه را نصب کنید."
                )
            alembic_cfg = alembic_config(url)
            with engine.begin() as connection:
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")
            return MigrationResult(current, head, None, True)

    inspector = inspect(engine)
    if not inspector.has_table("alembic_version") and not inspector.has_table("documents"):
        current = None
    else:
        current = _sqlite_current_revision(engine)
    stale_batch_tables = cfg.backend == "sqlite" and _has_stale_batch_tables(engine)
    if current == head and not stale_batch_tables:
        return MigrationResult(current, head, None, False)
    if current == head:
        backup = _backup_sqlite(engine, cfg, "cleanup")
        try:
            _run_sqlite_upgrade(engine, cfg, url)
        except Exception:
            if backup and cfg.sqlite_path:
                engine.dispose()
                _restore_pre_upgrade_backup(backup, Path(cfg.sqlite_path))
            raise
        return MigrationResult(current, head, backup, True)
    known = _known_revisions(url)
    if current and current not in known:
        raise SchemaTooNewError(
            f"نسخه ساختار دیتابیس ({current}) از نسخه این برنامه جدیدتر است. "
            "لطفاً نسخه جدیدتر برنامه را نصب کنید."
        )
    backup = _backup_sqlite(engine, cfg, current or "unknown")
    try:
        _run_sqlite_upgrade(engine, cfg, url)
    except Exception:
        if backup and cfg.sqlite_path:
            engine.dispose()
            _restore_pre_upgrade_backup(backup, Path(cfg.sqlite_path))
        raise
    return MigrationResult(current, head, backup, True)
