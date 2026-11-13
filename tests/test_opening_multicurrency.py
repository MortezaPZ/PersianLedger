from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app import bootstrap, config as config_module
from app.db import seed
from app.db.base import Base
from app.db.models import Account, Currency, DocumentLine, Tafsili
from app.domain.enums import DocumentType
from app.domain.errors import ValidationError
from app.services import document_service, master_data
from app.ui.context import AppContext
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.widgets.line_grid import COL_ACCOUNT, COL_T1


@pytest.fixture
def opening_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        seed.seed_base(session)
        yield session
    engine.dispose()


def test_opening_balance_requires_every_active_currency_and_stores_only_nonzero_lines(opening_session):
    session = opening_session
    year = master_data.current_fiscal_year(session)
    cash = session.scalar(select(Account).where(Account.code == "1001"))
    capital = session.scalar(select(Account).where(Account.code == "3001"))
    cash_tafsili = session.scalar(select(Tafsili).where(Tafsili.code == "1101"))
    currencies = list(session.execute(select(Currency).where(Currency.is_active.is_(True))).scalars())
    irr = next(currency for currency in currencies if currency.code == "IRR")

    data = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        doc_type=DocumentType.OPENING,
        description="افتتاحیه چندارزی",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("10"), Decimal(0), cash_tafsili.id),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("10")),
        ],
    )

    with pytest.raises(ValidationError, match="ارزهای"):
        document_service.validate(session, data)

    for account_id, tafsili1_id in ((cash.id, cash_tafsili.id), (capital.id, None)):
        present = {line.currency_id for line in data.lines if line.account_id == account_id}
        for currency in currencies:
            if currency.id not in present:
                data.lines.append(
                    document_service.LineInput(
                        account_id,
                        currency.id,
                        Decimal(0),
                        Decimal(0),
                        tafsili1_id,
                    )
                )

    document_service.validate(session, data)
    document = document_service.save_and_post(session, data)
    stored_lines = list(
        session.execute(select(DocumentLine).where(DocumentLine.document_id == document.id)).scalars()
    )
    assert len(stored_lines) == 2
    assert {line.currency_id for line in stored_lines} == {irr.id}


def test_opening_entry_view_adds_rows_for_all_allowed_currencies(qapp, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cfg = config_module.AppConfig(data_dir=data_dir, sqlite_path=data_dir / "ledger.sqlite3")
    ctx = AppContext(bootstrap.start(cfg, with_demo=False))
    view = DocumentEntryView(ctx)
    view.type_combo.setCurrentIndex(view.type_combo.findData(DocumentType.OPENING))

    cash = next(account for account in ctx.refdata.postable if account.code == "1001")
    cash_tafsili = next(item for item in ctx.refdata.tafsilis if item.code == "1101")
    view.model.setData(view.model.index(0, COL_ACCOUNT), cash.id)
    view.model.setData(view.model.index(0, COL_T1), cash_tafsili.id)

    expected = {currency.id for currency in ctx.refdata.currencies_for(cash.id)}
    rows = [row for row in view.model.rows if row.account_id == cash.id]
    assert {row.currency_id for row in rows} == expected
    assert len(rows) == len(expected)
    assert all(row.tafsili1_id == cash_tafsili.id for row in rows)

    data = view._input()
    assert {line.currency_id for line in data.lines if line.account_id == cash.id} == expected
    view.close()
