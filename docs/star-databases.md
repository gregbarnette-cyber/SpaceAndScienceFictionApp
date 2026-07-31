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

- Uses `astroquery.simbad.Simbad` with votable fields: `sp_type`, `plx_value`, `V`, `mesfe_h` (temperature in the `mesfe_h.teff` column, metallicity [Fe/H] in the `mesfe_h.fe_h` column). Updated for astroquery ≥ 0.4.8 — the pre-0.4.8 top-level names (`sptype`, `plx`, `flux(V)`, `fe_h`) are deprecated (note: the live metallicity comes from the `mesfe_h.fe_h` **subcolumn**, not the deprecated top-level `fe_h` field).
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Result column names are lowercase: `main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `mesfe_h.teff`, `mesfe_h.fe_h`.
- `compute_simbad_lookup` returns an additive top-level `fe_h` key (float, or `None` when SIMBAD has no value) from the `mesfe_h.fe_h` subcolumn. It is consumed as the **real-anchor metallicity fallback** by the research-priors v2 generation path (`core.generate._resolve_anchor_feh` prefers a Hypatia [Fe/H], falling back to this SIMBAD value); `query.py simbad-lookup` carries it for free.
- Designations are pulled from `Simbad.query_objectids()`; the result column is `id` (lowercase).
- **Bayer & Flamsteed (Phase AN2, 2026-07-29).** `designations` carries two keys — **`Bayer`**
  (`* alf CMi`) and **`Flamsteed`** (`*  10 CMi`) — inserted directly after `NAME`. SIMBAD returns
  these under an asterisk-space prefix that `_CSV_PREFIX_MAP` cannot express (`* ` carries *two*
  designation systems, told apart by whether the first token is a bare integer), so they come from
  `core.shared._classify_star_id`'s pre-pass in `_match_designations`, not from a map row. Three
  things to know:
  - **Stored verbatim** — prefix intact, Flamsteed's **double space** preserved (`"*  10 CMi"`). The
    raw SIMBAD string is the identifier; turning it into `10 Canis Minoris` is Phase AN3's
    display-layer job and is never stored.
  - **For 22 of 43 sampled stars the Bayer id *is* `main_id`.** `core.shared._join_designations`
    therefore emits a repeated value **once**, keeping the first key — which, because `MAIN_ID` leads
    the only key list containing it, means the banner keeps `main_id` and drops the duplicate keyed
    copy. The dict still holds both, so `query.py` consumers see no suppression. On such a star the
    *visible* gain is the Flamsteed id, which is never a main id.
  - **`V*` (variable) and `**` (double-**system**) ids are classified but not captured** — `**` names
    a pair, not this star, and `V*` duplicates the Bayer form on nearly every star carrying both.
    `_classify_star_id` still returns `"Variable"`, so promoting it to a key later is one line.
  - The **narrow** key set behind opts 17/19/20/21 and the seven route planners deliberately does
    **not** gain these keys (those tables name the star in a separate column) — that is Phase AN's
    D7, still true. `star_systems.designations` **does** carry them as of the 2026-07-29 option-50
    rebuild (this bullet previously said it would not until a rebuild happened; one has) — see the
    opt-50 section below for the measured before/after.
  - **Rendering (Phase AN3, 2026-07-29) is a display layer and stores nothing.**
    `core.shared.format_star_designation("*  10 CMi")` → `"10 Canis Minoris"`;
    `format_designation_names(designations)` gives the `[(key, display), …]` pairs the GUI line
    `gui.panels.base.add_designation_names_line` renders beneath the banner on the same four panels
    as the Gould line. AN3 owns the **Greek abbreviation** table (`_GREEK_ABBREVIATIONS`, 24 letters
    verified against live SIMBAD — `mu.`/`nu.`/`pi.` carry a **trailing period**, and ξ/θ/ο are
    spelled `ksi`/`tet`/`omi`); the 88 **constellation genitives** are Phase AO's table, consumed
    here and never rebuilt. Superscript numerals render (`* alf01 Cen` → `α¹ Centauri`) — not an
    edge case, since α Cen A/B are the only corpus stars whose Bayer id survives the MAIN_ID dedupe.
    A `** ` double-*system* id renders as `None`, and an unknown constellation or an unmapped Bayer
    *extension* letter (`* b Vel` → `b Velorum`) degrades to the raw token rather than inventing one.
  - **When a star offers several competing `* ` ids, the pick is rule-based and deterministic** (D8,
    settled 2026-07-29 against a catalogue-wide census). Bayer prefers the component-less form and then
    the **superscript** one (`* ksi02 Cap` over `* ksi Cap` — in 47 of 49 such stars a numbered sibling
    exists, so the bare form does not say which star is meant); Flamsteed prefers the component-less form
    (`*   4 Cen` over `*   4 Cen A`) and then the constellation matching the chosen Bayer (which is what
    rejects Fomalhaut's cross-boundary `*  79 Aqr`). Where no rule can prefer — **α And *is* δ Peg** — the
    tie breaks on the raw string, so the pick is arbitrary but cannot drift when CDS reorders its ids.
    **No pick can be wrong**: SIMBAD attaches no `* ` id to more than one object (0 of 6293 measured).
  - **`core.shared.strip_star_prefix` is the one prefix stripper for display labels.** It strips
    `NAME `/`V* `/`* ` **and then `.strip()`s** — which matters only for Flamsteed, whose SIMBAD form
    carries a **double** space (`"*  18 Eri"`), so the fixed-width `name[len("* "):]` slice that three
    display sites used left a stray leading space (`" 18 Eri"`). That misrendered **796 live
    `star_systems` rows** before Phase AN existed. It deliberately leaves `** ` alone (that id names a
    different object). Use it rather than open-coding the slice —
    `tests/test_designation_display.py::StripperTest::test_no_display_site_open_codes_the_slice_any_more`
    fails if a copy returns.
- Parallax (mas) from `plx_value`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
- `compute_simbad_lookup` in `core/databases.py` checks `len(result) == 0` in addition to `result is None`; SIMBAD can return an empty table (not `None`) for unknown star names, and both cases now return `{"error": "No results found for '...'"}` cleanly.
- **GUI (`SimbadPanel`)**: the background call runs `_simbad_with_hypatia()`, which calls `compute_simbad_lookup` then `compute_hypatia_data` in a single thread. Results are presented in three tabs: **Star Properties** (designation banner + star properties table), **Hypatia** (Stellar Properties, Kinematics, and the full 104-species Elemental Abundances — grouped into per-nucleosynthetic-family sub-tables — via `build_hypatia_tab()`), and **Abundance Profile** (category-colored horizontal bar chart, scroll-wrapped; only shown when matplotlib is available and the star has elemental abundance data). A **Kinematics** tab (Phase O O11 — Toomre / galactic-kinematics diagram via `core.viz.prepare_toomre` → `make_toomre_canvas`, with an "ℹ What is this?" Explain button) is added beside Abundance Profile whenever Hypatia returns all three U/V/W velocities. See `docs/star-system-regions.md` for the canonical abundance shape and grouping.

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
- **GUI (`NasaPlanetarySystemsPanel`)**: background call uses `_planetary_systems_with_hypatia()`, which calls `compute_planetary_systems_composite` then `compute_hypatia_data`. Results are shown in **Data** and **Hypatia** tabs (inline `QTabWidget`). Show Diagrams view adds **Orbital Diagram** (with a Phase O O4 "Show Solar System reference" overlay checkbox + an O10b "Show Honorverse Hyper Limit (fiction)" checkbox when the host spectral type resolves), **HZ Diagram**, **Mass–Radius** (Phase O O3, when ≥1 planet has mass + radius), **Transit Geometry** (Phase O O13, when `st_rad` + ≥1 `pl_orbincl`), **Size Comparison** (Phase O O14, when ≥1 planet has a radius), **Abundance Profile** (when Hypatia data is available), and a **Kinematics** tab (Phase O O11 — Toomre diagram + Explain button, when Hypatia returns all three U/V/W velocities) to `_viz_tabs_widget`.
- **GUI (`NasaPlanetarySystemsMapPanel`)**: GUI-only nav entry "NASA Planetary Systems Map". A copy of `NasaPlanetarySystemsPanel` that adds a **Map Date** `QDateEdit` to the form (defaults to today) and a new **System Map** viz tab. System Map is a top-down 2D ecliptic-view diagram (style mirrors `make_solar_travel_canvas`) showing the host star at the origin and each planet at its date-resolved heliocentric position on its measured orbit. **Phase O O5a** adds a **date scrubber** under the map (`_SystemMapScrubber`: slider + ▶ Play/Pause + ⏮ Reset + "Map date:" readout) that re-runs the offline `prepare_exoplanet_system_diagram` for the scrubbed date and re-offsets only the epoch-known planet markers (`set_offsets`; orbits + host star stay static — no network); `epoch_known=False` planets stay pinned at periastron. Same Data / Hypatia tabs and the same Orbital Diagram (with the O4 solar-overlay checkbox) / HZ Diagram / Mass–Radius (O3) / Transit Geometry (O13) / Size Comparison (O14) / Abundance Profile viz tabs as opt 3. Click a planet on the map to open a non-modal info dialog populated entirely from the already-fetched pscomppars row (no extra network call). See `@docs/gui-architecture.md` for the diagram pipeline and click-dialog details.

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
- **GUI (`NasaHwoExepPanel`)**: background call uses `_hwo_exep_with_hypatia()`, which calls `compute_hwo_exep` then `compute_hypatia_data`. Results are shown in **Data** and **Hypatia** tabs. Show Diagrams view adds **HZ Diagram**, **Abundance Profile**, and a **Kinematics** tab (Phase O O11 — Toomre diagram + Explain button) when Hypatia data / all three U/V/W velocities are available.

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
- **GUI (`NasaMissionExocatPanel`)**: background call uses `_mission_exocat_with_hypatia()`, which calls `compute_mission_exocat` then `compute_hypatia_data`. Results are shown in **Data** and **Hypatia** tabs. Show Diagrams view adds **HZ Diagram**, **Abundance Profile**, and a **Kinematics** tab (Phase O O11 — Toomre diagram + Explain button) when Hypatia data / all three U/V/W velocities are available.

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
  - **Planet Properties table** — one row per planet: Planet (`P_NAME`), Mass E (`P_MASS`, 2dp), Radius E (`P_RADIUS`, 2dp), Orbit (`P_PERIOD`, 2dp), Semi-Major Axis (`P_SEMI_MAJOR_AXIS`, 3dp), Eccentricity (`P_ECCENTRICITY`, 2dp), Density (`P_DENSITY`, 4dp), Potential (`P_POTENTIAL`, 5dp), Gravity (`P_GRAVITY`, 5dp), Escape (`P_ESCAPE`, 5dp).
  - **Planet Habitability Properties table** — one row per planet: Planet Type (`P_TYPE`), EFF Dist (`P_DISTANCE_EFF`, 5dp), Periastron (`P_PERIASTRON`, 5dp), Apastron (`P_APASTRON`, 5dp), Temp Type (`P_TYPE_TEMP`), Hill Sphere (`P_HILL_SPHERE`, 8dp), Habitable? (`P_HABITABLE`: `1`→`Yes`, `0`→`No`), ESI (`P_ESI`, 6dp), In HZ Con (`P_HABZONE_CON`: `1`→`Yes`, `0`→`No`), In HZ Opt (`P_HABZONE_OPT`: `1`→`Yes`, `0`→`No`).
  - **Planet Temperature Properties table** — one row per planet: Flux Min (`P_FLUX_MIN`, 5dp), Flux (`P_FLUX`, 5dp), Flux Max (`P_FLUX_MAX`, 5dp), EQ Min (`P_TEMP_EQUIL_MIN`, 3dp), EQ (`P_TEMP_EQUIL`, 3dp), EQ Max (`P_TEMP_EQUIL_MAX`, 3dp), Surf Min (`P_TEMP_SURF_MIN`, 3dp), Surf (`P_TEMP_SURF`, 3dp), Surf Max (`P_TEMP_SURF_MAX`, 3dp).
- If no match is found, prints a message and returns to menu.
- **GUI (`HwcPanel`)**: background call uses `_hwc_with_hypatia()`, which calls `compute_hwc` then `compute_hypatia_data`. All HWC tables are placed inside a **Data** tab alongside a **Hypatia** tab (inner `QTabWidget`). Show Diagrams view adds **Orbital Diagram** (with the Phase O O4 "Show Solar System reference" overlay checkbox + an O10b "Show Honorverse Hyper Limit (fiction)" checkbox when `S_TYPE` resolves), **HZ Diagram**, **Mass–Radius** (Phase O O3, from `P_MASS`/`P_RADIUS`), **Size Comparison** (Phase O O14, from `P_RADIUS`), **Temperature Ranges** + **ESI vs Orbit** (Phase O O12 — per-planet equilibrium/surface temperature bars with the 273–373 K liquid-water band; SMA-vs-ESI scatter with the host's optimistic/conservative HZ shaded and points coloured by `P_HABITABLE`; each shown only when ≥1 planet qualifies), **Abundance Profile** (when Hypatia data is available), and a **Kinematics** tab (Phase O O11 — Toomre diagram + Explain button, when Hypatia returns all three U/V/W velocities). (No Transit Geometry tab — HWC carries no orbital inclination.)

## Open Exoplanet Catalogue Feature (opt 7 — rebuilt, Phase OEC)

Menu option 7: `query_open_exoplanet_catalogue()` (CLI) / `OecPanel` (GUI, `gui/panels/catalogs.py`).
Ground-up rebuild (see `completed_plans/PHASE_OEC_PLAN.md`). **OEC is a recursive `system → binary → star → planet →
satellite` hierarchy — not a flat table like options 1–6** — so a resolved system is rendered as a
**tree**, not property tables. Core: `core.databases.compute_oec(target)` →
`{"query", "matched_name", "system": <node>, ["simbad"]}` or `{"error"}`.

- **Data source + cache.** `systems.xml.gz` from the `oec_gzip` GitHub repo (~1 MB), parsed with stdlib
  `gzip` + `xml.etree.ElementTree` (the broken astroquery OEC module is not used). Cached at
  `data/oec/systems.xml.gz` (gitignored) with a 7-day staleness window (`_OEC_CACHE_MAX_AGE_DAYS`);
  offline after first pull, with a stale-cache fallback on network failure. Validate-before-cache
  (rejects a short download below `_OEC_MIN_SYSTEMS`). Memoized in `_OEC_DATA` (double-checked locking).
- **Node model — generic complete capture (D7).** `_oec_node()` walks every element into
  `{tag, names[], fields{}, children[]}`. `_oec_num()` keeps `value` + `errorminus/errorplus`,
  `upperlimit/lowerlimit`, `unit`, and `type` (e.g. `mass type="msini"`). **Any field may repeat → a list**
  (e.g. `separation` in AU+arcsec; `<list>` — a planet in a binary carries "Confirmed planets" *and*
  "Planets in binary systems, S-type"). `<satellite>` moons are captured as nested nodes.
- **Matching (D1).** `_norm_oec_name()` builds a normalized alias index over all `<name>` tags;
  resolution is **direct-alias-first, SIMBAD-fallback** — the typed name matches offline first, and only
  on a miss does `compute_oec` (when given a raw string) call `compute_simbad_lookup` to translate a
  common name → HD/HIP and retry. A planet name resolves to its system (trailing planet-letter stripped).
- **Expectation.** OEC lists only systems with planets/candidates, so a planetless star (Delta Pav,
  36 UMa) returns `"'…' is not in the Open Exoplanet Catalogue (which lists only systems with planets…)"`
  — a correct result, not a lookup error. A matched system may have **zero planets** (61 Cygni) and still
  renders its stellar hierarchy.
- **Display (shared formatters in `core.databases`).** `oec_fv` (first-or-list accessor — never read
  `field["value"]` directly), `oec_format_field` (`value ±err unit`; bound-only fields render `<= N`/`>= N`
  from the attribute), `oec_statuses` (all `<list>` statuses), `oec_binary_label` (synthesized "Binary
  (A + B)" for unnamed binaries). CLI prints an indented tree; **GUI (`OecPanel`)** renders a
  `QTreeWidget` (◆ system · ⋔ binary · ★ star · ● planet · ☾ moon) with a per-node property column,
  `M·sin i` labels, and multiple status badges. Spectral types (incl. white/brown dwarfs `DA…`/`T…`) are
  shown verbatim — not routed through the OBAFGKM parser.
- **`query.py`:** `oec-system --name` (full tree) and `oec-planet --name` (planet node + host chain +
  `attached_to` ∈ `star|binary|system`) — offline direct-alias resolution (`allow_simbad=False`), the same
  node dict serialized as JSON. **Phase 4** adds three catalogue-wide readers (no name, offline over the whole
  cache): `oec-search` (structural filters — star count, `--circumbinary`, planet status / discovery-method /
  discovery-year / mass / radius / period / sma ranges, host `--spectral-type` prefix → matched systems +
  topology + matching planets), `oec-census` (topology statistics — the §A evaluation live: counts,
  stars/planets/binary-depth distributions, `planet_attachment` star/binary/system, circumbinary/rogue/
  planetless, discovery-method + status histograms), and `oec-status` (cache freshness + element counts). See
  `docs/integration.md`.
- **GUI parity (Phase 2, built).** `OecPanel` is a `DiagramToggleMixin` matching `NasaPlanetarySystemsPanel`.
  Beyond the **Data** tree tab it adds — **per selected host star** (a **Host** `QComboBox` when a system has
  more than one planet-bearing star; single-host systems auto-select) — a **Hypatia** tab and **Show
  Diagrams** viz tabs: **Orbital Diagram** (+ O4 Solar overlay + O10b Honorverse hyper-limit ring),
  **HZ Diagram**, **Mass–Radius**, **Transit Geometry**, **Size Comparison**, **Abundance Profile**, and
  **Kinematics** (Toomre). All reuse the existing `core.viz` preps + the NASA panel's `_make_*_tab`
  builders via an OEC-node→NASA-key adapter (`_oec_host_to_nasa`, which converts planet mass/radius from
  Jupiter to Earth units) and the shared Hypatia path (`compute_hypatia_data` fed a `{designations,
  main_id}` compat built from the host star's OEC names — empty/graceful for M/BD/WD hosts). Hosts may be a
  **star** (normal), a **binary** (circumbinary/P-type pseudo-host), or the **system** (rogue → Data tab
  only, no diagrams). *Known limitation:* a circumbinary host's HZ uses the primary component's light, not
  the combined light (a `compute_circumbinary_hz` refinement — see `completed_plans/PHASE_OEC_PLAN.md`).
- **System Architecture map (Phase 3 — static 3a + interactive 3b, built 2026-07-19).** A **GUI-only**
  system-level viz tab (`OecPanel`, viz tab 0) shown for **every** matched system — including planetless
  (61 Cygni) and rogue ones that have no per-host diagrams. `core.viz.prepare_oec_architecture(system_node,
  focus_node=None)` places every star by a recursive **mass-weighted-barycenter (Jacobi) roll-up** (each
  `<binary>` splits its two components about their barycenter, offset `sep × m_other/(m₁+m₂)`), then maps them
  **log-radially** from the system barycenter so ~6 orders of scale coexist (Proxima 15 000 AU ↔ α Cen A/B
  23 AU ↔ planets < 1 AU); planets ride as small log-scaled rings on their host. Separation ladder:
  `semimajoraxis` → `separation[AU]` → `separation[arcsec]×distance_pc` (projected) → **Kepler**
  `a=∛((M₁+M₂)·P²)` from the binary period (61 Cyg) → schematic offset; a missing component mass → equal split
  (both flagged). Rendered by `plot_helpers.make_oec_architecture_canvas` (dark-navy Star-Chart palette) with
  a persistent caveat footnote (architecture sketch, not an ephemeris — projected separation, static placement
  / no orbital phase).
  - **Phase 3b interactivity (built 2026-07-19).** (1) **Click-to-recenter** — clicking a **star** re-anchors
    the log-radial view on it (`prepare_oec_architecture(system, focus_node=<node>)`) *and*, when that star is
    a planet host, drives the per-host detail tabs to it (the map replaces the Host combo as the selector);
    clicking a **binary ◆ handle** recenters on that subsystem's barycenter (e.g. α Cen AB → spreads the tight
    pair). A **breadcrumb + "⟲ Reset diagram"** bar sits above the canvas; the rebuild is deferred via a
    `QTimer.singleShot(0, …)` so the canvas isn't torn down inside its own pick-event, and the map (viz tab 0)
    stays selected across recenters without leaving diagram mode. **Reset diagram** is always available and does
    a full reset — it drops any recenter focus (back to the whole-system barycenter) **and** restores the
    default zoom/pan (via a `canvas.reset_view()` seam); with no focus set it is a pure zoom reset that doesn't
    tear down the detail tabs. (2) **Circumbinary (P-type) planet rings** —
    `prepare_oec_architecture` now emits a `centers:[{x,y,label,node,planets}]` for every `<binary>` carrying
    direct `<planet>` children (Kepler-16 b, Kepler-47…), keyed to the binary barycenter (reusing
    `_oecv_planet_ring_data`); the canvas draws these as **dashed** rings around that point (distinct from the
    solid per-star rings). (3) **Star-chart interaction parity** — scroll-wheel zoom around the cursor + a
    cursor-anchored hover tooltip (`_anchor_hover_to_cursor`, name/sp-type/mass/planet-count for stars,
    "click to recenter" for handles). Click semantics are reconciled: **hover = info, click = recenter**
    (for stars / ◆ handles). (4) **Click a planet → info dialog** — planet dots are pickable; clicking one
    opens a **non-modal planet dialog** (`_show_oec_planet_dialog`, parented to the panel) populated from the
    planet's OEC node (mass with the M·sin i label, radius, period, SMA, eccentricity, inclination, temp,
    discovery method/year, status badges, satellites) — no network, mirroring the NASA System Map's
    click-planet dialog. Each planet dict from `prepare_oec_architecture` carries its full `node` for this;
    the pick handler dispatches planet (→ `on_planet_click`, dialog) vs star/◆ (→ `on_select`, recenter).
  See `docs/gui-architecture.md` (OEC System Architecture map) and `completed_plans/PHASE_OEC_PLAN.md` §C Phase 3.
- **Phase status:** All phases built — 1 (core + tree + Tier-1 query.py), 2 (Hypatia + per-host diagrams), 3a
  (static Architecture map), 3b (interactive map — click-to-recenter + circumbinary rings + zoom/hover +
  click-a-planet dialog), 4 (`oec-search`/`oec-census`/`oec-status` structural readers), and 5 (the app-wide HZ
  Rings/Strip toggle, which OEC's HZ tab inherits via the shared `_make_hz_tab`). See `completed_plans/PHASE_OEC_PLAN.md`.

## HZ Diagram — Rings / Strip toggle (Phase 5, app-wide)

Every Star Databases panel's **HZ Diagram** tab carries a **Rings | Strip** segmented control (Rings default).
**Rings** is the unchanged concentric-zone `make_hz_canvas`; **Strip** is `make_hz_strip_canvas` — a horizontal
√AU view (same light palette) with the optimistic (Recent Venus → Early Mars) + conservative (Runaway GH → Max
GH) HZ bands and **planet markers placed by semi-major axis** (green inside the optimistic HZ, blue outside),
plus hover + click-to-info. Backed by `core.viz.prepare_hz_strip(teff, lum, planets)` (reuses the
`prepare_hz_diagram` Kopparapu zones) and the shared `gui.panels.diagram_tabs.wrap_hz_with_toggle` /
`_hz_toggle_tab`. Panels with planet data (NASA opt 3, HWC opt 6, OEC opt 7) show planet markers on the Strip;
single-star panels (Star Regions 8/9/10, Sol 13, NASA HWO/Exocat 4/5) show the bands alone. The System-Dossier
Report is a static PNG export, so it keeps Rings. See `docs/gui-architecture.md` (HZ Rings/Strip toggle).

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
  - **Currently a no-op.** SIMBAD has since reassigned those identifiers: sampling queries 1 and 17 (2026-07-26) returns **0** `PLX …` main_ids out of 40,655 rows, and the built table contains none. The rule is retained as a cheap defensive filter.
  - **It is a data-quality filter, not a crash guard.** It historically also removed most rows carrying degenerate `ra`/`dec` (which `_run_simbad_csv_query` writes as `""` when SIMBAD's value fails to parse), which masked an unguarded `IndexError` in opt 19's per-row coordinate parse. That parser is now hardened (see `docs/calculators.md`, opt 19) and every downstream viz prep skips `x is None`, so consumers must not depend on this rule to keep malformed rows out. Note that blank `spectral_type` (171k of 238k rows) and blank `designations` (678 rows) are already normal and handled everywhere.
- **DB columns**: `star_name`, `designations`, `spectral_type`, `parallax`, `parsecs`, `light_years`, `app_magnitude`, `ra`, `dec`. These are also the column order written by opt 51's CSV export (`Star Name, Star Designations, Spectral Type, Parallax, Parsecs, Light Years, Apparent Magnitude, RA, DEC`).
  - Star Name: `main_id`; Star Designations: comma-separated IDs — SIMBAD's common **NAME** first, then **Bayer, Flamsteed** (Phase AN2), then the catalog IDs (GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS) — parsed from the pipe-separated `ids.ids` string via `_parse_designations_from_ids()`. Output order follows the key list, so a named star reads `NAME Chara, GJ 475, HD 109358, HIP 61317, …` (* bet CVn).
    - **Bayer/Flamsteed ARE in the stored column** — option 50 was re-run **2026-07-29**, discharging
      the Phase AN2 D4 deferral the same day the phase closed. **2135 rows** now carry a `* ` token
      (1316 Bayer + 1591 Flamsteed). The lookup-vs-DB asymmetry that D4 described is gone: opts 18/19,
      opt 51's CSV export, the Route Planning tables and the G1 `designation_prefix` search all see
      them (`designation_prefix="*  10"` → 29 rows).
      - **The rebuild's row count did not move: 256,003 before and after, 0 discarded.** Adding keys
        *can* change the count — a row previously dropped by the `PLX …` rule for having an empty
        `desig_str` may now capture something — but SIMBAD currently returns **zero** `PLX ` main_ids,
        so the rule fires on nothing. (702 rows still have a blank `designations`; none is a `PLX `
        main_id.) Mechanism real, effect nil — re-measure rather than assume if the rule or the
        catalogue changes.
      - The stored picks follow the **D8 precedence rule**, not SIMBAD's id order — ξ Cap stores
        `* ksi02 Cap`, α Cen A stores `* alf01 Cen`. D8 was settled *before* this rebuild, so the
        column holds rule-based values; the reverse order would have required a second rebuild.
    - **No MAIN_ID here, so no duplicate.** This key list has no `MAIN_ID` entry (the main id goes to the separate `star_name` column), so the Bayer-equals-main_id duplication that `compute_simbad_lookup`'s banner has to dedupe cannot arise on this path.
    - **NAME first**: `core.databases._CSV_DESIG_KEYS` is now simply `core.shared._CSV_DESIG_KEYS` (which leads with `NAME`). It previously held a deliberately **NAME-less** copy, so SIMBAD's common name was parsed out of `ids` and then dropped — no `star_systems.designations` value ever carried one, and every surface fed by that column (opts 18/19, opt 51's CSV, the Route Planning tables, the Star Chart click-info box, the G1 search) showed catalog IDs only. **Do not re-introduce a local key set in `core/databases.py`.** Two consequences of the change: (1) rows written *before* it have no NAME token — **re-run option 50** to rebuild; (2) in principle the PLX discard rule above now keeps a `PLX …` row that has a NAME but no catalog ID and no spectral type — but **measured against live SIMBAD (2026-07-26) this is zero**: queries 1 and 17 (21,054 and 19,601 rows, the two ends of the parallax range) return **no** `PLX …` main_id at all, and the table held none either (re-measured 2026-07-29: **256,003 rows**, still **0** `PLX ` main_ids — the table was last rebuilt 2026-07-28, hence the growth from the 238,217 first measured). Expect the rebuilt row count to be unchanged. Those rows would be safe to admit anyway: opt 19's coordinate parse was hardened to skip malformed `ra`/`dec` rather than raise (see the discard-rule note above). Safe by construction: the GCNS cross-match regexes (`Gaia\s+E?DR3\s+(\d+)`, `2MASS\s+J?\s*([0-9+\-.]+)`) scan the whole string, and the G1 `designation_prefix` clause already tests both the leading-token and after-`", "` branches.
    - **Gaia prefix**: SIMBAD's `ids` output labels the Gaia source `"Gaia DR3 <id>"` (it no longer emits `"Gaia EDR3"`); DR3 ≡ EDR3 source_ids, so `_CSV_PREFIX_MAP` matches both `"Gaia DR3 "` and `"Gaia EDR3 "` into the `Gaia EDR3` slot. DR1/DR2 are intentionally **not** captured (their source_ids differ from EDR3/DR3). This is what lets the GCNS import (opt 58) cross-match on Gaia `source_id`. The same prefix handling is mirrored in `compute_simbad_lookup` and `core/shared._parse_designations` so `simbad-lookup`'s `designations["Gaia EDR3"]` is likewise populated with the `Gaia DR3` id.
  - Parallax: 4dp; Parsecs = 1000/plx (3dp); Light Years = parsecs × 3.26156 (3dp); Apparent Magnitude: 3dp.
  - RA: converted from decimal degrees to sexagesimal `HH MM SS.SSSS` (divide by 15 to get hours). DEC: converted to `±DD MM SS.SSS`. Conversion is pure Python math, no extra libraries.
- **Backup**: if the `star_systems` table is non-empty at startup, its rows are copied to `star_systems_backup_YYYYMMDD` (e.g. `star_systems_backup_20260405`) and `star_systems` is cleared before any queries run.
- **Backup pruning**: after a successful build, `core.db.prune_star_systems_backups(keep_n=3)` keeps only the **3 newest** `star_systems_backup_YYYYMMDD` tables (ranked by date stamp, which sorts chronologically) and drops the rest, so the dated backups can't accumulate forever. Only tables matching `^star_systems_backup_\d{8}$` are ever dropped — no other table is touched, and it is a no-op when ≤ 3 backups exist. The pruner returns `{"dropped": [...], "kept": [...]}` (both newest→oldest); `compute_star_systems_csv` surfaces these as `backups_dropped` / `backups_kept` in its result dict, and opt 50 reports them in its completion output (CLI print + GUI summary).
- **Deduplication**: `existing_ids` is passed as a live set to `_run_simbad_csv_query()` and updated in-place as rows are accepted — so each query automatically skips stars already captured by earlier queries. No separate cross-query dedup pass needed.
- **Sort**: all new rows from all queries are sorted together ascending by Light Years before writing.
- Helper `_run_simbad_csv_query(simbad, criteria, query_num, total_queries, existing_ids, progress_callback=None)` encapsulates per-query fetch, row processing, discard logic, and deduplication; returns `(new_rows, discarded)`.
- Helper `_parse_designations_from_ids(ids_string)` is defined before `MENU_OPTIONS`. **Phase AN0 (2026-07-29): it is now a thin wrapper over `core.shared._parse_designations_from_ids`, and `main.py`'s own `_CSV_PREFIX_MAP` / `_CSV_DESIG_KEYS` literals are deleted.** CLI opt 50 and GUI opt 50 write the *same* `star_systems.designations` column, so a second prefix map here would make the two builders write different content into one column as soon as a designation key is added. **Do not re-add a local map to `main.py`** — `tests/test_designation_harness.py::SharedMapGuardTest::test_the_shared_matcher_is_the_only_designation_loop_in_core` pins the count of match loops per module (`main.py` is allowed exactly the two display-only copies behind opts 1 and 17/19/20/21, which stay exempt per `IMPROVEMENT_PLAN.md` ground rule 1).
- More queries (different parallax ranges or criteria) can be added to the `queries` list in `query_star_systems_csv()`; each will merge into the same `star_systems` table with the same deduplication logic.

## Export Star Systems to CSV Feature (opt 51)

- Menu option 51: `export_star_systems_csv()` — reads the `star_systems` DB table and writes `starSystems.csv` to the project directory.
- Output columns: `Star Name, Star Designations, Spectral Type, Parallax, Parsecs, Light Years, Apparent Magnitude, RA, DEC`. Rows sorted ascending by Light Years. The export is a straight dump of the DB column, so `Star Designations` now leads with SIMBAD's `NAME …` token for named stars (see the opt-50 "NAME first" note above) — the column count/order is unchanged, but a downstream consumer that splits the field on `", "` and assumes index 0 is a catalog ID would shift.
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

## Import GCNS Data Feature (opt 58)

Adds the **Gaia Catalogue of Nearby Stars** (GCNS; Smart et al. 2021, A&A 649 A6) as a separate astrometric/completeness backbone with **Bayesian distances + uncertainties** — data the SIMBAD-built `star_systems` table lacks. GCNS is stored in its own isolated `gcns_stars` table; nothing about options 18/19/50/51 or the existing `star_systems` table changes. The data is exposed only via `query.py` — the readers `gcns-within-sol` (Phase T1a added the `--wd-prob-min/max` white-dwarf census filter), `gcns-source`, `gcns-system`, plus the GCNS-backed calculators `gcns-distance`, `gcns-travel-time`, `gcns-stars-within-star`, and the Phase T1c `substellar` census (L/T/Y by spectral-type prefix over `gcns_stars`, with a `completeness_note` JSON caveat) — all read-only consumers of the `gcns_stars`/`gcns_systems` tables; see `docs/integration.md`; no existing menu option displays it.

- Menu option 58: `import_gcns_data()` (CLI) / `ImportGcnsPanel` (GUI, in `gui/panels/csv_utility.py`). Core function: `core.databases.compute_gcns_ingest(progress_callback=None)` → `{total_rows, main_count, missing_count, simbad_matched, resolved_pairs, systems_count, systems_multi, members_in_stars, snapshot_date, gcns_version}` or `{"error": ...}`.
- **Source:** GAVO TAP service `https://dc.g-vo.org/tap`, tables `gcns.main` (331,312 rows), `gcns.missing_10mas` (1,259 known-nearby objects Gaia EDR3 missed — e.g. Alpha Cen A/B, Luhman 16), and `gcns.resolvedss` (19,176 resolved-pair rows — see "Resolved systems" below). All three are pulled in one opt-58 run so they share a single `snapshot_date`. Pulled via `pyvo` **async** jobs (`submit_job` → `run` → `wait` → `fetch_result` → `delete`) with `maxrec=400000`; sync mode is unusable (20k default cap, 60 s timeout). Wrapped in the shared `_with_retries`/`_timeout_ctx` helpers from `core/shared.py`; network errors classified via `_network_error_msg`.
- **Unit conversions:** GAVO distances `dist_16/50/84` are in **kpc** → ×1000 for pc; `light_years = dist_pc × 3.26156`. `gcns_prob` (probability astrometry reliable) → `astrom_reliable_prob`; `adoptedrv` → `rv_kms`.
- **`gcns.main` rows:** `distance_method = "gcns_bayesian"`, full Gaia photometry (`phot_g/bp/rp_mean_mag`), `wd_prob`, Bayesian `dist_pc`/`dist_lo_pc`/`dist_hi_pc`.
- **`gcns.missing_10mas` rows:** reduced schema (no Gaia `source_id`, no Bayesian distance, no Gaia photometry). `gaia_source_id = NULL`, `parallax = plx_value`, `dist_pc = 1000/plx` (1/ϖ inversion), `dist_lo_pc`/`dist_hi_pc`/photometry = `NULL`, `distance_method = "gcns_missing_plx_inversion"`, `star_name` = GCNS `main_id`. SQLite allows multiple NULL `gaia_source_id` under the UNIQUE index.
- **SIMBAD cross-match** (`_build_simbad_crossmatch`): attaches `spectral_type` / `star_name` / `app_magnitude` (Johnson V) from `star_systems` by exact key, in priority order — (1) Gaia EDR3/DR3 `source_id` parsed from `designations` (regex `Gaia E?DR3 (\d+)`; **DR2 ids are excluded** — they differ from EDR3/DR3), (2) normalised **2MASS** core (`_norm_2mass` strips the `2MASS J` prefix; GCNS `name_2mass` has no prefix), (3) exact `star_name` (for `missing_10mas` rows). No positional/fuzzy matching; unmatched rows keep `spectral_type`/`star_name`/`app_magnitude` = `NULL` and `in_simbad = 0` (never fabricated). **Note:** the cross-match yields matches only insofar as `star_systems` carries those keys — a `star_systems` build with no Gaia ids falls back to the 2MASS/name keys.
- **Hard rules honoured:** Gaia `G/BP/RP` are kept separate from the Johnson `V` column (`app_magnitude`); spectral types are never fabricated; matched rows carry `distance_method` so the distance basis is explicit.
- **Check gates (validate-before-destroy):** the build replaces the four GCNS data tables (`gcns_stars`, `gcns_systems`, `gcns_system_members`, `gcns_system_pairs`) **in place** (no backup table). (1) **Gate 1**, per table, *before any DB write* — abort if the pyvo result reports `OVERFLOW` or the row count is below its floor (`_GCNS_MAIN_MIN_ROWS = 330_000`, `_GCNS_MISSING_MIN_ROWS = 1_200`, `_GCNS_RESOLVED_MIN_ROWS = 19_000`; floors sit just under the known counts to tolerate a future GCNS version bump). A short/truncated download of *any* of the three tables therefore leaves all existing GCNS tables intact. (2) Transform + cross-match + resolved-system derivation. (3) `DELETE` of all four tables + bulk `INSERT` in **one transaction** (mid-insert crash rolls back). (4) **Gate 2**, post-commit — assert `gcns_stars` count ≥ `_GCNS_MAIN_MIN_ROWS` **and** `gcns_system_pairs` count ≥ `_GCNS_RESOLVED_MIN_ROWS`, then record provenance into `gcns_meta`.
- **`gcns_meta` table** (key/value): `snapshot_date`, `gcns_version`, `gcns_main_count`, `gcns_missing_count`, `total_count`, `simbad_matched`, `gcns_resolved_pairs`, `gcns_systems_count`, `gcns_systems_multi` (systems with >2 components), `gcns_members_in_stars` (resolved-system members that link to a `gcns_stars` row). Surfaced in the `snapshot_date`/`gcns_version` fields of the `query.py` GCNS results.

