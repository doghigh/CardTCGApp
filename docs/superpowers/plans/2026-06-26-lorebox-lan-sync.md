# LoreBox LAN Sync v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the phone push user-selected scanned cards (data + images) to the desktop over the LAN; each card the desktop acknowledges is deleted from the phone.

**Architecture:** Desktop runs a token-gated stdlib `http.server` (no new deps) started only while a "Receive from phone" dialog is open; it ingests cards via `Database.add_card(merge_duplicates=True)` and saves base64 images to the scans dir. The phone connects via a QR carrying the PC's LAN IP+port+token, pushes one card per request (JSON + base64 images), and on each per-card ack deletes that card's row and image files.

**Tech Stack:** Desktop — Python 3.11 stdlib (`http.server`, `socket`, `secrets`, `base64`), PyQt6, existing `Database`/`AppConfig`, `qrcode`. Phone — Kotlin, OkHttp, kotlinx-serialization, Room, ZXing (existing), `okhttp3:mockwebserver` (new test dep).

## Global Constraints

- **Two repos.** Desktop: `C:\Users\catsj\zenflow_projects\CardTCGApp` (Phase A). Phone: `C:\Users\catsj\zenflow_projects\LoreBox-Mobile` (Phase B). Build Phase A first so Phase B has a real server for end-to-end.
- **Direction:** phone → PC only. Sync **moves** a card (deleted from phone on ack). No PC→phone.
- **Desktop: stdlib only for the server** — no Flask/Werkzeug, no new runtime dependency in the packaged app.
- **Protocol** (exact):
  - `GET /sync/ping` → `200 {"app":"lorebox","proto":1}`.
  - `POST /sync/card`, body `application/json`: `{ "client_uid": str, "card": {…schema fields…}, "front_jpeg_b64": str, "back_jpeg_b64": str|null }` → `200 {"id": <int>}`.
  - Every request: header `Authorization: Bearer <syncToken>`; missing/wrong → `401`. Constant-time compare.
  - Duplicate `client_uid` within a server run → idempotent: return the same `{"id"}` without re-adding.
- **Card schema fields** (the `card` object keys, matching desktop DB): `name, set_name, card_number, rarity, game, year, language, foil, condition_grade, condition_score, defects_json, estimated_value, purchase_price, purchase_date, notes, quantity`.
- **Sync token:** `secrets.token_urlsafe(32)`, persisted in `AppConfig` under key `"SYNC_TOKEN"`, reused across sessions.
- **Scans dir (desktop):** `%APPDATA%/Lorebox/scans/cards/` (same dir the app already uses). Received images saved there as `sync_{client_uid}_front.jpg` / `_back.jpg`.
- **QR payload:** JSON `{ "host": str, "port": int, "syncToken": str }`.
- **Merge:** desktop uses `Database.add_card(card_dict, merge_duplicates=True)` unchanged.
- **Desktop server bind:** `ThreadingHTTPServer(("0.0.0.0", port), …)`, runs on a background daemon thread, started/stopped by the receive dialog.
- **Phone package root:** `com.lorebox.android`. Phone Gradle runs with `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"` and `ANDROID_SDK_ROOT="/c/Users/catsj/AppData/Local/Android/Sdk"`.

---

## File Structure

```
# Phase A — desktop (CardTCGApp)
core/net_utils.py              # detect_lan_ip()
core/config.py                 # + get_or_create_sync_token()  (modify)
core/sync_server.py            # ingest_card() + SyncServer (http.server, lifecycle)
ui/sync_receive_dialog.py      # ReceiveFromPhoneDialog (start server, QR, live log, stop)
ui/main_window.py              # + "Receive from phone…" action  (modify)
tests/test_net_utils.py
tests/test_sync_server.py

# Phase B — phone (LoreBox-Mobile), under app/src/main/java/com/lorebox/android/
data/sync/SyncEndpoint.kt      # payload {host,port,syncToken} + parseSyncEndpoint()
data/sync/SyncModels.kt        # CardSyncResult
data/sync/SyncClient.kt        # ping(), pushCard(), buildCardJson()
data/keys/KeyStore.kt          # + sync endpoint accessors (modify)
data/image/ImageStore.kt       # + delete(path) + read(path)  (modify)
data/CardRepository.kt         # + deleteCardWithImages()  (modify; inject ImageStore)
LoreboxApp.kt                  # pass imageStore into CardRepository  (modify)
ui/sync/SyncViewModel.kt       # push orchestration + progress
ui/collection/CollectionScreen.kt  # multi-select + Sync action  (modify)
ui/nav/LoreboxNav.kt           # sync route/flow wiring  (modify)
# tests under app/src/test/java/com/lorebox/android/
```

---

## Phase A — Desktop receiver (CardTCGApp)

Work from `C:\Users\catsj\zenflow_projects\CardTCGApp`. Run Python tests with `python -m pytest <path> -v`.

### Task A1: LAN IP detection

**Files:**
- Create: `core/net_utils.py`
- Test: `tests/test_net_utils.py`

**Interfaces:**
- Produces: `def detect_lan_ip() -> str` — best-effort primary LAN IPv4; returns `"127.0.0.1"` if it can't be determined.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_net_utils.py
from core.net_utils import detect_lan_ip

def test_returns_ipv4_string():
    ip = detect_lan_ip()
    assert isinstance(ip, str)
    parts = ip.split(".")
    assert len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

def test_never_raises_and_is_nonempty():
    assert detect_lan_ip()  # non-empty, no exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_utils.py -v`
Expected: FAIL (ModuleNotFoundError: core.net_utils).

- [ ] **Step 3: Implement**

```python
# core/net_utils.py
"""Network helpers for LAN sync."""
import socket


def detect_lan_ip() -> str:
    """Return this machine's primary LAN IPv4 address, or '127.0.0.1' on failure.

    Uses the standard UDP-connect trick: connecting a datagram socket to a public
    address forces the OS to pick the outbound interface, whose address we read.
    No packets are actually sent.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_utils.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/net_utils.py tests/test_net_utils.py
git commit -m "feat(sync): LAN IP detection util"
```

---

### Task A2: Persistent sync token in config

**Files:**
- Modify: `core/config.py` (add a method to the `AppConfig` class)
- Test: `tests/test_sync_token.py`

