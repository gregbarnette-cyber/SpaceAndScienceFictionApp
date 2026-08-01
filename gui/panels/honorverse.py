# gui/panels/honorverse.py — Options 15, 16, 17: Honorverse reference tables.
# Each option is its own independent panel class so the nav tree opens each
# in its own content area rather than combining them behind tabs.

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QFormLayout, QPushButton,
    QLineEdit, QComboBox, QSlider, QWidget, QScrollArea, QCheckBox,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
from gui.panels.hypatia_tab import fit_table_height
import core.science
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_hyper_bar_canvas, make_hyper_ring_canvas, wrap_scrollable,
)

_FOOTNOTE = (
    "* Merchantmen do not normally use these bands. "
    "This represents the maximum theoretical speed for them if they did.\n"
    "  Q-ships and merchant cruisers with reworked drives and compensators "
    "sometimes can reach these bands."
)


def _speed_str(xc: float, ly_hr: float, note: str = "") -> str:
    """Format an xC speed as 'X (Y ly/hr)[note]'."""
    if xc == 0:
        return "Currently Unattainable"
    s = f"{xc} ({ly_hr:.5f} ly/hr)"
    if note.strip():
        s += note
    return s


def _hyper_ring_tab(data, mode):
    """Class-grouped hyper-limit ring tab: a per-class checkbox row (plus Select
    All / Clear All) over an auto-rebuilt make_hyper_ring_canvas — the
    solvent_zones._ice_ring_tab scaffold.

    Unchecking a class drops it from the dial and rescales to what is left — in
    sector mode the survivors also re-divide the full circle, so a two- or
    three-class view is far more readable than a filtered eight-class one.
    Clearing every class is a valid state: the canvas renders its "No spectral
    classes selected." card.
    """
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)

    row = QWidget()
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(10)
    rl.addWidget(QLabel("Show classes:"))
    boxes = []
    for g in data.get("groups", []):
        cb = QCheckBox(g["label"])
        cb.setChecked(True)
        n = len(g["rows"])
        cb.setToolTip(f"{n} row{'s' if n != 1 else ''}  ·  "
                      f"{g['lo_au']:.2f}–{g['hi_au']:.2f} AU")
        boxes.append((g["key"], cb))
        rl.addWidget(cb)
    rl.addStretch()
    btn_all = QPushButton("Select All")
    btn_none = QPushButton("Clear All")
    rl.addWidget(btn_all)
    rl.addWidget(btn_none)
    lay.addWidget(row)

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
        keys = [k for k, cb in boxes if cb.isChecked()]
        canvas, toolbar = make_hyper_ring_canvas(None, data, mode=mode, classes=keys)
        if canvas is not None:
            hlay.addWidget(toolbar)
            hlay.addWidget(canvas)

    def _set_all(state):
        # Signals are blocked during the bulk set so the canvas is rebuilt ONCE
        # at the end rather than once per checkbox (eight full redraws).
        for _k, cb in boxes:
            cb.blockSignals(True)
            cb.setChecked(state)
            cb.blockSignals(False)
        _rebuild()

    for _k, cb in boxes:
        cb.toggled.connect(lambda _checked: _rebuild())
    btn_all.clicked.connect(lambda: _set_all(True))
    btn_none.clicked.connect(lambda: _set_all(False))
    _rebuild()
    return w


