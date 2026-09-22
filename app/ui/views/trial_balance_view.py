from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QTableView

from app.domain import money
from app.export import excel, printing
from app.services import ledger_reports as lr
from app.services.report_service import StatementFilter
from app.ui import theme
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
        headers = ["کد", "عنوان", "شرح"]
        for col in self.result.currencies:
            headers.extend([f"{col.code}\n{label}" for label in labels])
        return headers

    # Fixed columns before the per-currency figures start.
    LEAD_COLUMNS = 3

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
            return QBrush(QColor(theme.current_palette().subtotal_row))
        if role == Qt.ToolTipRole and index.column() == 2:
            return row.description  # full text when the column is capped
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        if index.column() == 0:
            return row.code
        if index.column() == 1:
            return row.name
        if index.column() == 2:
            return row.description
        offset = (index.column() - self.LEAD_COLUMNS) % self.result.columns
        currency_index = (index.column() - self.LEAD_COLUMNS) // self.result.columns
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
        self.attach_account_tafsili_filters()
        self.level = QComboBox()
        for key, label in lr.LEVEL_FA.items():
            self.level.addItem(label, key)
        self.level.setCurrentIndex(1)
        self.columns = QComboBox()
        for n in (2, 4, 6):
            self.columns.addItem(f"{n} ستونی", n)
        self.columns.setCurrentIndex(1)
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        from app.ui.widgets.pickers import combo_with_picker
        self.add_filter("سطح", combo_with_picker(self.level, "سطح تراز"))
        self.add_filter("ستون‌ها", combo_with_picker(self.columns, "تعداد ستون"))
        self.add_filter("ارزها", self.make_currency_list())
        self.add_filter("گروه تفصیلی", self.make_group_list())
        self.finish_filters()
        self.model = TrialBalanceModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.reload_currencies()
        self.reload_groups()

    def refresh(self) -> None:
        self.fill_linked_filters()
        self.reload_currencies()
        self.reload_groups()
        self.run()

    def run(self) -> None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        try:
            with self.ctx.read_session() as db:
                self._result = lr.trial_balance(
                    db,
                    StatementFilter(**kwargs),
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
