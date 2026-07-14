# tests/test_thermal.py — Phase V power/thermal/shielding core (in-process).
#
# Covers the three pure-math calculators in core/thermal.py against the request's
# acceptance anchors, plus the F3 bundled-table integrity (HVL/TVL <-> mu/rho closure)
# and the self-validating ({"error"}) matrix. No network/DB/RNG/Qt.

import math
import unittest

import core.thermal as thermal
from core import shielding_tables
from core.equations import _STEFAN_BOLTZMANN


class WasteHeatTest(unittest.TestCase):
    def test_gross_input_anchor(self):
        # 3 GW thermal @ eta=0.4 -> useful 1.2 GW, waste 1.8 GW
        d = thermal.compute_waste_heat(input_power_watts=3e9, efficiency=0.4)
        self.assertAlmostEqual(d["useful_power_w"], 1.2e9, places=0)
        self.assertAlmostEqual(d["waste_heat_w"], 1.8e9, places=0)
        self.assertIsNone(d["carnot_efficiency"])

    def test_useful_output_anchor(self):
        d = thermal.compute_waste_heat(useful_power_watts=1.2e9, efficiency=0.4)
        self.assertAlmostEqual(d["input_power_w"], 3e9, places=0)
        self.assertAlmostEqual(d["waste_heat_w"], 1.8e9, places=0)

    def test_carnot_ceiling_and_limited_flag(self):
        # T_hot=1500, T_cold=300 -> eta_carnot=0.8; claimed eta=0.9 is impossible
        d = thermal.compute_waste_heat(useful_power_watts=1e9, efficiency=0.9,
                                       hot_temp_k=1500, cold_temp_k=300)
        self.assertAlmostEqual(d["carnot_efficiency"], 0.8, places=6)
        self.assertTrue(d["carnot_limited"])
        self.assertTrue(d["notes"])

    def test_carnot_derives_efficiency_when_only_temps(self):
        d = thermal.compute_waste_heat(input_power_watts=1e9, hot_temp_k=1500, cold_temp_k=300)
        self.assertAlmostEqual(d["efficiency"], 0.8, places=6)
        self.assertFalse(d["carnot_limited"])

    def test_carnot_min_waste(self):
        # Q_min = P_useful * T_cold/(T_hot-T_cold) = 1e9 * 300/1200 = 2.5e8
        d = thermal.compute_waste_heat(useful_power_watts=1e9, efficiency=0.8,
                                       hot_temp_k=1500, cold_temp_k=300)
        self.assertAlmostEqual(d["carnot_min_waste_heat_w"], 2.5e8, places=0)

    def test_validation(self):
        for kw in (
            {},                                                      # no power anchor
            {"input_power_watts": 1e9, "useful_power_watts": 1e9},   # both anchors
            {"input_power_watts": -1, "efficiency": 0.4},            # neg power
            {"input_power_watts": 1e9, "efficiency": 1.5},           # eta > 1
            {"input_power_watts": 1e9, "efficiency": 0},             # eta = 0
            {"input_power_watts": 1e9},                              # no efficiency anchor
            {"input_power_watts": 1e9, "hot_temp_k": 300, "cold_temp_k": 1500},  # hot<=cold
            {"input_power_watts": 1e9, "hot_temp_k": 1500},          # incomplete reservoir pair
        ):
            self.assertIn("error", thermal.compute_waste_heat(**kw), kw)

    def test_steady_state_no_mode_key(self):
        # C9 regression pin: the steady-state result carries no "mode" key (byte-identical shape)
        r = thermal.compute_waste_heat(input_power_watts=3e9, efficiency=0.4)
        self.assertNotIn("mode", r)


