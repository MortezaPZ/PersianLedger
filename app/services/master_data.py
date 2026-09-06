"""Currencies, fiscal years and the floating tafsili register."""
from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AppSetting, Currency, DocumentLine, FiscalYear, Tafsili, TafsiliGroup, TafsiliGroupMember
from app.domain import jalali
from app.domain.enums import AuditAction
from app.domain.errors import InUseError, ValidationError
from app.services import audit, auth_service
from app.domain.permissions import Perm


def get_setting(session: Session, key: str, default: str | None = None) -> str | None:
    row = session.get(AppSetting, key)
    return row.value if row else default


def set_setting(session: Session, key: str, value: str | None) -> None:
    row = session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()


def currencies(session: Session, only_active: bool = False) -> list[Currency]:
    stmt = select(Currency)
    if only_active:
        stmt = stmt.where(Currency.is_active.is_(True))
    return list(session.execute(stmt.order_by(Currency.sort_order, Currency.code)).scalars())


def currency_in_use(session: Session, currency_id: int) -> bool:
    return bool(
        session.execute(
            select(exists().where(DocumentLine.currency_id == currency_id))
        ).scalar()
    )


def create_currency(
    session: Session,
    *,
    code: str,
    name: str,
    decimals: int,
    symbol: str = "",
    sort_order: int = 0,
    user_id: int | None = None,
) -> Currency:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    code = (code or "").strip().upper()
    if not code:
        raise ValidationError("کد ارز الزامی است.")
    if session.execute(select(Currency.id).where(Currency.code == code)).first():
        raise ValidationError(f"ارز {code} قبلاً تعریف شده است.")
    if decimals < 0 or decimals > 4:
        raise ValidationError("تعداد اعشار باید بین ۰ تا ۴ باشد.")
    row = Currency(
        code=code,
        name=(name or "").strip() or code,
        symbol=(symbol or "").strip() or code,
        decimals=decimals,
        sort_order=sort_order,
    )
    session.add(row)
    session.flush()
    audit.record(session, entity_type="Currency", action=AuditAction.CREATE, entity_id=row.id, user_id=user_id, after={"code": row.code})
    return row


def update_currency(
    session: Session,
    currency: Currency,
    *,
    name: str | None = None,
    symbol: str | None = None,
    decimals: int | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
    user_id: int | None = None,
) -> Currency:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    if decimals is not None and decimals != currency.decimals:
        if currency.is_locked or currency_in_use(session, currency.id):
            raise InUseError(f"ارز {currency.code} در اسناد استفاده شده است؛ تعداد اعشار آن قابل تغییر نیست.")
        if decimals < 0 or decimals > 4:
            raise ValidationError("تعداد اعشار باید بین ۰ تا ۴ باشد.")
        currency.decimals = decimals
    if name is not None:
        currency.name = name.strip()
    if symbol is not None:
        currency.symbol = symbol.strip()
    if sort_order is not None:
        currency.sort_order = sort_order
    if is_active is not None:
        currency.is_active = is_active
    session.flush()
    audit.record(session, entity_type="Currency", action=AuditAction.UPDATE, entity_id=currency.id, user_id=user_id, after={"code": currency.code})
    return currency


def lock_used_currencies(session: Session) -> None:
    """Called after posting; freezes `decimals` for anything that now has history."""
    for currency in currencies(session):
        if not currency.is_locked and currency_in_use(session, currency.id):
            currency.is_locked = True
    session.flush()


def fiscal_years(session: Session) -> list[FiscalYear]:
    return list(session.execute(select(FiscalYear).order_by(FiscalYear.start_date_g)).scalars())


def create_fiscal_year(session: Session, jyear: int, user_id: int | None = None) -> FiscalYear:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    title = str(jyear)
    if session.execute(select(FiscalYear.id).where(FiscalYear.title == title)).first():
        raise ValidationError(f"سال مالی {title} قبلاً تعریف شده است.")
    start_g, end_g, start_j, end_j = jalali.fiscal_year_bounds(jyear)
    year = FiscalYear(
        title=title,
        start_date_g=start_g,
        end_date_g=end_g,
        start_date_j=start_j,
        end_date_j=end_j,
    )
    session.add(year)
    session.flush()
    audit.record(session, entity_type="FiscalYear", action=AuditAction.CREATE, entity_id=year.id, user_id=user_id, after={"title": title})
    return year


