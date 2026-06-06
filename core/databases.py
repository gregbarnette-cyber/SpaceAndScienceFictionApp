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

    if result is None or len(result) == 0:
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
        # SIMBAD now labels the Gaia source "Gaia DR3 <id>" (not "Gaia EDR3");
        # DR3 ≡ EDR3 source_ids, so both map to the "Gaia EDR3" key. DR1/DR2 differ
        # and are intentionally not captured.
        ("Gaia EDR3 ",  "Gaia EDR3"),
        ("Gaia DR3 ",   "Gaia EDR3"),
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
    """Load mission_exocat table; return (hip_idx, hd_idx, gj_idx) case-insensitive dicts."""
    global _MISSION_EXOCAT
    if _MISSION_EXOCAT is not None:
        return _MISSION_EXOCAT
    from core.db import get_conn, table_exists
    hip_idx, hd_idx, gj_idx = {}, {}, {}
    try:
        if table_exists("mission_exocat"):
            for row in get_conn().execute("SELECT * FROM mission_exocat").fetchall():
                row = dict(row)
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
    """Load hwc table; return (hip_idx, hd_idx, name_idx)."""
    global _HWC_DATA
    if _HWC_DATA is not None:
        return _HWC_DATA
    from core.db import get_conn, table_exists
    hip_idx, hd_idx, name_idx = {}, {}, {}
    try:
        if table_exists("hwc"):
            for row in get_conn().execute("SELECT * FROM hwc").fetchall():
                row = dict(row)
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
    # SIMBAD's `ids` output labels the Gaia source as "Gaia DR3 <id>" (and DR1/DR2);
    # it no longer emits "Gaia EDR3". DR3 and EDR3 source_ids are identical, so both
    # prefixes map to the same slot; DR1/DR2 are deliberately NOT captured (their
    # source_ids differ). Capturing DR3 is what lets the GCNS cross-match join.
    ("Gaia EDR3 ",  "Gaia EDR3"),
    ("Gaia DR3 ",   "Gaia EDR3"),
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


