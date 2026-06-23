# Equations Feature Documentation

Options 33–41. Planetary equations, rotating habitat equations, and miscellaneous equations. Pure math with no external API dependencies — the most stable feature group.

> **`query.py`:** options 33–38 are also exposed as subcommands — `orbit-distance` (33), `moon-orbital-distance` (34/35), and `gravity-acceleration` / `gravity-distance` / `gravity-rpm` (36/37/38); options 39–41 as `habitable-zone` / `habitable-zone-sma` / `star-luminosity`. These wrap the **non-self-validating** functions below (out-of-range input → raw-exception exit 1 or nonsense exit 0; argparse exit 2 for bad args). See `docs/integration.md`.

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

### H3: `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0, moon_inclination_deg=0, prograde=True)`
Gravitational sphere of influence of a planet; stable satellite orbits exist within ~0.5 × Hill radius.
- Validate `star_mass_solar > 0`, `planet_mass_earth > 0`, `sma_au > 0`, `0 ≤ e < 1`, and (Phase T1a) `0 ≤ moon_inclination_deg ≤ 180`.
- `r_H_m = a_m × (1 − e) × (M_p / (3 × M_star))^(1/3)`; `stable_limit = 0.5 × r_H`. Both reported in km and AU.
- Returns `{star_mass_solar, planet_mass_earth, sma_au, eccentricity, moon_inclination_deg, prograde, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au, stable_fraction, stable_moon_limit_km, stable_moon_limit_au}`.
- **Anchor:** Earth (1 M☉, 1 M⊕, 1 AU, e=0) → hill_radius ≈ 1,496,000 km (0.0100 AU), stable ≈ 748,000 km.
- **Phase T1a — Domingos 2006 exomoon keys (B3, additive).** The crude `stable_orbit_limit_*` (0.5 × r_H heuristic) is **retained** but superseded by the largest-stable-satellite-orbit fit of Domingos, Winter & Yokoyama (2006, MNRAS 373, 1227): `stable_moon_limit = f × r_Hill`, where the **prograde** factor `f = 0.4895·(1 − 1.0305·e_p − 0.2738·i_sat)` and the **retrograde** factor `f = 0.9309·(1 − 1.0764·e_p − 0.9812·i_sat)` (the retrograde e/i coefficients are pinned against the paper). `e_p` is the planet's eccentricity; the satellite inclination `i_sat` is taken in **degrees on input, radians internally**. New keys: `stable_fraction` (= `f`), `stable_moon_limit_au` (headline) and `stable_moon_limit_km`. The two new inputs `moon_inclination_deg` (default 0) and `prograde` (default True) are **additive/defaulted** — with both omitted, all pre-existing keys/values are byte-identical to before. **Anchor:** e=0, i=0, prograde → `stable_fraction = 0.4895`; retrograde → `0.9309`; i=45° prograde → ≈ 0.3843.

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

## Stellar Evolution Timeline (Phase L3)

`compute_stellar_evolution(mass_solar, current_age_gyr=None)` in `core/equations.py` — evolutionary-stage durations and timeline for a star, backing the GUI `StellarEvolutionPanel` (Comparison nav) and the `stellar-evolution` `query.py` subcommand. **Self-validating** (like the Phase H calculators): a mass outside `0.1 ≤ mass_solar ≤ 20 M☉` returns `{"error": str}` rather than extrapolating; `current_age_gyr` may be `< 0` → error, or exceed the total lifetime (`current_stage="Beyond AGB"`, not an error).

- `T_ms = 10¹⁰ × (1/mass_solar)^2.5` years (same relation as `core/regions.py` `mainSeqLifeSpan`), reported in Gyr. Module constant `_EVOLUTION_STAGES` holds the six `(name, fraction_of_T_ms, color)` rows: Pre-Main Sequence 0.01, Main Sequence 1.00, Subgiant 0.15, Red Giant Branch 0.10, Horizontal Branch 0.10, Asymptotic Giant Branch 0.02.
- Stages are emitted with contiguous `start_gyr`/`end_gyr`/`duration_gyr`; `current_stage` is the stage containing `current_age_gyr`.
- **Special cases (values, not errors):** `mass < 0.8 M☉` → `low_mass=True`, only Pre-MS + MS emitted (MS lifetime exceeds a Hubble time; the GUI/diagram render MS as "> 13.8 Gyr"). `mass > 8 M☉` → `high_mass=True`, the AGB stage is replaced by `"Supergiant → Supernova"` (color `#7a0000`).
- Returns `{mass_solar, stages:[{name, start_gyr, end_gyr, duration_gyr, color}], total_gyr, ms_end_gyr, current_age_gyr, current_stage, low_mass, high_mass}`.
- **Anchor:** 1 M☉ → `T_ms = 10 Gyr`, `ms_end_gyr ≈ 10.1 Gyr` (after the 0.01·T_ms Pre-MS), six stages, `total_gyr ≈ 13.8 Gyr`.
- Viz: `core.viz.prepare_evolution_diagram(result)` → `{stages, current_age_gyr, x_max_gyr, …}`; `gui/visualizations/plot_helpers.make_evolution_canvas(parent, data)` renders the horizontal stacked-bar timeline with a dashed current-age marker.

