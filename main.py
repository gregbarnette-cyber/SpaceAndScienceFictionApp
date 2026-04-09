#!/usr/bin/env python3
"""Space and Science Fiction App"""

import csv
from datetime import datetime
import math
import os
import re
import sys

import requests
from astroquery.simbad import Simbad
from astroquery.jplhorizons import Horizons
import astropy.time


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
_HWC_DATA       = None  # (hip_index, hd_index, name_index)  — each maps key → [row, ...]


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

def _display_alternate_hz_regions(ffInner, ffOuter, fsInner, fsOuter, prwInner, prwOuter, praInner, praOuter, pmInner, pmOuter, phInner, phOuter):
    """Print the Solar System Alternate Habitable Zone Regions table."""
    title = "Solar System Alternate Habitable Zone Regions"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()

    def au_fmt(val):
        return f"{val:.4f} ({val * 8.3167:.3f} LM)"

    headers1 = [" Region", "AU"]
    headers2 = ["", ""]
    rows = [
        [" Fluorosilicone-Fluorosilicone Inner Limit", au_fmt(ffInner)],
        [" Fluorocarbon-Sulfur Inner Limit",           au_fmt(fsInner)],
        [" Fluorosilicone-Fluorosilicone Outer Limit", au_fmt(ffOuter)],
        [" Fluorocarbon-Sulfur Outer Limit",           au_fmt(fsOuter)],
        [" Protein-Water Inner Limit",                 au_fmt(prwInner)],
        [" Protein-Water Outer Limit",                 au_fmt(prwOuter)],
        [" Protein-Ammonia Inner Limit",               au_fmt(praInner)],
        [" Protein-Ammonia Outer Limit",               au_fmt(praOuter)],
        [" Polylipid-Methane Inner Limit",             au_fmt(pmInner)],
        [" Polylipid-Methane Outer Limit",             au_fmt(pmOuter)],
        [" Polylipid-Hydrogen Inner Limit",            au_fmt(phInner)],
        [" Polylipid-Hydrogen Outer Limit",            au_fmt(phOuter)],
    ]
    aligns = ["l", "l"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_calculated_hz(bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, stellarRadius):
    """Print the Calculated Habitable Zone table using Kopparapu et al. coefficients."""
    title = "Calculated Habitable Zone"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()

    seffsun = [1.776, 1.107, 0.356, 0.320, 1.188, 0.99]
    a = [2.136e-4, 1.332e-4, 6.171e-5, 5.547e-5, 1.433e-4, 1.209e-4]
    b = [2.533e-8, 1.580e-8, 1.698e-9, 1.526e-9, 1.707e-8, 1.404e-8]
    c = [-1.332e-11, -8.308e-12, -3.198e-12, -2.874e-12, -8.968e-12, -7.418e-12]
    d = [-3.097e-15, -1.931e-15, -5.575e-16, -5.011e-16, -2.084e-15, -1.713e-15]

    tstar = temp - 5780.0
    seff = [seffsun[i] + a[i]*tstar + b[i]*tstar**2 + c[i]*tstar**3 + d[i]*tstar**4 for i in range(6)]

    def au_fmt(lum, i):
        au = math.sqrt(lum / seff[i])
        return f"{au:.3f} ({au * 8.3167:.3f} LM)"

    zone_indices = [
        ("Optimistic Inner HZ (Recent Venus)",                           0),
        ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",    4),
        ("Conservative Inner HZ (Runaway Greenhouse)",                   1),
        ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)",  5),
        ("Conservative Outer HZ (Maximum Greenhouse)",                   2),
        ("Optimistic Outer HZ (Early Mars)",                             3),
    ]

    headers1 = [" Zone", "Bolometric Luminosity (AU)", "Luminosity from Mass (AU)", "Calculated Luminosity (AU)"]
    headers2 = ["", "", "", ""]
    rows = [
        [f" {name}", au_fmt(bcLuminosity, i), au_fmt(luminosityFromMass, i), au_fmt(calculatedLuminosity, i)]
        for name, i in zone_indices
    ]
    aligns = ["l", "l", "l", "l"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_earth_equivalent_orbit(distAU, distKM, planetaryYear, planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF, sizeOfSun):
    """Print the Earth Equivalent Orbit Properties table."""
    title = "Earth Equivalent Orbit Properties"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()
    headers1 = ["Distance (AU)", "Distance (KM)", "Year", "Temp (K)", "Temp (C)", "Temp (F)", "Size"]
    headers2 = ["", "", "", "", "", "", "of Sun"]
    rows = [[
        f"{distAU:.4f}",
        f"{distKM:.5e}",
        f"{planetaryYear:.4f}",
        f"{planetaryTemperature:.2f}",
        f"{planetaryTemperatureC:.2f}",
        f"{planetaryTemperatureF:.2f}",
        sizeOfSun,
    ]]
    aligns = ["r", "r", "r", "r", "r", "r", "r"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_solar_system_regions(sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol):
    """Print the Solar System Regions table."""
    title = "Solar System Regions"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()

    def au_fmt(val):
        return f"{val:.4f} ({val * 8.3167:.3f} LM)"

    headers1 = [" Region", "AU"]
    headers2 = ["", ""]
    rows = [
        [" System Inner Limit (Gravity)",             au_fmt(sysilGrav)],
        [" System Inner Limit (Sunlight)",            au_fmt(sysilSunlight)],
        [" Circumstellar Habitable Zone Inner Limit", au_fmt(hzil)],
        [" Circumstellar Habitable Zone Outer Limit", au_fmt(hzol)],
        [" Snow Line",                                au_fmt(snowLine)],
        [" Liquid Hydrogen (LH2) Line",               au_fmt(lh2Line)],
        [" System Outer Limit",                       au_fmt(sysol)],
    ]
    aligns = ["l", "l"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_star_distance(parallax, trigParallax, parsecs, lightYears):
    """Print the Star Distance table."""
    title = "Star Distance"
    dashes = "-" * len(title)
    print(dashes)
    print(title)
    print(dashes)
    print()
    headers1 = ["Parallax", "Trig Parallax", "Parsecs", "Light Years"]
    headers2 = ["", "", "", ""]
    rows = [[
        f"{parallax:.2f}",
        f"{trigParallax:.4f}",
        f"{parsecs:.4f}",
        f"{lightYears:.4f}",
    ]]
    aligns = ["r", "r", "r", "r"]
    _print_table(headers1, headers2, rows, aligns)
    print()


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
    trigParallax = plx / 1000
    lightYears = 3.2616 / trigParallax
    distAU = math.sqrt(bcLuminosity / sunlightIntensity)
    distKM = distAU * 149000000
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass)
    planetaryTemperature = 374 * 1.1 * (1 - bondAlbedo) * (sunlightIntensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9 / 5) + 32
    starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"
    sysilGrav = 0.2 * stellarMass
    sysilSunlight = math.sqrt(bcLuminosity / 16)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    snowLine = math.sqrt(bcLuminosity / 0.04)
    lh2Line = math.sqrt(bcLuminosity / 0.0025)
    sysol = 40 * stellarMass
    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778) ** 4
    ffInner  = math.sqrt(bcLuminosity / 52)
    ffOuter  = math.sqrt(bcLuminosity / 29.9)
    fsInner  = math.sqrt(bcLuminosity / 38.7)
    fsOuter  = math.sqrt(bcLuminosity / 3.2)
    prwInner = math.sqrt(bcLuminosity / 2.8)
    prwOuter = math.sqrt(bcLuminosity / 0.8)
    praInner = math.sqrt(bcLuminosity / 0.48)
    praOuter = math.sqrt(bcLuminosity / 0.21)
    pmInner  = math.sqrt(bcLuminosity / 0.023)
    pmOuter  = math.sqrt(bcLuminosity / 0.0094)
    phInner  = math.sqrt(bcLuminosity / 0.0025)
    phOuter  = math.sqrt(bcLuminosity / 0.000024)

    _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp)
    _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan)
    _display_star_distance(plx, trigParallax, parsecs, lightYears)
    _display_earth_equivalent_orbit(distAU, distKM, planetaryYear, planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF, sizeOfSun)
    _display_solar_system_regions(sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol)
    _display_alternate_hz_regions(ffInner, ffOuter, fsInner, fsOuter, prwInner, prwOuter, praInner, praOuter, pmInner, pmOuter, phInner, phOuter)
    _display_calculated_hz(bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, stellarRadius)

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


_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]


def _lookup_spectral_type(sp_str):
    """Return (row_dict, key_used_str) for the nearest ceiling entry in the CSV.

    Ceiling rule: smallest available subtype number >= requested subtype.
    Within-class fallthrough: if all entries are cooler than requested (e.g. F9
    with entries only up to F7), advance to the next cooler letter class and
    return its hottest (lowest subtype) entry (e.g. G0).
    Falls back to the last entry in the final available class if no next class exists.
    Returns (None, None) if class letter not found in data.
    """
    letter, subtype = _parse_spectral_class(sp_str)
    if letter is None:
        return None, None

    data = _load_main_sequence_data()

    # Walk the letter sequence starting at the requested letter.
    try:
        start_idx = _LETTER_SEQUENCE.index(letter)
    except ValueError:
        return None, None

    for idx in range(start_idx, len(_LETTER_SEQUENCE)):
        current_letter = _LETTER_SEQUENCE[idx]
        entries = data.get(current_letter)
        if not entries:
            continue

        if idx == start_idx:
            # Ceiling search within the requested letter.
            for entry_subtype, row in entries:
                if entry_subtype >= subtype:
                    return row, row.get("Spectral Class", "").strip()
            # All entries were below the requested subtype — fall through to next letter.
        else:
            # Next cooler letter: return its hottest (smallest subtype) entry.
            row = entries[0][1]
            return row, row.get("Spectral Class", "").strip()

    # No match found at all — return last entry of the starting letter as fallback.
    entries = data.get(letter)
    if entries:
        row = entries[-1][1]
        return row, row.get("Spectral Class", "").strip()
    return None, None


# ─── NASA Exoplanet Archive: Planetary Systems Composite ─────────────────────

def query_planetary_systems_composite():
    """Query NASA Exoplanet Archive (pscomppars) and display SIMBAD info, star/planet
    properties, and the calculated habitable zone — without HWO or Mission Exocat."""
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

    os.system("cls" if os.name == "nt" else "clear")
    _display_exoplanet_results(simbad_result, designations, exo_rows)

    input("\nPress Enter to Return to the Main Menu")


# ─── NASA Exoplanet Archive: HWO ExEP Precursor Science Stars ────────────────

def query_hwo_exep():
    """Query HWO ExEP Precursor Science Stars Archive and display SIMBAD info,
    star/EEI properties, and the calculated habitable zone."""
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

    # ── Choose HWO archive query parameter ────────────────────────────────────
    hwo_field, hwo_value = _get_hwo_query_params(designations)

    if not hwo_field:
        print("No usable designation (HIP, HD, TIC, HR, GJ) found for HWO ExEP archive.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── HWO ExEP archive query ────────────────────────────────────────────────
    print(f"Querying HWO ExEP Precursor Science Stars Archive using {hwo_value}...\n")

    try:
        hwo_rows = _query_hwo_exep_archive(hwo_field, hwo_value)
    except Exception as e:
        print(f"Error querying HWO ExEP archive: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if not hwo_rows:
        print(f"No data found in HWO ExEP archive for '{hwo_value}'.")
        input("\nPress Enter to Return to the Main Menu")
        return

    os.system("cls" if os.name == "nt" else "clear")
    _display_results(simbad_result, designations)
    _display_hwo_exep_results(designations, hwo_rows)

    input("\nPress Enter to Return to the Main Menu")


# ─── NASA Exoplanet Archive: Mission Exocat Stars ────────────────────────────

def query_mission_exocat_stars():
    """Query Mission Exocat archive and display SIMBAD info, star properties,
    and the calculated habitable zone."""
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

    # ── Mission Exocat lookup ─────────────────────────────────────────────────
    exocat_row = _query_mission_exocat(designations)

    if not exocat_row:
        print(f"No data found in Mission Exocat archive for '{designation}'.")
        input("\nPress Enter to Return to the Main Menu")
        return

    os.system("cls" if os.name == "nt" else "clear")
    _display_results(simbad_result, designations)
    _display_mission_exocat_results(designations, exocat_row)

    input("\nPress Enter to Return to the Main Menu")


# ─── Star System Regions (Semi-Manual) ───────────────────────────────────────

def query_star_system_regions_semi_manual():
    """Display star system regions with manually entered Sunlight Intensity and Bond Albedo."""
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

    # ── Manual entry of Sunlight Intensity and Bond Albedo ────────────────────
    while True:
        try:
            sunlightIntensity = float(input("Enter Sunlight Intensity (Terra = 1.0): ").strip() or "1.0")
            break
        except ValueError:
            print("Invalid value. Please enter a number.")

    while True:
        try:
            bondAlbedo = float(input("Enter Bond Albedo (Terra = 0.3, Venus = 0.9): ").strip() or "0.3")
            break
        except ValueError:
            print("Invalid value. Please enter a number.")

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
    trigParallax = plx / 1000
    lightYears = 3.2616 / trigParallax
    distAU = math.sqrt(bcLuminosity / sunlightIntensity)
    distKM = distAU * 149000000
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass)
    planetaryTemperature = 374 * 1.1 * (1 - bondAlbedo) * (sunlightIntensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9 / 5) + 32
    starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"
    sysilGrav = 0.2 * stellarMass
    sysilSunlight = math.sqrt(bcLuminosity / 16)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    snowLine = math.sqrt(bcLuminosity / 0.04)
    lh2Line = math.sqrt(bcLuminosity / 0.0025)
    sysol = 40 * stellarMass
    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778) ** 4
    ffInner  = math.sqrt(bcLuminosity / 52)
    ffOuter  = math.sqrt(bcLuminosity / 29.9)
    fsInner  = math.sqrt(bcLuminosity / 38.7)
    fsOuter  = math.sqrt(bcLuminosity / 3.2)
    prwInner = math.sqrt(bcLuminosity / 2.8)
    prwOuter = math.sqrt(bcLuminosity / 0.8)
    praInner = math.sqrt(bcLuminosity / 0.48)
    praOuter = math.sqrt(bcLuminosity / 0.21)
    pmInner  = math.sqrt(bcLuminosity / 0.023)
    pmOuter  = math.sqrt(bcLuminosity / 0.0094)
    phInner  = math.sqrt(bcLuminosity / 0.0025)
    phOuter  = math.sqrt(bcLuminosity / 0.000024)

    _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp)
    _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan)
    _display_star_distance(plx, trigParallax, parsecs, lightYears)
    _display_earth_equivalent_orbit(distAU, distKM, planetaryYear, planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF, sizeOfSun)
    _display_solar_system_regions(sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol)
    _display_alternate_hz_regions(ffInner, ffOuter, fsInner, fsOuter, prwInner, prwOuter, praInner, praOuter, pmInner, pmOuter, phInner, phOuter)
    _display_calculated_hz(bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, stellarRadius)

    input("\nPress Enter to Return to the Main Menu")


# ─── Star System Regions (Manual) ────────────────────────────────────────────

def query_star_system_regions_manual():
    """Display star system regions with all values entered manually — no SIMBAD lookup."""
    os.system("cls" if os.name == "nt" else "clear")
    print("\nEnter star data manually:\n")

    def prompt_float(label):
        while True:
            try:
                return float(input(f"{label}: ").strip())
            except ValueError:
                print("Invalid value. Please enter a number.")

    vmag             = prompt_float("Apparent Magnitude (V)")
    plx              = prompt_float("Parallax (mas)")
    boloLum          = prompt_float("Bolometric Correction (BC)")
    temp             = prompt_float("Star Effective Temperature (K)")
    sunlightIntensity = prompt_float("Sunlight Intensity (Terra = 1.0)")
    bondAlbedo       = prompt_float("Bond Albedo (Terra = 0.3, Venus = 0.9)")

    if plx <= 0:
        print("Parallax must be greater than zero.")
        input("\nPress Enter to Return to the Main Menu")
        return

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
    trigParallax = plx / 1000
    lightYears = 3.2616 / trigParallax
    distAU = math.sqrt(bcLuminosity / sunlightIntensity)
    distKM = distAU * 149000000
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass)
    planetaryTemperature = 374 * 1.1 * (1 - bondAlbedo) * (sunlightIntensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9 / 5) + 32
    starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"
    sysilGrav = 0.2 * stellarMass
    sysilSunlight = math.sqrt(bcLuminosity / 16)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    snowLine = math.sqrt(bcLuminosity / 0.04)
    lh2Line = math.sqrt(bcLuminosity / 0.0025)
    sysol = 40 * stellarMass
    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778) ** 4
    ffInner  = math.sqrt(bcLuminosity / 52)
    ffOuter  = math.sqrt(bcLuminosity / 29.9)
    fsInner  = math.sqrt(bcLuminosity / 38.7)
    fsOuter  = math.sqrt(bcLuminosity / 3.2)
    prwInner = math.sqrt(bcLuminosity / 2.8)
    prwOuter = math.sqrt(bcLuminosity / 0.8)
    praInner = math.sqrt(bcLuminosity / 0.48)
    praOuter = math.sqrt(bcLuminosity / 0.21)
    pmInner  = math.sqrt(bcLuminosity / 0.023)
    pmOuter  = math.sqrt(bcLuminosity / 0.0094)
    phInner  = math.sqrt(bcLuminosity / 0.0025)
    phOuter  = math.sqrt(bcLuminosity / 0.000024)

    print()
    _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp)
    _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan)
    _display_star_distance(plx, trigParallax, parsecs, lightYears)
    _display_earth_equivalent_orbit(distAU, distKM, planetaryYear, planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF, sizeOfSun)
    _display_solar_system_regions(sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol)
    _display_alternate_hz_regions(ffInner, ffOuter, fsInner, fsOuter, prwInner, prwOuter, praInner, praOuter, pmInner, pmOuter, phInner, phOuter)
    _display_calculated_hz(bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, stellarRadius)

    input("\nPress Enter to Return to the Main Menu")