def _masked_to_none(val):
    """Return None if val is a numpy/astropy masked element, otherwise val."""
    try:
        if hasattr(val, "mask") and val.mask:
            return None
    except Exception:
        pass
    return val


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
            plx_raw = _masked_to_none(row["plx_value"])
            plx_f   = float(plx_raw)
            plx     = f"{plx_f:.4f}"
            parsecs = f"{1000.0 / plx_f:.3f}" if plx_f > 0 else ""
            ly      = f"{1000.0 / plx_f * 3.26156:.3f}" if plx_f > 0 else ""
        except (TypeError, ValueError, ZeroDivisionError):
            plx = parsecs = ly = ""

        try:
            v_raw = _masked_to_none(row['V'])
            vmag  = f"{float(v_raw):.3f}"
        except (TypeError, ValueError):
            vmag = ""

        try:
            ra_raw = _masked_to_none(row["ra"])
            ra_deg = float(ra_raw)
            ra_h   = int(ra_deg / 15)
            ra_m   = int((ra_deg / 15 - ra_h) * 60)
            ra_s   = ((ra_deg / 15 - ra_h) * 60 - ra_m) * 60
            ra     = f"{ra_h:02d} {ra_m:02d} {ra_s:07.4f}"
        except (TypeError, ValueError):
            ra = ""

        try:
            dec_raw  = _masked_to_none(row["dec"])
            dec_deg  = float(dec_raw)
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
    """Run 17 SIMBAD criteria queries and write results to the star_systems DB table.

    Calls progress_callback(msg) after each query.
    Returns {total_rows, queries_run, backup_table, total_new, total_discarded}
    or {"error": str}.
    """
    from astroquery.simbad import Simbad
    from datetime import datetime
    from core.db import get_conn

    simbad = Simbad()
    simbad.TIMEOUT = 480
    simbad.add_votable_fields("sp_type", "plx_value", "V", "ids")

    conn = get_conn()

    # Back up existing rows to a dated table, then clear for fresh run.
    backup_table = None
    existing_count = conn.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0]
    if existing_count > 0:
        date_stamp   = datetime.now().strftime("%Y%m%d")
        backup_table = f"star_systems_backup_{date_stamp}"
        with conn:
            conn.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM star_systems")
            conn.execute("DELETE FROM star_systems")

    existing_ids = set()

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

    try:
        with conn:
            conn.executemany(
                """INSERT INTO star_systems
                   (star_name, designations, spectral_type, parallax,
                    parsecs, light_years, app_magnitude, ra, dec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r["Star Name"],
                        r["Star Designations"],
                        r["Spectral Type"],
                        r["Parallax"],
                        r["Parsecs"],
                        r["Light Years"],
                        r["Apparent Magnitude"],
                        r["RA"],
                        r["DEC"],
                    )
                    for r in all_new_rows
                ],
            )
    except Exception as e:
        return {"error": f"Could not write to star_systems table: {e}"}

    return {
        "total_rows":      len(all_new_rows),
        "queries_run":     total_queries,
        "backup_table":    backup_table,
        "total_new":       len(all_new_rows),
        "total_discarded": total_discarded,
    }


# ── Option 51: Export Star Systems to CSV ────────────────────────────────────

def export_star_systems_csv(output_dir: str) -> dict:
    """Read the star_systems table and write starSystems.csv to output_dir.

    Returns {"path": str, "count": int} or {"error": str}.
    """
    from core.db import get_conn

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM star_systems ORDER BY light_years ASC"
    ).fetchall()

    if not rows:
        return {"error": "star_systems table is empty. Run option 50 first."}

    path = os.path.join(output_dir, "starSystems.csv")
    fieldnames = [
        "Star Name", "Star Designations", "Spectral Type", "Parallax",
        "Parsecs", "Light Years", "Apparent Magnitude", "RA", "DEC",
    ]

    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({
                    "Star Name":          r["star_name"],
                    "Star Designations":  r["designations"],
                    "Spectral Type":      r["spectral_type"],
                    "Parallax":           r["parallax"],
                    "Parsecs":            r["parsecs"],
                    "Light Years":        r["light_years"],
                    "Apparent Magnitude": r["app_magnitude"],
                    "RA":                 r["ra"],
                    "DEC":                r["dec"],
                })
    except Exception as e:
        return {"error": f"Could not write starSystems.csv: {e}"}

    return {"path": path, "count": len(rows)}


# ── Options 52–56: Import functions ──────────────────────────────────────────

def import_hwc_csv(csv_path: str) -> dict:
    """Replace the hwc table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"P_NAME", "S_NAME", "S_NAME_HIP", "S_NAME_HD"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    conn = get_conn()
    cols_ddl = ", ".join(f'"{col}" TEXT' for col in headers)
    placeholders = ", ".join("?" for _ in headers)

    try:
        col_list = ", ".join(f'"{col}"' for col in headers)
        with conn:
            conn.execute("DROP TABLE IF EXISTS hwc")
            conn.execute(f"CREATE TABLE hwc ({cols_ddl})")
            conn.executemany(
                f"INSERT INTO hwc ({col_list}) VALUES ({placeholders})",
                [tuple(r.get(col, "") for col in headers) for r in rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    global _HWC_DATA
    _HWC_DATA = None

    return {"count": len(rows), "path": csv_path}


def import_mission_exocat_csv(csv_path: str) -> dict:
    """Replace the mission_exocat table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"star_name", "hip_name", "hd_name", "gj_name"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    conn = get_conn()
    # First column is rowid (INTEGER PRIMARY KEY); remaining are TEXT.
    rest = [col for col in headers if col != "rowid"]
    cols_ddl = '"rowid" INTEGER PRIMARY KEY, ' + ", ".join(f'"{col}" TEXT' for col in rest)
    all_cols = ["rowid"] + rest
    placeholders = ", ".join("?" for _ in all_cols)

    try:
        col_list = ", ".join(f'"{col}"' for col in all_cols)
        with conn:
            conn.execute("DROP TABLE IF EXISTS mission_exocat")
            conn.execute(f"CREATE TABLE mission_exocat ({cols_ddl})")
            conn.executemany(
                f"INSERT INTO mission_exocat ({col_list}) VALUES ({placeholders})",
                [tuple(r.get(col, "") for col in all_cols) for r in rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    global _MISSION_EXOCAT
    _MISSION_EXOCAT = None

    return {"count": len(rows), "path": csv_path}


def import_main_sequence_csv(csv_path: str) -> dict:
    """Replace main_sequence_stars table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"Spectral Class", "Bolo. Corr. (BC)"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM main_sequence_stars")
            conn.executemany(
                """INSERT INTO main_sequence_stars
                   (spectral_class, b_v, teff_k, abs_mag_vis, abs_mag_bol, bc,
                    lum, radius, mass, density, lifetime)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r.get("Spectral Class", ""),
                        r.get("B-V", ""),
                        r.get("Teeff(K)", ""),
                        r.get("AbsMag Vis.", ""),
                        r.get("AbsMag Bol.", ""),
                        r.get("Bolo. Corr. (BC)", ""),
                        r.get("Lum", ""),
                        r.get("R", ""),
                        r.get("M", ""),
                        r.get("p (g/cm3)", ""),
                        r.get("Lifetime (years)", ""),
                    )
                    for r in rows
                ],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {"count": len(rows), "path": csv_path}


def import_solar_system_csvs(data_dir: str) -> dict:
    """Replace planets, moons, dwarf_planets, and asteroids tables from CSV files in data_dir.

    Validates all four files exist before replacing anything.
    Returns {"planets": N, "moons": N, "dwarf_planets": N, "asteroids": N} or {"error": str}.
    """
    from core.db import get_conn

    files = {
        "planets":      "planetInfo.csv",
        "moons":        "moonInfo.csv",
        "dwarf_planets": "dwarfPlanetInfo.csv",
        "asteroids":    "asteroidsInfo.csv",
    }
    paths = {key: os.path.join(data_dir, fname) for key, fname in files.items()}
    missing = [fname for key, fname in files.items() if not os.path.exists(paths[key])]
    if missing:
        return {"error": f"File(s) not found: {', '.join(missing)}"}

    def _read(path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    try:
        planet_rows      = _read(paths["planets"])
        moon_rows        = _read(paths["moons"])
        dwarf_rows       = _read(paths["dwarf_planets"])
        asteroid_rows    = _read(paths["asteroids"])
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM planets")
            conn.executemany(
                """INSERT INTO planets
                   (planet_name, mass, diameter, period, periastron,
                    semimajor_axis, apastron, eccentricity, moons)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Planet",""), r.get("Mass",""), r.get("Diameter",""),
                  r.get("Period",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Moons",""))
                 for r in planet_rows],
            )

            conn.execute("DELETE FROM moons")
            conn.executemany(
                """INSERT INTO moons
                   (satellite_name, planet_name, diameter_km, mean_radius_km, mass_kg,
                    perigee_km, apogee_km, semimajor_axis_km, eccentricity,
                    period_days, gravity, escape_velocity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Satellite Name",""), r.get("Planet Name",""), r.get("Diameter (km)",""),
                  r.get("Mean Radius (km)",""), r.get("Mass (kg)",""), r.get("Perigee (km)",""),
                  r.get("Apogee (km)",""), r.get("SemiMajor Axis (km)",""), r.get("Eccentricity",""),
                  r.get("Period (days)",""), r.get("Gravity (m/s^2)",""), r.get("Escape Velocity (km/s)",""))
                 for r in moon_rows],
            )

            conn.execute("DELETE FROM dwarf_planets")
            conn.executemany(
                """INSERT INTO dwarf_planets
                   (name, periastron, semimajor_axis, apastron, eccentricity,
                    period, mass, diameter, moons)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Name",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Period",""),
                  r.get("Mass",""), r.get("Diameter",""), r.get("Moons",""))
                 for r in dwarf_rows],
            )

            conn.execute("DELETE FROM asteroids")
            conn.executemany(
                """INSERT INTO asteroids
                   (name, periastron, semimajor_axis, apastron, eccentricity, period, diameter)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Name",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Period",""),
                  r.get("Diameter",""))
                 for r in asteroid_rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {
        "planets":      len(planet_rows),
        "moons":        len(moon_rows),
        "dwarf_planets": len(dwarf_rows),
        "asteroids":    len(asteroid_rows),
    }


# ── Hypatia Catalog ────────────────────────────────────────────────────────────

_HYPATIA_BASE = "https://hypatiacatalog.com/hypatia/api/v2"

# All 104 Hypatia species (incl. ionized) and their names/atomic numbers/categories
# live in core.hypatia_elements — the single source of truth shared with the GUI and CLI.
from core.hypatia_elements import (
    HYPATIA_REQUEST_SYMBOLS,
    SPECIES_BY_SYMBOL,
    SPECIES_ORDER,
)

# The Hypatia server caps the GET request line at ~4094 bytes, so the 104 species can't be
# requested in one call — fetch in chunks small enough to stay well under that limit.
_HYPATIA_COMPOSITION_CHUNK = 30


def _parse_hypatia_star(data: list) -> dict:
    """Parse /star JSON response into a normalized properties dict.

    Field names are confirmed against the live API.  Additional fallback keys
    handle any minor naming variations across API versions.
    """
    if not data:
        return {}
    s = data[0]

    def _f(key, *fallbacks):
        for k in (key,) + fallbacks:
            v = s.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return None

    return {
        "teff":          _f("temperature", "teff", "t_eff"),
        "logg":          _f("logg", "log_g"),
        "spectral_type": s.get("spectral_type") or s.get("spectraltype") or s.get("sptype"),
        "vmag":          _f("vmag", "v_mag"),
        "bmag":          _f("bmag", "b_mag"),
        "bv":            _f("bv", "b_v", "color_bv"),
        "distance_pc":   _f("dist", "distance", "distance_pc"),
        "disk":          s.get("disk") or s.get("disk_membership"),
        "u_vel":         _f("u", "u_vel", "uvel"),
        "v_vel":         _f("v", "v_vel", "vvel"),
        "w_vel":         _f("w", "w_vel", "wvel"),
        "pm_ra":         _f("pm_ra", "pmra", "proper_motion_ra"),
        "pm_dec":        _f("pm_dec", "pmdec", "proper_motion_dec"),
    }


def _parse_hypatia_composition(data: list) -> list:
    """Parse /composition JSON response into a list of element abundance dicts.

    Omits species for which no mean value is available. Preserves the species'
    casing as returned by the API (e.g. "Fe", "Ba_II"), attaches the full element
    name / atomic number / nucleosynthetic-family category from the master table,
    and orders the result by that table's display order.
    """
    results = []

    for item in data:
        el_raw = item.get("element") or item.get("name") or ""
        el = el_raw.strip()
        key = el.lower()

        mean = None
        for k in ("mean", "average", "median"):
            v = item.get(k)
            if v is not None:
                try:
                    mean = float(v)
                    break
                except (TypeError, ValueError):
                    pass
        if mean is None:
            continue

        def _f2(k, *fallbacks):
            for kk in (k,) + fallbacks:
                v = item.get(kk)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
            return None

        n_raw = item.get("n") or item.get("catalog_count") or item.get("num_catalogs")
        try:
            n = int(n_raw) if n_raw is not None else None
        except (TypeError, ValueError):
            n = None
        # The API has no explicit catalog count, but lists per-catalog values in
        # "catalogs_linear" — use its length as the "# Catalogs" value when present.
        if n is None:
            cl = item.get("catalogs_linear")
            if isinstance(cl, dict):
                n = len(cl)

        species = SPECIES_BY_SYMBOL.get(key, {})

        # Hypatia's "plusminus" is the symmetric spread in dex ([X/H]) and is the
        # value the catalog plots as an error bar. The API's own "std" field is the
        # log of the linear-space scatter — it is negative for almost every element
        # and is NOT a usable dex uncertainty, so prefer "plusminus" here.
        results.append({
            "element":  el or species.get("symbol", ""),  # API casing, e.g. "Ba_II"
            "name":     species.get("name", ""),
            "z":        species.get("z"),
            "category": species.get("category", ""),
            "mean":     mean,
            "std":      _f2("plusminus", "std", "sigma", "stdev"),
            "min":      _f2("min", "minimum"),
            "max":      _f2("max", "maximum"),
            "n":        n,
            "_order":   SPECIES_ORDER.get(key, 999),
        })

    results.sort(key=lambda x: x["_order"])
    for r in results:
        del r["_order"]
    return results


def compute_hypatia_data(simbad_result: dict) -> dict:
    """Fetch stellar properties and elemental abundances from Hypatia Catalog API.

    Uses HIP → HD → MAIN_ID from the SIMBAD result for name resolution.
    Returns {"star_name": str, "properties": dict, "abundances": list}
    or {"error": str}.
    """
    import requests

    desig = simbad_result.get("designations", {})
    star_name = (
        desig.get("HIP")
        or desig.get("HD")
        or simbad_result.get("main_id", "")
    )
    if not star_name:
        return {"error": "No usable designation for Hypatia Catalog lookup"}

    # ── /star endpoint ────────────────────────────────────────────────────────
    try:
        def _get_star():
            r = requests.get(
                f"{_HYPATIA_BASE}/star",
                params={"name": [star_name]},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        star_data = _with_retries(_get_star)
    except Exception as e:
        return {"error": _network_error_msg(e, "Hypatia Catalog")}

    if not star_data:
        return {"error": f"No Hypatia data for '{star_name}'"}

    properties = _parse_hypatia_star(star_data)

    # ── /composition endpoint ─────────────────────────────────────────────────
    # All 104 species are requested, but the server caps the GET request line at
    # ~4094 bytes, so they're fetched in chunks and the responses concatenated.
    abundances = []
    try:
        comp_data = []
        for i in range(0, len(HYPATIA_REQUEST_SYMBOLS), _HYPATIA_COMPOSITION_CHUNK):
            chunk = HYPATIA_REQUEST_SYMBOLS[i:i + _HYPATIA_COMPOSITION_CHUNK]
            nch = len(chunk)
            comp_params = {
                "name":      [star_name] * nch,
                "element":   chunk,
                "solarnorm": ["lodders09"] * nch,
            }

            def _get_comp(params=comp_params):
                r = requests.get(
                    f"{_HYPATIA_BASE}/composition",
                    params=params,
                    timeout=30,
                )
                r.raise_for_status()
                return r.json()
            comp_data.extend(_with_retries(_get_comp))
        abundances = _parse_hypatia_composition(comp_data)
    except Exception:
        pass  # return properties with empty abundances rather than failing entirely

    return {
        "star_name":  star_name,
        "properties": properties,
        "abundances": abundances,
    }


def import_honorverse_hyper_csv(csv_path: str) -> dict:
    """Replace honorverse_hyper table with data from csv_path (headerless CSV).

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for line in csv.reader(f):
                if len(line) < 2:
                    continue
                sp_class = line[0].strip().strip('"')
                try:
                    lm = float(line[1])
                except ValueError:
                    continue
                rows.append((sp_class, lm))
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    if not rows:
        return {"error": "No valid rows found in file."}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM honorverse_hyper")
            conn.executemany(
                "INSERT INTO honorverse_hyper (spectral_class, lm) VALUES (?, ?)",
                rows,
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {"count": len(rows), "path": csv_path}


# ── Option 58: Gaia Catalogue of Nearby Stars (GCNS) ─────────────────────────
#
# Ingests the GCNS (Smart et al. 2021) into the isolated `gcns_stars` DB table
# as the astrometric/completeness backbone, with Bayesian distances + their
# uncertainties — data the SIMBAD-built star_systems table lacks. The SIMBAD
# identity layer (spectral type / common name / Johnson V) is attached by an
# exact-key cross-match against star_systems (Gaia source_id → 2MASS → name);
# never fabricated, never positionally guessed. See docs/star-databases.md.

_GCNS_TAP_URL          = "https://dc.g-vo.org/tap"
_GCNS_VERSION          = ("GCNS / Smart et al. 2021 A&A 649 A6 (VizieR J/A+A/649/A6) "
                          "via GAVO gcns.main + gcns.missing_10mas + gcns.resolvedss")
_GCNS_MAXREC           = 400_000   # must exceed the total row count AND the 20k default cap
_GCNS_MAIN_MIN_ROWS    = 330_000   # known 331,312 — floor sits just under to tolerate version drift
_GCNS_MISSING_MIN_ROWS = 1_200     # known 1,259
_GCNS_RESOLVED_MIN_ROWS = 19_000   # known 19,176 resolved pairs
_LY_PER_PC             = 3.26156
_KPC_TO_PC             = 1000.0

_GCNS_MAIN_ADQL = """SELECT source_id, ra, dec, parallax, parallax_error,
       dist_16, dist_50, dist_84,
       phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
       adoptedrv, wd_prob, gcns_prob, name_2mass
  FROM gcns.main"""

_GCNS_MISSING_ADQL = """SELECT main_id, otype, ra, dec, plx_value
  FROM gcns.missing_10mas"""

# gcns.resolvedss is PAIR-keyed: one row per resolved pair, no system identifier.
# source_id1/source_id2 are Gaia EDR3 source_ids; separation in arcsec, proj_sep
# in AU; bin = probable >2-star system; bound = probable gravitationally bound.
_GCNS_RESOLVED_ADQL = """SELECT source_id1, source_id2, separation, mag_diff,
       proj_sep, bin, bound
  FROM gcns.resolvedss"""


def _ni(v):
    """Coerce a TAP value to int, or None if missing/masked."""
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_2mass(s: str) -> str:
    """Normalise a 2MASS designation to its bare coordinate core for joining.

    star_systems stores '2MASS J14294291-6240465'; GCNS name_2mass stores
    '14294291-6240465'. Strip the '2MASS'/'J' prefixes and whitespace so both
    forms compare equal.
    """
    if not s:
        return ""
    s = str(s).strip()
    if s.upper().startswith("2MASS"):
        s = s[5:].strip()
    if s[:1] in ("J", "j"):
        s = s[1:]
    return s.strip()


def _build_simbad_crossmatch():
    """Build exact-match lookup tables from star_systems for the SIMBAD layer.

    Returns (by_gaia, by_2mass, by_name) where each maps a key to a dict of
    {spectral_type, star_name, app_magnitude}. Keys:
      - by_gaia : int Gaia EDR3/DR3 source_id parsed from `designations`
                  (DR2 ids are deliberately excluded — they differ from EDR3/DR3)
      - by_2mass: normalised 2MASS core
      - by_name : exact star_name (used for missing_10mas rows)
    Empty dicts if star_systems is empty or carries no usable keys.
    """
    from core.db import get_conn

    by_gaia, by_2mass, by_name = {}, {}, {}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT star_name, designations, spectral_type, app_magnitude "
            "FROM star_systems"
        ).fetchall()
    except Exception:
        return by_gaia, by_2mass, by_name

    gaia_re  = re.compile(r"Gaia\s+E?DR3\s+(\d+)")  # EDR3 or DR3 only — not DR2
    twomass_re = re.compile(r"2MASS\s+J?\s*([0-9+\-.]+)")

    for r in rows:
        sp   = (r["spectral_type"] or "").strip() or None
        name = (r["star_name"] or "").strip() or None
        vmag = _fval(r["app_magnitude"])
        payload = {"spectral_type": sp, "star_name": name, "app_magnitude": vmag}
        desig = r["designations"] or ""

        m = gaia_re.search(desig)
        if m:
            by_gaia.setdefault(int(m.group(1)), payload)
        tm = twomass_re.search(desig)
        if tm:
            by_2mass.setdefault(_norm_2mass(tm.group(1)), payload)
        if name:
            by_name.setdefault(name, payload)

    return by_gaia, by_2mass, by_name


def _gcns_fetch(adql: str, maxrec: int):
    """Run an async TAP query against GAVO; return the pyvo result set.

    Uses async (1 hr execution window) because the result far exceeds the 20k
    sync cap. Deletes the UWS job afterward. Wrapped in the shared retry/timeout
    helpers. Raises on exhausted retries (caller classifies the error).
    """
    import pyvo

    def _do():
        svc = pyvo.dal.TAPService(_GCNS_TAP_URL)
        job = svc.submit_job(adql, maxrec=maxrec)
        try:
            job.run()
            job.wait(phases={"COMPLETED", "ERROR", "ABORTED"}, timeout=3000.0)
            job.raise_if_error()
            return job.fetch_result()
        finally:
            try:
                job.delete()
            except Exception:
                pass

    with _timeout_ctx(300):
        return _with_retries(_do, retries=3, base_delay=5.0)


def _gcns_check_overflow(result, n_rows: int) -> bool:
    """True if the TAP result was truncated (server OVERFLOW or hit maxrec)."""
    try:
        status = str(getattr(result, "query_status", "") or "")
        if "overflow" in status.lower():
            return True
    except Exception:
        pass
    return n_rows >= _GCNS_MAXREC


def _gcns_build_systems(resolved_rows, gcns_star_ids):
    """Derive resolved systems from gcns.resolvedss pair rows.

    The source table has no system id — each row is a resolved PAIR
    (source_id1, source_id2). Systems are connected components over the pair
    graph (union-find). system_id is synthetic and deterministic: components are
    sorted by their smallest member source_id and numbered from 1.

    `gcns_star_ids` is the set of source_ids present in gcns_stars (i.e. the
    gcns.main ids), used to flag which members link to an existing gcns_stars row.

    Returns (systems_rows, members_rows, pair_rows, sid_info, n_multi,
    n_members_in_stars):
      - systems_rows: tuples for gcns_systems
      - members_rows: tuples for gcns_system_members
      - pair_rows:    tuples for gcns_system_pairs
      - sid_info:     {source_id: (system_id, n_components)} for gcns_stars enrich
      - n_multi:      systems with n_components > 2
      - n_members_in_stars: members whose source_id is in gcns_stars
    """
    from collections import defaultdict

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pairs = []
    for row in resolved_rows:
        s1 = _ni(row["source_id1"])
        s2 = _ni(row["source_id2"])
        if s1 is None or s2 is None:
            continue
        union(s1, s2)
        pairs.append({
            "s1":   s1,
            "s2":   s2,
            "sep":  _fval(row["separation"]),
            "magd": _fval(row["mag_diff"]),
            "proj": _fval(row["proj_sep"]),
            "bin":  _ni(row["bin"]),
            "bound": _ni(row["bound"]),
        })

    # Group source_ids into connected components.
    comps = defaultdict(set)
    for x in list(parent):
        comps[find(x)].add(x)

    # Deterministic system_id: order components by smallest member id.
    comp_list = sorted(comps.values(), key=min)
    sid_to_sysid = {}
    n_components = {}
    for i, members in enumerate(comp_list, start=1):
        n_components[i] = len(members)
        for sid in members:
            sid_to_sysid[sid] = i

    # Members + per-system in-gcns_stars counts.
    members_rows = []
    sys_in_stars = defaultdict(int)
    n_members_in_stars = 0
    for sid, sysid in sid_to_sysid.items():
        in_stars = 1 if sid in gcns_star_ids else 0
        members_rows.append((sysid, sid, in_stars))
        sys_in_stars[sysid] += in_stars
        n_members_in_stars += in_stars

    # Pairs grouped per system for aggregates.
    pair_rows = []
    sys_pairs = defaultdict(list)
    for p in pairs:
        sysid = sid_to_sysid[p["s1"]]
        sys_pairs[sysid].append(p)
        pair_rows.append((sysid, p["s1"], p["s2"], p["sep"], p["magd"],
                          p["proj"], p["bin"], p["bound"]))

    systems_rows = []
    n_multi = 0
    for sysid in sorted(n_components):
        nc = n_components[sysid]
        if nc > 2:
            n_multi += 1
        ps = sys_pairs.get(sysid, [])
        projs  = [p["proj"]  for p in ps if p["proj"]  is not None]
        bins   = [p["bin"]   for p in ps if p["bin"]   is not None]
        bounds = [p["bound"] for p in ps if p["bound"] is not None]
        systems_rows.append((
            sysid,
            nc,
            len(ps),
            1 if any(b == 1 for b in bins) else 0,
            1 if any(b == 1 for b in bounds) else 0,
            1 if (bounds and all(b == 1 for b in bounds)) else 0,
            max(projs) if projs else None,
            min(projs) if projs else None,
            sys_in_stars[sysid],
        ))

    sid_info = {sid: (sysid, n_components[sysid]) for sid, sysid in sid_to_sysid.items()}
    return systems_rows, members_rows, pair_rows, sid_info, n_multi, n_members_in_stars


def compute_gcns_ingest(progress_callback=None) -> dict:
    """Pull the GCNS into the gcns_stars table (replace-in-place) with check gates.

    Flow (validate-before-destroy — a short/truncated download leaves the
    existing tables intact):
      1. async-fetch gcns.main, gcns.missing_10mas, and gcns.resolvedss into
         memory (one snapshot)
      2. Gate 1 (per table, BEFORE any DB write): fail on OVERFLOW or row count
         below the configured floor
      3. transform (kpc->pc, ly, SIMBAD cross-match) + derive resolved systems
         (connected components over the resolvedss pair graph)
      4. replace-in-place: DELETE + bulk INSERT of gcns_stars, gcns_systems,
         gcns_system_members, gcns_system_pairs in ONE transaction
      5. Gate 2 (post-commit): assert final counts meet floors; record provenance

    Returns a stats dict on success or {"error": str}.
    """
    from datetime import datetime
    from core.db import get_conn

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    # ── 1. Fetch ────────────────────────────────────────────────────────────
    _progress("Querying GAVO TAP for gcns.main (331,312 rows; this takes a few minutes)…")
    try:
        main_res = _gcns_fetch(_GCNS_MAIN_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.main)")}
    main_rows = list(main_res)
    n_main = len(main_rows)
    _progress(f"gcns.main returned {n_main:,} rows.")

    # ── 2. Gate 1 (gcns.main) — before touching the DB ──────────────────────
    if _gcns_check_overflow(main_res, n_main):
        return {"error": ("gcns.main result was TRUNCATED (TAP OVERFLOW / hit "
                          f"maxrec={_GCNS_MAXREC:,}). Aborted before writing; "
                          "existing gcns_stars table left intact.")}
    if n_main < _GCNS_MAIN_MIN_ROWS:
        return {"error": (f"gcns.main returned only {n_main:,} rows (expected "
                          f">= {_GCNS_MAIN_MIN_ROWS:,}). Likely an incomplete "
                          "download; aborted before writing.")}

    _progress("Querying GAVO TAP for gcns.missing_10mas…")
    try:
        miss_res = _gcns_fetch(_GCNS_MISSING_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.missing_10mas)")}
    miss_rows = list(miss_res)
    n_miss = len(miss_rows)
    _progress(f"gcns.missing_10mas returned {n_miss:,} rows.")

    if _gcns_check_overflow(miss_res, n_miss):
        return {"error": ("gcns.missing_10mas result was TRUNCATED. Aborted "
                          "before writing; existing gcns_stars left intact.")}
    if n_miss < _GCNS_MISSING_MIN_ROWS:
        return {"error": (f"gcns.missing_10mas returned only {n_miss:,} rows "
                          f"(expected >= {_GCNS_MISSING_MIN_ROWS:,}); aborted "
                          "before writing.")}

    _progress("Querying GAVO TAP for gcns.resolvedss (resolved multiples)…")
    try:
        resolved_res = _gcns_fetch(_GCNS_RESOLVED_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.resolvedss)")}
    resolved_rows = list(resolved_res)
    n_resolved = len(resolved_rows)
    _progress(f"gcns.resolvedss returned {n_resolved:,} pairs.")

    if _gcns_check_overflow(resolved_res, n_resolved):
        return {"error": ("gcns.resolvedss result was TRUNCATED. Aborted before "
                          "writing; existing GCNS tables left intact.")}
    if n_resolved < _GCNS_RESOLVED_MIN_ROWS:
        return {"error": (f"gcns.resolvedss returned only {n_resolved:,} pairs "
                          f"(expected >= {_GCNS_RESOLVED_MIN_ROWS:,}); aborted "
                          "before writing.")}

    # ── 3. Transform + cross-match ──────────────────────────────────────────
    _progress("Cross-matching against star_systems (SIMBAD layer)…")
    by_gaia, by_2mass, by_name = _build_simbad_crossmatch()

    # Derive resolved systems (connected components over the resolvedss pairs).
    # Membership links by Gaia source_id; the in_gcns_stars flag is computed
    # against the gcns.main source_ids (missing_10mas rows have no source_id).
    _progress("Deriving resolved systems (connected components)…")
    main_source_ids = {sid for sid in (_ni(r["source_id"]) for r in main_rows)
                       if sid is not None}
    (systems_rows, members_rows, pair_rows, sid_info,
     n_multi, n_members_in_stars) = _gcns_build_systems(resolved_rows, main_source_ids)
    n_systems = len(systems_rows)

    matched = 0
    insert_rows = []

    for row in main_rows:
        sid   = _ni(row["source_id"])
        d50   = _fval(row["dist_50"])
        d16   = _fval(row["dist_16"])
        d84   = _fval(row["dist_84"])
        dist_pc    = d50 * _KPC_TO_PC if d50 is not None else None
        dist_lo_pc = d16 * _KPC_TO_PC if d16 is not None else None
        dist_hi_pc = d84 * _KPC_TO_PC if d84 is not None else None
        ly = dist_pc * _LY_PER_PC if dist_pc is not None else None

        sim = None
        if sid is not None and sid in by_gaia:
            sim = by_gaia[sid]
        else:
            key2 = _norm_2mass(row["name_2mass"])
            if key2 and key2 in by_2mass:
                sim = by_2mass[key2]
        if sim is not None:
            matched += 1

        info = sid_info.get(sid) if sid is not None else None
        system_id    = info[0] if info else None
        n_components = info[1] if info else None

        insert_rows.append((
            sid,
            _fval(row["ra"]), _fval(row["dec"]),
            _fval(row["parallax"]), _fval(row["parallax_error"]),
            dist_pc, dist_lo_pc, dist_hi_pc, ly,
            _fval(row["phot_g_mean_mag"]), _fval(row["phot_bp_mean_mag"]),
            _fval(row["phot_rp_mean_mag"]),
            _fval(row["adoptedrv"]), _fval(row["wd_prob"]), _fval(row["gcns_prob"]),
            sim["spectral_type"] if sim else None,
            sim["star_name"] if sim else None,
            sim["app_magnitude"] if sim else None,
            1,                       # in_gcns
            1 if sim else 0,         # in_simbad
            "gcns_bayesian",
            "main",
            system_id,
            n_components,
        ))

    # missing_10mas: parallax-only objects Gaia EDR3 missed — no source_id, no
    # Bayesian distance, no Gaia photometry. Distance via 1/plx inversion, flagged.
    for row in miss_rows:
        plx = _fval(row["plx_value"])
        dist_pc = (1000.0 / plx) if (plx and plx > 0) else None
        ly = dist_pc * _LY_PER_PC if dist_pc is not None else None
        main_id = (str(row["main_id"]).strip() if row["main_id"] is not None else None)

        sim = by_name.get(main_id) if main_id else None
        if sim is not None:
            matched += 1

        insert_rows.append((
            None,                                  # gaia_source_id
            _fval(row["ra"]), _fval(row["dec"]),
            plx, None,                             # parallax, parallax_error
            dist_pc, None, None, ly,               # dist_pc, lo, hi, ly
            None, None, None,                      # G, BP, RP
            None, None, None,                      # rv, wd_prob, astrom_reliable
            sim["spectral_type"] if sim else None,
            sim["star_name"] if sim else main_id,  # keep GCNS main_id as the name
            sim["app_magnitude"] if sim else None,
            1,                                     # in_gcns
            1 if sim else 0,                       # in_simbad
            "gcns_missing_plx_inversion",
            "missing_10mas",
            None,                                  # system_id (no source_id to join)
            None,                                  # n_components
        ))

    # ── 4. Replace-in-place (one transaction) ───────────────────────────────
    _progress(f"Writing {len(insert_rows):,} stars and {n_systems:,} resolved "
              "systems…")
    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM gcns_stars")
            conn.execute("DELETE FROM gcns_systems")
            conn.execute("DELETE FROM gcns_system_members")
            conn.execute("DELETE FROM gcns_system_pairs")
            conn.executemany(
                """INSERT OR IGNORE INTO gcns_stars
                   (gaia_source_id, ra, dec, parallax, parallax_error,
                    dist_pc, dist_lo_pc, dist_hi_pc, light_years,
                    phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
                    rv_kms, wd_prob, astrom_reliable_prob,
                    spectral_type, star_name, app_magnitude,
                    in_gcns, in_simbad, distance_method, gcns_table,
                    system_id, n_components)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                insert_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_systems
                   (system_id, n_components, n_pairs, any_bin, any_bound,
                    all_bound, max_proj_sep_au, min_proj_sep_au, n_in_gcns_stars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                systems_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_system_members
                   (system_id, gaia_source_id, in_gcns_stars)
                   VALUES (?, ?, ?)""",
                members_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_system_pairs
                   (system_id, source_id1, source_id2, separation_arcsec,
                    mag_diff, proj_sep_au, bin, bound)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                pair_rows,
            )
    except Exception as e:
        return {"error": f"Could not write GCNS tables: {e}"}

    # ── 5. Gate 2 (post-commit) + provenance ────────────────────────────────
    final = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    if final < _GCNS_MAIN_MIN_ROWS:
        return {"error": (f"Post-commit check failed: gcns_stars holds {final:,} "
                          f"rows (expected >= {_GCNS_MAIN_MIN_ROWS:,}). The table "
                          "may be incomplete — investigate before relying on it.")}
    final_pairs = conn.execute("SELECT COUNT(*) FROM gcns_system_pairs").fetchone()[0]
    if final_pairs < _GCNS_RESOLVED_MIN_ROWS:
        return {"error": (f"Post-commit check failed: gcns_system_pairs holds "
                          f"{final_pairs:,} rows (expected >= "
                          f"{_GCNS_RESOLVED_MIN_ROWS:,}). The resolved-systems "
                          "tables may be incomplete — investigate before relying "
                          "on them.")}

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "snapshot_date":         snapshot_date,
        "gcns_version":          _GCNS_VERSION,
        "gcns_main_count":       str(n_main),
        "gcns_missing_count":    str(n_miss),
        "total_count":           str(final),
        "simbad_matched":        str(matched),
        "gcns_resolved_pairs":   str(n_resolved),
        "gcns_systems_count":    str(n_systems),
        "gcns_systems_multi":    str(n_multi),
        "gcns_members_in_stars": str(n_members_in_stars),
    }
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO gcns_meta (key, value) VALUES (?, ?)",
            list(meta.items()),
        )

    _progress(f"Done — {final:,} GCNS rows ({matched:,} SIMBAD-matched); "
              f"{n_systems:,} resolved systems ({n_multi:,} with >2 components).")
    return {
        "total_rows":       final,
        "main_count":       n_main,
        "missing_count":    n_miss,
        "simbad_matched":   matched,
        "resolved_pairs":   n_resolved,
        "systems_count":    n_systems,
        "systems_multi":    n_multi,
        "members_in_stars": n_members_in_stars,
        "snapshot_date":    snapshot_date,
        "gcns_version":     _GCNS_VERSION,
    }


