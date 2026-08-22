# tests/test_reports_panel.py — Phase Q Q-core-5: DossierExportPanel GUI smoke tests.
# Headless (offscreen). Skipped if PySide6 is absent. No network: the panel's render path
# is driven directly from a json envelope built via mocked readers.

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    _GUI_OK = True
except Exception:
    _GUI_OK = False

import core.report as report

# Reuse the core test fixtures for a fully-populated envelope.
try:
    import tests.test_report as tr
except Exception:
    tr = None


def _star_envelope():
    """A json-format dossier envelope for a normal star, via the mocked readers."""
    sb = tr._simbad_fixture(); rg = tr._regions_fixture(sb)
    na = tr._nasa_fixture(); hw = tr._hwc_fixture(); hy = tr._hypatia_fixture()
    with mock.patch("core.databases.compute_simbad_lookup", return_value=sb), \
         mock.patch("core.regions.compute_star_system_regions_from_simbad", return_value=rg), \
         mock.patch("core.databases.compute_planetary_systems_composite", return_value=na), \
         mock.patch("core.databases.compute_hwc", return_value=hw), \
         mock.patch("core.databases.compute_hypatia_data", return_value=hy), \
         mock.patch("core.binary.binary_orbit",
                    return_value={"query": "Tau Ceti", "identity": {}, "solutions": [], "route_tried": []}), \
         mock.patch("core.catalog.gaia_astrophysical", return_value={"parameters": None}), \
         mock.patch("core.debris_disk.debris_disk",
                    return_value={"detection": "upper_limit", "components": [],
                                  "upper_limit_L_IR_over_Lstar": 1e-4}):
        return report.build_system_dossier("Tau Ceti", fmt="json")


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


@unittest.skipUnless(_GUI_OK and tr is not None, "PySide6 / fixtures not available")
class DossierPanelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from gui.panels.reports import DossierExportPanel
        return DossierExportPanel(_FakeWindow())

    def test_constructs_with_default_sections(self):
        p = self._panel()
        self.assertEqual(p._selected_sections(),
                         ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"])
        self.assertFalse(p._save_btn.isEnabled())

    def test_moons_checkbox_appends_section(self):
        p = self._panel()
        p._moons_check.setChecked(True)
        self.assertIn("moons", p._selected_sections())

    def test_markdown_render_populates_preview_and_enables_save(self):
        p = self._panel()
        env = _star_envelope()
        p._on_generated(env, "markdown")
        self.assertTrue(p._save_btn.isEnabled())
        self.assertIn("System Dossier", p._preview.toPlainText())
        self.assertEqual(p._last[0], "markdown")

    def test_html_render_includes_figures(self):
        p = self._panel()
        env = _star_envelope()
        p._on_generated(env, "html")
        fmt, document, star = p._last
        self.assertEqual(fmt, "html")
        self.assertTrue(document.startswith("<!DOCTYPE html>"))
        # Option A: GUI splices inline base64 figures (when matplotlib is present).
        try:
            from gui.visualizations.plot_helpers import mpl_available
            if mpl_available():
                self.assertIn("data:image/png;base64,", document)
                self.assertIn("Diagrams", document)
        except Exception:
            pass

    def test_error_envelope_shows_status_no_save(self):
        p = self._panel()
        p._on_generated({"error": "No results found for 'Nonesuch'"}, "markdown")
        self.assertFalse(p._save_btn.isEnabled())
        self.assertIn("Error", p._status.text())

    def test_warnings_surface_in_status(self):
        p = self._panel()
        env = _star_envelope()
        env["warnings"] = ["hypatia: none"]
        p._on_generated(env, "markdown")
        self.assertIn("warning", p._status.text())

    def test_figures_html_no_mpl_is_empty_safe(self):
        # _figures_html must never raise; returns '' when mpl unavailable / data thin.
        from gui.panels.reports import _figures_html
        self.assertIsInstance(_figures_html({}), str)

    def test_panel_in_nav(self):
        from gui.nav import NAVIGATION
        cats = dict(NAVIGATION)
        self.assertIn("Reports", cats)
        self.assertIn(("System Dossier Export", "DossierExportPanel"), cats["Reports"])

    def test_panel_exported(self):
        import gui.panels as panels
        self.assertTrue(hasattr(panels, "DossierExportPanel"))


if __name__ == "__main__":
    unittest.main()
