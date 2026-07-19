# Custom Game Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users add custom game categories via a "➕ Add game" button in the Batch Review dialog; added games persist in prefs and appear in every game dropdown app-wide.

**Architecture:** A new `core/games.py` is the single source of truth — `BUILTIN_GAMES` (moved from the two duplicated `GAMES` lists) plus prefs-backed customs, exposed as `all_games()`. The three game dropdowns read `all_games()`; the Add button calls `add_custom_game()` and repopulates the review-table combos.

**Tech Stack:** Python 3.11 stdlib + existing `core.config` prefs; PyQt6 (existing). Spec: `docs/superpowers/specs/2026-07-18-lorebox-custom-games-design.md`.

## Global Constraints

- Add-only; case-insensitive dedupe against built-ins + existing customs; custom name trimmed and capped at **40 chars**.
- `BUILTIN_GAMES` is exactly (order preserved): `["Baseball", "Basketball", "Football", "Hockey", "Sports Cards", "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece", "Lorcana", "Flesh and Blood", "Non-Sport", "Other"]`.
- Customs persist in prefs key `"custom_games"` (JSON list) via `core.config.get_pref`/`set_pref`. No new storage, no DB schema change, no vision-prompt change.
- `all_games()` order: built-ins first, then customs (insertion order), case-insensitively de-duplicated.
- No new runtime dependency.

---

## File Structure

- Create: `core/games.py` — `BUILTIN_GAMES`, `get_custom_games`, `add_custom_game`, `all_games`.
- Create: `tests/test_games.py`.
- Modify: `ui/dialogs.py` — remove local `GAMES`, read `all_games()`.
- Modify: `ui/batch_review_dialog.py` — remove local `GAMES`, read `all_games()`, add the "➕ Add game" button + handler.
- Modify: `ui/scan_tab.py` — the inline game list reads `all_games()`.

---

## Task 1: `core/games.py` — the games source of truth

**Files:**
- Create: `core/games.py`
- Test: `tests/test_games.py`

**Interfaces:**
- Produces: `BUILTIN_GAMES: list[str]`, `get_custom_games() -> list[str]`, `add_custom_game(name: str) -> bool`, `all_games() -> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_games.py
import core.config as config_mod
import core.games as games


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_all_games_defaults_to_builtin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.all_games() == games.BUILTIN_GAMES


def test_add_custom_game_appends_after_builtins(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("Digimon") is True
    result = games.all_games()
    assert result[: len(games.BUILTIN_GAMES)] == games.BUILTIN_GAMES
    assert result[-1] == "Digimon"
    assert games.get_custom_games() == ["Digimon"]


def test_empty_or_whitespace_rejected(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("   ") is False
    assert games.add_custom_game("") is False
    assert games.get_custom_games() == []


def test_dedupe_is_case_insensitive(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("baseball") is False    # shadows a built-in
    assert games.add_custom_game("Digimon") is True
    assert games.add_custom_game("digimon") is False     # case-insensitive dup
    assert games.get_custom_games() == ["Digimon"]


def test_persistence_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    games.add_custom_game("Sorcery")
    assert "Sorcery" in games.get_custom_games()
    assert "Sorcery" in games.all_games()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_games.py -v`
Expected: FAIL — `No module named 'core.games'`.

- [ ] **Step 3: Write the implementation**

```python
# core/games.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_games.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (105 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add core/games.py tests/test_games.py
git commit -m "feat(games): single source of truth for built-in + custom games"
```

---

## Task 2: Point every game dropdown at `all_games()`

**Files:**
- Modify: `ui/dialogs.py` (remove `GAMES` at line ~18; `addItems(GAMES)` at ~168)
- Modify: `ui/batch_review_dialog.py` (remove `GAMES` at line ~33; `addItems(GAMES)` at ~340)
- Modify: `ui/scan_tab.py` (inline `addItems([...])` at ~286)

**Interfaces:**
- Consumes: `core.games.all_games`.

- [ ] **Step 1: `ui/dialogs.py`**

Remove the local `GAMES = [ ... ]` block (lines ~18-22). Add near the top imports:

```python
from core.games import all_games
```

Change (line ~168):

```python
        self.game_combo.addItems(GAMES)
```
to:
```python
        self.game_combo.addItems(all_games())
```