## Solvent Zones & Ice Lines (Phase P)

Two self-validating pure-math calculators in `core/equations.py` backing the GUI
**Worldbuilding** panels `SolventZonePanel` (Solvent Habitable Zone), `IceLineCalculatorPanel`
(Ice Line Calculator), and `SolventReferencePanel` (static reference table), plus the
`solvent-zone` / `ice-lines` `query.py` subcommands (see `docs/integration.md`). They also
ground the corrected/extended **Alternate Habitable Zone Regions** output of opts 8–10/13
(see `docs/star-system-regions.md`). No network, no DB.

### Two temperature models (M1 / M2)

Phase P uses two physically-distinct reference temperatures, centralized as helpers so the
calculators can't drift (the model fix replaces the legacy linear `(1−A)` albedo term with
the correct fourth-root `(1−A)^0.25`):

- **`_t_ref_surface(albedo=0.3)` — M1 surface model** `T_ref = 314.9 × (1−A)^0.25` (= 288.0 K
  at A=0.3, the existing alt-HZ convention). Equilibrium **+ Earth-like greenhouse**; used for
  whether a solvent is **liquid on a surface** (habitability).
- **`_t_ref_equilibrium(albedo=0.0)` — M2 equilibrium model** `T_ref = 278.5 × (1−A)^0.25`
  (278.5 K at A=0). Bare radiative equilibrium, **no greenhouse**; used for **ice/snow
  condensation** (vacuum / thin disk gas).

Shared scaling: `S_eff(T) = (T / T_ref)^4`; `AU(S_eff, L) = sqrt(L / S_eff)`. The
**P7a implied-edge-temperature** helper `implied_edge_temp(au, luminosity_solar, model)` inverts
this (`T = T_ref × (L/au²)^0.25`) to annotate each region row with its band-edge temperature.

### Built-in solvent table — `_SOLVENTS` / `get_solvents()`

The single source of truth shared by P4/P5/P6: one entry per solvent — `{key, name, t_low_k
(freeze), t_high_k (boil), pressure_conditional, assumed_pressure_atm, citation, plausibility}`.
13 solvents: water, ammonia, methane, ethane, water_ammonia (eutectic), so2, co2 (pressure-
conditional, ≥5.2 atm), sulfuric_acid, sulfur, hydrogen (13.8/20.3 K — **not** the legacy 64 K),
nitrogen, hf, formamide. Edge temps are 1-atm liquid ranges (CRC; Asimov 1962; Bains 2024;
Gillett), confirmed at build time.

### `compute_solvent_zone(luminosity_solar, solvent=None, t_low_k=None, t_high_k=None, albedo=0.3)`

The AU band where a solvent is liquid on a surface (**M1**). Named solvent **or** custom
`t_low_k`/`t_high_k` (explicit temps take precedence). Inner edge = boiling point (closer in),
outer = freezing point. `s_eff_inner = (t_high_k / T_ref)^4`, `s_eff_outer = (t_low_k / T_ref)^4`;
`inner_au = sqrt(L / s_eff_inner)`, etc. Self-validates: `luminosity_solar > 0`, `0 ≤ albedo < 1`,
`0 < t_low_k < t_high_k`, named `solvent ∈ _SOLVENTS`. At A=0.3 reproduces the legacy alt-HZ
divisors (water 2.8/0.8 → 373/273 K, ammonia 0.48/0.21, methane 0.023/0.0094). Returns
`{solvent, name, t_low_k, t_high_k, albedo, t_ref_k, luminosity_solar, inner_au, outer_au,
inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional,
assumed_pressure_atm, citation}` (`t_eq_*` round-trip the edge temps).
- **Anchors:** water (L=1, A=0.3) → 0.596/1.112 AU; hydrogen → ~202/436 AU (the corrected band,
  `s_eff` = the P1a divisors 0.0000247/0.0000053); co2 → `pressure_conditional=True`, 5.2 atm.
