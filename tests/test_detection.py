# tests/test_detection.py — CR-6 detection-completeness (core, offline).
#
# Pins the Sun@10pc RV floor validation, the PER-METHOD monotonicity (RV/transit harden with SMA;
# astrometry/imaging ease with SMA), the astrometry baseline gate, and the honest transit-N/A path.

import unittest

import core.calculators as calculators
import core.detection as detection
import core.detection_tables as dt


def _sun10(**kw):
    return detection.compute_detection_completeness(
        app_mag=4.83, distance_pc=10.0, sp_type="G2V", **kw)


def _g2v(app_mag, **kw):
    return detection.compute_detection_completeness(
        app_mag=app_mag, distance_pc=10.0, sp_type="G2V", **kw)


def _method(res, name):
    return [m for m in res["methods"] if m["method"] == name][0]


def _at(curve, sma, key):
    return [p for p in curve if p["sma_au"] == sma][0][key]


class RvFloorTest(unittest.TestCase):
    def test_earth_below_hot_jupiter_above(self):
        rv = _method(_sun10(methods=["rv"], sma_grid=[0.05, 1.0]), "rv")["detectable_vs_sma"]
        self.assertGreater(_at(rv, 1.0, "min_mass_earth"), 1.0)     # Earth (1 M⊕) below the floor
        self.assertLess(_at(rv, 0.05, "min_mass_earth"), 317.8)     # hot Jupiter above the floor

    def test_rv_increases_with_sma(self):
        # SMAs within the 10 yr default baseline (3 AU → ~5.5 yr) so all points return a value.
        rv = _method(_sun10(methods=["rv"], sma_grid=[0.1, 1.0, 3.0]), "rv")["detectable_vs_sma"]
        vals = [p["min_mass_earth"] for p in rv]
        self.assertEqual(vals, sorted(vals))                        # monotone increasing

    def test_rv_baseline_gate(self):
        rv = _method(_sun10(methods=["rv"], sma_grid=[1.0, 50.0]), "rv")["detectable_vs_sma"]
        self.assertIsNotNone(_at(rv, 1.0, "min_mass_earth"))
        self.assertIsNone(_at(rv, 50.0, "min_mass_earth"))          # P >> 10 yr baseline

    def test_rv_baseline_override_gates_closer(self):
        rv = _method(_sun10(methods=["rv"], sma_grid=[3.0], rv_baseline_yr=1.0), "rv")["detectable_vs_sma"]
        self.assertIsNone(rv[0]["min_mass_earth"])                  # 3 AU ≈ 5.5 yr > 1 yr override


class MonotonicityTest(unittest.TestCase):
    def test_astrometry_decreases_then_baseline_gates(self):
        astro = _method(_sun10(methods=["astrometry"], sma_grid=[0.1, 1.0, 100.0]),
                        "astrometry")["detectable_vs_sma"]
        self.assertLess(_at(astro, 1.0, "min_mass_earth"), _at(astro, 0.1, "min_mass_earth"))
        self.assertIsNone(_at(astro, 100.0, "min_mass_earth"))      # P > baseline → not sampled

    def test_imaging_inner_iwa_then_resolvable(self):
        img = _method(_sun10(methods=["imaging"], sma_grid=[0.05, 20.0]), "imaging")["detectable_vs_sma"]
        self.assertIsNone(_at(img, 0.05, "min_radius_earth"))       # sep inside inner working angle
        self.assertIsNotNone(_at(img, 20.0, "min_radius_earth"))

    def test_transit_radius_sma_independent(self):
        tr = _method(_sun10(methods=["transit"], sma_grid=[0.1, 1.0, 10.0]),
                     "transit")["detectable_vs_sma"]
        vals = [p["min_radius_earth"] for p in tr]
        self.assertAlmostEqual(vals[0], vals[-1], places=9)


class TransitApplicabilityTest(unittest.TestCase):
    def test_not_applicable_by_default(self):
        tr = _method(_sun10(methods=["transit"]), "transit")
        self.assertFalse(tr["applicable"])
        self.assertIn("note", tr)

    def test_applicable_with_target_flag(self):
        tr = _method(_sun10(methods=["transit"], transit_target=True), "transit")
        self.assertTrue(tr["applicable"])

    def test_applicable_with_precision_override(self):
        tr = _method(_sun10(methods=["transit"], transit_precision_ppm=100.0), "transit")
        self.assertTrue(tr["applicable"])
        self.assertEqual(tr["floor_source"], "per-star override")


