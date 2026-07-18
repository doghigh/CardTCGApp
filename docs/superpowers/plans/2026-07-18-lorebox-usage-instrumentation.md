# Beta Usage Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the activation funnel to a local, on-device file (never auto-transmitted) plus a manual "Export usage log" for consenting beta testers — so drop-off is visible without breaking the app's "no analytics or tracking" promise for ordinary users.

**Architecture:** One small `core/usage.py` logger writes JSONL funnel events to `APP_DIR/usage_events.jsonl` (best-effort, size-capped, primitives-only). ~12 one-line `log_event(...)` calls at funnel points. A Help-menu "Export usage log…" zips the log(s) for a tester to inspect and send.

**Tech Stack:** Python 3.11 stdlib only (`json`, `secrets`, `zipfile`); PyQt6 (existing) for the menu action. Spec: `docs/superpowers/specs/2026-07-18-lorebox-usage-instrumentation-design.md`.

## Global Constraints

- **Nothing is auto-transmitted.** No network, no endpoint. Manual export only.
- **No PII / no card data ever** in the log: props are primitives only (`str`/`bool`/`int`/`float`); strings truncated to **40 chars**; non-primitives dropped. No card names, image data, file paths, keys, or free text.
- **Best-effort:** `log_event` must never raise and never block the app — all errors swallowed at debug level.
- **Size-capped:** rotate `usage_events.jsonl` → `usage_events.jsonl.1` once past **1 MB**.
- Data dir comes from `core.paths.APP_DIR` (honors `LOREBOX_DATA_DIR`).
- No new runtime dependency.

---

## File Structure

- Create: `core/usage.py` — the logger (`log_event`, `SESSION_ID`, `_safe_props`, rotation) + `export_zip`.
- Create: `tests/test_usage.py`.
- Modify: `main.py` — `app_launched` event.
- Modify: `ui/main_window.py` — `session_ended` in `closeEvent`; `welcome_*`/`key_*` events; Help-menu "Export usage log…" action + handler.
- Modify: `ui/scan_tab.py` — `scan_tab_opened`, `scanner_detected`/`scanner_none`, `scan_started`/`scan_completed`, `identify_result`, `card_saved`.
- Modify: `ui/batch_tab.py` — `batch_import_started`/`batch_import_completed`, `card_saved{source:"batch"}`.
- Modify: `ui/help_content.py` — precise privacy wording.

---

## Task 1: `core/usage.py` — the logger

**Files:**
- Create: `core/usage.py`
- Test: `tests/test_usage.py`

**Interfaces:**
- Produces:
  - `SESSION_ID: str` (random hex, per process)
  - `USAGE_LOG: Path` (`APP_DIR/usage_events.jsonl`)
  - `log_event(event: str, **props) -> None`
  - `export_zip(dest: Path, include_app_log: bool = True) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_usage.py
import json
import zipfile
from pathlib import Path

import core.usage as usage


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "USAGE_LOG", tmp_path / "usage_events.jsonl")


def test_log_event_writes_jsonl_line(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    usage.log_event("card_saved", source="scan")
    line = (tmp_path / "usage_events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    rec = json.loads(line)
    assert rec["event"] == "card_saved"
    assert rec["source"] == "scan"
    assert rec["session"] == usage.SESSION_ID
    assert rec["ts"].endswith("Z")


def test_props_are_sanitized(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    usage.log_event("e", ok=3, flag=True, ratio=1.5,
                    name="A" * 100, bad=[1, 2], obj={"x": 1})
    rec = json.loads((tmp_path / "usage_events.jsonl").read_text().splitlines()[0])
    assert rec["ok"] == 3 and rec["flag"] is True and rec["ratio"] == 1.5
    assert len(rec["name"]) == 40           # long string truncated
    assert "bad" not in rec and "obj" not in rec   # non-primitives dropped


def test_log_event_never_raises_on_bad_path(tmp_path, monkeypatch):
    # USAGE_LOG points at a directory → append open fails; must be swallowed.
    monkeypatch.setattr(usage, "USAGE_LOG", tmp_path)
    usage.log_event("x", n=1)               # must not raise


def test_rotation_caps_size(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(usage, "_MAX_BYTES", 200)
    for _ in range(80):
        usage.log_event("e", n=1)
    assert (tmp_path / "usage_events.jsonl.1").exists()   # rotated
    assert (tmp_path / "usage_events.jsonl").exists()     # still appending


def test_export_zip_contains_usage_log(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    usage.log_event("app_launched", version="1.2.0")
    dest = tmp_path / "out.zip"
    usage.export_zip(dest, include_app_log=False)
    with zipfile.ZipFile(dest) as z:
        assert "usage_events.jsonl" in z.namelist()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_usage.py -v`
Expected: FAIL — `No module named 'core.usage'`.

- [ ] **Step 3: Write the implementation**

