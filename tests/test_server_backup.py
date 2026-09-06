from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text

from app.config import AppConfig
from app.db import engine as engine_module
from app.db.base import Base
from app.db import seed
from app.domain.errors import LedgerError
from app.services.backup_service import BackupError
from app.services import server_backup


pg = os.environ.get("PL_TEST_PG_URL")
BIN = Path(r"F:\tools\pgsql-extract\pgsql\bin")
pytestmark = pytest.mark.skipif(
    not pg or not (BIN / "pg_dump.exe").is_file(),
    reason="PL_TEST_PG_URL or pg_dump missing",
)


def _cfg(tmp_path) -> AppConfig:
    parsed = urlparse(pg.replace("postgresql+psycopg", "postgresql"))
    return AppConfig(
        backend="postgresql",
        data_dir=tmp_path,
        pg_host=parsed.hostname or "localhost",
        pg_port=parsed.port or 5432,
        pg_database=(parsed.path or "/").lstrip("/"),
        pg_user=parsed.username or "postgres",
        pg_password=parsed.password or "",
        pg_bin_dir=BIN,
        server_backup_dir=tmp_path / "pgbackups",
    )


def test_pg_dump_and_restore_and_busy_guard(tmp_path, pg_url):
    cfg = _cfg(tmp_path)
    engine = engine_module.build_engine(pg_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        seed.seed_base(session)
        session.commit()
    engine.dispose()
    info = server_backup.create(cfg, None)
    assert info.path.exists()
    assert info.size_bytes > 1024
    engine = engine_module.build_engine(pg_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM documents"))
    engine.dispose()
    result = server_backup.restore(cfg, None, info.path)
    assert result.accounts > 0
    busy = create_engine(pg_url, connect_args={"options": "-c application_name=PersianLedger"})
    conn = busy.connect()
    try:
        with pytest.raises(BackupError):
            server_backup.restore(cfg, None, info.path)
    finally:
        conn.close()
        busy.dispose()
