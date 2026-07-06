# tests/test_query_phase_t.py — Phase T1a + T1b query.py subcommand contracts.
#
# T1a (5 items): trojan-stability, lorentz-factor, circumbinary-hz (new), plus
# additive extensions to hill-sphere (Domingos exomoon keys) and gcns-within-sol
# (--wd-prob-*).
# T1b (8 calculators + 1 input mode): the detectability group rv-semi-amplitude /
# transit-signal / astrometric-signal / direct-imaging (A1–A4); tidal-heating (B1,
# order-of-mag); kozai-lidov (C2, order-of-mag); relativistic-brachistochrone (D1);
# and the deferred circumbinary-hz --star1/--star2 SIMBAD-resolve mode.
#
# These tests lock the happy-path JSON contract (keys + verified anchors), core/
# input-mode parity, the self-validating exit-code matrix (curated {"error"} →
# exit 1; argparse → exit 2), and — for T1a — the hill-sphere additive-regression
# guard and the gcns-within-sol --wd-prob filter (seeded throwaway gcns_stars).
#
# Subprocess harness mirrors tests/test_query_phase_n.py.

import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import core.calculators as calculators
import core.db as db
import core.databases as databases
import core.equations as equations
import core.feasibility as feasibility

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent

_ENV = make_env("phase_t_throwaway.db")


def _run(*cmd_args, env=None):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    return run_query(*cmd_args, env=env or _ENV)


# ── T1a-1 · trojan-stability (wraps R2 gascheau_coorbital_stable) ─────────────

class TrojanStabilityTest(unittest.TestCase):

    def test_happy_path_contract(self):
        code, payload, _ = _run("trojan-stability", "--host-mass-earth", "1",
                                "--companion-mass-earth", "0", "--star-mass-solar", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"mass_ratio", "criterion", "stable"})
        self.assertTrue(payload["stable"])
        self.assertAlmostEqual(payload["criterion"], 0.03852089650455137, places=10)

    def test_parity_with_core(self):
        code, payload, _ = _run("trojan-stability", "--host-mass-earth", "300",
                                "--companion-mass-earth", "1", "--star-mass-solar", "0.8")
        self.assertEqual(code, 0)
        self.assertEqual(payload, feasibility.gascheau_coorbital_stable(300.0, 1.0, 0.8))

    def test_flips_at_mu_critical(self):
        # μ_crit ≈ 0.0385 → host ≈ 12,823 Earth masses around 1 M☉.
        below = _run("trojan-stability", "--host-mass-earth", "12800",
                     "--companion-mass-earth", "0", "--star-mass-solar", "1")[1]
        above = _run("trojan-stability", "--host-mass-earth", "12900",
                     "--companion-mass-earth", "0", "--star-mass-solar", "1")[1]
        self.assertTrue(below["stable"])
        self.assertFalse(above["stable"])
        self.assertLess(below["mass_ratio"], below["criterion"])
        self.assertGreater(above["mass_ratio"], above["criterion"])

    def test_bad_input_exit1(self):
        for args in (("--host-mass-earth", "0", "--companion-mass-earth", "0",
                      "--star-mass-solar", "1"),
                     ("--host-mass-earth", "1", "--companion-mass-earth", "0",
                      "--star-mass-solar", "0")):
            code, payload, _ = _run("trojan-stability", *args)
            self.assertEqual(code, 1)
            self.assertIn("error", payload)

    def test_argparse_exit2(self):
        code, _, _ = _run("trojan-stability", "--host-mass-earth", "1",
                          "--companion-mass-earth", "0")  # missing --star-mass-solar
        self.assertEqual(code, 2)
        code, _, _ = _run("trojan-stability", "--host-mass-earth", "x",
                          "--companion-mass-earth", "0", "--star-mass-solar", "1")
        self.assertEqual(code, 2)


# ── T1a-2 · lorentz-factor (new pure-math) ────────────────────────────────────

class LorentzFactorTest(unittest.TestCase):

    def test_happy_path_contract(self):
        code, payload, _ = _run("lorentz-factor", "--velocity-c", "0.6")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"velocity_c", "lorentz_factor", "time_dilation_pct"})
        self.assertAlmostEqual(payload["lorentz_factor"], 1.25, places=9)
        self.assertAlmostEqual(payload["time_dilation_pct"], 25.0, places=9)

    def test_anchors(self):
        self.assertAlmostEqual(
            _run("lorentz-factor", "--velocity-c", "0")[1]["lorentz_factor"], 1.0, places=12)
        big = _run("lorentz-factor", "--velocity-c", "0.999")[1]["lorentz_factor"]
        self.assertGreater(big, 22.0)  # γ(0.999) ≈ 22.37

    def test_parity_with_core(self):
        code, payload, _ = _run("lorentz-factor", "--velocity-c", "0.87")
        self.assertEqual(payload, calculators.compute_lorentz_factor(0.87))

    def test_bad_input_exit1(self):
        for v in ("1", "1.5", "-0.1"):
            code, payload, _ = _run("lorentz-factor", "--velocity-c", v)
            self.assertEqual(code, 1)
            self.assertIn("error", payload)

    def test_argparse_exit2(self):
        self.assertEqual(_run("lorentz-factor")[0], 2)               # missing
        self.assertEqual(_run("lorentz-factor", "--velocity-c", "x")[0], 2)  # non-numeric


