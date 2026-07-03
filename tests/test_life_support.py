# tests/test_life_support.py — Phase X closed-loop life-support calculators (core, in-process).
#
# Covers core/life_support.py + core/life_support_tables.py: bundled-table integrity, the X1/X2/X3
# acceptance anchors, override paths, the validation matrix, and determinism. Pure math, offline
# (no network / DB / Qt / RNG / clock).

import math
import unittest

import core.life_support as ls
import core.life_support_tables as t

_KCAL_TO_KJ = 4.184


class BundledTableTest(unittest.TestCase):
    def test_bvad_rates_match_rev2(self):
        r = t.get_bvad_rates()
        self.assertAlmostEqual(r["o2_kg"], 0.895)
        self.assertAlmostEqual(r["co2_kg"], 1.085)
        self.assertAlmostEqual(r["potable_water_kg"], 2.0)
        self.assertAlmostEqual(r["total_water_kg"], 9.12)
        self.assertAlmostEqual(r["food_dry_kg"], 0.800)
        self.assertAlmostEqual(r["kcal"], 3054.0)

    def test_crop_rows_present_and_energy_dense(self):
        crops = t.get_crops()
        for name in ("wheat", "white_potato", "sweet_potato", "soybean", "lettuce",
                     "chlorella", "spirulina"):
            self.assertIn(name, crops)
            self.assertGreater(crops[name]["energy_density_kcal_g"], 0)
            self.assertGreater(crops[name]["edible_dry_g_m2_d"], 0)
        # BVAD crops carry an HI + water uptake; algae do not.
        self.assertAlmostEqual(crops["wheat"]["hi"], 0.40)
        self.assertAlmostEqual(crops["wheat"]["water_uptake_kg_m2_d"], 11.79)
        self.assertIsNone(crops["chlorella"]["hi"])
        self.assertIsNone(crops["chlorella"]["water_uptake_kg_m2_d"])
        self.assertEqual(crops["chlorella"]["source_tag"], "algae")

    def test_par_photon_energy_first_principles(self):
        # h·c·N_A / 550 nm, per µmol. Bundled 0.2177 is the standard spectrum-weighted citation;
        # the monochromatic 550 nm recompute is ~0.2175 — agree within ~1%.
        h, c, na, lam = 6.62607015e-34, 2.99792458e8, 6.02214076e23, 550e-9
        recomputed = h * c * na / lam / 1e6
        self.assertLess(abs(t._PAR_J_PER_UMOL - recomputed), 0.01 * recomputed)

    def test_closure_scenarios_in_range(self):
        for name, sc in t.get_closure_scenarios().items():
            for stream in ("water", "o2", "food"):
                self.assertTrue(0.0 <= sc[stream] <= 1.0, (name, stream))


