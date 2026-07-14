# tests/test_energy_storage.py — Phase AL (Group R) energy-storage core (in-process).
#
# Offline golden-pin tests for core.energy_storage (R8 flywheel-storage, R9 smes-storage) against
# the request spec's acceptance anchors + the self-validating ({"error"}) matrix. No net/DB/RNG/Qt.

import unittest

import core.energy_storage as es
from core.equations import _MU_0


class FlywheelStorageTest(unittest.TestCase):
    def test_anchor_carbon_fiber_k05(self):
        r = es.compute_flywheel_storage(tensile_strength_pa=5e9, density_kgm3=1800,
                                        shape_factor=0.5)
        self.assertAlmostEqual(r["specific_energy_j_kg"], 1.388889e6, delta=1.0)
        self.assertAlmostEqual(r["specific_energy_wh_kg"], 385.8, delta=0.1)
        self.assertIsNone(r["stored_energy_j"])

    def test_thin_rim_k03(self):
        r = es.compute_flywheel_storage(tensile_strength_pa=5e9, density_kgm3=1800,
                                        shape_factor=0.3)
        self.assertAlmostEqual(r["specific_energy_j_kg"], 0.3 * 5e9 / 1800, delta=1.0)

    def test_stored_energy_with_mass(self):
        r = es.compute_flywheel_storage(tensile_strength_pa=5e9, density_kgm3=1800,
                                        shape_factor=0.5, mass_kg=1000)
        self.assertAlmostEqual(r["stored_energy_j"], 1.388889e9, delta=1e3)

    def test_errors(self):
        for kw in (
            {"tensile_strength_pa": 0, "density_kgm3": 1800},
            {"tensile_strength_pa": 5e9, "density_kgm3": 0},
            {"tensile_strength_pa": 5e9, "density_kgm3": 1800, "shape_factor": 1.5},
            {"tensile_strength_pa": 5e9, "density_kgm3": 1800, "mass_kg": -1},
        ):
            self.assertIn("error", es.compute_flywheel_storage(**kw))


class SmesStorageTest(unittest.TestCase):
    def test_anchor_20t(self):
        r = es.compute_smes_storage(field_t=20.0)
        self.assertAlmostEqual(r["energy_density_j_m3"], 400.0 / (2.0 * _MU_0), delta=1e3)
        self.assertAlmostEqual(r["energy_density_j_m3"], 1.5915e8, delta=1e4)
        self.assertIsNone(r["specific_energy_j_kg"])
        self.assertIsNone(r["critical_field_exceeded"])

    def test_specific_energy_branch(self):
        r = es.compute_smes_storage(field_t=20.0, tensile_strength_pa=5e9, density_kgm3=1800)
        self.assertAlmostEqual(r["specific_energy_j_kg"], 5e9 / 1800.0, places=3)

    def test_critical_field_flag(self):
        self.assertTrue(es.compute_smes_storage(field_t=25.0, critical_field_t=20.0)["critical_field_exceeded"])
        self.assertFalse(es.compute_smes_storage(field_t=15.0, critical_field_t=20.0)["critical_field_exceeded"])

    def test_stored_energy_with_volume(self):
        r = es.compute_smes_storage(field_t=20.0, volume_m3=100.0)
        self.assertAlmostEqual(r["stored_energy_j"], r["energy_density_j_m3"] * 100.0, places=3)

    def test_errors(self):
        for kw in (
            {"field_t": 0},
            {"field_t": 20, "critical_field_t": -1},
            {"field_t": 20, "volume_m3": 0},
            {"field_t": 20, "tensile_strength_pa": 5e9},     # sigma without rho
            {"field_t": 20, "density_kgm3": 1800},           # rho without sigma
        ):
            self.assertIn("error", es.compute_smes_storage(**kw))


if __name__ == "__main__":
    unittest.main()
