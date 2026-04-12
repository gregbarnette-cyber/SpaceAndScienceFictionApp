# gui/panels/travel_time.py — Options 25 (time at ly/hr) and 26 (time at ×c).
# Each option has its own standalone panel.

from PySide6.QtWidgets import QFormLayout, QPushButton, QLineEdit

from gui.panels.base import ResultPanel
import core.calculators


class _TravelTimeBase(ResultPanel):
    """Base for two-input travel-time panels that render a single result row."""

    _fields  = []    # [(label, placeholder), ...]
    _headers = []

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
        pass   # results rendered dynamically via clear_results / add_result_widget

    def _calculate(self):
        vals = []
        for inp in self._inputs:
            try:
                v = float(inp.text().strip())
                if v <= 0:
                    raise ValueError
            except ValueError:
                self.clear_results()
                from PySide6.QtWidgets import QLabel
                lbl = QLabel("All values must be positive numbers.")
                lbl.setStyleSheet("color: red;")
                self.add_result_widget(lbl)
                return
            vals.append(v)

        try:
            result = self._compute(*vals)
        except Exception as e:
            self.clear_results()
            from PySide6.QtWidgets import QLabel
            lbl = QLabel(f"Error: {e}")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return

        self.clear_results()
        table = self.make_table(self._headers, [self._row(result)])
        table.setSortingEnabled(False)
        self.add_result_widget(table)

    def _compute(self, *vals):
        raise NotImplementedError

    def _row(self, result):
        raise NotImplementedError


class TravelTimeLyHrPanel(_TravelTimeBase):
    """Time to travel N light years at X ly/hr  (option 25)."""

    _fields = [
        ("Distance (light years):", "e.g. 4.37"),
        ("Velocity (ly/hr):",       "e.g. 0.001"),
    ]
    _headers = ["Distance (LYs)", "LY/HR", "X Times Speed of Light",
                "Travel Time (Hours)", "Travel Time"]

    def _compute(self, dist, vel):
        return core.calculators.compute_travel_time_ly_hr(dist, vel)

    def _row(self, r):
        return [f"{r['distance_ly']:.6f}", f"{r['ly_hr']:.6f}",
                f"{r['times_c']:.6f}", f"{r['total_hours']:.6f}", r["travel_time_str"]]


class TravelTimeTimesCPanel(_TravelTimeBase):
    """Time to travel N light years at X×c  (option 26)."""

    _fields = [
        ("Distance (light years):", "e.g. 4.37"),
        ("Velocity (×c):",          "e.g. 8.77"),
    ]
    _headers = ["Distance (LYs)", "X Times Speed of Light", "LY/HR",
                "Travel Time (Hours)", "Travel Time"]

    def _compute(self, dist, vel):
        return core.calculators.compute_travel_time_times_c(dist, vel)

    def _row(self, r):
        return [f"{r['distance_ly']:.6f}", f"{r['times_c']:.6f}",
                f"{r['ly_hr']:.6f}", f"{r['total_hours']:.6f}", r["travel_time_str"]]