def _gcns_meta_dict() -> dict:
    """Return the gcns_meta key/value pairs as a dict (empty if unbuilt)."""
    from core.db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM gcns_meta").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


_GCNS_ROW_COLS = [
    "gaia_source_id", "ra", "dec", "parallax", "parallax_error",
    "dist_pc", "dist_lo_pc", "dist_hi_pc", "light_years",
    "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag",
    "rv_kms", "wd_prob", "astrom_reliable_prob",
    "spectral_type", "star_name", "app_magnitude",
    "in_gcns", "in_simbad", "distance_method", "gcns_table",
    "system_id", "n_components",
]


def _gcns_row_to_dict(row) -> dict:
    """Convert a gcns_stars DB row to the public JSON shape (snake_case keys)."""
    d = {c: row[c] for c in _GCNS_ROW_COLS}
    d["in_gcns"]   = bool(row["in_gcns"])
    d["in_simbad"] = bool(row["in_simbad"])
    return d


def compute_gcns_within_sol(limit_ly: float) -> dict:
    """All GCNS stars within limit_ly light years of Sol (Bayesian distances).

    Reads the gcns_stars DB table only — no network. Returns
    {limit_ly, count, snapshot_date, gcns_version, stars[]} or {"error": str}.
    Each star carries heliocentric x/y/z (ly) for map parity with stars-within-sol.
    """
    import math as _math
    from core.db import get_conn

    if limit_ly is None or limit_ly <= 0:
        return {"error": "Distance limit must be greater than 0."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        "WHERE light_years IS NOT NULL AND light_years <= ? "
        "ORDER BY light_years ASC",
        (limit_ly,),
    ).fetchall()

    stars = []
    for row in rows:
        d = _gcns_row_to_dict(row)
        ra, dec, ly = row["ra"], row["dec"], row["light_years"]
        if ra is not None and dec is not None and ly is not None:
            rr, dr = _math.radians(ra), _math.radians(dec)
            d["x"] = ly * _math.cos(dr) * _math.cos(rr)
            d["y"] = ly * _math.cos(dr) * _math.sin(rr)
            d["z"] = ly * _math.sin(dr)
        else:
            d["x"] = d["y"] = d["z"] = None
        stars.append(d)

    meta = _gcns_meta_dict()
    return {
        "limit_ly":      limit_ly,
        "count":         len(stars),
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "stars":         stars,
    }


