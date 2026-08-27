# tests/test_cooling_hz.py — Phase U core engine (core/cooling.py + core/cooling_tables.py).
#
# Offline, in-process. Covers the bundled-table integrity (the closure-consistency
# guard on every transcribed row), the (mass, age) interpolation, the three modes
# (snapshot / residence / CHZ), the Kopparapu validity gating, the Roche cross-check,
# the validation matrix, determinism — and the five §Acceptance benchmarks from
# completed_plans/PHASE_U_PLAN.md, anchored against the real Bedard et al. 2020 0.6 M_sun WD track.

import math
import unittest
from unittest import mock

import core.cooling as cooling
import core.cooling_tables as ct
from core.equations import compute_habitable_zone

_TSUN = 5772.0


class TableIntegrityTest(unittest.TestCase):
    def test_closure_consistency(self):
        # Every transcribed row must satisfy L/Lsun = (R/Rsun)^2 (Teff/Tsun)^4 — the
        # strong integrity check that a Teff/L/R triple was copied correctly.
        for mass, rows in ct.get_wd_tracks().items():
            for age, teff, log10_l, radius in rows:
                closure = math.log10((radius ** 2) * (teff / _TSUN) ** 4)
                self.assertAlmostEqual(
                    log10_l, closure, delta=0.01,
                    msg=f"WD {mass} M_sun row (age={age}, Teff={teff}) breaks the closure")

    def test_rows_sorted_and_monotone_cooling(self):
        for mass, rows in ct.get_wd_tracks().items():
            ages = [r[0] for r in rows]
            teffs = [r[1] for r in rows]
            self.assertEqual(ages, sorted(ages), f"{mass}: ages not sorted")
            # Teff strictly decreases as the star cools (age increases)
            self.assertTrue(all(teffs[i] > teffs[i + 1] for i in range(len(teffs) - 1)),
                            f"{mass}: Teff not monotone-decreasing with age")


class InterpolationTest(unittest.TestCase):
    def test_grid_node_reproduced(self):
        # At an exact grid age the interpolator returns that node's Teff/radius, and the
        # closure-derived L matches the stored log10L.
        rows = ct.get_wd_tracks()[0.60]
        for age, teff, log10_l, radius in rows[1:-1]:
            t, lum, r = cooling._interp_track("wd", 0.60, age)
            self.assertAlmostEqual(t, teff, places=3)
            self.assertAlmostEqual(r, radius, places=5)
            self.assertAlmostEqual(math.log10(lum), log10_l, delta=0.01)

    def test_age_for_teff_inverts(self):
        age = cooling._age_for_teff("wd", 0.60, 5000.0)
        t, _, _ = cooling._interp_track("wd", 0.60, age)
        self.assertAlmostEqual(t, 5000.0, delta=1.0)

    def test_offgrid_mass_raises(self):
        with self.assertRaises(cooling._OffGrid):
            cooling._interp_track("wd", 2.0, 1.0)


class ModeSnapshotTest(unittest.TestCase):
    def test_acceptance_5000k(self):
        # 0.6 M_sun @ 5000 K -> L ~ 9.2e-5 (closure-exact ~8.6e-5), cons HZ ~0.0095-0.017 AU.
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, teff=5000)
        self.assertEqual(r["mode"], "snapshot")
        self.assertTrue(8.0e-5 < r["lum_lsun"] < 9.5e-5, r["lum_lsun"])
        self.assertFalse(r["out_of_range_teff"])
        zi = {z["key"]: z["au"] for z in r["zones"]}
        self.assertTrue(0.0085 < zi["rg"] < 0.0100, zi["rg"])   # conservative inner
        self.assertTrue(0.0155 < zi["mg"] < 0.0180, zi["mg"])   # conservative outer

    def test_edge_keys(self):
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, cooling_age_gyr=6.0)
        zones = compute_habitable_zone(r["teff_k"], r["lum_lsun"])
        keys = {z["key"] for z in r["zones"]}
        self.assertEqual(keys, {z["key"] for z in zones})

    def test_teff_age_parity(self):
        ra = cooling.compute_cooling_hz("wd", mass_solar=0.6, teff=5000)
        rb = cooling.compute_cooling_hz("wd", mass_solar=0.6,
                                        cooling_age_gyr=ra["cooling_age_gyr"])
        self.assertAlmostEqual(ra["teff_k"], rb["teff_k"], delta=1.0)
        self.assertAlmostEqual(ra["lum_lsun"], rb["lum_lsun"], delta=ra["lum_lsun"] * 1e-3)

    def test_hot_young_flagged_not_clamped(self):
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, cooling_age_gyr=0.001)
        self.assertGreater(r["teff_k"], 7200)
        self.assertTrue(r["out_of_range_teff"])
        self.assertTrue(r["any_out_of_range"])
        # flag-don't-clamp: cooling outputs are still returned
        self.assertIn("lum_lsun", r)
        self.assertIn("radius_rsun", r)