class WasteHeatTransientTest(unittest.TestCase):
    # C9 — pulsed thermal-buffer mode
    def _t(self, **kw):
        base = dict(peak_w=3e9, mean_w=1e9, duty=0.5, pulse_period_s=100,
                    storage_mass_kg=1000, specific_heat_jkgk=500)
        base.update(kw)
        return thermal.compute_waste_heat(**base)

    def test_anchor(self):
        r = self._t()
        self.assertEqual(r["mode"], "transient")
        self.assertEqual(r["on_time_s"], 50.0)
        self.assertEqual(r["excess_power_w"], 2e9)
        # temp_swing_k = excess·on_time/(m·c) = 2e9·50/(1000·500) = 2e5
        self.assertAlmostEqual(r["temp_swing_k"], 2e5, places=3)
        self.assertGreater(r["buffer_time_s"], 0)

    def test_temp_swing_scales(self):
        # doubling the buffer heat capacity halves the swing
        base = self._t()
        big = self._t(storage_mass_kg=2000)
        self.assertAlmostEqual(big["temp_swing_k"], base["temp_swing_k"] / 2.0, places=6)

    def test_validation(self):
        for kw in (
            {"peak_w": 3e9},                                          # incomplete set
            {"peak_w": 1e9, "mean_w": 3e9, "duty": 0.5, "pulse_period_s": 100,
             "storage_mass_kg": 1000, "specific_heat_jkgk": 500},     # peak < mean
            {"peak_w": 3e9, "mean_w": 1e9, "duty": 1.5, "pulse_period_s": 100,
             "storage_mass_kg": 1000, "specific_heat_jkgk": 500},     # duty > 1
            {"peak_w": 3e9, "mean_w": 1e9, "duty": 0.5, "pulse_period_s": 0,
             "storage_mass_kg": 1000, "specific_heat_jkgk": 500},     # period 0
            {"peak_w": 3e9, "mean_w": 1e9, "duty": 0.5, "pulse_period_s": 100,
             "storage_mass_kg": 0, "specific_heat_jkgk": 500},        # mass 0
        ):
            self.assertIn("error", thermal.compute_waste_heat(**kw), kw)


class RadiatorAreaTest(unittest.TestCase):
    def test_blackside_flux_anchors(self):
        for T, expect in ((300, 459.3), (1000, 5.6704e4)):
            d = thermal.compute_radiator_area(heat_watts=1e6, radiator_temp_k=T,
                                              emissivity=1.0, sides=1)
            self.assertAlmostEqual(d["blackside_flux_wm2"], expect, delta=expect * 1e-3)

    def test_gigawatt_kilometre_anchor(self):
        # 1 GW @ 300 K, eps=0.9, double-sided -> ~1.21e6 m^2 ~ 1.21 km^2
        d = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300,
                                          emissivity=0.9, sides=2)
        self.assertAlmostEqual(d["radiator_area_m2"], 1.21e6, delta=1e4)
        self.assertAlmostEqual(d["radiator_area_km2"], 1.21, delta=0.01)
        self.assertTrue(d["scaling_note"])

    def test_t_minus_4_scaling(self):
        # halving radiator temp -> 16x area
        hot = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=600)
        cold = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300)
        self.assertAlmostEqual(cold["radiator_area_m2"] / hot["radiator_area_m2"], 16.0, places=2)

    def test_inline_f1_chain(self):
        d = thermal.compute_radiator_area(input_power_watts=3e9, efficiency=0.4,
                                          radiator_temp_k=300)
        self.assertAlmostEqual(d["heat_watts"], 1.8e9, places=0)

    def test_sides_and_mass(self):
        one = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300, sides=1)
        two = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300, sides=2)
        self.assertAlmostEqual(one["radiator_area_m2"], 2 * two["radiator_area_m2"], places=2)
        d = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300,
                                          areal_mass_kgm2=5.0)
        self.assertAlmostEqual(d["radiator_mass_kg"], d["radiator_area_m2"] * 5.0, places=2)

    def test_sink_flux_collapse(self):
        # a warm sink shrinks net flux -> larger area than deep-space
        cold = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300, sink_temp_k=0)
        warm = thermal.compute_radiator_area(heat_watts=1e9, radiator_temp_k=300, sink_temp_k=250)
        self.assertGreater(warm["radiator_area_m2"], cold["radiator_area_m2"])

    def test_validation(self):
        for kw in (
            {"radiator_temp_k": 300},                                          # no heat anchor
            {"heat_watts": 1e9, "input_power_watts": 1e9, "radiator_temp_k": 300},  # both anchors
            {"heat_watts": -1, "radiator_temp_k": 300},                        # neg heat
            {"heat_watts": 1e9, "radiator_temp_k": 0},                         # T_rad <= 0
            {"heat_watts": 1e9, "radiator_temp_k": 300, "emissivity": 1.5},    # eps > 1
            {"heat_watts": 1e9, "radiator_temp_k": 300, "sides": 3},           # bad sides
            {"heat_watts": 1e9, "radiator_temp_k": 300, "sink_temp_k": 350},   # sink >= rad
            {"heat_watts": 1e9, "radiator_temp_k": 300, "sink_temp_k": -10},   # sink < 0
            {"input_power_watts": 1e9, "radiator_temp_k": 300},               # chain w/o efficiency
        ):
            self.assertIn("error", thermal.compute_radiator_area(**kw), kw)


