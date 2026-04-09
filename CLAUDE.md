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
  Star Databases                                    Calculators
  --------------                                    -----------
1. SIMBAD Lookup Query                              18. Distance Between 2 Stars
2. NASA Exoplanet Archive: All Tables               19. Stars within a Certain Distance of Sol
3. NASA Exoplanet Archive: Planetary Systems        20. Stars within a Certain Distance of a Star
4. NASA Exoplanet Archive: HWO ExEP Stars           21. Light Years per Hour to X Times the Speed of Light
5. NASA Exoplanet Archive: Mission Exocat Stars     22. X Times the Speed of Light to Light Years per Hour
6. Habitable Worlds Catalog                         23. Distance Traveled at a certain ly/hr within a certain time
7. Open Exoplanet Catalogue                         24. Distance Traveled at a certain X times the speed of light
8. Exoplanet EU Encyclopaedia                       25. Time to Travel # of Light Years at X LY/HR
                                                    26. Time to Travel # of Light Years at X Times the Speed of Light
  Star System Regions                               27. Travel Time Between 2 Stars (LYs/HR)
  ------------------                                28. Travel Time Between 2 Stars (X Times the Speed of Light)
9.  Star System Regions (SIMBAD)                    29. Distance Traveled at an Acceleration Within a Certain Time
10. Star System Regions (Semi-SIMBAD)               30. Travel Time Between 2 System Objs (Generic, Distance in AUs)
11. Star System Regions (Manual)                    31. Travel Time Between 2 System Objs (Generic, Distance in LMs)
                                                    32. Travel Time Between 2 System Objs (Planet/Moon/Asteroid)
  Science
  -------                                           Planetary Equations
12. Solar System Planet/Dwarf Planets/Asteroids     -------------------
13. Main Sequence Star Properties                   33. Planetary Orbit Periastron & Apastron Distance Calculator
14. Sol Solar System Regions                        34. Orbital Distance of an Earth-sized Moon with a 24 hour day
                                                    35. Orbital Distance of an Earth-sized Moon with a X hour day
  Science Fiction
  ---------------                                   Rotating Habitat Equations
15. Honorverse Hyper Limits by Spectral Class       --------------------------
16. Honorverse Acceleration by Mass Table           36. Centrifugal Artificial Gravity Acceleration at Point X (m/s^2)
17. Honorverse Effective Speed by Hyper Band        37. Distance from Point X to the Center of Rotation (m)
                                                    38. Rotation Rate at Point X (rpm)
  Utilities
  ---------                                         Misc. Equations
50. Star Systems CSV Query                          ---------------
Q.  Quit                                            39. Habitable Zone Calculator
                                                    40. Habitable Zone Calculator w/SMA
                                                    41. Star Luminosity
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

All three Star System Regions variants (options 9, 10, 11) produce identical output tables. They differ only in how their input values are obtained.

### Option 9: Star System Regions (SIMBAD) — `query_star_system_regions()`

- Menu option 9: fully automated — SIMBAD lookup + BC CSV lookup; `sunlightIntensity = 1.0`, `bondAlbedo = 0.3` hardcoded.
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

### Option 10: Star System Regions (Semi-SIMBAD) — `query_star_system_regions_semi_manual()`

- Menu option 10: same SIMBAD lookup, checks, and BC CSV lookup as option 9, but prompts the user for `sunlightIntensity` and `bondAlbedo` after all validations pass.
- Prompts (loop until valid float entered):
  - `Enter Sunlight Intensity (Terra = 1.0):` — blank defaults to `1.0`
  - `Enter Bond Albedo (Terra = 0.3, Venus = 0.9):` — blank defaults to `0.3`

### Option 11: Star System Regions (Manual) — `query_star_system_regions_manual()`

- Menu option 11: no SIMBAD lookup, no checks, no CSV lookup. All six input values are entered manually.
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

