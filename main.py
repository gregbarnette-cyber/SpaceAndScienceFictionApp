#!/usr/bin/env python3
"""Space and Science Fiction App"""

import csv
import math
import os
import re
import sys

import requests
from astroquery.simbad import Simbad


# ─── SIMBAD Star Query ────────────────────────────────────────────────────────

def query_star():
    """Query SIMBAD astronomical database for star information."""
    os.system("cls" if os.name == "nt" else "clear")
    designation = input(
        "\nEnter star designation (e.g., 'Vega', 'HD 209458', 'HIP 27989'): "
    ).strip()

    if not designation:
        print("No designation entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"\nQuerying SIMBAD for '{designation}'...\n")

    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("sp_type", "plx_value", "V", "mesfe_h")

    try:
        result = custom_simbad.query_object(designation)
        ids_result = Simbad.query_objectids(designation)

        if result is None:
            print(f"No results found for '{designation}'.")
            input("\nPress Enter to Return to the Main Menu")
            return

        designations = _parse_designations(result, ids_result)
        _display_results(result, designations)

    except Exception as e:
        print(f"Error querying SIMBAD: {e}")

    input("\nPress Enter to Return to the Main Menu")


def _parse_designations(result, ids_result):
    """Extract and organise star designations from SIMBAD results."""
    keys_order = [
        "MAIN_ID", "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
        "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
        "TIC", "Gaia EDR3", "2MASS",
    ]
    designations = {k: None for k in keys_order}

    if result is not None and "main_id" in result.colnames:
        designations["MAIN_ID"] = str(result["main_id"][0])

    if ids_result is None:
        return designations

    # Ordered so more-specific prefixes are checked before shorter ones
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

    for row in ids_result:
        id_str = str(row["id"]).strip()
        for prefix, key in prefix_map:
            if id_str.startswith(prefix) and designations[key] is None:
                designations[key] = id_str
                break

    return designations


def _safe_get(row, col_names, col):
    """Return a column value, or None if missing/masked/blank."""
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


def _display_results(result, designations):
    """Print formatted star information."""
    row = result[0]
    col_names = result.colnames

    # ── Designations ──────────────────────────────────────────────────────────
    keys_order = [
        "MAIN_ID", "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
        "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
        "TIC", "Gaia EDR3", "2MASS",
    ]
    desig_list = [str(designations[k]) for k in keys_order if designations[k]]

    desig_str = ", ".join(desig_list) if desig_list else "N/A"
    sep_width = len(desig_str)
    print("=" * sep_width)
    print("STAR DESIGNATIONS:")
    print(desig_str)
    print("=" * sep_width)
    print()

    # ── Field extraction ──────────────────────────────────────────────────────
    ra  = str(_safe_get(row, col_names, "ra")  or "N/A")
    dec = str(_safe_get(row, col_names, "dec") or "N/A")

    sp_raw = _safe_get(row, col_names, "sp_type")
    sp_type = str(sp_raw) if sp_raw is not None else "N/A"

    plx_raw = _safe_get(row, col_names, "plx_value")
    if plx_raw is not None:
        try:
            plx_f   = float(plx_raw)
            plx     = str(round(plx_f, 4))
            if plx_f > 0:
                parsecs = str(round(1000.0 / plx_f, 4))
                ly      = str(round(1000.0 / plx_f * 3.26156, 4))
            else:
                parsecs = ly = "N/A"
        except (ValueError, ZeroDivisionError):
            plx = parsecs = ly = "N/A"
    else:
        plx = parsecs = ly = "N/A"

    temp_raw = _safe_get(row, col_names, "mesfe_h.teff")
    temp = f"{int(float(temp_raw))} K" if temp_raw is not None else "N/A"

    vmag_raw = _safe_get(row, col_names, "V")
    vmag = str(round(float(vmag_raw), 3)) if vmag_raw is not None else "N/A"

    # ── Table ─────────────────────────────────────────────────────────────────
    headers = [
        "Spectral Type", "Parallax (mas)", "Distance (pc)", "Distance (ly)",
        "Temperature", "RA", "DEC", "App. Magnitude (V)",
    ]
    values = [sp_type, plx, parsecs, ly, temp, ra, dec, vmag]

    col_widths = [max(len(h), len(v)) + 2 for h, v in zip(headers, values)]

    sep        = "+" + "+".join("-" * w for w in col_widths) + "+"
    header_row = "|" + "|".join(h.center(w) for h, w in zip(headers, col_widths)) + "|"
    value_row  = "|" + "|".join(v.center(w) for v, w in zip(values,  col_widths)) + "|"

    print(sep)
    print(header_row)
    print(sep)
    print(value_row)
    print(sep)
    print()


# ─── NASA Exoplanet Archive Query ─────────────────────────────────────────────

def query_exoplanets():
    """Query NASA Exoplanet Archive (pscomppars) for a star's exoplanet data."""
    os.system("cls" if os.name == "nt" else "clear")
    designation = input(
        "\nEnter star designation (e.g., 'Tau Ceti', 'HD 10700', 'HIP 8102'): "
    ).strip()

    if not designation:
        print("No designation entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── SIMBAD lookup ─────────────────────────────────────────────────────────
    print(f"\nQuerying SIMBAD for '{designation}'...\n")
    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("sp_type", "plx_value", "V", "mesfe_h")

    try:
        simbad_result = custom_simbad.query_object(designation)
        ids_result    = Simbad.query_objectids(designation)
    except Exception as e:
        print(f"Error querying SIMBAD: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if simbad_result is None:
        print(f"No results found in SIMBAD for '{designation}'.")
        input("\nPress Enter to Return to the Main Menu")
        return

    designations = _parse_designations(simbad_result, ids_result)

    # ── Choose archive query parameter ────────────────────────────────────────
    archive_field, archive_value = _get_archive_query_params(designations)

    if not archive_field:
        print("No usable designation (HIP, HD, TIC, Gaia) found for NASA Exoplanet Archive.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── NASA Exoplanet Archive query ──────────────────────────────────────────
    print(f"Querying NASA Exoplanet Archive using {archive_value}...\n")

    try:
        exo_rows = _query_exoplanet_archive(archive_field, archive_value)
    except Exception as e:
        print(f"Error querying NASA Exoplanet Archive: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if not exo_rows:
        print(f"No exoplanet data found in NASA Exoplanet Archive for '{archive_value}'.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── HWO ExEP query (optional) ──────────────────────────────────────────────
    hwo_rows = None
    hwo_field, hwo_value = _get_hwo_query_params(designations)
    if hwo_field:
        print(f"Querying HWO ExEP Precursor Science Stars Archive using {hwo_value}...")
        try:
            hwo_result = _query_hwo_exep_archive(hwo_field, hwo_value)
            if hwo_result:
                hwo_rows = hwo_result
        except Exception as e:
            print(f"Warning: Could not query HWO ExEP archive: {e}")

    os.system("cls" if os.name == "nt" else "clear")
    _display_exoplanet_results(simbad_result, designations, exo_rows)
    if hwo_rows:
        input("\nPress Enter to Continue to HWO ExEP Precursor Science Stars Archive")
        print()
        _display_hwo_exep_results(designations, hwo_rows)

    exocat_row = _query_mission_exocat(designations)
    if exocat_row:
        input("\nPress Enter to Continue to Mission Exocat Archive")
        print()
        _display_mission_exocat_results(designations, exocat_row)

    input("\nPress Enter to Return to the Main Menu")


def _get_archive_query_params(designations):
    """Return (field_name, value) for NASA Exoplanet Archive. Priority: HIP > HD > TIC > Gaia."""
    if designations.get("HIP"):
        return "hip_name", designations["HIP"]
    if designations.get("HD"):
        return "hd_name", designations["HD"]
    if designations.get("TIC"):
        return "tic_id", designations["TIC"]
    if designations.get("Gaia EDR3"):
        return "gaia_id", designations["Gaia EDR3"]
    return None, None


def _query_exoplanet_archive(field, value):
    """Query pscomppars via NASA Exoplanet Archive TAP; return list of row dicts."""
    query = f"SELECT * FROM pscomppars WHERE {field}='{value}' ORDER BY pl_orbsmax"
    resp  = requests.get(
        "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
        params={"query": query, "format": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _get_hwo_query_params(designations):
    """Return (field_name, value) for HWO ExEP archive. Priority: HIP > HD > TIC > HR > GJ."""
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


def _query_hwo_exep_archive(field, value):
    """Query di_stars_exep via NASA Exoplanet Archive TAP; return list of row dicts."""
    query = f"SELECT * FROM di_stars_exep WHERE {field}='{value}' ORDER BY sy_dist"
    resp  = requests.get(
        "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
        params={"query": query, "format": "json"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


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


def _display_exoplanet_results(simbad_result, designations, exo_rows):
    """Print formatted NASA Exoplanet Archive results."""

    # ── SIMBAD star info (same format as Query Star Information) ──────────────
    _display_results(simbad_result, designations)

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# NASA Exoplanet Archive #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    # ── Star Name line ─────────────────────────────────────────────────────────
    main_id  = str(designations.get("MAIN_ID") or "").strip().lstrip("*").strip()
    id_parts = [str(designations[k]) for k in ("HD", "HIP", "TIC", "Gaia EDR3")
                if designations.get(k)]
    star_line = (f"Star Name: {main_id} ({', '.join(id_parts)})"
                 if id_parts else f"Star Name: {main_id}")
    dashes = "-" * len(star_line)
    print(dashes)
    print(star_line)
    print(dashes)
    print()

    # ── Star / Planet counts ──────────────────────────────────────────────────
    first     = exo_rows[0]
    n_stars   = int(_fval(first.get("sy_snum")) or 1)
    n_planets = int(_fval(first.get("sy_pnum")) or len(exo_rows))
    print(f"Star Properties: # of Stars: {n_stars} - # of Planets: {n_planets}")
    print()

    # ── Star Properties table ─────────────────────────────────────────────────
    star_rows = []
    for i, row in enumerate(exo_rows, 1):
        sp_type = str(row.get("st_spectype") or "N/A")
        magv    = _fmt(row.get("sy_vmag"), 5)

        st_lum  = _fval(row.get("st_lum"))
        st_rad  = _fval(row.get("st_rad"))
        st_teff = _fval(row.get("st_teff"))

        if st_rad is not None and st_teff is not None:
            calc = (st_rad ** 2) * ((st_teff / 5778) ** 4)
            lum  = (f"{st_lum:.5f} ({calc:.6f})"
                    if st_lum is not None else f"({calc:.6f})")
        else:
            lum = f"{st_lum:.5f}" if st_lum is not None else "N/A"

        temp    = _fmt(row.get("st_teff"), 0)
        mass    = _fmt(row.get("st_mass"), 3)
        radius  = _fmt(row.get("st_rad"),  2)
        plx     = _fmt(row.get("sy_plx"),  3)
        sy_dist = _fval(row.get("sy_dist"))
        parsecs = f"{sy_dist:.5f}"       if sy_dist is not None else "N/A"
        lys     = f"{sy_dist * 3.26156:.4f}" if sy_dist is not None else "N/A"
        fe_h    = _fmt(row.get("st_met"), 2)
        age     = _fmt(row.get("st_age"), 2)

        star_rows.append([str(i), sp_type, magv, lum, temp, mass,
                          radius, plx, parsecs, lys, fe_h, age])

    _print_table(
        headers1=["#", "Spectral",   "MagV",  "Luminosity", "Temp", "Mass",
                  "Radius", "Parallax", "Parsecs", "LYs", "Fe/H", "Age"],
        headers2=["",  "Type",       "",       "",           "",     "",
                  "",       "",         "",        "",    "",      ""],
        rows=star_rows,
        aligns=["r", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    print()

    # ── Planet Properties table ───────────────────────────────────────────────
    print("Planet Properties:")
    print()

    planet_rows = []
    for i, row in enumerate(exo_rows, 1):
        pl_name = str(row.get("pl_name") or "N/A")
        mass_e  = _fmt(row.get("pl_bmasse"), 2)
        mass_j  = _fmt(row.get("pl_bmassj"), 7)
        rad_e   = _fmt(row.get("pl_rade"),   2)
        rad_j   = _fmt(row.get("pl_radj"),   3)

        orbper  = _fval(row.get("pl_orbper"))
        orb_str = f"{orbper:.3f} days" if orbper is not None else "N/A"

        sma = _fval(row.get("pl_orbsmax"))
        ecc = _fval(row.get("pl_orbeccen"))

        if sma is not None and ecc is not None:
            ecc_au   = sma * ecc
            peri     = sma - ecc_au
            apo      = sma + ecc_au
            dist_str = f"{peri:.3f} AU - {sma:.3f} AU - {apo:.3f} AU"
            ecc_str  = f"{ecc:.2f} ({ecc_au:.3f} AU)"
        elif sma is not None:
            dist_str = f"N/A - {sma:.3f} AU - N/A"
            ecc_str  = "N/A"
        else:
            dist_str = "N/A"
            ecc_str  = "N/A"

        eq_temp = _fmt(row.get("pl_eqt"),   0)
        insol   = _fmt(row.get("pl_insol"),  2)
        density = _fmt(row.get("pl_dens"),   2)

        planet_rows.append([
            str(i), pl_name, mass_e, mass_j, rad_e, rad_j,
            orb_str, dist_str, ecc_str, eq_temp, insol, density,
        ])

    _print_table(
        headers1=["#", "Planet Name", "Mass(E)", "Mass(J)", "Radius(E)",
                  "Radius(J)", "Orbit", "Distance", "Eccentricity",
                  "Temperature", "Insol Flux",    "Density"],
        headers2=["",  "",           "",        "",        "",
                  "",          "",      "",         "",
                  "",           "(Earth Flux)", ""],
        rows=planet_rows,
        aligns=["r", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    print()

    _display_habitable_zone(exo_rows)


def _display_habitable_zone(exo_rows):
    """Calculate and display the habitable zone boundaries for the star system."""
    row = exo_rows[0]

    teff   = _fval(row.get("st_teff"))
    st_lum = _fval(row.get("st_lum"))
    st_rad = _fval(row.get("st_rad"))

    # Luminosity in solar units: prefer calculated from radius/teff, fall back to archive log10 value
    if st_rad is not None and teff is not None:
        slum = (st_rad ** 2) * ((teff / 5778) ** 4)
    elif st_lum is not None:
        slum = 10 ** st_lum
    else:
        slum = None

    if teff is None or slum is None:
        return

    seff    = [0.0] * 6
    seffsun = [1.776, 1.107, 0.356, 0.320, 1.188, 0.99]
    a = [2.136e-4, 1.332e-4, 6.171e-5, 5.547e-5, 1.433e-4, 1.209e-4]
    b = [2.533e-8, 1.580e-8, 1.698e-9, 1.526e-9, 1.707e-8, 1.404e-8]
    c = [-1.332e-11, -8.308e-12, -3.198e-12, -2.874e-12, -8.968e-12, -7.418e-12]
    d = [-3.097e-15, -1.931e-15, -5.575e-16, -5.011e-16, -2.084e-15, -1.713e-15]

    tstar = teff - 5780.0
    for i in range(len(a)):
        seff[i] = seffsun[i] + a[i]*tstar + b[i]*tstar**2 + c[i]*tstar**3 + d[i]*tstar**4

    recentVenus       = (slum / seff[0]) ** 0.5
    runawayGreenhouse = (slum / seff[1]) ** 0.5
    maxGreenhouse     = (slum / seff[2]) ** 0.5
    earlyMars         = (slum / seff[3]) ** 0.5
    fivemeRunaway     = (slum / seff[4]) ** 0.5
    tenthmeRunaway    = (slum / seff[5]) ** 0.5

    AU_TO_LM = 8.3167

    zones = [
        ("Optimistic Inner HZ (Recent Venus)",                           recentVenus),
        ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",    fivemeRunaway),
        ("Conservative Inner HZ (Runaway Greenhouse)",                   runawayGreenhouse),
        ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)",  tenthmeRunaway),
        ("Conservative Outer HZ (Maximum Greenhouse)",                   maxGreenhouse),
        ("Optimistic Outer HZ (Early Mars)",                             earlyMars),
    ]

    formatted = [(name, f"{au:.3f} ({au * AU_TO_LM:.3f} LM)") for name, au in zones]

    zone_w = max(len(f" {name}") for name, _ in formatted)
    zone_w = max(zone_w, len(" Zone"))
    au_w   = max(len(val) for _, val in formatted)
    au_w   = max(au_w, len("AU"))

    title = "Calculated Habitable Zone"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    print(f"{' Zone'.ljust(zone_w)} | {'AU'.ljust(au_w)}")
    print("-" * zone_w + "-+-" + "-" * au_w)
    for name, val in formatted:
        print(f"{(' ' + name).ljust(zone_w)} | {val}")
    print()


def _display_hwo_exep_results(designations, hwo_rows):
    """Print formatted HWO ExEP Precursor Science Stars Archive results."""

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# HWO ExEP Precursor Science Stars Archive #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    # ── Star Name line ─────────────────────────────────────────────────────────
    main_id  = str(designations.get("MAIN_ID") or "").strip().lstrip("*").strip()
    id_parts = [str(designations[k]) for k in ("HD", "HIP", "HR", "GJ")
                if designations.get(k)]
    star_line = (f"Star Name: {main_id} ({', '.join(id_parts)})"
                 if id_parts else f"Star Name: {main_id}")
    dashes = "-" * len(star_line)
    print(dashes)
    print(star_line)
    print(dashes)
    print()

    # ── Star Properties table ──────────────────────────────────────────────────
    print("Star Properties:")
    print()

    star_rows = []
    for row in hwo_rows:
        sp_type = str(row.get("st_spectype") or "N/A")

        st_lum  = _fval(row.get("st_lum"))
        st_rad  = _fval(row.get("st_rad"))
        st_teff = _fval(row.get("st_teff"))

        if st_rad is not None and st_teff is not None:
            calc = (st_rad ** 2) * ((st_teff / 5778) ** 4)
            lum  = (f"{st_lum:.4f} ({calc:.6f})"
                    if st_lum is not None else f"({calc:.6f})")
        else:
            lum = f"{st_lum:.4f}" if st_lum is not None else "N/A"

        temp    = _fmt(row.get("st_teff"), 0)
        mass    = _fmt(row.get("st_mass"), 2)
        radius  = _fmt(row.get("st_rad"),  3)
        plx     = _fmt(row.get("sy_plx"),  2)
        sy_dist = _fval(row.get("sy_dist"))
        parsecs = f"{sy_dist:.4f}"               if sy_dist is not None else "N/A"
        lys     = f"{sy_dist * 3.26156:.4f}"     if sy_dist is not None else "N/A"
        fe_h    = _fmt(row.get("st_met"), 2)

        star_rows.append([sp_type, lum, temp, mass, radius, plx, parsecs, lys, fe_h])

    _print_table(
        headers1=["Spectral",  "Luminosity", "Temp", "Mass", "Radius", "Parallax", "Parsecs", "LYs", "Fe/H"],
        headers2=["Type",      "",           "",     "",     "",       "",         "",        "",    ""],
        rows=star_rows,
        aligns=["l", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    print()
    print()

    # ── System\EEI Properties table ───────────────────────────────────────────
    print("System\\EEI Properties:")
    print()

    AU_TO_LM = 8.3167
    eei_rows = []
    for row in hwo_rows:
        planets_flag = _fval(row.get("sy_planets_flag"))
        if planets_flag is None:
            planets = "None"
        elif planets_flag == 1.0:
            planets = "Y"
        else:
            planets = "N"

        pnum_f = _fval(row.get("sy_pnum"))
        pnum   = str(int(pnum_f)) if pnum_f is not None else "N/A"

        disk_flag = _fval(row.get("sy_disksflag"))
        if disk_flag is None:
            disk = "None"
        elif disk_flag == 1.0:
            disk = "Y"
        else:
            disk = "N"

        eei_sep = _fval(row.get("st_eei_orbsep"))
        eei_str = (f"{eei_sep:.3f} AU ({eei_sep * AU_TO_LM:.4f} LM)"
                   if eei_sep is not None else "N/A")

        bratio   = _fval(row.get("st_etwin_bratio"))
        bratio_str = f"{bratio:.2e}" if bratio is not None else "N/A"

        orbper   = _fval(row.get("st_eei_orbper"))
        orbper_str = f"{orbper:.1f} days" if orbper is not None else "N/A"

        eei_rows.append([planets, pnum, disk, eei_str, bratio_str, orbper_str])

    _print_table(
        headers1=["Planets", "# of Planets", "Disk", "Earth Equivalent",          "Earth Equivalent",    "Orbital Period"],
        headers2=["",        "",             "",     "Insolation Distance (au)",   "Planet-Star Ratio",   "at EEID (days)"],
        rows=eei_rows,
        aligns=["l", "r", "l", "l", "r", "r"],
    )
    print()

    # ── Calculated Habitable Zone ──────────────────────────────────────────────
    _display_habitable_zone(hwo_rows)


# ─── Mission Exocat Archive ───────────────────────────────────────────────────

_MISSION_EXOCAT = None  # (rows, hip_index, hd_index, gj_index)


def _load_mission_exocat():
    """Load missionExocat.csv into memory and build lookup indices by HIP, HD, GJ."""
    global _MISSION_EXOCAT
    if _MISSION_EXOCAT is not None:
        return _MISSION_EXOCAT

    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "missionExocat.csv")
    rows = []
    hip_index = {}
    hd_index  = {}
    gj_index  = {}

    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                hip = row.get("hip_name", "").strip().upper()
                hd  = row.get("hd_name",  "").strip().upper()
                gj  = row.get("gj_name",  "").strip().upper()
                if hip:
                    hip_index[hip] = row
                if hd:
                    hd_index[hd] = row
                if gj:
                    gj_index[gj] = row
    except Exception as e:
        print(f"Warning: Could not load missionExocat.csv: {e}")
        _MISSION_EXOCAT = ([], {}, {}, {})
        return _MISSION_EXOCAT

    _MISSION_EXOCAT = (rows, hip_index, hd_index, gj_index)
    return _MISSION_EXOCAT


def _query_mission_exocat(designations):
    """Search Mission Exocat by HIP, HD, or GJ designation. Returns a row dict or None."""
    _, hip_index, hd_index, gj_index = _load_mission_exocat()

    hip = (designations.get("HIP") or "").strip().upper()
    hd  = (designations.get("HD")  or "").strip().upper()
    gj  = (designations.get("GJ")  or "").strip().upper()

    if hip:
        row = hip_index.get(hip)
        if row:
            return row
    if hd:
        row = hd_index.get(hd)
        if row:
            return row
    if gj:
        row = gj_index.get(gj)
        if row:
            return row
    return None


def _display_mission_exocat_results(designations, exocat_row):
    """Print formatted Mission Exocat Archive results."""

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# Mission Exocat Archive #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    # ── Star Name line ─────────────────────────────────────────────────────────
    star_name = str(exocat_row.get("star_name") or "").strip()
    id_parts  = []
    for csv_field in ("hd_name", "hip_name", "gj_name"):
        val = str(exocat_row.get(csv_field) or "").strip()
        if val:
            id_parts.append(val)
    star_line = (f"Star Name: {star_name} ({', '.join(id_parts)})"
                 if id_parts else f"Star Name: {star_name}")
    dashes = "-" * len(star_line)
    print(dashes)
    print(star_line)
    print(dashes)
    print()

    # ── Planet count ──────────────────────────────────────────────────────────
    ppnum = str(exocat_row.get("st_ppnum") or "").strip()
    print(f"Star Properties: # of Planets: {ppnum if ppnum else 'N/A'}")
    print()

    # ── Star Properties table ─────────────────────────────────────────────────
    sp_type = str(exocat_row.get("st_spttype") or "").strip() or "N/A"

    st_teff = _fval(exocat_row.get("st_teff"))
    st_rad  = _fval(exocat_row.get("st_rad"))
    st_lbol = _fval(exocat_row.get("st_lbol"))

    if st_rad is not None and st_teff is not None:
        calc = (st_rad ** 2) * ((st_teff / 5778) ** 4)
        lum  = (f"{st_lbol:.2f} ({calc:.6f})"
                if st_lbol is not None else f"({calc:.6f})")
    else:
        lum = f"{st_lbol:.2f}" if st_lbol is not None else "N/A"

    temp    = str(int(st_teff)) if st_teff is not None else ""
    mass    = _fmt(exocat_row.get("st_mass"),   1, "")
    radius  = _fmt(exocat_row.get("st_rad"),    2, "")

    eeidau  = _fval(exocat_row.get("st_eeidau"))
    eei_str = (f"{eeidau:.2f} ({eeidau * 8.3167:.4f} LM)"
               if eeidau is not None else "N/A")

    st_dist = _fval(exocat_row.get("st_dist"))
    parsecs = f"{st_dist:.2f}"           if st_dist is not None else ""
    lys     = f"{st_dist * 3.26156:.4f}" if st_dist is not None else ""

    fe_h = _fmt(exocat_row.get("st_metfe"), 2, "")
    age  = str(exocat_row.get("st_age") or "").strip()

    _print_table(
        headers1=["Spectral",  "Temp", "Mass", "Radius", "Luminosity", "EE Rad",    "Parsecs", "LYs", "Fe/H", "Age"],
        headers2=["Type",      "",     "",     "",       "",           "Distance",  "",        "",    "",     ""],
        rows=[[sp_type, temp, mass, radius, lum, eei_str, parsecs, lys, fe_h, age]],
        aligns=["l", "r", "r", "r", "r", "l", "r", "r", "r", "r"],
    )
    print()

    # ── Calculated Habitable Zone ──────────────────────────────────────────────
    lbol_log10 = None
    if st_rad is None and st_lbol is not None and st_lbol > 0:
        lbol_log10 = math.log10(st_lbol)
    hz_row = {
        "st_teff": exocat_row.get("st_teff"),
        "st_rad":  exocat_row.get("st_rad"),
        "st_lum":  str(lbol_log10) if lbol_log10 is not None else None,
    }
    _display_habitable_zone([hz_row])


def _print_table(headers1, headers2, rows, aligns):
    """Print a table with optional two-line headers and dynamic column widths."""
    n = len(headers1)

    # Calculate column widths from headers and all data rows
    widths = [0] * n
    for i in range(n):
        widths[i] = max(len(str(headers1[i])), len(str(headers2[i])))
    for row in rows:
        for i in range(n):
            widths[i] = max(widths[i], len(str(row[i])))

    def fmt_cell(val, w, align):
        s = str(val)
        return s.rjust(w) if align == "r" else s.ljust(w)

    def make_row(cells, row_aligns):
        return " | ".join(fmt_cell(c, w, a)
                          for c, w, a in zip(cells, widths, row_aligns))

    def make_sep():
        return "-+-".join("-" * w for w in widths)

    print(make_row(headers1, aligns))
    if any(headers2):
        print(make_row(headers2, ["l"] * n))
    print(make_sep())
    for row in rows:
        print(make_row(row, aligns))


# ─── Star System Regions ──────────────────────────────────────────────────────

def _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan):
    """Print the Stellar Properties table."""
    title = "Stellar Properties"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()
    headers1 = ["Stellar Mass", "Stellar Radius", "Stellar Diameter (Sol)", "Stellar Diameter (KM)", "Main Sequence Life Span"]
    headers2 = ["", "", "", "", ""]
    rows = [[
        f"{stellarMass:.4f}",
        f"{stellarRadius:.5f}",
        f"{stellarDiameterSol:.4f}",
        f"{stellarDiameterKM:.5e}",
        f"{mainSeqLifeSpan:.5e}",
    ]]
    aligns = ["r", "r", "r", "r", "r"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp):
    """Print the Star System Properties table."""
    rows = [
        ("Apparent Magnitude",            f"{vmag:.3f}"),
        ("Absolute Magnitude",            f"{absMagnitude:.3f}"),
        ("Bolometric Absolute Magnitude", f"{bcAbsMagnitude:.3f}"),
        ("Bolometric Luminosity",         f"{bcLuminosity:.6f}"),
        ("Luminosity from Mass",          f"{luminosityFromMass:.5f}"),
        ("BC (Bolometric Correction)",    f"{boloLum:.1f}"),
        ("Star Temperature (K)",          f"{int(round(temp))}"),
    ]

    label_width = max(len(label) for label, _ in rows)
    value_width = max(len(value) for _, value in rows)

    title = "Star System Properties"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()
    for label, value in rows:
        print(f" {label.ljust(label_width)} | {value.rjust(value_width)}")
    print()


def query_star_system_regions():
    """Display galactic region context for a star using SIMBAD data."""
    os.system("cls" if os.name == "nt" else "clear")
    designation = input(
        "\nEnter star designation (e.g., 'Vega', 'HD 209458', 'HIP 27989'): "
    ).strip()

    if not designation:
        print("No designation entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"\nQuerying SIMBAD for '{designation}'...\n")

    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("sp_type", "plx_value", "V", "mesfe_h")

    try:
        result = custom_simbad.query_object(designation)
        ids_result = Simbad.query_objectids(designation)

        if result is None:
            print(f"No results found for '{designation}'.")
            input("\nPress Enter to Return to the Main Menu")
            return

        designations = _parse_designations(result, ids_result)
        _display_results(result, designations)

        sp_raw  = _safe_get(result[0], result.colnames, "sp_type")
        sp_type = str(sp_raw).strip() if sp_raw is not None else ""

        letter, _ = _parse_spectral_class(sp_type)
        if not letter:
            print(f"Spectral type '{sp_type or 'N/A'}' is not a main-sequence class (O B A F G K M) — cannot determine star system region.")
            print()
            input("\nPress Enter to Return to the Main Menu")
            return

        ms_row, key_used = _lookup_spectral_type(sp_type)
        boloLum = float(ms_row["Bolo. Corr. (BC)"]) if ms_row else None

        temp_raw = _safe_get(result[0], result.colnames, "mesfe_h.teff")
        try:
            temp = float(temp_raw)
        except (TypeError, ValueError):
            temp = None

        if temp is None:
            print("Temperature is not available for this star — cannot determine star system region.")
            print()
            input("\nPress Enter to Return to the Main Menu")
            return

        vmag_raw = _safe_get(result[0], result.colnames, "V")
        try:
            vmag = float(vmag_raw)
        except (TypeError, ValueError):
            vmag = None

        if vmag is None:
            print("Apparent Magnitude (V) is not available for this star — cannot determine star system region.")
            print()
            input("\nPress Enter to Return to the Main Menu")
            return

        plx_raw = _safe_get(result[0], result.colnames, "plx_value")
        try:
            plx = float(plx_raw)
            if plx <= 0:
                plx = None
        except (TypeError, ValueError):
            plx = None

        if plx is None:
            print("Parallax is not available for this star — cannot determine star system region.")
            print()
            input("\nPress Enter to Return to the Main Menu")
            return

    except Exception as e:
        print(f"Error querying SIMBAD: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    sunlightIntensity = 1.0
    bondAlbedo = 0.3
    parsecs = 1000.0 / plx
    absMagnitude = vmag + 5 - (5 * math.log10(parsecs))
    bcAbsMagnitude = absMagnitude + boloLum
    bcLuminosity = 2.52 ** (4.85 - bcAbsMagnitude)
    stellarMass = bcLuminosity ** 0.2632
    luminosityFromMass = stellarMass ** 3.5
    stellarRadius = stellarMass ** 0.57 if stellarMass >= 1 else stellarMass ** 0.8
    stellarDiameterSol = ((5780**2) / (temp**2)) * math.sqrt(bcLuminosity)
    stellarDiameterKM = stellarDiameterSol * 1391600
    mainSeqLifeSpan = (10**10) * ((1 / stellarMass) ** 2.5)

    _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp)
    _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan)

    input("\nPress Enter to Return to the Main Menu")


# ─── Main-Sequence Star Properties ────────────────────────────────────────────

_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")
_MAIN_SEQUENCE_DATA = None


def _load_main_sequence_data():
    """Load propertiesOfMainSequenceStars.csv into a per-class lookup structure."""
    global _MAIN_SEQUENCE_DATA
    if _MAIN_SEQUENCE_DATA is not None:
        return _MAIN_SEQUENCE_DATA

    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "propertiesOfMainSequenceStars.csv",
    )
    data = {}

    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sc = row.get("Spectral Class", "").strip()
                m = _SP_PATTERN.match(sc)
                if not m:
                    continue
                letter  = m.group(1)
                subtype = float(m.group(2))
                data.setdefault(letter, []).append((subtype, row))
        for letter in data:
            data[letter].sort(key=lambda t: t[0])
    except Exception as e:
        print(f"Warning: Could not load propertiesOfMainSequenceStars.csv: {e}")
        data = {}

    _MAIN_SEQUENCE_DATA = data
    return _MAIN_SEQUENCE_DATA


def _parse_spectral_class(sp_str):
    """Extract primary class letter and numeric subtype from a SIMBAD spectral string.

    Returns (letter, subtype_float) or (None, None) if no OBAFGKM class found.
    Uses search so prefixes like 'sd' in 'sdG5' are skipped transparently.
    """
    if not sp_str or sp_str in ("N/A", "None", ""):
        return None, None
    m = _SP_PATTERN.search(sp_str)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def _lookup_spectral_type(sp_str):
    """Return (row_dict, key_used_str) for the nearest floor entry in the CSV.

    Floor rule: largest available subtype number <= requested subtype.
    Falls back to smallest available if requested is below all entries (e.g. O2 with only O5).
    Returns (None, None) if class letter not found in data.
    """
    letter, subtype = _parse_spectral_class(sp_str)
    if letter is None:
        return None, None

    data = _load_main_sequence_data()
    entries = data.get(letter)
    if not entries:
        return None, None

    best_row = None
    best_key = None
    for entry_subtype, row in entries:
        if entry_subtype <= subtype:
            best_row = row
            best_key = row.get("Spectral Class", "").strip()
        else:
            break

    if best_row is None:
        best_row = entries[0][1]
        best_key = best_row.get("Spectral Class", "").strip()

    return best_row, best_key


# ─── Main Menu ────────────────────────────────────────────────────────────────

MENU_OPTIONS = {
    "1": ("Query Star Information (SIMBAD)",            query_star),
    "2": ("Query Exoplanet Data (NASA Exoplanet Archive)", query_exoplanets),
    "3": ("Star System Regions",                        query_star_system_regions),
}


def main_menu():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 50)
        print("   SPACE AND SCIENCE FICTION APP")
        print("=" * 50)
        for key, (label, _) in MENU_OPTIONS.items():
            print(f"  {key}. {label}")
        print("  Q. Quit")
        print("=" * 50)

        choice = input("Select an option: ").strip().upper()

        if choice == "Q":
            print("\nGoodbye!\n")
            sys.exit(0)
        elif choice in MENU_OPTIONS:
            MENU_OPTIONS[choice][1]()
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    main_menu()
