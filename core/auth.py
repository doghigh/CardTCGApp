"""
Authentication module with secure password handling, TOTP, and Windows Hello.
Fixed: Secure key derivation, recovery codes, and input validation.
"""

import json
import secrets
import base64
import os
import hashlib
from pathlib import Path
from typing import Optional, List

import pyotp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QCheckBox, QMessageBox, QHBoxLayout)
from PyQt6.QtCore import Qt

# Global APP_DIR
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
APP_DIR.mkdir(parents=True, exist_ok=True)


class LoginDialog(QDialog):
    """Login dialog with password, TOTP, Windows Hello, and recovery."""

    def __init__(self, auth_manager, hello_auth, parent=None):
        super().__init__(parent)
        self.auth = auth_manager
        self.hello = hello_auth
        self.setWindowTitle("Login - Trading Card Manager")
        self.resize(420, 320)
        self._build_ui()
        self._attempt_hello()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        QLabel("<h2>Welcome back</h2>", self)
        layout.addWidget(QLabel("<h2>Welcome back</h2>"))

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Enter master password")
        layout.addWidget(self.pass_edit)

        self.totp_edit = QLineEdit()
        self.totp_edit.setPlaceholderText("TOTP code (if enabled)")
        layout.addWidget(self.totp_edit)

        self.remember = QCheckBox("Remember this device")
        layout.addWidget(self.remember)

        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self._try_login)
        self.login_btn.setDefault(True)
        btn_layout.addWidget(self.login_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.recovery_btn = QPushButton("Use Recovery Code")
        self.recovery_btn.clicked.connect(self._recovery_login)
        layout.addWidget(self.recovery_btn)

    def _attempt_hello(self):
        if self.hello.is_available():
            if self.hello.request_biometric_login():
                self.accept()
                return

    def _try_login(self):
        pw = self.pass_edit.text().strip()
        totp = self.totp_edit.text().strip()

        if self.auth.check_password(pw):
            if totp and not self.auth.verify_totp(totp):
                QMessageBox.warning(self, "Invalid", "TOTP code invalid.")
                return
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid password.")

    def _recovery_login(self):
        code, ok = QInputDialog.getText(self, "Recovery", "Enter recovery code:")
        if ok and code and self.auth.verify_recovery_code(code):
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid", "Recovery code invalid or used.")


from PyQt6.QtWidgets import QInputDialog  # late import for recovery
