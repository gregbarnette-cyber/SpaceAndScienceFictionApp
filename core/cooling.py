"""Phase U — cooling-primary (white-dwarf / brown-dwarf) HZ-residence calculator.

A cooling primary has no equilibrium luminosity: its habitable zone migrates inward as
it cools, so a planet at a fixed orbit is habitable only for a finite *residence time*.
This module models that with bundled static cooling tracks (``core.cooling_tables``) +
the existing Kopparapu HZ engine, in three modes:

  * **Mode 1 — snapshot:** HZ at one epoch (``cooling_age_gyr`` or ``teff``).
  * **Mode 2 — residence:** how long a planet at ``sma_au`` stays in the HZ.
  * **Mode 3 — CHZ band (default):** the orbit range whose residence ≥ a threshold.

Reuses ``equations.compute_habitable_zone`` (per-epoch band) and
``equations.compute_roche_limit`` (CHZ inner-edge cross-check) verbatim — no HZ or Roche
physics is re-derived here. Self-validating (curated ``{"error"}`` for bad input), the
Phase-H/P contract. Out-of-Kopparapu-range Teff is **flagged, not clamped** (the
``circumbinary-hz`` convention). Pure math: no network, no DB, no RNG, no time.
"""

import math

from core.equations import (
    compute_habitable_zone,
    compute_roche_limit,
    _KOPPARAPU_TEFF_MIN,
    _KOPPARAPU_TEFF_MAX,
)
from core import cooling_tables

# ── constants ────────────────────────────────────────────────────────────────
_MJUP_TO_MSUN = 9.543e-4          # 1 Jupiter mass in solar masses
_MSUN_TO_MEARTH = 332946.0        # 1 solar mass in Earth masses (for the Roche call)
_RSUN_TO_REARTH = 109.2           # 1 solar radius in Earth radii (for the Roche call)
_TEFF_SUN_K = 5772.0              # IAU nominal solar Teff (L↔Teff closure guard)

_WD_MASS_DEFAULT = 0.60           # M_sun
_BD_MASS_DEFAULT_MJUP = 50.0      # M_Jup

# conservative HZ = runaway-greenhouse → maximum-greenhouse; optimistic = recent-venus → early-mars
_EDGE_KEYS = {
    "conservative": ("rg", "mg"),
    "optimistic":   ("rv", "em"),
}

_HZ_VALID_TEFF = [_KOPPARAPU_TEFF_MIN, _KOPPARAPU_TEFF_MAX]
_AGE_EPS = 1e-9


class _OffGrid(Exception):
    """Raised by the interpolators when a (mass, age, teff) request leaves the table."""


# ── track interpolation ──────────────────────────────────────────────────────
def _tracks_for(track):
    if track == "wd":
        return cooling_tables.get_wd_tracks(), "M_sun"
    return cooling_tables.get_bd_tracks(), "M_Jup"


def _interp_age(rows, age):
    """Interpolate one mass's sequence at ``age`` → (teff_k, log10_l, radius_rsun).

    ``rows`` are (age_gyr, teff_k, log10_l_lsun, radius_rsun) sorted ascending by age.
    Age below the track start clamps to the first row (tracks start at age 0); age
    beyond the last row is off-grid (older than the model covers).
    """
    if age <= rows[0][0] + _AGE_EPS:
        return rows[0][1], rows[0][2], rows[0][3]
    if age > rows[-1][0] + _AGE_EPS:
        raise _OffGrid(f"cooling age {age:g} Gyr is beyond the track (max "
                       f"{rows[-1][0]:g} Gyr)")
    for i in range(1, len(rows)):
        a0, t0, l0, r0 = rows[i - 1]
        a1, t1, l1, r1 = rows[i]
        if age <= a1 + _AGE_EPS:
            w = (age - a0) / (a1 - a0)
            return (t0 + w * (t1 - t0),
                    l0 + w * (l1 - l0),       # interpolate L in log10 space
                    r0 + w * (r1 - r0))
    return rows[-1][1], rows[-1][2], rows[-1][3]


