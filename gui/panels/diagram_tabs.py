# gui/panels/diagram_tabs.py — shared diagram-tab builders for the Star Databases panels.
#
# Stateless QWidget factories: each takes (panel, planets) — `planets` being a list of
# dicts with NASA-style keys (`pl_orbsmax`/`pl_orbeccen`/`pl_orbincl`/`pl_bmasse`/`pl_rade`,
# and `st_teff`/`st_rad`/`st_spectype`/`hostname` on each row) — and returns an embedded
# matplotlib tab QWidget, or None when the data is insufficient. All chart drawing lives in
# `core.viz` (prep) + `gui.visualizations.plot_helpers` (canvas); these just wire prep→canvas
# →tab. Shared by the NASA panels (opts 3/4/5) and OecPanel (opt 7, which adapts OEC nodes
# to these keys). Extracted from nasa_exoplanet.py so no panel imports another panel's privates.

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup,
    QStackedWidget, QLineEdit, QComboBox,
)
from PySide6.QtCore import Qt, QItemSelectionModel

import core.viz
import core.science
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_hz_strip_canvas, make_orbits_canvas,
    make_mass_radius_canvas, make_transit_canvas, make_size_comparison_canvas,
    wrap_orbits_with_solar_toggle,
    make_star_chart_canvas, make_star_chart_3d_canvas, _isochrone_rings,
)


# ── Phase 5: the shared HZ Rings/Strip toggle ────────────────────────────────────
# One control, wired into every panel's HZ Diagram tab. Rings is the default and its
# canvas (make_hz_canvas) is unchanged; Strip is the opt-in √AU view with planet-SMA
# markers. Both share the light HZ palette so they read as one tab.

_HZ_TOGGLE_QSS = """
QWidget#hzToggleBar QPushButton {
    padding: 3px 14px; border: 1px solid #b9c2d0; background: #f4f6fa;
    color: #465063; font-size: 12px;
}
QWidget#hzToggleBar QPushButton:first-child { border-top-left-radius: 6px; border-bottom-left-radius: 6px; }
QWidget#hzToggleBar QPushButton:last-child  { border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none; }
QWidget#hzToggleBar QPushButton:checked { background: #2f9e5a; color: #ffffff; border-color: #268a4d; }
"""


def _wrap_canvas_tab(canvas, toolbar):
    """A QWidget holding a matplotlib toolbar + canvas (the standard diagram-tab body)."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def wrap_hz_with_toggle(build_rings, build_strip):
    """Return a QWidget: a **Rings | Strip** segmented control over a QStackedWidget,
    Rings selected by default. `build_rings()` / `build_strip()` are zero-arg factories
    each returning a QWidget (or None). If Rings can't build → None; if Strip can't build
    → the bare Rings widget (no toggle) so nothing regresses."""
    rings_w = build_rings()
    if rings_w is None:
        return None
    strip_w = build_strip()
    if strip_w is None:
        return rings_w   # no strip (e.g. bands not computable) → plain rings, no toggle

    container = QWidget()
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(3)

    bar = QWidget()
    bar.setObjectName("hzToggleBar")
    bar.setStyleSheet(_HZ_TOGGLE_QSS)
    row = QHBoxLayout(bar)
    row.setContentsMargins(6, 4, 6, 0)
    row.setSpacing(0)
    lbl = QLabel("HZ view:")
    lbl.setContentsMargins(0, 0, 8, 0)
    row.addWidget(lbl)
    grp = QButtonGroup(container)
    grp.setExclusive(True)
    rings_btn = QPushButton("Rings")
    strip_btn = QPushButton("Strip")
    for b in (rings_btn, strip_btn):
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        grp.addButton(b)
        row.addWidget(b)
    rings_btn.setChecked(True)
    row.addStretch()
    v.addWidget(bar)

    stack = QStackedWidget()
    stack.addWidget(rings_w)   # index 0 (default)
    stack.addWidget(strip_w)   # index 1
    v.addWidget(stack, 1)

    rings_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
    strip_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
    return container


def _hz_toggle_tab(panel, teff, lum, title, eeid_au=None, planets=None, markers=None):
    """Build the HZ Diagram tab as a Rings/Strip toggle (Rings default). `planets` is a
    list of {"name","au"} for the strip markers ([] / None for single-star panels →
    bands only). Returns a QWidget, or None when the HZ isn't computable."""
    if not mpl_available():
        return None
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None

    def build_rings():
        canvas, toolbar = make_hz_canvas(
            panel, hz_data["zones"], hz_data["max_au"],
            title=title, eeid_au=eeid_au, markers=markers)
        return _wrap_canvas_tab(canvas, toolbar)

    def build_strip():
        strip = core.viz.prepare_hz_strip(teff, lum, planets)
        if "error" in strip:
            return None
        canvas, toolbar = make_hz_strip_canvas(
            panel, strip, title=title, eeid_au=eeid_au, markers=markers)
        if canvas is None:
            return None
        return _wrap_canvas_tab(canvas, toolbar)

    return wrap_hz_with_toggle(build_rings, build_strip)


