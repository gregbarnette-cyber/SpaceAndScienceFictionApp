# tests/test_prepare_abundance_profile.py — offline test for core.viz.prepare_abundance_profile.
import json
import os
import unittest

from core.databases import _parse_hypatia_composition
from core.viz import prepare_abundance_profile

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "tau_ceti_composition.json")


class TestPrepareAbundanceProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_FIXTURE) as f:
            raw = json.load(f)
        abundances = _parse_hypatia_composition(raw)
        cls.result = prepare_abundance_profile({
            "star_name": "Tau Ceti", "properties": {}, "abundances": abundances,
        })

    def test_parallel_lists_aligned(self):
        r = self.result
        self.assertNotIn("error", r)
        n = len(r["elements"])
        self.assertGreater(n, 19)
        for key in ("names", "means", "stds", "categories", "colors"):
            self.assertEqual(len(r[key]), n, f"{key} length mismatch")

    def test_display_symbols_and_colors(self):
        r = self.result
        # ionized rendered with a space, not an underscore
        self.assertFalse(any("_II" in e for e in r["elements"]))
        for c in r["colors"]:
            self.assertTrue(c.startswith("#"))

    def test_error_passthrough(self):
        self.assertIn("error", prepare_abundance_profile({"error": "boom"}))
        self.assertIn("error", prepare_abundance_profile(
            {"star_name": "x", "abundances": []}))


if __name__ == "__main__":
    unittest.main()
