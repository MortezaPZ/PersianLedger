from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


TreeChoice = tuple[int, str, int | None, bool]


class TreePickerDialog(QDialog):
    """Small reusable tree dialog; rows are (id, label, parent_id, selectable)."""

    def __init__(
        self,
        title: str,
        choices: list[TreeChoice],
        selected_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(620, 520)
        self.selected_id: int | None = None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setObjectName("TreePickerSearch")
        self.search.setPlaceholderText("جست‌وجو در درخت…")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.tree, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)

        nodes: dict[int, QTreeWidgetItem] = {}
        parents: dict[int, int | None] = {}
        selectable: set[int] = set()
        for ident, label, parent_id, can_select in choices:
            node = QTreeWidgetItem([label])
            node.setData(0, Qt.UserRole, ident)
            if can_select:
                selectable.add(ident)
            else:
                node.setForeground(0, self.palette().brush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text))
                node.setToolTip(0, "این شاخه را باز کنید و یکی از موارد پایین‌تر را انتخاب کنید.")
            nodes[ident] = node
            parents[ident] = parent_id
        self._selectable_ids = selectable
        for ident, node in nodes.items():
            parent_id = parents[ident]
            if parent_id in nodes:
                nodes[parent_id].addChild(node)
            else:
                self.tree.addTopLevelItem(node)
        if selected_id in nodes:
            self.tree.setCurrentItem(nodes[selected_id])
            parent_node = nodes[selected_id].parent()
            while parent_node is not None:
                parent_node.setExpanded(True)
                parent_node = parent_node.parent()
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.search.textChanged.connect(self._filter_tree)
        self._selection_changed(self.tree.currentItem(), None)

    def _filter_tree(self, query: str) -> None:
        needle = (query or "").strip().casefold()
        def visit(item: QTreeWidgetItem, parent_matches: bool = False) -> bool:
            matches = bool(needle) and needle in item.text(0).casefold()
            show_subtree = parent_matches or matches
            descendant_matches = False
            for position in range(item.childCount()):
                child_matches = visit(item.child(position), show_subtree)
                descendant_matches = descendant_matches or child_matches
            visible = not needle or show_subtree or descendant_matches
            item.setHidden(not visible)
            if needle and visible and item.childCount() and (show_subtree or descendant_matches):
                item.setExpanded(True)
            elif not needle:
                item.setExpanded(False)
            return visible

        root = self.tree.invisibleRootItem()
        for position in range(root.childCount()):
            visit(root.child(position))
        current = self.tree.currentItem()
        if current is not None and current.isHidden():
            self.tree.setCurrentItem(None)
        elif not needle and current is not None:
            parent = current.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()

    def _selection_changed(self, current, _previous) -> None:
        ident = current.data(0, Qt.UserRole) if current else None
        self.selected_id = ident if ident in self._selectable_ids else None
        self.ok_button.setEnabled(self.selected_id is not None)

    def _activate(self, item, _column) -> None:
        ident = item.data(0, Qt.UserRole)
        if ident in self._selectable_ids:
            self.selected_id = ident
            self.accept()
        else:
            item.setExpanded(not item.isExpanded())
