# tests/test_nuclear.py — CR-4 nuclear-fuel & radiogenic inventory (core, offline).
#
# Pins the shared Interface-A solar anchor (present U-235/U-238 ≈ 0.00725), the corrected
# radiogenic BSE anchor (~5e-12 W/kg), and the monotonicity + honest-empty criteria.

import unittest

import core.nuclear as nuclear
import core.nuclear_tables as nt


def _solar():
    return nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.0)


class FissileAnchorTest(unittest.TestCase):
    def test_solar_u235_u238_anchor(self):
        f = _solar()["fissile"]
        # The shared Interface-A validation: production(1.35) → formation-epoch → decay → 0.00725.
        self.assertAlmostEqual(f["U235_U238_ratio"], 0.00725, delta=1e-4)

    def test_solar_isotopic_and_actinide_fractions(self):
        f = _solar()["fissile"]
        self.assertAlmostEqual(f["U235_frac"] + f["U238_frac"], 1.0, places=9)
        self.assertAlmostEqual(f["U235_frac"], 0.0072, delta=5e-4)
        self.assertAlmostEqual(f["Th232_frac"], 0.80, delta=0.02)   # Th/U(number) ≈ 4

    def test_younger_star_higher_u235_u238(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=1.0, eu_h=0.0)
        self.assertGreater(young["fissile"]["U235_U238_ratio"], _solar()["fissile"]["U235_U238_ratio"])

    def test_r_process_poor_lower_absolute_same_ratio(self):
        poor = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_h=-1.0)
        self.assertLess(poor["fissile"]["u_over_h"], _solar()["fissile"]["u_over_h"])
        # The isotopic ratio is Eu-independent (a ratio) → unchanged by r-process poverty.
        self.assertAlmostEqual(poor["fissile"]["U235_U238_ratio"],
                               _solar()["fissile"]["U235_U238_ratio"], delta=1e-4)

    def test_no_tracer_is_note_not_null(self):
        f = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567)["fissile"]
        self.assertIsNone(f["U235_frac"])
        self.assertIn("note", f)

    def test_eu_fe_equivalent_to_eu_h(self):
        # [Eu/Fe]=−0.5 at [Fe/H]=−0.5 → [Eu/H]=−1.0.
        a = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_fe=-0.5)
        b = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_h=-1.0)
        self.assertAlmostEqual(a["fissile"]["u_over_h"], b["fissile"]["u_over_h"], places=18)


class RadiogenicTest(unittest.TestCase):
    def test_solar_bse_anchor_order(self):
        q = _solar()["radiogenic_heat_W_per_kg"]
        self.assertTrue(3e-12 < q < 8e-12, f"radiogenic {q} outside 3–8e-12 W/kg BSE band")
        self.assertAlmostEqual(q, 5.03e-12, delta=0.3e-12)

    def test_younger_body_hotter(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=1.0, eu_h=0.0)
        self.assertGreater(young["radiogenic_heat_W_per_kg"], _solar()["radiogenic_heat_W_per_kg"])

    def test_metal_rich_hotter(self):
        rich = nuclear.compute_nuclear_inventory(fe_h=0.3, age_gyr=4.567, eu_h=0.0)
        self.assertGreater(rich["radiogenic_heat_W_per_kg"], _solar()["radiogenic_heat_W_per_kg"])


class FusionTest(unittest.TestCase):
    def test_d_h_astrated_below_primordial(self):
        f = _solar()["fusion"]
        self.assertLess(f["D_over_H"], 2.53e-5)          # astrated below BBN primordial
        self.assertGreater(f["D_over_H"], 1.0e-5)

    def test_d_h_higher_at_lower_metallicity(self):
        poor = nuclear.compute_nuclear_inventory(fe_h=-1.0, age_gyr=4.567, eu_h=-1.0)
        self.assertGreater(poor["fusion"]["D_over_H"], _solar()["fusion"]["D_over_H"])


class ProvenanceAndValidationTest(unittest.TestCase):
    def test_domain_ok_true_solar_false_out_of_range(self):
        self.assertTrue(_solar()["provenance"]["domain_ok"])
        old = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=15.0, eu_h=0.0)
        self.assertFalse(old["provenance"]["domain_ok"])
        self.assertIsNotNone(old["provenance"]["domain_note"])

    def test_provenance_carries_gce_version(self):
        prov = _solar()["provenance"]
        self.assertIn("gce_model_version", prov)
        self.assertEqual(prov["gce_model_version"], "3c-v1.0.0-2026-08-15")   # 3c FINAL swapped in


