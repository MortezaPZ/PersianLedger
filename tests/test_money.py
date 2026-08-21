from decimal import Decimal

from app.domain import jalali, money


def test_parse_persian_amount():
    assert money.parse("۱٬۰۰۰") == Decimal("1000")
    formatted = money.format_amount(Decimal("15000"), 0, True)
    assert money.to_latin_digits(formatted.replace(",", "")) == "15000"


def test_fiscal_year_bounds():
    start, end, start_j, end_j = jalali.fiscal_year_bounds(1404)
    assert start_j.startswith("1404-01-01")
    assert end >= start