### Resolved systems (`gcns.resolvedss`)

GCNS exposes Gaia-resolved multiples in `gcns.resolvedss`, so consumers can tell **rows ≠ systems**. The real schema (introspected from GAVO `TAP_SCHEMA`, 19,176 rows): the table is **pair-keyed** — one row per resolved pair, with **no system-identifier column**. Columns: `source_id1` / `source_id2` (the two components' Gaia EDR3 source_ids), `separation` (arcsec), `mag_diff` (Gaia G mag difference), `proj_sep` (projected separation, **AU**), `bin` (`1` if the pair probably belongs to a >2-star system), `bound` (`1` if probably gravitationally bound).

- **Systems are derived as connected components** over the pair graph (union-find, in `_gcns_build_systems`). Chaining pairs that share a component (A-B and B-C → one 3-component system) yields the full membership. `system_id` is **synthetic and deterministic**: components are ordered by their smallest member source_id and numbered from 1, so the same snapshot always produces the same ids. The 19,176 pairs collapse to ~17,103 systems (≈16,293 binaries, the rest higher-order).
- **Storage (isolated, additive):** three new tables in `core/db.py`. `gcns_systems` (one row per derived system: `system_id`, `n_components`, `n_pairs`, `any_bin`, `any_bound`, `all_bound`, `max_proj_sep_au`, `min_proj_sep_au`, `n_in_gcns_stars`). `gcns_system_members` (membership join: `system_id`, `gaia_source_id`, `in_gcns_stars`; indexed on both `system_id` and `gaia_source_id`). `gcns_system_pairs` (the raw resolvedss edges mapped into their system: `system_id`, `source_id1`, `source_id2`, `separation_arcsec`, `mag_diff`, `proj_sep_au`, `bin`, `bound`; indexed on `system_id`).
- **Non-destructive linkage to `gcns_stars`:** component rows in `gcns_stars` are **never** collapsed or deleted — multiplicity is exposed by join on `gaia_source_id`. As a convenience, two **nullable, additive** columns (`system_id`, `n_components`) are populated on `gcns_stars` rows during ingest (NULL for `missing_10mas` rows, which have no source_id to join, and for any source not in a resolved pair). These are added via an idempotent `ALTER TABLE` migration (`_migrate_schema` in `core/db.py`) so existing databases pick them up.
- **No fabricated membership:** a `source_id` not present in `gcns.resolvedss` is a single/unresolved object — its `system_id`/`n_components` stay NULL and `gcns-system` returns an error for it. Members listed in `resolvedss` whose `source_id` is **not** in `gcns_stars` (e.g. a secondary fainter than the GCNS cut) are **retained** in `gcns_system_members` and flagged `in_gcns_stars = 0` — never silently dropped.
- **DB impact:** `gcns_stars`, `gcns_systems`, `gcns_system_members`, `gcns_system_pairs` are **not** auto-seeded (like `star_systems`); they exist empty until opt 58 runs, and add ~55–65 MB to `data/space_app.db` (which is gitignored). Schema/DDL is in `core/db.py` (the four tables + `gcns_meta` + indexes on `gaia_source_id`, `light_years`, the two membership keys, and the pair `system_id`).

### Known limits (documented, not "fixed")

- **Substellar incompleteness is fundamental.** GCNS (Gaia-only) is ~95% complete only to ~M7–M8; L/T/Y dwarfs are too faint for Gaia beyond ~10–25 pc. `gcns.missing_10mas` patches a small set of known bright/nearby objects Gaia missed, but the cold-dwarf census stays partial beyond ~25 pc. A fuller cold-dwarf census would need the IR-parallax samples (Best et al. 2021, Kirkpatrick et al. 2021) as supplementary inputs — not included here.
- **Distances:** `gcns.main` uses GCNS Bayesian distances (Bailer-Jones-style); `missing_10mas` rows fall back to biased `1/ϖ` inversion and are flagged via `distance_method`.
- **Snapshot/version:** GCNS is Gaia EDR3-based and static; the pull date and catalogue/source string are recorded in `gcns_meta` for reproducibility.
- **Resolved systems cover only Gaia-resolved multiples.** `gcns.resolvedss` is built from Gaia's own astrometry, so it captures pairs Gaia could resolve; unresolved (close/spectroscopic) binaries and wide or literature-only companions are **not** in it — a `source_id` returning "not part of any resolved system" means *not Gaia-resolved*, not necessarily single. The connected-component grouping is a friends-of-friends linkage: a small number of dense regions chain into large spurious "systems" (the largest derived component has ~159 members). These are represented faithfully (not dropped); the per-pair `bin`/`bound` flags and `proj_sep_au` let consumers filter. Treat `n_components` from chained pairs as an upper bound on true multiplicity in crowded fields.

### GCNS Display Surfaces (Phase M — GUI-only)

Until Phase M, GCNS was reachable only through `query.py`. Phase M adds six **GUI-only** panels (new **"GCNS"** nav category, panel classes in `gui/panels/gcns.py`; see `docs/gui-architecture.md`) plus the opt-1 SIMBAD enrichment (M5). Every panel **reuses the existing `compute_gcns_*` readers verbatim** — no new core code except M5. The headline everywhere is the **Bayesian distance with `dist_lo_pc`/`dist_hi_pc` (−σ/+σ) uncertainty** — the only distance error bar in the app; `missing_10mas` rows show a `—` (1/ϖ point value).

- **GCNS Census Browser** (`GcnsCensusBrowserPanel`, M1) → `compute_gcns_within_sol(ly)`. Instant local read (no SIMBAD/thread). Table: Star Name · Gaia source_id · Spectral Type · Dist (pc) · −σ/+σ (pc) · Light Years · Distance Method · In SIMBAD; reuses the opt-18/19 **Star Chart** + **Star Chart 3D** diagram tabs.
- **GCNS Source Lookup** (`GcnsSourceLookupPanel`, M2) → `_resolve_gcns_row(star=|source_id=)`. Single-source detail; Gaia G/BP/RP kept explicitly separate from Johnson V; a resolved-system pointer when `system_id` is set, otherwise a muted "not part of a Gaia-resolved multiple system (single or unresolved)" note — so the multiplicity status shows either way and Source Lookup agrees with the System Viewer.
- **Resolved System Viewer** (`GcnsSystemViewerPanel`, M3) → `compute_gcns_system(source_id)` (name path resolves to a Gaia id first). System Summary + Members (▶ on the queried component) + Pairs.
- **GCNS Distance / Travel Time / Stars Within a Star** (`GcnsDistancePanel` M4a, `GcnsTravelTimePanel` M4b, `GcnsStarsWithinStarPanel` M4c) → `compute_gcns_distance` / `compute_gcns_travel_time` / `compute_gcns_stars_within_star`. M4c keeps Gaia-resolved close companions (excluded only by exact source_id) and reuses the opt-18/19 **Star Chart** + **Star Chart 3D** tabs with the center gold-highlighted.
- **Resolution model:** M2/M3/M4 take a **name** (SIMBAD → Gaia id, background thread) **or** a raw **Gaia source_id** (offline, instant); the id wins if both are filled. Not-in-GCNS / ambiguous-name / empty-table errors come straight from the core functions.

**M5 — opt-1 SIMBAD GCNS cross-reference.** `compute_simbad_lookup` gains a **non-fatal, silent** top-level `"gcns"` key (`_simbad_gcns_block`): it parses the Gaia id from the designations and attaches the matching `gcns_stars` row (Bayesian `dist_pc` + `dist_lo_pc`/`dist_hi_pc`, `distance_method`, Gaia G/BP/RP, `astrom_reliable_prob`, `wd_prob`, `system_id`/`n_components`) — a single indexed local read, no extra network. `None` when there is no Gaia id, the source is not in GCNS, or the table is empty. `SimbadPanel` shows it as a **"GCNS" tab** (Bayesian distance + σ beside the naive 1/ϖ distance); `query.py simbad-lookup` carries the key for free. See `docs/integration.md`.

## Gould Designations (Phase AO)

The star's *Uranometria Argentina* (B.A. Gould, 1879) designation — **HD 102365 = 66 G.
Centauri**, **GJ 432 A / HD 100623 = 289 G. Hydrae**. Attached to `compute_simbad_lookup`
as a **non-fatal, silent** top-level `"gould"` key (`_simbad_gould_block`), exactly like
M5's `gcns`.

**Why this is a data layer, not a parser change.** **SIMBAD has no Gould identifiers at
all** — verified against the live `ident` table (2026-07-28): `id LIKE 'G. %'` → 0 rows,
`id LIKE '% G. %'` → 0 rows, and `'%Gould%'` returns only `NAME Gould('s) Belt` (the
nebular structure). CDS never ingested Gould's cross-identifications, so no amount of
designation parsing can surface them.

- **Source:** VizieR **`V/135A/catalog`**, exported once to the committed
  **`gouldDesignations.csv`** (8471 rows, ~310 KB) rather than queried live — the catalogue
  closed in 1879, and a per-star CDS round-trip would make the SIMBAD panel's latency depend
  on VizieR availability. Columns: `g_number, cst, hd, sao, flamsteed, bayer, name, vmag`,
  under `#` provenance comment lines. *(The export must request `columns=['**']`; VizieR's
  default `'*'` returns a subset with **no `SAO` column**. The SAO join was later removed as
  unreachable — see the Join bullet — but the column is exported and stored, so the flag still
  matters for a re-export.)*
- **Storage:** the `gould_designations` table (`core/db.py`), **auto-seeded** via
  `_STATIC_TABLES` like `main_sequence_stars` / `planets` / `honorverse_hyper` — it
  populates itself on first `get_conn()`, with no import step, since frozen data needs no
  refresh path. Indexed on `hd` and `sao`. Listed in the **Database Table Status** panel.
- **Type coercion is load-bearing** (`_gould_num`): blanks become **`NULL`, never
  empty-string TEXT**, and a row with no Gould number is **kept** (it still carries HD/SAO).
  Neither seeding precedent in `core/db.py` does this — `_seed_main_sequence` inserts raw
  strings, `_seed_honorverse_hyper` drops the whole row on a bad value. It matters because
  SQLite orders `NULL < INTEGER < TEXT`, so a mixed column would make the tie-break below
  pick the wrong component of a double star. Pinned by a `typeof()` assertion in
  `tests/test_gould.py`.
- **Join: `HD` only.** The integer is parsed out of the designation string
  (`"HD 102365"` → `102365`). **11 HD values sit on two rows** (multi-component systems) —
  lowest `g_number` wins, resolved in SQL, with an `AND g_number IS NOT NULL` filter that is
  load-bearing because **SQLite sorts NULL first** (without it an un-numbered row sharing the
  HD would win). **SAO has zero duplicates** (measured 2026-07-29 over all 8415 non-null
  values).
  - **An `SAO` fallback was built and then removed** (code review, 2026-07-29). It was
    **unreachable**: `designations` can never carry an `"SAO"` key — neither
    `core/databases.py`'s `keys_order`/`prefix_map` nor the shared `_CSV_PREFIX_MAP` captures
    SAO ids — and the test that "covered" it hand-built `{"SAO": …}`, a dict shape the
    pipeline never produces, so it passed against dead code. `matched_on` is therefore always
    `"hd"`; the `sao` column is retained in the schema and echoed in the block.
  - **Reviving it is Phase AN's call, not a bug fix.** SIMBAD *does* emit `SAO nnnnn`, so the
    fallback is implementable — but only by adding SAO to the designation key set, which also
    injects `SAO nnnnn` into `desig_str` on all four GUI banners and into the `query.py`
    contract. That is AN2's "key insertion + ripple", and AN is already going to touch this
    exact map. **Payoff if taken up: 26 catalogue rows carry an SAO number but no HD, of which
    only 3 have a Gould number.** `tests/test_gould.py::test_sao_is_absent_from_the_designation_key_set`
    fails the moment SAO starts being captured, as the prompt to reconsider.
- **Contract:** `{g_number, cst, constellation, designation, display, hd, sao, matched_on,
  source}`. `designation` = `"66 G. Cen"`, `display` = `"66 G. Centauri"`, built from
  `g_number` + `cst` via the 88-entry `core.shared._CONSTELLATION_GENITIVES` table (**owned
  here; Phase AN3 consumes it for Bayer/Flamsteed rendering and must not rebuild it**).
  An unrecognised code degrades to the raw abbreviation — a name is never invented.
- **Display:** a **`Gould: 101 G. Eridani`** segment on the historical-names line beneath the
  designations banner on all four SIMBAD-fed panels (`SimbadPanel`, `star_regions`,
  `nasa_exoplanet`, `catalogs`), via the shared
  `gui.panels.base.add_gould_line(layout, simbad, inline_with=<the AN3 label>)` — passing
  `inline_with` **appends** it to the Phase AN3 Bayer/Flamsteed label instead of starting a second
  line, so the star reads `Bayer: ε Eridani · Flamsteed: 18 Eridani · Gould: 101 G. Eridani`
  (with `inline_with=None` — a star with no Bayer/Flamsteed id — it still gets its own line).
  Plus a **"Gould designation"** row in the Phase Q
  system dossier's identity block. Deliberately **not** folded into the `designations` dict:
  that dict means "what SIMBAD returned", and mixing a VizieR value in would make `desig_str`
  misattribute provenance and put a non-SIMBAD string into `star_systems.designations`
  semantics.

### Two documented caveats (not bugs)

- **Coverage is intentionally partial.** Gould catalogued **bright southern stars** only;
  7756 of the 8471 rows carry a Gould number. **`None` is the normal, correct answer for most
  stars** — an absent designation is coverage, not a lookup failure.
- **1875 constellation boundaries.** Gould predates the IAU, so `cst` sometimes names a
  different constellation than the star sits in today. **HD 100623 is `Hya` in the catalogue
  but lies in Crater now** — SIMBAD's own Flamsteed id for it is `*  20 Crt`. The app will
  therefore show **both** "20 Crateris" and "289 G. Hydrae" for the same star. **This is
  correct and must not be "reconciled"** — each designation is right within its own epoch.

## Phase G — Interactive Search & Filtering

Three filter functions backing the GUI **Search & Filter** nav category. **No CLI
menu option**; originally GUI-only, they were later exposed as `query.py`
subcommands (`search-star-systems` / `search-hwc` / `search-exoplanets`, all
filters optional — see `docs/integration.md`). Each returns a dict
`{"count": int, "capped": bool, "cap": int, "stars": [row dicts]}` or
`{"error": str}` — always check for `"error"` before reading `stars`.

### Shared spectral-class control

All three filter spectral type with a friendly **chips + refine** control, not a
raw `LIKE` box. Two core filter keys (in `core/shared.py`):

- `spectral_classes: list[str]` — selected chips from `O B A F G K M Other`.
  Each letter → a parameterized **case-sensitive `GLOB`** term per allowed
  luminosity prefix, OR-ed together; `Other` is the **exact complement** of the
  same expression over all seven letters, plus NULLs — so a star can never be
  returned under both a letter chip and `Other`.

  **Why GLOB and not LIKE (the load-bearing detail).** SQLite's `LIKE` is
  case-**insensitive** for ASCII, so it cannot distinguish the lowercase *dwarf*
  prefix `d` (`dM6` = Wolf 359, an M dwarf) from the uppercase *degenerate*
  prefix `D` (`DA`/`DZ7.5` = white dwarfs). `GLOB` is case-sensitive. Verified:
  `core/db.py` sets no `PRAGMA case_sensitive_like`, no custom collation, and no
  `like()`/`glob()` UDF, so the default semantics hold on this connection.

  The prefix set is `core.shared._SP_CLASS_PREFIXES` — `''`, `d`, `sd`, `esd`,
  `usd`, `k`, `h`, `kn`, `d/sd`, `sd:`, `s/sd`, `(sd)` — derived from a census of
  every distinct string preceding the first uppercase OBAFGKM letter in
  `star_systems` + `gcns_stars`. `d`/`sd`/`esd`/`usd` are Yerkes/Gliese
  luminosity prefixes (dwarf / subdwarf); `k`/`h`/`kn` are the **Am/Ap
  line-type** notation (Ca II K-line / hydrogen-line type) — *not* a luminosity
  prefix and *not* a binarity marker (that is the `+` in e.g.
  `kA0hA7Sr+kA2hF2mF2(IV)`). `core.shared.spectral_leading_class(sp)` is the
  Python counterpart of the same rule. The equivalence is not enforced at runtime —
  it is pinned by `tests/test_search.py::test_sql_and_python_rules_agree`, which
  cross-checks both implementations over a sample covering every prefix; run it after
  changing either one. `spectral_leading_class(sp, letters=...)` also backs the
  **colour/legend** path via the wider `_SP_DISPLAY_LETTERS` set — see "Spectral
  colour & legend bucketing" below.

  **Bucketing changes (2026-07-27).** Chip `M` gained 2,707 rows in
  `star_systems` (`dM*` 2,394 · `sdM*` 194 · `esdM*` 75 · `usdM*` 28 · misc) —
  Wolf 359 (`dM6`) and Ross 128 (`dM4`) now appear under `M` instead of `Other`.
  `A` +103, `F` +8, `G` +5, `B` +4, `O` +1. **Chip `K` lost 75**: the ~107
  lowercase `kA…` Am/Ap stars were previously matched by the case-insensitive
  `LIKE 'K%'` — a second, separate pre-existing bug — and are now correctly filed
  under `A`/`F`. An Am star buckets by its **first** class letter
  (`kA5hF0mF2` → `A`), matching `_SP_PATTERN`, which already drives BC/Teff/HZ/HR
  everywhere else; the astronomically better hydrogen-line-type rule (→ `F`) was
  considered and declined, since adopting it would require changing `_SP_PATTERN`
  app-wide. White dwarfs (`DA`, `DZ7.5`, `DQ`, `DA+dM`), brown dwarfs
  (`L`/`T`/`Y`), and blank/NULL types are unchanged and remain in `Other`.
  Verified invariant on live data: chips ∪ `Other` = every row exactly once, with
  zero overlap between any two chips (all 21 pairs, across `star_systems`,
  `gcns_stars`, and `hwc`).

  **Spectral colour & legend bucketing (Part 2, 2026-07-27).** The same rule, with a
  wider alphabet, now drives every star-chart dot colour and per-class legend entry.
  `core.shared._SP_DISPLAY_LETTERS` = the chip letters **plus** `L T Y W D C N` —
  the classes that are not main-sequence OBAFGKM but are still real and colourable
  (degenerate white dwarfs, brown dwarfs, Wolf-Rayet, carbon). Two sets are required,
  not one: a search chip must send `DA` to `Other`, but a chart must still *paint*
  it — reusing the chip rule for colour would turn all 19,674 white-dwarf /
  brown-dwarf / Wolf-Rayet rows **grey**. Before the fix, `sp[:1].upper()` painted
  `dM6` (Wolf 359) white-dwarf blue and filed it under a bogus "Class D" legend
  entry; `sdM3.0` → `S` and `esdL7` → `E` fell through to grey.
  - Entry points: `core.viz._sp_color` (charts, HR, Night Sky, GCNS panels) and
    `gui.visualizations.plot_helpers._display_class` (legend / label / highlight
    bucketing). **All 17 display sites must use these** — the legend loops,
    `name_cls` (highlight suppression) and `label_groups` (labels) agree only by
    producing the same string, so a partial conversion breaks legend filtering
    silently, with no error and no test failure (`test_cross_site_agreement` pins it).
  - `R` and `S` are **deliberately excluded**: zero catalogue rows, and including
    them made non-spectral labels resolve — `"Red Giant"` (a row label in the
    Honorverse hyper-limit table, fed through the same helper) became carbon class R.
  - Palette additions `Y #A9746E`, `C`/`N` `#D94F2B`. `_SPECTRAL_COLORS` is
    **physically motivated** and deliberately fails the generic categorical-palette
    checks (F `#F8F7FF` ↔ G `#FFF4EA` sit at OKLab ΔE 2.7 — F and G stars really are
    both near-white). Identity is carried by *secondary encoding* — legend labels,
    hover tooltip, click info box — never hue alone. Do not "fix" it by re-stepping
    the hues; that would make the colours lie about the physics.
  - `core.calculators._star_map_color` (route-planning maps + opts 17/20/21) was a
    **second palette** whose G/M/D and unknown-default differed. Part 2 left it in
    place (giving it only the same prefix-aware derivation and additive-only
    `L/T/W/Y/C/N` keys) to avoid repainting route maps mid-fix; the **route-chart
    refactor deleted it on 2026-07-27** (`completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` Phase 3).
    The one palette now lives in `core/shared.py` as `_SPECTRAL_COLORS` + `sp_color`,
    beside the `spectral_leading_class` rule it keys off, and `core.viz` re-exports it
    as `_SPECTRAL_COLORS`/`_sp_color`. **Do not add a local palette** —
    `test_search.py::test_there_is_exactly_one_spectral_palette` pins it.

  Note `spectral_adql` (G3, live NASA TAP) was **deliberately left on `LIKE`** —
  `_query_tap` sends ADQL as a GET parameter and the prefixed form would add ~6 KB
  of query string against an endpoint whose length tolerance is untested, for
  essentially no benefit (NASA `st_spectype` uses modern MK with no `d`-prefixes).
- `spectral_refine: str` — case-insensitive **contains** match on the rest of the
  type: `AND <col> LIKE '%refine%'` (LIKE wildcards in the refine text are escaped
  with `ESCAPE '\'`). So `V` finds the luminosity class wherever it sits, and
  `M5.5Ve` still matches `V`.

`core.shared.spectral_where(column, classes, refine) -> (sql_fragment, params)`
builds the parameterized SQL for the SQLite searches (G1/G2);
`spectral_adql(column, classes, refine) -> str` builds the inline-literal ADQL
clause for the live archive search (G3) — the refine text is sanitized to a safe
character set (quotes stripped) so it cannot break out of the ADQL string literal.

### G1 — `search_star_systems(filters: dict) -> dict`

Filters the local `star_systems` table. No network. Filter keys (all optional):
`spectral_classes` / `spectral_refine`, `ly_min` / `ly_max`, `mag_min` / `mag_max`
(floats, inclusive), `designation_prefix` (matches `star_name` or any `designations`
token — a parameterized `LIKE 'p%'` at the start or after a `", "` separator; since opt 50 now
writes SIMBAD's common name first, a common name is matchable too — but only as the **whole
token including the prefix**, e.g. `"NAME Chara"`. A bare `"Chara"` does **not** match, because
both branches anchor at the string start or immediately after `", "`. See "NAME first" under
opt 50 above).
Default sort `light_years ASC`; capped at `_SEARCH_CAP` (500). Returns
`{"error": "star_systems table is empty — run option 50 first…"}` when the table is
empty. **Phase L4 metallicity filter:** `fe_h_min` / `fe_h_max` are now wired — when
either is set, the query gains `JOIN hypatia_cache hc ON ss.star_name = hc.star_name`
and a `hc.fe_h` range clause (the only JOIN this function ever uses; the base query is
aliased `star_systems ss`). The JOIN is an inner join, so an fe_h filter returns only
stars present in the Hypatia cache — with an empty/unbuilt cache it simply matches
nothing (not an error). See "Phase L4 — Hypatia Abundance Cache & Search" below.

### G2 — `search_hwc(filters: dict) -> dict`

Filters the local `hwc` table. No network. **All `hwc` columns are TEXT** (created
dynamically from the CSV headers), so every numeric predicate is
`CAST(<col> AS REAL)` guarded by `NULLIF(<col>,'') IS NOT NULL` — a blank cell is
excluded, never treated as `0`. Filter keys: `esi_min`; `habitable` /
`habzone_con` / `habzone_opt` (bool → `P_HABITABLE='1'` etc.); `mass_min/max`
(`P_MASS`), `radius_min/max` (`P_RADIUS`), `temp_min/max` (`P_TEMP_EQUIL`);
`spectral_classes` / `spectral_refine` (on `S_TYPE`); `ly_max`
(`CAST(S_DISTANCE AS REAL) * 3.26156`). Default sort `P_ESI DESC` (blank ESI sorts
last); capped at 500. Empty table → `{"error": "… run option 52 …"}`.

### G3 — `search_exoplanets(filters: dict) -> dict`

Live NASA `pscomppars` TAP query. Builds an ADQL `WHERE` from the filters and calls
`_query_tap("pscomppars", where, order_by="pl_orbsmax", top=200, select=<cols>)`.
Filter keys: `pl_bmasse_min/max`, `pl_rade_min/max`, `pl_orbper_min/max`,
`st_teff_min/max` (floats), `sy_dist_max` (**pc** — `sy_dist` is parsecs; the GUI
panel's "Max Distance (LY)" field converts ly→pc as `ly / 3.26156` and displays the
result column back in ly), `discoverymethod` (exact; `"Any"`
ignored), `spectral_classes` / `spectral_refine` (on `st_spectype`). A set
`pl_rade` bound naturally excludes null-radius detections (ADQL comparison
semantics). Capped at `_EXO_SEARCH_CAP` (200). Network failures are classified via
`_network_error_msg(…, "NASA Exoplanet Archive")` into `{"error": str}`.

`_query_tap` gained two backward-compatible kwargs for this: `top` (ADQL
`SELECT TOP N`) and `select` (column list, default `"*"`). Existing callers
(opts 2/4) are unaffected.

## Phase L — Comparison Dashboard (L1–L3)

GUI-only "Comparison" nav category (`gui/panels/comparison.py`) plus one `query.py`
subcommand. L4 (Hypatia cache + abundance search) is **complete** — see the
"Phase L4 — Hypatia Abundance Cache & Search" section below.

### L1 — `compare_stars(names: list) -> dict`

Side-by-side comparison of **2–4 stars** (`StarComparisonPanel`). Reuses
`compute_simbad_lookup`, the NASA `_get_archive_query_params` / `_query_tap`
helpers, `regions.compute_star_system_regions_from_simbad`,
`equations.compute_habitable_zone`, and `compute_hypatia_data` verbatim — no new
query path. Per star: SIMBAD lookup → **pscomppars supplement** (designation
priority HIP → HD → TIC → Gaia EDR3; fills `st_rad`/`st_mass` and `st_teff`/`st_lum`
that SIMBAD lacks) → **photometric fallback** for mass/radius/luminosity when
pscomppars has no row → luminosity (prefers `radius² × (teff/5778)⁴`, else the
archive/regions value) → Conservative HZ inner (`rg`) / outer (`mg`) via
`compute_habitable_zone` → Hypatia data.

- **Photometric fallback** (the key coverage fix): NASA `pscomppars` only carries
  planet-**host** stars, so most stars (e.g. 18 Scorpii, Delta Pavonis) miss it and
  would show N/A for mass/radius/luminosity. When `st_rad`/`st_mass` are still
  unfilled, `compare_stars` calls `compute_star_system_regions_from_simbad(sl)` and
  takes its `stellarMass`/`stellarRadius`/`bcLuminosity` — the same V mag + parallax
  + teff + bolometric-correction derivation as the Star System Regions feature,
  which works for any main-sequence star. Luminosity is then recomputed uniformly
  as `radius² × (teff/5778)⁴`, and the HZ follows. A star whose spectral type isn't
  a parseable O B A F G K M class (e.g. a white dwarf) still falls through to N/A.

- **Per-star failures are isolated**: each star carries its own `"error"` key
  (`None` on success) and missing numerics are `None`; the **only** top-level error
  is the arg-count check (`< 2` non-blank names, or `> 4`).
- **Sol/Sun special-case** (`_sol_compare_entry`): `"Sol"`/`"Sun"` (case-insensitive)
  don't resolve in SIMBAD, so the Sun's textbook reference constants are injected
  directly (G2V, 5778 K, 1 M☉/R☉/L☉, HZ from `compute_habitable_zone`, ly 0,
  app mag −26.74). Because Hypatia's [X/H] is *defined* relative to the Sun under
  Lodders 2009, the synthetic Hypatia block carries every species at `mean = 0.0`
  with `n = 0` — the natural zero-point baseline. `prepare_abundance_comparison`
  treats `n = 0` rows as baseline-only: they fill existing element rows but never
  expand the chart's element union (so a Sun column doesn't bloat it to all 104
  species).
