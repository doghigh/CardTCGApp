"""Microsoft Store review prompt — policy for when to ask, and how often.

Asks at most twice in a user's lifetime: first at FIRST_THRESHOLD cards, then only
once the collection has grown by REPEAT_GAP more cards than it had at the first ask.

The repeat gap is deliberately relative rather than an absolute second threshold.
BatchTab.cards_added fires once with a whole import's count, so a user at 40 cards
importing a 200-card box crosses the first threshold at 240 — an absolute second
threshold of 250 would then fire a second ask ten cards later.

No module-level Qt import: open_store_review() imports Qt lazily so this module
doesn't take a direct UI dependency for one hand-off call — core/ is policy,
ui/ is Qt.
"""
from core.config import get_pref, set_pref

STORE_PRODUCT_ID = "9N94V4458M3V"
STORE_REVIEW_URI = f"ms-windows-store://review?ProductId={STORE_PRODUCT_ID}"
STORE_WEB_URL = f"https://apps.microsoft.com/store/detail/{STORE_PRODUCT_ID}"

FIRST_THRESHOLD = 50    # cards before the first ask
REPEAT_GAP = 200        # additional cards before a second ask
MAX_ASKS = 2            # hard lifetime ceiling

_COUNT = "review_prompt_count"
_LAST = "review_prompt_last_count"
_DISMISSED = "review_prompt_dismissed"
_DUE = "review_prompt_due"


def _int_pref(key: str) -> int:
    """Read an int pref, treating anything unparseable as 0."""
    try:
        return int(get_pref(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def asks_used() -> int:
    return _int_pref(_COUNT)


def is_dismissed() -> bool:
    return bool(get_pref(_DISMISSED, False))


def is_due() -> bool:
    """True when a prompt has been armed but not yet displayed."""
    return bool(get_pref(_DUE, False))


def next_threshold() -> int:
    """Card count at which the next ask becomes eligible."""
    if asks_used() == 0:
        return FIRST_THRESHOLD
    return _int_pref(_LAST) + REPEAT_GAP


def should_prompt(card_count: int) -> bool:
    if is_dismissed():
        return False
    if asks_used() >= MAX_ASKS:
        return False
    try:
        count = int(card_count)
    except (TypeError, ValueError):
        return False
    return count >= next_threshold()


def arm() -> None:
    """Mark a prompt as owed. Idempotent."""
    set_pref(_DUE, True)


def mark_prompted(card_count: int) -> None:
    """Record that the dialog was displayed: spend an ask, anchor the next gap."""
    try:
        anchor = int(card_count)
    except (TypeError, ValueError):
        anchor = 0
    set_pref(_COUNT, asks_used() + 1)
    set_pref(_LAST, anchor)
    set_pref(_DUE, False)


def mark_rated() -> None:
    """The user went to the Store. Never ask again."""
    set_pref(_DISMISSED, True)
    set_pref(_DUE, False)


def mark_declined(permanent: bool) -> None:
    """'Don't ask again' sets a permanent stop; 'Not now' only clears the flag."""
    if permanent:
        set_pref(_DISMISSED, True)
    set_pref(_DUE, False)


def open_store_review() -> None:
    """Open the Store review page: protocol deep link, falling back to the web."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    if not QDesktopServices.openUrl(QUrl(STORE_REVIEW_URI)):
        QDesktopServices.openUrl(QUrl(STORE_WEB_URL))
