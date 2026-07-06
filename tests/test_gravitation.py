# tests/test_gravitation.py — Phase AE (Group K) core calculators.
#
# Offline golden-pin tests for core.gravitation: the corrected acceptance anchors from the
# request spec + the self-validating error matrix. No network, no Qt, no DB.

import math
import unittest

import core.gravitation as g


class EscapeVelocityTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(g.compute_escape_velocity(body="earth")["escape_velocity_kms"], 11.19, delta=0.01)
        self.assertAlmostEqual(g.compute_escape_velocity(body="sun")["escape_velocity_kms"], 617.7, delta=0.3)
        self.assertAlmostEqual(g.compute_escape_velocity(body="jupiter")["escape_velocity_kms"], 59.5, delta=0.1)

    def test_specific_energy_and_circular(self):
        d = g.compute_escape_velocity(body="earth")
        self.assertAlmostEqual(d["specific_energy_j_per_kg"], 6.26e7, delta=1e5)
        self.assertAlmostEqual(d["circular_velocity_kms"], d["escape_velocity_kms"] / math.sqrt(2), places=6)
        self.assertEqual(d["body"], "Earth")
        self.assertGreater(d["escape_velocity_c"], 0)

    def test_explicit_matches_preset(self):
        d = g.compute_escape_velocity(mass_mearth=1.0, radius_rearth=1.0)
        self.assertAlmostEqual(d["escape_velocity_kms"], 11.19, delta=0.01)
        self.assertIsNone(d["body"])

    def test_errors(self):
        self.assertIn("error", g.compute_escape_velocity())                                  # nothing
        self.assertIn("error", g.compute_escape_velocity(mass_mearth=1.0))                    # no radius
        self.assertIn("error", g.compute_escape_velocity(body="earth", mass_kg=1.0))          # body+explicit
        self.assertIn("error", g.compute_escape_velocity(mass_kg=1.0, mass_msun=1.0, radius_m=1.0))  # 2 mass units
        self.assertIn("error", g.compute_escape_velocity(mass_kg=-1.0, radius_m=1.0))         # negative


class GravitationalPotentialTest(unittest.TestCase):
    def test_anchors(self):
        e = g.compute_gravitational_potential(body="earth", r_from_m=6.371e6)
        self.assertAlmostEqual(e["well_depth_j_per_kg"], 6.26e7, delta=1e5)
        self.assertAlmostEqual(e["delta_v_kms"], 11.19, delta=0.01)
        self.assertLess(e["potential_j_per_kg"], 0)
        s = g.compute_gravitational_potential(body="sun", r_from_m=6.957e8)
        self.assertAlmostEqual(s["well_depth_j_per_kg"], 1.91e11, delta=1e9)

    def test_payload_and_finite_r_to(self):
        d = g.compute_gravitational_potential(body="earth", r_from_m=6.371e6, r_to_m=6.371e7,
                                              payload_kg=1000.0)
        self.assertAlmostEqual(d["binding_energy_j"], 1000.0 * d["well_depth_j_per_kg"], places=3)
        self.assertLess(d["well_depth_j_per_kg"], 6.26e7)   # not all the way to infinity
        self.assertEqual(d["r_to_m"], 6.371e7)

    def test_errors(self):
        self.assertIn("error", g.compute_gravitational_potential(body="earth"))                  # no r-from
        self.assertIn("error", g.compute_gravitational_potential(r_from_m=1e7))                   # no mass
        self.assertIn("error", g.compute_gravitational_potential(body="earth", r_from_m=1e7, r_from_au=1))  # 2 units
        self.assertIn("error", g.compute_gravitational_potential(body="earth", r_from_m=1e7, payload_kg=-1))


