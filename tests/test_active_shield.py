# tests/test_active_shield.py — Phase AD (C8) active magnetic-shield rigidity cutoff.
#
# In-process: the Störmer-cutoff Earth cross-check anchor, the three field sources,
# the deflected-fraction model (monotone in R_c, ∈[0,1]), the validation matrix, and
# determinism. Pure math — offline, no DB/network/RNG.

import math
import unittest

import core.active_shield as a


class ActiveShieldAnchorTest(unittest.TestCase):
    def test_earth_stormer_cross_check(self):
        # m ≈ 8e22 A·m², r = R⊕ = 6.371e6 m → equatorial cutoff ≈ 14.8 GV (measured).
        r = a.compute_active_shield(shield_radius_m=6.371e6, magnetic_moment_am2=8e22)
        self.assertAlmostEqual(r["rigidity_cutoff_gv"], 14.8, delta=0.3)
        self.assertTrue(r["is_order_of_magnitude"])

    def test_coil_and_field_sources_agree(self):
        # coil m = I·π·R²; field source m = 4π r₀³ B/μ₀. Pick both to give the same moment.
        from core.equations import _MU_0
        r0 = 10.0
        b = 5.0
        m_field = 4.0 * math.pi * r0 ** 3 * b / _MU_0
        i = m_field / (math.pi * r0 ** 2)
        by_coil = a.compute_active_shield(shield_radius_m=r0, coil_current_a=i, coil_radius_m=r0)
        by_field = a.compute_active_shield(shield_radius_m=r0, field_tesla=b, field_radius_m=r0)
        by_moment = a.compute_active_shield(shield_radius_m=r0, magnetic_moment_am2=m_field)
        self.assertAlmostEqual(by_coil["rigidity_cutoff_gv"], by_field["rigidity_cutoff_gv"], places=6)
        self.assertAlmostEqual(by_coil["rigidity_cutoff_gv"], by_moment["rigidity_cutoff_gv"], places=6)

    def test_field_at_radius(self):
        from core.equations import _MU_0
        r = a.compute_active_shield(shield_radius_m=10.0, magnetic_moment_am2=1e10)
        expected = _MU_0 * 1e10 / (4.0 * math.pi * 10.0 ** 3)
        self.assertAlmostEqual(r["magnetic_field_t"], expected, places=9)

    def test_cutoff_scales_inverse_r2(self):
        near = a.compute_active_shield(shield_radius_m=10.0, magnetic_moment_am2=1e12)
        far = a.compute_active_shield(shield_radius_m=20.0, magnetic_moment_am2=1e12)
        self.assertAlmostEqual(near["rigidity_cutoff_gv"] / far["rigidity_cutoff_gv"], 4.0, places=6)


class DeflectedFractionTest(unittest.TestCase):
    def test_none_without_spectrum(self):
        r = a.compute_active_shield(shield_radius_m=10.0, magnetic_moment_am2=5e10)
        self.assertIsNone(r["deflected_fraction"])

    def test_fraction_in_range_and_monotone(self):
        weak = a.compute_active_shield(shield_radius_m=10.0, magnetic_moment_am2=1e10,
                                       spectrum_characteristic_rigidity_gv=1.0)
        strong = a.compute_active_shield(shield_radius_m=10.0, magnetic_moment_am2=1e11,
                                         spectrum_characteristic_rigidity_gv=1.0)
        for r in (weak, strong):
            self.assertGreaterEqual(r["deflected_fraction"], 0.0)
            self.assertLess(r["deflected_fraction"], 1.0)
        # a stronger field (higher R_c) deflects a larger fraction
        self.assertGreater(strong["deflected_fraction"], weak["deflected_fraction"])


class ValidationTest(unittest.TestCase):
    def test_matrix(self):
        for kw in (
            {"magnetic_moment_am2": 1e10},                                       # no shield radius
            {"shield_radius_m": 0, "magnetic_moment_am2": 1e10},                 # radius ≤ 0
            {"shield_radius_m": 10},                                             # no field source
            {"shield_radius_m": 10, "magnetic_moment_am2": 1e10,
             "coil_current_a": 1, "coil_radius_m": 1},                          # two field sources
            {"shield_radius_m": 10, "coil_current_a": 1},                        # partial coil
            {"shield_radius_m": 10, "magnetic_moment_am2": -1},                  # neg moment
            {"shield_radius_m": 10, "field_tesla": 5},                           # partial field
            {"shield_radius_m": 10, "magnetic_moment_am2": 1e10,
             "spectrum_characteristic_rigidity_gv": 0},                          # R_s ≤ 0
        ):
            self.assertIn("error", a.compute_active_shield(**kw), kw)


class DeterminismTest(unittest.TestCase):
    def test_deterministic(self):
        kw = dict(shield_radius_m=10.0, magnetic_moment_am2=5e10,
                  spectrum_characteristic_rigidity_gv=1.0)
        self.assertEqual(a.compute_active_shield(**kw), a.compute_active_shield(**kw))


if __name__ == "__main__":
    unittest.main()
