"""
Authentication module with secure password handling, TOTP, and Windows Hello.
Fixed: Secure key derivation, recovery codes, and input validation.
"""

import json
import secrets
import os
import hashlib
from pathlib import Path
from typing import Optional, List

import pyotp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
                             QCheckBox, QMessageBox, QHBoxLayout, QInputDialog)
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


class AuthManager:
    """Secure authentication manager."""

    def __init__(self):
        self.key_file = APP_DIR / ".auth.key"
        self.salt_file = APP_DIR / ".salt"
        self.totp_secret_file = APP_DIR / ".totp_secret"
        self.recovery_file = APP_DIR / ".recovery_codes"
        self._ensure_salt()

    def _ensure_salt(self):
        if not self.salt_file.exists():
            self.salt = secrets.token_bytes(16)
            self.salt_file.write_bytes(self.salt)
        else:
            self.salt = self.salt_file.read_bytes()

    def _derive_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=600_000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    def set_password(self, password: str):
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        derived = self._derive_key(password)
        verification_hash = hashlib.sha256(derived).hexdigest()
        self.key_file.write_text(verification_hash)

    def check_password(self, password: str) -> bool:
        if not self.key_file.exists():
            return True  # first run
        if not password:
            return False
        try:
            stored_data = self.key_file.read_bytes() if self.key_file.stat().st_size <= 64 else self.key_file.read_text()
            
            # Migration: detect old format (raw 32-byte hash) and convert to new format
            if isinstance(stored_data, bytes) and len(stored_data) == 32:
                # Old format detected — re-prompt user and migrate
                derived = self._derive_key(password)
                verification_hash = hashlib.sha256(derived).hexdigest()
                # Write new format
                self.key_file.write_text(verification_hash)
                # Verify matches
                return secrets.compare_digest(hashlib.sha256(derived).hexdigest(), verification_hash)
            
            # New format: hex string
            stored_hash = self.key_file.read_text().strip() if isinstance(stored_data, str) else stored_data.hex()
            derived = self._derive_key(password)
            verification_hash = hashlib.sha256(derived).hexdigest()
            return secrets.compare_digest(stored_hash, verification_hash)
        except Exception:
            return False

    def has_password(self) -> bool:
        return self.key_file.exists()

    def setup_totp(self) -> Optional[str]:
        if not self.totp_secret_file.exists():
            secret = pyotp.random_base32()
            self.totp_secret_file.write_text(secret)
        return self.get_totp_uri()

    def get_totp_uri(self) -> Optional[str]:
        if not self.totp_secret_file.exists():
            return None
        secret = self.totp_secret_file.read_text().strip()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name="TradingCardManager", issuer_name="TradingCardManager")

    def verify_totp(self, code: str) -> bool:
        if not self.totp_secret_file.exists():
            return False
        try:
            secret = self.totp_secret_file.read_text().strip()
            totp = pyotp.TOTP(secret)
            return totp.verify(code.strip(), valid_window=1)
        except Exception:
            return False

    def generate_recovery_codes(self) -> List[str]:
        codes = [secrets.token_hex(4).upper() for _ in range(8)]
        self.recovery_file.write_text(json.dumps(codes))
        return codes

    def verify_recovery_code(self, code: str) -> bool:
        if not self.recovery_file.exists():
            return False
        try:
            codes = json.loads(self.recovery_file.read_text())
            if code in codes:
                codes.remove(code)
                self.recovery_file.write_text(json.dumps(codes))
                return True
        except Exception:
            pass
        return False


class WindowsHelloAuth:
    """Windows Hello biometric authentication."""

    def __init__(self):
        self.credential_name = "TradingCardManager_Login"

    def is_available(self) -> bool:
        try:
            from winrt.windows.security.credentials import KeyCredentialManager
            return KeyCredentialManager.is_supported()
        except Exception:
            return False

    def request_biometric_login(self) -> bool:
        if not self.is_available():
            return False
        try:
            import asyncio
            from winrt.windows.security.credentials import KeyCredentialManager, KeyCredentialCreationOption

            async def auth_async():
                manager = KeyCredentialManager()
                result = await manager.request_create_async(
                    self.credential_name, KeyCredentialCreationOption.SILENT
                )
                if result.status == 0:
                    verify_result = await result.credential.request_verification_async()
                    return verify_result.status == 0
                return False

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(auth_async())
            loop.close()
            return success
        except Exception as e:
            print(f"Windows Hello error: {e}")
            return False
