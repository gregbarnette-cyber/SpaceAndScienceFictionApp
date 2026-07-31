# tests/test_hwc_panel_formatting.py — headless GUI tests for the Habitable
# Worlds Catalog panel's Star Habitability Properties table (opt 6, `HwcPanel`).
#
# The defect this file pins: `HwcPanel._render`'s `_sf(key, dp=None)` helper
# falls back to `str(int(f))` when no decimal count is given. That fallback
# exists for `S_TEMPERATURE` (documented as an integer, and truncated the same
# way by the CLI), but the three AU-valued habitability columns were riding on
# it too — so Tau Ceti's tidal-lock distance 0.49908380 rendered as "0", its
# snow line 1.9004820 as "1", and GJ 581's abiogenesis zone 0.022930729 as "0".
#
# `docs/star-databases.md` specifies these three at 6dp, and the CLI
# (`main.py::_display_hwc_star_habitability`) already printed them at 6dp, so
# the GUI was the sole divergence. The panel's diagram markers were never
# affected — they read the raw strings through `_fval()`.
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTableView
    from PySide6.QtCore import Qt
    _GUI_OK = True
except Exception:
    _GUI_OK = False

# Real hwc.csv values, inlined so the test does not drift with a catalogue
# refresh. Tau Ceti is the star the truncation was reported against; GJ 581's
# abiogenesis zone is the case that truncated to "0" from a value two orders of
# magnitude below 1.
_TAU_CETI = {
    "S_NAME": "tau Cet", "S_NAME_HD": "10700", "S_NAME_HIP": "8102",
    "S_TYPE": "G8.5V", "S_MAG": "3.50", "S_LUMINOSITY": "0.52",
    "S_TEMPERATURE": "5344.0000", "S_MASS": "0.78", "S_RADIUS": "0.79",
    "S_RA": "26.017", "S_DEC": "-15.9375", "S_DISTANCE": "3.65",
    "S_METALLICITY": "-0.55", "S_AGE": "5.80",
    "S_HZ_OPT_MIN": "0.54266377", "S_HZ_OPT_MAX": "1.2969635",
    "S_HZ_CON_MIN": "0.68785757", "S_HZ_CON_MAX": "1.2153813",
    "S_HZ_CON1_MIN": "0.65867352", "S_HZ_CON1_MAX": "1.2153813",
    "S_SNOW_LINE": "1.9004820", "S_ABIO_ZONE": "0.83572862",
    "S_TIDAL_LOCK": "0.49908380",
}
_GJ_581 = dict(_TAU_CETI, **{
    "S_NAME": "GJ 581", "S_TYPE": "M3V", "S_TEMPERATURE": "3498.0000",
    "S_HZ_OPT_MIN": "0.093483539", "S_HZ_OPT_MAX": "0.24383309",
    "S_SNOW_LINE": "0.30822209", "S_ABIO_ZONE": "0.022930729",
    "S_TIDAL_LOCK": "0.30873804",
})

_PLANET = {
    "P_NAME": "tau Cet e", "P_MASS": "3.93", "P_RADIUS": "1.81",
    "P_PERIOD": "162.87", "P_SEMI_MAJOR_AXIS": "0.538", "P_ECCENTRICITY": "0.18",
    "P_DENSITY": "0.66", "P_POTENTIAL": "2.17", "P_GRAVITY": "1.20",
    "P_ESCAPE": "1.47", "P_TYPE": "Warm Superterran", "P_DISTANCE_EFF": "0.55",
    "P_PERIASTRON": "0.44", "P_APASTRON": "0.63", "P_TYPE_TEMP": "Warm",
    "P_HILL_SPHERE": "0.00354", "P_HABITABLE": "1", "P_ESI": "0.78",
    "P_HABZONE_CON": "0", "P_HABZONE_OPT": "1",
    "P_FLUX_MIN": "1.30", "P_FLUX": "1.79", "P_FLUX_MAX": "2.66",
    "P_TEMP_EQUIL_MIN": "260.0", "P_TEMP_EQUIL": "286.0",
    "P_TEMP_EQUIL_MAX": "316.0", "P_TEMP_SURF_MIN": "280.0",
    "P_TEMP_SURF": "300.0", "P_TEMP_SURF_MAX": "330.0",
}

