from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.config import AppConfig
from app.db import engine as engine_module
from app.db import migrate
from app.db.base import Base


pytestmark = pytest.mark.skipif(not os.environ.get("PL_TEST_PG_URL"), reason="PL_TEST_PG_URL not set")


def _cfg_from_url(url: str) -> AppConfig:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    return AppConfig(
        backend="postgresql",
        pg_host=parsed.hostname or "localhost",
        pg_port=parsed.port or 5432,
        pg_database=(parsed.path or "/").lstrip("/"),
        pg_user=parsed.username or "postgres",
        pg_password=parsed.password or "",
    )


def test_alembic_upgrade_matches_models(pg_url):
    cfg = _cfg_from_url(pg_url)
    engine = engine_module.build_engine(pg_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    try:
        migrate.upgrade_to_head(engine, cfg)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            diff = compare_metadata(context, Base.metadata)
        named_only = [
            item
            for item in diff
            if not (
                getattr(item, "__class__", type(item)).__name__ in {"tuple"}
                and len(item) >= 1
            )
        ]
        assert diff == [] or named_only == diff
        assert diff == [], diff
    finally:
        engine.dispose()
