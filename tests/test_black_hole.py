# tests/test_black_hole.py — Phase AI (Group O) core calculators.
#
# Offline golden-pin tests for core.black_hole: the corrected acceptance anchors + the
# self-validating error matrix. No network, no Qt, no DB.

import unittest

import core.black_hole as bh


class SchwarzschildTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(bh.compute_schwarzschild_radius(mass_msun=1)["schwarzschild_radius_km"], 2.953, delta=0.002)
        self.assertAlmostEqual(bh.compute_schwarzschild_radius(mass_mearth=1)["schwarzschild_radius_m"] * 1000, 8.87, delta=0.05)
        self.assertAlmostEqual(bh.compute_schwarzschild_radius(object="sgr-a-star")["schwarzschild_radius_au"], 0.082, delta=0.001)

    def test_errors(self):
        self.assertIn("error", bh.compute_schwarzschild_radius())
        self.assertIn("error", bh.compute_schwarzschild_radius(mass_msun=1, object="sun"))


class HawkingTest(unittest.TestCase):
    def test_forward_and_inverse(self):
        self.assertAlmostEqual(bh.compute_hawking_temperature(mass_msun=1)["hawking_temperature_k"], 6.17e-8, delta=1e-10)
        self.assertAlmostEqual(bh.compute_hawking_temperature(temperature_k=2.725)["mass_kg"], 4.5e22, delta=1e21)

    def test_roundtrip(self):
        T = bh.compute_hawking_temperature(mass_kg=1e23)["hawking_temperature_k"]
        self.assertAlmostEqual(bh.compute_hawking_temperature(temperature_k=T)["mass_kg"], 1e23, delta=1e17)

    def test_errors(self):
        self.assertIn("error", bh.compute_hawking_temperature())
        self.assertIn("error", bh.compute_hawking_temperature(mass_msun=1, temperature_k=1))
        self.assertIn("error", bh.compute_hawking_temperature(temperature_k=-1))


class EvaporationTest(unittest.TestCase):
    def test_anchors(self):
        d = bh.compute_black_hole_evaporation(mass_msun=1)
        self.assertAlmostEqual(d["lifetime_yr"], 2.1e67, delta=1e65)
        self.assertAlmostEqual(d["power_w"], 9.0e-29, delta=1e-30)
        self.assertAlmostEqual(bh.compute_black_hole_evaporation(lifetime_yr=1.38e10)["mass_kg"], 1.73e11, delta=2e9)

    def test_errors(self):
        self.assertIn("error", bh.compute_black_hole_evaporation())
        self.assertIn("error", bh.compute_black_hole_evaporation(mass_msun=1, lifetime_yr=1))
        self.assertIn("error", bh.compute_black_hole_evaporation(lifetime_yr=-1))


class EntropyTest(unittest.TestCase):
    def test_anchor(self):
        self.assertAlmostEqual(bh.compute_bekenstein_hawking_entropy(mass_msun=1)["entropy_over_kb"], 1.05e77, delta=1e75)

    def test_radius_input(self):
        d = bh.compute_bekenstein_hawking_entropy(radius_m=2954.0)
        self.assertGreater(d["entropy_over_kb"], 0)
        self.assertIsNone(d["mass_kg"])

    def test_errors(self):
        self.assertIn("error", bh.compute_bekenstein_hawking_entropy())
        self.assertIn("error", bh.compute_bekenstein_hawking_entropy(mass_msun=1, radius_m=1))


class IscoTest(unittest.TestCase):
    def test_schwarzschild(self):
        d = bh.compute_isco(mass_msun=1)
        self.assertAlmostEqual(d["isco_radius_m"], 8862, delta=2)
        self.assertAlmostEqual(d["isco_radius_rs"], 3.0, places=6)
        self.assertAlmostEqual(d["binding_efficiency"], 0.0572, delta=1e-3)
        self.assertAlmostEqual(d["orbital_velocity_c"], 0.5, delta=1e-6)

    def test_kerr_extremal(self):
        self.assertAlmostEqual(bh.compute_isco(mass_msun=1, spin=1.0)["binding_efficiency"], 0.4226, delta=1e-3)
        self.assertAlmostEqual(bh.compute_isco(mass_msun=1, spin=1.0, prograde=False)["binding_efficiency"], 0.0377, delta=1e-3)
        self.assertIsNone(bh.compute_isco(mass_msun=1, spin=0.5)["orbital_velocity_c"])  # null for spin≠0

    def test_errors(self):
        self.assertIn("error", bh.compute_isco())
        self.assertIn("error", bh.compute_isco(mass_msun=1, spin=1.5))


