# gui/panels/worldbuilding.py — Phase H: Worldbuilding Calculators (GUI-only).
#
# Five pure-math panels (no network, no DB) following the LuminosityPanel pattern:
#   RocheLimitPanel, TidalLockingPanel, HillSpherePanel, BinaryOrbitPanel,
#   AtmosphereRetentionPanel.

from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QGroupBox, QPushButton,
    QLineEdit, QTableView, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor

from gui.panels.base import ResultPanel
import core.equations


_STATUS_COLORS = {
    "Retained": "#2e8b57",
    "Escaping slowly": "#b8860b",
    "Lost rapidly": "#b03030",
}


def _item(text, color=None):
    it = QStandardItem(text)
    it.setEditable(False)
    if color:
        it.setForeground(QBrush(QColor(color)))
    return it


def _make_table(headers, rows, max_height=None):
    """Build a non-editable QTableView from headers and a list of row-cell lists.

    Each cell is either a string or a (text, color) tuple.
    """
    model = QStandardItemModel(len(rows), len(headers))
    model.setHorizontalHeaderLabels(headers)
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if isinstance(cell, tuple):
                model.setItem(r, c, _item(cell[0], cell[1]))
            else:
                model.setItem(r, c, _item(cell))
    view = QTableView()
    view.setModel(model)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.resizeColumnsToContents()
    if max_height is not None:
        view.setMaximumHeight(max_height)
    return view


class _WorldbuildingPanel(ResultPanel):
    """Shared scaffold: a QFormLayout of inputs + Calculate button + error label
    + a result container that the subclass repopulates on each calculation."""

    def _add_form(self, rows):
        """rows: list of (label, QLineEdit). Returns nothing; stores the form."""
        form = QFormLayout()
        for label, widget in rows:
            form.addRow(label, widget)
        self._layout.addLayout(form)
        return form

    def _add_calculate_button(self, line_edits):
        btn = QPushButton("Calculate")
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)
        for le in line_edits:
            le.returnPressed.connect(btn.click)

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._layout.addWidget(self._err)
        self._err.hide()

        self._result_container = QVBoxLayout()
        self._layout.addLayout(self._result_container)
        self._layout.addStretch()

    def _clear_results(self):
        while self._result_container.count():
            item = self._result_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _show_error(self, msg):
        self._err.setText(msg)
        self._err.show()

    def _read_float(self, widget, label, *, required=True, allow_blank_default=None):
        """Read a float from a QLineEdit. Returns (value, ok). On blank with a
        default, returns the default. Raises ValueError-style handling via ok flag."""
        text = widget.text().strip()
        if not text:
            if required and allow_blank_default is None:
                raise _InputError(f"{label} is required.")
            return allow_blank_default
        return float(text)


class _InputError(Exception):
    pass


# ── H1: Roche Limit ──────────────────────────────────────────────────────────

class RocheLimitPanel(_WorldbuildingPanel):
    """Rigid-body and fluid Roche limits for a satellite orbiting a primary."""

    def build_inputs(self):
        self._input_count = 2

        self._mass = QLineEdit(); self._mass.setPlaceholderText("e.g. 1.0")
        self._sat_density = QLineEdit(); self._sat_density.setPlaceholderText("e.g. 3.34")
        self._radius = QLineEdit(); self._radius.setPlaceholderText("optional")
        self._add_form([
            ("Primary Mass (M⊕):", self._mass),
            ("Satellite Density (g/cm³):", self._sat_density),
            ("Primary Radius (R⊕) — optional, estimated from mass if blank:", self._radius),
        ])
        self._add_calculate_button([self._mass, self._sat_density, self._radius])

    def _calculate(self):
        self._err.hide()
        self._clear_results()
        try:
            mass = self._read_float(self._mass, "Primary Mass")
            density = self._read_float(self._sat_density, "Satellite Density")
            radius = self._read_float(self._radius, "Primary Radius",
                                      required=False, allow_blank_default=None)
        except _InputError as ex:
            self._show_error(str(ex)); return
        except ValueError:
            self._show_error("Invalid input — please enter a number in each field."); return

        result = core.equations.compute_roche_limit(mass, density, radius)
        if "error" in result:
            self._show_error(result["error"]); return

        headers = ["Primary Mass (M⊕)", "Primary Radius (km)", "Primary Density (g/cm³)",
                   "Satellite Density (g/cm³)", "Rigid Roche (km)", "Rigid Roche (AU)",
                   "Fluid Roche (km)", "Fluid Roche (AU)"]
        row = [
            f"{result['primary_mass_earth']:.4f}",
            f"{result['primary_radius_km']:.4f}",
            f"{result['primary_density_gcc']:.4f}",
            f"{result['satellite_density_gcc']:.4f}",
            f"{result['rigid_km']:.4f}",
            f"{result['rigid_au']:.4f}",
            f"{result['fluid_km']:.4f}",
            f"{result['fluid_au']:.4f}",
        ]
        self._result_container.addWidget(_make_table(headers, [row], max_height=80))


