# tests/test_power_tables.py — Phase AL (Group R) bundled power tables (in-process).
#
# Golden-pin + contract tests for core.power_tables (T1 energy-storage / _STORAGE, T2 reactor-power
# / _REACTOR_SPECIFIC_POWER): row pins, all-rows vs single-class, --override echo, the sensible/latent
# compute branch, the mandatory T2 thermal pointer, and the unknown-class error idiom. No net/DB/RNG.

import unittest

import core.power_tables as pt


class StorageTableTest(unittest.TestCase):
    def test_all_rows_when_no_class(self):
        r = pt.compute_energy_storage()
        self.assertIn("classes", r)
        self.assertEqual(len(r["classes"]), len(pt._STORAGE))

    def test_single_class_li_ion(self):
        r = pt.compute_energy_storage(class_name="li-ion")
        self.assertEqual(r["class"], "li-ion")
        self.assertAlmostEqual(r["specific_energy_j_kg"], 1.0e6, places=1)
        self.assertAlmostEqual(r["specific_energy_wh_kg"], 1.0e6 / 3600.0, places=3)
        self.assertIn("source_tag", r)
        self.assertIn("note", r)

    def test_override_wh_kg_echoed(self):
        r = pt.compute_energy_storage(class_name="li-ion", override_wh_kg=500.0)
        self.assertAlmostEqual(r["specific_energy_j_kg"], 500.0 * 3600.0, places=1)
        self.assertEqual(r["overridden"]["specific_energy_wh_kg"], 500.0)

    def test_sensible_compute_branch(self):
        r = pt.compute_energy_storage(class_name="sensible-thermal", mass_kg=1000,
                                      specific_heat_jkgk=4186, delta_t_k=100)
        self.assertAlmostEqual(r["stored_energy_j"], 4.186e8, places=1)

    def test_latent_compute_branch(self):
        r = pt.compute_energy_storage(class_name="latent-thermal", mass_kg=1000,
                                      latent_heat_jkg=334000)
        self.assertAlmostEqual(r["stored_energy_j"], 3.34e8, places=1)

    def test_compute_branch_without_class(self):
        r = pt.compute_energy_storage(mass_kg=1000, specific_heat_jkgk=4186, delta_t_k=100)
        self.assertAlmostEqual(r["stored_energy_j"], 4.186e8, places=1)

    def test_nuclear_ceiling_pointer_in_chemical_note(self):
        r = pt.compute_energy_storage(class_name="chemical-fuel")
        self.assertIn("f·c²", r["note"])

    def test_errors(self):
        self.assertIn("error", pt.compute_energy_storage(class_name="nope"))
        self.assertIn("error", pt.compute_energy_storage(mass_kg=1000, specific_heat_jkgk=4186,
                                                         latent_heat_jkg=334000))  # both branches
        self.assertIn("error", pt.compute_energy_storage(mass_kg=-1, latent_heat_jkg=1))
        self.assertIn("error", pt.compute_energy_storage(class_name="li-ion", override_wh_kg=-1))


class ReactorPowerTableTest(unittest.TestCase):
    def test_all_rows_when_no_class(self):
        r = pt.compute_reactor_power()
        self.assertEqual(len(r["classes"]), len(pt._REACTOR_SPECIFIC_POWER))
        self.assertIn("thermal_pointer", r)

    def test_single_class_fusion(self):
        r = pt.compute_reactor_power(class_name="fusion")
        self.assertEqual(r["class"], "fusion")
        self.assertAlmostEqual(r["specific_power_kw_kg"], 5.0, places=3)
        self.assertIsNone(r["core_mass_kg"])
        self.assertIn("thermal_pointer", r)   # mandatory on every result

    def test_implied_core_mass(self):
        r = pt.compute_reactor_power(class_name="fusion", gross_power_w=1e9)
        # m = P / (alpha_kwkg * 1000) = 1e9 / (5*1000) = 2e5 kg.
        self.assertAlmostEqual(r["core_mass_kg"], 2.0e5, places=1)

    def test_override_kw_kg_echoed(self):
        r = pt.compute_reactor_power(class_name="fusion", override_kw_kg=10.0, gross_power_w=1e9)
        self.assertAlmostEqual(r["specific_power_kw_kg"], 10.0, places=3)
        self.assertAlmostEqual(r["core_mass_kg"], 1e5, places=1)
        self.assertEqual(r["overridden"]["specific_power_kw_kg"], 10.0)

    def test_thermal_pointer_on_every_row(self):
        for row in pt.compute_reactor_power()["classes"]:
            self.assertIn("thermal_pointer", row)

    def test_errors(self):
        self.assertIn("error", pt.compute_reactor_power(class_name="nope"))
        self.assertIn("error", pt.compute_reactor_power(gross_power_w=-1))
        self.assertIn("error", pt.compute_reactor_power(class_name="fusion", override_kw_kg=0))


if __name__ == "__main__":
    unittest.main()
