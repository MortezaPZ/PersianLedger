from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
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
from app.ui import icons, theme
from app.ui.views.accounts_view import AccountsView
from app.ui.views.audit_view import AuditView
from app.ui.views.browse_view import BrowseView
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.views.document_list_view import DocumentListView
from app.ui.views.journal_view import JournalView
from app.ui.views.ledger_view import LedgerView
from app.ui.views.income_statement_view import IncomeStatementView
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
            ("income", "صورت سود و زیان", "Ctrl+Shift+2", IncomeStatementView),
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
        width = min(max(window.width(), 1), screen.width())
        height = min(max(window.height(), 1), screen.height())
        x = screen.x() + max(0, (screen.width() - width) // 2)
        y = screen.y() + max(0, (screen.height() - height) // 2)
        window.setGeometry(x, y, width, height)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        title_suffix = f" — {ctx.display_name}" if ctx.display_name else ""
        self.setWindowTitle(f"{APP_NAME_FA} {APP_VERSION}{title_suffix}")
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
        pal = theme.current_palette()
        panel = QFrame()
        panel.setObjectName("NavPanel")
        panel.setFixedWidth(244)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("NavHeader")
        head = QVBoxLayout(header)
        head.setContentsMargins(18, 18, 18, 16)
        head.setSpacing(2)
        title = QLabel(APP_NAME_FA); title.setObjectName("NavTitle")
        sub = QLabel(f"نسخه {APP_VERSION}"); sub.setObjectName("NavSubtitle")
        head.addWidget(title); head.addWidget(sub)
        outer.addWidget(header)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget(); inner.setObjectName("NavInner")
        col = QVBoxLayout(inner); col.setContentsMargins(0, 4, 0, 12); col.setSpacing(0)
        self.buttons = QButtonGroup(self); self.buttons.setExclusive(True)
        self._nav_buttons: list[tuple[QPushButton, str]] = []
        index = 0
        for section, pages in SECTIONS:
            label = QLabel(section); label.setObjectName("NavSection"); col.addWidget(label)
            for key, title_text, shortcut, _cls in pages:
                btn = QPushButton(title_text)
                btn.setIcon(icons.page_icon(key, pal.ink_text))
                btn.setIconSize(QSize(18, 18))
                btn.setCheckable(True)
                btn.setToolTip(f"{title_text}  ({shortcut})")
                btn.setCursor(Qt.PointingHandCursor)
                self.buttons.addButton(btn, index)
                btn.clicked.connect(lambda _=False, i=index: self.go_to(i))
                QShortcut(QKeySequence(shortcut), self, activated=lambda i=index: self.go_to(i))
                col.addWidget(btn)
                self._nav_buttons.append((btn, key))
                index += 1
        col.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return panel

    def restyle_nav(self) -> None:
        """Re-tint the nav icons after a theme change (active one stays white)."""
        pal = theme.current_palette()
        icons.clear_cache()
        for btn, key in getattr(self, "_nav_buttons", ()):
            colour = pal.text_on_brand if btn.isChecked() else pal.ink_text
            btn.setIcon(icons.page_icon(key, colour))

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
        self.restyle_nav()
        view = self.views[index]
        if hasattr(view, "refresh"):
            view.refresh()

    def _restore_geometry(self) -> None:
        settings = QSettings("PersianLedger", "desktop")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _make_exit_backup_box(self) -> QMessageBox:
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME_FA)
        box.setText("آیا می‌خواهید قبل از خروج یک نسخه پشتیبان تهیه شود؟")
        box.addButton("بله", QMessageBox.YesRole)
        box.addButton("خیر", QMessageBox.NoRole)
        box.addButton("انصراف", QMessageBox.RejectRole)
        return box

    def _query_exit_backup(self) -> str:
        box = self._make_exit_backup_box()
        box.exec()
        clicked = box.clickedButton()
        role = box.buttonRole(clicked) if clicked is not None else QMessageBox.RejectRole
        if role == QMessageBox.RejectRole:
            return "cancel"
        if role == QMessageBox.YesRole:
            return "yes"
        return "no"

    def closeEvent(self, event) -> None:
        choice = self._query_exit_backup()
        if choice == "cancel":
            event.ignore()
            return
        if choice == "yes":
            try:
                info = backup_service.create(engine_module.get_engine(), self.ctx.config)
                QMessageBox.information(self, APP_NAME_FA, f"پشتیبان ذخیره شد:\n{info.path}")
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME_FA, str(exc))
                event.ignore()
                return
        QSettings("PersianLedger", "desktop").setValue("geometry", self.saveGeometry())
        event.accept()
