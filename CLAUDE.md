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
    "1": ("SIMBAD Lookup Query", query_star),
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
1. SIMBAD Lookup Query
2. NASA Exoplanet Archive: All Tables
3. NASA Exoplanet Archive: Planetary Systems Composite
4. NASA Exoplanet Archive: HWO ExEP Precursor Science Stars
5. NASA Exoplanet Archive: Mission Exocat Stars
6. Star System Regions
7. Star System Regions (Semi-Manual)
8. Star System Regions (Manual)
9. Habitable Worlds Catalog
10. Open Exoplanet Catalogue
11. Exoplanet EU Encyclopaedia
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

All three Star System Regions variants (options 6, 7, 8) produce identical output tables. They differ only in how their input values are obtained.

### Option 6: Star System Regions — `query_star_system_regions()`

- Menu option 6: fully automated — SIMBAD lookup + BC CSV lookup; `sunlightIntensity = 1.0`, `bondAlbedo = 0.3` hardcoded.
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
- **Constants:** `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`

### Option 7: Star System Regions (Semi-Manual) — `query_star_system_regions_semi_manual()`

- Menu option 7: same SIMBAD lookup, checks, and BC CSV lookup as option 6, but prompts the user for `sunlightIntensity` and `bondAlbedo` after all validations pass.
- Prompts (loop until valid float entered):
  - `Enter Sunlight Intensity (Terra = 1.0):` — blank defaults to `1.0`
  - `Enter Bond Albedo (Terra = 0.3, Venus = 0.9):` — blank defaults to `0.3`

### Option 8: Star System Regions (Manual) — `query_star_system_regions_manual()`

- Menu option 8: no SIMBAD lookup, no checks, no CSV lookup. All six input values are entered manually.
- Prompts (loop until valid float entered, no defaults):
  - `Apparent Magnitude (V)`
  - `Parallax (mas)` — rejected if `<= 0`
  - `Bolometric Correction (BC)`
  - `Star Effective Temperature (K)`
  - `Sunlight Intensity (Terra = 1.0)`
  - `Bond Albedo (Terra = 0.3, Venus = 0.9)`
- Uses a shared `prompt_float(label)` helper defined inside the function.

### Shared calculations and output tables (all three options)

- **Constants defined for later sections:** `sunlightIntensity` and `bondAlbedo` (source varies by option)
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

## Habitable Worlds Catalog Feature

- Menu option 9: `query_habitable_worlds_catalog()` — runs the same SIMBAD lookup, then queries `hwc.csv` only.
- Data source: `hwc.csv` in the project directory, loaded once at first use into a module-level cache (`_HWC_DATA`).
- Helper: `_load_hwc()` reads the CSV and builds HIP/HD/S_NAME lookup indices (each maps uppercased key → list of planet row dicts); `_query_hwc(designations)` searches by HIP → HD → NAME priority; strips `"NAME "` prefix from the NAME designation before lookup.
- Planet rows sorted ascending by `P_SEMI_MAJOR_AXIS` before display.
- Renders four tables via `_print_table()`:
  - **Star Properties table** — one row from star-level fields: Star (`S_NAME`), HD (`S_NAME_HD`), HIP (`S_NAME_HIP`), Spectral Type (`S_TYPE`), MagV (`S_MAG`, 5dp), L (`S_LUMINOSITY`, 5dp), Temp (`S_TEMPERATURE`, integer), Mass (`S_MASS`, 2dp), Radius (`S_RADIUS`, 2dp), RA (`S_RA`, 4dp), DEC (`S_DEC`, 4dp), Parsecs (`S_DISTANCE`, 5dp), LY (`S_DISTANCE × 3.26156`, 4dp), Fe/H (`S_METALLICITY`, 3dp), Age (`S_AGE`, 2dp).
  - **Star Habitability Properties table** — one row: Inner Opt HZ (`S_HZ_OPT_MIN`), Inner Con HZ (`S_HZ_CON_MIN`), Outer Con HZ (`S_HZ_CON_MAX`), Outer Opt HZ (`S_HZ_OPT_MAX`), Inner Con 5 Me HZ (`S_HZ_CON1_MIN`), Outer Con 5 Me HZ (`S_HZ_CON1_MAX`), Tidal Lock (`S_TIDAL_LOCK`), Abiogenesis (`S_ABIO_ZONE`), Snow Line (`S_SNOW_LINE`); all 6dp.
  - **Planet Properties table** — one row per planet: Planet (`P_NAME`), Mass E (`P_MASS`, 2dp), Radius E (`P_RADIUS`, 2dp), Orbit (`P_PERIOD`, 2dp), Semi-Major Axis (`P_SEMI_MAJOR_AXIS`, 4dp), Eccentricity (`P_ECCENTRICITY`, 2dp), Temp Meas (`P_DENSITY`, 4dp), Density (`P_POTENTIAL`, 5dp), Potential (`P_GRAVITY`, 5dp), Gravity (`P_ESCAPE`, 5dp).
  - **Planet Habitability Properties table** — one row per planet: Planet Type (`P_TYPE`), EFF Dist (`P_DISTANCE_EFF`, 5dp), Periastron (`P_PERIASTRON`, 5dp), Apastron (`P_APASTRON`, 5dp), Temp Type (`P_TYPE_TEMP`), Hill Sphere (`P_HILL_SPHERE`, 8dp), Habitable? (`P_HABITABLE`: `1`→`Yes`, `0`→`No`), ESI (`P_ESI`, 6dp), In HZ Con (`P_HABZONE_CON`: `1`→`Yes`, `0`→`No`), In HZ Opt (`P_HABZONE_OPT`: `1`→`Yes`, `0`→`No`).
  - **Planet Temperature Properties table** — one row per planet: Flux Min (`P_FLUX_MIN`, 5dp), Flux (`P_FLUX`, 5dp), Flux Max (`P_FLUX_MAX`, 5dp), EQ Min (`P_TEMP_EQUIL_MIN`, 3dp), EQ (`P_TEMP_EQUIL`, 3dp), EQ Max (`P_TEMP_EQUIL_MAX`, 3dp), Surf Min (`P_TEMP_SURF_MIN`, 3dp), Surf (`P_TEMP_SURF`, 3dp), Surf Max (`P_TEMP_SURF_MAX`, 3dp).
