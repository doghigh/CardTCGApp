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