def compute_gcns_by_source_id(source_id: int) -> dict:
    """Single GCNS row by Gaia EDR3/DR3 source_id (the join key). No network.

    Returns {snapshot_date, gcns_version, star} or {"error": str}.
    """
    from core.db import get_conn

    sid = _ni(source_id)
    if sid is None:
        return {"error": "source_id must be an integer Gaia EDR3/DR3 id."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    row = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars WHERE gaia_source_id = ?",
        (sid,),
    ).fetchone()
    if row is None:
        return {"error": f"No GCNS source found with source_id {sid}."}

    meta = _gcns_meta_dict()
    return {
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "star":          _gcns_row_to_dict(row),
    }


def _gcns_bool(v):
    """0/1/None -> bool/None (membership/pair flags may be NULL)."""
    return bool(v) if v is not None else None


def compute_gcns_system(source_id: int) -> dict:
    """Resolved multiple-star system containing a Gaia source_id. No network.

    Looks up which derived resolved system (connected component of gcns.resolvedss
    pairs) the component belongs to, then returns the system record, every member's
    source_id with a thin summary joined from gcns_stars where available, and the
    raw pair edges. A source_id that is in no resolved system (a single/unresolved
    object) returns {"error": ...}.

    Returns {snapshot_date, gcns_version, query_source_id, system} or {"error": str}.
    """
    from core.db import get_conn

    sid = _ni(source_id)
    if sid is None:
        return {"error": "source_id must be an integer Gaia EDR3/DR3 id."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_systems").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_systems table: {e}"}
    if total == 0:
        return {"error": "gcns_systems table is empty — run option 58 (Import GCNS Data) first."}

    mrow = conn.execute(
        "SELECT system_id FROM gcns_system_members WHERE gaia_source_id = ?",
        (sid,),
    ).fetchone()
    if mrow is None:
        return {"error": (f"Gaia source_id {sid} is not part of any GCNS resolved "
                          "system (single or unresolved object).")}
    sysid = mrow["system_id"]

    srow = conn.execute(
        """SELECT system_id, n_components, n_pairs, any_bin, any_bound, all_bound,
                  max_proj_sep_au, min_proj_sep_au, n_in_gcns_stars
           FROM gcns_systems WHERE system_id = ?""",
        (sysid,),
    ).fetchone()

    members = []
    for m in conn.execute(
        "SELECT gaia_source_id, in_gcns_stars FROM gcns_system_members "
        "WHERE system_id = ? ORDER BY gaia_source_id",
        (sysid,),
    ).fetchall():
        msid = m["gaia_source_id"]
        star = conn.execute(
            "SELECT star_name, spectral_type, dist_pc, light_years "
            "FROM gcns_stars WHERE gaia_source_id = ?",
            (msid,),
        ).fetchone()
        members.append({
            "gaia_source_id": msid,
            "in_gcns_stars":  _gcns_bool(m["in_gcns_stars"]),
            "is_query":       msid == sid,
            "star_name":      star["star_name"]     if star else None,
            "spectral_type":  star["spectral_type"] if star else None,
            "dist_pc":        star["dist_pc"]        if star else None,
            "light_years":    star["light_years"]    if star else None,
        })

    pairs = [{
        "source_id1":        p["source_id1"],
        "source_id2":        p["source_id2"],
        "separation_arcsec": p["separation_arcsec"],
        "mag_diff":          p["mag_diff"],
        "proj_sep_au":       p["proj_sep_au"],
        "bin":               _gcns_bool(p["bin"]),
        "bound":             _gcns_bool(p["bound"]),
    } for p in conn.execute(
        "SELECT source_id1, source_id2, separation_arcsec, mag_diff, proj_sep_au, "
        "bin, bound FROM gcns_system_pairs WHERE system_id = ? ORDER BY proj_sep_au",
        (sysid,),
    ).fetchall()]

    meta = _gcns_meta_dict()
    return {
        "snapshot_date":   meta.get("snapshot_date"),
        "gcns_version":    meta.get("gcns_version"),
        "query_source_id": sid,
        "system": {
            "system_id":       srow["system_id"],
            "n_components":    srow["n_components"],
            "n_pairs":         srow["n_pairs"],
            "any_bin":         _gcns_bool(srow["any_bin"]),
            "any_bound":       _gcns_bool(srow["any_bound"]),
            "all_bound":       _gcns_bool(srow["all_bound"]),
            "max_proj_sep_au": srow["max_proj_sep_au"],
            "min_proj_sep_au": srow["min_proj_sep_au"],
            "n_in_gcns_stars": srow["n_in_gcns_stars"],
            "members":         members,
            "pairs":           pairs,
        },
    }


