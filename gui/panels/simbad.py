# gui/panels/simbad.py — Option 1: SIMBAD Lookup Query.

from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QPushButton, QLabel, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.databases


class SimbadPanel(ResultPanel):
    """SIMBAD star lookup panel (option 1).

    Input:  Star name / designation text field.
    Output: Designation banner + star properties table.
    """

    def build_inputs(self):
        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Vega, HD 209458, Alpha Centauri")
        self._name_input.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name_input)

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        form.addRow("", self.run_btn)   # button in input column, directly below the field

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass   # results added dynamically in render()

    def _search(self):
        name = self._name_input.text().strip()
        if not name:
            return
        self.clear_results()
        self.run_in_background(core.databases.compute_simbad_lookup, name)

    def render(self, result: dict):
        self.clear_results()

        if "error" in result:
            self.show_error(result["error"])
            return

        # ── Designation banner ────────────────────────────────────────────────
        desig_str = result.get("desig_str", "N/A")
        banner = QLabel(f"<b>STAR DESIGNATIONS:</b><br>{desig_str}")
        banner.setWordWrap(True)
        banner.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.add_result_widget(banner)

        # ── Star properties table ─────────────────────────────────────────────
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
        self.add_result_widget(table)
