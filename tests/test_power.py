# tests/test_power.py — Phase AL (Group R) power-generation core (in-process).
#
# Offline golden-pin tests for core.power (R1 annihilation-power-train, R2 antimatter-production,
# R4 reactor-net-power, R7 beamed-power-delivery, R10 fusion-lawson) against the request spec's
# acceptance anchors + the self-validating ({"error"}) matrix. No network/DB/RNG/Qt/numpy.

import unittest

import core.power as power
from core.equations import _C_MS


class AnnihilationPowerTrainTest(unittest.TestCase):
    def test_anchor_pp_1ug_per_s(self):
        r = power.compute_annihilation_power_train(mass_flow_kgs=1e-9)
        self.assertAlmostEqual(r["power_total_w"], 8.9875518e7, delta=1e2)
        self.assertAlmostEqual(r["power_directed_w"], 4.4937759e7, delta=1e2)   # eta_dir 0.5
        self.assertAlmostEqual(r["power_gamma_w"], r["power_total_w"] / 3.0, places=3)
        self.assertAlmostEqual(r["power_neutrino_w"], r["power_total_w"] / 2.0, places=3)
        self.assertEqual(r["eta_dir"], 0.5)

    def test_power_total_path_matches_mass_flow(self):
        p = 1e-9 * _C_MS ** 2
        a = power.compute_annihilation_power_train(mass_flow_kgs=1e-9)
        b = power.compute_annihilation_power_train(power_total_w=p)
        self.assertAlmostEqual(a["power_directed_w"], b["power_directed_w"], places=3)

    def test_ee_no_neutrino_default_eta_one(self):
        r = power.compute_annihilation_power_train(power_total_w=1.0, species="ee")
        self.assertEqual(r["power_neutrino_w"], 0.0)
        self.assertEqual(r["power_gamma_w"], 1.0)
        self.assertEqual(r["eta_dir"], 1.0)

    def test_eta_dir_override(self):
        r = power.compute_annihilation_power_train(power_total_w=1.0, eta_dir=0.7)
        self.assertAlmostEqual(r["power_directed_w"], 0.7, places=9)

    def test_errors(self):
        for kw in (
            {},                                                   # neither anchor
            {"mass_flow_kgs": 1e-9, "power_total_w": 1.0},        # both anchors
            {"mass_flow_kgs": -1},                                # <= 0
            {"power_total_w": 1.0, "species": "xx"},              # bad species
            {"power_total_w": 1.0, "eta_dir": 1.5},               # eta out of range
        ):
            self.assertIn("error", power.compute_annihilation_power_train(**kw))


class AntimatterProductionTest(unittest.TestCase):
    def test_anchor(self):
        r = power.compute_antimatter_production(stored_mass_kg=1e-9, production_efficiency=1e-4)
        self.assertAlmostEqual(r["energy_stored_j"], 8.9875518e7, delta=1e2)
        self.assertAlmostEqual(r["energy_in_j"], 8.9875518e11, delta=1e6)
        self.assertAlmostEqual(r["threshold_floor_efficiency"], 1.0 / 3.0, places=9)
        self.assertAlmostEqual(r["energy_ratio_in_per_stored"], 1e4, places=3)
        self.assertIsNone(r["storage_density_kg_m3"])

    def test_stored_energy_path(self):
        r = power.compute_antimatter_production(stored_energy_j=8.9875518e7,
                                                production_efficiency=1e-4)
        self.assertAlmostEqual(r["energy_in_j"], 8.9875518e11, delta=1e6)

    def test_storage_density_brillouin(self):
        from core.equations import _EPSILON_0
        r = power.compute_antimatter_production(stored_mass_kg=1e-9, production_efficiency=1e-4,
                                                trap_field_t=20.0)
        self.assertAlmostEqual(r["storage_density_kg_m3"], _EPSILON_0 * 400.0 / 2.0, places=18)

    def test_efficiency_required_no_default(self):
        self.assertIn("error", power.compute_antimatter_production(stored_mass_kg=1e-9))

    def test_above_threshold_flagged(self):
        r = power.compute_antimatter_production(stored_mass_kg=1e-9, production_efficiency=0.5)
        self.assertTrue(any("ceiling" in n for n in r["notes"]))

    def test_errors(self):
        for kw in (
            {"production_efficiency": 1e-4},                                    # neither anchor
            {"stored_mass_kg": 1e-9, "stored_energy_j": 1.0, "production_efficiency": 1e-4},  # both
            {"stored_mass_kg": -1, "production_efficiency": 1e-4},              # <= 0
            {"stored_mass_kg": 1e-9, "production_efficiency": 0},               # eff <= 0
            {"stored_mass_kg": 1e-9, "production_efficiency": 1.5},             # eff > 1
            {"stored_mass_kg": 1e-9, "production_efficiency": 1e-4, "trap_field_t": -1},
        ):
            self.assertIn("error", power.compute_antimatter_production(**kw))