- Returns `{"stars": [ {name, sp_type, teff, luminosity, mass, radius, hz_inner_au,
  hz_outer_au, ly, app_magnitude, hypatia, error}, … ]}` where `hypatia` is the raw
  `compute_hypatia_data` result (or `{"error": …}`).
- **GUI:** transposed `make_table` (properties as rows, stars as columns) + a
  second "Hypatia Catalog" table (log g, Disk, Fe/H, Mg/H, Si/H, O/H, U/V/W) when
  ≥1 star has Hypatia data; per-star error surfaced on the Spectral Type row. A
  background worker runs `compare_stars`; a **"Abundance Profiles"** diagram tab
  (`DiagramToggleMixin`) shows a grouped [X/H] bar chart via
  `core.viz.prepare_abundance_comparison` → `make_abundance_comparison_canvas`.
- **query.py:** `compare-stars --stars N [N …]` (2–4) wraps `compare_stars` verbatim
  — see `docs/integration.md`. (Added after the original L1 build, once the
  `scifiWorldBuilding-Claude` consumer's need for a bundled multi-star comparison
  was confirmed.)

### L2 — ESI Ranking (no new core function)

`EsiRankingPanel` is **presentation-only over the Phase G2 `search_hwc`** — it
calls `search_hwc({"esi_min", "habitable", "habzone_con", "ly_max"})` (already
sorted `P_ESI DESC`, cap 500), prepends a 1-based **Rank** column, and computes
Distance (LY) = `S_DISTANCE (pc) × 3.26156`. Synchronous local-DB read; a
double-clicked row opens `HwcPanel` for that `S_NAME`. No new core code and **no
`esi-ranking` query.py subcommand** — `search-hwc --esi-min …` already covers it.
The panel is a `DiagramToggleMixin` with a **top-N ESI bar chart** Show-Diagrams
tab (`core.viz.prepare_esi_bar_chart` → `make_esi_bar_canvas`; bars colored by the
habitable flag).

