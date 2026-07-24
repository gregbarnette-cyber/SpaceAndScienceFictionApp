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


class TestCensusDedup(unittest.TestCase):
    """The census counts SYSTEMS, not catalogue rows. Two ways it used to double-count:

      • INTRA-SOURCE — one Gaia `source_id` carrying several NSS orbit solutions;
      • CROSS-ROUTE — the same star reached via both NSS and SB9, missed because the old
        positional box was 3″ while SB9's coarse coordinates put real twins 6–9″ apart.

    All four systems below are real, and each pins a DIFFERENT rule. The two that must be
    collapsed and the two that must NOT be are equally load-bearing: a rule that fixes the
    first pair by distrusting low-grade or short-period rows would break the second pair.
    """

    # FK Aqr / GJ 867 A — one source, two solutions; the low-grade targeted search is
    # spurious and the SB2C reproduces the primary paper (Tsvetkova 2024) to 10 sig figs.
    FK_AQR = "2400808142038361088"
    # BY Dra — same shape: grade-17 targeted search vs a grade-141 SB2 matching the paper.
    BY_DRA = "2145277550935525760"

    def _nss(self, source_id, period, grade, stype, ra=10.0, dec=20.0):
        return {"source": "gaia-nss:two_body_orbit", "source_id": source_id,
                "solution_type": stype, "name": None, "ra": ra, "dec": dec,
                "parallax_mas": 100.0, "distance_ly": 32.6, "period_d": period,
                "eccentricity": 0.1, "grade": grade,
                "companion": {"class": "stellar", "m2_solar": 0.3}, "verification": "x"}

    def _sb9(self, name, period, gaia_id=None, ra=10.0, dec=20.0, seq=1):
        return {"source": "sb9", "source_id": None, "seq": seq, "name": name,
                "gaia_source_id": gaia_id, "ra": ra, "dec": dec, "parallax_mas": 100.0,
                "distance_ly": 32.6, "period_d": period, "eccentricity": 0.1, "grade": 3,
                "primary_ref": "1965ApJ...141..649H",
                "companion": {"class": "stellar"}, "verification": "y"}

    # ── intra-source collapse ────────────────────────────────────────────────

    def test_multiple_nss_solutions_collapse_to_the_highest_grade(self):
        rows = binary._collapse_nss_solutions([
            self._nss(self.FK_AQR, 7.980586, 42.96, "OrbitalTargetedSearch"),
            self._nss(self.FK_AQR, 4.083196151, 205.48, "SB2C"),
        ])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["period_d"], 4.083196151)   # the primary-paper value
        self.assertEqual(rows[0]["n_orbit_solutions"], 2)
        self.assertFalse(rows[0]["sole_solution"])

    def test_the_discarded_solution_is_surfaced_not_dropped(self):
        rows = binary._collapse_nss_solutions([
            self._nss(self.BY_DRA, 32.2660, 17.42, "OrbitalTargetedSearch"),
            self._nss(self.BY_DRA, 5.9773, 140.52, "SB2"),
        ])
        other = rows[0]["other_solutions"]
        self.assertEqual(len(other), 1)
        self.assertAlmostEqual(other[0]["period_d"], 32.2660)
        self.assertEqual(other[0]["solution_type"], "OrbitalTargetedSearch")
        self.assertAlmostEqual(other[0]["grade"], 17.42)

    def test_both_regression_cases_resolve_mechanically(self):
        # No per-system special-casing: the same grade rule fixes both.
        for sid, spurious, correct in ((self.FK_AQR, 7.980586, 4.083196151),
                                       (self.BY_DRA, 32.2660, 5.9773)):
            rows = binary._collapse_nss_solutions([
                self._nss(sid, spurious, 20.0, "OrbitalTargetedSearch"),
                self._nss(sid, correct, 200.0, "SB2"),
            ])
            self.assertAlmostEqual(rows[0]["period_d"], correct)

    def test_a_sole_solution_is_flagged_but_not_judged(self):
        # G 184-19: sole SB2 at grade 126 — trustworthy. Wolf 227: sole targeted search at
        # grade 38 — weak. SAME sole_solution flag; the caller tells them apart by type +
        # grade. No "distrust low grades" rule exists, and none should: the NSS grades run
        # 2.9-270.7 with a median of 44.4, so any cutoff would flag much of the census.
        strong = binary._collapse_nss_solutions(
            [self._nss("g18419", 2.535, 125.86, "SB2")])[0]
        weak = binary._collapse_nss_solutions(
            [self._nss("wolf227", 10.59, 37.89, "OrbitalTargetedSearch")])[0]
        for r in (strong, weak):
            self.assertTrue(r["sole_solution"])
            self.assertEqual(r["n_orbit_solutions"], 1)
            self.assertEqual(r["other_solutions"], [])
        self.assertEqual(strong["solution_type"], "SB2")
        self.assertEqual(weak["solution_type"], "OrbitalTargetedSearch")

    # ── cross-route dedup ────────────────────────────────────────────────────

    def test_identity_match_single_counts_across_routes(self):
        nss = [self._nss(self.FK_AQR, 7.980586, 42.96, "OrbitalTargetedSearch")]
        sb9 = [self._sb9("HIP 111802", 4.0832, gaia_id=self.FK_AQR)]
        out = binary._dedup_census(nss, sb9)
        self.assertEqual(len(out), 1)
        self.assertIn("sb9", out[0]["also_in"])

    def test_period_disagreement_is_surfaced_never_resolved_silently(self):
        # This disagreement is what identified BOTH spurious Gaia solutions; hiding it
        # behind a silent winner would have hidden the finding.
        nss = [self._nss(self.BY_DRA, 32.2660, 17.42, "OrbitalTargetedSearch")]
        out = binary._dedup_census(nss, [self._sb9("BY Dra", 5.9751, gaia_id=self.BY_DRA)])
        pd = out[0]["period_disagreement"]
        self.assertAlmostEqual(pd["nss_period_d"], 32.2660)
        self.assertAlmostEqual(pd["sb9_period_d"], 5.9751)
        self.assertEqual(pd["nss_solution_type"], "OrbitalTargetedSearch")
        self.assertAlmostEqual(pd["nss_grade"], 17.42)

    def test_agreeing_periods_raise_no_disagreement(self):
        nss = [self._nss("s1", 12.9773, 50.0, "SB1")]
        out = binary._dedup_census(nss, [self._sb9("HIP 80686", 12.9762, gaia_id="s1")])
        self.assertNotIn("period_disagreement", out[0])

    def test_positional_proximity_flags_but_never_merges(self):
        # 7.2″ apart — inside the widened box — but with no resolved identity. Castor proves
        # proximity alone cannot justify a merge, so this stays in the census, flagged.
        nss = [self._nss("s9", 7.98, 40.0, "OrbitalTargetedSearch", ra=339.69202, dec=-20.62148)]
        sb9 = [self._sb9("HIP 111802", 4.0832, gaia_id=None, ra=339.68991, dec=-20.62113)]
        out = binary._dedup_census(nss, sb9)
        self.assertEqual(len(out), 2, "a positional match must NOT collapse a row")
        flagged = [r for r in out if r.get("possible_duplicate_of")]
        self.assertEqual(len(flagged), 1)
        self.assertAlmostEqual(flagged[0]["possible_duplicate_of"]["separation_arcsec"], 7.2,
                               delta=0.3)

    def test_castor_style_two_real_pairs_at_one_position_both_survive(self):
        # HIP 36850 carries two genuine close pairs (Aa/Ab 9.2128 d, Ba/Bb 2.9283 d).
        # A widened positional box that merged them would UNDER-count.
        sb9 = [self._sb9("HIP 36850", 9.2128, seq=461),
               self._sb9("HIP 36850", 2.9283, seq=462)]
        out = binary._dedup_census([], sb9)
        self.assertEqual(len(out), 2)

    def test_two_sb9_orbits_on_one_gaia_source_keep_both(self):
        # The same trap via the identity path: a second SB9 orbit on one source is usually a
        # second real pair, so it is kept and flagged rather than absorbed.
        nss = [self._nss("shared", 9.2128, 60.0, "SB1")]
        sb9 = [self._sb9("HIP 36850", 9.2128, gaia_id="shared", seq=461),
               self._sb9("HIP 36850", 2.9283, gaia_id="shared", seq=462)]
        out = binary._dedup_census(nss, sb9)
        self.assertEqual(len(out), 2)
        kept = [r for r in out if r["source"] == "sb9"][0]
        self.assertIsNotNone(kept.get("possible_duplicate_of"))

    def test_rows_without_coordinates_are_never_matched(self):
        nss = [self._nss("s1", 10.0, 50.0, "SB1", ra=None, dec=None)]
        sb9 = [self._sb9("X", 10.0, gaia_id=None, ra=None, dec=None)]
        self.assertEqual(len(binary._dedup_census(nss, sb9)), 2)

    # ── the accounting block ─────────────────────────────────────────────────

    @mock.patch("core.binary._census_sb9")
    @mock.patch("core.binary._census_nss")
    def test_dedup_accounting_is_reported(self, m_nss, m_sb9):
        m_nss.return_value = ([dict(self._nss(self.BY_DRA, 5.9773, 140.52, "SB2"),
                                    n_orbit_solutions=2, sole_solution=False,
                                    other_solutions=[{"period_d": 32.266, "grade": 17.42,
                                                      "solution_type": "OrbitalTargetedSearch",
                                                      "eccentricity": 0.1}])], None)
        m_sb9.return_value = ([self._sb9("BY Dra", 5.9751, gaia_id=self.BY_DRA)], None)
        r = binary.close_binary_census(65, 365)
        self.assertEqual(r["count"], 1)                       # one SYSTEM, two catalogue rows
        self.assertEqual(r["dedup"]["cross_route_single_counted"], 1)
        self.assertEqual(r["dedup"]["multi_solution_sources"], 1)
        self.assertEqual(r["dedup"]["possible_duplicates"], 0)


if __name__ == "__main__":
    unittest.main()