# ── T1a-3 · circumbinary-hz (reuses compute_habitable_zone) ───────────────────

class CircumbinaryHzTest(unittest.TestCase):

    def test_happy_path_contract(self):
        code, payload, _ = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                                "--teff2", "5778", "--lum2", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload),
                         {"teff1", "lum1", "teff2", "lum2", "combined_lum",
                          "eff_teff", "out_of_range_teff", "zones"})
        self.assertEqual(len(payload["zones"]), 6)
        for z in payload["zones"]:
            self.assertEqual(set(z), {"zone_name", "key", "au", "lm", "seff"})

    def test_lum_weighted_eff_teff(self):
        # Equal stars → eff_teff = common teff; combined_lum = L1+L2.
        eq = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                  "--teff2", "5778", "--lum2", "1")[1]
        self.assertAlmostEqual(eq["eff_teff"], 5778.0, places=6)
        self.assertAlmostEqual(eq["combined_lum"], 2.0, places=9)
        self.assertFalse(eq["out_of_range_teff"])
        # Degenerate lum2 → 0 collapses eff_teff toward teff1.
        deg = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                   "--teff2", "3000", "--lum2", "0.0001")[1]
        self.assertAlmostEqual(deg["eff_teff"], 5778.0, delta=1.0)

    def test_out_of_range_flag_not_clamp(self):
        cool = _run("circumbinary-hz", "--teff1", "2400", "--lum1", "0.01",
                    "--teff2", "2400", "--lum2", "0.01")[1]
        self.assertTrue(cool["out_of_range_teff"])
        self.assertAlmostEqual(cool["eff_teff"], 2400.0, places=6)   # not clamped to 2600
        self.assertEqual(len(cool["zones"]), 6)                      # still returned

    def test_parity_with_core(self):
        code, payload, _ = _run("circumbinary-hz", "--teff1", "5000", "--lum1", "0.5",
                                "--teff2", "4000", "--lum2", "0.2")
        self.assertEqual(payload, equations.compute_circumbinary_hz(5000.0, 0.5, 4000.0, 0.2))

    def test_bad_input_exit1(self):
        code, payload, _ = _run("circumbinary-hz", "--teff1", "0", "--lum1", "1",
                                "--teff2", "5778", "--lum2", "1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_incomplete_numeric_exit1(self):
        # P4.1: partial numeric (missing --lum2) is a handler validation failure,
        # now a curated {"error"} on stdout with exit 1 (was stderr/exit 2).
        code, payload, _ = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                                "--teff2", "5778")  # missing --lum2
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


# ── T1a-4 · hill-sphere Domingos exomoon keys (additive extension) ────────────

class HillSphereExomoonTest(unittest.TestCase):

    def test_new_keys_present(self):
        code, payload, _ = _run("hill-sphere", "--star-mass-solar", "1",
                                "--planet-mass-earth", "1", "--sma-au", "1")
        self.assertEqual(code, 0)
        for k in ("moon_inclination_deg", "prograde", "stable_fraction",
                  "stable_moon_limit_au", "stable_moon_limit_km"):
            self.assertIn(k, payload)

    def test_domingos_prograde_anchor(self):
        p = _run("hill-sphere", "--star-mass-solar", "1",
                 "--planet-mass-earth", "1", "--sma-au", "1")[1]
        self.assertAlmostEqual(p["stable_fraction"], 0.4895, places=6)
        self.assertAlmostEqual(p["stable_moon_limit_au"],
                               p["stable_fraction"] * p["hill_radius_au"], places=12)
        self.assertTrue(p["prograde"])

    def test_retrograde_changes_fraction(self):
        r = _run("hill-sphere", "--star-mass-solar", "1", "--planet-mass-earth", "1",
                 "--sma-au", "1", "--retrograde")[1]
        self.assertAlmostEqual(r["stable_fraction"], 0.9309, places=6)
        self.assertFalse(r["prograde"])

    def test_inclination_reduces_fraction(self):
        flat = _run("hill-sphere", "--star-mass-solar", "1", "--planet-mass-earth", "1",
                    "--sma-au", "1")[1]["stable_fraction"]
        incl = _run("hill-sphere", "--star-mass-solar", "1", "--planet-mass-earth", "1",
                    "--sma-au", "1", "--moon-inclination-deg", "45")[1]["stable_fraction"]
        self.assertLess(incl, flat)

    def test_existing_keys_unchanged_when_args_omitted(self):
        """The pre-existing hill-sphere keys are byte-identical with new args omitted."""
        payload = _run("hill-sphere", "--star-mass-solar", "1",
                       "--planet-mass-earth", "1", "--sma-au", "1")[1]
        legacy = {"star_mass_solar", "planet_mass_earth", "sma_au", "eccentricity",
                  "hill_radius_km", "hill_radius_au",
                  "stable_orbit_limit_km", "stable_orbit_limit_au"}
        # Compare each legacy key against a direct core call with only the old args.
        core_old = equations.compute_hill_sphere(1.0, 1.0, 1.0, 0)
        for k in legacy:
            self.assertEqual(payload[k], core_old[k])

    def test_bad_inclination_exit1(self):
        code, payload, _ = _run("hill-sphere", "--star-mass-solar", "1",
                                "--planet-mass-earth", "1", "--sma-au", "1",
                                "--moon-inclination-deg", "200")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


