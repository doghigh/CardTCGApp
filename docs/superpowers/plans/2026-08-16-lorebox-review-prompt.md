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

There is no unit test for this task. It is a Qt dialog with no logic of its own beyond dispatching to Task 1, which is already tested; a test here would assert only that buttons are wired to functions. It is verified manually in Step 3.

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

    def _rate(self):
        self._resolved = True
        review_prompt.mark_rated()
        usage.log_event("review_prompt_rated", source="prompt")
        review_prompt.open_store_review()
        self.accept()

    def _later(self):
        self._resolved = True
        review_prompt.mark_declined(permanent=False)
        usage.log_event("review_prompt_declined", permanent=False)
        self.reject()

    def _never(self):
        self._resolved = True
        review_prompt.mark_declined(permanent=True)
        usage.log_event("review_prompt_declined", permanent=True)
        self.reject()

    def closeEvent(self, event):
        """Closing with the window X counts as 'Not now', never as permanent."""
        if not self._resolved:
            self._resolved = True
            review_prompt.mark_declined(permanent=False)
            usage.log_event("review_prompt_declined", permanent=False)
        super().closeEvent(event)
```

`_resolved` matters: `QDialog.closeEvent` also runs when the window X is used, and without the guard a user clicking "Don't ask again" could have it followed by a second, contradictory decline event in the usage log.

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
git add ui/review_dialog.py
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

- [ ] **Step 3: Add the three methods**

Insert these immediately before `def _show_first_run_notice(self):` (currently line 125):

```python
    # ── Store review prompt ──────────────────────────────────────────────────

    def _card_count(self) -> int:
        """Total unique cards, or 0 if the collection cannot be read."""
        try:
            return int(self.db.get_collection_stats().get('total_cards', 0) or 0)
        except Exception:      # noqa: BLE001 — a review prompt must never break a save
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

- [ ] **Step 5: Verify the trigger end to end**

This is the one behavior no unit test covers. Force the threshold down so you can reach it, rather than adding 50 cards by hand:

```bash
.venv/Scripts/python -c "import core.review_prompt as rp; print(rp.FIRST_THRESHOLD)"
```

Temporarily set `FIRST_THRESHOLD = 1` in `core/review_prompt.py`, launch the app with `run.bat`, add or import a single card, and confirm:

1. The prompt appears about 1.5 seconds after the save, **not** on top of the Batch Review dialog.
2. "Not now" closes it and it does not return during that session.
3. Restarting the app does not re-show it.

Then **restore `FIRST_THRESHOLD = 50`** and clear the test state from your real prefs:

```bash
.venv/Scripts/python -c "from core.config import set_pref; [set_pref(k, v) for k, v in [('review_prompt_count', 0), ('review_prompt_last_count', 0), ('review_prompt_dismissed', False), ('review_prompt_due', False)]]; print('prefs reset')"
```

Confirm the constant is back before committing:

```bash
git diff core/review_prompt.py
```

Expected: no diff.

- [ ] **Step 6: Commit**

```bash
git add ui/main_window.py
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

- [ ] **Step 4: Verify it renders**

Launch the app with `run.bat` and open Settings. Confirm:

1. An **About Lorebox** group appears below Appearance and above Save / Cancel.
2. The button reads **Rate Lorebox on the Microsoft Store** and the intro text is not clipped.
3. The dialog is still usable at its default size — if the added group makes it too tall for a 1080p screen, report it rather than resizing the dialog unilaterally.

Do not click the button unless you intend to write a permanent dismissal to your real prefs. If you do click it to test the Store hand-off, reset afterwards with the command in Task 3 Step 5.

- [ ] **Step 5: Commit**

```bash
git add ui/settings_dialog.py
git commit -m "feat(review): Rate Lorebox button in Settings"
```

---

## Final verification

- [ ] **Full suite green**

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Expected: baseline count + 11 passing, zero failures.

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
