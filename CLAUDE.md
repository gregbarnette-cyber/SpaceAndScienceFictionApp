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

## Menu Options

```
1. Query Star Information (SIMBAD)
2. NASA Exoplanet Archive: All Tables
3. NASA Exoplanet Archive: Planetary Systems Composite
4. NASA Exoplanet Archive: HWO ExEP Precursor Science Stars
5. NASA Exoplanet Archive: Mission Exocat Stars
6. Star System Regions
```

## NASA Exoplanet Archive: All Tables Feature

- Menu option 2: `query_exoplanets()` — runs the same SIMBAD lookup first to resolve designations, then queries all three NASA Exoplanet Archive sources in sequence.
- Archive query uses TAP endpoint `https://exoplanetarchive.ipac.caltech.edu/TAP/sync` against the `pscomppars` table.
- Designation priority for archive query: HIP → HD → TIC → Gaia EDR3 (fields: `hip_name`, `hd_name`, `tic_id`, `gaia_id`).
- Results sorted ascending by `pl_orbsmax` (semi-major axis in AU).
- Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴`; displayed as `{st_lum} ({calculated})` when both `st_rad` and `st_teff` are available, otherwise falls back to `st_lum`.
- Distance (planet): periastron `pl_orbsmax - (pl_orbsmax × pl_orbeccen)`, semi-major axis, apastron.
- Helper functions: `_fval()` converts to float/None, `_fmt()` formats to fixed decimals, `_print_table()` renders two-line-header tables with dynamic column widths.
- After planet table, `_display_habitable_zone()` is called to render the habitable zone table.
- After the habitable zone table, `_display_hwo_exep_results()` is called if the HWO ExEP query returned data (see below).
- After the HWO section, `_query_mission_exocat()` is called and `_display_mission_exocat_results()` is shown if a match is found (see Mission Exocat Archive below).

## NASA Exoplanet Archive: Planetary Systems Composite Feature

- Menu option 3: `query_planetary_systems_composite()` — runs the same SIMBAD lookup as `query_exoplanets()`, then queries NASA Exoplanet Archive (`pscomppars`) and displays results. Does **not** query HWO ExEP or Mission Exocat archives.
- Reuses `_get_archive_query_params()`, `_query_exoplanet_archive()`, and `_display_exoplanet_results()` from the All Tables feature.
- `_display_exoplanet_results()` renders: SIMBAD star designations + info table, Star Name line, Star Properties table, Planet Properties table, and Calculated Habitable Zone (`_display_habitable_zone()`).
- Designation priority for archive query: HIP → HD → TIC → Gaia EDR3 (same as option 2).
- After the Calculated Habitable Zone, returns directly to the main menu prompt.

## NASA Exoplanet Archive: HWO ExEP Precursor Science Stars Feature

- Menu option 4: `query_hwo_exep()` — runs the same SIMBAD lookup, then queries the HWO ExEP archive only. Does **not** query pscomppars or Mission Exocat.
- Designation priority: HIP → HD → TIC → HR → GJ (fields: `hip_name`, `hd_name`, `tic_id`, `hr_name`, `gj_name`).
- Helper: `_get_hwo_query_params()` selects the designation; `_query_hwo_exep_archive()` runs the TAP query against `di_stars_exep`; `_display_hwo_exep_results()` renders the output.
- Renders: SIMBAD star designations + info table, then `_display_hwo_exep_results()` which includes:
  - Star Name line (HD, HIP, HR, GJ designations)
  - **Star Properties table** columns: Spectral Type (`st_spectype`), Luminosity (`st_lum` / calculated), Temp (`st_teff`), Mass (`st_mass`), Radius (`st_rad`), Parallax (`sy_plx`), Parsecs (`sy_dist`), LYs (parsecs × 3.26156), Fe/H (`st_met`).
    - Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴` when both fields are numbers; displayed as `{st_lum:.4f} ({calculated:.6f})`; falls back to `st_lum` alone if radius/teff unavailable.
  - **System\EEI Properties table** columns: Planets (`sy_planets_flag` → Y/N/None), # of Planets (`sy_pnum`), Disk (`sy_disksflag` → Y/N/None), Earth Equivalent Insolation Distance (`st_eei_orbsep` in AU and LM), Earth Equivalent Planet-Star Ratio (`st_etwin_bratio` in scientific notation), Orbital Period at EEID (`st_eei_orbper` in days).
    - Flag fields: `1` → `Y`, `0` → `N`, null → `None`.
    - EEID distance formatted as `{au:.3f} AU ({au × 8.3167:.4f} LM)`.
  - **Calculated Habitable Zone** via `_display_habitable_zone(hwo_rows)`.
