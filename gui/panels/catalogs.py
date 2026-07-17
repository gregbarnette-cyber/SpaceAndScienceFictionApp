# gui/panels/catalogs.py — Option 6: HWC.
#
#   HwcPanel  — option 6 (Habitable Worlds Catalog)

import math
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QTabWidget, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QComboBox,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
from gui.panels.hypatia_tab import build_hypatia_tab
import core.databases
import core.viz
import core.science
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_orbits_canvas, make_abundance_canvas, wrap_scrollable,
    make_kinematics_tab, make_hwc_temp_canvas, make_hwc_esi_canvas,
    make_mass_radius_canvas, make_size_comparison_canvas, wrap_orbits_with_solar_toggle,
    log_viz_error,
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


def _hwc_with_hypatia(simbad_result: dict) -> dict:
    result = core.databases.compute_hwc(simbad_result)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(simbad_result)
    return result


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
            _hwc_with_hypatia,
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
        hypatia     = result.get("hypatia")

        self._result_area.addWidget(
            QLabel(f"<b>SIMBAD:</b> {simbad.get('desig_str', 'N/A')}")
        )

        # ── Data / Hypatia tabs ───────────────────────────────────────────────
        data_tabs = QTabWidget()
        data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        data_w = QWidget()
        data_l = QVBoxLayout(data_w)
        data_l.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        data_l.addWidget(QLabel("<b>Star Properties</b>"))
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
        data_l.addWidget(t)

        # Star Habitability Properties
        data_l.addWidget(QLabel("<b>Star Habitability Properties</b>"))
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
        data_l.addWidget(t)

        # Planet Properties
        data_l.addWidget(QLabel("<b>Planet Properties</b>"))
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
        data_l.addWidget(t)

        # Planet Habitability Properties
        data_l.addWidget(QLabel("<b>Planet Habitability Properties</b>"))
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
        data_l.addWidget(t)

        # Planet Temperature Properties
        data_l.addWidget(QLabel("<b>Planet Temperature Properties</b>"))
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
        data_l.addWidget(t)

        _add_hz(self, data_l,
                star_row.get("S_TEMPERATURE"), None, star_row.get("S_RADIUS"))

        data_tabs.addTab(data_w, "Data")
        if hypatia is not None:
            data_tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")
        self._result_area.addWidget(data_tabs)

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
            _hl = core.science.compute_hyper_limit_for_spectral_type(
                str(star_row.get("S_TYPE", "")))
            hyper_au = _hl["au"] if _hl else None

            # Phase P V6/V7: host luminosity → snow-line + solvent-zone overlays.
            def _hwc_lum():
                for k in ("S_LUMINOSITY",):
                    try:
                        v = float(star_row.get(k) or 0)
                        if v > 0:
                            return v
                    except (ValueError, TypeError):
                        pass
                try:
                    r = float(star_row.get("S_RADIUS") or 0)
                    t = float(star_row.get("S_TEMPERATURE") or 0)
                    if r > 0 and t > 0:
                        return r ** 2 * (t / 5778.0) ** 4
                except (ValueError, TypeError):
                    pass
                return None

            ov = core.viz.prepare_orbit_overlays(_hwc_lum())
            snow_au = ov.get("snow_au")
            solvent_options = ov.get("solvent_options")

            def _build_orbits(solar_overlay, show_hyper, snow, solvent_bands):
                return make_orbits_canvas(
                    self,
                    orbit_data["orbits"],
                    orbit_data.get("hz_zones", []),
                    orbit_data["max_au"],
                    star_name=str(star_row.get("S_NAME", "")),
                    markers=markers_arg,
                    solar_overlay=solar_overlay,
                    hyper_au=hyper_au if show_hyper else None,
                    snow_au=snow,
                    solvent_bands=solvent_bands,
                )
            orb_w = wrap_orbits_with_solar_toggle(
                self, _build_orbits, hyper_au=hyper_au,
                snow_au=snow_au, solvent_options=solvent_options)
            if orb_w is not None:
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

        # Mass–Radius diagram (Phase O · O3) — only when ≥1 planet has M and R.
        if mpl_available():
            mr_data = core.viz.prepare_mass_radius(
                planet_rows, "P_MASS", "P_RADIUS", "P_NAME")
            if "error" not in mr_data:
                mr_canvas, mr_toolbar = make_mass_radius_canvas(self, mr_data)
                if mr_canvas is not None:
                    mr_w = QWidget()
                    mr_l = QVBoxLayout(mr_w)
                    mr_l.setContentsMargins(4, 4, 4, 4)
                    mr_l.addWidget(mr_toolbar)
                    mr_l.addWidget(mr_canvas)
                    self._viz_tabs_widget.addTab(mr_w, "Mass–Radius")

        # Planet Size-Comparison strip (Phase O · O14) — only when ≥1 planet has R.
        if mpl_available():
            sz_canvas, sz_toolbar = make_size_comparison_canvas(
                self, planet_rows, "P_RADIUS", "P_NAME")
            if sz_canvas is not None:
                sz_w = QWidget()
                sz_l = QVBoxLayout(sz_w)
                sz_l.setContentsMargins(4, 4, 4, 4)
                sz_l.addWidget(sz_toolbar)
                sz_l.addWidget(sz_canvas)
                self._viz_tabs_widget.addTab(sz_w, "Size Comparison")

        # HWC habitability visuals (Phase O · O12) — per-system temperature ranges
        # and ESI-vs-orbit; each tab appears only when ≥1 planet qualifies.
        if mpl_available():
            try:
                tr_data = core.viz.prepare_hwc_temps(planet_rows)
                if "error" not in tr_data:
                    tr_canvas, tr_toolbar = make_hwc_temp_canvas(None, tr_data)
                    if tr_canvas is not None:
                        tr_w = wrap_scrollable(None, tr_canvas, tr_toolbar)
                        self._viz_tabs_widget.addTab(tr_w, "Temperature Ranges")
            except Exception:
                log_viz_error("Temperature Ranges")
            try:
                es_data = core.viz.prepare_hwc_esi(star_row, planet_rows)
                if "error" not in es_data:
                    es_canvas, es_toolbar = make_hwc_esi_canvas(self, es_data)
                    if es_canvas is not None:
                        es_w = QWidget()
                        es_l = QVBoxLayout(es_w)
                        es_l.setContentsMargins(4, 4, 4, 4)
                        es_l.addWidget(es_toolbar)
                        es_l.addWidget(es_canvas)
                        self._viz_tabs_widget.addTab(es_w, "ESI vs Orbit")
            except Exception:
                log_viz_error("ESI vs Orbit")

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


