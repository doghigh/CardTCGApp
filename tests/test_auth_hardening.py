# tests/test_auth_hardening.py
"""Security regressions for AuthManager.

Covers the second-factor bypass and the unthrottled recovery-code path.
The LoginDialog itself is not exercised here — these assert the manager-level
contract the dialog is required to honor.
"""
import pytest

import core.auth as auth_mod
from core.auth import AuthManager, AuthLockedError


@pytest.fixture
def mgr(tmp_path, monkeypatch):
    """An AuthManager rooted in a tmp dir, never touching real user state."""
    monkeypatch.setattr(auth_mod, "APP_DIR", tmp_path)
    m = AuthManager()
    for attr, name in [
        ("key_file", ".auth.key"), ("salt_file", ".salt"),
        ("totp_secret_file", ".totp_secret"), ("recovery_file", ".recovery_codes"),
        ("lockout_file", ".auth.lockout"),
    ]:
        setattr(m, attr, tmp_path / name)
    m._ensure_salt()
    return m


# ── Second factor ────────────────────────────────────────────────────────────

def test_totp_required_reports_false_when_not_configured(mgr):
    assert mgr.totp_enabled() is False


def test_totp_required_reports_true_once_configured(mgr):
    mgr.set_password("correct horse battery")
    mgr.setup_totp()
    assert mgr.totp_enabled() is True


def test_blank_totp_does_not_satisfy_an_enabled_second_factor(mgr):
    """Regression: the dialog only verified TOTP `if totp` — leaving the field
    blank skipped the second factor entirely even when one was configured."""
    mgr.set_password("correct horse battery")
    mgr.setup_totp()
    assert mgr.totp_enabled() is True
    assert mgr.verify_totp("") is False
    assert mgr.verify_totp("   ") is False
    assert mgr.verify_totp(None) is False


def test_wrong_totp_is_rejected(mgr):
    mgr.set_password("correct horse battery")
    mgr.setup_totp()
    assert mgr.verify_totp("000000") is False


def test_correct_totp_is_accepted(mgr):
    import pyotp
    mgr.set_password("correct horse battery")
    mgr.setup_totp()
    secret = mgr._read_totp_secret()
    assert mgr.verify_totp(pyotp.TOTP(secret).now()) is True


# ── Recovery codes ───────────────────────────────────────────────────────────

def test_recovery_code_works_once_then_is_consumed(mgr):
    mgr.set_password("correct horse battery")
    codes = mgr.generate_recovery_codes()
    assert mgr.verify_recovery_code(codes[0]) is True
    assert mgr.verify_recovery_code(codes[0]) is False


def test_recovery_attempts_are_rate_limited(mgr):
    """Regression: recovery codes had no lockout at all, while passwords got
    exponential backoff — leaving a 32-bit secret open to unthrottled guessing."""
    mgr.set_password("correct horse battery")
    mgr.generate_recovery_codes()
    for _ in range(mgr.MAX_ATTEMPTS):
        assert mgr.verify_recovery_code("DEADBEEF") is False
    with pytest.raises(AuthLockedError):
        mgr.verify_recovery_code("DEADBEEF")


def test_recovery_lockout_also_blocks_password_attempts(mgr):
    """Lockout state is shared — an attacker cannot burn recovery attempts and
    then fall back to password guessing with a fresh allowance."""
    mgr.set_password("correct horse battery")
    mgr.generate_recovery_codes()
    for _ in range(mgr.MAX_ATTEMPTS):
        mgr.verify_recovery_code("DEADBEEF")
    with pytest.raises(AuthLockedError):
        mgr.check_password("correct horse battery")


def test_a_valid_recovery_code_clears_the_failure_counter(mgr):
    mgr.set_password("correct horse battery")
    codes = mgr.generate_recovery_codes()
    for _ in range(mgr.MAX_ATTEMPTS - 1):
        mgr.verify_recovery_code("DEADBEEF")
    assert mgr.verify_recovery_code(codes[0]) is True
    assert mgr.attempts_remaining() == mgr.MAX_ATTEMPTS