- If no match is found, prints a message and returns to menu.

## Open Exoplanet Catalogue Feature

- Menu option 10: `query_open_exoplanet_catalogue()` — runs the same SIMBAD lookup, then queries the Open Exoplanet Catalogue (OEC) only.
- Data source: downloaded once per session via `astroquery.open_exoplanet_catalogue.get_catalogue()` which fetches a gzip'd XML file from GitHub. Cached in module-level `_OEC_DATA = (root_element, name_index)`.
- `_load_oec()` calls `get_catalogue()`, calls `.getroot()` on the returned `ElementTree`, then builds a case-insensitive `{name_lower: system_element}` index by iterating all `<name>` elements across the entire tree.
- `_get_oec_candidates(designations)` builds an ordered candidate list from the designations dict (HIP → HD → GJ → HR → WASP → HAT_P → Kepler → TOI → K2 → CoRoT → COCONUTS → KOI → TIC → 2MASS → NAME → MAIN_ID) with normalizations:
  - `K2 N` → `K2-N`, `Kepler N` → `Kepler-N` (SIMBAD uses spaces, OEC uses dashes)
  - `WASP-94A` → `WASP-94 A` (SIMBAD omits space before component letter, OEC includes it)
  - `2MASS J...` → `2MASS ...` (SIMBAD includes leading `J`, OEC omits it)
  - NAME: strips `"NAME "` prefix; MAIN_ID: strips `"* "`, `"V* "`, `"NAME "` prefixes
  - Gaia EDR3 excluded (OEC uses Gaia DR2 IDs — incompatible)
- `_query_oec(designations)` returns `(system_elem, star_elem)` or `(None, None)`.
- `_find_star_in_system(system_elem, matched_name_lower)` locates the specific `<star>` within the matched system using `iter('star')` (descends into `<binary>` nesting automatically); falls back to first star with planets if name was system-level.
- Renders: SIMBAD star designations + info table, then `_display_oec_results()` which includes:
  - Star Name line (primary OEC name + up to 3 alternates from star `<name>` elements)
  - **Star Properties table** columns: Spectral Type (`spectraltype`), MagV (3dp), Temp (int K), Mass (3dp Msun), Radius (3dp Rsun), Fe/H (3dp), Age (2dp Gyr), Parsecs (4dp, from `system/distance`), LYs (parsecs × 3.26156, 4dp).
  - **Planet Properties table** — one row per planet sorted ascending by `semimajoraxis` (N/A last): `#`, Planet Name, Mass(J) (4dp), Mass(E) (2dp, ×317.8), Rad(J) (4dp), Rad(E) (2dp, ×11.2), Period (3dp days), Distance as `peri - SMA - apo AU` (if eccentricity missing: `N/A - SMA - N/A AU`), Eccentricity (3dp), Temp (int K), Method, Year, Status.
    - Status abbreviation map: "Confirmed planets"→"Confirmed", "Controversial"→"Controversial", "Retracted planet candidate"→"Retracted", "Solar System"→"Solar Sys", "Kepler Objects of Interest"→"KOI", "Planets in binary systems, S-type"→"Binary S".
  - **Calculated Habitable Zone** via `_display_habitable_zone()` using a synthetic row with `st_teff` and `st_rad` from OEC star fields.