class KerrHorizonTest(unittest.TestCase):
    def test_anchors(self):
        schw = bh.compute_kerr_horizon(mass_msun=1, spin=0.0)
        rs = bh.compute_schwarzschild_radius(mass_msun=1)["schwarzschild_radius_m"]
        self.assertAlmostEqual(schw["outer_horizon_m"], rs, places=3)      # a*=0 → r₊ = r_s
        ext = bh.compute_kerr_horizon(mass_msun=1, spin=1.0)
        self.assertAlmostEqual(ext["outer_horizon_m"], rs / 2, delta=1)    # a*=1 → r₊ = GM/c² = r_s/2
        self.assertAlmostEqual(ext["ergosphere_equatorial_m"], rs, places=3)
        self.assertTrue(ext["extremal"])

    def test_errors(self):
        self.assertIn("error", bh.compute_kerr_horizon())
        self.assertIn("error", bh.compute_kerr_horizon(mass_msun=1, spin=2.0))


class TidalForceTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(bh.compute_bh_tidal_force(mass_msun=10)["tidal_gees"], 1.89e7, delta=1e6)
        self.assertAlmostEqual(bh.compute_bh_tidal_force(mass_msun=1)["tidal_gees"], 1.89e9, delta=1e8)
        smbh = bh.compute_bh_tidal_force(mass_msun=1e8)
        self.assertAlmostEqual(smbh["tidal_gees"], 1.9e-7, delta=2e-8)

    def test_threshold(self):
        d = bh.compute_bh_tidal_force(mass_msun=1e8, threshold_g=1000)
        self.assertTrue(d["inside_horizon"])       # SMBH: lethal radius inside the horizon
        self.assertIsNotNone(d["spaghettification_radius_m"])
        stellar = bh.compute_bh_tidal_force(mass_msun=10, threshold_g=1000)
        self.assertFalse(stellar["inside_horizon"])

    def test_errors(self):
        self.assertIn("error", bh.compute_bh_tidal_force())
        self.assertIn("error", bh.compute_bh_tidal_force(mass_msun=10, distance_m=1e4, distance_rs=1))
        self.assertIn("error", bh.compute_bh_tidal_force(mass_msun=10, object_length_m=-1))
        self.assertIn("error", bh.compute_bh_tidal_force(mass_msun=10, threshold_g=-1))


class EddingtonTest(unittest.TestCase):
    def test_anchors(self):
        d = bh.compute_eddington_luminosity(mass_msun=1)
        self.assertAlmostEqual(d["eddington_luminosity_w"], 1.26e31, delta=1e29)
        self.assertAlmostEqual(d["eddington_luminosity_lsun"], 3.3e4, delta=1e3)
        self.assertAlmostEqual(d["eddington_accretion_rate_kg_s"], 1.4e15, delta=1e13)

    def test_efficiency_scaling(self):
        d = bh.compute_eddington_luminosity(mass_msun=1, efficiency=0.2)
        self.assertAlmostEqual(d["eddington_accretion_rate_kg_s"], 0.7e15, delta=1e13)  # ∝ 1/η

    def test_errors(self):
        self.assertIn("error", bh.compute_eddington_luminosity())
        self.assertIn("error", bh.compute_eddington_luminosity(mass_msun=1, efficiency=2.0))


class UnruhTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(bh.compute_unruh_temperature(acceleration_ms2=2.47e20)["unruh_temperature_k"], 1.0, delta=0.01)
        self.assertAlmostEqual(bh.compute_unruh_temperature(acceleration_g=1.0)["unruh_temperature_k"], 4.0e-20, delta=1e-21)

    def test_inverse(self):
        d = bh.compute_unruh_temperature(temperature_k=1.0)
        self.assertAlmostEqual(d["acceleration_ms2"], 2.47e20, delta=1e18)

    def test_errors(self):
        self.assertIn("error", bh.compute_unruh_temperature())
        self.assertIn("error", bh.compute_unruh_temperature(acceleration_ms2=1, temperature_k=1))
        self.assertIn("error", bh.compute_unruh_temperature(acceleration_ms2=-1))


class BekensteinBoundTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(bh.compute_bekenstein_bound(radius_m=0.1, mass_kg=1)["max_information_bits"], 2.58e42, delta=1e40)
        self.assertAlmostEqual(bh.compute_bekenstein_bound(radius_m=1, mass_kg=70)["max_information_bits"], 1.80e45, delta=1e43)

    def test_energy_input(self):
        import math
        c2 = 299792458.0 ** 2
        a = bh.compute_bekenstein_bound(radius_m=0.1, mass_kg=1)["max_information_bits"]
        b = bh.compute_bekenstein_bound(radius_m=0.1, energy_j=c2)["max_information_bits"]
        self.assertAlmostEqual(a, b, delta=1e30)

    def test_errors(self):
        self.assertIn("error", bh.compute_bekenstein_bound(mass_kg=1))                 # no radius
        self.assertIn("error", bh.compute_bekenstein_bound(radius_m=1))                # no energy/mass
        self.assertIn("error", bh.compute_bekenstein_bound(radius_m=1, mass_kg=1, energy_j=1))
        self.assertIn("error", bh.compute_bekenstein_bound(radius_m=-1, mass_kg=1))


if __name__ == "__main__":
    unittest.main()
