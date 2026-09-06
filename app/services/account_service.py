"""Chart of accounts. An account that carries activity can only be deactivated."""
from __future__ import annotations

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Account, AccountGroup, AccountCurrency, AccountTafsiliRule, DocumentLine
from app.domain.enums import AccountNature, AccountType, AuditAction
from app.domain.errors import InUseError, ValidationError
from app.services import audit, auth_service
from app.domain.permissions import Perm


def account_groups(session: Session, only_active: bool = False) -> list[AccountGroup]:
    stmt = select(AccountGroup)
    if only_active:
        stmt = stmt.where(AccountGroup.is_active.is_(True))
    return list(session.execute(stmt.order_by(AccountGroup.sort_order, AccountGroup.code)).scalars())


def create_account_group(
    session: Session,
    *,
    code: str,
    name: str,
    account_type: AccountType,
    sort_order: int = 0,
    user_id: int | None = None,
) -> AccountGroup:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    code = (code or "").strip()
    if not code:
        raise ValidationError("کد گروه الزامی است.")
    if session.execute(select(AccountGroup.id).where(AccountGroup.code == code)).first():
        raise ValidationError(f"گروه با کد {code} قبلاً تعریف شده است.")
    row = AccountGroup(code=code, name=(name or "").strip() or code, account_type=account_type, sort_order=sort_order)
    session.add(row)
    session.flush()
    audit.record(session, entity_type="AccountGroup", action=AuditAction.CREATE, entity_id=row.id, user_id=user_id, after={"code": code, "name": name})
    return row


def group_has_accounts(session: Session, group_id: int) -> bool:
    return bool(session.execute(select(exists().where(Account.group_id == group_id))).scalar())


def all_accounts(session: Session, include_inactive: bool = False) -> list[Account]:
    stmt = select(Account).options(selectinload(Account.allowed_currencies), selectinload(Account.tafsili_rules))
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(session.execute(stmt.order_by(Account.code)).scalars())


def postable_accounts(session: Session, include_inactive: bool = False) -> list[Account]:
    stmt = select(Account).where(Account.is_postable.is_(True))
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return list(session.execute(stmt.order_by(Account.code)).scalars())


def has_activity(session: Session, account_id: int) -> bool:
    return bool(session.execute(select(exists().where(DocumentLine.account_id == account_id))).scalar())


def has_children(session: Session, account_id: int) -> bool:
    return bool(session.execute(select(exists().where(Account.parent_id == account_id))).scalar())


def line_count(session: Session, account_id: int) -> int:
    return int(
        session.execute(select(func.count(DocumentLine.id)).where(DocumentLine.account_id == account_id)).scalar_one()
    )


def _check_code(session: Session, code: str, account_id: int | None = None) -> str:
    code = (code or "").strip()
    if not code:
        raise ValidationError("کد سرفصل الزامی است.")
    if not code.isdigit():
        raise ValidationError("کد سرفصل فقط می‌تواند رقم باشد.")
    stmt = select(Account.id).where(Account.code == code)
    if account_id is not None:
        stmt = stmt.where(Account.id != account_id)
    if session.execute(stmt).first():
        raise ValidationError(f"کد {code} قبلاً استفاده شده است.")
    return code


def _sync_currencies(session: Session, account: Account, currency_ids: list[int] | None) -> None:
    account.allowed_currencies.clear()
    session.flush()
    if not currency_ids:
        return
    for cid in currency_ids:
        account.allowed_currencies.append(AccountCurrency(currency_id=cid))


def _sync_tafsili_rules(session: Session, account: Account, rules: list[tuple[int, int]] | None) -> None:
    account.tafsili_rules.clear()
    session.flush()
    if not rules:
        return
    for group_id, slot in rules:
        account.tafsili_rules.append(AccountTafsiliRule(tafsili_group_id=group_id, slot=slot))


