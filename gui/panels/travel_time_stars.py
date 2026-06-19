# gui/panels/travel_time_stars.py — Options 20, 21: travel time between 2 stars.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QWidget, QVBoxLayout,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.calculators
from gui.panels.route_planning import add_two_star_chart_tabs


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


class _TravelTimeStarsBase(DiagramToggleMixin, ResultPanel):
    """Base class — subclasses set _use_times_c and _vel_label/_vel_ph."""

    _use_times_c = False
    _vel_label   = "Velocity (light years / hour):"
    _vel_ph      = "e.g. 0.0001141"

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._origin = QLineEdit()
        self._origin.setPlaceholderText("e.g. Sol, Vega, Alpha Centauri")
        form.addRow("Origin Star:", self._origin)

        self._dest = QLineEdit()
        self._dest.setPlaceholderText("e.g. Epsilon Eridani, HD 10700")
        form.addRow("Destination Star:", self._dest)

        self._velocity = QLineEdit()
        self._velocity.setPlaceholderText(self._vel_ph)
        self._velocity.returnPressed.connect(self._calculate)
        form.addRow(self._vel_label, self._velocity)

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
        vel_s  = self._velocity.text().strip()
        if not origin or not dest or not vel_s:
            return
        try:
            vel = float(vel_s)
            if vel <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_layout(self._tables_layout)
            lbl = QLabel("Velocity must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return

        self._prepare_render()
        _clear_layout(self._tables_layout)
        ly_hr   = None if self._use_times_c else vel
        times_c = vel  if self._use_times_c else None
        self.run_in_background(
            core.calculators.compute_travel_time_between_stars,
            origin, dest, ly_hr, times_c,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._prepare_render()
        _clear_layout(self._tables_layout)
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        s1 = result["origin_info"]
        s2 = result["dest_info"]

        star_headers = ["Star", "Star Designations", "RA", "DEC", "Light Years"]
        star_rows = [
            [s1["name"], s1["desig_str"],
             s1.get("ra_hms", ""), s1.get("dec_dms", ""), f"{s1['ly']:.4f}"],
            [s2["name"], s2["desig_str"],
             s2.get("ra_hms", ""), s2.get("dec_dms", ""), f"{s2['ly']:.4f}"],
        ]
        star_table = self.make_table(star_headers, star_rows)
        star_table.setSortingEnabled(False)
        self._tables_layout.addWidget(star_table)

        dist_ly = result["distance_ly"]
        ly_hr   = result["ly_hr"]
        times_c = result["times_c"]
        hrs     = result["total_hours"]
        tts     = result["travel_time_str"]

        if self._use_times_c:
            headers = ["Origin", "Destination", "Distance (LYs)",
                       "X Times Speed of Light", "LY/HR",
                       "Travel Time (Hours)", "Travel Time"]
            row = [s1["name"], s2["name"], f"{dist_ly:.6f}",
                   f"{times_c:.6f}", f"{ly_hr:.6f}", f"{hrs:.6f}", tts]
        else:
            headers = ["Origin", "Destination", "Distance (LYs)",
                       "LY/HR", "X Times Speed of Light",
                       "Travel Time (Hours)", "Travel Time"]
            row = [s1["name"], s2["name"], f"{dist_ly:.6f}",
                   f"{ly_hr:.6f}", f"{times_c:.6f}", f"{hrs:.6f}", tts]

        result_table = self.make_table(headers, [row])
        result_table.setSortingEnabled(False)
        self._tables_layout.addWidget(result_table)

        add_two_star_chart_tabs(self, result, "travel")
        self._finish_render()


class TravelTimeStarsLyHrPanel(_TravelTimeStarsBase):
    """Travel time between 2 stars at LY/HR  (option 20)."""

    _use_times_c = False
    _vel_label   = "Velocity (light years / hour):"
    _vel_ph      = "e.g. 0.0001141"


class TravelTimeStarsTimesCPanel(_TravelTimeStarsBase):
    """Travel time between 2 stars at ×c  (option 21)."""

    _use_times_c = True
    _vel_label   = "Velocity (× speed of light):"
    _vel_ph      = "e.g. 0.001"
