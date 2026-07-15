# Claude-Vision Card Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grade card condition with Claude vision (which recognizes tears, chips, creases, scratches that the pixel-brightness CV grader cannot), keep the CV inspector as an offline fallback, fix the grade-bin gaps, and add a user-triggered "Re-grade collection" action.

**Architecture:** Fold condition into the existing identify vision call (no extra API call). A new `core/grading.py` owns the single grade-derivation function (contiguous bands) and a `resolve_condition` helper that prefers vision condition and falls back to `CardInspector`. Scan/batch/re-identify call that one helper.

**Tech Stack:** Python 3.11 / PyQt6 (existing); `anthropic==0.105.2`; pytest. Spec: `docs/superpowers/specs/2026-07-13-lorebox-vision-grading-design.md`.

## Global Constraints

- No new Python runtime dependency; reuse the pinned `anthropic==0.105.2`.
- Vision model stays `claude-haiku-4-5-20251001` (one merged call; grading rides the same call as identification).
- Grade is ALWAYS derived from the numeric score via one function (`grading.grade_for_score`) — grade and score can never contradict.
- Contiguous grade bands (fixes the bin-gap bug): `>=95` Gem Mint, `>=88` Mint, `>=76` Near Mint, `>=64` Excellent, `>=52` Very Good, `>=40` Good, `>=25` Played, else Poor.
- A trial credit is consumed only on a confirmed successful vision call (unchanged from the trial feature).
- DB schema unchanged; use existing `add_card` / `update_card` (they whitelist `condition_grade`, `condition_score`, `defects`).
- The vision prompt must instruct: missing material (torn/chipped/exposed cardboard) caps the grade at Good (≤51) or lower.

---

## File Structure

- Create: `core/grading.py` — `grade_for_score()`, `resolve_condition()`.
- Create: `tests/test_grading.py`.
- Modify: `core/inspector.py` — derive grade via `grade_for_score` (remove the gap-prone `GRADES` loop).
- Modify: `core/identifier.py` — extend `VISION_PROMPT` + parse `condition` into the result.
- Modify: `tests/test_identifier_routing.py` (or new `tests/test_identifier_condition.py`) — condition-parse tests.
- Modify: `ui/scan_tab.py`, `ui/batch_tab.py`, `ui/batch_review_dialog.py` — use `resolve_condition`.
- Modify: `ui/main_window.py` — add "Re-grade collection" menu action + handler.
- Create: `ui/regrade_dialog.py` — cost-confirm dialog + background re-grade worker.

---

## Task 1: `grade_for_score` — contiguous bands (bin-gap fix)

**Files:**
- Create: `core/grading.py`
- Test: `tests/test_grading.py`

**Interfaces:**
- Produces: `grade_for_score(score: float) -> str`. Clamps to [0,100]; returns one of the 8 grade names.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grading.py
import pytest
from core.grading import grade_for_score


@pytest.mark.parametrize("score,grade", [
    (100, "Gem Mint"), (96, "Gem Mint"), (95, "Gem Mint"),
    (94.9, "Mint"), (94.5, "Mint"), (88, "Mint"),
    (87.9, "Near Mint"), (78, "Near Mint"), (76, "Near Mint"),
    (75.4, "Excellent"), (64, "Excellent"),
    (63.9, "Very Good"), (52, "Very Good"),
    (51.9, "Good"), (40, "Good"),
    (39.9, "Played"), (25, "Played"),
    (24.9, "Poor"), (0, "Poor"),
])
def test_grade_for_score_boundaries(score, grade):
    assert grade_for_score(score) == grade


def test_grade_for_score_clamps_out_of_range():
    assert grade_for_score(150) == "Gem Mint"
    assert grade_for_score(-5) == "Poor"


def test_no_score_in_0_100_returns_poor_default_gap():
    # The exact bug-B cases must NOT return "Poor".
    assert grade_for_score(94.5) != "Poor"
    assert grade_for_score(75.4) != "Poor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_grading.py -v`
