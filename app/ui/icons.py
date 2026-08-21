from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QSize, Qt

ICONS_DIR = Path(__file__).resolve().parent / "resources" / "icons"

PAGE_ICONS = {
    "entry": "document",
    "list": "list",
    "browse": "folder",
    "statement": "card",
    "trial": "balance",
    "journal": "book",
    "ledger": "ledger",
    "party": "users",
    "accounts": "tree",
    "tafsili": "tag",
    "settings": "gear",
    "audit": "clock",
}


def icon(name: str, color: str = "#d5deea", size: int = 18) -> QIcon:
    path = ICONS_DIR / f"{name}.svg"
    if path.exists():
        loaded = QIcon(str(path))
        if not loaded.isNull():
            return loaded
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 3, 3)
    painter.end()
    return QIcon(pix)


def page_icon(page_key: str, color: str = "#d5deea") -> QIcon:
    return icon(PAGE_ICONS.get(page_key, "document"), color)
