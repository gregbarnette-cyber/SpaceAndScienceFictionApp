# tests/test_search.py — offline coverage for the Phase G search/filter functions.
#
# Covers core.shared.spectral_where / spectral_adql (pure), the DB-backed
# search_star_systems / search_hwc (temp DB, no network, auto-seed disabled), and
# search_exoplanets with the TAP fetch mocked (no network). Mirrors the DB-setup
# pattern in tests/test_gcns.py.

import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.databases as databases
from core.shared import spectral_where, spectral_adql


# ── pure spectral-clause builders (no DB) ────────────────────────────────────

class SpectralClauseTest(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(spectral_where("sp", [], ""), ("", []))
        self.assertEqual(spectral_where("sp", None, None), ("", []))
        self.assertEqual(spectral_adql("st", [], ""), "")

    def test_single_letter(self):
        frag, params = spectral_where("sp", ["G"], "")
        self.assertEqual(frag, "(sp LIKE ?)")
        self.assertEqual(params, ["G%"])

    def test_two_letters_or(self):
        frag, params = spectral_where("sp", ["G", "K"], "")
        self.assertEqual(frag, "(sp LIKE ? OR sp LIKE ?)")
        self.assertEqual(params, ["G%", "K%"])

    def test_other_clause(self):
        frag, params = spectral_where("sp", ["Other"], "")
        self.assertIn("sp IS NULL OR NOT (", frag)
        self.assertEqual(params, ["O%", "B%", "A%", "F%", "G%", "K%", "M%"])

    def test_refine_only(self):
        frag, params = spectral_where("sp", [], "V")
        self.assertEqual(frag, "sp LIKE ? ESCAPE '\\'")
        self.assertEqual(params, ["%V%"])

    def test_class_and_refine(self):
        frag, params = spectral_where("sp", ["M"], "5.5")
        self.assertEqual(frag, "(sp LIKE ?) AND sp LIKE ? ESCAPE '\\'")
        self.assertEqual(params, ["M%", "%5.5%"])

    def test_refine_escapes_wildcards(self):
        frag, params = spectral_where("sp", [], "5_0%")
        self.assertEqual(params, ["%5\\_0\\%%"])

    def test_adql_injection_sanitized(self):
        # A quote in the refine text must not escape the ADQL string literal.
        clause = spectral_adql("st_spectype", ["M"], "5'V")
        self.assertNotIn("'5'", clause)            # the embedded quote is stripped
        self.assertIn("st_spectype LIKE '%5V%'", clause)
        self.assertIn("st_spectype LIKE 'M%'", clause)


# ── DB-backed searches (temp DB, no network) ─────────────────────────────────

class SearchDBTest(unittest.TestCase):

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

    def _seed_star_systems(self):
        rows = [
            # star_name, designations, spectral_type, light_years, app_magnitude
            ("Alpha Centauri A", "GJ 559 A, HD 128620, HIP 71683", "G2V",    4.36, 0.01),
            ("Proxima Centauri", "GJ 551, HIP 70890",              "M5.5Ve", 4.24, 11.13),
            ("Sirius B",         "GJ 244 B",                       "DA2",    8.60, 8.44),
            ("Mystery Star",     "HD 999",                         None,     10.0, 5.0),
            ("Tau Ceti",         "GJ 71, HD 10700, HIP 8102",      "G8.5V",  11.91, 3.50),
        ]
        self.conn.executemany(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "light_years, app_magnitude) VALUES (?, ?, ?, ?, ?)", rows)
        self.conn.commit()

    def _names(self, result):
        return [s["star_name"] for s in result["stars"]]

    # star_systems ------------------------------------------------------------

    def test_empty_table_error(self):
        result = databases.search_star_systems({"spectral_classes": ["M"]})
        self.assertIn("error", result)
        self.assertIn("option 50", result["error"])

    def test_class_m_excludes_g_and_whitedwarf(self):
        self._seed_star_systems()
        self.assertEqual(self._names(databases.search_star_systems({"spectral_classes": ["M"]})),
                         ["Proxima Centauri"])

    def test_other_matches_whitedwarf_and_null(self):
        self._seed_star_systems()
        names = self._names(databases.search_star_systems({"spectral_classes": ["Other"]}))
        self.assertCountEqual(names, ["Sirius B", "Mystery Star"])

    def test_designation_prefix_after_comma(self):
        self._seed_star_systems()
        # "HD 1" must match Alpha Cen A (HD 128620) and Tau Ceti (HD 10700),
        # via the after-comma token rule — but NOT Mystery Star (HD 999).
        names = self._names(databases.search_star_systems({"designation_prefix": "HD 1"}))
        self.assertCountEqual(names, ["Alpha Centauri A", "Tau Ceti"])

    def test_ly_range_and_sort(self):
        self._seed_star_systems()
        result = databases.search_star_systems({"ly_max": 9.0})
        self.assertEqual(self._names(result), ["Proxima Centauri", "Alpha Centauri A", "Sirius B"])

    def test_mag_range(self):
        self._seed_star_systems()
        names = self._names(databases.search_star_systems({"mag_min": 8.0}))
        self.assertCountEqual(names, ["Proxima Centauri", "Sirius B"])

    def test_cap_detection(self):
        self._seed_star_systems()
        with mock.patch.object(databases, "_SEARCH_CAP", 2):
            result = databases.search_star_systems({"mag_min": -30})  # matches all 5
            self.assertTrue(result["capped"])
            self.assertEqual(len(result["stars"]), 2)

    # hwc ---------------------------------------------------------------------

    def _seed_hwc(self):
        self.conn.execute(
            "CREATE TABLE hwc (P_NAME TEXT, P_ESI TEXT, P_HABITABLE TEXT, "
            "P_HABZONE_CON TEXT, P_HABZONE_OPT TEXT, P_MASS TEXT, P_RADIUS TEXT, "
            "P_TEMP_EQUIL TEXT, S_NAME TEXT, S_NAME_HD TEXT, S_NAME_HIP TEXT, "
            "S_TYPE TEXT, S_DISTANCE TEXT)")
        rows = [
            # name, esi, hab, con, opt, mass, radius, teq, star, hd, hip, sptype, dist_pc
            ("Earth b",   "0.99", "1", "1", "1", "1.0", "1.0", "255", "Sun",   "", "", "G2V", "0.0"),
            ("Blank b",   "",     "1", "1", "1", "",    "",    "",    "BlS",   "", "", "M3V", "2.0"),
            ("Hot b",     "0.50", "0", "0", "1", "5.0", "2.0", "400", "HotS",  "", "", "K2V", "3.0"),
            ("Far b",     "0.85", "1", "1", "1", "1.2", "1.1", "260", "FarS",  "", "", "M5V", "40.0"),
        ]
        self.conn.executemany(
            "INSERT INTO hwc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def test_hwc_empty_error(self):
        result = databases.search_hwc({"esi_min": 0.8})
        self.assertIn("error", result)
        self.assertIn("option 52", result["error"])

    def test_hwc_esi_excludes_blank_not_as_zero(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"esi_min": 0.8})["stars"]]
        # Earth (0.99) and Far (0.85) qualify; Blank ('') must NOT match as 0.
        self.assertCountEqual(names, ["Earth b", "Far b"])

    def test_hwc_habitable_flag(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"habitable": True})["stars"]]
        self.assertCountEqual(names, ["Earth b", "Blank b", "Far b"])

    def test_hwc_sorted_esi_desc_blank_last(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({})["stars"]]
        self.assertEqual(names, ["Earth b", "Far b", "Hot b", "Blank b"])

    def test_hwc_ly_max(self):
        self._seed_hwc()
        # Far b at 40 pc ≈ 130 ly excluded by ly_max=20.
        names = [s["P_NAME"] for s in databases.search_hwc({"ly_max": 20})["stars"]]
        self.assertNotIn("Far b", names)

    def test_hwc_spectral_class(self):
        self._seed_hwc()
        names = [s["P_NAME"] for s in databases.search_hwc({"spectral_classes": ["M"]})["stars"]]
        self.assertCountEqual(names, ["Blank b", "Far b"])


