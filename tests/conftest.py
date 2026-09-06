"""Qt offscreen fixtures. Platform must be set before QApplication exists."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.engine import set_session_factory
from app.ui import theme


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    try:
        import PySide6

        plugin_dir = Path(PySide6.__file__).resolve().parent / "plugins"
        if plugin_dir.exists():
            os.environ.setdefault("QT_PLUGIN_PATH", str(plugin_dir))
    except Exception:
        pass
    app = QApplication.instance() or QApplication([])
    theme.apply(app, dark=False)
    return app


@pytest.fixture(scope="session")
def pg_url():
    return os.environ.get("PL_TEST_PG_URL")


@pytest.fixture(params=["sqlite", "postgresql"])
def db_session(request, pg_url):
    if request.param == "postgresql":
        if not pg_url:
            pytest.skip("PL_TEST_PG_URL not set")
        engine = create_engine(pg_url, future=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        set_session_factory(factory, engine)
        session = factory()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
        return

    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    set_session_factory(factory, engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
