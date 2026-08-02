# gui/panels/catalogs.py — Option 6: HWC.
#
#   HwcPanel  — option 6 (Habitable Worlds Catalog)

import math
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QTabWidget, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QComboBox, QHeaderView, QSplitter, QCheckBox,
    QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QTimer

from gui.panels.base import (
    ResultPanel, DiagramToggleMixin, add_designation_names_line, add_gould_line,
)
from gui.panels.hypatia_tab import build_hypatia_tab
import core.databases
import core.viz
import core.science
import core.oec_derived
import core.equations
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_orbits_canvas, make_abundance_canvas, wrap_scrollable,
    make_kinematics_tab, make_hwc_temp_canvas, make_hwc_esi_canvas,
    make_mass_radius_canvas, make_size_comparison_canvas, wrap_orbits_with_solar_toggle,
    make_oec_architecture_canvas, log_viz_error,
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
        names_line = add_designation_names_line(self._result_area, simbad)  # AN3 — no-op
        add_gould_line(self._result_area, simbad, inline_with=names_line)   # AO3 — same line

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
            _sf("S_TIDAL_LOCK", 6), _sf("S_ABIO_ZONE", 6), _sf("S_SNOW_LINE", 6),
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
            # HZ Diagram — Rings/Strip toggle (Phase 5). HWC planets carry
            # P_SEMI_MAJOR_AXIS, so the Strip view gets planet-SMA markers.
            hz_planets = [{"name": p.get("P_NAME") or "planet",
                           "au": _fval(p.get("P_SEMI_MAJOR_AXIS"))}
                          for p in planet_rows if _fval(p.get("P_SEMI_MAJOR_AXIS"))]
            hz_w = _hz_toggle_tab(
                self, teff_v, lum_v,
                title=f"Habitable Zone  (T={teff_v:.0f} K, L={lum_v:.4f} L☉)",
                planets=hz_planets, markers=markers_arg)
            if hz_w is not None:
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

from core.databases import (oec_fv as _oec_fv,
                            oec_statuses as _oec_statuses, oec_binary_label as _oec_binary_label)

# ── Columnar tree (OEC_SYSTEM_VIEW_PLAN Stage 1) ─────────────────────────────
# Star rows populate the SAME columns as planets (M/R/T + the derived L and HZ
# cells), so nothing about a star is hidden behind a selection. The old
# `_OEC_TREE_KEYS` / `_oec_tree_bits` crammed-string model is replaced, not extended.

_OEC_TREE_PREFIX = {"system": "◆", "binary": "⋔", "star": "★",
                    "planet": "●", "satellite": "☾"}

_OEC_COLUMNS = ["Node", "Type", "M", "R", "P (d)", "a (AU)", "e", "T (K)",
                "L / S⊕", "HZ"]
(_OEC_COL_NODE, _OEC_COL_TYPE, _OEC_COL_M, _OEC_COL_R, _OEC_COL_P,
 _OEC_COL_A, _OEC_COL_E, _OEC_COL_T, _OEC_COL_L, _OEC_COL_HZ) = range(10)

# Columns 8/9 are derived (violet in the pane; here they simply carry a value or
# stay empty). Stage 1b fills them for stars via `_oec_tree_derived_cells`.
_OEC_DERIVED_COLUMNS = (_OEC_COL_L, _OEC_COL_HZ)

# D1 — the tri-state units control. Label → the `units` value `oec_planet_units`
# understands; the reverse map seeds the combo from the current state.
_OEC_NODE_COL_WIDTH = 300      # a name column, not what Stretch leaves over
_OEC_UNIT_LABELS = {"Auto": "auto", "M⊕ / R⊕": "earth", "M♃ / R♃": "jupiter"}
_OEC_UNIT_LABEL_OF = {v: k for k, v in _OEC_UNIT_LABELS.items()}


# The value formatters live in gui/panels/oec_detail.py so the tree and the
# detail pane can never render the same field two different ways (§B.6).
from gui.panels.oec_detail import (
    oec_value_cell as _oec_value_cell,
    oec_planet_units as _oec_planet_units,
    oec_mass_label as _oec_mass_label,
    oec_num as _oec_num,
    build_detail_pane as _oec_build_detail_pane,
    build_context as _oec_build_context,
    oec_star_xrefs as _oec_star_xrefs,
    oec_hz_short as _oec_hz_short,
)


def _oec_node_tooltip(node):
    """Every catalogued field of a node, one per line — so no value is unreachable
    at any build stage (the detail pane, Stage 3, is the permanent home)."""
    lines = []
    for key in sorted(node.get("fields", {})):
        if key == "list":
            continue
        # repeats=True: a binary's `separation` is catalogued in AU *and* arcsec,
        # so first-value-only would break this function's whole promise.
        txt = _oec_value_cell(node["fields"][key], repeats=True)
        if txt:
            lines.append(f"{key}: {txt}")
    return "\n".join(lines)


def _oec_field_by_unit(field, want_unit):
    """The numeric value of the repeat whose `unit` attribute matches, or None.

    A repeated field is not "the first one plus some extras" — a binary's
    `separation` is genuinely two different measurements of one pair (AU and
    arcsec), and taking the first would silently mix the units."""
    if field is None:
        return None
    for fv in (field if isinstance(field, list) else [field]):
        if str(fv.get("unit") or "").strip().lower() == want_unit.lower():
            try:
                return float(fv.get("value"))
            except (TypeError, ValueError):
                # Keep scanning: a blank AU row must not mask a usable one that
                # follows it.
                continue
    return None


