"""Single source of truth for the app's data directory.

Every module resolves its data location from here, so the whole app can be
pointed at one place. Set the ``LOREBOX_DATA_DIR`` environment variable (e.g. in
``.env``) to keep data in a stable, non-virtualized folder; otherwise it
defaults to ``%APPDATA%/Lorebox``.

Why the override exists: when the app runs under a Microsoft Store (MSIX)
packaged Python, writes to ``%APPDATA%`` are redirected into a per-package
``LocalCache`` that Windows treats as disposable and can wipe. Pointing
``LOREBOX_DATA_DIR`` at a normal folder (outside AppData) avoids that.

``LOREBOX_DATA_DIR`` must be set in the environment before this module is first
imported. ``main.py`` loads ``.env`` before importing anything from ``core``, so
a value set there is honored.
"""
import os
from pathlib import Path


def resolve_app_dir() -> Path:
    """Return the configured data dir: LOREBOX_DATA_DIR if set, else %APPDATA%/Lorebox."""
    override = os.environ.get("LOREBOX_DATA_DIR", "").strip()
    if override:
        return Path(override)
    return Path(os.environ.get("APPDATA", Path.home())) / "Lorebox"


APP_DIR = resolve_app_dir()
APP_DIR.mkdir(parents=True, exist_ok=True)

SCANS_DIR = APP_DIR / "scans"
SCANS_CARDS_DIR = SCANS_DIR / "cards"
