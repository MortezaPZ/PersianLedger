from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from PySide6.QtWidgets import QDialogButtonBox

from app import bootstrap, config as config_module
from app.domain import jalali
from app.services import document_service, master_data
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
    widget._popup.set_date(1405, 5, 31)
    texts = [b.text() for b in widget._popup._buttons if b.text()]
    assert "۱" in texts
    assert "۳۱" in texts


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


def _attach_empty_draft(ctx):
    with ctx.session() as db:
        year = next(y for y in master_data.fiscal_years(db) if y.id == ctx.fiscal_year_id)
        return document_service.save_draft(
            db,
            document_service.DocumentInput(
                fiscal_year_id=year.id,
                date_g=year.start_date_g,
                date_j=year.start_date_j,
                description="draft",
            ),
        )


def test_new_document_releases_draft_number(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    view.document = _attach_empty_draft(ctx)
    number = view.document.number
    with patch.object(view, "confirm", return_value=True):
        view.new_document()
    assert view.document is None
    with ctx.read_session() as db:
        year = next(y for y in master_data.fiscal_years(db) if y.id == ctx.fiscal_year_id)
        assert document_service.next_number_preview(db, year) == number


def test_new_document_cancel_keeps_draft(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    view.document = _attach_empty_draft(ctx)
    kept = view.document.id
    with patch.object(view, "confirm", return_value=False):
        view.new_document()
    assert view.document is not None
    assert view.document.id == kept


def test_save_draft_does_not_crash_attachment_panel(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    acc = ctx.refdata.postable[0]
    cur = ctx.refdata.currencies[0]
    view.model.set_rows([
        LineRow(acc.id, None, None, cur.id, Decimal("10"), Decimal("0")),
        LineRow(acc.id, None, None, cur.id, Decimal("0"), Decimal("10")),
    ])
    with patch.object(view, "inform"), patch.object(view, "warn"):
        view.save_draft()
        assert view.attachments.document is view.document
        assert view.attachments.list.count() == 0
        view.post()
    assert view.attachments.document is view.document
    assert view.attachments.list.count() == 0


def test_browse_has_special_document_checkboxes(qapp, tmp_path):
    from app.ui.views.browse_view import BrowseView

    ctx = _ctx(tmp_path)
    view = BrowseView(ctx)
    assert view.chk_opening.text() == "افتتاحیه"
    assert view.chk_closing.text() == "اختتامیه"
    assert view.chk_close_books.text() == "بستن حساب‌ها"
    assert not view.chk_opening.isChecked()
    flt = view._filter()
    from app.domain.enums import DocumentType
    assert DocumentType.OPENING in flt.exclude_doc_types
    view.chk_opening.setChecked(True)
    flt = view._filter()
    assert DocumentType.OPENING not in flt.exclude_doc_types


def test_account_dialog_lists_period_natures(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    dialog = AccountDialog(ctx)
    labels = [dialog.nature.itemText(i) for i in range(dialog.nature.count())]
    assert "بدهکار طی دوره" in labels
    assert "بستانکار پایان دوره" in labels
    assert "مهم نیست" in labels
    dialog.close()


def test_trial_balance_has_no_description_column(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = TrialBalanceView(ctx)
    assert "شرح" not in TrialBalanceView.hint
    from app.ui.views.trial_balance_view import TrialBalanceModel
    assert TrialBalanceModel()._headers() == []
