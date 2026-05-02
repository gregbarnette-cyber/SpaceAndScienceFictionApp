# Context

The app is a mature Space & Science Fiction CLI/GUI tool that has completed Phases A–F:
- **A–B**: Project skeleton + static/pure-math panels
- **C**: SIMBAD network features + QThread pattern
- **D**: Multi-source features (NASA archives, JPL Horizons, HWC, OEC, CSV utilities)
- **E**: Matplotlib visualizations embedded in panels (star maps, orbital diagrams, HZ rings, solar travel map)
- **F**: SQLite migration — all static tables auto-seeded from CSVs; star systems DB query; import/export utilities

This document brainstorms future phases in order of likely value and implementation effort.

---

## Phase G — Interactive Data Search & Filtering

**New options**: 57 (Star Systems Search), 58 (HWC Planet Search), 59 (NASA Exoplanet Quick Search)
**Existing options touched**: none

The large datasets (252K `star_systems` rows, 5,600 `hwc` rows) are only browsable via exact-name lookup. A filter/search UI unlocks the real power of the data.

### G1: Star Systems Search — opt 57

Filters the local `star_systems` SQLite table (populated by opt 50) by spectral type pattern, distance range, apparent magnitude range, or designation prefix. No network calls.

**`core/databases.py`** — add `search_star_systems(filters: dict) -> list[dict]`:
- Builds a parameterized `SELECT ... FROM star_systems WHERE ...` with only the clauses for non-None filter keys (safe — no string interpolation of user input)
- Supported filters: `spectral_type_like` (SQL LIKE pattern, e.g. `"G%"` or `"K2%"`), `ly_min`/`ly_max` (float, inclusive), `mag_min`/`mag_max` (float, inclusive), `designation_prefix` (matches if any designation starts with the prefix, using `designations LIKE ?`)
- Default sort: `light_years ASC`; returns at most 500 rows to prevent UI freeze
- Returns list of dicts with keys: `star_name`, `designations`, `spectral_type`, `parallax`, `parsecs`, `light_years`, `app_magnitude`, `ra`, `dec`
- Returns `{"error": str}` if the `star_systems` table is empty (directs user to run opt 50)

**Output table columns** (CLI and GUI): Star Name | Designations | Spectral Type | Light Years (4dp) | App. Magnitude (3dp). Count printed above table: `"N stars found."` Footer: `"Showing first 500 results."` if capped.

**CLI** — `search_star_systems_db()` (57):
- Prompts for each filter field one at a time; blank = skip that filter; at least one filter required to prevent returning the entire table
- Clears screen after all inputs collected
- After table: `"Enter row number to open in SIMBAD (or Enter to return):"` — if a valid row number is entered, re-prompts for the "Press Enter" and returns the `main_id` of that row so the caller can chain into `query_star()`

**GUI** — `StarSystemsSearchPanel` (57):
- Filter form: spectral type `QLineEdit` (placeholder `"e.g. G2, K%, M%"`), LY min/max `QLineEdit` pair, magnitude min/max `QLineEdit` pair, designation prefix `QLineEdit`
- All fields optional; "Search" button disabled until at least one field is non-empty
- Results in `make_table()` with interactive column sorting; count label above table
- "Open in SIMBAD" button (hidden until a row is selected): calls `show_panel(SimbadPanel)` and sets the star name input to the selected row's `star_name`, then auto-triggers the search

### G2: HWC Planet Search — opt 58

Filters the local `hwc` SQLite table with planet-level and star-level predicates. Returns a ranked list; row selection drills into the full four-table HWC display for that star system.

**`core/databases.py`** — add `search_hwc(filters: dict) -> list[dict]`:
- Parameterized dynamic WHERE clause on the `hwc` table
- Supported filters: `habitable` (bool → `P_HABITABLE = 1`), `habzone_con` (bool → `P_HABZONE_CON = 1`), `habzone_opt` (bool → `P_HABZONE_OPT = 1`), `esi_min`/`esi_max` (float), `temp_min`/`temp_max` (float on `P_TEMP_EQUIL`), `sp_type_like` (SQL LIKE on `S_TYPE`), `ly_min`/`ly_max` (float on `S_DISTANCE * 3.26156`)
- Default sort: `P_ESI DESC`; cap at 500 rows
- Returns list of dicts with keys: `P_NAME`, `P_ESI`, `P_HABITABLE`, `P_HABZONE_CON`, `P_HABZONE_OPT`, `P_TEMP_EQUIL`, `S_NAME`, `S_NAME_HD`, `S_NAME_HIP`, `S_TYPE`, `S_DISTANCE`

**Output table columns**: Planet (P_NAME) | ESI (4dp) | Habitable? | In Con HZ? | In Opt HZ? | Temp K (0dp) | Star (S_NAME) | Spectral Type | Distance (LY, 4dp). Count above table.

**CLI** — `search_hwc_planets()` (58):
- Prompts: ESI min (blank = 0), Habitable only? (Y/N, default N), Conservative HZ only? (Y/N, default N), Spectral type pattern (blank = any), Max distance LY (blank = any), Temp range min/max K (blank = any)
- Clears screen after inputs
- After table: `"Enter row number for full star details (or Enter to return):"` — calls existing `_query_hwc()` + `_display_hwc_results()` for that system's `S_NAME`

**GUI** — `HwcSearchPanel` (58):
- Filter form: ESI min `QDoubleSpinBox` (0.0–1.0, step 0.05, default 0.0), `QCheckBox` "Habitable only", `QCheckBox` "Conservative HZ only", `QCheckBox` "Optimistic HZ only", spectral type `QLineEdit`, LY max `QLineEdit`, temp min/max `QLineEdit` pair
- Results in sortable `make_table()`
- "View Full Details" button (hidden until row selected): calls `show_panel(HwcPanel)` and pre-fills the HWC star name input with the selected row's `S_NAME`, auto-triggering the HWC lookup

### G3: NASA Exoplanet Quick Search — opt 59

Queries the live NASA Exoplanet Archive `pscomppars` TAP endpoint with user-supplied predicates. Results rendered via existing `_display_exoplanet_results()`.

**`core/databases.py`** — add `search_exoplanets(filters: dict) -> list[dict]`:
- Builds ADQL SELECT with a dynamic WHERE clause; uses existing `_query_tap()` helper (already has `_with_retries` + `_network_error_msg`)
- Supported filters: `pl_bmasse_min`/`max` (planet mass in Earth masses), `pl_orbper_min`/`max` (orbital period in days), `st_spectype_like` (SQL LIKE on `st_spectype`), `discoverymethod` (exact match), `st_teff_min`/`max`, `sy_dist_max` (distance in parsecs)
- Returns list of planet row dicts with the same columns as `_query_exoplanet_archive()` so existing `_display_exoplanet_results()` can render them without changes
- Cap at 200 rows; sorted by `pl_orbsmax ASC`

