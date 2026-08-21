"""Filesystem locations. Data always lives outside the install directory."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from app.version import APP_ID


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


PORTABLE_MARKER = "portable.txt"


def executable_dir() -> Path:
    return Path(sys.executable).resolve().parent


def is_portable() -> bool:
    """The ZIP build ships a marker file so it keeps its data beside the .exe."""
    return is_frozen() and (executable_dir() / PORTABLE_MARKER).exists()


def config_dir() -> Path:
    if is_portable():
        p = executable_dir() / "data"
    else:
        p = _roaming_config_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _roaming_config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_ID


def config_file() -> Path:
    return config_dir() / "config.ini"


def default_data_dir() -> Path:
    if is_portable():
        p = executable_dir() / "data"
    elif is_frozen():
        base = os.environ.get("PROGRAMDATA") or str(Path.home())
        p = Path(base) / APP_ID
    else:
        p = project_root() / ".localdata"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
