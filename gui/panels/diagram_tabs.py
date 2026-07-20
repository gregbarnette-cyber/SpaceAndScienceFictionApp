# gui/panels/diagram_tabs.py — shared diagram-tab builders for the Star Databases panels.
#
# Stateless QWidget factories: each takes (panel, planets) — `planets` being a list of
# dicts with NASA-style keys (`pl_orbsmax`/`pl_orbeccen`/`pl_orbincl`/`pl_bmasse`/`pl_rade`,
# and `st_teff`/`st_rad`/`st_spectype`/`hostname` on each row) — and returns an embedded
# matplotlib tab QWidget, or None when the data is insufficient. All chart drawing lives in
# `core.viz` (prep) + `gui.visualizations.plot_helpers` (canvas); these just wire prep→canvas
# →tab. Shared by the NASA panels (opts 3/4/5) and OecPanel (opt 7, which adapts OEC nodes
# to these keys). Extracted from nasa_exoplanet.py so no panel imports another panel's privates.

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup,
    QStackedWidget,
)
from PySide6.QtCore import Qt

import core.viz
import core.science
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_hz_strip_canvas, make_orbits_canvas,
    make_mass_radius_canvas, make_transit_canvas, make_size_comparison_canvas,
    wrap_orbits_with_solar_toggle,
)


# ── Phase 5: the shared HZ Rings/Strip toggle ────────────────────────────────────
# One control, wired into every panel's HZ Diagram tab. Rings is the default and its
# canvas (make_hz_canvas) is unchanged; Strip is the opt-in √AU view with planet-SMA
# markers. Both share the light HZ palette so they read as one tab.

_HZ_TOGGLE_QSS = """
QWidget#hzToggleBar QPushButton {
    padding: 3px 14px; border: 1px solid #b9c2d0; background: #f4f6fa;
    color: #465063; font-size: 12px;
}
QWidget#hzToggleBar QPushButton:first-child { border-top-left-radius: 6px; border-bottom-left-radius: 6px; }
QWidget#hzToggleBar QPushButton:last-child  { border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none; }
QWidget#hzToggleBar QPushButton:checked { background: #2f9e5a; color: #ffffff; border-color: #268a4d; }
"""


def _wrap_canvas_tab(canvas, toolbar):
    """A QWidget holding a matplotlib toolbar + canvas (the standard diagram-tab body)."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def wrap_hz_with_toggle(build_rings, build_strip):
    """Return a QWidget: a **Rings | Strip** segmented control over a QStackedWidget,
    Rings selected by default. `build_rings()` / `build_strip()` are zero-arg factories
    each returning a QWidget (or None). If Rings can't build → None; if Strip can't build
    → the bare Rings widget (no toggle) so nothing regresses."""
    rings_w = build_rings()
    if rings_w is None:
        return None
    strip_w = build_strip()
    if strip_w is None:
        return rings_w   # no strip (e.g. bands not computable) → plain rings, no toggle

    container = QWidget()
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(3)

    bar = QWidget()
    bar.setObjectName("hzToggleBar")
    bar.setStyleSheet(_HZ_TOGGLE_QSS)
    row = QHBoxLayout(bar)
    row.setContentsMargins(6, 4, 6, 0)
    row.setSpacing(0)
    lbl = QLabel("HZ view:")
    lbl.setContentsMargins(0, 0, 8, 0)
    row.addWidget(lbl)
    grp = QButtonGroup(container)
    grp.setExclusive(True)
    rings_btn = QPushButton("Rings")
    strip_btn = QPushButton("Strip")
    for b in (rings_btn, strip_btn):
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        grp.addButton(b)
        row.addWidget(b)
    rings_btn.setChecked(True)
    row.addStretch()
    v.addWidget(bar)

    stack = QStackedWidget()
    stack.addWidget(rings_w)   # index 0 (default)
    stack.addWidget(strip_w)   # index 1
    v.addWidget(stack, 1)

    rings_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
    strip_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
    return container


def _hz_toggle_tab(panel, teff, lum, title, eeid_au=None, planets=None, markers=None):
    """Build the HZ Diagram tab as a Rings/Strip toggle (Rings default). `planets` is a
    list of {"name","au"} for the strip markers ([] / None for single-star panels →
    bands only). Returns a QWidget, or None when the HZ isn't computable."""
    if not mpl_available():
        return None
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None

    def build_rings():
        canvas, toolbar = make_hz_canvas(
            panel, hz_data["zones"], hz_data["max_au"],
            title=title, eeid_au=eeid_au, markers=markers)
        return _wrap_canvas_tab(canvas, toolbar)

    def build_strip():
        strip = core.viz.prepare_hz_strip(teff, lum, planets)
        if "error" in strip:
            return None
        canvas, toolbar = make_hz_strip_canvas(
            panel, strip, title=title, eeid_au=eeid_au, markers=markers)
        if canvas is None:
            return None
        return _wrap_canvas_tab(canvas, toolbar)

    return wrap_hz_with_toggle(build_rings, build_strip)