def _oec_node_values(node):
    """OEC node → the plain numeric dict `core.oec_derived` consumes (it never
    sees a node dict, so it stays Qt-free and headlessly testable)."""
    f = node.get("fields", {}) or {}
    out = {}
    for key in ("mass", "radius", "temperature", "semimajoraxis", "period",
                "eccentricity", "inclination", "distance", "age", "metallicity",
                "separation", "magU", "magB", "magV", "magR", "magI",
                "magJ", "magH", "magK"):
        v = _oec_num(f.get(key))
        if v is not None:
            out[key] = v
    if node.get("tag") == "binary":
        # The circumbinary HZ needs both components' light (D9).
        out["components"] = [_oec_node_values(c) for c in node.get("children", [])
                             if c.get("tag") == "star"]
        # `separation` REPEATS — the same pair is catalogued in AU and in arcsec.
        # Select by the unit attribute; `_oec_num` would hand back whichever came
        # first, so a 400 AU pair could arrive as "80" (arcsec).
        out["separation_au"] = _oec_field_by_unit(f.get("separation"), "au")
        out["separation_arcsec"] = _oec_field_by_unit(f.get("separation"), "arcsec")
        masses = [c.get("mass") for c in out["components"]]
        nested = [c for c in node.get("children", []) if c.get("tag") == "binary"]
        if len(masses) >= 2 and all(m is not None for m in masses) and not nested:
            # Kepler III needs M_total; 61 Cygni has a period but no
            # `semimajoraxis`, so without this the pair has no `a` at all.
            #
            # A NESTED binary component disqualifies the sum: α Cen's outer pair is
            # Proxima + the AB binary, and a `<binary>` carries no mass of its own,
            # so summing the star children alone would yield 0.12 M☉ for a ~2.1 M☉
            # pair and a Kepler-recovered `a` wrong by a factor of ~2.4.
            out["total_mass"] = sum(masses)
    fv = _oec_fv(f.get("spectraltype"))
    if fv:
        out["spectraltype"] = fv.get("value")
    fvm = _oec_fv(f.get("mass"))
    if fvm and fvm.get("type"):
        out["mass_type"] = fvm.get("type")
    return out


def _oec_host_of(node, ctx):
    """The node a planet orbits — a `<star>` parent, or the `<binary>` itself for a
    circumbinary (P-type) planet. None for a rogue planet."""
    parent = (ctx.get("parents") or {}).get(id(node))
    if parent is None or parent.get("tag") not in ("star", "binary"):
        return None
    return parent


def _oec_pair_host_values(binary):
    """A circumbinary planet's host is the PAIR, not its primary component.

    A P-type planet orbits the barycenter and is lit by both stars, so Kepler III
    needs `M₁+M₂` and the insolation needs `L₁+L₂`. Taking the first component
    alone understates both: measured on the real cache, TIC 172900988 b's recovered
    semi-major axis came out **0.7115 AU instead of 0.8921 AU (−20%)**, and
    KIC 7177553 b's insolation read 0.361 S⊕ where the pair's own pane row (one
    click away) implies 0.708 — the same panel disagreeing with itself by ~2×."""
    comps = [c for c in binary.get("children", []) if c.get("tag") == "star"]
    nested = [c for c in binary.get("children", []) if c.get("tag") == "binary"]
    vals = [_oec_node_values(c) for c in comps]
    out = {"host_kind": "pair"}

    masses = [v.get("mass") for v in vals]
    # A nested `<binary>` component carries no mass of its own, so the sum would
    # silently omit it (α Cen's outer pair → 0.12 M☉ for ~2.1 M☉).
    if len(masses) >= 2 and all(m is not None for m in masses) and not nested:
        out["mass"] = sum(masses)

    lums, weighted = [], []
    for v in vals:
        r, t = v.get("radius"), v.get("temperature")
        if r and r > 0 and t and t > 0:
            lum = core.equations.compute_star_luminosity(r, t)["luminosity"]
            lums.append(lum)
            weighted.append(lum * t)
    if len(lums) >= 2 and not nested:
        out["luminosity"] = sum(lums)
        # The same luminosity-weighted effective Teff `compute_circumbinary_hz`
        # uses, so the pane's planet rows and its binary HZ row agree.
        out["temperature"] = sum(weighted) / sum(lums)
    # Transit geometry is against a single disc; the primary's radius is the only
    # defensible R★ for a pair, and the transit source says so.
    if vals and vals[0].get("radius"):
        out["radius"] = vals[0]["radius"]
    return out


def _oec_host_values(node, ctx):
    """Host values for a planet's derived layer (empty for everything else)."""
    if node.get("tag") != "planet":
        return {}
    host = _oec_host_of(node, ctx)
    if host is None:
        return {}
    if host.get("tag") == "binary":
        return _oec_pair_host_values(host)
    return _oec_node_values(host)


def _oec_star_tree_cells(node):
    """(L / S⊕, HZ) tree cells for a star — Stage 1b's derived minimum."""
    d = core.oec_derived.derive("star", _oec_node_values(node))
    lum = d.get("luminosity_lsun", {})
    hz = d.get("hz_bounds", {})
    lum_cell = f"{lum['value']:.4g} L☉" if lum.get("value") is not None else ""
    hz_cell = ""
    if hz.get("value"):
        inner = hz["value"].get("conservative_inner_au")
        outer = hz["value"].get("conservative_outer_au")
        if inner is not None and outer is not None:
            hz_cell = f"{inner:.3g}–{outer:.3g} AU"
    return lum_cell, hz_cell


def _oec_derived_tree_provider(node):
    """The tree's derived-cell provider. Only stars carry cells at Stage 1b;
    planet insolation / HZ verdict arrive with Stage 4b."""
    if node.get("tag") == "star":
        return _oec_star_tree_cells(node)
    return "", ""


def _oec_tree_derived_cells(node, ctx):
    """(L / S⊕, HZ) cells. Filled by the derived provider in ``ctx`` when one is
    installed (Stage 1b); ('', '') otherwise."""
    provider = (ctx or {}).get("derived_cells", _oec_derived_tree_provider)
    if provider is None:
        return "", ""
    try:
        return provider(node)
    except Exception:                            # a derived value must never break the tree
        log_viz_error("OEC derived tree cells")
        return "", ""


