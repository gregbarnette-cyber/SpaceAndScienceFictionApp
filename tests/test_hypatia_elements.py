# tests/test_hypatia_elements.py — offline tests for the element master table.
import unittest

from core.hypatia_elements import (
    HYPATIA_SPECIES, HYPATIA_REQUEST_SYMBOLS, SPECIES_BY_SYMBOL, SPECIES_ORDER,
    CATEGORIES, display_symbol, category_label, category_color,
)


class TestHypatiaElements(unittest.TestCase):
    def test_count_and_uniqueness(self):
        self.assertEqual(len(HYPATIA_SPECIES), 104)
        self.assertEqual(len(HYPATIA_REQUEST_SYMBOLS), 104)
        self.assertEqual(len(set(HYPATIA_REQUEST_SYMBOLS)), 104)

    def test_every_species_has_metadata(self):
        cat_keys = {k for k, _l, _c in CATEGORIES}
        for s in HYPATIA_SPECIES:
            self.assertTrue(s["name"], f"missing name for {s['symbol']}")
            self.assertIsInstance(s["z"], int)
            self.assertTrue(3 <= s["z"] <= 90, f"z out of range for {s['symbol']}: {s['z']}")
            self.assertIn(s["category"], cat_keys, f"bad category for {s['symbol']}")

    def test_display_and_lookup(self):
        self.assertEqual(display_symbol("Ba_II"), "Ba II")
        self.assertEqual(display_symbol("Fe"), "Fe")
        self.assertEqual(display_symbol("Eu_II"), "Eu II")
        self.assertIn("fe", SPECIES_BY_SYMBOL)
        self.assertIn("ba_ii", SPECIES_BY_SYMBOL)
        self.assertEqual(SPECIES_BY_SYMBOL["ba_ii"]["name"], "Barium II")

    def test_ordering_category_major_then_z(self):
        # Within the list, category index is non-decreasing, and within a category
        # atomic number is non-decreasing (neutral before its ionized form).
        cat_order = {k: i for i, (k, _l, _c) in enumerate(CATEGORIES)}
        prev = (-1, -1, -1)
        for s in HYPATIA_SPECIES:
            key = (cat_order[s["category"]], s["z"], 1 if s["ionized"] else 0)
            self.assertGreaterEqual(key, prev, f"ordering broke at {s['symbol']}")
            prev = key

    def test_species_order_matches_list(self):
        for i, s in enumerate(HYPATIA_SPECIES):
            self.assertEqual(SPECIES_ORDER[s["symbol"].lower()], i)

    def test_category_helpers(self):
        self.assertEqual(category_label("iron"), "Iron-peak")
        self.assertTrue(category_color("iron").startswith("#"))
        # all 19 original elements still present
        original = ["Fe", "Mg", "Si", "Ca", "Ti", "O", "C", "N", "Na", "Al",
                    "S", "Ni", "Co", "Cr", "Mn", "Ba", "Y", "Sr", "Eu"]
        for sym in original:
            self.assertIn(sym.lower(), SPECIES_BY_SYMBOL, f"{sym} dropped from set")


if __name__ == "__main__":
    unittest.main()
