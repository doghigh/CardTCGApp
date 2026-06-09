from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QFont


# ── Color tokens ────────────────────────────────────────────────────────────
BG_DEEP    = "#0d0f18"   # window / outermost background
BG_BASE    = "#13151f"   # widget / panel background
BG_RAISED  = "#1c1f2e"   # cards, group boxes, raised surfaces
BG_HOVER   = "#252840"   # hover state for list rows / buttons
BORDER     = "#2a2d3e"   # subtle borders
DEFAULT_ACCENT = "#5865f2"   # default indigo accent
TEXT_PRI   = "#e8eaf0"   # primary text
TEXT_SEC   = "#8b8fa8"   # secondary / placeholder text
TEXT_DIS   = "#4a4d60"   # disabled text
SUCCESS    = "#43b581"
WARNING    = "#faa61a"
DANGER     = "#ed4245"
# ─────────────────────────────────────────────────────────────────────────────


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _adjust(hex_color: str, factor: float) -> str:
    """Lighten (factor>0) or darken (factor<0) a hex color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor >= 0:
        r = _clamp(int(r + (255 - r) * factor))
        g = _clamp(int(g + (255 - g) * factor))
        b = _clamp(int(b + (255 - b) * factor))
    else:
        f = 1 + factor
        r, g, b = _clamp(int(r * f)), _clamp(int(g * f)), _clamp(int(b * f))
    return f"#{r:02x}{g:02x}{b:02x}"


def _tokens(high_contrast: bool):
    """Return the color token set for normal or high-contrast mode."""
    if high_contrast:
        return {
            "BG_DEEP": "#000000", "BG_BASE": "#000000", "BG_RAISED": "#0a0a0a",
            "BG_HOVER": "#1a1a1a", "BORDER": "#ffffff",
            "TEXT_PRI": "#ffffff", "TEXT_SEC": "#e0e0e0", "TEXT_DIS": "#9a9a9a",
            "FOCUS_W": "3px",
        }
    return {
        "BG_DEEP": BG_DEEP, "BG_BASE": BG_BASE, "BG_RAISED": BG_RAISED,
        "BG_HOVER": BG_HOVER, "BORDER": BORDER,
        "TEXT_PRI": TEXT_PRI, "TEXT_SEC": TEXT_SEC, "TEXT_DIS": TEXT_DIS,
        "FOCUS_W": "2px",
    }


def build_stylesheet(accent: str = DEFAULT_ACCENT, scale: float = 1.0,
                     high_contrast: bool = False) -> str:
    """Build the full stylesheet around an accent color, text scale and mode."""
    ACCENT = accent
    ACCENT_HOV = _adjust(accent, 0.15)
    ACCENT_PRS = _adjust(accent, -0.15)
    BORDER_FOCUS = accent if not high_contrast else "#ffcc00"

    t = _tokens(high_contrast)
    BG_DEEP_  = t["BG_DEEP"];  BG_BASE_ = t["BG_BASE"];  BG_RAISED = t["BG_RAISED"]
    BG_HOVER  = t["BG_HOVER"]; BORDER   = t["BORDER"]
    TEXT_PRI_ = t["TEXT_PRI"]; TEXT_SEC = t["TEXT_SEC"]; TEXT_DIS = t["TEXT_DIS"]
    FOCUS_W   = t["FOCUS_W"]
    # Re-alias so the template below reads naturally
    BG_DEEP = BG_DEEP_; BG_BASE = BG_BASE_; TEXT_PRI = TEXT_PRI_

    base = max(10, round(13 * scale))      # base font size in px

    return f"""
* {{
    font-family: "Segoe UI", sans-serif;
    font-size: {base}px;
    color: {TEXT_PRI};
}}

/* Visible keyboard focus on interactive controls */
QPushButton:focus, QComboBox:focus, QCheckBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QTabBar::tab:focus {{
    outline: {FOCUS_W} solid {BORDER_FOCUS};
    outline-offset: 1px;
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
    margin-top: 20px;
    font-weight: 600;
    font-size: 12px;
    color: {TEXT_SEC};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
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


def get_accent() -> str:
    """Return the user's saved accent color, or the default."""
    try:
        from core.config import get_pref
        return get_pref("accent_color", DEFAULT_ACCENT) or DEFAULT_ACCENT
    except Exception:
        return DEFAULT_ACCENT


def get_ui_scale() -> float:
    try:
        from core.config import get_pref
        return float(get_pref("ui_scale", 1.0) or 1.0)
    except Exception:
        return 1.0


def get_high_contrast() -> bool:
    try:
        from core.config import get_pref
        return bool(get_pref("high_contrast", False))
    except Exception:
        return False


def apply_dark_theme(app: QApplication, accent: str = None,
                     scale: float = None, high_contrast: bool = None):
    """Apply the theme with the given (or saved) accent, text scale, and mode."""
    app.setStyle("Fusion")

    accent = accent or get_accent()
    scale = get_ui_scale() if scale is None else scale
    high_contrast = get_high_contrast() if high_contrast is None else high_contrast

    app.setFont(QFont("Segoe UI", max(8, round(10 * scale))))

    t = _tokens(high_contrast)
    c = lambda h: QColor(h)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          c(t["BG_DEEP"]))
    palette.setColor(QPalette.ColorRole.WindowText,      c(t["TEXT_PRI"]))
    palette.setColor(QPalette.ColorRole.Base,            c(t["BG_BASE"]))
    palette.setColor(QPalette.ColorRole.AlternateBase,   c(t["BG_RAISED"]))
    palette.setColor(QPalette.ColorRole.Text,            c(t["TEXT_PRI"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, c(t["TEXT_SEC"]))
    palette.setColor(QPalette.ColorRole.Button,          c(t["BG_RAISED"]))
    palette.setColor(QPalette.ColorRole.ButtonText,      c(t["TEXT_PRI"]))
    palette.setColor(QPalette.ColorRole.Highlight,       c(accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link,            c(accent))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     c(t["BG_RAISED"]))
    palette.setColor(QPalette.ColorRole.ToolTipText,     c(t["TEXT_PRI"]))

    if high_contrast:
        palette.setColor(QPalette.ColorRole.Light,    QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Mid,      QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Dark,     QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Shadow,   QColor(0, 0, 0))
    else:
        palette.setColor(QPalette.ColorRole.Light,    QColor(60, 62, 72))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(45, 47, 56))
        palette.setColor(QPalette.ColorRole.Mid,      QColor(35, 37, 45))
        palette.setColor(QPalette.ColorRole.Dark,     QColor(22, 24, 30))
        palette.setColor(QPalette.ColorRole.Shadow,   QColor(10, 11, 15))

    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, c(t["TEXT_DIS"]))

    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet(accent, scale, high_contrast))


def set_accent(app: QApplication, accent: str):
    """Persist and apply a new accent color at runtime."""
    try:
        from core.config import set_pref
        set_pref("accent_color", accent)
    except Exception:
        pass
    apply_dark_theme(app, accent)


def set_appearance(app: QApplication, scale: float = None,
                   high_contrast: bool = None):
    """Persist and apply text scale and/or high-contrast mode at runtime."""
    try:
        from core.config import set_pref
        if scale is not None:
            set_pref("ui_scale", scale)
        if high_contrast is not None:
            set_pref("high_contrast", bool(high_contrast))
    except Exception:
        pass
    apply_dark_theme(app)