# ── Option 7: Open Exoplanet Catalogue ───────────────────────────────────────

from core.databases import (oec_fv as _oec_fv, oec_format_field as _oec_fmt,
                            oec_statuses as _oec_statuses, oec_binary_label as _oec_binary_label)

# Per-node headline field keys + display units (GUI). Any field may repeat — the
# shared _oec_fv/_oec_fmt handle that (PHASE_OEC_PLAN.md §F.1).
_OEC_TREE_KEYS = {
    "binary":    [("separation", "sep", ""), ("semimajoraxis", "a", "AU"),
                  ("eccentricity", "e", ""), ("period", "P", "d"),
                  ("inclination", "i", "°")],
    "star":      [("mass", "M", "M_sun"), ("radius", "R", "R_sun"),
                  ("temperature", "T", "K"), ("metallicity", "[Fe/H]", ""),
                  ("age", "age", "Gyr")],
    "planet":    [("mass", "M", "M_jup"), ("radius", "R", "R_jup"),
                  ("period", "P", "d"), ("semimajoraxis", "a", "AU"),
                  ("eccentricity", "e", ""), ("inclination", "i", "°")],
    "satellite": [("mass", "M", "M_earth"), ("radius", "R", "R_earth"),
                  ("semimajoraxis", "a", "AU"), ("period", "P", "d")],
}
_OEC_TREE_PREFIX = {"system": "◆", "binary": "⋔", "star": "★",
                    "planet": "●", "satellite": "☾"}