- Results sorted ascending by `sy_dist` (distance in parsecs).
- If no HWO data is found, prints a message and returns to menu.

## NASA Exoplanet Archive: Mission Exocat Stars Feature

- Menu option 5: `query_mission_exocat_stars()` — runs the same SIMBAD lookup, then queries Mission Exocat only. Does **not** query pscomppars or HWO ExEP.
- Data source: `missionExocat.csv` in the project directory, loaded once at first use into a module-level cache (`_MISSION_EXOCAT`).
- Helper: `_load_mission_exocat()` reads the CSV and builds HIP/HD/GJ lookup indices (case-insensitive); `_query_mission_exocat(designations)` searches by HIP → HD → GJ priority; `_display_mission_exocat_results()` renders the output.
- Renders: SIMBAD star designations + info table, then `_display_mission_exocat_results()` which includes:
  - Star Name line (`star_name` from CSV plus `hd_name`, `hip_name`, `gj_name`)
  - **Star Properties line**: `# of Planets` from `st_ppnum`.
  - **Star Properties table** columns: Spectral Type (`st_spttype`), Temp (`st_teff`), Mass (`st_mass`, 1 decimal), Radius (`st_rad`, 2 decimal), Luminosity (`st_lbol` / calculated), EE Rad Distance (`st_eeidau`), Parsecs (`st_dist`, 2 decimal), LYs (parsecs × 3.26156, 4 decimal), Fe/H (`st_metfe`, 2 decimal), Age (`st_age`, raw CSV value).
    - Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴` when both fields are present; displayed as `{st_lbol:.2f} ({calculated:.6f})`; falls back to `{st_lbol:.2f}` alone if radius/teff unavailable.
    - EE Rad Distance formatted as `{au:.2f} ({au × 8.3167:.4f} LM)`.
    - Note: `st_lbol` is direct luminosity in solar units (not log₁₀), unlike `st_lum` in the NASA/HWO archives.
  - **Calculated Habitable Zone** via `_display_habitable_zone()`. A synthetic row is passed with `st_teff` and `st_rad` from the CSV; if `st_rad` is absent, `st_lum` is set to `log₁₀(st_lbol)` as fallback.
- If no match is found, prints a message and returns to menu.

## HWO ExEP Archive (shared helpers)

- Used by options 2 and 4. TAP endpoint `https://exoplanetarchive.ipac.caltech.edu/TAP/sync` against `di_stars_exep`.
- `_get_hwo_query_params()` selects designation (HIP → HD → TIC → HR → GJ).
- `_query_hwo_exep_archive()` runs the query sorted ascending by `sy_dist`.
- `_display_hwo_exep_results()` renders Star Name, Star Properties, System\EEI Properties, and Calculated HZ.
- In option 2, if no HWO data is found for the star, the section is silently skipped.

## Mission Exocat Archive (shared helpers)

- Used by options 2 and 5. Data source: `missionExocat.csv`.
- `_load_mission_exocat()` builds HIP/HD/GJ lookup indices (case-insensitive).
- `_query_mission_exocat(designations)` searches by HIP → HD → GJ priority; returns a row dict or None.
- `_display_mission_exocat_results()` renders Star Name, Star Properties, and Calculated HZ.
- In option 2, displayed after HWO ExEP section (or after NASA HZ if HWO was skipped). If no match, silently skipped.

## Calculated Habitable Zone

- Rendered by `_display_habitable_zone(rows)` after planet/star property tables in multiple features.
- Luminosity source: prefers `(st_rad²) × (st_teff/5778)⁴`; falls back to `10 ** st_lum` (archive log₁₀ value) if radius unavailable. Skipped entirely if neither teff nor luminosity is available.
- Uses Kopparapu et al. polynomial coefficients (seffsun, a, b, c, d arrays) with `tstar = teff - 5780`.
- Six zone boundaries computed: Recent Venus, Runaway Greenhouse, Runaway Greenhouse (5 Earth mass), Runaway Greenhouse (0.1 Earth mass), Maximum Greenhouse, Early Mars.
- Output columns: zone name and distance in AU with light-minutes `(AU × 8.3167 LM)`.
- Table format: plain text with `ljust` padding; column widths derived from longest label/value.

## Star System Regions Feature

