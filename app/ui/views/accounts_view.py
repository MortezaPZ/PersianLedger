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
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from app.domain.enums import ACCOUNT_NATURE_FA, ACCOUNT_TYPE_FA, NATURE_CHOICES, AccountType, normalize_nature
from app.domain.errors import LedgerError
from app.services import account_service
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.version import APP_NAME_FA


class AccountDialog(QDialog):
    def __init__(self, context, parent=None, parent_account=None, account=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.parent_account = parent_account
        self.account = account
        self.setWindowTitle("سرفصل")
        self.setLayoutDirection(Qt.RightToLeft)
        form = QFormLayout(self)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.nature = QComboBox()
        for item in NATURE_CHOICES:
            self.nature.addItem(ACCOUNT_NATURE_FA[item], item)
        self.t1_req = QCheckBox("تفصیلی ۱ الزامی است")
        self.t2_req = QCheckBox("تفصیلی ۲ الزامی است")
        self.g1 = QListWidget(); self.g2 = QListWidget()
        for box in (self.g1, self.g2):
            box.setSelectionMode(QAbstractItemView.NoSelection)
            box.setMaximumHeight(90)
        for g in context.refdata.groups:
            for box in (self.g1, self.g2):
                it = QListWidgetItem(f"{g.code} {g.name}")
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                it.setData(Qt.UserRole, g.id)
                box.addItem(it)
        self.type = QComboBox()
        for item, label in ACCOUNT_TYPE_FA.items():
            self.type.addItem(label, item)
        form.addRow("کد", self.code)
        form.addRow("نام", self.name)
        if parent_account is None and account is None:
            form.addRow("نوع", self.type)
        form.addRow("ماهیت", self.nature)
        form.addRow(self.t1_req)
        form.addRow("گروه‌های مجاز تفصیلی ۱", self.g1)
        form.addRow(self.t2_req)
        form.addRow("گروه‌های مجاز تفصیلی ۲", self.g2)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        fields.localize_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if account:
            self.code.setText(account.code)
            self.name.setText(account.name)
            idx = self.nature.findData(normalize_nature(account.nature))
            if idx >= 0:
                self.nature.setCurrentIndex(idx)
            self.t1_req.setChecked(account.tafsili1_required)
            self.t2_req.setChecked(account.tafsili2_required)
            allowed = {(r.tafsili_group_id, r.slot) for r in account.tafsili_rules}
            for i in range(self.g1.count()):
                if (self.g1.item(i).data(Qt.UserRole), 1) in allowed:
                    self.g1.item(i).setCheckState(Qt.Checked)
                if (self.g2.item(i).data(Qt.UserRole), 2) in allowed:
                    self.g2.item(i).setCheckState(Qt.Checked)

    def rules(self) -> list[tuple[int, int]]:
        out = []
        for i in range(self.g1.count()):
            if self.g1.item(i).checkState() == Qt.Checked:
                out.append((self.g1.item(i).data(Qt.UserRole), 1))
            if self.g2.item(i).checkState() == Qt.Checked:
                out.append((self.g2.item(i).data(Qt.UserRole), 2))
        return out

    def accept(self) -> None:
        try:
            with self.ctx.session() as db:
                if self.account is None:
                    kind = self.parent_account.account_type if self.parent_account else self.type.currentData()
                    group_id = None
                    if self.parent_account is None:
                        match = next((g for g in account_service.account_groups(db) if g.account_type == kind), None)
                        group_id = match.id if match else None
                    account_service.create(
                        db,
                        code=self.code.text(),
                        name=self.name.text(),
                        parent_id=self.parent_account.id if self.parent_account else None,
                        group_id=group_id,
                        account_type=kind,
                        nature=self.nature.currentData(),
                        tafsili1_required=self.t1_req.isChecked(),
                        tafsili2_required=self.t2_req.isChecked(),
                        tafsili_rules=self.rules(),
                        user_id=self.ctx.user_id,
                    )
                else:
                    account_service.update(
                        db,
                        db.merge(self.account),
                        code=self.code.text(),
                        name=self.name.text(),
                        nature=self.nature.currentData(),
                        tafsili1_required=self.t1_req.isChecked(),
                        tafsili2_required=self.t2_req.isChecked(),
                        tafsili_rules=self.rules(),
                        user_id=self.ctx.user_id,
                    )
            super().accept()
        except LedgerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, APP_NAME_FA, str(exc))


