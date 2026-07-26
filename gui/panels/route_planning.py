# gui/panels/route_planning.py — Phase I + I-OPTS: Route Planning (GUI-only).
#
# Seven panels under the "Route Planning" nav category:
#   MultiStopJourneyPanel   → core.calculators.compute_multi_stop_journey      (I1)
#   OptimalTourPanel        → core.calculators.compute_optimal_tour            (A)
#   NearestNeighborPanel    → core.calculators.compute_nearest_neighbor_chain  (I2)
#   FarthestFirstPanel      → core.calculators.compute_farthest_first_chain    (D)
#   JumpRoutePanel          → core.calculators.compute_jump_route              (B)
#   JumpNetworkPanel        → core.calculators.compute_jump_network            (C)
#   TradeRoutePlannerPanel  → core.calculators.compute_trade_route_mst         (I3, stretch)
#
# All inherit (DiagramToggleMixin, ResultPanel) and follow the opts-18/19 pattern.
# Maps reuse the dark-navy GCNS "Star Chart" / "Star Chart 3D" diagrams with the
# new routes= overlay; coordinates are shifted so the route's origin/start/center
# sits at the chart origin (gold ★) with distance rings measured from it.

import math

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_star_chart_canvas, make_star_chart_3d_canvas,
)
from gui.panels.diagram_tabs import _build_iso_chart_tab, _wire_row_map_linking


# ── shared scaffolding ───────────────────────────────────────────────────────

def _build_results_area_route(panel):
    """Create _tables_widget + diagram view (mirrors distance-star panels)."""
    panel._tables_widget = QWidget()
    panel._tables_layout = QVBoxLayout(panel._tables_widget)
    panel._tables_layout.setContentsMargins(0, 0, 0, 0)
    panel._layout.addWidget(panel._tables_widget, 1)
    panel._setup_diagram_view()
    panel._input_count = panel._layout.count()


def _clear_tables_layout(panel):
    lay = panel._tables_layout
    while lay.count():
        w = lay.takeAt(0).widget()
        if w:
            w.deleteLater()


def _button_row(panel, run_label, enter_fields=()):
    """Standard run + Show Diagrams button row; sets panel.run_btn / _show_diagrams_btn.

    enter_fields: QLineEdits whose Enter/Return key triggers panel._search, so the
    Route Planning panels submit on Enter like the other option panels. (Multi-line
    QPlainTextEdit fields are intentionally not wired — there Enter means newline.)
    """
    btn_widget = QWidget()
    row = QHBoxLayout(btn_widget)
    row.setContentsMargins(0, 0, 0, 0)
    panel.run_btn = QPushButton(run_label)
    panel.run_btn.clicked.connect(panel._search)
    for f in enter_fields:
        f.returnPressed.connect(panel._search)
    panel._show_diagrams_btn = QPushButton("Show Diagrams")
    panel._show_diagrams_btn.clicked.connect(panel._enter_diagram_mode)
    panel._show_diagrams_btn.setVisible(False)
    row.addWidget(panel.run_btn)
    row.addWidget(panel._show_diagrams_btn)
    row.addStretch()
    return btn_widget


def _error_label(panel, msg):
    lbl = QLabel(msg)
    lbl.setStyleSheet("color: red;")
    lbl.setWordWrap(True)
    panel._tables_layout.addWidget(lbl)


def _centered(rm):
    """Shift route geometry so stars[0] (origin/start/center) is at (0,0,0).

    Returns (stars, edges, limit_ly) ready for the Star Chart canvases — the
    gold ★ marks the center, distance rings are measured from it.
    """
    stars, edges = rm["stars"], rm["edges"]
    c = stars[0]
    cx, cy, cz = c["x"], c["y"], c["z"]
    s_stars = [
        {**s, "x": s["x"] - cx, "y": s["y"] - cy, "z": s["z"] - cz}
        for s in stars
    ]
    s_edges = [
        {**e,
         "x1": e["x1"] - cx, "y1": e["y1"] - cy, "z1": e["z1"] - cz,
         "x2": e["x2"] - cx, "y2": e["y2"] - cy, "z2": e["z2"] - cz}
        for e in edges
    ]
    R = max((math.sqrt(s["x"] ** 2 + s["y"] ** 2 + s["z"] ** 2) for s in s_stars),
            default=1.0) or 1.0
    return s_stars, s_edges, R * 1.1