# ── T1a-5 · gcns-within-sol --wd-prob-* filter (seeded throwaway DB) ──────────

class GcnsWdProbFilterTest(unittest.TestCase):
    """Build a throwaway gcns_stars on disk, then drive query.py against it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dbpath = pathlib.Path(self.tmpdir) / "gcns_t.db"
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = self.dbpath
            db._conn = None
            db._auto_seed = lambda conn: None  # skip static CSV seeding
            conn = db.get_conn()
            conn.executemany(
                "INSERT INTO gcns_stars (gaia_source_id, ra, dec, light_years, dist_pc, "
                "wd_prob, in_gcns, in_simbad, distance_method, gcns_table) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, 0, 'gcns_bayesian', 'main')",
                [
                    (1, 0.0,  0.0,  4.0, 1.2, 0.95),   # high wd_prob (white dwarf)
                    (2, 90.0, 0.0,  2.0, 0.6, 0.02),   # low wd_prob
                    (3, 0.0,  45.0, 6.0, 1.8, None),   # null wd_prob
                ],
            )
            conn.commit()
            db.close_conn()
        finally:
            db._DB_PATH, db._conn, db._auto_seed = saved

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _env(self):
        return {"SPACE_APP_DB": str(self.dbpath), "PATH": os.environ.get("PATH", "")}

    def test_unfiltered_byte_identical(self):
        code, payload, _ = _run("gcns-within-sol", "--ly", "20", env=self._env())
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 3)
        ids = {s["gaia_source_id"] for s in payload["stars"]}
        self.assertEqual(ids, {1, 2, 3})

    def test_wd_prob_min_filters_to_white_dwarfs(self):
        code, payload, _ = _run("gcns-within-sol", "--ly", "20",
                                "--wd-prob-min", "0.5", env=self._env())
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["stars"][0]["gaia_source_id"], 1)  # null wd_prob excluded too

    def test_wd_prob_max_filters_out_white_dwarfs(self):
        code, payload, _ = _run("gcns-within-sol", "--ly", "20",
                                "--wd-prob-max", "0.5", env=self._env())
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["stars"][0]["gaia_source_id"], 2)

    def test_min_above_max_matches_nothing(self):
        code, payload, _ = _run("gcns-within-sol", "--ly", "20", "--wd-prob-min", "0.9",
                                "--wd-prob-max", "0.1", env=self._env())
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 0)

    def test_argparse_exit2_non_numeric(self):
        code, _, _ = _run("gcns-within-sol", "--ly", "20",
                          "--wd-prob-min", "abc", env=self._env())
        self.assertEqual(code, 2)


# ═══════════════════════════════════════════════════════════════════════════
# Phase T1b — new pure-math calculators
# ═══════════════════════════════════════════════════════════════════════════

# ── A1 · rv-semi-amplitude ────────────────────────────────────────────────────

class RvSemiAmplitudeTest(unittest.TestCase):

    def test_earth_sun_anchor(self):
        code, p, _ = _run("rv-semi-amplitude", "--planet-mass-earth", "1",
                          "--star-mass-solar", "1", "--period-days", "365.25")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"k_ms", "period_days", "sma_au", "ecc",
                                  "inclination_deg", "planet_mass_earth", "star_mass_solar"})
        self.assertAlmostEqual(p["k_ms"], 0.0895, places=3)        # ~0.09 m/s
        self.assertAlmostEqual(p["sma_au"], 1.0, places=2)

    def test_period_sma_parity(self):
        by_p = _run("rv-semi-amplitude", "--planet-mass-earth", "1", "--star-mass-solar", "1",
                    "--period-days", "365.25")[1]
        by_a = _run("rv-semi-amplitude", "--planet-mass-earth", "1", "--star-mass-solar", "1",
                    "--sma-au", "1.0")[1]
        self.assertAlmostEqual(by_p["k_ms"], by_a["k_ms"], places=4)

    def test_core_parity(self):
        code, p, _ = _run("rv-semi-amplitude", "--planet-mass-earth", "5", "--star-mass-solar", "0.8",
                          "--sma-au", "0.3", "--ecc", "0.1", "--inclination-deg", "60")
        self.assertEqual(p, calculators.compute_rv_semi_amplitude(
            5.0, 0.8, sma_au=0.3, ecc=0.1, inclination_deg=60))

    def test_bad_input_exit1(self):
        self.assertEqual(_run("rv-semi-amplitude", "--planet-mass-earth", "0",
                              "--star-mass-solar", "1", "--sma-au", "1")[0], 1)
        self.assertEqual(_run("rv-semi-amplitude", "--planet-mass-earth", "1",
                              "--star-mass-solar", "1", "--sma-au", "1", "--ecc", "1")[0], 1)

    def test_argparse_exit2(self):
        # neither period nor sma (required mutually-exclusive group)
        self.assertEqual(_run("rv-semi-amplitude", "--planet-mass-earth", "1",
                              "--star-mass-solar", "1")[0], 2)
        # both period and sma
        self.assertEqual(_run("rv-semi-amplitude", "--planet-mass-earth", "1",
                              "--star-mass-solar", "1", "--period-days", "365",
                              "--sma-au", "1")[0], 2)


# ── A2 · transit-signal ───────────────────────────────────────────────────────

class TransitSignalTest(unittest.TestCase):

    def test_earth_sun_anchor(self):
        code, p, _ = _run("transit-signal", "--planet-radius-earth", "1",
                          "--star-radius-solar", "1", "--sma-au", "1", "--star-mass-solar", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"depth_ppm", "depth_frac", "transit_prob", "duration_hours",
                                  "sma_au", "period_days", "planet_radius_earth", "star_radius_solar"})
        self.assertAlmostEqual(p["depth_ppm"], 83.9, places=1)
        self.assertAlmostEqual(p["transit_prob"], 0.00465, places=4)
        self.assertAlmostEqual(p["duration_hours"], 13.0, delta=0.5)

    def test_sma_only_leaves_duration_none(self):
        p = _run("transit-signal", "--planet-radius-earth", "1",
                 "--star-radius-solar", "1", "--sma-au", "1")[1]
        self.assertAlmostEqual(p["depth_ppm"], 83.9, places=1)
        self.assertIsNone(p["duration_hours"])
        self.assertIsNone(p["period_days"])

    def test_period_path_derives_sma(self):
        p = _run("transit-signal", "--planet-radius-earth", "1", "--star-radius-solar", "1",
                 "--period-days", "365.25", "--star-mass-solar", "1")[1]
        self.assertAlmostEqual(p["sma_au"], 1.0, places=3)

    def test_bad_input(self):
        self.assertEqual(_run("transit-signal", "--planet-radius-earth", "0",
                              "--star-radius-solar", "1", "--sma-au", "1")[0], 1)
        # neither sma nor (period+mass)
        self.assertEqual(_run("transit-signal", "--planet-radius-earth", "1",
                              "--star-radius-solar", "1")[0], 1)
        # missing required radius -> argparse
        self.assertEqual(_run("transit-signal", "--planet-radius-earth", "1")[0], 2)


# ── A3 · astrometric-signal ───────────────────────────────────────────────────

class AstrometricSignalTest(unittest.TestCase):

    def test_jupiter_sun_10pc_anchor(self):
        code, p, _ = _run("astrometric-signal", "--planet-mass-earth", "317.828",
                          "--star-mass-solar", "1", "--sma-au", "5.2", "--distance-pc", "10")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"signal_microarcsec", "signal_arcsec", "planet_mass_earth",
                                  "star_mass_solar", "sma_au", "distance_pc"})
        self.assertAlmostEqual(p["signal_microarcsec"], 496, delta=5)
        self.assertAlmostEqual(p["signal_arcsec"] * 1e6, p["signal_microarcsec"], places=6)

    def test_bad_input(self):
        self.assertEqual(_run("astrometric-signal", "--planet-mass-earth", "1",
                              "--star-mass-solar", "1", "--sma-au", "1", "--distance-pc", "0")[0], 1)
        self.assertEqual(_run("astrometric-signal", "--planet-mass-earth", "1",
                              "--star-mass-solar", "1", "--sma-au", "1")[0], 2)


# ── A4 · direct-imaging ───────────────────────────────────────────────────────

class DirectImagingTest(unittest.TestCase):

    def test_earth_sun_anchor_no_telescope(self):
        code, p, _ = _run("direct-imaging", "--sma-au", "1", "--distance-pc", "10",
                          "--planet-radius-earth", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"angular_sep_arcsec", "contrast_reflected", "iwa_arcsec",
                                  "resolvable", "sma_au", "distance_pc", "planet_radius_earth", "albedo"})
        self.assertAlmostEqual(p["angular_sep_arcsec"], 0.1, places=6)
        self.assertAlmostEqual(p["contrast_reflected"], 5.4e-10, delta=0.2e-10)
        self.assertIsNone(p["iwa_arcsec"])
        self.assertIsNone(p["resolvable"])

    def test_iwa_when_telescope_given(self):
        p = _run("direct-imaging", "--sma-au", "1", "--distance-pc", "10",
                 "--planet-radius-earth", "1", "--telescope-diameter-m", "6.5",
                 "--wavelength-um", "1.0")[1]
        self.assertIsNotNone(p["iwa_arcsec"])
        self.assertIsInstance(p["resolvable"], bool)
        self.assertTrue(p["resolvable"])             # sep 0.1" > IWA ~0.032"

    def test_only_one_telescope_arg_errors(self):
        # Only --telescope-diameter-m (no --wavelength-um): core returns {"error"} → exit 1.
        code, p, _ = _run("direct-imaging", "--sma-au", "1", "--distance-pc", "10",
                          "--planet-radius-earth", "1", "--telescope-diameter-m", "6.5")
        self.assertEqual(code, 1)
        self.assertIn("error", p)

    def test_bad_input(self):
        self.assertEqual(_run("direct-imaging", "--sma-au", "0", "--distance-pc", "10",
                              "--planet-radius-earth", "1")[0], 1)
        self.assertEqual(_run("direct-imaging", "--sma-au", "1", "--distance-pc", "10",
                              "--planet-radius-earth", "1", "--albedo", "0")[0], 1)


# ── B1 · tidal-heating ────────────────────────────────────────────────────────

class TidalHeatingTest(unittest.TestCase):

    def test_io_like_anchor(self):
        code, p, _ = _run("tidal-heating", "--primary-mass-earth", "317.828",
                          "--satellite-radius-km", "1821", "--sma-km", "421700", "--ecc", "0.0041")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"heating_power_w", "surface_flux_wm2", "mean_motion_rad_s",
                                  "io_flux_ratio", "primary_mass_earth", "satellite_radius_km",
                                  "sma_km", "ecc", "k2", "tidal_q"})
        self.assertAlmostEqual(p["mean_motion_rad_s"], 4.1e-5, delta=0.2e-5)
        self.assertGreater(p["io_flux_ratio"], 0.01)    # O(1) order, not zero
        self.assertLess(p["io_flux_ratio"], 100)

    def test_surface_flux_consistency(self):
        p = _run("tidal-heating", "--primary-mass-earth", "317.828", "--satellite-radius-km", "1821",
                 "--sma-km", "421700", "--ecc", "0.01")[1]
        r_m = 1821 * 1000.0
        self.assertAlmostEqual(p["surface_flux_wm2"],
                               p["heating_power_w"] / (4 * math.pi * r_m ** 2), places=6)
        self.assertAlmostEqual(p["io_flux_ratio"], p["surface_flux_wm2"] / 2.0, places=9)

    def test_bad_input(self):
        self.assertEqual(_run("tidal-heating", "--primary-mass-earth", "1",
                              "--satellite-radius-km", "1000", "--sma-km", "100000", "--ecc", "1")[0], 1)
        self.assertEqual(_run("tidal-heating", "--primary-mass-earth", "1",
                              "--satellite-radius-km", "1000", "--sma-km", "100000",
                              "--ecc", "0.1", "--k2", "0")[0], 1)
        self.assertEqual(_run("tidal-heating", "--primary-mass-earth", "1")[0], 2)


# ── C2 · kozai-lidov ──────────────────────────────────────────────────────────

class KozaiLidovTest(unittest.TestCase):

    def test_anchor(self):
        code, p, _ = _run("kozai-lidov", "--m1-solar", "1", "--m2-solar", "1", "--m3-solar", "1",
                          "--period-inner-yr", "1", "--period-outer-yr", "100")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"timescale_years", "m1_solar", "m2_solar", "m3_solar",
                                  "period_inner_yr", "period_outer_yr", "ecc_outer"})
        # (8/15π)·3·(100²/1) ≈ 5093 yr
        self.assertAlmostEqual(p["timescale_years"], 5093, delta=5)

    def test_period_sma_parity(self):
        # sma mode derives P_in=√(1/2), P_out=√(27000/3); feed those back as periods.
        by_sma = _run("kozai-lidov", "--m1-solar", "1", "--m2-solar", "1", "--m3-solar", "1",
                      "--sma-inner-au", "1", "--sma-outer-au", "30")[1]
        by_per = _run("kozai-lidov", "--m1-solar", "1", "--m2-solar", "1", "--m3-solar", "1",
                      "--period-inner-yr", str(by_sma["period_inner_yr"]),
                      "--period-outer-yr", str(by_sma["period_outer_yr"]))[1]
        self.assertAlmostEqual(by_sma["timescale_years"], by_per["timescale_years"], places=3)

    def test_bad_input(self):
        self.assertEqual(_run("kozai-lidov", "--m1-solar", "1", "--m2-solar", "1", "--m3-solar", "1",
                              "--period-inner-yr", "1", "--period-outer-yr", "100",
                              "--ecc-outer", "1")[0], 1)
        # neither complete period nor complete sma pair -> exit 1 (core)
        self.assertEqual(_run("kozai-lidov", "--m1-solar", "1", "--m2-solar", "1", "--m3-solar", "1",
                              "--period-inner-yr", "1")[0], 1)
        self.assertEqual(_run("kozai-lidov", "--m1-solar", "1")[0], 2)


# ── D1 · relativistic-brachistochrone ─────────────────────────────────────────

class RelativisticBrachistochroneTest(unittest.TestCase):

    def test_alpha_cen_anchor(self):
        code, p, _ = _run("relativistic-brachistochrone", "--accel-g", "1", "--distance-ly", "4.37")
        self.assertEqual(code, 0)
        self.assertEqual(set(p), {"accel_g", "distance_ly", "coord_time_yr", "proper_time_yr",
                                  "peak_velocity_c", "peak_lorentz_factor"})
        self.assertAlmostEqual(p["coord_time_yr"], 6.0, delta=0.2)
        self.assertAlmostEqual(p["proper_time_yr"], 3.58, delta=0.2)
        self.assertAlmostEqual(p["peak_velocity_c"], 0.95, delta=0.02)
        self.assertLess(p["proper_time_yr"], p["coord_time_yr"])   # dilation near c

    def test_low_speed_matches_newtonian(self):
        # Tiny distance → coord ≈ proper ≈ Newtonian flip-burn 2√(D/a).
        p = _run("relativistic-brachistochrone", "--accel-g", "1", "--distance-ly", "1e-7")[1]
        self.assertLess(p["peak_velocity_c"], 0.01)
        self.assertAlmostEqual(p["coord_time_yr"], p["proper_time_yr"], places=6)
        newt = calculators.compute_travel_time_system_au(1.0, 1e-7 * 63241.077)
        # Profile 1 (continuous-to-halfway) is the Newtonian flip-burn.
        prof1_hours = newt["profiles"][0]["hours"]
        self.assertAlmostEqual(p["coord_time_yr"] * 8765.8128, prof1_hours, delta=prof1_hours * 0.01)

    def test_peak_velocity_always_sublight(self):
        for d in ("0.001", "100", "100000"):
            p = _run("relativistic-brachistochrone", "--accel-g", "1", "--distance-ly", d)[1]
            self.assertLess(p["peak_velocity_c"], 1.0)

    def test_bad_input(self):
        self.assertEqual(_run("relativistic-brachistochrone", "--accel-g", "0", "--distance-ly", "1")[0], 1)
        self.assertEqual(_run("relativistic-brachistochrone", "--accel-g", "1", "--distance-ly", "0")[0], 1)
        self.assertEqual(_run("relativistic-brachistochrone", "--accel-g", "1")[0], 2)


# ── circumbinary-hz --star1/--star2 (deferred-from-T1a SIMBAD-resolve mode) ───

class CircumbinaryStarModeTest(unittest.TestCase):
    """The --star mode needs network mocking, so exercise it in-process via the
    query handler; the mutual-exclusion exit codes are checked via subprocess."""

    def test_star_mode_parity_with_numeric(self):
        import query
        fake_simbad = {"main_id": "X", "designations": {}}
        fake_reg = {"temp": 5778.0, "bcLuminosity": 1.0}
        with mock.patch.object(query.databases, "compute_simbad_lookup",
                               return_value=fake_simbad), \
             mock.patch.object(query.regions, "compute_star_system_regions_from_simbad",
                               return_value=fake_reg):
            res = query._resolve_star_teff_lum("Alpha Cen A")
        self.assertEqual(res, {"teff": 5778.0, "lum": 1.0})
        # Resolved (teff,lum) feeds the same core fn as the numeric mode.
        self.assertEqual(
            equations.compute_circumbinary_hz(5778.0, 1.0, 5778.0, 1.0),
            equations.compute_circumbinary_hz(res["teff"], res["lum"], res["teff"], res["lum"]))

    def test_resolver_simbad_error_passthrough(self):
        import query
        with mock.patch.object(query.databases, "compute_simbad_lookup",
                               return_value={"error": "No results found"}):
            res = query._resolve_star_teff_lum("Nonexistent")
        self.assertIn("error", res)

    def test_numeric_mode_still_works(self):
        code, p, _ = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                          "--teff2", "5778", "--lum2", "1")
        self.assertEqual(code, 0)
        self.assertEqual(len(p["zones"]), 6)

    def test_both_modes_given_exit1(self):
        # P4.1: numeric+star both given is a handler validation failure → curated
        # {"error"} on stdout, exit 1 (was stderr/exit 2).
        code, payload, _ = _run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                                "--teff2", "5778", "--lum2", "1", "--star1", "Sun", "--star2", "Sun")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_incomplete_exit1(self):
        # P4.1: one star only, or partial numeric → incomplete → curated exit 1.
        code, payload, _ = _run("circumbinary-hz", "--star1", "Sun")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        self.assertEqual(_run("circumbinary-hz", "--teff1", "5778", "--lum1", "1",
                              "--teff2", "5778")[0], 1)


# ═══════════════════════════════════════════════════════════════════════════
# Phase T1c — census-filter presets (seeded throwaway DBs)
# ═══════════════════════════════════════════════════════════════════════════

class _SeededDbCase(unittest.TestCase):
    """Build a throwaway DB on disk, seed it, drive query.py against it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dbpath = pathlib.Path(self.tmpdir) / "t1c.db"
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = self.dbpath
            db._conn = None
            db._auto_seed = lambda conn: None      # skip static CSV seeding
            self._seed(db.get_conn())
            db.close_conn()
        finally:
            db._DB_PATH, db._conn, db._auto_seed = saved

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, conn):  # override
        pass

    def _env(self):
        return {"SPACE_APP_DB": str(self.dbpath), "PATH": os.environ.get("PATH", "")}

    def _q(self, *args):
        return _run(*args, env=self._env())


