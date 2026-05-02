# Star Databases Feature Documentation

Options 1–7, 50–52. All sections here involve querying external star/exoplanet data sources or managing the local data store. They change together when APIs, data schemas, or the DB layer is updated.

## Network Reliability (all online features)

All SIMBAD and NASA TAP queries use three shared helpers from `core/shared.py`:

- **`_make_simbad(*fields, timeout=30)`** — factory used by every SIMBAD caller except `compute_star_systems_csv` (which sets its own `simbad.TIMEOUT = 480`). Sets a 30 s instance timeout so interactive lookups don't hang indefinitely.
- **`_timeout_ctx(seconds)`** — context manager that sets the socket default timeout; used as an additional belt-and-suspenders layer around `query_object` and `query_objectids` calls.
- **`_with_retries(fn, retries=3, base_delay=2.0)`** — wraps any callable; on failure sleeps `base_delay × 2^attempt + jitter` seconds and retries. All three retry attempts exhaust before an error is surfaced. Used on every network call in this module.
- **`_network_error_msg(e, service)`** — classifies `requests.Timeout`, `requests.ConnectionError`, `urllib.error.URLError`, and string-pattern matches into user-friendly messages ("… timed out. Try again." / "Could not connect to … Check your network connection.").

`_query_tap` wraps its `requests.get` call in `_with_retries`; the 60 s per-request `timeout=` parameter is preserved. All callers of `_query_tap` (opts 2, 3, 4) surface failures via `_network_error_msg`. The optional HWO sub-query inside `compute_exoplanet_archive` keeps its silent `except: pass` because it is intentionally optional.

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sp_type`, `plx_value`, `V`, `mesfe_h` (temperature in `mesfe_h.teff` column). Updated for astroquery ≥ 0.4.8 — prior names (`sptype`, `plx`, `flux(V)`, `fe_h`) are deprecated.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Result column names are lowercase: `main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `mesfe_h.teff`.
- Designations are pulled from `Simbad.query_objectids()`; the result column is `id` (lowercase).
- Parallax (mas) from `plx_value`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.

## NASA Exoplanet Archive: All Tables Feature

- Menu option 2: `query_exoplanets()` — runs the same SIMBAD lookup first to resolve designations, then queries all three NASA Exoplanet Archive sources in sequence.
- Archive query uses TAP endpoint `https://exoplanetarchive.ipac.caltech.edu/TAP/sync` against the `pscomppars` table.
- Designation priority for archive query: HIP → HD → TIC → Gaia EDR3 (fields: `hip_name`, `hd_name`, `tic_id`, `gaia_id`).
- Results sorted ascending by `pl_orbsmax` (semi-major axis in AU).
- Luminosity: calculated as `(st_rad²) × (st_teff/5778)⁴`; displayed as `{st_lum} ({calculated})` when both `st_rad` and `st_teff` are available, otherwise falls back to `st_lum`.
- Distance (planet): periastron `pl_orbsmax - (pl_orbsmax × pl_orbeccen)`, semi-major axis, apastron.
- Helper functions: `_fval()` converts to float/None, `_fmt()` formats to fixed decimals, `_print_table()` renders two-line-header tables with dynamic column widths.
- After planet table, `_display_habitable_zone()` is called to render the habitable zone table — see Calculated Habitable Zone section below.
- After the habitable zone table, `_display_hwo_exep_results()` is called if the HWO ExEP query returned data (see HWO ExEP Archive shared helpers below).
- After the HWO section, `_query_mission_exocat()` is called and `_display_mission_exocat_results()` is shown if a match is found (see Mission Exocat Archive shared helpers below).

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

## Star Systems DB Query Feature (opt 50) / Export to CSV (opt 51) / Import Utilities (opts 52–56)

- Menu option 50: `query_star_systems_csv()` — runs 17 SIMBAD criteria queries in sequence and writes results to the `star_systems` DB table.
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
- **DB columns**: `star_name`, `designations`, `spectral_type`, `parallax`, `parsecs`, `light_years`, `app_magnitude`, `ra`, `dec`. These are also the column order written by opt 51's CSV export (`Star Name, Star Designations, Spectral Type, Parallax, Parsecs, Light Years, Apparent Magnitude, RA, DEC`).
  - Star Name: `main_id`; Star Designations: comma-separated catalog IDs (GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS) parsed from pipe-separated `ids.ids` string via `_parse_designations_from_ids()`.
  - Parallax: 4dp; Parsecs = 1000/plx (3dp); Light Years = parsecs × 3.26156 (3dp); Apparent Magnitude: 3dp.
  - RA: converted from decimal degrees to sexagesimal `HH MM SS.SSSS` (divide by 15 to get hours). DEC: converted to `±DD MM SS.SSS`. Conversion is pure Python math, no extra libraries.
