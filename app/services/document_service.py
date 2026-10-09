"""Every rule that decides whether a document may exist lives here.

The UI calls this module; it never touches the session directly for writes.
"""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Account,
    AccountTafsiliRule,
    Currency,
    Document,
    DocumentLine,
    FiscalYear,
    NumberSequence,
    Tafsili,
)
from app.db.types import utcnow
from app.domain import money
from app.domain.enums import AuditAction, DocumentStatus, DocumentType
from app.domain.errors import ConcurrencyError, ImmutableDocumentError, UnbalancedDocumentError, ValidationError
from app.domain.permissions import Perm
from app.repositories import sequences
from app.services import audit, auth_service


@dataclass
class LineInput:
    account_id: int | None = None
    currency_id: int | None = None
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    tafsili1_id: int | None = None
    tafsili2_id: int | None = None
    description: str = ""


@dataclass
class DocumentInput:
    fiscal_year_id: int | None = None
    date_g: _dt.date | None = None
    date_j: str = ""
    doc_type: DocumentType = DocumentType.GENERAL
    description: str = ""
    lines: list[LineInput] = field(default_factory=list)


@dataclass
class CurrencyBalance:
    code: str
    decimals: int
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)

    @property
    def difference(self) -> Decimal:
        return self.debit - self.credit

    @property
    def balanced(self) -> bool:
        return self.difference == 0


