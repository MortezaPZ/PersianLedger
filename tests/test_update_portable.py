"""The portable updater replaces program files and leaves data bytes unchanged."""
from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "packaging" / "update_portable.ps1"


def _layout(folder: Path, exe_text: str, internal_text: str) -> None:
    folder.mkdir()
    (folder / "PersianLedger.exe").write_text(exe_text, encoding="utf-8")
    internal = folder / "_internal"
    internal.mkdir()
    (internal / "marker.txt").write_text(internal_text, encoding="utf-8")
    (folder / "portable.txt").write_text("portable", encoding="utf-8")


def _seed(data: Path) -> None:
    data.mkdir()
    db = data / "ledger.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, description TEXT)")
    conn.execute("INSERT INTO users (username) VALUES ('morteza')")
    conn.execute("INSERT INTO documents (description) VALUES ('home-invoice')")
    conn.commit()
    conn.close()
    (data / "note.txt").write_text("keep-me", encoding="utf-8")


def _run(install: Path, update: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-InstallDir",
            str(install),
            "-UpdateDir",
            str(update),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_update_replaces_program_and_keeps_ledger(tmp_path: Path) -> None:
    install = tmp_path / "install"
    update = tmp_path / "update"
    _layout(install, "old-exe", "old-internal")
    _layout(update, "new-exe", "new-internal")
    _seed(install / "data")
    (update / "data").mkdir()
    (update / "data" / "ledger.sqlite3").write_text("empty-new-db", encoding="utf-8")

    result = _run(install, update)
    assert result.returncode == 0, result.stderr

    assert (install / "PersianLedger.exe").read_text(encoding="utf-8") == "new-exe"
    assert (install / "_internal" / "marker.txt").read_text(encoding="utf-8") == "new-internal"
    assert not (install / "_internal.prev").exists()
    assert (install / "data" / "note.txt").read_text(encoding="utf-8") == "keep-me"

    conn = sqlite3.connect(install / "data" / "ledger.sqlite3")
    try:
        user = conn.execute("SELECT username FROM users").fetchone()[0]
        doc = conn.execute("SELECT description FROM documents").fetchone()[0]
    finally:
        conn.close()
    assert user == "morteza"
    assert doc == "home-invoice"


def test_update_refuses_when_program_files_missing(tmp_path: Path) -> None:
    install = tmp_path / "install"
    update = tmp_path / "update"
    _layout(install, "old-exe", "old-internal")
    update.mkdir()
    result = _run(install, update)
    assert result.returncode != 0
    assert (install / "PersianLedger.exe").read_text(encoding="utf-8") == "old-exe"


def test_update_refuses_nested_folders(tmp_path: Path) -> None:
    install = tmp_path / "install"
    update = install / "new"
    _layout(install, "old-exe", "old-internal")
    _layout(update, "new-exe", "new-internal")
    _seed(install / "data")
    result = _run(install, update)
    assert result.returncode != 0
    assert (install / "data" / "note.txt").read_text(encoding="utf-8") == "keep-me"
    assert (install / "PersianLedger.exe").read_text(encoding="utf-8") == "old-exe"


def test_update_failure_restores_previous_program(tmp_path: Path) -> None:
    install = tmp_path / "install"
    update = tmp_path / "update"
    _layout(install, "old-exe", "old-internal")
    _layout(update, "new-exe", "new-internal")
    _seed(install / "data")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-InstallDir",
            str(install),
            "-UpdateDir",
            str(update),
            "-SimulateFailure",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert (install / "PersianLedger.exe").read_text(encoding="utf-8") == "old-exe"
    assert (install / "_internal" / "marker.txt").read_text(encoding="utf-8") == "old-internal"
    assert not (install / "PersianLedger.exe.prev").exists()
    conn = sqlite3.connect(install / "data" / "ledger.sqlite3")
    try:
        assert conn.execute("SELECT username FROM users").fetchone()[0] == "morteza"
    finally:
        conn.close()
