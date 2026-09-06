from __future__ import annotations

import os
from decimal import Decimal
from threading import Thread

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.engine import build_engine, set_session_factory
from app.db.models import Account, Currency, Document, Tafsili
from app.db import seed
from app.domain.errors import ConcurrencyError, ImmutableDocumentError
from app.repositories import sequences
from app.services import document_service, master_data


pytestmark = pytest.mark.skipif(not os.environ.get("PL_TEST_PG_URL"), reason="PL_TEST_PG_URL not set")


def test_parallel_number_allocation(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(factory, engine)
    s = factory()
    seed.seed_base(s)
    s.commit()
    s.close()
    year = factory()
    fy = master_data.current_fiscal_year(year)
    scope = sequences.document_scope(fy.title)
    year.close()
    got: list[int] = []

    def work():
        session = factory()
        for _ in range(200):
            got.append(sequences.next_value(session, scope))
            session.commit()
        session.close()

    t1 = Thread(target=work)
    t2 = Thread(target=work)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    engine.dispose()
    assert len(set(got)) == 400
    assert sorted(got) == list(range(1, 401))


def test_save_draft_expected_version(pg_url, db_session):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("pg only")
    session = db_session
    seed.seed_base(session)
    year = master_data.current_fiscal_year(session)
    cash = session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    capital = session.execute(select(Account).where(Account.code == "3001")).scalar_one()
    irr = session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    fund = session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    data = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        description="v1",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("1"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("1"), None, None, ""),
        ],
    )
    doc = document_service.save_draft(session, data)
    session.commit()
    old = doc.row_version
    data.description = "v2"
    document_service.save_draft(session, data, doc)
    session.commit()
    session.refresh(doc)
    with pytest.raises(ConcurrencyError):
        document_service.save_draft(session, data, doc, expected_row_version=old)


def test_double_post_one_wins(pg_url):
    engine = build_engine(pg_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(factory, engine)
    s = factory()
    seed.seed_base(s)
    year = master_data.current_fiscal_year(s)
    cash = s.execute(select(Account).where(Account.code == "1001")).scalar_one()
    capital = s.execute(select(Account).where(Account.code == "3001")).scalar_one()
    irr = s.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    fund = s.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    data = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        description="race",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("1"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("1"), None, None, ""),
        ],
    )
    doc = document_service.save_draft(s, data)
    s.commit()
    doc_id = doc.id
    s.close()
    errors: list[type] = []

    def work():
        session = factory()
        d = session.get(Document, doc_id)
        try:
            document_service.post(session, d)
            session.commit()
        except (ImmutableDocumentError, ConcurrencyError) as exc:
            errors.append(type(exc))
            session.rollback()
        session.close()

    t1 = Thread(target=work)
    t2 = Thread(target=work)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    engine.dispose()
    assert len(errors) == 1
