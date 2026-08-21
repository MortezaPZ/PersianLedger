from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.ui import icons, palette as palette_module, stylesheet as stylesheet_module

_PERSIAN_FALLBACKS = ("Vazirmatn", "Sahel", "IRANSans", "Segoe UI", "Tahoma")
log = logging.getLogger("theme")
_fonts_loaded = False


def palette(dark: bool = False) -> palette_module.Palette:
    return palette_module.get(dark)


def _checkmark_url(pal: palette_module.Palette) -> str:
    """Path to the tick glyph, regenerated per theme.

    Qt can only pull style-sheet images from a URL, so it has to be a real file.
    A read-only install directory must not break theming, hence the temp-dir
    fallback and the broad except: a missing tick is cosmetic, a crash is not.
    """
    try:
        from app import paths

        target = paths.config_dir() / f"checkmark-{pal.name}.png"
    except Exception:
        target = Path(tempfile.gettempdir()) / f"pl-checkmark-{pal.name}.png"
    try:
        return icons.write_checkmark(target, pal.text_on_brand)
    except Exception:
        log.warning("could not write the checkbox tick to %s", target, exc_info=True)
        return ""


def stylesheet(dark: bool = False) -> str:
    pal = palette_module.get(dark)
    return stylesheet_module.build(pal, _checkmark_url(pal))


def current_palette(app: QApplication | None = None) -> palette_module.Palette:
    """Palette matching the theme currently applied to the application."""
    app = app or QApplication.instance()
    dark = bool(app.property("darkMode")) if app is not None else False
    return palette_module.get(dark)


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
    # Icons are tinted per theme, so cached pixmaps from the old theme must go.
    icons.clear_cache()
    app.setStyleSheet(stylesheet(dark))
