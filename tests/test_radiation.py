# tests/test_radiation.py — Phase AS (Packet 34) radiation dose → per-clade ceiling converter.
#
# In-process, offline (no DB/network/RNG/time). Reproduces the eight §3 acceptance cases and
# the §3 edge/limit behaviors from the request, the two-axis independence, the lever-coupling
# enforcement, provenance tagging, and determinism.

import unittest

import core.radiation as r
import core.radiation_tables as rt


class AcceptanceCasesTest(unittest.TestCase):
    def test_case1_baseline_acute_4gy_photon_ld50_band(self):
        d = r.compute_radiation_ceiling(clade="baseline-human", profile="acute",
                                        absorbed_dose_gy=4.0, let_kev_um=0.3)
        a = d["axis_a_deterministic"]
        self.assertTrue(a["applicable"])
        self.assertAlmostEqual(a["clade_acute_ceiling_gy"], 3.75, places=6)
        self.assertTrue(1.0 <= a["fraction_of_ceiling"] <= 1.1)   # ~50% lethality region
        self.assertEqual(a["ars_severity_band"], "ld50-region")

    def test_case2_baseline_chronic_600msv_is_exactly_3pct_reid(self):
        d = r.compute_radiation_ceiling(clade="baseline-human", profile="chronic",
                                        absorbed_dose_gy=0.6, let_kev_um=0.3)
        b = d["axis_b_stochastic"]
        self.assertAlmostEqual(b["reid_percent"], 3.0, places=9)          # the policy anchor, exact
        self.assertAlmostEqual(b["fraction_of_budget"], 1.0, places=9)
        self.assertFalse(d["axis_a_deterministic"]["applicable"])          # acute ceiling not triggered

    def test_case3_hze_exhausts_budget_faster_than_photon(self):
        photon = r.compute_radiation_ceiling(absorbed_dose_gy=0.1, let_kev_um=0.3)
        hze = r.compute_radiation_ceiling(absorbed_dose_gy=0.1, let_kev_um=100.0)
        bp, bh = photon["axis_b_stochastic"], hze["axis_b_stochastic"]
        # Equal absorbed Gy, but Q(HZE) >> Q(photon) → higher Sv & REID for HZE.
        self.assertGreater(bh["cumulative_equivalent_dose_sv"], bp["cumulative_equivalent_dose_sv"])
        self.assertGreater(bh["reid_percent"], bp["reid_percent"])
        self.assertAlmostEqual(hze["exposure"]["q_effective"], 29.8, places=6)  # ICRP Q(100)=30-ish
        self.assertAlmostEqual(photon["exposure"]["q_effective"], 1.0, places=6)

    def test_case4_genemod_dsup_is_about_2x_not_3000x(self):
        d = r.compute_radiation_ceiling(clade="gene-mod", absorbed_dose_gy=4.0, let_kev_um=0.3)
        a = d["axis_a_deterministic"]
        self.assertAlmostEqual(a["clade_acute_ceiling_gy"], 7.5, places=6)   # ~2× baseline 3.75
        self.assertAlmostEqual(d["clade_modifiers"]["m_a"], 2.0, places=6)
        self.assertLess(a["clade_acute_ceiling_gy"], rt.DEINOCOCCUS_CEILING_GY)  # not 3000×
        self.assertEqual(d["clade_confidence"], "extrapolation")

    def test_case5_misengineered_clade_lowers_ceiling_below_baseline(self):
        d = r.compute_radiation_ceiling(clade="custom", lever="repair-fidelity",
                                        lever_m_a=0.8, lever_m_b=1.2,
                                        absorbed_dose_gy=3.0, let_kev_um=0.3)
        a = d["axis_a_deterministic"]
        self.assertAlmostEqual(a["clade_acute_ceiling_gy"], 3.0, places=6)   # ~3 Gy fatal (S14)
        self.assertLess(a["clade_acute_ceiling_gy"], rt.LD50_REFERENCE_GY)   # signed m_A works

    def test_case6_upload_returns_na_both_axes_and_seu_budget(self):
        d = r.compute_radiation_ceiling(clade="upload", fluence=1e10,
                                        memory_bits=1e12, ecc_margin=1e6)
        self.assertFalse(d["axis_a_deterministic"]["applicable"])
        self.assertFalse(d["axis_b_stochastic"]["applicable"])
        # No Gy/Sv emitted for the biological axes.
        self.assertNotIn("acute_equivalent_dose_gy", d["axis_a_deterministic"])
        self.assertNotIn("cumulative_equivalent_dose_sv", d["axis_b_stochastic"])
        seu = d["seu_budget"]
        self.assertTrue(seu["different_physical_quantity"])
        self.assertAlmostEqual(seu["expected_upsets"], 1e10 * rt.SEU_CROSS_SECTION_DEFAULT_CM2 * 1e12)
        self.assertFalse(seu["within_ecc_margin"])

    def test_case7_p53_trade_enforced_repair_fidelity_permitted(self):
        # p53 lever: acute up AND cancer up (the trade is enforced).
        p53 = r.compute_radiation_ceiling(clade="custom", lever="p53", lever_m_a=1.5, lever_m_b=1.5,
                                          absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertGreater(p53["clade_modifiers"]["m_a"], 1.0)
        self.assertGreater(p53["clade_modifiers"]["m_b"], 1.0)
        self.assertTrue(p53["clade_modifiers"]["coupling_enforced"])
        # p53 improving BOTH is forbidden by default…
        blocked = r.compute_radiation_ceiling(clade="custom", lever="p53", lever_m_a=1.5,
                                              lever_m_b=0.7, absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertIn("error", blocked)
        # …but overridable with the explicit flag.
        overridden = r.compute_radiation_ceiling(clade="custom", lever="p53", lever_m_a=1.5,
                                                 lever_m_b=0.7, absorbed_dose_gy=4.0, let_kev_um=0.3,
                                                 allow_p53_double_improve=True)
        self.assertNotIn("error", overridden)
        self.assertTrue(overridden["flags"]["p53_double_improve_overridden"])
        # repair-fidelity lever: both axes MAY improve (lever-specific coupling).
        rf = r.compute_radiation_ceiling(clade="custom", lever="repair-fidelity", lever_m_a=1.5,
                                         lever_m_b=0.7, absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertGreater(rf["clade_modifiers"]["m_a"], 1.0)
        self.assertLess(rf["clade_modifiers"]["m_b"], 1.0)

    def test_case8_sanity_bounds(self):
        # No Axis-A ceiling beyond the Deinococcus existence proof without the RB flag.
        blocked = r.compute_radiation_ceiling(clade="custom", lever="repair-fidelity",
                                              lever_m_a=2000.0, absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertIn("error", blocked)
        allowed = r.compute_radiation_ceiling(clade="custom", lever="repair-fidelity",
                                              lever_m_a=2000.0, absorbed_dose_gy=4.0, let_kev_um=0.3,
                                              allow_required_breakthrough=True)
        self.assertTrue(allowed["flags"]["required_breakthrough"])
        # Pharmacological DMF alone ≤ 3×.
        dmf = r.compute_radiation_ceiling(absorbed_dose_gy=4.0, let_kev_um=0.3, pharmacological_dmf=5.0)
        self.assertEqual(dmf["axis_a_deterministic"]["dmf_applied"], rt.DMF_MAX)
        self.assertTrue(dmf["flags"]["dmf_capped"])
        # career_budget always reported as policy, not physics.
        base = r.compute_radiation_ceiling(absorbed_dose_gy=0.6, let_kev_um=0.3, profile="chronic")
        self.assertEqual(base["axis_b_stochastic"]["provenance"]["career_budget_policy"], "policy")


class EdgeBehaviorTest(unittest.TestCase):
    def test_zero_dose_full_margin_both_axes(self):
        d = r.compute_radiation_ceiling(absorbed_dose_gy=0.0, let_kev_um=0.3)
        self.assertEqual(d["axis_a_deterministic"]["fraction_of_ceiling"], 0.0)
        self.assertEqual(d["axis_a_deterministic"]["ars_severity_band"], "none")
        self.assertEqual(d["axis_b_stochastic"]["reid_percent"], 0.0)

    def test_fluence_without_quality_is_error(self):
        self.assertIn("error", r.compute_radiation_ceiling(fluence=1e8))

    def test_off_table_let_flags_extrapolation_not_silent(self):
        d = r.compute_radiation_ceiling(absorbed_dose_gy=1.0, let_kev_um=2000.0)
        self.assertTrue(d["flags"]["out_of_range_let"])

    def test_let_spectrum_dose_weights_rbe_and_q(self):
        d = r.compute_radiation_ceiling(let_spectrum="0.3:1e9, 100:1e7")
        e = d["exposure"]
        self.assertEqual(e["source_form"], "let_spectrum")
        self.assertGreater(e["absorbed_dose_gy"], 0.0)
        # Composite Q sits between the photon (1) and HZE (~30) bin values.
        self.assertTrue(1.0 < e["q_effective"] < 30.0)
        self.assertTrue(1.0 <= e["rbe_effective"] <= 3.5)

    def test_both_axes_scored_for_an_acute_exposure(self):
        # Two independent numbers, never one scalar.
        d = r.compute_radiation_ceiling(absorbed_dose_gy=2.0, let_kev_um=0.3, profile="acute")
        self.assertTrue(d["axis_a_deterministic"]["applicable"])
        self.assertTrue(d["axis_b_stochastic"]["applicable"])
        self.assertIn("acute_equivalent_dose_gy", d["axis_a_deterministic"])
        self.assertIn("cumulative_equivalent_dose_sv", d["axis_b_stochastic"])

    def test_cyborg_scores_biology_and_hardware_seu(self):
        d = r.compute_radiation_ceiling(clade="cyborg", absorbed_dose_gy=2.0, let_kev_um=0.3,
                                        fluence=None)
        self.assertTrue(d["axis_a_deterministic"]["applicable"])   # biological fraction governs
        self.assertIsNotNone(d["seu_budget"])                      # hardware fraction → SEU
        # With no fluence, the SEU block asks for one rather than fabricating a rate.
        self.assertIsNone(d["seu_budget"]["seu_rate_per_bit"])

    def test_ddref_reduces_chronic_reid_when_set(self):
        base = r.compute_radiation_ceiling(absorbed_dose_gy=0.6, let_kev_um=0.3, profile="chronic")
        ddref2 = r.compute_radiation_ceiling(absorbed_dose_gy=0.6, let_kev_um=0.3, profile="chronic",
                                             ddref=2.0)
        self.assertAlmostEqual(ddref2["axis_b_stochastic"]["reid_percent"],
                               base["axis_b_stochastic"]["reid_percent"] / 2.0, places=9)

    def test_particle_preset_yields_high_let_rbe_above_one(self):
        d = r.compute_radiation_ceiling(absorbed_dose_gy=1.0, particle_type="iron")
        self.assertGreater(d["exposure"]["rbe_effective"], 1.0)   # HZE RBE > 1 (validation §3.3)


class QualityWeightingTest(unittest.TestCase):
    def test_rbe_and_q_are_distinct_numbers(self):
        # At L=100 keV/µm the deterministic RBE (~3) and the stochastic Q (~30) must differ.
        d = r.compute_radiation_ceiling(absorbed_dose_gy=1.0, let_kev_um=100.0)
        self.assertNotAlmostEqual(d["exposure"]["rbe_effective"], d["exposure"]["q_effective"])

    def test_icrp_q_relation_anchors(self):
        self.assertEqual(rt.q_for_let(5.0), 1.0)
        self.assertAlmostEqual(rt.q_for_let(100.0), 29.8, places=6)    # 0.32·100−2.2 (≤100 branch)
        self.assertAlmostEqual(rt.q_for_let(400.0), 15.0, places=6)    # 300/sqrt(400)

    def test_rbe_peaks_then_declines(self):
        peak = rt.rbe_for_let(200.0)[0]
        self.assertGreater(peak, rt.rbe_for_let(30.0)[0])
        self.assertGreater(peak, rt.rbe_for_let(1000.0)[0])   # declines past the peak


class ValidationMatrixTest(unittest.TestCase):
    def test_matrix(self):
        for kw in (
            {"clade": "nope", "absorbed_dose_gy": 1, "let_kev_um": 1},          # bad clade
            {"profile": "weekly", "absorbed_dose_gy": 1, "let_kev_um": 1},      # bad profile
            {"fluence": 1e8},                                                    # no quality
            {"absorbed_dose_gy": 1, "fluence": 1e8, "let_kev_um": 1},           # two magnitudes
            {"absorbed_dose_gy": -1, "let_kev_um": 1},                          # neg dose
            {"absorbed_dose_gy": 1, "let_kev_um": -1},                          # neg LET
            {"absorbed_dose_gy": 1, "let_kev_um": 1, "pharmacological_dmf": 0}, # DMF ≤ 0
            {"absorbed_dose_gy": 1, "let_kev_um": 1, "ddref": 0},               # DDREF ≤ 0
            {"absorbed_dose_gy": 1, "let_kev_um": 1, "career_budget_policy": "42"},  # bad policy
            {"absorbed_dose_gy": 1, "let_kev_um": 1, "lever": "voodoo"},        # bad lever
            {"let_spectrum": "junk"},                                            # malformed spectrum
            {"let_spectrum": "1e9:-1"},                                          # non-positive spectrum val
            {"absorbed_dose_gy": 1, "let_spectrum": "0.3:1e9"},                 # spectrum not exclusive
        ):
            self.assertIn("error", r.compute_radiation_ceiling(**kw), kw)


class DeterminismTest(unittest.TestCase):
    def test_deterministic(self):
        kw = dict(clade="gene-mod", absorbed_dose_gy=2.5, let_kev_um=50.0, profile="chronic",
                  ddref=2.0, pharmacological_dmf=1.5)
        self.assertEqual(r.compute_radiation_ceiling(**kw), r.compute_radiation_ceiling(**kw))

    def test_provenance_legend_present(self):
        d = r.compute_radiation_ceiling(absorbed_dose_gy=1.0, let_kev_um=0.3)
        for tag in ("physics-limit", "policy", "required-breakthrough", "extrapolation",
                    "present-datapoint"):
            self.assertIn(tag, d["provenance_legend"])
        self.assertTrue(d["is_order_of_magnitude"])

    def test_policy_rooted_axis_b_numbers_are_not_physics_limit(self):
        # F1/F2 (Packet-34 review): REID is a linear projection off the POLICY anchor, and the
        # clade-adjusted budget IS the policy budget — neither may be tagged physics-limit (§4 MTA).
        prov = r.compute_radiation_ceiling(clade="baseline-human", absorbed_dose_gy=0.6,
                                           let_kev_um=0.3, profile="chronic")["axis_b_stochastic"]["provenance"]
        self.assertEqual(prov["reid_percent"], "extrapolation")            # F1
        self.assertEqual(prov["clade_adjusted_budget_sv"], "policy")       # F2
        self.assertEqual(prov["career_budget_policy"], "policy")
        self.assertNotEqual(prov["reid_percent"], "physics-limit")
        self.assertNotEqual(prov["clade_adjusted_budget_sv"], "physics-limit")
        self.assertEqual(prov["q_used"], "physics-limit")                  # ICRP Q genuinely is

    def test_ddref_note_surfaced_only_when_non_default(self):
        base = r.compute_radiation_ceiling(absorbed_dose_gy=0.6, let_kev_um=0.3, profile="chronic")
        self.assertIsNone(base["axis_b_stochastic"]["ddref_note"])
        ddref2 = r.compute_radiation_ceiling(absorbed_dose_gy=0.6, let_kev_um=0.3, profile="chronic",
                                             ddref=2.0)
        self.assertIn("disagree", ddref2["axis_b_stochastic"]["ddref_note"].lower())

    def test_acute_axis_a_carries_baseline_photon_equivalent_band_note(self):
        d = r.compute_radiation_ceiling(absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertIn("baseline", d["axis_a_deterministic"]["ars_band_note"].lower())


if __name__ == "__main__":
    unittest.main()
