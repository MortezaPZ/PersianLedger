from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app import config as config_module
from app.db import engine as engine_module
from app.db import migrate
from app.domain.errors import LedgerError
from app.services import auth_service, backup_service, master_data
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.ui.widgets.tables import fit_columns, size_to_rows
from app.version import APP_NAME_FA, APP_VERSION


class UserDialog(QDialog):
    def __init__(self, context, parent=None, user=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.user = user
        self.setWindowTitle("ویرایش کاربر" if user else "کاربر جدید")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.username = QLineEdit()
        self.display_name = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.is_admin = QCheckBox("مدیر سیستم")
        self.is_active = QCheckBox("فعال")
        self.is_active.setChecked(True)
        form.addRow("نام کاربری", self.username)
        form.addRow("نام نمایشی", self.display_name)
        if user:
            self.username.setText(user.username)
            self.username.setReadOnly(True)
            self.display_name.setText(user.display_name)
            self.is_admin.setChecked(user.is_admin)
            self.is_active.setChecked(user.is_active)
            form.addRow("رمز عبور جدید (خالی = بدون تغییر)", self.password)
            form.addRow(self.is_active)
        else:
            form.addRow("رمز عبور", self.password)
        form.addRow(self.is_admin)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        try:
            with self.ctx.session() as db:
                if self.user is None:
                    auth_service.create_user(
                        db,
                        username=self.username.text(),
                        display_name=self.display_name.text(),
                        password=self.password.text(),
                        is_admin=self.is_admin.isChecked(),
                        created_by=self.ctx.user_id,
                    )
                else:
                    row = db.merge(self.user)
                    row.display_name = (self.display_name.text() or "").strip() or row.username
                    if self.password.text().strip():
                        auth_service.set_password(db, row, self.password.text(), user_id=self.ctx.user_id)
                    auth_service.set_admin(db, row, self.is_admin.isChecked(), user_id=self.ctx.user_id)
                    auth_service.set_active(db, row, self.is_active.isChecked(), user_id=self.ctx.user_id)
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, APP_NAME_FA, str(exc))


class UsersDialog(QDialog):
    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.setWindowTitle("کاربران")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        add = QPushButton("کاربر جدید"); add.setProperty("kind", "primary")
        edit = QPushButton("ویرایش")
        add.clicked.connect(self.add_user)
        edit.clicked.connect(self.edit_user)
        bar.addWidget(add); bar.addWidget(edit); bar.addStretch()
        layout.addLayout(bar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["نام کاربری", "نام نمایشی", "مدیر", "وضعیت"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_user)
        layout.addWidget(self.table)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        close.button(QDialogButtonBox.Close).clicked.connect(self.reject)
        layout.addWidget(close)
        self.reload()

    def reload(self) -> None:
        with self.ctx.read_session() as db:
            users = auth_service.list_users(db)
        self.table.setRowCount(len(users))
        for r, u in enumerate(users):
            values = (u.username, u.display_name, "بله" if u.is_admin else "خیر", "فعال" if u.is_active else "غیرفعال")
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, u.id)
                self.table.setItem(r, c, item)
        fit_columns(self.table)

    def _selected(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        uid = self.table.item(row, 0).data(Qt.UserRole)
        with self.ctx.read_session() as db:
            from app.db.models import User
            return db.get(User, uid)

    def add_user(self) -> None:
        if UserDialog(self.ctx, self).exec():
            self.reload()

    def edit_user(self) -> None:
        user = self._selected()
        if not user:
            return
        if UserDialog(self.ctx, self, user=user).exec():
            self.reload()


class CurrencyDialog(QDialog):
    def __init__(self, context, parent=None, currency=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.currency = currency
        self.setWindowTitle("ویرایش ارز" if currency else "ارز جدید")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.symbol = QLineEdit()
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 4)
        self.active = QCheckBox("فعال")
        self.active.setChecked(True)
        form.addRow("کد", self.code)
        form.addRow("نام", self.name)
        form.addRow("نماد", self.symbol)
        form.addRow("اعشار", self.decimals)
        if currency:
            form.addRow(self.active)
            self.code.setText(currency.code)
            self.code.setReadOnly(True)
            self.name.setText(currency.name)
            self.symbol.setText(currency.symbol)
            self.decimals.setValue(currency.decimals)
            self.active.setChecked(currency.is_active)
            if currency.is_locked:
                self.decimals.setEnabled(False)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        try:
            with self.ctx.session() as db:
                if self.currency is None:
                    master_data.create_currency(
                        db,
                        code=self.code.text(),
                        name=self.name.text(),
                        symbol=self.symbol.text(),
                        decimals=self.decimals.value(),
                        user_id=self.ctx.user_id,
                    )
                else:
                    row = db.merge(self.currency)
                    master_data.update_currency(
                        db,
                        row,
                        name=self.name.text(),
                        symbol=self.symbol.text(),
                        decimals=self.decimals.value(),
                        is_active=self.active.isChecked(),
                        user_id=self.ctx.user_id,
                    )
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, APP_NAME_FA, str(exc))


