# Lorebox — in-app review prompt (design)

**Date:** 2026-08-15
**Status:** approved, ready for implementation plan
**Store listing:** `9N94V4458M3V` (https://apps.microsoft.com/store/detail/9N94V4458M3V)

## Goal

Ask committed users to review Lorebox on the Microsoft Store, at most twice, without
interrupting their work — plus a permanent manual entry point in Settings for users
who want to review on their own initiative.

## Why cards, not hours

The trigger is cumulative cards in the collection, not time-in-app.

Card count is the value moment: a user with 50 cards has proven the scan → identify →
value loop works for them. Time-in-app is a weak proxy — the window can sit open on a
second monitor all day without a single card being added — and it would need a new
persisted accumulator on top of `MainWindow._session_start`. Card count is already
tracked exactly, via `db.get_collection_stats()['total_cards']`, and is inherently
durable across restarts because it lives in the database.

## Trigger rules

First ask at **50 cards**. Second ask requires **200 more cards than the count at the
first ask**. Hard ceiling of **two asks, ever**.

The second threshold is relative, not absolute. An absolute second threshold (e.g.
"250 cards") is breakable, because `BatchTab.cards_added` fires once with a whole
import's count:

> A user at 40 cards imports a 200-card box. The count jumps to 240 and the first ask
> fires. They click "Not now". The next single card takes them to 250 and the second
> ask fires — two asks, ten cards apart.

Anchoring on `review_prompt_last_count + 200` guarantees a genuine 200-card gap
regardless of the user's trajectory.

The threshold test fires on a **crossing**, not on every add above the line, so later
saves cannot repeatedly re-arm an already-armed prompt.

## Framing

A straight ask. No sentiment gate — no "are you enjoying Lorebox?" pre-question that
routes happy users to the Store and unhappy users to a feedback form. Microsoft does
not prohibit rating gates, but they are manipulative, and an honest negative review is
information worth having. This is consistent with the project's credibility-first
standard.

### Copy

> **Getting value out of Lorebox?**
>
> Reviews on the Microsoft Store are the main way other collectors find it.
> Takes about a minute.

Buttons: **Rate Lorebox** · **Not now** · **Don't ask again**

No emoji, no exclamation marks, concrete about why the ask is being made.

## Architecture

Two new modules, following the existing `core/` = logic, `ui/` = Qt split. The decision
logic imports no Qt, so it is unit-testable in an environment without PyQt6 — which
matters, since the current suite cannot run without the full dependency set installed.

### `core/review_prompt.py`

Policy over prefs. **No module-level Qt import** — `open_store_review()` imports
`QDesktopServices` / `QUrl` lazily inside the function body, matching how
`ui/main_window.py:132` and `ui/batch_review_dialog.py:409` already defer Qt imports.

The reason is layering, not testability: `core/` holds policy and should not take a
direct Qt dependency for one hand-off call. It does **not** make the module importable
without PyQt6 — `core/__init__.py:5-10` eagerly imports `scanner`→`cv2` and
`auth`→`PyQt6`, so any `core.*` import already pulls in the full dependency set. The
policy tests therefore need the complete environment like every other test in the suite.

```
STORE_PRODUCT_ID  = "9N94V4458M3V"
STORE_REVIEW_URI  = "ms-windows-store://review?ProductId=9N94V4458M3V"
STORE_WEB_URL     = "https://apps.microsoft.com/store/detail/9N94V4458M3V"

FIRST_THRESHOLD   = 50
REPEAT_GAP        = 200
MAX_ASKS          = 2

should_prompt(card_count: int) -> bool
mark_prompted(card_count: int) -> None
mark_rated() -> None
mark_declined(permanent: bool) -> None
open_store_review() -> None      # deep link, web fallback
```

`open_store_review()` is the single Store hand-off used by both the automatic dialog and
the Settings button, so the listing ID lives in exactly one place.

### `ui/review_dialog.py`

A small `QDialog` with the three buttons above. Owns no policy — it calls into
`core.review_prompt` for every state transition.

## State

Four keys in `prefs.json`, via the existing `get_pref` / `set_pref`. These are not
secrets, so they belong in prefs rather than the encrypted config.

| key | meaning |
|---|---|
| `review_prompt_count` | 0, 1, or 2 — asks used |
| `review_prompt_last_count` | card count at the last ask, anchors the +200 gap |
| `review_prompt_dismissed` | permanent stop — Rate, Don't-ask-again, or Settings button |
| `review_prompt_due` | armed but not yet shown (deferred past a modal) |

Gate:

```
not dismissed
and count < MAX_ASKS
and card_count >= (FIRST_THRESHOLD if count == 0 else last_count + REPEAT_GAP)
```

## Timing — never interrupt a save

`MainWindow` already connects `scan_tab.card_added` and `batch_tab.cards_added` to three
refresh slots. A fourth slot, `_maybe_prompt_review`, joins them and reads the card count
from the `get_collection_stats()` call already being made for the dashboard refresh.

On a threshold crossing the slot sets `review_prompt_due` and fires
`QTimer.singleShot(1500, ...)`. When it fires:

- If `QApplication.activeModalWidget()` is not `None` — a Batch Review dialog is still
  closing, or a save is in progress — the dialog does **not** show. `review_prompt_due`
  stays set and the prompt appears at next launch instead.
- Otherwise the dialog shows, and `mark_prompted(card_count)` records the anchor and
  clears `review_prompt_due`.

`review_prompt_due` is therefore cleared in exactly one place: `mark_prompted()`, called
when the dialog is actually displayed. Arming it is idempotent — an already-armed prompt
that gets re-armed by a later save is unchanged.

The deferred case is drained on the next run: `MainWindow` checks `review_prompt_due` once
during startup and, if set, shows the dialog through the same `QTimer.singleShot(1500)` +
modal-check path. Startup uses the same code path as the live trigger, so there is one
display routine, not two.

The ask therefore always lands on a quiet app and never stacks on top of a modal.

## Settings entry point

A new **About Lorebox** group in `ui/settings_dialog.py`, inserted between the Appearance
group and the Save/Cancel button box (currently line 165–168), containing one button:
**Rate Lorebox on the Microsoft Store**.

`settings_dialog.py` already imports `QDesktopServices` and `QUrl`, so no new imports.

Behavior:

- Ignores all gating. Works at zero cards and after a permanent dismissal — this is the
  user asking, not the app.
- **Sets `review_prompt_dismissed`.** Being nagged to review an app you already went and
  reviewed is the most irritating version of this feature. The cost is that a user who
  clicks it merely to look around also stops being asked automatically; that trade is
  accepted deliberately.

## Instrumentation

Three events via the existing `core.usage.log_event`, primitives only so they stay within
`_safe_props` and the PII-free export guarantee:

| event | props |
|---|---|
| `review_prompt_shown` | `card_count` |
| `review_prompt_rated` | `source` — `"prompt"` or `"settings"` |
| `review_prompt_declined` | `permanent` — bool |

The `source` prop distinguishes which entry point actually earns reviews.

## Why not the WinRT in-app rating sheet

`StoreContext.RequestRateAndReviewAppAsync` shows a native rating sheet without leaving
the app, but it requires a packaged MSIX identity. It would throw in the PyInstaller dev
build and in any sideload, meaning a code path that cannot be tested locally. The
`ms-windows-store://` deep link works in both, with an `https://` fallback if the
protocol handler is unavailable.

## Testing

`tests/test_review_prompt.py`, pytest-style like the existing sync tests, monkeypatching
the prefs path to `tmp_path`. Pure Python — no Qt, no display.

- below threshold → no prompt
- at threshold → prompt
- "Not now" at 50 → no second prompt at 249, prompt at 250
- **batch jump:** first ask at 240 → no second ask at 250 → second ask at 440
- no third ask after two
- "Don't ask again" → permanent, even far past the gap
- "Rate" → permanent
- Settings button → sets permanent dismissal
- arming is idempotent — re-arming an already-armed prompt does not change state
- `mark_prompted()` clears `review_prompt_due` and records the anchor together

The batch-jump case is the regression test for the bug this design corrects.

The modal-deferral and next-launch display paths are Qt-level and are not covered by this
suite; they are verified manually against a running app.

## Out of scope

- Time-based triggering
- Sentiment gating
- In-app star capture or review text
- Prompting on anything other than card count (e.g. successful valuations, reports run)
