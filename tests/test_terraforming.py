# tests/test_terraforming.py — Phase AB planetary energy-balance / terraforming (core).
#
# In-process tests for core.terraforming (J1 equilibrium-temp, J2 insolation-shift,
# J3 atmosphere-mass), offline. Phase-N/T/V/W/X/AA lineage: acceptance anchors +
# forcing forms + inverse solves + mirror/shade signs + mass↔pressure round-trips +
# the validation matrix + determinism. All three are textbook closed forms over the
# constants in core.equations; the anchors below were hand-verified against the
# Group-J spec (Earth/Mars T_eq, Mars atmosphere mass).

import unittest

import core.terraforming as tf


class EquilibriumTempTest(unittest.TestCase):
    def test_earth_anchor(self):
        r = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3, greenhouse_delta_k=33)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["t_eq_k"], 255.0, delta=1.0)
        self.assertAlmostEqual(r["t_surface_k"], 288.0, delta=1.0)
        self.assertEqual(r["greenhouse_delta_k"], 33.0)
        self.assertIsNone(r["optical_depth"])
        self.assertEqual(r["regime"], "offset")

    def test_mars_anchor(self):
        r = tf.compute_equilibrium_temp(insolation_wm2=589, albedo=0.25, greenhouse_delta_k=0)
        self.assertAlmostEqual(r["t_eq_k"], 210.0, delta=1.0)
        self.assertEqual(r["regime"], "offset")

    def test_airless_anchor(self):
        # B — no forcing form → bare airless equilibrium, t_surface = t_eq, no error.
        r = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["t_eq_k"], 254.6, delta=0.5)
        self.assertEqual(r["t_surface_k"], r["t_eq_k"])
        self.assertEqual(r["regime"], "airless")
        self.assertIsNone(r["greenhouse_delta_k"])
        self.assertIsNone(r["optical_depth"])
        self.assertIsNone(r["required_forcing"])

    def test_airless_mars(self):
        r = tf.compute_equilibrium_temp(insolation_wm2=589, albedo=0.25)
        self.assertAlmostEqual(r["t_eq_k"], 210.1, delta=0.5)
        self.assertEqual(r["t_surface_k"], r["t_eq_k"])
        self.assertEqual(r["regime"], "airless")

    def test_grey_atmosphere_form(self):
        # τ ≈ 0.851 reproduces Earth's 288 K surface from T_eq ≈ 255 K.
        r = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3, optical_depth=0.851)
        self.assertAlmostEqual(r["t_surface_k"], 288.0, delta=0.5)
        self.assertEqual(r["optical_depth"], 0.851)
        self.assertIsNone(r["greenhouse_delta_k"])
        self.assertEqual(r["regime"], "grey")

    def test_inverse_target(self):
        # Inverse: 288 K target → required ΔT ≈ 33 K and the equivalent τ ≈ 0.85.
        r = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3, target_surface_k=288)
        self.assertAlmostEqual(r["t_surface_k"], 288.0, places=6)
        self.assertEqual(r["regime"], "inverse")
        rf = r["required_forcing"]
        self.assertAlmostEqual(rf["greenhouse_delta_k"], 33.0, delta=1.0)
        self.assertAlmostEqual(rf["optical_depth"], 0.851, delta=0.01)
        self.assertFalse(rf["cooling_required"])

    def test_inverse_cooling_flag(self):
        # A target below the bare equilibrium needs cooling → negative forcing, flagged.
        r = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3, target_surface_k=200)
        rf = r["required_forcing"]
        self.assertLess(rf["greenhouse_delta_k"], 0)
        self.assertLess(rf["optical_depth"], 0)
        self.assertTrue(rf["cooling_required"])

    def test_lum_dist_source_parity(self):
        r = tf.compute_equilibrium_temp(luminosity_lsun=1.0, distance_au=1.0, albedo=0.3,
                                        greenhouse_delta_k=0)
        self.assertAlmostEqual(r["insolation_wm2"], 1361.0, delta=2.0)
        self.assertAlmostEqual(r["t_eq_k"], 255.0, delta=1.0)


