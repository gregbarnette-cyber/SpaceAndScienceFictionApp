# tests/test_databases.py — offline unit coverage for core/databases.py helpers.
#
# Phase 6 seeds this file with the P6.2 (_adql_quote) and P6.3 (_validate_csv_headers)
# hardening helpers; Phase 7 (P7.2) expands it with the mocked-network archive readers
# (compute_exoplanet_archive / _planetary_systems_composite / _hwo_exep — _query_tap
# mocked) and the CSV/DB-backed readers (compute_mission_exocat via a temp CSV import,
# compute_hwc via the real hwc.csv against a temp DB). Pure offline, no network, no Qt.
# OEC was removed (rebuild pending); only the _load_oec fetch loader remains, untested here.
# Mocking style mirrors tests/test_comparison.py
# and the temp-DB pattern in tests/test_search.py.

import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.databases as databases
import core.db as db


class AdqlQuoteTest(unittest.TestCase):
    def test_normal_designation_is_byte_identical(self):
        # No quotes / control chars → unchanged, so existing built queries don't shift.
        for s in ("HIP 12345", "HD 209458", "Gaia DR3 5853498713190525696", "TIC 001", "K2-18"):
            self.assertEqual(databases._adql_quote(s), s)

    def test_single_quote_doubled(self):
        self.assertEqual(databases._adql_quote("O'Brien"), "O''Brien")
        self.assertEqual(databases._adql_quote("a'b'c"), "a''b''c")

    def test_control_chars_stripped(self):
        self.assertEqual(databases._adql_quote("bad\x00\x1fname"), "badname")
        self.assertEqual(databases._adql_quote("line\nbreak"), "linebreak")

    def test_none_becomes_empty(self):
        self.assertEqual(databases._adql_quote(None), "")

    def test_injection_attempt_neutralized(self):
        # A classic break-out attempt becomes an inert doubled-quote literal.
        out = databases._adql_quote("x' OR '1'='1")
        self.assertEqual(out, "x'' OR ''1''=''1")
        self.assertNotIn("' OR '", f"'{out}'".replace("''", ""))


class ValidateCsvHeadersTest(unittest.TestCase):
    def test_valid_headers_pass(self):
        # The real hwc.csv / missionExocat.csv headers are [A-Za-z0-9_]; the allowed
        # set is a small safe superset.
        ok = ["P_NAME", "S_NAME_HIP", "st_teff", "col 1", "A.B", "x-y", "a/b", "n(1)", "pct%"]
        self.assertIsNone(databases._validate_csv_headers(ok))

    def test_double_quote_rejected(self):
        r = databases._validate_csv_headers(["ok", 'bad"col'])
        self.assertIsInstance(r, dict)
        self.assertIn("error", r)

    def test_semicolon_and_paren_injection_rejected(self):
        for bad in ["a;DROP TABLE", "a) ; --", "a,b"]:
            r = databases._validate_csv_headers([bad])
            self.assertIn("error", r, bad)

    def test_empty_header_rejected(self):
        self.assertIn("error", databases._validate_csv_headers([""]))


