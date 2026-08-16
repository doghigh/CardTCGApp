# tests/test_sync_server_hardening.py
"""Security regressions for the LAN sync receiver.

The receiver is reachable by anything on the LAN that holds the bearer token,
and the token ships in a QR code anyone in the room can photograph. These cover
the two ways a malicious payload could reach past the token.
"""
import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from core.database import Database
from core.sync_server import ingest_card, SyncServer, MAX_BODY_BYTES

PNG1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
B64 = base64.b64encode(PNG1x1).decode()


def _payload(uid="u1"):
    return {"client_uid": uid,
            "card": {"name": "Black Lotus", "game": "Magic: The Gathering"},
            "front_jpeg_b64": B64, "back_jpeg_b64": None}


# ── Path traversal ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("uid", [
    r"\..\..\..\evil",              # Windows separators, escapes via lexical norm
    "/../../pwned",                 # POSIX separators
    "../../../../etc/passwd",
    "a/b/c",                        # plain nested path
    "C:/Windows/System32/evil",     # absolute-looking
    "..\\..\\Startup\\payload",     # doubled backslashes
])
def test_hostile_uid_cannot_escape_the_scans_dir(tmp_path, uid):
    """A crafted client_uid must never place a file outside scans_dir.

    Regression: uid was interpolated straight into the filename, so
    r'\\..\\..\\..\\evil' resolved out of the scans dir entirely — enough ..
    reaches the Startup folder, which is persistence, not just a stray file.
    """
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    canary = tmp_path / "canary"
    canary.mkdir()

    ingest_card(db, scans, _payload(uid=uid), {})

    written = [p for p in scans.rglob("*") if p.is_file()]
    assert len(written) == 1, "expected exactly one image inside scans_dir"
    # Every written path must resolve to somewhere inside scans_dir.
    assert written[0].resolve().is_relative_to(scans.resolve())
    # And no image may have landed anywhere else under the tmp root. (tmp_path
    # also holds the test's own SQLite files, so scope this to .jpg.)
    assert list(canary.rglob("*")) == []
    strays = [p for p in tmp_path.rglob("*.jpg")
              if not p.resolve().is_relative_to(scans.resolve())]
    assert strays == [], f"image escaped scans_dir: {strays}"


def test_distinct_uids_do_not_collide_on_disk(tmp_path):
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    seen = {}
    ingest_card(db, scans, _payload(uid="alpha"), seen)
    ingest_card(db, scans, _payload(uid="beta"), seen)
    assert len({p.name for p in scans.iterdir() if p.is_file()}) == 2


def test_same_uid_is_still_idempotent(tmp_path):
    """Hardening must not break the dedup contract the phone relies on."""
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    seen = {}
    a = ingest_card(db, scans, _payload(uid="dup"), seen)
    b = ingest_card(db, scans, _payload(uid="dup"), seen)
    assert a["id"] == b["id"]
    assert len(db.get_all_cards()) == 1


@pytest.mark.parametrize("uid", [None, "", 123, {"a": 1}, [], "x" * 5000])
def test_non_string_or_oversized_uid_is_rejected(tmp_path, uid):
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    with pytest.raises(ValueError):
        ingest_card(db, scans, _payload(uid=uid), {})


# ── Request size limits ──────────────────────────────────────────────────────

def test_oversized_body_is_refused_without_reading_it(tmp_path):
    """A declared Content-Length past the cap must 413 before any read.

    Regression: the handler did int(Content-Length) and read the whole body
    into memory unbounded — one request could exhaust RAM.
    """
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    srv = SyncServer(db, scans, token="secret", host="127.0.0.1", port=0)
    port = srv.start()
    try:
        body = json.dumps(_payload()).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/sync/card",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer secret",
                     "Content-Length": str(MAX_BODY_BYTES + 1)},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req, timeout=5)
        assert ei.value.code == 413
        assert db.get_all_cards() == []
    finally:
        srv.stop()


def test_normal_sized_card_still_accepted(tmp_path):
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    srv = SyncServer(db, scans, token="secret", host="127.0.0.1", port=0)
    port = srv.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/sync/card",
            data=json.dumps(_payload(uid="ok1")).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer secret"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        assert json.loads(resp.read())["id"] > 0
        assert len(db.get_all_cards()) == 1
    finally:
        srv.stop()


def test_oversized_decoded_image_is_rejected(tmp_path):
    """Even within the body cap, a single absurd image must not be written."""
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    payload = _payload(uid="big")
    payload["front_jpeg_b64"] = base64.b64encode(b"\x00" * (12 * 1024 * 1024)).decode()
    with pytest.raises(ValueError):
        ingest_card(db, scans, payload, {})
    assert list(scans.rglob("*")) == []


def test_malformed_base64_is_a_clean_400_not_a_crash(tmp_path):
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"
    scans.mkdir()
    payload = _payload(uid="bad64")
    payload["front_jpeg_b64"] = "!!!not base64!!!"
    with pytest.raises(ValueError):
        ingest_card(db, scans, payload, {})