class HonorverseHyperPanel(DiagramToggleMixin, ResultPanel):
    """Option 14 — Honorverse Hyper Limits by Spectral Class.

    Phase O · O10a adds a "Hyper Limits" bar-chart viz tab (LM, secondary AU
    axis, coloured by class) behind a Show Diagrams toggle. The table is unchanged.
    """

    def build_inputs(self):
        form_widget = QWidget()
        row = QHBoxLayout(form_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        row.addWidget(self._show_diagrams_btn)
        row.addStretch()
        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        limits = core.science.compute_honorverse_hyper_limits()
        headers = ["Spectral Class", "Light Minutes", "AUs"]
        rows = [
            [r["spectral_class"], f"{r['lm']:.2f}", f"{r['au']:.4f}"]
            for r in limits
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        self._tables_widget = QWidget()
        tl = QVBoxLayout(self._tables_widget)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(view)
        self._layout.addWidget(self._tables_widget, 1)

        # ── Hyper Limits viz tabs ─────────────────────────────────────────────
        # Tab order is deliberate: the two class-grouped ring diagrams first
        # (ghost is the default view), then the original Phase O O10a 44-bar
        # chart, which stays as-is — it still answers "what is the exact number
        # for K3" better than any ring can.
        self._setup_diagram_view()
        if mpl_available():
            rings = core.viz.prepare_hyper_limit_rings()
            if "error" not in rings:
                self._viz_tabs_widget.addTab(
                    _hyper_ring_tab(rings, "ghost"), "Class Rings")
                self._viz_tabs_widget.addTab(
                    _hyper_ring_tab(rings, "sector"), "Class Sectors")
            data = core.viz.prepare_hyper_limits()
            if "error" not in data:
                canvas, toolbar = make_hyper_bar_canvas(None, data)
                if canvas is not None:
                    self._viz_tabs_widget.addTab(
                        wrap_scrollable(None, canvas, toolbar), "Hyper Limits")
        self._finish_render()
        self._input_count = self._layout.count()


class HonorverseAccelPanel(ResultPanel):
    """Option 16 — Honorverse Acceleration by Mass Table."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        accel = core.science.compute_honorverse_acceleration_table()
        headers = [
            "Ship Mass (tons)",
            "Warship (Normal Space)", "Merchantship (Normal Space)",
            "Warship (Hyper Space)",  "Merchantship (Hyper Space)",
        ]
        rows = [
            [r["mass_range"], r["warship_normal"], r["merchant_normal"],
             r["warship_hyper"], r["merchant_hyper"]]
            for r in accel
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        self._layout.addWidget(view)


class HonorverseSpeedPanel(ResultPanel):
    """Option 17 — Honorverse Effective Speed by Hyper Band (two tables + footnote)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        data = core.science.compute_honorverse_effective_speed()

        # Both tables are sized to their exact content height and stacked inside
        # one scroll area, so neither gets a private scrollbar and neither is
        # padded with dead space by the layout's equal-share stretching.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        scroll.setWidget(content)

        # ── Table 1: Alpha–Iota ───────────────────────────────────────────────
        t1_label = QLabel("Effective Speed by Hyper Band")
        t1_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        body.addWidget(t1_label)

        spd_headers = [
            "Band", "Translation Bleed-Off", "Velocity Multiplier",
            "Warship (xC)", "Merchantship (xC)",
        ]
        spd_rows = [
            [
                b["band"],
                b["bleed_off"],
                str(b["multiplier"]),
                _speed_str(b["warship_xc"],  b["warship_ly_hr"]),
                _speed_str(b["merchant_xc"], b["merchant_ly_hr"], b["merchant_note"]),
            ]
            for b in data["bands"]
        ]
        view1 = self.make_table(spd_headers, spd_rows)
        view1.setSortingEnabled(False)
        fit_table_height(view1)
        body.addWidget(view1)

        # ── Footnote after table 1 ────────────────────────────────────────────
        note1 = QLabel(_FOOTNOTE)
        note1.setWordWrap(True)
        note1.setStyleSheet("font-style: italic; margin-bottom: 8px;")
        body.addWidget(note1)

        # ── Table 2: Alpha–Omega (expanded) ───────────────────────────────────
        t2_label = QLabel("Effective Speed by Hyper Band (Expanded)")
        t2_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        body.addWidget(t2_label)

        exp_headers = [
            "Band", "Translation Bleed-Off", "Velocity Multiplier",
            "Warship (xC)", "Merchantship (xC)",
        ]
        exp_rows = [
            [
                b["band"],
                b["bleed_off"] + ("" if b["bleed_off_canon"] else " †"),
                str(b["multiplier"]),
                _speed_str(b["warship_xc"],  b["warship_ly_hr"]),
                _speed_str(b["merchant_xc"], b["merchant_ly_hr"], b["merchant_note"]),
            ]
            for b in data["expanded_bands"]
        ]
        view2 = self.make_table(exp_headers, exp_rows)
        view2.setSortingEnabled(False)
        fit_table_height(view2)
        body.addWidget(view2)

        # ── Footnote after table 2 ────────────────────────────────────────────
        note2 = QLabel(
            _FOOTNOTE + "\n"
            "† Bleed-off extrapolated from the canon Alpha–Iota decay "
            "(92 × 0.9215^(n−1), ~7.85% per band); canon publishes no value above Iota.")
        note2.setWordWrap(True)
        note2.setStyleSheet("font-style: italic; margin-top: 4px;")
        body.addWidget(note2)

        body.addStretch()
        self._layout.addWidget(scroll)


# ── Phase K — interactive calculators ────────────────────────────────────────

def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


class HonorverseHyperTimePanel(ResultPanel):
    """Phase K1 — Hyper Translation Time across all 24 bands."""

    def build_inputs(self):
        form = QFormLayout()
        self._dist = QLineEdit()
        self._dist.setPlaceholderText("e.g. 11.4")
        form.addRow("Distance (light years):", self._dist)
        self._ship = QComboBox()
        self._ship.addItems(["Warship", "Merchantship"])
        form.addRow("Ship type:", self._ship)
        self._layout.addLayout(form)

        btn = QPushButton("Calculate")
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)
        self._dist.returnPressed.connect(btn.click)
        self._input_count = 2

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._err.setWordWrap(True)
        self._err.hide()
        self._layout.addWidget(self._err)
        self._box = QVBoxLayout()
        # Stretch factor 1 (and no trailing addStretch) so the 24-band table
        # fills the available height instead of being capped at ~15 rows.
        self._layout.addLayout(self._box, 1)

    def _calculate(self):
        self._err.hide()
        _clear_layout(self._box)
        try:
            dist = float(self._dist.text().strip())
        except ValueError:
            self._err.setText("Enter a number for the distance."); self._err.show(); return
        ship = "warship" if self._ship.currentText() == "Warship" else "merchantship"
        r = core.science.compute_hyper_translation_time(dist, ship)
        if "error" in r:
            self._err.setText(r["error"]); self._err.show(); return

        rows = [
            [b["band"] + (" *" if b["note"] else ""),
             f"{b['speed_xc']:g}",
             f"{b['speed_ly_hr']:.5f}" if b["speed_xc"] else "—",
             b["travel_time"]]
            for b in r["bands"]
        ]
        view = self.make_table(
            ["Band", "Speed (×c)", "Speed (ly/hr)", "Travel Time"], rows)
        view.setSortingEnabled(False)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._box.addWidget(view, 1)   # fill available vertical space
        if r["footnote"]:
            note = QLabel(r["footnote"])
            note.setWordWrap(True)
            note.setStyleSheet("font-style: italic; color: #777; margin-top: 4px;")
            self._box.addWidget(note)


class HonorverseImpellerPanel(ResultPanel):
    """Phase K2 — Impeller wedge geometry; results update live with the slider."""

    def build_inputs(self):
        form = QFormLayout()
        self._mass = QLineEdit()
        self._mass.setPlaceholderText("e.g. 350000")
        self._mass.textChanged.connect(self._calculate)
        form.addRow("Ship mass (tons):", self._mass)
        self._ship = QComboBox()
        self._ship.addItems(["Warship", "Merchantship"])
        self._ship.currentIndexChanged.connect(self._calculate)
        form.addRow("Ship type:", self._ship)

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self._pow = QSlider(Qt.Orientation.Horizontal)
        self._pow.setRange(1, 100)
        self._pow.setValue(100)
        self._powval = QLabel("100%")
        self._powval.setMinimumWidth(40)
        self._pow.valueChanged.connect(self._calculate)
        rl.addWidget(self._pow)
        rl.addWidget(self._powval)
        form.addRow("Wedge power:", row)
        self._layout.addLayout(form)
        self._input_count = 1

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._err.hide()
        self._layout.addWidget(self._err)
        self._box = QVBoxLayout()
        self._layout.addLayout(self._box)
        self._layout.addStretch()

    def _calculate(self):
        self._powval.setText(f"{self._pow.value()}%")
        self._err.hide()
        _clear_layout(self._box)
        txt = self._mass.text().strip()
        if not txt:
            return
        try:
            mass = float(txt)
        except ValueError:
            self._err.setText("Enter a number for the ship mass."); self._err.show(); return
        ship = "warship" if self._ship.currentText() == "Warship" else "merchantship"
        r = core.science.compute_impeller_wedge(mass, ship, float(self._pow.value()))
        if "error" in r:
            self._err.setText(r["error"]); self._err.show(); return

        rows = [
            ["Mass Band", r["mass_band"]],
            ["Base Acceleration", f"{r['base_accel_g']:g} g"],
            ["Effective Acceleration", f"{r['effective_accel_g']:.1f} g"],
            ["Max Velocity (normal-space)", f"{r['max_vel_normal_xc']:.4f} c"],
            ["Max Velocity (hyper, at entry)", f"{r['max_vel_hyper_xc']:.4f} c"],
            ["Time to Max Velocity", r["time_to_max_vel"]],
        ]
        view = self.make_table(["Property", "Value"], rows)
        view.setSortingEnabled(False)
        self._box.addWidget(view)
        if r["clamped"]:
            note = QLabel("Mass above the heaviest band (SD) — clamped to it.")
            note.setStyleSheet("font-style: italic; color: #b8860b; margin-top: 4px;")
            self._box.addWidget(note)


class HonorverseMissilePanel(ResultPanel):
    """Phase K3 — Missile intercept (1D head-on)."""

    def build_inputs(self):
        form = QFormLayout()
        self._lv = QLineEdit(); self._lv.setPlaceholderText("e.g. 0.3")
        form.addRow("Launcher velocity (×c):", self._lv)
        self._acc = QLineEdit(); self._acc.setPlaceholderText("e.g. 10000")
        form.addRow("Missile acceleration (G):", self._acc)
        self._dv = QLineEdit(); self._dv.setPlaceholderText("e.g. 0.5")
        form.addRow("Missile delta-v budget (×c):", self._dv)
        self._tv = QLineEdit(); self._tv.setPlaceholderText("− = head-on, e.g. -0.2")
        form.addRow("Target velocity (×c):", self._tv)
        self._rng = QLineEdit(); self._rng.setPlaceholderText("e.g. 8")
        form.addRow("Initial range (light minutes):", self._rng)
        self._layout.addLayout(form)

        btn = QPushButton("Calculate")
        btn.clicked.connect(self._calculate)
        self._layout.addWidget(btn)
        for fld in (self._lv, self._acc, self._dv, self._tv, self._rng):
            fld.returnPressed.connect(btn.click)
        self._input_count = 2

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._err.hide()
        self._layout.addWidget(self._err)
        self._box = QVBoxLayout()
        self._layout.addLayout(self._box)
        self._layout.addStretch()

    def _calculate(self):
        self._err.hide()
        _clear_layout(self._box)
        try:
            lv = float(self._lv.text().strip()); acc = float(self._acc.text().strip())
            dv = float(self._dv.text().strip()); tv = float(self._tv.text().strip())
            rng = float(self._rng.text().strip())
        except ValueError:
            self._err.setText("Enter a number in each field."); self._err.show(); return
        r = core.calculators.compute_missile_intercept(lv, acc, dv, tv, rng)
        if "error" in r:
            self._err.setText(r["error"]); self._err.show(); return

        verdict = QLabel()
        if r["intercepts"]:
            verdict.setText(f"✓ Intercept — {r['intercept_phase']} phase, "
                            f"in {r['time_to_impact_str']}")
            verdict.setStyleSheet("color: #2e8b57; font-weight: bold; font-size: 14px;")
        else:
            verdict.setText("✗ No intercept (missile cannot close)")
            verdict.setStyleSheet("color: #b03030; font-weight: bold; font-size: 14px;")
        self._box.addWidget(verdict)

        rows = [
            ["Burnout velocity", f"{r['v_burnout_xc']:.4f} c"],
            ["Closing velocity (post-burn)", f"{r['v_close_xc']:.4f} c"],
            ["Burn duration", f"{core.calculators.format_travel_time(r['burn_duration_s'] / 3600.0)} "
                              f"({r['burn_duration_s']:.0f} s)"],
            ["Range at burnout", f"{r['range_at_burnout_lm']:.4f} LM"],
            ["Time to impact", r["time_to_impact_str"] or "—"],
            ["Intercept phase", r["intercept_phase"] or "—"],
        ]
        view = self.make_table(["Property", "Value"], rows)
        view.setSortingEnabled(False)
        self._box.addWidget(view)
