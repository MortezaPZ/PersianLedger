"""Trial balance, journal and general ledger.

One row per (account, currency) pair. Currencies are reported side by side and
never added together, so no exchange rate is needed and none exists.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, replace
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Account, AccountGroup, Currency, Document, DocumentLine, Tafsili
from app.domain import money
from app.domain.enums import ACCOUNT_TYPE_FA, DOCUMENT_TYPE_FA, AccountType, DocumentStatus, nature_carries_opening
from app.services.report_service import CurrencyColumn, StatementFilter, StatementResult, _apply_scope, account_statement

ZERO = Decimal(0)


def _sql_money(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return money.from_minor_units(int(value))
LEVEL_KOL = "kol"
LEVEL_MOIN = "moin"
LEVEL_TAFSILI = "tafsili"
LEVEL_TAFSILI2 = "tafsili2"
LEVEL_GROUP = "group"
LEVEL_FA = {
    LEVEL_KOL: "کل",
    LEVEL_MOIN: "معین",
    LEVEL_TAFSILI: "تفصیلی ۱",
    LEVEL_TAFSILI2: "تفصیلی ۲",
}
TAFSILI_LEVELS = (LEVEL_TAFSILI, LEVEL_TAFSILI2)
BROWSE_LEVELS = (LEVEL_GROUP, LEVEL_KOL, LEVEL_MOIN, LEVEL_TAFSILI, LEVEL_TAFSILI2)
BROWSE_LEVEL_FA = {
    LEVEL_GROUP: "گروه",
    LEVEL_KOL: "کل",
    LEVEL_MOIN: "معین",
    LEVEL_TAFSILI: "تفصیلی ۱",
    LEVEL_TAFSILI2: "تفصیلی ۲",
}
COLUMN_SETS = (2, 4, 6)
NO_TAFSILI = 0


def _day_before(day: _dt.date) -> _dt.date:
    return day - _dt.timedelta(days=1)


def _window_label(flt: StatementFilter) -> str:
    if flt.date_from and flt.date_to:
        return f"از {flt.date_from} تا {flt.date_to}"
    if flt.date_from:
        return f"از {flt.date_from}"
    if flt.date_to:
        return f"تا {flt.date_to}"
    return "کل دوره"


def _aggregate(
    session: Session,
    flt: StatementFilter,
    group_column,
    date_from: _dt.date | None,
    date_to: _dt.date | None,
    keep_null_key: bool = False,
) -> dict[tuple[int, int], tuple[Decimal, Decimal]]:
    """{(group_key, currency_id): (debit, credit)} over the given date window."""
    stmt = select(
        group_column,
        DocumentLine.currency_id,
        func.coalesce(func.sum(DocumentLine.debit), 0),
        func.coalesce(func.sum(DocumentLine.credit), 0),
    )
    if group_column in (Account.parent_id, Account.group_id):
        stmt = stmt.join(Account, DocumentLine.account_id == Account.id)
    stmt = _apply_scope(stmt, flt)
    if date_from:
        stmt = stmt.where(Document.date_g >= date_from)
    if date_to:
        stmt = stmt.where(Document.date_g <= date_to)
    stmt = stmt.group_by(group_column, DocumentLine.currency_id)
    result: dict[tuple[int, int], tuple[Decimal, Decimal]] = {}
    for key, currency_id, debit, credit in session.execute(stmt):
        if key is None:
            if not keep_null_key:
                continue
            key = NO_TAFSILI
        result[(int(key), int(currency_id))] = (_sql_money(debit), _sql_money(credit))
    return result


@dataclass
class TrialBalanceRow:
    """One account, with a full set of figures for every currency column."""

    kind: str
    code: str
    name: str
    key: int | None = None
    opening_debit: dict[int, Decimal] = field(default_factory=dict)
    opening_credit: dict[int, Decimal] = field(default_factory=dict)
    turnover_debit: dict[int, Decimal] = field(default_factory=dict)
    turnover_credit: dict[int, Decimal] = field(default_factory=dict)
    closing_debit: dict[int, Decimal] = field(default_factory=dict)
    closing_credit: dict[int, Decimal] = field(default_factory=dict)

    def sources(self, columns: int) -> list[dict[int, Decimal]]:
        if columns == 2:
            return [self.closing_debit, self.closing_credit]
        if columns == 4:
            return [self.turnover_debit, self.turnover_credit, self.closing_debit, self.closing_credit]
        return [
            self.opening_debit,
            self.opening_credit,
            self.turnover_debit,
            self.turnover_credit,
            self.closing_debit,
            self.closing_credit,
        ]

    def cell(self, columns: int, offset: int, currency_id: int) -> Decimal:
        return self.sources(columns)[offset].get(currency_id, ZERO)

    def total(self, columns: int, offset: int) -> Decimal:
        return sum(self.sources(columns)[offset].values(), ZERO)


@dataclass
class TrialBalanceResult:
    title: str
    subtitle: str
    level: str
    columns: int
    currencies: list[CurrencyColumn]
    rows: list[TrialBalanceRow]

    @property
    def is_empty(self) -> bool:
        return not self.rows


def _split(balance: Decimal) -> tuple[Decimal, Decimal]:
    if balance >= 0:
        return balance, ZERO
    return ZERO, -balance


def _currencies_from_maps(session: Session, maps: list[dict[tuple[int, int], tuple[Decimal, Decimal]]], flt: StatementFilter) -> list[CurrencyColumn]:
    ids = set()
    for mapping in maps:
        ids.update(cid for _k, cid in mapping)
    if flt.currency_ids:
        ids = set(flt.currency_ids) & ids if ids else set(flt.currency_ids)
    stmt = select(Currency).order_by(Currency.sort_order, Currency.code)
    if ids:
        stmt = stmt.where(Currency.id.in_(ids))
    return [CurrencyColumn(c.id, c.code, c.name, c.decimals) for c in session.execute(stmt).scalars()]


def trial_balance(session: Session, flt: StatementFilter, level: str = LEVEL_MOIN, columns: int = 4) -> TrialBalanceResult:
    columns = columns if columns in COLUMN_SETS else 4
    opening: dict[tuple[int, int], tuple[Decimal, Decimal]] = {}
    if flt.include_opening and flt.date_from:
        opening = _aggregate(session, flt, _group_column(level), None, _day_before(flt.date_from), keep_null_key=level in TAFSILI_LEVELS)
    turnover = _aggregate(
        session,
        flt,
        _group_column(level),
        flt.date_from,
        flt.date_to,
        keep_null_key=level in TAFSILI_LEVELS,
    )
    currencies = _currencies_from_maps(session, [opening, turnover], flt)
    names = _names_for_level(session, level)
    opening_ok = _opening_allowed_by_key(session, level)
    keys = {k for k, _c in opening} | {k for k, _c in turnover}
    rows: list[TrialBalanceRow] = []
    for key in sorted(keys, key=lambda k: names.get(k, ("", ""))[0]):
        code, name = names.get(key, (str(key), "بدون تفصیلی" if key == NO_TAFSILI else str(key)))
        row = TrialBalanceRow(kind=level, code=code, name=name, key=key)
        allow_open = opening_ok.get(key, True)
        for col in currencies:
            od, oc = opening.get((key, col.id), (ZERO, ZERO)) if allow_open else (ZERO, ZERO)
            td, tc = turnover.get((key, col.id), (ZERO, ZERO))
            open_bal = od - oc
            close_bal = open_bal + td - tc
            row.opening_debit[col.id], row.opening_credit[col.id] = _split(open_bal)
            row.turnover_debit[col.id] = td
            row.turnover_credit[col.id] = tc
            row.closing_debit[col.id], row.closing_credit[col.id] = _split(close_bal)
        rows.append(row)
    totals = TrialBalanceRow(kind="total", code="", name="جمع")
    for col in currencies:
        for src in (
            "opening_debit",
            "opening_credit",
            "turnover_debit",
            "turnover_credit",
            "closing_debit",
            "closing_credit",
        ):
            getattr(totals, src)[col.id] = sum((getattr(r, src).get(col.id, ZERO) for r in rows), ZERO)
    if rows:
        rows.append(totals)
    return TrialBalanceResult(
        title=f"تراز آزمایشی — سطح {LEVEL_FA.get(level, level)}",
        subtitle=_window_label(flt),
        level=level,
        columns=columns,
        currencies=currencies,
        rows=rows,
    )


def _group_column(level: str):
    if level == LEVEL_KOL:
        return Account.parent_id
    if level == LEVEL_TAFSILI:
        return DocumentLine.tafsili1_id
    if level == LEVEL_TAFSILI2:
        return DocumentLine.tafsili2_id
    if level == LEVEL_GROUP:
        return Account.group_id
    return DocumentLine.account_id


def _opening_allowed_by_key(session: Session, level: str) -> dict[int, bool]:
    accounts = list(session.execute(select(Account)).scalars())
    by_id = {a.id: a for a in accounts}
    if level == LEVEL_MOIN:
        return {a.id: nature_carries_opening(a.nature) for a in accounts}
    if level == LEVEL_KOL:
        out: dict[int, bool] = {}
        for a in accounts:
            if a.level != 1:
                continue
            children = [c for c in accounts if c.parent_id == a.id]
            natures = [c.nature for c in children] or [a.nature]
            out[a.id] = any(nature_carries_opening(n) for n in natures)
        return out
    if level == LEVEL_GROUP:
        out = {}
        for a in accounts:
            gid = a.group_id
            if gid is None:
                continue
            out[gid] = out.get(gid, False) or nature_carries_opening(a.nature)
        return out
    return {a.id: nature_carries_opening(a.nature) for a in by_id.values()}


def _names_for_level(session: Session, level: str) -> dict[int, tuple[str, str]]:
    if level == LEVEL_GROUP:
        return {g.id: (g.code, g.name) for g in session.execute(select(AccountGroup)).scalars()}
    if level in TAFSILI_LEVELS:
        names = {t.id: (t.code, t.name) for t in session.execute(select(Tafsili)).scalars()}
        names[NO_TAFSILI] = ("", "بدون تفصیلی")
        return names
    accounts = list(session.execute(select(Account)).scalars())
    if level == LEVEL_KOL:
        return {a.id: (a.code, a.name) for a in accounts if a.level == 1}
    return {a.id: (a.code, a.name) for a in accounts}


@dataclass
class JournalRow:
    kind: str
    date_j: str
    number: str
    line_no: str
    account: str
    tafsili: str
    description: str
    document_id: int | None
    is_draft: bool
    amounts: dict[int, tuple[Decimal, Decimal]]


@dataclass
class JournalResult:
    title: str
    subtitle: str
    currencies: list[CurrencyColumn]
    rows: list[JournalRow]

    @property
    def is_empty(self) -> bool:
        return not self.rows


def journal(session: Session, flt: StatementFilter) -> JournalResult:
    stmt = (
        select(DocumentLine, Document, Account)
        .join(Account, DocumentLine.account_id == Account.id)
    )
    stmt = _apply_scope(stmt, flt)
    if flt.date_from:
        stmt = stmt.where(Document.date_g >= flt.date_from)
    if flt.date_to:
        stmt = stmt.where(Document.date_g <= flt.date_to)
    stmt = stmt.order_by(Document.date_g, Document.number, DocumentLine.line_no)
    raw = list(session.execute(stmt))
    used = {line.currency_id for line, _d, _a in raw}
    currencies = _currencies_from_maps(session, [{(0, cid): (ZERO, ZERO) for cid in used}], flt)
    tafsili_by_id = {t.id: t for t in session.execute(select(Tafsili)).scalars()}
    rows: list[JournalRow] = []
    current_id = None
    doc_totals: dict[int, list[Decimal]] = {}

    def tafsili_text(line: DocumentLine) -> str:
        parts = []
        for tid in (line.tafsili1_id, line.tafsili2_id):
            item = tafsili_by_id.get(tid) if tid else None
            if item:
                parts.append(item.display)
        return " / ".join(parts)

    def flush_doc_totals(doc: Document | None) -> None:
        if not doc_totals:
            return
        for cid, (debit, credit) in doc_totals.items():
            amounts = {col.id: (ZERO, ZERO) for col in currencies}
            amounts[cid] = (debit, credit)
            rows.append(
                JournalRow(
                    "subtotal",
                    "",
                    doc.number_display if doc else "",
                    "",
                    "",
                    "",
                    "جمع سند",
                    doc.id if doc else None,
                    False,
                    amounts,
                )
            )
        doc_totals.clear()

    last_doc = None
    for line, doc, acc in raw:
        if current_id is not None and doc.id != current_id:
            flush_doc_totals(last_doc)
        current_id = doc.id
        last_doc = doc
        amounts = {col.id: (ZERO, ZERO) for col in currencies}
        debit, credit = Decimal(line.debit or 0), Decimal(line.credit or 0)
        amounts[line.currency_id] = (debit, credit)
        bucket = doc_totals.setdefault(line.currency_id, [ZERO, ZERO])
        bucket[0] += debit
        bucket[1] += credit
        desc = (line.description or "").strip() or (doc.description or "")
        rows.append(
            JournalRow(
                "line",
                doc.date_j,
                doc.number_display,
                str(line.line_no),
                acc.display,
                tafsili_text(line),
                desc,
                doc.id,
                doc.status == DocumentStatus.DRAFT,
                amounts,
            )
        )
    flush_doc_totals(last_doc)
    period: dict[int, list[Decimal]] = {}
    for row in rows:
        if row.kind != "line":
            continue
        for cid, (d, c) in row.amounts.items():
            bucket = period.setdefault(cid, [ZERO, ZERO])
            bucket[0] += d
            bucket[1] += c
    for cid, (d, c) in period.items():
        amounts = {col.id: (ZERO, ZERO) for col in currencies}
        amounts[cid] = (d, c)
        rows.append(JournalRow("total", "", "", "", "", "", "جمع کل دوره", None, False, amounts))
    return JournalResult("دفتر روزنامه", _window_label(flt), currencies, rows)


@dataclass
class LedgerSection:
    account_id: int
    code: str
    name: str
    result: StatementResult


@dataclass
class LedgerResult:
    title: str
    subtitle: str
    sections: list[LedgerSection]

    @property
    def is_empty(self) -> bool:
        return not self.sections


def general_ledger(session: Session, flt: StatementFilter, kol: bool = False) -> LedgerResult:
    accounts = list(session.execute(select(Account).where(Account.is_postable.is_(True)).order_by(Account.code)).scalars())
    sections: list[LedgerSection] = []
    for account in accounts:
        child_ids = [account.id]
        if kol and account.level == 1:
            continue
        scoped = StatementFilter(
            account_id=account.id if not kol else None,
            account_ids=[account.id] if not kol else [c.id for c in accounts if c.parent_id == account.id] or [account.id],
            date_from=flt.date_from,
            date_to=flt.date_to,
            currency_ids=flt.currency_ids,
            group_ids=flt.group_ids,
            include_drafts=flt.include_drafts,
            include_opening=flt.include_opening,
            tafsili_id=flt.tafsili_id,
            tafsili_any_id=flt.tafsili_any_id,
        )
        if kol:
            continue
        result = account_statement(session, scoped)
        if result.rows:
            sections.append(LedgerSection(account.id, account.code, account.name, result))
    if kol:
        kols = [a for a in session.execute(select(Account).where(Account.level == 1).order_by(Account.code)).scalars()]
        for parent in kols:
            children = [a.id for a in accounts if a.parent_id == parent.id]
            if not children:
                continue
            scoped = StatementFilter(
                account_ids=children,
                date_from=flt.date_from,
                date_to=flt.date_to,
                currency_ids=flt.currency_ids,
                group_ids=flt.group_ids,
                include_drafts=flt.include_drafts,
                include_opening=flt.include_opening,
            )
            result = account_statement(session, scoped)
            if result.rows:
                sections.append(LedgerSection(parent.id, parent.code, parent.name, result))
    title = "دفتر کل" if kol else "دفتر معین"
    return LedgerResult(title, _window_label(flt), sections)


def browse_accounts(session: Session, flt: StatementFilter, level: str = LEVEL_GROUP) -> TrialBalanceResult:
    result = trial_balance(session, flt, level=level if level != LEVEL_GROUP else LEVEL_GROUP, columns=6)
    result.title = f"مرور حسابها — {BROWSE_LEVEL_FA.get(level, level)}"
    return result



@dataclass
class IncomeStatementLine:
    code: str
    name: str
    amounts: dict[int, Decimal] = field(default_factory=dict)
    is_total: bool = False

    def amount(self, currency_id: int) -> Decimal:
        return self.amounts.get(currency_id, ZERO)


@dataclass
class IncomeStatementResult:
    title: str
    subtitle: str
    currencies: list[CurrencyColumn]
    income: list[IncomeStatementLine]
    expense: list[IncomeStatementLine]
    income_total: dict[int, Decimal]
    expense_total: dict[int, Decimal]
    net: dict[int, Decimal]

    @property
    def is_empty(self) -> bool:
        return not self.income and not self.expense


def income_statement(session: Session, flt: StatementFilter, level: str = LEVEL_MOIN) -> IncomeStatementResult:
    """صورت سود و زیان: درآمد منهای هزینه، هر ارز در ستون خودش.

    Only income and expense accounts take part, and only movement inside the
    period -- a profit figure carries no opening balance by definition.
    """
    scoped = replace(flt, include_opening=False)
    turnover = _aggregate(session, scoped, _group_column(level), flt.date_from, flt.date_to)
    currencies = _currencies_from_maps(session, [turnover], flt)
    labels = _names_for_level(session, level)
    kinds = {a.id: a.account_type for a in session.execute(select(Account)).scalars()}

    buckets: dict[AccountType, dict[int, IncomeStatementLine]] = {AccountType.INCOME: {}, AccountType.EXPENSE: {}}
    totals: dict[AccountType, dict[int, Decimal]] = {AccountType.INCOME: {}, AccountType.EXPENSE: {}}
    for (key, currency_id), (debit, credit) in sorted(turnover.items()):
        kind = kinds.get(key)
        if kind not in buckets:
            continue
        # Income lives on the credit side, expense on the debit side; each is
        # shown as a positive figure so the statement reads like a statement.
        value = (credit - debit) if kind == AccountType.INCOME else (debit - credit)
        code, name = labels.get(key, ("", ""))
        line = buckets[kind].setdefault(key, IncomeStatementLine(code, name))
        line.amounts[currency_id] = line.amounts.get(currency_id, ZERO) + value
        totals[kind][currency_id] = totals[kind].get(currency_id, ZERO) + value

    income = sorted(buckets[AccountType.INCOME].values(), key=lambda r: r.code)
    expense = sorted(buckets[AccountType.EXPENSE].values(), key=lambda r: r.code)
    net = {
        c.id: totals[AccountType.INCOME].get(c.id, ZERO) - totals[AccountType.EXPENSE].get(c.id, ZERO)
        for c in currencies
    }
    subtitle = ""
    if flt.date_from or flt.date_to:
        subtitle = f"{flt.date_from or ''} تا {flt.date_to or ''}"
    return IncomeStatementResult(
        "صورت سود و زیان",
        subtitle,
        currencies,
        income,
        expense,
        totals[AccountType.INCOME],
        totals[AccountType.EXPENSE],
        net,
    )

__all__ = (
    "LEVEL_KOL",
    "LEVEL_MOIN",
    "LEVEL_TAFSILI",
    "LEVEL_TAFSILI2",
    "TAFSILI_LEVELS",
    "LEVEL_GROUP",
    "LEVEL_FA",
    "BROWSE_LEVELS",
    "BROWSE_LEVEL_FA",
    "COLUMN_SETS",
    "TrialBalanceRow",
    "TrialBalanceResult",
    "trial_balance",
    "JournalRow",
    "JournalResult",
    "journal",
    "LedgerSection",
    "LedgerResult",
    "general_ledger",
    "browse_accounts",
    "IncomeStatementLine",
    "IncomeStatementResult",
    "income_statement",
)
