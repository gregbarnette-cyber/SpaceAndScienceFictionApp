"""CR-30.1 — the WB-owned reference tables: md5 gate, structure, the DB mirrors, the import, no runtime old-file read.

Offline; the DB tests run on a tmp DB (``core.db._DB_PATH`` monkeypatched) and never touch ``data/space_app.db``.
"""
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from core import ms_reference_tables as mrt

_REPO = pathlib.Path(__file__).resolve().parent.parent


class _DataDirMixin:
    def _copy_dir(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for f in os.listdir(mrt._DEFAULT_DIR):
            shutil.copy(os.path.join(mrt._DEFAULT_DIR, f), d)
        return d

    def _use_dir(self, d):
        old = os.environ.get("SPACE_APP_CR30_DATA_DIR")
        os.environ["SPACE_APP_CR30_DATA_DIR"] = d
        mrt.clear_cr30_cache()

        def _restore():
            if old is None:
                os.environ.pop("SPACE_APP_CR30_DATA_DIR", None)
            else:
                os.environ["SPACE_APP_CR30_DATA_DIR"] = old
            mrt.clear_cr30_cache()
        self.addCleanup(_restore)


class Md5GateTest(_DataDirMixin, unittest.TestCase):
    def test_vendored_files_verify(self):
        mrt.clear_cr30_cache()
        v = mrt.verify_all()
        self.assertEqual({k: x["rows"] for k, x in v.items()},
                         {mrt.S1_FILE: 87, mrt.MIST_FILE: 171, mrt.FACTOR_FILE: 888})
        self.assertEqual(mrt.CR30_MD5[mrt.S1_FILE], "2b7746f6339b8b72fb589351c54c0594")
        self.assertEqual(mrt.CR30_MD5[mrt.MIST_FILE], "b212537685cf8d5787df23a03e1f262a")
        self.assertEqual(mrt.CR30_MD5[mrt.FACTOR_FILE], "1ce818caf06a5a1d99b70dfabed9068b")

    def test_raw_s1_file_vendored_with_its_md5(self):
        raw = _REPO / "data" / "cr30" / "mamajek-EEM_dwarf_UBVIJHK_colors_Teff-2022.04.16.txt"
        import hashlib
        self.assertEqual(hashlib.md5(raw.read_bytes()).hexdigest(), "afa3e0c8b249e8b9511b917c03aceb84")
        self.assertIn("afa3e0c8b249e8b9511b917c03aceb84", (_REPO / "data" / "cr30" / "MANIFEST.txt").read_text())

    def test_mismatch_is_loud(self):
        d = self._copy_dir()
        with open(os.path.join(d, mrt.S1_FILE), "ab") as fh:
            fh.write(b"\n")
        self._use_dir(d)
        with self.assertRaisesRegex(mrt.Cr30DataError, "fails its pinned md5"):
            mrt.s1_rows()

    def test_missing_is_loud(self):
        d = self._copy_dir()
        os.remove(os.path.join(d, mrt.MIST_FILE))
        self._use_dir(d)
        with self.assertRaisesRegex(mrt.Cr30DataError, "missing"):
            mrt.mist_tracks()

    def test_structure_check_is_loud(self):
        # a structurally inconsistent file with a matching md5 (the pin patched) still fails loud
        d = self._copy_dir()
        p = os.path.join(d, mrt.S1_FILE)
        body = open(p, encoding="utf-8").read().replace("M9.5V,2350", "M9.5V,2350,EXTRA", 1)
        open(p, "w", encoding="utf-8").write(body)
        import hashlib
        self._use_dir(d)
        old = dict(mrt.CR30_MD5)
        mrt.CR30_MD5[mrt.S1_FILE] = hashlib.md5(open(p, "rb").read()).hexdigest()
        self.addCleanup(mrt.CR30_MD5.update, old)
        with self.assertRaises(mrt.Cr30DataError):
            mrt.s1_rows()

    def test_comment_lines_skipped_and_empty_cell_is_none(self):
        mrt.clear_cr30_cache()
        rows = mrt.s1_rows()
        self.assertEqual(rows[0]["SpT"], "O3V")
        self.assertEqual(rows[-1]["SpT"], "M9.5V")
        self.assertIsNone(rows[-1]["B-V"])                  # S1's placeholder
        self.assertEqual(rows[-1]["Msun"], 0.078)

    def test_mist_duration_is_the_difference(self):
        for t in mrt.mist_tracks():
            self.assertAlmostEqual(t["t_end_yr"] - t["t_zams_yr"], t["ms_duration_yr"],
                                   delta=1e-6 * t["ms_duration_yr"])


class MainSequenceTableTest(unittest.TestCase):
    def test_87_rows_o3v_first_m95v_last(self):
        from core import science
        rows = science.compute_main_sequence_table()
        self.assertEqual(len(rows), 87)
        self.assertEqual(rows[0]["SpT"], "O3V")
        self.assertEqual(rows[-1]["SpT"], "M9.5V")
        self.assertIsNone(rows[-1]["B-V"])
        for k in ("SpT", "Teff", "B-V", "Mv", "BCv", "logL", "R_Rsun", "Msun", "s1_line", "Mbol_computed",
                  "density_computed_gcc", "density_computed_rho_sun", "ms_lifetime_gyr_computed"):
            self.assertIn(k, rows[0])
        g2 = next(r for r in rows if r["SpT"] == "G2V")
        self.assertAlmostEqual(g2["Mbol_computed"], g2["Mv"] + g2["BCv"])


class _TmpDbMixin:
    def setUp(self):
        import core.db as db
        self.db = db
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._old = db._DB_PATH
        db.close_conn()
        db._DB_PATH = pathlib.Path(self.tmp) / "t.db"

        def _restore():
            db.close_conn()
            db._DB_PATH = self._old
        self.addCleanup(_restore)


class DbMirrorTest(_TmpDbMixin, unittest.TestCase):
    """Acceptance 2: a pre-CR-30 main_sequence_stars table cannot supply a value; the mirrors carry the md5."""

    def test_old_table_untouched_and_unread(self):
        # a pre-CR-30 DB with a poisoned old main_sequence_stars row
        conn = sqlite3.connect(self.db._DB_PATH)
        conn.execute("CREATE TABLE main_sequence_stars (id INTEGER PRIMARY KEY AUTOINCREMENT, spectral_class TEXT,"
                     " b_v TEXT, teff_k TEXT, abs_mag_vis TEXT, abs_mag_bol TEXT, bc TEXT, lum TEXT, radius TEXT,"
                     " mass TEXT, density TEXT, lifetime TEXT)")
        conn.execute("INSERT INTO main_sequence_stars (spectral_class, bc, mass, lum, teff_k) "
                     "VALUES ('G2V', '-9.99', '9.99', '999', '9999')")
        conn.commit()
        conn.close()
        c = self.db.get_conn()
        # untouched
        self.assertEqual(c.execute("SELECT COUNT(*) FROM main_sequence_stars").fetchone()[0], 1)
        # unread: the region lookup and the main-sequence table give S1's G2V, not the poisoned row
        from core import regions, science
        s1, _p = regions._lookup_s1("G2V")
        self.assertEqual(s1["BCv"], -0.085)
        self.assertEqual(s1["Msun"], 1.0)
        g2 = next(r for r in science.compute_main_sequence_table() if r["SpT"] == "G2V")
        self.assertEqual(g2["Teff"], 5770.0)

    def test_mirrors_seeded_with_md5_and_reseeded_when_stale(self):
        c = self.db.get_conn()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM ms_reference_s1").fetchone()[0], 87)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM ms_reference_mist").fetchone()[0], 171)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM ms_reference_factor").fetchone()[0], 888)
        self.assertEqual(c.execute("SELECT DISTINCT source_md5 FROM ms_reference_s1").fetchall()[0][0],
                         mrt.CR30_MD5[mrt.S1_FILE])
        c.execute("UPDATE ms_reference_s1 SET source_md5 = 'stale'")
        c.commit()
        w = self.db.seed_cr30_mirrors(c)
        self.assertEqual(w["ms_reference_s1"], 87)
        self.assertEqual(w["ms_reference_mist"], 0)        # already current → untouched

    def test_current_mirror_takes_no_write_lock(self):
        c = self.db.get_conn()
        other = sqlite3.connect(self.db._DB_PATH, timeout=0.1)
        other.execute("BEGIN IMMEDIATE")                   # another writer holds the lock
        try:
            self.assertEqual(self.db.seed_cr30_mirrors(c), {"ms_reference_s1": 0, "ms_reference_mist": 0,
                                                             "ms_reference_factor": 0})
        finally:
            other.execute("ROLLBACK")
            other.close()

    def test_import_reports_a_failed_seed(self):
        from unittest import mock
        from core import databases
        with mock.patch("core.db.seed_cr30_mirrors", side_effect=sqlite3.OperationalError("database is locked")):
            r = databases.import_cr30_reference_tables()
        self.assertIn("error", r)

    def test_get_conn_survives_missing_data_dir(self):
        old = os.environ.get("SPACE_APP_CR30_DATA_DIR")
        os.environ["SPACE_APP_CR30_DATA_DIR"] = os.path.join(self.tmp, "nope")
        mrt.clear_cr30_cache()
        try:
            c = self.db.get_conn()                         # never raises Cr30DataError
            self.assertEqual(c.execute("SELECT COUNT(*) FROM ms_reference_s1").fetchone()[0], 0)
        finally:
            if old is None:
                os.environ.pop("SPACE_APP_CR30_DATA_DIR", None)
            else:
                os.environ["SPACE_APP_CR30_DATA_DIR"] = old
            mrt.clear_cr30_cache()

    def test_import_loads_all_three(self):
        from core import databases
        r = databases.import_cr30_reference_tables()
        self.assertNotIn("error", r)
        self.assertEqual({t["table"]: t["rows"] for t in r["tables"]},
                         {"ms_reference_s1": 87, "ms_reference_mist": 171, "ms_reference_factor": 888})
        status = {t["table"]: t["rows"] for t in self.db.get_table_status()}
        self.assertEqual(status["CR-30 S1 Dwarf Sequence"], 87)
        self.assertEqual(status["CR-30 MIST v2.5 Lifetimes"], 171)
        self.assertEqual(status["CR-30 BHAC15 Over-read Factors"], 888)