class ReactorNetPowerTest(unittest.TestCase):
    def test_anchor(self):
        r = power.compute_reactor_net_power(gross_power_w=1e9, thermal_efficiency=0.4,
                                            q_plasma=10.0)
        self.assertAlmostEqual(r["electric_power_w"], 4.0e8, places=1)
        self.assertAlmostEqual(r["engineering_breakeven_q"], 2.5, places=6)
        self.assertAlmostEqual(r["net_power_w"], 3.6e8, places=1)

    def test_no_q_plasma_no_tax(self):
        r = power.compute_reactor_net_power(gross_power_w=1e9, thermal_efficiency=0.4)
        self.assertAlmostEqual(r["net_power_w"], 4.0e8, places=1)

    def test_recirc(self):
        r = power.compute_reactor_net_power(gross_power_w=1e9, thermal_efficiency=0.4,
                                            recirculating_fraction=0.25)
        self.assertAlmostEqual(r["net_power_w"], 3.0e8, places=1)

    def test_errors(self):
        for kw in (
            {"gross_power_w": -1, "thermal_efficiency": 0.4},
            {"gross_power_w": 1e9, "thermal_efficiency": 1.5},
            {"gross_power_w": 1e9, "thermal_efficiency": 0.4, "q_plasma": 0},
            {"gross_power_w": 1e9, "thermal_efficiency": 0.4, "recirculating_fraction": 1.0},
        ):
            self.assertIn("error", power.compute_reactor_net_power(**kw))


class BeamedPowerDeliveryTest(unittest.TestCase):
    def test_anchor(self):
        r = power.compute_beamed_power_delivery(wavelength_m=1e-6, tx_aperture_m=10,
                                                rx_aperture_m=100, range_m=1.496e11)
        self.assertAlmostEqual(r["spot_diameter_m"], 3.65024e4, delta=1.0)
        self.assertAlmostEqual(r["capture_fraction"], 7.505e-6, delta=1e-8)
        self.assertIsNone(r["delivered_power_w"])

    def test_frequency_matches_wavelength(self):
        lam = 1e-6
        freq = _C_MS / lam
        a = power.compute_beamed_power_delivery(wavelength_m=lam, tx_aperture_m=10,
                                                rx_aperture_m=100, range_m=1.496e11)
        b = power.compute_beamed_power_delivery(frequency_hz=freq, tx_aperture_m=10,
                                                rx_aperture_m=100, range_m=1.496e11)
        self.assertAlmostEqual(a["spot_diameter_m"], b["spot_diameter_m"], places=3)

    def test_delivered_power(self):
        r = power.compute_beamed_power_delivery(wavelength_m=1e-6, tx_aperture_m=10,
                                                rx_aperture_m=100, range_m=1.496e11,
                                                tx_power_w=1e9)
        self.assertAlmostEqual(r["delivered_power_w"], 1e9 * r["capture_fraction"], places=3)

    def test_errors(self):
        base = {"tx_aperture_m": 10, "rx_aperture_m": 100, "range_m": 1.496e11}
        for kw in (
            {**base},                                              # no wavelength/frequency
            {"wavelength_m": 1e-6, "frequency_hz": 1e14, **base},  # both
            {"wavelength_m": -1, **base},                          # <= 0
            {"wavelength_m": 1e-6, "tx_aperture_m": 0, "rx_aperture_m": 100, "range_m": 1e11},
            {"wavelength_m": 1e-6, **base, "pointing_efficiency": 1.5},
        ):
            self.assertIn("error", power.compute_beamed_power_delivery(**kw))


class FusionLawsonTest(unittest.TestCase):
    def test_anchor_dt_ignition_boundary(self):
        r = power.compute_fusion_lawson(fuel="d-t", triple_product=3e21)
        self.assertAlmostEqual(r["q_fusion"], 1.0, places=6)
        self.assertTrue(r["ignited"])

    def test_triple_from_parts(self):
        # n·T·τ = 3e21 → q 1 for D-T.
        r = power.compute_fusion_lawson(fuel="d-t", density_m3=1e21, temp_kev=3.0,
                                        confinement_s=1.0)
        self.assertAlmostEqual(r["q_fusion"], 1.0, places=6)

    def test_confinement_boost_scales(self):
        r = power.compute_fusion_lawson(fuel="d-t", triple_product=3e21, confinement_boost=3.0)
        self.assertAlmostEqual(r["q_fusion"], 3.0, places=6)
        self.assertAlmostEqual(r["triple_product_kev_s_m3"], 9e21, delta=1e18)

    def test_scope_guard_in_note(self):
        r = power.compute_fusion_lawson(fuel="d-t", triple_product=3e21)
        self.assertIn("SCOPE GUARD", r["model_note"])

    def test_pb11_much_harder(self):
        self.assertGreater(power.compute_fusion_lawson(fuel="p-b11", triple_product=1.0)["ignition_threshold"],
                           1e3 * power.compute_fusion_lawson(fuel="d-t", triple_product=1.0)["ignition_threshold"] * 0.99)

    def test_errors(self):
        for kw in (
            {"fuel": "unobtainium", "triple_product": 3e21},
            {"fuel": "d-t"},                                          # no triple / parts
            {"fuel": "d-t", "triple_product": 3e21, "density_m3": 1e21},  # both
            {"fuel": "d-t", "density_m3": 1e21, "temp_kev": 3.0},     # partial parts
            {"fuel": "d-t", "triple_product": -1},
            {"fuel": "d-t", "triple_product": 3e21, "confinement_boost": 0},
        ):
            self.assertIn("error", power.compute_fusion_lawson(**kw))


class ModelNoteTest(unittest.TestCase):
    def test_every_calc_carries_model_note(self):
        for r in (
            power.compute_annihilation_power_train(mass_flow_kgs=1e-9),
            power.compute_antimatter_production(stored_mass_kg=1e-9, production_efficiency=1e-4),
            power.compute_reactor_net_power(gross_power_w=1e9, thermal_efficiency=0.4),
            power.compute_beamed_power_delivery(wavelength_m=1e-6, tx_aperture_m=10,
                                                rx_aperture_m=100, range_m=1.496e11),
            power.compute_fusion_lawson(fuel="d-t", triple_product=3e21),
        ):
            self.assertIn("model_note", r)


if __name__ == "__main__":
    unittest.main()
