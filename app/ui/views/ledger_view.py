from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QTableView

from app.export import excel, printing
from app.services import ledger_reports as lr
from app.services.report_service import StatementFilter
from app.ui.views.report_base import ReportView
from app.ui.views.statement_view import StatementModel
from app.ui.widgets.tables import fit_columns
from PySide6.QtWidgets import QAbstractItemView


class LedgerView(ReportView):
    title = "دفتر کل و معین"
    hint = "گردش و مانده هر سرفصل با شرح ردیف‌ها"
    file_stem = "دفتر-کل"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.attach_account_tafsili_filters()
        self.kind = QComboBox(); self.kind.addItem("دفتر معین", False); self.kind.addItem("دفتر کل", True)
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        from app.ui.widgets.pickers import combo_with_picker
        self.add_filter("سطح دفتر", combo_with_picker(self.kind, "سطح دفتر"))
        self.finish_filters()
        split = QHBoxLayout()
        self.accounts = QListWidget()
        self.model = StatementModel()
        self.table = QTableView(); self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.accounts.currentRowChanged.connect(self._show)
        split.addWidget(self.accounts, 1)
        split.addWidget(self.table, 4)
        self.body.addLayout(split, 1)

    def run(self) -> None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        try:
            with self.ctx.read_session() as db:
                self._result = lr.general_ledger(db, StatementFilter(**kwargs), kol=bool(self.kind.currentData()))
            self.accounts.clear()
            for section in self._result.sections:
                self.accounts.addItem(f"{section.code} {section.name}")
            if self._result.sections:
                self.accounts.setCurrentRow(0)
            self.summary.setText(f"{len(self._result.sections)} سرفصل")
        except Exception as exc:
            self.report_error(exc)

    def _show(self, row: int) -> None:
        if not self._result or row < 0 or row >= len(self._result.sections):
            return
        self.model.set_result(self._result.sections[row].result)
        fit_columns(self.table)

    def build_html(self) -> str:
        parts = [printing.statement_html(s.result) for s in self._result.sections]
        return "".join(parts)

    def write_excel(self, path) -> None:
        if self._result and self._result.sections:
            excel.export_statement(path, self._result.sections[0].result)
