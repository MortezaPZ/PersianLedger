"""Engine and session factory. Nothing here is SQLite-specific except the PRAGMAs."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

SCHEMA_LOCK_KEY = 7_419_001


def _apply_sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()


def build_engine(url: str, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 15}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 1800
        kwargs["connect_args"] = {"options": "-c timezone=UTC"}
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine


def test_connection(url: str) -> str:
    from app.domain.errors import LedgerError

    engine = None
    try:
        engine = build_engine(url)
        with engine.connect() as connection:
            if url.startswith("sqlite"):
                version = connection.execute(text("select sqlite_version()")).scalar()
            else:
                version = connection.execute(text("SELECT version()")).scalar()
        return str(version)
    except LedgerError:
        raise
    except Exception as exc:
        raise LedgerError(f"اتصال به سرور برقرار نشد:\n{exc}") from exc
    finally:
        if engine is not None:
            engine.dispose()


@contextmanager
def advisory_lock(connection, key: int):
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": key})
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
    else:
        yield


def init_engine(cfg: AppConfig, echo: bool = False) -> Engine:
    global _engine, _session_factory
    dispose()
    _engine = build_engine(cfg.database_url(), echo=echo)
    _session_factory = sessionmaker(bind=_engine, autoflush=True, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("موتور دیتابیس هنوز راه‌اندازی نشده است")
    return _engine


def new_session() -> Session:
    if _session_factory is None:
        raise RuntimeError("موتور دیتابیس هنوز راه‌اندازی نشده است")
    return _session_factory()


def set_session_factory(factory: sessionmaker[Session], engine: Engine) -> None:
    """Used by tests to point the app at a throwaway database."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = factory


def dispose() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
