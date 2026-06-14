# tests/test_honorverse_expansion.py — Phase K Honorverse calculators (K0–K3).
#
# Pure math, offline (no DB, no network — the Honorverse tables are in-module
# constants; only compute_honorverse_hyper_limits reads the DB and is not under
# test here). Covers:
#   * K0 refactor parity — opt 15/16 output unchanged after centralization,
#   * K1 compute_hyper_translation_time,
#   * K2 compute_impeller_wedge,
#   * K3 compute_missile_intercept (in core.calculators).

import unittest

import core.science as science
import core.calculators as calc

_HOURS_PER_YEAR = 8765.8128


# ── K0: refactor parity ──────────────────────────────────────────────────────

class ParityTest(unittest.TestCase):

    def test_accel_table_strings_unchanged(self):
        at = science.compute_honorverse_acceleration_table()
        self.assertEqual(len(at), 6)
        self.assertEqual(at[0], {
            "mass_range": "0-79,999 (FG/DD)", "warship_normal": "550 g",
            "merchant_normal": "253 g", "warship_hyper": "5280 g",
            "merchant_hyper": "2429 g"})
        self.assertEqual(at[-1]["mass_range"], "7,000,000-8,499,999 (SD)")
        self.assertEqual(at[-1]["warship_normal"], "420 g")

    def test_effective_speed_shape(self):
        es = science.compute_honorverse_effective_speed()
        self.assertEqual(len(es["bands"]), 9)            # Alpha–Iota
        self.assertEqual(len(es["expanded_bands"]), 24)  # Alpha–Omega
        # Table 1 Iota is canon "unattainable" (0).
        iota = next(b for b in es["bands"] if b["band"] == "Iota")
        self.assertEqual(iota["warship_xc"], 0)
        self.assertEqual(iota["multiplier"], 6000)

    def test_expanded_internal_consistency(self):
        """merchant = warship × 5/6 for every band; Iota = 3600/3000; Omega = 9949.2/8291.0."""
        eb = science.compute_honorverse_effective_speed()["expanded_bands"]
        for b in eb:
            self.assertAlmostEqual(b["merchant_xc"], b["warship_xc"] * 5 / 6, places=1,
                                   msg=f"ratio off at {b['band']}")
        iota = next(b for b in eb if b["band"] == "Iota")
        self.assertEqual((iota["warship_xc"], iota["merchant_xc"]), (3600.0, 3000.0))
        self.assertEqual((eb[-1]["warship_xc"], eb[-1]["merchant_xc"]), (9949.2, 8291.0))


# ── K1: hyper translation time ───────────────────────────────────────────────

class HyperTranslationTimeTest(unittest.TestCase):

    def test_known_band_value(self):
        r = science.compute_hyper_translation_time(11.4, "warship")
        self.assertNotIn("error", r)
        self.assertEqual(len(r["bands"]), 24)
        alpha = r["bands"][0]
        self.assertEqual(alpha["speed_xc"], 37.2)
        self.assertAlmostEqual(alpha["speed_ly_hr"], 37.2 / _HOURS_PER_YEAR, places=9)
        self.assertAlmostEqual(alpha["travel_hours"], 11.4 / (37.2 / _HOURS_PER_YEAR), places=3)

    def test_ship_type_case_insensitive(self):
        self.assertNotIn("error", science.compute_hyper_translation_time(5, "WarShip"))

    def test_merchant_footnote(self):
        war = science.compute_hyper_translation_time(5, "warship")
        mer = science.compute_hyper_translation_time(5, "merchantship")
        self.assertIsNone(war["footnote"])           # warship bands carry no * note
        self.assertIsNotNone(mer["footnote"])        # merchant Epsilon+ are starred
        # merchant uses the merchant column
        self.assertEqual(mer["bands"][0]["speed_xc"], 31.0)

    def test_zero_speed_band_renders_na(self):
        # No 0-speed band in the 24-band table, so this is the defensive path:
        # confirm a real band never yields "N/A".
        r = science.compute_hyper_translation_time(5, "merchantship")
        self.assertTrue(all(b["travel_time"] != "N/A" for b in r["bands"]))

    def test_errors(self):
        self.assertIn("error", science.compute_hyper_translation_time(0, "warship"))
        self.assertIn("error", science.compute_hyper_translation_time(-3, "warship"))
        self.assertIn("error", science.compute_hyper_translation_time(5, "frigate"))


