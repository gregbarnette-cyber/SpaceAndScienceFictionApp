# gui/panels/system_travel.py — Options 31, 32: solar system travel via JPL Horizons.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QComboBox, QWidget, QVBoxLayout, QDateEdit, QDialog,
    QGridLayout, QDialogButtonBox, QSizePolicy,
)
from PySide6.QtCore import QDate, Qt, QTimer, QThread, Signal, QObject

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_solar_travel_canvas,
)


def _clear_tables_layout(panel):
    lay = panel._tables_layout
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _fit_table_height(view):
    """Set a fixed height equal to the header plus all row heights.

    Fires at 0 ms and again at 50 ms so the horizontal scrollbar's visibility
    (if columns overflow the panel width) is included in the final height.
    The 50 ms shot is necessary because Qt's LayoutRequest event (posted by
    addWidget) may not be processed before the 0 ms timer fires, meaning
    the scrollbar isn't yet marked visible on the first correction.
    """
    def _apply():
        try:
            view.resizeRowsToContents()
            h = view.horizontalHeader().height() + view.verticalHeader().length()
            h += view.frameWidth() * 2
            sb = view.horizontalScrollBar()
            if sb.isVisible():
                h += sb.sizeHint().height()
            view.setFixedHeight(h)
        except RuntimeError:
            pass  # view was deleted before this shot fired
    _apply()
    QTimer.singleShot(0, _apply)
    QTimer.singleShot(50, _apply)


# Module-level list keeps (thread, worker, bridge) triples alive until the OS
# thread fully exits — same pattern as ResultPanel._live_threads in base.py.
_dialog_threads: list = []


class _BodyInfoWorker(QObject):
    finished = Signal(dict)

    def __init__(self, horizons_id):
        super().__init__()
        self._hid = horizons_id

    def run(self):
        result = core.calculators.fetch_body_properties(self._hid)
        self.finished.emit(result)


class _DialogBridge(QObject):
    """Relay worker results from the worker thread to a plain Python callback
    running safely on the main thread.

    The bridge itself lives in the main thread (no moveToThread call).
    When worker.finished emits from the worker thread and connects to
    bridge.receive, Qt's auto-connection detects the cross-thread scenario
    and queues the call on the main thread's event loop.  receive() then
    calls populate_fn() directly, which is also on the main thread — so
    Qt widgets can be safely created and reparented there.
    """
    _relay = Signal(dict)

    def __init__(self, populate_fn):
        super().__init__()
        self._relay.connect(populate_fn)

    def receive(self, props: dict):
        self._relay.emit(props)


