from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QComboBox, QLabel, QTableView

from app.export import excel, printing
from app.services.report_service import StatementFilter, party_statement
from app.ui.views.report_base import ReportView
from app.ui.views.statement_view import StatementModel
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.tables import fit_columns


class PartyStatementView(ReportView):
    title = "صورت وضعیت اشخاص"
    hint = "مانده یک شخص یا پروژه در همه سرفصل‌ها. برای گردش یک سرفصل از «صورتحساب سرفصل» استفاده کنید."
    file_stem = "صورت-وضعیت"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.from_date, self.to_date = self.make_date_range()
        self.group = QComboBox()
        self.party = QComboBox(); self.party.setEditable(True)
        self.group.currentIndexChanged.connect(self._fill_parties)
        self.group.setToolTip("یک گروه، یا همه گروه‌ها. تفصیلی مشترک در چند گروه با انتخاب گروه محدود می‌شود.")
        self.add_filter("گروه", combo_with_picker(self.group, "انتخاب گروه"))
        self.add_filter("شخص / پروژه", combo_with_picker(self.party, "انتخاب تفصیلی"))
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("ارزها", self.make_currency_list())
        self.finish_filters()
        self.model = StatementModel()
        self.table = QTableView(); self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.body.addWidget(self.table, 1)
        self.reload_currencies()
        self._fill_groups()

    def _fill_groups(self) -> None:
        self.group.clear(); self.group.addItem("همه گروه‌ها", None)
        for g in self.ctx.refdata.groups:
            self.group.addItem(f"{g.code} {g.name}", g.id)
        self._fill_parties()

    def _fill_parties(self) -> None:
        gid = self.group.currentData()
        self.party.clear(); self.party.addItem("انتخاب کنید", None)
        for item in self.ctx.refdata.tafsilis:
            if gid is None or gid in item.group_ids:
                self.party.addItem(item.display, item.id)

    def refresh(self) -> None:
        self.reload_currencies(); self._fill_groups()

    def run(self) -> None:
        if not self.party.currentData():
            self.warn("تفصیلی را انتخاب کنید.")
            return
        groups = [self.group.currentData()] if self.group.currentData() else None
        kwargs = self.ready_filters()
        if kwargs is None:
            return
        if groups:
            kwargs["group_ids"] = groups
        try:
            with self.ctx.read_session() as db:
                self._result = party_statement(db, StatementFilter(tafsili_any_id=self.party.currentData(), **kwargs))
            self.model.set_result(self._result)
            fit_columns(self.table)
            self.summary.setText(f"{len(self._result.rows)} سطر")
        except Exception as exc:
            self.report_error(exc)

    def build_html(self) -> str:
        return printing.statement_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_statement(path, self._result)