class FiscalYearDialog(QDialog):
    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.setWindowTitle("سال مالی جدید")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.year = QSpinBox()
        self.year.setRange(1300, 1600)
        from app.domain import jalali
        self.year.setValue(jalali.today_jalali().year)
        form.addRow("سال شمسی", self.year)
        hint = QLabel("بازه از ۱ فروردین تا پایان اسفند همان سال ساخته می‌شود.")
        hint.setWordWrap(True)
        form.addRow(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        try:
            with self.ctx.session() as db:
                master_data.create_fiscal_year(db, self.year.value(), user_id=self.ctx.user_id)
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, APP_NAME_FA, str(exc))


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
        cur_bar = QHBoxLayout()
        add_cur = QPushButton("افزودن ارز")
        add_cur.setProperty("kind", "primary")
        edit_cur = QPushButton("ویرایش ارز")
        add_cur.clicked.connect(self.add_currency)
        edit_cur.clicked.connect(self.edit_currency)
        cur_bar.addWidget(add_cur)
        cur_bar.addWidget(edit_cur)
        cur_bar.addStretch()
        year_bar = QHBoxLayout()
        add_year = QPushButton("سال مالی جدید")
        add_year.setProperty("kind", "primary")
        add_year.clicked.connect(self.add_fiscal_year)
        year_bar.addWidget(add_year)
        year_bar.addStretch()
        self.body.addWidget(currencies_title)
        self.body.addLayout(cur_bar)
        self.body.addWidget(self.currency_table)
        self.body.addWidget(years_title)
        self.body.addLayout(year_bar)
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
        if self.ctx.is_admin:
            users_box = QGroupBox("کاربران")
            users_layout = QVBoxLayout(users_box)
            users_btn = QPushButton("مدیریت کاربران")
            users_btn.setProperty("kind", "primary")
            users_btn.clicked.connect(self.manage_users)
            users_layout.addWidget(users_btn)
            self.body.addWidget(users_box)
        help_btn = QPushButton("پاسخ پرسش‌های راهنما")
        help_btn.clicked.connect(self.open_answers)
        self.body.addWidget(help_btn)
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
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, c.id)
                self.currency_table.setItem(r, col, item)
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

    def _selected_currency(self):
        row = self.currency_table.currentRow()
        if row < 0:
            return None
        item = self.currency_table.item(row, 0)
        cid = item.data(Qt.UserRole) if item else None
        if cid is None:
            return None
        with self.ctx.read_session() as db:
            from app.db.models import Currency
            return db.get(Currency, cid)

    def add_currency(self) -> None:
        if CurrencyDialog(self.ctx, self).exec():
            self.ctx.reload_refdata()
            self.reload()

    def edit_currency(self) -> None:
        currency = self._selected_currency()
        if not currency:
            self.warn("یک ارز را از جدول انتخاب کنید.")
            return
        if CurrencyDialog(self.ctx, self, currency=currency).exec():
            self.ctx.reload_refdata()
            self.reload()

    def add_fiscal_year(self) -> None:
        if FiscalYearDialog(self.ctx, self).exec():
            self.ctx.reload_refdata()
            self.reload()

    def manage_users(self) -> None:
        UsersDialog(self.ctx, self).exec()

    def open_answers(self) -> None:
        from app import paths

        path = paths.project_root() / "docs" / "answers-fa.md"
        if paths.is_frozen():
            frozen = paths.resource_dir() / "docs" / "answers-fa.md"
            if frozen.exists():
                path = frozen
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self.warn("فایل راهنما پیدا نشد.")

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
            result = backup_service.restore(engine_module.get_engine(), self.ctx.config, Path(path))
            engine_module.init_engine(self.ctx.config)
            migrate.upgrade_to_head(engine_module.get_engine(), self.ctx.config)
            self.ctx.reset_caches()
            self.ctx.resync_user()
            self.ctx.dataChanged.emit()
            if callable(self.after_restore):
                self.after_restore()
            r = result
            self.inform(
                f"بازیابی انجام شد.\n{r.documents} سند ({r.posted} قطعی)، {r.accounts} سرفصل و {r.tafsilis} تفصیلی از فایل پشتیبان بارگذاری شد.\nنسخه ایمنی از وضعیت قبلی:\n{r.safety_path}"
            )
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))
        except Exception as exc:
            self.report_error(exc)