**Interfaces:**
- Consumes: existing `AppConfig.get(key)`, `AppConfig.save({key: val})`.
- Produces: `AppConfig.get_or_create_sync_token() -> str` — returns the stored `"SYNC_TOKEN"`, generating and persisting a new `secrets.token_urlsafe(32)` on first call. Stable across calls.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_token.py
import importlib

def test_token_is_stable_and_urlsafe(tmp_path, monkeypatch):
    # Point APP_DIR at a temp dir so we don't touch the real config.
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.config as config_mod
    importlib.reload(config_mod)
    cfg = config_mod.AppConfig()

    t1 = cfg.get_or_create_sync_token()
    t2 = cfg.get_or_create_sync_token()
    assert t1 == t2                      # stable
    assert len(t1) >= 32                 # token_urlsafe(32) -> ~43 chars
    # A freshly constructed config reads the same persisted token.
    assert config_mod.AppConfig().get_or_create_sync_token() == t1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_token.py -v`
Expected: FAIL (AttributeError: get_or_create_sync_token).

- [ ] **Step 3: Implement** — add `import secrets` at the top of `core/config.py` if absent, and this method to `AppConfig`:

```python
    def get_or_create_sync_token(self) -> str:
        """Return the persistent LAN-sync bearer token, creating it on first use."""
        token = self._data.get("SYNC_TOKEN", "")
        if not token:
            token = secrets.token_urlsafe(32)
            self.save({"SYNC_TOKEN": token})
        return token
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sync_token.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/config.py tests/test_sync_token.py
git commit -m "feat(sync): persistent sync bearer token in config"
```

---

### Task A3: Sync server — ingest + HTTP + lifecycle

**Files:**
- Create: `core/sync_server.py`
- Test: `tests/test_sync_server.py`

**Interfaces:**
- Consumes: `Database` (existing, `add_card(dict, merge_duplicates=True) -> int`), `detect_lan_ip` not needed here.
- Produces:
  - `def ingest_card(db, scans_dir: Path, payload: dict, seen: dict) -> dict` — pure ingest: validates `payload` has `client_uid`, `card`, `front_jpeg_b64`; if `client_uid` already in `seen`, returns `{"id": seen[client_uid]}` without re-adding; else base64-decodes images → writes `scans_dir/sync_<uid>_front.jpg` (and `_back.jpg` if present) → `db.add_card({**card, "front_scan_path":…, "back_scan_path":…}, merge_duplicates=True)` → records `seen[uid]=id` → returns `{"id": id}`. Raises `ValueError` on malformed payload.
  - `class SyncServer`: `__init__(self, db, scans_dir: Path, token: str, host="0.0.0.0", port=0, on_card=None)`; `start() -> int` (binds, returns actual port, serves on a daemon thread); `stop()`. `on_card` is an optional `Callable[[dict], None]` called with each ingested card dict (for the UI log).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sync_server.py -v`
Expected: FAIL (ModuleNotFoundError: core.sync_server).

- [ ] **Step 3: Implement `core/sync_server.py`**

```python
# core/sync_server.py
"""LAN sync receiver: a tiny stdlib HTTP server the phone pushes scanned cards to.

No third-party dependency. Token-gated. Started/stopped by the receive dialog.
Protocol:
  GET  /sync/ping  -> 200 {"app":"lorebox","proto":1}
  POST /sync/card  -> 200 {"id": <card_id>}   (JSON body; base64 images)
Every request must carry  Authorization: Bearer <token>.
"""
import base64
import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


def ingest_card(db, scans_dir: Path, payload: dict, seen: Dict[str, int]) -> dict:
    """Validate + persist one pushed card. Idempotent on client_uid. Returns {"id": int}."""
    uid = payload.get("client_uid")
    card = payload.get("card")
    front_b64 = payload.get("front_jpeg_b64")
    if not uid or not isinstance(card, dict) or not front_b64:
        raise ValueError("payload missing client_uid, card, or front_jpeg_b64")

    if uid in seen:
        return {"id": seen[uid]}

    scans_dir.mkdir(parents=True, exist_ok=True)
    front_path = scans_dir / f"sync_{uid}_front.jpg"
    front_path.write_bytes(base64.b64decode(front_b64))
    back_path = None
    if payload.get("back_jpeg_b64"):
        back_path = scans_dir / f"sync_{uid}_back.jpg"
        back_path.write_bytes(base64.b64decode(payload["back_jpeg_b64"]))

    record = {**card,
              "front_scan_path": str(front_path),
              "back_scan_path": str(back_path) if back_path else None}
    card_id = db.add_card(record, merge_duplicates=True)
    seen[uid] = card_id
    return {"id": card_id}


def _make_handler(db, scans_dir: Path, token: str, seen: Dict[str, int],
                  on_card: Optional[Callable[[dict], None]]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default stderr logging
            pass

        def _authed(self) -> bool:
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            supplied = header[len(prefix):] if header.startswith(prefix) else ""
            return hmac.compare_digest(supplied, token)

        def _send(self, code: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            if self.path == "/sync/ping":
                return self._send(200, {"app": "lorebox", "proto": 1})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            if self.path != "/sync/card":
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length).decode())
                result = ingest_card(db, scans_dir, payload, seen)
            except ValueError as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 — never crash the server thread
                logger.warning("sync ingest failed: %s", exc)
                return self._send(500, {"error": "ingest failed"})
            if on_card:
                try:
                    on_card(payload.get("card", {}))
                except Exception:  # noqa: BLE001 — UI callback must not break ingest
                    pass
            self._send(200, result)

    return Handler


class SyncServer:
    def __init__(self, db, scans_dir: Path, token: str, host: str = "0.0.0.0",
                 port: int = 0, on_card: Optional[Callable[[dict], None]] = None):
        self._db = db
        self._scans_dir = Path(scans_dir)
        self._token = token
        self._host = host
        self._port = port
        self._on_card = on_card
        self._seen: Dict[str, int] = {}
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        handler = _make_handler(self._db, self._scans_dir, self._token,
                                self._seen, self._on_card)
        self._httpd = ThreadingHTTPServer((self._host, self._port), handler)
        actual_port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Sync server listening on %s:%d", self._host, actual_port)
        return actual_port

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self._thread = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sync_server.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/sync_server.py tests/test_sync_server.py
git commit -m "feat(sync): stdlib http.server receiver with token auth + idempotent ingest"
```

---

### Task A4: "Receive from phone" dialog + menu action

