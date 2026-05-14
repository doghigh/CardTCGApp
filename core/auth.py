import json
import secrets
import base64
import random
import os
from pathlib import Path
from typing import Optional, List, Dict

import pyotp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

try:
    from winrt.windows.security.credentials import KeyCredentialManager, KeyCredentialCreationOption
    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False


class AuthManager:
    """Handles password, TOTP, and recovery for the app."""

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
            iterations=600000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    def set_password(self, password: str):
        """Set master password."""
        key = self._derive_key(password)
        self.key_file.write_bytes(key)

    def check_password(self, password: str) -> bool:
        """Verify master password."""
        if not self.key_file.exists():
            return True  # First run
        stored = self.key_file.read_bytes()
        try:
            derived = self._derive_key(password)
            return secrets.compare_digest(stored, derived)
        except:
            return False

    def has_password(self) -> bool:
        return self.key_file.exists()

    # TOTP Methods
    def setup_totp(self) -> Optional[str]:
        """Generate TOTP secret and return provisioning URI."""
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
        """Verify TOTP code."""
        if not self.totp_secret_file.exists():
            return False
        secret = self.totp_secret_file.read_text().strip()
        totp = pyotp.TOTP(secret)
        return totp.verify(code.strip(), valid_window=1)

    # Recovery codes
    def generate_recovery_codes(self) -> List[str]:
        codes = [f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}" for _ in range(8)]
        self.recovery_file.write_text(json.dumps(codes))
        return codes

    def verify_recovery_code(self, code: str) -> bool:
        if not self.recovery_file.exists():
            return False
        codes = json.loads(self.recovery_file.read_text())
        if code in codes:
            codes.remove(code)
            self.recovery_file.write_text(json.dumps(codes))
            return True
        return False


class WindowsHelloAuth:
    """Windows Hello biometric authentication."""

    def __init__(self):
        self.credential_name = "TradingCardManager_Login"

    def is_available(self) -> bool:
        if not HAS_WINRT:
            return False
        try:
            return KeyCredentialManager.is_supported()
        except:
            return False

    def request_biometric_login(self) -> bool:
        """Prompt Windows Hello (Face / Fingerprint / PIN)."""
        if not HAS_WINRT or not self.is_available():
            return False

        try:
            import asyncio

            async def auth_async():
                manager = KeyCredentialManager()
                result = await manager.request_create_async(
                    self.credential_name,
                    KeyCredentialCreationOption.SILENT
                )
                if result.status == 0:  # Success
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