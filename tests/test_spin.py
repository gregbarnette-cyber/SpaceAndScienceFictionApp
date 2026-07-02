# tests/test_spin.py — Phase W rotating-habitat comfort calculator (core, in-process).
#
# Covers core/spin.py + core/spin_tables.py: the request's acceptance cases A/B/C, all six
# anchor pairings, the solve-consistency case, the validation matrix, overrides, single-tier
# selection, determinism, and the bundled-band golden pin. Pure math, offline (no network/DB/Qt).
# Constants: g0 = 9.80665, occupant height h = 1.8 m, walk speed u = 1.0 m/s.

import math
import unittest

import core.spin as spin
import core.spin_tables as spin_tables

_G0 = 9.80665


class AcceptanceCaseTest(unittest.TestCase):
    def test_case_a_large_ring(self):
        d = spin.compute_spin_comfort(radius_m=224, rpm=2.0)
        self.assertNotIn("error", d)
        self.assertAlmostEqual(d["accel_ms2"], 9.8257, places=3)
        self.assertAlmostEqual(d["gravity_g"], 1.0019, places=3)
        self.assertAlmostEqual(d["tangential_velocity_ms"], 46.91, places=1)
        self.assertAlmostEqual(d["gravity_gradient_pct"], 0.80, places=2)
        self.assertAlmostEqual(d["head_gravity_g"], 0.994, places=3)
        self.assertAlmostEqual(d["coriolis_ratio_pct"], 4.26, places=2)
        self.assertEqual(d["anchors"], ["radius_m", "rpm"])
        # Conservative tier passes all checks (incl. max-gravity via _BAND_TOL on 1.0019 g).
        self.assertIs(d["criteria"]["conservative"]["pass"], True)

    def test_case_b_small_drum(self):
        # --gravity-g 1.0 arrives at the core as accel_ms2 = g0.
        d = spin.compute_spin_comfort(radius_m=10, accel_ms2=_G0)
        self.assertAlmostEqual(d["rpm"], 9.457, places=2)
        self.assertAlmostEqual(d["tangential_velocity_ms"], 9.90, places=2)
        self.assertAlmostEqual(d["gravity_gradient_pct"], 18.0, places=1)
        self.assertAlmostEqual(d["head_gravity_g"], 0.820, places=3)
        self.assertAlmostEqual(d["coriolis_ratio_pct"], 20.2, places=1)
        self.assertIs(d["criteria"]["conservative"]["pass"], False)
        self.assertIs(d["criteria"]["relaxed"]["pass"], False)  # RPM 9.46 > 6
        checks = d["criteria"]["conservative"]["checks"]
        self.assertIs(checks["max_rpm"]["pass"], False)
        self.assertIs(checks["max_gradient_pct"]["pass"], False)
        # Reconciliation #2: 20.2% < 25% cap → Coriolis PASSES (the request prose's
        # "coriolis fail" is imprecise; the tier still FAILs on rpm + gradient).
        self.assertIs(checks["max_coriolis_pct"]["pass"], True)

    def test_case_c_mid_ring(self):
        d = spin.compute_spin_comfort(radius_m=56, rpm=4.0)
        self.assertAlmostEqual(d["accel_ms2"], 9.8257, places=3)
        self.assertAlmostEqual(d["gravity_g"], 1.0019, places=3)
        self.assertAlmostEqual(d["tangential_velocity_ms"], 23.46, places=1)
        self.assertAlmostEqual(d["gravity_gradient_pct"], 3.21, places=2)
        self.assertAlmostEqual(d["head_gravity_g"], 0.970, places=3)
        self.assertAlmostEqual(d["coriolis_ratio_pct"], 8.53, places=2)
        self.assertIs(d["criteria"]["conservative"]["pass"], False)  # RPM 4 > 2
        # Reconciliation #1: moderate/relaxed PASS despite 1.0019 g > 1.0 ceiling (_BAND_TOL).
        self.assertIs(d["criteria"]["moderate"]["pass"], True)
        self.assertIs(d["criteria"]["relaxed"]["pass"], True)


class SolveTest(unittest.TestCase):
    def test_six_pairings_consistent(self):
        # All six anchor pairs drawn from the Case A design recover the same (ω, r).
        ref = spin.compute_spin_comfort(radius_m=224, rpm=2.0)
        r, omega = ref["radius_m"], ref["angular_velocity_rads"]
        a, v, rpm = ref["accel_ms2"], ref["tangential_velocity_ms"], ref["rpm"]
        pairs = [
            {"radius_m": r, "rpm": rpm},
            {"radius_m": r, "accel_ms2": a},
            {"radius_m": r, "tangential_velocity_ms": v},
            {"rpm": rpm, "accel_ms2": a},
            {"rpm": rpm, "tangential_velocity_ms": v},
            {"accel_ms2": a, "tangential_velocity_ms": v},
        ]
        for kwargs in pairs:
            d = spin.compute_spin_comfort(**kwargs)
            self.assertNotIn("error", d, kwargs)
            self.assertAlmostEqual(d["angular_velocity_rads"], omega, places=6, msg=str(kwargs))
            self.assertAlmostEqual(d["radius_m"], r, places=4, msg=str(kwargs))

    def test_solve_consistency_velocity_floor_blows_rpm(self):
        # Meeting the 6 m/s tangential floor at 1 g alone still blows the RPM ceiling.
        d = spin.compute_spin_comfort(accel_ms2=_G0, tangential_velocity_ms=6)
        self.assertAlmostEqual(d["radius_m"], 3.67, places=2)
        self.assertAlmostEqual(d["rpm"], 15.6, places=1)


