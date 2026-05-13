# gui/panels/simbad.py — Option 1: SIMBAD Lookup Query.

from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QPushButton, QLabel, QWidget, QVBoxLayout, QTabWidget,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
from gui.panels.hypatia_tab import build_hypatia_tab, fit_table_height
from gui.visualizations.plot_helpers import mpl_available, make_abundance_canvas
import core.databases
import core.viz


def _simbad_with_hypatia(name: str) -> dict:
    result = core.databases.compute_simbad_lookup(name)
    if "error" not in result:
        result["hypatia"] = core.databases.compute_hypatia_data(result)
    return result


class SimbadPanel(ResultPanel):
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

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass   # results added dynamically in render()

    def _search(self):
        name = self._name_input.text().strip()
        if not name:
            return
        self.clear_results()
        self.run_in_background(_simbad_with_hypatia, name)

    def render(self, result: dict):
        self.clear_results()

        if "error" in result:
            self.show_error(result["error"])
            return

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
        props_layout.addWidget(table)
        fit_table_height(table)

        # ── Assemble tab widget ───────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.addTab(props_widget, "Star Properties")

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
                            ab_w = QWidget()
                            ab_l = QVBoxLayout(ab_w)
                            ab_l.setContentsMargins(4, 4, 4, 4)
                            ab_l.addWidget(ab_toolbar)
                            ab_l.addWidget(ab_canvas)
                            tabs.addTab(ab_w, "Abundance Profile")
                except Exception:
                    pass

        self.add_result_widget(tabs)
