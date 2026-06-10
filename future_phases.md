# Context

The app is a mature Space & Science Fiction CLI/GUI tool that has completed Phases A–F plus the following post-F additions:
- **A–B**: Project skeleton + static/pure-math panels
- **C**: SIMBAD network features + QThread pattern
- **D**: Multi-source features (NASA archives, JPL Horizons, HWC, OEC, CSV utilities)
- **E**: Matplotlib visualizations embedded in panels (star maps, orbital diagrams, HZ rings, solar travel map)
- **F**: SQLite migration — all static tables auto-seeded from CSVs; star systems DB query; import/export utilities
- **Hypatia Catalog integration** (post-F): `compute_hypatia_data(simbad_result)` in `core/databases.py` fetches stellar properties, kinematics, and the full **104-species** Lodders 2009 elemental abundance set (including ionized species; defined in `core/hypatia_elements.py`) from `https://hypatiacatalog.com/hypatia/api/v2`. The 104 species are requested in chunks of 30 (the server caps the GET request line at ~4094 bytes). Integrated into opts 1, 3, 4, 5, 6, and 8 — results shown in **Hypatia** data tabs (abundances grouped by nucleosynthetic family) and **Abundance Profile** viz tabs (category-colored horizontal bar chart via `make_abundance_canvas()`). Also exposed as the `hypatia-data` subcommand in `query.py`.
- **NASA Planetary Systems Map** (post-F): `NasaPlanetarySystemsMapPanel` in `gui/panels/nasa_exoplanet.py` — GUI-only variant of opt 3 that adds a **Map Date** `QDateEdit` (defaults to today) and a **System Map** viz tab. The map is a top-down 2D ecliptic-view diagram showing the host star at the origin and each planet at its date-resolved heliocentric position, computed by solving Kepler's equation using `pl_orbtper` (JD epoch of periastron) or derived from `pl_tranmid`. Clicking a planet opens a non-modal info dialog populated from the already-fetched pscomppars row. Backed by `core.viz.prepare_exoplanet_system_diagram(planets, date_iso)` and `gui/visualizations/plot_helpers.py::make_exoplanet_system_canvas()`.

This document brainstorms future phases in order of likely value and implementation effort.

> **Scope — GUI-only.** New feature work targets the PySide6 GUI only. The CLI (`main.py` / `MENU_OPTIONS`) is **frozen at opts 1–58** and is not extended by any phase below. Every new feature is a GUI nav entry backed by a panel class (the precedent set by `DbStatusPanel` and `NasaPlanetarySystemsMapPanel`, which carry no option number), so there are **no menu numbers to assign and nothing to renumber**. The shared `core/` functions each phase specifies are still built — the GUI and `query.py` consume them; only the CLI presentation layer is dropped. Phase M is already written in this GUI-only form; treat it as the template. **Exception:** Phase N is integration-surface-only — it adds `query.py` subcommands over existing `core/` functions and touches neither the GUI nor the CLI menu.

---

## Phase G — Interactive Data Search & Filtering

**New panels (GUI-only)**: `StarSystemsSearchPanel`, `HwcSearchPanel`, `NasaExoplanetSearchPanel`
**Existing options touched**: none

The large datasets (252K `star_systems` rows, 5,600 `hwc` rows) are only browsable via exact-name lookup. A filter/search UI unlocks the real power of the data.

> **Design locked via interactive mockup** (`mockups/phase-g.html`, reviewed & approved). The two cross-panel conventions below were settled there.

#### Shared convention — spectral-class control

All three panels filter spectral type with the **same friendly control** (not a raw SQL `LIKE` box): a row of **class chips** (`O B A F G K M` + `Other`) plus a small **subtype/luminosity refine** `QLineEdit`.
- **Chips** (multi-select; empty = any) select the leading class letter. `Other` matches anything whose leading type is not `OBAFGKM` (white dwarfs / degenerate `D…` types — consistent with the `_SP_PATTERN` leading-letter logic in `docs/star-system-regions.md`).
- **Refine box** matches the rest of the type as a case-insensitive substring (e.g. `2V`, `5.5`, `V`, `IV`). **Decision: contains-match**, not a `{class}{text}` prefix anchor — so `V` finds the luminosity class wherever it sits and `M5.5Ve` still matches `V`.
- **Core filter keys** (replacing the old `*_like` keys): `spectral_classes: list[str]` → OR of parameterized `LIKE 'X%'` per selected letter (`Other` → `NOT (… OBAFGKM …)`); `spectral_refine: str` → `AND <col> LIKE '%refine%'`. Applies to `spectral_type` (G1), `S_TYPE` (G2), `st_spectype` (G3).

#### Shared convention — drill-down opens inline tabs

Row selection does **not** navigate away via `show_panel()`. Each search panel hosts an **inner `QTabWidget`**: a persistent **"Search Results"** tab plus **closable detail tabs** added on demand, so the user can open **multiple stars/planets at once and switch between them** without losing the result list. Opening an already-open item re-focuses its tab. Each detail tab renders the same view the standalone panel would (reuse `SimbadPanel` / `HwcPanel` / `NasaPlanetarySystemsPanel` rendering inside the tab, or factor a shared detail widget). This is a new pattern vs. the rest of the GUI (which shows one panel at a time) — call it out in `docs/gui-architecture.md`.

### G1: Star Systems Search

Filters the local `star_systems` SQLite table (populated by opt 50) by spectral class, distance range, apparent magnitude range, or designation prefix. No network calls.

**`core/databases.py`** — add `search_star_systems(filters: dict) -> list[dict]`:
- Builds a parameterized `SELECT ... FROM star_systems WHERE ...` with only the clauses for non-None filter keys (safe — no string interpolation of user input)
- Supported filters: `spectral_classes`/`spectral_refine` (see shared convention above), `ly_min`/`ly_max` (float, inclusive), `mag_min`/`mag_max` (float, inclusive), `designation_prefix` (matches if any designation starts with the prefix, using `designations LIKE ?`)
- Default sort: `light_years ASC`; returns at most 500 rows to prevent UI freeze
- Returns list of dicts with keys: `star_name`, `designations`, `spectral_type`, `parallax`, `parsecs`, `light_years`, `app_magnitude`, `ra`, `dec`
- Returns `{"error": str}` if the `star_systems` table is empty (directs user to run opt 50)

**Output table columns**: Star Name | Designations | Spectral Type | Light Years (4dp) | App. Magnitude (3dp). Count printed above table: `"N stars found."` Footer: `"Showing first 500 results."` if capped.

**GUI** — `StarSystemsSearchPanel`:
- Filter form: spectral-class chips + refine box, LY min/max `QLineEdit` pair, magnitude min/max `QLineEdit` pair, designation prefix `QLineEdit`
- All fields optional; "Search" button disabled until at least one filter is set (a selected chip or non-empty refine counts)
- Results in `make_table()` with interactive column sorting; count label above table
- "Open star in new tab" (hidden until a row is selected): adds an inline detail tab rendering the SIMBAD view for the selected `star_name` (Hypatia data fetched as part of that lookup) — per the inline-tab convention above

**Stretch goal (requires Phase L4 Hypatia cache)**: add a `fe_h_min`/`fe_h_max` filter pair to `search_star_systems()` using a JOIN against the `hypatia_cache` table. Only applicable once L4 is implemented; include as a commented-out parameter stub in `search_star_systems()` from the start so L4 can activate it without a signature change. (Shown as a disabled "Fe/H" field with an `L4` badge in the mockup.)

### G2: HWC Planet Search

Filters the local `hwc` SQLite table with planet-level and star-level predicates. Returns a ranked list; row selection opens the full four-table HWC display for that star system in an inline tab.

**`core/databases.py`** — add `search_hwc(filters: dict) -> list[dict]`:
- Parameterized dynamic WHERE clause on the `hwc` table
- Supported filters: `habitable` (bool → `P_HABITABLE = 1`), `habzone_con` (bool → `P_HABZONE_CON = 1`), `habzone_opt` (bool → `P_HABZONE_OPT = 1`), `esi_min`/`esi_max` (float), `mass_min`/`mass_max` (float on `P_MASS`, Earth masses), `radius_min`/`radius_max` (float on `P_RADIUS`, Earth radii), `temp_min`/`temp_max` (float on `P_TEMP_EQUIL`), `spectral_classes`/`spectral_refine` (on `S_TYPE`), `ly_min`/`ly_max` (float on `S_DISTANCE * 3.26156`)
- Default sort: `P_ESI DESC`; cap at 500 rows
- Returns list of dicts with keys: `P_NAME`, `P_ESI`, `P_HABITABLE`, `P_HABZONE_CON`, `P_HABZONE_OPT`, `P_MASS`, `P_RADIUS`, `P_TEMP_EQUIL`, `S_NAME`, `S_NAME_HD`, `S_NAME_HIP`, `S_TYPE`, `S_DISTANCE`

**Output table columns**: Planet (P_NAME) | ESI (4dp) | Habitable? | In Con HZ? | In Opt HZ? | Mass (M⊕, 2dp) | Radius (R⊕, 2dp) | Temp K (0dp) | Star (S_NAME) | Spectral Type | Distance (LY, 4dp). Count above table.

**GUI** — `HwcSearchPanel`:
- Filter form: ESI min `QDoubleSpinBox` (0.0–1.0, step 0.05, default 0.0); three separate `QCheckBox`es — "Habitable only", "Conservative HZ only", "Optimistic HZ only"; planet mass min/max `QLineEdit` pair (M⊕); planet radius min/max `QLineEdit` pair (R⊕); temp min/max `QLineEdit` pair; spectral-class chips + refine box; LY max `QLineEdit`
- Results in sortable `make_table()`
- "Open system in new tab" (hidden until row selected): adds an inline detail tab rendering the full four-table HWC view for the selected `S_NAME`

### G3: NASA Exoplanet Quick Search

Queries the live NASA Exoplanet Archive `pscomppars` TAP endpoint with user-supplied predicates.

