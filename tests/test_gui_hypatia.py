# tests/test_gui_hypatia.py — headless GUI smoke test for the grouped Hypatia tab
# and the category-coloured abundance chart. Skipped if PySide6/matplotlib are absent.
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTableView
    from PySide6.QtCore import Qt
    import matplotlib  # noqa: F401
    _GUI_OK = True
except Exception:
    _GUI_OK = False

from core.hypatia_elements import HYPATIA_SPECIES


def _synthetic_hypatia(n=60):
    """Build a hypatia-result dict with n measured species spanning many categories."""
    abundances = []
    for i, s in enumerate(HYPATIA_SPECIES[:n]):
        abundances.append({
            "element": s["symbol"], "name": s["name"], "z": s["z"],
            "category": s["category"], "mean": (i % 7 - 3) * 0.1,
            "std": 0.05, "min": -0.3, "max": 0.3, "n": 4,
        })
    return {"star_name": "Test Star", "properties":
            {"teff": 5500, "logg": 4.4, "spectral_type": "G5V"},
            "abundances": abundances}


@unittest.skipUnless(_GUI_OK, "PySide6 / matplotlib not available")
class TestGuiHypatia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.hypatia = _synthetic_hypatia(60)

    def test_grouped_table_has_all_rows(self):
        from gui.panels.hypatia_tab import build_hypatia_tab
        scroll = build_hypatia_tab(self.hypatia)
        tables = scroll.findChildren(QTableView)
        # Stellar Properties + Kinematics + one table per non-empty category.
        self.assertGreaterEqual(len(tables), 3)
        # Total abundance rows across the per-category tables == measured species.
        # Identify abundance tables by their first header ("Element").
        def _is_abundance(t):
            m = t.model()
            return (m is not None and
                    m.headerData(0, Qt.Orientation.Horizontal) == "Element")
        abundance_tables = [t for t in tables if _is_abundance(t)]
        # More than one category table (grouping actually happened).
        self.assertGreater(len(abundance_tables), 1)
        abundance_rows = sum(t.model().rowCount() for t in abundance_tables)
        self.assertEqual(abundance_rows, len(self.hypatia["abundances"]))

    def test_abundance_canvas_renders(self):
        from core.viz import prepare_abundance_profile
        from gui.visualizations.plot_helpers import make_abundance_canvas, wrap_scrollable
        ab = prepare_abundance_profile(self.hypatia)
        self.assertNotIn("error", ab)
        canvas, toolbar = make_abundance_canvas(None, ab, "Test Star")
        self.assertIsNotNone(canvas)
        widget = wrap_scrollable(None, canvas, toolbar)
        self.assertIsNotNone(widget)

    def test_wheel_over_the_canvas_scrolls_the_pane(self):
        """A wheel event on the canvas must scroll the enclosing QScrollArea.

        A matplotlib canvas accepts wheel events, so without the forwarder the
        pane only scrolls while the pointer is over the scrollbar itself.
        """
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt as _Qt
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtWidgets import QScrollArea
        from core.viz import prepare_abundance_profile
        from gui.visualizations.plot_helpers import make_abundance_canvas, wrap_scrollable

        ab = prepare_abundance_profile(self.hypatia)
        canvas, toolbar = make_abundance_canvas(None, ab, "Test Star")
        widget = wrap_scrollable(None, canvas, toolbar)
        widget.resize(600, 300)      # force the tall figure to overflow the viewport
        widget.show()
        self.app.processEvents()

        scroll = widget.findChild(QScrollArea)
        bar = scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), bar.minimum(),
                           "figure should overflow the viewport for this test")
        before = bar.value()
        ev = QWheelEvent(QPointF(50, 50), canvas.mapToGlobal(QPoint(50, 50)),
                         QPoint(0, -120), QPoint(0, -120),
                         _Qt.MouseButton.NoButton, _Qt.KeyboardModifier.NoModifier,
                         _Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(canvas, ev)
        self.assertGreater(bar.value(), before)
        widget.hide()


if __name__ == "__main__":
    unittest.main()
