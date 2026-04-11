# gui/panels/distance_stars.py — Options 18, 19, 20: star distance and proximity.
#
# A single DistanceStarsPanel with three tabs:
#   "Between 2 Stars"          — option 18
#   "Within Distance of Sol"   — option 19
#   "Within Distance of Star"  — option 20

from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators


# ── Option 18 tab ─────────────────────────────────────────────────────────────

class _BetweenStarsTab(QWidget):
    """Two star name inputs → distance in ly (and AU if < 0.5 ly)."""

    def __init__(self, parent_panel: "DistanceStarsPanel"):
        super().__init__()
        self._panel = parent_panel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._star1 = QLineEdit()
        self._star1.setPlaceholderText("e.g. Sol, Vega, Alpha Centauri")
        form.addRow("Star 1:", self._star1)

        self._star2 = QLineEdit()
        self._star2.setPlaceholderText("e.g. Epsilon Eridani, HD 10700")
        form.addRow("Star 2:", self._star2)
        layout.addLayout(form)

        self._btn = QPushButton("Calculate")
        self._btn.clicked.connect(self._calculate)
        self._star2.returnPressed.connect(self._calculate)
        layout.addWidget(self._btn)

        self._result_area = QVBoxLayout()
        layout.addLayout(self._result_area)
        layout.addStretch()

    def _clear(self):
        while self._result_area.count():
            item = self._result_area.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _calculate(self):
        s1 = self._star1.text().strip()
        s2 = self._star2.text().strip()
        if not s1 or not s2:
            return
        self._clear()
        self._panel.run_in_background(
            core.calculators.compute_distance_between_stars,
            s1, s2,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._clear()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._result_area.addWidget(lbl)
            return

        s1 = result["star1_info"]
        s2 = result["star2_info"]

        headers = ["Star", "Star Designations", "RA", "DEC", "Light Years"]
        rows = [
            [s1["name"], s1["desig_str"], s1.get("ra_hms", ""), s1.get("dec_dms", ""), f"{s1['ly']:.4f}"],
            [s2["name"], s2["desig_str"], s2.get("ra_hms", ""), s2.get("dec_dms", ""), f"{s2['ly']:.4f}"],
        ]

        from gui.panels.base import ResultPanel as _RP
        model_view = self._panel.make_table(headers, rows)
        model_view.setSortingEnabled(False)
        self._result_area.addWidget(model_view)

        dist_ly = result["distance_ly"]
        dist_au = result.get("distance_au")
        dist_text = f"<b>Distance:</b> {dist_ly:.4f} Light Years"
        if dist_au is not None:
            dist_text += f"  /  {dist_au:.2f} AU"
        lbl = QLabel(dist_text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result_area.addWidget(lbl)


# ── Option 19 tab ─────────────────────────────────────────────────────────────

class _WithinDistanceSolTab(QWidget):
    """Distance limit input → list of stars in starSystems.csv within that range of Sol."""

    def __init__(self, parent_panel: "DistanceStarsPanel"):
        super().__init__()
        self._panel = parent_panel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        self._btn = QPushButton("Search")
        self._btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        form.addRow(self._btn)
        layout.addLayout(form)

        self._result_area = QVBoxLayout()
        layout.addLayout(self._result_area, 1)

    def _clear(self):
        while self._result_area.count():
            item = self._result_area.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _search(self):
        raw = self._limit.text().strip()
        try:
            limit_ly = float(raw)
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self._clear()
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._result_area.addWidget(lbl)
            return

        self._clear()
        self._panel.run_in_background(
            core.calculators.compute_stars_within_distance_of_sol,
            limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._clear()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._result_area.addWidget(lbl)
            return

        count = result["count"]
        limit = result["limit_ly"]
        lbl = QLabel(f"Stars within {limit} light years of Sol: <b>{count}</b>")
        self._result_area.addWidget(lbl)

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"], r["Spectral Type"], f"{r['Light Years']:.4f}"]
            for r in result["stars"]
        ]
        view = self._panel.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._result_area.addWidget(view, 1)


# ── Option 20 tab ─────────────────────────────────────────────────────────────

class _WithinDistanceStarTab(QWidget):
    """Star name + distance limit → stars in starSystems.csv within range."""

    def __init__(self, parent_panel: "DistanceStarsPanel"):
        super().__init__()
        self._panel = parent_panel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._star = QLineEdit()
        self._star.setPlaceholderText("e.g. Alpha Centauri, Vega, HIP 27989")
        form.addRow("Center Star:", self._star)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        self._btn = QPushButton("Search")
        self._btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        form.addRow(self._btn)
        layout.addLayout(form)

        self._result_area = QVBoxLayout()
        layout.addLayout(self._result_area, 1)

    def _clear(self):
        while self._result_area.count():
            item = self._result_area.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _search(self):
        star = self._star.text().strip()
        raw  = self._limit.text().strip()
        if not star:
            return
        try:
            limit_ly = float(raw)
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self._clear()
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self._result_area.addWidget(lbl)
            return

        self._clear()
        self._panel.run_in_background(
            core.calculators.compute_stars_within_distance_of_star,
            star, limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self._clear()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self._result_area.addWidget(lbl)
            return

        center = result["center"]
        count  = result["count"]
        limit  = result["limit_ly"]
        lbl = QLabel(f"Stars within {limit} light years of {center}: <b>{count}</b>")
        self._result_area.addWidget(lbl)

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"], r["Spectral Type"], f"{r['Distance']:.3f}"]
            for r in result["stars"]
        ]
        view = self._panel.make_table(headers, rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._result_area.addWidget(view, 1)


# ── Main panel ────────────────────────────────────────────────────────────────

class DistanceStarsPanel(ResultPanel):
    """Star distance and proximity panel (options 18, 19, 20) — three tabs."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        tabs = QTabWidget()
        tabs.addTab(_BetweenStarsTab(self),        "Between 2 Stars  [opt 18]")
        tabs.addTab(_WithinDistanceSolTab(self),   "Within Distance of Sol  [opt 19]")
        tabs.addTab(_WithinDistanceStarTab(self),  "Within Distance of Star  [opt 20]")
        self._layout.addWidget(tabs)
