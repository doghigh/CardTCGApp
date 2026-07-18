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
