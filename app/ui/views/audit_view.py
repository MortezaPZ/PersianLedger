from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QTableWidget, QTableWidgetItem
from sqlalchemy import select

from app.db.models import AuditLog
from app.domain.enums import AUDIT_ACTION_FA
from app.ui.views.base_view import BaseView
from app.ui.widgets.pickers import combo_with_picker
from app.ui.widgets.tables import fit_columns


class AuditView(BaseView):
    title = "سوابق تغییرات"
    hint = "هر ایجاد، ویرایش، قطعی کردن و برگشت در این جدول ثبت می‌شود."

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        bar = QHBoxLayout()
        self.entity = QComboBox(); self.entity.addItems(["همه", "Document", "Account", "Tafsili", "Currency", "FiscalYear"])
        self.entity.currentIndexChanged.connect(self.reload)
        bar.addWidget(QLabel("موضوع")); bar.addWidget(combo_with_picker(self.entity, "موضوع")); bar.addStretch()
        self.body.addLayout(bar)
        split = QHBoxLayout()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["زمان", "موضوع", "عملیات", "شناسه", "یادداشت"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.currentCellChanged.connect(self._show)
        self.detail = QPlainTextEdit(); self.detail.setReadOnly(True)
        split.addWidget(self.table, 3)
        split.addWidget(self.detail, 2)
        self.body.addLayout(split, 1)
        self.reload()

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        with self.ctx.read_session() as db:
            stmt = select(AuditLog).order_by(AuditLog.at.desc()).limit(500)
            entity = self.entity.currentText()
            if entity != "همه":
                stmt = stmt.where(AuditLog.entity_type == entity)
            rows = list(db.execute(stmt).scalars())
        self.table.setRowCount(len(rows))
        self._rows = rows
        for r, log in enumerate(rows):
            values = [str(log.at), log.entity_type, AUDIT_ACTION_FA.get(log.action, log.action.value), str(log.entity_id or ""), log.note or ""]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))
        fit_columns(self.table)

    def _show(self, row: int) -> None:
        if row < 0 or row >= len(getattr(self, "_rows", [])):
            return
        log = self._rows[row]
        self.detail.setPlainText(f"قبل:\n{log.before_json or '—'}\n\nبعد:\n{log.after_json or '—'}")