- Menu option 6: `query_habitable_worlds_catalog()` — runs the same SIMBAD lookup, then queries `hwc.csv` only.
- Data source: `hwc.csv` in the project directory, loaded once at first use into a module-level cache (`_HWC_DATA`).
- Helper: `_load_hwc()` reads the CSV and builds HIP/HD/S_NAME lookup indices (each maps uppercased key → list of planet row dicts); `_query_hwc(designations)` searches by HIP → HD → NAME priority; strips `"NAME "` prefix from the NAME designation before lookup.
- Planet rows sorted ascending by `P_SEMI_MAJOR_AXIS` before display.
- Renders four tables via `_print_table()`:
  - **Star Properties table** — one row from star-level fields: Star (`S_NAME`), HD (`S_NAME_HD`), HIP (`S_NAME_HIP`), Spectral Type (`S_TYPE`), MagV (`S_MAG`, 5dp), L (`S_LUMINOSITY`, 5dp), Temp (`S_TEMPERATURE`, integer), Mass (`S_MASS`, 2dp), Radius (`S_RADIUS`, 2dp), RA (`S_RA`, 4dp), DEC (`S_DEC`, 4dp), Parsecs (`S_DISTANCE`, 5dp), LY (`S_DISTANCE × 3.26156`, 4dp), Fe/H (`S_METALLICITY`, 3dp), Age (`S_AGE`, 2dp).
  - **Star Habitability Properties table** — one row: Inner Opt HZ (`S_HZ_OPT_MIN`), Inner Con HZ (`S_HZ_CON_MIN`), Outer Con HZ (`S_HZ_CON_MAX`), Outer Opt HZ (`S_HZ_OPT_MAX`), Inner Con 5 Me HZ (`S_HZ_CON1_MIN`), Outer Con 5 Me HZ (`S_HZ_CON1_MAX`), Tidal Lock (`S_TIDAL_LOCK`), Abiogenesis (`S_ABIO_ZONE`), Snow Line (`S_SNOW_LINE`); all 6dp.
  - **Planet Properties table** — one row per planet: Planet (`P_NAME`), Mass E (`P_MASS`, 2dp), Radius E (`P_RADIUS`, 2dp), Orbit (`P_PERIOD`, 2dp), Semi-Major Axis (`P_SEMI_MAJOR_AXIS`, 4dp), Eccentricity (`P_ECCENTRICITY`, 2dp), Density (`P_DENSITY`, 4dp), Potential (`P_POTENTIAL`, 5dp), Gravity (`P_GRAVITY`, 5dp), Escape (`P_ESCAPE`, 5dp).
  - **Planet Habitability Properties table** — one row per planet: Planet Type (`P_TYPE`), EFF Dist (`P_DISTANCE_EFF`, 5dp), Periastron (`P_PERIASTRON`, 5dp), Apastron (`P_APASTRON`, 5dp), Temp Type (`P_TYPE_TEMP`), Hill Sphere (`P_HILL_SPHERE`, 8dp), Habitable? (`P_HABITABLE`: `1`→`Yes`, `0`→`No`), ESI (`P_ESI`, 6dp), In HZ Con (`P_HABZONE_CON`: `1`→`Yes`, `0`→`No`), In HZ Opt (`P_HABZONE_OPT`: `1`→`Yes`, `0`→`No`).
  - **Planet Temperature Properties table** — one row per planet: Flux Min (`P_FLUX_MIN`, 5dp), Flux (`P_FLUX`, 5dp), Flux Max (`P_FLUX_MAX`, 5dp), EQ Min (`P_TEMP_EQUIL_MIN`, 3dp), EQ (`P_TEMP_EQUIL`, 3dp), EQ Max (`P_TEMP_EQUIL_MAX`, 3dp), Surf Min (`P_TEMP_SURF_MIN`, 3dp), Surf (`P_TEMP_SURF`, 3dp), Surf Max (`P_TEMP_SURF_MAX`, 3dp).
- If no match is found, prints a message and returns to menu.

## Open Exoplanet Catalogue Feature

- Menu option 7: `query_open_exoplanet_catalogue()` — runs the same SIMBAD lookup, then queries the Open Exoplanet Catalogue (OEC) only.
- Data source: downloaded once per session via `astroquery.open_exoplanet_catalogue.get_catalogue()` which fetches a gzip'd XML file from GitHub. Cached in module-level `_OEC_DATA = (root_element, name_index)`.
- `_load_oec()` calls `get_catalogue()`, calls `.getroot()` on the returned `ElementTree`, then builds a case-insensitive `{name_lower: system_element}` index by iterating all `<name>` elements across the entire tree.
- `_get_oec_candidates(designations)` builds an ordered candidate list from the designations dict (HIP → HD → GJ → HR → WASP → HAT_P → Kepler → TOI → K2 → CoRoT → COCONUTS → KOI → TIC → 2MASS → NAME → MAIN_ID) with normalizations:
  - `K2 N` → `K2-N`, `Kepler N` → `Kepler-N` (SIMBAD uses spaces, OEC uses dashes)
  - `WASP-94A` → `WASP-94 A` (SIMBAD omits space before component letter, OEC includes it)
  - `2MASS J...` → `2MASS ...` (SIMBAD includes leading `J`, OEC omits it)
  - NAME: strips `"NAME "` prefix; MAIN_ID: strips `"* "`, `"V* "`, `"NAME "` prefixes
  - Gaia EDR3 excluded (OEC uses Gaia DR2 IDs — incompatible)
