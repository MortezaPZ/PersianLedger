"""Consistent SQLite snapshots and safe database-file replacement."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import Engine


def snapshot_engine(engine: Engine, destination: Path) -> Path:
    """Write a standalone, consistent snapshot of an open SQLite engine."""
    raw = engine.raw_connection()
    try:
        source = getattr(raw, "driver_connection", raw)
        return _snapshot_connection(source, destination)
    finally:
        raw.close()


def snapshot_file(source_path: Path, destination: Path) -> Path:
    """Copy a SQLite database, including committed WAL content, via SQLite."""
    source_path = Path(source_path).resolve()
    uri = source_path.as_uri() + "?mode=ro"
    source = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        return _snapshot_connection(source, destination)
    finally:
        source.close()


def _snapshot_connection(source: sqlite3.Connection, destination: Path) -> Path:
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    target: sqlite3.Connection | None = None
    try:
        target = sqlite3.connect(temporary, timeout=30)
        source.backup(target, pages=256, sleep=0.05)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise sqlite3.DatabaseError("SQLite snapshot failed integrity_check")
        target.commit()
        target.close()
        target = None
        os.replace(temporary, destination)
        return destination
    finally:
        if target is not None:
            target.close()
        _remove_sqlite_sidecars(temporary)
        temporary.unlink(missing_ok=True)


def replace_database(staged: Path, destination: Path) -> None:
    """Atomically replace a database and quarantine stale WAL sidecars first."""
    staged = Path(staged).resolve()
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    quarantine = Path(tempfile.mkdtemp(prefix=f".{destination.name}.sidecars-", dir=destination.parent))
    moved: list[tuple[Path, Path]] = []
    replaced = False
    try:
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(destination) + suffix)
            if sidecar.exists():
                held = quarantine / sidecar.name
                os.replace(sidecar, held)
                moved.append((held, sidecar))
        os.replace(staged, destination)
        replaced = True
    except Exception:
        rollback_error: Exception | None = None
        for held, sidecar in reversed(moved):
            try:
                if held.exists():
                    os.replace(held, sidecar)
            except Exception as exc:  # Preserve the quarantined file for manual recovery.
                rollback_error = rollback_error or exc
        if rollback_error is not None:
            raise OSError(f"Could not restore database sidecars; recovery files are in {quarantine}") from rollback_error
        raise
    finally:
        if replaced or not any(held.exists() for held, _ in moved):
            shutil.rmtree(quarantine, ignore_errors=True)
        _remove_sqlite_sidecars(staged)
        staged.unlink(missing_ok=True)


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)
