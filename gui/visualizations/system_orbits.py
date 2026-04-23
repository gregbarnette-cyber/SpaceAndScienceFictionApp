# gui/visualizations/system_orbits.py — SystemOrbitsPanel (Phase E)

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPushButton, QLabel

from gui.panels.base import ResultPanel
import core.databases
import core.viz

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_SPACE_BG  = "#03030f"
_LABEL_CLR = "#cccccc"
_GRID_CLR  = "#1a1a3a"


class SystemOrbitsPanel(ResultPanel):
    """Phase E — Keplerian orbital diagram for a planetary system.

    Look up a star via SIMBAD → NASA Exoplanet Archive → draw elliptical orbits
    with a habitable-zone annulus overlay.
    """

    def build_inputs(self):
        if not _MPL_OK:
            return

        form = QFormLayout()
        self._name = QLineEdit(self)
        self._name.setPlaceholderText("e.g. 51 Pegasi, HD 209458, Tau Ceti")
        self._name.returnPressed.connect(self._search)
        form.addRow("Star Name / Designation:", self._name)

        self.run_btn = QPushButton("Load Orbits", self)
        self.run_btn.clicked.connect(self._search)
        form.addRow("", self.run_btn)

        self._layout.addLayout(form)
        self._input_count = self._layout.count()

    def build_results_area(self):
        if not _MPL_OK:
            lbl = QLabel("matplotlib is not installed.\nRun: pip install matplotlib", self)
            lbl.setStyleSheet("color: red;")
            self._layout.addWidget(lbl)

    # ── Search pipeline: SIMBAD → NASA archive → plot ──────────────────────────

    def _search(self):
        name = self._name.text().strip()
        if not name:
            return
        self.clear_results()
        self.set_status("Looking up star in SIMBAD…")
        self.run_in_background(
            core.databases.compute_simbad_lookup, name,
            on_result=self._on_simbad,
        )

    def _on_simbad(self, simbad_result: dict):
        if "error" in simbad_result:
            self.show_error(simbad_result["error"])
            return
        self.set_status("Querying NASA Exoplanet Archive…")
        self.run_in_background(
            core.databases.compute_planetary_systems_composite,
            simbad_result,
            on_result=self._on_archive,
            on_progress=self.set_status,
        )

    def _on_archive(self, result: dict):
        if "error" in result:
            self.show_error(result["error"])
            return

        planets = result.get("planets", [])
        orbit_data = core.viz.prepare_system_orbits(planets)
        if "error" in orbit_data:
            self.show_error(orbit_data["error"])
            return

        self.clear_results()
        self._render(orbit_data)

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _render(self, data: dict):
        orbits    = data["orbits"]
        hz_zones  = data["hz_zones"]
        max_au    = data["max_au"]
        star_name = data["star_name"]

        fig = Figure(figsize=(7, 7), facecolor=_SPACE_BG)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

        # HZ annulus (painted outside-in so inner regions cover outer ones)
        if hz_zones:
            for zone in reversed(hz_zones):
                ax.add_patch(Circle((0, 0), zone["outer"],
                                    color=zone["color"], alpha=0.18, zorder=1))
            # Outermost HZ boundary line for reference
            ax.add_patch(Circle((0, 0), hz_zones[-1]["outer"],
                                fill=False, edgecolor="#4499FF",
                                linewidth=0.8, linestyle=":", alpha=0.6, zorder=2))
            ax.add_patch(Circle((0, 0), hz_zones[0]["outer"],
                                fill=False, edgecolor="#CC3300",
                                linewidth=0.8, linestyle=":", alpha=0.6, zorder=2))

        # Planet orbits
        for orb in orbits:
            ax.plot(orb["x_pts"], orb["y_pts"],
                    color=orb["color"], linewidth=1.2, zorder=3,
                    label=f"{orb['name']}  (a={orb['sma']:.3f} AU)")
            # Mark the position at periastron (closest approach)
            ax.scatter([orb["peri"]], [0],
                       color=orb["color"], s=20, zorder=4)

        # Star at centre
        star_r = max_au * 0.015
        ax.add_patch(Circle((0, 0), star_r, color="#FFEE55", zorder=10))
        ax.text(0, star_r * 1.6, star_name or "★",
                color="#FFEE55", fontsize=7, ha="center", va="bottom",
                alpha=0.85, zorder=11)

        ax.set_xlim(-max_au, max_au)
        ax.set_ylim(-max_au, max_au)
        ax.set_xlabel("AU", color=_LABEL_CLR, fontsize=9)
        ax.set_ylabel("AU", color=_LABEL_CLR, fontsize=9)
        ax.tick_params(colors=_LABEL_CLR, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID_CLR)
        ax.grid(True, color=_GRID_CLR, linewidth=0.5, linestyle=":")

        title = self._name.text().strip()
        ax.set_title(f"Planetary Orbits  —  {title}",
                     color=_LABEL_CLR, fontsize=10, pad=8)

        # Planet legend
        ax.legend(loc="upper right", fontsize=7, framealpha=0.25,
                  labelcolor="white", facecolor="#111133", edgecolor="#444466")

        # HZ legend entries
        if hz_zones:
            import matplotlib.patches as mpatches
            hz_handles = [
                mpatches.Patch(facecolor=z["color"], alpha=0.45,
                               edgecolor="none", label=z["label"])
                for z in hz_zones[-2:]   # show only conservative and optimistic outer
            ]
            if hz_handles:
                ax2_leg = ax.legend(handles=hz_handles,
                                    loc="lower right", fontsize=6,
                                    framealpha=0.25, labelcolor="white",
                                    facecolor="#111133", edgecolor="#444466",
                                    title="HZ Zones", title_fontsize=6)
                ax.add_artist(ax2_leg)
                # Re-add planet legend (adding second legend removes first by default)
                ax.legend(loc="upper right", fontsize=7, framealpha=0.25,
                          labelcolor="white", facecolor="#111133",
                          edgecolor="#444466")

        fig.tight_layout(pad=1.2)

        toolbar = NavToolbar(canvas, self)
        self.add_result_widget(toolbar)
        self.add_result_widget(canvas)