_HAB_HEADERS = ["Inner Opt HZ", "Inner Con HZ", "Outer Con HZ", "Outer Opt HZ",
                "Inner Con 5 Me HZ", "Outer Con 5 Me HZ",
                "Tidal Lock", "Abiogenesis", "Snow Line"]


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class HwcStarHabitabilityFormattingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from gui.app import MainWindow
        from gui.panels.catalogs import HwcPanel
        cls.window = MainWindow()
        cls.window.show_panel(HwcPanel)
        cls.panel = cls.window._panels[HwcPanel]

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def _render(self, star_row):
        self.panel._render({
            "simbad": {"desig_str": star_row["S_NAME"], "designations": {}},
            "star_row": star_row,
            "planet_rows": [_PLANET],
            "hypatia": None,
        })
        self.app.processEvents()

    def _find_table(self, headers_wanted):
        """The live table whose headers match, newest first.

        A re-render leaves the previous container pending deleteLater, so
        findChildren still returns the stale table alongside the current one —
        the same wrinkle tests/test_honorverse_speed_panel.py documents. The
        last match belongs to the current render.
        """
        found = []
        for view in self.panel.findChildren(QTableView):
            model = view.model()
            if model is None:
                continue
            headers = [model.headerData(c, Qt.Orientation.Horizontal)
                       for c in range(model.columnCount())]
            if headers_wanted(headers):
                found.append(model)
        self.assertTrue(found, "no table in the panel matched")
        return found[-1]

    def _habitability_row(self):
        """The Star Habitability table's single data row, as displayed text."""
        model = self._find_table(lambda h: h == _HAB_HEADERS)
        return [model.item(0, c).text() for c in range(model.columnCount())]

    # ── the reported defect ──────────────────────────────────────────────────

    def test_tau_ceti_habitability_values_are_not_truncated_to_integers(self):
        self._render(_TAU_CETI)
        row = dict(zip(_HAB_HEADERS, self._habitability_row()))
        self.assertEqual(row["Tidal Lock"], "0.499084")
        self.assertEqual(row["Abiogenesis"], "0.835729")
        self.assertEqual(row["Snow Line"], "1.900482")

    def test_gj_581_sub_unity_abiogenesis_zone_survives(self):
        # 0.022930729 truncated to "0" before the fix — the worst case, since
        # the value is two orders of magnitude below 1.
        self._render(_GJ_581)
        row = dict(zip(_HAB_HEADERS, self._habitability_row()))
        self.assertEqual(row["Tidal Lock"], "0.308738")
        self.assertEqual(row["Abiogenesis"], "0.022931")
        self.assertEqual(row["Snow Line"], "0.308222")

    def test_every_habitability_column_renders_at_six_decimals(self):
        # Guards the whole row, not just the three that regressed: all nine are
        # AU distances and `docs/star-databases.md` specifies 6dp for each.
        for star_row in (_TAU_CETI, _GJ_581):
            self._render(star_row)
            for header, text in zip(_HAB_HEADERS, self._habitability_row()):
                with self.subTest(star=star_row["S_NAME"], column=header):
                    self.assertRegex(text, r"^-?\d+\.\d{6}$")

    def test_habitability_values_match_the_underlying_catalogue_floats(self):
        # The formatting must not merely be 6dp — it must be *this* number.
        self._render(_TAU_CETI)
        for header, key in (("Tidal Lock", "S_TIDAL_LOCK"),
                            ("Abiogenesis", "S_ABIO_ZONE"),
                            ("Snow Line", "S_SNOW_LINE")):
            text = dict(zip(_HAB_HEADERS, self._habitability_row()))[header]
            with self.subTest(column=header):
                self.assertAlmostEqual(float(text), float(_TAU_CETI[key]), places=6)

    # ── the int fallback that is still correct ───────────────────────────────

    def test_star_temperature_is_still_rendered_as_an_integer(self):
        # `_sf`'s int fallback is deliberate for Temp — the CLI truncates it the
        # same way (`main.py::_display_hwc_star_properties`). This pins that the
        # fix above did not turn the whole helper into a float formatter.
        self._render(_TAU_CETI)
        model = self._find_table(
            lambda h: "Temp" in h and "Spectral Type" in h)
        headers = [model.headerData(c, Qt.Orientation.Horizontal)
                   for c in range(model.columnCount())]
        self.assertEqual(model.item(0, headers.index("Temp")).text(), "5344")


if __name__ == "__main__":
    unittest.main()