class ModeResidenceTest(unittest.TestCase):
    def test_acceptance_001au(self):
        # a=0.01 AU: optimistic edges reproduce Fossati's ~8 Gyr; conservative ~4-6.
        ro = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.01,
                                        hz_edge="optimistic")
        self.assertTrue(ro["ever_habitable"])
        self.assertTrue(6.0 < ro["residence_gyr"] < 9.0, ro["residence_gyr"])
        rc = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.01)
        self.assertTrue(3.5 < rc["residence_gyr"] < 6.0, rc["residence_gyr"])

    def test_crossing_direction(self):
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.012)
        self.assertLess(r["entry_age_gyr"], r["exit_age_gyr"])      # enters younger, exits older
        self.assertGreater(r["entry_teff_k"], r["exit_teff_k"])     # and cooler at exit

    def test_never_habitable_far_and_near(self):
        # a=1.0 AU (HZ only at extrapolated hot epochs) and a=1e-4 (always too cold)
        far = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=1.0)
        near = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=1e-4)
        self.assertFalse(far["ever_habitable"])
        self.assertFalse(near["ever_habitable"])
        self.assertIsNone(far["residence_gyr"])


class ModeChzTest(unittest.TestCase):
    def test_acceptance_band(self):
        # Agol 2011: CHZ ~ 0.005-0.02 AU for a 0.6 M_sun WD at threshold 3 Gyr.
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=3.0)
        self.assertEqual(r["mode"], "chz")
        self.assertLess(r["chz_inner_au"], r["chz_outer_au"])
        self.assertTrue(0.004 < r["chz_inner_au"] < 0.008, r["chz_inner_au"])
        self.assertTrue(0.017 < r["chz_outer_au"] < 0.022, r["chz_outer_au"])
        # the band overlaps Agol's 0.005-0.02
        self.assertLess(r["chz_inner_au"], 0.02)
        self.assertGreater(r["chz_outer_au"], 0.005)

    def test_roche_collision(self):
        # Pkt 7 R2: the cool-WD CHZ inner edge collides with the tidal-disruption radius.
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=3.0,
                                       hz_edge="optimistic")
        self.assertTrue(0.004 < r["roche_limit_au"] < 0.008, r["roche_limit_au"])
        self.assertTrue(r["inner_edge_roche_limited"])

    def test_higher_threshold_narrows_band(self):
        lo = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=1.0)
        hi = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=5.0)
        # CR-12 None-guard: both bands must be non-empty (0.6 M☉ conservative peak residence ~6.98 Gyr
        # > 5.0, so thr-5 is reachable). Fail cleanly if a future shift empties a band rather than a
        # None-None TypeError on the width subtraction.
        for b in (lo, hi):
            self.assertIsNotNone(b["chz_inner_au"])
            self.assertIsNotNone(b["chz_outer_au"])
        lo_w = lo["chz_outer_au"] - lo["chz_inner_au"]
        hi_w = hi["chz_outer_au"] - hi["chz_inner_au"]
        self.assertGreater(lo_w, hi_w)

    def test_chz_reproduces_across_masses(self):
        # Acceptance: CHZ ~ 0.005-0.02 AU holds across 0.4-0.9 M_sun (Agol 2011).
        for m in (0.40, 0.50, 0.70, 0.80, 0.90):
            r = cooling.compute_cooling_hz("wd", mass_solar=m, chz_threshold_gyr=3.0)
            self.assertLess(r["chz_inner_au"], r["chz_outer_au"], m)
            # CR-12: m=0.40's source-faithful CHZ inner edge is ~0.00287 AU (the old grid gave
            # ~0.0053), so the shared floor is lowered 0.003 → 0.0025 (pinned with margin).
            self.assertTrue(0.0025 < r["chz_inner_au"] < 0.012, (m, r["chz_inner_au"]))
            self.assertTrue(0.010 < r["chz_outer_au"] < 0.025, (m, r["chz_outer_au"]))