def _interp_track(track, grid_mass, age):
    """(track, grid_mass, age) → (teff_k, lum_lsun, radius_rsun). Raises _OffGrid.

    Teff and radius are interpolated linearly; **luminosity is then derived from them by
    the exact identity ``L/L_sun = (R/R_sun)^2 (Teff/Teff_sun)^4``** rather than
    interpolated independently. The table's stored ``log10_l`` column would otherwise
    drift off that identity between sparse grid points; deriving L keeps every
    interpolated epoch physically self-consistent (and matches each grid node, which
    satisfies the identity by construction — see the table closure test).
    """
    tracks, unit = _tracks_for(track)
    if not tracks:
        raise _OffGrid(f"no {track} cooling tracks are bundled yet")
    masses = sorted(tracks)
    if grid_mass < masses[0] - 1e-6 or grid_mass > masses[-1] + 1e-6:
        raise _OffGrid(f"mass {grid_mass:g} {unit} is outside the bundled {track} "
                       f"cooling grid (available: {masses})")
    if grid_mass in tracks or grid_mass <= masses[0] or grid_mass >= masses[-1]:
        key = grid_mass if grid_mass in tracks else (masses[0] if grid_mass <= masses[0] else masses[-1])
        t, _, r = _interp_age(tracks[key], age)
    else:
        m_lo = max(m for m in masses if m <= grid_mass)
        m_hi = min(m for m in masses if m >= grid_mass)
        t0, _, r0 = _interp_age(tracks[m_lo], age)
        t1, _, r1 = _interp_age(tracks[m_hi], age)
        w = (grid_mass - m_lo) / (m_hi - m_lo)
        t = t0 + w * (t1 - t0)
        r = r0 + w * (r1 - r0)
    lum = r ** 2 * (t / _TEFF_SUN_K) ** 4
    return t, lum, r


def _track_max_age(track, grid_mass):
    """Largest age covered for this mass (min over bracketing masses, to stay in-grid)."""
    tracks, _ = _tracks_for(track)
    masses = sorted(tracks)
    if grid_mass in tracks:
        return tracks[grid_mass][-1][0]
    lo = [m for m in masses if m <= grid_mass] or [masses[0]]
    hi = [m for m in masses if m >= grid_mass] or [masses[-1]]
    return min(tracks[lo[-1]][-1][0], tracks[hi[0]][-1][0])


def _age_for_teff(track, grid_mass, teff):
    """Cooling age (Gyr) at which the track reaches ``teff`` (Teff decreases with age)."""
    amax = _track_max_age(track, grid_mass)
    t_young, _, _ = _interp_track(track, grid_mass, 0.0)
    t_old, _, _ = _interp_track(track, grid_mass, amax)
    if teff > t_young + 1e-6 or teff < t_old - 1e-6:
        raise _OffGrid(f"Teff {teff:g} K is outside this track's range "
                       f"[{t_old:g}, {t_young:g}] K")
    return _bisect(lambda a: _interp_track(track, grid_mass, a)[0] - teff, 0.0, amax)


# ── HZ edge helpers (reuse compute_habitable_zone) ───────────────────────────
def _zone_au(teff, lum, key):
    """AU of one Kopparapu zone edge; +inf if the polynomial is too extrapolated to solve."""
    try:
        zones = compute_habitable_zone(teff, lum)
    except (ValueError, ZeroDivisionError):
        return float("inf")
    for z in zones:
        if z["key"] == key:
            return z["au"]
    return float("inf")


def _edge_au(track, grid_mass, age, key):
    teff, lum, _ = _interp_track(track, grid_mass, age)
    return _zone_au(teff, lum, key)


# ── root finder ──────────────────────────────────────────────────────────────
def _bisect(f, lo, hi, tol=1e-4, maxit=200):
    """Bisection root of a monotone-decreasing f on [lo, hi] (f(lo) ≥ 0 ≥ f(hi))."""
    flo = f(lo)
    if flo <= 0:
        return lo
    for _ in range(maxit):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(hi - lo) < tol:
            return mid
        if fm > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _out_of_range(teff):
    return teff < _KOPPARAPU_TEFF_MIN or teff > _KOPPARAPU_TEFF_MAX


