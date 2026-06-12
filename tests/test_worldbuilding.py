# tests/test_worldbuilding.py — offline coverage for the Phase H worldbuilding
# calculators in core/equations.py. Pure math — no network, no Qt, no DB.
#
# Anchored to the reference values verified in PHASE_H_PLAN.md, and locks the two
# formula corrections vs the future_phases brainstorm:
#   - Roche rigid coefficient = 1.26 (not 2.44)
#   - Binary P-type mass-ratio term = +4.12μ (not −4.12μ)

import unittest

from core import equations


class RocheLimitTest(unittest.TestCase):
    def test_earth_moon_reference(self):
        # Earth primary (ρ≈5.51) + Moon-density satellite (3.34 g/cm³).
        r = equations.compute_roche_limit(1.0, 3.34)
        self.assertAlmostEqual(r["primary_density_gcc"], 5.51, places=1)
        self.assertAlmostEqual(r["rigid_km"], 9487, delta=9487 * 0.01)
        self.assertAlmostEqual(r["fluid_km"], 18492, delta=18492 * 0.01)

    def test_rigid_less_than_fluid(self):
        # The 1.26-vs-2.456 correction: rigid must be well below fluid (≈ factor 1.95),
        # not nearly equal (which the erroneous 2.44/2.456 pair would give).
        r = equations.compute_roche_limit(1.0, 3.34)
        self.assertLess(r["rigid_km"], r["fluid_km"])
        self.assertAlmostEqual(r["fluid_km"] / r["rigid_km"], 2.456 / 1.26, places=3)

    def test_explicit_radius_used(self):
        r = equations.compute_roche_limit(1.0, 3.34, primary_radius_earth=1.0)
        self.assertAlmostEqual(r["primary_radius_km"], 6371.0, places=1)

    def test_au_conversion(self):
        r = equations.compute_roche_limit(1.0, 3.34)
        self.assertAlmostEqual(r["rigid_au"], r["rigid_km"] / 149_597_870.7, places=9)

    def test_error_paths(self):
        self.assertIn("error", equations.compute_roche_limit(-1, 3.34))
        self.assertIn("error", equations.compute_roche_limit(1, 0))
        self.assertIn("error", equations.compute_roche_limit(1, 3.34, primary_radius_earth=-1))


class HillSphereTest(unittest.TestCase):
    def test_earth_reference(self):
        h = equations.compute_hill_sphere(1.0, 1.0, 1.0, 0)
        self.assertAlmostEqual(h["hill_radius_km"], 1.496e6, delta=1.496e6 * 0.01)
        self.assertAlmostEqual(h["hill_radius_au"], 0.0100, places=3)
        self.assertAlmostEqual(h["stable_orbit_limit_km"], 7.48e5, delta=7.48e5 * 0.01)

    def test_stable_is_half_hill(self):
        h = equations.compute_hill_sphere(1.0, 1.0, 1.0, 0)
        self.assertAlmostEqual(h["stable_orbit_limit_km"], 0.5 * h["hill_radius_km"], places=6)

    def test_eccentricity_shrinks_hill(self):
        circ = equations.compute_hill_sphere(1.0, 1.0, 1.0, 0)
        ecc = equations.compute_hill_sphere(1.0, 1.0, 1.0, 0.5)
        self.assertAlmostEqual(ecc["hill_radius_km"], 0.5 * circ["hill_radius_km"], places=6)

    def test_error_paths(self):
        self.assertIn("error", equations.compute_hill_sphere(-1, 1, 1, 0))
        self.assertIn("error", equations.compute_hill_sphere(1, 1, 1, 1.0))
        self.assertIn("error", equations.compute_hill_sphere(1, 1, 1, -0.1))


