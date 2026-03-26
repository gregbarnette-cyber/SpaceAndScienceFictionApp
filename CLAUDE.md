# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Architecture

`main.py` is the single entry point. All features live as functions in this file (for now) and are registered in the `MENU_OPTIONS` dict at the bottom, which drives the main menu loop.

```
MENU_OPTIONS = {
    "1": ("Query Star Information (SIMBAD)", query_star),
    # add new features here
}
```

The main menu loop calls whichever function the user picks, then returns to the menu after the function ends. Every feature function must call `input("\nPress Enter to Return to the Main Menu")` before returning.

## Adding New Features

1. Write the feature as a top-level function.
2. Register it in `MENU_OPTIONS` with the next available key and a short label.
3. End the function with the "Press Enter to Return to the Main Menu" prompt.

## NASA Exoplanet Archive Query Feature

- Menu option 2: `query_exoplanets()` — runs the same SIMBAD lookup first to resolve designations, then queries NASA Exoplanet Archive.
- Archive query uses TAP endpoint `https://exoplanetarchive.ipac.caltech.edu/TAP/sync` against the `pscomppars` table.
- Designation priority for archive query: HIP → HD → TIC → Gaia EDR3 (fields: `hip_name`, `hd_name`, `tic_id`, `gaia_id`).
- Results sorted ascending by `pl_orbsmax` (semi-major axis in AU).
- Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴`; displayed as `{st_lum} ({calculated})` when both `st_rad` and `st_teff` are available, otherwise falls back to `st_lum`.
- Distance (planet): periastron `pl_orbsmax - (pl_orbsmax × pl_orbeccen)`, semi-major axis, apastron.
- Helper functions: `_fval()` converts to float/None, `_fmt()` formats to fixed decimals, `_print_table()` renders two-line-header tables with dynamic column widths.
- After planet table, `_display_habitable_zone()` is called to render the habitable zone table.
- After the habitable zone table, `_display_hwo_exep_results()` is called if the HWO ExEP query returned data (see below).

## HWO ExEP Precursor Science Stars Archive

- Queried automatically at the end of `query_exoplanets()`, after the NASA HZ table, only when NASA exoplanet data was found.
- Uses the same TAP endpoint against the `di_stars_exep` table.
- Designation priority: HIP → HD → TIC → HR → GJ (fields: `hip_name`, `hd_name`, `tic_id`, `hr_name`, `gj_name`).
- Results sorted ascending by `sy_dist` (distance in parsecs).
- If no HWO data is found for the star, the section is silently skipped.
- Helper: `_get_hwo_query_params()` selects the designation; `_query_hwo_exep_archive()` runs the TAP query; `_display_hwo_exep_results()` renders the output.
- **Star Properties table** columns: Spectral Type (`st_spectype`), Luminosity (`st_lum` / calculated), Temp (`st_teff`), Mass (`st_mass`), Radius (`st_rad`), Parallax (`sy_plx`), Parsecs (`sy_dist`), LYs (parsecs × 3.26156), Fe/H (`st_met`).
  - Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴` when both fields are numbers; displayed as `{st_lum:.4f} ({calculated:.6f})`; falls back to `st_lum` alone if radius/teff unavailable.
- **System\EEI Properties table** columns: Planets (`sy_planets_flag` → Y/N/None), # of Planets (`sy_pnum`), Disk (`sy_disksflag` → Y/N/None), Earth Equivalent Insolation Distance (`st_eei_orbsep` in AU and LM), Earth Equivalent Planet-Star Ratio (`st_etwin_bratio` in scientific notation), Orbital Period at EEID (`st_eei_orbper` in days).
  - Flag fields: `1` → `Y`, `0` → `N`, null → `None`.
  - EEID distance formatted as `{au:.3f} AU ({au × 8.3167:.4f} LM)`.
- Star Name line uses HD, HIP, HR, GJ designations (vs. HD, HIP, TIC, Gaia EDR3 in the NASA section).
- After the EEI table, `_display_habitable_zone(hwo_rows)` renders a Calculated HZ using the HWO archive's stellar data.

## Calculated Habitable Zone

- Rendered by `_display_habitable_zone(rows)` after the Planet Properties table in `query_exoplanets()`, and again after the HWO EEI table using HWO stellar data.
- Luminosity source: prefers `(st_rad²) × (st_teff/5778)⁴`; falls back to `10 ** st_lum` (archive log₁₀ value) if radius unavailable. Skipped entirely if neither teff nor luminosity is available.
- Uses Kopparapu et al. polynomial coefficients (seffsun, a, b, c, d arrays) with `tstar = teff - 5780`.
- Six zone boundaries computed: Recent Venus, Runaway Greenhouse, Runaway Greenhouse (5 Earth mass), Runaway Greenhouse (0.1 Earth mass), Maximum Greenhouse, Early Mars.
- Output columns: zone name and distance in AU with light-minutes `(AU × 8.3167 LM)`.
- Table format: plain text with `ljust` padding; column widths derived from longest label/value.

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sptype`, `plx`, `flux(V)`, `fe_h` (temperature in `Fe_H_Teff` column). Field names are specific to astroquery 0.4.x.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Parallax (mas) from `PLX_VALUE`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Designations are pulled from `Simbad.query_objectids()` and matched by prefix in `_parse_designations()`.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
