# gui/panels/honorverse.py — Options 15, 16, 17: Honorverse reference tables.
# Each option is its own independent panel class so the nav tree opens each
# in its own content area rather than combining them behind tabs.

from PySide6.QtWidgets import QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.science

_FOOTNOTE = (
    "* Merchantmen do not normally use these bands. "
    "This represents the maximum theoretical speed for them if they did.\n"
    "  Q-ships and merchant cruisers with reworked drives and compensators "
    "sometimes can reach these bands."
)


def _speed_str(xc: float, ly_hr: float, note: str = "") -> str:
    """Format an xC speed as 'X (Y ly/hr)[note]'."""
    if xc == 0:
        return "Currently Unattainable"
    s = f"{xc} ({ly_hr:.5f} ly/hr)"
    if note.strip():
        s += note
    return s


class HonorverseHyperPanel(ResultPanel):
    """Option 15 — Honorverse Hyper Limits by Spectral Class."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        limits = core.science.compute_honorverse_hyper_limits()
        headers = ["Spectral Class", "Light Minutes", "AUs"]
        rows = [
            [r["spectral_class"], f"{r['lm']:.2f}", f"{r['au']:.4f}"]
            for r in limits
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        self._layout.addWidget(view)


class HonorverseAccelPanel(ResultPanel):
    """Option 16 — Honorverse Acceleration by Mass Table."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        accel = core.science.compute_honorverse_acceleration_table()
        headers = [
            "Ship Mass (tons)",
            "Warship (Normal Space)", "Merchantship (Normal Space)",
            "Warship (Hyper Space)",  "Merchantship (Hyper Space)",
        ]
        rows = [
            [r["mass_range"], r["warship_normal"], r["merchant_normal"],
             r["warship_hyper"], r["merchant_hyper"]]
            for r in accel
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        self._layout.addWidget(view)


class HonorverseSpeedPanel(ResultPanel):
    """Option 17 — Honorverse Effective Speed by Hyper Band (two tables + footnote)."""

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        data = core.science.compute_honorverse_effective_speed()

        # ── Table 1: Alpha–Iota ───────────────────────────────────────────────
        t1_label = QLabel("Effective Speed by Hyper Band")
        t1_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self._layout.addWidget(t1_label)

        spd_headers = [
            "Band", "Translation Bleed-Off", "Velocity Multiplier",
            "Warship (xC)", "Merchantship (xC)",
        ]
        spd_rows = [
            [
                b["band"],
                b["bleed_off"],
                str(b["multiplier"]),
                _speed_str(b["warship_xc"],  b["warship_ly_hr"]),
                _speed_str(b["merchant_xc"], b["merchant_ly_hr"], b["merchant_note"]),
            ]
            for b in data["bands"]
        ]
        view1 = self.make_table(spd_headers, spd_rows)
        view1.setSortingEnabled(False)
        self._layout.addWidget(view1)

        # ── Footnote after table 1 ────────────────────────────────────────────
        note1 = QLabel(_FOOTNOTE)
        note1.setWordWrap(True)
        note1.setStyleSheet("font-style: italic; margin-bottom: 8px;")
        self._layout.addWidget(note1)

        # ── Table 2: Alpha–Omega (expanded) ───────────────────────────────────
        t2_label = QLabel("Effective Speed by Hyper Band (Expanded)")
        t2_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self._layout.addWidget(t2_label)

        exp_headers = ["Band", "Warship (xC)", "Merchantship (xC)"]
        exp_rows = [
            [
                b["band"],
                _speed_str(b["warship_xc"],  b["warship_ly_hr"]),
                _speed_str(b["merchant_xc"], b["merchant_ly_hr"], b["merchant_note"]),
            ]
            for b in data["expanded_bands"]
        ]
        view2 = self.make_table(exp_headers, exp_rows)
        view2.setSortingEnabled(False)
        self._layout.addWidget(view2)

        # ── Footnote after table 2 ────────────────────────────────────────────
        note2 = QLabel(_FOOTNOTE)
        note2.setWordWrap(True)
        note2.setStyleSheet("font-style: italic; margin-top: 4px;")
        self._layout.addWidget(note2)
