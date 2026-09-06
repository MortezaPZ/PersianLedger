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
    DEBIT_PERIOD = "DEBIT_PERIOD"
    CREDIT_PERIOD = "CREDIT_PERIOD"
    DEBIT_CLOSING = "DEBIT_CLOSING"
    CREDIT_CLOSING = "CREDIT_CLOSING"


class DocumentType(str, enum.Enum):
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    CLOSE_BOOKS = "CLOSE_BOOKS"
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
    UNPOST = "UNPOST"
    DELETE_POSTED = "DELETE_POSTED"
    PURGE = "PURGE"


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
    AccountNature.BOTH: "مهم نیست",
    AccountNature.DEBIT_PERIOD: "بدهکار طی دوره",
    AccountNature.CREDIT_PERIOD: "بستانکار طی دوره",
    AccountNature.DEBIT_CLOSING: "بدهکار پایان دوره",
    AccountNature.CREDIT_CLOSING: "بستانکار پایان دوره",
}

NATURE_CHOICES = (
    AccountNature.DEBIT_PERIOD,
    AccountNature.CREDIT_PERIOD,
    AccountNature.DEBIT_CLOSING,
    AccountNature.CREDIT_CLOSING,
    AccountNature.BOTH,
)

PERIOD_NATURES = {
    AccountNature.DEBIT_PERIOD,
    AccountNature.CREDIT_PERIOD,
}


def normalize_nature(value: AccountNature) -> AccountNature:
    if value == AccountNature.DEBIT:
        return AccountNature.DEBIT_PERIOD
    if value == AccountNature.CREDIT:
        return AccountNature.CREDIT_PERIOD
    return value


def nature_carries_opening(value: AccountNature | None) -> bool:
    if value is None:
        return True
    return normalize_nature(value) not in PERIOD_NATURES

DOCUMENT_TYPE_FA = {
    DocumentType.OPENING: "افتتاحیه",
    DocumentType.CLOSING: "اختتامیه",
    DocumentType.CLOSE_BOOKS: "بستن حساب‌ها",
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
    AuditAction.UNPOST: "بازگردانی به پیش‌نویس",
    AuditAction.DELETE_POSTED: "حذف سند قطعی",
    AuditAction.PURGE: "پاک‌سازی اسناد",
}
