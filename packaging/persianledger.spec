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


from PyInstaller.utils.hooks import collect_all

psycopg_datas, psycopg_bins, psycopg_hidden = collect_all("psycopg")
psycopg_b_datas, psycopg_b_bins, psycopg_b_hidden = collect_all("psycopg_binary")

extra_binaries = (
    _package_binaries(shiboken6, "shiboken6")
    + _package_binaries(PySide6, "PySide6")
    + list(psycopg_bins)
    + list(psycopg_b_bins)
)

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=extra_binaries,
    # The stylesheet is generated from app/ui/palette.py and the icons are drawn
    # with QPainter, so neither ships as a data file any more -- only the fonts do.
    datas=[
        (str(ROOT / "app" / "ui" / "resources" / "fonts"), "app/ui/resources/fonts"),
        (str(ROOT / "migrations"), "migrations"),
        (str(ROOT / "docs"), "docs"),
        (str(ROOT / "deploy"), "deploy"),
        (str(ROOT / "portable.txt"), "."),
    ]
    + list(psycopg_datas)
    + list(psycopg_b_datas),
    hiddenimports=[
        "app.db.models",
        "app.ui.main_window",
        "app.ui.icons",
        "app.ui.palette",
        "app.ui.stylesheet",
        "app.domain.permissions",
        "psycopg",
        "psycopg_binary",
        "psycopg.pq",
        "keyring",
        "keyring.backends.Windows",
        "shiboken6",
        "shiboken6.Shiboken",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtPrintSupport",
    ]
    + list(psycopg_hidden)
    + list(psycopg_b_hidden),
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
