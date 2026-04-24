# core/viz.py — Data-prep functions for Phase E visualizations (no Qt, pure Python).

import csv
import math
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")

# ── Kopparapu et al. 2014 HZ coefficients ─────────────────────────────────────

_KOPPARAPU_PARAMS = {
    "rv":   (1.776,  2.136e-4,  2.533e-8,  -1.332e-11, -3.097e-15),
    "rg5":  (1.188,  1.433e-4,  1.707e-8,  -8.968e-12, -2.084e-15),
    "rg01": (0.99,   1.209e-4,  1.404e-8,  -7.418e-12, -1.713e-15),
    "rg":   (1.107,  1.332e-4,  1.580e-8,  -8.308e-12, -1.931e-15),
    "mg":   (0.356,  6.171e-5,  1.698e-9,  -3.198e-12, -5.575e-16),
    "em":   (0.320,  5.547e-5,  1.526e-9,  -2.874e-12, -5.011e-16),
}

# Zone boundary definitions, ordered inner → outer.
# Each entry is the fill color of the region INSIDE this boundary line.
# (Painted from outside-in so each circle covers only the interior.)
_HZ_ZONE_DEFS = [
    # (boundary key, region label, fill_color)
    ("rv",   "Too Hot  (< Recent Venus)",            "#CC3300"),
    ("rg5",  "Optimistic Inner  (rv → rg5)",         "#FF8833"),
    ("rg",   "Conservative Inner I  (rg5 → rg)",     "#FFCC00"),
    ("rg01", "Conservative Inner II  (rg → rg01)",   "#CCDD22"),
    ("mg",   "Conservative HZ  (rg01 → mg)",         "#33AA55"),
    ("em",   "Optimistic Outer  (mg → em)",          "#4499FF"),
]

# Spectral class colours for star map scatter
_SPECTRAL_COLORS = {
    "O": "#9BB0FF",
    "B": "#AABFFF",
    "A": "#CAD7FF",
    "F": "#F8F7FF",
    "G": "#FFF4EA",
    "K": "#FFD2A1",
    "M": "#FF8D3F",
    "L": "#FF4500",
    "T": "#CD853F",
    "W": "#E040FB",
    "D": "#B0C4DE",
}

# Cyclic orbit colours for system-orbit diagram
_ORBIT_COLORS = [
    "#4FC3F7", "#81C784", "#FFB74D", "#F06292", "#CE93D8",
    "#80CBC4", "#FFCC80", "#EF9A9A", "#B39DDB", "#80DEEA",
]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _kopparapu_seff(teff: float, key: str) -> float:
    tS = teff - 5780.0
    S0, a, b, c, d = _KOPPARAPU_PARAMS[key]
    return S0 + a * tS + b * tS**2 + c * tS**3 + d * tS**4


def _parse_ra_hms(s: str):
    """'HH MM SS.SSSS' → decimal degrees, or None on failure."""
    parts = s.strip().split()
    if len(parts) != 3:
        return None
    try:
        return (float(parts[0]) + float(parts[1]) / 60.0 + float(parts[2]) / 3600.0) * 15.0
    except ValueError:
        return None


def _parse_dec_dms(s: str):
    """'±DD MM SS.SSS' → decimal degrees, or None on failure."""
    s = s.strip()
    sign = -1.0 if s.startswith("-") else 1.0
    parts = s.lstrip("+-").split()
    if len(parts) != 3:
        return None
    try:
        return sign * (float(parts[0]) + float(parts[1]) / 60.0 + float(parts[2]) / 3600.0)
    except ValueError:
        return None


def _to_cartesian(ra_deg: float, dec_deg: float, ly: float):
    ra_r  = math.radians(ra_deg)
    dec_r = math.radians(dec_deg)
    x = ly * math.cos(dec_r) * math.cos(ra_r)
    y = ly * math.cos(dec_r) * math.sin(ra_r)
    z = ly * math.sin(dec_r)
    return x, y, z


def _compute_hz_zones(teff: float, lum: float) -> list:
    """Return list of zone dicts with outer AU and region metadata.

    Each dict: key, label, outer (AU), color.
    Zones are ordered inner → outer; the region between consecutive boundaries
    is shown by painting circles from outside-in in the GUI.
    """
    zones = []
    for key, label, color in _HZ_ZONE_DEFS:
        seff = _kopparapu_seff(teff, key)
        if seff <= 0:
            continue
        zones.append({
            "key":   key,
            "label": label,
            "outer": math.sqrt(lum / seff),
            "color": color,
        })
    return zones


# ── Public API ─────────────────────────────────────────────────────────────────

