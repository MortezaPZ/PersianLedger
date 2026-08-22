from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QDialogButtonBox

from app import bootstrap, config as config_module
from app.domain import jalali
from app.ui.context import AppContext
from app.ui.views.accounts_view import AccountDialog, AccountsView
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.views.settings_view import SettingsView
from app.ui.views.trial_balance_view import TrialBalanceView
from app.ui.views.tafsili_view import TafsiliDialog
from app.ui.widgets.jalali_date_edit import JalaliDateEdit
from app.ui.widgets.line_grid import LineRow


def _ctx(tmp_path):
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    return AppContext(bootstrap.start(cfg, with_demo=True))


def test_balance_bar_switches_ok_and_bad(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    acc = ctx.refdata.postable[0]
    cur = ctx.refdata.currencies[0]
    view.model.set_rows([
        LineRow(acc.id, None, None, cur.id, Decimal("10"), Decimal("0")),
        LineRow(acc.id, None, None, cur.id, Decimal("0"), Decimal("3")),
    ])
    qapp.processEvents()
    assert view.balance.objectName() == "BalanceBad"
    view.model.set_rows([
        LineRow(acc.id, None, None, cur.id, Decimal("10"), Decimal("0")),
        LineRow(acc.id, None, None, cur.id, Decimal("0"), Decimal("10")),
    ])
    qapp.processEvents()
    assert view.balance.objectName() == "BalanceOk"


def test_dialog_buttons_are_persian(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    account = AccountDialog(ctx)
    tafsili = TafsiliDialog(ctx)
    for dialog in (account, tafsili):
        box = dialog.findChild(QDialogButtonBox)
        assert box.button(QDialogButtonBox.Save).text() == "ذخیره"
        assert box.button(QDialogButtonBox.Cancel).text() == "بی‌خیال"
        dialog.close()


def test_accounts_tree_lists_tafsili_leaves(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = AccountsView(ctx)
    labels = set()

    def walk(item):
        labels.add(item.text(2))
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(view.tree.topLevelItemCount()):
        walk(view.tree.topLevelItem(i))
    assert "تفصیلی" in labels


def test_jalali_calendar_pick_sets_date(qapp):
    widget = JalaliDateEdit()
    picked = jalali.parse_jalali("1404-05-12")
    widget._apply_jalali(picked)
    assert widget.gregorian() == jalali.to_gregorian(picked)


def test_report_dates_default_and_reject_invalid(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = TrialBalanceView(ctx)
    year = next(y for y in ctx.fiscal_years() if y.id == ctx.fiscal_year_id)
    assert view.from_date.gregorian() == year.start_date_g
    assert view.to_date.gregorian() == year.end_date_g
    view.from_date.setText("xxxx")
    assert view.date_range_error()


def test_settings_has_currency_and_year_actions(qapp, tmp_path):
    from PySide6.QtWidgets import QPushButton

    ctx = _ctx(tmp_path)
    view = SettingsView(ctx)
    texts = {btn.text() for btn in view.findChildren(QPushButton)}
    assert "افزودن ارز" in texts
    assert "سال مالی جدید" in texts
    assert "پاسخ پرسش‌های راهنما" in texts
