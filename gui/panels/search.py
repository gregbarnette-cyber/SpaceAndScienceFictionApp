# gui/panels/search.py — Phase G Search & Filter panels (GUI-only).
#
#   StarSystemsSearchPanel    (G1) — local star_systems table
#   HwcSearchPanel            (G2) — local hwc table
#   NasaExoplanetSearchPanel  (G3) — live NASA pscomppars TAP
#
# All three share SpectralClassControl + SearchPanelBase (inline drill-down tabs)
# from search_common, and the core search_* functions from core.databases.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QCheckBox, QComboBox,
)
from PySide6.QtCore import Qt

from gui.panels.search_common import SearchPanelBase, SpectralClassControl
from core.shared import _fval, LY_PER_PC
import core.databases


# ── small form helpers ───────────────────────────────────────────────────────

def _fnum(edit: QLineEdit):
    """Parse a QLineEdit as float; blank or invalid → None."""
    t = edit.text().strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _range_pair(on_change=None):
    """Return (container_widget, min_edit, max_edit) for a 'min to max' field."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    lo = QLineEdit(); lo.setPlaceholderText("min")
    hi = QLineEdit(); hi.setPlaceholderText("max")
    for e in (lo, hi):
        e.setMaximumWidth(90)
        e.setProperty("no_width_cap", True)
        if on_change is not None:
            e.textChanged.connect(lambda _t: on_change())
    h.addWidget(lo)
    h.addWidget(QLabel("to"))
    h.addWidget(hi)
    h.addStretch()
    return w, lo, hi


def _fmt(v, dp):
    """Format a value as fixed-decimal, or 'N/A' (parses numeric strings via _fval)."""
    fv = _fval(v)
    return f"{fv:.{dp}f}" if fv is not None else "N/A"


def _ly(pc):
    """Format a parsec value as light years (4 dp), or 'N/A'."""
    fv = _fval(pc)
    return f"{fv * LY_PER_PC:.4f}" if fv is not None else "N/A"


# ── G1: Star Systems Search ──────────────────────────────────────────────────

class StarSystemsSearchPanel(SearchPanelBase):
    """Filter the local star_systems table by spectral class, distance,
    magnitude, or designation prefix (Phase G1). No network."""

    def build_search_ui(self, layout):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spectral = SpectralClassControl()
        self._spectral.changed.connect(self._gate)
        form.addRow("Spectral Class:", self._spectral)

        ly_w, self._ly_min, self._ly_max = _range_pair(self._gate)
        form.addRow("Light Years:", ly_w)

        mag_w, self._mag_min, self._mag_max = _range_pair(self._gate)
        form.addRow("Apparent Magnitude:", mag_w)

        self._desig = QLineEdit()
        self._desig.setPlaceholderText("e.g. GJ, HD 1")
        self._desig.textChanged.connect(lambda _t: self._gate())
        self._desig.returnPressed.connect(self._search)
        form.addRow("Designation Prefix:", self._desig)

        # Phase L4 stretch: Fe/H filter (needs the Hypatia cache) — disabled stub.
        feh_w, feh_lo, feh_hi = _range_pair()
        for e in (feh_lo, feh_hi):
            e.setEnabled(False)
        form.addRow("Fe/H  [L4]:", feh_w)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self.run_btn.setEnabled(False)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        self._hint = QLabel("Pick a spectral class or enter at least one filter.")
        self._hint.setStyleSheet("color: #999; font-size: 11px;")
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(self._hint)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._build_results_scaffold(layout)
        self._gate()

    def _has_any_filter(self) -> bool:
        if not self._spectral.is_empty():
            return True
        for e in (self._ly_min, self._ly_max, self._mag_min, self._mag_max, self._desig):
            if e.text().strip():
                return True
        return False

    def _gate(self):
        ready = self._has_any_filter()
        self.run_btn.setEnabled(ready)
        self._hint.setText("Ready — searching the star_systems table."
                           if ready else "Pick a spectral class or enter at least one filter.")

    def _clear_form(self):
        self._spectral.clear()
        for e in (self._ly_min, self._ly_max, self._mag_min, self._mag_max, self._desig):
            e.clear()
        self._gate()

    def _filters(self) -> dict:
        return {
            "spectral_classes":   self._spectral.classes() or None,
            "spectral_refine":    self._spectral.refine(),
            "ly_min":             _fnum(self._ly_min),
            "ly_max":             _fnum(self._ly_max),
            "mag_min":            _fnum(self._mag_min),
            "mag_max":            _fnum(self._mag_max),
            "designation_prefix": self._desig.text().strip() or None,
        }

    def _search(self):
        if not self._has_any_filter():
            return
        self.run_in_background(core.databases.search_star_systems, self._filters(),
                               on_result=self._render)

    def _render(self, result: dict):
        if "error" in result:
            self._show_search_error(result["error"])
            return
        records = result["stars"]
        headers = ["Star Name", "Designations", "Spectral Type", "Light Years", "App. Magnitude"]

        display_rows = [
            [r.get("star_name") or "N/A", r.get("designations") or "",
             r.get("spectral_type") or "N/A",
             _fmt(r.get("light_years"), 4), _fmt(r.get("app_magnitude"), 3)]
            for r in records
        ]
        self._render_table(headers, display_rows, records,
                           "Open star in new tab →", self._open_star, "star")
        self._set_footer(result.get("capped"), result.get("cap"))

    def _open_star(self, rec: dict):
        name = rec.get("star_name") or ""
        if not name:
            return
        from gui.panels.simbad import SimbadPanel
        self.open_detail_tab(("g1", name), f"★ {name}",
                             lambda: self._make_detail(SimbadPanel, "_name_input", name))


# ── G2: HWC Planet Search ────────────────────────────────────────────────────

def _yn(v):
    return "Yes" if str(v).strip() == "1" else "No"


class HwcSearchPanel(SearchPanelBase):
    """Filter the local Habitable Worlds Catalog (hwc) table by habitability
    flags, ESI, mass, radius, temperature, spectral class, and distance
    (Phase G2). No network. Sorted by ESI desc."""

    def build_search_ui(self, layout):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._esi = QLineEdit()
        self._esi.setPlaceholderText("0.0")
        self._esi.setMaximumWidth(90)
        self._esi.setProperty("no_width_cap", True)
        self._esi.returnPressed.connect(self._search)
        form.addRow("ESI minimum:", self._esi)

        checks = QHBoxLayout()
        self._hab = QCheckBox("Habitable only")
        self._con = QCheckBox("Conservative HZ only")
        self._opt = QCheckBox("Optimistic HZ only")
        for c in (self._hab, self._con, self._opt):
            checks.addWidget(c)
        checks.addStretch()
        checks_w = QWidget(); checks_w.setLayout(checks)
        form.addRow("Flags:", checks_w)

        mass_w, self._mass_min, self._mass_max = _range_pair()
        form.addRow("Planet Mass (M⊕):", mass_w)
        rad_w, self._rad_min, self._rad_max = _range_pair()
        form.addRow("Planet Radius (R⊕):", rad_w)
        temp_w, self._temp_min, self._temp_max = _range_pair()
        form.addRow("Equil. Temp (K):", temp_w)

        self._spectral = SpectralClassControl()
        form.addRow("Spectral Class:", self._spectral)

        self._ly_max = QLineEdit()
        self._ly_max.setPlaceholderText("any")
        self._ly_max.setMaximumWidth(90)
        self._ly_max.setProperty("no_width_cap", True)
        self._ly_max.returnPressed.connect(self._search)
        form.addRow("Max Distance (LY):", self._ly_max)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        hint = QLabel("Sorted by ESI (desc) · caps at 500 rows.")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(hint)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._build_results_scaffold(layout)

    def _clear_form(self):
        for e in (self._esi, self._mass_min, self._mass_max, self._rad_min,
                  self._rad_max, self._temp_min, self._temp_max, self._ly_max):
            e.clear()
        for c in (self._hab, self._con, self._opt):
            c.setChecked(False)
        self._spectral.clear()

    def _filters(self) -> dict:
        return {
            "esi_min":          _fnum(self._esi),
            "habitable":        self._hab.isChecked(),
            "habzone_con":      self._con.isChecked(),
            "habzone_opt":      self._opt.isChecked(),
            "mass_min":         _fnum(self._mass_min),
            "mass_max":         _fnum(self._mass_max),
            "radius_min":       _fnum(self._rad_min),
            "radius_max":       _fnum(self._rad_max),
            "temp_min":         _fnum(self._temp_min),
            "temp_max":         _fnum(self._temp_max),
            "spectral_classes": self._spectral.classes() or None,
            "spectral_refine":  self._spectral.refine(),
            "ly_max":           _fnum(self._ly_max),
        }

    def _search(self):
        self.run_in_background(core.databases.search_hwc, self._filters(),
                               on_result=self._render)

    def _render(self, result: dict):
        if "error" in result:
            self._show_search_error(result["error"])
            return
        records = result["stars"]
        headers = ["Planet", "ESI", "Habitable?", "In Con HZ?", "In Opt HZ?",
                   "Mass (M⊕)", "Radius (R⊕)", "Temp K", "Star", "Spectral Type",
                   "Distance (LY)"]

        display_rows = [
            [r.get("P_NAME") or "N/A", _fmt(r.get("P_ESI"), 4),
             _yn(r.get("P_HABITABLE")), _yn(r.get("P_HABZONE_CON")), _yn(r.get("P_HABZONE_OPT")),
             _fmt(r.get("P_MASS"), 2), _fmt(r.get("P_RADIUS"), 2), _fmt(r.get("P_TEMP_EQUIL"), 0),
             r.get("S_NAME") or "N/A", r.get("S_TYPE") or "N/A", _ly(r.get("S_DISTANCE"))]
            for r in records
        ]
        self._render_table(headers, display_rows, records,
                           "Open system in new tab →", self._open_system, "planet")
        self._set_footer(result.get("capped"), result.get("cap"))

    def _open_system(self, rec: dict):
        star = rec.get("S_NAME") or ""
        if not star:
            return
        from gui.panels.catalogs import HwcPanel
        self.open_detail_tab(("g2", star), f"🪐 {star}",
                             lambda: self._make_detail(HwcPanel, "_name", star))


# ── G3: NASA Exoplanet Quick Search ──────────────────────────────────────────

class NasaExoplanetSearchPanel(SearchPanelBase):
    """Query the live NASA Exoplanet Archive (pscomppars) by planet mass, radius,
    period, host spectral class, discovery method, distance, and temperature
    (Phase G3). Caps at 200 rows sorted by SMA asc."""

    # Exact NASA pscomppars `discoverymethod` enum values — this is an exact-match
    # filter, so the labels MUST match the archive (e.g. "Imaging" not "Direct
    # Imaging"; "Transit Timing Variations" not "Timing") or the query returns 0.
    _METHODS = ["Any", "Transit", "Radial Velocity", "Imaging", "Microlensing",
                "Astrometry", "Transit Timing Variations"]

    def build_search_ui(self, layout):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        mass_w, self._mass_min, self._mass_max = _range_pair()
        form.addRow("Planet Mass (M⊕):", mass_w)
        rad_w, self._rad_min, self._rad_max = _range_pair()
        form.addRow("Planet Radius (R⊕):", rad_w)
        per_w, self._per_min, self._per_max = _range_pair()
        form.addRow("Orbital Period (days):", per_w)

        self._method = QComboBox()
        self._method.addItems(self._METHODS)
        form.addRow("Discovery Method:", self._method)

        teff_w, self._teff_min, self._teff_max = _range_pair()
        form.addRow("Teff (K):", teff_w)

        self._spectral = SpectralClassControl()
        form.addRow("Spectral Class:", self._spectral)

        self._dist = QLineEdit()
        self._dist.setPlaceholderText("any")
        self._dist.setMaximumWidth(90)
        self._dist.setProperty("no_width_cap", True)
        self._dist.returnPressed.connect(self._search)
        form.addRow("Max Distance (LY):", self._dist)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_form)
        hint = QLabel("Live network query · caps at 200 rows · sorted by SMA.")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(hint)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._build_results_scaffold(layout)

    def _clear_form(self):
        for e in (self._mass_min, self._mass_max, self._rad_min, self._rad_max,
                  self._per_min, self._per_max, self._teff_min, self._teff_max, self._dist):
            e.clear()
        self._method.setCurrentIndex(0)
        self._spectral.clear()

    def _filters(self) -> dict:
        # The user enters Max Distance in light years; the archive's sy_dist is in
        # parsecs, so convert ly -> pc (pc = ly / 3.26156) for the query.
        ly_max = _fnum(self._dist)
        return {
            "pl_bmasse_min":    _fnum(self._mass_min),
            "pl_bmasse_max":    _fnum(self._mass_max),
            "pl_rade_min":      _fnum(self._rad_min),
            "pl_rade_max":      _fnum(self._rad_max),
            "pl_orbper_min":    _fnum(self._per_min),
            "pl_orbper_max":    _fnum(self._per_max),
            "st_teff_min":      _fnum(self._teff_min),
            "st_teff_max":      _fnum(self._teff_max),
            "sy_dist_max":      (ly_max / LY_PER_PC) if ly_max is not None else None,
            "discoverymethod":  self._method.currentText(),
            "spectral_classes": self._spectral.classes() or None,
            "spectral_refine":  self._spectral.refine(),
        }

    def _search(self):
        self._count_lbl.setStyleSheet("color: #777;")
        self._count_lbl.setText("Querying NASA Exoplanet Archive…")
        self.run_in_background(core.databases.search_exoplanets, self._filters(),
                               on_result=self._render)

    def _render(self, result: dict):
        if "error" in result:
            self._show_search_error(result["error"])
            return
        records = result["stars"]
        headers = ["Planet", "Host Star", "Mass (M⊕)", "Radius (R⊕)", "Period (d)",
                   "SMA (AU)", "Spectral Type", "Discovery Method", "Teff (K)",
                   "Distance (LY)"]

        display_rows = [
            [r.get("pl_name") or "N/A", r.get("hostname") or "N/A",
             _fmt(r.get("pl_bmasse"), 2), _fmt(r.get("pl_rade"), 2), _fmt(r.get("pl_orbper"), 2),
             _fmt(r.get("pl_orbsmax"), 4), r.get("st_spectype") or "N/A",
             r.get("discoverymethod") or "N/A", _fmt(r.get("st_teff"), 0), _ly(r.get("sy_dist"))]
            for r in records
        ]
        self._render_table(headers, display_rows, records,
                           "Open system in new tab →", self._open_system, "planet")
        self._set_footer(result.get("capped"), result.get("cap"))

    def _open_system(self, rec: dict):
        host = rec.get("hostname") or ""
        if not host:
            return
        from gui.panels.nasa_exoplanet import NasaPlanetarySystemsPanel
        self.open_detail_tab(("g3", host), f"🪐 {host}",
                             lambda: self._make_detail(NasaPlanetarySystemsPanel, "_name", host))