def prepare_star_map(csv_path=None) -> dict:
    """Load starSystems.csv and return star dicts suitable for scatter plotting.

    Each dict: name, desig, sp_type, color, ly, x, y, z.
    Sol is prepended at the origin (0, 0, 0).

    Returns {"stars": list, "count": int} or {"error": str}.
    """
    if csv_path is None:
        csv_path = os.path.normpath(os.path.join(_DATA_DIR, "starSystems.csv"))

    if not os.path.exists(csv_path):
        return {"error": "starSystems.csv not found.\nRun the Star Systems Database Query (option 50) first."}

    stars = [{
        "name": "Sol", "desig": "", "sp_type": "G2V",
        "color": _SPECTRAL_COLORS["G"],
        "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0,
    }]

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    ly = float(row.get("Light Years", ""))
                except (ValueError, TypeError):
                    continue
                ra_deg  = _parse_ra_hms(row.get("RA",  ""))
                dec_deg = _parse_dec_dms(row.get("DEC", ""))
                if ra_deg is None or dec_deg is None:
                    continue
                sp = row.get("Spectral Type", "").strip()
                x, y, z = _to_cartesian(ra_deg, dec_deg, ly)
                stars.append({
                    "name":  row.get("Star Name", "").strip(),
                    "desig": row.get("Star Designations", "").strip(),
                    "sp_type": sp,
                    "color": _SPECTRAL_COLORS.get((sp[0].upper() if sp else ""), "#AAAAAA"),
                    "ly": ly,
                    "x": x, "y": y, "z": z,
                })
    except Exception as e:
        return {"error": f"Error reading starSystems.csv: {e}"}

    return {"stars": stars, "count": len(stars)}


def prepare_system_orbits(planets: list) -> dict:
    """Build Keplerian orbital ellipse data from NASA-archive planet dicts.

    Returns {"orbits": list, "hz_zones": list, "max_au": float, "star_name": str}
    or {"error": str}.
    """
    if not planets:
        return {"error": "No planet data to plot."}

    N = 361
    thetas = [2.0 * math.pi * i / (N - 1) for i in range(N)]

    orbits = []
    max_au = 0.0

    for i, p in enumerate(planets):
        try:
            sma = float(p.get("pl_orbsmax") or 0)
        except (ValueError, TypeError):
            continue
        if sma <= 0:
            continue
        try:
            ecc = float(p.get("pl_orbeccen") or 0)
            if math.isnan(ecc) or ecc < 0:
                ecc = 0.0
        except (ValueError, TypeError):
            ecc = 0.0
        ecc = min(ecc, 0.99)

        b  = sma * math.sqrt(1.0 - ecc * ecc)
        ae = sma * ecc
        orbits.append({
            "name":  str(p.get("pl_name") or f"Planet {i + 1}"),
            "sma":   sma,
            "peri":  sma * (1.0 - ecc),
            "apo":   sma * (1.0 + ecc),
            "ecc":   ecc,
            "x_pts": [sma * math.cos(t) - ae for t in thetas],
            "y_pts": [b   * math.sin(t)      for t in thetas],
            "color": _ORBIT_COLORS[i % len(_ORBIT_COLORS)],
        })
        max_au = max(max_au, sma * (1.0 + ecc))

    if not orbits:
        return {"error": "No valid orbital data found (all planets missing semi-major axis)."}

    # Derive HZ zones from the first planet's stellar parameters
    hz_zones = []
    first = planets[0]
    try:
        teff = float(first.get("st_teff") or 0)
        st_r = float(first.get("st_rad")  or 0)
        if teff > 0 and st_r > 0:
            lum = st_r ** 2 * (teff / 5778.0) ** 4
            hz_zones = _compute_hz_zones(teff, lum)
    except (ValueError, TypeError):
        pass

    star_name = str(first.get("hostname") or first.get("hd_name") or "")
    return {
        "orbits":    orbits,
        "hz_zones":  hz_zones,
        "max_au":    max_au * 1.25,
        "star_name": star_name,
    }


