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


def resolve_condition(info, front_img, inspector) -> dict:
    """Return {'grade','score','defects','source'} for a card.

    Prefers the Claude-vision condition carried in `info['condition']`; falls
    back to the CV inspector when vision produced no condition. Grade is always
    derived from the score so the two never disagree.
    """
    cond = (info or {}).get('condition') if isinstance(info, dict) else None
    if cond and isinstance(cond.get('score'), (int, float)):
        score = float(cond['score'])
        defects = cond.get('defects') if isinstance(cond.get('defects'), list) else []
        return {'grade': grade_for_score(score), 'score': score,
                'defects': defects, 'source': 'vision'}

    inspection = inspector.inspect(front_img)
    score = float(inspection.get('score', 0.0))
    return {'grade': grade_for_score(score), 'score': score,
            'defects': inspection.get('defects', []), 'source': 'cv'}
