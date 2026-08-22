"""Tests for utils.image_ops — rotation and (optimized) deskew."""

import unittest

import numpy as np

from utils.image_ops import deskew, rotate_90_cw, rotate_90_ccw, rotate_180, rotate_by, _rotate_bound


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

    def test_rotate_by_zero_is_identity(self):
        img = _card()
        result = rotate_by(img, 0)
        np.testing.assert_array_equal(result, img)

    def test_rotate_by_invalid_value_is_identity(self):
        img = _card()
        result = rotate_by(img, 45)
        np.testing.assert_array_equal(result, img)

    def test_rotate_by_90_matches_rotate_90_cw(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 90), rotate_90_cw(img))

    def test_rotate_by_180_matches_rotate_180(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 180), rotate_180(img))

    def test_rotate_by_270_matches_rotate_90_ccw(self):
        img = _card()
        np.testing.assert_array_equal(rotate_by(img, 270), rotate_90_ccw(img))

    def test_rotate_by_moves_content_not_just_shape(self):
        """Shape alone would pass even if 90 and 270 were swapped internally.

        Verified empirically which corner a top-left marker lands in:
          90 CW  -> top-right
          180    -> bottom-right
          270 (90 CCW) -> bottom-left
        """
        marker = np.full((40, 20, 3), 255, np.uint8)
        marker[0:5, 0:5] = (10, 20, 30)

        r90 = rotate_by(marker, 90)
        self.assertTrue(np.array_equal(r90[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8)))

        r180 = rotate_by(marker, 180)
        self.assertTrue(np.array_equal(r180[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8)))

        r270 = rotate_by(marker, 270)
        self.assertTrue(np.array_equal(r270[-5:, 0:5], np.full((5, 5, 3), (10, 20, 30), np.uint8)))


if __name__ == "__main__":
    unittest.main()
