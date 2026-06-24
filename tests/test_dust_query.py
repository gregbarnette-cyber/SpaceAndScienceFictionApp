# tests/test_dust_query.py — Phase T2 Part A (dust / ISM query path) contracts.
#
# core/dust.py is the ONLY module that imports dustmaps/healpy, lazily, so the
# stellar layer stays importable on a checkout without the optional 'dust' extra.
# These tests split into:
#   - NON-GATED (always run): the dependency-isolation guard, the extra-missing
#     error path, and the engine math/seam/coverage logic via a MOCKED map (no
#     dustmaps data needed — astropy geometry runs for real, only the map query
#     is faked). This is the bulk of the coverage and runs everywhere.
#   - GATED on dustmaps importability: the validation/exit-code matrix and the
#     map-not-fetched path (need dustmaps installed to reach them).
#   - GATED on importability AND a fetched map: the real-data sightline anchor
#     (the maintainer fetches via CLI option 59; skipped otherwise).
#
# Subprocess harness mirrors tests/test_query_phase_n.py / test_query_phase_t.py.

import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

import core.dust as dust
from tests._dustcheck import dustmaps_importable, maps_fetched

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/dust_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    proc = subprocess.run([sys.executable, str(_REPO / "query.py"), *cmd_args],
                          capture_output=True, text=True, cwd=str(_REPO), env=_ENV)
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


# A fake map query: Leike → constant density 10.0 e-fold/kpc (σ 1.0); Edenhofer →
# 0.1 ZGR23 E/pc (σ 0.01). With the pinned conversions this gives exactly
# checkable A_V per bin. `nan_for` forces out-of-coverage on a chosen map.
def _make_fake_query(nan_for=None):
    def _q(mk, qobj, coords):
        n = len(coords)
        if mk == nan_for:
            return np.full(n, np.nan), np.full(n, np.nan)
        if mk == "leike2020":
            return np.full(n, 10.0), np.full(n, 1.0)
        return np.full(n, 0.1), np.full(n, 0.01)   # edenhofer2023
    return _q


class DustIsolationTest(unittest.TestCase):
    """Importing the stellar layer must NOT pull dustmaps/healpy (the whole point
    of the forked core/dust.py)."""

    def test_calculators_does_not_import_dustmaps(self):
        code = ("import core.calculators, sys; "
                "print('dustmaps' in sys.modules or 'healpy' in sys.modules)")
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, cwd=str(_REPO))
        self.assertEqual(proc.stdout.strip(), "False", proc.stdout + proc.stderr)


class DustExtraMissingTest(unittest.TestCase):
    """With the extra unavailable, every entry point returns the curated error —
    never a traceback. Forces the path even where dustmaps IS installed."""

    def setUp(self):
        self._patch = mock.patch.object(dust, "_dustmaps_available", lambda: False)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_sightline(self):
        r = dust.compute_dust_sightline(l=10, b=5, dist_end_pc=100)
        self.assertIn("error", r)
        self.assertIn("dust", r["error"].lower())

    def test_between(self):
        r = dust.compute_dust_between(star1="Sol", star2="Sirius")
        self.assertIn("error", r)

    def test_fetch(self):
        r = dust.compute_dust_fetch()
        self.assertIn("error", r)


