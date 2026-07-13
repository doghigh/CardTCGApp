# LoreBox — Claude-Vision Card Grading

**Date:** 2026-07-13
**Status:** Design approved, pending spec review
**Author:** Jesse + Claude

## Problem

The CV condition grader (`core/inspector.py`) systematically under-detects real
damage and mis-labels grades. Reported by a user card: a Fleer "Award Winner"
Bert Blyleven with the **top-right corner physically torn off** (exposing brown
cardboard) graded **Near Mint (78)**.

### Reproduced root causes

**Bug A — one-directional damage detection.** The corner/edge detectors only
flag regions *whiter* than the card's own border baseline (whitening, frayed
white edges). Missing material that exposes the darker cardboard core produces
a region *darker* than baseline → negative "excess" → structurally below every
threshold. Verified: on a clean card (Roger Clemens, same Fleer design) a
simulated brown torn corner scored **80 (Near Mint)** and the corner detector
returned `[]`; the tip measured `white_ratio=0.000` against `baseline=1.0`, i.e.
`excess = -1.0`. A *white* hole (scanner bed) at the same corner scored 68 —
proving the grader scores exposed-cardboard damage (worse) *higher* than a white
gap (better), purely because it can only see white. Even the white hole it can
see caps at a 14-point "severe corner" penalty — far too light for missing
material.

**Bug B — grade-bin gaps.** `GRADES` uses integer-bounded ranges with gaps:
`Mint (88,94)`, `Gem Mint (95,100)`. A score of 94.1–94.9 (and 75.x, 87.x, …)
matches no band, and the grading loop falls through to its default
`grade = 'Poor'`. Six cards in the live 615-card DB are currently mis-labeled
"Poor" at scores of 94.x / 75.4 despite being high-quality cards.

**Scale of impact:** 89.8% of the 615-card collection grades Near Mint or
better; 35% Gem Mint — implausible for a vintage flatbed-scanned collection, and
clean vs. damaged cards land at indistinguishable scores.

## Goal

Grade condition with Claude vision (which trivially recognizes tears, chips,
creases, and scratches that pixel-brightness heuristics cannot), keep the CV
inspector as an offline fallback, and fix the grade-bin gaps so grade and score
never contradict. Provide a way to re-grade the existing mis-graded collection.

## Non-goals / deferred

- **Offline card-outline integrity detector** (contour-notch detection so the CV
  fallback also catches torn corners) — deferred to a follow-up; vision is the
  primary grader and handles tears.
- Changing the DB schema, the 8-point grade scale, or the valuation pipeline.
- A stronger/dedicated grading model — v1 reuses the identify model.

## Architecture

```
Scan / Batch / Re-identify
        │
        ├─ identifier.identify_card(front, back)   ← ONE vision call, now returns
        │        (name/set/… + condition_score + defects, source marker)
        │
        └─ grading.resolve_condition(info, front_img)
                 ├─ vision condition present (source=='claude') → use it
                 └─ else → CardInspector.inspect(front_img)   (offline fallback)
                 → {grade, score, defects, source}
                    grade ALWAYS = grading.grade_for_score(score)   (single source of truth)
```

**One merged vision call.** Grading folds into the existing identify call — the
prompt already sends the front (and back) image to Claude; adding condition to
its JSON response costs only a few output tokens and **no second API call**.
Grading therefore flows through the trial/own-key routing and monthly spend cap
already in place.

**Single source of truth for grade.** A new `core/grading.py` owns
`grade_for_score(score) -> str` with **contiguous** bands (Bug B fixed). Both the
vision path and the CV fallback derive the grade label from the numeric score
via this one function, so grade and score can never diverge again.

## Components

### 1. Vision prompt extension (`core/identifier.py`)

Extend `VISION_PROMPT` and the `_identify_with_claude` JSON parse to also return:

- `condition_score`: integer 0–100.
- `defects`: list of `{type, location, severity}`.

**Rubric** embedded in the prompt so the model calibrates to our scale, with an
explicit instruction that **missing material (torn/chipped corner or edge,
exposed cardboard) caps the grade at Good (≤51) or lower**, and heavy
creasing/staining is Excellent-or-lower:

| Band | Score | Meaning |
|------|-------|---------|
| Gem Mint | 95–100 | Pristine; sharp corners, clean edges/surface, centered |
| Mint | 88–94 | Near-perfect; a trivial flaw |
| Near Mint | 76–87 | Light wear; minor corner/edge touch |
| Excellent | 64–75 | Noticeable corner/edge wear or a light crease |
| Very Good | 52–63 | Multiple defects; visible creasing/edge wear |
| Good | 40–51 | Heavy wear, or a small chip/tear |
| Played | 25–39 | Major creasing, staining, or edge/corner loss |
| Poor | 0–24 | Severe damage, large tears, missing material |

**Defect vocabulary** (so output maps to the existing defects display):
- `type`: `missing_material` (torn/chipped/exposed cardboard), `corner_damage`,
  `edge_wear`, `surface_crease`, `surface_scratch`, `staining`, `print_defect`,
  `off_centering`.
- `location`: `top_left|top_right|bottom_left|bottom_right|top|bottom|left|right|center`.
- `severity`: `minor|moderate|severe`.