# ── mode 2: residence at a fixed orbit ───────────────────────────────────────
def _residence_at(track, grid_mass, sma_au, hz_edge, age_max_gyr):
    """Entry/exit ages and residence time for a planet at ``sma_au``.

    As the primary cools both HZ edges shrink in AU. A planet at fixed ``a`` is too hot
    while the inner (hot) edge is still outside ``a``; it enters when the inner edge
    crosses ``a``, stays habitable until the outer (cold) edge crosses ``a``, then is too
    cold. "Never habitable" is a normal result (ever_habitable=False), not an error.

    **The Kopparapu validity gate is asymmetric — hot-side only.** Above ~7200 K the
    polynomial is unreliable and eventually returns a negative S_eff (it *raises*), so the
    young hot-dwarf phase is genuinely undefined and is gated out — otherwise a far orbit
    would show a spurious habitable window while the dwarf blazes. The cool side is the
    opposite: S_eff stays positive and smoothly varying well below 2600 K (down to a few
    hundred K), and a cooling brown/white dwarf's HZ keeps migrating inward through that
    regime — so the cold extrapolation is **allowed and flagged** (``entry/exit_out_of_range``
    when a crossing Teff is outside [2600, 7200] K), not gated. This is what lets a planet
    track a cooling BD's HZ for Gyr (Bolmont 2011/2017). ``truncated_at_age_max`` flags a
    window still open at the integration ceiling.
    """
    ik, ok = _EDGE_KEYS[hz_edge]
    amax = min(age_max_gyr, _track_max_age(track, grid_mass))

    res = {
        "ever_habitable": False, "entry_age_gyr": None, "exit_age_gyr": None,
        "residence_gyr": None, "entry_teff_k": None, "exit_teff_k": None,
        "entry_out_of_range": None, "exit_out_of_range": None,
        "truncated_at_age_max": False,
    }

    # Hot-side gate only: search from the age where Teff has cooled to 7200 K (or 0 if the
    # track is already cooler than that) through the full track. No cold-side gate.
    t_young = _interp_track(track, grid_mass, 0.0)[0]
    valid_lo = 0.0 if t_young <= _KOPPARAPU_TEFF_MAX else \
        _bisect(lambda a: _interp_track(track, grid_mass, a)[0] - _KOPPARAPU_TEFF_MAX, 0.0, amax)
    if amax <= valid_lo:
        return res

    def au_in(a):
        return _edge_au(track, grid_mass, a, ik)

    def au_out(a):
        return _edge_au(track, grid_mass, a, ok)

    # never habitable: hot edge never reaches a over the (in-range) track (always too hot),
    # or cold edge already interior to a at the hottest in-range epoch (always too cold).
    if au_in(amax) - sma_au > 0:
        return res
    if au_out(valid_lo) - sma_au < 0:
        return res

    # entry: inner (hot) edge crosses a (clipped to the hot-validity bound if it would
    # otherwise cross while the dwarf is still hotter than 7200 K)
    if au_in(valid_lo) - sma_au <= 0:
        entry = valid_lo
    else:
        entry = _bisect(lambda a: au_in(a) - sma_au, valid_lo, amax)

    # exit: outer (cold) edge crosses a; if it never does within the track, truncate
    if au_out(amax) - sma_au >= 0:
        exit_age = None
        res["truncated_at_age_max"] = True
    else:
        exit_age = _bisect(lambda a: au_out(a) - sma_au, valid_lo, amax)

    eff_exit = exit_age if exit_age is not None else amax
    if eff_exit <= entry:
        return res

    entry_teff = _interp_track(track, grid_mass, entry)[0]
    exit_teff = _interp_track(track, grid_mass, eff_exit)[0]
    res["ever_habitable"] = True
    res["entry_age_gyr"] = entry
    res["exit_age_gyr"] = exit_age
    res["residence_gyr"] = eff_exit - entry
    res["entry_teff_k"] = entry_teff
    res["exit_teff_k"] = exit_teff
    res["entry_out_of_range"] = _out_of_range(entry_teff)
    res["exit_out_of_range"] = _out_of_range(exit_teff)
    return res


