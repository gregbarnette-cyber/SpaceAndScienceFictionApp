# gui/visualizations/star_map.py — StarMapPanel (Phase E)

import os

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QFormLayout, QSizePolicy,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.viz

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_SPACE_BG  = "#f5f5f5"
_LABEL_CLR = "#333333"
_GRID_CLR  = "#cccccc"

# Axis-projection options: (label, x_key, y_key, xlabel, ylabel)
_PROJECTIONS = [
    ("X – Y  (top-down)",  "x", "y", "X  (ly)", "Y  (ly)"),
    ("X – Z  (edge-on)",   "x", "z", "X  (ly)", "Z  (ly)"),
    ("Y – Z  (side view)", "y", "z", "Y  (ly)", "Z  (ly)"),
]


class StarMapPanel(ResultPanel):
    """Phase E — 2D scatter plot of stars from starSystems.csv.

    Stars are colour-coded by spectral class.  Hovering a point shows the
    star name in a tooltip annotation.
    """

    def build_inputs(self):
        if not _MPL_OK:
            return

        bar = QHBoxLayout()

        self.run_btn = QPushButton("Load Star Map", self)
        self.run_btn.clicked.connect(self._load)
        bar.addWidget(self.run_btn)

        bar.addWidget(QLabel("Projection:", self))
        self._proj = QComboBox(self)
        for label, *_ in _PROJECTIONS:
            self._proj.addItem(label)
        self._proj.currentIndexChanged.connect(self._redraw)
        bar.addWidget(self._proj)

        bar.addWidget(QLabel("Max distance (ly):", self))
        self._limit = QLineEdit(self)
        self._limit.setPlaceholderText("all")
        self._limit.setFixedWidth(70)
        self._limit.returnPressed.connect(self._redraw)
        bar.addWidget(self._limit)

        bar.addStretch()
        self._layout.addLayout(bar)
        self._input_count = self._layout.count()

        self._stars_cache = None  # cached result from prepare_star_map()

    def build_results_area(self):
        if not _MPL_OK:
            lbl = QLabel("matplotlib is not installed.\nRun: pip install matplotlib", self)
            lbl.setStyleSheet("color: red;")
            self._layout.addWidget(lbl)

    # ── Loading ────────────────────────────────────────────────────────────────

    def _load(self):
        self.clear_results()
        self.run_in_background(core.viz.prepare_star_map, on_result=self._on_loaded)

    def _on_loaded(self, result: dict):
        if "error" in result:
            self.show_error(result["error"])
            return
        self._stars_cache = result["stars"]
        self._redraw()

    # ── (Re)draw whenever projection or filter changes ─────────────────────────

    def _redraw(self):
        if self._stars_cache is None:
            return
        self.clear_results()

        proj_idx = self._proj.currentIndex()
        _, xk, yk, xlabel, ylabel = _PROJECTIONS[proj_idx]

        limit_text = self._limit.text().strip()
        try:
            limit_ly = float(limit_text)
        except ValueError:
            limit_ly = None

        stars = self._stars_cache
        if limit_ly is not None:
            stars = [s for s in stars if s["ly"] <= limit_ly]

        if not stars:
            self.show_error("No stars to display (check distance limit).")
            return

        self._build_plot(stars, xk, yk, xlabel, ylabel)

    def _build_plot(self, stars: list, xk: str, yk: str, xlabel: str, ylabel: str):
        xs     = [s[xk]    for s in stars]
        ys     = [s[yk]    for s in stars]
        colors = [s["color"] for s in stars]
        names  = [s["name"]  for s in stars]
        sizes  = [30 if s["name"] == "Sol" else 12 for s in stars]

        fig = Figure(figsize=(7, 7), facecolor=_SPACE_BG)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111, facecolor=_SPACE_BG)

        sc = ax.scatter(xs, ys, c=colors, s=sizes, linewidths=0, alpha=0.85,
                        picker=True, pickradius=4, zorder=3)

        # Sol marker
        if stars[0]["name"] == "Sol":
            ax.scatter([xs[0]], [ys[0]], c=colors[0], s=80,
                       marker="*", zorder=5, edgecolors="#333333", linewidths=0.5)

        ax.set_facecolor(_SPACE_BG)
        ax.set_xlabel(xlabel, color=_LABEL_CLR, fontsize=9)
        ax.set_ylabel(ylabel, color=_LABEL_CLR, fontsize=9)
        ax.tick_params(colors=_LABEL_CLR, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID_CLR)
        ax.grid(True, color=_GRID_CLR, linewidth=0.5, linestyle=":")
        ax.set_title(
            f"Star Map  ({len(stars)} stars)",
            color=_LABEL_CLR, fontsize=10, pad=8,
        )

        # Spectral-class legend
        seen = {}
        for s in stars:
            cls = s["sp_type"][0].upper() if s["sp_type"] else "?"
            if cls not in seen:
                seen[cls] = s["color"]
        import matplotlib.patches as mpatches
        handles = [mpatches.Patch(color=c, label=f"Class {k}")
                   for k, c in sorted(seen.items())]
        if handles:
            ax.legend(handles=handles, loc="upper right", fontsize=7,
                      framealpha=0.85, labelcolor="#333333",
                      facecolor="#ffffff", edgecolor="#aaaaaa")

        # Hover annotation
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0", ec="#2266cc",
                      lw=0.8, alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="#2266cc", lw=0.8),
            color="#333333", fontsize=8, zorder=10,
        )
        annot.set_visible(False)

        def _on_motion(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return
            cont, ind = sc.contains(event)
            if cont:
                idx = ind["ind"][0]
                annot.xy = (xs[idx], ys[idx])
                name = names[idx]
                ly   = stars[idx]["ly"]
                annot.set_text(f"{name}\n{ly:.2f} ly")
                annot.set_visible(True)
            else:
                annot.set_visible(False)
            canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _on_motion)
        fig.tight_layout(pad=1.2)

        toolbar = NavToolbar(canvas, self)
        self.add_result_widget(toolbar)
        self.add_result_widget(canvas)
