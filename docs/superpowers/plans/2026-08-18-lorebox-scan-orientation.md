# Lorebox Scan-Orientation Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-correct 90°/180°/270° scan-orientation errors on captured card images, using judgment already returned by the existing Claude vision `identify_card()` call — no new dependency, no new API request.

**Architecture:** `core/identifier.py`'s vision prompt gains two fields (`front_rotation`, `back_rotation`); `_identify_with_claude()` parses and clamps them into the returned dict, always present as an int defaulting to `0`. A new `utils/image_ops.rotate_by(img, degrees)` dispatches to the three rotate functions already in that file. Three call sites — the only places a *new* capture enters the app — apply the correction immediately after identification, before grading, thumbnailing, or saving.

**Tech Stack:** Python 3.11+, PyQt6, OpenCV, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-18-lorebox-scan-orientation-design.md`

**Branch:** `fix/batch-scan-quality` (already checked out; carries the natural-sort fix and this spec, committed)

## Global Constraints

- **No new dependencies.** Reuses the Anthropic API call `identify_card()` already makes.
- **`front_rotation` / `back_rotation` are always ints in `{0, 90, 180, 270}`, always present** in `_identify_with_claude()`'s returned dict, defaulting to `0` on anything missing, non-numeric, or out of range. Callers never need `None`-guarding.
- **Correction is applied automatically, with no confirmation step** — matches `deskew()`'s existing silent-auto-correct behavior. The manual rotate buttons remain the escape hatch.
- **Exactly three wiring call sites**, all "new capture" flows:
  - `ui/scan_tab.py` — `ScanTab._auto_identify()` (via a new `_apply_rotation()` method)
  - `ui/batch_review_dialog.py` — `BatchProcessWorker._process()`
  - `ui/batch_tab.py` — `ImageBatchWorker.run()` (also covers watch-folder import, which instantiates this same class)
- **Do NOT touch `ui/collection_tab.py` or `ui/regrade_dialog.py`.** Both call `identify_card()` too, but to refresh metadata on an already-saved card — out of scope, per the spec.
- **No Tesseract/OSD code.** Ruled out empirically in the spec (works on text-rich fronts, hard-fails with "too few characters" on symmetric/sparse-text backs at every rotation).
- Correction is applied exactly once per image, immediately after identification. Every downstream step (grading, thumbnailing, saving, display) operates on the corrected image — never a parallel corrected/uncorrected copy.

---

### Task 1: `rotate_by()` dispatcher

**Files:**
- Modify: `utils/image_ops.py`
- Test: `tests/test_image_ops.py`

**Interfaces:**
- Produces, relied on by Tasks 3–5: `rotate_by(img: np.ndarray, degrees: int) -> np.ndarray` — dispatches `90 -> rotate_90_cw`, `180 -> rotate_180`, `270 -> rotate_90_ccw`; any other value (including `0`) returns `img` unchanged.

- [ ] **Step 1: Confirm the baseline suite is green**

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `145 passed`. If this is not green, stop and report — do not build on a red suite.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_image_ops.py`, inside the existing `ImageOpsTests` class (after `test_deskew_handles_empty`, before the `if __name__ == "__main__":` line):

```python
    def test_rotate_by_zero_is_identity(self):
        img = _card()
        result = rotate_by(img, 0)
        np.testing.assert_array_equal(result, img)

    def test_rotate_by_invalid_value_is_identity(self):
        img = _card()
        result = rotate_by(img, 45)
        np.testing.assert_array_equal(result, img)

    def test_rotate_by_90_matches_rotate_90_cw(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 90), rotate_90_cw(img))

    def test_rotate_by_180_matches_rotate_180(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 180), rotate_180(img))

    def test_rotate_by_270_matches_rotate_90_ccw(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 270), rotate_90_ccw(img))

    def test_rotate_by_moves_content_not_just_shape(self):
        """Shape alone would pass even if 90 and 270 were swapped internally.

        Verified empirically which corner a top-left marker lands in:
          90 CW  -> top-right
          180    -> bottom-right
          270 (90 CCW) -> bottom-left
        """
        marker = np.full((40, 20, 3), 255, np.uint8)
        marker[0:5, 0:5] = (10, 20, 30)

        r90 = rotate_by(marker, 90)
        self.assertTrue(np.array_equal(r90[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8)))

        r180 = rotate_by(marker, 180)
        self.assertTrue(np.array_equal(r180[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8)))

        r270 = rotate_by(marker, 270)
        self.assertTrue(np.array_equal(r270[-5:, 0:5], np.full((5, 5, 3), (10, 20, 30), np.uint8)))
```