# ── K2: impeller wedge ───────────────────────────────────────────────────────

class ImpellerWedgeTest(unittest.TestCase):

    def test_band_selection_boundaries(self):
        # exact lower/upper boundary of the CL/CA band (80,000–499,999)
        self.assertEqual(science.compute_impeller_wedge(80000, "warship", 100)["mass_band"],
                         "80-499,999 (CL/CA)")
        self.assertEqual(science.compute_impeller_wedge(499999, "warship", 100)["mass_band"],
                         "80-499,999 (CL/CA)")
        # FG/DD top boundary
        self.assertEqual(science.compute_impeller_wedge(79999, "warship", 100)["mass_band"],
                         "0-79,999 (FG/DD)")

    def test_clamp_above_top_band(self):
        r = science.compute_impeller_wedge(9_000_000, "warship", 100)
        self.assertTrue(r["clamped"])
        self.assertEqual(r["mass_band"], "7,000,000-8,499,999 (SD)")

    def test_scaling(self):
        r = science.compute_impeller_wedge(50000, "warship", 50)   # FG/DD warship base 550
        self.assertEqual(r["base_accel_g"], 550)
        self.assertAlmostEqual(r["effective_accel_g"], 550 * 0.5)
        self.assertAlmostEqual(r["max_vel_normal_xc"], 0.8 * 0.5)   # warship cap 0.8c
        self.assertEqual(r["max_vel_hyper_xc"], r["max_vel_normal_xc"])

    def test_merchant_cap(self):
        r = science.compute_impeller_wedge(50000, "merchantship", 100)
        self.assertEqual(r["base_accel_g"], 253)                    # FG/DD merchant
        self.assertAlmostEqual(r["max_vel_normal_xc"], 0.6)         # merchant cap 0.6c

    def test_errors(self):
        self.assertIn("error", science.compute_impeller_wedge(0, "warship", 50))
        self.assertIn("error", science.compute_impeller_wedge(1000, "warship", 0))
        self.assertIn("error", science.compute_impeller_wedge(1000, "warship", 150))
        self.assertIn("error", science.compute_impeller_wedge(1000, "tugboat", 50))


# ── K3: missile intercept ────────────────────────────────────────────────────

class MissileInterceptTest(unittest.TestCase):

    def test_burn_phase_intercept(self):
        r = calc.compute_missile_intercept(0.3, 10000, 0.5, -0.2, 8)   # head-on, short range
        self.assertTrue(r["intercepts"])
        self.assertEqual(r["intercept_phase"], "burn")
        self.assertGreater(r["time_to_impact_s"], 0)
        self.assertAlmostEqual(r["v_burnout_xc"], 0.8, places=6)       # 0.3 + 0.5

    def test_coast_phase_intercept(self):
        r = calc.compute_missile_intercept(0.0, 5000, 0.3, 0.0, 50)    # stationary target, long range
        self.assertTrue(r["intercepts"])
        self.assertEqual(r["intercept_phase"], "coast")
        self.assertGreater(r["time_to_impact_s"], r["burn_duration_s"])

    def test_no_intercept_when_outrun(self):
        r = calc.compute_missile_intercept(0.3, 10000, 0.1, 0.7, 8)    # target faster than burnout
        self.assertFalse(r["intercepts"])
        self.assertIsNone(r["intercept_phase"])
        self.assertIsNone(r["time_to_impact_s"])
        self.assertLessEqual(r["v_close_xc"], 0)

    def test_head_on_faster_than_receding(self):
        head_on = calc.compute_missile_intercept(0.3, 8000, 0.4, -0.2, 30)
        receding = calc.compute_missile_intercept(0.3, 8000, 0.4, 0.2, 30)
        self.assertTrue(head_on["intercepts"])
        # head-on closes faster → strictly shorter time (or receding may miss entirely)
        if receding["intercepts"]:
            self.assertLess(head_on["time_to_impact_s"], receding["time_to_impact_s"])

    def test_errors(self):
        self.assertIn("error", calc.compute_missile_intercept(0.3, 10000, 0.5, 0, -1))
        self.assertIn("error", calc.compute_missile_intercept(0.3, 0, 0.5, 0, 8))
        self.assertIn("error", calc.compute_missile_intercept(0.3, 10000, 0, 0, 8))


if __name__ == "__main__":
    unittest.main()
