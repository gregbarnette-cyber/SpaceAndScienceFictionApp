# Calculator Feature Documentation

Options 18–32. Distance, velocity, travel time, and brachistochrone features. These change together when travel/distance calculation logic is revised.

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