class Gce3cFinalTest(unittest.TestCase):
    """The 3c FINAL age-dependent uniform-production survival integral (coordination MSG 042)."""

    def test_gce_factor_matches_3c_derived_table(self):
        # g_i(age) reproduces the delivered fissile-fraction-gce-model.json derived_table_validation.
        # The line-28 formula is authoritative; the table is rounded (its steep old-age end, e.g.
        # age-10 U235 0.5118, is ~0.2% off the exact integral) — cross-check to 0.2%, not bit-exact.
        for age, gu235, gu238, gth in [
                (4.567, 0.1452, 0.6105, 0.8458), (0.5, 0.0918, 0.4782, 0.7708),
                (8.0, 0.2770, 0.7687, 0.9172), (10.0, 0.5118, 0.8885, 0.9626)]:
            self.assertAlmostEqual(nt.gce_enrichment_factor("U235", age), gu235, delta=2e-3)
            self.assertAlmostEqual(nt.gce_enrichment_factor("U238", age), gu238, delta=2e-3)
            self.assertAlmostEqual(nt.gce_enrichment_factor("Th232", age), gth, delta=2e-3)

    def test_halo_floor_above_d_eff(self):
        # age ≥ D_eff (11.55) → fresh-production floor g_i = 1.
        for iso in ("U235", "U238", "Th232"):
            self.assertEqual(nt.gce_enrichment_factor(iso, 12.0), 1.0)

    def test_dv2_actinide_boost_voids_domain(self):
        # [Eu/Fe] ≳ +0.7 (r-II star) → domain_ok False, reason names Eu/Fe.
        d = nuclear.compute_nuclear_inventory(fe_h=-1.0, age_gyr=5.0, eu_fe=1.0)
        self.assertFalse(d["provenance"]["domain_ok"])
        self.assertIn("Eu/Fe", d["provenance"]["domain_note"])

    def test_domain_bands_flag_regimes(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=3.0, eu_h=0.0)
        self.assertTrue(any("young band" in b for b in young["provenance"]["bands"]))
        old = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=10.0, eu_h=0.0)
        self.assertTrue(any("ISM-mixing" in b for b in old["provenance"]["bands"]))
        self.assertTrue(any("joint" in b for b in old["provenance"]["bands"]))

    def test_cq_7_3c_3_boundary_holes_closed(self):
        # CQ-7-3c-3 (DEFECT-3): age exactly 4.0/8.0 and the 11.5<A<11.55 sliver previously fell in NO band.
        from core import nuclear_tables as nt
        self.assertTrue(nt.gce_domain_ok(4.0, 0.0, eu_fe=0.0)[2], "age 4.0 young-edge hole")
        self.assertTrue(nt.gce_domain_ok(8.0, 0.0, eu_fe=0.0)[2], "age 8.0 joint-edge hole")
        self.assertTrue(nt.gce_domain_ok(11.52, 0.0, eu_fe=0.0)[2], "11.5-11.55 ISM sliver hole")
        self.assertEqual(nt.gce_domain_ok(7.9, 0.0, eu_fe=0.0)[2], [])   # a genuinely mid-age star: no band

    def test_bad_inputs_error(self):
        self.assertIn("error", nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=-1.0))
        self.assertIn("error", nuclear.compute_nuclear_inventory(fe_h=None, age_gyr=4.567))
        self.assertIn("error", nuclear.compute_nuclear_inventory(
            fe_h=0.0, age_gyr=4.567, eu_h=0.0, eu_fe=0.0))
        self.assertIn("error", nuclear.compute_nuclear_inventory(
            fe_h=0.0, age_gyr=4.567, population="disk"))


class Cq73c1RadiogenicEuWiringTest(unittest.TestCase):
    """CQ-7-3c-1 (WB MSG 079): the radiogenic-heat actinide channels track [Eu/H], not [Fe/H];
    withheld when no r-process tracer (never the 10^[Fe/H] co-formation fallback)."""

    def test_heat_tracks_eu_h_not_fe_h(self):
        solar = _solar()["radiogenic_heat_W_per_kg"]
        eu_rich = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.5)
        eu_poor = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=-1.0)
        self.assertGreater(eu_rich["radiogenic_heat_W_per_kg"], solar)   # more Eu → more actinide → hotter
        self.assertLess(eu_poor["radiogenic_heat_W_per_kg"], solar)      # r-poor → cooler

    def test_solar_anchor_unchanged_by_the_rewiring(self):
        # The Eu-anchor rewiring must leave the solar BSE anchor byte-stable.
        self.assertAlmostEqual(_solar()["radiogenic_heat_W_per_kg"], 5.03e-12, delta=0.3e-12)

    def test_actinide_channels_use_eu_not_fe(self):
        # At fixed [Eu/H]=0 the actinide comps are Fe-independent; only K-40 moves with [Fe/H].
        a = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.0)["radiogenic_heat"]
        b = nuclear.compute_nuclear_inventory(fe_h=0.5, age_gyr=4.567, eu_h=0.0)["radiogenic_heat"]
        self.assertAlmostEqual(a["components_W_per_kg"]["U238"], b["components_W_per_kg"]["U238"], places=20)
        self.assertGreater(b["components_W_per_kg"]["K40"], a["components_W_per_kg"]["K40"])  # K40 ∝ 10^[Fe/H]
        self.assertEqual(a["actinide_scaling"], "eu_h_gce_actinide_inventory")

    def test_heat_withheld_without_eu_no_fe_fallback(self):
        rh = nuclear.compute_nuclear_inventory(fe_h=0.3, age_gyr=4.567)["radiogenic_heat"]
        self.assertIsNone(rh["value_W_per_kg"])              # withheld, NOT a 10^[Fe/H] number
        self.assertFalse(rh["computable"])
        self.assertIsNone(rh["components_W_per_kg"]["U238"])
        self.assertIsNotNone(rh["components_W_per_kg"]["K40"])   # K-40 partial still shown for reference
        self.assertEqual(rh["actinide_scaling"], "withheld")
        # top-level headline mirrors the withhold
        self.assertIsNone(nuclear.compute_nuclear_inventory(fe_h=0.3, age_gyr=4.567)["radiogenic_heat_W_per_kg"])

    def test_heat_isotopic_split_is_the_stars_own(self):
        # A young star's U-235/U-238 heat ratio must exceed the solar one (star's own age-dependent split).
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=1.0, eu_h=0.0)["radiogenic_heat"]
        solar = _solar()["radiogenic_heat"]
        y = young["components_W_per_kg"]["U235"] / young["components_W_per_kg"]["U238"]
        s = solar["components_W_per_kg"]["U235"] / solar["components_W_per_kg"]["U238"]
        self.assertGreater(y, s)