**CLI** — `search_exoplanets_quick()` (59):
- Prompts for each filter (blank = skip); at least one required
- Clears screen; prints "Querying NASA Exoplanet Archive..." before the network call
- Displays planet rows using `_print_table()`; after table: `"Enter row number for full star details (or Enter to return):"` — re-runs the full SIMBAD + archive lookup for that star's host name

**GUI** — `NasaExoplanetSearchPanel` (59):
- Filter form: planet mass min/max `QLineEdit` pair (in Earth masses), orbital period min/max `QLineEdit` pair (days), spectral type `QLineEdit`, discovery method `QComboBox` (Any / Transit / Radial Velocity / Direct Imaging / Microlensing / Astrometry / Timing), max distance `QLineEdit` (parsecs), teff min/max `QLineEdit` pair
- "Search" fires `run_in_background` with the TAP query; uses existing `_network_error_msg` error classification
- Results in sortable `make_table()`; "View Full Details" button navigates to `NasaPlanetarySystemsPanel` with host star name pre-filled

### Remaining Steps

- **`gui/panels/__init__.py`** — export `StarSystemsSearchPanel`, `HwcSearchPanel`, `NasaExoplanetSearchPanel`
- **`gui/nav.py`** — add "Search & Filter" nav category with three entries
- **`main.py`** — register opts 57–59 in `MENU_OPTIONS`
- **`docs/star-databases.md`** — document all three search functions, supported filter keys, return schemas, and 500/200-row caps

---

## Phase H — Worldbuilding Calculators

**New options**: 42 (Roche Limit), 43 (Tidal Locking), 44 (Hill Sphere), 45 (Binary Orbit Stability), 46 (Atmosphere Retention)
**Existing options touched**: none (pure additions alongside opts 33–41)

New physics tools for authors and worldbuilders. All pure math — no network calls, no CSV reads, no DB access.

### H1: Roche Limit Calculator — opt 42

Computes the rigid-body and fluid Roche limit for a satellite orbiting a primary body (works for planet-moon or star-planet scenarios).

**Physical constants**: `EARTH_MASS_KG = 5.972e24`, `EARTH_RADIUS_KM = 6371`, `AU_PER_KM = 1 / 149597870.7`

**`core/equations.py`** — add `compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None) -> dict`:
- If `primary_radius_earth` not supplied, estimate from mass: `R_km = EARTH_RADIUS_KM × primary_mass_earth^0.55` (approximate rocky-body mass-radius relation)
- Convert primary radius to metres: `R_m = R_km × 1000`
- Estimate primary density from mass and radius: `ρ_primary = (3 × M_primary_kg) / (4π × R_m³)` in g/cm³
- Rigid-body Roche limit: `d_rigid_m = R_m × 2.44 × (ρ_primary / satellite_density_gcc)^(1/3)`
- Fluid Roche limit: `d_fluid_m = R_m × 2.456 × (ρ_primary / satellite_density_gcc)^(1/3)`
- Convert both to km and AU
- Returns `{"primary_mass_earth": float, "primary_radius_km": float, "primary_density_gcc": float, "satellite_density_gcc": float, "rigid_km": float, "rigid_au": float, "fluid_km": float, "fluid_au": float}`

**Output table columns**: Primary Mass (M⊕) | Primary Radius (km) | Primary Density (g/cm³) | Satellite Density (g/cm³) | Rigid Roche Limit (km) | Rigid Roche (AU) | Fluid Roche Limit (km) | Fluid Roche (AU). All 4dp.

**CLI** — `roche_limit_calculator()` (42): prompts primary mass (M⊕, > 0), satellite density (g/cm³, > 0), primary radius (M⊕, optional — blank = estimated). Screen cleared after inputs. Standard table + "Press Enter" pattern.

**GUI** — `RocheLimitPanel`: primary mass `QLineEdit`, satellite density `QLineEdit`, primary radius `QLineEdit` (labeled "optional — estimated from mass if blank"). Pure math — result updates immediately on button click.

### H2: Tidal Locking Timescale Calculator — opt 43

Estimates how long it takes for a satellite's rotation to become tidally locked to its primary, using the MacDonald (1964) torque model.

**Physical constants**: `G = 6.674e-11`, `EARTH_MASS_KG = 5.972e24`, `EARTH_RADIUS_KM = 6371`

**`core/equations.py`** — add `compute_tidal_locking_time(primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa=3e10, tidal_q=100) -> dict`:
- Convert all inputs to SI: mass to kg, SMA to metres, rotation to rad/s (`ω₀ = 2π / (hours × 3600)`)
- Satellite radius estimated: `R_sat_m = EARTH_RADIUS_KM × satellite_mass_earth^0.55 × 1000`
- Moment of inertia: `I = 0.4 × M_sat × R_sat²` (uniform sphere approximation)
- Love number: `k₂ = 1.5 / (1 + 19μ / (2ρgR))` where `μ = rigidity_pa`; simplified to `k₂ ≈ 0.3` for rocky bodies
- Tidal locking timescale: `T = (ω₀ × a⁶ × I × tidal_q) / (3 × G × M_primary² × k₂ × R_sat⁵)` seconds → convert to years and Gyr
- `is_locked`: `True` if `T < 0` (already past locking time given age of solar system) — note this calculator does not receive the system age, so `is_locked` is always `False` unless `T` is computed as ≤ 0 due to extreme parameters
- Returns `{"primary_mass_earth": float, "satellite_mass_earth": float, "sma_km": float, "initial_rotation_hours": float, "rigidity_pa": float, "tidal_q": int, "satellite_radius_km": float, "lock_time_years": float, "lock_time_gyr": float}`

**Output table columns**: Primary Mass (M⊕) | Satellite Mass (M⊕) | SMA (km) | Sat. Radius (km) | Init. Rotation (hr) | Rigidity (Pa) | Tidal Q | Lock Time (yr, scientific) | Lock Time (Gyr, 4dp)

**CLI** — `tidal_locking_calculator()` (43): prompts primary mass, satellite mass, SMA (km), initial rotation (hours). Advanced inputs (rigidity, Q) shown with defaults; blank = use default. Screen cleared after inputs.

**GUI** — `TidalLockingPanel`: four required `QLineEdit` inputs (primary mass, satellite mass, SMA, rotation); collapsible "Advanced Parameters" section with rigidity and Q fields showing defaults. Pure math.

### H3: Hill Sphere Calculator — opt 44

Computes the gravitational sphere of influence of a planet within a star system — the region where the planet's gravity dominates over the star's. Stable satellite orbits exist within ~0.5 × Hill radius.

