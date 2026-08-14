# gui/panels/distance_stars.py — Options 17, 18, 19: star distance and proximity.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QSizePolicy, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_star_map_canvas, make_star_map_3d_canvas,
    make_hr_canvas, make_sky_canvas,
)
from gui.panels.diagram_tabs import (
    _build_iso_chart_tab, _star_click_select, _wire_row_map_linking,
    # O18 find box — moved to diagram_tabs (see the note further down). Only
    # `_add_find_box` is called here; the other three are RE-EXPORTS with no
    # in-module use, kept so `tests/test_viz_phase_o.py::O18FindTest` can go on
    # importing them from this module. An "unused import" cleanup would silently
    # break those tests.
    _add_find_box, _add_reset_diagram_button,
    _norm_find, _find_on_map, _clear_find,   # noqa: F401  (re-export)
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

        # The 2-row table holds star names in column 0, so O15 row↔map linking
        # works here (clicking a dot selects its row and rings it on both charts).
        add_two_star_chart_tabs(self, result, "distance", link_view=table)
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


# ── O18 — Find-Star-on-Map box ───────────────────────────────────────────────
# Moved to gui/panels/diagram_tabs.py (Route-Find, 2026-07-31) so the seven Route
# Planning panels can share it — it could not stay here, because this module
# imports route_planning, so the reverse import would be circular. Imported (and
# partly re-exported) at the top of this file.


def _add_map_tabs(panel, map_stars, limit, title, result):
    """Build the opt-18/19 diagram tabs in display order — Star Chart, Star Chart
    3D, HR Diagram, Night Sky, Map X–Y, Map X–Z, Map 3D — and wire O15 row↔map
    linking. Star Chart is the default selected tab. Appends tabs to
    panel._viz_tabs_widget and expects panel._link_view to already hold the result
    table."""
    canvases = []
    click_cb = lambda nm: _star_click_select(panel, nm)

    # Labeled X-Y star chart (dark theme) + O17 isochrone control — the default
    # tab. The helper appends the live canvas to `canvases` (re-appended on each
    # Apply rebuild).
    chart_w = _build_iso_chart_tab(panel, map_stars, limit, click_cb,
                                   canvases, is_3d=False)
    panel._viz_tabs_widget.addTab(chart_w, "Star Chart")

    # Star Chart 3D — labeled 3D companion + O17 isochrone control.
    chart3d_w = _build_iso_chart_tab(panel, map_stars, limit, click_cb,
                                     canvases, is_3d=True)
    panel._viz_tabs_widget.addTab(chart3d_w, "Star Chart 3D")

    # HR Diagram (O2b) + Night Sky (O1) — between the star charts and the maps.
    _add_hr_tab(panel, result)
    _add_night_sky_tab(panel, result)

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

    _wire_row_map_linking(panel, panel._link_view, canvases)
    _add_find_box(panel)
    _add_reset_diagram_button(panel)
    panel._viz_tabs_widget.setCurrentIndex(0)   # default to Star Chart


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
                    result,
                )

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
                    result,
                )

        self._finish_render()
