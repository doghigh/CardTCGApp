"""
Authentication module — password, TOTP, Windows Hello, recovery codes.

Security properties:
  - PBKDF2-SHA256 with 600,000 iterations for password key derivation
  - Fernet (AES-128-CBC + HMAC-SHA256) for TOTP secret at rest
  - Recovery codes stored as SHA-256 hashes (one-time use)
  - Brute-force lockout: 5 attempts → exponential backoff (30s … 5min)
  - Timing-safe comparison via secrets.compare_digest
"""

import base64
import json
import logging
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QMessageBox, QHBoxLayout, QInputDialog,
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

from core.paths import APP_DIR


# ── Custom exceptions ────────────────────────────────────────────────────────

class AuthLockedError(Exception):
    """Raised when login is temporarily locked after too many failed attempts."""


# ── Login dialog ─────────────────────────────────────────────────────────────

class LoginDialog(QDialog):
    """Login dialog: password + optional TOTP, Windows Hello, recovery."""

    def __init__(self, auth_manager, hello_auth, parent=None):
        super().__init__(parent)
        self.auth  = auth_manager
        self.hello = hello_auth
        self.setWindowTitle("Login — Lorebox")
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

        btn_row = QHBoxLayout()
        self.login_btn = QPushButton("Login")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._try_login)
        btn_row.addWidget(self.login_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        recovery_btn = QPushButton("Use Recovery Code")
        recovery_btn.clicked.connect(self._recovery_login)
        layout.addWidget(recovery_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ed4245; font-size: 12px;")
        layout.addWidget(self.status_label)

    def _attempt_hello(self):
        if self.hello.is_available():
            if self.hello.request_biometric_login():
                self.accept()

    def _try_login(self):
        pw   = self.pass_edit.text()   # do NOT strip — spaces are valid in passwords
        totp = self.totp_edit.text().strip()

        try:
            ok = self.auth.check_password(pw)
        except AuthLockedError as exc:
            self.status_label.setText(str(exc))
            self.login_btn.setEnabled(False)
            return

        if ok:
            if totp and not self.auth.verify_totp(totp):
                self.status_label.setText("Invalid TOTP code.")
                return
            self.accept()
        else:
            remaining = self.auth.attempts_remaining()
            if remaining > 0:
                self.status_label.setText(
                    f"Incorrect password. {remaining} attempt(s) remaining."
                )
            else:
                self.status_label.setText("Account locked — too many failed attempts.")
                self.login_btn.setEnabled(False)

    def _recovery_login(self):
        code, ok = QInputDialog.getText(self, "Recovery", "Enter recovery code:")
        if ok and code and self.auth.verify_recovery_code(code):
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid", "Recovery code invalid or already used.")


# ── Auth manager ─────────────────────────────────────────────────────────────

class AuthManager:
    """Secure authentication: password + optional TOTP + recovery codes."""

    MAX_ATTEMPTS  = 5
    BASE_LOCKOUT  = 30   # seconds for first lockout
    MAX_LOCKOUT   = 300  # cap at 5 minutes

    def __init__(self):
        self.key_file          = APP_DIR / ".auth.key"
        self.salt_file         = APP_DIR / ".salt"
        self.totp_secret_file  = APP_DIR / ".totp_secret"
        self.recovery_file     = APP_DIR / ".recovery_codes"
        self.lockout_file      = APP_DIR / ".auth.lockout"

        # Session key is in-memory only and never persisted.
        self._session_key: Optional[bytes] = None

        # Brute-force state IS persisted (see _load_lockout_state) so a restart
        # cannot reset the counter and bypass the lockout.
        self._failed_attempts: int = 0          # failures in the current window
        self._lockout_count: int = 0            # lockouts so far (escalates backoff)
        self._lockout_until: Optional[datetime] = None

        self._ensure_salt()
        self._load_lockout_state()

    # ── Salt / key derivation ────────────────────────────────────────────────

    def _ensure_salt(self):
        if not self.salt_file.exists():
            self.salt = secrets.token_bytes(32)   # 256-bit salt
            self.salt_file.write_bytes(self.salt)
        else:
            self.salt = self.salt_file.read_bytes()

    def _derive_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=600_000,
            backend=default_backend(),
        )
        return kdf.derive(password.encode("utf-8"))

    def _get_fernet(self) -> Optional[Fernet]:
        """Return a Fernet cipher using the current session key."""
        if not self._session_key:
            return None
        return Fernet(base64.urlsafe_b64encode(self._session_key))

    # ── Password ─────────────────────────────────────────────────────────────

    def set_password(self, password: str):
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        derived = self._derive_key(password)
        self.key_file.write_text(hashlib.sha256(derived).hexdigest())
        self._session_key = derived
        logger.info("Password set successfully.")

    def check_password(self, password: str) -> bool:
        """
        Verify the password.

        Raises AuthLockedError if the account is temporarily locked.
        Returns True on success, False on failure.
        First run (no key file) always returns True and logs a warning.
        """
        # If a prior lockout has elapsed, clear the current attempt window so the
        # user regains a full allowance (the escalating lockout_count is kept).
        self._clear_expired_lockout()

        # Lockout check
        if self._lockout_until and datetime.now() < self._lockout_until:
            remaining = int((self._lockout_until - datetime.now()).total_seconds()) + 1
            raise AuthLockedError(
                f"Too many failed attempts. Try again in {remaining} second(s)."
            )

        if not self.key_file.exists():
            logger.warning(
                "No password file found — granting first-run access. "
                "Set a password in Settings."
            )
            return True

        if not password:
            return False

        try:
            stored = self.key_file.read_text().strip()
            derived = self._derive_key(password)
            expected = hashlib.sha256(derived).hexdigest()
            success = secrets.compare_digest(stored, expected)
        except (OSError, ValueError) as exc:
            logger.error("Password verification error: %s", exc)
            return False

        if success:
            self._failed_attempts = 0
            self._lockout_count   = 0
            self._lockout_until   = None
            self._session_key     = derived
            self._persist_lockout_state()
            logger.info("Login successful.")
        else:
            self._failed_attempts += 1
            logger.warning(
                "Failed login attempt %d/%d.", self._failed_attempts, self.MAX_ATTEMPTS
            )
            if self._failed_attempts >= self.MAX_ATTEMPTS:
                # Escalate by how many times we have locked out, not by raw
                # attempt count — this survives the per-window reset on expiry.
                self._lockout_count += 1
                backoff = min(
                    self.MAX_LOCKOUT,
                    self.BASE_LOCKOUT * (2 ** (self._lockout_count - 1)),
                )
                self._lockout_until = datetime.now() + timedelta(seconds=backoff)
                logger.warning("Account locked for %ds.", backoff)
            self._persist_lockout_state()

        return success

    def attempts_remaining(self) -> int:
        return max(0, self.MAX_ATTEMPTS - self._failed_attempts)

    def has_password(self) -> bool:
        return self.key_file.exists()

    # ── Lockout persistence ───────────────────────────────────────────────────

    def _load_lockout_state(self):
        """Load persisted brute-force state so a restart cannot reset it."""
        if not self.lockout_file.exists():
            return
        try:
            data = json.loads(self.lockout_file.read_text())
            self._failed_attempts = int(data.get("failed_attempts", 0))
            self._lockout_count   = int(data.get("lockout_count", 0))
            until = data.get("lockout_until")
            self._lockout_until = datetime.fromisoformat(until) if until else None
        except (json.JSONDecodeError, OSError, ValueError, TypeError) as exc:
            logger.error("Could not read lockout state (%s) — starting fresh.", exc)
            self._failed_attempts = 0
            self._lockout_count   = 0
            self._lockout_until   = None

    def _persist_lockout_state(self):
        """Write brute-force state to disk. Best-effort; never blocks login."""
        try:
            self.lockout_file.write_text(json.dumps({
                "failed_attempts": self._failed_attempts,
                "lockout_count":   self._lockout_count,
                "lockout_until":   self._lockout_until.isoformat()
                                   if self._lockout_until else None,
            }))
        except OSError as exc:
            logger.error("Could not persist lockout state: %s", exc)

    def _clear_expired_lockout(self):
        """
        When a lockout has elapsed, reset the per-window attempt counter so the
        user regains a full allowance. The escalating lockout_count is preserved
        so repeated lockouts keep backing off (30s … 5min).
        """
        if self._lockout_until and datetime.now() >= self._lockout_until:
            self._failed_attempts = 0
            self._lockout_until   = None
            self._persist_lockout_state()

    # ── TOTP ─────────────────────────────────────────────────────────────────

    def setup_totp(self) -> Optional[str]:
        """Generate and store a new TOTP secret, encrypted with session key."""
        if not self.totp_secret_file.exists():
            secret = pyotp.random_base32()
            self._write_totp_secret(secret)
        return self.get_totp_uri()

    def _write_totp_secret(self, secret: str):
        fernet = self._get_fernet()
        if fernet:
            self.totp_secret_file.write_bytes(fernet.encrypt(secret.encode()))
            logger.debug("TOTP secret written (encrypted).")
        else:
            # Session key not yet established (edge case); store plaintext with warning
            self.totp_secret_file.write_text(secret)
            logger.warning(
                "TOTP secret written in plaintext — log in first to enable encryption."
            )

    def _read_totp_secret(self) -> Optional[str]:
        if not self.totp_secret_file.exists():
            return None
        data = self.totp_secret_file.read_bytes()
        fernet = self._get_fernet()
        if fernet:
            try:
                return fernet.decrypt(data).decode()
            except InvalidToken:
                # Possibly stored in old plaintext format — try decoding as UTF-8
                try:
                    plaintext = data.decode().strip()
                    # Re-encrypt now that we have a session key
                    self._write_totp_secret(plaintext)
                    logger.info("Migrated TOTP secret to encrypted storage.")
                    return plaintext
                except UnicodeDecodeError:
                    logger.error("Cannot decrypt TOTP secret — data corrupted.")
                    return None
        else:
            # No session key — try plaintext fallback
            try:
                return data.decode().strip()
            except UnicodeDecodeError:
                logger.error("Cannot read TOTP secret without session key.")
                return None

    def get_totp_uri(self) -> Optional[str]:
        secret = self._read_totp_secret()
        if not secret:
            return None
        return pyotp.TOTP(secret).provisioning_uri(
            name="Lorebox", issuer_name="Lorebox"
        )

    def verify_totp(self, code: str) -> bool:
        if not self.totp_secret_file.exists():
            return False
        try:
            secret = self._read_totp_secret()
            if not secret:
                return False
            return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
        except (ValueError, AttributeError) as exc:
            logger.warning("TOTP verification error: %s", exc)
            return False

    # ── Recovery codes ────────────────────────────────────────────────────────

    def generate_recovery_codes(self) -> List[str]:
        """
        Generate 8 one-time recovery codes.
        Returns plaintext codes to show the user once.
        Stores SHA-256 hashes — plaintext is never written to disk.
        """
        codes  = [secrets.token_hex(4).upper() for _ in range(8)]
        hashes = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
        self.recovery_file.write_text(json.dumps(hashes))
        logger.info("Recovery codes generated (%d codes).", len(codes))
        return codes

    def verify_recovery_code(self, code: str) -> bool:
        if not self.recovery_file.exists():
            return False
        try:
            stored = json.loads(self.recovery_file.read_text())
            code_hash = hashlib.sha256(code.strip().upper().encode()).hexdigest()
            if code_hash in stored:
                stored.remove(code_hash)
                self.recovery_file.write_text(json.dumps(stored))
                logger.info("Recovery code used — %d remaining.", len(stored))
                return True
            return False
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Recovery code verification error: %s", exc)
            return False


# ── Windows Hello ─────────────────────────────────────────────────────────────

class WindowsHelloAuth:
    """Windows Hello biometric authentication."""

    def __init__(self):
        self.credential_name = "Lorebox_Login"

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
            from winrt.windows.security.credentials import (
                KeyCredentialManager, KeyCredentialCreationOption,
            )

            async def _auth():
                manager = KeyCredentialManager()
                result  = await manager.request_create_async(
                    self.credential_name, KeyCredentialCreationOption.SILENT
                )
                if result.status == 0:
                    verify = await result.credential.request_verification_async()
                    return verify.status == 0
                return False

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(_auth())
            loop.close()
            return ok
        except Exception as exc:
            logger.debug("Windows Hello error: %s", exc)
            return False
