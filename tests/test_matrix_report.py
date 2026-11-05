from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.db import seed
from app.db.models import Account, Currency, Document, DocumentLine, Tafsili, TafsiliGroup
from app.domain.enums import DocumentStatus, DocumentType
from app.services.report_service import tafsili_moein_matrix
from app.services import master_data


def _post_line(session, *, year, number, date, account, tafsili, currency, debit=0, credit=0):
    document = Document(
        fiscal_year_id=year.id,
        number=number,
        doc_type=DocumentType.GENERAL,
        date_g=date,
        date_j=year.start_date_j,
        description=f"سند {number}",
        status=DocumentStatus.POSTED,
    )
    document.lines.append(
        DocumentLine(
            line_no=1,
            account_id=account.id,
            tafsili1_id=tafsili.id,
            currency_id=currency.id,
            debit=Decimal(debit),
            credit=Decimal(credit),
        )
    )
    session.add(document)
    session.flush()


def test_matrix_rolls_up_descendants_by_moein_and_keeps_currencies_separate(db_session):
    seed.seed_base(db_session)
    year = master_data.current_fiscal_year(db_session)
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    root = Tafsili(code="92001", name="صندوق‌ها", group_id=group.id)
    branch = Tafsili(code="92002", name="شعبه شمال", group_id=group.id, parent=root)
    leaf_a = Tafsili(code="92003", name="صندوق یک", group_id=group.id, parent=branch)
    leaf_b = Tafsili(code="92004", name="صندوق دو", group_id=group.id, parent=root)
    outside = Tafsili(code="92005", name="صندوق بیرونی", group_id=group.id)
    db_session.add_all([root, branch, leaf_a, leaf_b, outside])
    db_session.flush()
    cash = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    bank = db_session.execute(select(Account).where(Account.code == "1002")).scalar_one()
    irr = db_session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    usd = db_session.execute(select(Currency).where(Currency.code == "USD")).scalar_one()
    from_date = year.start_date_g + dt.timedelta(days=5)
    to_date = year.start_date_g + dt.timedelta(days=20)

    # Legacy rows on a node remain visible after that node becomes a parent.
    _post_line(db_session, year=year, number=7001, date=year.start_date_g, account=cash, tafsili=root, currency=irr, debit=2)
    _post_line(db_session, year=year, number=7006, date=year.start_date_g, account=cash, tafsili=leaf_a, currency=irr, debit=3)
    _post_line(db_session, year=year, number=7002, date=from_date, account=cash, tafsili=leaf_a, currency=irr, debit=10)
    _post_line(db_session, year=year, number=7003, date=from_date, account=cash, tafsili=leaf_b, currency=irr, credit=4)
    _post_line(db_session, year=year, number=7004, date=from_date, account=bank, tafsili=leaf_a, currency=usd, debit=2)
    _post_line(db_session, year=year, number=7005, date=from_date, account=cash, tafsili=outside, currency=irr, debit=99)
    _post_line(db_session, year=year, number=7007, date=from_date, account=bank, tafsili=leaf_b, currency=usd, credit=5)

    result = tafsili_moein_matrix(db_session, root.id, from_date, to_date, None)
    assert set(result.tafsili_ids) == {root.id, branch.id, leaf_a.id, leaf_b.id}
    rows = {row.account_id: row for row in result.rows}
    cash_irr = rows[cash.id].amounts[irr.id]
    bank_usd = rows[bank.id].amounts[usd.id]

    assert cash_irr.debit_turnover == Decimal("10")
    assert cash_irr.credit_turnover == Decimal("4")
    assert cash_irr.debit_balance == Decimal("11")
    assert cash_irr.credit_balance == Decimal("0")
    assert bank_usd.debit_turnover == Decimal("2")
    assert bank_usd.credit_turnover == Decimal("5")
    assert bank_usd.debit_balance == Decimal("0")
    assert bank_usd.credit_balance == Decimal("3")
    assert bank_usd.debit_turnover != cash_irr.debit_turnover
    assert set(rows) == {cash.id, bank.id}


def test_matrix_leaf_filter_excludes_sibling_descendants(db_session):
    seed.seed_base(db_session)
    year = master_data.current_fiscal_year(db_session)
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    parent = Tafsili(code="93001", name="درخت", group_id=group.id)
    chosen = Tafsili(code="93002", name="انتخابی", group_id=group.id, parent=parent)
    sibling = Tafsili(code="93003", name="هم‌سطح", group_id=group.id, parent=parent)
    db_session.add_all([parent, chosen, sibling])
    db_session.flush()
    cash = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    irr = db_session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    date = year.start_date_g + dt.timedelta(days=5)
    _post_line(db_session, year=year, number=7101, date=date, account=cash, tafsili=chosen, currency=irr, debit=5)
    _post_line(db_session, year=year, number=7102, date=date, account=cash, tafsili=sibling, currency=irr, debit=8)

    result = tafsili_moein_matrix(db_session, chosen.id, date, date, [irr.id])
    row = next(row for row in result.rows if row.account_id == cash.id)
    assert row.amounts[irr.id].debit_turnover == Decimal("5")
    assert row.amounts[irr.id].debit_balance == Decimal("5")


def test_matrix_report_view_has_tree_date_currency_filters_and_four_amount_columns(qapp, tmp_path):
    from app import bootstrap, config as config_module
    from app.ui.context import AppContext
    from app.ui.views.tafsili_moein_matrix_view import TafsiliMoeinMatrixView

    data_dir = tmp_path / "matrix-ui-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data_dir, sqlite_path=data_dir / "ledger.sqlite3")
    context = AppContext(bootstrap.start(cfg))
    view = TafsiliMoeinMatrixView(context)
    selected = next(item for item in context.refdata.tafsilis if item.code == "1101")
    view.tafsili.setCurrentIndex(view.tafsili.findData(selected.id))
    view.run()

    assert view._result.title == "گردش حساب‌های معین به تفکیک تفصیلی"
    assert view.tree_button.text() == "درخت…"
    assert view.from_date.gregorian() is not None
    assert view.to_date.gregorian() is not None
    assert view.model.columnCount() == 2 + 4 * len(view._result.currencies)
    view.close()