class BrownDwarfTest(unittest.TestCase):
    """BD track (ATMO 2020). Acceptance: residence tens-hundreds of Myr, rising with mass,
    reaching multi-Gyr only for the most massive BDs (> ~52 M_Jup) — Bolmont 2011/2017."""

    def _peak_residence_gyr(self, mjup):
        best = 0.0
        a = 0.005
        while a < 1.0:
            r = cooling.compute_cooling_hz("bd", mass_mjup=mjup, sma_au=a)
            if r.get("ever_habitable") and r.get("residence_gyr"):
                best = max(best, r["residence_gyr"])
            a *= 1.12
        return best

    def test_residence_rises_with_mass(self):
        masses = [13.6, 31.4, 52.4, 75.4]
        res = [self._peak_residence_gyr(m) for m in masses]
        self.assertEqual(res, sorted(res), res)               # monotonic in mass
        self.assertTrue(0.1 < res[0] < 0.7, res[0])           # lightest: hundreds of Myr
        self.assertTrue(3.0 < res[-1] < 12.0, res[-1])        # heaviest: multi-Gyr (1-10)

    def test_cold_extrapolation_is_flagged(self):
        # a deep-cold BD residence relies on Teff < 2600 K and must say so.
        r = cooling.compute_cooling_hz("bd", mass_mjup=75.4, sma_au=0.02)
        self.assertTrue(r["ever_habitable"])
        self.assertTrue(r["exit_out_of_range"])               # exits below 2600 K
        self.assertTrue(r["any_out_of_range"])

    def test_mass_unit_conversion(self):
        r = cooling.compute_cooling_hz("bd", mass_mjup=52.4, cooling_age_gyr=0.01)
        self.assertAlmostEqual(r["mass_solar"], 52.4 * 9.543e-4, places=5)
        self.assertAlmostEqual(r["mass_mjup"], 52.4, places=3)
        self.assertIn("ATMO 2020", r["model_note"])


class Cr111HighMassWDTest(unittest.TestCase):
    """CR-11.1 — WD cooling grid extended to 1.30 M☉ (+ Chandrasekhar clamp to ~1.38)."""

    def test_grid_extends_to_130(self):
        masses = sorted(ct.get_wd_tracks())
        self.assertEqual(masses[-1], 1.30)
        for m in (1.05, 1.10, 1.15, 1.20, 1.25, 1.30):
            self.assertIn(m, ct.get_wd_tracks())

    def test_sirius_b_returns_without_error(self):
        # 1.018 M☉ / 25970 K. CR-12.2: at fixed Teff a more massive WD is OLDER (t_cool ∝ M^~1.19;
        # the Bedard 2020 sequences are monotone in mass), so Sirius B is slightly older than a clean
        # M=1.00 — NOT shorter. The retired backwards "shorter than 0.151" clause is gone.
        r = cooling.compute_cooling_hz("wd", mass_solar=1.018, teff=25970)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["radius_rsun"], 0.008, delta=0.0006)      # ~0.008 R☉
        self.assertAlmostEqual(r["cooling_age_gyr"], 0.118, delta=0.004)   # ~0.118 Gyr (Bond 2017 ~0.126)
        a100 = cooling.compute_cooling_hz("wd", mass_solar=1.00, teff=25970)["cooling_age_gyr"]
        self.assertGreater(r["cooling_age_gyr"], a100)                     # older than the clean M=1.00

    def test_radius_monotone_decreasing_in_mass(self):
        radii = [cooling.compute_cooling_hz("wd", mass_solar=m, teff=25970)["radius_rsun"]
                 for m in (1.0, 1.05, 1.10, 1.20, 1.30)]
        self.assertEqual(radii, sorted(radii, reverse=True))            # R ∝ M^-1/3

    def test_high_masses_return_without_error(self):
        for m in (1.20, 1.30):
            self.assertNotIn("error", cooling.compute_cooling_hz("wd", mass_solar=m, teff=20000))

    def test_chandrasekhar_clamp_and_refuse(self):
        # 1.30 < M ≤ 1.38 clamps to the 1.30 sequence (no error); above Chandrasekhar refuses.
        self.assertNotIn("error", cooling.compute_cooling_hz("wd", mass_solar=1.35, teff=20000))
        self.assertNotIn("error", cooling.compute_cooling_hz("wd", mass_solar=1.38, teff=20000))
        r = cooling.compute_cooling_hz("wd", mass_solar=1.45, teff=20000)
        self.assertIn("error", r)
        self.assertIn("Chandrasekhar", r["error"])

    def test_young_teff_note_removed(self):
        # CR-12 (D-B) removed the young_teff_cooling_age_inflation advisory BECAUSE the re-derived ages
        # are source-faithful (no massive-WD over-read). Guard both facts: the note string is absent,
        # AND the young/hot case it used to flag now returns a source-faithful age — Sirius B ~0.118,
        # NOT the old inflated ~0.146 (a regression back to the sparse grid would re-inflate it).
        sb = cooling.compute_cooling_hz("wd", mass_solar=1.018, teff=25970)
        self.assertNotIn("young_teff_cooling_age_inflation", " ".join(sb.get("notes", [])))
        self.assertLess(sb["cooling_age_gyr"], 0.13)      # ~0.118 source-faithful, not the old ~0.146
        for m in (1.0, 1.30, 0.6):
            note = " ".join(cooling.compute_cooling_hz("wd", mass_solar=m, teff=25970).get("notes", []))
            self.assertNotIn("young_teff_cooling_age_inflation", note)


