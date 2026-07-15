"""
Lorebox - Main Entry Point
"""

import sys
import os
from pathlib import Path
from PyQt6.QtCore import Qt


def _load_dotenv():
    """Load .env file from the project root into os.environ (no dependencies)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

# Initialise logging before anything else logs.
import logging
from core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger("main")

# Apply user-saved API keys (Settings screen). .env / real env vars take
# precedence so developers can still override locally.
try:
    from core.config import config as _app_config
    _app_config.apply_to_env(override=False)
except Exception as _exc:  # noqa: BLE001 — config is best-effort at startup
    logger.warning("Config load skipped: %s", _exc)


try:
    from PyQt6.QtWidgets import (
        QApplication, 
        QWidget,
        )
except ImportError:
    try:
        from PyQt5.QtWidgets import (QApplication, QWidget)
    except ImportError as exc:
        raise ImportError("PyQt6 or PyQt5 is required to run this application") from exc

# Import theme
from utils.theme import apply_dark_theme

# Import main window (which imports everything else)
from ui.main_window import MainWindow


APP_NAME = "Lorebox"
APP_VERSION = "1.2.0"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Only the main window closing should exit the app — never a child dialog
    # (Help, Settings, card detail, etc.). MainWindow.closeEvent quits explicitly.
    app.setQuitOnLastWindowClosed(False)

    # Apply beautiful dark theme with accessibility support
    apply_dark_theme(app)

    # Create and show main window maximized
    window = MainWindow()
    window.showMaximized()

    logger.info("%s v%s started successfully!", APP_NAME, APP_VERSION)
    sys.exit(app.exec())


if __name__ == "__main__":
    # APP_DIR is created on import of core.paths (honoring LOREBOX_DATA_DIR,
    # which _load_dotenv above loads from .env before any core import).
    main()
