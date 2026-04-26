# Calculator Feature Documentation

Options 17–32. Distance, velocity, travel time, and brachistochrone features. These change together when travel/distance calculation logic is revised.

## Distance Between 2 Stars Feature

- Menu option 17: `query_distance_between_stars()` — computes the 3D Euclidean distance in light years between two star systems.
- Helper `_lookup_star_for_distance(designation)` handles SIMBAD lookup for a single star; returns `(name, ra_deg, dec_deg, ly, desig_str)` or `None` on failure.
  - Special case: if designation is `"sun"` or `"sol"` (case-insensitive), returns `(designation, 0.0, 0.0, 0.0, "")` with no SIMBAD query.
  - Queries SIMBAD with `add_votable_fields("plx_value")` and also calls `Simbad.query_objectids()` to build a short designation string (NAME, HD, HR, GJ, Wolf only).
  - Computes `ly = 1000 / plx_mas × 3.26156`.
- Math: converts each star's RA/DEC (decimal degrees from SIMBAD) + distance (ly) to 3D Cartesian coordinates; distance = `sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)`.
- Output table columns: Star | Star Designations | RA (HMS) | DEC (±DMS) | Light Years.
- After the table, prints `Distance Between <star1> and <star2>: X.XXXX Light Years`. If distance < 0.5 ly, also prints the distance in AU (`ly × 63241.077`).

## Stars within a Certain Distance of Sol Feature

- Menu option 18: `query_stars_within_distance()` — lists all stars in `starSystems.csv` within a user-supplied light year limit of Sol.
- Reads `starSystems.csv` directly; uses the `Light Years` column for distance comparison. No SIMBAD query.
- Prompts for a distance limit (float, must be > 0). Prints error if `starSystems.csv` not found (directs user to run option 50).
- Results sorted ascending by Light Years. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (4dp).
- **GUI diagram tabs** (via `DiagramToggleMixin`): "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D". All three use a light gray background (`bg="#ebebeb"`). The 3D tab includes Top View / Side View / 3D Perspective preset buttons above the matplotlib toolbar. Stars are coloured by spectral class; Sol is highlighted with a star marker at the origin. Hover shows name + distance; click shows full info box.

## Stars within a Certain Distance of a Star Feature

- Menu option 19: `query_stars_within_distance_of_star()` — lists all stars in `starSystems.csv` within a user-supplied light year limit of a queried star.
- Prompts for Star System Name and distance limit (float, must be > 0).
- Queries SIMBAD for the center star via `_lookup_star_for_distance()`.
- Reads `starSystems.csv`; for each row parses `Parallax` → ly, `RA` (sexagesimal HMS) → decimal degrees, `DEC` (sexagesimal ±DMS) → decimal degrees, then converts to 3D Cartesian coordinates and computes Euclidean distance from the center star.
- Skips any row with computed distance < 0.001 ly (eliminates the center star itself and floating-point near-zero matches).
- Results sorted ascending by distance. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (3dp).
- **GUI diagram tabs**: identical to option 18 — "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" with the same preset buttons, background, and interactivity. Center star placed at origin (gold `#FFD700`); surrounding stars' coordinates shifted relative to it.

## Speed / Velocity Converter Features

### Shared velocity conversion constant
- `8765.8128` = hours in a Julian year (365.25 × 24). Used to convert between ly/hr and multiples of c: `times_c = ly_hr × 8765.8128`.

### Option 20: Light Years per Hour to X Times the Speed of Light — `ly_per_hour_to_speed_of_light()`
- Prompts: `Enter velocity in light years per hour`
- Converts ly/hr → X times c: `times_c = ly_hr × 8765.8128`
- Screen cleared after input, before output.
- Output: single line showing both values.

### Option 21: X Times the Speed of Light to Light Years per Hour — `speed_of_light_to_ly_per_hour()`
- Prompts: `Enter velocity in X times the speed of light`
- Converts X times c → ly/hr: `ly_hr = times_c / 8765.8128`
- Screen cleared after input, before output.
- Output: single line showing both values.

## Distance Traveled Features

### Option 22: Distance Traveled at a certain ly/hr within a certain time — `distance_traveled_ly_per_hour()`
- Prompts: `Enter travel time in hours`, `Enter the velocity in light years per hour`
- Calculates: `distance = ly_hr × hours`
- Screen cleared after all inputs, before output.
- Output: single line showing velocity, time, and distance in light years.

