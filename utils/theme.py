"""
Theme utilities with full accessibility support.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
import winreg


def apply_dark_theme(app: QApplication):
    """Apply a beautiful dark theme with automatic high-contrast / accessibility detection."""
    app.setStyle("Fusion")

    # Detect Windows High Contrast mode
    high_contrast = False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        apps_light = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        system_light = winreg.QueryValueEx(key, "SystemUsesLightTheme")[0]
        high_contrast = (apps_light == 0 and system_light == 0)
    except Exception:
        pass

    if high_contrast:
        # High Contrast / Accessibility Mode
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 128, 255))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

        app.setStyleSheet("""
            * { font-size: 14px; }
            QGroupBox, QLabel, QPushButton, QLineEdit, QTextEdit, QTableWidget, QComboBox {
                border: 2px solid #00aaff; 
                padding: 6px; 
            }
            QPushButton:focus, QLineEdit:focus, QTextEdit:focus, 
            QComboBox:focus, QSpinBox:focus, QTableWidget:focus {
                border: 3px solid #ffff00;
            }
            QTabBar::tab:selected { 
                background: #0066cc; 
                color: white; 
            }
        """)
    else:
        # Standard Dark Theme with excellent accessibility
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 32, 40))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
        palette.setColor(QPalette.ColorRole.Base, QColor(22, 24, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(38, 40, 48))
        palette.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 48, 58))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(230, 230, 230))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 100, 100))
        palette.setColor(QPalette.ColorRole.Link, QColor(66, 153, 225))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(44, 82, 130))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

        app.setStyleSheet("""
            * { 
                font-size: 13px; 
            }
            QGroupBox {
                border: 1px solid #4a5568; 
                border-radius: 6px;
                margin-top: 12px; 
                padding-top: 8px; 
                font-weight: bold;
            }
            QGroupBox::title { 
                color: #90cdf4; 
            }
            QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 6px 10px;
                border-radius: 4px;
            }
            QPushButton:focus, QLineEdit:focus, QTextEdit:focus, 
            QComboBox:focus, QSpinBox:focus, QTableWidget:focus {
                border: 2px solid #4299e1;
            }
            QPushButton:hover {
                background: #4a5568;
            }
            QTableWidget::item:selected {
                background: #2c5282;
                color: white;
            }
            QTabBar::tab:selected {
                border-bottom: 3px solid #4299e1;
            }
        """)