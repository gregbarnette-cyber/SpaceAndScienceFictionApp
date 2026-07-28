# tests/test_honorverse_speed_panel.py — headless GUI tests for the Honorverse
# Effective Speed panel (opt 16, `HonorverseSpeedPanel`).
#
# Two defects this file pins, neither of which had any coverage:
#  1. Layout — both tables were plain QTableViews in the panel's QVBoxLayout,
#     which splits vertical space between them: the 9-row table got padded with
#     dead space while the 24-row table was squeezed into its own scrollbar.
#     They are now content-height-fitted inside one QScrollArea.
#  2. Columns — the expanded (Alpha–Omega) table was missing Translation
#     Bleed-Off and Velocity Multiplier between Band and Warship (xC).
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTableView, QScrollArea
    from PySide6.QtCore import Qt
    _GUI_OK = True
except Exception:
    _GUI_OK = False

import core.science

_HEADERS = ["Band", "Translation Bleed-Off", "Velocity Multiplier",
            "Warship (xC)", "Merchantship (xC)"]


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class HonorverseSpeedPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from gui.app import MainWindow
        from gui.panels.honorverse import HonorverseSpeedPanel
        cls.window = MainWindow()
        cls.window.resize(1400, 950)
        cls.window.show_panel(HonorverseSpeedPanel)
        cls.panel = cls.window._panels[HonorverseSpeedPanel]
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def _tables(self):
        """The panel's two live tables, in display order (table 1, then expanded)."""
        views = [v for v in self.panel.findChildren(QTableView) if v.model() is not None]
        # A reset() leaves the previous container pending deleteLater; keep the
        # last pair, which belongs to the current container.
        return views[-2:]

    def _cell(self, view, row, col):
        return view.model().item(row, col).text()

    # ── columns ──────────────────────────────────────────────────────────────

    def test_both_tables_carry_the_same_five_columns(self):
        for view in self._tables():
            model = view.model()
            headers = [model.headerData(c, Qt.Orientation.Horizontal)
                       for c in range(model.columnCount())]
            self.assertEqual(headers, _HEADERS)

    def test_expanded_table_has_all_24_bands_with_bleed_off_and_multiplier(self):
        t1, t2 = self._tables()
        self.assertEqual(t1.model().rowCount(), 9)    # Alpha–Iota
        self.assertEqual(t2.model().rowCount(), 24)   # Alpha–Omega
        # Canon rows read identically in both tables (bar Iota's speeds, which
        # Table 1 shows as "Currently Unattainable").
        for r in range(9):
            self.assertEqual(self._cell(t1, r, 0), self._cell(t2, r, 0))  # Band
            self.assertEqual(self._cell(t1, r, 1), self._cell(t2, r, 1))  # Bleed-Off
            self.assertEqual(self._cell(t1, r, 2), self._cell(t2, r, 2))  # Multiplier
        self.assertEqual(self._cell(t2, 0, 1), "92%")      # Alpha, canon
        self.assertEqual(self._cell(t2, 0, 2), "62")
        self.assertEqual(self._cell(t2, 23, 0), "Omega")
        self.assertEqual(self._cell(t2, 23, 2), "16582")

    def test_extrapolated_bleed_off_is_marked_and_canon_is_not(self):
        _, t2 = self._tables()
        for r in range(9):                            # Alpha–Iota: published
            self.assertNotIn("†", self._cell(t2, r, 1))
        for r in range(9, 24):                        # Kappa–Omega: derived
            self.assertIn("†", self._cell(t2, r, 1))
        self.assertEqual(self._cell(t2, 9, 1), "44% †")   # Kappa
        self.assertEqual(self._cell(t2, 23, 1), "14% †")  # Omega

    def test_cells_match_the_core_data(self):
        """The panel renders compute_honorverse_effective_speed, not its own copy."""
        _, t2 = self._tables()
        for r, b in enumerate(core.science.compute_honorverse_effective_speed()
                              ["expanded_bands"]):
            self.assertEqual(self._cell(t2, r, 0), b["band"])
            self.assertEqual(self._cell(t2, r, 2), str(b["multiplier"]))
            self.assertIn(str(b["warship_xc"]), self._cell(t2, r, 3))
            self.assertIn(str(b["merchant_xc"]), self._cell(t2, r, 4))

    # ── layout ───────────────────────────────────────────────────────────────

    def test_tables_are_fitted_to_content_and_stacked_in_one_scroll_area(self):
        """No dead space under table 1, no private scrollbar on table 2."""
        self.assertTrue(self.panel.findChildren(QScrollArea),
                        "results area should scroll as a whole")
        for view in self._tables():
            model = view.model()
            expected = (view.horizontalHeader().height()
                        + view.verticalHeader().length()
                        + view.frameWidth() * 2)
            self.assertAlmostEqual(view.height(), expected, delta=4,
                                   msg="table height should equal header + rows")
            self.assertFalse(view.verticalScrollBar().isVisible(),
                             "a content-fitted table needs no scrollbar")
            # Guard the regression directly: heights must track row counts.
            self.assertGreater(view.height(), model.rowCount() * 10)

    def test_expanded_table_is_taller_than_table_one(self):
        t1, t2 = self._tables()
        self.assertGreater(t2.height(), t1.height(),
                           "24 rows must not be squeezed into 9 rows' space")


if __name__ == "__main__":
    unittest.main()