class ResolveAndValidationTest(unittest.TestCase):
    def test_sp_type_resolves_mass_radius(self):
        res = _sun10(methods=["rv"])
        self.assertAlmostEqual(res["star_mass_solar"], 0.95)
        self.assertAlmostEqual(res["star_radius_solar"], 0.95)

    def test_explicit_mr_overrides(self):
        res = detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, star_mass_solar=1.0, star_radius_solar=1.0, methods=["rv"])
        self.assertEqual(res["star_mass_solar"], 1.0)

    def test_out_of_domain_flag(self):
        res = detection.compute_detection_completeness(app_mag=25, distance_pc=10, sp_type="M5V")
        self.assertTrue(res["assumptions"]["out_of_domain"])
        self.assertIsNotNone(res["assumptions"]["domain_note"])

    def test_assumptions_carry_reference(self):
        a = _sun10()["assumptions"]
        self.assertIn("reference_version", a)
        self.assertIn("confidence", a)

    def test_methods_subset(self):
        res = _sun10(methods=["rv", "imaging"])
        self.assertEqual({m["method"] for m in res["methods"]}, {"rv", "imaging"})

    def test_errors(self):
        self.assertIn("error", detection.compute_detection_completeness(app_mag=5, distance_pc=0, sp_type="G2V"))
        self.assertIn("error", detection.compute_detection_completeness(app_mag=None, distance_pc=10, sp_type="G2V"))
        self.assertIn("error", detection.compute_detection_completeness(app_mag=5, distance_pc=10))
        self.assertIn("error", detection.compute_detection_completeness(app_mag=5, distance_pc=10, sp_type="G2V", albedo=1.5))
        self.assertIn("error", detection.compute_detection_completeness(app_mag=5, distance_pc=10, sp_type="G2V", methods=["xyz"]))

    def test_non_positive_star_override_is_curated_error(self):
        # A ≤0 mass/radius override must be a curated error, not a KeyError from the forward calc.
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, star_mass_solar=0, star_radius_solar=1))
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, star_mass_solar=1, star_radius_solar=-1))

    def test_non_positive_baseline_is_error(self):
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, sp_type="G2V", rv_baseline_yr=0))
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, sp_type="G2V", astrom_baseline_yr=-5))


class RvJitterBySptypeTest(unittest.TestCase):
    # WB 3a v1.1.0 (MSG 050): effective RV floor = max(precision, sp_type-keyed jitter).
    # O/B/A=5, F=3, G/K/M=1.5 (Kraft-break bump); flat 1.5 when no host letter.
    def test_jitter_floor_by_letter(self):
        # _rv_jitter_floor now returns (floor, advisory); the MS Kraft-break floors are unchanged and
        # never advisory (no evolved host, no activity signal).
        rv_def = dt._DETECTION_DEFAULTS["methods"]["rv"]
        row = rv_def["by_mag"][0]
        self.assertEqual(detection._rv_jitter_floor(rv_def, row, "A0V"), (5.0, False))
        self.assertEqual(detection._rv_jitter_floor(rv_def, row, "F5V"), (3.0, False))
        self.assertEqual(detection._rv_jitter_floor(rv_def, row, "G2V"), (1.5, False))
        self.assertEqual(detection._rv_jitter_floor(rv_def, row, "M4V"), (1.5, False))
        self.assertEqual(detection._rv_jitter_floor(rv_def, row, None), (1.5, False))   # flat fallback

    def test_a_star_effective_floor_is_five(self):
        # Bright A star: photon precision 0.3 → effective floor = max(0.3, 5.0) = 5.0 m/s.
        rv = _method(detection.compute_detection_completeness(
            app_mag=4.83, distance_pc=10, sp_type="A0V", methods=["rv"], sma_grid=[1.0]),
            "rv")["detectable_vs_sma"]
        k = calculators.compute_rv_semi_amplitude(1.0, 1.6, sma_au=1.0)["k_ms"]   # A0V → 1.6 M☉
        self.assertAlmostEqual(rv[0]["min_mass_earth"], 5.0 / k, places=9)

    def test_a_star_floor_exceeds_g_star_jitter(self):
        # Same mag/SMA: an A host's larger jitter → a coarser (larger m/s) RV floor than a G host's.
        a = _method(detection.compute_detection_completeness(
            app_mag=4.83, distance_pc=10, sp_type="A0V", methods=["rv"], sma_grid=[1.0]), "rv")
        self.assertIn("jitter 5.0", a["floor_source"])


