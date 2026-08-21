"""Vector icons drawn with QPainter.

The bundled PySide6 is trimmed and ships no QtSvg module, so ``QIcon("x.svg")``
silently produced blank icons.  Drawing the strokes directly keeps the icons
crisp at any DPI, lets them follow the theme colour, and adds nothing to the
frozen build.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# Icons are authored on a 24x24 grid, like most line-icon sets.
_GRID = 24.0
_cache: dict[tuple[str, str, int], QIcon] = {}


def _rounded_rect(path: QPainterPath, x, y, w, h, r) -> None:
    path.addRoundedRect(QRectF(x, y, w, h), r, r)


def _polyline(path: QPainterPath, points) -> None:
    path.moveTo(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))


def _document(path: QPainterPath) -> None:
    _polyline(path, [(7, 3), (14, 3), (19, 8), (19, 21), (7, 21), (7, 3)])
    _polyline(path, [(14, 3), (14, 8), (19, 8)])
    _polyline(path, [(9.5, 13), (15, 13)])
    _polyline(path, [(9.5, 17), (13, 17)])


def _list(path: QPainterPath) -> None:
    for y in (7, 12, 17):
        _polyline(path, [(9, y), (19, y)])
        path.addEllipse(QPointF(5.5, y), 1.1, 1.1)


def _folder(path: QPainterPath) -> None:
    _polyline(path, [(4, 8), (4, 19), (20, 19), (20, 9), (12, 9), (10, 6.5), (4, 6.5), (4, 8)])


def _card(path: QPainterPath) -> None:
    _rounded_rect(path, 3.5, 6, 17, 12, 2.5)
    _polyline(path, [(3.5, 10.5), (20.5, 10.5)])
    _polyline(path, [(7, 14.5), (11, 14.5)])


def _balance(path: QPainterPath) -> None:
    _polyline(path, [(12, 4), (12, 20)])
    _polyline(path, [(6, 7), (18, 7)])
    _polyline(path, [(6, 7), (3.5, 13)])
    _polyline(path, [(6, 7), (8.5, 13)])
    _polyline(path, [(3.5, 13), (8.5, 13)])
    _polyline(path, [(18, 7), (15.5, 13)])
    _polyline(path, [(18, 7), (20.5, 13)])
    _polyline(path, [(15.5, 13), (20.5, 13)])
    _polyline(path, [(8.5, 20), (15.5, 20)])


def _book(path: QPainterPath) -> None:
    _polyline(path, [(5, 5), (5, 19)])
    _polyline(path, [(5, 5), (11.5, 6.5), (11.5, 20), (5, 18.5)])
    _polyline(path, [(19, 5), (19, 19)])
    _polyline(path, [(19, 5), (12.5, 6.5), (12.5, 20), (19, 18.5)])


def _ledger(path: QPainterPath) -> None:
    _rounded_rect(path, 4, 4, 16, 16, 2.5)
    _polyline(path, [(4, 9.5), (20, 9.5)])
    _polyline(path, [(9.5, 9.5), (9.5, 20)])


def _users(path: QPainterPath) -> None:
    path.addEllipse(QPointF(9.5, 9), 3.1, 3.1)
    _polyline(path, [(3.5, 19.5), (3.5, 18), (5.5, 15), (13.5, 15), (15.5, 18), (15.5, 19.5)])
    _polyline(path, [(16, 6.5), (17.5, 7.5), (17.5, 10.5), (16, 11.5)])
    _polyline(path, [(17.5, 15), (19, 16), (20.5, 18.5), (20.5, 19.5)])


def _tree(path: QPainterPath) -> None:
    _rounded_rect(path, 9, 3.5, 6, 4.5, 1.2)
    _rounded_rect(path, 3, 16, 6, 4.5, 1.2)
    _rounded_rect(path, 15, 16, 6, 4.5, 1.2)
    _polyline(path, [(12, 8), (12, 12.5)])
    _polyline(path, [(6, 16), (6, 12.5), (18, 12.5), (18, 16)])


def _tag(path: QPainterPath) -> None:
    _polyline(path, [(11.5, 3.5), (20.5, 12.5), (12.5, 20.5), (3.5, 11.5), (3.5, 3.5), (11.5, 3.5)])
    path.addEllipse(QPointF(7.6, 7.6), 1.4, 1.4)


def _gear(path: QPainterPath) -> None:
    path.addEllipse(QPointF(12, 12), 3.0, 3.0)
    path.addEllipse(QPointF(12, 12), 7.2, 7.2)
    for x1, y1, x2, y2 in (
        (12, 2.6, 12, 5.2), (12, 18.8, 12, 21.4),
        (2.6, 12, 5.2, 12), (18.8, 12, 21.4, 12),
    ):
        _polyline(path, [(x1, y1), (x2, y2)])


def _clock(path: QPainterPath) -> None:
    path.addEllipse(QPointF(12, 12), 8.2, 8.2)
    _polyline(path, [(12, 7.2), (12, 12), (16, 14)])


def _chart(path: QPainterPath) -> None:
    _polyline(path, [(4, 19.5), (20, 19.5)])
    _polyline(path, [(7.5, 19.5), (7.5, 13)])
    _polyline(path, [(12, 19.5), (12, 8)])
    _polyline(path, [(16.5, 19.5), (16.5, 11)])


_SHAPES = {
    "document": _document,
    "list": _list,
    "folder": _folder,
    "card": _card,
    "balance": _balance,
    "book": _book,
    "ledger": _ledger,
    "users": _users,
    "tree": _tree,
    "tag": _tag,
    "gear": _gear,
    "clock": _clock,
    "chart": _chart,
}

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


def _pixmap(name: str, color: str, size: int, ratio: float) -> QPixmap:
    edge = int(size * ratio)
    pix = QPixmap(edge, edge)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scale = edge / _GRID
    painter.scale(scale, scale)

    path = QPainterPath()
    builder = _SHAPES.get(name, _document)
    builder(path)

    pen = QPen(QColor(color))
    # Keep the stroke visually constant once the painter scale is undone.
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    painter.end()

    pix.setDevicePixelRatio(ratio)
    return pix


def icon(name: str, color: str = "#c9d6e6", size: int = 18) -> QIcon:
    key = (name, color, size)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    result = QIcon()
    # Two densities so the icon stays sharp on HiDPI screens.
    for ratio in (1.0, 2.0):
        result.addPixmap(_pixmap(name, color, size, ratio))
    _cache[key] = result
    return result


def page_icon(page_key: str, color: str = "#c9d6e6", size: int = 18) -> QIcon:
    return icon(PAGE_ICONS.get(page_key, "document"), color, size)


def clear_cache() -> None:
    """Drop cached icons so a theme switch re-renders them in the new colour."""
    _cache.clear()


def write_checkmark(path, color: str = "#ffffff", size: int = 14) -> str:
    """Render the checkbox tick to *path* and return it as a QSS-ready url.

    Qt style sheets can only reference images by URL, so the glyph has to exist
    as a file.  Regenerating it per theme keeps the tick readable on both.
    """
    edge = size * 2
    pix = QPixmap(edge, edge)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(edge / _GRID, edge / _GRID)
    pen = QPen(QColor(color))
    pen.setWidthF(2.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    path_ = QPainterPath()
    _polyline(path_, [(5.5, 12.5), (10, 17), (18.5, 7.5)])
    painter.drawPath(path_)
    painter.end()
    pix.save(str(path), "PNG")
    # QSS wants forward slashes even on Windows.
    return str(path).replace("\\", "/")
