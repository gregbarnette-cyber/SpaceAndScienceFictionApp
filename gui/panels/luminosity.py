# gui/panels/luminosity.py — Option 42: Star Luminosity Calculator.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton,
    QLineEdit, QTableView, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from gui.panels.base import ResultPanel
import core.equations


class LuminosityPanel(ResultPanel):
    """Star Luminosity Calculator (option 42): radius + temperature → luminosity."""

    def build_inputs(self):
        self._input_count = 2   # form + button

        form = QFormLayout()
        self._radius = QLineEdit()
        self._radius.setPlaceholderText("e.g. 1.0")
        form.addRow("Star Radius (R☉):", self._radius)

        self._temp = QLineEdit()
        self._temp.setPlaceholderText("e.g. 5778")
        form.addRow("Star Temperature (K):", self._temp)
        self._layout.addLayout(form)

        btn = QPushButton("Calculate")
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)

        self._radius.returnPressed.connect(btn.click)
        self._temp.returnPressed.connect(btn.click)

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._layout.addWidget(self._err)
        self._err.hide()

        self._view_container = QVBoxLayout()
        self._layout.addLayout(self._view_container)
        self._layout.addStretch()
        self._table = None

    def _calculate(self):
        self._err.hide()
        try:
            radius = float(self._radius.text().strip())
            temp   = float(self._temp.text().strip())
        except ValueError:
            self._err.setText("Invalid input — please enter a number in each field.")
            self._err.show()
            return

        result = core.equations.compute_star_luminosity(radius, temp)

        if self._table:
            self._view_container.removeWidget(self._table)
            self._table.deleteLater()

        headers = ["Radius (R☉)", "Temperature (K)", "Luminosity (Lsun)"]
        model = QStandardItemModel(1, 3)
        model.setHorizontalHeaderLabels(headers)
        model.setItem(0, 0, QStandardItem(f"{result['radius']:.4f}"))
        model.setItem(0, 1, QStandardItem(f"{result['temp']:.4f}"))
        model.setItem(0, 2, QStandardItem(f"{result['luminosity']:.6f}"))
        for c in range(3):
            model.item(0, c).setEditable(False)

        self._table = QTableView()
        self._table.setModel(model)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.resizeColumnsToContents()
        self._table.setMaximumHeight(80)
        self._view_container.addWidget(self._table)
