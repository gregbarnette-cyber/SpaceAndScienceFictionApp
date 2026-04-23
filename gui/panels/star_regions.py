# gui/panels/star_regions.py — Options 8, 9, 10: Star System Regions.
#
# Three independent panels:
#   StarRegionsAutoPanel       — option 8:  star name only; sunlight=1.0, albedo=0.3 hardcoded
#   StarRegionsSemiManualPanel — option 9:  star name + user-supplied sunlight/albedo
#   StarRegionsManualPanel     — option 10: all six inputs manually; no SIMBAD

import math

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QTableView,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from gui.panels.base import ResultPanel
import core.databases
import core.regions
import core.viz
from core.equations import _kopparapu_seff
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_system_regions_canvas,
)


# ── Single-step background functions (SIMBAD + regions in one thread) ─────────

def _compute_auto_regions(name: str) -> dict:
    simbad = core.databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    return core.regions.compute_star_system_regions_from_simbad(simbad)


def _compute_semi_manual_regions(name: str, sunlight: float, albedo: float) -> dict:
    simbad = core.databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    return core.regions.compute_star_system_regions_from_simbad(simbad, sunlight, albedo)


# ── AU formatting helpers ──────────────────────────────────────────────────────

def _au_lm4(val: float) -> str:
    return f"{val:.4f} ({val * 8.3167:.3f} LM)"


def _au_lm3(val: float) -> str:
    return f"{val:.3f} ({val * 8.3167:.3f} LM)"


# ── Shared table builder ───────────────────────────────────────────────────────

def _tbl(headers, rows) -> QTableView:
    model = QStandardItemModel(len(rows), len(headers))
    model.setHorizontalHeaderLabels(headers)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = QStandardItem(str(val) if val is not None else "N/A")
            item.setEditable(False)
            model.setItem(r, c, item)
    view = QTableView()
    view.setModel(model)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.resizeColumnsToContents()
    return view


# ── Shared results renderer ───────────────────────────────────────────────────