Expected: FAIL — `No module named 'core.grading'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/grading.py
"""Condition grading helpers: one source of truth for score->grade, and a
resolver that prefers Claude-vision condition over the CV inspector."""

# Contiguous bands — every score in [0,100] maps to exactly one grade (no gaps).
# (lower_inclusive, grade), checked high to low.
_BANDS = [
    (95, "Gem Mint"),
    (88, "Mint"),
    (76, "Near Mint"),
    (64, "Excellent"),
    (52, "Very Good"),
    (40, "Good"),
    (25, "Played"),
    (0,  "Poor"),
]


def grade_for_score(score: float) -> str:
    """Map a 0-100 condition score to a grade label. Clamps out-of-range input."""
    s = max(0.0, min(100.0, float(score)))
    for lower, grade in _BANDS:
        if s >= lower:
            return grade
    return "Poor"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_grading.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/grading.py tests/test_grading.py
git commit -m "feat(grading): grade_for_score with contiguous bands (fixes bin-gap)"
```

---

## Task 2: CardInspector derives grade via `grade_for_score`

**Files:**
- Modify: `core/inspector.py` (the grade-selection loop in `inspect`, around lines 360-364)
- Test: `tests/test_grading.py` (add a regression case)

**Interfaces:**
- Consumes: `core.grading.grade_for_score`.
- Produces: `CardInspector.inspect()` returns the same dict shape, but `grade` now comes from `grade_for_score(score)` — so a fractional score like 94.5 no longer defaults to "Poor".

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_grading.py
def test_inspector_uses_shared_grade_mapping(monkeypatch):
    import numpy as np
    from core.inspector import CardInspector
    insp = CardInspector()
    # Force a known score by stubbing the detectors to yield no defects and a
    # centering score that lands the total at 94.5 (previously the "Poor" gap).
    monkeypatch.setattr(insp, "_detect_card_region", lambda img: img)
    monkeypatch.setattr(insp, "_detect_corner_damage", lambda img: [])
    monkeypatch.setattr(insp, "_detect_edge_wear", lambda img: [])
    monkeypatch.setattr(insp, "_detect_surface_defects", lambda img: [])
    monkeypatch.setattr(insp, "_detect_centering", lambda img: ([], 45.0))  # -> 100 - 5.5 = 94.5
    out = insp.inspect(np.zeros((100, 100, 3), dtype=np.uint8))
    assert out["score"] == 94.5
    assert out["grade"] == "Mint"   # NOT "Poor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_grading.py::test_inspector_uses_shared_grade_mapping -v`
Expected: FAIL — current code returns grade "Poor" for score 94.5.

- [ ] **Step 3: Edit `core/inspector.py`**

Add the import near the top (after the existing imports, around line 13):

```python
from core.grading import grade_for_score
```

Replace the grade-selection block in `inspect` (currently):

```python
        grade = 'Poor'
        for g, (lo, hi) in self.GRADES.items():
            if lo <= score <= hi:
                grade = g
                break
```

with:

```python
        grade = grade_for_score(score)
```

Leave the `GRADES` dict in place (it documents the human-facing ranges and may be referenced elsewhere), but it is no longer used for lookup.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_grading.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/inspector.py tests/test_grading.py
git commit -m "refactor(inspector): derive grade via shared grade_for_score"
```

---

## Task 3: Vision prompt returns condition

**Files:**
- Modify: `core/identifier.py` (`VISION_PROMPT` string; the parse/return in `_identify_with_claude`, lines ~199-216; bump `max_tokens`)
- Test: `tests/test_identifier_condition.py`

**Interfaces:**
- Produces: `_identify_with_claude` (and therefore `identify_card`) result dict gains a `'condition'` key: `{'score': int(0-100), 'defects': list}` when vision returned a valid `condition_score`, else `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identifier_condition.py
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


