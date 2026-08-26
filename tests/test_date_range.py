"""Date entry must never silently widen a report to the whole ledger.

The employer reported picking 15/5–16/5 and still seeing documents dated
today.  The cause was the short day/month form failing to parse: the bound
became ``None``, the WHERE clause dropped, and every document came back.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from app.domain import jalali
from app.domain.jalali import JalaliError


@pytest.fixture(autouse=True)
def working_year():
    jalali.set_default_year(1405)
    yield
    jalali.set_default_year(None)


@pytest.mark.parametrize(
    "text",
    ["1405-05-15", "1405/05/15", "1405-5-15", "1405.05.15", "۱۴۰۵-۰۵-۱۵", "  1405-05-15  "],
)
def test_full_forms_parse_to_the_same_day(text):
    assert jalali.gregorian_from_string(text) == _dt.date(2026, 8, 6)


@pytest.mark.parametrize("text", ["15/5", "۱۵/۵", "15-5", "15.5"])
def test_short_day_month_uses_the_working_year(text):
    assert jalali.gregorian_from_string(text) == _dt.date(2026, 8, 6)


def test_short_form_follows_the_fiscal_year_not_today():
    jalali.set_default_year(1404)
    assert jalali.gregorian_from_string("15/5").year == 2025


@pytest.mark.parametrize("text", ["32/5", "15/13", "abc", "1405-05", "/", ""])
def test_unparseable_dates_raise_instead_of_becoming_none(text):
    with pytest.raises(JalaliError):
        jalali.gregorian_from_string(text)


def test_report_rejects_a_bad_date_rather_than_running_unbounded(qapp):
    """A typo must stop the run, not quietly report on every document."""
    from app.ui.views.report_base import ReportView
    from app.ui.widgets.jalali_date_edit import JalaliDateEdit

    view = ReportView.__new__(ReportView)  # no DB needed for the date gate
    view.from_date = JalaliDateEdit()
    view.to_date = JalaliDateEdit()

    view.from_date.setText("1405-05-15")
    view.to_date.setText("چرند")
    assert view.date_range_error() is not None

    view.to_date.setText("1405-05-16")
    assert view.date_range_error() is None

    view.from_date.setText("1405-05-20")  # reversed range
    assert view.date_range_error() is not None


def test_empty_date_still_means_no_bound(qapp):
    from app.ui.widgets.jalali_date_edit import JalaliDateEdit

    field = JalaliDateEdit()
    field.clear()
    assert field.gregorian() is None
