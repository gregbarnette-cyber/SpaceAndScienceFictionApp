# tests/test_exotic_physics.py — Phase AG (Group M) core calculators.
#
# Offline golden-pin tests for core.exotic_physics: the corrected acceptance anchors + the
# self-validating error matrix. No network, no Qt, no DB.

import unittest

import core.exotic_physics as ex


class CasimirTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(ex.compute_casimir(separation_nm=1000)["pressure_pa"], 1.30e-3, delta=1e-5)
        self.assertAlmostEqual(ex.compute_casimir(separation_nm=1000)["energy_density_j_m3"], -4.33e-10, delta=1e-12)
        self.assertAlmostEqual(ex.compute_casimir(separation_nm=10)["pressure_pa"], 1.30e5, delta=1e3)

    def test_inverse_fourth_power_and_area(self):
        p1 = ex.compute_casimir(separation_nm=1000)["pressure_pa"]
        p2 = ex.compute_casimir(separation_nm=100)["pressure_pa"]
        self.assertAlmostEqual(p2 / p1, 1e4, delta=1)              # 10x closer → 1e4x pressure
        d = ex.compute_casimir(separation_nm=1000, area_m2=2.0)
        self.assertAlmostEqual(d["force_n"], d["pressure_pa"] * 2.0, places=15)

    def test_sphere_plate(self):
        d = ex.compute_casimir(separation_nm=100, geometry="sphere-plate", sphere_radius_m=1e-4)
        self.assertLess(d["force_n"], 0)
        self.assertIsNone(d["pressure_pa"])
        self.assertIsNone(d["energy_density_j_m3"])

    def test_errors(self):
        self.assertIn("error", ex.compute_casimir())                                       # no separation
        self.assertIn("error", ex.compute_casimir(separation_m=1e-6, separation_nm=1000))  # two units
        self.assertIn("error", ex.compute_casimir(separation_nm=-1))                        # negative
        self.assertIn("error", ex.compute_casimir(separation_nm=100, geometry="sphere-plate"))  # no radius
        self.assertIn("error", ex.compute_casimir(separation_nm=100, sphere_radius_m=1e-4))     # radius w/ pp


class VacuumEnergyTest(unittest.TestCase):
    def test_anchors(self):
        d = ex.compute_vacuum_energy()
        self.assertAlmostEqual(d["rho_lambda_j_m3"], 5.3e-10, delta=2e-11)
        self.assertAlmostEqual(d["rho_crit_j_m3"], 7.7e-10, delta=3e-11)
        self.assertAlmostEqual(d["lambda_m2"], 1.09e-52, delta=1e-53)
        self.assertEqual(d["equation_of_state_w"], -1.0)
        self.assertTrue(1e121 < d["catastrophe_ratio"] < 1e124)      # ~10^122

    def test_cutoff_presets_and_custom(self):
        ew = ex.compute_vacuum_energy(cutoff="electroweak")["catastrophe_ratio"]
        pl = ex.compute_vacuum_energy(cutoff="planck")["catastrophe_ratio"]
        self.assertLess(ew, pl)                                       # lower cutoff → smaller ratio
        custom = ex.compute_vacuum_energy(cutoff="1000")             # 1000 GeV
        self.assertIn("GeV", custom["cutoff"])

    def test_errors(self):
        self.assertIn("error", ex.compute_vacuum_energy(omega_lambda=2.0))
        self.assertIn("error", ex.compute_vacuum_energy(hubble_kms_mpc=-1))
        self.assertIn("error", ex.compute_vacuum_energy(cutoff="banana"))


class SchwingerTest(unittest.TestCase):
    def test_anchors(self):
        d = ex.compute_schwinger_limit()
        self.assertAlmostEqual(d["critical_field_vm"], 1.32e18, delta=1e16)
        self.assertAlmostEqual(d["critical_magnetic_field_t"], 4.41e9, delta=1e7)
        self.assertAlmostEqual(d["critical_intensity_wcm2"], 2.3e29, delta=5e27)
        self.assertIsNone(d["ratio_to_critical"])

    def test_ratio(self):
        d = ex.compute_schwinger_limit(field_vm=1.3232854741e18)
        self.assertAlmostEqual(d["ratio_to_critical"], 1.0, delta=1e-3)
        i = ex.compute_schwinger_limit(intensity_wcm2=2.324e29)
        self.assertAlmostEqual(i["ratio_to_critical"], 1.0, delta=1e-2)

    def test_errors(self):
        self.assertIn("error", ex.compute_schwinger_limit(field_vm=1e18, intensity_wcm2=1e29))
        self.assertIn("error", ex.compute_schwinger_limit(field_vm=-1))


class HubbleFlowTest(unittest.TestCase):
    def test_recession_anchor(self):
        d = ex.compute_hubble_flow(distance_mpc=100)
        self.assertAlmostEqual(d["recession_velocity_kms"], 6740, delta=1)
        self.assertIsNone(d["bound"])

    def test_binding_anchors(self):
        lg = ex.compute_hubble_flow(mass_msun=3e12, radius_mpc=1.0)
        self.assertTrue(lg["bound"])
        self.assertAlmostEqual(lg["turnaround_radius_mpc"], 1.6, delta=0.3)
        gal = ex.compute_hubble_flow(mass_msun=1e11, radius_mpc=0.01)
        self.assertTrue(gal["bound"])
        self.assertGreater(gal["binding_ratio"], 1e4)

    def test_unbound_far_out(self):
        # a small mass at large radius is not bound
        d = ex.compute_hubble_flow(mass_msun=1e11, radius_mpc=5.0)
        self.assertFalse(d["bound"])

    def test_errors(self):
        self.assertIn("error", ex.compute_hubble_flow())                                   # neither mode
        self.assertIn("error", ex.compute_hubble_flow(distance_mpc=100, mass_msun=1e12))    # both modes
        self.assertIn("error", ex.compute_hubble_flow(mass_msun=1e12))                      # no radius
        self.assertIn("error", ex.compute_hubble_flow(distance_mpc=-1))
        self.assertIn("error", ex.compute_hubble_flow(mass_msun=1e12, radius_mpc=1, radius_ly=1))  # 2 radius units


if __name__ == "__main__":
    unittest.main()
