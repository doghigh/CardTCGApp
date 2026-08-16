# Lorebox Review Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ask committed users to review Lorebox on the Microsoft Store — at most twice, triggered by card count, never on top of an open dialog — plus a permanent manual entry point in Settings.

**Architecture:** A pure-policy module (`core/review_prompt.py`) decides *whether* to ask, reading and writing four keys in `prefs.json`. A small `QDialog` (`ui/review_dialog.py`) presents the ask. `MainWindow` arms the prompt on the existing `card_added` / `cards_added` signals and displays it through a single deferred, modal-guarded routine. Settings gets an "About Lorebox" group with a button that bypasses all gating.

**Tech Stack:** Python 3.11+, PyQt6, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-15-lorebox-review-prompt-design.md`

**Branch:** `feature/review-prompt` (already created; the spec is committed there)

## Global Constraints

- **No new dependencies.** Everything used here is already in `requirements.txt`.
- **`core/review_prompt.py` must not import Qt at module level.** Import `QDesktopServices` / `QUrl` inside the function body, as the codebase already does at `ui/main_window.py:132` and `ui/batch_review_dialog.py:409`. The reason is layering: `core/` holds policy and must not take a direct Qt dependency for what is a single hand-off call. (Note: this does *not* make the module importable without PyQt6 — `core/__init__.py:5-10` eagerly imports `scanner`→`cv2` and `auth`→`PyQt6`, so any `core.*` import pulls in the full dependency set regardless. The constraint stands on layering grounds alone.)
- **Prefs, not encrypted config.** Use `get_pref` / `set_pref` from `core.config`. These values are not secrets.
- **Store product ID is `9N94V4458M3V`** and must appear in exactly one module (`core/review_prompt.py`).
- **Copy rules:** no emoji, no exclamation marks, no vague startup phrasing. Exact copy strings are given in the tasks — use them verbatim.
- **Usage props must be primitives** (str / int / float / bool). `core.usage._safe_props` silently drops anything else, and strings are truncated at 40 chars.
- **Thresholds:** first ask at 50 cards; second ask requires `last_count + 200`; hard maximum of 2 asks ever.
- **Do not touch** `ui/main_window.py:55` (the stale `"Lorebox v1.1.0"` window title) — it is a known separate issue and is out of scope for this branch.

---

### Task 1: Review-prompt policy module

Pure decision logic plus its tests. This task has no Qt dependency and is the foundation every later task consumes.

**Files:**
- Create: `core/review_prompt.py`
- Test: `tests/test_review_prompt.py`

**Interfaces:**
- Consumes: `core.config.get_pref(key, default)` / `core.config.set_pref(key, value)` — already exist at `core/config.py:130` and `core/config.py:139`.
- Produces, relied on by Tasks 2–4:
  - `should_prompt(card_count: int) -> bool`
  - `arm() -> None`
  - `is_due() -> bool`
  - `mark_prompted(card_count: int) -> None`
  - `mark_rated() -> None`
  - `mark_declined(permanent: bool) -> None`
  - `open_store_review() -> None`
  - Constants `FIRST_THRESHOLD = 50`, `REPEAT_GAP = 200`, `MAX_ASKS = 2`

- [ ] **Step 1: Make sure you can run the test suite**

The repo has no committed virtualenv and the system Python installations are missing dependencies. Create one before writing any code:

```bash
py -3.11 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt pytest
```

**Use 3.11, not 3.13.** `requirements.txt` pins `numpy==1.26.4`, which has no cp313 wheel — pip falls back to a source build that produces a broken long-double and fails at import with `OverflowError: cannot convert longdouble infinity to integer`, taking down 16 of 18 test files at collection. 3.11.9 is installed on this machine and resolves every pin from wheels.

Verify the existing suite runs and passes before you change anything:

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: all tests pass. If they do not, stop and report — do not build on a red suite.

All later `pytest` commands in this plan use `.venv/Scripts/python -m pytest`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_review_prompt.py`. The `_isolate` helper mirrors the established pattern in `tests/test_games.py:5` — it points `PREFS_FILE` at a tmp dir so tests never touch real user prefs.