def _fval(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _make_hz_tab(panel, rows_or_row):
    """Return the HZ Diagram tab (Rings/Strip toggle), or None if data is missing.
    NASA planet rows carry `pl_orbsmax`, so the Strip view gets planet-SMA markers."""
    if not mpl_available():
        return None
    rows = rows_or_row if isinstance(rows_or_row, list) else [rows_or_row or {}]
    row = rows[0] if rows else {}
    teff   = _fval(row.get("st_teff"))
    st_rad = _fval(row.get("st_rad"))
    st_lum = _fval(row.get("st_lum"))
    if teff is None:
        return None
    if st_rad is not None:
        lum = st_rad ** 2 * (teff / 5778.0) ** 4
    elif st_lum is not None:
        lum = 10 ** st_lum
    else:
        return None
    planets = []
    for r in rows:
        au = _fval(r.get("pl_orbsmax"))
        if au:
            planets.append({"name": r.get("pl_name") or "planet", "au": au})
    return _hz_toggle_tab(
        panel, teff, lum,
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=_fval(row.get("st_eei_orbsep")), planets=planets)


def _make_hz_tab_exocat(panel, row):
    """HZ tab for Mission Exocat rows (uses st_teff / st_rad; eeid from st_eeidau).
    Star-level row → the Strip shows bands only (no per-planet SMA)."""
    if not mpl_available() or not row:
        return None
    teff   = _fval(row.get("st_teff"))
    st_rad = _fval(row.get("st_rad"))
    st_lbol= _fval(row.get("st_lbol"))
    if teff is None:
        return None
    if st_rad is not None:
        lum = st_rad ** 2 * (teff / 5778.0) ** 4
    elif st_lbol is not None:
        lum = st_lbol
    else:
        return None
    return _hz_toggle_tab(
        panel, teff, lum,
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=_fval(row.get("st_eeidau")), planets=[])


def _hyper_au_for(sp_type):
    """Resolve a host spectral type → Honorverse hyper-limit AU, or None (O10b)."""
    if not sp_type:
        return None
    hl = core.science.compute_hyper_limit_for_spectral_type(str(sp_type))
    return hl["au"] if hl else None


def _make_orbits_tab(panel, planets, star_name="", sp_type=None):
    """Return a QWidget with an embedded orbital diagram, or None if insufficient data.

    The diagram carries a "Show Solar System reference" overlay checkbox (Phase O · O4)
    and, when the host spectral type resolves a Honorverse hyper limit (Phase O · O10b),
    a "Show Honorverse Hyper Limit (fiction)" checkbox.
    """
    if not mpl_available():
        return None
    orbit_data = core.viz.prepare_system_orbits(planets)
    if "error" in orbit_data:
        return None
    hyper_au = _hyper_au_for(sp_type)

    # Phase P V6/V7: snow-line + solvent-zone overlays from the host luminosity.
    ov = core.viz.prepare_orbit_overlays(orbit_data.get("luminosity"))
    snow_au = ov.get("snow_au")
    solvent_options = ov.get("solvent_options")

    def _build(solar_overlay, show_hyper, snow, solvent_bands):
        return make_orbits_canvas(
            panel,
            orbit_data["orbits"],
            orbit_data["hz_zones"],
            orbit_data["max_au"],
            star_name=star_name,
            solar_overlay=solar_overlay,
            hyper_au=hyper_au if show_hyper else None,
            snow_au=snow,
            solvent_bands=solvent_bands,
        )

    return wrap_orbits_with_solar_toggle(
        panel, _build, hyper_au=hyper_au,
        snow_au=snow_au, solvent_options=solvent_options)


def _make_mass_radius_tab(panel, planets, mass_key="pl_bmasse",
                          radius_key="pl_rade", name_key="pl_name"):
    """Return a QWidget with an embedded Mass–Radius diagram, or None (Phase O · O3).

    Added only when ≥1 planet carries both a positive mass and radius. Generic over
    NASA (pl_bmasse/pl_rade/pl_name — the defaults) and HWC (P_MASS/P_RADIUS/P_NAME)
    rows via the column keys.
    """
    if not mpl_available():
        return None
    mr_data = core.viz.prepare_mass_radius(planets, mass_key, radius_key, name_key)
    if "error" in mr_data:
        return None
    canvas, toolbar = make_mass_radius_canvas(panel, mr_data)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_transit_tab(panel, planets):
    """Return a QWidget with an embedded Transit Geometry diagram, or None (Phase O · O13).

    Added on opts 3 + Map only when ≥1 planet has a host stellar radius and a
    measured orbital inclination (NASA `st_rad`/`pl_orbsmax`/`pl_orbincl`).
    """
    if not mpl_available():
        return None
    tg_data = core.viz.prepare_transit_geometry(planets)
    if "error" in tg_data:
        return None
    canvas, toolbar = make_transit_canvas(panel, tg_data)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_size_tab(panel, planets, radius_key="pl_rade", name_key="pl_name"):
    """Return a QWidget with a Planet Size-Comparison strip, or None (Phase O · O14).

    Added on opts 3/6/Map only when ≥1 planet carries a radius. Generic over NASA
    (pl_rade/pl_name — the defaults) and HWC (P_RADIUS/P_NAME) via the column keys.
    """
    if not mpl_available():
        return None
    canvas, toolbar = make_size_comparison_canvas(panel, planets, radius_key, name_key)
    if canvas is None:
        return None
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w
