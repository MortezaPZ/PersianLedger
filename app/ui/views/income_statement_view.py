from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QTableView

from app.domain import money
from app.export import excel, printing
from app.services import ledger_reports as lr
from app.services.report_service import StatementFilter
from app.ui import theme
from app.ui.views.report_base import ReportView
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.tables import fit_columns

SECTION, LINE, TOTAL = range(3)


class IncomeStatementModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result = None
        self._rows: list[tuple[int, str, str, dict]] = []

    def set_result(self, result) -> None:
        self.beginResetModel()
        self.result = result
        self._rows = []
        if result:
            self._rows.append((SECTION, "", "درآمدها", {}))
            for line in result.income:
                self._rows.append((LINE, line.code, line.name, line.amounts))
            self._rows.append((TOTAL, "", "جمع درآمدها", result.income_total))
            self._rows.append((SECTION, "", "هزینه‌ها", {}))
            for line in result.expense:
                self._rows.append((LINE, line.code, line.name, line.amounts))
            self._rows.append((TOTAL, "", "جمع هزینه‌ها", result.expense_total))
            self._rows.append((TOTAL, "", "سود (زیان) خالص", result.net))
        self.endResetModel()

    def _headers(self) -> list[str]:
        if not self.result:
            return []
        return ["کد", "عنوان"] + [f"{c.code}\n{c.name}" for c in self.result.currencies]

    def rowCount(self, parent=None) -> int:
        return len(self._rows)

    def columnCount(self, parent=None) -> int:
        return len(self._headers())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers()[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not self.result or not index.isValid():
            return None
        kind, code, name, amounts = self._rows[index.row()]
        if role == Qt.BackgroundRole and kind in (SECTION, TOTAL):
            return QBrush(QColor(theme.current_palette().subtotal_row))
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        if index.column() == 0:
            return code
        if index.column() == 1:
            return name
        if kind == SECTION:
            return ""
        col = self.result.currencies[index.column() - 2]
        value = amounts.amount(col.id) if hasattr(amounts, "amount") else amounts.get(col.id)
        return money.format_amount(value, col.decimals) if value else ""


class IncomeStatementView(ReportView):
    title = "صورت سود و زیان"
    hint = "درآمدها منهای هزینه‌ها در بازه انتخابی. هر ارز در ستون خودش."
    file_stem = "صورت-سود-و-زیان"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.level = QComboBox()
        for key, label in lr.LEVEL_FA.items():
            if key not in lr.TAFSILI_LEVELS:
                self.level.addItem(label, key)
        self.level.setCurrentIndex(self.level.count() - 1)
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("سطح", combo_with_picker(self.level, "سطح گزارش"))
        self.add_filter("ارزها", self.make_currency_list())
        self.add_filter("گروه تفصیلی", self.make_group_list())
        self.finish_filters()
        self.include_opening.setVisible(False)  # a profit figure has no opening balance
        self.model = IncomeStatementModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.reload_currencies()
        self.reload_groups()

    def refresh(self) -> None:
        self.reload_currencies()
        self.reload_groups()

    def run(self) -> None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        try:
            with self.ctx.read_session() as db:
                self._result = lr.income_statement(
                    db, StatementFilter(**kwargs), level=self.level.currentData()
                )
            self.model.set_result(self._result)
            fit_columns(self.table)
            rows = len(self._result.income) + len(self._result.expense)
            self.summary.setText(f"{rows} سرفصل")
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.income_statement_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_income_statement(path, self._result)