**`core/databases.py`** — add `search_exoplanets(filters: dict) -> list[dict]`:
- Builds ADQL SELECT with a dynamic WHERE clause; uses existing `_query_tap()` helper (already has `_with_retries` + `_network_error_msg`)
- Supported filters: `pl_bmasse_min`/`max` (planet mass in Earth masses), `pl_rade_min`/`max` (planet radius in Earth radii), `pl_orbper_min`/`max` (orbital period in days), `spectral_classes`/`spectral_refine` (on `st_spectype`), `discoverymethod` (exact match), `st_teff_min`/`max`, `sy_dist_max` (distance in parsecs)
- A set `pl_rade` bound excludes rows with null radius (ADQL `BETWEEN` semantics) — i.e. radius-less detections (RV / imaging / microlensing / timing) drop out when a radius filter is active
- Returns planet row dicts carrying the same raw archive columns as `_query_exoplanet_archive()` (plus `pl_rade`) so the detail tab can reuse the existing NASA rendering
- Cap at 200 rows; sorted by `pl_orbsmax ASC`

**Output table columns**: Planet | Host Star | Mass (M⊕, 2dp) | Radius (R⊕, 2dp, `N/A` if null) | Period (d, 2dp) | SMA (AU, 4dp) | Spectral Type | Discovery Method | Teff (K, 0dp) | Distance (pc, 2dp). Count above table.

**GUI** — `NasaExoplanetSearchPanel`:
- Filter form: planet mass min/max `QLineEdit` pair (M⊕), planet radius min/max `QLineEdit` pair (R⊕), orbital period min/max `QLineEdit` pair (days), discovery method `QComboBox` (Any / Transit / Radial Velocity / Direct Imaging / Microlensing / Astrometry / Timing), teff min/max `QLineEdit` pair, spectral-class chips + refine box, max distance `QLineEdit` (parsecs)
- "Search" fires `run_in_background` with the TAP query; uses existing `_network_error_msg` error classification
- Results in sortable `make_table()`; "Open system in new tab" adds an inline detail tab running the full SIMBAD + archive lookup for the host star

### Remaining Steps

- **`gui/panels/__init__.py`** — export `StarSystemsSearchPanel`, `HwcSearchPanel`, `NasaExoplanetSearchPanel`
- **`gui/nav.py`** — add "Search & Filter" nav category with three entries
- **`gui/panels/base.py`** (or a shared helper) — factor the inline result-tabs + detail-tab mechanism, and the spectral-class chip/refine widget, so all three panels reuse them
- **`docs/star-databases.md`** — document all three search functions, the `spectral_classes`/`spectral_refine` keys, the mass/radius filters, return schemas, and 500/200-row caps
- **`docs/gui-architecture.md`** — document the inline result-tabs drill-down pattern and the shared spectral-class control

---

## Phase H — Worldbuilding Calculators

**New panels (GUI-only)**: `RocheLimitPanel`, `TidalLockingPanel`, `HillSpherePanel`, `BinaryOrbitPanel`, `AtmosphereRetentionPanel`
**Existing options touched**: none (pure additions alongside the existing equation calculators, opts 33–41)

New physics tools for authors and worldbuilders. All pure math — no network calls, no CSV reads, no DB access.

### H1: Roche Limit Calculator

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

**GUI** — `RocheLimitPanel`: primary mass `QLineEdit`, satellite density `QLineEdit`, primary radius `QLineEdit` (labeled "optional — estimated from mass if blank"). Pure math — result updates immediately on button click.

### H2: Tidal Locking Timescale Calculator

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

**GUI** — `TidalLockingPanel`: four required `QLineEdit` inputs (primary mass, satellite mass, SMA, rotation); collapsible "Advanced Parameters" section with rigidity and Q fields showing defaults. Pure math.

### H3: Hill Sphere Calculator

Computes the gravitational sphere of influence of a planet within a star system — the region where the planet's gravity dominates over the star's. Stable satellite orbits exist within ~0.5 × Hill radius.

**`core/equations.py`** — add `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0) -> dict`:
- Convert masses: `M_star_kg = star_mass_solar × 1.989e30`, `M_planet_kg = planet_mass_earth × 5.972e24`
- Convert SMA to metres: `a_m = sma_au × 149597870700`
- Hill radius: `r_H = a_m × (1 − e) × (M_planet_kg / (3 × M_star_kg))^(1/3)` metres
- Convert to km and AU; stable orbit limit = `0.5 × r_H`
- Validation note: for Solar System reference, Earth's Hill sphere ≈ 1,496,000 km (1.5M km) — Moon at 384,400 km is well within it
- Returns `{"star_mass_solar": float, "planet_mass_earth": float, "sma_au": float, "eccentricity": float, "hill_radius_km": float, "hill_radius_au": float, "stable_orbit_limit_km": float, "stable_orbit_limit_au": float}`

**Output table columns**: Star Mass (M☉) | Planet Mass (M⊕) | SMA (AU) | Eccentricity | Hill Radius (km) | Hill Radius (AU) | Stable Orbit Limit (km) | Stable Orbit Limit (AU). All 4dp.

**GUI** — `HillSpherePanel`: three required `QLineEdit` fields (star mass, planet mass, SMA), one optional (eccentricity, placeholder "0 if circular"). Pure math.

### H4: Binary Star Orbit Stability Calculator

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

**GUI** — `BinaryOrbitPanel`: four required `QLineEdit` (mass1, mass2, binary SMA, test SMA), one optional (eccentricity, default 0). Result includes stability verdict label styled green (stable) or red (unstable) above the table.

### H5: Planetary Atmosphere Retention Calculator

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

**GUI** — `AtmosphereRetentionPanel`: three `QLineEdit` inputs. Results: escape velocity label above `make_table()`. Status cells colored: green = Retained, yellow = Escaping slowly, red = Lost rapidly (using `QTableView` delegate or HTML in a `QTextEdit` fallback).

### Remaining Steps

- **`gui/panels/worldbuilding.py`** — new file containing all five panel classes; all inherit `ResultPanel` directly (no `DiagramToggleMixin` needed — no visualizations)
- **`gui/panels/__init__.py`** — export all five new panel classes
- **`gui/nav.py`** — add "Worldbuilding" nav category with five entries
- **`docs/equations.md`** — document all five functions with full formula derivations, constant values, and output dict schemas

---

## Phase I — Multi-System / Route Planning

**New panels (GUI-only)**: `MultiStopJourneyPanel`, `NearestNeighborPanel`, `TradeRoutePlannerPanel` (stretch)
**Existing options touched**: opts 17–21 share `compute_lookup_star_for_distance` — no changes needed, just reused; `core/viz.py` and `gui/visualizations/plot_helpers.py` extended for route overlays

### I1: Multi-Stop Journey Calculator

Computes cumulative travel time along an ordered list of stops. Uses the same 3D Euclidean distance math and `_format_travel_time()` as opts 20–21.

**Star name resolution** (per leg): first tries a case-insensitive match against `star_name` in the `star_systems` DB for speed; falls back to a live SIMBAD lookup (via existing `compute_lookup_star_for_distance`) if not found. "sun"/"sol" short-circuits to origin `(0, 0, 0)` with no query, same as opts 20–21. If a lookup fails, the error is reported per-star and the user is asked whether to skip that leg or abort.

**Velocity input**: prompt for velocity unit first (L = LY/HR, C = ×c), then the value — mirrors the two-option pattern of opts 20 vs 21. Derives `ly_hr` and `times_c` from whichever unit is entered.

**Output table**: Leg # | Origin | Destination | Distance (LY) | LY/HR | ×c | Travel Time | Cumulative Time. Footer lines: Total Distance (LY) and Total Travel Time.

**`core/calculators.py`** — add `compute_multi_stop_journey(star_names, velocity_input, use_times_c) -> dict`
- Returns `{"legs": [{"leg": int, "origin": str, "dest": str, "distance_ly": float, "ly_hr": float, "times_c": float, "hours": float, "cumulative_hours": float, "travel_time": str, "cumulative_time": str}], "total_ly": float, "total_hours": float, "total_time": str, "stars": list}` where `stars` is a star-map-compatible list (name, x, y, z, spectral color) for the visualization layer

**GUI** — `MultiStopJourneyPanel`: `QTextEdit` for star names (one per line), velocity unit `QComboBox` (LY/HR / ×c), velocity `QLineEdit`. Run button fires a single `run_in_background` worker that resolves all stars sequentially and computes legs. Results: leg table via `make_table()`. Diagram tabs (3): "Map X–Y", "Map X–Z", "Map 3D" — numbered dashed arrows connect stops in sequence; star dots colored by spectral class; hover shows name + distance from Sol.

### I2: Nearest Neighbor Chain

Greedy nearest-neighbor traversal: from a starting star, repeatedly hop to the closest unvisited star within `max_ly`, building a chain of N hops.

**Position data**: loads all rows from the `star_systems` DB table, parses RA (HMS → decimal degrees), DEC (±DMS → decimal degrees), and LY; converts to 3D Cartesian via the same math used by opts 18–19. The starting star is resolved via SIMBAD (`compute_lookup_star_for_distance`) so its exact position is used; if it also appears in the DB, the DB entry is excluded from candidates to avoid a zero-distance self-match.

**Algorithm**: maintain a `visited` set; at each step compute Euclidean distance from the current position to all unvisited stars; pick the minimum within `max_ly`. Stop early (with a note) if no unvisited star is within range.

**Output table**: Hop # | Star Name | Designations | Spectral Type | Dist from Prev (LY) | Cumulative Dist (LY) | Dist from Sol (LY). Footer: total hops completed, total distance.

**`core/calculators.py`** — add `compute_nearest_neighbor_chain(start_star, num_hops, max_ly) -> dict`
- Returns `{"chain": [{"hop": int, "star_name": str, "desig": str, "sp_type": str, "dist_from_prev_ly": float, "cumulative_ly": float, "ly_from_sol": float}], "stars": list, "total_ly": float, "stopped_early": bool}`

**GUI** — `NearestNeighborPanel`: star name `QLineEdit`, hop count `QSpinBox` (1–50), max hop distance `QDoubleSpinBox`. Results: chain table. Diagram tabs (3): same "Map X–Y", "Map X–Z", "Map 3D" as opt 18–19, with numbered hop-order labels on the route line and the starting star highlighted.

### I3: Trade Route Network Planner (stretch goal)

Given a set of "important" star systems, find the minimum-cost network (minimum spanning tree) that connects all of them.

**Position resolution**: each star resolved from DB or SIMBAD. Pairwise distance matrix built using 3D Euclidean math. Kruskal's MST: sort all `N×(N−1)/2` edges by distance; greedily add non-cycle-forming edges using union-find until `N−1` edges selected.

