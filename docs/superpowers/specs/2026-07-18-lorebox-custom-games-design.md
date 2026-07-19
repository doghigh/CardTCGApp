# LoreBox — Custom Game Categories

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Author:** Jesse + Claude

## Problem

Cards whose game isn't in the fixed built-in list fall into catch-alls ("Other"
/ "Non-Sport"). Users want to add their own game categories (e.g. "Digimon",
"Flesh and Blood") so their collection and dashboard breakdown are organized the
way they collect. The built-in `GAMES` list is also **duplicated** across
`ui/dialogs.py` and `ui/batch_review_dialog.py`, with a third inline copy in
`ui/scan_tab.py` — so there's no single source of truth to extend.

## Goal

Let users add custom game categories via a deliberate **"➕ Add game" button in
the Batch Review dialog** (where mis-bucketed cards are caught before saving).
Added games persist and appear in **every** game dropdown app-wide. Centralize
the built-in list so there's one source of truth.

## Non-goals

- No settings-management screen (add-only for now; removing a custom game is a
  trivial YAGNI follow-up).
- The vision auto-identify prompt is **unchanged** — it still returns only the
  built-in game enum. Custom games are a *manual* organization feature; a scanned
  card won't auto-classify as a custom game (the user picks it in review). This
  is expected and stated in the UI's mental model, not a gap.
- No DB schema change — `game` is already a free-text column.

## Architecture

```
core/games.py  ── BUILTIN_GAMES (single source of truth)
                  get_custom_games()  ← prefs "custom_games"
                  add_custom_game(name) → validates + dedupes + persists
                  all_games()  = BUILTIN_GAMES + custom (deduped, order-stable)
        ▲                     ▲                         ▲
        │                     │                         │
  scan_tab game_combo   dialogs card-detail combo   batch_review per-row combos
  (reads all_games)     (reads all_games)           (read all_games)
                                                          ▲
                                              "➕ Add game" button
                                              → add_custom_game → repopulate row combos
```

### `core/games.py` (new — single source of truth)

- `BUILTIN_GAMES: list[str]` — the canonical built-in list (moved from the
  duplicated `GAMES` definitions), ending with the "Non-Sport" / "Other"
  catch-alls:
  `["Baseball", "Basketball", "Football", "Hockey", "Sports Cards",
    "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece", "Lorcana",
    "Flesh and Blood", "Non-Sport", "Other"]`
- `get_custom_games() -> list[str]` — reads the prefs key `"custom_games"`
  (a JSON list via `core.config.get_pref`); returns `[]` if unset/malformed.
- `add_custom_game(name: str) -> bool` — trims the name; rejects empty; **dedupes
  case-insensitively** against BUILTIN + existing custom (so no duplicate and no
  shadowing of a built-in); on a genuinely new name, appends to prefs
  (`set_pref("custom_games", ...)`, capped to a sane length e.g. 40 chars) and
  returns `True`. Returns `False` when nothing was added (empty or duplicate).
- `all_games() -> list[str]` — `BUILTIN_GAMES` followed by custom games, with
  case-insensitive de-duplication and stable order (built-ins first, customs in
  insertion order).

### Surfaces that read `all_games()`

Replace the three hard-coded lists with `all_games()`:
- `ui/scan_tab.py` — the inline `addItems([...])` at ~line 286 (combo is already
  `setEditable(True)`; keep that — it's a harmless bonus).
- `ui/dialogs.py` — `self.game_combo.addItems(GAMES)` (~line 168); remove the
  local `GAMES` (line 18), import from `core.games`.
- `ui/batch_review_dialog.py` — `game_combo.addItems(GAMES)` (~line 340); remove
  the local `GAMES` (line 33), import from `core.games`.

### The "➕ Add game" button (Batch Review dialog)

- A button labelled "➕ Add game" in the dialog's button bar.
- Click handler:
  1. `QInputDialog.getText(self, "Add game category", "New game name:")`.
  2. If accepted and non-blank: `added = games.add_custom_game(name)`.
  3. If `added`: **repopulate every row's game combo** — for each row's
     `COL_GAME` `QComboBox`, remember its `currentText()`, `clear()`,
     `addItems(all_games())`, then restore the previous selection via
     `findText` (so no row's existing choice is lost); the new game is now
     selectable on any row.
  4. If not added (empty/duplicate): a brief, non-blocking notice (status text
     or a small `QMessageBox.information`), no error.

## Data

- Prefs key `"custom_games"`: a JSON list of strings (e.g. `["Digimon", "Sorcery"]`).
- Stored via the existing `core.config` prefs (`prefs.json`, non-secret,
  honors the data dir). No new storage mechanism.

## Testing

`tests/test_games.py` (prefs isolated via monkeypatched `core.config.PREFS_FILE`,
so no live prefs touched):

- `all_games()` with no customs == `BUILTIN_GAMES`.
- `add_custom_game("Digimon")` returns True, then `all_games()` contains
  "Digimon" after the built-ins; `get_custom_games()` == `["Digimon"]`.
- `add_custom_game("")` / whitespace → False, nothing added.
- Case-insensitive dedupe: `add_custom_game("baseball")` (built-in) → False;
  adding "Digimon" twice (any case) keeps one entry.
- Persistence round-trip: added game survives re-reading via `get_custom_games`.

(UI wiring — the three combos reading `all_games()` and the Add button — is
verified by import-smoke + full suite; the logic under test lives in
`core/games.py` and is fully covered.)

## Open items / follow-ups

- Removing / renaming a custom game (settings UI) — deferred, YAGNI.
- Teaching the vision prompt about custom games (so scans auto-classify) —
  deferred; would require passing the user's custom list into the prompt.
