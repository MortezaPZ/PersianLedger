from __future__ import annotations


class LedgerError(Exception):
    """Base class for every rule violation the user should see in Persian."""


class ValidationError(LedgerError):
    pass


class UnbalancedDocumentError(ValidationError):
    def __init__(self, per_currency: dict[str, str]) -> None:
        self.per_currency = per_currency
        detail = "، ".join(f"{code}: {diff}" for code, diff in per_currency.items())
        super().__init__(f"سند تراز نیست. اختلاف بدهکار و بستانکار به تفکیک ارز — {detail}")


class ImmutableDocumentError(LedgerError):
    def __init__(self, number: int) -> None:
        super().__init__(
            f"سند شماره {number} قطعی شده است و قابل تغییر یا حذف نیست. "
            "برای اصلاح از سند برگشتی یا اصلاحی استفاده کنید."
        )


class InUseError(LedgerError):
    pass


class ConcurrencyError(LedgerError):
    def __init__(self, entity: str = "رکورد") -> None:
        super().__init__(
            f"این {entity} در همین فاصله توسط کاربر دیگری تغییر کرده است. "
            "لطفاً صفحه را تازه کنید و دوباره تلاش کنید."
        )


class PermissionDeniedError(LedgerError):
    def __init__(self, message: str = "شما اجازه انجام این عملیات را ندارید.") -> None:
        super().__init__(message)
