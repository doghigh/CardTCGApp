"""
Authentication module with secure password handling, TOTP, and Windows Hello.
"""

import json
import secrets
import base64
import os
from pathlib import Path
from typing import Optional, List

import pyotp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Global APP_DIR
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
APP_DIR.mkdir(parents=True, exist_ok=True)


class AuthManager:
    """Secure authentication manager."""

    def __init__(self):
        self.key_file = APP_DIR / ".auth.key"
        self.salt_file = APP_DIR / ".salt"
        self.totp_secret_file = APP_DIR / ".totp_secret"
        self.recovery_file = APP_DIR / ".recovery_codes"
        self._ensure_salt()

    def _ensure_salt(self):
        """Generate or load salt for key derivation."""
        if not self.salt_file.exists():
            self.salt = secrets.token_bytes(16)
            self.salt_file.write_bytes(self.salt)
        else:
            self.salt = self.salt_file.read_bytes()

    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=600_000,          # High iteration count
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    def set_password(self, password: str):
        """Set a new master password."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        key = self._derive_key(password)
        self.key_file.write_bytes(key)

    def check_password(self, password: str) -> bool:
        """Verify master password."""
        if not self.key_file.exists():
            return True  # First run - no password set
        if not password:
            return False
        stored = self.key_file.read_bytes()
        try:
            derived = self._derive_key(password)
            return secrets.compare_digest(stored, derived)
        except Exception:
            return False

    def has_password(self) -> bool:
        """Check if a master password has been set."""
        return self.key_file.exists()

    # ==================== TOTP (Authenticator App) ====================
    def setup_totp(self) -> Optional[str]:
        """Generate TOTP secret and return provisioning URI for QR code."""
        if not self.totp_secret_file.exists():
            secret = pyotp.random_base32()
            self.totp_secret_file.write_text(secret)
        return self.get_totp_uri()

    def get_totp_uri(self) -> Optional[str]:
        """Return TOTP provisioning URI."""
        if not self.totp_secret_file.exists():
            return None
        secret = self.totp_secret_file.read_text().strip()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name="TradingCardManager", issuer_name="TradingCardManager")

    def verify_totp(self, code: str) -> bool:
        """Verify a TOTP code."""
        if not self.totp_secret_file.exists():
            return False
        try:
            secret = self.totp_secret_file.read_text().strip()
            totp = pyotp.TOTP(secret)
            return totp.verify(code.strip(), valid_window=1)
        except Exception:
            return False

    # ==================== Recovery Codes ====================
    def generate_recovery_codes(self) -> List[str]:
        """Generate cryptographically secure recovery codes."""
        codes = [secrets.token_hex(4).upper() for _ in range(8)]
        self.recovery_file.write_text(json.dumps(codes))
        return codes

    def verify_recovery_code(self, code: str) -> bool:
        """Verify and consume a recovery code."""
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
        """Prompt Windows Hello (Face/Fingerprint/PIN)."""
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