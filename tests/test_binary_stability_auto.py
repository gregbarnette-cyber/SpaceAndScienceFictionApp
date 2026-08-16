# tests/test_binary_stability_auto.py — CR-3 auto-pipe binary-orbit → Holman-Wiegert (core).
#
# Offline tests monkeypatch binary.binary_orbit with synthetic solution dicts to exercise the
# tiered element extractor + the stability wiring; one live-gated anchor reproduces the 36 Oph card.

import math
import unittest
from unittest.mock import patch

import core.binary as binary
from tests._netcheck import live_enabled, reachable

_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


def _fake(solutions, sp_type=None, query="X"):
    return {"query": query, "identity": {"sp_type": sp_type, "ra": 1.0, "dec": 2.0},
            "solutions": solutions, "route_tried": ["gaia-nss:two_body_orbit", "sb9", "wds", "orb6"]}


def _run(fake, **kw):
    with patch("core.binary.binary_orbit", return_value=fake):
        return binary.binary_stability_auto(star="X", **kw)


class ElementExtractionTest(unittest.TestCase):
    def test_tier1_absolute_masses_plus_period(self):
        # M_tot=1.5, P=25.82 yr → a_bin ≈ 10 AU; test 0.5 AU S-type stable.
        p_d = math.sqrt(10.0 ** 3 / 1.5) * 365.25
        sol = {"source": "gaia-nss:two_body_orbit", "period_d": p_d, "eccentricity": 0.0,
               "grade": 50.0, "companion": {"m1_solar": 1.0, "m2_solar": 0.5, "method": "astrom"}}
        d = _run(_fake([sol]), test_sma_au=0.5)
        self.assertAlmostEqual(d["elements"]["sma_au"], 10.0, delta=0.05)
        self.assertEqual(d["elements"]["m2_solar"], 0.5)
        self.assertIn("companion classifier", d["elements"]["mass_basis"])
        self.assertEqual(d["test_verdict"], "stable")
        self.assertFalse(d["e_out_of_hw_range"])

    def test_tier2_sb2_mass_ratio(self):
        sol = {"source": "sb9", "period_d": 400.0, "eccentricity": 0.1, "grade": 4,
               "companion": {"method": "SB2", "mass_ratio_q": 0.8}}
        d = _run(_fake([sol], sp_type="G0V"))
        m1 = binary.m1_from_spectral_type("G0V")
        self.assertAlmostEqual(d["elements"]["m1_solar"], m1)
        self.assertAlmostEqual(d["elements"]["m2_solar"], m1 * 0.8)
        self.assertIn("SB2 mass ratio", d["elements"]["mass_basis"])

    def test_tier3_36oph_like_visual_equal_mass(self):
        # orb6 visual pair, no companion masses; K1V primary; P=471 yr; e=0.92 → the 36 Oph card.
        sol = {"source": "orb6", "period_d": None, "eccentricity": 0.92, "grade": 3,
               "visual_period": 471.0, "visual_period_unit": "y", "separation_arcsec": 4.5}
        d = _run(_fake([sol], sp_type="K1V"), test_sma_au=1.0)
        self.assertAlmostEqual(d["elements"]["m1_solar"], d["elements"]["m2_solar"])   # equal-mass
        self.assertTrue(48.0 <= d["elements"]["sma_au"] <= 75.0)                        # a ≈ 72 AU
        self.assertTrue(0.30 <= d["stype_critical_au"] <= 0.47)                         # S-type crit
        self.assertTrue(202.0 <= d["ptype_critical_au"] <= 316.0)                       # P-type crit
        self.assertEqual(d["test_verdict"], "unstable")                                 # 1 AU unstable
        self.assertTrue(d["e_out_of_hw_range"])                                         # e=0.92 > 0.8
        self.assertIn("equal-mass", d["elements"]["mass_basis"])


class HonestEmptyAndEdgeTest(unittest.TestCase):
    def test_no_solutions_is_honest_empty(self):
        d = _run(_fake([]))
        self.assertIsNone(d["elements"])
        self.assertIn("no orbital solution", d["note"])

    def test_wds_only_no_period_is_honest_empty(self):
        sol = {"source": "wds", "period_d": None, "eccentricity": None,
               "separation_arcsec": 3.0, "separation_au": 20.0, "companion": None}
        d = _run(_fake([sol], sp_type="K1V"))
        self.assertIsNone(d["elements"])
        self.assertIn("masses + period", d["note"])

    def test_test_sma_none_gives_crit_no_verdict(self):
        sol = {"source": "gaia-nss:two_body_orbit", "period_d": 3650.0, "eccentricity": 0.2,
               "companion": {"m1_solar": 1.0, "m2_solar": 0.8, "method": "astrom"}}
        d = _run(_fake([sol]))
        self.assertIsNotNone(d["stype_critical_au"])
        self.assertIsNone(d["test_verdict"])
        self.assertIsNone(d["orbit_type"])

    def test_ecc_assumed_when_absent(self):
        sol = {"source": "orb6", "eccentricity": None, "visual_period": 100.0,
               "visual_period_unit": "y", "companion": None}
        d = _run(_fake([sol], sp_type="G2V"))
        self.assertEqual(d["elements"]["ecc"], 0.0)
        self.assertIn("assumed circular", d["note"])

    def test_bad_test_sma_errors(self):
        self.assertIn("error", binary.binary_stability_auto(star="X", test_sma_au=0))

    def test_binary_orbit_error_propagates(self):
        with patch("core.binary.binary_orbit", return_value={"error": "unresolvable"}):
            self.assertIn("error", binary.binary_stability_auto(star="X"))

    def test_period_unit_conversion(self):
        self.assertAlmostEqual(binary._solution_period_yr(
            {"visual_period": 2.0, "visual_period_unit": "c"}), 200.0)   # centuries
        self.assertAlmostEqual(binary._solution_period_yr(
            {"period_d": 365.25}), 1.0)
        # orb6 'm' is MINUTES, not months: 525960 min = 1 yr.
        self.assertAlmostEqual(binary._solution_period_yr(
            {"visual_period": 525960.0, "visual_period_unit": "m"}), 1.0)


@unittest.skipUnless(_ONLINE, "SIMBAD/VizieR not reachable / SPACE_APP_RUN_LIVE unset")
class BinaryStabilityAutoLiveTest(unittest.TestCase):
    def test_36_ophiuchi_live_honest_null_or_card(self):
        # 36 Oph's visual orbit is NOT in a period-bearing route binary_orbit reaches (only WDS
        # projected separations; it is absent from orb6 even at a 0.2° cone), so the live bare-name
        # path correctly returns an HONEST NULL — find≠fabricate, not the 0.30–0.47 AU anchor. The
        # tier-3 anchor numbers are pinned offline (test_tier3_36oph_like_visual_equal_mass) and by
        # WB's manual binary-stability byte-match. This test accepts either outcome, both correct.
        d = binary.binary_stability_auto(star="36 Ophiuchi", test_sma_au=1.0)
        self.assertNotIn("error", d)
        if d.get("elements") is None:
            self.assertIsNotNone(d.get("note"))               # honest null, not a silent empty
            self.assertIsNone(d["stype_critical_au"])
        else:                                                  # if a period-bearing orbit is ever reached
            self.assertTrue(0.20 <= d["stype_critical_au"] <= 0.55)
            self.assertEqual(d["test_verdict"], "unstable")


if __name__ == "__main__":
    unittest.main()