def _show_body_dialog(parent_widget, body_info: dict):
    """Open a non-modal dialog showing physical properties for a solar system body.

    body_info must have at minimum: name, x, y, z (heliocentric AU).
    If horizons_id is present, physical properties are fetched from Horizons.
    """
    import math as _m

    horizons_id = body_info.get("horizons_id", "")
    body_name   = body_info.get("name", "Unknown")
    # Strip "Origin: " / "Destination: " prefixes if present
    display_name = body_name
    for prefix in ("Origin: ", "Destination: "):
        if display_name.startswith(prefix):
            display_name = display_name[len(prefix):]
            break

    dlg = QDialog(parent_widget)
    dlg.setWindowTitle(f"Body Info — {display_name}")
    dlg.setMinimumWidth(520)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.Window)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(12, 12, 12, 8)
    outer.setSpacing(8)

    # Header: name + current position
    dist_sun = _m.sqrt(body_info["x"]**2 + body_info["y"]**2
                       + body_info.get("z", 0.0)**2)
    hdr = QLabel(
        f"<b>{display_name}</b>"
        f"<br/>Heliocentric position  —  "
        f"X: {body_info['x']:.4f} AU,  Y: {body_info['y']:.4f} AU,  "
        f"Z: {body_info.get('z', 0.0):.4f} AU"
        f"<br/>Distance from Sun: <b>{dist_sun:.4f} AU</b>"
        + (f"  ({dist_sun * 8.3167:.3f} LM)" if dist_sun > 0 else "")
    )
    hdr.setWordWrap(True)
    outer.addWidget(hdr)

    # Separator
    sep = QLabel()
    sep.setFrameShape(QLabel.Shape.HLine)
    sep.setFrameShadow(QLabel.Shadow.Sunken)
    outer.addWidget(sep)

    # Properties area — no scroll; dialog resizes to fit after _populate runs
    content = QWidget()
    grid = QGridLayout(content)
    grid.setContentsMargins(4, 4, 4, 4)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(4)
    grid.setColumnStretch(1, 1)
    outer.addWidget(content)

    # Status label (shown while loading)
    status_lbl = QLabel("Fetching physical data from JPL Horizons…")
    status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    outer.addWidget(status_lbl)

    def _add_row(label, value, row):
        lbl = QLabel(f"<b>{label}:</b>")
        val = QLabel(str(value))
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(val, row, 1, Qt.AlignmentFlag.AlignTop)
        return row + 1

    def _populate(props: dict):
        status_lbl.setVisible(False)
        row = 0

        btype = props.get("body_type", "unknown")
        if "error" in props:
            grid.addWidget(QLabel(f"<i>Could not fetch data: {props['error']}</i>"), 0, 0, 1, 2)
            return

        name_full = props.get("name_full", display_name)
        row = _add_row("Full Name", name_full, row)
        row = _add_row("Body Type", btype.title(), row)

        def _show(key, label, unit=""):
            nonlocal row
            val = props.get(key, "N/A")
            if val and val != "N/A":
                row = _add_row(label, f"{val}{' ' + unit if unit else ''}", row)

        if btype == "planet":
            _show("mean_radius_km",   "Mean Radius",             "km")
            _show("mass_str",         "Mass")
            _show("density_gcc",      "Density",                 "g/cm³")
            _show("equ_gravity_ms2",  "Equatorial Gravity",      "m/s²")
            _show("escape_km_s",      "Escape Velocity",         "km/s")
            _show("rot_period",       "Sidereal Rotation Period")
            _show("mean_solar_day",   "Mean Solar Day")
            _show("mean_temp_k",      "Mean Temperature",        "K")
            _show("atm_pressure_bar", "Atmospheric Pressure",    "bar")
            _show("geometric_albedo", "Geometric Albedo")
            _show("obliquity_deg",    "Obliquity",               "°")
            _show("orbital_speed_kms","Orbital Speed",           "km/s")
            _show("orbital_period_y", "Orbital Period",          "yr")
            _show("hills_sphere",     "Hill's Sphere Radius",    "Rp")
            _show("gm_km3s2",         "GM",                      "km³/s²")

        elif btype == "moon":
            _show("mean_radius_km",   "Mean Radius",             "km")
            _show("density_gcc",      "Density",                 "g/cm³")
            _show("gm_km3s2",         "GM",                      "km³/s²")
            _show("geometric_albedo", "Geometric Albedo")
            _show("v10",              "Visual Magnitude V(1,0)")
            _show("sma_km",           "Semi-major Axis (×10³ km)")
            _show("orbital_period_d", "Orbital Period",          "days")
            _show("eccentricity",     "Eccentricity")
            _show("inclination_deg",  "Inclination",             "°")
            _show("rot_period",       "Rotational Period")

        elif btype == "asteroid":
            _show("mean_radius_km",   "Radius",                  "km")
            _show("gm_km3s2",         "GM",                      "km³/s²")
            _show("rot_period_hr",    "Rotation Period",         "hr")
            _show("abs_magnitude",    "Absolute Magnitude (H)")
            _show("slope_g",          "Slope Parameter (G)")
            _show("bv_color",         "B-V Color")
            _show("albedo",           "Geometric Albedo")
            _show("spectral_type",    "Spectral Type")

        elif btype == "comet":
            _show("mean_radius_km",   "Radius",                  "km")
            _show("abs_magnitude_m1", "Total Abs. Magnitude (M1)")
            _show("abs_magnitude_m2", "Nuclear Abs. Magnitude (M2)")

        else:
            grid.addWidget(
                QLabel("<i>No structured physical data available for this body.</i>"),
                0, 0, 1, 2)

        dlg.adjustSize()

    # If we have a Horizons ID, fetch properties in a background thread.
    # _DialogBridge lives in the main thread; Qt auto-connect sees worker
    # (worker thread) → bridge (main thread) and queues the call, so
    # _populate is always invoked on the main thread where widgets are safe.
    if horizons_id:
        thread = QThread()
        worker = _BodyInfoWorker(horizons_id)
        bridge = _DialogBridge(_populate)   # stays in main thread
        worker.moveToThread(thread)
        triple = (thread, worker, bridge)
        _dialog_threads.append(triple)

        thread.started.connect(worker.run)
        worker.finished.connect(bridge.receive)  # cross-thread → auto-queued
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda t=triple: QTimer.singleShot(
                500,
                lambda: (_dialog_threads.remove(t) if t in _dialog_threads else None)
            )
        )
        dlg.finished.connect(thread.quit)
        thread.start()
    else:
        status_lbl.setText("No Horizons ID available for this body.")

    close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_btn.rejected.connect(dlg.close)
    outer.addWidget(close_btn)

    dlg.show()


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

        self._date_lbl = QLabel("")
        self._date_lbl.setVisible(False)
        form.addRow(self._date_lbl)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._tables_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._tables_widget)
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
            self._date_lbl.setVisible(False)
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

        self._date_lbl.setText(f"Departure Date: {result['departure_date']}")
        self._date_lbl.setVisible(True)

        # ── Combined summary + profiles table ─────────────────────────────────
        headers = [
            "Acceleration Profile", "Max Vel",
            "Origin", "Destination", "Acceleration (G's)",
            "Distance (AU)", "Distance (LM)",
            "Total Travel Time (Hours)", "Total Travel Time",
        ]
        rows = [[
            p["label"], p["max_vel"],
            origin, dest,
            f"{accel_g:.4f}",
            f"{dist_au:.4f}",
            f"{dist_lm:.4f}",
            f"{p['hours']:.6f}",
            p["travel_time_str"],
        ] for p in profiles]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        _fit_table_height(view)
        self._tables_layout.addWidget(view)

        if mpl_available() and "origin_xyz" in result:
            map_data = core.viz.prepare_solar_travel_diagram(result)
            if "error" not in map_data:
                self._add_solar_travel_tabs(map_data)

        self._tables_layout.addStretch(1)
        self._finish_render()

    def _add_solar_travel_tabs(self, map_data: dict):
        w2d = QWidget()
        l2d = QVBoxLayout(w2d)
        l2d.setContentsMargins(4, 4, 4, 4)
        canvas, toolbar = make_solar_travel_canvas(
            self, map_data, on_body_click=lambda bi: _show_body_dialog(self, bi))
        l2d.addWidget(toolbar)
        l2d.addWidget(canvas)
        self._viz_tabs_widget.addTab(w2d, "Solar System Map")


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

        self._date_lbl = QLabel("")
        self._date_lbl.setVisible(False)
        form.addRow(self._date_lbl)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._tables_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._tables_widget)
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
            self._date_lbl.setVisible(False)
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        fmt_tt = core.calculators.format_travel_time

        self._date_lbl.setText(f"Departure Date: {result['departure_date']}")
        self._date_lbl.setVisible(True)

        # ── Combined phase + summary table ────────────────────────────────────
        origin = result["origin"]
        dest   = result["destination"]
        accel  = f"{result['accel_g']:.4f}"
        if result["fallback"]:
            coast_dur = coast_au = coast_lm = "N/A"
        else:
            coast_dur = fmt_tt(result["t_coast_hours"])
            coast_au  = f"{result['d_coast_au']:.4f}"
            coast_lm  = f"{result['d_coast_lm']:.4f}"
        phase_headers = [
            "Phase", "Duration",
            "Origin", "Destination", "Acceleration (G's)",
            "Distance (AU)", "Distance (LM)",
            "Total Travel Time (Hours)", "Total Travel Time",
        ]
        phase_rows = [
            ["Acceleration",
             fmt_tt(result["t_accel_hours"]),
             origin, dest, accel,
             f"{result['d_accel_au']:.4f}", f"{result['d_accel_lm']:.4f}",
             "", ""],
            ["Coast",
             coast_dur,
             origin, dest, accel,
             coast_au, coast_lm,
             "", ""],
            ["Deceleration",
             fmt_tt(result["t_accel_hours"]),
             origin, dest, accel,
             f"{result['d_accel_au']:.4f}", f"{result['d_accel_lm']:.4f}",
             "", ""],
            ["Total",
             result["travel_time_str"],
             origin, dest, accel,
             f"{result['distance_au']:.4f}", f"{result['distance_lm']:.4f}",
             f"{result['t_total_hours']:.6f}", result["travel_time_str"]],
        ]
        v1 = self.make_table(phase_headers, phase_rows)
        v1.setSortingEnabled(False)
        _fit_table_height(v1)
        self._tables_layout.addWidget(v1)

        # ── Burn Profile ──────────────────────────────────────────────────────
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
        _fit_table_height(v2)
        self._tables_layout.addWidget(v2)

        n = result["iterations_done"]
        iter_note = QLabel(
            f"<i>Destination position estimated via iterative JPL Horizons queries "
            f"({n} iteration{'s' if n != 1 else ''} converged).</i>"
        )
        iter_note.setWordWrap(True)
        self._tables_layout.addWidget(iter_note)

        # ── Fallback note ─────────────────────────────────────────────────────
        if result["fallback"]:
            note = QLabel("<i>Note: Distance too short for requested burn — "
                          "using continuous accel-to-midpoint profile.</i>")
            note.setWordWrap(True)
            self._tables_layout.addWidget(note)

        if mpl_available() and "origin_xyz" in result:
            map_data = core.viz.prepare_solar_travel_diagram(result)
            if "error" not in map_data:
                self._add_solar_travel_tabs(map_data)

        self._tables_layout.addStretch(1)
        self._finish_render()

    def _add_solar_travel_tabs(self, map_data: dict):
        w2d = QWidget()
        l2d = QVBoxLayout(w2d)
        l2d.setContentsMargins(4, 4, 4, 4)
        canvas, toolbar = make_solar_travel_canvas(
            self, map_data, on_body_click=lambda bi: _show_body_dialog(self, bi))
        l2d.addWidget(toolbar)
        l2d.addWidget(canvas)
        self._viz_tabs_widget.addTab(w2d, "Solar System Map")