# ── GCNS-backed pairwise calculators (distance / travel-time / within-star) ────
#
# GCNS-sourced versions of the SIMBAD-based calculators in core/calculators.py.
# Coordinates and Bayesian distances come from the gcns_stars table; the existing
# SIMBAD-based subcommands are left unchanged. _to_cartesian / _fmt_ra / _fmt_dec /
# format_travel_time / HOURS_PER_JULIAN_YEAR are imported lazily from core.calculators
# inside the function bodies (neither module imports the other at top level).

_GCNS_GAIA_ID_RE = re.compile(r"Gaia\s+E?DR3\s+(\d+)")  # EDR3 or DR3 only — same source_id


def _resolve_gcns_row(*, star=None, source_id=None) -> dict:
    """Resolve a star to a single gcns_stars row, by Gaia source_id or by name.

    Exactly one of `star` / `source_id` must be supplied.

    Resolution order:
      - source_id (offline): direct gcns_stars fetch by gaia_source_id. missing_10mas
        rows have NULL gaia_source_id and are therefore not addressable this way.
      - star (network): SIMBAD lookup → extract the Gaia EDR3/DR3 id from its
        designations → fetch by id. If SIMBAD itself errors, that error propagates.
        If the id is absent from gcns_stars, fall through to an exact star_name match
        (case-insensitive) — this is how missing_10mas rows (Alpha Cen A/B, …) resolve.

    Returns the bare _gcns_row_to_dict shape, or {"error": str}. Never falls back to
    the SIMBAD star_systems table; an unmatched star is an error, not a silent
    substitution.
    """
    from core.db import get_conn

    if (star is None) == (source_id is None):
        return {"error": "Supply exactly one of star or source_id."}

    # ── source_id path (offline) ──────────────────────────────────────────────
    if source_id is not None:
        r = compute_gcns_by_source_id(source_id)
        if "error" in r:
            return r
        return r["star"]

    # ── star path (network via SIMBAD) ────────────────────────────────────────
    simbad = compute_simbad_lookup(star)
    if "error" in simbad:
        return simbad  # network / no-match — fatal, do not fall back

    gaia_raw = (simbad.get("designations") or {}).get("Gaia EDR3")
    if gaia_raw:
        m = _GCNS_GAIA_ID_RE.search(str(gaia_raw))
        if m:
            r = compute_gcns_by_source_id(int(m.group(1)))
            if "error" not in r:
                return r["star"]
            # id not in gcns_stars — fall through to name match (do not propagate)

    # ── name fallback (missing_10mas and any id-miss) ─────────────────────────
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        "WHERE star_name = ? COLLATE NOCASE",
        (str(star).strip(),),
    ).fetchall()
    if len(rows) == 1:
        return _gcns_row_to_dict(rows[0])
    if len(rows) > 1:
        cands = []
        for row in rows:
            sid = row["gaia_source_id"]
            cands.append(str(sid) if sid is not None
                         else f"<missing_10mas: {row['star_name']}>")
        return {"error": (f"'{star}' is ambiguous in the GCNS catalog — matches "
                          f"{len(rows)} rows: {', '.join(cands)}. Query by --id instead.")}

    return {"error": (f"'{star}' is not in the GCNS catalog "
                      "(no Gaia EDR3 id or name match).")}


