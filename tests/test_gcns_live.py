# tests/test_gcns_live.py — network test (auto-skipped when GAVO is unreachable).
#
# Verifies the live GAVO gcns.main / gcns.missing_10mas schema still matches what
# core.databases.compute_gcns_ingest depends on: the exact columns it SELECTs, the
# kpc distance unit, and that the catalogue still meets the configured row floors.
# Pulls only a handful of rows (maxrec small) — it does NOT download the catalogue.

import unittest

from tests._netcheck import gavo_reachable, live_enabled
import core.databases as databases

_ONLINE = live_enabled() and gavo_reachable()

_MAIN_COLS = {
    "source_id", "ra", "dec", "parallax", "parallax_error",
    "dist_16", "dist_50", "dist_84",
    "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag",
    "adoptedrv", "wd_prob", "gcns_prob", "name_2mass",
}
_MISSING_COLS = {"main_id", "otype", "ra", "dec", "plx_value"}
_RESOLVED_COLS = {"source_id1", "source_id2", "separation", "mag_diff",
                  "proj_sep", "bin", "bound"}


@unittest.skipUnless(_ONLINE, "GAVO (dc.g-vo.org) not reachable")
class TestGcnsLive(unittest.TestCase):

    def _svc(self):
        import pyvo
        return pyvo.dal.TAPService(databases._GCNS_TAP_URL)

    def test_main_columns_present(self):
        r = self._svc().run_sync(
            "SELECT column_name FROM TAP_SCHEMA.columns WHERE table_name='gcns.main'",
            maxrec=400,
        )
        cols = {str(row["column_name"]) for row in r}
        missing = _MAIN_COLS - cols
        self.assertFalse(missing, f"gcns.main lost expected columns: {missing}")

    def test_missing_table_columns_present(self):
        r = self._svc().run_sync(
            "SELECT column_name FROM TAP_SCHEMA.columns WHERE table_name='gcns.missing_10mas'",
            maxrec=400,
        )
        cols = {str(row["column_name"]) for row in r}
        missing = _MISSING_COLS - cols
        self.assertFalse(missing, f"gcns.missing_10mas lost expected columns: {missing}")

    def test_resolved_table_columns_present(self):
        r = self._svc().run_sync(
            "SELECT column_name FROM TAP_SCHEMA.columns WHERE table_name='gcns.resolvedss'",
            maxrec=400,
        )
        cols = {str(row["column_name"]) for row in r}
        missing = _RESOLVED_COLS - cols
        self.assertFalse(missing, f"gcns.resolvedss lost expected columns: {missing}")

    def test_row_counts_meet_floors(self):
        svc = self._svc()
        n_main = int(svc.run_sync("SELECT COUNT(*) AS n FROM gcns.main")[0]["n"])
        n_miss = int(svc.run_sync("SELECT COUNT(*) AS n FROM gcns.missing_10mas")[0]["n"])
        n_res  = int(svc.run_sync("SELECT COUNT(*) AS n FROM gcns.resolvedss")[0]["n"])
        self.assertGreaterEqual(n_main, databases._GCNS_MAIN_MIN_ROWS)
        self.assertGreaterEqual(n_miss, databases._GCNS_MISSING_MIN_ROWS)
        self.assertGreaterEqual(n_res, databases._GCNS_RESOLVED_MIN_ROWS)

    def test_proj_sep_unit_is_au(self):
        """proj_sep must be in AU: a nearby resolved pair sits at tens-hundreds AU."""
        r = self._svc().run_sync(
            "SELECT TOP 1 proj_sep FROM gcns.resolvedss "
            "WHERE proj_sep IS NOT NULL ORDER BY proj_sep ASC"
        )
        closest_au = float(r[0]["proj_sep"])
        self.assertTrue(1.0 < closest_au < 1e5, f"proj_sep={closest_au} not AU-scaled")

    def test_distance_unit_is_kpc(self):
        """dist_50 must be in kpc: the nearest GCNS source sits ~0.0013 kpc (Proxima)."""
        r = self._svc().run_sync(
            "SELECT TOP 1 dist_50 FROM gcns.main WHERE dist_50 IS NOT NULL ORDER BY parallax DESC"
        )
        nearest_kpc = float(r[0]["dist_50"])
        self.assertTrue(0.0 < nearest_kpc < 0.01, f"dist_50={nearest_kpc} not kpc-scaled")


if __name__ == "__main__":
    unittest.main()