- `_query_oec(designations)` returns `(system_elem, star_elems_list)` or `(None, [])`.
- `_find_stars_in_system(system_elem, matched_name_lower)` returns a **list** of `<star>` elements:
  - Always returns **all stars with planets** in the system, regardless of which star the query matched. This ensures binary systems like WASP-94 (A and B each with a planet) and Alpha Centauri (Proxima + Alpha Cen B) always show all planet-bearing stars.
  - If no stars have planets, falls back to all stars in the system.
- OEC XML structure: `<system>` may contain `<binary>` elements (nested arbitrarily), which contain `<star>` elements. `system.iter('star')` descends into all nesting automatically.
- Renders: SIMBAD star designations + info table, then `_display_oec_results()` which **iterates over each star** in `star_elems` and for each prints:
  - Star Name line (primary OEC name + up to 3 alternates from star `<name>` elements)
  - **Star Properties table** columns: Spectral Type (`spectraltype`), MagV (3dp), Temp (int K), Mass (3dp Msun), Radius (3dp Rsun), Fe/H (3dp), Age (2dp Gyr), Parsecs (4dp, from `system/distance`), LYs (parsecs × 3.26156, 4dp).
  - **Planet Properties table** — one row per planet sorted ascending by `semimajoraxis` (N/A last): `#`, Planet Name, Mass(J) (4dp), Mass(E) (2dp, ×317.8), Rad(J) (4dp), Rad(E) (2dp, ×11.2), Period (3dp days), Distance as `peri - SMA - apo AU` (if eccentricity missing: `N/A - SMA - N/A AU`), Eccentricity (3dp), Temp (int K), Method, Year, Status.
    - Status abbreviation map: "Confirmed planets"→"Confirmed", "Controversial"→"Controversial", "Retracted planet candidate"→"Retracted", "Solar System"→"Solar Sys", "Kepler Objects of Interest"→"KOI", "Planets in binary systems, S-type"→"Binary S".
  - **Calculated Habitable Zone** via `_display_habitable_zone()` using a synthetic row with `st_teff` and `st_rad` from OEC star fields.
- If `star_elems` is empty (system-level planets, no host star), prints a note and skips star/planet tables.
- If no match found, prints a message and returns to menu.

## Exoplanet EU Encyclopaedia Feature

- Menu option 8: `query_exoplanet_eu()` — runs the same SIMBAD lookup, then queries the Exoplanet Encyclopaedia (exoplanet.eu) only.
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

## Star Systems CSV Query Feature

- Menu option 50: `query_star_systems_csv()` — runs 17 SIMBAD criteria queries in sequence and writes results to `starSystems.csv`.
- Uses `query_criteria()` (deprecated but still functional) with `add_votable_fields("sp_type", "plx_value", "V", "ids")`. The deprecation warning is suppressed via `warnings.catch_warnings()`. `query_tap` ADQL was investigated but rejected: SIMBAD TAP does not support table-qualified column names (`basic.col`), `maintype` does not exist in the TAP schema, and the `mes_fe_h` JOIN causes syntax errors.
- **Query 1**: `"plx > 25.99 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'"` — stars closer than ~38.5 ly.
- **Query 2**: `"plx > 20.99 & plx < 26 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'"` — stars ~38.5–47.6 ly range.
- **Query 3**: `"plx > 17.99 & plx < 21 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')"` — stars ~47.6–55.6 ly range.
- **Query 4**: `"plx > 16.49 & plx < 18 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')"` — stars ~55.6–60.6 ly range.
- **Query 5**: `"plx > 15.49 & plx < 16.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')"` — stars ~60.6–64.6 ly range.
- **Query 6**: `"plx > 14.49 & plx < 15.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')"` — stars ~64.6–69.0 ly range.
- **Query 7**: `"plx > 13.99 & plx < 14.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~69.0–71.5 ly range.
- **Query 8**: `"plx > 13.49 & plx < 14 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~71.5–74.1 ly range.
- **Query 9**: `"plx > 12.99 & plx < 13.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~74.1–77.0 ly range.
- **Query 10**: `"plx > 12.49 & plx < 13 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~77.0–80.1 ly range.
- **Query 11**: `"plx > 11.99 & plx < 12.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~80.1–83.4 ly range.
- **Query 12**: `"plx > 11.49 & plx < 12 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~83.4–87.0 ly range.
- **Query 13**: `"plx > 11.09 & plx < 11.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~87.0–90.2 ly range.
- **Query 14**: `"plx > 10.79 & plx < 11.1 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~90.2–92.8 ly range.
- **Query 15**: `"plx > 10.49 & plx < 10.8 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~92.8–95.3 ly range.
- **Query 16**: `"plx > 10.29 & plx < 10.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~95.3–97.2 ly range.
- **Query 17**: `"plx > 9.99 & plx < 10.3 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')"` — stars ~97.2–100.1 ly range.
- Each query returns many raw rows (one per star measurement); deduplicates to unique stars in Python by `main_id`.
- **Discard rule**: rows where `main_id` starts with `"PLX "` AND `Star Designations` is empty AND `Spectral Type` is empty are silently dropped.
- **CSV columns**: `Star Name, Star Designations, Spectral Type, Parallax, Parsecs, Light Years, Apparent Magnitude, RA, DEC` (matches `templateStarSystems.csv`).
  - Star Name: `main_id`; Star Designations: comma-separated catalog IDs (GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS) parsed from pipe-separated `ids.ids` string via `_parse_designations_from_ids()`.
  - Parallax: 4dp; Parsecs = 1000/plx (3dp); Light Years = parsecs × 3.26156 (3dp); Apparent Magnitude: 3dp.
  - RA: converted from decimal degrees to sexagesimal `HH MM SS.SSSS` (divide by 15 to get hours). DEC: converted to `±DD MM SS.SSS`. Conversion is pure Python math, no extra libraries.
