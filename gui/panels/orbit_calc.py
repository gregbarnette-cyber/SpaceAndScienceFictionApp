# gui/panels/orbit_calc.py — Options 34, 35, 36: Planetary orbit calculators.
# Each option has its own independent panel class.

from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QPushButton, QLineEdit, QTableView, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from gui.panels.base import ResultPanel
import core.equations


class _CalcForm(QVBoxLayout):
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


class OrbitPeriastronPanel(ResultPanel):
    """Option 34 — Planetary Orbit Periastron & Apastron Distance Calculator."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_CalcForm(
            fields=[
                ("Semi-Major Axis (AU):", "e.g. 1.0"),
                ("Eccentricity (0–<1):",  "e.g. 0.017"),
            ],
            compute_fn=core.equations.compute_orbit_periastron_apastron,
            headers=["Periastron (AU)", "Semi-Major Axis (AU)", "Apastron (AU)",
                     "Eccentricity", "Eccentricity (AU)"],
            row_fn=lambda r: [
                f"{r['periastron']:.6f}",
                f"{r['sma']:.6f}",
                f"{r['apastron']:.6f}",
                f"{r['ecc']:.6f}",
                f"{r['ecc_au']:.6f}",
            ],
            parent_widget=self,
        ))


class MoonDistance24Panel(ResultPanel):
    """Option 35 — Orbital Distance of an Earth-sized Moon with a 24-hour day."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_CalcForm(
            fields=[
                ("Planetary Mass (Earth Masses):", "e.g. 1.0"),
            ],
            compute_fn=lambda m: core.equations.compute_moon_orbital_distance(m, 24.0),
            headers=["Planetary Mass (Earth Masses)", "Day Length (Hours)", "Orbital Distance (km)"],
            row_fn=lambda r: [
                f"{r['planet_mass_earth']:.4f}",
                "24.0000",
                f"{r['orbital_distance_km']:.4f}",
            ],
            parent_widget=self,
        ))


class MoonDistanceXPanel(ResultPanel):
    """Option 36 — Orbital Distance of an Earth-sized Moon with a user-specified day length."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        self._layout.addLayout(_CalcForm(
            fields=[
                ("Planetary Mass (Earth Masses):", "e.g. 1.0"),
                ("Day Length (Hours):",            "e.g. 24"),
            ],
            compute_fn=core.equations.compute_moon_orbital_distance,
            headers=["Planetary Mass (Earth Masses)", "Day Length (Hours)", "Orbital Distance (km)"],
            row_fn=lambda r: [
                f"{r['planet_mass_earth']:.4f}",
                f"{r['day_hours']:.4f}",
                f"{r['orbital_distance_km']:.4f}",
            ],
            parent_widget=self,
        ))