class ShieldingPhotonTest(unittest.TestCase):
    def test_water_1mev_anchor(self):
        d = thermal.compute_shielding_attenuation(material="water", energy_mev=1.0,
                                                  areal_density_gcm2=20)
        self.assertAlmostEqual(d["transmitted_fraction"], 0.2431, places=3)
        self.assertAlmostEqual(d["half_value_layer_gcm2"], 9.80, delta=0.05)
        self.assertAlmostEqual(d["tenth_value_layer_gcm2"], 32.6, delta=0.2)
        self.assertFalse(d["is_order_of_magnitude"])
        self.assertTrue(d["energy_exact"])

    def test_lead_1mev_linear_hvl(self):
        d = thermal.compute_shielding_attenuation(material="lead", energy_mev=1.0,
                                                  thickness_cm=1, density_gcm3=11.35)
        self.assertAlmostEqual(d["half_value_layer_cm"], 0.86, delta=0.01)

    def test_explicit_coefficient(self):
        d = thermal.compute_shielding_attenuation(mass_atten_coeff_cm2g=0.0707,
                                                  areal_density_gcm2=20)
        self.assertAlmostEqual(d["transmitted_fraction"], math.exp(-0.0707 * 20), places=9)
        self.assertIsNone(d["material"])

    def test_nearest_energy_flagged(self):
        d = thermal.compute_shielding_attenuation(material="water", energy_mev=0.9,
                                                  areal_density_gcm2=10)
        self.assertEqual(d["energy_mev"], 1.0)
        self.assertFalse(d["energy_exact"])
        self.assertTrue(d["notes"])

    def test_hydrogen_alias_and_note(self):
        a = thermal.compute_shielding_attenuation(material="hydrogen", energy_mev=1.0,
                                                  areal_density_gcm2=10)
        b = thermal.compute_shielding_attenuation(material="liquid_h2", energy_mev=1.0,
                                                  areal_density_gcm2=10)
        self.assertEqual(a["mass_atten_coeff_cm2g"], b["mass_atten_coeff_cm2g"])
        self.assertTrue(any("per-gram" in n for n in a["notes"]))

    def test_nist_pinned_grid(self):
        # Golden values reconciled cell-by-cell against the live NIST XAAMDI tables
        # (2026-06-30): water/PE -> ComTab; Al/Pb/H/Fe -> ElemTab z13/82/01/26; regolith
        # = SiO2 computed from elemental Si(z14)+O(z08). Guards against silent drift.
        NIST = {
            "water":        {0.1: 0.1707,  0.5: 0.09687, 1.0: 0.07072, 2.0: 0.04942, 5.0: 0.03031, 10.0: 0.02219},
            "polyethylene": {0.1: 0.1719,  0.5: 0.09947, 1.0: 0.07262, 2.0: 0.05064, 5.0: 0.03045, 10.0: 0.02145},
            "aluminum":     {0.1: 0.1704,  0.5: 0.08445, 1.0: 0.06146, 2.0: 0.04324, 5.0: 0.02836, 10.0: 0.02318},
            "regolith":     {0.1: 0.16838, 0.5: 0.08738, 1.0: 0.06367, 2.0: 0.04469, 5.0: 0.02866, 10.0: 0.02263},
            "lead":         {0.1: 5.549,   0.5: 0.1614,  1.0: 0.07102, 2.0: 0.04606, 5.0: 0.04272, 10.0: 0.04972},
            "liquid_h2":    {0.1: 0.2944,  0.5: 0.1729,  1.0: 0.1263,  2.0: 0.08769, 5.0: 0.05049, 10.0: 0.03254},
            "iron":         {0.1: 0.3717,  0.5: 0.08414, 1.0: 0.05995, 2.0: 0.04265, 5.0: 0.03146, 10.0: 0.02994},
        }
        self.assertEqual(set(shielding_tables._XCOM_MU_RHO), set(NIST))
        for mat, grid in NIST.items():
            for e, expect in grid.items():
                got, chosen, _ = shielding_tables.lookup_mu_rho(mat, e)
                self.assertEqual(chosen, e)
                # regolith is a computed mixture (rounding tolerance); the rest are verbatim
                self.assertAlmostEqual(got, expect, places=(5 if mat == "regolith" else 6),
                                       msg=f"{mat} @ {e} MeV")

    def test_table_closure_all_materials(self):
        # HVL = ln2/(mu/rho), TVL = ln10/(mu/rho) for every bundled (material, energy)
        for mat, grid in shielding_tables._XCOM_MU_RHO.items():
            for e, mu_rho in grid.items():
                d = thermal.compute_shielding_attenuation(material=mat, energy_mev=e,
                                                          areal_density_gcm2=1.0)
                self.assertAlmostEqual(d["half_value_layer_gcm2"], math.log(2) / mu_rho, places=9)
                self.assertAlmostEqual(d["tenth_value_layer_gcm2"], math.log(10) / mu_rho, places=9)
                self.assertAlmostEqual(d["transmitted_fraction"], math.exp(-mu_rho), places=12)

    def test_thickness_density_path(self):
        a = thermal.compute_shielding_attenuation(material="water", energy_mev=1.0,
                                                  areal_density_gcm2=20)
        b = thermal.compute_shielding_attenuation(material="water", energy_mev=1.0,
                                                  thickness_cm=20, density_gcm3=1.0)
        self.assertAlmostEqual(a["transmitted_fraction"], b["transmitted_fraction"], places=12)
        self.assertEqual(b["areal_density_gcm2"], 20.0)


