"""Backup and restore of the whole ledger.

The database is one SQLite file, so a backup is a consistent copy of that file.
`VACUUM INTO` is used rather than a plain copy because it collapses the WAL into
the destination, giving a file that opens cleanly on its own.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text

from app.config import AppConfig
from app.domain.errors import LedgerError


class BackupError(LedgerError):
    pass


@dataclass
class BackupInfo:
    path: Path
    size_bytes: int
    taken_at: _dt.datetime

    @property
    def size_text(self) -> str:
        kb = self.size_bytes / 1024
        if kb < 1024:
            return f"{kb:.0f} کیلوبایت"
        return f"{kb / 1024:.1f} مگابایت"


def suggested_name(prefix: str = "backup") -> str:
    return f"{prefix}-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"


def create(engine: Engine, cfg: AppConfig, target: Path | None = None) -> BackupInfo:
    """Write a self-contained copy of the database to `target`."""
    if cfg.backend != "sqlite":
        raise BackupError(
            "پشتیبان‌گیری از این نوع دیتابیس از داخل برنامه انجام نمی‌شود؛ از ابزار پشتیبان‌گیری سرور استفاده کنید."
        )
    dest = Path(target) if target else cfg.backup_dir / suggested_name()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        with engine.connect() as connection:
            connection.execute(text("VACUUM INTO :path"), {"path": str(dest)})
    except Exception as exc:
        raise BackupError("ساخت فایل پشتیبان انجام نشد.") from exc
    stat = dest.stat()
    return BackupInfo(dest, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime))


def inspect(path: Path) -> BackupInfo:
    """Refuse anything that is not a readable ledger before we overwrite live data."""
    source = Path(path)
    if not source.is_file():
        raise BackupError(f"فایل پشتیبان پیدا نشد:\n{source}")
    try:
        conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        try:
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"این فایل یک دیتابیس معتبر نیست:\n{source}") from exc
    required = {"documents", "document_lines", "accounts", "currencies"}
    if not required.issubset(names):
        raise BackupError("این فایل پشتیبانِ همین برنامه نیست؛ جدول‌های اصلی در آن پیدا نشد.")
    stat = source.stat()
    return BackupInfo(source, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime))


def restore(engine: Engine, cfg: AppConfig, source: Path) -> Path:
    """Replace the live database, keeping a safety copy of what was there.

    Returns the path of the safety copy. The caller must reopen the engine
    afterwards — the file underneath it has changed.
    """
    if cfg.backend != "sqlite":
        raise BackupError("بازیابی فقط برای دیتابیس محلی SQLite در دسترس است.")
    inspect(source)
    live = Path(cfg.sqlite_path)
    safety = cfg.backup_dir / suggested_name("pre-restore")
    if live.exists():
        with engine.connect() as connection:
            connection.execute(text("VACUUM INTO :path"), {"path": str(safety)})
    engine.dispose()
    if live.exists():
        live.unlink()
    shutil.copy2(source, live)
    wal = Path(str(live) + "-wal")
    shm = Path(str(live) + "-shm")
    for extra in (wal, shm):
        if extra.exists():
            extra.unlink()
    return safety


def list_backups(cfg: AppConfig) -> list[BackupInfo]:
    items: list[BackupInfo] = []
    for path in sorted(cfg.backup_dir.glob("*.sqlite3"), reverse=True):
        stat = path.stat()
        items.append(BackupInfo(path, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)))
    return items
