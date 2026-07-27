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
        lo_w = lo["chz_outer_au"] - lo["chz_inner_au"]
        hi_w = hi["chz_outer_au"] - hi["chz_inner_au"]
        self.assertGreater(lo_w, hi_w)

    def test_chz_reproduces_across_masses(self):
        # Acceptance: CHZ ~ 0.005-0.02 AU holds across 0.4-0.9 M_sun (Agol 2011).
        for m in (0.40, 0.50, 0.70, 0.80, 0.90):
            r = cooling.compute_cooling_hz("wd", mass_solar=m, chz_threshold_gyr=3.0)
            self.assertLess(r["chz_inner_au"], r["chz_outer_au"], m)
            self.assertTrue(0.003 < r["chz_inner_au"] < 0.012, (m, r["chz_inner_au"]))
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
            dict(track="wd", mass_solar=2.0),                 # off-grid (WD grid 0.4-1.0)
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
