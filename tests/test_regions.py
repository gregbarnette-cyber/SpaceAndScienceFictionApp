# tests/test_regions.py — offline coverage for core/regions.py spectral helpers.
#
# Exercises _parse_spectral_class and the _lookup_spectral_type ceiling rule
# (smallest available subtype >= requested; cross-letter fallthrough when all
# entries in a class are cooler than requested) plus white-dwarf rejection.
#
# _lookup_spectral_type reads the main_sequence_stars DB table, so each test
# runs against a controlled in-tmp fixture DB (auto-seeding disabled) seeded
# with a known set of F and G subtypes. No network, no Qt.

import pathlib
import shutil
import tempfile
import unittest

import core.db as db
import core.regions as regions

from tests._queryharness import restore_main_sequence_cache, save_main_sequence_cache


# A deliberately sparse, known main-sequence set: F0/F2/F5/F8 and G0/G2/G5/G8.
# No F9 and no G1, so the ceiling rule and cross-letter fallthrough are testable.
_FIXTURE_CLASSES = ["F0", "F2", "F5", "F8", "G0", "G2", "G5", "G8"]


class SpectralLookupTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None        # skip static CSV seeding
        self.conn = db.get_conn()
        self.conn.executemany(
            "INSERT INTO main_sequence_stars "
            "(spectral_class, b_v, teff_k, abs_mag_vis, abs_mag_bol, bc, "
            " lum, radius, mass, density, lifetime) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(sc, "0", "5000", "5", "5", "-0.1", "1", "1", "1", "1", "1e10")
             for sc in _FIXTURE_CLASSES],
        )
        self.conn.commit()
        # Reset the module-level caches so they reload from the fixture DB (and can't
        # poison a later test — resets both the regions and shared caches).
        self._saved_cache = save_main_sequence_cache()

    def tearDown(self):
        restore_main_sequence_cache(self._saved_cache)
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── _parse_spectral_class ────────────────────────────────────────────────

    def test_parse_basic(self):
        self.assertEqual(regions._parse_spectral_class("G2V"), ("G", 2.0))

    def test_parse_decimal_subtype(self):
        self.assertEqual(regions._parse_spectral_class("M5.5Ve"), ("M", 5.5))

    def test_parse_white_dwarf_returns_none(self):
        # 'A' in 'DA1.9' is preceded by 'D' → negative lookbehind blocks it.
        self.assertEqual(regions._parse_spectral_class("DA1.9"), (None, None))

    def test_parse_empty_and_placeholder(self):
        self.assertEqual(regions._parse_spectral_class(""), (None, None))
        self.assertEqual(regions._parse_spectral_class("N/A"), (None, None))

    # ── _lookup_spectral_type ceiling rule ───────────────────────────────────

    def test_exact_match(self):
        row, key = regions._lookup_spectral_type("G2V")
        self.assertEqual(key, "G2.0")
        self.assertIsNotNone(row)

    def test_ceiling_rounds_up_within_class(self):
        # G1 → smallest available G subtype >= 1 → G2.
        _, key = regions._lookup_spectral_type("G1")
        self.assertEqual(key, "G2.0")

    def test_ceiling_g6_to_g8(self):
        _, key = regions._lookup_spectral_type("G6")
        self.assertEqual(key, "G8.0")

    def test_cross_letter_fallthrough_f9_to_g0(self):
        # No F entry >= 9, so it advances to the hottest entry of the next
        # cooler class (G0).
        _, key = regions._lookup_spectral_type("F9")
        self.assertEqual(key, "G0.0")

    def test_white_dwarf_not_matched(self):
        row, key = regions._lookup_spectral_type("DA1.9")
        self.assertIsNone(row)
        self.assertIsNone(key)

    def test_unknown_class_returns_none(self):
        # 'O' is a valid letter but absent from the fixture → no match.
        row, key = regions._lookup_spectral_type("O5")
        self.assertIsNone(row)
        self.assertIsNone(key)


if __name__ == "__main__":
    unittest.main()