class InsolationShiftTest(unittest.TestCase):
    def test_mirror_and_shade_sign(self):
        warm = tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=20,
                                           solar_flux_wm2=589)
        cool = tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=-20,
                                           solar_flux_wm2=589)
        self.assertEqual(warm["mode"], "mirror")
        self.assertEqual(cool["mode"], "shade")
        # Area is a magnitude — same |ΔS| → same area regardless of sign.
        self.assertAlmostEqual(warm["mirror_area_m2"], cool["mirror_area_m2"], places=3)

    def test_mars_order_of_magnitude(self):
        # A_m = |ΔS|·4πR²/solar_flux;  4πR²(Mars) ≈ 1.44e14 m².
        r = tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=20,
                                        solar_flux_wm2=589)
        expected = 20 * 1.444e14 / 589
        self.assertAlmostEqual(r["mirror_area_m2"], expected, delta=expected * 0.01)
        # cross-section ratio = 4·|ΔS|/solar_flux (sphere/cross-section = 4).
        self.assertAlmostEqual(r["area_vs_planet_cross_section"], 4 * 20 / 589, delta=1e-4)

    def test_lum_dist_source(self):
        r = tf.compute_insolation_shift(planet_radius_km=6371, delta_insolation_wm2=10,
                                        luminosity_lsun=1.0, distance_au=1.0)
        self.assertAlmostEqual(r["solar_flux_wm2"], 1361.0, delta=2.0)


class AtmosphereMassTest(unittest.TestCase):
    def test_mars_1bar_anchor(self):
        r = tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                       pressure_bar=1)
        self.assertAlmostEqual(r["atmosphere_mass_kg"], 3.9e18, delta=0.1e18)
        self.assertAlmostEqual(r["atmosphere_mass_earth_atm"], 0.76, delta=0.02)

    def test_mass_pressure_round_trip(self):
        fwd = tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                         pressure_bar=1)
        inv = tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                         volatile_mass_kg=fwd["atmosphere_mass_kg"])
        self.assertAlmostEqual(inv["surface_pressure_bar"], 1.0, places=6)

    def test_gravity_from_mass(self):
        # Mars ≈ 0.107 M⊕ at R 3390 km → g ≈ 3.71 (matches an explicit g).
        gm = tf.compute_atmosphere_mass(planet_radius_km=3390, planet_mass_earth=0.107,
                                        pressure_bar=1)
        gexp = tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                          pressure_bar=1)
        self.assertAlmostEqual(gm["surface_gravity_ms2"], 3.71, delta=0.02)
        self.assertAlmostEqual(gm["atmosphere_mass_kg"], gexp["atmosphere_mass_kg"],
                               delta=gexp["atmosphere_mass_kg"] * 0.01)

    def test_species_label_echoed(self):
        r = tf.compute_atmosphere_mass(planet_radius_km=6371, surface_gravity_ms2=9.81,
                                       pressure_bar=1, species="n2")
        self.assertEqual(r["species"], "n2")


class ValidationMatrixTest(unittest.TestCase):
    def test_curated_errors(self):
        cases = [
            tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=1.0, greenhouse_delta_k=33),
            tf.compute_equilibrium_temp(insolation_wm2=1361, greenhouse_delta_k=33, optical_depth=0.5),  # >1 forcing
            tf.compute_equilibrium_temp(insolation_wm2=1361, greenhouse_delta_k=33,
                                        target_surface_k=288),                      # >1 forcing (2 forms)
            tf.compute_equilibrium_temp(albedo=0.3, greenhouse_delta_k=33),         # no insolation
            tf.compute_equilibrium_temp(),                                          # no insolation, no forcing
            tf.compute_equilibrium_temp(insolation_wm2=1361, optical_depth=-0.1),   # τ<0
            tf.compute_equilibrium_temp(insolation_wm2=1361, target_surface_k=0),   # target≤0
            tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=0, solar_flux_wm2=589),
            tf.compute_insolation_shift(planet_radius_km=0, delta_insolation_wm2=20, solar_flux_wm2=589),
            tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=20),  # no flux src
            tf.compute_atmosphere_mass(planet_radius_km=0, surface_gravity_ms2=3.71, pressure_bar=1),
            tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                       planet_mass_earth=0.1, pressure_bar=1),       # two gravity
            tf.compute_atmosphere_mass(planet_radius_km=3390, pressure_bar=1),       # no gravity
            tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                       pressure_bar=1, volatile_mass_kg=1e18),        # two of P/m
            tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                       pressure_bar=1, species="argon"),              # bad species
        ]
        for r in cases:
            self.assertIn("error", r)
            self.assertIsInstance(r["error"], str)


class DeterminismTest(unittest.TestCase):
    def test_deep_equal_on_repeat(self):
        a = tf.compute_equilibrium_temp(luminosity_lsun=0.5, distance_au=0.8, albedo=0.2,
                                        optical_depth=1.5)
        b = tf.compute_equilibrium_temp(luminosity_lsun=0.5, distance_au=0.8, albedo=0.2,
                                        optical_depth=1.5)
        self.assertEqual(a, b)
        c = tf.compute_atmosphere_mass(planet_radius_km=6371, planet_mass_earth=1.0, pressure_bar=1)
        d = tf.compute_atmosphere_mass(planet_radius_km=6371, planet_mass_earth=1.0, pressure_bar=1)
        self.assertEqual(c, d)


if __name__ == "__main__":
    unittest.main()
