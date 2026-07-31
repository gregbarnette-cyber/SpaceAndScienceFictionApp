# tests/test_gould_display.py — Phase AO3 display surfaces.
#
# The Gould designation is a SEPARATE top-level key (AO3a), so unlike the "gcns"
# block it does not reach any banner for free — each surface needed an explicit
# edit. These tests pin that the shared helper renders when a Gould designation
# is present, stays completely silent when it is not (the normal case for most
# stars — AO4a), and never leaks into `designations` / `desig_str`.
#
# Offscreen Qt; no network, no DB.
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
    _GUI_OK = True
except Exception:
    _GUI_OK = False

import core.report as report


_GOULD = {
    "g_number": 66, "cst": "Cen", "constellation": "Centauri",
    "designation": "66 G. Cen", "display": "66 G. Centauri",
    "hd": 102365, "sao": 223020, "matched_on": "hd",
    "source": "VizieR V/135A (Gould 1879)",
}


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class AddGouldLineTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Hold the parent widget alive — a bare QVBoxLayout(QWidget()) has its
        # parent collected immediately and the layout dies with it.
        self._widgets = []

    def _layout(self):
        w = QWidget()
        self._widgets.append(w)
        return QVBoxLayout(w)

    def test_renders_display_form_when_present(self):
        from gui.panels.base import add_gould_line
        layout = self._layout()
        label = add_gould_line(layout, {"gould": _GOULD})
        self.assertIsNotNone(label)
        self.assertEqual(layout.count(), 1)
        self.assertIn("66 G. Centauri", label.text())
        self.assertIn("Gould", label.text())

    def test_tooltip_carries_provenance_and_the_1875_caveat(self):
        from gui.panels.base import add_gould_line
        label = add_gould_line(self._layout(), {"gould": _GOULD})
        tip = label.toolTip()
        self.assertIn("Gould 1879", tip)
        self.assertIn("1875", tip)          # AO4b — must not be "reconciled" away

    def test_inline_with_appends_to_the_bayer_flamsteed_line(self):
        # The Gould designation shares one line with the AN3 Bayer/Flamsteed
        # names rather than sitting on a line of its own.
        from gui.panels.base import add_designation_names_line, add_gould_line
        layout = self._layout()
        names = add_designation_names_line(
            layout, {"designations": {"Flamsteed": "*  18 Eri"}})
        label = add_gould_line(layout, {"gould": _GOULD}, inline_with=names)
        self.assertIs(label, names)
        self.assertEqual(layout.count(), 1)          # no second widget
        self.assertIn("18 Eridani", label.text())
        self.assertIn("66 G. Centauri", label.text())
        self.assertIn("·", label.text())
        self.assertIn("1875", label.toolTip())       # both tooltips survive
        self.assertIn("genitive", label.toolTip())

    def test_inline_with_none_still_gets_its_own_line(self):
        # A star with no Bayer/Flamsteed id — add_designation_names_line
        # returned None, so Gould falls back to a standalone label.
        from gui.panels.base import add_gould_line
        layout = self._layout()
        label = add_gould_line(layout, {"gould": _GOULD}, inline_with=None)
        self.assertIsNotNone(label)
        self.assertEqual(layout.count(), 1)
        self.assertIn("66 G. Centauri", label.text())

    def test_adds_nothing_when_absent(self):
        # The normal case: Gould listed bright southern stars only.
        from gui.panels.base import add_gould_line
        for simbad in ({}, {"gould": None}, None, {"gould": {}},
                       {"gould": {"display": None}}):
            with self.subTest(simbad=simbad):
                layout = self._layout()
                self.assertIsNone(add_gould_line(layout, simbad))
                self.assertEqual(layout.count(), 0)


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class PanelWiringTest(unittest.TestCase):
    """Every panel that renders a designations banner must call the helper."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_four_banner_panels_call_add_gould_line(self):
        import inspect
        from gui.panels import simbad, star_regions, nasa_exoplanet, catalogs
        for module in (simbad, star_regions, nasa_exoplanet, catalogs):
            with self.subTest(module=module.__name__):
                src = inspect.getsource(module)
                self.assertIn("add_gould_line(", src)

    def test_nasa_banner_helper_emits_the_gould_line(self):
        from gui.panels.nasa_exoplanet import _add_simbad_banner
        self._w = QWidget()
        layout = QVBoxLayout(self._w)
        _add_simbad_banner(layout, {"desig_str": "HD 102365", "gould": _GOULD})
        texts = [layout.itemAt(i).widget().text() for i in range(layout.count())
                 if isinstance(layout.itemAt(i).widget(), QLabel)]
        self.assertEqual(len(texts), 2)
        self.assertIn("HD 102365", texts[0])
        self.assertIn("66 G. Centauri", texts[1])

    def test_nasa_banner_helper_silent_without_gould(self):
        from gui.panels.nasa_exoplanet import _add_simbad_banner
        self._w = QWidget()
        layout = QVBoxLayout(self._w)
        _add_simbad_banner(layout, {"desig_str": "HD 999999"})
        self.assertEqual(layout.count(), 1)


class ReportIdentityTest(unittest.TestCase):
    """AO3 [R6] / D3 — the Phase Q dossier carries it (maintainer decision)."""

    def _simbad(self, gould=None):
        s = {"main_id": "HD 102365", "sp_type": "G2V",
             "designations": {"HD": "HD 102365", "NAME": "NAME Foo"}}
        if gould is not None:
            s["gould"] = gould
        return s

    def test_identity_data_carries_the_display_form(self):
        d = report._identity_data_star(self._simbad(_GOULD))
        self.assertEqual(d["gould"], "66 G. Centauri")

    def test_identity_data_key_present_but_none_without_gould(self):
        # Key is always present so the export contract is stable.
        for simbad in (self._simbad(), self._simbad(None)):
            with self.subTest(simbad=simbad):
                self.assertIsNone(report._identity_data_star(simbad)["gould"])

    def test_gould_is_not_appended_to_the_designations_list(self):
        d = report._identity_data_star(self._simbad(_GOULD))
        self.assertEqual(d["designations"], ["HD 102365"])

    def test_rendered_row_appears_only_when_present(self):
        with_g = dict(report._identity_data_star(self._simbad(_GOULD)))
        without = dict(report._identity_data_star(self._simbad()))

        def labels(d):
            _, blocks = report._blocks_identity(d)
            return [row[0] for row in blocks[0][1]]

        self.assertIn("Gould designation", labels(with_g))
        self.assertNotIn("Gould designation", labels(without))

    def test_rendered_row_sits_after_designations(self):
        _, blocks = report._blocks_identity(
            report._identity_data_star(self._simbad(_GOULD)))
        labels = [row[0] for row in blocks[0][1]]
        self.assertEqual(labels.index("Gould designation"),
                         labels.index("Designations") + 1)

    def test_sol_identity_has_the_key(self):
        self.assertIsNone(report._identity_data_sol()["gould"])


if __name__ == "__main__":
    unittest.main()
