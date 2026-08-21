"""Qt offscreen fixtures. Platform must be set before QApplication exists."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

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
