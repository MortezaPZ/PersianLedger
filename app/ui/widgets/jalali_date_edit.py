from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain import jalali
from app.domain.jalali import JalaliError
from app.domain.money import to_persian_digits
from app.ui import icons, theme


class JalaliCalendarPopup(QWidget):
    datePicked = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.Popup)
        self.setLayoutDirection(Qt.RightToLeft)
        self._year = jalali.today_jalali().year
        self._month = jalali.today_jalali().month
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        nav = QHBoxLayout()
        prev_m = QPushButton("‹")
        next_m = QPushButton("›")
        prev_y = QPushButton("«")
        next_y = QPushButton("»")
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignCenter)
        prev_m.clicked.connect(lambda: self._shift(0, -1))
        next_m.clicked.connect(lambda: self._shift(0, 1))
        prev_y.clicked.connect(lambda: self._shift(-1, 0))
        next_y.clicked.connect(lambda: self._shift(1, 0))
        nav.addWidget(next_y)
        nav.addWidget(next_m)
        nav.addWidget(self.title, 1)
        nav.addWidget(prev_m)
        nav.addWidget(prev_y)
        root.addLayout(nav)
        self.grid = QGridLayout()
        root.addLayout(self.grid)
        self._buttons: list[QPushButton] = []
        for col, name in enumerate(jalali.WEEKDAY_NAMES):
            label = QLabel(name[:1])
            label.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(label, 0, col)
        for i in range(42):
            btn = QPushButton()
            btn.setObjectName("CalendarDay")
            btn.setFixedSize(36, 32)
            btn.setStyleSheet("padding: 0; min-width: 36px; min-height: 32px;")
            btn.clicked.connect(self._pick)
            self._buttons.append(btn)
            self.grid.addWidget(btn, 1 + i // 7, i % 7)

    def set_date(self, year: int, month: int, day: int | None = None) -> None:
        self._year, self._month = year, month
        self._selected_day = day
        self._rebuild()

    def _shift(self, years: int, months: int) -> None:
        month = self._month + months
        year = self._year + years
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self.set_date(year, month, getattr(self, "_selected_day", None))

    def _rebuild(self) -> None:
        self.title.setText(f"{jalali.MONTH_NAMES[self._month - 1]} {self._year}")
        first = jalali.parse_jalali(f"{self._year:04d}-{self._month:02d}-01")
        offset = first.weekday()
        dim = jalali.days_in_month(self._year, self._month)
        for i, btn in enumerate(self._buttons):
            day = i - offset + 1
            if 1 <= day <= dim:
                btn.setText(to_persian_digits(str(day)))
                btn.setEnabled(True)
                btn.setProperty("day", day)
            else:
                btn.setText("")
                btn.setEnabled(False)
                btn.setProperty("day", None)

    def _pick(self) -> None:
        day = self.sender().property("day")
        if not day:
            return
        picked = jalali.parse_jalali(f"{self._year:04d}-{self._month:02d}-{int(day):02d}")
        self.datePicked.emit(picked)
        self.hide()


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
        # A drawn icon, not an emoji: the bundled Persian font has no emoji
        # glyph, so "📅" showed up as an empty box.
        cal = QPushButton()
        cal.setIcon(icons.icon("calendar", theme.current_palette().text_muted))
        cal.setIconSize(QSize(16, 16))
        cal.setFixedWidth(34)
        cal.setToolTip("انتخاب از تقویم")
        cal.clicked.connect(self._open_calendar)
        layout.addWidget(self.edit, 1)
        layout.addWidget(cal)
        layout.addWidget(today)
        self._popup = JalaliCalendarPopup(self)
        self._popup.datePicked.connect(self._apply_jalali)
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

    def _apply_jalali(self, value) -> None:
        self.edit.setText(jalali.format_jalali(value))
        self.dateChanged.emit()

    def _open_calendar(self) -> None:
        current = None
        try:
            current = jalali.parse_jalali(self.text()) if self.text() else jalali.today_jalali()
        except JalaliError:
            current = jalali.today_jalali()
        self._popup.set_date(current.year, current.month, current.day)
        self._popup.move(self.mapToGlobal(self.rect().bottomRight()))
        self._popup.show()
