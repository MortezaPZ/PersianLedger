from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QTableView

from app.domain import money
from app.export import excel, printing
from app.services.report_service import StatementFilter, account_statement
from app.ui import theme
from app.ui.views.report_base import ReportView
from app.ui.widgets.tables import fit_columns


class StatementModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result = None

    def set_result(self, result) -> None:
        self.beginResetModel()
        self.result = result
        self.endResetModel()

    def headers(self) -> list[str]:
        if not self.result:
            return []
        headers = ["تاریخ", "شماره", "نوع", "شرح", "سرفصل", "تفصیلی"]
        for col in self.result.currencies:
            headers.extend([f"{col.code} بدهکار", f"{col.code} بستانکار", f"{col.code} مانده"])
        return headers

    def rowCount(self, parent=None) -> int:
        return 0 if not self.result else len(self.result.rows)

    def columnCount(self, parent=None) -> int:
        return len(self.headers())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers()[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not self.result or not index.isValid():
            return None
        row = self.result.rows[index.row()]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.BackgroundRole and (row.is_draft or row.is_opening):
            return QBrush(QColor(theme.current_palette().draft_row))
        if role != Qt.DisplayRole:
            return None
        fixed = [row.date_j, row.number, row.doc_type, row.description, f"{row.account_code} {row.account_name}".strip(), row.tafsili]
        if index.column() < 6:
            return fixed[index.column()]
        currency_index = (index.column() - 6) // 3
        offset = (index.column() - 6) % 3
        col = self.result.currencies[currency_index]
        debit, credit, balance = row.amounts.get(col.id, (0, 0, 0))
        value = (debit, credit, balance)[offset]
        return money.format_amount(value, col.decimals) if value else ""


class StatementView(ReportView):
    title = "صورتحساب سرفصل"
    hint = "گردش یک سرفصل. برای مانده یک شخص در همه سرفصل‌ها از «صورت وضعیت اشخاص» استفاده کنید."
    file_stem = "صورتحساب-سرفصل"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.attach_account_tafsili_filters()
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("ارزها", self.make_currency_list())
        self.add_filter("گروه تفصیلی", self.make_group_list())
        self.finish_filters()
        self.model = StatementModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.reload_currencies(); self.reload_groups()

    def refresh(self) -> None:
        self.fill_linked_filters(); self.reload_currencies(); self.reload_groups()

    def run(self) -> None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        if not kwargs.get("account_id") and not kwargs.get("tafsili_any_id"):
            self.warn("سرفصل یا تفصیلی را انتخاب کنید.")
            return
        try:
            with self.ctx.read_session() as db:
                self._result = account_statement(
                    db,
                    StatementFilter(**kwargs),
                )
            self.model.set_result(self._result)
            fit_columns(self.table)
            self.summary.setText(f"{len(self._result.rows)} سطر")
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.statement_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_statement(path, self._result)
