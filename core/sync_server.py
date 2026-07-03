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