# ── T1c-1 · solar-analogs ─────────────────────────────────────────────────────

class SolarAnalogsTest(_SeededDbCase):

    def _seed(self, conn):
        conn.executemany(
            "INSERT INTO hypatia_cache (star_name, teff, logg, fe_h, distance_pc, light_years) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Twin Near",   5772.0, 4.44,  0.00, 10.0,  32.6),   # twin box, near
                ("Twin Far",    5780.0, 4.45,  0.05, 100.0, 326.0),  # twin box, far
                ("Analog Only", 5500.0, 4.50, -0.25, 12.0,  39.0),   # outside twin, inside analog
                ("Giant",       4800.0, 2.50,  0.10, 20.0,  65.0),   # outside both
            ],
        )
        # For the --gcns-distance join: a star_systems row carrying a Gaia id + its gcns_stars row.
        conn.execute(
            "INSERT INTO star_systems (star_name, designations, spectral_type, app_magnitude) "
            "VALUES (?, ?, ?, ?)", ("Twin Near", "Gaia DR3 12345", "G2V", 5.0))
        conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, dist_pc, light_years, in_gcns, in_simbad, "
            "distance_method, gcns_table) VALUES (12345, 9.9, 32.3, 1, 1, 'gcns_bayesian', 'main')")
        conn.commit()

    def test_twin_box_contract(self):
        code, p, _ = self._q("solar-analogs")
        self.assertEqual(code, 0)
        self.assertEqual(p["mode"], "twin")
        names = {s["star_name"] for s in p["stars"]}
        self.assertEqual(names, {"Twin Near", "Twin Far"})    # both in the tight box
        self.assertEqual(p["criteria"]["teff_tol"], 100.0)
        self.assertEqual(p["criteria"]["teff_center"], 5772.0)

    def test_population_caveat_field_present(self):
        p = self._q("solar-analogs")[1]
        self.assertEqual(p["population"]["source"], "hypatia_cache")
        self.assertEqual(p["population"]["total_in_cache"], 4)
        self.assertEqual(p["population"]["returned"], 2)
        self.assertIn("Hypatia", p["population"]["note"])

    def test_analog_box_is_wider(self):
        p = self._q("solar-analogs", "--mode", "analog")[1]
        names = {s["star_name"] for s in p["stars"]}
        self.assertEqual(names, {"Twin Near", "Twin Far", "Analog Only"})  # giant still out

    def test_ly_max_filters(self):
        p = self._q("solar-analogs", "--ly-max", "100")[1]
        self.assertEqual({s["star_name"] for s in p["stars"]}, {"Twin Near"})  # Twin Far at 326 ly out

    def test_teff_tol_override(self):
        p = self._q("solar-analogs", "--teff-tol", "5")[1]   # only |ΔTeff| ≤ 5
        self.assertEqual({s["star_name"] for s in p["stars"]}, {"Twin Near"})
        self.assertEqual(p["criteria"]["teff_tol"], 5.0)

    def test_gcns_distance_join(self):
        p = self._q("solar-analogs", "--gcns-distance")[1]
        by_name = {s["star_name"]: s for s in p["stars"]}
        self.assertAlmostEqual(by_name["Twin Near"]["dist_pc_gcns"], 9.9, places=6)
        self.assertIsNone(by_name["Twin Far"]["dist_pc_gcns"])      # no star_systems row
        self.assertEqual(p["population"]["gcns_distance_matched"], 1)

    def test_no_gcns_distance_by_default(self):
        p = self._q("solar-analogs")[1]
        self.assertIsNone(p["population"]["gcns_distance_matched"])
        self.assertNotIn("dist_pc_gcns", p["stars"][0])

    def test_bad_tol_exit1(self):
        self.assertEqual(self._q("solar-analogs", "--teff-tol", "0")[0], 1)
        self.assertEqual(self._q("solar-analogs", "--ly-max", "-5")[0], 1)

    def test_bad_mode_exit2(self):
        self.assertEqual(self._q("solar-analogs", "--mode", "giant")[0], 2)
        self.assertEqual(self._q("solar-analogs", "--teff-tol", "x")[0], 2)