def prepare_star_map_from_result(result: dict) -> dict:
    """Convert a compute_stars_within_distance_of_sol/star result to star-map format.

    Expects result["stars"] to contain dicts with x/y/z coordinates.
    For the Sol variant, adds Sol at the origin.
    For the star variant, the center star is provided via center_* keys.

    Returns {"stars": list, "count": int} or {"error": str}.
    """
    if "error" in result:
        return result

    is_sol_query = "limit_ly" in result and "center" not in result

    stars = []
    if is_sol_query:
        stars.append({
            "name": "Sol", "desig": "", "sp_type": "G2V",
            "color": _SPECTRAL_COLORS["G"],
            "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0,
        })
    else:
        cx = result.get("center_x", 0.0)
        cy = result.get("center_y", 0.0)
        cz = result.get("center_z", 0.0)
        # Shift all coordinates so the center star is at the origin
        for s in result.get("stars", []):
            if s.get("x") is None:
                continue
            sp = s.get("Spectral Type", "").strip()
            stars.append({
                "name":  s.get("Star Name", ""),
                "desig": s.get("Star Designations", ""),
                "sp_type": sp,
                "color": _SPECTRAL_COLORS.get((sp[0].upper() if sp else ""), "#AAAAAA"),
                "ly":   s["Distance"],
                "x":    s["x"] - cx,
                "y":    s["y"] - cy,
                "z":    s["z"] - cz,
            })
        center_name = result.get("center", "Center Star")
        stars.insert(0, {
            "name": center_name, "desig": "", "sp_type": "",
            "color": "#FFD700",
            "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0,
        })
        return {"stars": stars, "count": len(stars)}

    for s in result.get("stars", []):
        if s.get("x") is None:
            continue
        sp = s.get("Spectral Type", "").strip()
        stars.append({
            "name":  s.get("Star Name", ""),
            "desig": s.get("Star Designations", ""),
            "sp_type": sp,
            "color": _SPECTRAL_COLORS.get((sp[0].upper() if sp else ""), "#AAAAAA"),
            "ly":   s["Light Years"],
            "x":    s["x"],
            "y":    s["y"],
            "z":    s["z"],
        })

    return {"stars": stars, "count": len(stars)}


def prepare_system_regions_diagram(d: dict) -> dict:
    """Extract labelled AU distances from a star-regions result dict for diagram rendering.

    Returns {"regions": list, "hz_zones": list, "eeid_au": float, "max_au": float}.
    Each region dict: label, au, color.
    """
    regions = [
        ("System Inner Limit (Gravity)",   d["sysilGrav"],    "#CC3300"),
        ("System Inner Limit (Sunlight)",  d["sysilSunlight"],"#FF6633"),
        ("Circumstellar HZ Inner",         d["hzil"],         "#FFCC00"),
        ("Circumstellar HZ Outer",         d["hzol"],         "#44AA55"),
        ("Snow Line",                      d["snowLine"],     "#4499FF"),
        ("LH₂ Line",                       d["lh2Line"],      "#9933FF"),
        ("System Outer Limit",             d["sysol"],        "#888888"),
    ]
    hz_zones = _compute_hz_zones(d["temp"], d["calculatedLuminosity"])
    eeid_au  = d.get("distAU", 0.0)
    max_au   = d["sysol"] * 1.05
    return {
        "regions":  [{"label": l, "au": au, "color": c} for l, au, c in regions],
        "hz_zones": hz_zones,
        "eeid_au":  eeid_au,
        "max_au":   max_au,
    }


def prepare_alt_hz_diagram(d: dict) -> dict:
    """Extract alternate biochemistry HZ zone data from a star-regions result dict.

    Returns {"zones": list, "max_au": float} or {"error": str}.
    Each zone dict: label, inner_au, outer_au, color.  Ordered hot (close) → cold (far).
    """
    try:
        zones = [
            {"label": "Fluorosilicone-Fluorosilicone",
             "inner_au": d["ffInner"], "outer_au": d["ffOuter"], "color": "#FF3300"},
            {"label": "Fluorocarbon-Sulfur",
             "inner_au": d["fsInner"], "outer_au": d["fsOuter"], "color": "#FF8800"},
            {"label": "Protein-Water",
             "inner_au": d["prwInner"], "outer_au": d["prwOuter"], "color": "#33AA55"},
            {"label": "Protein-Ammonia",
             "inner_au": d["praInner"], "outer_au": d["praOuter"], "color": "#4488CC"},
            {"label": "Polylipid-Methane",
             "inner_au": d["pmInner"], "outer_au": d["pmOuter"], "color": "#8833EE"},
            {"label": "Polylipid-Hydrogen",
             "inner_au": d["phInner"], "outer_au": d["phOuter"], "color": "#223366"},
        ]
    except KeyError as e:
        return {"error": f"Missing field: {e}"}
    max_au = max(z["outer_au"] for z in zones)
    return {"zones": zones, "max_au": max_au}


def prepare_hz_diagram(teff: float, luminosity: float) -> dict:
    """Compute HZ ring data for a star with given temperature and luminosity.

    Returns {"zones": list, "max_au": float} or {"error": str}.
    """
    if teff <= 0 or luminosity <= 0:
        return {"error": "Temperature and luminosity must be positive."}
    zones = _compute_hz_zones(teff, luminosity)
    if not zones:
        return {"error": "Could not compute habitable zone boundaries."}
    return {"zones": zones, "max_au": zones[-1]["outer"] * 1.35}