def test_condition_parsed_from_vision_json():
    text = ('{"name":"Bert Blyleven","set_name":"Fleer","card_number":"3",'
            '"rarity":"Award Winner","year":1987,"game":"Baseball",'
            '"condition_score":35,"defects":[{"type":"missing_material",'
            '"location":"top_right","severity":"severe"}]}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["name"] == "Bert Blyleven"
    assert out["condition"] == {"score": 35,
                                "defects": [{"type": "missing_material",
                                             "location": "top_right",
                                             "severity": "severe"}]}


def test_missing_condition_score_yields_none_condition():
    text = '{"name":"X","set_name":null,"card_number":null,"rarity":null,"year":null,"game":"Other"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] is None


def test_malformed_defects_do_not_crash():
    text = '{"name":"X","game":"Other","condition_score":80,"defects":"oops"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] == {"score": 80, "defects": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_identifier_condition.py -v`
Expected: FAIL — result has no `condition` key.

- [ ] **Step 3: Edit `VISION_PROMPT`**

Append this block to the end of the `VISION_PROMPT` string in `core/identifier.py` (before the closing `"""`), after the existing example line:

```
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
Include condition_score and defects as additional fields in the SAME JSON object.
```

- [ ] **Step 4: Bump `max_tokens` and parse the condition**

In `_identify_with_claude`, change `max_tokens=256` to `max_tokens=512` (room for the defects list).

Replace the `return { ... }` block (lines ~209-216) with:

```python
            condition = None
            cs = data.get('condition_score')
            if isinstance(cs, bool):
                cs = None
            if isinstance(cs, (int, float)) or (isinstance(cs, str) and cs.strip().lstrip('-').isdigit()):
                score = max(0, min(100, int(float(cs))))
                defects = data.get('defects')
                if not isinstance(defects, list):
                    defects = []
                condition = {'score': score, 'defects': defects}

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

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_identifier_condition.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (existing identifier tests still green; they don't assert on `condition`).

- [ ] **Step 7: Commit**

```bash
git add core/identifier.py tests/test_identifier_condition.py
git commit -m "feat(identifier): vision call also returns condition_score + defects"
```

---

## Task 4: `resolve_condition` (vision-or-CV)

**Files:**
- Modify: `core/grading.py` (add `resolve_condition`)
- Test: `tests/test_grading.py`

**Interfaces:**
- Consumes: `grade_for_score`; a `CardInspector`-like object with `.inspect(img) -> {'score','defects',...}`.
- Produces: `resolve_condition(info: dict, front_img, inspector) -> {'grade','score','defects','source'}` where `source` is `'vision'` (used the identify result's condition) or `'cv'` (fell back to the inspector). `grade` is always `grade_for_score(score)`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_grading.py
class _FakeInspector:
    def __init__(self, score, defects): self._s, self._d = score, defects
    def inspect(self, img):
        return {'grade': 'ignored', 'score': self._s, 'defects': self._d, 'centering_score': 0.0}


def test_resolve_condition_prefers_vision():
    from core.grading import resolve_condition
    info = {'name': 'x', 'condition': {'score': 35,
            'defects': [{'type': 'missing_material', 'location': 'top_right', 'severity': 'severe'}]}}
    out = resolve_condition(info, front_img=None, inspector=_FakeInspector(99, []))
    assert out['source'] == 'vision'
    assert out['score'] == 35.0
    assert out['grade'] == 'Played'          # grade_for_score(35)
    assert out['defects'][0]['type'] == 'missing_material'


def test_resolve_condition_falls_back_to_cv():
    from core.grading import resolve_condition
    info = {'name': 'x', 'condition': None}   # no vision condition
    out = resolve_condition(info, front_img=object(), inspector=_FakeInspector(94.5, []))
    assert out['source'] == 'cv'
    assert out['score'] == 94.5
    assert out['grade'] == 'Mint'            # shared mapping, not "Poor"


def test_resolve_condition_handles_missing_info():
    from core.grading import resolve_condition
    out = resolve_condition(None, front_img=object(), inspector=_FakeInspector(80, []))
    assert out['source'] == 'cv' and out['grade'] == 'Near Mint'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_grading.py -k resolve_condition -v`
Expected: FAIL — `resolve_condition` not defined.

- [ ] **Step 3: Add `resolve_condition` to `core/grading.py`**

```python
def resolve_condition(info, front_img, inspector) -> dict:
    """Return {'grade','score','defects','source'} for a card.

    Prefers the Claude-vision condition carried in `info['condition']`; falls
    back to the CV inspector when vision produced no condition. Grade is always
    derived from the score so the two never disagree.
    """
    cond = (info or {}).get('condition') if isinstance(info, dict) else None
    if cond and isinstance(cond.get('score'), (int, float)):
        score = float(cond['score'])
        defects = cond.get('defects') if isinstance(cond.get('defects'), list) else []
        return {'grade': grade_for_score(score), 'score': score,
                'defects': defects, 'source': 'vision'}

    inspection = inspector.inspect(front_img)
    score = float(inspection.get('score', 0.0))
    return {'grade': grade_for_score(score), 'score': score,
            'defects': inspection.get('defects', []), 'source': 'cv'}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_grading.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/grading.py tests/test_grading.py
git commit -m "feat(grading): resolve_condition prefers vision, falls back to CV"
```

---

## Task 5: Use `resolve_condition` in scan / batch / batch-review

**Files:**
- Modify: `ui/scan_tab.py` (`_auto_identify` store the result; `_inspect` use `resolve_condition`)
- Modify: `ui/batch_tab.py` (line ~211-212)
- Modify: `ui/batch_review_dialog.py` (line ~98-99)

**Interfaces:**
- Consumes: `core.grading.resolve_condition`; `identify_card`'s `info` (with `condition`).

- [ ] **Step 1: `ui/scan_tab.py` — store the identify result**

In `_auto_identify` (around line 461), immediately after `info = self.identifier.identify_card(...)`, add:

```python
            self._last_identify = info
```

And in `ScanTab.__init__` (near other instance attrs), initialize it:

```python
        self._last_identify = None
```

- [ ] **Step 2: `ui/scan_tab.py` — `_inspect` uses resolve_condition**

Replace the body assignment in `_inspect` (line ~497):

```python
            self.current_inspection = self.inspector.inspect(self.current_front_img)
```

with:

```python
            from core.grading import resolve_condition
            self.current_inspection = resolve_condition(
                getattr(self, '_last_identify', None), self.current_front_img, self.inspector)
```

`current_inspection` still has `grade`/`score`/`defects` keys, so the rest of `_inspect` is unchanged.

- [ ] **Step 3: `ui/batch_tab.py` — swap inspect**

Replace (line ~212):

```python
                inspection = self.inspector.inspect(front)
```

with:

```python
                from core.grading import resolve_condition
                inspection = resolve_condition(info, front, self.inspector)
```

`inspection['grade'|'score'|'defects']` are consumed downstream (lines ~218, ~240-242) — unchanged.

- [ ] **Step 4: `ui/batch_review_dialog.py` — swap inspect**

At line ~98-99, the code calls `identify_card` then `inspector.inspect(front)`. Replace:

```python
        inspection = self.inspector.inspect(front)
```

with:

```python
        from core.grading import resolve_condition
        inspection = resolve_condition(info, front, self.inspector)
```

(`info` is the identify result already in scope at that point — confirm by reading the surrounding lines; if the variable has a different name, use it.)

- [ ] **Step 5: Import-smoke + full suite**

Run: `python -c "import ui.scan_tab, ui.batch_tab, ui.batch_review_dialog"`
Expected: exit 0.
Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/scan_tab.py ui/batch_tab.py ui/batch_review_dialog.py
git commit -m "feat(grading): use vision condition (CV fallback) in scan/batch flows"
```

---

## Task 6: "Re-grade collection" action

**Files:**
- Create: `ui/regrade_dialog.py` (cost-confirm dialog + background worker)
- Modify: `ui/main_window.py` (menu action + handler)

**Interfaces:**
- Consumes: `db.get_all_cards()`, `db.update_card(id, {...})`, `identifier.identify_card`, `core.grading.resolve_condition`, `core.inspector.CardInspector`.
- Produces: `class RegradeDialog(QDialog)` and `MainWindow._regrade_collection()`.

- [ ] **Step 1: Implement `ui/regrade_dialog.py`**

```python
# ui/regrade_dialog.py
"""Re-grade existing cards with the current grader (vision, CV fallback).

Shows a cost estimate + confirm, then re-runs grading on every card that has a
readable front scan, applying ONLY the condition fields (name/set untouched).
Stops and asks for a key if the free trial is exhausted mid-run.
"""
import os

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QMessageBox
)

