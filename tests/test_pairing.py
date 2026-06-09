"""Tests for front/back pairing logic in ImageBatchWorker."""

import unittest

from ui.batch_tab import ImageBatchWorker as W


def _pages(spec):
    """spec: list of (stem, side) → page descriptor dicts."""
    return [{"source": s, "page": None, "kind": "image", "stem": s, "side": side}
            for s, side in spec]


def _names(pairs):
    return [(f["stem"] if f else None, b["stem"] if b else None) for f, b in pairs]


class PairingTests(unittest.TestCase):
    def test_single(self):
        pages = _pages([("a", "front"), ("b", "front")])
        self.assertEqual(_names(W._pair_pages(pages, W.SINGLE)),
                         [("a", None), ("b", None)])

    def test_sequential(self):
        pages = _pages([("1", "front"), ("2", "back"), ("3", "front"), ("4", "back")])
        self.assertEqual(_names(W._pair_pages(pages, W.SEQUENTIAL)),
                         [("1", "2"), ("3", "4")])

    def test_sequential_odd_leaves_backless(self):
        pages = _pages([("1", "front"), ("2", "back"), ("3", "front")])
        self.assertEqual(_names(W._pair_pages(pages, W.SEQUENTIAL)),
                         [("1", "2"), ("3", None)])

    def test_filename(self):
        pages = _pages([("Sol_front", "front"), ("Sol_back", "back"),
                        ("Bolt_front", "front"), ("Bolt_back", "back")])
        self.assertEqual(_names(W._pair_pages(pages, W.FILENAME)),
                         [("Sol_front", "Sol_back"), ("Bolt_front", "Bolt_back")])

    def test_orientation_back_then_front_with_orphan(self):
        # Mirrors the 1986 Topps case: leading orphan front, then back→front pairs
        pages = _pages([
            ("202", "front"),                 # orphan (back in a prior batch)
            ("203", "back"), ("204", "front"),
            ("205", "back"), ("206", "front"),
        ])
        result = _names(W._pair_pages(pages, W.ORIENTATION))
        self.assertEqual(result, [
            ("202", None),
            ("204", "203"),
            ("206", "205"),
        ])


if __name__ == "__main__":
    unittest.main()