# ─── Habitable Worlds Catalog ─────────────────────────────────────────────────

def _load_hwc():
    """Load hwc.csv into memory and build lookup indices by HIP, HD, and S_NAME.
    Each index maps a normalised uppercase key → list of planet row dicts."""
    global _HWC_DATA
    if _HWC_DATA is not None:
        return _HWC_DATA

    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hwc.csv")
    hip_index  = {}
    hd_index   = {}
    name_index = {}

    def _add(index, key, row):
        key = key.strip().upper()
        if key:
            index.setdefault(key, []).append(row)

    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _add(hip_index,  row.get("S_NAME_HIP", ""), row)
                _add(hd_index,   row.get("S_NAME_HD",  ""), row)
                _add(name_index, row.get("S_NAME",      ""), row)
    except Exception as e:
        print(f"Warning: Could not load hwc.csv: {e}")
        _HWC_DATA = ({}, {}, {})
        return _HWC_DATA

    _HWC_DATA = (hip_index, hd_index, name_index)
    return _HWC_DATA


def _query_hwc(designations):
    """Search HWC by HIP → HD → S_NAME. Returns a list of planet row dicts or None."""
    hip_index, hd_index, name_index = _load_hwc()

    # designations store full strings like "HIP 8102", "HD 10700"; HWC uses same format
    hip  = (designations.get("HIP")  or "").strip().upper()
    hd   = (designations.get("HD")   or "").strip().upper()
    # designations["NAME"] is stored as "NAME Tau Ceti"; strip the prefix
    raw_name = (designations.get("NAME") or "").strip()
    name = raw_name[5:].strip().upper() if raw_name.upper().startswith("NAME ") else raw_name.upper()

    for key, index in [(hip, hip_index), (hd, hd_index), (name, name_index)]:
        if key:
            rows = index.get(key)
            if rows:
                return rows
    return None


def _display_hwc_star_properties(row):
    """Print the Star Properties table from a HWC row."""
    title = "Star Properties"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    def _f(key, decimals=None):
        v = row.get(key, "")
        if v == "":
            return ""
        try:
            f = float(v)
            return f"{f:.{decimals}f}" if decimals is not None else str(f)
        except ValueError:
            return v.strip()

    ly = ""
    try:
        ly = f"{float(row['S_DISTANCE']) * 3.26156:.4f}"
    except (ValueError, KeyError):
        pass

    temp_raw = row.get("S_TEMPERATURE", "")
    temp = ""
    try:
        temp = str(int(float(temp_raw)))
    except (ValueError, TypeError):
        pass

    headers1 = [" Star", "HD", "HIP", "Spectral", "MagV", "L", "Temp", "Mass", "Radius", "RA", "DEC", "Parsecs", "LY", "Fe/H", "Age"]
    headers2 = ["", "", "", "Type", "", "", "", "", "", "", "", "", "", "", ""]
    data_row = [
        row.get("S_NAME", "").strip(),
        row.get("S_NAME_HD", "").strip(),
        row.get("S_NAME_HIP", "").strip(),
        row.get("S_TYPE", "").strip(),
        _f("S_MAG", 5),
        _f("S_LUMINOSITY", 5),
        temp,
        _f("S_MASS", 2),
        _f("S_RADIUS", 2),
        _f("S_RA", 4),
        _f("S_DEC", 4),
        _f("S_DISTANCE", 5),
        ly,
        _f("S_METALLICITY", 2),
        _f("S_AGE", 2),
    ]
    aligns = ["l", "l", "l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r"]
    _print_table(headers1, headers2, [data_row], aligns)
    print()


def _display_hwc_star_habitability(row):
    """Print the Star Habitability Properties table from a HWC row."""
    title = "Star Habitability Properties"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    def _f(key):
        v = row.get(key, "")
        try:
            return f"{float(v):.6f}"
        except (ValueError, TypeError):
            return v.strip()

    headers1 = ["Inner Opt HZ", "Inner Con HZ", "Outer Con HZ", "Outer Opt HZ",
                "Inner Con 5 Me HZ", "Outer Con 5 Me HZ", "Tidal Lock", "Abiogenesis", "Snow Line"]
    headers2 = [""] * 9
    data_row = [
        _f("S_HZ_OPT_MIN"), _f("S_HZ_CON_MIN"), _f("S_HZ_CON_MAX"), _f("S_HZ_OPT_MAX"),
        _f("S_HZ_CON1_MIN"), _f("S_HZ_CON1_MAX"),
        _f("S_TIDAL_LOCK"), _f("S_ABIO_ZONE"), _f("S_SNOW_LINE"),
    ]
    aligns = ["r"] * 9
    _print_table(headers1, headers2, [data_row], aligns)
    print()


