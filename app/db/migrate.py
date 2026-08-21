"""Startup schema upgrade with an automatic backup of the SQLite file."""
from __future__ import annotations

import datetime as _dt
import shutil
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from app import paths
from app.config import AppConfig


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


def _backup_sqlite(cfg: AppConfig, tag: str) -> Path | None:
    source = Path(cfg.sqlite_path)
    if cfg.backend != "sqlite" or not source.exists():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = cfg.backup_dir / f"pre-upgrade-{tag}-{stamp}.sqlite3"
    shutil.copy2(source, dest)
    return dest


def upgrade_to_head(engine: Engine, cfg: AppConfig) -> MigrationResult:
    url = cfg.database_url()
    head = head_revision(url)
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
    backup = _backup_sqlite(cfg, current or "unknown")
    alembic_cfg = alembic_config(url)
    try:
        with engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection
            command.upgrade(alembic_cfg, "head")
    except Exception:
        engine.dispose()
        if backup and cfg.sqlite_path:
            shutil.copy2(backup, Path(cfg.sqlite_path))
        raise
    return MigrationResult(current, head, backup, True)
