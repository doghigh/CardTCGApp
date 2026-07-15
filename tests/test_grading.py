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
