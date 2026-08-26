"""Editable document-line grid: model, delegates and per-currency totals."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QComboBox, QCompleter, QStyledItemDelegate, QStyle

from app.domain import money
from app.ui import theme
from app.ui.refdata import RefData

COL_NO, COL_ACCOUNT, COL_T1, COL_T2, COL_CURRENCY, COL_DEBIT, COL_CREDIT, COL_DESC = range(8)
HEADERS = ("ردیف", "سرفصل", "تفصیلی ۱", "تفصیلی ۲", "ارز", "بدهکار", "بستانکار", "شرح")
PICKER_COLUMNS = {COL_ACCOUNT, COL_T1, COL_T2, COL_CURRENCY}
NEW_TAFSILI = -1
NEW_TAFSILI_LABEL = "+  تعریف تفصیلی جدید…"


@dataclass
class LineRow:
    account_id: int | None = None
    tafsili1_id: int | None = None
    tafsili2_id: int | None = None
    currency_id: int | None = None
    debit: Decimal = field(default_factory=lambda: Decimal(0))
    credit: Decimal = field(default_factory=lambda: Decimal(0))
    description: str = ""

    @property
    def is_blank(self) -> bool:
        return not self.account_id and not self.debit and not self.credit


class LineGridModel(QAbstractTableModel):
    totalsChanged = Signal()

    def __init__(self, refdata: RefData, parent=None) -> None:
        super().__init__(parent)
        self.ref = refdata
        self.rows: list[LineRow] = [LineRow(), LineRow()]
        self.read_only = False

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return HEADERS[section]
        return None

    def flags(self, index: QModelIndex):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.read_only or index.column() == COL_NO:
            return flags
        row = self.rows[index.row()]
        if index.column() in (COL_T1, COL_T2) and not self.ref.slot_enabled(row.account_id, 1 if index.column() == COL_T1 else 2):
            return flags
        return flags | Qt.ItemIsEditable

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._text(index.row(), row, column, role == Qt.EditRole)
        if role == Qt.TextAlignmentRole:
            if column in (COL_DEBIT, COL_CREDIT):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            if column in (COL_NO, COL_CURRENCY):
                return int(Qt.AlignCenter)
        if role == Qt.ForegroundRole and column in (COL_T1, COL_T2) and not self.ref.slot_enabled(row.account_id, 1 if column == COL_T1 else 2):
            return QBrush(QColor(theme.current_palette().text_faint))
        if role == Qt.BackgroundRole and (row.debit or row.credit) == 0 and row.account_id:
            return QBrush(QColor(theme.current_palette().draft_row))
        return None

    def _text(self, position: int, row: LineRow, column: int, editing: bool) -> str:
        if column == COL_NO:
            return str(position + 1)
        if column == COL_ACCOUNT:
            acc = self.ref.account_by_id.get(row.account_id or 0)
            return acc.display if acc else ""
        if column in (COL_T1, COL_T2):
            slot = 1 if column == COL_T1 else 2
            tid = row.tafsili1_id if slot == 1 else row.tafsili2_id
            item = self.ref.tafsili_by_id.get(tid or 0)
            if item:
                return item.display
            if not row.account_id:
                return "ابتدا سرفصل را انتخاب کنید"
            if not self.ref.slot_enabled(row.account_id, slot):
                return "تعریف نشده — کلیک کنید"
            if not self.ref.tafsilis_for(row.account_id, slot):
                return "کلیک کنید و تعریف کنید"
            if self._slot_required(row, slot):
                return "الزامی"
            return ""
        if column == COL_CURRENCY:
            cur = self.ref.currency_by_id.get(row.currency_id or 0)
            return cur.code if cur else ""
        if column in (COL_DEBIT, COL_CREDIT):
            value = row.debit if column == COL_DEBIT else row.credit
            if not value:
                return ""
            return money.format_amount(value, self._decimals(row))
        if column == COL_DESC:
            return row.description
        return ""

    def _slot_required(self, row: LineRow, slot: int) -> bool:
        return self.ref.slot_required(row.account_id, slot)

    def _decimals(self, row: LineRow) -> int:
        cur = self.ref.currency_by_id.get(row.currency_id or 0)
        return cur.decimals if cur else 0

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid():
            return False
        row = self.rows[index.row()]
        column = index.column()
        if column == COL_ACCOUNT:
            self._set_account(row, int(value) if value not in (None, "") else None)
        elif column == COL_T1:
            row.tafsili1_id = int(value) if value not in (None, "", NEW_TAFSILI) else None
        elif column == COL_T2:
            row.tafsili2_id = int(value) if value not in (None, "", NEW_TAFSILI) else None
        elif column == COL_CURRENCY:
            row.currency_id = int(value) if value not in (None, "") else None
        elif column in (COL_DEBIT, COL_CREDIT):
            try:
                amount = money.parse(value, self._decimals(row))
            except money.MoneyError:
                return False
            if column == COL_DEBIT:
                row.debit = amount
                if amount:
                    row.credit = Decimal(0)
            else:
                row.credit = amount
                if amount:
                    row.debit = Decimal(0)
        elif column == COL_DESC:
            row.description = str(value or "").strip()
        self.dataChanged.emit(index, self.index(index.row(), self.columnCount() - 1))
        self.totalsChanged.emit()
        return True

    def _set_account(self, row: LineRow, account_id: int | None) -> None:
        row.account_id = account_id
        if not self.ref.slot_enabled(account_id, 1):
            row.tafsili1_id = None
        if not self.ref.slot_enabled(account_id, 2):
            row.tafsili2_id = None
        allowed = self.ref.currencies_for(account_id)
        if allowed and (row.currency_id is None or row.currency_id not in {c.id for c in allowed}):
            row.currency_id = allowed[0].id

    def add_row(self, copy_currency_from_last: bool = False) -> None:
        row = LineRow()
        if copy_currency_from_last and self.rows:
            last = self.rows[-1]
            row.account_id = last.account_id
            row.tafsili1_id = last.tafsili1_id
            row.tafsili2_id = last.tafsili2_id
            row.currency_id = last.currency_id
        self.beginInsertRows(QModelIndex(), len(self.rows), len(self.rows))
        self.rows.append(row)
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        if len(self.rows) <= 1:
            self.rows[0] = LineRow()
            self.dataChanged.emit(self.index(0, 0), self.index(0, self.columnCount() - 1))
            self.totalsChanged.emit()
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.rows[row]
        self.endRemoveRows()
        self.totalsChanged.emit()

    def set_rows(self, rows: list[LineRow]) -> None:
        self.beginResetModel()
        self.rows = rows or [LineRow(), LineRow()]
        self.endResetModel()
        self.totalsChanged.emit()

    def filled_rows(self) -> list[LineRow]:
        return [r for r in self.rows if not r.is_blank]

    def totals(self) -> dict[int, tuple[Decimal, Decimal]]:
        result: dict[int, list[Decimal]] = {}
        for row in self.filled_rows():
            if not row.currency_id:
                continue
            bucket = result.setdefault(row.currency_id, [Decimal(0), Decimal(0)])
            bucket[0] += row.debit
            bucket[1] += row.credit
        return {cid: (d, c) for cid, (d, c) in result.items()}


class PickerDelegate(QStyledItemDelegate):
    """Single-click combo with a visible drop-down arrow."""

    requestConfigure = Signal(int, int)  # row, slot
    requestNewTafsili = Signal(int, int)

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setMaxVisibleItems(16)
        combo.view().setMinimumWidth(280)
        combo.view().setTextElideMode(Qt.ElideNone)
        completer = combo.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self._fill(combo, index)
        combo.activated.connect(lambda _i, editor=combo: self._commit(editor))
        return combo

    def _fill(self, combo: QComboBox, index: QModelIndex) -> None:
        raise NotImplementedError

    def setModelData(self, editor, model, index) -> None:
        combo: QComboBox = editor
        model.setData(index, combo.currentData())

    def _commit(self, editor: QComboBox) -> None:
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

    def updateEditorGeometry(self, editor, option, index) -> None:
        editor.setGeometry(option.rect)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            return False
        return super().editorEvent(event, model, option, index)


class AccountDelegate(PickerDelegate):
    def _fill(self, combo: QComboBox, index: QModelIndex) -> None:
        model: LineGridModel = index.model()
        combo.addItem("", None)
        for acc in model.ref.postable:
            combo.addItem(acc.display, acc.id)
        current = model.rows[index.row()].account_id
        if current:
            pos = combo.findData(current)
            if pos >= 0:
                combo.setCurrentIndex(pos)


class TafsiliDelegate(PickerDelegate):
    def __init__(self, slot: int, parent=None) -> None:
        super().__init__(parent)
        self.slot = slot

    def _fill(self, combo: QComboBox, index: QModelIndex) -> None:
        model: LineGridModel = index.model()
        row = model.rows[index.row()]
        if not row.account_id:
            combo.addItem("ابتدا سرفصل را انتخاب کنید", None)
            return
        if not model.ref.slot_enabled(row.account_id, self.slot):
            combo.addItem("تعریف نشده — کلیک کنید", None)
            self.requestConfigure.emit(index.row(), self.slot)
            return
        combo.addItem("", None)
        items = model.ref.tafsilis_for(row.account_id, self.slot)
        for item in items:
            combo.addItem(item.display, item.id)
        combo.addItem(NEW_TAFSILI_LABEL, NEW_TAFSILI)
        current = row.tafsili1_id if self.slot == 1 else row.tafsili2_id
        if current:
            pos = combo.findData(current)
            if pos >= 0:
                combo.setCurrentIndex(pos)

    def setModelData(self, editor, model, index) -> None:
        value = editor.currentData()
        if value == NEW_TAFSILI:
            self.requestNewTafsili.emit(index.row(), self.slot)
            return
        super().setModelData(editor, model, index)


class CurrencyDelegate(PickerDelegate):
    def _fill(self, combo: QComboBox, index: QModelIndex) -> None:
        model: LineGridModel = index.model()
        row = model.rows[index.row()]
        combo.addItem("", None)
        for cur in model.ref.currencies_for(row.account_id):
            combo.addItem(f"{cur.code} — {cur.name}", cur.id)
        if row.currency_id:
            pos = combo.findData(row.currency_id)
            if pos >= 0:
                combo.setCurrentIndex(pos)
