"""Orientation is detected BEFORE identification, so the card is read upright.

Regression: identification used to read the name from the image as scanned and
only report a rotation afterwards — upside-down scans came back as nonsense
names ("Wyld", "Witch" for Island, Mountain) even when the rotation was right.
"""
import numpy as np
import pytest
from types import SimpleNamespace

import core.trial as trial
from core.identifier import CardIdentifier
from utils.image_ops import rotate_180, rotate_90_cw


def _img():
    # Asymmetric so a rotation is detectable by comparing arrays
    img = np.zeros((30, 20, 3), dtype=np.uint8)
    img[0:5, 0:5] = 255
    return img


class _FakeClient:
    """Records each messages.create call and replies with fixed text."""
    def __init__(self, text):
        self.calls = []
        def create(**kw):
            self.calls.append(kw)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=text)],
                stop_reason="end_turn")
        self.messages = SimpleNamespace(create=create)


@pytest.fixture
def own_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")


# ── detect_orientation ────────────────────────────────────────────────────────

def test_detect_orientation_parses_front_and_back(own_key, monkeypatch):
    ident = CardIdentifier()
    client = _FakeClient('{"front": 180, "back": 90}')
    monkeypatch.setattr(ident, "_resolve_client", lambda: (client, "own"))
    assert ident.detect_orientation(_img(), _img()) == (180, 90)
    images = [c for c in client.calls[0]["messages"][0]["content"] if c["type"] == "image"]
    assert len(images) == 2


def test_detect_orientation_front_only_sends_one_image(own_key, monkeypatch):
    ident = CardIdentifier()
    client = _FakeClient('{"front": 270}')
    monkeypatch.setattr(ident, "_resolve_client", lambda: (client, "own"))
    assert ident.detect_orientation(_img(), None) == (270, 0)
    images = [c for c in client.calls[0]["messages"][0]["content"] if c["type"] == "image"]
    assert len(images) == 1


def test_detect_orientation_tolerates_prose_around_json(own_key, monkeypatch):
    ident = CardIdentifier()
    client = _FakeClient('Sure:\n```json\n{"front": 0, "back": 180}\n```')
    monkeypatch.setattr(ident, "_resolve_client", lambda: (client, "own"))
    assert ident.detect_orientation(_img(), _img()) == (0, 180)


@pytest.mark.parametrize("text", ["not json", '{"front": 45, "back": "x"}', ""])
def test_detect_orientation_bad_reply_means_no_rotation(own_key, monkeypatch, text):
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "_resolve_client", lambda: (_FakeClient(text), "own"))
    assert ident.detect_orientation(_img(), _img()) == (0, 0)


def test_detect_orientation_api_error_means_no_rotation(own_key, monkeypatch):
    ident = CardIdentifier()
    def boom(**kw):
        raise RuntimeError("network down")
    client = SimpleNamespace(messages=SimpleNamespace(create=boom))
    monkeypatch.setattr(ident, "_resolve_client", lambda: (client, "own"))
    assert ident.detect_orientation(_img(), _img()) == (0, 0)


def test_detect_orientation_skipped_in_trial_mode(monkeypatch):
    ident = CardIdentifier()
    client = _FakeClient('{"front": 180, "back": 180}')
    monkeypatch.setattr(ident, "_resolve_client", lambda: (client, "trial"))
    assert ident.detect_orientation(_img(), _img()) == (0, 0)
    assert client.calls == []


# ── identify_card uses the detected orientation ───────────────────────────────

def test_identify_reads_the_card_upright(own_key, monkeypatch):
    front, back = _img(), _img()
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "detect_orientation", lambda f, b: (180, 90))
    seen = {}
    def fake_identify(f, b):
        seen["front"], seen["back"] = f, b
        # The identification call's own (unreliable) rotation guess is ignored
        return {"name": "Island", "front_rotation": 0, "back_rotation": 270}
    monkeypatch.setattr(ident, "_identify_with_claude", fake_identify)

    out = ident.identify_card(front, back)

    assert np.array_equal(seen["front"], rotate_180(front))
    assert np.array_equal(seen["back"], rotate_90_cw(back))
    # Callers rotate their own copies by these, so they must be the detected values
    assert out["front_rotation"] == 180
    assert out["back_rotation"] == 90
    assert out["name"] == "Island"
    assert out["source"] == "claude"


def test_identify_upright_card_is_passed_through_unrotated(own_key, monkeypatch):
    front = _img()
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "detect_orientation", lambda f, b: (0, 0))
    seen = {}
    monkeypatch.setattr(ident, "_identify_with_claude",
                        lambda f, b: seen.update(front=f, back=b) or {"name": "Forest"})
    out = ident.identify_card(front)
    assert np.array_equal(seen["front"], front)
    assert seen["back"] is None
    assert (out["front_rotation"], out["back_rotation"]) == (0, 0)


def test_ocr_fallback_also_reports_detected_rotation(own_key, monkeypatch):
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "detect_orientation", lambda f, b: (180, 0))
    monkeypatch.setattr(ident, "_identify_with_claude", lambda f, b: None)
    monkeypatch.setattr(ident, "extract_text", lambda img: "")
    out = ident.identify_card(_img(), _img())
    assert out["source"] == "ocr"
    assert out["front_rotation"] == 180


def test_trial_mode_does_not_run_orientation_check(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    monkeypatch.setattr(trial, "consume_trial", lambda: None)
    ident = CardIdentifier()
    called = {"n": 0}
    def detect(f, b):
        called["n"] += 1
        return (0, 0)
    monkeypatch.setattr(ident, "detect_orientation", detect)
    monkeypatch.setattr(ident, "_identify_with_claude", lambda f, b: {"name": "X"})
    ident.identify_card(_img())
    assert called["n"] == 0
