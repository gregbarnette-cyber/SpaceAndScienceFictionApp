"""tests/test_besancon.py — offline coverage for the Phase AM `besancon-query` (core/besancon.py).

Pure parsing + math + validation — NO network (matching astroquery's own choice to disable all live
Besançon testing). The output-parsing fixture is a REAL `m1612` header + data row captured from the
live UWS service 2026-07-23; the derived-summary math is checked on hand-built rows with known values.
A live end-to-end check is manual + opt-in (BESANCON_LIVE=1), never in CI.
"""

import os
import unittest

from core import besancon

# A real Besançon m1612 `output` header + one data row (captured live 2026-07-23). 49 columns.
_FIXTURE = (
    "#     V     B-V     U-B     V-I     V-K       mux       muy      HRV       UU      VV      WW"
    "       Px        Mv   CL Typ    Teff   logg  Pop  Age     Mass   Mbol    Radius   [M/H]    [a/Fe]"
    "  longitude   latitude   RAJ2000     DECJ2000   Dist     x_Gal    y_Gal    z_Gal     Av     errPx"
    "   errMux   errMuy   errHrv    errMv     errMass     errAge     errTeff    errLogg    errMet"
    "     errAlphaFe     errBand_V  errBand_B  errBand_U  errBand_I  errBand_K\n"
    "  10.824  0.781   0.527   0.943   2.097    -16.675    20.306    -0.29   -11.22    -1.14     3.50"
    "    0.01075   5.89  5 6.00    5127.  4.46   3  1.6853  0.723    5.465    0.903   0.186  -0.006"
    "    89.958382   44.937931  239.972229   58.276875   0.0930  -8.0000   0.0658   0.0807   0.049"
    "    0.0000     1.0000     1.0000     2.0000     0.0000     0.1000     0.1000    50.0000     0.1000"
    "     0.1000     0.0200     0.0411    -0.0068    -0.0078    -0.0296    -0.0293\n"
)


class ParseOutputTest(unittest.TestCase):
    def test_real_row_columns(self):
        header, rows = besancon._parse_besancon_output(_FIXTURE)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        # header/data align (49 columns each)
        self.assertEqual(len(header), 49)
        self.assertEqual(len(r), 49)
        self.assertAlmostEqual(r["V"], 10.824, places=3)
        self.assertAlmostEqual(r["Age"], 1.6853, places=4)     # Gyr
        self.assertAlmostEqual(r["Mass"], 0.723, places=3)     # M_sun
        self.assertEqual(int(r["Pop"]), 3)                     # thin disc
        self.assertAlmostEqual(r["[M/H]"], 0.186, places=3)
        self.assertAlmostEqual(r["Teff"], 5127.0, places=0)
        self.assertAlmostEqual(r["Dist"], 0.0930, places=4)    # kpc

    def test_blank_and_headerless_safe(self):
        self.assertEqual(besancon._parse_besancon_output(""), ([], []))
        self.assertEqual(besancon._parse_besancon_output("no header here\n1 2 3\n")[1], [])


class PopGroupTest(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(besancon._pop_group(1), "thin")
        self.assertEqual(besancon._pop_group(7), "thin")
        self.assertEqual(besancon._pop_group(8), "thick")
        self.assertEqual(besancon._pop_group(9), "halo")
        self.assertEqual(besancon._pop_group(10), "bulge")
        self.assertEqual(besancon._pop_group(11), "other")
        self.assertEqual(besancon._pop_group(None), "unknown")


class AgeDistTest(unittest.TestCase):
    ROWS = [
        {"Age": 1.0, "Mass": 0.5, "Pop": 3, "[M/H]": 0.0},
        {"Age": 1.0, "Mass": 0.6, "Pop": 3, "[M/H]": 0.1},
        {"Age": 8.0, "Mass": 0.8, "Pop": 8, "[M/H]": -0.5},    # thick
        {"Age": 12.0, "Mass": 0.7, "Pop": 9, "[M/H]": -1.5},   # halo
        {"Age": 2.0, "Mass": 1.2, "Pop": 1, "[M/H]": 0.05},    # thin
        {"Age": 5.0, "Mass": 0.9, "Pop": 10, "[M/H]": 0.2},    # bulge
    ]

    def test_summary_math(self):
        d = besancon.build_age_dist(self.ROWS)
        self.assertEqual(d["n_stars"], 6)
        self.assertAlmostEqual(d["mean_age_gyr"], 29.0 / 6, places=3)
        self.assertAlmostEqual(d["median_age_gyr"], 3.5, places=3)
        # the [1,2) Gyr age bin holds the two 1-Gyr stars
        b12 = next(b for b in d["histogram"] if b["lo"] == 1.0)
        self.assertEqual(b12["count"], 2)
        # population mix: thin=3/6, thick/halo/bulge = 1/6 each
        self.assertAlmostEqual(d["population_mix"]["thin"], 0.5, places=4)
        self.assertAlmostEqual(d["population_mix"]["thick"], 1 / 6, places=4)
        self.assertAlmostEqual(d["population_mix"]["halo"], 1 / 6, places=4)
        self.assertAlmostEqual(d["population_mix"]["bulge"], 1 / 6, places=4)
        self.assertEqual(d["population_by_pop_code"]["3"], 2)
        # feh mean over all six
        self.assertAlmostEqual(d["feh_mean"], (-1.65) / 6, places=4)
        # AMR: the oldest age band skews metal-poor
        old = [a for a in d["age_metallicity_relation"] if a["age_lo"] == 12.0]
        self.assertTrue(old and old[0]["mean_feh"] < -1.0)

    def test_empty(self):
        d = besancon.build_age_dist([])
        self.assertEqual(d["n_stars"], 0)
        self.assertIsNone(d["mean_age_gyr"])


class ValidationAndCredentialTest(unittest.TestCase):
    def setUp(self):
        # Ensure these tests never touch the network: drop creds so the flow stops at the cred gate,
        # and use invalid inputs that fail even earlier. Save/restore the real env.
        self._saved = {k: os.environ.get(k) for k in ("BESANCON_USER", "BESANCON_PASS")}
        os.environ.pop("BESANCON_USER", None)
        os.environ.pop("BESANCON_PASS", None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_missing_direction(self):
        r = besancon.besancon_query()          # no glon/glat, no --local
        self.assertIn("error", r)
        self.assertIn("--glon", r["error"])

    def test_area_cap(self):
        r = besancon.besancon_query(local=True, area_deg2=999)
        self.assertIn("error", r)
        self.assertIn("smallfield", r["error"])

    def test_bad_distance(self):
        r = besancon.besancon_query(local=True, dist_max_pc=0)
        self.assertIn("error", r)

    def test_missing_credentials(self):
        # valid inputs, but creds removed → curated credential error, no network
        r = besancon.besancon_query(local=True, area_deg2=1.0, dist_max_pc=100)
        self.assertIn("error", r)
        self.assertIn("BESANCON_USER", r["error"])
        self.assertIn("subscribe.php", r["error"])


if __name__ == "__main__":
    unittest.main()
