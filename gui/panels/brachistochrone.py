# gui/panels/brachistochrone.py — Options 24, 29, 30: brachistochrone calculators.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QWidget,
    QVBoxLayout, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import mpl_available, make_profile_canvas


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _render_profiles_table(panel, result):
    """Build the brachistochrone profile table; returns the QTableView."""
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


def _add_profile_tab(panel, result):
    """Add the Phase O O9 'Acceleration Profiles' viz tab to panel._viz_tabs_widget.

    No-op when matplotlib is unavailable or the profile reconstruction yields no
    data (so the host render is unchanged when the tab can't be built).
    """
    if not mpl_available():
        return
    data = core.viz.prepare_brachistochrone_profiles(result)
    if not data or "error" in data:
        return
    canvas, toolbar = make_profile_canvas(panel, data)
    if canvas is None:
        return
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    panel._viz_tabs_widget.addTab(w, "Acceleration Profiles")


class _BrachistochroneProfilePanel(DiagramToggleMixin, ResultPanel):
    """Shared scaffold: two-field form → profile table + O9 profile chart tab.

    Subclasses set _field2_label / _field2_ph / _field2_name and _compute_fn (a
    staticmethod wrapping the core function called as fn(accel, value)).
    """

    _field2_label = "Value:"
    _field2_ph    = ""
    _field2_name  = "Value"
    _compute_fn   = None

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._accel = QLineEdit()
        self._accel.setPlaceholderText("e.g. 1.0")
        form.addRow("Acceleration (G's):", self._accel)

        self._field2 = QLineEdit()
        self._field2.setPlaceholderText(self._field2_ph)
        self._field2.returnPressed.connect(self._calculate)
        form.addRow(self._field2_label, self._field2)

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
        self._tables_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._tables_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._tables_widget)
        self._setup_diagram_view()
        self._input_count = self._layout.count()

    def _calculate(self):
        try:
            accel = float(self._accel.text())
            value = float(self._field2.text())
            if accel <= 0 or value <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_layout(self._tables_layout)
            lbl = QLabel(f"Acceleration and {self._field2_name} must be positive numbers.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return
        self._render(self._compute_fn(accel, value))

    def _render(self, result):
        self._prepare_render()
        _clear_layout(self._tables_layout)
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return
        self._tables_layout.addWidget(_render_profiles_table(self, result))
        _add_profile_tab(self, result)
        self._tables_layout.addStretch(1)
        self._finish_render()


# ── Option 24: Accel + time → distance ────────────────────────────────────────

class BrachistochroneAccelPanel(_BrachistochroneProfilePanel):
    """Acceleration + time → distance  (option 24)."""

    _field2_label = "Travel Time (Hours):"
    _field2_ph    = "e.g. 24.0"
    _field2_name  = "Travel Time"
    _compute_fn   = staticmethod(core.calculators.compute_distance_at_acceleration)


# ── Option 29: Accel + distance (AU) → travel time ────────────────────────────

class BrachistochroneAuPanel(_BrachistochroneProfilePanel):
    """Acceleration + distance (AU) → travel time  (option 29)."""

    _field2_label = "Distance (AU):"
    _field2_ph    = "e.g. 4.2"
    _field2_name  = "Distance"
    _compute_fn   = staticmethod(core.calculators.compute_travel_time_system_au)


# ── Option 30: Accel + distance (LM) → travel time ────────────────────────────

class BrachistochroneLmPanel(_BrachistochroneProfilePanel):
    """Acceleration + distance (light minutes) → travel time  (option 30)."""

    _field2_label = "Distance (Light Minutes):"
    _field2_ph    = "e.g. 35.0"
    _field2_name  = "Distance"
    _compute_fn   = staticmethod(core.calculators.compute_travel_time_system_lm)
