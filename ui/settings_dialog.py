"""
Settings dialog — lets each user enter their own API keys.

Keys are stored encrypted (see core.config) and applied immediately on save.
Includes a "Test" button for each service so users get instant feedback that
their key works before they start scanning.
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QFormLayout, QDialogButtonBox, QCheckBox, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from core.config import config


class _KeyTestWorker(QThread):
    """Validates a credential in the background so the UI stays responsive."""
    done = pyqtSignal(bool, str)   # (ok, message)

    def __init__(self, service: str, values: dict):
        super().__init__()
        self.service = service
        self.values = values

    def run(self):
        try:
            if self.service == "anthropic":
                ok, msg = self._test_anthropic()
            else:
                ok, msg = self._test_ebay()
        except Exception as exc:
            ok, msg = False, f"Error: {exc}"
        self.done.emit(ok, msg)

    def _test_anthropic(self):
        key = self.values.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return False, "No key entered."
        try:
            import anthropic
        except ImportError:
            return False, "anthropic package not installed."
        client = anthropic.Anthropic(api_key=key)
        # Cheapest possible call — 1 token completion
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, "✓ Anthropic key is valid."

    def _test_ebay(self):
        import base64
        import requests
        app_id  = self.values.get("EBAY_APP_ID", "").strip()
        cert_id = self.values.get("EBAY_CERT_ID", "").strip()
        if not app_id or not cert_id:
            return False, "Enter both App ID and Cert ID."
        sandbox = "SBX" in app_id.upper()
        url = ("https://api.sandbox.ebay.com/identity/v1/oauth2/token"
               if sandbox else
               "https://api.ebay.com/identity/v1/oauth2/token")
        creds = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
        r = requests.post(
            url,
            headers={"Authorization": f"Basic {creds}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials",
                  "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=15,
        )
        if r.status_code == 200:
            env = "sandbox" if sandbox else "production"
            return True, f"✓ eBay keys valid ({env})."
        return False, f"eBay rejected the keys (HTTP {r.status_code})."


class SettingsDialog(QDialog):
    """Edit and test user-supplied API keys."""

    ANTHROPIC_HELP = "https://console.anthropic.com/settings/keys"
    EBAY_HELP      = "https://developer.ebay.com/my/keys"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — API Keys")
        self.setMinimumWidth(620)
        self._worker: Optional[_KeyTestWorker] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        intro = QLabel(
            "Enter your own API keys below. They're stored encrypted on this "
            "computer and never shared. You only pay your providers for what "
            "you use (Anthropic card scanning is ~$0.006 per card; eBay is free)."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b8fa8;")
        layout.addWidget(intro)

        # ── Anthropic ────────────────────────────────────────────────────────
        anthropic_box = QGroupBox("Card Identification — Anthropic (Claude)")
        a_form = QFormLayout(anthropic_box)
        self.anthropic_edit = self._secret_field()
        self.anthropic_edit.setText(config.get("ANTHROPIC_API_KEY"))
        a_form.addRow("API Key:", self.anthropic_edit)

        a_actions = QHBoxLayout()
        self.anthropic_status = QLabel("")
        self.anthropic_status.setStyleSheet("font-size: 12px;")
        get_a = QPushButton("Get a key ↗")
        get_a.setFlat(True)
        get_a.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.ANTHROPIC_HELP)))
        test_a = QPushButton("Test")
        test_a.clicked.connect(self._test_anthropic)
        a_actions.addWidget(self.anthropic_status, 1)
        a_actions.addWidget(get_a)
        a_actions.addWidget(test_a)
        a_form.addRow("", self._wrap(a_actions))
        layout.addWidget(anthropic_box)

        # ── eBay ──────────────────────────────────────────────────────────────
        ebay_box = QGroupBox("Valuation — eBay (optional)")
        e_form = QFormLayout(ebay_box)
        self.ebay_app_edit = self._secret_field()
        self.ebay_app_edit.setText(config.get("EBAY_APP_ID"))
        self.ebay_cert_edit = self._secret_field()
        self.ebay_cert_edit.setText(config.get("EBAY_CERT_ID"))
        e_form.addRow("App ID:", self.ebay_app_edit)
        e_form.addRow("Cert ID:", self.ebay_cert_edit)

        e_actions = QHBoxLayout()
        self.ebay_status = QLabel("")
        self.ebay_status.setStyleSheet("font-size: 12px;")
        get_e = QPushButton("Get keys ↗")
        get_e.setFlat(True)
        get_e.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.EBAY_HELP)))
        test_e = QPushButton("Test")
        test_e.clicked.connect(self._test_ebay)
        e_actions.addWidget(self.ebay_status, 1)
        e_actions.addWidget(get_e)
        e_actions.addWidget(test_e)
        e_form.addRow("", self._wrap(e_actions))

        note = QLabel("Without eBay keys the app still identifies and grades "
                      "cards; valuation falls back to PriceCharting.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b8fa8; font-size: 11px;")
        e_form.addRow("", note)
        layout.addWidget(ebay_box)

        # ── Save / Cancel ─────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _secret_field(self) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setMinimumWidth(360)
        # Show/hide toggle via the line edit's trailing action
        action = edit.addAction(self.style().standardIcon(
            self.style().StandardPixmap.SP_DialogYesButton),
            QLineEdit.ActionPosition.TrailingPosition)
        action.setToolTip("Show / hide")

        def toggle():
            edit.setEchoMode(
                QLineEdit.EchoMode.Normal
                if edit.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password
            )
        action.triggered.connect(toggle)
        return edit

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _current_values(self) -> dict:
        return {
            "ANTHROPIC_API_KEY": self.anthropic_edit.text().strip(),
            "EBAY_APP_ID":       self.ebay_app_edit.text().strip(),
            "EBAY_CERT_ID":      self.ebay_cert_edit.text().strip(),
        }

    # ── test buttons ────────────────────────────────────────────────────────

    def _test_anthropic(self):
        self.anthropic_status.setText("Testing…")
        self.anthropic_status.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        self._run_test("anthropic", self.anthropic_status)

    def _test_ebay(self):
        self.ebay_status.setText("Testing…")
        self.ebay_status.setStyleSheet("color: #8b8fa8; font-size: 12px;")
        self._run_test("ebay", self.ebay_status)

    def _run_test(self, service: str, status_label: QLabel):
        if self._worker and self._worker.isRunning():
            return
        self._worker = _KeyTestWorker(service, self._current_values())
        self._worker.done.connect(
            lambda ok, msg: self._show_test_result(status_label, ok, msg)
        )
        self._worker.start()

    @staticmethod
    def _show_test_result(label: QLabel, ok: bool, msg: str):
        color = "#43b581" if ok else "#ed4245"
        label.setStyleSheet(f"color: {color}; font-size: 12px;")
        label.setText(msg)

    # ── save ────────────────────────────────────────────────────────────────

    def _save(self):
        config.save(self._current_values())
        self.accept()
