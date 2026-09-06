from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from app import config as config_module
from app.config import AppConfig
from app.db import engine as engine_module
from app.domain.errors import LedgerError
from app.ui.widgets import fields
from app.version import APP_NAME_FA


class ConnectionDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None, *, save_path: Path | None = None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.save_path = save_path
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle("تنظیمات اتصال به دیتابیس")
        layout = QVBoxLayout(self)
        self.radio_sqlite = QRadioButton("فایل محلی (SQLite)")
        self.radio_pg = QRadioButton("سرور شبکه (PostgreSQL)")
        layout.addWidget(self.radio_sqlite)
        layout.addWidget(self.radio_pg)
        self.sqlite_group = QGroupBox("SQLite")
        sqlite_form = QHBoxLayout(self.sqlite_group)
        self.sqlite_path = QLineEdit(str(cfg.sqlite_path or ""))
        pick = QPushButton("انتخاب…")
        pick.clicked.connect(self._pick_sqlite)
        sqlite_form.addWidget(self.sqlite_path)
        sqlite_form.addWidget(pick)
        layout.addWidget(self.sqlite_group)
        self.pg_group = QGroupBox("PostgreSQL")
        form = QFormLayout(self.pg_group)
        self.pg_host = QLineEdit(cfg.pg_host)
        self.pg_port = QSpinBox()
        self.pg_port.setRange(1, 65535)
        self.pg_port.setValue(cfg.pg_port or 5432)
        self.pg_database = QLineEdit(cfg.pg_database)
        self.pg_user = QLineEdit(cfg.pg_user)
        self.pg_password = QLineEdit(cfg.pg_password)
        self.pg_password.setEchoMode(QLineEdit.Password)
        self.pg_ssl = QComboBox()
        self.pg_ssl.addItems(["disable", "prefer", "require"])
        idx = self.pg_ssl.findText(cfg.pg_sslmode or "prefer")
        self.pg_ssl.setCurrentIndex(max(idx, 0))
        form.addRow("نشانی سرور", self.pg_host)
        form.addRow("پورت", self.pg_port)
        form.addRow("نام دیتابیس", self.pg_database)
        form.addRow("نام کاربری", self.pg_user)
        form.addRow("رمز عبور", self.pg_password)
        form.addRow("SSL", self.pg_ssl)
        layout.addWidget(self.pg_group)
        test = QPushButton("آزمایش اتصال")
        test.clicked.connect(self._test)
        layout.addWidget(test)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.radio_sqlite.toggled.connect(self._sync_enabled)
        if cfg.backend == "postgresql":
            self.radio_pg.setChecked(True)
        else:
            self.radio_sqlite.setChecked(True)
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        sqlite = self.radio_sqlite.isChecked()
        self.sqlite_group.setEnabled(sqlite)
        self.pg_group.setEnabled(not sqlite)

    def _pick_sqlite(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "فایل دیتابیس", self.sqlite_path.text(), "SQLite (*.sqlite3)")
        if path:
            self.sqlite_path.setText(path)

    def candidate(self) -> AppConfig:
        cfg = AppConfig(
            backend="postgresql" if self.radio_pg.isChecked() else "sqlite",
            sqlite_path=Path(self.sqlite_path.text()) if self.sqlite_path.text() else self.cfg.sqlite_path,
            pg_host=self.pg_host.text().strip(),
            pg_port=self.pg_port.value(),
            pg_database=self.pg_database.text().strip(),
            pg_user=self.pg_user.text().strip(),
            pg_password=self.pg_password.text(),
            pg_sslmode=self.pg_ssl.currentText(),
            pg_connect_timeout=self.cfg.pg_connect_timeout,
            data_dir=self.cfg.data_dir,
            dark_mode=self.cfg.dark_mode,
            pg_bin_dir=self.cfg.pg_bin_dir,
            server_backup_dir=self.cfg.server_backup_dir,
        )
        return cfg

    def _test(self) -> None:
        try:
            version = engine_module.test_connection(self.candidate().database_url())
            QMessageBox.information(self, APP_NAME_FA, f"اتصال برقرار شد.\n{version}")
        except LedgerError as exc:
            QMessageBox.warning(self, APP_NAME_FA, str(exc))

    def _save(self) -> None:
        cfg = self.candidate()
        config_module.save(cfg, path=self.save_path)
        QMessageBox.information(
            self,
            APP_NAME_FA,
            "تنظیمات ذخیره شد. برنامه را دوباره اجرا کنید تا به دیتابیس جدید متصل شود.",
        )
        self.accept()
