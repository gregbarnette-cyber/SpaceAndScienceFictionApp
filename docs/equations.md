# Equations Feature Documentation

Options 33–41. Planetary equations, rotating habitat equations, and miscellaneous equations. Pure math with no external API dependencies — the most stable feature group.

## Planetary Equations

### Option 33: Planetary Orbit Periastron & Apastron Distance Calculator — `planetary_orbit_periastron_apastron()`
- Prompts: `Enter the Planetary Semi-Major Axis (AU)` (> 0), `Enter the Planetary Orbit Eccentricity` (0 ≤ e < 1).
- Calculates:
  - `periastron = sma × (1 - e)`
  - `apastron = sma × (1 + e)`
  - `ecc_au = sma × e`
- Screen cleared after all inputs, before output.
- Output table columns: Periastron (AU) | Semi-Major Axis (AU) | Apastron (AU) | Eccentricity | Eccentricity (AU); all 6dp.

### Option 34: Orbital Distance of an Earth-sized Moon with a 24 hour day — `moon_orbital_distance_24h()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0).
- Uses Kepler's third law: `r = (G × M_planet × T² / (4π²))^(1/3)` where `T = 86400 s`, `EARTH_MASS_KG = 5.972e24`, `G = 6.674e-11`.
- Converts result to km.
- Screen cleared after input, before output.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (fixed "24.0000") | Orbital Distance (km) (4dp).

### Option 35: Orbital Distance of an Earth-sized Moon with a X hour day — `moon_orbital_distance_x_hours()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0), `Enter Day in Hours` (> 0).
- Same Kepler's third law as option 34 but `T = day_hours × 3600 s`.
- Screen cleared after all inputs, before output.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (4dp) | Orbital Distance (km) (4dp).

## Rotating Habitat Equations

### Option 36: Centrifugal Artificial Gravity Acceleration at Point X (m/s^2) — `centrifugal_gravity_acceleration()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Distance (m) from Point X to Center of Rotation` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `a = omega² × r`.
- Screen cleared after all inputs, before output.
- Output table columns: Rotation Rate (rpm) (4dp) | Distance from Center (m) (4dp) | Centrifugal Gravity (m/s^2) (2dp).

### Option 37: Distance from Point X to the Center of Rotation (m) — `centrifugal_gravity_distance()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `r = a / omega²`.
- Screen cleared after all inputs, before output.
- Output table columns: Rotation Rate (rpm) (4dp) | Centrifugal Gravity (m/s^2) (4dp) | Distance from Center (m) (2dp).

### Option 38: Rotation Rate at Point X (rpm) — `centrifugal_gravity_rpm()`
- Prompts: `Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X` (> 0), `Enter Distance (m) from Point X to Center of Rotation` (> 0).
- Calculates: `omega = sqrt(a / r)`, `rpm = omega × 60 / (2π)`.
- Screen cleared after all inputs, before output.
- Output table columns: Centrifugal Gravity (m/s^2) (4dp) | Distance from Center (m) (4dp) | Rotation Rate (rpm) (2dp).

## Misc. Equations

### Shared helper: `_kopparapu_seff(teff, zone)`
- Returns Kopparapu et al. 2014 Seff boundary for six zone keys: `rv`, `rg5`, `rg01`, `rg`, `mg`, `em`.
- Formula: `Seff = SeffSUN + a×tS + b×tS² + c×tS³ + d×tS⁴` where `tS = teff - 5780`.
- Used by both `habitable_zone_calculator()` and `habitable_zone_calculator_sma()`.
- Note: shares the same Kopparapu et al. coefficient table used by `_display_habitable_zone()` in `docs/star-databases.md`, but is a separate standalone function for menu-driven calculator use.

### Option 39: Habitable Zone Calculator — `habitable_zone_calculator()`
- Prompts: `Enter the Star's Temperature (K)` (> 0), `Enter the Star's Luminosity (Lsun)` (> 0).
- Computes HZ boundary distances: `au = sqrt(luminosity / Seff)` for each of the six Kopparapu zones.
- Screen cleared after all inputs, before output.
- Output: "Calculated Habitable Zone" table with Zone | AU columns; AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`.
- Zone order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (RG 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (RG 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars).

### Option 40: Habitable Zone Calculator w/SMA — `habitable_zone_calculator_sma()`
- Prompts: `Enter the Star's Temperature (K)` (> 0), `Enter the Star's Luminosity (Lsun)` (> 0), `Enter the Object's Semi-Major Axis (AU)` (> 0).
- Computes planet's Seff: `planet_seff = (1 / sma)² × luminosity`.
- Screen cleared after all inputs, before output.
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
- Screen cleared after all inputs, before output.
- Output table columns: Radius (R☉) (4dp) | Temperature (K) (4dp) | Luminosity (Lsun) (6dp).