- If `star_elem` is None (system-level planets, no host star), prints a note and skips star/planet tables.
- If no match found, prints a message and returns to menu.

## Exoplanet EU Encyclopaedia Feature

- Menu option 11: `query_exoplanet_eu()` — runs the same SIMBAD lookup, then queries the Exoplanet Encyclopaedia (exoplanet.eu) only.
- Data source: downloaded once per session via `requests.get("https://exoplanet.eu/catalog/csv/")` — a 79-column CSV with ~8,174 planet rows. Cached in module-level `_EU_DATA = (rows_list, star_name_index)`.
- `_load_eu()` fetches the CSV, parses with `csv.DictReader`, and builds a case-insensitive `{star_name_lower: [row, ...]}` index.
- `_get_eu_candidates(designations)` builds an ordered candidate list from the designations dict (HD → GJ → HR → WASP → HAT_P → Kepler → TOI → K2 → CoRoT → COCONUTS → KOI → TIC → HIP → 2MASS → NAME → MAIN_ID) with normalizations:
  - Same Kepler/K2/WASP/HAT-P normalizations as OEC
  - For WASP-N, HAT-P-N, HD N: also tries `"<name> A"` as a fallback (exoplanet.eu often appends " A" to single-star systems)
  - NAME strips `"NAME "` prefix; MAIN_ID strips `"* "`, `"V* "`, `"NAME "` prefixes (enabling e.g. `"* tau Cet"` → `"tau Cet"` to match `star_name = "tau Cet"`)
- `_query_eu(designations)` returns a list of planet row dicts (all planets for matched star, sorted by `semi_major_axis` ascending) or `None`.
- `_eu_val(row, col)` returns stripped non-empty string or None; treats `"nan"` as None.
- Renders: SIMBAD star designations + info table, then `_display_eu_results()` which includes:
  - Star Name line (`star_name` from EU data + HD/HIP/HR/GJ from designations dict)
  - **Star Properties table** columns: Spectral Type (`star_sp_type`), MagV (3dp, `mag_v`), Temp (int K, `star_teff`), Mass (3dp Msun, `star_mass`), Radius (3dp Rsun, `star_radius`), Fe/H (3dp, `star_metallicity`), Age (2dp Gyr, `star_age`), Parsecs (4dp, `star_distance`), LYs (parsecs × 3.26156, 4dp).
  - **Planet Properties table** — one row per planet sorted by `semi_major_axis`: `#`, Planet Name (`name`), Mass(J) (4dp), Mass(E) (2dp, ×317.8), Rad(J) (4dp), Rad(E) (2dp, ×11.2), Period (3dp days, `orbital_period`), Distance as peri-SMA-apo AU (if ecc missing: `N/A - SMA - N/A AU`), Eccentricity (3dp), Temp (int K, `temp_calculated`), Method (`detection_type`), Year (`discovered`), Status (`planet_status`).
  - **Calculated Habitable Zone** via `_display_habitable_zone()` using `star_teff` and `star_radius` from the first planet row.
- If no match found, prints a message and returns to menu.
- Note: `pyExoplaneteu` is listed in `requirements.txt` but not used directly (the library has a CSV format compatibility bug); the feature fetches the CSV directly via `requests`.

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sp_type`, `plx_value`, `V`, `mesfe_h` (temperature in `mesfe_h.teff` column). Updated for astroquery ≥ 0.4.8 — prior names (`sptype`, `plx`, `flux(V)`, `fe_h`) are deprecated.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Result column names are lowercase: `main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `mesfe_h.teff`.
- Designations are pulled from `Simbad.query_objectids()`; the result column is `id` (lowercase).
- Parallax (mas) from `plx_value`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
