# gui/panels/solvent_zones.py — Phase P: Solvent Habitable Zones (GUI-only).
#
# Panels fold into the existing "Worldbuilding" nav category:
#   SolventZonePanel (P4) — solvent liquid-zone calculator + V3 ring diagram.
#   (IceLineCalculatorPanel (P5) and SolventReferencePanel (P6) are added later.)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QLineEdit, QComboBox, QLabel, QCheckBox,
)

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.equations
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_solvent_zone_canvas, make_solvent_bar_canvas,
    make_ice_line_canvas, wrap_scrollable,
)

_CUSTOM = "Custom liquid range…"


def _err_label(msg):
    lbl = QLabel(msg)
    lbl.setStyleSheet("color: red;")
    lbl.setWordWrap(True)
    return lbl


def _note_label(msg, color="#777"):
    lbl = QLabel(msg)
    lbl.setStyleSheet(f"color: {color};")
    lbl.setWordWrap(True)
    return lbl


class SolventZonePanel(DiagramToggleMixin, ResultPanel):
    """Solvent Habitable Zone (Phase P P4) — the AU band where a chosen solvent is
    liquid on a planet surface (M1 surface model). Pure math, no network."""

    def build_inputs(self):
        self._form_widget = QWidget()
        outer = QVBoxLayout(self._form_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._lum = QLineEdit()
        self._lum.setPlaceholderText("e.g. 1.0")
        self._lum.returnPressed.connect(self._calculate)
        form.addRow("Star Luminosity (L☉):", self._lum)

        self._solvent = QComboBox()
        for s in core.equations.get_solvents():
            label = s["name"] + (f"  (≥{s['assumed_pressure_atm']} atm)"
                                  if s["pressure_conditional"] else "")
            self._solvent.addItem(label, s["key"])
        self._solvent.addItem(_CUSTOM, "__custom")
        self._solvent.currentIndexChanged.connect(self._on_solvent_change)
        form.addRow("Solvent:", self._solvent)

        self._t_low = QLineEdit();  self._t_low.setPlaceholderText("freeze / lower edge K")
        self._t_high = QLineEdit(); self._t_high.setPlaceholderText("boil / upper edge K")
        self._t_low.returnPressed.connect(self._calculate)
        self._t_high.returnPressed.connect(self._calculate)
        self._t_low_row = QLabel("Custom Lower T (K):")
        self._t_high_row = QLabel("Custom Upper T (K):")
        form.addRow(self._t_low_row, self._t_low)
        form.addRow(self._t_high_row, self._t_high)

        self._albedo = QLineEdit()
        self._albedo.setPlaceholderText("0.3")
        self._albedo.returnPressed.connect(self._calculate)
        form.addRow("Bond Albedo (optional):", self._albedo)
        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Compute")
        self.run_btn.clicked.connect(self._calculate)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._layout.addWidget(self._form_widget)
        self._input_count = self._layout.count()
        self._on_solvent_change()   # set initial custom-field visibility

    def _on_solvent_change(self):
        custom = self._solvent.currentData() == "__custom"
        for w in (self._t_low, self._t_high, self._t_low_row, self._t_high_row):
            w.setVisible(custom)

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()

    def _clear_tables(self):
        while self._tables_layout.count():
            item = self._tables_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _calculate(self):
        self._prepare_render()
        self._clear_tables()
        self._render()
        self._tables_layout.addStretch(1)

    @staticmethod
    def _read_float(text):
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return "BAD"

    def _render(self):
        lum = self._read_float(self._lum.text())
        if lum is None or lum == "BAD":
            self._tables_layout.addWidget(_err_label("Enter a numeric luminosity (L☉)."))
            return

        albedo = self._read_float(self._albedo.text())
        if albedo == "BAD":
            self._tables_layout.addWidget(_err_label("Albedo must be a number in [0, 1)."))
            return
        if albedo is None:
            albedo = 0.3

        custom = self._solvent.currentData() == "__custom"
        if custom:
            t_low = self._read_float(self._t_low.text())
            t_high = self._read_float(self._t_high.text())
            if t_low in (None, "BAD") or t_high in (None, "BAD"):
                self._tables_layout.addWidget(
                    _err_label("Custom range needs both a numeric lower and upper temperature (K)."))
                return
            result = core.equations.compute_solvent_zone(
                lum, t_low_k=t_low, t_high_k=t_high, albedo=albedo)
        else:
            result = core.equations.compute_solvent_zone(
                lum, solvent=self._solvent.currentData(), albedo=albedo)

        if "error" in result:
            self._tables_layout.addWidget(_err_label(result["error"]))
            return

        headers = ["Solvent", "Liquid Range (K)", "Albedo",
                   "Inner", "Outer", "S_eff (in / out)"]
        rows = [[
            result["name"],
            f"{result['t_low_k']:.1f} – {result['t_high_k']:.1f}",
            f"{result['albedo']:.2f}",
            f"{result['inner_au']:.3f} AU ({result['inner_lm']:.3f} LM)",
            f"{result['outer_au']:.3f} AU ({result['outer_lm']:.3f} LM)",
            f"{result['s_eff_inner']:.4g} / {result['s_eff_outer']:.4g}",
        ]]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        table.setMaximumHeight(80)
        self._tables_layout.addWidget(table)

        if result.get("pressure_conditional"):
            self._tables_layout.addWidget(_note_label(
                f"⚠ Pressure-conditional solvent — band assumes "
                f"≥ {result['assumed_pressure_atm']} atm (no 1-atm liquid phase).",
                color="#b8860b"))
        if result.get("citation"):
            self._tables_layout.addWidget(_note_label(
                f"Liquid range: {result['citation']}.  M1 surface model "
                f"(T_ref = {result['t_ref_k']:.1f} K at A = {result['albedo']:.2f})."))

        # V3 ring diagram tab (water HZ drawn behind for reference).
        if mpl_available():
            water_ref = None
            if result.get("solvent") != "water":
                water_ref = core.equations.compute_solvent_zone(
                    lum, solvent="water", albedo=albedo)
            canvas, toolbar = make_solvent_zone_canvas(None, result, water_ref)
            if canvas is not None:
                w = QWidget()
                wl = QVBoxLayout(w)
                wl.setContentsMargins(4, 4, 4, 4)
                wl.addWidget(toolbar)
                wl.addWidget(canvas)
                self._viz_tabs_widget.addTab(w, "Solvent Zone Ring")

        self._finish_render()


def _ice_ring_tab(data):
    """V4 frost-line ring tab: a 'Full range' checkbox over an auto-rebuilt
    make_ice_line_canvas (inner-focus ≤ 18 AU by default)."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    chk = QCheckBox("Full range (draw the deep-cold N₂/CO disk fronts to scale)")
    lay.addWidget(chk)
    holder = QWidget()
    hlay = QVBoxLayout(holder)
    hlay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(holder, 1)

    def _rebuild():
        while hlay.count():
            it = hlay.takeAt(0)
            ww = it.widget()
            if ww:
                ww.deleteLater()
        canvas, toolbar = make_ice_line_canvas(None, data, full_range=chk.isChecked())
        if canvas is not None:
            hlay.addWidget(toolbar)
            hlay.addWidget(canvas)

    chk.toggled.connect(_rebuild)
    _rebuild()
    return w


class IceLineCalculatorPanel(DiagramToggleMixin, ResultPanel):
    """Ice-Line Calculator (Phase P P5) — the water snow line + CO₂/NH₃/N₂/CO
    condensation fronts for a star of a given luminosity (M2 equilibrium model,
    no greenhouse). Pure math; the V4 frost-line ring is behind Show Diagrams."""

    def build_inputs(self):
        self._form_widget = QWidget()
        outer = QVBoxLayout(self._form_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._lum = QLineEdit()
        self._lum.setPlaceholderText("e.g. 1.0")
        self._lum.returnPressed.connect(self._calculate)
        form.addRow("Star Luminosity (L☉):", self._lum)

        self._albedo = QLineEdit()
        self._albedo.setPlaceholderText("0.0  (bare ice grains)")
        self._albedo.returnPressed.connect(self._calculate)
        form.addRow("Bond Albedo (optional):", self._albedo)
        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Compute")
        self.run_btn.clicked.connect(self._calculate)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._layout.addWidget(self._form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()

    def _clear_tables(self):
        while self._tables_layout.count():
            item = self._tables_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _calculate(self):
        self._prepare_render()
        self._clear_tables()
        self._render()
        self._tables_layout.addStretch(1)

    def _render(self):
        lum = SolventZonePanel._read_float(self._lum.text())
        if lum is None or lum == "BAD":
            self._tables_layout.addWidget(_err_label("Enter a numeric luminosity (L☉)."))
            return
        albedo = SolventZonePanel._read_float(self._albedo.text())
        if albedo == "BAD":
            self._tables_layout.addWidget(_err_label("Albedo must be a number in [0, 1)."))
            return
        if albedo is None:
            albedo = 0.0

        result = core.equations.compute_ice_lines(lum, albedo=albedo)
        if "error" in result:
            self._tables_layout.addWidget(_err_label(result["error"]))
            return

        headers = ["Species / line", "Cond. T (K)", "Distance (AU)",
                   "Distance (LM)", "Type", "Note"]
        rows = [[
            ln["species"], f"{ln['t_cond_k']:.0f}",
            f"{ln['au']:.3f}", f"{ln['lm']:.2f}", ln["kind"], ln["note"],
        ] for ln in result["lines"]]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        self._tables_layout.addWidget(table)
        self._tables_layout.addWidget(_note_label(
            f"M2 equilibrium model (no greenhouse), T_ref = {result['t_ref_k']:.1f} K "
            f"at A = {result['albedo']:.2f}. Disk-set N₂/CO fronts: placement illustrative. "
            f"Formation-era water snow line spans ~2–3 AU across the disk's lifetime."))

        if mpl_available():
            data = core.viz.prepare_ice_line_diagram(result)
            if "error" not in data:
                self._viz_tabs_widget.addTab(_ice_ring_tab(data), "Frost-Line Map")

        self._finish_render()


class SolventReferencePanel(DiagramToggleMixin, ResultPanel):
    """Solvent Reference Table (Phase P P6) — a static display of the built-in
    solvent table (à la Main Sequence Star Properties). No computation; the
    liquid ranges, the implied 288 K equilibrium-T band, the Bains-2024
    plausibility verdict, and the key citation. A V5 liquid-range bar chart is
    behind the Show Diagrams toggle."""

    def build_inputs(self):
        # No inputs — just a Show Diagrams button (revealed after the V5 tab builds).
        from PySide6.QtWidgets import QWidget as _QW, QHBoxLayout as _QH
        form_widget = _QW()
        row = _QH(form_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        row.addWidget(self._show_diagrams_btn)
        row.addStretch()
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        tlay = QVBoxLayout(self._tables_widget)
        tlay.setContentsMargins(0, 0, 0, 0)

        headers = ["Solvent", "Liquid Range (K, 1 atm)",
                   "Equilibrium-T Band (A=0.3)", "Plausibility (Bains 2024)",
                   "Key Citation"]
        rows = []
        for s in core.equations.get_solvents():
            name = s["name"]
            if s["pressure_conditional"]:
                name += f"  (≥{s['assumed_pressure_atm']} atm)"
            rows.append([
                name,
                f"{s['t_low_k']:.1f} – {s['t_high_k']:.1f}",
                f"{s['t_low_k']:.0f} – {s['t_high_k']:.0f} K",
                s["plausibility"],
                s["citation"],
            ])
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)   # preserve the built-in table order
        tlay.addWidget(view)
        self._layout.addWidget(self._tables_widget, 1)

        # ── V5 liquid-range bar chart viz tab ─────────────────────────────────
        self._setup_diagram_view()
        if mpl_available():
            data = core.viz.prepare_solvent_ranges()
            canvas, toolbar = make_solvent_bar_canvas(None, data)
            if canvas is not None:
                self._viz_tabs_widget.addTab(
                    wrap_scrollable(None, canvas, toolbar), "Liquid Ranges")
        self._finish_render()
