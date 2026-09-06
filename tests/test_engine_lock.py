from __future__ import annotations

from sqlalchemy import create_engine

from app.db.engine import SCHEMA_LOCK_KEY, advisory_lock


def test_advisory_lock_sqlite_is_noop():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.connect() as connection, advisory_lock(connection, SCHEMA_LOCK_KEY):
        pass