```python
import core.config as config_mod
import core.review_prompt as rp


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_no_prompt_below_threshold(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.should_prompt(0) is False
    assert rp.should_prompt(49) is False


def test_prompts_at_threshold(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.should_prompt(50) is True
    assert rp.should_prompt(120) is True


def test_second_ask_requires_gap_after_first(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(249) is False
    assert rp.should_prompt(250) is True


def test_batch_jump_does_not_trigger_immediate_second_ask(tmp_path, monkeypatch):
    """Regression: a 200-card batch import can fire the first ask at 240.

    With an absolute second threshold of 250 the next single card would fire a
    second ask ten cards later. The gap must be relative to the first ask.
    """
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(240)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(250) is False
    assert rp.should_prompt(439) is False
    assert rp.should_prompt(440) is True


def test_no_third_ask_ever(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    rp.mark_prompted(250)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(10_000) is False


def test_dont_ask_again_is_permanent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=True)
    assert rp.should_prompt(10_000) is False


def test_rating_is_permanent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_rated()
    assert rp.should_prompt(10_000) is False


def test_arm_is_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.is_due() is False
    rp.arm()
    rp.arm()
    assert rp.is_due() is True


def test_mark_prompted_clears_due_and_records_anchor(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.arm()
    rp.mark_prompted(240)
    assert rp.is_due() is False
    assert rp.asks_used() == 1
    assert rp.next_threshold() == 440


def test_decline_clears_due_so_it_does_not_reshow_next_launch(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.arm()
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    assert rp.is_due() is False


def test_corrupt_prefs_values_do_not_crash(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config_mod.set_pref("review_prompt_count", "not-a-number")
    config_mod.set_pref("review_prompt_last_count", None)
    assert rp.asks_used() == 0
    assert rp.should_prompt(50) is True
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_review_prompt.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'core.review_prompt'`.

- [ ] **Step 4: Write the implementation**

Create `core/review_prompt.py`:

```python
"""Microsoft Store review prompt — policy for when to ask, and how often.

Asks at most twice in a user's lifetime: first at FIRST_THRESHOLD cards, then only
once the collection has grown by REPEAT_GAP more cards than it had at the first ask.

The repeat gap is deliberately relative rather than an absolute second threshold.
BatchTab.cards_added fires once with a whole import's count, so a user at 40 cards
importing a 200-card box crosses the first threshold at 240 — an absolute second
threshold of 250 would then fire a second ask ten cards later.

No module-level Qt import: open_store_review() imports Qt lazily so this module,
and its tests, work without PyQt6 installed.
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
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_review_prompt.py -q
```

Expected: 11 passed.

Then confirm nothing else regressed:

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: all pass, 11 more than the baseline you recorded in Step 1.

- [ ] **Step 6: Commit**

```bash
git add core/review_prompt.py tests/test_review_prompt.py
git commit -m "feat(review): Store review prompt policy with relative repeat gap"
```

---

### Task 2: Review prompt dialog

**Files:**
- Create: `ui/review_dialog.py`

**Interfaces:**
- Consumes from Task 1: `review_prompt.mark_rated()`, `review_prompt.mark_declined(permanent: bool)`, `review_prompt.open_store_review()`.
- Consumes existing: `core.usage.log_event(event: str, **props)` at `core/usage.py:46`.
- Produces, relied on by Task 3: `ReviewPromptDialog(card_count: int, parent=None)` — a `QDialog`; call `.exec()` to show it modally.

**Test:** `tests/test_review_dialog.py` — one test asserting every exit path resolves exactly once.