class TransitTessDefaultTest(unittest.TestCase):
    # Q1: transit fallback default is TESS-only, NOT Kepler (25/34 ppm off-field would overstate).
    def test_default_floor_is_tess(self):
        for mag, ppm in [(4.83, "68"), (8.5, "149"), (11.0, "440")]:
            t = _method(detection.compute_detection_completeness(
                app_mag=mag, distance_pc=20, sp_type="K0V", methods=["transit"],
                transit_target=True, sma_grid=[1.0]), "transit")
            self.assertIn("TESS", t["floor_source"])
            self.assertIn(ppm, t["floor_source"])
            self.assertNotIn("Kepler", t["floor_source"])


class NoiseModelFaintTailTest(unittest.TestCase):
    # Q2 (B): prefer the analytic noise model over the binned scalar at the faint tail.
    def test_tess_noise_model_anchor(self):
        nm = dt._DETECTION_DEFAULTS["methods"]["transit"]["noise_model"]
        self.assertAlmostEqual(detection._tess_sigma_1hr_ppm(10.0, nm), 240.5, places=1)

    def test_gaia_noise_model_anchors(self):
        nm = dt._DETECTION_DEFAULTS["methods"]["astrometry"]["noise_model"]
        self.assertAlmostEqual(detection._gaia_sigma_pi_uas(20.0, nm), 461.7, places=1)
        self.assertAlmostEqual(detection._gaia_sigma_pi_uas(18.0, nm), 106.6, places=1)

    def test_transit_switches_to_model_above_12(self):
        scalar = _method(detection.compute_detection_completeness(
            app_mag=12.0, distance_pc=20, sp_type="K0V", methods=["transit"],
            transit_target=True, sma_grid=[1.0]), "transit")
        model = _method(detection.compute_detection_completeness(
            app_mag=12.5, distance_pc=20, sp_type="K0V", methods=["transit"],
            transit_target=True, sma_grid=[1.0]), "transit")
        self.assertNotIn("noise-model", scalar["floor_source"])   # 12.0 in the 10-12 scalar bin
        self.assertIn("noise-model", model["floor_source"])       # 12.5 → TESS σ(Tmag)

    def test_astrometry_switches_to_model_above_15(self):
        scalar = _method(_g2v(15.0, methods=["astrometry"], sma_grid=[1.0]), "astrometry")
        model = _method(_g2v(18.0, methods=["astrometry"], sma_grid=[1.0]), "astrometry")
        self.assertNotIn("noise-model", scalar["floor_source"])
        self.assertIn("noise-model", model["floor_source"])

    def test_model_is_less_optimistic_than_old_scalar_near_g20(self):
        # The 200 µas >15 scalar over-stated detection ~4× near G20; the model (462 µas) is coarser,
        # so min-detectable mass is LARGER (a wider undetected-planet envelope — the safe direction).
        astro = _method(_g2v(20.0, methods=["astrometry"], sma_grid=[1.0]),
                        "astrometry")["detectable_vs_sma"]
        floor_used = float(astro[0].get("min_mass_earth"))
        # reconstruct with the raw 200 µas scalar → a smaller (more optimistic) min mass
        ref200 = _method(detection.compute_detection_completeness(
            app_mag=20.0, distance_pc=10, sp_type="G2V", methods=["astrometry"],
            astrom_precision_uas=200.0, sma_grid=[1.0]), "astrometry")["detectable_vs_sma"][0]["min_mass_earth"]
        self.assertGreater(floor_used, ref200)


class ImagingCaveatTest(unittest.TestCase):
    def test_band_and_mechanism_caveat_surfaced(self):
        im = _method(_sun10(methods=["imaging"], sma_grid=[20.0]), "imaging")
        self.assertEqual(im["contrast_band"], "H")
        self.assertIn("self-luminous", im["mechanism_caveat"].lower())
        self.assertIn("NOT reflected", im["mechanism_caveat"])


