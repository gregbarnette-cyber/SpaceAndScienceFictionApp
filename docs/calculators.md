# Calculator Feature Documentation

Options 17–32. Distance, velocity, travel time, and brachistochrone features. These change together when travel/distance calculation logic is revised.

> **`query.py`:** several pure-math calculators here are also exposed as subcommands —
> `distance` (17), `travel-time` (20/21), `distance-at-acceleration` (24), `brachistochrone-au`/`-lm` (29/30),
> and the six velocity/distance/travel converters `ly-hr-to-times-c` (31), `times-c-to-ly-hr` (32),
> `distance-traveled-ly-hr` (25), `distance-traveled-times-c` (26), `travel-time-ly-hr` (27),
> `travel-time-times-c` (28). The JPL Horizons ones are exposed too (`travel-time-solar`, `travel-time-custom-thrust`).
> All wrap **non-self-validating** functions (out-of-range → raw-exception exit 1, argparse exit 2). See `docs/integration.md`.

## Distance Between 2 Stars Feature

- Menu option 17: `query_distance_between_stars()` — computes the 3D Euclidean distance in light years between two star systems.
- Helper `_lookup_star_for_distance(designation)` handles SIMBAD lookup for a single star; returns `(name, ra_deg, dec_deg, ly, desig_str)` or `None` on failure.
  - Special case: if designation is `"sun"` or `"sol"` (case-insensitive), returns `(designation, 0.0, 0.0, 0.0, "")` with no SIMBAD query.
  - Queries SIMBAD with `add_votable_fields("plx_value")` and also calls `Simbad.query_objectids()` to build a short designation string (NAME, HD, HR, GJ, Wolf only).
  - Computes `ly = 1000 / plx_mas × 3.26156`.
- Math: converts each star's RA/DEC (decimal degrees from SIMBAD) + distance (ly) to 3D Cartesian coordinates; distance = `sqrt((x2-x1)² + (y2-y1)² + (z2-z1)²)`.
- Output table columns: Star | Star Designations | RA (HMS) | DEC (±DMS) | Light Years.
- **GUI diagram tabs**: "Star Chart" + "Star Chart 3D" (Phase O8) — **Sol-centered** (gold ★ at the origin) with the two
  searched stars at their true heliocentric positions, coloured by spectral class. Identical in look and interactivity
  to the opt-18/19 Star Charts (per-class legend filter, travel-time isochrone control, click-info box, 3D viewpoint
  presets); clicking a dot selects its row in the two-row result table. See the Phase O8 note in Route Planning below.
- After the table, prints `Distance Between <star1> and <star2>: X.XXXX Light Years`. If distance < 0.5 ly, also prints the distance in AU (`ly × 63241.077`).

## Stars within a Certain Distance of Sol Feature