class Cr12AgeRederivationTest(unittest.TestCase):
    """CR-12 — the ≤1.00 cooling-age re-derivation guard. Asserts the shipped table's cooling-age
    matches the dense Bedard 2020 source (seq_0XX_thick.txt Age column) across the FULL 0.40-1.30 grid
    at all four audited Teff — the check CR-11.1's radius-only closure identity lacked, which let the
    sparse-age defect pass. Source ages are frozen literals (generated from the archived seq files;
    WB re-derives them independently), so a regression in _WD_COOLING breaks this."""

    # Dense-source cooling ages (Gyr) {Teff_K: {mass_Msun: age}} — every grid mass, all four Teff
    # (25970 = Sirius B's regime; 15000 held the old worst error +86% @1.00; 6000 spans the turnover).
    _SOURCE = {
        25970: {0.40: 0.0085, 0.45: 0.0116, 0.50: 0.0132, 0.55: 0.0142, 0.60: 0.0154, 0.65: 0.0175, 0.70: 0.0218, 0.75: 0.0296, 0.80: 0.0411, 0.85: 0.0554, 0.90: 0.0716, 0.95: 0.0895, 1.00: 0.1095, 1.05: 0.1326, 1.10: 0.1609, 1.15: 0.1971, 1.20: 0.2452, 1.25: 0.3100, 1.30: 0.4675},
        15000: {0.40: 0.0960, 0.45: 0.1160, 0.50: 0.1395, 0.55: 0.1662, 0.60: 0.1954, 0.65: 0.2266, 0.70: 0.2597, 0.75: 0.2951, 0.80: 0.3342, 0.85: 0.3790, 0.90: 0.4317, 0.95: 0.4949, 1.00: 0.5708, 1.05: 0.6609, 1.10: 0.8276, 1.15: 1.0623, 1.20: 1.2657, 1.25: 1.4102, 1.30: 1.4534},
        10000: {0.40: 0.3909, 0.45: 0.4464, 0.50: 0.5051, 0.55: 0.5667, 0.60: 0.6329, 0.65: 0.7069, 0.70: 0.7931, 0.75: 0.8947, 0.80: 1.0134, 0.85: 1.1503, 0.90: 1.3508, 0.95: 1.6853, 1.00: 2.0158, 1.05: 2.2952, 1.10: 2.5242, 1.15: 2.6830, 1.20: 2.7457, 1.25: 2.6946, 1.30: 2.4440},
        6000:  {0.40: 1.4694, 0.45: 1.6487, 0.50: 1.8629, 0.55: 2.1181, 0.60: 2.4190, 0.65: 2.9198, 0.70: 3.6172, 0.75: 4.2777, 0.80: 4.7817, 0.85: 5.2385, 0.90: 5.5940, 0.95: 5.8598, 1.00: 6.0777, 1.05: 6.1840, 1.10: 6.1496, 1.15: 6.0087, 1.20: 5.6855, 1.25: 5.1310, 1.30: 4.3117},
    }

    def test_source_faithful_below_one_msun(self):
        # CR-12: the ≤1.0 M☉ cooling AGES are re-derived from the dense Bedard 2020 source. The CR-11.1
        # "byte-identical ≤1.0" guarantee is deliberately SUPERSEDED (it protected the sparse-sampling
        # over-read): ages drop ~28%. radius/Teff/L stay source-faithful — the radius differs from the
        # old chord value by ~1e-6 (recomputed, not just loosened). Relative-ish tolerances (age places=4,
        # radius places=5) rather than places=6 so a benign last-ULP interpolation change can't flake it.
        r06 = cooling.compute_cooling_hz("wd", mass_solar=0.6, teff=25970)
        self.assertAlmostEqual(r06["cooling_age_gyr"], 0.015389, places=4)   # was 0.021342
        self.assertAlmostEqual(r06["radius_rsun"], 0.013900, places=5)
        r10 = cooling.compute_cooling_hz("wd", mass_solar=1.0, teff=25970)
        self.assertAlmostEqual(r10["cooling_age_gyr"], 0.109566, places=4)   # was 0.151411
        self.assertAlmostEqual(r10["radius_rsun"], 0.008294, places=5)

    def test_age_matches_source_at_anchors(self):
        # Tolerance is 2% = the WB re-gate tolerance, NOT the <0.5% build-time TABLE fidelity: the tool's
        # _age_for_teff bisection adds a ~1e-4 Gyr resolution floor (~1% at the youngest sub-0.01-Gyr
        # epochs), so 2% is the tightest gate that holds across the whole grid via the tool. _SOURCE here
        # is transcribe-pipeline-generated; test_age_matches_independent_verbatim_source_rows (below)
        # breaks that circularity with raw verification-doc rows.
        for teff, bymass in self._SOURCE.items():
            for m, src in bymass.items():
                got = cooling.compute_cooling_hz("wd", mass_solar=m, teff=teff)["cooling_age_gyr"]
                self.assertLessEqual(abs(got - src) / src, 0.02,
                                     f"{m} M☉ @ {teff} K: {got:.4f} vs source {src:.4f}")
        # Sirius B (1.018) interpolates between the 1.00 and 1.05 nodes @25970 (monotonic older-with-mass).
        sb = cooling.compute_cooling_hz("wd", mass_solar=1.018, teff=25970)["cooling_age_gyr"]
        self.assertTrue(0.1095 < sb < 0.1326, sb)

    def test_age_matches_independent_verbatim_source_rows(self):
        # F4 guard (independent of the transcribe pipeline): _SOURCE above is generated by the SAME
        # pipeline as _WD_COOLING, so a shared parse/units bug would corrupt both and still pass. These
        # raw (Teff_K, Age_yr) bracketing rows are the wd-cooling-grid-verification.md §3.1 VERBATIM pins
        # (cross-checked byte-for-byte against the seq files at build). The test does its OWN /1e9
        # conversion + linear-in-Teff interp, so a table age-units error is independently caught.
        def independent_gyr(lo, hi, teff):        # lo/hi = (Teff_K, Age_yr)
            w = (teff - lo[0]) / (hi[0] - lo[0])
            return (lo[1] + w * (hi[1] - lo[1])) / 1e9
        cases = [
            (1.00, 25970, (26239.5864, 1.054917e8), (25827.3842, 1.116121e8)),  # seq_100 -> ~0.1095 Gyr
            (0.90, 10000, (10157.5197, 1.275791e9), (9994.1959, 1.353542e9)),   # seq_090 -> ~1.351 Gyr
            (1.00, 10000, (10109.5634, 1.954125e9), (9934.1117, 2.052958e9)),   # seq_100 -> ~2.016 Gyr
        ]
        for m, teff, lo, hi in cases:
            expected = independent_gyr(lo, hi, teff)
            got = cooling.compute_cooling_hz("wd", mass_solar=m, teff=teff)["cooling_age_gyr"]
            self.assertLessEqual(abs(got - expected) / expected, 0.02,
                                 f"{m} M☉ @ {teff} K: {got:.4f} vs independent {expected:.4f}")

    def test_age_monotonic_with_mass_below_turnover(self):
        # At fixed Teff cooling age rises with mass up to the (Teff-dependent) crystallization turnover,
        # then may fall — real physics, kept. Assert STRICTLY monotone below the turnover (a flattened
        # age column must fail). Near-turnover steps are only ~1.7-2.3%, so this relies on the <0.5%
        # build tolerance, not the 2% re-gate.
        def age(m, teff):
            return cooling.compute_cooling_hz("wd", mass_solar=m, teff=teff)["cooling_age_gyr"]
        # 25970 K: no turnover through 1.30 — strictly increasing with mass.
        a = [age(m, 25970) for m in (0.90, 0.95, 1.00, 1.05, 1.10, 1.20, 1.30)]
        self.assertTrue(all(a[i] < a[i + 1] for i in range(len(a) - 1)), a)
        # 10000 K: rises to the ~1.20 turnover, then falls by 1.25.
        self.assertLess(age(1.15, 10000), age(1.20, 10000))
        self.assertGreater(age(1.20, 10000), age(1.25, 10000))
        # 6000 K: turnover near ~1.05 — 1.10 is younger than 1.05.
        self.assertGreater(age(1.05, 6000), age(1.10, 6000))


