from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from app.services import attachment_service


class AttachmentPanel(QWidget):
    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.document = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("پیوست‌ها")
        title.setStyleSheet("font-weight:bold;")
        layout.addWidget(title)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        self.add_btn = QPushButton("افزودن")
        self.open_btn = QPushButton("باز کردن")
        self.save_btn = QPushButton("ذخیره نسخه")
        self.remove_btn = QPushButton("حذف")
        self.remove_btn.setProperty("kind", "danger")
        self.add_btn.clicked.connect(self.add_files)
        self.open_btn.clicked.connect(self.open_selected)
        self.save_btn.clicked.connect(self.save_copy)
        self.remove_btn.clicked.connect(self.remove_selected)
        for btn in (self.add_btn, self.open_btn, self.save_btn, self.remove_btn):
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        self.set_document(None)

    def set_document(self, document) -> None:
        self.document = document
        self.list.clear()
        enabled = document is not None and document.id is not None
        self.add_btn.setEnabled(enabled and not (document and document.is_posted))
        self.remove_btn.setEnabled(enabled and not (document and document.is_posted))
        if not document:
            return
        for att in document.attachments:
            item = QListWidgetItem(f"{att.original_name}  ({att.size_bytes // 1024} KB)")
            item.setData(Qt.UserRole, att)
            self.list.addItem(item)

    def add_files(self) -> None:
        if not self.document:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "افزودن پیوست")
        if not files:
            return
        with self.ctx.session() as db:
            doc = db.merge(self.document)
            for path in files:
                attachment_service.add(db, self.ctx.config, doc, Path(path))
            db.refresh(doc)
            self.document = doc
        self.set_document(self.document)

    def _current(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def open_selected(self) -> None:
        att = self._current()
        if not att:
            return
        path = attachment_service.absolute_path(self.ctx.config, att)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def save_copy(self) -> None:
        att = self._current()
        if not att:
            return
        dest, _ = QFileDialog.getSaveFileName(self, "ذخیره نسخه", att.original_name)
        if dest:
            attachment_service.export_copy(self.ctx.config, att, Path(dest))

    def remove_selected(self) -> None:
        att = self._current()
        if not att or not self.document:
            return
        with self.ctx.session() as db:
            doc = db.merge(self.document)
            attachment_service.remove(db, self.ctx.config, db.merge(att), doc)
        self.set_document(self.document)
