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
# routes= overlay; coordinates are shifted so the route's origin/start/center
# sits at the chart origin (gold ★) with distance rings measured from it.
#
# Both tab builders here — `_add_route_chart_tabs` (the seven planners) and
# `add_two_star_chart_tabs` (opts 17/20/21) — go through the shared opt-18/19
# `_build_iso_chart_tab`, so every route chart carries the O16 legend filter, the
# O17 isochrone control, the click-info box and the 3D viewpoint presets. The
# route overlay reaches the canvas through that builder's `routes=` passthrough
# (completed_plans/ROUTE_CHART_REFACTOR_PLAN.md Phases 1–2, 2026-07-27). Phase 3 (same date)
# retired the second `_star_map_color` palette: dot colours here now come from the
# one app-wide `core.shared.sp_color`, so a star reads the same on every panel.
#
# Each panel also carries a `DESCRIPTION` class attribute explaining what the
# option does. It renders as a hidden QLabel at the top of the results pane
# (`_build_description_box`), toggled by the Show/Hide Description button in
# `_button_row`, and is deliberately persistent — `_clear_tables_layout` skips it
# so a Run never destroys it.

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from core.shared import sp_color   # the one app-wide spectral palette (Phase 3)
from gui.visualizations.plot_helpers import mpl_available
from gui.panels.diagram_tabs import (
    _build_iso_chart_tab, _wire_row_map_linking, _add_find_box,
    _add_reset_diagram_button,
)


# ── shared scaffolding ───────────────────────────────────────────────────────

_DESC_QSS = ("color: #23517d; background: #eaf3fb; border: 1px solid #c3ddf2; "
             "border-radius: 4px; padding: 8px;")


def _build_description_box(panel):
    """Create the (hidden) description label at the top of the results area.

    It lives inside _tables_widget — i.e. in the same pane the result tables are
    drawn in — so a finished Run shows the description directly above its data.
    It is a persistent widget: `_clear_tables_layout` skips it, and the
    Show/Hide Description button toggles its visibility (hidden by default).
    """
    lbl = QLabel(getattr(panel, "DESCRIPTION", "").strip())
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(_DESC_QSS)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    lbl.setVisible(False)
    panel._desc_box = lbl
    # AlignTop: before a Run the results pane is otherwise empty, and without it
    # the label would stretch to fill (and vertically centre in) the whole pane.
    panel._tables_layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignTop)
    # Everything at/above this index in _tables_layout survives a clear.
    panel._tables_keep = panel._tables_layout.count()


def _toggle_description(panel):
    box = getattr(panel, "_desc_box", None)
    if box is None:
        return
    # isHidden(), not isVisible(): the latter is False whenever an ancestor is
    # hidden (diagram mode, an un-shown panel), which would desync the toggle.
    show = box.isHidden()
    box.setVisible(show)
    panel._desc_btn.setText("Hide Description" if show else "Show Description")


def _build_results_area_route(panel):
    """Create _tables_widget + diagram view (mirrors distance-star panels)."""
    panel._tables_widget = QWidget()
    panel._tables_layout = QVBoxLayout(panel._tables_widget)
    panel._tables_layout.setContentsMargins(0, 0, 0, 0)
    _build_description_box(panel)
    panel._layout.addWidget(panel._tables_widget, 1)
    panel._setup_diagram_view()
    panel._input_count = panel._layout.count()


def _clear_tables_layout(panel):
    lay = panel._tables_layout
    keep = getattr(panel, "_tables_keep", 0)
    while lay.count() > keep:
        w = lay.takeAt(keep).widget()
        if w:
            w.deleteLater()


