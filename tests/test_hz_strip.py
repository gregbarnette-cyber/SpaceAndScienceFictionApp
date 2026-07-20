# tests/test_hz_strip.py — Phase 5 (HZ Rings/Strip toggle).
#
# Covers the new strip data prep (core.viz.prepare_hz_strip — pure, offline) and the
# Qt/matplotlib pieces (make_hz_strip_canvas + the shared wrap_hz_with_toggle /
# _hz_toggle_tab wrapper), gated on PySide6/matplotlib like the OEC canvas tests.
# The Rings path (make_hz_canvas) is unchanged and asserted to still build.

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import core.viz as viz


class PrepareHzStripTests(unittest.TestCase):
    """prepare_hz_strip reuses the Kopparapu zones and adds bands + placed planets."""

    def test_sol_band_edges(self):
        r = viz.prepare_hz_strip(5778, 1.0)
        self.assertNotIn("error", r)
        b = r["bands"]
        # canonical Kopparapu (Sun): recent Venus ~0.75, runaway GH ~0.95,
        # max GH ~1.68, early Mars ~1.77
        self.assertAlmostEqual(b["opt_inner"], 0.75, delta=0.03)
        self.assertAlmostEqual(b["opt_outer"], 1.77, delta=0.03)
        self.assertAlmostEqual(b["con_inner"], 0.95, delta=0.03)
        self.assertAlmostEqual(b["con_outer"], 1.68, delta=0.03)
        self.assertTrue(b["opt_inner"] < b["con_inner"] < b["con_outer"] < b["opt_outer"])

    def test_planet_in_hz_flags(self):
        r = viz.prepare_hz_strip(5778, 1.0, [
            {"name": "Mercury", "au": 0.387}, {"name": "Venus", "au": 0.723},
            {"name": "Earth", "au": 1.0}, {"name": "Mars", "au": 1.524}])
        flags = {p["name"]: p["in_hz"] for p in r["planets"]}
        self.assertEqual(flags, {"Mercury": False, "Venus": False,
                                 "Earth": True, "Mars": True})

    def test_no_planets_is_bands_only(self):
        r = viz.prepare_hz_strip(5810, 1.05, [])
        self.assertEqual(r["planets"], [])
        self.assertGreater(r["max_au"], r["bands"]["opt_outer"])

    def test_bad_or_missing_planet_au_dropped(self):
        r = viz.prepare_hz_strip(5778, 1.0, [
            {"name": "good", "au": 1.0}, {"name": "nosma", "au": None},
            {"name": "zero", "au": 0.0}, {"name": "neg", "au": -3}])
        self.assertEqual([p["name"] for p in r["planets"]], ["good"])

    def test_max_au_expands_for_outer_planet(self):
        r = viz.prepare_hz_strip(5778, 1.0, [{"name": "far", "au": 30.0}])
        self.assertGreaterEqual(r["max_au"], 30.0)

    def test_error_passthrough(self):
        self.assertIn("error", viz.prepare_hz_strip(0, 1.0))
        self.assertIn("error", viz.prepare_hz_strip(5778, -1))


def _mpl_ok():
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


@unittest.skipUnless(_mpl_ok(), "matplotlib/PySide6 not available")
class HzStripCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_rings_canvas_still_builds(self):
        # Rings is unchanged — guard against the Phase-5 edit breaking make_hz_canvas.
        from gui.visualizations.plot_helpers import make_hz_canvas
        hz = viz.prepare_hz_diagram(5778, 1.0)
        canvas, toolbar = make_hz_canvas(None, hz["zones"], hz["max_au"], title="HZ")
        self.assertIsNotNone(canvas)
        self.assertIsNotNone(toolbar)

    def test_strip_canvas_with_planets(self):
        from gui.visualizations.plot_helpers import make_hz_strip_canvas
        strip = viz.prepare_hz_strip(5778, 1.0, [
            {"name": "Earth", "au": 1.0}, {"name": "Mars", "au": 1.524}])
        canvas, toolbar = make_hz_strip_canvas(None, strip, title="HZ strip", eeid_au=1.0)
        self.assertIsNotNone(canvas)
        self.assertIsNotNone(toolbar)
        ax = canvas.figure.axes[0]
        # one scatter (the planets) + the two axvspan band patches present
        self.assertTrue(any(hasattr(a, "get_offsets") for a in ax.collections))

    def test_strip_canvas_bands_only(self):
        from gui.visualizations.plot_helpers import make_hz_strip_canvas
        strip = viz.prepare_hz_strip(5810, 1.05, [])
        canvas, toolbar = make_hz_strip_canvas(None, strip)
        self.assertIsNotNone(canvas)

    def test_strip_canvas_none_without_bands(self):
        from gui.visualizations.plot_helpers import make_hz_strip_canvas
        canvas, toolbar = make_hz_strip_canvas(None, {"bands": {}})
        self.assertIsNone(canvas)
        self.assertIsNone(toolbar)


@unittest.skipUnless(_mpl_ok(), "matplotlib/PySide6 not available")
class HzToggleWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_toggle_tab_has_two_views_rings_default(self):
        from gui.panels.diagram_tabs import _hz_toggle_tab
        from PySide6.QtWidgets import QStackedWidget, QPushButton
        w = _hz_toggle_tab(None, 5778, 1.0, title="HZ",
                           planets=[{"name": "Earth", "au": 1.0}])
        self.assertIsNotNone(w)
        stack = w.findChild(QStackedWidget)
        self.assertIsNotNone(stack)
        self.assertEqual(stack.count(), 2)
        self.assertEqual(stack.currentIndex(), 0)   # Rings is the default
        # clicking Strip switches the stack
        strip_btn = next(b for b in w.findChildren(QPushButton) if b.text() == "Strip")
        strip_btn.click()
        self.assertEqual(stack.currentIndex(), 1)

    def test_toggle_tab_bands_only_still_has_toggle(self):
        # A single-star panel (no planets) still gets the Rings/Strip control.
        from gui.panels.diagram_tabs import _hz_toggle_tab
        from PySide6.QtWidgets import QStackedWidget
        w = _hz_toggle_tab(None, 5810, 1.05, title="HZ", planets=[])
        self.assertIsNotNone(w.findChild(QStackedWidget))

    def test_wrap_falls_back_to_rings_when_strip_none(self):
        # If the strip factory returns None, the wrapper returns the bare rings widget
        # (no toggle) rather than failing.
        from gui.panels.diagram_tabs import wrap_hz_with_toggle
        from PySide6.QtWidgets import QLabel, QStackedWidget
        sentinel = QLabel("rings")
        out = wrap_hz_with_toggle(lambda: sentinel, lambda: None)
        self.assertIs(out, sentinel)
        self.assertIsNone(out.findChild(QStackedWidget))

    def test_wrap_none_when_rings_none(self):
        from gui.panels.diagram_tabs import wrap_hz_with_toggle
        self.assertIsNone(wrap_hz_with_toggle(lambda: None, lambda: None))


if __name__ == "__main__":
    unittest.main()
