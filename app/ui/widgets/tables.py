from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTableView, QTableWidget

DESC_MAX_WIDTH = 300
ROW_HEIGHT = 30


def fit_columns(
    view: QTableView | QTableWidget,
    description_headers: tuple[str, ...] = ("شرح", "توضیحات"),
    stretch_last: bool = False,
) -> None:
    """Size columns to their contents, capping the description column.

    Reports keep ``stretch_last`` off on purpose: narrow columns are what let
    more of them fit on a page.  Entry grids turn it on so the trailing
    description field takes the leftover width for typing.
    """
    header = view.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    view.resizeColumnsToContents()
    model = view.model()
    count = view.columnCount() if isinstance(view, QTableWidget) else (model.columnCount() if model else 0)
    for col in range(count):
        if isinstance(view, QTableWidget):
            label = view.horizontalHeaderItem(col).text() if view.horizontalHeaderItem(col) else ""
        else:
            label = str(model.headerData(col, header.orientation()) or "")
        width = view.columnWidth(col)
        if any(token in label for token in description_headers):
            view.setColumnWidth(col, min(max(width, 120), DESC_MAX_WIDTH))
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        else:
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            view.setColumnWidth(col, min(width + 8, 220))
    header.setStretchLastSection(stretch_last)

    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    view.setShowGrid(False)


def size_to_rows(view: QTableView | QTableWidget, max_rows: int = 8) -> None:
    """Shrink a short table to fit its rows so it stops clipping the last one."""
    rows = view.model().rowCount() if view.model() else 0
    visible = max(1, min(rows, max_rows))
    height = view.horizontalHeader().height() + visible * ROW_HEIGHT + 2 * view.frameWidth()
    if rows > max_rows:
        height += ROW_HEIGHT // 2  # hint that more rows are scrollable
    view.setMinimumHeight(height)
    view.setMaximumHeight(height)
