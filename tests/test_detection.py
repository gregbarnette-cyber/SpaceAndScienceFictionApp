# tests/test_detection.py — CR-6 detection-completeness (core, offline).
#
# Pins the Sun@10pc RV floor validation, the PER-METHOD monotonicity (RV/transit harden with SMA;
# astrometry/imaging ease with SMA), the astrometry baseline gate, and the honest transit-N/A path.

import unittest

import core.detection as detection


def _sun10(**kw):
    return detection.compute_detection_completeness(
        app_mag=4.83, distance_pc=10.0, sp_type="G2V", **kw)


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


if __name__ == "__main__":
    unittest.main()