class DustEngineMathTest(unittest.TestCase):
    """The integration / conversion / seam / coverage / cumulative logic, with a
    mocked map (no dustmaps data). astropy SkyCoord geometry runs for real."""

    def setUp(self):
        self._patches = [
            mock.patch.object(dust, "_dustmaps_available", lambda: True),
            mock.patch.object(dust, "_load_map", lambda mk: ("FAKE", None)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_leike_conversion_and_cumulative(self):
        with mock.patch.object(dust, "_query_native", _make_fake_query()):
            r = dust.compute_dust_sightline(l=120, b=0, dist_start_pc=0,
                                            dist_end_pc=100, n_steps=10,
                                            map_sel="near-field")
        self.assertNotIn("error", r)
        self.assertEqual(len(r["bins"]), 10)
        self.assertEqual(r["units"], "A_V_mag_RV3.1")
        self.assertAlmostEqual(r["rv"], 3.1)
        # density 10 e-fold/kpc over a 10-pc bin: A_V = 1.30506·(10·10/1000).
        expect_bin = dust._LEIKE_TAU_TO_AV * (10.0 * 10.0 / 1000.0)
        self.assertAlmostEqual(r["bins"][0]["a_v"], expect_bin, places=6)
        self.assertEqual(r["bins"][0]["map"], "leike2020")
        self.assertEqual(r["bins"][0]["native_value"], 10.0)
        self.assertIn("efoldings", r["bins"][0]["native_quantity"])
        self.assertAlmostEqual(r["cumulative_a_v"], 10 * expect_bin, places=6)
        # σ band present and ordered.
        self.assertLess(r["bins"][0]["a_v_lo"], r["bins"][0]["a_v"])
        self.assertGreater(r["bins"][0]["a_v_hi"], r["bins"][0]["a_v"])
        self.assertGreater(r["cumulative_a_v_hi"], r["cumulative_a_v"])

    def test_edenhofer_conversion(self):
        with mock.patch.object(dust, "_query_native", _make_fake_query()):
            r = dust.compute_dust_sightline(l=120, b=0, dist_start_pc=100,
                                            dist_end_pc=200, n_steps=10,
                                            map_sel="edenhofer")
        # density 0.1 E/pc over a 10-pc bin: A_V = 2.8·(0.1·10).
        expect_bin = dust._AV_PER_ZGR23_E * (0.1 * 10.0)
        self.assertAlmostEqual(r["bins"][0]["a_v"], expect_bin, places=6)
        self.assertEqual(r["bins"][0]["map"], "edenhofer2023")
        self.assertIn("ZGR23", r["bins"][0]["native_quantity"])

    def test_auto_seam_ownership(self):
        with mock.patch.object(dust, "_query_native", _make_fake_query()):
            r = dust.compute_dust_sightline(l=120, b=0, dist_start_pc=0,
                                            dist_end_pc=100, n_steps=10,
                                            map_sel="auto")
        # centers at 5,15,...,95 → ≤69 pc Leike, >69 pc Edenhofer.
        owners = [b["map"] for b in r["bins"]]
        self.assertEqual(owners[:7], ["leike2020"] * 7)
        self.assertEqual(owners[7:], ["edenhofer2023"] * 3)
        # the 65-pc bin is within 5 pc of the 69-pc seam → flagged.
        self.assertTrue(r["bins"][6]["seam"])
        self.assertIn("seam_crossed", r["notes"])

    def test_out_of_coverage_null_not_clamped(self):
        # Edenhofer returns NaN beyond the seam → those bins are null, not 0.
        with mock.patch.object(dust, "_query_native",
                               _make_fake_query(nan_for="edenhofer2023")):
            r = dust.compute_dust_sightline(l=120, b=0, dist_start_pc=0,
                                            dist_end_pc=100, n_steps=10,
                                            map_sel="auto")
        self.assertIsNone(r["bins"][9]["a_v"])
        self.assertIn("out_of_coverage", r["bins"][9]["notes"])
        self.assertIn("out_of_coverage", r["notes"])
        # cumulative counts only the covered (Leike) bins, unchanged across nulls.
        covered = [b for b in r["bins"] if b["a_v"] is not None]
        self.assertAlmostEqual(r["cumulative_a_v"],
                               sum(b["a_v"] for b in covered), places=6)

    def test_between_geometry_and_endpoints(self):
        with mock.patch.object(dust, "_query_native", _make_fake_query()):
            r = dust.compute_dust_between(star1="Sol", star2="Sol",
                                          n_steps=5, map_sel="near-field")
        # Sol→Sol is a degenerate point.
        self.assertIn("error", r)
        with mock.patch.object(dust, "_query_native", _make_fake_query()):
            # mock a non-Sol endpoint via a patched resolver position.
            with mock.patch.object(dust, "_endpoint", side_effect=[
                {"pos_pc": (0.0, 0.0, 0.0), "info": {"name": "Sol"}},
                {"pos_pc": (10.0, 0.0, 0.0), "info": {"name": "X"}},
            ]):
                r = dust.compute_dust_between(star1="Sol", star2="X",
                                              n_steps=5, map_sel="near-field")
        self.assertNotIn("error", r)
        self.assertEqual(r["frame"], "star-to-star")
        self.assertAlmostEqual(r["separation_pc"], 10.0)
        self.assertEqual(r["star1_info"]["name"], "Sol")
        self.assertEqual(len(r["bins"]), 5)
        # per-bin dist_pc is the path distance from star1 (0→10 pc).
        self.assertLess(r["bins"][0]["dist_pc"], r["bins"][-1]["dist_pc"])


class DustMapStatusTest(unittest.TestCase):
    """get_dust_map_status() is pure-pathlib — works WITHOUT the dust extra (no
    dustmaps import) and reports file presence/size for the opt-57 status panel."""

    def test_shape_and_keys(self):
        rows = dust.get_dust_map_status()
        self.assertEqual([r["map"] for r in rows], ["leike2020", "edenhofer2023"])
        for r in rows:
            self.assertEqual(set(r), {"map", "label", "path", "present", "size_mb"})
            self.assertIn("Dust Map", r["label"])
            self.assertIsInstance(r["present"], bool)
            # size_mb is a float when present, None when missing.
            self.assertTrue(r["size_mb"] is None or isinstance(r["size_mb"], float))

    def test_missing_file_reports_none_size(self):
        with mock.patch.object(dust, "_DUST_CACHE_DIR",
                               pathlib.Path(tempfile.mkdtemp())):
            rows = dust.get_dust_map_status()
        self.assertTrue(all(r["present"] is False for r in rows))
        self.assertTrue(all(r["size_mb"] is None for r in rows))

    def test_present_file_reports_size(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        sub, fn = dust._MAP_FILE["leike2020"]
        (tmp / sub).mkdir(parents=True)
        (tmp / sub / fn).write_bytes(b"x" * 2048)
        with mock.patch.object(dust, "_DUST_CACHE_DIR", tmp):
            rows = {r["map"]: r for r in dust.get_dust_map_status()}
        self.assertTrue(rows["leike2020"]["present"])
        self.assertAlmostEqual(rows["leike2020"]["size_mb"], round(2048 / 1e6, 1))
        self.assertFalse(rows["edenhofer2023"]["present"])


@unittest.skipUnless(dustmaps_importable(), "optional 'dust' extra not installed")
class DustValidationContractTest(unittest.TestCase):
    """Validation reachable only with the extra installed (the availability gate
    runs first). In-process + subprocess exit-code matrix."""

    def test_direction_mode(self):
        self.assertIn("error", dust.compute_dust_sightline(dist_end_pc=100))
        self.assertIn("error", dust.compute_dust_sightline(l=1, b=2, ra=3, dec=4,
                                                           dist_end_pc=100))

    def test_dist_and_step_validation(self):
        self.assertIn("error", dust.compute_dust_sightline(l=1, b=2))  # no end
        self.assertIn("error", dust.compute_dust_sightline(l=1, b=2,
                                                           dist_start_pc=50,
                                                           dist_end_pc=10))
        self.assertIn("error", dust.compute_dust_sightline(l=1, b=2,
                                                           dist_end_pc=100,
                                                           step_pc=0))
        self.assertIn("error", dust.compute_dust_sightline(l=1, b=2,
                                                           dist_end_pc=100,
                                                           n_steps=0))

    def test_subprocess_exit_codes(self):
        # core validation → curated exit 1.
        code, payload, _ = _run("dust-sightline")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        code, payload, _ = _run("dust-sightline", "--l", "1", "--b", "2",
                                "--dist-start", "50", "--dist-end", "10")
        self.assertEqual(code, 1)
        # bad --map → argparse exit 2.
        code, _, _ = _run("dust-sightline", "--l", "1", "--b", "2",
                          "--dist-end", "100", "--map", "bogus")
        self.assertEqual(code, 2)
        # dust-between needs one endpoint per side → argparse exit 2.
        code, _, _ = _run("dust-between")
        self.assertEqual(code, 2)
        code, _, _ = _run("dust-between", "--star1", "Sol", "--id1", "123",
                          "--star2", "Sirius")
        self.assertEqual(code, 2)

    def test_map_not_fetched(self):
        # Point the cache at an empty temp dir → loading any map is "not fetched".
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(dust, "_DUST_CACHE_DIR", pathlib.Path(td)), \
                 mock.patch.dict(dust._MAP_CACHE, {}, clear=True):
                q, err = dust._load_map("leike2020")
        self.assertIsNone(q)
        self.assertIn("not fetched", err["error"])


@unittest.skipUnless(dustmaps_importable() and maps_fetched(),
                     "dust maps not fetched (run CLI option 59)")
class DustRealAnchorTest(unittest.TestCase):
    """Real-data sightline against the fetched Leike map. A high-latitude, short
    sightline through the Local Bubble cavity should carry only modest A_V."""

    def test_local_sightline(self):
        dust._MAP_CACHE.clear()
        r = dust.compute_dust_sightline(l=0, b=90, dist_start_pc=0,
                                        dist_end_pc=60, n_steps=30,
                                        map_sel="near-field")
        self.assertNotIn("error", r)
        self.assertEqual(len(r["bins"]), 30)
        # Toward the Galactic pole within the cavity: small, non-negative column.
        self.assertGreaterEqual(r["cumulative_a_v"], 0.0)
        self.assertLess(r["cumulative_a_v"], 1.0)
        # every covered bin has a finite native value + A_V.
        for b in r["bins"]:
            if b["a_v"] is not None:
                self.assertTrue(math.isfinite(b["native_value"]))


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    _GUI_OK = True
except Exception:
    _GUI_OK = False


class _FakeNav:
    def show(self): pass
    def hide(self): pass


class _FakeWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()

    def statusBar(self):
        class _SB:
            def showMessage(self, *a): pass
        return _SB()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class FetchDustMapPanelSmoke(unittest.TestCase):
    """Headless GUI smoke for the option-59 GUI surface (Utilities nav). Drives
    the render path directly (no thread / no map data)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from gui.panels.csv_utility import FetchDustMapPanel
        return FetchDustMapPanel(_FakeWindow())

    def test_construction_and_controls(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: True):
            p = self._panel()
        self.assertTrue(p._check_btn.isEnabled())
        self.assertTrue(p._fetch_btn.isEnabled())
        self.assertEqual(p._map_combo.itemData(0), "auto")
        self.assertEqual(p._map_combo.count(), 3)

    def test_disabled_without_extra(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: False):
            p = self._panel()
        self.assertFalse(p._check_btn.isEnabled())
        self.assertFalse(p._fetch_btn.isEnabled())
        self.assertIn("dust", p._status_lbl.text().lower())

    def test_render_check_result(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: True):
            p = self._panel()
        p._on_done({
            "map": "auto", "cache_dir": "/tmp/dust",
            "fetched": [
                {"map": "leike2020", "status": "missing", "path": "/tmp/dust/a",
                 "size_mb": None},
                {"map": "edenhofer2023", "status": "cached", "path": "/tmp/dust/b",
                 "size_mb": 3251.7},
            ],
        })
        self.assertEqual(p._progress_bar.format(), "Done")

    def test_render_error_result(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: True):
            p = self._panel()
        p._on_done({"error": "map data not fetched"})
        self.assertEqual(p._progress_bar.format(), "Error")

    def test_manual_download_commands_and_copy(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: True):
            p = self._panel()
        cmds = p._cmd_box.toPlainText()
        # Both maps, both Zenodo records, both md5s, resumable flags, cache dir.
        self.assertIn("zenodo.org/record/3993082/files/mean_std.h5", cmds)
        self.assertIn("zenodo.org/record/8187943/files/mean_and_std_healpix.fits", cmds)
        self.assertIn("1ea998fdaef58f53da639356362223ba", cmds)
        self.assertIn("aria2c -c", cmds)
        self.assertIn("wget -c", cmds)
        self.assertIn(str(dust._DUST_CACHE_DIR / "leike_2020"), cmds)
        # Copy puts the same text on the clipboard.
        p._copy_commands()
        self.assertEqual(QApplication.clipboard().text(), cmds)


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class DbStatusPanelDustSmoke(unittest.TestCase):
    """The opt-57 Database Status panel appends the cached dust-map FILES beneath
    the DB tables (file-presence/size, not a row count)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dust_rows_appended(self):
        import core.db
        from gui.panels.csv_utility import DbStatusPanel
        fake_tables = [{"table": "Star Systems", "rows": 5, "populated": True}]
        present = [
            {"map": "leike2020", "label": "Dust Map: Leike 2020 (near-field)",
             "path": "/x/a", "present": True, "size_mb": 2365.6},
            {"map": "edenhofer2023", "label": "Dust Map: Edenhofer 2024",
             "path": "/x/b", "present": False, "size_mb": None},
        ]
        p = DbStatusPanel(_FakeWindow())
        captured = {}
        orig = p.make_table
        p.make_table = lambda headers, rows: (
            captured.update(headers=headers, rows=rows), orig(headers, rows))[1]
        with mock.patch.object(core.db, "get_table_status", lambda: fake_tables), \
             mock.patch.object(dust, "get_dust_map_status", lambda: present):
            p._run()
        # Header relabeled to cover both tables and files.
        self.assertEqual(captured["headers"], ["Table / File", "Rows / Size", "Status"])
        labels = [r[0] for r in captured["rows"]]
        self.assertIn("Dust Map: Leike 2020 (near-field)", labels)
        self.assertIn("Dust Map: Edenhofer 2024", labels)
        # Present map shows size + "Present"; missing shows "—" + "Missing".
        by_label = {r[0]: r for r in captured["rows"]}
        self.assertEqual(by_label["Dust Map: Leike 2020 (near-field)"][1], "2,365.6 MB")
        self.assertEqual(by_label["Dust Map: Leike 2020 (near-field)"][2], "Present")
        self.assertEqual(by_label["Dust Map: Edenhofer 2024"][1], "—")
        self.assertEqual(by_label["Dust Map: Edenhofer 2024"][2], "Missing")


if __name__ == "__main__":
    unittest.main()