# ── exoplanet search (TAP mocked, no network) ────────────────────────────────

class SearchExoplanetTest(unittest.TestCase):

    def test_where_and_top_built(self):
        captured = {}

        def _fake_tap(table, where, order_by=None, timeout=60, top=None, select="*"):
            captured.update(table=table, where=where, order_by=order_by, top=top, select=select)
            return [{"pl_name": "x"}]

        with mock.patch.object(databases, "_query_tap", _fake_tap):
            databases.search_exoplanets({
                "pl_bmasse_min": 1, "pl_rade_max": 2,
                "discoverymethod": "Transit",
                "spectral_classes": ["M"], "sy_dist_max": 15,
            })
        self.assertEqual(captured["table"], "pscomppars")
        self.assertEqual(captured["top"], databases._EXO_SEARCH_CAP + 1)  # cap+1 fetch
        self.assertEqual(captured["order_by"], "pl_orbsmax")
        self.assertIn("pl_bmasse >= 1.0", captured["where"])
        self.assertIn("pl_rade <= 2.0", captured["where"])
        self.assertIn("sy_dist <= 15.0", captured["where"])
        self.assertIn("discoverymethod = 'Transit'", captured["where"])
        self.assertIn("st_spectype LIKE 'M%'", captured["where"])

    def test_empty_filters_default_where(self):
        captured = {}

        def _fake_tap(table, where, **kw):
            captured["where"] = where
            return []

        with mock.patch.object(databases, "_query_tap", _fake_tap):
            databases.search_exoplanets({})
        self.assertEqual(captured["where"], "pl_name IS NOT NULL")

    def test_any_method_ignored(self):
        captured = {}
        with mock.patch.object(databases, "_query_tap",
                               lambda table, where, **kw: captured.update(where=where) or []):
            databases.search_exoplanets({"discoverymethod": "Any"})
        self.assertNotIn("discoverymethod", captured["where"])

    def test_network_error_classified(self):
        import requests

        def _boom(*a, **k):
            raise requests.exceptions.Timeout("slow")

        with mock.patch.object(databases, "_query_tap", _boom):
            result = databases.search_exoplanets({"pl_rade_min": 1})
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"].lower())

    def test_cap_flag(self):
        cap = databases._EXO_SEARCH_CAP
        # Exactly `cap` matches must NOT be reported as capped (the off-by-one fix).
        exact = [{"pl_name": f"p{i}"} for i in range(cap)]
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: exact):
            result = databases.search_exoplanets({})
        self.assertFalse(result["capped"])
        self.assertEqual(result["count"], cap)
        # The fetch asks for cap+1; if that many come back, report capped and slice.
        over = [{"pl_name": f"p{i}"} for i in range(cap + 1)]
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: over):
            result = databases.search_exoplanets({})
        self.assertTrue(result["capped"])
        self.assertEqual(result["count"], cap)


if __name__ == "__main__":
    unittest.main()
