# core/calculators.py — Distance, speed, travel time, and brachistochrone functions.
# Phase A: compute_ly_hr_to_times_c (option 21).
# Phase B: options 22–26.
# Phase C: compute_lookup_star_for_distance, compute_distance_between_stars,
#           compute_stars_within_distance_of_sol, compute_stars_within_distance_of_star.
# Phase D: remaining brachistochrone and travel-time-between-stars functions.

import csv
import heapq
import itertools
import math
import os
from collections import deque

from .equations import _C_MS, _LY_M  # single source of truth (Phase Y/P4.5 promoted to equations)
from .shared import (_make_simbad, _network_error_msg, _timeout_ctx, _with_retries,
                     _to_cartesian, spectral_leading_class, _SP_DISPLAY_LETTERS,
                     gcns_neighbor_separation,  # CR-18 neighbourhood separation (shared)
                     sp_color,   # the one app-wide spectral palette (Phase 3)
                     # The synthetic-Sol row constants (see _sol_result_row below).
                     _SOL_NAME, _SOL_DESIG, _SOL_SP_TYPE, _SOL_APP_MAG, _SOL_PARSECS,
                     # AN0: the canonical designation matcher + the narrow key set
                     # (was a re-typed 5-entry prefix map in this module).
                     _match_designations, _join_designations,
                     _designation_ids_from_rows, _NARROW_DESIG_KEYS,
                     # B.2: the one Jupiter→Earth mass constant (OEC_SYSTEM_VIEW_PLAN)
                     M_JUP_EARTH as _M_JUP_EARTH_SHARED)
from .sensing import _rayleigh_theta  # S2 shared kernel (Phase AP) — direct-imaging IWA (1·λ/D)

HOURS_PER_JULIAN_YEAR = 8765.8128  # 365.2422 × 24 (tropical year) — legacy ly/hr↔×c anchor; NOT 365.25×24 (=8766.0).
                                   # Golden pins and the downstream consumer depend on this exact value; see IMPROVEMENT_PLAN D1.

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")


def compute_ly_hr_to_times_c(ly_hr: float) -> dict:
    """Convert a velocity in light years per hour to multiples of the speed of light.

    Args:
        ly_hr: velocity in light years per hour

    Returns:
        dict with keys: ly_hr, times_c (both floats)
    """
    return {"ly_hr": ly_hr, "times_c": ly_hr * HOURS_PER_JULIAN_YEAR}


def compute_speed_of_light_to_ly_hr(times_c: float) -> dict:
    """Convert a velocity in multiples of c to light years per hour.

    Args:
        times_c: velocity as a multiple of the speed of light

    Returns:
        dict with keys: times_c, ly_hr (both floats)
    """
    return {"times_c": times_c, "ly_hr": times_c / HOURS_PER_JULIAN_YEAR}


def compute_lorentz_factor(velocity_c: float) -> dict:
    """Special-relativistic Lorentz (time-dilation) factor for a sublight velocity.

    γ = 1/√(1 − β²) where β = velocity_c (a fraction of c). Self-validating
    (Phase-H/P contract): velocity must satisfy 0 ≤ β < 1.

    NOTE: this is a *relativistic* calculator and is deliberately distinct from the
    FTL-arithmetic converters (compute_ly_hr_to_times_c / compute_speed_of_light_to_ly_hr),
    which treat "× c" as a plain multiplier with no relativistic interpretation.

    Args:
        velocity_c: velocity as a fraction of the speed of light (0 ≤ β < 1)

    Returns:
        dict with keys: velocity_c, lorentz_factor, time_dilation_pct — or {"error": str}.
        time_dilation_pct = (γ − 1) × 100 (percent slowdown of the moving clock).
    """
    if velocity_c < 0 or velocity_c >= 1:
        return {"error": "Velocity must be in the range 0 ≤ β < 1 (sublight)."}
    gamma = 1.0 / math.sqrt(1.0 - velocity_c * velocity_c)
    return {
        "velocity_c": velocity_c,
        "lorentz_factor": gamma,
        "time_dilation_pct": (gamma - 1.0) * 100.0,
    }


def compute_distance_traveled_ly_hr(ly_hr: float, hours: float) -> dict:
    """Distance traveled at a given ly/hr over a given number of hours.

    Args:
        ly_hr:  velocity in light years per hour
        hours:  travel time in hours

    Returns:
        dict with keys: ly_hr, hours, distance_ly
    """
    return {"ly_hr": ly_hr, "hours": hours, "distance_ly": ly_hr * hours}


def compute_distance_traveled_times_c(times_c: float, hours: float) -> dict:
    """Distance traveled at a given multiple of c over a given number of hours.

    Args:
        times_c: velocity as a multiple of the speed of light
        hours:   travel time in hours

    Returns:
        dict with keys: times_c, ly_hr, hours, distance_ly
    """
    ly_hr = times_c / HOURS_PER_JULIAN_YEAR
    return {"times_c": times_c, "ly_hr": ly_hr, "hours": hours, "distance_ly": ly_hr * hours}


def format_travel_time(total_hours: float) -> str:
    """Break total_hours into years, months, days, hours, minutes, seconds.

    Only includes units that are >= 1 (or seconds if < 1 minute total).
    Uses Julian year: 365.25 * 24 hours.

    Returns a comma-separated string such as '5 Months, 24 Days, 11 Hours'.
    """
    HOURS_PER_YEAR  = 365.25 * 24          # 8766.0 (Julian year)
    HOURS_PER_MONTH = HOURS_PER_YEAR / 12  # ~730.485
    HOURS_PER_DAY   = 24.0
    HOURS_PER_MIN   = 1 / 60.0

    remaining = total_hours

    years = int(remaining / HOURS_PER_YEAR)
    remaining -= years * HOURS_PER_YEAR

    months = int(remaining / HOURS_PER_MONTH)
    remaining -= months * HOURS_PER_MONTH

    days = int(remaining / HOURS_PER_DAY)
    remaining -= days * HOURS_PER_DAY

    hours = int(remaining)
    remaining -= hours

    minutes = int(remaining * 60)
    remaining -= minutes / 60

    seconds = remaining * 3600

    parts = []
    if years:
        parts.append(f"{years} Year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} Month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} Hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} Minute{'s' if minutes != 1 else ''}")
    if seconds >= 0.005 and (not parts or total_hours < HOURS_PER_MIN):
        parts.append(f"{seconds:.2f} Second{'s' if seconds != 1.0 else ''}")

    return ", ".join(parts) if parts else "0 Seconds"


def compute_travel_time_ly_hr(distance_ly: float, ly_hr: float) -> dict:
    """Time to travel a given number of light years at a given ly/hr velocity.

    Args:
        distance_ly: distance in light years
        ly_hr:       velocity in light years per hour (must be > 0)

    Returns:
        dict with keys: distance_ly, ly_hr, times_c, total_hours, travel_time_str
    """
    total_hours = distance_ly / ly_hr
    times_c = ly_hr * HOURS_PER_JULIAN_YEAR
    return {
        "distance_ly": distance_ly,
        "ly_hr": ly_hr,
        "times_c": times_c,
        "total_hours": total_hours,
        "travel_time_str": format_travel_time(total_hours),
    }


# ── Star distance / proximity helpers (Phase C, options 18–20) ───────────────

def _fmt_ra(deg: float) -> str:
    """Format decimal RA degrees as 'HH MM SS.SSSS'."""
    h = int(deg / 15)
    m = int((deg / 15 - h) * 60)
    s = ((deg / 15 - h) * 60 - m) * 60
    return f"{h:02d} {m:02d} {s:07.4f}"


def _fmt_dec(deg: float) -> str:
    """Format decimal DEC degrees as '±DD MM SS.SSS'."""
    sign = "-" if deg < 0 else "+"
    a = abs(deg)
    d = int(a)
    m = int((a - d) * 60)
    s = ((a - d) * 60 - m) * 60
    return f"{sign}{d:02d} {m:02d} {s:06.3f}"


# _to_cartesian imported from core.shared (P4.6 — one canonical copy).


def compute_lookup_star_for_distance(designation: str) -> dict:
    """Query SIMBAD for RA, DEC, parallax, spectral type, and short designations.

    Special-cases 'sun' / 'sol' (case-insensitive) → origin coordinates with
    no SIMBAD query.

    `sp_type` is additive (added for the O8 two-star Star Charts, which colour
    each dot by spectral class the way opts 18/19 do); it is "" when SIMBAD has
    no type. Consumers must read it via `.get("sp_type", "")`.

    Returns:
        {name, ra_deg, dec_deg, ly, sp_type, desig_str}   on success
        {"error": str}                                     on failure
    """
    norm = designation.strip().lower()
    if norm in ("sun", "sol"):
        return {
            "name":     designation.strip(),
            "ra_deg":   0.0,
            "dec_deg":  0.0,
            "ly":       0.0,
            "sp_type":  "G2V",
            "desig_str": "",
        }

    from astroquery.simbad import Simbad

    try:
        with _timeout_ctx(30):
            # Inside the try: _make_simbad lazily hits SIMBAD's TAP capabilities
            # endpoint, so a connection failure there is classified by
            # _network_error_msg rather than leaking a raw DALServiceError.
            custom_simbad = _make_simbad("plx_value", "sp_type")
            result     = _with_retries(custom_simbad.query_object, designation)
            ids_result = _with_retries(Simbad.query_objectids, designation)
    except Exception as e:
        return {"error": _network_error_msg(e, "SIMBAD")}

    if result is None:
        return {"error": f"No results found for '{designation}'"}

    row = result[0]
    col_names = result.colnames

    def _safe(col):
        if col not in col_names:
            return None
        val = row[col]
        try:
            if hasattr(val, "mask") and val.mask:
                return None
        except Exception:
            pass
        s = str(val).strip()
        if s in ("", "--", "N/A", "nan", "None"):
            return None
        return val

    try:
        ra_deg  = float(_safe("ra"))
        dec_deg = float(_safe("dec"))
    except (TypeError, ValueError):
        return {"error": f"Could not read RA/DEC for '{designation}'"}

    plx_raw = _safe("plx_value")
    try:
        plx_f = float(plx_raw)
        if plx_f <= 0:
            raise ValueError("non-positive parallax")
        ly = 1000.0 / plx_f * 3.26156
    except (TypeError, ValueError, ZeroDivisionError):
        return {"error": f"Could not read valid parallax for '{designation}'"}

    name = str(_safe("main_id") or designation)

    # Phase AN0: the narrow (NAME/HD/HR/GJ/Wolf) designation set for this cheap
    # lookup — opts 17/19/20/21 and all seven route planners. The key list is passed
    # EXPLICITLY and its order is load-bearing (AN0b [R4]): deriving it by filtering
    # core.shared._CSV_PREFIX_MAP would move GJ from 4th to 2nd in desig_str on
    # every one of those surfaces.
    desig_found = _match_designations(_designation_ids_from_rows(ids_result),
                                      _NARROW_DESIG_KEYS)
    desig_str = _join_designations(desig_found, _NARROW_DESIG_KEYS)

    sp_type = str(_safe("sp_type") or "").strip()

    return {"name": name, "ra_deg": ra_deg, "dec_deg": dec_deg, "ly": ly,
            "sp_type": sp_type, "desig_str": desig_str}


def compute_distance_between_stars(star1: str, star2: str) -> dict:
    """Compute the 3D Euclidean distance in light years between two star systems.

    Returns:
        {
          star1_info: {name, ra_deg, dec_deg, ly, desig_str, ra_hms, dec_dms},
          star2_info: same,
          distance_ly: float,
          distance_au: float | None  (set only when distance_ly < 0.5)
        }
        or {"error": str} on failure.
    """
    s1 = compute_lookup_star_for_distance(star1)
    if "error" in s1:
        return s1
    s2 = compute_lookup_star_for_distance(star2)
    if "error" in s2:
        return s2

    x1, y1, z1 = _to_cartesian(s1["ra_deg"], s1["dec_deg"], s1["ly"])
    x2, y2, z2 = _to_cartesian(s2["ra_deg"], s2["dec_deg"], s2["ly"])
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    for s in (s1, s2):
        s["ra_hms"]  = _fmt_ra(s["ra_deg"])
        s["dec_dms"] = _fmt_dec(s["dec_deg"])

    result = {
        "star1_info":   s1,
        "star2_info":   s2,
        "distance_ly":  distance_ly,
        "distance_au":  distance_ly * 63241.077 if distance_ly < 0.5 else None,
    }
    return result


# ── Sol as a *result row* (opt 19 / GCNS M4c) ────────────────────────────────
# The `_SOL_*` constants live in core.shared (imported at the top of this module)
# — `core.viz` needs the name to flag Sol for its ★ chart marker and must not
# import this heavier module. See the comment block there for why `_SOL_PARSECS`
# is 1 AU in parsecs and why that value is load-bearing.


def _sol_result_row(cx: float, cy: float, cz: float, limit_ly: float):
    """A synthetic Sol row for a star-centred search, or None when out of range.

    Sol sits at the heliocentric origin, so its separation from the centre star is
    just the length of the centre's own position vector. The `0.001 <` floor is the
    same self-exclusion the DB rows use — it drops Sol when the centre *is* Sol
    (`compute_lookup_star_for_distance` resolves "sol"/"sun" to ly = 0).
    """
    dist = math.sqrt(cx * cx + cy * cy + cz * cz)
    if not (0.001 < dist <= limit_ly):
        return None
    return {
        "Star Name":         _SOL_NAME,
        "Star Designations": _SOL_DESIG,
        "Spectral Type":     _SOL_SP_TYPE,
        "Distance":          dist,
        "app_magnitude":     _SOL_APP_MAG,
        "parsecs":           _SOL_PARSECS,
        "x": 0.0, "y": 0.0, "z": 0.0,
    }


