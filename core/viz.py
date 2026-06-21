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
    lum = None
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
        "luminosity": lum,   # Phase P V6/V7: host L (☉) for snow-line / solvent overlays
    }


# km per AU — converts moon SMA (km) → AU for the O7 orbital diagrams.
_KM_PER_AU_SS = 1.496e8


def prepare_solar_system_orbits(kind: str = "planets") -> dict:
    """Solar-system orbital-ellipse data for opt 11 (Phase O · O7).

    kind ∈ {"planets", "dwarfs_asteroids", "moons:<planet>"} — planet/dwarf/
    asteroid SMAs are AU; moon SMAs are km (÷1.496e8 → AU). Same orbit-dict shape
    as ``prepare_system_orbits`` ({name, sma, peri, apo, ecc, x_pts, y_pts,
    color}) plus {hz_zones: [], max_au, star_name} (no HZ — these bodies orbit
    the Sun / their planet) or {"error": str}.
    """
    import core.science
    data = core.science.compute_solar_system_tables()

    km_to_au = 1.0
    if kind == "planets":
        rows = [(p.get("Planet"), p.get("Semimajor Axis"), p.get("Eccentricity"))
                for p in data["planets"]]
        star_name = "Sun"
    elif kind == "dwarfs_asteroids":
        rows = [(b.get("Name"), b.get("Semimajor Axis"), b.get("Eccentricity"))
                for b in data["dwarf_planets"] + data["asteroids"]]
        star_name = "Sun"
    elif kind.startswith("moons:"):
        planet = kind.split(":", 1)[1]
        moons = data["moons"].get(planet)
        if not moons:
            return {"error": f"No moon data for '{planet}'."}
        rows = [(m.get("Satellite Name"), m.get("SemiMajor Axis (km)"),
                 m.get("Eccentricity")) for m in moons]
        km_to_au = 1.0 / _KM_PER_AU_SS
        star_name = planet
    else:
        return {"error": f"Unknown kind '{kind}'."}

    N = 361
    thetas = [2.0 * math.pi * i / (N - 1) for i in range(N)]
    orbits = []
    max_au = 0.0
    for i, (name, sma_s, ecc_s) in enumerate(rows):
        try:
            sma = float(sma_s) * km_to_au
        except (ValueError, TypeError):
            continue
        if sma <= 0:
            continue
        try:
            ecc = float(ecc_s)
            if math.isnan(ecc) or ecc < 0:
                ecc = 0.0
        except (ValueError, TypeError):
            ecc = 0.0
        ecc = min(ecc, 0.99)
        b  = sma * math.sqrt(1.0 - ecc * ecc)
        ae = sma * ecc
        orbits.append({
            "name":  str(name or f"Body {i + 1}"),
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
        return {"error": "No valid orbital data found."}
    return {"orbits": orbits, "hz_zones": [], "max_au": max_au * 1.25,
            "star_name": star_name}


def prepare_hyper_limits() -> dict:
    """Honorverse hyper-limit bar-chart data (Phase O · O10a).

    Reads ``core.science.compute_honorverse_hyper_limits()`` (44 spectral classes:
    O/B/A, F0–M9, Red Giant). Returns parallel lists in table order (hot→cool),
    coloured by leading spectral class:
        {classes:[str], lm:[float], au:[float], colors:[str]} or {"error": str}.
    """
    import core.science
    rows = core.science.compute_honorverse_hyper_limits()
    if not rows:
        return {"error": "Honorverse hyper-limit table is empty."}
    return {
        "classes": [r["spectral_class"] for r in rows],
        "lm":      [r["lm"] for r in rows],
        "au":      [r["au"] for r in rows],
        "colors":  [_sp_color(r["spectral_class"]) for r in rows],
    }


# Plausibility colours for the solvent reference bar chart (Phase P V5 / P6).
# Keyed by _SOLVENTS key; mirrors the mockup's _PLAUS_COLOR.
_SOLVENT_PLAUS_COLORS = {
    "water": "#2e8b57", "sulfuric_acid": "#2e8b57",                       # functional & abundant
    "co2": "#b8860b", "methane": "#b8860b", "ethane": "#b8860b",
    "water_ammonia": "#b8860b", "so2": "#b8860b", "ammonia": "#b8860b",   # notable / conditional
}
_SOLVENT_PLAUS_OTHER = "#8899aa"                                          # other


def solvent_plausibility_color(key: str) -> str:
    """Plausibility-category colour for a solvent key (Phase P V5 / P6)."""
    return _SOLVENT_PLAUS_COLORS.get(key, _SOLVENT_PLAUS_OTHER)


def prepare_solvent_ranges() -> dict:
    """Solvent liquid-range bar-chart data (Phase P V5; backs SolventReferencePanel).

    Reads the built-in solvent table (core.equations.get_solvents()), sorted by
    freezing point ascending (coldest first). Each bar spans freeze→boil on a
    Temperature (K) axis, coloured by Bains-2024 plausibility category. Returns
    parallel lists:
        {names, lo, hi, colors, plausibility, pressure_conditional,
         assumed_pressure_atm, citation}.
    """
    import core.equations
    solv = sorted(core.equations.get_solvents(), key=lambda s: s["t_low_k"])
    return {
        "names":   [s["name"] for s in solv],
        "lo":      [s["t_low_k"] for s in solv],
        "hi":      [s["t_high_k"] for s in solv],
        "colors":  [solvent_plausibility_color(s["key"]) for s in solv],
        "plausibility":         [s["plausibility"] for s in solv],
        "pressure_conditional": [s["pressure_conditional"] for s in solv],
        "assumed_pressure_atm": [s["assumed_pressure_atm"] for s in solv],
        "citation":             [s["citation"] for s in solv],
    }


# Frost-line ring colours (Phase P V4), keyed by condensation temperature (K).
_ICE_LINE_COLORS = {170: "#4499FF", 80: "#33AAAA", 70: "#FF8800",
                    22: "#9966CC", 20: "#cc66aa"}


def prepare_ice_line_diagram(result: dict) -> dict:
    """Frost-line ring-map data (Phase P V4) from a compute_ice_lines() result.

    Each line carries its AU, condensation T, a colour (by T), and the disk_line
    flag (drawn dashed-finer on the canvas). Returns
    {lines:[{species, au, t_cond_k, color, disk_line, kind, note}],
     luminosity_solar} or {"error": str}.
    """
    if not result or "error" in result:
        return result if result else {"error": "No ice-line data."}
    lines = [{
        "species": ln["species"], "au": ln["au"], "t_cond_k": ln["t_cond_k"],
        "color": _ICE_LINE_COLORS.get(int(round(ln["t_cond_k"])), "#888888"),
        "disk_line": ln["disk_line"], "kind": ln["kind"], "note": ln["note"],
    } for ln in result["lines"]]
    return {"lines": lines, "luminosity_solar": result["luminosity_solar"]}


# Phase P V7 solvent overlay set for the orbital diagrams: (key, colour, default-on).
# All default OFF → the orbital diagram is byte-identical until the user opts in.
_ORBIT_SOLVENTS = [
    ("water",         "#2e8b57", False),
    ("ammonia",       "#4488cc", False),
    ("methane",       "#8833ee", False),
    ("ethane",        "#00aaaa", False),
    ("co2",           "#cc8844", False),
    ("sulfuric_acid", "#cc4466", False),
]


def prepare_orbit_overlays(luminosity_solar) -> dict:
    """Phase P V6/V7 — snow-line + solvent-zone overlay data for the orbital
    diagrams (opts 3/6/Map), derived from a host luminosity (☉).

    Returns {snow_au, solvent_options:[{key, name, inner_au, outer_au, color,
    default}]} or {"error": str} for a missing/non-positive luminosity.
    """
    import core.equations
    if luminosity_solar is None or luminosity_solar <= 0:
        return {"error": "Host luminosity unavailable — overlays need st_rad + st_teff."}
    ice = core.equations.compute_ice_lines(luminosity_solar)
    snow_au = next((l["au"] for l in ice["lines"] if l["kind"] == "snow_line"), None)
    options = []
    for key, color, default in _ORBIT_SOLVENTS:
        z = core.equations.compute_solvent_zone(luminosity_solar, key)
        if "error" in z:
            continue
        options.append({
            "key": key, "name": z["name"], "inner_au": z["inner_au"],
            "outer_au": z["outer_au"], "color": color, "default": default,
        })
    return {"snow_au": snow_au, "solvent_options": options}


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
        ("Water snow line",                d["snowLine"],     "#4499FF"),
        ("N₂/CO (1-atm)",                  d["lh2Line"],      "#9933FF"),
        ("System Outer Limit",             d["sysol"],        "#888888"),
    ]
    hz_zones = _compute_hz_zones(d["temp"], d["calculatedLuminosity"])
    eeid_au  = d.get("distAU", 0.0)
    max_au   = d["sysol"] * 1.05
    result = {
        "regions":  [{"label": l, "au": au, "color": c} for l, au, c in regions],
        "hz_zones": hz_zones,
        "eeid_au":  eeid_au,
        "max_au":   max_au,
    }
    # Phase O O10b: when the star's spectral type resolves, attach the Honorverse
    # hyper limit as a SEPARATE overlay key (not a physical region — the canvas
    # draws it as a dashed-red ring only when its checkbox is ticked). Absent for
    # opt-10 (manual) / opt-13 (Sol) dicts, which carry no spectral_type.
    sp = d.get("spectral_type")
    if sp:
        import core.science
        hl = core.science.compute_hyper_limit_for_spectral_type(sp)
        if hl:
            result["hyper_limit"] = {
                "label": "Honorverse Hyper Limit", "au": hl["au"],
                "color": "#cc2222", "matched_class": hl["matched_class"],
            }
    return result


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
        # Phase P P2 (V1): additional alternative-solvent bands → 10-band diagram.
        # Present only on dicts built after P2 (regions.compute_star_system_regions);
        # guarded so an older/partial dict still renders the original six.
        if "co2Inner" in d:
            zones += [
                {"label": "Carbon Dioxide (≥5.2 atm)",
                 "inner_au": d["co2Inner"], "outer_au": d["co2Outer"], "color": "#00AAAA"},
                {"label": "Liquid Sulfur",
                 "inner_au": d["sInner"], "outer_au": d["sOuter"], "color": "#AA2200"},
                {"label": "Water-Ammonia Eutectic",
                 "inner_au": d["waInner"], "outer_au": d["waOuter"], "color": "#66CCEE"},
                {"label": "Sulfuric Acid",
                 "inner_au": d["saInner"], "outer_au": d["saOuter"], "color": "#CC8844"},
            ]
    except KeyError as e:
        return {"error": f"Missing field: {e}"}
    max_au = max(z["outer_au"] for z in zones)
    return {"zones": zones, "max_au": max_au}


_PLANET_SMAS = {
    "Mercury": 0.387, "Venus": 0.723, "Earth": 1.000, "Mars":    1.524,
    "Jupiter": 5.203, "Saturn": 9.537, "Uranus": 19.191, "Neptune": 30.069,
}
_PLANET_COLORS_VIZ = {
    "Mercury": "#b5b5b5", "Venus": "#e8cda0", "Earth": "#4fc3f7",
    "Mars":    "#ef5350",  "Jupiter": "#c9956b", "Saturn": "#d4b896",
    "Uranus":  "#7de8e8",  "Neptune": "#5b8df5",
}


def prepare_solar_travel_diagram(result: dict) -> dict:
    """Convert a solar-travel result dict to visualization data.

    Accepts the return value of compute_travel_time_solar_objects or
    compute_travel_time_custom_thrust.

    Returns:
        {origin_name, dest_name, origin_xyz, dest_xyz,
         planets, planet_orbits, max_au}
    or {"error": str}
    """
    if "origin_xyz" not in result or "dest_xyz" not in result:
        return {"error": "Position data not available."}

    origin_xyz = result["origin_xyz"]
    dest_xyz   = result["dest_xyz"]
    planets    = result.get("planet_positions", [])

    # max XY radius of all bodies to determine view scale
    all_pts = [origin_xyz, dest_xyz] + [(p["x"], p["y"], p["z"]) for p in planets]
    radii = [math.sqrt(x**2 + y**2) for x, y, _ in all_pts if abs(x) + abs(y) > 1e-9]
    max_r = max(radii) if radii else 1.5
    max_au = max(max_r * 1.15, 1.5)

    planet_orbits = [
        {"name": name, "sma_au": sma, "color": _PLANET_COLORS_VIZ.get(name, "#888888")}
        for name, sma in _PLANET_SMAS.items()
        if sma <= max_au * 1.1
    ]

    return {
        "origin_name":   result["origin"],
        "dest_name":     result["destination"],
        "origin_id":     result.get("origin_id", ""),
        "dest_id":       result.get("dest_id", ""),
        "origin_xyz":    origin_xyz,
        "dest_xyz":      dest_xyz,
        "planets":       planets,
        "planet_orbits": planet_orbits,
        "max_au":        max_au,
    }


def prepare_abundance_profile(hypatia_result: dict) -> dict:
    """Extract abundance list from a compute_hypatia_data() result for bar-chart rendering.

    Returns {"elements", "names", "means", "stds", "categories", "colors", "star_name"}
    or {"error": str}. Lists run in parallel; elements are in the master display order
    (already sorted by the parser). `elements` uses human-readable symbols ("Ba II").
    """
    from core.hypatia_elements import display_symbol, category_color

    if not hypatia_result or "error" in hypatia_result:
        msg = hypatia_result.get("error", "No Hypatia data available") if hypatia_result else "No Hypatia data available"
        return {"error": msg}

    abundances = hypatia_result.get("abundances", [])
    if not abundances:
        return {"error": "No abundance data available for this star"}

    elements, names, means, stds, categories, colors = [], [], [], [], [], []
    for a in abundances:
        m = a.get("mean")
        if m is None:
            continue
        elements.append(display_symbol(a["element"]))
        names.append(a.get("name", ""))
        means.append(float(m))
        stds.append(a.get("std"))
        cat = a.get("category", "")
        categories.append(cat)
        colors.append(category_color(cat))

    if not elements:
        return {"error": "No measurable abundances found"}

    return {
        "elements":   elements,
        "names":      names,
        "means":      means,
        "stds":       stds,
        "categories": categories,
        "colors":     colors,
        "star_name":  hypatia_result.get("star_name", ""),
    }


# Solar motion w.r.t. the Local Standard of Rest (Schönrich, Binney & Dehnen 2010),
# km/s, in Hypatia's (U toward the Galactic centre, V along Galactic rotation, W toward
# the north Galactic pole) frame. Hypatia's U/V/W are *heliocentric*, so adding this
# puts a star's velocity in the LSR frame — where the Toomre population thresholds
# (thin <50 / thick ≈70–180 / halo >180 km/s total) are defined and the constant-total-
# velocity arcs centre at the origin. (Phase O Open Decision #2, resolved 2026-06-18:
# Hypatia returns heliocentric U/V/W → LSR-correct. Set this to (0, 0, 0) to plot the
# raw heliocentric velocities instead.)
_SOLAR_MOTION_UVW = (11.1, 12.24, 7.25)


def prepare_toomre(hypatia_result: dict) -> dict:
    """Toomre / galactic-kinematics data from a compute_hypatia_data() result (Phase O · O11).

    Hypatia returns heliocentric U/V/W velocities; they are LSR-corrected here by adding
    the solar motion (``_SOLAR_MOTION_UVW``) so the constant-total-velocity arcs centre at
    the LSR origin and the thin/thick/halo speed thresholds read directly off the plot.

    Returns ``{v, uw, total, disk, star_name}`` (``uw = √(U²+W²)``, ``total = √(U²+V²+W²)``,
    all LSR-frame, km/s) or ``{"error": str}`` when any of U/V/W is null — a Toomre point
    needs all three components.
    """
    if not hypatia_result or "error" in hypatia_result:
        msg = (hypatia_result.get("error", "No Hypatia data available")
               if hypatia_result else "No Hypatia data available")
        return {"error": msg}

    props = hypatia_result.get("properties") or {}
    u, v, w = props.get("u_vel"), props.get("v_vel"), props.get("w_vel")
    if u is None or v is None or w is None:
        return {"error": "No U/V/W kinematics available for this star"}

    su, sv, sw = _SOLAR_MOTION_UVW
    u_l = float(u) + su
    v_l = float(v) + sv
    w_l = float(w) + sw
    return {
        "v":         v_l,
        "uw":        math.hypot(u_l, w_l),
        "total":     math.sqrt(u_l * u_l + v_l * v_l + w_l * w_l),
        "disk":      props.get("disk"),
        "star_name": hypatia_result.get("star_name", ""),
    }


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


# ── Exoplanet system map (per-planet positions on a given date) ──────────────

def _date_iso_to_jd(date_iso: str):
    """Convert 'YYYY-MM-DD' to Julian Date at noon UT (no external dep)."""
    if not date_iso:
        return None
    try:
        y, m, d = (int(x) for x in date_iso.split("-"))
    except (ValueError, AttributeError):
        return None
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return float(jdn)  # noon UT


def _solve_kepler(M: float, e: float, tol: float = 1e-9, max_iter: int = 60) -> float:
    """Solve M = E - e sin E for eccentric anomaly E (Newton-Raphson)."""
    M = M - 2.0 * math.pi * math.floor((M + math.pi) / (2.0 * math.pi))
    E = M if e < 0.8 else math.pi
    for _ in range(max_iter):
        f = E - e * math.sin(E) - M
        fp = 1.0 - e * math.cos(E)
        dE = f / fp
        E -= dE
        if abs(dE) < tol:
            break
    return E


def _true_anomaly_from_E(E: float, e: float) -> float:
    return 2.0 * math.atan2(math.sqrt(1.0 + e) * math.sin(E / 2.0),
                            math.sqrt(1.0 - e) * math.cos(E / 2.0))


def _E_from_true_anomaly(nu: float, e: float) -> float:
    return 2.0 * math.atan2(math.sqrt(1.0 - e) * math.sin(nu / 2.0),
                            math.sqrt(1.0 + e) * math.cos(nu / 2.0))


def _ffloat(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def prepare_exoplanet_system_diagram(planets: list, date_iso: str = None) -> dict:
    """Build top-down system map data with each planet at its date-resolved position.

    For each planet:
      • Orbit ellipse polyline is computed from pl_orbsmax + pl_orbeccen and
        rotated by pl_orblper (argument of periastron, deg).  Orbits are
        treated as coplanar (no Ω data is available for exoplanets).
      • Current position is solved from Kepler's equation using either
        pl_orbtper (epoch of periastron, JD) or — if missing — derived from
        pl_tranmid (transit mid-point, JD).  When neither is available the
        planet is placed at periastron and `epoch_known` is False.

    Returns:
        {"orbits": [...], "planets": [...], "star_name": str,
         "max_au": float, "epoch_iso": str|None}
    or {"error": str}.

    Each orbit dict: {name, color, x_pts, y_pts, sma, ecc, peri, apo}.
    Each planet dict: {name, color, x, y, z, sma, ecc, period, epoch_known, info}.
    `info` is the raw pscomppars row (for downstream display).
    """
    if not planets:
        return {"error": "No planet data."}

    jd = _date_iso_to_jd(date_iso) if date_iso else None

    N = 361
    thetas = [2.0 * math.pi * i / (N - 1) for i in range(N)]

    orbits = []
    plist  = []
    max_au = 0.0

    for i, p in enumerate(planets):
        sma = _ffloat(p.get("pl_orbsmax"))
        if sma is None or sma <= 0:
            continue
        ecc = _ffloat(p.get("pl_orbeccen")) or 0.0
        if ecc < 0:
            ecc = 0.0
        ecc = min(ecc, 0.99)

        # Argument of periastron (degrees → radians); default 0 if unknown.
        omega_deg = _ffloat(p.get("pl_orblper"))
        omega = math.radians(omega_deg) if omega_deg is not None else 0.0
        cos_w, sin_w = math.cos(omega), math.sin(omega)

        period = _ffloat(p.get("pl_orbper"))
        tper   = _ffloat(p.get("pl_orbtper"))
        if tper is None:
            tran = _ffloat(p.get("pl_tranmid"))
            if tran is not None and period is not None and period > 0:
                # At mid-transit, ν + ω ≈ π/2  →  ν_tran = π/2 - ω
                nu_tran = math.pi / 2.0 - omega
                E_tran  = _E_from_true_anomaly(nu_tran, ecc)
                M_tran  = E_tran - ecc * math.sin(E_tran)
                dt_days = M_tran * period / (2.0 * math.pi)
                tper    = tran - dt_days

        # Orbit ellipse polyline (orbit-frame: focus at origin, periastron +x),
        # rotated by ω about Z.
        b  = sma * math.sqrt(1.0 - ecc * ecc)
        ae = sma * ecc
        x_pts, y_pts = [], []
        for t in thetas:
            xo = sma * math.cos(t) - ae
            yo = b * math.sin(t)
            x_pts.append(xo * cos_w - yo * sin_w)
            y_pts.append(xo * sin_w + yo * cos_w)

        # Current planet position
        epoch_known = False
        if jd is not None and tper is not None and period is not None and period > 0:
            M  = 2.0 * math.pi * (jd - tper) / period
            E  = _solve_kepler(M, ecc)
            nu = _true_anomaly_from_E(E, ecc)
            r  = sma * (1.0 - ecc * math.cos(E))
            epoch_known = True
        else:
            nu = 0.0                          # periastron
            r  = sma * (1.0 - ecc)
        xo = r * math.cos(nu)
        yo = r * math.sin(nu)
        px = xo * cos_w - yo * sin_w
        py = xo * sin_w + yo * cos_w

        color = _ORBIT_COLORS[i % len(_ORBIT_COLORS)]
        name  = str(p.get("pl_name") or f"Planet {i + 1}")

        orbits.append({
            "name":  name,
            "color": color,
            "x_pts": x_pts,
            "y_pts": y_pts,
            "sma":   sma,
            "ecc":   ecc,
            "peri":  sma * (1.0 - ecc),
            "apo":   sma * (1.0 + ecc),
        })
        plist.append({
            "name":         name,
            "color":        color,
            "x":            px,
            "y":            py,
            "z":            0.0,
            "sma":          sma,
            "ecc":          ecc,
            "period":       period,
            "omega_deg":    omega_deg,
            "epoch_known":  epoch_known,
            "info":         p,
        })
        max_au = max(max_au, sma * (1.0 + ecc))

    if not orbits:
        return {"error": "No valid orbital data found (all planets missing semi-major axis)."}

    first = planets[0]
    star_name = str(first.get("hostname") or first.get("hd_name") or "")

    return {
        "orbits":    orbits,
        "planets":   plist,
        "star_name": star_name,
        "max_au":    max_au * 1.20,
        "epoch_iso": date_iso,
    }


# ── Phase I — Route map overlay ──────────────────────────────────────────────

def _route_edge(a, b, label, style):
    return {
        "x1": a["x"], "y1": a["y"], "z1": a["z"],
        "x2": b["x"], "y2": b["y"], "z2": b["z"],
        "label": label, "style": style,
    }


def prepare_route_map(result: dict) -> dict:
    """Normalize a route-planning result into star-chart + route-edge geometry.

    Handles every Route Planning result:
      * I1/I2 (legs/chain) and A (optimal tour, +closed wrap) → dashed ordered.
      * B (jump route) → dashed consecutive jumps.
      * D (farthest-first) → dashed exploration-tree edges (non-consecutive).
      * C (jump network) → nodes only (per-tier colours carried on `stars`); no edges.
      * I3 (MST) → solid edges.

    Returns:
        {"stars": [...], "edges": [{x1,y1,z1,x2,y2,z2,label,style}], "edge_style"}
        or {"error": str} (passthrough).
    """
    if not isinstance(result, dict) or "error" in result:
        return result

    stars = result.get("stars", [])
    edges = []

    if "tiers" in result:
        # C — reachability: tier-coloured nodes, no edges (scales to large pools).
        return {"stars": stars, "edges": [], "edge_style": "none"}

    if "tree_edges" in result:
        # D — farthest-first: dashed edges from each node to the visited node it
        # reached from (indices into `stars`), labelled with the step number.
        style = "dashed"
        for i, te in enumerate(result["tree_edges"]):
            fi, ti = te["from_index"], te["to_index"]
            if 0 <= fi < len(stars) and 0 <= ti < len(stars):
                label = _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
                edges.append(_route_edge(stars[fi], stars[ti], label, style))
        return {"stars": stars, "edges": edges, "edge_style": style}

    if "route" in result:
        # B — jump route: dashed edges between consecutive route nodes. `stars`
        # is the route in order; an unreachable result has an empty route (no
        # edges — the two endpoints are drawn disconnected for context).
        style = "dashed"
        route = result.get("route", [])
        for i in range(len(route)):
            if i + 1 < len(stars):
                label = f"{route[i]['jump_ly']:.1f} ly"
                edges.append(_route_edge(stars[i], stars[i + 1], label, style))
        return {"stars": stars, "edges": edges, "edge_style": style}

    if "closed" in result:
        # A — optimal tour: dashed consecutive legs (+ wrap when closed),
        # labelled with the visit order.
        style = "dashed"
        for i in range(len(stars) - 1):
            label = _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
            edges.append(_route_edge(stars[i], stars[i + 1], label, style))
        if result.get("closed") and len(stars) > 1:
            i = len(stars) - 1
            label = _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
            edges.append(_route_edge(stars[-1], stars[0], label, style))
        return {"stars": stars, "edges": edges, "edge_style": style}

    if "legs" in result or "chain" in result:
        # I1/I2 — ordered route: dashed edges between consecutive stars.
        style = "dashed"
        for i in range(len(stars) - 1):
            a, b = stars[i], stars[i + 1]
            if "legs" in result and i < len(result["legs"]):
                label = f"{result['legs'][i]['distance_ly']:.1f} ly"
            else:
                label = _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
            edges.append(_route_edge(a, b, label, style))
        return {"stars": stars, "edges": edges, "edge_style": style}

    # I3 — MST: solid edges mapped from {from,to} names to coordinates.
    style = "solid"
    by_name = {s["name"]: s for s in stars}
    for e in result.get("edges", []):
        a, b = by_name.get(e["from"]), by_name.get(e["to"])
        if a is None or b is None:
            continue
        edges.append(_route_edge(a, b, f"{e['distance_ly']:.1f} ly", style))
    return {"stars": stars, "edges": edges, "edge_style": style}


_CIRCLED = ["①", "②", "③", "④", "⑤", "⑥",
            "⑦", "⑧", "⑨", "⑩", "⑪", "⑫"]


# ── Stellar evolution diagram (Phase L3) ─────────────────────────────────────

def prepare_evolution_diagram(result: dict) -> dict:
    """Normalize a compute_stellar_evolution() result into stacked-bar data.

    Returns {stages, current_age_gyr, x_max_gyr, mass_solar, total_gyr,
    ms_end_gyr, current_stage, low_mass, high_mass} or {"error": str}.
    `x_max_gyr` = max(total, current_age) × 1.1 for axis scaling.
    """
    if not result or "error" in result:
        return {"error": result.get("error", "No evolution data") if result else "No evolution data"}
    stages = result.get("stages", [])
    total  = result.get("total_gyr", 0.0) or 0.0
    age    = result.get("current_age_gyr")
    x_max  = max(total, age or 0.0) * 1.1 or 1.0
    return {
        "stages":          stages,
        "current_age_gyr": age,
        "x_max_gyr":       x_max,
        "mass_solar":      result.get("mass_solar"),
        "total_gyr":       total,
        "ms_end_gyr":      result.get("ms_end_gyr"),
        "current_stage":   result.get("current_stage"),
        "low_mass":        result.get("low_mass", False),
        "high_mass":       result.get("high_mass", False),
    }


# ── Multi-star abundance comparison (Phase L1) ───────────────────────────────

# Distinct per-star series colours for the grouped abundance chart.
_COMPARE_COLORS = ["#d8a13a", "#4a90d9", "#7a5bd0", "#2e8b57"]


def prepare_abundance_comparison(compare_result: dict) -> dict:
    """Build grouped [X/H] bar-chart data from a compare_stars() result.

    Returns {star_names, colors, elements, matrix} or {"error": str}.
    `elements` is the union of measured species across all stars, in the master
    display order (core.hypatia_elements); `matrix[i][j]` is star j's [X/H] mean
    for element i (None when that star lacks the species). Only stars whose
    Hypatia result carries ≥1 non-None abundance are included.
    """
    from core.hypatia_elements import display_symbol, SPECIES_ORDER

    if not compare_result or "error" in compare_result:
        return {"error": "No comparison data available"}

    star_names, per_star, defining = [], [], set()
    for s in compare_result.get("stars", []):
        hyp = s.get("hypatia")
        if not hyp or "error" in hyp:
            continue
        vals = {}
        for a in hyp.get("abundances", []):
            m = a.get("mean")
            if m is None:
                continue
            el = a["element"]
            vals[el] = float(m)
            # Only catalogued measurements (n > 0, or unknown n) define which
            # elements to chart; an all-zero reference baseline like the Sun
            # (n = 0) fills existing rows but must not expand the union to all
            # 104 species.
            n = a.get("n")
            if n is None or n > 0:
                defining.add(el)
        if vals:
            star_names.append(s.get("name", "?"))
            per_star.append(vals)

    if len(star_names) < 1:
        return {"error": "No stars with elemental abundance data to compare"}

    # Element union: catalogued measurements only; fall back to all present keys
    # when nothing is catalogued (e.g. the Sun compared against itself).
    keys = defining if defining else set().union(*[set(v) for v in per_star])
    ordered = sorted(keys, key=lambda k: SPECIES_ORDER.get(k.lower(), 999))

    elements = [display_symbol(k) for k in ordered]
    matrix   = [[vals.get(k) for vals in per_star] for k in ordered]
    colors   = [_COMPARE_COLORS[i % len(_COMPARE_COLORS)] for i in range(len(star_names))]

    return {"star_names": star_names, "colors": colors,
            "elements": elements, "matrix": matrix}


# ── L2 ESI bar chart ──────────────────────────────────────────────────────────

def prepare_esi_bar_chart(result: dict, top_n: int = 20) -> dict:
    """Top-N planets-by-ESI bar-chart data from a search_hwc result (Phase L2).

    Input is `databases.search_hwc(...)` output (already sorted P_ESI desc).
    Returns {"names", "esi", "habitable", "shown", "total"} (parallel lists,
    highest ESI first) or {"error": str}. Only planets with a numeric P_ESI are
    included; `habitable` is the P_HABITABLE flag as bool.
    """
    if not isinstance(result, dict) or "error" in result:
        return {"error": (result or {}).get("error", "No ranking data")}
    rows = []
    for r in (result.get("stars") or []):
        esi = _ffloat(r.get("P_ESI"))
        if esi is None:
            continue
        rows.append((r.get("P_NAME") or "?", esi,
                     str(r.get("P_HABITABLE")).strip() == "1"))
    if not rows:
        return {"error": "No planets with an ESI value to plot."}
    total = len(rows)
    rows = rows[:max(1, int(top_n))]
    return {
        "names":     [n for n, _e, _h in rows],
        "esi":       [e for _n, e, _h in rows],
        "habitable": [h for _n, _e, h in rows],
        "shown":     len(rows),
        "total":     total,
    }


# ── Phase O O-8: HWC habitability visuals (opt 6) ─────────────────────────────

def prepare_hwc_temps(planet_rows: list) -> dict:
    """Per-planet temperature-range data from HWC planet rows (Phase O · O12).

    Each planet contributes an equilibrium bar (P_TEMP_EQUIL_MIN→MAX, centre
    P_TEMP_EQUIL) and/or a surface bar (P_TEMP_SURF_MIN→MAX, centre P_TEMP_SURF).
    A planet qualifies when it carries at least one complete min/max pair; planets
    with neither pair are counted in `skipped`. Returns
    {"planets":[{name, eq_min, eq, eq_max, surf_min, surf, surf_max}], "skipped"}
    or {"error": str} when none qualify. All HWC columns are TEXT, so blanks parse
    to None (never 0).
    """
    if not planet_rows:
        return {"error": "No planets in this system."}

    planets, skipped = [], 0
    for p in planet_rows:
        eq_min, eq_max = _num(p.get("P_TEMP_EQUIL_MIN")), _num(p.get("P_TEMP_EQUIL_MAX"))
        s_min,  s_max  = _num(p.get("P_TEMP_SURF_MIN")),  _num(p.get("P_TEMP_SURF_MAX"))
        has_eq   = eq_min is not None and eq_max is not None
        has_surf = s_min is not None and s_max is not None
        if not (has_eq or has_surf):
            skipped += 1
            continue
        planets.append({
            "name":     p.get("P_NAME") or "?",
            "eq_min":   eq_min if has_eq else None,
            "eq":       _num(p.get("P_TEMP_EQUIL")),
            "eq_max":   eq_max if has_eq else None,
            "surf_min": s_min if has_surf else None,
            "surf":     _num(p.get("P_TEMP_SURF")),
            "surf_max": s_max if has_surf else None,
        })

    if not planets:
        return {"error": "No planets carry an equilibrium or surface temperature range."}
    return {"planets": planets, "skipped": skipped}


def prepare_hwc_esi(star_row: dict, planet_rows: list) -> dict:
    """ESI-vs-orbit data from an HWC star + planet rows (Phase O · O12).

    Per planet: semi-major axis (P_SEMI_MAJOR_AXIS, AU) vs ESI (P_ESI); coloured by
    P_HABITABLE. The host's optimistic (S_HZ_OPT_MIN/MAX) and conservative
    (S_HZ_CON_MIN/MAX) habitable zones are returned as shaded bands. `log_x` is True
    when the plotted SMA span exceeds 10×. Planets missing a numeric SMA or ESI are
    counted in `skipped`. Returns {"planets":[{name, a_au, esi, habitable}], "hz_opt",
    "hz_con", "log_x", "skipped"} or {"error": str} when none qualify.
    """
    if not planet_rows:
        return {"error": "No planets in this system."}

    planets, skipped = [], 0
    for p in planet_rows:
        a = _num(p.get("P_SEMI_MAJOR_AXIS"))
        esi = _num(p.get("P_ESI"))
        if a is None or a <= 0 or esi is None:
            skipped += 1
            continue
        planets.append({
            "name":      p.get("P_NAME") or "?",
            "a_au":      a,
            "esi":       esi,
            "habitable": str(p.get("P_HABITABLE")).strip() == "1",
        })
    if not planets:
        return {"error": "No planets carry both a semi-major axis and an ESI."}

    star_row = star_row or {}

    def _band(lo_key, hi_key):
        lo, hi = _num(star_row.get(lo_key)), _num(star_row.get(hi_key))
        if lo is not None and hi is not None and hi > 0:
            return [lo, hi]
        return None

    a_vals = [p["a_au"] for p in planets]
    log_x = (max(a_vals) / min(a_vals)) > 10.0
    return {
        "planets": planets,
        "hz_opt":  _band("S_HZ_OPT_MIN", "S_HZ_OPT_MAX"),
        "hz_con":  _band("S_HZ_CON_MIN", "S_HZ_CON_MAX"),
        "log_x":   log_x,
        "skipped": skipped,
    }


# ── L4 Hypatia abundance scatter ──────────────────────────────────────────────

# Plottable axis key -> axis label. Shared with the panel's X/Y dropdowns so the
# two never drift; each key is also a column on a search_hypatia_cache result row.
HYPATIA_SCATTER_AXES = [
    ("fe_h",        "[Fe/H]"),
    ("teff",        "Teff (K)"),
    ("logg",        "log g"),
    ("light_years", "Distance (ly)"),
    ("vmag",        "V mag"),
    ("bv",          "B–V"),
    ("mg_h",        "[Mg/H]"),
    ("si_h",        "[Si/H]"),
    ("o_h",         "[O/H]"),
]
_HYPATIA_AXIS_LABELS = dict(HYPATIA_SCATTER_AXES)


def prepare_hypatia_scatter(result: dict, x_key: str, y_key: str) -> dict:
    """Scatter-plot data for the L4 abundance-search results (Phase L4).

    Input is `databases.search_hypatia_cache(...)` output; x_key/y_key are keys
    from HYPATIA_SCATTER_AXES. Returns {"xs", "ys", "labels", "x_label",
    "y_label", "count"} (only rows where BOTH axes are numeric) or {"error": str}.
    """
    if not isinstance(result, dict) or "error" in result:
        return {"error": (result or {}).get("error", "No search data")}
    if x_key not in _HYPATIA_AXIS_LABELS or y_key not in _HYPATIA_AXIS_LABELS:
        return {"error": "Unknown plot axis."}
    xs, ys, labels = [], [], []
    for r in (result.get("stars") or []):
        x = _ffloat(r.get(x_key))
        y = _ffloat(r.get(y_key))
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
        labels.append(r.get("star_name") or "?")
    if not xs:
        return {"error": "No result rows have both selected quantities measured."}
    return {
        "xs": xs, "ys": ys, "labels": labels,
        "x_label": _HYPATIA_AXIS_LABELS[x_key],
        "y_label": _HYPATIA_AXIS_LABELS[y_key],
        "count": len(xs),
    }


# ── Phase O O-2: Star-Map Data Products ───────────────────────────────────────

def _num(v):
    """Parse a possibly comma-formatted numeric string/value to float, else None."""
    if v is None:
        return None
    try:
        return _ffloat(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _sp_color(sp_type: str) -> str:
    letter = (sp_type or "").strip()[:1].upper()
    return _SPECTRAL_COLORS.get(letter, "#AAAAAA")


def prepare_sky_from_star(result: dict, mag_limit: float = 6.5) -> dict:
    """Night-sky (celestial-sphere) view from the queried centre star (Phase O · O1).

    Input is a `compute_stars_within_distance_of_star` result: each star carries
    absolute heliocentric x/y/z (ly) + the F1 `app_magnitude`/`parsecs` keys, and the
    centre is given by `center_x/y/z`. For each star the vector FROM the vantage
    (centre) is `(x-cx, y-cy, z-cz)`; Sol is added at `-(cx,cy,cz)` with M_V 4.83.

    Apparent magnitude from the vantage: `M = V + 5 − 5·log₁₀(parsecs)` (absolute mag
    from the Sol-centric values), then `m' = M − 5 + 5·log₁₀(d_ly/3.26156)`. Stars with
    no V magnitude are skipped and counted in `skipped_no_mag` (never fabricated).

    Returns {"vantage_name", "mag_limit", "skipped_no_mag",
             "stars": [{name, ra_deg, dec_deg, mag, sp_class, color}]} or {"error": str}.
    """
    if not isinstance(result, dict) or "error" in result:
        return {"error": (result or {}).get("error", "No star-list data")}

    cx = result.get("center_x", 0.0) or 0.0
    cy = result.get("center_y", 0.0) or 0.0
    cz = result.get("center_z", 0.0) or 0.0
    vantage = result.get("center", "Sol")   # opt-18 Sol-centric result has no "center"

    sky, skipped = [], 0
    for s in result.get("stars", []):
        x, y, z = s.get("x"), s.get("y"), s.get("z")
        if x is None or y is None or z is None:
            continue
        vx, vy, vz = x - cx, y - cy, z - cz
        d = math.sqrt(vx * vx + vy * vy + vz * vz)
        if d < 1e-9:
            continue
        vmag = _num(s.get("app_magnitude"))
        pc = _num(s.get("parsecs"))
        if vmag is None or pc is None or pc <= 0:
            skipped += 1
            continue
        abs_m = vmag + 5.0 - 5.0 * math.log10(pc)
        m_prime = abs_m - 5.0 + 5.0 * math.log10(d / 3.26156)
        if m_prime > mag_limit:
            continue
        sp = (s.get("Spectral Type") or "").strip()
        sky.append({
            "name": s.get("Star Name", ""),
            "ra_deg": math.degrees(math.atan2(vy, vx)) % 360.0,
            "dec_deg": math.degrees(math.asin(max(-1.0, min(1.0, vz / d)))),
            "mag": m_prime,
            "sp_class": sp[:1].upper(),
            "color": _sp_color(sp),
        })

    # Sol as seen from the vantage (vector back toward the origin).
    d_sol = math.sqrt(cx * cx + cy * cy + cz * cz)
    if d_sol > 1e-9:
        m_sol = 4.83 - 5.0 + 5.0 * math.log10(d_sol / 3.26156)
        if m_sol <= mag_limit:
            sky.append({
                "name": "Sol",
                "ra_deg": math.degrees(math.atan2(-cy, -cx)) % 360.0,
                "dec_deg": math.degrees(math.asin(max(-1.0, min(1.0, -cz / d_sol)))),
                "mag": m_sol, "sp_class": "G", "color": _SPECTRAL_COLORS["G"],
            })

    return {
        "vantage_name": vantage,
        "mag_limit": mag_limit,
        "skipped_no_mag": skipped,
        "stars": sky,
    }


def prepare_hr_main_sequence() -> dict:
    """Main-sequence reference points for an HR diagram (Phase O · O2a).

    Reads the local `main_sequence_stars` table. Returns
    {"points": [{label, teff, abs_mag, bv, lum, color}]} (sorted hot→cool) or
    {"error": str} when the table is empty / unusable.
    """
    from core.db import get_conn
    try:
        rows = get_conn().execute(
            "SELECT spectral_class, b_v, teff_k, abs_mag_vis, lum FROM main_sequence_stars"
        ).fetchall()
    except Exception as e:
        return {"error": f"Error reading main_sequence_stars table: {e}"}
    if not rows:
        return {"error": "main_sequence_stars table is empty — run option 54 to import it."}

    points = []
    for r in rows:
        teff = _num(r["teff_k"])
        abs_mag = _num(r["abs_mag_vis"])
        if teff is None or abs_mag is None or teff <= 0:
            continue
        sc = (r["spectral_class"] or "").strip()
        points.append({
            "label": sc, "teff": teff, "abs_mag": abs_mag,
            "bv": _num(r["b_v"]), "lum": _num(r["lum"]),
            "color": _sp_color(sc),
        })
    if not points:
        return {"error": "No usable main-sequence rows (need Teff + abs visual mag)."}
    points.sort(key=lambda p: -p["teff"])   # hot (left) → cool (right)
    return {"points": points}


def prepare_hr_from_stars(result: dict) -> dict:
    """Overlay points for an HR diagram from a stars-within result (Phase O · O2b).

    Per result star: `M_V = app_magnitude + 5 − 5·log₁₀(parsecs)` (uses the F1 keys);
    Teff from the canonical `core.regions._lookup_spectral_type` ceiling rule. Stars
    missing a V magnitude/parsecs or without a parseable OBAFGKM Teff are skipped and
    counted. Returns {"points": [{name, teff, abs_mag, color, sp_type}], "skipped": int}
    or {"error": str}.
    """
    if not isinstance(result, dict) or "error" in result:
        return {"error": (result or {}).get("error", "No star-list data")}
    from core.regions import _lookup_spectral_type

    pts, skipped = [], 0
    for s in result.get("stars", []):
        vmag = _num(s.get("app_magnitude"))
        pc = _num(s.get("parsecs"))
        sp = (s.get("Spectral Type") or "").strip()
        if vmag is None or pc is None or pc <= 0:
            skipped += 1
            continue
        row, _key = _lookup_spectral_type(sp)
        teff = _num(row.get("Teeff(K)")) if row else None
        if teff is None or teff <= 0:
            skipped += 1
            continue
        pts.append({
            "name": s.get("Star Name", ""),
            "teff": teff,
            "abs_mag": vmag + 5.0 - 5.0 * math.log10(pc),
            "color": _sp_color(sp),
            "sp_type": sp,
        })

    # Reference anchor (drawn as a gold ★ by make_hr_canvas): Sol for the opt-18
    # Sol-centric result, or the queried centre star for opt 19 (best-effort DB
    # lookup — skipped if the centre isn't in the catalog).
    if "center" in result:
        ref = _hr_center_point(result.get("center", ""))
        if ref:
            pts.append(ref)
    else:
        pts.append({"name": "Sun", "teff": 5778.0, "abs_mag": 4.83,
                    "color": "#FFD700", "sp_type": "G2V", "highlight": True})
    return {"points": pts, "skipped": skipped}


def _hr_center_point(name: str):
    """Best-effort HR point for an opt-19 centre star, looked up in `star_systems`.

    Returns a highlight point dict (gold ★), or None when the star isn't in the
    catalog / lacks a V magnitude, parsecs, or a parseable OBAFGKM Teff.
    """
    if not name:
        return None
    from core.db import get_conn
    from core.regions import _lookup_spectral_type
    try:
        row = get_conn().execute(
            "SELECT spectral_type, app_magnitude, parsecs FROM star_systems "
            "WHERE LOWER(star_name) = LOWER(?) LIMIT 1", (name,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    vmag = _num(row["app_magnitude"])
    pc = _num(row["parsecs"])
    sp = (row["spectral_type"] or "").strip()
    if vmag is None or pc is None or pc <= 0:
        return None
    r2, _k = _lookup_spectral_type(sp)
    teff = _num(r2.get("Teeff(K)")) if r2 else None
    if teff is None or teff <= 0:
        return None
    return {"name": name, "teff": teff, "abs_mag": vmag + 5.0 - 5.0 * math.log10(pc),
            "color": "#FFD700", "sp_type": sp, "highlight": True}


# ── Phase O O-4: Planet & System Diagrams ─────────────────────────────────────

def prepare_mass_radius(planets: list, mass_key: str, radius_key: str,
                        name_key: str) -> dict:
    """Mass–radius scatter data for a planet set (Phase O · O3).

    Generic over NASA (`pl_bmasse`/`pl_rade`/`pl_name`) and HWC
    (`P_MASS`/`P_RADIUS`/`P_NAME`) planet rows — the caller passes the column keys.
    Filters to planets carrying BOTH a positive mass and radius (Earth units); the
    rest are counted in `skipped`. Returns {"planets": [{name, mass_e, radius_e}],
    "skipped": int} or {"error": str} when none qualify.
    """
    if not planets:
        return {"error": "No planets to plot."}
    out, skipped = [], 0
    for p in planets:
        m = _num(p.get(mass_key))
        r = _num(p.get(radius_key))
        if m is None or r is None or m <= 0 or r <= 0:
            skipped += 1
            continue
        out.append({"name": str(p.get(name_key) or "?"), "mass_e": m, "radius_e": r})
    if not out:
        return {"error": "No planets with both mass and radius to plot."}
    return {"planets": out, "skipped": skipped}


# Solar radius expressed in AU (R☉ = 0.00465047 AU) — converts st_rad (R☉) → R★ (AU).
_R_SUN_AU = 0.00465


def prepare_transit_geometry(planets: list) -> dict:
    """Transit-geometry (impact-parameter) data for a planet set (Phase O · O13).

    Needs the host stellar radius (`st_rad`, R☉) plus, per planet, `pl_orbsmax` (AU)
    and `pl_orbincl` (deg). `R★ = st_rad × 0.00465 AU`; the impact parameter is
    `b = (a/R★)·cos i`. Planets missing an inclination (or SMA) are counted in
    `skipped`. Returns {"star_radius_au", "planets":[{name, a_au, incl_deg, b}],
    "skipped": int} or {"error": str} when `st_rad` is missing/≤0 or no planet has a
    usable inclination. (Note: `b` uses the inclination only — the ascending node is
    unknown, so a transiting `|b|≤1` is necessary but not on its own sufficient.)
    """
    if not planets:
        return {"error": "No planet data to plot."}
    st_rad = None
    for p in planets:
        st_rad = _num(p.get("st_rad"))
        if st_rad is not None and st_rad > 0:
            break
    if st_rad is None or st_rad <= 0:
        return {"error": "Transit geometry needs a stellar radius (st_rad)."}
    r_star_au = st_rad * _R_SUN_AU

    out, skipped = [], 0
    for p in planets:
        a = _num(p.get("pl_orbsmax"))
        incl = _num(p.get("pl_orbincl"))
        if a is None or a <= 0 or incl is None:
            skipped += 1
            continue
        b = (a / r_star_au) * math.cos(math.radians(incl))
        out.append({"name": str(p.get("pl_name") or "?"), "a_au": a,
                    "incl_deg": incl, "b": b})
    if not out:
        return {"error": "No planets have a measured orbital inclination."}
    return {"star_radius_au": r_star_au, "planets": out, "skipped": skipped}


# ── O9 — Brachistochrone profile charts ──────────────────────────────────────
# Physical constants mirror core/calculators.py (kept local so this module stays
# Qt/calculators-import-free).
_O9_G_MS2 = 9.80665                 # 1 g in m/s²
_O9_C_MS  = 299_792_458.0           # speed of light, m/s
_O9_AU_M  = 149_597_870_700.0       # metres per AU

# Fixed per-profile colours (index order) — matches the o09 mockup.
_PROFILE_COLORS = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400"]


def _integrate_phases(phases):
    """Build per-segment kinematic state from a list of (a_seg_ms2, dt_sec) phases.

    Each segment carries the state at its START: (t_start, t_end, v_start, d_start,
    a_seg) integrating from v=0, d=0. Returns (segments, total_time_sec).
    """
    segs = []
    t0 = v0 = d0 = 0.0
    for a_seg, dt in phases:
        if dt is None or dt < 0:
            dt = 0.0
        segs.append((t0, t0 + dt, v0, d0, a_seg))
        d0 = d0 + v0 * dt + 0.5 * a_seg * dt * dt
        v0 = v0 + a_seg * dt
        t0 = t0 + dt
    return segs, t0


def _sample_phases(phases, n=200):
    """Sample piecewise-constant-acceleration phases into (t_hours, v_kms, d_au).

    ``phases`` is a list of (a_seg_ms2, dt_sec) tuples; integrates exact kinematics
    (v = v₀ + a·τ, d = d₀ + v₀·τ + ½·a·τ²) and returns n+1 evenly-spaced samples
    across the total time. A zero-length profile collapses to a single origin point.
    """
    segs, total = _integrate_phases(phases)
    if total <= 0 or not segs:
        return [0.0], [0.0], [0.0]
    t_hours, v_kms, d_au = [], [], []
    j = 0
    for i in range(n + 1):
        t = total * i / n
        while j < len(segs) - 1 and t > segs[j][1]:
            j += 1
        t0, _t1, v0, d0, a = segs[j]
        tl = t - t0
        v = v0 + a * tl
        d = d0 + v0 * tl + 0.5 * a * tl * tl
        t_hours.append(t / 3600.0)
        v_kms.append(v / 1000.0)
        d_au.append(d / _O9_AU_M)
    return t_hours, v_kms, d_au


def prepare_brachistochrone_profiles(result: dict, n_samples: int = 200) -> dict:
    """Reconstruct each brachistochrone profile's v(t)/d(t) curve (Phase O · O9).

    Accepts the result dict from any of the five brachistochrone-bearing core
    functions and rebuilds the piecewise velocity/distance curves from `accel_g`
    plus the per-profile total time and profile type, using the EXACT phase
    structure in `docs/calculators.md`:

      * **opts 22 / 29 / 30** (time-given-distance, `_brachistochrone_profiles`) —
        each profile carries `hours`; P1 = accel T/2 + decel T/2, P2 = accel T/4 /
        coast T/2 / decel T/4, P3 = accel-to-cap / coast / decel (or P1's shape when
        the cap isn't reached, `max_vel == "N"`). `v_cap_pct` defaults to 3.
      * **opt 24** (`compute_distance_at_acceleration`, distance-given-time) — the
        top-level `hours` is the shared total time; P1 = continuous accel (no
        decel), P2 = accel T/4 / coast T/2 / decel T/4, P3 = accel-to-3%c / coast
        (no decel; P1's shape when the cap isn't reached).
      * **opt 23** (`compute_travel_time_custom_thrust`) — a single custom-thrust
        profile: accel for the effective burn / coast / decel for the same burn
        (or accel-to-midpoint / decel in the short-distance `fallback` case).

    Returns {accel_g, profiles:[{label, color, t_hours, v_kms, d_au}]} (parallel
    sample lists per profile; colours fixed per index) or {"error": str}.
    """
    if not result or "error" in result:
        return result if result else {"error": "No data to plot."}
    accel_g = _num(result.get("accel_g"))
    if accel_g is None or accel_g <= 0:
        return {"error": "No acceleration in result."}
    a = accel_g * _O9_G_MS2
    out = []

    # ── opt 23 — custom thrust: single profile, no "profiles" list ────────────
    if "profiles" not in result and result.get("t_total_hours") is not None:
        t_acc   = (_num(result.get("t_accel_hours")) or 0.0) * 3600.0
        t_coast = (_num(result.get("t_coast_hours")) or 0.0) * 3600.0
        if result.get("fallback"):
            phases = [(a, t_acc), (-a, t_acc)]
            label = "Custom Thrust — accelerate to midpoint, decelerate"
        else:
            phases = [(a, t_acc), (0.0, t_coast), (-a, t_acc)]
            label = "Custom Thrust — accelerate · coast · decelerate"
        th, vk, da = _sample_phases(phases, n_samples)
        out.append({"label": label, "color": _PROFILE_COLORS[0],
                    "t_hours": th, "v_kms": vk, "d_au": da})
        return {"accel_g": accel_g, "profiles": out}

    profiles = result.get("profiles")
    if not profiles:
        return {"error": "No brachistochrone profiles in result."}

    # ── opt 24 — distance-given-time: top-level "hours" is the shared total ────
    if result.get("hours") is not None:
        T = (_num(result.get("hours")) or 0.0) * 3600.0
        t_cap = (0.03 * _O9_C_MS) / a                 # opt 24 hard-codes a 3% c cap
        for i, p in enumerate(profiles):
            if i == 0:
                phases = [(a, T)]                                  # continuous, no decel
            elif i == 1:
                phases = [(a, T / 4.0), (0.0, T / 2.0), (-a, T / 4.0)]
            else:
                if p.get("max_vel") == "N" or t_cap >= T:          # cap not reached
                    phases = [(a, T)]
                else:
                    phases = [(a, t_cap), (0.0, T - t_cap)]        # accel-to-cap, coast, no decel
            th, vk, da = _sample_phases(phases, n_samples)
            out.append({"label": p.get("label", f"Profile {i + 1}"),
                        "color": _PROFILE_COLORS[i % len(_PROFILE_COLORS)],
                        "t_hours": th, "v_kms": vk, "d_au": da})
        return {"accel_g": accel_g, "profiles": out}

    # ── opts 22 / 29 / 30 — time-given-distance: each profile carries "hours" ──
    v_cap_pct = _num(result.get("v_cap_pct")) or 3.0
    t_cap = (v_cap_pct / 100.0 * _O9_C_MS) / a
    for i, p in enumerate(profiles):
        T = (_num(p.get("hours")) or 0.0) * 3600.0
        if i == 0:
            phases = [(a, T / 2.0), (-a, T / 2.0)]
        elif i == 1:
            phases = [(a, T / 4.0), (0.0, T / 2.0), (-a, T / 4.0)]
        else:
            if p.get("max_vel") == "N" or 2.0 * t_cap >= T:        # cap not reached → P1 shape
                phases = [(a, T / 2.0), (-a, T / 2.0)]
            else:
                phases = [(a, t_cap), (0.0, T - 2.0 * t_cap), (-a, t_cap)]
        th, vk, da = _sample_phases(phases, n_samples)
        out.append({"label": p.get("label", f"Profile {i + 1}"),
                    "color": _PROFILE_COLORS[i % len(_PROFILE_COLORS)],
                    "t_hours": th, "v_kms": vk, "d_au": da})
    return {"accel_g": accel_g, "profiles": out}
