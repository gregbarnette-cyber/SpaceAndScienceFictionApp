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
import re

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
                             label_max_ly=None, routes=None):
    """Build a "Star Chart 3D" tab widget with preset viewpoint buttons.

    Mirrors the Map 3D tab pattern but uses the dark-themed
    make_star_chart_3d_canvas helper. Returns (widget, canvas) so the caller can
    keep the canvas ref for O15 row↔map linking. `legend_filter` is opt-in
    (opts 18/19 pass True for O16/CP3 per-class filtering; GCNS keeps False).
    `isochrone` (opts 18/19, O17) switches the reference spheres to travel-time
    contours; GCNS keeps None (distance spheres). `label_max_ly` raises the
    zoom-driven label threshold for sparse charts (the O8 two-star maps).
    `routes` is the Phase-I route overlay (dashed legs / solid MST edges) —
    default None, so opts 18/19 / GCNS are unaffected; the seven Route Planning
    panels pass their edges through it.
    """
    chart3d_w = QWidget()
    chart3d_l = QVBoxLayout(chart3d_w)
    chart3d_l.setContentsMargins(4, 4, 4, 4)
    chart3d_l.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_chart_3d_canvas(
        panel, map_stars, limit_ly=limit_ly, on_star_click=on_star_click,
        legend_filter=legend_filter, isochrone=isochrone,
        label_max_ly=label_max_ly, routes=routes,
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

def _selected_star_name(view, name_col=0):
    """The Star-Name of the table's current/last-selected row, or None.

    Multi-row drag-select → the current (last-interacted) row wins; an empty
    selection → None (clears the highlight). Robust to interactive column sorting
    because it reads the model cell at the current visual row.

    `name_col` (default 0) is the column holding the star name. Opts 18/19 and
    the O8 two-star maps lead with it; the Route Planning tables lead with an
    index column instead (Hop # / Step / Jumps) and pass 1."""
    model = view.model() if view is not None else None
    sel = view.selectionModel() if view is not None else None
    if model is None or sel is None or not sel.selectedRows():
        return None
    idx = sel.currentIndex()
    row = idx.row() if idx.isValid() else sel.selectedRows()[-1].row()
    item = model.item(row, name_col)
    return item.text() if item is not None else None


def _on_link_selection(panel):
    """Table selection changed → ring that star on every map canvas (O15)."""
    name = _selected_star_name(getattr(panel, "_link_view", None),
                               getattr(panel, "_link_name_col", 0))
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
    name_col = getattr(panel, "_link_name_col", 0)
    for r in range(model.rowCount()):
        item = model.item(r, name_col)
        if item is not None and item.text() == name:
            idx = model.index(r, 0)
            view.selectionModel().setCurrentIndex(
                idx,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            view.scrollTo(idx)
            return


def _wire_row_map_linking(panel, view, canvases, name_col=0):
    """Connect a result table to its map canvases, both directions (O15).

    `name_col` is the table column holding the star name (default 0; the Route
    Planning tables pass 1 — they lead with an index column)."""
    panel._link_view = view
    panel._link_canvases = canvases
    panel._link_name_col = name_col
    sm = view.selectionModel() if view is not None else None
    if sm is not None:
        sm.selectionChanged.connect(lambda *a: _on_link_selection(panel))


# ── O18 — Find-Star-on-Map box (depends on O15's highlight) ──────────────────
#
# Lives here rather than in distance_stars.py so the Route Planning panels can
# reach it: distance_stars imports route_planning, so the reverse import would
# be circular. distance_stars re-exports these names for its own callers and
# for the tests that import them from there.

_WS_RE = re.compile(r"\s+")


def _norm_find(s):
    """Whitespace-collapsed, case-folded text for substring matching. Collapsing
    runs of spaces lets a query like `61 Cyg A` match the stored `*  61 Cyg A`."""
    return _WS_RE.sub(" ", (s or "").strip()).lower()


def _dedupe_find_rows(rows):
    """Normalize a `(name, designations)` sequence into the `_find_rows` shape:
    blank names dropped, deduped by name with the first occurrence winning, order
    preserved. Dedupe is load-bearing, not defensive — Multi-Stop and Optimal Tour
    legitimately emit one node per typed stop, so revisiting a star yields the same
    name twice, and the canvases' name-keyed coord maps collapse those to one dot.
    Without this a find would read "1 of 2" while centring the same point twice."""
    out, seen = [], set()
    for name, desig in rows:
        name = name or ""
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((name, desig or ""))
    return out


def _find_rows_from_table(panel):
    """Build `_find_rows` from the linked result table: the star-name column
    (`_link_name_col`) plus the column immediately after it (designations). This
    is the opts-18/19 shape (name_col 0 → designations in 1)."""
    view = getattr(panel, "_link_view", None)
    model = view.model() if view is not None else None
    if model is None:
        return []
    nc = getattr(panel, "_link_name_col", 0)
    dc = nc + 1
    rows = []
    for r in range(model.rowCount()):
        nm_item = model.item(r, nc)
        nm = nm_item.text() if nm_item is not None else ""
        dz_item = model.item(r, dc) if model.columnCount() > dc else None
        dz = dz_item.text() if dz_item is not None else ""
        rows.append((nm, dz))
    return _dedupe_find_rows(rows)


def _find_on_map(panel):
    """Find a star by substring (name OR designations) over `panel._find_rows` and
    centre + ring it on every map (O18). Repeating the same query cycles matches;
    a new query restarts at the first. No match → status-bar message, no view
    change. A found star whose spectral class is legend-filtered off is revealed
    first, so find never centres on an invisible dot.

    `_find_rows` — not the result table — is the searchable set, so the four
    leg-shaped Route Planning panels (whose tables are `From|To` rows, not one row
    per star) are searchable too. When the panel *does* have a linked per-star
    table the row is additionally selected and scrolled to (the O15 gesture), but
    the ring is applied directly to every canvas either way: table selection is an
    extra, not the mechanism."""
    inp = getattr(panel, "_find_input", None)
    raw = inp.text().strip() if inp is not None else ""
    q = _norm_find(raw)
    if not q:
        return
    # Table-sourced panels (opts 18/19) re-derive on every find rather than using
    # the render-time snapshot: `make_table` enables sorting and `QStandardItemModel`
    # physically reorders rows, so a snapshot would cycle matches in render order
    # while the user is looking at a sorted table. The old live scan followed the
    # sort; keep that.
    #
    # Route panels never set the flag — including Nearest-Neighbor, Farthest-First
    # and Jump Network, which DO render sortable per-star tables. It is not that
    # they have no table to follow: their searchable set is the route star list by
    # design (D2), which is what covers the four leg-shaped panels, and re-deriving
    # from the table would change the *set*, not just its order — Jump Network's
    # table carries the start (tier 0), which D6 deliberately excludes. The visible
    # consequence is that after a user sorts one of those three tables the ring
    # cycles in route order (hop / step / tier) while `_star_click_select` scrolls
    # the selection non-monotonically. Route order is the more meaningful cycle on
    # a route panel, so this is the intended trade, not an oversight.
    if getattr(panel, "_find_rows_live", False):
        panel._find_rows = _find_rows_from_table(panel)
    find_rows = getattr(panel, "_find_rows", None) or []
    if not find_rows:
        return

    matches = [nm for nm, dz in find_rows
               if q in _norm_find(nm) or q in _norm_find(dz)]

    readout = getattr(panel, "_find_readout", None)
    if not matches:
        panel._find_matches = []
        if readout is not None:
            readout.setText("No match")
        try:
            panel.set_status(f"No star matching '{raw}' on the map.")
        except Exception:
            pass
        return

    if matches != getattr(panel, "_find_matches", None):
        panel._find_matches = matches
        panel._find_idx = 0
    else:
        panel._find_idx = (panel._find_idx + 1) % len(matches)
    name = matches[panel._find_idx]

    # Reveal a legend-hidden class first (so the dot/ring are visible), then
    # select the matching table row if there is one, then ring + centre each map.
    for c in getattr(panel, "_link_canvases", ()):
        reveal = getattr(c, "_o16_reveal_class", None)
        cls = getattr(c, "_o16_name_cls", {}).get(name)
        if reveal is not None and cls:
            try:
                reveal(cls)
            except Exception:
                pass
    # O15 extra: only the star-per-row panels have a linked table. `_star_click_select`
    # no-ops without one, so this is a nicety — the ring below is the mechanism.
    _star_click_select(panel, name)
    for c in getattr(panel, "_link_canvases", ()):
        try:
            c.highlight_star(name)
        except Exception:
            pass
        center = getattr(c, "center_on", None)
        if center is not None:
            try:
                center(name)
            except Exception:
                pass

    n = len(matches)
    msg = (f"{panel._find_idx + 1} of {n} matches — {name}" if n > 1
           else f"Found: {name}")
    if readout is not None:
        readout.setText(msg)
    try:
        panel.set_status(msg)
    except Exception:
        pass


def _clear_find(panel):
    """Reset the O18 Find box: empty the search field + readout, reset the cycle
    state, drop the found-star highlight (deselect on every map), and restore each
    map to the view it had before find started centring."""
    inp = getattr(panel, "_find_input", None)
    if inp is not None:
        inp.clear()
    readout = getattr(panel, "_find_readout", None)
    if readout is not None:
        readout.setText("")
    panel._find_matches = []
    panel._find_idx = 0
    _star_click_select(panel, None)   # clears the selection → ring off (linked panels)
    for c in getattr(panel, "_link_canvases", ()):
        try:
            c.highlight_star(None)    # …and directly, for the unlinked ones
        except Exception:
            pass
        reset = getattr(c, "reset_view", None)
        if reset is not None:
            try:
                reset()
            except Exception:
                pass


def _add_find_box(panel, rows=None):
    """Insert the O18 Find box above the map tabs (once per viz container). Resets
    the cycle state on every render so a fresh result starts clean.

    `rows` is the searchable `(name, designations)` set — the Route Planning panels
    pass their route star list, so the leg-shaped ones are searchable too. Omitted
    (opts 18/19) it is derived from the linked result table. Either way it is
    deduped by name; an empty set means there is nothing to find, so no box is
    added."""
    cont = getattr(panel, "_viz_container", None)
    if cont is None:
        return
    panel._find_rows_live = rows is None      # table-sourced → re-derive per find
    panel._find_rows = (_dedupe_find_rows(rows) if rows is not None
                        else _find_rows_from_table(panel))
    if not panel._find_rows:
        return
    panel._find_matches = []
    panel._find_idx = 0
    existing = getattr(panel, "_find_widget", None)
    # `_find_widget` is a panel-level attribute that survives reset() as a
    # dangling reference: reset() deletes the old container via deleteLater(),
    # and the real event loop's DeferredDelete pass frees the old find widget's
    # C++ object. Touching a freed widget (even `.parent()`) raises RuntimeError,
    # which would abort _render() before _finish_render() — leaving the table
    # visible but the "Show Diagrams" button hidden. Treat a freed/mismatched
    # widget as stale and rebuild a fresh box.
    try:
        reuse = existing is not None and existing.parent() is cont
    except RuntimeError:
        reuse = False
    if reuse:
        # Load-bearing: `_prepare_render` hides the box at the start of every
        # render, so this is what brings it back for a result that has one.
        existing.show()
        if getattr(panel, "_find_input", None) is not None:
            panel._find_input.clear()
        if getattr(panel, "_find_readout", None) is not None:
            panel._find_readout.setText("")
        return

    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 2)
    row.addWidget(QLabel("Find star:"))
    panel._find_input = QLineEdit()
    panel._find_input.setMaximumWidth(180)
    panel._find_input.setPlaceholderText("name or designation")
    find_btn = QPushButton("Find")
    clear_btn = QPushButton("Clear")
    panel._find_readout = QLabel("")
    panel._find_readout.setStyleSheet("color: #3a73ad;")
    row.addWidget(panel._find_input)
    row.addWidget(find_btn)
    row.addWidget(clear_btn)
    row.addWidget(panel._find_readout)
    row.addStretch()
    find_btn.clicked.connect(lambda: _find_on_map(panel))
    panel._find_input.returnPressed.connect(lambda: _find_on_map(panel))
    clear_btn.clicked.connect(lambda: _clear_find(panel))
    panel._find_widget = w
    # Insert just below the "Show Tables" button row, above the tabs widget.
    cont.layout().insertWidget(1, w)


_ISO_HOURS_PER_JULIAN_YEAR = 8765.8128   # ×c → ly/hr (matches core + plot_helpers)


def _build_iso_chart_tab(panel, map_stars, limit, click_cb, canvases, is_3d,
                         label_max_ly=None, routes=None, legend_filter=True):
    """Star Chart (2D or 3D) tab with an O17 travel-time isochrone control.

    A velocity field + unit (× c | LY/HR) + Apply/Clear sits above the chart;
    Apply rebuilds the canvas with travel-time rings (d = v·t), Clear / blank
    restores the distance rings. The rebuilt canvas replaces the old one in
    `canvases` (the O15 link list) and inherits the current highlight, so row↔map
    linking and the gold selection ring survive the rebuild.

    `label_max_ly` (default None → the shared 15 ly threshold) raises the
    zoom-driven star-label cutoff; the O8 two-star maps pass a large value so
    their handful of dots stay labelled at any zoom.

    `routes` (default None) is the Phase-I route overlay, re-passed on every
    isochrone rebuild so the legs survive it. `legend_filter` (default True) is
    the O16 per-class legend; JumpNetworkPanel passes False because it paints
    per-TIER colours, which the class-grouped legend would mislabel."""
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
                legend_filter=legend_filter, isochrone=iso,
                label_max_ly=label_max_ly, routes=routes)
            hl.addWidget(inner_w)
        else:
            new_canvas, new_toolbar = make_star_chart_canvas(
                panel, map_stars, limit_ly=limit, on_star_click=click_cb,
                legend_filter=legend_filter, isochrone=iso,
                label_max_ly=label_max_ly, routes=routes)
            hl.addWidget(new_toolbar)
            hl.addWidget(new_canvas)
        state["canvas"] = new_canvas
        canvases.append(new_canvas)
        if prev_hl:
            try:
                new_canvas.highlight_star(prev_hl)
            except Exception:
                pass
        # D9 — the rebuilt canvas gets a fresh `view0`, so any O18 find cycle in
        # flight is stale: leaving `_find_idx` set would make the next identical
        # Find *advance* the cycle instead of re-centring, and a later Clear would
        # silently fail to restore the view (reset_view() returns False with no
        # captured lims). Reset the cycle, not the highlight.
        #
        # The readout goes with it: the chart has just been rebuilt at its default
        # un-centred view and the cycle is back at 0, so a leftover "2 of 3
        # matches — Wolf 359" would be describing a state that no longer exists,
        # and the next Find with that query re-centres match *1*. The query itself
        # stays in the box — it is still what the user wants to search for.
        panel._find_matches = []
        panel._find_idx = 0
        ro = getattr(panel, "_find_readout", None)
        if ro is not None:
            try:
                ro.setText("")
            except RuntimeError:
                pass

    def _clear():
        vel.clear()
        _rebuild()

    apply_btn.clicked.connect(_rebuild)
    vel.returnPressed.connect(_rebuild)
    clear_btn.clicked.connect(_clear)

    _rebuild()   # initial build → distance rings (no velocity yet)
    return w
