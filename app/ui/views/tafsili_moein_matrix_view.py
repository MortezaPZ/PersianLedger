from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.domain import money
from app.export import excel, printing
from app.services.report_service import (
    MoeinMatrixResult,
    StatementFilter,
    account_statement,
    tafsili_descendant_ids,
    tafsili_moein_matrix,
)
from app.ui.views.report_base import ReportView
from app.ui.views.statement_view import StatementModel
from app.ui.widgets.tables import fit_columns
from app.ui.widgets.tree_picker import TreeChoice, TreePickerDialog


@dataclass(frozen=True)
class _RenderedFilters:
    tafsili_ids: tuple[int, ...]
    date_from: _dt.date | None
    date_to: _dt.date | None
    currency_ids: tuple[int, ...] | None


class MoeinMatrixModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result: MoeinMatrixResult | None = None

    def set_result(self, result: MoeinMatrixResult) -> None:
        self.beginResetModel()
        self.result = result
        self.endResetModel()

    def headers(self) -> list[str]:
        if not self.result:
            return []
        headers = ["کد معین", "نام معین"]
        for currency in self.result.currencies:
            headers.extend(
                [
                    f"{currency.code} گردش بدهکار",
                    f"{currency.code} گردش بستانکار",
                    f"{currency.code} مانده بدهکار",
                    f"{currency.code} مانده بستانکار",
                ]
            )
        return headers

    def rowCount(self, parent=None) -> int:
        return len(self.result.rows) if self.result else 0

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
        if role != Qt.DisplayRole:
            return None
        if index.column() == 0:
            return row.account_code
        if index.column() == 1:
            return row.account_name
        currency_index = (index.column() - 2) // 4
        offset = (index.column() - 2) % 4
        currency = self.result.currencies[currency_index]
        totals = row.amounts.get(currency.id)
        if totals is None:
            return ""
        value = (
            totals.debit_turnover,
            totals.credit_turnover,
            totals.debit_balance,
            totals.credit_balance,
        )[offset]
        return money.format_amount(value, currency.decimals) if value else ""


class TafsiliMoeinMatrixView(ReportView):
    title = "گردش حساب‌های معین به تفکیک تفصیلی"
    hint = "انتخاب یک تفصیلی والد، گردش همهٔ تفصیلی‌های نهایی زیرمجموعه را در معین‌ها جمع می‌کند. هر ارز در ستون‌های جداگانه می‌ماند. برای دیدن ریز سندها روی ردیف معین دوبار کلیک کنید."
    file_stem = "گردش-معین-به-تفکیک-تفصیلی"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.tafsili = QComboBox()
        self.tafsili.setEditable(True)
        self.tafsili.setInsertPolicy(QComboBox.NoInsert)
        self.tafsili.setMaxVisibleItems(18)
        self.tafsili.completer().setFilterMode(Qt.MatchContains)
        self.tafsili.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.tree_button = QToolButton()
        self.tree_button.setText("درخت…")
        self.tree_button.clicked.connect(self.pick_tafsili)
        selector = QHBoxLayout()
        selector.setContentsMargins(0, 0, 0, 0)
        selector.addWidget(self.tafsili, 1)
        selector.addWidget(self.tree_button)
        selector_widget = QWidget()
        selector_widget.setLayout(selector)
        self.add_filter("تفصیلی", selector_widget)
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("ارزها", self.make_currency_list())

        self.model = MoeinMatrixModel(self)
        self._rendered_filters: _RenderedFilters | None = None
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.show_statement)
        self.body.addWidget(self.table, 1)
        self.reload_currencies()
        self.reload_tafsilis()

    def reload_tafsilis(self) -> None:
        current = self.tafsili.currentData() if self.tafsili.count() else None
        self.tafsili.blockSignals(True)
        self.tafsili.clear()
        self.tafsili.addItem("انتخاب تفصیلی", None)
        for item in sorted(self.ctx.refdata.tafsilis, key=lambda row: row.code):
            depth = max(0, len(self.ctx.refdata._tafsili_path(item)) - 1)
            self.tafsili.addItem(f"{'　' * depth}{item.display}", item.id)
        self.tafsili.setCurrentIndex(max(0, self.tafsili.findData(current)))
        self.tafsili.blockSignals(False)

    def refresh(self) -> None:
        self.reload_currencies()
        self.reload_tafsilis()

    def _tree_choices(self) -> list[TreeChoice]:
        return [
            (item.id, item.display, item.parent_id, True)
            for item in sorted(self.ctx.refdata.tafsilis, key=lambda row: row.code)
        ]

    def pick_tafsili(self) -> None:
        dialog = TreePickerDialog(
            "انتخاب تفصیلی از درخت",
            self._tree_choices(),
            self.tafsili.currentData(),
            self,
        )
        if dialog.exec() and dialog.selected_id is not None:
            index = self.tafsili.findData(dialog.selected_id)
            if index >= 0:
                self.tafsili.setCurrentIndex(index)

    def run(self) -> None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        tafsili_id = self.tafsili.currentData()
        if not tafsili_id:
            self.warn("تفصیلی را از فهرست یا درخت انتخاب کنید.")
            return
        try:
            with self.ctx.read_session() as db:
                result = tafsili_moein_matrix(
                    db,
                    tafsili_id,
                    kwargs.get("date_from"),
                    kwargs.get("date_to"),
                    kwargs.get("currency_ids"),
                )
            currency_ids = kwargs.get("currency_ids")
            self._result = result
            self._rendered_filters = _RenderedFilters(
                tafsili_ids=result.tafsili_ids,
                date_from=kwargs.get("date_from"),
                date_to=kwargs.get("date_to"),
                currency_ids=tuple(currency_ids) if currency_ids else None,
            )
            self.model.set_result(self._result)
            fit_columns(self.table)
            self.summary.setText(f"{len(self._result.rows)} معین")
        except Exception as exc:
            self.report_error(exc)

    def show_statement(self, index) -> None:
        snapshot = self._rendered_filters
        if not self._result or snapshot is None or not index.isValid():
            return
        row = self._result.rows[index.row()]
        try:
            with self.ctx.read_session() as db:
                result = account_statement(
                    db,
                    StatementFilter(
                        account_id=row.account_id,
                        tafsili_ids=list(snapshot.tafsili_ids),
                        date_from=snapshot.date_from,
                        date_to=snapshot.date_to,
                        currency_ids=list(snapshot.currency_ids) if snapshot.currency_ids else None,
                        include_drafts=False,
                        include_opening=True,
                    ),
                )
            dialog = QDialog(self)
            dialog.setWindowTitle(result.title)
            dialog.setLayoutDirection(Qt.RightToLeft)
            dialog.resize(1050, 650)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(result.subtitle))
            table = QTableView()
            table.setModel(StatementModel(table))
            table.model().set_result(result)
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            layout.addWidget(table, 1)
            close = QPushButton("بستن")
            close.clicked.connect(dialog.accept)
            layout.addWidget(close)
            fit_columns(table)
            dialog.exec()
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.tafsili_moein_matrix_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_tafsili_moein_matrix(path, self._result)