# ── H2: Tidal Locking Timescale ──────────────────────────────────────────────

class TidalLockingPanel(_WorldbuildingPanel):
    """Estimate the tidal-locking timescale of a satellite (MacDonald 1964)."""

    def build_inputs(self):
        self._input_count = 2

        self._pri_mass = QLineEdit(); self._pri_mass.setPlaceholderText("e.g. 1.0")
        self._sat_mass = QLineEdit(); self._sat_mass.setPlaceholderText("e.g. 0.0123")
        self._sma = QLineEdit(); self._sma.setPlaceholderText("e.g. 384400")
        self._rotation = QLineEdit(); self._rotation.setPlaceholderText("e.g. 24")
        self._add_form([
            ("Primary Mass (M⊕):", self._pri_mass),
            ("Satellite Mass (M⊕):", self._sat_mass),
            ("Semi-Major Axis (km):", self._sma),
            ("Initial Rotation (hours):", self._rotation),
        ])

        adv = QGroupBox("Advanced Parameters")
        adv_form = QFormLayout()
        self._rigidity = QLineEdit("3e10")
        self._tidal_q = QLineEdit("100")
        adv_form.addRow("Rigidity (Pa):", self._rigidity)
        adv_form.addRow("Tidal Q:", self._tidal_q)
        adv.setLayout(adv_form)
        self._layout.addWidget(adv)

        self._add_calculate_button(
            [self._pri_mass, self._sat_mass, self._sma, self._rotation,
             self._rigidity, self._tidal_q])

    def _calculate(self):
        self._err.hide()
        self._clear_results()
        try:
            pm = self._read_float(self._pri_mass, "Primary Mass")
            sm = self._read_float(self._sat_mass, "Satellite Mass")
            sma = self._read_float(self._sma, "Semi-Major Axis")
            rot = self._read_float(self._rotation, "Initial Rotation")
            rigidity = self._read_float(self._rigidity, "Rigidity",
                                        required=False, allow_blank_default=3e10)
            tq = self._read_float(self._tidal_q, "Tidal Q",
                                  required=False, allow_blank_default=100.0)
        except _InputError as ex:
            self._show_error(str(ex)); return
        except ValueError:
            self._show_error("Invalid input — please enter a number in each field."); return

        result = core.equations.compute_tidal_locking_time(pm, sm, sma, rot, rigidity, tq)
        if "error" in result:
            self._show_error(result["error"]); return

        headers = ["Primary Mass (M⊕)", "Satellite Mass (M⊕)", "SMA (km)",
                   "Init. Rotation (hr)", "Rigidity (Pa)", "Tidal Q",
                   "Sat. Radius (km)", "Lock Time (yr)", "Lock Time (Gyr)"]
        row = [
            f"{result['primary_mass_earth']:.4f}",
            f"{result['satellite_mass_earth']:.4f}",
            f"{result['sma_km']:.4f}",
            f"{result['initial_rotation_hours']:.4f}",
            f"{result['rigidity_pa']:.3e}",
            f"{result['tidal_q']:.0f}",
            f"{result['satellite_radius_km']:.4f}",
            f"{result['lock_time_years']:.3e}",
            f"{result['lock_time_gyr']:.4f}",
        ]
        self._result_container.addWidget(_make_table(headers, [row], max_height=80))