```python
# core/usage.py
"""Local, opt-in-share usage instrumentation.

Writes funnel events to APP_DIR/usage_events.jsonl ON THE USER'S DEVICE. NOTHING
is ever transmitted by the app — a consenting beta tester exports and sends the
file manually (Help > Export usage log). Best-effort: never raises, never blocks.
Props are primitives only, and strings are truncated, so a stray value can never
carry a card name, file path, or key.
"""
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex

from core.paths import APP_DIR

logger = logging.getLogger(__name__)

USAGE_LOG = APP_DIR / "usage_events.jsonl"
SESSION_ID = token_hex(4)
_MAX_BYTES = 1_000_000
_STR_CAP = 40


def _safe_props(props: dict) -> dict:
    """Keep only primitive props; truncate strings so no PII/paths can ride along."""
    out = {}
    for key, val in props.items():
        if isinstance(val, bool) or isinstance(val, (int, float)):
            out[key] = val
        elif isinstance(val, str):
            out[key] = val[:_STR_CAP]
        # anything else (list/dict/object/None-complex) is intentionally dropped
    return out


def _rotate_if_needed() -> None:
    try:
        if USAGE_LOG.exists() and USAGE_LOG.stat().st_size > _MAX_BYTES:
            USAGE_LOG.replace(USAGE_LOG.with_name(USAGE_LOG.name + ".1"))
    except OSError:
        pass


def log_event(event: str, **props) -> None:
    """Append one funnel event to the local usage log. Best-effort; never raises."""
    try:
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "session": SESSION_ID,
            "event": str(event)[:_STR_CAP],
        }
        record.update(_safe_props(props))
        _rotate_if_needed()
        with open(USAGE_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:  # noqa: BLE001 — instrumentation must never break the app
        logger.debug("usage log skipped: %s", exc)


def export_zip(dest: Path, include_app_log: bool = True) -> Path:
    """Zip the usage log(s) (+ app.log) to `dest` for a tester to inspect and send."""
    candidates = [USAGE_LOG, USAGE_LOG.with_name(USAGE_LOG.name + ".1")]
    if include_app_log:
        candidates.append(APP_DIR / "logs" / "app.log")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in candidates:
            if path.exists():
                zf.write(path, arcname=path.name)
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_usage.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (100 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add core/usage.py tests/test_usage.py
git commit -m "feat(usage): local best-effort funnel logger + zip export"
```

---

## Task 2: "Export usage log…" Help-menu action

**Files:**
- Modify: `ui/main_window.py` (`_setup_menu` help menu, ~line 228-244; add a handler)

**Interfaces:**
- Consumes: `core.usage.export_zip`.
- Produces: `MainWindow._export_usage_log()`.

- [ ] **Step 1: Add the menu action**

In `_setup_menu`, in the Help menu block (after the Privacy action, around line 244), add:

```python
        help_menu.addSeparator()
        export_usage_action = QAction("Export usage log…", self)
        export_usage_action.triggered.connect(self._export_usage_log)
        help_menu.addAction(export_usage_action)
```

(`QAction` is already imported in this file.)

- [ ] **Step 2: Add the handler**

Add this method to `MainWindow` (near the other Help handlers):

```python
    def _export_usage_log(self):
        from datetime import date
        from pathlib import Path
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from core import usage
        default = str(Path.home() / f"lorebox-usage-{date.today().isoformat()}.zip")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export usage log", default, "Zip archive (*.zip)")
        if not path:
            return
        try:
            usage.export_zip(Path(path))
            QMessageBox.information(
                self, "Usage log exported",
                "Saved a zip of your local usage log.\n\n"
                "It contains only anonymous funnel events (no card data, names, "
                "or images) — you can open it to see exactly what's in it before "
                "sending it to the developer.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))
```

- [ ] **Step 3: Import-smoke**

Run: `python -c "import ui.main_window"`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add ui/main_window.py
git commit -m "feat(usage): Help > Export usage log action"
```

---

## Task 3: Wire the funnel event call sites

**Files:**
- Modify: `main.py`, `ui/main_window.py`, `ui/scan_tab.py`, `ui/batch_tab.py`

**Interfaces:**
- Consumes: `core.usage.log_event`.

> These are one-line side-effect calls at existing points. Verification is
> import-smoke + full suite (the logger itself is fully tested in Task 1). READ
> each target method first and place the call on the described line.

- [ ] **Step 1: `main.py` — `app_launched`**

Near the top-level imports add `from core.config import get_pref` if not present (it's in `core.config`). In `main()` (after `window.showMaximized()`, near the existing `logger.info(... started ...)` line ~83), add:

```python
    from core import usage
    usage.log_event("app_launched", version=APP_VERSION,
                    first_run=not bool(get_pref("welcome_ack")))
```

- [ ] **Step 2: `ui/main_window.py` — session timing + lifecycle/onboarding events**

In `MainWindow.__init__` (near the top, after `super().__init__()`), add:

```python
        import time
        self._session_start = time.monotonic()
```

In `closeEvent` (line ~246), before the window actually closes, add:

```python
        import time
        from core import usage
        usage.log_event("session_ended",
                        duration_sec=int(time.monotonic() - self._session_start))
```

In `_show_first_run_notice`: log `welcome_shown` right before `dlg.exec()` and `welcome_ack` right after it returns:

```python
        from core import usage
        usage.log_event("welcome_shown")
        dlg.exec()
        usage.log_event("welcome_ack")