class X1LifeSupportTest(unittest.TestCase):
    def test_per_person_open_one_day(self):
        d = ls.compute_life_support()
        self.assertNotIn("error", d)
        p = d["per_person_daily"]
        self.assertAlmostEqual(p["o2_kg"], 0.895)
        self.assertAlmostEqual(p["co2_kg"], 1.085)
        self.assertAlmostEqual(p["food_dry_kg"], 0.800)
        self.assertAlmostEqual(p["kcal"], 3054.0)
        self.assertAlmostEqual(p["potable_water_kg"], 2.0)
        # open loop → makeup == total for every stream
        self.assertAlmostEqual(d["makeup_mass_kg"]["water"], d["totals"]["total_water_kg"])
        self.assertAlmostEqual(d["makeup_mass_kg"]["o2"], d["totals"]["o2_kg"])

    def test_linear_scaling(self):
        d = ls.compute_life_support(crew=6, days=180)
        self.assertAlmostEqual(d["totals"]["o2_kg"], 0.895 * 6 * 180)
        self.assertAlmostEqual(d["totals"]["food_dry_kg"], 0.800 * 6 * 180)

    def test_iss_closure_cuts_water_makeup(self):
        iss = ls.compute_life_support(days=365, closure_scenario="iss")
        opn = ls.compute_life_support(days=365, closure_scenario="open")
        # ISS water recycle 0.90 → makeup is 0.10× the open-loop water total
        self.assertAlmostEqual(iss["makeup_mass_kg"]["water"],
                               0.10 * opn["totals"]["total_water_kg"], places=6)
        self.assertLess(iss["makeup_mass_kg"]["water"], 0.2 * opn["makeup_mass_kg"]["water"])

    def test_kcal_override_scales_energy_not_o2(self):
        d = ls.compute_life_support(kcal_per_day=2500)
        self.assertAlmostEqual(d["per_person_daily"]["kcal"], 2500.0)
        self.assertAlmostEqual(d["per_person_daily"]["o2_kg"], 0.895)  # unchanged

    def test_rate_overrides_reproduce_older_set(self):
        d = ls.compute_life_support(o2_rate=0.816, food_dry_rate=0.617, kcal_per_day=2500)
        p = d["per_person_daily"]
        self.assertAlmostEqual(p["o2_kg"], 0.816)
        self.assertAlmostEqual(p["food_dry_kg"], 0.617)
        self.assertAlmostEqual(p["kcal"], 2500.0)

    def test_per_stream_closure_override(self):
        d = ls.compute_life_support(closure_scenario="open", water_closure=0.5)
        self.assertAlmostEqual(d["closure"]["water"], 0.5)
        self.assertAlmostEqual(d["makeup_mass_kg"]["water"], 0.5 * d["totals"]["total_water_kg"])

    def test_validation(self):
        self.assertIn("error", ls.compute_life_support(crew=0))
        self.assertIn("error", ls.compute_life_support(days=0))
        self.assertIn("error", ls.compute_life_support(o2_rate=-1))
        self.assertIn("error", ls.compute_life_support(water_closure=1.5))
        self.assertIn("error", ls.compute_life_support(closure_scenario="nope"))


