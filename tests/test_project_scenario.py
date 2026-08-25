from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.engine import set_session_factory
from app.db.models import Account, Currency, Document, Tafsili
from app.db import seed
from app.domain.enums import AccountNature, DocumentStatus, DocumentType
from app.services import document_service, ledger_reports, master_data
from app.services.report_service import StatementFilter, account_statement, party_statement


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(factory, engine)
    return factory()


def test_project_a_scenario():
    session = _session()
    seed.seed_base(session)
    seed.seed_demo(session)
    seed.seed_project_example(session)

    accounts = {a.code: a for a in session.execute(select(Account)).scalars()}
    tafsilis = {t.code: t for t in session.execute(select(Tafsili)).scalars()}
    project = tafsilis["3105"]
    assert project.group.code == "30"
    assert len(project.group_ids) >= 2

    transport = account_statement(
        session,
        StatementFilter(
            account_id=accounts["5003"].id,
            tafsili_any_id=project.id,
            include_drafts=False,
            include_opening=False,
        ),
    )
    irr = next(c for c in transport.currencies if c.code == "IRR")
    assert transport.closing[irr.id] == Decimal("25000000")

    travel = account_statement(
        session,
        StatementFilter(
            account_id=accounts["5004"].id,
            tafsili_any_id=project.id,
            include_drafts=False,
            include_opening=False,
        ),
    )
    eur = next(c for c in travel.currencies if c.code == "EUR")
    assert travel.closing[eur.id] == Decimal("15000")

    bank = account_statement(
        session,
        StatementFilter(
            account_id=accounts["1002"].id,
            tafsili_any_id=project.id,
            include_drafts=False,
            include_opening=False,
        ),
    )
    bank_irr = next(c for c in bank.currencies if c.code == "IRR")
    assert bank.closing[bank_irr.id] == Decimal("25000000")

    cash = account_statement(
        session,
        StatementFilter(
            account_id=accounts["1001"].id,
            tafsili_any_id=project.id,
            include_drafts=False,
            include_opening=False,
        ),
    )
    cash_eur = next(c for c in cash.currencies if c.code == "EUR")
    assert cash.closing[cash_eur.id] == Decimal("60000")

    combined = party_statement(
        session,
        StatementFilter(tafsili_any_id=project.id, include_drafts=False, include_opening=False),
    )
    assert len(combined.rows) >= 6

    only_projects = party_statement(
        session,
        StatementFilter(
            tafsili_any_id=project.id,
            group_ids=[project.group_id],
            include_drafts=False,
        ),
    )
    assert not only_projects.is_empty

    journal = ledger_reports.journal(
        session, StatementFilter(tafsili_any_id=project.id, include_drafts=False)
    )
    assert any(row.description for row in journal.rows if row.kind == "line")

    docs = list(session.execute(select(Document)).scalars())
    posted = [d for d in docs if d.status == DocumentStatus.POSTED]
    assert posted
    for doc in posted:
        assert doc.number is not None
        assert len(doc.lines) >= 2


def test_atomic_save_keeps_number_and_lines_together():
    session = _session()
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
        description="آزمایش ذخیره اتمی",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("1000"), Decimal(0), fund.id, None, "بد"),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("1000"), None, None, "بس"),
        ],
    )
    doc = document_service.save_and_post(session, data)
    session.commit()
    loaded = document_service.load(session, doc.id)
    assert loaded.number == 1
    assert loaded.status == DocumentStatus.POSTED
    assert len(loaded.lines) == 2
    assert loaded.lines[0].description == "بد"


def test_statement_respects_date_to():
    import datetime as dt

    from app.domain import jalali

    session = _session()
    seed.seed_base(session)
    year = master_data.current_fiscal_year(session)
    cash = session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    capital = session.execute(select(Account).where(Account.code == "3001")).scalar_one()
    irr = session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    fund = session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    later = year.start_date_g + dt.timedelta(days=20)
    first = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        description="اول بازه",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("5"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("5"), None, None, ""),
        ],
    )
    second = document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=later,
        date_j=jalali.jalali_string(later),
        description="بعد از بازه",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("7"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("7"), None, None, ""),
        ],
    )
    document_service.save_and_post(session, first)
    document_service.save_and_post(session, second)
    session.commit()
    result = account_statement(
        session,
        StatementFilter(
            account_id=cash.id,
            date_from=year.start_date_g,
            date_to=year.start_date_g,
            include_drafts=False,
            include_opening=False,
        ),
    )
    assert [row.description for row in result.rows] == ["اول بازه"]
    assert result.closing[irr.id] == Decimal("5")


def test_browse_hides_opening_docs_when_excluded():
    session = _session()
    seed.seed_base(session)
    seed.seed_demo(session)
    hidden = ledger_reports.browse_accounts(
        session,
        StatementFilter(
            include_drafts=False,
            include_opening=False,
            exclude_doc_types=[DocumentType.OPENING, DocumentType.CLOSING, DocumentType.CLOSE_BOOKS],
        ),
        ledger_reports.LEVEL_MOIN,
    )
    shown = ledger_reports.browse_accounts(
        session,
        StatementFilter(include_drafts=False, include_opening=False, exclude_doc_types=None),
        ledger_reports.LEVEL_MOIN,
    )
    cash_hidden = next(r for r in hidden.rows if r.code == "1001")
    cash_shown = next(r for r in shown.rows if r.code == "1001")
    assert sum(cash_shown.turnover_debit.values()) > sum(cash_hidden.turnover_debit.values())


def test_period_nature_clears_opening_in_trial():
    from app.domain import jalali

    session = _session()
    seed.seed_base(session)
    seed.seed_demo(session)
    cash = session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    cash.nature = AccountNature.DEBIT_PERIOD
    session.flush()
    year = master_data.current_fiscal_year(session)
    start = jalali.gregorian_from_string(f"{year.title}-03-12")
    both = ledger_reports.trial_balance(
        session,
        StatementFilter(date_from=start, include_drafts=False, include_opening=True),
        level=ledger_reports.LEVEL_MOIN,
        columns=6,
    )
    row = next(r for r in both.rows if r.code == "1001")
    assert sum(row.opening_debit.values()) == 0
    assert sum(row.opening_credit.values()) == 0


def test_delete_draft_releases_last_number():
    session = _session()
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
        description="پیش‌نویس دورریختنی",
        lines=[
            document_service.LineInput(cash.id, irr.id, Decimal("1"), Decimal(0), fund.id, None, ""),
            document_service.LineInput(capital.id, irr.id, Decimal(0), Decimal("1"), None, None, ""),
        ],
    )
    doc = document_service.save_draft(session, data)
    number = doc.number
    session.commit()
    document_service.delete_draft(session, doc)
    session.commit()
    assert document_service.next_number_preview(session, year) == number


def test_create_currency_and_fiscal_year():
    session = _session()
    seed.seed_base(session)
    row = master_data.create_currency(session, code="XYZ", name="آزمایشی", decimals=2)
    assert row.code == "XYZ"
    year = master_data.create_fiscal_year(session, 1399)
    assert year.title == "1399"


def test_suggest_tafsili_code_follows_group():
    session = _session()
    seed.seed_base(session)
    group = next(g for g in master_data.tafsili_groups(session) if g.code == "30")
    code = master_data.suggest_tafsili_code(session, group.id)
    assert code.isdigit()
    existing = {t.code for t in master_data.tafsilis(session, group_id=group.id)}
    assert code not in existing
