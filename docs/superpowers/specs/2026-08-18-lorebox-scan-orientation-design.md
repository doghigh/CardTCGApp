# Lorebox — automatic scan-orientation correction (design)

**Date:** 2026-08-18
**Status:** approved, ready for implementation plan

## Background

Reported during manual testing of a 243-card batch scan session: cards were coming
out of the collection with their back image (and occasionally the front) rotated
90° or 180° from upright, seemingly at random. A companion report from the same
session — saved order not matching scan order — is a separate, already-fixed bug
(natural-sort fix, commit `e6f3b37`); this spec covers only the orientation issue.

## Root cause

Traced through `core/scanner.py`, `ui/scan_tab.py`, and `utils/image_ops.py`:

- The Scan tab's duplex checkbox defaults to checked. A "Scan Card" click drives a
  TWAIN scanner with a document feeder, capturing front and back for each physical
  card as it passes through (`core/scanner.py: scan()`).
- The TWAIN loop appends whatever the driver returns, with no orientation logic of
  any kind — nothing in the pipeline knows or corrects for how a physical card was
  placed in the feeder.
- `deskew()` (`utils/image_ops.py`) is mathematically incapable of ever catching
  this: a rectangle and its 180°-rotated copy occupy an identical pixel silhouette,
  so `cv2.minAreaRect` cannot distinguish them. Deskew only corrects tilt within
  ±15°; it is blind to 90°/180° flips by geometry, not by a missed case.
- A field screenshot confirmed the front and back of one physical card were
  rotated *together*, consistently with each other — the signature of a single
  card entering the feeder rotated, not a software bug transposing front and back
  independently.

Net effect: the app has no automatic upright-detection at all. Any card that goes
into the feeder rotated saves rotated, with the existing manual rotate buttons
(`ui/scan_tab.py: _make_rotate_bar` / `_transform`) as the only recourse. Doing
that by hand across 243 cards is why it read as "random" — it varies per how each
card happened to be placed, not from any pattern in the code.

## Why Tesseract OSD was ruled out

The initial hypothesis was Tesseract's orientation-and-script-detection (OSD),
already an optional dependency in this codebase (`core/identifier.py: HAS_TESSERACT`).
It was tested empirically before being designed around, not assumed:

Two synthetic 300-DPI card-scale images were built with real TrueType text — one
text-rich (mimicking an MTG front: name, type line, rules text), one text-sparse
and symmetric (mimicking an MTG back: a decorative ellipse and a small
"DECKMASTER" wordmark, no body text) — each tested at 0°/90°/180° rotation via
`tesseract --psm 0`:

```
FRONT (text-rich):
  0°   -> Rotate: 0    correct
  180° -> Rotate: 180  correct
  90°  -> Rotate: 90   correct

BACK (symmetric, sparse text):
  0° / 90° / 180° -> "Too few characters. Skipping this page. Error during processing."
```

OSD works cleanly on fronts and fails outright — a hard error, not merely low
confidence — on backs at every rotation. It needs actual character strokes to
analyze; a symmetric card-back design doesn't give it enough to work with.
Building the fix around OSD would solve fronts and do nothing for the reported
case (backs).

A front-detects/back-inherits design (using the fact that front and back rotate
together, per the screenshot evidence above) would work around this, but a second
option was identified and chosen instead: use Claude vision, already called for
every card via `identify_card()`, to judge orientation directly — including on the
back, where a real vision-language model can likely reason from composition and
symmetry even without readable text, unlike character-stroke-dependent OCR.

## Chosen approach: piggyback on `identify_card()`

No new dependency, no new API call. `identify_card(front, back)` already sends
both images to Claude in one message; the response gains two additional fields.

### Detection

`VISION_PROMPT` (`core/identifier.py`) gains:

```
- front_rotation: degrees to rotate the FRONT image clockwise to make it upright
    (0, 90, 180, or 270). 0 if already upright or you are not confident.
- back_rotation: same, for the back image (0 if no back image was provided, or
    if unreadable/unclear). Many card-game backs have little or no body text —
    use whatever text or wordmark IS present (e.g. a small logo) and its reading
    direction; if there is truly no orientation cue, answer 0 rather than guess.
```

This follows the prompt's existing "if unreadable, use null rather than guessing"
philosophy for other fields — biasing the model toward `0` (no correction) on
genuinely ambiguous images, which is what makes auto-apply (below) an acceptable
default rather than a risky one.

`_identify_with_claude()` parses and clamps both fields to `{0, 90, 180, 270}`,
defaulting to `0` on anything missing, non-numeric, or out of range. Both keys are
always present in the returned dict as plain ints — callers never need to
`None`-guard them.

### Correction

`utils/image_ops.py` gains one dispatcher:

```python
def rotate_by(img, degrees: int):
    """Rotate img by 0/90/180/270 degrees clockwise. Any other value is a no-op."""
```

It maps `90 -> rotate_90_cw`, `180 -> rotate_180`, `270 -> rotate_90_ccw`, and
passes the image through unchanged for `0` or any unrecognized value. No new
rotation math — a dispatcher over the three functions already in this file.

