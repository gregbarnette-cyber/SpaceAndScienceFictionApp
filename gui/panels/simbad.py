# gui/panels/simbad.py — Option 1: SIMBAD Lookup Query.

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QWidget, QVBoxLayout,
    QTabWidget, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import (
    ResultPanel, add_designation_names_line, add_gould_line,
)
from gui.panels.wikipedia_tab import WikipediaButtonMixin
from gui.panels.hypatia_tab import build_hypatia_tab, fit_table_height
from gui.visualizations.plot_helpers import mpl_available, make_abundance_canvas, log_viz_error, wrap_scrollable, make_kinematics_tab
import core.databases
import core.viz


def _simbad_with_hypatia(name: str) -> dict:
    result = core.databases.compute_simbad_lookup(name)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(result)
    return result


def _fmtf(v, dp):
    return f"{v:.{dp}f}" if isinstance(v, (int, float)) else "N/A"


def _build_gcns_tab(gcns: dict, simbad: dict) -> QWidget:
    """Phase M5: a GCNS cross-reference tab — Bayesian distance + 16th/84th
    uncertainty shown beside opt 1's naive 1/ϖ parallax distance."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(6, 6, 6, 6)
    lay.setAlignment(Qt.AlignmentFlag.AlignTop)

    # Headline: naive 1/ϖ vs GCNS Bayesian + σ
    naive_pc = simbad.get("parsecs")
    naive_ly = simbad.get("ly")
    bay_pc = gcns.get("dist_pc")
    lo, hi = gcns.get("dist_lo_pc"), gcns.get("dist_hi_pc")
    bay_ly = gcns.get("light_years")
    sig = (f" <span style='color:#1f6f8b'>({_fmtf(lo, 4)} … {_fmtf(hi, 4)})</span>"
           if lo is not None and hi is not None else
           " <span style='color:#888'>(1/ϖ point value — no error bar)</span>")
    headline = QLabel(
        f"<table cellpadding='4'>"
        f"<tr><td style='color:#777'>opt 1 naive 1/ϖ distance</td>"
        f"<td><b>{_fmtf(naive_pc, 4)} pc</b> &nbsp; {_fmtf(naive_ly, 4)} ly "
        f"<span style='color:#888'>· point estimate</span></td></tr>"
        f"<tr><td style='color:#1d6b41'>GCNS Bayesian distance</td>"
        f"<td><b>{_fmtf(bay_pc, 4)} pc</b>{sig} &nbsp; {_fmtf(bay_ly, 4)} ly "
        f"<span style='color:#3a6b48'>· 16th/84th-percentile uncertainty</span></td></tr>"
        f"</table>"
    )
    headline.setTextFormat(Qt.TextFormat.RichText)
    lay.addWidget(headline)

    g, bp, rp = (gcns.get("phot_g_mean_mag"), gcns.get("phot_bp_mean_mag"),
                 gcns.get("phot_rp_mean_mag"))
    phot = ("N/A" if g is None else
            f"{_fmtf(g, 2)} / {_fmtf(bp, 2)} / {_fmtf(rp, 2)}  (Gaia bands — NOT Johnson V)")
    method = {"gcns_bayesian": "Bayesian",
              "gcns_missing_plx_inversion": "1/ϖ inversion"}.get(
                  gcns.get("distance_method"), gcns.get("distance_method") or "N/A")
    detail = [
        ("Gaia source_id", gcns.get("gaia_source_id")),
        ("Distance method", method),
        ("Astrometry reliable prob.", _fmtf(gcns.get("astrom_reliable_prob"), 4)),
        ("White-dwarf prob.", _fmtf(gcns.get("wd_prob"), 4)),
        ("Gaia G / BP / RP", phot),
        ("Radial velocity (km/s)", _fmtf(gcns.get("rv_kms"), 1)),
    ]
    from PySide6.QtWidgets import QTableView
    from PySide6.QtGui import QStandardItemModel, QStandardItem
    model = QStandardItemModel(len(detail), 2)
    model.setHorizontalHeaderLabels(["Field", "Value"])
    for r, (k, v) in enumerate(detail):
        ki = QStandardItem(str(k)); ki.setEditable(False)
        vi = QStandardItem(str(v) if v is not None else "N/A"); vi.setEditable(False)
        model.setItem(r, 0, ki); model.setItem(r, 1, vi)
    view = QTableView()
    view.setModel(model)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.resizeColumnsToContents()
    lay.addWidget(view)

    if gcns.get("system_id") is not None:
        ptr = QLabel(f"▶ Part of a resolved <b>{gcns.get('n_components')}-component</b> "
                     "system — open the Resolved System Viewer (GCNS category).")
        ptr.setWordWrap(True)
        ptr.setStyleSheet("color:#23517d; background:#eaf3fb; border:1px solid #c3ddf2; "
                          "border-radius:4px; padding:6px 9px;")
        lay.addWidget(ptr)

    return w


class SimbadPanel(WikipediaButtonMixin, ResultPanel):
    """SIMBAD star lookup panel (option 1).

    Input:  Star name / designation text field.
    Output: QTabWidget with Star Properties tab + Hypatia tab.
    """

    def build_inputs(self):
        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Vega, HD 209458, Alpha Centauri")
        self._name_input.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name_input)

        # All three actions on one row (Search · Wikipedia · Add to project) rather than stacked.
        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)

        self._wiki_btn = self._make_wiki_button()
        self._wiki_btn.setToolTip("Open this star's Wikipedia article in a new tab.")

        self._add_proj_btn = QPushButton("Add to project ▾")
        self._add_proj_btn.setEnabled(False)
        self._add_proj_btn.setToolTip("Add this star to a project workspace (Phase S).")
        self._add_proj_btn.clicked.connect(self._add_to_project)

        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self._wiki_btn)
        btn_row.addWidget(self._add_proj_btn)
        btn_row.addStretch()
        form.addRow("", btn_widget)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def _add_to_project(self):
        from gui.panels.projects import choose_and_add
        name = getattr(self, "_last_star", None) or self._name_input.text().strip()
        choose_and_add(self, name, source="looked_up")

    def build_results_area(self):
        pass   # results added dynamically in render()

    def _search(self):
        name = self._name_input.text().strip()
        if not name:
            return
        self.clear_results()
        # clear_results() deleted the tab widget the wiki button targets; disable it until the
        # next successful render re-arms it (base clear_results, unlike the catalog panels', has
        # no wiki-aware disable of its own).
        self._wiki_btn.setEnabled(False)
        self.run_in_background(_simbad_with_hypatia, name)

    def render(self, result: dict):
        self.clear_results()

        if "error" in result:
            self._add_proj_btn.setEnabled(False)
            # clear_results() above deleted the prior tabs; disable the button so a stale
            # click can't reach a freed tab widget.
            self._wiki_btn.setEnabled(False)
            self.show_error(result["error"])
            return

        self._last_star = result.get("main_id") or self._name_input.text().strip()
        self._add_proj_btn.setEnabled(True)

        # ── Star Properties tab ───────────────────────────────────────────────
        props_widget = QWidget()
        props_layout = QVBoxLayout(props_widget)
        props_layout.setContentsMargins(4, 4, 4, 4)
        props_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        desig_str = result.get("desig_str", "N/A")
        banner = QLabel(f"<b>STAR DESIGNATIONS:</b><br>{desig_str}")
        banner.setWordWrap(True)
        banner.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        props_layout.addWidget(banner)
        names_line = add_designation_names_line(props_layout, result)  # AN3 — no-op when absent
        add_gould_line(props_layout, result, inline_with=names_line)   # AO3 — same line as AN3's

        plx    = result.get("plx_value")
        parsec = result.get("parsecs")
        ly     = result.get("ly")
        teff   = result.get("teff")
        vmag   = result.get("vmag")
        ra     = result.get("ra")
        dec    = result.get("dec")

        def _fmtf(v, dp):
            return f"{v:.{dp}f}" if v is not None else "N/A"

        headers = [
            "Spectral Type", "Parallax (mas)", "Distance (pc)", "Distance (ly)",
            "Temperature", "RA (deg)", "DEC (deg)", "App. Magnitude (V)",
        ]
        row = [
            result.get("sp_type") or "N/A",
            _fmtf(plx, 4),
            _fmtf(parsec, 4),
            _fmtf(ly, 4),
            f"{int(teff)} K" if teff is not None else "N/A",
            _fmtf(ra, 6),
            _fmtf(dec, 6),
            _fmtf(vmag, 3),
        ]

        table = self.make_table(headers, [row])
        table.setSortingEnabled(False)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        props_layout.addWidget(table)
        fit_table_height(table)

        # ── Assemble tab widget ───────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.addTab(props_widget, "Star Properties")

        # Phase M5: GCNS cross-reference (silent when absent — no Gaia id / not in GCNS).
        gcns = result.get("gcns")
        if gcns is not None:
            tabs.addTab(_build_gcns_tab(gcns, result), "GCNS")

        hypatia = result.get("hypatia")
        if hypatia is not None:
            tabs.addTab(build_hypatia_tab(hypatia), "Hypatia")

            if mpl_available() and "error" not in hypatia:
                try:
                    ab_data = core.viz.prepare_abundance_profile(hypatia)
                    if "error" not in ab_data:
                        ab_canvas, ab_toolbar = make_abundance_canvas(
                            None, ab_data, hypatia.get("star_name", "")
                        )
                        if ab_canvas is not None:
                            ab_w = wrap_scrollable(None, ab_canvas, ab_toolbar)
                            tabs.addTab(ab_w, "Abundance Profile")
                except Exception:
                    log_viz_error("Abundance Profile")

                # Kinematics (Toomre) — only when U/V/W are all present (Phase O O11).
                try:
                    kin_w = make_kinematics_tab(hypatia)
                    if kin_w is not None:
                        tabs.addTab(kin_w, "Kinematics")
                except Exception:
                    log_viz_error("Kinematics")

        self.add_result_widget(tabs)

        # Point the "📖 Wikipedia" button at this star's tab widget (rebuilt each render).
        self._set_wiki_context(
            tabs,
            designations=result.get("designations"),
            main_id=result.get("main_id"),
            star_label=result.get("main_id") or self._last_star,
        )
