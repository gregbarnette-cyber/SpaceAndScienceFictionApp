# gui/panels/comparison.py — Phase L: Exoplanet Comparison Dashboard (L1–L3).
#
#   StarComparisonPanel   (L1) — side-by-side 2–4 star comparison (compare_stars)
#   EsiRankingPanel       (L2) — ESI leaderboard over the local HWC (search_hwc)
#   StellarEvolutionPanel (L3) — evolutionary-stage timeline (compute_stellar_evolution)
#
# L1/L3 carry matplotlib viz tabs via DiagramToggleMixin; L2 is a plain table panel.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLineEdit,
    QLabel, QCheckBox, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.databases
import core.equations
import core.viz

from gui.visualizations.plot_helpers import (
    mpl_available, wrap_scrollable,
    make_abundance_comparison_canvas, make_evolution_canvas, make_esi_bar_canvas,
)


# ── shared formatting helpers ────────────────────────────────────────────────

def _f(v, d):
    """Format a number to *d* decimals, or return None (→ 'N/A') for non-numbers."""
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return None


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fit_table_height(view):
    """Pin a QTableView's height to exactly fit its rows (no trailing white space).

    Fires once now and once via a 0-ms timer so a horizontal scrollbar that only
    appears after layout is included in the final measurement.
    """
    def _apply():
        view.resizeRowsToContents()
        model = view.model()
        h = view.horizontalHeader().height() + 2 * view.frameWidth()
        for r in range(model.rowCount() if model else 0):
            h += view.rowHeight(r)
        if view.horizontalScrollBar().isVisible():
            h += view.horizontalScrollBar().height()
        view.setFixedHeight(h)
    _apply()
    QTimer.singleShot(0, _apply)


# ═══════════════════════════════════════════════════════════════════════════
# L1 — Star Comparison
# ═══════════════════════════════════════════════════════════════════════════