from core.grading import resolve_condition

COST_PER_CARD = 0.006


class _RegradeWorker(QThread):
    progress = pyqtSignal(int, int)          # done, total
    trial_blocked = pyqtSignal(str)          # source marker
    finished_ok = pyqtSignal(int, int)       # regraded, skipped

    def __init__(self, db, identifier, inspector, card_ids):
        super().__init__()
        self.db, self.identifier, self.inspector = db, identifier, inspector
        self.card_ids = card_ids
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        regraded = skipped = 0
        total = len(self.card_ids)
        for i, cid in enumerate(self.card_ids):
            if self._cancel:
                break
            card = self.db.get_card(cid)
            fp = card.get('front_scan_path') if card else None
            if not fp or not os.path.exists(fp):
                skipped += 1
                self.progress.emit(i + 1, total)
                continue
            front = cv2.cvtColor(cv2.imread(fp), cv2.COLOR_BGR2RGB)
            back = None
            bp = card.get('back_scan_path')
            if bp and os.path.exists(bp):
                back = cv2.cvtColor(cv2.imread(bp), cv2.COLOR_BGR2RGB)
            info = self.identifier.identify_card(front, back)
            if str(info.get('source', '')).startswith('trial_'):
                self.trial_blocked.emit(info['source'])
                return
            cond = resolve_condition(info, front, self.inspector)
            self.db.update_card(cid, {
                'condition_grade': cond['grade'],
                'condition_score': cond['score'],
                'defects': cond['defects'],
            })
            regraded += 1
            self.progress.emit(i + 1, total)
        self.finished_ok.emit(regraded, skipped)


