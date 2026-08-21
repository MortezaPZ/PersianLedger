from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from app.domain import jalali
from app.domain.jalali import JalaliError


class JalaliDateEdit(QWidget):
    dateChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("۱۴۰۵-۰۱-۱۵")
        self.edit.editingFinished.connect(self._normalize)
        today = QPushButton("امروز")
        today.clicked.connect(self.set_today)
        layout.addWidget(self.edit, 1)
        layout.addWidget(today)
        self.set_today()

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value)

    def clear(self) -> None:
        self.edit.clear()

    def set_today(self) -> None:
        self.edit.setText(jalali.format_jalali(jalali.today_jalali()))
        self.dateChanged.emit()

    def gregorian(self):
        if not self.text():
            return None
        try:
            return jalali.gregorian_from_string(self.text())
        except JalaliError:
            return None

    def jalali_text(self) -> str:
        g = self.gregorian()
        return jalali.jalali_string(g) if g else self.text()

    def _normalize(self) -> None:
        if not self.text():
            return
        try:
            parsed = jalali.parse_jalali(self.text())
            self.edit.setText(jalali.format_jalali(parsed))
            self.dateChanged.emit()
        except JalaliError:
            pass
