from __future__ import annotations

import enum

from app.domain.enums import UserRole


class Perm(str, enum.Enum):
    DOC_VIEW = "doc.view"
    DOC_DRAFT = "doc.draft"
    DOC_POST = "doc.post"
    DOC_REVERSE = "doc.reverse"
    DOC_UNPOST = "doc.unpost"
    DOC_DELETE_POSTED = "doc.delete_posted"
    DOC_PURGE = "doc.purge"
    MASTER_EDIT = "master.edit"
    REPORT_VIEW = "report.view"
    USERS_MANAGE = "users.manage"
    BACKUP = "backup"
    RESTORE = "restore"
    CONNECTION = "connection"
    AUDIT_VIEW = "audit.view"


ROLE_PERMS = {
    UserRole.ADMIN: set(Perm),
    UserRole.ACCOUNTANT: {
        Perm.DOC_VIEW,
        Perm.DOC_DRAFT,
        Perm.DOC_POST,
        Perm.DOC_REVERSE,
        Perm.MASTER_EDIT,
        Perm.REPORT_VIEW,
        Perm.BACKUP,
        Perm.AUDIT_VIEW,
    },
    UserRole.CLERK: {Perm.DOC_VIEW, Perm.DOC_DRAFT, Perm.REPORT_VIEW},
    UserRole.VIEWER: {Perm.DOC_VIEW, Perm.REPORT_VIEW},
}


def has(role: UserRole | None, perm: Perm) -> bool:
    if role is None:
        return False
    return perm in ROLE_PERMS.get(role, set())
