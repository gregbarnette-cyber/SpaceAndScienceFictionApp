# gui/panels/distance.py — Options 23 (distance at ly/hr) and 24 (distance at ×c).

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout, QPushButton, QLabel, QLineEdit,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


class _DistanceTab(QWidget):
    """One tab: two input fields, a Calculate button, and a result label."""

    def __init__(self, fields: list, convert_fn, result_fmt):
        """
        fields: list of (label_text, placeholder) tuples
        convert_fn: callable(*field_values_as_floats) → dict
        result_fmt: callable(dict) → str
        """
        super().__init__()
        self._fields = fields
        self._convert_fn = convert_fn
        self._result_fmt = result_fmt

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._inputs = []
        for label, placeholder in fields:
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            form.addRow(label, inp)
            self._inputs.append(inp)
        layout.addLayout(form)

        self._btn = QPushButton("Calculate")
        self._btn.clicked.connect(self._calculate)
        layout.addWidget(self._btn)

        self._result = QLabel()
        self._result.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result.setWordWrap(True)
        layout.addWidget(self._result)
        layout.addStretch()

        for inp in self._inputs:
            inp.returnPressed.connect(self._btn.click)

    def _calculate(self):
        vals = []
        for inp in self._inputs:
            raw = inp.text().strip()
            try:
                vals.append(float(raw))
            except ValueError:
                self._result.setText("Invalid input — please enter a number in each field.")
                self._result.setStyleSheet("color: red;")
                return
        result = self._convert_fn(*vals)
        self._result.setText(self._result_fmt(result))
        self._result.setStyleSheet("")


class DistancePanel(ResultPanel):
    """Distance traveled: two tabs for options 23 and 24."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        tabs = QTabWidget()
        self._layout.addWidget(tabs)

        # Option 23: ly/hr + hours
        def fmt23(r):
            return (
                f"Traveling at {r['ly_hr']} ly/hr for {r['hours']} hours "
                f"covers {r['distance_ly']:.6f} light years"
            )

        tab23 = _DistanceTab(
            fields=[
                ("Travel time (hours):", "e.g. 100"),
                ("Velocity (ly/hr):",    "e.g. 0.001"),
            ],
            convert_fn=lambda h, v: core.calculators.compute_distance_traveled_ly_hr(v, h),
            result_fmt=fmt23,
        )
        tabs.addTab(tab23, "At LY/HR  (opt 23)")

        # Option 24: ×c + hours
        def fmt24(r):
            return (
                f"Traveling at {r['times_c']}× the speed of light for {r['hours']} hours "
                f"covers {r['distance_ly']:.6f} light years"
            )

        tab24 = _DistanceTab(
            fields=[
                ("Travel time (hours):", "e.g. 100"),
                ("Velocity (×c):",       "e.g. 8.77"),
            ],
            convert_fn=lambda h, v: core.calculators.compute_distance_traveled_times_c(v, h),
            result_fmt=fmt24,
        )
        tabs.addTab(tab24, "At ×c  (opt 24)")
