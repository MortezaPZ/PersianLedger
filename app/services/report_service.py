"""Account statement (کاردکس) and party statement."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.db.models import Account, Currency, Document, DocumentLine, Tafsili, TafsiliGroupMember
from app.domain.enums import DOCUMENT_TYPE_FA, DocumentStatus, DocumentType
from app.domain import money

ZERO = Decimal(0)


@dataclass
class StatementFilter:
    account_id: int | None = None
    account_ids: list[int] | None = None
    tafsili_id: int | None = None
    tafsili_any_id: int | None = None
    tafsili_ids: list[int] | None = None
    date_from: _dt.date | None = None
    date_to: _dt.date | None = None
    currency_ids: list[int] | None = None
    group_ids: list[int] | None = None
    include_drafts: bool = True
    include_opening: bool = True
    exclude_doc_types: list[DocumentType] | None = None


@dataclass
class CurrencyColumn:
    id: int
    code: str
    name: str
    decimals: int


@dataclass
class StatementLine:
    line_id: int | None
    date_g: _dt.date | None
    date_j: str
    document_id: int | None
    number: str
    doc_type: str
    description: str
    account_code: str
    account_name: str
    tafsili: str
    is_draft: bool
    is_opening: bool
    amounts: dict[int, tuple[Decimal, Decimal, Decimal]]  # debit, credit, running


@dataclass
class StatementResult:
    title: str
    subtitle: str
    currencies: list[CurrencyColumn]
    rows: list[StatementLine]
    closing: dict[int, Decimal]

    @property
    def is_empty(self) -> bool:
        return not self.rows


@dataclass
class MatrixCurrencyTotals:
    debit_turnover: Decimal = ZERO
    credit_turnover: Decimal = ZERO
    debit_balance: Decimal = ZERO
    credit_balance: Decimal = ZERO


@dataclass
class MoeinMatrixRow:
    account_id: int
    account_code: str
    account_name: str
    amounts: dict[int, MatrixCurrencyTotals] = field(default_factory=dict)


@dataclass
class MoeinMatrixResult:
    title: str
    subtitle: str
    currencies: list[CurrencyColumn]
    rows: list[MoeinMatrixRow]

    @property
    def is_empty(self) -> bool:
        return not self.rows


def _apply_scope(stmt: Select, flt: StatementFilter) -> Select:
    stmt = stmt.join(Document, DocumentLine.document_id == Document.id)
    if flt.include_drafts:
        stmt = stmt.where(Document.status.in_((DocumentStatus.DRAFT, DocumentStatus.POSTED)))
    else:
        stmt = stmt.where(Document.status == DocumentStatus.POSTED)
    if flt.account_id:
        stmt = stmt.where(DocumentLine.account_id == flt.account_id)
    if flt.account_ids:
        stmt = stmt.where(DocumentLine.account_id.in_(flt.account_ids))
    if flt.tafsili_id:
        stmt = stmt.where(
            or_(DocumentLine.tafsili1_id == flt.tafsili_id, DocumentLine.tafsili2_id == flt.tafsili_id)
        )
    if flt.tafsili_any_id:
        stmt = stmt.where(
            or_(DocumentLine.tafsili1_id == flt.tafsili_any_id, DocumentLine.tafsili2_id == flt.tafsili_any_id)
        )
    if flt.tafsili_ids:
        stmt = stmt.where(
            or_(DocumentLine.tafsili1_id.in_(flt.tafsili_ids), DocumentLine.tafsili2_id.in_(flt.tafsili_ids))
        )
    if flt.currency_ids:
        stmt = stmt.where(DocumentLine.currency_id.in_(flt.currency_ids))
    if flt.group_ids:
        members = select(TafsiliGroupMember.tafsili_id).where(TafsiliGroupMember.group_id.in_(flt.group_ids))
        chosen = [i for i in (flt.tafsili_any_id, flt.tafsili_id) if i] or list(flt.tafsili_ids or [])
        if chosen:
            # Reporting a chosen tafsili "within group G" asks whether *that*
            # tafsili is in G.  Matching any tafsili on the line let the second
            # slot satisfy the filter, so a project line also tagged with a
            # person came back under the person's group and the filter looked
            # like it did nothing.
            stmt = stmt.where(
                select(TafsiliGroupMember.tafsili_id)
                .where(
                    TafsiliGroupMember.tafsili_id.in_(chosen),
                    TafsiliGroupMember.group_id.in_(flt.group_ids),
                )
                .exists()
            )
        else:
            stmt = stmt.where(
                or_(DocumentLine.tafsili1_id.in_(members), DocumentLine.tafsili2_id.in_(members))
            )
    if flt.exclude_doc_types:
        stmt = stmt.where(Document.doc_type.notin_(flt.exclude_doc_types))
    return stmt


def _currency_columns(session: Session, ids: set[int]) -> list[CurrencyColumn]:
    if not ids:
        rows = session.execute(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.sort_order)).scalars()
    else:
        rows = session.execute(select(Currency).where(Currency.id.in_(ids)).order_by(Currency.sort_order)).scalars()
    return [CurrencyColumn(c.id, c.code, c.name, c.decimals) for c in rows]


def _running_before(session: Session, flt: StatementFilter) -> dict[int, Decimal]:
    if not flt.date_from:
        return {}
    stmt = select(
        DocumentLine.currency_id,
        DocumentLine.debit,
        DocumentLine.credit,
    )
    stmt = _apply_scope(stmt, flt).where(Document.date_g < flt.date_from)
    opening: dict[int, Decimal] = {}
    for currency_id, debit, credit in session.execute(stmt):
        opening[currency_id] = opening.get(currency_id, ZERO) + money.parse(debit) - money.parse(credit)
    return opening


def account_statement(session: Session, flt: StatementFilter) -> StatementResult:
    account = session.get(Account, flt.account_id) if flt.account_id else None
    title = f"صورتحساب سرفصل — {account.display}" if account else "صورتحساب سرفصل"
    stmt = select(DocumentLine, Document, Account).join(Account, DocumentLine.account_id == Account.id)
    stmt = _apply_scope(stmt, flt)
    if flt.date_from:
        stmt = stmt.where(Document.date_g >= flt.date_from)
    if flt.date_to:
        stmt = stmt.where(Document.date_g <= flt.date_to)
    stmt = stmt.order_by(Document.date_g, Document.number, DocumentLine.line_no)
    rows_raw = list(session.execute(stmt))
    used = {line.currency_id for line, _doc, _acc in rows_raw}
    opening = _running_before(session, flt) if flt.include_opening else {}
    used.update(opening)
    columns = _currency_columns(session, used if (flt.currency_ids or used) else set())
    running = dict(opening)
    rows: list[StatementLine] = []
    if flt.include_opening and opening:
        amounts = {
            col.id: (ZERO, ZERO, running.get(col.id, ZERO))
            for col in columns
        }
        rows.append(
            StatementLine(
                None, None, "", None, "", "", "مانده از قبل", "", "", "", False, True, amounts
            )
        )
    tafsili_cache: dict[int, Tafsili] = {}

    def tafsili_text(line: DocumentLine) -> str:
        parts = []
        for tid in (line.tafsili1_id, line.tafsili2_id):
            if not tid:
                continue
            if tid not in tafsili_cache:
                tafsili_cache[tid] = session.get(Tafsili, tid)
            item = tafsili_cache.get(tid)
            if item:
                parts.append(item.display)
        return " / ".join(parts)

    for line, doc, acc in rows_raw:
        running[line.currency_id] = running.get(line.currency_id, ZERO) + money.parse(line.debit) - money.parse(line.credit)
        amounts = {}
        for col in columns:
            if col.id == line.currency_id:
                amounts[col.id] = (money.parse(line.debit), money.parse(line.credit), running[col.id])
            else:
                amounts[col.id] = (ZERO, ZERO, running.get(col.id, ZERO))
        desc = (line.description or "").strip() or (doc.description or "")
        rows.append(
            StatementLine(
                line.id,
                doc.date_g,
                doc.date_j,
                doc.id,
                doc.number_display,
                DOCUMENT_TYPE_FA.get(doc.doc_type, doc.doc_type.value),
                desc,
                acc.code,
                acc.name,
                tafsili_text(line),
                doc.status == DocumentStatus.DRAFT,
                False,
                amounts,
            )
        )
    closing = {col.id: running.get(col.id, ZERO) for col in columns}
    subtitle = ""
    if flt.date_from or flt.date_to:
        subtitle = f"{flt.date_from or ''} تا {flt.date_to or ''}"
    return StatementResult(title, subtitle, columns, rows, closing)


def party_statement(session: Session, flt: StatementFilter) -> StatementResult:
    ids = flt.tafsili_ids or ([flt.tafsili_any_id or flt.tafsili_id] if (flt.tafsili_any_id or flt.tafsili_id) else [])
    if len(ids) == 1:
        item = session.get(Tafsili, ids[0])
        title = f"صورت وضعیت اشخاص — {item.display}" if item else "صورت وضعیت اشخاص"
    elif ids:
        title = f"صورت وضعیت اشخاص — {len(ids)} مورد"
    else:
        title = "صورت وضعیت اشخاص"
    cloned = StatementFilter(
        tafsili_any_id=ids[0] if len(ids) == 1 else None,
        tafsili_ids=ids if len(ids) > 1 else None,
        date_from=flt.date_from,
        date_to=flt.date_to,
        currency_ids=flt.currency_ids,
        group_ids=flt.group_ids,
        include_drafts=flt.include_drafts,
        include_opening=flt.include_opening,
        exclude_doc_types=flt.exclude_doc_types,
    )
    result = account_statement(session, cloned)
    result.title = title
    return result


def tafsili_descendant_ids(session: Session, tafsili_id: int) -> list[int]:
    """Return a node and every descendant, retaining balances posted before it had children."""
    tree = select(Tafsili.id.label("id")).where(Tafsili.id == tafsili_id).cte(
        "tafsili_descendants", recursive=True
    )
    tree = tree.union_all(select(Tafsili.id).join(tree, Tafsili.parent_id == tree.c.id))
    return list(session.execute(select(tree.c.id)).scalars())


def tafsili_moein_matrix(
    db: Session,
    tafsili_id: int,
    from_date: _dt.date | None,
    to_date: _dt.date | None,
    currency_ids: list[int] | None,
) -> MoeinMatrixResult:
    """Aggregate posted turnover and closing balances by معین and currency.

    A selected parent tafsili includes every descendant. A selected leaf
    includes only that node. Legacy postings on a former leaf remain in the
    parent's roll-up after children are added. Amounts stay in separate currencies.
    """
    root = db.get(Tafsili, tafsili_id)
    if root is None:
        raise ValueError("تفصیلی انتخاب‌شده یافت نشد.")

    descendants = tafsili_descendant_ids(db, tafsili_id)
    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            DocumentLine.currency_id,
            Document.date_g,
            DocumentLine.debit,
            DocumentLine.credit,
        )
        .join(Document, DocumentLine.document_id == Document.id)
        .join(Account, DocumentLine.account_id == Account.id)
        .where(
            Document.status == DocumentStatus.POSTED,
            Account.level == 2,
            Account.is_postable.is_(True),
            or_(DocumentLine.tafsili1_id.in_(descendants), DocumentLine.tafsili2_id.in_(descendants)),
        )
    )
    if to_date:
        stmt = stmt.where(Document.date_g <= to_date)
    if currency_ids:
        stmt = stmt.where(DocumentLine.currency_id.in_(currency_ids))
    stmt = stmt.order_by(Account.code, DocumentLine.currency_id, Document.date_g)

    buckets: dict[tuple[int, int], list[Decimal]] = {}
    accounts: dict[int, tuple[str, str]] = {}
    used_currencies: set[int] = set()
    for account_id, code, name, currency_id, date_g, debit_raw, credit_raw in db.execute(stmt):
        debit, credit = money.parse(debit_raw), money.parse(credit_raw)
        bucket = buckets.setdefault((account_id, currency_id), [ZERO, ZERO, ZERO])
        if from_date is None or date_g >= from_date:
            bucket[0] += debit
            bucket[1] += credit
        bucket[2] += debit - credit
        accounts[account_id] = (code, name)
        used_currencies.add(currency_id)

    rows_by_account: dict[int, MoeinMatrixRow] = {}
    for (account_id, currency_id), (debit, credit, balance) in buckets.items():
        row = rows_by_account.setdefault(
            account_id,
            MoeinMatrixRow(account_id, *accounts[account_id]),
        )
        row.amounts[currency_id] = MatrixCurrencyTotals(
            debit_turnover=debit,
            credit_turnover=credit,
            debit_balance=max(balance, ZERO),
            credit_balance=max(-balance, ZERO),
        )

    columns = _currency_columns(db, set(currency_ids) if currency_ids else used_currencies)
    dates = " تا ".join(value.isoformat() if value else "" for value in (from_date, to_date))
    return MoeinMatrixResult(
        "گردش حساب‌های معین به تفکیک تفصیلی",
        f"{root.display} | {dates}".strip(" |"),
        columns,
        list(rows_by_account.values()),
    )
