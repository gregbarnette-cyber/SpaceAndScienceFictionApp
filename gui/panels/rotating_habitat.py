# gui/panels/rotating_habitat.py — Options 37, 38, 39: Rotating habitat equations.
# Each option has its own independent panel class.

from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QPushButton, QLineEdit, QTableView, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from gui.panels.base import ResultPanel
import core.equations


class _HabitatForm(QVBoxLayout):
    """Reusable form + button + single-row result table, embedded inside a panel."""

    def __init__(self, fields: list, compute_fn, headers: list, row_fn, parent_widget):
        super().__init__()
        self._compute_fn = compute_fn
        self._headers = headers
        self._row_fn = row_fn

        form = QFormLayout()
        self._inputs = []
        for label, ph in fields:
            inp = QLineEdit(parent_widget)
            inp.setPlaceholderText(ph)
            form.addRow(label, inp)
            self._inputs.append(inp)
        self.addLayout(form)

        btn = QPushButton("Calculate", parent_widget)
        btn.clicked.connect(self._calculate)
        self.addWidget(btn)

        self._err = QLabel(parent_widget)
        self._err.setStyleSheet("color: red;")
        self.addWidget(self._err)
        self._err.hide()

        self._view_area = QVBoxLayout()
        self.addLayout(self._view_area)
        self.addStretch()
        self._view = None

        for inp in self._inputs:
            inp.returnPressed.connect(btn.click)

    def _calculate(self):
        self._err.hide()
        vals = []
        for inp in self._inputs:
            try:
                vals.append(float(inp.text().strip()))
            except ValueError:
                self._err.setText("Invalid input — please enter a number in each field.")
                self._err.show()
                return
        try:
            result = self._compute_fn(*vals)
        except Exception as e:
            self._err.setText(f"Error: {e}")
            self._err.show()
            return

        if self._view:
            self._view_area.removeWidget(self._view)
            self._view.deleteLater()

        row_data = self._row_fn(result)
        model = QStandardItemModel(1, len(self._headers))
        model.setHorizontalHeaderLabels(self._headers)
        for c, val in enumerate(row_data):
            item = QStandardItem(str(val))
            item.setEditable(False)
            model.setItem(0, c, item)

        self._view = QTableView()
        self._view.setModel(model)
        self._view.setSortingEnabled(False)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.resizeColumnsToContents()
        self._view.setMaximumHeight(80)
        self._view_area.addWidget(self._view)


class GravityAccelPanel(ResultPanel):
    """Option 37 — Centrifugal Artificial Gravity Acceleration at Point X (m/s²)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_HabitatForm(
            fields=[
                ("Rotation Rate (rpm):",        "e.g. 2.0"),
                ("Distance from Center (m):",   "e.g. 100"),
            ],
            compute_fn=core.equations.compute_centrifugal_gravity_acceleration,
            headers=["Rotation Rate (rpm)", "Distance from Center (m)", "Centrifugal Gravity (m/s²)"],
            row_fn=lambda r: [
                f"{r['rpm']:.4f}",
                f"{r['radius_m']:.4f}",
                f"{r['accel_ms2']:.2f}",
            ],
            parent_widget=self,
        ))


class GravityDistancePanel(ResultPanel):
    """Option 38 — Distance from Point X to the Center of Rotation (m)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_HabitatForm(
            fields=[
                ("Rotation Rate (rpm):",            "e.g. 2.0"),
                ("Centrifugal Gravity (m/s²):",     "e.g. 9.81"),
            ],
            compute_fn=core.equations.compute_centrifugal_gravity_distance,
            headers=["Rotation Rate (rpm)", "Centrifugal Gravity (m/s²)", "Distance from Center (m)"],
            row_fn=lambda r: [
                f"{r['rpm']:.4f}",
                f"{r['accel_ms2']:.4f}",
                f"{r['radius_m']:.2f}",
            ],
            parent_widget=self,
        ))


class GravityRpmPanel(ResultPanel):
    """Option 39 — Rotation Rate at Point X (rpm)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_HabitatForm(
            fields=[
                ("Centrifugal Gravity (m/s²):",     "e.g. 9.81"),
                ("Distance from Center (m):",       "e.g. 100"),
            ],
            compute_fn=core.equations.compute_centrifugal_gravity_rpm,
            headers=["Centrifugal Gravity (m/s²)", "Distance from Center (m)", "Rotation Rate (rpm)"],
            row_fn=lambda r: [
                f"{r['accel_ms2']:.4f}",
                f"{r['radius_m']:.4f}",
                f"{r['rpm']:.2f}",
            ],
            parent_widget=self,
        ))
