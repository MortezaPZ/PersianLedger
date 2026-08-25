from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from PySide6.QtCore import Qt
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
from app.ui.widgets.line_grid import COL_T2, LineRow


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
    view._remember(_attach_empty_draft(ctx))
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
    view._remember(_attach_empty_draft(ctx))
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


def test_new_tafsili_from_grid_fills_cell(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    acc = next(
        a for a in ctx.refdata.postable if ctx.refdata.slot_enabled(a.id, 2)
    )
    view.model.setData(view.model.index(0, 1), acc.id)
    assert view.model.rows[0].tafsili2_id is None

    dialog = type("_D", (), {"exec": lambda self: True, "created_id": None})()

    with ctx.session() as db:
        group_id = next(iter(ctx.refdata.tafsilis_for(acc.id, 2))).group_id
        row = master_data.create_tafsili(db, code="9999", name="پروژه تستی", group_id=group_id)
        new_id = row.id
    dialog.created_id = new_id

    with patch("app.ui.views.tafsili_view.TafsiliDialog", return_value=dialog):
        view._new_tafsili(0, 2)

    assert view.model.rows[0].tafsili2_id == new_id
    index = view.model.index(0, COL_T2)
    assert view.model.data(index) == "9999 پروژه تستی"


def test_document_list_respects_date_range(qapp, tmp_path):
    from app.ui.views.document_list_view import DocumentListView

    ctx = _ctx(tmp_path)
    view = DocumentListView(ctx)
    with ctx.read_session() as db:
        from app.db.models import Document

        dates = sorted({d.date_j for d in db.query(Document).all()})
    assert dates, "seed data should contain documents"
    view.from_date.setText(dates[-1])
    view.to_date.setText(dates[-1])
    view.reload()
    assert view.table.rowCount() > 0
    for r in range(view.table.rowCount()):
        assert view.table.item(r, 1).text() == dates[-1]


def test_party_statement_supports_multiple_groups_and_parties(qapp, tmp_path):
    from app.ui.views.party_statement_view import PartyStatementView

    ctx = _ctx(tmp_path)
    view = PartyStatementView(ctx)
    by_code = {t.code: t.id for t in ctx.refdata.tafsilis}
    project_a, project_tehran = by_code["3105"], by_code["3001"]

    def _check(ids: set[int]) -> None:
        for i in range(view.party_list.count()):
            it = view.party_list.item(i)
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in ids else Qt.Unchecked)

    _check({project_a})
    view.run()
    rows_a = len(view._result.rows)
    assert rows_a > 0

    _check({project_a, project_tehran})
    view.run()
    rows_both = len(view._result.rows)
    assert rows_both > rows_a