class ImportHwcBadHeaderTest(unittest.TestCase):
    """P6.3 wiring: a malformed CSV header is rejected before any DDL/DML runs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "t.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bad_header_rejected(self):
        csv_path = os.path.join(self.tmpdir, "bad.csv")
        # Includes the required columns so we get past the missing-column check and
        # reach the header whitelist; one header carries an injection-y double quote.
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            f.write('P_NAME,S_NAME,S_NAME_HIP,S_NAME_HD,"evil""col"\n')
            f.write("b,Sun,HIP 1,HD 1,x\n")
        r = databases.import_hwc_csv(csv_path)
        self.assertIn("error", r)
        self.assertIn("invalid column header", r["error"])


# ── P7.2: mocked-network archive readers ─────────────────────────────────────

def _simbad(designations, main_id="* test", **extra):
    """Build a synthetic compute_simbad_lookup result (the archive readers only read
    the `designations` sub-dict + the `error` guard)."""
    r = {"main_id": main_id, "designations": designations}
    r.update(extra)
    return r


def _requests_timeout():
    import requests
    return requests.exceptions.Timeout()


class ComputeExoplanetArchiveTest(unittest.TestCase):
    """compute_exoplanet_archive (opt 2): pscomppars + optional HWO + Mission Exocat,
    with _query_tap and the DB-backed Mission-Exocat lookup mocked."""

    def test_happy_path_designation_and_shape(self):
        calls = []

        def fake_tap(table, where, *a, **k):
            calls.append((table, where))
            if table == "pscomppars":
                return [{"pl_name": "b", "pl_orbsmax": "0.05"}]
            if table == "di_stars_exep":
                return [{"st_spectype": "G2V"}]
            return []

        with mock.patch.object(databases, "_query_tap", fake_tap), \
             mock.patch.object(databases, "_query_mission_exocat_by_designations",
                               lambda d: {"star_name": "X"}):
            r = databases.compute_exoplanet_archive(_simbad({"HD": "HD 10700"}))
        self.assertNotIn("error", r)
        self.assertEqual(set(r), {"simbad", "planets", "hwo", "exocat"})
        self.assertEqual(r["planets"][0]["pl_name"], "b")
        self.assertEqual(r["hwo"][0]["st_spectype"], "G2V")
        self.assertEqual(r["exocat"], {"star_name": "X"})
        # HD priority → hd_name field, and the value flows through _adql_quote.
        self.assertEqual(calls[0], ("pscomppars", "hd_name='HD 10700'"))

    def test_no_designation_error(self):
        r = databases.compute_exoplanet_archive(_simbad({"NAME": "NAME Foo"}))
        self.assertIn("error", r)
        self.assertIn("No usable designation", r["error"])

    def test_error_passthrough(self):
        sr = {"error": "No results found for 'zzz'"}
        self.assertIs(databases.compute_exoplanet_archive(sr), sr)

    def test_no_planets_error(self):
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: []):
            r = databases.compute_exoplanet_archive(_simbad({"HIP": "HIP 8102"}))
        self.assertIn("error", r)
        self.assertIn("No exoplanet data found", r["error"])

    def test_tap_error_classified(self):
        def boom(*a, **k):
            raise _requests_timeout()

        with mock.patch.object(databases, "_query_tap", boom):
            r = databases.compute_exoplanet_archive(_simbad({"HD": "HD 1"}))
        self.assertEqual(r["error"], "NASA Exoplanet Archive request timed out. Try again.")

    def test_hwo_failure_is_non_fatal(self):
        # The optional HWO sub-query swallows errors; the planets result still returns.
        def fake_tap(table, where, *a, **k):
            if table == "pscomppars":
                return [{"pl_name": "b"}]
            raise _requests_timeout()          # HWO sub-query fails

        with mock.patch.object(databases, "_query_tap", fake_tap), \
             mock.patch.object(databases, "_query_mission_exocat_by_designations",
                               lambda d: None):
            r = databases.compute_exoplanet_archive(_simbad({"HD": "HD 1"}))
        self.assertNotIn("error", r)
        self.assertIsNone(r["hwo"])
        self.assertEqual(r["planets"][0]["pl_name"], "b")

    def test_adql_quote_applied_to_designation(self):
        # A designation carrying a single quote is doubled inside the ADQL literal.
        seen = {}

        def fake_tap(table, where, *a, **k):
            seen[table] = where
            return [{"pl_name": "b"}] if table == "pscomppars" else []

        with mock.patch.object(databases, "_query_tap", fake_tap), \
             mock.patch.object(databases, "_query_mission_exocat_by_designations",
                               lambda d: None):
            databases.compute_exoplanet_archive(_simbad({"HD": "O'Brien"}))
        self.assertEqual(seen["pscomppars"], "hd_name='O''Brien'")


class ComputePlanetarySystemsCompositeTest(unittest.TestCase):
    """compute_planetary_systems_composite (opt 3): pscomppars only."""

    def test_happy_path(self):
        with mock.patch.object(databases, "_query_tap",
                               lambda *a, **k: [{"pl_name": "b"}]):
            r = databases.compute_planetary_systems_composite(_simbad({"TIC": "TIC 1"}))
        self.assertEqual(set(r), {"simbad", "planets"})
        self.assertEqual(r["planets"][0]["pl_name"], "b")

    def test_no_designation_error(self):
        r = databases.compute_planetary_systems_composite(_simbad({"NAME": "NAME Foo"}))
        self.assertIn("No usable designation", r["error"])

    def test_no_planets_error(self):
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: []):
            r = databases.compute_planetary_systems_composite(_simbad({"HD": "HD 1"}))
        self.assertIn("No exoplanet data found", r["error"])

    def test_tap_error_classified(self):
        def boom(*a, **k):
            raise _requests_timeout()

        with mock.patch.object(databases, "_query_tap", boom):
            r = databases.compute_planetary_systems_composite(_simbad({"HD": "HD 1"}))
        self.assertEqual(r["error"], "NASA Exoplanet Archive request timed out. Try again.")

    def test_error_passthrough(self):
        sr = {"error": "boom"}
        self.assertIs(databases.compute_planetary_systems_composite(sr), sr)


class ComputeHwoExepTest(unittest.TestCase):
    """compute_hwo_exep (opt 4): di_stars_exep only, priority HIP>HD>TIC>HR>GJ."""

    def test_happy_path_and_gj_priority(self):
        seen = {}

        def fake_tap(table, where, *a, **k):
            seen["table"], seen["where"] = table, where
            return [{"st_spectype": "M3V"}]

        # Only GJ present → gj_name is used (HIP/HD/TIC/HR all absent).
        with mock.patch.object(databases, "_query_tap", fake_tap):
            r = databases.compute_hwo_exep(_simbad({"GJ": "GJ 887"}))
        self.assertEqual(set(r), {"simbad", "hwo"})
        self.assertEqual(seen["table"], "di_stars_exep")
        self.assertEqual(seen["where"], "gj_name='GJ 887'")

    def test_no_designation_error(self):
        # NAME is not part of the HWO priority set → no usable designation.
        r = databases.compute_hwo_exep(_simbad({"NAME": "NAME Foo"}))
        self.assertIn("No usable designation", r["error"])

    def test_no_rows_error(self):
        with mock.patch.object(databases, "_query_tap", lambda *a, **k: []):
            r = databases.compute_hwo_exep(_simbad({"HR": "HR 1"}))
        self.assertIn("No HWO ExEP data found", r["error"])

    def test_tap_error_classified(self):
        def boom(*a, **k):
            raise _requests_timeout()

        with mock.patch.object(databases, "_query_tap", boom):
            r = databases.compute_hwo_exep(_simbad({"HD": "HD 1"}))
        self.assertEqual(r["error"], "HWO ExEP archive request timed out. Try again.")


class _TempDbMixin:
    """Temp-DB setUp/tearDown (auto-seed disabled) that also clears the module-level
    HWC / Mission-Exocat caches so a lazy build from a previous test's DB can't leak."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        self._saved_caches = (databases._HWC_DATA, databases._MISSION_EXOCAT)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "t.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        databases._HWC_DATA = None
        databases._MISSION_EXOCAT = None
        db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        databases._HWC_DATA, databases._MISSION_EXOCAT = self._saved_caches
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class ComputeMissionExocatTest(_TempDbMixin, unittest.TestCase):
    """compute_mission_exocat (opt 5): DB-backed, priority HIP>HD>GJ. Seeded via a
    temp CSV through the real import path."""

    def _seed(self):
        csv_path = os.path.join(self.tmpdir, "missionExocat.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("rowid,star_name,hip_name,hd_name,gj_name,st_spttype\n")
            f.write("1,Tau Ceti,HIP 8102,HD 10700,GJ 71,G8V\n")
            f.write("2,Sirius,HIP 32349,HD 48915,,A1V\n")
        r = databases.import_mission_exocat_csv(csv_path)
        self.assertIn("count", r)

    def test_match_by_hip(self):
        self._seed()
        r = databases.compute_mission_exocat(_simbad({"HIP": "HIP 8102"}))
        self.assertEqual(set(r), {"simbad", "exocat"})
        self.assertEqual(r["exocat"]["star_name"], "Tau Ceti")

    def test_match_by_hd_case_insensitive(self):
        self._seed()
        r = databases.compute_mission_exocat(_simbad({"HD": "hd 48915"}))
        self.assertEqual(r["exocat"]["star_name"], "Sirius")

    def test_not_found_error(self):
        self._seed()
        r = databases.compute_mission_exocat(_simbad({"HIP": "HIP 99999"}))
        self.assertIn("error", r)
        self.assertIn("not found in Mission Exocat", r["error"])

    def test_error_passthrough(self):
        sr = {"error": "boom"}
        self.assertIs(databases.compute_mission_exocat(sr), sr)


class ComputeHwcTest(_TempDbMixin, unittest.TestCase):
    """compute_hwc (opt 6): the real hwc.csv imported into the temp DB, matched by
    designation. HD 149143 / HD 28109 are present in the catalogue."""

    _HWC_CSV = str(pathlib.Path(__file__).resolve().parent.parent / "hwc.csv")

    def _seed(self):
        r = databases.import_hwc_csv(self._HWC_CSV)
        self.assertIn("count", r)
        self.assertGreater(r["count"], 0)

    def test_match_by_hd(self):
        self._seed()
        r = databases.compute_hwc(_simbad({"HD": "HD 149143"}))
        self.assertEqual(set(r), {"simbad", "star_row", "planet_rows"})
        self.assertEqual(r["star_row"]["S_NAME"], "HD 149143")

    def test_match_by_hip(self):
        self._seed()
        r = databases.compute_hwc(_simbad({"HIP": "HIP 81022"}))
        self.assertEqual(r["star_row"]["S_NAME"], "HD 149143")

    def test_planets_sorted_by_semimajor_axis(self):
        self._seed()
        r = databases.compute_hwc(_simbad({"HD": "HD 28109"}))
        names = [p["P_NAME"] for p in r["planet_rows"]]
        # SMAs 0.1357 (b) < 0.308 (c) < 0.411 (d) → sorted b, c, d; star_row is the innermost.
        self.assertEqual(names, ["HD 28109 b", "HD 28109 c", "HD 28109 d"])
        self.assertEqual(r["star_row"]["P_NAME"], "HD 28109 b")

    def test_not_found_error(self):
        self._seed()
        r = databases.compute_hwc(_simbad({"HD": "HD 000000"}))
        self.assertIn("error", r)
        self.assertIn("Habitable Worlds Catalog", r["error"])

    def test_error_passthrough(self):
        sr = {"error": "boom"}
        self.assertIs(databases.compute_hwc(sr), sr)


class QueryTapRetryExhaustionTest(unittest.TestCase):
    """_query_tap wraps requests.get in _with_retries; on exhaustion the exception
    surfaces and the caller classifies it via _network_error_msg. time.sleep is
    patched so the backoff doesn't actually wait."""

    def test_exhaustion_surfaces_and_is_classified(self):
        import core.shared as shared
        import requests

        def always_timeout(*a, **k):
            raise requests.exceptions.Timeout()

        with mock.patch.object(shared.time, "sleep"), \
             mock.patch("requests.get", always_timeout):
            with self.assertRaises(requests.exceptions.Timeout):
                databases._query_tap("pscomppars", "hd_name='HD 1'")
            # The reader turns the same exhausted call into the curated message.
            r = databases.compute_planetary_systems_composite(_simbad({"HD": "HD 1"}))
        self.assertEqual(r["error"], "NASA Exoplanet Archive request timed out. Try again.")


if __name__ == "__main__":
    unittest.main()