def balance_by_currency(
    lines: list[LineInput] | list[DocumentLine],
    currencies: dict[int, Currency],
) -> dict[int, CurrencyBalance]:
    """Debit and credit totals per currency. Currencies are never mixed."""
    totals: dict[int, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for line in lines:
        cid = line.currency_id
        if not cid:
            continue
        totals[cid][0] += money.parse(line.debit)
        totals[cid][1] += money.parse(line.credit)
    result: dict[int, CurrencyBalance] = {}
    for cid, (debit, credit) in totals.items():
        currency = currencies.get(cid)
        result[cid] = CurrencyBalance(
            code=currency.code if currency else str(cid),
            decimals=currency.decimals if currency else 0,
            debit=debit,
            credit=credit,
        )
    return result


def _load_currencies(session: Session) -> dict[int, Currency]:
    return {c.id: c for c in session.execute(select(Currency)).scalars()}


def _load_accounts(session: Session, ids: set[int]) -> dict[int, Account]:
    if not ids:
        return {}
    rows = session.execute(
        select(Account)
        .options(selectinload(Account.allowed_currencies), selectinload(Account.tafsili_rules))
        .where(Account.id.in_(ids))
    ).scalars()
    return {a.id: a for a in rows}


def _load_tafsilis(session: Session, ids: set[int]) -> dict[int, Tafsili]:
    if not ids:
        return {}
    rows = session.execute(
        select(Tafsili).options(selectinload(Tafsili.memberships)).where(Tafsili.id.in_(ids))
    ).scalars()
    return {t.id: t for t in rows}


def _check_slot(
    account: Account,
    rules: list[AccountTafsiliRule],
    slot: int,
    tafsili: Tafsili | None,
    row: int,
) -> None:
    required = account.tafsili1_required if slot == 1 else account.tafsili2_required
    slot_rules = [r for r in rules if r.slot == slot]
    if required and tafsili is None:
        raise ValidationError(f"ردیف {row}: سرفصل «{account.name}» به تفصیلی {slot} نیاز دارد.")
    if tafsili is None:
        return
    if not slot_rules:
        raise ValidationError(f"ردیف {row}: برای سرفصل «{account.name}» تفصیلی {slot} تعریف نشده است.")
    specific = {r.tafsili_id for r in slot_rules if r.tafsili_id}
    groups = {r.tafsili_group_id for r in slot_rules if not r.tafsili_id}
    allowed = tafsili.id in specific or bool(tafsili.group_ids & groups)
    if not allowed:
        raise ValidationError(
            f"ردیف {row}: تفصیلی «{tafsili.name}» به سرفصل «{account.name}» وصل نیست."
        )
    if not tafsili.is_active:
        raise ValidationError(f"ردیف {row}: تفصیلی «{tafsili.name}» غیرفعال است.")


def validate(session: Session, data: DocumentInput) -> None:
    filled = [ln for ln in data.lines if ln.account_id or money.parse(ln.debit) or money.parse(ln.credit)]
    if len(filled) < 2:
        raise ValidationError("سند حداقل باید دو ردیف داشته باشد.")
    year = session.get(FiscalYear, data.fiscal_year_id) if data.fiscal_year_id else None
    if year is None:
        raise ValidationError("سال مالی انتخاب نشده است.")
    if year.is_closed:
        raise ValidationError(f"سال مالی {year.title} بسته شده است.")
    if data.date_g is None or not (year.start_date_g <= data.date_g <= year.end_date_g):
        raise ValidationError(
            f"تاریخ سند خارج از سال مالی {year.title} ({year.start_date_j} تا {year.end_date_j}) است."
        )
    currencies = _load_currencies(session)
    accounts = _load_accounts(session, {ln.account_id for ln in filled if ln.account_id})
    tafsilis = _load_tafsilis(
        session,
        {ln.tafsili1_id for ln in filled if ln.tafsili1_id}
        | {ln.tafsili2_id for ln in filled if ln.tafsili2_id},
    )
    for index, line in enumerate(filled, start=1):
        if not line.account_id:
            raise ValidationError(f"ردیف {index}: سرفصل انتخاب نشده است.")
        account = accounts.get(line.account_id)
        if account is None:
            raise ValidationError(f"ردیف {index}: سرفصل انتخاب نشده است.")
        if not account.is_postable:
            raise ValidationError(f"ردیف {index}: «{account.display}» سرفصل کل است و سند به آن ثبت نمی‌شود.")
        if not account.is_active:
            raise ValidationError(f"ردیف {index}: سرفصل «{account.display}» غیرفعال است.")
        if not line.currency_id:
            raise ValidationError(f"ردیف {index}: ارز انتخاب نشده است.")
        currency = currencies.get(line.currency_id)
        if currency is None or not currency.is_active:
            raise ValidationError(f"ردیف {index}: ارز {currency.code if currency else ''} غیرفعال است.")
        allowed = {row.currency_id for row in account.allowed_currencies}
        if allowed and line.currency_id not in allowed:
            names = "، ".join(sorted(currencies[cid].code for cid in allowed if cid in currencies))
            raise ValidationError(f"ردیف {index}: سرفصل «{account.name}» فقط با ارز {names} قابل استفاده است.")
        debit = money.parse(line.debit)
        credit = money.parse(line.credit)
        if debit < 0 or credit < 0:
            raise ValidationError(f"ردیف {index}: مبلغ منفی مجاز نیست.")
        if debit and credit:
            raise ValidationError(f"ردیف {index}: هر ردیف یا بدهکار است یا بستانکار، نه هر دو.")
        if debit + credit == 0:
            raise ValidationError(f"ردیف {index}: مبلغ وارد نشده است.")
        if not money.fits_scale(debit, currency.decimals) or not money.fits_scale(credit, currency.decimals):
            raise ValidationError(f"ردیف {index}: {currency.code} حداکثر {currency.decimals} رقم اعشار دارد.")
        _check_slot(account, account.tafsili_rules, 1, tafsilis.get(line.tafsili1_id) if line.tafsili1_id else None, index)
        _check_slot(account, account.tafsili_rules, 2, tafsilis.get(line.tafsili2_id) if line.tafsili2_id else None, index)
    balances = balance_by_currency(filled, currencies)
    unbalanced = {
        b.code: money.format_amount(abs(b.difference), b.decimals)
        for b in balances.values()
        if not b.balanced
    }
    if unbalanced:
        raise UnbalancedDocumentError(unbalanced)


def _apply_lines(document: Document, data: DocumentInput) -> None:
    document.lines.clear()
    filled = [ln for ln in data.lines if ln.account_id and (money.parse(ln.debit) or money.parse(ln.credit))]
    for index, line in enumerate(filled, start=1):
        document.lines.append(
            DocumentLine(
                line_no=index,
                account_id=line.account_id,
                tafsili1_id=line.tafsili1_id,
                tafsili2_id=line.tafsili2_id,
                currency_id=line.currency_id,
                debit=money.parse(line.debit),
                credit=money.parse(line.credit),
                description=(line.description or "").strip() or None,
            )
        )


def _scope_for(session: Session, document: Document) -> str:
    year = session.get(FiscalYear, document.fiscal_year_id)
    return sequences.document_scope(year.title)


def _ensure_number(session: Session, document: Document) -> None:
    """A document gets its number the moment it is first saved, draft or not."""
    if document.number is None:
        document.number = sequences.next_value(session, _scope_for(session, document))


def save_draft(
    session: Session,
    data: DocumentInput,
    document: Document | None = None,
    user_id: int | None = None,
    expected_row_version: int | None = None,
) -> Document:
    """Create or update a draft. Posted documents are refused outright.

    Header, detail lines and the document number share one SQLAlchemy session.
    The caller commits; on any error the caller rolls back, including the number.
    """
    auth_service.require(session, user_id, Perm.DOC_DRAFT)
    if document is not None and expected_row_version is not None and document.row_version != expected_row_version:
        raise ConcurrencyError("سند")
    if document is not None and document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    creating = document is None
    if creating:
        document = Document(
            status=DocumentStatus.DRAFT,
            created_by_user_id=auth_service.valid_user_id(session, user_id),
        )
        session.add(document)
    document.fiscal_year_id = data.fiscal_year_id
    document.date_g = data.date_g
    document.date_j = data.date_j
    document.doc_type = data.doc_type
    document.description = (data.description or "").strip()
    _apply_lines(document, data)
    _ensure_number(session, document)
    session.flush()
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.CREATE if creating else AuditAction.UPDATE,
        entity_id=document.id,
        user_id=user_id,
        after={"number": document.number, "lines": len(document.lines)},
    )
    return document


