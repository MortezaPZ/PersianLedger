# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import PySide6
import shiboken6

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent


def _package_binaries(package, dest: str):
    folder = Path(package.__file__).resolve().parent
    collected = []
    for pattern in ("*.pyd", "*.dll"):
        for file in folder.glob(pattern):
            collected.append((str(file), dest))
    return collected


# The venv may contain a copied (non-pip) PySide6/shiboken6 tree. PyInstaller's
# analysis does not import shiboken6.Shiboken unless we collect the .pyd explicitly.
extra_binaries = _package_binaries(shiboken6, "shiboken6") + _package_binaries(PySide6, "PySide6")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=extra_binaries,
    # The stylesheet is generated from app/ui/palette.py and the icons are drawn
    # with QPainter, so neither ships as a data file any more -- only the fonts do.
    datas=[
        (str(ROOT / "app" / "ui" / "resources" / "fonts"), "app/ui/resources/fonts"),
        (str(ROOT / "migrations"), "migrations"),
        (str(ROOT / "portable.txt"), "."),
    ],
    hiddenimports=[
        "app.db.models",
        "app.ui.main_window",
        "app.ui.icons",
        "app.ui.palette",
        "app.ui.stylesheet",
        "shiboken6",
        "shiboken6.Shiboken",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtPrintSupport",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PersianLedger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="PersianLedger")

import shutil

_dist = Path(DISTPATH) / "PersianLedger"
_dist.mkdir(parents=True, exist_ok=True)
shutil.copy2(ROOT / "portable.txt", _dist / "portable.txt")