**Output table**: From | To | Distance (LY). Footer: N nodes, N−1 edges, Total Network Distance (LY).

**`core/calculators.py`** — add `compute_trade_route_mst(star_names) -> dict`
- Returns `{"nodes": [{"name": str, "x": float, "y": float, "z": float, "sp_type": str}], "edges": [{"from": str, "to": str, "distance_ly": float}], "total_ly": float}`

**GUI** — `TradeRoutePlannerPanel`: `QTextEdit` star list + max-jump optional filter. Results: MST edge table. Diagram tab: star map with MST edges as solid lines (distinguished from dashed route lines used by I1/I2); nodes labeled; hover shows star name + degree (number of MST connections).

### Shared Visualization Infrastructure

**`core/viz.py`** — add `prepare_route_map(result) -> dict`
- Accepts multi-stop, nearest-neighbor, or MST result dicts; normalizes to `{"stars": list, "edges": [{"x1","y1","z1","x2","y2","z2","label"}], "edge_style": "dashed"|"solid"}`

**`gui/visualizations/plot_helpers.py`** — extend `make_star_map_canvas` and `make_star_map_3d_canvas` with optional `routes` parameter
- `routes`: list of `{"x1","y1","x2","y2","label","style"}` dicts; drawn as annotated lines over the scatter
- Labels rendered at leg midpoints; style `"dashed"` for ordered routes, `"solid"` for MST edges
- **Shared with Phase O8** (two-star maps for opts 17/20/21): whichever phase is built first implements the `routes` parameter; the other reuses it unchanged

### Remaining Steps

- **`gui/panels/__init__.py`** — export `MultiStopJourneyPanel`, `NearestNeighborPanel`, `TradeRoutePlannerPanel`
- **`gui/nav.py`** — add "Route Planning" nav category with three entries
- **`docs/calculators.md`** — document all three functions, resolution fallback order, and output dict schemas

---

## Phase J — User Preferences & Settings

**New panels (GUI-only)**: `SettingsPanel`, `FavoritesPanel`
**Existing panels touched**: all network-bound panels gain persistent field values (J1); the SIMBAD panel (opt 1) gains a bookmark button (J2); all panels outputting AU or temperature gain unit-toggle support (J3); all matplotlib panels gain dark-mode canvas colors (J4)

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

The unit toggle is GUI-only — it changes the display unit in panel renders via the shared `format_au()` / `format_temp()` helpers.

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

**New panels (GUI-only)**: `HonorverseHyperTimePanel`, `HonorverseImpellerPanel`, `HonorverseMissilePanel`
**Existing options touched**: opt 15 — mass-band acceleration table extracted into `core/science.py` and reused by K2; opt 16 — 24-band speed table extracted into `core/science.py` and reused by K1. Both opts 15 and 16 are then refactored to call the new core functions rather than using inline data.

### K1: Hyper Translation Time Calculator

Given a distance in light years and ship type, shows travel time across all 24 Honorverse hyper bands.

**Data source**: the 24-band expanded speed table currently hardcoded in `main.py` `honorverse_effective_speed()` (opt 16). This table must first be extracted to a module-level constant in `core/science.py` — a list of dicts, one per band, with keys `band`, `warship_xc`, `merchantship_xc`. Opt 16 is then refactored to call `core.science.get_honorverse_bands()` instead of using inline data (no behavior change).

**`core/science.py`** — add `_HONORVERSE_BANDS` module-level constant (24 entries, Alpha through Omega) and `compute_hyper_translation_time(distance_ly, ship_type) -> list[dict]`:
- `ship_type`: `"warship"` or `"merchantship"` (case-insensitive)
- For each band: `speed_ly_hr = speed_xc / 8765.8128`; `travel_hours = distance_ly / speed_ly_hr`; formats via existing `_format_travel_time()`
- Merchantship bands marked "Currently Unattainable" in opt 16 (Iota+) are included in output with `travel_time = "N/A"` and `travel_hours = None`
- Returns list of `{"band": str, "speed_xc": float, "speed_ly_hr": float, "travel_hours": float | None, "travel_time": str}`

**GUI** — `HonorverseHyperTimePanel`: distance `QLineEdit` + ship type `QComboBox` (Warship / Merchantship). Pure math, no background thread needed. Results via `make_table()`. N/A rows rendered with gray text.

### K2: Impeller Wedge Geometry Calculator

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

**GUI** — `HonorverseImpellerPanel`: mass `QLineEdit`, ship type `QComboBox`, wedge power `QSlider` (1–100) with live `QLabel` readout. Pure math — results update immediately on slider move.

### K3: Missile Intercept Calculator

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

**GUI** — `HonorverseMissilePanel`: five `QLineEdit` inputs. Pure math — no background thread. Results: verdict label (green = intercept, red = no intercept) + profile table via `make_table()`.

### Remaining Steps

- **`gui/panels/honorverse.py`** — add `HonorverseHyperTimePanel`, `HonorverseImpellerPanel`, `HonorverseMissilePanel` alongside existing panels
- **`gui/panels/__init__.py`** — export three new panel classes
- **`gui/nav.py`** — extend "Science Fiction" category with three new entries
- **`main.py`** — refactor opts 15 and 16 to call the new core functions (no behavior change)
- **`docs/science-and-scifi.md`** — document all three new functions, `_HONORVERSE_BANDS`, `_HONORVERSE_ACCEL_BANDS`, and the refactoring of opts 15–16

---

## Phase L — Exoplanet Comparison Dashboard

**New panels (GUI-only)**: `StarComparisonPanel`, `EsiRankingPanel`, `StellarEvolutionPanel`, plus `ImportHypatiaPanel` and `HypatiaSearchPanel` (L4)
**Existing options touched**: opt 1 SIMBAD lookup logic reused by L1; opt 6 `HwcPanel` drill-down target for L2; `core/viz.py` and `gui/visualizations/plot_helpers.py` extended for the evolution diagram in L3

### L1: Side-by-Side Star Comparison

Accepts 2–4 star names, runs a SIMBAD lookup for each, and renders a single transposed comparison table where rows are properties and columns are stars. Hypatia Catalog data (elemental abundances and kinematics) is fetched alongside SIMBAD and included as additional comparison rows.

**Data resolution per star**:
1. SIMBAD lookup (reuses existing pattern from `core/databases.py`) for: `sp_type`, `teff` (from `mesfe_h.teff`), `plx_value` (→ LY), `V` (apparent magnitude), `ra`, `dec`
2. If `st_rad` or `st_teff` missing from SIMBAD, attempt a supplemental NASA `pscomppars` TAP query using the best available designation (HIP → HD → TIC → Gaia EDR3) to fill `st_teff`, `st_rad`, `st_mass`, `st_lum`
3. HZ inner/outer computed via the existing Kopparapu coefficient logic (`_kopparapu_seff`) using the best available luminosity and teff
4. Hypatia Catalog lookup via `compute_hypatia_data(simbad_result)` — fetches stellar properties (logg, B-V, distance, disk membership), kinematics (U/V/W velocities, proper motions), and elemental abundances (the full 104-species Lodders 2009 set; see `core/hypatia_elements.py`). The comparison table need only surface a curated subset of rows (e.g. Fe/H, Mg/H, Si/H, O/H). Errors stored per-star without aborting the comparison.

**`core/databases.py`** — add `compare_stars(names: list[str]) -> dict`:
- Runs up to 4 SIMBAD + Hypatia lookup pairs; per-star errors are stored in the result without aborting the comparison
- HZ bounds: Conservative Inner (Runaway Greenhouse) and Conservative Outer (Maximum Greenhouse) only — same two used by the single-star HZ tables
- Returns `{"stars": [{"name": str, "sp_type": str, "teff": int|None, "luminosity": float|None, "mass": float|None, "radius": float|None, "hz_inner_au": float|None, "hz_outer_au": float|None, "ly": float|None, "app_magnitude": float|None, "hypatia": dict|None, "error": str|None}]}`
- `hypatia` key: the raw `compute_hypatia_data()` result dict (`{"star_name", "properties", "abundances"}`) or `{"error": str}` if the Hypatia call failed

**Comparison table rows** (property labels): Spectral Type | Temp (K) | Luminosity (Lsun) | Mass (Msun) | Radius (Rsun) | HZ Inner (AU) | HZ Outer (AU) | Distance (LY) | Apparent Magnitude. Followed by Hypatia rows (only rendered when at least one star has Hypatia data): log g | Disk | Fe/H | Mg/H | Si/H | O/H | U vel (km/s) | V vel (km/s) | W vel (km/s). Each column = one star; missing values shown as "N/A".

**GUI** — `StarComparisonPanel`: 2–4 `QLineEdit` fields (star 1 always visible; "Add Star" button reveals stars 3 and 4 up to maximum 4). Single "Compare" button fires parallel `run_in_background` workers — one per star, each running `compute_simbad_lookup` + `compute_hypatia_data` sequentially; all workers are joined before rendering. Results rendered as a transposed `make_table()` — stars as columns, properties as rows. Cells containing errors shown with red text. Hypatia rows separated by a horizontal rule row in the table.

**Diagram tab** — "Abundance Profiles": when `mpl_available()` and at least one star has abundance data, add a diagram tab to `_viz_tabs_widget` (via `DiagramToggleMixin`) showing a grouped horizontal bar chart comparing [X/H] values across all stars for the elements present in any star's Hypatia result. One color per star; elements on the y-axis; vertical line at 0 (solar reference). Built from a new `make_abundance_comparison_canvas(parent, stars_data)` helper in `gui/visualizations/plot_helpers.py`.

### L2: Exoplanet ESI Ranking

Queries the local HWC SQLite table for all planets meeting a minimum ESI threshold, with optional additional filters, and displays a ranked list. Row selection drills into the full HWC display for that star system.

**ESI context**: Earth Similarity Index (0–1.0); Earth = 1.0. Values > 0.8 are considered "Earth-like". The `P_ESI` column is already present in the `hwc` table.

**`core/databases.py`** — add `rank_hwc_by_esi(esi_min=0.8, habitable_only=False, con_hz_only=False, ly_max=None) -> list[dict]`:
- Builds dynamic WHERE clause: `P_ESI >= ?` always; `P_HABITABLE = 1` if `habitable_only`; `P_HABZONE_CON = 1` if `con_hz_only`; `S_DISTANCE * 3.26156 <= ?` if `ly_max` supplied
- Returns list of dicts: `P_NAME`, `P_ESI`, `P_HABITABLE`, `P_HABZONE_CON`, `P_HABZONE_OPT`, `P_TEMP_EQUIL`, `S_NAME`, `S_NAME_HD`, `S_NAME_HIP`, `S_TYPE`, `S_DISTANCE` (parsecs)
- Sorted by `P_ESI DESC`