def compute_stars_within_distance_of_sol(limit_ly: float) -> dict:
    """List all stars in the star_systems DB table within limit_ly light years of Sol.

    Returns:
        {limit_ly, count, stars: [sorted list of row dicts with 'Light Years' key]}
        or {"error": str} if the table is empty.
    """
    from core.db import get_conn

    def _parse_ra(s):
        p = s.strip().split()
        return (float(p[0]) + float(p[1]) / 60 + float(p[2]) / 3600) * 15

    def _parse_dec(s):
        s = s.strip()
        sign = -1 if s.startswith("-") else 1
        p = s.lstrip("+-").split()
        return sign * (float(p[0]) + float(p[1]) / 60 + float(p[2]) / 3600)

    try:
        conn = get_conn()
        db_rows = conn.execute(
            "SELECT star_name, designations, spectral_type, light_years, "
            "parsecs, app_magnitude, ra, dec "
            "FROM star_systems WHERE light_years <= ?",
            (limit_ly,),
        ).fetchall()
    except Exception as e:
        return {"error": f"Error reading star_systems table: {e}"}

    if not db_rows and get_conn().execute("SELECT COUNT(*) FROM star_systems").fetchone()[0] == 0:
        return {"error": "star_systems table is empty — run option 50 first to populate it."}

    matches = []
    for row in db_rows:
        ly = row["light_years"]
        if ly is None:
            continue
        try:
            ra_deg  = _parse_ra(row["ra"] or "")
            dec_deg = _parse_dec(row["dec"] or "")
            x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
        except Exception:
            x = y = z = None
        matches.append({
            "Star Name":         row["star_name"] or "",
            "Star Designations": row["designations"] or "",
            "Spectral Type":     row["spectral_type"] or "",
            "Light Years":       ly,
            # Phase O F1 — additive keys consumed by O1 (night sky) / O2b (HR overlay).
            "app_magnitude":     row["app_magnitude"],
            "parsecs":           row["parsecs"],
            "x": x, "y": y, "z": z,
        })

    matches.sort(key=lambda r: r["Light Years"])
    return {"limit_ly": limit_ly, "count": len(matches), "stars": matches}


def compute_stars_within_distance_of_star(center_star: str, limit_ly: float) -> dict:
    """List all stars in the star_systems DB table within limit_ly light years of center_star.

    Queries SIMBAD for center_star, then iterates star_systems and computes
    3D Euclidean distances. A synthetic **Sol** row is appended when the centre is
    within limit_ly of the origin — the Sun is not a SIMBAD object, so the catalogue
    has no row for it (see `_sol_result_row`).

    Returns:
        {center, limit_ly, count, stars: [sorted list of dicts with 'Distance' key]}
        or {"error": str} on failure.
    """
    from core.db import get_conn

    s = compute_lookup_star_for_distance(center_star)
    if "error" in s:
        return s

    try:
        conn = get_conn()
        count = conn.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0]
        if count == 0:
            return {"error": "star_systems table is empty — run option 50 first to populate it."}
        db_rows = conn.execute(
            "SELECT star_name, designations, spectral_type, parallax, light_years, "
            "app_magnitude, ra, dec "
            "FROM star_systems"
        ).fetchall()
    except Exception as e:
        return {"error": f"Error reading star_systems table: {e}"}

    def _parse_ra(ra_str: str) -> float:
        parts = ra_str.strip().split()
        h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return (h + m / 60 + sec / 3600) * 15

    def _parse_dec(dec_str: str) -> float:
        dec_str = dec_str.strip()
        sign = -1 if dec_str.startswith("-") else 1
        parts = dec_str.lstrip("+-").split()
        d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return sign * (d + m / 60 + sec / 3600)

    # CR-18: transverse separation uses the centre's SIMBAD distance (always available, same frame as
    # the reported 3D Distance). The GCNS bound flag additionally needs the centre's Gaia id → its
    # incident bound-pair map; that costs a second SIMBAD lookup, so it is gated to a non-Sol centre
    # AND a populated GCNS table (a Sol/Sun centre or an empty/unloaded GCNS degrades bound to null,
    # while transverse is still computed). The centre's ra/dec/ly are unchanged (from the lookup above).
    import re as _re
    center_dist_pc = (s["ly"] / 3.26156) if s.get("ly") else None
    center_pair_map = {}
    if center_star.strip().lower() not in ("sol", "sun"):
        try:
            gcns_ready = conn.execute("SELECT 1 FROM gcns_stars LIMIT 1").fetchone() is not None
        except Exception:
            gcns_ready = False
        if gcns_ready:
            center_gaia_id = None
            # Offline first: the centre is usually itself a `star_systems` row — parse its Gaia id from
            # the designations text (no network), matched on the resolved SIMBAD main_id. Fall back to a
            # SIMBAD lookup only when that misses, so the common case adds no second network round-trip.
            try:
                r0 = conn.execute("SELECT designations FROM star_systems WHERE star_name = ? LIMIT 1",
                                  (s.get("name"),)).fetchone()
                if r0:
                    m0 = _re.search(r"Gaia\s+E?DR3\s+(\d+)", r0["designations"] or "")
                    center_gaia_id = int(m0.group(1)) if m0 else None
            except Exception:
                center_gaia_id = None
            if center_gaia_id is None:
                try:
                    from core import databases
                    csl = databases.compute_simbad_lookup(center_star)
                    gv = (csl.get("designations") or {}).get("Gaia EDR3") \
                        if isinstance(csl, dict) and "error" not in csl else None
                    mm = _re.search(r"Gaia\s+E?DR3\s+(\d+)", str(gv)) if gv else None
                    center_gaia_id = int(mm.group(1)) if mm else None
                except Exception:
                    center_gaia_id = None
            if center_gaia_id is not None:
                try:
                    from core import databases
                    crow = conn.execute("SELECT system_id FROM gcns_stars WHERE gaia_source_id = ?",
                                        (center_gaia_id,)).fetchone()
                    if crow:
                        center_pair_map = databases.gcns_center_pair_map(
                            conn, crow["system_id"], center_gaia_id)
                except Exception:
                    pass

    cx, cy, cz = _to_cartesian(s["ra_deg"], s["dec_deg"], s["ly"])

    matches = []
    for row in db_rows:
        try:
            plx = float(row["parallax"] or 0)
            if plx <= 0:
                continue
            ly = 1000.0 / plx * 3.26156
            ra_deg  = _parse_ra(row["ra"] or "")
            dec_deg = _parse_dec(row["dec"] or "")
        except (ValueError, TypeError, IndexError):
            # IndexError matters: opt 50 writes ra/dec as "" when SIMBAD's value fails
            # to parse, and these split-based parsers raise IndexError (not ValueError)
            # on a blank/short string — which used to escape this handler and abort the
            # whole search. Matches _load_star_systems_positions' handler. Skip the row.
            continue
        x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
        dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
        if 0.001 < dist <= limit_ly:
            parsecs_n = 1000.0 / plx
            entry = {
                "Star Name":         row["star_name"] or "",
                "Star Designations": row["designations"] or "",
                "Spectral Type":     row["spectral_type"] or "",
                "Distance":          dist,
                # Phase O F1 — additive keys consumed by O1 (night sky) / O2b (HR overlay).
                "app_magnitude":     row["app_magnitude"],
                "parsecs":           parsecs_n,
                "x": x, "y": y, "z": z,
            }
            # CR-18: transverse separation + tri-state bound flag — SIMBAD 1/ϖ distance frame (matches
            # the reported 3D Distance); no parallax errors on this path, so the radial flag uses the
            # base rule. Neighbour Gaia id parsed from the designations text (the GCNS cross-match key).
            m = _re.search(r"Gaia\s+E?DR3\s+(\d+)", row["designations"] or "")
            entry.update(gcns_neighbor_separation(
                s["ra_deg"], s["dec_deg"], center_dist_pc,
                ra_deg, dec_deg, parsecs_n,
                center_pair_map.get(int(m.group(1))) if m else None))
            matches.append(entry)

    # Sol is never a `star_systems` row, so it has to be synthesized (see above).
    sol = _sol_result_row(cx, cy, cz, limit_ly)
    if sol:
        sol.update({  # CR-18: uniform shape — Sol is synthetic, bound features unknown.
            "transverse_sep_au": None, "transverse_sep_ly": None,
            "bound": None, "is_bound_companion": False,
            "sep_method": "synthetic_sol_origin", "radial_parallax_dominated": None,
        })
        matches.append(sol)

    matches.sort(key=lambda r: r["Distance"])
    return {
        "center":         s["name"],
        "center_x":       cx,
        "center_y":       cy,
        "center_z":       cz,
        "limit_ly":       limit_ly,
        "count":          len(matches),
        "stars":          matches,
    }


# ── Physical constants for brachistochrone calculations ───────────────────────
_G_MS2     = 9.80665              # 1 g in m/s²
# _C_MS imported from core.equations (Phase Y — single source of truth)
_M_PER_AU  = 149_597_870_700.0    # metres per AU
_M_PER_LM  = _C_MS * 60.0        # metres per light-minute

# ── Physical constants for the Phase T1b detectability / relativistic calcs ───
_M_JUP_EARTH         = _M_JUP_EARTH_SHARED  # Jupiter mass in Earth masses (core.shared)
_M_SUN_EARTH         = 332_946.0          # Sun mass in Earth masses
_R_SUN_AU            = 0.00465047          # solar radius in AU
_R_EARTH_AU          = 4.25875e-5          # Earth radius in AU
_ARCSEC_PER_RAD      = 206_264.806         # arcsec per radian
_SEC_PER_JULIAN_YEAR = 365.25 * 86400.0    # 31,557,600 s (Julian year)
# _LY_M imported from core.equations (P4.5 — identical to _C_MS * _SEC_PER_JULIAN_YEAR)


# ── Phase T1b · planet-detectability calculators (group A) ────────────────────
# Pure-compute, self-validating (Phase-H/P contract). Granular subcommands for the
# sibling worldbuilding repo's survey-bias research. See docs/calculators.md.

def compute_rv_semi_amplitude(planet_mass_earth, star_mass_solar,
                              period_days=None, sma_au=None,
                              ecc=0, inclination_deg=90):
    """Radial-velocity semi-amplitude K a planet induces on its star (Lovis & Fischer 2010).

    `K = 28.4329 m/s · (1/√(1−e²)) · (Mp·sin i / M_Jup) · ((M*+Mp)/M_sun)^(−2/3) · (P/1yr)^(−1/3)`.
    `--planet-mass-earth` is converted to M_Jup internally (the 28.4329 constant is per-M_Jup).
    Supply exactly one of `period_days` / `sma_au` (the other is derived via Kepler III).

    Returns {k_ms, period_days, sma_au, ecc, inclination_deg, planet_mass_earth,
    star_mass_solar} or {"error": str}.
    """
    if planet_mass_earth <= 0 or star_mass_solar <= 0:
        return {"error": "Planet mass and star mass must be positive."}
    if not (0 <= ecc < 1):
        return {"error": "Eccentricity must be in the range 0 ≤ e < 1."}
    if (period_days is None) == (sma_au is None):
        return {"error": "Provide exactly one of period_days / sma_au."}
    if period_days is not None and period_days <= 0:
        return {"error": "Period must be positive."}
    if sma_au is not None and sma_au <= 0:
        return {"error": "Semi-major axis must be positive."}

    mp_solar = planet_mass_earth / _M_SUN_EARTH
    total_mass = star_mass_solar + mp_solar
    if sma_au is not None:
        period_yr = math.sqrt(sma_au ** 3 / total_mass)
        period_days = period_yr * 365.25
    else:
        period_yr = period_days / 365.25
        sma_au = (total_mass * period_yr ** 2) ** (1.0 / 3.0)

    mp_jup = planet_mass_earth / _M_JUP_EARTH
    sin_i = math.sin(math.radians(inclination_deg))
    k_ms = (28.4329 * (1.0 / math.sqrt(1.0 - ecc ** 2)) * (mp_jup * sin_i)
            * total_mass ** (-2.0 / 3.0) * period_yr ** (-1.0 / 3.0))
    return {
        "k_ms": k_ms,
        "period_days": period_days,
        "sma_au": sma_au,
        "ecc": ecc,
        "inclination_deg": inclination_deg,
        "planet_mass_earth": planet_mass_earth,
        "star_mass_solar": star_mass_solar,
    }


def compute_transit_signal(planet_radius_earth, star_radius_solar,
                           sma_au=None, period_days=None, star_mass_solar=None):
    """Transit depth, geometric probability, and duration (Winn 2010).

    depth `δ=(Rp/R*)²`; probability `p≈R*/a` (circular); duration `T≈(P/π)·arcsin(R*/a)`.
    Supply `sma_au`, or `period_days` + `star_mass_solar` (a derived via Kepler III).
    When only `sma_au` is given (no `star_mass_solar`), the period/duration are left None.

    Returns {depth_ppm, depth_frac, transit_prob, duration_hours, sma_au, period_days,
    planet_radius_earth, star_radius_solar} or {"error": str}.
    """
    if planet_radius_earth <= 0 or star_radius_solar <= 0:
        return {"error": "Planet radius and star radius must be positive."}

    if sma_au is not None:
        if sma_au <= 0:
            return {"error": "Semi-major axis must be positive."}
        a_au = sma_au
        if star_mass_solar is not None:
            if star_mass_solar <= 0:
                return {"error": "Star mass must be positive."}
            period_days = 365.25 * math.sqrt(a_au ** 3 / star_mass_solar)
    elif period_days is not None and star_mass_solar is not None:
        if period_days <= 0 or star_mass_solar <= 0:
            return {"error": "Period and star mass must be positive."}
        period_yr = period_days / 365.25
        a_au = (star_mass_solar * period_yr ** 2) ** (1.0 / 3.0)
    else:
        return {"error": "Provide --sma-au, or both --period-days and --star-mass-solar."}

    r_star_au = star_radius_solar * _R_SUN_AU
    rp_au = planet_radius_earth * _R_EARTH_AU
    if r_star_au >= a_au:
        return {"error": "Star radius meets or exceeds the orbital distance (no transit geometry)."}

    depth_frac = (rp_au / r_star_au) ** 2
    transit_prob = r_star_au / a_au
    duration_hours = None
    if period_days is not None:
        duration_hours = (period_days * 24.0 / math.pi) * math.asin(r_star_au / a_au)

    return {
        "depth_ppm": depth_frac * 1e6,
        "depth_frac": depth_frac,
        "transit_prob": transit_prob,
        "duration_hours": duration_hours,
        "sma_au": a_au,
        "period_days": period_days,
        "planet_radius_earth": planet_radius_earth,
        "star_radius_solar": star_radius_solar,
    }