### Wiring — two call sites cover three entry points

`identify_card()` has five call sites in the codebase. Three are "new capture"
flows and are in scope; two are "re-identify an existing card" flows and are
explicitly out of scope (see below).

- **`ui/scan_tab.py` — `_auto_identify()`.** After `identify_card()` returns,
  apply `rotate_by()` to `self.current_front_img` / `self.current_back_img` and
  refresh both `ImageViewer`s via `front_view.set_image()` / `back_view.set_image()`
  — the same update pattern `_transform()` already uses for the manual rotate
  buttons, so the user sees the corrected image immediately, before saving.

- **`ui/batch_review_dialog.py` — `_process()`.** Apply `rotate_by()` to the local
  `front` / `back` right after its `identify_card()` call, before thumbnailing or
  `resolve_condition()` grading — so the review table shows the corrected image
  and the saved bytes match what's displayed.

- **`ui/batch_tab.py` — `ImageBatchWorker.run()`.** Apply `rotate_by()` to the
  local `front` / `back` right after `identify_card()`, before `resolve_condition()`
  and before `cv2.imwrite()`. Watch-folder import (`core/watcher.py` +
  `ui/main_window.py: _run_watch_import`) instantiates this same worker class, so
  this one change covers both folder Batch Import and watch-folder auto-import —
  two entry points from one wiring site, not two separate changes.

Correction is applied once, immediately after identification, and every
downstream step (grading, thumbnailing, saving, display) operates on the
already-corrected image. There is exactly one place per call site where the
image can be "the image" — no parallel corrected/uncorrected copies to keep in
sync.

### Auto-apply, not flag-for-review

The correction is applied automatically, with no confirmation step — consistent
with how `deskew()` already behaves today (silent, automatic, no per-card
confirmation). The manual rotate buttons remain as the escape hatch if the model
is ever wrong. The alternative (flag only, require a manual click to confirm)
was rejected because it reintroduces the exact per-card manual work this feature
exists to remove, at the scale (243 cards) where it matters most.

### Explicitly out of scope

- **`ui/collection_tab.py`** and **`ui/regrade_dialog.py`** also call
  `identify_card()`, but to refresh metadata on an *already-saved* card, not to
  process a new capture. Wiring rotation there would silently rotate a saved
  image during what a user thinks is a metadata-only refresh — an unrelated
  behavior change bolted onto an existing feature. Left untouched. A "fix my
  already-crooked cards" bulk tool is a natural follow-up, but a different
  feature with its own design questions (which existing cards to touch, how to
  surface the change, undo).
- **No Tesseract/OSD fallback** for the no-API-key OCR path — see "Why Tesseract
  OSD was ruled out" above. That path gets no auto-correction, same as today.
- **No retroactive fix** for cards already saved wrong in the 243-card session
  that surfaced this bug. Out of scope for the reason above.
- **No new dependency** of any kind — this reuses the Anthropic API call the app
  already makes for every card.

## Testing

Two isolated units, following the exact conventions already in this repo:

- **`tests/test_identifier_rotation.py`** — mirrors `tests/test_identifier_condition.py`'s
  `_FakeClient` / `_FakeResp` pattern (a stub `client.messages.create()` returning
  fixed JSON text). Feeds `_identify_with_claude()` valid, missing, and
  out-of-range rotation values; asserts the parsed-and-clamped output. No network
  call, no Qt.
- **`tests/test_image_ops.py`** — extended with `rotate_by()` cases for
  `0/90/180/270` and an invalid value, checking output shape and a corner-pixel
  content check (not shape alone — shape can be right while content is wrong for
  a square image).

Plus one end-to-end regression, the pattern that mattered most in this debugging
session (a "does the fix actually reach the saved file" proof, not just unit
correctness in isolation): a fake identifier returning `front_rotation: 180`
driven through `ImageBatchWorker.run()` against a `tmp_path` folder, asserting the
**saved PNG bytes** are actually rotated relative to the input — proving the
wiring end to end, the same way `test_reproduces_and_fixes_the_243_file_scramble`
proved the natural-sort fix at realistic scale rather than only unit-testing the
sort key.

## Spec self-review

- **Placeholders:** none — every field, function signature, and call site is named
  exactly as it exists in the current codebase.
- **Internal consistency:** the "why OSD was ruled out" section and the "chosen
  approach" section agree — OSD's back-image failure is the stated reason for
  choosing Claude vision, not an afterthought.
- **Scope:** three new-capture call sites via two wiring changes (batch worker
  wiring covers two entry points). Two re-identify call sites explicitly excluded
  with rationale. Single spec, no decomposition needed.
- **Ambiguity:** "auto-apply" is fully specified (no confirmation step, matches
  deskew's existing behavior). The rotation value contract (`0/90/180/270` int,
  always present, `0` on any invalid input) is unambiguous and matches the
  existing defensive-parsing style already used for `condition_score` in the same
  function.