class StarComparisonPanel(DiagramToggleMixin, ResultPanel):
    """Compare 2–4 stars in one transposed table (+ abundance-comparison chart)."""

    _MAX_STARS = 4

    def build_inputs(self):
        self._form_widget = QWidget()
        outer = QVBoxLayout(self._form_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._inputs = []
        for i in range(self._MAX_STARS):
            le = QLineEdit()
            le.setPlaceholderText("e.g. Tau Ceti")
            le.returnPressed.connect(self._compare)
            row_label = f"Star {i + 1}:"
            form.addRow(row_label, le)
            self._inputs.append(le)
            if i >= 2:                      # stars 3 & 4 hidden until "Add Star"
                le.hide()
                form.labelForField(le).hide()
        self._form = form
        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Compare")
        self.run_btn.clicked.connect(self._compare)
        self._add_star_btn = QPushButton("+ Add Star")
        self._add_star_btn.clicked.connect(self._add_star)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._add_star_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._visible_stars = 2
        self._layout.addWidget(self._form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        # Tables live in a scroll area: each table is pinned to its content
        # height (so a 9-row table shows no white space and the ~49-row Hypatia
        # table is fully tall), and the scroll area provides one outer scrollbar.
        inner = QWidget()
        self._tables_layout = QVBoxLayout(inner)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._tables_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        self._tables_widget = scroll           # mixin hides this in diagram mode
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()

    def _add_star(self):
        if self._visible_stars >= self._MAX_STARS:
            return
        le = self._inputs[self._visible_stars]
        le.show()
        self._form.labelForField(le).show()
        self._visible_stars += 1
        if self._visible_stars >= self._MAX_STARS:
            self._add_star_btn.setVisible(False)

    def _clear_tables(self):
        while self._tables_layout.count():
            item = self._tables_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _compare(self):
        names = [self._inputs[i].text().strip() for i in range(self._visible_stars)]
        names = [n for n in names if n]
        if len(names) < 2:
            self._prepare_render()
            self._clear_tables()
            self._tables_layout.addWidget(_err_label("Enter at least 2 stars to compare."))
            return
        self.run_in_background(core.databases.compare_stars, names,
                               on_result=self._render)

    # property rows: (label, key, decimals or None for str)
    _ROWS = [
        ("Spectral Type",   "sp_type",       None),
        ("Temp (K)",        "teff",          0),
        ("Luminosity (L☉)", "luminosity",    4),
        ("Mass (M☉)",       "mass",          2),
        ("Radius (R☉)",     "radius",        2),
        ("HZ Inner (AU)",   "hz_inner_au",   3),
        ("HZ Outer (AU)",   "hz_outer_au",   3),
        ("Distance (LY)",   "ly",            2),
        ("Apparent Mag",    "app_magnitude", 2),
    ]

    def _render(self, result):
        self._prepare_render()
        self._clear_tables()
        self._render_body(result)
        # Pack content against the top (the scroll area's inner widget can grow
        # taller than the tables when little data is returned).
        self._tables_layout.addStretch(1)

    def _render_body(self, result):
        if "error" in result:
            self._tables_layout.addWidget(_err_label(result["error"]))
            return

        stars = result.get("stars", [])
        col_names = [s.get("name") or "?" for s in stars]

        # Main comparison table (transposed: property rows × star columns).
        headers = ["Property"] + col_names
        rows = []
        for label, key, dec in self._ROWS:
            row = [label]
            for s in stars:
                if s.get("error"):
                    # surface the per-star error once, on the Spectral Type row
                    row.append(s["error"] if key == "sp_type" else None)
                elif dec is None:
                    row.append(s.get(key))
                else:
                    row.append(_f(s.get(key), dec))
            rows.append(row)
        self._tables_layout.addWidget(QLabel("<b>Star Comparison</b>"))
        main_table = self.make_table(headers, rows)
        _fit_table_height(main_table)
        self._tables_layout.addWidget(main_table)

        # Hypatia comparison table (only if ≥1 star has Hypatia properties/abundances).
        hyp_rows = self._hypatia_rows(stars)
        if hyp_rows:
            self._tables_layout.addWidget(QLabel("<b>Hypatia Catalog</b>"))
            hyp_table = self.make_table(headers, hyp_rows)
            _fit_table_height(hyp_table)
            self._tables_layout.addWidget(hyp_table)

        # Abundance-comparison diagram tab.
        if mpl_available():
            data = core.viz.prepare_abundance_comparison(result)
            if "error" not in data:
                canvas, toolbar = make_abundance_comparison_canvas(None, data)
                if canvas is not None:
                    self._viz_tabs_widget.addTab(
                        wrap_scrollable(None, canvas, toolbar), "Abundance Profiles")

        self._finish_render()

    @staticmethod
    def _hypatia_rows(stars):
        # Build per-star {element: mean} + properties; skip the section entirely
        # if no star carries usable Hypatia data. `defining` collects the union of
        # elements that are real catalogued measurements (n > 0 or unknown) so a
        # pure 0-baseline like the Sun (n = 0) fills rows without expanding the set.
        from core.hypatia_elements import display_symbol, SPECIES_ORDER

        per_star, has_any, defining = [], False, set()
        for s in stars:
            hyp = s.get("hypatia")
            if hyp and "error" not in hyp:
                props = hyp.get("properties") or {}
                ab = {}
                for a in hyp.get("abundances", []):
                    m = a.get("mean")
                    if m is None:
                        continue
                    el = a["element"]
                    ab[el] = m
                    n = a.get("n")
                    if n is None or n > 0:
                        defining.add(el)
                per_star.append((props, ab))
                if props or ab:
                    has_any = True
            else:
                per_star.append(({}, {}))
        if not has_any:
            return None

        def prop_row(label, pkey, dec):
            row = [label]
            for props, _ab in per_star:
                row.append(_f(props.get(pkey), dec) if dec is not None else props.get(pkey))
            return row

        # Stellar / kinematic property rows first.
        rows = [
            prop_row("log g",    "logg", 2),
            prop_row("Disk",     "disk", None),
            prop_row("U (km/s)", "u_vel", 1),
            prop_row("V (km/s)", "v_vel", 1),
            prop_row("W (km/s)", "w_vel", 1),
        ]
        # Then one [X/H] row per measured element, in the master display order
        # (category → atomic number), matching the SIMBAD Hypatia tab grouping.
        for el in sorted(defining, key=lambda k: SPECIES_ORDER.get(k.lower(), 999)):
            row = [f"[{display_symbol(el)}/H]"]
            for _props, ab in per_star:
                row.append(_f(ab.get(el), 2))
            rows.append(row)
        return rows


# ═══════════════════════════════════════════════════════════════════════════
# L2 — ESI Ranking (reuses search_hwc; no new core function)
# ═══════════════════════════════════════════════════════════════════════════

class EsiRankingPanel(DiagramToggleMixin, ResultPanel):
    """ESI leaderboard over the local HWC (presentation over search_hwc), with a
    top-N ESI bar chart in a Show Diagrams tab."""

    def build_inputs(self):
        self._form_widget = QWidget()
        outer = QVBoxLayout(self._form_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._esi = QLineEdit()
        self._esi.setPlaceholderText("e.g. 0.80  (blank = any)")
        self._esi.returnPressed.connect(self._rank)
        form.addRow("Minimum ESI:", self._esi)

        self._hab = QCheckBox("Habitable only")
        self._con = QCheckBox("Conservative HZ only")
        checks = QHBoxLayout()
        checks.addWidget(self._hab)
        checks.addWidget(self._con)
        checks.addStretch()
        form.addRow("", _wrap_layout(checks))

        self._lymax = QLineEdit()
        self._lymax.setPlaceholderText("(any)")
        self._lymax.returnPressed.connect(self._rank)
        form.addRow("Max Distance (LY):", self._lymax)
        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Rank")
        self.run_btn.clicked.connect(self._rank)
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
        # Table host fills the space below the inputs (stretch = 1) and scrolls
        # internally for long result sets (up to 500); the mixin hides it in
        # diagram mode and shows the ESI-chart tab instead.
        self._tables_widget = QWidget()
        self._result_container = QVBoxLayout(self._tables_widget)
        self._result_container.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()

    def _clear_container(self):
        while self._result_container.count():
            item = self._result_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rank(self):
        self._prepare_render()
        filters = {}
        esi = _safe_float(self._esi.text().strip())
        if esi is not None:                 # blank/invalid → no minimum (rank all)
            filters["esi_min"] = esi
        if self._hab.isChecked():
            filters["habitable"] = True
        if self._con.isChecked():
            filters["habzone_con"] = True
        lymax = _safe_float(self._lymax.text().strip())
        if lymax is not None:
            filters["ly_max"] = lymax

        result = core.databases.search_hwc(filters)
        self._clear_container()
        if "error" in result:
            self._result_container.addWidget(_err_label(result["error"]))
            return

        stars = result.get("stars", [])
        self._result_container.addWidget(QLabel(
            f"{len(stars)} planet{'s' if len(stars) != 1 else ''} found"
            + ("  (showing first 500)" if result.get("capped") else "")))

        headers = ["Rank", "Planet", "ESI", "Habitable?", "In Con HZ?", "In Opt HZ?",
                   "Temp (K)", "Star", "Spectral", "Distance (LY)"]
        rows = []
        self._esi_star_names = []
        for i, r in enumerate(stars, start=1):
            pc = _safe_float(r.get("S_DISTANCE"))
            rows.append([
                i,
                r.get("P_NAME"),
                _f(r.get("P_ESI"), 4),
                _yn(r.get("P_HABITABLE")),
                _yn(r.get("P_HABZONE_CON")),
                _yn(r.get("P_HABZONE_OPT")),
                _f(r.get("P_TEMP_EQUIL"), 0),
                r.get("S_NAME"),
                r.get("S_TYPE"),
                _f(pc * 3.26156, 4) if pc is not None else None,
            ])
            self._esi_star_names.append(r.get("S_NAME"))

        table = self.make_table(headers, rows)
        table.doubleClicked.connect(self._open_hwc)
        self._result_container.addWidget(table, 1)   # stretch → fill host + scroll

        # Top-N ESI bar chart tab.
        if mpl_available():
            data = core.viz.prepare_esi_bar_chart(result, top_n=20)
            if "error" not in data:
                canvas, toolbar = make_esi_bar_canvas(None, data)
                if canvas is not None:
                    self._viz_tabs_widget.addTab(
                        wrap_scrollable(None, canvas, toolbar), "ESI Chart")
        self._finish_render()

    def _open_hwc(self, index):
        row = index.row()
        if row < 0 or row >= len(getattr(self, "_esi_star_names", [])):
            return
        star = self._esi_star_names[row]
        if not star:
            return
        from gui.panels.catalogs import HwcPanel
        self.window.show_panel(HwcPanel)
        panel = self.window.stack.currentWidget()
        if hasattr(panel, "_name"):
            panel._name.setText(star)
            panel._search()


# ═══════════════════════════════════════════════════════════════════════════
# L3 — Stellar Evolution Timeline
# ═══════════════════════════════════════════════════════════════════════════

class StellarEvolutionPanel(DiagramToggleMixin, ResultPanel):
    """Evolutionary-stage durations + timeline for a star of a given mass."""

    def build_inputs(self):
        self._form_widget = QWidget()
        outer = QVBoxLayout(self._form_widget)
        outer.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._mass = QLineEdit()
        self._mass.setPlaceholderText("0.1 – 20")
        self._mass.returnPressed.connect(self._calculate)
        form.addRow("Stellar Mass (M☉):", self._mass)

        self._age = QLineEdit()
        self._age.setPlaceholderText("optional — marks current stage")
        self._age.returnPressed.connect(self._calculate)
        form.addRow("Current Age (Gyr):", self._age)
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
        self._render_evolution()
        # Trailing stretch packs the results against the top — without it the
        # QVBoxLayout inflates the summary label to fill the panel height (the
        # fixed-height stage table can't absorb the slack).
        self._tables_layout.addStretch(1)

    def _render_evolution(self):
        mass = _safe_float(self._mass.text().strip())
        if mass is None:
            self._tables_layout.addWidget(_err_label("Enter a numeric stellar mass."))
            return
        age = _safe_float(self._age.text().strip())   # blank → None

        result = core.equations.compute_stellar_evolution(mass, age)
        if "error" in result:
            self._tables_layout.addWidget(_err_label(result["error"]))
            return

        # Summary line.
        low = result.get("low_mass")
        total_txt = "> 13.8 Gyr" if low else f"{result['total_gyr']:.3f} Gyr"
        ms_txt    = "> 13.8 Gyr" if low else f"{result['ms_end_gyr']:.3f} Gyr"
        summary = f"<b>Total lifetime:</b> {total_txt} &nbsp;·&nbsp; <b>MS lifetime:</b> {ms_txt}"
        if result.get("current_stage"):
            summary += f" &nbsp;·&nbsp; <b>Current stage:</b> {result['current_stage']}"
        self._tables_layout.addWidget(QLabel(summary))
        if result.get("high_mass"):
            self._tables_layout.addWidget(_note_label(
                "M > 8 M☉ — ends as a supergiant → supernova in a few Myr."))
        if low:
            self._tables_layout.addWidget(_note_label(
                "M < 0.8 M☉ — main-sequence lifetime exceeds the age of the universe; "
                "post-MS stages are not yet reachable."))

        headers = ["Stage", "Start (Gyr)", "End (Gyr)", "Duration (Gyr)"]
        rows = []
        for s in result["stages"]:
            end = "> 13.8" if (low and s["name"] == "Main Sequence") else _f(s["end_gyr"], 3)
            rows.append([s["name"], _f(s["start_gyr"], 3), end, _f(s["duration_gyr"], 3)])
        stage_table = self.make_table(headers, rows)
        _fit_table_height(stage_table)
        self._tables_layout.addWidget(stage_table)

        # Evolution diagram tab.
        if mpl_available():
            data = core.viz.prepare_evolution_diagram(result)
            if "error" not in data:
                canvas, toolbar = make_evolution_canvas(None, data)
                if canvas is not None:
                    self._viz_tabs_widget.addTab(
                        wrap_scrollable(None, canvas, toolbar), "Evolution Diagram")

        self._finish_render()


# ── small widget helpers ─────────────────────────────────────────────────────

def _err_label(msg):
    lbl = QLabel(msg)
    lbl.setStyleSheet("color: red;")
    lbl.setWordWrap(True)
    return lbl


def _note_label(msg):
    lbl = QLabel(msg)
    lbl.setStyleSheet("color: #777;")
    lbl.setWordWrap(True)
    return lbl


def _wrap_layout(layout):
    w = QWidget()
    w.setLayout(layout)
    return w


def _yn(v):
    s = str(v).strip() if v is not None else ""
    if s == "1":
        return "Yes"
    if s == "0":
        return "No"
    return "N/A"
