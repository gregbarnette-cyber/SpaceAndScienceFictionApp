# gui/panels/system_travel.py — Options 31, 32: solar system travel via JPL Horizons.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QComboBox, QWidget, QVBoxLayout, QSizePolicy, QDateEdit,
)
from PySide6.QtCore import QDate

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_solar_travel_canvas, make_solar_travel_canvas_3d,
)


def _clear_tables_layout(panel):
    lay = panel._tables_layout
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


# ── Option 31: Planet/Moon/Asteroid ──────────────────────────────────────────

class SystemTravelSolarPanel(DiagramToggleMixin, ResultPanel):
    """JPL Horizons brachistochrone travel time  (option 31)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Earth, Mars, Titan")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Jupiter, 433 (Eros)")
        form.addRow("Destination:", self._dest)

        self._departure_date = QDateEdit()
        self._departure_date.setDate(QDate.currentDate())
        self._departure_date.setCalendarPopup(True)
        self._departure_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Departure Date:", self._departure_date)

        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        self._accel.returnPressed.connect(self._calculate)
        form.addRow("Acceleration (G's):", self._accel)

        self._vcap = QLineEdit("3")
        self._vcap.returnPressed.connect(self._calculate)
        form.addRow("Max Velocity (% of c):", self._vcap)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
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
        origin = self._origin.text().strip()
        dest   = self._dest.text().strip()
        if not origin or not dest:
            return
        try:
            accel = float(self._accel.text())
            if accel <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_tables_layout(self)
            lbl = QLabel("Acceleration must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return
        try:
            vcap = float(self._vcap.text()) if self._vcap.text().strip() else 3.0
            if vcap <= 0:
                vcap = 3.0
        except ValueError:
            vcap = 3.0

        qdate = self._departure_date.date()
        date_str = qdate.toString("yyyy-MM-dd")

        self.run_in_background(
            core.calculators.compute_travel_time_solar_objects,
            origin, dest, accel, vcap,
            on_result=self._render,
            departure_date=date_str,
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

        origin   = result["origin"]
        dest     = result["destination"]
        accel_g  = result["accel_g"]
        dist_au  = result["distance_au"]
        dist_lm  = result["distance_lm"]
        profiles = result["profiles"]

        date_lbl = QLabel(f"Departure Date: {result['departure_date']}")
        self._tables_layout.addWidget(date_lbl)

        # ── Summary table ─────────────────────────────────────────────────────
        sum_headers = [
            "Origin", "Destination", "Acceleration (G's)",
            "Distance (AU)", "Distance (LM)",
        ]
        sum_rows = [[
            origin, dest,
            f"{accel_g:.4f}",
            f"{dist_au:.4f}",
            f"{dist_lm:.4f}",
        ]]
        sum_view = self.make_table(sum_headers, sum_rows)
        sum_view.setSortingEnabled(False)
        self._tables_layout.addWidget(sum_view)

        # ── Profiles table ────────────────────────────────────────────────────
        headers = ["Acceleration Profile", "Travel Time (Hours)", "Travel Time", "Max Vel"]
        rows = [
            [p["label"], f"{p['hours']:.6f}", p["travel_time_str"], p["max_vel"]]
            for p in profiles
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if mpl_available() and "origin_xyz" in result:
            map_data = core.viz.prepare_solar_travel_diagram(result)
            if "error" not in map_data:
                self._add_solar_travel_tabs(map_data)

        self._finish_render()

    def _add_solar_travel_tabs(self, map_data: dict):
        # 2D tab
        w2d = QWidget()
        l2d = QVBoxLayout(w2d)
        l2d.setContentsMargins(4, 4, 4, 4)
        canvas, toolbar = make_solar_travel_canvas(self, map_data)
        l2d.addWidget(toolbar)
        l2d.addWidget(canvas)
        self._viz_tabs_widget.addTab(w2d, "Solar System Map")

        # 3D tab with viewpoint preset buttons
        w3d = QWidget()
        l3d = QVBoxLayout(w3d)
        l3d.setContentsMargins(4, 4, 4, 4)
        l3d.setSpacing(0)
        canvas3d, toolbar3d, ax3d = make_solar_travel_canvas_3d(self, map_data)
        preset_bar = QWidget()
        preset_bar.setFixedHeight(24)
        preset_row = QHBoxLayout(preset_bar)
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        for lbl_txt, elev, azim in [
            ("Top View", 90, 0),
            ("Side View", 0, 0),
            ("3D Perspective", 30, -60),
        ]:
            btn = QPushButton(lbl_txt)
            btn.setFixedHeight(24)
            def _make_cb(e=elev, a=azim):
                def _cb():
                    try:
                        if toolbar3d.mode:
                            toolbar3d.zoom() if "zoom" in str(toolbar3d.mode) else toolbar3d.pan()
                    except Exception:
                        pass
                    ax3d.view_init(elev=e, azim=a)
                    canvas3d.draw_idle()
                return _cb
            btn.clicked.connect(_make_cb())
            preset_row.addWidget(btn)
        preset_row.addStretch()
        l3d.addWidget(preset_bar)
        l3d.addWidget(toolbar3d)
        l3d.addWidget(canvas3d)
        self._viz_tabs_widget.addTab(w3d, "3D View")


# ── Option 32: Custom Thrust Duration ────────────────────────────────────────

class SystemTravelThrustPanel(DiagramToggleMixin, ResultPanel):
    """Custom thrust duration travel time with iterative convergence  (option 32)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Earth, Mars")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Jupiter, Titan")
        form.addRow("Destination:", self._dest)

        self._departure_date = QDateEdit()
        self._departure_date.setDate(QDate.currentDate())
        self._departure_date.setCalendarPopup(True)
        self._departure_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Departure Date:", self._departure_date)

        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        form.addRow("Acceleration (G's):", self._accel)

        self._burn = QLineEdit()
        self._burn.setPlaceholderText("e.g. 7.0")
        self._burn.returnPressed.connect(self._calculate)
        form.addRow("Burn Duration:", self._burn)

        self._unit = QComboBox()
        self._unit.addItems(["Days", "Hours", "Weeks"])
        form.addRow("Burn Duration Unit:", self._unit)

        self._vcap = QLineEdit("3")
        self._vcap.returnPressed.connect(self._calculate)
        form.addRow("Max Velocity (% of c):", self._vcap)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
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
        origin = self._origin.text().strip()
        dest   = self._dest.text().strip()
        if not origin or not dest:
            return
        try:
            accel = float(self._accel.text())
            burn  = float(self._burn.text())
            if accel <= 0 or burn <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_tables_layout(self)
            lbl = QLabel("Acceleration and Burn Duration must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return

        unit_label   = self._unit.currentText()
        unit_seconds = {"Hours": 3600.0, "Days": 86400.0, "Weeks": 604800.0}
        burn_s = burn * unit_seconds[unit_label]

        try:
            vcap = float(self._vcap.text()) if self._vcap.text().strip() else 3.0
            if vcap <= 0:
                vcap = 3.0
        except ValueError:
            vcap = 3.0

        qdate = self._departure_date.date()
        date_str = qdate.toString("yyyy-MM-dd")

        self.run_in_background(
            core.calculators.compute_travel_time_custom_thrust,
            origin, dest, accel, burn_s, vcap, burn, unit_label,
            on_result=self._render,
            departure_date=date_str,
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

        fmt_tt = core.calculators.format_travel_time

        date_lbl = QLabel(f"Departure Date: {result['departure_date']}")
        self._tables_layout.addWidget(date_lbl)

        # ── Table 1: Travel Summary ───────────────────────────────────────────
        sum_headers = [
            "Origin", "Destination", "Acceleration (G's)",
            "Distance (AU)", "Distance (LM)",
            "Total Travel Time (Hours)", "Total Travel Time",
        ]
        sum_rows = [[
            result["origin"],
            result["destination"],
            f"{result['accel_g']:.4f}",
            f"{result['distance_au']:.4f}",
            f"{result['distance_lm']:.4f}",
            f"{result['t_total_hours']:.6f}",
            result["travel_time_str"],
        ]]
        v1 = self.make_table(sum_headers, sum_rows)
        v1.setSortingEnabled(False)
        self._tables_layout.addWidget(v1)

        # ── Table 2: Burn Profile ─────────────────────────────────────────────
        req_burn = (f"{result['burn_value']:.4f} {result['burn_unit_label']}"
                    if result["burn_value"] is not None else "N/A")
        burn_headers = [
            "Req. Burn Duration", "Eff. Burn Duration",
            "Max Vel Cap", "Max Vel Reached",
            "Time to Max Vel", "Coast Velocity",
        ]
        burn_rows = [[
            req_burn,
            result["eff_burn_str"],
            f"{result['v_cap_pct']}% c  ({result['v_cap_ms']:,.2f} m/s)",
            "Y" if result["vmax_reached"] else "N",
            result["t_to_vmax_str"],
            f"{result['v_coast_ms']:,.2f} m/s  ({result['v_coast_pct_c']:.4f}% c)",
        ]]
        v2 = self.make_table(burn_headers, burn_rows)
        v2.setSortingEnabled(False)
        self._tables_layout.addWidget(v2)

        # ── Fallback note ─────────────────────────────────────────────────────
        if result["fallback"]:
            note = QLabel("<i>Note: Distance too short for requested burn — "
                          "using continuous accel-to-midpoint profile.</i>")
            note.setWordWrap(True)
            self._tables_layout.addWidget(note)

        # ── Table 3: Phase Breakdown ──────────────────────────────────────────
        phase_headers = ["Phase", "Duration", "Distance (AU)", "Distance (LM)"]
        if result["fallback"]:
            coast_dur = coast_au = coast_lm = "N/A"
        else:
            coast_dur = fmt_tt(result["t_coast_hours"])
            coast_au  = f"{result['d_coast_au']:.4f}"
            coast_lm  = f"{result['d_coast_lm']:.4f}"
        phase_rows = [
            ["Acceleration",
             fmt_tt(result["t_accel_hours"]),
             f"{result['d_accel_au']:.4f}",
             f"{result['d_accel_lm']:.4f}"],
            ["Coast", coast_dur, coast_au, coast_lm],
            ["Deceleration",
             fmt_tt(result["t_accel_hours"]),
             f"{result['d_accel_au']:.4f}",
             f"{result['d_accel_lm']:.4f}"],
            ["Total",
             result["travel_time_str"],
             f"{result['distance_au']:.4f}",
             f"{result['distance_lm']:.4f}"],
        ]
        v3 = self.make_table(phase_headers, phase_rows)
        v3.setSortingEnabled(False)
        self._tables_layout.addWidget(v3)

        n = result["iterations_done"]
        iter_note = QLabel(
            f"<i>Destination position estimated via iterative JPL Horizons queries "
            f"({n} iteration{'s' if n != 1 else ''} converged).</i>"
        )
        iter_note.setWordWrap(True)
        self._tables_layout.addWidget(iter_note)

        if mpl_available() and "origin_xyz" in result:
            map_data = core.viz.prepare_solar_travel_diagram(result)
            if "error" not in map_data:
                self._add_solar_travel_tabs(map_data)

        self._finish_render()

    def _add_solar_travel_tabs(self, map_data: dict):
        # 2D tab
        w2d = QWidget()
        l2d = QVBoxLayout(w2d)
        l2d.setContentsMargins(4, 4, 4, 4)
        canvas, toolbar = make_solar_travel_canvas(self, map_data)
        l2d.addWidget(toolbar)
        l2d.addWidget(canvas)
        self._viz_tabs_widget.addTab(w2d, "Solar System Map")

        # 3D tab with viewpoint preset buttons
        w3d = QWidget()
        l3d = QVBoxLayout(w3d)
        l3d.setContentsMargins(4, 4, 4, 4)
        l3d.setSpacing(0)
        canvas3d, toolbar3d, ax3d = make_solar_travel_canvas_3d(self, map_data)
        preset_bar = QWidget()
        preset_bar.setFixedHeight(24)
        preset_row = QHBoxLayout(preset_bar)
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        for lbl_txt, elev, azim in [
            ("Top View", 90, 0),
            ("Side View", 0, 0),
            ("3D Perspective", 30, -60),
        ]:
            btn = QPushButton(lbl_txt)
            btn.setFixedHeight(24)
            def _make_cb(e=elev, a=azim):
                def _cb():
                    try:
                        if toolbar3d.mode:
                            toolbar3d.zoom() if "zoom" in str(toolbar3d.mode) else toolbar3d.pan()
                    except Exception:
                        pass
                    ax3d.view_init(elev=e, azim=a)
                    canvas3d.draw_idle()
                return _cb
            btn.clicked.connect(_make_cb())
            preset_row.addWidget(btn)
        preset_row.addStretch()
        l3d.addWidget(preset_bar)
        l3d.addWidget(toolbar3d)
        l3d.addWidget(canvas3d)
        self._viz_tabs_widget.addTab(w3d, "3D View")
