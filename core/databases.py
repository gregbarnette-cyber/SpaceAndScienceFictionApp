# core/databases.py — Star database query functions (SIMBAD, NASA, HWC, OEC, Mission Exocat)
# Phase C: compute_simbad_lookup() added.
# Phase D: remaining query functions added.

import csv
import math
import os
import re

from .shared import _make_simbad, _network_error_msg, _timeout_ctx, _with_retries

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")

# Module-level caches
_HWC_DATA      = None
_OEC_DATA      = None
_MISSION_EXOCAT = None


# ── Shared numeric helpers ────────────────────────────────────────────────────

def _fval(v):
    """Convert to float; return None if missing or NaN."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _fmt(v, decimals=3, default="N/A"):
    """Format value to fixed-decimal string, or return default."""
    f = _fval(v)
    return f"{f:.{decimals}f}" if f is not None else default


def compute_habitable_zone(st_teff, st_lum_log10=None, st_rad=None):
    """Compute Kopparapu et al. habitable zone boundaries.

    Returns list of (zone_name, au_value) tuples, or [] if insufficient data.
    Luminosity source: prefers (st_rad² × (teff/5778)⁴); falls back to 10**st_lum_log10.
    """
    teff = _fval(st_teff)
    if teff is None:
        return []

    lum = None
    if st_rad is not None:
        r = _fval(st_rad)
        if r is not None:
            lum = r ** 2 * (teff / 5778) ** 4
    if lum is None and st_lum_log10 is not None:
        lv = _fval(st_lum_log10)
        if lv is not None:
            lum = 10 ** lv
    if lum is None:
        return []

    seffsun = [1.776, 1.107, 0.356, 0.320, 1.188, 0.99]
    a = [2.136e-4,  1.332e-4,  6.171e-5,  5.547e-5,  1.433e-4,  1.209e-4]
    b = [2.533e-8,  1.580e-8,  1.698e-9,  1.526e-9,  1.707e-8,  1.404e-8]
    c = [-1.332e-11,-8.308e-12,-3.198e-12,-2.874e-12,-8.968e-12,-7.418e-12]
    d = [-3.097e-15,-1.931e-15,-5.575e-16,-5.011e-16,-2.084e-15,-1.713e-15]

    tstar = teff - 5780.0
    seff  = [seffsun[i] + a[i]*tstar + b[i]*tstar**2 + c[i]*tstar**3 + d[i]*tstar**4
             for i in range(6)]

    rv   = math.sqrt(lum / seff[0])
    rg5  = math.sqrt(lum / seff[4])
    rg   = math.sqrt(lum / seff[1])
    rg01 = math.sqrt(lum / seff[5])
    mg   = math.sqrt(lum / seff[2])
    em   = math.sqrt(lum / seff[3])

    return [
        ("Optimistic Inner HZ (Recent Venus)",                          rv),
        ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",  rg5),
        ("Conservative Inner HZ (Runaway Greenhouse)",                  rg),
        ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)",rg01),
        ("Conservative Outer HZ (Maximum Greenhouse)",                  mg),
        ("Optimistic Outer HZ (Early Mars)",                            em),
    ]


def compute_simbad_lookup(star_name: str) -> dict:
    """Query SIMBAD for a star by name or designation.

    Returns a dict with keys:
        main_id      — str: SIMBAD primary identifier
        ra           — float | None: right ascension in decimal degrees
        dec          — float | None: declination in decimal degrees
        sp_type      — str | None: spectral type string
        plx_value    — float | None: parallax in mas (> 0 if present)
        teff         — float | None: effective temperature in K
        vmag         — float | None: apparent V magnitude
        ly           — float | None: distance in light years (4 dp)
        parsecs      — float | None: distance in parsecs (4 dp)
        designations — dict: {key: id_str | None} for MAIN_ID, NAME, GJ, HD, HIP, …
        desig_str    — str: comma-separated designation list for display

    Returns {"error": str} on any failure (no match, network error, etc.).
    """
    from astroquery.simbad import Simbad

    custom_simbad = _make_simbad("sp_type", "plx_value", "V", "mesfe_h")

    try:
        with _timeout_ctx(30):
            result     = _with_retries(custom_simbad.query_object, star_name)
            ids_result = _with_retries(Simbad.query_objectids, star_name)
    except Exception as e:
        return {"error": _network_error_msg(e, "SIMBAD")}

    if result is None:
        return {"error": f"No results found for '{star_name}'"}

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

    main_id = str(_safe("main_id") or star_name)

    ra_raw = _safe("ra")
    dec_raw = _safe("dec")
    ra = float(ra_raw) if ra_raw is not None else None
    dec = float(dec_raw) if dec_raw is not None else None

    sp_raw = _safe("sp_type")
    sp_type = str(sp_raw).strip() if sp_raw is not None else None

    plx_raw = _safe("plx_value")
    plx = None
    ly = None
    parsecs = None
    if plx_raw is not None:
        try:
            plx_f = float(plx_raw)
            if plx_f > 0:
                plx = plx_f
                parsecs = round(1000.0 / plx_f, 4)
                ly = round(parsecs * 3.26156, 4)
        except (ValueError, ZeroDivisionError):
            pass

    teff_raw = _safe("mesfe_h.teff")
    teff = None
    if teff_raw is not None:
        try:
            teff = float(teff_raw)
        except (ValueError, TypeError):
            pass

    vmag_raw = _safe("V")
    vmag = None
    if vmag_raw is not None:
        try:
            vmag = float(vmag_raw)
        except (ValueError, TypeError):
            pass

    # ── Designation parsing ───────────────────────────────────────────────────
    keys_order = [
        "MAIN_ID", "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
        "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
        "TIC", "Gaia EDR3", "2MASS",
    ]
    designations = {k: None for k in keys_order}
    designations["MAIN_ID"] = main_id

    prefix_map = [
        ("NAME ",       "NAME"),
        ("GJ ",         "GJ"),
        ("HD ",         "HD"),
        ("HIP ",        "HIP"),
        ("HR ",         "HR"),
        ("Wolf ",       "Wolf"),
        ("LHS ",        "LHS"),
        ("BD+",         "BD"),
        ("BD-",         "BD"),
        ("BD ",         "BD"),
        ("K2 ",         "K2"),
        ("Kepler-",     "Kepler"),
        ("Kepler ",     "Kepler"),
        ("KOI-",        "KOI"),
        ("KOI ",        "KOI"),
        ("TOI-",        "TOI"),
        ("TOI ",        "TOI"),
        ("CoRoT-",      "CoRoT"),
        ("CoRoT ",      "CoRoT"),
        ("COCONUTS-",   "COCONUTS"),
        ("HAT-P-",      "HAT_P"),
        ("WASP-",       "WASP"),
        ("TIC ",        "TIC"),
        ("Gaia EDR3 ",  "Gaia EDR3"),
        ("2MASS J",     "2MASS"),
        ("2MASS ",      "2MASS"),
    ]

    if ids_result is not None:
        for id_row in ids_result:
            id_str = str(id_row["id"]).strip()
            for prefix, key in prefix_map:
                if id_str.startswith(prefix) and designations[key] is None:
                    designations[key] = id_str
                    break

    desig_list = [str(designations[k]) for k in keys_order if designations[k]]
    desig_str = ", ".join(desig_list) if desig_list else "N/A"

    return {
        "main_id":      main_id,
        "ra":           ra,
        "dec":          dec,
        "sp_type":      sp_type,
        "plx_value":    plx,
        "teff":         teff,
        "vmag":         vmag,
        "ly":           ly,
        "parsecs":      parsecs,
        "designations": designations,
        "desig_str":    desig_str,
    }


# ── NASA Exoplanet Archive helpers ────────────────────────────────────────────

def _get_archive_query_params(designations):
    """Return (field, value) for pscomppars. Priority: HIP > HD > TIC > Gaia EDR3."""
    if designations.get("HIP"):
        return "hip_name", designations["HIP"]
    if designations.get("HD"):
        return "hd_name", designations["HD"]
    if designations.get("TIC"):
        return "tic_id", designations["TIC"]
    if designations.get("Gaia EDR3"):
        return "gaia_id", designations["Gaia EDR3"]
    return None, None


def _get_hwo_query_params(designations):
    """Return (field, value) for di_stars_exep. Priority: HIP > HD > TIC > HR > GJ."""
    if designations.get("HIP"):
        return "hip_name", designations["HIP"]
    if designations.get("HD"):
        return "hd_name", designations["HD"]
    if designations.get("TIC"):
        return "tic_id", designations["TIC"]
    if designations.get("HR"):
        return "hr_name", designations["HR"]
    if designations.get("GJ"):
        return "gj_name", designations["GJ"]
    return None, None


def _query_tap(table, where, order_by=None, timeout=60):
    """Query NASA Exoplanet Archive TAP endpoint; return list of row dicts."""
    import requests
    q = f"SELECT * FROM {table} WHERE {where}"
    if order_by:
        q += f" ORDER BY {order_by}"

    def _do_get():
        resp = requests.get(
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            params={"query": q, "format": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    return _with_retries(_do_get)


# ── Option 2: NASA Exoplanet Archive All Tables ───────────────────────────────

def compute_exoplanet_archive(simbad_result: dict,
                               progress_callback=None) -> dict:
    """Query NASA pscomppars + HWO ExEP + Mission Exocat.

    Returns {simbad, planets, hwo, exocat} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]

    field, value = _get_archive_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, Gaia) found for NASA Exoplanet Archive."}

    if progress_callback:
        progress_callback(f"Querying NASA Exoplanet Archive ({value})…")
    try:
        planets = _query_tap("pscomppars", f"{field}='{value}'", "pl_orbsmax")
    except Exception as e:
        return {"error": _network_error_msg(e, "NASA Exoplanet Archive")}

    if not planets:
        return {"error": f"No exoplanet data found for '{value}' in NASA Exoplanet Archive."}

    # HWO ExEP (optional)
    hwo = None
    hwo_field, hwo_value = _get_hwo_query_params(designations)
    if hwo_field:
        if progress_callback:
            progress_callback(f"Querying HWO ExEP archive ({hwo_value})…")
        try:
            rows = _query_tap("di_stars_exep", f"{hwo_field}='{hwo_value}'", "sy_dist")
            if rows:
                hwo = rows
        except Exception:
            pass

    # Mission Exocat (optional)
    if progress_callback:
        progress_callback("Searching Mission Exocat…")
    exocat = _query_mission_exocat_by_designations(designations)

    return {
        "simbad": simbad_result,
        "planets": planets,
        "hwo":    hwo,
        "exocat": exocat,
    }