def _gcns_endpoint_xyz(row, label):
    """(_to_cartesian of a resolved GCNS row, or an error dict). Guards null coords."""
    from core.calculators import _to_cartesian

    ra, dec, ly = row.get("ra"), row.get("dec"), row.get("light_years")
    if ra is None or dec is None or ly is None:
        name = row.get("star_name") or row.get("gaia_source_id") or label
        return None, {"error": f"GCNS row for {name} has incomplete coordinates "
                               "(ra/dec/light_years); cannot compute a 3D position."}
    return _to_cartesian(ra, dec, ly), None


def _gcns_info_block(row):
    """A resolved GCNS row plus its sexagesimal ra_hms / dec_dms (mirrors *_info)."""
    from core.calculators import _fmt_ra, _fmt_dec

    info = dict(row)
    info["ra_hms"]  = _fmt_ra(row["ra"])
    info["dec_dms"] = _fmt_dec(row["dec"])
    return info


def compute_gcns_distance(star1=None, id1=None, star2=None, id2=None) -> dict:
    """3D Euclidean distance in light years between two GCNS stars.

    Each endpoint accepts a name (star1/star2, via SIMBAD) or a Gaia source_id
    (id1/id2, offline). Mirrors compute_distance_between_stars' output, plus the
    GCNS provenance fields in each endpoint info block and snapshot_date/gcns_version
    at top level.

    Returns {star1_info, star2_info, distance_ly, distance_au, snapshot_date,
    gcns_version} or {"error": str}.
    """
    s1 = _resolve_gcns_row(star=star1, source_id=id1)
    if "error" in s1:
        return s1
    s2 = _resolve_gcns_row(star=star2, source_id=id2)
    if "error" in s2:
        return s2

    xyz1, err = _gcns_endpoint_xyz(s1, "star1")
    if err:
        return err
    xyz2, err = _gcns_endpoint_xyz(s2, "star2")
    if err:
        return err

    (x1, y1, z1), (x2, y2, z2) = xyz1, xyz2
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    meta = _gcns_meta_dict()
    return {
        "star1_info":    _gcns_info_block(s1),
        "star2_info":    _gcns_info_block(s2),
        "distance_ly":   distance_ly,
        "distance_au":   distance_ly * 63241.077 if distance_ly < 0.5 else None,
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
    }


