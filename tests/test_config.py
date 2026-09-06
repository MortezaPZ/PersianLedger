from __future__ import annotations

from pathlib import Path

import keyring
from keyring.backend import KeyringBackend

from app.config import AppConfig, load, save


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_dark_mode_roundtrip(tmp_path: Path):
    ini = tmp_path / "config.ini"
    cfg = AppConfig(data_dir=tmp_path, sqlite_path=tmp_path / "ledger.sqlite3", dark_mode=True)
    save(cfg, ini)
    loaded = load(ini)
    assert loaded.dark_mode is True
    loaded.dark_mode = False
    save(loaded, ini)
    assert load(ini).dark_mode is False


def test_pg_url_contains_sslmode_and_application_name():
    cfg = AppConfig(
        backend="postgresql",
        pg_host="127.0.0.1",
        pg_port=5432,
        pg_database="ledger",
        pg_user="u",
        pg_password="p",
        pg_sslmode="prefer",
    )
    url = cfg.database_url()
    assert "sslmode=prefer" in url
    assert "application_name=PersianLedger" in url
    assert cfg.is_server() is True


def test_keyring_roundtrip_leaves_ini_password_empty(tmp_path: Path):
    keyring.set_keyring(MemoryKeyring())
    ini = tmp_path / "config.ini"
    cfg = AppConfig(
        data_dir=tmp_path,
        sqlite_path=tmp_path / "ledger.sqlite3",
        backend="postgresql",
        pg_host="localhost",
        pg_port=5432,
        pg_database="persianledger",
        pg_user="app",
        pg_password="secret",
    )
    save(cfg, ini)
    text = ini.read_text(encoding="utf-8")
    assert "pg_password" in text
    assert "secret" not in text
    loaded = load(ini)
    assert loaded.pg_password == "secret"
