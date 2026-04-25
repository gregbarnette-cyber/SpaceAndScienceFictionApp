# gui/panels/system_travel.py — Options 32, 33: solar system travel via JPL Horizons.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QPushButton, QLabel, QComboBox,
)

from gui.panels.base import ResultPanel
import core.calculators


# ── Option 32: Planet/Moon/Asteroid ──────────────────────────────────────────

class SystemTravelSolarPanel(ResultPanel):
    """JPL Horizons brachistochrone travel time  (option 32)."""

    def build_inputs(self):
        form = QFormLayout()

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Earth, Mars, Titan")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Jupiter, 433 (Eros)")
        form.addRow("Destination:", self._dest)

        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        self._accel.returnPressed.connect(self._calculate)
        form.addRow("Acceleration (G's):", self._accel)

        self._vcap = QLineEdit("3")
        self._vcap.returnPressed.connect(self._calculate)
        form.addRow("Max Velocity (% of c):", self._vcap)

        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

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
            self.clear_results()
            lbl = QLabel("Acceleration must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return
        try:
            vcap = float(self._vcap.text()) if self._vcap.text().strip() else 3.0
            if vcap <= 0:
                vcap = 3.0
        except ValueError:
            vcap = 3.0

        self.clear_results()
        self.run_in_background(
            core.calculators.compute_travel_time_solar_objects,
            origin, dest, accel, vcap,
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

        origin   = result["origin"]
        dest     = result["destination"]
        accel_g  = result["accel_g"]
        dist_au  = result["distance_au"]
        dist_lm  = result["distance_lm"]
        profiles = result["profiles"]

        headers = ["Acceleration Profile", "Origin", "Destination",
                   "Acceleration (G's)", "Distance (AU)", "Distance (LM)",
                   "Travel Time (Hours)", "Travel Time", "Max Vel"]
        rows = [
            [p["label"], origin, dest, f"{accel_g:.4f}",
             f"{dist_au:.4f}", f"{dist_lm:.4f}",
             f"{p['hours']:.6f}", p["travel_time_str"], p["max_vel"]]
            for p in profiles
        ]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        self.add_result_widget(table)


# ── Option 33: Custom Thrust Duration ────────────────────────────────────────

class SystemTravelThrustPanel(ResultPanel):
    """Custom thrust duration travel time with iterative convergence  (option 33)."""

    def build_inputs(self):
        form = QFormLayout()

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Earth, Mars")
        form.addRow("Origin:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Jupiter, Titan")
        form.addRow("Destination:", self._dest)

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

        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

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
            self.clear_results()
            lbl = QLabel("Acceleration and Burn Duration must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
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

        self.clear_results()
        self.run_in_background(
            core.calculators.compute_travel_time_custom_thrust,
            origin, dest, accel, burn_s, vcap, burn, unit_label,
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

        def _row(label, value):
            lbl = QLabel(f"<b>{label}:</b>  {value}")
            lbl.setWordWrap(True)
            self.add_result_widget(lbl)

        _row("Origin",      result["origin"])
        _row("Destination", result["destination"])
        _row("Distance",
             f"{result['distance_au']:.4f} AU  ({result['distance_lm']:.4f} LM)")
        _row("Acceleration",
             f"{result['accel_g']:.4f} G's  ({result['a_ms2']:.4f} m/s²)")
        if result["burn_value"] is not None:
            _row("Requested Burn Duration",
                 f"{result['burn_value']:.4f} {result['burn_unit_label']}")
        _row("Effective Burn Duration", result["eff_burn_str"])
        _row("Max Velocity Cap",
             f"{result['v_cap_pct']}% c  ({result['v_cap_ms']:,.2f} m/s)")
        _row("Max Velocity Reached",    "Y" if result["vmax_reached"] else "N")
        _row("Time to Reach Max Velocity", result["t_to_vmax_str"])
        _row("Coast Velocity",
             f"{result['v_coast_ms']:,.2f} m/s  ({result['v_coast_pct_c']:.4f}% c)")

        if result["fallback"]:
            note = QLabel("<i>Note: Distance too short for requested burn — "
                          "using continuous accel-to-midpoint profile.</i>")
            note.setWordWrap(True)
            self.add_result_widget(note)
            _row("Acceleration Time",
                 core.calculators.format_travel_time(result["t_accel_hours"]))
            _row("Acceleration Distance",
                 f"{result['d_accel_au']:.4f} AU  ({result['d_accel_lm']:.4f} LM)")
            _row("Coast Time",     "N/A")
            _row("Coast Distance", "N/A")
            _row("Deceleration Time",
                 core.calculators.format_travel_time(result["t_accel_hours"]))
            _row("Deceleration Distance",
                 f"{result['d_accel_au']:.4f} AU  ({result['d_accel_lm']:.4f} LM)")
        else:
            _row("Acceleration Time",
                 core.calculators.format_travel_time(result["t_accel_hours"]))
            _row("Acceleration Distance",
                 f"{result['d_accel_au']:.4f} AU  ({result['d_accel_lm']:.4f} LM)")
            _row("Coast Time",
                 core.calculators.format_travel_time(result["t_coast_hours"]))
            _row("Coast Distance",
                 f"{result['d_coast_au']:.4f} AU  ({result['d_coast_lm']:.4f} LM)")
            _row("Deceleration Time",
                 core.calculators.format_travel_time(result["t_accel_hours"]))
            _row("Deceleration Distance",
                 f"{result['d_accel_au']:.4f} AU  ({result['d_accel_lm']:.4f} LM)")

        n = result["iterations_done"]
        _row("Total Travel Time",
             f"{result['travel_time_str']}  ({result['t_total_hours']:.2f} Hours)")
        note = QLabel(
            f"<i>Destination position estimated via iterative JPL Horizons queries "
            f"({n} iteration{'s' if n != 1 else ''} converged).</i>"
        )
        note.setWordWrap(True)
        self.add_result_widget(note)
