"""Capture screenshots of every page in both themes (offscreen).

Run after a UI change to eyeball the whole app:
    .venv/Scripts/python.exe scripts/capture_ui.py
"""
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
from app.ui.context import AppContext  # noqa: E402
from app.ui.main_window import PAGES, MainWindow  # noqa: E402

# The pages worth reviewing after a styling change, by nav key.
PAGE_KEYS = ("entry", "list", "browse", "trial", "accounts", "settings")


def main() -> int:
    out = ROOT / "docs" / "ui-before-after"
    out.mkdir(parents=True, exist_ok=True)
    data = ROOT / ".localdata"
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")

    app = QApplication([])
    startup = bootstrap.start(cfg, with_demo=True)
    ctx = AppContext(startup)

    index_of = {key: i for i, (key, *_rest) in enumerate(PAGES)}
    for dark in (False, True):
        theme.apply(app, dark=dark)
        window = MainWindow(ctx)
        window.resize(1360, 860)
        window.show()
        app.processEvents()
        mode = "dark" if dark else "light"
        for key in PAGE_KEYS:
            window.go_to(index_of[key])
            app.processEvents()
            window.grab().save(str(out / f"after-{mode}-{key}.png"))
        # Deliberately not window.close(): closeEvent opens the "back up before
        # exit?" dialog, which blocks forever with no one to click it.
        window.hide()
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
