from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QInputDialog,
)

from app.domain.errors import LedgerError
from app.services import master_data
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.ui.widgets.pickers import combo_with_picker
from app.version import APP_NAME_FA


class TafsiliDialog(QDialog):
    def __init__(self, context, parent=None, item=None, parent_id: int | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.item = item
        self.created_id: int | None = None
        self.setWindowTitle("تفصیلی شناور")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.group = QComboBox()
        for g in context.refdata.groups:
            self.group.addItem(f"{g.code} {g.name}", g.id)
        self.group.currentIndexChanged.connect(self._suggest)
        self.group.currentIndexChanged.connect(self._sync_home_row)
        self.parent_picker = QComboBox()
        self.parent_picker.addItem("بدون والد — ریشه", None)
        blocked_ids = {item.id} if item else set()
        if item:
            for candidate in context.refdata.tafsilis:
                if any(node.id == item.id for node in context.refdata._tafsili_path(candidate)):
                    blocked_ids.add(candidate.id)
        for candidate in sorted(context.refdata.tafsilis, key=lambda row: row.code):
            if candidate.id in blocked_ids or not candidate.is_active:
                continue
            depth = max(0, len(context.refdata._tafsili_path(candidate)) - 1)
            self.parent_picker.addItem(f"{'　' * (depth + 1)}{candidate.display}", candidate.id)
        selected_parent = item.parent_id if item else parent_id
        self.parent_picker.setCurrentIndex(max(0, self.parent_picker.findData(selected_parent)))
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
        self.extras.setToolTip("گروه اصلی همیشه یکی از گروه‌های عضویت است؛ ردیف آن اینجا به‌صورت انتخاب‌شده و غیرفعال نشان داده می‌شود.")
        self.linked_meoin = QListWidget()
        self.linked_meoin.setSelectionMode(QAbstractItemView.NoSelection)
        self.linked_meoin.setMinimumHeight(140)
        self.linked_meoin.setToolTip(
            "معین‌هایی که گروه اصلی این تفصیلی را می‌پذیرند. تیک‌ها برای همهٔ اعضای همان گروه مشترک است."
        )
        for acc in context.refdata.postable:
            it = QListWidgetItem(acc.display)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, acc.id)
            self.linked_meoin.addItem(it)
        self.group.currentIndexChanged.connect(self._sync_linked_meoin)
        form.addRow("گروه اصلی", combo_with_picker(self.group, "انتخاب گروه"))
        form.addRow("والد", combo_with_picker(self.parent_picker, "انتخاب والد از درخت تفصیلی"))
        form.addRow("کد", self.code)
        form.addRow("نام", self.name)
        form.addRow("عضویت در گروه‌های دیگر", self.extras)
        form.addRow("معین‌های متصل", self.linked_meoin)
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
        self._sync_home_row()
        self._sync_linked_meoin()

    def _sync_home_row(self) -> None:
        home = self.group.currentData()
        for i in range(self.extras.count()):
            it = self.extras.item(i)
            is_home = it.data(Qt.UserRole) == home
            flags = it.flags()
            if is_home:
                it.setCheckState(Qt.Checked)
                it.setFlags(flags & ~Qt.ItemIsEnabled)
            else:
                it.setFlags(flags | Qt.ItemIsEnabled)

    def _sync_linked_meoin(self) -> None:
        home = self.group.currentData()
        linked = {a.id for a in self.ctx.refdata.moein_accounts_for_groups({home} if home else set()) if a.is_postable}
        self.linked_meoin.blockSignals(True)
        for i in range(self.linked_meoin.count()):
            it = self.linked_meoin.item(i)
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in linked else Qt.Unchecked)
        self.linked_meoin.blockSignals(False)

    def linked_account_ids(self) -> list[int]:
        ids = []
        for i in range(self.linked_meoin.count()):
            it = self.linked_meoin.item(i)
            if it.checkState() == Qt.Checked:
                ids.append(it.data(Qt.UserRole))
        return ids

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
                    row = master_data.create_tafsili(
                        db,
                        code=self.code.text(),
                        name=self.name.text(),
                        group_id=self.group.currentData(),
                        parent_id=self.parent_picker.currentData(),
                        phone=self.phone.text() or None,
                        national_id=self.nid.text() or None,
                        address=self.address.text() or None,
                        note=self.note.text() or None,
                        extra_group_ids=self.extra_ids(),
                        user_id=self.ctx.user_id,
                    )
                    db.flush()
                    self.created_id = row.id
                    master_data.set_group_moein_accounts(
                        db,
                        group_id=self.group.currentData(),
                        account_ids=self.linked_account_ids(),
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
                        parent_id=self.parent_picker.currentData(),
                        extra_group_ids=self.extra_ids(),
                        phone=self.phone.text(),
                        national_id=self.nid.text(),
                        address=self.address.text(),
                        note=self.note.text(),
                        user_id=self.ctx.user_id,
                    )
                    master_data.set_group_moein_accounts(
                        db,
                        group_id=self.group.currentData(),
                        account_ids=self.linked_account_ids(),
                        user_id=self.ctx.user_id,
                    )
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, APP_NAME_FA, str(exc))


