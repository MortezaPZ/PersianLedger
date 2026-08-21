from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.export import printing
from app.ui.views.base_view import BaseView
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
        self.filter_grid.setContentsMargins(12, 12, 12, 12)
        self.filter_grid.setHorizontalSpacing(12)
        self.filter_grid.setVerticalSpacing(8)
        self.body.addWidget(self.filters)
        self.include_opening = QCheckBox("نمایش مانده قبل از بازه")
        self.include_opening.setChecked(True)
        self.filter_grid.addWidget(self.include_opening, 0, 6)
        self.summary = QLabel()
        self.summary.setObjectName("SummaryLine")
        self.body.addWidget(self.summary)

    def make_date_range(self) -> tuple[JalaliDateEdit, JalaliDateEdit]:
        self.from_date = JalaliDateEdit()
        self.to_date = JalaliDateEdit()
        self.from_date.clear()
        self.to_date.clear()
        return self.from_date, self.to_date

    def make_currency_list(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.currency_list = QListWidget()
        self.currency_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.currency_list.setMaximumHeight(90)
        self.currency_list.setMinimumWidth(160)
        hint = QLabel("هیچ‌کدام تیک نخورد = همه ارزها، هر کدام در ستون خودش")
        hint.setStyleSheet("color:#6b7a90; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(self.currency_list)
        layout.addWidget(hint)
        return box

    def make_group_list(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.group_list.setMaximumHeight(90)
        self.group_list.setMinimumWidth(160)
        hint = QLabel("هیچ‌کدام تیک نخورد = بدون فیلتر گروه")
        hint.setStyleSheet("color:#6b7a90; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(self.group_list)
        layout.addWidget(hint)
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
