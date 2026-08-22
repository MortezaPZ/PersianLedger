from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import fields


class PickFromListDialog(QDialog):
    def __init__(self, title: str, items: list[tuple[object, str]], parent=None) -> None:
        super().__init__(parent)
        self.chosen = None
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(360, 420)
        root = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو…")
        self.list = QListWidget()
        self._items = items
        for data, label in items:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, data)
            self.list.addItem(it)
        self.search.textChanged.connect(self._filter)
        self.list.itemDoubleClicked.connect(self.accept)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        save = buttons.button(QDialogButtonBox.Save)
        if save:
            save.setText("انتخاب")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(self.search)
        root.addWidget(self.list, 1)
        root.addWidget(buttons)

    def _filter(self, text: str) -> None:
        needle = (text or "").strip()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(needle) and needle not in it.text())

    def accept(self) -> None:
        item = self.list.currentItem()
        if item:
            self.chosen = item.data(Qt.UserRole)
        super().accept()


def combo_with_picker(combo, title: str = "انتخاب") -> QWidget:
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    btn = QPushButton("…")
    btn.setFixedWidth(36)
    btn.setToolTip(title)

    def pick() -> None:
        items = [(combo.itemData(i), combo.itemText(i)) for i in range(combo.count())]
        dialog = PickFromListDialog(title, items, box)
        if dialog.exec() and dialog.chosen is not None:
            idx = combo.findData(dialog.chosen)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    btn.clicked.connect(pick)
    row.addWidget(combo, 1)
    row.addWidget(btn)
    return box