Update the import line at the top of the file (currently line 7):

```python
from utils.image_ops import deskew, rotate_90_cw, rotate_90_ccw, rotate_180, rotate_by, _rotate_bound
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_image_ops.py -q
```

Expected: collection error — `ImportError: cannot import name 'rotate_by' from 'utils.image_ops'`.

- [ ] **Step 4: Implement `rotate_by()`**

In `utils/image_ops.py`, add immediately after `rotate_180` (currently ending at line 25, before the blank lines preceding `def deskew`):

```python
def rotate_by(img: np.ndarray, degrees: int) -> np.ndarray:
    """Rotate img by 0/90/180/270 degrees clockwise. Any other value is a no-op."""
    return {
        90:  rotate_90_cw,
        180: rotate_180,
        270: rotate_90_ccw,
    }.get(degrees, lambda x: x)(img)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_image_ops.py -q
```

Expected: `11 passed` (5 existing + 6 new).

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `151 passed` (145 + 6 new).

- [ ] **Step 6: Commit**

```bash
git add utils/image_ops.py tests/test_image_ops.py
git commit -m "feat(orientation): rotate_by() dispatcher over the existing rotate functions"
```

---

### Task 2: `identify_card()` returns rotation judgment

**Files:**
- Modify: `core/identifier.py`
- Test: `tests/test_identifier_rotation.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1 — independent.
- Produces, relied on by Tasks 3–5: `_identify_with_claude()`'s (and therefore `identify_card()`'s) returned dict always contains `'front_rotation': int` and `'back_rotation': int`, each in `{0, 90, 180, 270}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_identifier_rotation.py`, following the exact `_FakeClient`/`_FakeResp` pattern already used in `tests/test_identifier_condition.py`:

```python
import numpy as np
from types import SimpleNamespace
from core.identifier import CardIdentifier


class _FakeResp:
    def __init__(self, text):
        self.content = [SimpleNamespace(text=text)]


class _FakeClient:
    def __init__(self, text):
        self._text = text
        self.messages = SimpleNamespace(create=lambda **kw: _FakeResp(self._text))


def _img():
    return np.full((20, 20, 3), 200, dtype=np.uint8)


