"""Tests for core.valuator — pure logic (no network)."""

import unittest

from core.valuator import CardValuator, CONDITION_MULTIPLIERS


class ValuatorLogicTests(unittest.TestCase):
    def setUp(self):
        self.v = CardValuator()

    # ── compute_estimate ─────────────────────────────────────────────────────

    def test_no_values_is_zero(self):
        self.assertEqual(self.v.compute_estimate([]), 0.0)

    def test_zero_base_is_zero(self):
        self.assertEqual(self.v.compute_estimate([{"value": 0.0}], grade="Mint"), 0.0)

    def test_cheap_card_floored_to_penny(self):
        # $0.03 × Poor(0.25) = 0.0075 → would round to 0.00; floor at 0.01
        self.assertEqual(self.v.compute_estimate([{"value": 0.03}], grade="Poor"), 0.01)

    def test_grade_multiplier_applied(self):
        base = [{"value": 10.0}]
        self.assertEqual(self.v.compute_estimate(base, grade="Near Mint"),
                         round(10.0 * CONDITION_MULTIPLIERS["Near Mint"], 2))

    def test_played_grade_has_multiplier(self):
        self.assertIn("Played", CONDITION_MULTIPLIERS)
        self.assertGreater(self.v.compute_estimate([{"value": 5.0}], grade="Played"), 0)

    # ── eBay category routing ────────────────────────────────────────────────

    def test_ebay_category_routing(self):
        self.assertEqual(self.v._ebay_category("Baseball"), "213")
        self.assertEqual(self.v._ebay_category("Magic: The Gathering"), "183454")
        self.assertIsNone(self.v._ebay_category("Other"))        # non-sport → all
        self.assertIsNone(self.v._ebay_category(None))

    # ── Scryfall helpers ──────────────────────────────────────────────────────

    def test_is_mtg(self):
        self.assertTrue(self.v._is_mtg("Magic: The Gathering"))
        self.assertTrue(self.v._is_mtg("mtg"))
        self.assertFalse(self.v._is_mtg("Baseball"))
        self.assertFalse(self.v._is_mtg(None))

    def test_scryfall_set_code(self):
        self.assertEqual(self.v._scryfall_set_code("AKH"), "akh")
        self.assertEqual(self.v._scryfall_set_code("W17"), "w17")
        self.assertIsNone(self.v._scryfall_set_code("Fallen Empires"))  # has space
        self.assertIsNone(self.v._scryfall_set_code(None))

    def test_scryfall_price_prefers_usd(self):
        self.assertEqual(self.v._scryfall_price({"prices": {"usd": "1.23"}}), 1.23)
        self.assertEqual(self.v._scryfall_price({"prices": {"usd": None,
                                                            "usd_foil": "4.50"}}), 4.50)
        self.assertIsNone(self.v._scryfall_price({"prices": {}}))

    # ── query building ────────────────────────────────────────────────────────

    def test_build_query_includes_name(self):
        q = self.v._build_query("Sol Ring", "Commander", "Magic: The Gathering")
        self.assertIn("Sol Ring", q)
        self.assertIn("card", q)


if __name__ == "__main__":
    unittest.main()
