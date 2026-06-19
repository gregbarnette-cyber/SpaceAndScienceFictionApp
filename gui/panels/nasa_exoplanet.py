# gui/panels/nasa_exoplanet.py — Options 2, 3, 4, 5: NASA Exoplanet Archive queries.
#
# Each option is its own standalone panel class:
#   NasaAllTablesPanel        — option 2 (pscomppars + HWO ExEP + Mission Exocat)
#   NasaPlanetarySystemsPanel — option 3 (pscomppars only)
#   NasaHwoExepPanel          — option 4 (HWO ExEP only)
#   NasaMissionExocatPanel    — option 5 (Mission Exocat only)

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QTabWidget, QSizePolicy,
    QDateEdit, QDialog, QGridLayout, QDialogButtonBox, QSlider,
)
from PySide6.QtCore import Qt, QDate, QTimer

from gui.panels.base import ResultPanel, DiagramToggleMixin
from gui.panels.hypatia_tab import build_hypatia_tab
import core.databases
import core.viz
import core.science
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_orbits_canvas, make_abundance_canvas,
    make_exoplanet_system_canvas, make_mass_radius_canvas, make_transit_canvas,
    make_size_comparison_canvas, log_viz_error, wrap_scrollable,
    wrap_orbits_with_solar_toggle, make_kinematics_tab,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _fval(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _fmt(v, dp=3):
    f = _fval(v)
    return f"{f:.{dp}f}" if f is not None else "N/A"


def _lum_str(row):
    """Format luminosity from st_lum + calculated."""
    st_lum = _fval(row.get("st_lum"))
    st_rad = _fval(row.get("st_rad"))
    st_tef = _fval(row.get("st_teff"))
    if st_rad is not None and st_tef is not None:
        calc = st_rad ** 2 * (st_tef / 5778) ** 4
        return (f"{st_lum:.5f} ({calc:.6f})" if st_lum is not None
                else f"({calc:.6f})")
    return f"{st_lum:.5f}" if st_lum is not None else "N/A"


def _add_simbad_banner(layout, simbad):
    banner = QLabel(f"<b>SIMBAD Designations:</b><br>{simbad.get('desig_str', 'N/A')}")
    banner.setWordWrap(True)
    layout.addWidget(banner)


def _add_hz_table(panel, layout, rows_or_row):
    """Add Calculated Habitable Zone table to layout."""
    if isinstance(rows_or_row, list):
        row = rows_or_row[0] if rows_or_row else {}
    else:
        row = rows_or_row
    hz = core.databases.compute_habitable_zone(
        row.get("st_teff"), row.get("st_lum"), row.get("st_rad")
    )
    if not hz:
        return
    layout.addWidget(QLabel("<b>Calculated Habitable Zone</b>"))
    headers = ["Zone", "AU (Light Minutes)"]
    table_rows = [[name, f"{au:.3f} ({au * 8.3167:.3f} LM)"] for name, au in hz]
    t = panel.make_table(headers, table_rows)
    t.setSortingEnabled(False)
    layout.addWidget(t)


def _add_nasa_tables(panel, layout, simbad, planets):
    """Render Star Properties + Planet Properties tables from pscomppars rows."""
    if not planets:
        return

    first = planets[0]
    desig = simbad["designations"]
    main_id = str(desig.get("MAIN_ID") or "").strip().lstrip("*").strip()

    id_parts = [str(desig[k]) for k in ("HD", "HIP", "TIC", "Gaia EDR3") if desig.get(k)]
    star_line = f"{main_id}  ({', '.join(id_parts)})" if id_parts else main_id
    layout.addWidget(QLabel(f"<b>NASA Exoplanet Archive — {star_line}</b>"))

    n_stars   = int(_fval(first.get("sy_snum")) or 1)
    n_planets = int(_fval(first.get("sy_pnum")) or len(planets))
    layout.addWidget(QLabel(f"Stars: {n_stars}   Planets: {n_planets}"))

    layout.addWidget(QLabel("<b>Star Properties</b>"))
    star_headers = ["#", "Spectral Type", "MagV", "Luminosity", "Temp",
                    "Mass", "Radius", "Parallax", "Parsecs", "LYs", "Fe/H", "Age"]
    star_rows = []
    for i, row in enumerate(planets, 1):
        sy_dist = _fval(row.get("sy_dist"))
        star_rows.append([
            str(i),
            str(row.get("st_spectype") or "N/A"),
            _fmt(row.get("sy_vmag"), 5),
            _lum_str(row),
            _fmt(row.get("st_teff"), 0),
            _fmt(row.get("st_mass"), 3),
            _fmt(row.get("st_rad"),  2),
            _fmt(row.get("sy_plx"),  3),
            f"{sy_dist:.5f}" if sy_dist is not None else "N/A",
            f"{sy_dist * 3.26156:.4f}" if sy_dist is not None else "N/A",
            _fmt(row.get("st_met"),  2),
            _fmt(row.get("st_age"),  2),
        ])
    layout.addWidget(panel.make_table(star_headers, star_rows))

    layout.addWidget(QLabel("<b>Planet Properties</b>"))
    planet_headers = ["#", "Planet Name", "Mass (E)", "Mass (J)", "Radius (E)",
                      "Radius (J)", "Orbit", "Distance", "Eccentricity",
                      "Temp", "Insol Flux", "Density"]
    planet_rows = []
    for i, row in enumerate(planets, 1):
        sma  = _fval(row.get("pl_orbsmax"))
        ecc  = _fval(row.get("pl_orbeccen"))
        orb  = _fval(row.get("pl_orbper"))
        if sma is not None and ecc is not None:
            ea   = sma * ecc
            dist = f"{sma - ea:.3f} AU - {sma:.3f} AU - {sma + ea:.3f} AU"
            ecc_s = f"{ecc:.2f} ({ea:.3f} AU)"
        elif sma is not None:
            dist, ecc_s = f"N/A - {sma:.3f} AU - N/A", "N/A"
        else:
            dist, ecc_s = "N/A", "N/A"
        planet_rows.append([
            str(i),
            str(row.get("pl_name") or "N/A"),
            _fmt(row.get("pl_bmasse"), 2),
            _fmt(row.get("pl_bmassj"), 7),
            _fmt(row.get("pl_rade"),   2),
            _fmt(row.get("pl_radj"),   3),
            f"{orb:.3f} days" if orb is not None else "N/A",
            dist, ecc_s,
            _fmt(row.get("pl_eqt"),   0),
            _fmt(row.get("pl_insol"),  2),
            _fmt(row.get("pl_dens"),   2),
        ])
    layout.addWidget(panel.make_table(planet_headers, planet_rows))


def _add_hwo_tables(panel, layout, hwo_rows):
    """Render HWO ExEP Star Properties + System/EEI Properties tables."""
    if not hwo_rows:
        return
    layout.addWidget(QLabel("<b>HWO ExEP — Star Properties</b>"))
    star_headers = ["Spectral Type", "Luminosity", "Temp", "Mass", "Radius",
                    "Parallax", "Parsecs", "LYs", "Fe/H"]
    star_rows = []
    for row in hwo_rows:
        sy_dist = _fval(row.get("sy_dist"))
        sy_plx  = _fval(row.get("sy_plx"))
        star_rows.append([
            str(row.get("st_spectype") or "N/A"),
            _lum_str(row),
            _fmt(row.get("st_teff"), 0),
            _fmt(row.get("st_mass"), 3),
            _fmt(row.get("st_rad"),  2),
            _fmt(sy_plx, 3) if sy_plx is not None else "N/A",
            f"{sy_dist:.5f}" if sy_dist is not None else "N/A",
            f"{sy_dist * 3.26156:.4f}" if sy_dist is not None else "N/A",
            _fmt(row.get("st_met"),  3),
        ])
    layout.addWidget(panel.make_table(star_headers, star_rows))

    layout.addWidget(QLabel("<b>HWO ExEP — System / EEI Properties</b>"))
    eei_headers = ["Planets", "# Planets", "Disk",
                   "EEID (AU / LM)", "Earth Twin Ratio", "Orbital Period at EEID"]
    eei_rows = []
    for row in hwo_rows:
        def _flag(v):
            if v is None or str(v).strip() in ("", "None", "nan"):
                return "None"
            s = str(v).strip()
            if s in ("Y", "1"):
                return "Y"
            if s in ("N", "0"):
                return "N"
            return s
        eeid_au = _fval(row.get("st_eei_orbsep"))
        eeid_str = (f"{eeid_au:.3f} AU ({eeid_au * 8.3167:.4f} LM)"
                    if eeid_au is not None else "N/A")
        ratio = _fval(row.get("st_etwin_bratio"))
        ratio_str = f"{ratio:.3e}" if ratio is not None else "N/A"
        per   = _fval(row.get("st_eei_orbper"))
        per_str = f"{per:.3f} days" if per is not None else "N/A"
        eei_rows.append([
            _flag(row.get("sy_planets_flag")),
            str(row.get("sy_pnum") or "N/A"),
            _flag(row.get("sy_disks_flag") or row.get("sy_disksflag")),
            eeid_str, ratio_str, per_str,
        ])
    layout.addWidget(panel.make_table(eei_headers, eei_rows))


def _add_exocat_tables(panel, layout, row):
    """Render Mission Exocat Star Properties table."""
    if not row:
        return
    layout.addWidget(QLabel(
        f"<b>Mission Exocat — {row.get('star_name', 'N/A')}</b>"
    ))

    def _ef(key, dp=None):
        v = row.get(key, "")
        if v in (None, ""):
            return "N/A"
        try:
            f = float(v)
            return f"{f:.{dp}f}" if dp is not None else str(f)
        except ValueError:
            return str(v).strip()

    st_rad = _fval(row.get("st_rad"))
    st_tef = _fval(row.get("st_teff"))
    st_lbol = _fval(row.get("st_lbol"))
    if st_rad is not None and st_tef is not None:
        calc = st_rad**2 * (st_tef / 5778)**4
        lum_s = (f"{st_lbol:.2f} ({calc:.6f})" if st_lbol is not None
                 else f"({calc:.6f})")
    elif st_lbol is not None:
        lum_s = f"{st_lbol:.2f}"
    else:
        lum_s = "N/A"

    st_dist = _fval(row.get("st_dist"))
    eeid_au = _fval(row.get("st_eeidau"))
    eeid_s  = (f"{eeid_au:.2f} ({eeid_au * 8.3167:.4f} LM)"
               if eeid_au is not None else "N/A")

    headers = ["Spectral Type", "Temp", "Mass", "Radius", "Luminosity",
               "EE Rad Distance", "Parsecs", "LYs", "Fe/H", "Age"]
    data_row = [
        _ef("st_spttype"),
        _ef("st_teff", 0),
        _ef("st_mass", 1),
        _ef("st_rad",  2),
        lum_s,
        eeid_s,
        _ef("st_dist", 2),
        f"{st_dist * 3.26156:.4f}" if st_dist is not None else "N/A",
        _ef("st_metfe", 2),
        _ef("st_age"),
    ]
    layout.addWidget(panel.make_table(headers, [data_row]))

    hz = core.databases.compute_habitable_zone(
        row.get("st_teff"), None, row.get("st_rad")
    )
    if hz:
        layout.addWidget(QLabel("<b>Calculated Habitable Zone</b>"))
        hz_rows = [[name, f"{au:.3f} ({au * 8.3167:.3f} LM)"] for name, au in hz]
        t = panel.make_table(["Zone", "AU (Light Minutes)"], hz_rows)
        t.setSortingEnabled(False)
        layout.addWidget(t)


# ── Shared base for single-star search panels ─────────────────────────────────

class _StarSearchPanel(ResultPanel):
    """Base class for options 2–8: search form + scrollable results area."""

    _placeholder = "e.g. Star Name / Designation"

    def build_inputs(self):
        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name)

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._result_area = QVBoxLayout(self._scroll_widget)
        self._result_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_widget)
        self._layout.addWidget(scroll, 1)

    def _clear_results(self):
        while self._result_area.count():
            item = self._result_area.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_error(self, msg):
        self._clear_results()
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: red;")
        lbl.setWordWrap(True)
        self._result_area.addWidget(lbl)

    def _search(self):
        name = self._name.text().strip()
        if not name:
            return
        self._clear_results()
        self.set_status("Looking up star in SIMBAD…")
        self.run_in_background(
            core.databases.compute_simbad_lookup, name,
            on_result=self._on_simbad_done,
        )

    def _on_simbad_done(self, simbad_result):
        if "error" in simbad_result:
            self._show_error(simbad_result["error"])
            return
        self._do_search(simbad_result)

    def _do_search(self, simbad_result):
        raise NotImplementedError


