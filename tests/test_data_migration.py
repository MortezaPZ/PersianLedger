from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import bootstrap, config as config_module
from app.db import engine as engine_module
from app.db.models import Document
from app.services import document_service, master_data
from app.services.data_migration import migrate
from tests.test_unpost_and_purge import _post


pytestmark = pytest.mark.skipif(not os.environ.get("PL_TEST_PG_URL"), reason="PL_TEST_PG_URL not set")


def test_migrate_sqlite_to_postgres(tmp_path, pg_url):
    data = tmp_path / "data"
    data.mkdir()
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    bootstrap.start(cfg, with_demo=True)
    engine_module.init_engine(cfg)
    with Session(engine_module.get_engine()) as session:
        year = master_data.current_fiscal_year(session)
        n_src = document_service.next_number_preview(session, year)
        session.commit()
    report = migrate(cfg.sqlite_path, pg_url, replace=True, attachments_dir=cfg.attachments_dir)
    assert report.mismatches == []
    dst = engine_module.build_engine(pg_url)
    try:
        factory = Session.object_session  # placeholder
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=dst, expire_on_commit=False)
        engine_module.set_session_factory(factory, dst)
        session = factory()
        try:
            docs = list(session.execute(select(Document)).scalars())
            year = master_data.current_fiscal_year(session)
            assert document_service.next_number_preview(session, year) == n_src
            first = session.execute(select(Document).where(Document.number == 1)).scalar_one()
            assert first.lines
            max_id = max(d.id for d in docs)
            extra = _post(session, "after-migrate")
            session.commit()
            assert extra.id == max_id + 1
        finally:
            session.close()
    finally:
        dst.dispose()