class ValidationTest(unittest.TestCase):
    def test_matrix(self):
        bad = [
            dict(radius_m=10, rpm=2, occupant_height_m=12),      # h >= r
            dict(radius_m=10, rpm=2, tangential_velocity_ms=5),  # three anchors
            dict(radius_m=10),                                    # one anchor
            dict(),                                               # zero anchors
            dict(radius_m=0, rpm=2),                              # non-positive anchor
            dict(radius_m=10, rpm=-1),                            # negative anchor
            dict(radius_m=10, rpm=2, walk_speed_ms=0),            # non-positive walk speed
            dict(radius_m=10, rpm=2, occupant_height_m=0),        # non-positive height
            dict(radius_m=10, rpm=2, max_rpm=0),                  # non-positive override
            dict(radius_m=10, rpm=2, max_gradient_pct=150),       # percentage > 100
            dict(radius_m=10, rpm=2, criteria="bogus"),           # bad criteria selector
        ]
        for kwargs in bad:
            d = spin.compute_spin_comfort(**kwargs)
            self.assertIn("error", d, kwargs)

    def test_derived_radius_height_guard(self):
        # h < r must use the SOLVED radius: v²/a gives a tiny radius here.
        d = spin.compute_spin_comfort(accel_ms2=_G0, tangential_velocity_ms=6, occupant_height_m=5)
        self.assertIn("error", d)  # solved r ≈ 3.67 m < 5 m head height


class OverrideTest(unittest.TestCase):
    def test_override_flips_verdict(self):
        base = spin.compute_spin_comfort(radius_m=56, rpm=4.0)
        self.assertIs(base["criteria"]["conservative"]["pass"], False)  # 4 > 2
        self.assertEqual(base["overridden_thresholds"], [])
        d = spin.compute_spin_comfort(radius_m=56, rpm=4.0, max_rpm=10)
        self.assertIs(d["criteria"]["conservative"]["pass"], True)
        self.assertEqual(d["overridden_thresholds"], ["max_rpm"])
        self.assertEqual(d["criteria"]["conservative"]["checks"]["max_rpm"]["threshold"], 10)


class SelectorTest(unittest.TestCase):
    def test_single_tier(self):
        d = spin.compute_spin_comfort(radius_m=224, rpm=2.0, criteria="moderate")
        self.assertEqual(set(d["criteria"].keys()), {"moderate"})

    def test_null_threshold_reports_pass_none(self):
        d = spin.compute_spin_comfort(radius_m=224, rpm=2.0)
        # relaxed tier: max_gravity_g / min_tangential / max_coriolis are None → pass None.
        relaxed = d["criteria"]["relaxed"]["checks"]
        self.assertIsNone(relaxed["max_gravity_g"]["threshold"])
        self.assertIsNone(relaxed["max_gravity_g"]["pass"])
        self.assertIsNone(relaxed["max_coriolis_pct"]["pass"])


class DeterminismAndTableTest(unittest.TestCase):
    def test_determinism(self):
        a = spin.compute_spin_comfort(radius_m=100, rpm=3)
        b = spin.compute_spin_comfort(radius_m=100, rpm=3)
        self.assertEqual(a, b)

    def test_bands_golden_pin(self):
        # The bundled bands are the request's numbers, verbatim (drift guard).
        self.assertEqual(spin_tables._COMFORT_BANDS, {
            "conservative": {"max_rpm": 2.0, "min_gravity_g": 0.30, "max_gravity_g": 1.0,
                             "min_tangential_velocity_ms": 6.0, "max_gradient_pct": 10.0,
                             "max_coriolis_pct": 25.0},
            "moderate":     {"max_rpm": 4.0, "min_gravity_g": 0.20, "max_gravity_g": 1.0,
                             "min_tangential_velocity_ms": 3.0, "max_gradient_pct": 15.0,
                             "max_coriolis_pct": 25.0},
            "relaxed":      {"max_rpm": 6.0, "min_gravity_g": 0.10, "max_gravity_g": None,
                             "min_tangential_velocity_ms": None, "max_gradient_pct": 25.0,
                             "max_coriolis_pct": None},
        })


if __name__ == "__main__":
    unittest.main()
