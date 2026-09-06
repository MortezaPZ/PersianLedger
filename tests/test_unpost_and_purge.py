from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Account, AuditLog, Currency, Document, DocumentLine, Tafsili
from app.db import seed
from app.domain.enums import AuditAction, DocumentStatus
from app.domain.errors import ValidationError
from app.services import document_service, master_data
from tests.test_project_scenario import _session


def _post(session, description: str = "آزمایش") -> Document:
    year = master_data.current_fiscal_year(session)
    cash = session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    capital = session.execute(select(Account).where(Account.code == "3001")).scalar_one()
    irr = session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    fund = session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    data = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        description=description,
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("10"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("10"), None, None, ""),
        ],
    )
    return document_service.save_and_post(session, data)


def test_unpost_then_post_keeps_number():
    session = _session()
    seed.seed_base(session)
    doc = _post(session)
    number = doc.number
    document_service.unpost(session, doc, user_id=None)
    session.flush()
    assert doc.status == DocumentStatus.DRAFT
    assert doc.posted_at is None
    actions = [r.action for r in session.execute(select(AuditLog)).scalars() if r.action == AuditAction.UNPOST]
    assert actions
    document_service.post(session, doc)
    assert doc.number == number
    assert doc.status == DocumentStatus.POSTED


def test_unpost_reversed_and_correction_target_raise():
    session = _session()
    seed.seed_base(session)
    original = _post(session, "اصلی")
    year = master_data.current_fiscal_year(session)
    document_service.reverse(session, original, year.start_date_g, year.start_date_j)
    session.flush()
    session.refresh(original)
    with pytest.raises(ValidationError):
        document_service.unpost(session, original)

    other = _post(session, "اصلاح‌شونده")
    pointer = _post(session, "ارجاع اصلاح")
    pointer.corrects_document_id = other.id
    session.flush()
    with pytest.raises(ValidationError):
        document_service.unpost(session, other)


def test_delete_posted_lines_and_number_release():
    session = _session()
    seed.seed_base(session)
    first = _post(session, "اول")
    second = _post(session, "دوم")
    first_id = first.id
    document_service.delete_posted(session, first)
    session.flush()
    assert session.get(Document, first_id) is None
    leftover = session.execute(select(DocumentLine).where(DocumentLine.document_id == first_id)).scalars().all()
    assert leftover == []
    year = master_data.current_fiscal_year(session)
    assert document_service.next_number_preview(session, year) == 3

    second_id = second.id
    document_service.delete_posted(session, second)
    session.flush()
    assert session.get(Document, second_id) is None
    assert document_service.next_number_preview(session, year) == 2


def test_purge_fiscal_year_resets_numbering():
    session = _session()
    seed.seed_base(session)
    _post(session, "۱")
    _post(session, "۲")
    _post(session, "۳")
    year = master_data.current_fiscal_year(session)
    count = document_service.purge_fiscal_year(session, year)
    session.flush()
    assert count == 3
    assert session.execute(select(Document)).scalars().all() == []
    assert document_service.next_number_preview(session, year) == 1


def test_closed_year_blocks_unpost_and_purge():
    session = _session()
    seed.seed_base(session)
    doc = _post(session)
    year = master_data.current_fiscal_year(session)
    master_data.set_year_closed(session, year, True)
    session.flush()
    with pytest.raises(ValidationError):
        document_service.unpost(session, doc)
    with pytest.raises(ValidationError):
        document_service.purge_fiscal_year(session, year)
