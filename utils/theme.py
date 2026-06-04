from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QFont


# ── Colour tokens ────────────────────────────────────────────────────────────
BG_DEEP    = "#0d0f18"   # window / outermost background
BG_BASE    = "#13151f"   # widget / panel background
BG_RAISED  = "#1c1f2e"   # cards, group boxes, raised surfaces
BG_HOVER   = "#252840"   # hover state for list rows / buttons
BORDER     = "#2a2d3e"   # subtle borders
BORDER_FOCUS = "#5865f2" # indigo focus ring
ACCENT     = "#5865f2"   # primary accent (indigo)
ACCENT_HOV = "#6b77f5"   # accent hover
ACCENT_PRS = "#4752c4"   # accent pressed
TEXT_PRI   = "#e8eaf0"   # primary text
TEXT_SEC   = "#8b8fa8"   # secondary / placeholder text
TEXT_DIS   = "#4a4d60"   # disabled text
SUCCESS    = "#43b581"
WARNING    = "#faa61a"
DANGER     = "#ed4245"
# ─────────────────────────────────────────────────────────────────────────────

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT_PRI};
}}

QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}

QWidget {{
    background-color: transparent;
}}

QTabWidget > QWidget {{
    background-color: {BG_BASE};
}}

/* ── Menu ── */
QMenuBar {{
    background-color: {BG_DEEP};
    border-bottom: 1px solid {BORDER};
    padding: 2px 4px;
    spacing: 2px;
}}
QMenuBar::item {{
    background-color: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {BG_RAISED};
}}
QMenu {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    background-color: {BG_BASE};
}}
QTabBar {{
    background-color: {BG_DEEP};
}}
QTabBar::tab {{
    background-color: {BG_DEEP};
    color: {TEXT_SEC};
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
    min-width: 110px;
}}
QTabBar::tab:hover {{
    color: {TEXT_PRI};
    background-color: {BG_RAISED};
}}
QTabBar::tab:selected {{
    color: {TEXT_PRI};
    background-color: {BG_BASE};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:!selected {{
    margin-top: 2px;
}}

/* ── Group boxes ── */
QGroupBox {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 8px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT_SEC};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 0px;
    padding: 0 4px;
    background-color: {BG_RAISED};
    color: {TEXT_SEC};
}}

/* ── Inputs ── */
QLineEdit {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QLineEdit:disabled {{
    color: {TEXT_DIS};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 8px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
}}

/* ── Combo box ── */
QComboBox {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    color: {TEXT_PRI};
    min-width: 80px;
}}
QComboBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    selection-background-color: {BG_HOVER};
    color: {TEXT_PRI};
    outline: none;
}}

/* ── Spin boxes ── */
QSpinBox, QDoubleSpinBox {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    color: {TEXT_PRI};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {BG_RAISED};
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BG_HOVER};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    color: {TEXT_PRI};
    font-weight: 500;
    min-height: 30px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: #3a3d52;
}}
QPushButton:pressed {{
    background-color: {BG_BASE};
}}
QPushButton:disabled {{
    color: {TEXT_DIS};
    border-color: {BORDER};
}}
QPushButton[primary="true"] {{
    background-color: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background-color: {ACCENT_HOV};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {ACCENT_PRS};
}}

/* ── Checkbox ── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRI};
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_BASE};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #3a3d52;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #3a3d52;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Tables ── */
QTableWidget, QTableView {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    alternate-background-color: {BG_RAISED};
    selection-background-color: {BG_HOVER};
    selection-color: {TEXT_PRI};
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 5px 8px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {BG_HOVER};
    color: {TEXT_PRI};
}}
QHeaderView::section {{
    background-color: {BG_RAISED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 7px 10px;
    font-weight: 600;
    font-size: 11px;
    color: {TEXT_SEC};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {BORDER};
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {BG_DEEP};
    border-top: 1px solid {BORDER};
    color: {TEXT_SEC};
    font-size: 12px;
}}

/* ── Labels ── */
QLabel {{
    color: {TEXT_PRI};
    background-color: transparent;
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    color: {TEXT_PRI};
    padding: 5px 8px;
}}

/* ── Progress bar ── */
QProgressBar {{
    background-color: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
"""


def apply_dark_theme(app: QApplication):
    """Apply modern dark theme. High-contrast mode falls back to accessible variant."""
    app.setStyle("Fusion")

    # Set a modern font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    high_contrast = _is_high_contrast()

    if high_contrast:
        _apply_high_contrast(app)
    else:
        palette = QPalette()
        c = lambda h: QColor(h)

        # Core roles
        palette.setColor(QPalette.ColorRole.Window,          c(BG_DEEP))
        palette.setColor(QPalette.ColorRole.WindowText,      c(TEXT_PRI))
        palette.setColor(QPalette.ColorRole.Base,            c(BG_BASE))
        palette.setColor(QPalette.ColorRole.AlternateBase,   c(BG_RAISED))
        palette.setColor(QPalette.ColorRole.Text,            c(TEXT_PRI))
        palette.setColor(QPalette.ColorRole.PlaceholderText, c(TEXT_SEC))
        palette.setColor(QPalette.ColorRole.Button,          c(BG_RAISED))
        palette.setColor(QPalette.ColorRole.ButtonText,      c(TEXT_PRI))
        palette.setColor(QPalette.ColorRole.Highlight,       c(ACCENT))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link,            c(ACCENT))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     c(BG_RAISED))
        palette.setColor(QPalette.ColorRole.ToolTipText,     c(TEXT_PRI))

        # Neutral grey roles — Fusion derives border/shadow colors from these.
        # Without explicit values it auto-calculates from blue-tinted base → cyan borders.
        palette.setColor(QPalette.ColorRole.Light,           QColor(60,  62,  72))
        palette.setColor(QPalette.ColorRole.Midlight,        QColor(45,  47,  56))
        palette.setColor(QPalette.ColorRole.Mid,             QColor(35,  37,  45))
        palette.setColor(QPalette.ColorRole.Dark,            QColor(22,  24,  30))
        palette.setColor(QPalette.ColorRole.Shadow,          QColor(10,  11,  15))

        # Disabled
        palette.setColor(QPalette.ColorGroup.Disabled,
                         QPalette.ColorRole.Text,       c(TEXT_DIS))
        palette.setColor(QPalette.ColorGroup.Disabled,
                         QPalette.ColorRole.ButtonText, c(TEXT_DIS))
        palette.setColor(QPalette.ColorGroup.Disabled,
                         QPalette.ColorRole.WindowText, c(TEXT_DIS))

        app.setPalette(palette)
        app.setStyleSheet(STYLESHEET)


def _is_high_contrast() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        apps_light   = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        system_light = winreg.QueryValueEx(key, "SystemUsesLightTheme")[0]
        return apps_light == 0 and system_light == 0
    except Exception:
        return False


def _apply_high_contrast(app: QApplication):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,     QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base,       QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text,       QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button,     QColor(64, 64, 64))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight,  QColor(0, 128, 255))
    app.setPalette(palette)
    app.setStyleSheet("""
        * { font-size: 14px; }
        QGroupBox, QLineEdit, QTextEdit, QPushButton, QTableWidget {
            border: 2px solid #00aaff;
        }
        QPushButton:focus, QLineEdit:focus { border: 3px solid #ffff00; }
    """)