# ── Option 3: Planetary Systems Composite ────────────────────────────────────

def compute_planetary_systems_composite(simbad_result: dict,
                                         progress_callback=None) -> dict:
    """Query NASA pscomppars only.

    Returns {simbad, planets} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    field, value = _get_archive_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, Gaia) found for NASA Exoplanet Archive."}

    if progress_callback:
        progress_callback(f"Querying NASA Exoplanet Archive ({value})…")
    try:
        planets = _query_tap("pscomppars", f"{field}='{value}'", "pl_orbsmax")
    except Exception as e:
        return {"error": _network_error_msg(e, "NASA Exoplanet Archive")}

    if not planets:
        return {"error": f"No exoplanet data found for '{value}'."}

    return {"simbad": simbad_result, "planets": planets}


# ── Option 4: HWO ExEP ───────────────────────────────────────────────────────

def compute_hwo_exep(simbad_result: dict,
                      progress_callback=None) -> dict:
    """Query HWO ExEP archive only.

    Returns {simbad, hwo} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    field, value = _get_hwo_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, HR, GJ) found for HWO ExEP archive."}

    if progress_callback:
        progress_callback(f"Querying HWO ExEP archive ({value})…")
    try:
        rows = _query_tap("di_stars_exep", f"{field}='{value}'", "sy_dist")
    except Exception as e:
        return {"error": _network_error_msg(e, "HWO ExEP archive")}

    if not rows:
        return {"error": f"No HWO ExEP data found for '{value}'."}

    return {"simbad": simbad_result, "hwo": rows}