class NoRuntimeOldFileReadTest(unittest.TestCase):
    """Acceptance 3: no runtime read of the old table and no legacy 2.52 / 4.85 region luminosity."""
    _ROOTS = ("core", "gui")
    _FILES = ("query.py", "main.py", "gui_main.py")

    def _sources(self):
        for root in self._ROOTS:
            for p in (_REPO / root).rglob("*.py"):
                yield p
        for f in self._FILES:
            p = _REPO / f
            if p.exists():
                yield p

    def test_no_old_file_or_old_table_read(self):
        for p in self._sources():
            src = p.read_text(encoding="utf-8")
            self.assertNotIn("propertiesOfMainSequenceStars", src, p)
            self.assertNotRegex(src, r"FROM\s+main_sequence_stars", str(p))
            self.assertNotRegex(src, r"2\.52\s*\*\*", str(p))           # the legacy region step
            self.assertNotRegex(src, r"4\.85\s*-\s*bcAbs", str(p))      # the legacy zero point

    def test_vendored_files_tracked_by_git(self):
        try:
            out = subprocess.run(["git", "ls-files", "data/cr30"], cwd=_REPO, capture_output=True, text=True,
                                 timeout=20)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git unavailable")
        if out.returncode != 0:
            self.skipTest("not a git checkout")
        tracked = set(out.stdout.split())
        if not tracked:
            # pre-commit working tree: the files must at least not be ignored
            chk = subprocess.run(["git", "check-ignore", "-q", "data/cr30/" + mrt.S1_FILE], cwd=_REPO)
            self.assertNotEqual(chk.returncode, 0, "data/cr30/ is git-ignored")
            return
        for f in (mrt.S1_FILE, mrt.MIST_FILE, mrt.FACTOR_FILE, "MANIFEST.txt"):
            self.assertIn("data/cr30/" + f, tracked)


if __name__ == "__main__":
    unittest.main()


# ── CR-30.1 acceptance 4 (plan §13.6 T12): the Utilities import panel, offscreen ─────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QLabel
    _GUI_OK = True
except Exception:                       # pragma: no cover
    _GUI_OK = False


class _FakeNav:
    def currentItem(self):
        return None


class _FakeWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()

    def statusBar(self):
        class _SB:
            def showMessage(self, *a):
                pass
        return _SB()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class ImportPanelSmokeTest(_TmpDbMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_imports_all_three(self):
        from core import databases
        from gui.panels.csv_utility import ImportMainSequencePanel
        p = ImportMainSequencePanel(_FakeWindow())
        self.assertIn("CR-30", p._run_btn.text())
        p._on_done(databases.import_cr30_reference_tables())        # the background call, run synchronously
        text = " ".join(w.text() for w in p.findChildren(QLabel))
        for f in (mrt.S1_FILE, mrt.MIST_FILE, mrt.FACTOR_FILE):
            self.assertIn(f, text)
        for md5 in mrt.CR30_MD5.values():
            self.assertIn(md5, text)
        self.assertIn("87 rows", text)
        self.assertIn("171 rows", text)
        self.assertIn("888 rows", text)
