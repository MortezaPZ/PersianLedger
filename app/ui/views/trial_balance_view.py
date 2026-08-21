from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QTableView

from app.domain import money
from app.export import excel, printing
from app.services import ledger_reports as lr
from app.services.report_service import StatementFilter
from app.ui.views.report_base import ReportView
from app.ui.widgets.tables import fit_columns


class TrialBalanceModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result = None

    def set_result(self, result) -> None:
        self.beginResetModel()
        self.result = result
        self.endResetModel()

    def _headers(self) -> list[str]:
        if not self.result:
            return []
        labels = {2: ["مانده بد", "مانده بس"], 4: ["گردش بد", "گردش بس", "مانده بد", "مانده بس"], 6: ["افتتاحیه بد", "افتتاحیه بس", "گردش بد", "گردش بس", "مانده بد", "مانده بس"]}[self.result.columns]
        headers = ["کد", "عنوان"]
        for col in self.result.currencies:
            headers.extend([f"{col.code}\n{label}" for label in labels])
        return headers

    def rowCount(self, parent=None) -> int:
        return 0 if not self.result else len(self.result.rows)

    def columnCount(self, parent=None) -> int:
        return len(self._headers())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers()[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not self.result or not index.isValid():
            return None
        row = self.result.rows[index.row()]
        if role == Qt.BackgroundRole and row.kind == "total":
            return QBrush(QColor("#fff7e8"))
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        if index.column() == 0:
            return row.code
        if index.column() == 1:
            return row.name
        offset = (index.column() - 2) % self.result.columns
        currency_index = (index.column() - 2) // self.result.columns
        col = self.result.currencies[currency_index]
        value = row.cell(self.result.columns, offset, col.id)
        return money.format_amount(value, col.decimals) if value else ""


class TrialBalanceView(ReportView):
    title = "تراز آزمایشی"
    hint = "۲، ۴ یا ۶ ستونی در سطح کل، معین یا تفصیلی"
    file_stem = "تراز-آزمایشی"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.level = QComboBox()
        for key, label in lr.LEVEL_FA.items():
            self.level.addItem(label, key)
        self.level.setCurrentIndex(1)
        self.columns = QComboBox()
        for n in (2, 4, 6):
            self.columns.addItem(f"{n} ستونی", n)
        self.columns.setCurrentIndex(1)
        self.filter_grid.addWidget(QLabel("از تاریخ:"), 0, 0)
        self.filter_grid.addWidget(self.from_date, 0, 1)
        self.filter_grid.addWidget(QLabel("تا تاریخ:"), 0, 2)
        self.filter_grid.addWidget(self.to_date, 0, 3)
        self.filter_grid.addWidget(QLabel("سطح:"), 1, 0)
        self.filter_grid.addWidget(self.level, 1, 1)
        self.filter_grid.addWidget(QLabel("ستون‌ها:"), 1, 2)
        self.filter_grid.addWidget(self.columns, 1, 3)
        self.filter_grid.addWidget(QLabel("ارزها:"), 0, 4)
        self.filter_grid.addWidget(self.make_currency_list(), 0, 5, 2, 1)
        self.filter_grid.addWidget(QLabel("گروه تفصیلی:"), 1, 4)
        self.filter_grid.addWidget(self.make_group_list(), 1, 5)
        self.filter_grid.addWidget(self.make_drafts_combo(), 0, 6)
        self.model = TrialBalanceModel()
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
        try:
            with self.ctx.read_session() as db:
                self._result = lr.trial_balance(
                    db,
                    StatementFilter(**self.base_filter_kwargs()),
                    level=self.level.currentData(),
                    columns=self.columns.currentData(),
                )
            self.model.set_result(self._result)
            fit_columns(self.table)
            self.summary.setText(f"{len(self._result.rows)} سطر")
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.trial_balance_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_trial_balance(path, self._result)