def create(
    session: Session,
    *,
    code: str,
    name: str,
    parent_id: int | None = None,
    group_id: int | None = None,
    account_type: AccountType | None = None,
    nature: AccountNature = AccountNature.BOTH,
    tafsili1_required: bool = False,
    tafsili2_required: bool = False,
    currency_ids: list[int] | None = None,
    tafsili_rules: list[tuple[int, int]] | None = None,
    note: str | None = None,
    user_id: int | None = None,
) -> Account:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    code = _check_code(session, code)
    name = (name or "").strip()
    if not name:
        raise ValidationError("نام سرفصل الزامی است.")
    if parent_id:
        parent = session.get(Account, parent_id)
        if parent is None:
            raise ValidationError("سرفصل کل انتخاب‌شده یافت نشد.")
        if parent.level != 1:
            raise ValidationError("معین فقط زیر یک سرفصل کل تعریف می‌شود.")
        account = Account(
            code=code,
            name=name,
            parent_id=parent.id,
            group_id=parent.group_id,
            level=2,
            account_type=parent.account_type,
            nature=nature,
            is_postable=True,
            tafsili1_required=tafsili1_required,
            tafsili2_required=tafsili2_required,
            note=note,
        )
    else:
        if account_type is None:
            raise ValidationError("نوع سرفصل کل الزامی است.")
        account = Account(
            code=code,
            name=name,
            group_id=group_id,
            level=1,
            account_type=account_type,
            nature=nature,
            is_postable=False,
            note=note,
        )
    session.add(account)
    session.flush()
    _sync_currencies(session, account, currency_ids)
    _sync_tafsili_rules(session, account, tafsili_rules)
    audit.record(session, entity_type="Account", action=AuditAction.CREATE, entity_id=account.id, user_id=user_id, after={"code": code, "name": name})
    return account


def update(
    session: Session,
    account: Account,
    *,
    code: str | None = None,
    name: str | None = None,
    nature: AccountNature | None = None,
    group_id: int | None = None,
    tafsili1_required: bool | None = None,
    tafsili2_required: bool | None = None,
    currency_ids: list[int] | None = None,
    tafsili_rules: list[tuple[int, int]] | None = None,
    note: str | None = None,
    user_id: int | None = None,
) -> Account:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    if code is not None and code != account.code:
        if has_activity(session, account.id):
            raise InUseError("این سرفصل سند دارد؛ کد آن قابل تغییر نیست.")
        account.code = _check_code(session, code, account.id)
    if name is not None:
        name = name.strip()
        if not name:
            raise ValidationError("نام سرفصل الزامی است.")
        account.name = name
    if nature is not None:
        account.nature = nature
    if group_id is not None and account.level == 1:
        account.group_id = group_id
        for child in account.children:
            child.group_id = group_id
    if tafsili1_required is not None:
        account.tafsili1_required = tafsili1_required
    if tafsili2_required is not None:
        account.tafsili2_required = tafsili2_required
    if note is not None:
        account.note = note
    if currency_ids is not None:
        _sync_currencies(session, account, currency_ids)
    if tafsili_rules is not None:
        _sync_tafsili_rules(session, account, tafsili_rules)
    session.flush()
    audit.record(session, entity_type="Account", action=AuditAction.UPDATE, entity_id=account.id, user_id=user_id)
    return account


def set_active(session: Session, account: Account, active: bool, user_id: int | None = None) -> Account:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    account.is_active = active
    session.flush()
    audit.record(
        session,
        entity_type="Account",
        action=AuditAction.ACTIVATE if active else AuditAction.DEACTIVATE,
        entity_id=account.id,
        user_id=user_id,
        after={"code": account.code},
    )
    return account


def delete(session: Session, account: Account, user_id: int | None = None) -> None:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    if has_activity(session, account.id):
        raise InUseError("این سرفصل سند دارد و حذف نمی‌شود. آن را غیرفعال کنید.")
    if has_children(session, account.id):
        raise ValidationError("ابتدا معین‌های زیرمجموعه را حذف کنید.")
    audit.record(session, entity_type="Account", action=AuditAction.DELETE_DRAFT, entity_id=account.id, user_id=user_id, before={"code": account.code})
    session.delete(account)
    session.flush()
