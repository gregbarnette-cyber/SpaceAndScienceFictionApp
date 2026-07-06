# tests/test_hypatia_cache.py — Phase L4 (Hypatia abundance cache) coverage.
#
# Offline. Covers:
#   * import_hypatia_cache with the bulk GET /data fetch mocked — assembly
#     (props + denormalized fe_h + precomputed light_years + disk formatting),
#     idempotency / no-orphans, a non-fatal element-axis failure, and the
#     validate-before-destroy Gate 1 (a short download leaves the cache intact).
#   * search_hypatia_cache filter matrix (fe_h / teff / ly / disk / element
#     EXISTS / pivots), fe_h DESC NULL-last ordering, the cap, and the empty-table
#     error.
#   * The G1 search_star_systems fe_h JOIN — activates only with a populated
#     cache; the non-fe_h path is unaffected.
#   * The search-hypatia query.py subcommand contract (subprocess happy path +
#     argparse exit 2).
#
# DB isolation mirrors tests/test_db_backups.py (monkeypatch core.db._DB_PATH to a
# tmp file with auto-seed disabled) and tests/test_query_route_opts.py (subprocess
# via SPACE_APP_DB).

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
import core.databases as dbs

from tests._queryharness import run_query

_REPO = Path(__file__).resolve().parent.parent


def _make_fetch(n_stars=1500):
    """Return a fake _hypatia_data_fetch over n_stars synthetic stars."""
    def fetch(axis):
        if axis == "teff":
            return {f"* S{i}": 5000 + i for i in range(n_stars)}
        if axis == "dist":
            return {f"* S{i}": 10.0 for i in range(n_stars)}
        if axis == "disk":
            return {f"* S{i}": float(i % 2) for i in range(n_stars)}
        if axis == "logg":
            return {f"* S{i}": 4.5 for i in range(n_stars)}
        if axis == "Fe":
            return {f"* S{i}": round(-0.5 + 0.001 * i, 4) for i in range(n_stars)}
        if axis == "Mg":   # measured on the even stars only
            return {f"* S{i}": 0.1 for i in range(0, n_stars, 2)}
        return {}
    return fetch