def compute_gcns_travel_time(star1=None, id1=None, star2=None, id2=None,
                             ly_hr=None, times_c=None) -> dict:
    """GCNS-backed travel time between two stars. Supply exactly one of ly_hr/times_c.

    Distance comes from the GCNS census (see compute_gcns_distance); the velocity
    conversion and travel-time formatting mirror compute_travel_time_between_stars.

    Returns {origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours,
    travel_time_str, snapshot_date, gcns_version} or {"error": str}.
    """
    from core.calculators import HOURS_PER_JULIAN_YEAR, format_travel_time

    if ly_hr is None and times_c is None:
        return {"error": "Must supply ly_hr or times_c."}
    if ly_hr is not None and times_c is not None:
        return {"error": "Supply only one of ly_hr or times_c."}

    s1 = _resolve_gcns_row(star=star1, source_id=id1)
    if "error" in s1:
        return s1
    s2 = _resolve_gcns_row(star=star2, source_id=id2)
    if "error" in s2:
        return s2

    xyz1, err = _gcns_endpoint_xyz(s1, "origin")
    if err:
        return err
    xyz2, err = _gcns_endpoint_xyz(s2, "destination")
    if err:
        return err

    (x1, y1, z1), (x2, y2, z2) = xyz1, xyz2
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    if ly_hr is not None:
        v_ly_hr   = ly_hr
        v_times_c = ly_hr * HOURS_PER_JULIAN_YEAR
    else:
        v_times_c = times_c
        v_ly_hr   = times_c / HOURS_PER_JULIAN_YEAR

    if v_ly_hr <= 0:
        return {"error": "Velocity must be greater than 0."}

    total_hours = distance_ly / v_ly_hr

    meta = _gcns_meta_dict()
    return {
        "origin_info":     _gcns_info_block(s1),
        "dest_info":       _gcns_info_block(s2),
        "distance_ly":     distance_ly,
        "ly_hr":           v_ly_hr,
        "times_c":         v_times_c,
        "total_hours":     total_hours,
        "travel_time_str": format_travel_time(total_hours),
        "snapshot_date":   meta.get("snapshot_date"),
        "gcns_version":    meta.get("gcns_version"),
    }