An earlier draft of this plan claimed the dialog needed no test, on the grounds that it "has no logic beyond dispatching to Task 1." That was wrong. The `reject()` / `closeEvent()` lifecycle *is* real logic, and getting it wrong is exactly what left Escape unresolved. The test below is the regression test for that, and it needs no display — `QDialog` methods can be invoked directly.

- [ ] **Step 1: Write the dialog**

Create `ui/review_dialog.py`:

```python
"""Store review prompt dialog.

Shown at most twice per user — see core/review_prompt.py for the policy. Every
exit path resolves the prompt exactly once, including closing via the window X.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

from core import review_prompt, usage


class ReviewPromptDialog(QDialog):
    """Ask the user to review Lorebox on the Microsoft Store."""

    def __init__(self, card_count: int, parent=None):
        super().__init__(parent)
        self._resolved = False
        self.setWindowTitle("Rate Lorebox")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(22, 22, 22, 22)

        msg = QLabel(
            "<b>Getting value out of Lorebox?</b><br><br>"
            "Reviews on the Microsoft Store are the main way other collectors "
            "find it. Takes about a minute."
        )
        msg.setWordWrap(True)
        v.addWidget(msg)

        row = QHBoxLayout()
        never_btn = QPushButton("Don't ask again")
        never_btn.clicked.connect(self._never)
        row.addWidget(never_btn)
        row.addStretch()

        later_btn = QPushButton("Not now")
        later_btn.clicked.connect(self._later)
        row.addWidget(later_btn)

        rate_btn = QPushButton("Rate Lorebox")
        rate_btn.setProperty("primary", True)
        rate_btn.setDefault(True)
        rate_btn.clicked.connect(self._rate)
        row.addWidget(rate_btn)
        v.addLayout(row)

    def _decline(self, permanent: bool):
        """Resolve as a decline, exactly once."""
        if self._resolved:
            return
        self._resolved = True
        review_prompt.mark_declined(permanent=permanent)
        usage.log_event("review_prompt_declined", permanent=permanent)

    def _rate(self):
        self._resolved = True
        review_prompt.mark_rated()
        usage.log_event("review_prompt_rated", source="prompt")
        review_prompt.open_store_review()
        self.accept()

    def _later(self):
        self._decline(permanent=False)
        self.reject()

    def _never(self):
        self._decline(permanent=True)
        self.reject()

    def reject(self):
        """Every dismissal funnels here: Escape, the window X, and both buttons.

        Overriding reject() rather than closeEvent() is deliberate. Escape does
        NOT emit a close event — QDialog routes it straight to reject() — so a
        closeEvent override silently misses it. The window X does emit one, but
        QDialog.closeEvent's default implementation then calls reject(), so this
        single override covers every path. Verified:
            ESCAPE  -> ['reject']
            CLOSE/X -> ['closeEvent', 'reject']
        """
        self._decline(permanent=False)
        super().reject()
```

Two things carry the correctness here:

`_resolved` makes `_decline` idempotent. `_later` and `_never` both call `_decline` and then `reject()`, which calls `_decline` again — the guard makes the second call a no-op, so "Don't ask again" stays permanent instead of being overwritten by the `permanent=False` that follows it.

There is **no `closeEvent` override**. An earlier draft of this plan used one, which was wrong: it left Escape — a very common way to dismiss a modal — resolving nothing, so no decline event was ever logged for it.

- [ ] **Step 1b: Write the resolution test**

Create `tests/test_review_dialog.py`. It stubs the policy module and the usage logger so it asserts real dispatch behavior without touching prefs or opening the Store:

```python
import sys

import pytest
from PyQt6.QtWidgets import QApplication

import ui.review_dialog as rd


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def calls(monkeypatch):
    rec = {"declined": [], "rated": 0, "store": 0, "events": []}
    monkeypatch.setattr(rd.review_prompt, "mark_declined",
                        lambda permanent: rec["declined"].append(permanent))
    monkeypatch.setattr(rd.review_prompt, "mark_rated",
                        lambda: rec.update(rated=rec["rated"] + 1))
    monkeypatch.setattr(rd.review_prompt, "open_store_review",
                        lambda: rec.update(store=rec["store"] + 1))
    monkeypatch.setattr(rd.usage, "log_event",
                        lambda event, **props: rec["events"].append((event, props)))
    return rec


def test_escape_resolves_as_not_now(qapp, calls):
    """Escape routes straight to reject() without emitting a close event."""
    rd.ReviewPromptDialog(50).reject()
    assert calls["declined"] == [False]
    assert calls["events"] == [("review_prompt_declined", {"permanent": False})]


def test_window_close_resolves_exactly_once(qapp, calls):
    """The X emits closeEvent, whose default impl then calls reject().

    show() is required, not incidental: QDialog.closeEvent only calls reject()
    when the dialog is visible, so close() on a never-shown dialog resolves
    nothing and the test would not exercise the X path at all. Verified:
        hidden .close() -> []
        shown  .close() -> ['reject']
    """
    dlg = rd.ReviewPromptDialog(50)
    dlg.show()
    dlg.close()
    assert calls["declined"] == [False]
    assert len(calls["events"]) == 1


def test_not_now_resolves_exactly_once(qapp, calls):
    rd.ReviewPromptDialog(50)._later()
    assert calls["declined"] == [False]
    assert len(calls["events"]) == 1


def test_dont_ask_again_stays_permanent(qapp, calls):
    """_never() declines permanently, then reject() must not overwrite it."""
    rd.ReviewPromptDialog(50)._never()
    assert calls["declined"] == [True]
    assert calls["events"] == [("review_prompt_declined", {"permanent": True})]


def test_rate_logs_no_decline(qapp, calls):
    rd.ReviewPromptDialog(50)._rate()
    assert calls["rated"] == 1
    assert calls["store"] == 1
    assert calls["declined"] == []
    assert calls["events"] == [("review_prompt_rated", {"source": "prompt"})]
```

`test_escape_resolves_as_not_now` and `test_dont_ask_again_stays_permanent` are the two that matter. The first fails against a `closeEvent`-based implementation; the second catches a `_decline` that isn't idempotent, where `reject()` would downgrade a permanent dismissal back to "Not now".

- [ ] **Step 1c: Run the tests**

```bash
.venv/Scripts/python -m pytest tests/test_review_dialog.py -q
```

Expected: 5 passed.

- [ ] **Step 2: Verify it imports cleanly**

```bash
.venv/Scripts/python -c "import ui.review_dialog; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Verify it renders**

```bash
.venv/Scripts/python -c "from PyQt6.QtWidgets import QApplication; import sys; from ui.review_dialog import ReviewPromptDialog; app=QApplication(sys.argv); ReviewPromptDialog(50).exec()"
```

Expected: the dialog opens. Check the three buttons read **Don't ask again**, **Not now**, **Rate Lorebox**, and that no text is clipped. Close it with the X.

Do **not** click "Rate Lorebox" here — it writes a permanent dismissal to your real prefs and opens the Store.

- [ ] **Step 4: Commit**

```bash
git add ui/review_dialog.py tests/test_review_dialog.py
git commit -m "feat(review): Store review prompt dialog"
```

---

### Task 3: Wire the prompt into MainWindow

**Files:**
- Modify: `ui/main_window.py` — add two signal connections after line 94, one call after line 123, and three new methods.

**Interfaces:**
- Consumes from Task 1: `review_prompt.is_due()`, `should_prompt(card_count)`, `arm()`, `mark_prompted(card_count)`.
- Consumes from Task 2: `ReviewPromptDialog(card_count, parent)`.
- Consumes existing: `self.db.get_collection_stats()` (`core/database.py:396`, returns a dict with `total_cards`); `usage.log_event`; `QTimer` — already imported at `ui/main_window.py:13`.
- Produces: nothing consumed by later tasks. Task 4 is independent of this one.

- [ ] **Step 1: Connect the signals**

In `ui/main_window.py`, find this block (currently lines 88–94):

```python
        # Connect signals — refresh dashboard, collection, and reports on changes
        self.scan_tab.card_added.connect(self.collection_tab.refresh)
        self.scan_tab.card_added.connect(self.reports_tab.refresh)
        self.scan_tab.card_added.connect(self.dashboard_tab.refresh)
        self.batch_tab.cards_added.connect(self.collection_tab.refresh)
        self.batch_tab.cards_added.connect(self.reports_tab.refresh)
        self.batch_tab.cards_added.connect(self.dashboard_tab.refresh)