# ── Option 2: NASA All Tables ─────────────────────────────────────────────────

class NasaAllTablesPanel(_StarSearchPanel):
    """Option 2 — NASA Exoplanet Archive: All Tables."""

    _placeholder = "e.g. Tau Ceti, HD 10700, 51 Pegasi"

    def _do_search(self, simbad_result):
        self.set_status("Querying NASA Exoplanet Archive…")
        self.run_in_background(
            core.databases.compute_exoplanet_archive,
            simbad_result,
            on_result=self._render,
            on_progress=self.set_status,
        )

    def _render(self, result):
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        simbad  = result["simbad"]
        planets = result["planets"]
        hwo     = result.get("hwo")
        exocat  = result.get("exocat")

        _add_simbad_banner(self._result_area, simbad)

        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Tab 1: Planetary Composite Systems ────────────────────────────────
        pcs_w = QWidget()
        pcs_l = QVBoxLayout(pcs_w)
        pcs_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        _add_nasa_tables(self, pcs_l, simbad, planets)
        _add_hz_table(self, pcs_l, planets)
        tabs.addTab(pcs_w, "Planetary Composite Systems")

        # ── Tab 2: HWO ExEP Stars ─────────────────────────────────────────────
        hwo_w = QWidget()
        hwo_l = QVBoxLayout(hwo_w)
        hwo_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        if hwo:
            _add_hwo_tables(self, hwo_l, hwo)
            _add_hz_table(self, hwo_l, hwo)
        else:
            hwo_l.addWidget(QLabel("No HWO ExEP data found for this star."))
        tabs.addTab(hwo_w, "HWO ExEP Stars")

        # ── Tab 3: Mission Exocat ─────────────────────────────────────────────
        exo_w = QWidget()
        exo_l = QVBoxLayout(exo_w)
        exo_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        if exocat:
            _add_exocat_tables(self, exo_l, exocat)
        else:
            exo_l.addWidget(QLabel("No Mission Exocat data found for this star."))
        tabs.addTab(exo_w, "Mission Exocat")

        self._result_area.addWidget(tabs)