def compute_astrometric_signal(planet_mass_earth, star_mass_solar, sma_au, distance_pc):
    """Astrometric wobble of a star induced by a planet.

    `α [arcsec] = (Mp/M*)·(a_AU / d_pc)`; reported headline in microarcsec with an arcsec echo.

    Returns {signal_microarcsec, signal_arcsec, planet_mass_earth, star_mass_solar,
    sma_au, distance_pc} or {"error": str}.
    """
    if planet_mass_earth <= 0 or star_mass_solar <= 0 or sma_au <= 0 or distance_pc <= 0:
        return {"error": "Planet mass, star mass, SMA, and distance must be positive."}
    ratio = (planet_mass_earth / _M_SUN_EARTH) / star_mass_solar
    signal_arcsec = ratio * sma_au / distance_pc
    return {
        "signal_microarcsec": signal_arcsec * 1e6,
        "signal_arcsec": signal_arcsec,
        "planet_mass_earth": planet_mass_earth,
        "star_mass_solar": star_mass_solar,
        "sma_au": sma_au,
        "distance_pc": distance_pc,
    }


def compute_direct_imaging(sma_au, distance_pc, planet_radius_earth, albedo=0.3,
                           telescope_diameter_m=None, wavelength_um=None):
    """Reflected-light contrast and angular separation, optionally vs a telescope IWA.

    Angular separation `θ [arcsec] = a_AU / d_pc`; reflected contrast `C ≈ A_g·(Rp/a)²`
    (max, full phase) with Rp converted to AU; optional inner working angle `IWA = λ/D`
    (the 1·λ/D convention) in arcsec when both telescope args are given, and a
    `resolvable = θ ≥ IWA` flag (else both null).

    Returns {angular_sep_arcsec, contrast_reflected, iwa_arcsec, resolvable, sma_au,
    distance_pc, planet_radius_earth, albedo} or {"error": str}.
    """
    if sma_au <= 0 or distance_pc <= 0 or planet_radius_earth <= 0:
        return {"error": "SMA, distance, and planet radius must be positive."}
    if albedo <= 0:
        return {"error": "Albedo must be positive."}
    has_d = telescope_diameter_m is not None
    has_w = wavelength_um is not None
    if has_d != has_w:
        return {"error": "Provide both --telescope-diameter-m and --wavelength-um, or neither."}

    rp_au = planet_radius_earth * _R_EARTH_AU
    angular_sep_arcsec = sma_au / distance_pc
    contrast = albedo * (rp_au / sma_au) ** 2

    iwa_arcsec = None
    resolvable = None
    if has_d and has_w:
        if telescope_diameter_m <= 0 or wavelength_um <= 0:
            return {"error": "Telescope diameter and wavelength must be positive."}
        # Rayleigh/IWA kernel shared with S2 (Phase AP); coefficient 1.0 = the 1·λ/D IWA
        # convention this function has always used (behavior-preserving DRY refactor).
        iwa_rad = _rayleigh_theta(wavelength_um * 1e-6, telescope_diameter_m, coefficient=1.0)
        iwa_arcsec = iwa_rad * _ARCSEC_PER_RAD
        resolvable = angular_sep_arcsec >= iwa_arcsec

    return {
        "angular_sep_arcsec": angular_sep_arcsec,
        "contrast_reflected": contrast,
        "iwa_arcsec": iwa_arcsec,
        "resolvable": resolvable,
        "sma_au": sma_au,
        "distance_pc": distance_pc,
        "planet_radius_earth": planet_radius_earth,
        "albedo": albedo,
    }


def compute_relativistic_brachistochrone(accel_g, distance_ly):
    """Flip-and-burn under constant *proper* acceleration, relativistically correct (MTW).

    Per half-distance D/2 (then doubled): `X = arccosh(1 + a·(D/2)/c²)`; proper time per
    half `τ_h=(c/a)·X`, coordinate time `t_h=(c/a)·sinh X`; midpoint `peak_velocity_c=tanh X`,
    `peak_lorentz_factor=cosh X`. Lifts the 3%c Newtonian cap of the brachistochrone subcommands.

    Returns {accel_g, distance_ly, coord_time_yr, proper_time_yr, peak_velocity_c,
    peak_lorentz_factor} or {"error": str}.
    """
    if accel_g <= 0 or distance_ly <= 0:
        return {"error": "Acceleration and distance must be positive."}
    a = accel_g * _G_MS2
    half_m = (distance_ly * _LY_M) / 2.0
    x = math.acosh(1.0 + a * half_m / _C_MS ** 2)
    tau_half = (_C_MS / a) * x
    t_half = (_C_MS / a) * math.sinh(x)
    return {
        "accel_g": accel_g,
        "distance_ly": distance_ly,
        "coord_time_yr": 2.0 * t_half / _SEC_PER_JULIAN_YEAR,
        "proper_time_yr": 2.0 * tau_half / _SEC_PER_JULIAN_YEAR,
        "peak_velocity_c": math.tanh(x),
        "peak_lorentz_factor": math.cosh(x),
    }

# ── Horizons ID map (options 32, 33) ──────────────────────────────────────────
#
# Numbered small bodies MUST carry the trailing ";" (Horizons' small-body
# designator). A bare integer is read as a *major-body* id first, and ids 1-9
# are the planet barycenters — so "ceres": "1" silently resolved to Mercury
# Barycenter (199), "vesta": "4" to Mars Barycenter, and likewise Pallas ->
# Venus and Juno -> Earth-Moon. The ";" form is unambiguous on both call paths
# (astroquery elements()/vectors() and the OBJ_DATA text endpoint) and it also
# makes fetch_body_properties() take its "Asteroid physical parameters" branch.
# Comet ids (1P, 67P, C/1995 O1) are already unambiguous and take no ";".
_HORIZONS_ID_MAP = {
    "sun": "10",
    "mercury": "199", "venus": "299", "earth": "399", "mars": "499",
    "jupiter": "599", "saturn": "699", "uranus": "799", "neptune": "899",
    "pluto": "999", "ceres": "1;", "vesta": "4;", "pallas": "2;", "juno": "3;",
    "eris": "136199;", "makemake": "136472;", "haumea": "136108;", "sedna": "90377;",
    "moon": "301", "luna": "301",
    "phobos": "401", "deimos": "402",
    "io": "501", "europa": "502", "ganymede": "503", "callisto": "504",
    "amalthea": "505", "himalia": "506", "elara": "507", "pasiphae": "508",
    "sinope": "509", "lysithea": "510", "carme": "511", "ananke": "512",
    "leda": "513", "thebe": "514", "adrastea": "515", "metis": "516",
    "mimas": "601", "enceladus": "602", "tethys": "603", "dione": "604",
    "rhea": "605", "titan": "606", "hyperion": "607", "iapetus": "608",
    "phoebe": "609", "janus": "610", "epimetheus": "611", "helene": "612",
    "telesto": "613", "calypso": "614", "atlas": "615", "prometheus": "616",
    "pandora": "617", "pan": "618",
    "ariel": "701", "umbriel": "702", "miranda": "703", "titania": "704",
    "oberon": "705", "caliban": "706", "sycorax": "707", "puck": "708",
    "portia": "709", "juliet": "710", "belinda": "711", "cressida": "712",
    "desdemona": "713", "rosalind": "714", "bianca": "715", "cordelia": "716",
    "ophelia": "717",
    "triton": "801", "nereid": "802", "proteus": "808", "larissa": "807",
    "galatea": "806", "despina": "805", "thalassa": "804", "naiad": "803",
    "charon": "901", "nix": "902", "hydra": "903", "kerberos": "904", "styx": "905",
    "eros": "433;", "ida": "243;", "gaspra": "951;", "mathilde": "253;",
    "itokawa": "25143;", "ryugu": "162173;", "bennu": "101955;", "apophis": "99942;",
    "lutetia": "21;", "steins": "2867;", "churyumov": "67P",
    "halley": "1P", "encke": "2P", "hale-bopp": "C/1995 O1",
    "tempel 1": "9P", "wild 2": "81P",
}

_PLANET_IDS = [
    ("Mercury", "199"), ("Venus", "299"), ("Earth", "399"), ("Mars", "499"),
    ("Jupiter", "599"), ("Saturn", "699"), ("Uranus", "799"), ("Neptune", "899"),
]
_PLANET_COLORS = {
    "Mercury": "#b5b5b5", "Venus": "#e8cda0", "Earth": "#4fc3f7",
    "Mars":    "#ef5350",  "Jupiter": "#c9956b", "Saturn": "#d4b896",
    "Uranus":  "#7de8e8",  "Neptune": "#5b8df5",
}

_planet_pos_cache: list = []
_planet_pos_cache_time: float = 0.0
_planet_pos_cache_epoch_jd: float = 0.0
_PLANET_POS_CACHE_TTL = 1800.0   # 30 minutes
_BODY_PROPS_CACHE: dict = {}
_planet_fetch_errors: list = []


def _fetch_planet_positions(epoch_jd=None) -> list:
    """Return heliocentric x,y,z (AU) for the 8 planets. Cached for 30 min per epoch."""
    import time
    import astropy.time as _atime
    global _planet_pos_cache, _planet_pos_cache_time, _planet_pos_cache_epoch_jd, _planet_fetch_errors
    if epoch_jd is None:
        epoch_jd = _atime.Time.now().jd
    epoch_match = abs(epoch_jd - _planet_pos_cache_epoch_jd) < 0.02  # ~29 min in JD
    time_ok = (time.monotonic() - _planet_pos_cache_time) < _PLANET_POS_CACHE_TTL
    if _planet_pos_cache and epoch_match and time_ok:
        return _planet_pos_cache
    _planet_fetch_errors = []
    planets = []
    for name, pid in _PLANET_IDS:
        try:
            x, y, z = _get_heliocentric_vectors(pid, epoch_jd)
            planets.append({"name": name, "x": x, "y": y, "z": z,
                            "color": _PLANET_COLORS[name], "horizons_id": pid})
        except Exception as e:
            _planet_fetch_errors.append(f"{name} ({pid}): {e}")
    _planet_pos_cache = planets
    _planet_pos_cache_time = time.monotonic()
    _planet_pos_cache_epoch_jd = epoch_jd
    return planets


def _resolve_horizons_id(name: str) -> str:
    """Map a body name to a JPL Horizons-compatible ID."""
    normalized = name.strip().lower()
    if normalized in _HORIZONS_ID_MAP:
        return _HORIZONS_ID_MAP[normalized]
    tokens = normalized.split()
    if tokens and tokens[-1] in _HORIZONS_ID_MAP:
        return _HORIZONS_ID_MAP[tokens[-1]]
    return name.strip()


def _get_heliocentric_vectors(horizons_id: str, epoch_jd=None):
    """Query JPL Horizons for heliocentric x,y,z in AU.

    Returns (x, y, z) floats. Raises on failure.
    """
    import astropy.time
    from astroquery.jplhorizons import Horizons
    if epoch_jd is None:
        epoch_jd = astropy.time.Time.now().jd

    def _do_query():
        with _timeout_ctx(30):
            obj = Horizons(id=horizons_id, location="@sun", epochs=epoch_jd)
            vec = obj.vectors()
            return float(vec["x"][0]), float(vec["y"][0]), float(vec["z"][0])

    return _with_retries(_do_query)


