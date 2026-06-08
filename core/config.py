"""
Application configuration — user-supplied API keys, stored encrypted at rest.

Each user provides their own API credentials (Anthropic for card ID, eBay for
valuation) via the Settings screen. This keeps the app free to distribute on
the Microsoft Store: no shared keys, no per-user cost to the developer.

Storage:
  %APPDATA%/TradingCardManager/config.enc   — Fernet-encrypted JSON
  %APPDATA%/TradingCardManager/.config.key  — local Fernet key

Precedence: a real environment variable / .env value always wins over the
saved config, so developers can still override locally without touching the UI.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
APP_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = APP_DIR / "config.enc"
KEY_FILE    = APP_DIR / ".config.key"

# Keys this app understands. (env_var, human label, secret?)
MANAGED_KEYS = [
    ("ANTHROPIC_API_KEY", "Anthropic API Key", True),
    ("EBAY_APP_ID",       "eBay App ID (Client ID)", True),
    ("EBAY_CERT_ID",      "eBay Cert ID (Client Secret)", True),
]


class AppConfig:
    """Loads/saves encrypted user credentials and exposes them via os.environ."""

    def __init__(self):
        self._fernet = self._get_fernet()
        self._data: Dict[str, str] = self._read()

    # ── encryption ────────────────────────────────────────────────────────────

    def _get_fernet(self) -> Fernet:
        if KEY_FILE.exists():
            key = KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
        return Fernet(key)

    def _read(self) -> Dict[str, str]:
        if not CONFIG_FILE.exists():
            return {}
        try:
            decrypted = self._fernet.decrypt(CONFIG_FILE.read_bytes())
            return json.loads(decrypted.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, OSError) as exc:
            logger.error("Could not read config (%s) — starting fresh.", exc)
            return {}

    def _write(self):
        try:
            blob = json.dumps(self._data).encode("utf-8")
            CONFIG_FILE.write_bytes(self._fernet.encrypt(blob))
        except OSError as exc:
            logger.error("Could not write config: %s", exc)

    # ── public API ──────────────────────────────────────────────────────────

    def get(self, key: str) -> str:
        return self._data.get(key, "")

    def all(self) -> Dict[str, str]:
        return dict(self._data)

    def save(self, values: Dict[str, str]):
        """Persist values (blank entries are removed) and apply to os.environ."""
        for key, val in values.items():
            val = (val or "").strip()
            if val:
                self._data[key] = val
            else:
                self._data.pop(key, None)
        self._write()
        self.apply_to_env(override=True)
        logger.info("Configuration saved (%d keys).", len(self._data))

    def apply_to_env(self, override: bool = False):
        """
        Push saved keys into os.environ.

        With override=False (startup), an existing env/.env value wins so devs
        can override locally. With override=True (after a save), the new saved
        values take effect immediately.
        """
        for key, val in self._data.items():
            if override or not os.environ.get(key):
                os.environ[key] = val

    def has_anthropic_key(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def has_ebay_keys(self) -> bool:
        return bool(os.environ.get("EBAY_APP_ID") and os.environ.get("EBAY_CERT_ID"))


# Module-level singleton
config = AppConfig()


# ── Plain (non-secret) preferences — theme, UI choices, etc. ──────────────────

PREFS_FILE = APP_DIR / "prefs.json"


def get_pref(key: str, default=None):
    try:
        if PREFS_FILE.exists():
            return json.loads(PREFS_FILE.read_text(encoding="utf-8")).get(key, default)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Could not read prefs: %s", exc)
    return default


def set_pref(key, value):
    data = {}
    try:
        if PREFS_FILE.exists():
            data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    data[key] = value
    try:
        PREFS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write prefs: %s", exc)