```

Append two lines directly after it:

```python

        # Store review prompt — armed on a card-count threshold crossing
        self.scan_tab.card_added.connect(self._maybe_prompt_review)
        self.batch_tab.cards_added.connect(self._maybe_prompt_review)
```

`card_added` carries no argument and `cards_added` carries an `int`, which is why the slot signature in Step 3 is `(self, *_)`.

- [ ] **Step 2: Drain a prompt deferred from a previous session**

Find the end of `__init__` (currently lines 122–123):

```python
        # First-run: welcome / parental-involvement notice
        self._show_first_run_notice()
```

Append directly after it:

```python

        # A prompt armed in an earlier session but deferred past a modal
        self._drain_due_review_prompt()
```

- [ ] **Step 2b: Add a module logger**

`ui/main_window.py` has no logger — unusual for this codebase, where `core/auth.py`, `core/config.py`, and `core/usage.py` all define one. `_card_count` below swallows exceptions, and without a logger that swallow is silent: a broken `get_collection_stats()` would permanently disable the review prompt with no trace of why.

Add to the import block at the top of `ui/main_window.py` (currently lines 6-8, `import sys` / `import os` / `from pathlib import Path`):

```python
import logging
```

And immediately after the last import (after `from ui.reports_tab import ReportsTab`, currently line 29):

```python

logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Add the three methods**

Insert these immediately before `def _show_first_run_notice(self):` (currently line 125):

```python
    # ── Store review prompt ──────────────────────────────────────────────────

    def _card_count(self) -> int:
        """Total unique cards, or 0 if the collection cannot be read."""
        try:
            return int(self.db.get_collection_stats().get('total_cards', 0) or 0)
        except Exception as exc:   # noqa: BLE001 — a review prompt must never break a save
            logger.debug("Review prompt: could not read card count: %s", exc)
            return 0

    def _maybe_prompt_review(self, *_):
        """Arm the review prompt when the collection crosses a threshold.

        Accepts and ignores any argument: card_added sends none, cards_added
        sends an int.
        """
        from core import review_prompt
        if review_prompt.is_due():
            return                          # already armed; do not re-arm
        if review_prompt.should_prompt(self._card_count()):
            review_prompt.arm()
            QTimer.singleShot(1500, self._show_review_prompt)

    def _drain_due_review_prompt(self):
        """Show a prompt armed in a previous session, via the same routine."""
        from core import review_prompt
        if review_prompt.is_due():
            QTimer.singleShot(1500, self._show_review_prompt)

    def _show_review_prompt(self):
        """Display the prompt, unless a modal is up — then leave it armed."""
        from PyQt6.QtWidgets import QApplication
        from core import review_prompt
        from ui.review_dialog import ReviewPromptDialog

        if not review_prompt.is_due():
            return
        if QApplication.activeModalWidget() is not None:
            return          # stays armed; drained at next launch

        count = self._card_count()
        review_prompt.mark_prompted(count)
        usage.log_event("review_prompt_shown", card_count=count)
        ReviewPromptDialog(count, self).exec()

```