# ── Option 5: Mission Exocat ─────────────────────────────────────────────────

_MISSION_EXOCAT = None


def _load_mission_exocat():
    """Load missionExocat.csv; return (hip_idx, hd_idx, gj_idx) case-insensitive dicts."""
    global _MISSION_EXOCAT
    if _MISSION_EXOCAT is not None:
        return _MISSION_EXOCAT
    path = os.path.normpath(os.path.join(_DATA_DIR, "missionExocat.csv"))
    hip_idx, hd_idx, gj_idx = {}, {}, {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for idx, key in [(hip_idx, "hip_name"), (hd_idx, "hd_name"), (gj_idx, "gj_name")]:
                    v = (row.get(key) or "").strip().upper()
                    if v:
                        idx.setdefault(v, row)
    except Exception:
        pass
    _MISSION_EXOCAT = (hip_idx, hd_idx, gj_idx)
    return _MISSION_EXOCAT


def _query_mission_exocat_by_designations(designations):
    """Search Mission Exocat by HIP → HD → GJ; return row dict or None."""
    hip_idx, hd_idx, gj_idx = _load_mission_exocat()
    for desig_key, idx in [("HIP", hip_idx), ("HD", hd_idx), ("GJ", gj_idx)]:
        val = (designations.get(desig_key) or "").strip().upper()
        if val and val in idx:
            return idx[val]
    return None


def compute_mission_exocat(simbad_result: dict) -> dict:
    """Search missionExocat.csv for the star.

    Returns {simbad, exocat} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result
    row = _query_mission_exocat_by_designations(simbad_result["designations"])
    if row is None:
        return {"error": "Star not found in Mission Exocat."}
    return {"simbad": simbad_result, "exocat": row}


# ── Option 6: Habitable Worlds Catalog ───────────────────────────────────────

def _load_hwc():
    """Load hwc.csv; return (hip_idx, hd_idx, name_idx)."""
    global _HWC_DATA
    if _HWC_DATA is not None:
        return _HWC_DATA
    path = os.path.normpath(os.path.join(_DATA_DIR, "hwc.csv"))
    hip_idx, hd_idx, name_idx = {}, {}, {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for idx, col in [(hip_idx, "S_NAME_HIP"), (hd_idx, "S_NAME_HD"), (name_idx, "S_NAME")]:
                    k = (row.get(col) or "").strip().upper()
                    if k:
                        idx.setdefault(k, []).append(row)
    except Exception:
        pass
    _HWC_DATA = (hip_idx, hd_idx, name_idx)
    return _HWC_DATA


def compute_hwc(simbad_result: dict) -> dict:
    """Search hwc.csv (Habitable Worlds Catalog) for the star.

    Returns {simbad, star_row, planet_rows (sorted by semi-major axis)}
    or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    hip_idx, hd_idx, name_idx = _load_hwc()

    hip  = (designations.get("HIP")  or "").strip().upper()
    hd   = (designations.get("HD")   or "").strip().upper()
    raw  = (designations.get("NAME") or "").strip()
    name = (raw[5:].strip() if raw.upper().startswith("NAME ") else raw).upper()

    rows = None
    for k, idx in [(hip, hip_idx), (hd, hd_idx), (name, name_idx)]:
        if k:
            rows = idx.get(k)
            if rows:
                break

    if not rows:
        return {"error": "Star not found in Habitable Worlds Catalog."}

    try:
        rows = sorted(rows, key=lambda r: float(r.get("P_SEMI_MAJOR_AXIS") or "inf"))
    except Exception:
        pass

    return {"simbad": simbad_result, "star_row": rows[0], "planet_rows": rows}


# ── Option 7: Open Exoplanet Catalogue ───────────────────────────────────────

def _load_oec():
    """Download and parse OEC XML; build case-insensitive name→system index. Cached."""
    global _OEC_DATA
    if _OEC_DATA is not None:
        return _OEC_DATA
    from astroquery import open_exoplanet_catalogue as _oec_mod
    tree = _oec_mod.get_catalogue()
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    index = {}
    for system in root:
        for elem in system.iter("name"):
            if elem.text:
                k = elem.text.strip().lower()
                if k not in index:
                    index[k] = system
    _OEC_DATA = (root, index)
    return _OEC_DATA


def _get_oec_candidates(designations):
    """Return ordered candidate name strings for OEC lookup."""
    candidates = []
    for key in ("HIP", "HD", "GJ", "HR", "WASP", "HAT_P", "Kepler", "TOI",
                "K2", "CoRoT", "COCONUTS", "KOI", "TIC", "2MASS"):
        val = designations.get(key)
        if val:
            s = str(val).strip()
            s = re.sub(r"(?i)^(k2)\s+(\d)", r"K2-\2", s)
            s = re.sub(r"(?i)^(kepler)\s+(\d)", r"Kepler-\2", s)
            s = re.sub(r"(?i)^(hat-p)\s+(\d)", r"HAT-P-\2", s)
            s = re.sub(r"(?i)^(WASP-\d+)([AB])$", r"\1 \2", s)
            s = re.sub(r"(?i)^(2MASS\s+)J(\d)", r"\g<1>\2", s)
            candidates.append(s)
    name_val = str(designations.get("NAME") or "").strip()
    if name_val.upper().startswith("NAME "):
        candidates.append(name_val[5:].strip())
    elif name_val:
        candidates.append(name_val)
    main_id = str(designations.get("MAIN_ID") or "").strip()
    for prefix in ("NAME ", "V* ", "* "):
        if main_id.upper().startswith(prefix.upper()):
            main_id = main_id[len(prefix):].strip()
            break
    if main_id:
        candidates.append(main_id)
    return candidates


def _oec_val(elem, tag):
    """Return stripped text of first matching child tag, or None."""
    if elem is None:
        return None
    text = elem.findtext(tag)
    return text.strip() if text and text.strip() else None


def _oec_star_dict(system_elem, star_elem):
    """Extract star data from OEC XML as a dict."""
    def fmtf(v, dp):
        try:
            return f"{float(v):.{dp}f}"
        except (TypeError, ValueError):
            return "N/A"
    spec   = _oec_val(star_elem, "spectraltype") or "N/A"
    magv   = _oec_val(star_elem, "magV")
    temp   = _oec_val(star_elem, "temperature")
    mass   = _oec_val(star_elem, "mass")
    radius = _oec_val(star_elem, "radius")
    met    = _oec_val(star_elem, "metallicity")
    age    = _oec_val(star_elem, "age")
    dist   = _oec_val(system_elem, "distance")
    names  = [e.text.strip() for e in star_elem.findall("name") if e.text and e.text.strip()]
    # Planets
    planets = []
    for planet in star_elem.findall("planet"):
        pnames = [e.text.strip() for e in planet.findall("name") if e.text and e.text.strip()]
        mass_j  = _oec_val(planet, "mass")
        rad_j   = _oec_val(planet, "radius")
        period  = _oec_val(planet, "period")
        sma     = _oec_val(planet, "semimajoraxis")
        ecc     = _oec_val(planet, "eccentricity")
        temp_p  = _oec_val(planet, "temperature")
        method  = _oec_val(planet, "discoverymethod")
        year    = _oec_val(planet, "discoveryyear")
        status  = _oec_val(planet, "list") or ""
        planets.append({
            "name": pnames[0] if pnames else "N/A",
            "mass_j": mass_j, "rad_j": rad_j,
            "period": period, "sma": sma, "ecc": ecc,
            "temp": temp_p, "method": method, "year": year, "status": status,
        })
    # Sort planets by sma (N/A last)
    def sma_sort(p):
        try:
            return float(p["sma"])
        except (TypeError, ValueError):
            return float("inf")
    planets.sort(key=sma_sort)
    return {
        "names": names,
        "spec": spec, "magv": magv, "temp": temp, "mass": mass,
        "radius": radius, "met": met, "age": age, "dist": dist,
        "planets": planets,
    }


def compute_oec(simbad_result: dict, progress_callback=None) -> dict:
    """Search Open Exoplanet Catalogue for the star.

    Returns {simbad, stars: [list of star dicts]} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    if progress_callback:
        progress_callback("Loading Open Exoplanet Catalogue (first use downloads ~3 MB)…")

    designations = simbad_result["designations"]
    try:
        _, index = _load_oec()
    except Exception as e:
        return {"error": f"Failed to load Open Exoplanet Catalogue: {e}"}
    candidates = _get_oec_candidates(designations)

    system_elem = None
    for name in candidates:
        key = name.lower()
        if key in index:
            system_elem = index[key]
            break

    if system_elem is None:
        return {"error": "Star not found in Open Exoplanet Catalogue."}

    stars_with_planets = [s for s in system_elem.iter("star") if s.find("planet") is not None]
    star_elems = stars_with_planets if stars_with_planets else list(system_elem.iter("star"))

    if not star_elems:
        return {"error": "No star elements found in OEC system."}

    stars = [_oec_star_dict(system_elem, se) for se in star_elems]
    return {"simbad": simbad_result, "stars": stars}


# ── Option 50: Star Systems CSV Query ────────────────────────────────────────

_CSV_DESIG_KEYS = [
    "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
    "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
    "TIC", "Gaia EDR3", "2MASS",
]

_CSV_PREFIX_MAP = [
    ("GJ ",         "GJ"),
    ("HD ",         "HD"),
    ("HIP ",        "HIP"),
    ("HR ",         "HR"),
    ("Wolf ",       "Wolf"),
    ("LHS ",        "LHS"),
    ("BD+",         "BD"),
    ("BD-",         "BD"),
    ("BD ",         "BD"),
    ("K2 ",         "K2"),
    ("Kepler-",     "Kepler"),
    ("Kepler ",     "Kepler"),
    ("KOI-",        "KOI"),
    ("KOI ",        "KOI"),
    ("TOI-",        "TOI"),
    ("TOI ",        "TOI"),
    ("CoRoT-",      "CoRoT"),
    ("CoRoT ",      "CoRoT"),
    ("COCONUTS-",   "COCONUTS"),
    ("HAT-P-",      "HAT_P"),
    ("WASP-",       "WASP"),
    ("TIC ",        "TIC"),
    ("Gaia EDR3 ",  "Gaia EDR3"),
    ("2MASS J",     "2MASS"),
    ("2MASS ",      "2MASS"),
]


def _parse_designations_from_ids(ids_string: str) -> str:
    """Parse a pipe-separated SIMBAD ids string into a comma-separated designation string."""
    desig = {k: None for k in _CSV_DESIG_KEYS}
    if not ids_string:
        return ""
    for id_str in ids_string.split("|"):
        id_str = id_str.strip()
        for prefix, key in _CSV_PREFIX_MAP:
            if id_str.startswith(prefix) and desig[key] is None:
                desig[key] = id_str
                break
    parts = [desig[k] for k in _CSV_DESIG_KEYS if desig[k] is not None]
    return ", ".join(parts)


def _run_simbad_csv_query(simbad, criteria, query_num, total_queries,
                           existing_ids, progress_callback=None):
    """Run one SIMBAD criteria query; return (new_rows, discarded)."""
    import warnings
    if progress_callback:
        progress_callback(f"Query {query_num}/{total_queries}: running SIMBAD query…")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = simbad.query_criteria(criteria)
    except Exception as e:
        return [], 0

    if result is None or len(result) == 0:
        return [], 0

    seen_main_ids = {}
    new_rows  = []
    discarded = 0

    for row in result:
        main_id = str(row["main_id"]).strip() if row["main_id"] is not None else ""
        ids_str = str(row["ids"]).strip()     if row["ids"]     is not None else ""
        sp_type = str(row["sp_type"]).strip() if row["sp_type"] is not None else ""
        if sp_type.lower() in ("", "none", "--"):
            sp_type = ""
        desig_str = _parse_designations_from_ids(ids_str)

        if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":
            discarded += 1
            continue
        if main_id in seen_main_ids or main_id in existing_ids:
            continue

        try:
            plx_f   = float(row["plx_value"])
            plx     = f"{plx_f:.4f}"
            parsecs = f"{1000.0 / plx_f:.3f}" if plx_f > 0 else ""
            ly      = f"{1000.0 / plx_f * 3.26156:.3f}" if plx_f > 0 else ""
        except (TypeError, ValueError, ZeroDivisionError):
            plx = parsecs = ly = ""

        try:
            vmag = f"{float(row['V']):.3f}"
        except (TypeError, ValueError):
            vmag = ""

        try:
            ra_deg = float(row["ra"])
            ra_h   = int(ra_deg / 15)
            ra_m   = int((ra_deg / 15 - ra_h) * 60)
            ra_s   = ((ra_deg / 15 - ra_h) * 60 - ra_m) * 60
            ra     = f"{ra_h:02d} {ra_m:02d} {ra_s:07.4f}"
        except (TypeError, ValueError):
            ra = ""

        try:
            dec_deg  = float(row["dec"])
            dec_sign = "-" if dec_deg < 0 else "+"
            dec_abs  = abs(dec_deg)
            dec_d    = int(dec_abs)
            dec_m    = int((dec_abs - dec_d) * 60)
            dec_s    = ((dec_abs - dec_d) * 60 - dec_m) * 60
            dec      = f"{dec_sign}{dec_d:02d} {dec_m:02d} {dec_s:06.3f}"
        except (TypeError, ValueError):
            dec = ""

        seen_main_ids[main_id] = len(new_rows)
        existing_ids.add(main_id)
        new_rows.append({
            "Star Name":          main_id,
            "Star Designations":  desig_str,
            "Spectral Type":      sp_type,
            "Parallax":           plx,
            "Parsecs":            parsecs,
            "Light Years":        ly,
            "Apparent Magnitude": vmag,
            "RA":                 ra,
            "DEC":                dec,
        })

    if progress_callback:
        progress_callback(
            f"Query {query_num}/{total_queries} — {len(new_rows)} new stars ({discarded} discarded)"
        )
    return new_rows, discarded


def compute_star_systems_csv(progress_callback=None) -> dict:
    """Run 17 SIMBAD criteria queries and write starSystems.csv.

    Calls progress_callback(msg) after each query.
    Returns {total_rows, queries_run, output_file, total_new, total_discarded}
    or {"error": str}.
    """
    from astroquery.simbad import Simbad
    from datetime import datetime

    simbad = Simbad()
    simbad.TIMEOUT = 480
    simbad.add_votable_fields("sp_type", "plx_value", "V", "ids")

    csv_path   = os.path.normpath(os.path.join(_DATA_DIR, "starSystems.csv"))
    fieldnames = [
        "Star Name", "Star Designations", "Spectral Type", "Parallax",
        "Parsecs", "Light Years", "Apparent Magnitude", "RA", "DEC",
    ]

    if os.path.exists(csv_path):
        date_stamp   = datetime.now().strftime("%Y%m%d")
        backup_path  = os.path.normpath(os.path.join(_DATA_DIR, f"starSystemsBackup-{date_stamp}.csv"))
        os.rename(csv_path, backup_path)

    existing_rows = []
    existing_ids  = set()

    queries = [
        "plx > 25.99 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'",
        "plx > 20.99 & plx < 26 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'",
        "plx > 17.99 & plx < 21 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 16.49 & plx < 18 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 15.49 & plx < 16.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 14.49 & plx < 15.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 13.99 & plx < 14.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 13.49 & plx < 14 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 12.99 & plx < 13.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 12.49 & plx < 13 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.99 & plx < 12.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.49 & plx < 12 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.09 & plx < 11.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.79 & plx < 11.1 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.49 & plx < 10.8 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.29 & plx < 10.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 9.99 & plx < 10.3 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
    ]

    all_new_rows    = []
    total_discarded = 0
    total_queries   = len(queries)

    for i, criteria in enumerate(queries, start=1):
        new_rows, discarded = _run_simbad_csv_query(
            simbad, criteria, i, total_queries, existing_ids, progress_callback
        )
        all_new_rows.extend(new_rows)
        total_discarded += discarded

    all_new_rows.sort(key=lambda r: float(r["Light Years"]) if r["Light Years"] else float("inf"))
    all_rows = existing_rows + all_new_rows

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
    except Exception as e:
        return {"error": f"Could not write starSystems.csv: {e}"}

    return {
        "total_rows":      len(all_rows),
        "queries_run":     total_queries,
        "output_file":     csv_path,
        "total_new":       len(all_new_rows),
        "total_discarded": total_discarded,
    }
