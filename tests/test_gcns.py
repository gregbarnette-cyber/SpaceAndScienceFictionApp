# tests/test_gcns.py — offline unittest coverage for the GCNS ingest + query path.
#
# The TAP network fetch is mocked (core.databases._gcns_fetch is replaced), so
# these tests never hit GAVO. They exercise: the kpc->pc + light-year transform,
# the SIMBAD cross-match keys (Gaia source_id / 2MASS / name), the missing_10mas
# plx-inversion branch, the two check gates (validate-before-destroy), the
# gcns-within-sol / gcns-source read functions + their query.py contract, the
# opt-50 Gaia DR3 designation parser, and the DB-status listing.

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


def _res_row(s1, s2, separation=2.0, mag_diff=0.5, proj_sep=10.0, bin=0, bound=1, **over):
    row = {"source_id1": s1, "source_id2": s2, "separation": separation,
           "mag_diff": mag_diff, "proj_sep": proj_sep, "bin": bin, "bound": bound}
    row.update(over)
    return row


def _patch_fetch(main_rows, miss_rows, resolved_rows=(),
                 main_status="OK", miss_status="OK", resolved_status="OK"):
    """Return a mock.patch context manager replacing databases._gcns_fetch."""
    def _fetch(adql, maxrec):
        if "missing_10mas" in adql:
            return FakeResult(miss_rows, miss_status)
        if "resolvedss" in adql:
            return FakeResult(list(resolved_rows), resolved_status)
        return FakeResult(main_rows, main_status)
    return mock.patch.object(databases, "_gcns_fetch", _fetch)


