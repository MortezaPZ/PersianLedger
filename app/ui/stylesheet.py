"""Builds the Qt stylesheet from a :class:`~app.ui.palette.Palette`.

One template serves both themes; swapping the palette swaps the whole look,
so a rule can never exist in light mode and be forgotten in dark mode.
"""
from __future__ import annotations

from app.ui.palette import Palette

_TEMPLATE = """
* {{
    font-family: "Vazirmatn", "Sahel", "IRANSans", "Segoe UI", "Tahoma";
    outline: 0;
}}

QWidget {{
    background: {canvas};
    color: {text};
    font-size: 13px;
}}
QMainWindow::separator {{ width: 0; height: 0; }}
QToolTip {{
    background: {ink};
    color: {ink_text};
    border: 1px solid {ink_line};
    border-radius: 6px;
    padding: 6px 10px;
}}

/* ============================ Sidebar ============================ */
#NavPanel, #NavInner, #NavPanel QScrollArea {{
    background: {ink};
    border: none;
}}
#NavHeader {{
    background: {ink};
    border-bottom: 1px solid {ink_line};
}}
#NavMark {{
    background: {brand};
    border: 1px solid {ink_line};
    border-radius: 10px;
}}
#NavMarkText {{
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    background: transparent;
}}
#NavTitle {{
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    background: transparent;
}}
#NavSubtitle {{
    color: {ink_text_dim};
    font-size: 11px;
    background: transparent;
}}
#NavSearch {{
    margin: 10px 12px 6px;
    background: {ink_alt};
    color: #ffffff;
    border: 1px solid {ink_line};
    border-radius: 7px;
    padding: 7px 10px;
    min-height: 20px;
}}
#NavSearch:focus {{ border: 1px solid {focus}; }}
/* No letter-spacing here: Persian script is cursive and spacing breaks the
   joins between letters. */
#NavSection {{
    color: {ink_text_dim};
    font-size: 11px;
    font-weight: bold;
    padding: 18px 18px 6px 18px;
    background: transparent;
}}
#NavPanel QPushButton, #NavInner QPushButton {{
    background: transparent;
    color: {ink_text};
    border: none;
    border-right: 3px solid transparent;
    border-left: 3px solid transparent;
    padding: 10px 18px;
    margin: 1px 8px 1px 8px;
    text-align: right;
    font-size: 13px;
    border-radius: 6px;
    min-height: 22px;
}}
#NavPanel QPushButton:hover, #NavInner QPushButton:hover {{
    background: {ink_alt};
    color: #ffffff;
}}
#NavPanel QPushButton:checked, #NavInner QPushButton:checked {{
    background: {brand};
    color: #ffffff;
    border-right: 3px solid {accent};
    font-weight: bold;
}}
#NavPanel QPushButton:focus, #NavInner QPushButton:focus {{
    border-right: 3px solid {focus};
    border-left: 3px solid {focus};
    background: {ink_alt};
}}
#NavPanel QPushButton:checked:focus, #NavInner QPushButton:checked:focus {{
    border-right: 3px solid {accent};
    border-left: 3px solid {focus};
}}
#NavPanel QScrollBar:vertical {{ background: {ink}; width: 8px; }}
#NavPanel QScrollBar::handle:vertical {{ background: {ink_line}; border-radius: 4px; }}

/* ========================== Page chrome ========================== */
#PageHeader {{
    background: {surface};
    border: 1px solid {line};
    border-right: 3px solid {brand};
    border-radius: 9px;
}}
#PageTitle {{
    font-size: 17px;
    font-weight: bold;
    color: {text};
    background: transparent;
}}
#PageHint {{
    color: {text_muted};
    font-size: 12px;
    background: transparent;
}}
#Card, #BrowseChrome {{
    background: {surface};
    border: 1px solid {line};
    border-radius: 9px;
}}
#DashboardHero {{
    background: {ink};
    border: 1px solid {ink_line};
    border-radius: 14px;
}}
#HeroTitle {{
    color: #ffffff;
    font-size: 21px;
    font-weight: bold;
    background: transparent;
}}
#HeroHint {{
    color: {ink_text};
    font-size: 12px;
    background: transparent;
}}
#MetricCard {{
    background: {surface};
    border: 1px solid {line};
    border-radius: 11px;
}}
#MetricAccent {{ background: {brand}; border: none; border-radius: 2px; }}
#MetricValue {{ color: {text}; font-size: 23px; font-weight: bold; background: transparent; }}
#MetricCaption {{ color: {text_muted}; font-size: 11px; background: transparent; }}
#MetricIcon {{
    background: {brand_soft};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px;
}}
#DashboardHero QPushButton[kind="hero"] {{
    color: #ffffff;
    background: {brand};
    border: 1px solid {brand_hover};
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
}}
#DashboardHero QPushButton[kind="hero"]:hover {{ background: {brand_hover}; }}
#DashboardHero QPushButton[kind="hero"]:focus {{ border: 2px solid {focus}; }}
QPushButton[kind="dashboard-link"] {{
    color: {text};
    background: {surface_alt};
    border: 1px solid {line};
    border-radius: 7px;
    padding: 9px 12px;
    text-align: right;
}}
QPushButton[kind="dashboard-link"]:hover {{
    color: {brand};
    background: {brand_soft};
    border-color: {brand};
}}
/* Plain containers must not paint the canvas colour over a card they sit on. */
#FilterField {{ background: transparent; }}
#FieldLabel {{
    color: {text_muted};
    font-size: 11px;
    font-weight: bold;
    background: transparent;
    padding: 0 2px 2px 2px;
}}
#Hint {{
    color: {text_faint};
    font-size: 11px;
    background: transparent;
}}
#SummaryLine {{
    color: {text};
    font-weight: bold;
    padding: 2px 4px;
    background: transparent;
}}
#SectionTitle {{
    font-weight: bold;
    color: {text};
    background: transparent;
}}

/* ============================ Inputs ============================= */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
QPlainTextEdit, QTextEdit {{
    background: {surface};
    color: {text};
    border: 1px solid {line_strong};
    border-radius: 7px;
    padding: 7px 10px;
    min-height: 23px;
    selection-background-color: {brand};
    selection-color: #ffffff;
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
QSpinBox:hover, QPlainTextEdit:hover {{
    border-color: {text_faint};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {focus};
}}
QLineEdit:read-only {{ background: {surface_muted}; color: {text_muted}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
    background: {surface_muted};
    color: {text_faint};
    border-color: {line};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: left;
    width: 26px;
    border: none;
    background: transparent;
}}
/* Styling drop-down stops Qt drawing its native arrow, which then degrades to
   a dot, so the chevron is supplied as an image. */
QComboBox::down-arrow, QDateEdit::down-arrow, QSpinBox::down-arrow {{
    image: url({chevron});
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {overlay};
    color: {text};
    border: 1px solid {line_strong};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {brand_soft};
    selection-color: {text};
}}

/* ============================ Buttons ============================ */
QPushButton {{
    background: {surface};
    color: {text};
    border: 1px solid {line_strong};
    border-radius: 7px;
    padding: 7px 15px;
    min-height: 24px;
}}
QPushButton:hover {{ background: {surface_alt}; border-color: {text_faint}; }}
QPushButton:pressed {{ background: {surface_muted}; }}
QPushButton:focus {{ border: 1px solid {focus}; }}
QPushButton:disabled {{
    color: {text_faint};
    background: {surface_muted};
    border-color: {line};
}}

QPushButton[kind="primary"] {{
    background: {brand};
    color: #ffffff;
    border: 1px solid {brand};
    font-weight: bold;
}}
QPushButton[kind="primary"]:hover {{
    background: {brand_hover};
    border-color: {brand_hover};
}}
QPushButton[kind="primary"]:disabled {{
    background: {surface_muted};
    color: {text_faint};
    border-color: {line};
}}

QPushButton[kind="secondary"] {{
    background: {brand_soft};
    color: {text};
    border: 1px solid {brand};
    font-weight: bold;
}}
QPushButton[kind="secondary"]:hover {{
    background: {surface_muted};
    border-color: {brand_hover};
}}
QPushButton[kind="secondary"]:disabled {{
    background: {surface_muted};
    color: {text_faint};
    border-color: {line};
}}

#PickerButton {{
    padding: 7px 2px;
    font-size: 15px;
    font-weight: bold;
    color: {text_muted};
}}

QPushButton[kind="danger"] {{
    background: {surface};
    color: {danger};
    border-color: {danger};
}}
QPushButton[kind="danger"]:hover {{ background: {danger_soft}; }}

QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid {line_strong};
    color: {brand};
}}
QPushButton[kind="ghost"]:hover {{ background: {brand_soft}; }}
QPushButton[kind="ghost"]:disabled {{ color: {text_faint}; border-color: {line}; }}
QPushButton[kind="primary"]:focus, QPushButton[kind="secondary"]:focus {{
    border: 2px solid {focus};
}}

/* ====================== Tables / trees / lists =================== */
QTableView, QTreeWidget, QTreeView, QListWidget {{
    background: {surface};
    color: {text};
    border: 1px solid {line};
    border-radius: 9px;
    gridline-color: {grid};
    selection-background-color: {brand_soft};
    selection-color: {text};
    alternate-background-color: {surface_alt};
}}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {surface_muted};
    color: {text_muted};
    border: none;
    border-left: 1px solid {line};
    border-bottom: 2px solid {line_strong};
    padding: 10px 11px;
    font-weight: bold;
    font-size: 12px;
}}
QHeaderView::section:first {{ border-left: none; }}
QTableView::item, QTreeWidget::item, QTreeView::item {{
    padding: 7px 9px;
    border: none;
}}
QTableView::item:hover, QTreeWidget::item:hover,
QTreeView::item:hover, QListWidget::item:hover {{
    background: {surface_muted};
}}
QTableView::item:selected, QTreeWidget::item:selected,
QTreeView::item:selected, QListWidget::item:selected {{
    background: {brand_soft};
    color: {text};
}}
QTableView:focus, QTreeWidget:focus, QTreeView:focus,
QListWidget:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {focus};
}}
QTableCornerButton::section {{ background: {surface_muted}; border: none; }}
/* Branch indicators are painted by TreeBranchStyle; QSS branch overrides hang on Windows Qt. */
QListWidget::item {{ padding: 5px 8px; min-height: 22px; border-radius: 4px; }}
QListWidget::indicator, QCheckBox::indicator, QTreeWidget::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {line_strong};
    border-radius: 4px;
    background: {surface};
}}
QListWidget::indicator:checked, QCheckBox::indicator:checked,
QTreeWidget::indicator:checked {{
    background: {brand};
    border-color: {brand};
    image: url({checkmark});
}}
QListWidget::indicator:hover, QCheckBox::indicator:hover {{ border-color: {focus}; }}
QCheckBox::indicator:focus, QRadioButton::indicator:focus {{ border-color: {focus}; }}
QCheckBox::indicator:disabled {{ background: {surface_muted}; border-color: {line}; }}

/* ======================== Dialogs / menus ======================== */
QDialog {{ background: {canvas}; }}
QMessageBox {{ background: {surface}; }}
QMessageBox QLabel {{ background: transparent; color: {text}; }}
QMenu {{
    background: {overlay};
    color: {text};
    border: 1px solid {line_strong};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 7px 16px; border-radius: 5px; }}
QMenu::item:selected {{ background: {brand_soft}; }}
QMenu::separator {{ height: 1px; background: {line}; margin: 4px 6px; }}

QGroupBox {{
    border: 1px solid {line};
    border-radius: 10px;
    margin-top: 14px;
    background: {surface};
    padding: 14px 12px 12px 12px;
    font-weight: bold;
}}
/* Anchor to the corner rather than nudging with `right:`, which pushes the
   caption past the frame in RTL and clips its first letters. */
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top right;
    padding: 0 10px;
    color: {text_muted};
    background: transparent;
}}

QTabWidget::pane {{
    border: 1px solid {line};
    background: {surface};
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {text_muted};
    padding: 9px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-left: 2px;
}}
QTabBar::tab:hover {{ color: {text}; }}
QTabBar::tab:selected {{
    color: {brand};
    border-bottom: 2px solid {brand};
    font-weight: bold;
}}

QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; color: {text}; }}
QCheckBox:focus, QRadioButton:focus {{ color: {brand}; }}
#AttachmentEmpty {{
    color: {text_muted};
    background: {surface_alt};
    border: 1px dashed {line_strong};
    border-radius: 8px;
    padding: 18px;
    font-style: italic;
}}
QSplitter::handle {{ background: {line}; }}
QLabel {{ background: transparent; }}

/* ========================== Status bar =========================== */
QStatusBar {{
    background: {ink};
    color: {ink_text_dim};
    border-top: 1px solid {ink_line};
}}
QStatusBar QLabel {{ color: {ink_text_dim}; background: transparent; font-size: 11px; }}
QStatusBar::item {{ border: none; }}
#StatusPath {{ color: {ink_text}; }}
#StatusYear {{
    color: {ink_text};
    background: {ink_alt};
    border-radius: 5px;
    padding: 3px 8px;
    font-weight: bold;
}}

#BalanceBar {{
    background: {surface_alt};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
}}
#BalanceOk {{ color: {success}; font-weight: bold; background: transparent; }}
#BalanceBad {{ color: {danger}; font-weight: bold; background: transparent; }}

/* =========================== ScrollBars ========================== */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {line_strong}; border-radius: 4px; min-height: 32px; min-width: 32px; }}
QScrollBar::handle:hover {{ background: {text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
/* Where the two scrollbars meet; unstyled it paints a bare white square. */
QAbstractScrollArea::corner {{ background: transparent; border: none; }}

/* ===================== Browse (drill-down) ======================= */
#LevelStepper {{
    background: {surface_alt};
    border: 1px solid {line};
    border-radius: 8px;
}}
#LevelChip {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    color: {text_muted};
    min-height: 20px;
}}
#LevelChip:hover {{ background: {surface_muted}; color: {text}; }}
#LevelChip:checked {{
    background: {brand};
    color: #ffffff;
    font-weight: bold;
}}
#LevelChip:disabled {{ color: {text_faint}; background: transparent; }}

#BreadcrumbBar {{ background: transparent; }}
#BreadcrumbCrumb {{
    background: {surface_muted};
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    color: {brand};
    min-height: 18px;
}}
#BreadcrumbCrumb:hover {{ background: {brand_soft}; }}
#BreadcrumbCrumb[current="true"] {{
    background: {brand};
    color: #ffffff;
    font-weight: bold;
}}
#BreadcrumbSep {{
    color: {text_faint};
    background: transparent;
    padding: 0 2px;
}}
#BrowseHint {{ color: {text_faint}; font-size: 11px; background: transparent; }}
#EmptyState {{
    color: {text_muted};
    font-size: 13px;
    background: {surface_alt};
    border: 1px dashed {line_strong};
    border-radius: 10px;
    padding: 28px;
}}
"""


def build(
    palette: Palette,
    checkmark: str = "",
    chevron: str = "",
) -> str:
    return _TEMPLATE.format(
        checkmark=checkmark,
        chevron=chevron,
        **palette.__dict__,
    )