# ── Option 3: Planetary Systems Composite ────────────────────────────────────

# ── Viz helpers shared by opts 3, 4, 5 ───────────────────────────────────────

def _make_hz_tab(panel, rows_or_row):
    """Return a QWidget with an embedded HZ diagram, or None if data is missing."""
    if not mpl_available():
        return None
    if isinstance(rows_or_row, list):
        row = rows_or_row[0] if rows_or_row else {}
    else:
        row = rows_or_row or {}
    teff   = _fval(row.get("st_teff") or row.get("st_teff"))
    st_rad = _fval(row.get("st_rad"))
    st_lum = _fval(row.get("st_lum"))
    if teff is None:
        return None
    if st_rad is not None:
        lum = st_rad ** 2 * (teff / 5778.0) ** 4
    elif st_lum is not None:
        lum = 10 ** st_lum
    else:
        return None
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None
    eeid_au = _fval(row.get("st_eei_orbsep"))
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    canvas, toolbar = make_hz_canvas(
        panel, hz_data["zones"], hz_data["max_au"],
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=eeid_au,
    )
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_hz_tab_exocat(panel, row):
    """HZ tab for Mission Exocat rows (uses st_teff / st_rad; eeid from st_eeidau)."""
    if not mpl_available() or not row:
        return None
    teff   = _fval(row.get("st_teff"))
    st_rad = _fval(row.get("st_rad"))
    st_lbol= _fval(row.get("st_lbol"))
    if teff is None:
        return None
    if st_rad is not None:
        lum = st_rad ** 2 * (teff / 5778.0) ** 4
    elif st_lbol is not None:
        lum = st_lbol
    else:
        return None
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None
    eeid_au = _fval(row.get("st_eeidau"))
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    canvas, toolbar = make_hz_canvas(
        panel, hz_data["zones"], hz_data["max_au"],
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=eeid_au,
    )
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _hyper_au_for(sp_type):
    """Resolve a host spectral type → Honorverse hyper-limit AU, or None (O10b)."""
    if not sp_type:
        return None
    hl = core.science.compute_hyper_limit_for_spectral_type(str(sp_type))
    return hl["au"] if hl else None