def _button_row(panel, run_label, enter_fields=()):
    """Standard run + Show Description + Show Diagrams row; sets panel.run_btn /
    panel._desc_btn / panel._show_diagrams_btn.

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
    # Toggles the panel description, which is rendered at the top of the results
    # pane (created later, in build_results_area) — hidden by default.
    panel._desc_btn = QPushButton("Show Description")
    panel._desc_btn.clicked.connect(lambda: _toggle_description(panel))
    panel._show_diagrams_btn = QPushButton("Show Diagrams")
    panel._show_diagrams_btn.clicked.connect(panel._enter_diagram_mode)
    panel._show_diagrams_btn.setVisible(False)
    row.addWidget(panel.run_btn)
    row.addWidget(panel._desc_btn)
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


# Above this many nodes a chart is dense enough to need the shared 15 ly label
# decluttering (Jump Network can return thousands). Below it the route is a
# handful of dots, so — like the O8 two-star maps — the names stay readable at
# any zoom.
_ROUTE_SPARSE_MAX_NODES = 25


def _add_route_chart_tabs(panel, result, link_view=None, name_col=1,
                          legend_filter=True, find_box=True):
    """Add "Star Chart" + "Star Chart 3D" viz tabs with the route overlay.

    Built with the same `_build_iso_chart_tab` the opt-18/19 panels use, so the
    route charts carry the O16 per-class legend filter, the O17 travel-time
    isochrone control, the click-info box and the 3D viewpoint presets. The
    route overlay rides along via the builder's `routes=` passthrough, and is
    re-passed on every isochrone rebuild.

    `_centered` puts the route's origin/start at the chart origin (gold ★), so
    the isochrone rings read as travel time **from the start**.

    `link_view` (optional) is the result table to wire O15 row↔map linking to;
    `name_col` is its star-name column — 1 for the route tables, which all lead
    with an index column (Hop # / Step / Jumps). Leg-shaped `From|To` tables
    (Multi-Stop, Optimal Tour, Jump Route, Trade Route) omit it, as
    `add_two_star_chart_tabs` already does for opts 20/21.

    `legend_filter=False` suppresses the per-class legend for JumpNetworkPanel,
    whose dots carry per-tier rather than spectral colours.

    `find_box=False` suppresses the O18 Find box — passed by Jump Route's
    `reachable=False` branch, whose chart is just the two endpoints (the same
    "nothing to find" reasoning that keeps the box off opts 17/20/21).
    """
    if not mpl_available():
        return
    rm = core.viz.prepare_route_map(result)
    if not isinstance(rm, dict) or "error" in rm or not rm.get("stars"):
        return
    stars, edges, limit_ly = _centered(rm)

    canvases = []
    click_cb = None
    if link_view is not None:
        from gui.panels.diagram_tabs import _star_click_select
        click_cb = lambda nm: _star_click_select(panel, nm)

    label_max_ly = (max(limit_ly * 10.0, 100.0)
                    if len(stars) <= _ROUTE_SPARSE_MAX_NODES else None)

    panel._viz_tabs_widget.addTab(
        _build_iso_chart_tab(panel, stars, limit_ly, click_cb, canvases,
                             is_3d=False, label_max_ly=label_max_ly,
                             routes=edges, legend_filter=legend_filter),
        "Star Chart")
    panel._viz_tabs_widget.addTab(
        _build_iso_chart_tab(panel, stars, limit_ly, click_cb, canvases,
                             is_3d=True, label_max_ly=label_max_ly,
                             routes=edges, legend_filter=legend_filter),
        "Star Chart 3D")
    # Always registered so the canvases are reachable (highlighting, tests);
    # with link_view=None this connects nothing and clicks just show the info box.
    _wire_row_map_linking(panel, link_view, canvases, name_col=name_col)

    # O18 Find box, sourced from the route star list rather than the result table
    # — the leg-shaped panels' tables are From|To rows, not one row per star.
    # The start (stars[0], the gold ★) is excluded on all seven, so the gesture has
    # ONE outcome everywhere — here and on opts 18/19, where the centre star has no
    # table row at all. The O16 hazard is what motivated it: the ★ is drawn outside
    # the per-class scatter but *is* in the ring's name→class map, so filtering its
    # class off would suppress the ring while the ★ stayed visible, and the reveal
    # step would then un-hide a class the user deliberately filtered off.
    #
    # Note that neither premise holds for JumpNetworkPanel specifically: its start
    # DOES have a table row (`tiers[0]`), and it passes `legend_filter=False`, so no
    # class is ever hidden and `_o16_reveal_class` does not exist. Typing the start's
    # name there reports "No match" for a star that is visibly in the table and in
    # the canvas coord_map. That asymmetry is accepted deliberately: making it the
    # one panel where the start IS findable would give the same gesture two outcomes
    # across the seven, which is the inconsistency D6 exists to remove.
    #
    # Excluded by NAME, not by index: Multi-Stop and Optimal Tour emit one node
    # per typed stop, so a route that returns to its start (Sol → Sirius → Sol)
    # carries the start again at a later index — and the canvases' name-keyed
    # coord maps point every copy at the same ★.
    if find_box:
        start = stars[0]["name"]
        _add_find_box(panel, [(s["name"], s.get("desig", ""))
                              for s in stars[1:] if s["name"] != start])

    # ⟲ Reset Diagram — restore the active chart's default zoom/pan/rotation.
    _add_reset_diagram_button(panel)


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
                "sp_type": sp, "color": sp_color(sp),
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
                  "color": sp_color(centre["sp_type"] or "G2V")}
        stars = [centre] + others + at_origin[1:]
    else:
        stars = [{"name": "Sol", "desig": "", "sp_type": "G2V",
                  "color": sp_color("G2V"),
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

    # ⟲ Reset Diagram — restore the active chart's default zoom/pan/rotation.
    _add_reset_diagram_button(panel)


# ── I1: Multi-Stop Journey ───────────────────────────────────────────────────

class MultiStopJourneyPanel(DiagramToggleMixin, ResultPanel):
    """Ordered stops → cumulative travel time + route chart."""

    DESCRIPTION = """
    <b>Multi-Stop Journey</b> — travel time along a route you order yourself.<br><br>
    Enter two or more stars, one per line, <b>in the order you want to visit them</b>
    (the order is used exactly as typed — nothing is re-sorted), then a cruise
    velocity in either &times;&nbsp;c or LY/HR. Each stop is resolved to real
    coordinates: <i>Sol</i>/<i>Sun</i> is the origin, otherwise the local
    <code>star_systems</code> table is searched first and SIMBAD is queried only
    if that misses. If any stop cannot be resolved, the whole run stops with an
    error naming it.<br><br>
    <b>You get:</b> one row per leg — straight-line 3D distance in light years,
    the velocity in both units, the leg's travel time, and the running cumulative
    time — plus the journey totals above the table.<br><br>
    <b>Diagrams:</b> Star Chart and Star Chart 3D, centred on the first stop, with
    the legs drawn as dashed lines.
    """

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

    DESCRIPTION = """
    <b>Nearest-Neighbor Chain</b> — hop from star to star, always taking the
    closest one you have not visited yet.<br><br>
    Give a start star, how many hops to take, and a maximum hop distance in light
    years. Starting from that star, each step picks the <b>nearest unvisited</b>
    star in the local <code>star_systems</code> catalogue that lies within the hop
    limit; the start's own catalogue row is excluded so it cannot be hop 1. If no
    unvisited star is within reach the chain simply ends early — that is a normal
    result, flagged with an amber note, not an error.<br><br>
    <b>You get:</b> one row per hop — star name, designations, spectral type,
    distance from the previous hop, cumulative distance, and distance from Sol.<br><br>
    <b>Use it for</b> short-range "island hopping" routes; the chain naturally
    clusters in dense regions. For the opposite behaviour — spreading out to cover
    territory — use <i>Farthest-First Coverage</i>.
    """

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
            # One star per row → O15 row↔map linking (names in column 1).
            _add_route_chart_tabs(self, result, link_view=view)
        self._finish_render()


# ── I3: Trade-Route Network Planner (stretch) ────────────────────────────────

class TradeRoutePlannerPanel(DiagramToggleMixin, ResultPanel):
    """Minimum spanning tree connecting a set of systems."""

    DESCRIPTION = """
    <b>Trade-Route Network</b> — the cheapest way to connect a set of systems to
    each other.<br><br>
    Enter two or more systems, one per line (order does not matter; duplicates are
    ignored). The planner measures every possible pair, then builds a
    <b>minimum spanning tree</b>: it keeps adding the shortest link that does not
    close a loop until every system is connected by exactly
    <i>N&nbsp;&minus;&nbsp;1</i> links. The result is the shortest total length of
    track that still reaches every system — a trade or supply network, <b>not</b>
    a tour: it does not tell you what order to fly, and it may branch.<br><br>
    <b>You get:</b> one row per link — From, To, and its length in light years —
    with the node/edge counts and total network distance above the table.<br><br>
    <b>Diagrams:</b> Star Chart and Star Chart 3D with the network drawn as solid
    lines.
    """

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

    DESCRIPTION = """
    <b>Optimal Tour</b> — you say <i>which</i> stars to visit; this works out the
    best <i>order</i>.<br><br>
    Enter your stars one per line and a cruise velocity. The <b>first star stays
    fixed</b> as the departure point; the rest are re-ordered to minimise the total
    distance flown (a nearest-neighbour first guess, then repeated 2-opt
    improvement — a very good route, not a proven-perfect one). Tick
    <i>Closed loop</i> to add the return leg home.<br><br>
    <b>You get:</b> one row per leg in the optimised order — distance, velocity in
    both units, travel time and cumulative time — plus a summary comparing the
    optimised total against simply flying the list as typed, and how many light
    years (and what percentage) that saved.<br><br>
    <b>Compare with</b> <i>Multi-Stop Journey</i>, which flies your list in exactly
    the order given.
    """

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

    DESCRIPTION = """
    <b>Farthest-First Coverage</b> — spread out instead of hopping to the nearest
    neighbour.<br><br>
    Give a start star and a number of stops. Each step picks the unvisited star
    that is <b>farthest from everything visited so far</b>, so the picks push out
    in different directions rather than clumping — a good way to choose survey
    sites, outposts or sensor stations that cover a volume evenly. <i>Max Reach</i>
    optionally requires each new pick to still lie within that many light years of
    some already-visited star (leave it blank for no limit); if nothing qualifies,
    the run stops early with an amber note — a normal result, not an error.<br><br>
    <b>You get:</b> one row per stop — star name, designations, spectral type, its
    separation from the nearest visited star, its distance from the start, and its
    distance from Sol.<br><br>
    <b>Diagrams:</b> Star Chart and Star Chart 3D; dashed lines link each pick back
    to the visited star nearest it, showing the exploration tree.
    """

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
            # One star per row → O15 row↔map linking (names in column 1).
            _add_route_chart_tabs(self, result, link_view=view)
        self._finish_render()


# ── B: Jump-Range Pathfinding ────────────────────────────────────────────────

class JumpRoutePanel(DiagramToggleMixin, ResultPanel):
    """Route origin→destination over a jump-limited graph (Dijkstra / BFS)."""

    DESCRIPTION = """
    <b>Jump-Range Pathfinding</b> — get from A to B when your ship can only cross
    a limited distance at a time.<br><br>
    Give an origin, a destination and a <i>Max Jump</i> range in light years. The
    planner treats the whole local <code>star_systems</code> catalogue as possible
    stepping stones and finds a chain of stars where <b>no single jump exceeds the
    range</b>. <i>Optimize For</i> chooses what "best" means: <i>Min distance</i>
    finds the shortest total path, <i>Fewest jumps</i> finds the one with the least
    stops (which may be longer overall).<br><br>
    <b>Via (optional)</b> — comma-separated stars the route <b>must</b> pass
    through, e.g. <code>70 Vir</code>. They are a <i>set</i>, not a sequence: type
    them in any order and the planner visits them in whichever order is cheapest
    under <i>Optimize For</i>, so the order it reports back may not be the order you
    typed. Every single jump still obeys the range. Up to <b>8</b> waypoints.<br><br>
    <b>You get:</b> one row per jump — From, To, that jump's length and the running
    total — with the jump count, total path length and the direct straight-line
    distance for comparison. With waypoints, the arrival at each one is marked
    <b>◆</b> and listed in visit order above the table.<br><br>
    <b>A waypointed route may visit the same star twice.</b> Each leg is planned
    optimally on its own, so a detour out to a waypoint and back can re-use stars —
    that is normal for "must pass through" routing, not a glitch, and it is why the
    same name can appear on more than one row.<br><br>
    <b>If no route exists</b> at that range the panel says so plainly (an amber
    note) rather than erroring, naming the <i>particular hop</i> that failed — with
    waypoints that is often not origin→destination. The solar neighbourhood is
    genuinely sparse, so a short jump range often isolates a target, and adding a
    far-flung waypoint can strand a route that worked without it — raise the range
    to connect more of the catalogue.
    """

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Sol")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Procyon")
        form.addRow("Destination:", self._dest)

        # Blank = no waypoints; there is deliberately no on/off control.
        self._via = QLineEdit()
        self._via.setPlaceholderText("e.g. 70 Vir, 61 Vir  (max 8, blank = none)")
        form.addRow("Via (optional, comma-separated):", self._via)

        self._max = QLineEdit()
        self._max.setPlaceholderText("e.g. 9.0")
        form.addRow("Max Jump (LY):", self._max)

        self._opt = QComboBox()
        self._opt.addItems(["Min distance", "Fewest jumps"])
        form.addRow("Optimize For:", self._opt)

        form.addRow("", _button_row(self, "Find Route",
                                    enter_fields=(self._origin, self._dest,
                                                  self._via, self._max)))
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
        # An empty Via field is the off switch; the core validates the rest
        # (cap, resolution, duplicate terminals) and returns {"error"}.
        via = [p.strip() for p in self._via.text().split(",") if p.strip()]
        self.run_in_background(
            core.calculators.compute_jump_route,
            origin, dest, max_jump, optimize, via,
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
            # The failing hop is not necessarily origin→destination: with
            # waypoints it is whichever leg has no route (e.g. Sol→70 Vir).
            leg = result.get("unreachable_leg") or {"from": o, "to": d}
            note = QLabel(
                f"No route from {leg['from']} to {leg['to']} with jumps ≤ "
                f"{result['max_jump_ly']:.2f} ly — unreachable (disconnected from "
                f"the origin's jump network)."
                + (f"<br>The whole {o} → {d} route fails because of that leg."
                   if result.get("via") else ""))
            note.setStyleSheet("color: #b8860b; font-weight: 600;")
            note.setWordWrap(True)
            self._tables_layout.addWidget(note)
            # With waypoints the chart carries k+2 terminals, so the Find box has
            # something to find; without them it is still just the two endpoints.
            _add_route_chart_tabs(self, result,
                                  find_box=bool(result.get("via")))
            self._finish_render()
            return

        mode = "fewest jumps" if result["optimize"] == "jumps" else "min distance"
        self._tables_layout.addWidget(QLabel(
            f"<b>{result['jumps']} jump(s)</b> · Total Distance: "
            f"<b>{result['total_ly']:.3f} LY</b> · direct line {result['direct_ly']:.3f} LY · "
            f"optimized for {mode}"))

        via = result.get("via") or []
        if via:
            names = [s["name"] for s in result["stars"]]
            revisit = ("  ·  note: this route re-visits a star (each leg is "
                       "planned optimally on its own)"
                       if len(set(names)) != len(names) else "")
            self._tables_layout.addWidget(QLabel(
                "Via (in the visit order chosen, marked <b>◆</b> below): <b>"
                + " → ".join(via) + "</b>" + revisit))

        headers = ["Jump #", "From", "To", "Jump Dist (LY)", "Cumulative (LY)"]
        rows = [
            [str(r["jump"]), r["from"],
             ("◆ " + r["to"]) if r.get("waypoint") else r["to"],
             f"{r['jump_ly']:.3f}", f"{r['cumulative_ly']:.3f}"]
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

    DESCRIPTION = """
    <b>Jump Network / Reachability</b> — everything you can eventually get to from
    one system at a given jump range.<br><br>
    Give a start system and a <i>Max Jump</i> range in light years. Every star in
    the local <code>star_systems</code> catalogue that can be reached by a chain of
    jumps of that length is found and labelled with the <b>minimum number of jumps
    it takes to get there</b> — tier 1 is directly reachable, tier 2 needs one
    intermediate stop, and so on. <i>Max Jumps</i> optionally stops the expansion
    at a chosen tier (blank = go as far as the network reaches).<br><br>
    <b>You get:</b> the stars grouped by jump tier — name, designations, spectral
    type, distance from the start and from Sol — plus totals for how many stars are
    reachable and how many in the catalogue are not.<br><br>
    <b>Diagrams:</b> Star Chart and Star Chart 3D with each dot coloured by its
    jump tier (not by spectral class), so the reachable frontier is visible at a
    glance. This can return thousands of stars — a short jump range keeps it
    manageable.
    """

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

        # Dots carry per-TIER colours (compute_jump_network sets stars[].color),
        # so the spectral-class legend would mislabel them — suppressed here; the
        # tier swatch legend above the table is the key. Names are in column 1.
        _add_route_chart_tabs(self, result, link_view=view, legend_filter=False)
        self._finish_render()