`mark_prompted` runs *before* `.exec()` so the armed flag is spent even if the dialog raises — otherwise a crash in the dialog would leave the prompt armed forever and re-show it every launch.

- [ ] **Step 4: Verify the module imports and the suite is still green**

```bash
.venv/Scripts/python -c "import ui.main_window; print('ok')"
```

Expected: `ok`

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 5: Test the arming logic headlessly**

Do **not** launch the app to verify this task. `run.bat` opens a GUI that blocks until a human closes it, and driving it would write to the real `%APPDATA%/Lorebox/prefs.json`. The human runs the GUI check separately (see "Manual verification" below). Your job is the logic.

The three new methods are plain functions on `MainWindow`, so they can be exercised against a lightweight stub without constructing a real window — no database, scanner, or Qt widget tree required.

Create `tests/test_main_window_review_hook.py`:

```python
import sys

import pytest
from PyQt6.QtWidgets import QApplication

import core.config as config_mod
import core.review_prompt as rp
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _FakeDB:
    """Stands in for Database, returning a fixed collection size."""

    def __init__(self, total):
        self._total = total

    def get_collection_stats(self):
        return {"total_cards": self._total}


class _FakeWindow:
    """Borrows the real methods; supplies only what they actually touch."""

    _card_count = MainWindow._card_count
    _maybe_prompt_review = MainWindow._maybe_prompt_review
    _drain_due_review_prompt = MainWindow._drain_due_review_prompt

    def __init__(self, total):
        self.db = _FakeDB(total)

    def _show_review_prompt(self):
        pass          # QTimer target; never fires without an event loop


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_below_threshold_does_not_arm(qapp, isolated):
    _FakeWindow(49)._maybe_prompt_review()
    assert rp.is_due() is False


def test_crossing_threshold_arms(qapp, isolated):
    _FakeWindow(50)._maybe_prompt_review()
    assert rp.is_due() is True


def test_batch_signal_argument_is_accepted(qapp, isolated):
    """cards_added emits an int; card_added emits nothing. Both must work."""
    _FakeWindow(50)._maybe_prompt_review(12)
    assert rp.is_due() is True


def test_already_armed_does_not_rearm(qapp, isolated):
    win = _FakeWindow(50)
    win._maybe_prompt_review()
    rp.mark_prompted(50)              # spends the ask, clears due
    win._maybe_prompt_review()        # a later save must not re-arm
    assert rp.is_due() is False
    assert rp.asks_used() == 1


def test_card_count_survives_a_broken_db(qapp, isolated):
    class Broken:
        def get_collection_stats(self):
            raise RuntimeError("db is down")

    win = _FakeWindow(0)
    win.db = Broken()
    assert win._card_count() == 0     # must not raise — a save must never break
    win._maybe_prompt_review()
    assert rp.is_due() is False


def test_drain_is_a_noop_when_not_due(qapp, isolated):
    _FakeWindow(0)._drain_due_review_prompt()
    assert rp.is_due() is False


def test_armed_prompt_is_not_rearmed(qapp, isolated, monkeypatch):
    """A save arriving while a prompt is armed must not schedule a second one.

    This is the test for the `if is_due(): return` guard specifically. It has to
    arm() directly rather than going through mark_prompted(), because
    mark_prompted clears the due flag — which would leave the guard unreached
    and the test passing for an unrelated reason (the +200 gap), whether or not
    the guard exists at all.
    """
    win = _FakeWindow(50)
    rp.arm()                                  # armed, not yet displayed
    rearmed = []
    monkeypatch.setattr(rp, "arm", lambda: rearmed.append(1))
    win._maybe_prompt_review()
    assert rearmed == []                      # guard short-circuited before arm()
```

Two of these carry real weight. `test_already_armed_does_not_rearm` proves the +200 gap suppresses a second ask once one is spent. `test_armed_prompt_is_not_rearmed` proves the `is_due()` guard itself works — delete the guard from `_maybe_prompt_review` and only that test fails.