Parsing is defensive: unknown types/locations pass through as-is; a missing or
malformed `condition_score` means "no vision condition" (→ fallback), never a
crash. The identify result dict gains an optional `condition` key
`{score: int, defects: list}`; `None`/absent when vision didn't return it (OCR
or trial-blocked paths).

### 2. `core/grading.py` (new)

```
GRADE_BANDS: contiguous, ordered (see below)

def grade_for_score(score: float) -> str
    # clamps to [0,100]; returns the band whose range contains score.

def resolve_condition(info: dict, front_img, inspector) -> dict
    # returns {'grade','score','defects','source'}
    #  - if info.get('condition') present → source 'vision', score from it,
    #    defects from it, grade = grade_for_score(score)
    #  - else → inspection = inspector.inspect(front_img); source 'cv',
    #    grade = grade_for_score(inspection score) (so CV also uses the fix)
```

**Contiguous bands** (Bug B fix) — every score in [0,100] maps to exactly one
grade, no gaps:

| Grade | Range (inclusive lower, exclusive upper except top) |
|-------|------|
| Gem Mint | 95–100 |
| Mint | 88–95 |
| Near Mint | 76–88 |
| Excellent | 64–76 |
| Very Good | 52–64 |
| Good | 40–52 |
| Played | 25–40 |
| Poor | 0–25 |

`CardInspector.GRADES` is refactored to defer to `grade_for_score` (or the
inspector imports and uses it) so there is exactly one grade-derivation
implementation.

### 3. Scan / Batch / Re-identify integration

Replace the direct `inspector.inspect(...)` calls with
`grading.resolve_condition(info, front_img, inspector)`:

- `ui/scan_tab.py::_inspect` (line ~497) — but note scan currently runs
  `_auto_identify` and `_inspect` separately; `_inspect` gains access to the
  `info` from the last identify so it can prefer vision condition. Store the
  last identify result on the tab and pass it in.
- `ui/batch_tab.py` (line ~212) — `info` is already in scope at the call site;
  swap `inspection = self.inspector.inspect(front)` for
  `resolve_condition(info, front, self.inspector)`. The `card_data` keys
  (`condition_grade`, `condition_score`, `defects`) come from the result.
- `ui/batch_review_dialog.py` (line ~99) and any re-identify path — same swap.

The DB write path is unchanged (`condition_grade`, `condition_score`, `defects`
→ `defects_json`).

### 4. "Re-grade collection" action

A user-triggered batch (menu item in `ui/main_window.py`, e.g. under a Tools/
Collection menu) that re-grades existing cards:

- **Confirm dialog with cost estimate:** counts cards with an on-disk front
  scan, shows "Re-grade N cards (~$X.XX via Claude vision / your trial or key)?"
  before running. `X = N * 0.006`.
- For each card with a readable `front_scan_path` (and optional back): run the
  merged vision call (`identify_card` on the stored images) and apply **only**
  the condition fields via `db.update_card(id, {'condition_grade','condition_score','defects'})`.
  Name/set/etc. are never overwritten.
- If a card comes back trial-blocked (`source` starts with `trial_`), stop and
  surface the key-setup dialog (reusing `key_setup_requested` / `_open_key_setup`)
  — don't silently burn through and no-op the rest.
- Cancelable, with a progress indicator; runs off the UI thread
  (QThread/worker, mirroring the existing batch worker pattern).
- Skips (and reports a count of) cards whose scan files are missing.
- CV fallback applies per-card when vision is unavailable, same as a fresh scan.

### 5. Database

No schema change. Uses existing `update_card` (already whitelists
`condition_grade`, `condition_score`, `defects`) and `get_all_cards` /
`get_card`.

## Failure handling

- Vision returns no/invalid `condition_score` → treated as "no vision condition"
  → CV fallback. Never crashes.
- Vision unreachable / trial exhausted on a fresh scan → existing trial-blocked
  behavior for identification already handles the UX; condition falls back to CV
  when an image is available.
- Re-grade on trial exhaustion → stop + key-setup dialog (see component 4).
- A trial credit is still consumed only on a confirmed successful vision call
  (unchanged from the trial feature; grading rides the same call).

## Model

`claude-haiku-4-5-20251001` (same as identify) for v1 — one call, cheap.
Revisit if grading accuracy needs a stronger model.

## Testing

- `grade_for_score`: every boundary (94, 95, 87, 88, 75, 76, …) maps to the
  right band; the exact Bug-B cases (94.5 → Mint, 75.4 → Excellent) no longer
  return "Poor"; full [0,100] coverage has no gap.
- Vision condition parse: a response with `condition_score` + `defects` yields a
  `condition` dict; a missing/malformed score yields no condition (→ fallback);
  malformed JSON never crashes.
- `resolve_condition`: prefers vision when present; falls back to CV when absent;
  grade always equals `grade_for_score(score)` on both paths.
- CV inspector still produces consistent grade/score after refactor (regression:
  a known image grades the same score, and its grade now comes from the shared
  function).
- Re-grade worker: applies condition-only (name/set untouched) via a fake DB;
  skips cards with missing scan files; stops + signals key-setup on a trial_*
  result.

## Open items / follow-ups

- Offline card-outline integrity detector (deferred).
- Whether to auto-prompt a re-grade after upgrading (left as a manual action).
- Possible stronger grading model if haiku under-grades.