**Output table columns**: Rank | Planet (P_NAME) | ESI (4dp) | Habitable? | In Con HZ? | In Opt HZ? | Temp K (0dp) | Star (S_NAME) | Spectral Type | Distance (LY, 4dp)

**GUI** — `EsiRankingPanel`: `QDoubleSpinBox` for ESI (0.0–1.0, default 0.8, step 0.05) + `QCheckBox` for "Habitable only" + `QCheckBox` for "Conservative HZ only" + optional max LY `QLineEdit`. Results in sortable `make_table()`. Row double-click fires `show_panel(HwcPanel)` with `S_NAME` pre-filled in the HWC search field.

### L3: Stellar Evolution Timeline

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

**Output table columns**: Stage | Start (Gyr) | End (Gyr) | Duration (Gyr). Current stage row bolded in the GUI. Footer: total lifetime, current stage if age supplied.

**`core/viz.py`** — add `prepare_evolution_diagram(result) -> dict`:
- Normalizes stages to `{"stages": list, "current_age_gyr": float|None, "x_max_gyr": float}`
- `x_max_gyr` = `max(total_gyr, current_age_gyr or 0) × 1.1` for axis scaling

**`gui/visualizations/plot_helpers.py`** — add `make_evolution_canvas(parent, data)`:
- Horizontal stacked bar chart; one bar per stage, colored by stage color
- x-axis: time in Gyr; y-axis: single row labeled with the star mass
- Vertical dashed line at `current_age_gyr` labeled "Current Age: X.XX Gyr"
- Stage name labels centered within each bar segment (omitted if segment too narrow)
- Same light theme (`facecolor="#f5f5f5"`)

**GUI** — `StellarEvolutionPanel`: mass `QDoubleSpinBox` + optional age `QDoubleSpinBox` (enabled via "Enter current age" checkbox). Pure math — no background thread. Results: stage table + "Evolution Diagram" viz tab via `DiagramToggleMixin`.

### Remaining Steps

- **`gui/panels/comparison.py`** — new file containing `StarComparisonPanel`, `EsiRankingPanel`, `StellarEvolutionPanel`
- **`gui/panels/__init__.py`** — export all three panel classes
- **`gui/nav.py`** — add "Comparison" nav category with three entries
- **`gui/visualizations/plot_helpers.py`** — add `make_abundance_comparison_canvas(parent, stars_data)` for the multi-star grouped abundance chart
- **`docs/star-databases.md`** — document `compare_stars` including `hypatia` key in the per-star result dict, the parallel fetch pattern, and the abundance comparison rows; document `rank_hwc_by_esi` with filter keys and return schemas
- **`docs/equations.md`** — document `compute_stellar_evolution` with stage duration formulas and special-case mass ranges

### L4: Hypatia Catalog Cache & Abundance Search

Batch-fetches Hypatia Catalog data for all stars in the `star_systems` DB table and stores it locally, then exposes a filter-by-abundance search interface. This unlocks abundance-based filtering in G1 (Star Systems Search) and removes the per-lookup network dependency from L1 (Star Comparison).

**Why a local cache**: the Hypatia API at `https://hypatiacatalog.com/hypatia/api/v2` is per-star (no bulk endpoint). With ~252K rows in `star_systems`, a full batch is impractical; the cache should target a useful subset — the same stars already in the DB that have HIP or HD designations (the Hypatia name-resolution priority order is HIP → HD → main_id).

**`core/db.py`** — add to schema. **Note:** the element set is now the full **104 species** (`core/hypatia_elements.py`), not the original 19 the column list below assumes. Before building this, reconsider the storage shape — a wide 104-column table is unwieldy and many species are sparsely measured; a long/EAV `hypatia_abundance(star_name, element, mean, std, min, max, n)` table (with the star-level properties kept in `hypatia_cache`) is the better fit and keeps abundance filtering generic. The column list below is the original 19-element sketch, retained for reference:
```sql
CREATE TABLE IF NOT EXISTS hypatia_cache (
    star_name TEXT PRIMARY KEY,
    hip TEXT,
    hd TEXT,
    teff REAL,
    logg REAL,
    vmag REAL,
    bv REAL,
    distance_pc REAL,
    disk TEXT,
    u_vel REAL,
    v_vel REAL,
    w_vel REAL,
    pm_ra REAL,
    pm_dec REAL,
    fe_h REAL,
    mg_h REAL,
    si_h REAL,
    ca_h REAL,
    ti_h REAL,
    o_h REAL,
    c_h REAL,
    n_h REAL,
    na_h REAL,
    al_h REAL,
    s_h REAL,
    ni_h REAL,
    co_h REAL,
    cr_h REAL,
    mn_h REAL,
    ba_h REAL,
    y_h REAL,
    sr_h REAL,
    eu_h REAL,
    fetched_date TEXT
)
```

**`core/databases.py`** — add `import_hypatia_cache(progress_callback=None) -> dict`:
- Queries `star_systems` for all rows that have a HIP or HD designation (parsed from the `designations` column)
- For each star: builds a `simbad_compat` dict (same format expected by `compute_hypatia_data`) and calls `compute_hypatia_data()`; on success, upserts a row into `hypatia_cache` via `INSERT OR REPLACE`
- Rate-limiting: 0.25 s sleep between API calls to avoid hammering the Hypatia server; progress reported via `progress_callback(current, total, star_name)`
- Stars that return a Hypatia error are silently skipped (not inserted); a count of successes and failures is returned
- Returns `{"inserted": int, "skipped": int, "errors": int, "total_candidates": int}`

**`core/databases.py`** — add `search_hypatia_cache(filters: dict) -> list[dict]`:
- Dynamic WHERE clause on `hypatia_cache` using non-None filter keys
- Supported filters: `fe_h_min`/`fe_h_max` (float), `disk` (exact match: `"thin disk"`, `"thick disk"`, `"halo"`), `teff_min`/`teff_max` (float), `ly_min`/`ly_max` (float; joins against `star_systems` on `star_name` for the `light_years` column), `element` + `element_min`/`element_max` (filter on any single element column, e.g. `element="mg_h"`)
- Default sort: `fe_h DESC`; cap at 500 rows
- Returns list of dicts with keys: `star_name`, `hip`, `hd`, `disk`, `teff`, `fe_h`, `mg_h`, `si_h`, `o_h`, `distance_pc`, `ly` (joined from `star_systems`), plus the per-element abundance values (the full 104-species set if stored, per the schema note above)

**Output table columns**: Star Name | HIP | HD | Disk | Teff (K) | Fe/H | Mg/H | Si/H | O/H | Distance (LY). Count above table; "Showing first 500 results." footer if capped.

**GUI import** — `ImportHypatiaPanel`: "Import Hypatia Data" button fires `run_in_background`; progress streamed via `set_status()` updates; completion summary displayed as a result label. Warns the user upfront that this may take several minutes for large star_systems tables.

**GUI search** — `HypatiaSearchPanel`: filter form matching CLI prompts (Fe/H min/max `QLineEdit` pair, disk `QComboBox` with Any/Thin/Thick/Halo, teff min/max `QLineEdit` pair, element `QComboBox` + value min/max `QLineEdit` pair, max LY `QLineEdit`). Results in sortable `make_table()`. "Open in SIMBAD" button on row selection — also activates G1 stretch goal: passing `fe_h_min`/`fe_h_max` as additional filter parameters to `search_star_systems()` when both this table and the star_systems table have data.

**G1 integration**: once `hypatia_cache` is populated, `search_star_systems()` (G1) gains `fe_h_min`/`fe_h_max` filter parameters (the commented-out stub from G1). The filter adds `JOIN hypatia_cache hc ON ss.star_name = hc.star_name WHERE hc.fe_h BETWEEN ? AND ?` to the existing G1 query.

### Remaining Steps (L4)

- **`gui/panels/comparison.py`** — add `ImportHypatiaPanel`, `HypatiaSearchPanel`
- **`gui/panels/__init__.py`** — export both new panel classes
- **`gui/nav.py`** — add "Import Hypatia Cache" to Utilities category; add "Hypatia Abundance Search" to Comparison (or Search & Filter) category
- **`core/db.py`** — add `hypatia_cache` table to schema (auto-created on first `get_db()` call)
- **`docs/star-databases.md`** — document `import_hypatia_cache`, `search_hypatia_cache`, `hypatia_cache` table schema, rate-limiting behavior, and G1 integration path

---

## Phase M — GCNS Interactive Surfacing

**New panels (GUI-only, no menu numbers)**: `GcnsCensusBrowserPanel`, `GcnsSourceLookupPanel`, `GcnsSystemViewerPanel`, plus `GcnsDistancePanel`, `GcnsTravelTimePanel`, `GcnsStarsWithinStarPanel`
**Existing options touched**: opt 1 (SIMBAD Lookup) gains a GCNS cross-reference block; opts 18/19 star-map viz infrastructure reused by M1

GCNS (opt 58) is fully ingested — the 331,312-source Bayesian-distance census plus the ~17,103 Gaia-resolved multiple-star systems — but is reachable **only** through `query.py` (the `gcns-*` subcommands, for the external scifiWorldBuilding repo). Interactive users currently see only the import panel. Phase M reverses the deliberate "`query.py`-only" exposure and gives the data display surfaces, reusing the existing `compute_gcns_*` core functions without modification.

> **GUI-only — no menu numbers, no renumber**: Phase M is built entirely as GUI nav entries (precedent: `DbStatusPanel`, `NasaPlanetarySystemsMapPanel`), so it touches neither `main.py`'s `MENU_OPTIONS` nor the CLI menu. There is therefore **no collision with Phase G** and nothing to renumber — option numbers are CLI menu keys, which the GUI nav (label → panel class) does not use. The six panels are grouped under a new **"GCNS"** nav category. (The hedged `~42–55` numbering collisions across H/I/K/L remain a CLI-only concern, relevant only if those phases are ever built as CLI options.)

### Resolution model — name vs. Gaia source_id

