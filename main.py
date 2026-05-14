"""
Trading Card Manager - Main Entry Point
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication

# Import theme
from utils.theme import apply_dark_theme

# Import main window (which imports everything else)
from ui.main_window import MainWindow


APP_NAME = "Trading Card Manager"
APP_VERSION = "1.1.0"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Apply beautiful dark theme with accessibility support
    apply_dark_theme(app)

    # Create and show main window
    window = MainWindow()
    window.show()

    print(f"🚀 {APP_NAME} v{APP_VERSION} started successfully!")
    sys.exit(app.exec())


if __name__ == "__main__":
    # Ensure APP_DIR is available globally if needed
    APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
    APP_DIR.mkdir(parents=True, exist_ok=True)

    main()