class RegradeDialog(QDialog):
    trial_blocked = pyqtSignal(str)          # bubble up to MainWindow to open key dialog

    def __init__(self, db, identifier, inspector, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Re-grade collection")
        self.setMinimumWidth(420)
        self._db, self._identifier, self._inspector = db, identifier, inspector
        self._worker = None

        cards = db.get_all_cards()
        self._ids = [c['id'] for c in cards if c.get('front_scan_path')]
        n = len(self._ids)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)
        v.addWidget(QLabel(
            f"<b>Re-grade {n} cards</b> with the current grader "
            f"(Claude vision, falling back to offline analysis).<br><br>"
            f"Vision grading costs about ${COST_PER_CARD:.3f}/card "
            f"(~${n * COST_PER_CARD:.2f} total, via your free trial or your own key). "
            f"Only condition is updated — names and sets are left alone."
        ))
        self._status = QLabel("")
        self._status.setWordWrap(True)
        v.addWidget(self._status)
        self._bar = QProgressBar()
        self._bar.setMaximum(max(1, n))
        self._bar.setVisible(False)
        v.addWidget(self._bar)

        row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        row.addWidget(self._cancel_btn)
        row.addStretch()
        self._start_btn = QPushButton("Re-grade")
        self._start_btn.setProperty("primary", True)
        self._start_btn.setDefault(True)
        self._start_btn.setEnabled(n > 0)
        self._start_btn.clicked.connect(self._start)
        row.addWidget(self._start_btn)
        v.addLayout(row)

    def _start(self):
        self._start_btn.setEnabled(False)
        self._bar.setVisible(True)
        self._status.setText("Re-grading…")
        self._worker = _RegradeWorker(self._db, self._identifier, self._inspector, self._ids)
        self._worker.progress.connect(lambda d, t: self._bar.setValue(d))
        self._worker.finished_ok.connect(self._done)
        self._worker.trial_blocked.connect(self._on_trial_blocked)
        self._worker.start()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        else:
            self.reject()

    def _done(self, regraded, skipped):
        self._status.setText(f"Done — {regraded} re-graded, {skipped} skipped (no scan on disk).")
        self._start_btn.setEnabled(False)
        self._cancel_btn.setText("Close")

    def _on_trial_blocked(self, source):
        self._status.setText("Free trial used up — add your own key to finish re-grading.")
        self._start_btn.setEnabled(True)
        self.trial_blocked.emit(source)
