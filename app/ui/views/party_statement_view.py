from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QListWidgetItem, QTableView

from app.export import excel, printing
from app.services.report_service import StatementFilter, party_statement
from app.ui.views.report_base import ReportView
from app.ui.views.statement_view import StatementModel
from app.ui.widgets.tables import fit_columns


class PartyStatementView(ReportView):
    title = "صورت وضعیت اشخاص"
    hint = "مانده یک یا چند شخص/پروژه در همه سرفصل‌ها. برای گردش یک سرفصل از «صورتحساب سرفصل» استفاده کنید."
    file_stem = "صورت-وضعیت"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.add_filter("گروه", self.make_group_list())
        self.party_box, self.party_list = self._checkable_list("بدون تیک = هیچ؛ می‌توانید چند شخص/پروژه را هم‌زمان انتخاب کنید")
        self.group_list.itemChanged.connect(self._reload_parties)
        self.add_filter("شخص / پروژه", self.party_box)
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("ارزها", self.make_currency_list())
        self.finish_filters()
        self.model = StatementModel()
        self.table = QTableView(); self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.reload_currencies()
        self.reload_groups()
        self._reload_parties()

    def _reload_parties(self) -> None:
        checked = self._checked_party_ids()
        gids = set(self.checked_group_ids())
        self.party_list.blockSignals(True)
        self.party_list.clear()
        for item in self.ctx.refdata.tafsilis:
            if gids and not (gids & set(item.group_ids)):
                continue
            it = QListWidgetItem(item.display)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if item.id in checked else Qt.Unchecked)
            it.setData(Qt.UserRole, item.id)
            self.party_list.addItem(it)
        self.party_list.blockSignals(False)

    def _checked_party_ids(self) -> list[int]:
        ids = []
        for i in range(self.party_list.count()):
            it = self.party_list.item(i)
            if it.checkState() == Qt.Checked:
                ids.append(it.data(Qt.UserRole))
        return ids

    def refresh(self) -> None:
        self.reload_currencies(); self.reload_groups(); self._reload_parties()

    def run(self) -> None:
        party_ids = self._checked_party_ids()
        if not party_ids:
            self.warn("دست‌کم یک شخص/پروژه را انتخاب کنید.")
            return
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        try:
            with self.ctx.read_session() as db:
                self._result = party_statement(db, StatementFilter(tafsili_ids=party_ids, **kwargs))
            self.model.set_result(self._result)
            fit_columns(self.table)
            self.summary.setText(f"{len(self._result.rows)} سطر")
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.statement_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_statement(path, self._result)