- **Viz:** `core.viz.prepare_solvent_ranges()` → `make_solvent_bar_canvas` (V5 liquid-range bars,
  coloured by Bains-2024 plausibility); `make_solvent_zone_canvas` (V3 auto-fit ⁴√AU ring with a
  water reference + hover).

### `compute_ice_lines(luminosity_solar, albedo=0.0)`

The single canonical water snow line (170 K — no dual/formation line) plus the CO₂/NH₃/N₂/CO
condensation fronts (**M2**). `AU = sqrt(L) × (T_ref / T_cond)²`. Self-validates
(`luminosity_solar > 0`, `0 ≤ albedo < 1`). Returns `{luminosity_solar, albedo, t_ref_k,
lines:[{species, t_cond_k, au, lm, kind ("snow_line"|"front"), disk_line, note}]}` (hot→cold =
inner→outer). The deep-cold N₂/CO fronts carry `disk_line=True` (disk-midplane-set; ~160–194 AU
placement illustrative).
- **Anchors:** L=1, A=0 → `t_ref_k ≈ 278.5`; water snow line **2.68 AU** (170 K; Hayashi 1981);
  CO₂ ≈ 15.8 AU, NH₃ ≈ 12.1 AU.
- **Viz:** `core.viz.prepare_ice_line_diagram(result)` → `make_ice_line_canvas` (V4 frost-line ring,
  inner-focus ≤ 18 AU + Full-range toggle + hover); `prepare_orbit_overlays(L)` feeds the V6
  snow-line ring + V7 solvent-zone overlays (all default-off) on the opt-3/6/Map orbital diagrams.

## Research-Tooling Calculators (Phase T1a)

Two new self-validating pure-math calculators (Phase-H/P contract: curated `{"error"}` for
out-of-range) added for the sibling worldbuilding repo's `query.py` consumer. Backed by
`compute_circumbinary_hz` (`core/equations.py`) and `compute_lorentz_factor` (`core/calculators.py`,
documented here with its calculator siblings). The third Phase-T1a "calculator" — the Domingos 2006
exomoon keys — is folded into **H3 `compute_hill_sphere`** above, not a separate function. The
`trojan-stability` subcommand is a thin wrapper over the existing R2 `core/feasibility.gascheau_coorbital_stable`
(no new math). See `docs/integration.md` for the `query.py` contract.

### `compute_circumbinary_hz(teff1, lum1, teff2, lum2)` (C1)

