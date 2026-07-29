# tests/test_designation_display_gui.py — Phase AN3 display surface.
#
# The rendered Bayer/Flamsteed names are a GUI line beneath the designations
# banner, wired into the same four panels as Phase AO's Gould line and following
# the same contract: renders when present, completely silent when not (the normal
# case — SIMBAD emits these ids for bright stars only), never stored.
#
# The renderer itself is tested in test_designation_display.py. This file pins the
# wiring, which the AO precedent shows is the half that gets missed: a helper that
# no panel calls is invisible to every other test in the suite.
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


# Procyon as AN2 actually leaves it: the Bayer id equals MAIN_ID, so D3's dedupe
# removed it from desig_str — but the KEY survives, which is why the rendered
# line can still show both names (PHASE_AN_PLAN.md §5).
_PROCYON = {
    "desig_str": "* alf CMi, NAME Procyon, *  10 CMi, GJ 280 A, HD  61421",
    "designations": {
        "MAIN_ID": "* alf CMi", "NAME": "NAME Procyon",
        "Bayer": "* alf CMi", "Flamsteed": "*  10 CMi",
        "HD": "HD  61421", "GJ": "GJ 280 A",
    },
}


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class AddDesignationNamesLineTest(unittest.TestCase):

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

    def test_renders_both_names_when_present(self):
        from gui.panels.base import add_designation_names_line
        layout = self._layout()
        label = add_designation_names_line(layout, _PROCYON)
        self.assertIsNotNone(label)
        self.assertEqual(layout.count(), 1)
        self.assertIn("α Canis Minoris", label.text())
        self.assertIn("10 Canis Minoris", label.text())

    def test_flamsteed_alone_renders(self):
        # The realistic shape for a star with no Bayer designation at all.
        from gui.panels.base import add_designation_names_line
        label = add_designation_names_line(
            self._layout(), {"designations": {"Flamsteed": "*  18 Eri"}}
        )
        self.assertIn("18 Eridani", label.text())
        self.assertNotIn("Bayer", label.text())

    def test_the_superscript_form_reaches_the_label(self):
        # α Cen A is the star this phase visibly changes most: its Bayer id is the
        # only one in the corpus that survives D3's dedupe (§4b).
        from gui.panels.base import add_designation_names_line
        label = add_designation_names_line(
            self._layout(), {"designations": {"Bayer": "* alf01 Cen"}}
        )
        self.assertIn("α¹ Centauri", label.text())

    def test_adds_nothing_when_absent(self):
        # The normal case, and the reason panels can call it unconditionally.
        from gui.panels.base import add_designation_names_line
        for simbad in ({}, None, {"designations": None}, {"designations": {}},
                       {"designations": {"HD": "HD 61421"}},
                       {"designations": {"Bayer": None, "Flamsteed": None}}):
            with self.subTest(simbad=simbad):
                layout = self._layout()
                self.assertIsNone(add_designation_names_line(layout, simbad))
                self.assertEqual(layout.count(), 0)

    def test_a_double_system_id_produces_no_line(self):
        # Defence in depth: the classifier should never route a `** ` id into a
        # Bayer key, but if one ever arrives the label must not name the wrong
        # object.
        from gui.panels.base import add_designation_names_line
        layout = self._layout()
        self.assertIsNone(add_designation_names_line(
            layout, {"designations": {"Bayer": "** LDS 6248A"}}
        ))
        self.assertEqual(layout.count(), 0)


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class PanelWiringTest(unittest.TestCase):
    """Every panel that renders a designations banner must call the helper."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_four_banner_panels_call_it(self):
        import inspect
        from gui.panels import simbad, star_regions, nasa_exoplanet, catalogs
        for module in (simbad, star_regions, nasa_exoplanet, catalogs):
            with self.subTest(module=module.__name__):
                self.assertIn("add_designation_names_line(", inspect.getsource(module))

    def test_nasa_banner_helper_emits_the_line_under_the_banner(self):
        from gui.panels.nasa_exoplanet import _add_simbad_banner
        self._w = QWidget()
        layout = QVBoxLayout(self._w)
        _add_simbad_banner(layout, _PROCYON)
        texts = [layout.itemAt(i).widget().text() for i in range(layout.count())
                 if isinstance(layout.itemAt(i).widget(), QLabel)]
        self.assertEqual(len(texts), 2)
        # Order matters: the raw ids are the identifiers, the rendered names read
        # as their expansion. Reversing it would look like two competing banners.
        self.assertIn("*  10 CMi", texts[0])
        self.assertIn("10 Canis Minoris", texts[1])

    def test_nasa_banner_helper_silent_without_the_keys(self):
        from gui.panels.nasa_exoplanet import _add_simbad_banner
        self._w = QWidget()
        layout = QVBoxLayout(self._w)
        _add_simbad_banner(layout, {"desig_str": "HD 999999", "designations": {}})
        self.assertEqual(layout.count(), 1)


if __name__ == "__main__":
    unittest.main()
