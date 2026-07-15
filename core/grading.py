"""Condition grading helpers: one source of truth for score->grade, and a
resolver that prefers Claude-vision condition over the CV inspector."""

# Contiguous bands — every score in [0,100] maps to exactly one grade (no gaps).
# (lower_inclusive, grade), checked high to low.
_BANDS = [
    (95, "Gem Mint"),
    (88, "Mint"),
    (76, "Near Mint"),
    (64, "Excellent"),
    (52, "Very Good"),
    (40, "Good"),
    (25, "Played"),
    (0,  "Poor"),
]


def grade_for_score(score: float) -> str:
    """Map a 0-100 condition score to a grade label. Clamps out-of-range input."""
    s = max(0.0, min(100.0, float(score)))
    for lower, grade in _BANDS:
        if s >= lower:
            return grade
    return "Poor"