def compute_gcns_stars_within_star(star=None, source_id=None, limit_ly=None) -> dict:
    """All GCNS stars within limit_ly light years of a center star (Bayesian distances).

    The center is resolved by name (SIMBAD) or Gaia source_id (offline). The center
    itself is excluded precisely — by gaia_source_id when it has one, plus a Distance
    < 1e-9 exact-self skip for a missing_10mas center (no id) — so Gaia-resolved close
    companions remain in the results.

    Returns {center, center_x, center_y, center_z, limit_ly, count, snapshot_date,
    gcns_version, stars[]} (each star = gcns-within-sol row shape + 'Distance') or
    {"error": str}.
    """
    from core.calculators import _to_cartesian
    from core.db import get_conn

    if limit_ly is None or limit_ly <= 0:
        return {"error": "Distance limit must be greater than 0."}

    center = _resolve_gcns_row(star=star, source_id=source_id)
    if "error" in center:
        return center

    center_xyz, err = _gcns_endpoint_xyz(center, "center")
    if err:
        return err
    cx, cy, cz = center_xyz
    center_ly  = center["light_years"]
    center_sid = center.get("gaia_source_id")

    conn = get_conn()
    # Radial pre-filter: 3D separation >= |radial difference|, so anything outside
    # [center_ly - limit, center_ly + limit] cannot be within limit_ly. Lossless.
    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        "WHERE light_years IS NOT NULL AND light_years BETWEEN ? AND ?",
        (center_ly - limit_ly, center_ly + limit_ly),
    ).fetchall()

    matches = []
    for row in rows:
        ra, dec, ly = row["ra"], row["dec"], row["light_years"]
        if ra is None or dec is None or ly is None:
            continue
        if center_sid is not None and row["gaia_source_id"] == center_sid:
            continue  # the center's own row (precise exclusion)
        x, y, z = _to_cartesian(ra, dec, ly)
        dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
        if dist < 1e-9:
            continue  # exact self (covers a no-id missing_10mas center)
        if dist <= limit_ly:
            d = _gcns_row_to_dict(row)
            d["x"], d["y"], d["z"] = x, y, z
            d["Distance"] = dist
            matches.append(d)

    matches.sort(key=lambda r: r["Distance"])

    center_out = dict(center)
    center_out["x"], center_out["y"], center_out["z"] = cx, cy, cz

    meta = _gcns_meta_dict()
    return {
        "center":        center_out,
        "center_x":      cx,
        "center_y":      cy,
        "center_z":      cz,
        "limit_ly":      limit_ly,
        "count":         len(matches),
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "stars":         matches,
    }
