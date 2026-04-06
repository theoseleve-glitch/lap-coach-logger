"""Centralized desktop theme and style constants.

Design system based on the LAP COACH brand charter:
    Asphalt Black  #000000     Concrete    #141414
    Steel          #949494     Chalk       #F0EDE5
    Pit Orange     #C9A84C     Safety Red  #FF2A2A
    Acid Green     #22C55E     Marshal Yellow #FACC15
    Racing Purple  #8B5CF6
"""

from __future__ import annotations

WINDOW_MIN_WIDTH = 1180
WINDOW_MIN_HEIGHT = 760

# -- charter colours -------------------------------------------------------
ASPHALT   = "#000000"
CONCRETE  = "#141414"
STEEL     = "#949494"
CHALK     = "#F0EDE5"
PIT_ORANGE = "#C9A84C"
SAFETY_RED = "#FF2A2A"
ACID_GREEN = "#22C55E"
MARSHAL_YELLOW = "#FACC15"
RACING_PURPLE  = "#8B5CF6"

STATUS_COLORS = {
    "Idle": STEEL,
    "Simulator Detected": PIT_ORANGE,
    "Waiting": PIT_ORANGE,
    "Arming": MARSHAL_YELLOW,
    "Recording": ACID_GREEN,
    "Finalizing": MARSHAL_YELLOW,
    "Ready for Review": PIT_ORANGE,
    "Failed": SAFETY_RED,
}

APP_STYLESHEET = f"""
/* ── Base ── */
QWidget {{
    background-color: {ASPHALT};
    color: {CHALK};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background-color: {ASPHALT};
}}
QStackedWidget {{
    background-color: {ASPHALT};
}}
QScrollArea {{
    background-color: {ASPHALT};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {ASPHALT};
}}
QDialog {{
    background-color: {CONCRETE};
}}

/* ── Sidebar ── */
QFrame#Sidebar {{
    background-color: {CONCRETE};
    border-right: 1px solid rgba(240, 237, 229, 0.08);
}}
QFrame#Sidebar QLabel#AppTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {CHALK};
    letter-spacing: 2px;
}}
QFrame#Sidebar QLabel#AppSubtitle {{
    font-size: 10px;
    color: {STEEL};
    letter-spacing: 3px;
}}

/* ── TopBar ── */
QFrame#TopBar {{
    background-color: {CONCRETE};
    border-bottom: 1px solid rgba(240, 237, 229, 0.08);
}}

/* ── Cards ── */
QFrame#Card {{
    background-color: {CONCRETE};
    border: 1px solid rgba(240, 237, 229, 0.06);
    border-radius: 12px;
}}
QLabel#SectionTitle {{
    font-size: 10px;
    font-weight: 600;
    color: {PIT_ORANGE};
    letter-spacing: 2px;
}}
QLabel#CardHeading {{
    font-size: 18px;
    font-weight: 700;
    color: {CHALK};
    letter-spacing: 0.5px;
}}
QLabel#MetricValue {{
    font-size: 26px;
    font-weight: 700;
    color: {CHALK};
    font-family: 'Consolas', 'Space Mono', monospace;
}}
QLabel#MetricLabel {{
    font-size: 10px;
    color: {STEEL};
    letter-spacing: 1.5px;
}}
QLabel#MetricUnit {{
    font-size: 11px;
    color: {STEEL};
    font-family: 'Consolas', 'Space Mono', monospace;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: rgba(240, 237, 229, 0.06);
    border: 1px solid rgba(240, 237, 229, 0.10);
    border-radius: 8px;
    padding: 8px 16px;
    color: {CHALK};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton:hover {{
    background-color: rgba(240, 237, 229, 0.10);
    border: 1px solid rgba(240, 237, 229, 0.15);
}}
QPushButton:pressed {{
    background-color: rgba(240, 237, 229, 0.04);
}}
QPushButton#PrimaryButton {{
    background-color: {PIT_ORANGE};
    border: 1px solid {PIT_ORANGE};
    color: {ASPHALT};
    font-weight: 700;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #D4B35A;
}}
QPushButton#PrimaryButton:pressed {{
    background-color: #B89940;
}}
QPushButton#DangerButton {{
    background-color: rgba(255, 42, 42, 0.12);
    border: 1px solid rgba(255, 42, 42, 0.25);
    color: {SAFETY_RED};
}}
QPushButton#DangerButton:hover {{
    background-color: rgba(255, 42, 42, 0.20);
}}

/* ── Inputs ── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: rgba(240, 237, 229, 0.04);
    border: 1px solid rgba(240, 237, 229, 0.08);
    border-radius: 8px;
    padding: 7px 10px;
    color: {CHALK};
    font-family: 'Consolas', 'Space Mono', monospace;
    font-size: 12px;
}}
QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {PIT_ORANGE};
}}

/* ── Tables / Lists ── */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: rgba(240, 237, 229, 0.02);
    border: 1px solid rgba(240, 237, 229, 0.06);
    border-radius: 8px;
    gridline-color: rgba(240, 237, 229, 0.06);
    font-family: 'Consolas', 'Space Mono', monospace;
    font-size: 12px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 4px;
    color: {STEEL};
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 1.5px;
}}
QListWidget::item:selected {{
    background-color: rgba(201, 168, 76, 0.15);
    color: {PIT_ORANGE};
    border-left: 3px solid {PIT_ORANGE};
}}
QListWidget::item:hover:!selected {{
    background-color: rgba(240, 237, 229, 0.04);
    color: {CHALK};
}}
QHeaderView::section {{
    background-color: {CONCRETE};
    color: {STEEL};
    border: none;
    border-right: 1px solid rgba(240, 237, 229, 0.06);
    border-bottom: 1px solid rgba(240, 237, 229, 0.06);
    padding: 8px 10px;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1.5px;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid rgba(240, 237, 229, 0.04);
}}
QTableWidget::item:selected {{
    background-color: rgba(201, 168, 76, 0.12);
    color: {CHALK};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid rgba(240, 237, 229, 0.06);
    border-radius: 8px;
}}
QTabBar::tab {{
    background: rgba(240, 237, 229, 0.04);
    color: {STEEL};
    padding: 10px 18px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 1px;
}}
QTabBar::tab:selected {{
    background: {PIT_ORANGE};
    color: {ASPHALT};
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{
    background: rgba(240, 237, 229, 0.08);
    color: {CHALK};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(240, 237, 229, 0.12);
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(201, 168, 76, 0.3);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 4px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(240, 237, 229, 0.12);
    border-radius: 4px;
    min-width: 30px;
}}

/* ── Checkbox ── */
QCheckBox {{
    color: {STEEL};
    font-size: 11px;
    letter-spacing: 1px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid rgba(240, 237, 229, 0.15);
    border-radius: 4px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background-color: {PIT_ORANGE};
    border-color: {PIT_ORANGE};
}}

/* ── Status Bar ── */
QStatusBar {{
    background-color: {CONCRETE};
    color: {STEEL};
    border-top: 1px solid rgba(240, 237, 229, 0.06);
    font-size: 11px;
    font-family: 'Consolas', 'Space Mono', monospace;
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {CONCRETE};
    color: {CHALK};
    border: 1px solid rgba(240, 237, 229, 0.10);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
}}
"""