**`core/equations.py`** — add `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0) -> dict`:
- Convert masses: `M_star_kg = star_mass_solar × 1.989e30`, `M_planet_kg = planet_mass_earth × 5.972e24`
- Convert SMA to metres: `a_m = sma_au × 149597870700`
- Hill radius: `r_H = a_m × (1 − e) × (M_planet_kg / (3 × M_star_kg))^(1/3)` metres
- Convert to km and AU; stable orbit limit = `0.5 × r_H`
- Validation note: for Solar System reference, Earth's Hill sphere ≈ 1,496,000 km (1.5M km) — Moon at 384,400 km is well within it
- Returns `{"star_mass_solar": float, "planet_mass_earth": float, "sma_au": float, "eccentricity": float, "hill_radius_km": float, "hill_radius_au": float, "stable_orbit_limit_km": float, "stable_orbit_limit_au": float}`

**Output table columns**: Star Mass (M☉) | Planet Mass (M⊕) | SMA (AU) | Eccentricity | Hill Radius (km) | Hill Radius (AU) | Stable Orbit Limit (km) | Stable Orbit Limit (AU). All 4dp.

**CLI** — `hill_sphere_calculator()` (44): prompts star mass (M☉), planet mass (M⊕), SMA (AU), eccentricity (default 0). Screen cleared after inputs.

**GUI** — `HillSpherePanel`: three required `QLineEdit` fields (star mass, planet mass, SMA), one optional (eccentricity, placeholder "0 if circular"). Pure math.

### H4: Binary Star Orbit Stability Calculator — opt 45

Determines whether a planet's orbit is dynamically stable in a binary star system using the Holman & Wiegert (1999) empirical fit. Handles both S-type (planet orbits one star) and P-type (circumbinary) configurations.

**Orbit type definitions**:
- **S-type**: planet orbits one star; the other is a distant perturber. Stability requires the planet's SMA to be *less than* the S-type critical SMA
- **P-type**: planet orbits both stars in a wide circumbinary orbit. Stability requires the planet's SMA to be *greater than* the P-type critical SMA

**`core/equations.py`** — add `compute_binary_orbit_stability(mass1_solar, mass2_solar, binary_sma_au, test_sma_au, eccentricity=0) -> dict`:
- `μ = M2 / (M1 + M2)` (mass ratio; always `M2 ≤ M1` by convention — swap if needed)
- S-type critical SMA: `a_c_stype = (0.464 − 0.380μ − 0.631e + 0.586μe + 0.150e² − 0.198μe²) × binary_sma_au`
- P-type critical SMA: `a_c_ptype = (1.60 + 5.10e − 4.12μ − 4.27eμ − 2.22e² − 5.09μ² + 4.61e²μ²) × binary_sma_au`
- S-type stable if `test_sma_au < a_c_stype`; P-type stable if `test_sma_au > a_c_ptype`
- `orbit_type`: `"S-type"` if `test_sma_au < binary_sma_au / 2`, else `"P-type"` (heuristic — planet closer to one star than the binary separation is S-type, farther is circumbinary)
- Returns `{"mass1_solar": float, "mass2_solar": float, "mass_ratio": float, "binary_sma_au": float, "eccentricity": float, "stype_critical_sma_au": float, "ptype_critical_sma_au": float, "test_sma_au": float, "orbit_type": str, "is_stable": bool, "stable_region_description": str}`
- `stable_region_description`: human-readable e.g. `"S-type orbits stable within 0.32 AU of either star; P-type orbits stable beyond 2.1 AU from binary center"`

**Output table columns**: Mass 1 (M☉) | Mass 2 (M☉) | Mass Ratio (μ) | Binary SMA (AU) | Eccentricity | S-Type Critical SMA (AU) | P-Type Critical SMA (AU) | Test SMA (AU) | Orbit Type | Stable?. After table: stable region description printed as a plain line.

**CLI** — `binary_orbit_stability_calculator()` (45): prompts mass1 (M☉), mass2 (M☉), binary SMA (AU), test planet SMA (AU), eccentricity (default 0). Screen cleared after inputs.

**GUI** — `BinaryOrbitPanel`: four required `QLineEdit` (mass1, mass2, binary SMA, test SMA), one optional (eccentricity, default 0). Result includes stability verdict label styled green (stable) or red (unstable) above the table.

### H5: Planetary Atmosphere Retention Calculator — opt 46

Determines which atmospheric gases a planet can retain against Jeans escape, given its mass, radius, and equilibrium temperature.

**Physics**: Jeans escape parameter `λ = v_escape² / v_thermal²` where `v_escape = √(2GM/R)` and `v_thermal = √(2k_BT/m_gas)`. Simplifies to `λ = (G × M_planet × m_gas) / (k_B × T × R_planet)`.

**Physical constants**: `G = 6.674e-11`, `k_B = 1.380649e-23`, `EARTH_MASS_KG = 5.972e24`, `EARTH_RADIUS_M = 6.371e6`

**Gases evaluated** (molecular mass in amu): H₂ (2), He (4), CH₄ (16), H₂O (18), N₂ (28), O₂ (32), CO₂ (44)

**`core/equations.py`** — add `compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k) -> dict`:
- `M_kg = planet_mass_earth × EARTH_MASS_KG`; `R_m = planet_radius_earth × EARTH_RADIUS_M`
- `v_escape_kms = sqrt(2 × G × M_kg / R_m) / 1000` (km/s)
- For each gas: `m_gas_kg = mol_mass_amu × 1.66054e-27`; `λ = (G × M_kg × m_gas_kg) / (k_B × temperature_k × R_m)`; `v_thermal_kms = sqrt(2 × k_B × temperature_k / m_gas_kg) / 1000`
- Status thresholds: `λ > 6` → `"Retained"`; `3 < λ ≤ 6` → `"Escaping slowly"`; `λ ≤ 3` → `"Lost rapidly"`
- Returns `{"planet_mass_earth": float, "planet_radius_earth": float, "temperature_k": float, "v_escape_kms": float, "gases": [{"gas": str, "mol_mass_amu": int, "lambda": float, "v_thermal_kms": float, "status": str}]}`

**Output**: escape velocity line printed above table. Table columns: Gas | Mol. Mass (amu) | Jeans λ (2dp) | Escape Vel (km/s, 2dp) | Thermal Vel (km/s, 2dp) | Status.

**CLI** — `atmosphere_retention_calculator()` (46): prompts planet mass (M⊕), planet radius (M⊕), temperature (K). Screen cleared after inputs. Prints escape velocity, then gas retention table.

**GUI** — `AtmosphereRetentionPanel`: three `QLineEdit` inputs. Results: escape velocity label above `make_table()`. Status cells colored: green = Retained, yellow = Escaping slowly, red = Lost rapidly (using `QTableView` delegate or HTML in a `QTextEdit` fallback).

### Remaining Steps

- **`gui/panels/worldbuilding.py`** — new file containing all five panel classes; all inherit `ResultPanel` directly (no `DiagramToggleMixin` needed — no visualizations)
- **`gui/panels/__init__.py`** — export all five new panel classes
- **`gui/nav.py`** — add "Worldbuilding" nav category with five entries
- **`main.py`** — register opts 42–46 in `MENU_OPTIONS`
- **`docs/equations.md`** — document all five functions with full formula derivations, constant values, and output dict schemas
- **`CLAUDE.md`** — update menu options table to include opts 42–46

