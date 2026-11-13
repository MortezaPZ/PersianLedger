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
from app.domain.permissions import Perm
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
    COL_DESC,
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
    hint = "هر ارز جداگانه تراز می‌شود. تفصیلی ۱ و ۲ دو بُعد مستقل‌اند؛ با انتخاب تفصیلی، فهرست معین به اتصال‌های مجاز محدود می‌شود."
    scrollable = True

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.document = None
        self.document_id: int | None = None
        self.document_row_version: int | None = None
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
        self.type_combo.setToolTip(
            "نوع سند برای دسته‌بندی و گزارش است. در افتتاحیه، ارزهای فعال و مجاز هر سرفصل باید مشخص شوند."
        )
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
        self.opening_hint = QLabel(
            "برای هر سرفصلِ دارای مانده، یک ردیف به‌ازای هر ارز فعال و مجاز داشته باشید؛ "
            "اگر ماندهٔ ارزی صفر است، مبلغ را خالی بگذارید."
        )
        self.opening_hint.setWordWrap(True)
        self.opening_hint.setVisible(False)
        self.body.addWidget(self.opening_hint)
        self.model = LineGridModel(self.ctx.refdata)
        self.table = QTableView()
        self.table.setAccessibleName("ردیف‌های سند")
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
        self.table.selectionModel().currentRowChanged.connect(lambda *_: self._refresh_balance())
        self.body.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        add = QPushButton("افزودن ردیف")
        add.setProperty("kind", "secondary")
        dup = QPushButton("تکرار ردیف")
        dup.setProperty("kind", "ghost")
        remove = QPushButton("حذف ردیف")
        remove.setProperty("kind", "danger")
        add.clicked.connect(lambda: self.model.add_row())
        dup.clicked.connect(lambda: self.model.add_row(True))
        remove.clicked.connect(lambda: self.model.remove_row(self.table.currentIndex().row() if self.table.currentIndex().isValid() else len(self.model.rows) - 1))
        buttons.addWidget(add)
        buttons.addWidget(dup)
        buttons.addWidget(remove)
        self.opening_currency_btn = QPushButton("تکمیل ارزهای سرفصل")
        self.opening_currency_btn.setProperty("kind", "secondary")
        self.opening_currency_btn.setToolTip(
            "برای سرفصل ردیف جاری، ردیف ارزهای فعال و مجاز را اضافه می‌کند."
        )
        self.opening_currency_btn.clicked.connect(self._complete_current_account_currencies)
        self.opening_currency_btn.setVisible(False)
        buttons.addWidget(self.opening_currency_btn)
        buttons.addStretch()
        self.save_btn = QPushButton("ذخیره پیش‌نویس")
        self.save_btn.setProperty("kind", "secondary")
        self.post_btn = QPushButton("ثبت قطعی سند")
        self.post_btn.setProperty("kind", "primary")
        self.new_btn = QPushButton("سند جدید")
        self.new_btn.setProperty("kind", "ghost")
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
        self.model.dataChanged.connect(self._opening_row_changed)
        self.type_combo.currentIndexChanged.connect(lambda *_: self._update_opening_controls())
        self.ctx.refdataChanged.connect(self.refresh)
        self.refresh()
        self._update_opening_controls()
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
        opening = self.type_combo.currentData() == DocumentType.OPENING
        if opening:
            self._complete_opening_currency_rows()
        rows = self.model.rows if opening else self.model.filled_rows()
        if opening:
            rows = [row for row in rows if row.account_id and row.currency_id is not None]
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
                for r in rows
            ],
        )

    def _update_opening_controls(self) -> None:
        opening = self.type_combo.currentData() == DocumentType.OPENING
        self.opening_hint.setVisible(opening)
        self.opening_currency_btn.setVisible(opening)
        if opening:
            self._complete_opening_currency_rows()

    def _opening_row_changed(self, top_left, _bottom_right, *_roles) -> None:
        if self.type_combo.currentData() != DocumentType.OPENING or not top_left.isValid():
            return
        if getattr(self, "_syncing_opening_currencies", False):
            return
        row = self.model.rows[top_left.row()]
        # Once the user has started entering this account's opening balance,
        # add the remaining currency rows using the same tafsili dimensions.
        if row.account_id and (row.debit or row.credit or row.tafsili1_id or row.tafsili2_id):
            self._complete_account_currencies(row)

    def _complete_current_account_currencies(self) -> None:
        index = self.table.currentIndex()
        if not index.isValid() or not (0 <= index.row() < len(self.model.rows)):
            self.warn("ابتدا سرفصل را در ردیف جاری انتخاب کنید.")
            return
        row = self.model.rows[index.row()]
        if not row.account_id:
            self.warn("ابتدا سرفصل را در ردیف جاری انتخاب کنید.")
            return
        before = len(self.model.rows)
        self._complete_account_currencies(row)
        if len(self.model.rows) == before:
            self.inform("ردیف ارزهای مجاز این سرفصل از قبل کامل است.")

    def _complete_opening_currency_rows(self) -> None:
        if getattr(self, "_syncing_opening_currencies", False):
            return
        account_ids = list(dict.fromkeys(row.account_id for row in self.model.rows if row.account_id))
        for account_id in account_ids:
            row = next(row for row in self.model.rows if row.account_id == account_id)
            self._complete_account_currencies(row)

    def _complete_account_currencies(self, template: LineRow) -> None:
        if self.type_combo.currentData() != DocumentType.OPENING or not template.account_id:
            return
        currencies = self.ctx.refdata.currencies_for(template.account_id)
        if not currencies:
            return
        existing = {
            row.currency_id
            for row in self.model.rows
            if row.account_id == template.account_id and row.currency_id is not None
        }
        missing = [currency.id for currency in currencies if currency.id not in existing]
        if not missing:
            return

        account_id = template.account_id
        tafsili1_id = template.tafsili1_id
        tafsili2_id = template.tafsili2_id
        description = template.description
        self._syncing_opening_currencies = True
        try:
            for currency_id in missing:
                row_index = next(
                    (
                        i for i, row in enumerate(self.model.rows)
                        if row.account_id is None and not row.debit and not row.credit and not row.description
                    ),
                    None,
                )
                if row_index is None:
                    self.model.add_row()
                    row_index = len(self.model.rows) - 1
                self.model.setData(self.model.index(row_index, COL_ACCOUNT), account_id)
                if tafsili1_id is not None:
                    self.model.setData(self.model.index(row_index, COL_T1), tafsili1_id)
                if tafsili2_id is not None:
                    self.model.setData(self.model.index(row_index, COL_T2), tafsili2_id)
                self.model.setData(self.model.index(row_index, COL_CURRENCY), currency_id)
                if description:
                    self.model.setData(self.model.index(row_index, COL_DESC), description)
        finally:
            self._syncing_opening_currencies = False

    def _remember(self, doc) -> None:
        """Keep identity in plain values.

        A rolled-back session expires every object it touched, so an ORM
        instance held across sessions can become permanently unreadable. Only
        the id survives that, and it is all we need to load the row again.
        """
        self.document = doc
        self.document_id = doc.id if doc is not None else None
        self.document_row_version = getattr(doc, "row_version", None) if doc is not None else None

    def save_draft(self) -> None:
        try:
            with self.ctx.session() as db:
                data = self._input()
                current = document_service.load(db, self.document_id) if self.document_id else None
                doc = document_service.save_draft(
                    db, data, current, self.ctx.user_id, expected_row_version=self.document_row_version
                )
                db.refresh(doc)
                list(doc.attachments)
                number = doc.number
            self._remember(doc)
            self.number_edit.setText(str(number))
            self.attachments.set_document(doc)
            self.inform(f"پیش‌نویس شماره {number} ذخیره شد.")
            self.ctx.dataChanged.emit()
        except LedgerError as exc:
            self.warn(str(exc).replace("والد آن", "شاخهٔ بالاتر آن"))
            if isinstance(exc, ConcurrencyError) and self.document_id:
                self.load_document(self.document_id)
        except Exception as exc:
            self.report_error(exc)

    def post(self) -> None:
        try:
            with self.ctx.session() as db:
                data = self._input()
                current = document_service.load(db, self.document_id) if self.document_id else None
                doc = document_service.save_and_post(
                    db, data, current, self.ctx.user_id, expected_row_version=self.document_row_version
                )
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
            self.warn(str(exc).replace("والد آن", "شاخهٔ بالاتر آن"))
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
            if doc.doc_type == DocumentType.OPENING:
                self._complete_opening_currency_rows()
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
        balance_text = "  |  ".join(parts) or "ردیفی وارد نشده"
        index = self.table.currentIndex()
        if index.isValid() and 0 <= index.row() < len(self.model.rows):
            row = self.model.rows[index.row()]
            account = self.ctx.refdata.account_by_id.get(row.account_id or 0)
            tafsili1 = self.ctx.refdata.tafsili_by_id.get(row.tafsili1_id or 0)
            tafsili2 = self.ctx.refdata.tafsili_by_id.get(row.tafsili2_id or 0)
            line = [f"حساب: {account.posting_display}" if account else "حساب: —"]
            line.append(f"تفصیلی ۱: {tafsili1.display if tafsili1 else '—'}")
            line.append(f"تفصیلی ۲: {tafsili2.display if tafsili2 else '—'}")
            balance_text += "\nسطر فعال — " + " | ".join(line)
        self.balance.setText(balance_text)
        if not parts:
            name = "BalanceBar"
        else:
            name = "BalanceOk" if ok else "BalanceBad"
        self.balance.setObjectName(name)
        style = self.balance.style()
        style.unpolish(self.balance)
        style.polish(self.balance)
        self.save_btn.setEnabled(self.ctx.can(Perm.DOC_DRAFT) and not self.model.read_only)
        self.save_btn.setToolTip("" if self.ctx.can(Perm.DOC_DRAFT) else "دسترسی لازم را ندارید")
        can_post = self.ctx.can(Perm.DOC_POST)
        self.post_btn.setEnabled(ok and len(self.model.filled_rows()) >= 2 and not self.model.read_only and can_post)
        self.post_btn.setToolTip("" if can_post else "دسترسی لازم را ندارید")

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
