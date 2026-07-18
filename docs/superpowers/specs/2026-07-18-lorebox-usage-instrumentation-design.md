# LoreBox — Beta Usage Instrumentation (local, opt-in-share)

**Date:** 2026-07-18
**Status:** Design approved, pending spec review
**Author:** Jesse + Claude

## Problem

Partner Center telemetry shows a broken activation funnel (69 page views → 14
installs → 5 first-launches; 9 MAU; 26-second average sessions; 20% hang rate;
custom events empty). We can't see *where* in the funnel users drop off —
launch → onboarding → scan → identify → save — so we're guessing at fixes.

The app also carries an explicit, written promise: *"There is no analytics or
tracking"* (`ui/help_content.py`), and the brand is privacy-first ("100% local,
no cloud, no account"). Any covert or auto-transmitted telemetry would break
that promise.

## Goal

Reconstruct the activation funnel **without breaking the no-tracking promise**,
by recording funnel events to a **local file that never leaves the device by
default**, and giving **consenting beta testers** a simple way to export and
hand over their log. Public Store users are unaffected; testers share by
informed consent.

## Non-goals

- No automatic transmission of any data to any server (no endpoint, no
  auto-send). Manual export only.
- No PII, no card data, no image data of any kind in the log.
- No cross-user aggregation infrastructure (that's a later decision if the beta
  grows — the file format leaves a clean seam, but we don't build it now).
- Not a replacement for Partner Center **Health** data (crashes/hangs already
  come from the Store automatically; this adds the funnel the Store can't see).

## Privacy stance

- The instrumented events are **local diagnostic logging**, the same category as
  the existing rotating `app.log` — nothing is sent anywhere by the app.
- Because a tester must *manually export and send* the file, sharing is an
  explicit, informed act. The "no analytics or tracking" promise remains true
  for everyone who simply installs and uses the app.
- Help-text copy is updated for precision: from an absolute "no analytics or
  tracking" to "the app keeps a local diagnostic log on your device and never
  sends it anywhere; you can export it if you're helping test." (Exact wording
  in the plan; it must stay truthful and not weaselly.)

## Architecture

```
event happens (scan, save, launch…) ──► core.usage.log_event(name, **props)
                                              │  best-effort, never throws
                                              ▼
                                   APP_DIR/usage_events.jsonl   (size-capped)
                                              │
                          Help ▸ "Export usage log…"  ──► zip to user-chosen path
```

### `core/usage.py` (new)

A single, dependency-free module.

- Module-level random `SESSION_ID` (hex, generated once per process; not
  persisted, not linked to any identity).
- `log_event(event: str, **props) -> None`:
  - Builds `{"ts": <UTC ISO8601>, "session": SESSION_ID, "event": event, **safe_props}`.
  - **Prop sanitizer:** only keeps values whose type is `str`* / `bool` / `int` /
    `float`; drops everything else. (*strings are allowed only for the small,
    known enum props like `source`/`outcome`; the call sites never pass free
    text — the sanitizer is defense-in-depth, and to be safe it truncates any
    string to a short cap, e.g. 40 chars, so a stray value can't carry a card
    name or path.)
  - Appends one JSON line to `USAGE_LOG = APP_DIR / "usage_events.jsonl"`.
  - **Best-effort:** all filesystem/serialization errors are swallowed and
    logged at debug level — instrumentation must never crash or slow the app.
  - **Size cap:** before appending, if the file exceeds ~1 MB, rotate it once to
    `usage_events.jsonl.1` (mirrors the app.log rotation intent; keeps it bounded
    and keeps the current run's data).
- Uses `core.paths.APP_DIR` (honors `LOREBOX_DATA_DIR`).

### Event call sites (~12 one-liners)

**Lifecycle**
- `app_launched` `{version, first_run: bool}` — in `main.py` after startup (or
  `MainWindow.__init__`); `first_run` from the `welcome_ack` pref being unset.
- `session_ended` `{duration_sec: int}` — in `MainWindow.closeEvent`, duration
  from a start timestamp captured at launch.

**Onboarding**
- `welcome_shown`, `welcome_ack` — in `_show_first_run_notice`.
- `key_prompt_shown`, `key_added`, `key_skipped` — in the key-setup dialog flow
  (`ui/key_setup_dialog.py` / `MainWindow._open_key_setup`).

**Core value funnel**
- `scan_tab_opened` — `ScanTab.showEvent` (first reveal).
- `scanner_detected` `{count: int}` | `scanner_none` — in `ScanTab._load_sources`.
- `scan_started` `{source: "scan"|"file"}` → `scan_completed` — scan-trigger
  path in `scan_tab`.
- `identify_result` `{outcome: "claude"|"ocr"|"trial_blocked"|"error"}` — after
  `identify_card` in `scan_tab` (map from the result `source`).
- `card_saved` `{source: "scan"|"batch"}` — in `scan_tab._save_card` and the
  batch save path.
- `batch_import_started` `{mode}` → `batch_import_completed` `{count}` — in
  `batch_tab`.

**Health**
- `error_caught` `{where}` — at existing broad `except` points that already log
  warnings (add the event alongside, `where` = a short static label, never the
  exception text).

### Export UI

- `MainWindow` gains a Help-menu action **"Export usage log…"**.
- Opens a save-file dialog (default name `lorebox-usage-<date>.zip`), writes a
  zip containing `usage_events.jsonl` (+ the rotated `.1` if present). Optionally
  includes `app.log` — decided in the plan (leaning yes, since crashes correlate;
  app.log is also local-only diagnostic).
- A one-line explainer in the dialog/help: what's in it, that it's for helping
  test, and that they can open it first.

## Data shape

One JSON object per line (JSONL):
```json
{"ts":"2026-07-18T14:03:01Z","session":"a1b2c3d4","event":"card_saved","source":"scan"}
```
- `session`: random per-run hex; groups a single launch's events; ties to no
  identity and is not persisted across runs.
- Props: only small enums / booleans / ints / floats. **Never** card names,
  image data, file paths, keys, or free text.

## Testing

`tests/test_usage.py` (isolated temp dir via `LOREBOX_DATA_DIR` / monkeypatched
`core.paths.APP_DIR`, so no live file is touched):

- `log_event` appends a well-formed JSON line with `ts`/`session`/`event`.
- `SESSION_ID` is stable within a run (two events share a session).
- **Best-effort:** an unwritable path / bad input does not raise.
- **Prop sanitizer:** non-primitive props are dropped; long strings are
  truncated to the cap — a smuggled card name/path can't survive.
- **Size cap:** writing past the cap rotates to `.jsonl.1` and keeps appending.
- Export: produces a zip that contains `usage_events.jsonl`.

## Open items / follow-ups

- Exact revised help/privacy wording (truthful, non-weaselly) — finalized in the
  plan.
- Whether the export zip includes `app.log` (leaning yes).
- If the beta grows, an opt-in auto-send to a self-hosted endpoint could reuse
  the same event format — explicitly out of scope now.