def _patch_floors(main=1, missing=1, resolved=1):
    """Patch all three row-count floors low so small fixtures pass Gate 1."""
    return (
        mock.patch.object(databases, "_GCNS_MAIN_MIN_ROWS", main),
        mock.patch.object(databases, "_GCNS_MISSING_MIN_ROWS", missing),
        mock.patch.object(databases, "_GCNS_RESOLVED_MIN_ROWS", resolved),
    )


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
        # 999+111 form a resolved binary; 222 is single (in no pair).
        res_rows = [_res_row(999, 111, proj_sep=42.0, bound=1)]

        f1, f2, f3 = _patch_floors()
        with f1, f2, f3, _patch_fetch(main_rows, miss_rows, res_rows):
            res = databases.compute_gcns_ingest()

        self.assertNotIn("error", res)
        self.assertEqual(res["main_count"], 3)
        self.assertEqual(res["missing_count"], 1)
        self.assertEqual(res["total_rows"], 4)
        self.assertEqual(res["simbad_matched"], 3)
        self.assertEqual(res["resolved_pairs"], 1)
        self.assertEqual(res["systems_count"], 1)
        self.assertEqual(res["members_in_stars"], 2)  # 999 + 111 both in gcns.main
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
        self.assertEqual(r999["n_components"], 2)                  # resolved-system enrich
        self.assertIsNotNone(r999["system_id"])

        r111 = databases.compute_gcns_by_source_id(111)["star"]
        self.assertEqual(r111["spectral_type"], "M8V")            # matched via 2MASS fallback
        self.assertEqual(r111["star_name"], "Test A")
        self.assertEqual(r111["system_id"], r999["system_id"])    # same system as 999

        r222 = databases.compute_gcns_by_source_id(222)["star"]
        self.assertIs(r222["in_simbad"], False)                   # unmatched -> no fabrication
        self.assertIsNone(r222["spectral_type"])
        self.assertIsNone(r222["star_name"])
        self.assertIsNone(r222["system_id"])                      # single -> not in a system
        self.assertIsNone(r222["n_components"])

        meta = databases._gcns_meta_dict()
        self.assertEqual(meta["total_count"], "4")
        self.assertEqual(meta["simbad_matched"], "3")
        self.assertEqual(meta["gcns_resolved_pairs"], "1")
        self.assertEqual(meta["gcns_systems_count"], "1")
        self.assertIn("GCNS", meta["gcns_version"])

    def test_missing_10mas_plx_inversion(self):
        f1, f2, f3 = _patch_floors()
        with f1, f2, f3, _patch_fetch([_main_row(1, dist_50_kpc=0.01)],
                                      [_miss_row("Luhman 16", plx_value=500.0)],
                                      [_res_row(1, 2)]):
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

    # ── resolved systems (connected components) ──────────────────────────────

    def test_systems_connected_components(self):
        """resolvedss is pair-keyed; systems = connected components over the pairs.

        A chain of pairs (A-B, B-C) collapses to one 3-component system; a member
        present in resolvedss but absent from gcns_stars is retained, flagged.
        """
        main_rows = [_main_row(sid, dist_50_kpc=0.01)
                     for sid in (10, 11, 12, 20, 21, 40, 30)]
        res_rows = [
            _res_row(10, 11), _res_row(11, 12),  # triple {10,11,12}
            _res_row(20, 21),                    # binary {20,21}
            _res_row(40, 99),                    # {40,99}; 99 not in gcns.main
        ]
        f1, f2, f3 = _patch_floors(missing=0)
        with f1, f2, f3, _patch_fetch(main_rows, [], res_rows):
            res = databases.compute_gcns_ingest()

        self.assertNotIn("error", res)
        self.assertEqual(res["resolved_pairs"], 4)
        self.assertEqual(res["systems_count"], 3)
        self.assertEqual(res["systems_multi"], 1)        # only the triple has >2
        self.assertEqual(res["members_in_stars"], 6)     # all but 99

        # Deterministic system_id: components ordered by smallest member id.
        triple = databases.compute_gcns_system(11)["system"]
        self.assertEqual(triple["system_id"], 1)
        self.assertEqual(triple["n_components"], 3)
        self.assertEqual(triple["n_pairs"], 2)
        self.assertEqual([m["gaia_source_id"] for m in triple["members"]],
                         [10, 11, 12])
        self.assertTrue(any(m["is_query"] for m in triple["members"]))

        # Member in resolvedss but not in gcns_stars is retained, flagged.
        sys99 = databases.compute_gcns_system(99)["system"]
        self.assertEqual(sorted(m["gaia_source_id"] for m in sys99["members"]),
                         [40, 99])
        m99 = next(m for m in sys99["members"] if m["gaia_source_id"] == 99)
        self.assertIs(m99["in_gcns_stars"], False)
        self.assertIsNone(m99["dist_pc"])                # no gcns_stars row to join
        m40 = next(m for m in sys99["members"] if m["gaia_source_id"] == 40)
        self.assertIs(m40["in_gcns_stars"], True)

        # A source in no pair is not part of any resolved system.
        self.assertIn("error", databases.compute_gcns_system(30))
        # A source absent from the catalogue entirely.
        self.assertIn("error", databases.compute_gcns_system(123456))

    def test_gate_resolvedss_too_few_aborts_and_preserves(self):
        """A short resolvedss download aborts before any write, preserving tables."""
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, light_years, in_gcns, in_simbad, "
            "distance_method, gcns_table) VALUES (7, 4.0, 1, 0, 'gcns_bayesian', 'main')"
        )
        self.conn.execute(
            "INSERT INTO gcns_systems (system_id, n_components, n_pairs) VALUES (1, 2, 1)"
        )
        self.conn.commit()
        # main/missing floors low so we reach the resolved gate; resolved floor default.
        with mock.patch.object(databases, "_GCNS_MAIN_MIN_ROWS", 1), \
             mock.patch.object(databases, "_GCNS_MISSING_MIN_ROWS", 1), \
             _patch_fetch([_main_row(1)], [_miss_row("x")], [_res_row(1, 2)]):
            res = databases.compute_gcns_ingest()
        self.assertIn("error", res)
        self.assertIn("resolvedss", res["error"])
        self.assertIn("aborted", res["error"].lower())
        # Sentinels survived -> existing tables left intact.
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM gcns_systems").fetchone()[0], 1)

    def test_gcns_system_empty_table_errors(self):
        self.assertIn("error", databases.compute_gcns_system(1))

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

    def test_query_py_gcns_system_empty_contract(self):
        """query.py gcns-system emits valid JSON + exit 1 against an empty DB."""
        tmpdir = tempfile.mkdtemp()
        try:
            proc = subprocess.run(
                [sys.executable, str(_REPO / "query.py"), "gcns-system", "--id", "42"],
                capture_output=True, text=True, cwd=str(_REPO),
                env={"SPACE_APP_DB": os.path.join(tmpdir, "q.db"),
                     "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertIn("error", payload)
            self.assertIn("gcns_systems", payload["error"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── GCNS-backed calculators (distance / travel-time / within-star) ───────────

class GcnsCalcTest(unittest.TestCase):
    """Offline coverage for compute_gcns_distance / _travel_time / _stars_within_star
    and the _resolve_gcns_row helper. The --star (SIMBAD) path is mocked."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _insert(self, **cols):
        """Insert one gcns_stars row; sensible defaults for the membership flags."""
        cols.setdefault("in_gcns", 1)
        cols.setdefault("in_simbad", 0)
        cols.setdefault("distance_method", "gcns_bayesian")
        cols.setdefault("gcns_table", "main")
        keys = list(cols)
        self.conn.execute(
            f"INSERT INTO gcns_stars ({', '.join(keys)}) "
            f"VALUES ({', '.join('?' for _ in keys)})",
            tuple(cols[k] for k in keys),
        )
        self.conn.commit()

    # ── distance ─────────────────────────────────────────────────────────────

    def test_distance_by_id_shape_and_provenance(self):
        self._insert(gaia_source_id=10, ra=0.0,  dec=0.0,  light_years=4.0, dist_pc=1.2,
                     dist_lo_pc=1.1, dist_hi_pc=1.3, spectral_type="M5V", star_name="A")
        self._insert(gaia_source_id=20, ra=90.0, dec=0.0,  light_years=4.0, dist_pc=1.2,
                     dist_lo_pc=1.1, dist_hi_pc=1.3, spectral_type="K2V", star_name="B")
        res = databases.compute_gcns_distance(id1=10, id2=20)
        self.assertNotIn("error", res)
        # (4,0,0) vs (0,4,0) -> sqrt(32) ly
        self.assertAlmostEqual(res["distance_ly"], math.sqrt(32), places=6)
        self.assertIsNone(res["distance_au"])          # > 0.5 ly
        self.assertTrue(res["gcns_version"] is None or isinstance(res["gcns_version"], str))
        s1 = res["star1_info"]
        self.assertEqual(s1["gaia_source_id"], 10)
        self.assertEqual(s1["dist_pc"], 1.2)
        self.assertEqual(s1["dist_lo_pc"], 1.1)
        self.assertEqual(s1["dist_hi_pc"], 1.3)
        self.assertEqual(s1["distance_method"], "gcns_bayesian")
        self.assertIn("ra_hms", s1)
        self.assertIn("dec_dms", s1)

    def test_distance_self_is_zero_and_au_set(self):
        self._insert(gaia_source_id=10, ra=12.3, dec=-45.6, light_years=4.0, dist_pc=1.2)
        res = databases.compute_gcns_distance(id1=10, id2=10)
        self.assertNotIn("error", res)
        self.assertAlmostEqual(res["distance_ly"], 0.0, places=9)
        self.assertIsNotNone(res["distance_au"])       # < 0.5 ly -> AU populated
        self.assertAlmostEqual(res["distance_au"], 0.0, places=6)

    def test_distance_missing_10mas_endpoint_no_crash(self):
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2,
                     dist_lo_pc=1.1, dist_hi_pc=1.3)
        # missing_10mas: NULL source_id, NULL lo/hi, resolvable only by name
        self._insert(gaia_source_id=None, ra=90.0, dec=0.0, light_years=4.0,
                     dist_pc=1.3, dist_lo_pc=None, dist_hi_pc=None,
                     star_name="alf Cen A", distance_method="gcns_missing_plx_inversion",
                     gcns_table="missing_10mas")
        res = databases.compute_gcns_distance(id1=10, star2="alf Cen A")
        self.assertNotIn("error", res)
        s2 = res["star2_info"]
        self.assertIsNone(s2["gaia_source_id"])
        self.assertIsNone(s2["dist_lo_pc"])
        self.assertIsNone(s2["dist_hi_pc"])
        self.assertEqual(s2["distance_method"], "gcns_missing_plx_inversion")

    def test_distance_not_in_gcns_errors(self):
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2)
        self.assertIn("error", databases.compute_gcns_distance(id1=10, id2=99999))

    # ── resolver ─────────────────────────────────────────────────────────────

    def test_resolve_by_id_not_found_propagates_without_keyerror(self):
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2)
        r = databases._resolve_gcns_row(source_id=99999)
        self.assertIn("error", r)               # no KeyError on ["star"]

    def test_resolve_requires_exactly_one(self):
        self.assertIn("error", databases._resolve_gcns_row())
        self.assertIn("error", databases._resolve_gcns_row(star="x", source_id=1))

    def test_resolve_ambiguous_name_errors_and_lists_candidates(self):
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2,
                     star_name="Twin")
        self._insert(gaia_source_id=11, ra=1.0, dec=1.0, light_years=4.1, dist_pc=1.25,
                     star_name="Twin")
        # SIMBAD resolves but yields no Gaia id -> falls through to the name match,
        # which finds two "Twin" rows -> ambiguity error.
        fake = {"designations": {"Gaia EDR3": None}}
        with mock.patch.object(databases, "compute_simbad_lookup", lambda n: fake):
            r = databases._resolve_gcns_row(star="Twin")
        self.assertIn("error", r)
        self.assertIn("ambiguous", r["error"].lower())
        self.assertIn("10", r["error"])
        self.assertIn("11", r["error"])

    def test_resolve_star_path_id_miss_falls_through_to_name(self):
        """SIMBAD yields a Gaia id absent from gcns_stars; name match still resolves."""
        self._insert(gaia_source_id=None, ra=5.0, dec=5.0, light_years=4.0, dist_pc=1.2,
                     star_name="Luhman 16", gcns_table="missing_10mas",
                     distance_method="gcns_missing_plx_inversion")
        fake = {"designations": {"Gaia EDR3": "Gaia DR3 7777"}}  # 7777 not in table
        with mock.patch.object(databases, "compute_simbad_lookup", lambda n: fake):
            r = databases._resolve_gcns_row(star="Luhman 16")
        self.assertNotIn("error", r)
        self.assertEqual(r["star_name"], "Luhman 16")

    def test_resolve_simbad_error_propagates_no_fallback(self):
        self._insert(gaia_source_id=None, ra=5.0, dec=5.0, light_years=4.0, dist_pc=1.2,
                     star_name="Whatever", gcns_table="missing_10mas")
        err = {"error": "Could not connect to SIMBAD."}
        with mock.patch.object(databases, "compute_simbad_lookup", lambda n: err):
            r = databases._resolve_gcns_row(star="Whatever")
        self.assertEqual(r, err)                # fatal, no name fallback

    # ── travel time ──────────────────────────────────────────────────────────

    def test_travel_time_distance_over_velocity(self):
        self._insert(gaia_source_id=10, ra=0.0,  dec=0.0, light_years=4.0, dist_pc=1.2)
        self._insert(gaia_source_id=20, ra=90.0, dec=0.0, light_years=4.0, dist_pc=1.2)
        res = databases.compute_gcns_travel_time(id1=10, id2=20, times_c=100.0)
        self.assertNotIn("error", res)
        self.assertIn("origin_info", res)
        self.assertIn("dest_info", res)
        ly_hr = 100.0 / 8765.8128
        self.assertAlmostEqual(res["ly_hr"], ly_hr, places=9)
        self.assertAlmostEqual(res["total_hours"], math.sqrt(32) / ly_hr, places=3)
        self.assertTrue(res["travel_time_str"])

    def test_travel_time_zero_velocity_errors(self):
        self._insert(gaia_source_id=10, ra=0.0,  dec=0.0, light_years=4.0, dist_pc=1.2)
        self._insert(gaia_source_id=20, ra=90.0, dec=0.0, light_years=4.0, dist_pc=1.2)
        self.assertIn("error", databases.compute_gcns_travel_time(id1=10, id2=20, ly_hr=0))

    # ── within-star ──────────────────────────────────────────────────────────

    def test_within_star_excludes_center_keeps_close_companion(self):
        # center
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2,
                     star_name="Center")
        # close companion ~0.0001 ly away (would be dropped by a 0.001 ly threshold)
        self._insert(gaia_source_id=11, ra=0.0, dec=0.0001, light_years=4.0, dist_pc=1.2,
                     star_name="Companion")
        # genuine neighbour within 1 ly
        self._insert(gaia_source_id=12, ra=0.5, dec=0.0, light_years=4.0, dist_pc=1.2,
                     star_name="Neighbour")
        res = databases.compute_gcns_stars_within_star(source_id=10, limit_ly=1.0)
        self.assertNotIn("error", res)
        ids = {s["gaia_source_id"] for s in res["stars"]}
        self.assertNotIn(10, ids)               # center excluded
        self.assertIn(11, ids)                  # close companion RETAINED
        self.assertIn(12, ids)
        self.assertIn("Distance", res["stars"][0])
        # sorted ascending by Distance
        dists = [s["Distance"] for s in res["stars"]]
        self.assertEqual(dists, sorted(dists))
        self.assertEqual(res["center"]["gaia_source_id"], 10)
        self.assertIn("center_x", res)

    def test_within_star_radial_prefilter_is_lossless_not_sufficient(self):
        """A row inside the radial band but in a different sky direction (3D dist >
        limit) must be excluded by the 3D check, not admitted by the SQL pre-filter."""
        self._insert(gaia_source_id=10, ra=0.0,   dec=0.0, light_years=10.0, dist_pc=3.0,
                     star_name="Center")
        # same light_years (passes radial band) but opposite sky -> 3D dist ~20 ly
        self._insert(gaia_source_id=20, ra=180.0, dec=0.0, light_years=10.0, dist_pc=3.0,
                     star_name="Antipode")
        res = databases.compute_gcns_stars_within_star(source_id=10, limit_ly=2.0)
        self.assertEqual(res["count"], 0)       # antipode correctly excluded

    def test_within_star_bad_limit_and_missing_center(self):
        self._insert(gaia_source_id=10, ra=0.0, dec=0.0, light_years=4.0, dist_pc=1.2)
        self.assertIn("error", databases.compute_gcns_stars_within_star(source_id=10, limit_ly=0))
        self.assertIn("error", databases.compute_gcns_stars_within_star(source_id=99999, limit_ly=5))


# ── query.py subprocess contract for the new subcommands ─────────────────────

class GcnsCalcCliTest(unittest.TestCase):

    def _run(self, *argv, db_path):
        return subprocess.run(
            [sys.executable, str(_REPO / "query.py"), *argv],
            capture_output=True, text=True, cwd=str(_REPO),
            env={"SPACE_APP_DB": db_path, "PATH": os.environ.get("PATH", "")},
        )

    def test_empty_db_contract_exit1_json_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dbp = os.path.join(tmpdir, "q.db")
            for argv in (
                ["gcns-distance", "--id1", "100", "--id2", "200"],
                ["gcns-travel-time", "--id1", "100", "--id2", "200", "--times-c", "50"],
                ["gcns-stars-within-star", "--id", "100", "--ly", "5"],
            ):
                proc = self._run(*argv, db_path=dbp)
                self.assertEqual(proc.returncode, 1, argv)
                payload = json.loads(proc.stdout)
                self.assertIn("error", payload)
                self.assertIn("gcns_stars", payload["error"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_required_group_exit2_argparse(self):
        tmpdir = tempfile.mkdtemp()
        try:
            dbp = os.path.join(tmpdir, "q.db")
            proc = self._run("gcns-distance", "--id1", "100", db_path=dbp)
            self.assertEqual(proc.returncode, 2)       # argparse, NOT the JSON path
            self.assertTrue(proc.stderr.strip())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
