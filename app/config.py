"""Application configuration held in an ini file next to the user profile."""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from app import paths


@dataclass
class AppConfig:
    backend: str = "sqlite"
    sqlite_path: Path | None = None
    pg_host: str = ""
    pg_port: int = 5432
    pg_database: str = ""
    pg_user: str = ""
    pg_password: str = ""
    data_dir: Path | None = None
    dark_mode: bool = False
    configured: bool = False

    def __post_init__(self) -> None:
        if self.data_dir is None:
            self.data_dir = paths.default_data_dir()
        if self.sqlite_path is None:
            self.sqlite_path = self.data_dir / "ledger.sqlite3"

    @property
    def attachments_dir(self) -> Path:
        return paths.ensure_dir(Path(self.data_dir) / "attachments")

    @property
    def backup_dir(self) -> Path:
        return paths.ensure_dir(Path(self.data_dir) / "backups")

    @property
    def export_dir(self) -> Path:
        return paths.ensure_dir(Path(self.data_dir) / "exports")

    def database_url(self) -> str:
        if self.backend == "postgresql":
            return (
                f"postgresql+psycopg://{quote_plus(self.pg_user)}:"
                f"{quote_plus(self.pg_password)}@{self.pg_host}:{self.pg_port}/"
                f"{self.pg_database}"
            )
        return f"sqlite:///{Path(self.sqlite_path).as_posix()}"

    def describe(self) -> str:
        if self.backend == "postgresql":
            return f"PostgreSQL — {self.pg_host}:{self.pg_port}/{self.pg_database}"
        return f"SQLite — {self.sqlite_path}"


def load(path: Path | None = None) -> AppConfig:
    path = path or paths.config_file()
    cfg = AppConfig()
    if not path.exists():
        return cfg
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    db = parser["database"] if parser.has_section("database") else {}
    cfg.backend = db.get("backend", "sqlite")
    if db.get("data_dir"):
        cfg.data_dir = paths.ensure_dir(Path(db["data_dir"]))
    if db.get("sqlite_path"):
        cfg.sqlite_path = Path(db["sqlite_path"])
    else:
        cfg.sqlite_path = Path(cfg.data_dir) / "ledger.sqlite3"
    cfg.pg_host = db.get("pg_host", "")
    cfg.pg_port = int(db.get("pg_port", 5432) or 5432)
    cfg.pg_database = db.get("pg_database", "")
    cfg.pg_user = db.get("pg_user", "")
    cfg.pg_password = db.get("pg_password", "")
    ui = parser["ui"] if parser.has_section("ui") else {}
    cfg.dark_mode = ui.get("dark_mode", "false").strip().lower() in {"1", "true", "yes"}
    cfg.configured = True
    return cfg


def save(cfg: AppConfig, path: Path | None = None) -> None:
    path = path or paths.config_file()
    parser = configparser.ConfigParser()
    parser["database"] = {
        "backend": cfg.backend,
        "data_dir": str(cfg.data_dir),
        "sqlite_path": str(cfg.sqlite_path),
        "pg_host": cfg.pg_host,
        "pg_port": str(cfg.pg_port),
        "pg_database": cfg.pg_database,
        "pg_user": cfg.pg_user,
        "pg_password": cfg.pg_password,
    }
    parser["ui"] = {
        "dark_mode": "true" if cfg.dark_mode else "false",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    cfg.configured = True
