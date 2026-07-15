"""
Central logging configuration.

Packaged (MSIX / PyInstaller windowed) builds have no console, so anything
printed to stdout is lost. This routes all logging to a rotating file under
%APPDATA%/Lorebox/logs/ and, when a console exists, mirrors it there.

Call setup_logging() once at startup (main.py) before other modules log.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.paths import APP_DIR
LOG_DIR = APP_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)s: %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure root logging to a rotating file (+ console if available).

    Idempotent — safe to call more than once. Returns the log file path.
    """
    global _configured
    if _configured:
        return LOG_FILE

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)

    # Rotating file: 2 MB x 5 backups
    try:
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(fh)
    except OSError:
        pass  # read-only location — fall back to console only

    # Console handler only when a real stdout exists (dev runs)
    if sys.stderr is not None:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(ch)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "PIL", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info("Logging initialised → %s", LOG_FILE)
    return LOG_FILE
