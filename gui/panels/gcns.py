# gui/panels/gcns.py — Phase M: GCNS Interactive Surfacing (GUI-only, no menu numbers).
#
# Six panels that surface the GCNS census (opt 58) — previously reachable only via
# query.py's gcns-* subcommands. All call the existing core.databases.compute_gcns_*
# functions verbatim; no new core code lives here.
#
#   GcnsCensusBrowserPanel     — compute_gcns_within_sol         (M1, map tabs)
#   GcnsSourceLookupPanel      — _resolve_gcns_row               (M2, dual input)
#   GcnsSystemViewerPanel      — compute_gcns_system             (M3, dual input)
#   GcnsDistancePanel          — compute_gcns_distance           (M4a)
#   GcnsTravelTimePanel        — compute_gcns_travel_time        (M4b)
#   GcnsStarsWithinStarPanel   — compute_gcns_stars_within_star  (M4c, map tabs)
#
# Resolution model (M2/M3/M4): each endpoint accepts a name (resolved via SIMBAD →
# Gaia id, in a background thread) or a raw Gaia source_id (offline, instant). The
# id wins if both are filled. The "_endpoint"/"_go" helpers branch on whether any
# endpoint is a name (→ run_in_background) or all are ids (→ synchronous instant).

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QWidget, QComboBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel, DiagramToggleMixin
from gui.panels.diagram_tabs import _build_star_chart_3d_tab
import core.databases
from gui.visualizations.plot_helpers import mpl_available, make_star_chart_canvas
from core.viz import _SPECTRAL_COLORS, _sp_color as core_sp_color


# ── formatting helpers ────────────────────────────────────────────────────────

def _fmt(v, dp):
    return f"{v:.{dp}f}" if isinstance(v, (int, float)) else "N/A"


def _sigma(s):
    """−σ / +σ distance pair (pc), or '—' for missing_10mas rows (no Bayesian PDF)."""
    lo, hi = s.get("dist_lo_pc"), s.get("dist_hi_pc")
    if lo is None or hi is None:
        return "—"
    return f"{lo:.3f} / {hi:.3f}"


def _meth(m):
    # "synthetic_sol_origin" is the appended Sol row (no catalogue holds the Sun);
    # without an entry here the raw key would surface in the Distance Method column.
    return {"gcns_bayesian": "Bayesian",
            "gcns_missing_plx_inversion": "1/ϖ inversion",
            "synthetic_sol_origin": "Synthetic (origin)"}.get(m, m or "N/A")


def _yn(v):
    if v is None:
        return "N/A"
    return "Yes" if v else "No"


def _name_of(s):
    """Display name for a GCNS row: SIMBAD name, else the Gaia id, else a dash."""
    return s.get("star_name") or (str(s["gaia_source_id"])
                                  if s.get("gaia_source_id") is not None else "—")


def _sp_color(sp):
    sp = (sp or "").strip()
    return core_sp_color(sp)   # prefix-aware: dM6 -> M, DA -> D


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


# ── star-map adapters + tab builder (M1, M4c) ─────────────────────────────────