class _TmpDbTest(unittest.TestCase):
    """Base: a throwaway on-disk DB with auto-seed disabled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "t.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class ImportHypatiaCacheTest(_TmpDbTest):

    def setUp(self):
        super().setUp()
        self._saved_fetch = dbs._hypatia_data_fetch

    def tearDown(self):
        dbs._hypatia_data_fetch = self._saved_fetch
        super().tearDown()

    def test_import_assembles_rows(self):
        dbs._hypatia_data_fetch = _make_fetch(1500)
        r = dbs.import_hypatia_cache()
        self.assertEqual(r["inserted"], 1500)
        self.assertEqual(r["fe_h_count"], 1500)
        self.assertEqual(r["abundance_rows"], 1500 + 750)  # Fe (all) + Mg (even)
        self.assertEqual(r["errors"], 0)
        # disk int-formatted; light_years precomputed; fe_h denormalized.
        row = self.conn.execute(
            "SELECT disk, light_years, fe_h, teff FROM hypatia_cache WHERE star_name='* S2'"
        ).fetchone()
        self.assertEqual(row["disk"], "0")
        self.assertAlmostEqual(row["light_years"], 10.0 * 3.26156, places=4)
        self.assertAlmostEqual(row["fe_h"], -0.498, places=4)
        # meta written
        meta = dbs._hypatia_meta_dict()
        self.assertEqual(meta["star_count"], "1500")
        self.assertEqual(meta["simbad_norm"], "lodders09")

    def test_idempotent_no_orphans(self):
        dbs._hypatia_data_fetch = _make_fetch(1500)
        dbs.import_hypatia_cache()
        r2 = dbs.import_hypatia_cache()
        self.assertEqual(r2["inserted"], 1500)
        self.assertEqual(r2["abundance_rows"], 2250)
        orphans = self.conn.execute(
            "SELECT COUNT(*) FROM hypatia_abundance a "
            "LEFT JOIN hypatia_cache c ON a.star_name = c.star_name "
            "WHERE c.star_name IS NULL"
        ).fetchone()[0]
        self.assertEqual(orphans, 0)

    def test_element_axis_failure_is_nonfatal(self):
        base = _make_fetch(1500)

        def flaky(axis):
            if axis == "Mg":
                raise RuntimeError("boom")
            return base(axis)

        dbs._hypatia_data_fetch = flaky
        r = dbs.import_hypatia_cache()
        self.assertEqual(r["errors"], 1)
        self.assertEqual(r["inserted"], 1500)        # still succeeds
        self.assertEqual(r["abundance_rows"], 1500)  # only Fe survived

    def test_gate1_short_download_leaves_cache_intact(self):
        dbs._hypatia_data_fetch = _make_fetch(1500)
        dbs.import_hypatia_cache()
        before = self.conn.execute("SELECT COUNT(*) FROM hypatia_cache").fetchone()[0]

        def short(axis):
            return {f"* S{i}": 1.0 for i in range(50)} if axis in ("teff", "Fe") else {}

        dbs._hypatia_data_fetch = short
        err = dbs.import_hypatia_cache()
        self.assertIn("error", err)
        after = self.conn.execute("SELECT COUNT(*) FROM hypatia_cache").fetchone()[0]
        self.assertEqual(before, after)  # untouched


class SearchHypatiaCacheTest(_TmpDbTest):

    def setUp(self):
        super().setUp()
        self.conn.executemany(
            "INSERT INTO hypatia_cache (star_name, teff, distance_pc, disk, fe_h, "
            "light_years) VALUES (?,?,?,?,?,?)",
            [
                ("* 1 Aqr",  5000, 30.0, "0", 0.11, 97.8),
                ("* tau Cet", 5344, 3.6, "0", -0.50, 11.9),
                ("* nofe",   6000, 10.0, "1", None, 32.6),
            ],
        )
        self.conn.executemany(
            "INSERT INTO hypatia_abundance (star_name, element, mean) VALUES (?,?,?)",
            [("* 1 Aqr", "Fe", 0.11), ("* 1 Aqr", "Mg", 0.20),
             ("* tau Cet", "Fe", -0.50), ("* tau Cet", "Mg", -0.30)],
        )
        self.conn.commit()

    def _names(self, filters):
        return [s["star_name"] for s in dbs.search_hypatia_cache(filters)["stars"]]

    def test_default_order_fe_desc_null_last(self):
        self.assertEqual(self._names({}), ["* 1 Aqr", "* tau Cet", "* nofe"])

    def test_fe_h_filter(self):
        self.assertEqual(self._names({"fe_h_min": 0.0}), ["* 1 Aqr"])

    def test_teff_and_ly(self):
        self.assertEqual(self._names({"teff_max": 5500}), ["* 1 Aqr", "* tau Cet"])
        self.assertEqual(self._names({"ly_max": 20}), ["* tau Cet"])

    def test_disk_exact(self):
        self.assertEqual(self._names({"disk": "1"}), ["* nofe"])

    def test_element_exists(self):
        self.assertEqual(self._names({"element": "Mg", "element_min": 0.0}), ["* 1 Aqr"])
        self.assertEqual(
            sorted(self._names({"element": "Mg"})), ["* 1 Aqr", "* tau Cet"])

    def test_pivot_columns(self):
        top = dbs.search_hypatia_cache({})["stars"][0]
        self.assertEqual(top["star_name"], "* 1 Aqr")
        self.assertAlmostEqual(top["mg_h"], 0.20, places=3)
        self.assertIsNone(top["si_h"])  # no Si measured

    def test_empty_table_error(self):
        self.conn.execute("DELETE FROM hypatia_abundance")
        self.conn.execute("DELETE FROM hypatia_cache")
        self.conn.commit()
        self.assertIn("error", dbs.search_hypatia_cache({}))


class SearchStarSystemsFeHJoinTest(_TmpDbTest):

    def setUp(self):
        super().setUp()
        self.conn.executemany(
            "INSERT INTO star_systems (star_name, light_years) VALUES (?,?)",
            [("* 1 Aqr", 97.8), ("* tau Cet", 11.9)],
        )
        self.conn.commit()

    def test_fe_h_join_needs_cache(self):
        # No cache yet → an fe_h filter matches nothing (inner join), but is not
        # an error (star_systems is non-empty).
        r = dbs.search_star_systems({"fe_h_min": 0.0})
        self.assertEqual(r["count"], 0)
        self.assertNotIn("error", r)

    def test_fe_h_join_with_cache(self):
        self.conn.executemany(
            "INSERT INTO hypatia_cache (star_name, fe_h) VALUES (?,?)",
            [("* 1 Aqr", 0.11), ("* tau Cet", -0.50)],
        )
        self.conn.commit()
        names = [s["star_name"] for s in dbs.search_star_systems({"fe_h_min": 0.0})["stars"]]
        self.assertEqual(names, ["* 1 Aqr"])

    def test_non_feh_path_unaffected(self):
        # The aliased query still works without the join.
        r = dbs.search_star_systems({"ly_max": 50})
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["stars"][0]["star_name"], "* tau Cet")


class HypatiaScatterPrepTest(unittest.TestCase):
    """core.viz.prepare_hypatia_scatter (Phase L4 diagram data)."""

    def setUp(self):
        import core.viz as viz
        self.viz = viz
        self.result = {"stars": [
            {"star_name": "X", "fe_h": 0.1, "teff": 5800, "mg_h": 0.2},
            {"star_name": "Y", "fe_h": -0.3, "teff": 5000, "mg_h": None},
            {"star_name": "Z", "fe_h": None, "teff": 6000, "mg_h": 0.0},
        ]}

    def test_drops_rows_missing_either_axis(self):
        d = self.viz.prepare_hypatia_scatter(self.result, "fe_h", "teff")
        self.assertEqual(d["count"], 2)
        self.assertEqual(d["labels"], ["X", "Y"])      # Z dropped (no fe_h)
        self.assertEqual(d["x_label"], "[Fe/H]")
        self.assertEqual(d["y_label"], "Teff (K)")

    def test_element_axis_drops_more(self):
        d = self.viz.prepare_hypatia_scatter(self.result, "fe_h", "mg_h")
        self.assertEqual(d["labels"], ["X"])           # Y no mg, Z no fe

    def test_bad_axis_and_empty(self):
        self.assertIn("error", self.viz.prepare_hypatia_scatter(self.result, "nope", "teff"))
        self.assertIn("error", self.viz.prepare_hypatia_scatter({"stars": []}, "fe_h", "teff"))
        self.assertIn("error", self.viz.prepare_hypatia_scatter({"error": "x"}, "fe_h", "teff"))


class SearchHypatiaQueryCliTest(unittest.TestCase):
    """search-hypatia query.py subcommand via subprocess + SPACE_APP_DB."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "q.db")
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        try:
            db._DB_PATH = pathlib.Path(self.db_path)
            db._conn = None
            db._auto_seed = lambda conn: None
            conn = db.get_conn()
            conn.execute(
                "INSERT INTO hypatia_cache (star_name, teff, distance_pc, disk, "
                "fe_h, light_years) VALUES ('* tau Cet',5344,3.6,'0',-0.5,11.9)")
            conn.execute(
                "INSERT INTO hypatia_abundance (star_name, element, mean) "
                "VALUES ('* tau Cet','Mg',-0.3)")
            conn.commit()
            db.close_conn()
        finally:
            db._DB_PATH, db._conn, db._auto_seed = saved

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, *args):
        return run_query(*args, db_path=self.db_path)[:2]

    def test_happy(self):
        code, payload = self._run("search-hypatia", "--fe-h-max", "0",
                                  "--element", "Mg", "--element-max", "0")
        self.assertEqual(code, 0)
        self.assertEqual(payload["stars"][0]["star_name"], "* tau Cet")

    def test_no_filters_returns_all(self):
        code, payload = self._run("search-hypatia")
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 1)

    def test_bad_arg_exit_2(self):
        code, _ = self._run("search-hypatia", "--fe-h-min", "notanumber")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