**Files:**
- Create: `ui/sync_receive_dialog.py`
- Modify: `ui/main_window.py` (add a File-menu action)

**Interfaces:**
- Consumes: `AppConfig.get_or_create_sync_token()` (A2), `detect_lan_ip()` (A1), `SyncServer` (A3), existing `Database` instance held by `MainWindow`, `qrcode` (existing).
- Produces: `class ReceiveFromPhoneDialog(QDialog)` — on open: get token, detect IP, start `SyncServer` on a chosen port (default `8765`, fall back to `0`), render a QR of `{"host","port","syncToken"}`, show a live received-cards log; on close: stop the server. `MainWindow._open_receive_dialog(self)` opens it.

- [ ] **Step 1: Implement `ui/sync_receive_dialog.py`**

```python
# ui/sync_receive_dialog.py
"""'Receive from phone' dialog — runs the LAN sync server while open and shows a
connection QR for the LoreBox Android app to scan. See
docs/superpowers/specs/2026-06-26-lorebox-lan-sync-design.md.
"""
import io
import json
import os
from pathlib import Path

import qrcode
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPlainTextEdit

from core.config import config
from core.net_utils import detect_lan_ip
from core.sync_server import SyncServer

SCANS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Lorebox" / "scans" / "cards"
DEFAULT_PORT = 8765


class ReceiveFromPhoneDialog(QDialog):
    # Marshal server-thread callbacks onto the UI thread.
    _card_received = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Receive from phone")
        self.resize(360, 520)
        self._db = db
        self._count = 0

        layout = QVBoxLayout(self)
        info = QLabel("In the LoreBox phone app, select cards and tap Sync, then scan "
                      "this code. Keep this window open while syncing.")
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        token = config.get_or_create_sync_token()
        host = detect_lan_ip()
        self._server = SyncServer(db, SCANS_DIR, token, host="0.0.0.0",
                                  port=DEFAULT_PORT, on_card=self._on_card_threadsafe)
        try:
            port = self._server.start()
        except OSError:
            self._server = SyncServer(db, SCANS_DIR, token, host="0.0.0.0", port=0,
                                      on_card=self._on_card_threadsafe)
            port = self._server.start()

        payload = json.dumps({"host": host, "port": port, "syncToken": token})
        img = qrcode.make(payload)
        buf = io.BytesIO(); img.save(buf, format="PNG")
        pix = QPixmap(); pix.loadFromData(buf.getvalue(), "PNG")
        qr_label = QLabel(); qr_label.setPixmap(pix)
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(qr_label)

        layout.addWidget(QLabel(f"Listening on {host}:{port}"))
        self._log = QPlainTextEdit(); self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._card_received.connect(self._append_log)

    def _on_card_threadsafe(self, card: dict):
        name = (card or {}).get("name", "card")
        self._card_received.emit(str(name))

    def _append_log(self, name: str):
        self._count += 1
        self._log.appendPlainText(f"{self._count}. received {name}")

    def closeEvent(self, event):
        try:
            self._server.stop()
        finally:
            super().closeEvent(event)
```

- [ ] **Step 2: Wire the MainWindow action** — in `ui/main_window.py`, add next to the existing `pair_action` block:

```python
        receive_action = QAction("📡 Receive from phone…", self)
        receive_action.triggered.connect(self._open_receive_dialog)
        file_menu.addAction(receive_action)
```

and add the method (near `_open_pair_dialog`):

```python
    def _open_receive_dialog(self):
        from ui.sync_receive_dialog import ReceiveFromPhoneDialog
        ReceiveFromPhoneDialog(self.db, self).exec()
```

(Use the same attribute the MainWindow already holds its `Database` on. If it is not `self.db`, locate the existing `Database(...)` assignment in `main_window.py` and pass that attribute instead.)

- [ ] **Step 3: Headless construction smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "from PyQt6.QtWidgets import QApplication; app=QApplication([]); from core.database import Database; import tempfile,os; db=Database(os.path.join(tempfile.mkdtemp(),'t.db')); from ui.sync_receive_dialog import ReceiveFromPhoneDialog; d=ReceiveFromPhoneDialog(db); print('OK', d.windowTitle()); d._server.stop()"
```
Expected: prints `OK Receive from phone` with no exception. Also confirm `python -c "import ui.main_window"` still imports cleanly.

- [ ] **Step 4: Commit**

```bash
git add ui/sync_receive_dialog.py ui/main_window.py
git commit -m "feat(sync): Receive from phone dialog + menu action"
```

---

## Phase B — Phone client (LoreBox-Mobile)

Work from `C:\Users\catsj\zenflow_projects\LoreBox-Mobile`. Run unit tests:
`JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ANDROID_SDK_ROOT="/c/Users/catsj/AppData/Local/Android/Sdk" ./gradlew :app:testDebugUnitTest --tests "<filter>"`.

### Task B1: SyncEndpoint payload + parse + mockwebserver dep

**Files:**
- Create: `app/src/main/java/com/lorebox/android/data/sync/SyncEndpoint.kt`
- Modify: `app/build.gradle.kts` (add `testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")`)
- Test: `app/src/test/java/com/lorebox/android/data/sync/SyncEndpointTest.kt`

**Interfaces:**
- Produces: `@Serializable data class SyncEndpoint(val host: String, val port: Int, val syncToken: String)` and `fun parseSyncEndpoint(qr: String): SyncEndpoint?` — returns null unless all three keys are present/valid (distinguishes a sync QR from the key-provisioning QR). `fun SyncEndpoint.baseUrl(): String = "http://$host:$port"`.

- [ ] **Step 1: Add the test dep** in `app/build.gradle.kts` dependencies:

```kotlin
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
```

- [ ] **Step 2: Write the failing test**

```kotlin
package com.lorebox.android.data.sync
import org.junit.Assert.*
import org.junit.Test

class SyncEndpointTest {
    @Test fun parsesValid() {
        val e = parseSyncEndpoint("""{"host":"192.168.1.5","port":8765,"syncToken":"abc"}""")!!
        assertEquals("192.168.1.5", e.host); assertEquals(8765, e.port); assertEquals("abc", e.syncToken)
        assertEquals("http://192.168.1.5:8765", e.baseUrl())
    }
    @Test fun nullWhenMissingFields() {
        assertNull(parseSyncEndpoint("""{"host":"x","port":1}"""))      // no token
        assertNull(parseSyncEndpoint("""{"anthropicKey":"sk-x"}"""))    // a provisioning QR, not sync
        assertNull(parseSyncEndpoint("garbage"))
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncEndpointTest"`
Expected: FAIL (unresolved parseSyncEndpoint).