class SolarAnalogsEmptyTest(_SeededDbCase):
    def _seed(self, conn):
        pass  # leave hypatia_cache empty

    def test_empty_cache_exit1(self):
        code, p, _ = self._q("solar-analogs")
        self.assertEqual(code, 1)
        self.assertIn("hypatia_cache", p["error"])


# ── T1c-2 · substellar ────────────────────────────────────────────────────────

class SubstellarCensusTest(_SeededDbCase):

    def _seed(self, conn):
        conn.executemany(
            "INSERT INTO gcns_stars (gaia_source_id, spectral_type, light_years, in_gcns, "
            "in_simbad, distance_method, gcns_table) VALUES (?, ?, ?, 1, 1, 'gcns_bayesian', 'main')",
            [
                (1, "L5V", 8.0),    # L dwarf
                (2, "T2",  30.0),   # T dwarf
                (3, "M5V", 12.0),   # ordinary M (not substellar)
                (4, "M8V", 15.0),   # late-M (M/L boundary)
                (5, None,  5.0),    # untyped — excluded (spectral_type IS NOT NULL)
            ],
        )
        conn.commit()

    def test_default_lty_contract(self):
        code, p, _ = self._q("substellar")
        self.assertEqual(code, 0)
        self.assertEqual([s["gaia_source_id"] for s in p["stars"]], [1, 2])  # ly ASC
        self.assertEqual(p["classes"], ["L", "T", "Y"])

    def test_completeness_note_present(self):
        p = self._q("substellar")[1]
        self.assertIn("completeness_note", p)
        self.assertIn("lower bound", p["completeness_note"])
        self.assertEqual(p["population"]["total_in_gcns"], 5)
        self.assertEqual(p["population"]["with_spectral_type"], 4)   # row 5 untyped

    def test_ly_max_filters(self):
        p = self._q("substellar", "--ly-max", "20")[1]
        self.assertEqual([s["gaia_source_id"] for s in p["stars"]], [1])  # T2 at 30 ly out

    def test_include_late_m(self):
        p = self._q("substellar", "--include-late-m")[1]
        self.assertEqual({s["gaia_source_id"] for s in p["stars"]}, {1, 2, 4})  # +M8V, not M5V
        self.assertIn("M8", p["classes"])

    def test_classes_override(self):
        p = self._q("substellar", "--classes", "M")[1]
        self.assertEqual({s["gaia_source_id"] for s in p["stars"]}, {3, 4})  # all M types

    def test_bad_ly_exit1(self):
        self.assertEqual(self._q("substellar", "--ly-max", "-1")[0], 1)

    def test_non_numeric_ly_exit2(self):
        self.assertEqual(self._q("substellar", "--ly-max", "abc")[0], 2)


class SubstellarEmptyTest(_SeededDbCase):
    def _seed(self, conn):
        pass  # leave gcns_stars empty

    def test_empty_gcns_exit1(self):
        code, p, _ = self._q("substellar")
        self.assertEqual(code, 1)
        self.assertIn("gcns_stars", p["error"])


if __name__ == "__main__":
    unittest.main()