def _make_orbits_tab(panel, planets, star_name="", sp_type=None):
    """Return a QWidget with an embedded orbital diagram, or None if insufficient data.

    The diagram carries a "Show Solar System reference" overlay checkbox (Phase O · O4)
    and, when the host spectral type resolves a Honorverse hyper limit (Phase O · O10b),
    a "Show Honorverse Hyper Limit (fiction)" checkbox.
    """
    if not mpl_available():
        return None
    orbit_data = core.viz.prepare_system_orbits(planets)
    if "error" in orbit_data:
        return None
    hyper_au = _hyper_au_for(sp_type)

    def _build(solar_overlay, show_hyper):
        return make_orbits_canvas(
            panel,
            orbit_data["orbits"],
            orbit_data["hz_zones"],
            orbit_data["max_au"],
            star_name=star_name,
            solar_overlay=solar_overlay,
            hyper_au=hyper_au if show_hyper else None,
        )

    return wrap_orbits_with_solar_toggle(panel, _build, hyper_au=hyper_au)


def _make_mass_radius_tab(panel, planets, mass_key="pl_bmasse",
                          radius_key="pl_rade", name_key="pl_name"):
    """Return a QWidget with an embedded Mass–Radius diagram, or None (Phase O · O3).

    Added only when ≥1 planet carries both a positive mass and radius. Generic over
    NASA (pl_bmasse/pl_rade/pl_name — the defaults) and HWC (P_MASS/P_RADIUS/P_NAME)
    rows via the column keys.
    """
    if not mpl_available():
        return None
    mr_data = core.viz.prepare_mass_radius(planets, mass_key, radius_key, name_key)
    if "error" in mr_data:
        return None
    canvas, toolbar = make_mass_radius_canvas(panel, mr_data)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_transit_tab(panel, planets):
    """Return a QWidget with an embedded Transit Geometry diagram, or None (Phase O · O13).

    Added on opts 3 + Map only when ≥1 planet has a host stellar radius and a
    measured orbital inclination (NASA `st_rad`/`pl_orbsmax`/`pl_orbincl`).
    """
    if not mpl_available():
        return None
    tg_data = core.viz.prepare_transit_geometry(planets)
    if "error" in tg_data:
        return None
    canvas, toolbar = make_transit_canvas(panel, tg_data)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_size_tab(panel, planets, radius_key="pl_rade", name_key="pl_name"):
    """Return a QWidget with a Planet Size-Comparison strip, or None (Phase O · O14).

    Added on opts 3/6/Map only when ≥1 planet carries a radius. Generic over NASA
    (pl_rade/pl_name — the defaults) and HWC (P_RADIUS/P_NAME) via the column keys.
    """
    if not mpl_available():
        return None
    canvas, toolbar = make_size_comparison_canvas(panel, planets, radius_key, name_key)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _planetary_systems_with_hypatia(simbad_result: dict) -> dict:
    result = core.databases.compute_planetary_systems_composite(simbad_result)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(simbad_result)
    return result


def _hwo_exep_with_hypatia(simbad_result: dict) -> dict:
    result = core.databases.compute_hwo_exep(simbad_result)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(simbad_result)
    return result


def _mission_exocat_with_hypatia(simbad_result: dict) -> dict:
    result = core.databases.compute_mission_exocat(simbad_result)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(simbad_result)
    return result


# ── Option 3: Planetary Systems Composite ────────────────────────────────────

