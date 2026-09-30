# tests/test_cr24_tables.py — CR-24: the WB-owned V_ISM file (md5, rows, cross-check with CR-26) and the R&L 2008
# Table 16 cloud vectors + the DQ2 cloud set (spec §Units). Offline, pure.

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from core import ism_velocity_tables as ivt

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CSV = os.path.join(_REPO, "data", "cr24", ivt.CR24_FILE)


class Cr24DataFileTest(unittest.TestCase):
    def setUp(self):
        ivt.clear_cr24_cache()

    def tearDown(self):
        ivt.clear_cr24_cache()

    def test_md5_rows_and_cross_check(self):
        import hashlib
        with open(_CSV, "rb") as fh:
            raw = fh.read()
        self.assertEqual(hashlib.md5(raw).hexdigest(), "ffd164238d055d9134fe65bb9f9df097")
        self.assertNotIn(b"\r", raw)                                   # vendored byte-identical, LF only
        t = ivt.load_cr24_table()
        self.assertEqual(len(t), 36)
        from core import stellar_wind_tables as swt
        self.assertEqual(set(t), {r["row_key"] for r in swt.load_cr26_tables()["MEASURED"].values()})
        self.assertEqual(ivt.measured_row_vism("ev_lac"), 45.0)
        self.assertIsInstance(ivt.measured_row_vism("eps_eri"), float)   # Q7: emitted as a float
        self.assertEqual(ivt.measured_row_vism("alf_cen_b"), 25.0)
        self.assertIsNone(ivt.measured_row_vism("nope"))

    def test_git_attributes_keep_it_byte_identical(self):
        out = subprocess.run(["git", "check-attr", "text", "data/cr24/" + ivt.CR24_FILE], cwd=_REPO,
                             capture_output=True, text=True).stdout
        self.assertIn("text: unset", out)

    def test_tampered_or_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"SPACE_APP_CR24_DATA_DIR": d}):
                with self.assertRaises(ivt.Cr24DataError):
                    ivt.load_cr24_table()                              # missing
                ivt.clear_cr24_cache()
                shutil.copy(_CSV, os.path.join(d, ivt.CR24_FILE))
                with open(os.path.join(d, ivt.CR24_FILE), "ab") as fh:
                    fh.write(b"x")
                with self.assertRaises(ivt.Cr24DataError) as cm:
                    ivt.load_cr24_table()                              # md5
                self.assertIn("md5", str(cm.exception))

    def test_data_error_is_a_curated_exit_1(self):
        from tests._queryharness import run_query_inproc
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"SPACE_APP_CR24_DATA_DIR": d}):
            ivt.clear_cr24_cache()
            code, p, _ = run_query_inproc("exclusion-system", "--component",
                                          "id=E,mass=0.8112,class=K2V,main_id=* eps Eri", "--alpha", "0.4")
        self.assertEqual(code, 1)
        self.assertIn("CR-24 data file missing", p["error"])


class CloudVectorTest(unittest.TestCase):
    def test_lic_vector_and_the_fifteen(self):
        u, v, w = ivt.cloud_vector("LIC")
        self.assertAlmostEqual(u, -23.01, places=2)
        self.assertAlmostEqual(v, -2.83, places=2)
        self.assertAlmostEqual(w, -5.57, places=2)
        self.assertEqual(len(ivt.cloud_names()), 15)
        for n in ivt.cloud_names():
            v0 = ivt.CLOUDS[n][0]
            self.assertAlmostEqual(sum(x * x for x in ivt.cloud_vector(n)) ** 0.5, v0, places=9)

    def test_dq2_cloud_set_and_distances(self):
        self.assertEqual(set(ivt.cloud_set()), set(ivt.CLOUD_SET_EXPECTED))
        lic = ivt.cloud_vector("LIC")
        want = {"LIC": 0.0, "Leo": 2.60, "Eri": 4.29, "G": 6.72, "Mic": 9.68, "Aur": 10.42, "Blue": 11.69,
                "NGP": 13.89, "Hyades": 14.57, "Gem": 17.28, "Oph": 18.11, "Vel": 22.09, "Cet": 36.88,
                "Dor": 38.79, "Aql": 42.19}
        for n, d in want.items():
            self.assertAlmostEqual(ivt._dist(ivt.cloud_vector(n), lic), d, delta=0.01, msg=n)


if __name__ == "__main__":
    unittest.main()