class Cr124OneCoreCaveatTest(unittest.TestCase):
    """CR-12.4 — the additive ``one_core_uncertain`` notes caveat for high-mass WDs, in ALL three modes
    (snapshot / residence / CHZ; Part 2 extended it beyond snapshot). The bundled grid is Bedard 2020
    CO-core; WDs > 1.05 M☉ may host O-Ne cores it does not resolve (Camisassa et al. 2019). Transparency
    flag only — NO numeric output changes; Sirius B (1.018) is below the threshold; text identical across modes."""

    _FLAG = "one_core_uncertain"

    def _notes(self, r):
        return " ".join(r.get("notes", []))

    def test_present_above_threshold(self):
        # criterion 1: 1.10/25970 -> caveat present, cooling_age unchanged (~0.161).
        r = cooling.compute_cooling_hz("wd", mass_solar=1.10, teff=25970)
        self.assertIn(self._FLAG, self._notes(r))
        self.assertAlmostEqual(r["cooling_age_gyr"], 0.161, delta=0.004)

    def test_absent_at_and_below_threshold(self):
        # criterion 2 (1.00) + the boundary (1.05, the top CO node — the gate is strictly >1.05).
        r100 = cooling.compute_cooling_hz("wd", mass_solar=1.00, teff=25970)
        self.assertNotIn(self._FLAG, self._notes(r100))
        self.assertAlmostEqual(r100["cooling_age_gyr"], 0.1096, delta=0.003)
        r105 = cooling.compute_cooling_hz("wd", mass_solar=1.05, teff=25970)
        self.assertNotIn(self._FLAG, self._notes(r105))

    def test_sirius_b_unaffected(self):
        # criterion 3: Sirius B 1.018/25970 is below the threshold -> absent, value unchanged.
        r = cooling.compute_cooling_hz("wd", mass_solar=1.018, teff=25970)
        self.assertNotIn(self._FLAG, self._notes(r))
        self.assertAlmostEqual(r["cooling_age_gyr"], 0.1178, delta=0.004)

    def test_coexists_with_other_notes_no_numeric_drift(self):
        # criterion 4: the caveat coexists with a pre-existing note and changes NO numeric field.
        # A hot young >T_ONe snapshot carries BOTH one_core_uncertain and hz_undefined_extrapolation.
        r_hot = cooling.compute_cooling_hz("wd", mass_solar=1.20, cooling_age_gyr=0.0001)
        notes = " ".join(r_hot.get("notes", []))
        self.assertIn(self._FLAG, notes)
        self.assertIn("hz_undefined_extrapolation", notes)     # pre-existing note intact
        # numerics untouched by the additive note: 1.20/25970 still the CR-12 source value.
        r = cooling.compute_cooling_hz("wd", mass_solar=1.20, teff=25970)
        self.assertAlmostEqual(r["cooling_age_gyr"], 0.245, delta=0.006)

    def test_threshold_and_source_documented(self):
        # criterion 5: T_ONe and its cited source are recorded in code + surfaced in the runtime note.
        self.assertEqual(cooling._T_ONE_MSUN, 1.05)
        note = self._notes(cooling.compute_cooling_hz("wd", mass_solar=1.10, teff=25970))
        self.assertIn("Camisassa", note)          # cited source
        self.assertIn("1.05", note)               # threshold

    # ── CR-12.4 Part 2: residence + CHZ modes (criteria 6-10) ───────────────────────────────────
    def test_residence_and_chz_modes_carry_caveat(self):
        # criteria 6-8: residence + CHZ modes gain a `notes` array with the caveat >1.05, empty ≤1.05.
        res_hi = cooling.compute_cooling_hz("wd", mass_solar=1.10, sma_au=0.01)
        self.assertEqual(res_hi["mode"], "residence")
        self.assertIn(self._FLAG, self._notes(res_hi))
        self.assertEqual(cooling.compute_cooling_hz("wd", mass_solar=1.018, sma_au=0.01)["notes"], [])  # Sirius B
        chz_hi = cooling.compute_cooling_hz("wd", mass_solar=1.10, chz_threshold_gyr=3.0)
        self.assertEqual(chz_hi["mode"], "chz")
        self.assertIn(self._FLAG, self._notes(chz_hi))
        self.assertEqual(cooling.compute_cooling_hz("wd", mass_solar=1.00, chz_threshold_gyr=3.0)["notes"], [])

    def test_identical_caveat_text_across_all_three_modes(self):
        # criterion 10: byte-identical note string in snapshot / residence / CHZ (one source of truth).
        def onecore(r):
            return [n for n in r.get("notes", []) if self._FLAG in n]
        snap = onecore(cooling.compute_cooling_hz("wd", mass_solar=1.10, teff=25970))
        res = onecore(cooling.compute_cooling_hz("wd", mass_solar=1.10, sma_au=0.01))
        chz = onecore(cooling.compute_cooling_hz("wd", mass_solar=1.10, chz_threshold_gyr=3.0))
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap, res)
        self.assertEqual(res, chz)

    def test_bd_track_never_flagged(self):
        # the CO->ONe caveat is a WD-core concept; the BD track never carries it, in any mode.
        for kw in (dict(cooling_age_gyr=0.01), dict(sma_au=0.02), dict(chz_threshold_gyr=3.0)):
            self.assertNotIn(self._FLAG,
                             self._notes(cooling.compute_cooling_hz("bd", mass_mjup=60.0, **kw)))

    def test_part2_no_numeric_drift(self):
        # criteria 6-9: the caveat is a SEPARATE additive field, so residence/CHZ numerics are untouched.
        # Regression pin at a >1.05 mass (these ARE the CR-12 values — Part 2 never touches the computation).
        res = cooling.compute_cooling_hz("wd", mass_solar=1.10, sma_au=0.01)
        self.assertAlmostEqual(res["residence_gyr"], 3.748, delta=0.02)
        self.assertAlmostEqual(res["entry_age_gyr"], 4.575, delta=0.02)