- [ ] **Step 4: Implement `SyncEndpoint.kt`**

```kotlin
package com.lorebox.android.data.sync

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull

@Serializable
data class SyncEndpoint(val host: String, val port: Int, val syncToken: String)

fun SyncEndpoint.baseUrl(): String = "http://$host:$port"

fun parseSyncEndpoint(qr: String): SyncEndpoint? = try {
    val obj = Json.parseToJsonElement(qr.trim()).jsonObject
    val host = obj["host"]?.jsonPrimitive?.contentOrNull
    val port = obj["port"]?.jsonPrimitive?.intOrNull
    val token = obj["syncToken"]?.jsonPrimitive?.contentOrNull
    if (host.isNullOrBlank() || port == null || token.isNullOrBlank()) null
    else SyncEndpoint(host, port, token)
} catch (e: Exception) { null }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncEndpointTest"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/com/lorebox/android/data/sync/SyncEndpoint.kt app/src/test/java/com/lorebox/android/data/sync/SyncEndpointTest.kt app/build.gradle.kts
git commit -m "feat(sync): SyncEndpoint QR payload model + parser"
```

---

### Task B2: KeyStore sync-endpoint accessors

**Files:**
- Modify: `app/src/main/java/com/lorebox/android/data/keys/KeyStore.kt`

**Interfaces:**
- Consumes: existing `str()`/`set()` helpers; `SyncEndpoint`.
- Produces on `KeyStore`: `fun saveSyncEndpoint(e: SyncEndpoint)` and `fun syncEndpoint(): SyncEndpoint?` (returns the stored endpoint, or null if none saved). Stored under keys `sync_host`, `sync_port`, `sync_token`.

- [ ] **Step 1: Implement** — add to `KeyStore` (it already has `private fun str(key)` and `set(key, value)`):

```kotlin
    fun saveSyncEndpoint(e: com.lorebox.android.data.sync.SyncEndpoint) {
        set("sync_host", e.host)
        set("sync_port", e.port.toString())
        set("sync_token", e.syncToken)
    }

    fun syncEndpoint(): com.lorebox.android.data.sync.SyncEndpoint? {
        val host = str("sync_host") ?: return null
        val port = str("sync_port")?.toIntOrNull() ?: return null
        val token = str("sync_token") ?: return null
        return com.lorebox.android.data.sync.SyncEndpoint(host, port, token)
    }
```

- [ ] **Step 2: Compile check**

Run: `./gradlew :app:assembleDebug`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/java/com/lorebox/android/data/keys/KeyStore.kt
git commit -m "feat(sync): persist sync endpoint in encrypted KeyStore"
```

---

### Task B3: Delete-with-images (ImageStore + CardRepository)

**Files:**
- Modify: `app/src/main/java/com/lorebox/android/data/image/ImageStore.kt`
- Modify: `app/src/main/java/com/lorebox/android/data/CardRepository.kt` (inject ImageStore; add deleteCardWithImages)
- Modify: `app/src/main/java/com/lorebox/android/LoreboxApp.kt` (pass imageStore to repository)
- Test: `app/src/test/java/com/lorebox/android/data/CardRepositoryDeleteTest.kt`

**Interfaces:**
- Produces:
  - `ImageStore.delete(path: String?)` — deletes the file at `path` if non-null and present (no-op otherwise); `ImageStore.read(path: String): ByteArray?` — file bytes or null.
  - `CardRepository(dao, identifier, valuator, imageStore)` — ImageStore added as the 4th constructor param.
  - `suspend fun CardRepository.deleteCardWithImages(card: CardEntity)` — deletes `card.frontScanPath` and `card.backScanPath` files via ImageStore, then `dao.delete(card.id)`.

- [ ] **Step 1: Add `delete`/`read` to `ImageStore.kt`**

```kotlin
    fun delete(path: String?) {
        if (path.isNullOrBlank()) return
        runCatching { java.io.File(path).delete() }
    }

    fun read(path: String): ByteArray? =
        runCatching { java.io.File(path).readBytes() }.getOrNull()
```

- [ ] **Step 2: Write the failing repository test** (uses the existing `FakeDao` pattern from Task 9; here we give it a tiny inline fake plus a fake ImageStore via an interface seam)

First, to make ImageStore fakeable, extract a minimal interface. Add to `ImageStore.kt` above the class:

```kotlin
interface ImageFiles {
    fun save(bytes: ByteArray, prefix: String): String
    fun delete(path: String?)
    fun read(path: String): ByteArray?
}
```
and change `class ImageStore(...)` to `class ImageStore(private val context: Context) : ImageFiles`. Keep the existing `downscaleJpeg` (not part of the interface).

Change `CardRepository`'s constructor type for imageStore to `ImageFiles`.

Test:
```kotlin
package com.lorebox.android.data
import com.lorebox.android.data.db.CardEntity
import com.lorebox.android.data.image.ImageFiles
import com.lorebox.android.data.identify.CardFields
import com.lorebox.android.data.identify.Identifier
import com.lorebox.android.data.value.Valuation
import com.lorebox.android.data.value.Valuator
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

private class RecordingImages : ImageFiles {
    val deleted = mutableListOf<String?>()
    override fun save(bytes: ByteArray, prefix: String) = "/x/$prefix.jpg"
    override fun delete(path: String?) { deleted.add(path) }
    override fun read(path: String): ByteArray? = null
}

class CardRepositoryDeleteTest {
    @Test fun deletesRowAndBothImages() = runTest {
        val dao = FakeDao()   // reuse the FakeDao from CardRepositoryTest (same package)
        val imgs = RecordingImages()
        val repo = CardRepository(dao, FakeIdentifier(null), FakeValuator(null), imgs)
        val id = dao.insert(CardEntity(name="X", frontScanPath="/x/f.jpg", backScanPath="/x/b.jpg"))
        repo.deleteCardWithImages(dao.cards.first { it.id == id })
        assertTrue("/x/f.jpg" in imgs.deleted)
        assertTrue("/x/b.jpg" in imgs.deleted)
        assertTrue(dao.cards.none { it.id == id })
    }
}
```
(If `FakeDao`/`FakeIdentifier`/`FakeValuator` are `private` in `CardRepositoryTest.kt`, change them to internal/top-level so this test in the same package can reuse them, or copy minimal fakes into this file.)

- [ ] **Step 3: Run test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests "*CardRepositoryDeleteTest"`
Expected: FAIL (constructor arity / deleteCardWithImages unresolved).