class NasaPlanetarySystemsPanel(_StarSearchPanel):
    """Option 3 — NASA Exoplanet Archive: Planetary Systems."""

    _placeholder = "e.g. Tau Ceti, HD 10700"

    # ── Input form ────────────────────────────────────────────────────────────

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star System:", self._name)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    # ── Results area ──────────────────────────────────────────────────────────

    def build_results_area(self):
        # Tables view
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._result_area = QVBoxLayout(self._scroll_widget)
        self._result_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_widget)
        self._scroll_area = scroll
        self._layout.addWidget(scroll, 1)

        # Diagrams view (hidden until Show Diagrams pressed)
        self._viz_container = QWidget()
        self._viz_container.setVisible(False)
        viz_layout = QVBoxLayout(self._viz_container)
        viz_layout.setContentsMargins(4, 4, 4, 4)

        show_tables_row = QHBoxLayout()
        self._show_tables_btn = QPushButton("Show Tables")
        self._show_tables_btn.clicked.connect(self._exit_diagram_mode)
        show_tables_row.addWidget(self._show_tables_btn)
        show_tables_row.addStretch()
        viz_layout.addLayout(show_tables_row)

        self._viz_tabs_widget = QTabWidget()
        self._viz_tabs_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        viz_layout.addWidget(self._viz_tabs_widget, 1)

        self._layout.addWidget(self._viz_container, 1)

    # ── Navigation override ───────────────────────────────────────────────────

    def reset(self):
        self.window.nav_tree.show()
        super().reset()

    # ── Diagram toggle ────────────────────────────────────────────────────────

    def _enter_diagram_mode(self):
        self.window.nav_tree.hide()
        self._form_widget.hide()
        self._scroll_area.hide()
        self._viz_container.show()

    def _exit_diagram_mode(self):
        self.window.nav_tree.show()
        self._form_widget.show()
        self._scroll_area.show()
        self._viz_container.hide()

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self, simbad_result):
        self.set_status("Querying NASA Exoplanet Archive…")
        self.run_in_background(
            _planetary_systems_with_hypatia,
            simbad_result,
            on_result=self._render,
            on_progress=self.set_status,
        )

    def _render(self, result):
        self._exit_diagram_mode()
        self._show_diagrams_btn.setVisible(False)
        while self._viz_tabs_widget.count():
            w = self._viz_tabs_widget.widget(0)
            self._viz_tabs_widget.removeTab(0)
            if w:
                w.deleteLater()
        self._clear_results()

        if "error" in result:
            self._show_error(result["error"])
            return

        simbad  = result["simbad"]
        planets = result["planets"]
        hypatia = result.get("hypatia")

        _add_simbad_banner(self._result_area, simbad)

        # Data tabs
        data_tabs = QTabWidget()
        data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        data_w = QWidget()
        data_l = QVBoxLayout(data_w)
        data_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        _add_nasa_tables(self, data_l, simbad, planets)
        _add_hz_table(self, data_l, planets)
        data_tabs.addTab(data_w, "Data")

        if hypatia is not None:
            data_tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")

        self._result_area.addWidget(data_tabs)

        # Viz tabs (shown only via Show Diagrams button)
        star_name = str(planets[0].get("hostname") or "") if planets else ""
        orb_w = _make_orbits_tab(
            self, planets, star_name,
            sp_type=(planets[0].get("st_spectype") if planets else None))
        if orb_w:
            self._viz_tabs_widget.addTab(orb_w, "Orbital Diagram")
        hz_w = _make_hz_tab(self, planets)
        if hz_w:
            self._viz_tabs_widget.addTab(hz_w, "HZ Diagram")
        mr_w = _make_mass_radius_tab(self, planets)
        if mr_w:
            self._viz_tabs_widget.addTab(mr_w, "Mass–Radius")
        tg_w = _make_transit_tab(self, planets)
        if tg_w:
            self._viz_tabs_widget.addTab(tg_w, "Transit Geometry")
        sz_w = _make_size_tab(self, planets)
        if sz_w:
            self._viz_tabs_widget.addTab(sz_w, "Size Comparison")

        if hypatia and "error" not in hypatia:
            try:
                ab_data = core.viz.prepare_abundance_profile(hypatia)
                if "error" not in ab_data:
                    ab_canvas, ab_toolbar = make_abundance_canvas(
                        None, ab_data, hypatia.get("star_name", "")
                    )
                    if ab_canvas is not None:
                        ab_w = wrap_scrollable(None, ab_canvas, ab_toolbar)
                        self._viz_tabs_widget.addTab(ab_w, "Abundance Profile")
            except Exception:
                log_viz_error("Abundance Profile")

            try:
                kin_w = make_kinematics_tab(hypatia)
                if kin_w is not None:
                    self._viz_tabs_widget.addTab(kin_w, "Kinematics")
            except Exception:
                log_viz_error("Kinematics")

        if self._viz_tabs_widget.count() > 0:
            self._show_diagrams_btn.setVisible(True)


# ── Option 4: HWO ExEP ────────────────────────────────────────────────────────

class NasaHwoExepPanel(DiagramToggleMixin, _StarSearchPanel):
    """Option 4 — NASA Exoplanet Archive: HWO ExEP Stars."""

    _placeholder = "e.g. Tau Ceti, HD 10700, HR 509"

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._result_area = QVBoxLayout(self._scroll_widget)
        self._result_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_widget)
        self._tables_widget = scroll
        self._layout.addWidget(scroll, 1)
        self._setup_diagram_view()

    def _do_search(self, simbad_result):
        self.set_status("Querying HWO ExEP archive…")
        self.run_in_background(
            _hwo_exep_with_hypatia,
            simbad_result,
            on_result=self._render,
            on_progress=self.set_status,
        )

    def _render(self, result):
        self._prepare_render()
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        simbad  = result["simbad"]
        hwo     = result["hwo"]
        hypatia = result.get("hypatia")

        _add_simbad_banner(self._result_area, simbad)

        data_tabs = QTabWidget()
        data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        data_w = QWidget()
        data_l = QVBoxLayout(data_w)
        data_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        _add_hwo_tables(self, data_l, hwo)
        _add_hz_table(self, data_l, hwo)
        data_tabs.addTab(data_w, "Data")

        if hypatia is not None:
            data_tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")

        self._result_area.addWidget(data_tabs)

        hz_w = _make_hz_tab(self, hwo)
        if hz_w:
            self._viz_tabs_widget.addTab(hz_w, "HZ Diagram")

        if hypatia and "error" not in hypatia:
            try:
                ab_data = core.viz.prepare_abundance_profile(hypatia)
                if "error" not in ab_data:
                    ab_canvas, ab_toolbar = make_abundance_canvas(
                        None, ab_data, hypatia.get("star_name", "")
                    )
                    if ab_canvas is not None:
                        ab_w = wrap_scrollable(None, ab_canvas, ab_toolbar)
                        self._viz_tabs_widget.addTab(ab_w, "Abundance Profile")
            except Exception:
                log_viz_error("Abundance Profile")

            try:
                kin_w = make_kinematics_tab(hypatia)
                if kin_w is not None:
                    self._viz_tabs_widget.addTab(kin_w, "Kinematics")
            except Exception:
                log_viz_error("Kinematics")

        self._finish_render()