- **Backup**: if the `star_systems` table is non-empty at startup, its rows are copied to `star_systems_backup_YYYYMMDD` (e.g. `star_systems_backup_20260405`) and `star_systems` is cleared before any queries run.
- **Deduplication**: `existing_ids` is passed as a live set to `_run_simbad_csv_query()` and updated in-place as rows are accepted — so each query automatically skips stars already captured by earlier queries. No separate cross-query dedup pass needed.
- **Sort**: all new rows from all queries are sorted together ascending by Light Years before writing.
- Helper `_run_simbad_csv_query(simbad, criteria, query_num, total_queries, existing_ids, progress_callback=None)` encapsulates per-query fetch, row processing, discard logic, and deduplication; returns `(new_rows, discarded)`.
- Helper `_parse_designations_from_ids(ids_string)` and module-level `_CSV_PREFIX_MAP` / `_CSV_DESIG_KEYS` are defined before `MENU_OPTIONS`.
- More queries (different parallax ranges or criteria) can be added to the `queries` list in `query_star_systems_csv()`; each will merge into the same `star_systems` table with the same deduplication logic.

## Export Star Systems to CSV Feature (opt 51)

- Menu option 51: `export_star_systems_csv()` — reads the `star_systems` DB table and writes `starSystems.csv` to the project directory.
- Output columns: `Star Name, Star Designations, Spectral Type, Parallax, Parsecs, Light Years, Apparent Magnitude, RA, DEC`. Rows sorted ascending by Light Years.
- Returns error if `star_systems` table is empty (directs user to run opt 50 first).
- Core function: `core.databases.export_star_systems_csv(output_dir)` → `{"path": ..., "count": ...}` or `{"error": ...}`.
- GUI panel: `ExportStarSystemsPanel` in `gui/panels/csv_utility.py`.

## Import HWC Data Feature (opt 52)

- Menu option 52: `import_hwc_data()` — loads `hwc.csv` from the project directory into the `hwc` DB table, replacing all existing rows.
- Validates that the file exists and contains the expected HWC column headers before replacing.
- Flushes the in-memory HWC cache (`_HWC_DATA = None`) so opts 2 and 6 pick up the new data immediately without a restart.
- Core function: `core.databases.import_hwc_csv(csv_path)` → `{"count": ..., "path": ...}` or `{"error": ...}`.
- GUI panel: `ImportHwcPanel` in `gui/panels/csv_utility.py`.

## Import Mission Exocat Data Feature (opt 53)

- Menu option 53: `import_mission_exocat_data()` — loads `missionExocat.csv` from the project directory into the `mission_exocat` DB table, replacing all existing rows.
- Core function: `core.databases.import_mission_exocat_csv(csv_path)` → `{"count": ..., "path": ...}` or `{"error": ...}`.
- GUI panel: `ImportMissionExocatPanel` in `gui/panels/csv_utility.py`.

## Import Main Sequence Star Properties Feature (opt 54)

- Menu option 54: `import_main_sequence_data()` — loads `propertiesOfMainSequenceStars.csv` from the project directory into the `main_sequence_stars` DB table, replacing all existing rows.
- Core function: `core.databases.import_main_sequence_csv(csv_path)` → `{"count": ..., "path": ...}` or `{"error": ...}`.
- GUI panel: `ImportMainSequencePanel` in `gui/panels/csv_utility.py`.

## Import Solar System Data Feature (opt 55)

- Menu option 55: `import_solar_system_data()` — loads `planetInfo.csv`, `moonInfo.csv`, `dwarfPlanetInfo.csv`, and `asteroidsInfo.csv` from the project directory into their respective DB tables, replacing all existing rows.
- Core function: `core.databases.import_solar_system_csvs(data_dir)` → `{"planets": int, "moons": int, "dwarf_planets": int, "asteroids": int}` or `{"error": ...}`.
- GUI panel: `ImportSolarSystemPanel` in `gui/panels/csv_utility.py`.

## Import Honorverse Hyper Limits Feature (opt 56)

- Menu option 56: `import_honorverse_hyper_data()` — loads `spTypeHyperLM.csv` from the project directory into the `honorverse_hyper` DB table, replacing all existing rows.
- Core function: `core.databases.import_honorverse_hyper_csv(csv_path)` → `{"count": ..., "path": ...}` or `{"error": ...}`.
- GUI panel: `ImportHonorversePanel` in `gui/panels/csv_utility.py`.