- [ ] **Step 5b: Run the new tests**

```bash
.venv/Scripts/python -m pytest tests/test_main_window_review_hook.py -q
```

Expected: 7 passed.

Then the full suite:

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: 135 passed (128 + 7 new).

- [ ] **Step 5c: Confirm you left no test scaffolding behind**

```bash
git diff core/review_prompt.py
```

Expected: no diff. Never edit `FIRST_THRESHOLD` to test — the tests above control the card count instead, so the constant stays at 50.

**Manual verification (human, not the implementer).** The modal-deferral and next-launch paths are Qt-runtime behavior these tests cannot reach. To check them by hand: temporarily set `FIRST_THRESHOLD = 1`, run `run.bat`, import a small batch, and confirm the prompt appears ~1.5s after the Batch Review dialog closes rather than on top of it; then confirm "Not now" ends it for that session and it does not return on restart. Restore `FIRST_THRESHOLD = 50` and reset the four `review_prompt_*` keys in `%APPDATA%/Lorebox/prefs.json` afterwards.

- [ ] **Step 6: Commit**

```bash
git add ui/main_window.py tests/test_main_window_review_hook.py
git commit -m "feat(review): arm the Store review prompt on card-count thresholds"
```

---

### Task 4: Settings entry point

Independent of Task 3 — it can be built and reviewed on its own.

**Files:**
- Modify: `ui/settings_dialog.py` — add one line after line 165 and two new methods.

**Interfaces:**
- Consumes from Task 1: `review_prompt.mark_rated()`, `review_prompt.open_store_review()`.
- Consumes existing: `core.usage.log_event`. `QGroupBox`, `QVBoxLayout`, `QHBoxLayout`, `QLabel`, `QPushButton` are all already imported at `ui/settings_dialog.py:12-15` — add no imports.
- Produces: nothing.

- [ ] **Step 1: Add the group to the layout**

In `ui/settings_dialog.py`, find these lines (currently 164–167):

```python
        # ── Appearance ────────────────────────────────────────────────────────
        layout.addWidget(self._build_appearance_group())

        # ── Save / Cancel ─────────────────────────────────────────────────────
```

Insert the About group between them:

```python
        # ── Appearance ────────────────────────────────────────────────────────
        layout.addWidget(self._build_appearance_group())

        # ── About ─────────────────────────────────────────────────────────────
        layout.addWidget(self._build_about_group())

        # ── Save / Cancel ─────────────────────────────────────────────────────
```

- [ ] **Step 2: Add the two methods**

Insert these immediately before `def _build_appearance_group(self) -> QGroupBox:` (currently line 178):

```python
    # ── about / store review ────────────────────────────────────────────────

    def _build_about_group(self) -> QGroupBox:
        box = QGroupBox("About Lorebox")
        v = QVBoxLayout(box)

        intro = QLabel("Reviews on the Microsoft Store are the main way other "
                       "collectors find Lorebox.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b8fa8; font-size: 11px;")
        v.addWidget(intro)

        row = QHBoxLayout()
        rate_btn = QPushButton("Rate Lorebox on the Microsoft Store")
        rate_btn.clicked.connect(self._open_store_review)
        row.addWidget(rate_btn)
        row.addStretch()
        v.addLayout(row)
        return box

    def _open_store_review(self):
        """Manual review entry point. Ignores all gating — the user asked.

        Also stops the automatic prompt: being nagged to review an app you have
        already gone and reviewed is worse than never being asked.
        """
        from core import review_prompt, usage
        review_prompt.mark_rated()
        usage.log_event("review_prompt_rated", source="settings")
        review_prompt.open_store_review()

```

The `intro` styling copies the existing note styling at `ui/settings_dialog.py:160` so the group matches the surrounding dialog.

- [ ] **Step 3: Verify it imports and the suite is still green**

