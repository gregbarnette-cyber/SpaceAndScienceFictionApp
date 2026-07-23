"""tests/test_binary.py — offline coverage for the Phase AM companion-mass classifier
(core/binary.py). Pure math — no network, no Qt, no DB. Always runs.

The classifier is the load-bearing §3.3 piece (the planet filter). These tests lock the
Thiele-Innes → a₀ → mass-function → cubic math and the star/BD/planet thresholds with
synthetic inputs whose answers are known in closed form, so a bug in the a₀→mass path cannot
pass regardless of live-catalog availability. The live method-correctness anchor (T3, HD 110833
→ 0.16 M☉ vs Gaia binary_masses) lives in tests/test_catalog_live.py.
"""

import unittest
from unittest import mock

from core import binary


class SolveMassFunctionTest(unittest.TestCase):
    def test_roundtrip(self):
        # Forward: f = M₂³/(M₁+M₂)² for M₁=1, M₂=0.5 → 0.125/2.25.
        f = 0.5 ** 3 / (1.0 + 0.5) ** 2
        self.assertAlmostEqual(f, 0.0555556, places=6)
        m2 = binary._solve_mass_function(f, 1.0)
        self.assertAlmostEqual(m2, 0.5, places=4)

    def test_nonpositive_returns_zero(self):
        self.assertEqual(binary._solve_mass_function(0.0, 1.0), 0.0)
        self.assertEqual(binary._solve_mass_function(-1.0, 1.0), 0.0)
        self.assertEqual(binary._solve_mass_function(0.1, 0.0), 0.0)


class ThieleInnesTest(unittest.TestCase):
    def test_a0_is_max_axis_when_off_diagonal_zero(self):
        # With B=F=0, a₀ reduces to max(|A|,|G|) in closed form — the clean offline anchor.
        r = binary.companion_mass_from_thiele_innes(
            a_ti=88.5, b_ti=0.0, f_ti=0.0, g_ti=0.0,
            parallax_mas=50.0, period_yr=10.0, m1_solar=1.0)
        self.assertAlmostEqual(r["a0_mas"], 88.5, places=3)
        self.assertAlmostEqual(r["a1_au"], 88.5 / 50.0, places=6)   # 1.77 AU
        self.assertAlmostEqual(r["m2_solar"], 0.5, delta=0.01)      # → ~0.5 M☉
        self.assertEqual(r["method"], "astrom")
        self.assertAlmostEqual(r["m2_mjup"], r["m2_solar"] * binary._MJUP_PER_MSUN, places=6)

    def test_a0_takes_larger_of_a_or_g(self):
        r = binary.companion_mass_from_thiele_innes(
            a_ti=0.0, b_ti=0.0, f_ti=0.0, g_ti=88.5,
            parallax_mas=50.0, period_yr=10.0, m1_solar=1.0)
        self.assertAlmostEqual(r["a0_mas"], 88.5, places=3)

    def test_invalid_inputs_raise(self):
        for kw in ({"parallax_mas": 0.0}, {"parallax_mas": -1.0},
                   {"period_yr": 0.0}, {"m1_solar": 0.0}):
            base = dict(a_ti=10.0, b_ti=0.0, f_ti=0.0, g_ti=0.0,
                        parallax_mas=50.0, period_yr=10.0, m1_solar=1.0)
            base.update(kw)
            with self.assertRaises(ValueError):
                binary.companion_mass_from_thiele_innes(**base)


class Sb1Test(unittest.TestCase):
    def test_mass_function_formula(self):
        # f(m) = 1.0361e-7 · K1³ · P · (1−e²)^1.5 ; K1=10, P=100, e=0 → 0.010361.
        r = binary.companion_mass_from_sb1(k1_kms=10.0, period_d=100.0, ecc=0.0, m1_solar=0.6)
        self.assertAlmostEqual(r["mass_function"], 0.010361, places=6)
        self.assertGreater(r["m2_solar"], 0.0)
        self.assertEqual(r["method"], "spec-min")
        self.assertIn("lower bound", r["caveat"])

    def test_eccentricity_reduces_mass_function(self):
        f0 = binary.companion_mass_from_sb1(10.0, 100.0, 0.0, 0.6)["mass_function"]
        fe = binary.companion_mass_from_sb1(10.0, 100.0, 0.5, 0.6)["mass_function"]
        self.assertLess(fe, f0)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            binary.companion_mass_from_sb1(0.0, 100.0, 0.0, 0.6)
        with self.assertRaises(ValueError):
            binary.companion_mass_from_sb1(10.0, 100.0, 1.0, 0.6)   # e ≥ 1
        with self.assertRaises(ValueError):
            binary.companion_mass_from_sb1(10.0, -1.0, 0.0, 0.6)


class ClassifyTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(binary.classify_companion(0.5)["class"], "stellar")
        self.assertEqual(binary.classify_companion(0.08)["class"], "stellar")
        self.assertEqual(binary.classify_companion(0.075)["class"], "brown-dwarf")   # not > 0.075
        self.assertEqual(binary.classify_companion(0.03)["class"], "brown-dwarf")
        self.assertEqual(binary.classify_companion(0.013)["class"], "brown-dwarf")
        self.assertEqual(binary.classify_companion(0.0129)["class"], "planet")
        self.assertEqual(binary.classify_companion(0.003)["class"], "planet")
        self.assertEqual(binary.classify_companion(None)["class"], "unknown")

    def test_low_significance_flag(self):
        self.assertTrue(binary.classify_companion(0.5, a0_mas=0.5)["low_significance"])
        self.assertTrue(binary.classify_companion(0.5, a0_mas=1.0)["low_significance"])
        self.assertFalse(binary.classify_companion(0.5, a0_mas=5.0)["low_significance"])
        self.assertFalse(binary.classify_companion(0.5, a0_mas=None)["low_significance"])


