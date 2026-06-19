# gui/panels/distance_stars.py — Options 17, 18, 19: star distance and proximity.
# Each option has its own standalone panel.

import re

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QSizePolicy, QTabWidget, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt, QItemSelectionModel

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_star_map_canvas, make_star_map_3d_canvas,
    make_star_chart_canvas, make_star_chart_3d_canvas,
    make_hr_canvas, make_sky_canvas, _isochrone_rings,
)
from gui.panels.route_planning import add_two_star_chart_tabs


# ── Option 17: Distance Between 2 Stars ──────────────────────────────────────

class DistanceBetweenStarsPanel(DiagramToggleMixin, ResultPanel):
    """Two star name inputs → distance in light years + Star Chart  (option 17)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._star1 = QLineEdit()
        self._star1.setPlaceholderText("e.g. Sol, Vega, Alpha Centauri")
        form.addRow("Star 1:", self._star1)

        self._star2 = QLineEdit()
        self._star2.setPlaceholderText("e.g. Epsilon Eridani, HD 10700")
        form.addRow("Star 2:", self._star2)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._star2.returnPressed.connect(self._calculate)
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
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()
        self._input_count = self._layout.count()

    def _calculate(self):
        s1 = self._star1.text().strip()
        s2 = self._star2.text().strip()
        if not s1 or not s2:
            return
        self._prepare_render()
        _clear_tables_layout(self)
        self.run_in_background(
            core.calculators.compute_distance_between_stars,
            s1, s2,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        s1 = result["star1_info"]
        s2 = result["star2_info"]

        dist_ly = result["distance_ly"]
        dist_au = result.get("distance_au")
        dist_text = f"<b>Distance:</b> {dist_ly:.4f} Light Years"
        if dist_au is not None:
            dist_text += f"  /  {dist_au:.2f} AU"
        lbl = QLabel(dist_text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._tables_layout.addWidget(lbl)

        headers = ["Star", "Star Designations", "RA", "DEC", "Light Years"]
        rows = [
            [s1["name"], s1["desig_str"],
             s1.get("ra_hms", ""), s1.get("dec_dms", ""), f"{s1['ly']:.4f}"],
            [s2["name"], s2["desig_str"],
             s2.get("ra_hms", ""), s2.get("dec_dms", ""), f"{s2['ly']:.4f}"],
        ]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        self._tables_layout.addWidget(table)

        add_two_star_chart_tabs(self, result, "distance")
        self._finish_render()


# ── Shared build helper for opts 18, 19 ──────────────────────────────────────

def _build_results_area_distance(panel):
    """Create _tables_widget + diagram view for distance-star panels."""
    panel._tables_widget = QWidget()
    panel._tables_layout = QVBoxLayout(panel._tables_widget)
    panel._tables_layout.setContentsMargins(0, 0, 0, 0)
    panel._layout.addWidget(panel._tables_widget, 1)
    panel._setup_diagram_view()
    panel._input_count = panel._layout.count()


def _clear_tables_layout(panel):
    lay = panel._tables_layout
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _build_star_chart_3d_tab(panel, map_stars, limit_ly, on_star_click=None,
                             legend_filter=False, isochrone=None):
    """Build a "Star Chart 3D" tab widget with preset viewpoint buttons.

    Mirrors the Map 3D tab pattern but uses the dark-themed
    make_star_chart_3d_canvas helper. Returns (widget, canvas) so the caller can
    keep the canvas ref for O15 row↔map linking. `legend_filter` is opt-in
    (opts 18/19 pass True for O16/CP3 per-class filtering; GCNS keeps False).
    `isochrone` (opts 18/19, O17) switches the reference spheres to travel-time
    contours; GCNS keeps None (distance spheres).
    """
    chart3d_w = QWidget()
    chart3d_l = QVBoxLayout(chart3d_w)
    chart3d_l.setContentsMargins(4, 4, 4, 4)
    chart3d_l.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_chart_3d_canvas(
        panel, map_stars, limit_ly=limit_ly, on_star_click=on_star_click,
        legend_filter=legend_filter, isochrone=isochrone,
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


# ── O18 — Find-Star-on-Map box (opts 18/19; depends on O15's highlight) ───────

_WS_RE = re.compile(r"\s+")


def _norm_find(s):
    """Whitespace-collapsed, case-folded text for substring matching. Collapsing
    runs of spaces lets a query like `61 Cyg A` match the stored `*  61 Cyg A`."""
    return _WS_RE.sub(" ", (s or "").strip()).lower()


def _find_on_map(panel):
    """Find a star by substring (name OR designations) across the result table and
    centre + ring it on every map (O18). Repeating the same query cycles matches;
    a new query restarts at the first. No match → status-bar message, no view
    change. A found star whose spectral class is legend-filtered off is revealed
    first, so find never centres on an invisible dot."""
    inp = getattr(panel, "_find_input", None)
    raw = inp.text().strip() if inp is not None else ""
    q = _norm_find(raw)
    if not q:
        return
    view = getattr(panel, "_link_view", None)
    model = view.model() if view is not None else None
    if model is None:
        return

    matches = []
    for r in range(model.rowCount()):
        nm_item = model.item(r, 0)
        nm = nm_item.text() if nm_item is not None else ""
        dz_item = model.item(r, 1) if model.columnCount() > 1 else None
        dz = dz_item.text() if dz_item is not None else ""
        if q in _norm_find(nm) or q in _norm_find(dz):
            matches.append(nm)

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
    # select the row (rings every canvas via O15) and centre each map on it.
    for c in getattr(panel, "_link_canvases", ()):
        reveal = getattr(c, "_o16_reveal_class", None)
        cls = getattr(c, "_o16_name_cls", {}).get(name)
        if reveal is not None and cls:
            try:
                reveal(cls)
            except Exception:
                pass
    _star_click_select(panel, name)
    for c in getattr(panel, "_link_canvases", ()):
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
    _star_click_select(panel, None)   # clears the selection → ring off everywhere
    for c in getattr(panel, "_link_canvases", ()):
        reset = getattr(c, "reset_view", None)
        if reset is not None:
            try:
                reset()
            except Exception:
                pass


def _add_find_box(panel):
    """Insert the O18 Find box above the map tabs (once per viz container). Resets
    the cycle state on every render so a fresh result starts clean."""
    cont = getattr(panel, "_viz_container", None)
    if cont is None:
        return
    panel._find_matches = []
    panel._find_idx = 0
    existing = getattr(panel, "_find_widget", None)
    if existing is not None and existing.parent() is cont:
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


def _build_iso_chart_tab(panel, map_stars, limit, click_cb, canvases, is_3d):
    """Star Chart (2D or 3D) tab with an O17 travel-time isochrone control.

    A velocity field + unit (× c | LY/HR) + Apply/Clear sits above the chart;
    Apply rebuilds the canvas with travel-time rings (d = v·t), Clear / blank
    restores the distance rings. The rebuilt canvas replaces the old one in
    `canvases` (the O15 link list) and inherits the current highlight, so row↔map
    linking and the gold selection ring survive the rebuild."""
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
                legend_filter=True, isochrone=iso)
            hl.addWidget(inner_w)
        else:
            new_canvas, new_toolbar = make_star_chart_canvas(
                panel, map_stars, limit_ly=limit, on_star_click=click_cb,
                legend_filter=True, isochrone=iso)
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


def _add_map_tabs(panel, map_stars, limit, title):
    """Build the five opt-18/19 map tabs (Map X–Y/X–Z/3D, Star Chart, Star Chart
    3D) and wire O15 row↔map linking. Appends tabs to panel._viz_tabs_widget and
    expects panel._link_view to already hold the result table."""
    canvases = []
    click_cb = lambda nm: _star_click_select(panel, nm)

    # Map X–Y / X–Z (light-gray 2D scatter).
    for proj, xk, yk, xl, yl in [
        ("X–Y (top-down)", "x", "y", "X (ly)", "Y (ly)"),
        ("X–Z (edge-on)",  "x", "z", "X (ly)", "Z (ly)"),
    ]:
        map_w = QWidget()
        map_l = QVBoxLayout(map_w)
        map_l.setContentsMargins(4, 4, 4, 4)
        canvas, toolbar = make_star_map_canvas(
            panel, map_stars, title=title,
            xk=xk, yk=yk, xlabel=xl, ylabel=yl, bg="#ebebeb",
            on_star_click=click_cb, legend_filter=True,
        )
        map_l.addWidget(toolbar)
        map_l.addWidget(canvas)
        panel._viz_tabs_widget.addTab(map_w, f"Map {proj}")
        canvases.append(canvas)

    # Map 3D with viewpoint preset buttons.
    map3d_w = QWidget()
    map3d_l = QVBoxLayout(map3d_w)
    map3d_l.setContentsMargins(4, 4, 4, 4)
    map3d_l.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_map_3d_canvas(
        panel, map_stars, title=title, bg="#ebebeb", on_star_click=click_cb,
        legend_filter=True,
    )
    preset_bar = QWidget()
    preset_bar.setFixedHeight(24)
    preset_row = QHBoxLayout(preset_bar)
    preset_row.setContentsMargins(0, 0, 0, 0)
    preset_row.setSpacing(6)
    for lbl, elev, azim in [
        ("Top View", 90, 0),
        ("Side View", 0, 0),
        ("3D Perspective", 30, -60),
    ]:
        btn = QPushButton(lbl)
        btn.setFixedHeight(24)
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
    map3d_l.addWidget(preset_bar)
    map3d_l.addWidget(toolbar3d)
    map3d_l.addWidget(canvas3d)
    panel._viz_tabs_widget.addTab(map3d_w, "Map 3D")
    canvases.append(canvas3d)

    # Labeled X-Y star chart (dark theme) + O17 isochrone control. The helper
    # appends the live canvas to `canvases` (and re-appends on each Apply rebuild).
    chart_w = _build_iso_chart_tab(panel, map_stars, limit, click_cb,
                                   canvases, is_3d=False)
    panel._viz_tabs_widget.addTab(chart_w, "Star Chart")

    # Star Chart 3D — labeled 3D companion + O17 isochrone control.
    chart3d_w = _build_iso_chart_tab(panel, map_stars, limit, click_cb,
                                     canvases, is_3d=True)
    panel._viz_tabs_widget.addTab(chart3d_w, "Star Chart 3D")

    _wire_row_map_linking(panel, panel._link_view, canvases)
    _add_find_box(panel)


def _add_hr_tab(panel, result):
    """Phase O · O2b — add an 'HR Diagram' viz tab: the main-sequence reference line
    plus this result's stars overlaid. Silently skipped if the MS table is empty."""
    ref = core.viz.prepare_hr_main_sequence()
    if not isinstance(ref, dict) or "error" in ref:
        return
    overlay = core.viz.prepare_hr_from_stars(result)
    ov_points = overlay.get("points") if isinstance(overlay, dict) else None
    canvas, toolbar = make_hr_canvas(panel, ref, overlay_points=ov_points)
    w = QWidget()
    wl = QVBoxLayout(w)
    wl.setContentsMargins(4, 4, 4, 4)
    wl.addWidget(toolbar)
    wl.addWidget(canvas)
    panel._viz_tabs_widget.addTab(w, "HR Diagram")