### L3 — Stellar Evolution

`compute_stellar_evolution` (in `core/equations.py` — see `docs/equations.md`)
backs `StellarEvolutionPanel` and the `stellar-evolution` `query.py` subcommand.

## Phase L4 — Hypatia Abundance Cache & Search

The Hypatia `/star` and `/composition` endpoints are **per-star**, so cross-star
abundance *search* ("every star with Fe/H < −0.3 and Mg/H > 0") is impossible
against the live API. L4 pulls the whole catalog into a local two-table EAV cache
once, then filters it like the other Search & Filter panels. The pre-L4
verification spike passed (2026-06-14): `hypatiacatalog.com` has no robots.txt /
WAF / published rate limits and explicitly blesses API access, and the bulk
`GET /data` endpoint carries a **star identifier** per point (so the cheap
~112-call import path is viable).

### Storage (`core/db.py`) — EAV, isolated, not auto-seeded

Three tables (declared in `_create_schema` alongside the GCNS tables; empty until
the import runs, like `gcns_stars`):

- **`hypatia_cache`** — one row per star: `star_name` (PK; SIMBAD main_id with
  whitespace collapsed), `hip`/`hd` (NULL — not bulk-available), `teff`, `logg`,
  `vmag`, `bv`, `distance_pc`, `disk` (TEXT code: `0`=thin, `1`=thick),
  `u_vel`/`v_vel`/`w_vel` (NULL — see below), `pm_ra`, `pm_dec`, `fe_h`
  (denormalized [Fe/H] mean — the default sort + dominant filter + G1 JOIN key,
  indexed), `light_years` (= `distance_pc × 3.26156`, precomputed + indexed),
  `fetched_date`.
