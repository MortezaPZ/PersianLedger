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


_TAFSILI_TREE_REVISION = "tafsili_tree"
_TAFSILI_MUTEX_REVISION = "tafsili_tree_mutex"


def _sqlite_mutex_state(connection) -> tuple[str | None, list[tuple[int, int]]]:
    """Validate the mutex table shape and return its version and rows."""
    table_exists = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tafsili_tree_mutex'"
    ).first() is not None
    if not table_exists:
        return "absent", []

    columns = [tuple(row) for row in connection.exec_driver_sql("PRAGMA table_info(tafsili_tree_mutex)")]
    definition = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='tafsili_tree_mutex'"
    ).scalar_one()
    normalized_definition = "".join(definition.casefold().split())
    expected_definition = (
        "createtabletafsili_tree_mutex(idintegernotnull,revisionintegerdefault0notnull,"
        "constraintpk_tafsili_tree_mutexprimarykey(id))"
    )
    expected_columns = [
        (0, "id", "INTEGER", 1, None, 1),
        (1, "revision", "INTEGER", 1, "0", 0),
    ]
    indexes = [tuple(row) for row in connection.exec_driver_sql("PRAGMA index_list(tafsili_tree_mutex)")]
    foreign_keys = connection.exec_driver_sql("PRAGMA foreign_key_list(tafsili_tree_mutex)").all()
    triggers = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name='tafsili_tree_mutex'"
    ).first()
    # A SQLite primary key has one autoindex. Any other index, FK, trigger, or
    # column is unexpected and makes automatic recovery unsafe.
    valid_indexes = not indexes or (
        len(indexes) == 1 and indexes[0][2:] == (1, "pk", 0)
    )
    if (
        columns != expected_columns
        or normalized_definition != expected_definition
        or not valid_indexes
        or foreign_keys
        or triggers is not None
    ):
        raise RuntimeError(
            "ساختار جدول tafsili_tree_mutex با مهاجرت شناخته‌شده مطابقت ندارد؛ "
            "بازیابی خودکار متوقف شد و جدول/داده‌ها دست‌نخورده ماندند."
        )

    rows = [tuple(row) for row in connection.exec_driver_sql(
        "SELECT id, revision FROM tafsili_tree_mutex ORDER BY id"
    )]
    if not rows:
        return "empty", []
    if (
        len(rows) == 1
        and rows[0][0] == 1
        and isinstance(rows[0][1], int)
        and rows[0][1] >= 0
    ):
        return "seeded", rows
    raise RuntimeError(
        "ردیف‌های جدول tafsili_tree_mutex با وضعیت ناقص شناخته‌شده مطابقت ندارند؛ "
        "بازیابی خودکار متوقف شد و داده‌ها دست‌نخورده ماندند."
    )


def _sqlite_version_row(connection) -> list[tuple[str]]:
    if not inspect(connection).has_table("alembic_version"):
        return []
    return [tuple(row) for row in connection.exec_driver_sql(
        "SELECT version_num FROM alembic_version ORDER BY version_num"
    )]


def _recover_interrupted_mutex_migration(engine: Engine, cfg: AppConfig, head: str | None) -> Path | None:
    """Recover only the two provable states left by the immutable mutex migration."""
    with engine.connect() as connection:
        version_rows = _sqlite_version_row(connection)
        current = version_rows[0][0] if len(version_rows) == 1 else None
        table_exists = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tafsili_tree_mutex'"
        ).first() is not None
        if current == head:
            state, rows = _sqlite_mutex_state(connection)
            if state != "seeded" or len(rows) != 1:
                raise RuntimeError(
                    "نسخه مهاجرت سرآیند را نشان می‌دهد ولی جدول mutex سالم نیست؛ "
                    "برای جلوگیری از تغییر ناایمن، راه‌اندازی متوقف شد."
                )
            return None
        if current != _TAFSILI_TREE_REVISION or not table_exists:
            return None
        initial_state, _ = _sqlite_mutex_state(connection)
        if initial_state not in {"empty", "seeded"}:
            return None

    archive = _backup_sqlite(engine, cfg, "mutex-recovery")
    if archive is None:
        raise RuntimeError("از وضعیت ناقص مهاجرت mutex نسخه پشتیبان تهیه نشد؛ بازیابی انجام نشد.")

    recovered = False
    with engine.connect() as connection:
        raw_connection = connection.connection.driver_connection
        if raw_connection.in_transaction or connection.in_transaction():
            connection.rollback()
        raw_connection.execute("BEGIN IMMEDIATE")
        try:
            with connection.begin():
                version_rows = _sqlite_version_row(connection)
                current = version_rows[0][0] if len(version_rows) == 1 else None
                if current == _TAFSILI_TREE_REVISION:
                    state, rows = _sqlite_mutex_state(connection)
                    if state == "empty":
                        connection.exec_driver_sql("DROP TABLE tafsili_tree_mutex")
                        recovered = True
                    elif state == "seeded":
                        script = ScriptDirectory.from_config(alembic_config(cfg.database_url()))
                        MigrationContext.configure(connection).stamp(script, _TAFSILI_MUTEX_REVISION)
                        recovered = True
                    elif state == "absent":
                        # A concurrent startup may already have removed the
                        # empty remnant. The unchanged tree revision is safe to
                        # continue from; the normal migration will serialize
                        # on its own BEGIN IMMEDIATE.
                        pass
                    else:
                        raise RuntimeError(
                            "وضعیت جدول mutex در زمان بازیابی تغییر کرد؛ هیچ اصلاحی انجام نشد."
                        )
                elif current == head:
                    state, rows = _sqlite_mutex_state(connection)
                    if state != "seeded" or len(rows) != 1:
                        raise RuntimeError("وضعیت مهاجرت mutex هم‌زمان تغییر کرده و معتبر نیست.")
                else:
                    raise RuntimeError("نسخه مهاجرت هنگام بازیابی تغییر کرد؛ بازیابی امن متوقف شد.")
        except Exception:
            if connection.in_transaction() or raw_connection.in_transaction:
                connection.rollback()
            raise
        finally:
            if raw_connection.in_transaction:
                connection.rollback()

    return archive if recovered else None


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
        raw_connection = connection.connection.driver_connection
        # SQLite must have foreign keys disabled before the transaction starts:
        # Alembic batch migrations rebuild accounts while document_lines and
        # account_tafsili_rules still reference it.
        try:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            if enabled:
                raise RuntimeError("SQLite foreign keys could not be disabled for migration")
            connection.commit()
            # sqlite3 on Python 3.11 can defer the physical BEGIN until DML;
            # make DDL transactional before Alembic starts.
            raw_connection.execute("BEGIN IMMEDIATE")
            with connection.begin():
                _drop_stale_batch_tables(connection)
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")
        finally:
            if connection.in_transaction() or raw_connection.in_transaction:
                connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
                connection.rollback()
                raise RuntimeError("SQLite foreign keys could not be restored after migration")
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

    recovery_backup = _recover_interrupted_mutex_migration(engine, cfg, head)
    inspector = inspect(engine)
    if not inspector.has_table("alembic_version") and not inspector.has_table("documents"):
        current = None
    else:
        current = _sqlite_current_revision(engine)
    stale_batch_tables = cfg.backend == "sqlite" and _has_stale_batch_tables(engine)
    if current == head and not stale_batch_tables:
        return MigrationResult(current, head, recovery_backup, recovery_backup is not None)
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
