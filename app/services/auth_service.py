"""Username/password accounts. Local passwords, salted PBKDF2, no network calls."""
from __future__ import annotations

import hashlib
import hmac
import os

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.types import utcnow
from app.domain.enums import AuditAction, UserRole
from app.domain.errors import PermissionDeniedError, ValidationError
from app.domain.permissions import Perm, ROLE_PERMS, has
from app.services import audit

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)


def valid_user_id(session: Session, user_id: int | None) -> int | None:
    """`user_id` only if that row exists in *this* database, otherwise None.

    A restored backup can be missing the signed-in account. Writing its id into
    a foreign key would abort the whole transaction, so an unknown id is
    recorded as "no user" rather than blocking the user's accounting work.
    """
    if user_id is None:
        return None
    return user_id if session.get(User, user_id) is not None else None


def has_any_users(session: Session) -> bool:
    return bool(session.execute(select(exists().where(User.id.isnot(None)))).scalar())


def list_users(session: Session) -> list[User]:
    return list(session.execute(select(User).order_by(User.username)).scalars())


def _validate_username(session: Session, username: str, *, exclude_id: int | None = None) -> str:
    username = (username or "").strip()
    if not username:
        raise ValidationError("نام کاربری الزامی است.")
    stmt = select(User.id).where(User.username == username)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    if session.execute(stmt).first():
        raise ValidationError(f"نام کاربری «{username}» قبلاً استفاده شده است.")
    return username


def permissions_of(user: User) -> set[Perm]:
    return set(ROLE_PERMS.get(user.role, set()))


def require(session: Session, user_id: int | None, perm: Perm) -> User | None:
    """Allow the call when `user_id` is None (seed and internal helpers).

    The UI always passes `ctx.user_id`. A restored backup may not contain
    that user; that case is denied rather than silently proceeding.
    """
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None:
        raise PermissionDeniedError("کاربر شما در این دیتابیس وجود ندارد. دوباره وارد شوید.")
    if not user.is_active:
        raise PermissionDeniedError()
    if not has(user.role, perm):
        raise PermissionDeniedError()
    return user


def create_user(
    session: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    is_admin: bool = False,
    role: UserRole | None = None,
    created_by: int | None = None,
    user_id: int | None = None,
) -> User:
    actor = created_by if created_by is not None else user_id
    require(session, actor, Perm.USERS_MANAGE)
    username = _validate_username(session, username)
    if not (password or "").strip():
        raise ValidationError("رمز عبور الزامی است.")
    if len(password) < 4:
        raise ValidationError("رمز عبور باید حداقل ۴ نویسه باشد.")
    if role is None:
        role = UserRole.ADMIN if is_admin else UserRole.ACCOUNTANT
    is_admin = role == UserRole.ADMIN
    row = User(
        username=username,
        display_name=(display_name or "").strip() or username,
        password_hash=hash_password(password),
        is_active=True,
        is_admin=is_admin,
        role=role,
    )
    session.add(row)
    session.flush()
    audit.record(
        session,
        entity_type="User",
        action=AuditAction.CREATE,
        entity_id=row.id,
        user_id=actor,
        after={"username": username, "role": role.value},
    )
    return row


def set_password(session: Session, user: User, new_password: str, *, user_id: int | None = None) -> None:
    if user_id is not None and user.id != user_id:
        require(session, user_id, Perm.USERS_MANAGE)
    if len(new_password or "") < 4:
        raise ValidationError("رمز عبور باید حداقل ۴ نویسه باشد.")
    user.password_hash = hash_password(new_password)
    audit.record(session, entity_type="User", action=AuditAction.UPDATE, entity_id=user.id, user_id=user_id, note="password reset")


def set_active(session: Session, user: User, is_active: bool, *, user_id: int | None = None) -> None:
    require(session, user_id, Perm.USERS_MANAGE)
    user.is_active = is_active
    audit.record(
        session,
        entity_type="User",
        action=AuditAction.ACTIVATE if is_active else AuditAction.DEACTIVATE,
        entity_id=user.id,
        user_id=user_id,
    )


def set_role(session: Session, user: User, role: UserRole, *, user_id: int | None = None) -> None:
    require(session, user_id, Perm.USERS_MANAGE)
    user.role = role
    user.is_admin = role == UserRole.ADMIN
    audit.record(session, entity_type="User", action=AuditAction.UPDATE, entity_id=user.id, user_id=user_id, note=f"role={role.value}")


def set_admin(session: Session, user: User, is_admin: bool, *, user_id: int | None = None) -> None:
    set_role(session, user, UserRole.ADMIN if is_admin else UserRole.ACCOUNTANT, user_id=user_id)


def authenticate(session: Session, username: str, password: str) -> User | None:
    username = (username or "").strip()
    if not username:
        return None
    user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not user.is_active or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = utcnow()
    audit.record(session, entity_type="User", action=AuditAction.LOGIN, entity_id=user.id, user_id=user.id)
    return user
