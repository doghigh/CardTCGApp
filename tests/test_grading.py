import pytest
from core.grading import grade_for_score


@pytest.mark.parametrize("score,grade", [
    (100, "Gem Mint"), (96, "Gem Mint"), (95, "Gem Mint"),
    (94.9, "Mint"), (94.5, "Mint"), (88, "Mint"),
    (87.9, "Near Mint"), (78, "Near Mint"), (76, "Near Mint"),
    (75.4, "Excellent"), (64, "Excellent"),
    (63.9, "Very Good"), (52, "Very Good"),
    (51.9, "Good"), (40, "Good"),
    (39.9, "Played"), (25, "Played"),
    (24.9, "Poor"), (0, "Poor"),
])
def test_grade_for_score_boundaries(score, grade):
    assert grade_for_score(score) == grade


def test_grade_for_score_clamps_out_of_range():
    assert grade_for_score(150) == "Gem Mint"
    assert grade_for_score(-5) == "Poor"


def test_no_score_in_0_100_returns_poor_default_gap():
    # The exact bug-B cases must NOT return "Poor".
    assert grade_for_score(94.5) != "Poor"
    assert grade_for_score(75.4) != "Poor"


def test_inspector_uses_shared_grade_mapping(monkeypatch):
    import numpy as np
    from core.inspector import CardInspector
    insp = CardInspector()
    # Force a known score by stubbing the detectors to yield no defects and a
    # centering score that lands the total at 94.5 (previously the "Poor" gap).
    monkeypatch.setattr(insp, "_detect_card_region", lambda img: img)
    monkeypatch.setattr(insp, "_detect_corner_damage", lambda img: [])
    monkeypatch.setattr(insp, "_detect_edge_wear", lambda img: [])
    monkeypatch.setattr(insp, "_detect_surface_defects", lambda img: [])
    monkeypatch.setattr(insp, "_detect_centering", lambda img: ([], 45.0))  # -> 100 - 5.5 = 94.5
    out = insp.inspect(np.zeros((100, 100, 3), dtype=np.uint8))
    assert out["score"] == 94.5
    assert out["grade"] == "Mint"   # NOT "Poor"


# resolve_condition tests
class _FakeInspector:
    def __init__(self, score, defects): self._s, self._d = score, defects
    def inspect(self, img):
        return {'grade': 'ignored', 'score': self._s, 'defects': self._d, 'centering_score': 0.0}


def test_resolve_condition_prefers_vision():
    from core.grading import resolve_condition
    info = {'name': 'x', 'condition': {'score': 35,
            'defects': [{'type': 'missing_material', 'location': 'top_right', 'severity': 'severe'}]}}
    out = resolve_condition(info, front_img=None, inspector=_FakeInspector(99, []))
    assert out['source'] == 'vision'
    assert out['score'] == 35.0
    assert out['grade'] == 'Played'          # grade_for_score(35)
    assert out['defects'][0]['type'] == 'missing_material'


def test_resolve_condition_falls_back_to_cv():
    from core.grading import resolve_condition
    info = {'name': 'x', 'condition': None}   # no vision condition
    out = resolve_condition(info, front_img=object(), inspector=_FakeInspector(94.5, []))
    assert out['source'] == 'cv'
    assert out['score'] == 94.5
    assert out['grade'] == 'Mint'            # shared mapping, not "Poor"


def test_resolve_condition_handles_missing_info():
    from core.grading import resolve_condition
    out = resolve_condition(None, front_img=object(), inspector=_FakeInspector(80, []))
    assert out['source'] == 'cv' and out['grade'] == 'Near Mint'
