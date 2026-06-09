"""Tests for utils.theme — colour math and stylesheet building."""

import unittest

from utils.theme import _adjust, build_stylesheet, DEFAULT_ACCENT


class ThemeTests(unittest.TestCase):
    def test_adjust_lighten_and_darken(self):
        light = _adjust("#808080", 0.5)
        dark = _adjust("#808080", -0.5)
        self.assertEqual(light, "#bfbfbf")
        self.assertEqual(dark, "#404040")

    def test_adjust_handles_bad_input(self):
        self.assertEqual(_adjust("not-a-color", 0.2), "not-a-color")

    def test_stylesheet_applies_accent(self):
        ss = build_stylesheet("#c41e3a")
        self.assertIn("#c41e3a", ss)
        self.assertIn("outline:", ss)   # visible focus present

    def test_scale_changes_font_size(self):
        import re
        small = build_stylesheet(DEFAULT_ACCENT, 0.9)
        large = build_stylesheet(DEFAULT_ACCENT, 1.3)
        fs = lambda s: int(re.search(r"font-size:\s*(\d+)px", s).group(1))
        self.assertLess(fs(small), fs(large))

    def test_high_contrast_uses_black_and_yellow_focus(self):
        hc = build_stylesheet(DEFAULT_ACCENT, 1.0, True)
        self.assertIn("#000000", hc)
        self.assertIn("#ffcc00", hc)   # high-contrast focus colour


if __name__ == "__main__":
    unittest.main()