- Menu option 18: `query_stars_within_distance()` — lists all stars in the `star_systems` DB table within a user-supplied light year limit of Sol.
- Reads from the `star_systems` DB table directly; uses the `light_years` column for distance comparison. No SIMBAD query.
- Prompts for a distance limit (float, must be > 0). Prints error if `star_systems` table is empty (directs user to run option 50).
- Results sorted ascending by Light Years. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (4dp).
- **GUI diagram tabs** (via `DiagramToggleMixin`), in display order: "Star Chart" (the **default** selected tab when Show Diagrams is pressed), "Star Chart 3D", "HR Diagram", "Night Sky", "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D". The three Map tabs use a light gray background (`bg="#ebebeb"`). The 3D tab includes Top View / Side View / 3D Perspective preset buttons above the matplotlib toolbar. Stars are coloured by spectral class; Sol is highlighted with a star marker at the origin. Hover shows name + distance in a **cursor-anchored** tooltip (it follows the pointer next to the hovered dot, clamped on-canvas); click shows full info box. Scroll wheel zooms in/out; Home button resets to the initial zoom and view angles. The rectangle Zoom button is removed from the 3D toolbar — it cannot map a 2D screen selection back to 3D data coordinates correctly.
  - **"⟲ Reset Diagram" button (2026-08-14)** — a labelled reset control next to **Show Tables** in the diagram header (mirroring the OEC Architecture map's `⟲ Reset diagram`). It restores the **currently-visible tab** to its build-time default: it calls that tab's `canvas.reset_view()` (undoes any O18 find-centering) and its `toolbar.home()` (undoes scroll-wheel / toolbar zoom, pan, and 3D rotation — `push_current()` seeds each chart's nav-stack home at build, and scroll-zoom sets limits directly without pushing, so `home()` is a full reset). It is the discoverable equivalent of the per-tab toolbar Home. Built by `diagram_tabs._add_reset_diagram_button` (created once, reused across renders; guarded against duplicates) inserted into the shared `DiagramToggleMixin._viz_header_row`; the reset itself is `diagram_tabs._reset_active_diagram`, which reaches the active tab's live canvas/toolbar via `findChildren` (so it survives the isochrone tabs' Apply-time canvas swap). **The same button is on the two-star charts (opts 17/20/21) and all seven Route Planning panels** — added in their shared `add_two_star_chart_tabs` / `_add_route_chart_tabs` builders (Jump Route's `reachable=False` chart gets it too — the call sits outside the `find_box` guard). Tests: `tests/test_route_find.py::OptEighteenNineteenResetTest` + `RouteResetButtonTest`.
  - "Star Chart" is a labeled X–Y projection in the dark navy palette of `generate_star_map_html.py` (fig bg `#070b18`, plot bg `#0b1020`, minor grid `#1a2448` / major `#2a3868`, axes `#4a6a99`, distance rings `#3a5a8a`). Each star is drawn as a small dot coloured by spectral class with a `"Name (Z=±X.XXX)"` label nudged downward when it would overlap a previously placed label; Sol is a gold ★ at the origin. Grid/ring intervals scale with the user's distance limit (1/5 ly for ≤ 20, 2/10 for ≤ 50, 5/25 for ≤ 100, 10/50 otherwise). Stars whose `|x|` or `|y|` exceeds the limit (still inside the sphere but outside the projection square) are excluded — same rule as the HTML script. Per-star labels (and the Sol Z-label) are always created but their visibility is governed by the visible half-range: they're shown whenever `(x1-x0)/2 ≤ 15` (or equivalently `(y1-y0)/2 ≤ 15`) and hidden otherwise. So at small initial limits (≤ 15 ly) labels appear immediately; at larger limits the chart starts unlabeled and labels appear as soon as the user zooms in enough that the visible half-range drops below 15 ly. The toolbar's Home button resets the view to the original limit, which hides them again. Per-star labels are drawn with `ax.annotate(..., xytext=(6, 5), textcoords="offset points")` — a **fixed pixel offset** — so each label stays glued to its dot at any zoom level (a data-space offset would drift off the marker as you zoom in); initially-overlapping labels are nudged downward in screen-space points. All in-plot text — the per-star/Sol labels **and** the axis tick numbers, the `X (ly)`/`Y (ly)` axis titles, and the ring `N ly` labels — is drawn with `clip_on=True` (plus `annotation_clip=True` on the annotations) so nothing renders past the axes box when the view is panned or zoomed (only the click-info box, anchored in axes-fraction coordinates, is intentionally unclipped). Hover/click still surface individual star details at any zoom level.
  - "Star Chart 3D" is the 3D companion to "Star Chart" — same dark navy palette and styling, drag-rotate (`azel` style), Top View / Side View / 3D Perspective preset buttons above the matplotlib toolbar, scroll-wheel zoom, and the same zoom-driven label toggle (visibility recomputed off `max((x1-x0)/2, (y1-y0)/2, (z1-z0)/2) ≤ 15 ly`, with `xlim_changed`/`ylim_changed`/`zlim_changed` callbacks). The center star is a gold ★ at the origin; surrounding stars are spectral-class colored dots. Faint blue wireframe spheres are drawn at every `major_step` ly (5, 10, 15 ly at the default 1/5 stepping) as 3D depth cues. **The 3D axis cube is hidden** — pane fills, pane edges, and grid lines are all removed (`axis.pane.fill = False`, transparent pane edge color, `ax.grid(False)`); only the tick labels and X/Y/Z axis labels remain for numeric scale reference. The 3D content is enlarged within the axes via `ax.set_box_aspect((1,1,1), zoom=1.35)` (matplotlib 3.6+; falls back gracefully on older versions) and full-figure subplot margins (`left=0, right=1, top=1, bottom=0`). Hover tooltip is **cursor-anchored** (a `text2D` whose axes-fraction position is updated to follow the pointer via `_anchor_hover_to_cursor`, alignment-flipped + clamped so it never runs off-canvas); click info box stays pinned in the lower-left. Rectangle Zoom is removed from the toolbar — it cannot map a 2D screen selection back to 3D data coords correctly. The figure uses symmetric `subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.06)` plus `anchor="C"` so the square aspect-equal axes stays visually centred when the canvas is wider than tall. Hover shows name + distance; click shows the full info box (name, designations, spectral type, distance, X/Y/Z); scroll wheel zooms around the cursor; the toolbar Home button restores the initial view.

## Stars within a Certain Distance of a Star Feature

- Menu option 19: `query_stars_within_distance_of_star()` — lists all stars in the `star_systems` DB table within a user-supplied light year limit of a queried star.
- Prompts for Star System Name and distance limit (float, must be > 0).
- Queries SIMBAD for the center star via `_lookup_star_for_distance()`.
- Reads the `star_systems` DB table; for each row uses `parallax` → ly, `ra` (sexagesimal HMS) → decimal degrees, `dec` (sexagesimal ±DMS) → decimal degrees, then converts to 3D Cartesian coordinates and computes Euclidean distance from the center star.
- Skips any row with computed distance < 0.001 ly (eliminates the center star itself and floating-point near-zero matches).
- **Sol is synthesized, not read (2026-07-31).** The Sun is not a SIMBAD catalog object, so `star_systems` holds **no row for it** and never can — yet from any other star Sol is an ordinary neighbour (11.91 ly from τ Ceti, 4.24 ly from Proxima). It was therefore silently missing from every opt-19 result. `core.calculators._sol_result_row(cx, cy, cz, limit_ly)` appends one at the heliocentric origin, gated by the **same** `0.001 < dist ≤ limit_ly` rule as the DB rows — which is also what excludes it when the center *is* Sol (`compute_lookup_star_for_distance` resolves `"sol"`/`"sun"` to `ly = 0`, so the distance is 0). Fields: name `Sol`, designations `Sun`, `G2V`, `app_magnitude = -26.74`, `parsecs = 4.84813681e-06`, `x/y/z = 0`.
  - **`parsecs` is 1 AU in parsecs, and that is load-bearing** — not a fudge. The HR-diagram and night-sky preps recover an absolute magnitude as `M = V + 5 − 5·log₁₀(pc)`; pairing Sol's Earth-apparent V of −26.74 with its true 1 AU distance makes that round-trip land on M_V = 4.83, so **neither prep needs a Sol special case**. Consequently `core.viz.prepare_sky_from_star` **no longer appends its own Sol** (it previously hard-coded exactly that 4.83) — re-adding it would put Sol on the sky twice.
  - Both code paths need it: `core/calculators.py` (GUI + `query.py stars-within-star`) and `main.py`'s CLI copy, which does **not** delegate to core. The CLI imports the shared helper and keeps only the four columns it renders.
  - `count` and `stars[]` now include a row with no catalogue backing — an observable `query.py` contract change (see `docs/integration.md`). The GCNS sibling `compute_gcns_stars_within_star` has the identical gap and the identical fix, flagged there by `in_gcns = False` / `distance_method = "synthetic_sol_origin"` (see `docs/star-databases.md`).
  - **Sol is drawn as a ★, not a dot.** On the four map canvases (`make_star_chart_canvas`/`_3d`, `make_star_map_canvas`/`_3d`) a star flagged `is_sol` gets a ★ overlay at ~3× the body-dot size, keeping its **G-class colour** — shape carries the identity, colour still carries the physics, and the paler fill keeps it distinct from the gold centre ★. The flag is set in `core.viz.prepare_star_map_from_result` (by name) and `gui.panels.gcns._gcns_map_stars` (by `distance_method`); an unflagged star list builds exactly as before.
    - It is an **overlay artist on top of the body scatter**, not a per-point marker swap, for two concrete reasons: the body scatter is a single `PathCollection` whose point **order** backs hit-testing, legend filtering and the O15 selection ring; and in 3D `do_3d_projection` depth-sorts the sizes and colours but **not** the paths, so a per-point path swap would migrate the ★ onto whichever star sorted into that slot as the view rotates. `make_star_map_canvas`/`_3d` already highlight the centre star this same way. `gui.visualizations.plot_helpers._overlay_sol_marker` is the one implementation — don't open-code a second.
    - The `_SOL_*` constants live in **`core/shared.py`**, not beside the row builder: `core.viz` needs the name to set the flag and must not import the heavier `core.calculators`.
  - **Opt 18 deliberately does not gain a Sol row**: its distances are measured *from* Sol, so Sol's own distance is 0 and the row would be meaningless. Sol has always appeared there as a map dot injected in `prepare_star_map_from_result` — that path is unchanged.
- **Malformed-row tolerance**: opt 50 writes `ra`/`dec` as `""` when SIMBAD's value fails to parse, and the split-based sexagesimal parsers raise **`IndexError`** (not `ValueError`) on a blank or short string. The per-row handler therefore catches `(ValueError, TypeError, IndexError)` and skips the row — matching `_load_star_systems_positions`. Before this, a single degenerate row aborted the entire search; it was masked only because the opt-50 `PLX …` discard rule happened to filter most such rows out. Opt 18 already caught bare `Exception` (it returns the row with `x/y/z = None`, which every viz prep skips).
- Results sorted ascending by distance. Displays count of matches above the table.
- Output table columns: Star Name | Star Designations | Spectral Type | Distance (LY) (3dp).
- **GUI diagram tabs**: identical to option 18 — "Star Chart" (default), "Star Chart 3D", "HR Diagram", "Night Sky", "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" — with the same preset buttons, background, and interactivity. Center star placed at origin (gold `#FFD700`); surrounding stars' coordinates shifted relative to it. The Star Chart and Star Chart 3D tabs' center-star anchor label uses the queried star's name in place of "Sol".

## Speed / Velocity Converter Features

### Shared velocity conversion constant
- `8765.8128` = hours in a **tropical** year (365.2422 × 24), **not** the Julian year (365.25 × 24 = 8766.0). This tropical-year value is the legacy ly/hr↔×c anchor kept for output stability (golden pins and the downstream consumer depend on the exact value — see IMPROVEMENT_PLAN D1). Used to convert between ly/hr and multiples of c: `times_c = ly_hr × 8765.8128`.

### Option 31: Light Years per Hour to X Times the Speed of Light — `ly_per_hour_to_speed_of_light()`
- Prompts: `Enter velocity in light years per hour`
- Converts ly/hr → X times c: `times_c = ly_hr × 8765.8128`
- Screen cleared after input, before output.
- Output: single line showing both values.

### Option 32: X Times the Speed of Light to Light Years per Hour — `speed_of_light_to_ly_per_hour()`
- Prompts: `Enter velocity in X times the speed of light`
- Converts X times c → ly/hr: `ly_hr = times_c / 8765.8128`
- Screen cleared after input, before output.
- Output: single line showing both values.

## Distance Traveled Features

### Option 25: Distance Traveled at a certain ly/hr within a certain time — `distance_traveled_ly_per_hour()`
- Prompts: `Enter travel time in hours`, `Enter the velocity in light years per hour`
- Calculates: `distance = ly_hr × hours`
- Screen cleared after all inputs, before output.
- Output: single line showing velocity, time, and distance in light years.

### Option 26: Distance Traveled at a certain X times the speed of light within a certain time — `distance_traveled_times_c()`
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

### Option 27: Time to Travel # of Light Years at X LY/HR — `time_to_travel_ly_at_ly_per_hour()`
- Prompts: `Enter number of light years`, `Enter velocity in light years per hour` (must be > 0)
- Calculates: `total_hours = distance_ly / ly_hr`, `times_c = ly_hr × 8765.8128`
- Screen cleared after all inputs, before output.
- Output table columns: Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time

### Option 28: Time to Travel # of Light Years at X Times the Speed of Light — `time_to_travel_ly_at_times_c()`
- Prompts: `Enter number of light years`, `Enter velocity in X times the speed of light` (must be > 0)
- Calculates: `ly_hr = times_c / 8765.8128`, `total_hours = distance_ly / ly_hr`
- Screen cleared after all inputs, before output.
- Output table columns: Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

## Travel Time Between 2 Stars Features

### Shared helper: `_travel_time_between_stars(velocity_label, velocity_prompt, use_times_c)`
- Used by options 20 and 21. `use_times_c=False` → velocity input is ly/hr; `use_times_c=True` → velocity input is X times c.
- Prompts: `Enter origin star`, `Enter destination star`, then the velocity prompt.
- Looks up both stars via `_lookup_star_for_distance()` (Sun/Sol → `(0.0, 0.0, 0.0)` with no SIMBAD query).
- Computes 3D Euclidean distance in ly using same Cartesian math as option 17.
- Converts velocity: if `use_times_c`, derives `ly_hr = times_c / 8765.8128`; else derives `times_c = ly_hr × 8765.8128`.
- `total_hours = distance_ly / ly_hr`; travel time formatted via `_format_travel_time()`.
- Screen cleared after all inputs and star lookups succeed, before table output. Early-return error paths (empty name, lookup failure) do not clear.
- Output table columns (option 20): Origin | Destination | Distance (LYs) | LY/HR | X Times Speed of Light | Travel Time (Hours) | Travel Time
- Output table columns (option 21): Origin | Destination | Distance (LYs) | X Times Speed of Light | LY/HR | Travel Time (Hours) | Travel Time

### Option 20: Travel Time Between 2 Stars (LYs/HR) — `travel_time_between_stars_ly_hr()`
- Calls `_travel_time_between_stars(..., use_times_c=False)`.

### Option 21: Travel Time Between 2 Stars (X Times the Speed of Light) — `travel_time_between_stars_times_c()`
- Calls `_travel_time_between_stars(..., use_times_c=True)`.

## Brachistochrone Calculator Features

### Physical constants (used by options 22–24, 29–30)
- `G_MS2 = 9.80665` m/s² (1 g)
- `C_MS = 299,792,458` m/s (speed of light)
- `V_CAP_MS = 0.03 × C_MS` (3% of c = 8,993,773.74 m/s)
- `M_PER_AU = 149,597,870,700` m
- `M_PER_LM = C_MS × 60` m (metres per light-minute)
- All kinematics are non-relativistic (appropriate at v ≤ 3% c).

### Three acceleration profiles (used by options 22–23, 29–30)
Options 22–23 and 29–30 are given a distance and solve for travel time.
- **Profile 1 — Continuous to Halfway Point**: accelerate for t/2, flip and decelerate for t/2. `t = 2 × √(d/a)`
- **Profile 2 — Half Continuous Accel Time, Coast, Then Decelerate**: accelerate t/4, coast t/2, decelerate t/4. `t = √(16d / (3a))`
- **Profile 3 — Accel to 3% c, Coast, Then Decelerate**: `t_cap = V_CAP / a`. If `a×t_cap² ≥ d`, cap not reached → use Profile 1 formula. Else: `t = 2×t_cap + (d - a×t_cap²) / V_CAP`.
  - When cap not reached, label appended with `"(cap not reached)"`.

> **Phase O · O9 — Acceleration Profiles diagram tab (GUI).** `core.viz.prepare_brachistochrone_profiles(result)` reconstructs each profile's piecewise `v(t)`/`d(t)` from `accel_g` + the per-profile total time + the profile type (the formulas above, plus the opt-24 distance-given-time variants and the opt-23 custom-thrust accel/coast/decel profile), sampling ~200 points → `{accel_g, profiles:[{label, color, t_hours, v_kms, d_au}]}` (colours fixed per index). `gui.visualizations.plot_helpers.make_profile_canvas` draws two stacked subplots sharing the time axis: velocity (km/s + a secondary `% c` axis) over cumulative distance (AU + a secondary LM axis). Added as an **"Acceleration Profiles"** viz tab on opts **24/29/30** (which gained `DiagramToggleMixin`) and to the existing diagram tabs of opts **22/23**. Pure viz reconstruction — no change to the core travel-time math. See `docs/gui-architecture.md`.

### Option 24: Distance Traveled at an Acceleration Within a Certain Time — `distance_traveled_at_acceleration()`
- Prompts: `Enter Acceleration in # of g's` (> 0), `Enter Travel Time in Hours` (> 0)
- Computes distance (metres → AU and LM) for each profile given the travel time.
- Profile 1 for this option differs from options 22–23, 29–30: **Continuous Acceleration for Entire Time** — `d = ½ × a × t²` (no flip/decelerate).
- Profile 2: same as options 22–23, 29–30 — accel t/4, coast t/2, decel t/4; `d = 3×a×t²/16`.
- Profile 3: accel to 3% c (V_CAP) then coast for remaining time — no decel (decel happens at destination outside the time window). `d = ½×a×t_cap² + V_CAP×(t - t_cap)`. Cap-not-reached condition: `t_cap ≥ t` (one phase only, not two); fallback is `d = ½ × a × t²`.
- Screen cleared after all inputs, before output.
- Output table columns: Acceleration Profile | Acceleration (G's) | Travel Time (Hours) | Travel Time | Distance (AU) | Distance (LM) | Max Vel
  - Max Vel: "N/A" for Profiles 1 and 2 (no velocity cap); "Y" or "N" for Profile 3 indicating whether the 3% c cap was reached.
- Row order: Profile 1, Profile 2, Profile 3.
- **`query.py`:** exposed as `distance-at-acceleration --accel-g --hours` (core `calculators.compute_distance_at_acceleration(accel_g, hours)` → `{accel_g, hours, travel_time_str, profiles:[{label, distance_au, distance_lm, max_vel}]}`). The inverse of `brachistochrone-au`/`-lm` (accel + time → distance vs accel + distance → time); non-self-validating like them (out-of-range → raw-exception exit 1). See `docs/integration.md`.

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

## Network Reliability (JPL Horizons features)

All JPL Horizons queries are wrapped by helpers in `core/calculators.py`, which in turn rely on the shared retry/timeout/error-classification helpers (`_with_retries`, `_timeout_ctx`, `_network_error_msg`, `_make_simbad`) from `core/shared.py`:

- **`_get_heliocentric_vectors(horizons_id, epoch_jd)`** — wraps the `Horizons(...).vectors()` call in `_with_retries` (3 attempts, exponential backoff) inside `_timeout_ctx(30)` (30 s socket timeout per attempt). Raises on exhausted retries; callers catch and classify via `_network_error_msg`.
- **`fetch_body_properties(horizons_id)`** — wraps `requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params=…, timeout=15)` (`raise_for_status`) in `_with_retries`. Uses `requests` (certifi CA bundle) rather than raw `urllib.request`: on networks with a TLS-intercepting proxy / self-signed CA chain, `urllib` fails SSL verification ("Network Error") while `requests` — like every other network call in this project — succeeds. Errors are **not cached** in `_BODY_PROPS_CACHE`; only successful responses are cached, so a transient failure retries fresh next call.
- **`_planet_fetch_errors`** — module-level list reset at each fresh `_fetch_planet_positions` call. Any planet that fails all retries is omitted from the returned list (preserving existing behavior) and its error message appended here. The list is available for debugging but not currently surfaced in the GUI.
- **`compute_lookup_star_for_distance`** — uses `_make_simbad("plx_value", timeout=30)` + `_with_retries` + `_timeout_ctx(30)`, same pattern as SIMBAD callers in `databases.py`. Error messages classified via `_network_error_msg`.

Ambiguous-name detection (`"Multiple major-bodies"` / `"ambiguous"`) in `compute_travel_time_solar_objects` and `compute_travel_time_custom_thrust` is checked **before** `_network_error_msg` so the disambiguation hint is still shown verbatim.

### Option 22: Travel Time Between 2 System Objs (Planet/Moon/Asteroid) — `travel_time_between_solar_system_objects()`
- Prompts: `Enter Origin Planet/Satellite/Asteroid`, `Enter Destination Planet/Satellite/Asteroid`, `Enter Acceleration in # of G's` (> 0), `Enter Max Velocity for Accelerate-to-Max-Velocity Profile (% of c, Default 3)` (blank → 3.0).
- Screen cleared after all user inputs and before JPL Horizons queries begin (the "Querying JPL Horizons..." status messages appear on the cleared screen).
- Uses `astroquery.jplhorizons.Horizons` to fetch heliocentric state vectors (x, y, z in AU) for both objects via `_get_heliocentric_vectors()` at the selected departure epoch. Distance computed as 3D Euclidean: `sqrt((dx-ox)²+(dy-oy)²+(dz-oz)²)`.
- **Object name resolution**: `_resolve_horizons_id(name)` checks `_HORIZONS_ID_MAP` (normalized lowercase) first, then the last token of the input (handles "Jupiter's moon Io" → "io"), then falls through to pass the raw string to Horizons (handles numeric IDs like "433", asteroid designations like "1998 QE2").
- `_HORIZONS_ID_MAP`: module-level dict mapping ~100 common names to Horizons IDs (8 planets, Sun, all major moons, dwarf planets, common asteroids/comets).
  - **A numbered small body MUST carry the trailing `;`** (Horizons' small-body designator) — `"ceres": "1;"`, `"vesta": "4;"`, `"eros": "433;"`. Horizons resolves a bare integer as a **major-body** id first, and ids 1–9 are the planet *barycenters*, so the original `"ceres": "1"` / `"pallas": "2"` / `"juno": "3"` / `"vesta": "4"` silently resolved to **Mercury / Venus / Earth-Moon / Mars Barycenter** — opts 22/23 computed travel to the wrong body, with no error (fixed 2026-08-02). The `;` form is unambiguous on both call paths (`astroquery` `vectors()`/`elements()` and the `OBJ_DATA` text endpoint) and is also what makes `fetch_body_properties` take its "Asteroid physical parameters" branch — before the fix, Ceres and Vesta returned `body_type="unknown"` with no physical data at all.
  - The other numbered entries (Eros 433, Ida 243, Gaspra 951, Mathilde 253, Lutetia 21, Itokawa, Ryugu, Bennu, Apophis, Steins, and the TNOs Eris/Makemake/Haumea/Sedna) resolved correctly by luck — no major body occupies their numbers — but all now carry `;` explicitly so a future JPL addition cannot break them. **Comet ids (`1P`, `2P`, `9P`, `81P`, `67P`, `C/1995 O1`) are already unambiguous and must NOT gain a `;`.** Major bodies (Sun `10`, planets `N99`, moons `NMM`) stay bare.
  - Guarded offline by `tests/test_calculators.py::HorizonsIdMapTest`, which fails if any bare integer outside the 100–999 moon range reappears.
- Profile 3 velocity cap is user-configurable: `V_CAP_MS = (v_cap_pct / 100.0) × C_MS`. Label reads `"Accel to {v_cap_pct}% c, Coast, Then Decelerate"`.
- Same brachistochrone physics as options 29/30; Profile 1: `t = 2·√(d/a)`, Profile 2: `t = √(16d/(3a))`, Profile 3: `t = 2·t_cap + (d - a·t_cap²)/V_CAP` (falls back to Profile 1 if cap not reached).
- Error handling: ambiguous Horizons name prints the disambiguation table from the exception message + tip to use numeric ID; other errors print the exception; both return early. Same-object detection: distance < 1e-9 AU triggers error and early return.
- **GUI output** (one combined table, preceded by persistent "Departure Date: YYYY-MM-DD" form label):
  - **Combined table** (3 rows — one per profile): Acceleration Profile | Max Vel | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Total Travel Time (Hours) | Total Travel Time
    - Max Vel: "N/A" for Profiles 1 and 2; "Y" or "N" for Profile 3.
- **GUI diagram tab** (via `DiagramToggleMixin`): "Solar System Map" — 2D top-down XY ecliptic view showing heliocentric positions of all 8 planets at the departure date as coloured dots with dashed reference orbit circles, the Sun as a gold star at the origin, the origin body as an orange ★, the destination body as a cyan ■, and a dashed line connecting origin to destination. Clicking any body opens a non-modal `_show_body_dialog` window with physical properties fetched from JPL Horizons.
- **Core function**: `core.calculators.compute_travel_time_solar_objects(origin, destination, accel_g, v_cap_pct, departure_date)` — `departure_date` is an ISO string `"YYYY-MM-DD"`; when `None`, defaults to today. Returns `departure_date`, `origin_xyz`, `dest_xyz`, `origin_id`, `dest_id`, and `planet_positions` in addition to the travel data. Planet positions fetched via `_fetch_planet_positions(epoch_jd)`; each planet dict includes `horizons_id`.

### Option 23: Travel Time Between 2 System Objs (Custom Thrust Duration) — `travel_time_custom_thrust_duration()`
- Prompts: `Enter Origin Planet/Satellite/Asteroid`, `Enter Destination Planet/Satellite/Asteroid`, `Enter Acceleration in # of G's` (> 0), `Enter Acceleration/Deceleration Duration` (> 0), `Enter Unit (H=Hours, D=Days, W=Weeks) [D]` (default Days), `Enter Max Velocity for Coast Phase (% of c, Default 3)` (blank → 3.0).
- Screen cleared after all user inputs and before JPL Horizons queries begin.
- Uses `_resolve_horizons_id()` and `_HORIZONS_ID_MAP` (same as option 31).
- **Iterative destination position estimation**: unlike option 31 which uses a single snapshot, this function queries the destination's position at the estimated arrival time and iterates until the travel time converges (change < 60 seconds, max 10 iterations). Origin position is fixed at departure epoch. Uses `_get_heliocentric_vectors()` with `epoch_jd` parameter.
- **Acceleration profile**: Accelerate for the user-specified burn duration, coast at the reached velocity, then decelerate for the same duration. If max velocity is reached before the burn ends, effective burn time is shortened to `v_max / a`.
- **Physics**:
  - `t_accel_eff = min(burn_seconds, V_CAP_MS / a_ms2)`
  - `v_coast = a_ms2 × t_accel_eff`
  - `d_accel = 0.5 × a_ms2 × t_accel_eff²`; `d_decel = d_accel`
  - `d_coast = d_total - 2 × d_accel`; `t_coast = d_coast / v_coast`
  - `t_total = 2 × t_accel_eff + t_coast`
- **Fallback**: if `2 × d_accel ≥ d_total` (distance too short for requested burn), falls back to midpoint profile: `t = 2·√(d/a)`, with an explanatory note in the output.
- **Time to Reach Max Velocity**: displayed if `burn_seconds > V_CAP_MS / a_ms2`; otherwise shows `N/A`.
- **GUI output** (two tables, preceded by persistent "Departure Date: YYYY-MM-DD" form label):
  - **Combined Phase + Summary table** (4 rows — Acceleration, Coast, Deceleration, Total): Phase | Duration | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Total Travel Time (Hours) | Total Travel Time. Only the Total row populates the last two travel-time columns; the first three phase rows leave them blank. Coast row shows "N/A" in the fallback case.
  - **Burn Profile table** (1 row): Req. Burn Duration | Eff. Burn Duration | Max Vel Cap | Max Vel Reached | Time to Max Vel | Coast Velocity
  - Iterations note rendered as italic label after Burn Profile table; fallback note rendered as italic label below that (when applicable).
- Same error handling as option 31: ambiguous Horizons name, lookup failure, same-object detection (distance < 1e-9 AU).
- **GUI diagram tab**: identical to option 22 — "Solar System Map" (2D top-down XY ecliptic view) with the same planet map, origin/dest markers, dashed travel line, and click-to-dialog interactivity. Planet positions are fetched at departure epoch `t0_jd`.
- **Core function**: `core.calculators.compute_travel_time_custom_thrust(origin, destination, accel_g, burn_duration_s, v_cap_pct, burn_value, burn_unit_label, departure_date)` — `departure_date` is an ISO string `"YYYY-MM-DD"`; when `None`, defaults to today. Returns `departure_date`, `origin_xyz`, `dest_xyz`, `origin_id`, `dest_id`, and `planet_positions` in addition to the thrust/phase data.

> **Phase O · O5b — Solar System Map date scrubber (GUI, opts 22/23).** The "Solar System Map" tab (`gui/panels/system_travel.py` `_SolarMapScrubber`) adds an **"▶ Animate over time"** button + slider + Play/Pause/Reset. On Animate it batch-fetches each animated body's real ephemeris over `[departure − span, departure + span]` via `core.calculators.compute_solar_ephemeris_track(body_ids, start_iso, stop_iso, n_steps=300)` — **one JPL Horizons range query per body** (`epochs` start/stop/step → the whole span in a single round-trip), run on a background thread. Scrubbing then re-offsets markers (`set_offsets`) from the cached track with **no per-frame network**. Animated bodies = origin + destination + in-view reference planets; the dashed departure trajectory line, orbit rings, and the Sun stay static (the readout labels it "trajectory fixed at departure"). Span (half) = `min(2 × longest trip-body period, 50 yr)` floored at 2 yr, period estimated `P ≈ r^1.5` yr. `compute_solar_ephemeris_track` returns `{dates, jds, bodies:{id:{x,y,z}}}` or `{"error"}`; it is **GUI-only** (no `query.py` subcommand). The exoplanet-archive **System Map** (opt-3 Map variant) has the sibling **O5a** scrubber, which is fully offline (Kepler from archive elements — `prepare_exoplanet_system_diagram`). See `docs/gui-architecture.md`.

## Route Planning (Phase I)

Three route-planning calculators in `core/calculators.py`, surfaced by the GUI **"Route Planning"** nav category
(`MultiStopJourneyPanel`, `NearestNeighborPanel`, `TradeRoutePlannerPanel` in `gui/panels/route_planning.py`). New,
**self-validating** functions (return `{"error": str}` for bad input) reusing the existing distance / Cartesian /
travel-time helpers. **No CLI menu entry**; originally GUI-only, they were later given `query.py` subcommands
(`multi-stop` / `nearest-neighbor` / `trade-route`) — see `docs/integration.md`.

### Panel descriptions (GUI, 2026-07-27)

Every one of the seven Route Planning panels carries a `DESCRIPTION` class attribute — a short
rich-text explanation of what the option does, what its inputs mean, what the result columns are,
and how it differs from its siblings. It is rendered by `_build_description_box` as a QLabel at the
**top of the results pane** (`_tables_widget`), so a finished Run shows it directly above its data,
and it is **hidden by default**, toggled by a **Show/Hide Description** button that `_button_row`
places between the Run and Show Diagrams buttons. The label is persistent: `_clear_tables_layout`
deletes from layout index `panel._tables_keep` **onward** (not from 0), so a Run — or an error
render — never deletes it and the button label stays in sync. GUI-only; no core or `query.py` change.

### Shared star resolution

All three resolve a typed star **name** via `_resolve_star_position(name)` (no picker/autocomplete — free-hand text,
like opts 17–21), in this order so most names never hit the network:

1. `"sol"`/`"sun"` → the origin `(0,0,0)` instantly (no DB, no SIMBAD), `sp_type="G2V"`.
2. **DB-first** — case-insensitive exact match on `star_systems.star_name` (offline; also yields the spectral type
   used for the map dot colour). Uses module-level `_parse_db_ra` / `_parse_db_dec` (sexagesimal → degrees) + `_to_cartesian`.
3. **SIMBAD fallback** — `compute_lookup_star_for_distance(name)` (live network, background thread); `sp_type=""` (grey dot).

A name matching neither returns `{"error": str}`. Resolved records become star-map-compatible dicts
(`{name, desig, sp_type, color, ly, x, y, z}`; `ly` = distance from Sol) via `_map_node`. `_load_star_systems_positions()`
reads the whole `star_systems` table as the candidate pool for the nearest-neighbor chain (empty table → the opt-50 message).

### Multi-Stop Journey — `compute_multi_stop_journey(star_names, velocity_input, use_times_c)`

Cumulative travel time along an ordered list of stops (same 3D-Euclidean + `format_travel_time` math as opts 20/21).
- Validate: `len(star_names) >= 2`; `velocity_input > 0`. `use_times_c` selects the unit (×c vs LY/HR); derives both
  via `HOURS_PER_JULIAN_YEAR` (8765.8128).
- Resolves every stop; **the first unresolvable stop fails fast → `{"error": "Stop N ('name'): <reason>"}`**. *(This
  deviates from the original "ask skip/abort" brainstorm — a pure core function cannot prompt and this is GUI-only, so
  the panel surfaces the error and the user edits the list and re-runs.)*
- Returns `{legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time,
  cumulative_time}], total_ly, total_hours, total_time, stars:[map dicts]}`.
- **GUI table**: Leg # | Origin | Destination | Distance (LY) | LY/HR | × c | Travel Time | Cumulative Time; totals label above.

### Nearest-Neighbor Chain — `compute_nearest_neighbor_chain(start_star, num_hops, max_ly)`

Greedy nearest-unvisited traversal from a start star over the `star_systems` candidate pool.
- Validate: `num_hops >= 1` (int); `max_ly > 0`. Resolve the start (`sol`/`sun` → origin); empty table → opt-50 error.
- **Self-exclusion**: the start's own DB row is dropped within `1e-3` ly so it can't be hop 1.
- Each step picks the closest unvisited star with `dist <= max_ly`; if none in range, sets `stopped_early=True` (not an error) and stops.
- Returns `{chain:[{hop, star_name, desig, sp_type, dist_from_prev_ly, cumulative_ly, ly_from_sol}], stars:[map dicts,
  start at index 0 (gold)], total_ly, stopped_early, start_name}`.
- **GUI table**: Hop # | Star Name | Designations | Spectral Type | Dist from Prev (LY) | Cumulative (LY) | Dist from Sol (LY); an amber italic note when `stopped_early`.

### Trade-Route Network (MST) — `compute_trade_route_mst(star_names)` *(stretch)*

Minimum spanning tree connecting a set of systems (Kruskal + `_UnionFind`).
- Validate: dedup case-insensitively, then `>= 2` systems; resolve each (first failure → `{"error": "'name': <reason>"}`).
- Builds all `N·(N−1)/2` Euclidean edges, sorts ascending, adds non-cycle-forming edges until `N−1` chosen.
- Returns `{nodes:[{name,x,y,z,sp_type,desig}], edges:[{from,to,distance_ly}] (N−1, ascending), total_ly, stars:[map dicts]}`.
- **GUI table**: From | To | Distance (LY); node/edge/total summary label above.

## Route Planning — Additional Options (Phase I-OPTS — GUI + `query.py`)

Four more self-validating route planners in `core/calculators.py`, added **alongside** I1–I3 (none replaced),
surfaced as four new GUI panels in the same **"Route Planning"** nav category
(`OptimalTourPanel`, `JumpRoutePanel`, `JumpNetworkPanel`, `FarthestFirstPanel` in `gui/panels/route_planning.py`).
They reuse the same `_resolve_star_position` (DB-first → SIMBAD), `_load_star_systems_positions` candidate pool,
`_map_node`, and the dark-navy Star Chart `routes=` overlay. All four are exposed as `query.py` subcommands
(`optimal-tour` / `jump-route` / `jump-network` / `farthest-first`); the original I1/I2/I3 planners were likewise
backfilled (`multi-stop` / `nearest-neighbor` / `trade-route`), so **all seven Route Planning options now have both a
GUI panel and a `query.py` subcommand** — see `docs/integration.md`. These four also carry the Show/Hide Description
box (see **Panel descriptions** under Phase I above — it covers all seven panels).

Shared helpers (module-level): `_node_dist(a,b)` (3D Euclidean); `_merge_endpoint(pool, endpoint)` (reuse a pool row
matched by name or within `1e-3` ly, else append); `_SpatialGrid(nodes, cell)` — a uniform 3D grid (cell = the jump
radius) giving O(neighbours) within-radius queries via `grid.neighbors(i, max_dist)`, so B/C traverse the **~256k-row**
`star_systems` table in ~2–5 s instead of the O(n²) all-pairs build (which was ~3.5 h — see the note below);
`TIER_COLORS` (tier 0 = start gold). B's Dijkstra/BFS and C's BFS expand nodes lazily over the grid (Dijkstra/BFS exit
early once the target pops). B/C still run in a background thread.

> **Scale note:** `star_systems` (option 50, out to ~100 pc) holds **~256k rows** (256,003 measured 2026-07-29;
> ~238k when the grid was built), not the "few thousand" first assumed.
> An all-pairs adjacency build is ~2.8×10¹⁰ pairs (≈3.5 h) and would never complete — hence the spatial grid. The
> solar neighbourhood is genuinely sparse (only Proxima/α Cen/Barnard's within ~6 ly of Sol), so a small `max_jump_ly`
> legitimately yields a tiny reachable set / `reachable=False` for a 20-ly target — that is a correct answer, not a bug;
> raise the jump range to connect more of the catalogue.

### A — Optimal Tour — `compute_optimal_tour(star_names, velocity_input, use_times_c, closed=False)`

Shortest-total-distance visit order for a set of stars (nearest-neighbor seed from the **fixed** first stop, then
**2-opt** local search; the start never moves). `closed=True` adds the return-to-start leg.
- Validate: case-insensitive dedup → `>= 2` distinct stars; `velocity_input > 0`; first unresolvable star →
  `{"error": "'name': <reason>"}`.
- Returns `{legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time,
  cumulative_time}], total_ly, total_hours, total_time, naive_total_ly, optimized_total_ly, saved_ly, saved_pct,
  closed, stars:[map dicts in optimized order]}` (`legs` includes the wrap leg when `closed`).
- **GUI table**: Leg # | Origin | Destination | Distance (LY) | LY/HR | × c | Travel Time | Cumulative Time; a
  totals line reports optimized vs as-typed distance and the saved ly / %.

### B — Jump-Range Pathfinding — `compute_jump_route(origin, destination, max_jump_ly, optimize="distance", via=None)`

Route origin→destination through intermediate stars, each single jump ≤ `max_jump_ly`. `optimize="distance"` →
**Dijkstra** (min total ly); `"jumps"` → **BFS** (fewest jumps). Graph = pool ∪ {origin, dest, *waypoints*} (deduped).
- Validate: `max_jump_ly > 0`; `optimize ∈ {distance, jumps}`; both endpoints resolvable; same endpoint (name or
  within `1e-3` ly) → error. Waypoints: see **Required waypoints** below.
- An unreachable destination is a **clear result, not an error**: `reachable=False`, empty `route`,
  `unreachable_leg={from,to}` naming the hop that failed, and `stars` = **every terminal**
  (origin + waypoints + destination) so the chart still draws the requested stars. Without waypoints that is the
  historical `[origin, dest]`.
- Returns `{origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly,
  route:[{jump, from, to, jump_ly, cumulative_ly, waypoint}], max_jump_ly, stars:[map dicts along the route],
  via, via_legs, unreachable_leg}`.
- **GUI table**: Jump # | From | To | Jump Dist (LY) | Cumulative (LY); amber "unreachable" note when
  `reachable=False`, naming the hop from `unreachable_leg`. A **"Via (optional, comma-separated)"** field sits
  between Destination and Max Jump (blank = no waypoints); a waypointed route lists the chosen visit order above
  the table and prefixes each waypoint-arrival row's **To** cell with **◆** (from `route[i]["waypoint"]`).

#### Required waypoints (`via=`)

`via` is `None` or a list of star names the route **must** pass through — an **unordered set** (D2): the planner
picks the cheapest visit order under whatever `optimize` selects, so typing them in the expensive order still
returns the cheap one. Implemented by the `_route_through` helper in `core/calculators.py`, shared by **all three**
jump-route planners (plain + the two dust forks — see "Waypoints on the forks" under Dust-weighted variants below),
each passing its own `edge_cost`. It is a fixed-endpoint Hamiltonian path over the **metric closure** of the
terminals:
**stage 1** runs the existing `_grid_search` between each terminal pair (each unordered pair once — costs are
symmetric to within float-summation ULPs, so the stored path is reversed for the other direction; the direct
origin↔destination pair is skipped, since with ≥1 waypoint no permutation uses it); **stage 2** brute-forces the
`k!` orders and breaks ties on the permutation tuple (deterministic — ties are common under `optimize="jumps"`,
whose objective is a small integer; this is also why `via` must be an ordered **list/tuple** — a set would make
the tie-break vary between interpreter runs); **stage 3** stitches the winning legs, de-duplicating the junction
node at each seam. **An infinite pair short-circuits the whole closure.** Reachability is an equivalence relation on an undirected
graph, so one unreachable pair means those two terminals are in different components and *no* visit order can
work — stage 1 returns `unreachable_leg` at once instead of searching the rest. This is load-bearing, not tidy:
`_grid_search`'s early exit fires only on **success**, so an unreachable pair drains the entire reachable
component every time it is searched, and without the short-circuit one stranded waypoint would cost k+1 full
sweeps. Pairs are ordered origin-first, so a terminal disconnected from the origin is caught on the first
search (measured: a stranded Vega at `max_jump 4.5` over the 256k pool returns in ~8 s). Stranding a route with
a far-flung waypoint is a documented, expected outcome, so this is a likely path rather than an exotic one.

The **pairwise** closure is deliberate and measured: the alternative (one full single-source
sweep per terminal, k+2 runs) was built and timed against the real 256k-row pool — Sol → 38 Vir via 70 Vir at
`max_jump 20` took **227 s** as sweeps vs **4.96 s** as pairs, because `_grid_search` early-exits when the target
pops while a sweep must settle the whole reachable component. Cost at the cap is still real (44 searches; ~12 s
measured at k=3, `max_jump 20`), which is why the GUI runs it on a background thread. All terminals are merged into the node list **before** `_SpatialGrid` is constructed — the grid indexes
at construction, so a later append is invisible to `neighbors()`.

Three always-present output keys (`[]`/`[]`/`null` when unused): **`via`** — resolved waypoint names in the
**chosen** visit order when `reachable`, and in the **requested** (typed) order when not, since no order was
chosen (`via_legs` is `[]` there for the same reason); **`via_legs`** — `[{from, to, jumps, ly}]` per waypoint-to-waypoint leg; **`unreachable_leg`**.
Plus an always-present **`waypoint`** boolean on every `route[]` row, `true` on the row that *arrives at a waypoint
at a leg boundary* — flagged by route index, not by name match, so a leg incidentally passing back through a
waypoint is not flagged. Invariant: `count(waypoint) == len(via)`. `route[]` stays flat and continuously numbered
across the whole trip.

Validation (all `{"error"}`): more than **8** waypoints (`MAX_VIA_WAYPOINTS`, enforced *before* resolution so an
over-cap list fires no SIMBAD lookups); `via` a bare string or a list holding a non-string; an unresolvable
waypoint → `"Waypoint N ('…'): <reason>"` (1-based over the whitespace-stripped list, matching
`compute_multi_stop_journey`'s "Stop N"); and any two terminals that resolve to **the same post-merge node index**
— checked on indices, not on the resolved records, because `_merge_endpoint` matches a pool row by name *or*
within 1e-3 ly, so two terminals up to 2e-3 apart can still collapse onto one node. `"Sol"`/`"Sun"` therefore
collide correctly even though the name arm misses. **One deliberate behaviour change on the `via=None` path**:
that same post-merge check now also catches an *origin/destination* pair that collides only after merge (each
within 1e-3 ly of one pool row but >1e-3 from each other, so the older pre-merge check missed them). It used to
return a degenerate `reachable=True, jumps=0, route=[], stars=[one node]`; it now returns
`"Origin and destination are the same star."`

**Accepted caveats (documented, not bugs).** The stitched route is **not a simple path** — legs may reuse stars, so
a star can appear **twice** in `route[]`/`stars[]`. This is `jump-route`'s first repeated star (`multi-stop` /
`optimal-tour` already do it): `len({s["name"] for s in stars}) != len(stars)` is now possible, and any
`{s["name"]: s}` index silently loses route position. Per-leg optimal ≠ globally optimal; forcing node-disjointness
is NP-hard. On the charts a revisited star is labelled twice at identical coordinates, and if the route revisits
the **origin** only index 0 gets the gold ★. Finally, two *aliases* of one star that resolve via different paths
(DB vs SIMBAD coordinates) can land > 1e-3 ly apart and merge as two nodes — pre-existing, but waypoints are the
first feature where typing an alias is likely.

### C — Jump Network / Reachability — `compute_jump_network(start, max_jump_ly, max_jumps=None)`

BFS reachability tiers from `start` at jump range `max_jump_ly` (each reachable star → its minimum jump count).
- Validate: `max_jump_ly > 0`; `max_jumps` is `None` or an int `>= 1`; start resolvable; empty pool → the opt-50 message.
- Returns `{start_name, max_jump_ly, max_jumps, max_tier, reachable_count, total_in_pool, unreachable_count,
  tiers:[{jumps, stars:[{star_name, desig, sp_type, dist_from_start_ly, ly_from_sol}]}], stars:[map dicts]}`. `stars`
  carry a per-tier `color` (overriding spectral colour) so the chart paints reachability tiers; `reachable_count`
  includes the start, `unreachable_count` is over the original `star_systems` rows.
- **GUI**: tier-grouped table (Jumps | Star Name | Designations | Spectral | Dist from Start | Dist from Sol) + a tier
  colour legend; the map is tier-coloured nodes (no edges — scales to large pools).

### D — Farthest-First Coverage — `compute_farthest_first_chain(start, num_stops, max_reach_ly=None)`

De-clustering coverage: each step picks the unvisited star **farthest** from the visited set (optionally still within
`max_reach_ly` of some visited star). The opposite of the nearest-neighbor chain's clustering.
- Validate: `num_stops` int `>= 1`; `max_reach_ly` is `None` or `> 0`; start resolvable; empty pool → opt-50 message.
  The start's own row is self-excluded within `1e-3` ly. No star within reach → `stopped_early=True` (not an error).
- Returns `{chain:[{step, star_name, desig, sp_type, sep_to_visited_ly, dist_from_start_ly, ly_from_sol}],
  tree_edges:[{from_index, to_index}], stars:[map dicts, start at 0], widest_ly, stopped_early, start_name}`.
  `tree_edges` is the exploration tree (each new star links to the nearest visited node) — drawn dashed on the map.
- **GUI table**: Step | Star Name | Designations | Spectral Type | Sep to Visited (LY) | Dist from Start (LY) |
  Dist from Sol (LY); amber note when `stopped_early`.

### Route map overlay — `core.viz.prepare_route_map(result)` + the Star-Chart `routes=` param

`prepare_route_map(result)` normalizes any Route Planning result into `{stars, edges:[{x1,y1,z1,x2,y2,z2,label,style}],
edge_style}` — `"dashed"` consecutive legs for the ordered routes (I1/I2; label = leg distance / hop ②③…), `"solid"`
MST edges for I3 (label = edge ly). The Phase I-OPTS results are handled too: **A** (optimal tour) → dashed consecutive
+ a wrap edge when `closed`; **B** (jump route) → dashed jumps (no edges when unreachable); **D** (farthest-first) →
dashed `tree_edges` (non-consecutive, labelled by step); **C** (jump network) → **nodes only** (`edge_style="none"`),
the per-tier `color` on each star carrying the reachability tiers. `{"error"}` passes through.

The maps are the **dark-navy GCNS "Star Chart" + "Star Chart 3D"** diagrams (`make_star_chart_canvas` /
`make_star_chart_3d_canvas` in `gui/visualizations/plot_helpers.py`), which gained an optional trailing
`routes=None` kwarg (additive — existing opts-18/19 / GCNS callers are unaffected). The panel shifts coordinates so the
route's origin/start/center sits at the chart origin (gold ★), with distance rings measured from it and
`limit_ly = max node distance × 1.1`. Route lines stay visible at all zooms; the per-segment labels follow the chart's
existing **zoom-driven label decluttering** (shown once the visible half-range drops below ~15 ly), so a busy route
starts uncluttered and reveals labels on zoom.

**Route-chart refactor (`completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` Phases 1–2, built 2026-07-27).** `_add_route_chart_tabs` no
longer calls the canvases directly — both tabs are built by the **shared opt-18/19 `_build_iso_chart_tab`**
(`gui/panels/diagram_tabs.py`), which gained a `routes=None` passthrough (and so did `_build_star_chart_3d_tab`,
retiring the duplicate private `_route_chart_3d_tab`). All seven route charts therefore now carry the **O16 per-class
legend filter**, the **O17 travel-time isochrone control** (rings centred on the route's start, so they read as travel
time *from* it) and the 3D viewpoint presets. Two deliberate exceptions: **`JumpNetworkPanel` passes
`legend_filter=False`** (its dots carry per-tier, not spectral, colours — the class-grouped legend would mislabel
them; its own tier-swatch legend stands), and **`label_max_ly`** is raised only for sparse routes (≤ 25 nodes), since
Jump Network can return thousands. **O15 row↔map linking** is wired on the three star-per-row panels
(Nearest-Neighbor, Farthest-First, Jump Network) via an additive `name_col` on the linking helpers — those tables lead
with an index column (`Hop #`/`Step`/`Jumps`), so they pass **1**; the default 0 keeps opts 18/19 and the two-star maps
unchanged. The leg-shaped `From|To` panels pass no `link_view`, as opts 20/21 already did. **O18 Find-star box (Route-Find, 2026-07-31)** — the last opt-18/19 chart feature the
refactor left behind — is now on all seven too. Unlike opts 18/19 it searches the **route star
list**, not the result table (`panel._find_rows`, deduped by name), which is what covers the four
leg-shaped `From|To` panels that pass no `link_view`; and it rings each canvas **directly** rather
than via table selection, which those panels have no path to. The start ★ is excluded, and Jump
Route's `reachable=False` chart passes `find_box=False` **only when it carries no waypoints** — with
`--via` stars that chart holds k+2 terminals, so there is something to find (2026-07-31). The shared implementation
moved to `gui/panels/diagram_tabs.py` (re-exported from `distance_stars.py`, which imports
`route_planning` and so could not be imported back). Tests: `tests/test_route_find.py`. **Phase 3** then deleted the
`core.calculators._star_map_color` second palette: dot colours (including the `stars[].color` these planners return
through `query.py`) now come from the single `core.shared.sp_color`, so a star reads the same on every panel. Four
values moved — G/M/D and the unknown grey; see `docs/integration.md` for the consumer-facing note.

**Phase O8 — two-star maps (opts 17/20/21), rebuilt Sol-centered 2026-07-26.** Originally these reused the `routes=`
overlay above and centred on star-1/origin. They are now **Sol-centered with full opt-18/19 parity**.
`gui/panels/route_planning.py::_two_star_route_map(result, kind)` converts a two-star result (`kind="distance"` for opt
17's `star1_info`/`star2_info`, `"travel"` for opts 20/21's `origin_info`/`dest_info`) into `{stars, edges}` where **Sol
is `stars[0]` at the origin** — `make_star_chart_canvas` paints the first entry as the gold ★ only when it sits at
(0,0,0), which is what makes these charts read exactly like opts 18/19 — and the two searched stars keep their **true
heliocentric coordinates**, coloured by spectral class from the additive `sp_type` that
`compute_lookup_star_for_distance` now returns. An endpoint that *is* Sol/Sun becomes the centre node rather than being
duplicated. **`edges` is always empty**: the dashed connecting leg was dropped (the result tables already carry the
distance / travel time), so no `routes=` passthrough is needed.
`add_two_star_chart_tabs(panel, result, kind, link_view=None)` computes `limit_ly = max node distance × 1.1` and builds
both tabs with the **same `_build_iso_chart_tab` the opt-18/19 panels use** (`gui/panels/diagram_tabs.py`), so
**"Star Chart"** + **"Star Chart 3D"** carry the O16 per-class legend filter, the O17 travel-time isochrone control, the
click-info box, and the 3D viewpoint presets. `link_view` wires O15 row↔map linking — opt 17 passes its 2-row table
(star names in column 0); opts 20/21 omit it (their table is Origin|Destination-shaped) and a click just shows the info
box. Because these charts hold only two or three dots, they also pass `label_max_ly` (the additive Star-Chart canvas kwarg) so the star names stay visible at any zoom instead of following the shared 15 ly decluttering threshold opts 18/19 need. Used by `DistanceBetweenStarsPanel` (17) and the two `TravelTimeStars*` panels (20/21), all `DiagramToggleMixin`.

### Dust-weighted variants (Phase T2 Part B — `core/dust_routing.py`)

Five of the planners above — `compute_jump_route` / `compute_optimal_tour` / `compute_multi_stop_journey` /
`compute_nearest_neighbor_chain` / `compute_trade_route_mst` — have **dust-weighted forks** in
`core/dust_routing.py` (`compute_*_dust`), surfaced by the `query.py` `--weight {distance,dust}` flag (default
`distance` → these unchanged functions; `dust` → the fork). The fork reuses the same resolution / pool /
`_SpatialGrid` helpers but weights each edge by the **integrated dust extinction A_V** (`core/dust.py`) instead
of 3D distance — least-extinction corridors, with per-leg + cumulative A_V and a distance-optimal comparison
(`extra_ly`/`saved_av`). **Reachability stays geometric** (`--max-jump`/`--max-ly` are unchanged; dust only
weights existing edges). The shared Dijkstra/BFS was extracted into `calculators._grid_search(... edge_cost)`
(distance passes `edge_cost=lambda u,v,w: w` → byte-identical, guarded by the route tests). It is an **optional,
WSL/Linux-only** path (needs the `dustmaps` extra). See `docs/integration.md` (Dust-weighted routing) and
`completed_plans/PHASE_T_PLAN.md`.

**Waypoints on the forks (2026-07-31).** The two `jump-route` forks (`compute_jump_route_dust` /
`compute_jump_route_blend`) take the same additive `via=None`, sharing `calculators._route_through` and passing
their own `edge_cost` — so the waypoint **visit order is chosen under the weight the caller selected** (least
A_V for dust, blended for blend), not under distance. Their front half is the shared `_jump_setup` (validate →
resolve → pool → merge → post-merge terminal check, mirroring `compute_jump_route`'s order and messages) and
their `via_legs` rows carry **`a_v`** alongside `ly`. The `dref` distance-optimal comparison threads `via`
through, so `extra_ly`/`saved_av` compare the constrained dust route against the **constrained** distance route
— without it the two sides are different problems and both numbers are meaningless. The other three forks
(tour/multi-stop/nearest-neighbor/MST) take no `via`: waypoints are a `jump-route` concept, since those
planners already visit a caller-supplied star set.

## Detectability & Relativistic Calculators (Phase T1b)

Five new pure-math `query.py`-only calculators in `core/calculators.py` for the sibling worldbuilding repo's
survey-bias / STL-travel research (alongside B1 `tidal-heating` and C2 `kozai-lidov`, which live in
`core/equations.py`). All **self-validating** (Phase-H/P contract: curated `{"error"}` exit 1, argparse exit 2).
No network, no GUI. Full per-field contract + anchors in `docs/integration.md`.

- **`compute_rv_semi_amplitude(planet_mass_earth, star_mass_solar, period_days=None, sma_au=None, ecc=0, inclination_deg=90)`** (A1) — Lovis & Fischer 2010 RV semi-amplitude `K`. Input mass in Earth masses → **M_Jup internally** (the 28.4329 m/s constant is per-M_Jup). Exactly one of period/sma (Kepler III derives the other). → `{k_ms, period_days, sma_au, ecc, inclination_deg, …}`. Anchor: Earth→Sun ≈ 0.0895 m/s.
- **`compute_transit_signal(planet_radius_earth, star_radius_solar, sma_au=None, period_days=None, star_mass_solar=None)`** (A2) — Winn 2010 depth `(Rp/R*)²`, geometric prob `R*/a`, duration `(P/π)·arcsin(R*/a)`. `--sma-au` alone leaves period/duration `null`; `--period-days`+`--star-mass-solar` derives `a`. → `{depth_ppm, depth_frac, transit_prob, duration_hours, sma_au, period_days, …}`. Anchor: Earth→Sun ≈ 83.9 ppm / 0.0047 / ~13 h.
- **`compute_astrometric_signal(planet_mass_earth, star_mass_solar, sma_au, distance_pc)`** (A3) — `α=(Mp/M*)·(a/d)`; **microarcsec** headline + arcsec echo. → `{signal_microarcsec, signal_arcsec, …}`. Anchor: Jupiter→Sun @10 pc ≈ 496 µas.
- **`compute_direct_imaging(sma_au, distance_pc, planet_radius_earth, albedo=0.3, telescope_diameter_m=None, wavelength_um=None)`** (A4) — sep `a/d`, reflected contrast `A_g·(Rp/a)²` (Rp→AU), optional `IWA=λ/D` (1·λ/D convention; real coronagraphs use 1–4 λ/D) + `resolvable` flag (both `null` unless both telescope args given; only one → error). → `{angular_sep_arcsec, contrast_reflected, iwa_arcsec, resolvable, …}`. Anchor: Earth→Sun contrast ≈ 5.4e-10.
- **`compute_relativistic_brachistochrone(accel_g, distance_ly)`** (D1) — constant **proper**-acceleration flip-and-burn (MTW), lifting the 3%c Newtonian cap of options 22–23/29–30. `X=arccosh(1+a·(D/2)/c²)`; coordinate time `2(c/a)sinh X`, proper time `2(c/a)X`, midpoint `peak_velocity_c=tanh X`, `peak_lorentz_factor=cosh X`. → `{coord_time_yr, proper_time_yr, peak_velocity_c, peak_lorentz_factor, …}`. Anchor: 1 g over 4.37 ly → coord ≈ 6.0 yr, proper ≈ 3.58 yr, peak ≈ 0.95 c; converges to the Newtonian `2√(D/a)` at low speed. Constants added: `_M_JUP_EARTH`, `_M_SUN_EARTH`, `_R_SUN_AU`, `_R_EARTH_AU`, `_ARCSEC_PER_RAD`, `_SEC_PER_JULIAN_YEAR`, `_LY_M`.
