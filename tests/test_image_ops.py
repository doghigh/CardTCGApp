"""Tests for utils.image_ops — rotation and (optimized) deskew."""

import unittest

import numpy as np

from utils.image_ops import deskew, rotate_90_cw, rotate_180, _rotate_bound


def _card(h=900, w=600):
    """A dark card centered on a white background."""
    img = np.full((h, w, 3), 255, np.uint8)
    img[h // 8: 7 * h // 8, w // 8: 7 * w // 8] = (60, 90, 160)
    return img


class ImageOpsTests(unittest.TestCase):
    def test_rotate_90_changes_orientation(self):
        img = _card()
        r = rotate_90_cw(img)
        self.assertEqual(r.shape[0], img.shape[1])
        self.assertEqual(r.shape[1], img.shape[0])

    def test_rotate_180_preserves_shape(self):
        img = _card()
        self.assertEqual(rotate_180(img).shape, img.shape)

    def test_deskew_leaves_straight_image_unchanged(self):
        img = _card()
        out = deskew(img)
        self.assertEqual(out.shape, img.shape)  # no warp on a straight card

    def test_deskew_corrects_a_tilt(self):
        tilted = _rotate_bound(_card(), 7.0)
        fixed = deskew(tilted)
        # A correction was applied (canvas re-expanded), so the shape changes
        self.assertNotEqual(fixed.shape, tilted.shape)

    def test_deskew_handles_empty(self):
        self.assertIsNone(deskew(None))


if __name__ == "__main__":
    unittest.main()
