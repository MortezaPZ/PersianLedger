"""Jalali <-> Gregorian conversion and the canonical `YYYY-MM-DD` Jalali string."""
from __future__ import annotations

import datetime as _dt
import re

import jdatetime

from app.domain.money import to_latin_digits, to_persian_digits

_J_PATTERN = re.compile(r"^\s*(\d{4})\s*[-/._]\s*(\d{1,2})\s*[-/._]\s*(\d{1,2})\s*$")
# Accountants routinely type just day/month ("۱۵/۵") and expect the working
# year.  Without this the value failed to parse, the date bound was dropped,
# and the report quietly covered the whole ledger instead of the range asked
# for.  Order is day/month, matching how the full form reads right to left.
_J_SHORT_PATTERN = re.compile(r"^\s*(\d{1,2})\s*[-/._]\s*(\d{1,2})\s*$")

# Set from the active fiscal year so a bare day/month lands in the year being
# worked on rather than whatever today happens to be.
_default_year: int | None = None


def set_default_year(jyear: int | None) -> None:
    global _default_year
    _default_year = jyear


def default_year() -> int:
    return _default_year or today_jalali().year

MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

WEEKDAY_NAMES = (
    "شنبه",
    "یکشنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
)


class JalaliError(ValueError):
    """Raised for an unparsable or impossible Jalali date."""


def is_leap(jyear: int) -> bool:
    return jdatetime.date(jyear, 1, 1).isleap()


def days_in_month(jyear: int, jmonth: int) -> int:
    if jmonth <= 6:
        return 31
    if jmonth <= 11:
        return 30
    return 30 if is_leap(jyear) else 29


def today_jalali() -> jdatetime.date:
    return jdatetime.date.today()


def to_jalali(gregorian: _dt.date) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=gregorian)


def to_gregorian(jalali: jdatetime.date) -> _dt.date:
    return jalali.togregorian()


def parse_jalali(text: str) -> jdatetime.date:
    raw = to_latin_digits(text or "")
    match = _J_PATTERN.match(raw)
    if match:
        year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        short = _J_SHORT_PATTERN.match(raw)
        if not short:
            raise JalaliError("تاریخ شمسی را به صورت ۱۴۰۴-۰۵-۲۴ وارد کنید.")
        year = default_year()
        day, month = int(short.group(1)), int(short.group(2))
    try:
        return jdatetime.date(year, month, day)
    except ValueError as exc:
        raise JalaliError("این تاریخ شمسی وجود ندارد.") from exc


def format_jalali(jalali: jdatetime.date, persian_digits: bool = False) -> str:
    text = f"{jalali.year:04d}-{jalali.month:02d}-{jalali.day:02d}"
    return to_persian_digits(text) if persian_digits else text


def jalali_string(gregorian: _dt.date) -> str:
    return format_jalali(to_jalali(gregorian))


def gregorian_from_string(text: str) -> _dt.date:
    return to_gregorian(parse_jalali(text))


def long_form(gregorian: _dt.date) -> str:
    jalali = to_jalali(gregorian)
    weekday = WEEKDAY_NAMES[jalali.weekday()]
    month = MONTH_NAMES[jalali.month - 1]
    return f"{weekday} {jalali.day} {month} {jalali.year}"


def fiscal_year_bounds(jyear: int) -> tuple[_dt.date, _dt.date, str, str]:
    start_j = jdatetime.date(jyear, 1, 1)
    end_j = jdatetime.date(jyear, 12, days_in_month(jyear, 12))
    return to_gregorian(start_j), to_gregorian(end_j), format_jalali(start_j), format_jalali(end_j)
