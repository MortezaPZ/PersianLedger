"""Column types shared by every model."""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from sqlalchemy import BigInteger, Date, String, TypeDecorator

from app.domain import money


class MoneyColumn(TypeDecorator):
    """Decimal stored as an exact integer count of 1/10**STORAGE_SCALE units.

    BIGINT is used on SQLite and PostgreSQL alike, so SUM() is exact in SQL and a
    backend migration is a straight value copy. No float is involved at any point.
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return money.to_minor_units(money.parse(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return money.from_minor_units(int(value))


class JalaliDateColumn(TypeDecorator):
    """Canonical `1404-05-24` string; sortable and LIKE-filterable per month."""

    impl = String(10)
    cache_ok = True


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


__all__ = ("MoneyColumn", "JalaliDateColumn", "Date", "Decimal", "utcnow")
