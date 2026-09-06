"""Application configuration held in an ini file next to the user profile."""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from app import paths

KEYRING_SERVICE = "PersianLedger"


@dataclass
class AppConfig:
    backend: str = "sqlite"
    sqlite_path: Path | None = None
    pg_host: str = ""
    pg_port: int = 5432
    pg_database: str = ""
    pg_user: str = ""
    pg_password: str = ""
    pg_sslmode: str = "prefer"
    pg_connect_timeout: int = 5
    attachments_dir_override: Path | None = None
    pg_bin_dir: Path | None = None
    server_backup_dir: Path | None = None
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

    def is_server(self) -> bool:
        return self.backend == "postgresql"

    def database_url(self) -> str:
        if self.backend == "postgresql":
            return (
                f"postgresql+psycopg://{quote_plus(self.pg_user)}:"
                f"{quote_plus(self.pg_password)}@{self.pg_host}:{self.pg_port}/"
                f"{self.pg_database}?sslmode={self.pg_sslmode}"
                f"&connect_timeout={self.pg_connect_timeout}"
                f"&application_name=PersianLedger"
            )
        return f"sqlite:///{Path(self.sqlite_path).as_posix()}"

    def describe(self) -> str:
        if self.backend == "postgresql":
            return f"PostgreSQL — {self.pg_host}:{self.pg_port}/{self.pg_database}"
        return f"SQLite — {self.sqlite_path}"


def _keyring_username(cfg: AppConfig) -> str:
    return f"{cfg.pg_user}@{cfg.pg_host}:{cfg.pg_port}/{cfg.pg_database}"


def store_password(cfg: AppConfig) -> bool:
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, _keyring_username(cfg), cfg.pg_password or "")
        return True
    except Exception:
        return False


def load_password(cfg: AppConfig) -> None:
    try:
        import keyring

        value = keyring.get_password(KEYRING_SERVICE, _keyring_username(cfg))
        if value:
            cfg.pg_password = value
    except Exception:
        return


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
    cfg.pg_sslmode = db.get("pg_sslmode", "prefer") or "prefer"
    cfg.pg_connect_timeout = int(db.get("pg_connect_timeout", 5) or 5)
    if db.get("attachments_dir_override"):
        cfg.attachments_dir_override = Path(db["attachments_dir_override"])
    server = parser["server"] if parser.has_section("server") else {}
    if server.get("pg_bin_dir"):
        cfg.pg_bin_dir = Path(server["pg_bin_dir"])
    if server.get("server_backup_dir"):
        cfg.server_backup_dir = Path(server["server_backup_dir"])
    ui = parser["ui"] if parser.has_section("ui") else {}
    cfg.dark_mode = ui.get("dark_mode", "false").strip().lower() in {"1", "true", "yes"}
    if not cfg.pg_password:
        load_password(cfg)
    cfg.configured = True
    return cfg


def save(cfg: AppConfig, path: Path | None = None) -> None:
    path = path or paths.config_file()
    password_for_ini = cfg.pg_password
    if store_password(cfg):
        password_for_ini = ""
    parser = configparser.ConfigParser()
    parser["database"] = {
        "backend": cfg.backend,
        "data_dir": str(cfg.data_dir),
        "sqlite_path": str(cfg.sqlite_path),
        "pg_host": cfg.pg_host,
        "pg_port": str(cfg.pg_port),
        "pg_database": cfg.pg_database,
        "pg_user": cfg.pg_user,
        "pg_password": password_for_ini,
        "pg_sslmode": cfg.pg_sslmode,
        "pg_connect_timeout": str(cfg.pg_connect_timeout),
        "attachments_dir_override": str(cfg.attachments_dir_override or ""),
    }
    parser["server"] = {
        "pg_bin_dir": str(cfg.pg_bin_dir or ""),
        "server_backup_dir": str(cfg.server_backup_dir or ""),
    }
    parser["ui"] = {
        "dark_mode": "true" if cfg.dark_mode else "false",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    cfg.configured = True