def _oec_tree_cells(node, ctx=None):
    """The 10 column strings for one OEC node.

    Split out of `_oec_tree_item` so the Stage-6 toolbar can re-render the cells of
    the EXISTING items (`_oec_refresh_tree_cells`) instead of rebuilding the tree:
    a rebuild would drop the expansion state, the scroll position and the selection
    every time a checkbox moved (T12a asserts item identity survives)."""
    ctx = ctx or {}
    errs = ctx.get("errors", True)
    tag, f = node["tag"], node["fields"]
    cells = [""] * len(_OEC_COLUMNS)
    prefix = _OEC_TREE_PREFIX.get(tag, "")

    if tag == "system":
        name = node["names"][0] if node.get("names") else "System"
        extra = []
        if f.get("constellation"):
            extra.append(_oec_fv(f["constellation"])["value"])
        if f.get("distance"):
            extra.append("d=" + _oec_value_cell(f["distance"], "pc", show_errors=errs))
        if extra:
            name += "  ·  " + " · ".join(extra)
        cells[_OEC_COL_TYPE] = "system"
    elif tag == "binary":
        name = _oec_binary_label(node)
        if f.get("separation"):
            name += "  ·  sep " + _oec_value_cell(f["separation"], show_errors=errs)
        cells[_OEC_COL_TYPE] = "binary"
        cells[_OEC_COL_P] = _oec_value_cell(f.get("period"), show_errors=errs)
        cells[_OEC_COL_A] = _oec_value_cell(f.get("semimajoraxis"), show_errors=errs)
        cells[_OEC_COL_E] = _oec_value_cell(f.get("eccentricity"), show_errors=errs)
    elif tag == "star":
        name = node["names"][0] if node.get("names") else "Star"
        if not node.get("children"):
            name += "  ·  (no planets catalogued)"
        sp = _oec_fv(f["spectraltype"])["value"] if f.get("spectraltype") else ""
        cells[_OEC_COL_TYPE] = sp or "star"
        cells[_OEC_COL_M] = _oec_value_cell(f.get("mass"), "M☉", show_errors=errs)
        cells[_OEC_COL_R] = _oec_value_cell(f.get("radius"), "R☉", show_errors=errs)
        cells[_OEC_COL_T] = _oec_value_cell(f.get("temperature"), show_errors=errs)
    elif tag == "satellite":
        name = node["names"][0] if node.get("names") else "Moon"
        cells[_OEC_COL_TYPE] = "satellite"
        # A `<satellite>`'s mass/radius are catalogued in JUPITER units, exactly
        # like a planet's (the Moon is 0.000039 M♃ / 0.024847 R♃) — labelling the
        # raw number M⊕/R⊕ was wrong by 318× / 11×. Converted, always to Earth: a
        # moon is unreadable in Jupiter units, and the D1 toolbar stays planet-only.
        cells[_OEC_COL_M] = _oec_value_cell(f.get("mass"), "M⊕", _MJUP_MEARTH,
                                            show_errors=errs)
        cells[_OEC_COL_R] = _oec_value_cell(f.get("radius"), "R⊕", _RJUP_REARTH,
                                            show_errors=errs)
        cells[_OEC_COL_P] = _oec_value_cell(f.get("period"), show_errors=errs)
        cells[_OEC_COL_A] = _oec_value_cell(f.get("semimajoraxis"), show_errors=errs)
        cells[_OEC_COL_E] = _oec_value_cell(f.get("eccentricity"), show_errors=errs)
    else:  # planet
        name = node["names"][0] if node.get("names") else "Planet"
        statuses = _oec_statuses(f)
        if statuses:
            name += f"  [{' / '.join(statuses)}]"
        mf, mu, rf, ru = _oec_planet_units(node, ctx.get("units", "auto"))
        cells[_OEC_COL_TYPE] = "planet"
        cells[_OEC_COL_M] = _oec_value_cell(f.get("mass"), mu, mf, show_errors=errs)
        # `oec_mass_label` returns "M·sin i" or "Mass" — never "M". Comparing
        # against "M" made EVERY mass an RV minimum mass (2,581 of 2,844 real
        # masses mislabelled). Test the positive value, not a near-miss.
        if cells[_OEC_COL_M] and _oec_mass_label(node) == "M·sin i":
            cells[_OEC_COL_M] = "M·sin i " + cells[_OEC_COL_M]
        cells[_OEC_COL_R] = _oec_value_cell(f.get("radius"), ru, rf, show_errors=errs)
        cells[_OEC_COL_P] = _oec_value_cell(f.get("period"), show_errors=errs)
        cells[_OEC_COL_A] = _oec_value_cell(f.get("semimajoraxis"), show_errors=errs)
        cells[_OEC_COL_E] = _oec_value_cell(f.get("eccentricity"), show_errors=errs)
        cells[_OEC_COL_T] = _oec_value_cell(f.get("temperature"), show_errors=errs)

    cells[_OEC_COL_NODE] = f"{prefix} {name}".strip()
    if ctx.get("derived", True):
        cells[_OEC_COL_L], cells[_OEC_COL_HZ] = _oec_tree_derived_cells(node, ctx)
    return cells


