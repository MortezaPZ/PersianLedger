# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "app" / "ui" / "style.qss"), "app/ui"),
        (str(ROOT / "app" / "ui" / "style-dark.qss"), "app/ui"),
        (str(ROOT / "app" / "ui" / "resources" / "fonts"), "app/ui/resources/fonts"),
        (str(ROOT / "app" / "ui" / "resources" / "icons"), "app/ui/resources/icons"),
        (str(ROOT / "migrations"), "migrations"),
        (str(ROOT / "portable.txt"), "."),
    ],
    hiddenimports=[
        "app.db.models",
        "app.ui.main_window",
        "app.ui.icons",
        "PySide6.QtSvg",
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