def _oec_tree_bits(node):
    """`label=value unit` fragments for a node's headline fields."""
    f, tag = node["fields"], node["tag"]
    bits = []
    for key, label, unit in _OEC_TREE_KEYS.get(tag, []):
        if not f.get(key):
            continue
        if key == "mass" and tag == "planet":
            fv = _oec_fv(f["mass"])
            if fv and fv.get("type") == "msini":
                label = "M·sin i"
        bits.append(f"{label}={_oec_fmt(f[key], unit)}")
    return bits


def _oec_tree_item(node):
    """Build a QTreeWidgetItem (col 0 = name, col 1 = properties) for an OEC node."""
    tag = node["tag"]
    prefix = _OEC_TREE_PREFIX.get(tag, "")
    if tag == "system":
        name = node["names"][0] if node.get("names") else "System"
        extra = []
        if node["fields"].get("constellation"):
            extra.append(_oec_fv(node["fields"]["constellation"])["value"])
        if node["fields"].get("distance"):
            extra.append("d=" + _oec_fmt(node["fields"]["distance"], "pc"))
        detail = " · ".join(extra)
    elif tag == "binary":
        name = _oec_binary_label(node)
        detail = "   ".join(_oec_tree_bits(node))
    elif tag == "star":
        base = node["names"][0] if node.get("names") else "Star"
        sp = _oec_fv(node["fields"]["spectraltype"])["value"] if node["fields"].get("spectraltype") else ""
        name = f"{base}  {sp}".strip()
        detail = "   ".join(_oec_tree_bits(node))
        if not node.get("children"):
            detail = (detail + "   ") if detail else ""
            detail += "(no planets catalogued)"
    elif tag == "satellite":
        name = node["names"][0] if node.get("names") else "Moon"
        detail = "   ".join(_oec_tree_bits(node))
    else:  # planet
        base = node["names"][0] if node.get("names") else "Planet"
        statuses = _oec_statuses(node["fields"])
        name = f"{base}  [{' / '.join(statuses)}]" if statuses else base
        detail = "   ".join(_oec_tree_bits(node))

    item = QTreeWidgetItem([f"{prefix} {name}".strip(), detail])
    for child in node.get("children", []):
        item.addChild(_oec_tree_item(child))
    return item


# ── Phase 2: Star-Databases parity (Hypatia + per-host diagrams) ──────────────
# Reuse the shared diagram-tab builders + the Hypatia path verbatim; the only new code
# is the OEC-node → NASA-key adapter and the OEC-star → Hypatia compat dict.
from gui.panels.diagram_tabs import (
    _make_hz_tab, _make_orbits_tab, _make_mass_radius_tab,
    _make_transit_tab, _make_size_tab,
)

_MJUP_MEARTH = 317.828   # M_jup → M_earth
_RJUP_REARTH = 11.209    # R_jup → R_earth


def _oec_num(field):
    """Numeric value of a (possibly repeated) OEC field, or None."""
    fv = _oec_fv(field)
    if fv is None:
        return None
    try:
        return float(fv.get("value"))
    except (TypeError, ValueError):
        return None


def _oec_collect_hosts(system):
    """Planet-bearing nodes → host descriptors. A host is a star (normal), a binary
    (circumbinary/P-type — §F.7 pseudo-host), or the system itself (rogue)."""
    hosts = []

    def walk(n):
        planets = [c for c in n.get("children", []) if c["tag"] == "planet"]
        if planets and n["tag"] in ("star", "binary", "system"):
            name = (n["names"][0] if n.get("names")
                    else (_oec_binary_label(n) if n["tag"] == "binary" else "System"))
            hosts.append({"node": n, "kind": n["tag"], "name": name, "planets": planets})
        for c in n.get("children", []):
            walk(c)

    walk(system)
    return hosts