# ── Option 5: Mission Exocat ──────────────────────────────────────────────────

class NasaMissionExocatPanel(DiagramToggleMixin, _StarSearchPanel):
    """Option 5 — NASA Exoplanet Archive: Mission Exocat Stars."""

    _placeholder = "e.g. Tau Ceti, HD 10700, GJ 667"

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._result_area = QVBoxLayout(self._scroll_widget)
        self._result_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_widget)
        self._tables_widget = scroll
        self._layout.addWidget(scroll, 1)
        self._setup_diagram_view()

    def _do_search(self, simbad_result):
        self.set_status("Searching Mission Exocat…")
        self.run_in_background(
            _mission_exocat_with_hypatia,
            simbad_result,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        simbad  = result["simbad"]
        exocat  = result["exocat"]
        hypatia = result.get("hypatia")

        _add_simbad_banner(self._result_area, simbad)

        data_tabs = QTabWidget()
        data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        data_w = QWidget()
        data_l = QVBoxLayout(data_w)
        data_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        _add_exocat_tables(self, data_l, exocat)
        data_tabs.addTab(data_w, "Data")

        if hypatia is not None:
            data_tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")

        self._result_area.addWidget(data_tabs)

        hz_w = _make_hz_tab_exocat(self, exocat)
        if hz_w:
            self._viz_tabs_widget.addTab(hz_w, "HZ Diagram")

        if hypatia and "error" not in hypatia:
            try:
                ab_data = core.viz.prepare_abundance_profile(hypatia)
                if "error" not in ab_data:
                    ab_canvas, ab_toolbar = make_abundance_canvas(
                        None, ab_data, hypatia.get("star_name", "")
                    )
                    if ab_canvas is not None:
                        ab_w = wrap_scrollable(None, ab_canvas, ab_toolbar)
                        self._viz_tabs_widget.addTab(ab_w, "Abundance Profile")
            except Exception:
                log_viz_error("Abundance Profile")

            try:
                kin_w = make_kinematics_tab(hypatia)
                if kin_w is not None:
                    self._viz_tabs_widget.addTab(kin_w, "Kinematics")
            except Exception:
                log_viz_error("Kinematics")

        self._finish_render()


# ── Phase O O5 — System Map date scrubber ────────────────────────────────────

def _scrub_span_days(planets) -> int:
    """Half-span (days) for the scrubber: min(2 × longest period, 50 yr).

    Falls back to 365 days when no planet has a usable orbital period.
    """
    periods = [_fval(p.get("pl_orbper")) for p in planets]
    periods = [pp for pp in periods if pp and pp > 0]
    if not periods:
        return 365   # no usable period → a ±1-year default window
    span = min(2.0 * max(periods), 50.0 * 365.25)
    return max(1, int(round(span)))


def _scrub_offset_date_iso(base_iso: str, offset_days: int) -> str:
    """ISO date = base date + offset_days (offline; pure)."""
    import datetime
    base = datetime.date.fromisoformat(base_iso)
    return (base + datetime.timedelta(days=int(offset_days))).isoformat()


class _SystemMapScrubber(QWidget):
    """System Map tab with a date slider + Play/Pause (Phase O · O5).

    Re-runs the offline ``prepare_exoplanet_system_diagram`` for the scrubbed
    date and re-offsets each epoch-known planet marker/label (``set_offsets``
    only — orbits and the host star stay static). ``epoch_known=False`` planets
    stay pinned at periastron (the scrubber invents no motion for them). No
    network calls during scrubbing.
    """

    def __init__(self, panel, base_data, planets, base_date_iso, on_planet_click):
        super().__init__()
        self._planets   = planets
        self._base_date = base_date_iso
        self._span_days = _scrub_span_days(planets)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)

        self._canvas, toolbar = make_exoplanet_system_canvas(
            panel, base_data, on_planet_click=on_planet_click)
        lay.addWidget(toolbar)
        lay.addWidget(self._canvas, 1)

        ctl = QHBoxLayout()
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._toggle_play)
        ctl.addWidget(self._play_btn)
        self._reset_btn = QPushButton("⏮ Reset")
        self._reset_btn.clicked.connect(self._reset)
        ctl.addWidget(self._reset_btn)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(-self._span_days)
        self._slider.setMaximum(self._span_days)
        self._slider.setValue(0)
        self._slider.setProperty("no_width_cap", True)
        self._slider.valueChanged.connect(self._on_slider)
        ctl.addWidget(self._slider, 1)
        self._readout = QLabel(f"Map date: {base_date_iso}")
        ctl.addWidget(self._readout)
        lay.addLayout(ctl)

        # ~10 fps play stepper + a 50 ms throttle that coalesces rapid drags.
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._advance)
        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)
        self._throttle.setInterval(50)
        self._throttle.timeout.connect(self._recompute)

    def _on_slider(self, _value):
        if not self._throttle.isActive():
            self._throttle.start()

    def _toggle_play(self):
        if self._timer.isActive():
            self._timer.stop()
            self._play_btn.setText("▶ Play")
        else:
            self._play_btn.setText("⏸ Pause")
            self._timer.start()

    def _advance(self):
        step = max(1, round(2 * self._span_days / 120))
        v = self._slider.value() + step
        if v > self._slider.maximum():
            v = self._slider.minimum()
        self._slider.setValue(v)

    def _reset(self):
        """Stop playback and snap the slider back to the base map date (centre)."""
        if self._timer.isActive():
            self._timer.stop()
            self._play_btn.setText("▶ Play")
        self._slider.setValue(0)
        self._recompute()   # immediate (don't wait on the throttle)

    def _recompute(self):
        offset   = self._slider.value()
        date_iso = _scrub_offset_date_iso(self._base_date, offset)
        data  = core.viz.prepare_exoplanet_system_diagram(self._planets, date_iso)
        scrub = getattr(self._canvas, "_scrub", None)
        if not scrub or "error" in data:
            return
        max_au = scrub["max_au"]
        by_name = {p["name"]: p for p in data.get("planets", [])}
        for name, h in scrub["planets"].items():
            if not h["epoch_known"]:
                continue   # pinned at periastron — invent no motion
            np_ = by_name.get(name)
            if np_ is None:
                continue
            x, y = np_["x"], np_["y"]
            h["scatter"].set_offsets([[x, y]])
            r = math.hypot(x, y) or 0.01
            h["label"].set_position(
                (x + x / r * max_au * 0.045, y + y / r * max_au * 0.045))
        scrub["ax"].title.set_text(f"{scrub['title_base']}   ({date_iso})")
        self._readout.setText(f"Map date: {date_iso}")
        self._canvas.draw_idle()