## Worldbuilding Calculators (Phase H)

Five pure-math calculators in `core/equations.py` for authors/worldbuilders. **GUI-only** (panels in `gui/panels/worldbuilding.py` under the "Worldbuilding" nav category) plus a `query.py` subcommand each (see `docs/integration.md`). No network, no CSV, no DB. **Unlike the older equation functions, these self-validate physical ranges and return `{"error": str}` for bad input** (≤ 0 where a positive is required, `e ∉ [0,1)`) — the same `{"error"}` contract used by the search functions, so both the GUI red-error label and the `query.py` exit-1 path work.

### Shared constants block + helper

A module-level constants block at the top of `core/equations.py` (so H1–H5 don't re-declare and drift): `_G = 6.674e-11`, `_K_B = 1.380649e-23`, `_EARTH_MASS_KG = 5.972e24`, `_EARTH_RADIUS_KM = 6371.0`, `_EARTH_RADIUS_M = 6.371e6`, `_SOLAR_MASS_KG = 1.989e30`, `_M_PER_AU = 149597870700.0`, `_KM_PER_AU = 149597870.7`, `_AMU_KG = 1.66054e-27`, `_SEC_PER_YEAR = 3.15576e7` (Julian year). The older functions keep their own inline constants (out of scope).

`_rocky_radius_km(mass_earth) -> float` — approximate rocky-body radius from mass (`R = _EARTH_RADIUS_KM × mass_earth^0.55`); shared by H1 and H2.

> **Two formula corrections vs. the `future_phases.md` brainstorm** (both verified numerically): (H1) the rigid Roche coefficient is **1.26** (= 2^(1/3)), **not 2.44** — 2.44 makes rigid ≈ fluid, which is physically meaningless. (H4) the P-type mass-ratio term is **`+4.12μ`**, **not `−4.12μ`** — the negative sign drives the critical SMA negative for an equal-mass circular binary.

### H1: `compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None)`
Rigid-body and fluid Roche limits for a satellite orbiting a primary (planet-moon or star-planet).
- Validate: `primary_mass_earth > 0`, `satellite_density_gcc > 0`, and (if supplied) `primary_radius_earth > 0`.
- `R_km` = `primary_radius_earth × _EARTH_RADIUS_KM` if supplied, else `_rocky_radius_km(primary_mass_earth)`; `R_m = R_km × 1000`.
- `ρ_primary_gcc = (3 × M_kg / (4π R_m³)) / 1000`; `ratio = (ρ_primary_gcc / satellite_density_gcc)^(1/3)`.
- **`rigid_km = R_km × 1.26 × ratio`**; `fluid_km = R_km × 2.456 × ratio`; `*_au = *_km / _KM_PER_AU`.
- Returns `{primary_mass_earth, primary_radius_km, primary_density_gcc, satellite_density_gcc, rigid_km, rigid_au, fluid_km, fluid_au}`.
- **Anchor:** Earth (ρ≈5.51) + 3.34 g/cm³ satellite → rigid ≈ 9,487 km, fluid ≈ 18,492 km.

### H2: `compute_tidal_locking_time(primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa=3e10, tidal_q=100)`
Tidal-locking timescale of a satellite (MacDonald 1964 torque model).
- Validate all four primaries `> 0`; `rigidity_pa > 0`, `tidal_q > 0`.
- `ω₀ = 2π/(initial_rotation_hours × 3600)`; `a_m = sma_km × 1000`; `R_sat_m = _rocky_radius_km(satellite_mass_earth) × 1000`.
- `I = 0.4 × M_sat × R_sat_m²` (uniform sphere); `k₂ = 0.3` (rocky-body approximation).
- `T_sec = (ω₀ × a_m⁶ × I × tidal_q) / (3 × _G × M_pri² × k₂ × R_sat_m⁵)`; `years = T_sec / _SEC_PER_YEAR`; `gyr = years / 1e9`.
- Returns `{primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa, tidal_q, satellite_radius_km, lock_time_years, lock_time_gyr}`.
- **Model limitation:** `rigidity_pa` is accepted and echoed for transparency, but `k₂` is fixed at 0.3 (the MacDonald rocky-body simplification) — an order-of-magnitude estimate, reserved for a future Love-number refinement. The `a⁶` dependence means doubling `sma_km` multiplies the lock time by ≈ 64.

### H3: `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0)`
Gravitational sphere of influence of a planet; stable satellite orbits exist within ~0.5 × Hill radius.
- Validate `star_mass_solar > 0`, `planet_mass_earth > 0`, `sma_au > 0`, `0 ≤ e < 1`.
- `r_H_m = a_m × (1 − e) × (M_p / (3 × M_star))^(1/3)`; `stable_limit = 0.5 × r_H`. Both reported in km and AU.
- Returns `{star_mass_solar, planet_mass_earth, sma_au, eccentricity, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au}`.
- **Anchor:** Earth (1 M☉, 1 M⊕, 1 AU, e=0) → hill_radius ≈ 1,496,000 km (0.0100 AU), stable ≈ 748,000 km.

### H4: `compute_binary_orbit_stability(mass1_solar, mass2_solar, binary_sma_au, test_sma_au, eccentricity=0)`
Planet orbit stability in a binary (Holman & Wiegert 1999 empirical fit). S-type = planet orbits one star; P-type = circumbinary.
- Validate masses `> 0`, `binary_sma_au > 0`, `test_sma_au > 0`, `0 ≤ e < 1`. Masses ordered so `M1 ≥ M2`; `μ = M2/(M1+M2)` (≤ 0.5).
- `a_c_stype = (0.464 − 0.380μ − 0.631e + 0.586μe + 0.150e² − 0.198μe²) × binary_sma_au`.
- **`a_c_ptype = (1.60 + 5.10e − 2.22e² + 4.12μ − 4.27eμ − 5.09μ² + 4.61e²μ²) × binary_sma_au`**.
- `orbit_type = "S-type"` if `test_sma_au < binary_sma_au/2` else `"P-type"` (heuristic). `is_stable`: S-type → `test_sma_au < a_c_stype`; P-type → `test_sma_au > a_c_ptype`.
- Returns `{mass1_solar, mass2_solar, mass_ratio, binary_sma_au, eccentricity, stype_critical_sma_au, ptype_critical_sma_au, test_sma_au, orbit_type, is_stable, stable_region_description}`.
- **Anchor:** μ=0.5, e=0 → `a_c_stype ≈ 0.274 × a_b`, `a_c_ptype ≈ 2.388 × a_b`.

### H5: `compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k)`
Which atmospheric gases a planet retains against Jeans escape.
- Validate all `> 0`. `v_escape_kms = sqrt(2 × _G × M / R) / 1000`.
- Gases (amu): H₂ 2, He 4, CH₄ 16, H₂O 18, N₂ 28, O₂ 32, CO₂ 44. Per gas: `λ = (_G × M × m) / (_K_B × T × R)`; `v_thermal_kms = sqrt(2 × _K_B × T / m) / 1000`; status `λ > 6` → "Retained", `3 < λ ≤ 6` → "Escaping slowly", `λ ≤ 3` → "Lost rapidly".
- Returns `{planet_mass_earth, planet_radius_earth, temperature_k, v_escape_kms, gases:[{gas, mol_mass_amu, lambda, v_thermal_kms, status}]}`.
- **Model limitation:** uses the planet's *equilibrium* temperature, which underestimates exospheric temperature, so the simplified Jeans model is **optimistic about retention** — a worldbuilding heuristic, not an exospheric-escape simulation. `λ` scales linearly with molecular mass (`λ_CO2 = 22 × λ_H2`).
- **Anchor:** Earth (1 M⊕, 1 R⊕, 255 K) → v_escape ≈ 11.19 km/s.

### GUI panels (`gui/panels/worldbuilding.py`)
All five inherit `ResultPanel` directly (no `DiagramToggleMixin` — no visualizations), following the `LuminosityPanel` pure-math pattern (`QFormLayout` of `QLineEdit`s + Calculate button, hidden red `_err` label, a `_result_container` rebuilt on each calc). A shared `_WorldbuildingPanel` scaffold factors the form/button/error/clear logic and a `_read_float` helper. `RocheLimitPanel`'s radius and the optional eccentricity / advanced fields default when left blank. `BinaryOrbitPanel` shows a green/red **Stable/Unstable** verdict label above the table plus the description line below it; `AtmosphereRetentionPanel` color-codes each gas's Status cell (green Retained / amber Escaping slowly / red Lost rapidly) and prints the escape velocity in a label above the table. `TidalLockingPanel` puts rigidity + Q in a collapsible "Advanced Parameters" `QGroupBox` pre-filled with `3e10` / `100`.
