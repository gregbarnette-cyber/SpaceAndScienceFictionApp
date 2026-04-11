# gui/panels/science_tables.py — Options 12 (Solar System Bodies) and 13 (Main Sequence Stars).
# Each option has its own independent panel class.

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout

from gui.panels.base import ResultPanel
import core.science


def _au_lm(val_str: str) -> str:
    """Format a string AU value as 'X (Y LM)', stripping trailing zeros."""
    try:
        v = float(val_str)
    except (ValueError, TypeError):
        return str(val_str)
    return f"{v:g} ({v * 8.3167:.3f} LM)"


class SolarSystemPanel(ResultPanel):
    """Option 12 — Solar System Bodies: four sub-tabs for planets, moons, dwarf planets, asteroids."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        data = core.science.compute_solar_system_tables()
        tabs = QTabWidget()
        self._layout.addWidget(tabs)

        # ── Planets ───────────────────────────────────────────────────────────
        p_headers = [
            "Planet Name", "Mass (J)", "Diameter (J)", "Period",
            "Periastron (AU)", "Semimajor Axis (AU)", "Apastron (AU)",
            "Eccentricity", "Moons",
        ]
        p_rows = [
            [
                p.get("Planet", ""),
                p.get("Mass", ""),
                p.get("Diameter", ""),
                p.get("Period", ""),
                _au_lm(p.get("Periastron", "")),
                _au_lm(p.get("Semimajor Axis", "")),
                _au_lm(p.get("Apastron", "")),
                p.get("Eccentricity", ""),
                p.get("Moons", ""),
            ]
            for p in data["planets"]
        ]
        view = self.make_table(p_headers, p_rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "Planets")

        # ── Moons (one sub-tab per planet) ────────────────────────────────────
        moon_widget = QWidget()
        moon_layout = QVBoxLayout(moon_widget)
        moon_layout.setContentsMargins(0, 0, 0, 0)
        moon_subtabs = QTabWidget()
        moon_layout.addWidget(moon_subtabs)

        moon_headers = [
            "Satellite Name", "Diameter (km)", "Mass (kg)",
            "Perigee (km)", "Apogee (km)", "SemiMajor Axis (km)",
            "Eccentricity", "Period (days)", "Gravity (m/s²)", "Escape Velocity (km/s)",
        ]
        for planet, moons in data["moons"].items():
            m_rows = [
                [
                    m.get("Satellite Name", ""),
                    m.get("Diameter (km)", ""),
                    m.get("Mass (kg)", ""),
                    m.get("Perigee (km)", ""),
                    m.get("Apogee (km)", ""),
                    m.get("SemiMajor Axis (km)", ""),
                    m.get("Eccentricity", ""),
                    m.get("Period (days)", ""),
                    m.get("Gravity (m/s^2)", ""),
                    m.get("Escape Velocity (km/s)", ""),
                ]
                for m in moons
            ]
            moon_subtabs.addTab(self.make_table(moon_headers, m_rows), planet)

        tabs.addTab(moon_widget, "Moons")

        # ── Dwarf Planets ─────────────────────────────────────────────────────
        d_headers = [
            "Dwarf Planet Name", "Mass (E)", "Diameter", "Period",
            "Periastron (AU)", "Semimajor Axis (AU)", "Apastron (AU)",
            "Eccentricity", "Moons",
        ]
        d_rows = [
            [
                d.get("Name", ""),
                d.get("Mass", ""),
                d.get("Diameter", ""),
                d.get("Period", ""),
                _au_lm(d.get("Periastron", "")),
                _au_lm(d.get("Semimajor Axis", "")),
                _au_lm(d.get("Apastron", "")),
                d.get("Eccentricity", ""),
                d.get("Moons", ""),
            ]
            for d in data["dwarf_planets"]
        ]
        view = self.make_table(d_headers, d_rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "Dwarf Planets")

        # ── Asteroids ─────────────────────────────────────────────────────────
        a_headers = [
            "Asteroid Name", "Diameter (KM)", "Period",
            "Periastron (AU)", "Semimajor Axis (AU)", "Apastron (AU)", "Eccentricity",
        ]
        a_rows = [
            [
                a.get("Name", ""),
                a.get("Diameter", ""),
                a.get("Period", ""),
                _au_lm(a.get("Periastron", "")),
                _au_lm(a.get("Semimajor Axis", "")),
                _au_lm(a.get("Apastron", "")),
                a.get("Eccentricity", ""),
            ]
            for a in data["asteroids"]
        ]
        view = self.make_table(a_headers, a_rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "Asteroids")


class MainSequencePanel(ResultPanel):
    """Option 13 — Main Sequence Star Properties from propertiesOfMainSequenceStars.csv."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        rows_data = core.science.compute_main_sequence_table()
        col_keys = [
            "Spectral Class", "B-V", "Teeff(K)", "AbsMag Vis.", "AbsMag Bol.",
            "Bolo. Corr. (BC)", "Lum", "R", "M", "p (g/cm3)", "Lifetime (years)",
        ]
        headers = [
            "Spectral Class", "B-V", "Teff (K)", "Abs Mag Vis", "Abs Mag Bol",
            "BC", "Lum", "R", "M", "p (g/cm³)", "Lifetime (years)",
        ]
        table_rows = [[row.get(k, "") for k in col_keys] for row in rows_data]
        view = self.make_table(headers, table_rows)
        view.setSortingEnabled(False)  # preserve spectral order
        self._layout.addWidget(view)
