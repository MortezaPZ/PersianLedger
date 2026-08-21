from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app import config as config_module
from app.db import engine as engine_module
from app.db import migrate
from app.domain.errors import LedgerError
from app.services import backup_service, master_data
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.tables import fit_columns, size_to_rows
from app.version import APP_NAME_FA, APP_VERSION


class SettingsView(BaseView):
    title = "ارزها و سال مالی"
    hint = "تعریف ارز، سال مالی، پشتیبان‌گیری و بازیابی"
    scrollable = True  # currencies + years + appearance + backups exceed one screen

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.after_restore = None
        self.currency_table = QTableWidget(0, 5)
        self.currency_table.setHorizontalHeaderLabels(["کد", "نام", "نماد", "اعشار", "وضعیت"])
        self.year_table = QTableWidget(0, 4)
        self.year_table.setHorizontalHeaderLabels(["سال", "از", "تا", "وضعیت"])
        for table in (self.currency_table, self.year_table):
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        currencies_title = QLabel("ارزها")
        currencies_title.setObjectName("SectionTitle")
        years_title = QLabel("سال مالی")
        years_title.setObjectName("SectionTitle")
        self.body.addWidget(currencies_title)
        self.body.addWidget(self.currency_table)
        self.body.addWidget(years_title)
        self.body.addWidget(self.year_table)
        appearance = QGroupBox("ظاهر")
        appear_layout = QVBoxLayout(appearance)
        self.dark_check = QCheckBox("حالت تیره")
        self.dark_check.setChecked(self.ctx.config.dark_mode)
        self.dark_check.toggled.connect(self._toggle_dark)
        appear_layout.addWidget(self.dark_check)
        hint = QLabel("فونت برنامه Vazirmatn است و جهت صفحه راست‌به‌چپ می‌ماند.")
        hint.setObjectName("PageHint")
        hint.setWordWrap(True)
        appear_layout.addWidget(hint)
        self.body.addWidget(appearance)
        box = QGroupBox("پشتیبان‌گیری و بازیابی")
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        backup = QPushButton("تهیه پشتیبان")
        backup.setProperty("kind", "primary")
        quick = QPushButton("پشتیبان سریع")
        restore = QPushButton("بازیابی از فایل")
        restore.setProperty("kind", "danger")
        folder = QPushButton("باز کردن پوشه پشتیبان‌ها")
        backup.clicked.connect(self.backup_as)
        quick.clicked.connect(self.backup_quick)
        restore.clicked.connect(self.restore)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ctx.config.backup_dir))))
        for btn in (backup, quick, restore, folder):
            row.addWidget(btn)
        layout.addLayout(row)
        self.backup_table = QTableWidget(0, 3)
        self.backup_table.setHorizontalHeaderLabels(["فایل", "حجم", "تاریخ"])
        layout.addWidget(self.backup_table)
        self.body.addWidget(box)
        self.about_label = QLabel()
        self.body.addWidget(self.about_label)
        self.reload()

    def refresh(self) -> None:
        self.reload()

    def _toggle_dark(self, on: bool) -> None:
        self.ctx.config.dark_mode = bool(on)
        config_module.save(self.ctx.config)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            theme.apply(app, dark=bool(on))
        # The stylesheet reloads on its own, but icons already handed to the nav
        # buttons keep the previous theme's colour until they are redrawn.
        window = self.window()
        if hasattr(window, "restyle_nav"):
            window.restyle_nav()

    def reload(self) -> None:
        with self.ctx.read_session() as db:
            currencies = master_data.currencies(db)
            years = master_data.fiscal_years(db)
        self.currency_table.setRowCount(len(currencies))
        for r, c in enumerate(currencies):
            for col, value in enumerate((c.code, c.name, c.symbol, str(c.decimals), "فعال" if c.is_active else "غیرفعال")):
                self.currency_table.setItem(r, col, QTableWidgetItem(value))
        self.year_table.setRowCount(len(years))
        for r, y in enumerate(years):
            for col, value in enumerate((y.title, y.start_date_j, y.end_date_j, "بسته" if y.is_closed else "باز")):
                self.year_table.setItem(r, col, QTableWidgetItem(value))
        backups = backup_service.list_backups(self.ctx.config)
        self.backup_table.setRowCount(len(backups))
        for r, b in enumerate(backups):
            self.backup_table.setItem(r, 0, QTableWidgetItem(b.path.name))
            self.backup_table.setItem(r, 1, QTableWidgetItem(b.size_text))
            self.backup_table.setItem(r, 2, QTableWidgetItem(str(b.taken_at)))
        for table in (self.currency_table, self.year_table, self.backup_table):
            fit_columns(table)
            size_to_rows(table)
        engine = engine_module.get_engine()
        rev = migrate.current_revision(engine)
        self.about_label.setText(
            f"{APP_NAME_FA} {APP_VERSION}  |  {self.ctx.config.describe()}  |  ساختار: {rev or '—'}"
        )

    def backup_quick(self) -> None:
        try:
            info = backup_service.create(engine_module.get_engine(), self.ctx.config)
            self.inform(f"پشتیبان ذخیره شد:\n{info.path}")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def backup_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "تهیه پشتیبان", str(self.ctx.config.backup_dir / backup_service.suggested_name()), "SQLite (*.sqlite3)")
        if not path:
            return
        try:
            info = backup_service.create(engine_module.get_engine(), self.ctx.config, Path(path))
            self.inform(f"پشتیبان ذخیره شد:\n{info.path}")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "بازیابی از فایل", str(self.ctx.config.backup_dir), "SQLite (*.sqlite3 *.db)")
        if not path or not self.confirm("بازیابی فایل پشتیبان، دیتابیس فعلی را جایگزین می‌کند. ادامه می‌دهید؟"):
            return
        self.apply_restore(Path(path))

    def apply_restore(self, path: Path) -> None:
        try:
            safety = backup_service.restore(engine_module.get_engine(), self.ctx.config, Path(path))
            engine_module.init_engine(self.ctx.config)
            migrate.upgrade_to_head(engine_module.get_engine(), self.ctx.config)
            self.ctx.reload_refdata()
            self.ctx.dataChanged.emit()
            if callable(self.after_restore):
                self.after_restore()
            self.inform(f"بازیابی انجام شد. نسخه ایمنی:\n{safety}")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))
        except Exception as exc:
            self.report_error(exc)
