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
- After the HWO section, `_query_mission_exocat()` is called and `_display_mission_exocat_results()` is shown if a match is found (see Mission Exocat Archive below).

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

## Mission Exocat Archive

- Displayed automatically after the HWO ExEP section (or after the NASA HZ if HWO was skipped), before the "Press Enter to Return to the Main Menu" prompt in `query_exoplanets()`. Not a menu option.
- Data source: `missionExocat.csv` in the project directory, loaded once at first use into a module-level cache (`_MISSION_EXOCAT`).
- Helper: `_load_mission_exocat()` reads the CSV and builds HIP/HD/GJ lookup indices (case-insensitive); `_query_mission_exocat(designations)` searches by HIP → HD → GJ priority; `_display_mission_exocat_results()` renders the output.
- Designation priority: HIP → HD → GJ (CSV fields: `hip_name`, `hd_name`, `gj_name`).
- If no match is found, the section is silently skipped.
- Star Name line uses `star_name` from the CSV plus `hd_name`, `hip_name`, `gj_name` in that order.
- **Star Properties line**: `# of Planets` from `st_ppnum`.
- **Star Properties table** columns: Spectral Type (`st_spttype`), Temp (`st_teff`), Mass (`st_mass`, 1 decimal), Radius (`st_rad`, 2 decimal), Luminosity (`st_lbol` / calculated), EE Rad Distance (`st_eeidau`), Parsecs (`st_dist`, 2 decimal), LYs (parsecs × 3.26156, 4 decimal), Fe/H (`st_metfe`, 2 decimal), Age (`st_age`, raw CSV value).
  - Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴` when both fields are present; displayed as `{st_lbol:.2f} ({calculated:.6f})`; falls back to `{st_lbol:.2f}` alone if radius/teff unavailable.
  - EE Rad Distance formatted as `{au:.2f} ({au × 8.3167:.4f} LM)`.
  - Note: `st_lbol` is direct luminosity in solar units (not log₁₀), unlike `st_lum` in the NASA/HWO archives.
- After the Star Properties table, `_display_habitable_zone()` renders a Calculated HZ. A synthetic row is passed with `st_teff` and `st_rad` from the CSV; if `st_rad` is absent, `st_lum` is set to `log₁₀(st_lbol)` as fallback.

## Calculated Habitable Zone

- Rendered by `_display_habitable_zone(rows)` after the Planet Properties table in `query_exoplanets()`, and again after the HWO EEI table using HWO stellar data.
- Luminosity source: prefers `(st_rad²) × (st_teff/5778)⁴`; falls back to `10 ** st_lum` (archive log₁₀ value) if radius unavailable. Skipped entirely if neither teff nor luminosity is available.
- Uses Kopparapu et al. polynomial coefficients (seffsun, a, b, c, d arrays) with `tstar = teff - 5780`.
- Six zone boundaries computed: Recent Venus, Runaway Greenhouse, Runaway Greenhouse (5 Earth mass), Runaway Greenhouse (0.1 Earth mass), Maximum Greenhouse, Early Mars.
- Output columns: zone name and distance in AU with light-minutes `(AU × 8.3167 LM)`.
- Table format: plain text with `ljust` padding; column widths derived from longest label/value.

## Star System Regions Feature

- Menu option 3: `query_star_system_regions()` — runs the same SIMBAD lookup as `query_star()`, then validates the star's data for suitability before proceeding to region calculations.
- **Spectral type validation:** extracted from SIMBAD `sp_type`. If the type does not contain an OBAFGKM class letter (e.g. white dwarfs like DA, DZ), a message is printed and the function returns early.
- **CSV lookup:** `_load_main_sequence_data()` loads `propertiesOfMainSequenceStars.csv` (lazy, cached in `_MAIN_SEQUENCE_DATA`) into `{letter: [(subtype_float, row_dict), ...]}` sorted ascending by subtype.
  - `_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")` — negative lookbehind prevents matching an OBAFGKM letter that is preceded by another uppercase letter (e.g. the `A` in `DA1.9` is excluded).
  - `_parse_spectral_class(sp_str)` uses `_SP_PATTERN.search()` to extract `(letter, subtype_float)`.
  - `_lookup_spectral_type(sp_str)` applies a **floor rule**: finds the largest available subtype number ≤ the requested subtype (e.g. G1 → G0, G6 → G5). Falls back to the smallest available entry if the requested subtype is below all entries (e.g. O2 → O5).
- **Values extracted and validated** (all required; each triggers message + early return if missing):
  - `boloLum` — `Bolo. Corr. (BC)` from the matched CSV row (float)
  - `temp` — temperature in K from SIMBAD `mesfe_h.teff`
  - `vmag` — apparent magnitude from SIMBAD `V`
  - `plx` — parallax in mas from SIMBAD `plx_value`; also rejected if `<= 0`
- **Constants defined for later sections:** `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`
- **Star System Properties table** — rendered by `_display_star_system_properties()` after all validations pass:
  - `parsecs = 1000.0 / plx`
  - `absMagnitude = vmag + 5 - (5 × log10(parsecs))`
  - `bcAbsMagnitude = absMagnitude + boloLum`
  - `bcLuminosity = 2.52 ** (4.85 - bcAbsMagnitude)`
  - `stellarMass = bcLuminosity ** 0.2632` (intermediate, not displayed)
  - `luminosityFromMass = stellarMass ** 3.5`
  - Table rows (label | value): Apparent Magnitude (3dp), Absolute Magnitude (3dp), Bolometric Absolute Magnitude (3dp), Bolometric Luminosity (6dp), Luminosity from Mass (5dp), BC (1dp), Star Temperature K (integer)
  - Column widths computed dynamically; labels left-justified, values right-justified, separated by ` | `
- **Stellar Properties table** — rendered by `_display_stellar_properties()` after the Star System Properties table; uses `_print_table()` (single header row, all columns right-aligned):
  - `stellarRadius = stellarMass ** 0.57` if `stellarMass >= 1`, else `stellarMass ** 0.8`
  - `stellarDiameterSol = ((5780²) / (temp²)) × √bcLuminosity`
  - `stellarDiameterKM = stellarDiameterSol × 1391600`
  - `mainSeqLifeSpan = 10¹⁰ × (1 / stellarMass) ** 2.5`
  - Columns: Stellar Mass (4dp), Stellar Radius (5dp), Stellar Diameter Sol (4dp), Stellar Diameter KM (5e), Main Sequence Life Span (5e)

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sp_type`, `plx_value`, `V`, `mesfe_h` (temperature in `mesfe_h.teff` column). Updated for astroquery ≥ 0.4.8 — prior names (`sptype`, `plx`, `flux(V)`, `fe_h`) are deprecated.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Result column names are lowercase: `main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `mesfe_h.teff`.
- Designations are pulled from `Simbad.query_objectids()`; the result column is `id` (lowercase).
- Parallax (mas) from `plx_value`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
