# tests/test_viz_phase_o.py — Phase O (visualization expansion) test scaffold.
#
# This file is the home for every Phase-O test. O-1 (Shared Foundations) seeds it with:
#   * F1 — the additive `app_magnitude` / `parsecs` keys on the opts-18/19 result rows
#          (offline, tmp star_systems DB; the test_db_backups.py isolation pattern).
#   * F2 — an offscreen smoke test of the reusable help-dialog component.
#   * F3 — `build_canvas_ok` (offscreen canvas-builds-without-error helper) + the
#          additivity-regression guard that calls every shared canvas with NO new
#          kwargs, protecting opts 18/19 / GCNS / Phase-I callers from signature breaks
#          when later sub-phases (O-3 capability layer, O-4 solar_overlay) extend them.
#
# Later sub-phases append their `prepare_*` unit tests here.

import os
# Qt must run headless under the test runner. Set before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pathlib
import shutil
import tempfile
import unittest

import core.db as db
import core.calculators as calc


def _qt_available() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except Exception:
        return False


def _mpl_available() -> bool:
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# F1 — opts 18/19 result-row extension (offline, tmp DB)
# ─────────────────────────────────────────────────────────────────────────────
class F1RowExtensionTest(unittest.TestCase):
    """`app_magnitude` + `parsecs` are added to the opts-18/19 rows, additively."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()  # creates the real (empty) schema; star_systems exists
        # Seed one star (parallax 200 mas → 5 pc → 16.3 ly) into the real table.
        self.conn.execute(
            "INSERT INTO star_systems "
            "(star_name, designations, spectral_type, parallax, parsecs, "
            " light_years, app_magnitude, ra, dec) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("Test Star", "HD 1", "G2V", 200.0, 5.0, 16.3076, 5.5,
             "12 00 00.0", "+10 00 00.0"),
        )
        self.conn.commit()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_sol_rows_carry_app_magnitude_and_parsecs(self):
        res = calc.compute_stars_within_distance_of_sol(50.0)
        self.assertNotIn("error", res)
        self.assertEqual(res["count"], 1)
        row = res["stars"][0]
        # New additive keys present + numeric.
        self.assertEqual(row["app_magnitude"], 5.5)
        self.assertAlmostEqual(row["parsecs"], 5.0)
        # Pre-existing keys untouched (additive only).
        for k in ("Star Name", "Star Designations", "Spectral Type",
                  "Light Years", "x", "y", "z"):
            self.assertIn(k, row)
        self.assertEqual(row["Star Name"], "Test Star")

    def test_star_rows_carry_app_magnitude_and_parsecs(self):
        # compute_stars_within_distance_of_star calls SIMBAD for the centre — mock it
        # to an offline origin so the test stays network-free.
        orig = calc.compute_lookup_star_for_distance
        calc.compute_lookup_star_for_distance = lambda name: {
            "name": "Origin", "ra_deg": 0.0, "dec_deg": 0.0, "ly": 0.0,
        }
        try:
            res = calc.compute_stars_within_distance_of_star("Origin", 50.0)
        finally:
            calc.compute_lookup_star_for_distance = orig
        self.assertNotIn("error", res)
        self.assertEqual(res["count"], 1)
        row = res["stars"][0]
        self.assertEqual(row["app_magnitude"], 5.5)
        self.assertAlmostEqual(row["parsecs"], 5.0)  # 1000 / 200 mas
        for k in ("Star Name", "Star Designations", "Spectral Type",
                  "Distance", "x", "y", "z"):
            self.assertIn(k, row)


# ─────────────────────────────────────────────────────────────────────────────
# F2 — reusable help-dialog component (offscreen smoke)
# ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(_qt_available(), "PySide6 not available")
class F2HelpDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_help_text_constant_present(self):
        from gui.help_text import TOOMRE_HELP_HTML
        self.assertIn("Toomre", TOOMRE_HELP_HTML)
        self.assertIn("U", TOOMRE_HELP_HTML)
        self.assertGreater(len(TOOMRE_HELP_HTML), 200)

    def test_show_help_dialog_opens(self):
        from gui.help import show_help_dialog
        dlg = show_help_dialog(None, "Title", "<p>hello</p>")
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.windowTitle(), "Title")
        dlg.close()

    def test_info_button_opens_dialog_on_click(self):
        from gui.help import info_button, _open_help_dialogs
        from gui.help_text import TOOMRE_HELP_HTML
        n0 = len(_open_help_dialogs)
        btn = info_button("Toomre diagram", TOOMRE_HELP_HTML)
        btn.click()
        self.assertGreaterEqual(len(_open_help_dialogs), n0 + 1)


# ─────────────────────────────────────────────────────────────────────────────
# F3 — additivity-regression guard for the shared canvases
# ─────────────────────────────────────────────────────────────────────────────
def build_canvas_ok(test, make_fn, *args, **kwargs):
    """Assert a `make_*_canvas` builds without raising; return its result.

    Shared offscreen smoke helper reused by later Phase-O sub-phases.
    """
    result = make_fn(*args, **kwargs)
    test.assertIsNotNone(result)
    # Helpers return (canvas, toolbar[, ax]); first element is the FigureCanvas.
    canvas = result[0] if isinstance(result, tuple) else result
    test.assertTrue(hasattr(canvas, "figure"))
    return result


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class F3CanvasRegressionGuardTest(unittest.TestCase):
    """Shared canvases still build with NO new kwargs (no signature break)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _stars(self):
        return [
            {"name": "Sol", "desig": "", "sp_type": "G2V",
             "color": "#fff4c2", "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Alpha Cen", "desig": "HD 128620", "sp_type": "G2V",
             "color": "#fff4c2", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
        ]

    def test_shared_canvases_no_new_required_kwargs(self):
        from gui.visualizations.plot_helpers import (
            make_star_chart_canvas, make_star_chart_3d_canvas,
            make_star_map_canvas, make_star_map_3d_canvas, make_orbits_canvas,
        )
        stars = self._stars()
        build_canvas_ok(self, make_star_chart_canvas, None, stars, 20.0)
        build_canvas_ok(self, make_star_chart_3d_canvas, None, stars, 20.0)
        build_canvas_ok(self, make_star_map_canvas, None, stars)
        build_canvas_ok(self, make_star_map_3d_canvas, None, stars)
        build_canvas_ok(self, make_orbits_canvas, None, [], [], 2.0)


# ─────────────────────────────────────────────────────────────────────────────
# O-2 — Star-Map Data Products: prepare_* unit tests (offline)
# ─────────────────────────────────────────────────────────────────────────────
import math

import core.viz as viz


class O1SkyFromStarTest(unittest.TestCase):
    """prepare_sky_from_star — vantage projection, vantage magnitude, skip counts."""

    def _result(self):
        return {
            "center": "Vantage", "center_x": 3.0, "center_y": 0.0, "center_z": 0.0,
            "stars": [
                # vector from vantage = (0, 4, 0): d=4 ly, ra=90°, dec=0°
                {"Star Name": "A", "Spectral Type": "G2V", "app_magnitude": 5.0,
                 "parsecs": 3.0, "x": 3.0, "y": 4.0, "z": 0.0},
                # no V magnitude → skipped + counted
                {"Star Name": "NoMag", "Spectral Type": "M0", "app_magnitude": None,
                 "parsecs": 5.0, "x": 3.0, "y": 0.0, "z": 2.0},
            ],
        }

    def test_projection_magnitude_and_skip(self):
        res = viz.prepare_sky_from_star(self._result(), mag_limit=6.5)
        self.assertNotIn("error", res)
        self.assertEqual(res["skipped_no_mag"], 1)
        names = {s["name"] for s in res["stars"]}
        self.assertIn("A", names)         # bright enough
        self.assertIn("Sol", names)       # vantage looks back at Sol
        a = next(s for s in res["stars"] if s["name"] == "A")
        self.assertAlmostEqual(a["ra_deg"], 90.0, places=4)
        self.assertAlmostEqual(a["dec_deg"], 0.0, places=4)
        # M = 5 + 5 - 5log10(3) = 7.614; m' = M - 5 + 5log10(4/3.26156) ≈ 3.057
        self.assertAlmostEqual(a["mag"], 3.057, places=2)
        self.assertEqual(a["sp_class"], "G")

    def test_mag_limit_filters_fainter_stars(self):
        res = viz.prepare_sky_from_star(self._result(), mag_limit=0.0)
        names = {s["name"] for s in res["stars"]}
        self.assertNotIn("A", names)      # m'≈3.06 > 0.0 → excluded
        self.assertIn("Sol", names)       # m'≈-0.35 ≤ 0.0 → kept

    def test_error_passthrough(self):
        self.assertIn("error", viz.prepare_sky_from_star({"error": "boom"}))

    def test_sol_centric_vantage(self):
        # opt-18 result has no "center" → vantage defaults to Sol at the origin.
        result = {"limit_ly": 50.0, "count": 1, "stars": [
            {"Star Name": "A", "Spectral Type": "G2V", "app_magnitude": 5.0,
             "parsecs": 3.0, "x": 0.0, "y": 4.0, "z": 0.0},   # vector (0,4,0): ra=90, dec=0
        ]}
        res = viz.prepare_sky_from_star(result, mag_limit=6.5)
        self.assertEqual(res["vantage_name"], "Sol")
        names = {s["name"] for s in res["stars"]}
        self.assertIn("A", names)
        self.assertNotIn("Sol", names)   # can't see the Sun as a night-sky star from Sol
        a = next(s for s in res["stars"] if s["name"] == "A")
        self.assertAlmostEqual(a["ra_deg"], 90.0, places=4)
        self.assertAlmostEqual(a["dec_deg"], 0.0, places=4)


class O2HrTest(unittest.TestCase):
    """prepare_hr_main_sequence + prepare_hr_from_stars (tmp DB w/ seeded MS table)."""

    def setUp(self):
        import core.regions as regions
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        self._saved_ms = regions._MAIN_SEQUENCE_DATA
        regions._MAIN_SEQUENCE_DATA = None   # force reload from the tmp DB
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()
        for sc, bv, teff, amv in [
            ("A0", "0.00", "9790", "0.7"),
            ("G2", "0.63", "5778", "4.83"),
            ("K0", "0.81", "5150", "5.9"),
            ("M0", "1.40", "3840", "8.8"),
        ]:
            self.conn.execute(
                "INSERT INTO main_sequence_stars "
                "(spectral_class, b_v, teff_k, abs_mag_vis, abs_mag_bol, bc, lum, "
                " radius, mass, density, lifetime) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sc, bv, teff, amv, amv, "0", "1", "1", "1", "1", "1e10"),
            )
        self.conn.commit()

    def tearDown(self):
        import core.regions as regions
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        regions._MAIN_SEQUENCE_DATA = self._saved_ms
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_main_sequence_points_sorted_hot_to_cool(self):
        res = viz.prepare_hr_main_sequence()
        self.assertNotIn("error", res)
        teffs = [p["teff"] for p in res["points"]]
        self.assertEqual(teffs, sorted(teffs, reverse=True))   # hot → cool
        g2 = next(p for p in res["points"] if p["label"] == "G2")
        self.assertEqual(g2["teff"], 5778.0)
        self.assertAlmostEqual(g2["abs_mag"], 4.83)
        self.assertEqual(g2["color"], viz._SPECTRAL_COLORS["G"])

    def test_main_sequence_empty_table_error(self):
        self.conn.execute("DELETE FROM main_sequence_stars")
        self.conn.commit()
        self.assertIn("error", viz.prepare_hr_main_sequence())

    def test_hr_from_stars_mv_and_teff(self):
        result = {"stars": [
            # M_V = 4.83 + 5 - 5log10(10) = 4.83; Teff from G2 ceiling = 5778
            {"Star Name": "Sunlike", "Spectral Type": "G2V",
             "app_magnitude": 4.83, "parsecs": 10.0},
            {"Star Name": "NoMag", "Spectral Type": "K0",
             "app_magnitude": None, "parsecs": 8.0},          # skipped (no mag)
            {"Star Name": "WhiteDwarf", "Spectral Type": "DA",
             "app_magnitude": 11.0, "parsecs": 5.0},          # skipped (no OBAFGKM Teff)
        ]}
        res = viz.prepare_hr_from_stars(result)   # no "center" → Sol-centric (opt 18)
        self.assertNotIn("error", res)
        self.assertEqual(res["skipped"], 2)
        # 1 result star (Sunlike) + the Sol reference anchor (gold ★).
        result_stars = [p for p in res["points"] if not p.get("highlight")]
        refs = [p for p in res["points"] if p.get("highlight")]
        self.assertEqual(len(result_stars), 1)
        self.assertEqual(result_stars[0]["name"], "Sunlike")
        self.assertAlmostEqual(result_stars[0]["abs_mag"], 4.83, places=4)
        self.assertEqual(result_stars[0]["teff"], 5778.0)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["name"], "Sun")
        self.assertEqual(refs[0]["teff"], 5778.0)

    def test_hr_from_stars_center_highlight(self):
        # opt 19: the queried centre star is added as a gold-★ reference if in catalog.
        self.conn.execute(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "parallax, parsecs, light_years, app_magnitude, ra, dec) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("Centre Star", "", "K0V", 100.0, 10.0, 32.6156, 5.9,
             "12 00 00.0", "+00 00 00.0"),
        )
        self.conn.commit()
        res = viz.prepare_hr_from_stars({"center": "Centre Star", "stars": []})
        refs = [p for p in res["points"] if p.get("highlight")]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["name"], "Centre Star")
        self.assertEqual(refs[0]["teff"], 5150.0)            # K0 ceiling row
        self.assertAlmostEqual(refs[0]["abs_mag"], 5.9, places=4)  # 5.9+5-5log10(10)

    def test_hr_from_stars_center_not_in_catalog(self):
        # Unknown centre → no reference point (graceful), not an error.
        res = viz.prepare_hr_from_stars({"center": "Nonexistent Star", "stars": []})
        self.assertNotIn("error", res)
        self.assertEqual([p for p in res["points"] if p.get("highlight")], [])


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O2CanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_hr_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_hr_canvas
        ref = {"points": [
            {"label": "A0", "teff": 9790, "abs_mag": 0.7, "bv": 0.0, "lum": 50, "color": "#cad7ff"},
            {"label": "G2", "teff": 5778, "abs_mag": 4.83, "bv": 0.63, "lum": 1, "color": "#fff4ea"},
            {"label": "M0", "teff": 3840, "abs_mag": 8.8, "bv": 1.4, "lum": 0.05, "color": "#ff8d3f"},
        ]}
        overlay = [
            {"name": "X", "teff": 5200, "abs_mag": 6.0, "color": "#ffd2a1", "sp_type": "K1V"},
            {"name": "Sun", "teff": 5778, "abs_mag": 4.83, "color": "#FFD700",
             "sp_type": "G2V", "highlight": True},   # gold-★ reference path
        ]
        build_canvas_ok(self, make_hr_canvas, None, ref, overlay)
        build_canvas_ok(self, make_hr_canvas, None, ref)   # no overlay

    def test_sky_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_sky_canvas
        data = {"vantage_name": "Vega", "mag_limit": 6.5, "skipped_no_mag": 2, "stars": [
            {"name": "A", "ra_deg": 90.0, "dec_deg": 0.0, "mag": 3.1, "sp_class": "G", "color": "#fff4ea"},
            {"name": "Sol", "ra_deg": 180.0, "dec_deg": -10.0, "mag": -0.3, "sp_class": "G", "color": "#fff4ea"},
        ]}
        build_canvas_ok(self, make_sky_canvas, None, data)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O2PanelWiringSmokeTest(unittest.TestCase):
    """Construct the host panels offscreen and exercise the O-2 tab builders.

    Uses the real (auto-seeded) DB so the main-sequence HR reference is available.
    """

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_panels_construct(self):
        import gui.panels as panels
        win = self._StubWindow()
        for cls in (panels.MainSequencePanel,
                    panels.StarsWithinDistanceSolPanel,
                    panels.StarsWithinDistanceStarPanel):
            p = cls(win)
            self.assertIsNotNone(p)
        # opt 12 builds its HR tab at construction.
        ms = panels.MainSequencePanel(win)
        self.assertGreaterEqual(ms._viz_tabs_widget.count(), 1)

    def test_hr_and_night_sky_tab_builders(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_hr_tab, _add_night_sky_tab
        p = panels.StarsWithinDistanceStarPanel(self._StubWindow())
        n0 = p._viz_tabs_widget.count()
        result = {
            "center": "Vega", "center_x": 3.0, "center_y": 0.0, "center_z": 0.0,
            "stars": [{"Star Name": "A", "Spectral Type": "G2V",
                       "app_magnitude": 5.0, "parsecs": 3.0, "Distance": 4.0,
                       "x": 3.0, "y": 4.0, "z": 0.0}],
        }
        _add_hr_tab(p, result)
        _add_night_sky_tab(p, result)
        self.assertEqual(p._viz_tabs_widget.count(), n0 + 2)

    def test_night_sky_tab_builds_for_sol_centric(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_night_sky_tab
        p = panels.StarsWithinDistanceSolPanel(self._StubWindow())
        n0 = p._viz_tabs_widget.count()
        result = {"limit_ly": 20.0, "count": 1, "stars": [
            {"Star Name": "A", "Spectral Type": "G2V", "app_magnitude": 5.0,
             "parsecs": 3.0, "x": 0.0, "y": 4.0, "z": 0.0}]}
        _add_night_sky_tab(p, result)   # opt-18 Sol-centric → now adds a Night Sky tab
        self.assertEqual(p._viz_tabs_widget.count(), n0 + 1)


if __name__ == "__main__":
    unittest.main()
