# gui/panels/catalogs.py — Options 6, 7: HWC, OEC.
#
# Each option is its own standalone panel class:
#   HwcPanel  — option 6 (Habitable Worlds Catalog)
#   OecPanel  — option 7 (Open Exoplanet Catalogue)

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QTabWidget, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.databases
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_orbits_canvas,
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


def _fit_table_height(view) -> None:
    """Fix a QTableView's height to exactly its rows + header, no internal scrollbar."""
    h = (view.horizontalHeader().sizeHint().height()
         + view.verticalHeader().defaultSectionSize() * view.model().rowCount()
         + 2)
    view.setFixedHeight(h)


def _add_hz(panel, layout, teff, lum_log=None, rad=None):
    hz = core.databases.compute_habitable_zone(teff, lum_log, rad)
    if not hz:
        return
    layout.addWidget(QLabel("<b>Calculated Habitable Zone</b>"))
    rows = [[name, f"{au:.3f} ({au * 8.3167:.3f} LM)"] for name, au in hz]
    t = panel.make_table(["Zone", "AU (Light Minutes)"], rows)
    t.setSortingEnabled(False)
    _fit_table_height(t)
    layout.addWidget(t)


# ── Shared base class for single-star-search panels ──────────────────────────

class _StarSearchPanel(ResultPanel):
    """Base class for catalog panels that do a SIMBAD lookup then a data query."""

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


# ── Option 6: Habitable Worlds Catalog ───────────────────────────────────────

