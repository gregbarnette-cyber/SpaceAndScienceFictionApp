# tests/test_hypatia_live.py — network tests (skipped automatically when offline).
#   - element drift: hardcoded request set == live /element endpoint
#   - end-to-end compute_hypatia_data returns the expanded set
import unittest

from tests._netcheck import hypatia_reachable
from core.hypatia_elements import HYPATIA_REQUEST_SYMBOLS, SPECIES_BY_SYMBOL

_ONLINE = hypatia_reachable()
_BASE = "https://hypatiacatalog.com/hypatia/api/v2"


@unittest.skipUnless(_ONLINE, "Hypatia Catalog not reachable")
class TestHypatiaLive(unittest.TestCase):
    def test_element_set_matches_api(self):
        import requests
        r = requests.get(f"{_BASE}/element", timeout=30)
        r.raise_for_status()
        api_set = {str(s).strip() for s in r.json()}
        self.assertEqual(set(HYPATIA_REQUEST_SYMBOLS), api_set,
                         "hardcoded species set drifted from the live API")

    def test_compute_expands_beyond_19(self):
        import core.databases as db
        res = db.compute_hypatia_data({"designations": {"HIP": "HIP 8102"},
                                       "main_id": "* tau Cet"})
        self.assertNotIn("error", res)
        ab = res.get("abundances", [])
        self.assertGreater(len(ab), 19, "expansion did not take effect")
        master = set(SPECIES_BY_SYMBOL)
        for a in ab:
            self.assertIn(a["element"].lower(), master)
            self.assertTrue(a["category"])
        self.assertTrue(res.get("properties"))

    def test_unknown_star_is_graceful(self):
        import core.databases as db
        res = db.compute_hypatia_data(
            {"designations": {}, "main_id": "ZZ Not A Real Star 999999"})
        # Either an error dict or empty abundances — never a crash.
        self.assertTrue("error" in res or res.get("abundances") == [])


if __name__ == "__main__":
    unittest.main()
