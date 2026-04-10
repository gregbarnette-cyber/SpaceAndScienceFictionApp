# Equations Feature Documentation

Options 34–42. Planetary equations, rotating habitat equations, and miscellaneous equations. Pure math with no external API dependencies — the most stable feature group.

## Planetary Equations

### Option 34: Planetary Orbit Periastron & Apastron Distance Calculator — `planetary_orbit_periastron_apastron()`
- Prompts: `Enter the Planetary Semi-Major Axis (AU)` (> 0), `Enter the Planetary Orbit Eccentricity` (0 ≤ e < 1).
- Calculates:
  - `periastron = sma × (1 - e)`
  - `apastron = sma × (1 + e)`
  - `ecc_au = sma × e`
- Screen cleared after all inputs, before output.
- Output table columns: Periastron (AU) | Semi-Major Axis (AU) | Apastron (AU) | Eccentricity | Eccentricity (AU); all 6dp.

### Option 35: Orbital Distance of an Earth-sized Moon with a 24 hour day — `moon_orbital_distance_24h()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0).
- Uses Kepler's third law: `r = (G × M_planet × T² / (4π²))^(1/3)` where `T = 86400 s`, `EARTH_MASS_KG = 5.972e24`, `G = 6.674e-11`.
- Converts result to km.
- Screen cleared after input, before output.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (fixed "24.0000") | Orbital Distance (km) (4dp).

### Option 36: Orbital Distance of an Earth-sized Moon with a X hour day — `moon_orbital_distance_x_hours()`
- Prompts: `Enter Planetary Mass in Earth Masses` (> 0), `Enter Day in Hours` (> 0).
- Same Kepler's third law as option 35 but `T = day_hours × 3600 s`.
- Screen cleared after all inputs, before output.
- Output table columns: Planetary Mass (Earth Masses) (4dp) | Day Length (Hours) (4dp) | Orbital Distance (km) (4dp).

## Rotating Habitat Equations

### Option 37: Centrifugal Artificial Gravity Acceleration at Point X (m/s^2) — `centrifugal_gravity_acceleration()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Distance (m) from Point X to Center of Rotation` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `a = omega² × r`.
- Screen cleared after all inputs, before output.
- Output table columns: Rotation Rate (rpm) (4dp) | Distance from Center (m) (4dp) | Centrifugal Gravity (m/s^2) (2dp).

### Option 38: Distance from Point X to the Center of Rotation (m) — `centrifugal_gravity_distance()`
- Prompts: `Enter Rotation Rate (rpm)` (> 0), `Enter Centrifugal Artificial Gravity Acceleration (m/s^2) at Point X` (> 0).
- Calculates: `omega = rpm × 2π / 60`, `r = a / omega²`.
- Screen cleared after all inputs, before output.
- Output table columns: Rotation Rate (rpm) (4dp) | Centrifugal Gravity (m/s^2) (4dp) | Distance from Center (m) (2dp).

### Option 39: Rotation Rate at Point X (rpm) — `centrifugal_gravity_rpm()`
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

### Option 40: Habitable Zone Calculator — `habitable_zone_calculator()`
- Prompts: `Enter the Star's Temperature (K)` (> 0), `Enter the Star's Luminosity (Lsun)` (> 0).
- Computes HZ boundary distances: `au = sqrt(luminosity / Seff)` for each of the six Kopparapu zones.
- Screen cleared after all inputs, before output.
- Output: "Calculated Habitable Zone" table with Zone | AU columns; AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`.
- Zone order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (RG 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (RG 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars).

### Option 41: Habitable Zone Calculator w/SMA — `habitable_zone_calculator_sma()`
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

### Option 42: Star Luminosity — `star_luminosity_calculator()`
- Prompts: `Enter the Star's Radius (R☉)` (> 0), `Enter the Star's Temperature (K)` (> 0).
- Calculates: `luminosity = radius² × (temp / 5778)⁴`.
- Screen cleared after all inputs, before output.
- Output table columns: Radius (R☉) (4dp) | Temperature (K) (4dp) | Luminosity (Lsun) (6dp).