class HwcPanel(DiagramToggleMixin, _StarSearchPanel):
    """Habitable Worlds Catalog — option 6."""

    _placeholder = "e.g. Tau Ceti, HD 10700, GJ 667C"

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
        self.set_status("Querying Habitable Worlds Catalog…")
        self.run_in_background(
            core.databases.compute_hwc,
            simbad_result,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._prepare_render()
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        simbad      = result["simbad"]
        star_row    = result["star_row"]
        planet_rows = result["planet_rows"]

        self._result_area.addWidget(
            QLabel(f"<b>SIMBAD:</b> {simbad.get('desig_str', 'N/A')}")
        )

        def _sf(key, dp=None):
            v = star_row.get(key, "")
            if v in (None, ""):
                return "N/A"
            try:
                f = float(v)
                return f"{f:.{dp}f}" if dp is not None else str(int(f))
            except ValueError:
                return str(v).strip()

        # Star Properties
        self._result_area.addWidget(QLabel("<b>Star Properties</b>"))
        st_dist = _fval(star_row.get("S_DISTANCE"))
        s_headers = ["Star", "HD", "HIP", "Spectral Type", "MagV", "L",
                     "Temp", "Mass", "Radius", "RA", "DEC", "Parsecs", "LY",
                     "Fe/H", "Age"]
        s_row = [
            _sf("S_NAME"), _sf("S_NAME_HD"), _sf("S_NAME_HIP"),
            _sf("S_TYPE"),
            _sf("S_MAG", 5), _sf("S_LUMINOSITY", 5),
            _sf("S_TEMPERATURE"), _sf("S_MASS", 2), _sf("S_RADIUS", 2),
            _sf("S_RA", 4), _sf("S_DEC", 4),
            _sf("S_DISTANCE", 5),
            f"{st_dist * 3.26156:.4f}" if st_dist is not None else "N/A",
            _sf("S_METALLICITY", 3), _sf("S_AGE", 2),
        ]
        t = self.make_table(s_headers, [s_row])
        _fit_table_height(t)
        self._result_area.addWidget(t)

        # Star Habitability Properties
        self._result_area.addWidget(QLabel("<b>Star Habitability Properties</b>"))
        sh_headers = ["Inner Opt HZ", "Inner Con HZ", "Outer Con HZ",
                      "Outer Opt HZ", "Inner Con 5 Me HZ", "Outer Con 5 Me HZ",
                      "Tidal Lock", "Abiogenesis", "Snow Line"]
        sh_row = [
            _sf("S_HZ_OPT_MIN", 6), _sf("S_HZ_CON_MIN", 6),
            _sf("S_HZ_CON_MAX", 6), _sf("S_HZ_OPT_MAX", 6),
            _sf("S_HZ_CON1_MIN", 6), _sf("S_HZ_CON1_MAX", 6),
            _sf("S_TIDAL_LOCK"), _sf("S_ABIO_ZONE"), _sf("S_SNOW_LINE"),
        ]
        t = self.make_table(sh_headers, [sh_row])
        _fit_table_height(t)
        self._result_area.addWidget(t)

        # Planet Properties
        self._result_area.addWidget(QLabel("<b>Planet Properties</b>"))
        pp_headers = ["Planet", "Mass E", "Radius E", "Orbit", "SMA",
                      "Eccentricity", "Density", "Potential", "Gravity", "Escape"]
        pp_rows = []
        for p in planet_rows:
            def _pf(key, dp=None, _p=p):
                v = _p.get(key, "")
                if v in (None, ""):
                    return "N/A"
                try:
                    f = float(v)
                    return f"{f:.{dp}f}" if dp is not None else str(f)
                except ValueError:
                    return str(v).strip()
            pp_rows.append([
                _pf("P_NAME"), _pf("P_MASS", 2), _pf("P_RADIUS", 2),
                _pf("P_PERIOD", 2), _pf("P_SEMI_MAJOR_AXIS", 4),
                _pf("P_ECCENTRICITY", 2), _pf("P_DENSITY", 4),
                _pf("P_POTENTIAL", 5), _pf("P_GRAVITY", 5), _pf("P_ESCAPE", 5),
            ])
        t = self.make_table(pp_headers, pp_rows)
        _fit_table_height(t)
        self._result_area.addWidget(t)

        # Planet Habitability Properties
        self._result_area.addWidget(QLabel("<b>Planet Habitability Properties</b>"))
        ph_headers = ["Planet Type", "EFF Dist", "Periastron", "Apastron",
                      "Temp Type", "Hill Sphere", "Habitable?", "ESI",
                      "In HZ Con", "In HZ Opt"]
        ph_rows = []
        for p in planet_rows:
            def _pflag(key, _p=p):
                v = str(_p.get(key, "")).strip()
                return "Yes" if v == "1" else ("No" if v == "0" else v)
            def _pf2(key, dp=None, _p=p):
                v = _p.get(key, "")
                if v in (None, ""):
                    return "N/A"
                try:
                    f = float(v)
                    return f"{f:.{dp}f}" if dp is not None else str(f)
                except ValueError:
                    return str(v).strip()
            ph_rows.append([
                _pf2("P_TYPE"), _pf2("P_DISTANCE_EFF", 5),
                _pf2("P_PERIASTRON", 5), _pf2("P_APASTRON", 5),
                _pf2("P_TYPE_TEMP"), _pf2("P_HILL_SPHERE", 8),
                _pflag("P_HABITABLE"), _pf2("P_ESI", 6),
                _pflag("P_HABZONE_CON"), _pflag("P_HABZONE_OPT"),
            ])
        t = self.make_table(ph_headers, ph_rows)
        _fit_table_height(t)
        self._result_area.addWidget(t)

        # Planet Temperature Properties
        self._result_area.addWidget(QLabel("<b>Planet Temperature Properties</b>"))
        pt_headers = ["Flux Min", "Flux", "Flux Max",
                      "EQ Min", "EQ", "EQ Max",
                      "Surf Min", "Surf", "Surf Max"]
        pt_rows = []
        for p in planet_rows:
            def _ptf(key, dp=3, _p=p):
                v = _p.get(key, "")
                if v in (None, ""):
                    return "N/A"
                try:
                    return f"{float(v):.{dp}f}"
                except ValueError:
                    return str(v).strip()
            pt_rows.append([
                _ptf("P_FLUX_MIN", 5), _ptf("P_FLUX", 5), _ptf("P_FLUX_MAX", 5),
                _ptf("P_TEMP_EQUIL_MIN", 3), _ptf("P_TEMP_EQUIL", 3),
                _ptf("P_TEMP_EQUIL_MAX", 3),
                _ptf("P_TEMP_SURF_MIN", 3), _ptf("P_TEMP_SURF", 3),
                _ptf("P_TEMP_SURF_MAX", 3),
            ])
        t = self.make_table(pt_headers, pt_rows)
        _fit_table_height(t)
        self._result_area.addWidget(t)

        _add_hz(self, self._result_area,
                star_row.get("S_TEMPERATURE"), None, star_row.get("S_RADIUS"))

        if not mpl_available():
            self._finish_render()
            return

        # ── Viz tabs ──────────────────────────────────────────────────────────
        hwc_planets = []
        for p in planet_rows:
            hwc_planets.append({
                "pl_name":    p.get("P_NAME", ""),
                "pl_orbsmax": p.get("P_SEMI_MAJOR_AXIS"),
                "pl_orbeccen":p.get("P_ECCENTRICITY"),
                "st_teff":    star_row.get("S_TEMPERATURE"),
                "st_rad":     star_row.get("S_RADIUS"),
            })

        orbit_data  = core.viz.prepare_system_orbits(hwc_planets) if hwc_planets else {}
        teff_v      = _fval(star_row.get("S_TEMPERATURE")) or 0
        lum_v       = _fval(star_row.get("S_LUMINOSITY"))  or 0
        hz_data_viz = core.viz.prepare_hz_diagram(teff_v, lum_v) if teff_v else {}

        # Build markers shared by both diagrams
        hwc_markers = []
        tidal_lock = _fval(star_row.get("S_TIDAL_LOCK"))
        abio_zone  = _fval(star_row.get("S_ABIO_ZONE"))
        snow_line  = _fval(star_row.get("S_SNOW_LINE"))
        if tidal_lock and tidal_lock > 0:
            hwc_markers.append({
                "label": "Tidal Lock", "au": tidal_lock, "color": "#CC6600",
                "body": "Distance at which a planet would be tidally\nlocked to its host star.",
            })
        if abio_zone and abio_zone > 0:
            hwc_markers.append({
                "label": "Abiogenesis Zone", "au": abio_zone, "color": "#00AACC",
                "body": "Outer boundary of the abiogenesis zone —\nfavourable conditions for the origin of life.",
            })
        if snow_line and snow_line > 0:
            hwc_markers.append({
                "label": "Snow Line", "au": snow_line, "color": "#AAAAFF",
                "body": "Distance at which water ice condenses\nin the protoplanetary disk.",
            })
        markers_arg = hwc_markers if hwc_markers else None

        if "orbits" in orbit_data:
            orb_w = QWidget()
            orb_l = QVBoxLayout(orb_w)
            orb_l.setContentsMargins(4, 4, 4, 4)
            canvas, toolbar = make_orbits_canvas(
                self,
                orbit_data["orbits"],
                orbit_data.get("hz_zones", []),
                orbit_data["max_au"],
                star_name=str(star_row.get("S_NAME", "")),
                markers=markers_arg,
            )
            orb_l.addWidget(toolbar)
            orb_l.addWidget(canvas)
            self._viz_tabs_widget.addTab(orb_w, "Orbital Diagram")

        if "zones" in hz_data_viz:
            hz_w = QWidget()
            hz_l = QVBoxLayout(hz_w)
            hz_l.setContentsMargins(4, 4, 4, 4)
            canvas, toolbar = make_hz_canvas(
                self,
                hz_data_viz["zones"],
                hz_data_viz["max_au"],
                title=f"Habitable Zone  (T={teff_v:.0f} K, L={lum_v:.4f} L☉)",
                markers=markers_arg,
            )
            hz_l.addWidget(toolbar)
            hz_l.addWidget(canvas)
            self._viz_tabs_widget.addTab(hz_w, "HZ Diagram")

        self._finish_render()


# ── Option 7: Open Exoplanet Catalogue ───────────────────────────────────────

class OecPanel(_StarSearchPanel):
    """Open Exoplanet Catalogue — option 7."""

    _placeholder = "e.g. WASP-94, HD 189733, Kepler-22"

    def _do_search(self, simbad_result):
        self.set_status("Querying Open Exoplanet Catalogue…")
        self.run_in_background(
            core.databases.compute_oec,
            simbad_result,
            on_result=self._render,
            on_progress=self.set_status,
        )

    def _render(self, result: dict):
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        simbad = result["simbad"]
        stars  = result["stars"]

        self._result_area.addWidget(
            QLabel(f"<b>SIMBAD:</b> {simbad.get('desig_str', 'N/A')}")
        )

        for star in stars:
            names = star.get("names", [])
            star_label = names[0] if names else "Unknown"
            if len(names) > 1:
                star_label += f"  ({', '.join(names[1:4])})"
            self._result_area.addWidget(QLabel(f"<b>Star: {star_label}</b>"))

            def _sf(key, dp=None, _s=star):
                v = _s.get(key)
                if v is None:
                    return "N/A"
                if dp is not None:
                    try:
                        return f"{float(v):.{dp}f}"
                    except (ValueError, TypeError):
                        pass
                return str(v)

            # Star Properties
            self._result_area.addWidget(QLabel("<b>Star Properties</b>"))
            dist = _fval(star.get("dist"))
            s_headers = ["Spectral Type", "MagV", "Temp", "Mass", "Radius",
                         "Fe/H", "Age", "Parsecs", "LYs"]
            temp_val = _fval(star.get("temp"))
            s_row = [
                _sf("spec"), _sf("magv", 3),
                str(int(temp_val)) if temp_val is not None else "N/A",
                _sf("mass", 3), _sf("radius", 3),
                _sf("met", 3), _sf("age", 2),
                _sf("dist", 4),
                f"{dist * 3.26156:.4f}" if dist is not None else "N/A",
            ]
            self._result_area.addWidget(self.make_table(s_headers, [s_row]))

            # Planet Properties
            planets = star.get("planets", [])
            if planets:
                self._result_area.addWidget(QLabel("<b>Planet Properties</b>"))
                STATUS_MAP = {
                    "Confirmed planets": "Confirmed",
                    "Controversial": "Controversial",
                    "Retracted planet candidate": "Retracted",
                    "Solar System": "Solar Sys",
                    "Kepler Objects of Interest": "KOI",
                    "Planets in binary systems, S-type": "Binary S",
                }
                p_headers = ["#", "Planet Name", "Mass (J)", "Mass (E)",
                             "Rad (J)", "Rad (E)", "Period", "Distance",
                             "Eccentricity", "Temp", "Method", "Year", "Status"]
                p_rows = []
                for idx, p in enumerate(planets, 1):
                    def _pf(key, dp=None, _p=p):
                        v = _p.get(key)
                        if v is None:
                            return "N/A"
                        if dp is not None:
                            try:
                                return f"{float(v):.{dp}f}"
                            except (ValueError, TypeError):
                                pass
                        return str(v)
                    sma = _fval(p.get("sma"))
                    ecc = _fval(p.get("ecc"))
                    if sma is not None and ecc is not None:
                        ea = sma * ecc
                        dist_s = f"{sma - ea:.3f} - {sma:.3f} - {sma + ea:.3f} AU"
                    elif sma is not None:
                        dist_s = f"N/A - {sma:.3f} - N/A AU"
                    else:
                        dist_s = "N/A"
                    mass_j = _fval(p.get("mass_j"))
                    mass_e = f"{mass_j * 317.8:.2f}" if mass_j is not None else "N/A"
                    rad_j  = _fval(p.get("rad_j"))
                    rad_e  = f"{rad_j * 11.2:.2f}" if rad_j is not None else "N/A"
                    t_val  = _fval(p.get("temp"))
                    temp_s = str(int(t_val)) if t_val is not None else "N/A"
                    status = STATUS_MAP.get(p.get("status", ""), p.get("status", "N/A"))
                    p_rows.append([
                        str(idx), _pf("name"),
                        _pf("mass_j", 4), mass_e,
                        _pf("rad_j",  4), rad_e,
                        _pf("period", 3), dist_s,
                        _pf("ecc",    3), temp_s,
                        _pf("method"), _pf("year"), status,
                    ])
                self._result_area.addWidget(self.make_table(p_headers, p_rows))

            _add_hz(self, self._result_area,
                    star.get("temp"), None, star.get("radius"))