- **`hypatia_abundance`** — one row per `(star_name, element)`: `element` (API
  casing, e.g. `Fe`, `Mg`, `Ba_II`), `mean` ([X/H], Lodders 2009),
  `std`/`min`/`max`/`n` (NULL — not bulk-available). PK `(star_name, element)`;
  indexed on `(element, mean)`.
- **`hypatia_meta`** (key/value, mirroring `gcns_meta`): `snapshot_date`,
  `source`, `simbad_norm` (`lodders09`), `star_count`, `abundance_count`,
  `fe_h_count`, `axis_errors`.

`get_table_status()` lists **Hypatia Cache**.

### Import — `import_hypatia_cache(progress_callback=None)`

Bulk path via `GET /data/?xaxis1=<axis>` — one call per axis returns
`{star_name: value}` for every star carrying that quantity. Pulls **8 stellar-
property axes** (`teff`, `logg`, `vmag`, `bv`, `dist`→`distance_pc`, `disk`,
`pm_ra`, `pm_dec`) + the **104 element species** from `core/hypatia_elements.py`
(`Fe` also fills the denormalized `fe_h`). Names are whitespace-normalized
(`_norm_hypatia_name`: `"*   1 Aqr"` → `"* 1 Aqr"`, the SIMBAD/`star_systems`
form). Flow mirrors `compute_gcns_ingest` (validate-before-destroy): fetch all →
**Gate 1** (abort before any DB write if the [Fe/H] star count < `_HYPATIA_MIN_STARS`
= 1000) → assemble → **DELETE + bulk INSERT both tables in ONE transaction** →
**Gate 2** (post-commit count) → write `hypatia_meta`. A single element axis
failing is non-fatal (skipped + counted in `errors`). Throttle envelope (Stage
0a): serial, ~0.5 s inter-request delay, `_with_retries` backoff **+ honors
`Retry-After`** on 429/503, descriptive `User-Agent` with contact email. Returns
`{inserted, abundance_rows, fe_h_count, errors, total_candidates, snapshot_date,
source}` or `{"error": str}`.

