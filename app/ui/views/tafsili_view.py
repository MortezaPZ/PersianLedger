from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.domain.errors import LedgerError
from app.services import master_data
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.tables import fit_columns
from app.version import APP_NAME_FA


class TafsiliDialog(QDialog):
    def __init__(self, context, parent=None, item=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.item = item
        self.setWindowTitle("تفصیلی شناور")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.group = QComboBox()
        for g in context.refdata.groups:
            self.group.addItem(f"{g.code} {g.name}", g.id)
        self.group.currentIndexChanged.connect(self._suggest)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.nid = QLineEdit()
        self.address = QLineEdit()
        self.note = QLineEdit()
        self.extras = QListWidget()
        self.extras.setSelectionMode(QAbstractItemView.NoSelection)
        for g in context.refdata.groups:
            it = QListWidgetItem(f"{g.code} {g.name}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, g.id)
            self.extras.addItem(it)
        self.group.setToolTip("گروه اصلی مبنای کد پیشنهادی است. عضویت در گروه‌های دیگر همان رکورد را در چند گزارش نشان می‌دهد.")
        form.addRow("گروه اصلی", combo_with_picker(self.group, "انتخاب گروه"))
        form.addRow("کد", self.code)
        form.addRow("نام", self.name)
        form.addRow("عضویت در گروه‌های دیگر", self.extras)
        form.addRow("تلفن", self.phone)
        form.addRow("شناسه ملی", self.nid)
        form.addRow("نشانی", self.address)
        form.addRow("یادداشت", self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if item:
            idx = self.group.findData(item.group_id)
            if idx >= 0:
                self.group.setCurrentIndex(idx)
            self.code.setText(item.code)
            self.name.setText(item.name)
            self.phone.setText(item.phone or "")
            self.nid.setText(item.national_id or "")
            self.address.setText(item.address or "")
            self.note.setText(item.note or "")
            for i in range(self.extras.count()):
                it = self.extras.item(i)
                gid = it.data(Qt.UserRole)
                it.setCheckState(Qt.Checked if gid in item.group_ids and gid != item.group_id else Qt.Unchecked)
        else:
            self._suggest()

    def _suggest(self) -> None:
        if self.item:
            return
        gid = self.group.currentData()
        if not gid:
            return
        with self.ctx.read_session() as db:
            self.code.setText(master_data.suggest_tafsili_code(db, gid))

    def extra_ids(self) -> list[int]:
        ids = []
        home = self.group.currentData()
        for i in range(self.extras.count()):
            it = self.extras.item(i)
            if it.checkState() == Qt.Checked and it.data(Qt.UserRole) != home:
                ids.append(it.data(Qt.UserRole))
        return ids

    def accept(self) -> None:
        try:
            with self.ctx.session() as db:
                if self.item is None:
                    master_data.create_tafsili(
                        db,
                        code=self.code.text(),
                        name=self.name.text(),
                        group_id=self.group.currentData(),
                        phone=self.phone.text() or None,
                        national_id=self.nid.text() or None,
                        address=self.address.text() or None,
                        note=self.note.text() or None,
                        extra_group_ids=self.extra_ids(),
                        user_id=self.ctx.user_id,
                    )
                else:
                    item = db.merge(self.item)
                    master_data.update_tafsili(
                        db,
                        item,
                        code=self.code.text(),
                        name=self.name.text(),
                        group_id=self.group.currentData(),
                        extra_group_ids=self.extra_ids(),
                        phone=self.phone.text(),
                        national_id=self.nid.text(),
                        address=self.address.text(),
                        note=self.note.text(),
                        user_id=self.ctx.user_id,
                    )
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, APP_NAME_FA, str(exc))


class TafsiliView(BaseView):
    title = "تفصیلی شناور"
    hint = "اشخاص، صندوق‌ها، پروژه‌ها و مراکز هزینه. یک تفصیلی می‌تواند عضو چند گروه باشد."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        bar = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItem("همه گروه‌ها", None)
        add = QPushButton("تفصیلی جدید")
        add.setProperty("kind", "primary")
        add.clicked.connect(self.create)
        edit = QPushButton("ویرایش")
        edit.clicked.connect(self.edit)
        bar.addWidget(QLabel("گروه"))
        bar.addWidget(combo_with_picker(self.filter, "فیلتر گروه"))
        bar.addStretch()
        bar.addWidget(edit)
        bar.addWidget(add)
        self.body.addLayout(bar)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["کد", "نام", "گروه اصلی", "گروه‌های دیگر", "وضعیت"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit)
        self.body.addWidget(self.table)
        self.filter.currentIndexChanged.connect(self.reload)
        self.reload()

    def refresh(self) -> None:
        current = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("همه گروه‌ها", None)
        for g in self.ctx.refdata.groups:
            self.filter.addItem(f"{g.code} {g.name}", g.id)
        idx = self.filter.findData(current)
        self.filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter.blockSignals(False)
        self.reload()

    def reload(self) -> None:
        gid = self.filter.currentData()
        groups = {g.id: g for g in self.ctx.refdata.groups}
        with self.ctx.read_session() as db:
            rows = master_data.tafsilis(db, group_id=gid)
            payload = []
            for item in rows:
                extras = [groups[i].name for i in item.group_ids if i != item.group_id and i in groups]
                home = groups[item.group_id].name if item.group_id in groups else ""
                payload.append(
                    (
                        item.id,
                        [item.code, item.name, home, "، ".join(extras), "فعال" if item.is_active else "غیرفعال"],
                    )
                )
        self.table.setRowCount(len(payload))
        for r, (ident, values) in enumerate(payload):
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, ident)
                self.table.setItem(r, c, cell)
        fit_columns(self.table)

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def create(self) -> None:
        if TafsiliDialog(self.ctx, self).exec():
            self.ctx.reload_refdata()
            self.refresh()

    def edit(self) -> None:
        tid = self._current_id()
        if not tid:
            return
        with self.ctx.read_session() as db:
            item = db.get(type(self.ctx.refdata.tafsilis[0]) if self.ctx.refdata.tafsilis else None, tid)
            from app.db.models import Tafsili

            item = db.get(Tafsili, tid)
        if item and TafsiliDialog(self.ctx, self, item).exec():
            self.ctx.reload_refdata()
            self.refresh()