class BinaryOrbitStabilityTest(unittest.TestCase):
    def test_critical_sma_reference(self):
        # μ=0.5, e=0 → stype ≈ 0.274·a_b, ptype ≈ 2.388·a_b.
        b = equations.compute_binary_orbit_stability(1.0, 1.0, 1.0, 0.5, 0)
        self.assertAlmostEqual(b["stype_critical_sma_au"], 0.274, places=3)
        self.assertAlmostEqual(b["ptype_critical_sma_au"], 2.388, places=3)

    def test_ptype_correction_positive(self):
        # A −4.12μ regression would drive the P-type critical SMA negative.
        b = equations.compute_binary_orbit_stability(1.0, 1.0, 20.0, 5.0, 0)
        self.assertGreater(b["ptype_critical_sma_au"], 0)

    def test_mass_ordering(self):
        # mass1 < mass2 input must be swapped so μ ≤ 0.5 and M1 ≥ M2.
        b = equations.compute_binary_orbit_stability(0.5, 1.0, 1.0, 0.1, 0)
        self.assertLessEqual(b["mass_ratio"], 0.5)
        self.assertEqual(b["mass1_solar"], 1.0)
        self.assertEqual(b["mass2_solar"], 0.5)

    def test_stype_stable_verdict(self):
        # Test SMA well inside the binary separation and below the S-type critical.
        b = equations.compute_binary_orbit_stability(1.0, 1.0, 20.0, 1.0, 0)
        self.assertEqual(b["orbit_type"], "S-type")
        self.assertTrue(b["is_stable"])

    def test_stype_unstable_verdict(self):
        # S-type region (test < binary/2) but beyond the S-type critical SMA.
        b = equations.compute_binary_orbit_stability(1.0, 1.0, 20.0, 9.0, 0)
        self.assertEqual(b["orbit_type"], "S-type")
        self.assertFalse(b["is_stable"])

    def test_ptype_stable_verdict(self):
        # Circumbinary region (test > binary/2) and beyond the P-type critical SMA.
        b = equations.compute_binary_orbit_stability(1.0, 1.0, 1.0, 5.0, 0)
        self.assertEqual(b["orbit_type"], "P-type")
        self.assertTrue(b["is_stable"])

    def test_error_paths(self):
        self.assertIn("error", equations.compute_binary_orbit_stability(-1, 1, 1, 1, 0))
        self.assertIn("error", equations.compute_binary_orbit_stability(1, 1, 1, 1, 1.0))


class AtmosphereRetentionTest(unittest.TestCase):
    def test_earth_escape_velocity(self):
        a = equations.compute_atmosphere_retention(1.0, 1.0, 255.0)
        self.assertAlmostEqual(a["v_escape_kms"], 11.19, places=1)

    def test_lambda_increases_with_mass(self):
        a = equations.compute_atmosphere_retention(1.0, 1.0, 255.0)
        lambdas = [g["lambda"] for g in a["gases"]]
        self.assertEqual(lambdas, sorted(lambdas))

    def test_co2_h2_ratio(self):
        a = equations.compute_atmosphere_retention(1.0, 1.0, 255.0)
        by = {g["gas"]: g["lambda"] for g in a["gases"]}
        self.assertAlmostEqual(by["CO2"] / by["H2"], 22.0, places=1)

    def test_status_matches_bucket(self):
        a = equations.compute_atmosphere_retention(1.0, 1.0, 255.0)
        for g in a["gases"]:
            lam = g["lambda"]
            expected = ("Retained" if lam > 6
                        else "Escaping slowly" if lam > 3
                        else "Lost rapidly")
            self.assertEqual(g["status"], expected, msg=g["gas"])

    def test_seven_gases(self):
        a = equations.compute_atmosphere_retention(1.0, 1.0, 255.0)
        self.assertEqual([g["gas"] for g in a["gases"]],
                         ["H2", "He", "CH4", "H2O", "N2", "O2", "CO2"])

    def test_error_paths(self):
        self.assertIn("error", equations.compute_atmosphere_retention(0, 1, 255))
        self.assertIn("error", equations.compute_atmosphere_retention(1, -1, 255))
        self.assertIn("error", equations.compute_atmosphere_retention(1, 1, 0))


class TidalLockingTest(unittest.TestCase):
    def test_finite_positive(self):
        t = equations.compute_tidal_locking_time(1.0, 0.0123, 384400, 24)
        self.assertGreater(t["lock_time_gyr"], 0)
        self.assertTrue(t["lock_time_years"] < float("inf"))

    def test_a6_dependence(self):
        # Doubling SMA multiplies lock time by 2^6 = 64.
        t1 = equations.compute_tidal_locking_time(1.0, 0.0123, 384400, 24)
        t2 = equations.compute_tidal_locking_time(1.0, 0.0123, 768800, 24)
        self.assertAlmostEqual(t2["lock_time_years"] / t1["lock_time_years"], 64.0, places=1)

    def test_defaults_echoed(self):
        t = equations.compute_tidal_locking_time(1.0, 0.0123, 384400, 24)
        self.assertEqual(t["rigidity_pa"], 3e10)
        self.assertEqual(t["tidal_q"], 100)

    def test_error_paths(self):
        self.assertIn("error", equations.compute_tidal_locking_time(-1, 0.01, 1e5, 24))
        self.assertIn("error", equations.compute_tidal_locking_time(1, 0.01, 1e5, 24, tidal_q=0))


if __name__ == "__main__":
    unittest.main()