- [ ] **Step 2: `ui/batch_review_dialog.py`**

Remove the local `GAMES = [ ... ]` block (lines ~33-37). Add near the top imports:

```python
from core.games import all_games
```

Change (line ~340):

```python
        game_combo.addItems(GAMES)
```
to:
```python
        game_combo.addItems(all_games())
```

- [ ] **Step 3: `ui/scan_tab.py`**

READ around line 284-290 first. The game combo is built with an inline list:

```python
        self.game_combo = QComboBox()
        self.game_combo.setEditable(True)
        self.game_combo.addItems([
            ...inline list...
        ])
```

Add `from core.games import all_games` to the top imports and replace the inline
`addItems([...])` with:

```python
        self.game_combo.addItems(all_games())
```

Leave `setEditable(True)` as-is (harmless bonus).

- [ ] **Step 4: Import-smoke + full suite**

Run: `python -c "import ui.dialogs, ui.batch_review_dialog, ui.scan_tab"`
Expected: exit 0.
Run: `python -m pytest tests/ -q`
Expected: PASS (110 — unchanged from Task 1; no test asserts on these combos).

- [ ] **Step 5: Commit**

```bash
git add ui/dialogs.py ui/batch_review_dialog.py ui/scan_tab.py
git commit -m "refactor(games): all game dropdowns read the shared games list"
```

---

## Task 3: "➕ Add game" button in Batch Review

**Files:**
- Modify: `ui/batch_review_dialog.py` (add the button to the button bar + a handler)

**Interfaces:**
- Consumes: `core.games.add_custom_game`, `core.games.all_games`; the per-row game combo at column `COL_GAME`.

- [ ] **Step 1: Add the button + handler**

READ `ui/batch_review_dialog.py` to find where the bottom button bar is built (the row that holds Save/Cancel-style buttons — search for `QPushButton` in the dialog's layout methods, likely near a `_build_review_phase` / button-row section). Add a button there:

```python
        add_game_btn = QPushButton("➕ Add game")
        add_game_btn.setToolTip("Add a custom game category (applies to all rows)")
        add_game_btn.clicked.connect(self._add_game_category)
        # add to the same button row/layout as the other dialog buttons
```

Add this handler method to the `BatchReviewDialog` class:

```python
    def _add_game_category(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from core.games import add_custom_game, all_games
        name, ok = QInputDialog.getText(self, "Add game category", "New game name:")
        if not ok:
            return
        if not add_custom_game(name):
            QMessageBox.information(
                self, "Not added",
                "Enter a new game name that isn't already in the list.")
            return
        # Refresh every row's game combo, preserving each row's current choice.
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, COL_GAME)
            if combo is None:
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(all_games())
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else combo.count() - 1)
            combo.blockSignals(False)
```

(`QPushButton` is already imported in this file; `COL_GAME` and `self._table` already exist.)

- [ ] **Step 2: Import-smoke**

Run: `python -c "import ui.batch_review_dialog"`
Expected: exit 0.

- [ ] **Step 3: Full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (110).

- [ ] **Step 4: Commit**

```bash
git add ui/batch_review_dialog.py
git commit -m "feat(games): Add-game button in Batch Review repopulates row combos"
```

---

## Self-Review

**Spec coverage:**
- `core/games.py` single source of truth (BUILTIN + customs, all_games/add/get) → Task 1. ✅
- Case-insensitive dedupe, empty-reject, 40-char cap, prefs persistence → Task 1 + tests. ✅
- All three dropdowns read `all_games()`; duplicated `GAMES` lists removed → Task 2. ✅
- "➕ Add game" button in Batch Review + repopulate row combos preserving selections → Task 3. ✅
- No DB/schema change, no vision-prompt change → nothing in the plan touches them. ✅

**Placeholder scan:** No "TBD"/"add error handling"/"write tests for the above". Task 2 step 3 and Task 3 step 1 explicitly say READ the file first (the scan inline list and the button-bar location) because exact lines vary — with the precise before/after given.

**Type consistency:** `all_games() -> list[str]`, `add_custom_game(name) -> bool`, `get_custom_games() -> list[str]`, `BUILTIN_GAMES` (Task 1) used consistently in Tasks 2 & 3. Prefs key `"custom_games"` and the `COL_GAME` column name match the existing code.