def _oec_host_star(host):
    """The star providing teff/radius/spectral/Hypatia for a host: the star itself, a
    binary's first component star (recursing), or None for a rogue (system) host."""
    node = host["node"]
    if node["tag"] == "star":
        return node
    if node["tag"] == "binary":
        for c in node.get("children", []):
            if c["tag"] == "star":
                return c
            if c["tag"] == "binary":
                s = _oec_host_star({"node": c})
                if s:
                    return s
    return None


def _oec_host_to_nasa(host):
    """Convert a host's planets → NASA-key planet dicts (with Jupiter→Earth unit
    conversion) so the reused diagram builders work unchanged. Returns (planets, sp_type)."""
    star = _oec_host_star(host)
    teff = _oec_num(star["fields"].get("temperature")) if star else None
    st_rad = _oec_num(star["fields"].get("radius")) if star else None
    sp = (_oec_fv(star["fields"].get("spectraltype")) or {}).get("value") if star else None
    planets = []
    for p in host["planets"]:
        f = p["fields"]
        mj, rj = _oec_num(f.get("mass")), _oec_num(f.get("radius"))
        planets.append({
            "pl_name": p["names"][0] if p.get("names") else "?",
            "pl_orbsmax": _oec_num(f.get("semimajoraxis")),
            "pl_orbeccen": _oec_num(f.get("eccentricity")),
            "pl_orbincl": _oec_num(f.get("inclination")),
            "pl_bmasse": mj * _MJUP_MEARTH if mj is not None else None,
            "pl_rade": rj * _RJUP_REARTH if rj is not None else None,
            "st_teff": teff, "st_rad": st_rad, "st_spectype": sp, "hostname": host["name"],
        })
    return planets, sp


def _oec_hypatia_for(host):
    """Hypatia Catalog data for a host's star, resolved from its OEC designations.
    None for a rogue (no star); {"error"} on lookup failure (rendered gracefully)."""
    star = _oec_host_star(host)
    if star is None:
        return None
    desig = {}
    for nm in star.get("names", []):
        for key, pat in (("HIP", r"^HIP\s*(\d+)"), ("HD", r"^HD\s*(\d+)"),
                         ("GJ", r"^(?:GJ|Gliese)\s*([\d.]+)"), ("HR", r"^HR\s*(\d+)")):
            m = re.match(pat, nm)
            if m and key not in desig:
                desig[key] = nm
    if not desig:
        return {"error": "No catalogue designation (HD/HIP/GJ/HR) for a Hypatia lookup."}
    return core.databases.compute_hypatia_data(
        {"designations": desig, "main_id": star["names"][0] if star.get("names") else ""})


def _oec_with_hypatia(name):
    """Background: resolve the system, then pre-fetch Hypatia for every host (usually
    1–3 stars) so switching the host selector is instant."""
    result = core.databases.compute_oec(name)
    if "error" in result:
        return result
    hosts = _oec_collect_hosts(result["system"])
    result["_hypatia"] = {h["name"]: _oec_hypatia_for(h) for h in hosts}
    return result