class Cq73c24DomainGuardTest(unittest.TestCase):
    """CQ-7-3c-2 (DV-1 age_soft + DV-3 s-process) and CQ-7-3c-4 (tri-state + per-output + multi-reason)."""

    def test_dv3_s_process_proxy_flags_thin_disk_high_eu(self):
        # The runbook's canonical distrust case (thin-disk, [Fe/H]0, [Eu/Fe]+0.5) previously → domain_ok=true.
        d = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=5.0, eu_fe=0.5, population="thin")["provenance"]
        self.assertFalse(d["domain_ok"])
        self.assertTrue(d["flags"]["s_process"])
        self.assertEqual(d["per_output"]["isotope_ratio"], "ok")        # ratio is Eu-independent → survives
        self.assertEqual(d["per_output"]["tonnage"], "unreliable")
        self.assertEqual(d["per_output"]["radiogenic_heat"], "unreliable")

    def test_dv3_does_not_fire_for_metal_poor_halo(self):
        # A metal-poor star with the same [Eu/Fe] is genuine r-process → not DV-3.
        d = nuclear.compute_nuclear_inventory(fe_h=-1.5, age_gyr=11.0, eu_fe=0.5, population="halo")["provenance"]
        self.assertFalse(d["flags"]["s_process"])

    def test_dv3_ba_eu_preferred_discriminant(self):
        s = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=5.0, eu_h=0.0, ba_eu=0.7)["provenance"]
        r = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=5.0, eu_h=0.0, ba_eu=-0.6)["provenance"]
        self.assertTrue(s["flags"]["s_process"])        # [Ba/Eu] ≥ +0.5 (CEMP-s) → s-dominance
        self.assertFalse(r["flags"]["s_process"])       # [Ba/Eu] ≈ pure-r → clean

    def test_dv3_ba_eu_solar_reference_not_flagged(self):
        # Guard (Gate-B #1): a solar-composition star ([Ba/Eu]=0, the anchor) must NOT read s-process.
        d = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.0, ba_eu=0.0)["provenance"]
        self.assertFalse(d["flags"]["s_process"])
        self.assertTrue(d["domain_ok"])
        self.assertEqual(d["per_output"]["tonnage"], "ok")

    def test_dv1_age_soft_is_advisory_flag_not_veto(self):
        d = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=5.0, eu_h=0.0, age_soft=True)["provenance"]
        self.assertTrue(d["domain_ok"])                 # advisory (order-of-magnitude), NOT a veto
        self.assertTrue(d["flags"]["age_soft"])
        self.assertTrue(any("age_soft" in b for b in d["bands"]))

    def test_cq_4_tri_state_unevaluable_without_eu(self):
        # No r-process tracer → DV-2/DV-3 unevaluable → domain_ok is None, not a confident True.
        d = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=5.0)["provenance"]
        self.assertIsNone(d["domain_ok"])
        self.assertEqual(d["per_output"]["radiogenic_heat"], "unevaluable")

    def test_cq_4_multi_reason_no_shadowing(self):
        # age out AND [Fe/H] out AND DV-2 all fire → three reasons collected (no elif shadow).
        d = nuclear.compute_nuclear_inventory(fe_h=-3.0, age_gyr=14.0, eu_h=-2.0)["provenance"]
        self.assertFalse(d["domain_ok"])
        self.assertGreaterEqual(len(d["domain_reasons"]), 3)

    def test_domain_detail_tuple_is_four_wide(self):
        # gce_domain_ok grew a 4th (detail) element; bands stay at index [2] for the CQ-3 tests.
        res = nt.gce_domain_ok(5.0, 0.0, eu_fe=0.0)
        self.assertEqual(len(res), 4)
        self.assertIsInstance(res[2], list)
        self.assertIn("per_output", res[3])


if __name__ == "__main__":
    unittest.main()
