"""Capture after screenshots of the redesigned UI (offscreen)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import bootstrap, config as config_module  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.context import AppContext  # noqa: E402


def main() -> int:
    out = ROOT / "docs" / "ui-before-after"
    out.mkdir(parents=True, exist_ok=True)
    data = ROOT / ".localdata"
    cfg = AppConfig if False else config_module.AppConfig
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    app = QApplication([])
    theme.apply(app, dark=False)
    startup = bootstrap.start(cfg, with_demo=True)
    ctx = AppContext(startup)
    window = MainWindow(ctx)
    window.resize(1280, 800)
    window.show()
    app.processEvents()
    window.grab().save(str(out / "after-light-entry.png"))
    window.go_to(2)
    app.processEvents()
    window.grab().save(str(out / "after-light-browse.png"))
    theme.apply(app, dark=True)
    app.processEvents()
    window.grab().save(str(out / "after-dark-browse.png"))
    window.go_to(0)
    app.processEvents()
    window.grab().save(str(out / "after-dark-entry.png"))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