class DistillationPauseTest(unittest.TestCase):
    """Phase AD A0 — the ²²Ne distillation cooling pause (--cooling-delay-gyr).

    Anchored to Vanderburg, Bedard, Becker & Blouin 2025 (arXiv:2501.06613): a 0.6 M_sun DA
    pauses at Teff ~ 5500 K, and the pause roughly doubles-to-triples the max HZ residence
    (their Table 1: 6.67 -> 15.56 Gyr) while pushing the long-residence CHZ outward.
    """

    def test_delta_zero_byte_identical(self):
        # The headline regression pin: Δt=0 (default) reproduces the pre-A0 result exactly,
        # across all three modes.
        for kw in (dict(teff=5000),
                   dict(sma_au=0.01, hz_edge="optimistic"),
                   dict(chz_threshold_gyr=3.0)):
            base = cooling.compute_cooling_hz("wd", mass_solar=0.6, **kw)
            zero = cooling.compute_cooling_hz("wd", mass_solar=0.6,
                                              cooling_delay_gyr=0.0, **kw)
            self.assertEqual(base, zero, kw)
            # and no pause_* keys leak into the Δt=0 output
            self.assertNotIn("pause_teff_k", base)
            self.assertNotIn("cooling_delay_gyr", base)

    def test_pause_fields_present_and_consistent(self):
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=3.0,
                                       cooling_delay_gyr=8.0)
        self.assertAlmostEqual(r["pause_teff_k"], 5500.0, delta=5.0)   # onset Teff (0.6 M_sun)
        self.assertEqual(r["pause_duration_gyr"], 8.0)
        self.assertEqual(r["cooling_delay_gyr"], 8.0)
        self.assertEqual(r["distillation_teff_k"], 5500.0)
        self.assertAlmostEqual(r["effective_age_max_gyr"], 13.8 + 8.0, places=6)
        self.assertLess(r["pause_hz_inner_au"], r["pause_hz_outer_au"])
        # pause HZ band ~ 0.011-0.019 AU for a 0.6 M_sun WD at 5500 K
        self.assertTrue(0.009 < r["pause_hz_inner_au"] < 0.013, r["pause_hz_inner_au"])
        self.assertTrue(0.017 < r["pause_hz_outer_au"] < 0.021, r["pause_hz_outer_au"])
        self.assertIn("distillation pause", r["model_note"])
        self.assertIn("Vanderburg", r["model_note"])

    def test_residence_lengthens_by_delta(self):
        # A planet inside the frozen pause-HZ band stays habitable for the whole pause, so its
        # residence rises by ~Δt (Vanderburg direction).
        a = 0.017
        base = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=a)
        paused = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=a,
                                            cooling_delay_gyr=10.0)
        self.assertTrue(base["ever_habitable"] and paused["ever_habitable"])
        self.assertAlmostEqual(paused["residence_gyr"] - base["residence_gyr"], 10.0, delta=0.5)

    def test_peak_residence_matches_vanderburg(self):
        # Their Table 1: standard 6.67 Gyr -> distillation 15.56 Gyr for a 0.6 M_sun WD.
        def peak(dt):
            best, a = 0.0, 0.006
            while a < 0.03:
                r = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=a,
                                               cooling_delay_gyr=dt)
                if r.get("residence_gyr"):
                    best = max(best, r["residence_gyr"])
                a *= 1.03
            return best
        std, dist = peak(0.0), peak(10.0)
        self.assertTrue(5.5 < std < 7.5, std)        # ~6.3, matches their 6.67
        self.assertTrue(14.0 < dist < 18.0, dist)    # ~16, matches their 15.56 direction
        self.assertGreater(dist, std + 8.0)          # pause adds ~Δt

    def test_chz_moves_outward(self):
        # At a long-residence threshold the standard CHZ can't reach the outer orbits the
        # distillation pause freezes into — so the pause pushes the CHZ outer edge outward.
        b6 = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=6.0)
        p6 = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=6.0,
                                        cooling_delay_gyr=8.0)
        # CR-12 None-guard: the no-pause thr-6.0 band must be non-empty (0.6 M☉ peak ~6.98 > 6.0);
        # fail cleanly rather than assertGreater(number, None) → TypeError if a future shift empties it.
        self.assertIsNotNone(b6["chz_outer_au"])
        self.assertIsNotNone(p6["chz_outer_au"])
        self.assertGreater(p6["chz_outer_au"], b6["chz_outer_au"])
        # At 8 Gyr standard cooling yields NO CHZ, but the pause creates one.
        b8 = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=8.0)
        p8 = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=8.0,
                                        cooling_delay_gyr=10.0)
        self.assertIsNone(b8["chz_outer_au"])
        self.assertIsNotNone(p8["chz_outer_au"])

    def test_snapshot_through_pause(self):
        # Snapshot by the pause Teff resolves to the pause epoch and carries the pause block.
        r = cooling.compute_cooling_hz("wd", mass_solar=0.6, teff=5500, cooling_delay_gyr=10.0)
        self.assertEqual(r["mode"], "snapshot")
        self.assertAlmostEqual(r["teff_k"], 5500.0, delta=5.0)
        self.assertIn("pause_teff_k", r)

    def test_validation(self):
        cases = [
            dict(cooling_delay_gyr=-1.0),                                  # negative delay
            dict(cooling_delay_gyr=5.0, distillation_teff_k=0.0),          # teff <= 0
            dict(cooling_delay_gyr=5.0, distillation_teff_k=200000.0),     # distil Teff off track
        ]
        for kw in cases:
            r = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=3.0, **kw)
            self.assertIn("error", r, kw)
        # distillation is a WD mechanism — rejected on the BD track
        rbd = cooling.compute_cooling_hz("bd", mass_mjup=52.4, sma_au=0.05,
                                         cooling_delay_gyr=5.0)
        self.assertIn("error", rbd)

    def test_determinism(self):
        a = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=6.0,
                                       cooling_delay_gyr=8.0)
        b = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=6.0,
                                       cooling_delay_gyr=8.0)
        self.assertEqual(a, b)


