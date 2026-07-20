# gui/panels/generator.py — Phase R1: procedural System Generator (GUI).
#
# SystemGeneratorPanel is a thin presentation layer over core.generate.generate_system
# (pure, deterministic — same seed (+ same anchor) → identical output). It adds NO new
# core code; it only collects inputs, calls the verified generator, and renders the
# result into the existing diagrams (make_orbits_canvas / make_hz_canvas) + a planet
# table whose Source column distinguishes observed (NASA/HWC) from synthetic bodies.
#
# Two modes mirror the engine:
#   • Synthetic (anchor blank) — pure/offline → run synchronously (instant).
#   • Anchor on a real star    — networked (SIMBAD/NASA/HWC) → run_in_background.
#
# The standalone "Send to Dossier" button stays present-but-disabled: the generated-
# system dossier renderer now exists (Phase S `core.report.build_generated_dossier`),
# but the supported export path is "Add to project" → the Projects panel's Export
# Project Dossier (which fans build_generated_dossier over the members). A one-click
# single-system file export from here is an optional later add. "Copy JSON" + "Add to
# project" cover the immediate needs.

import json
import math
import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QCheckBox, QRadioButton, QButtonGroup, QSpinBox, QSizePolicy,
    QApplication, QComboBox, QFrame,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

# Phase R2 constraint vocabulary (the GUI builder emits the spec JSON directly).
_CONSTRAINT_TYPES = ["planet_at_location", "trojan", "moon", "resonance",
                     "habitable_world", "alt_solvent_world", "architecture"]
_BODY_TYPES = ["terrestrial", "ice", "gas", "super_jovian"]
_LOC_KINDS = ["in_hz", "at", "between", "interior_to", "exterior_to", "in_zone"]

# Per-verdict colours (background, foreground) for the feasibility cards/banner.
_VERDICT_COLORS = {
    "feasible":      ("#e7f6ec", "#aedcbd", "#155f33"),
    "infeasible":    ("#fbe9e9", "#e3b5b5", "#9b2226"),
    "marginal":      ("#fff4d6", "#e6c869", "#8a5a00"),
    "not_evaluated": ("#eeeeee", "#cccccc", "#666666"),
}

from gui.panels.base import ResultPanel, DiagramToggleMixin
import core.generate
import core.research_priors
import core.viz
from gui.visualizations.plot_helpers import (
    mpl_available, make_orbits_canvas, make_hz_canvas,
)
from gui.panels.diagram_tabs import _hz_toggle_tab

# Observed vs synthetic styling (matches the approved mockup legend).
_OBSERVED_COLOR = "#1f7a3d"     # green — observed (NASA / HWC)
_SYNTH_COLOR    = "#2b6cb0"     # blue  — synthetic (generated)
_OBS_ROW_BG     = "#f3faf5"     # faint green row tint for observed planets


