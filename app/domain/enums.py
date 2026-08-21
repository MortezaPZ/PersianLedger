from __future__ import annotations

import enum


class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class AccountNature(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    BOTH = "BOTH"


class DocumentType(str, enum.Enum):
    OPENING = "OPENING"
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    PARTY = "PARTY"
    TRANSFER = "TRANSFER"
    GENERAL = "GENERAL"
    REVERSAL = "REVERSAL"
    CORRECTION = "CORRECTION"


class DocumentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE_DRAFT = "DELETE_DRAFT"
    POST = "POST"
    REVERSE = "REVERSE"
    CORRECT = "CORRECT"
    DEACTIVATE = "DEACTIVATE"
    ACTIVATE = "ACTIVATE"
    LOGIN = "LOGIN"


ACCOUNT_TYPE_FA = {
    AccountType.ASSET: "دارایی",
    AccountType.LIABILITY: "بدهی",
    AccountType.EQUITY: "سرمایه",
    AccountType.INCOME: "درآمد",
    AccountType.EXPENSE: "هزینه",
}

ACCOUNT_NATURE_FA = {
    AccountNature.DEBIT: "بدهکار",
    AccountNature.CREDIT: "بستانکار",
    AccountNature.BOTH: "بدهکار/بستانکار",
}

DOCUMENT_TYPE_FA = {
    DocumentType.OPENING: "افتتاحیه",
    DocumentType.EXPENSE: "هزینه",
    DocumentType.INCOME: "درآمد",
    DocumentType.PARTY: "حساب اشخاص",
    DocumentType.TRANSFER: "انتقال بین صندوق‌ها",
    DocumentType.GENERAL: "عمومی",
    DocumentType.REVERSAL: "برگشتی",
    DocumentType.CORRECTION: "اصلاحی",
}

DOCUMENT_STATUS_FA = {
    DocumentStatus.DRAFT: "پیش‌نویس",
    DocumentStatus.POSTED: "قطعی",
}

AUDIT_ACTION_FA = {
    AuditAction.CREATE: "ایجاد",
    AuditAction.UPDATE: "ویرایش",
    AuditAction.DELETE_DRAFT: "حذف پیش‌نویس",
    AuditAction.POST: "قطعی کردن",
    AuditAction.REVERSE: "برگشت",
    AuditAction.CORRECT: "اصلاح",
    AuditAction.DEACTIVATE: "غیرفعال کردن",
    AuditAction.ACTIVATE: "فعال کردن",
    AuditAction.LOGIN: "ورود",
}