The GCNS core is keyed on **Gaia source_id and distance**, and every reader runs **offline** against the local `gcns_stars`/`gcns_systems`/… tables. SIMBAD is **never required** — it serves only as an optional front-end that translates a human-typed star *name* into a Gaia source_id. This dual path is already built and proven in the `query.py` GCNS calculators (`--star` vs `--id`); Phase M panels mirror it:

- **Name input** → SIMBAD lookup (background QThread, like every other network panel) → extract the Gaia id from `designations["Gaia EDR3"]` (holds `"Gaia DR3 <id>"`) → fetch the `gcns_stars` row by id → fall back to an exact `star_name` match for `missing_10mas` rows (Alpha Cen A/B, which have no source_id). This is exactly `_resolve_gcns_row` in `core/databases.py`.
- **Gaia source_id input** → direct local fetch, **no network, no thread** — instant.
- A star genuinely absent from GCNS surfaces a clean "… is not in the GCNS catalog …" message — it is **never** silently substituted with a SIMBAD distance. An ambiguous name names the candidate source_ids.

Panels offering lookup (M2, M3) and the GCNS calculators expose **both** inputs — a name field and a raw source_id field — so power users skip the SIMBAD round-trip. M1 (census) takes neither: it is a pure distance-limit query.

### M1: GCNS Census Browser — `GcnsCensusBrowserPanel`

All GCNS sources within N light years of Sol. Backed by `databases.compute_gcns_within_sol(ly)`.

**No SIMBAD, no network, no background thread** — an instant local-DB read, more like opt 18 (Stars within Distance of Sol, which reads the DB directly) than opt 1.

**Output table columns**: Star Name | Gaia source_id | Spectral Type | Dist (pc) | −σ / +σ (pc) | Light Years (4dp) | Distance Method | In SIMBAD. The **−σ/+σ uncertainty columns** (`dist_lo_pc`/`dist_hi_pc`) are the headline differentiator — nothing else in the app carries a distance error bar; `missing_10mas` rows show the point value only (1/ϖ inversion, uncertainty cells blank). Count printed above: `"N GCNS sources found."`

Single distance `QLineEdit`; instant render (no worker). Error if `gcns_stars` empty → directs user to run opt 58. Reuses the opts 18/19 star-map / 3D-map viz tabs via the heliocentric `x`/`y`/`z` already returned by `compute_gcns_within_sol`. **Viz enhancement**: `make_star_map_canvas` gains an optional radial distance-uncertainty indicator (drawn from `dist_lo_pc`/`dist_hi_pc`) — the first GCNS-specific visualization capability.

### M2: GCNS Source Lookup — `GcnsSourceLookupPanel`

Full detail for a single GCNS source. Dual input (name → SIMBAD → id, or raw Gaia source_id → offline). Backed by `databases.compute_gcns_by_source_id(id)` with the `_resolve_gcns_row` name path.

**Output**: a single-star detail view — Bayesian distance + uncertainty, light-years, `distance_method`, Gaia **G/BP/RP** photometry (kept explicitly separate from Johnson V `app_magnitude`), `wd_prob`, `astrom_reliable_prob`, `rv_kms`, SIMBAD cross-match fields (`spectral_type`, `star_name`), and `system_id`/`n_components`. When `system_id` is set, a line: `"Part of a resolved N-component system — open in the System Viewer."`

A name `QLineEdit` and a Gaia source_id `QLineEdit` (use whichever is filled; id wins if both). Name path runs in a background worker; id path renders instantly.

### M3: Resolved Multiple-Star System Viewer — `GcnsSystemViewerPanel`

The Gaia-resolved system containing a given source. Dual input (name → id, or source_id). Backed by `databases.compute_gcns_system(id)`.

**Output** — three sections:
- **System summary**: `system_id`, `n_components`, `n_pairs`, `any_bin`/`any_bound`/`all_bound`, `max_proj_sep_au`/`min_proj_sep_au`, `n_in_gcns_stars`.
- **Members table**: `gaia_source_id`, `in_gcns_stars`, `is_query` (▶ marker on the queried component), `star_name`, `spectral_type`, `dist_pc`, `light_years` (last four joined from `gcns_stars`; `null`/N-A for a member not present there — retained, not dropped).
- **Pairs table**: `source_id1`/`source_id2`, `separation_arcsec`, `mag_diff`, `proj_sep_au`, `bin`, `bound`.

Error when the id is in **no** resolved system — message clarifies *"not Gaia-resolved (not necessarily single)"* — or when `gcns_systems` is empty. Members + pairs rendered as `make_table()`s. **Stretch viz**: a component-geometry diagram positioned from `proj_sep_au` (note the friends-of-friends chaining caveat — `n_components` from chained pairs is an upper bound in crowded fields).

### M4: GCNS-backed calculators — GUI-only, no menu numbers

`GcnsDistancePanel`, `GcnsTravelTimePanel`, `GcnsStarsWithinStarPanel` mirror opts 17 / 20–21 / 19 but compute over the **GCNS census** (Bayesian distances + uncertainties) instead of the SIMBAD `star_systems` table — keeping Gaia-resolved close companions that the SIMBAD `stars-within-star` drops within 0.001 ly. Backed by the existing `compute_gcns_distance` / `compute_gcns_travel_time` / `compute_gcns_stars_within_star`. Each accepts both name and source_id endpoints and carries `distance_method` + `dist_lo_pc`/`dist_hi_pc` in its info blocks.

**Deliberately GUI-only (no menu numbers)**: these duplicate existing *numbered* calculators on a different table and are already fully exposed via `query.py`; three more near-identical CLI menu entries would be clutter. Precedent: `DbStatusPanel` and `NasaPlanetarySystemsMapPanel` are GUI-only with no option number.

### M5: opt 1 SIMBAD GCNS cross-reference — enhancement, no new option

opt 1 already resolves `designations["Gaia EDR3"]`; M5 reuses that id **for free (no extra network)** to attach a GCNS block.

- After designations resolve, parse the bare Gaia id and call `compute_gcns_by_source_id(id)` — a single indexed local-DB read. Store the result under a new `"gcns"` key on the `compute_simbad_lookup` return (`None` when no id / not found / table empty).
- **Headline value**: display the GCNS **Bayesian distance with its 16th/84th uncertainty** alongside opt 1's existing naive **1/ϖ parallax distance** — a probabilistic distance *with error bars* next to the point estimate. Plus `distance_method`, `astrom_reliable_prob`, `wd_prob`, the Gaia G/BP/RP photometry (separate from Johnson V), and a "part of a resolved N-component system — open in the System Viewer" pointer when `system_id` is set.
- **Non-fatal and silent when absent** — no Gaia id, GCNS not imported, or star outside the census → the block is simply omitted, exactly how opt 1's optional HWO/Hypatia sub-sections behave.
- **GUI**: `SimbadPanel` shows the block as a small table inside the **Star Properties** tab (or a dedicated **GCNS** tab when data is present). (The CLI `query_star()` is out of scope — GUI-only project — but the enrichment lives in the shared core function, so a CLI print could be added later for free.)
- **`query.py` parity**: `simbad-lookup` output gains the same optional `"gcns"` key, so the consuming repo gets the Bayesian distance in the call it already makes.

### Remaining Steps

- **`core/databases.py`** — add the M5 `"gcns"` enrichment to `compute_simbad_lookup` (single indexed read; non-fatal). No new core functions needed for M1–M4 — they reuse `compute_gcns_within_sol`, `compute_gcns_by_source_id`, `compute_gcns_system`, and the three `compute_gcns_*` calculators verbatim.
- **`gui/panels/gcns.py`** — new file: `GcnsCensusBrowserPanel`, `GcnsSourceLookupPanel`, `GcnsSystemViewerPanel` (census inherits `(DiagramToggleMixin, ResultPanel)` for the map tabs; the other two inherit `ResultPanel`), plus `GcnsDistancePanel`, `GcnsTravelTimePanel`, `GcnsStarsWithinStarPanel`.
- **`gui/panels/simbad.py`** — render the M5 GCNS cross-reference block.
- **`gui/panels/__init__.py`** — export the six new panel classes.
- **`gui/nav.py`** — add a **"GCNS"** nav category (census, source lookup, system viewer, + the three calculators). No `main.py` / `MENU_OPTIONS` changes — GUI-only.
- **`gui/visualizations/plot_helpers.py`** — optional distance-uncertainty indicator in `make_star_map_canvas`.
- **`query.py`** — add the optional `"gcns"` key to `simbad-lookup` output.
- **`docs/gui-architecture.md`** — document the three GCNS panels + the six panel→nav mappings + opt-1 cross-reference. **`docs/star-databases.md`** — document the GCNS display surfaces. **`docs/integration.md`** — note the new `simbad-lookup` `"gcns"` key.

---

## Phase N — query.py Integration Expansion

**New panels**: none — integration-surface only (no GUI, no CLI menu changes; see the scope-note exception above)
**Existing options touched**: none — every subcommand wraps an existing `core/` function verbatim. Precedent: Phase M5 already extends `query.py` (the `"gcns"` key on `simbad-lookup`).

The ScienceFictionResearch repo consumes this app exclusively through `query.py` (see `docs/integration.md`). A 2026-06-10 audit found ~24 `core/` `compute_*` functions with no subcommand; this phase exposes the **curated five** with real integration value and records why the rest were excluded.

**Shared conventions** (same contract as every existing subcommand — see `docs/integration.md` "Implementation notes"):
- Malformed/missing args → argparse rejection, **exit 2**, message on stderr (not JSON).
- Semantically invalid values (e.g. non-positive acceleration) → the core function's `{"error": ...}` dict on stdout, **exit 1**.
- Success → the core function's return dict, pretty-printed, **exit 0**. No new output shapes are invented — each subcommand returns exactly what its core function returns today.

### N1: `habitable-zone-sma`

HZ boundaries plus the object's Seff and HZ membership verdict (the opt-40 calculation).

```bash
query.py habitable-zone-sma --teff 4900 --luminosity 0.15 --sma 0.45
```
Core function: `equations.compute_habitable_zone_sma(teff, luminosity, sma)` (`core/equations.py:175`). No network. Complements the existing `habitable-zone` subcommand (which lacks the per-object Seff/verdict).

### N2: `star-luminosity`

Stellar luminosity from radius and temperature: `L = R² × (T/5778)⁴` (the opt-41 calculation).