- **Backup**: if `starSystems.csv` already exists at startup, it is renamed to `starSystemsBackup-YYYYMMDD.csv` (e.g. `starSystemsBackup-20260405.csv`) before any queries run. The function then starts fresh with an empty dataset.
- **Deduplication**: `existing_ids` is passed as a live set to `_run_simbad_csv_query()` and updated in-place as rows are accepted — so each query automatically skips stars already captured by earlier queries. No separate cross-query dedup pass needed.
- **Sort**: all new rows from all queries are sorted together ascending by Light Years before writing.
- Helper `_run_simbad_csv_query(simbad, criteria, query_num, existing_ids)` encapsulates per-query fetch, row processing, discard logic, and deduplication; returns `(new_rows, discarded)`.
- Helper `_parse_designations_from_ids(ids_string)` and module-level `_CSV_PREFIX_MAP` / `_CSV_DESIG_KEYS` are defined before `MENU_OPTIONS`.
- More queries (different parallax ranges or criteria) can be added to the `queries` list in `query_star_systems_csv()`; each will merge into the same `starSystems.csv` with the same deduplication logic.

## Distance Between 2 Stars Feature

- Menu option 18: `query_distance_between_stars()` — computes the 3D Euclidean distance in light years between two star systems.
- Helper `_lookup_star_for_distance(designation)` handles SIMBAD lookup for a single star; returns `(name, ra_deg, dec_deg, ly, desig_str)` or `None` on failure.
  - Special case: if designation is `"sun"` or `"sol"` (case-insensitive), returns `(designation, 0.0, 0.0, 0.0, "")` with no SIMBAD query.
  - Queries SIMBAD with `add_votable_fields("plx_value")` and also calls `Simbad.query_objectids()` to build a short designation string (NAME, HD, HR, GJ, Wolf only).
  - Computes `ly = 1000 / plx_mas × 3.26156`.
- Math: converts each star's RA/DEC (decimal degrees from SIMBAD) + distance (ly) to 3D Cartesian coordinates; distance = `sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)`.
- Output table columns: Star | Star Designations | RA (HMS) | DEC (±DMS) | Light Years.
- After the table, prints `Distance Between <star1> and <star2>: X.XXXX Light Years`. If distance < 0.5 ly, also prints the distance in AU (`ly × 63241.077`).

## Stars within a Certain Distance of Sol Feature

- Menu option 19: `query_stars_within_distance()` — lists all stars in `starSystems.csv` within a user-supplied light year limit of Sol.
- Reads `starSystems.csv` directly; uses the `Light Years` column for distance comparison. No SIMBAD query.
- Prompts for a distance limit (float, must be > 0). Prints error if `starSystems.csv` not found (directs user to run option 50).
- Results sorted ascending by Light Years. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (4dp).

## Stars within a Certain Distance of a Star Feature