---

## Phase I — Multi-System / Route Planning

**New options**: 47 (Multi-Stop Journey), 48 (Nearest Neighbor Chain), 49 (Trade Route Planner, stretch)
**Existing options touched**: opts 17–21 share `compute_lookup_star_for_distance` — no changes needed, just reused; `core/viz.py` and `gui/visualizations/plot_helpers.py` extended for route overlays

### I1: Multi-Stop Journey Calculator — opt 47

Computes cumulative travel time along an ordered list of stops. Uses the same 3D Euclidean distance math and `_format_travel_time()` as opts 20–21.

**Star name resolution** (per leg): first tries a case-insensitive match against `star_name` in the `star_systems` DB for speed; falls back to a live SIMBAD lookup (via existing `compute_lookup_star_for_distance`) if not found. "sun"/"sol" short-circuits to origin `(0, 0, 0)` with no query, same as opts 20–21. If a lookup fails, the error is reported per-star and the user is asked whether to skip that leg or abort.

**Velocity input**: prompt for velocity unit first (L = LY/HR, C = ×c), then the value — mirrors the two-option pattern of opts 20 vs 21. Derives `ly_hr` and `times_c` from whichever unit is entered.

**Output table** (CLI and GUI): Leg # | Origin | Destination | Distance (LY) | LY/HR | ×c | Travel Time | Cumulative Time. Footer lines: Total Distance (LY) and Total Travel Time.

**`core/calculators.py`** — add `compute_multi_stop_journey(star_names, velocity_input, use_times_c) -> dict`
- Returns `{"legs": [{"leg": int, "origin": str, "dest": str, "distance_ly": float, "ly_hr": float, "times_c": float, "hours": float, "cumulative_hours": float, "travel_time": str, "cumulative_time": str}], "total_ly": float, "total_hours": float, "total_time": str, "stars": list}` where `stars` is a star-map-compatible list (name, x, y, z, spectral color) for the visualization layer

**CLI** — `multi_stop_journey()` (47): prompts velocity unit, then star names one per line (blank line to finish, minimum 2). Screen cleared after all inputs resolve successfully. Prints the leg table then the two summary lines.

**GUI** — `MultiStopJourneyPanel`: `QTextEdit` for star names (one per line), velocity unit `QComboBox` (LY/HR / ×c), velocity `QLineEdit`. Run button fires a single `run_in_background` worker that resolves all stars sequentially and computes legs. Results: leg table via `make_table()`. Diagram tabs (3): "Map X–Y", "Map X–Z", "Map 3D" — numbered dashed arrows connect stops in sequence; star dots colored by spectral class; hover shows name + distance from Sol.

### I2: Nearest Neighbor Chain — opt 48

Greedy nearest-neighbor traversal: from a starting star, repeatedly hop to the closest unvisited star within `max_ly`, building a chain of N hops.

**Position data**: loads all rows from the `star_systems` DB table, parses RA (HMS → decimal degrees), DEC (±DMS → decimal degrees), and LY; converts to 3D Cartesian via the same math used by opts 18–19. The starting star is resolved via SIMBAD (`compute_lookup_star_for_distance`) so its exact position is used; if it also appears in the DB, the DB entry is excluded from candidates to avoid a zero-distance self-match.

**Algorithm**: maintain a `visited` set; at each step compute Euclidean distance from the current position to all unvisited stars; pick the minimum within `max_ly`. Stop early (with a note) if no unvisited star is within range.

**Output table** (CLI and GUI): Hop # | Star Name | Designations | Spectral Type | Dist from Prev (LY) | Cumulative Dist (LY) | Dist from Sol (LY). Footer: total hops completed, total distance.

**`core/calculators.py`** — add `compute_nearest_neighbor_chain(start_star, num_hops, max_ly) -> dict`
- Returns `{"chain": [{"hop": int, "star_name": str, "desig": str, "sp_type": str, "dist_from_prev_ly": float, "cumulative_ly": float, "ly_from_sol": float}], "stars": list, "total_ly": float, "stopped_early": bool}`

**CLI** — `nearest_neighbor_chain()` (48): prompts starting star, # hops, max hop distance (LY). Clears screen after inputs and star lookup. Prints chain table; if `stopped_early`, prints a note before "Press Enter".

**GUI** — `NearestNeighborPanel`: star name `QLineEdit`, hop count `QSpinBox` (1–50), max hop distance `QDoubleSpinBox`. Results: chain table. Diagram tabs (3): same "Map X–Y", "Map X–Z", "Map 3D" as opt 18–19, with numbered hop-order labels on the route line and the starting star highlighted.

### I3: Trade Route Network Planner — opt 49 (stretch goal)

Given a set of "important" star systems, find the minimum-cost network (minimum spanning tree) that connects all of them.

**Position resolution**: each star resolved from DB or SIMBAD. Pairwise distance matrix built using 3D Euclidean math. Kruskal's MST: sort all `N×(N−1)/2` edges by distance; greedily add non-cycle-forming edges using union-find until `N−1` edges selected.

**Output table**: From | To | Distance (LY). Footer: N nodes, N−1 edges, Total Network Distance (LY).

**`core/calculators.py`** — add `compute_trade_route_mst(star_names) -> dict`
- Returns `{"nodes": [{"name": str, "x": float, "y": float, "z": float, "sp_type": str}], "edges": [{"from": str, "to": str, "distance_ly": float}], "total_ly": float}`

**CLI** — `trade_route_planner()` (49): prompts star names one per line. Prints MST edge table + summary.

**GUI** — `TradeRoutePlannerPanel`: `QTextEdit` star list + max-jump optional filter. Results: MST edge table. Diagram tab: star map with MST edges as solid lines (distinguished from dashed route lines used by I1/I2); nodes labeled; hover shows star name + degree (number of MST connections).

### Shared Visualization Infrastructure

**`core/viz.py`** — add `prepare_route_map(result) -> dict`
- Accepts multi-stop, nearest-neighbor, or MST result dicts; normalizes to `{"stars": list, "edges": [{"x1","y1","z1","x2","y2","z2","label"}], "edge_style": "dashed"|"solid"}`

**`gui/visualizations/plot_helpers.py`** — extend `make_star_map_canvas` and `make_star_map_3d_canvas` with optional `routes` parameter
- `routes`: list of `{"x1","y1","x2","y2","label","style"}` dicts; drawn as annotated lines over the scatter
- Labels rendered at leg midpoints; style `"dashed"` for ordered routes, `"solid"` for MST edges

### Remaining Steps

