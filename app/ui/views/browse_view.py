from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from app.db.models import Account
from app.domain.enums import DocumentType
from app.export import excel, printing
from app.services import ledger_reports as lr
from app.services.report_service import StatementFilter
from app.ui.views.report_base import ReportView
from app.ui.views.trial_balance_view import TrialBalanceModel
from app.ui.widgets.tables import fit_columns


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child = item.layout()
        if child is not None:
            _clear_layout(child)


class BrowseView(ReportView):
    title = "مرور حسابها"
    hint = "از گروه شروع کنید و با دابل‌کلیک روی هر سطر یک سطح پایین‌تر بروید. گردش و مانده هر ارز در ستون‌های خودش نمایش داده می‌شود."
    file_stem = "مرور-حسابها"

    def __init__(self, context, parent=None) -> None:
        super().__init__(context, parent)
        self._level = lr.LEVEL_GROUP
        self._trail: list[tuple[int, str, str]] = []
        self.from_date, self.to_date = self.make_date_range()
        self.add_filter("از تاریخ", self.from_date)
        self.add_filter("تا تاریخ", self.to_date)
        self.add_filter("ارزها", self.make_currency_list())
        special = QWidget()
        special_row = QHBoxLayout(special)
        special_row.setContentsMargins(0, 0, 0, 0)
        self.chk_opening = QCheckBox("افتتاحیه")
        self.chk_closing = QCheckBox("اختتامیه")
        self.chk_close_books = QCheckBox("بستن حساب‌ها")
        for box in (self.chk_opening, self.chk_closing, self.chk_close_books):
            special_row.addWidget(box)
        special_row.addStretch()
        self.add_filter("اسناد خاص", special)
        self.finish_filters()

        chrome = QFrame()
        chrome.setObjectName("BrowseChrome")
        chrome_layout = QVBoxLayout(chrome)
        chrome_layout.setContentsMargins(12, 12, 12, 12)
        chrome_layout.setSpacing(8)

        stepper = QFrame()
        stepper.setObjectName("LevelStepper")
        stepper_row = QHBoxLayout(stepper)
        stepper_row.setContentsMargins(4, 4, 4, 4)
        stepper_row.setSpacing(4)
        self.level_buttons: list[tuple[str, QPushButton]] = []
        for index, level in enumerate(lr.BROWSE_LEVELS):
            if index:
                sep = QLabel("←")
                sep.setObjectName("BreadcrumbSep")
                sep.setAlignment(Qt.AlignCenter)
                stepper_row.addWidget(sep)
            btn = QPushButton(lr.BROWSE_LEVEL_FA[level])
            btn.setObjectName("LevelChip")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _=False, lv=level: self.go_to_level(lv))
            self.level_buttons.append((level, btn))
            stepper_row.addWidget(btn)
        stepper_row.addStretch()
        self.up_button = QPushButton("یک سطح بالاتر")
        self.up_button.setObjectName("up")
        self.up_button.setProperty("kind", "ghost")
        self.up_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.up_button.clicked.connect(self.go_up)
        stepper_row.addWidget(self.up_button)
        chrome_layout.addWidget(stepper)

        crumbs = QWidget()
        crumbs.setObjectName("BreadcrumbBar")
        self.crumb_row = QHBoxLayout(crumbs)
        self.crumb_row.setContentsMargins(0, 0, 0, 0)
        self.crumb_row.setSpacing(4)
        chrome_layout.addWidget(crumbs)

        hint = QLabel("دابل‌کلیک روی سطر — یا کلید Enter — یک سطح پایین‌تر می‌رود. روی سطح‌ها یا مسیر بالا کلیک کنید تا برگردید.")
        hint.setObjectName("BrowseHint")
        hint.setWordWrap(True)
        chrome_layout.addWidget(hint)
        self.body.addWidget(chrome)

        self.model = TrialBalanceModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMouseTracking(True)
        self.table.setCursor(QCursor(Qt.PointingHandCursor))
        self.table.setToolTip("دابل‌کلیک برای ورود به سطح بعد")
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.drill_down)
        self.table.installEventFilter(self)
        self.body.addWidget(self.table, 1)

        self.empty = QLabel("در بازه انتخاب‌شده گردشی ثبت نشده است.")
        self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.empty.hide()
        self.body.addWidget(self.empty, 1)

        self.summary.setObjectName("SummaryLine")
        self.reload_currencies()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.table and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.drill_down()
                return True
        return super().eventFilter(obj, event)

    def refresh(self) -> None:
        self.reload_currencies()
        self.run()

    def _filter(self) -> StatementFilter | None:
        kwargs = self.ready_filters()
        if kwargs is None:
            return None
        flt = StatementFilter(**kwargs)
        exclude = []
        if not self.chk_opening.isChecked():
            exclude.append(DocumentType.OPENING)
        if not self.chk_closing.isChecked():
            exclude.append(DocumentType.CLOSING)
        if not self.chk_close_books.isChecked():
            exclude.append(DocumentType.CLOSE_BOOKS)
        flt.exclude_doc_types = exclude
        if not self._trail:
            return flt
        ident = self._trail[-1][0]
        with self.ctx.read_session() as db:
            if self._level == lr.LEVEL_KOL:
                ids = list(db.execute(select(Account.id).where(Account.group_id == ident)).scalars())
                flt.account_ids = ids or [-1]
            elif self._level == lr.LEVEL_MOIN:
                ids = list(db.execute(select(Account.id).where(Account.parent_id == ident)).scalars())
                flt.account_ids = ids or [ident]
            elif self._level in lr.TAFSILI_LEVELS:
                flt.account_id = ident
        return flt

    def _rebuild_crumbs(self) -> None:
        _clear_layout(self.crumb_row)
        labels = ["همه حساب‌ها"] + [label for _key, _from, label in self._trail]
        current = len(labels) - 1
        for index, text in enumerate(labels):
            if index:
                sep = QLabel("‹")
                sep.setObjectName("BreadcrumbSep")
                self.crumb_row.addWidget(sep)
            crumb = QPushButton(text)
            crumb.setObjectName("BreadcrumbCrumb")
            crumb.setCursor(QCursor(Qt.PointingHandCursor))
            crumb.setProperty("current", "true" if index == current else "false")
            crumb.style().unpolish(crumb)
            crumb.style().polish(crumb)
            crumb.clicked.connect(lambda _=False, i=index: self._go_crumb(i))
            self.crumb_row.addWidget(crumb)
        self.crumb_row.addStretch()

    def _go_crumb(self, index: int) -> None:
        self._trail = self._trail[:index]
        self._level = lr.BROWSE_LEVELS[len(self._trail)]
        self.run()

    def run(self) -> None:
        flt = self._filter()
        if flt is None:
            return
        try:
            with self.ctx.read_session() as db:
                self._result = lr.browse_accounts(db, flt, self._level)
            self.model.set_result(self._result)
            fit_columns(self.table)
            for position, (level, btn) in enumerate(self.level_buttons):
                btn.blockSignals(True)
                btn.setChecked(level == self._level)
                btn.blockSignals(False)
            self.up_button.setEnabled(bool(self._trail))
            self._rebuild_crumbs()
            empty = self._result.is_empty
            self.empty.setVisible(empty)
            self.table.setVisible(not empty)
            level_fa = lr.BROWSE_LEVEL_FA.get(self._level, self._level)
            if empty:
                self.summary.setText(f"سطح {level_fa}  |  در بازه انتخاب‌شده گردشی ثبت نشده است.")
            else:
                self.summary.setText(f"سطح {level_fa}  |  {len(self._result.rows)} سطر  |  دابل‌کلیک برای سطح بعد")
        except Exception as exc:
            self.report_error(exc)

    def go_to_level(self, level: str) -> None:
        index = lr.BROWSE_LEVELS.index(level)
        self._trail = self._trail[:index]
        self._level = level
        self.run()

    def go_up(self) -> None:
        if self._trail:
            self._trail.pop()
        self._level = lr.BROWSE_LEVELS[len(self._trail)]
        self.run()

    def drill_down(self) -> None:
        index = self.table.currentIndex()
        if not self._result or not index.isValid():
            return
        row = self._result.rows[index.row()]
        if row.kind == "total" or row.key is None:
            return
        pos = lr.BROWSE_LEVELS.index(self._level)
        if pos >= len(lr.BROWSE_LEVELS) - 1:
            self.inform("پایین‌ترین سطح همین است.")
            return
        self._trail.append((row.key, self._level, f"{row.code} {row.name}".strip()))
        self._level = lr.BROWSE_LEVELS[pos + 1]
        self.run()

    def build_html(self) -> str:
        return printing.trial_balance_html(self._result)

    def write_excel(self, path) -> None:
        excel.export_trial_balance(path, self._result)
