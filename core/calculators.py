# core/calculators.py — Distance, speed, travel time, and brachistochrone functions.
# Phase A: compute_ly_hr_to_times_c (option 21).
# Phase B: options 22–26.
# Phase C: compute_lookup_star_for_distance, compute_distance_between_stars,
#           compute_stars_within_distance_of_sol, compute_stars_within_distance_of_star.
# Phase D: remaining brachistochrone and travel-time-between-stars functions.

import csv
import math
import os

HOURS_PER_JULIAN_YEAR = 8765.8128  # 365.25 * 24

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
    HOURS_PER_YEAR  = 365.25 * 24          # 8765.82
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


def _to_cartesian(ra_deg: float, dec_deg: float, ly: float):
    """Convert spherical (RA/DEC + distance) to Cartesian light-year coordinates."""
    ra_r  = math.radians(ra_deg)
    dec_r = math.radians(dec_deg)
    return (
        ly * math.cos(dec_r) * math.cos(ra_r),
        ly * math.cos(dec_r) * math.sin(ra_r),
        ly * math.sin(dec_r),
    )


def compute_lookup_star_for_distance(designation: str) -> dict:
    """Query SIMBAD for RA, DEC, parallax, and short designations.

    Special-cases 'sun' / 'sol' (case-insensitive) → origin coordinates with
    no SIMBAD query.

    Returns:
        {name, ra_deg, dec_deg, ly, desig_str}   on success
        {"error": str}                            on failure
    """
    norm = designation.strip().lower()
    if norm in ("sun", "sol"):
        return {
            "name":     designation.strip(),
            "ra_deg":   0.0,
            "dec_deg":  0.0,
            "ly":       0.0,
            "desig_str": "",
        }

    from astroquery.simbad import Simbad

    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("plx_value")

    try:
        result     = custom_simbad.query_object(designation)
        ids_result = Simbad.query_objectids(designation)
    except Exception as e:
        return {"error": str(e)}

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

    desig_found = {k: None for k in ("NAME", "HD", "HR", "GJ", "Wolf")}
    desig_prefix_map = [
        ("NAME ", "NAME"), ("HD ",  "HD"),  ("HR ",   "HR"),
        ("GJ ",   "GJ"),   ("Wolf ", "Wolf"),
    ]
    if ids_result is not None:
        for id_row in ids_result:
            id_str = str(id_row["id"]).strip()
            for prefix, key in desig_prefix_map:
                if id_str.startswith(prefix) and desig_found[key] is None:
                    desig_found[key] = id_str
                    break
    desig_str = ", ".join(v for v in desig_found.values() if v)

    return {"name": name, "ra_deg": ra_deg, "dec_deg": dec_deg, "ly": ly, "desig_str": desig_str}


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


def compute_stars_within_distance_of_sol(limit_ly: float) -> dict:
    """List all stars in starSystems.csv within limit_ly light years of Sol.

    Returns:
        {limit_ly, count, stars: [sorted list of row dicts with 'Light Years' key]}
        or {"error": str} if the CSV is missing.
    """
    csv_path = os.path.normpath(os.path.join(_DATA_DIR, "starSystems.csv"))
    if not os.path.exists(csv_path):
        return {"error": "starSystems.csv not found — run option 50 first to generate it."}

    matches = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    ly = float(row["Light Years"])
                except (ValueError, KeyError):
                    continue
                if ly <= limit_ly:
                    matches.append({
                        "Star Name":         row.get("Star Name", ""),
                        "Star Designations": row.get("Star Designations", ""),
                        "Spectral Type":     row.get("Spectral Type", ""),
                        "Light Years":       ly,
                    })
    except Exception as e:
        return {"error": f"Error reading starSystems.csv: {e}"}

    matches.sort(key=lambda r: r["Light Years"])
    return {"limit_ly": limit_ly, "count": len(matches), "stars": matches}


def compute_stars_within_distance_of_star(center_star: str, limit_ly: float) -> dict:
    """List all stars in starSystems.csv within limit_ly light years of center_star.

    Queries SIMBAD for center_star, then iterates starSystems.csv and computes
    3D Euclidean distances.

    Returns:
        {center, limit_ly, count, stars: [sorted list of dicts with 'Distance' key]}
        or {"error": str} on failure.
    """
    s = compute_lookup_star_for_distance(center_star)
    if "error" in s:
        return s

    csv_path = os.path.normpath(os.path.join(_DATA_DIR, "starSystems.csv"))
    if not os.path.exists(csv_path):
        return {"error": "starSystems.csv not found — run option 50 first to generate it."}

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

    cx, cy, cz = _to_cartesian(s["ra_deg"], s["dec_deg"], s["ly"])

    matches = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    plx = float(row["Parallax"])
                    if plx <= 0:
                        continue
                    ly = 1000.0 / plx * 3.26156
                    ra_deg  = _parse_ra(row["RA"])
                    dec_deg = _parse_dec(row["DEC"])
                except (ValueError, KeyError):
                    continue
                x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
                dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
                if 0.001 < dist <= limit_ly:
                    matches.append({
                        "Star Name":         row.get("Star Name", ""),
                        "Star Designations": row.get("Star Designations", ""),
                        "Spectral Type":     row.get("Spectral Type", ""),
                        "Distance":          dist,
                    })
    except Exception as e:
        return {"error": f"Error reading starSystems.csv: {e}"}

    matches.sort(key=lambda r: r["Distance"])
    return {
        "center":   s["name"],
        "limit_ly": limit_ly,
        "count":    len(matches),
        "stars":    matches,
    }


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