class SphereOfInfluenceTest(unittest.TestCase):
    def test_anchors(self):
        e = g.compute_sphere_of_influence(body_mass_mearth=1.0, primary="sun", semimajor_au=1.0)
        self.assertAlmostEqual(e["soi_laplace_au"], 0.00618, delta=1e-4)
        self.assertAlmostEqual(e["hill_radius_au"], 0.0100, delta=1e-4)
        self.assertAlmostEqual(e["soi_laplace_km"], 0.924e6, delta=5e3)
        j = g.compute_sphere_of_influence(body_mass_mjup=1.0, primary="sun", semimajor_au=5.2)
        self.assertAlmostEqual(j["soi_laplace_km"], 4.82e7, delta=5e5)

    def test_ratio_and_explicit_primary(self):
        d = g.compute_sphere_of_influence(body_mass_mearth=1.0, primary_mass_msun=1.0, semimajor_au=1.0)
        self.assertAlmostEqual(d["ratio_soi_hill"], d["soi_laplace_au"] / d["hill_radius_au"], places=9)
        self.assertIsNone(d["primary"])

    def test_errors(self):
        self.assertIn("error", g.compute_sphere_of_influence(primary="sun", semimajor_au=1.0))          # no body mass
        self.assertIn("error", g.compute_sphere_of_influence(body_mass_mearth=1.0, semimajor_au=1.0))   # no primary
        self.assertIn("error", g.compute_sphere_of_influence(body_mass_mearth=1.0, primary="sun"))      # no sma
        self.assertIn("error", g.compute_sphere_of_influence(body_mass_mearth=1.0, primary="sun", semimajor_au=0))


class HyperbolicApproachTest(unittest.TestCase):
    def test_anchor(self):
        d = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_km=6771.0)
        self.assertAlmostEqual(d["v_periapsis_kms"], 11.26, delta=0.02)
        self.assertAlmostEqual(d["capture_delta_v_kms"], 3.59, delta=0.02)
        self.assertAlmostEqual(d["c3_km2s2"], 9.0, delta=0.01)

    def test_arrival_speed_mode(self):
        # v∞ derived from arrival speed at r_from should reproduce a direct v∞ run
        ref = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_km=6771.0)
        # arrival speed at 1e6 km: v_arr = sqrt(v_inf^2 + 2GM/r) ; pick r and back-derive
        import core.astro_bodies as ab
        M = ab.body_preset("earth")["mass_kg"]
        from core.equations import _G
        r = 1.0e9  # 1e6 km in m
        v_arr = math.sqrt(3000.0 ** 2 + 2 * _G * M / r) / 1000.0
        d = g.compute_hyperbolic_approach(body="earth", arrival_speed_kms=v_arr, r_from_km=1.0e6,
                                          periapsis_km=6771.0)
        self.assertAlmostEqual(d["v_infinity_kms"], ref["v_infinity_kms"], delta=0.01)

    def test_parabolic_and_elliptical_targets(self):
        para = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_km=6771.0,
                                             target="parabolic")
        circ = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_km=6771.0)
        # parabolic capture leaves a barely-bound orbit → smaller Δv than capture-to-circular
        self.assertLess(para["capture_delta_v_kms"], circ["capture_delta_v_kms"])
        ell = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_km=6771.0,
                                            target="elliptical", target_apoapsis_km=100000.0)
        self.assertGreater(ell["capture_delta_v_kms"], para["capture_delta_v_kms"])

    def test_periapsis_rbody(self):
        d = g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3.0, periapsis_rbody=1.0)
        self.assertGreater(d["v_periapsis_kms"], 0)

    def test_errors(self):
        base = dict(body="earth", periapsis_km=6771.0)
        self.assertIn("error", g.compute_hyperbolic_approach(**base))                              # no v mode
        self.assertIn("error", g.compute_hyperbolic_approach(v_infinity_kms=3, arrival_speed_kms=5, **base))  # both v modes
        self.assertIn("error", g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3))      # no periapsis
        self.assertIn("error", g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3,
                                                             periapsis_km=6771, periapsis_rbody=1))  # both periapsis
        self.assertIn("error", g.compute_hyperbolic_approach(mass_mearth=1.0, v_infinity_kms=3,
                                                             periapsis_rbody=1))                    # rbody w/o radius
        self.assertIn("error", g.compute_hyperbolic_approach(body="earth", arrival_speed_kms=1.0,
                                                             r_from_km=6771, periapsis_km=6771))    # bound arrival
        self.assertIn("error", g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3,
                                                             periapsis_km=6771, target="elliptical"))  # no apoapsis
        self.assertIn("error", g.compute_hyperbolic_approach(body="earth", v_infinity_kms=3,
                                                             periapsis_km=6771, target="elliptical",
                                                             target_apoapsis_km=1000))             # apoapsis < periapsis


if __name__ == "__main__":
    unittest.main()
