"""Streamlined 'add your own Anthropic key' dialog.

Shown when the free trial is used up (or at capacity). Three actions:
deep-link to the console keys page, paste-and-validate inline, or defer.
"""
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)

from core.config import config
from core.key_validation import validate_anthropic_key

CONSOLE_KEYS_URL = "https://console.anthropic.com/settings/keys"

_HEADLINES = {
    'trial_exhausted': "You've used your 10 free card identifications.",
    'trial_capacity':  "The free trial is at capacity right now.",
    'trial_unavailable': "The free trial service is temporarily unavailable.",
    'first_run': "Add an Anthropic key to auto-identify your cards.",
}


class KeySetupDialog(QDialog):
    def __init__(self, parent=None, reason: str = 'trial_exhausted'):
        super().__init__(parent)
        self.setWindowTitle("Add your Anthropic key")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 22, 22, 22)
        v.setSpacing(12)

        headline = _HEADLINES.get(reason, _HEADLINES['trial_exhausted'])
        msg = QLabel(
            f"<b>{headline}</b><br><br>"
            "To keep scanning, add your own free Anthropic key — it's about "
            "$0.006 per card. Once added, scanning goes directly to Anthropic; "
            "nothing passes through us."
        )
        msg.setWordWrap(True)
        v.addWidget(msg)

        get_btn = QPushButton("Get a key (opens browser)…")
        get_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CONSOLE_KEYS_URL)))
        v.addWidget(get_btn)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Paste your API key here")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        v.addWidget(self.key_edit)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        row = QHBoxLayout()
        later = QPushButton("Maybe later")
        later.clicked.connect(self.reject)
        row.addWidget(later)
        row.addStretch()
        self.save_btn = QPushButton("Validate & Save")
        self.save_btn.setProperty("primary", True)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._validate_and_save)
        row.addWidget(self.save_btn)
        v.addLayout(row)

    def _validate_and_save(self):
        self.save_btn.setEnabled(False)
        self.status.setText("Checking…")
        # Process the label update before the (blocking) network call.
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        key = self.key_edit.text()
        ok, message = validate_anthropic_key(key)
        if ok:
            try:
                config.save({"ANTHROPIC_API_KEY": key.strip()})
            except Exception as exc:  # noqa: BLE001 — surface, don't crash the dialog
                self.status.setText(f"⚠ Could not save the key: {exc}")
                self.save_btn.setEnabled(True)
                return
            self.accept()
            return
        self.status.setText(f"⚠ {message}")
        self.save_btn.setEnabled(True)
