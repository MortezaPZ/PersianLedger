from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import QObject, Signal

from app.bootstrap import Startup
from app.db import engine as engine_module
from app.services import master_data
from app.ui.refdata import RefData


class AppContext(QObject):
    """Shared session access plus a cached snapshot of master data."""

    dataChanged = Signal()
    refdataChanged = Signal()

    def __init__(self, startup: Startup) -> None:
        super().__init__()
        self.startup = startup
        self.config = startup.config
        self.user_id = None
        self.username: str | None = None
        self.display_name: str | None = None
        self.is_admin: bool = False
        self._refdata: RefData | None = None
        self._fiscal_year_id: int | None = None

    @contextmanager
    def session(self):
        db = engine_module.new_session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def read_session(self):
        db = engine_module.new_session()
        try:
            yield db
        finally:
            db.close()

    @property
    def refdata(self) -> RefData:
        if self._refdata is None:
            with self.read_session() as db:
                self._refdata = RefData.load(db)
        return self._refdata

    def reload_refdata(self) -> None:
        """Refresh in place; delegates and models keep the same object."""
        with self.read_session() as db:
            if self._refdata is None:
                self._refdata = RefData.load(db)
            else:
                self._refdata.reload(db)
        self.refdataChanged.emit()

    def fiscal_years(self):
        with self.read_session() as db:
            return master_data.fiscal_years(db)

    @property
    def fiscal_year_id(self) -> int | None:
        if self._fiscal_year_id is None:
            with self.read_session() as db:
                year = master_data.current_fiscal_year(db)
                self._fiscal_year_id = year.id if year else None
        return self._fiscal_year_id

    @fiscal_year_id.setter
    def fiscal_year_id(self, value: int | None) -> None:
        self._fiscal_year_id = value

    @property
    def fiscal_year_title(self) -> str:
        for year in self.fiscal_years():
            if year.id == self.fiscal_year_id:
                return year.title
        return ""
