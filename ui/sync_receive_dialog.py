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
