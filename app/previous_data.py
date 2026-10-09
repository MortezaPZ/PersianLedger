"""Copy a previous portable data folder into a new install once."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def default_desktop_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    for folder in (home / "Desktop", home / "OneDrive" / "Desktop"):
        if folder.is_dir():
            roots.append(folder)
    public_desktop = Path(os.environ.get("PUBLIC", "")) / "Desktop"
    if public_desktop.is_dir() and public_desktop not in roots:
        roots.append(public_desktop)
    return roots


def find_previous_ledger(roots: list[Path], ignore_dir: Path | None = None) -> Path | None:
    """Return the newest ledger.sqlite3 that sits in a previous program folder."""
    ignore = ignore_dir.resolve() if ignore_dir else None
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        direct = root / "PersianLedger" / "data" / "ledger.sqlite3"
        candidates = [direct]
        try:
            children = list(root.iterdir())
        except OSError:
            children = []
        for child in children:
            if not child.is_dir():
                continue
            ledger = child / "data" / "ledger.sqlite3"
            exe = child / "PersianLedger.exe"
            if ledger.is_file() and exe.is_file():
                candidates.append(ledger)
        for ledger in candidates:
            if not ledger.is_file():
                continue
            if ignore is not None and ledger.parent.resolve() == ignore:
                continue
            found.append(ledger)
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def recall_previous_data(dest_dir: Path, roots: list[Path]) -> Path | None:
    """Copy the previous data folder when this install does not have a ledger yet."""
    dest_dir = Path(dest_dir)
    if (dest_dir / "ledger.sqlite3").exists():
        return None
    source = find_previous_ledger(roots, ignore_dir=dest_dir)
    if source is None:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    origin = source.parent
    for item in origin.iterdir():
        target = dest_dir / item.name
        if item.resolve() == target.resolve():
            continue
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return source
