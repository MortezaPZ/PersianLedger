from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.context import AppContext
from app.version import APP_NAME_FA


class BaseView(QWidget):
    title = ""
    hint = ""
    #: Pages taller than the window set this so their content scrolls instead
    #: of being cut off at the bottom edge.
    scrollable = False

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = context
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)
        header = QWidget()
        header.setObjectName("PageHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 12, 16, 12)
        titles = QVBoxLayout()
        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("PageTitle")
        self.hint_label = QLabel(self.hint)
        self.hint_label.setObjectName("PageHint")
        self.hint_label.setWordWrap(True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.hint_label)
        h.addLayout(titles, 1)
        self.header_actions = QHBoxLayout()
        h.addLayout(self.header_actions)
        root.addWidget(header)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        if self.scrollable:
            canvas = QWidget()
            canvas.setObjectName("FilterField")  # transparent
            canvas.setLayout(self.body)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(canvas)
            root.addWidget(scroll, 1)
        else:
            root.addLayout(self.body, 1)

    def add_action(self, widget) -> None:
        self.header_actions.addWidget(widget)

    def refresh(self) -> None:
        pass

    def warn(self, text: str) -> None:
        QMessageBox.warning(self, APP_NAME_FA, text)

    def inform(self, text: str) -> None:
        QMessageBox.information(self, APP_NAME_FA, text)

    def report_error(self, exc: Exception) -> None:
        QMessageBox.critical(self, APP_NAME_FA, str(exc))

    def confirm(self, text: str) -> bool:
        return QMessageBox.question(self, APP_NAME_FA, text) == QMessageBox.Yes