class _TreeTableCompatibility:
    """Keep simple row/item inspection helpers while the visible list is hierarchical."""

    def __init__(self, tree: QTreeWidget) -> None:
        self.tree = tree

    def _items(self) -> list[QTreeWidgetItem]:
        out: list[QTreeWidgetItem] = []

        def visit(node: QTreeWidgetItem) -> None:
            out.append(node)
            for index in range(node.childCount()):
                visit(node.child(index))

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))
        return out

    def rowCount(self) -> int:
        return len(self._items())

    def item(self, row: int, _column: int) -> _TreeTableCell:
        return _TreeTableCell(self._items()[row], _column)

    def selectRow(self, row: int) -> None:
        item = self._items()[row]
        self.tree.setCurrentItem(item)
        item.setSelected(True)


class _TreeTableCell:
    def __init__(self, item: QTreeWidgetItem, column: int) -> None:
        self.item = item
        self.column = column

    def text(self) -> str:
        return self.item.text(self.column)


class TafsiliView(BaseView):
    title = "تفصیلی شناور"
    hint = "تفصیلی‌ها را در درخت والد و فرزند مدیریت کنید. گروه‌ها دسته‌بندی مستقل‌اند؛ در سند همچنان دو خانهٔ تفصیلی ۱ و ۲ وجود دارد."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        bar = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItem("همه گروه‌ها", None)
        add = QPushButton("تفصیلی جدید")
        add.setProperty("kind", "primary")
        add.clicked.connect(self.create)
        add_group = QPushButton("گروه تفصیلی جدید")
        add_group.clicked.connect(self.create_group)
        edit = QPushButton("ویرایش")
        edit.clicked.connect(self.edit)
        child = QPushButton("فرزند جدید")
        child.clicked.connect(self.create_child)
        toggle = QPushButton("فعال / غیرفعال")
        toggle.clicked.connect(self.toggle_active)
        remove = QPushButton("حذف")
        remove.setProperty("kind", "danger")
        remove.clicked.connect(self.delete_current)
        bar.addWidget(QLabel("گروه"))
        bar.addWidget(combo_with_picker(self.filter, "فیلتر گروه"))
        bar.addStretch()
        bar.addWidget(edit)
        bar.addWidget(child)
        bar.addWidget(toggle)
        bar.addWidget(remove)
        bar.addWidget(add_group)
        bar.addWidget(add)
        self.body.addLayout(bar)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["کد", "نام", "گروه اصلی", "گروه‌های دیگر", "معین‌های متصل", "وضعیت"])
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.doubleClicked.connect(self.edit)
        self.body.addWidget(self.tree)
        self.table = _TreeTableCompatibility(self.tree)
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
            rows = master_data.tafsilis(db)
            visible = {
                item.id: item for item in rows if gid is None or gid in item.group_ids
            }
            if gid is not None:
                for item in list(visible.values()):
                    parent = item.parent
                    while parent is not None:
                        visible.setdefault(parent.id, parent)
                        parent = parent.parent
            payload = []
            for item in rows:
                if item.id not in visible:
                    continue
                extras = [groups[i].name for i in item.group_ids if i != item.group_id and i in groups]
                home = groups[item.group_id].name if item.group_id in groups else ""
                meoin = self.ctx.refdata.moein_accounts_for_groups(item.group_ids)
                meoin_names = "، ".join(sorted({a.code for a in meoin if a.is_postable}))
                payload.append(
                    (
                        item,
                        [item.code, item.name, home, "، ".join(extras), meoin_names, "فعال" if item.is_active else "غیرفعال"],
                    )
                )
        self.tree.clear()
        nodes: dict[int, QTreeWidgetItem] = {}
        parent_ids: dict[int, int | None] = {}
        for item, values in payload:
            node = QTreeWidgetItem(values)
            node.setData(0, Qt.UserRole, item.id)
            nodes[item.id] = node
            parent_ids[item.id] = item.parent_id if item.parent_id in visible else None
        for ident, node in nodes.items():
            parent_id = parent_ids[ident]
            if parent_id in nodes:
                nodes[parent_id].addChild(node)
            else:
                self.tree.addTopLevelItem(node)
        self.tree.expandAll()
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    def _current_id(self) -> int | None:
        node = self.tree.currentItem()
        return node.data(0, Qt.UserRole) if node else None

    def create(self) -> None:
        if TafsiliDialog(self.ctx, self).exec():
            self.ctx.reload_refdata()
            self.refresh()

    def create_child(self) -> None:
        parent_id = self._current_id()
        if not parent_id:
            self.warn("برای ایجاد فرزند ابتدا یک تفصیلی را انتخاب کنید.")
            return
        if TafsiliDialog(self.ctx, self, parent_id=parent_id).exec():
            self.ctx.reload_refdata()
            self.refresh()

    def toggle_active(self) -> None:
        tid = self._current_id()
        if not tid:
            self.warn("یک تفصیلی را انتخاب کنید.")
            return
        from app.db.models import Tafsili

        try:
            with self.ctx.session() as db:
                item = db.get(Tafsili, tid)
                if item is None:
                    return
                active = not item.is_active
                master_data.update_tafsili(db, item, is_active=active, user_id=self.ctx.user_id)
            self.ctx.reload_refdata()
            self.refresh()
            self.inform("تفصیلی فعال شد." if active else "تفصیلی غیرفعال شد.")
        except LedgerError as exc:
            self.warn(str(exc))
        except Exception as exc:
            self.report_error(exc)

    def create_group(self) -> None:
        code, ok = QInputDialog.getText(self, "گروه تفصیلی جدید", "کد گروه:")
        if not ok or not code.strip():
            return
        name, ok = QInputDialog.getText(self, "گروه تفصیلی جدید", "نام گروه:")
        if not ok or not name.strip():
            return
        try:
            with self.ctx.session() as db:
                master_data.create_tafsili_group(db, code=code.strip(), name=name.strip(), user_id=self.ctx.user_id)
            self.ctx.reload_refdata()
            self.refresh()
            self.inform("گروه تفصیلی ایجاد شد.")
        except LedgerError as exc:
            self.warn(str(exc))
        except Exception as exc:
            self.report_error(exc)

    def delete_current(self) -> None:
        tid = self._current_id()
        if not tid:
            self.warn("یک تفصیلی را انتخاب کنید.")
            return
        if not self.confirm("این تفصیلی حذف شود؟"):
            return
        try:
            with self.ctx.session() as db:
                from app.db.models import Tafsili

                item = db.get(Tafsili, tid)
                if item is None:
                    return
                master_data.delete_tafsili(db, item, user_id=self.ctx.user_id)
            self.ctx.reload_refdata()
            self.refresh()
        except LedgerError as exc:
            self.warn(str(exc))

    def edit(self) -> None:
        tid = self._current_id()
        if not tid:
            return
        with self.ctx.read_session() as db:
            from app.db.models import Tafsili
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            item = db.execute(
                select(Tafsili)
                .options(selectinload(Tafsili.memberships), selectinload(Tafsili.children), selectinload(Tafsili.parent))
                .where(Tafsili.id == tid)
            ).scalar_one_or_none()
        if item and TafsiliDialog(self.ctx, self, item).exec():
            self.ctx.reload_refdata()
            self.refresh()
