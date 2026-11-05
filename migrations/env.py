from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from alembic.runtime.migration import MigrationContext
from sqlalchemy import pool

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "app").exists():
    ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402
from app.db.engine import build_engine  # noqa: E402

config = context.config
if config.config_file_name is not None and config.get_section("loggers"):
    from logging.config import fileConfig

    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url")


def _sqlite_path_crosses_tafsili_tree(connection) -> bool:
    """Whether this Alembic command upgrades or downgrades the tree revision."""
    from alembic.script import ScriptDirectory

    migration_context = MigrationContext.configure(connection)
    current = migration_context.get_current_revision()
    destination = context.get_revision_argument()
    if current == destination:
        return False

    script = ScriptDirectory.from_config(config)

    def ancestors(revision) -> set[str]:
        pending = [revision] if isinstance(revision, str) else list(revision or [])
        found: set[str] = set()
        while pending:
            current_revision = script.get_revision(pending.pop())
            if current_revision is None or current_revision.revision in found:
                continue
            found.add(current_revision.revision)
            down_revision = current_revision.down_revision
            if isinstance(down_revision, str):
                pending.append(down_revision)
            elif down_revision:
                pending.extend(down_revision)
        return found

    current_has_tree = "tafsili_tree" in ancestors(current)
    destination_has_tree = "tafsili_tree" in ancestors(destination)
    return current_has_tree != destination_has_tree


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        engine = build_engine(_url())
        with engine.connect() as connection:
            _run(connection)
        engine.dispose()
    else:
        _run(connectable)


def _run(connection) -> None:
    is_sqlite = connection.dialect.name == "sqlite"

    def configure() -> None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            compare_type=True,
        )

    if not is_sqlite:
        configure()
        with context.begin_transaction():
            context.run_migrations()
        return

    raw_connection = connection.connection.driver_connection
    caller_owns_transaction = connection.in_transaction() or raw_connection.in_transaction
    if caller_owns_transaction:
        foreign_keys = raw_connection.execute("PRAGMA foreign_keys").fetchone()[0]
        if foreign_keys and _sqlite_path_crosses_tafsili_tree(connection):
            raise RuntimeError(
                "SQLite tafsili_tree migration cannot change PRAGMA foreign_keys inside a caller-owned "
                "transaction. Roll back or commit it before running this migration; no migration was run."
            )
        # The caller owns both the transaction and PRAGMA state here. Do not
        # commit it or try to toggle foreign keys mid-transaction. Startup's
        # migration wrapper disables FKs before opening its transaction; other
        # callers must provide a state compatible with their migration path.
        # Python 3.11's sqlite3 legacy transaction mode may not emit a database
        # BEGIN until the first DML. Start the caller-owned SQLite transaction
        # explicitly before Alembic can issue DDL, unless it already exists.
        if not raw_connection.in_transaction:
            raw_connection.execute("BEGIN IMMEDIATE")
        configure()
        with context.begin_transaction():
            context.run_migrations()
        return

    # PRAGMA foreign_keys is a no-op inside an SQLite transaction. This env owns
    # the connection here, so disable it before Alembic starts and restore it
    # after the migration transaction commits or rolls back.
    raw_connection.execute("PRAGMA foreign_keys=OFF")
    if raw_connection.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise RuntimeError("SQLite foreign keys could not be disabled for migration")
    try:
        # Force a real DBAPI transaction before the first migration DDL. The
        # SQLAlchemy transaction below adopts it; it does not nest a BEGIN.
        raw_connection.execute("BEGIN IMMEDIATE")
        with connection.begin():
            configure()
            with context.begin_transaction():
                context.run_migrations()
    finally:
        if connection.in_transaction() or raw_connection.in_transaction:
            connection.rollback()
        raw_connection.execute("PRAGMA foreign_keys=ON")
        if raw_connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign keys could not be restored after migration")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
