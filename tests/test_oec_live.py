# tests/test_oec_live.py — network test (auto-skipped when GitHub is unreachable).
#
# Verifies the live Open Exoplanet Catalogue download + parse still works and that
# compute_oec resolves real systems through the disk-cached loader. Pulls the
# ~1 MB systems.xml.gz once (cached under data/oec/ thereafter). Does NOT assert on
# exact catalogue contents beyond stable, well-known systems.

import unittest

from tests._netcheck import live_enabled, reachable
import core.databases as databases

_ONLINE = live_enabled() and reachable("github.com")


@unittest.skipUnless(_ONLINE, "GitHub unreachable — skipping OEC live test")
class OecLiveTests(unittest.TestCase):
    def test_load_and_resolve_real_systems(self):
        root, index = databases._load_oec()
        self.assertGreaterEqual(len(root), databases._OEC_MIN_SYSTEMS)

        # Alpha Centauri: three stars (A, B, Proxima) share one system tree.
        r = databases.compute_oec("Alpha Centauri", allow_simbad=False)
        self.assertNotIn("error", r)
        stars = []
        def walk(n):
            if n["tag"] == "star":
                stars.append(n)
            for c in n.get("children", []):
                walk(c)
        walk(r["system"])
        self.assertGreaterEqual(len(stars), 3)

    def test_alias_and_not_found(self):
        # HD alias resolves to a real system; a planetless star is absent.
        self.assertNotIn("error", databases.compute_oec("HD 186408", allow_simbad=False))
        r = databases.compute_oec("Delta Pavonis", allow_simbad=False)
        self.assertIn("error", r)
        self.assertIn("not in the Open Exoplanet Catalogue", r["error"])

    def test_circumbinary_attachment(self):
        r = databases.compute_oec_planet("Kepler-16 b")
        self.assertNotIn("error", r)
        self.assertEqual(r["attached_to"], "binary")

    def test_census_over_real_catalogue(self):
        # Phase 4: the §A structural evaluation computed live — planets attach to all
        # three parent kinds, and circumbinary/rogue systems exist (the rebuild lesson).
        c = databases.compute_oec_census()
        self.assertNotIn("error", c)
        self.assertGreaterEqual(c["n_systems"], databases._OEC_MIN_SYSTEMS)
        self.assertGreater(c["planet_attachment"]["star"], 0)
        self.assertGreater(c["planet_attachment"]["binary"], 0)   # circumbinary planets
        self.assertGreater(c["planet_attachment"]["system"], 0)   # rogue planets
        self.assertGreater(c["circumbinary_systems"], 0)
        self.assertGreater(c["rogue_systems"], 0)

    def test_search_circumbinary_finds_kepler16(self):
        r = databases.compute_oec_search(circumbinary=True, limit=500)
        self.assertNotIn("error", r)
        self.assertGreater(r["count"], 0)
        self.assertTrue(any((s.get("name") or "").startswith("Kepler-16")
                            for s in r["systems"]))

    def test_status_snapshot_over_real_catalogue(self):
        s = databases.compute_oec_status()
        self.assertNotIn("error", s)
        self.assertGreaterEqual(s["n_systems"], databases._OEC_MIN_SYSTEMS)
        self.assertTrue(s["cached"])   # _load_oec pulled/parsed the cache


if __name__ == "__main__":
    unittest.main()
