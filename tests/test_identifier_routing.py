# tests/test_identifier_routing.py
import numpy as np
import pytest

import core.trial as trial
from core.identifier import CardIdentifier


@pytest.fixture
def img():
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_own_key_calls_direct_and_does_not_consume(monkeypatch, img):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "_identify_with_claude",
                        lambda f, b: {"name": "Black Lotus"})
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))

    out = ident.identify_card(img)
    assert out["source"] == "claude"
    assert consumed["n"] == 0  # own key never touches the trial counter


def test_trial_success_consumes_one_credit(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "_identify_with_claude", lambda f, b: {"name": "Shivan Dragon"})

    out = ident.identify_card(img)
    assert out["source"] == "claude"
    assert consumed["n"] == 1


def test_trial_exhausted_makes_no_call(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 0)
    ident = CardIdentifier()
    called = {"n": 0}
    monkeypatch.setattr(ident, "_identify_with_claude",
                        lambda f, b: called.__setitem__("n", called["n"] + 1))

    out = ident.identify_card(img)
    assert out["source"] == "trial_exhausted"
    assert called["n"] == 0


def test_trial_capacity_does_not_consume(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()

    def raise_capacity(f, b):
        raise trial.TrialCapacityReached()
    monkeypatch.setattr(ident, "_identify_with_claude", raise_capacity)

    out = ident.identify_card(img)
    assert out["source"] == "trial_capacity"
    assert consumed["n"] == 0


def test_trial_unavailable_does_not_consume(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()

    def raise_unavailable(f, b):
        raise trial.TrialUnavailable()
    monkeypatch.setattr(ident, "_identify_with_claude", raise_unavailable)

    out = ident.identify_card(img)
    assert out["source"] == "trial_unavailable"
    assert consumed["n"] == 0


# ----------------------------------------------------------------------
# Real _identify_with_claude(...) exception-translation tests.
#
# The tests above all monkeypatch _identify_with_claude wholesale, so the
# real `except Exception as e:` block that translates a proxy error into
# TrialCapacityReached / TrialUnavailable (when trial_mode=True) is never
# exercised. These tests call _identify_with_claude directly with a fake
# `client` so that real code path runs.
# ----------------------------------------------------------------------

class _FakeProxyError(Exception):
    """Stand-in for the anthropic SDK's APIStatusError shape.

    _identify_with_claude's except block reads `status_code` and `body`
    off the raised exception via getattr(..., None), and if `body` is a
    dict it looks at body["error"]["type"]. This fake carries exactly
    those two attributes so the real translation logic runs unmodified.
    """
    def __init__(self, status_code=None, body=None):
        super().__init__("fake proxy error")
        self.status_code = status_code
        self.body = body


class _FakeMessages:
    def __init__(self, exc):
        self._exc = exc

    def create(self, *args, **kwargs):
        raise self._exc


class _FakeClient:
    def __init__(self, exc):
        self.messages = _FakeMessages(exc)


def test_identify_with_claude_trial_429_capacity_raises_trial_capacity(img):
    """trial_mode=True + status_code 429 + trial_capacity body -> TrialCapacityReached."""
    ident = CardIdentifier()
    exc = _FakeProxyError(status_code=429, body={"error": {"type": "trial_capacity"}})
    client = _FakeClient(exc)

    with pytest.raises(trial.TrialCapacityReached):
        ident._identify_with_claude(img, client=client, trial_mode=True)


def test_identify_with_claude_trial_generic_error_raises_trial_unavailable(img):
    """trial_mode=True + an error that isn't the 429/trial_capacity shape -> TrialUnavailable."""
    ident = CardIdentifier()
    exc = _FakeProxyError(status_code=500, body={"error": {"type": "server_error"}})
    client = _FakeClient(exc)

    with pytest.raises(trial.TrialUnavailable):
        ident._identify_with_claude(img, client=client, trial_mode=True)


def test_identify_with_claude_trial_429_wrong_type_raises_trial_unavailable(img):
    """429 status but a body type other than trial_capacity still falls through to TrialUnavailable."""
    ident = CardIdentifier()
    exc = _FakeProxyError(status_code=429, body={"error": {"type": "rate_limited"}})
    client = _FakeClient(exc)

    with pytest.raises(trial.TrialUnavailable):
        ident._identify_with_claude(img, client=client, trial_mode=True)


def test_identify_with_claude_own_key_generic_error_returns_none(img):
    """Non-trial mode (own API key): the same error is swallowed and returns None,
    preserving existing own-key behavior (no exception propagates)."""
    ident = CardIdentifier()
    exc = _FakeProxyError(status_code=500, body={"error": {"type": "server_error"}})
    client = _FakeClient(exc)

    result = ident._identify_with_claude(img, client=client, trial_mode=False)
    assert result is None