# ── H3: Hill Sphere ──────────────────────────────────────────────────────────

class HillSpherePanel(_WorldbuildingPanel):
    """Gravitational sphere of influence of a planet within a star system."""

    def build_inputs(self):
        self._input_count = 2

        self._star_mass = QLineEdit(); self._star_mass.setPlaceholderText("e.g. 1.0")
        self._planet_mass = QLineEdit(); self._planet_mass.setPlaceholderText("e.g. 1.0")
        self._sma = QLineEdit(); self._sma.setPlaceholderText("e.g. 1.0")
        self._ecc = QLineEdit(); self._ecc.setPlaceholderText("0 if circular")
        self._add_form([
            ("Star Mass (M☉):", self._star_mass),
            ("Planet Mass (M⊕):", self._planet_mass),
            ("Semi-Major Axis (AU):", self._sma),
            ("Eccentricity:", self._ecc),
        ])
        self._add_calculate_button(
            [self._star_mass, self._planet_mass, self._sma, self._ecc])

    def _calculate(self):
        self._err.hide()
        self._clear_results()
        try:
            star = self._read_float(self._star_mass, "Star Mass")
            planet = self._read_float(self._planet_mass, "Planet Mass")
            sma = self._read_float(self._sma, "Semi-Major Axis")
            ecc = self._read_float(self._ecc, "Eccentricity",
                                   required=False, allow_blank_default=0.0)
        except _InputError as ex:
            self._show_error(str(ex)); return
        except ValueError:
            self._show_error("Invalid input — please enter a number in each field."); return

        result = core.equations.compute_hill_sphere(star, planet, sma, ecc)
        if "error" in result:
            self._show_error(result["error"]); return

        headers = ["Star Mass (M☉)", "Planet Mass (M⊕)", "SMA (AU)", "Eccentricity",
                   "Hill Radius (km)", "Hill Radius (AU)",
                   "Stable Orbit Limit (km)", "Stable Orbit Limit (AU)"]
        row = [
            f"{result['star_mass_solar']:.4f}",
            f"{result['planet_mass_earth']:.4f}",
            f"{result['sma_au']:.4f}",
            f"{result['eccentricity']:.4f}",
            f"{result['hill_radius_km']:.4f}",
            f"{result['hill_radius_au']:.4f}",
            f"{result['stable_orbit_limit_km']:.4f}",
            f"{result['stable_orbit_limit_au']:.4f}",
        ]
        self._result_container.addWidget(_make_table(headers, [row], max_height=80))


# ── H4: Binary Orbit Stability ───────────────────────────────────────────────

