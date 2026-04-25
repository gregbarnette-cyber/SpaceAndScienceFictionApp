# gui/panels/distance_stars.py — Options 17, 18, 19: star distance and proximity.
# Each option has its own standalone panel.

from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QPushButton, QLabel, QSizePolicy,
    QTabWidget, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.calculators
import core.viz
from gui.visualizations.plot_helpers import mpl_available, make_star_map_canvas


# ── Option 17: Distance Between 2 Stars ──────────────────────────────────────

class DistanceBetweenStarsPanel(ResultPanel):
    """Two star name inputs → distance in light years  (option 17)."""

    def build_inputs(self):
        form = QFormLayout()

        self._star1 = QLineEdit()
        self._star1.setPlaceholderText("e.g. Sol, Vega, Alpha Centauri")
        form.addRow("Star 1:", self._star1)

        self._star2 = QLineEdit()
        self._star2.setPlaceholderText("e.g. Epsilon Eridani, HD 10700")
        form.addRow("Star 2:", self._star2)

        self.run_btn = QPushButton("Calculate")
        self.run_btn.clicked.connect(self._calculate)
        self._star2.returnPressed.connect(self._calculate)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _calculate(self):
        s1 = self._star1.text().strip()
        s2 = self._star2.text().strip()
        if not s1 or not s2:
            return
        self.clear_results()
        self.run_in_background(
            core.calculators.compute_distance_between_stars,
            s1, s2,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self.add_result_widget(lbl)
            return

        s1 = result["star1_info"]
        s2 = result["star2_info"]

        dist_ly = result["distance_ly"]
        dist_au = result.get("distance_au")
        dist_text = f"<b>Distance:</b> {dist_ly:.4f} Light Years"
        if dist_au is not None:
            dist_text += f"  /  {dist_au:.2f} AU"
        lbl = QLabel(dist_text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.add_result_widget(lbl)

        headers = ["Star", "Star Designations", "RA", "DEC", "Light Years"]
        rows = [
            [s1["name"], s1["desig_str"],
             s1.get("ra_hms", ""), s1.get("dec_dms", ""), f"{s1['ly']:.4f}"],
            [s2["name"], s2["desig_str"],
             s2.get("ra_hms", ""), s2.get("dec_dms", ""), f"{s2['ly']:.4f}"],
        ]
        table = self.make_table(headers, rows)
        table.setSortingEnabled(False)
        self.add_result_widget(table)


# ── Option 18: Stars Within Distance of Sol ───────────────────────────────────

class StarsWithinDistanceSolPanel(ResultPanel):
    """Distance limit → stars in starSystems.csv within that range of Sol  (option 18)."""

    def build_inputs(self):
        form = QFormLayout()

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        form.addRow(self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _search(self):
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self.clear_results()
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return

        self.clear_results()
        self.run_in_background(
            core.calculators.compute_stars_within_distance_of_sol,
            limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self.add_result_widget(lbl)
            return

        count = result["count"]
        limit = result["limit_ly"]
        lbl = QLabel(f"Stars within {limit} light years of Sol: <b>{count}</b>")
        self.add_result_widget(lbl)

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"],
             r["Spectral Type"], f"{r['Light Years']:.4f}"]
            for r in result["stars"]
        ]

        if mpl_available():
            tabs = QTabWidget()

            tbl_w = QWidget()
            tbl_l = QVBoxLayout(tbl_w)
            view = self.make_table(headers, rows)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            tbl_l.addWidget(view)
            tabs.addTab(tbl_w, "Table")

            map_data = core.viz.prepare_star_map_from_result(result)
            if "stars" in map_data and map_data["stars"]:
                for proj, xk, yk, xl, yl in [
                    ("X–Y (top-down)", "x", "y", "X (ly)", "Y (ly)"),
                    ("X–Z (edge-on)",  "x", "z", "X (ly)", "Z (ly)"),
                ]:
                    map_w = QWidget()
                    map_l = QVBoxLayout(map_w)
                    map_l.setContentsMargins(4, 4, 4, 4)
                    canvas, toolbar = make_star_map_canvas(
                        self, map_data["stars"],
                        title=f"Stars within {limit} ly of Sol  ({count} stars)",
                        xk=xk, yk=yk, xlabel=xl, ylabel=yl,
                    )
                    map_l.addWidget(toolbar)
                    map_l.addWidget(canvas)
                    tabs.addTab(map_w, f"Map {proj}")

            self.add_result_widget(tabs)
        else:
            view = self.make_table(headers, rows)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.add_result_widget(view)


# ── Option 19: Stars Within Distance of a Star ───────────────────────────────

class StarsWithinDistanceStarPanel(ResultPanel):
    """Star name + distance limit → stars within range  (option 19)."""

    def build_inputs(self):
        form = QFormLayout()

        self._star = QLineEdit()
        self._star.setPlaceholderText("e.g. Alpha Centauri, Vega, HIP 27989")
        form.addRow("Center Star:", self._star)

        self._limit = QLineEdit()
        self._limit.setPlaceholderText("e.g. 10.0")
        form.addRow("Distance Limit (Light Years):", self._limit)

        self.run_btn = QPushButton("Search")
        self.run_btn.clicked.connect(self._search)
        self._limit.returnPressed.connect(self._search)
        form.addRow(self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _search(self):
        star = self._star.text().strip()
        if not star:
            return
        try:
            limit_ly = float(self._limit.text().strip())
            if limit_ly <= 0:
                raise ValueError
        except ValueError:
            self.clear_results()
            lbl = QLabel("Distance must be a positive number.")
            lbl.setStyleSheet("color: red;")
            self.add_result_widget(lbl)
            return

        self.clear_results()
        self.run_in_background(
            core.calculators.compute_stars_within_distance_of_star,
            star, limit_ly,
            on_result=self._render,
        )

    def _render(self, result: dict):
        self.clear_results()
        if "error" in result:
            lbl = QLabel(result["error"])
            lbl.setStyleSheet("color: red;")
            lbl.setWordWrap(True)
            self.add_result_widget(lbl)
            return

        center = result["center"]
        count  = result["count"]
        limit  = result["limit_ly"]
        lbl = QLabel(f"Stars within {limit} light years of {center}: <b>{count}</b>")
        self.add_result_widget(lbl)

        if count == 0:
            return

        headers = ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"]
        rows = [
            [r["Star Name"], r["Star Designations"],
             r["Spectral Type"], f"{r['Distance']:.3f}"]
            for r in result["stars"]
        ]

        if mpl_available():
            tabs = QTabWidget()

            tbl_w = QWidget()
            tbl_l = QVBoxLayout(tbl_w)
            view = self.make_table(headers, rows)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            tbl_l.addWidget(view)
            tabs.addTab(tbl_w, "Table")

            map_data = core.viz.prepare_star_map_from_result(result)
            if "stars" in map_data and map_data["stars"]:
                for proj, xk, yk, xl, yl in [
                    ("X–Y (top-down)", "x", "y", "X (ly)", "Y (ly)"),
                    ("X–Z (edge-on)",  "x", "z", "X (ly)", "Z (ly)"),
                ]:
                    map_w = QWidget()
                    map_l = QVBoxLayout(map_w)
                    map_l.setContentsMargins(4, 4, 4, 4)
                    canvas, toolbar = make_star_map_canvas(
                        self, map_data["stars"],
                        title=f"Stars within {limit} ly of {center}  ({count} stars)",
                        xk=xk, yk=yk, xlabel=xl, ylabel=yl,
                    )
                    map_l.addWidget(toolbar)
                    map_l.addWidget(canvas)
                    tabs.addTab(map_w, f"Map {proj}")

            self.add_result_widget(tabs)
        else:
            view = self.make_table(headers, rows)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.add_result_widget(view)