def _oec_tree_item(node, ctx=None):
    """Build a 10-column QTreeWidgetItem for an OEC node (children recursed).

    ``ctx`` carries display state: ``units`` ("auto"/"earth"/"jupiter"),
    ``errors`` (bool) and an optional ``derived_cells`` provider."""
    ctx = ctx or {}
    cells = _oec_tree_cells(node, ctx)
    item = QTreeWidgetItem(cells)
    # Python attribute, NOT setData(…, UserRole, node): PySide6 marshals a dict
    # through QVariantMap and hands back a *copy*, so identity — which every
    # selection path keys on — would be lost.
    item._oec_node = node
    tip = _oec_node_tooltip(node)
    if tip:
        item.setToolTip(_OEC_COL_NODE, tip)
    for col in range(1, len(_OEC_COLUMNS)):
        item.setTextAlignment(
            col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    for child in node.get("children", []):
        item.addChild(_oec_tree_item(child, ctx))
    return item


def _oec_item_node(item):
    """The OEC node dict a tree item was built from (None if absent)."""
    return getattr(item, "_oec_node", None)


def _oec_node_count(node):
    return 1 + sum(_oec_node_count(c) for c in node.get("children", []))


def _oec_expand_tree(tree, root_item, node_count):
    """D5 — `expandAll()` at ≤ 25 nodes, else expand only down to star level."""
    if node_count <= 25:
        tree.expandAll()
        return

    def walk(item):
        node = _oec_item_node(item) or {}
        if node.get("tag") in ("system", "binary"):
            item.setExpanded(True)
            for i in range(item.childCount()):
                walk(item.child(i))

    walk(root_item)


def _oec_hide_empty_columns(tree):
    """Hide every value column no row populates (toolbar 'Hide empty columns')."""
    def cells(item, col, out):
        out.append(item.text(col))
        for i in range(item.childCount()):
            cells(item.child(i), col, out)

    roots = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    for col in range(1, tree.columnCount()):
        texts = []
        for r in roots:
            cells(r, col, texts)
        tree.setColumnHidden(col, not any(t.strip() for t in texts))


def _oec_show_all_columns(tree):
    for col in range(tree.columnCount()):
        tree.setColumnHidden(col, False)


def _oec_refresh_tree_cells(tree, ctx):
    """Re-render every item's cells in place under new display state (Stage 6).

    The items themselves are reused, so expansion, scroll position and the current
    selection all survive a toolbar change — and the pane, which keys on node
    identity (§B.3), keeps pointing at the same node."""
    def walk(item):
        node = _oec_item_node(item)
        if node is not None:
            for col, text in enumerate(_oec_tree_cells(node, ctx)):
                item.setText(col, text)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i))


# ── Phase 2: Star-Databases parity (Hypatia + per-host diagrams) ──────────────
# Reuse the shared diagram-tab builders + the Hypatia path verbatim; the only new code
# is the OEC-node → NASA-key adapter and the OEC-star → Hypatia compat dict.
from gui.panels.diagram_tabs import (
    _make_hz_tab, _hz_toggle_tab, _make_orbits_tab, _make_mass_radius_tab,
    _make_transit_tab, _make_size_tab,
)

# B.2 — the canonical pair lives in core.shared; do not re-type the literals here.
from core.shared import M_JUP_EARTH as _MJUP_MEARTH, R_JUP_EARTH as _RJUP_REARTH


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


