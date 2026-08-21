"""File logging. The packaged app has no console, so errors must land on disk."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path

from app import paths
from app.version import APP_ID

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


def log_file() -> Path:
    try:
        directory = paths.ensure_dir(paths.default_data_dir() / "logs")
    except OSError:
        directory = Path(os.environ.get("TEMP", ".")) / APP_ID
        directory.mkdir(parents=True, exist_ok=True)
    return directory / "app.log"


def configure(level: int = logging.INFO) -> Path:
    target = log_file()
    handler = logging.handlers.RotatingFileHandler(
        target, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    if not paths.is_frozen():
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(console)
    return target


def install_excepthook() -> None:
    def _hook(exc_type, exc, tb) -> None:
        logging.getLogger("crash").critical(
            "".join(traceback.format_exception(exc_type, exc, tb))
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
