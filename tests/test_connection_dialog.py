from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import keyring
import pytest
from PySide6.QtWidgets import QMessageBox

from app.config import AppConfig
from app.db import engine as engine_module
from app.domain.errors import LedgerError
from app.ui.connection_dialog import ConnectionDialog
from tests.test_config import MemoryKeyring


def test_connection_dialog_toggle_and_save(qapp, tmp_path):
    keyring.set_keyring(MemoryKeyring())
    cfg = AppConfig(data_dir=tmp_path, sqlite_path=tmp_path / "ledger.sqlite3")
    dialog = ConnectionDialog(cfg, save_path=tmp_path / "config.ini")
    assert dialog.sqlite_group.isEnabled()
    assert not dialog.pg_group.isEnabled()
    dialog.radio_pg.setChecked(True)
    assert dialog.pg_group.isEnabled()
    assert not dialog.sqlite_group.isEnabled()
    dialog.pg_host.setText("db.local")
    dialog.pg_database.setText("ledger")
    dialog.pg_user.setText("app")
    dialog.pg_password.setText("hidden")
    with patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
        dialog._save()
    text = (tmp_path / "config.ini").read_text(encoding="utf-8")
    assert "backend = postgresql" in text
    assert "hidden" not in text


def test_test_connection_bogus_url_raises():
    cfg = AppConfig(
        backend="postgresql",
        pg_host="127.0.0.1",
        pg_port=1,
        pg_database="nope",
        pg_user="u",
        pg_password="p",
        pg_connect_timeout=1,
        pg_sslmode="disable",
    )
    with pytest.raises(LedgerError):
        engine_module.test_connection(cfg.database_url())
