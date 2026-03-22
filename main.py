#!/usr/bin/env python3
"""Space and Science Fiction App"""

import os
import sys
from astroquery.simbad import Simbad


# ─── SIMBAD Star Query ────────────────────────────────────────────────────────

def query_star():
    """Query SIMBAD astronomical database for star information."""
    designation = input(
        "\nEnter star designation (e.g., 'Vega', 'HD 209458', 'HIP 27989'): "
    ).strip()

    if not designation:
        print("No designation entered.")
        input("\nPress Enter to Return to the Main Menu")
        return

    print(f"\nQuerying SIMBAD for '{designation}'...\n")

    custom_simbad = Simbad()
    custom_simbad.add_votable_fields("sptype", "plx", "flux(V)", "fe_h")

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

    if result is not None and "MAIN_ID" in result.colnames:
        designations["MAIN_ID"] = str(result["MAIN_ID"][0])

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
        id_str = str(row["ID"]).strip()
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
    # Astropy masked values
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

    print("=" * 110)
    print("STAR DESIGNATIONS:")
    print(", ".join(desig_list) if desig_list else "N/A")
    print("=" * 110)
    print()

    # ── Field extraction ──────────────────────────────────────────────────────
    ra  = str(_safe_get(row, col_names, "RA")  or "N/A")
    dec = str(_safe_get(row, col_names, "DEC") or "N/A")

    sp_raw = _safe_get(row, col_names, "SP_TYPE")
    sp_type = str(sp_raw) if sp_raw is not None else "N/A"

    plx_raw = _safe_get(row, col_names, "PLX_VALUE")
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

    temp_raw = _safe_get(row, col_names, "Fe_H_Teff")
    temp = f"{int(float(temp_raw))} K" if temp_raw is not None else "N/A"

    vmag_raw = _safe_get(row, col_names, "FLUX_V")
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


# ─── Main Menu ────────────────────────────────────────────────────────────────

MENU_OPTIONS = {
    "1": ("Query Star Information (SIMBAD)", query_star),
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
    main_menu()