def fetch_body_properties(horizons_id: str) -> dict:
    """Query JPL Horizons for physical properties of a solar system body.

    Returns a dict with keys depending on body type. Always includes:
      body_type: "planet", "moon", "asteroid", "comet", or "unknown"
      raw_text: the full text response from Horizons
    Cached per horizons_id for the session.
    """
    import re
    import requests

    if horizons_id in _BODY_PROPS_CACHE:
        return _BODY_PROPS_CACHE[horizons_id]

    try:
        params = {
            "format": "text",
            "COMMAND": horizons_id,
            "OBJ_DATA": "YES",
            "MAKE_EPHEM": "NO",
        }

        # Use requests (certifi CA bundle) rather than urllib.request: on networks
        # with a TLS-intercepting proxy / self-signed CA chain, raw urllib fails
        # SSL verification ("Network Error") while requests — like every other
        # network call in this project — succeeds.
        def _do_fetch():
            resp = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api",
                                params=params, timeout=15)
            resp.raise_for_status()
            return resp.text

        text = _with_retries(_do_fetch)
    except Exception as e:
        return {"body_type": "unknown", "raw_text": "", "error": _network_error_msg(e, "JPL Horizons")}

    props = {"raw_text": text}

    def _find(pattern, default="N/A"):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    if "SATELLITE PHYSICAL PROPERTIES" in text or "SATELLITE PHYSICAL" in text:
        props["body_type"] = "moon"
        # Name: from "Revised: <date>  <Name> / (Parent)" line
        rev_m = re.search(r"Revised:[^\n]+", text)
        if rev_m:
            chunks = re.split(r'\s{3,}', rev_m.group(0).strip())
            raw = chunks[1].strip() if len(chunks) >= 2 else horizons_id
            # Strip " / (Parent)" suffix if present
            props["name_full"] = re.sub(r'\s*/\s*\(.*\)$', '', raw).strip()
        else:
            props["name_full"] = horizons_id
        props["mean_radius_km"]   = _find(r"Mean [Rr]adius\s*\(km\)\s*=\s*([\d.]+(?:\s*[+-]+\s*[\d.]+)?)")
        props["density_gcc"]      = _find(r"Density\s*\(g\s*(?:cm|/cm)\^?[-]?3\)\s*=?\s*([\d.]+(?:\s*[+-]+\s*[\d.]+)?)")
        props["gm_km3s2"]         = _find(r"GM\s*\(km\^3/s\^2\)\s*=\s*([\d.]+(?:\s*[+-]+\s*[\d.]+)?)")
        props["geometric_albedo"] = _find(r"Geometric [Aa]lbedo\s*=\s*([\d.]+)")
        props["sma_km"]           = _find(r"Semi-major axis,\s*a\s*\(km\)\s*=?\s*([\d,. ]+(?:\(10\^3\))?)")
        props["orbital_period_d"] = _find(r"Orbital period\s*=\s*([\d.]+)\s*d")
        props["eccentricity"]     = _find(r"Eccentricity,\s*e\s*=\s*([\d.]+)")
        props["inclination_deg"]  = _find(r"Inclination,\s*i\s*\(?deg\)?\s*=\s*([\d.]+)")
        props["rot_period"]       = _find(r"Rotational period\s*=\s*([^\n]+?)(?:\s*$)", "N/A")
        props["v10"]              = _find(r"V\(1,0\)\s*=\s*([-\d.]+)")

    elif "Asteroid physical parameters" in text:
        props["body_type"] = "asteroid"
        nm = re.search(r"JPL/HORIZONS\s+(.+?)\s{2,}", text)
        props["name_full"] = nm.group(1).strip() if nm else horizons_id
        props["gm_km3s2"]         = _find(r"GM=\s*([\d.na]+)", "N/A")
        props["mean_radius_km"]   = _find(r"RAD=\s*([\d.]+)")
        props["rot_period_hr"]    = _find(r"ROTPER=\s*([\d.]+)")
        props["abs_magnitude"]    = _find(r"\bH=\s*([\d.]+)")
        props["slope_g"]          = _find(r"\bG=\s*([-\d.]+)")
        props["bv_color"]         = _find(r"B-V=\s*([\d.]+)")
        props["albedo"]           = _find(r"ALBEDO=\s*([\d.]+)")
        props["spectral_type"]    = _find(r"STYP=\s*(\w+)")

    elif "Comet physical" in text or "Comet non-gravitational" in text:
        props["body_type"] = "comet"
        nm = re.search(r"JPL/HORIZONS\s+(.+?)\s{2,}", text)
        props["name_full"] = nm.group(1).strip() if nm else horizons_id
        props["mean_radius_km"]   = _find(r"RAD=\s*([\d.]+)")
        props["abs_magnitude_m1"] = _find(r"M1=\s*([\d.]+)")
        props["abs_magnitude_m2"] = _find(r"M2=\s*([\d.]+)")

    elif any(x in text for x in ("PHYSICAL DATA", "GEOPHYSICAL PROPERTIES",
                                  "GEOPHYSICAL DATA", "PHYSICAL PROPERTIES")):
        props["body_type"] = "planet"
        # Name: extract from "Revised: <date>  <Name>  <ID>" line; strip / (Parent)
        rev_m = re.search(r"Revised:[^\n]+", text)
        if rev_m:
            chunks = re.split(r'\s{3,}', rev_m.group(0).strip())
            raw = chunks[1].strip() if len(chunks) >= 2 else horizons_id
            props["name_full"] = re.sub(r'\s*/\s*\(.*\)$', '', raw).strip()
        else:
            props["name_full"] = horizons_id

        # Mean radius — "Vol. mean radius (km) = X", "Vol. mean radius, km = X"
        props["mean_radius_km"] = _find(
            r"Vol\.?\s*[Mm]ean\s*[Rr]adius\s*[,(]?\s*km[).]?\s*=\s*([\d.+\-]+)")
        if props["mean_radius_km"] == "N/A":
            props["mean_radius_km"] = _find(
                r"Equat(?:orial)?\s*[Rr]adius[^=\n]*=\s*([\d,]+)\s*km")

        # Mass — "Mass x10^26 (kg)", "Mass x 10^26 (kg)", "Mass, x10^22 kg"
        mass_m = re.search(
            r"Mass[,\s]*x\s*10\^(\d+)\s*(?:\(kg\)|kg)[^=\n]*=\s*([\d.]+)", text, re.IGNORECASE)
        if mass_m:
            props["mass_exp"] = mass_m.group(1)
            props["mass_val"] = mass_m.group(2)
            props["mass_str"] = f"{mass_m.group(2)} × 10^{mass_m.group(1)} kg"
        else:
            props["mass_str"] = "N/A"

        # Density — (g/cm^3), (g cm^-3), or "Density, g/cm^3"
        props["density_gcc"] = _find(
            r"Density\s*[,(]?\s*g[/ ]?cm\^?[-]?3\s*[)]?\s*=\s*([\d.]+(?:\([^)]*\))?)")

        # Surface gravity — equatorial; "Equ. grav, ge (m/s^2) = X" (Saturn),
        # "Equ. gravity  m/s^2 = X" (Mars), "g_e, m/s^2 = X" (Earth)
        props["equ_gravity_ms2"] = _find(
            r"Equ[^=\n]*\(m/s\^2\)\s*=\s*([\d.]+)")
        if props["equ_gravity_ms2"] == "N/A":
            props["equ_gravity_ms2"] = _find(
                r"Equ(?:atorial)?\.?\s*grav(?:ity)?[,\s]+m/s\^2\s*=\s*([\d.]+)")
        if props["equ_gravity_ms2"] == "N/A":
            props["equ_gravity_ms2"] = _find(r"g_e,\s*m/s\^2\s*[^=\n]*=\s*([\d.]+)")

        # Escape velocity — both "km/s = X" and "= X km/s" formats
        props["escape_km_s"] = _find(
            r"Escape\s*(?:speed|vel(?:ocity)?)[,.]?\s*km/s\s*=\s*([\d.]+)")
        if props["escape_km_s"] == "N/A":
            props["escape_km_s"] = _find(
                r"Escape\s+(?:speed|velocity)\s*=\s*([\d.]+)\s*km/s")

        # Rotation period — "Sidereal rot. period = X hr/d", "Sid. rot. period = 10h 39m",
        # or "Mean sidereal day, hr = X" (Earth)
        props["rot_period"] = _find(
            r"Sid(?:ereal)?\.?\s*rot(?:ation)?\.?\s*period\s*[^=\n]*=\s*([^\s][^\n]*?)(?:\s{2,}|\n|$)")
        if props["rot_period"] == "N/A":
            rot_m = re.search(r"Mean\s+sidereal\s+day[^=\n]*=\s*([\d.]+)", text, re.IGNORECASE)
            props["rot_period"] = (rot_m.group(1) + " hr") if rot_m else "N/A"
        else:
            props["rot_period"] = props["rot_period"].strip()

        # Mean solar day — "(sol) = X s", "hrs =~X.X", or "2000.0, s = X"
        props["mean_solar_day"] = _find(
            r"Mean\s+solar\s+day[^=\n]*=\s*~?\s*([\d.]+)")
        if props["mean_solar_day"] != "N/A":
            props["mean_solar_day"] = props["mean_solar_day"].strip()

        # Mean temperature — "(K) = X" or "(Ts), K= X" or "Atmos. temp. (1 bar)"
        props["mean_temp_k"] = _find(
            r"Mean\s+(?:surface\s+)?temp(?:erature)?\s*\([^)]*\)[^=\n]*=\s*([\d.]+)")
        if props["mean_temp_k"] == "N/A":
            props["mean_temp_k"] = _find(
                r"Mean\s+(?:surface\s+)?temp(?:erature)?\s*\(K\)\s*=\s*([\d.]+)")
        if props["mean_temp_k"] == "N/A":
            props["mean_temp_k"] = _find(
                r"Atmos\.\s*temp\.\s*\(1\s*bar\)\s*=\s*([\d.+\-]+)")

        # Atmospheric pressure — "(bar) = X", "= X bar", or "Atm. pressure = X bar"
        props["atm_pressure_bar"] = _find(
            r"Atm(?:os)?(?:ospheric)?\.?\s*pressure\s*(?:\(bar\)\s*)?=\s*([<\d.e+\-]+)")
        if props["atm_pressure_bar"] == "N/A":
            props["atm_pressure_bar"] = _find(
                r"Atm(?:os)?(?:ospheric)?\.?\s*pressure\s*=\s*([\d.]+)\s*bar")

        props["geometric_albedo"] = _find(r"Geometric\s+[Aa]lbedo\s*=\s*([\d.]+)")

        # Obliquity — "= X deg" or "deg = X" (Earth puts deg before the =)
        props["obliquity_deg"] = _find(
            r"Obliquity\s+to\s+orbit[^\n=]*=\s*([\d.]+)")

        # Orbital speed — "km/s = X" or "= X km/s"
        props["orbital_speed_kms"] = _find(
            r"(?:Orbital|Mean\s+[Oo]rbit)\s+(?:speed|vel(?:ocity)?)[,.]?\s*km/s\s*=\s*([\d.]+)")
        if props["orbital_speed_kms"] == "N/A":
            props["orbital_speed_kms"] = _find(
                r"(?:Orbital|Mean\s+[Oo]rbit)\s+(?:speed|velocity)\s*=\s*([\d.]+)\s*km/s")

        props["orbital_period_y"] = _find(
            r"(?:Mean\s+)?[Ss]idereal\s+orb(?:it)?\s+per(?:iod)?\s*=\s*([\d.]+)\s*y")
        props["hills_sphere"] = _find(
            r"Hill'?s?\s+sphere\s+rad(?:ius)?[^=\n]*=\s*([\d.]+)")
        # GM — "(km^3/s^2) = X" or "GM, km^3/s^2 = X"
        props["gm_km3s2"] = _find(
            r"GM[,\s]*(?:\(km\^3/s\^2\)|km\^3/s\^2)\s*=\s*([\d,.]+)")
    else:
        props["body_type"] = "unknown"
        nm = re.search(r"JPL/HORIZONS\s+(.+?)\s{2,}", text)
        props["name_full"] = nm.group(1).strip() if nm else horizons_id

    _BODY_PROPS_CACHE[horizons_id] = props
    return props


def _brachistochrone_profiles(d_m: float, a_ms2: float, v_cap_pct: float = 3.0) -> list:
    """Compute three brachistochrone profiles for a given distance in metres.

    Returns list of 3 dicts:
        label, hours, travel_time_str, max_vel  ('N/A', 'Y', or 'N')
    """
    V_CAP_MS = (v_cap_pct / 100.0) * _C_MS

    # Profile 1: Continuous to Halfway — t = 2·√(d/a)
    t1_sec   = 2.0 * math.sqrt(d_m / a_ms2)
    t1_hours = t1_sec / 3600.0

    # Profile 2: Half accel time, coast, decel — t = √(16d/(3a))
    t2_sec   = math.sqrt((16.0 * d_m) / (3.0 * a_ms2))
    t2_hours = t2_sec / 3600.0

    # Profile 3: Accel to v_cap, coast, decel
    t_cap      = V_CAP_MS / a_ms2
    d_both_cap = a_ms2 * t_cap ** 2
    if d_both_cap >= d_m:
        t3_sec       = t1_sec
        t3_hours     = t1_hours
        label3       = f"Accel to {v_cap_pct}% c, Coast, Then Decelerate (cap not reached)"
        cap3_reached = False
    else:
        d_coast3 = d_m - d_both_cap
        t_coast3 = d_coast3 / V_CAP_MS
        t3_sec       = 2.0 * t_cap + t_coast3
        t3_hours     = t3_sec / 3600.0
        label3       = f"Accel to {v_cap_pct}% c, Coast, Then Decelerate"
        cap3_reached = True

    return [
        {
            "label": "Continuous to Halfway Point",
            "hours": t1_hours,
            "travel_time_str": format_travel_time(t1_hours),
            "max_vel": "N/A",
        },
        {
            "label": "Half Continuous Accel Time, Coast, Then Decelerate",
            "hours": t2_hours,
            "travel_time_str": format_travel_time(t2_hours),
            "max_vel": "N/A",
        },
        {
            "label": label3,
            "hours": t3_hours,
            "travel_time_str": format_travel_time(t3_hours),
            "max_vel": "Y" if cap3_reached else "N",
        },
    ]


def compute_travel_time_between_stars(
        origin: str, destination: str,
        ly_hr: float = None, times_c: float = None) -> dict:
    """Compute travel time between two star systems.

    Supply exactly one of ly_hr or times_c.

    Returns:
        {origin_info, dest_info, distance_ly, ly_hr, times_c,
         total_hours, travel_time_str}
        or {"error": str}
    """
    if ly_hr is None and times_c is None:
        return {"error": "Must supply ly_hr or times_c."}
    if ly_hr is not None and times_c is not None:
        return {"error": "Supply only one of ly_hr or times_c."}

    s1 = compute_lookup_star_for_distance(origin)
    if "error" in s1:
        return s1
    s2 = compute_lookup_star_for_distance(destination)
    if "error" in s2:
        return s2

    x1, y1, z1 = _to_cartesian(s1["ra_deg"], s1["dec_deg"], s1["ly"])
    x2, y2, z2 = _to_cartesian(s2["ra_deg"], s2["dec_deg"], s2["ly"])
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    if ly_hr is not None:
        v_ly_hr  = ly_hr
        v_times_c = ly_hr * HOURS_PER_JULIAN_YEAR
    else:
        v_times_c = times_c
        v_ly_hr   = times_c / HOURS_PER_JULIAN_YEAR

    total_hours = distance_ly / v_ly_hr

    for s in (s1, s2):
        s["ra_hms"]  = _fmt_ra(s["ra_deg"])
        s["dec_dms"] = _fmt_dec(s["dec_deg"])

    return {
        "origin_info":     s1,
        "dest_info":       s2,
        "distance_ly":     distance_ly,
        "ly_hr":           v_ly_hr,
        "times_c":         v_times_c,
        "total_hours":     total_hours,
        "travel_time_str": format_travel_time(total_hours),
    }


def compute_distance_at_acceleration(accel_g: float, hours: float) -> dict:
    """Distance traveled for three profiles given acceleration and travel time.

    Profile 1: Continuous acceleration for entire time (d = ½·a·t²).
    Profile 2: Accel t/4, coast t/2, decel t/4 (d = 3a·t²/16).
    Profile 3: Accel to v_cap, coast remaining time (no decel in window).

    Returns:
        {accel_g, hours, travel_time_str,
         profiles: [list of 3 dicts with label, distance_au, distance_lm, max_vel]}
    """
    a_ms2 = accel_g * _G_MS2
    t_sec = hours * 3600.0
    V_CAP_MS = 0.03 * _C_MS

    # Profile 1
    d1_m = 0.5 * a_ms2 * t_sec ** 2

    # Profile 2
    t_accel2 = t_sec / 4.0
    v_peak2  = a_ms2 * t_accel2
    d2_m     = 0.5 * a_ms2 * t_accel2**2 + v_peak2 * (t_sec / 2.0) + 0.5 * a_ms2 * t_accel2**2

    # Profile 3
    t_cap = V_CAP_MS / a_ms2
    if t_cap >= t_sec:
        d3_m         = 0.5 * a_ms2 * t_sec ** 2
        label3       = "Accel to 3% c, Coast, Then Decelerate (cap not reached)"
        cap3_reached = False
    else:
        d_accel3 = 0.5 * a_ms2 * t_cap ** 2
        t_coast3 = t_sec - t_cap
        d3_m         = d_accel3 + V_CAP_MS * t_coast3
        label3       = "Accel to 3% c, Coast, Then Decelerate"
        cap3_reached = True

    return {
        "accel_g":         accel_g,
        "hours":           hours,
        "travel_time_str": format_travel_time(hours),
        "profiles": [
            {
                "label":       "Continuous Acceleration for Entire Time",
                "distance_au": d1_m / _M_PER_AU,
                "distance_lm": d1_m / _M_PER_LM,
                "max_vel":     "N/A",
            },
            {
                "label":       "Half Continuous Accel Time, Coast, Then Decelerate",
                "distance_au": d2_m / _M_PER_AU,
                "distance_lm": d2_m / _M_PER_LM,
                "max_vel":     "N/A",
            },
            {
                "label":       label3,
                "distance_au": d3_m / _M_PER_AU,
                "distance_lm": d3_m / _M_PER_LM,
                "max_vel":     "Y" if cap3_reached else "N",
            },
        ],
    }


