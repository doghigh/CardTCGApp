"""Pair phone dialog — renders a QR code that provisions the Android app's keys.

The QR encodes a small JSON payload the LoreBox Android app scans on first run.
It is shown on the user's own PC and scanned by their own phone — keys never
transit a network. See docs/superpowers/specs/2026-06-22-lorebox-android-v1-design.md.
"""

import io
import json
import qrcode
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout

from core.config import config


class PairPhoneDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pair phone")
        layout = QVBoxLayout(self)

        info = QLabel(
            "Scan this code from the LoreBox Android app\n"
            "(Settings → Pair with PC) to copy your API keys to the phone.\n"
            "Keep this screen private — it contains your keys."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        payload = json.dumps(self._payload())
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")

        qr_label = QLabel()
        qr_label.setPixmap(pix)
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(qr_label)

    @staticmethod
    def _payload() -> dict:
        return {
            "anthropicKey": config.get("ANTHROPIC_API_KEY") or "",
            "ebayAppId": config.get("EBAY_APP_ID") or "",
            "ebayCertId": config.get("EBAY_CERT_ID") or "",
        }
