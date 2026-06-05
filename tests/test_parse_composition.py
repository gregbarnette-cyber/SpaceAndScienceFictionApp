# tests/test_parse_composition.py — offline tests for _parse_hypatia_composition,
# driven by a recorded live /composition response for Tau Ceti (all 104 species).
import json
import os
import unittest

from core.databases import _parse_hypatia_composition
from core.hypatia_elements import SPECIES_ORDER

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "tau_ceti_composition.json")


class TestParseComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_FIXTURE) as f:
            cls.raw = json.load(f)
        cls.parsed = _parse_hypatia_composition(cls.raw)

    def test_drops_none_mean(self):
        # Fixture has species with no measured mean (e.g. Li) — they must be omitted.
        self.assertLess(len(self.parsed), len(self.raw))
        for a in self.parsed:
            self.assertIsNotNone(a["mean"])

    def test_more_than_legacy_19(self):
        self.assertGreater(len(self.parsed), 19)

    def test_ionized_casing_preserved(self):
        syms = {a["element"] for a in self.parsed}
        # At least one ionized species is present and keeps its API casing (not "Si_ii").
        ionized = [s for s in syms if "_II" in s]
        self.assertTrue(ionized, "expected ionized species in fixture")
        for s in ionized:
            self.assertTrue(s.endswith("_II"), f"bad ionized casing: {s}")
            self.assertNotIn("_ii", s)

    def test_metadata_attached(self):
        for a in self.parsed:
            self.assertTrue(a["name"], f"no name for {a['element']}")
            self.assertIsInstance(a["z"], int)
            self.assertTrue(a["category"], f"no category for {a['element']}")
        fe = next(a for a in self.parsed if a["element"] == "Fe")
        self.assertEqual(fe["name"], "Iron")
        self.assertEqual(fe["category"], "iron")

    def test_sorted_by_master_order(self):
        orders = [SPECIES_ORDER[a["element"].lower()] for a in self.parsed]
        self.assertEqual(orders, sorted(orders))

    def test_std_uses_plusminus(self):
        # plusminus is positive; the API's own std is negative log-space and must NOT be used.
        for a in self.parsed:
            if a["std"] is not None:
                self.assertGreaterEqual(a["std"], 0.0, f"negative std for {a['element']}")

    def test_n_from_catalogs_linear(self):
        # The response has no explicit count; parser derives it from catalogs_linear length.
        item = {"element": "Fe", "mean": -0.2, "plusminus": 0.1,
                "catalogs_linear": {"a": 1.0, "b": 1.1, "c": 0.9}}
        out = _parse_hypatia_composition([item])
        self.assertEqual(out[0]["n"], 3)


if __name__ == "__main__":
    unittest.main()