def _add_night_sky_tab(panel, result):
    """Phase O · O1 — add a 'Night Sky' viz tab (opts 18 & 19) with a re-runnable
    magnitude limit; recomputes prepare_sky_from_star on the cached result (no new
    query). Vantage = the queried centre star (opt 19) or Sol (opt 18)."""
    panel._sky_result = result
    w = QWidget()
    wl = QVBoxLayout(w)
    wl.setContentsMargins(4, 4, 4, 4)
    wl.setSpacing(4)

    ctl = QHBoxLayout()
    ctl.addWidget(QLabel("Limiting magnitude m′:"))
    panel._sky_mag = QLineEdit("6.5")
    panel._sky_mag.setMaximumWidth(80)
    ctl.addWidget(panel._sky_mag)
    apply_btn = QPushButton("Apply")
    ctl.addWidget(apply_btn)
    ctl.addStretch()
    wl.addLayout(ctl)

    holder = QWidget()
    holder_l = QVBoxLayout(holder)
    holder_l.setContentsMargins(0, 0, 0, 0)
    wl.addWidget(holder, 1)

    def _redraw():
        try:
            mag = float(panel._sky_mag.text().strip())
        except ValueError:
            mag = 6.5
        while holder_l.count():
            item = holder_l.takeAt(0)
            ww = item.widget()
            if ww:
                ww.deleteLater()
        data = core.viz.prepare_sky_from_star(panel._sky_result, mag_limit=mag)
        canvas, toolbar = make_sky_canvas(panel, data)
        holder_l.addWidget(toolbar)
        holder_l.addWidget(canvas)

    apply_btn.clicked.connect(_redraw)
    panel._sky_mag.returnPressed.connect(_redraw)
    _redraw()
    panel._viz_tabs_widget.addTab(w, "Night Sky")