- Menu option 20: `query_stars_within_distance_of_star()` — lists all stars in `starSystems.csv` within a user-supplied light year limit of a queried star.
- Prompts for Star System Name and distance limit (float, must be > 0).
- Queries SIMBAD for the center star via `_lookup_star_for_distance()`.
- Reads `starSystems.csv`; for each row parses `Parallax` → ly, `RA` (sexagesimal HMS) → decimal degrees, `DEC` (sexagesimal ±DMS) → decimal degrees, then converts to 3D Cartesian coordinates and computes Euclidean distance from the center star.
- Skips any row with computed distance < 0.001 ly (eliminates the center star itself and floating-point near-zero matches).
- Results sorted ascending by distance. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (3dp).

## Speed / Velocity Converter Features

### Shared velocity conversion constant
- `8765.8128` = hours in a Julian year (365.25 × 24). Used to convert between ly/hr and multiples of c: `times_c = ly_hr × 8765.8128`.

### Option 21: Light Years per Hour to X Times the Speed of Light — `ly_per_hour_to_speed_of_light()`
- Prompts: `Enter velocity in light years per hour`
- Converts ly/hr → X times c: `times_c = ly_hr × 8765.8128`
- Output: single line showing both values.

### Option 22: X Times the Speed of Light to Light Years per Hour — `speed_of_light_to_ly_per_hour()`
- Prompts: `Enter velocity in X times the speed of light`
- Converts X times c → ly/hr: `ly_hr = times_c / 8765.8128`
- Output: single line showing both values.

## Distance Traveled Features

### Option 23: Distance Traveled at a certain ly/hr within a certain time — `distance_traveled_ly_per_hour()`
- Prompts: `Enter travel time in hours`, `Enter the velocity in light years per hour`
- Calculates: `distance = ly_hr × hours`
- Output: single line showing velocity, time, and distance in light years.

### Option 24: Distance Traveled at a certain X times the speed of light within a certain time — `distance_traveled_times_c()`
- Prompts: `Enter travel time in hours`, `Enter the velocity X times the speed of light`
- Converts to ly/hr first: `ly_hr = times_c / 8765.8128`, then `distance = ly_hr × hours`
- Output: single line showing velocity (×c), time, and distance in light years.

## Travel Time Features (Given Distance in Light Years)

### Shared helper: `_format_travel_time(total_hours)`
- Breaks total hours into Years, Months, Days, Hours, Minutes, Seconds.
- Only includes units that are ≥ 1 (seconds shown if < 1 minute total, or if remaining seconds ≥ 0.005).
- Uses Julian year: `HOURS_PER_YEAR = 365.25 × 24 = 8765.82`, `HOURS_PER_MONTH = HOURS_PER_YEAR / 12`.
- Returns a comma-separated string, e.g. `"5 Months, 24 Days, 11 Hours, 30 Minutes"`.

### Option 25: Time to Travel # of Light Years at X LY/HR — `time_to_travel_ly_at_ly_per_hour()`
- Prompts: `Enter number of light years`, `Enter velocity in light years per hour` (must be > 0)
- Calculates: `total_hours = distance_ly / ly_hr`, `times_c = ly_hr × 8765.8128`
- Output table columns: Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time

### Option 26: Time to Travel # of Light Years at X Times the Speed of Light — `time_to_travel_ly_at_times_c()`
- Prompts: `Enter number of light years`, `Enter velocity in X times the speed of light` (must be > 0)
- Calculates: `ly_hr = times_c / 8765.8128`, `total_hours = distance_ly / ly_hr`
- Output table columns: Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

## Travel Time Between 2 Stars Features

### Shared helper: `_travel_time_between_stars(velocity_label, velocity_prompt, use_times_c)`
- Used by options 27 and 28. `use_times_c=False` → velocity input is ly/hr; `use_times_c=True` → velocity input is X times c.
- Prompts: `Enter origin star`, `Enter destination star`, then the velocity prompt.
- Looks up both stars via `_lookup_star_for_distance()` (Sun/Sol → `(0.0, 0.0, 0.0)` with no SIMBAD query).
- Computes 3D Euclidean distance in ly using same Cartesian math as option 18.
- Converts velocity: if `use_times_c`, derives `ly_hr = times_c / 8765.8128`; else derives `times_c = ly_hr × 8765.8128`.
- `total_hours = distance_ly / ly_hr`; travel time formatted via `_format_travel_time()`.
- Output table columns (option 27): Origin | Destination | Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time
- Output table columns (option 28): Origin | Destination | Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

### Option 27: Travel Time Between 2 Stars (LYs/HR) — `travel_time_between_stars_ly_hr()`
- Calls `_travel_time_between_stars(..., use_times_c=False)`.

### Option 28: Travel Time Between 2 Stars (X Times the Speed of Light) — `travel_time_between_stars_times_c()`
- Calls `_travel_time_between_stars(..., use_times_c=True)`.

## Brachistochrone Calculator Features