def _build_region_tabs(d: dict) -> QTabWidget:
    """Build a QTabWidget of result tables from a compute_star_system_regions() result dict."""
    tabs = QTabWidget()

    tabs.addTab(
        _tbl(
            ["Property", "Value"],
            [
                ["Apparent Magnitude",            f"{d['vmag']:.3f}"],
                ["Absolute Magnitude",            f"{d['absMagnitude']:.3f}"],
                ["Bolometric Absolute Magnitude", f"{d['bcAbsMagnitude']:.3f}"],
                ["Bolometric Luminosity",         f"{d['bcLuminosity']:.6f}"],
                ["Luminosity from Mass",          f"{d['luminosityFromMass']:.5f}"],
                ["BC",                            f"{d['boloLum']:.1f}"],
                ["Star Temperature K",            f"{int(d['temp'])}"],
            ],
        ),
        "Star System Properties",
    )

    tabs.addTab(
        _tbl(
            ["Stellar Mass", "Stellar Radius", "Stellar Diameter (Sol)",
             "Stellar Diameter (KM)", "Main Sequence Life Span"],
            [[
                f"{d['stellarMass']:.4f}",
                f"{d['stellarRadius']:.5f}",
                f"{d['stellarDiameterSol']:.4f}",
                f"{d['stellarDiameterKM']:.5e}",
                f"{d['mainSeqLifeSpan']:.5e}",
            ]],
        ),
        "Stellar Properties",
    )

    tabs.addTab(
        _tbl(
            ["Parallax", "Trig Parallax", "Parsecs", "Light Years"],
            [[
                f"{d['plx']:.2f}",
                f"{d['trigParallax']:.4f}",
                f"{d['parsecs']:.4f}",
                f"{d['lightYears']:.4f}",
            ]],
        ),
        "Star Distance",
    )

    tabs.addTab(
        _tbl(
            ["Distance (AU)", "Distance (KM)", "Year",
             "Temp (K)", "Temp (C)", "Temp (F)", "Size of Sun"],
            [[
                f"{d['distAU']:.4f}",
                f"{d['distKM']:.5e}",
                f"{d['planetaryYear']:.4f}",
                f"{d['planetaryTemperature']:.2f}",
                f"{d['planetaryTemperatureC']:.2f}",
                f"{d['planetaryTemperatureF']:.2f}",
                d["sizeOfSun"],
            ]],
        ),
        "Earth Equiv. Orbit",
    )

    tabs.addTab(
        _tbl(
            ["Region", "AU"],
            [
                ["System Inner Limit (Gravity)",  _au_lm4(d["sysilGrav"])],
                ["System Inner Limit (Sunlight)", _au_lm4(d["sysilSunlight"])],
                ["Circumstellar HZ Inner Limit",  _au_lm4(d["hzil"])],
                ["Circumstellar HZ Outer Limit",  _au_lm4(d["hzol"])],
                ["Snow Line",                     _au_lm4(d["snowLine"])],
                ["Liquid Hydrogen (LH2) Line",    _au_lm4(d["lh2Line"])],
                ["System Outer Limit",            _au_lm4(d["sysol"])],
            ],
        ),
        "System Regions",
    )

    tabs.addTab(
        _tbl(
            ["Region", "AU"],
            [
                ["Fluorosilicone-Fluorosilicone Inner Limit", _au_lm4(d["ffInner"])],
                ["Fluorocarbon-Sulfur Inner Limit",           _au_lm4(d["fsInner"])],
                ["Fluorosilicone-Fluorosilicone Outer Limit", _au_lm4(d["ffOuter"])],
                ["Fluorocarbon-Sulfur Outer Limit",           _au_lm4(d["fsOuter"])],
                ["Protein-Water Inner Limit",                 _au_lm4(d["prwInner"])],
                ["Protein-Water Outer Limit",                 _au_lm4(d["prwOuter"])],
                ["Protein-Ammonia Inner Limit",               _au_lm4(d["praInner"])],
                ["Protein-Ammonia Outer Limit",               _au_lm4(d["praOuter"])],
                ["Polylipid-Methane Inner Limit",             _au_lm4(d["pmInner"])],
                ["Polylipid-Methane Outer Limit",             _au_lm4(d["pmOuter"])],
                ["Polylipid-Hydrogen Inner Limit",            _au_lm4(d["phInner"])],
                ["Polylipid-Hydrogen Outer Limit",            _au_lm4(d["phOuter"])],
            ],
        ),
        "Alternate HZ Regions",
    )

    _KEY_MAP = {
        "Recent Venus":    "rv",
        "5 Earth Mass":    "rg5",
        "Runaway Greenhouse - 0.1": "rg01",
        "Runaway Greenhouse)": "rg",
        "Maximum Greenhouse": "mg",
        "Early Mars":      "em",
    }
    zone_names = [
        "Optimistic Inner HZ (Recent Venus)",
        "Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",
        "Conservative Inner HZ (Runaway Greenhouse)",
        "Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)",
        "Conservative Outer HZ (Maximum Greenhouse)",
        "Optimistic Outer HZ (Early Mars)",
    ]

    def _hz_row(zone_name):
        key = next((v for k, v in _KEY_MAP.items() if k in zone_name), None)
        if key is None:
            return [zone_name, "?", "?", "?"]
        seff = _kopparapu_seff(d["temp"], key)
        def fmt(lum):
            au = math.sqrt(lum / seff)
            return _au_lm3(au)
        return [zone_name, fmt(d["bcLuminosity"]), fmt(d["luminosityFromMass"]), fmt(d["calculatedLuminosity"])]

    tabs.addTab(
        _tbl(
            ["Zone", "Bolometric Luminosity (AU)", "Luminosity from Mass (AU)", "Calculated Luminosity (AU)"],
            [_hz_row(z) for z in zone_names],
        ),
        "Calculated HZ",
    )

    # ── Visualization tabs (require matplotlib) ───────────────────────────────
    if mpl_available():
        # HZ Diagram: use calculatedLuminosity + temp, mark Earth Equiv. Orbit
        hz_data = core.viz.prepare_hz_diagram(d["temp"], d["calculatedLuminosity"])
        if "zones" in hz_data:
            hz_w = QWidget()
            hz_l = QVBoxLayout(hz_w)
            hz_l.setContentsMargins(4, 4, 4, 4)
            canvas, toolbar = make_hz_canvas(
                None,
                hz_data["zones"],
                hz_data["max_au"],
                title=f"Habitable Zone  (T={d['temp']:.0f} K,  L={d['calculatedLuminosity']:.4f} L☉)",
                eeid_au=d.get("distAU"),
            )
            hz_l.addWidget(toolbar)
            hz_l.addWidget(canvas)
            tabs.addTab(hz_w, "HZ Diagram")

        # System Regions Diagram: log-scale radial ruler
        regions_data = core.viz.prepare_system_regions_diagram(d)
        sr_canvas, sr_toolbar = make_system_regions_canvas(None, regions_data)
        if sr_canvas is not None:
            sr_w = QWidget()
            sr_l = QVBoxLayout(sr_w)
            sr_l.setContentsMargins(4, 4, 4, 4)
            sr_l.addWidget(sr_toolbar)
            sr_l.addWidget(sr_canvas)
            tabs.addTab(sr_w, "System Regions Diagram")

    return tabs


# ── Shared result-area helpers ────────────────────────────────────────────────

def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _render_result(result: dict, result_area: QVBoxLayout, show_designations: bool = True):
    _clear_layout(result_area)
    if "error" in result:
        lbl = QLabel(result["error"])
        lbl.setStyleSheet("color: red;")
        lbl.setWordWrap(True)
        result_area.addWidget(lbl)
        return
    if show_designations:
        simbad = result.get("simbad", {})
        desig_str = simbad.get("desig_str", "N/A")
        banner = QLabel(f"<b>STAR DESIGNATIONS:</b><br>{desig_str}")
        banner.setWordWrap(True)
        result_area.addWidget(banner)
    result_area.addWidget(_build_region_tabs(result))


# ── Option 8: Auto (SIMBAD) ───────────────────────────────────────────────────

