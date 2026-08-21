"""Exact money handling. float is never used for an amount anywhere in this app."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext

getcontext().prec = 34

STORAGE_SCALE = 4
STORAGE_QUANT = Decimal(1).scaleb(-STORAGE_SCALE)
ZERO = Decimal(0)

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate(_PERSIAN_DIGITS)}
_DIGIT_MAP.update({ord(a): str(i) for i, a in enumerate(_ARABIC_DIGITS)})
_DIGIT_MAP[ord("٫")] = "."
_DIGIT_MAP[ord("٬")] = ""


def to_latin_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def to_persian_digits(text: str) -> str:
    return text.translate({ord(str(i)): _PERSIAN_DIGITS[i] for i in range(10)})


class MoneyError(ValueError):
    pass


def parse(text, scale: int | None = None) -> Decimal:
    if text is None or text == "":
        return ZERO
    if isinstance(text, Decimal):
        value = text
    elif isinstance(text, int):
        value = Decimal(text)
    else:
        raw = to_latin_digits(str(text)).strip().replace(",", "").replace(" ", "")
        if not raw:
            return ZERO
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError) as exc:
            raise MoneyError("مبلغ واردشده معتبر نیست.") from exc
    if scale is not None:
        value = quantize(value, scale)
    return value


def quantize(value: Decimal, scale: int | None = None) -> Decimal:
    q = Decimal(1).scaleb(-(STORAGE_SCALE if scale is None else scale))
    return value.quantize(q, rounding=ROUND_HALF_UP)


def fits_scale(value: Decimal, scale: int) -> bool:
    return quantize(value, scale) == value


def to_minor_units(value: Decimal) -> int:
    return int(quantize(value, STORAGE_SCALE) / STORAGE_QUANT)


def from_minor_units(value: int) -> Decimal:
    return Decimal(value) * STORAGE_QUANT


def format_amount(
    value: Decimal | None,
    scale: int = 2,
    persian_digits: bool = False,
) -> str:
    if value is None:
        return ""
    quantized = quantize(value, scale)
    text = f"{quantized:,.{scale}f}"
    if persian_digits:
        text = to_persian_digits(text)
    return text
