"""
Watch-folder auto-import configuration and scheduling logic.

The user drops card scans into a folder; the app imports them automatically
on a schedule (a daily time, or a repeating interval). Imported files are
moved into an "imported" subfolder so they're never processed twice.

Config persists to %APPDATA%/Lorebox/watch_config.json.
The actual import run is driven by the main window (it owns the components
and a 60-second QTimer); this module only stores settings and answers
"is a run due right now?".
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "Lorebox"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / "watch_config.json"

IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.pdf")
IMPORTED_SUBDIR = "imported"


class WatchConfig:
    """Persistent settings for the auto-import watch folder."""

    def __init__(self):
        self.enabled: bool = False
        self.folder: str = ""
        self.mode: str = "daily"          # "daily" | "interval"
        self.time: str = "02:00"          # HH:MM for daily mode
        self.interval_min: int = 30       # minutes for interval mode
        self.pairing: str = "single"      # single | sequential | filename
        self.auto_value: bool = False
        self.last_run: str = ""           # ISO datetime of last completed run
        self.load()

    # ── persistence ────────────────────────────────────────────────────────

    def load(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for key in ("enabled", "folder", "mode", "time", "interval_min",
                        "pairing", "auto_value", "last_run"):
                if key in data:
                    setattr(self, key, data[key])
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Could not read watch config: %s", exc)

    def save(self):
        try:
            CONFIG_FILE.write_text(json.dumps({
                "enabled": self.enabled, "folder": self.folder,
                "mode": self.mode, "time": self.time,
                "interval_min": self.interval_min, "pairing": self.pairing,
                "auto_value": self.auto_value, "last_run": self.last_run,
            }, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.error("Could not write watch config: %s", exc)

    # ── scheduling ─────────────────────────────────────────────────────────

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """True if an auto-import should run now."""
        if not self.enabled or not self.folder:
            return False
        if not Path(self.folder).is_dir():
            return False

        now = now or datetime.now()
        last = None
        if self.last_run:
            try:
                last = datetime.fromisoformat(self.last_run)
            except ValueError:
                last = None

        if self.mode == "interval":
            if last is None:
                return True
            return (now - last).total_seconds() >= self.interval_min * 60

        # daily: due once per day, at or after the scheduled time
        try:
            hh, mm = (int(x) for x in self.time.split(":"))
        except (ValueError, AttributeError):
            hh, mm = 2, 0
        scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now < scheduled:
            return False
        # haven't run since today's scheduled time
        return last is None or last < scheduled

    def mark_run(self, when: Optional[datetime] = None):
        self.last_run = (when or datetime.now()).isoformat()
        self.save()

    # ── folder helpers ─────────────────────────────────────────────────────

    def pending_images(self) -> List[Path]:
        """Top-level image files awaiting import (excludes the imported/ subdir)."""
        if not self.folder or not Path(self.folder).is_dir():
            return []
        folder = Path(self.folder)
        files: List[Path] = []
        for pattern in IMAGE_EXTS:
            files.extend(folder.glob(pattern))
        return sorted(files)

    def next_run_text(self) -> str:
        """Human-readable description of when the next run will happen."""
        if not self.enabled:
            return "Auto-import is off."
        if self.mode == "interval":
            return f"Every {self.interval_min} min while files are present."
        return f"Daily at {self.time}."
