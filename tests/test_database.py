"""Tests for core.database — validation, duplicates, updates, aggregations."""

import tempfile
import unittest
from pathlib import Path

from core.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(Path(tempfile.mktemp(suffix=".db")))

    # ── validation ──────────────────────────────────────────────────────────

    def test_validation_clamps_and_defaults(self):
        cid = self.db.add_card({
            "name": "  Test Card  ", "year": 3000, "quantity": -5,
            "purchase_price": -10, "estimated_value": 9_999_999,
            "condition_score": 250, "foil": "yes",
        })
        c = self.db.get_card(cid)
        self.assertEqual(c["name"], "Test Card")          # trimmed
        self.assertIsNone(c["year"])                      # out of range → None
        self.assertEqual(c["quantity"], 1)                # clamped up
        self.assertEqual(c["purchase_price"], 0.0)        # negative → 0
        self.assertEqual(c["estimated_value"], 1_000_000) # clamped to max
        self.assertEqual(c["condition_score"], 100.0)     # clamped
        self.assertEqual(c["foil"], 1)                    # truthy → 1

    def test_missing_name_defaults_unknown(self):
        cid = self.db.add_card({"name": ""})
        self.assertEqual(self.db.get_card(cid)["name"], "Unknown")

    # ── duplicates ──────────────────────────────────────────────────────────

    def test_duplicates_merge_and_sum_quantity(self):
        base = {"name": "Sol Ring", "set_name": "CMD", "card_number": "1",
                "game": "Magic: The Gathering"}
        a = self.db.add_card({**base, "quantity": 1})
        b = self.db.add_card({**base, "name": "sol ring", "quantity": 2})  # diff case
        self.assertEqual(a, b)                              # merged
        self.assertEqual(self.db.get_card(a)["quantity"], 3)

    def test_foil_variant_does_not_merge(self):
        base = {"name": "Sol Ring", "set_name": "CMD", "card_number": "1",
                "game": "Magic: The Gathering"}
        a = self.db.add_card({**base, "foil": 0})
        b = self.db.add_card({**base, "foil": 1})
        self.assertNotEqual(a, b)

    def test_merge_existing_duplicates(self):
        base = {"name": "Bolt", "set_name": "M11", "card_number": "149",
                "game": "Magic: The Gathering"}
        for q in (1, 1, 1):
            self.db.add_card({**base, "quantity": q}, merge_duplicates=False)
        res = self.db.merge_existing_duplicates()
        self.assertEqual(res["removed"], 2)
        self.assertEqual(self.db.get_collection_stats()["total_cards"], 1)
        self.assertEqual(self.db.get_collection_stats()["total_quantity"], 3)

    # ── update_card must not clobber un-passed fields ─────────────────────────

    def test_update_card_preserves_other_fields(self):
        cid = self.db.add_card({
            "name": "Darryl Strawberry", "game": "Baseball", "year": 1986,
            "quantity": 3, "foil": 1, "purchase_price": 5.0, "estimated_value": 10.0,
        })
        self.db.update_card(cid, {"estimated_value": 42.5})
        c = self.db.get_card(cid)
        self.assertEqual(c["estimated_value"], 42.5)
        self.assertEqual(c["name"], "Darryl Strawberry")
        self.assertEqual(c["quantity"], 3)
        self.assertEqual(c["foil"], 1)
        self.assertEqual(c["year"], 1986)
        self.assertEqual(c["purchase_price"], 5.0)

    # ── aggregations & history ────────────────────────────────────────────────

    def test_breakdowns_and_top(self):
        self.db.add_card({"name": "A", "game": "Baseball", "estimated_value": 1, "quantity": 1})
        self.db.add_card({"name": "B", "game": "Magic: The Gathering",
                          "estimated_value": 50, "quantity": 1})
        games = {g["game"]: g["value"] for g in self.db.get_game_breakdown()}
        self.assertEqual(games["Magic: The Gathering"], 50)
        top = self.db.get_top_cards(1)
        self.assertEqual(top[0]["name"], "B")

    def test_value_snapshot_upserts_one_per_day(self):
        self.db.add_card({"name": "A", "estimated_value": 5, "quantity": 2})
        self.db.record_value_snapshot()
        self.db.record_value_snapshot()  # same day → still one row
        hist = self.db.get_value_history(90)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["total_value"], 10)


if __name__ == "__main__":
    unittest.main()