# ── NASA Planetary Systems Map (opt 3 + System Map tab) ──────────────────────

def _show_exoplanet_dialog(parent_widget, planet_info: dict):
    """Non-modal dialog showing pscomppars fields for a clicked exoplanet.

    No network call — all data comes from the planet_info dict already in hand.
    """
    raw = planet_info.get("info") or {}
    name = planet_info.get("name", "Unknown Planet")

    dlg = QDialog(parent_widget)
    dlg.setWindowTitle(f"Planet Info — {name}")
    dlg.setMinimumWidth(540)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.Window)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(12, 12, 12, 8)
    outer.setSpacing(8)

    dist = math.sqrt(planet_info["x"] ** 2 + planet_info["y"] ** 2)
    note = "" if planet_info.get("epoch_known") else \
           "<br/><i>(Epoch unknown &mdash; planet shown at periastron.)</i>"
    hdr = QLabel(
        f"<b>{name}</b>"
        f"<br/>Position on map &mdash; "
        f"X: {planet_info['x']:.4f} AU,  Y: {planet_info['y']:.4f} AU"
        f"<br/>Distance from host star: <b>{dist:.4f} AU</b>"
        + note
    )
    hdr.setWordWrap(True)
    outer.addWidget(hdr)

    sep = QLabel()
    sep.setFrameShape(QLabel.Shape.HLine)
    sep.setFrameShadow(QLabel.Shadow.Sunken)
    outer.addWidget(sep)

    content = QWidget()
    grid = QGridLayout(content)
    grid.setContentsMargins(4, 4, 4, 4)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(4)
    grid.setColumnStretch(1, 1)
    outer.addWidget(content)

    def _add_row(label, value, row):
        lbl = QLabel(f"<b>{label}:</b>")
        val = QLabel(str(value))
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(val, row, 1, Qt.AlignmentFlag.AlignTop)
        return row + 1

    row = 0
    row = _add_row("Host Star", raw.get("hostname", "N/A"), row)

    def _show(key, label, fmt=None, suffix=""):
        nonlocal row
        v = raw.get(key)
        if v is None or str(v).strip() in ("", "nan", "None"):
            return
        try:
            f = float(v)
            if math.isnan(f):
                return
            text = (fmt.format(f) if fmt else str(f))
        except (ValueError, TypeError):
            text = str(v).strip()
        row = _add_row(label, f"{text}{(' ' + suffix) if suffix else ''}", row)

    _show("discoverymethod", "Discovery Method")
    _show("disc_year",       "Discovery Year")
    _show("disc_facility",   "Discovery Facility")
    _show("pl_orbsmax",      "Semi-Major Axis", "{:.4f}", "AU")
    _show("pl_orbeccen",     "Eccentricity",    "{:.4f}")
    _show("pl_orbper",       "Orbital Period",  "{:.4f}", "days")
    _show("pl_orblper",      "Argument of Periastron", "{:.3f}", "°")
    _show("pl_orbincl",      "Inclination",     "{:.3f}", "°")
    _show("pl_orbtper",      "Epoch of Periastron", "{:.4f}", "JD")
    _show("pl_tranmid",      "Transit Mid-point",   "{:.4f}", "JD")
    _show("pl_bmasse",       "Mass",            "{:.3f}", "M⊕")
    _show("pl_bmassj",       "Mass",            "{:.5f}", "M♃")
    _show("pl_rade",         "Radius",          "{:.3f}", "R⊕")
    _show("pl_radj",         "Radius",          "{:.4f}", "R♃")
    _show("pl_dens",         "Density",         "{:.3f}", "g/cm³")
    _show("pl_eqt",          "Equilibrium Temp", "{:.1f}", "K")
    _show("pl_insol",        "Insolation Flux", "{:.3f}", "S⊕")
    _show("pl_controv_flag", "Controversial?")

    close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btn.rejected.connect(dlg.close)
    outer.addWidget(close_btn)

    dlg.adjustSize()
    dlg.show()