### Physical constants (used by options 29–32)
- `G_MS2 = 9.80665` m/s² (1 g)
- `C_MS = 299,792,458` m/s (speed of light)
- `V_CAP_MS = 0.003 × C_MS` (0.3% of c = 899,377.374 m/s)
- `M_PER_AU = 149,597,870,700` m
- `M_PER_LM = C_MS × 60` m (metres per light-minute)
- All kinematics are non-relativistic (appropriate at v ≤ 0.3% c).

### Three acceleration profiles (used by options 30–32)
Options 30–32 are given a distance and solve for travel time.
- **Profile 1 — Continuous to Halfway Point**: accelerate for t/2, flip and decelerate for t/2. `t = 2 × √(d/a)`
- **Profile 2 — Half Continuous Accel Time, Coast, Then Decelerate**: accelerate t/4, coast t/2, decelerate t/4. `t = √(16d / (3a))`
- **Profile 3 — Accel to 0.3% c, Coast, Then Decelerate**: `t_cap = V_CAP / a`. If `a×t_cap² ≥ d`, cap not reached → use Profile 1 formula. Else: `t = 2×t_cap + (d - a×t_cap²) / V_CAP`.
  - When cap not reached, label appended with `"(cap not reached)"`.

### Option 29: Distance Traveled at an Acceleration Within a Certain Time — `distance_traveled_at_acceleration()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Travel Time in Hours` (> 0)
- Computes distance (metres → AU and LM) for each profile given the travel time.
- Profile 1 for this option differs from options 30–32: **Continuous Acceleration for Entire Time** — `d = ½ × a × t²` (no flip/decelerate).
- Profile 2: same as options 30–32 — accel t/4, coast t/2, decel t/4; `d = 3×a×t²/16`.
- Profile 3: accel to V_CAP then coast for remaining time — no decel (decel happens at destination outside the time window). `d = ½×a×t_cap² + V_CAP×(t - t_cap)`. Cap-not-reached condition: `t_cap ≥ t` (one phase only, not two); fallback is `d = ½ × a × t²`.
- Output table columns: Acceleration Profile | Acceleration (G's) | Travel Time (Hours) | Travel Time | Distance (AU) | Distance (LM)
- Row order: Profile 1, Profile 2, Profile 3.

### Option 30: Travel Time Between 2 System Objs (Generic, Distance in AUs) — `travel_time_between_system_objects()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Distance in AUs` (> 0)
- Converts AU → metres, then solves for travel time for each profile.
- Also computes `distance_lm = d_m / M_PER_LM` for display.
- Output table columns: Acceleration Profile | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time
- Row order: Profile 1, Profile 2, Profile 3.

### Option 31: Travel Time Between 2 System Objs (Generic, Distance in LMs) — `travel_time_between_system_objects_lm()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Distance in Light Minutes` (> 0)
- Converts LM → metres, then solves for travel time for each profile. Same formulas as option 30.
- Also computes `distance_au = d_m / M_PER_AU` for display.
- Output table columns: Acceleration Profile | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time
- Row order: Profile 1, Profile 2, Profile 3.

### Option 32: Travel Time Between 2 System Objs (Planet/Moon/Asteroid) — `travel_time_between_solar_system_objects()`
- Prompts: `Enter Origin Planet/Satellite/Asteroid`, `Enter Destination Planet/Satellite/Asteroid`, `Enter Acceleration in # of G's` (> 0), `Enter Max Velocity for Accelerate-to-Max-Velocity Profile (% of c, Default 0.3)` (blank → 0.3).
- Uses `astroquery.jplhorizons.Horizons` to fetch current heliocentric state vectors (x, y, z in AU) for both objects via `_get_heliocentric_vectors()`. Distance computed as 3D Euclidean: `sqrt((dx-ox)²+(dy-oy)²+(dz-oz)²)`.
- **Object name resolution**: `_resolve_horizons_id(name)` checks `_HORIZONS_ID_MAP` (normalized lowercase) first, then the last token of the input (handles "Jupiter's moon Io" → "io"), then falls through to pass the raw string to Horizons (handles numeric IDs like "433", asteroid designations like "1998 QE2").
- `_HORIZONS_ID_MAP`: module-level dict mapping ~100 common names to Horizons numeric IDs (8 planets, Sun, all major moons, dwarf planets, common asteroids/comets).
- Profile 3 velocity cap is user-configurable: `V_CAP_MS = (v_cap_pct / 100.0) × C_MS`. Label reads `"Accel to {v_cap_pct}% c, Coast, Then Decelerate"`.
- Same brachistochrone physics as options 30/31; Profile 1: `t = 2·√(d/a)`, Profile 2: `t = √(16d/(3a))`, Profile 3: `t = 2·t_cap + (d - a·t_cap²)/V_CAP` (falls back to Profile 1 if cap not reached).
- Error handling: ambiguous Horizons name prints the disambiguation table from the exception message + tip to use numeric ID; other errors print the exception; both return early. Same-object detection: distance < 1e-9 AU triggers error and early return.
- Output table columns: Acceleration Profile | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time
- Row order: Profile 1, Profile 2, Profile 3. Origin/Destination columns show user's raw input strings.

## Planetary Equations

### Option 33: Planetary Orbit Periastron & Apastron Distance Calculator — `planetary_orbit_periastron_apastron()`
- Prompts: `Enter the Planetary Semi-Major Axis (AU)` (> 0), `Enter the Planetary Orbit Eccentricity` (0 ≤ e < 1).
- Calculates:
  - `periastron = sma × (1 - e)`
  - `apastron = sma × (1 + e)`
  - `ecc_au = sma × e`
- Output table columns: Periastron (AU) | Semi-Major Axis (AU) | Apastron (AU) | Eccentricity | Eccentricity (AU); all 6dp.

### Option 34: Orbital Distance of an Earth-sized Moon with a 24 hour day — `moon_orbital_distance_24h()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0).
- Uses Kepler's third law: `r = (G × M_planet × T² / (4π²))^(1/3)` where `T = 86400 s`, `EARTH_MASS_KG = 5.972e24`, `G = 6.674e-11`.
- Converts result to km.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (fixed "24.0000") | Orbital Distance (km) (4dp).

### Option 35: Orbital Distance of an Earth-sized Moon with a X hour day — `moon_orbital_distance_x_hours()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0), `Enter Day in Hours` (> 0).
- Same Kepler's third law as option 34 but `T = day_hours × 3600 s`.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (4dp) | Orbital Distance (km) (4dp).

## Rotating Habitat Equations

### Option 36: Centrifugal Artificial Gravity Acceleration at Point X (m/s^2) — `centrifugal_gravity_acceleration()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Distance (m) from Point X to Center of Rotation` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `a = omega² × r`.
- Output table columns: Rotation Rate (rpm) (4dp) | Distance from Center (m) (4dp) | Centrifugal Gravity (m/s^2) (2dp).

### Option 37: Distance from Point X to the Center of Rotation (m) — `centrifugal_gravity_distance()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `r = a / omega²`.
- Output table columns: Rotation Rate (rpm) (4dp) | Centrifugal Gravity (m/s^2) (4dp) | Distance from Center (m) (2dp).

### Option 38: Rotation Rate at Point X (rpm) — `centrifugal_gravity_rpm()`
- Prompts: `Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X` (> 0), `Enter Distance (m) from Point X to Center of Rotation` (> 0).
- Calculates: `omega = sqrt(a / r)`, `rpm = omega × 60 / (2π)`.
- Output table columns: Centrifugal Gravity (m/s^2) (4dp) | Distance from Center (m) (4dp) | Rotation Rate (rpm) (2dp).

## Misc. Equations

### Shared helper: `_kopparapu_seff(teff, zone)`
- Returns Kopparapu et al. 2014 Seff boundary for six zone keys: `rv`, `rg5`, `rg01`, `rg`, `mg`, `em`.
- Formula: `Seff = SeffSUN + a×tS + b×tS² + c×tS³ + d×tS⁴` where `tS = teff - 5780`.
- Used by both `habitable_zone_calculator()` and `habitable_zone_calculator_sma()`.

### Option 39: Habitable Zone Calculator — `habitable_zone_calculator()`
- Prompts: `Enter the Star's Temperature (K)` (> 0), `Enter the Star's Luminosity (Lsun)` (> 0).
- Computes HZ boundary distances: `au = sqrt(luminosity / Seff)` for each of the six Kopparapu zones.
- Output: "Calculated Habitable Zone" table with Zone | AU columns; AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`.
- Zone order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (RG 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (RG 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars).

### Option 40: Habitable Zone Calculator w/SMA — `habitable_zone_calculator_sma()`
- Prompts: `Enter the Star's Temperature (K)` (> 0), `Enter the Star's Luminosity (Lsun)` (> 0), `Enter the Object's Semi-Major Axis (AU)` (> 0).
- Computes planet's Seff: `planet_seff = (1 / sma)² × luminosity`.
- Output: "Calculated Habitable Zone" table with Zone | AU | LM | Seff columns; object's Seff printed above the table (8dp).
- After table, prints HZ membership verdict based on Seff boundaries:
  - `< seff_em` → "NOT in HZ (Beyond Early Mars)"
  - `≤ seff_mg` → "Optimistic HZ (Between Maximum Greenhouse and Early Mars)"
  - `≤ seff_rg` → "Conservative HZ (Between Runaway Greenhouse and Maximum Greenhouse)"
  - `≤ seff_rv` → "Optimistic HZ (Between Recent Venus and Runaway Greenhouse)"
  - `> seff_rv` → "NOT in HZ (Interior to Recent Venus)"

### Option 41: Star Luminosity — `star_luminosity_calculator()`
- Prompts: `Enter the Star's Radius (R☉)` (> 0), `Enter the Star's Temperature (K)` (> 0).
- Calculates: `luminosity = radius² × (temp / 5778)⁴`.
- Output table columns: Radius (R☉) (4dp) | Temperature (K) (4dp) | Luminosity (Lsun) (6dp).

## Science Features

### Option 12: Solar System Planet/Dwarf Planets/Asteroids — `solar_system_data_tables()`
- Displays four sequential data tables from CSV files in the project directory.
- **Solar System Planets Data** — from `planetInfo.csv`; columns: Planet Name, Mass (J), Diameter (J), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity, Moons. AU values formatted as `{v:g} ({v × 8.3167:.3f} LM)`.
- **Moon Data tables** — from `moonInfo.csv`; grouped by planet in order: Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto; columns: Satellite Name, Diameter (km), Mass (kg), Perigee (km), Apogee (km), SemiMajor Axis (km), Eccentricity, Period (days), Gravity (m/s^2), Escape Velocity (km/s).
- **Solar System Dwarf Planets Data** — from `dwarfPlanetInfo.csv`; same columns as planets table but header row says "Dwarf Planet Name" and Mass is in Earth masses.
- **Solar System Major Asteroids Data** — from `asteroidsInfo.csv`; sorted ascending by Semimajor Axis; columns: Asteroid Name, Diameter (KM), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity.

### Option 13: Main Sequence Star Properties — `main_sequence_star_properties()`
- Reads `propertiesOfMainSequenceStars.csv` and displays all rows in a single table.
- Columns: Spectral Class, B-V, Teff (K), Abs Mag Vis, Abs Mag Bol, BC, Lum, R, M, p (g/cm3), Lifetime (years).

### Option 14: Sol Solar System Regions — `sol_solar_system_regions()`
- Displays all Star System Regions output tables for the Sun using hardcoded solar constants: `vmag = -26.74`, `boloLum = -0.07`, `temp = 5778 K`, `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`.
- Parallax back-computed from absolute magnitude: `plx = 1000 / (10^((vmag - absMag + 5) / 5))` ≈ 206265 mas.
- Calls the same shared display helpers as options 9–11: `_display_star_system_properties()`, `_display_stellar_properties()`, `_display_star_distance()`, `_display_earth_equivalent_orbit()`, `_display_solar_system_regions()`, `_display_alternate_hz_regions()`, `_display_calculated_hz()`.

## Science Fiction Features

### Option 15: Honorverse Hyper Limits by Spectral Class — `honorverse_hyper_limits()`
- Reads `spTypeHyperLM.csv` (no header; columns: Spectral Class, Light Minutes).
- Converts LM → AU: `au = lm / 8.3167`.
- Output table columns: Spectral Class | Light Minutes (2dp) | AUs (4dp).

### Option 16: Honorverse Acceleration by Mass Table — `honorverse_acceleration_by_mass()`
- Hardcoded table of ship mass ranges and acceleration values (no external data file).
- Output table columns: Ship Mass (tons) | Warship (Normal Space) | Merchantship (Normal Space) | Warship (Hyper Space) | Merchantship (Hyper Space).
- Six rows covering mass ranges from FG/DD (< 80,000 tons) through SD (7,000,000–8,499,999 tons).

### Option 17: Honorverse Effective Speed by Hyper Band — `honorverse_effective_speed()`
- Hardcoded data; displays two tables.
- **Table 1 "Effective Speed by Hyper Band"**: Alpha–Iota bands; columns: Band | Translation Bleed-Off | Velocity Multiplier | Warship (xC) | Merchantship (xC). Speeds shown as `{xc} ({xc / 8765.8128:.5f} ly/hr)`. Iota merchantship speed shown as "Currently Unattainable". Footnote about merchantmen not normally using Epsilon–Iota bands.
- **Table 2 "Effective Speed by Hyper Band (Expanded)"**: Alpha–Omega bands (24 total); columns: Band | Warship (xC) | Merchantship (xC). Same speed format as Table 1.