class X2BioregenAreaTest(unittest.TestCase):
    def test_wheat_area_anchor(self):
        d = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30)
        self.assertNotIn("error", d)
        self.assertTrue(30.0 <= d["area_m2_per_person"] <= 50.0, d["area_m2_per_person"])
        # measured cross-check within a factor ~2 of the energy-balance area
        ratio = d["area_m2_per_person_measured"] / d["area_m2_per_person"]
        self.assertTrue(0.5 <= ratio <= 2.0, ratio)
        self.assertIn("par_is_input_note", d)

    def test_artificial_lighting_power_anchor(self):
        d = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30,
                                     artificial=True, led_par_efficiency=0.4)
        w = d["lighting"]["electrical_power_w_per_person"]
        self.assertTrue(5000.0 <= w <= 15000.0, w)
        self.assertTrue(d["lighting"]["artificial"])

    def test_no_artificial_power_null(self):
        d = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30)
        self.assertIsNone(d["lighting"]["electrical_power_w_per_person"])

    def test_three_light_anchors_agree(self):
        # DLI 30 mol/m²·d over a 16 h photoperiod == a specific PPFD and PAR W/m².
        base = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30, photoperiod_h=16)
        ppfd = 30e6 / (16 * 3600)
        by_ppfd = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat",
                                           ppfd_umol=ppfd, photoperiod_h=16)
        by_par = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat",
                                          par_wm2=base["lighting"]["par_wm2_delivered"],
                                          photoperiod_h=16)
        self.assertAlmostEqual(base["area_m2_per_person"], by_ppfd["area_m2_per_person"], places=3)
        self.assertAlmostEqual(base["area_m2_per_person"], by_par["area_m2_per_person"], places=3)

    def test_algae_smaller_area(self):
        wheat = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30)
        algae = ls.compute_bioregen_area(kcal_per_day=2500, crop="chlorella", dli_mol=30)
        self.assertLess(algae["area_m2_per_person"], wheat["area_m2_per_person"])
        self.assertIsNone(algae["photo_efficiency"])  # algae take the productivity path
        # still reports gas exchange
        self.assertIsNotNone(algae["crop_gas_exchange"]["o2_kg_day"])
        self.assertIsNone(algae["transpiration_water_kg_day"])

    def test_gas_and_transpiration_scale_with_crew(self):
        one = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30)
        six = ls.compute_bioregen_area(kcal_per_day=2500, crew=6, crop="wheat", dli_mol=30)
        self.assertAlmostEqual(six["crop_gas_exchange"]["o2_kg_day"],
                               6 * one["crop_gas_exchange"]["o2_kg_day"], places=6)
        self.assertAlmostEqual(six["transpiration_water_kg_day"],
                               6 * one["transpiration_water_kg_day"], places=6)

    def test_generic_hi_required_without_crop(self):
        self.assertIn("error", ls.compute_bioregen_area(kcal_per_day=2500, dli_mol=30))
        ok = ls.compute_bioregen_area(kcal_per_day=2500, dli_mol=30, harvest_index=0.4)
        self.assertNotIn("error", ok)
        self.assertIsNone(ok["crop_gas_exchange"]["o2_kg_day"])  # no crop → no gas exchange

    def test_validation(self):
        self.assertIn("error", ls.compute_bioregen_area(kcal_per_day=0, dli_mol=30, harvest_index=0.4))
        self.assertIn("error", ls.compute_bioregen_area(crew=0, dli_mol=30, harvest_index=0.4))
        self.assertIn("error", ls.compute_bioregen_area(dli_mol=30, harvest_index=0.4, photoperiod_h=0))
        self.assertIn("error", ls.compute_bioregen_area(dli_mol=30, harvest_index=1.5))
        self.assertIn("error", ls.compute_bioregen_area(dli_mol=30, harvest_index=0.4, photo_efficiency=0))
        self.assertIn("error", ls.compute_bioregen_area(dli_mol=30, harvest_index=0.4, led_par_efficiency=2))
        self.assertIn("error", ls.compute_bioregen_area(dli_mol=30, harvest_index=0.4, f_edible_energy=0))
        self.assertIn("error", ls.compute_bioregen_area(crop="bogus", dli_mol=30))
        # zero / two light anchors
        self.assertIn("error", ls.compute_bioregen_area(crop="wheat", harvest_index=0.4))
        self.assertIn("error", ls.compute_bioregen_area(crop="wheat", dli_mol=30, ppfd_umol=500))


