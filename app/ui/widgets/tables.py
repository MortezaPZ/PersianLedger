from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTableView, QTableWidget

DESC_MAX_WIDTH = 300


def fit_columns(view: QTableView | QTableWidget, description_headers: tuple[str, ...] = ("شرح", "توضیحات")) -> None:
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