class BinaryOrbitPanel(_WorldbuildingPanel):
    """Dynamical stability of a planet's orbit in a binary (Holman & Wiegert 1999)."""

    def build_inputs(self):
        self._input_count = 2

        self._mass1 = QLineEdit(); self._mass1.setPlaceholderText("e.g. 1.0")
        self._mass2 = QLineEdit(); self._mass2.setPlaceholderText("e.g. 0.5")
        self._binary_sma = QLineEdit(); self._binary_sma.setPlaceholderText("e.g. 20")
        self._test_sma = QLineEdit(); self._test_sma.setPlaceholderText("e.g. 5")
        self._ecc = QLineEdit(); self._ecc.setPlaceholderText("0 if circular")
        self._add_form([
            ("Star 1 Mass (M☉):", self._mass1),
            ("Star 2 Mass (M☉):", self._mass2),
            ("Binary Separation SMA (AU):", self._binary_sma),
            ("Planet Test SMA (AU):", self._test_sma),
            ("Binary Eccentricity:", self._ecc),
        ])
        self._add_calculate_button(
            [self._mass1, self._mass2, self._binary_sma, self._test_sma, self._ecc])

    def _calculate(self):
        self._err.hide()
        self._clear_results()
        try:
            m1 = self._read_float(self._mass1, "Star 1 Mass")
            m2 = self._read_float(self._mass2, "Star 2 Mass")
            bsma = self._read_float(self._binary_sma, "Binary Separation SMA")
            tsma = self._read_float(self._test_sma, "Planet Test SMA")
            ecc = self._read_float(self._ecc, "Binary Eccentricity",
                                   required=False, allow_blank_default=0.0)
        except _InputError as ex:
            self._show_error(str(ex)); return
        except ValueError:
            self._show_error("Invalid input — please enter a number in each field."); return

        result = core.equations.compute_binary_orbit_stability(m1, m2, bsma, tsma, ecc)
        if "error" in result:
            self._show_error(result["error"]); return

        verdict = QLabel("Stable" if result["is_stable"] else "Unstable")
        verdict.setStyleSheet(
            "color: #2e8b57; font-weight: bold;" if result["is_stable"]
            else "color: #b03030; font-weight: bold;")
        self._result_container.addWidget(verdict)

        headers = ["Mass 1 (M☉)", "Mass 2 (M☉)", "Mass Ratio (μ)", "Binary SMA (AU)",
                   "Eccentricity", "S-Type Critical SMA (AU)", "P-Type Critical SMA (AU)",
                   "Test SMA (AU)", "Orbit Type", "Stable?"]
        row = [
            f"{result['mass1_solar']:.4f}",
            f"{result['mass2_solar']:.4f}",
            f"{result['mass_ratio']:.4f}",
            f"{result['binary_sma_au']:.4f}",
            f"{result['eccentricity']:.4f}",
            f"{result['stype_critical_sma_au']:.4f}",
            f"{result['ptype_critical_sma_au']:.4f}",
            f"{result['test_sma_au']:.4f}",
            result["orbit_type"],
            "Yes" if result["is_stable"] else "No",
        ]
        self._result_container.addWidget(_make_table(headers, [row], max_height=80))

        desc = QLabel(result["stable_region_description"])
        desc.setWordWrap(True)
        self._result_container.addWidget(desc)


# ── H5: Atmosphere Retention ─────────────────────────────────────────────────

class AtmosphereRetentionPanel(_WorldbuildingPanel):
    """Which atmospheric gases a planet retains against Jeans escape."""

    def build_inputs(self):
        self._input_count = 2

        self._mass = QLineEdit(); self._mass.setPlaceholderText("e.g. 1.0")
        self._radius = QLineEdit(); self._radius.setPlaceholderText("e.g. 1.0")
        self._temp = QLineEdit(); self._temp.setPlaceholderText("e.g. 255")
        self._add_form([
            ("Planet Mass (M⊕):", self._mass),
            ("Planet Radius (R⊕):", self._radius),
            ("Equilibrium Temperature (K):", self._temp),
        ])
        self._add_calculate_button([self._mass, self._radius, self._temp])

    def _calculate(self):
        self._err.hide()
        self._clear_results()
        try:
            mass = self._read_float(self._mass, "Planet Mass")
            radius = self._read_float(self._radius, "Planet Radius")
            temp = self._read_float(self._temp, "Equilibrium Temperature")
        except _InputError as ex:
            self._show_error(str(ex)); return
        except ValueError:
            self._show_error("Invalid input — please enter a number in each field."); return

        result = core.equations.compute_atmosphere_retention(mass, radius, temp)
        if "error" in result:
            self._show_error(result["error"]); return

        self._result_container.addWidget(
            QLabel(f"Escape Velocity: {result['v_escape_kms']:.2f} km/s"))

        headers = ["Gas", "Mol. Mass (amu)", "Jeans λ", "Escape Vel (km/s)",
                   "Thermal Vel (km/s)", "Status"]
        rows = []
        for g in result["gases"]:
            color = _STATUS_COLORS.get(g["status"])
            rows.append([
                g["gas"],
                f"{g['mol_mass_amu']}",
                f"{g['lambda']:.2f}",
                f"{result['v_escape_kms']:.2f}",
                f"{g['v_thermal_kms']:.2f}",
                (g["status"], color),
            ])
        self._result_container.addWidget(_make_table(headers, rows, max_height=260))