def _display_hwc_planet_properties(planet_rows):
    """Print the Planet Properties table from a list of HWC planet rows."""
    title = "Planet Properties"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    def _f(row, key, decimals):
        v = row.get(key, "")
        try:
            return f"{float(v):.{decimals}f}"
        except (ValueError, TypeError):
            return v.strip()

    headers1 = [" Planet", "Mass (E)", "Radius (E)", "Orbit", "Semi-Major", "Eccentricity",
                "Density", "Potential", "Gravity", "Escape"]
    headers2 = ["", "", "", "", "Axis", "", "", "", "", ""]
    rows = []
    for r in planet_rows:
        rows.append([
            r.get("P_NAME", "").strip(),
            _f(r, "P_MASS", 2),
            _f(r, "P_RADIUS", 2),
            _f(r, "P_PERIOD", 2),
            _f(r, "P_SEMI_MAJOR_AXIS", 3),
            _f(r, "P_ECCENTRICITY", 2),
            _f(r, "P_DENSITY", 4),
            _f(r, "P_POTENTIAL", 5),
            _f(r, "P_GRAVITY", 5),
            _f(r, "P_ESCAPE", 5),
        ])
    aligns = ["l", "r", "r", "r", "r", "r", "r", "r", "r", "r"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_hwc_planet_habitability(planet_rows):
    """Print the Planet Habitability Properties table from a list of HWC planet rows."""
    title = "Planet Habitability Properties"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    def _f(row, key, decimals):
        v = row.get(key, "")
        try:
            return f"{float(v):.{decimals}f}"
        except (ValueError, TypeError):
            return v.strip()

    def _flag(row, key):
        v = row.get(key, "").strip()
        if v == "1":
            return "Yes"
        if v == "0":
            return "No"
        return ""

    headers1 = [" Planet", "EFF", "Periastron", "Apastron", "Temp", "Hill", "Habitable?", "ESI", "In HZ Con", "In HZ Opt"]
    headers2 = [" Type", "Dist", "", "", "Type", "Sphere", "", "", "", ""]
    rows = []
    for r in planet_rows:
        rows.append([
            r.get("P_TYPE", "").strip(),
            _f(r, "P_DISTANCE_EFF", 5),
            _f(r, "P_PERIASTRON", 5),
            _f(r, "P_APASTRON", 5),
            r.get("P_TYPE_TEMP", "").strip(),
            _f(r, "P_HILL_SPHERE", 8),
            _flag(r, "P_HABITABLE"),
            _f(r, "P_ESI", 6),
            _flag(r, "P_HABZONE_CON"),
            _flag(r, "P_HABZONE_OPT"),
        ])
    aligns = ["l", "r", "r", "r", "l", "r", "l", "r", "l", "l"]
    _print_table(headers1, headers2, rows, aligns)
    print()


def _display_hwc_planet_temperature(planet_rows):
    """Print the Planet Temperature Properties table from a list of HWC planet rows."""
    title = "Planet Temperature Properties"
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print()

    def _f(row, key, decimals):
        v = row.get(key, "")
        try:
            return f"{float(v):.{decimals}f}"
        except (ValueError, TypeError):
            return v.strip()

    headers1 = ["Flux Min", "Flux", "Flux Max", "EQ Min", "EQ", "EQ Max", "Surf Min", "Surf", "Surf Max"]
    headers2 = [""] * 9
    rows = []
    for r in planet_rows:
        rows.append([
            _f(r, "P_FLUX_MIN", 5),
            _f(r, "P_FLUX", 5),
            _f(r, "P_FLUX_MAX", 5),
            _f(r, "P_TEMP_EQUIL_MIN", 3),
            _f(r, "P_TEMP_EQUIL", 3),
            _f(r, "P_TEMP_EQUIL_MAX", 3),
            _f(r, "P_TEMP_SURF_MIN", 3),
            _f(r, "P_TEMP_SURF", 3),
            _f(r, "P_TEMP_SURF_MAX", 3),
        ])
    aligns = ["r"] * 9
    _print_table(headers1, headers2, rows, aligns)
    print()


def query_habitable_worlds_catalog():
    """Query the Habitable Worlds Catalog for a star."""
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
    _display_results(simbad_result, designations)

    # ── Habitable Worlds Catalog lookup ───────────────────────────────────────
    hwc_rows = _query_hwc(designations)

    if not hwc_rows:
        print("No data found in the Habitable Worlds Catalog for this star.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # Sort planets by semi-major axis ascending
    def _sma(r):
        try:
            return float(r.get("P_SEMI_MAJOR_AXIS", "0") or "0")
        except ValueError:
            return 0.0
    hwc_rows.sort(key=_sma)

    _display_hwc_star_properties(hwc_rows[0])
    _display_hwc_star_habitability(hwc_rows[0])
    _display_hwc_planet_properties(hwc_rows)
    _display_hwc_planet_habitability(hwc_rows)
    _display_hwc_planet_temperature(hwc_rows)

    input("\nPress Enter to Return to the Main Menu")


# ─── Open Exoplanet Catalogue ─────────────────────────────────────────────────

import astroquery.open_exoplanet_catalogue as _oec_mod

_OEC_DATA = None  # (root_element, {lowercase_name: system_element})

_OEC_STATUS_MAP = {
    "Confirmed planets":                       "Confirmed",
    "Controversial":                           "Controversial",
    "Retracted planet candidate":              "Retracted",
    "Solar System":                            "Solar Sys",
    "Kepler Objects of Interest":              "KOI",
    "Planets in binary systems, S-type":       "Binary S",
}


def _load_oec():
    """Download and parse OEC XML; build case-insensitive name→system index. Cached."""
    global _OEC_DATA
    if _OEC_DATA is not None:
        return _OEC_DATA

    tree = _oec_mod.get_catalogue()
    root = tree.getroot() if hasattr(tree, "getroot") else tree

    # Build index: lowercase name text → system element
    index = {}
    for system in root:
        for elem in system.iter("name"):
            if elem.text:
                key = elem.text.strip().lower()
                if key not in index:
                    index[key] = system

    _OEC_DATA = (root, index)
    return _OEC_DATA


def _get_oec_candidates(designations):
    """Return ordered list of candidate name strings to try against the OEC index."""
    candidates = []

    for key in ("HIP", "HD", "GJ", "HR", "WASP", "HAT_P", "Kepler", "TOI",
                "K2", "CoRoT", "COCONUTS", "KOI", "TIC", "2MASS"):
        val = designations.get(key)
        if val:
            s = str(val).strip()
            # Normalize space-separated mission IDs to dash form (OEC convention)
            s = re.sub(r"(?i)^(k2)\s+(\d)", r"K2-\2", s)
            s = re.sub(r"(?i)^(kepler)\s+(\d)", r"Kepler-\2", s)
            s = re.sub(r"(?i)^(hat-p)\s+(\d)", r"HAT-P-\2", s)
            # WASP-94A → WASP-94 A  (SIMBAD omits space before component letter)
            s = re.sub(r"(?i)^(WASP-\d+)([AB])$", r"\1 \2", s)
            # 2MASS J20550794-3408079 → 2MASS 20550794-3408079  (strip leading J)
            s = re.sub(r"(?i)^(2MASS\s+)J(\d)", r"\g<1>\2", s)
            candidates.append(s)

    # NAME designation: strip "NAME " prefix
    name_val = str(designations.get("NAME") or "").strip()
    if name_val.upper().startswith("NAME "):
        candidates.append(name_val[5:].strip())
    elif name_val:
        candidates.append(name_val)

    # MAIN_ID: strip leading "* ", "V* ", "NAME " SIMBAD prefixes
    main_id = str(designations.get("MAIN_ID") or "").strip()
    for prefix in ("NAME ", "V* ", "* "):
        if main_id.upper().startswith(prefix.upper()):
            main_id = main_id[len(prefix):].strip()
            break
    if main_id:
        candidates.append(main_id)

    return candidates


def _find_stars_in_system(system_elem, matched_name_lower):
    """Return list of <star> elements for matched_name.

    If the system has multiple stars with planets (e.g. WASP-94, Alpha Centauri),
    returns all of them regardless of which star the query matched — so the user
    always sees the full binary picture.
    If only one star has planets, returns [that_star].
    Last resort: all stars.
    """
    stars_with_planets = [s for s in system_elem.iter("star") if s.find("planet") is not None]
    if stars_with_planets:
        return stars_with_planets

    # Last resort: all stars
    return list(system_elem.iter("star"))


def _query_oec(designations):
    """Search OEC for designations; return (system_elem, star_elems_list) or (None, [])."""
    _, index = _load_oec()
    candidates = _get_oec_candidates(designations)

    for name in candidates:
        key = name.lower()
        if key in index:
            system_elem = index[key]
            star_elems = _find_stars_in_system(system_elem, key)
            return system_elem, star_elems

    return None, []


def _oec_val(elem, tag):
    """Return stripped text of first matching child tag, or None."""
    if elem is None:
        return None
    text = elem.findtext(tag)
    return text.strip() if text and text.strip() else None


def _display_oec_star_properties(system_elem, star_elem):
    """Print Star Properties table for the OEC star."""
    spec   = _oec_val(star_elem, "spectraltype") or "N/A"
    magv   = _oec_val(star_elem, "magV")
    temp   = _oec_val(star_elem, "temperature")
    mass   = _oec_val(star_elem, "mass")
    radius = _oec_val(star_elem, "radius")
    met    = _oec_val(star_elem, "metallicity")
    age    = _oec_val(star_elem, "age")
    dist   = _oec_val(system_elem, "distance")

    def _fmt_f(v, dp):
        try:
            return f"{float(v):.{dp}f}"
        except (TypeError, ValueError):
            return "N/A"

    def _fmt_i(v):
        try:
            return str(int(float(v)))
        except (TypeError, ValueError):
            return "N/A"

    parsecs_str = _fmt_f(dist, 4)
    ly_str = "N/A"
    if dist:
        try:
            ly_str = f"{float(dist) * 3.26156:.4f}"
        except (TypeError, ValueError):
            pass

    _print_table(
        headers1=["Spectral", "MagV",       "Temp",      "Mass",      "Radius",    "Fe/H",      "Age",       "Parsecs",    "LYs"],
        headers2=["Type",     "",            "",          "",          "",          "",          "",          "",           ""],
        rows=[[
            spec,
            _fmt_f(magv, 3),
            _fmt_i(temp),
            _fmt_f(mass, 3),
            _fmt_f(radius, 3),
            _fmt_f(met, 3),
            _fmt_f(age, 2),
            parsecs_str,
            ly_str,
        ]],
        aligns=["l", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    print()


def _display_oec_planet_properties(star_elem):
    """Print Planet Properties table; sorted by semimajoraxis ascending (N/A last)."""

    def _fv(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _fmt_f(v, dp):
        f = _fv(v)
        return f"{f:.{dp}f}" if f is not None else "N/A"

    def _fmt_i(v):
        f = _fv(v)
        return str(int(f)) if f is not None else "N/A"

    planets = list(star_elem.iter("planet"))

    def sort_key(p):
        sma = _fv(p.findtext("semimajoraxis"))
        return (0, sma) if sma is not None else (1, 0)

    planets.sort(key=sort_key)

    planet_rows = []
    for idx, planet in enumerate(planets, 1):
        name_elem = planet.find("name")
        pname = name_elem.text.strip() if name_elem is not None and name_elem.text else "N/A"

        mass_j   = _fv(planet.findtext("mass"))
        mass_e   = f"{mass_j * 317.8:.2f}" if mass_j is not None else "N/A"
        mass_j_s = f"{mass_j:.4f}" if mass_j is not None else "N/A"

        rad_j    = _fv(planet.findtext("radius"))
        rad_e    = f"{rad_j * 11.2:.2f}" if rad_j is not None else "N/A"
        rad_j_s  = f"{rad_j:.4f}" if rad_j is not None else "N/A"

        period   = _fmt_f(planet.findtext("period"), 3)
        temp_s   = _fmt_i(planet.findtext("temperature"))

        sma_v    = _fv(planet.findtext("semimajoraxis"))
        ecc_v    = _fv(planet.findtext("eccentricity"))
        ecc_s    = f"{ecc_v:.3f}" if ecc_v is not None else "N/A"

        if sma_v is not None:
            sma_s = f"{sma_v:.3f}"
            if ecc_v is not None:
                peri = f"{sma_v * (1 - ecc_v):.3f}"
                apo  = f"{sma_v * (1 + ecc_v):.3f}"
                dist_s = f"{peri} - {sma_s} - {apo} AU"
            else:
                dist_s = f"N/A - {sma_s} - N/A AU"
        else:
            dist_s = "N/A"

        method   = planet.findtext("discoverymethod") or "N/A"
        year     = planet.findtext("discoveryyear") or "N/A"

        status_raw = planet.findtext("list") or ""
        status = _OEC_STATUS_MAP.get(status_raw, status_raw[:12] if status_raw else "N/A")

        planet_rows.append([
            str(idx), pname, mass_j_s, mass_e, rad_j_s, rad_e,
            period, dist_s, ecc_s, temp_s, method, year, status,
        ])

    _print_table(
        headers1=["#", "Planet Name", "Mass(J)",  "Mass(E)", "Rad(J)",  "Rad(E)", "Period",    "Distance (Peri - SMA - Apo)", "Eccentricity", "Temp", "Method", "Year", "Status"],
        headers2=["",  "",            "",          "",        "",        "",       "(days)",    "",                           "",             "",    "",       "",    ""],
        rows=planet_rows,
        aligns=["r", "l", "r", "r", "r", "r", "r", "r", "r", "r", "l", "r", "l"],
    )
    print()


def _display_oec_results(designations, system_elem, star_elems):
    """Render all OEC result tables. star_elems is a list of <star> elements."""

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# Open Exoplanet Catalogue #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    if not star_elems:
        # No individual star found — show system name only
        names = [n.text.strip() for n in system_elem.findall("name") if n.text and n.text.strip()]
        primary = names[0] if names else "Unknown"
        alternates = names[1:4]
        star_line = (f"Star Name: {primary}  ({', '.join(alternates)})"
                     if alternates else f"Star Name: {primary}")
        sep = "-" * len(star_line)
        print(sep)
        print(star_line)
        print(sep)
        print()
        print("Note: No individual host star element found for this object in OEC.")
        return

    for star_elem in star_elems:
        # ── Star Name line ────────────────────────────────────────────────────
        names = [n.text.strip() for n in star_elem.findall("name") if n.text and n.text.strip()]
        primary    = names[0] if names else "Unknown"
        alternates = names[1:4]
        star_line  = (f"Star Name: {primary}  ({', '.join(alternates)})"
                      if alternates else f"Star Name: {primary}")
        sep = "-" * len(star_line)
        print(sep)
        print(star_line)
        print(sep)
        print()

        # ── Star Properties ───────────────────────────────────────────────────
        _display_oec_star_properties(system_elem, star_elem)

        # ── Planet Properties ─────────────────────────────────────────────────
        planets = list(star_elem.iter("planet"))
        if planets:
            _display_oec_planet_properties(star_elem)
        else:
            print("No planets found for this star in the Open Exoplanet Catalogue.")
            print()

        # ── Calculated Habitable Zone ─────────────────────────────────────────
        teff_s = _oec_val(star_elem, "temperature")
        rad_s  = _oec_val(star_elem, "radius")
        hz_row = {"st_teff": teff_s, "st_rad": rad_s, "st_lum": None}
        _display_habitable_zone([hz_row])


def query_open_exoplanet_catalogue():
    """Query the Open Exoplanet Catalogue for a star's exoplanet data."""
    os.system("cls" if os.name == "nt" else "clear")
    designation = input(
        "\nEnter star designation (e.g., 'tau Ceti', 'HD 209458', 'WASP-12'): "
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

    # ── Load and query OEC ────────────────────────────────────────────────────
    print("Loading Open Exoplanet Catalogue...")
    try:
        system_elem, star_elems = _query_oec(designations)
    except Exception as e:
        print(f"Error loading Open Exoplanet Catalogue: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if system_elem is None:
        print("No data found in the Open Exoplanet Catalogue for this star.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Display ───────────────────────────────────────────────────────────────
    os.system("cls" if os.name == "nt" else "clear")
    _display_results(simbad_result, designations)
    _display_oec_results(designations, system_elem, star_elems)

    input("\nPress Enter to Return to the Main Menu")


# ─── Exoplanet EU Encyclopaedia ───────────────────────────────────────────────

import csv as _csv
import io as _io
import math as _math

_EU_DATA = None  # (rows_list, {star_name_lower: [row, ...]})
_EU_CSV_URL = "https://exoplanet.eu/catalog/csv/"


def _load_eu():
    """Download exoplanet.eu CSV and build star_name index. Cached per session."""
    global _EU_DATA
    if _EU_DATA is not None:
        return _EU_DATA

    resp = requests.get(_EU_CSV_URL, timeout=30)
    resp.raise_for_status()
    reader = _csv.DictReader(_io.StringIO(resp.text))
    rows = list(reader)

    # Build case-insensitive star_name index
    index = {}
    for row in rows:
        key = row.get("star_name", "").strip().lower()
        if key:
            index.setdefault(key, []).append(row)

    _EU_DATA = (rows, index)
    return _EU_DATA


def _get_eu_candidates(designations):
    """Return ordered list of star name candidates to try against the exoplanet.eu index."""
    candidates = []

    for key in ("HD", "GJ", "HR", "WASP", "HAT_P", "Kepler", "TOI",
                "K2", "CoRoT", "COCONUTS", "KOI", "TIC", "HIP", "2MASS"):
        val = designations.get(key)
        if val:
            s = str(val).strip()
            # Normalize space-separated mission IDs to dash form
            s = re.sub(r"(?i)^(k2)\s+(\d)", r"K2-\2", s)
            s = re.sub(r"(?i)^(kepler)\s+(\d)", r"Kepler-\2", s)
            s = re.sub(r"(?i)^(hat-p)\s+(\d)", r"HAT-P-\2", s)
            # WASP-94A → WASP-94 A
            s = re.sub(r"(?i)^(WASP-\d+)([AB])$", r"\1 \2", s)
            candidates.append(s)
            # exoplanet.eu often appends " A" to single-star WASP systems
            # e.g. SIMBAD "WASP-12" → try "WASP-12 A" as well
            if re.match(r"(?i)^WASP-\d+$", s):
                candidates.append(s + " A")
            if re.match(r"(?i)^HAT-P-\d+$", s):
                candidates.append(s + " A")
            if re.match(r"(?i)^HD \d+$", s):
                candidates.append(s + " A")

    # NAME designation: strip "NAME " prefix
    name_val = str(designations.get("NAME") or "").strip()
    if name_val.upper().startswith("NAME "):
        candidates.append(name_val[5:].strip())
    elif name_val:
        candidates.append(name_val)

    # MAIN_ID: strip leading "* ", "V* ", "NAME " SIMBAD prefixes
    main_id = str(designations.get("MAIN_ID") or "").strip()
    for prefix in ("NAME ", "V* ", "* "):
        if main_id.upper().startswith(prefix.upper()):
            main_id = main_id[len(prefix):].strip()
            break
    if main_id:
        candidates.append(main_id)

    return candidates


def _query_eu(designations):
    """Search exoplanet.eu for designations; return sorted list of planet rows or None."""
    _, index = _load_eu()
    candidates = _get_eu_candidates(designations)

    for name in candidates:
        key = name.lower()
        if key in index:
            rows = index[key]
            # Sort by semi_major_axis ascending (N/A last)
            def sort_key(r):
                try:
                    return (0, float(r.get("semi_major_axis", "") or ""))
                except (ValueError, TypeError):
                    return (1, 0)
            return sorted(rows, key=sort_key)

    return None


def _eu_val(row, col):
    """Return stripped non-empty string value from row, or None if missing/NaN."""
    v = row.get(col, "")
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def _display_eu_star_properties(rows):
    """Print Star Properties table using the first matching planet row for star fields."""
    row = rows[0]

    def _fmt_f(col, dp):
        v = _eu_val(row, col)
        try:
            return f"{float(v):.{dp}f}"
        except (TypeError, ValueError):
            return "N/A"

    def _fmt_i(col):
        v = _eu_val(row, col)
        try:
            return str(int(float(v)))
        except (TypeError, ValueError):
            return "N/A"

    dist = _eu_val(row, "star_distance")
    parsecs_str = _fmt_f("star_distance", 4)
    ly_str = "N/A"
    if dist:
        try:
            ly_str = f"{float(dist) * 3.26156:.4f}"
        except (TypeError, ValueError):
            pass

    _print_table(
        headers1=["Spectral", "MagV",           "Temp",       "Mass",        "Radius",       "Fe/H",           "Age",         "Parsecs",     "LYs"],
        headers2=["Type",     "",               "",           "",            "",             "",               "",            "",            ""],
        rows=[[
            _eu_val(row, "star_sp_type") or "N/A",
            _fmt_f("mag_v", 3),
            _fmt_i("star_teff"),
            _fmt_f("star_mass", 3),
            _fmt_f("star_radius", 3),
            _fmt_f("star_metallicity", 3),
            _fmt_f("star_age", 2),
            parsecs_str,
            ly_str,
        ]],
        aligns=["l", "r", "r", "r", "r", "r", "r", "r", "r"],
    )
    print()


def _display_eu_planet_properties(rows):
    """Print Planet Properties table; one row per planet."""

    def _fv(v):
        try:
            f = float(v)
            return None if _math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    def _fmt_f(v, dp):
        f = _fv(v)
        return f"{f:.{dp}f}" if f is not None else "N/A"

    def _fmt_i(v):
        f = _fv(v)
        return str(int(f)) if f is not None else "N/A"

    planet_rows = []
    for idx, row in enumerate(rows, 1):
        pname   = _eu_val(row, "name") or "N/A"
        mass_j  = _fv(_eu_val(row, "mass"))
        mass_j_s = f"{mass_j:.4f}" if mass_j is not None else "N/A"
        mass_e   = f"{mass_j * 317.8:.2f}" if mass_j is not None else "N/A"

        rad_j   = _fv(_eu_val(row, "radius"))
        rad_j_s  = f"{rad_j:.4f}" if rad_j is not None else "N/A"
        rad_e    = f"{rad_j * 11.2:.2f}" if rad_j is not None else "N/A"

        period  = _fmt_f(_eu_val(row, "orbital_period"), 3)
        temp_s  = _fmt_i(_eu_val(row, "temp_calculated"))

        sma_v   = _fv(_eu_val(row, "semi_major_axis"))
        ecc_v   = _fv(_eu_val(row, "eccentricity"))
        ecc_s   = f"{ecc_v:.3f}" if ecc_v is not None else "N/A"

        if sma_v is not None:
            sma_s = f"{sma_v:.3f}"
            if ecc_v is not None:
                peri = f"{sma_v * (1 - ecc_v):.3f}"
                apo  = f"{sma_v * (1 + ecc_v):.3f}"
                dist_s = f"{peri} - {sma_s} - {apo} AU"
            else:
                dist_s = f"N/A - {sma_s} - N/A AU"
        else:
            dist_s = "N/A"

        method  = _eu_val(row, "detection_type") or "N/A"
        year    = _eu_val(row, "discovered") or "N/A"
        status  = _eu_val(row, "planet_status") or "N/A"

        planet_rows.append([
            str(idx), pname, mass_j_s, mass_e, rad_j_s, rad_e,
            period, dist_s, ecc_s, temp_s, method, year, status,
        ])

    _print_table(
        headers1=["#", "Planet Name", "Mass(J)",  "Mass(E)", "Rad(J)",  "Rad(E)", "Period",   "Distance (Peri - SMA - Apo)", "Eccentricity", "Temp", "Method",     "Year", "Status"],
        headers2=["",  "",            "",          "",        "",        "",       "(days)",   "",                           "",             "",    "",           "",    ""],
        rows=planet_rows,
        aligns=["r", "l", "r", "r", "r", "r", "r", "r", "r", "r", "l", "r", "l"],
    )
    print()


def _display_eu_results(designations, rows):
    """Render all Exoplanet EU result tables."""

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# Exoplanet EU Encyclopaedia #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    # ── Star Name line ─────────────────────────────────────────────────────────
    eu_star = rows[0].get("star_name", "").strip()
    id_parts = [str(designations[k]) for k in ("HD", "HIP", "HR", "GJ")
                if designations.get(k)]
    if id_parts:
        star_line = f"Star Name: {eu_star}  ({', '.join(id_parts)})"
    else:
        main_id = str(designations.get("MAIN_ID") or "").strip().lstrip("*").strip()
        star_line = f"Star Name: {eu_star}  ({main_id})" if main_id and main_id != eu_star else f"Star Name: {eu_star}"
    sep = "-" * len(star_line)
    print(sep)
    print(star_line)
    print(sep)
    print()

    # ── Star Properties ───────────────────────────────────────────────────────
    _display_eu_star_properties(rows)

    # ── Planet Properties ─────────────────────────────────────────────────────
    _display_eu_planet_properties(rows)

    # ── Calculated Habitable Zone ─────────────────────────────────────────────
    row = rows[0]
    hz_row = {
        "st_teff": _eu_val(row, "star_teff"),
        "st_rad":  _eu_val(row, "star_radius"),
        "st_lum":  None,
    }
    _display_habitable_zone([hz_row])


def query_exoplanet_eu():
    """Query the Exoplanet EU Encyclopaedia for a star's exoplanet data."""
    os.system("cls" if os.name == "nt" else "clear")
    designation = input(
        "\nEnter star designation (e.g., 'tau Ceti', 'HD 209458', 'WASP-12'): "
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

    # ── Load and query Exoplanet EU ───────────────────────────────────────────
    print("Loading Exoplanet EU Encyclopaedia...")
    try:
        eu_rows = _query_eu(designations)
    except Exception as e:
        print(f"Error loading Exoplanet EU Encyclopaedia: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if eu_rows is None:
        print("No data found in the Exoplanet EU Encyclopaedia for this star.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Display ───────────────────────────────────────────────────────────────
    os.system("cls" if os.name == "nt" else "clear")
    _display_results(simbad_result, designations)
    _display_eu_results(designations, eu_rows)

    input("\nPress Enter to Return to the Main Menu")


# ─── Star Systems CSV Query ───────────────────────────────────────────────────

_CSV_PREFIX_MAP = [
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

_CSV_DESIG_KEYS = [
    "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
    "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
    "TIC", "Gaia EDR3", "2MASS",
]


def _parse_designations_from_ids(ids_string):
    """Parse a pipe-separated SIMBAD ids string into a comma-separated designation string.

    Returns a string of found designations (excluding MAIN_ID), or an empty string.
    """
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


def _run_simbad_csv_query(simbad, criteria, query_num, existing_ids):
    """Run one SIMBAD criteria query and return (new_rows, discarded) deduped against existing_ids.

    existing_ids is a set of Star Name strings already committed; updated in-place as new rows
    are accepted so that a second call automatically skips duplicates from the first query.
    """
    import warnings
    print(f"Query {query_num}: {criteria}")
    print(f"  Querying SIMBAD (this may take up to 8 minutes)...")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = simbad.query_criteria(criteria)
    except Exception as e:
        print(f"  Error querying SIMBAD: {e}")
        return [], 0

    if result is None or len(result) == 0:
        print(f"  No results returned.")
        return [], 0

    print(f"  Retrieved {len(result)} rows. Processing...")

    seen_main_ids = {}   # main_id -> index in new_rows (within this query's batch)
    new_rows = []
    discarded = 0

    for row in result:
        main_id = str(row["main_id"]).strip() if row["main_id"] is not None else ""
        ids_str = str(row["ids"]).strip() if row["ids"] is not None else ""
        sp_type = str(row["sp_type"]).strip() if row["sp_type"] is not None else ""
        if sp_type.lower() in ("", "none", "--"):
            sp_type = ""

        desig_str = _parse_designations_from_ids(ids_str)

        # Discard rule: PLX-prefixed main_id with no other designations and no sp_type
        if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":
            discarded += 1
            continue

        # If already seen this star within this batch, skip
        if main_id in seen_main_ids:
            continue

        # Skip stars already present from a prior query or the existing CSV
        if main_id in existing_ids:
            continue

        # Parallax / distance
        try:
            plx_f = float(row["plx_value"])
            plx = f"{plx_f:.4f}"
            parsecs = f"{1000.0 / plx_f:.3f}" if plx_f > 0 else ""
            ly = f"{1000.0 / plx_f * 3.26156:.3f}" if plx_f > 0 else ""
        except (TypeError, ValueError, ZeroDivisionError):
            plx = parsecs = ly = ""

        # Apparent magnitude
        try:
            vmag_f = float(row["V"])
            vmag = f"{vmag_f:.3f}"
        except (TypeError, ValueError):
            vmag = ""

        try:
            ra_deg = float(row["ra"])
            ra_h = int(ra_deg / 15)
            ra_m = int((ra_deg / 15 - ra_h) * 60)
            ra_s = ((ra_deg / 15 - ra_h) * 60 - ra_m) * 60
            ra = f"{ra_h:02d} {ra_m:02d} {ra_s:07.4f}"
        except (TypeError, ValueError):
            ra = ""

        try:
            dec_deg = float(row["dec"])
            dec_sign = "-" if dec_deg < 0 else "+"
            dec_abs = abs(dec_deg)
            dec_d = int(dec_abs)
            dec_m = int((dec_abs - dec_d) * 60)
            dec_s = ((dec_abs - dec_d) * 60 - dec_m) * 60
            dec = f"{dec_sign}{dec_d:02d} {dec_m:02d} {dec_s:06.3f}"
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

    print(f"  Discarded (PLX/no-desig/no-sptype): {discarded}  |  New unique rows: {len(new_rows)}")
    return new_rows, discarded


def query_star_systems_csv():
    """Query SIMBAD by criteria and write results to starSystems.csv."""
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 60)
    print("   STAR SYSTEMS CSV QUERY")
    print("=" * 60)
    print()

    simbad = Simbad()
    simbad.TIMEOUT = 480
    simbad.add_votable_fields("sp_type", "plx_value", "V", "ids")

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starSystems.csv")
    fieldnames = [
        "Star Name", "Star Designations", "Spectral Type", "Parallax",
        "Parsecs", "Light Years", "Apparent Magnitude", "RA", "DEC",
    ]

    # Rename existing CSV to backup before overwriting
    if os.path.exists(csv_path):
        date_stamp = datetime.now().strftime("%Y%m%d")
        backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"starSystemsBackup-{date_stamp}.csv")
        os.rename(csv_path, backup_path)
        print(f"  Backed up existing CSV to: starSystemsBackup-{date_stamp}.csv")
        print()

    # Load existing CSV so both queries can dedup against it
    existing_rows = []
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_rows.append(r)

    existing_ids = {r["Star Name"] for r in existing_rows}

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

    all_new_rows = []
    total_discarded = 0

    for i, criteria in enumerate(queries, start=1):
        new_rows, discarded = _run_simbad_csv_query(simbad, criteria, i, existing_ids)
        all_new_rows.extend(new_rows)
        total_discarded += discarded
        print()

    all_new_rows.sort(key=lambda r: float(r["Light Years"]) if r["Light Years"] else float("inf"))

    existing_rows.extend(all_new_rows)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"Done.")
    print(f"  Total rows discarded (PLX/no-desig/no-sptype): {total_discarded}")
    print(f"  Total new rows written:                        {len(all_new_rows)}")
    print(f"  Total rows in starSystems.csv:                 {len(existing_rows)}")
    print(f"\nOutput: {csv_path}")

    input("\nPress Enter to Return to the Main Menu")


# ─── Calculators ──────────────────────────────────────────────────────────────

def _lookup_star_for_distance(designation):
    """Query SIMBAD for RA, DEC, parallax, and designations.
    Returns (name, ra_deg, dec_deg, ly, desig_str) or None on failure.
    desig_str contains NAME/HD/HR/GJ/Wolf designations (comma-separated).
    """
    norm = designation.strip().lower()
    if norm in ("sun", "sol"):
        return (designation.strip(), 0.0, 0.0, 0.0, "")

    print(f"\nQuerying SIMBAD for '{designation}'...")
    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("plx_value")

    try:
        result     = custom_simbad.query_object(designation)
        ids_result = Simbad.query_objectids(designation)
    except Exception as e:
        print(f"  Error querying SIMBAD: {e}")
        return None

    if result is None:
        print(f"  No results found for '{designation}'.")
        return None

    row = result[0]
    col_names = result.colnames

    ra_raw  = _safe_get(row, col_names, "ra")
    dec_raw = _safe_get(row, col_names, "dec")
    plx_raw = _safe_get(row, col_names, "plx_value")

    try:
        ra_deg  = float(ra_raw)
        dec_deg = float(dec_raw)
    except (TypeError, ValueError):
        print(f"  Could not read RA/DEC for '{designation}'.")
        return None

    try:
        plx_f = float(plx_raw)
        if plx_f <= 0:
            raise ValueError("non-positive parallax")
        ly = 1000.0 / plx_f * 3.26156
    except (TypeError, ValueError, ZeroDivisionError):
        print(f"  Could not read valid parallax for '{designation}'.")
        return None

    name = str(_safe_get(row, col_names, "main_id") or designation)

    # Build short designation string: NAME, HD, HR, GJ, Wolf only
    desig_parts = []
    desig_found = {k: None for k in ("NAME", "HD", "HR", "GJ", "Wolf")}
    desig_prefix_map = [
        ("NAME ",  "NAME"),
        ("HD ",    "HD"),
        ("HR ",    "HR"),
        ("GJ ",    "GJ"),
        ("Wolf ",  "Wolf"),
    ]
    if ids_result is not None:
        for id_row in ids_result:
            id_str = str(id_row["id"]).strip()
            for prefix, key in desig_prefix_map:
                if id_str.startswith(prefix) and desig_found[key] is None:
                    desig_found[key] = id_str
                    break
    for key in ("NAME", "HD", "HR", "GJ", "Wolf"):
        if desig_found[key]:
            desig_parts.append(desig_found[key])
    desig_str = ", ".join(desig_parts)

    return (name, ra_deg, dec_deg, ly, desig_str)


def query_distance_between_stars():
    """Compute the 3D distance in light years between two star systems using SIMBAD."""
    import math
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 50)
    print("   DISTANCE BETWEEN 2 STARS")
    print("=" * 50)
    print()

    name1 = input("Enter Star Name 1: ").strip()
    if not name1:
        print("No star name entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    name2 = input("Enter Star Name 2: ").strip()
    if not name2:
        print("No star name entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    s1 = _lookup_star_for_distance(name1)
    s2 = _lookup_star_for_distance(name2)

    if s1 is None or s2 is None:
        input("\nPress Enter to Return to the Main Menu")
        return

    label1, ra1_deg, dec1_deg, ly1, desig1 = s1
    label2, ra2_deg, dec2_deg, ly2, desig2 = s2

    # Convert to radians
    ra1_r  = math.radians(ra1_deg)
    dec1_r = math.radians(dec1_deg)
    ra2_r  = math.radians(ra2_deg)
    dec2_r = math.radians(dec2_deg)

    # Cartesian coordinates (light years)
    x1 = ly1 * math.cos(dec1_r) * math.cos(ra1_r)
    y1 = ly1 * math.cos(dec1_r) * math.sin(ra1_r)
    z1 = ly1 * math.sin(dec1_r)

    x2 = ly2 * math.cos(dec2_r) * math.cos(ra2_r)
    y2 = ly2 * math.cos(dec2_r) * math.sin(ra2_r)
    z2 = ly2 * math.sin(dec2_r)

    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    # Format RA/DEC as sexagesimal for display
    def fmt_ra(deg):
        h = int(deg / 15)
        m = int((deg / 15 - h) * 60)
        s = ((deg / 15 - h) * 60 - m) * 60
        return f"{h:02d} {m:02d} {s:07.4f}"

    def fmt_dec(deg):
        sign = "-" if deg < 0 else "+"
        a = abs(deg)
        d = int(a); m = int((a - d) * 60)
        s = ((a - d) * 60 - m) * 60
        return f"{sign}{d:02d} {m:02d} {s:06.3f}"

    print()
    _print_table(
        ["Star", "Star Designations", "RA", "DEC", "Light Years"],
        ["",     "",                  "",   "",    ""],
        [
            [label1, desig1, fmt_ra(ra1_deg), fmt_dec(dec1_deg), f"{ly1:.4f}"],
            [label2, desig2, fmt_ra(ra2_deg), fmt_dec(dec2_deg), f"{ly2:.4f}"],
        ],
        ["l", "l", "r", "r", "r"],
    )
    print()
    print(f"  Distance Between {label1} and {label2}:")
    print(f"  {distance_ly:.4f} Light Years")
    if distance_ly < 0.5:
        distance_au = distance_ly * 63241.077
        print(f"  {distance_au:.2f} AU")
    print()

    input("\nPress Enter to Return to the Main Menu")


def query_stars_within_distance():
    """List all stars in starSystems.csv within a given distance of Sol."""
    import csv
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 50)
    print("   STARS WITHIN A CERTAIN DISTANCE OF SOL")
    print("=" * 50)
    print()

    # Prompt for distance limit
    while True:
        raw = input("Enter distance limit in Light Years: ").strip()
        if not raw:
            print("No distance entered.")
            input("\nPress Enter to Return to the Main Menu")
            return
        try:
            limit_ly = float(raw)
            if limit_ly <= 0:
                print("  Distance must be greater than 0.")
                continue
            break
        except ValueError:
            print("  Please enter a valid number.")

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starSystems.csv")
    if not os.path.exists(csv_path):
        print("\n  starSystems.csv not found. Run option 50 first to generate it.")
        input("\nPress Enter to Return to the Main Menu")
        return

    matches = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ly = float(row["Light Years"])
                except (ValueError, KeyError):
                    continue
                if ly <= limit_ly:
                    matches.append({
                        "Star Name":        row.get("Star Name", ""),
                        "Star Designations": row.get("Star Designations", ""),
                        "Spectral Type":    row.get("Spectral Type", ""),
                        "Light Years":      ly,
                    })
    except Exception as e:
        print(f"\n  Error reading starSystems.csv: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    matches.sort(key=lambda r: r["Light Years"])

    print()
    if not matches:
        print(f"  No stars found within {limit_ly} light years.")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"  Stars within {limit_ly} light years of Sol: {len(matches)}")
    print()

    _print_table(
        ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
        ["",          "",                  "",              ""],
        [[r["Star Name"], r["Star Designations"], r["Spectral Type"], f"{r['Light Years']:.3f}"]
         for r in matches],
        ["l", "l", "l", "r"],
    )
    print()

    input("\nPress Enter to Return to the Main Menu")


def query_stars_within_distance_of_star():
    """List all stars in starSystems.csv within a given distance of a queried star."""
    import csv, math
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 50)
    print("   STARS WITHIN A CERTAIN DISTANCE OF A STAR")
    print("=" * 50)
    print()

    star_name = input("Enter Star System Name: ").strip()
    if not star_name:
        print("No star name entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    while True:
        raw = input("Enter distance limit in Light Years: ").strip()
        if not raw:
            print("No distance entered.")
            input("\nPress Enter to Return to the Main Menu")
            return
        try:
            limit_ly = float(raw)
            if limit_ly <= 0:
                print("  Distance must be greater than 0.")
                continue
            break
        except ValueError:
            print("  Please enter a valid number.")

    # Look up the target star via SIMBAD (reuses existing helper)
    s = _lookup_star_for_distance(star_name)
    if s is None:
        input("\nPress Enter to Return to the Main Menu")
        return
    center_label, center_ra_deg, center_dec_deg, center_ly, _ = s

    # Convert center star to Cartesian (ly)
    def to_cartesian(ra_deg, dec_deg, ly):
        ra_r  = math.radians(ra_deg)
        dec_r = math.radians(dec_deg)
        return (
            ly * math.cos(dec_r) * math.cos(ra_r),
            ly * math.cos(dec_r) * math.sin(ra_r),
            ly * math.sin(dec_r),
        )

    # Parse sexagesimal RA "HH MM SS.SSSS" → decimal degrees
    def parse_ra(s):
        parts = s.strip().split()
        h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return (h + m / 60 + sec / 3600) * 15

    # Parse sexagesimal DEC "±DD MM SS.SSS" → decimal degrees
    def parse_dec(s):
        s = s.strip()
        sign = -1 if s.startswith("-") else 1
        parts = s.lstrip("+-").split()
        d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return sign * (d + m / 60 + sec / 3600)

    cx, cy, cz = to_cartesian(center_ra_deg, center_dec_deg, center_ly)

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starSystems.csv")
    if not os.path.exists(csv_path):
        print("\n  starSystems.csv not found. Run option 50 first to generate it.")
        input("\nPress Enter to Return to the Main Menu")
        return

    matches = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    plx = float(row["Parallax"])
                    if plx <= 0:
                        continue
                    ly = 1000.0 / plx * 3.26156
                    ra_deg  = parse_ra(row["RA"])
                    dec_deg = parse_dec(row["DEC"])
                except (ValueError, KeyError):
                    continue
                x, y, z = to_cartesian(ra_deg, dec_deg, ly)
                dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
                if 0.001 < dist <= limit_ly:
                    matches.append({
                        "Star Name":         row.get("Star Name", ""),
                        "Star Designations": row.get("Star Designations", ""),
                        "Spectral Type":     row.get("Spectral Type", ""),
                        "Distance":          dist,
                    })
    except Exception as e:
        print(f"\n  Error reading starSystems.csv: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    matches.sort(key=lambda r: r["Distance"])

    print()
    if not matches:
        print(f"  No stars found within {limit_ly} light years of {center_label}.")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"  Stars within {limit_ly} light years of {center_label}: {len(matches)}")
    print()

    _print_table(
        ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
        ["",          "",                  "",              ""],
        [[r["Star Name"], r["Star Designations"], r["Spectral Type"], f"{r['Distance']:.3f}"]
         for r in matches],
        ["l", "l", "l", "r"],
    )
    print()

    input("\nPress Enter to Return to the Main Menu")


def ly_per_hour_to_speed_of_light():
    while True:
        raw = input("Enter velocity in light years per hour: ").strip()
        try:
            ly_hr = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    # 1 light year per hour = 8765.8128 times the speed of light
    # (hours in a year = 365.25 * 24 = 8765.8128)
    times_c = ly_hr * 8765.8128
    print(f"\n  {ly_hr} ly/hr = {times_c:.6f}x the speed of light")
    input("\nPress Enter to Return to the Main Menu")


def speed_of_light_to_ly_per_hour():
    while True:
        raw = input("Enter velocity in X times the speed of light: ").strip()
        try:
            times_c = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    ly_hr = times_c / 8765.8128
    print(f"\n  {times_c}x the speed of light = {ly_hr:.6f} ly/hr")
    input("\nPress Enter to Return to the Main Menu")


def distance_traveled_ly_per_hour():
    while True:
        raw = input("Enter travel time in hours: ").strip()
        try:
            hours = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    while True:
        raw = input("Enter the velocity in light years per hour: ").strip()
        try:
            ly_hr = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    distance = ly_hr * hours
    print(f"\n  Traveling at {ly_hr} ly/hr for {hours} hours covers {distance:.6f} light years")
    input("\nPress Enter to Return to the Main Menu")


def distance_traveled_times_c():
    while True:
        raw = input("Enter travel time in hours: ").strip()
        try:
            hours = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    while True:
        raw = input("Enter the velocity X times the speed of light: ").strip()
        try:
            times_c = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    ly_hr = times_c / 8765.8128
    distance = ly_hr * hours
    print(f"\n  Traveling at {times_c}x the speed of light for {hours} hours covers {distance:.6f} light years")
    input("\nPress Enter to Return to the Main Menu")


def _format_travel_time(total_hours):
    """Break total_hours into years, months, days, hours, minutes, seconds.
    Only includes units that are >= 1 (or seconds if < 1 minute)."""
    HOURS_PER_YEAR  = 365.25 * 24          # 8765.82
    HOURS_PER_MONTH = HOURS_PER_YEAR / 12  # ~730.485
    HOURS_PER_DAY   = 24.0
    HOURS_PER_MIN   = 1 / 60.0
    HOURS_PER_SEC   = 1 / 3600.0

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
    # Always show seconds if nothing larger applies, or if < 1 minute total
    if seconds >= 0.005 and (not parts or total_hours < HOURS_PER_MIN):
        parts.append(f"{seconds:.2f} Second{'s' if seconds != 1.0 else ''}")

    return ", ".join(parts) if parts else "0 Seconds"


def time_to_travel_ly_at_ly_per_hour():
    while True:
        raw = input("Enter number of light years: ").strip()
        try:
            distance_ly = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    while True:
        raw = input("Enter velocity in light years per hour: ").strip()
        try:
            ly_hr = float(raw)
            if ly_hr <= 0:
                print("Velocity must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    total_hours = distance_ly / ly_hr
    times_c     = ly_hr * 8765.8128
    travel_time = _format_travel_time(total_hours)

    # Build table rows
    col1 = "Distance (LYs)"
    col2 = "LY/HR"
    col3 = "X Times Speed of Light"
    col4 = "Travel Time (Hours)"
    col5 = "Travel Time"

    v1 = f"{distance_ly:.6f}"
    v2 = f"{ly_hr:.6f}"
    v3 = f"{times_c:.6f}"
    v4 = f"{total_hours:.6f}"
    v5 = travel_time

    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))
    w3 = max(len(col3), len(v3))
    w4 = max(len(col4), len(v4))
    w5 = max(len(col5), len(v5))

    sep = "  "
    header = (col1.ljust(w1) + sep + col2.ljust(w2) + sep +
              col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5))
    row    = (v1.ljust(w1)   + sep + v2.ljust(w2)   + sep +
              v3.ljust(w3)   + sep + v4.ljust(w4)   + sep + v5.ljust(w5))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def time_to_travel_ly_at_times_c():
    while True:
        raw = input("Enter number of light years: ").strip()
        try:
            distance_ly = float(raw)
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    while True:
        raw = input("Enter velocity in X times the speed of light: ").strip()
        try:
            times_c = float(raw)
            if times_c <= 0:
                print("Velocity must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    ly_hr       = times_c / 8765.8128
    total_hours = distance_ly / ly_hr
    travel_time = _format_travel_time(total_hours)

    col1 = "Distance (LYs)"
    col2 = "X Times Speed of Light"
    col3 = "LY/HR"
    col4 = "Travel Time (Hours)"
    col5 = "Travel Time"

    v1 = f"{distance_ly:.6f}"
    v2 = f"{times_c:.6f}"
    v3 = f"{ly_hr:.6f}"
    v4 = f"{total_hours:.6f}"
    v5 = travel_time

    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))
    w3 = max(len(col3), len(v3))
    w4 = max(len(col4), len(v4))
    w5 = max(len(col5), len(v5))

    sep = "  "
    header = (col1.ljust(w1) + sep + col2.ljust(w2) + sep +
              col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5))
    row    = (v1.ljust(w1)   + sep + v2.ljust(w2)   + sep +
              v3.ljust(w3)   + sep + v4.ljust(w4)   + sep + v5.ljust(w5))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def _travel_time_between_stars(velocity_label, velocity_prompt, use_times_c):
    """Shared logic for functions 21 and 22.
    use_times_c=False  → velocity input is ly/hr, col order: dist, ly/hr, xc
    use_times_c=True   → velocity input is X times c,  col order: dist, xc, ly/hr
    """
    import math

    origin_name = input("Enter origin star: ").strip()
    if not origin_name:
        print("No star name entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    dest_name = input("Enter destination star: ").strip()
    if not dest_name:
        print("No star name entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    while True:
        raw = input(velocity_prompt).strip()
        try:
            velocity = float(raw)
            if velocity <= 0:
                print("Velocity must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    s1 = _lookup_star_for_distance(origin_name)
    s2 = _lookup_star_for_distance(dest_name)

    if s1 is None or s2 is None:
        input("\nPress Enter to Return to the Main Menu")
        return

    label1, ra1_deg, dec1_deg, ly1, _ = s1
    label2, ra2_deg, dec2_deg, ly2, _ = s2

    ra1_r  = math.radians(ra1_deg);  dec1_r = math.radians(dec1_deg)
    ra2_r  = math.radians(ra2_deg);  dec2_r = math.radians(dec2_deg)

    x1 = ly1 * math.cos(dec1_r) * math.cos(ra1_r)
    y1 = ly1 * math.cos(dec1_r) * math.sin(ra1_r)
    z1 = ly1 * math.sin(dec1_r)
    x2 = ly2 * math.cos(dec2_r) * math.cos(ra2_r)
    y2 = ly2 * math.cos(dec2_r) * math.sin(ra2_r)
    z2 = ly2 * math.sin(dec2_r)

    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    if use_times_c:
        times_c = velocity
        ly_hr   = times_c / 8765.8128
    else:
        ly_hr   = velocity
        times_c = ly_hr * 8765.8128

    total_hours = distance_ly / ly_hr
    travel_time = _format_travel_time(total_hours)

    col0 = "Origin"
    col1 = "Destination"
    col2 = "Distance (LYs)"
    col3 = "X Times Speed of Light" if use_times_c else "LY/HR"
    col4 = "LY/HR"                  if use_times_c else "X Times Speed of Light"
    col5 = "Travel Time (Hours)"
    col6 = "Travel Time"

    v0 = label1
    v1 = label2
    v2 = f"{distance_ly:.6f}"
    v3 = f"{times_c:.6f}"          if use_times_c else f"{ly_hr:.6f}"
    v4 = f"{ly_hr:.6f}"            if use_times_c else f"{times_c:.6f}"
    v5 = f"{total_hours:.6f}"
    v6 = travel_time

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))
    w3 = max(len(col3), len(v3))
    w4 = max(len(col4), len(v4))
    w5 = max(len(col5), len(v5))
    w6 = max(len(col6), len(v6))

    sep = "  "
    header = (col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
              col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5) + sep + col6.ljust(w6))
    row    = (v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)   + sep +
              v3.ljust(w3)   + sep + v4.ljust(w4)   + sep + v5.ljust(w5)   + sep + v6.ljust(w6))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def travel_time_between_stars_ly_hr():
    _travel_time_between_stars(
        velocity_label="ly/hr",
        velocity_prompt="Enter velocity in light years per hour: ",
        use_times_c=False,
    )


def travel_time_between_stars_times_c():
    _travel_time_between_stars(
        velocity_label="x c",
        velocity_prompt="Enter velocity in X times the speed of light: ",
        use_times_c=True,
    )


def distance_traveled_at_acceleration():
    """Brachistochrone distance for three profiles (non-relativistic, v <= 0.3% c):
      1. Continuous to halfway point: accel t/2, flip, decel t/2.
      2. Half continuous accel time, coast, then decel:
           accel t/4, coast t/2, decel t/4.
      3. Accelerate to 0.3% c, coast, then decel:
           accel to v_cap, coast, decel from v_cap.
    """

    while True:
        raw = input("Enter Acceleration in # of g's: ").strip()
        try:
            g_count = float(raw)
            if g_count <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Travel Time in Hours: ").strip()
        try:
            travel_hours = float(raw)
            if travel_hours <= 0:
                print("Travel time must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Physical constants
    G_MS2    = 9.80665            # 1 g in m/s²
    C_MS     = 299_792_458.0      # speed of light in m/s
    V_CAP_MS = 0.003 * C_MS      # 0.3% of c in m/s
    M_PER_AU = 149_597_870_700.0  # metres per AU
    M_PER_LM = C_MS * 60.0       # metres per light-minute

    a_ms2 = g_count * G_MS2       # acceleration in m/s²
    t_sec = travel_hours * 3600.0  # total travel time in seconds

    # ── Profile 1: Continuous to Halfway Point (accel t/2, flip & decel t/2) ──
    # d = 2 × (½ × a × (t/2)²)  =  ¼ × a × t²
    t_half = t_sec / 2.0
    d1_m   = 2.0 * (0.5 * a_ms2 * t_half ** 2)
    label1 = "Continuous to Halfway Point"

    # ── Profile 2: Half Continuous Accel Time, Coast, Then Decelerate ─────────
    # Accel for t/4, coast for t/2, decel for t/4.
    # Peak velocity reached: v_peak = a × (t/4)
    t_accel2 = t_sec / 4.0
    v_peak2  = a_ms2 * t_accel2
    t_coast2 = t_sec / 2.0
    d_accel2 = 0.5 * a_ms2 * t_accel2 ** 2
    d_coast2 = v_peak2 * t_coast2
    d_decel2 = d_accel2  # symmetric deceleration covers same distance
    d2_m     = d_accel2 + d_coast2 + d_decel2
    label2   = "Half Continuous Accel Time, Coast, Then Decelerate"

    # ── Profile 3: Accelerate to 0.3% c, Coast, Then Decelerate ──────────────
    # Accel to v_cap, coast the middle, decel from v_cap.
    # Time to reach cap: t_cap = v_cap / a
    # Need 2×t_cap <= t_sec for there to be a coast phase.
    t_cap = V_CAP_MS / a_ms2
    if 2.0 * t_cap >= t_sec:
        # Not enough time to reach the cap and also decelerate — treat as
        # profile 1 kinematics (accel t/2, decel t/2) since the cap is irrelevant.
        d3_m   = d1_m
        label3 = "Accel to 0.3% c, Coast, Then Decelerate (cap not reached)"
    else:
        d_accel3 = 0.5 * a_ms2 * t_cap ** 2      # distance accelerating
        d_decel3 = d_accel3                        # symmetric decel
        t_coast3 = t_sec - 2.0 * t_cap
        d_coast3 = V_CAP_MS * t_coast3
        d3_m     = d_accel3 + d_coast3 + d_decel3
        label3   = "Accel to 0.3% c, Coast, Then Decelerate"

    travel_time_str = _format_travel_time(travel_hours)

    def to_au(m): return m / M_PER_AU
    def to_lm(m): return m / M_PER_LM

    # ── Build table ─────────────────────────────────────────────────────────
    col0 = "Acceleration Profile"
    col1 = "Acceleration (G's)"
    col2 = "Travel Time (Hours)"
    col3 = "Travel Time"
    col4 = "Distance (AU)"
    col5 = "Distance (LM)"

    g_str = f"{g_count:.4f}"
    h_str = f"{travel_hours:.6f}"

    rows = [
        (label1, g_str, h_str, travel_time_str, f"{to_au(d1_m):.4f}", f"{to_lm(d1_m):.4f}"),
        (label2, g_str, h_str, travel_time_str, f"{to_au(d2_m):.4f}", f"{to_lm(d2_m):.4f}"),
        (label3, g_str, h_str, travel_time_str, f"{to_au(d3_m):.4f}", f"{to_lm(d3_m):.4f}"),
    ]

    w0 = max(len(col0), *(len(r[0]) for r in rows))
    w1 = max(len(col1), *(len(r[1]) for r in rows))
    w2 = max(len(col2), *(len(r[2]) for r in rows))
    w3 = max(len(col3), *(len(r[3]) for r in rows))
    w4 = max(len(col4), *(len(r[4]) for r in rows))
    w5 = max(len(col5), *(len(r[5]) for r in rows))

    sep = "  "
    header  = (col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
               col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    for r in rows:
        row_str = (r[0].ljust(w0) + sep + r[1].ljust(w1) + sep + r[2].ljust(w2) + sep +
                   r[3].ljust(w3) + sep + r[4].ljust(w4) + sep + r[5].ljust(w5))
        print(f"  {row_str}")

    input("\nPress Enter to Return to the Main Menu")


def travel_time_between_system_objects():
    """Brachistochrone travel time for three profiles given distance in AU.
      1. Continuous to halfway point: accel t/2, flip, decel t/2.
           d = ¼·a·t²  →  t = 2·√(d/a)
      2. Half continuous accel time, coast, then decelerate:
           accel t/4, coast t/2, decel t/4.
           d = 3·a·t²/16  →  t = √(16d / (3a))
      3. Accelerate to 0.3% c, coast, then decelerate.
           If accel+decel distance (= a·t_cap²) >= d: use profile 1 formula.
           Else: t = 2·t_cap + (d - a·t_cap²) / v_cap
    """
    import math

    while True:
        raw = input("Enter Acceleration in # of g's: ").strip()
        try:
            g_count = float(raw)
            if g_count <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Distance in AUs: ").strip()
        try:
            distance_au = float(raw)
            if distance_au <= 0:
                print("Distance must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Physical constants
    G_MS2    = 9.80665            # 1 g in m/s²
    C_MS     = 299_792_458.0      # speed of light in m/s
    V_CAP_MS = 0.003 * C_MS      # 0.3% of c in m/s
    M_PER_AU = 149_597_870_700.0  # metres per AU
    M_PER_LM = C_MS * 60.0       # metres per light-minute

    a_ms2    = g_count * G_MS2
    d_m      = distance_au * M_PER_AU
    distance_lm = d_m / M_PER_LM

    # ── Profile 1: Continuous to Halfway Point ───────────────────────────────
    # d = ¼·a·t²  →  t = 2·√(d/a)
    t1_sec   = 2.0 * math.sqrt(d_m / a_ms2)
    t1_hours = t1_sec / 3600.0
    label1   = "Continuous to Halfway Point"

    # ── Profile 2: Half Continuous Accel Time, Coast, Then Decelerate ────────
    # accel t/4, coast t/2, decel t/4
    # d = 3·a·t²/16  →  t = √(16d / (3a))
    t2_sec   = math.sqrt((16.0 * d_m) / (3.0 * a_ms2))
    t2_hours = t2_sec / 3600.0
    label2   = "Half Continuous Accel Time, Coast, Then Decelerate"

    # ── Profile 3: Accelerate to 0.3% c, Coast, Then Decelerate ─────────────
    # t_cap = v_cap / a  (time to reach 0.3% c)
    # d_accel = ½·a·t_cap²,  d_decel = d_accel
    # combined accel+decel distance = a·t_cap²
    # If that >= d, the cap is never reached within the trip → use profile 1.
    t_cap       = V_CAP_MS / a_ms2
    d_accel_cap = 0.5 * a_ms2 * t_cap ** 2   # one-way accel distance to cap
    d_both_cap  = 2.0 * d_accel_cap           # accel + decel combined

    if d_both_cap >= d_m:
        t3_sec   = t1_sec
        t3_hours = t1_hours
        label3   = "Accel to 0.3% c, Coast, Then Decelerate (cap not reached)"
    else:
        d_coast3 = d_m - d_both_cap
        t_coast3 = d_coast3 / V_CAP_MS
        t3_sec   = 2.0 * t_cap + t_coast3
        t3_hours = t3_sec / 3600.0
        label3   = "Accel to 0.3% c, Coast, Then Decelerate"

    # ── Build table ──────────────────────────────────────────────────────────
    col0 = "Acceleration Profile"
    col1 = "Acceleration (G's)"
    col2 = "Distance (AU)"
    col3 = "Distance (LM)"
    col4 = "Travel Time (Hours)"
    col5 = "Travel Time"

    g_str  = f"{g_count:.4f}"
    au_str = f"{distance_au:.4f}"
    lm_str = f"{distance_lm:.4f}"

    rows = [
        (label1, g_str, au_str, lm_str, f"{t1_hours:.6f}", _format_travel_time(t1_hours)),
        (label2, g_str, au_str, lm_str, f"{t2_hours:.6f}", _format_travel_time(t2_hours)),
        (label3, g_str, au_str, lm_str, f"{t3_hours:.6f}", _format_travel_time(t3_hours)),
    ]

    w0 = max(len(col0), *(len(r[0]) for r in rows))
    w1 = max(len(col1), *(len(r[1]) for r in rows))
    w2 = max(len(col2), *(len(r[2]) for r in rows))
    w3 = max(len(col3), *(len(r[3]) for r in rows))
    w4 = max(len(col4), *(len(r[4]) for r in rows))
    w5 = max(len(col5), *(len(r[5]) for r in rows))

    sep = "  "
    header  = (col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
               col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    for r in rows:
        row_str = (r[0].ljust(w0) + sep + r[1].ljust(w1) + sep + r[2].ljust(w2) + sep +
                   r[3].ljust(w3) + sep + r[4].ljust(w4) + sep + r[5].ljust(w5))
        print(f"  {row_str}")

    input("\nPress Enter to Return to the Main Menu")


def travel_time_between_system_objects_lm():
    """Brachistochrone travel time for three profiles given distance in light minutes.
      1. Continuous to halfway point: accel t/2, flip, decel t/2.
           d = ¼·a·t²  →  t = 2·√(d/a)
      2. Half continuous accel time, coast, then decelerate:
           accel t/4, coast t/2, decel t/4.
           d = 3·a·t²/16  →  t = √(16d / (3a))
      3. Accelerate to 0.3% c, coast, then decelerate.
           If accel+decel distance (= a·t_cap²) >= d: use profile 1 formula.
           Else: t = 2·t_cap + (d - a·t_cap²) / v_cap
    """
    import math

    while True:
        raw = input("Enter Acceleration in # of g's: ").strip()
        try:
            g_count = float(raw)
            if g_count <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Distance in Light Minutes: ").strip()
        try:
            distance_lm = float(raw)
            if distance_lm <= 0:
                print("Distance must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Physical constants
    G_MS2    = 9.80665            # 1 g in m/s²
    C_MS     = 299_792_458.0      # speed of light in m/s
    V_CAP_MS = 0.003 * C_MS      # 0.3% of c in m/s
    M_PER_AU = 149_597_870_700.0  # metres per AU
    M_PER_LM = C_MS * 60.0       # metres per light-minute

    a_ms2       = g_count * G_MS2
    d_m         = distance_lm * M_PER_LM
    distance_au = d_m / M_PER_AU

    # ── Profile 1: Continuous to Halfway Point ───────────────────────────────
    t1_sec   = 2.0 * math.sqrt(d_m / a_ms2)
    t1_hours = t1_sec / 3600.0
    label1   = "Continuous to Halfway Point"

    # ── Profile 2: Half Continuous Accel Time, Coast, Then Decelerate ────────
    t2_sec   = math.sqrt((16.0 * d_m) / (3.0 * a_ms2))
    t2_hours = t2_sec / 3600.0
    label2   = "Half Continuous Accel Time, Coast, Then Decelerate"

    # ── Profile 3: Accelerate to 0.3% c, Coast, Then Decelerate ─────────────
    t_cap       = V_CAP_MS / a_ms2
    d_both_cap  = 2.0 * (0.5 * a_ms2 * t_cap ** 2)

    if d_both_cap >= d_m:
        t3_sec   = t1_sec
        t3_hours = t1_hours
        label3   = "Accel to 0.3% c, Coast, Then Decelerate (cap not reached)"
    else:
        d_coast3 = d_m - d_both_cap
        t_coast3 = d_coast3 / V_CAP_MS
        t3_sec   = 2.0 * t_cap + t_coast3
        t3_hours = t3_sec / 3600.0
        label3   = "Accel to 0.3% c, Coast, Then Decelerate"

    # ── Build table ──────────────────────────────────────────────────────────
    col0 = "Acceleration Profile"
    col1 = "Acceleration (G's)"
    col2 = "Distance (AU)"
    col3 = "Distance (LM)"
    col4 = "Travel Time (Hours)"
    col5 = "Travel Time"

    g_str  = f"{g_count:.4f}"
    au_str = f"{distance_au:.4f}"
    lm_str = f"{distance_lm:.4f}"

    rows = [
        (label1, g_str, au_str, lm_str, f"{t1_hours:.6f}", _format_travel_time(t1_hours)),
        (label2, g_str, au_str, lm_str, f"{t2_hours:.6f}", _format_travel_time(t2_hours)),
        (label3, g_str, au_str, lm_str, f"{t3_hours:.6f}", _format_travel_time(t3_hours)),
    ]

    w0 = max(len(col0), *(len(r[0]) for r in rows))
    w1 = max(len(col1), *(len(r[1]) for r in rows))
    w2 = max(len(col2), *(len(r[2]) for r in rows))
    w3 = max(len(col3), *(len(r[3]) for r in rows))
    w4 = max(len(col4), *(len(r[4]) for r in rows))
    w5 = max(len(col5), *(len(r[5]) for r in rows))

    sep = "  "
    header  = (col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
               col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    for r in rows:
        row_str = (r[0].ljust(w0) + sep + r[1].ljust(w1) + sep + r[2].ljust(w2) + sep +
                   r[3].ljust(w3) + sep + r[4].ljust(w4) + sep + r[5].ljust(w5))
        print(f"  {row_str}")

    input("\nPress Enter to Return to the Main Menu")


# ─── JPL Horizons Solar System Object Lookup ──────────────────────────────────

_HORIZONS_ID_MAP = {
    # Sun
    "sun":       "10",
    # Planets
    "mercury":   "199",
    "venus":     "299",
    "earth":     "399",
    "mars":      "499",
    "jupiter":   "599",
    "saturn":    "699",
    "uranus":    "799",
    "neptune":   "899",
    # Dwarf planets / TNOs
    "pluto":     "999",
    "ceres":     "1",
    "vesta":     "4",
    "pallas":    "2",
    "juno":      "3",
    "eris":      "136199",
    "makemake":  "136472",
    "haumea":    "136108",
    "sedna":     "90377",
    # Earth's Moon
    "moon":      "301",
    "luna":      "301",
    # Mars moons
    "phobos":    "401",
    "deimos":    "402",
    # Jupiter moons
    "io":        "501",
    "europa":    "502",
    "ganymede":  "503",
    "callisto":  "504",
    "amalthea":  "505",
    "himalia":   "506",
    "elara":     "507",
    "pasiphae":  "508",
    "sinope":    "509",
    "lysithea":  "510",
    "carme":     "511",
    "ananke":    "512",
    "leda":      "513",
    "thebe":     "514",
    "adrastea":  "515",
    "metis":     "516",
    # Saturn moons
    "mimas":     "601",
    "enceladus": "602",
    "tethys":    "603",
    "dione":     "604",
    "rhea":      "605",
    "titan":     "606",
    "hyperion":  "607",
    "iapetus":   "608",
    "phoebe":    "609",
    "janus":     "610",
    "epimetheus":"611",
    "helene":    "612",
    "telesto":   "613",
    "calypso":   "614",
    "atlas":     "615",
    "prometheus":"616",
    "pandora":   "617",
    "pan":       "618",
    # Uranus moons
    "ariel":     "701",
    "umbriel":   "702",
    "miranda":   "703",
    "titania":   "704",
    "oberon":    "705",
    "caliban":   "706",
    "sycorax":   "707",
    "puck":      "708",
    "portia":    "709",
    "juliet":    "710",
    "belinda":   "711",
    "cressida":  "712",
    "desdemona": "713",
    "rosalind":  "714",
    "bianca":    "715",
    "cordelia":  "716",
    "ophelia":   "717",
    # Neptune moons
    "triton":    "801",
    "nereid":    "802",
    "proteus":   "808",
    "larissa":   "807",
    "galatea":   "806",
    "despina":   "805",
    "thalassa":  "804",
    "naiad":     "803",
    # Pluto moons
    "charon":    "901",
    "nix":       "902",
    "hydra":     "903",
    "kerberos":  "904",
    "styx":      "905",
    # Common asteroids (numbered)
    "eros":      "433",
    "ida":       "243",
    "gaspra":    "951",
    "mathilde":  "253",
    "itokawa":   "25143",
    "ryugu":     "162173",
    "bennu":     "101955",
    "apophis":   "99942",
    "lutetia":   "21",
    "steins":    "2867",
    "churyumov": "67P",
    # Common comets
    "halley":    "1P",
    "encke":     "2P",
    "hale-bopp": "C/1995 O1",
    "tempel 1":  "9P",
    "wild 2":    "81P",
}


def _resolve_horizons_id(name):
    """Return a Horizons-compatible ID for the given body name.

    Checks _HORIZONS_ID_MAP first (normalized lowercase).  If not found,
    also tries just the last token of the input (handles phrases like
    "Jupiter's moon Io" → check "io").  Falls through to the raw user
    string for asteroid numbers, designations, etc.
    """
    normalized = name.strip().lower()
    if normalized in _HORIZONS_ID_MAP:
        return _HORIZONS_ID_MAP[normalized]
    tokens = normalized.split()
    if tokens and tokens[-1] in _HORIZONS_ID_MAP:
        return _HORIZONS_ID_MAP[tokens[-1]]
    # Fall through: pass raw string to Horizons (handles "433", "1998 QE2", etc.)
    return name.strip()


def _get_heliocentric_vectors(horizons_id, body_name):
    """Query JPL Horizons for current heliocentric x,y,z position in AU.

    Returns (x, y, z) as floats.  Raises on lookup failure (ambiguous name,
    not found, network error).  body_name is used only in calling code for
    error messages.
    """
    epoch = astropy.time.Time.now().jd
    obj = Horizons(id=horizons_id, location='@sun', epochs=epoch)
    vec = obj.vectors()
    return float(vec['x'][0]), float(vec['y'][0]), float(vec['z'][0])


def travel_time_between_solar_system_objects():
    """Brachistochrone travel time using live JPL Horizons positions.

    Queries current heliocentric state vectors for origin and destination,
    computes the 3D Euclidean distance in AU, then applies three
    brachistochrone acceleration profiles.  Profile 3 velocity cap is
    user-configurable (default 0.3% of c).
    """
    import math

    # ── Input: Origin ────────────────────────────────────────────────────────
    origin_name = input("Enter Origin Planet/Satellite/Asteroid: ").strip()
    if not origin_name:
        print("No origin entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Input: Destination ───────────────────────────────────────────────────
    dest_name = input("Enter Destination Planet/Satellite/Asteroid: ").strip()
    if not dest_name:
        print("No destination entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Input: Acceleration ──────────────────────────────────────────────────
    while True:
        raw = input("Enter Acceleration in # of G's: ").strip()
        try:
            g_count = float(raw)
            if g_count <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    # ── Input: Max Velocity Cap ──────────────────────────────────────────────
    raw = input(
        "Enter Max Velocity for Accelerate-to-Max-Velocity Profile "
        "(% of c, Default 0.3): "
    ).strip()
    if raw == "":
        v_cap_pct = 0.3
    else:
        try:
            v_cap_pct = float(raw)
            if v_cap_pct <= 0:
                print("Max velocity must be greater than zero. Using default 0.3%.")
                v_cap_pct = 0.3
        except ValueError:
            print("Invalid input. Using default 0.3%.")
            v_cap_pct = 0.3

    # ── Resolve Horizons IDs ──────────────────────────────────────────────────
    origin_id = _resolve_horizons_id(origin_name)
    dest_id   = _resolve_horizons_id(dest_name)

    # ── Fetch heliocentric positions ──────────────────────────────────────────
    print(f"\nQuerying JPL Horizons for '{origin_name}'...")
    try:
        ox, oy, oz = _get_heliocentric_vectors(origin_id, origin_name)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            print(f"\nAmbiguous body name '{origin_name}'. JPL Horizons returned:")
            print(err)
            print("\nTip: Use a more specific name or numeric ID (e.g., '499' for Mars).")
        else:
            print(f"\nCould not retrieve position for '{origin_name}': {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"Querying JPL Horizons for '{dest_name}'...")
    try:
        dx, dy, dz = _get_heliocentric_vectors(dest_id, dest_name)
    except Exception as e:
        err = str(e)
        if "Multiple major-bodies" in err or "ambiguous" in err.lower():
            print(f"\nAmbiguous body name '{dest_name}'. JPL Horizons returned:")
            print(err)
            print("\nTip: Use a more specific name or numeric ID (e.g., '501' for Io).")
        else:
            print(f"\nCould not retrieve position for '{dest_name}': {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Compute 3D distance in AU ─────────────────────────────────────────────
    distance_au = math.sqrt(
        (dx - ox) ** 2 + (dy - oy) ** 2 + (dz - oz) ** 2
    )

    if distance_au < 1e-9:
        print(
            f"\nOrigin and destination appear to be the same object "
            f"(distance ≈ 0 AU). Please enter two different objects."
        )
        input("\nPress Enter to Return to the Main Menu")
        return

    # ── Physical constants ────────────────────────────────────────────────────
    G_MS2    = 9.80665
    C_MS     = 299_792_458.0
    M_PER_AU = 149_597_870_700.0
    M_PER_LM = C_MS * 60.0

    a_ms2       = g_count * G_MS2
    d_m         = distance_au * M_PER_AU
    distance_lm = d_m / M_PER_LM
    V_CAP_MS    = (v_cap_pct / 100.0) * C_MS

    # ── Profile 1: Continuous to Halfway Point ───────────────────────────────
    # d = ¼·a·t²  →  t = 2·√(d/a)
    t1_sec   = 2.0 * math.sqrt(d_m / a_ms2)
    t1_hours = t1_sec / 3600.0
    label1   = "Continuous to Halfway Point"

    # ── Profile 2: Half Continuous Accel Time, Coast, Then Decelerate ────────
    # d = 3·a·t²/16  →  t = √(16d / (3a))
    t2_sec   = math.sqrt((16.0 * d_m) / (3.0 * a_ms2))
    t2_hours = t2_sec / 3600.0
    label2   = "Half Continuous Accel Time, Coast, Then Decelerate"

    # ── Profile 3: Accelerate to V_CAP, Coast, Then Decelerate ───────────────
    # t_cap = v_cap / a;  d_both_cap = a·t_cap²  (combined accel + decel dist)
    # If d_both_cap >= d: cap never reached → use Profile 1 kinematics.
    t_cap      = V_CAP_MS / a_ms2
    d_both_cap = a_ms2 * t_cap ** 2

    if d_both_cap >= d_m:
        t3_sec   = t1_sec
        t3_hours = t1_hours
        label3   = f"Accel to {v_cap_pct}% c, Coast, Then Decelerate (cap not reached)"
    else:
        d_coast3 = d_m - d_both_cap
        t_coast3 = d_coast3 / V_CAP_MS
        t3_sec   = 2.0 * t_cap + t_coast3
        t3_hours = t3_sec / 3600.0
        label3   = f"Accel to {v_cap_pct}% c, Coast, Then Decelerate"

    # ── Build and print table ─────────────────────────────────────────────────
    col0 = "Acceleration Profile"
    col1 = "Origin"
    col2 = "Destination"
    col3 = "Acceleration (G's)"
    col4 = "Distance (AU)"
    col5 = "Distance (LM)"
    col6 = "Travel Time (Hours)"
    col7 = "Travel Time"

    g_str  = f"{g_count:.4f}"
    au_str = f"{distance_au:.4f}"
    lm_str = f"{distance_lm:.4f}"

    rows = [
        (label1, origin_name, dest_name, g_str, au_str, lm_str,
         f"{t1_hours:.6f}", _format_travel_time(t1_hours)),
        (label2, origin_name, dest_name, g_str, au_str, lm_str,
         f"{t2_hours:.6f}", _format_travel_time(t2_hours)),
        (label3, origin_name, dest_name, g_str, au_str, lm_str,
         f"{t3_hours:.6f}", _format_travel_time(t3_hours)),
    ]

    w0 = max(len(col0), *(len(r[0]) for r in rows))
    w1 = max(len(col1), *(len(r[1]) for r in rows))
    w2 = max(len(col2), *(len(r[2]) for r in rows))
    w3 = max(len(col3), *(len(r[3]) for r in rows))
    w4 = max(len(col4), *(len(r[4]) for r in rows))
    w5 = max(len(col5), *(len(r[5]) for r in rows))
    w6 = max(len(col6), *(len(r[6]) for r in rows))
    w7 = max(len(col7), *(len(r[7]) for r in rows))

    sep = "  "
    header = (
        col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
        col3.ljust(w3) + sep + col4.ljust(w4) + sep + col5.ljust(w5) + sep +
        col6.ljust(w6) + sep + col7.ljust(w7)
    )
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    for r in rows:
        row_str = (
            r[0].ljust(w0) + sep + r[1].ljust(w1) + sep + r[2].ljust(w2) + sep +
            r[3].ljust(w3) + sep + r[4].ljust(w4) + sep + r[5].ljust(w5) + sep +
            r[6].ljust(w6) + sep + r[7].ljust(w7)
        )
        print(f"  {row_str}")

    input("\nPress Enter to Return to the Main Menu")


# ─── Planetary Equations ──────────────────────────────────────────────────────

def planetary_orbit_periastron_apastron():
    """Calculate periastron and apastron from semi-major axis and eccentricity.
      Periastron = SMA × (1 - e)
      Apastron   = SMA × (1 + e)
      Eccentricity (AU) = SMA × e
    """
    while True:
        raw = input("Enter the Planetary Semi-Major Axis (AU): ").strip()
        try:
            sma = float(raw)
            if sma <= 0:
                print("Semi-major axis must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter the Planetary Orbit Eccentricity: ").strip()
        try:
            ecc = float(raw)
            if ecc < 0 or ecc >= 1:
                print("Eccentricity must be between 0 (inclusive) and 1 (exclusive).")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    periastron    = sma * (1.0 - ecc)
    apastron      = sma * (1.0 + ecc)
    ecc_au        = sma * ecc

    col0 = "Periastron (AU)"
    col1 = "Semi-Major Axis (AU)"
    col2 = "Apastron (AU)"
    col3 = "Eccentricity"
    col4 = "Eccentricity (AU)"

    v0 = f"{periastron:.6f}"
    v1 = f"{sma:.6f}"
    v2 = f"{apastron:.6f}"
    v3 = f"{ecc:.6f}"
    v4 = f"{ecc_au:.6f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))
    w3 = max(len(col3), len(v3))
    w4 = max(len(col4), len(v4))

    sep    = "  "
    header = (col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep +
              col3.ljust(w3) + sep + col4.ljust(w4))
    row    = (v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)   + sep +
              v3.ljust(w3)   + sep + v4.ljust(w4))
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def moon_orbital_distance_24h():
    """Orbital distance of an Earth-sized moon with a 24-hour day.
      Uses Kepler's third law: r = (G * M_planet * T^2 / (4*pi^2))^(1/3)
      where T = 24 hours = 86400 seconds, M_planet in kg = Earth_mass * planet_mass_in_earth_masses.
    """
    import math

    EARTH_MASS_KG = 5.972e24   # kg
    G             = 6.674e-11  # m^3 kg^-1 s^-2
    T_SEC         = 86400.0    # 24 hours in seconds

    while True:
        raw = input("Enter Planetary Mass in Earth Masses: ").strip()
        try:
            mass_earth = float(raw)
            if mass_earth <= 0:
                print("Mass must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    M_kg      = mass_earth * EARTH_MASS_KG
    r_m       = (G * M_kg * T_SEC**2 / (4.0 * math.pi**2)) ** (1.0 / 3.0)
    r_km      = r_m / 1000.0

    col0 = "Planetary Mass (Earth Masses)"
    col1 = "Day Length (Hours)"
    col2 = "Orbital Distance (km)"

    v0 = f"{mass_earth:.4f}"
    v1 = "24.0000"
    v2 = f"{r_km:.4f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def moon_orbital_distance_x_hours():
    """Orbital distance of an Earth-sized moon with a user-specified day length.
      Uses Kepler's third law: r = (G * M_planet * T^2 / (4*pi^2))^(1/3)
      where T = day_hours * 3600 seconds, M_planet in kg = Earth_mass * planet_mass_in_earth_masses.
    """
    import math

    EARTH_MASS_KG = 5.972e24   # kg
    G             = 6.674e-11  # m^3 kg^-1 s^-2

    while True:
        raw = input("Enter Planetary Mass in Earth Masses: ").strip()
        try:
            mass_earth = float(raw)
            if mass_earth <= 0:
                print("Mass must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Day in Hours: ").strip()
        try:
            day_hours = float(raw)
            if day_hours <= 0:
                print("Day length must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    T_sec     = day_hours * 3600.0
    M_kg      = mass_earth * EARTH_MASS_KG
    r_m       = (G * M_kg * T_sec**2 / (4.0 * math.pi**2)) ** (1.0 / 3.0)
    r_km      = r_m / 1000.0

    col0 = "Planetary Mass (Earth Masses)"
    col1 = "Day Length (Hours)"
    col2 = "Orbital Distance (km)"

    v0 = f"{mass_earth:.4f}"
    v1 = f"{day_hours:.4f}"
    v2 = f"{r_km:.4f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


# ─── Rotating Habitat Equations ───────────────────────────────────────────────

def centrifugal_gravity_acceleration():
    """Centrifugal artificial gravity acceleration at Point X.
      a = omega^2 * r
      where omega (rad/s) = rpm * 2*pi / 60
    """
    import math

    while True:
        raw = input("Enter Rotation Rate (rpm): ").strip()
        try:
            rpm = float(raw)
            if rpm <= 0:
                print("Rotation rate must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Distance (m) from Point X to Center of Rotation: ").strip()
        try:
            r = float(raw)
            if r <= 0:
                print("Distance must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    omega = rpm * 2.0 * math.pi / 60.0
    a     = omega ** 2 * r

    col0 = "Rotation Rate (rpm)"
    col1 = "Distance from Center (m)"
    col2 = "Centrifugal Gravity (m/s^2)"

    v0 = f"{rpm:.4f}"
    v1 = f"{r:.4f}"
    v2 = f"{a:.2f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def centrifugal_gravity_distance():
    """Distance from Point X to the center of rotation.
      r = a / omega^2
      where omega (rad/s) = rpm * 2*pi / 60
    """
    import math

    while True:
        raw = input("Enter Rotation Rate (rpm): ").strip()
        try:
            rpm = float(raw)
            if rpm <= 0:
                print("Rotation rate must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X: ").strip()
        try:
            a = float(raw)
            if a <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    omega = rpm * 2.0 * math.pi / 60.0
    r     = a / omega ** 2

    col0 = "Rotation Rate (rpm)"
    col1 = "Centrifugal Gravity (m/s^2)"
    col2 = "Distance from Center (m)"

    v0 = f"{rpm:.4f}"
    v1 = f"{a:.4f}"
    v2 = f"{r:.2f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


def centrifugal_gravity_rpm():
    """Rotation rate (rpm) at Point X given gravity and distance.
      omega = sqrt(a / r)
      rpm = omega * 60 / (2*pi)
    """
    import math

    while True:
        raw = input("Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X: ").strip()
        try:
            a = float(raw)
            if a <= 0:
                print("Acceleration must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter Distance (m) from Point X to Center of Rotation: ").strip()
        try:
            r = float(raw)
            if r <= 0:
                print("Distance must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    omega = math.sqrt(a / r)
    rpm   = omega * 60.0 / (2.0 * math.pi)

    col0 = "Centrifugal Gravity (m/s^2)"
    col1 = "Distance from Center (m)"
    col2 = "Rotation Rate (rpm)"

    v0 = f"{a:.4f}"
    v1 = f"{r:.4f}"
    v2 = f"{rpm:.2f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


# ─── Misc. Equations ──────────────────────────────────────────────────────────

def _kopparapu_seff(teff, zone):
    """Return Seff boundary (Kopparapu et al. 2014) for the given zone key."""
    tS = teff - 5780.0
    params = {
        "rv":   (1.776,  2.136e-4,  2.533e-8,  -1.332e-11, -3.097e-15),
        "rg5":  (1.188,  1.433e-4,  1.707e-8,  -8.968e-12, -2.084e-15),
        "rg01": (0.99,   1.209e-4,  1.404e-8,  -7.418e-12, -1.713e-15),
        "rg":   (1.107,  1.332e-4,  1.580e-8,  -8.308e-12, -1.931e-15),
        "mg":   (0.356,  6.171e-5,  1.698e-9,  -3.198e-12, -5.575e-16),
        "em":   (0.320,  5.547e-5,  1.526e-9,  -2.874e-12, -5.011e-16),
    }
    SeffSUN, a, b, c, d = params[zone]
    return SeffSUN + a*tS + b*tS**2 + c*tS**3 + d*tS**4


def habitable_zone_calculator():
    """Habitable Zone Calculator — user supplies temperature (K) and luminosity (Lsun).
      Uses Kopparapu et al. 2014 coefficients via _kopparapu_seff().
      HZ distance (AU) = sqrt(luminosity / Seff)
    """
    import math

    while True:
        raw = input("Enter the Star's Temperature (K): ").strip()
        try:
            teff = float(raw)
            if teff <= 0:
                print("Temperature must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter the Star's Luminosity (Lsun): ").strip()
        try:
            slum = float(raw)
            if slum <= 0:
                print("Luminosity must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    AU_TO_LM = 8.3167

    zones = [
        ("Optimistic Inner HZ (Recent Venus)",                          "rv"),
        ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",   "rg5"),
        ("Conservative Inner HZ (Runaway Greenhouse)",                  "rg"),
        ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)", "rg01"),
        ("Conservative Outer HZ (Maximum Greenhouse)",                  "mg"),
        ("Optimistic Outer HZ (Early Mars)",                            "em"),
    ]

    results = []
    for name, key in zones:
        seff = _kopparapu_seff(teff, key)
        au   = math.sqrt(slum / seff)
        results.append((name, f"{au:.3f} ({au * AU_TO_LM:.3f} LM)"))

    zone_w = max(len(f" {name}") for name, _ in results)
    zone_w = max(zone_w, len(" Zone"))
    au_w   = max(len(val) for _, val in results)
    au_w   = max(au_w, len("AU"))

    title = "Calculated Habitable Zone"
    print(f"\n{'-' * len(title)}")
    print(title)
    print(f"{'-' * len(title)}")
    print()
    print(f"{' Zone'.ljust(zone_w)} | {'AU'.ljust(au_w)}")
    print("-" * zone_w + "-+-" + "-" * au_w)
    for name, val in results:
        print(f"{(' ' + name).ljust(zone_w)} | {val}")
    print()

    input("\nPress Enter to Return to the Main Menu")


def habitable_zone_calculator_sma():
    """Habitable Zone Calculator with SMA — adds Seff column and HZ verdict.
      Seff at planet = (1/SMA)^2 * luminosity  (flux relative to Earth)
      HZ distance (AU) = sqrt(luminosity / Seff_boundary)
      Output: combined table with Zone | AU | LM | Seff, then verdict.
    """
    import math

    while True:
        raw = input("Enter the Star's Temperature (K): ").strip()
        try:
            teff = float(raw)
            if teff <= 0:
                print("Temperature must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter the Star's Luminosity (Lsun): ").strip()
        try:
            slum = float(raw)
            if slum <= 0:
                print("Luminosity must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter the Object's Semi-Major Axis (AU): ").strip()
        try:
            sma = float(raw)
            if sma <= 0:
                print("Semi-major axis must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    AU_TO_LM = 8.3167
    planet_seff = ((1.0 / sma) ** 2) * slum

    zone_defs = [
        ("Optimistic Inner HZ (Recent Venus)",                          "rv"),
        ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",   "rg5"),
        ("Conservative Inner HZ (Runaway Greenhouse)",                  "rg"),
        ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)", "rg01"),
        ("Conservative Outer HZ (Maximum Greenhouse)",                  "mg"),
        ("Optimistic Outer HZ (Early Mars)",                            "em"),
    ]

    rows = []
    seff_boundaries = {}
    for name, key in zone_defs:
        seff = _kopparapu_seff(teff, key)
        seff_boundaries[key] = seff
        au   = math.sqrt(slum / seff)
        au_str   = f"{au:.3f}"
        lm_str   = f"{au * AU_TO_LM:.3f} LM"
        seff_str = f"{seff:.8f}"
        rows.append((name, au_str, lm_str, seff_str))

    col0 = " Zone"
    col1 = "AU"
    col2 = "LM"
    col3 = "Seff"

    w0 = max(len(col0), *(len(r[0]) + 1 for r in rows))  # +1 for leading space
    w1 = max(len(col1), *(len(r[1]) for r in rows))
    w2 = max(len(col2), *(len(r[2]) for r in rows))
    w3 = max(len(col3), *(len(r[3]) for r in rows))

    sep = " | "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2) + sep + col3.ljust(w3)
    divider = "-" * w0 + "-+-" + "-" * w1 + "-+-" + "-" * w2 + "-+-" + "-" * w3

    title = "Calculated Habitable Zone"
    print(f"\n{'-' * len(title)}")
    print(title)
    print(f"{'-' * len(title)}")
    print()
    print(f"  Object's Seff: {planet_seff:.8f}")
    print()
    print(header)
    print(divider)
    for name, au_str, lm_str, seff_str in rows:
        print(f"{(' ' + name).ljust(w0)}{sep}{au_str.ljust(w1)}{sep}{lm_str.ljust(w2)}{sep}{seff_str.ljust(w3)}")
    print()

    # HZ membership verdict using rg (inner conservative) and em (outer conservative/optimistic)
    seff_rv = seff_boundaries["rv"]
    seff_rg = seff_boundaries["rg"]
    seff_mg = seff_boundaries["mg"]
    seff_em = seff_boundaries["em"]

    if planet_seff < seff_em:
        verdict = "This object is NOT in the Habitable Zone (Beyond Early Mars)"
    elif planet_seff <= seff_mg:
        verdict = "This object is in the Optimistic Habitable Zone (Between Maximum Greenhouse and Early Mars)"
    elif planet_seff <= seff_rg:
        verdict = "This object is in the Conservative Habitable Zone (Between Runaway Greenhouse and Maximum Greenhouse)"
    elif planet_seff <= seff_rv:
        verdict = "This object is in the Optimistic Habitable Zone (Between Recent Venus and Runaway Greenhouse)"
    else:
        verdict = "This object is NOT in the Habitable Zone (Interior to Recent Venus)"

    print(verdict)
    print()

    input("\nPress Enter to Return to the Main Menu")


def star_luminosity_calculator():
    """Star Luminosity Calculator.
      luminosity = (radius / 1)^2 * (temperature / 5778)^4
    """
    while True:
        raw = input("Enter the Star's Radius (R\u2609): ").strip()
        try:
            radius = float(raw)
            if radius <= 0:
                print("Radius must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        raw = input("Enter the Star's Temperature (K): ").strip()
        try:
            temp = float(raw)
            if temp <= 0:
                print("Temperature must be greater than zero.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")

    luminosity = (radius ** 2) * ((temp / 5778.0) ** 4)

    col0 = "Radius (R\u2609)"
    col1 = "Temperature (K)"
    col2 = "Luminosity (Lsun)"

    v0 = f"{radius:.4f}"
    v1 = f"{temp:.4f}"
    v2 = f"{luminosity:.6f}"

    w0 = max(len(col0), len(v0))
    w1 = max(len(col1), len(v1))
    w2 = max(len(col2), len(v2))

    sep     = "  "
    header  = col0.ljust(w0) + sep + col1.ljust(w1) + sep + col2.ljust(w2)
    row     = v0.ljust(w0)   + sep + v1.ljust(w1)   + sep + v2.ljust(w2)
    divider = "-" * len(header)

    print(f"\n  {header}")
    print(f"  {divider}")
    print(f"  {row}")

    input("\nPress Enter to Return to the Main Menu")


# ─── Science Menu ─────────────────────────────────────────────────────────────

def solar_system_data_tables():
    """Display data tables for Solar System planets, moons, dwarf planets, and asteroids."""
    os.system("cls" if os.name == "nt" else "clear")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    def _read_csv(filename):
        path = os.path.join(base_dir, filename)
        try:
            with open(path, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            print(f"Warning: Could not load {filename}: {e}")
            return []

    def _au_lm(val_str):
        """Format an AU value as 'X (Y LM)', stripping trailing zeros."""
        try:
            v = float(val_str)
        except (ValueError, TypeError):
            return str(val_str)
        au_s = f"{v:g}"
        lm_s = f"{v * 8.3167:.3f}"
        return f"{au_s} ({lm_s} LM)"

    # ── Planets ───────────────────────────────────────────────────────────────
    planets = _read_csv("planetInfo.csv")
    if planets:
        title = "Solar System Planets Data"
        print(f"\n{'-' * len(title)}")
        print(title)
        print(f"{'-' * len(title)}")
        print()

        p_rows = []
        for p in planets:
            name      = p.get("Planet", "")
            mass      = p.get("Mass", "")
            diameter  = p.get("Diameter", "")
            period    = p.get("Period", "")
            peri_raw  = p.get("Periastron", "")
            sma_raw   = p.get("Semimajor Axis", "")
            apo_raw   = p.get("Apastron", "")
            ecc       = p.get("Eccentricity", "")
            moons     = p.get("Moons", "")
            p_rows.append([
                name, mass, diameter, period,
                _au_lm(peri_raw), _au_lm(sma_raw), _au_lm(apo_raw),
                ecc, moons,
            ])

        _print_table(
            headers1=[" Planet Name", "  Mass (J)", "  Diameter (J)", "Period",
                      "Periastron (AU)", "Semimajor", "Apastron (AU)",
                      "  Eccentricity", "  Moons"],
            headers2=["",             "",           "",              "",
                      "",              "Axis (AU)", "",
                      "",              ""],
            rows=p_rows,
            aligns=["l", "r", "r", "l", "l", "l", "l", "r", "r"],
        )
        print()

    # ── Moons grouped by planet ───────────────────────────────────────────────
    moons_data = _read_csv("moonInfo.csv")
    planet_order = ["Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

    def _moon_title(planet):
        if planet == "Earth":
            return "Earth Moon Data"
        elif planet in ("Neptune", "Pluto"):
            return f"{planet} Moon Data"
        else:
            return f"{planet} Moons Data"

    for planet in planet_order:
        planet_moons = [m for m in moons_data if m.get("Planet Name", "").strip() == planet]
        if not planet_moons:
            continue
        title = _moon_title(planet)
        print(f"{'-' * len(title)}")
        print(title)
        print(f"{'-' * len(title)}")
        print()

        m_rows = []
        for m in planet_moons:
            m_rows.append([
                m.get("Satellite Name", ""),
                m.get("Diameter (km)", ""),
                m.get("Mass (kg)", ""),
                m.get("Perigee (km)", ""),
                m.get("Apogee (km)", ""),
                m.get("SemiMajor Axis (km)", ""),
                m.get("Eccentricity", ""),
                m.get("Period (days)", ""),
                m.get("Gravity (m/s^2)", ""),
                m.get("Escape Velocity (km/s)", ""),
            ])

        _print_table(
            headers1=[" Satellite", "  Diameter (km)", "Mass (kg)",
                      "  Perigee (km)", "  Apogee (km)", "  SemiMajor",
                      "  Eccentricity", "  Period", "  Gravity", "           Escape"],
            headers2=[" Name",     "",                "",
                      "",           "",              "  Axis (km)",
                      "",           "  (days)",      "  (m/s^2)", "  Velocity (km/s)"],
            rows=m_rows,
            aligns=["l", "r", "l", "r", "r", "r", "r", "r", "r", "r"],
        )
        print()

    # ── Dwarf Planets ─────────────────────────────────────────────────────────
    dwarfs = _read_csv("dwarfPlanetInfo.csv")
    if dwarfs:
        title = "Solar System Dwarf Planets Data"
        print(f"{'-' * len(title)}")
        print(title)
        print(f"{'-' * len(title)}")
        print()

        d_rows = []
        for d in dwarfs:
            name     = d.get("Name", "")
            mass     = d.get("Mass", "")
            diameter = d.get("Diameter", "")
            period   = d.get("Period", "")
            peri_raw = d.get("Periastron", "")
            sma_raw  = d.get("Semimajor Axis", "")
            apo_raw  = d.get("Apastron", "")
            ecc      = d.get("Eccentricity", "")
            moons    = d.get("Moons", "")
            d_rows.append([
                name, mass, diameter, period,
                _au_lm(peri_raw), _au_lm(sma_raw), _au_lm(apo_raw),
                ecc, moons,
            ])

        _print_table(
            headers1=[" Dwarf", "  Mass (E)", "Diameter", "Period",
                      "Periastron (AU)", "Semimajor", "Apastron (AU)",
                      "  Eccentricity", "  Moons"],
            headers2=[" Planet Name", "", "", "",
                      "",             "Axis (AU)", "",
                      "",              ""],
            rows=d_rows,
            aligns=["l", "r", "l", "l", "l", "l", "l", "r", "r"],
        )
        print()

    # ── Asteroids ─────────────────────────────────────────────────────────────
    asteroids = _read_csv("asteroidsInfo.csv")
    if asteroids:
        # Sort by Semimajor Axis ascending
        def _sma_key(row):
            try:
                return float(row.get("Semimajor Axis", "0") or "0")
            except ValueError:
                return 0.0
        asteroids.sort(key=_sma_key)

        title = "Solar System Major Asteroids Data"
        print(f"{'-' * len(title)}")
        print(title)
        print(f"{'-' * len(title)}")
        print()

        a_rows = []
        for a in asteroids:
            name     = a.get("Name", "")
            diameter = a.get("Diameter", "")
            period   = a.get("Period", "")
            peri_raw = a.get("Periastron", "")
            sma_raw  = a.get("Semimajor Axis", "")
            apo_raw  = a.get("Apastron", "")
            ecc      = a.get("Eccentricity", "")
            a_rows.append([
                name, diameter, period,
                _au_lm(peri_raw), _au_lm(sma_raw), _au_lm(apo_raw),
                ecc,
            ])

        _print_table(
            headers1=[" Asteroid Name", "Diameter (KM)", "Period",
                      "Periastron (AU)", "Semimajor", "Apastron (AU)",
                      "  Eccentricity"],
            headers2=["",              "",             "",
                      "",              "Axis (AU)",   "",
                      ""],
            rows=a_rows,
            aligns=["l", "l", "l", "l", "l", "l", "r"],
        )
        print()

    input("\nPress Enter to Return to the Main Menu")


def main_sequence_star_properties():
    """Display the Main Sequence Star Properties table from propertiesOfMainSequenceStars.csv."""
    os.system("cls" if os.name == "nt" else "clear")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "propertiesOfMainSequenceStars.csv")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        print(f"Error loading propertiesOfMainSequenceStars.csv: {e}")
        input("\nPress Enter to Return to the Main Menu")
        return

    if not rows:
        print("No data found in propertiesOfMainSequenceStars.csv.")
        input("\nPress Enter to Return to the Main Menu")
        return

    title = "Main Sequence Star Properties"
    print(f"\n{'-' * len(title)}")
    print(title)
    print(f"{'-' * len(title)}")
    print()

    # Columns from CSV (in display order)
    col_keys = [
        "Spectral Class", "B-V", "Teeff(K)", "AbsMag Vis.", "AbsMag Bol.",
        "Bolo. Corr. (BC)", "Lum", "R", "M", "p (g/cm3)", "Lifetime (years)",
    ]
    headers = [
        "Spectral Class", "B-V", "Teff (K)", "Abs Mag Vis", "Abs Mag Bol",
        "BC", "Lum", "R", "M", "p (g/cm3)", "Lifetime (years)",
    ]

    table_rows = []
    for row in rows:
        table_rows.append([row.get(k, "") for k in col_keys])

    _print_table(
        headers1=headers,
        headers2=[""] * len(headers),
        rows=table_rows,
        aligns=["l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "l"],
    )
    print()

    input("\nPress Enter to Return to the Main Menu")


def sol_solar_system_regions():
    """Display Star System Regions for Sol using hardcoded solar constants."""
    os.system("cls" if os.name == "nt" else "clear")
    print()

    # Solar constants
    # Apparent magnitude of Sun as seen from Earth
    vmag              = -26.74
    # Parallax: 1 AU = 1 parsec reference; Sun is at ~1/206265 parsecs, parallax = 206265 mas
    # but for the distance formula we want parsecs = 1000/plx, so plx = 1000/parsecs.
    # The Sun is trivially 0 parsecs away, so we use a conventional reference.
    # Standard approach: use absMagnitude directly (4.83) and back-solve vmag/plx.
    # Since absMagnitude = vmag + 5 - 5*log10(parsecs), and absMag_sun = 4.83, vmag_sun = -26.74,
    # parsecs = 10^((vmag - absMag + 5) / 5) = 10^((-26.74 - 4.83 + 5)/5) = 10^(-26.57/5)
    # = 10^(-5.314) ≈ 4.85e-6 parsecs, plx = 1000/parsecs ≈ 206265 mas (correct: 1 arcsec = Sun's parallax)
    plx               = 1000.0 / (10 ** ((-26.74 - 4.83 + 5.0) / 5.0))
    boloLum           = -0.07       # Bolometric correction for G2V Sun
    temp              = 5778.0      # Effective temperature (K)
    sunlightIntensity = 1.0         # Terra = 1.0
    bondAlbedo        = 0.3         # Terra = 0.3

    parsecs          = 1000.0 / plx
    absMagnitude     = vmag + 5 - (5 * math.log10(parsecs))
    bcAbsMagnitude   = absMagnitude + boloLum
    bcLuminosity     = 2.52 ** (4.85 - bcAbsMagnitude)
    stellarMass      = bcLuminosity ** 0.2632
    luminosityFromMass = stellarMass ** 3.5
    stellarRadius    = stellarMass ** 0.57 if stellarMass >= 1 else stellarMass ** 0.8
    stellarDiameterSol = ((5780 ** 2) / (temp ** 2)) * math.sqrt(bcLuminosity)
    stellarDiameterKM  = stellarDiameterSol * 1391600
    mainSeqLifeSpan  = (10 ** 10) * ((1 / stellarMass) ** 2.5)
    trigParallax     = plx / 1000
    lightYears       = 3.2616 / trigParallax
    distAU           = math.sqrt(bcLuminosity / sunlightIntensity)
    distKM           = distAU * 149000000
    planetaryYear    = math.sqrt((distAU ** 3) / stellarMass)
    planetaryTemperature  = 374 * 1.1 * (1 - bondAlbedo) * (sunlightIntensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9 / 5) + 32
    starAngularDiameter   = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun        = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"
    sysilGrav        = 0.2 * stellarMass
    sysilSunlight    = math.sqrt(bcLuminosity / 16)
    hzil             = math.sqrt(bcLuminosity / 1.1)
    hzol             = math.sqrt(bcLuminosity / 0.53)
    snowLine         = math.sqrt(bcLuminosity / 0.04)
    lh2Line          = math.sqrt(bcLuminosity / 0.0025)
    sysol            = 40 * stellarMass
    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778) ** 4
    ffInner  = math.sqrt(bcLuminosity / 52)
    ffOuter  = math.sqrt(bcLuminosity / 29.9)
    fsInner  = math.sqrt(bcLuminosity / 38.7)
    fsOuter  = math.sqrt(bcLuminosity / 3.2)
    prwInner = math.sqrt(bcLuminosity / 2.8)
    prwOuter = math.sqrt(bcLuminosity / 0.8)
    praInner = math.sqrt(bcLuminosity / 0.48)
    praOuter = math.sqrt(bcLuminosity / 0.21)
    pmInner  = math.sqrt(bcLuminosity / 0.023)
    pmOuter  = math.sqrt(bcLuminosity / 0.0094)
    phInner  = math.sqrt(bcLuminosity / 0.0025)
    phOuter  = math.sqrt(bcLuminosity / 0.000024)

    _display_star_system_properties(vmag, absMagnitude, bcAbsMagnitude, bcLuminosity, luminosityFromMass, boloLum, temp)
    _display_stellar_properties(stellarMass, stellarRadius, stellarDiameterSol, stellarDiameterKM, mainSeqLifeSpan)
    _display_star_distance(plx, trigParallax, parsecs, lightYears)
    _display_earth_equivalent_orbit(distAU, distKM, planetaryYear, planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF, sizeOfSun)
    _display_solar_system_regions(sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol)
    _display_alternate_hz_regions(ffInner, ffOuter, fsInner, fsOuter, prwInner, prwOuter, praInner, praOuter, pmInner, pmOuter, phInner, phOuter)
    _display_calculated_hz(bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, stellarRadius)

    input("\nPress Enter to Return to the Main Menu")


# ─── Main Menu ────────────────────────────────────────────────────────────────

MENU_OPTIONS = {
    "1":  ("SIMBAD Lookup Query",                                     query_star),
    "2":  ("NASA Exoplanet Archive: All Tables",                      query_exoplanets),
    "3":  ("NASA Exoplanet Archive: Planetary Systems Composite",     query_planetary_systems_composite),
    "4":  ("NASA Exoplanet Archive: HWO ExEP Precursor Science Stars", query_hwo_exep),
    "5":  ("NASA Exoplanet Archive: Mission Exocat Stars",            query_mission_exocat_stars),
    "6":  ("Habitable Worlds Catalog",                                query_habitable_worlds_catalog),
    "7":  ("Open Exoplanet Catalogue",                                query_open_exoplanet_catalogue),
    "8":  ("Exoplanet EU Encyclopaedia",                              query_exoplanet_eu),
    "9":  ("Star System Regions (SIMBAD)",                            query_star_system_regions),
    "10": ("Star System Regions (Semi-SIMBAD)",                       query_star_system_regions_semi_manual),
    "11": ("Star System Regions (Manual)",                            query_star_system_regions_manual),
    "12": ("Distance Between 2 Stars",                               query_distance_between_stars),
    "13": ("Stars within a Certain Distance of Sol",                 query_stars_within_distance),
    "14": ("Stars within a Certain Distance of a Star",             query_stars_within_distance_of_star),
    "15": ("Light Years per Hour to X Times the Speed of Light",    ly_per_hour_to_speed_of_light),
    "16": ("X Times the Speed of Light to Light Years per Hour",    speed_of_light_to_ly_per_hour),
    "17": ("Distance Traveled at a certain ly/hr within a certain time", distance_traveled_ly_per_hour),
    "18": ("Distance Traveled at a certain X times the speed of light within a certain time", distance_traveled_times_c),
    "19": ("Time to Travel # of Light Years at X LY/HR",            time_to_travel_ly_at_ly_per_hour),
    "20": ("Time to Travel # of Light Years at X Times the Speed of Light", time_to_travel_ly_at_times_c),
    "21": ("Travel Time Between 2 Stars (LYs/HR)",                    travel_time_between_stars_ly_hr),
    "22": ("Travel Time Between 2 Stars (X Times the Speed of Light)", travel_time_between_stars_times_c),
    "23": ("Distance Traveled at an Acceleration Within a Certain Time", distance_traveled_at_acceleration),
    "24": ("Travel Time Between 2 System Objs (Generic, Distance in AUs)", travel_time_between_system_objects),
    "25": ("Travel Time Between 2 System Objs (Generic, Distance in LMs)", travel_time_between_system_objects_lm),
    "26": ("Travel Time Between 2 System Objs (Planet/Moon/Asteroid)", travel_time_between_solar_system_objects),
    "27": ("Planetary Orbit Periastron & Apastron Distance Calculator", planetary_orbit_periastron_apastron),
    "28": ("Orbital Distance of an Earth-sized Moon with a 24 hour day", moon_orbital_distance_24h),
    "29": ("Orbital Distance of an Earth-sized Moon with a X hour day",  moon_orbital_distance_x_hours),
    "30": ("Centrifugal Artificial Gravity Acceleration at Point X (m/s^2)", centrifugal_gravity_acceleration),
    "31": ("Distance from Point X to the Center of Rotation (m)",           centrifugal_gravity_distance),
    "32": ("Rotation Rate at Point X (rpm)",                                centrifugal_gravity_rpm),
    "33": ("Habitable Zone Calculator",                                      habitable_zone_calculator),
    "34": ("Habitable Zone Calculator w/SMA",                               habitable_zone_calculator_sma),
    "35": ("Star Luminosity",                                                star_luminosity_calculator),
    "36": ("Solar System Planet/Dwarf Planets/Asteroids Data Table",         solar_system_data_tables),
    "37": ("Main Sequence Star Properties",                                  main_sequence_star_properties),
    "38": ("Sol Solar System Regions",                                       sol_solar_system_regions),
    "50": ("Star Systems CSV Query",                                  query_star_systems_csv),
}

_STAR_DB_KEYS = {"1", "2", "3", "4", "5", "6", "7", "8"}
_STAR_REGIONS_KEYS = {"9", "10", "11"}
_ROTATING_HABITAT_KEYS = {"30", "31", "32"}
_CALCULATORS_KEYS = {
    "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26",
    "27", "28", "29",
    "33", "34", "35",
}
_SCIENCE_KEYS = {"36", "37", "38"}
_UTILITY_KEYS = {"50"}


def _print_two_column_section(keys):
    sorted_keys = sorted(keys, key=int)
    labels = [f"{k}. {MENU_OPTIONS[k][0]}" for k in sorted_keys]
    col_width = max(len(l) for l in labels)
    for i in range(0, len(labels), 2):
        left = f"  {labels[i]:<{col_width}}"
        if i + 1 < len(labels):
            print(left + f"    {labels[i+1]}")
        else:
            print(left)


def main_menu():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 50)
        print("   SPACE AND SCIENCE FICTION APP")
        print("=" * 50)
        print("  Star Databases")
        print("-" * 50)
        _print_two_column_section(_STAR_DB_KEYS)
        print("-" * 50)
        print("  Star System Regions")
        print("-" * 50)
        for key in sorted(_STAR_REGIONS_KEYS, key=int):
            label = MENU_OPTIONS[key][0]
            print(f"  {key}. {label}")
        print("-" * 50)
        print("  Rotating Habitat Equations")
        print("-" * 50)
        for key in sorted(_ROTATING_HABITAT_KEYS, key=int):
            label = MENU_OPTIONS[key][0]
            print(f"  {key}. {label}")
        print("-" * 50)
        print("  Calculators")
        print("-" * 50)
        _print_two_column_section(_CALCULATORS_KEYS)
        print("-" * 50)
        print("  Science")
        print("-" * 50)
        for key in sorted(_SCIENCE_KEYS, key=int):
            label = MENU_OPTIONS[key][0]
            print(f"  {key}. {label}")
        print("-" * 50)
        for key in sorted(_UTILITY_KEYS, key=int):
            label = MENU_OPTIONS[key][0]
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
