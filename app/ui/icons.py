from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

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


def pixmap(name: str, color: str = "#d5deea", size: int = 18) -> QPixmap:
    path = ICONS_DIR / f"{name}.svg"
    data = path.read_text(encoding="utf-8").replace("#000000", color) if path.exists() else ""
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    image = QPixmap(size, size)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def icon(name: str, color: str = "#d5deea", size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))


def page_icon(page_key: str, color: str = "#d5deea") -> QIcon:
    return icon(PAGE_ICONS.get(page_key, "document"), color)