class M1FromSpectralTypeTest(unittest.TestCase):
    def test_known_types(self):
        self.assertAlmostEqual(binary.m1_from_spectral_type("G2V"), 1.02, places=2)
        self.assertAlmostEqual(binary.m1_from_spectral_type("A0V"), 2.18, places=2)
        self.assertAlmostEqual(binary.m1_from_spectral_type("M5V"), 0.16, places=2)
        self.assertAlmostEqual(binary.m1_from_spectral_type("K0V"), 0.88, places=2)

    def test_interpolation_between_anchors(self):
        # G3 sits between G2 (1.02) and G5 (0.93).
        m = binary.m1_from_spectral_type("G3V")
        self.assertTrue(0.93 < m < 1.02)

    def test_unknown_or_degenerate_falls_back_to_default(self):
        self.assertEqual(binary.m1_from_spectral_type("DA1.9"), 1.0)   # white dwarf → default
        self.assertEqual(binary.m1_from_spectral_type(""), 1.0)
        self.assertEqual(binary.m1_from_spectral_type(None), 1.0)
        self.assertEqual(binary.m1_from_spectral_type("T6"), 1.0)      # brown dwarf, non-OBAFGKM


class VerificationTagTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(
            binary.verification_tag("gaia-nss:two_body_orbit", source_id=12345),
            "[V-PRIMARY-Gaia-DR3-NSS source_id=12345]")
        self.assertEqual(
            binary.verification_tag("sb9", grade=4, bibcode="1976ApJS...30..273A"),
            "[V-SECONDARY SB9 gr4 1976ApJS...30..273A]")
        self.assertEqual(
            binary.verification_tag("wds", ref="2001AJ....122.3466M"),
            "[V-SECONDARY WDS/orb6 2001AJ....122.3466M]")


class ApplyBinaryMassesTest(unittest.TestCase):
    """§3.3 Gaia binary_masses cross-check / fill (core/binary._apply_binary_masses), offline."""
    def test_none_bmass_is_passthrough(self):
        comp = {"method": "astrom", "m2_solar": 0.5, "class": "stellar"}
        self.assertEqual(binary._apply_binary_masses(comp, None), comp)

    def test_fill_when_comp_none_and_gaia_m2_present(self):
        bmass = {"m1": 0.8, "m2": 0.17, "fluxratio": 0.01,
                 "combination_method": "AstroSpectroSB1+M1", "m1_ref": "IsocLum"}
        out = binary._apply_binary_masses(None, bmass)
        self.assertEqual(out["method"], "gaia-binary-masses")
        self.assertAlmostEqual(out["m2_solar"], 0.17, places=4)
        self.assertEqual(out["class"], "stellar")
        self.assertEqual(out["binary_masses"]["m2_solar"], 0.17)

    def test_no_fill_when_gaia_m2_null(self):
        # Gaia frequently derives only the primary mass → nothing to fill.
        self.assertIsNone(binary._apply_binary_masses(None, {"m1": 0.8, "m2": None}))

    def test_crosscheck_attaches_agreement_without_mutating(self):
        comp = {"method": "astrom", "m2_solar": 0.156, "class": "stellar"}
        bmass = {"m1": 0.8, "m2": 0.171, "fluxratio": 0.01,
                 "combination_method": "AstroSpectroSB1+M1", "m1_ref": "IsocLum"}
        out = binary._apply_binary_masses(comp, bmass)
        self.assertEqual(out["method"], "astrom")                 # our estimate stays primary
        self.assertAlmostEqual(out["binary_masses"]["m2_solar"], 0.171, places=4)
        self.assertAlmostEqual(out["binary_masses"]["agreement_pct"],
                               abs(0.156 - 0.171) / 0.171 * 100, places=1)
        self.assertNotIn("binary_masses", comp)                   # original not mutated


class CensusIncludeHonestyTest(unittest.TestCase):
    """close-binary-census --include validation + honest coverage (no silent drop), offline (mocked)."""
    def test_unknown_include_errors(self):
        r = binary.close_binary_census(65, 365, include=("nss", "sb9", "bogus"))
        self.assertIn("error", r)
        self.assertIn("bogus", r["error"])

    @mock.patch("core.binary._census_sb9", return_value=([], None))
    @mock.patch("core.binary._census_nss", return_value=([], None))
    def test_requested_wds_reported_not_dropped(self, *_):
        r = binary.close_binary_census(65, 365, include=("nss", "sb9", "wds"))
        cov = r["coverage"]
        self.assertIn("B/wds visual pairs", cov["requested_not_implemented"])
        self.assertNotIn("B/wds visual pairs", cov["catalogs_not_swept"])   # not silently dropped
        self.assertIn("B/cb Ritter & Kolb CVs", cov["catalogs_not_swept"])  # cv not requested → not_swept
        self.assertTrue(any("not yet wired" in n for n in cov["notes"]))

    @mock.patch("core.binary._census_sb9", return_value=([], None))
    @mock.patch("core.binary._census_nss", return_value=([], None))
    def test_default_include_has_empty_requested_not_implemented(self, *_):
        r = binary.close_binary_census(65, 365)                  # default nss,sb9
        self.assertEqual(r["coverage"]["requested_not_implemented"], [])
        self.assertIn("B/wds visual pairs", r["coverage"]["catalogs_not_swept"])


if __name__ == "__main__":
    unittest.main()