```bash
query.py star-luminosity --radius 0.82 --teff 5344
```
Core function: `equations.compute_star_luminosity(radius, temp)` (`core/equations.py:38`). No network. Arg is `--teff` for consistency with N1/`habitable-zone`, mapped to the function's `temp` parameter.

### N3 / N4: `brachistochrone-au` and `brachistochrone-lm`

All three brachistochrone acceleration profiles for a given distance (the opt-29/opt-30 calculations).

```bash
query.py brachistochrone-au --accel-g 1.0 --au 5.2
query.py brachistochrone-lm --accel-g 0.5 --lm 43.2
```
Core functions: `calculators.compute_travel_time_system_au(accel_g, distance_au)` / `compute_travel_time_system_lm(accel_g, distance_lm)` (`core/calculators.py:900` / `:918`). No network.

### N5: `travel-time-solar`

Brachistochrone travel time between two solar-system bodies at a departure epoch (the opt-22 calculation). **Live JPL Horizons network call** — must be flagged as such in the `docs/integration.md` quick-reference table (the only network-bound entry in this phase).

```bash
query.py travel-time-solar --origin Earth --destination Mars --accel-g 1.0
query.py travel-time-solar --origin Earth --destination "Jupiter" --accel-g 0.3 --v-cap-pct 5 --date 2027-03-15
```
Core function: `calculators.compute_travel_time_solar_objects(origin, destination, accel_g, v_cap_pct=3.0, departure_date=None)` (`core/calculators.py:936`). `--v-cap-pct` defaults to 3.0; `--date` is ISO `YYYY-MM-DD`, defaulting to today. Ambiguous Horizons names return the disambiguation error already produced by the core function. The result includes `planet_positions` / `origin_xyz` / `dest_xyz`, which JSON consumers may ignore.

### Deliberately excluded (do not re-propose without new justification)

- **Unit converters** (opts 25–28, 31–32 equivalents: ly/hr ↔ ×c, distance/time at constant velocity) — one-line arithmetic on the documented constant `8765.8128`; a caller can do this itself.
- **Static data-table dumps** (main-sequence properties, solar-system tables, Honorverse tables) — static reference data; no computation to delegate.
- **`star-regions-raw`** (manual six-parameter regions) — the SIMBAD-backed `star-regions` already covers the integration use case.

### Forward note — Phase H

When Phase H's five equation functions are built (`compute_roche_limit`, `compute_tidal_locking_time`, `compute_hill_sphere`, `compute_binary_orbit_stability`, `compute_atmosphere_retention`), each gains a `query.py` subcommand **at build time** under this phase's conventions, rather than as a separate retrofit.

### Remaining Steps

- **`query.py`** — five dispatcher functions + argparse subparsers (numeric validation per shared conventions above)
- **`docs/integration.md`** — five rows in the quick-reference table (N5 flagged as live network) + one subcommand section each, following the existing format
- No GUI, CLI, `core/`, or DB changes

---

## Phase O — Visualization Expansion

**New panels (GUI-only)**: none — every item adds viz tabs, canvases, or interactivity to *existing* panels
**Existing options touched (viz layer only — no computation changes)**: 1, 3–6, 8–14, 17–24, 29–30, plus `NasaPlanetarySystemsMapPanel`

Sourced from a 2026-06-10 visualization audit: the app fetches substantial data it never draws (`pl_orbincl` is explicitly dropped by both orbit-prep functions; GCNS photometry, Hypatia UVW kinematics, and the complete HR-diagram dataset in `main_sequence_stars` are all unvisualized), ~35 panels have no diagrams at all, and no animation or table↔map linking exists anywhere (no `FuncAnimation`, no time sliders; all date controls are one-shot).

> **Mockup-gated, individually skippable.** Before implementing, build an HTML mockup per item (`mockups/phase-o/o<NN>-<slug>.html`, following the `mockups/phase-g.html` precedent) for maintainer review. The maintainer decides per-item inclusion **at implementation time from the mockups** — items are independent unless a dependency is noted below; skipping any item must not block the others.

**Item index**: A. Signature features — O1 night sky, O2 HR diagrams, O3 mass–radius, O4 Solar System overlay, O5 date scrubber/animation. B. Diagram parity — O6 (opt 13), O7 (opt 11), O8 (opts 17/20/21), O9 brachistochrone charts (22–24/29–30), O10 Honorverse (14 + 8–10 overlay). C. Unvisualized data — O11 Toomre kinematics, O12 HWC habitability, O13 transit geometry, O14 size strip. D. Interactivity — O15 table↔map linking, O16 legend filtering, O17 isochrone rings, O18 find-star box.

### O1: Night Sky From Another Star (opt 19)

A celestial-sphere view of the sky as seen *from* the queried center star, computed entirely from data opt 19 already returns.

**`core/viz.py`** — add `prepare_sky_from_star(result, mag_limit=6.5) -> dict`:
- Input: the `compute_stars_within_distance_of_star` result (center at origin; each star carries shifted `x/y/z` in ly, `Star Name`, `Spectral Type`; per-row apparent magnitude and parsecs must be threaded through from the `star_systems` rows — extend the result rows with `app_magnitude` and `parsecs` keys, a one-line change in `core/calculators.py` `compute_stars_within_distance_of_star`).
- **Sol is appended as a sky object** at the vector pointing from the center star back to Sol (i.e. `-center_x/-center_y/-center_z`), with `M_V = 4.83`.
- Per star: vector `v = (x, y, z)` from vantage; `d_ly = |v|`; `ra_deg = degrees(atan2(y, x)) % 360`; `dec_deg = degrees(asin(z / d_ly))`.
- Apparent magnitude from vantage: `M = app_magnitude + 5 − 5·log₁₀(parsecs)` (absolute mag from the Sol-centric values), then `m' = M − 5 + 5·log₁₀(d_ly / 3.26156)`. Stars with NULL `app_magnitude` are **skipped and counted** (`skipped_no_mag` in the return) — never given a fabricated magnitude.
- Filter to `m' ≤ mag_limit`. Returns `{"vantage_name": str, "mag_limit": float, "skipped_no_mag": int, "stars": [{"name", "ra_deg", "dec_deg", "mag", "sp_class", "color"}]}` or `{"error": str}`.

**`gui/visualizations/plot_helpers.py`** — add `make_sky_canvas(parent, data)`:
- Dark navy chart palette (same constants as `make_star_chart_canvas`). Aitoff projection (`fig.add_subplot(projection="aitoff")`) with RA reversed (sky convention); fall back to a rectangular RA/Dec plot if the projection complicates hover math — decide in the mockup.
- Marker size scaled by brightness: `size = max(2, 40 × 10^(−0.4 × (mag − mag_min)))` clamped to [2, 80]; color by spectral class (same map as the star charts). Hover: name, apparent mag from vantage, distance from vantage. Click: full info box.
- Title: `"Night sky from {vantage_name} (to m={mag_limit})"`. A footnote label when `skipped_no_mag > 0`: `"N stars omitted (no V magnitude)"`.

**GUI** — `StarsWithinDistanceStarPanel` (19) gains a **"Night Sky"** viz tab plus a magnitude-limit `QLineEdit` (default 6.5) inside the tab with an Apply button (re-runs `prepare_sky_from_star` on the cached result — no new query). Caveat label: the view only contains stars within the queried distance limit; querying ≥ 50 ly gives a fuller sky.

### O2: HR / Color–Magnitude Diagrams (opts 12, 18, 19)

No HR diagram exists anywhere despite three ready datasets. (The GCNS BP−RP CMD belongs to **Phase M1** as an extension — not duplicated here.)

**O2a — opt 12 reference HR diagram.** `core/viz.py` — add `prepare_hr_main_sequence() -> dict`: reads the `main_sequence_stars` table (`spectral_class`, `b_v`, `teff_k`, `abs_mag_vis`, `lum`); returns `{"points": [{"label", "teff", "abs_mag", "bv", "lum", "color"}]}` (color by leading class letter) or `{"error"}` if the table is empty. `plot_helpers.py` — add `make_hr_canvas(parent, data, overlay_points=None)`: x = Teff in K, **log scale, inverted** (hot left); y = absolute visual magnitude, **inverted** (bright top); the main-sequence rows drawn as a connected line + labeled points (label every other row to avoid clutter); secondary top x-axis showing spectral class letters at their Teff positions. `MainSequencePanel` (12) gains `DiagramToggleMixin` + an **"HR Diagram"** viz tab.

**O2b — opts 18/19 result overlay.** Same canvas, second use: `prepare_hr_from_stars(result) -> dict` computes per-result-star `M_V = app_magnitude + 5 − 5·log₁₀(parsecs)` (requires the same row extension as O1) and a Teff estimate by matching the star's parsed spectral class against `main_sequence_stars` (`_lookup_spectral_type` ceiling rule from `core/regions.py` — already the app's canonical mapping). Result stars render as scatter points (`overlay_points`) on top of the O2a reference line. Stars missing magnitude or an OBAFGKM class are skipped and counted. Opts 18/19 gain an **"HR Diagram"** viz tab.

### O3: Mass–Radius Diagram (opts 3, 6, NasaPlanetarySystemsMapPanel)

**`core/viz.py`** — add `prepare_mass_radius(planets, mass_key, radius_key, name_key) -> dict`:
- Generic over sources: NASA pscomppars (`pl_bmasse`/`pl_rade`/`pl_name`) and HWC (`P_MASS`/`P_RADIUS`/`P_NAME`). Filters to planets with both values; returns `{"planets": [{"name", "mass_e", "radius_e"}], "skipped": int}` or `{"error"}` when none qualify.

**`plot_helpers.py`** — add `make_mass_radius_canvas(parent, data)`:
- log–log scatter, x = mass (M⊕) 0.05–4000, y = radius (R⊕) 0.3–25.
- **Constant-density reference curves** via `R = (M / (ρ/ρ⊕))^(1/3)` with `ρ⊕ = 5.51 g/cm³`: iron (7.9), rocky/Earth-like (5.51), water (1.0), plus a Jupiter-density line (1.33) — labeled along the curve, thin gray dashes. (Deliberately simple constant-density curves, not Zeng interior models — state this in the legend.)
- **Solar System reference points** (gray, small, labeled): Mercury (0.055, 0.383), Mars (0.107, 0.532), Venus (0.815, 0.95), Earth (1, 1), Uranus (14.5, 4.01), Neptune (17.1, 3.88), Saturn (95.2, 9.45), Jupiter (317.8, 11.21).
- System planets as colored labeled points; hover + click info.

