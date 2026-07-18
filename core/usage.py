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