Circumbinary (P-type) habitable zone from the **combined** light of a close binary. For a
circumbinary planet the binary separation ≪ the planet's orbit, so the pair acts as one point
source of luminosity `L_tot = L₁ + L₂`. The Kopparapu S_eff coefficients need one effective
temperature; the **luminosity/flux-weighted** convention is used:
`eff_teff = (L₁·T₁ + L₂·T₂)/(L₁+L₂)` (collapses to the brighter star as the other's L → 0). The six
zone boundaries are then `compute_habitable_zone(eff_teff, L_tot)`.
- **Out-of-range Teff — flag, don't clamp.** The Kopparapu polynomial is only valid ~2600–7200 K; a
  binary's combined Teff trips this far more often than a single star. When `eff_teff` is outside
  `[2600, 7200]` K, the result sets `out_of_range_teff = True` and echoes `eff_teff` but **still
  returns the zones** (more conservative than single-star `habitable-zone`'s silent extrapolation).
- **Validation (self-validating):** all four inputs `> 0` else `{"error": str}`.
- Returns `{teff1, lum1, teff2, lum2, combined_lum, eff_teff, out_of_range_teff, zones}` — `zones` is
  the same 6-dict list (`zone_name, key, au, lm, seff`) as `compute_habitable_zone`.
- **Anchors:** equal Sun-like stars (5778 K, L=1 each) → `eff_teff = 5778 K`, `combined_lum = 2`,
  `out_of_range_teff = False`; two 2400 K stars → `eff_teff = 2400 K`, `out_of_range_teff = True`
  (still 6 zones returned).

### `compute_lorentz_factor(velocity_c)` (D2)

Special-relativistic Lorentz / time-dilation factor for a **sublight** velocity (lives with the
velocity converters in `core/calculators.py`). `γ = 1/√(1 − β²)`, `time_dilation_pct = (γ − 1)·100`.
- **Deliberately distinct** from the FTL-arithmetic converters (`compute_ly_hr_to_times_c` /
  `compute_speed_of_light_to_ly_hr`), which treat "× c" as a plain multiplier with **no** relativistic
  interpretation. This one is relativistic and rejects β ≥ 1.
- **Validation (self-validating):** `0 ≤ velocity_c < 1` else
  `{"error": "Velocity must be in the range 0 ≤ β < 1 (sublight)."}`.
- Returns `{velocity_c, lorentz_factor, time_dilation_pct}`.
- **Anchors:** β=0 → γ=1; β=0.6 → γ=1.25 (25% dilation); β→0.999 → γ≈22.37.

### `compute_tidal_heating(primary_mass_earth, satellite_radius_km, sma_km, ecc, k2=0.3, tidal_q=100)` (B1)

Tidal heating power + surface flux of a **synchronously rotating** satellite on an eccentric orbit
(Phase T1b). **`Ė = (21/2)·(G·k₂·M_p²·R_s⁵·n·e²)/(Q·a⁶)`** — the leading **`21/2`** is the Peale &
Cassen (1978) constant, verified against Heller & Barnes 2013 (arXiv:1209.5323) / Henning et al. 2009;
mean motion `n = √(G·M_p/a³)`. Surface flux `= Ė/(4πR_s²)` W/m²; `io_flux_ratio = surface_flux / 2.0`
(Io's globally-averaged heat flux ≈ 2 W/m²).
- **Order-of-magnitude** (fixed-Q, homogeneous body, small-e expansion) — labelled as such; a scale
  estimate, not a precise dissipation prediction.
- **Validation (self-validating):** `primary_mass_earth>0`, `satellite_radius_km>0`, `sma_km>0`,
  `0≤e<1`, `k2>0`, `tidal_q>0`.
- Returns `{heating_power_w, surface_flux_wm2, mean_motion_rad_s, io_flux_ratio, primary_mass_earth,
  satellite_radius_km, sma_km, ecc, k2, tidal_q}`.
- **Anchor:** Io-like (M_p=317.8 M⊕, R_s=1821 km, a=421 700 km, e=0.0041, k₂=0.3, Q=100) →
  `mean_motion_rad_s ≈ 4.1e-5`, `io_flux_ratio` O(1) (within an order of Io — Io's real k₂≈0.03 ≪ 0.3).

### `compute_kozai_lidov(m1_solar, m2_solar, m3_solar, period_inner_yr=None, period_outer_yr=None, sma_inner_au=None, sma_outer_au=None, ecc_outer=0)` (C2)

Kozai–Lidov (von Zeipel–Lidov–Kozai) oscillation timescale for a hierarchical triple (Phase T1b).
**`T_KL = (8/15π)·((M₁+M₂+M₃)/M₃)·(P_out²/P_in)·(1−e_out²)^{3/2}`** years — the leading **`8/15π`**
(≈0.16977) is verified against Antognini 2015 (MNRAS 452, 3610, Eq. 42); the general-triple mass factor
`(M₁+M₂+M₃)/M₃` (M₃ = outer/tertiary perturber, **denominator**) is the Kiseleva et al. 1998 form. Supply
either both periods (yr) or both SMAs (AU) — `P_in=√(a_in³/(M₁+M₂))`, `P_out=√(a_out³/(M₁+M₂+M₃))`.
- **Order-of-magnitude** (the exact KL period varies within "a factor of a few" of this; Antognini 2015) —
  labelled as such.
- **Validation (self-validating):** masses `>0`, `0≤e_out<1`; exactly one complete period **or** SMA pair
  (partial/both → `{"error"}`).
- Returns `{timescale_years, m1_solar, m2_solar, m3_solar, period_inner_yr, period_outer_yr, ecc_outer}`.
- **Anchor:** M₁=M₂=M₃=1 M☉, P_in=1 yr, P_out=100 yr, e_out=0 → `T_KL = (8/15π)·3·(100²/1) ≈ 5093 yr`.
