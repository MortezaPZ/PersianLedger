from __future__ import annotations

from pathlib import Path

from app.config import AppConfig, load, save


def test_dark_mode_roundtrip(tmp_path: Path):
    ini = tmp_path / "config.ini"
    cfg = AppConfig(data_dir=tmp_path, sqlite_path=tmp_path / "ledger.sqlite3", dark_mode=True)
    save(cfg, ini)
    loaded = load(ini)
    assert loaded.dark_mode is True
    loaded.dark_mode = False
    save(loaded, ini)
    assert load(ini).dark_mode is False
