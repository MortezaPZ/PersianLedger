from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QInputDialog,
    QWidget,
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

        # Match the reference workflow: browse groups and their nested details
        # in a tree at the left, and inspect the selected branch in a table.
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setLayoutDirection(Qt.LeftToRight)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIndentation(18)
        self.tree.setMinimumWidth(220)
        self.tree.setLayoutDirection(Qt.RightToLeft)
        self.tree.setToolTip("گروه‌ها و تفصیلی‌های والد و فرزند را برای مرور انتخاب کنید.")

        listing = QWidget()
        listing_layout = QVBoxLayout(listing)
        listing_layout.setContentsMargins(0, 0, 0, 0)
        listing_layout.setSpacing(8)
        self.selection_title = QLabel("همهٔ تفصیلی‌ها")
        self.selection_title.setObjectName("PageTitle")
        listing_layout.addWidget(self.selection_title)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["کد", "نام", "گروه اصلی", "گروه‌های دیگر", "معین‌های متصل", "وضعیت"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setLayoutDirection(Qt.RightToLeft)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        for column, width in enumerate((76, 146, 104, 126, 176, 68)):
            self.table.setColumnWidth(column, width)
        listing_layout.addWidget(self.table, 1)

        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(listing)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([270, 730])
        self.body.addWidget(self.splitter, 1)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.doubleClicked.connect(self.edit)
        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        self.table.itemSelectionChanged.connect(self._table_selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit())
        self._reloading = False
        self._syncing_selection = False
        self._rows_by_id = {}
        self._tree_items_by_id = {}
        self._meoin_tooltips = {}
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
        self._meoin_tooltips = {}
        with self.ctx.read_session() as db:
            rows = master_data.tafsilis(db)
            visible = {
                item.id: item for item in rows if gid is None or gid in item.group_ids
            }
            if gid is not None:
                for item in list(visible.values()):
                    seen_parent_ids = {item.id}
                    parent = item.parent
                    while parent is not None and parent.id not in seen_parent_ids:
                        visible.setdefault(parent.id, parent)
                        seen_parent_ids.add(parent.id)
                        parent = parent.parent
            payload = []
            for item in rows:
                if item.id not in visible:
                    continue
                extras = [groups[i].name for i in item.group_ids if i != item.group_id and i in groups]
                home = groups[item.group_id].name if item.group_id in groups else ""
                meoin = self.ctx.refdata.moein_accounts_for_groups(item.group_ids)
                linked_codes = sorted({a.code for a in meoin if a.is_postable})
                self._meoin_tooltips[item.id] = "، ".join(linked_codes)
                meoin_names = "، ".join(linked_codes[:3])
                if len(linked_codes) > 3:
                    meoin_names += f" و {len(linked_codes) - 3} مورد دیگر"
                payload.append(
                    (
                        item,
                        [item.code, item.name, home, "، ".join(extras), meoin_names, "فعال" if item.is_active else "غیرفعال"],
                    )
                )

        self._rows_by_id = {item.id: (item, values) for item, values in payload}
        self._tree_items_by_id = {}
        self._reloading = True
        self.tree.clear()
        root = QTreeWidgetItem(["تفصیلی‌ها"])
        root.setData(0, Qt.UserRole, ("root", None))
        root.setToolTip(0, "همهٔ گروه‌ها و تفصیلی‌ها")
        self.tree.addTopLevelItem(root)

        payload_by_id = {item.id: (item, values) for item, values in payload}
        for group in sorted(groups.values(), key=lambda row: (row.code, row.name)):
            if gid is not None and group.id != gid:
                continue
            group_node = QTreeWidgetItem([f"{group.code} {group.name}"])
            group_node.setData(0, Qt.UserRole, ("group", group.id))
            group_node.setToolTip(0, f"گروه تفصیلی: {group.name}")
            root.addChild(group_node)

            # A detail can belong to multiple reporting groups. It appears in
            # each applicable branch, while its stored parent-child relation
            # remains unchanged. Ancestors are included to keep paths legible.
            group_visible = {
                ident for ident, (item, _values) in payload_by_id.items() if group.id in item.group_ids
            }
            pending = list(group_visible)
            while pending:
                current_id = pending.pop()
                current = payload_by_id.get(current_id)
                if current is None:
                    continue
                parent_id = current[0].parent_id
                if parent_id in payload_by_id and parent_id not in group_visible:
                    group_visible.add(parent_id)
                    pending.append(parent_id)

            nodes: dict[int, QTreeWidgetItem] = {}
            for ident in sorted(group_visible, key=lambda value: payload_by_id[value][0].code):
                item, _values = payload_by_id[ident]
                node = QTreeWidgetItem([item.display])
                node.setData(0, Qt.UserRole, item.id)
                node.setToolTip(0, f"تفصیلی {item.code} — {item.name}")
                nodes[ident] = node
                self._tree_items_by_id.setdefault(ident, []).append(node)
            for ident, node in nodes.items():
                parent_id = payload_by_id[ident][0].parent_id
                if parent_id in nodes:
                    nodes[parent_id].addChild(node)
                else:
                    group_node.addChild(node)

        root.setExpanded(True)
        for index in range(root.childCount()):
            root.child(index).setExpanded(gid is not None)
        self._reloading = False

        target = root
        if gid is not None:
            for index in range(root.childCount()):
                if root.child(index).data(0, Qt.UserRole) == ("group", gid):
                    target = root.child(index)
                    break
        self.tree.setCurrentItem(target)
        self._render_table_for_item(target)

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 0) is not None:
            ident = self.table.item(row, 0).data(Qt.UserRole)
            if isinstance(ident, int):
                return ident
        node = self.tree.currentItem()
        data = node.data(0, Qt.UserRole) if node else None
        return data if isinstance(data, int) else None

    def _tree_selection_changed(self, current, _previous) -> None:
        if self._reloading or self._syncing_selection or current is None:
            return
        data = current.data(0, Qt.UserRole)
        if isinstance(data, tuple) and data[0] in {"root", "group"}:
            wanted = data[1] if data[0] == "group" else None
            if self.filter.currentData() != wanted:
                index = self.filter.findData(wanted)
                if index >= 0:
                    self.filter.blockSignals(True)
                    self.filter.setCurrentIndex(index)
                    self.filter.blockSignals(False)
                    self.reload()
                    return
        self._render_table_for_item(current)

    def _render_table_for_item(self, node: QTreeWidgetItem) -> None:
        data = node.data(0, Qt.UserRole)
        selected: list[tuple[object, list[str]]]
        if isinstance(data, int):
            include = {data}
            children_by_parent: dict[int, list[int]] = {}
            for ident, (item, _values) in self._rows_by_id.items():
                if item.parent_id is not None:
                    children_by_parent.setdefault(item.parent_id, []).append(ident)
            pending = [data]
            while pending:
                current_id = pending.pop()
                for child_id in children_by_parent.get(current_id, []):
                    if child_id not in include:
                        include.add(child_id)
                        pending.append(child_id)
            selected = [self._rows_by_id[ident] for ident in include if ident in self._rows_by_id]
            entry = self._rows_by_id.get(data)
            title = entry[0].display if entry else "تفصیلی"
        elif isinstance(data, tuple) and data[0] == "group":
            group_id = data[1]
            selected = [
                entry for entry in self._rows_by_id.values() if group_id in entry[0].group_ids
            ]
            group = next((g for g in self.ctx.refdata.groups if g.id == group_id), None)
            title = f"{group.code} {group.name}" if group else "گروه تفصیلی"
        else:
            selected = list(self._rows_by_id.values())
            title = "همهٔ تفصیلی‌ها" if self.filter.currentData() is None else "تفصیلی‌های گروه"

        selected.sort(key=lambda entry: (entry[0].code, entry[0].name))
        self._syncing_selection = True
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(len(selected))
        for row, (item, values) in enumerate(selected):
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, item.id)
                if column == 4:
                    cell.setToolTip(self._meoin_tooltips.get(item.id, value))
                self.table.setItem(row, column, cell)
        self.table.blockSignals(False)
        self._syncing_selection = False
        self.selection_title.setText(f"{title}  ·  {len(selected)} مورد")
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setShowGrid(False)

    def _table_selection_changed(self) -> None:
        if self._syncing_selection:
            return
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return
        ident = self.table.item(row, 0).data(Qt.UserRole)
        candidates = self._tree_items_by_id.get(ident, [])
        if candidates:
            self._syncing_selection = True
            self.tree.setCurrentItem(candidates[0])
            self._syncing_selection = False

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