# ── Option 18: Stars Within Distance of Sol ───────────────────────────────────

class StarsWithinDistanceSolPanel(DiagramToggleMixin, ResultPanel):
    """Distance limit → stars in starSystems.csv within that range of Sol  (option 18)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
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
        _build_results_area_distance(self)

    def _search(self):
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_tables_layout(self)
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return

        self.run_in_background(
            core.calculators.compute_stars_within_distance_of_sol,
            limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._prepare_render()
        _clear_tables_layout(self)

        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        count = result["count"]
        limit = result["limit_ly"]
        self._tables_layout.addWidget(
            QLabel(f"Stars within {limit} light years of Sol: <b>{count}</b>")
        )

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"],
             r["Spectral Type"], f"{r['Light Years']:.4f}"]
            for r in result["stars"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if mpl_available():
            map_data = core.viz.prepare_star_map_from_result(result)
            if "stars" in map_data and map_data["stars"]:
                self._link_view = view
                _add_map_tabs(
                    self, map_data["stars"], limit,
                    f"Stars within {limit} ly of Sol  ({count} stars)",
                )

                # Phase O — HR Diagram (O2b) + Night Sky (O1), placed to the
                # RIGHT of the map/chart tabs.
                _add_hr_tab(self, result)
                _add_night_sky_tab(self, result)

        self._finish_render()


# ── Option 19: Stars Within Distance of a Star ───────────────────────────────

class StarsWithinDistanceStarPanel(DiagramToggleMixin, ResultPanel):
    """Star name + distance limit → stars within range  (option 19)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._star = QLineEdit()
        self._star.setPlaceholderText("e.g. Alpha Centauri, Vega, HIP 27989")
        form.addRow("Center Star:", self._star)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
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
        _build_results_area_distance(self)

    def _search(self):
        star = self._star.text().strip()
        if not star:
            return
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_tables_layout(self)
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return

        self.run_in_background(
            core.calculators.compute_stars_within_distance_of_star,
            star, limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._prepare_render()
        _clear_tables_layout(self)

        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        center = result["center"]
        count  = result["count"]
        limit  = result["limit_ly"]
        self._tables_layout.addWidget(
            QLabel(f"Stars within {limit} light years of {center}: <b>{count}</b>")
        )

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"],
             r["Spectral Type"], f"{r['Distance']:.3f}"]
            for r in result["stars"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if mpl_available():
            map_data = core.viz.prepare_star_map_from_result(result)
            if "stars" in map_data and map_data["stars"]:
                self._link_view = view
                _add_map_tabs(
                    self, map_data["stars"], limit,
                    f"Stars within {limit} ly of {center}  ({count} stars)",
                )

                # Phase O — HR Diagram (O2b) + Night Sky (O1), placed to the
                # RIGHT of the map/chart tabs.
                _add_hr_tab(self, result)
                _add_night_sky_tab(self, result)

        self._finish_render()
