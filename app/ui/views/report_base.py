from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.export import printing
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.ui.widgets.jalali_date_edit import JalaliDateEdit


class ReportView(BaseView):
    """Filter card, run/export/print actions and a summary line."""

    file_stem = "گزارش"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self._result = None
        self.export_button = QPushButton("خروجی اکسل")
        self.print_button = QPushButton("چاپ")
        self.run_button = QPushButton("نمایش گزارش")
        self.run_button.setProperty("kind", "primary")
        self.export_button.clicked.connect(self._export)
        self.print_button.clicked.connect(self._print)
        self.run_button.clicked.connect(self.run)
        self.add_action(self.export_button)
        self.add_action(self.print_button)
        self.add_action(self.run_button)
        self.filters = QFrame()
        self.filters.setObjectName("Card")
        self.filter_grid = QGridLayout(self.filters)
        self.filter_grid.setContentsMargins(16, 14, 16, 14)
        self.filter_grid.setHorizontalSpacing(16)
        self.filter_grid.setVerticalSpacing(12)
        self._filter_slot = 0
        self.body.addWidget(self.filters)
        self.summary = QLabel()
        self.summary.setObjectName("SummaryLine")
        self.body.addWidget(self.summary)
        self.include_opening = QCheckBox("نمایش مانده قبل از بازه")
        self.include_opening.setChecked(True)

    # ------------------------------------------------------------------
    # Filter bar
    #
    # Filters flow into a fixed-column grid instead of hand-picked (row, col)
    # coordinates.  Every cell is top-aligned, so a tall control (a currency
    # list) no longer drags its short neighbours out of line.
    # ------------------------------------------------------------------
    FILTER_COLUMNS = 4

    def add_filter(self, label: str, widget: QWidget) -> QWidget:
        group = fields.labeled(label, widget)
        row, col = divmod(self._filter_slot, self.FILTER_COLUMNS)
        self.filter_grid.addWidget(group, row, col, Qt.AlignTop)
        self.filter_grid.setColumnStretch(col, 1)
        self._filter_slot += 1
        return group

    def finish_filters(self) -> None:
        """Place the shared options after the view's own filters."""
        self.add_filter("اسناد", self.make_drafts_combo())
        self.add_filter("", self.include_opening)

    def make_date_range(self) -> tuple[JalaliDateEdit, JalaliDateEdit]:
        self.from_date = JalaliDateEdit()
        self.to_date = JalaliDateEdit()
        self.apply_fiscal_year_dates()
        return self.from_date, self.to_date

    def apply_fiscal_year_dates(self) -> None:
        years = self.ctx.fiscal_years()
        year = next((y for y in years if y.id == self.ctx.fiscal_year_id), years[0] if years else None)
        if not year:
            self.from_date.clear()
            self.to_date.clear()
            return
        self.from_date.setText(year.start_date_j)
        self.to_date.setText(year.end_date_j)

    def date_range_error(self) -> str | None:
        if not hasattr(self, "from_date"):
            return None
        if self.from_date.text() and self.from_date.gregorian() is None:
            return "تاریخ شروع نامعتبر است."
        if self.to_date.text() and self.to_date.gregorian() is None:
            return "تاریخ پایان نامعتبر است."
        start, end = self.from_date.gregorian(), self.to_date.gregorian()
        if start and end and start > end:
            return "تاریخ شروع از تاریخ پایان بزرگ‌تر است."
        return None

    def ready_filters(self) -> dict | None:
        err = self.date_range_error()
        if err:
            self.warn(err)
            return None
        return self.base_filter_kwargs()

    @staticmethod
    def _checkable_list(hint_text: str) -> tuple[QWidget, QListWidget]:
        box = QWidget()
        box.setObjectName("FilterField")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        listing = QListWidget()
        listing.setSelectionMode(QAbstractItemView.NoSelection)
        listing.setFixedHeight(104)  # three rows plus padding, so nothing clips
        listing.setMinimumWidth(150)
        hint = QLabel(hint_text)
        hint.setObjectName("Hint")  # themed, so it stays legible in dark mode
        hint.setWordWrap(True)
        shortcuts = QHBoxLayout()
        all_btn = QPushButton("همه")
        none_btn = QPushButton("هیچ")
        all_btn.setProperty("kind", "ghost")
        none_btn.setProperty("kind", "ghost")

        def _set(state) -> None:
            for i in range(listing.count()):
                listing.item(i).setCheckState(state)

        all_btn.clicked.connect(lambda: _set(Qt.Checked))
        none_btn.clicked.connect(lambda: _set(Qt.Unchecked))
        shortcuts.addWidget(all_btn)
        shortcuts.addWidget(none_btn)
        shortcuts.addStretch()
        layout.addWidget(listing)
        layout.addLayout(shortcuts)
        layout.addWidget(hint)
        return box, listing

    def make_currency_list(self) -> QWidget:
        box, self.currency_list = self._checkable_list("بدون تیک = همهٔ ارزها، هر کدام در ستون خودش")
        return box

    def make_group_list(self) -> QWidget:
        box, self.group_list = self._checkable_list("بدون تیک = بدون فیلتر گروه")
        return box

    def reload_groups(self) -> None:
        if not hasattr(self, "group_list"):
            return
        checked = self.checked_group_ids()
        self.group_list.clear()
        for group in sorted(self.ctx.refdata.groups, key=lambda g: g.code):
            item = QListWidgetItem(f"{group.code} {group.name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if group.id in checked else Qt.Unchecked)
            item.setData(Qt.UserRole, group.id)
            self.group_list.addItem(item)

    def checked_group_ids(self) -> list[int]:
        if not hasattr(self, "group_list"):
            return []
        ids = []
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def make_drafts_combo(self) -> QComboBox:
        self.drafts_combo = QComboBox()
        self.drafts_combo.addItem("قطعی + پیش‌نویس", True)
        self.drafts_combo.addItem("فقط اسناد قطعی", False)
        self.drafts_combo.setToolTip("پیش‌نویس‌ها با پس‌زمینه زرد مشخص می‌شوند تا با اسناد قطعی اشتباه نشوند.")
        return self.drafts_combo

    def reload_currencies(self) -> None:
        checked = self.checked_currency_ids()
        self.currency_list.clear()
        for cur in self.ctx.refdata.currencies:
            if not cur.is_active:
                continue
            item = QListWidgetItem(f"{cur.code} {cur.name}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if cur.id in checked else Qt.Unchecked)
            item.setData(Qt.UserRole, cur.id)
            self.currency_list.addItem(item)

    def checked_currency_ids(self) -> list[int]:
        if not hasattr(self, "currency_list"):
            return []
        ids = []
        for i in range(self.currency_list.count()):
            item = self.currency_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def base_filter_kwargs(self) -> dict:
        groups = self.checked_group_ids()
        currencies = self.checked_currency_ids()
        return {
            "date_from": getattr(self, "from_date", JalaliDateEdit()).gregorian() if hasattr(self, "from_date") else None,
            "date_to": getattr(self, "to_date", JalaliDateEdit()).gregorian() if hasattr(self, "to_date") else None,
            "currency_ids": currencies or None,
            "group_ids": groups or None,
            "include_drafts": bool(self.drafts_combo.currentData()) if hasattr(self, "drafts_combo") else True,
            "include_opening": self.include_opening.isChecked(),
        }

    def run(self) -> None:
        raise NotImplementedError

    def build_html(self) -> str:
        raise NotImplementedError

    def write_excel(self, path) -> None:
        raise NotImplementedError

    def _has_result(self) -> bool:
        if self._result is None or getattr(self._result, "is_empty", False):
            self.warn("ابتدا گزارش را نمایش دهید یا فیلترها را تغییر دهید.")
            return False
        return True

    def _export(self) -> None:
        if not self._has_result():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره خروجی اکسل", str(self.ctx.config.export_dir / f"{self.file_stem}.xlsx"), "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            self.write_excel(path)
            self.inform(f"فایل ذخیره شد:\n{path}")
        except Exception as exc:
            self.report_error(exc)

    def _print(self) -> None:
        if not self._has_result():
            return
        try:
            printing.preview(self, self.build_html())
        except Exception as exc:
            self.report_error(exc)
