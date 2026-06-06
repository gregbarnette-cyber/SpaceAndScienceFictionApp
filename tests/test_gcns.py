# tests/test_gcns.py — offline unittest coverage for the GCNS ingest + query path.
#
# The TAP network fetch is mocked (core.databases._gcns_fetch is replaced), so
# these tests never hit GAVO. They exercise: the kpc->pc + light-year transform,
# the SIMBAD cross-match keys (Gaia source_id / 2MASS / name), the missing_10mas
# plx-inversion branch, the two check gates (validate-before-destroy), the
# gcns-within-sol / gcns-source read functions + their query.py contract, the
# opt-50 Gaia DR3 designation parser, and the DB-status listing.

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.databases as databases

_REPO = pathlib.Path(__file__).resolve().parent.parent


class FakeResult(list):
    """Stand-in for a pyvo TAPResults: a list of row dicts + a query_status."""

    def __init__(self, rows, query_status="OK"):
        super().__init__(rows)
        self.query_status = query_status


def _main_row(source_id, name_2mass=None, dist_50_kpc=0.001, **over):
    row = {
        "source_id": source_id,
        "ra": 217.0, "dec": -62.0,
        "parallax": 768.0, "parallax_error": 0.05,
        "dist_16": dist_50_kpc * 0.99, "dist_50": dist_50_kpc, "dist_84": dist_50_kpc * 1.01,
        "phot_g_mean_mag": 9.0, "phot_bp_mean_mag": 10.0, "phot_rp_mean_mag": 8.0,
        "adoptedrv": -22.4, "wd_prob": 0.01, "gcns_prob": 1.0,
        "name_2mass": name_2mass,
    }
    row.update(over)
    return row


def _miss_row(main_id, plx_value=743.0, **over):
    row = {"main_id": main_id, "otype": "SB", "ra": 219.9, "dec": -60.8, "plx_value": plx_value}
    row.update(over)
    return row


def _patch_fetch(main_rows, miss_rows, main_status="OK", miss_status="OK"):
    """Return a mock.patch context manager replacing databases._gcns_fetch."""
    def _fetch(adql, maxrec):
        if "missing_10mas" in adql:
            return FakeResult(miss_rows, miss_status)
        return FakeResult(main_rows, main_status)
    return mock.patch.object(databases, "_gcns_fetch", _fetch)


# ── pure parsing / normalisation (no DB) ─────────────────────────────────────

class GcnsParseTest(unittest.TestCase):

    def test_norm_2mass(self):
        cases = [
            ("2MASS J14294291-6240465", "14294291-6240465"),
            ("2MASS 14294291-6240465",  "14294291-6240465"),
            ("14294291-6240465",        "14294291-6240465"),
            ("J10562886+0700527",       "10562886+0700527"),
            ("", ""),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(databases._norm_2mass(raw), expected)

    def test_opt50_parser_captures_gaia_dr3_not_dr2(self):
        """SIMBAD's `ids` labels the Gaia source 'Gaia DR3 <id>' (not 'Gaia EDR3').
        The opt-50 designation parser must capture DR3 (so the GCNS cross-match key
        lands in star_systems) and must NOT capture DR1/DR2 (different source_ids).
        """
        ids = ("GJ 551|HIP 70890|Gaia DR1 111|Gaia DR2 222|"
               "Gaia DR3 5853498713190525696|2MASS J14294291-6240465")
        out = databases._parse_designations_from_ids(ids)
        self.assertIn("Gaia DR3 5853498713190525696", out)
        self.assertNotIn("Gaia DR2", out)
        self.assertNotIn("Gaia DR1", out)
        import re
        m = re.search(r"Gaia\s+E?DR3\s+(\d+)", out)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "5853498713190525696")


# ── DB-backed tests (isolated temp SQLite) ───────────────────────────────────

class GcnsDBTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None        # skip static CSV seeding
        self.conn = db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_star_systems(self, rows):
        self.conn.executemany(
            "INSERT INTO star_systems (star_name, designations, spectral_type, app_magnitude) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def _seed_gcns(self, rows):
        # rows: (source_id, ra, dec, light_years, dist_pc)
        self.conn.executemany(
            "INSERT INTO gcns_stars (gaia_source_id, ra, dec, light_years, dist_pc, "
            "in_gcns, in_simbad, distance_method, gcns_table) "
            "VALUES (?, ?, ?, ?, ?, 1, 0, 'gcns_bayesian', 'main')",
            rows,
        )
        self.conn.commit()

    # ── ingest happy path: transform + cross-match ───────────────────────────

    def test_ingest_transform_and_crossmatch(self):
        self._seed_star_systems([
            ("Test B", "Gaia DR3 999",            "G2V", 5.0),    # match main by source_id
            ("Test A", "2MASS J10562886+0700527", "M8V", 12.3),   # match main by 2MASS
            ("* alf Cen A", "GJ 559 A, HD 128620", "G2V", -0.01), # match missing by name
        ])
        main_rows = [
            _main_row(999, name_2mass=None,               dist_50_kpc=0.001),  # -> 1.0 pc
            _main_row(111, name_2mass="10562886+0700527", dist_50_kpc=0.002),  # -> 2.0 pc
            _main_row(222, name_2mass=None,               dist_50_kpc=0.05),   # unmatched
        ]
        miss_rows = [_miss_row("* alf Cen A", plx_value=743.0)]

        with mock.patch.object(databases, "_GCNS_MAIN_MIN_ROWS", 1), \
             mock.patch.object(databases, "_GCNS_MISSING_MIN_ROWS", 1), \
             _patch_fetch(main_rows, miss_rows):
            res = databases.compute_gcns_ingest()

        self.assertNotIn("error", res)
        self.assertEqual(res["main_count"], 3)
        self.assertEqual(res["missing_count"], 1)
        self.assertEqual(res["total_rows"], 4)
        self.assertEqual(res["simbad_matched"], 3)
        self.assertTrue(res["snapshot_date"])

        r999 = databases.compute_gcns_by_source_id(999)["star"]
        self.assertIs(r999["in_simbad"], True)
        self.assertIs(r999["in_gcns"], True)
        self.assertEqual(r999["spectral_type"], "G2V")
        self.assertEqual(r999["star_name"], "Test B")
        self.assertEqual(r999["app_magnitude"], 5.0)
        self.assertEqual(r999["distance_method"], "gcns_bayesian")
        self.assertAlmostEqual(r999["dist_pc"], 1.0)               # 0.001 kpc * 1000
        self.assertAlmostEqual(r999["light_years"], 1.0 * 3.26156, places=5)
        self.assertEqual(r999["phot_g_mean_mag"], 9.0)             # Gaia G separate from V

        r111 = databases.compute_gcns_by_source_id(111)["star"]
        self.assertEqual(r111["spectral_type"], "M8V")            # matched via 2MASS fallback
        self.assertEqual(r111["star_name"], "Test A")

        r222 = databases.compute_gcns_by_source_id(222)["star"]
        self.assertIs(r222["in_simbad"], False)                   # unmatched -> no fabrication
        self.assertIsNone(r222["spectral_type"])
        self.assertIsNone(r222["star_name"])

        meta = databases._gcns_meta_dict()
        self.assertEqual(meta["total_count"], "4")
        self.assertEqual(meta["simbad_matched"], "3")
        self.assertIn("GCNS", meta["gcns_version"])

    def test_missing_10mas_plx_inversion(self):
        with mock.patch.object(databases, "_GCNS_MAIN_MIN_ROWS", 1), \
             mock.patch.object(databases, "_GCNS_MISSING_MIN_ROWS", 1), \
             _patch_fetch([_main_row(1, dist_50_kpc=0.01)],
                          [_miss_row("Luhman 16", plx_value=500.0)]):
            res = databases.compute_gcns_ingest()
        self.assertNotIn("error", res)

        out = databases.compute_gcns_within_sol(20.0)
        miss = [s for s in out["stars"] if s["gcns_table"] == "missing_10mas"]
        self.assertEqual(len(miss), 1)
        m = miss[0]
        self.assertIsNone(m["gaia_source_id"])
        self.assertEqual(m["distance_method"], "gcns_missing_plx_inversion")
        self.assertAlmostEqual(m["dist_pc"], 1000.0 / 500.0)       # 2.0 pc
        self.assertIsNone(m["dist_lo_pc"])
        self.assertIsNone(m["dist_hi_pc"])
        self.assertIsNone(m["phot_g_mean_mag"])
        self.assertEqual(m["star_name"], "Luhman 16")             # GCNS main_id kept as name

    # ── check gates (validate-before-destroy) ────────────────────────────────

    def test_gate1_too_few_rows_aborts_and_preserves(self):
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, light_years, in_gcns, in_simbad, "
            "distance_method, gcns_table) VALUES (42, 4.0, 1, 0, 'gcns_bayesian', 'main')"
        )
        self.conn.commit()
        # Default floors (330k) with only 2 rows -> Gate 1 fails before any DB write.
        with _patch_fetch([_main_row(1), _main_row(2)], [_miss_row("x")]):
            res = databases.compute_gcns_ingest()
        self.assertIn("error", res)
        self.assertIn("only", res["error"])
        self.assertIn("aborted", res["error"].lower())
        # Sentinel survived -> existing table left intact.
        n = self.conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
        self.assertEqual(n, 1)
        self.assertEqual(self.conn.execute("SELECT gaia_source_id FROM gcns_stars").fetchone()[0], 42)

    def test_gate1_overflow_aborts_and_preserves(self):
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, light_years, in_gcns, in_simbad, "
            "distance_method, gcns_table) VALUES (42, 4.0, 1, 0, 'gcns_bayesian', 'main')"
        )
        self.conn.commit()
        with mock.patch.object(databases, "_GCNS_MAIN_MIN_ROWS", 1), \
             mock.patch.object(databases, "_GCNS_MISSING_MIN_ROWS", 1), \
             _patch_fetch([_main_row(1), _main_row(2)], [_miss_row("x")], main_status="OVERFLOW"):
            res = databases.compute_gcns_ingest()
        self.assertIn("error", res)
        self.assertIn("truncated", res["error"].lower())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0], 1)

    # ── read functions ───────────────────────────────────────────────────────

    def test_within_sol_filters_orders_and_xyz(self):
        self._seed_gcns([
            (1, 0.0,   0.0,  4.0, 1.2),
            (2, 90.0,  0.0,  2.0, 0.6),
            (3, 0.0,   90.0, 9.0, 2.8),    # outside a 5 ly limit
            (4, 10.0,  10.0, None, None),  # null light_years -> excluded
        ])
        out = databases.compute_gcns_within_sol(5.0)
        self.assertEqual(out["count"], 2)
        self.assertEqual([s["light_years"] for s in out["stars"]], [2.0, 4.0])  # ascending
        s2 = out["stars"][0]
        self.assertAlmostEqual(s2["x"], 0.0, places=9)
        self.assertAlmostEqual(s2["y"], 2.0, places=9)

    def test_within_sol_bad_limit(self):
        self._seed_gcns([(1, 0.0, 0.0, 4.0, 1.2)])
        self.assertIn("error", databases.compute_gcns_within_sol(0))
        self.assertIn("error", databases.compute_gcns_within_sol(-3))

    def test_by_source_id_not_found(self):
        self._seed_gcns([(1, 0.0, 0.0, 4.0, 1.2)])
        self.assertIn("error", databases.compute_gcns_by_source_id(99999))
        found = databases.compute_gcns_by_source_id(1)
        self.assertEqual(found["star"]["gaia_source_id"], 1)

    def test_empty_table_errors(self):
        self.assertIn("error", databases.compute_gcns_within_sol(20))
        self.assertIn("error", databases.compute_gcns_by_source_id(1))

    def test_db_status_lists_gcns_tables(self):
        labels = [r["table"] for r in db.get_table_status()]
        self.assertIn("GCNS Stars", labels)
        self.assertIn("GCNS Meta", labels)


# ── query.py contract (subprocess, isolated DB via SPACE_APP_DB) ─────────────

class GcnsQueryCliTest(unittest.TestCase):

    def test_query_py_gcns_within_sol_empty_contract(self):
        """query.py emits valid JSON + exit 1 against an empty gcns_stars table."""
        tmpdir = tempfile.mkdtemp()
        try:
            proc = subprocess.run(
                [sys.executable, str(_REPO / "query.py"), "gcns-within-sol", "--ly", "20"],
                capture_output=True, text=True, cwd=str(_REPO),
                env={"SPACE_APP_DB": os.path.join(tmpdir, "q.db"),
                     "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertIn("error", payload)
            self.assertIn("gcns_stars", payload["error"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