```

In `_open_key_setup(self, reason)`: log `key_prompt_shown` before `dlg.exec()`, and `key_added` vs `key_skipped` based on the result:

```python
        from core import usage
        usage.log_event("key_prompt_shown", reason=reason)
        if dlg.exec() == 1:
            usage.log_event("key_added")
            ...existing accepted branch...
        else:
            usage.log_event("key_skipped")
```

(Adapt to the method's existing structure — the accepted branch already calls `reload_credentials()` etc.; add the two events around it.)

- [ ] **Step 3: `ui/scan_tab.py` — scan/identify/save funnel**

- In `showEvent` (added earlier), after the lazy-load guard, add `usage.log_event("scan_tab_opened")` (once — guard with the existing `_sources_loaded` flag path or a separate `_opened_logged` flag so it fires once).
- In `_load_sources`, after enumerating: `usage.log_event("scanner_detected", count=len(sources))` when sources exist, else `usage.log_event("scanner_none")`.
- In `_scan_card` (line ~339): `usage.log_event("scan_started", source="scan")` at entry; in `_load_file`-driven path use `source="file"`.
- In `_finish_scanning` (single-card branch) / after images load: `usage.log_event("scan_completed")`.
- In `_auto_identify` (after `identify_card`, line ~499), map source→outcome:

```python
            from core import usage
            src = (info or {}).get("source", "")
            outcome = ("trial_blocked" if src.startswith("trial_")
                       else src if src in ("claude", "ocr") else "error")
            usage.log_event("identify_result", outcome=outcome)
```

- In `_save_card` (after `self.db.add_card(...)`, line ~622): `usage.log_event("card_saved", source="scan")`.

Add `from core import usage` at the top of `scan_tab.py`.

- [ ] **Step 4: `ui/batch_tab.py` — batch funnel**

- Where a batch run starts (the worker kickoff), log `usage.log_event("batch_import_started", mode=<pairing/mode string>)`.
- After each `self.db.add_card(card_data)` (lines ~249, ~300): `usage.log_event("card_saved", source="batch")`.
- Where `self.cards_added.emit(count)` fires (line ~653): `usage.log_event("batch_import_completed", count=int(count))`.

Add `from core import usage` at the top of `batch_tab.py`.

- [ ] **Step 5: Import-smoke all touched modules**

Run: `python -c "import main, ui.main_window, ui.scan_tab, ui.batch_tab"`
Expected: exit 0.

- [ ] **Step 6: Full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (unchanged count — these are UI side effects, no test asserts on them).

- [ ] **Step 7: Commit**

```bash
git add main.py ui/main_window.py ui/scan_tab.py ui/batch_tab.py
git commit -m "feat(usage): log funnel events at launch/onboarding/scan/save"
```

---

## Task 4: Precise privacy wording

**Files:**
- Modify: `ui/help_content.py` (the "no analytics or tracking" line, ~line 240)

**Interfaces:** none.

- [ ] **Step 1: Update the copy**

Replace the absolute claim:

```
- API keys are stored **encrypted**. There is **no analytics or tracking**.
```

with the precise, truthful version:

```
- API keys are stored **encrypted**. The app does **not send any data anywhere**
  — no accounts, no cloud, no tracking. It keeps a **local diagnostic log on your
  device** (Help ▸ Export usage log) that never leaves your computer unless you
  choose to export and share it while helping test.
```

- [ ] **Step 2: Verify**

Run: `python -c "import ui.help_content"` and `grep -n "does \*\*not send" ui/help_content.py`
Expected: import exit 0; grep finds the new line.

- [ ] **Step 3: Commit**

```bash
git add ui/help_content.py
git commit -m "docs(help): precise privacy wording — local log, never auto-sent"
```

---

## Self-Review

**Spec coverage:**
- Local best-effort logger, size-capped, primitives-only, no auto-send → Task 1. ✅
- The ~12 funnel events (lifecycle/onboarding/scan/identify/save/batch) → Task 3. ✅
- Manual export (Help menu) → Task 2. ✅
- Precise privacy wording → Task 4. ✅
- JSONL shape + session id + prop sanitizer → Task 1 (`log_event`/`_safe_props`). ✅
- Testing (well-formed line, never-raises, sanitizer, rotation, export) → Task 1 tests. ✅
- `app.log` included in export (leaning yes) → Task 1 `export_zip(include_app_log=True)`, used by Task 2's handler (default True). ✅

**Placeholder scan:** No "TBD"/"add error handling"/"write tests for the above". Task 3's call sites are explicit per-file with the exact event + props; they're one-liners verified by import-smoke + suite, which is the right strategy since the logic under test (the logger) is fully covered in Task 1.

**Type consistency:** `log_event(event: str, **props)` and `export_zip(dest, include_app_log=True) -> Path` defined in Task 1, used consistently in Tasks 2 & 3. `SESSION_ID`/`USAGE_LOG` names match between module and tests. Event names and prop keys are consistent with the spec's funnel list.