def _gcns_map_stars(result, *, center=False):
    """Adapt a GCNS within-sol / within-star result into star-chart map stars.

    Returns a list of {name, desig, sp_type, color, ly, x, y, z} dicts. The Sol
    origin (within-sol) or the center star (within-star) is prepended as a gold ★.
    """
    out = []
    if center:
        cx = result.get("center_x") or 0.0
        cy = result.get("center_y") or 0.0
        cz = result.get("center_z") or 0.0
        cen = result.get("center", {}) or {}
        out.append({"name": _name_of(cen), "desig": "", "sp_type": cen.get("spectral_type") or "",
                    "color": "#FFD700", "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0})
        for s in result.get("stars", []):
            if s.get("x") is None:
                continue
            out.append({"name": _name_of(s), "desig": "", "sp_type": s.get("spectral_type") or "",
                        "color": _sp_color(s.get("spectral_type")),
                        "ly": s.get("Distance"),
                        "x": s["x"] - cx, "y": s["y"] - cy, "z": s["z"] - cz,
                        # The synthetic Sol row -> a ★ instead of a dot.
                        "is_sol": s.get("distance_method") == "synthetic_sol_origin"})
    else:
        out.append({"name": "Sol", "desig": "", "sp_type": "G2V",
                    "color": _SPECTRAL_COLORS.get("G", "#FFD700"),
                    "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0})
        for s in result.get("stars", []):
            if s.get("x") is None:
                continue
            out.append({"name": _name_of(s), "desig": "", "sp_type": s.get("spectral_type") or "",
                        "color": _sp_color(s.get("spectral_type")),
                        "ly": s.get("light_years"),
                        "x": s["x"], "y": s["y"], "z": s["z"]})
    return out


def _add_chart_tabs(panel, map_stars, limit_ly):
    """Add 'Star Chart' + 'Star Chart 3D' tabs — the labeled dark-navy diagrams from
    opts 18/19 (make_star_chart_canvas / make_star_chart_3d_canvas). The center
    (Sol or the queried star) is the gold ★ at the origin."""
    # Star Chart — labeled 2D X–Y projection (dark navy palette)
    chart_w = QWidget()
    chart_l = QVBoxLayout(chart_w)
    chart_l.setContentsMargins(4, 4, 4, 4)
    canvas_sc, toolbar_sc = make_star_chart_canvas(panel, map_stars, limit_ly=limit_ly)
    chart_l.addWidget(toolbar_sc)
    chart_l.addWidget(canvas_sc)
    panel._viz_tabs_widget.addTab(chart_w, "Star Chart")

    # Star Chart 3D — labeled 3D companion with Top/Side/Perspective presets.
    # _build_star_chart_3d_tab returns (widget, canvas); GCNS uses only the widget.
    chart3d_w, _ = _build_star_chart_3d_tab(panel, map_stars, limit_ly)
    panel._viz_tabs_widget.addTab(chart3d_w, "Star Chart 3D")


# ── shared scaffold for the non-map GCNS panels (M2, M3, M4a, M4b) ────────────

class _GcnsFormPanel(ResultPanel):
    """Error label + a result container the subclass repopulates on each run.

    Provides the dual name/id endpoint widgets and the instant-vs-background branch.
    """

    def build_results_area(self):
        self._err = QLabel()
        self._err.setStyleSheet("color: red;")
        self._err.setWordWrap(True)
        self._layout.addWidget(self._err)
        self._err.hide()

        self._box = QWidget()
        self._box_l = QVBoxLayout(self._box)
        self._box_l.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._box, 1)
        self._layout.addStretch()

    # result-area management
    def _begin(self):
        self._err.hide()
        _clear_layout(self._box_l)

    def _show_err(self, msg):
        _clear_layout(self._box_l)
        self._err.setText(msg)
        self._err.setStyleSheet("color: red;")
        self._err.show()

    def _show_info(self, msg):
        """Show a neutral, non-error message (e.g. 'this star is single')."""
        _clear_layout(self._box_l)
        self._err.setText(msg)
        self._err.setStyleSheet(
            "color:#23517d; background:#eaf3fb; border:1px solid #c3ddf2; "
            "border-radius:4px; padding:6px 9px;")
        self._err.show()

    def _add(self, widget, stretch=0):
        self._box_l.addWidget(widget, stretch)

    def _kv(self, pairs):
        view = self.make_table(["Field", "Value"], [[k, v] for k, v in pairs])
        view.setSortingEnabled(False)
        return view

    # dual endpoint widgets
    def _dual_endpoint(self, form, *, name_default="", name_label="Star name:",
                       id_label="or Gaia source_id:", name_hint="e.g. Barnard's Star"):
        name_edit = QLineEdit()
        name_edit.setText(name_default)
        name_edit.setPlaceholderText(name_hint)
        id_edit = QLineEdit()
        id_edit.setPlaceholderText("offline — e.g. 4472832130942575872")
        form.addRow(name_label, name_edit)
        form.addRow(id_label, id_edit)
        return name_edit, id_edit

    def _endpoint(self, name_edit, id_edit):
        """Return (kind, value): ('id', int) | ('name', str) | ('empty', None) | ('err', msg)."""
        idt = id_edit.text().strip()
        nm = name_edit.text().strip()
        if idt:
            try:
                return ("id", int(idt))
            except ValueError:
                return ("err", f"Gaia source_id must be an integer (got '{idt}').")
        if nm:
            return ("name", nm)
        return ("empty", None)

    @staticmethod
    def _ep_kwargs(ep, name_key, id_key):
        kind, value = ep
        if kind == "id":
            return {id_key: value}
        if kind == "name":
            return {name_key: value}
        return {}

    def _go(self, fn, kwargs, network):
        """Run fn(**kwargs): background thread if a name endpoint needs SIMBAD,
        else synchronously for an instant local-DB read."""
        if network:
            self.run_in_background(fn, on_result=self._render, **kwargs)
        else:
            self._render(fn(**kwargs))


# ── M1: GCNS Census Browser ───────────────────────────────────────────────────

class GcnsCensusBrowserPanel(DiagramToggleMixin, ResultPanel):
    """All GCNS sources within N ly of Sol — instant local-DB read (no SIMBAD)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance from Sol (Light Years):", self._limit)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()
        self._input_count = self._layout.count()

    def _search(self):
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self._prepare_render()
            _clear_layout(self._tables_layout)
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._tables_layout.addWidget(lbl)
            return
        # Instant local read (opt 18 pattern) — no background thread.
        self._render(core.databases.compute_gcns_within_sol(limit_ly))

    def _render(self, result: dict):
        self._prepare_render()
        _clear_layout(self._tables_layout)

        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._tables_layout.addWidget(lbl)
            return

        count = result["count"]
        limit = result["limit_ly"]
        self._tables_layout.addWidget(
            QLabel(f"GCNS sources within {limit} ly of Sol: <b>{count}</b>")
        )
        snap = result.get("snapshot_date")
        if snap:
            self._tables_layout.addWidget(
                QLabel(f"<span style='color:#777'>GCNS snapshot {snap}</span>")
            )
        if count == 0:
            return

        headers = ["Star Name", "Gaia source_id", "Spectral Type", "Dist (pc)",
                   "−σ / +σ (pc)", "Light Years", "Distance Method", "In SIMBAD"]
        rows = [
            [_name_of(s), s.get("gaia_source_id") or "—", s.get("spectral_type") or "N/A",
             _fmt(s.get("dist_pc"), 4), _sigma(s), _fmt(s.get("light_years"), 4),
             _meth(s.get("distance_method")), _yn(s.get("in_simbad"))]
            for s in result["stars"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if mpl_available():
            map_stars = _gcns_map_stars(result, center=False)
            if map_stars:
                _add_chart_tabs(self, map_stars, limit)

        self._finish_render()


# ── M2: GCNS Source Lookup ────────────────────────────────────────────────────

class GcnsSourceLookupPanel(_GcnsFormPanel):
    """Full detail for one GCNS source. Name (SIMBAD → id) or raw Gaia source_id."""

    def build_inputs(self):
        form = QFormLayout()
        self._name, self._id = self._dual_endpoint(form)
        self._layout.addLayout(form)

        self.run_btn = QPushButton("Look Up")
        self.run_btn.clicked.connect(self._lookup)
        self._name.returnPressed.connect(self._lookup)
        self._id.returnPressed.connect(self._lookup)
        self._layout.addWidget(self.run_btn)
        self._input_count = self._layout.count()

    def _lookup(self):
        self._begin()
        ep = self._endpoint(self._name, self._id)
        if ep[0] == "err":
            return self._show_err(ep[1])
        if ep[0] == "empty":
            return self._show_err("Enter a star name or a Gaia source_id.")
        kwargs = self._ep_kwargs(ep, "star", "source_id")
        self._go(core.databases._resolve_gcns_row, kwargs, network=(ep[0] == "name"))

    def _render(self, row: dict):
        self._begin()
        if "error" in row:
            return self._show_err(row["error"])

        # Headline: Bayesian distance + uncertainty
        if row.get("dist_lo_pc") is not None:
            hl = (f"<b>{_fmt(row.get('dist_pc'), 4)} pc</b> "
                  f"<span style='color:#1f6f8b'>({_fmt(row.get('dist_lo_pc'), 4)} … "
                  f"{_fmt(row.get('dist_hi_pc'), 4)})</span> &nbsp; "
                  f"= {_fmt(row.get('light_years'), 4)} ly &nbsp;·&nbsp; "
                  f"16th/84th-percentile uncertainty")
        else:
            hl = (f"<b>{_fmt(row.get('dist_pc'), 4)} pc</b> "
                  f"= {_fmt(row.get('light_years'), 4)} ly &nbsp;·&nbsp; "
                  f"1/ϖ point value (no error bar — missing_10mas)")
        lbl = QLabel(hl)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 14px; padding: 4px 0;")
        self._add(lbl)

        gid = row.get("gaia_source_id")
        phot = ("N/A (not in Gaia)" if row.get("phot_g_mean_mag") is None else
                f"{_fmt(row.get('phot_g_mean_mag'), 2)} / {_fmt(row.get('phot_bp_mean_mag'), 2)} / "
                f"{_fmt(row.get('phot_rp_mean_mag'), 2)}  (Gaia bands — NOT Johnson V)")
        pairs = [
            ("Gaia source_id", gid if gid is not None else "N/A (missing_10mas — no source_id)"),
            ("Star name (SIMBAD)", row.get("star_name") or "N/A"),
            ("Spectral Type (SIMBAD)", row.get("spectral_type") or "N/A"),
            ("Bayesian distance (pc)", _fmt(row.get("dist_pc"), 4)),
            ("Uncertainty −σ / +σ (pc)", _sigma(row)),
            ("Light Years", _fmt(row.get("light_years"), 4)),
            ("Distance method", _meth(row.get("distance_method"))),
            ("RA / DEC (deg)", f"{_fmt(row.get('ra'), 4)} / {_fmt(row.get('dec'), 4)}"),
            ("Parallax (mas)", _fmt(row.get("parallax"), 4)),
            ("Gaia G / BP / RP", phot),
            ("Johnson V (app_magnitude)", _fmt(row.get("app_magnitude"), 2)),
            ("Radial velocity (km/s)", _fmt(row.get("rv_kms"), 1)),
            ("White-dwarf prob.", _fmt(row.get("wd_prob"), 4)),
            ("Astrometry reliable prob.", _fmt(row.get("astrom_reliable_prob"), 4)),
            ("GCNS table", row.get("gcns_table") or "N/A"),
        ]
        self._add(self._kv(pairs), stretch=1)

        if row.get("system_id") is not None:
            ptr = QLabel(f"▶ Part of a resolved <b>{row.get('n_components')}-component</b> "
                         "system — open it in the Resolved System Viewer.")
            ptr.setWordWrap(True)
            ptr.setStyleSheet("color:#23517d; background:#eaf3fb; border:1px solid #c3ddf2; "
                              "border-radius:4px; padding:6px 9px;")
            self._add(ptr)
        else:
            # State multiplicity explicitly for single stars too, so the user
            # doesn't need the System Viewer to learn the star is single and the
            # two panels visibly agree.
            note = QLabel("Not part of a Gaia-resolved multiple system "
                          "(single or unresolved).")
            note.setWordWrap(True)
            note.setStyleSheet("color:#666; font-style:italic; padding:4px 0;")
            self._add(note)


# ── M3: Resolved Multiple-Star System Viewer ──────────────────────────────────

def _gcns_system_by_name(star):
    """Name → SIMBAD → Gaia id → compute_gcns_system. Used for the M3 name path."""
    row = core.databases._resolve_gcns_row(star=star)
    if "error" in row:
        return row
    sid = row.get("gaia_source_id")
    if sid is None:
        return {"error": (f"'{star}' has no Gaia source_id (a missing_10mas object) — "
                          "it cannot be part of a Gaia-resolved system.")}
    return core.databases.compute_gcns_system(sid)


class GcnsSystemViewerPanel(_GcnsFormPanel):
    """The Gaia-resolved system containing a source (from gcns.resolvedss)."""

    def build_inputs(self):
        form = QFormLayout()
        self._name, self._id = self._dual_endpoint(
            form, name_hint="e.g. 61 Cygni A, Sirius A")
        self._layout.addLayout(form)

        self.run_btn = QPushButton("View System")
        self.run_btn.clicked.connect(self._view)
        self._name.returnPressed.connect(self._view)
        self._id.returnPressed.connect(self._view)
        self._layout.addWidget(self.run_btn)
        self._input_count = self._layout.count()

    def _view(self):
        self._begin()
        ep = self._endpoint(self._name, self._id)
        if ep[0] == "err":
            return self._show_err(ep[1])
        if ep[0] == "empty":
            return self._show_err("Enter a star name or a Gaia source_id.")
        if ep[0] == "id":
            self._render(core.databases.compute_gcns_system(ep[1]))
        else:
            self.run_in_background(_gcns_system_by_name, ep[1], on_result=self._render)

    def _render(self, result: dict):
        self._begin()
        if "error" in result:
            msg = result["error"]
            low = msg.lower()
            # "single / not Gaia-resolved" and "no source_id" are normal outcomes,
            # not lookup failures — present them as info, not a red error.
            if ("not part of any" in low or "cannot be part of a gaia-resolved" in low
                    or "no gaia source_id" in low):
                return self._show_info(
                    msg + "\n\nThis is a normal result — the star is single or its "
                    "companions weren't resolved by Gaia. gcns.resolvedss only lists "
                    "multiples Gaia could resolve, so a single star (e.g. Epsilon "
                    "Eridani) correctly has no resolved system.")
            return self._show_err(msg)

        sys = result["system"]
        self._add(QLabel(f"<b>System {sys['system_id']}</b> · "
                         f"{sys['n_components']} components · {sys['n_pairs']} pair(s)"))

        # System summary
        self._add(QLabel("<b>System Summary</b>"))
        summary = [
            ("system_id", sys["system_id"]),
            ("n_components", sys["n_components"]),
            ("n_pairs", sys["n_pairs"]),
            ("any_bin", _yn(sys["any_bin"])),
            ("any_bound", _yn(sys["any_bound"])),
            ("all_bound", _yn(sys["all_bound"])),
            ("min / max proj. sep (AU)",
             f"{_fmt(sys['min_proj_sep_au'], 2)} / {_fmt(sys['max_proj_sep_au'], 2)}"),
            ("members in gcns_stars", sys["n_in_gcns_stars"]),
        ]
        self._add(self._kv(summary))

        # Members
        self._add(QLabel("<b>Members</b>"))
        mheaders = ["Gaia source_id", "In gcns_stars", "Query", "Star Name",
                    "Spectral Type", "Dist (pc)", "Light Years"]
        mrows = [
            [m["gaia_source_id"], _yn(m["in_gcns_stars"]), "▶" if m["is_query"] else "",
             m["star_name"] or "N/A", m["spectral_type"] or "N/A",
             _fmt(m["dist_pc"], 4), _fmt(m["light_years"], 4)]
            for m in sys["members"]
        ]
        mview = self.make_table(mheaders, mrows)
        mview.setSortingEnabled(False)
        self._add(mview)

        # Pairs
        self._add(QLabel("<b>Resolved Pairs</b>"))
        pheaders = ["source_id1", "source_id2", "Separation (″)", "Δmag",
                    "Proj. Sep (AU)", "bin", "bound"]
        prows = [
            [p["source_id1"], p["source_id2"], _fmt(p["separation_arcsec"], 2),
             _fmt(p["mag_diff"], 2), _fmt(p["proj_sep_au"], 2), _yn(p["bin"]), _yn(p["bound"])]
            for p in sys["pairs"]
        ]
        pview = self.make_table(pheaders, prows)
        pview.setSortingEnabled(False)
        self._add(pview, stretch=1)


# ── M4a: GCNS Distance Between 2 Stars ────────────────────────────────────────

class GcnsDistancePanel(_GcnsFormPanel):
    """3D Euclidean distance over the GCNS Bayesian-distance census."""

    def build_inputs(self):
        form = QFormLayout()
        self._n1, self._i1 = self._dual_endpoint(
            form, name_label="Star 1 name:", id_label="Star 1 Gaia source_id:",
            name_hint="e.g. Proxima Centauri")
        self._n2, self._i2 = self._dual_endpoint(
            form, name_label="Star 2 name:", id_label="Star 2 Gaia source_id:",
            name_hint="e.g. Barnard's Star")
        self._layout.addLayout(form)

        self.run_btn = QPushButton("Compute")
        self.run_btn.clicked.connect(self._compute)
        for e in (self._n1, self._i1, self._n2, self._i2):
            e.returnPressed.connect(self._compute)
        self._layout.addWidget(self.run_btn)
        self._input_count = self._layout.count()

    def _compute(self):
        self._begin()
        e1 = self._endpoint(self._n1, self._i1)
        e2 = self._endpoint(self._n2, self._i2)
        for e in (e1, e2):
            if e[0] == "err":
                return self._show_err(e[1])
            if e[0] == "empty":
                return self._show_err("Enter a name or Gaia source_id for both stars.")
        kwargs = {**self._ep_kwargs(e1, "star1", "id1"),
                  **self._ep_kwargs(e2, "star2", "id2")}
        network = e1[0] == "name" or e2[0] == "name"
        self._go(core.databases.compute_gcns_distance, kwargs, network)

    def _render(self, result: dict):
        self._begin()
        if "error" in result:
            return self._show_err(result["error"])

        a, b = result["star1_info"], result["star2_info"]
        d = result["distance_ly"]
        au = result.get("distance_au")
        hl = (f"<b>Distance: {_fmt(d, 4)} light years</b>"
              + (f" &nbsp;=&nbsp; {_fmt(au, 2)} AU" if au is not None else "")
              + f"<br><span style='color:#444'>{_name_of(a)} ↔ {_name_of(b)}</span>")
        lbl = QLabel(hl)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 14px; padding: 4px 0;")
        self._add(lbl)

        headers = ["Field", "Star 1", "Star 2"]
        fields = [
            ("Gaia source_id", "gaia_source_id", None),
            ("Star name", "star_name", None),
            ("Spectral type", "spectral_type", None),
            ("Dist (pc)", "dist_pc", 4),
            ("Light Years", "light_years", 4),
            ("Distance method", "distance_method", "meth"),
            ("RA (hms)", "ra_hms", None),
            ("DEC (dms)", "dec_dms", None),
        ]
        rows = []
        for label, key, dp in fields:
            def cell(info):
                v = info.get(key)
                if dp == "meth":
                    return _meth(v)
                if isinstance(dp, int):
                    return _fmt(v, dp)
                return v if v is not None else "N/A"
            rows.append([label, cell(a), cell(b)])
        # −σ/+σ row (special — combines two keys)
        rows.insert(4, ["−σ / +σ (pc)", _sigma(a), _sigma(b)])
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        self._add(view, stretch=1)


# ── M4b: GCNS Travel Time ─────────────────────────────────────────────────────

class GcnsTravelTimePanel(_GcnsFormPanel):
    """FTL travel time between two GCNS stars at a chosen velocity."""

    def build_inputs(self):
        form = QFormLayout()
        self._n1, self._i1 = self._dual_endpoint(
            form, name_label="Origin name:", id_label="Origin Gaia source_id:",
            name_hint="e.g. Proxima Centauri")
        self._n2, self._i2 = self._dual_endpoint(
            form, name_label="Destination name:", id_label="Destination Gaia source_id:",
            name_hint="e.g. 61 Cygni A")

        self._unit = QComboBox()
        self._unit.addItem("× the speed of light", "c")
        self._unit.addItem("light years / hour", "lyhr")
        form.addRow("Velocity unit:", self._unit)
        self._vel = QLineEdit()
        self._vel.setPlaceholderText("e.g. 100")
        form.addRow("Velocity value:", self._vel)
        self._layout.addLayout(form)

        self.run_btn = QPushButton("Compute")
        self.run_btn.clicked.connect(self._compute)
        self._vel.returnPressed.connect(self._compute)
        self._layout.addWidget(self.run_btn)
        self._input_count = self._layout.count()

    def _compute(self):
        self._begin()
        e1 = self._endpoint(self._n1, self._i1)
        e2 = self._endpoint(self._n2, self._i2)
        for e in (e1, e2):
            if e[0] == "err":
                return self._show_err(e[1])
            if e[0] == "empty":
                return self._show_err("Enter a name or Gaia source_id for both endpoints.")
        try:
            v = float(self._vel.text().strip())
            if v <= 0:
                raise ValueError
        except ValueError:
            return self._show_err("Velocity must be a positive number.")

        kwargs = {**self._ep_kwargs(e1, "star1", "id1"),
                  **self._ep_kwargs(e2, "star2", "id2")}
        if self._unit.currentData() == "c":
            kwargs["times_c"] = v
        else:
            kwargs["ly_hr"] = v
        network = e1[0] == "name" or e2[0] == "name"
        self._go(core.databases.compute_gcns_travel_time, kwargs, network)

    def _render(self, result: dict):
        self._begin()
        if "error" in result:
            return self._show_err(result["error"])

        a, b = result["origin_info"], result["dest_info"]
        headers = ["Origin", "Destination", "Distance (LY)", "LY/HR", "× c",
                   "Travel Time (Hours)", "Travel Time"]
        row = [
            _name_of(a), _name_of(b), _fmt(result["distance_ly"], 4),
            f"{result['ly_hr']:.4e}", _fmt(result["times_c"], 2),
            _fmt(result["total_hours"], 2), result["travel_time_str"],
        ]
        view = self.make_table(headers, [row])
        view.setSortingEnabled(False)
        self._add(view)


# ── M4c: GCNS Stars Within a Star ─────────────────────────────────────────────

class GcnsStarsWithinStarPanel(DiagramToggleMixin, ResultPanel):
    """All GCNS stars within N ly of a center star (keeps close companions)."""

    def build_inputs(self):
        form_widget = QWidget()
        form = QFormLayout(form_widget)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Sirius A, Alpha Centauri A")
        form.addRow("Center star name:", self._name)
        self._id = QLineEdit()
        self._id.setPlaceholderText("offline — e.g. 2947050466531873024")
        form.addRow("or Gaia source_id:", self._id)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 6.0")
        form.addRow("Distance (Light Years):", self._limit)

        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        self._show_diagrams_btn = QPushButton("Show Diagrams")
        self._show_diagrams_btn.clicked.connect(self._enter_diagram_mode)
        self._show_diagrams_btn.setVisible(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._show_diagrams_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._form_widget = form_widget
        self._layout.addWidget(form_widget)
        self._input_count = self._layout.count()

    def build_results_area(self):
        self._tables_widget = QWidget()
        self._tables_layout = QVBoxLayout(self._tables_widget)
        self._tables_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._tables_widget, 1)
        self._setup_diagram_view()
        self._input_count = self._layout.count()

    def _search(self):
        idt = self._id.text().strip()
        nm = self._name.text().strip()
        if idt:
            try:
                source_id = int(idt)
            except ValueError:
                return self._err_to_tables(f"Gaia source_id must be an integer (got '{idt}').")
            star = None
        elif nm:
            source_id, star = None, nm
        else:
            return self._err_to_tables("Enter a center star name or a Gaia source_id.")
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            return self._err_to_tables("Distance must be a positive number.")

        kwargs = {"limit_ly": limit_ly}
        if source_id is not None:
            kwargs["source_id"] = source_id
            self._render(core.databases.compute_gcns_stars_within_star(**kwargs))
        else:
            kwargs["star"] = star
            self.run_in_background(core.databases.compute_gcns_stars_within_star,
                                   on_result=self._render, **kwargs)

    def _err_to_tables(self, msg):
        self._prepare_render()
        _clear_layout(self._tables_layout)
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: red;")
        lbl.setWordWrap(True)
        self._tables_layout.addWidget(lbl)

    def _render(self, result: dict):
        self._prepare_render()
        _clear_layout(self._tables_layout)

        if "error" in result:
            self._err_to_tables(result["error"])
            return

        count = result["count"]
        limit = result["limit_ly"]
        center_name = _name_of(result.get("center", {}))
        self._tables_layout.addWidget(
            QLabel(f"GCNS stars within {limit} ly of {center_name}: <b>{count}</b>")
        )
        if count == 0:
            return

        headers = ["Star Name", "Gaia source_id", "Spectral Type", "Dist (pc)",
                   "−σ / +σ (pc)", "Distance from center (ly)", "Distance Method"]
        rows = [
            [_name_of(s), s.get("gaia_source_id") or "—", s.get("spectral_type") or "N/A",
             _fmt(s.get("dist_pc"), 4), _sigma(s), _fmt(s.get("Distance"), 4),
             _meth(s.get("distance_method"))]
            for s in result["stars"]
        ]
        view = self.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tables_layout.addWidget(view, 1)

        if mpl_available():
            map_stars = _gcns_map_stars(result, center=True)
            if map_stars:
                _add_chart_tabs(self, map_stars, limit)

        self._finish_render()
