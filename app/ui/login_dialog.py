"""Startup login: normal sign-in, or first-run admin creation when no user exists."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.domain.enums import UserRole
from app.domain.errors import LedgerError
from app.services import auth_service
from app.version import APP_NAME_FA


class LoginDialog(QDialog):
    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.user_id: int | None = None
        self.username: str | None = None
        self.display_name: str | None = None
        self.is_admin: bool = False
        self.role = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(APP_NAME_FA)
        with self.ctx.read_session() as db:
            self._first_run = not auth_service.has_any_users(db)
        if self._first_run:
            self._build_first_run()
        else:
            self._build_login()

    def _build_login(self) -> None:
        self.setWindowTitle(f"ورود — {APP_NAME_FA}")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self.accept)
        form.addRow("نام کاربری", self.username_edit)
        form.addRow("رمز عبور", self.password_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("ورود")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._add_connection_row(layout)
        self.username_edit.setFocus()

    def _build_first_run(self) -> None:
        self.setWindowTitle(f"ایجاد حساب مدیر — {APP_NAME_FA}")
        layout = QVBoxLayout(self)
        hint = QLabel("این اولین اجرای برنامه است. یک حساب مدیر بسازید تا وارد شوید.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.display_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("نام کاربری", self.username_edit)
        form.addRow("نام نمایشی", self.display_edit)
        form.addRow("رمز عبور", self.password_edit)
        form.addRow("تکرار رمز عبور", self.confirm_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("ساخت حساب")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._add_connection_row(layout)
        self.username_edit.setFocus()

    def _add_connection_row(self, layout) -> None:
        conn = QPushButton("تنظیمات اتصال")
        conn.setFlat(True)
        conn.clicked.connect(self._open_connection)
        row = QHBoxLayout()
        row.addWidget(conn)
        row.addStretch()
        layout.addLayout(row)

    def _open_connection(self) -> None:
        from app.ui.connection_dialog import ConnectionDialog

        ConnectionDialog(self.ctx.config, self).exec()

    def accept(self) -> None:
        if self._first_run:
            self._accept_first_run()
        else:
            self._accept_login()

    def _accept_login(self) -> None:
        with self.ctx.session() as db:
            user = auth_service.authenticate(db, self.username_edit.text(), self.password_edit.text())
            if user is None:
                QMessageBox.warning(self, APP_NAME_FA, "نام کاربری یا رمز عبور اشتباه است.")
                self.password_edit.clear()
                self.password_edit.setFocus()
                return
            self.user_id = user.id
            self.username = user.username
            self.display_name = user.display_name
            self.is_admin = user.is_admin
            self.role = user.role
        super().accept()

    def _accept_first_run(self) -> None:
        if self.password_edit.text() != self.confirm_edit.text():
            QMessageBox.warning(self, APP_NAME_FA, "رمز عبور و تکرار آن یکسان نیستند.")
            return
        try:
            with self.ctx.session() as db:
                user = auth_service.create_user(
                    db,
                    username=self.username_edit.text(),
                    display_name=self.display_edit.text(),
                    password=self.password_edit.text(),
                    is_admin=True,
                    role=UserRole.ADMIN,
                )
                db.flush()
                self.user_id = user.id
                self.username = user.username
                self.display_name = user.display_name
                self.is_admin = True
                self.role = UserRole.ADMIN
        except LedgerError as exc:
            QMessageBox.warning(self, APP_NAME_FA, str(exc))
            return
        super().accept()