def test_tafsili_dialog_shows_home_group_as_membership_and_linked_meoin(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    tafsili = next(t for t in ctx.refdata.tafsilis if t.code == "3105")
    dialog = TafsiliDialog(ctx, item=tafsili)
    home_row = next(
        dialog.extras.item(i)
        for i in range(dialog.extras.count())
        if dialog.extras.item(i).data(Qt.UserRole) == tafsili.group_id
    )
    assert home_row.checkState() == Qt.Checked
    assert not (home_row.flags() & Qt.ItemIsEnabled)
    assert dialog.linked_meoin.text() != "—"
    dialog.close()


def test_tafsili_view_lists_linked_meoin_column(qapp, tmp_path):
    from app.ui.views.tafsili_view import TafsiliView

    ctx = _ctx(tmp_path)
    view = TafsiliView(ctx)
    codes = [view.table.item(r, 0).text() for r in range(view.table.rowCount())]
    row = codes.index("3105")
    assert view.table.item(row, 4).text() != ""


def test_auth_service_hash_and_authenticate_roundtrip(tmp_path):
    from app.services import auth_service

    ctx = _ctx(tmp_path)
    with ctx.session() as db:
        auth_service.create_user(db, username="admin", display_name="مدیر", password="secret1", is_admin=True)
    with ctx.session() as db:
        ok = auth_service.authenticate(db, "admin", "secret1")
        assert ok is not None
        assert ok.is_admin
        bad = auth_service.authenticate(db, "admin", "wrong")
        assert bad is None


def test_login_dialog_first_run_creates_admin(qapp, tmp_path):
    from app.ui.login_dialog import LoginDialog

    ctx = _ctx(tmp_path)
    dialog = LoginDialog(ctx)
    assert dialog._first_run
    dialog.username_edit.setText("owner")
    dialog.display_edit.setText("مالک")
    dialog.password_edit.setText("pass1234")
    dialog.confirm_edit.setText("pass1234")
    dialog.accept()
    assert dialog.user_id is not None
    assert dialog.is_admin


def test_login_dialog_rejects_wrong_password(qapp, tmp_path):
    from app.services import auth_service
    from app.ui.login_dialog import LoginDialog

    ctx = _ctx(tmp_path)
    with ctx.session() as db:
        auth_service.create_user(db, username="u1", display_name="کاربر یک", password="rightpass")
    dialog = LoginDialog(ctx)
    assert not dialog._first_run
    dialog.username_edit.setText("u1")
    dialog.password_edit.setText("wrongpass")
    with patch("app.ui.login_dialog.QMessageBox.warning"):
        dialog.accept()
    assert dialog.user_id is None


def test_settings_shows_user_management_only_for_admins(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    ctx.is_admin = True
    view = SettingsView(ctx)
    from PySide6.QtWidgets import QPushButton
    texts = {btn.text() for btn in view.findChildren(QPushButton)}
    assert "مدیریت کاربران" in texts


def test_failed_save_does_not_poison_the_open_document(qapp, tmp_path):
    """A rolled-back session must not leave the view holding an expired object."""
    ctx = _ctx(tmp_path)
    view = DocumentEntryView(ctx)
    acc = next(
        a for a in ctx.refdata.postable
        if not ctx.refdata.slot_required(a.id, 1) and not ctx.refdata.slot_required(a.id, 2)
    )
    cur = ctx.refdata.currencies[0]
    rows = [
        LineRow(acc.id, None, None, cur.id, Decimal("10"), Decimal("0")),
        LineRow(acc.id, None, None, cur.id, Decimal("0"), Decimal("10")),
    ]
    errors = []
    with patch.object(view, "inform"), patch.object(view, "warn"), \
            patch.object(view, "report_error", side_effect=lambda exc: errors.append(exc)):
        view.model.set_rows(list(rows))
        view.save_draft()
        assert view.document_id

        view.model.set_rows(list(rows))
        with patch(
            "app.ui.views.document_entry_view.master_data.lock_used_currencies",
            side_effect=RuntimeError("boom"),
        ):
            view.post()
        assert len(errors) == 1

        errors.clear()
        view.model.set_rows(list(rows))
        view.post()

    assert not errors, f"retry after a failed save must work, got {errors}"
    assert view.document.is_posted


def test_trial_balance_has_no_description_column(qapp, tmp_path):
    ctx = _ctx(tmp_path)
    view = TrialBalanceView(ctx)
    assert "شرح" not in TrialBalanceView.hint
    from app.ui.views.trial_balance_view import TrialBalanceModel
    assert TrialBalanceModel()._headers() == []


def test_stale_user_id_does_not_block_saving(qapp, tmp_path):
    """A restored backup can lack the signed-in account; writes must still work."""
    from app.services import auth_service

    ctx = _ctx(tmp_path)
    ctx.user_id = 9999  # no such row
    view = DocumentEntryView(ctx)
    acc = next(
        a for a in ctx.refdata.postable
        if not ctx.refdata.slot_required(a.id, 1) and not ctx.refdata.slot_required(a.id, 2)
    )
    cur = ctx.refdata.currencies[0]
    view.model.set_rows([
        LineRow(acc.id, None, None, cur.id, Decimal("10"), Decimal("0")),
        LineRow(acc.id, None, None, cur.id, Decimal("0"), Decimal("10")),
    ])
    errors = []
    with patch.object(view, "inform"), patch.object(view, "warn"), \
            patch.object(view, "report_error", side_effect=lambda e: errors.append(e)):
        view.save_draft()
    assert not errors, f"stale user id must not abort the write: {errors}"
    assert view.document_id
    with ctx.read_session() as db:
        assert auth_service.valid_user_id(db, 9999) is None


def test_accounts_tree_edit_loads_kol_and_moin(qapp, tmp_path):
    """The dialog reads relationships, so the row must come back eager-loaded."""
    ctx = _ctx(tmp_path)
    view = AccountsView(ctx)
    for level in (1, 2):
        ident = next(a.id for a in ctx.refdata.accounts if a.level == level)
        acc = view._load_account(ident)
        dialog = AccountDialog(ctx, None, account=acc)
        assert dialog.code.text() == acc.code
        assert acc.tafsili_rules is not None
        dialog.close()


def test_project_example_is_seeded_without_demo_flag(qapp, tmp_path):
    from app.db.models import Document, DocumentLine, Tafsili

    data = tmp_path / "plain"
    data.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    ctx = AppContext(bootstrap.start(cfg))  # no with_demo
    with ctx.read_session() as db:
        descriptions = [d.description for d in db.query(Document).all()]
        assert any("پروژه A" in d for d in descriptions), descriptions
        person = db.query(Tafsili).filter(Tafsili.code == "2106").one()
        assert len(person.group_ids) == 2, "نفر A must sit in both اشخاص and صندوق‌ها"
        cash = db.query(DocumentLine).filter(DocumentLine.description.like("%نفر A%")).one()
        assert cash.tafsili1_id == person.id
        assert db.get(Tafsili, cash.tafsili2_id).code == "3105"


def test_income_statement_reports_net_result(qapp, tmp_path):
    from app.services import ledger_reports as lr
    from app.services.report_service import StatementFilter
    from app.ui.views.income_statement_view import IncomeStatementView

    ctx = _ctx(tmp_path)
    with ctx.read_session() as db:
        result = lr.income_statement(db, StatementFilter())
    assert result.expense, "the seeded example has expenses"
    for col in result.currencies:
        expected = result.income_total.get(col.id, Decimal(0)) - result.expense_total.get(col.id, Decimal(0))
        assert result.net[col.id] == expected

    view = IncomeStatementView(ctx)
    view.run()
    labels = [view.model.data(view.model.index(r, 1)) for r in range(view.model.rowCount())]
    assert "درآمدها" in labels and "هزینه‌ها" in labels
    assert "سود (زیان) خالص" in labels


def test_income_statement_prints_when_a_currency_has_no_income(qapp, tmp_path):
    """Printing must not crash on a currency that only has expenses."""
    from app.export import excel, printing
    from app.services import ledger_reports as lr
    from app.services.report_service import StatementFilter

    ctx = _ctx(tmp_path)
    all_currency_ids = [c.id for c in ctx.refdata.currencies]
    with ctx.read_session() as db:
        result = lr.income_statement(db, StatementFilter(currency_ids=all_currency_ids))
    assert len(result.currencies) > 1, "need several currency columns for this to bite"
    html = printing.income_statement_html(result)
    assert "سود (زیان) خالص" in html
    excel.export_income_statement(tmp_path / "pnl.xlsx", result)
    assert (tmp_path / "pnl.xlsx").exists()


def test_trial_balance_can_group_by_tafsili_2(qapp, tmp_path):
    """Projects live in the تفصیلی ۲ slot, so that level has to be reportable."""
    from app.services import ledger_reports as lr
    from app.services.report_service import StatementFilter

    ctx = _ctx(tmp_path)
    assert lr.LEVEL_TAFSILI2 in lr.LEVEL_FA
    with ctx.read_session() as db:
        slot1 = lr.trial_balance(db, StatementFilter(), level=lr.LEVEL_TAFSILI, columns=4)
        slot2 = lr.trial_balance(db, StatementFilter(), level=lr.LEVEL_TAFSILI2, columns=4)
    names1 = {r.code for r in slot1.rows}
    names2 = {r.code for r in slot2.rows}
    assert "3105" not in names1, "پروژه A is only ever in slot 2"
    assert "3105" in names2, "grouping by تفصیلی ۲ must surface the project"
    project = next(r for r in slot2.rows if r.code == "3105")
    assert any(project.cell(4, 0, c.id) for c in slot2.currencies), "project must show turnover"
