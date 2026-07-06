# tests/test_databases.py — offline unit coverage for core/databases.py helpers.
#
# Phase 6 seeds this file with the P6.2 (_adql_quote) and P6.3 (_validate_csv_headers)
# hardening helpers; Phase 7 (P7.2) expands it with the mocked-network archive readers.
# Pure offline, no network, no Qt.

import os
import pathlib
import shutil
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
