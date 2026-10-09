"""Backup and restore of the whole ledger.

The database is one SQLite file, so a backup is a consistent copy of that file.
`VACUUM INTO` is used rather than a plain copy because it collapses the WAL into
the destination, giving a file that opens cleanly on its own.
"""
from __future__ import annotations

import datetime as _dt
import gc
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


@dataclass
class RestoreResult:
    safety_path: Path
    documents: int
    posted: int
    accounts: int
    tafsilis: int


def suggested_name(prefix: str = "backup") -> str:
    return f"{prefix}-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"


def create(engine: Engine, cfg: AppConfig, target: Path | None = None, user_id: int | None = None) -> BackupInfo:
    """Write a self-contained copy of the database to `target`."""
    if cfg.backend == "postgresql":
        from app.services import server_backup

        return server_backup.create(cfg, user_id, target)
    from app.domain.permissions import Perm
    from app.services import auth_service
    from sqlalchemy.orm import Session as SASession

    with SASession(engine) as db:
        auth_service.require(db, user_id, Perm.BACKUP)
    dest = Path(target).resolve() if target else (Path(cfg.backup_dir) / suggested_name()).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        with engine.connect() as connection:
            escaped = str(dest).replace("'", "''")
            connection.exec_driver_sql(f"VACUUM INTO '{escaped}'")
    except Exception as exc:
        raise BackupError("ساخت فایل پشتیبان انجام نشد.") from exc
    if not dest.is_file():
        raise BackupError(f"فایل پشتیبان در این مسیر ساخته نشد:\n{dest}")
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


def restore(engine: Engine, cfg: AppConfig, source: Path, user_id: int | None = None) -> RestoreResult:
    """Replace the live database, keeping a safety copy of what was there.

    Returns counts from the restored file. The caller must reopen the engine
    afterwards — the file underneath it has changed.
    """
    from app.domain.permissions import Perm
    from app.services import auth_service
    from sqlalchemy.orm import Session as SASession

    if cfg.backend == "postgresql":
        from app.services import server_backup

        return server_backup.restore(cfg, user_id, source)
    with SASession(engine) as db:
        auth_service.require(db, user_id, Perm.RESTORE)
    inspect(source)
    live = Path(cfg.sqlite_path)
    safety = cfg.backup_dir / suggested_name("pre-restore")
    if live.exists():
        with engine.connect() as connection:
            connection.execute(text("VACUUM INTO :path"), {"path": str(safety)})
    engine.dispose()
    gc.collect()
    if live.exists():
        try:
            live.unlink()
        except PermissionError as exc:
            raise BackupError(
                "فایل دیتابیس در حال استفاده است. برنامه را ببندید و دوباره باز کنید، سپس بازیابی را تکرار کنید."
            ) from exc
    shutil.copy2(source, live)
    wal = Path(str(live) + "-wal")
    shm = Path(str(live) + "-shm")
    for extra in (wal, shm):
        if extra.exists():
            extra.unlink()
    try:
        conn = sqlite3.connect(f"file:{live.as_posix()}?mode=ro", uri=True)
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise BackupError("فایل پشتیبان آسیب‌دیده است؛ دیتابیس قبلی دست‌نخورده ماند.")
            documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            posted = conn.execute("SELECT COUNT(*) FROM documents WHERE status='POSTED'").fetchone()[0]
            accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            tafsilis = conn.execute("SELECT COUNT(*) FROM tafsilis").fetchone()[0]
        finally:
            conn.close()
    except BackupError:
        _put_safety_back(live, safety)
        raise
    except sqlite3.DatabaseError as exc:
        _put_safety_back(live, safety)
        raise BackupError("فایل پشتیبان آسیب‌دیده است؛ دیتابیس قبلی دست‌نخورده ماند.") from exc
    _upgrade_restored_file(cfg, live, safety)
    return RestoreResult(safety, documents, posted, accounts, tafsilis)


def _upgrade_restored_file(cfg: AppConfig, live: Path, safety: Path) -> None:
    """Bring an older backup up to the schema this build understands.

    If that migration fails, the database that was live before the restore is
    put back. The caller must not be left on a half-upgraded file.
    """
    from app.db import engine as engine_module
    from app.db import migrate

    fresh = engine_module.build_engine(cfg.database_url())
    try:
        migrate.upgrade_to_head(fresh, cfg)
    except Exception as exc:
        fresh.dispose()
        _put_safety_back(live, safety)
        raise BackupError(
            "به‌روزرسانی ساختار فایل پشتیبان انجام نشد؛ دیتابیس قبلی دست‌نخورده ماند."
        ) from exc
    fresh.dispose()


def _put_safety_back(live: Path, safety: Path) -> None:
    if live.exists():
        live.unlink(missing_ok=True)
    if safety.exists():
        shutil.copy2(safety, live)


def list_backups(cfg: AppConfig) -> list[BackupInfo]:
    items: list[BackupInfo] = []
    for path in sorted(cfg.backup_dir.glob("*.sqlite3"), reverse=True):
        stat = path.stat()
        items.append(BackupInfo(path, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)))
    if cfg.backend == "postgresql":
        from app.services import server_backup

        items.extend(server_backup.list_backups(cfg))
    else:
        for path in sorted(cfg.backup_dir.glob("*.pgdump"), reverse=True):
            stat = path.stat()
            items.append(BackupInfo(path, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)))
    return items
