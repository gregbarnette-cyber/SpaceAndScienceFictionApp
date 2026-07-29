# tests/test_gould.py — offline coverage for Phase AO (Gould designations).
#
# AO attaches an optional top-level "gould" key to compute_simbad_lookup's return
# (parallel to "gcns"), built by _simbad_gould_block from the HD number in the
# SIMBAD designations against the bundled Uranometria Argentina catalogue. SIMBAD
# itself carries NO Gould ids, so this is a separate data layer.
#
# TWO fixtures are needed, not one (PHASE_AO_PLAN.md AO5 [R3b]): the established
# isolation pattern (test_gcns.py, test_simbad_gcns_enrichment.py) monkeypatches
# db._auto_seed away, which disables ALL static seeding — so it can never exercise
# a seeder. The seeder gets its own class that calls _seed_gould directly.
#
# Everything here is offline: a temp SQLite DB plus the committed CSV.

import inspect
import pathlib
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.databases as databases
from core.shared import _CONSTELLATION_GENITIVES, constellation_genitive


_CSV_PATH = pathlib.Path(__file__).resolve().parents[1] / "gouldDesignations.csv"

# Reference stars, verified against VizieR V/135A live on 2026-07-29.
_HD_CEN = 102365     # 66 G. Centauri
_HD_HYA = 100623     # GJ 432 A — 289 G. Hydrae (Hya in 1875, Crater today)
_HD_ERI = 22049      # epsilon Eri — 101 G. Eridani


class _TempDbTest(unittest.TestCase):
    """Temp DB with static seeding DISABLED — rows are hand-inserted."""

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

    def _insert(self, g_number, cst, hd, sao=None, bayer=None, flamsteed=None):
        self.conn.execute(
            "INSERT INTO gould_designations "
            "(g_number, cst, hd, sao, flamsteed, bayer, name, vmag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (g_number, cst, hd, sao, flamsteed, bayer, None, None),
        )
        self.conn.commit()


# ── AO1 — the seeder (its own fixture; _auto_seed is NOT disabled here) ───────

