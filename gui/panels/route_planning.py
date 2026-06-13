# gui/panels/route_planning.py — Phase I: Multi-System / Route Planning (GUI-only).
#
# Three panels under the "Route Planning" nav category:
#   MultiStopJourneyPanel   → core.calculators.compute_multi_stop_journey
#   NearestNeighborPanel    → core.calculators.compute_nearest_neighbor_chain
#   TradeRoutePlannerPanel  → core.calculators.compute_trade_route_mst   (stretch)
#
# All inherit (DiagramToggleMixin, ResultPanel) and follow the opts-18/19 pattern.
# Maps reuse the dark-navy GCNS "Star Chart" / "Star Chart 3D" diagrams with the
# new routes= overlay; coordinates are shifted so the route's origin/start/center
# sits at the chart origin (gold ★) with distance rings measured from it.

import math

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_star_chart_canvas, make_star_chart_3d_canvas,
)


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


def _button_row(panel, run_label):
    """Standard run + Show Diagrams button row; sets panel.run_btn / _show_diagrams_btn."""
    btn_widget = QWidget()
    row = QHBoxLayout(btn_widget)
    row.setContentsMargins(0, 0, 0, 0)
    panel.run_btn = QPushButton(run_label)
    panel.run_btn.clicked.connect(panel._search)
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

        form.addRow("", _button_row(self, "Plan Journey"))
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

        form.addRow("", _button_row(self, "Build Chain"))
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