### Option 23: Distance Traveled at a certain X times the speed of light within a certain time — `distance_traveled_times_c()`
- Prompts: `Enter travel time in hours`, `Enter the velocity X times the speed of light`
- Converts to ly/hr first: `ly_hr = times_c / 8765.8128`, then `distance = ly_hr × hours`
- Screen cleared after all inputs, before output.
- Output: single line showing velocity (×c), time, and distance in light years.

## Travel Time Features (Given Distance in Light Years)

### Shared helper: `_format_travel_time(total_hours)`
- Breaks total hours into Years, Months, Days, Hours, Minutes, Seconds.
- Only includes units that are ≥ 1 (seconds shown if < 1 minute total, or if remaining seconds ≥ 0.005).
- Uses Julian year: `HOURS_PER_YEAR = 365.25 × 24 = 8765.82`, `HOURS_PER_MONTH = HOURS_PER_YEAR / 12`.
- Returns a comma-separated string, e.g. `"5 Months, 24 Days, 11 Hours, 30 Minutes"`.

### Option 24: Time to Travel # of Light Years at X LY/HR — `time_to_travel_ly_at_ly_per_hour()`
- Prompts: `Enter number of light years`, `Enter velocity in light years per hour` (must be > 0)
- Calculates: `total_hours = distance_ly / ly_hr`, `times_c = ly_hr × 8765.8128`
- Screen cleared after all inputs, before output.
- Output table columns: Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time

### Option 25: Time to Travel # of Light Years at X Times the Speed of Light — `time_to_travel_ly_at_times_c()`
- Prompts: `Enter number of light years`, `Enter velocity in X times the speed of light` (must be > 0)
- Calculates: `ly_hr = times_c / 8765.8128`, `total_hours = distance_ly / ly_hr`
- Screen cleared after all inputs, before output.
- Output table columns: Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

## Travel Time Between 2 Stars Features

### Shared helper: `_travel_time_between_stars(velocity_label, velocity_prompt, use_times_c)`
- Used by options 26 and 27. `use_times_c=False` → velocity input is ly/hr; `use_times_c=True` → velocity input is X times c.
- Prompts: `Enter origin star`, `Enter destination star`, then the velocity prompt.
- Looks up both stars via `_lookup_star_for_distance()` (Sun/Sol → `(0.0, 0.0, 0.0)` with no SIMBAD query).
- Computes 3D Euclidean distance in ly using same Cartesian math as option 17.
- Converts velocity: if `use_times_c`, derives `ly_hr = times_c / 8765.8128`; else derives `times_c = ly_hr × 8765.8128`.
- `total_hours = distance_ly / ly_hr`; travel time formatted via `_format_travel_time()`.
- Screen cleared after all inputs and star lookups succeed, before table output. Early-return error paths (empty name, lookup failure) do not clear.
- Output table columns (option 26): Origin | Destination | Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time
- Output table columns (option 27): Origin | Destination | Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

### Option 26: Travel Time Between 2 Stars (LYs/HR) — `travel_time_between_stars_ly_hr()`
- Calls `_travel_time_between_stars(..., use_times_c=False)`.

### Option 27: Travel Time Between 2 Stars (X Times the Speed of Light) — `travel_time_between_stars_times_c()`
- Calls `_travel_time_between_stars(..., use_times_c=True)`.

## Brachistochrone Calculator Features

### Physical constants (used by options 28–31)
- `G_MS2 = 9.80665` m/s² (1 g)
- `C_MS = 299,792,458` m/s (speed of light)
- `V_CAP_MS = 0.03 × C_MS` (3% of c = 8,993,773.74 m/s)
- `M_PER_AU = 149,597,870,700` m
- `M_PER_LM = C_MS × 60` m (metres per light-minute)
- All kinematics are non-relativistic (appropriate at v ≤ 3% c).

### Three acceleration profiles (used by options 29–31)
Options 29–31 are given a distance and solve for travel time.
- **Profile 1 — Continuous to Halfway Point**: accelerate for t/2, flip and decelerate for t/2. `t = 2 × √(d/a)`
- **Profile 2 — Half Continuous Accel Time, Coast, Then Decelerate**: accelerate t/4, coast t/2, decelerate t/4. `t = √(16d / (3a))`
- **Profile 3 — Accel to 3% c, Coast, Then Decelerate**: `t_cap = V_CAP / a`. If `a×t_cap² ≥ d`, cap not reached → use Profile 1 formula. Else: `t = 2×t_cap + (d - a×t_cap²) / V_CAP`.
  - When cap not reached, label appended with `"(cap not reached)"`.

