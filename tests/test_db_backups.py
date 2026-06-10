# tests/test_db_backups.py — offline coverage for core.db.prune_star_systems_backups.
#
# Verifies the opt-50 backup pruner keeps the 3 newest dated backups, never
# touches non-backup tables (or a backup-shaped name with a non-8-digit stamp),
# and is a no-op when <= keep_n backups exist. Runs against a tmp fixture DB.

import pathlib
import shutil
import tempfile
import unittest

import core.db as db


class PruneBackupsTest(unittest.TestCase):

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

    def _make_backup(self, stamp):
        self.conn.execute(f"CREATE TABLE star_systems_backup_{stamp} (a INTEGER)")
        self.conn.commit()

    def _tables(self):
        return {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    def test_keeps_three_newest(self):
        for stamp in ["20260101", "20260202", "20260303", "20260404", "20260505"]:
            self._make_backup(stamp)
        result = db.prune_star_systems_backups(keep_n=3)
        self.assertEqual(
            result["kept"],
            ["star_systems_backup_20260505", "star_systems_backup_20260404",
             "star_systems_backup_20260303"],
        )
        self.assertEqual(
            result["dropped"],
            ["star_systems_backup_20260202", "star_systems_backup_20260101"],
        )
        tables = self._tables()
        self.assertNotIn("star_systems_backup_20260101", tables)
        self.assertNotIn("star_systems_backup_20260202", tables)
        self.assertIn("star_systems_backup_20260505", tables)

    def test_noop_when_three_or_fewer(self):
        for stamp in ["20260101", "20260202", "20260303"]:
            self._make_backup(stamp)
        result = db.prune_star_systems_backups(keep_n=3)
        self.assertEqual(result["dropped"], [])
        self.assertEqual(len(result["kept"]), 3)

    def test_never_touches_non_matching_tables(self):
        # star_systems itself (created by the schema), and a backup-shaped name
        # with a non-8-digit suffix, must survive even when dated backups prune.
        self.conn.execute("CREATE TABLE star_systems_backup_keepme (a INTEGER)")
        self.conn.commit()
        for stamp in ["20260101", "20260202", "20260303", "20260404"]:
            self._make_backup(stamp)
        db.prune_star_systems_backups(keep_n=3)
        tables = self._tables()
        self.assertIn("star_systems", tables)
        self.assertIn("star_systems_backup_keepme", tables)
        self.assertNotIn("star_systems_backup_20260101", tables)

    def test_idempotent(self):
        for stamp in ["20260101", "20260202", "20260303", "20260404", "20260505"]:
            self._make_backup(stamp)
        db.prune_star_systems_backups(keep_n=3)
        second = db.prune_star_systems_backups(keep_n=3)
        self.assertEqual(second["dropped"], [])
        self.assertEqual(len(second["kept"]), 3)


if __name__ == "__main__":
    unittest.main()
