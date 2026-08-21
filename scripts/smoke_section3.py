"""Offscreen smoke checks for the 11-item delivery checklist (no real client DB)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QPushButton  # noqa: E402

from app import bootstrap, config as config_module  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.context import AppContext  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.views.browse_view import BrowseView  # noqa: E402
from app.ui.views.document_entry_view import DocumentEntryView  # noqa: E402
from app.ui.views.settings_view import SettingsView  # noqa: E402
from app.ui.views.statement_view import StatementView  # noqa: E402
from app.version import APP_VERSION  # noqa: E402


def main() -> int:
    assert APP_VERSION == "0.6.0", APP_VERSION
    cfg = config_module.AppConfig(
        data_dir=ROOT / ".localdata",
        sqlite_path=ROOT / ".localdata" / "ledger.sqlite3",
    )
    app = QApplication([])
    theme.apply(app, dark=False)
    startup = bootstrap.start(cfg, with_demo=True)
    ctx = AppContext(startup)
    window = MainWindow(ctx)
    window.show()
    app.processEvents()
    assert window.windowTitle().endswith("0.6.0")
    entry: DocumentEntryView = window.views[0]
    assert entry.table.editTriggers() != 0
    browse = next(v for v in window.views if isinstance(v, BrowseView))
    window.go_to(window.views.index(browse))
    app.processEvents()
    assert browse.crumb_row is not None
    assert browse.up_button is not None
    statement = next(v for v in window.views if isinstance(v, StatementView))
    window.go_to(window.views.index(statement))
    app.processEvents()
    assert isinstance(statement.include_opening, QCheckBox)
    settings = next(v for v in window.views if isinstance(v, SettingsView))
    window.go_to(window.views.index(settings))
    app.processEvents()
    assert isinstance(settings.dark_check, QCheckBox)
    combos = window.findChildren(QComboBox)
    assert combos, "expected combo boxes"
    print("section-3-smoke-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
