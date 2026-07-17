# tests/test_oec_live.py — network test (auto-skipped when GitHub is unreachable).
#
# Verifies the live Open Exoplanet Catalogue download + parse still works and that
# compute_oec resolves real systems through the disk-cached loader. Pulls the
# ~1 MB systems.xml.gz once (cached under data/oec/ thereafter). Does NOT assert on
# exact catalogue contents beyond stable, well-known systems.

import unittest

from tests._netcheck import reachable
import core.databases as databases

_ONLINE = reachable("github.com")


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


if __name__ == "__main__":
    unittest.main()