class C10CropMixTest(unittest.TestCase):
    """Phase AD (C10) — the --crops diet-mix (calorie-split area sum)."""

    def test_single_crop_mix_matches_single_crop(self):
        single = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30)
        mix = ls.compute_bioregen_area(kcal_per_day=2500, crops="wheat:1.0", dli_mol=30)
        self.assertAlmostEqual(mix["area_m2_per_person"], single["area_m2_per_person"], places=9)
        self.assertAlmostEqual(mix["area_m2_total"], single["area_m2_total"], places=9)
        self.assertAlmostEqual(mix["crop_gas_exchange"]["o2_kg_day"],
                               single["crop_gas_exchange"]["o2_kg_day"], places=9)
        self.assertEqual(len(mix["per_crop_area_m2"]), 1)
        self.assertEqual(mix["per_crop_area_m2"][0]["crop"], "wheat")

    def test_mix_is_calorie_weighted_sum(self):
        d = ls.compute_bioregen_area(kcal_per_day=2500,
                                     crops="wheat:0.5, white_potato:0.3, soybean:0.2", dli_mol=30)
        self.assertEqual([c["crop"] for c in d["per_crop_area_m2"]],
                         ["wheat", "white_potato", "soybean"])
        # total = Σ per-crop; each crop's area = its calorie share at its own HI
        self.assertAlmostEqual(d["area_m2_total"],
                               sum(c["area_m2_total"] for c in d["per_crop_area_m2"]), places=9)
        # per-crop = single-crop area × that crop's calorie fraction
        for name, frac in (("wheat", 0.5), ("white_potato", 0.3), ("soybean", 0.2)):
            single = ls.compute_bioregen_area(kcal_per_day=2500, crop=name, dli_mol=30)
            row = next(c for c in d["per_crop_area_m2"] if c["crop"] == name)
            self.assertAlmostEqual(row["area_m2_per_person"],
                                   single["area_m2_per_person"] * frac, places=9)

    def test_lp_deferral_note_present(self):
        d = ls.compute_bioregen_area(kcal_per_day=2500, crops="wheat:1.0", dli_mol=30)
        self.assertIn("linear-programming", d["model_note"])

    def test_validation(self):
        self.assertIn("error", ls.compute_bioregen_area(crops="wheat:0.5, potato:0.6", dli_mol=30))   # not summing 1
        self.assertIn("error", ls.compute_bioregen_area(crops="wheat:0.5, bogus:0.5", dli_mol=30))    # unknown crop
        self.assertIn("error", ls.compute_bioregen_area(crops="wheatnocolon", dli_mol=30))            # malformed token
        self.assertIn("error", ls.compute_bioregen_area(crops="wheat:xyz", dli_mol=30))               # bad fraction
        self.assertIn("error", ls.compute_bioregen_area(crops="wheat:-0.5, potato:1.5", dli_mol=30))  # negative frac
        self.assertIn("error", ls.compute_bioregen_area(crops="", dli_mol=30))                        # empty
        self.assertIn("error", ls.compute_bioregen_area(crop="wheat", crops="wheat:1.0", dli_mol=30)) # both

    def test_determinism(self):
        kw = dict(kcal_per_day=2500, crops="wheat:0.6, soybean:0.4", dli_mol=30, crew=4)
        self.assertEqual(ls.compute_bioregen_area(**kw), ls.compute_bioregen_area(**kw))


class X3PopulationCapacityTest(unittest.TestCase):
    def test_power_bound(self):
        d = ls.compute_population_capacity(power_w=1e6, per_person_power_w=1e4)
        self.assertAlmostEqual(d["sustainable_population"], 100.0)
        self.assertEqual(d["binding_constraint"], "power")

    def test_binding_flips_to_nitrogen(self):
        d = ls.compute_population_capacity(power_w=1e6, per_person_power_w=1e4,
                                           fixed_nitrogen_kg_yr=100)  # 100/5 = 20 people
        self.assertEqual(d["binding_constraint"], "fixed_nitrogen")
        self.assertAlmostEqual(d["sustainable_population"], 20.0)
        self.assertIn("power", d["slack"])
        self.assertGreater(d["slack"]["power"], 0)

    def test_default_vs_flag_source(self):
        d = ls.compute_population_capacity(water_kg_day=100)
        self.assertEqual(d["per_resource"]["water"]["source"], "default")
        d2 = ls.compute_population_capacity(water_kg_day=100, per_person_water_kg_day=2.0)
        self.assertEqual(d2["per_resource"]["water"]["source"], "flag")
        self.assertAlmostEqual(d2["sustainable_population"], 50.0)

    def test_omitted_resource_not_counted(self):
        d = ls.compute_population_capacity(power_w=1e6, per_person_power_w=1e4)
        self.assertEqual(set(d["per_resource"].keys()), {"power"})

    def test_validation(self):
        self.assertIn("error", ls.compute_population_capacity())
        self.assertIn("error", ls.compute_population_capacity(power_w=-1))
        self.assertIn("error", ls.compute_population_capacity(power_w=1e6, per_person_power_w=0))


class DeterminismTest(unittest.TestCase):
    def test_deep_equal(self):
        a = ls.compute_life_support(crew=4, days=90, closure_scenario="bioregen")
        b = ls.compute_life_support(crew=4, days=90, closure_scenario="bioregen")
        self.assertEqual(a, b)
        c = ls.compute_bioregen_area(kcal_per_day=3000, crop="soybean", dli_mol=25, artificial=True)
        d = ls.compute_bioregen_area(kcal_per_day=3000, crop="soybean", dli_mol=25, artificial=True)
        self.assertEqual(c, d)


if __name__ == "__main__":
    unittest.main()
