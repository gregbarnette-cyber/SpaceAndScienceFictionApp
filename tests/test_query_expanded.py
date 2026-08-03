# tests/test_query_expanded.py — query.py expansion: Search & Filter (G1/G2/G3),
# reference-data, and planetary/rotating-habitat equation subcommands.
#
# Offline subprocess contracts against a throwaway SPACE_APP_DB seeded once
# (class-level — all these subcommands are read-only): reference tables auto-seed
# from the CSVs, star_systems gets a few rows, and hwc is imported from hwc.csv.
# The two network-bound subcommands (search-exoplanets live NASA TAP,
# travel-time-custom-thrust live JPL Horizons) are gated on host reachability and
# otherwise only have their argparse contracts checked.

import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import core.db as db
import core.databases as databases

from tests._netcheck import live_enabled
from tests._queryharness import run_query

_REPO = Path(__file__).resolve().parent.parent


def _reachable(host, port=443, timeout=3.0):
    # Opt-in: the NASA/JPL live query-subprocess tests skip unless SPACE_APP_RUN_LIVE=1
    # (see tests/_netcheck.live_enabled) so a routine `pytest -q` opens no network socket.
    if not live_enabled():
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


class _ExpandedQueryTest(unittest.TestCase):
    """Class-level throwaway DB: auto-seeded reference tables + seeded
    star_systems + imported hwc. All subcommands under test are read-only."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmpdir, "q.db")
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = pathlib.Path(cls.db_path)
            db._conn = None
            conn = db.get_conn()                 # auto-seeds reference tables
            rows = [
                ("AX3", "NAME AX3", "M3V", _plx_for_ly(3.0), 3.0, "00 00 00", "+00 00 00", 8.1),
                ("AX5", "NAME AX5", "K2V", _plx_for_ly(5.0), 5.0, "00 00 00", "+00 00 00", 6.2),
                ("BY9", "NAME BY9", "G5V", _plx_for_ly(9.0), 9.0, "06 00 00", "+00 00 00", 4.3),
            ]
            conn.executemany(
                "INSERT INTO star_systems (star_name, designations, spectral_type, "
                "parallax, light_years, ra, dec, app_magnitude) VALUES (?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            hwc_csv = _REPO / "hwc.csv"
            if hwc_csv.exists():
                databases.import_hwc_csv(str(hwc_csv))
                cls.has_hwc = True
            else:
                cls.has_hwc = False
            db.close_conn()
        finally:
            db._DB_PATH, db._conn, db._auto_seed = saved

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _run(self, *cmd_args):
        return run_query(*cmd_args, db_path=self.db_path)

    # ── Tier 1: Search & Filter ──────────────────────────────────────────────

    def test_search_star_systems_happy(self):
        code, payload, _ = self._run("search-star-systems", "--spectral-classes", "M", "K")
        self.assertEqual(code, 0)
        self.assertIn("count", payload)
        names = {s["star_name"] for s in payload["stars"]}
        self.assertIn("AX3", names)   # M3V
        self.assertIn("AX5", names)   # K2V
        self.assertNotIn("BY9", names)  # G5V excluded

    def test_search_star_systems_ly_filter(self):
        code, payload, _ = self._run("search-star-systems", "--ly-max", "4")
        self.assertEqual(code, 0)
        self.assertEqual({s["star_name"] for s in payload["stars"]}, {"AX3"})

    def test_search_star_systems_no_filters_returns_all(self):
        code, payload, _ = self._run("search-star-systems")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(payload["count"], 3)

    def test_search_hwc_happy(self):
        if not self.has_hwc:
            self.skipTest("hwc.csv not present")
        code, payload, _ = self._run("search-hwc", "--habitable")
        self.assertEqual(code, 0)
        self.assertIn("count", payload)

    def test_search_exoplanets_offline_argparse(self):
        # No live call here — just confirm the parser accepts the flags (a bad
        # numeric is rejected with exit 2 before any network).
        code, _, _ = self._run("search-exoplanets", "--mass-min", "not-a-number")
        self.assertEqual(code, 2)

    @unittest.skipUnless(_reachable("exoplanetarchive.ipac.caltech.edu"),
                         "NASA Exoplanet Archive unreachable")
    def test_search_exoplanets_live(self):
        code, payload, _ = self._run("search-exoplanets", "--radius-min", "0.5",
                                     "--radius-max", "1.5", "--dist-max-pc", "10")
        self.assertEqual(code, 0)
        self.assertIn("count", payload)

    # ── Tier 2: Reference data ───────────────────────────────────────────────

    def test_main_sequence(self):
        code, payload, _ = self._run("main-sequence")
        self.assertEqual(code, 0)
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 24)

    def test_solar_system(self):
        code, payload, _ = self._run("solar-system")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"planets", "moons", "dwarf_planets", "asteroids"})
        self.assertEqual(len(payload["planets"]), 8)

    def test_sol_regions(self):
        code, payload, _ = self._run("sol-regions")
        self.assertEqual(code, 0)
        self.assertIn("hzil", payload)
        self.assertIn("snowLine", payload)

    # ── Tier 3: planetary / rotating-habitat equations ───────────────────────

    def test_orbit_distance(self):
        code, payload, _ = self._run("orbit-distance", "--sma", "1.0", "--ecc", "0.0")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(payload["periastron"], 1.0, places=6)
        self.assertAlmostEqual(payload["apastron"], 1.0, places=6)

    def test_moon_orbital_distance(self):
        code, payload, _ = self._run("moon-orbital-distance",
                                     "--planet-mass-earth", "1.0", "--day-hours", "24")
        self.assertEqual(code, 0)
        self.assertTrue(any("rbital" in k or "istance" in k for k in payload))

    def test_gravity_roundtrip(self):
        # rpm 2 + radius 224 → accel; then gravity-rpm with that accel + radius → ~2 rpm.
        code, acc, _ = self._run("gravity-acceleration", "--rpm", "2", "--radius-m", "224")
        self.assertEqual(code, 0)
        a = next(v for k, v in acc.items() if isinstance(v, (int, float))
                 and "gravity" in k.lower() or "accel" in k.lower())
        code, rpm, _ = self._run("gravity-rpm", "--accel-ms2", str(a), "--radius-m", "224")
        self.assertEqual(code, 0)
        r = next(v for k, v in rpm.items() if "rpm" in k.lower())
        self.assertAlmostEqual(r, 2.0, places=3)

    def test_gravity_missing_arg_exit2(self):
        code, _, stderr = self._run("gravity-rpm", "--accel-ms2", "9.81")
        self.assertEqual(code, 2)
        self.assertTrue(stderr)

    def test_orbit_missing_arg_exit2(self):
        code, _, _ = self._run("orbit-distance", "--sma", "1.0")
        self.assertEqual(code, 2)

    # ── travel-time-custom-thrust (live JPL Horizons) ────────────────────────

    def test_custom_thrust_missing_arg_exit2(self):
        code, _, _ = self._run("travel-time-custom-thrust", "--origin", "Earth",
                               "--destination", "Mars", "--accel-g", "1.0")
        self.assertEqual(code, 2)   # missing --burn-value

    @unittest.skipUnless(_reachable("ssd.jpl.nasa.gov"), "JPL Horizons unreachable")
    def test_custom_thrust_live(self):
        code, payload, _ = self._run("travel-time-custom-thrust", "--origin", "Earth",
                                     "--destination", "Mars", "--accel-g", "1.0",
                                     "--burn-value", "2", "--burn-unit", "D")
        self.assertEqual(code, 0)
        self.assertIn("travel_time_str", payload)


if __name__ == "__main__":
    unittest.main()