def _show_oec_planet_dialog(parent_widget, planet, ctx=None):
    """Non-modal dialog of a clicked OEC planet's fields (mirrors the NASA System
    Map's click-planet dialog). All data comes from the planet node already in hand
    — no network. Kept alive by Qt parent-ownership + WA_DeleteOnClose.

    D7 — the map has no detail pane, so the dialog stays; it renders from the SAME
    section builder as the pane (`gui.panels.oec_detail`), so the two can never
    disagree about a field's label, unit or presence. Its own hand-written label
    table is gone with it — that table is where the `periastron` collision lived
    (it labelled the argument of periastron, in degrees, as "Periastron ... AU")."""
    node = planet.get("node") or {}
    name = planet.get("name") or "Planet"

    dlg = QDialog(parent_widget)
    dlg.setWindowTitle(f"Planet Info — {name}")
    dlg.setMinimumWidth(460)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.Window)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(12, 12, 12, 8)
    outer.setSpacing(6)

    if planet.get("host"):
        host_lbl = QLabel(f"Host: {planet['host']}")
        host_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(host_lbl)

    body = QScrollArea()
    body.setWidgetResizable(True)
    # The panel passes its live ctx so the dialog shows the SAME derived rows and
    # honours the same units mode as the tree pane. A hard-coded ctx would leave
    # `derived_values` empty and silently drop the entire Derived block — the one
    # thing the shared builder is meant to make impossible.
    body.setWidget(_oec_build_detail_pane(
        node, ctx if ctx is not None else {"units": "auto", "errors": True}))
    body.setMinimumHeight(320)
    outer.addWidget(body, 1)

    moons = [c for c in node.get("children", []) if c.get("tag") == "satellite"]
    if moons:
        names = ", ".join((m["names"][0] if m.get("names") else "moon") for m in moons)
        outer.addWidget(QLabel(f"<b>Satellites:</b> {len(moons)} ({names})"))

    close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btn.rejected.connect(dlg.close)
    outer.addWidget(close_btn)

    dlg.adjustSize()
    dlg.show()
    return dlg


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

        self._oec_system = result["system"]
        self._oec_hosts = _oec_collect_hosts(result["system"])
        self._oec_hypatia = result.get("_hypatia", {})
        # Phase-3b interactive-map state: which node the Architecture map is anchored
        # on (None = whole-system barycenter) and which host drives the detail tabs.
        self._oec_focus = None
        self._oec_host_idx = 0 if self._oec_hosts else None
        # Session-only view state (D6 — no QSettings). Defaults: D1 auto units,
        # D3 derived on, D4 errors on, hide-empty on.
        #
        # Initialised ONCE per panel, not per result: rebuilding it here would
        # revert the user's pane position and toggles on every new search, and
        # Stage 6 adds three more controls to this same dict.
        if not getattr(self, "_oec_view", None):
            self._oec_view = {"units": "auto", "errors": True, "derived": True,
                              "hide_empty": True, "pane": "Right",
                              "pin_host": True}
        # §B.3 — the ONE selection attribute the tree, the map, the host combo
        # and (Stage 5) the pinned band all converge on.
        self._oec_sel = None
        self._oec_syncing = False     # guards the programmatic tree-cursor sync
        self._oec_ctx = _oec_build_context(result["system"])
        self._oec_derived_cache = {}  # cleared per result (§D.4 rule 4 / T19)

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
        self._data_tabs.addTab(self._build_oec_data_widget(result["system"]), "Data")
        self._result_area.addWidget(self._data_tabs, 1)

        # System Architecture map (Phase 3) — a system-level viz tab, always tab 0,
        # shown even for planetless / rogue systems (which skip _render_host).
        self._add_architecture_tab()
        if self._oec_hosts:
            self._render_host(0)
        self._set_oec_selection(self._oec_cold_selection(result["system"]))
        self._finish_render()

    def _oec_tree_ctx(self):
        """Display state handed to `_oec_tree_item` (units / errors / derived)."""
        ctx = dict(getattr(self, "_oec_view", None) or {})
        # The panel's own provider: it can reach the host star (a planet's S⊕ and
        # HZ verdict need the host's light) and shares the derived cache, which the
        # module-level fallback provider cannot.
        ctx["derived_cells"] = self._oec_tree_cells
        return ctx

    def _oec_tree_cells(self, node):
        """(L / S⊕, HZ) tree cells for a star or a planet."""
        tag = node.get("tag")
        if tag not in ("star", "planet"):
            return "", ""
        d = self._oec_derived_for(node)
        if tag == "star":
            lum, hz = d.get("luminosity_lsun", {}), d.get("hz_bounds", {})
            lum_cell = (f"{lum['value']:.4g} L☉"
                        if lum.get("value") is not None else "")
            hz_cell = ""
            if hz.get("value"):
                inner = hz["value"].get("conservative_inner_au")
                outer = hz["value"].get("conservative_outer_au")
                if inner is not None and outer is not None:
                    hz_cell = f"{inner:.3g}–{outer:.3g} AU"
            return lum_cell, hz_cell
        seff, verdict = d.get("insolation_searth", {}), d.get("hz_verdict", {})
        seff_cell = (f"{seff['value']:.3g}"
                     if seff.get("value") is not None else "")
        return seff_cell, _oec_hz_short(verdict.get("value"))

    def _oec_detail_ctx(self, node):
        """Display state + the parent chain + this node's derived values.

        A star's position/distance live on the **system** node and its companions
        on the **parent binary**, so the pane needs the context, not just the node
        (`oec_detail.build_context`)."""
        ctx = dict(self._oec_tree_ctx())
        ctx.pop("derived_cells", None)
        ctx.update(getattr(self, "_oec_ctx", None) or {})
        ctx["derived_values"] = self._oec_derived_for(node)
        # A star's Companions block reports the PARENT PAIR's mass ratio and
        # S/P-type critical SMAs (the mockup shows exactly that). Those keys live
        # on the binary's derived entry, not the star's, so without this the rows
        # are silently dropped by `_derived_rows` and the whole stability
        # derivation is invisible in the UI.
        parent = (ctx.get("parents") or {}).get(id(node))
        ctx["parent_derived"] = (self._oec_derived_for(parent)
                                 if parent is not None
                                 and parent.get("tag") == "binary" else {})
        # Stage 5 — the pinned host band. `_oec_host_of` is the SAME resolver the
        # planet's own derived layer uses, so the band can never describe a
        # different host than the numbers beside it were computed from (a
        # circumbinary planet's host is the pair, not its primary component).
        host = _oec_host_of(node, ctx) if node.get("tag") == "planet" else None
        ctx["host_node"] = host
        ctx["host_derived"] = (self._oec_derived_for(host)
                               if host is not None else {})
        ctx["on_select_host"] = self._set_oec_selection
        ctx["on_lookup"] = self._open_oec_star_lookup
        return ctx

    def _oec_derived_for(self, node):
        """Derived entries for one node, memoised per result.

        §D.4 rule 4 warns that a bare `id(node)` key is a wrong-numbers bug: ids
        are reused after GC and the node dicts are rebuilt per search. Three things
        together make this safe, and **all three are load-bearing** —
          1. the cache is cleared in `_on_oec_result`, so entries never outlive
             the result they were computed for;
          2. each entry stores the node itself, `(node, values)`, keeping a strong
             reference so that id cannot be reused while the entry is live;
          3. the read re-checks `hit[0] is node`, so a reused id can never return
             another node's numbers.
        Removing any one of them reintroduces the bug (T19)."""
        cache = getattr(self, "_oec_derived_cache", None)
        if cache is None:
            cache = self._oec_derived_cache = {}
        key = id(node)
        hit = cache.get(key)
        if hit is not None and hit[0] is node:
            return hit[1]
        ctx = getattr(self, "_oec_ctx", None) or {}
        system = ctx.get("system") or node
        try:
            values = core.oec_derived.derive(
                node.get("tag"), _oec_node_values(node),
                host_values=_oec_host_values(node, ctx),
                system_values=_oec_node_values(system))
        except Exception:
            log_viz_error("OEC derived values")
            values = {}
        values.update(self._oec_panel_derived(node))
        cache[key] = (node, values)
        return values

    def _oec_panel_derived(self, node):
        """Derived values the pure module deliberately cannot produce.

        Two of them: `compute_hyper_limit_for_spectral_type` does a **SQLite
        read**, so it is computed here and merged in, keeping
        `core/oec_derived.py` free of I/O (§D rule 6 / D.1); and `topology` is a
        **tree walk**, and the derived module only ever sees a flat value dict."""
        if node.get("tag") == "system":
            return {"topology": self._oec_topology(node)}
        if node.get("tag") != "star":
            return {}
        fv = _oec_fv((node.get("fields") or {}).get("spectraltype"))
        sp = (fv or {}).get("value")
        src = ("core.science.compute_hyper_limit_for_spectral_type — "
               "Honorverse (fiction), not physics")
        if not sp:
            return {"hyper_limit_au": {"value": None, "unit": "AU",
                                       "reason": "no catalogued spectral type",
                                       "source": src}}
        try:
            # Returns {"lm", "au", "matched_class"} — NOT a bare float.
            hit = core.science.compute_hyper_limit_for_spectral_type(sp)
        except Exception:
            log_viz_error("OEC hyper limit")
            hit = None
        au = hit.get("au") if isinstance(hit, dict) else hit
        if au is None:
            return {"hyper_limit_au": {
                "value": None, "unit": "AU",
                "reason": f"no hyper limit for spectral type '{sp}' "
                          "(not an O/B/A/F/G/K/M class)", "source": src}}
        return {"hyper_limit_au": {"value": au, "unit": "AU",
                                   "reason": None, "source": src}}

    def _open_oec_star_lookup(self, node):
        """Cross-reference action — open the star in a SimbadPanel (which carries
        Hypatia, GCNS and Gould) in a separate non-modal window, mirroring
        `ProjectsPanel._open_real`. User-initiated, so the network call is fine."""
        xrefs = _oec_star_xrefs(node)
        name = xrefs[0][1] if xrefs else (node.get("names") or [""])[0]
        if not name:
            return
        from gui.panels.simbad import SimbadPanel
        dlg = QDialog(self)
        dlg.setWindowTitle(f"SIMBAD — {name}")
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.Window)
        v = QVBoxLayout(dlg)
        panel = SimbadPanel(self.window)
        if hasattr(panel, "_name_input"):
            panel._name_input.setText(name)
        v.addWidget(panel)
        dlg.resize(820, 640)
        dlg.setModal(False)
        dlg.show()
        try:
            panel._search()
        except Exception:
            log_viz_error("OEC cross-reference lookup")
        return dlg

    def _build_oec_tree(self, system):
        """The 10-column Data tree (Stage 1). Star rows carry M/R/T in the same
        columns as planets; §B.5 keeps alternating rows. Sizing is
        ResizeToContents on the numeric columns and **Interactive at
        `_OEC_NODE_COL_WIDTH`** on the name column — §B.5's Stretch starved it
        beside the detail pane (see the comment below)."""
        tree = QTreeWidget()
        tree.setHeaderLabels(_OEC_COLUMNS)
        tree.setAlternatingRowColors(True)
        tree.setUniformRowHeights(True)
        root = _oec_tree_item(system, self._oec_tree_ctx())
        tree.addTopLevelItem(root)
        _oec_expand_tree(tree, root, _oec_node_count(system))

        hdr = tree.header()
        # §B.5 dropped the old fixed 340 px column-0 width in favour of Stretch —
        # but Stretch only gets what the ResizeToContents columns leave over, and
        # beside the Stage-2 detail pane that was ~95 px: every tau Ceti planet
        # rendered as "t…" (found by the V6 visual pass). Interactive with a
        # readable default restores Stage 1's acceptance line and still lets the
        # user drag; the numeric columns keep sizing to their content.
        hdr.setSectionResizeMode(_OEC_COL_NODE, QHeaderView.ResizeMode.Interactive)
        tree.setColumnWidth(_OEC_COL_NODE, _OEC_NODE_COL_WIDTH)
        for col in range(1, len(_OEC_COLUMNS)):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        tree.setMinimumHeight(240)
        if self._oec_view.get("hide_empty", True):
            _oec_hide_empty_columns(tree)
        self._oec_tree = tree
        return tree

    # ── Stage 2: the detail pane, its splitter, and selection (§B.3 / §B.4) ──

    def _build_oec_data_widget(self, system):
        """The Data tab: tree + detail pane in a QSplitter.

        §B.4 — the pane lives **inside** the Data tab, never as a sibling tab:
        `_rebuild_after_focus` deletes every tab above index 0, so a pane-as-tab
        would be silently destroyed on every map recenter and host switch (T10)."""
        tree = self._build_oec_tree(system)

        pane = QScrollArea()
        pane.setWidgetResizable(True)
        pane.setMinimumWidth(300)
        self._oec_pane = pane

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tree)
        splitter.addWidget(pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        self._oec_splitter = splitter

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(4, 2, 4, 0)

        # Stage 6 toolbar. Session-only state (D6 — no QSettings), no "Columns…"
        # button (D8) and no Copy/Export (D12): the mockup shows those three, and
        # shipping a dead button is worse than shipping none.
        h.addWidget(QLabel("Units:"))
        units = QComboBox()
        units.addItems(list(_OEC_UNIT_LABELS))
        units.setCurrentText(_OEC_UNIT_LABEL_OF.get(
            self._oec_view.get("units", "auto"), "Auto"))
        units.setToolTip("Catalogued planet mass/radius only (D1). Auto picks M⊕ "
                         "below 0.1 M♃, per node; derived values keep their own "
                         "fixed units.")
        units.currentTextChanged.connect(self._on_oec_units)
        self._oec_units_combo = units
        h.addWidget(units)

        h.addWidget(QLabel("Detail pane:"))
        combo = QComboBox()
        combo.addItems(["Right", "Below", "Hidden"])
        combo.setCurrentText(self._oec_view.get("pane", "Right"))
        combo.currentTextChanged.connect(self._on_oec_pane_position)
        self._oec_pane_combo = combo
        h.addWidget(combo)

        # Hide-empty needed its own control from the moment it existed (Stage 2):
        # without one, a column hidden as empty could never be re-shown.
        for attr, text, key, slot in (
                ("_oec_errors_box", "Errors", "errors", self._on_oec_errors),
                ("_oec_derived_box", "Derived", "derived", self._on_oec_derived),
                ("_oec_hide_empty_box", "Hide empty columns", "hide_empty",
                 self._on_oec_hide_empty),
                ("_oec_pin_host_box", "Pin host star", "pin_host",
                 self._on_oec_pin_host)):
            box = QCheckBox(text)
            box.setChecked(self._oec_view.get(key, True))
            box.toggled.connect(slot)
            setattr(self, attr, box)
            h.addWidget(box)
        h.addStretch()
        v.addWidget(bar)
        v.addWidget(splitter, 1)
        # §B.5 / T10b — the enclosing QScrollArea layout is AlignTop, which gives
        # each item its size hint rather than stretching it, so the height floor
        # has to be explicit or the tree collapses to a sliver.
        container.setMinimumHeight(420)

        tree.selectionModel().currentChanged.connect(self._on_oec_tree_current)
        self._on_oec_pane_position(self._oec_view.get("pane", "Right"))
        return container

    def _on_oec_hide_empty(self, checked):
        """Toggle the empty-column filter without rebuilding the tree."""
        self._oec_view["hide_empty"] = bool(checked)
        self._apply_oec_column_visibility()

    def _apply_oec_column_visibility(self):
        tree = getattr(self, "_oec_tree", None)
        if tree is None:
            return
        if self._oec_view.get("hide_empty", True):
            _oec_hide_empty_columns(tree)
        else:
            _oec_show_all_columns(tree)

    # ── Stage 6 — the rest of the toolbar ──

    def _on_oec_units(self, label):
        """D1 tri-state — Auto / M⊕ / M♃, catalogued planet mass+radius only."""
        self._oec_view["units"] = _OEC_UNIT_LABELS.get(label, "auto")
        self._refresh_oec_view()

    def _on_oec_errors(self, checked):
        self._oec_view["errors"] = bool(checked)
        self._refresh_oec_view()

    def _on_oec_derived(self, checked):
        self._oec_view["derived"] = bool(checked)
        self._refresh_oec_view()

    def _on_oec_pin_host(self, checked):
        """The pinned host band is a pane-only concern — no tree cell moves."""
        self._oec_view["pin_host"] = bool(checked)
        self._refresh_oec_view(tree=False)

    def _refresh_oec_view(self, tree=True):
        """Re-render tree cells + the pane under the current view state.

        The tree is NEVER rebuilt: `_oec_refresh_tree_cells` re-texts the existing
        items, so expansion, scroll position and the selection all survive
        (T12a asserts `topLevelItem(0)` identity). Column visibility is re-applied
        afterwards because a toggle can empty a column — turning Derived off
        empties L and HZ — and with hide-empty on those columns should go."""
        widget = getattr(self, "_oec_tree", None)
        if tree and widget is not None:
            _oec_refresh_tree_cells(widget, self._oec_tree_ctx())
            self._apply_oec_column_visibility()
        sel = getattr(self, "_oec_sel", None)
        if sel:
            self._render_oec_detail(sel[0])

    def _on_oec_pane_position(self, text):
        """Detail pane Right (default) / Below / Hidden — session-only (D2, D6)."""
        self._oec_view["pane"] = text
        splitter = getattr(self, "_oec_splitter", None)
        pane = getattr(self, "_oec_pane", None)
        if splitter is None or pane is None:
            return
        if text == "Hidden":
            pane.setVisible(False)
            return
        splitter.setOrientation(Qt.Orientation.Vertical if text == "Below"
                                else Qt.Orientation.Horizontal)
        pane.setVisible(True)

    def _on_oec_tree_current(self, current, _previous):
        """Tree selection → the shared selection attribute.

        Wired to `currentChanged`, NOT `itemClicked` (§B.3): with `itemClicked`,
        arrow-key navigation silently stops updating the pane."""
        tree = getattr(self, "_oec_tree", None)
        if tree is None or not current.isValid() or getattr(self, "_oec_syncing", False):
            return
        node = _oec_item_node(tree.itemFromIndex(current))
        if node is not None:
            self._set_oec_selection(node, sync_tree=False)

    def _set_oec_selection(self, node, sync_tree=True):
        """The single entry point every selector funnels through. Renders the
        detail pane — and NOTHING else: a selection change must never rebuild the
        viz tabs, or clicking a planet would tear down the diagram in view."""
        if node is None:
            return
        self._oec_sel = (node, node.get("tag"))
        if sync_tree:
            self._select_oec_tree_node(node)
        self._render_oec_detail(node)

    def _select_oec_tree_node(self, node):
        """Move the tree cursor to `node` without re-entering `_set_oec_selection`."""
        tree = getattr(self, "_oec_tree", None)
        if tree is None:
            return

        def find(item):
            if _oec_item_node(item) is node:
                return item
            for i in range(item.childCount()):
                hit = find(item.child(i))
                if hit is not None:
                    return hit
            return None

        for i in range(tree.topLevelItemCount()):
            item = find(tree.topLevelItem(i))
            if item is not None:
                # A re-entrancy FLAG, not blockSignals(). Two traps here:
                #   * `tree.blockSignals()` does not stop `currentChanged` at all —
                #     that signal belongs to the selection model, so the pane would
                #     be built twice.
                #   * `selectionModel().blockSignals()` does stop it, but also
                #     suppresses the VIEW's own slots, so the row moves without
                #     being painted as selected or scrolled into view.
                self._oec_syncing = True
                try:
                    tree.setCurrentItem(item)
                finally:
                    self._oec_syncing = False
                return

    def _render_oec_detail(self, node):
        """Rebuild the pane's contents for one node. Never blanks the panel: a
        failing section degrades inside `build_detail_pane` (T18), and a failure
        of the pane as a whole is logged and leaves the previous pane in place."""
        pane = getattr(self, "_oec_pane", None)
        if pane is None:
            return
        try:
            pane.setWidget(_oec_build_detail_pane(node, self._oec_detail_ctx(node)))
        except Exception:
            log_viz_error("OEC detail pane")

    def _oec_topology(self, system):
        """The system's shape, in the same vocabulary `oec-census` uses (§D.1):
        star count, max binary nesting depth, and where the planets attach —
        circumbinary (to a `<binary>`), rogue (to the `<system>`), or to a star."""
        src = "tree walk — same classification as `query.py oec-census`"
        stars = attached = circumbinary = rogue = 0
        depth = 0

        def walk(node, d):
            nonlocal stars, attached, circumbinary, rogue, depth
            depth = max(depth, d)
            for child in node.get("children", []):
                tag = child.get("tag")
                if tag == "star":
                    stars += 1
                elif tag == "planet":
                    if node.get("tag") == "binary":
                        circumbinary += 1
                    elif node.get("tag") == "system":
                        rogue += 1
                    else:
                        attached += 1
                walk(child, d + 1 if tag == "binary" else d)

        walk(system, 0)
        bits = [f"{stars} star{'s' if stars != 1 else ''}"]
        if depth:
            bits.append(f"binary nesting depth {depth}")
        planets = attached + circumbinary + rogue
        if not planets:
            bits.append("no planets catalogued")
        else:
            if circumbinary:
                bits.append(f"{circumbinary} circumbinary (P-type)")
            if rogue:
                bits.append(f"{rogue} rogue (attached to the system)")
            if attached:
                bits.append(f"{attached} attached to a star")
        return {"value": " · ".join(bits), "unit": "", "reason": None,
                "source": src}

    def _show_oec_planet(self, planet):
        """Map click → the planet dialog, rendered with the panel's live context so
        it carries the same derived rows and units as the tree pane."""
        node = planet.get("node") or {}
        ctx = self._oec_detail_ctx(node) if node.get("tag") else None
        return _show_oec_planet_dialog(self, planet, ctx)

    def _oec_cold_selection(self, system):
        """D10 — the primary host star on build, so the pane paints immediately."""
        if self._oec_hosts:
            host = self._oec_hosts[0]
            return _oec_host_star(host) or host["node"]
        return system

    def _add_architecture_tab(self):
        """Insert the system Architecture map as viz tab 0. Interactive (Phase-3b):
        the map is anchored on ``self._oec_focus`` (None = whole system), star / ◆
        clicks recenter + drive the host tabs, and a breadcrumb + Reset bar sits
        above the canvas. Shown for every matched system (incl. planetless / rogue)."""
        if not mpl_available() or not getattr(self, "_oec_system", None):
            return
        try:
            focus = getattr(self, "_oec_focus", None)
            data = core.viz.prepare_oec_architecture(self._oec_system, focus_node=focus)
            if "error" in data:
                return
            canvas, toolbar = make_oec_architecture_canvas(
                None, data, on_select=self._on_arch_select,
                on_planet_click=self._show_oec_planet)
            if canvas is None:
                return
            self._arch_canvas = canvas
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(2, 2, 2, 2)

            bar = QWidget()
            brow = QHBoxLayout(bar)
            brow.setContentsMargins(2, 2, 2, 2)
            crumb = QLabel(self._arch_breadcrumb(data))
            crumb.setTextFormat(Qt.TextFormat.RichText)
            brow.addWidget(crumb)
            brow.addStretch()
            reset = QPushButton("⟲ Reset diagram")
            reset.setToolTip("Return the map to the whole-system view and default zoom")
            reset.clicked.connect(self._on_arch_reset)
            brow.addWidget(reset)
            lay.addWidget(bar)

            lay.addWidget(toolbar)
            lay.addWidget(canvas, 1)
            self._viz_tabs_widget.insertTab(0, w, "Architecture")
        except Exception:
            log_viz_error("Architecture")

    def _arch_breadcrumb(self, data):
        """Breadcrumb text reflecting the current map focus."""
        sysname = data.get("star_name") or "System"
        if getattr(self, "_oec_focus", None) is None:
            return f"⌂ <b>{sysname}</b> &middot; whole-system barycenter"
        return f"⌂ {sysname} &nbsp;▸&nbsp; <b>{data.get('focus_label', '')}</b>"

    def _on_arch_select(self, node):
        """Map click (Phase-3b): recenter on a star / binary and, when the clicked
        node is a planet host, switch the detail tabs to it (the map replaces the
        Host combo as the selector). Deferred via a 0-timer so the canvas whose
        pick-event is firing isn't torn down mid-callback."""
        self._oec_focus = node
        self._set_oec_selection(node)          # §B.3 — one selection attribute
        host_idx = next(
            (i for i, h in enumerate(self._oec_hosts) if h["node"] is node), None)
        if host_idx is not None and getattr(self, "_host_combo", None) is not None:
            self._host_combo.blockSignals(True)
            self._host_combo.setCurrentIndex(host_idx)
            self._host_combo.blockSignals(False)
        idx = host_idx if host_idx is not None else self._oec_host_idx
        QTimer.singleShot(0, lambda: self._rebuild_after_focus(idx))

    def _on_arch_reset(self):
        """⟲ Reset diagram — restore the map to its default state: drop any click-to-
        recenter focus (back to the whole-system barycenter) AND reset the zoom/pan.
        When already at the whole-system view, this is a pure zoom/pan reset (no
        teardown of the detail tabs); when focused, the focus rebuild restores the
        default view for free."""
        if getattr(self, "_oec_focus", None) is not None:
            self._oec_focus = None
            QTimer.singleShot(0, lambda: self._rebuild_after_focus(self._oec_host_idx))
        else:
            cv = getattr(self, "_arch_canvas", None)
            if cv is not None and hasattr(cv, "reset_view"):
                cv.reset_view()

    def _on_host_changed(self, idx):
        """Host combo change — also recenter the map on that host so map + detail
        stay in sync."""
        self._oec_focus = self._oec_hosts[idx]["node"] if self._oec_hosts else None
        if self._oec_hosts:
            host = self._oec_hosts[idx]
            self._set_oec_selection(_oec_host_star(host) or host["node"])
        self._rebuild_after_focus(idx)

    def _rebuild_after_focus(self, host_idx):
        """Rebuild the detail (Hypatia + diagram) tabs + the Architecture map in place,
        without leaving diagram mode (so a recenter keeps the user on the map). Mirrors
        the host-switch teardown; keeps the Data tree tab at index 0."""
        while self._data_tabs.count() > 1:
            w = self._data_tabs.widget(1)
            self._data_tabs.removeTab(1)
            if w:
                w.deleteLater()
        self._clear_viz_tabs()
        self._add_architecture_tab()
        if self._oec_hosts and host_idx is not None:
            self._oec_host_idx = host_idx
            self._render_host(host_idx)
        self._finish_render()
        # Stay on the Architecture map (viz tab 0) after a recenter / host switch.
        if self._viz_tabs_widget.count():
            self._viz_tabs_widget.setCurrentIndex(0)

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