class ValidationTest(unittest.TestCase):
    def test_error_matrix(self):
        cases = [
            dict(track="xx"),
            dict(track="wd", mass_solar=2.0),                 # off-grid (WD grid 0.4-1.30; 2.0 > Chandrasekhar)
            dict(track="bd", mass_mjup=200),                  # off-grid (BD grid ~13-75)
            dict(track="wd", teff=-5),
            dict(track="wd", sma_au=0.0),
            dict(track="wd", cooling_age_gyr=-1),
            dict(track="wd", chz_threshold_gyr=0),
            dict(track="wd", age_max_gyr=0),
            dict(track="wd", satellite_density=-1),
            dict(track="wd", hz_edge="bogus"),
        ]
        for kw in cases:
            r = cooling.compute_cooling_hz(**kw)
            self.assertIn("error", r, kw)

    def test_common_fields_and_determinism(self):
        r1 = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.011)
        r2 = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.011)
        self.assertEqual(r1, r2)                              # deterministic
        for k in ("track", "mass_solar", "model_note", "any_out_of_range",
                  "hz_model_valid_teff_k"):
            self.assertIn(k, r1)
        self.assertEqual(r1["hz_model_valid_teff_k"], [2600.0, 7200.0])
        self.assertIn("Bedard", r1["model_note"])


