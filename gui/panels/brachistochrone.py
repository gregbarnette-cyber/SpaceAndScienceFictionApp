# gui/panels/brachistochrone.py — Options 29, 30, 31: brachistochrone calculators.
# Each option has its own standalone panel.

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPushButton, QLabel

from gui.panels.base import ResultPanel
import core.calculators


def _render_profiles(panel, result):
    """Render brachistochrone profile table; returns the QTableView."""
    accel_g  = result["accel_g"]
    profiles = result["profiles"]
    hours_v  = result.get("hours")
    dist_au  = result.get("distance_au")
    dist_lm  = result.get("distance_lm")
    tts_v    = result.get("travel_time_str")

    if hours_v is not None:
        headers = ["Acceleration Profile", "Acceleration (G's)",
                   "Travel Time (Hours)", "Travel Time",
                   "Distance (AU)", "Distance (LM)", "Max Vel"]
        rows = [[p["label"], f"{accel_g:.4f}", f"{hours_v:.6f}", tts_v,
                 f"{p['distance_au']:.4f}", f"{p['distance_lm']:.4f}", p["max_vel"]]
                for p in profiles]
    else:
        headers = ["Acceleration Profile", "Acceleration (G's)",
                   "Distance (AU)", "Distance (LM)",
                   "Travel Time (Hours)", "Travel Time", "Max Vel"]
        rows = [[p["label"], f"{accel_g:.4f}", f"{dist_au:.4f}", f"{dist_lm:.4f}",
                 f"{p['hours']:.6f}", p["travel_time_str"], p["max_vel"]]
                for p in profiles]

    table = panel.make_table(headers, rows)
    table.setSortingEnabled(False)
    return table


# ── Option 29: Accel → Distance ───────────────────────────────────────────────

class BrachistochroneAccelPanel(ResultPanel):
    """Acceleration + time → distance  (option 29)."""

    def build_inputs(self):
        form = QFormLayout()
        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        form.addRow("Acceleration (G's):", self._accel)
        self._hours = QLineEdit()
        self._hours.setPlaceholderText("e.g. 24.0")
        form.addRow("Travel Time (Hours):", self._hours)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._hours.returnPressed.connect(self._calculate)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _calculate(self):
        try:
            accel = float(self._accel.text())
            hours = float(self._hours.text())
            if accel <= 0 or hours <= 0:
                raise ValueError
        except ValueError:
            self.clear_results()
            lbl = QLabel("Acceleration and Travel Time must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return
        result = core.calculators.compute_distance_at_acceleration(accel, hours)
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
        else:
            self.add_result_widget(_render_profiles(self, result))


# ── Option 30: Distance in AU ─────────────────────────────────────────────────

class BrachistochroneAuPanel(ResultPanel):
    """Acceleration + distance (AU) → travel time  (option 30)."""

    def build_inputs(self):
        form = QFormLayout()
        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        form.addRow("Acceleration (G's):", self._accel)
        self._dist = QLineEdit()
        self._dist.setPlaceholderText("e.g. 4.2")
        form.addRow("Distance (AU):", self._dist)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._dist.returnPressed.connect(self._calculate)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _calculate(self):
        try:
            accel = float(self._accel.text())
            dist  = float(self._dist.text())
            if accel <= 0 or dist <= 0:
                raise ValueError
        except ValueError:
            self.clear_results()
            lbl = QLabel("Acceleration and Distance must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return
        result = core.calculators.compute_travel_time_system_au(accel, dist)
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
        else:
            self.add_result_widget(_render_profiles(self, result))


# ── Option 31: Distance in LM ─────────────────────────────────────────────────

class BrachistochroneLmPanel(ResultPanel):
    """Acceleration + distance (light minutes) → travel time  (option 31)."""

    def build_inputs(self):
        form = QFormLayout()
        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        form.addRow("Acceleration (G's):", self._accel)
        self._dist = QLineEdit()
        self._dist.setPlaceholderText("e.g. 35.0")
        form.addRow("Distance (Light Minutes):", self._dist)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._dist.returnPressed.connect(self._calculate)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _calculate(self):
        try:
            accel = float(self._accel.text())
            dist  = float(self._dist.text())
            if accel <= 0 or dist <= 0:
                raise ValueError
        except ValueError:
            self.clear_results()
            lbl = QLabel("Acceleration and Distance must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return
        result = core.calculators.compute_travel_time_system_lm(accel, dist)
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
        else:
            self.add_result_widget(_render_profiles(self, result))
