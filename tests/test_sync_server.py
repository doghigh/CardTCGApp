# tests/test_sync_server.py
import base64, json, urllib.request, urllib.error
from pathlib import Path
import pytest
from core.database import Database
from core.sync_server import ingest_card, SyncServer

PNG1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
B64 = base64.b64encode(PNG1x1).decode()

def _payload(uid="u1", name="Black Lotus"):
    return {"client_uid": uid,
            "card": {"name": name, "game": "Magic: The Gathering", "estimated_value": 9999.0},
            "front_jpeg_b64": B64, "back_jpeg_b64": None}

def test_ingest_adds_card_and_saves_image(tmp_path):
    db = Database(tmp_path / "t.db")
    scans = tmp_path / "scans"; scans.mkdir()
    seen = {}
    out = ingest_card(db, scans, _payload(), seen)
    assert out["id"] > 0
    cards = db.get_all_cards()
    assert len(cards) == 1 and cards[0]["name"] == "Black Lotus"
    assert Path(cards[0]["front_scan_path"]).exists()

def test_ingest_idempotent_on_repeat_uid(tmp_path):
    db = Database(tmp_path / "t.db"); scans = tmp_path / "scans"; scans.mkdir(); seen = {}
    a = ingest_card(db, scans, _payload(uid="dup"), seen)
    b = ingest_card(db, scans, _payload(uid="dup"), seen)
    assert a["id"] == b["id"]
    assert len(db.get_all_cards()) == 1     # not added twice

def test_ingest_malformed_raises(tmp_path):
    db = Database(tmp_path / "t.db"); scans = tmp_path / "scans"; scans.mkdir()
    with pytest.raises(ValueError):
        ingest_card(db, scans, {"card": {}}, {})   # missing client_uid/front

def _req(url, token=None, data=None):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    return urllib.request.Request(url, data=body, headers=headers,
                                  method="POST" if data is not None else "GET")

def test_http_ping_and_auth(tmp_path):
    db = Database(tmp_path / "t.db"); scans = tmp_path / "scans"; scans.mkdir()
    srv = SyncServer(db, scans, token="secret", host="127.0.0.1", port=0)
    port = srv.start()
    try:
        # wrong token -> 401
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(_req(f"http://127.0.0.1:{port}/sync/ping", token="nope"))
        assert ei.value.code == 401
        # right token -> 200 ping
        r = urllib.request.urlopen(_req(f"http://127.0.0.1:{port}/sync/ping", token="secret"))
        assert json.loads(r.read())["app"] == "lorebox"
        # post a card
        r2 = urllib.request.urlopen(_req(f"http://127.0.0.1:{port}/sync/card",
                                         token="secret", data=_payload(uid="h1")))
        assert json.loads(r2.read())["id"] > 0
        assert len(db.get_all_cards()) == 1
    finally:
        srv.stop()

def test_ingest_preserves_defects_json(tmp_path):
    db = Database(tmp_path / "t.db"); scans = tmp_path / "scans"; scans.mkdir(); seen = {}
    p = _payload(uid="dj1")
    p["card"]["defects_json"] = '[{"type":"scratch","severity":2}]'
    ingest_card(db, scans, p, seen)
    row = db.get_all_cards()[0]
    assert row["defects_json"] == '[{"type":"scratch","severity":2}]'