class ShieldingGcrTest(unittest.TestCase):
    def test_gcr_bundled_and_caveat(self):
        d = thermal.compute_shielding_attenuation(mode="gcr", material="water",
                                                  areal_density_gcm2=30)
        self.assertTrue(d["is_order_of_magnitude"])
        self.assertTrue(d["buildup_caveat"])
        self.assertIn("attenuation_length_gcm2", d)
        self.assertAlmostEqual(d["transmitted_fraction"],
                               math.exp(-30 / d["attenuation_length_gcm2"]), places=12)

    def test_gcr_explicit_lambda(self):
        d = thermal.compute_shielding_attenuation(mode="gcr", attenuation_length_gcm2=25,
                                                  areal_density_gcm2=25)
        self.assertAlmostEqual(d["transmitted_fraction"], math.exp(-1.0), places=12)


class ShieldingCsdaTest(unittest.TestCase):
    # C6 — charged-particle CSDA range
    def test_proton_water_100mev_anchor(self):
        # NIST PSTAR 100 MeV proton in water → CSDA range 7.718 g/cm² (web-verified).
        r = thermal.compute_shielding_attenuation(areal_density_gcm2=5.0, particle="proton",
                                                  material="water", energy_mev=100.0)
        self.assertEqual(r["mode"], "csda")
        self.assertAlmostEqual(r["csda_range_gcm2"], 7.718, places=3)
        self.assertFalse(r["stops_primary"])           # 5 < 7.718 g/cm²
        self.assertTrue(r["penetrates"])
        self.assertAlmostEqual(r["residual_range_gcm2"], 7.718 - 5.0, places=3)
        self.assertFalse(r["is_order_of_magnitude"])

    def test_stops_when_thick_enough(self):
        r = thermal.compute_shielding_attenuation(areal_density_gcm2=10.0, particle="proton",
                                                  material="water", energy_mev=100.0)
        self.assertTrue(r["stops_primary"])
        self.assertEqual(r["residual_range_gcm2"], 0.0)

    def test_csda_range_cm_with_density(self):
        r = thermal.compute_shielding_attenuation(thickness_cm=5.0, density_gcm3=1.0,
                                                  particle="proton", material="water",
                                                  energy_mev=100.0)
        # water ρ=1 → range in cm equals range in g/cm²
        self.assertAlmostEqual(r["csda_range_cm"], r["csda_range_gcm2"], places=6)

    def test_explicit_range_for_alpha(self):
        # alpha/other materials are supported via the explicit override
        r = thermal.compute_shielding_attenuation(areal_density_gcm2=1.0, particle="alpha",
                                                  csda_range_gcm2=0.65)
        self.assertEqual(r["particle"], "alpha")
        self.assertAlmostEqual(r["csda_range_gcm2"], 0.65, places=6)
        self.assertTrue(r["stops_primary"])

    def test_csda_range_monotone_in_energy(self):
        # table closure: CSDA range strictly increases with energy
        rng = [thermal.compute_shielding_attenuation(areal_density_gcm2=1.0, particle="proton",
                                                     material="water", energy_mev=e)["csda_range_gcm2"]
               for e in (10, 50, 100, 150, 200, 250)]
        self.assertEqual(rng, sorted(rng))
        self.assertEqual(len(set(rng)), len(rng))

    def test_golden_pin(self):
        from core import shielding_tables as st
        self.assertEqual(st._CSDA_RANGE["proton"]["water"][100.0], 7.718)
        self.assertEqual(st._CSDA_RANGE["proton"]["water"][10.0], 0.1230)
        self.assertEqual(st._CSDA_RANGE["proton"]["water"][250.0], 37.94)

    def test_validation(self):
        for kw in (
            {"areal_density_gcm2": 10, "particle": "proton", "material": "water"},  # no energy
            {"areal_density_gcm2": 10, "particle": "proton", "material": "water", "energy_mev": 0},  # E≤0
            {"areal_density_gcm2": 10, "particle": "alpha", "material": "water", "energy_mev": 100},  # no bundled alpha
            {"areal_density_gcm2": 10, "particle": "proton", "material": "lead", "energy_mev": 100},  # no bundled mat
            {"areal_density_gcm2": 10, "particle": "proton", "csda_range_gcm2": 0},  # explicit range ≤0
            {"areal_density_gcm2": 10, "particle": "proton", "energy_mev": 100},     # no material, no override
        ):
            self.assertIn("error", thermal.compute_shielding_attenuation(**kw), kw)