**GUI** — viz tab **"Mass–Radius"** on `NasaPlanetarySystemsPanel` (3), `NasaPlanetarySystemsMapPanel`, and `HwcPanel` (6), added only when ≥ 1 planet qualifies.

### O4: Solar System Reference Overlay on Orbital Diagrams (opts 3, 6)

**`plot_helpers.py`** — `make_orbits_canvas()` gains an optional `solar_overlay: bool = False` parameter: when True, draws dashed gray circles at the `_PLANET_SMAS` values from `core/viz.py` (already defined at `core/viz.py:354`) for every planet whose SMA ≤ `max_au × 1.1`, each with a small end-of-orbit label (Mercury … Neptune). **GUI** — a "Show Solar System reference" `QCheckBox` placed above the Orbital Diagram canvas in opts 3 / Map panel / 6; toggling rebuilds the canvas (cheap — same data). Default unchecked so existing renders are unchanged.

### O5: Date Scrubber / Orbital Animation (Map panel; opts 22–23)

**`NasaPlanetarySystemsMapPanel`** — the System Map already resolves planet positions for any date by solving Kepler's equation **offline** (`prepare_exoplanet_system_diagram`); only the one-shot Search stands between it and animation.
- Add below the System Map canvas: a horizontal `QSlider` spanning `[map_date − span, map_date + span]` where `span = min(2 × longest pl_orbper, 50 yr)`, plus a date readout label and a **Play/Pause** `QPushButton`.
- On slider move (throttled with a 50 ms `QTimer`): recompute positions via `prepare_exoplanet_system_diagram(planets, date_iso)` and update only the planet marker offsets (`PathCollection.set_offsets`) + `canvas.draw_idle()` — orbits and star are static artists, never redrawn. Play steps the slider at ~10 fps with step = `longest_period / 200` days.
- `epoch_known=False` planets stay pinned at periastron with their open-ring overlay (already the convention) — the scrubber must not invent motion for them.

**Opts 22/23 Solar System Map (approximate mode)** — planet positions come from Horizons per epoch, so live scrubbing propagates **along the circular reference orbits** instead: from each planet's fetched position at the departure epoch, advance the angle by mean motion `n = 2π / P` with `P = a^1.5` years (Kepler's third law from `_PLANET_SMAS`). A persistent amber label **"approximate positions (propagated, not ephemeris)"** is shown whenever the slider is off the departure date. Origin/destination markers and the travel line stay fixed at their queried epochs. No new Horizons calls during scrubbing.

### O6: Diagram Parity for Opt 13 (Sol Regions)

`SolRegionsPanel` computes the same regions dict as opts 8–10 (`core.regions.compute_sol_regions()`, `core/regions.py:301` — same keys: `vmag`, `temp`, `calculatedLuminosity`, `distAU`, `hzil` … `phOuter`) but builds its seven tabs inline (`gui/panels/sol_regions.py:34`) and has **no diagrams**. Add `DiagramToggleMixin` + the same three viz tabs opts 9/10 get — **HZ Diagram**, **System Regions Diagram**, **Alternate HZ Diagram** — by passing the dict through the existing `prepare_system_regions_diagram` / `prepare_alt_hz_diagram` / `prepare_hz_diagram` pipeline. Note: opt 13 currently renders at construction time (`build_results_area` computes directly, no Run button); the mixin expects a render cycle — either give the panel a minimal "Show Diagrams" flow by calling `_setup_diagram_view()` + populating viz tabs in `build_results_area`, or refactor to the standard render pattern. Decide in implementation; behavior of the seven data tabs must not change.

### O7: Solar System Orbital Diagrams (opt 11)

Opt 11 displays full orbital elements (SMA, eccentricity, periastron/apastron, period for planets/dwarfs/asteroids; perigee/apogee/SMA-km for moons) as text only.

**`core/viz.py`** — add `prepare_solar_system_orbits(kind="planets") -> dict`: reads the relevant DB table via `core/science.py` accessors; `kind` ∈ `"planets"` (8 planets + optionally dwarfs), `"dwarfs+asteroids"`, or `"moons:<planet>"` (moon SMA-km → AU via `/ 1.496e8`). Returns the same `{"orbits", "max_au", "star_name"}` shape `make_orbits_canvas` already consumes (no HZ zones; `hz_zones=[]`), with each orbit dict carrying `sma`, `ecc`, `name`, color from `_PLANET_COLORS_VIZ` where known.

**GUI** — `SolarSystemPanel` (11) gains `DiagramToggleMixin` + two viz tabs: **"Orbital Diagram — Planets & Dwarfs"** and **"Moon Systems"** (a `QComboBox` of Earth/Mars/Jupiter/Saturn/Uranus/Neptune/Pluto above the canvas; switching rebuilds the canvas for that planet's moons, axis labeled in both AU and km).

### O8: Two-Star Map for Distance / Travel-Time Panels (opts 17, 20, 21)

`DistanceBetweenStarsPanel` (17) and the two `TravelTimeStars*` panels (20/21) compute both endpoints' 3D positions but render text only.

- **Shared infrastructure with Phase I**: Phase I's "Shared Visualization Infrastructure" adds an optional `routes` parameter to `make_star_map_canvas`/`make_star_map_3d_canvas`. O8 uses exactly that parameter — **whichever of Phase I / O8 is built first implements it; the other reuses it** (note this dependency in both phases' implementation order).
- **GUI** — all three panels gain `DiagramToggleMixin` + a **"Map"** viz tab: dark-navy star chart showing the two endpoint stars (+ Sol as a gray reference point when neither endpoint is Sol), connected by a dashed line labeled with the distance in ly (opts 20/21: distance + travel time, e.g. `"11.4 ly — 4 Months, 6 Days @ 100×c"`). View framed to fit both stars with 15% padding. Hover/click per the existing chart conventions.
- Data: endpoints already return `(name, ra_deg, dec_deg, ly)` from `_lookup_star_for_distance` — convert with the same Cartesian math used by opt 17's distance computation; no new lookups.

### O9: Brachistochrone Profile Charts (opts 22, 23, 24, 29, 30)

All brachistochrone results are tables only; the three acceleration profiles are ideal line-chart material and pure math.

**`core/viz.py`** — add `prepare_brachistochrone_profiles(result) -> dict`:
- Reconstructs each profile's piecewise `v(t)` / `d(t)` segments from `accel_g` + per-profile total time + profile type, using the exact formulas documented in `docs/calculators.md` (Profile 1: accel t/2 / decel t/2 — opt 24 variant: continuous accel for the whole window; Profile 2: accel t/4, coast t/2, decel t/4; Profile 3: accel to cap, coast, decel — opt 24 variant: accel to cap then coast, no decel; opt 23: accel `t_accel_eff`, coast, decel). Sample ~200 points per profile.
- Returns `{"profiles": [{"label", "color", "t_hours": [...], "v_kms": [...], "d_au": [...]}], "accel_g": float}` or `{"error"}`. Colors fixed per profile index so the chart matches across panels.

**`plot_helpers.py`** — add `make_profile_canvas(parent, data)`: two stacked subplots sharing the x-axis (time in hours) — top: velocity (km/s, secondary y-axis in %c), bottom: cumulative distance (AU, secondary y-axis in LM). One colored line per profile, legend with profile labels, light theme.

**GUI** — viz tab **"Acceleration Profiles"** via `DiagramToggleMixin` on `BrachistochroneAccelPanel` (24), `BrachistochroneAuPanel` (29), `BrachistochroneLmPanel` (30), and added to the existing viz tabs of `SystemTravelSolarPanel` (22) and `SystemTravelThrustPanel` (23) (opt 23 renders its single custom-thrust profile: accel/coast/decel segments from the phase durations already in its result).

### O10: Honorverse Visualization (opt 14 + hyper-limit ring on opts 8–10)

**O10a — opt 14 bar chart.** `HonorverseHyperPanel` gains `DiagramToggleMixin` + a **"Hyper Limits"** viz tab: horizontal bar chart of hyper limit per spectral class (rows in CSV order; x-axis in LM with a secondary AU axis via `/ 8.3167`), bars colored by leading class letter. Data is the already-loaded `honorverse_hyper` table — no new core function needed beyond a trivial `prepare_hyper_limits()` in `core/viz.py`.

**O10b — hyper-limit ring on the System Regions Diagram.** `prepare_system_regions_diagram(d)` gains an optional lookup: when `d` carries a `spectral_type` (opts 8/9 always do; opt 10 manual does not → ring omitted), parse it with the canonical `_parse_spectral_class` and resolve a hyper limit from the `honorverse_hyper` table using the same ceiling rule as the BC lookup (`_lookup_spectral_type` semantics); convert LM → AU (`/ 8.3167`) and append a region entry `{"label": "Honorverse Hyper Limit", "au": ..., "color": "#cc2222", "style": "dashed"}`. `make_system_regions_canvas` renders it as a distinct dashed red ring (clearly styled apart from the physical zones — it is fiction). No match in the table → silently omitted. Document in both `docs/star-system-regions.md` and `docs/science-and-scifi.md`.

### O11: Toomre / Galactic Kinematics Diagram (opts 1, 3–6, 8)

Hypatia `u_vel`/`v_vel`/`w_vel` and `disk` membership are fetched on every lookup and shown only as table numbers.

**`core/viz.py`** — add `prepare_toomre(hypatia_result) -> dict`: returns `{"v": v_vel, "uw": sqrt(u_vel² + w_vel²), "disk": str|None, "star_name": str}` or `{"error"}` when any of U/V/W is None.

**`plot_helpers.py`** — add `make_toomre_canvas(parent, data)`: x = V (km/s, range ≈ −400…+100), y = √(U²+W²) (0…400); dashed quarter-circles of constant total space velocity at 50, 100, and 180 km/s centered on the origin, with region annotations "thin disk" (< 50), "thick disk" (≈ 70–180), "halo" (> 180) — clearly labeled as heuristic boundaries; the star as a gold ★ with its name; subtitle shows Hypatia's own `disk` classification when present.

**GUI** — a **"Kinematics"** viz tab added wherever the Hypatia integration already adds the Abundance Profile tab (opts 1, 3–6, 8), shown only when U, V, and W are all non-null.

