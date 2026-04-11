# core/databases.py — Star database query functions (SIMBAD, NASA, HWC, OEC, EU, Mission Exocat)
# Phase C: compute_simbad_lookup() added.
# Phase D: remaining query functions added.


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

    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("sp_type", "plx_value", "V", "mesfe_h")

    try:
        result = custom_simbad.query_object(star_name)
        ids_result = Simbad.query_objectids(star_name)
    except Exception as e:
        return {"error": str(e)}

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