def compute_travel_time_system_au(accel_g: float, distance_au: float) -> dict:
    """Brachistochrone travel time for three profiles given distance in AU.

    Returns:
        {accel_g, distance_au, distance_lm, profiles: [...]}
    """
    a_ms2      = accel_g * _G_MS2
    d_m        = distance_au * _M_PER_AU
    distance_lm = d_m / _M_PER_LM
    profiles   = _brachistochrone_profiles(d_m, a_ms2)
    return {
        "accel_g":     accel_g,
        "distance_au": distance_au,
        "distance_lm": distance_lm,
        "profiles":    profiles,
    }


def compute_travel_time_system_lm(accel_g: float, distance_lm: float) -> dict:
    """Brachistochrone travel time for three profiles given distance in light minutes.

    Returns:
        {accel_g, distance_au, distance_lm, profiles: [...]}
    """
    a_ms2      = accel_g * _G_MS2
    d_m        = distance_lm * _M_PER_LM
    distance_au = d_m / _M_PER_AU
    profiles   = _brachistochrone_profiles(d_m, a_ms2)
    return {
        "accel_g":     accel_g,
        "distance_au": distance_au,
        "distance_lm": distance_lm,
        "profiles":    profiles,
    }


def compute_travel_time_solar_objects(
        origin: str, destination: str,
        accel_g: float, v_cap_pct: float = 3.0,
        departure_date: str = None,
        progress_callback=None) -> dict:
    """Brachistochrone travel time between two solar system objects via JPL Horizons.

    Args:
        departure_date: ISO date string "YYYY-MM-DD"; defaults to today when None.

    Returns:
        {origin, destination, accel_g, distance_au, distance_lm,
         v_cap_pct, departure_date, profiles: [...]}
        or {"error": str, "disambiguation": str (optional)}
    """
    import astropy.time
    origin_id = _resolve_horizons_id(origin)
    dest_id   = _resolve_horizons_id(destination)
    if departure_date:
        epoch_jd = astropy.time.Time(f"{departure_date}T12:00:00").jd
    else:
        import datetime
        departure_date = datetime.date.today().isoformat()
        epoch_jd = astropy.time.Time.now().jd

    if progress_callback:
        progress_callback(f"Querying JPL Horizons for '{origin}'…")
    try:
        ox, oy, oz = _get_heliocentric_vectors(origin_id, epoch_jd)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            return {"error": f"Ambiguous body name '{origin}'.\nTip: Use a more specific name or numeric ID (e.g. '499' for Mars).\n\n{err}"}
        return {"error": _network_error_msg(e, f"JPL Horizons for '{origin}'")}

    if progress_callback:
        progress_callback(f"Querying JPL Horizons for '{destination}'…")
    try:
        dx, dy, dz = _get_heliocentric_vectors(dest_id, epoch_jd)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            return {"error": f"Ambiguous body name '{destination}'.\nTip: Use a more specific name or numeric ID (e.g. '501' for Io).\n\n{err}"}
        return {"error": _network_error_msg(e, f"JPL Horizons for '{destination}'")}

    distance_au = math.sqrt((dx - ox)**2 + (dy - oy)**2 + (dz - oz)**2)
    if distance_au < 1e-9:
        return {"error": "Origin and destination appear to be the same object (distance ≈ 0 AU)."}

    a_ms2       = accel_g * _G_MS2
    d_m         = distance_au * _M_PER_AU
    distance_lm = d_m / _M_PER_LM
    profiles    = _brachistochrone_profiles(d_m, a_ms2, v_cap_pct)

    if progress_callback:
        progress_callback("Querying JPL Horizons for planet positions…")
    planet_positions = _fetch_planet_positions(epoch_jd)

    return {
        "origin":           origin,
        "destination":      destination,
        "accel_g":          accel_g,
        "distance_au":      distance_au,
        "distance_lm":      distance_lm,
        "v_cap_pct":        v_cap_pct,
        "departure_date":   departure_date,
        "profiles":         profiles,
        "origin_xyz":       (ox, oy, oz),
        "dest_xyz":         (dx, dy, dz),
        "planet_positions": planet_positions,
        "origin_id":        origin_id,
        "dest_id":          dest_id,
    }


def compute_travel_time_custom_thrust(
        origin: str, destination: str,
        accel_g: float, burn_duration_s: float,
        v_cap_pct: float = 3.0,
        burn_value: float = None, burn_unit_label: str = "Days",
        departure_date: str = None,
        progress_callback=None) -> dict:
    """Travel time between two solar system objects with custom thrust duration.

    The ship accelerates for burn_duration_s seconds, coasts, then decelerates
    for the same duration. Destination position is iteratively estimated.

    Args:
        departure_date: ISO date string "YYYY-MM-DD"; defaults to today when None.

    Returns:
        {origin, destination, distance_au, distance_lm, accel_g, a_ms2,
         burn_value, burn_unit_label, burn_seconds, eff_burn_s,
         v_cap_pct, v_cap_ms, vmax_reached, t_to_vmax_str,
         v_coast_ms, v_coast_pct_c, fallback, departure_date,
         t_accel_hours, t_coast_hours, d_accel_au, d_accel_lm,
         d_coast_au, d_coast_lm, t_total_hours, travel_time_str,
         iterations_done}
        or {"error": str}
    """
    import astropy.time

    origin_id = _resolve_horizons_id(origin)
    dest_id   = _resolve_horizons_id(destination)

    a_ms2    = accel_g * _G_MS2
    V_CAP_MS = (v_cap_pct / 100.0) * _C_MS

    if departure_date:
        t0_jd = astropy.time.Time(f"{departure_date}T12:00:00").jd
    else:
        import datetime
        departure_date = datetime.date.today().isoformat()
        t0_jd = astropy.time.Time.now().jd

    if progress_callback:
        progress_callback(f"Querying JPL Horizons for '{origin}'…")
    try:
        ox, oy, oz = _get_heliocentric_vectors(origin_id, t0_jd)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            return {"error": f"Ambiguous body name '{origin}'.\nTip: Use a numeric ID (e.g. '499' for Mars).\n\n{err}"}
        return {"error": _network_error_msg(e, f"JPL Horizons for '{origin}'")}

    def _compute_travel(d_m):
        t_to_vmax   = V_CAP_MS / a_ms2
        t_accel_eff = min(burn_duration_s, t_to_vmax)
        v_coast     = a_ms2 * t_accel_eff
        d_accel     = 0.5 * a_ms2 * t_accel_eff ** 2
        if 2.0 * d_accel >= d_m:
            t_half  = math.sqrt(d_m / a_ms2)
            t_total = 2.0 * t_half
            v_peak  = a_ms2 * t_half
            return (t_total, t_half, 0.0, v_peak, False, d_m / 2.0, 0.0, True)
        d_coast_m = d_m - 2.0 * d_accel
        t_coast   = d_coast_m / v_coast
        t_total   = 2.0 * t_accel_eff + t_coast
        vmax_reached = burn_duration_s > t_to_vmax
        return (t_total, t_accel_eff, t_coast, v_coast, vmax_reached,
                d_accel, d_coast_m, False)

    MAX_ITER = 10
    CONVERGE_SEC = 60.0

    if progress_callback:
        progress_callback(f"Querying JPL Horizons for '{destination}' (iteration 1)…")
    try:
        dx, dy, dz = _get_heliocentric_vectors(dest_id, t0_jd)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            return {"error": f"Ambiguous body name '{destination}'.\nTip: Use a numeric ID.\n\n{err}"}
        return {"error": _network_error_msg(e, f"JPL Horizons for '{destination}'")}

    distance_au = math.sqrt((dx - ox)**2 + (dy - oy)**2 + (dz - oz)**2)
    if distance_au < 1e-9:
        return {"error": "Origin and destination appear to be the same object (distance ≈ 0 AU)."}

    d_m = distance_au * _M_PER_AU
    res = _compute_travel(d_m)
    prev_t_total = res[0]
    iterations_done = 1

    for iteration in range(2, MAX_ITER + 1):
        arrival_jd = t0_jd + prev_t_total / 86400.0
        if progress_callback:
            progress_callback(f"Querying JPL Horizons for '{destination}' (iteration {iteration})…")
        try:
            dx, dy, dz = _get_heliocentric_vectors(dest_id, arrival_jd)
        except Exception:
            break
        new_dist = math.sqrt((dx - ox)**2 + (dy - oy)**2 + (dz - oz)**2)
        if new_dist < 1e-9:
            break
        d_m = new_dist * _M_PER_AU
        distance_au = new_dist
        res = _compute_travel(d_m)
        iterations_done = iteration
        if abs(res[0] - prev_t_total) < CONVERGE_SEC:
            break
        prev_t_total = res[0]

    (t_total_sec, t_accel_eff, t_coast_sec, v_coast_ms, vmax_reached,
     d_accel_m, d_coast_m, fallback) = res

    distance_lm   = d_m / _M_PER_LM
    t_total_hours = t_total_sec / 3600.0
    t_accel_hours = t_accel_eff / 3600.0
    t_coast_hours = t_coast_sec / 3600.0
    d_accel_au    = d_accel_m / _M_PER_AU
    d_accel_lm    = d_accel_m / _M_PER_LM
    d_coast_au    = d_coast_m / _M_PER_AU
    d_coast_lm    = d_coast_m / _M_PER_LM
    v_coast_pct_c = (v_coast_ms / _C_MS) * 100.0
    t_to_vmax_sec = V_CAP_MS / a_ms2

    if vmax_reached:
        t_to_vmax_str = format_travel_time(t_to_vmax_sec / 3600.0)
    else:
        t_to_vmax_str = "N/A"

    if fallback:
        eff_burn_hours = t_accel_eff / 3600.0
        eff_burn_str   = f"{eff_burn_hours:.4f} Hours (midpoint reached)"
    else:
        unit_seconds = {"Hours": 3600.0, "Days": 86400.0, "Weeks": 604800.0}
        eff_val = t_accel_eff / unit_seconds.get(burn_unit_label, 86400.0)
        eff_burn_str = f"{eff_val:.4f} {burn_unit_label}"

    if progress_callback:
        progress_callback("Querying JPL Horizons for planet positions…")
    planet_positions = _fetch_planet_positions(t0_jd)

    return {
        "origin":           origin,
        "destination":      destination,
        "distance_au":      distance_au,
        "distance_lm":      distance_lm,
        "accel_g":          accel_g,
        "a_ms2":            a_ms2,
        "burn_value":       burn_value,
        "burn_unit_label":  burn_unit_label,
        "burn_seconds":     burn_duration_s,
        "eff_burn_str":     eff_burn_str,
        "v_cap_pct":        v_cap_pct,
        "v_cap_ms":         V_CAP_MS,
        "vmax_reached":     vmax_reached,
        "t_to_vmax_str":    t_to_vmax_str,
        "v_coast_ms":       v_coast_ms,
        "v_coast_pct_c":    v_coast_pct_c,
        "fallback":         fallback,
        "departure_date":   departure_date,
        "t_accel_hours":    t_accel_hours,
        "t_coast_hours":    t_coast_hours,
        "d_accel_au":       d_accel_au,
        "d_accel_lm":       d_accel_lm,
        "d_coast_au":       d_coast_au,
        "d_coast_lm":       d_coast_lm,
        "t_total_hours":    t_total_hours,
        "travel_time_str":  format_travel_time(t_total_hours),
        "iterations_done":  iterations_done,
        "origin_xyz":       (ox, oy, oz),
        "dest_xyz":         (dx, dy, dz),
        "planet_positions": planet_positions,
        "origin_id":        origin_id,
        "dest_id":          dest_id,
    }


def compute_solar_ephemeris_track(body_ids, start_date_iso: str,
                                  stop_date_iso: str, n_steps: int = 300) -> dict:
    """Batch heliocentric ephemeris for several bodies over a date range (Phase O O5b).

    One JPL Horizons *range* query per body (epochs start/stop/step) returns the
    body's position at every sample epoch in a single round-trip, so the GUI solar
    map can animate over time with NO per-frame network call. Bodies share the
    same epoch grid; the returned `jds`/`dates` come from the first body queried.

    Args:
        body_ids: iterable of Horizons ids (deduped internally; falsy ids skipped).
        start_date_iso / stop_date_iso: ISO "YYYY-MM-DD".
        n_steps: target number of sample steps across the range (caps the table).

    Returns:
        {"dates": [iso…], "jds": [float…], "bodies": {id: {"x":[…],"y":[…],"z":[…]}}}
        or {"error": str}.
    """
    import warnings
    import astropy.time
    from astroquery.jplhorizons import Horizons
    try:
        from erfa import ErfaWarning
    except ImportError:  # pragma: no cover — fallback for older astropy bundling
        try:
            from astropy.utils.exceptions import ErfaWarning
        except ImportError:
            ErfaWarning = Warning

    # A multi-decade span reaches years past the leap-second table, so every
    # ISO↔JD conversion emits an ERFA "dubious year" warning. The leap-second
    # uncertainty is sub-second — irrelevant to AU-level positions — so silence
    # just that category around the time conversions / Horizons calls.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ErfaWarning)

        t0 = astropy.time.Time(f"{start_date_iso}T12:00:00").jd
        t1 = astropy.time.Time(f"{stop_date_iso}T12:00:00").jd
        total_days = max(1.0, t1 - t0)
        step_days = max(1, int(round(total_days / max(1, n_steps))))
        epochs = {"start": start_date_iso, "stop": stop_date_iso,
                  "step": f"{step_days}d"}

        bodies = {}
        jds = None
        for bid in body_ids:
            if not bid or bid in bodies:
                continue

            def _do_query(bid=bid):
                with _timeout_ctx(60):
                    return Horizons(id=bid, location="@sun", epochs=epochs).vectors()

            try:
                vec = _with_retries(_do_query)
            except Exception as e:
                return {"error": _network_error_msg(e, f"JPL Horizons (body {bid})")}
            bodies[bid] = {
                "x": [float(v) for v in vec["x"]],
                "y": [float(v) for v in vec["y"]],
                "z": [float(v) for v in vec["z"]],
            }
            if jds is None:
                jds = [float(v) for v in vec["datetime_jd"]]

        if not bodies or not jds:
            return {"error": "No ephemeris returned for the requested bodies."}
        dates = [astropy.time.Time(j, format="jd").iso[:10] for j in jds]
    return {"dates": dates, "jds": jds, "bodies": bodies}