```

- [ ] **Step 2: Wire it into `ui/main_window.py`**

In `_setup_menu` (find where menu actions are created — search for `addAction`), add an action (e.g. under a Tools or the existing menu):

```python
        regrade_action = QAction("Re-grade Collection…", self)
        regrade_action.triggered.connect(self._regrade_collection)
        # add to an appropriate menu, e.g. tools_menu.addAction(regrade_action)
```

Add the handler near `_open_key_setup`:

```python
    def _regrade_collection(self):
        from ui.regrade_dialog import RegradeDialog
        dlg = RegradeDialog(self.db, self.identifier, self.inspector, self)
        dlg.trial_blocked.connect(self._open_key_setup)
        dlg.exec()
        # refresh views to show updated grades
        self.collection_tab.refresh()
        self.reports_tab.refresh()
        self.dashboard_tab.refresh()
```

(If `_setup_menu` uses a different `QAction` import or menu variable, match the file's existing pattern — read the method first.)

- [ ] **Step 3: Import-smoke**

Run: `python -c "import ui.regrade_dialog, ui.main_window"`
Expected: exit 0.

- [ ] **Step 4: Full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/regrade_dialog.py ui/main_window.py
git commit -m "feat(grading): Re-grade Collection action (vision, cost-confirm, cancelable)"
```

---

## Self-Review

**Spec coverage:**
- Merged vision call returns condition → Task 3. ✅
- Single source of truth for grade / bin-gap fix → Task 1 + Task 2. ✅
- Vision-or-CV fallback (`resolve_condition`) → Task 4. ✅
- Scan/batch/re-identify integration → Task 5. ✅
- Re-grade collection action (cost estimate, confirm, progress, cancel, skip-missing, condition-only, trial-block handling) → Task 6. ✅
- Model stays haiku; DB schema unchanged → Tasks 3 & 6 use existing model/`update_card`. ✅
- Prompt caps torn/missing-material at Good or lower → Task 3 prompt block. ✅

**Placeholder scan:** No "TBD"/"add error handling"/"write tests for the above". The one place needing the implementer to read surrounding code (Task 5 step 4 `info` variable name; Task 6 step 2 menu var / QAction import) is called out explicitly with how to resolve it.

**Type consistency:** `grade_for_score(score: float) -> str` (Task 1) used in Tasks 2, 4. `resolve_condition(info, front_img, inspector) -> {'grade','score','defects','source'}` (Task 4) used in Task 5 & 6. `identify_card` result `condition` = `{'score': int, 'defects': list}` or `None` (Task 3) consumed by `resolve_condition` (Task 4). Consistent.
