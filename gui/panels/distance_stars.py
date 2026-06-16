# gui/panels/distance_stars.py — Options 17, 18, 19: star distance and proximity.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QSizePolicy,
    QTabWidget, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt, QItemSelectionModel

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_star_map_canvas, make_star_map_3d_canvas,
    make_star_chart_canvas, make_star_chart_3d_canvas,
    make_hr_canvas, make_sky_canvas,
)


# ── Option 17: Distance Between 2 Stars ──────────────────────────────────────

class DistanceBetweenStarsPanel(ResultPanel):
    """Two star name inputs → distance in light years  (option 17)."""

    def build_inputs(self):
        form = QFormLayout()

        self._star1 = QLineEdit()
        self._star1.setPlaceholderText("e.g. Sol, Vega, Alpha Centauri")
        form.addRow("Star 1:", self._star1)

        self._star2 = QLineEdit()
        self._star2.setPlaceholderText("e.g. Epsilon Eridani, HD 10700")
        form.addRow("Star 2:", self._star2)

        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._star2.returnPressed.connect(self._calculate)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _calculate(self):
        s1 = self._star1.text().strip()
        s2 = self._star2.text().strip()
        if not s1 or not s2:
            return
        self.clear_results()
        self.run_in_background(
            core.calculators.compute_distance_between_stars,
            s1, s2,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self.add_result_widget(lbl)
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
        self.add_result_widget(lbl)

        headers = ["Star", "Star Designations", "RA", "DEC", "Light Years"]
        rows = [
            [s1["name"], s1["desig_str"],
             s1.get("ra_hms", ""), s1.get("dec_dms", ""), f"{s1['ly']:.4f}"],
            [s2["name"], s2["desig_str"],
             s2.get("ra_hms", ""), s2.get("dec_dms", ""), f"{s2['ly']:.4f}"],
        ]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        self.add_result_widget(table)


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


def _build_star_chart_3d_tab(panel, map_stars, limit_ly, on_star_click=None):
    """Build a "Star Chart 3D" tab widget with preset viewpoint buttons.

    Mirrors the Map 3D tab pattern but uses the dark-themed
    make_star_chart_3d_canvas helper. Returns (widget, canvas) so the caller can
    keep the canvas ref for O15 row↔map linking.
    """
    chart3d_w = QWidget()
    chart3d_l = QVBoxLayout(chart3d_w)
    chart3d_l.setContentsMargins(4, 4, 4, 4)
    chart3d_l.setSpacing(0)
    canvas3d, toolbar3d, ax3d = make_star_chart_3d_canvas(
        panel, map_stars, limit_ly=limit_ly, on_star_click=on_star_click,
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
    table row) matches nothing and is a graceful no-op."""
    view = getattr(panel, "_link_view", None)
    model = view.model() if view is not None else None
    if model is None or not name:
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

    # Labeled X-Y star chart (dark theme).
    chart_w = QWidget()
    chart_l = QVBoxLayout(chart_w)
    chart_l.setContentsMargins(4, 4, 4, 4)
    canvas_sc, toolbar_sc = make_star_chart_canvas(
        panel, map_stars, limit_ly=limit, on_star_click=click_cb,
        legend_filter=True,
    )
    chart_l.addWidget(toolbar_sc)
    chart_l.addWidget(canvas_sc)
    panel._viz_tabs_widget.addTab(chart_w, "Star Chart")
    canvases.append(canvas_sc)

    # Star Chart 3D — labeled 3D companion.
    chart3d_w, canvas_sc3d = _build_star_chart_3d_tab(
        panel, map_stars, limit, on_star_click=click_cb)
    panel._viz_tabs_widget.addTab(chart3d_w, "Star Chart 3D")
    canvases.append(canvas_sc3d)

    _wire_row_map_linking(panel, panel._link_view, canvases)


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