def compute_travel_time_times_c(distance_ly: float, times_c: float) -> dict:
    """Time to travel a given number of light years at a given multiple of c.

    Args:
        distance_ly: distance in light years
        times_c:     velocity as a multiple of the speed of light (must be > 0)

    Returns:
        dict with keys: distance_ly, times_c, ly_hr, total_hours, travel_time_str
    """
    ly_hr = times_c / HOURS_PER_JULIAN_YEAR
    total_hours = distance_ly / ly_hr
    return {
        "distance_ly": distance_ly,
        "times_c": times_c,
        "ly_hr": ly_hr,
        "total_hours": total_hours,
        "travel_time_str": format_travel_time(total_hours),
    }


# ── Phase I — Route Planning ──────────────────────────────────────────────────
# Multi-stop journeys, nearest-neighbor chains, and trade-route MSTs. New,
# self-validating functions (return {"error": str} on bad input) reusing the
# existing resolver / Cartesian / travel-time helpers above. GUI-only — no CLI
# menu entry, no query.py subcommand.


def _parse_db_ra(s: str) -> float:
    """Sexagesimal RA string 'HH MM SS' → decimal degrees (×15)."""
    p = s.strip().split()
    return (float(p[0]) + float(p[1]) / 60 + float(p[2]) / 3600) * 15


def _parse_db_dec(s: str) -> float:
    """Sexagesimal DEC string '±DD MM SS' → signed decimal degrees."""
    s = s.strip()
    sign = -1 if s.startswith("-") else 1
    p = s.lstrip("+-").split()
    return sign * (float(p[0]) + float(p[1]) / 60 + float(p[2]) / 3600)


# NOTE: the route maps used to have their own `_star_map_color` palette here,
# disagreeing with the star-chart one on G/M/D and the unknown grey — so the same
# star was a different colour depending on which panel you opened. It was deleted
# 2026-07-27 (completed_plans/ROUTE_CHART_REFACTOR_PLAN.md Phase 3); `_map_node` now uses the one
# app-wide palette, `core.shared.sp_color`. Do not reintroduce a local palette.


def _resolve_star_position(name: str) -> dict:
    """Resolve a star name to a heliocentric position, DB-first then SIMBAD.

    Order: 'sol'/'sun' → origin (no DB, no network); then a case-insensitive
    exact match on star_systems.star_name (offline, also yields a spectral
    type); then a live SIMBAD lookup via compute_lookup_star_for_distance.

    Returns:
        {name, x, y, z, ly, sp_type, desig, source}  on success
        {"error": str}                                if it resolves nowhere
    """
    norm = name.strip().lower()
    if norm in ("sun", "sol"):
        return {"name": name.strip(), "x": 0.0, "y": 0.0, "z": 0.0,
                "ly": 0.0, "sp_type": "G2V", "desig": "", "source": "sol"}

    # DB-first: exact (case-insensitive) star_name match.
    try:
        from core.db import get_conn
        row = get_conn().execute(
            "SELECT star_name, designations, spectral_type, parallax, "
            "light_years, ra, dec FROM star_systems "
            "WHERE lower(star_name) = ? LIMIT 1",
            (norm,),
        ).fetchone()
    except Exception:
        row = None

    if row is not None:
        try:
            ly = row["light_years"]
            if ly is None or ly <= 0:
                plx = float(row["parallax"] or 0)
                if plx > 0:
                    ly = 1000.0 / plx * 3.26156
            if ly and ly > 0 and row["ra"] and row["dec"]:
                ra_deg = _parse_db_ra(row["ra"])
                dec_deg = _parse_db_dec(row["dec"])
                x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
                return {
                    "name": row["star_name"] or name.strip(),
                    "x": x, "y": y, "z": z, "ly": ly,
                    "sp_type": row["spectral_type"] or "",
                    "desig": row["designations"] or "",
                    "source": "db",
                }
        except Exception:
            pass  # fall through to SIMBAD

    # SIMBAD fallback (live network).
    s = compute_lookup_star_for_distance(name)
    if "error" in s:
        return s
    x, y, z = _to_cartesian(s["ra_deg"], s["dec_deg"], s["ly"])
    return {
        "name": s["name"], "x": x, "y": y, "z": z, "ly": s["ly"],
        "sp_type": s.get("sp_type", ""), "desig": s.get("desig_str", ""),
        "source": "simbad",
    }


def _map_node(rec: dict) -> dict:
    """Build a star-map-compatible dict from a resolved record."""
    return {
        "name": rec["name"], "desig": rec.get("desig", ""),
        "sp_type": rec.get("sp_type", ""),
        "color": sp_color(rec.get("sp_type", "")),
        "ly": math.sqrt(rec["x"] ** 2 + rec["y"] ** 2 + rec["z"] ** 2),
        "x": rec["x"], "y": rec["y"], "z": rec["z"],
    }


def _load_star_systems_positions() -> dict:
    """Read all star_systems rows as 3D positions for the nearest-neighbor pool.

    Returns:
        {"stars": [ {name, desig, sp_type, ly, x, y, z} ]}  on success
        {"error": str}                                       if the table is empty
    """
    from core.db import get_conn
    try:
        conn = get_conn()
        if conn.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0] == 0:
            return {"error": "star_systems table is empty — run option 50 first to populate it."}
        rows = conn.execute(
            "SELECT star_name, designations, spectral_type, parallax, "
            "light_years, ra, dec FROM star_systems"
        ).fetchall()
    except Exception as e:
        return {"error": f"Error reading star_systems table: {e}"}

    out = []
    for row in rows:
        try:
            plx = float(row["parallax"] or 0)
            if plx <= 0:
                continue
            ly = 1000.0 / plx * 3.26156
            ra_deg = _parse_db_ra(row["ra"] or "")
            dec_deg = _parse_db_dec(row["dec"] or "")
        except (ValueError, TypeError, IndexError):
            continue
        x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
        out.append({
            "name": row["star_name"] or "", "desig": row["designations"] or "",
            "sp_type": row["spectral_type"] or "", "ly": ly,
            "x": x, "y": y, "z": z,
        })
    return {"stars": out}


def compute_multi_stop_journey(star_names, velocity_input: float,
                               use_times_c: bool) -> dict:
    """Cumulative travel time along an ordered list of stops.

    Resolution per stop is DB-first then SIMBAD ('sol'/'sun' → origin); the
    first unresolvable stop fails fast with an error naming it.

    Returns:
        {legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours,
                cumulative_hours, travel_time, cumulative_time}],
         total_ly, total_hours, total_time, stars:[map dicts]}
        or {"error": str}
    """
    if not star_names or len(star_names) < 2:
        return {"error": "Enter at least two stops."}
    if velocity_input is None or velocity_input <= 0:
        return {"error": "Velocity must be positive."}

    if use_times_c:
        ly_hr = velocity_input / HOURS_PER_JULIAN_YEAR
        times_c = velocity_input
    else:
        ly_hr = velocity_input
        times_c = velocity_input * HOURS_PER_JULIAN_YEAR

    nodes = []
    for i, nm in enumerate(star_names):
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return {"error": f"Stop {i + 1} ('{nm}'): {rec['error']}"}
        nodes.append(rec)

    legs = []
    cumulative_hours = 0.0
    total_ly = 0.0
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        d = math.sqrt((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2 + (b["z"] - a["z"]) ** 2)
        hours = d / ly_hr
        cumulative_hours += hours
        total_ly += d
        legs.append({
            "leg": i + 1, "origin": a["name"], "dest": b["name"],
            "distance_ly": d, "ly_hr": ly_hr, "times_c": times_c,
            "hours": hours, "cumulative_hours": cumulative_hours,
            "travel_time": format_travel_time(hours),
            "cumulative_time": format_travel_time(cumulative_hours),
        })

    return {
        "legs": legs,
        "total_ly": total_ly,
        "total_hours": cumulative_hours,
        "total_time": format_travel_time(cumulative_hours),
        "stars": [_map_node(n) for n in nodes],
    }


def compute_nearest_neighbor_chain(start_star: str, num_hops: int,
                                   max_ly: float) -> dict:
    """Greedy nearest-unvisited traversal from a start star over star_systems.

    Returns:
        {chain:[{hop, star_name, desig, sp_type, dist_from_prev_ly,
                 cumulative_ly, ly_from_sol}],
         stars:[map dicts incl. start at index 0], total_ly,
         stopped_early, start_name}
        or {"error": str}
    """
    try:
        num_hops = int(num_hops)
    except (TypeError, ValueError):
        return {"error": "Number of hops must be a positive integer."}
    if num_hops < 1:
        return {"error": "Number of hops must be a positive integer."}
    if max_ly is None or max_ly <= 0:
        return {"error": "Max hop distance must be positive."}

    start = _resolve_star_position(start_star)
    if "error" in start:
        return start

    pool_res = _load_star_systems_positions()
    if "error" in pool_res:
        return pool_res
    # Self-exclusion: drop the start's own DB row (within 1e-3 ly).
    pool = [
        s for s in pool_res["stars"]
        if math.sqrt((s["x"] - start["x"]) ** 2 + (s["y"] - start["y"]) ** 2
                     + (s["z"] - start["z"]) ** 2) > 1e-3
    ]

    visited = set()
    cur = start
    cumulative_ly = 0.0
    chain = []
    chain_nodes = [start]
    stopped_early = False
    for hop in range(1, num_hops + 1):
        best_i, best_d = None, float("inf")
        for idx, cand in enumerate(pool):
            if idx in visited:
                continue
            d = math.sqrt((cand["x"] - cur["x"]) ** 2 + (cand["y"] - cur["y"]) ** 2
                          + (cand["z"] - cur["z"]) ** 2)
            if d <= max_ly and d < best_d:
                best_d, best_i = d, idx
        if best_i is None:
            stopped_early = True
            break
        visited.add(best_i)
        cand = pool[best_i]
        cumulative_ly += best_d
        chain.append({
            "hop": hop, "star_name": cand["name"], "desig": cand["desig"],
            "sp_type": cand["sp_type"], "dist_from_prev_ly": best_d,
            "cumulative_ly": cumulative_ly, "ly_from_sol": cand["ly"],
        })
        chain_nodes.append(cand)
        cur = cand

    stars = [_map_node(start)]
    stars[0]["color"] = "#FFD700"  # start highlighted gold
    for c in chain_nodes[1:]:
        stars.append(_map_node(c))

    return {
        "chain": chain,
        "stars": stars,
        "total_ly": cumulative_ly,
        "stopped_early": stopped_early,
        "start_name": start["name"],
    }


class _UnionFind:
    """Disjoint-set with path compression + union by rank (for Kruskal)."""

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


def compute_trade_route_mst(star_names) -> dict:
    """Minimum spanning tree connecting a set of systems (Kruskal + union-find).

    Returns:
        {nodes:[{name,x,y,z,sp_type,desig}], edges:[{from,to,distance_ly}],
         total_ly, stars:[map dicts]}
        or {"error": str}
    """
    # Dedup case-insensitively, preserving order.
    seen, names = set(), []
    for nm in (star_names or []):
        k = nm.strip().lower()
        if k and k not in seen:
            seen.add(k)
            names.append(nm)
    if len(names) < 2:
        return {"error": "Enter at least two systems."}

    nodes = []
    for nm in names:
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return {"error": f"'{nm}': {rec['error']}"}
        nodes.append(rec)

    n = len(nodes)
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = nodes[i], nodes[j]
            d = math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)
            candidates.append((d, i, j))
    candidates.sort(key=lambda e: e[0])

    uf = _UnionFind(n)
    edges, total_ly = [], 0.0
    for d, i, j in candidates:
        if uf.union(i, j):
            edges.append({"from": nodes[i]["name"], "to": nodes[j]["name"], "distance_ly": d})
            total_ly += d
            if len(edges) == n - 1:
                break

    return {
        "nodes": [
            {"name": nd["name"], "x": nd["x"], "y": nd["y"], "z": nd["z"],
             "sp_type": nd.get("sp_type", ""), "desig": nd.get("desig", "")}
            for nd in nodes
        ],
        "edges": edges,
        "total_ly": total_ly,
        "stars": [_map_node(nd) for nd in nodes],
    }


# ── Phase I-OPTS: four new route planners (A/B/C/D) ──────────────────────────
#
# A  compute_optimal_tour          — shortest-total-distance visit order (NN + 2-opt)
# B  compute_jump_route            — point-to-point over a jump-limited graph
# C  compute_jump_network          — BFS reachability tiers from a start
# D  compute_farthest_first_chain  — de-clustering coverage (farthest-from-visited)
#
# All self-validate ({"error": str}); each returns a star-map-compatible `stars`
# list. They reuse _resolve_star_position / _load_star_systems_positions /
# _map_node and the dark-navy Star Chart routes= overlay (via prepare_route_map).

# Tier colours for the reachability map (tier 0 = start, gold).
TIER_COLORS = [
    "#FFD700", "#7fd3ff", "#7fe0a0", "#ffd27f", "#ff9bce",
    "#c8a2ff", "#9affd0", "#ffec99", "#9db4ff", "#ff8f8f",
]


def _node_dist(a: dict, b: dict) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2
                     + (a["z"] - b["z"]) ** 2)


def _merge_endpoint(pool: list, endpoint: dict) -> int:
    """Return the index of `endpoint` in `pool`, appending it if not already
    present (matched by case-insensitive name OR within 1e-3 ly). Mutates pool."""
    nm = endpoint["name"].strip().lower()
    for i, p in enumerate(pool):
        if p["name"].strip().lower() == nm or _node_dist(p, endpoint) <= 1e-3:
            return i
    pool.append(endpoint)
    return len(pool) - 1


