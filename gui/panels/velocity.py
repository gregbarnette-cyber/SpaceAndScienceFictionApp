# gui/panels/velocity.py — Options 21 (ly/hr → ×c) and 22 (×c → ly/hr).
# Each option has its own standalone panel.

from PySide6.QtWidgets import QFormLayout, QPushButton, QLabel, QLineEdit
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


class _VelocityBase(ResultPanel):
    """Base for single-input velocity converter panels."""

    _prompt      = ""
    _placeholder = ""

    def build_inputs(self):
        form = QFormLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText(self._placeholder)
        self._input.returnPressed.connect(self._calculate)
        form.addRow(self._prompt, self._input)
        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        form.addRow("", self.run_btn)
        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._result_lbl = QLabel()
        self._result_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result_lbl.setWordWrap(True)
        self._layout.addWidget(self._result_lbl)
        self._layout.addStretch()

    def _calculate(self):
        raw = self._input.text().strip()
        try:
            val = float(raw)
        except ValueError:
            self._result_lbl.setText("Invalid input — please enter a number.")
            self._result_lbl.setStyleSheet("color: red;")
            return
        result = self._convert(val)
        self._result_lbl.setText(self._format(result))
        self._result_lbl.setStyleSheet("")

    def _convert(self, val):
        raise NotImplementedError

    def _format(self, result):
        raise NotImplementedError


class VelocityLyHrPanel(_VelocityBase):
    """LY/HR → ×c  (option 21)."""

    _prompt      = "Velocity (ly/hr):"
    _placeholder = "e.g. 0.001"

    def _convert(self, val):
        return core.calculators.compute_ly_hr_to_times_c(val)

    def _format(self, r):
        return f"{r['ly_hr']} ly/hr  =  {r['times_c']:.6f}× the speed of light"


class VelocityTimesCPanel(_VelocityBase):
    """×c → LY/HR  (option 22)."""

    _prompt      = "Velocity (×c):"
    _placeholder = "e.g. 8.77"

    def _convert(self, val):
        return core.calculators.compute_speed_of_light_to_ly_hr(val)

    def _format(self, r):
        return f"{r['times_c']}× the speed of light  =  {r['ly_hr']:.6f} ly/hr"
