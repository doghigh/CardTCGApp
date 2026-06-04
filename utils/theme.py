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
/* ── Global ─────────────────────────────────────────────────────────────── */
* {{
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
    color: {TEXT_PRI};
    outline: none;
}}

QMainWindow, QDialog {{
    background: {BG_DEEP};
}}

QWidget {{
    background: transparent;
}}

/* ── Menu bar ────────────────────────────────────────────────────────────── */
QMenuBar {{
    background: {BG_DEEP};
    border-bottom: 1px solid {BORDER};
    padding: 2px 4px;
    spacing: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {BG_RAISED};
}}
QMenu {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ── Tab bar ─────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: {BG_BASE};
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    background: {BG_DEEP};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SEC};
    padding: 10px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
    min-width: 100px;
}}
QTabBar::tab:hover {{
    color: {TEXT_PRI};
    background: {BG_RAISED};
}}
QTabBar::tab:selected {{
    color: {TEXT_PRI};
    border-bottom: 2px solid {ACCENT};
    background: {BG_BASE};
}}

/* ── Group boxes ─────────────────────────────────────────────────────────── */
QGroupBox {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT_SEC};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    padding: 0 6px;
    background: {BG_RAISED};
}}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
    background: {BG_BASE};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {TEXT_DIS};
    border-color: {BORDER};
}}
QLineEdit::placeholder {{
    color: {TEXT_SEC};
}}

/* ── Combo box ───────────────────────────────────────────────────────────── */
QComboBox {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    color: {TEXT_PRI};
    min-width: 80px;
}}
QComboBox:focus, QComboBox:on {{
    border-color: {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SEC};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {BG_HOVER};
    padding: 4px;
    outline: none;
}}

/* ── Spin boxes ──────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {TEXT_PRI};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_RAISED};
    border: none;
    border-radius: 3px;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BG_HOVER};
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 16px;
    color: {TEXT_PRI};
    font-weight: 500;
    min-height: 32px;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border-color: #3a3d52;
}}
QPushButton:pressed {{
    background: {BG_BASE};
}}
QPushButton:disabled {{
    color: {TEXT_DIS};
    border-color: {BORDER};
}}

/* Primary action buttons — Save Card, Scan Card */
QPushButton[primary="true"],
QPushButton#save_btn,
QPushButton#scan_btn {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton[primary="true"]:hover,
QPushButton#save_btn:hover,
QPushButton#scan_btn:hover {{
    background: {ACCENT_HOV};
}}
QPushButton[primary="true"]:pressed,
QPushButton#save_btn:pressed,
QPushButton#scan_btn:pressed {{
    background: {ACCENT_PRS};
}}

/* ── Check box ───────────────────────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRI};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_BASE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

/* ── Scroll bars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3a3d52;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #3a3d52;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Tables ──────────────────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    alternate-background-color: {BG_RAISED};
    selection-background-color: {BG_HOVER};
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {BG_HOVER};
    color: {TEXT_PRI};
}}
QHeaderView::section {{
    background: {BG_RAISED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 8px 10px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT_SEC};
    text-transform: uppercase;
    letter-spacing: 0.3px;
}}
QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}
QHeaderView::section:last {{
    border-right: none;
    border-top-right-radius: 8px;
}}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
    height: 1px;
}}
QSplitter::handle:hover {{
    background: {ACCENT};
}}

/* ── Status bar ──────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {BG_DEEP};
    border-top: 1px solid {BORDER};
    color: {TEXT_SEC};
    font-size: 12px;
    padding: 0 8px;
}}

/* ── Labels ──────────────────────────────────────────────────────────────── */
QLabel {{
    color: {TEXT_PRI};
    background: transparent;
}}

/* ── Tool tips ───────────────────────────────────────────────────────────── */
QToolTip {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRI};
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── Message box ─────────────────────────────────────────────────────────── */
QMessageBox {{
    background: {BG_RAISED};
}}
QMessageBox QLabel {{
    color: {TEXT_PRI};
}}

/* ── Progress bar ────────────────────────────────────────────────────────── */
QProgressBar {{
    background: {BG_BASE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
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

        # Disabled
        palette.setColor(QPalette.ColorGroup.Disabled,
                         QPalette.ColorRole.Text,       c(TEXT_DIS))
        palette.setColor(QPalette.ColorGroup.Disabled,
                         QPalette.ColorRole.ButtonText, c(TEXT_DIS))

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