class _SpatialGrid:
    """Uniform 3D grid for fast within-radius neighbour queries.

    Cell size = the jump radius, so any two stars within `cell` ly of each other
    fall in cells differing by at most 1 on each axis — i.e. a candidate's
    neighbours are confined to the 27 cells around its own. This turns the
    O(n^2) all-pairs graph build into O(n · neighbours), which is the only way
    B/C stay usable against the ~238k-row `star_systems` table.
    """

    def __init__(self, nodes: list, cell: float):
        self.nodes = nodes
        self.cell = cell
        self.cells = {}
        for i, p in enumerate(nodes):
            key = (int(math.floor(p["x"] / cell)),
                   int(math.floor(p["y"] / cell)),
                   int(math.floor(p["z"] / cell)))
            self.cells.setdefault(key, []).append(i)

    def neighbors(self, i: int, max_dist: float):
        """Yield (j, dist_ly) for every node within max_dist of node i (j != i)."""
        p = self.nodes[i]
        cell = self.cell
        cx = int(math.floor(p["x"] / cell))
        cy = int(math.floor(p["y"] / cell))
        cz = int(math.floor(p["z"] / cell))
        px, py, pz = p["x"], p["y"], p["z"]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in self.cells.get((cx + dx, cy + dy, cz + dz), ()):
                        if j == i:
                            continue
                        q = self.nodes[j]
                        d = math.sqrt((px - q["x"]) ** 2 + (py - q["y"]) ** 2
                                      + (pz - q["z"]) ** 2)
                        if d <= max_dist:
                            yield j, d


# ── Shared cost-injected graph search (Phase T2 Part B seam) ─────────────────

def _grid_search(nodes, grid, s, t, max_jump_ly, optimize, edge_cost):
    """BFS / Dijkstra over a _SpatialGrid, with a pluggable additive edge cost.

    optimize="jumps" → BFS minimizing hop count (edge_cost ignored);
    optimize="distance" → Dijkstra minimizing the sum of edge_cost(u, v, w_ly),
    where w_ly is the geometric leg length. Passing edge_cost=lambda u,v,w: w
    reproduces the original distance-weighted jump route byte-identically; dust
    routing (core/dust_routing.py) passes the per-leg integrated A_V instead.

    Returns (prev, dist_arr) for path reconstruction by the caller.
    """
    nn = len(nodes)
    prev = [-1] * nn
    dist_arr = [float("inf")] * nn
    if optimize == "jumps":
        dist_arr[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            if u == t:
                break
            for v, _w in grid.neighbors(u, max_jump_ly):
                if dist_arr[v] == float("inf"):
                    dist_arr[v] = dist_arr[u] + 1
                    prev[v] = u
                    q.append(v)
    else:
        dist_arr[s] = 0.0
        pq = [(0.0, s)]
        done = [False] * nn
        while pq:
            du, u = heapq.heappop(pq)
            if done[u]:
                continue
            done[u] = True
            if u == t:
                break
            for v, w in grid.neighbors(u, max_jump_ly):
                c = du + edge_cost(u, v, w)
                if c < dist_arr[v]:
                    dist_arr[v] = c
                    prev[v] = u
                    heapq.heappush(pq, (dist_arr[v], v))
    return prev, dist_arr


# ── Waypoints ("via") — shared by the plain / dust / blend jump routes ────────
#
# A required-intermediate route is a fixed-endpoint Hamiltonian path over the
# metric closure of the terminals (origin + waypoints + destination): pairwise
# shortest paths (stage 1), brute-force the k! visit orders (stage 2), stitch the
# winning legs (stage 3). Waypoints are an unordered SET — the planner picks the
# cheapest order under whatever metric `optimize`/`edge_cost` selects.
#
# The stitched route is NOT a simple path: legs may reuse stars, so a star can
# appear twice in route[]/stars[]. Inherent to waypoint routing (forcing
# node-disjointness is NP-hard); documented rather than "fixed".

MAX_VIA_WAYPOINTS = 8


def _normalize_via(via):
    """Validate/clean a `via` argument. Returns (names, None) or (None, {"error"}).

    None/[]/whitespace-only entries → []. A bare string is rejected (it would
    iterate as characters). The cap is enforced here, BEFORE any resolution, so
    an over-cap list doesn't fire k SIMBAD lookups first.
    """
    if via is None:
        return [], None
    if isinstance(via, str):
        return None, {"error": "via must be a list of star names, not a single string."}
    # An ORDERED sequence only. A set/dict/generator would iterate in an order
    # the caller never chose, and stage 2 breaks ties on input order — so an
    # unordered container would silently make the "deterministic" visit order
    # vary between interpreter runs (string hash randomization).
    if not isinstance(via, (list, tuple)):
        return None, {"error": "via must be None or a list of star names."}
    names = []
    for v in via:
        if v is None:
            continue
        if not isinstance(v, str):
            return None, {"error": "via must be a list of star names."}
        if v.strip():
            names.append(v)
    if len(names) > MAX_VIA_WAYPOINTS:
        return None, {"error": f"At most {MAX_VIA_WAYPOINTS} waypoints."}
    return names, None


def _resolve_via(names):
    """Resolve cleaned waypoint names to node records, fail-fast.

    Returns (records, None) or (None, {"error"}); the "Waypoint N" index is
    1-based over the stripped list, matching compute_multi_stop_journey's
    "Stop N" wording.
    """
    recs = []
    for i, nm in enumerate(names):
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return None, {"error": f"Waypoint {i + 1} ('{nm.strip()}'): {rec['error']}"}
        recs.append(rec)
    return recs, None


def _check_terminal_indices(s, t, via_idx, via_names):
    """Reject terminals that collapsed onto the same pool node after merge.

    Checked on POST-MERGE indices, not on the resolved records: `_merge_endpoint`
    matches a pool row by name OR within 1e-3 ly, so two terminals each within
    1e-3 ly of the *same* pool star can be up to 2e-3 apart from each other —
    they pass a pairwise coordinate check and still merge to one index, which
    would make a stage-1 pair search from a node to itself.
    """
    if s == t:
        return {"error": "Origin and destination are the same star."}
    for i, wi in enumerate(via_idx):
        nm = via_names[i].strip()
        if wi == s:
            return {"error": f"Waypoint {i + 1} ('{nm}') is the same star as the origin."}
        if wi == t:
            return {"error": f"Waypoint {i + 1} ('{nm}') is the same star as the destination."}
        for j in range(i):
            if wi == via_idx[j]:
                return {"error": f"Waypoint {i + 1} ('{nm}') is the same star as "
                                 f"waypoint {j + 1} ('{via_names[j].strip()}')."}
    return None


def _route_through(nodes, grid, s, t, via_idx, max_jump_ly, optimize, edge_cost):
    """Shortest s→t path visiting every node in `via_idx` (in any order).

    Returns ``(path, seams, unreachable_leg)``:
      * ``path``  — flat list of node indices, junction nodes de-duplicated;
      * ``seams`` — positions in `path` of the leg boundaries, first and last
        included, so ``seams[1:-1]`` are the waypoint arrivals in visit order;
      * ``unreachable_leg`` — ``None`` on success, else ``{"from", "to"}``.

    With `via_idx` empty this is a straight passthrough to the single
    `_grid_search` + reconstruction the un-waypointed route has always used.
    """
    terminals = [s] + list(via_idx) + [t]
    k = len(via_idx)

    # Stage 1 — metric closure: one `_grid_search` per terminal PAIR
    # (C(k+2,2)−1, i.e. 2 at k=1 … 44 at the cap). Costs are symmetric, so each
    # unordered pair is searched once and the stored path reversed for the other
    # direction. The direct origin↔destination pair is skipped when waypoints
    # exist (the path must route through them, so no permutation uses it).
    #
    # The plan's alternative — one full single-source sweep per terminal (k+2
    # runs, via a sentinel target that never matches) — was built and MEASURED
    # against the real 256k-row pool: Sol → 38 Vir via 70 Vir at max_jump 20
    # took 227 s as sweeps vs 4.96 s as pairs (k=3: 11.7 s as pairs). Pairwise
    # wins decisively because `_grid_search` early-exits when the target pops,
    # while a sweep must settle the entire reachable component — which at a
    # usable jump range is most of the catalogue. Do not "optimize" this back.
    #
    # An infinite pair SHORT-CIRCUITS the whole closure. Reachability is an
    # equivalence relation on an undirected graph, so cost(a,b) = ∞ means a and
    # b sit in different components — and then no visit order can work, because
    # a route visiting every terminal would put them all in one component. This
    # is the difference between one full sweep and k+1 of them: the early exit
    # fires only on SUCCESS, so an unreachable pair drains the entire reachable
    # component every time it is searched. Stranding a route with a far-flung
    # waypoint is a documented, expected outcome, so this is a likely path, not
    # an exotic one. Pairs are ordered origin-first, so a terminal disconnected
    # from the origin is caught on the first sweep.
    paths, costs = {}, {}
    for i in range(len(terminals)):
        for j in range(i + 1, len(terminals)):
            if k and i == 0 and j == len(terminals) - 1:
                continue
            a, b = terminals[i], terminals[j]
            prev, dist_arr = _grid_search(nodes, grid, a, b, max_jump_ly,
                                          optimize, edge_cost)
            if dist_arr[b] == float("inf"):
                return [], [], {"from": nodes[a]["name"], "to": nodes[b]["name"]}
            fwd, cur = [], b
            while cur != -1:
                fwd.append(cur)
                cur = prev[cur]
            fwd.reverse()
            # Reconstruct now and drop `prev` — retaining one ~256k-int array per
            # pair would be tens of MB at the waypoint cap.
            paths[(a, b)] = fwd
            paths[(b, a)] = list(reversed(fwd))
            costs[(a, b)] = costs[(b, a)] = dist_arr[b]

    # Stage 2 — order selection. Every pair is finite by the short-circuit
    # above, so this only picks the cheapest. itertools.permutations yields in
    # lexicographic order of the waypoint indices and the comparison is strict,
    # so the first (lexicographically smallest) permutation wins any tie —
    # determinism that matters under optimize="jumps", where the objective is a
    # small integer and ties are common.
    best_order, best_cost = (), float("inf")
    for perm in itertools.permutations(range(k)):
        seq = [s] + [via_idx[i] for i in perm] + [t]
        c = sum(costs[(seq[i], seq[i + 1])] for i in range(len(seq) - 1))
        if c < best_cost:
            best_cost, best_order = c, perm

    # Stage 3 — stitch, de-duplicating the junction node at each seam.
    seq = [s] + [via_idx[i] for i in best_order] + [t]
    path, seams = [], [0]
    for i in range(len(seq) - 1):
        leg = paths[(seq[i], seq[i + 1])]
        path.extend(leg if i == 0 else leg[1:])
        seams.append(len(path) - 1)
    return path, seams, None


# ── A: Optimal Tour ──────────────────────────────────────────────────────────

def _tour_len(order: list, closed: bool) -> float:
    s = 0.0
    for i in range(len(order) - 1):
        s += _node_dist(order[i], order[i + 1])
    if closed and len(order) > 1:
        s += _node_dist(order[-1], order[0])
    return s


def compute_optimal_tour(star_names, velocity_input: float,
                         use_times_c: bool, closed: bool = False) -> dict:
    """Visit a set of stars in the shortest-total-distance order.

    Nearest-neighbor seed from the fixed first stop, then 2-opt local search.
    `closed=True` returns to the start (adds the wrap leg).

    Returns:
        {legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours,
                cumulative_hours, travel_time, cumulative_time}],
         total_ly, total_hours, total_time, naive_total_ly, optimized_total_ly,
         saved_ly, saved_pct, closed, stars:[map dicts in optimized order]}
        or {"error": str}
    """
    # Dedup case-insensitively, preserving order.
    seen, names = set(), []
    for nm in (star_names or []):
        k = (nm or "").strip().lower()
        if k and k not in seen:
            seen.add(k)
            names.append(nm)
    if len(names) < 2:
        return {"error": "Enter at least two stars."}
    if velocity_input is None or velocity_input <= 0:
        return {"error": "Velocity must be positive."}

    if use_times_c:
        ly_hr = velocity_input / HOURS_PER_JULIAN_YEAR
        times_c = velocity_input
    else:
        ly_hr = velocity_input
        times_c = velocity_input * HOURS_PER_JULIAN_YEAR

    typed = []
    for nm in names:
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return {"error": f"'{nm}': {rec['error']}"}
        typed.append(rec)

    naive_total_ly = _tour_len(typed, closed)

    # Nearest-neighbor seed from the fixed first stop.
    remaining = typed[1:]
    order = [typed[0]]
    while remaining:
        bi, bd = 0, float("inf")
        for ci, c in enumerate(remaining):
            d = _node_dist(order[-1], c)
            if d < bd:
                bd, bi = d, ci
        order.append(remaining.pop(bi))

    # 2-opt (start fixed at index 0; reverse segments [i..k]). P2.7: the current
    # tour length is an invariant of `order`, so it's hoisted out of the O(n²) (i,k)
    # loop and only recomputed when a swap is accepted — behavior-identical (cur
    # always equals _tour_len(order, closed), same acceptance/tie-breaking).
    n = len(order)
    cur_len = _tour_len(order, closed)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                cand_len = _tour_len(cand, closed)
                if cand_len + 1e-9 < cur_len:
                    order = cand
                    cur_len = cand_len
                    improved = True

    optimized_total_ly = cur_len

    # Build legs (consecutive; + wrap when closed).
    pairs = [(order[i], order[i + 1]) for i in range(len(order) - 1)]
    if closed:
        pairs.append((order[-1], order[0]))

    legs = []
    cumulative_hours = 0.0
    total_ly = 0.0
    for i, (a, b) in enumerate(pairs):
        d = _node_dist(a, b)
        hours = d / ly_hr
        cumulative_hours += hours
        total_ly += d
        legs.append({
            "leg": i + 1, "origin": a["name"], "dest": b["name"],
            "distance_ly": d, "ly_hr": ly_hr, "times_c": times_c,
            "hours": hours, "cumulative_hours": cumulative_hours,
            "travel_time": format_travel_time(hours),
            "cumulative_time": format_travel_time(cumulative_hours),
        })

    saved_ly = max(naive_total_ly - optimized_total_ly, 0.0)
    saved_pct = (saved_ly / naive_total_ly * 100.0) if naive_total_ly > 0 else 0.0

    return {
        "legs": legs,
        "total_ly": total_ly,
        "total_hours": cumulative_hours,
        "total_time": format_travel_time(cumulative_hours),
        "naive_total_ly": naive_total_ly,
        "optimized_total_ly": optimized_total_ly,
        "saved_ly": saved_ly,
        "saved_pct": saved_pct,
        "closed": closed,
        "stars": [_map_node(n) for n in order],
    }


# ── B: Jump-Range Pathfinding ────────────────────────────────────────────────

def compute_jump_route(origin: str, destination: str, max_jump_ly: float,
                       optimize: str = "distance", via=None) -> dict:
    """Route origin→destination through intermediate stars, each jump ≤ max_jump_ly.

    optimize="distance" → Dijkstra (min total ly); "jumps" → BFS (fewest jumps).
    An unreachable destination is a clear result (reachable=False), not an error.

    `via` is None or a list of star names that the route MUST pass through — an
    unordered set, visited in whichever order is cheapest under `optimize` (cap
    MAX_VIA_WAYPOINTS). With waypoints the route may revisit a star, so
    route[]/stars[] can repeat a name; see _route_through.

    Returns:
        {origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly,
         route:[{jump, from, to, jump_ly, cumulative_ly, waypoint}], max_jump_ly,
         stars:[map dicts along the route], via, via_legs, unreachable_leg}
        or {"error": str}
    """
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "Max jump distance must be positive."}
    if optimize not in ("distance", "jumps"):
        return {"error": "optimize must be 'distance' or 'jumps'."}
    via_names, err = _normalize_via(via)
    if err:
        return err

    o = _resolve_star_position(origin)
    if "error" in o:
        return {"error": f"Origin: {o['error']}"}
    d = _resolve_star_position(destination)
    if "error" in d:
        return {"error": f"Destination: {d['error']}"}
    if o["name"].strip().lower() == d["name"].strip().lower() or _node_dist(o, d) <= 1e-3:
        return {"error": "Origin and destination are the same star."}
    via_recs, err = _resolve_via(via_names)
    if err:
        return err

    pool_res = _load_star_systems_positions()
    nodes = list(pool_res["stars"]) if "stars" in pool_res else []
    # Every terminal must be merged BEFORE the grid is built — _SpatialGrid
    # indexes at construction, so a node appended after is invisible to it.
    s = _merge_endpoint(nodes, o)
    t = _merge_endpoint(nodes, d)
    via_idx = [_merge_endpoint(nodes, w) for w in via_recs]
    err = _check_terminal_indices(s, t, via_idx, via_names)
    if err:
        return err
    grid = _SpatialGrid(nodes, max_jump_ly)

    path, seams, unreachable_leg = _route_through(
        nodes, grid, s, t, via_idx, max_jump_ly, optimize,
        edge_cost=lambda u, v, w: w)

    direct_ly = _node_dist(o, d)
    if unreachable_leg is not None:
        return {
            "origin_info": o, "dest_info": d, "reachable": False,
            "optimize": optimize, "jumps": 0, "total_ly": 0.0,
            "direct_ly": direct_ly, "route": [], "max_jump_ly": max_jump_ly,
            # Waypoints are reported from their MERGED pool nodes, exactly as the
            # reachable branch does, so an alias that merges onto a catalogue row
            # reports the same name and spectral colour either way. The two
            # endpoints keep the resolved-record form this branch has always used.
            "stars": ([_map_node(o)] + [_map_node(nodes[i]) for i in via_idx]
                      + [_map_node(d)]),
            "via": [nodes[i]["name"] for i in via_idx], "via_legs": [],
            "unreachable_leg": unreachable_leg,
        }

    waypoint_at = set(seams[1:-1])
    route = []
    cumulative_ly = 0.0
    for i in range(len(path) - 1):
        a, b = nodes[path[i]], nodes[path[i + 1]]
        jd = _node_dist(a, b)
        cumulative_ly += jd
        route.append({
            "jump": i + 1, "from": a["name"], "to": b["name"],
            "jump_ly": jd, "cumulative_ly": cumulative_ly,
            "waypoint": (i + 1) in waypoint_at,
        })

    via_legs = []
    for i in range(len(seams) - 1):
        p0, p1 = seams[i], seams[i + 1]
        via_legs.append({
            "from": nodes[path[p0]]["name"], "to": nodes[path[p1]]["name"],
            "jumps": p1 - p0,
            "ly": sum(r["jump_ly"] for r in route[p0:p1]),
        })

    return {
        "origin_info": o, "dest_info": d, "reachable": True,
        "optimize": optimize, "jumps": len(path) - 1, "total_ly": cumulative_ly,
        "direct_ly": direct_ly, "route": route, "max_jump_ly": max_jump_ly,
        "stars": [_map_node(nodes[i]) for i in path],
        "via": [nodes[path[p]]["name"] for p in seams[1:-1]],
        "via_legs": via_legs if via_idx else [],
        "unreachable_leg": None,
    }


