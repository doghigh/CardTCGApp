"""Local, advisory free-trial counter + trial-proxy routing constants.

The per-install counter lives in (non-secret) prefs and is deliberately
resettable — it only decides when to show the "add your own key" dialog.
Actual spend is bounded server-side by the Worker's monthly cap.
"""
from core.config import get_pref, set_pref

TRIAL_LIMIT = 10

# Set to the deployed Cloudflare Worker origin (see trial-proxy/README.md).
# The anthropic SDK appends "/v1/messages", so this is the origin only.
WORKER_BASE_URL = "https://lorebox-trial.REPLACE.workers.dev"

_PREF_KEY = "trial_used"


class TrialCapacityReached(Exception):
    """The global monthly trial cap is exhausted (Worker returned 429)."""


class TrialUnavailable(Exception):
    """The trial proxy could not be reached or returned an unexpected error."""


def trial_remaining() -> int:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    return max(0, TRIAL_LIMIT - used)


def consume_trial() -> None:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    set_pref(_PREF_KEY, used + 1)
