"""Tests for utils.image_ops.crop_to_card / clean_scan — trimming the pure-white
margin a flatbed scanner (and deskew's padding) leaves around a card."""

import unittest

import numpy as np

from utils.image_ops import crop_to_card, clean_scan, _rotate_bound


def _scan(h=1000, w=720, margin=35, card=(60, 90, 160)):
    """A card filling the image except for a pure-white scanner margin."""
    img = np.full((h, w, 3), 255, np.uint8)
    img[margin:h - margin, margin:w - margin] = card
    return img


class CropToCardTests(unittest.TestCase):
    def test_trims_uniform_scanner_margin(self):
        out = crop_to_card(_scan(margin=35))
        self.assertEqual(out.shape, (1000 - 70, 720 - 70, 3))
        self.assertTrue((out != 255).any(axis=2).all())  # no white left

    def test_trims_uneven_margins(self):
        img = np.full((1000, 720, 3), 255, np.uint8)
        img[60:950, 30:700] = (40, 40, 40)
        out = crop_to_card(img)
        self.assertEqual(out.shape, (890, 670, 3))

    def test_keeps_printed_off_white_border(self):
        # Card with an off-white (240) printed border inside the scanner margin
        img = _scan(margin=35, card=(240, 240, 240))
        img[60:-60, 60:-60] = (60, 90, 160)
        out = crop_to_card(img)
        self.assertEqual(out.shape, (1000 - 70, 720 - 70, 3))

    def test_tolerates_dust_in_margin(self):
        img = _scan(margin=35)
        img[10, 300] = (0, 0, 0)          # one dark speck in the top margin
        out = crop_to_card(img)
        self.assertEqual(out.shape[0], 1000 - 70)

    def test_never_trims_more_than_limit_per_side(self):
        img = _scan(margin=300)            # 30% of the height is "margin"
        out = crop_to_card(img, max_trim=0.15)
        self.assertEqual(out.shape[0], 1000 - 2 * 150)

    def test_all_white_image_is_unchanged(self):
        img = np.full((100, 70, 3), 255, np.uint8)
        self.assertIs(crop_to_card(img), img)

    def test_no_margin_is_unchanged(self):
        img = np.full((100, 70, 3), 50, np.uint8)
        out = crop_to_card(img)
        self.assertEqual(out.shape, img.shape)

    def test_grayscale_supported(self):
        img = _scan(margin=20)[:, :, 0].copy()
        out = crop_to_card(img)
        self.assertEqual(out.shape, (1000 - 40, 720 - 40))

    def test_handles_empty(self):
        self.assertIsNone(crop_to_card(None))


class CleanScanTests(unittest.TestCase):
    def test_tilted_scan_is_straightened_and_trimmed(self):
        tilted = _rotate_bound(_scan(margin=60), 5.0)
        out = clean_scan(tilted)
        # Deskew pads the canvas with white; the crop takes it back off, so
        # the result is no bigger than the card plus small corner slivers.
        self.assertLess(out.shape[0], tilted.shape[0])
        self.assertLess(out.shape[1], tilted.shape[1])
        self.assertLessEqual(abs(out.shape[0] - 880), 20)
        self.assertLessEqual(abs(out.shape[1] - 600), 20)

    def test_handles_empty(self):
        self.assertIsNone(clean_scan(None))


if __name__ == "__main__":
    unittest.main()