def _fval(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _make_hz_tab(panel, rows_or_row):
    """Return the HZ Diagram tab (Rings/Strip toggle), or None if data is missing.
    NASA planet rows carry `pl_orbsmax`, so the Strip view gets planet-SMA markers."""
    if not mpl_available():
        return None
    rows = rows_or_row if isinstance(rows_or_row, list) else [rows_or_row or {}]
    row = rows[0] if rows else {}
    teff   = _fval(row.get("st_teff"))
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
    planets = []
    for r in rows:
        au = _fval(r.get("pl_orbsmax"))
        if au:
            planets.append({"name": r.get("pl_name") or "planet", "au": au})
    return _hz_toggle_tab(
        panel, teff, lum,
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=_fval(row.get("st_eei_orbsep")), planets=planets)


def _make_hz_tab_exocat(panel, row):
    """HZ tab for Mission Exocat rows (uses st_teff / st_rad; eeid from st_eeidau).
    Star-level row → the Strip shows bands only (no per-planet SMA)."""
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
    return _hz_toggle_tab(
        panel, teff, lum,
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=_fval(row.get("st_eeidau")), planets=[])


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

    # Phase P V6/V7: snow-line + solvent-zone overlays from the host luminosity.
    ov = core.viz.prepare_orbit_overlays(orbit_data.get("luminosity"))
    snow_au = ov.get("snow_au")
    solvent_options = ov.get("solvent_options")

    def _build(solar_overlay, show_hyper, snow, solvent_bands):
        return make_orbits_canvas(
            panel,
            orbit_data["orbits"],
            orbit_data["hz_zones"],
            orbit_data["max_au"],
            star_name=star_name,
            solar_overlay=solar_overlay,
            hyper_au=hyper_au if show_hyper else None,
            snow_au=snow,
            solvent_bands=solvent_bands,
        )

    return wrap_orbits_with_solar_toggle(
        panel, _build, hyper_au=hyper_au,
        snow_au=snow_au, solvent_options=solvent_options)


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


# ── Star Chart tab builders (opts 17/18/19/20/21) ────────────────────────────
# Moved here from distance_stars.py so the two-star panels (opts 17/20/21, via
# route_planning.add_two_star_chart_tabs) can reuse the exact opt-18/19 builders
# without a circular panel import. Behaviour is unchanged by the move.

def _build_star_chart_3d_tab(panel, map_stars, limit_ly, on_star_click=None,
                             legend_filter=False, isochrone=None,
                             label_max_ly=None):
    """Build a "Star Chart 3D" tab widget with preset viewpoint buttons.

    Mirrors the Map 3D tab pattern but uses the dark-themed
    make_star_chart_3d_canvas helper. Returns (widget, canvas) so the caller can
    keep the canvas ref for O15 row↔map linking. `legend_filter` is opt-in
    (opts 18/19 pass True for O16/CP3 per-class filtering; GCNS keeps False).
    `isochrone` (opts 18/19, O17) switches the reference spheres to travel-time
    contours; GCNS keeps None (distance spheres). `label_max_ly` raises the
    zoom-driven label threshold for sparse charts (the O8 two-star maps).
    """
    chart3d_w = QWidget()
    chart3d_l = QVBoxLayout(chart3d_w)
    chart3d_l.setContentsMargins(4, 4, 4, 4)
    chart3d_l.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_chart_3d_canvas(
        panel, map_stars, limit_ly=limit_ly, on_star_click=on_star_click,
        legend_filter=legend_filter, isochrone=isochrone,
        label_max_ly=label_max_ly,
    )
    preset_bar = QWidget()
    preset_bar.setFixedHeight(18)
    preset_row = QHBoxLayout(preset_bar)
    preset_row.setContentsMargins(0, 0, 0, 0)
    preset_row.setSpacing(6)
    _preset_btn_style = (
        "QPushButton { padding: 0px 8px; margin: 0px; font-size: 10px; }"
    )
    for lbl, elev, azim in [
        ("Top View", 90, 0),
        ("Side View", 0, 0),
        ("3D Perspective", 30, -60),
    ]:
        btn = QPushButton(lbl)
        btn.setFixedHeight(18)
        btn.setStyleSheet(_preset_btn_style)
        def _make_cb(e=elev, a=azim):
            def _cb():
                try:
                    if toolbar3d.mode:
                        if "zoom rect" in str(toolbar3d.mode):
                            toolbar3d.zoom()
                        else:
                            toolbar3d.pan()
                except Exception:
                    pass
                ax3d.view_init(elev=e, azim=a)
                canvas3d.draw_idle()
            return _cb
        btn.clicked.connect(_make_cb())
        preset_row.addWidget(btn)
    preset_row.addStretch()
    chart3d_l.addWidget(preset_bar)
    chart3d_l.addWidget(toolbar3d)
    chart3d_l.addWidget(canvas3d)
    return chart3d_w, canvas3d


# ── O15 — Table-Row ↔ Map Linking (opts 18/19, all five map tabs) ─────────────

def _selected_star_name(view):
    """The Star-Name (column 0) of the table's current/last-selected row, or None.

    Multi-row drag-select → the current (last-interacted) row wins; an empty
    selection → None (clears the highlight). Robust to interactive column sorting
    because it reads the model cell at the current visual row."""
    model = view.model() if view is not None else None
    sel = view.selectionModel() if view is not None else None
    if model is None or sel is None or not sel.selectedRows():
        return None
    idx = sel.currentIndex()
    row = idx.row() if idx.isValid() else sel.selectedRows()[-1].row()
    item = model.item(row, 0)
    return item.text() if item is not None else None


def _on_link_selection(panel):
    """Table selection changed → ring that star on every map canvas (O15)."""
    name = _selected_star_name(getattr(panel, "_link_view", None))
    for canvas in getattr(panel, "_link_canvases", ()):
        try:
            canvas.highlight_star(name)
        except Exception:
            pass


def _star_click_select(panel, name):
    """Map star clicked → select + scroll to the matching table row (O15).

    The selection change then rings the star on every canvas via
    _on_link_selection. A click on the centre ★ (Sol / queried star, which has no
    table row) matches nothing and is a graceful no-op. Called with a falsy name
    (empty-space click) it clears the table selection, which clears the ring on
    every canvas — the deselect gesture."""
    view = getattr(panel, "_link_view", None)
    model = view.model() if view is not None else None
    if model is None:
        return
    if not name:
        sm = view.selectionModel()
        if sm is not None:
            sm.clearSelection()      # → selectionChanged → highlight_star(None) everywhere
        return
    for r in range(model.rowCount()):
        item = model.item(r, 0)
        if item is not None and item.text() == name:
            idx = model.index(r, 0)
            view.selectionModel().setCurrentIndex(
                idx,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            view.scrollTo(idx)
            return


def _wire_row_map_linking(panel, view, canvases):
    """Connect a result table to its map canvases, both directions (O15)."""
    panel._link_view = view
    panel._link_canvases = canvases
    sm = view.selectionModel() if view is not None else None
    if sm is not None:
        sm.selectionChanged.connect(lambda *a: _on_link_selection(panel))


_ISO_HOURS_PER_JULIAN_YEAR = 8765.8128   # ×c → ly/hr (matches core + plot_helpers)


def _build_iso_chart_tab(panel, map_stars, limit, click_cb, canvases, is_3d,
                         label_max_ly=None):
    """Star Chart (2D or 3D) tab with an O17 travel-time isochrone control.

    A velocity field + unit (× c | LY/HR) + Apply/Clear sits above the chart;
    Apply rebuilds the canvas with travel-time rings (d = v·t), Clear / blank
    restores the distance rings. The rebuilt canvas replaces the old one in
    `canvases` (the O15 link list) and inherits the current highlight, so row↔map
    linking and the gold selection ring survive the rebuild.

    `label_max_ly` (default None → the shared 15 ly threshold) raises the
    zoom-driven star-label cutoff; the O8 two-star maps pass a large value so
    their handful of dots stay labelled at any zoom."""
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(4, 4, 4, 4)
    outer.setSpacing(3)

    ctl = QHBoxLayout()
    ctl.setContentsMargins(0, 0, 0, 0)
    ctl.addWidget(QLabel("Isochrone velocity:"))
    vel = QLineEdit()
    vel.setMaximumWidth(90)
    vel.setPlaceholderText("blank = distance")
    unit = QComboBox()
    unit.addItems(["× c", "LY/HR"])
    apply_btn = QPushButton("Apply")
    clear_btn = QPushButton("Clear")
    for ww in (vel, unit, apply_btn, clear_btn):
        ctl.addWidget(ww)
    ctl.addStretch()
    outer.addLayout(ctl)

    holder = QWidget()
    hl = QVBoxLayout(holder)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(0)
    outer.addWidget(holder, 1)

    state = {"canvas": None}

    def _iso_kwarg():
        raw = vel.text().strip()
        if not raw:
            return None
        try:
            v = float(raw)
            if v <= 0:
                raise ValueError
        except ValueError:
            try:
                panel.set_status("Isochrone velocity must be a positive number.")
            except Exception:
                pass
            return None
        ly_hr = (v / _ISO_HOURS_PER_JULIAN_YEAR
                 if unit.currentText().startswith("×") else v)
        return {"ly_hr": ly_hr, "label_unit": f"{ly_hr:.4f} ly/hr"}

    def _rebuild():
        iso = _iso_kwarg()
        if iso is not None and not _isochrone_rings(iso["ly_hr"], limit):
            # Velocity valid but too fast for this range — even the 1-hour ring
            # overshoots, so the chart shows distance rings. Tell the user why.
            try:
                panel.set_status(
                    f"{iso['ly_hr']:.4f} ly/hr is too fast for a {limit:g} ly "
                    f"chart — no travel-time rings fit; showing distance rings.")
            except Exception:
                pass
        old = state["canvas"]
        prev_hl = None
        if old is not None:
            try:
                prev_hl = old.highlighted_star()
            except Exception:
                prev_hl = None
            if old in canvases:
                canvases.remove(old)
        while hl.count():
            item = hl.takeAt(0)
            ww = item.widget()
            if ww:
                ww.deleteLater()
        if is_3d:
            inner_w, new_canvas = _build_star_chart_3d_tab(
                panel, map_stars, limit, on_star_click=click_cb,
                legend_filter=True, isochrone=iso, label_max_ly=label_max_ly)
            hl.addWidget(inner_w)
        else:
            new_canvas, new_toolbar = make_star_chart_canvas(
                panel, map_stars, limit_ly=limit, on_star_click=click_cb,
                legend_filter=True, isochrone=iso, label_max_ly=label_max_ly)
            hl.addWidget(new_toolbar)
            hl.addWidget(new_canvas)
        state["canvas"] = new_canvas
        canvases.append(new_canvas)
        if prev_hl:
            try:
                new_canvas.highlight_star(prev_hl)
            except Exception:
                pass

    def _clear():
        vel.clear()
        _rebuild()

    apply_btn.clicked.connect(_rebuild)
    vel.returnPressed.connect(_rebuild)
    clear_btn.clicked.connect(_clear)

    _rebuild()   # initial build → distance rings (no velocity yet)
    return w