def post(session: Session, document: Document, user_id: int | None = None) -> Document:
    """Assign the sequential number and make the document permanent."""
    auth_service.require(session, user_id, Perm.DOC_POST)
    locked = session.execute(select(Document).where(Document.id == document.id).with_for_update()).scalar_one_or_none()
    if locked is not None:
        document = locked
    if document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    data = DocumentInput(
        fiscal_year_id=document.fiscal_year_id,
        date_g=document.date_g,
        date_j=document.date_j,
        doc_type=document.doc_type,
        description=document.description,
        lines=[
            LineInput(
                account_id=ln.account_id,
                currency_id=ln.currency_id,
                debit=ln.debit,
                credit=ln.credit,
                tafsili1_id=ln.tafsili1_id,
                tafsili2_id=ln.tafsili2_id,
                description=ln.description or "",
            )
            for ln in document.lines
        ],
    )
    validate(session, data)
    _ensure_number(session, document)
    document.status = DocumentStatus.POSTED
    document.posted_by_user_id = auth_service.valid_user_id(session, user_id)
    document.posted_at = utcnow()
    session.flush()
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.POST,
        entity_id=document.id,
        user_id=user_id,
        after={"number": document.number},
    )
    return document


def save_and_post(
    session: Session,
    data: DocumentInput,
    document: Document | None = None,
    user_id: int | None = None,
    expected_row_version: int | None = None,
) -> Document:
    validate(session, data)
    document = save_draft(session, data, document, user_id, expected_row_version=expected_row_version)
    return post(session, document, user_id)


def delete_draft(session: Session, document: Document, user_id: int | None = None) -> None:
    auth_service.require(session, user_id, Perm.DOC_DRAFT)
    if document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    number = document.number
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.DELETE_DRAFT,
        entity_id=document.id,
        user_id=user_id,
        before={"number": number, "date_j": document.date_j, "lines": len(document.lines)},
        note="حذف پیش‌نویس ثبت‌نشده",
    )
    scope = _scope_for(session, document)
    session.delete(document)
    session.flush()
    if number is not None:
        sequences.release_value(session, scope, number)


def reverse(
    session: Session,
    original: Document,
    date_g: _dt.date,
    date_j: str,
    description: str | None = None,
    user_id: int | None = None,
) -> Document:
    """Post a mirrored document. The original is never touched beyond a flag."""
    auth_service.require(session, user_id, Perm.DOC_REVERSE)
    if not original.is_posted:
        raise ValidationError("فقط سند قطعی‌شده قابل برگشت است.")
    if original.is_reversed:
        raise ValidationError(f"سند شماره {original.number} قبلاً برگشت خورده است.")
    data = DocumentInput(
        fiscal_year_id=original.fiscal_year_id,
        date_g=date_g,
        date_j=date_j,
        doc_type=DocumentType.REVERSAL,
        description=description or f"برگشت سند شماره {original.number}",
        lines=[
            LineInput(
                account_id=ln.account_id,
                currency_id=ln.currency_id,
                debit=ln.credit,
                credit=ln.debit,
                tafsili1_id=ln.tafsili1_id,
                tafsili2_id=ln.tafsili2_id,
                description=ln.description or "",
            )
            for ln in original.lines
        ],
    )
    reversal = save_draft(session, data, user_id=user_id)
    reversal.reverses_document_id = original.id
    post(session, reversal, user_id)
    original.is_reversed = True
    session.flush()
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.REVERSE,
        entity_id=original.id,
        user_id=user_id,
        after={"reversal_number": reversal.number},
    )
    return reversal


def create_correction_draft(
    session: Session,
    original: Document,
    date_g: _dt.date,
    date_j: str,
    user_id: int | None = None,
) -> tuple[Document, Document]:
    """Reverse the original and return an editable copy for the corrected figures."""
    auth_service.require(session, user_id, Perm.DOC_REVERSE)
    reversal = reverse(
        session,
        original,
        date_g,
        date_j,
        description=f"برگشت سند شماره {original.number} جهت اصلاح",
        user_id=user_id,
    )
    data = DocumentInput(
        fiscal_year_id=original.fiscal_year_id,
        date_g=date_g,
        date_j=date_j,
        doc_type=DocumentType.CORRECTION,
        description=f"اصلاح سند شماره {original.number}",
        lines=[
            LineInput(
                account_id=ln.account_id,
                currency_id=ln.currency_id,
                debit=ln.debit,
                credit=ln.credit,
                tafsili1_id=ln.tafsili1_id,
                tafsili2_id=ln.tafsili2_id,
                description=ln.description or "",
            )
            for ln in original.lines
        ],
    )
    draft = save_draft(session, data, user_id=user_id)
    draft.corrects_document_id = original.id
    session.flush()
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.CORRECT,
        entity_id=original.id,
        user_id=user_id,
        after={"correction_id": draft.id},
    )
    return reversal, draft