### Option 28: Distance Traveled at an Acceleration Within a Certain Time — `distance_traveled_at_acceleration()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Travel Time in Hours` (> 0)
- Computes distance (metres → AU and LM) for each profile given the travel time.
- Profile 1 for this option differs from options 29–31: **Continuous Acceleration for Entire Time** — `d = ½ × a × t²` (no flip/decelerate).
- Profile 2: same as options 29–31 — accel t/4, coast t/2, decel t/4; `d = 3×a×t²/16`.
- Profile 3: accel to 3% c (V_CAP) then coast for remaining time — no decel (decel happens at destination outside the time window). `d = ½×a×t_cap² + V_CAP×(t - t_cap)`. Cap-not-reached condition: `t_cap ≥ t` (one phase only, not two); fallback is `d = ½ × a × t²`.
- Screen cleared after all inputs, before output.
- Output table columns: Acceleration Profile | Acceleration (G's) | Travel Time (Hours) | Travel Time | Distance (AU) | Distance (LM) | Max Vel
  - Max Vel: "N/A" for Profiles 1 and 2 (no velocity cap); "Y" or "N" for Profile 3 indicating whether the 3% c cap was reached.
- Row order: Profile 1, Profile 2, Profile 3.

### Option 29: Travel Time Between 2 System Objs (Generic, Distance in AUs) — `travel_time_between_system_objects()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Distance in AUs` (> 0)
- Converts AU → metres, then solves for travel time for each profile.
- Also computes `distance_lm = d_m / M_PER_LM` for display.
- Screen cleared after all inputs, before output.
- Output table columns: Acceleration Profile | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time | Max Vel
  - Max Vel: "N/A" for Profiles 1 and 2; "Y" or "N" for Profile 3.
- Row order: Profile 1, Profile 2, Profile 3.

### Option 30: Travel Time Between 2 System Objs (Generic, Distance in LMs) — `travel_time_between_system_objects_lm()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Distance in Light Minutes` (> 0)
- Converts LM → metres, then solves for travel time for each profile. Same formulas as option 29.
- Also computes `distance_au = d_m / M_PER_AU` for display.
- Screen cleared after all inputs, before output.
- Output table columns: Acceleration Profile | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time | Max Vel
  - Max Vel: "N/A" for Profiles 1 and 2; "Y" or "N" for Profile 3.
- Row order: Profile 1, Profile 2, Profile 3.

### Option 31: Travel Time Between 2 System Objs (Planet/Moon/Asteroid) — `travel_time_between_solar_system_objects()`
- Prompts: `Enter Origin Planet/Satellite/Asteroid`, `Enter Destination Planet/Satellite/Asteroid`, `Enter Acceleration in # of G's` (> 0), `Enter Max Velocity for Accelerate-to-Max-Velocity Profile (% of c, Default 3)` (blank → 3.0).
- Screen cleared after all user inputs and before JPL Horizons queries begin (the "Querying JPL Horizons..." status messages appear on the cleared screen).
- Uses `astroquery.jplhorizons.Horizons` to fetch current heliocentric state vectors (x, y, z in AU) for both objects via `_get_heliocentric_vectors()`. Distance computed as 3D Euclidean: `sqrt((dx-ox)²+(dy-oy)²+(dz-oz)²)`.
- **Object name resolution**: `_resolve_horizons_id(name)` checks `_HORIZONS_ID_MAP` (normalized lowercase) first, then the last token of the input (handles "Jupiter's moon Io" → "io"), then falls through to pass the raw string to Horizons (handles numeric IDs like "433", asteroid designations like "1998 QE2").
- `_HORIZONS_ID_MAP`: module-level dict mapping ~100 common names to Horizons numeric IDs (8 planets, Sun, all major moons, dwarf planets, common asteroids/comets).
- Profile 3 velocity cap is user-configurable: `V_CAP_MS = (v_cap_pct / 100.0) × C_MS`. Label reads `"Accel to {v_cap_pct}% c, Coast, Then Decelerate"`.
- Same brachistochrone physics as options 29/30; Profile 1: `t = 2·√(d/a)`, Profile 2: `t = √(16d/(3a))`, Profile 3: `t = 2·t_cap + (d - a·t_cap²)/V_CAP` (falls back to Profile 1 if cap not reached).
- Error handling: ambiguous Horizons name prints the disambiguation table from the exception message + tip to use numeric ID; other errors print the exception; both return early. Same-object detection: distance < 1e-9 AU triggers error and early return.
- Output table columns: Acceleration Profile | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Travel Time (Hours) | Travel Time | Max Vel
  - Max Vel: "N/A" for Profiles 1 and 2; "Y" or "N" for Profile 3.
- Row order: Profile 1, Profile 2, Profile 3. Origin/Destination columns show user's raw input strings.
- **GUI diagram tabs** (via `DiagramToggleMixin`): "Solar System Map" (2D top-down XY ecliptic view) and "3D View". Both show current heliocentric positions of all 8 planets as coloured dots with dashed reference orbit circles, the Sun as a gold star at the origin, the origin body as an orange ★, the destination body as a cyan ■, and a dashed line connecting origin to destination. The 3D tab includes Top View / Side View / 3D Perspective preset buttons above the matplotlib toolbar. Hover shows body name; click shows name + XY position + distance from Sun. Planet positions are fetched alongside the origin/dest query and cached for 30 minutes so repeated calculations reuse the same planet data.
- **Core function**: `core.calculators.compute_travel_time_solar_objects()` — extended to also return `origin_xyz: (x, y, z)`, `dest_xyz: (x, y, z)`, and `planet_positions: list` in addition to the existing keys. Planet positions fetched via `_fetch_planet_positions(epoch_jd)`.

### Option 32: Travel Time Between 2 System Objs (Custom Thrust Duration) — `travel_time_custom_thrust_duration()`
- Prompts: `Enter Origin Planet/Satellite/Asteroid`, `Enter Destination Planet/Satellite/Asteroid`, `Enter Acceleration in # of G's` (> 0), `Enter Acceleration/Deceleration Duration` (> 0), `Enter Unit (H=Hours, D=Days, W=Weeks) [D]` (default Days), `Enter Max Velocity for Coast Phase (% of c, Default 3)` (blank → 3.0).
- Screen cleared after all user inputs and before JPL Horizons queries begin.
- Uses `_resolve_horizons_id()` and `_HORIZONS_ID_MAP` (same as option 31).
- **Iterative destination position estimation**: unlike option 31 which uses a single snapshot, this function queries the destination's position at the estimated arrival time and iterates until the travel time converges (change < 60 seconds, max 10 iterations). Origin position is fixed at departure time (now). Uses `_get_heliocentric_vectors()` with `epoch_jd` parameter.
- **Acceleration profile**: Accelerate for the user-specified burn duration, coast at the reached velocity, then decelerate for the same duration. If max velocity is reached before the burn ends, effective burn time is shortened to `v_max / a`.
- **Physics**:
  - `t_accel_eff = min(burn_seconds, V_CAP_MS / a_ms2)`
  - `v_coast = a_ms2 × t_accel_eff`
  - `d_accel = 0.5 × a_ms2 × t_accel_eff²`; `d_decel = d_accel`
  - `d_coast = d_total - 2 × d_accel`; `t_coast = d_coast / v_coast`
  - `t_total = 2 × t_accel_eff + t_coast`
- **Fallback**: if `2 × d_accel ≥ d_total` (distance too short for requested burn), falls back to midpoint profile: `t = 2·√(d/a)`, with an explanatory note in the output.
- **Time to Reach Max Velocity**: displayed if `burn_seconds > V_CAP_MS / a_ms2`; otherwise shows `N/A`.
- Output: vertical key-value layout showing Origin, Destination, Distance (AU/LM), Acceleration (G's/m/s²), Requested vs Effective Burn Duration, Max Velocity Cap, Max Velocity Reached (Y/N), Time to Reach Max Velocity, Coast Velocity (m/s and % c), Acceleration/Coast/Deceleration Time and Distance, Total Travel Time. Includes a note about iterative convergence.
- Same error handling as option 31: ambiguous Horizons name, lookup failure, same-object detection (distance < 1e-9 AU).
- **GUI diagram tabs**: identical to option 31 — "Solar System Map" and "3D View" with the same planet map, origin/dest markers, dashed travel line, preset buttons, and interactivity. Planet positions are fetched at departure epoch `t0_jd` (same epoch as origin's first Horizons query). Core function `core.calculators.compute_travel_time_custom_thrust()` returns the same three added keys: `origin_xyz`, `dest_xyz`, `planet_positions`.
