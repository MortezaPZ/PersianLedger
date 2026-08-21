from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

_PERSIAN_FALLBACKS = ("Vazirmatn", "Sahel", "IRANSans", "Segoe UI", "Tahoma")
log = logging.getLogger("theme")
_fonts_loaded = False


def stylesheet(dark: bool = False) -> str:
    name = "style-dark.qss" if dark else "style.qss"
    path = Path(__file__).resolve().parent / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_bundled_fonts() -> int:
    global _fonts_loaded
    if _fonts_loaded:
        return 1
    fonts_dir = Path(__file__).resolve().parent / "resources" / "fonts"
    loaded = 0
    if not fonts_dir.exists():
        log.warning("no bundled fonts at %s; falling back to system fonts", fonts_dir)
        return 0
    for file in sorted(fonts_dir.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(file)) == -1:
            log.warning("could not load font %s", file.name)
        else:
            loaded += 1
    _fonts_loaded = loaded > 0
    return loaded


def pick_font() -> QFont:
    families = set(QFontDatabase.families())
    for name in _PERSIAN_FALLBACKS:
        if name in families:
            font = QFont(name, 10)
            break
    else:
        font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    return font


def apply(app: QApplication, dark: bool = False) -> None:
    _load_bundled_fonts()
    locale = QLocale(QLocale.Persian, QLocale.Iran)
    QLocale.setDefault(locale)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(pick_font())
    app.setProperty("darkMode", dark)
    app.setStyleSheet(stylesheet(dark))
