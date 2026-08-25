"""Baseline chart of accounts, plus an optional demo dataset."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account, Currency, Document, Tafsili, TafsiliGroup
from app.domain import jalali
from app.domain.enums import AccountNature, AccountType, DocumentType
from app.services import account_service, document_service, master_data

CURRENCIES = (
    ("IRR", "ریال", "﷼", 0, 10),
    ("EUR", "یورو", "€", 2, 20),
    ("USD", "دلار آمریکا", "$", 2, 30),
    ("AED", "درهم امارات", "د.إ", 2, 40),
    ("TRY", "لیر ترکیه", "₺", 2, 50),
)

TAFSILI_GROUPS = (
    ("10", "اشخاص"),
    ("20", "صندوق‌ها و بانک‌ها"),
    ("30", "پروژه‌ها"),
    ("40", "مراکز هزینه"),
)

ACCOUNT_GROUPS = (
    ("1", "دارایی‌ها", AccountType.ASSET, 10),
    ("2", "بدهی‌ها", AccountType.LIABILITY, 20),
    ("3", "سرمایه", AccountType.EQUITY, 30),
    ("4", "درآمدها", AccountType.INCOME, 40),
    ("5", "هزینه‌ها", AccountType.EXPENSE, 50),
)

# kol code, kol name, type, list of (moin_code, moin_name, t1_group, t1_required, t2_group)
CHART = (
    (
        "1",
        "دارایی‌ها",
        AccountType.ASSET,
        (
            ("1001", "صندوق", "20", True, "30"),
            ("1002", "بانک", "20", True, "30"),
            ("1003", "حساب‌های دریافتنی", "10", True, "30"),
            ("1004", "پیش‌پرداخت‌ها", "10", True, "30"),
        ),
    ),
    (
        "2",
        "بدهی‌ها",
        AccountType.LIABILITY,
        (
            ("2001", "حساب‌های پرداختنی", "10", True, "30"),
            ("2002", "پیش‌دریافت‌ها", "10", True, "30"),
        ),
    ),
    (
        "3",
        "سرمایه",
        AccountType.EQUITY,
        (
            ("3001", "سرمایه", None, False, None),
            ("3002", "برداشت", "10", False, "30"),
        ),
    ),
    (
        "4",
        "درآمدها",
        AccountType.INCOME,
        (
            ("4001", "درآمد خدمات", "10", False, "30"),
            ("4002", "سایر درآمدها", None, False, "30"),
        ),
    ),
    (
        "5",
        "هزینه‌ها",
        AccountType.EXPENSE,
        (
            ("5001", "حقوق و دستمزد", "10", False, "40"),
            ("5002", "اجاره", None, False, "40"),
            ("5003", "حمل و نقل", None, False, "30"),
            ("5004", "هزینه سفر", "10", False, "30"),
            ("5005", "ملزومات اداری", None, False, "40"),
            ("5006", "کارمزد بانکی", None, False, None),
            ("5007", "سایر هزینه‌ها", None, False, "40"),
        ),
    ),
)

STARTER_TAFSILIS = (
    ("1101", "صندوق اصلی", "20", ()),
    ("1102", "حساب بانکی اصلی", "20", ()),
    ("2101", "شخص نمونه — نام را ویرایش کنید", "10", ()),
    ("3101", "پروژه عمومی", "30", ("40",)),
    ("4101", "دفتر مرکزی", "40", ()),
    # The worked example from the employer's notes. "نفر A" is deliberately a
    # member of both اشخاص and صندوق‌ها so cash held by a named person can sit
    # in the تفصیلی ۱ slot of صندوق, which only accepts group 20.
    ("2105", "کارفرمای B", "10", ()),
    ("2106", "نفر A", "10", ("20",)),
    ("3105", "پروژه A", "30", ("40",)),
)

DEMO_TAFSILIS = (
    ("1001", "صندوق ریالی", "20", ()),
    ("1002", "صندوق یورو", "20", ()),
    ("1003", "صندوق درهم", "20", ()),
    ("1004", "بانک ملت - جاری ۱۲۳", "20", ()),
    ("2001", "شرکت آلفا", "10", ()),
    ("2002", "آقای رضایی", "10", ()),
    ("2003", "خانم محمدی", "10", ()),
    ("2004", "شرکت بتا", "10", ()),
    ("3001", "پروژه تهران", "30", ("40",)),
    ("3002", "پروژه دبی", "30", ("40",)),
    ("4001", "دفتر مرکزی", "40", ()),
)


def is_empty(session: Session) -> bool:
    return session.execute(select(Account.id).limit(1)).first() is None


def has_documents(session: Session) -> bool:
    return bool(session.execute(select(func.count(Document.id))).scalar_one())


def _group_map(session: Session) -> dict[str, int]:
    return {g.code: g.id for g in master_data.tafsili_groups(session)}


def seed_base(session: Session) -> None:
    """Currencies, tafsili groups, chart of accounts, current fiscal year."""
    existing_codes = {c.code for c in master_data.currencies(session)}
    for code, name, symbol, decimals, order in CURRENCIES:
        if code not in existing_codes:
            master_data.create_currency(
                session, code=code, name=name, symbol=symbol, decimals=decimals, sort_order=order
            )
    for code, name in TAFSILI_GROUPS:
        if session.execute(select(TafsiliGroup.id).where(TafsiliGroup.code == code)).scalar_one_or_none() is None:
            master_data.create_tafsili_group(session, code=code, name=name)
    groups_by_type = {}
    for code, name, kind, order in ACCOUNT_GROUPS:
        existing = next((g for g in account_service.account_groups(session) if g.code == code), None)
        if existing is None:
            existing = account_service.create_account_group(
                session, code=code, name=name, account_type=kind, sort_order=order
            )
        groups_by_type[kind] = existing
    tafsili_by_code = _group_map(session)
    for kol_code, kol_name, kind, moins in CHART:
        kol = session.execute(select(Account).where(Account.code == kol_code)).scalar_one_or_none()
        if kol is None:
            kol = account_service.create(
                session,
                code=kol_code,
                name=kol_name,
                group_id=groups_by_type[kind].id,
                account_type=kind,
                nature=AccountNature.BOTH,
            )
        for moin_code, moin_name, t1, t1_req, t2 in moins:
            if session.execute(select(Account.id).where(Account.code == moin_code)).first():
                continue
            rules: list[tuple[int, int]] = []
            if t1:
                rules.append((tafsili_by_code[t1], 1))
            if t2:
                rules.append((tafsili_by_code[t2], 2))
            account_service.create(
                session,
                code=moin_code,
                name=moin_name,
                parent_id=kol.id,
                nature=AccountNature.BOTH,
                tafsili1_required=bool(t1_req),
                tafsili_rules=rules,
            )
    for code, name, group_code, extra in STARTER_TAFSILIS:
        if session.execute(select(Tafsili.id).where(Tafsili.code == code)).first():
            continue
        master_data.create_tafsili(
            session,
            code=code,
            name=name,
            group_id=tafsili_by_code[group_code],
            extra_group_ids=[tafsili_by_code[c] for c in extra],
        )
    if not master_data.fiscal_years(session):
        master_data.create_fiscal_year(session, jalali.today_jalali().year)
    session.commit()


def _ids(session: Session) -> tuple[dict[str, int], dict[str, int], dict[str, int], int]:
    accounts = {a.code: a.id for a in account_service.all_accounts(session, include_inactive=True)}
    currencies = {c.code: c.id for c in master_data.currencies(session)}
    from app.db.models import Tafsili

    tafsilis = {t.code: t.id for t in session.execute(select(Tafsili)).scalars()}
    year = master_data.current_fiscal_year(session)
    return accounts, currencies, tafsilis, year.id


def seed_demo(session: Session) -> None:
    """Sample data for testing. Includes the exact combined entry from the brief."""
    tafsili_by_code = _group_map(session)
    from app.db.models import Tafsili

    for code, name, group_code, extra in DEMO_TAFSILIS:
        if session.execute(select(Tafsili.id).where(Tafsili.code == code)).first():
            continue
        master_data.create_tafsili(
            session,
            code=code,
            name=name,
            group_id=tafsili_by_code[group_code],
            extra_group_ids=[tafsili_by_code[c] for c in extra],
        )
    session.flush()
    accounts, currencies, tafsilis, year_id = _ids(session)
    year = master_data.current_fiscal_year(session)
    jyear = int(year.title)

    def make(day_j: str, doc_type: DocumentType, description: str, rows: list[tuple]) -> None:
        date_j = f"{jyear}-{day_j}"
        lines = []
        for account_code, t1, t2, cur, debit, credit, desc in rows:
            lines.append(
                document_service.LineInput(
                    account_id=accounts[account_code],
                    tafsili1_id=tafsilis.get(t1) if t1 else None,
                    tafsili2_id=tafsilis.get(t2) if t2 else None,
                    currency_id=currencies[cur],
                    debit=Decimal(debit),
                    credit=Decimal(credit),
                    description=desc,
                )
            )
        document_service.save_and_post(
            session,
            document_service.DocumentInput(
                fiscal_year_id=year_id,
                date_g=jalali.gregorian_from_string(date_j),
                date_j=date_j,
                doc_type=doc_type,
                description=description,
                lines=lines,
            ),
        )

    make(
        "01-01",
        DocumentType.OPENING,
        "سند افتتاحیه",
        [
            ("1001", "1001", None, "IRR", "50000000", "0", "موجودی اول دوره صندوق"),
            ("3001", None, None, "IRR", "0", "50000000", "سرمایه اول دوره"),
            ("1002", "1002", None, "EUR", "20000", "0", "موجودی اول دوره صندوق یورو"),
            ("3001", None, None, "EUR", "0", "20000", "سرمایه ارزی"),
        ],
    )
    make(
        "03-12",
        DocumentType.GENERAL,
        "دریافت ۵۰٬۰۰۰ یورو و تخصیص آن",
        [
            ("1001", "1002", None, "EUR", "50000", "0", "دریافت ۵۰٬۰۰۰ یورو"),
            ("5004", "2001", "3002", "EUR", "0", "18000", "هزینه سفر"),
            ("5003", None, "3002", "EUR", "0", "12000", "حمل و نقل"),
            ("2001", "2002", None, "EUR", "0", "20000", "انتقال به آقای رضایی"),
        ],
    )
    make(
        "03-20",
        DocumentType.INCOME,
        "صورتحساب خدمات شرکت آلفا",
        [
            ("1003", "2001", "3001", "IRR", "80000000", "0", "طلب از آلفا"),
            ("4001", "2001", "3001", "IRR", "0", "80000000", "درآمد خدمات"),
        ],
    )
    make(
        "03-25",
        DocumentType.PARTY,
        "دریافت از شرکت آلفا",
        [
            ("1002", "1004", "3001", "IRR", "30000000", "0", "واریز به بانک"),
            ("1003", "2001", "3001", "IRR", "0", "30000000", "کاهش طلب"),
        ],
    )
    make(
        "03-28",
        DocumentType.EXPENSE,
        "هزینه‌های اداری خرداد",
        [
            ("5002", None, "4001", "IRR", "12000000", "0", "اجاره دفتر"),
            ("1002", "1004", None, "IRR", "0", "12000000", "پرداخت اجاره"),
        ],
    )
    make(
        "04-02",
        DocumentType.TRANSFER,
        "انتقال بین صندوق‌ها",
        [
            ("1001", "1001", None, "IRR", "5000000", "0", "انتقال به صندوق"),
            ("1002", "1004", None, "IRR", "0", "5000000", "برداشت از بانک"),
        ],
    )
    make(
        "04-10",
        DocumentType.EXPENSE,
        "حقوق تیر ماه",
        [
            ("5001", "2003", "4001", "IRR", "18000000", "0", "حقوق"),
            ("1002", "1004", None, "IRR", "0", "18000000", "پرداخت حقوق"),
        ],
    )
    master_data.lock_used_currencies(session)
    session.commit()


def seed_project_example(session: Session) -> None:
    """The scenario from the employer's notes, posted end to end.

    قرارداد پروژه A با کارفرمای B: ۲۰۰٬۰۰۰٬۰۰۰ ریال و ۳۰۰٬۰۰۰ یورو.
    دریافت ۲۵٪ از هر دو (ریالی به بانک، ارزی نقدی به صندوق).
    هزینه پروژه: ۲۵٬۰۰۰٬۰۰۰ ریال و ۱۵٬۰۰۰ یورو.

    Every line carries تفصیلی ۲ = پروژه A, which is what makes the three
    project reports possible without any extra bookkeeping.
    """
    accounts, currencies, tafsilis, year_id = _ids(session)
    year = master_data.current_fiscal_year(session)
    jyear = int(year.title)

    def post(day_j: str, doc_type: DocumentType, description: str, rows: list[tuple]) -> None:
        date_j = f"{jyear}-{day_j}"
        lines = [
            document_service.LineInput(
                account_id=accounts[account_code],
                tafsili1_id=tafsilis.get(t1) if t1 else None,
                tafsili2_id=tafsilis.get(t2) if t2 else None,
                currency_id=currencies[cur],
                debit=Decimal(debit),
                credit=Decimal(credit),
                description=desc,
            )
            for account_code, t1, t2, cur, debit, credit, desc in rows
        ]
        document_service.save_and_post(
            session,
            document_service.DocumentInput(
                fiscal_year_id=year_id,
                date_g=jalali.gregorian_from_string(date_j),
                date_j=date_j,
                doc_type=doc_type,
                description=description,
                lines=lines,
            ),
        )

    employer, person_a, project = "2105", "2106", "3105"
    bank, cash = "1102", "1101"
    post(
        "05-01",
        DocumentType.PARTY,
        "انعقاد قرارداد پروژه A با کارفرمای B",
        [
            ("1003", employer, project, "IRR", "200000000", "0", "مبلغ قرارداد — ریالی"),
            ("2002", employer, project, "IRR", "0", "200000000", "پیش‌دریافت قرارداد"),
            ("1003", employer, project, "EUR", "300000", "0", "مبلغ قرارداد — ارزی"),
            ("2002", employer, project, "EUR", "0", "300000", "پیش‌دریافت قرارداد"),
        ],
    )
    post(
        "05-08",
        DocumentType.PARTY,
        "دریافت ۲۵٪ از مبلغ قرارداد پروژه A",
        [
            ("1002", bank, project, "IRR", "50000000", "0", "واریز ۲۵٪ ریالی به بانک"),
            ("1003", employer, project, "IRR", "0", "50000000", "کاهش طلب از کارفرما"),
            ("1001", person_a, project, "EUR", "75000", "0", "دریافت ۲۵٪ ارزی نقدی در صندوق به نفر A"),
            ("1003", employer, project, "EUR", "0", "75000", "کاهش طلب از کارفرما"),
        ],
    )
    post(
        "05-12",
        DocumentType.EXPENSE,
        "هزینه‌های پروژه A",
        [
            ("5003", None, project, "IRR", "25000000", "0", "هزینه ریالی پروژه A"),
            ("1002", bank, project, "IRR", "0", "25000000", "پرداخت از بانک"),
            ("5004", employer, project, "EUR", "15000", "0", "هزینه ارزی پروژه A"),
            ("1001", person_a, project, "EUR", "0", "15000", "پرداخت نقدی از صندوق"),
        ],
    )
    session.commit()
