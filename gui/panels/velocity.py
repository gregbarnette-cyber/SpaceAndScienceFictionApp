# gui/panels/velocity.py — Options 21 (ly/hr → ×c) and 22 (×c → ly/hr).

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QFormLayout, QPushButton, QLabel
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


class _VelocityTab(QWidget):
    """One tab: a single input field, a Calculate button, and a result label."""

    def __init__(self, prompt: str, placeholder: str, convert_fn, result_fmt, parent_panel):
        super().__init__()
        self._convert_fn = convert_fn
        self._result_fmt = result_fmt
        self._panel = parent_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        from PySide6.QtWidgets import QLineEdit
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        form.addRow(prompt, self._input)
        layout.addLayout(form)

        self._btn = QPushButton("Calculate")
        self._btn.clicked.connect(self._calculate)
        layout.addWidget(self._btn)

        self._result = QLabel()
        self._result.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result.setWordWrap(True)
        layout.addWidget(self._result)
        layout.addStretch()

        self._input.returnPressed.connect(self._btn.click)

    def _calculate(self):
        raw = self._input.text().strip()
        try:
            val = float(raw)
        except ValueError:
            self._result.setText("Invalid input — please enter a number.")
            self._result.setStyleSheet("color: red;")
            return
        result = self._convert_fn(val)
        self._result.setText(self._result_fmt(result))
        self._result.setStyleSheet("")


class VelocityPanel(ResultPanel):
    """Velocity converter: two tabs for options 21 and 22."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        tabs = QTabWidget()
        self._layout.addWidget(tabs)

        # Option 21: ly/hr → ×c
        def fmt21(r):
            return f"{r['ly_hr']} ly/hr  =  {r['times_c']:.6f}× the speed of light"

        tab21 = _VelocityTab(
            "Velocity (ly/hr):",
            "e.g. 0.001",
            core.calculators.compute_ly_hr_to_times_c,
            fmt21,
            self,
        )
        tabs.addTab(tab21, "LY/HR → ×c  (opt 21)")

        # Option 22: ×c → ly/hr
        def fmt22(r):
            return f"{r['times_c']}× the speed of light  =  {r['ly_hr']:.6f} ly/hr"

        tab22 = _VelocityTab(
            "Velocity (×c):",
            "e.g. 8.77",
            core.calculators.compute_speed_of_light_to_ly_hr,
            fmt22,
            self,
        )
        tabs.addTab(tab22, "×c → LY/HR  (opt 22)")
