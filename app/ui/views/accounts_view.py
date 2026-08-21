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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
)

from app.domain.enums import ACCOUNT_NATURE_FA, ACCOUNT_TYPE_FA, AccountNature, AccountType
from app.domain.errors import LedgerError
from app.services import account_service
from app.ui.views.base_view import BaseView
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
        for item, label in ACCOUNT_NATURE_FA.items():
            self.nature.addItem(label, item)
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
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if account:
            self.code.setText(account.code)
            self.name.setText(account.name)
            idx = self.nature.findData(account.nature)
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
    hint = "گروه ← کل ← معین. سند فقط روی معین ثبت می‌شود."

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
        self.body.addWidget(self.tree)
        self.reload()

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.tree.clear()
        with self.ctx.read_session() as db:
            groups = account_service.account_groups(db)
            accounts = account_service.all_accounts(db, include_inactive=True)
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
                moin = QTreeWidgetItem([child.display, ACCOUNT_NATURE_FA.get(child.nature, ""), "معین" if child.is_active else "غیرفعال"])
                moin.setData(0, Qt.UserRole, ("account", child.id))
                kol.addChild(moin)
        self.tree.expandAll()

    def _current_account(self):
        item = self.tree.currentItem()
        if not item:
            return None
        kind, ident = item.data(0, Qt.UserRole) or (None, None)
        if kind != "account":
            return None
        with self.ctx.read_session() as db:
            from app.db.models import Account
            return db.get(Account, ident)

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
        acc = self._current_account()
        if not acc:
            return
        if AccountDialog(self.ctx, self, account=acc).exec():
            self.ctx.reload_refdata(); self.reload()
