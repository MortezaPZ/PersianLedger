from __future__ import annotations

import os

from app import paths
from app.config import AppConfig
from app.services import backup_service


def test_installed_build_uses_visible_documents_backup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "is_portable", lambda: False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    cfg = AppConfig(data_dir=tmp_path / "ProgramData")

    assert cfg.backup_dir == tmp_path / "Documents" / "PersianLedger" / "Backups"


def test_backup_list_includes_recent_custom_and_legacy_locations(tmp_path):
    legacy = tmp_path / "ProgramData" / "PersianLedger"
    visible = tmp_path / "Documents" / "PersianLedger" / "Backups"
    custom = tmp_path / "chosen-folder"
    (legacy / "backups").mkdir(parents=True)
    visible.mkdir(parents=True)
    custom.mkdir()
    (legacy / "backups" / "old.sqlite3").write_bytes(b"old")
    (visible / "new.sqlite3").write_bytes(b"new")
    last = custom / "last.sqlite3"
    last.write_bytes(b"last")
    os.utime(last, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))

    cfg = AppConfig(
        data_dir=legacy,
        backup_dir_override=visible,
        last_backup_path=last,
    )

    backups = backup_service.list_backups(cfg)
    listed = {item.path.resolve() for item in backups}
    assert listed == {
        (legacy / "backups" / "old.sqlite3").resolve(),
        (visible / "new.sqlite3").resolve(),
        last.resolve(),
    }
    assert backups[0].path == last.resolve()
