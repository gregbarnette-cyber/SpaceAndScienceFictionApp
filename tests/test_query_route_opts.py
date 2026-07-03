# tests/test_query_route_opts.py — Phase I-OPTS query.py subcommand contracts.
#
# Three new subcommands (optimal-tour, jump-route, jump-network) wrap the
# self-validating compute_optimal_tour / compute_jump_route / compute_jump_network.
# These tests lock the happy-path JSON contracts, the curated-error/exit-1 path
# (out-of-range numerics), and the argparse exit-2 matrix. All endpoints use
# "Sol" + seeded star_systems rows so the subprocess never hits the network.
#
# Pattern mirrors tests/test_query_phase_n.py / test_gcns.py::GcnsQueryCliTest:
# a throwaway DB is seeded in setUp, then passed to query.py via SPACE_APP_DB.

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path

import core.db as db

_REPO = Path(__file__).resolve().parent.parent


def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


class _SeededQueryTest(unittest.TestCase):
    """Seed a tmp star_systems DB on disk, then drive query.py against it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "q.db")
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = pathlib.Path(self.db_path)
            db._conn = None
            db._auto_seed = lambda conn: None
            conn = db.get_conn()
            rows = [
                ("AX3", "NAME AX3", "M3V", _plx_for_ly(3.0), 3.0, "00 00 00", "+00 00 00"),
                ("AX5", "NAME AX5", "K2V", _plx_for_ly(5.0), 5.0, "00 00 00", "+00 00 00"),
                ("AX8", "NAME AX8", "G5V", _plx_for_ly(8.0), 8.0, "00 00 00", "+00 00 00"),
                ("BY5", "NAME BY5", "F5V", _plx_for_ly(5.0), 5.0, "06 00 00", "+00 00 00"),
            ]
            conn.executemany(
                "INSERT INTO star_systems (star_name, designations, spectral_type, "
                "parallax, light_years, ra, dec) VALUES (?,?,?,?,?,?,?)", rows)
            conn.commit()
            db.close_conn()
        finally:
            db._DB_PATH, db._conn, db._auto_seed = saved

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, *cmd_args):
        proc = subprocess.run(
            [sys.executable, str(_REPO / "query.py"), *cmd_args],
            capture_output=True, text=True, cwd=str(_REPO),
            env={"SPACE_APP_DB": self.db_path, "PATH": os.environ.get("PATH", "")},
        )
        try:
            payload = json.loads(proc.stdout)
        except Exception:
            payload = None
        return proc.returncode, payload, proc.stderr

    # ── optimal-tour ─────────────────────────────────────────────────────────

    def test_optimal_tour_happy(self):
        code, payload, _ = self._run("optimal-tour", "--stars", "Sol", "AX8",
                                     "AX3", "AX5", "--ly-hr", "0.01")
        self.assertEqual(code, 0)
        self.assertIn("optimized_total_ly", payload)
        self.assertAlmostEqual(payload["optimized_total_ly"], 8.0, places=3)
        self.assertEqual([s["name"] for s in payload["stars"]],
                         ["Sol", "AX3", "AX5", "AX8"])

    def test_optimal_tour_times_c_parity(self):
        code, p_c, _ = self._run("optimal-tour", "--stars", "Sol", "AX5",
                                 "--times-c", "100")
        self.assertEqual(code, 0)
        # times_c=100 ⇒ ly_hr = 100 / 8765.8128.
        self.assertAlmostEqual(p_c["legs"][0]["times_c"], 100.0, places=3)

    def test_optimal_tour_closed(self):
        code, payload, _ = self._run("optimal-tour", "--stars", "Sol", "AX3",
                                     "AX5", "AX8", "--ly-hr", "0.01", "--closed")
        self.assertEqual(code, 0)
        self.assertTrue(payload["closed"])
        self.assertAlmostEqual(payload["total_ly"], 16.0, places=3)

    def test_optimal_tour_both_velocity_exit2(self):
        code, _, stderr = self._run("optimal-tour", "--stars", "Sol", "AX5",
                                    "--ly-hr", "1", "--times-c", "1")
        self.assertEqual(code, 2)
        self.assertTrue(stderr)

    def test_optimal_tour_fewer_than_two_exit1(self):
        code, payload, _ = self._run("optimal-tour", "--stars", "Sol",
                                     "--ly-hr", "1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    # ── jump-route ───────────────────────────────────────────────────────────

    def test_jump_route_reachable(self):
        code, payload, _ = self._run("jump-route", "--origin", "Sol",
                                     "--destination", "AX8", "--max-jump", "4")
        self.assertEqual(code, 0)
        self.assertTrue(payload["reachable"])
        self.assertEqual(payload["jumps"], 3)

    def test_jump_route_unreachable_exit0(self):
        code, payload, _ = self._run("jump-route", "--origin", "Sol",
                                     "--destination", "AX8", "--max-jump", "2")
        self.assertEqual(code, 0)            # unreachable is a normal result
        self.assertFalse(payload["reachable"])

    def test_jump_route_bad_max_jump_exit1(self):
        code, payload, _ = self._run("jump-route", "--origin", "Sol",
                                     "--destination", "AX3", "--max-jump", "-1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_jump_route_bad_optimize_exit2(self):
        code, _, stderr = self._run("jump-route", "--origin", "Sol",
                                    "--destination", "AX3", "--max-jump", "4",
                                    "--optimize", "bogus")
        self.assertEqual(code, 2)            # argparse choices rejection
        self.assertTrue(stderr)

    def test_jump_route_missing_max_jump_exit2(self):
        code, _, stderr = self._run("jump-route", "--origin", "Sol",
                                    "--destination", "AX3")
        self.assertEqual(code, 2)

    # ── jump-route --weight blend (C11, Phase AD) ─────────────────────────────
    # The blended-cost route itself needs the dust extra + fetched maps (exercised
    # in-process with a mocked _seg in test_dust_routing.py); here we cover the two
    # weight-flag guards that are pure argparse/handler (no dust needed).

    def test_jump_route_alpha_without_blend_exit1(self):
        code, payload, _ = self._run("jump-route", "--origin", "Sol",
                                     "--destination", "AX3", "--max-jump", "4", "--alpha", "2")
        self.assertEqual(code, 1)               # handler guard: α/β require --weight blend
        self.assertIn("error", payload)

    def test_jump_route_bad_weight_exit2(self):
        code, _, stderr = self._run("jump-route", "--origin", "Sol",
                                    "--destination", "AX3", "--max-jump", "4",
                                    "--weight", "bogus")
        self.assertEqual(code, 2)               # argparse choices rejection
        self.assertTrue(stderr)

    # ── jump-network ─────────────────────────────────────────────────────────

    def test_jump_network_happy(self):
        code, payload, _ = self._run("jump-network", "--start", "Sol", "--max-jump", "4")
        self.assertEqual(code, 0)
        self.assertEqual(payload["max_tier"], 3)
        self.assertEqual(payload["unreachable_count"], 1)

    def test_jump_network_max_jumps_cap(self):
        code, payload, _ = self._run("jump-network", "--start", "Sol",
                                     "--max-jump", "4", "--max-jumps", "1")
        self.assertEqual(code, 0)
        self.assertEqual(payload["max_tier"], 1)

    def test_jump_network_bad_max_jump_exit1(self):
        code, payload, _ = self._run("jump-network", "--start", "Sol", "--max-jump", "-1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    # ── multi-stop (I1) ──────────────────────────────────────────────────────

    def test_multi_stop_happy(self):
        code, payload, _ = self._run("multi-stop", "--stars", "Sol", "AX5", "AX8",
                                     "--ly-hr", "0.01")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["legs"]), 2)
        self.assertAlmostEqual(payload["total_ly"], 5.0 + 3.0, places=3)  # 5 + 5→8

    def test_multi_stop_fewer_than_two_exit1(self):
        code, payload, _ = self._run("multi-stop", "--stars", "Sol", "--ly-hr", "1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_multi_stop_both_velocity_exit2(self):
        code, _, stderr = self._run("multi-stop", "--stars", "Sol", "AX5",
                                    "--ly-hr", "1", "--times-c", "1")
        self.assertEqual(code, 2)
        self.assertTrue(stderr)

    # ── nearest-neighbor (I2) ────────────────────────────────────────────────

    def test_nearest_neighbor_happy(self):
        code, payload, _ = self._run("nearest-neighbor", "--start", "Sol",
                                     "--hops", "3", "--max-ly", "100")
        self.assertEqual(code, 0)
        self.assertEqual([c["star_name"] for c in payload["chain"]],
                         ["AX3", "AX5", "AX8"])

    def test_nearest_neighbor_bad_hops_exit1(self):
        code, payload, _ = self._run("nearest-neighbor", "--start", "Sol",
                                     "--hops", "0", "--max-ly", "5")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_nearest_neighbor_non_int_hops_exit2(self):
        code, _, stderr = self._run("nearest-neighbor", "--start", "Sol",
                                    "--hops", "abc", "--max-ly", "5")
        self.assertEqual(code, 2)

    # ── farthest-first (D) ───────────────────────────────────────────────────

    def test_farthest_first_happy(self):
        code, payload, _ = self._run("farthest-first", "--start", "Sol", "--stops", "1")
        self.assertEqual(code, 0)
        self.assertEqual(payload["chain"][0]["star_name"], "AX8")  # farthest first

    def test_farthest_first_bad_stops_exit1(self):
        code, payload, _ = self._run("farthest-first", "--start", "Sol", "--stops", "0")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    # ── trade-route (I3) ─────────────────────────────────────────────────────

    def test_trade_route_happy(self):
        code, payload, _ = self._run("trade-route", "--stars", "Sol", "AX3", "AX5", "AX8")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["edges"]), 3)
        self.assertAlmostEqual(payload["total_ly"], 8.0, places=3)

    def test_trade_route_fewer_than_two_exit1(self):
        code, payload, _ = self._run("trade-route", "--stars", "Sol")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
