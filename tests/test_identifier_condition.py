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


def test_condition_parsed_from_vision_json():
    text = ('{"name":"Bert Blyleven","set_name":"Fleer","card_number":"3",'
            '"rarity":"Award Winner","year":1987,"game":"Baseball",'
            '"condition_score":35,"defects":[{"type":"missing_material",'
            '"location":"top_right","severity":"severe"}]}')
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["name"] == "Bert Blyleven"
    assert out["condition"] == {"score": 35,
                                "defects": [{"type": "missing_material",
                                             "location": "top_right",
                                             "severity": "severe"}]}


def test_missing_condition_score_yields_none_condition():
    text = '{"name":"X","set_name":null,"card_number":null,"rarity":null,"year":null,"game":"Other"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] is None


def test_malformed_defects_do_not_crash():
    text = '{"name":"X","game":"Other","condition_score":80,"defects":"oops"}'
    ident = CardIdentifier()
    out = ident._identify_with_claude(_img(), None, client=_FakeClient(text))
    assert out["condition"] == {"score": 80, "defects": []}