class ShieldingLayersTest(unittest.TestCase):
    # C7 — multi-layer stacks
    def test_single_layer_parity(self):
        stacked = thermal.compute_shielding_attenuation(layers="water:20", energy_mev=1.0)
        single = thermal.compute_shielding_attenuation(areal_density_gcm2=20, material="water",
                                                       energy_mev=1.0)
        self.assertAlmostEqual(stacked["total_transmitted_fraction"],
                               single["transmitted_fraction"], places=12)

    def test_two_layers_product(self):
        r = thermal.compute_shielding_attenuation(layers="water:10, lead:5", energy_mev=1.0)
        self.assertEqual(len(r["layers"]), 2)
        prod = r["layers"][0]["transmitted_fraction"] * r["layers"][1]["transmitted_fraction"]
        self.assertAlmostEqual(r["total_transmitted_fraction"], prod, places=12)
        self.assertAlmostEqual(r["total_areal_density_gcm2"], 15.0, places=9)

    def test_order_independence(self):
        a = thermal.compute_shielding_attenuation(layers="water:10, lead:5", energy_mev=1.0)
        b = thermal.compute_shielding_attenuation(layers="lead:5, water:10", energy_mev=1.0)
        self.assertAlmostEqual(a["total_transmitted_fraction"],
                               b["total_transmitted_fraction"], places=12)

    def test_gcr_layers(self):
        r = thermal.compute_shielding_attenuation(mode="gcr", layers="polyethylene:30, water:10")
        self.assertTrue(r["is_order_of_magnitude"])
        self.assertEqual(len(r["layers"]), 2)

    def test_validation(self):
        for kw in (
            {"layers": "water 20", "energy_mev": 1.0},                # malformed token (no colon)
            {"layers": "water:abc", "energy_mev": 1.0},               # non-numeric σ
            {"layers": "unobtainium:10", "energy_mev": 1.0},          # unknown material
            {"layers": "water:-5", "energy_mev": 1.0},                # non-positive σ
            {"layers": "water:20"},                                   # photon layer, no energy
        ):
            self.assertIn("error", thermal.compute_shielding_attenuation(**kw), kw)


