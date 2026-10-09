from pathlib import Path

from app.previous_data import find_previous_ledger, recall_previous_data


def test_recall_copies_previous_folder_once(tmp_path: Path) -> None:
    previous = tmp_path / "Desktop" / "PersianLedger"
    data = previous / "data"
    data.mkdir(parents=True)
    (previous / "PersianLedger.exe").write_bytes(b"exe")
    (data / "ledger.sqlite3").write_bytes(b"ledger")
    (data / "note.txt").write_text("keep", encoding="utf-8")
    dest = tmp_path / "ProgramData" / "PersianLedger"
    copied = recall_previous_data(dest, [tmp_path / "Desktop"])
    assert copied == data / "ledger.sqlite3"
    assert (dest / "ledger.sqlite3").read_bytes() == b"ledger"
    assert (dest / "note.txt").read_text(encoding="utf-8") == "keep"
    (data / "ledger.sqlite3").write_bytes(b"newer")
    assert recall_previous_data(dest, [tmp_path / "Desktop"]) is None
    assert (dest / "ledger.sqlite3").read_bytes() == b"ledger"


def test_recall_ignores_the_destination_folder(tmp_path: Path) -> None:
    dest = tmp_path / "Desktop" / "PersianLedger" / "data"
    dest.mkdir(parents=True)
    assert find_previous_ledger([tmp_path / "Desktop"], ignore_dir=dest) is None