> **Bulk-path caveat (mean-only):** `/data` carries the catalog-averaged **[X/H]
> mean** per element — the search filter key — but **not** the spread
> (`std`/`min`/`max`/`n`) or the UVW kinematics (the `u`/`v`/`w` `/data` axes
> collide with the U/V/W *element* symbols). Those columns stay NULL; the live
> per-star `compute_hypatia_data` (opt 1 / 3–6 / 8 displays) still serves full
> detail with error bars. Live build (2026-06-14): **14,085 stars / 244,867
> abundance rows**, all with [Fe/H], 0 axis errors.

### Search — `search_hypatia_cache(filters) -> dict`

Reuses the G1/G2 helpers (`_range_clause`, `_SEARCH_CAP`=500, `get_conn`). Filter
keys (all optional): `fe_h_min`/`fe_h_max`, `teff_min`/`teff_max`, `ly_max`
(`light_years`), `disk` (exact), and `element` + `element_min`/`element_max` (an
`EXISTS` subquery on `hypatia_abundance` for that species' [X/H]). Display columns
`mg_h`/`si_h`/`o_h` are pivoted via correlated subqueries (Fe/H is the denormalized
column). Sorted `fe_h DESC` (NULL fe_h last), cap 500, same
`{count, capped, cap, stars[]}` shape as `search_star_systems`. Empty cache →
`{"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}`.

### G1 integration

`search_star_systems` gains `fe_h_min`/`fe_h_max` (see G1 above) — the only JOIN
that function uses, activating only when an fe_h filter is set.

### GUI / `query.py`

- **`ImportHypatiaPanel`** (Utilities nav; `gui/panels/csv_utility.py`) — mirrors
  `ImportGcnsPanel` (`_HypatiaWorker` on a `QThread`, busy progress bar, status
  label, completion summary).
- **`HypatiaSearchPanel`** (Search & Filter nav; `gui/panels/search.py`) — reuses
  `SearchPanelBase` (inline drill-down detail tabs; "Open star in new tab"
  embeds a `SimbadPanel`). Form: Fe/H, Teff, Disk combo, Element combo + [X/H]
  range, Max Distance (LY). No `SpectralClassControl`. The Star Systems Search
  panel's previously-disabled Fe/H field is now live. A **scatter "Plot" tab**
  (X/Y axis dropdowns over `core.viz.HYPATIA_SCATTER_AXES` — Fe/H, Teff, log g,
  distance, V, B–V, Mg/Si/O — `prepare_hypatia_scatter` → `make_scatter_canvas`,
  with a hover tooltip) plots the current result set; re-plotting rebuilds the
  single Plot tab.
- **`query.py search-hypatia`** — local-DB read over `search_hypatia_cache`; same
  `search-*` contract (see `docs/integration.md`).
- **`query.py solar-analogs`** (Phase T1c E2) — a convenience preset over
  `hypatia_cache`: a solar twin/analog tolerance box (Teff 5772 / log g 4.44 /
  [Fe/H] 0) with an opt-in best-effort GCNS Bayesian-distance join. Emits a
  `population` block (source + size + the Hypatia-limit caveat note) in the JSON.
  See `docs/integration.md`.