### O12: HWC Habitability Visuals (opt 6)

`P_FLUX_*`, `P_TEMP_EQUIL/SURF_MIN/MAX`, and `P_ESI` are tabled, never drawn. Two new `HwcPanel` viz tabs:

- **"Temperature Ranges"** — per planet, two horizontal range bars (equilibrium min→max and surface min→max, distinct colors) with a marker at the central value; x-axis in K with dashed reference lines at 273 K and 373 K (liquid-water band, labeled). `prepare_hwc_temps(planet_rows)` filters planets having at least one min/max pair.
- **"ESI vs Orbit"** — scatter of `P_SEMI_MAJOR_AXIS` (x, AU, log scale if span > 10×) vs `P_ESI` (y, 0–1); the star's HZ shaded as two vertical bands from `S_HZ_OPT_MIN/MAX` (light green) and `S_HZ_CON_MIN/MAX` (darker green); points colored by `P_HABITABLE` (green=1, gray=0) and labeled. `prepare_hwc_esi(star_row, planet_rows)`.

(Per-system visuals only — no overlap with Phase L2's cross-catalog ESI ranking *table*.)

### O13: Transit Geometry View (opts 3, NasaPlanetarySystemsMapPanel)

`pl_orbincl` is fetched and explicitly ignored by both orbit-prep functions (`core/viz.py` `prepare_system_orbits` and `prepare_exoplanet_system_diagram`). A full 3D orbit view would overreach (Ω is unmeasured for exoplanets), but **impact parameter** needs only inclination: `b = (a / R★) · cos(i)` with `a` in AU and `R★ = st_rad × 0.00465 AU`.

**`core/viz.py`** — add `prepare_transit_geometry(planets) -> dict`: requires `st_rad` and per-planet `pl_orbsmax` + `pl_orbincl`; returns `{"star_radius_au": float, "planets": [{"name", "a_au", "incl_deg", "b"}], "skipped": [names]}` or `{"error"}` when `st_rad` or all inclinations are missing.

**`plot_helpers.py`** — add `make_transit_canvas(parent, data)`: the stellar disk drawn to scale at the left (circle of radius 1 in units of R★), each planet as a labeled marker at `(x = a_au on a log axis, y = b)`, with the band `|b| ≤ 1` shaded and labeled "transiting"; mirrored y-axis (−3…+3 R★). A footnote lists skipped planets ("no inclination measured"). Caveat label: "geometry from i only; ascending node unknown".

**GUI** — viz tab **"Transit Geometry"** on opt 3 and the Map panel when ≥ 1 planet qualifies.

### O14: Planet Size-Comparison Strip (opts 3, 6, NasaPlanetarySystemsMapPanel)

**`plot_helpers.py`** — add `make_size_comparison_canvas(parent, planets, radius_key, name_key)`: a single row of to-scale circles — gray Earth (1 R⊕) and Jupiter (11.21 R⊕) silhouettes as anchors, then each system planet (radius from `pl_rade` / `P_RADIUS`) colored and labeled beneath with name + radius. Planets without a radius are listed in a footnote, not drawn. Equal-aspect axes, no ticks. **GUI** — viz tab **"Size Comparison"** on opts 3 / Map panel / 6 when ≥ 1 planet has a radius.

### O15: Table-Row ↔ Map Linking (opts 18, 19)

Confirmed absent: selecting a result row does nothing on the maps, and clicking a map star does not select its row.

- **`plot_helpers.py`** — each star-map/chart helper (`make_star_map_canvas`, `make_star_map_3d_canvas`, `make_star_chart_canvas`, `make_star_chart_3d_canvas`) attaches a `canvas.highlight_star(name: str | None)` function (attribute on the canvas object — **no signature changes**, so existing callers are untouched): draws/moves a single hollow gold ring marker (`facecolors="none"`, linewidth 2, ~3× point size) at the named star's coordinates, or removes it for `None`; calls `draw_idle()`. Each helper also gains an optional `on_star_click(name)` callback (default `None`, preserving the current inline info-box behavior when unset).
- **GUI** — opts 18/19: panels keep references to all created canvases; connect the result `QTableView`'s `selectionChanged` → resolve the row's `Star Name` → call `highlight_star(name)` on every canvas. Map click (via `on_star_click`) selects + scrolls to the matching table row. Selection must survive switching viz tabs.

### O16: Clickable Legend Filtering (opts 18, 19 maps and charts)

Spectral-class legends are currently display-only. In each star-map helper, draw the scatter **as one `PathCollection` per spectral class** (prerequisite for toggling; verify current single-vs-per-class structure during implementation), set `legend_handle.set_picker(5)` on each legend entry, and on `pick_event` toggle that class's collection visibility, dimming the legend text to alpha 0.3 when hidden. Per-star labels in the charts follow their star's visibility. Works in 2D and 3D variants.

### O17: Travel-Time Isochrone Rings (opts 18, 19 star charts)

The star charts draw distance rings at fixed ly steps. Add an **isochrone mode**: a velocity input (`QLineEdit` + unit `QComboBox` LY/HR | ×c) and Apply button above the chart; when set, rings are redrawn at distances `d = v_lyhr × t` for "nice" time steps chosen so 3–6 rings fit inside the limit (step ladder: 1 week, 1 month, 3 months, 6 months, 1 yr, 2 yr, 5 yr, 10 yr, 25 yr, 50 yr), each labeled `"6 months @ 0.01 ly/hr"`. Clearing the velocity restores the plain distance rings. Conversion uses the canonical `8765.8128` constant. Implemented as a parameter on `make_star_chart_canvas` / `make_star_chart_3d_canvas` (`isochrone: {"ly_hr": float, "label_unit": str} | None = None`) + panel-side rebuild on Apply.

### O18: Find-Star-on-Map Search Box (opts 18, 19)

A small `QLineEdit` + "Find" button above the chart tabs: case-insensitive substring match against `Star Name` and `Star Designations` of the rendered stars. On match: center the view on the star at a half-range of `min(current, 15)` ly (so labels become visible per the existing label-visibility rule), call `highlight_star(name)` (reuses O15's ring — **O18 depends on O15's highlight function**), and show `"1 of N matches"` when multiple match (Find again cycles). No match → status-bar message, no view change.

### Remaining Steps

- **`core/viz.py`** — add `prepare_sky_from_star`, `prepare_hr_main_sequence`, `prepare_hr_from_stars`, `prepare_mass_radius`, `prepare_solar_system_orbits`, `prepare_brachistochrone_profiles`, `prepare_hyper_limits`, `prepare_toomre`, `prepare_hwc_temps`, `prepare_hwc_esi`, `prepare_transit_geometry`; extend `prepare_system_regions_diagram` (O10b hyper ring)
- **`gui/visualizations/plot_helpers.py`** — add `make_sky_canvas`, `make_hr_canvas`, `make_mass_radius_canvas`, `make_profile_canvas`, `make_toomre_canvas`, `make_transit_canvas`, `make_size_comparison_canvas`; extend `make_orbits_canvas` (`solar_overlay`), star-map/chart helpers (`highlight_star`, `on_star_click`, per-class collections + legend picking, `isochrone` param)
- **`core/calculators.py`** — thread `app_magnitude` + `parsecs` through the opts 18/19 result rows (O1/O2b prerequisite; additive keys only)
- **Panels touched** — `MainSequencePanel` (12), `SolarSystemPanel` (11), `SolRegionsPanel` (13), `HonorverseHyperPanel` (14), `DistanceBetweenStarsPanel` (17), `TravelTimeStars*` (20/21), `Brachistochrone*` (24/29/30), `StarsWithinDistance*` (18/19), `SystemTravel*` (22/23), `NasaPlanetarySystems*` (3/Map), `NasaHwoExepPanel`/`NasaMissionExocatPanel` (O11 only), `HwcPanel` (6), `SimbadPanel` (1, O11), `StarRegions*` (8–10, O10b)
- **`mockups/phase-o/`** — one HTML mockup per item before its implementation (maintainer gate)
- **Docs** — `docs/gui-architecture.md` (new helpers + per-panel viz tab lists + the `highlight_star`/linking pattern), `docs/calculators.md` (O8/O9 tabs, row-key additions), `docs/star-system-regions.md` (O6, O10b), `docs/science-and-scifi.md` (O7, O10), `docs/star-databases.md` (O3/O12/O13/O14 tabs)
- **Cross-phase notes** — O8 shares the `routes` map parameter with Phase I (first builder implements); GCNS color–magnitude diagram and uncertainty visuals belong to Phase M, not O; multi-star abundance comparison belongs to L1

---

## Implementation Priority Recommendation

| Phase | Effort | Value | Recommendation |
|---|---|---|---|
| G — Data Filtering | Medium | High | **Do first** — unlocks the large datasets |
| H — Worldbuilding Calcs | Medium | High | **Do second** — pure math, no network, clean additions |
| I — Route Planning | Medium | Medium | Good sci-fi worldbuilding value |
| J — User Preferences | Medium | Medium | Quality-of-life; grows more valuable as feature count grows |
| K — Honorverse Expansion | Low | Medium | Narrow audience but fast to implement |
| L1–L3 — Comparison Dashboard | Medium | Medium | Independent of G — L1 uses live SIMBAD+Hypatia, L2 reads the `hwc` table, L3 is pure math. (L1 *benefits* from L4's cache for offline comparison.) |
| L4 — Hypatia Cache & Search | Medium | Medium | Do after G1 to activate the Fe/H filter stretch goal; needed before L1 for offline comparison |
| M — GCNS Surfacing | Low | High | Low effort (reuses `compute_gcns_*` verbatim), high visibility — surfaces the only dataset with distance uncertainties |
| N — query.py Expansion | Low | Medium | Anytime — no dependencies on G–M; pure integration-surface work over existing core functions |
| O — Visualization Expansion | Varies (per-item S–M) | High | Mockup-gated, individually skippable items; small items (O4, O6, O9, O10, O14) are quick wins; O1/O5 carry the most wow. O8 shares the `routes` param with Phase I |
| **M — GCNS Surfacing** | **Low–Medium** | **High** | **Strong candidate to do early** — data is already ingested; reuses `compute_gcns_*` verbatim, so it's mostly UI. Surfaces the only major dataset with no interactive surface, and the only one with distance uncertainties. |
