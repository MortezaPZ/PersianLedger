from __future__ import annotations

import datetime as _dt
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import AppConfig
from app.domain.permissions import Perm
from app.services import auth_service
from app.services.backup_service import BackupError, BackupInfo, RestoreResult, suggested_name


def find_pg_tool(cfg: AppConfig, name: str) -> Path:
    exe = f"{name}.exe" if os.name == "nt" else name
    if cfg.pg_bin_dir:
        candidate = Path(cfg.pg_bin_dir) / exe
        if candidate.is_file():
            return candidate
    which = shutil.which(name) or shutil.which(exe)
    if which:
        return Path(which)
    root = Path(r"C:\Program Files\PostgreSQL")
    if root.is_dir():
        for folder in sorted(root.glob("*/bin"), reverse=True):
            candidate = folder / exe
            if candidate.is_file():
                return candidate
    portable = Path(r"F:\tools\pgsql-extract\pgsql\bin") / exe
    if portable.is_file():
        return portable
    raise BackupError("ابزار pg_dump پیدا نشد. مسیر پوشه bin پستگرس را در تنظیمات اتصال وارد کنید.")


def _libpq_url(cfg: AppConfig) -> str:
    from urllib.parse import quote_plus

    return (
        f"postgresql://{quote_plus(cfg.pg_user)}:{quote_plus(cfg.pg_password)}"
        f"@{cfg.pg_host}:{cfg.pg_port}/{cfg.pg_database}"
    )


def _run(cfg: AppConfig, args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PGPASSWORD"] = cfg.pg_password or ""
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(args, capture_output=True, timeout=timeout, env=env, creationflags=flags)


def create(cfg: AppConfig, user_id: int | None, target: Path | None = None) -> BackupInfo:
    engine = create_engine(cfg.database_url(), future=True)
    try:
        with Session(engine) as db:
            auth_service.require(db, user_id, Perm.BACKUP)
    finally:
        engine.dispose()
    dump = find_pg_tool(cfg, "pg_dump")
    folder = Path(cfg.server_backup_dir or cfg.backup_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = Path(target) if target else folder / f"backup-{cfg.pg_host}-{cfg.pg_database}-{stamp}.pgdump"
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = _run(
        cfg,
        [
            str(dump),
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(dest),
            "--dbname",
            _libpq_url(cfg),
        ],
    )
    if result.returncode != 0:
        raise BackupError((result.stderr or result.stdout or b"").decode("utf-8", "replace") or "pg_dump failed")
    stat = dest.stat()
    return BackupInfo(dest, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime))


def restore(cfg: AppConfig, user_id: int | None, source: Path) -> RestoreResult:
    engine = create_engine(cfg.database_url(), future=True)
    try:
        with Session(engine) as db:
            auth_service.require(db, user_id, Perm.RESTORE)
            n = db.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND application_name = 'PersianLedger'"
                )
            ).scalar_one()
            if n:
                raise BackupError(f"{n} کاربر دیگر به دیتابیس متصل است. برای بازیابی همه باید از برنامه خارج شوند.")
    finally:
        engine.dispose()
    safety = create(cfg, user_id)
    restore_bin = find_pg_tool(cfg, "pg_restore")
    result = _run(
        cfg,
        [
            str(restore_bin),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            _libpq_url(cfg),
            str(source),
        ],
    )
    if result.returncode != 0:
        raise BackupError((result.stderr or result.stdout or b"").decode("utf-8", "replace") or "pg_restore failed")
    engine = create_engine(cfg.database_url(), future=True)
    try:
        with engine.connect() as conn:
            documents = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()
            posted = conn.execute(text("SELECT COUNT(*) FROM documents WHERE status='POSTED'")).scalar_one()
            accounts = conn.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one()
            tafsilis = conn.execute(text("SELECT COUNT(*) FROM tafsilis")).scalar_one()
    finally:
        engine.dispose()
    return RestoreResult(safety.path, documents, posted, accounts, tafsilis)


def list_backups(cfg: AppConfig) -> list[BackupInfo]:
    folder = Path(cfg.server_backup_dir or cfg.backup_dir)
    items: list[BackupInfo] = []
    if not folder.is_dir():
        return items
    for path in sorted(folder.glob("*.pgdump"), reverse=True):
        stat = path.stat()
        items.append(BackupInfo(path, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)))
    return items
