# gui/visualizations/hz_diagram.py — HabZoneDiagramPanel (Phase E)

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPushButton, QLabel, QVBoxLayout

from gui.panels.base import ResultPanel
import core.viz

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_SPACE_BG   = "#f5f5f5"
_LABEL_CLR  = "#333333"
_GRID_CLR   = "#cccccc"


class HabZoneDiagramPanel(ResultPanel):
    """Option E-3 — Habitable Zone Diagram.

    Draws concentric coloured rings for the six Kopparapu HZ boundaries.
    Pure math — no network call.
    """

    def build_inputs(self):
        if not _MPL_OK:
            return

        form = QFormLayout()

        self._teff = QLineEdit(self)
        self._teff.setPlaceholderText("e.g. 5778")
        form.addRow("Star Temperature (K):", self._teff)

        self._lum = QLineEdit(self)
        self._lum.setPlaceholderText("e.g. 1.0")
        form.addRow("Star Luminosity (L☉):", self._lum)

        self._layout.addLayout(form)

        self.run_btn = QPushButton("Draw Diagram", self)
        self.run_btn.clicked.connect(self._draw)
        self._layout.addWidget(self.run_btn)

        self._err = QLabel(self)
        self._err.setStyleSheet("color: red;")
        self._err.hide()
        self._layout.addWidget(self._err)

        for w in (self._teff, self._lum):
            w.returnPressed.connect(self._draw)

        self._input_count = self._layout.count()

    def build_results_area(self):
        if not _MPL_OK:
            lbl = QLabel("matplotlib is not installed.\nRun: pip install matplotlib", self)
            lbl.setStyleSheet("color: red;")
            self._layout.addWidget(lbl)

    # ── Drawing ────────────────────────────────────────────────────────────────

    def _draw(self):
        self._err.hide()
        try:
            teff = float(self._teff.text().strip())
            lum  = float(self._lum.text().strip())
        except ValueError:
            self._err.setText("Enter valid numbers for temperature and luminosity.")
            self._err.show()
            return

        result = core.viz.prepare_hz_diagram(teff, lum)
        if "error" in result:
            self._err.setText(result["error"])
            self._err.show()
            return

        self.clear_results()
        self._render(result, teff, lum)

    def _render(self, data: dict, teff: float, lum: float):
        zones   = data["zones"]
        max_au  = data["max_au"]

        fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

        # Paint zones as filled circles from outermost inward (layering trick).
        for zone in reversed(zones):
            ax.add_patch(Circle((0, 0), zone["outer"],
                                color=zone["color"], alpha=0.55, zorder=2))

        # Boundary lines and AU labels
        for zone in zones:
            ax.add_patch(Circle((0, 0), zone["outer"],
                                fill=False, edgecolor="#555555",
                                linewidth=0.8, linestyle="--", alpha=0.5, zorder=3))
            # Label at 45° angle
            lx = zone["outer"] * 0.717
            ly_ = zone["outer"] * 0.717
            ax.text(lx, ly_, f"{zone['outer']:.3f} AU",
                    color="#333333", fontsize=6.5, ha="left", va="bottom",
                    alpha=0.9, zorder=4)

        # Star at centre
        star_r = max_au * 0.018
        ax.add_patch(Circle((0, 0), star_r, color="#FFEE55", zorder=10))

        # Axis styling
        ax.set_xlim(-max_au, max_au)
        ax.set_ylim(-max_au, max_au)
        ax.set_xlabel("AU", color=_LABEL_CLR, fontsize=9)
        ax.set_ylabel("AU", color=_LABEL_CLR, fontsize=9)
        ax.tick_params(colors=_LABEL_CLR, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID_CLR)
        ax.grid(True, color=_GRID_CLR, linewidth=0.5, linestyle=":")
        ax.set_title(
            f"Habitable Zone  —  T = {teff:.0f} K,  L = {lum:.4f} L☉",
            color=_LABEL_CLR, fontsize=10, pad=8,
        )

        # Legend
        import matplotlib.patches as mpatches
        handles = [
            mpatches.Patch(facecolor=z["color"], edgecolor="#555555",
                           alpha=0.7, label=z["label"])
            for z in zones
        ]
        # Add "Too Cold" entry for the region beyond em
        handles.append(mpatches.Patch(facecolor=_SPACE_BG, edgecolor="#555555",
                                       alpha=0.7, label="Too Cold  (> Early Mars)"))
        ax.legend(handles=handles, loc="upper left",
                  fontsize=7, framealpha=0.85, labelcolor="#333333",
                  facecolor="#ffffff", edgecolor="#aaaaaa")

        fig.tight_layout(pad=1.2)

        toolbar = NavToolbar(canvas, self)
        self.add_result_widget(toolbar)
        self.add_result_widget(canvas)