class NonMsHostGuardTest(unittest.TestCase):
    # CR-6-AMEND (WB MSG 053): a non-MS host must flag (out_of_domain + host_class) and NOT fake
    # MS mass/radius/jitter by scanning to the first OBAFGKM letter.
    def _rv(self, res):
        return [m for m in res["methods"] if m["method"] == "rv"][0]

    def test_cell1_wd_no_mr_flags_and_does_not_fake(self):
        res = detection.compute_detection_completeness(app_mag=12, distance_pc=15, sp_type="DA2")
        self.assertEqual(res["host_class"], "white_dwarf")
        self.assertTrue(res["assumptions"]["out_of_domain"])
        self.assertIsNone(res["star_mass_solar"])                  # NOT faked to 1.6 M☉
        rv = self._rv(res)
        self.assertFalse(rv["applicable"])                         # not computed
        self.assertEqual(rv["detectable_vs_sma"], [])
        self.assertIn("non-main-sequence", rv["note"])

    def test_cell2_wd_with_real_mr_computes_flagged_flat_jitter(self):
        res = detection.compute_detection_completeness(
            app_mag=12, distance_pc=15, sp_type="DA2", star_mass_solar=0.6, star_radius_solar=0.013)
        self.assertEqual(res["host_class"], "white_dwarf")
        self.assertTrue(res["assumptions"]["out_of_domain"])
        self.assertEqual(res["star_mass_solar"], 0.6)              # real WD M/R, not faked
        self.assertIsNotNone(res["assumptions"]["host_class_note"])
        rv = self._rv(res)
        self.assertTrue(rv["applicable"])
        self.assertIn("jitter 1.5", rv["floor_source"])            # FLAT jitter, not the A-star map 5.0

    def test_cell3_giant(self):
        res = detection.compute_detection_completeness(app_mag=6, distance_pc=100, sp_type="K0III")
        self.assertEqual(res["host_class"], "giant")
        self.assertTrue(res["assumptions"]["out_of_domain"])

    def test_cell4_g2v_regression_ms(self):
        res = _sun10(methods=["rv"])
        self.assertIsNone(res["host_class"])
        self.assertFalse(res["assumptions"]["out_of_domain"])      # MS dwarf unchanged

    def test_cell5_brown_dwarf(self):
        res = detection.compute_detection_completeness(app_mag=14, distance_pc=8, sp_type="L5")
        self.assertEqual(res["host_class"], "brown_dwarf")
        self.assertTrue(res["assumptions"]["out_of_domain"])

    def test_host_class_classifier(self):
        cases = {"DA2": "white_dwarf", "DZ7.5": "white_dwarf", "sdB": "subdwarf", "sdO": "subdwarf",
                 "K0III": "giant", "M2Iab": "giant", "A0IV": "subgiant", "L5": "brown_dwarf",
                 "T6": "brown_dwarf", "Y2": "brown_dwarf",
                 "G2V": None, "K5V": None, "B3V": None, "dM6": None, "sdM3.0": None, "M5V": None}
        for sp, exp in cases.items():
            self.assertEqual(detection._host_class(sp), exp, sp)

    def test_non_ms_partial_mr_is_error(self):
        # a non-MS host needs BOTH explicit M/R (or neither) — a lone mass is a curated error
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=12, distance_pc=15, sp_type="DA2", star_mass_solar=0.6))