# ── mode 3: continuously-habitable-zone band ─────────────────────────────────
def _chz_band(track, grid_mass, threshold_gyr, hz_edge, age_max_gyr, n=600):
    """Orbit range whose residence ≥ threshold, plus the Roche-limited inner-edge flag inputs."""
    amax = min(age_max_gyr, _track_max_age(track, grid_mass))
    ik, ok = _EDGE_KEYS[hz_edge]
    # bracket the search: from well inside the oldest-epoch inner edge to well outside the
    # youngest in-range outer edge.
    inner_old = _edge_au(track, grid_mass, amax, ik)
    # find the youngest age that is already in Kopparapu range, for a finite outer edge
    a_lo = 0.0
    while a_lo < amax and _out_of_range(_interp_track(track, grid_mass, a_lo)[0]):
        a_lo += amax / 200.0
    outer_young = _edge_au(track, grid_mass, a_lo, ok)
    if not math.isfinite(outer_young):
        outer_young = _edge_au(track, grid_mass, amax, ok) * 4.0
    lo = max(inner_old * 0.3, 1e-5)
    hi = outer_young * 1.5
    if hi <= lo:
        return {"chz_inner_au": None, "chz_outer_au": None,
                "ctrl_entry_teff": None, "ctrl_exit_teff": None}

    qualifying = []
    for i in range(n + 1):
        a = lo * (hi / lo) ** (i / n)        # log-spaced sweep
        r = _residence_at(track, grid_mass, a, hz_edge, age_max_gyr)
        if r["ever_habitable"] and r["residence_gyr"] is not None \
                and r["residence_gyr"] >= threshold_gyr:
            qualifying.append((a, r))
    if not qualifying:
        return {"chz_inner_au": None, "chz_outer_au": None,
                "ctrl_inner_oor": None, "ctrl_outer_oor": None}

    inner_a, inner_r = qualifying[0]
    outer_a, outer_r = qualifying[-1]
    return {
        "chz_inner_au": inner_a,
        "chz_outer_au": outer_a,
        # whether each CHZ edge's controlling crossing relies on Teff extrapolation
        # (outside the Kopparapu 2600-7200 K range — typically the cold side)
        "ctrl_inner_oor": inner_r["entry_out_of_range"],
        "ctrl_outer_oor": outer_r["exit_out_of_range"],
    }


# ── public entry point ───────────────────────────────────────────────────────
def compute_cooling_hz(track, mass_solar=None, mass_mjup=None,
                       cooling_age_gyr=None, teff=None, sma_au=None,
                       chz_threshold_gyr=3.0, hz_edge="conservative",
                       age_max_gyr=13.8, satellite_density=5.5):
    """Cooling-primary HZ residence / CHZ calculator. See module docstring for modes.

    Returns a mode-dependent dict (always carrying ``track``, ``mass_solar``,
    ``model_note``, ``any_out_of_range``, ``hz_model_valid_teff_k``) or ``{"error": str}``.
    """
    # ── validation ────────────────────────────────────────────────────────────
    if track not in ("wd", "bd"):
        return {"error": "track must be 'wd' or 'bd'."}
    if hz_edge not in _EDGE_KEYS:
        return {"error": "hz_edge must be 'conservative' or 'optimistic'."}
    for name, v in (("cooling_age_gyr", cooling_age_gyr), ("teff", teff),
                    ("sma_au", sma_au)):
        if v is not None and v <= 0:
            return {"error": f"{name} must be positive."}
    if chz_threshold_gyr <= 0:
        return {"error": "chz_threshold_gyr must be positive."}
    if age_max_gyr <= 0:
        return {"error": "age_max_gyr must be positive."}
    if satellite_density <= 0:
        return {"error": "satellite_density must be positive."}

    # ── mass resolution (canonical M_sun + the grid's native unit) ────────────
    if track == "wd":
        if mass_solar is not None:
            m_solar = mass_solar
        elif mass_mjup is not None:
            m_solar = mass_mjup * _MJUP_TO_MSUN
        else:
            m_solar = _WD_MASS_DEFAULT
        grid_mass = m_solar
        mass_mjup_out = m_solar / _MJUP_TO_MSUN
    else:  # bd — grid keyed in M_Jup
        if mass_mjup is not None:
            m_mjup = mass_mjup
        elif mass_solar is not None:
            m_mjup = mass_solar / _MJUP_TO_MSUN
        else:
            m_mjup = _BD_MASS_DEFAULT_MJUP
        grid_mass = m_mjup
        m_solar = m_mjup * _MJUP_TO_MSUN
        mass_mjup_out = m_mjup

    if m_solar <= 0:
        return {"error": "mass must be positive."}

    model_note = (f"{track.upper()} {cooling_tables._WD_TABLE_SOURCE if track == 'wd' else cooling_tables._BD_TABLE_SOURCE}"
                  " (interpolated bundled table)")
    base = {
        "track": track,
        "mass_solar": m_solar,
        "mass_mjup": mass_mjup_out,
        "hz_edge": hz_edge,
        "age_max_gyr": age_max_gyr,
        "hz_model_valid_teff_k": _HZ_VALID_TEFF,
        "model_note": model_note,
    }

    # validate mass is on-grid (cheap probe at age 0)
    try:
        _interp_track(track, grid_mass, 0.0)
    except _OffGrid as e:
        return {"error": str(e)}

    # ── mode dispatch ─────────────────────────────────────────────────────────
    try:
        if teff is not None or cooling_age_gyr is not None:
            return _mode_snapshot(track, grid_mass, base, cooling_age_gyr, teff)
        if sma_au is not None:
            return _mode_residence(track, grid_mass, base, sma_au, hz_edge, age_max_gyr)
        return _mode_chz(track, grid_mass, base, chz_threshold_gyr, hz_edge,
                         age_max_gyr, satellite_density)
    except _OffGrid as e:
        return {"error": str(e)}