class ShieldingValidationTest(unittest.TestCase):
    def test_validation(self):
        for kw in (
            {"particle": "muon", "areal_density_gcm2": 10},                             # bad particle
            {"mode": "bogus", "areal_density_gcm2": 10, "mass_atten_coeff_cm2g": 0.07},  # bad mode
            {"areal_density_gcm2": 10, "thickness_cm": 5, "mass_atten_coeff_cm2g": 0.07},  # both Σ paths
            {"areal_density_gcm2": -1, "mass_atten_coeff_cm2g": 0.07},        # neg Σ
            {"thickness_cm": 5, "mass_atten_coeff_cm2g": 0.07},              # thickness w/o density
            {"thickness_cm": 0, "density_gcm3": 1, "mass_atten_coeff_cm2g": 0.07},  # zero thickness
            {"areal_density_gcm2": 10},                                       # photon: no coeff/material
            {"areal_density_gcm2": 10, "material": "unobtainium", "energy_mev": 1.0},  # off-grid mat
            {"areal_density_gcm2": 10, "material": "water"},                  # photon: no energy
            {"areal_density_gcm2": 10, "mass_atten_coeff_cm2g": 0},           # zero coeff
            {"mode": "gcr", "areal_density_gcm2": 10},                        # gcr: no Λ/material
            {"mode": "gcr", "areal_density_gcm2": 10, "material": "lead"},    # gcr: no bundled Λ for lead
        ):
            self.assertIn("error", thermal.compute_shielding_attenuation(**kw), kw)


class HeatPumpTest(unittest.TestCase):
    """R3 (Phase AL) — active-refrigeration Carnot COP (the inverse of waste-heat)."""

    def test_anchor_lift_1w_300_to_320(self):
        r = thermal.compute_heat_pump(cold_temp_k=300, hot_temp_k=320, heat_lifted_w=1.0)
        self.assertAlmostEqual(r["cop_cool_carnot"], 15.0, places=6)
        self.assertAlmostEqual(r["cop_heat_carnot"], 16.0, places=6)
        self.assertAlmostEqual(r["work_w"], 1.0 / 15.0, places=9)
        self.assertAlmostEqual(r["heat_rejected_w"], 1.0 + 1.0 / 15.0, places=9)
        self.assertIn("model_note", r)

    def test_work_anchor_consistent_with_heat_anchor(self):
        # Q_c given and W given should round-trip to the same heat_rejected_w.
        by_qc = thermal.compute_heat_pump(cold_temp_k=300, hot_temp_k=320, heat_lifted_w=1.0)
        by_w = thermal.compute_heat_pump(cold_temp_k=300, hot_temp_k=320, work_w=by_qc["work_w"])
        self.assertAlmostEqual(by_w["heat_lifted_w"], 1.0, places=9)
        self.assertAlmostEqual(by_w["heat_rejected_w"], by_qc["heat_rejected_w"], places=9)

    def test_efficiency_fraction_scales_cop(self):
        r = thermal.compute_heat_pump(cold_temp_k=300, hot_temp_k=320, heat_lifted_w=1.0,
                                      efficiency_fraction=0.5)
        self.assertAlmostEqual(r["cop_cool_actual"], 7.5, places=6)

    def test_errors(self):
        for kw in (
            {"cold_temp_k": 320, "hot_temp_k": 300, "heat_lifted_w": 1.0},   # T_h <= T_c
            {"cold_temp_k": 300, "hot_temp_k": 320},                         # no load anchor
            {"cold_temp_k": 300, "hot_temp_k": 320, "heat_lifted_w": 1.0, "work_w": 1.0},  # both
            {"cold_temp_k": -1, "hot_temp_k": 320, "heat_lifted_w": 1.0},    # T <= 0
            {"cold_temp_k": 300, "hot_temp_k": 320, "heat_lifted_w": 1.0,
             "efficiency_fraction": 1.5},                                    # frac out of range
        ):
            self.assertIn("error", thermal.compute_heat_pump(**kw))


class DeterminismTest(unittest.TestCase):
    def test_deterministic(self):
        for fn, kw in (
            (thermal.compute_waste_heat, {"input_power_watts": 3e9, "efficiency": 0.4}),
            (thermal.compute_radiator_area, {"heat_watts": 1e9, "radiator_temp_k": 300}),
            (thermal.compute_shielding_attenuation,
             {"material": "water", "energy_mev": 1.0, "areal_density_gcm2": 20}),
            (thermal.compute_heat_pump,
             {"cold_temp_k": 300, "hot_temp_k": 320, "heat_lifted_w": 1.0}),
        ):
            self.assertEqual(fn(**kw), fn(**kw))


if __name__ == "__main__":
    unittest.main()