def _fmt(v, nd=2):
    """Format a numeric value to nd decimals, or '—' for None."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}"
    except (ValueError, TypeError):
        return str(v)


def _orbit_dicts(planets):
    """Build make_orbits_canvas orbit dicts from generated planet rows, coloured by
    source (observed = green, synthetic = blue). Returns (orbits, max_au)."""
    N = 361
    thetas = [2.0 * math.pi * i / (N - 1) for i in range(N)]
    orbits, max_au = [], 0.0
    for p in planets:
        a = p.get("a_au")
        if a is None or a <= 0:
            continue
        try:
            e = float(p.get("ecc") or 0.0)
        except (ValueError, TypeError):
            e = 0.0
        e = min(max(e, 0.0), 0.99)
        b = a * math.sqrt(1.0 - e * e)
        ae = a * e
        color = _OBSERVED_COLOR if p.get("source") == "observed" else _SYNTH_COLOR
        orbits.append({
            "name":  p.get("name", "?"),
            "sma":   a,
            "peri":  a * (1.0 - e),
            "apo":   a * (1.0 + e),
            "ecc":   e,
            "x_pts": [a * math.cos(t) - ae for t in thetas],
            "y_pts": [b * math.sin(t) for t in thetas],
            "color": color,
        })
        max_au = max(max_au, a * (1.0 + e))
    return orbits, max_au


def _hz_label(planet):
    """In-HZ display token: 'cons.' / 'opt.' / '—'."""
    if not planet.get("in_hz"):
        return "—"
    return {"conservative": "cons.", "optimistic": "opt."}.get(
        planet.get("hz_class"), "yes")


def _notes_for(planet):
    """Compact per-planet note: atmosphere + moon count (synthetic giants)."""
    bits = []
    atm = planet.get("atmosphere")
    if atm:
        bits.append(atm)
    moons = planet.get("moons") or []
    if moons:
        bits.append(f"{len(moons)} moon{'s' if len(moons) != 1 else ''}")
    return "; ".join(bits) if bits else "—"


class _ConstraintRow(QWidget):
    """One structured constraint-builder row (Phase R2). A type dropdown drives a
    set of dependent fields; ``to_spec()`` emits the constraint dict the engine
    consumes (the GUI never builds the DSL string — it produces the spec directly)."""

    def __init__(self, on_remove):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        self._type = QComboBox()
        self._type.addItems(_CONSTRAINT_TYPES)
        self._type.setMaximumWidth(160)
        self._type.currentTextChanged.connect(self._rebuild)
        lay.addWidget(self._type)
        self._fields = QWidget()
        self._fl = QHBoxLayout(self._fields)
        self._fl.setContentsMargins(0, 0, 0, 0)
        self._fl.setSpacing(6)
        lay.addWidget(self._fields, 1)
        rm = QPushButton("✕")
        rm.setMaximumWidth(28)
        rm.setToolTip("Remove this feature")
        rm.clicked.connect(lambda: on_remove(self))
        lay.addWidget(rm)
        self._w = {}
        self._rebuild(self._type.currentText())

    # field factories
    def _combo(self, items, width=120):
        c = QComboBox(); c.addItems(items); c.setMaximumWidth(width); return c

    def _edit(self, placeholder, text="", width=90):
        e = QLineEdit(text); e.setPlaceholderText(placeholder); e.setMaximumWidth(width); return e

    def _add(self, widget, label=None):
        if label:
            lb = QLabel(label); lb.setStyleSheet("color:#666;font-size:11px;")
            self._fl.addWidget(lb)
        self._fl.addWidget(widget)

    def _rebuild(self, ctype):
        while self._fl.count():
            it = self._fl.takeAt(0); w = it.widget()
            if w:
                w.deleteLater()
        self._w = {}
        if ctype == "planet_at_location":
            self._w["body"] = self._combo(_BODY_TYPES); self._add(self._w["body"])
            self._w["mass"] = self._edit("M⊕", "1.0", 70); self._add(self._w["mass"], "mass")
            self._w["loc"] = self._combo(_LOC_KINDS, 120); self._add(self._w["loc"], "loc")
            self._w["ref_a"] = self._edit("ref / AU", "", 80); self._add(self._w["ref_a"])
            self._w["ref_b"] = self._edit("…and ref", "", 80); self._add(self._w["ref_b"])
        elif ctype == "trojan":
            self._w["body"] = self._combo(_BODY_TYPES); self._add(self._w["body"])
            self._w["host"] = self._edit("host", "giant_in_hz", 150); self._add(self._w["host"], "host")
            self._w["point"] = self._combo(["L4", "L5"], 60); self._add(self._w["point"], "pt")
        elif ctype == "moon":
            self._w["host"] = self._edit("host", "super_jovian_in_hz", 170); self._add(self._w["host"], "host")
            self._w["mass"] = self._edit("M⊕", "1.0", 70); self._add(self._w["mass"], "mass")
            self._w["terra"] = QCheckBox("terraformable"); self._add(self._w["terra"])
        elif ctype == "resonance":
            self._w["a"] = self._edit("body A", "b", 70); self._add(self._w["a"], "bodies")
            self._w["b"] = self._edit("body B", "c", 70); self._add(self._w["b"])
            self._w["ratio"] = self._edit("2:1", "2:1", 60); self._add(self._w["ratio"], "ratio")
        elif ctype == "habitable_world":
            self._w["hz"] = self._combo(["cons", "opt"], 70); self._add(self._w["hz"], "HZ")
            self._w["min"] = self._edit("count", "1", 60); self._add(self._w["min"], "≥")
        elif ctype == "alt_solvent_world":
            self._w["solvent"] = self._combo(
                ["water", "ammonia", "methane", "ethane", "sulfuric_acid", "nitrogen"], 130)
            self._add(self._w["solvent"], "solvent")
        elif ctype == "architecture":
            self._w["rule"] = self._combo(["giant_beyond_snow_line", "no_hot_jupiter"], 190)
            self._add(self._w["rule"], "rule")
        self._fl.addStretch()

    def _flt(self, key, default=None):
        try:
            return float(self._w[key].text().strip())
        except (ValueError, KeyError, AttributeError):
            return default

    def to_spec(self):
        t = self._type.currentText()
        if t == "planet_at_location":
            kind = self._w["loc"].currentText()
            ra = self._w["ref_a"].text().strip()
            rb = self._w["ref_b"].text().strip()
            if kind == "at":
                loc = {"kind": "at", "au": self._flt("ref_a", 1.0)}
            elif kind == "between":
                loc = {"kind": "between", "ref_a": ra, "ref_b": rb}
            elif kind in ("interior_to", "exterior_to"):
                loc = {"kind": kind, "ref": ra}
            elif kind == "in_zone":
                loc = {"kind": "in_zone", "zone": ra or "hz"}
            else:
                loc = {"kind": "in_hz"}
            return {"type": t, "planet_type": self._w["body"].currentText(),
                    "mass_earth": self._flt("mass", 1.0), "location": loc}
        if t == "trojan":
            return {"type": t, "companion_type": self._w["body"].currentText(),
                    "host": self._w["host"].text().strip(), "point": self._w["point"].currentText()}
        if t == "moon":
            out = {"type": t, "host": self._w["host"].text().strip()}
            m = self._flt("mass")
            if m is not None:
                out["mass_earth"] = m
            if self._w["terra"].isChecked():
                out["terraformable"] = True
            return out
        if t == "resonance":
            return {"type": t, "bodies": [self._w["a"].text().strip(), self._w["b"].text().strip()],
                    "ratio": self._w["ratio"].text().strip() or "2:1"}
        if t == "habitable_world":
            out = {"type": t, "hz": self._w["hz"].currentText()}
            try:
                out["min_count"] = int(self._w["min"].text().strip())
            except ValueError:
                pass
            return out
        if t == "alt_solvent_world":
            return {"type": t, "solvent": self._w["solvent"].currentText()}
        if t == "architecture":
            return {"type": t, "rule": self._w["rule"].currentText()}
        return {"type": t}


class SystemGeneratorPanel(DiagramToggleMixin, ResultPanel):
    """Deterministic procedural system generator (Phase R1).

    Inputs: seed (+ Randomize), Synthetic / Anchor-on-real-star mode, anchor star,
    spectral-class chips (synthetic only), planet count (or Auto), require-habitable,
    and a DEFAULTS research-priors pill. Renders a Planet Table (Source-coloured) plus
    Orbit Diagram + HZ Ring viz tabs, with a Copy JSON action.
    """

    # ── inputs ──────────────────────────────────────────────────────────────────

    def build_inputs(self):
        self._last_result = None
        self._constraint_rows = []
        self._active_specs = []
        self._last_params = None
        self._apply_depth = 0

        form_widget = QWidget()
        form = QFormLayout(form_widget)

        # Seed + Randomize.
        seed_w = QWidget()
        seed_row = QHBoxLayout(seed_w)
        seed_row.setContentsMargins(0, 0, 0, 0)
        self._seed = QLineEdit("4173")
        self._seed.setMaximumWidth(120)
        self._seed.returnPressed.connect(self._generate)
        self._rand_btn = QPushButton("🎲 Randomize")
        self._rand_btn.clicked.connect(self._randomize)
        seed_row.addWidget(self._seed)
        seed_row.addWidget(self._rand_btn)
        hint = QLabel("the seed is the system's identity")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        seed_row.addWidget(hint)
        seed_row.addStretch()
        form.addRow("Seed:", seed_w)

        # Mode radios.
        mode_w = QWidget()
        mode_row = QHBoxLayout(mode_w)
        mode_row.setContentsMargins(0, 0, 0, 0)
        self._mode_group = QButtonGroup(self)
        self._rb_synth = QRadioButton("Synthetic (offline)")
        self._rb_anchor = QRadioButton("Anchor on real star")
        self._rb_synth.setChecked(True)
        self._mode_group.addButton(self._rb_synth)
        self._mode_group.addButton(self._rb_anchor)
        self._rb_synth.toggled.connect(self._update_mode)
        mode_row.addWidget(self._rb_synth)
        mode_row.addWidget(self._rb_anchor)
        mode_row.addStretch()
        form.addRow("Mode:", mode_w)

        # Anchor star.
        self._anchor = QLineEdit()
        self._anchor.setPlaceholderText("e.g. Tau Ceti — pulls real specs + known planets (network)")
        self._anchor.returnPressed.connect(self._generate)
        form.addRow("Anchor star:", self._anchor)

        # Spectral-class chips + subtype (synthetic only).
        sc_w = QWidget()
        sc_row = QHBoxLayout(sc_w)
        sc_row.setContentsMargins(0, 0, 0, 0)
        sc_row.setSpacing(4)
        self._chips = {}
        for letter in "OBAFGKM":
            chip = QPushButton(letter)
            chip.setCheckable(True)
            chip.setMaximumWidth(34)
            chip.clicked.connect(lambda _checked, L=letter: self._on_chip(L))
            self._chips[letter] = chip
            sc_row.addWidget(chip)
        self._subtype = QLineEdit()
        self._subtype.setPlaceholderText("subtype e.g. 2V")
        self._subtype.setMaximumWidth(110)
        sc_row.addWidget(self._subtype)
        sc_hint = QLabel("(synthetic only)")
        sc_hint.setStyleSheet("color: #666; font-size: 11px;")
        sc_row.addWidget(sc_hint)
        sc_row.addStretch()
        form.addRow("Spectral class:", sc_w)

        # Planet count (Auto = sample) + require-habitable + priors pill.
        pl_w = QWidget()
        pl_row = QHBoxLayout(pl_w)
        pl_row.setContentsMargins(0, 0, 0, 0)
        self._planets = QSpinBox()
        self._planets.setRange(-1, core.generate._MAX_N_PLANETS)
        self._planets.setSpecialValueText("Auto (sample)")
        self._planets.setValue(5)
        self._planets.setMaximumWidth(110)
        pl_row.addWidget(self._planets)
        self._req_hab = QCheckBox("require habitable")
        pl_row.addWidget(self._req_hab)
        self._nbody_chk = QCheckBox("N-body confirm (marginal)")
        self._nbody_chk.setToolTip("Run a short deterministic N-body integration to resolve "
                                   "marginal packing verdicts (opt-in).")
        pl_row.addWidget(self._nbody_chk)
        priors_lbl = QLabel("Research policy:")
        priors_lbl.setStyleSheet("color: #444; margin-left: 10px;")
        pl_row.addWidget(priors_lbl)
        self._policy = QComboBox()
        self._policy.addItems(["permissive", "strict"])
        self._policy.setMaximumWidth(120)
        self._policy.setToolTip(
            "permissive: literature-informed DefaultPriors (grounding=default-extrapolation).\n"
            "strict: research-calibrated priors from an ingested dataset (Import Research "
            "Priors utility); with no dataset loaded, generation returns a curated error.")
        self._policy.currentTextChanged.connect(self._update_policy_pill)
        pl_row.addWidget(self._policy)
        self._priors_pill = QLabel("DEFAULTS")
        pl_row.addWidget(self._priors_pill)
        pl_row.addStretch()
        form.addRow("Planets:", pl_w)
        self._update_policy_pill()

        # Desired features (constraints) — optional; empty → plain generation.
        cons_w = QWidget()
        cons_l = QVBoxLayout(cons_w)
        cons_l.setContentsMargins(0, 0, 0, 0)
        cons_l.setSpacing(2)
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("+ Add feature")
        add_btn.clicked.connect(self._add_constraint_row)
        hdr.addWidget(add_btn)
        chint = QLabel("optional — describe the system you want; empty → plain generation")
        chint.setStyleSheet("color: #666; font-size: 11px;")
        hdr.addWidget(chint)
        hdr.addStretch()
        cons_l.addLayout(hdr)
        self._constraints_box = QVBoxLayout()
        self._constraints_box.setContentsMargins(0, 0, 0, 0)
        self._constraints_box.setSpacing(2)
        cons_l.addLayout(self._constraints_box)
        form.addRow("Desired features:", cons_w)

        # Action buttons.
        btn_w = QWidget()
        btn_row = QHBoxLayout(btn_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Generate / Check Feasibility")
        self.run_btn.clicked.connect(self._generate)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        self._copy_btn = QPushButton("⭳ Copy JSON")
        self._copy_btn.clicked.connect(self._copy_json)
        self._copy_btn.setEnabled(False)
        self._dossier_btn = QPushButton("📄 Send to Dossier")
        self._dossier_btn.setEnabled(False)
        self._dossier_btn.setToolTip("To export this system as a dossier: use ➕ Add to "
                                     "project, then Export Project Dossier in the Projects "
                                     "panel (a single-system one-click export is a later add).")
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addWidget(self._copy_btn)
        self._add_proj_btn = QPushButton("➕ Add to project")
        self._add_proj_btn.setEnabled(False)
        self._add_proj_btn.setToolTip("Add this generated system to a project "
                                      "workspace (stores its spec for byte-identical reopen).")
        self._add_proj_btn.clicked.connect(self._add_to_project)
        btn_row.addWidget(self._add_proj_btn)
        btn_row.addWidget(self._dossier_btn)
        btn_row.addStretch()
        form.addRow("", btn_w)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()
        self._update_mode()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()
        self._input_count = self._layout.count()

    # ── input helpers ─────────────────────────────────────────────────────────

    def _update_mode(self, *_):
        """Enable/disable inputs by mode: anchor field active only when anchored;
        spectral chips + subtype active only when synthetic."""
        anchored = self._rb_anchor.isChecked()
        self._anchor.setEnabled(anchored)
        for chip in self._chips.values():
            chip.setEnabled(not anchored)
        self._subtype.setEnabled(not anchored)

    def _on_chip(self, letter):
        """Single-select chip behaviour: checking one unchecks the others."""
        if self._chips[letter].isChecked():
            for other, chip in self._chips.items():
                if other != letter:
                    chip.setChecked(False)

    def _selected_class(self):
        for letter, chip in self._chips.items():
            if chip.isChecked():
                return letter
        return None

    def _build_spectral_class(self):
        """Combine the selected chip + subtype into a 'K2V'-style string, or None."""
        letter = self._selected_class()
        if not letter:
            return None
        sub = self._subtype.text().strip()
        return f"{letter}{sub}" if sub else letter

    def _randomize(self):
        self._seed.setText(str(random.randint(0, 2 ** 31 - 1)))

    def _clear_tables(self):
        lay = self._tables_layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_msg(self, msg, error=False):
        self._prepare_render()
        self._clear_tables()
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        if error:
            lbl.setStyleSheet("color: red;")
        self._tables_layout.addWidget(lbl)

    # ── constraint builder ──────────────────────────────────────────────────────

    def _add_constraint_row(self):
        row = _ConstraintRow(self._remove_constraint_row)
        self._constraint_rows.append(row)
        self._constraints_box.addWidget(row)
        return row

    def _remove_constraint_row(self, row):
        if row in self._constraint_rows:
            self._constraint_rows.remove(row)
        self._constraints_box.removeWidget(row)
        row.deleteLater()

    def _collect_specs(self):
        return [r.to_spec() for r in self._constraint_rows]

    # ── generate ────────────────────────────────────────────────────────────────

    def _update_policy_pill(self, *_):
        """Reflect the selected research policy + ingested-dataset status in the pill."""
        if self._policy.currentText() == "strict":
            st = core.research_priors.get_research_priors_status()
            if st.get("loaded"):
                self._priors_pill.setText(f"RESEARCH · {st['dataset_version']}")
                style = ("background:#e6effa;color:#1a4e84;border:1px solid #a9c6e6;")
            else:
                self._priors_pill.setText("RESEARCH · none ingested")
                style = ("background:#fbe9e9;color:#9b2226;border:1px solid #e3b5b5;")
        else:
            self._priors_pill.setText("DEFAULTS")
            style = ("background:#fff4d6;color:#9a6700;border:1px solid #e6c869;")
        self._priors_pill.setStyleSheet(
            style + "border-radius:8px;padding:1px 7px;font-weight:600;font-size:11px;")

    def _generate(self):
        raw = self._seed.text().strip()
        try:
            seed = int(raw)
        except ValueError:
            self._show_msg("Seed must be an integer.", error=True)
            return

        n = self._planets.value()
        anchored = self._rb_anchor.isChecked()
        anchor = self._anchor.text().strip() if anchored else None
        if anchored and not anchor:
            self._show_msg("Enter an anchor star name, or switch to Synthetic mode.", error=True)
            return

        # Snapshot the generation parameters so an applied alternative can re-run.
        self._last_params = {
            "mode": "anchor" if anchored else "synthetic",
            "seed": seed, "anchor": anchor,
            "spectral_class": self._build_spectral_class(),
            "n_planets": None if n < 0 else n,
            "require": self._req_hab.isChecked(),
            "nbody": self._nbody_chk.isChecked(),
            "research_policy": self._policy.currentText(),
        }
        self._apply_depth = 0
        self._run_specs(self._collect_specs())

    def _run_specs(self, specs):
        """Invoke the engine for the given constraint specs (+ snapshotted params).
        Zero specs → the R1 generation path (constraints=None, byte-identical)."""
        self._active_specs = specs
        p = self._last_params
        cons = specs or None
        policy = p.get("research_policy", "permissive")
        if p["mode"] == "anchor":
            self._prepare_render()
            self._clear_tables()
            self._copy_btn.setEnabled(False)
            self._tables_layout.addWidget(QLabel(f"Resolving {p['anchor']} (network)…"))
            self.run_in_background(
                core.generate.generate_system, p["seed"],
                anchor_star=p["anchor"], n_planets=p["n_planets"],
                require_habitable=p["require"], constraints=cons, nbody=p["nbody"],
                research_policy=policy,
                on_result=self._render,
            )
        else:
            result = core.generate.generate_system(
                p["seed"], spectral_class=p["spectral_class"], n_planets=p["n_planets"],
                require_habitable=p["require"], constraints=cons, nbody=p["nbody"],
                research_policy=policy)
            self._render(result)

    def _apply_alternative(self, idx, patch, label):
        """Clickable-apply (D6): merge an alternative's spec_patch into its
        constraint and re-run deterministically (bounded re-apply depth)."""
        if self._apply_depth >= 6:
            self.set_status("Alternative re-apply limit reached — press Generate to reset.")
            return
        if not (0 <= idx < len(self._active_specs)):
            return
        self._apply_depth += 1
        specs = list(self._active_specs)
        specs[idx] = {**specs[idx], **(patch or {})}
        self.set_status(f"Applied alternative: {label}")
        self._run_specs(specs)

    # ── render ───────────────────────────────────────────────────────────────────

    def _render(self, result):
        self._prepare_render()
        self._clear_tables()
        self._copy_btn.setEnabled(False)
        self._add_proj_btn.setEnabled(False)

        if not result or "error" in result:
            msg = result.get("error", "Unknown error") if result else "No result"
            lbl = QLabel(msg)
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            self.set_status(f"Error: {msg}")
            return

        self._last_result = result
        star = result["star"]
        planets = result["planets"]
        n_obs = sum(1 for p in planets if p.get("source") == "observed")
        n_syn = len(planets) - n_obs
        is_feas = "constraints" in result and "feasible" in result

        # Banner (feasibility) or verdict line (plain generation).
        if is_feas:
            self._render_feasibility_banner(result, n_obs, n_syn)
        else:
            if result.get("mode") == "real_anchor":
                verdict = (f"✓ Generated <b>{star['name']}</b> ({star.get('spectral_class') or '—'}) — "
                           f"{n_obs} observed + {n_syn} synthetic planet(s).")
            else:
                verdict = (f"✓ Generated <b>{star['name']}</b> ({star.get('spectral_class') or '—'}) — "
                           f"{len(planets)} synthetic planet(s), seed {result.get('seed')}.")
            vlbl = QLabel(verdict)
            vlbl.setWordWrap(True)
            vlbl.setStyleSheet("background: #e7f6ec; border: 1px solid #aedcbd; color: #155f33;"
                               "border-radius: 4px; padding: 7px 10px;")
            self._tables_layout.addWidget(vlbl)

        # Star card.
        hz = f"{_fmt(star.get('hz_inner_au'))} – {_fmt(star.get('hz_outer_au'))} AU"
        card = (f"<b>Spectral type:</b> {star.get('spectral_class') or '—'} "
                f"({star.get('source')})&nbsp;&nbsp; "
                f"<b>T<sub>eff</sub>:</b> {_fmt(star.get('teff'), 0)} K&nbsp;&nbsp; "
                f"<b>Mass/Radius:</b> {_fmt(star.get('mass_solar'))} / "
                f"{_fmt(star.get('radius_solar'))} ☉&nbsp;&nbsp; "
                f"<b>Luminosity:</b> {_fmt(star.get('luminosity'), 4)} ☉&nbsp;&nbsp; "
                f"<b>HZ:</b> {hz}&nbsp;&nbsp; "
                f"<b>Snow line:</b> {_fmt(star.get('snow_line_au'))} AU")
        clbl = QLabel(card)
        clbl.setWordWrap(True)
        clbl.setStyleSheet("background: #f7f9fc; border: 1px solid #e2e2e2;"
                           "border-radius: 4px; padding: 8px 10px;")
        self._tables_layout.addWidget(clbl)

        # Per-constraint four-layer cards (feasibility mode).
        if is_feas:
            for idx, con in enumerate(result["constraints"]):
                self._tables_layout.addWidget(self._make_constraint_card(con, idx))

        # Planet table.
        self._planet_table = self._make_planet_table(planets)
        self._tables_layout.addWidget(self._planet_table, 1)

        # Legend.
        legend = QLabel(
            f"<span style='color:{_OBSERVED_COLOR};font-weight:600'>■ observed</span> "
            f"(NASA / HWC) &nbsp;&nbsp; "
            f"<span style='color:{_SYNTH_COLOR};font-weight:600'>■ synthetic</span> "
            f"(generated, seed {result.get('seed')})")
        legend.setStyleSheet("font-size: 11px;")
        self._tables_layout.addWidget(legend)

        # Warnings (multiplicity / no-observed-planets / etc.).
        warns = result.get("warnings") or []
        for w in warns:
            wl = QLabel("⚠ " + w)
            wl.setWordWrap(True)
            wl.setStyleSheet("color: #9a6700; font-size: 11.5px;")
            self._tables_layout.addWidget(wl)

        # Viz tabs.
        if mpl_available():
            self._add_orbit_tab(result)
            self._add_hz_tab(star, result.get("planets"))

        self._copy_btn.setEnabled(True)
        self._add_proj_btn.setEnabled(True)
        self._finish_render()

        bits = []
        if warns:
            bits.append(f"{len(warns)} warning(s)")
        self.set_status("Generated · " + (", ".join(bits) if bits else "no warnings"))

    # ── feasibility rendering ─────────────────────────────────────────────────────

    def _render_feasibility_banner(self, result, n_obs, n_syn):
        verdicts = [c["verdict"] for c in result["constraints"]]
        if any(v == "infeasible" for v in verdicts):
            icon, txt = "✗", f"{verdicts.count('infeasible')} of {len(verdicts)} constraint(s) infeasible"
            bg, bd, fg = _VERDICT_COLORS["infeasible"]
        elif any(v == "marginal" for v in verdicts):
            icon, txt = "◐", "marginal — some constraints need confirmation"
            bg, bd, fg = _VERDICT_COLORS["marginal"]
        elif any(v == "feasible" for v in verdicts):
            icon, txt = "✓", "all evaluated constraints feasible"
            bg, bd, fg = _VERDICT_COLORS["feasible"]
        else:
            icon, txt = "•", "no constraints evaluated"
            bg, bd, fg = _VERDICT_COLORS["not_evaluated"]
        star = result["star"]
        lbl = QLabel(f"{icon} <b>{star['name']}</b> — {txt}. "
                     f"({n_obs} observed + {n_syn} synthetic bodies.)")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"background:{bg};border:1px solid {bd};color:{fg};"
                          "border-radius:4px;padding:7px 10px;font-weight:600;")
        self._tables_layout.addWidget(lbl)

    def _wrap_label(self, html):
        lb = QLabel(html)
        lb.setWordWrap(True)
        lb.setTextFormat(Qt.TextFormat.RichText)
        lb.setStyleSheet("font-size: 12px;")
        return lb

    def _make_constraint_card(self, c, idx):
        """A four-layer card for one constraint: verdict chip + Layer 1–4. Layer-4
        alternatives are clickable buttons that apply their spec_patch and re-run."""
        verdict = c.get("verdict", "not_evaluated")
        bg, _bd, fg = _VERDICT_COLORS.get(verdict, _VERDICT_COLORS["not_evaluated"])
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #c8c8c8; border-radius: 5px; }")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 6, 8, 8)
        fl.setSpacing(3)

        hdr = QLabel(f"<span style='background:{bg};color:{fg};border-radius:8px;"
                     f"padding:1px 8px;font-weight:700'>{verdict}</span>&nbsp;&nbsp;"
                     f"<b>{c.get('id')}</b> · {c.get('type')}")
        hdr.setTextFormat(Qt.TextFormat.RichText)
        fl.addWidget(hdr)

        l1 = c.get("layer1") or {}
        if l1.get("reason"):
            fl.addWidget(self._wrap_label("① " + l1["reason"]))

        l2 = c.get("layer2") or {}
        if l2.get("mechanism") or l2.get("checked"):
            checked = ", ".join(l2.get("checked") or [])
            fl.addWidget(self._wrap_label(
                f"② mechanism: <b>{l2.get('mechanism') or 'none'}</b>"
                + (f" &nbsp;·&nbsp; checked: {checked}" if checked else "")))

        hyps = (c.get("layer3") or {}).get("hypotheses") or []
        if hyps:
            parts = [(f"{h['pathway']} <i>({h['plausibility']})</i> "
                      f"<span style='background:#fff4d6;color:#9a6700;border:1px solid #e6c869;"
                      f"border-radius:6px;padding:0 4px;font-size:10px'>{h['grounding']}</span>")
                     for h in hyps]
            fl.addWidget(self._wrap_label("③ origin: " + "; ".join(parts)))

        alts = (c.get("layer4") or {}).get("alternatives") or []
        if alts:
            alt_w = QWidget()
            alt_l = QHBoxLayout(alt_w)
            alt_l.setContentsMargins(0, 0, 0, 0)
            alt_l.setSpacing(6)
            lab = QLabel("④ try:")
            lab.setStyleSheet("font-size: 12px;")
            alt_l.addWidget(lab)
            for a in alts:
                btn = QPushButton(a.get("change", "…"))
                btn.setToolTip(f"→ {a.get('result', '')}  (click to apply and re-check)")
                btn.setStyleSheet("text-align:left; padding:2px 8px;")
                btn.clicked.connect(
                    lambda _checked=False, i=idx, patch=a.get("spec_patch") or {},
                    label=a.get("change", ""): self._apply_alternative(i, patch, label))
                alt_l.addWidget(btn)
            alt_l.addStretch()
            fl.addWidget(alt_w)
        return frame

    def _make_planet_table(self, planets):
        """QTableView with a Source column; observed rows tinted, Source cell coloured.
        Built from a QStandardItemModel so per-row backgrounds survive (insertion order
        preserved — sorting disabled since rows are ordered by SMA)."""
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        from PySide6.QtWidgets import QTableView

        headers = ["Planet", "SMA (AU)", "Mass (M⊕)", "Radius (R⊕)", "Ecc",
                   "Type", "T_eq (K)", "In HZ", "Notes", "Source"]
        model = QStandardItemModel(len(planets), len(headers))
        model.setHorizontalHeaderLabels(headers)
        for r, p in enumerate(planets):
            observed = p.get("source") == "observed"
            cells = [
                p.get("name", "?"),
                _fmt(p.get("a_au"), 4),
                _fmt(p.get("mass_earth"), 3),
                _fmt(p.get("radius_earth"), 3),
                _fmt(p.get("ecc"), 3),
                p.get("type") or "—",
                _fmt(p.get("t_eq_k"), 0),
                _hz_label(p),
                _notes_for(p),
                p.get("source") or "—",
            ]
            for c, val in enumerate(cells):
                item = QStandardItem(str(val))
                item.setEditable(False)
                if observed:
                    item.setBackground(QColor(_OBS_ROW_BG))
                if c == len(cells) - 1:   # Source cell: colour + bold
                    item.setForeground(QColor(_OBSERVED_COLOR if observed else _SYNTH_COLOR))
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                model.setItem(r, c, item)
        view = QTableView()
        view.setModel(model)
        view.setSortingEnabled(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.resizeColumnsToContents()
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return view

    # ── viz tabs ─────────────────────────────────────────────────────────────────

    def _add_orbit_tab(self, result):
        """Orbit Diagram — observed vs synthetic orbits styled distinctly (colour),
        with the HZ annulus + water snow-line ring drawn from the star's specs."""
        orbits, max_au = _orbit_dicts(result["planets"])
        if not orbits:
            return
        star = result["star"]
        hz = core.viz.prepare_hz_diagram(star.get("teff") or 0, star.get("luminosity") or 0)
        hz_zones = hz.get("zones", []) if isinstance(hz, dict) and "error" not in hz else []
        outer_hz = hz_zones[-1]["outer"] if hz_zones else 0.0
        frame = max(max_au, outer_hz) * 1.1 or 1.0
        try:
            canvas, toolbar = make_orbits_canvas(
                self, orbits, hz_zones, frame,
                star_name=star.get("name", ""),
                snow_au=star.get("snow_line_au"),
                title="Generated System Orbits")
        except Exception:
            return
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.addWidget(toolbar)
        wl.addWidget(canvas)
        self._viz_tabs_widget.addTab(w, "Orbit Diagram")

    def _add_hz_tab(self, star, planets=None):
        """HZ Diagram — Rings/Strip toggle (Phase 5) for the generated star; the Strip
        places the generated planets by semi-major axis."""
        teff = star.get("teff") or 0
        lum = star.get("luminosity") or 0
        hz_planets = [{"name": p.get("name", "?"), "au": p.get("a_au")}
                      for p in (planets or []) if p.get("a_au")]
        try:
            w = _hz_toggle_tab(self, teff, lum, title="Habitable Zone",
                               planets=hz_planets)
        except Exception:
            return
        if w is not None:
            self._viz_tabs_widget.addTab(w, "HZ Ring")

    # ── copy json ─────────────────────────────────────────────────────────────────

    def _copy_json(self):
        if not self._last_result:
            return
        text = json.dumps(self._last_result, indent=2, default=str)
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
            self.set_status("Copied system JSON to clipboard.")

    def _add_to_project(self):
        if not self._last_result or "error" in self._last_result:
            return
        from gui.panels.projects import choose_and_add
        lp = self._last_params or {}
        spec = {
            "seed": lp.get("seed"),
            "mode": "real_anchor" if lp.get("mode") == "anchor" else "synthetic",
            "anchor_star": lp.get("anchor"),
            "spectral_class": lp.get("spectral_class"),
            "n_planets": lp.get("n_planets"),
            "require_habitable": lp.get("require", False),
            "constraints": self._active_specs or None,
            "research_policy": lp.get("research_policy", "permissive"),
            "nbody": lp.get("nbody", False),
        }
        star = self._last_result["star"]["name"]
        choose_and_add(self, star, source="generated", seed=lp.get("seed"), spec=spec)
