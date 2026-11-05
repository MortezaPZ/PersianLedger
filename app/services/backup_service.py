"""Backup and restore of the whole ledger.

The database is one SQLite file, so a backup is a consistent copy of that file.
SQLite's online backup API is used rather than a plain file copy so committed
WAL content is included in the standalone destination.
"""
from __future__ import annotations

import datetime as _dt
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from app.config import AppConfig
from app.domain.errors import LedgerError
from app.db.sqlite_snapshot import replace_database, snapshot_engine, snapshot_file


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
    return f"{prefix}-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3"


def remember_backup(cfg: AppConfig, path: Path) -> None:
    cfg.last_backup_path = Path(path).resolve()
    if cfg.configured:
        from app import config as config_module

        config_module.save(cfg)


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
    try:
        snapshot_engine(engine, dest)
    except Exception as exc:
        raise BackupError("ساخت فایل پشتیبان انجام نشد.") from exc
    if not dest.is_file():
        raise BackupError(f"فایل پشتیبان در این مسیر ساخته نشد:\n{dest}")
    remember_backup(cfg, dest)
    stat = dest.stat()
    return BackupInfo(dest, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime))


def inspect(path: Path) -> BackupInfo:
    """Refuse anything that is not a readable ledger before we overwrite live data."""
    source = Path(path)
    if not source.is_file():
        raise BackupError(f"فایل پشتیبان پیدا نشد:\n{source}")
    try:
        conn = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
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
    live = Path(cfg.sqlite_path).resolve()
    safety = cfg.backup_dir / suggested_name("pre-restore")
    staged = live.with_name(f".{live.name}.restore-{uuid.uuid4().hex}.sqlite3")
    if live.exists():
        try:
            snapshot_engine(engine, safety)
        except Exception as exc:
            raise BackupError("تهیه نسخه ایمنی از دیتابیس فعلی انجام نشد؛ بازیابی لغو شد.") from exc
    try:
        snapshot_file(source, staged)
        conn = sqlite3.connect(staged)
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise BackupError("فایل پشتیبان آسیب‌دیده است؛ دیتابیس فعلی دست‌نخورده ماند.")
            documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            posted = conn.execute("SELECT COUNT(*) FROM documents WHERE status='POSTED'").fetchone()[0]
            accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            tafsilis = conn.execute("SELECT COUNT(*) FROM tafsilis").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError("فایل پشتیبان آسیب‌دیده است؛ دیتابیس فعلی دست‌نخورده ماند.") from exc
    except Exception as exc:
        if isinstance(exc, BackupError):
            raise
        raise BackupError("خواندن فایل پشتیبان انجام نشد؛ دیتابیس فعلی دست‌نخورده ماند.") from exc

    # Migrate the staged copy. The current database remains untouched until the
    # backup has passed validation and every migration has committed.
    from dataclasses import replace

    from app.db import engine as engine_module
    from app.db import migrate

    staged_cfg = replace(cfg, sqlite_path=staged)
    staged_engine = engine_module.build_engine(staged_cfg.database_url())
    try:
        migrate.upgrade_to_head(staged_engine, staged_cfg)
    except Exception as exc:
        staged_engine.dispose()
        staged.unlink(missing_ok=True)
        Path(str(staged) + "-wal").unlink(missing_ok=True)
        Path(str(staged) + "-shm").unlink(missing_ok=True)
        Path(str(staged) + "-journal").unlink(missing_ok=True)
        raise BackupError(
            f"ساختار فایل پشتیبان به‌روزرسانی نشد؛ دیتابیس فعلی تغییر نکرد.\n{exc}"
        ) from exc
    staged_engine.dispose()

    # Leave the staged SQLite file in rollback-journal mode so no stale WAL can
    # be mistaken for pages from the database it replaces.
    conn = sqlite3.connect(staged)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
    finally:
        conn.close()

    engine.dispose()
    try:
        replace_database(staged, live)
    except PermissionError as exc:
        raise BackupError(
            "فایل دیتابیس توسط برنامه دیگری در حال استفاده است؛ دیتابیس فعلی حفظ شد. "
            "همه پنجره‌های دفتر مالی را ببندید و بازیابی را دوباره انجام دهید."
        ) from exc
    except OSError as exc:
        raise BackupError(f"جایگزینی دیتابیس انجام نشد؛ دیتابیس فعلی حفظ شد.\n{exc}") from exc
    remember_backup(cfg, Path(source))
    return RestoreResult(safety, documents, posted, accounts, tafsilis)


def list_backups(cfg: AppConfig) -> list[BackupInfo]:
    paths_to_scan = {
        Path(cfg.backup_dir).resolve(),
        (Path(cfg.data_dir) / "backups").resolve(),
    }
    if cfg.last_backup_path is not None:
        paths_to_scan.add(Path(cfg.last_backup_path).expanduser().resolve().parent)
    found: dict[Path, BackupInfo] = {}
    for folder in paths_to_scan:
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.suffix.lower() not in {".sqlite3", ".pgdump"}:
                continue
            resolved = path.resolve()
            stat = resolved.stat()
            found[resolved] = BackupInfo(
                resolved, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)
            )
    if cfg.backend == "postgresql":
        from app.services import server_backup

        for item in server_backup.list_backups(cfg):
            found[item.path.resolve()] = item
    return sorted(found.values(), key=lambda item: (item.taken_at, item.path.name), reverse=True)
