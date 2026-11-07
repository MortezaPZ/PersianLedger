from __future__ import annotations

from PySide6.QtCore import Qt
from sqlalchemy import func, select

from app import bootstrap, config as config_module
from app.db.models import Document, Tafsili
from app.ui.context import AppContext
from app.ui.main_window import MainWindow
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.document_entry_view import DocumentEntryView


def _window(tmp_path, qapp) -> MainWindow:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    config = config_module.AppConfig(data_dir=data_dir, sqlite_path=data_dir / "ledger.sqlite3")
    startup = bootstrap.start(config, with_demo=True)
    window = MainWindow(AppContext(startup))
    window.show()
    qapp.processEvents()
    return window


def test_dashboard_is_start_page_with_current_year_summary(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    dashboard = next(view for view in window.views if isinstance(view, DashboardView))
    assert window.stack.currentWidget() is dashboard
    assert window.page_index["entry"] == 0
    assert window.page_index["list"] == 1
    assert dashboard.period.text() == f"نمای کلی عملکرد در سال مالی {window.ctx.fiscal_year_title}"

    with window.ctx.read_session() as db:
        year_id = window.ctx.fiscal_year_id
        document_count = db.execute(
            select(func.count(Document.id)).where(Document.fiscal_year_id == year_id)
        ).scalar_one()
        tafsili_count = db.execute(
            select(func.count(Tafsili.id)).where(Tafsili.is_active.is_(True))
        ).scalar_one()

    assert dashboard._metric_values["documents"].text() == f"{document_count:,}"
    assert dashboard._metric_values["tafsilis"].text() == f"{tafsili_count:,}"
    assert dashboard.recent_table.rowCount() == min(6, document_count)


def test_dashboard_actions_keep_existing_pages_and_open_recent_document(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    dashboard = next(view for view in window.views if isinstance(view, DashboardView))
    entry_index = window.page_index["entry"]
    dashboard.new_document.click()
    assert window.stack.currentIndex() == entry_index
    assert isinstance(window.stack.currentWidget(), DocumentEntryView)

    window.go_to(window.page_index["home"])
    assert dashboard.recent_table.rowCount() > 0
    expected = dashboard.recent_table.item(0, 0).data(Qt.UserRole)
    dashboard._open_selected_document(0, 0)
    assert window.stack.currentIndex() == entry_index
    assert window.views[entry_index].document_id == expected


def test_sidebar_search_filters_navigation_and_clear_restores_it(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    all_buttons = [button for button, _key in window._nav_buttons]
    assert all(button.isVisible() for button in all_buttons)

    window.nav_search.setText("تراز")
    qapp.processEvents()
    visible = [button.text() for button in all_buttons if button.isVisible()]
    assert visible == ["تراز آزمایشی"]
    assert [label.text() for label, _buttons in window._nav_groups if label.isVisible()] == ["گزارش‌ها"]

    window.nav_search.clear()
    qapp.processEvents()
    assert all(button.isVisible() for button in all_buttons)
