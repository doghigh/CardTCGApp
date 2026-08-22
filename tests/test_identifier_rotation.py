import numpy as np
from types import SimpleNamespace
from core.identifier import CardIdentifier


class _FakeResp:
    def __init__(self, text):
        self.content = [SimpleNamespace(text=text)]


class _FakeClient:
    def __init__(self, text):
        self._text = text
        self.messages = SimpleNamespace(create=lambda **kw: _FakeResp(self._text))


def _img():
    return np.full((20, 20, 3), 200, dtype=np.uint8)


def test_valid_rotation_values_are_parsed():
    text = ('{"name":"Elvish Farmer","game":"Magic: The Gathering",'
            '"front_rotation":90,"back_rotation":180}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), _img(), client=_FakeClient(text))
    assert out["front_rotation"] == 90
    assert out["back_rotation"] == 180


def test_missing_rotation_fields_default_to_zero():
    text = '{"name":"X","game":"Other"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_out_of_range_rotation_clamps_to_zero():
    text = ('{"name":"X","game":"Other","front_rotation":45,"back_rotation":-90}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_non_numeric_rotation_does_not_crash():
    text = '{"name":"X","game":"Other","front_rotation":"upright","back_rotation":null}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["front_rotation"] == 0
    assert out["back_rotation"] == 0


def test_rotation_present_alongside_condition_fields():
    """Regression: rotation parsing must not disturb the existing condition path."""
    text = ('{"name":"X","game":"Other","condition_score":80,"defects":[],'
            '"front_rotation":180,"back_rotation":0}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] == {"score": 80, "defects": []}
    assert out["front_rotation"] == 180
