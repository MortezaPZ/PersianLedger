from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from app.db.models import Document, Tafsili
from app.domain.enums import DocumentStatus
from app.ui import icons, theme
from app.ui.views.base_view import BaseView


class DashboardView(BaseView):
    """At-a-glance workspace with read-only counts and recent documents."""

    title = "میزکار"
    hint = "نمای کلی سال مالی و دسترسی سریع به کارهای روزانه"
    scrollable = True

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self.navigate_requested: Callable[[str], None] = lambda _key: None
        self.open_document_requested: Callable[[int], None] = lambda _doc_id: None
        self._metric_values: dict[str, QLabel] = {}
        self._metric_icons: list[tuple[QLabel, str]] = []

        self.hero = QFrame()
        self.hero.setObjectName("DashboardHero")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(20)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(6)
        self.greeting = QLabel()
        self.greeting.setObjectName("HeroTitle")
        self.period = QLabel()
        self.period.setObjectName("HeroHint")
        self.period.setWordWrap(True)
        hero_text.addWidget(self.greeting)
        hero_text.addWidget(self.period)
        hero_layout.addLayout(hero_text, 1)
        self.new_document = QPushButton("ثبت سند جدید")
        self.new_document.setProperty("kind", "hero")
        self.new_document.setIcon(icons.icon("plus", "#ffffff", 18))
        self.new_document.setIconSize(QSize(18, 18))
        self.new_document.clicked.connect(lambda: self.navigate_requested("entry"))
        hero_layout.addWidget(self.new_document, 0, Qt.AlignVCenter)
        self.body.addWidget(self.hero)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(12)
        metric_grid.setVerticalSpacing(12)
        metrics = (
            ("documents", "اسناد این سال مالی", "document"),
            ("posted", "اسناد قطعی", "check"),
            ("drafts", "پیش‌نویس‌ها", "edit"),
            ("tafsilis", "تفصیلی‌های فعال", "tag"),
        )
        for column, (key, caption, icon_name) in enumerate(metrics):
            card, value_label, icon_label = self._metric_card(caption, icon_name)
            self._metric_values[key] = value_label
            self._metric_icons.append((icon_label, icon_name))
            metric_grid.addWidget(card, 0, column)
            metric_grid.setColumnStretch(column, 1)
        self.body.addLayout(metric_grid)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        recent_card = QFrame()
        recent_card.setObjectName("Card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(16, 14, 16, 14)
        recent_layout.setSpacing(10)
        recent_head = QHBoxLayout()
        recent_title = QLabel("آخرین اسناد")
        recent_title.setObjectName("SectionTitle")
        self.recent_hint = QLabel("برای بازکردن سند، روی ردیف آن دوبار کلیک کنید.")
        self.recent_hint.setObjectName("Hint")
        recent_head.addWidget(recent_title)
        recent_head.addStretch()
        recent_head.addWidget(self.recent_hint)
        recent_layout.addLayout(recent_head)
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(("شماره", "تاریخ", "شرح", "وضعیت"))
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_table.setSelectionMode(QTableWidget.SingleSelection)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setShowGrid(False)
        self.recent_table.verticalHeader().hide()
        self.recent_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for column in (0, 1, 3):
            self.recent_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.recent_table.setMinimumHeight(240)
        self.recent_table.cellDoubleClicked.connect(self._open_selected_document)
        recent_layout.addWidget(self.recent_table)
        self.recent_empty = QLabel("هنوز سندی در این سال مالی ثبت نشده است.")
        self.recent_empty.setObjectName("EmptyState")
        self.recent_empty.setAlignment(Qt.AlignCenter)
        self.recent_empty.setMinimumHeight(110)
        recent_layout.addWidget(self.recent_empty)
        bottom.addWidget(recent_card, 3)

        shortcuts = QFrame()
        shortcuts.setObjectName("Card")
        shortcuts.setMinimumWidth(220)
        shortcut_layout = QVBoxLayout(shortcuts)
        shortcut_layout.setContentsMargins(16, 14, 16, 14)
        shortcut_layout.setSpacing(10)
        shortcut_title = QLabel("دسترسی سریع")
        shortcut_title.setObjectName("SectionTitle")
        shortcut_layout.addWidget(shortcut_title)
        self._shortcut_buttons: list[tuple[QPushButton, str]] = []
        for key, caption, page_icon in (
            ("list", "فهرست اسناد", "list"),
            ("browse", "مرور حساب‌ها", "folder"),
            ("trial", "تراز آزمایشی", "balance"),
            ("accounts", "درخت سرفصل‌ها", "tree"),
        ):
            button = QPushButton(caption)
            button.setProperty("kind", "dashboard-link")
            button.setIcon(icons.icon(page_icon, theme.current_palette().brand, 18))
            button.clicked.connect(lambda _checked=False, page=key: self.navigate_requested(page))
            shortcut_layout.addWidget(button)
            self._shortcut_buttons.append((button, page_icon))
        shortcut_layout.addStretch(1)
        self.body.addLayout(bottom)
        bottom.addWidget(shortcuts, 1)
        self.refresh()

    @staticmethod
    def _metric_card(caption: str, icon_name: str) -> tuple[QWidget, QLabel, QLabel]:
        pal = theme.current_palette()
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(12)
        accent = QFrame()
        accent.setObjectName("MetricAccent")
        accent.setFixedSize(4, 48)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        value = QLabel("—")
        value.setObjectName("MetricValue")
        label = QLabel(caption)
        label.setObjectName("MetricCaption")
        copy.addWidget(value)
        copy.addWidget(label)
        glyph = QLabel()
        glyph.setObjectName("MetricIcon")
        glyph.setPixmap(icons.icon(icon_name, pal.brand, 22).pixmap(22, 22))
        layout.addWidget(accent)
        layout.addLayout(copy, 1)
        layout.addWidget(glyph, 0, Qt.AlignTop)
        return card, value, glyph

    def restyle(self) -> None:
        pal = theme.current_palette()
        for icon_label, icon_name in self._metric_icons:
            icon_label.setPixmap(icons.icon(icon_name, pal.brand, 22).pixmap(22, 22))
        for button, icon_name in self._shortcut_buttons:
            button.setIcon(icons.icon(icon_name, pal.brand, 18))

    def refresh(self) -> None:
        user = (self.ctx.display_name or "همکار گرامی").strip()
        self.greeting.setText(f"سلام {user}، خوش آمدید")
        fiscal_title = self.ctx.fiscal_year_title
        period_text = (
            f"نمای کلی عملکرد در سال مالی {fiscal_title}"
            if fiscal_title
            else "سال مالی فعالی تعریف نشده است."
        )
        self.period.setText(period_text)

        year_id = self.ctx.fiscal_year_id
        counts = {"documents": 0, "posted": 0, "drafts": 0, "tafsilis": 0}
        recent: list[Document] = []
        with self.ctx.read_session() as db:
            if year_id is not None:
                grouped = db.execute(
                    select(Document.status, func.count(Document.id))
                    .where(Document.fiscal_year_id == year_id)
                    .group_by(Document.status)
                )
                for status, count in grouped:
                    counts["documents"] += int(count)
                    if status == DocumentStatus.POSTED:
                        counts["posted"] = int(count)
                    elif status == DocumentStatus.DRAFT:
                        counts["drafts"] = int(count)
                recent = list(
                    db.execute(
                        select(Document)
                        .where(Document.fiscal_year_id == year_id)
                        .order_by(Document.date_g.desc(), Document.number.desc(), Document.id.desc())
                        .limit(6)
                    ).scalars()
                )
            counts["tafsilis"] = int(
                db.execute(select(func.count(Tafsili.id)).where(Tafsili.is_active.is_(True))).scalar_one()
            )

        for key, value in counts.items():
            self._metric_values[key].setText(f"{value:,}")
        self._populate_recent(recent)

    def _populate_recent(self, documents: list[Document]) -> None:
        self.recent_table.setRowCount(len(documents))
        for row, doc in enumerate(documents):
            status = "قطعی" if doc.status == DocumentStatus.POSTED else "پیش‌نویس"
            values = (doc.number_display, doc.date_j, doc.description, status)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, doc.id)
                if column == 3:
                    pal = theme.current_palette()
                    is_posted = doc.status == DocumentStatus.POSTED
                    item.setForeground(QColor(pal.success if is_posted else pal.warning))
                    item.setTextAlignment(Qt.AlignCenter)
                self.recent_table.setItem(row, column, item)
            self.recent_table.setRowHeight(row, 38)
        has_documents = bool(documents)
        self.recent_table.setVisible(has_documents)
        self.recent_empty.setVisible(not has_documents)

    def _open_selected_document(self, row: int, _column: int) -> None:
        item = self.recent_table.item(row, 0)
        document_id = item.data(Qt.UserRole) if item else None
        if document_id is not None:
            self.open_document_requested(int(document_id))