class GouldSeederTest(unittest.TestCase):
    """Calls _seed_gould directly against the committed CSV."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "seed.db"
        db._conn = None
        self.conn = sqlite3.connect(db._DB_PATH)
        self.conn.row_factory = sqlite3.Row
        db._create_schema(self.conn)
        with self.conn:
            db._seed_gould(self.conn, _CSV_PATH)

    def tearDown(self):
        self.conn.close()
        db._DB_PATH, db._conn = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _scalar(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()[0]

    def test_bundled_csv_exists(self):
        self.assertTrue(_CSV_PATH.exists(), f"missing bundled catalogue: {_CSV_PATH}")

    def test_row_and_gould_number_counts(self):
        # Live profile of VizieR V/135A, 2026-07-29.
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM gould_designations"), 8471)
        self.assertEqual(
            self._scalar("SELECT COUNT(*) FROM gould_designations WHERE g_number IS NOT NULL"),
            7756)

    def test_gould_less_rows_are_kept_not_dropped(self):
        # AO1b: _seed_honorverse_hyper's `continue`-the-row-on-ValueError pattern
        # would silently drop these 715 rows, which still carry HD/SAO data.
        self.assertEqual(
            self._scalar("SELECT COUNT(*) FROM gould_designations WHERE g_number IS NULL"),
            715)
        self.assertGreater(
            self._scalar("SELECT COUNT(*) FROM gould_designations "
                         "WHERE g_number IS NULL AND hd IS NOT NULL"), 0)

    def test_column_storage_types_are_never_text_for_numerics(self):
        # THE AO1b guard. _seed_main_sequence inserts raw DictReader strings, so a
        # blank cell lands as ''-as-TEXT. SQLite orders NULL < INTEGER < TEXT, so a
        # mixed column would make AO2a's `ORDER BY g_number LIMIT 1` pick the wrong
        # component of a double star. Assert the storage class directly.
        for col, allowed in (
            ("g_number",  {"integer", "null"}),
            ("hd",        {"integer", "null"}),
            ("sao",       {"integer", "null"}),
            ("flamsteed", {"integer", "null"}),
            ("vmag",      {"real", "null"}),
            ("cst",       {"text", "null"}),
            ("bayer",     {"text", "null"}),
        ):
            with self.subTest(column=col):
                seen = {r[0] for r in self.conn.execute(
                    f"SELECT DISTINCT typeof({col}) FROM gould_designations")}
                self.assertTrue(seen <= allowed, f"{col} stored as {seen - allowed}")

    def test_provenance_comments_are_skipped_not_ingested(self):
        # The CSV leads with '#' provenance lines above the header.
        self.assertEqual(
            self._scalar("SELECT COUNT(*) FROM gould_designations WHERE cst LIKE '#%'"), 0)
        with open(_CSV_PATH, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("#"))

    def test_reference_stars_seed_correctly(self):
        for hd, g, cst in ((_HD_CEN, 66, "Cen"), (_HD_HYA, 289, "Hya"), (_HD_ERI, 101, "Eri")):
            with self.subTest(hd=hd):
                row = self.conn.execute(
                    "SELECT g_number, cst FROM gould_designations WHERE hd = ? "
                    "ORDER BY g_number LIMIT 1", (hd,)).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual((row["g_number"], row["cst"]), (g, cst))

    def test_every_constellation_code_used_resolves_to_a_genitive(self):
        codes = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT cst FROM gould_designations WHERE cst IS NOT NULL")]
        self.assertEqual(len(codes), 66)          # measured; Gould is southern-only
        unresolved = [c for c in codes if not constellation_genitive(c)]
        self.assertEqual(unresolved, [])

    def test_hd_duplicates_exist_and_sao_duplicates_do_not(self):
        # AO2a / [R5]: the measurement the plan asked for, pinned so a future
        # re-export that changes it fails loudly instead of silently.
        hd_dupes = self._scalar(
            "SELECT COUNT(*) FROM (SELECT hd FROM gould_designations "
            "WHERE hd IS NOT NULL GROUP BY hd HAVING COUNT(*) > 1)")
        sao_dupes = self._scalar(
            "SELECT COUNT(*) FROM (SELECT sao FROM gould_designations "
            "WHERE sao IS NOT NULL GROUP BY sao HAVING COUNT(*) > 1)")
        self.assertEqual(hd_dupes, 11)
        self.assertEqual(sao_dupes, 0)

    def test_table_status_lists_gould(self):
        db._conn = self.conn
        try:
            entry = [t for t in db.get_table_status() if t["table"] == "Gould Designations"]
            self.assertEqual(len(entry), 1)
            self.assertEqual(entry[0]["rows"], 8471)
            self.assertTrue(entry[0]["populated"])
        finally:
            db._conn = None


# ── §2 — the constellation-genitive table ────────────────────────────────────

class ConstellationGenitiveTest(unittest.TestCase):

    def test_all_88_constellations_present(self):
        self.assertEqual(len(_CONSTELLATION_GENITIVES), 88)

    def test_known_genitives(self):
        for abbr, genitive in (
            ("Cen", "Centauri"), ("Hya", "Hydrae"), ("Eri", "Eridani"),
            ("Crt", "Crateris"), ("CMi", "Canis Minoris"),
            ("TrA", "Trianguli Australis"), ("Com", "Comae Berenices"),
        ):
            with self.subTest(abbr=abbr):
                self.assertEqual(constellation_genitive(abbr), genitive)

    def test_lookup_is_case_and_whitespace_insensitive(self):
        for raw in ("CMa", "cma", "CMA", "  CMa  "):
            with self.subTest(raw=raw):
                self.assertEqual(constellation_genitive(raw), "Canis Majoris")

    def test_unknown_and_blank_return_none_never_invent(self):
        for raw in ("Xyz", "", None, "  ", 0):
            with self.subTest(raw=raw):
                self.assertIsNone(constellation_genitive(raw))

    def test_genitives_are_unique(self):
        values = list(_CONSTELLATION_GENITIVES.values())
        self.assertEqual(len(values), len(set(values)))


# ── AO3b — the formatter ──────────────────────────────────────────────────────

class GouldFormatTest(unittest.TestCase):

    def test_builds_both_forms_from_number_and_code(self):
        self.assertEqual(databases._gould_format(66, "Cen"), ("66 G. Cen", "66 G. Centauri"))
        self.assertEqual(databases._gould_format(289, "Hya"), ("289 G. Hya", "289 G. Hydrae"))

    def test_display_falls_back_to_abbreviation_when_unknown(self):
        designation, display = databases._gould_format(5, "Zzz")
        self.assertEqual(designation, "5 G. Zzz")
        self.assertEqual(display, "5 G. Zzz")        # never invents a constellation

    def test_missing_constellation_still_formats(self):
        designation, display = databases._gould_format(7, None)
        self.assertEqual(designation, "7 G.")
        self.assertEqual(display, "7 G.")

    def test_catalog_number_parsed_out_of_designation_string(self):
        self.assertEqual(databases._gould_catalog_number({"HD": "HD 102365"}, "HD"), 102365)
        self.assertEqual(databases._gould_catalog_number({"SAO": "SAO 223020"}, "SAO"), 223020)
        self.assertIsNone(databases._gould_catalog_number({"HD": None}, "HD"))
        self.assertIsNone(databases._gould_catalog_number({}, "HD"))
        self.assertIsNone(databases._gould_catalog_number({"HD": "no digits"}, "HD"))


# ── AO2 — _simbad_gould_block ─────────────────────────────────────────────────

class SimbadGouldBlockTest(_TempDbTest):

    def test_reference_star_hd_102365(self):
        self._insert(66, "Cen", _HD_CEN, sao=223020)
        block = databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"})
        self.assertIsNotNone(block)
        self.assertEqual(block["g_number"], 66)
        self.assertEqual(block["cst"], "Cen")
        self.assertEqual(block["constellation"], "Centauri")
        self.assertEqual(block["designation"], "66 G. Cen")
        self.assertEqual(block["display"], "66 G. Centauri")
        self.assertEqual(block["matched_on"], "hd")
        self.assertEqual(block["source"], "VizieR V/135A (Gould 1879)")

    def test_reference_star_gj_432_a(self):
        self._insert(289, "Hya", _HD_HYA, sao=202583)
        block = databases._simbad_gould_block({"HD": f"HD {_HD_HYA}"})
        self.assertEqual(block["display"], "289 G. Hydrae")

    def test_join_is_hd_only_sao_alone_does_not_match(self):
        # The SAO fallback was REMOVED after code review (2026-07-29): it was
        # unreachable, because `designations` never carries an "SAO" key. The
        # test that "covered" it hand-built {"SAO": …} — a shape the pipeline
        # cannot produce — so it passed while the branch was dead in production.
        # Pin the real behaviour instead.
        self._insert(66, "Cen", _HD_CEN, sao=223020)
        self.assertIsNone(databases._simbad_gould_block({"SAO": "SAO 223020"}))

    def test_matched_on_is_always_hd(self):
        self._insert(66, "Cen", _HD_CEN, sao=223020)
        block = databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"})
        self.assertEqual(block["matched_on"], "hd")
        self.assertEqual(block["sao"], 223020)      # echoed, but not joined on

    def test_sao_is_absent_from_the_designation_key_set(self):
        # THE GUARD behind the two tests above, and the reason the dead branch
        # went unnoticed. If a future change (Phase AN's AN2 key insertion is the
        # likely one) starts capturing SAO ids, this fails — which is the signal
        # to reconsider the fallback, since SIMBAD DOES emit "SAO nnnnn".
        from core.shared import _CSV_PREFIX_MAP
        self.assertNotIn("SAO", {key for _, key in _CSV_PREFIX_MAP})
        src = inspect.getsource(databases.compute_simbad_lookup)
        self.assertNotIn('"SAO"', src)

    def test_hd_tie_break_is_lowest_gould_number(self):
        # AO2a: 11 HD values sit on two rows. Insert high-then-low so a naive
        # "first row wins" would return 900.
        self._insert(900, "Cen", 47138)
        self._insert(120, "Cen", 47138)
        block = databases._simbad_gould_block({"HD": "HD 47138"})
        self.assertEqual(block["g_number"], 120)

    def test_tie_break_ignores_null_gould_rows(self):
        # A NULL g_number sorts FIRST in SQLite; without the IS NOT NULL filter
        # this would return a row with no Gould number at all.
        self._insert(None, None, _HD_CEN)
        self._insert(66, "Cen", _HD_CEN)
        block = databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"})
        self.assertIsNotNone(block)
        self.assertEqual(block["g_number"], 66)

    def test_none_when_no_hd(self):
        self._insert(66, "Cen", _HD_CEN)
        self.assertIsNone(databases._simbad_gould_block({"HIP": "HIP 57443"}))
        self.assertIsNone(databases._simbad_gould_block({}))
        self.assertIsNone(databases._simbad_gould_block(None))

    def test_none_when_not_in_catalogue(self):
        self._insert(66, "Cen", _HD_CEN)
        self.assertIsNone(databases._simbad_gould_block({"HD": "HD 999999"}))

    def test_none_when_table_empty(self):
        self.assertIsNone(databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"}))

    def test_none_when_table_missing_does_not_raise(self):
        self.conn.execute("DROP TABLE gould_designations")
        self.conn.commit()
        self.assertIsNone(databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"}))

    def test_none_on_unexpected_error_does_not_raise(self):
        self._insert(66, "Cen", _HD_CEN)
        with mock.patch("core.db.get_conn", side_effect=RuntimeError("boom")):
            self.assertIsNone(databases._simbad_gould_block({"HD": f"HD {_HD_CEN}"}))


# ── AO2 wiring — compute_simbad_lookup attaches the key (SIMBAD mocked) ───────

class _FakeTable(list):
    def __init__(self, rowdict, colnames):
        super().__init__([rowdict])
        self.colnames = colnames


class _FakeSimbad:
    def query_object(self, name):
        return _FakeTable({"main_id": "HD 102365"}, ["main_id"])


class SimbadLookupGouldWiringTest(_TempDbTest):

    def _lookup(self, ids):
        with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _FakeSimbad()), \
             mock.patch.object(databases, "_with_retries", lambda fn, *a, **k: fn(*a)), \
             mock.patch("astroquery.simbad.Simbad.query_objectids", lambda name: ids):
            return databases.compute_simbad_lookup("HD 102365")

    def test_attaches_populated_gould_key(self):
        self._insert(66, "Cen", _HD_CEN, sao=223020)
        result = self._lookup([{"id": f"HD {_HD_CEN}"}, {"id": "HIP 57443"}])
        self.assertNotIn("error", result)
        self.assertIn("gould", result)
        self.assertEqual(result["gould"]["display"], "66 G. Centauri")

    def test_key_present_but_none_when_star_not_in_catalogue(self):
        # Coverage is intentionally partial (AO4a) — None is the normal answer.
        self._insert(66, "Cen", _HD_CEN)
        result = self._lookup([{"id": "HD 999999"}])
        self.assertIn("gould", result)
        self.assertIsNone(result["gould"])

    def test_lookup_survives_a_failing_gould_block(self):
        self._insert(66, "Cen", _HD_CEN)
        with mock.patch.object(databases, "_simbad_gould_block",
                               side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self._lookup([{"id": f"HD {_HD_CEN}"}])
        # …and with the real block, a broken DB degrades to None rather than
        # taking the whole SIMBAD result down.
        with mock.patch("core.db.table_exists", side_effect=RuntimeError("boom")):
            result = self._lookup([{"id": f"HD {_HD_CEN}"}])
        self.assertNotIn("error", result)
        self.assertIsNone(result["gould"])
        self.assertEqual(result["designations"]["HD"], f"HD {_HD_CEN}")

    def test_gould_is_not_folded_into_designations(self):
        # AO3a: `designations` means "what SIMBAD returned"; SIMBAD has no Gould ids.
        self._insert(66, "Cen", _HD_CEN)
        result = self._lookup([{"id": f"HD {_HD_CEN}"}])
        self.assertNotIn("Gould", result["designations"])
        self.assertNotIn("G.", result["desig_str"])


if __name__ == "__main__":
    unittest.main()
