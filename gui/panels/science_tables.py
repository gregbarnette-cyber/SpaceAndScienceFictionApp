# gui/panels/science_tables.py — Options 12 (Solar System Bodies) and 13 (Main Sequence Stars).
# Each option has its own independent panel class.

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.science
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_hr_canvas, make_orbits_canvas,
)


def _orbit_diagram_tab(choices, km_axis=False):
    """A diagram tab: a QComboBox over `choices` [(label, kind), …] + an orbital
    canvas (`make_orbits_canvas`) rebuilt for the selected kind (Phase O · O7)."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    combo = QComboBox()
    combo.setProperty("no_width_cap", True)
    for label, _kind in choices:
        combo.addItem(label)
    lay.addWidget(combo)
    holder = QWidget()
    hlay = QVBoxLayout(holder)
    hlay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(holder, 1)

    def _rebuild(idx):
        while hlay.count():
            it = hlay.takeAt(0)
            ww = it.widget()
            if ww:
                ww.deleteLater()
        label, kind = choices[idx]
        data = core.viz.prepare_solar_system_orbits(kind)
        if "error" in data:
            hlay.addWidget(QLabel(data["error"]))
            return
        title = (f"{data['star_name']}'s Moons" if km_axis
                 else f"Solar System — {label}")
        canvas, toolbar = make_orbits_canvas(
            None, data["orbits"], data["hz_zones"], data["max_au"],
            star_name=data["star_name"], title=title, km_axis=km_axis)
        hlay.addWidget(toolbar)
        hlay.addWidget(canvas)

    combo.currentIndexChanged.connect(_rebuild)
    _rebuild(0)
    return w


def _au_lm(val_str: str) -> str:
    """Format a string AU value as 'X (Y LM)', stripping trailing zeros."""
    try:
        v = float(val_str)
    except (ValueError, TypeError):
        return str(val_str)
    return f"{v:g} ({v * 8.3167:.3f} LM)"


class SolarSystemPanel(DiagramToggleMixin, ResultPanel):
    """Option 11 — Solar System Bodies: four sub-tabs for planets, moons, dwarf
    planets, asteroids.

    Phase O · O7 adds an "Orbital Diagram" tab (combo: Planets / Dwarf Planets +
    Asteroids) and a "Moon Systems" tab (combo: per-planet moon orbits, with a km
    secondary axis) behind a Show Diagrams toggle. The four data tabs are
    unchanged; rendered once at construction (no inputs).
    """

    def build_inputs(self):
        form_widget = QWidget()
        row = QHBoxLayout(form_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        row.addWidget(self._show_diagrams_btn)
        row.addStretch()
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        data = core.science.compute_solar_system_tables()
        tabs = QTabWidget()
        self._tables_widget = tabs
        self._layout.addWidget(tabs, 1)

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

        # ── Phase O O7: orbital-diagram viz tabs ──────────────────────────────
        self._setup_diagram_view()
        if mpl_available():
            self._viz_tabs_widget.addTab(
                _orbit_diagram_tab([("Planets", "planets"),
                                    ("Dwarf Planets + Asteroids", "dwarfs_asteroids")]),
                "Orbital Diagram")
            moon_planets = list(data["moons"].keys())
            if moon_planets:
                self._viz_tabs_widget.addTab(
                    _orbit_diagram_tab([(p, f"moons:{p}") for p in moon_planets],
                                       km_axis=True),
                    "Moon Systems")
        self._finish_render()
        self._input_count = self._layout.count()


class MainSequencePanel(DiagramToggleMixin, ResultPanel):
    """Option 12 — Main Sequence Star Properties from propertiesOfMainSequenceStars.csv.

    Phase O · O2a: gains an "HR Diagram" viz tab (Teff vs absolute visual magnitude)
    via the Show Diagrams toggle. No inputs — the table + diagram are built once.
    """

    def build_inputs(self):
        # No inputs; just a Show Diagrams button (revealed after the HR tab is built).
        form_widget = QWidget()
        row = QHBoxLayout(form_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        row.addWidget(self._show_diagrams_btn)
        row.addStretch()
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        # ── Data table ────────────────────────────────────────────────────────
        self._tables_widget = QWidget()
        tlay = QVBoxLayout(self._tables_widget)
        tlay.setContentsMargins(0, 0, 0, 0)

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
        tlay.addWidget(view)
        self._layout.addWidget(self._tables_widget, 1)

        # ── HR Diagram viz tab (O2a) ──────────────────────────────────────────
        self._setup_diagram_view()
        if mpl_available():
            ref = core.viz.prepare_hr_main_sequence()
            if "error" not in ref:
                canvas, toolbar = make_hr_canvas(self, ref)
                w = QWidget()
                wl = QVBoxLayout(w)
                wl.setContentsMargins(4, 4, 4, 4)
                wl.addWidget(toolbar)
                wl.addWidget(canvas)
                self._viz_tabs_widget.addTab(w, "HR Diagram")
        self._finish_render()