class ChzDegenerateBandTest(unittest.TestCase):
    """P1.2 regression — `_chz_band`'s `hi <= lo` early return must emit the keys
    the consumer `_mode_chz` reads (`ctrl_inner_oor`/`ctrl_outer_oor`), NOT the old
    `ctrl_entry_teff`/`ctrl_exit_teff`, which raised an uncaught KeyError.

    `hi <= lo` requires the hot young outer edge to fall inside the cold old inner
    edge — physically impossible with the real cooling tracks — so `_edge_au` is
    patched to force the degenerate geometry while every other helper runs against
    the real bundled 0.6 M_sun WD track.
    """

    @staticmethod
    def _force_degenerate(track, grid_mass, age, key, pause=None):
        # conservative hz_edge → ik="rg" (inner), ok="mg" (outer).
        # inner_old large, outer_young small → hi = 0.1*1.5 < lo = 3.0.
        return 10.0 if key == "rg" else 0.1

    def test_chz_band_degenerate_keys(self):
        with mock.patch.object(cooling, "_edge_au", side_effect=self._force_degenerate):
            band = cooling._chz_band("wd", 0.6, 3.0, "conservative", 13.8)
        self.assertEqual(
            set(band),
            {"chz_inner_au", "chz_outer_au", "ctrl_inner_oor", "ctrl_outer_oor"},
        )
        self.assertNotIn("ctrl_entry_teff", band)
        self.assertNotIn("ctrl_exit_teff", band)
        for k in band:
            self.assertIsNone(band[k])

    def test_mode_chz_no_keyerror_on_degenerate_band(self):
        # The actual bug site: _mode_chz reads band["ctrl_inner_oor"]/["ctrl_outer_oor"].
        base = {"mass_solar": 0.6}
        with mock.patch.object(cooling, "_edge_au", side_effect=self._force_degenerate):
            out = cooling._mode_chz("wd", 0.6, base, 3.0, "conservative", 13.8, 5.5)
        self.assertIsNone(out["chz_inner_au"])
        self.assertIsNone(out["chz_outer_au"])
        self.assertIsNone(out["chz_inner_out_of_range"])
        self.assertIsNone(out["chz_outer_out_of_range"])
        self.assertFalse(out["any_out_of_range"])


if __name__ == "__main__":
    unittest.main()
