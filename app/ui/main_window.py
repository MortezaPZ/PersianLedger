from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import engine as engine_module
from app.services import backup_service
from app.ui.context import AppContext
from app.ui import icons
from app.ui.views.accounts_view import AccountsView
from app.ui.views.audit_view import AuditView
from app.ui.views.browse_view import BrowseView
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.views.document_list_view import DocumentListView
from app.ui.views.journal_view import JournalView
from app.ui.views.ledger_view import LedgerView
from app.ui.views.party_statement_view import PartyStatementView
from app.ui.views.settings_view import SettingsView
from app.ui.views.statement_view import StatementView
from app.ui.views.tafsili_view import TafsiliView
from app.ui.views.trial_balance_view import TrialBalanceView
from app.version import APP_NAME_FA, APP_VERSION

SECTIONS = (
    (
        "اسناد",
        (
            ("entry", "ثبت سند", "Ctrl+1", DocumentEntryView),
            ("list", "فهرست اسناد", "Ctrl+2", DocumentListView),
        ),
    ),
    (
        "گزارش‌ها",
        (
            ("browse", "مرور حسابها", "Ctrl+3", BrowseView),
            ("statement", "صورتحساب سرفصل", "Ctrl+4", StatementView),
            ("trial", "تراز آزمایشی", "Ctrl+5", TrialBalanceView),
            ("journal", "دفتر روزنامه", "Ctrl+6", JournalView),
            ("ledger", "دفتر کل و معین", "Ctrl+7", LedgerView),
            ("party", "صورت وضعیت اشخاص", "Ctrl+8", PartyStatementView),
        ),
    ),
    (
        "اطلاعات پایه",
        (
            ("accounts", "درخت سرفصل‌ها", "Ctrl+9", AccountsView),
            ("tafsili", "تفصیلی شناور", "Ctrl+0", TafsiliView),
            ("settings", "ارزها و سال مالی", "Ctrl+Shift+1", SettingsView),
        ),
    ),
    (
        "سیستم",
        (("audit", "سوابق تغییرات", "Ctrl+L", AuditView),),
    ),
)

PAGES = tuple((key, title, shortcut, cls) for _section, pages in SECTIONS for key, title, shortcut, cls in pages)


def clamp_to_screen(window: QMainWindow) -> None:
    screen = QGuiApplication.primaryScreen().availableGeometry()
    geo = window.frameGeometry()
    if geo.width() > screen.width() or geo.height() > screen.height() or not screen.intersects(geo):
        window.resize(min(window.width(), screen.width()), min(window.height(), screen.height()))
        frame = window.frameGeometry()
        window.move(screen.center() - frame.center())


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_NAME_FA} {APP_VERSION}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1280, 800)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.views = []
        for _key, _title, _shortcut, cls in PAGES:
            view = cls(ctx)
            self.views.append(view)
            self.stack.addWidget(view)
        self._wire()
        layout.addWidget(self._build_nav())
        layout.addWidget(self.stack, 1)
        self._build_status_bar()
        self._restore_geometry()
        clamp_to_screen(self)
        self.go_to(0)

    def _build_nav(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("NavPanel")
        panel.setFixedWidth(232)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        title = QLabel(APP_NAME_FA); title.setObjectName("NavTitle")
        sub = QLabel(f"نسخه {APP_VERSION}"); sub.setObjectName("NavSubtitle")
        outer.addWidget(title); outer.addWidget(sub)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget(); inner.setObjectName("NavInner")
        col = QVBoxLayout(inner); col.setContentsMargins(0, 0, 0, 8)
        self.buttons = QButtonGroup(self); self.buttons.setExclusive(True)
        index = 0
        for section, pages in SECTIONS:
            label = QLabel(section); label.setObjectName("NavSection"); col.addWidget(label)
            for key, title_text, shortcut, _cls in pages:
                btn = QPushButton(title_text)
                btn.setIcon(icons.page_icon(key))
                btn.setIconSize(btn.iconSize())
                btn.setCheckable(True)
                btn.setToolTip(shortcut)
                btn.setCursor(Qt.PointingHandCursor)
                self.buttons.addButton(btn, index)
                btn.clicked.connect(lambda _=False, i=index: self.go_to(i))
                QShortcut(QKeySequence(shortcut), self, activated=lambda i=index: self.go_to(i))
                col.addWidget(btn)
                index += 1
        col.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return panel

    def _wire(self) -> None:
        entry: DocumentEntryView = self.views[0]
        listing: DocumentListView = self.views[1]
        listing.open_requested = lambda doc_id: (entry.load_document(doc_id), self.go_to(0))
        for view in self.views:
            if isinstance(view, SettingsView):
                view.after_restore = self._after_restore
        self.ctx.dataChanged.connect(self._refresh_status)

    def _after_restore(self) -> None:
        for view in self.views:
            if hasattr(view, "refresh"):
                view.refresh()
        clamp_to_screen(self)
        self._refresh_status()

    def _build_status_bar(self) -> None:
        self.status = self.statusBar()
        self.year_label = QLabel()
        self.path_label = QLabel()
        self.status.addPermanentWidget(self.year_label)
        self.status.addWidget(self.path_label, 1)
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.year_label.setText(f"سال مالی {self.ctx.fiscal_year_title}")
        self.path_label.setText(self.ctx.config.describe())

    def go_to(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        btn = self.buttons.button(index)
        if btn:
            btn.setChecked(True)
        view = self.views[index]
        if hasattr(view, "refresh"):
            view.refresh()

    def _restore_geometry(self) -> None:
        settings = QSettings("PersianLedger", "desktop")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME_FA)
        box.setText("آیا می‌خواهید قبل از خروج یک نسخه پشتیبان تهیه شود؟")
        yes = box.addButton("بله", QMessageBox.YesRole)
        no = box.addButton("خیر", QMessageBox.NoRole)
        cancel = box.addButton("انصراف", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            event.ignore()
            return
        if clicked is yes:
            try:
                info = backup_service.create(engine_module.get_engine(), self.ctx.config)
                QMessageBox.information(self, APP_NAME_FA, f"پشتیبان ذخیره شد:\n{info.path}")
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME_FA, str(exc))
                event.ignore()
                return
        QSettings("PersianLedger", "desktop").setValue("geometry", self.saveGeometry())
        event.accept()
