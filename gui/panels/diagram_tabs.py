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

from PySide6.QtWidgets import QWidget, QVBoxLayout

import core.viz
import core.science
from gui.visualizations.plot_helpers import (
    mpl_available, make_hz_canvas, make_orbits_canvas, make_mass_radius_canvas,
    make_transit_canvas, make_size_comparison_canvas, wrap_orbits_with_solar_toggle,
)


def _fval(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _make_hz_tab(panel, rows_or_row):
    """Return a QWidget with an embedded HZ diagram, or None if data is missing."""
    if not mpl_available():
        return None
    if isinstance(rows_or_row, list):
        row = rows_or_row[0] if rows_or_row else {}
    else:
        row = rows_or_row or {}
    teff   = _fval(row.get("st_teff") or row.get("st_teff"))
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
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None
    eeid_au = _fval(row.get("st_eei_orbsep"))
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    canvas, toolbar = make_hz_canvas(
        panel, hz_data["zones"], hz_data["max_au"],
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=eeid_au,
    )
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


def _make_hz_tab_exocat(panel, row):
    """HZ tab for Mission Exocat rows (uses st_teff / st_rad; eeid from st_eeidau)."""
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
    hz_data = core.viz.prepare_hz_diagram(teff, lum)
    if "error" in hz_data:
        return None
    eeid_au = _fval(row.get("st_eeidau"))
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(4, 4, 4, 4)
    canvas, toolbar = make_hz_canvas(
        panel, hz_data["zones"], hz_data["max_au"],
        title=f"Habitable Zone  (T={teff:.0f} K, L={lum:.4f} L☉)",
        eeid_au=eeid_au,
    )
    lay.addWidget(toolbar)
    lay.addWidget(canvas)
    return w


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
