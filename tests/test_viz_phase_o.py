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


# ─────────────────────────────────────────────────────────────────────────────
# O-3 — Star-Chart Interactivity: capability layer (CP0)
#   highlight_star + on_star_click on all four shared canvases, plus the
#   structural-regression guard that the DEFAULT (foreign-caller) render is
#   unchanged. The fixture deliberately includes the classifier edge rows —
#   a composite `+`-type, a `dM`-prefix dwarf, a null `sp_type`, the white
#   dwarf, two coincident-coordinate stars, and a null-coordinate star.
# ─────────────────────────────────────────────────────────────────────────────
def _o3_edge_stars():
    return [
        {"name": "Sol", "desig": "", "sp_type": "G2V",
         "color": "#fff4c2", "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
        {"name": "* alf Cen", "desig": "", "sp_type": "G2V+K1V",          # composite
         "color": "#fff4c2", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
        {"name": "* alf Cen B", "desig": "GJ 559 B", "sp_type": "K1V",     # coincident w/ above
         "color": "#ffd2a1", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
        {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "dM6",          # dM → "D" bucket
         "color": "#dfe6ff", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
        {"name": "* alf CMa B", "desig": "GJ 244 B", "sp_type": "DA1.9",   # white dwarf
         "color": "#dfe6ff", "ly": 8.6, "x": -1.6, "y": 8.2, "z": -2.5},
        {"name": "NoType", "desig": "", "sp_type": "",                     # null/empty type → "?"
         "color": "#cccccc", "ly": 9.0, "x": 2.0, "y": -3.0, "z": 1.0},
        {"name": "NullCoord", "desig": "", "sp_type": "M0",                # no map point
         "color": "#ff9d6c", "ly": 10.0, "x": None, "y": None, "z": None},
    ]


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O3CapabilityLayerTest(unittest.TestCase):
    """highlight_star + on_star_click are present and behave additively."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _canvases(self):
        from gui.visualizations.plot_helpers import (
            make_star_map_canvas, make_star_map_3d_canvas,
            make_star_chart_canvas, make_star_chart_3d_canvas)
        stars = _o3_edge_stars()
        clicks = []
        cb = clicks.append
        return [
            ("map2d", make_star_map_canvas(None, stars, on_star_click=cb)[0]),
            ("map3d", make_star_map_3d_canvas(None, stars, on_star_click=cb)[0]),
            ("chart2d", make_star_chart_canvas(None, stars, 15.0, on_star_click=cb)[0]),
            ("chart3d", make_star_chart_3d_canvas(None, stars, 15.0, on_star_click=cb)[0]),
        ]

    def test_highlight_star_present_and_additive(self):
        for label, canvas in self._canvases():
            with self.subTest(canvas=label):
                self.assertTrue(callable(getattr(canvas, "highlight_star", None)))
                ax = canvas.figure.axes[0]
                base = len(ax.collections)
                # A present star adds exactly one ring collection.
                canvas.highlight_star("Wolf 359")
                self.assertEqual(len(ax.collections), base + 1)
                self.assertEqual(canvas.highlighted_star(), "Wolf 359")
                # Re-highlighting another present star does not accumulate rings.
                canvas.highlight_star("* alf Cen B")
                self.assertEqual(len(ax.collections), base + 1)
                # Absent name / null-coord star / None → ring cleared, back to baseline.
                for nm in ("DoesNotExist", "NullCoord", None):
                    canvas.highlight_star(nm)
                    self.assertEqual(len(ax.collections), base)
                self.assertIsNone(canvas.highlighted_star())

    def test_on_star_click_optional(self):
        # Building without on_star_click must also succeed (default None path).
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        canvas = make_star_chart_canvas(None, _o3_edge_stars(), 15.0)[0]
        self.assertTrue(hasattr(canvas, "highlight_star"))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O3StructuralRegressionTest(unittest.TestCase):
    """The DEFAULT (foreign-caller) render is structurally unchanged by the
    capability layer. Guards GCNS / Phase-I against the O16 per-class split
    accidentally becoming unconditional (which would change collection counts)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_default_render_structural_invariants(self):
        from gui.visualizations.plot_helpers import (
            make_star_map_canvas, make_star_map_3d_canvas,
            make_star_chart_canvas, make_star_chart_3d_canvas)
        stars = _o3_edge_stars()

        # 2D scatter map: one body scatter + one center-★ scatter.
        c = make_star_map_canvas(None, stars)[0]          # default path, no kwargs
        ax = c.figure.axes[0]
        self.assertEqual(len(c.figure.axes), 1)
        self.assertEqual(len(ax.collections), 2)

        # 3D scatter map: body scatter + center ★.
        c = make_star_map_3d_canvas(None, stars)[0]
        self.assertEqual(len(c.figure.axes), 1)
        self.assertEqual(len(c.figure.axes[0].collections), 2)

        # 2D star chart: body scatter + center ★; 3 distance-ring patches at
        # limit 15 (major step 5); axes pinned to ±limit.
        c = make_star_chart_canvas(None, stars, 15.0)[0]
        ax = c.figure.axes[0]
        self.assertEqual(len(ax.collections), 2)
        self.assertEqual(len(ax.patches), 3)              # distance rings
        self.assertEqual(ax.get_xlim(), (-15.0, 15.0))
        self.assertEqual(ax.get_ylim(), (-15.0, 15.0))

        # 3D star chart: body scatter + center ★ + 3 wireframe reference spheres.
        c = make_star_chart_3d_canvas(None, stars, 15.0)[0]
        ax = c.figure.axes[0]
        self.assertEqual(len(ax.collections), 5)
        self.assertEqual(ax.get_zlim3d(), (-15.0, 15.0))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O15RowMapLinkingTest(unittest.TestCase):
    """O15 — table selection ↔ map highlight across all five opt-18/19 map tabs."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def _panel_with_maps(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        p = panels.StarsWithinDistanceSolPanel(self._StubWindow())
        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            ["Wolf 359", "GJ 406", "dM6", "7.860"],
            ["* alf Cen B", "GJ 559 B", "K1V", "4.370"],
        ]
        view = p.make_table(headers, rows)
        p._link_view = view
        map_stars = [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "dM6",
             "color": "#dfe6ff", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
            {"name": "* alf Cen B", "desig": "GJ 559 B", "sp_type": "K1V",
             "color": "#ffd2a1", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
        ]
        _add_map_tabs(p, map_stars, 15.0, "title")
        return p, view

    def test_five_canvases_wired(self):
        p, _ = self._panel_with_maps()
        self.assertEqual(len(p._link_canvases), 5)
        for c in p._link_canvases:
            self.assertTrue(callable(getattr(c, "highlight_star", None)))

    def test_row_selection_highlights_all_canvases(self):
        from PySide6.QtCore import QItemSelectionModel
        p, view = self._panel_with_maps()
        idx = view.model().index(0, 0)   # Wolf 359
        view.selectionModel().setCurrentIndex(
            idx,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        for c in p._link_canvases:
            self.assertEqual(c.highlighted_star(), "Wolf 359")

    def test_map_click_selects_row_and_highlights(self):
        from gui.panels.distance_stars import _star_click_select
        p, view = self._panel_with_maps()
        _star_click_select(p, "* alf Cen B")
        self.assertEqual(view.currentIndex().row(), 1)
        for c in p._link_canvases:
            self.assertEqual(c.highlighted_star(), "* alf Cen B")

    def test_click_center_star_is_noop(self):
        # The gold ★ (Sol) has no table row → no selection, no crash.
        from gui.panels.distance_stars import _star_click_select
        p, view = self._panel_with_maps()
        _star_click_select(p, "Sol")
        self.assertFalse(view.selectionModel().hasSelection())

    def test_empty_space_click_clears_selection_and_rings(self):
        # The deselect gesture: an empty-space click calls on_star_click(None) →
        # _star_click_select(panel, None) clears the table selection, which clears
        # the ring on every canvas.
        from PySide6.QtCore import QItemSelectionModel
        from gui.panels.distance_stars import _star_click_select
        p, view = self._panel_with_maps()
        idx = view.model().index(0, 0)   # Wolf 359
        view.selectionModel().setCurrentIndex(
            idx,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        for c in p._link_canvases:
            self.assertEqual(c.highlighted_star(), "Wolf 359")
        _star_click_select(p, None)      # empty-space click → deselect
        self.assertFalse(view.selectionModel().hasSelection())
        for c in p._link_canvases:
            self.assertIsNone(c.highlighted_star())


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O3SharedHelperReuseTest(unittest.TestCase):
    """Cross-panel reuse of the opt-18/19 chart helpers stays intact. Guards the
    CP1 `_build_star_chart_3d_tab` -> (widget, canvas) return change against the
    GCNS callers that consume it (which previously got a bare widget)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_gcns_add_chart_tabs_builds_two_tabs(self):
        from gui.panels.gcns import GcnsCensusBrowserPanel, _add_chart_tabs
        p = GcnsCensusBrowserPanel(self._StubWindow())
        n0 = p._viz_tabs_widget.count()
        map_stars = [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "M6",
             "color": "#ff9d6c", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
        ]
        _add_chart_tabs(p, map_stars, 15.0)
        self.assertEqual(p._viz_tabs_widget.count(), n0 + 2)   # Star Chart + 3D


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O16LegendFilterTest(unittest.TestCase):
    """O16 — opt-in per-class split + pickable legend on the two 2D canvases."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _stars(self):
        return [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "dM6",      # dM → D
             "color": "#dfe6ff", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
            {"name": "alf Cen B", "desig": "", "sp_type": "K1V",
             "color": "#ffd2a1", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
            {"name": "Sirius", "desig": "", "sp_type": "A0",
             "color": "#cad7ff", "ly": 8.6, "x": -1.6, "y": 8.2, "z": -2.5},
            {"name": "NoType", "desig": "", "sp_type": "",                 # ? → no legend
             "color": "#cccccc", "ly": 9.0, "x": 2.0, "y": -3.0, "z": 1.0},
        ]

    def test_map_filter_splits_classes_excludes_unknown(self):
        from gui.visualizations.plot_helpers import make_star_map_canvas
        c, _ = make_star_map_canvas(None, self._stars(), legend_filter=True)
        entries = {t.get_text() for t in c.figure.axes[0].get_legend().get_texts()}
        self.assertEqual(entries, {"Class A", "Class D", "Class G", "Class K"})
        # default path: single body scatter + center ★ = 2 collections.
        c2, _ = make_star_map_canvas(None, self._stars())
        self.assertEqual(len(c2.figure.axes[0].collections), 2)

    def test_chart_filter_adds_legend_default_has_none(self):
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        c, _ = make_star_chart_canvas(None, self._stars(), 15.0, legend_filter=True)
        leg = c.figure.axes[0].get_legend()
        self.assertIsNotNone(leg)
        # body excludes the Sol (G) centre; ? excluded.
        self.assertEqual({t.get_text() for t in leg.get_texts()},
                         {"Class A", "Class D", "Class K"})
        c2, _ = make_star_chart_canvas(None, self._stars(), 15.0)
        self.assertIsNone(c2.figure.axes[0].get_legend())

    def test_hit_skips_hidden_class(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.backend_bases import MouseEvent
        from gui.visualizations.plot_helpers import _legend_filter_2d
        fig = Figure(); FigureCanvasAgg(fig)
        ax = fig.add_subplot(111); ax.set_xlim(-10, 10); ax.set_ylim(-10, 10)
        xs, ys = [4.0, -1.6, 2.0], [4.8, -1.3, -3.0]
        hit = _legend_filter_2d(
            fig.canvas, ax, xs, ys, ["#dfe6ff", "#ffd2a1", "#ccc"],
            ["dM6", "K1V", ""], [36] * 3,
            scatter_kw=dict(zorder=5), legend_kw=dict(loc="upper right"),
            hidden=set())
        fig.canvas.draw()
        dx, dy = ax.transData.transform((4.0, 4.8))
        ev = MouseEvent("motion_notify_event", fig.canvas, dx, dy)
        self.assertEqual(hit(ev), 0)                       # visible star → its index
        for coll in ax.collections:                        # hide the D-class dot
            offs = coll.get_offsets()
            if len(offs) and abs(offs[0][0] - 4.0) < 1e-6:
                coll.set_visible(False)
        self.assertIsNone(hit(ev))                         # hidden → not hit

    def test_legend_pick_toggles_class_and_labels(self):
        from matplotlib.backend_bases import PickEvent, MouseEvent
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        c, _ = make_star_chart_canvas(None, self._stars(), 15.0, legend_filter=True)
        ax = c.figure.axes[0]; c.draw()
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        d_handle = leg.legend_handles[texts.index("Class D")]
        d_coll = next(coll for coll in ax.collections
                      if len(coll.get_offsets()) and
                      abs(coll.get_offsets()[0][0] - 4.0) < 1e-6)
        self.assertTrue(d_coll.get_visible())
        me = MouseEvent("button_press_event", c, 0, 0)
        c.callbacks.process("pick_event", PickEvent("pick_event", c, me, d_handle))
        self.assertFalse(d_coll.get_visible())             # class hidden
        d_labels = [t for t in ax.texts if getattr(t, "_o16_cls", None) == "D"]
        self.assertTrue(d_labels and not d_labels[0].get_visible())  # labels follow

    def test_highlight_ring_follows_class_visibility(self):
        # A selection ring on a star whose class is then legend-hidden must hide
        # too (and reappear when the class is shown again) — no ring lingering
        # over a filtered-out dot.
        from matplotlib.backend_bases import PickEvent, MouseEvent
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        c, _ = make_star_chart_canvas(None, self._stars(), 15.0, legend_filter=True)
        ax = c.figure.axes[0]; c.draw()
        c.highlight_star("Wolf 359")               # D-class star → ring appended
        ring = ax.collections[-1]
        self.assertTrue(ring.get_visible())
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        d_handle = leg.legend_handles[texts.index("Class D")]
        me = MouseEvent("button_press_event", c, 0, 0)
        c.callbacks.process("pick_event", PickEvent("pick_event", c, me, d_handle))
        self.assertFalse(ring.get_visible())       # ring hidden with its class
        c.callbacks.process("pick_event", PickEvent("pick_event", c, me, d_handle))
        self.assertTrue(ring.get_visible())        # and back when re-shown


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O16LegendFilter3DTest(unittest.TestCase):
    """O16/CP3 — opt-in per-class split + pickable legend on the two 3D canvases
    (Map 3D, Star Chart 3D). Best-effort: asserts the per-class split, legend
    entries, default-path invariance, and pick-driven visibility/label toggling."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _stars(self):
        return [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "dM6",      # dM → D
             "color": "#dfe6ff", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
            {"name": "alf Cen B", "desig": "", "sp_type": "K1V",
             "color": "#ffd2a1", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
            {"name": "Sirius", "desig": "", "sp_type": "A0",
             "color": "#cad7ff", "ly": 8.6, "x": -1.6, "y": 8.2, "z": -2.5},
            {"name": "NoType", "desig": "", "sp_type": "",                 # ? → no legend
             "color": "#cccccc", "ly": 9.0, "x": 2.0, "y": -3.0, "z": 1.0},
        ]

    def test_map3d_filter_splits_classes_excludes_unknown(self):
        from gui.visualizations.plot_helpers import make_star_map_3d_canvas
        # Body scatter includes the centre (index 0), so Sol's G is a togglable
        # entry — matches the 2D Map.
        c = make_star_map_3d_canvas(None, self._stars(), legend_filter=True)[0]
        entries = {t.get_text() for t in c.figure.axes[0].get_legend().get_texts()}
        self.assertEqual(entries, {"Class A", "Class D", "Class G", "Class K"})
        # Default path: single body scatter + centre ★ = 2 collections.
        c2 = make_star_map_3d_canvas(None, self._stars())[0]
        self.assertEqual(len(c2.figure.axes[0].collections), 2)

    def test_chart3d_filter_adds_legend_default_has_none(self):
        from gui.visualizations.plot_helpers import make_star_chart_3d_canvas
        c = make_star_chart_3d_canvas(None, self._stars(), 15.0, legend_filter=True)[0]
        leg = c.figure.axes[0].get_legend()
        self.assertIsNotNone(leg)
        # Body excludes the Sol (G) centre ★; ? excluded from the legend.
        self.assertEqual({t.get_text() for t in leg.get_texts()},
                         {"Class A", "Class D", "Class K"})
        c2 = make_star_chart_3d_canvas(None, self._stars(), 15.0)[0]
        self.assertIsNone(c2.figure.axes[0].get_legend())

    def test_legend_pick_toggles_class_and_labels_3d(self):
        # 3D Path3DCollection offsets are projected, not data-space, so identify
        # the toggled class by counting hidden collections (+1) and by the
        # labels following — both robust to the 3D projection.
        from matplotlib.backend_bases import PickEvent, MouseEvent
        from gui.visualizations.plot_helpers import make_star_chart_3d_canvas
        c = make_star_chart_3d_canvas(None, self._stars(), 15.0, legend_filter=True)[0]
        ax = c.figure.axes[0]; c.draw()
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        d_handle = leg.legend_handles[texts.index("Class D")]
        d_labels = [t for t in ax.texts if getattr(t, "_o16_cls", None) == "D"]
        self.assertTrue(d_labels and d_labels[0].get_visible())   # initially shown
        hidden_before = sum(1 for coll in ax.collections if not coll.get_visible())
        me = MouseEvent("button_press_event", c, 0, 0)
        c.callbacks.process("pick_event", PickEvent("pick_event", c, me, d_handle))
        hidden_after = sum(1 for coll in ax.collections if not coll.get_visible())
        self.assertEqual(hidden_after, hidden_before + 1)         # one class hidden
        self.assertFalse(d_labels[0].get_visible())               # labels follow


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O17IsochroneTest(unittest.TestCase):
    """O17/CP4 — travel-time isochrone rings on the Star Chart 2D + 3D canvases."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    # ── ring math ────────────────────────────────────────────────────────────
    def test_ring_math_anchors(self):
        from gui.visualizations.plot_helpers import _isochrone_rings
        # 10×c → ly_hr = 10/8765.8128; the 1-year ring sits at exactly N ly = 10 ly,
        # the 6-month ring at 5 ly (the CP4 hand anchors).
        rings = dict((d, r) for r, d in _isochrone_rings(10 / 8765.8128, 15.0))
        self.assertAlmostEqual(rings["1 year"], 10.0, places=6)
        self.assertAlmostEqual(rings["6 months"], 5.0, places=6)
        # 0.01 ly/hr → 1 week ≈ 1.68 ly, 1 month ≈ 7.305 ly (only those two fit 15 ly).
        slow = dict((d, r) for r, d in _isochrone_rings(0.01, 15.0))
        self.assertAlmostEqual(slow["1 week"], 1.68, places=3)
        self.assertAlmostEqual(slow["1 month"], 7.305, places=2)

    def test_xc_and_lyhr_give_identical_radii(self):
        from gui.visualizations.plot_helpers import _isochrone_rings
        a = _isochrone_rings(10 / 8765.8128, 15.0)
        b = _isochrone_rings(0.0011408, 15.0)    # ≈ the same velocity in ly/hr
        self.assertEqual([d for _, d in a], [d for _, d in b])
        for (ra, _), (rb, _) in zip(a, b):
            self.assertAlmostEqual(ra, rb, places=2)

    def test_invalid_velocity_yields_no_rings(self):
        from gui.visualizations.plot_helpers import _isochrone_rings
        for bad in (0, -1, None, float("nan"), float("inf")):
            self.assertEqual(_isochrone_rings(bad, 15.0), [])
        self.assertEqual(_isochrone_rings(0.01, 0), [])    # non-positive limit

    def test_fast_velocity_uses_hour_day_steps(self):
        # Regression: 0.1 ly/hr overshoots "1 week" (16.8 ly) at limit 15 — the
        # hour/day steps must still produce rings (previously: silent no-rings).
        from gui.visualizations.plot_helpers import _isochrone_rings
        rings = dict((d, r) for r, d in _isochrone_rings(0.1, 15.0))
        self.assertTrue(rings)                              # not empty
        self.assertAlmostEqual(rings["1 day"], 2.4, places=3)
        self.assertAlmostEqual(rings["3 days"], 7.2, places=3)

    def test_tiny_rings_dropped_and_count_bounded(self):
        from gui.visualizations.plot_helpers import _isochrone_rings
        # Every ring is ≥ 5% of the range (no sub-pixel clutter) and ≤ 6 rings.
        for v in (0.001, 0.01, 0.1, 1.0, 10 / 8765.8128):
            rings = _isochrone_rings(v, 15.0)
            self.assertLessEqual(len(rings), 6)
            for r, _d in rings:
                self.assertGreaterEqual(r, 15.0 * 0.05 - 1e-9)

    def test_too_fast_velocity_yields_no_rings(self):
        # 20 ly/hr at limit 15: even the 1-hour ring (20 ly) overshoots → none.
        from gui.visualizations.plot_helpers import _isochrone_rings
        self.assertEqual(_isochrone_rings(20.0, 15.0), [])

    # ── canvas integration ───────────────────────────────────────────────────
    def _stars(self):
        return [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "M6",
             "color": "#ff9d6c", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
        ]

    def test_chart_isochrone_relabels_rings(self):
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        iso = {"ly_hr": 0.01, "label_unit": "0.0100 ly/hr"}
        c, _ = make_star_chart_canvas(None, self._stars(), 15.0, isochrone=iso)
        c.draw()
        labels = [t.get_text() for t in c.figure.axes[0].texts
                  if "@" in t.get_text() and "ly/hr" in t.get_text()]
        self.assertTrue(any(t.startswith("1 week @") for t in labels))
        self.assertTrue(any(t.startswith("1 month @") for t in labels))
        # default (no isochrone) → distance rings: 3 ring patches at limit 15.
        c2, _ = make_star_chart_canvas(None, self._stars(), 15.0)
        self.assertEqual(len(c2.figure.axes[0].patches), 3)
        self.assertFalse([t for t in c2.figure.axes[0].texts
                          if "@" in t.get_text()])

    def test_chart_3d_isochrone_builds_with_labels(self):
        from gui.visualizations.plot_helpers import make_star_chart_3d_canvas
        iso = {"ly_hr": 10 / 8765.8128, "label_unit": "0.0011 ly/hr"}
        c, _, _ = make_star_chart_3d_canvas(None, self._stars(), 15.0, isochrone=iso)
        c.draw()
        labels = [t.get_text() for t in c.figure.axes[0].texts
                  if "@" in t.get_text() and "ly/hr" in t.get_text()]
        self.assertTrue(any("6 months @" in t for t in labels))
        self.assertTrue(any("1 year @" in t for t in labels))

    # ── panel control: Apply / Clear + highlight survival ────────────────────
    class _StubWindow:
        def __init__(self):
            from PySide6.QtWidgets import QWidget
            self.nav_tree = QWidget()

        def statusBar(self):
            return None

    def _panel_with_maps(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        p = panels.StarsWithinDistanceSolPanel(self._StubWindow())
        view = p.make_table(
            ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
            [["Wolf 359", "GJ 406", "M6", "7.860"],
             ["* alf Cen B", "GJ 559 B", "K1V", "4.370"]])
        p._link_view = view
        map_stars = [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "Wolf 359", "desig": "GJ 406", "sp_type": "M6",
             "color": "#ff9d6c", "ly": 7.86, "x": 4.0, "y": 4.8, "z": -2.0},
            {"name": "* alf Cen B", "desig": "GJ 559 B", "sp_type": "K1V",
             "color": "#ffd2a1", "ly": 4.37, "x": -1.6, "y": -1.3, "z": -3.8},
        ]
        _add_map_tabs(p, map_stars, 15.0, "title")
        return p, view

    def _chart_iso_controls(self, panel, tab_text):
        from PySide6.QtWidgets import QLineEdit, QComboBox, QPushButton
        tabs = panel._viz_tabs_widget
        idx = [i for i in range(tabs.count()) if tabs.tabText(i) == tab_text][0]
        tab = tabs.widget(idx)
        vel = tab.findChild(QLineEdit)
        unit = tab.findChild(QComboBox)
        btns = {b.text(): b for b in tab.findChildren(QPushButton)}
        return vel, unit, btns

    def _iso_labels(self, panel):
        return [t.get_text() for c in panel._link_canvases
                for t in c.figure.axes[0].texts
                if "@" in t.get_text() and "ly/hr" in t.get_text()]

    def test_panel_control_present_and_starts_with_distance_rings(self):
        p, _ = self._panel_with_maps()
        self.assertEqual(len(p._link_canvases), 5)
        vel, unit, btns = self._chart_iso_controls(p, "Star Chart")
        self.assertIsNotNone(vel)
        self.assertIn("Apply", btns)
        self.assertIn("Clear", btns)
        self.assertFalse(self._iso_labels(p))        # distance rings initially

    def test_apply_then_clear_with_highlight_survival(self):
        from PySide6.QtCore import QItemSelectionModel
        p, view = self._panel_with_maps()
        # Select Wolf 359 → gold ring on every canvas.
        view.selectionModel().setCurrentIndex(
            view.model().index(0, 0),
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        self.assertTrue(all(c.highlighted_star() == "Wolf 359"
                            for c in p._link_canvases))
        # Apply 10 ×c on the 2D Star Chart → isochrone rings; highlight survives.
        vel, unit, btns = self._chart_iso_controls(p, "Star Chart")
        unit.setCurrentIndex(0)                       # "× c"
        vel.setText("10")
        btns["Apply"].click()
        self.assertEqual(len(p._link_canvases), 5)    # rebuilt, not leaked
        self.assertTrue(self._iso_labels(p))          # isochrone rings present
        self.assertTrue(all(c.highlighted_star() == "Wolf 359"
                            for c in p._link_canvases))
        # Clear → distance rings return, no isochrone labels remain.
        btns["Clear"].click()
        self.assertFalse(self._iso_labels(p))
        self.assertEqual(len(p._link_canvases), 5)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O18FindTest(unittest.TestCase):
    """O18/CP5 — Find-Star-on-Map box: substring match on name + designations,
    cycling, centre + ring (reuses O15), no-match status, hidden-class reveal."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_norm_find_collapses_whitespace_and_case(self):
        from gui.panels.distance_stars import _norm_find
        self.assertEqual(_norm_find("*  61 Cyg A"), "* 61 cyg a")
        self.assertEqual(_norm_find("  Wolf   359 "), "wolf 359")
        self.assertEqual(_norm_find(None), "")

    class _StubWindow:
        def __init__(self):
            from PySide6.QtWidgets import QWidget
            self.nav_tree = QWidget()
            self._status = ""

        def statusBar(self):
            outer = self

            class _S:
                def showMessage(self, m):
                    outer._status = m
            return _S()

    def _panel(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        p = panels.StarsWithinDistanceSolPanel(self._StubWindow())
        view = p.make_table(
            ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
            [["*  61 Cyg A", "GJ 820 A", "K5V", "11.40"],     # double-space name
             ["*  61 Cyg B", "GJ 820 B", "K7V", "11.40"],
             ["NAME Barnard's star", "GJ 699", "M4V", "5.96"],
             ["Wolf  359", "GJ 406", "M6", "7.86"]])
        p._link_view = view
        map_stars = [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "*  61 Cyg A", "desig": "GJ 820 A", "sp_type": "K5V",
             "color": "#ffd2a1", "ly": 11.4, "x": 6.5, "y": 6.1, "z": 7.1},
            {"name": "*  61 Cyg B", "desig": "GJ 820 B", "sp_type": "K7V",
             "color": "#ffd2a1", "ly": 11.4, "x": 6.5, "y": 6.1, "z": 7.2},
            {"name": "NAME Barnard's star", "desig": "GJ 699", "sp_type": "M4V",
             "color": "#ff9d6c", "ly": 5.96, "x": -0.06, "y": 5.94, "z": 0.49},
            {"name": "Wolf  359", "desig": "GJ 406", "sp_type": "M6",
             "color": "#dfe6ff", "ly": 7.86, "x": -7.42, "y": 2.1, "z": 1.02},
        ]
        _add_map_tabs(p, map_stars, 15.0, "title")
        return p

    def _find(self, p, q):
        from gui.panels.distance_stars import _find_on_map
        p._find_input.setText(q)
        _find_on_map(p)

    def test_find_box_present_after_render(self):
        p = self._panel()
        self.assertEqual(len(p._link_canvases), 5)
        self.assertIsNotNone(getattr(p, "_find_widget", None))
        self.assertIsNotNone(getattr(p, "_find_input", None))

    def test_whitespace_normalized_name_and_designation(self):
        p = self._panel()
        # single-space query matches the double-space stored name
        self._find(p, "61 Cyg A")
        self.assertEqual(p._find_readout.text(), "Found: *  61 Cyg A")
        self.assertTrue(all(c.highlighted_star() == "*  61 Cyg A"
                            for c in p._link_canvases))
        # designation hit (case-insensitive)
        self._find(p, "gj 699")
        self.assertTrue(all(c.highlighted_star() == "NAME Barnard's star"
                            for c in p._link_canvases))

    def test_multiple_matches_cycle(self):
        p = self._panel()
        self._find(p, "61 Cyg")
        self.assertIn("1 of 2", p._find_readout.text())
        first = {c.highlighted_star() for c in p._link_canvases}
        self._find(p, "61 Cyg")
        self.assertIn("2 of 2", p._find_readout.text())
        second = {c.highlighted_star() for c in p._link_canvases}
        self.assertNotEqual(first, second)
        self._find(p, "61 Cyg")                      # wraps back to the first
        self.assertIn("1 of 2", p._find_readout.text())

    def test_no_match_keeps_highlight_and_sets_status(self):
        p = self._panel()
        self._find(p, "barnard")
        before = {c.highlighted_star() for c in p._link_canvases}
        self._find(p, "zzzzz")
        self.assertEqual(p._find_readout.text(), "No match")
        self.assertIn("No star matching", p.window._status)
        after = {c.highlighted_star() for c in p._link_canvases}
        self.assertEqual(before, after)              # no stale-highlight change

    def test_empty_query_is_noop(self):
        p = self._panel()
        self._find(p, "barnard")
        ro = p._find_readout.text()
        self._find(p, "   ")                          # blank → no-op
        self.assertEqual(p._find_readout.text(), ro)

    def test_clear_button_resets_box_and_highlight(self):
        from gui.panels.distance_stars import _clear_find
        p = self._panel()
        self._find(p, "61 Cyg")
        self.assertTrue(p._find_input.text())
        self.assertIn("of 2", p._find_readout.text())
        self.assertTrue(any(c.highlighted_star() for c in p._link_canvases))
        _clear_find(p)                                # the Find-box Clear button
        self.assertEqual(p._find_input.text(), "")
        self.assertEqual(p._find_readout.text(), "")
        self.assertEqual(p._find_matches, [])
        self.assertTrue(all(c.highlighted_star() is None
                            for c in p._link_canvases))

    def test_clear_recenters_map(self):
        from gui.panels.distance_stars import _clear_find
        # A 2D star chart starts centred on the origin (±limit); find shifts it,
        # Clear restores the original view.
        sc = None
        p = self._panel()
        for c in p._link_canvases:
            ax = c.figure.axes[0]
            if (c.figure.axes[0].get_facecolor()[0] < 0.1
                    and "3d" not in type(ax).__name__.lower()):
                sc = c
                break
        self.assertIsNotNone(sc)
        before = (sc.figure.axes[0].get_xlim(), sc.figure.axes[0].get_ylim())
        self._find(p, "61 Cyg A")                     # shifts the view off-origin
        self.assertNotEqual((sc.figure.axes[0].get_xlim(),
                             sc.figure.axes[0].get_ylim()), before)
        _clear_find(p)
        self.assertEqual((sc.figure.axes[0].get_xlim(),
                          sc.figure.axes[0].get_ylim()), before)

    def test_center_on_capability_moves_view(self):
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        stars = [
            {"name": "Sol", "sp_type": "G2V", "color": "#fff4c2", "ly": 0.0,
             "x": 0.0, "y": 0.0, "z": 0.0, "desig": ""},
            {"name": "Barnard", "sp_type": "M4V", "color": "#ff9d6c", "ly": 6.0,
             "x": 0.0, "y": 6.0, "z": 0.0, "desig": ""},
        ]
        c, _ = make_star_chart_canvas(None, stars, 15.0)
        self.assertTrue(callable(getattr(c, "center_on", None)))
        self.assertTrue(c.center_on("Barnard"))
        y0, y1 = c.figure.axes[0].get_ylim()
        self.assertAlmostEqual((y0 + y1) / 2.0, 6.0, places=6)   # centred on star
        self.assertFalse(c.center_on("DoesNotExist"))            # graceful no-op

    def test_find_reveals_hidden_class(self):
        from matplotlib.backend_bases import PickEvent, MouseEvent
        p = self._panel()
        # Hide class M on the Star Chart canvas via a legend pick.
        sc = next(c for c in p._link_canvases
                  if c.figure.axes[0].get_facecolor()[0] < 0.1
                  and c.figure.axes[0].get_legend() is not None
                  and "3d" not in type(c.figure.axes[0]).__name__.lower())
        ax = sc.figure.axes[0]
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        m_handle = leg.legend_handles[texts.index("Class M")]
        me = MouseEvent("button_press_event", sc, 0, 0)
        sc.callbacks.process("pick_event", PickEvent("pick_event", sc, me, m_handle))
        self.assertIn("M", _hidden_classes(ax))
        # Finding an M star un-hides class M on that canvas.
        self._find(p, "barnard")
        self.assertNotIn("M", _hidden_classes(ax))


def _hidden_classes(ax):
    """The set of spectral classes whose per-class scatter is currently hidden."""
    out = set()
    leg = ax.get_legend()
    if leg is None:
        return out
    for txt in leg.get_texts():
        if txt.get_alpha() not in (None, 1.0):
            out.add(txt.get_text().replace("Class ", ""))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# O-4 — Planet & System Diagrams
#   O3 Mass–Radius: prepare_mass_radius (null filter + skipped, key genericity,
#   density-curve anchor) + the canvas smoke + panel-tab wiring (opts 3, 6, Map).
# ─────────────────────────────────────────────────────────────────────────────
class O3MassRadiusPrepTest(unittest.TestCase):
    """core.viz.prepare_mass_radius — generic key filtering + skipped count."""

    def test_nasa_keys_filter_and_skip(self):
        planets = [
            {"pl_name": "b", "pl_bmasse": "4.8", "pl_rade": "1.9"},
            {"pl_name": "c", "pl_bmasse": "2.0", "pl_rade": None},      # no radius
            {"pl_name": "d", "pl_bmasse": None,  "pl_rade": "3.1"},     # no mass
            {"pl_name": "e", "pl_bmasse": "0",   "pl_rade": "0.9"},     # non-positive mass
        ]
        res = viz.prepare_mass_radius(planets, "pl_bmasse", "pl_rade", "pl_name")
        self.assertNotIn("error", res)
        self.assertEqual(len(res["planets"]), 1)
        self.assertEqual(res["skipped"], 3)
        self.assertEqual(res["planets"][0]["name"], "b")
        self.assertAlmostEqual(res["planets"][0]["mass_e"], 4.8)
        self.assertAlmostEqual(res["planets"][0]["radius_e"], 1.9)

    def test_hwc_keys_generic(self):
        rows = [{"P_NAME": "HWC b", "P_MASS": "1.2", "P_RADIUS": "1.05"}]
        res = viz.prepare_mass_radius(rows, "P_MASS", "P_RADIUS", "P_NAME")
        self.assertNotIn("error", res)
        self.assertEqual(res["planets"][0]["name"], "HWC b")
        self.assertAlmostEqual(res["planets"][0]["mass_e"], 1.2)

    def test_none_qualify_is_error(self):
        rows = [{"pl_name": "x", "pl_bmasse": None, "pl_rade": None}]
        self.assertIn("error", viz.prepare_mass_radius(rows, "pl_bmasse", "pl_rade", "pl_name"))
        self.assertIn("error", viz.prepare_mass_radius([], "pl_bmasse", "pl_rade", "pl_name"))

    def test_comma_formatted_value_parses(self):
        rows = [{"pl_name": "big", "pl_bmasse": "1,234", "pl_rade": "11.2"}]
        res = viz.prepare_mass_radius(rows, "pl_bmasse", "pl_rade", "pl_name")
        self.assertAlmostEqual(res["planets"][0]["mass_e"], 1234.0)

    def test_rock_density_curve_anchor(self):
        # The "rock" reference curve uses ρ = ρ⊕ = 5.51, so R=(M/1)^(1/3): Earth
        # (M=1) lands at R=1 — the canvas's composition-curve anchor.
        from gui.visualizations.plot_helpers import _MR_CURVES, _RHO_EARTH
        rho = dict((nm, r) for nm, r, _c in _MR_CURVES)["rock"]
        self.assertEqual(rho, _RHO_EARTH)
        r_at_earth = (1.0 / (rho / _RHO_EARTH)) ** (1.0 / 3.0)
        self.assertAlmostEqual(r_at_earth, 1.0)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O3MassRadiusCanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_mass_radius_canvas
        data = {"planets": [
            {"name": "b", "mass_e": 4.8, "radius_e": 1.9},
            {"name": "c", "mass_e": 317.8, "radius_e": 11.21},
        ], "skipped": 2}
        build_canvas_ok(self, make_mass_radius_canvas, None, data)

    def test_canvas_error_passthrough(self):
        from gui.visualizations.plot_helpers import make_mass_radius_canvas
        build_canvas_ok(self, make_mass_radius_canvas, None, {"error": "none qualify"})


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O3PanelWiringSmokeTest(unittest.TestCase):
    """Mass–Radius tab builder adds a tab on opts 3/Map (NASA keys) and not when empty."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_nasa_tab_builder(self):
        import gui.panels as panels
        from gui.panels.nasa_exoplanet import _make_mass_radius_tab
        p = panels.NasaPlanetarySystemsPanel(self._StubWindow())
        planets = [{"pl_name": "b", "pl_bmasse": 4.8, "pl_rade": 1.9}]
        self.assertIsNotNone(_make_mass_radius_tab(p, planets))
        # No qualifying planet → no tab.
        self.assertIsNone(_make_mass_radius_tab(
            p, [{"pl_name": "x", "pl_bmasse": None, "pl_rade": None}]))

    def test_hwc_panel_constructs(self):
        import gui.panels as panels
        p = panels.HwcPanel(self._StubWindow())
        self.assertIsNotNone(p)


# ─────────────────────────────────────────────────────────────────────────────
# O-4 — O4 Solar System Reference Overlay (additive solar_overlay param + the
#   "Show Solar System reference" checkbox that rebuilds the orbits canvas).
# ─────────────────────────────────────────────────────────────────────────────
def _simple_orbit(sma=1.0, name="b", color="#4fc3f7"):
    th = [2 * math.pi * i / 36 for i in range(37)]
    return {"name": name, "sma": sma, "peri": sma, "apo": sma, "ecc": 0.0,
            "x_pts": [sma * math.cos(t) for t in th],
            "y_pts": [sma * math.sin(t) for t in th], "color": color}


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O4SolarOverlayCanvasTest(unittest.TestCase):
    """make_orbits_canvas solar_overlay: default-off additivity + overlay circles."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _circle_count(canvas):
        from matplotlib.patches import Circle
        ax = canvas.figure.axes[0]
        return sum(1 for p in ax.patches if isinstance(p, Circle))

    def test_default_off_is_additive(self):
        from gui.visualizations.plot_helpers import make_orbits_canvas
        orbits = [_simple_orbit()]
        c_default, _ = make_orbits_canvas(None, orbits, [], 35.0)
        c_off, _ = make_orbits_canvas(None, orbits, [], 35.0, solar_overlay=False)
        # Default (param absent) draws exactly the same circles as explicit off.
        self.assertEqual(self._circle_count(c_default), self._circle_count(c_off))

    def test_overlay_adds_all_eight_when_in_frame(self):
        from gui.visualizations.plot_helpers import make_orbits_canvas
        orbits = [_simple_orbit()]
        base = self._circle_count(make_orbits_canvas(None, orbits, [], 35.0)[0])
        on, _ = make_orbits_canvas(None, orbits, [], 35.0, solar_overlay=True)
        # max_au×1.1 = 38.5 ≥ Neptune (30.069) → all 8 reference circles added.
        self.assertEqual(self._circle_count(on), base + 8)

    def test_overlay_respects_max_au_filter(self):
        from gui.visualizations.plot_helpers import make_orbits_canvas
        orbits = [_simple_orbit()]
        base = self._circle_count(make_orbits_canvas(None, orbits, [], 2.0)[0])
        on, _ = make_orbits_canvas(None, orbits, [], 2.0, solar_overlay=True)
        # max_au×1.1 = 2.2 → only Mercury/Venus/Earth/Mars fit (Jupiter 5.203 out).
        self.assertEqual(self._circle_count(on), base + 4)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O4OrbitsToggleWiringTest(unittest.TestCase):
    """The Orbital Diagram tab carries a checkbox that rebuilds the canvas."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_orbits_tab_has_checkbox_and_rebuilds(self):
        import gui.panels as panels
        from gui.panels.nasa_exoplanet import _make_orbits_tab
        from PySide6.QtWidgets import QCheckBox
        p = panels.NasaPlanetarySystemsPanel(self._StubWindow())
        planets = [{"pl_name": "b", "pl_orbsmax": "1.0", "pl_orbeccen": "0.0",
                    "st_teff": "5778", "st_rad": "1.0", "hostname": "Test"}]
        w = _make_orbits_tab(p, planets)
        self.assertIsNotNone(w)
        chk = w.findChild(QCheckBox)
        self.assertIsNotNone(chk)
        self.assertFalse(chk.isChecked())          # default unchecked
        chk.setChecked(True)                        # rebuild w/ overlay
        chk.setChecked(False)                       # rebuild back — no exception

    def test_wrapper_returns_none_when_canvas_fails(self):
        from gui.visualizations.plot_helpers import wrap_orbits_with_solar_toggle
        # A builder that yields no canvas → wrapper returns None (no empty tab).
        self.assertIsNone(
            wrap_orbits_with_solar_toggle(None, lambda _ov, _h: (None, None)))


# ─────────────────────────────────────────────────────────────────────────────
# O-4 — O13 Transit Geometry: prepare_transit_geometry (b = (a/R★)·cos i anchor,
#   skip list, error gates) + the canvas smoke + panel-tab wiring (opts 3, Map).
# ─────────────────────────────────────────────────────────────────────────────
class O13TransitGeometryPrepTest(unittest.TestCase):

    def test_b_formula_anchor(self):
        # st_rad=1 R☉ → R★ = 0.00465 AU. a = R★, i = 0 → b = (1)·cos0 = 1.0 (limb).
        planets = [
            {"pl_name": "edge", "st_rad": "1.0", "pl_orbsmax": str(viz._R_SUN_AU),
             "pl_orbincl": "0"},
            {"pl_name": "central", "st_rad": "1.0", "pl_orbsmax": "0.5",
             "pl_orbincl": "90"},   # cos 90° = 0 → b = 0 (dead-centre transit)
        ]
        res = viz.prepare_transit_geometry(planets)
        self.assertNotIn("error", res)
        self.assertAlmostEqual(res["star_radius_au"], 0.00465)
        by_name = {p["name"]: p for p in res["planets"]}
        self.assertAlmostEqual(by_name["edge"]["b"], 1.0, places=6)
        self.assertAlmostEqual(by_name["central"]["b"], 0.0, places=6)

    def test_skip_missing_inclination_and_sma(self):
        planets = [
            {"pl_name": "ok", "st_rad": "0.8", "pl_orbsmax": "0.1", "pl_orbincl": "89"},
            {"pl_name": "no_incl", "st_rad": "0.8", "pl_orbsmax": "0.2",
             "pl_orbincl": None},                                   # skipped
            {"pl_name": "no_sma", "st_rad": "0.8", "pl_orbsmax": None,
             "pl_orbincl": "88"},                                   # skipped
        ]
        res = viz.prepare_transit_geometry(planets)
        self.assertEqual(len(res["planets"]), 1)
        self.assertEqual(res["planets"][0]["name"], "ok")
        self.assertEqual(res["skipped"], 2)

    def test_error_when_no_stellar_radius(self):
        planets = [{"pl_name": "x", "pl_orbsmax": "0.1", "pl_orbincl": "89"}]
        self.assertIn("error", viz.prepare_transit_geometry(planets))
        planets2 = [{"pl_name": "x", "st_rad": "0", "pl_orbsmax": "0.1", "pl_orbincl": "89"}]
        self.assertIn("error", viz.prepare_transit_geometry(planets2))

    def test_error_when_no_inclination_at_all(self):
        planets = [{"pl_name": "x", "st_rad": "1.0", "pl_orbsmax": "0.1",
                    "pl_orbincl": None}]
        self.assertIn("error", viz.prepare_transit_geometry(planets))
        self.assertIn("error", viz.prepare_transit_geometry([]))

    def test_stellar_radius_found_on_later_row(self):
        # st_rad absent on the first row but present on a later one → still resolves.
        planets = [
            {"pl_name": "a", "pl_orbsmax": "0.1", "pl_orbincl": "89"},
            {"pl_name": "b", "st_rad": "1.2", "pl_orbsmax": "0.2", "pl_orbincl": "88"},
        ]
        res = viz.prepare_transit_geometry(planets)
        self.assertNotIn("error", res)
        self.assertAlmostEqual(res["star_radius_au"], 1.2 * viz._R_SUN_AU)
        self.assertEqual(len(res["planets"]), 2)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O13TransitCanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_transit_canvas
        data = {"star_radius_au": 0.00465, "skipped": 1, "planets": [
            {"name": "b", "a_au": 0.05, "incl_deg": 89.6, "b": 0.4},     # transiting
            {"name": "e", "a_au": 1.1, "incl_deg": 87.2, "b": 7.4},      # misses (clamped)
        ]}
        build_canvas_ok(self, make_transit_canvas, None, data)

    def test_canvas_error_passthrough(self):
        from gui.visualizations.plot_helpers import make_transit_canvas
        build_canvas_ok(self, make_transit_canvas, None, {"error": "no inclination"})


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O13PanelWiringSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_transit_tab_builder(self):
        import gui.panels as panels
        from gui.panels.nasa_exoplanet import _make_transit_tab
        p = panels.NasaPlanetarySystemsPanel(self._StubWindow())
        planets = [{"pl_name": "b", "st_rad": "1.0", "pl_orbsmax": "0.05",
                    "pl_orbincl": "89.6"}]
        self.assertIsNotNone(_make_transit_tab(p, planets))
        # No inclination → no tab (additive).
        self.assertIsNone(_make_transit_tab(
            p, [{"pl_name": "x", "st_rad": "1.0", "pl_orbsmax": "0.1",
                 "pl_orbincl": None}]))


# ─────────────────────────────────────────────────────────────────────────────
# O-4 — O14 Planet Size-Comparison Strip (canvas-only, no prepare_*): qualifies
#   when ≥1 planet has a radius; radius-less planets footnoted; (None,None) when
#   none qualify; generic over NASA/HWC keys + panel-tab wiring (opts 3, 6, Map).
# ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O14SizeStripCanvasTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_builds_with_nasa_keys_and_footnote(self):
        from gui.visualizations.plot_helpers import make_size_comparison_canvas
        planets = [
            {"pl_name": "b", "pl_rade": "1.9"},
            {"pl_name": "c", "pl_rade": "0.0"},      # non-positive → footnoted
            {"pl_name": "g", "pl_rade": None},        # missing → footnoted
        ]
        canvas, _ = make_size_comparison_canvas(None, planets, "pl_rade", "pl_name")
        self.assertIsNotNone(canvas)
        ax = canvas.figure.axes[0]
        # Earth + Jupiter anchors are always present → ≥3 circles (1 planet + 2).
        from matplotlib.patches import Circle
        n_circles = sum(1 for p in ax.patches if isinstance(p, Circle))
        self.assertEqual(n_circles, 3)
        # Footnote lists the radius-less planets.
        foot = " ".join(t.get_text() for t in canvas.figure.texts)
        self.assertIn("No radius", foot)
        self.assertIn("g", foot)
        self.assertIn("c", foot)

    def test_builds_with_hwc_keys(self):
        from gui.visualizations.plot_helpers import make_size_comparison_canvas
        rows = [{"P_NAME": "HWC b", "P_RADIUS": "2.4"}]
        canvas, _ = make_size_comparison_canvas(None, rows, "P_RADIUS", "P_NAME")
        self.assertIsNotNone(canvas)

    def test_none_when_no_radius(self):
        from gui.visualizations.plot_helpers import make_size_comparison_canvas
        rows = [{"pl_name": "x", "pl_rade": None}, {"pl_name": "y", "pl_rade": ""}]
        canvas, toolbar = make_size_comparison_canvas(None, rows, "pl_rade", "pl_name")
        self.assertIsNone(canvas)
        self.assertIsNone(toolbar)
        # Empty list → also (None, None).
        self.assertEqual(make_size_comparison_canvas(None, [], "pl_rade", "pl_name"),
                         (None, None))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O14PanelWiringSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_nasa_size_tab_builder(self):
        import gui.panels as panels
        from gui.panels.nasa_exoplanet import _make_size_tab
        p = panels.NasaPlanetarySystemsPanel(self._StubWindow())
        self.assertIsNotNone(_make_size_tab(p, [{"pl_name": "b", "pl_rade": "1.9"}]))
        # No radius anywhere → no tab.
        self.assertIsNone(_make_size_tab(p, [{"pl_name": "x", "pl_rade": None}]))


# ─────────────────────────────────────────────────────────────────────────────
# O-5 — O9 Brachistochrone Profile Charts: prepare_brachistochrone_profiles
#   reconstructs each profile's piecewise v(t)/d(t) from accel_g + total time +
#   profile type, using the docs/calculators.md formulas. Anchors: every profile
#   starts at (0,0,0); its final cumulative distance reproduces the core's
#   distance for that profile; profile-1 peak velocity = √(a·D); colours fixed.
# ─────────────────────────────────────────────────────────────────────────────
_O9_G   = 9.80665
_O9_C   = 299_792_458.0
_O9_AU  = 149_597_870_700.0


class O9BrachistochroneProfilePrepTest(unittest.TestCase):
    """core.viz.prepare_brachistochrone_profiles — segment reconstruction."""

    def test_style_a_time_given_distance(self):
        # opts 22/29/30 shape: top-level distance_au, profiles carry "hours".
        res = calc.compute_travel_time_system_au(1.0, 5.2)
        out = viz.prepare_brachistochrone_profiles(res)
        self.assertEqual(out["accel_g"], 1.0)
        self.assertEqual(len(out["profiles"]), 3)
        # Colours fixed per index.
        self.assertEqual([p["color"] for p in out["profiles"]],
                         ["#c0392b", "#2980b9", "#27ae60"])
        for p in out["profiles"]:
            # Every profile starts at the origin.
            self.assertAlmostEqual(p["t_hours"][0], 0.0)
            self.assertAlmostEqual(p["v_kms"][0], 0.0)
            self.assertAlmostEqual(p["d_au"][0], 0.0)
            # Cumulative distance reproduces the brachistochrone distance.
            self.assertAlmostEqual(p["d_au"][-1], 5.2, places=3)
            # Velocity returns to ~0 at arrival (decel profiles) or stays positive
            # (none here is a no-decel profile), but never negative.
            self.assertGreaterEqual(min(p["v_kms"]), -1e-6)
        # Profile 1 peak velocity at the midpoint = √(a·D).
        a   = 1.0 * _O9_G
        D_m = 5.2 * _O9_AU
        v_peak_kms = math.sqrt(a * D_m) / 1000.0
        mid = len(out["profiles"][0]["v_kms"]) // 2
        self.assertAlmostEqual(out["profiles"][0]["v_kms"][mid], v_peak_kms, places=1)

    def test_style_a_profile3_cap_reached(self):
        # A large distance makes profile 3 actually reach the 3% c cap.
        res = calc.compute_travel_time_system_au(1.0, 200_000.0)
        out = viz.prepare_brachistochrone_profiles(res)
        p3 = out["profiles"][2]
        self.assertAlmostEqual(p3["d_au"][-1], 200_000.0, places=0)
        # Peak velocity is capped at 3% c.
        v_cap_kms = 0.03 * _O9_C / 1000.0
        self.assertAlmostEqual(max(p3["v_kms"]), v_cap_kms, places=1)

    def test_style_b_distance_given_time(self):
        # opt 24 shape: top-level "hours" shared; each profile carries distance_au.
        res = calc.compute_distance_at_acceleration(1.0, 100.0)
        out = viz.prepare_brachistochrone_profiles(res)
        self.assertEqual(len(out["profiles"]), 3)
        for core_p, viz_p in zip(res["profiles"], out["profiles"]):
            self.assertAlmostEqual(viz_p["d_au"][-1], core_p["distance_au"], places=3)
        # Profile 1 here is continuous accel (no decel) → velocity monotonically rises.
        v = out["profiles"][0]["v_kms"]
        self.assertTrue(all(v[i] <= v[i + 1] + 1e-9 for i in range(len(v) - 1)))

    def test_style_c_custom_thrust(self):
        # opt 23 shape: single profile, no "profiles" list. Hand-built result.
        a, t_acc, t_coast = 1.0 * _O9_G, 36000.0, 72000.0   # 10 h burn, 20 h coast
        expected_d_m = a * t_acc ** 2 + a * t_acc * t_coast
        result = {
            "accel_g": 1.0, "fallback": False,
            "t_total_hours": (2 * t_acc + t_coast) / 3600.0,
            "t_accel_hours": t_acc / 3600.0,
            "t_coast_hours": t_coast / 3600.0,
        }
        out = viz.prepare_brachistochrone_profiles(result)
        self.assertEqual(len(out["profiles"]), 1)
        self.assertEqual(out["profiles"][0]["color"], "#c0392b")
        self.assertAlmostEqual(out["profiles"][0]["d_au"][-1],
                               expected_d_m / _O9_AU, places=5)
        # Coast phase holds a constant velocity (a flat middle segment exists).
        v = out["profiles"][0]["v_kms"]
        self.assertGreater(max(v), 0.0)

    def test_style_c_fallback(self):
        a, t_half = 1.0 * _O9_G, 36000.0
        result = {
            "accel_g": 1.0, "fallback": True,
            "t_total_hours": (2 * t_half) / 3600.0,
            "t_accel_hours": t_half / 3600.0, "t_coast_hours": 0.0,
        }
        out = viz.prepare_brachistochrone_profiles(result)
        self.assertEqual(len(out["profiles"]), 1)
        self.assertAlmostEqual(out["profiles"][0]["d_au"][-1],
                               (a * t_half ** 2) / _O9_AU, places=5)

    def test_error_paths(self):
        self.assertIn("error", viz.prepare_brachistochrone_profiles({"error": "x"}))
        self.assertIn("error", viz.prepare_brachistochrone_profiles({}))
        self.assertIn("error", viz.prepare_brachistochrone_profiles(
            {"accel_g": 0.0, "profiles": []}))
        self.assertIn("error", viz.prepare_brachistochrone_profiles(
            {"accel_g": 1.0, "distance_au": 5.0}))   # no profiles, no t_total_hours


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O9ProfileCanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_profile_canvas
        data = viz.prepare_brachistochrone_profiles(
            calc.compute_travel_time_system_au(1.0, 5.2))
        build_canvas_ok(self, make_profile_canvas, None, data)

    def test_error_canvas(self):
        from gui.visualizations.plot_helpers import make_profile_canvas
        build_canvas_ok(self, make_profile_canvas, None, {"error": "no data"})


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O9PanelWiringSmokeTest(unittest.TestCase):
    """Construct the host panels offscreen and exercise the O9 tab builders."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def test_brachistochrone_panels_construct_and_add_tab(self):
        import gui.panels as panels
        from gui.panels.brachistochrone import _add_profile_tab
        win = self._StubWindow()
        for cls, result in (
            (panels.BrachistochroneAuPanel, calc.compute_travel_time_system_au(1.0, 4.2)),
            (panels.BrachistochroneLmPanel, calc.compute_travel_time_system_lm(1.0, 35.0)),
            (panels.BrachistochroneAccelPanel, calc.compute_distance_at_acceleration(1.0, 24.0)),
        ):
            p = cls(win)
            n0 = p._viz_tabs_widget.count()
            _add_profile_tab(p, result)
            self.assertEqual(p._viz_tabs_widget.count(), n0 + 1)

    def test_system_travel_profile_tab_builder(self):
        import gui.panels as panels
        from gui.panels.system_travel import _add_profile_tab
        # opt 23 custom-thrust shape (no network — hand-built result).
        result = {
            "accel_g": 1.0, "fallback": False,
            "t_total_hours": 50.0, "t_accel_hours": 10.0, "t_coast_hours": 30.0,
        }
        p = panels.SystemTravelThrustPanel(self._StubWindow())
        n0 = p._viz_tabs_widget.count()
        _add_profile_tab(p, result)
        self.assertEqual(p._viz_tabs_widget.count(), n0 + 1)


# ─────────────────────────────────────────────────────────────────────────────
# O-5 — O5 Date Scrubber: pure date/span helpers + the System Map scrubber's
#   offline recompute (day-0 == the one-shot Search; epoch_known=False pinned).
# ─────────────────────────────────────────────────────────────────────────────
class O5ScrubberHelpersTest(unittest.TestCase):
    """Pure span/date helpers in gui.panels.nasa_exoplanet (no Qt needed)."""

    def test_span_days(self):
        from gui.panels.nasa_exoplanet import _scrub_span_days
        # 2 × longest period.
        self.assertEqual(_scrub_span_days(
            [{"pl_orbper": "100"}, {"pl_orbper": "400"}]), 800)
        # No usable period → 365-day fallback.
        self.assertEqual(_scrub_span_days([{"pl_name": "x"}]), 365)
        # Capped at 50 yr.
        self.assertEqual(_scrub_span_days([{"pl_orbper": "100000"}]),
                         int(round(50.0 * 365.25)))

    def test_offset_date_iso(self):
        from gui.panels.nasa_exoplanet import _scrub_offset_date_iso
        self.assertEqual(_scrub_offset_date_iso("2026-06-14", 30), "2026-07-14")
        self.assertEqual(_scrub_offset_date_iso("2026-06-14", -14), "2026-05-31")
        self.assertEqual(_scrub_offset_date_iso("2026-06-14", 0), "2026-06-14")


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O5ScrubberRecomputeTest(unittest.TestCase):
    """The System Map scrubber re-offsets epoch-known planets; pins the rest."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _fixture(self):
        return [
            {"pl_name": "b", "pl_orbsmax": "1.0", "pl_orbeccen": "0.1",
             "pl_orbper": "365.0", "pl_orbtper": "2451545.0", "hostname": "Test"},
            {"pl_name": "c", "pl_orbsmax": "2.0", "pl_orbeccen": "0.2"},  # no epoch
        ]

    def test_day0_anchor_and_pinned(self):
        from gui.panels.nasa_exoplanet import (
            _SystemMapScrubber, _scrub_offset_date_iso)
        planets = self._fixture()
        base = "2026-06-14"
        base_data = viz.prepare_exoplanet_system_diagram(planets, base)
        scr = _SystemMapScrubber(None, base_data, planets, base, None)
        scrub = scr._canvas._scrub
        self.assertTrue(scrub["planets"]["b"]["epoch_known"])
        self.assertFalse(scrub["planets"]["c"]["epoch_known"])

        bd = {p["name"]: p for p in base_data["planets"]}
        # Day-0: the marker sits exactly where the one-shot Search placed it.
        off_b0 = scrub["planets"]["b"]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_b0[0]), bd["b"]["x"], places=6)
        self.assertAlmostEqual(float(off_b0[1]), bd["b"]["y"], places=6)
        off_c0 = scrub["planets"]["c"]["scatter"].get_offsets()[0]

        # Scrub +90 days: epoch-known 'b' moves to the recomputed position.
        scr._slider.setValue(90)
        scr._recompute()
        exp = viz.prepare_exoplanet_system_diagram(
            planets, _scrub_offset_date_iso(base, 90))
        exp_b = {p["name"]: p for p in exp["planets"]}["b"]
        off_b1 = scrub["planets"]["b"]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_b1[0]), exp_b["x"], places=6)
        self.assertAlmostEqual(float(off_b1[1]), exp_b["y"], places=6)
        self.assertNotAlmostEqual(float(off_b1[0]), float(off_b0[0]), places=4)

        # epoch-unknown 'c' stays pinned at periastron (no invented motion).
        off_c1 = scrub["planets"]["c"]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_c1[0]), float(off_c0[0]), places=9)
        self.assertAlmostEqual(float(off_c1[1]), float(off_c0[1]), places=9)

        # Reset snaps the slider back to centre (base date) and re-centres 'b'.
        scr._reset()
        self.assertEqual(scr._slider.value(), 0)
        off_b2 = scrub["planets"]["b"]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_b2[0]), bd["b"]["x"], places=6)
        self.assertAlmostEqual(float(off_b2[1]), bd["b"]["y"], places=6)

    def test_map_panel_constructs(self):
        import gui.panels as panels

        class _StubWindow:
            pass
        p = panels.NasaPlanetarySystemsMapPanel(_StubWindow())
        self.assertIsNotNone(p)


# ─────────────────────────────────────────────────────────────────────────────
# O-5 — O5b Solar-map ephemeris animation: the range-fetch core fn (mocked
#   Horizons), the pure body-id/span helpers, and the scrubber's frame stepping.
# ─────────────────────────────────────────────────────────────────────────────
class O5bEphemerisTrackTest(unittest.TestCase):
    """core.calculators.compute_solar_ephemeris_track — batch range fetch."""

    def test_track_mocked_horizons(self):
        from unittest.mock import patch
        vec = {"x": [1.0, 1.1, 1.2], "y": [0.0, 0.1, 0.2], "z": [0.0, 0.0, 0.0],
               "datetime_jd": [2451545.0, 2451546.0, 2451547.0]}
        with patch("astroquery.jplhorizons.Horizons") as MockH:
            MockH.return_value.vectors.return_value = vec
            res = calc.compute_solar_ephemeris_track(
                ["399", "499", "399"], "2026-06-01", "2026-06-30", n_steps=3)
        self.assertNotIn("error", res)
        self.assertEqual(set(res["bodies"].keys()), {"399", "499"})  # deduped
        self.assertEqual(len(res["jds"]), 3)
        self.assertEqual(res["dates"][0], "2000-01-01")              # jd 2451545
        self.assertEqual(res["bodies"]["399"]["x"], [1.0, 1.1, 1.2])

    def test_no_bodies(self):
        res = calc.compute_solar_ephemeris_track([], "2026-06-01", "2026-06-30")
        self.assertIn("error", res)


class O5bSolarHelpersTest(unittest.TestCase):
    """Pure body-id / span helpers in gui.panels.system_travel (no Qt needed)."""

    def _map_data(self):
        return {
            "origin_name": "Earth", "dest_name": "Mars",
            "origin_id": "399", "dest_id": "499",
            "origin_xyz": (1.0, 0.0, 0.0), "dest_xyz": (0.0, 1.52, 0.0),
            "planets": [
                {"name": "Earth", "x": 1.0, "y": 0.0, "z": 0.0,
                 "color": "#4fc3f7", "horizons_id": "399"},
                {"name": "Neptune", "x": 30.0, "y": 0.0, "z": 0.0,   # out of view
                 "color": "#5b8df5", "horizons_id": "899"},
            ],
            "planet_orbits": [{"name": "Earth", "sma_au": 1.0, "color": "#4fc3f7"}],
            "max_au": 2.0,
        }

    def test_offset_date(self):
        from gui.panels.system_travel import _offset_date_iso
        self.assertEqual(_offset_date_iso("2026-06-14", 10), "2026-06-24")
        self.assertEqual(_offset_date_iso("2026-06-14", -14), "2026-05-31")

    def test_body_ids_dedup_and_inview(self):
        from gui.panels.system_travel import _solar_anim_body_ids
        ids = _solar_anim_body_ids(self._map_data())
        # origin + dest + the in-view Earth planet; Neptune (30 AU) excluded.
        self.assertEqual(ids, ["399", "499"])

    def test_span_days(self):
        from gui.panels.system_travel import _solar_anim_span_days
        span = _solar_anim_span_days(self._map_data())
        # 2 × 1.52^1.5 yr ≈ 3.75 yr, floored at 2 yr, capped at 50 yr.
        self.assertGreater(span, int(2 * 365.25))
        self.assertLessEqual(span, int(round(50 * 365.25)))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O5bSolarScrubberTest(unittest.TestCase):
    """The solar-map scrubber re-offsets markers from a cached track."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_frame_moves_markers(self):
        import astropy.time
        from gui.panels.system_travel import _SolarMapScrubber
        map_data = {
            "origin_name": "Earth", "dest_name": "Mars",
            "origin_id": "399", "dest_id": "499",
            "origin_xyz": (1.0, 0.0, 0.0), "dest_xyz": (0.0, 1.5, 0.0),
            "planets": [{"name": "Earth", "x": 1.0, "y": 0.0, "z": 0.0,
                         "color": "#4fc3f7", "horizons_id": "399"}],
            "planet_orbits": [{"name": "Earth", "sma_au": 1.0, "color": "#4fc3f7"}],
            "max_au": 2.0,
        }
        base = "2026-06-14"
        scr = _SolarMapScrubber(None, map_data, base, None)
        # Controls start hidden until ephemeris loads.
        self.assertFalse(scr._slider.isVisible())

        base_jd = astropy.time.Time(f"{base}T12:00:00").jd
        track = {
            "dates": ["2026-06-01", "2026-06-14", "2026-06-27"],
            "jds":   [base_jd - 13, base_jd, base_jd + 13],
            "bodies": {
                "399": {"x": [0.9, 1.0, 1.1], "y": [0.0, 0.0, 0.0], "z": [0, 0, 0]},
                "499": {"x": [0.0, 0.0, 0.0], "y": [1.4, 1.5, 1.6], "z": [0, 0, 0]},
            },
        }
        scr._on_track(track)
        # Slider spans the samples; centred on the base date (index 1).
        self.assertEqual(scr._slider.maximum(), 2)
        self.assertEqual(scr._base_index, 1)

        scrub = scr._canvas._scrub
        scr._frame(2)
        off_o = scrub["bodies"][("origin", "Earth")]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_o[0]), 1.1, places=6)
        off_d = scrub["bodies"][("dest", "Mars")]["scatter"].get_offsets()[0]
        self.assertAlmostEqual(float(off_d[1]), 1.6, places=6)

        # Reset → back to the base-date sample.
        scr._reset()
        self.assertEqual(scr._slider.value(), 1)

    def test_track_error_is_non_fatal(self):
        from gui.panels.system_travel import _SolarMapScrubber
        map_data = {
            "origin_name": "Earth", "dest_name": "Mars",
            "origin_id": "399", "dest_id": "499",
            "origin_xyz": (1.0, 0.0, 0.0), "dest_xyz": (0.0, 1.5, 0.0),
            "planets": [], "planet_orbits": [], "max_au": 2.0,
        }
        scr = _SolarMapScrubber(None, map_data, "2026-06-14", None)
        scr._on_track({"error": "JPL Horizons unreachable."})
        self.assertFalse(scr._slider.isVisible())  # stays in pre-load state
        self.assertIn("unreachable", scr._readout.text())


# ─────────────────────────────────────────────────────────────────────────────
# O-5 — O8 Two-Star Map (opts 17/20/21): the node-conversion / edge-label helper
#   (offline, hand-checkable geometry) + canvas smoke + panel tab wiring.
# ─────────────────────────────────────────────────────────────────────────────
class O8TwoStarRouteMapTest(unittest.TestCase):
    """gui.panels.route_planning._two_star_route_map — node/edge conversion."""

    def test_distance_with_sol_endpoint(self):
        from gui.panels.route_planning import _two_star_route_map
        result = {
            "star1_info": {"name": "Sol", "ra_deg": 0.0, "dec_deg": 0.0,
                           "ly": 0.0, "desig_str": ""},
            "star2_info": {"name": "Star2", "ra_deg": 0.0, "dec_deg": 0.0,
                           "ly": 10.0, "desig_str": "HD 1"},
            "distance_ly": 10.0,
        }
        rm = _two_star_route_map(result, "distance")
        # An endpoint is Sol (at the origin) → no extra Sol node.
        self.assertEqual(len(rm["stars"]), 2)
        self.assertEqual(rm["stars"][0]["name"], "Sol")
        self.assertAlmostEqual(rm["stars"][0]["x"], 0.0)
        self.assertAlmostEqual(rm["stars"][1]["x"], 10.0)   # ra=dec=0, ly=10 → (10,0,0)
        self.assertAlmostEqual(rm["stars"][1]["y"], 0.0)
        self.assertEqual(len(rm["edges"]), 1)
        e = rm["edges"][0]
        self.assertEqual(e["label"], "10.00 ly")
        self.assertEqual(e["style"], "dashed")
        self.assertAlmostEqual(e["x1"], 0.0)
        self.assertAlmostEqual(e["x2"], 10.0)

    def test_distance_neither_sol_appends_sol(self):
        from gui.panels.route_planning import _two_star_route_map
        result = {
            "star1_info": {"name": "A", "ra_deg": 0.0, "dec_deg": 0.0,
                           "ly": 4.0, "desig_str": ""},
            "star2_info": {"name": "B", "ra_deg": 90.0, "dec_deg": 0.0,
                           "ly": 3.0, "desig_str": ""},
            "distance_ly": 5.0,
        }
        rm = _two_star_route_map(result, "distance")
        self.assertEqual(len(rm["stars"]), 3)               # A, B, + grey Sol
        self.assertEqual(rm["stars"][2]["name"], "Sol")
        self.assertAlmostEqual(rm["stars"][2]["x"], 0.0)
        self.assertAlmostEqual(rm["stars"][1]["y"], 3.0)    # ra=90 → (0,3,0)
        self.assertEqual(rm["edges"][0]["label"], "5.00 ly")

    def test_travel_label_has_time_and_velocity(self):
        from gui.panels.route_planning import _two_star_route_map
        result = {
            "origin_info": {"name": "Sol", "ra_deg": 0.0, "dec_deg": 0.0,
                            "ly": 0.0, "desig_str": ""},
            "dest_info": {"name": "Eps Ind", "ra_deg": 0.0, "dec_deg": 0.0,
                          "ly": 11.4, "desig_str": ""},
            "distance_ly": 11.4, "times_c": 100.0, "travel_time_str": "4 Months",
        }
        rm = _two_star_route_map(result, "travel")
        self.assertEqual(rm["edges"][0]["label"], "11.40 ly — 4 Months @ 100×c")

    def test_error_passthrough(self):
        from gui.panels.route_planning import _two_star_route_map
        self.assertIn("error", _two_star_route_map({"error": "no match"}, "distance"))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O8TwoStarCanvasAndPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def _distance_result(self):
        return {
            "star1_info": {"name": "Sol", "ra_deg": 0.0, "dec_deg": 0.0,
                           "ly": 0.0, "desig_str": "", "ra_hms": "", "dec_dms": ""},
            "star2_info": {"name": "Vega", "ra_deg": 279.2, "dec_deg": 38.8,
                           "ly": 25.0, "desig_str": "HD 172167",
                           "ra_hms": "18 36 56", "dec_dms": "+38 47 01"},
            "distance_ly": 25.0, "distance_au": None,
        }

    def test_canvas_builds_with_routes(self):
        from gui.panels.route_planning import _two_star_route_map, _centered
        from gui.visualizations.plot_helpers import (
            make_star_chart_canvas, make_star_chart_3d_canvas)
        rm = _two_star_route_map(self._distance_result(), "distance")
        stars, edges, limit_ly = _centered(rm)
        build_canvas_ok(self, make_star_chart_canvas, None, stars,
                        limit_ly=limit_ly, routes=edges)
        build_canvas_ok(self, make_star_chart_3d_canvas, None, stars,
                        limit_ly=limit_ly, routes=edges)

    def test_panels_add_two_chart_tabs(self):
        import gui.panels as panels
        from gui.panels.route_planning import add_two_star_chart_tabs
        win = self._StubWindow()
        d = panels.DistanceBetweenStarsPanel(win)
        add_two_star_chart_tabs(d, self._distance_result(), "distance")
        self.assertEqual(d._viz_tabs_widget.count(), 2)   # Star Chart + Star Chart 3D
        self.assertEqual(d._viz_tabs_widget.tabText(0), "Star Chart")
        self.assertEqual(d._viz_tabs_widget.tabText(1), "Star Chart 3D")

        travel = {
            "origin_info": {"name": "Sol", "ra_deg": 0.0, "dec_deg": 0.0,
                            "ly": 0.0, "desig_str": ""},
            "dest_info": {"name": "Vega", "ra_deg": 279.2, "dec_deg": 38.8,
                          "ly": 25.0, "desig_str": ""},
            "distance_ly": 25.0, "times_c": 100.0, "ly_hr": 0.0114,
            "total_hours": 1.0, "travel_time_str": "3 Months",
        }
        t = panels.TravelTimeStarsTimesCPanel(win)
        add_two_star_chart_tabs(t, travel, "travel")
        self.assertEqual(t._viz_tabs_widget.count(), 2)


# ─────────────────────────────────────────────────────────────────────────────
# O-6 — O6 Sol Regions diagram parity (opt 13): the three existing ring preps
#   return valid shapes for the compute_sol_regions() dict; canvas smoke; the
#   panel gains 3 viz tabs without disturbing its 7 data tabs.
# ─────────────────────────────────────────────────────────────────────────────
import core.regions as regions


class O6SolRegionsPrepTest(unittest.TestCase):
    """The HZ / System-Regions / Alt-HZ preps work on the Sol regions dict."""

    def test_preps_valid_for_sol(self):
        d = regions.compute_sol_regions()
        # Anchor: Sol's circumstellar HZ inner/outer bracket ~1 AU.
        self.assertAlmostEqual(d["hzil"], 0.95, delta=0.1)
        self.assertAlmostEqual(d["hzol"], 1.37, delta=0.1)

        hz = viz.prepare_hz_diagram(d["temp"], d["calculatedLuminosity"])
        self.assertIn("zones", hz)
        self.assertNotIn("error", hz)

        sr = viz.prepare_system_regions_diagram(d)
        self.assertNotIn("error", sr)
        self.assertIn("regions", sr)

        alt = viz.prepare_alt_hz_diagram(d)
        self.assertIn("zones", alt)
        self.assertNotIn("error", alt)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O6SolRegionsCanvasAndPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_smoke(self):
        from gui.visualizations.plot_helpers import (
            make_hz_canvas, make_system_regions_canvas, make_alt_hz_canvas)
        d = regions.compute_sol_regions()
        hz = viz.prepare_hz_diagram(d["temp"], d["calculatedLuminosity"])
        build_canvas_ok(self, make_hz_canvas, None, hz["zones"], hz["max_au"])
        build_canvas_ok(self, make_system_regions_canvas, None,
                        viz.prepare_system_regions_diagram(d))
        alt = viz.prepare_alt_hz_diagram(d)
        build_canvas_ok(self, make_alt_hz_canvas, None, alt["zones"], alt["max_au"])

    def test_panel_has_seven_data_tabs_and_three_viz_tabs(self):
        import gui.panels as panels

        class _StubWindow:
            pass
        p = panels.SolRegionsPanel(_StubWindow())
        self.assertEqual(p._tables_widget.count(), 7)        # data tabs unchanged
        self.assertEqual(p._viz_tabs_widget.count(), 3)
        names = [p._viz_tabs_widget.tabText(i) for i in range(3)]
        self.assertEqual(names, ["HZ Diagram", "System Regions Diagram",
                                 "Alternate HZ Diagram"])

    def test_opts_9_10_still_build_region_diagrams(self):
        # The extracted add_region_diagram_tabs keeps opts 8/9/10 parity.
        from gui.panels.star_regions import add_region_diagram_tabs
        from PySide6.QtWidgets import QTabWidget
        d = regions.compute_sol_regions()
        tw = QTabWidget()
        add_region_diagram_tabs(tw, d)            # hypatia None → no Abundance tab
        self.assertEqual(tw.count(), 3)


# ─────────────────────────────────────────────────────────────────────────────
# O-6 — O7 Solar System Orbital Diagrams (opt 11): prepare_solar_system_orbits
#   (moon km→AU conversion anchor + orbit shape) + canvas smoke + panel tabs.
# ─────────────────────────────────────────────────────────────────────────────
class O7SolarSystemOrbitsPrepTest(unittest.TestCase):
    """core.viz.prepare_solar_system_orbits — body sets + km→AU moon conversion."""

    def test_planets(self):
        res = viz.prepare_solar_system_orbits("planets")
        self.assertNotIn("error", res)
        self.assertEqual(len(res["orbits"]), 8)
        self.assertEqual(res["star_name"], "Sun")
        self.assertEqual(res["hz_zones"], [])
        # Sorted by SMA → Mercury first; orbit-frame x_pts[0] == periastron.
        o0 = res["orbits"][0]
        self.assertEqual(o0["name"], "Mercury")
        self.assertAlmostEqual(o0["peri"], 0.387 * (1 - 0.205), places=3)
        self.assertAlmostEqual(o0["x_pts"][0], o0["peri"], places=6)

    def test_dwarfs_asteroids(self):
        res = viz.prepare_solar_system_orbits("dwarfs_asteroids")
        self.assertNotIn("error", res)
        self.assertGreater(len(res["orbits"]), 0)

    def test_moon_km_to_au_anchor(self):
        res = viz.prepare_solar_system_orbits("moons:Earth")
        self.assertNotIn("error", res)
        self.assertEqual(res["star_name"], "Earth")
        # Luna SMA 384399 km ÷ 1.496e8 = 0.002569 AU.
        self.assertAlmostEqual(res["orbits"][0]["sma"], 384399 / 1.496e8, places=6)

    def test_errors(self):
        self.assertIn("error", viz.prepare_solar_system_orbits("nope"))
        self.assertIn("error", viz.prepare_solar_system_orbits("moons:Zog"))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O7SolarSystemCanvasAndPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_canvas_smoke(self):
        from gui.visualizations.plot_helpers import make_orbits_canvas
        pl = viz.prepare_solar_system_orbits("planets")
        build_canvas_ok(self, make_orbits_canvas, None, pl["orbits"], pl["hz_zones"],
                        pl["max_au"], star_name="Sun", title="Solar System — Planets")
        mn = viz.prepare_solar_system_orbits("moons:Jupiter")
        build_canvas_ok(self, make_orbits_canvas, None, mn["orbits"], mn["hz_zones"],
                        mn["max_au"], star_name="Jupiter", km_axis=True)

    def test_orbits_canvas_additive_no_new_kwargs(self):
        # F3-style guard: default title/km_axis → still builds for existing callers.
        from gui.visualizations.plot_helpers import make_orbits_canvas
        pl = viz.prepare_solar_system_orbits("planets")
        build_canvas_ok(self, make_orbits_canvas, None, pl["orbits"], [], pl["max_au"])

    def test_panel_tabs(self):
        import gui.panels as panels

        class _StubWindow:
            pass
        p = panels.SolarSystemPanel(_StubWindow())
        self.assertEqual(p._tables_widget.count(), 4)        # data tabs unchanged
        self.assertEqual(p._viz_tabs_widget.count(), 2)
        self.assertEqual([p._viz_tabs_widget.tabText(i) for i in range(2)],
                         ["Orbital Diagram", "Moon Systems"])


# ─────────────────────────────────────────────────────────────────────────────
# O-6 — O10 Honorverse Visualization.
#   O10a (opt 14): prepare_hyper_limits + make_hyper_bar_canvas + panel tab.
#   O10b (opts 8/9): compute_hyper_limit_for_spectral_type ceiling rule;
#     prepare_system_regions_diagram adds `hyper_limit` only when spectral_type
#     resolves; the ring draws only with show_hyper=True; the wrapper's checkbox
#     appears only when a hyper_limit is present.
# ─────────────────────────────────────────────────────────────────────────────
import core.science as science


class O10aHyperLimitsPrepTest(unittest.TestCase):
    def test_prep(self):
        d = viz.prepare_hyper_limits()
        self.assertEqual(len(d["classes"]), 44)
        self.assertEqual(d["classes"][0], "O")
        self.assertAlmostEqual(d["lm"][0], 49.6, places=2)
        self.assertAlmostEqual(d["au"][0], 49.6 / 8.3167, places=4)
        self.assertEqual(d["colors"][0], "#9BB0FF")
        # Red Giant has no OBAFGKM leading letter → default grey.
        self.assertEqual(d["colors"][d["classes"].index("Red Giant")], "#AAAAAA")
        self.assertEqual(len(d["lm"]), len(d["au"]))


class O10bHyperLookupTest(unittest.TestCase):
    def test_ceiling_rule(self):
        f = science.compute_hyper_limit_for_spectral_type
        self.assertEqual(f("G2V")["matched_class"], "G2")    # exact (complete 0–9)
        self.assertEqual(f("K5V")["matched_class"], "K5")
        self.assertEqual(f("O5V")["matched_class"], "O")     # single-entry letter
        self.assertEqual(f("A0V")["matched_class"], "A")
        self.assertEqual(f("F3IV")["matched_class"], "F3")
        self.assertEqual(f("M9.5")["matched_class"], "M9")   # clamp past coolest
        self.assertAlmostEqual(f("G2V")["au"], 21.12 / 8.3167, places=4)

    def test_none_paths(self):
        f = science.compute_hyper_limit_for_spectral_type
        self.assertIsNone(f("DA1.9"))   # white dwarf — no OBAFGKM class
        self.assertIsNone(f(""))
        self.assertIsNone(f(None))
        self.assertIsNone(f("WR"))


class O10bRegionsPrepGatingTest(unittest.TestCase):
    def _regions_dict(self, spectral=None):
        import core.regions as reg
        d = reg.compute_star_system_regions(
            vmag=4.83, boloLum=-0.07, temp=5778, plx=130,
            sunlight_intensity=1.0, bond_albedo=0.3)
        if spectral is not None:
            d["spectral_type"] = spectral
        return d

    def test_hyper_limit_added_only_with_spectral_type(self):
        with_sp = viz.prepare_system_regions_diagram(self._regions_dict("G2V"))
        self.assertIn("hyper_limit", with_sp)
        self.assertAlmostEqual(with_sp["hyper_limit"]["au"], 21.12 / 8.3167, places=3)
        # No spectral type (opt 10 / opt 13 path) → no hyper_limit key.
        without = viz.prepare_system_regions_diagram(self._regions_dict(None))
        self.assertNotIn("hyper_limit", without)
        # Unresolvable type (white dwarf) → no hyper_limit either.
        wd = viz.prepare_system_regions_diagram(self._regions_dict("DA1.9"))
        self.assertNotIn("hyper_limit", wd)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O10CanvasAndPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _regions_data(self, spectral="G2V"):
        import core.regions as reg
        d = reg.compute_star_system_regions(
            vmag=4.83, boloLum=-0.07, temp=5778, plx=130,
            sunlight_intensity=1.0, bond_albedo=0.3)
        d["spectral_type"] = spectral
        return viz.prepare_system_regions_diagram(d)

    def test_hyper_bar_canvas(self):
        from gui.visualizations.plot_helpers import make_hyper_bar_canvas
        build_canvas_ok(self, make_hyper_bar_canvas, None, viz.prepare_hyper_limits())
        build_canvas_ok(self, make_hyper_bar_canvas, None, {"error": "empty"})

    def test_regions_ring_only_when_show_hyper(self):
        from gui.visualizations.plot_helpers import make_system_regions_canvas
        data = self._regions_data()
        c_off, _ = make_system_regions_canvas(None, data, show_hyper=False)
        c_on, _  = make_system_regions_canvas(None, data, show_hyper=True)

        def _legend_text(cv):
            leg = cv.figure.axes[0].get_legend()
            return " ".join(t.get_text() for t in leg.get_texts()) if leg else ""
        self.assertNotIn("Honorverse", _legend_text(c_off))   # additive: off → no ring
        self.assertIn("Honorverse", _legend_text(c_on))

    def test_wrapper_checkbox_presence(self):
        from PySide6.QtWidgets import QCheckBox
        from gui.visualizations.plot_helpers import wrap_system_regions_with_hyper_toggle
        w_hyper = wrap_system_regions_with_hyper_toggle(None, self._regions_data())
        self.assertEqual(len(w_hyper.findChildren(QCheckBox)), 1)
        # No hyper_limit → no checkbox (opt-10 manual path: no spectral type).
        import core.regions as reg
        d_manual = reg.compute_star_system_regions(
            vmag=4.83, boloLum=-0.07, temp=5778, plx=130,
            sunlight_intensity=1.0, bond_albedo=0.3)
        w_plain = wrap_system_regions_with_hyper_toggle(
            None, viz.prepare_system_regions_diagram(d_manual))
        self.assertEqual(len(w_plain.findChildren(QCheckBox)), 0)

    def test_opt14_panel_has_hyper_tab(self):
        import gui.panels as panels

        class _StubWindow:
            pass
        p = panels.HonorverseHyperPanel(_StubWindow())
        names = [p._viz_tabs_widget.tabText(i)
                 for i in range(p._viz_tabs_widget.count())]
        self.assertIn("Hyper Limits", names)

    def test_region_tabs_checkbox_gating(self):
        # add_region_diagram_tabs: System Regions tab gets a checkbox only when
        # the dict resolves a hyper limit (opts 8/9), not for opts 10/13.
        from PySide6.QtWidgets import QTabWidget, QCheckBox
        from gui.panels.star_regions import add_region_diagram_tabs
        import core.regions as reg

        def _sr_tab_checkboxes(d):
            tw = QTabWidget()
            add_region_diagram_tabs(tw, d)
            for i in range(tw.count()):
                if tw.tabText(i) == "System Regions Diagram":
                    return len(tw.widget(i).findChildren(QCheckBox))
            return None

        d_sp = reg.compute_star_system_regions(
            vmag=4.83, boloLum=-0.07, temp=5778, plx=130,
            sunlight_intensity=1.0, bond_albedo=0.3)
        d_sp["spectral_type"] = "G2V"
        self.assertEqual(_sr_tab_checkboxes(d_sp), 1)
        # Opt 13 (Sol) now carries G2V → checkbox present (Sun hyper limit).
        self.assertEqual(_sr_tab_checkboxes(reg.compute_sol_regions()), 1)
        # Opt 10 (manual, no spectral type) → no checkbox.
        d_manual = reg.compute_star_system_regions(
            vmag=4.83, boloLum=-0.07, temp=5778, plx=130,
            sunlight_intensity=1.0, bond_albedo=0.3)
        self.assertEqual(_sr_tab_checkboxes(d_manual), 0)


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O10cOrbitalHyperOverlayTest(unittest.TestCase):
    """O10b extension — hyper-limit ring on the Orbital Diagram (opts 3/6/Map)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _StubWindow:
        pass

    def _orbits(self):
        return viz.prepare_system_orbits([
            {"pl_name": "b", "pl_orbsmax": "1.0", "pl_orbeccen": "0.0",
             "st_teff": "5778", "st_rad": "1.0", "hostname": "Test"}])

    def test_canvas_ring_only_with_hyper_au(self):
        from gui.visualizations.plot_helpers import make_orbits_canvas
        od = self._orbits()

        def _legend_text(cv):
            leg = cv.figure.axes[0].get_legend()
            return " ".join(t.get_text() for t in leg.get_texts()) if leg else ""
        c_off, _ = make_orbits_canvas(None, od["orbits"], od["hz_zones"], od["max_au"])
        c_on, _  = make_orbits_canvas(None, od["orbits"], od["hz_zones"], od["max_au"],
                                      hyper_au=2.54)
        self.assertNotIn("Honorverse", _legend_text(c_off))   # additive: default off
        self.assertIn("Honorverse", _legend_text(c_on))

    def test_hyper_au_resolution(self):
        from gui.panels.nasa_exoplanet import _hyper_au_for
        self.assertAlmostEqual(_hyper_au_for("G2V"), 21.12 / 8.3167, places=3)
        self.assertIsNone(_hyper_au_for("DA1.9"))             # white dwarf
        self.assertIsNone(_hyper_au_for(None))

    def test_orbits_tab_checkbox_gating(self):
        from PySide6.QtWidgets import QCheckBox
        from gui.panels.nasa_exoplanet import _make_orbits_tab
        import gui.panels as panels
        p = panels.NasaPlanetarySystemsPanel(self._StubWindow())
        planets = [{"pl_name": "b", "pl_orbsmax": "1.0", "pl_orbeccen": "0.0",
                    "st_teff": "5778", "st_rad": "1.0", "hostname": "Test"}]
        # Resolvable type → solar + hyper checkboxes (2).
        w2 = _make_orbits_tab(p, planets, "Test", sp_type="G2V")
        self.assertEqual(len(w2.findChildren(QCheckBox)), 2)
        # No / unresolvable type → solar checkbox only (1).
        self.assertEqual(
            len(_make_orbits_tab(p, planets, "Test", sp_type=None).findChildren(QCheckBox)), 1)
        self.assertEqual(
            len(_make_orbits_tab(p, planets, "Test", sp_type="DA1.9").findChildren(QCheckBox)), 1)

    def test_hwc_panel_render_builds_viz_tabs(self):
        # Regression: a function-level `import core.science` in HwcPanel._render
        # once shadowed the module-level `core`, aborting the whole viz section
        # (no Show Diagrams). Drive _render end-to-end and assert viz tabs build.
        from PySide6.QtWidgets import QCheckBox
        import gui.panels as panels

        class _Nav:
            def show(self): pass
            def hide(self): pass

        class _Win:
            nav_tree = _Nav()
            def statusBar(self):
                class _S:
                    def showMessage(self, *a, **k): pass
                return _S()

        p = panels.HwcPanel(_Win())
        result = {
            "simbad": {"desig_str": "Tau Ceti"},
            "star_row": {"S_NAME": "Tau Ceti", "S_TYPE": "G8.5V",
                         "S_TEMPERATURE": "5344", "S_RADIUS": "0.79",
                         "S_LUMINOSITY": "0.52"},
            "planet_rows": [{"P_NAME": "Tau Ceti e", "P_SEMI_MAJOR_AXIS": "0.538",
                             "P_ECCENTRICITY": "0.18"}],
            "hypatia": None,
        }
        p._render(result)
        tabs = [p._viz_tabs_widget.tabText(i)
                for i in range(p._viz_tabs_widget.count())]
        self.assertIn("Orbital Diagram", tabs)      # render reached the viz section
        self.assertIn("HZ Diagram", tabs)
        for i in range(p._viz_tabs_widget.count()):
            if p._viz_tabs_widget.tabText(i) == "Orbital Diagram":
                # G8.5 resolves → solar + hyper checkboxes.
                self.assertEqual(
                    len(p._viz_tabs_widget.widget(i).findChildren(QCheckBox)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# O-7 — Hypatia Kinematics (O11 Toomre diagram + F2 Explain dialog)
# ─────────────────────────────────────────────────────────────────────────────
class O11ToomreTest(unittest.TestCase):
    """prepare_toomre — √(U²+W²) anchor, LSR correction, null/error paths (offline)."""

    @staticmethod
    def _hyp(u, v, w, disk="thin"):
        return {"star_name": "Tau Ceti",
                "properties": {"u_vel": u, "v_vel": v, "w_vel": w, "disk": disk},
                "abundances": []}

    def test_uw_and_lsr_anchor(self):
        su, sv, sw = viz._SOLAR_MOTION_UVW
        res = viz.prepare_toomre(self._hyp(30.0, -40.0, 10.0))
        self.assertNotIn("error", res)
        self.assertAlmostEqual(res["v"], -40.0 + sv, places=6)
        self.assertAlmostEqual(res["uw"], math.hypot(30.0 + su, 10.0 + sw), places=6)
        self.assertAlmostEqual(
            res["total"],
            math.sqrt((30.0 + su) ** 2 + (-40.0 + sv) ** 2 + (10.0 + sw) ** 2),
            places=6)
        self.assertEqual(res["disk"], "thin")
        self.assertEqual(res["star_name"], "Tau Ceti")

    def test_error_when_any_component_null(self):
        self.assertIn("error", viz.prepare_toomre(self._hyp(None, -40.0, 10.0)))
        self.assertIn("error", viz.prepare_toomre(self._hyp(30.0, None, 10.0)))
        self.assertIn("error", viz.prepare_toomre(self._hyp(30.0, -40.0, None)))

    def test_error_passthrough_and_empty(self):
        self.assertIn("error", viz.prepare_toomre({"error": "boom"}))
        self.assertIn("error", viz.prepare_toomre({}))
        self.assertIn("error", viz.prepare_toomre(
            {"star_name": "X", "properties": {}}))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O11CanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_toomre_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_toomre_canvas
        data = viz.prepare_toomre(O11ToomreTest._hyp(20.0, -25.0, 8.0))
        build_canvas_ok(self, make_toomre_canvas, None, data)

    def test_toomre_canvas_error_card(self):
        from gui.visualizations.plot_helpers import make_toomre_canvas
        build_canvas_ok(self, make_toomre_canvas, None, {"error": "no kinematics"})

    def test_make_kinematics_tab_builds_with_help_button(self):
        from PySide6.QtWidgets import QWidget, QPushButton
        from gui.visualizations.plot_helpers import make_kinematics_tab
        w = make_kinematics_tab(O11ToomreTest._hyp(20.0, -25.0, 8.0))
        self.assertIsInstance(w, QWidget)
        # The "ℹ What is this?" help button is present and opens the dialog.
        btns = w.findChildren(QPushButton)
        self.assertTrue(btns)
        from gui.help import _open_help_dialogs
        n0 = len(_open_help_dialogs)
        btns[0].click()
        self.assertGreaterEqual(len(_open_help_dialogs), n0 + 1)

    def test_make_kinematics_tab_none_without_uvw(self):
        from gui.visualizations.plot_helpers import make_kinematics_tab
        self.assertIsNone(make_kinematics_tab(O11ToomreTest._hyp(None, -25.0, 8.0)))
        self.assertIsNone(make_kinematics_tab({"error": "x"}))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O11PanelWiringSmokeTest(unittest.TestCase):
    """A host panel's _render adds a "Kinematics" tab when U/V/W are present."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _Nav:
        def show(self): pass
        def hide(self): pass

    class _Win:
        def __init__(self):
            self.nav_tree = O11PanelWiringSmokeTest._Nav()
        def statusBar(self):
            class _S:
                def showMessage(self, *a, **k): pass
            return _S()

    def _result(self, hypatia):
        return {
            "simbad": {"desig_str": "Tau Ceti"},
            "star_row": {"S_NAME": "Tau Ceti", "S_TYPE": "G8.5V",
                         "S_TEMPERATURE": "5344", "S_RADIUS": "0.79",
                         "S_LUMINOSITY": "0.52"},
            "planet_rows": [{"P_NAME": "Tau Ceti e", "P_SEMI_MAJOR_AXIS": "0.538",
                             "P_ECCENTRICITY": "0.18"}],
            "hypatia": hypatia,
        }

    def test_kinematics_tab_present_with_uvw(self):
        import gui.panels as panels
        p = panels.HwcPanel(self._Win())
        hyp = {"star_name": "Tau Ceti",
               "properties": {"u_vel": 10.0, "v_vel": -20.0, "w_vel": 5.0,
                              "disk": "thin"},
               "abundances": []}
        p._render(self._result(hyp))
        tabs = [p._viz_tabs_widget.tabText(i)
                for i in range(p._viz_tabs_widget.count())]
        self.assertIn("Kinematics", tabs)

    def test_no_kinematics_tab_without_uvw(self):
        import gui.panels as panels
        p = panels.HwcPanel(self._Win())
        hyp = {"star_name": "Tau Ceti",
               "properties": {"u_vel": None, "v_vel": -20.0, "w_vel": 5.0},
               "abundances": []}
        p._render(self._result(hyp))
        tabs = [p._viz_tabs_widget.tabText(i)
                for i in range(p._viz_tabs_widget.count())]
        self.assertNotIn("Kinematics", tabs)


# ─────────────────────────────────────────────────────────────────────────────
# O-8 — HWC Habitability Visuals (O12: Temperature Ranges + ESI vs Orbit, opt 6)
# ─────────────────────────────────────────────────────────────────────────────
class O12HwcTempsTest(unittest.TestCase):
    """prepare_hwc_temps — qualify rule, skip count, error path (offline)."""

    def test_eq_only_surf_only_both_and_skipped(self):
        rows = [
            {"P_NAME": "b", "P_TEMP_EQUIL_MIN": "240", "P_TEMP_EQUIL": "265",
             "P_TEMP_EQUIL_MAX": "290"},                                   # eq only
            {"P_NAME": "c", "P_TEMP_SURF_MIN": "195", "P_TEMP_SURF": "215",
             "P_TEMP_SURF_MAX": "240"},                                    # surf only
            {"P_NAME": "d", "P_TEMP_EQUIL_MIN": "330", "P_TEMP_EQUIL_MAX": "400",
             "P_TEMP_SURF_MIN": "360", "P_TEMP_SURF_MAX": "440"},          # both
            {"P_NAME": "e", "P_TEMP_EQUIL_MIN": "250"},                    # no pair → skip
        ]
        res = viz.prepare_hwc_temps(rows)
        self.assertNotIn("error", res)
        self.assertEqual(len(res["planets"]), 3)
        self.assertEqual(res["skipped"], 1)
        b = res["planets"][0]
        self.assertEqual((b["eq_min"], b["eq"], b["eq_max"]), (240.0, 265.0, 290.0))
        self.assertIsNone(b["surf_min"])
        c = res["planets"][1]
        self.assertIsNone(c["eq_min"])
        self.assertEqual((c["surf_min"], c["surf_max"]), (195.0, 240.0))

    def test_error_when_none_qualify(self):
        self.assertIn("error", viz.prepare_hwc_temps(
            [{"P_NAME": "x", "P_TEMP_EQUIL": "300"}]))
        self.assertIn("error", viz.prepare_hwc_temps([]))


class O12HwcEsiTest(unittest.TestCase):
    """prepare_hwc_esi — SMA/ESI filter, HZ bands from star row, log span (offline)."""

    def _star(self):
        return {"S_HZ_OPT_MIN": "0.75", "S_HZ_OPT_MAX": "1.77",
                "S_HZ_CON_MIN": "0.95", "S_HZ_CON_MAX": "1.67"}

    def test_filter_bands_and_habitable(self):
        rows = [
            {"P_NAME": "b", "P_SEMI_MAJOR_AXIS": "0.7", "P_ESI": "0.92", "P_HABITABLE": "1"},
            {"P_NAME": "c", "P_SEMI_MAJOR_AXIS": "1.4", "P_ESI": "0.64", "P_HABITABLE": "0"},
            {"P_NAME": "d", "P_SEMI_MAJOR_AXIS": "", "P_ESI": "0.5"},        # no SMA → skip
            {"P_NAME": "e", "P_SEMI_MAJOR_AXIS": "0.3", "P_ESI": ""},        # no ESI → skip
        ]
        res = viz.prepare_hwc_esi(self._star(), rows)
        self.assertNotIn("error", res)
        self.assertEqual(len(res["planets"]), 2)
        self.assertEqual(res["skipped"], 2)
        self.assertEqual(res["hz_opt"], [0.75, 1.77])
        self.assertEqual(res["hz_con"], [0.95, 1.67])
        self.assertTrue(res["planets"][0]["habitable"])
        self.assertFalse(res["planets"][1]["habitable"])
        self.assertFalse(res["log_x"])              # 1.4/0.7 = 2× < 10

    def test_log_x_when_span_exceeds_10x(self):
        rows = [
            {"P_NAME": "b", "P_SEMI_MAJOR_AXIS": "0.2", "P_ESI": "0.5"},
            {"P_NAME": "f", "P_SEMI_MAJOR_AXIS": "5.0", "P_ESI": "0.3"},   # 25× span
        ]
        res = viz.prepare_hwc_esi({}, rows)
        self.assertTrue(res["log_x"])
        self.assertIsNone(res["hz_opt"])            # empty star row → no bands

    def test_error_when_none_qualify(self):
        self.assertIn("error", viz.prepare_hwc_esi(
            self._star(), [{"P_NAME": "x", "P_ESI": "0.5"}]))
        self.assertIn("error", viz.prepare_hwc_esi(self._star(), []))


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O12CanvasSmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_temp_canvas_builds(self):
        from gui.visualizations.plot_helpers import make_hwc_temp_canvas
        data = viz.prepare_hwc_temps([
            {"P_NAME": "b", "P_TEMP_EQUIL_MIN": "240", "P_TEMP_EQUIL": "265",
             "P_TEMP_EQUIL_MAX": "290", "P_TEMP_SURF_MIN": "255",
             "P_TEMP_SURF": "280", "P_TEMP_SURF_MAX": "305"}])
        build_canvas_ok(self, make_hwc_temp_canvas, None, data)

    def test_esi_canvas_builds_and_error_card(self):
        from gui.visualizations.plot_helpers import make_hwc_esi_canvas
        data = viz.prepare_hwc_esi(
            {"S_HZ_OPT_MIN": "0.75", "S_HZ_OPT_MAX": "1.77"},
            [{"P_NAME": "b", "P_SEMI_MAJOR_AXIS": "0.7", "P_ESI": "0.92", "P_HABITABLE": "1"}])
        build_canvas_ok(self, make_hwc_esi_canvas, None, data)
        build_canvas_ok(self, make_hwc_esi_canvas, None, {"error": "x"})


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class O12PanelWiringSmokeTest(unittest.TestCase):
    """HwcPanel._render adds the two O12 tabs when planets qualify, omits them otherwise."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    class _Nav:
        def show(self): pass
        def hide(self): pass

    class _Win:
        def __init__(self):
            self.nav_tree = O12PanelWiringSmokeTest._Nav()
        def statusBar(self):
            class _S:
                def showMessage(self, *a, **k): pass
            return _S()

    def _render(self, planet_rows):
        import gui.panels as panels
        p = panels.HwcPanel(self._Win())
        p._render({
            "simbad": {"desig_str": "Tau Ceti"},
            "star_row": {"S_NAME": "Tau Ceti", "S_TYPE": "G8.5V",
                         "S_TEMPERATURE": "5344", "S_RADIUS": "0.79",
                         "S_LUMINOSITY": "0.52",
                         "S_HZ_OPT_MIN": "0.55", "S_HZ_OPT_MAX": "1.0",
                         "S_HZ_CON_MIN": "0.7", "S_HZ_CON_MAX": "0.9"},
            "planet_rows": planet_rows,
            "hypatia": None,
        })
        return [p._viz_tabs_widget.tabText(i)
                for i in range(p._viz_tabs_widget.count())]

    def test_tabs_present_with_qualifying_planets(self):
        tabs = self._render([
            {"P_NAME": "Tau Ceti e", "P_SEMI_MAJOR_AXIS": "0.538", "P_ESI": "0.78",
             "P_HABITABLE": "1", "P_TEMP_EQUIL_MIN": "230", "P_TEMP_EQUIL": "250",
             "P_TEMP_EQUIL_MAX": "270"}])
        self.assertIn("Temperature Ranges", tabs)
        self.assertIn("ESI vs Orbit", tabs)

    def test_tabs_absent_without_qualifying_data(self):
        tabs = self._render([
            {"P_NAME": "Tau Ceti e", "P_SEMI_MAJOR_AXIS": "0.538"}])  # no ESI, no temp range
        self.assertNotIn("Temperature Ranges", tabs)
        self.assertNotIn("ESI vs Orbit", tabs)


if __name__ == "__main__":
    unittest.main()