- Menu option 6: `query_star_system_regions()` — runs the same SIMBAD lookup as `query_star()`, then validates the star's data for suitability before proceeding to region calculations.
- **Spectral type validation:** extracted from SIMBAD `sp_type`. If the type does not contain an OBAFGKM class letter (e.g. white dwarfs like DA, DZ), a message is printed and the function returns early.
- **CSV lookup:** `_load_main_sequence_data()` loads `propertiesOfMainSequenceStars.csv` (lazy, cached in `_MAIN_SEQUENCE_DATA`) into `{letter: [(subtype_float, row_dict), ...]}` sorted ascending by subtype.
  - `_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")` — negative lookbehind prevents matching an OBAFGKM letter that is preceded by another uppercase letter (e.g. the `A` in `DA1.9` is excluded).
  - `_parse_spectral_class(sp_str)` uses `_SP_PATTERN.search()` to extract `(letter, subtype_float)`.
  - `_lookup_spectral_type(sp_str)` applies a **ceiling rule**: finds the smallest available subtype number ≥ the requested subtype (e.g. G1 → G2, G6 → G8, A4 → A5). If all entries in the class are cooler than requested (subtype exceeds all), advances to the next cooler letter class's hottest entry (e.g. F9 → G0). `_LETTER_SEQUENCE = ["O","B","A","F","G","K","M"]` defines the cross-letter fallthrough order.
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
- **Star Distance table** — rendered by `_display_star_distance()`; uses `_print_table()` (single header row, all columns right-aligned):
  - `trigParallax = plx / 1000`
  - `lightYears = 3.2616 / trigParallax`
  - `parsecs` already computed as `1000.0 / plx`
  - Columns: Parallax (2dp), Trig Parallax (4dp), Parsecs (4dp), Light Years (4dp)
- **Earth Equivalent Orbit Properties table** — rendered by `_display_earth_equivalent_orbit()`; uses `_print_table()` (two-line header row, all columns right-aligned):
  - `distAU = sqrt(bcLuminosity / sunlightIntensity)`
  - `distKM = distAU × 149000000`
  - `planetaryYear = sqrt(distAU³ / stellarMass)`
  - `planetaryTemperature = 374 × 1.1 × (1 - bondAlbedo) × sunlightIntensity ** 0.25`
  - `planetaryTemperatureC = planetaryTemperature - 273.15`
  - `planetaryTemperatureF = (planetaryTemperatureC × 9/5) + 32`
  - `starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)`; `sizeOfSun = f"{starAngularDiameter:.2f}°"`
  - Columns: Distance AU (4dp), Distance KM (5e), Year (4dp), Temp K (2dp), Temp C (2dp), Temp F (2dp), Size of Sun (degree string)
- **Solar System Regions table** — rendered by `_display_solar_system_regions()`; uses `_print_table()` (Region | AU, left-aligned); AU formatted as `{val:.4f} ({val × 8.3167:.3f} LM)`:
  - `sysilGrav = 0.2 × stellarMass`, `sysilSunlight = sqrt(bcLuminosity/16)`
  - `hzil = sqrt(bcLuminosity/1.1)`, `hzol = sqrt(bcLuminosity/0.53)`
  - `snowLine = sqrt(bcLuminosity/0.04)`, `lh2Line = sqrt(bcLuminosity/0.0025)`, `sysol = 40 × stellarMass`
- **Solar System Alternate Habitable Zone Regions table** — rendered by `_display_alternate_hz_regions()`; same 2-column format as Solar System Regions; all 12 values computed as `sqrt(bcLuminosity / divisor)`:
  - Fluorosilicone-Fluorosilicone Inner/Outer (÷52, ÷29.9), Fluorocarbon-Sulfur Inner/Outer (÷38.7, ÷3.2)
  - Protein-Water Inner/Outer (÷2.8, ÷0.8), Protein-Ammonia Inner/Outer (÷0.48, ÷0.21)
  - Polylipid-Methane Inner/Outer (÷0.023, ÷0.0094), Polylipid-Hydrogen Inner/Outer (÷0.0025, ÷0.000024)
- **Calculated Habitable Zone table** — rendered by `_display_calculated_hz()`; uses `_print_table()` (4 columns: Zone + 3 luminosity AU columns, all left-aligned); AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`:
  - `calculatedLuminosity = stellarRadius² × (temp/5778)⁴`
  - Uses same Kopparapu et al. coefficients and `tstar = temp - 5780` as `_display_habitable_zone()` (line 474)
  - Three columns: Bolometric Luminosity (`bcLuminosity`), Luminosity from Mass (`luminosityFromMass`), Calculated Luminosity
  - Six zones in order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (RG 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (RG 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars)

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sp_type`, `plx_value`, `V`, `mesfe_h` (temperature in `mesfe_h.teff` column). Updated for astroquery ≥ 0.4.8 — prior names (`sptype`, `plx`, `flux(V)`, `fe_h`) are deprecated.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Result column names are lowercase: `main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `mesfe_h.teff`.
- Designations are pulled from `Simbad.query_objectids()`; the result column is `id` (lowercase).
- Parallax (mas) from `plx_value`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