def _mode_snapshot(track, grid_mass, base, cooling_age_gyr, teff_in):
    if teff_in is not None:
        age = _age_for_teff(track, grid_mass, teff_in)
    else:
        age = cooling_age_gyr
    teff_k, lum, radius = _interp_track(track, grid_mass, age)
    oor = _out_of_range(teff_k)
    notes = []
    try:
        zones = compute_habitable_zone(teff_k, lum)
    except (ValueError, ZeroDivisionError):
        zones = []
        notes.append("hz_undefined_extrapolation")
    out = dict(base)
    out.update({
        "mode": "snapshot",
        "cooling_age_gyr": age,
        "teff_k": teff_k,
        "lum_lsun": lum,
        "radius_rsun": radius,
        "zones": zones,
        "out_of_range_teff": oor,
        "any_out_of_range": oor,
        "notes": notes,
    })
    return out


def _mode_residence(track, grid_mass, base, sma_au, hz_edge, age_max_gyr):
    r = _residence_at(track, grid_mass, sma_au, hz_edge, age_max_gyr)
    out = dict(base)
    out.update({"mode": "residence", "sma_au": sma_au})
    out.update(r)
    out["any_out_of_range"] = bool(r["entry_out_of_range"] or r["exit_out_of_range"])
    return out


def _mode_chz(track, grid_mass, base, threshold_gyr, hz_edge, age_max_gyr, satellite_density):
    band = _chz_band(track, grid_mass, threshold_gyr, hz_edge, age_max_gyr)
    out = dict(base)
    out.update({
        "mode": "chz",
        "chz_threshold_gyr": threshold_gyr,
        "satellite_density": satellite_density,
        "chz_inner_au": band["chz_inner_au"],
        "chz_outer_au": band["chz_outer_au"],
    })

    # Roche cross-check at the cool epoch (WD/BD radius is nearly constant late). The
    # **fluid** (strengthless rubble-pile) Roche limit is the tidal-disruption radius for
    # a planet-sized body — the relevant floor for "the cool-WD CHZ inner edge collides
    # with the disruption radius" (Pkt 7 R2). The rigid limit is echoed for transparency.
    roche_limit_au = None
    roche_rigid_au = None
    inner_roche = None
    radius_rsun = _interp_track(track, grid_mass, _track_max_age(track, grid_mass))[2]
    roche = compute_roche_limit(
        base["mass_solar"] * _MSUN_TO_MEARTH,
        satellite_density,
        primary_radius_earth=radius_rsun * _RSUN_TO_REARTH,
    )
    if "error" not in roche:
        roche_limit_au = roche["fluid_au"]
        roche_rigid_au = roche["rigid_au"]
        if band["chz_inner_au"] is not None:
            inner_roche = band["chz_inner_au"] < roche_limit_au
    out["roche_limit_au"] = roche_limit_au
    out["roche_rigid_au"] = roche_rigid_au
    out["inner_edge_roche_limited"] = inner_roche

    ci = band["ctrl_inner_oor"]
    co = band["ctrl_outer_oor"]
    out["chz_inner_out_of_range"] = ci
    out["chz_outer_out_of_range"] = co
    out["any_out_of_range"] = bool(ci or co)
    return out
