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


if __name__ == "__main__":
    unittest.main()
