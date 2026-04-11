# gui/panels/habitable_zone_calc.py — Options 40 (HZ Calculator) and 41 (HZ + SMA).
# Each option has its own independent panel class.

from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QPushButton, QLineEdit, QTableView, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.equations


def _make_hz_table(zones: list) -> QTableView:
    """Build a QTableView for a list of zone dicts (zone_name, au, lm)."""
    headers = ["Zone", "AU", "LM"]
    model = QStandardItemModel(len(zones), len(headers))
    model.setHorizontalHeaderLabels(headers)
    for r, z in enumerate(zones):
        model.setItem(r, 0, QStandardItem(z["zone_name"]))
        model.setItem(r, 1, QStandardItem(f"{z['au']:.3f}"))
        model.setItem(r, 2, QStandardItem(f"{z['lm']:.3f} LM"))
    view = QTableView()
    view.setModel(model)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.resizeColumnsToContents()
    return view


class HabZonePanel(ResultPanel):
    """Option 40 — Habitable Zone Calculator (temperature + luminosity)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        form = QFormLayout()
        self._teff = QLineEdit(self)
        self._teff.setPlaceholderText("e.g. 5778")
        form.addRow("Star Temperature (K):", self._teff)

        self._lum = QLineEdit(self)
        self._lum.setPlaceholderText("e.g. 1.0")
        form.addRow("Star Luminosity (Lsun):", self._lum)
        self._layout.addLayout(form)

        btn = QPushButton("Calculate", self)
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)

        self._err = QLabel(self)
        self._err.setStyleSheet("color: red;")
        self._layout.addWidget(self._err)
        self._err.hide()

        self._result_area = QVBoxLayout()
        self._layout.addLayout(self._result_area)
        self._layout.addStretch()
        self._table = None

        self._teff.returnPressed.connect(btn.click)
        self._lum.returnPressed.connect(btn.click)

    def _calculate(self):
        self._err.hide()
        if self._table:
            self._result_area.removeWidget(self._table)
            self._table.deleteLater()
            self._table = None
        try:
            teff = float(self._teff.text().strip())
            lum  = float(self._lum.text().strip())
        except ValueError:
            self._err.setText("Invalid input — please enter numbers.")
            self._err.show()
            return
        zones = core.equations.compute_habitable_zone(teff, lum)
        self._table = _make_hz_table(zones)
        self._result_area.addWidget(self._table)


class HabZoneSmaPanel(ResultPanel):
    """Option 41 — Habitable Zone Calculator with SMA (shows Seff + HZ verdict)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        form = QFormLayout()
        self._teff = QLineEdit(self)
        self._teff.setPlaceholderText("e.g. 5778")
        form.addRow("Star Temperature (K):", self._teff)

        self._lum = QLineEdit(self)
        self._lum.setPlaceholderText("e.g. 1.0")
        form.addRow("Star Luminosity (Lsun):", self._lum)

        self._sma = QLineEdit(self)
        self._sma.setPlaceholderText("e.g. 1.0")
        form.addRow("Object's Semi-Major Axis (AU):", self._sma)
        self._layout.addLayout(form)

        btn = QPushButton("Calculate", self)
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)

        self._err = QLabel(self)
        self._err.setStyleSheet("color: red;")
        self._layout.addWidget(self._err)
        self._err.hide()

        self._seff_label = QLabel(self)
        self._layout.addWidget(self._seff_label)
        self._seff_label.hide()

        self._result_area = QVBoxLayout()
        self._layout.addLayout(self._result_area)

        self._verdict_label = QLabel(self)
        self._verdict_label.setWordWrap(True)
        self._layout.addWidget(self._verdict_label)
        self._verdict_label.hide()

        self._layout.addStretch()
        self._table = None

        for w in (self._teff, self._lum, self._sma):
            w.returnPressed.connect(btn.click)

    def _calculate(self):
        self._err.hide()
        if self._table:
            self._result_area.removeWidget(self._table)
            self._table.deleteLater()
            self._table = None
        self._seff_label.hide()
        self._verdict_label.hide()

        try:
            teff = float(self._teff.text().strip())
            lum  = float(self._lum.text().strip())
            sma  = float(self._sma.text().strip())
        except ValueError:
            self._err.setText("Invalid input — please enter numbers.")
            self._err.show()
            return

        result = core.equations.compute_habitable_zone_sma(teff, lum, sma)

        self._seff_label.setText(f"Object's Seff: {result['planet_seff']:.8f}")
        self._seff_label.show()

        zones = result["zones"]
        headers = ["Zone", "AU", "LM", "Seff"]
        model = QStandardItemModel(len(zones), 4)
        model.setHorizontalHeaderLabels(headers)
        for r, z in enumerate(zones):
            model.setItem(r, 0, QStandardItem(z["zone_name"]))
            model.setItem(r, 1, QStandardItem(f"{z['au']:.3f}"))
            model.setItem(r, 2, QStandardItem(f"{z['lm']:.3f} LM"))
            model.setItem(r, 3, QStandardItem(f"{z['seff']:.8f}"))
        view = QTableView()
        view.setModel(model)
        view.setSortingEnabled(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.resizeColumnsToContents()
        self._table = view
        self._result_area.addWidget(view)

        self._verdict_label.setText(result["verdict"])
        self._verdict_label.show()
