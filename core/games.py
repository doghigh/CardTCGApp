"""Single source of truth for game categories: built-in list + user customs.

Custom games are add-only and persist in prefs, so a game added in Batch Review
appears in every game dropdown app-wide via all_games().
"""
from core.config import get_pref, set_pref

BUILTIN_GAMES = [
    "Baseball", "Basketball", "Football", "Hockey", "Sports Cards",
    "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece",
    "Lorcana", "Flesh and Blood", "Non-Sport", "Other",
]

_PREF_KEY = "custom_games"
_MAX_LEN = 40


def get_custom_games() -> list:
    """Return the user's saved custom game names (empty list if none/malformed)."""
    val = get_pref(_PREF_KEY, [])
    return [str(g) for g in val] if isinstance(val, list) else []


def all_games() -> list:
    """Built-in games first, then customs — case-insensitively de-duplicated."""
    seen = set()
    out = []
    for game in BUILTIN_GAMES + get_custom_games():
        key = game.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(game)
    return out


def add_custom_game(name: str) -> bool:
    """Add a custom game. Returns True if added, False if blank or a duplicate
    (case-insensitively) of a built-in or an existing custom."""
    name = (name or "").strip()[:_MAX_LEN]
    if not name:
        return False
    if name.lower() in {g.strip().lower() for g in all_games()}:
        return False
    set_pref(_PREF_KEY, get_custom_games() + [name])
    return True
