# core/calculators.py — Distance, speed, travel time, and brachistochrone functions.
# Phase A: compute_ly_hr_to_times_c (option 21).
# Phase B: options 22–26.
# Phase C: compute_lookup_star_for_distance, compute_distance_between_stars,
#           compute_stars_within_distance_of_sol, compute_stars_within_distance_of_star.
# Phase D: remaining brachistochrone and travel-time-between-stars functions.

import csv
import heapq
import math
import os
from collections import deque

from .shared import _make_simbad, _network_error_msg, _timeout_ctx, _with_retries

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

    try:
        with _timeout_ctx(30):
            # Inside the try: _make_simbad lazily hits SIMBAD's TAP capabilities
            # endpoint, so a connection failure there is classified by
            # _network_error_msg rather than leaking a raw DALServiceError.
            custom_simbad = _make_simbad("plx_value")
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
            "SELECT star_name, designations, spectral_type, light_years, ra, dec "
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
            "x": x, "y": y, "z": z,
        })

    matches.sort(key=lambda r: r["Light Years"])
    return {"limit_ly": limit_ly, "count": len(matches), "stars": matches}


def compute_stars_within_distance_of_star(center_star: str, limit_ly: float) -> dict:
    """List all stars in the star_systems DB table within limit_ly light years of center_star.

    Queries SIMBAD for center_star, then iterates star_systems and computes
    3D Euclidean distances.

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
            "SELECT star_name, designations, spectral_type, parallax, light_years, ra, dec "
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
        except (ValueError, TypeError):
            continue
        x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
        dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
        if 0.001 < dist <= limit_ly:
            matches.append({
                "Star Name":         row["star_name"] or "",
                "Star Designations": row["designations"] or "",
                "Spectral Type":     row["spectral_type"] or "",
                "Distance":          dist,
                "x": x, "y": y, "z": z,
            })

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
_C_MS      = 299_792_458.0        # speed of light in m/s
_M_PER_AU  = 149_597_870_700.0    # metres per AU
_M_PER_LM  = _C_MS * 60.0        # metres per light-minute

# ── Horizons ID map (options 32, 33) ──────────────────────────────────────────
_HORIZONS_ID_MAP = {
    "sun": "10",
    "mercury": "199", "venus": "299", "earth": "399", "mars": "499",
    "jupiter": "599", "saturn": "699", "uranus": "799", "neptune": "899",
    "pluto": "999", "ceres": "1", "vesta": "4", "pallas": "2", "juno": "3",
    "eris": "136199", "makemake": "136472", "haumea": "136108", "sedna": "90377",
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
    "eros": "433", "ida": "243", "gaspra": "951", "mathilde": "253",
    "itokawa": "25143", "ryugu": "162173", "bennu": "101955", "apophis": "99942",
    "lutetia": "21", "steins": "2867", "churyumov": "67P",
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
    import urllib.request
    import urllib.parse

    if horizons_id in _BODY_PROPS_CACHE:
        return _BODY_PROPS_CACHE[horizons_id]

    try:
        params = {
            "format": "text",
            "COMMAND": horizons_id,
            "OBJ_DATA": "YES",
            "MAKE_EPHEM": "NO",
        }
        url = ("https://ssd.jpl.nasa.gov/api/horizons.api?"
               + urllib.parse.urlencode(params))

        def _do_fetch():
            with urllib.request.urlopen(url, timeout=15) as resp:
                return resp.read().decode("utf-8")

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


def _star_map_color(sp_type: str) -> str:
    """Spectral type → map dot colour (leading-letter; default grey)."""
    palette = {
        "O": "#9bb0ff", "B": "#aabfff", "A": "#cad7ff", "F": "#f8f7ff",
        "G": "#fff4c2", "K": "#ffd2a1", "M": "#ff9d6c", "D": "#dfe6ff",
    }
    c = (sp_type or "").strip()
    return palette.get(c[0].upper(), "#cccccc") if c else "#cccccc"


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
        "sp_type": "", "desig": s.get("desig_str", ""), "source": "simbad",
    }


def _map_node(rec: dict) -> dict:
    """Build a star-map-compatible dict from a resolved record."""
    return {
        "name": rec["name"], "desig": rec.get("desig", ""),
        "sp_type": rec.get("sp_type", ""),
        "color": _star_map_color(rec.get("sp_type", "")),
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

    # 2-opt (start fixed at index 0; reverse segments [i..k]).
    n = len(order)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                if _tour_len(cand, closed) + 1e-9 < _tour_len(order, closed):
                    order = cand
                    improved = True

    optimized_total_ly = _tour_len(order, closed)

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
                       optimize: str = "distance") -> dict:
    """Route origin→destination through intermediate stars, each jump ≤ max_jump_ly.

    optimize="distance" → Dijkstra (min total ly); "jumps" → BFS (fewest jumps).
    An unreachable destination is a clear result (reachable=False), not an error.

    Returns:
        {origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly,
         route:[{jump, from, to, jump_ly, cumulative_ly}], max_jump_ly,
         stars:[map dicts along the route]}
        or {"error": str}
    """
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "Max jump distance must be positive."}
    if optimize not in ("distance", "jumps"):
        return {"error": "optimize must be 'distance' or 'jumps'."}

    o = _resolve_star_position(origin)
    if "error" in o:
        return {"error": f"Origin: {o['error']}"}
    d = _resolve_star_position(destination)
    if "error" in d:
        return {"error": f"Destination: {d['error']}"}
    if o["name"].strip().lower() == d["name"].strip().lower() or _node_dist(o, d) <= 1e-3:
        return {"error": "Origin and destination are the same star."}

    pool_res = _load_star_systems_positions()
    nodes = list(pool_res["stars"]) if "stars" in pool_res else []
    s = _merge_endpoint(nodes, o)
    t = _merge_endpoint(nodes, d)
    grid = _SpatialGrid(nodes, max_jump_ly)

    nn = len(nodes)
    prev = [-1] * nn
    if optimize == "jumps":
        dist_arr = [float("inf")] * nn
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
        dist_arr = [float("inf")] * nn
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
                if du + w < dist_arr[v]:
                    dist_arr[v] = du + w
                    prev[v] = u
                    heapq.heappush(pq, (dist_arr[v], v))

    direct_ly = _node_dist(o, d)
    reachable = dist_arr[t] != float("inf")
    if not reachable:
        return {
            "origin_info": o, "dest_info": d, "reachable": False,
            "optimize": optimize, "jumps": 0, "total_ly": 0.0,
            "direct_ly": direct_ly, "route": [], "max_jump_ly": max_jump_ly,
            "stars": [_map_node(o), _map_node(d)],
        }

    # Reconstruct the path.
    path = []
    cur = t
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    route = []
    cumulative_ly = 0.0
    for i in range(len(path) - 1):
        a, b = nodes[path[i]], nodes[path[i + 1]]
        jd = _node_dist(a, b)
        cumulative_ly += jd
        route.append({
            "jump": i + 1, "from": a["name"], "to": b["name"],
            "jump_ly": jd, "cumulative_ly": cumulative_ly,
        })

    return {
        "origin_info": o, "dest_info": d, "reachable": True,
        "optimize": optimize, "jumps": len(path) - 1, "total_ly": cumulative_ly,
        "direct_ly": direct_ly, "route": route, "max_jump_ly": max_jump_ly,
        "stars": [_map_node(nodes[i]) for i in path],
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