class StarRegionsAutoPanel(ResultPanel):
    """Star System Regions — Auto (SIMBAD) [option 8]."""

    def build_inputs(self):
        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Vega, Alpha Centauri, HIP 27989")
        self._name.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name)
        self._btn = QPushButton("Search")
        self._btn.clicked.connect(self._search)
        form.addRow("", self._btn)
        self._layout.addLayout(form)

        self._result_area = QVBoxLayout()
        self._layout.addLayout(self._result_area)
        self._layout.addStretch()

    def build_results_area(self):
        pass

    def _search(self):
        name = self._name.text().strip()
        if not name:
            return
        _clear_layout(self._result_area)
        self.run_in_background(_compute_auto_regions, name, on_result=self._render)

    def _render(self, result: dict):
        _render_result(result, self._result_area, show_designations=True)


# ── Option 9: Semi-Manual ─────────────────────────────────────────────────────

class StarRegionsSemiManualPanel(ResultPanel):
    """Star System Regions — Semi-Manual [option 9]."""

    def build_inputs(self):
        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Vega, Alpha Centauri, HIP 27989")
        form.addRow("Star Name / Designation:", self._name)

        self._sunlight = QLineEdit()
        self._sunlight.setPlaceholderText("default: 1.0")
        form.addRow("Sunlight Intensity (Terra = 1.0):", self._sunlight)

        self._albedo = QLineEdit()
        self._albedo.setPlaceholderText("default: 0.3")
        form.addRow("Bond Albedo (Terra = 0.3, Venus = 0.9):", self._albedo)

        self._btn = QPushButton("Search")
        self._btn.clicked.connect(self._search)
        form.addRow("", self._btn)
        self._layout.addLayout(form)

        self._result_area = QVBoxLayout()
        self._layout.addLayout(self._result_area)
        self._layout.addStretch()

    def build_results_area(self):
        pass

    def _show_err(self, msg):
        _clear_layout(self._result_area)
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: red;")
        self._result_area.addWidget(lbl)

    def _search(self):
        name = self._name.text().strip()
        if not name:
            return
        try:
            sunlight = float(self._sunlight.text().strip() or "1.0")
        except ValueError:
            self._show_err("Sunlight Intensity must be a number.")
            return
        try:
            albedo = float(self._albedo.text().strip() or "0.3")
        except ValueError:
            self._show_err("Bond Albedo must be a number.")
            return
        _clear_layout(self._result_area)
        self.run_in_background(
            _compute_semi_manual_regions, name, sunlight, albedo,
            on_result=self._render,
        )

    def _render(self, result: dict):
        _render_result(result, self._result_area, show_designations=True)


# ── Option 10: Manual ─────────────────────────────────────────────────────────

class StarRegionsManualPanel(ResultPanel):
    """Star System Regions — Manual [option 10]."""

    def build_inputs(self):
        form = QFormLayout()

        def _field(placeholder):
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            return f

        self._vmag     = _field("e.g. 4.83")
        self._plx      = _field("e.g. 745.0 (must be > 0)")
        self._bc       = _field("e.g. -0.07")
        self._teff     = _field("e.g. 5778")
        self._sunlight = _field("e.g. 1.0")
        self._albedo   = _field("e.g. 0.3")

        form.addRow("Apparent Magnitude (V):",               self._vmag)
        form.addRow("Parallax (mas):",                       self._plx)
        form.addRow("Bolometric Correction (BC):",           self._bc)
        form.addRow("Star Effective Temperature (K):",       self._teff)
        form.addRow("Sunlight Intensity (Terra = 1.0):",     self._sunlight)
        form.addRow("Bond Albedo (Terra = 0.3, Venus = 0.9):", self._albedo)
        self._layout.addLayout(form)

        self._btn = QPushButton("Calculate")
        self._btn.clicked.connect(self._calculate)
        self._layout.addWidget(self._btn)

        self._result_area = QVBoxLayout()
        self._layout.addLayout(self._result_area)
        self._layout.addStretch()

    def build_results_area(self):
        pass

    def _show_err(self, msg):
        _clear_layout(self._result_area)
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: red;")
        self._result_area.addWidget(lbl)

    def _calculate(self):
        fields = {
            "Apparent Magnitude (V)": self._vmag,
            "Parallax (mas)":         self._plx,
            "Bolometric Correction":  self._bc,
            "Temperature (K)":        self._teff,
            "Sunlight Intensity":     self._sunlight,
            "Bond Albedo":            self._albedo,
        }
        values = {}
        for label, widget in fields.items():
            raw = widget.text().strip()
            if not raw:
                self._show_err(f"{label} is required.")
                return
            try:
                values[label] = float(raw)
            except ValueError:
                self._show_err(f"{label} must be a number.")
                return

        plx = values["Parallax (mas)"]
        if plx <= 0:
            self._show_err("Parallax must be greater than 0.")
            return

        result = core.regions.compute_star_system_regions(
            vmag=values["Apparent Magnitude (V)"],
            boloLum=values["Bolometric Correction"],
            temp=values["Temperature (K)"],
            plx=plx,
            sunlight_intensity=values["Sunlight Intensity"],
            bond_albedo=values["Bond Albedo"],
        )
        _render_result(result, self._result_area, show_designations=False)