class CompanionCr1JitterBumpTest(unittest.TestCase):
    """Companion CR #1 (Phase-5 D3): STRUCTURE + advisory flag for the evolved / active-young jitter
    floors. Asserts the structure and the advisory flag, NOT a specific placeholder magnitude."""
    def _rv(self, res):
        return [m for m in res["methods"] if m["method"] == "rv"][0]

    def test_bumps_table_structure_present(self):
        rv_def = dt._DETECTION_DEFAULTS["methods"]["rv"]
        bumps = rv_def["jitter_bumps"]
        self.assertTrue(bumps["advisory"])
        self.assertIn("subgiant_m_s", bumps["evolved"])
        self.assertIn("giant_m_s", bumps["evolved"])
        self.assertIn("active_young_cool_dwarf_m_s", bumps)

    def test_evolved_host_bump_is_advisory_and_larger(self):
        # A giant with explicit M/R: the flat 1.5 floor is bumped upward, flagged advisory.
        rv_def = dt._DETECTION_DEFAULTS["methods"]["rv"]
        row = rv_def["by_mag"][0]
        flat, adv0 = detection._rv_jitter_floor(rv_def, row, None)
        bumped, adv1 = detection._rv_jitter_floor(rv_def, row, None, host_class="giant")
        self.assertFalse(adv0)
        self.assertTrue(adv1)
        self.assertGreater(bumped, flat)

    def test_giant_with_mr_surfaces_advisory_flag(self):
        res = detection.compute_detection_completeness(
            app_mag=6, distance_pc=100, sp_type="K0III", star_mass_solar=1.1, star_radius_solar=10.0,
            methods=["rv"], sma_grid=[1.0])
        rv = self._rv(res)
        self.assertTrue(rv.get("jitter_advisory"))
        self.assertIn("advisory", rv["jitter_note"].lower())

    def test_active_young_cool_dwarf_bump_only_with_signal(self):
        # Default (no activity) MS cool dwarf → unchanged, no advisory.
        quiet = self._rv(detection.compute_detection_completeness(
            app_mag=8, distance_pc=10, sp_type="K5V", methods=["rv"], sma_grid=[1.0]))
        self.assertNotIn("jitter_advisory", quiet)
        # With an activity signal → advisory bump.
        active = self._rv(detection.compute_detection_completeness(
            app_mag=8, distance_pc=10, sp_type="K5V", methods=["rv"], sma_grid=[1.0], activity="active"))
        self.assertTrue(active.get("jitter_advisory"))

    def test_ms_default_is_regression_stable(self):
        # A normal MS star with no activity signal must be byte-identical to pre-CR#1 (no bump keys).
        rv = self._rv(_sun10(methods=["rv"], sma_grid=[1.0]))
        self.assertNotIn("jitter_advisory", rv)
        self.assertNotIn("jitter_note", rv)

    def test_activity_validation(self):
        self.assertIn("error", detection.compute_detection_completeness(
            app_mag=8, distance_pc=10, sp_type="K5V", activity="sizzling"))

    def test_bump_that_does_not_raise_the_floor_is_not_advisory(self):
        # Gate-B #3: advisory must be True ONLY when the placeholder actually raises the floor.
        row = {"jitter_floor_m_s": 20.0}                       # base already above a tiny bump
        rv_def = {"jitter_floor_by_sptype_m_s": {}, "jitter_bumps": {"evolved": {"giant_m_s": 5.0}}}
        floor, advisory = detection._rv_jitter_floor(rv_def, row, None, host_class="giant")
        self.assertEqual(floor, 20.0)
        self.assertFalse(advisory)


class Cr104MassProvenanceTest(unittest.TestCase):
    """CR-10.4: star_mass_provenance in the core output — sp_type_estimate / manual / archive / None."""

    def test_sp_type_estimate(self):
        self.assertEqual(_sun10(methods=["rv"])["star_mass_provenance"], "sp_type_estimate")

    def test_explicit_mass_defaults_manual(self):
        res = detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, star_mass_solar=1.0, star_radius_solar=1.0, methods=["rv"])
        self.assertEqual(res["star_mass_provenance"], "manual")

    def test_archive_provenance_passed_through(self):
        res = detection.compute_detection_completeness(
            app_mag=5, distance_pc=10, sp_type="G2V", star_mass_solar=0.86,
            star_mass_provenance="archive", methods=["rv"])
        self.assertAlmostEqual(res["star_mass_solar"], 0.86)
        self.assertEqual(res["star_mass_provenance"], "archive")

    def test_non_ms_with_mr_reports_provenance(self):
        res = detection.compute_detection_completeness(
            app_mag=12, distance_pc=15, sp_type="DA2", star_mass_solar=0.6, star_radius_solar=0.013,
            star_mass_provenance="archive", methods=["rv"])
        self.assertEqual(res["star_mass_provenance"], "archive")

    def test_non_ms_no_mr_provenance_none(self):
        res = detection.compute_detection_completeness(app_mag=12, distance_pc=15, sp_type="DA2")
        self.assertIsNone(res["star_mass_solar"])
        self.assertIsNone(res["star_mass_provenance"])


class ReferenceVersionTest(unittest.TestCase):
    def test_v1_1_0_and_domain(self):
        a = _sun10()["assumptions"]
        self.assertEqual(a["reference_version"], "3a-v1.1.0-2026-08-15")
        self.assertEqual(a["confidence"], "extrapolation")
        self.assertEqual(a["mag_domain"], [3.0, 20.7])


if __name__ == "__main__":
    unittest.main()