- [ ] **Step 4: Implement** — update `CardRepository`:

```kotlin
class CardRepository(
    private val dao: CardDao,
    private val identifier: Identifier,
    private val valuator: Valuator,
    private val imageStore: com.lorebox.android.data.image.ImageFiles,
) {
    // …existing methods unchanged…

    suspend fun deleteCardWithImages(card: CardEntity) {
        imageStore.delete(card.frontScanPath)
        imageStore.delete(card.backScanPath)
        dao.delete(card.id)
    }
}
```

and in `LoreboxApp.kt` pass the existing `imageStore`:

```kotlin
        repository = CardRepository(db.cardDao(), IdentifyService(keyStore), ValuationService(keyStore), imageStore)
```

- [ ] **Step 5: Run test + full unit suite**

Run: `./gradlew :app:testDebugUnitTest`
Expected: PASS (including the existing `CardRepositoryTest` — update its `CardRepository(...)` construction to pass a fake `ImageFiles` if it now fails to compile).

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/com/lorebox/android/data/image/ImageStore.kt app/src/main/java/com/lorebox/android/data/CardRepository.kt app/src/main/java/com/lorebox/android/LoreboxApp.kt app/src/test/java/com/lorebox/android/data/CardRepositoryDeleteTest.kt
git commit -m "feat(sync): delete card row + scan images together"
```

---

### Task B4: SyncClient (ping + pushCard)

**Files:**
- Create: `app/src/main/java/com/lorebox/android/data/sync/SyncModels.kt`
- Create: `app/src/main/java/com/lorebox/android/data/sync/SyncClient.kt`
- Test: `app/src/test/java/com/lorebox/android/data/sync/SyncClientTest.kt`

**Interfaces:**
- Consumes: `SyncEndpoint`, `baseUrl()`, OkHttp.
- Produces:
  - `SyncModels.kt`: `sealed interface CardSyncResult { data class Ack(val id: Long): CardSyncResult; data class Failed(val reason: String): CardSyncResult }`.
  - `fun buildCardJson(card: CardEntity, frontB64: String, backB64: String?, clientUid: String): String` — the exact request body (pure, testable).
  - `class SyncClient(private val client: OkHttpClient = OkHttpClient())`:
    - `suspend fun ping(e: SyncEndpoint): Boolean`
    - `suspend fun pushCard(e: SyncEndpoint, card: CardEntity, frontJpeg: ByteArray, backJpeg: ByteArray?, clientUid: String): CardSyncResult`

- [ ] **Step 1: Write the failing test (MockWebServer)**

```kotlin
package com.lorebox.android.data.sync
import com.lorebox.android.data.db.CardEntity
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class SyncClientTest {
    private lateinit var server: MockWebServer
    private lateinit var ep: SyncEndpoint
    @Before fun setUp() { server = MockWebServer(); server.start()
        ep = SyncEndpoint(server.hostName, server.port, "tok") }
    @After fun tearDown() = server.shutdown()

    @Test fun pingTrueOn200() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"app":"lorebox","proto":1}"""))
        assertTrue(SyncClient().ping(ep))
        val req = server.takeRequest()
        assertEquals("Bearer tok", req.getHeader("Authorization"))
        assertEquals("/sync/ping", req.path)
    }

    @Test fun pushReturnsAckId() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"id":42}"""))
        val res = SyncClient().pushCard(ep, CardEntity(id=1, name="X"), ByteArray(2), null, "uid1")
        assertEquals(CardSyncResult.Ack(42), res)
        val req = server.takeRequest()
        assertEquals("/sync/card", req.path)
        assertTrue(req.body.readUtf8().contains("\"client_uid\":\"uid1\""))
    }

    @Test fun pushFailsOn500() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(500).setBody("""{"error":"x"}"""))
        val res = SyncClient().pushCard(ep, CardEntity(id=1, name="X"), ByteArray(2), null, "uid2")
        assertTrue(res is CardSyncResult.Failed)
    }

    @Test fun buildJsonShape() {
        val json = buildCardJson(CardEntity(id=1, name="Servo", game="Magic: The Gathering",
            estimatedValue=1.49), "AAAA", null, "u9")
        assertTrue(json.contains("\"client_uid\":\"u9\""))
        assertTrue(json.contains("\"name\":\"Servo\""))
        assertTrue(json.contains("\"front_jpeg_b64\":\"AAAA\""))
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncClientTest"`
Expected: FAIL (unresolved SyncClient/buildCardJson/CardSyncResult).

- [ ] **Step 3: Implement `SyncModels.kt` and `SyncClient.kt`**

```kotlin
// SyncModels.kt
package com.lorebox.android.data.sync

sealed interface CardSyncResult {
    data class Ack(val id: Long) : CardSyncResult
    data class Failed(val reason: String) : CardSyncResult
}
```

```kotlin
// SyncClient.kt
package com.lorebox.android.data.sync

import com.lorebox.android.data.db.CardEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.Base64

private val JSON_MEDIA = "application/json".toMediaType()

fun buildCardJson(card: CardEntity, frontB64: String, backB64: String?, clientUid: String): String {
    val c = JSONObject()
        .put("name", card.name).put("set_name", card.setName).put("card_number", card.cardNumber)
        .put("rarity", card.rarity).put("game", card.game).put("year", card.year)
        .put("language", card.language).put("foil", card.foil)
        .put("condition_grade", card.conditionGrade).put("condition_score", card.conditionScore)
        .put("defects_json", card.defectsJson).put("estimated_value", card.estimatedValue)
        .put("purchase_price", card.purchasePrice).put("purchase_date", card.purchaseDate)
        .put("notes", card.notes).put("quantity", card.quantity)
    return JSONObject()
        .put("client_uid", clientUid).put("card", c)
        .put("front_jpeg_b64", frontB64)
        .put("back_jpeg_b64", backB64 ?: JSONObject.NULL)
        .toString()
}

class SyncClient(private val client: OkHttpClient = OkHttpClient()) {

    suspend fun ping(e: SyncEndpoint): Boolean = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("${e.baseUrl()}/sync/ping")
            .header("Authorization", "Bearer ${e.syncToken}").build()
        runCatching { client.newCall(req).execute().use { it.isSuccessful } }.getOrDefault(false)
    }

    suspend fun pushCard(e: SyncEndpoint, card: CardEntity, frontJpeg: ByteArray,
                         backJpeg: ByteArray?, clientUid: String): CardSyncResult =
        withContext(Dispatchers.IO) {
            val front = Base64.getEncoder().encodeToString(frontJpeg)
            val back = backJpeg?.let { Base64.getEncoder().encodeToString(it) }
            val body = buildCardJson(card, front, back, clientUid).toRequestBody(JSON_MEDIA)
            val req = Request.Builder().url("${e.baseUrl()}/sync/card")
                .header("Authorization", "Bearer ${e.syncToken}")
                .post(body).build()
            runCatching {
                client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) return@use CardSyncResult.Failed("HTTP ${resp.code}")
                    val id = Json.parseToJsonElement(resp.body!!.string())
                        .jsonObject["id"]?.jsonPrimitive?.longOrNull
                        ?: return@use CardSyncResult.Failed("no id in ack")
                    CardSyncResult.Ack(id)
                }
            }.getOrElse { CardSyncResult.Failed(it.message ?: "network error") }
        }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncClientTest"`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/com/lorebox/android/data/sync/SyncModels.kt app/src/main/java/com/lorebox/android/data/sync/SyncClient.kt app/src/test/java/com/lorebox/android/data/sync/SyncClientTest.kt
git commit -m "feat(sync): SyncClient ping + per-card push with JSON/base64"
```

---

### Task B5: Sync orchestration (SyncViewModel)

**Files:**
- Create: `app/src/main/java/com/lorebox/android/ui/sync/SyncViewModel.kt`
- Test: `app/src/test/java/com/lorebox/android/ui/sync/SyncViewModelTest.kt`

**Interfaces:**
- Consumes: `CardRepository` (`getById`, `deleteCardWithImages`), `ImageFiles.read`, `SyncClient`, `SyncEndpoint`, `KeyStore.syncEndpoint()/saveSyncEndpoint()`.
- Produces: `class SyncViewModel(repo, imageStore, client, keyStore)` with:
  - `data class SyncProgress(val total: Int, val done: Int, val failed: Int, val finished: Boolean, val needsScan: Boolean, val message: String)`
  - `val progress: StateFlow<SyncProgress>`
  - `fun onEndpointScanned(qr: String): Boolean` — parse + persist; returns false if not a valid sync QR.
  - `suspend fun sync(cardIds: List<Long>)` — ping stored endpoint (if none/unreachable, set `needsScan=true` and return); for each id: load card, read front/back bytes, `pushCard`; on `Ack` → `deleteCardWithImages` + done++; on `Failed` → failed++. Generates a fresh `clientUid` per card (UUID).

- [ ] **Step 1: Write the failing test** (fakes for repo/client/images)

```kotlin
package com.lorebox.android.ui.sync
import com.lorebox.android.data.db.CardEntity
import com.lorebox.android.data.sync.CardSyncResult
import com.lorebox.android.data.sync.SyncEndpoint
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class SyncViewModelTest {
    @Test fun pushesEachCardAndDeletesOnAck() = runTest {
        val deleted = mutableListOf<Long>()
        val repo = FakeSyncRepo(
            cards = mapOf(1L to CardEntity(id=1, name="A", frontScanPath="/a.jpg"),
                          2L to CardEntity(id=2, name="B", frontScanPath="/b.jpg")),
            onDelete = { deleted.add(it.id) })
        val client = FakeSyncClient(pingOk = true,
            results = mapOf(1L to CardSyncResult.Ack(11), 2L to CardSyncResult.Ack(22)))
        val vm = SyncViewModel(repo, FakeReadImages(), client,
            FakeKeys(SyncEndpoint("h", 1, "t")))
        vm.sync(listOf(1L, 2L))
        val p = vm.progress.value
        assertTrue(p.finished); assertEquals(2, p.done); assertEquals(0, p.failed)
        assertEquals(listOf(1L, 2L), deleted)
    }

    @Test fun failedCardIsNotDeleted() = runTest {
        val deleted = mutableListOf<Long>()
        val repo = FakeSyncRepo(mapOf(1L to CardEntity(id=1, name="A", frontScanPath="/a.jpg")),
            onDelete = { deleted.add(it.id) })
        val client = FakeSyncClient(true, mapOf(1L to CardSyncResult.Failed("boom")))
        val vm = SyncViewModel(repo, FakeReadImages(), client, FakeKeys(SyncEndpoint("h",1,"t")))
        vm.sync(listOf(1L))
        assertEquals(1, vm.progress.value.failed)
        assertTrue(deleted.isEmpty())
    }

    @Test fun noEndpointRequestsScan() = runTest {
        val vm = SyncViewModel(FakeSyncRepo(emptyMap(),{}), FakeReadImages(),
            FakeSyncClient(false, emptyMap()), FakeKeys(null))
        vm.sync(listOf(1L))
        assertTrue(vm.progress.value.needsScan)
    }
}
```

Define the fakes (same test file or a shared test util). They implement the **seam interfaces** the ViewModel depends on — to keep the VM testable, depend on narrow interfaces:

```kotlin
// In SyncViewModel.kt, declare these seams:
interface SyncRepo {
    suspend fun getById(id: Long): CardEntity?
    suspend fun deleteCardWithImages(card: CardEntity)
}
interface SyncTransport {
    suspend fun ping(e: SyncEndpoint): Boolean
    suspend fun pushCard(e: SyncEndpoint, card: CardEntity, front: ByteArray, back: ByteArray?, uid: String): CardSyncResult
}
interface EndpointStore { fun current(): SyncEndpoint?; fun save(e: SyncEndpoint) }
interface ImageReader { fun read(path: String): ByteArray? }
```
The fakes implement these; `CardRepository`, `SyncClient`, `KeyStore`, and `ImageStore` get thin adapters (or implement them directly) when wired in B6.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncViewModelTest"`
Expected: FAIL (unresolved SyncViewModel and seams).

- [ ] **Step 3: Implement `SyncViewModel.kt`**

```kotlin
package com.lorebox.android.ui.sync

import androidx.lifecycle.ViewModel
import com.lorebox.android.data.db.CardEntity
import com.lorebox.android.data.sync.CardSyncResult
import com.lorebox.android.data.sync.SyncEndpoint
import com.lorebox.android.data.sync.parseSyncEndpoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.UUID

interface SyncRepo {
    suspend fun getById(id: Long): CardEntity?
    suspend fun deleteCardWithImages(card: CardEntity)
}
interface SyncTransport {
    suspend fun ping(e: SyncEndpoint): Boolean
    suspend fun pushCard(e: SyncEndpoint, card: CardEntity, front: ByteArray, back: ByteArray?, uid: String): CardSyncResult
}
interface EndpointStore { fun current(): SyncEndpoint?; fun save(e: SyncEndpoint) }
interface ImageReader { fun read(path: String): ByteArray? }

data class SyncProgress(
    val total: Int = 0, val done: Int = 0, val failed: Int = 0,
    val finished: Boolean = false, val needsScan: Boolean = false, val message: String = "",
)

class SyncViewModel(
    private val repo: SyncRepo,
    private val images: ImageReader,
    private val transport: SyncTransport,
    private val endpoints: EndpointStore,
) : ViewModel() {

    private val _progress = MutableStateFlow(SyncProgress())
    val progress: StateFlow<SyncProgress> = _progress

    fun onEndpointScanned(qr: String): Boolean {
        val e = parseSyncEndpoint(qr) ?: return false
        endpoints.save(e)
        _progress.value = _progress.value.copy(needsScan = false, message = "Connected")
        return true
    }

    suspend fun sync(cardIds: List<Long>) {
        val e = endpoints.current()
        if (e == null || !transport.ping(e)) {
            _progress.value = SyncProgress(needsScan = true, message = "Scan the desktop QR to connect")
            return
        }
        var done = 0; var failed = 0
        _progress.value = SyncProgress(total = cardIds.size, message = "Syncing…")
        for (id in cardIds) {
            val card = repo.getById(id)
            val front = card?.frontScanPath?.let { images.read(it) }
            if (card == null || front == null) { failed++; _progress.value = _progress.value.copy(failed = failed); continue }
            val back = card.backScanPath?.let { images.read(it) }
            when (transport.pushCard(e, card, front, back, UUID.randomUUID().toString())) {
                is CardSyncResult.Ack -> { repo.deleteCardWithImages(card); done++ }
                is CardSyncResult.Failed -> failed++
            }
            _progress.value = _progress.value.copy(done = done, failed = failed)
        }
        _progress.value = _progress.value.copy(done = done, failed = failed, finished = true,
            message = "Done — $done synced, $failed failed")
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./gradlew :app:testDebugUnitTest --tests "*SyncViewModelTest"`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/src/main/java/com/lorebox/android/ui/sync/SyncViewModel.kt app/src/test/java/com/lorebox/android/ui/sync/SyncViewModelTest.kt
git commit -m "feat(sync): SyncViewModel push orchestration with per-card ack/delete"
```

---

### Task B6: Collection multi-select + Sync flow UI

**Files:**
- Modify: `app/src/main/java/com/lorebox/android/ui/collection/CollectionScreen.kt` (+ its ViewModel) — selection mode + "Sync to PC".
- Modify: `app/src/main/java/com/lorebox/android/ui/nav/LoreboxNav.kt` — wire a sync screen/flow and adapters.
- Create: `app/src/main/java/com/lorebox/android/ui/sync/SyncScreen.kt` — progress UI + ZXing scan launch on `needsScan`.
- Create thin adapters so real classes satisfy the B5 seams.

**Interfaces:**
- Consumes: `SyncViewModel`, `CardRepository`, `KeyStore`, `ImageStore`, `SyncClient`, the existing ZXing `ScanContract` (used in `PairScreen`).
- Produces: a selectable collection list (long-press or a "Select" toggle enters multi-select; tapping toggles a checkbox; a "Sync (N)" button starts the flow), a `SyncScreen` that shows progress and, when `needsScan` is true, launches the ZXing scanner and feeds the result to `vm.onEndpointScanned(...)` then retries.

- [ ] **Step 1: Add adapters** in `LoreboxNav.kt` (or a small `SyncWiring.kt`) so real components satisfy the seams:

```kotlin
// adapters
class RepoSyncAdapter(private val repo: com.lorebox.android.data.CardRepository) : com.lorebox.android.ui.sync.SyncRepo {
    override suspend fun getById(id: Long) = repo.getById(id)
    override suspend fun deleteCardWithImages(card: com.lorebox.android.data.db.CardEntity) = repo.deleteCardWithImages(card)
}
class ClientSyncAdapter(private val c: com.lorebox.android.data.sync.SyncClient) : com.lorebox.android.ui.sync.SyncTransport {
    override suspend fun ping(e: com.lorebox.android.data.sync.SyncEndpoint) = c.ping(e)
    override suspend fun pushCard(e: com.lorebox.android.data.sync.SyncEndpoint, card: com.lorebox.android.data.db.CardEntity, front: ByteArray, back: ByteArray?, uid: String) =
        c.pushCard(e, card, front, back, uid)
}
class KeysEndpointAdapter(private val k: com.lorebox.android.data.keys.KeyStore) : com.lorebox.android.ui.sync.EndpointStore {
    override fun current() = k.syncEndpoint()
    override fun save(e: com.lorebox.android.data.sync.SyncEndpoint) = k.saveSyncEndpoint(e)
}
class ImagesReadAdapter(private val s: com.lorebox.android.data.image.ImageStore) : com.lorebox.android.ui.sync.ImageReader {
    override fun read(path: String) = s.read(path)
}
```

- [ ] **Step 2: Add multi-select to the collection** — in `CollectionViewModel`, add a selection set and a toggle; in `CollectionScreen`, render a checkbox per row when in select mode and a "Sync (N)" button in the top bar that navigates to `sync` passing the selected ids. (Pass ids via a shared holder `object SyncSelection { var ids: List<Long> = emptyList() }` to avoid long nav-arg lists, mirroring the existing `CaptureBuffer` pattern.)

```kotlin
// CollectionViewModel additions
private val _selected = MutableStateFlow<Set<Long>>(emptySet())
val selected: StateFlow<Set<Long>> = _selected
val selectMode = MutableStateFlow(false)
fun toggleSelectMode() { selectMode.value = !selectMode.value; if (!selectMode.value) _selected.value = emptySet() }
fun toggle(id: Long) { _selected.value = _selected.value.let { if (id in it) it - id else it + id } }
```

```kotlin
// SyncSelection.kt (holder)
package com.lorebox.android.ui.sync
object SyncSelection { var ids: List<Long> = emptyList() }
```

In `CollectionScreen` top bar: a "Select"/"Cancel" action toggles select mode; when in select mode show "Sync (${selected.size})" that sets `SyncSelection.ids = selected.toList()` and `onSync()` (nav to "sync"). Rows show a leading `Checkbox(checked = id in selected, onCheckedChange = { vm.toggle(id) })` when in select mode, else behave as before.

- [ ] **Step 3: Create `SyncScreen.kt`**

```kotlin
package com.lorebox.android.ui.sync

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncScreen(vm: SyncViewModel, cardIds: List<Long>, onDone: () -> Unit) {
    val p by vm.progress.collectAsState()
    val scope = rememberCoroutineScope()
    val scanLauncher = rememberLauncherForActivityResult(ScanContract()) { result ->
        val ok = result.contents?.let { vm.onEndpointScanned(it) } == true
        if (ok) scope.launch { vm.sync(cardIds) }
    }
    LaunchedEffect(Unit) { vm.sync(cardIds) }
    LaunchedEffect(p.needsScan) {
        if (p.needsScan) scanLauncher.launch(ScanOptions().setOrientationLocked(false)
            .setPrompt("Scan the desktop 'Receive from phone' QR").setBeepEnabled(false))
    }
    Scaffold(topBar = { TopAppBar(title = { Text("Sync to PC") },
        navigationIcon = { TextButton(onClick = onDone) { Text("Close") } }) }) { pad ->
        Column(Modifier.padding(pad).padding(24.dp)) {
            Text(p.message.ifBlank { "Preparing…" })
            Spacer(Modifier.height(12.dp))
            if (p.total > 0) LinearProgressIndicator(progress = { (p.done + p.failed).toFloat() / p.total })
            Spacer(Modifier.height(12.dp))
            Text("Synced: ${p.done}   Failed: ${p.failed}   Total: ${p.total}")
            if (p.finished) { Spacer(Modifier.height(16.dp)); Button(onClick = onDone) { Text("Done") } }
        }
    }
}
```

- [ ] **Step 4: Wire the `sync` route** in `LoreboxNav.kt`, constructing the VM from adapters (use the `viewModelFactory` pattern already in this file):

```kotlin
composable("sync") {
    val vm: com.lorebox.android.ui.sync.SyncViewModel = viewModel(factory = viewModelFactory {
        initializer {
            com.lorebox.android.ui.sync.SyncViewModel(
                RepoSyncAdapter(app.repository),
                ImagesReadAdapter(app.imageStore),
                ClientSyncAdapter(com.lorebox.android.data.sync.SyncClient()),
                KeysEndpointAdapter(app.keyStore),
            )
        }
    })
    com.lorebox.android.ui.sync.SyncScreen(vm,
        cardIds = com.lorebox.android.ui.sync.SyncSelection.ids,
        onDone = { nav.popBackStack("collection", inclusive = false) })
}
```
and make the collection route's new "Sync (N)" action `onSync = { nav.navigate("sync") }`.

- [ ] **Step 5: Build, install, and end-to-end verify on the device**

Run: `./gradlew :app:installDebug` (device serial `R5CX5270L3D`).
Manual E2E: on the **PC**, open **File → Receive from phone…** (a QR appears). On the **phone**, scan/capture a card so the collection has ≥1 card, tap **Select**, check it, tap **Sync (1)**, scan the desktop QR. Expect: the desktop log shows "received <name>", the card appears in the desktop collection (run the desktop app and check the Collection tab), and the card **disappears from the phone**. Verify the scan image is present in `%APPDATA%/Lorebox/scans/cards/`.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/com/lorebox/android/ui/
git commit -m "feat(sync): multi-select collection + Sync-to-PC flow with QR connect"
```

---

## Self-Review

**Spec coverage:**
- Phone→PC one-way, user-selected, per-card ack, delete-on-ack → B5 (`sync`), B3 (`deleteCardWithImages`), B6 (UI). Partial-failure keeps un-acked cards → B5 (`Failed` path, no delete).
- QR connect reusing pairing; phone remembers host; re-scan on failure → B1 (parse), B2 (persist), B5 (`ping` → `needsScan`), B6 (ZXing relaunch).
- Bearer token over plain LAN HTTP → A3 (auth, `hmac.compare_digest`), B4 (Bearer header).
- Server only while dialog open → A4 (`start` on open, `closeEvent` → `stop`).
- PC merges via `add_card(merge_duplicates=True)`; images to scans dir → A3 (`ingest_card`).
- Idempotent duplicate delivery via `client_uid` → A3 (`seen`), B5 (fresh UUID per card per attempt — note: a re-attempt of the *same* card after a lost ack uses a new UUID, so the desktop's `seen` set guards within a run; cross-run dup is out of scope and acceptable per spec's edge note).
- Sync token in config; LAN IP; QR payload `{host,port,syncToken}` → A2, A1, A4.
- Stdlib only (no Flask) → A3 uses `http.server`. Testing approaches per spec → A1–A3, B1–B5 unit tests; B6 manual E2E.

**Placeholder scan:** none. The one conditional ("if MainWindow's DB attribute isn't `self.db`") is an explicit lookup instruction with a concrete fallback, not a TODO.

**Type consistency:** `SyncEndpoint(host,port,syncToken)` + `baseUrl()` consistent across B1/B2/B4/B5. `CardSyncResult.Ack(id: Long)`/`Failed(reason)` consistent B4/B5. `ingest_card(db, scans_dir, payload, seen)` and `SyncServer(db, scans_dir, token, host, port, on_card)` consistent A3/A4. `deleteCardWithImages(card: CardEntity)` consistent B3/B5/B6. `ImageFiles`/`ImageReader` seams consistent B3/B5/B6. Protocol strings (`/sync/ping`, `/sync/card`, `Bearer`, `{"app":"lorebox"}`, `{"id"}`, `client_uid`, `front_jpeg_b64`) match between A3 and B4.

**Cross-repo note:** Phase A commits land in `CardTCGApp`; Phase B commits land in `LoreBox-Mobile`. Keep a copy of this plan's protocol section in both repos' docs (already in the design spec).
