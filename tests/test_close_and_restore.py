"""Automated coverage for delivery checklist items 9 (exit backup) and 10 (restore)."""
from __future__ import annotations

from unittest.mock import patch

from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMessageBox

from app import bootstrap, config as config_module
from app.db import engine as engine_module
from app.services import backup_service, master_data
from app.ui.context import AppContext
from app.ui.main_window import MainWindow, clamp_to_screen
from app.ui.views.accounts_view import AccountsView
from app.ui.views.settings_view import SettingsView
from app.ui.views.tafsili_view import TafsiliView


def _window(tmp_path, qapp) -> MainWindow:
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(
        data_dir=data,
        sqlite_path=data / "ledger.sqlite3",
    )
    startup = bootstrap.start(cfg, with_demo=True)
    window = MainWindow(AppContext(startup))
    window.show()
    qapp.processEvents()
    return window


def _tree_labels(view: AccountsView) -> set[str]:
    labels: set[str] = set()

    def walk(item) -> None:
        labels.add(item.text(0))
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(view.tree.topLevelItemCount()):
        walk(view.tree.topLevelItem(i))
    return labels


def test_exit_dialog_shows_yes_no_cancel(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    box = window._make_exit_backup_box()
    box.show()
    qapp.processEvents()
    assert box.isVisible()
    assert box.text() == "آیا می‌خواهید قبل از خروج یک نسخه پشتیبان تهیه شود؟"
    labels = {btn.text() for btn in box.buttons()}
    assert labels == {"بله", "خیر", "انصراف"}
    roles = {box.buttonRole(btn) for btn in box.buttons()}
    assert roles == {QMessageBox.YesRole, QMessageBox.NoRole, QMessageBox.RejectRole}
    box.close()


def test_exit_cancel_keeps_app_open(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    before = list(window.ctx.config.backup_dir.glob("*.sqlite3"))
    event = QCloseEvent()
    with patch.object(window, "_query_exit_backup", return_value="cancel"):
        window.closeEvent(event)
    qapp.processEvents()
    assert not event.isAccepted()
    assert window.isVisible()
    assert list(window.ctx.config.backup_dir.glob("*.sqlite3")) == before


def test_exit_no_closes_without_backup(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    before = {p.name for p in window.ctx.config.backup_dir.glob("*.sqlite3")}
    event = QCloseEvent()
    with patch.object(window, "_query_exit_backup", return_value="no"):
        window.closeEvent(event)
    qapp.processEvents()
    assert event.isAccepted()
    after = {p.name for p in window.ctx.config.backup_dir.glob("*.sqlite3")}
    assert after == before


def test_exit_yes_creates_backup_and_closes(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    before = {p.name for p in window.ctx.config.backup_dir.glob("*.sqlite3")}
    event = QCloseEvent()
    with (
        patch.object(window, "_query_exit_backup", return_value="yes"),
        patch.object(QMessageBox, "information", return_value=QMessageBox.Ok),
    ):
        window.closeEvent(event)
    qapp.processEvents()
    assert event.isAccepted()
    after = {p.name for p in window.ctx.config.backup_dir.glob("*.sqlite3")}
    assert after - before


def test_restore_reopens_engine_reloads_tree_and_clamps_geometry(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    settings = next(v for v in window.views if isinstance(v, SettingsView))
    accounts = next(v for v in window.views if isinstance(v, AccountsView))
    tafsili_view = next(v for v in window.views if isinstance(v, TafsiliView))

    snapshot = backup_service.create(engine_module.get_engine(), window.ctx.config)
    codes_before = {t.code for t in window.ctx.refdata.tafsilis}
    tree_before = _tree_labels(accounts)
    old_engine = engine_module.get_engine()

    group_id = window.ctx.refdata.groups[0].id
    with window.ctx.session() as db:
        master_data.create_tafsili(db, code="ZZ-RESTORE", name="موقت بازیابی", group_id=group_id)
    window.ctx.reload_refdata()
    accounts.refresh()
    tafsili_view.refresh()
    qapp.processEvents()
    assert "ZZ-RESTORE" in {t.code for t in window.ctx.refdata.tafsilis}

    window.move(-8000, -8000)
    with (
        patch.object(SettingsView, "inform", lambda *args, **kwargs: None),
        patch("app.ui.main_window.clamp_to_screen", wraps=clamp_to_screen) as clamped,
    ):
        settings.apply_restore(snapshot.path)
    qapp.processEvents()

    new_engine = engine_module.get_engine()
    assert new_engine is not old_engine
    with new_engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")

    assert "ZZ-RESTORE" not in {t.code for t in window.ctx.refdata.tafsilis}
    assert {t.code for t in window.ctx.refdata.tafsilis} == codes_before
    assert _tree_labels(accounts) == tree_before
    assert clamped.called
    assert window.x() != -8000
    assert window.y() != -8000


def test_clamp_to_screen_pulls_window_onto_display(qapp):
    from PySide6.QtWidgets import QMainWindow

    window = QMainWindow()
    window.show()
    qapp.processEvents()
    window.setGeometry(-8000, -8000, 9000, 9000)
    clamp_to_screen(window)
    qapp.processEvents()
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert window.width() <= screen.width()
    assert window.height() <= screen.height()
    assert screen.intersects(window.frameGeometry())
