# tests/test_query_strategic_geography.py — Phase AQ (Group T) query.py contract.
#
# Subprocess tests for network-centrality (T1) and arrival-corridors (T2). Both read the star
# catalog, so a throwaway star_systems DB is seeded on disk in setUp and passed to query.py via
# SPACE_APP_DB (the tests/test_query_route_opts.py::_SeededQueryTest pattern) — the subprocess never
# hits the network. Locks the happy-path JSON contract, the curated-error/exit-1 path, and the
# argparse exit-2 matrix.

import math
import os
import pathlib
import shutil
import tempfile
import unittest

import core.db as db
from tests._dustcheck import heavy_dust_enabled
from tests._queryharness import run_query


def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


def _radec_for_xyz(x, y, z):
    ly = math.sqrt(x * x + y * y + z * z)
    dec = math.degrees(math.asin(z / ly)) if ly else 0.0
    ra = math.degrees(math.atan2(y, x)) % 360.0
    rah = ra / 15.0
    h = int(rah); m = int((rah - h) * 60); s = ((rah - h) * 60 - m) * 60
    ad = abs(dec); dd = int(ad); dm = int((ad - dd) * 60); ds = ((ad - dd) * 60 - dm) * 60
    return (f"{h:02d} {m:02d} {s:08.4f}",
            f"{'-' if dec < 0 else '+'}{dd:02d} {dm:02d} {ds:07.4f}", ly)


class _SeededQueryTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "q.db")
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = pathlib.Path(self.db_path)
            db._conn = None
            db._auto_seed = lambda conn: None
            conn = db.get_conn()
            rows = []
            # chain A(10)-B(13)-C(16)-D(19) for T1; three 90° origins for T2.
            for nm, x, y, z in (("A", 10.0, 0.0, 0.0), ("B", 13.0, 0.0, 0.0),
                                ("C", 16.0, 0.0, 0.0), ("D", 19.0, 0.0, 0.0),
                                ("O1", 4.0, 0.0, 0.0), ("O2", 0.0, 4.0, 0.0),
                                ("O3", 0.0, 0.0, 4.0)):
                ra, dec, ly = _radec_for_xyz(x, y, z)
                rows.append((nm, f"NAME {nm}", "G2V", _plx_for_ly(ly), ly, ra, dec))
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
        return run_query(*cmd_args, db_path=self.db_path)


class NetworkCentralityQueryTest(_SeededQueryTest):
    def test_chain_happy(self):
        rc, d, _ = self._run("network-centrality", "--stars", "A", "B", "C", "D",
                             "--max-jump", "3.1", "--from", "A", "--to", "D")
        self.assertEqual(rc, 0)
        self.assertEqual(d["articulation_points"], ["B", "C"])
        self.assertEqual(d["bridges"], [["A", "B"], ["B", "C"], ["C", "D"]])
        self.assertEqual(d["graph"]["n_edges"], 3)
        self.assertTrue(d["graph"]["connected"])
        self.assertEqual(d["min_cut"]["value"], 1)
        betw = {n["name"]: n["betweenness"] for n in d["nodes"]}
        self.assertEqual(betw["B"], 2.0)

    def test_within_ly_happy(self):
        rc, d, _ = self._run("network-centrality", "--within-ly", "25", "--of", "Sol",
                             "--max-jump", "3.1")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(d["graph"]["n_nodes"], 4)

    def test_curated_error_exit_1(self):
        rc, d, _ = self._run("network-centrality", "--stars", "A", "B", "--max-jump", "0")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_argparse_exit_2(self):
        rc, _d, _ = self._run("network-centrality", "--stars", "A", "B")   # no --max-jump
        self.assertEqual(rc, 2)

    @unittest.skipUnless(
        heavy_dust_enabled(),
        "opt-in only: set SPACE_APP_RUN_HEAVY_DUST=1 (loads the multi-GB dust map — kept out of "
        "routine sweeps so an 8 GB WSL box doesn't OOM; the dust logic is covered offline by "
        "test_strategic_geography.py::DustWeightTest)")
    def test_weight_dust_happy(self):
        # Guards the --weight dust / --map / --dust-step-pc wiring end-to-end (real map integration).
        rc, d, _ = self._run("network-centrality", "--stars", "A", "B", "C", "D",
                             "--max-jump", "3.1", "--weight", "dust", "--map", "auto")
        self.assertEqual(rc, 0)
        self.assertEqual(d["weight"], "dust")
        self.assertEqual(d["dust_map"], "auto")
        self.assertEqual(d["articulation_points"], ["B", "C"])   # topology unchanged by the weight


class ArrivalCorridorsQueryTest(_SeededQueryTest):
    def test_three_origins_happy(self):
        rc, d, _ = self._run("arrival-corridors", "--system", "Sol",
                             "--origins", "O1", "O2", "O3",
                             "--corridor-halfwidth-deg", "5", "--cluster-deg", "5")
        self.assertEqual(rc, 0)
        self.assertEqual(d["n_distinct_corridors"], 3)
        self.assertAlmostEqual(d["angular_coverage_fraction"], 0.005707952862, places=7)

    def test_within_ly_happy(self):
        rc, d, _ = self._run("arrival-corridors", "--system", "Sol", "--within-ly", "10")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(d["n_origins"], 3)

    def test_curated_error_exit_1(self):
        rc, d, _ = self._run("arrival-corridors", "--system", "Sol", "--within-ly", "10",
                             "--corridor-halfwidth-deg", "0")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_argparse_exit_2(self):
        rc, _d, _ = self._run("arrival-corridors", "--system", "Sol")   # no origin selector
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