class AccountsView(BaseView):
    title = "درخت سرفصل‌ها"
    hint = "گروه ← کل ← معین ← تفصیلی۱ و ۲. دابل‌کلیک یا دکمه ویرایش برای تغییر."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        bar = QHBoxLayout()
        kol = QPushButton("کل جدید"); kol.clicked.connect(self.add_kol)
        moin = QPushButton("معین جدید"); moin.setProperty("kind", "primary"); moin.clicked.connect(self.add_moin)
        edit = QPushButton("ویرایش"); edit.clicked.connect(self.edit)
        bar.addWidget(kol); bar.addWidget(moin); bar.addWidget(edit); bar.addStretch()
        self.body.addLayout(bar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["کد / عنوان", "نوع", "وضعیت"])
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit())
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        # The name column carries the hierarchy and needs the room; otherwise
        # the last column stretches by default and elides the account titles.
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setAlternatingRowColors(True)
        self.body.addWidget(self.tree)
        self.reload()

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.tree.clear()
        with self.ctx.read_session() as db:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.db.models import Tafsili

            groups = account_service.account_groups(db)
            accounts = account_service.all_accounts(db, include_inactive=True)
            tafsilis = list(
                db.execute(
                    select(Tafsili).options(selectinload(Tafsili.memberships), selectinload(Tafsili.group))
                ).scalars()
            )
        by_parent = {}
        for acc in accounts:
            by_parent.setdefault(acc.parent_id, []).append(acc)
        group_nodes = {}
        for group in groups:
            node = QTreeWidgetItem([group.display, ACCOUNT_TYPE_FA.get(group.account_type, ""), "گروه"])
            node.setData(0, Qt.UserRole, ("group", group.id))
            self.tree.addTopLevelItem(node)
            group_nodes[group.id] = node
        for acc in by_parent.get(None, []):
            parent_node = group_nodes.get(acc.group_id) or self.tree.invisibleRootItem()
            kol = QTreeWidgetItem([acc.display, ACCOUNT_TYPE_FA.get(acc.account_type, ""), "کل"])
            kol.setData(0, Qt.UserRole, ("account", acc.id))
            parent_node.addChild(kol)
            for child in by_parent.get(acc.id, []):
                moin = QTreeWidgetItem([child.display, ACCOUNT_NATURE_FA.get(normalize_nature(child.nature), ""), "معین" if child.is_active else "غیرفعال"])
                moin.setData(0, Qt.UserRole, ("account", child.id))
                kol.addChild(moin)
                by_slot: dict[int, list[int]] = {1: [], 2: []}
                for rule in child.tafsili_rules:
                    by_slot.setdefault(rule.slot, []).append(rule.tafsili_group_id)
                for slot in (1, 2):
                    gids = set(by_slot.get(slot) or [])
                    if not gids:
                        continue
                    slot_node = QTreeWidgetItem([f"تفصیلی {slot}", "", "خانه سند"])
                    slot_node.setData(0, Qt.UserRole, ("slot", child.id))
                    moin.addChild(slot_node)
                    for item in tafsilis:
                        if item.group_ids & gids:
                            leaf = QTreeWidgetItem([item.display, item.group.name if item.group else "", "تفصیلی"])
                            leaf.setData(0, Qt.UserRole, ("tafsili", item.id))
                            slot_node.addChild(leaf)
        self.tree.expandToDepth(2)

    def _current_payload(self):
        item = self.tree.currentItem()
        if not item:
            return None, None
        data = item.data(0, Qt.UserRole) or (None, None)
        return data[0], data[1] if len(data) > 1 else None

    def _current_account(self):
        kind, ident = self._current_payload()
        if kind != "account":
            return None
        with self.ctx.read_session() as db:
            from app.db.models import Account
            return db.get(Account, ident)

    def _menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("کل جدید", self.add_kol)
        menu.addAction("معین جدید", self.add_moin)
        menu.addAction("ویرایش", self.edit)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def add_kol(self) -> None:
        if AccountDialog(self.ctx, self).exec():
            self.ctx.reload_refdata(); self.reload()

    def add_moin(self) -> None:
        acc = self._current_account()
        parent = acc if acc and acc.level == 1 else (acc.parent if acc else None)
        if parent is None:
            self.warn("ابتدا یک سرفصل کل را انتخاب کنید.")
            return
        if AccountDialog(self.ctx, self, parent_account=parent).exec():
            self.ctx.reload_refdata(); self.reload()

    def edit(self) -> None:
        kind, ident = self._current_payload()
        if kind == "group":
            self.warn("گروه حساب از نوع دارایی/بدهی است و از همین‌جا ویرایش نمی‌شود. کل یا معین را انتخاب کنید.")
            return
        if kind == "slot":
            self.warn("خانه تفصیلی را از ویرایش معین تنظیم کنید.")
            return
        if kind == "tafsili":
            from app.db.models import Tafsili
            from app.ui.views.tafsili_view import TafsiliDialog
            with self.ctx.read_session() as db:
                item = db.get(Tafsili, ident)
            if item and TafsiliDialog(self.ctx, self, item=item).exec():
                self.ctx.reload_refdata()
                self.reload()
            return
        acc = self._current_account()
        if not acc:
            self.warn("یک سرفصل کل یا معین را انتخاب کنید.")
            return
        if AccountDialog(self.ctx, self, account=acc).exec():
            self.ctx.reload_refdata(); self.reload()
