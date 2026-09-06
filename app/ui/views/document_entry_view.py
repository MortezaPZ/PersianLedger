from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.domain.enums import DOCUMENT_TYPE_FA, DocumentType
from app.domain.errors import ConcurrencyError, LedgerError
from app.services import document_service, master_data
from app.ui.views.base_view import BaseView
from app.ui.widgets import fields
from app.ui.widgets.attachment_panel import AttachmentPanel
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.jalali_date_edit import JalaliDateEdit
from app.ui.widgets.line_grid import (
    COL_ACCOUNT,
    COL_CURRENCY,
    COL_T1,
    COL_T2,
    AccountDelegate,
    CurrencyDelegate,
    LineGridModel,
    LineRow,
    TafsiliDelegate,
)
from app.ui.widgets.tables import fit_columns
from app.version import APP_NAME_FA


class DocumentEntryView(BaseView):
    title = "ثبت سند"
    hint = "هر ارز جداگانه تراز می‌شود. نرخ تسعیر در این برنامه وجود ندارد."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.document = None
        self.document_id: int | None = None
        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        self.number_edit = QLineEdit()
        self.number_edit.setReadOnly(True)
        self.date_edit = JalaliDateEdit()
        self.type_combo = QComboBox()
        for item, label in DOCUMENT_TYPE_FA.items():
            if item not in (DocumentType.REVERSAL, DocumentType.CORRECTION):
                self.type_combo.addItem(label, item)
        self.type_combo.setToolTip("نوع سند فقط برای دسته‌بندی و گزارش است؛ روی تراز یا شماره اثر ندارد.")
        self.desc_edit = QLineEdit()
        self.year_combo = QComboBox()
        grid.addWidget(fields.labeled("شماره سند", self.number_edit), 0, 0)
        grid.addWidget(fields.labeled("تاریخ", self.date_edit), 0, 1)
        grid.addWidget(fields.labeled("نوع سند", combo_with_picker(self.type_combo, "انتخاب نوع سند")), 0, 2)
        grid.addWidget(fields.labeled("سال مالی", combo_with_picker(self.year_combo, "انتخاب سال مالی")), 0, 3)
        grid.addWidget(fields.labeled("شرح سند", self.desc_edit), 1, 0, 1, 4)
        for column in range(4):
            grid.setColumnStretch(column, 1)
        self.body.addWidget(card)
        self.model = LineGridModel(self.ctx.refdata)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(COL_ACCOUNT, AccountDelegate(self.table))
        self.t1 = TafsiliDelegate(1, self.table)
        self.t2 = TafsiliDelegate(2, self.table)
        self.t1.requestNewTafsili.connect(self._new_tafsili)
        self.t2.requestNewTafsili.connect(self._new_tafsili)
        self.table.setItemDelegateForColumn(COL_T1, self.t1)
        self.table.setItemDelegateForColumn(COL_T2, self.t2)
        self.table.setItemDelegateForColumn(COL_CURRENCY, CurrencyDelegate(self.table))
        self.table.setEditTriggers(
            QAbstractItemView.SelectedClicked
            | QAbstractItemView.CurrentChanged
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.body.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        add = QPushButton("افزودن ردیف")
        dup = QPushButton("تکرار ردیف")
        remove = QPushButton("حذف ردیف")
        add.clicked.connect(lambda: self.model.add_row())
        dup.clicked.connect(lambda: self.model.add_row(True))
        remove.clicked.connect(lambda: self.model.remove_row(self.table.currentIndex().row() if self.table.currentIndex().isValid() else len(self.model.rows) - 1))
        buttons.addWidget(add)
        buttons.addWidget(dup)
        buttons.addWidget(remove)
        buttons.addStretch()
        self.save_btn = QPushButton("ذخیره پیش‌نویس")
        self.post_btn = QPushButton("ثبت قطعی سند")
        self.post_btn.setProperty("kind", "primary")
        self.new_btn = QPushButton("سند جدید")
        self.save_btn.clicked.connect(self.save_draft)
        self.post_btn.clicked.connect(self.post)
        self.new_btn.clicked.connect(self.new_document)
        buttons.addWidget(self.new_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.post_btn)
        self.body.addLayout(buttons)
        bottom = QHBoxLayout()
        self.balance = QLabel()
        self.balance.setObjectName("BalanceBar")
        self.balance.setWordWrap(True)
        # Without this the label stretches to match the attachment panel beside
        # it and turns into a large empty slab.
        self.balance.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.balance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bottom.addWidget(self.balance, 1, Qt.AlignTop)
        self.attachments = AttachmentPanel(self.ctx)
        self.attachments.setMaximumHeight(180)
        bottom.addWidget(self.attachments)
        self.body.addLayout(bottom)
        self.model.totalsChanged.connect(self._refresh_balance)
        self.ctx.refdataChanged.connect(self.refresh)
        self.refresh()
        # Trailing column is the line description; let it take the spare width.
        fit_columns(self.table, stretch_last=True)

    def refresh(self) -> None:
        self.year_combo.clear()
        for year in self.ctx.fiscal_years():
            self.year_combo.addItem(year.title, year.id)
            if year.id == self.ctx.fiscal_year_id:
                self.year_combo.setCurrentIndex(self.year_combo.count() - 1)
        with self.ctx.read_session() as db:
            year = next((y for y in master_data.fiscal_years(db) if y.id == self.ctx.fiscal_year_id), None)
            preview = document_service.next_number_preview(db, year) if year else 1
        if self.document is None:
            self.number_edit.setText(f"پیشنهادی {preview}")
        self._refresh_balance()

    def _input(self) -> document_service.DocumentInput:
        return document_service.DocumentInput(
            fiscal_year_id=self.year_combo.currentData(),
            date_g=self.date_edit.gregorian(),
            date_j=self.date_edit.jalali_text(),
            doc_type=self.type_combo.currentData() or DocumentType.GENERAL,
            description=self.desc_edit.text(),
            lines=[
                document_service.LineInput(
                    account_id=r.account_id,
                    currency_id=r.currency_id,
                    debit=r.debit,
                    credit=r.credit,
                    tafsili1_id=r.tafsili1_id,
                    tafsili2_id=r.tafsili2_id,
                    description=r.description,
                )
                for r in self.model.filled_rows()
            ],
        )

    def _remember(self, doc) -> None:
        """Keep identity in plain values.

        A rolled-back session expires every object it touched, so an ORM
        instance held across sessions can become permanently unreadable. Only
        the id survives that, and it is all we need to load the row again.
        """
        self.document = doc
        self.document_id = doc.id if doc is not None else None

    def save_draft(self) -> None:
        try:
            with self.ctx.session() as db:
                data = self._input()
                current = document_service.load(db, self.document_id) if self.document_id else None
                doc = document_service.save_draft(db, data, current, self.ctx.user_id)
                db.refresh(doc)
                list(doc.attachments)
                number = doc.number
            self._remember(doc)
            self.number_edit.setText(str(number))
            self.attachments.set_document(doc)
            self.inform(f"پیش‌نویس شماره {number} ذخیره شد.")
            self.ctx.dataChanged.emit()
        except LedgerError as exc:
            self.warn(str(exc))
            if isinstance(exc, ConcurrencyError) and self.document_id:
                self.load_document(self.document_id)
        except Exception as exc:
            self.report_error(exc)

    def post(self) -> None:
        try:
            with self.ctx.session() as db:
                data = self._input()
                current = document_service.load(db, self.document_id) if self.document_id else None
                doc = document_service.save_and_post(db, data, current, self.ctx.user_id)
                master_data.lock_used_currencies(db)
                list(doc.attachments)
                number = doc.number
            self._remember(doc)
            self.number_edit.setText(str(number))
            self.model.read_only = True
            self.attachments.set_document(doc)
            self.inform(f"سند شماره {number} قطعی شد.")
            self.ctx.dataChanged.emit()
            self.ctx.reload_refdata()
        except LedgerError as exc:
            self.warn(str(exc))
            if isinstance(exc, ConcurrencyError) and self.document_id:
                self.load_document(self.document_id)
        except Exception as exc:
            self.report_error(exc)

    def _abandon_open_draft(self) -> bool:
        if not self.document_id:
            return True
        with self.ctx.read_session() as db:
            current = document_service.load(db, self.document_id)
            if current is None or current.is_posted:
                return True
            number = current.number
        if not self.confirm(
            f"پیش‌نویس شماره {number} هنوز قطعی نشده. با ادامه، حذف می‌شود و شماره آزاد می‌گردد."
        ):
            return False
        try:
            with self.ctx.session() as db:
                current = document_service.load(db, self.document_id)
                if current and not current.is_posted:
                    document_service.delete_draft(db, current, self.ctx.user_id)
            self.ctx.dataChanged.emit()
        except LedgerError as exc:
            self.warn(str(exc))
            return False
        return True

    def new_document(self) -> None:
        if not self._abandon_open_draft():
            return
        self.clear()

    def load_document(self, document_id: int) -> None:
        if self.document_id and self.document_id != document_id:
            if not self._abandon_open_draft():
                return
            self._remember(None)
        with self.ctx.read_session() as db:
            doc = document_service.load(db, document_id)
            self._remember(doc)
            if not doc:
                return
            self.number_edit.setText(doc.number_display)
            self.date_edit.setText(doc.date_j)
            idx = self.type_combo.findData(doc.doc_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.desc_edit.setText(doc.description)
            rows = [
                LineRow(
                    ln.account_id,
                    ln.tafsili1_id,
                    ln.tafsili2_id,
                    ln.currency_id,
                    ln.debit,
                    ln.credit,
                    ln.description or "",
                )
                for ln in doc.lines
            ]
            self.model.set_rows(rows)
            self.model.read_only = doc.is_posted
            self.attachments.set_document(doc)

    def reset_after_restore(self) -> None:
        self.clear()

    def clear(self) -> None:
        self._remember(None)
        self.model.read_only = False
        self.model.set_rows([LineRow(), LineRow()])
        self.desc_edit.clear()
        self.attachments.set_document(None)
        self.refresh()

    def _refresh_balance(self) -> None:
        parts = []
        ok = True
        for cid, (debit, credit) in self.model.totals().items():
            cur = self.ctx.refdata.currency_by_id.get(cid)
            if not cur:
                continue
            diff = debit - credit
            if diff:
                ok = False
            parts.append(f"{cur.code}: بد {debit} / بس {credit}")
        self.balance.setText("  |  ".join(parts) or "ردیفی وارد نشده")
        if not parts:
            name = "BalanceBar"
        else:
            name = "BalanceOk" if ok else "BalanceBad"
        self.balance.setObjectName(name)
        style = self.balance.style()
        style.unpolish(self.balance)
        style.polish(self.balance)
        self.post_btn.setEnabled(ok and len(self.model.filled_rows()) >= 2 and not self.model.read_only)

    def _new_tafsili(self, row: int, slot: int) -> None:
        from app.ui.views.tafsili_view import TafsiliDialog

        dialog = TafsiliDialog(self.ctx, self)
        if dialog.exec():
            self.ctx.reload_refdata()
            self.model.ref = self.ctx.refdata
            if dialog.created_id is not None:
                column = COL_T1 if slot == 1 else COL_T2
                index = self.model.index(row, column)
                self.model.setData(index, dialog.created_id)