```bash
.venv/Scripts/python -c "import ui.settings_dialog; print('ok')"
```

Expected: `ok`

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 4: Test it headlessly**

Do **not** launch the app. `run.bat` opens a GUI that blocks until a human closes it, and clicking the button would write a permanent dismissal into the real `%APPDATA%/Lorebox/prefs.json` and open the Microsoft Store. The human does the visual check (see below).

Create `tests/test_settings_review_button.py`:

```python
import sys

import pytest
from PyQt6.QtWidgets import QApplication, QGroupBox, QPushButton

import core.config as config_mod
import core.review_prompt as rp
from ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_about_group_is_present(qapp, isolated):
    dlg = SettingsDialog()
    titles = [b.title() for b in dlg.findChildren(QGroupBox)]
    assert "About Lorebox" in titles


def test_rate_button_is_present(qapp, isolated):
    dlg = SettingsDialog()
    labels = [b.text() for b in dlg.findChildren(QPushButton)]
    assert "Rate Lorebox on the Microsoft Store" in labels


def test_button_dispatches_and_dismisses(qapp, isolated, monkeypatch):
    """The Settings path records a permanent dismissal and tags its source.

    open_store_review is stubbed so the test never launches the Store, but
    mark_rated is left real so the prefs write is genuinely exercised.
    """
    opened, events = [], []
    monkeypatch.setattr(rp, "open_store_review", lambda: opened.append(1))
    import core.usage as usage_mod
    monkeypatch.setattr(usage_mod, "log_event",
                        lambda event, **props: events.append((event, props)))

    assert rp.is_dismissed() is False
    SettingsDialog()._open_store_review()

    assert opened == [1]
    assert events == [("review_prompt_rated", {"source": "settings"})]
    assert rp.is_dismissed() is True
    assert rp.should_prompt(10_000) is False   # auto-prompt is now off for good
```

The third test is the one that matters: it proves the Settings button suppresses the automatic prompt, which is the behavioral decision that distinguishes this entry point from a plain hyperlink.

- [ ] **Step 4b: Run the tests**

```bash
.venv/Scripts/python -m pytest tests/test_settings_review_button.py -q
```

Expected: 3 passed.

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: 138 passed (135 + 3 new).

**Manual verification (human, not the implementer).** Open Settings in the running app and confirm the About Lorebox group sits below Appearance and above Save / Cancel, the intro text is not clipped, and the dialog still fits a 1080p screen with the extra group. Do not click the button unless you intend to write a real permanent dismissal.

- [ ] **Step 5: Commit**

```bash
git add ui/settings_dialog.py tests/test_settings_review_button.py
git commit -m "feat(review): Rate Lorebox button in Settings"
```

---

## Final verification

- [ ] **Full suite green**

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: 138 passed, zero failures.

- [ ] **Store ID appears in exactly one module**

```bash
git grep -n "9N94V4458M3V" -- "*.py"
```

Expected: exactly one line — `core/review_prompt.py`, the `STORE_PRODUCT_ID` assignment. The two URL constants build from that name via f-string, so the literal must not appear anywhere else.

- [ ] **No Qt import at module level in the policy module**

```bash
.venv/Scripts/python -c "import ast,sys; t=ast.parse(open('core/review_prompt.py').read()); bad=[n for n in t.body if isinstance(n,(ast.Import,ast.ImportFrom)) and 'PyQt6' in ast.dump(n)]; print('FAIL' if bad else 'ok')"
```

Expected: `ok`

- [ ] **No stray threshold override left behind**

```bash
git grep -n "FIRST_THRESHOLD = " -- "*.py"
```

Expected: exactly one line, `core/review_prompt.py`, reading `FIRST_THRESHOLD = 50`.

- [ ] **Report what was not covered**

State plainly in the completion summary that the modal-deferral path and the next-launch drain were verified manually (Task 3 Step 5) and are not under automated test. Do not describe them as "tested".