def current_fiscal_year(session: Session) -> FiscalYear | None:
    today = jalali.to_gregorian(jalali.today_jalali())
    row = session.execute(
        select(FiscalYear).where(FiscalYear.start_date_g <= today, FiscalYear.end_date_g >= today)
    ).scalars().first()
    if row:
        return row
    return session.execute(select(FiscalYear).order_by(FiscalYear.start_date_g.desc())).scalars().first()


def set_year_closed(session: Session, year: FiscalYear, closed: bool, user_id: int | None = None) -> FiscalYear:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    year.is_closed = closed
    session.flush()
    audit.record(session, entity_type="FiscalYear", action=AuditAction.UPDATE, entity_id=year.id, user_id=user_id, after={"is_closed": closed})
    return year


def tafsili_groups(session: Session, only_active: bool = False) -> list[TafsiliGroup]:
    stmt = select(TafsiliGroup)
    if only_active:
        stmt = stmt.where(TafsiliGroup.is_active.is_(True))
    return list(session.execute(stmt.order_by(TafsiliGroup.code)).scalars())


def create_tafsili_group(session: Session, *, code: str, name: str, user_id: int | None = None) -> TafsiliGroup:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    code = (code or "").strip()
    if not code:
        raise ValidationError("کد گروه تفصیلی الزامی است.")
    if session.execute(select(TafsiliGroup.id).where(TafsiliGroup.code == code)).first():
        raise ValidationError(f"گروه تفصیلی با کد {code} قبلاً تعریف شده است.")
    row = TafsiliGroup(code=code, name=(name or "").strip() or code)
    session.add(row)
    session.flush()
    audit.record(session, entity_type="TafsiliGroup", action=AuditAction.CREATE, entity_id=row.id, user_id=user_id, after={"code": code})
    return row


def tafsilis(
    session: Session,
    group_id: int | None = None,
    only_active: bool = False,
    group_ids: list[int] | None = None,
) -> list[Tafsili]:
    """`group_ids` matches a tafsili that is in ANY of the given groups."""
    stmt = select(Tafsili).options(selectinload(Tafsili.memberships))
    if group_ids:
        stmt = stmt.where(
            Tafsili.id.in_(select(TafsiliGroupMember.tafsili_id).where(TafsiliGroupMember.group_id.in_(group_ids)))
        )
    elif group_id is not None:
        stmt = stmt.where(
            Tafsili.id.in_(select(TafsiliGroupMember.tafsili_id).where(TafsiliGroupMember.group_id == group_id))
        )
    if only_active:
        stmt = stmt.where(Tafsili.is_active.is_(True))
    return list(session.execute(stmt.order_by(Tafsili.code)).scalars())


def set_tafsili_groups(
    session: Session,
    item: Tafsili,
    group_ids: list[int] | None,
    user_id: int | None = None,
) -> Tafsili:
    """Replace the group membership. The home group is always kept."""
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    wanted = {item.group_id}
    if group_ids:
        wanted.update(group_ids)
    wanted.add(item.group_id)
    found = {g.id for g in session.execute(select(TafsiliGroup).where(TafsiliGroup.id.in_(wanted))).scalars()}
    if found != wanted:
        raise ValidationError("گروه تفصیلی انتخاب‌شده یافت نشد.")
    item.memberships.clear()
    session.flush()
    for gid in sorted(wanted):
        item.memberships.append(TafsiliGroupMember(group_id=gid))
    session.flush()
    audit.record(
        session,
        entity_type="Tafsili",
        action=AuditAction.UPDATE,
        entity_id=item.id,
        user_id=user_id,
        after={"groups": sorted(wanted)},
        note="تغییر عضویت گروه‌ها",
    )
    return item


def suggest_tafsili_code(session: Session, group_id: int) -> str:
    """Continue the numbering the group already uses, so codes stay grouped."""
    codes = list(
        session.execute(
            select(Tafsili.code).where(
                Tafsili.id.in_(
                    select(TafsiliGroupMember.tafsili_id).where(TafsiliGroupMember.group_id == group_id)
                )
            )
        ).scalars()
    )
    numeric = [c for c in codes if c.isdigit()]
    if numeric:
        width = max(len(c) for c in numeric)
        return str(max(int(c) for c in numeric) + 1).zfill(width)
    group = session.get(TafsiliGroup, group_id)
    prefix = (group.code if group else "1").rstrip()
    return f"{prefix}01"