def _route_chart_3d_tab(panel, stars, limit_ly, routes):
    """"Star Chart 3D" tab with viewpoint preset buttons + route overlay."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_chart_3d_canvas(
        panel, stars, limit_ly=limit_ly, routes=routes,
    )
    preset_bar = QWidget()
    preset_bar.setFixedHeight(18)
    prow = QHBoxLayout(preset_bar)
    prow.setContentsMargins(0, 0, 0, 0)
    prow.setSpacing(6)
    style = "QPushButton { padding: 0px 8px; margin: 0px; font-size: 10px; }"
    for label, elev, azim in [("Top View", 90, 0), ("Side View", 0, 0),
                              ("3D Perspective", 30, -60)]:
        btn = QPushButton(label)
        btn.setFixedHeight(18)
        btn.setStyleSheet(style)

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
        prow.addWidget(btn)
    prow.addStretch()
    lay.addWidget(preset_bar)
    lay.addWidget(toolbar3d)
    lay.addWidget(canvas3d)
    return w


def _add_route_chart_tabs(panel, result):
    """Add "Star Chart" + "Star Chart 3D" viz tabs with the route overlay."""
    if not mpl_available():
        return
    rm = core.viz.prepare_route_map(result)
    if not isinstance(rm, dict) or "error" in rm or not rm.get("stars"):
        return
    stars, edges, limit_ly = _centered(rm)

    chart_w = QWidget()
    chart_l = QVBoxLayout(chart_w)
    chart_l.setContentsMargins(4, 4, 4, 4)
    canvas, toolbar = make_star_chart_canvas(panel, stars, limit_ly=limit_ly,
                                             routes=edges)
    chart_l.addWidget(toolbar)
    chart_l.addWidget(canvas)
    panel._viz_tabs_widget.addTab(chart_w, "Star Chart")

    panel._viz_tabs_widget.addTab(
        _route_chart_3d_tab(panel, stars, limit_ly, edges), "Star Chart 3D")


# ── Phase O O8 — Two-Star Map (opts 17, 20, 21) ──────────────────────────────

def _two_star_route_map(result: dict, kind: str) -> dict:
    """Convert a two-star result into **Sol-centered** star-map geometry.

    `kind="distance"` (opt 17: `star1_info`/`star2_info`) or `"travel"` (opts
    20/21: `origin_info`/`dest_info`).

    **Sol is `stars[0]` at the origin** — `make_star_chart_canvas` paints the
    first entry as the gold ★ only when it sits at (0,0,0), so this is what makes
    these charts read exactly like the opt-18/19 Star Charts. The two searched
    stars keep their true heliocentric coordinates and are coloured by spectral
    class from the (additive) `sp_type` that
    `core.calculators.compute_lookup_star_for_distance` now returns. When one
    endpoint *is* Sol/Sun it becomes the centre node (keeping the typed name)
    rather than being duplicated.

    No connecting edge is drawn (the tables carry the distance / travel time), so
    `edges` is always empty. Returns {"stars", "edges", "edge_style"} or the
    `{"error"}` passthrough.
    """
    if not isinstance(result, dict) or "error" in result:
        return result
    if kind == "distance":
        s1, s2 = result["star1_info"], result["star2_info"]
    else:
        s1, s2 = result["origin_info"], result["dest_info"]

    def _node(s):
        x, y, z = core.calculators._to_cartesian(s["ra_deg"], s["dec_deg"], s["ly"])
        sp = (s.get("sp_type") or "").strip()
        return {"name": s["name"], "desig": s.get("desig_str", ""),
                "sp_type": sp, "color": core.calculators._star_map_color(sp),
                "ly": s["ly"], "x": x, "y": y, "z": z}

    nodes = [_node(s1), _node(s2)]
    # One of the endpoints may already be Sol (ly == 0) — use it as the centre
    # node instead of appending a second one at the same spot.
    at_origin = [n for n in nodes if abs(n["ly"]) < 1e-9]
    others = [n for n in nodes if abs(n["ly"]) >= 1e-9]
    if at_origin:
        centre = at_origin[0]
        centre = {**centre, "x": 0.0, "y": 0.0, "z": 0.0,
                  "sp_type": centre["sp_type"] or "G2V",
                  "color": core.calculators._star_map_color(
                      centre["sp_type"] or "G2V")}
        stars = [centre] + others + at_origin[1:]
    else:
        stars = [{"name": "Sol", "desig": "", "sp_type": "G2V",
                  "color": core.calculators._star_map_color("G2V"),
                  "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0}] + nodes
    return {"stars": stars, "edges": [], "edge_style": "none"}


def add_two_star_chart_tabs(panel, result: dict, kind: str, link_view=None):
    """Add "Star Chart" + "Star Chart 3D" viz tabs for a two-star result (O8).

    Built with the same `_build_iso_chart_tab` the opt-18/19 panels use, so the
    two tabs get full parity: the O16 per-class legend filter, the O17 travel-time
    isochrone control, the click-info box, and the 3D viewpoint presets. `stars[0]`
    is Sol at the origin (gold ★) with the searched stars placed relative to it.

    `link_view` (optional) is the result table to wire O15 row↔map linking to; its
    column 0 must hold star names. Omit it (opts 20/21, whose table is
    Origin|Destination-shaped) and clicks simply show the info box.
    """
    if not mpl_available():
        return
    rm = _two_star_route_map(result, kind)
    if not isinstance(rm, dict) or "error" in rm or not rm.get("stars"):
        return
    stars = rm["stars"]
    limit_ly = max(
        (math.sqrt(s["x"] ** 2 + s["y"] ** 2 + s["z"] ** 2) for s in stars),
        default=1.0) * 1.1 or 1.0

    canvases = []
    click_cb = None
    if link_view is not None:
        from gui.panels.diagram_tabs import _star_click_select
        click_cb = lambda nm: _star_click_select(panel, nm)

    # Three dots at most, so there is no clutter to declutter: raise the shared
    # 15 ly label cutoff past this chart's range and keep the names visible at
    # any zoom (opts 18/19 keep the default — they plot hundreds of stars).
    label_max_ly = max(limit_ly * 10.0, 100.0)

    panel._viz_tabs_widget.addTab(
        _build_iso_chart_tab(panel, stars, limit_ly, click_cb, canvases,
                             is_3d=False, label_max_ly=label_max_ly),
        "Star Chart")
    panel._viz_tabs_widget.addTab(
        _build_iso_chart_tab(panel, stars, limit_ly, click_cb, canvases,
                             is_3d=True, label_max_ly=label_max_ly),
        "Star Chart 3D")
    if link_view is not None:
        _wire_row_map_linking(panel, link_view, canvases)


# ── I1: Multi-Stop Journey ───────────────────────────────────────────────────

class MultiStopJourneyPanel(DiagramToggleMixin, ResultPanel):
    """Ordered stops → cumulative travel time + route chart."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._stops = QPlainTextEdit()
        self._stops.setPlaceholderText("One star per line, e.g.\nSol\nAlpha Centauri\nSirius")
        self._stops.setFixedHeight(110)
        self._stops.setMaximumWidth(300)   # match the other field widths
        form.addRow("Stops:", self._stops)

        self._unit = QComboBox()
        self._unit.addItems(["× c", "LY/HR"])
        form.addRow("Velocity Unit:", self._unit)

        self._vel = QLineEdit()
        self._vel.setPlaceholderText("e.g. 100")
        form.addRow("Velocity:", self._vel)

        form.addRow("", _button_row(self, "Plan Journey", enter_fields=(self._vel,)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        names = [ln.strip() for ln in self._stops.toPlainText().splitlines() if ln.strip()]
        self._prepare_render()
        _clear_tables_layout(self)
        try:
            vel = float(self._vel.text().strip())
            if vel <= 0:
                raise ValueError
        except ValueError:
            _error_label(self, "Velocity must be a positive number.")
            return
        use_times_c = self._unit.currentText().startswith("×")
        self.run_in_background(
            core.calculators.compute_multi_stop_journey,
            names, vel, use_times_c,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        self._tables_layout.addWidget(QLabel(
            f"Total Distance: <b>{result['total_ly']:.3f} LY</b> &nbsp;·&nbsp; "
            f"Total Travel Time: <b>{result['total_time']}</b>"))

        headers = ["Leg #", "Origin", "Destination", "Distance (LY)", "LY/HR",
                   "× c", "Travel Time", "Cumulative Time"]
        rows = [
            [str(l["leg"]), l["origin"], l["dest"], f"{l['distance_ly']:.3f}",
             f"{l['ly_hr']:.5f}", f"{l['times_c']:.2f}",
             l["travel_time"], l["cumulative_time"]]
            for l in result["legs"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        _add_route_chart_tabs(self, result)
        self._finish_render()


# ── I2: Nearest-Neighbor Chain ───────────────────────────────────────────────

class NearestNeighborPanel(DiagramToggleMixin, ResultPanel):
    """Greedy nearest-unvisited chain from a start star."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._start = QLineEdit()
        self._start.setPlaceholderText("e.g. Sol, Alpha Centauri, HIP 27989")
        form.addRow("Start Star:", self._start)

        self._hops = QSpinBox()
        self._hops.setRange(1, 50)
        self._hops.setValue(5)
        self._hops.setMaximumWidth(300)   # match the other field widths
        form.addRow("Number of Hops:", self._hops)

        self._max = QLineEdit()
        self._max.setPlaceholderText("e.g. 6.0")
        form.addRow("Max Hop Distance (LY):", self._max)

        form.addRow("", _button_row(self, "Build Chain",
                                    enter_fields=(self._start, self._max)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        start = self._start.text().strip()
        self._prepare_render()
        _clear_tables_layout(self)
        if not start:
            _error_label(self, "Enter a start star.")
            return
        try:
            max_ly = float(self._max.text().strip())
            if max_ly <= 0:
                raise ValueError
        except ValueError:
            _error_label(self, "Max hop distance must be a positive number.")
            return
        self.run_in_background(
            core.calculators.compute_nearest_neighbor_chain,
            start, self._hops.value(), max_ly,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        chain = result["chain"]
        self._tables_layout.addWidget(QLabel(
            f"{len(chain)} hop(s) from {result['start_name']} · "
            f"Total Distance: <b>{result['total_ly']:.3f} LY</b>"))
        if result.get("stopped_early"):
            note = QLabel("No unvisited star within max hop distance — chain ended early.")
            note.setStyleSheet("color: #b8860b; font-style: italic;")
            self._tables_layout.addWidget(note)

        headers = ["Hop #", "Star Name", "Designations", "Spectral Type",
                   "Dist from Prev (LY)", "Cumulative (LY)", "Dist from Sol (LY)"]
        rows = [
            [str(c["hop"]), c["star_name"], c["desig"], c["sp_type"],
             f"{c['dist_from_prev_ly']:.3f}", f"{c['cumulative_ly']:.3f}",
             f"{c['ly_from_sol']:.3f}"]
            for c in chain
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if chain:
            _add_route_chart_tabs(self, result)
        self._finish_render()


# ── I3: Trade-Route Network Planner (stretch) ────────────────────────────────

class TradeRoutePlannerPanel(DiagramToggleMixin, ResultPanel):
    """Minimum spanning tree connecting a set of systems."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._systems = QPlainTextEdit()
        self._systems.setPlaceholderText("One system per line, e.g.\nSol\nSirius\nProcyon\n61 Cygni")
        self._systems.setFixedHeight(120)
        self._systems.setMaximumWidth(300)   # narrower than the pane
        form.addRow("Systems:", self._systems)

        form.addRow("", _button_row(self, "Build Network"))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        names = [ln.strip() for ln in self._systems.toPlainText().splitlines() if ln.strip()]
        self._prepare_render()
        _clear_tables_layout(self)
        self.run_in_background(
            core.calculators.compute_trade_route_mst,
            names,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        n_nodes = len(result["nodes"])
        edges = result["edges"]
        self._tables_layout.addWidget(QLabel(
            f"{n_nodes} nodes · {len(edges)} edges · "
            f"Total Network Distance: <b>{result['total_ly']:.3f} LY</b>"))

        view = self.make_table(
            ["From", "To", "Distance (LY)"],
            [[e["from"], e["to"], f"{e['distance_ly']:.3f}"] for e in edges])
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        _add_route_chart_tabs(self, result)
        self._finish_render()


# ── A: Optimal Tour ──────────────────────────────────────────────────────────

class OptimalTourPanel(DiagramToggleMixin, ResultPanel):
    """Shortest-total-distance visit order for a set of stars (NN + 2-opt)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._stops = QPlainTextEdit()
        self._stops.setPlaceholderText("One star per line; first = start, e.g.\nSol\nProcyon\nSirius\nBarnard's Star")
        self._stops.setFixedHeight(110)
        self._stops.setMaximumWidth(300)
        form.addRow("Stars to Visit:", self._stops)

        self._closed = QCheckBox("Closed loop (return to start)")
        form.addRow("", self._closed)

        self._unit = QComboBox()
        self._unit.addItems(["× c", "LY/HR"])
        form.addRow("Velocity Unit:", self._unit)

        self._vel = QLineEdit()
        self._vel.setPlaceholderText("e.g. 500")
        form.addRow("Velocity:", self._vel)

        form.addRow("", _button_row(self, "Optimize Tour", enter_fields=(self._vel,)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        names = [ln.strip() for ln in self._stops.toPlainText().splitlines() if ln.strip()]
        self._prepare_render()
        _clear_tables_layout(self)
        try:
            vel = float(self._vel.text().strip())
            if vel <= 0:
                raise ValueError
        except ValueError:
            _error_label(self, "Velocity must be a positive number.")
            return
        use_times_c = self._unit.currentText().startswith("×")
        self.run_in_background(
            core.calculators.compute_optimal_tour,
            names, vel, use_times_c, self._closed.isChecked(),
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        self._tables_layout.addWidget(QLabel(
            f"Optimized Total: <b>{result['optimized_total_ly']:.3f} LY</b> &nbsp;·&nbsp; "
            f"{result['total_time']} &nbsp;·&nbsp; "
            f"as-typed {result['naive_total_ly']:.3f} LY → "
            f"<span style='color:#2e8b57'>saved {result['saved_ly']:.3f} LY "
            f"({result['saved_pct']:.1f}%)</span> &nbsp;·&nbsp; "
            f"{'closed loop' if result['closed'] else 'open path'}"))

        headers = ["Leg #", "Origin", "Destination", "Distance (LY)", "LY/HR",
                   "× c", "Travel Time", "Cumulative Time"]
        rows = [
            [str(l["leg"]), l["origin"], l["dest"], f"{l['distance_ly']:.3f}",
             f"{l['ly_hr']:.5f}", f"{l['times_c']:.2f}",
             l["travel_time"], l["cumulative_time"]]
            for l in result["legs"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        _add_route_chart_tabs(self, result)
        self._finish_render()


# ── D: Farthest-First Coverage ───────────────────────────────────────────────

class FarthestFirstPanel(DiagramToggleMixin, ResultPanel):
    """De-clustering coverage: each step picks the star farthest from the visited set."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._start = QLineEdit()
        self._start.setPlaceholderText("e.g. Sol, Alpha Centauri, HIP 27989")
        form.addRow("Start Star:", self._start)

        self._stops = QSpinBox()
        self._stops.setRange(1, 50)
        self._stops.setValue(5)
        self._stops.setMaximumWidth(300)
        form.addRow("Number of Stops:", self._stops)

        self._max = QLineEdit()
        self._max.setPlaceholderText("blank = unlimited")
        form.addRow("Max Reach (LY):", self._max)

        form.addRow("", _button_row(self, "Build Coverage",
                                    enter_fields=(self._start, self._max)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        start = self._start.text().strip()
        self._prepare_render()
        _clear_tables_layout(self)
        if not start:
            _error_label(self, "Enter a start star.")
            return
        raw = self._max.text().strip()
        max_reach = None
        if raw:
            try:
                max_reach = float(raw)
                if max_reach <= 0:
                    raise ValueError
            except ValueError:
                _error_label(self, "Max reach must be a positive number (or blank).")
                return
        self.run_in_background(
            core.calculators.compute_farthest_first_chain,
            start, self._stops.value(), max_reach,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        chain = result["chain"]
        self._tables_layout.addWidget(QLabel(
            f"{len(chain)} outpost(s) from {result['start_name']} · "
            f"Widest from start: <b>{result['widest_ly']:.3f} LY</b>"))
        if result.get("stopped_early"):
            note = QLabel("No further star within reach of the visited set — coverage ended early.")
            note.setStyleSheet("color: #b8860b; font-style: italic;")
            self._tables_layout.addWidget(note)

        headers = ["Step", "Star Name", "Designations", "Spectral Type",
                   "Sep to Visited (LY)", "Dist from Start (LY)", "Dist from Sol (LY)"]
        rows = [
            [str(c["step"]), c["star_name"], c["desig"], c["sp_type"],
             f"{c['sep_to_visited_ly']:.3f}", f"{c['dist_from_start_ly']:.3f}",
             f"{c['ly_from_sol']:.3f}"]
            for c in chain
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if chain:
            _add_route_chart_tabs(self, result)
        self._finish_render()


# ── B: Jump-Range Pathfinding ────────────────────────────────────────────────

class JumpRoutePanel(DiagramToggleMixin, ResultPanel):
    """Route origin→destination over a jump-limited graph (Dijkstra / BFS)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Sol")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Procyon")
        form.addRow("Destination:", self._dest)

        self._max = QLineEdit()
        self._max.setPlaceholderText("e.g. 9.0")
        form.addRow("Max Jump (LY):", self._max)

        self._opt = QComboBox()
        self._opt.addItems(["Min distance", "Fewest jumps"])
        form.addRow("Optimize For:", self._opt)

        form.addRow("", _button_row(self, "Find Route",
                                    enter_fields=(self._origin, self._dest, self._max)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        origin = self._origin.text().strip()
        dest = self._dest.text().strip()
        self._prepare_render()
        _clear_tables_layout(self)
        if not origin or not dest:
            _error_label(self, "Enter both an origin and a destination.")
            return
        try:
            max_jump = float(self._max.text().strip())
            if max_jump <= 0:
                raise ValueError
        except ValueError:
            _error_label(self, "Max jump must be a positive number.")
            return
        optimize = "jumps" if self._opt.currentText().startswith("Fewest") else "distance"
        self.run_in_background(
            core.calculators.compute_jump_route,
            origin, dest, max_jump, optimize,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        o = result["origin_info"]["name"]
        d = result["dest_info"]["name"]
        if not result["reachable"]:
            note = QLabel(
                f"No route from {o} to {d} with jumps ≤ {result['max_jump_ly']:.2f} ly — "
                f"destination unreachable (disconnected from the origin's jump network).")
            note.setStyleSheet("color: #b8860b; font-weight: 600;")
            note.setWordWrap(True)
            self._tables_layout.addWidget(note)
            _add_route_chart_tabs(self, result)
            self._finish_render()
            return

        mode = "fewest jumps" if result["optimize"] == "jumps" else "min distance"
        self._tables_layout.addWidget(QLabel(
            f"<b>{result['jumps']} jump(s)</b> · Total Distance: "
            f"<b>{result['total_ly']:.3f} LY</b> · direct line {result['direct_ly']:.3f} LY · "
            f"optimized for {mode}"))

        headers = ["Jump #", "From", "To", "Jump Dist (LY)", "Cumulative (LY)"]
        rows = [
            [str(r["jump"]), r["from"], r["to"], f"{r['jump_ly']:.3f}",
             f"{r['cumulative_ly']:.3f}"]
            for r in result["route"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        _add_route_chart_tabs(self, result)
        self._finish_render()


# ── C: Jump Network / Reachability ───────────────────────────────────────────

class JumpNetworkPanel(DiagramToggleMixin, ResultPanel):
    """BFS reachability tiers from a start star at a jump range."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._start = QLineEdit()
        self._start.setPlaceholderText("e.g. Sol")
        form.addRow("Start System:", self._start)

        self._max = QLineEdit()
        self._max.setPlaceholderText("e.g. 6.0")
        form.addRow("Max Jump (LY):", self._max)

        self._hops = QLineEdit()
        self._hops.setPlaceholderText("blank = unlimited")
        form.addRow("Max Jumps:", self._hops)

        form.addRow("", _button_row(self, "Map Reachable",
                                    enter_fields=(self._start, self._max, self._hops)))
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        _build_results_area_route(self)

    def _search(self):
        start = self._start.text().strip()
        self._prepare_render()
        _clear_tables_layout(self)
        if not start:
            _error_label(self, "Enter a start system.")
            return
        try:
            max_jump = float(self._max.text().strip())
            if max_jump <= 0:
                raise ValueError
        except ValueError:
            _error_label(self, "Max jump must be a positive number.")
            return
        raw = self._hops.text().strip()
        max_jumps = None
        if raw:
            try:
                max_jumps = int(raw)
                if max_jumps < 1:
                    raise ValueError
            except ValueError:
                _error_label(self, "Max jumps must be a positive integer (or blank).")
                return
        self.run_in_background(
            core.calculators.compute_jump_network,
            start, max_jump, max_jumps,
            on_result=self._render,
        )

    def _render(self, result):
        self._prepare_render()
        _clear_tables_layout(self)
        if "error" in result:
            _error_label(self, result["error"])
            return

        self._tables_layout.addWidget(QLabel(
            f"Reachable from <b>{result['start_name']}</b>: "
            f"<b>{result['reachable_count']}</b> star(s) "
            f"(up to {result['max_tier']} jump(s) at ≤ {result['max_jump_ly']:.2f} ly/jump) · "
            f"<b>{result['unreachable_count']}</b> in-pool star(s) out of range"))

        # Tier colour legend.
        tier_colors = core.calculators.TIER_COLORS
        swatches = []
        for ti in range(0, result["max_tier"] + 1):
            col = tier_colors[min(ti, len(tier_colors) - 1)]
            label = "start" if ti == 0 else f"{ti} jump{'s' if ti > 1 else ''}"
            swatches.append(
                f"<span style='color:{col}'>●</span> {label}")
        legend = QLabel(" &nbsp; ".join(swatches))
        legend.setStyleSheet("font-size: 11px;")
        self._tables_layout.addWidget(legend)

        headers = ["Jumps", "Star Name", "Designations", "Spectral Type",
                   "Dist from Start (LY)", "Dist from Sol (LY)"]
        rows = []
        for tier in result["tiers"]:
            for s in tier["stars"]:
                rows.append([
                    str(tier["jumps"]), s["star_name"], s["desig"], s["sp_type"],
                    f"{s['dist_from_start_ly']:.3f}", f"{s['ly_from_sol']:.3f}"])
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        _add_route_chart_tabs(self, result)
        self._finish_render()