- **`gui/panels/__init__.py`** — export `MultiStopJourneyPanel`, `NearestNeighborPanel`, `TradeRoutePlannerPanel`
- **`gui/nav.py`** — add "Route Planning" nav category with three entries
- **`main.py`** — register opts 47–49 in `MENU_OPTIONS`
- **`docs/calculators.md`** — document all three functions, resolution fallback order, and output dict schemas

---

## Phase J — User Preferences & Settings

**New options**: none (new `SettingsPanel` + `FavoritesPanel` added to GUI nav only; CLI is unaffected)
**Existing options touched**: all network-bound panels gain persistent field values (J1); opt 1 gains a bookmark button (J2); all panels outputting AU or temperature gain unit-toggle support (J3); all matplotlib panels gain dark-mode canvas colors (J4)

### J1: Persistent Settings

Saves and restores each panel's last-used input field values across app sessions via a `user_prefs` SQLite table.

**`core/db.py`** — add to schema:
```sql
CREATE TABLE IF NOT EXISTS user_prefs (key TEXT PRIMARY KEY, value TEXT)
```
Add `get_pref(key: str, default=None) -> str | None` and `set_pref(key: str, value: str) -> None` module-level helpers. Both open a connection via the existing `get_db()` pattern and close it when done.

**Key naming convention**: `"{panel_id}_{field_id}"` — e.g. `"simbad_star_name"`, `"system_travel_departure_date"`, `"star_regions_semi_sunlight"`.

**`gui/panels/base.py`** — add `load_pref(key, default="")` and `save_pref(key, value)` convenience wrappers on `ResultPanel` that delegate to `core.db.get_pref` / `core.db.set_pref`.

**Per-panel changes** — call `load_pref` in `build_inputs()` after widget creation (via `setText()` / `setValue()` / `setDate()` as appropriate), and `save_pref` at the start of the successful `_render()` callback:

| Panel | Fields saved |
|---|---|
| `SimbadPanel` (1) | `star_name` |
| `NasaPlanetarySystemsPanel` (3) | `star_name` |
| `NasaHwoExepPanel` (4) | `star_name` |
| `NasaMissionExocatPanel` (5) | `star_name` |
| `HwcPanel` (6) | `star_name` |
| `StarRegionsAutoPanel` (8) | `star_name` |
| `StarRegionsSemiManualPanel` (9) | `star_name`, `sunlight_intensity`, `bond_albedo` |
| `DistanceBetweenStarsPanel` (17) | `star1`, `star2` |
| `StarsWithinDistanceSolPanel` (18) | `max_distance` |
| `StarsWithinDistanceStarPanel` (19) | `star_name`, `max_distance` |
| `TravelTimeStarsLyHrPanel` (20) | `origin`, `destination`, `velocity` |
| `TravelTimeStarsTimesCPanel` (21) | `origin`, `destination`, `velocity` |
| `SystemTravelSolarPanel` (22) | `origin`, `destination`, `accel_g`, `v_cap_pct`, `departure_date` |
| `SystemTravelThrustPanel` (23) | `origin`, `destination`, `accel_g`, `burn_value`, `burn_unit`, `v_cap_pct`, `departure_date` |

### J2: Saved Favorites

Lets users bookmark stars from SIMBAD results and reload them instantly from a dedicated nav panel.

**`core/db.py`** — add to schema:
```sql
CREATE TABLE IF NOT EXISTS favorites (
    star_name TEXT PRIMARY KEY,
    designations TEXT,
    spectral_type TEXT,
    ly REAL,
    ra TEXT,
    dec TEXT,
    added_date TEXT
)
```
Add `add_favorite(row_dict)`, `remove_favorite(star_name)`, `list_favorites() -> list[dict]` helpers. `add_favorite` uses `INSERT OR REPLACE` so re-bookmarking the same star is a no-op.

**`gui/panels/simbad.py`** (opt 1):
- Add "Bookmark Star" `QPushButton` to the results area (hidden initially; revealed after a successful lookup alongside the SIMBAD results)
- On click: calls `core.db.add_favorite({"star_name": main_id, "designations": desig_str, "spectral_type": sp_type, "ly": ly, "ra": ra, "dec": dec, "added_date": today})`; button text temporarily changes to "Bookmarked ✓" for 2 seconds then reverts

**`gui/panels/favorites.py`** (new file):
- `FavoritesPanel`: no option number; GUI-only nav entry
- On show: calls `list_favorites()` and renders results in `make_table()` with columns: Star Name | Designations | Spectral Type | Distance (LY, 4dp) | RA | DEC | Date Added
- Per-row "Load in SIMBAD" button: calls `show_panel(SimbadPanel)`, sets `star_name_input.setText(row["star_name"])`, calls `run_btn.click()` to immediately trigger the lookup
- Per-row "Remove" button: calls `remove_favorite(star_name)`, refreshes table
- "Refresh" button at top: re-runs `list_favorites()` and re-renders (handles stars added in the current session from the SIMBAD panel)

**`gui/nav.py`** — add "Favorites" entry near the top of nav (above "Star Databases").

### J3: Unit System Toggle

Allows users to switch the primary display unit for distance and temperature across all result panels.

**`core/shared.py`** — add two formatting helpers:

`format_au(au: float, unit: str | None = None) -> str`:
- If `unit` is `None`, reads `get_pref("distance_unit", "AU")`
- `"AU"` (default): `f"{au:.4f} AU"` — preserves the existing format exactly
- `"LM"`: `f"{au * 8.3167:.4f} LM"`
- `"km"`: `f"{au * 149597870.7:.0f} km"`
- Note: the existing parenthetical secondary `(X.XXX LM)` appended to AU values in many display helpers is removed when unit ≠ AU; the unit toggle replaces the primary, not adds a secondary

`format_temp(k: float, unit: str | None = None) -> str`:
- If `unit` is `None`, reads `get_pref("temp_unit", "K")`
- `"K"` (default): `f"{k:.0f} K"`
- `"C"`: `f"{k - 273.15:.1f} °C"`
- `"F"`: `f"{(k - 273.15) * 9/5 + 32:.1f} °F"`

**Files to update** — replace inline AU/temperature f-strings with calls to `format_au()` / `format_temp()`:
- `core/databases.py` — all `f"{val:.Xf} AU"` and `f"{val:.0f} K"` occurrences in `_display_habitable_zone()`, `_display_hwo_exep_results()`, `_display_mission_exocat_results()`, `_display_oec_results()`
- `core/regions.py` — all AU outputs in `_display_solar_system_regions()`, `_display_alternate_hz_regions()`, `_display_calculated_hz()`, `_display_earth_equivalent_orbit()`
- `core/science.py` — moon AU columns in `solar_system_data_tables()`
- `core/equations.py` — AU outputs in `habitable_zone_calculator()`, `habitable_zone_calculator_sma()`

**CLI is unaffected** — the CLI always uses the existing hardcoded format. Unit toggle is GUI-only.