def test_valid_rotation_values_are_parsed():
    text = ('{"name":"Elvish Farmer","game":"Magic: The Gathering",'
            '"front_rotation":90,"back_rotation":180}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), _img(), client=_FakeClient(text))
    assert out["front_rotation"] == 90
    assert out["back_rotation"] == 180


def test_missing_rotation_fields_default_to_zero():
    text = '{"name":"X","game":"Other"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_out_of_range_rotation_clamps_to_zero():
    text = ('{"name":"X","game":"Other","front_rotation":45,"back_rotation":-90}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_non_numeric_rotation_does_not_crash():
    text = '{"name":"X","game":"Other","front_rotation":"upright","back_rotation":null}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_rotation_present_alongside_condition_fields():
    """Regression: rotation parsing must not disturb the existing condition path."""
    text = ('{"name":"X","game":"Other","condition_score":80,"defects":[],'
            '"front_rotation":180,"back_rotation":0}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] == {"score": 80, "defects": []}
    assert out["front_rotation"] == 180
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_identifier_rotation.py -q
```

Expected: all 5 fail with `KeyError: 'front_rotation'`.

- [ ] **Step 3: Extend the vision prompt**

In `core/identifier.py`, find the end of `VISION_PROMPT` (currently lines 65–79):

```python
Also grade the card's physical condition from the image(s):
- condition_score: an integer 0-100 using this scale:
    95-100 Gem Mint (pristine); 88-94 Mint; 76-87 Near Mint (light wear);
    64-75 Excellent; 52-63 Very Good; 40-51 Good; 25-39 Played;
    0-24 Poor. IMPORTANT: if any material is missing — a torn or chipped
    corner/edge, or exposed cardboard — the card is AT MOST Good (<=51), and
    large tears/missing chunks are Poor. Heavy creasing or staining is
    Excellent or lower.
- defects: a list (possibly empty) of {"type","location","severity"} where
    type is one of "missing_material","corner_damage","edge_wear",
    "surface_crease","surface_scratch","staining","print_defect",
    "off_centering"; location is one of "top_left","top_right","bottom_left",
    "bottom_right","top","bottom","left","right","center"; severity is
    "minor","moderate", or "severe".
Include condition_score and defects as additional fields in the SAME JSON object."""
```

Replace the final line (`Include condition_score and defects...`) with:

```python
Include condition_score and defects as additional fields in the SAME JSON object.

Also determine image orientation:
- front_rotation: degrees to rotate the FRONT image CLOCKWISE so it reads
    upright — one of 0, 90, 180, 270. Use 0 if it is already upright or you
    are not confident.
- back_rotation: same, for the back image. Use 0 if no back image was given.
    Many card-game backs (e.g. Magic's Deckmaster design) have little or no
    body text — use whatever text or wordmark is present and its reading
    direction; if there is truly no orientation cue, use 0 rather than guess.
Include front_rotation and back_rotation as additional fields in the SAME
JSON object."""
```

- [ ] **Step 4: Parse and clamp the new fields**

In `core/identifier.py`, add this function immediately before `class CardIdentifier:` (currently line 82):

```python
def _clamp_rotation(value) -> int:
    """Clamp a rotation value to {0, 90, 180, 270}; anything else is 0."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return 0
    return v if v in (0, 90, 180, 270) else 0
```

Then find the return statement inside `_identify_with_claude` (currently lines 244–252):

```python
            return {
                'name': data.get('name') or None,
                'set_name': set_name,
                'card_number': str(data['card_number']) if data.get('card_number') else None,
                'rarity': data.get('rarity') or None,
                'year': int(data['year']) if data.get('year') else None,
                'game': data.get('game') or None,
                'condition': condition,
            }
```

Replace it with:

```python
            return {
                'name': data.get('name') or None,
                'set_name': set_name,
                'card_number': str(data['card_number']) if data.get('card_number') else None,
                'rarity': data.get('rarity') or None,
                'year': int(data['year']) if data.get('year') else None,
                'game': data.get('game') or None,
                'condition': condition,
                'front_rotation': _clamp_rotation(data.get('front_rotation')),
                'back_rotation': _clamp_rotation(data.get('back_rotation')),
            }
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_identifier_rotation.py tests/test_identifier_condition.py tests/test_identifier_routing.py -q
```

Expected: `13 passed` (5 new + 3 existing condition + 5 existing routing — confirms the new fields don't disturb either existing path).

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `156 passed` (151 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add core/identifier.py tests/test_identifier_rotation.py
git commit -m "feat(orientation): identify_card returns front/back rotation judgment"
```

---

### Task 3: Wire into the Scan tab

**Files:**
- Modify: `ui/scan_tab.py`
- Test: `tests/test_scan_tab_rotation.py` (new)

**Interfaces:**
- Consumes from Task 1: `rotate_by(img, degrees)`.
- Consumes from Task 2: `info['front_rotation']` / `info['back_rotation']`, always present ints.
- Produces: new method `ScanTab._apply_rotation(self, info: dict) -> None`. Not consumed by later tasks (each of Tasks 3–5 wires its own call site independently) but must exist with this exact name for the test in this task.

This task extracts the rotation-application logic into its own method rather than inlining it in `_auto_identify()`. `_apply_rotation` touches only `current_front_img` / `current_back_img` / `front_view` / `back_view` — none of the many other widgets `_auto_identify` touches (name/set/number/rarity fields, year spinner, game combo) — so it can be tested with a lightweight fake object instead of constructing a real `ScanTab` (which needs a database, scanner, inspector, valuator, and a fully built widget tree).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scan_tab_rotation.py`:

```python
import numpy as np

from ui.scan_tab import ScanTab


class _FakeView:
    """Stands in for ImageViewer — records what it was shown."""

    def __init__(self):
        self.images = []

    def set_image(self, img):
        self.images.append(img)


class _FakeScanTab:
    """Borrows the real method under test; supplies only what it touches."""

    _apply_rotation = ScanTab._apply_rotation

    def __init__(self, front, back):
        self.current_front_img = front
        self.current_back_img = back
        self.front_view = _FakeView()
        self.back_view = _FakeView()


def _marked(h=40, w=20):
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)   # marker in the top-left corner
    return img


def test_no_rotation_leaves_images_untouched():
    front, back = _marked(), _marked()
    tab = _FakeScanTab(front, back)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 0})
    assert tab.current_front_img is front
    assert tab.current_back_img is back
    assert tab.front_view.images == []
    assert tab.back_view.images == []


def test_missing_rotation_keys_default_to_no_op():
    """Trial-blocked and OCR-fallback info dicts carry no rotation keys at all."""
    front, back = _marked(), _marked()
    tab = _FakeScanTab(front, back)
    tab._apply_rotation({'name': None})
    assert tab.current_front_img is front
    assert tab.current_back_img is back


def test_front_rotation_applied_and_view_refreshed():
    front = _marked()
    tab = _FakeScanTab(front, None)
    tab._apply_rotation({'front_rotation': 90, 'back_rotation': 0})
    assert tab.current_front_img is not front
    assert np.array_equal(tab.current_front_img[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))
    assert tab.front_view.images == [tab.current_front_img]


def test_back_rotation_applied_independently_of_front():
    back = _marked()
    tab = _FakeScanTab(_marked(), back)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 180})
    assert tab.current_back_img is not back
    assert np.array_equal(tab.current_back_img[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))
    assert tab.back_view.images == [tab.current_back_img]


def test_back_rotation_skipped_when_no_back_image():
    tab = _FakeScanTab(_marked(), None)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 180})
    assert tab.current_back_img is None
    assert tab.back_view.images == []
```

This test needs no `QApplication` — it never constructs a real `ScanTab`, only references `ScanTab._apply_rotation` as an unbound function and calls it against `_FakeScanTab`, which touches no Qt widgets. If Step 2 below fails with something Qt-related rather than the expected `AttributeError`, that is a different problem than the one this task is testing for — stop and report rather than working around it.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_scan_tab_rotation.py -q
```

Expected: all 5 fail with `AttributeError: type object 'ScanTab' has no attribute '_apply_rotation'`.

- [ ] **Step 3: Add `_apply_rotation()` and call it from `_auto_identify()`**

In `ui/scan_tab.py`, find the trial-block early-return inside `_auto_identify` (currently lines 515–520):

```python
            if source.startswith('trial_'):
                self.status_label.setText(
                    "Free trial used — add your own key to keep auto-identifying."
                )
                self.key_setup_requested.emit(source)
                return

            if info.get('name') and not self.name_edit.text().strip():
```

Insert a call to the new method between the early-return and the field-population block:

```python
            if source.startswith('trial_'):
                self.status_label.setText(
                    "Free trial used — add your own key to keep auto-identifying."
                )
                self.key_setup_requested.emit(source)
                return

            self._apply_rotation(info)

            if info.get('name') and not self.name_edit.text().strip():
```

Then add the new method immediately before `_auto_identify` (currently line 504, right after `_scan_error` ends at line 502):

```python
    def _apply_rotation(self, info: dict):
        """Auto-correct front/back orientation using identify_card's judgment.

        Safe against any info dict: a missing key defaults to 0 (no-op), the
        same convention core.identifier uses whenever it is unsure.
        """
        from utils.image_ops import rotate_by

        front_deg = info.get('front_rotation', 0)
        if front_deg and self.current_front_img is not None:
            self.current_front_img = rotate_by(self.current_front_img, front_deg)
            self.front_view.set_image(self.current_front_img)

        back_deg = info.get('back_rotation', 0)
        if back_deg and self.current_back_img is not None:
            self.current_back_img = rotate_by(self.current_back_img, back_deg)
            self.back_view.set_image(self.current_back_img)

    def _auto_identify(self):
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_scan_tab_rotation.py -q
```

Expected: `5 passed`.

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `161 passed` (156 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add ui/scan_tab.py tests/test_scan_tab_rotation.py
git commit -m "feat(orientation): auto-correct Scan tab front/back rotation"
```

---

### Task 4: Wire into the multi-card scan review

**Files:**
- Modify: `ui/batch_review_dialog.py`
- Test: `tests/test_batch_review_rotation.py` (new)

**Interfaces:**
- Consumes from Task 1: `rotate_by(img, degrees)`.
- Consumes from Task 2: `info['front_rotation']` / `info['back_rotation']`.
- Produces: nothing consumed by later tasks.

`BatchProcessWorker._process()` runs on any of up to 4 concurrent `ThreadPoolExecutor` worker threads (see `BatchProcessWorker.run()`, which submits one `_process` call per chunk). `front` / `back` are local variables inside `_process`, so there is no shared-state concern — but `front`/`back` start as aliases into the `chunk` list (`front = chunk[0]`), and reassigning a local variable does not mutate the list it came from. `chunk` is rebuilt explicitly from the (possibly rotated) `front`/`back` rather than relying on that aliasing, so the dict this method returns (`'images': chunk`) reflects the correction.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch_review_rotation.py`:

```python
import numpy as np

from ui.batch_review_dialog import BatchProcessWorker
from core.inspector import CardInspector


class _FakeIdentifier:
    def __init__(self, front_rotation=0, back_rotation=0):
        self._front_rotation = front_rotation
        self._back_rotation = back_rotation

    def identify_card(self, front, back):
        return {'name': 'Test Card', 'set_name': None, 'card_number': None,
                'game': 'Magic: The Gathering', 'year': None, 'rarity': None,
                'condition': {'score': 85, 'defects': []},
                'front_rotation': self._front_rotation,
                'back_rotation': self._back_rotation}


class _FakeValuator:
    """A real CardValuator would make a live Scryfall/eBay network call here —
    this test is about rotation wiring, not valuation, so stub it out."""

    def value_summary(self, *args, **kwargs):
        return {'estimated': 0.0, 'source': '', 'sample': 0}


def _marked(h=40, w=20):
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)
    return img


def _worker(front_rotation=0, back_rotation=0):
    return BatchProcessWorker(
        chunks=[], identifier=_FakeIdentifier(front_rotation, back_rotation),
        inspector=CardInspector(), valuator=_FakeValuator(),
    )


def test_front_rotation_reflected_in_returned_images():
    front = _marked()
    result = _worker(front_rotation=90)._process(0, [front])
    corrected = result['images'][0]
    assert not np.array_equal(corrected, front)
    assert np.array_equal(corrected[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))


def test_back_rotation_reflected_independently():
    front, back = _marked(), _marked()
    result = _worker(back_rotation=180)._process(0, [front, back])
    corrected_front, corrected_back = result['images']
    assert np.array_equal(corrected_front, front)   # front_rotation=0, untouched
    assert np.array_equal(corrected_back[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))


def test_no_rotation_is_a_no_op():
    front = _marked()
    result = _worker()._process(0, [front])
    assert np.array_equal(result['images'][0], front)
```

`CardInspector()` is constructed for real (it's cheap — no model loading, no I/O) but never exercised: `_process` calls `resolve_condition(info, front, self.inspector)`, and `core/grading.py: resolve_condition` prefers `info['condition']` when present (which the fake identifier always supplies) over calling `inspector.inspect()`. `CardValuator` is NOT constructed for real — `_process` unconditionally calls `self.valuator.value_summary(...)`, and a real `CardValuator` would make a genuine HTTP request to Scryfall for a `"Magic: The Gathering"` game value, which a unit test must not do.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_batch_review_rotation.py -q
```

Expected: all 3 fail — `test_front_rotation_reflected_in_returned_images` and `test_back_rotation_reflected_independently` fail on the `assert not np.array_equal(...)` / marker assertions (no rotation applied yet); `test_no_rotation_is_a_no_op` passes trivially already (it is here as a regression guard for later, not currently a failing case — that is fine, it is not required that every test in a task fail at this step, only that at least one does and that none pass for the wrong reason).

- [ ] **Step 3: Wire the correction into `_process()`**

In `ui/batch_review_dialog.py`, find `_process` (currently lines 85–93):

```python
    def _process(self, idx: int, chunk: List[np.ndarray]) -> dict:
        from utils.image_ops import deskew

        # Auto-straighten before identification/grading — improves both
        chunk = [deskew(im) for im in chunk]
        front = chunk[0]
        back  = chunk[1] if len(chunk) > 1 else None

        info       = self.identifier.identify_card(front, back)
```

Replace it with:

```python
    def _process(self, idx: int, chunk: List[np.ndarray]) -> dict:
        from utils.image_ops import deskew, rotate_by

        # Auto-straighten before identification/grading — improves both
        chunk = [deskew(im) for im in chunk]
        front = chunk[0]
        back  = chunk[1] if len(chunk) > 1 else None

        info = self.identifier.identify_card(front, back)

        # Auto-correct orientation using identify_card's judgment. Rebuild
        # chunk explicitly from the (possibly rotated) front/back rather than
        # relying on them staying aliases into it — reassigning a local does
        # not mutate the list it came from.
        front = rotate_by(front, info.get('front_rotation', 0))
        if back is not None:
            back = rotate_by(back, info.get('back_rotation', 0))
        chunk = [front] if back is None else [front, back]
```

The line immediately after this block is already `from core.grading import resolve_condition` — leave it and everything below unchanged; `resolve_condition(info, front, self.inspector)` now receives the corrected `front`.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_batch_review_rotation.py -q
```

Expected: `3 passed`.

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `164 passed` (161 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add ui/batch_review_dialog.py tests/test_batch_review_rotation.py
git commit -m "feat(orientation): auto-correct multi-card scan review rotation"
```

---

### Task 5: Wire into folder Batch Import / watch-folder, plus the end-to-end regression

**Files:**
- Modify: `ui/batch_tab.py`
- Test: `tests/test_batch_tab_rotation.py` (new)

**Interfaces:**
- Consumes from Task 1: `rotate_by(img, degrees)`.
- Consumes from Task 2: `info['front_rotation']` / `info['back_rotation']`.
- Produces: nothing consumed by later tasks — this is the last task.

`ImageBatchWorker.run()` covers two entry points from one change: folder Batch Import, and watch-folder auto-import (`core/watcher.py` + `ui/main_window.py: _run_watch_import` both instantiate this same `ImageBatchWorker` class). Unlike Task 4, `front`/`back` here are plain local variables, not sliced from a list — a direct reassignment is sufficient, no rebuild needed.

This task also carries the plan's one end-to-end regression: proof that a rotation judgment reaches the **saved PNG bytes on disk**, not just an in-memory array — the same kind of proof `test_reproduces_and_fixes_the_243_file_scramble` gave for the natural-sort fix.

- [ ] **Step 1: Write the failing test**

Create `tests/test_batch_tab_rotation.py`:

```python
import cv2
import numpy as np

import ui.batch_tab as batch_tab_module
from ui.batch_tab import ImageBatchWorker
from core.database import Database
from core.inspector import CardInspector
from core.scanner import ScannerInterface


class _FakeIdentifier:
    def identify_card(self, front, back):
        return {'name': 'Test Card', 'set_name': None, 'card_number': None,
                'game': 'Other', 'year': None, 'rarity': None,
                'condition': {'score': 85, 'defects': []},
                'front_rotation': 180, 'back_rotation': 0}


class _FakeValuator:
    def value_summary(self, *args, **kwargs):
        return {'estimated': 0.0, 'source': '', 'sample': 0}


def _marked_png(path, h=40, w=20):
    """Write a PNG with a distinct marker in the top-left corner; return the
    in-memory RGB array so the test can assert against the ORIGINAL, not just
    re-derive it from the file it's checking."""
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return img


def test_saved_file_reflects_front_rotation(tmp_path, monkeypatch):
    """The whole point of this feature: does the correction reach disk?

    front_rotation=180 on a marker whose original position is top-left must
    produce a saved file with the marker at bottom-right — proof this isn't
    just an in-memory transform that gets discarded before cv2.imwrite.
    """
    scans_dir = tmp_path / "scans"
    scans_dir.mkdir()
    monkeypatch.setattr(batch_tab_module, "SCANS_DIR", scans_dir)

    folder = tmp_path / "import"
    folder.mkdir()
    original = _marked_png(folder / "card_1.png")

    worker = ImageBatchWorker(
        folder=folder, db=Database(tmp_path / "t.db"), scanner=ScannerInterface(),
        inspector=CardInspector(), identifier=_FakeIdentifier(),
        valuator=_FakeValuator(), auto_value=False, pairing=ImageBatchWorker.SINGLE,
    )
    worker.run()

    saved = list(scans_dir.glob("*_front.png"))
    assert len(saved) == 1, f"expected exactly one saved front image, found {saved}"
    saved_img = cv2.cvtColor(cv2.imread(str(saved[0])), cv2.COLOR_BGR2RGB)

    assert not np.array_equal(saved_img, original)
    assert np.array_equal(saved_img[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))
```

`monkeypatch.setattr(batch_tab_module, "SCANS_DIR", scans_dir)` redirects the save location without touching the real `%APPDATA%/Lorebox` — the same pattern `tests/test_review_prompt.py` already uses for `PREFS_FILE`. The 5×5 marker is well under `deskew()`'s `len(coords) >= 50` threshold (`utils/image_ops.py`), so `_load()`'s automatic deskew pass leaves it untouched before rotation is even considered — the marker survives to prove specifically the *rotation* wiring, not deskew interacting with it.

**`scans_dir.mkdir()` is required, not optional — this is a test-isolation gap, not a production bug.** `ui/batch_tab.py:29-31` ensures the real `SCANS_DIR` exists once, at module-import time, against the real path — long before this test's `monkeypatch.setattr` ever runs. The monkeypatch substitutes a *different* path afterward, which the import-time `mkdir()` never touched and which does not otherwise exist under `tmp_path`. `cv2.imwrite()` fails silently on a missing directory — it returns `False` and raises nothing (verified: `cv2.imwrite('nonexistent/out.png', img)` returns `False`, writes no file) — so without this line the test would fail at `assert len(saved) == 1` (`found 0`), not at the rotation assertion it exists to check. Real app behavior is unaffected either way: `SCANS_DIR` never changes after import in production, so the one-time `mkdir()` at `ui/batch_tab.py:31` is always sufficient there.

**One residual uncertainty, flagged rather than assumed away:** `ImageBatchWorker` is a `QThread` subclass, and this test calls `worker.run()` directly (the method body, synchronously — not `.start()`, which would need a live thread and event loop). No test in this codebase currently constructs `ImageBatchWorker` this way. It is expected to work — `QThread` is not a widget and constructing one, or calling a plain method on one, does not typically require a running `QApplication` — but if Step 2 fails with a Qt-runtime error instead of the expected assertion failure, that is a different problem than the one this task is testing for. Stop and report rather than working around it with, for instance, a `QApplication` fixture that the rest of this test's design didn't anticipate needing.

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/Scripts/python -m pytest tests/test_batch_tab_rotation.py -q
```

Expected: fails on `assert not np.array_equal(saved_img, original)` — the saved file is currently identical to the input, since nothing rotates it yet.

- [ ] **Step 3: Wire the correction into `run()`**

In `ui/batch_tab.py`, find this block inside `run()` (currently lines 216–220):

```python
                back = self._load(back_desc)

                info = self.identifier.identify_card(front, back)
                from core.grading import resolve_condition
                inspection = resolve_condition(info, front, self.inspector)
```

Replace it with:

```python
                back = self._load(back_desc)

                info = self.identifier.identify_card(front, back)

                from utils.image_ops import rotate_by
                front = rotate_by(front, info.get('front_rotation', 0))
                if back is not None:
                    back = rotate_by(back, info.get('back_rotation', 0))

                from core.grading import resolve_condition
                inspection = resolve_condition(info, front, self.inspector)
```

Everything below this — grading, valuation, the `cv2.imwrite` calls for `front_scan`/`back_scan` — already references the local `front`/`back` variables and needs no further change; it now picks up the corrected images automatically.

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/Scripts/python -m pytest tests/test_batch_tab_rotation.py -q
```

Expected: `1 passed`.

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `165 passed` (164 + 1 new).

- [ ] **Step 5: Commit**

```bash
git add ui/batch_tab.py tests/test_batch_tab_rotation.py
git commit -m "feat(orientation): auto-correct batch/watch-folder import rotation"
```

---

## Final verification

- [ ] **Full suite green**

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: `165 passed` (145 baseline + 20 new across the five tasks), zero failures.

- [ ] **No stray Tesseract/OSD code was introduced**

```bash
git diff 16cdddd..HEAD -- '*.py' | grep -i "image_to_osd\|--psm 0"
```

Expected: no output. (The spec ruled out OSD; this plan never calls it — this check exists so a future reader doesn't have to re-derive that from the diff.)

- [ ] **`identify_card()`'s two re-identify call sites are untouched**

```bash
git diff 16cdddd..HEAD -- ui/collection_tab.py ui/regrade_dialog.py
```

Expected: no output — confirms the explicit out-of-scope boundary held.

- [ ] **Manual verification (human, not the implementer)**

The full loop — a real TWAIN duplex scan producing an actually-rotated card, auto-corrected before save — cannot be exercised headlessly; there is no physical scanner in this environment. Automated coverage proves every stage of the pipeline (prompt parsing, dispatcher, three wiring sites, saved-file bytes) independently and end-to-end with a fake identifier standing in for Claude's real judgment. What remains unverified by this plan: whether Claude's actual vision judgment on a real rotated card — particularly a symmetric, sparse-text back — is accurate enough in practice to trust auto-apply. Recommend running a real scan session (including at least one deliberately-upside-down card) before relying on this for another large batch.
