# gui/panels/distance.py — Options 23 (distance at ly/hr) and 24 (distance at ×c).
# Each option has its own standalone panel.

from PySide6.QtWidgets import QFormLayout, QPushButton, QLabel, QLineEdit
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


class _DistanceBase(ResultPanel):
    """Base for two-input distance-traveled panels."""

    _fields = []   # list of (label, placeholder)

    def build_inputs(self):
        form = QFormLayout()
        self._inputs = []
        for label, ph in self._fields:
            inp = QLineEdit()
            inp.setPlaceholderText(ph)
            form.addRow(label, inp)
            self._inputs.append(inp)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()
        for inp in self._inputs:
            inp.returnPressed.connect(self._calculate)

    def build_results_area(self):
        self._result_lbl = QLabel()
        self._result_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result_lbl.setWordWrap(True)
        self._layout.addWidget(self._result_lbl)
        self._layout.addStretch()

    def _calculate(self):
        vals = []
        for inp in self._inputs:
            try:
                vals.append(float(inp.text().strip()))
            except ValueError:
                self._result_lbl.setText("Invalid input — please enter a number in each field.")
                self._result_lbl.setStyleSheet("color: red;")
                return
        result = self._compute(*vals)
        self._result_lbl.setText(self._format(result))
        self._result_lbl.setStyleSheet("")

    def _compute(self, *vals):
        raise NotImplementedError

    def _format(self, result):
        raise NotImplementedError


class DistanceLyHrPanel(_DistanceBase):
    """Distance traveled at ly/hr  (option 23)."""

    _fields = [
        ("Travel time (hours):", "e.g. 100"),
        ("Velocity (ly/hr):",    "e.g. 0.001"),
    ]

    def _compute(self, hours, ly_hr):
        return core.calculators.compute_distance_traveled_ly_hr(ly_hr, hours)

    def _format(self, r):
        return (f"Traveling at {r['ly_hr']} ly/hr for {r['hours']} hours "
                f"covers {r['distance_ly']:.6f} light years")


class DistanceTimesCPanel(_DistanceBase):
    """Distance traveled at ×c  (option 24)."""

    _fields = [
        ("Travel time (hours):", "e.g. 100"),
        ("Velocity (×c):",       "e.g. 8.77"),
    ]

    def _compute(self, hours, times_c):
        return core.calculators.compute_distance_traveled_times_c(times_c, hours)

    def _format(self, r):
        return (f"Traveling at {r['times_c']}× the speed of light for {r['hours']} hours "
                f"covers {r['distance_ly']:.6f} light years")