def load(session: Session, document_id: int) -> Document | None:
    return session.execute(
        select(Document)
        .options(
            selectinload(Document.lines).selectinload(DocumentLine.account),
            selectinload(Document.lines).selectinload(DocumentLine.currency),
            selectinload(Document.lines).selectinload(DocumentLine.tafsili1),
            selectinload(Document.lines).selectinload(DocumentLine.tafsili2),
            selectinload(Document.attachments),
        )
        .where(Document.id == document_id)
    ).scalar_one_or_none()


def _year_or_error(session: Session, document: Document) -> FiscalYear:
    year = session.get(FiscalYear, document.fiscal_year_id)
    if year is None:
        raise ValidationError("سال مالی سند پیدا نشد.")
    if year.is_closed:
        raise ValidationError(f"سال مالی {year.title} بسته شده است.")
    return year


def unpost(session: Session, document: Document, user_id: int | None = None) -> Document:
    auth_service.require(session, user_id, Perm.DOC_UNPOST)
    if not document.is_posted:
        raise ValidationError("این سند قطعی نیست.")
    year = _year_or_error(session, document)
    n = document.number or 0
    if document.is_reversed:
        raise ValidationError(f"سند شماره {n} برگشت خورده است؛ اول سند برگشتی آن را حذف کنید.")
    referring = session.execute(
        select(Document.id).where(
            (Document.reverses_document_id == document.id)
            | (Document.corrects_document_id == document.id)
        )
    ).first()
    if referring:
        raise ValidationError(f"سند شماره {n} توسط سند دیگری ارجاع شده است و قابل بازگردانی نیست.")
    before = {"number": document.number, "posted_at": document.posted_at}
    if document.reverses_document_id:
        original = session.get(Document, document.reverses_document_id)
        if original is not None:
            original.is_reversed = False
    document.status = DocumentStatus.DRAFT
    document.posted_by_user_id = None
    document.posted_at = None
    session.flush()
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.UNPOST,
        entity_id=document.id,
        user_id=user_id,
        before=before,
    )
    return document


def delete_posted(session: Session, document: Document, user_id: int | None = None) -> None:
    auth_service.require(session, user_id, Perm.DOC_DELETE_POSTED)
    unpost(session, document, user_id)
    before = {
        "number": document.number,
        "date_j": document.date_j,
        "lines": len(document.lines),
    }
    audit.record(
        session,
        entity_type="Document",
        action=AuditAction.DELETE_POSTED,
        entity_id=document.id,
        user_id=user_id,
        before=before,
    )
    delete_draft(session, document, user_id)


def purge_fiscal_year(session: Session, fiscal_year: FiscalYear, user_id: int | None = None) -> int:
    auth_service.require(session, user_id, Perm.DOC_PURGE)
    if fiscal_year.is_closed:
        raise ValidationError(f"سال مالی {fiscal_year.title} بسته شده است.")
    count = session.execute(
        select(Document.id).where(Document.fiscal_year_id == fiscal_year.id)
    ).all()
    n = len(count)
    session.execute(delete(Document).where(Document.fiscal_year_id == fiscal_year.id))
    scope = sequences.document_scope(fiscal_year.title)
    sequences.ensure_scope(session, scope)
    session.execute(
        update(NumberSequence)
        .where(NumberSequence.scope == scope)
        .values(last_value=0),
        execution_options={"synchronize_session": False},
    )
    audit.record(
        session,
        entity_type="FiscalYear",
        action=AuditAction.PURGE,
        entity_id=fiscal_year.id,
        user_id=user_id,
        before={"documents": n},
    )
    return n


def next_number_preview(session: Session, fiscal_year: FiscalYear) -> int:
    return sequences.peek_value(session, sequences.document_scope(fiscal_year.title)) + 1


__all__ = (
    "LineInput",
    "DocumentInput",
    "CurrencyBalance",
    "balance_by_currency",
    "validate",
    "save_draft",
    "post",
    "save_and_post",
    "delete_draft",
    "unpost",
    "delete_posted",
    "purge_fiscal_year",
    "reverse",
    "create_correction_draft",
    "load",
    "next_number_preview",
)
