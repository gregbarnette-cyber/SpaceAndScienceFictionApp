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
                "Temp (Meas)", "Density", "Potential", "Gravity"]
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


def _find_star_in_system(system_elem, matched_name_lower):
    """Return the <star> element containing matched_name; fallback to first star with planets."""
    for star in system_elem.iter("star"):
        for n in star.findall("name"):
            if n.text and n.text.strip().lower() == matched_name_lower:
                return star
    # Name was at system/binary level — return first star that has at least one planet
    for star in system_elem.iter("star"):
        if star.find("planet") is not None:
            return star
    # Last resort: any star
    return next(system_elem.iter("star"), None)


def _query_oec(designations):
    """Search OEC for designations; return (system_elem, star_elem) or (None, None)."""
    _, index = _load_oec()
    candidates = _get_oec_candidates(designations)

    for name in candidates:
        key = name.lower()
        if key in index:
            system_elem = index[key]
            star_elem = _find_star_in_system(system_elem, key)
            return system_elem, star_elem

    return None, None


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


def _display_oec_results(designations, system_elem, star_elem):
    """Render all OEC result tables."""

    # ── Title ─────────────────────────────────────────────────────────────────
    title  = "# Open Exoplanet Catalogue #"
    border = "#" * len(title)
    print(border)
    print(title)
    print(border)
    print()

    # ── Star Name line ────────────────────────────────────────────────────────
    if star_elem is not None:
        names = [n.text.strip() for n in star_elem.findall("name") if n.text and n.text.strip()]
    else:
        names = [n.text.strip() for n in system_elem.findall("name") if n.text and n.text.strip()]

    primary   = names[0] if names else "Unknown"
    alternates = names[1:4]
    star_line  = (f"Star Name: {primary}  ({', '.join(alternates)})"
                  if alternates else f"Star Name: {primary}")
    sep = "-" * len(star_line)
    print(sep)
    print(star_line)
    print(sep)
    print()

    if star_elem is None:
        print("Note: No individual host star element found for this object in OEC.")
        return

    # ── Star Properties ───────────────────────────────────────────────────────
    _display_oec_star_properties(system_elem, star_elem)

    # ── Planet Properties ─────────────────────────────────────────────────────
    planets = list(star_elem.iter("planet"))
    if planets:
        _display_oec_planet_properties(star_elem)
    else:
        print("No planets found for this star in the Open Exoplanet Catalogue.")
        print()

    # ── Calculated Habitable Zone ─────────────────────────────────────────────
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
        system_elem, star_elem = _query_oec(designations)
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
    _display_oec_results(designations, system_elem, star_elem)

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

        # Temperature
        try:
            teff_raw = row["mesfe_h.teff"]
            temp = str(int(float(teff_raw))) if teff_raw is not None and str(teff_raw).strip() not in ("", "--") else ""
        except (TypeError, ValueError):
            temp = ""

        # If already seen this star within this batch, just try to fill in a missing teff
        if main_id in seen_main_ids:
            if temp and not new_rows[seen_main_ids[main_id]]["Temperature"]:
                new_rows[seen_main_ids[main_id]]["Temperature"] = temp
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
            "Temperature":        temp,
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
    simbad.add_votable_fields("sp_type", "plx_value", "V", "mesfe_h", "ids")

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starSystems.csv")
    fieldnames = [
        "Star Name", "Star Designations", "Spectral Type", "Parallax",
        "Parsecs", "Light Years", "Temperature", "Apparent Magnitude", "RA", "DEC",
    ]

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


# ─── Main Menu ────────────────────────────────────────────────────────────────

MENU_OPTIONS = {
    "1": ("SIMBAD Lookup Query",                                     query_star),
    "2": ("NASA Exoplanet Archive: All Tables",                     query_exoplanets),
    "3": ("NASA Exoplanet Archive: Planetary Systems Composite",    query_planetary_systems_composite),
    "4": ("NASA Exoplanet Archive: HWO ExEP Precursor Science Stars", query_hwo_exep),
    "5": ("NASA Exoplanet Archive: Mission Exocat Stars",           query_mission_exocat_stars),
    "6": ("Star System Regions",                                    query_star_system_regions),
    "7": ("Star System Regions (Semi-Manual)",                      query_star_system_regions_semi_manual),
    "8": ("Star System Regions (Manual)",                           query_star_system_regions_manual),
    "9": ("Habitable Worlds Catalog",                               query_habitable_worlds_catalog),
    "10": ("Open Exoplanet Catalogue",                              query_open_exoplanet_catalogue),
    "11": ("Exoplanet EU Encyclopaedia",                            query_exoplanet_eu),
    "12": ("Star Systems CSV Query",                               query_star_systems_csv),
}


def main_menu():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 50)
        print("   SPACE AND SCIENCE FICTION APP")
        print("=" * 50)
        print("  Star Databases")
        print("-" * 50)
        for key, (label, _) in MENU_OPTIONS.items():
            print(f"  {key}. {label}")
        print("-" * 50)
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