def tafsili_in_use(session: Session, tafsili_id: int) -> bool:
    return bool(
        session.execute(
            select(
                exists().where(
                    (DocumentLine.tafsili1_id == tafsili_id) | (DocumentLine.tafsili2_id == tafsili_id)
                )
            )
        ).scalar()
    )


def create_tafsili(
    session: Session,
    *,
    code: str,
    name: str,
    group_id: int,
    phone: str | None = None,
    national_id: str | None = None,
    address: str | None = None,
    note: str | None = None,
    extra_group_ids: list[int] | None = None,
    user_id: int | None = None,
) -> Tafsili:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    code = (code or "").strip()
    name = (name or "").strip()
    if not code:
        raise ValidationError("کد تفصیلی الزامی است.")
    if not name:
        raise ValidationError("نام تفصیلی الزامی است.")
    if session.execute(select(Tafsili.id).where(Tafsili.code == code)).first():
        raise ValidationError(f"تفصیلی با کد {code} قبلاً تعریف شده است.")
    group = session.get(TafsiliGroup, group_id)
    if group is None:
        raise ValidationError("گروه تفصیلی انتخاب نشده است.")
    item = Tafsili(
        code=code,
        name=name,
        group_id=group_id,
        phone=phone,
        national_id=national_id,
        address=address,
        note=note,
    )
    session.add(item)
    session.flush()
    set_tafsili_groups(session, item, list(extra_group_ids or []), user_id)
    audit.record(
        session,
        entity_type="Tafsili",
        action=AuditAction.CREATE,
        entity_id=item.id,
        user_id=user_id,
        after={"code": code, "groups": sorted(item.group_ids)},
    )
    return item


def update_tafsili(
    session: Session,
    item: Tafsili,
    *,
    code: str | None = None,
    name: str | None = None,
    group_id: int | None = None,
    extra_group_ids: list[int] | None = None,
    phone: str | None = None,
    national_id: str | None = None,
    address: str | None = None,
    note: str | None = None,
    is_active: bool | None = None,
    user_id: int | None = None,
) -> Tafsili:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    in_use = tafsili_in_use(session, item.id)
    if code is not None:
        code = code.strip()
        if in_use and code != item.code:
            raise InUseError("این تفصیلی سند دارد؛ کد آن قابل تغییر نیست.")
        other = session.execute(select(Tafsili).where(Tafsili.code == code, Tafsili.id != item.id)).first()
        if other:
            raise ValidationError(f"تفصیلی با کد {code} قبلاً تعریف شده است.")
        item.code = code
    if name is not None:
        item.name = name.strip()
    if group_id is not None and group_id != item.group_id:
        if in_use:
            raise InUseError("این تفصیلی سند دارد؛ گروه اصلی آن قابل تغییر نیست.")
        item.group_id = group_id
    if extra_group_ids is not None:
        set_tafsili_groups(session, item, extra_group_ids, user_id)
    elif group_id is not None:
        set_tafsili_groups(session, item, list(item.group_ids), user_id)
    for field, value in (
        ("phone", phone),
        ("national_id", national_id),
        ("address", address),
        ("note", note),
    ):
        if value is not None:
            setattr(item, field, value)
    if is_active is not None:
        item.is_active = is_active
    session.flush()
    audit.record(session, entity_type="Tafsili", action=AuditAction.UPDATE, entity_id=item.id, user_id=user_id)
    return item


def delete_tafsili(session: Session, item: Tafsili, user_id: int | None = None) -> None:
    auth_service.require(session, user_id, Perm.MASTER_EDIT)
    if tafsili_in_use(session, item.id):
        raise InUseError(f"تفصیلی «{item.display}» سند دارد و حذف نمی‌شود. آن را غیرفعال کنید.")
    audit.record(
        session,
        entity_type="Tafsili",
        action=AuditAction.DELETE_DRAFT,
        entity_id=item.id,
        user_id=user_id,
        before={"code": item.code},
    )
    session.delete(item)
    session.flush()