class NasaPlanetarySystemsMapPanel(_StarSearchPanel):
    """NASA Exoplanet Archive: Planetary Systems + top-down System Map tab.

    Same data + Hypatia tabs as opt 3, with an added "System Map" diagram
    showing each planet at its date-resolved position on its orbit.
    """

    _placeholder = "e.g. Tau Ceti, HD 10700"

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star System:", self._name)

        self._departure_date = QDateEdit()
        self._departure_date.setDate(QDate.currentDate())
        self._departure_date.setCalendarPopup(True)
        self._departure_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Map Date:", self._departure_date)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._date_lbl = QLabel("")
        self._date_lbl.setVisible(False)
        form.addRow(self._date_lbl)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._result_area = QVBoxLayout(self._scroll_widget)
        self._result_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_widget)
        self._scroll_area = scroll
        self._layout.addWidget(scroll, 1)

        self._viz_container = QWidget()
        self._viz_container.setVisible(False)
        viz_layout = QVBoxLayout(self._viz_container)
        viz_layout.setContentsMargins(4, 4, 4, 4)

        show_tables_row = QHBoxLayout()
        self._show_tables_btn = QPushButton("Show Tables")
        self._show_tables_btn.clicked.connect(self._exit_diagram_mode)
        show_tables_row.addWidget(self._show_tables_btn)
        show_tables_row.addStretch()
        viz_layout.addLayout(show_tables_row)

        self._viz_tabs_widget = QTabWidget()
        self._viz_tabs_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        viz_layout.addWidget(self._viz_tabs_widget, 1)

        self._layout.addWidget(self._viz_container, 1)

    def reset(self):
        self.window.nav_tree.show()
        super().reset()

    def _enter_diagram_mode(self):
        self.window.nav_tree.hide()
        self._form_widget.hide()
        self._scroll_area.hide()
        self._viz_container.show()

    def _exit_diagram_mode(self):
        self.window.nav_tree.show()
        self._form_widget.show()
        self._scroll_area.show()
        self._viz_container.hide()

    def _do_search(self, simbad_result):
        self.set_status("Querying NASA Exoplanet Archive…")
        self.run_in_background(
            _planetary_systems_with_hypatia,
            simbad_result,
            on_result=self._render,
            on_progress=self.set_status,
        )

    def _render(self, result):
        self._exit_diagram_mode()
        self._show_diagrams_btn.setVisible(False)
        self._date_lbl.setVisible(False)
        while self._viz_tabs_widget.count():
            w = self._viz_tabs_widget.widget(0)
            self._viz_tabs_widget.removeTab(0)
            if w:
                w.deleteLater()
        self._clear_results()

        if "error" in result:
            self._show_error(result["error"])
            return

        simbad  = result["simbad"]
        planets = result["planets"]
        hypatia = result.get("hypatia")

        date_iso = self._departure_date.date().toString("yyyy-MM-dd")
        self._date_lbl.setText(f"Map Date: {date_iso}")
        self._date_lbl.setVisible(True)

        _add_simbad_banner(self._result_area, simbad)

        data_tabs = QTabWidget()
        data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        data_w = QWidget()
        data_l = QVBoxLayout(data_w)
        data_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        _add_nasa_tables(self, data_l, simbad, planets)
        _add_hz_table(self, data_l, planets)
        data_tabs.addTab(data_w, "Data")

        if hypatia is not None:
            data_tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")

        self._result_area.addWidget(data_tabs)

        star_name = str(planets[0].get("hostname") or "") if planets else ""

        # System Map tab — planets at date-resolved positions, with the Phase O
        # O5 date scrubber (slider + Play/Pause) driving offline recomputes.
        if mpl_available():
            sys_data = core.viz.prepare_exoplanet_system_diagram(planets, date_iso)
            if "error" not in sys_data:
                if not sys_data.get("star_name"):
                    sys_data["star_name"] = star_name
                scrubber = _SystemMapScrubber(
                    self, sys_data, planets, date_iso,
                    on_planet_click=lambda pi: _show_exoplanet_dialog(self, pi),
                )
                self._viz_tabs_widget.addTab(scrubber, "System Map")

        # Carry over the existing Orbital Diagram + HZ Diagram tabs
        orb_w = _make_orbits_tab(
            self, planets, star_name,
            sp_type=(planets[0].get("st_spectype") if planets else None))
        if orb_w:
            self._viz_tabs_widget.addTab(orb_w, "Orbital Diagram")
        hz_w = _make_hz_tab(self, planets)
        if hz_w:
            self._viz_tabs_widget.addTab(hz_w, "HZ Diagram")
        mr_w = _make_mass_radius_tab(self, planets)
        if mr_w:
            self._viz_tabs_widget.addTab(mr_w, "Mass–Radius")
        tg_w = _make_transit_tab(self, planets)
        if tg_w:
            self._viz_tabs_widget.addTab(tg_w, "Transit Geometry")
        sz_w = _make_size_tab(self, planets)
        if sz_w:
            self._viz_tabs_widget.addTab(sz_w, "Size Comparison")

        if hypatia and "error" not in hypatia:
            try:
                ab_data = core.viz.prepare_abundance_profile(hypatia)
                if "error" not in ab_data:
                    ab_canvas, ab_toolbar = make_abundance_canvas(
                        None, ab_data, hypatia.get("star_name", "")
                    )
                    if ab_canvas is not None:
                        ab_w = wrap_scrollable(None, ab_canvas, ab_toolbar)
                        self._viz_tabs_widget.addTab(ab_w, "Abundance Profile")
            except Exception:
                log_viz_error("Abundance Profile")

            try:
                kin_w = make_kinematics_tab(hypatia)
                if kin_w is not None:
                    self._viz_tabs_widget.addTab(kin_w, "Kinematics")
            except Exception:
                log_viz_error("Kinematics")

        if self._viz_tabs_widget.count() > 0:
            self._show_diagrams_btn.setVisible(True)