# ── C: Jump Network / Reachability ───────────────────────────────────────────

def compute_jump_network(start: str, max_jump_ly: float,
                         max_jumps=None) -> dict:
    """BFS reachability from `start` at jump range `max_jump_ly`.

    Each reachable star gets its minimum jump count (tier); the rest are
    out-of-range. `max_jumps` caps the frontier.

    Returns:
        {start_name, max_jump_ly, max_jumps, max_tier, reachable_count,
         total_in_pool, unreachable_count,
         tiers:[{jumps, stars:[{star_name, desig, sp_type, dist_from_start_ly,
                                ly_from_sol}]}],
         stars:[map dicts, colour overridden per tier; start gold]}
        or {"error": str}
    """
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "Max jump distance must be positive."}
    if max_jumps is not None:
        try:
            max_jumps = int(max_jumps)
        except (TypeError, ValueError):
            return {"error": "Max jumps must be a positive integer."}
        if max_jumps < 1:
            return {"error": "Max jumps must be a positive integer."}

    st = _resolve_star_position(start)
    if "error" in st:
        return st

    pool_res = _load_star_systems_positions()
    if "error" in pool_res:
        return pool_res
    nodes = list(pool_res["stars"])
    total_in_pool = len(nodes)          # original star_systems rows (pre-merge)
    s = _merge_endpoint(nodes, st)
    start_is_appended = s >= total_in_pool   # start wasn't already a pool row
    grid = _SpatialGrid(nodes, max_jump_ly)

    nn = len(nodes)
    tier = [-1] * nn
    tier[s] = 0
    q = deque([s])
    while q:
        u = q.popleft()
        if max_jumps is not None and tier[u] >= max_jumps:
            continue
        for v, _w in grid.neighbors(u, max_jump_ly):
            if tier[v] == -1:
                tier[v] = tier[u] + 1
                q.append(v)

    reached = [i for i in range(nn) if tier[i] >= 0]
    reached.sort(key=lambda i: (tier[i], nodes[i].get("ly", 0.0)))
    max_tier = max((tier[i] for i in reached), default=0)

    # Tier-grouped table.
    tiers = []
    for ti in range(0, max_tier + 1):
        members = [i for i in reached if tier[i] == ti]
        if not members:
            continue
        tiers.append({
            "jumps": ti,
            "stars": [{
                "star_name": nodes[i]["name"], "desig": nodes[i].get("desig", ""),
                "sp_type": nodes[i].get("sp_type", ""),
                "dist_from_start_ly": _node_dist(nodes[i], st),
                "ly_from_sol": nodes[i].get("ly", 0.0),
            } for i in members],
        })

    # Map nodes: every reached node, colour overridden per tier.
    stars = []
    for i in reached:
        m = _map_node(nodes[i])
        m["color"] = TIER_COLORS[min(tier[i], len(TIER_COLORS) - 1)]
        m["tier"] = tier[i]
        stars.append(m)
    # Ensure the start is first (gold ★ at the centred origin).
    stars.sort(key=lambda m: 0 if m["name"] == st["name"] else 1)

    # reachable_count includes the start node; unreachable_count is over the
    # original star_systems rows (so it excludes an appended Sol/SIMBAD start).
    reachable_original = len(reached) - (1 if start_is_appended else 0)
    unreachable_count = total_in_pool - reachable_original

    return {
        "start_name": st["name"], "max_jump_ly": max_jump_ly,
        "max_jumps": max_jumps, "max_tier": max_tier,
        "reachable_count": len(reached), "total_in_pool": total_in_pool,
        "unreachable_count": unreachable_count,
        "tiers": tiers,
        "stars": stars,
    }


# ── D: Farthest-First Coverage ───────────────────────────────────────────────

def compute_farthest_first_chain(start: str, num_stops: int,
                                 max_reach_ly=None) -> dict:
    """De-clustering coverage: each step picks the unvisited star farthest from
    the visited set (optionally still within max_reach_ly of some visited star).

    Returns:
        {chain:[{step, star_name, desig, sp_type, sep_to_visited_ly,
                 dist_from_start_ly, ly_from_sol}],
         tree_edges:[{from_index, to_index}], stars:[map dicts, start at 0],
         widest_ly, stopped_early, start_name}
        or {"error": str}
    """
    try:
        num_stops = int(num_stops)
    except (TypeError, ValueError):
        return {"error": "Number of stops must be a positive integer."}
    if num_stops < 1:
        return {"error": "Number of stops must be a positive integer."}
    if max_reach_ly is not None and max_reach_ly <= 0:
        return {"error": "Max reach must be positive."}
    reach = float("inf") if max_reach_ly is None else max_reach_ly

    st = _resolve_star_position(start)
    if "error" in st:
        return st

    pool_res = _load_star_systems_positions()
    if "error" in pool_res:
        return pool_res
    # Self-exclusion: drop the start's own row (within 1e-3 ly).
    pool = [p for p in pool_res["stars"] if _node_dist(p, st) > 1e-3]

    # Running farthest-first: mind[ci] = distance from pool[ci] to its nearest
    # visited node; near[ci] = that node's index in `visited`. Updated against
    # each newly added node so the loop is O(num_stops · n), not O(num_stops^2 · n).
    npool = len(pool)
    mind = [_node_dist(pool[ci], st) for ci in range(npool)]
    near = [0] * npool
    used = [False] * npool

    visited = [st]
    chain = []
    tree_edges = []
    stopped_early = False
    for step in range(1, num_stops + 1):
        best_i, best_spread = -1, -1.0
        for ci in range(npool):
            if used[ci] or mind[ci] > reach:
                continue
            if mind[ci] > best_spread:
                best_spread, best_i = mind[ci], ci
        if best_i < 0:
            stopped_early = True
            break
        used[best_i] = True
        c = pool[best_i]
        new_idx = len(visited)
        tree_edges.append({"from_index": near[best_i], "to_index": new_idx})
        visited.append(c)
        chain.append({
            "step": step, "star_name": c["name"], "desig": c.get("desig", ""),
            "sp_type": c.get("sp_type", ""), "sep_to_visited_ly": best_spread,
            "dist_from_start_ly": _node_dist(c, st),
            "ly_from_sol": c.get("ly", 0.0),
        })
        # Relax running min/near against the just-added node.
        for cj in range(npool):
            if used[cj]:
                continue
            dj = _node_dist(pool[cj], c)
            if dj < mind[cj]:
                mind[cj], near[cj] = dj, new_idx

    widest_ly = max((_node_dist(v, st) for v in visited[1:]), default=0.0)

    return {
        "chain": chain,
        "tree_edges": tree_edges,
        "stars": [_map_node(v) for v in visited],
        "widest_ly": widest_ly,
        "stopped_early": stopped_early,
        "start_name": st["name"],
    }


# ── Phase K — Honorverse missile intercept (K3) ──────────────────────────────

def compute_missile_intercept(launcher_vel_xc, missile_accel_g, missile_delta_v_xc,
                              target_vel_xc, range_lm) -> dict:
    """Whether a missile from a moving launcher intercepts a moving target.

    1D head-on, non-relativistic (valid at these ×c scales). target_vel_xc > 0 =
    receding (same direction as the missile); < 0 = head-on (closing). The missile
    burns at constant accel until its delta-v budget is spent, then coasts.

    Self-validating (range/accel/delta-v > 0). `intercepts=False` is a normal
    result. Returns:
        {intercepts, intercept_phase, time_to_impact_s, time_to_impact_str,
         v_burnout_xc, v_close_xc, range_at_burnout_lm, burn_duration_s}
        or {"error": str}
    """
    if range_lm is None or range_lm <= 0:
        return {"error": "Initial range must be positive."}
    if missile_accel_g is None or missile_accel_g <= 0:
        return {"error": "Missile acceleration must be positive."}
    if missile_delta_v_xc is None or missile_delta_v_xc <= 0:
        return {"error": "Missile delta-v budget must be positive."}
    if launcher_vel_xc is None or target_vel_xc is None:
        return {"error": "Launcher and target velocity must be numbers."}

    v_l = launcher_vel_xc * _C_MS
    v_t = target_vel_xc * _C_MS
    dv = missile_delta_v_xc * _C_MS
    accel = missile_accel_g * _G_MS2
    range_m = range_lm * _M_PER_LM

    t_burn = dv / accel
    v_bo = v_l + dv
    d_burn = v_l * t_burn + 0.5 * accel * t_burn ** 2
    closing_burn = d_burn - v_t * t_burn          # missile's gain on the target during burn
    v_close = v_bo - v_t

    intercepts, phase, t_impact = False, None, None
    if closing_burn >= range_m:                   # caught up before burnout
        intercepts, phase = True, "burn"
        t_impact = t_burn * (range_m / d_burn) if d_burn > 0 else 0.0
    elif v_close > 0:                             # closes during the coast phase
        t_coast = (range_m - closing_burn) / v_close
        intercepts, phase, t_impact = True, "coast", t_burn + t_coast
    # else v_close <= 0 and not caught during burn → never intercepts

    return {
        "intercepts": intercepts,
        "intercept_phase": phase,
        "time_to_impact_s": t_impact,
        "time_to_impact_str": format_travel_time(t_impact / 3600.0) if t_impact is not None else None,
        "v_burnout_xc": v_bo / _C_MS,
        "v_close_xc": v_close / _C_MS,
        "range_at_burnout_lm": (range_m - closing_burn) / _M_PER_LM,
        "burn_duration_s": t_burn,
    }
