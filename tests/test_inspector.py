"""Tests for core.inspector — score→grade mapping and robustness."""

import unittest

import numpy as np

from core.inspector import CardInspector


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.insp = CardInspector()

    def test_empty_image_is_unknown(self):
        result = self.insp.inspect(None)
        self.assertEqual(result["grade"], "Unknown")
        self.assertEqual(result["score"], 0.0)

    def test_inspect_returns_expected_shape(self):
        # A clean synthetic "card": white border around a coloured center
        img = np.full((400, 280, 3), 255, dtype=np.uint8)
        img[40:360, 40:240] = (60, 90, 160)
        result = self.insp.inspect(img)
        self.assertIn("grade", result)
        self.assertIn("score", result)
        self.assertIn("defects", result)
        self.assertTrue(0.0 <= result["score"] <= 100.0)

    def test_grades_cover_full_range(self):
        # Every integer score 0..100 must map to some grade band
        grades = CardInspector.GRADES
        for score in range(0, 101):
            matched = any(lo <= score <= hi for (lo, hi) in grades.values())
            self.assertTrue(matched, f"score {score} has no grade band")

    def test_clean_card_not_graded_poor(self):
        # A pristine synthetic card should not come out as Poor/0
        img = np.full((600, 420, 3), 250, dtype=np.uint8)
        img[60:540, 60:360] = (40, 120, 80)
        result = self.insp.inspect(img)
        self.assertGreater(result["score"], 24)   # above the Poor band


if __name__ == "__main__":
    unittest.main()
