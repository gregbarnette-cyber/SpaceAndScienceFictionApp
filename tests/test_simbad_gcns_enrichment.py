# tests/test_simbad_gcns_enrichment.py — offline coverage for Phase M5.
#
# M5 attaches an optional top-level "gcns" key to compute_simbad_lookup's return
# (parallel to "hypatia"), built by _simbad_gcns_block from the Gaia EDR3/DR3 id in
# the SIMBAD designations. It is non-fatal and silent: None when there is no Gaia
# id, the id is absent from GCNS, or the gcns_stars table is empty/missing.
#
# Tests run fully offline: the gcns_stars table is a seeded temp SQLite DB, and the
# one end-to-end wiring test mocks the SIMBAD network touchpoints.

import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.databases as databases


_GAIA_ID = 4472832130942575872   # Barnard's Star, Gaia DR3


class SimbadGcnsEnrichmentTest(unittest.TestCase):

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

    def _seed_one(self):
        self.conn.execute(
            "INSERT INTO gcns_stars (gaia_source_id, ra, dec, parallax, dist_pc, "
            "dist_lo_pc, dist_hi_pc, light_years, phot_g_mean_mag, phot_bp_mean_mag, "
            "phot_rp_mean_mag, wd_prob, astrom_reliable_prob, spectral_type, star_name, "
            "app_magnitude, in_gcns, in_simbad, distance_method, gcns_table) "
            "VALUES (?, 269.45, 4.69, 546.98, 1.8380, 1.8282, 1.8475, 5.9947, "
            "8.19, 9.79, 6.96, 0.20, 1.0, 'M4V', 'NAME Barnard star', 9.511, "
            "1, 1, 'gcns_bayesian', 'main')",
            (_GAIA_ID,),
        )
        self.conn.commit()

    # ── _simbad_gcns_block (the new unit) ────────────────────────────────────

    def test_block_returns_row_with_uncertainty_for_present_id(self):
        self._seed_one()
        block = databases._simbad_gcns_block({"Gaia EDR3": f"Gaia DR3 {_GAIA_ID}"})
        self.assertIsNotNone(block)
        self.assertEqual(block["gaia_source_id"], _GAIA_ID)
        self.assertEqual(block["distance_method"], "gcns_bayesian")
        # The headline differentiator: Bayesian distance WITH a 16th/84th error bar.
        self.assertIsNotNone(block["dist_lo_pc"])
        self.assertIsNotNone(block["dist_hi_pc"])
        self.assertLess(block["dist_lo_pc"], block["dist_pc"])
        self.assertGreater(block["dist_hi_pc"], block["dist_pc"])

    def test_block_accepts_both_dr3_and_edr3_prefixes(self):
        self._seed_one()
        for raw in (f"Gaia DR3 {_GAIA_ID}", f"Gaia EDR3 {_GAIA_ID}"):
            with self.subTest(raw=raw):
                block = databases._simbad_gcns_block({"Gaia EDR3": raw})
                self.assertIsNotNone(block)
                self.assertEqual(block["gaia_source_id"], _GAIA_ID)

    def test_block_none_when_no_gaia_id(self):
        self._seed_one()
        self.assertIsNone(databases._simbad_gcns_block({"Gaia EDR3": None}))
        self.assertIsNone(databases._simbad_gcns_block({}))
        self.assertIsNone(databases._simbad_gcns_block({"Gaia EDR3": "not a gaia id"}))

    def test_block_none_when_id_absent_from_gcns(self):
        self._seed_one()
        self.assertIsNone(
            databases._simbad_gcns_block({"Gaia EDR3": "Gaia DR3 999999999999999999"}))

    def test_block_none_when_table_empty(self):
        # No seed → gcns_stars empty. Must be non-fatal (returns None, no raise).
        self.assertIsNone(
            databases._simbad_gcns_block({"Gaia EDR3": f"Gaia DR3 {_GAIA_ID}"}))

    # ── wiring: compute_simbad_lookup attaches the key (SIMBAD mocked) ────────

    def test_compute_simbad_lookup_attaches_gcns_key(self):
        self._seed_one()

        class _FakeTable(list):
            def __init__(self, rowdict, colnames):
                super().__init__([rowdict])
                self.colnames = colnames

        class _FakeSimbad:
            def query_object(self, name):
                return _FakeTable({"main_id": "NAME Barnard star"}, ["main_id"])

        ids = [{"id": f"Gaia DR3 {_GAIA_ID}"}, {"id": "HIP 87937"}]

        with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _FakeSimbad()), \
             mock.patch.object(databases, "_with_retries", lambda fn, *a, **k: fn(*a)), \
             mock.patch("astroquery.simbad.Simbad.query_objectids", lambda name: ids):
            result = databases.compute_simbad_lookup("Barnard's Star")

        self.assertNotIn("error", result)
        self.assertIn("gcns", result)                       # key always present
        self.assertIsNotNone(result["gcns"])                # and populated here
        self.assertEqual(result["gcns"]["gaia_source_id"], _GAIA_ID)
        self.assertEqual(result["designations"]["Gaia EDR3"], f"Gaia DR3 {_GAIA_ID}")

    def test_compute_simbad_lookup_gcns_none_when_not_in_census(self):
        # gcns_stars empty → the key is present but None; the SIMBAD result is intact.
        class _FakeTable(list):
            def __init__(self, rowdict, colnames):
                super().__init__([rowdict])
                self.colnames = colnames

        class _FakeSimbad:
            def query_object(self, name):
                return _FakeTable({"main_id": "NAME Barnard star"}, ["main_id"])

        ids = [{"id": f"Gaia DR3 {_GAIA_ID}"}]
        with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _FakeSimbad()), \
             mock.patch.object(databases, "_with_retries", lambda fn, *a, **k: fn(*a)), \
             mock.patch("astroquery.simbad.Simbad.query_objectids", lambda name: ids):
            result = databases.compute_simbad_lookup("Barnard's Star")

        self.assertIn("gcns", result)
        self.assertIsNone(result["gcns"])
        self.assertEqual(result["main_id"], "NAME Barnard star")


if __name__ == "__main__":
    unittest.main()