class OecPanel(DiagramToggleMixin, _StarSearchPanel):
    """Option 7 — Open Exoplanet Catalogue. Renders a star system's full hierarchy
    (system → binary → star → planet → satellite) as a tree, plus per-host Hypatia +
    diagram tabs (Phase 2). Resolution is direct-alias-first with a SIMBAD fallback."""

    _placeholder = "e.g. Alpha Centauri, HD 186408, Kepler-16 b"

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._placeholder)
        self._name.returnPressed.connect(self._search)
        form.addRow("Star / Planet Name:", self._name)

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

    def _search(self):
        name = self._name.text().strip()
        if not name:
            return
        self._clear_results()
        self.set_status("Searching the Open Exoplanet Catalogue…")
        self.run_in_background(_oec_with_hypatia, name, on_result=self._on_oec_result)

    def _on_oec_result(self, result):
        self._prepare_render()
        self._clear_results()
        if "error" in result:
            self._show_error(result["error"])
            return

        self._oec_hosts = _oec_collect_hosts(result["system"])
        self._oec_hypatia = result.get("_hypatia", {})

        if result.get("matched_name"):
            hdr = QLabel(f"Matched on: <b>{result['matched_name']}</b>")
            hdr.setTextFormat(Qt.TextFormat.RichText)
            self._result_area.addWidget(hdr)

        if len(self._oec_hosts) > 1:
            sel_w = QWidget()
            sel_l = QHBoxLayout(sel_w)
            sel_l.setContentsMargins(0, 0, 0, 0)
            sel_l.addWidget(QLabel("Host (diagrams &amp; Hypatia):"))
            self._host_combo = QComboBox()
            self._host_combo.addItems([h["name"] for h in self._oec_hosts])
            self._host_combo.currentIndexChanged.connect(self._on_host_changed)
            sel_l.addWidget(self._host_combo)
            sel_l.addStretch()
            self._result_area.addWidget(sel_w)
        else:
            self._host_combo = None

        self._data_tabs = QTabWidget()
        self._data_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tree = QTreeWidget()
        tree.setHeaderLabels(["System / Component / Planet", "Properties"])
        tree.setColumnWidth(0, 340)
        tree.setAlternatingRowColors(True)
        tree.addTopLevelItem(_oec_tree_item(result["system"]))
        tree.expandAll()
        tree.setMinimumHeight(360)
        self._data_tabs.addTab(tree, "Data")
        self._result_area.addWidget(self._data_tabs, 1)

        if self._oec_hosts:
            self._render_host(0)
        self._finish_render()

    def _on_host_changed(self, idx):
        # Drop the previous host's Hypatia data-tab (keep Data at index 0) + viz tabs.
        while self._data_tabs.count() > 1:
            w = self._data_tabs.widget(1)
            self._data_tabs.removeTab(1)
            if w:
                w.deleteLater()
        self._clear_viz_tabs()
        self._render_host(idx)
        self._finish_render()

    def _render_host(self, idx):
        host = self._oec_hosts[idx]
        hyp = self._oec_hypatia.get(host["name"])

        if hyp is not None:
            self._data_tabs.addTab(build_hypatia_tab(hyp), "Hypatia")

        planets, sp = _oec_host_to_nasa(host)
        builders = [
            (lambda: _make_orbits_tab(self, planets, host["name"], sp), "Orbital Diagram"),
            (lambda: _make_hz_tab(self, planets), "HZ Diagram"),
            (lambda: _make_mass_radius_tab(self, planets), "Mass–Radius"),
            (lambda: _make_transit_tab(self, planets), "Transit Geometry"),
            (lambda: _make_size_tab(self, planets), "Size Comparison"),
        ]
        for build, title in builders:
            try:
                w = build()
                if w:
                    self._viz_tabs_widget.addTab(w, title)
            except Exception:
                log_viz_error(title)

        if hyp and "error" not in hyp:
            try:
                ab = core.viz.prepare_abundance_profile(hyp)
                if "error" not in ab:
                    canvas, toolbar = make_abundance_canvas(None, ab, hyp.get("star_name", ""))
                    if canvas is not None:
                        self._viz_tabs_widget.addTab(
                            wrap_scrollable(None, canvas, toolbar), "Abundance Profile")
            except Exception:
                log_viz_error("Abundance Profile")
            try:
                kin_w = make_kinematics_tab(hyp)
                if kin_w is not None:
                    self._viz_tabs_widget.addTab(kin_w, "Kinematics")
            except Exception:
                log_viz_error("Kinematics")
