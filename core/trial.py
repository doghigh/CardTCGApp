"""Local, advisory free-trial counter + trial-proxy routing constants.

The per-install counter lives in (non-secret) prefs and is deliberately
resettable — it only decides when to show the "add your own key" dialog.
Actual spend is bounded server-side by the Worker's monthly cap.
"""
import os

from core.config import get_pref, set_pref

# Number of free trial identifications per install. Set to 0 to disable the
# trial entirely (new users go straight to the add-your-own-key dialog).
# When you deploy the Worker (see trial-proxy/README.md), set this to the
# desired per-install allowance (e.g., 10).
TRIAL_LIMIT = 0

# Deployed Cloudflare Worker origin. The Anthropic SDK appends "/v1/messages",
# so this should be the origin only (no path).
# Override via the LOREBOX_TRIAL_WORKER_URL environment variable, or edit the
# fallback below. While the fallback still contains "REPLACE", trial calls are
# treated as disabled so the app never hits an unreachable host.
_PLACEHOLDER_URL = "https://lorebox-trial.REPLACE.workers.dev"
WORKER_BASE_URL = os.environ.get("LOREBOX_TRIAL_WORKER_URL", _PLACEHOLDER_URL)

_PREF_KEY = "trial_used"


class TrialCapacityReached(Exception):
    """The global monthly trial cap is exhausted (Worker returned 429)."""


class TrialUnavailable(Exception):
    """The trial proxy could not be reached or returned an unexpected error."""


def is_configured() -> bool:
    """True when a real Worker URL has been set (not the placeholder)."""
    return WORKER_BASE_URL != _PLACEHOLDER_URL


def trial_remaining() -> int:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    return max(0, TRIAL_LIMIT - used)


def consume_trial() -> None:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    set_pref(_PREF_KEY, used + 1)
