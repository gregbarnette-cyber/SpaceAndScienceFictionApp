# gui/panels/travel_time.py — Options 25 (time at ly/hr) and 26 (time at ×c).

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout, QPushButton, QLineEdit,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


class _TravelTimeTab(QWidget):
    """Two inputs, Calculate button, result table."""

    def __init__(self, fields: list, compute_fn, headers: list, row_fn):
        """
        fields:     [(label, placeholder), ...]
        compute_fn: callable(*floats) → result dict
        headers:    column header strings
        row_fn:     callable(result dict) → list of cell strings
        """
        super().__init__()
        self._compute_fn = compute_fn
        self._headers = headers
        self._row_fn = row_fn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._inputs = []
        for label, ph in fields:
            inp = QLineEdit()
            inp.setPlaceholderText(ph)
            form.addRow(label, inp)
            self._inputs.append(inp)
        layout.addLayout(form)

        self._btn = QPushButton("Calculate")
        self._btn.clicked.connect(self._calculate)
        layout.addWidget(self._btn)

        self._result_area = QVBoxLayout()
        layout.addLayout(self._result_area)
        layout.addStretch()

        for inp in self._inputs:
            inp.returnPressed.connect(self._btn.click)

        self._table_widget = None

    def _calculate(self):
        vals = []
        for inp in self._inputs:
            raw = inp.text().strip()
            try:
                v = float(raw)
            except ValueError:
                self._show_error("Invalid input — please enter a number in each field.")
                return
        # second pass after validation
        vals = []
        for inp in self._inputs:
            vals.append(float(inp.text().strip()))

        try:
            result = self._compute_fn(*vals)
        except Exception as e:
            self._show_error(f"Error: {e}")
            return

        if self._table_widget:
            self._result_area.removeWidget(self._table_widget)
            self._table_widget.deleteLater()
            self._table_widget = None

        from gui.panels.base import ResultPanel
        from PySide6.QtWidgets import QTableView
        from PySide6.QtGui import QStandardItemModel, QStandardItem

        row_data = self._row_fn(result)
        model = QStandardItemModel(1, len(self._headers))
        model.setHorizontalHeaderLabels(self._headers)
        for c, val in enumerate(row_data):
            item = QStandardItem(str(val))
            item.setEditable(False)
            model.setItem(0, c, item)

        view = QTableView()
        view.setModel(model)
        view.setSortingEnabled(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.resizeColumnsToContents()
        view.setMaximumHeight(80)

        self._table_widget = view
        self._result_area.addWidget(view)

    def _show_error(self, msg: str):
        from PySide6.QtWidgets import QLabel
        if self._table_widget:
            self._result_area.removeWidget(self._table_widget)
            self._table_widget.deleteLater()
            self._table_widget = None
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: red;")
        self._result_area.addWidget(lbl)
        self._table_widget = lbl


class TravelTimePanel(ResultPanel):
    """Travel time given a distance in light years: options 25 and 26."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        tabs = QTabWidget()
        self._layout.addWidget(tabs)

        # Option 25: distance + ly/hr
        tab25 = _TravelTimeTab(
            fields=[
                ("Distance (light years):", "e.g. 4.37"),
                ("Velocity (ly/hr):",       "e.g. 0.001"),
            ],
            compute_fn=lambda d, v: core.calculators.compute_travel_time_ly_hr(d, v),
            headers=[
                "Distance (LYs)", "LY/HR", "X Times Speed of Light",
                "Travel Time (Hours)", "Travel Time",
            ],
            row_fn=lambda r: [
                f"{r['distance_ly']:.6f}",
                f"{r['ly_hr']:.6f}",
                f"{r['times_c']:.6f}",
                f"{r['total_hours']:.6f}",
                r["travel_time_str"],
            ],
        )
        tabs.addTab(tab25, "At LY/HR  (opt 25)")

        # Option 26: distance + ×c
        tab26 = _TravelTimeTab(
            fields=[
                ("Distance (light years):", "e.g. 4.37"),
                ("Velocity (×c):",          "e.g. 8.77"),
            ],
            compute_fn=lambda d, v: core.calculators.compute_travel_time_times_c(d, v),
            headers=[
                "Distance (LYs)", "X Times Speed of Light", "LY/HR",
                "Travel Time (Hours)", "Travel Time",
            ],
            row_fn=lambda r: [
                f"{r['distance_ly']:.6f}",
                f"{r['times_c']:.6f}",
                f"{r['ly_hr']:.6f}",
                f"{r['total_hours']:.6f}",
                r["travel_time_str"],
            ],
        )
        tabs.addTab(tab26, "At ×c  (opt 26)")
