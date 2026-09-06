from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem

from app.domain.enums import DOCUMENT_STATUS_FA, DOCUMENT_TYPE_FA, DocumentStatus, DocumentType
from app.domain.permissions import Perm
from app.domain.errors import LedgerError
from app.db.models import Document
from app.domain import jalali
from app.services import document_service
from app.ui import theme
from app.ui.views.base_view import BaseView
from app.ui.widgets.jalali_date_edit import JalaliDateEdit
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.tables import fit_columns
from sqlalchemy import select


class DocumentListView(BaseView):
    title = "فهرست اسناد"
    hint = "جستجو، مشاهده، برگشت و اصلاح اسناد"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.open_requested = None
        bar = QHBoxLayout()
        self.from_date = JalaliDateEdit(); self.from_date.clear()
        self.to_date = JalaliDateEdit(); self.to_date.clear()
        self.status = QComboBox(); self.status.addItem("همه", None)
        self.status.addItem("پیش‌نویس", DocumentStatus.DRAFT)
        self.status.addItem("قطعی", DocumentStatus.POSTED)
        self.search = QLineEdit(); self.search.setPlaceholderText("جستجو در شرح")
        go = QPushButton("نمایش"); go.setProperty("kind", "primary"); go.clicked.connect(self.reload)
        bar.addWidget(QLabel("از")); bar.addWidget(self.from_date)
        bar.addWidget(QLabel("تا")); bar.addWidget(self.to_date)
        bar.addWidget(combo_with_picker(self.status, "وضعیت سند")); bar.addWidget(self.search); bar.addWidget(go)
        self.body.addLayout(bar)
        actions = QHBoxLayout()
        open_btn = QPushButton("باز کردن"); open_btn.clicked.connect(self.open_current)
        rev = QPushButton("سند برگشتی"); rev.clicked.connect(self.reverse)
        corr = QPushButton("سند اصلاحی"); corr.clicked.connect(self.correct)
        delete = QPushButton("حذف پیش‌نویس"); delete.setProperty("kind", "danger"); delete.clicked.connect(self.delete_draft)
        self.rev_btn = rev
        self.corr_btn = corr
        self.delete_btn = delete
        unpost = QPushButton("بازگردانی به پیش‌نویس")
        unpost.clicked.connect(self.unpost)
        delete_posted = QPushButton("حذف سند قطعی")
        delete_posted.setProperty("kind", "danger")
        delete_posted.clicked.connect(self.delete_posted)
        self.unpost_btn = unpost
        self.delete_posted_btn = delete_posted
        actions.addWidget(open_btn); actions.addWidget(rev); actions.addWidget(corr); actions.addWidget(delete)
        actions.addWidget(unpost)
        actions.addWidget(delete_posted)
        actions.addStretch()
        self.body.addLayout(actions)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["شماره", "تاریخ", "نوع", "شرح", "وضعیت", "ردیف‌ها"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.open_current)
        self.body.addWidget(self.table)
        self._apply_permissions()
        self.reload()

    def _apply_permissions(self) -> None:
        mapping = (
            (self.rev_btn, Perm.DOC_REVERSE),
            (self.corr_btn, Perm.DOC_REVERSE),
            (self.delete_btn, Perm.DOC_DRAFT),
            (self.unpost_btn, Perm.DOC_UNPOST),
            (self.delete_posted_btn, Perm.DOC_DELETE_POSTED),
        )
        for widget, perm in mapping:
            ok = self.ctx.can(perm)
            widget.setEnabled(ok)
            widget.setToolTip("" if ok else "دسترسی لازم را ندارید")

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        with self.ctx.read_session() as db:
            stmt = select(Document).order_by(Document.date_g.desc(), Document.number.desc())
            status = self.status.currentData()
            if status:
                stmt = stmt.where(Document.status == status)
            date_from = self.from_date.gregorian()
            if date_from:
                stmt = stmt.where(Document.date_g >= date_from)
            date_to = self.to_date.gregorian()
            if date_to:
                stmt = stmt.where(Document.date_g <= date_to)
            if self.search.text().strip():
                stmt = stmt.where(Document.description.contains(self.search.text().strip()))
            docs = list(db.execute(stmt.limit(500)).scalars())
            rows = [
                (
                    doc.id,
                    doc.number_display,
                    doc.date_j,
                    DOCUMENT_TYPE_FA.get(doc.doc_type, ""),
                    doc.description,
                    DOCUMENT_STATUS_FA.get(doc.status, ""),
                    str(len(doc.lines)),
                    doc.status,
                )
                for doc in docs
            ]
        self.table.setRowCount(len(rows))
        draft_tint = QBrush(QColor(theme.current_palette().draft_row))
        for r, (doc_id, *values, status) in enumerate(rows):
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, doc_id)
                if status == DocumentStatus.DRAFT:
                    item.setBackground(draft_tint)
                self.table.setItem(r, c, item)
        fit_columns(self.table)

    def _id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def open_current(self) -> None:
        doc_id = self._id()
        if doc_id and callable(self.open_requested):
            self.open_requested(doc_id)

    def reverse(self) -> None:
        doc_id = self._id()
        if not doc_id:
            return
        try:
            with self.ctx.session() as db:
                original = document_service.load(db, doc_id)
                today = jalali.today_jalali()
                document_service.reverse(db, original, jalali.to_gregorian(today), jalali.format_jalali(today), user_id=self.ctx.user_id)
            self.inform("سند برگشتی ثبت شد.")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def correct(self) -> None:
        doc_id = self._id()
        if not doc_id:
            return
        try:
            with self.ctx.session() as db:
                original = document_service.load(db, doc_id)
                today = jalali.today_jalali()
                _rev, draft = document_service.create_correction_draft(db, original, jalali.to_gregorian(today), jalali.format_jalali(today), self.ctx.user_id)
                draft_id = draft.id
            if callable(self.open_requested):
                self.open_requested(draft_id)
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def delete_draft(self) -> None:
        doc_id = self._id()
        if not doc_id or not self.confirm("پیش‌نویس حذف شود؟"):
            return
        try:
            with self.ctx.session() as db:
                document_service.delete_draft(db, document_service.load(db, doc_id), self.ctx.user_id)
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def unpost(self) -> None:
        doc_id = self._id()
        if not doc_id:
            return
        try:
            with self.ctx.session() as db:
                doc = document_service.load(db, doc_id)
                n = doc.number if doc else ""
            if not self.confirm(
                f"سند شماره {n} به پیش‌نویس برمی‌گردد و از گزارش‌ها حذف می‌شود تا دوباره قطعی شود. ادامه می‌دهید؟"
            ):
                return
            with self.ctx.session() as db:
                document_service.unpost(db, document_service.load(db, doc_id), self.ctx.user_id)
            self.inform("سند به پیش‌نویس بازگشت.")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))

    def delete_posted(self) -> None:
        doc_id = self._id()
        if not doc_id:
            return
        try:
            with self.ctx.session() as db:
                doc = document_service.load(db, doc_id)
                n = doc.number if doc else ""
            if not self.confirm(
                f"سند قطعی شماره {n} برای همیشه حذف می‌شود. این کار در سوابق تغییرات ثبت می‌شود. ادامه می‌دهید؟"
            ):
                return
            with self.ctx.session() as db:
                document_service.delete_posted(db, document_service.load(db, doc_id), self.ctx.user_id)
            self.inform("سند حذف شد.")
            self.reload()
        except LedgerError as exc:
            self.warn(str(exc))