**`gui/panels/settings.py`** (new file) — `SettingsPanel`:
- Distance unit `QComboBox`: AU / Light Minutes / Kilometers; saves to `"distance_unit"` pref key (`"AU"` / `"LM"` / `"km"`)
- Temperature unit `QComboBox`: Kelvin / Celsius / Fahrenheit; saves to `"temp_unit"` pref key (`"K"` / `"C"` / `"F"`)
- Changes take effect on the *next* panel render (no live re-render of already-displayed results)

**`gui/nav.py`** — add "Settings" entry (below "Favorites" at the top of nav).

### J4: Dark Mode

Switches the Qt widget palette and all matplotlib canvas backgrounds to a dark color scheme.

**`gui/app.py`** — add `apply_theme(dark: bool)`:
- Light palette: the existing default `QApplication` palette (no change needed — just don't call `setPalette`)
- Dark `QPalette` colors:
  - `Window` / `Base`: `#2b2b2b` / `#1e1e1e`
  - `WindowText` / `Text` / `ButtonText`: `#dddddd`
  - `Button` / `AlternateBase`: `#3c3f41` / `#2a2a2a`
  - `Highlight` / `HighlightedText`: `#4a90d9` / `#ffffff`
  - `ToolTipBase` / `ToolTipText`: `#2b2b2b` / `#dddddd`
- Called on startup: `apply_theme(get_pref("dark_mode", "0") == "1")`
- Called on toggle: `apply_theme(checked)` + `set_pref("dark_mode", "1" if checked else "0")`

**`gui/panels/settings.py`** — add "Dark Mode" `QCheckBox`; `stateChanged` signal calls `apply_theme()` + `set_pref`. Checkbox restored on panel load via `load_pref`.

**`gui/visualizations/plot_helpers.py`** — define two color scheme dicts:
```python
_LIGHT = {"fig": "#f5f5f5", "ax": "#f5f5f5", "text": "#333333", "grid": "#cccccc", "tick": "#555555"}
_DARK  = {"fig": "#2b2b2b", "ax": "#2b2b2b", "text": "#dddddd", "grid": "#444444", "tick": "#aaaaaa"}
```
All canvas helpers call `_colors = _DARK if get_pref("dark_mode") == "1" else _LIGHT` at the top and use `_colors["fig"]` etc. throughout. Existing hardcoded `#f5f5f5` / `#333333` / `#cccccc` references replaced with dict lookups.

**Already-rendered canvases**: `apply_theme()` also iterates `QApplication.instance().allWidgets()`, finds any `FigureCanvasQTAgg` instances, calls `canvas.figure.patch.set_facecolor(_colors["fig"])` and `canvas.draw_idle()` on each so open diagrams update immediately on toggle.

**Opts with matplotlib diagrams** that gain dark-mode support: 3–6, 8–10, 18–19, 22–23, and all future Phase I/L diagram panels.

### Remaining Steps

- **`gui/panels/__init__.py`** — export `FavoritesPanel`, `SettingsPanel`
- **`gui/nav.py`** — add "Favorites" and "Settings" entries; place above "Star Databases" in nav order
- **`docs/gui-architecture.md`** — document `user_prefs` / `favorites` table schemas, `get_pref`/`set_pref` API, `FavoritesPanel`, `SettingsPanel`, `apply_theme`, `format_au`/`format_temp`, and the per-panel pref key naming convention

---

## Phase K — Honorverse Expansion

**New options**: ~49 (Hyper Translation Time), ~50 (Impeller Wedge Geometry), ~51 (Missile Intercept)
**Existing options touched**: opt 15 — mass-band acceleration table extracted into `core/science.py` and reused by K2; opt 16 — 24-band speed table extracted into `core/science.py` and reused by K1. Both opts 15 and 16 are then refactored to call the new core functions rather than using inline data.

### K1: Hyper Translation Time Calculator — opt ~49

Given a distance in light years and ship type, shows travel time across all 24 Honorverse hyper bands.

**Data source**: the 24-band expanded speed table currently hardcoded in `main.py` `honorverse_effective_speed()` (opt 16). This table must first be extracted to a module-level constant in `core/science.py` — a list of dicts, one per band, with keys `band`, `warship_xc`, `merchantship_xc`. Opt 16 is then refactored to call `core.science.get_honorverse_bands()` instead of using inline data (no behavior change).

**`core/science.py`** — add `_HONORVERSE_BANDS` module-level constant (24 entries, Alpha through Omega) and `compute_hyper_translation_time(distance_ly, ship_type) -> list[dict]`:
- `ship_type`: `"warship"` or `"merchantship"` (case-insensitive)
- For each band: `speed_ly_hr = speed_xc / 8765.8128`; `travel_hours = distance_ly / speed_ly_hr`; formats via existing `_format_travel_time()`
- Merchantship bands marked "Currently Unattainable" in opt 16 (Iota+) are included in output with `travel_time = "N/A"` and `travel_hours = None`
- Returns list of `{"band": str, "speed_xc": float, "speed_ly_hr": float, "travel_hours": float | None, "travel_time": str}`

**CLI** — `honorverse_hyper_translation_time()` (~49): prompts distance (LY, > 0), then ship type (W/M, default W). Clears screen after inputs. Output table: Band | Effective Speed (×c) | LY/HR | Travel Time. N/A rows shown with dashes.

**GUI** — `HonorverseHyperTimePanel`: distance `QLineEdit` + ship type `QComboBox` (Warship / Merchantship). Pure math, no background thread needed. Results via `make_table()`. N/A rows rendered with gray text.

### K2: Impeller Wedge Geometry Calculator — opt ~50

Given ship mass and wedge power percentage, computes effective acceleration and maximum velocities.

**Data source**: the mass-band acceleration table currently hardcoded in `main.py` `honorverse_acceleration_by_mass()` (opt 15). Extract to `_HONORVERSE_ACCEL_BANDS` constant in `core/science.py` — list of dicts with keys `mass_range_label`, `warship_normal_g`, `merchantship_normal_g`, `warship_hyper_g`, `merchantship_hyper_g`. Opt 15 refactored to call `core.science.get_honorverse_accel_bands()` (no behavior change).

**`core/science.py`** — add `compute_impeller_wedge(ship_mass_tons, ship_type, wedge_power_pct) -> dict`:
- Finds the matching mass band by comparing `ship_mass_tons` to each band's range boundaries
- `base_accel_g` = normal-space G for the given ship type from the matched band
- `effective_accel_g = base_accel_g × (wedge_power_pct / 100)`
- Max normal-space velocity: Honorverse canon caps at ~0.8c for warships at full power; scale by `wedge_power_pct / 100` → `max_vel_normal_xc = 0.8 × (wedge_power_pct / 100)` (warship) or `0.6 × (wedge_power_pct / 100)` (merchantship)
- Max hyper-space velocity mirrors the normal-space cap (hyper bands multiply this via the translation factor applied at entry, not by the wedge directly)
- Time to reach max velocity from rest: `t = (max_vel_xc × C_MS) / (effective_accel_g × G_MS2)` formatted as travel time
- Returns `{"mass_band": str, "ship_type": str, "wedge_power_pct": float, "base_accel_g": float, "effective_accel_g": float, "max_vel_normal_xc": float, "max_vel_hyper_xc": float, "time_to_max_vel": str}`

**CLI** — `honorverse_impeller_wedge()` (~50): prompts ship mass (tons), ship type (W/M), wedge power % (1–100, default 100). Output table: Mass Band | Ship Type | Wedge Power | Base Accel (G) | Effective Accel (G) | Max Vel Normal (×c) | Max Vel Hyper (×c) | Time to Max Vel.

**GUI** — `HonorverseImpellerPanel`: mass `QLineEdit`, ship type `QComboBox`, wedge power `QSlider` (1–100) with live `QLabel` readout. Pure math — results update immediately on slider move.

### K3: Missile Intercept Calculator — opt ~51

Determines whether a missile fired from a moving launcher can intercept a moving target at a given range, using Honorverse-appropriate physics (all velocities as fractions of c; non-relativistic approximation valid at these scales).

**Inputs**: launcher velocity (×c), missile acceleration (G), missile total delta-v budget (×c), target velocity (×c, positive = same direction as missile, negative = head-on), initial range (LM).

**Physics** (1D head-on simplification):
- All velocities converted to m/s using `C_MS = 299,792,458`; distances via `M_PER_LM = C_MS × 60`
- Missile starts at launcher velocity; burns at `missile_accel_g × G_MS2` until delta-v budget exhausted
- `t_burn = (delta_v_ms) / accel_ms2`; `v_burnout = v_launcher + delta_v_ms`
- Distance covered during burn: `d_burn = v_launcher × t_burn + 0.5 × accel × t_burn²`
- Closing velocity after burnout: `v_close = v_burnout − v_target`
- If `v_close ≤ 0`: missile cannot close → intercept = False
- Remaining range after burn: `range_remaining = range_m − d_burn + v_target × t_burn` (target also moves during burn)
- If `range_remaining ≤ 0`: intercept during burn phase → `t_impact = t_burn × (range_m / d_burn)` (linear approx)
- Else: coast phase time = `range_remaining / v_close`; total `t_impact = t_burn + coast_time`
- Builds on existing constants `G_MS2`, `C_MS`, `M_PER_LM` from `core/calculators.py`

**`core/calculators.py`** — add `compute_missile_intercept(launcher_vel_xc, missile_accel_g, missile_delta_v_xc, target_vel_xc, range_lm) -> dict`:
- Returns `{"intercepts": bool, "intercept_phase": "burn"|"coast"|None, "time_to_impact_s": float|None, "time_to_impact_str": str|None, "v_burnout_xc": float, "v_close_xc": float, "range_at_burnout_lm": float, "burn_duration_s": float}`

**CLI** — `honorverse_missile_intercept()` (~51): prompts all five inputs; clears screen; output has two sections:
- **Intercept verdict** line: "INTERCEPT" or "NO INTERCEPT" with reason
- **Missile Profile table**: Launcher Vel (×c) | Missile Accel (G) | Delta-V Budget (×c) | Burnout Vel (×c) | Burn Duration | Closing Vel (×c) | Range at Burnout (LM) | Time to Impact

**GUI** — `HonorverseMissilePanel`: five `QLineEdit` inputs. Pure math — no background thread. Results: verdict label (green = intercept, red = no intercept) + profile table via `make_table()`.

### Remaining Steps

- **`gui/panels/honorverse.py`** — add `HonorverseHyperTimePanel`, `HonorverseImpellerPanel`, `HonorverseMissilePanel` alongside existing panels
- **`gui/panels/__init__.py`** — export three new panel classes
- **`gui/nav.py`** — extend "Science Fiction" category with three new entries
- **`main.py`** — register new opts in `MENU_OPTIONS`; refactor opts 15 and 16 to call new core functions
- **`docs/science-and-scifi.md`** — document all three new functions, `_HONORVERSE_BANDS`, `_HONORVERSE_ACCEL_BANDS`, and the refactoring of opts 15–16

---

## Phase L — Exoplanet Comparison Dashboard

**New options**: ~52 (Star Comparison), ~53 (ESI Ranking), ~54 (Stellar Evolution Timeline)
**Existing options touched**: opt 1 SIMBAD lookup logic reused by L1; opt 6 `HwcPanel` drill-down target for L2; `core/viz.py` and `gui/visualizations/plot_helpers.py` extended for the evolution diagram in L3

### L1: Side-by-Side Star Comparison — opt ~52

Accepts 2–4 star names, runs a SIMBAD lookup for each, and renders a single transposed comparison table where rows are properties and columns are stars.

**Data resolution per star**:
1. SIMBAD lookup (reuses existing pattern from `core/databases.py`) for: `sp_type`, `teff` (from `mesfe_h.teff`), `plx_value` (→ LY), `V` (apparent magnitude), `ra`, `dec`
2. If `st_rad` or `st_teff` missing from SIMBAD, attempt a supplemental NASA `pscomppars` TAP query using the best available designation (HIP → HD → TIC → Gaia EDR3) to fill `st_teff`, `st_rad`, `st_mass`, `st_lum`
3. HZ inner/outer computed via the existing Kopparapu coefficient logic (`_kopparapu_seff`) using the best available luminosity and teff

**`core/databases.py`** — add `compare_stars(names: list[str]) -> dict`:
- Runs up to 4 lookups; per-star errors are stored in the result without aborting the comparison
- HZ bounds: Conservative Inner (Runaway Greenhouse) and Conservative Outer (Maximum Greenhouse) only — same two used by the single-star HZ tables
- Returns `{"stars": [{"name": str, "sp_type": str, "teff": int|None, "luminosity": float|None, "mass": float|None, "radius": float|None, "hz_inner_au": float|None, "hz_outer_au": float|None, "ly": float|None, "app_magnitude": float|None, "error": str|None}]}`

**Comparison table rows** (property labels): Spectral Type | Temp (K) | Luminosity (Lsun) | Mass (Msun) | Radius (Rsun) | HZ Inner (AU) | HZ Outer (AU) | Distance (LY) | Apparent Magnitude. Each column = one star; missing values shown as "N/A".

**CLI** — `star_comparison()` (~52): prompts star names one per line (blank to finish; 2 minimum, 4 maximum). Screen cleared after all lookups succeed. Renders transposed table using `_print_table()` with property names as the left-most column and one star column per star.

**GUI** — `StarComparisonPanel`: 2–4 `QLineEdit` fields (star 1 always visible; "Add Star" button reveals stars 3 and 4 up to maximum 4). Single "Compare" button fires `run_in_background` worker. Results rendered as a transposed `make_table()` — stars as columns, properties as rows. Cells containing errors shown with red text. Parallel SIMBAD lookups: fire all 4 workers simultaneously; block until all complete before rendering.

### L2: Exoplanet ESI Ranking — opt ~53

Queries the local HWC SQLite table for all planets meeting a minimum ESI threshold, with optional additional filters, and displays a ranked list. Row selection drills into the full HWC display for that star system.

**ESI context**: Earth Similarity Index (0–1.0); Earth = 1.0. Values > 0.8 are considered "Earth-like". The `P_ESI` column is already present in the `hwc` table.

**`core/databases.py`** — add `rank_hwc_by_esi(esi_min=0.8, habitable_only=False, con_hz_only=False, ly_max=None) -> list[dict]`:
- Builds dynamic WHERE clause: `P_ESI >= ?` always; `P_HABITABLE = 1` if `habitable_only`; `P_HABZONE_CON = 1` if `con_hz_only`; `S_DISTANCE * 3.26156 <= ?` if `ly_max` supplied
- Returns list of dicts: `P_NAME`, `P_ESI`, `P_HABITABLE`, `P_HABZONE_CON`, `P_HABZONE_OPT`, `P_TEMP_EQUIL`, `S_NAME`, `S_NAME_HD`, `S_NAME_HIP`, `S_TYPE`, `S_DISTANCE` (parsecs)
- Sorted by `P_ESI DESC`

**Output table columns**: Rank | Planet (P_NAME) | ESI (4dp) | Habitable? | In Con HZ? | In Opt HZ? | Temp K (0dp) | Star (S_NAME) | Spectral Type | Distance (LY, 4dp)

**CLI** — `esi_ranking()` (~53): prompts ESI threshold (default 0.8), habitable-only filter (Y/N, default N), conservative-HZ-only filter (Y/N, default N), max distance LY (blank = no limit). Clears screen. Prints count + ranked table. Prompt: "Enter rank number for full star details (or Enter to return):" — entering a valid rank number calls the existing HWC display logic for that star.

**GUI** — `EsiRankingPanel`: `QDoubleSpinBox` for ESI (0.0–1.0, default 0.8, step 0.05) + `QCheckBox` for "Habitable only" + `QCheckBox` for "Conservative HZ only" + optional max LY `QLineEdit`. Results in sortable `make_table()`. Row double-click fires `show_panel(HwcPanel)` with `S_NAME` pre-filled in the HWC search field.

### L3: Stellar Evolution Timeline — opt ~54

Given a star's mass (and optionally its current age), computes the approximate duration of each evolutionary stage and visualizes the star's position on its timeline.

**Stage model** (main sequence and evolved stars; valid for 0.1 M☉ – 20 M☉):

| Stage | Duration formula | Notes |
|---|---|---|
| Pre-Main Sequence | `~0.01 × T_ms` | T Tauri / Hayashi track |
| Main Sequence | `T_ms = 10^10 × (1/mass)^2.5 yr` | ZAMS to TAMS |
| Subgiant Branch | `0.15 × T_ms` | Core H exhausted; shell burning begins |
| Red Giant Branch | `0.10 × T_ms` | Envelope expands |
| Horizontal Branch | `0.10 × T_ms` | Core He burning |
| Asymptotic Giant Branch | `0.02 × T_ms` | Double-shell burning |

Special cases:
- `mass < 0.8 M☉`: MS lifetime exceeds age of universe; shown as "> 13.8 Gyr"; no post-MS stages reachable yet
- `mass > 8 M☉`: AGB replaced by "Supergiant → Supernova"; total lifetime ~few Myr; note added

**`core/equations.py`** — add `compute_stellar_evolution(mass_solar, current_age_gyr=None) -> dict`:
- Returns `{"mass_solar": float, "stages": [{"name": str, "start_gyr": float, "end_gyr": float, "duration_gyr": float, "color": str}], "total_gyr": float, "ms_end_gyr": float, "current_age_gyr": float|None, "current_stage": str|None}`
- `current_stage` = name of the stage containing `current_age_gyr`, or `"Beyond AGB"` if past all stages
- Stage colors for diagram: Pre-MS = `#aaaaaa`, Main Sequence = `#ffe066`, Subgiant = `#ffaa33`, RGB = `#ff6600`, HB = `#ff99cc`, AGB = `#cc3300`

**Output table columns** (CLI and GUI): Stage | Start (Gyr) | End (Gyr) | Duration (Gyr). Current stage row prefixed with "▶" marker in CLI; bolded in GUI. Footer: total lifetime, current stage if age supplied.

**`core/viz.py`** — add `prepare_evolution_diagram(result) -> dict`:
- Normalizes stages to `{"stages": list, "current_age_gyr": float|None, "x_max_gyr": float}`
- `x_max_gyr` = `max(total_gyr, current_age_gyr or 0) × 1.1` for axis scaling

**`gui/visualizations/plot_helpers.py`** — add `make_evolution_canvas(parent, data)`:
- Horizontal stacked bar chart; one bar per stage, colored by stage color
- x-axis: time in Gyr; y-axis: single row labeled with the star mass
- Vertical dashed line at `current_age_gyr` labeled "Current Age: X.XX Gyr"
- Stage name labels centered within each bar segment (omitted if segment too narrow)
- Same light theme (`facecolor="#f5f5f5"`)

**CLI** — `stellar_evolution_timeline()` (~54): prompts mass (M☉, > 0) and optional current age (Gyr, blank to skip). Output: stage table with current-stage marker. No network calls.

**GUI** — `StellarEvolutionPanel`: mass `QDoubleSpinBox` + optional age `QDoubleSpinBox` (enabled via "Enter current age" checkbox). Pure math — no background thread. Results: stage table + "Evolution Diagram" viz tab via `DiagramToggleMixin`.

### Remaining Steps

- **`gui/panels/comparison.py`** — new file containing `StarComparisonPanel`, `EsiRankingPanel`, `StellarEvolutionPanel`
- **`gui/panels/__init__.py`** — export all three panel classes
- **`gui/nav.py`** — add "Comparison" nav category with three entries
- **`main.py`** — register new opts in `MENU_OPTIONS`
- **`docs/star-databases.md`** — document `compare_stars`, `rank_hwc_by_esi` with filter keys and return schemas
- **`docs/equations.md`** — document `compute_stellar_evolution` with stage duration formulas and special-case mass ranges

---

## Implementation Priority Recommendation

| Phase | Effort | Value | Recommendation |
|---|---|---|---|
| G — Data Filtering | Medium | High | **Do first** — unlocks the large datasets |
| H — Worldbuilding Calcs | Medium | High | **Do second** — pure math, no network, clean additions |
| I — Route Planning | Medium | Medium | Good sci-fi worldbuilding value |
| J — User Preferences | Medium | Medium | Quality-of-life; grows more valuable as feature count grows |
| K — Honorverse Expansion | Low | Medium | Narrow audience but fast to implement |
| L — Comparison Dashboard | Medium | Medium | Depends on G for data access |
