# Science and Science Fiction Feature Documentation

Options 11–16. All features here display data from local CSV files or hardcoded tables. No external API calls. Lowest change frequency of all feature groups.

> **`query.py`:** options 11–13 are also exposed as subcommands — `solar-system` (11), `main-sequence` (12), and `sol-regions` (13) — see `docs/integration.md`. The Honorverse tables (options 14–16) remain GUI/CLI-only.

## Science Features

### Option 11: Solar System Planet/Dwarf Planets/Asteroids — `solar_system_data_tables()`
- Displays four sequential data tables from CSV files in the project directory.
- **Solar System Planets Data** — from `planetInfo.csv`; sorted ascending by Semimajor Axis; columns: Planet Name, Mass (J), Diameter (J), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity, Moons. AU values formatted as `{v:g} ({v × 8.3167:.3f} LM)`.
- **Moon Data tables** — from `moonInfo.csv`; grouped by planet in order: Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto; each planet's moons sorted ascending by SemiMajor Axis (km); columns: Satellite Name, Diameter (km), Mass (kg), Perigee (km), Apogee (km), SemiMajor Axis (km), Eccentricity, Period (days), Gravity (m/s^2), Escape Velocity (km/s).
- **Solar System Dwarf Planets Data** — from `dwarfPlanetInfo.csv`; sorted ascending by Semimajor Axis; same columns as planets table but header row says "Dwarf Planet Name" and Mass is in Earth masses.
- **Solar System Major Asteroids Data** — from `asteroidsInfo.csv`; sorted ascending by Semimajor Axis; columns: Asteroid Name, Diameter (KM), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity.
- **GUI (`SolarSystemPanel`)**: the four data tabs (Planets, Moons, Dwarf Planets, Asteroids) are unchanged. **Phase O O7** makes it a `DiagramToggleMixin` with a **Show Diagrams** toggle adding two orbital-diagram tabs via `core.viz.prepare_solar_system_orbits` → `make_orbits_canvas`: **Orbital Diagram** (a `QComboBox` over *Planets* / *Dwarf Planets + Asteroids*) and **Moon Systems** (a `QComboBox` per planet; moon SMAs km→AU via ÷1.496e8, with a secondary km top axis). No new menu option, no CLI change.

### Option 12: Main Sequence Star Properties — `main_sequence_star_properties()`
- Reads `propertiesOfMainSequenceStars.csv` and displays all rows in a single table.
- Columns: Spectral Class, B-V, Teff (K), Abs Mag Vis, Abs Mag Bol, BC, Lum, R, M, p (g/cm3), Lifetime (years).

### Option 13: Sol Solar System Regions — `sol_solar_system_regions()`
- Displays all Star System Regions output tables for the Sun using hardcoded solar constants: `vmag = -26.74`, `boloLum = -0.07`, `temp = 5778 K`, `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`.
- Parallax back-computed from absolute magnitude: `plx = 1000 / (10^((vmag - absMag + 5) / 5))` ≈ 206265 mas.
- Calls the same shared display helpers documented in `docs/star-system-regions.md`: `_display_star_system_properties()`, `_display_stellar_properties()`, `_display_star_distance()`, `_display_earth_equivalent_orbit()`, `_display_solar_system_regions()`, `_display_alternate_hz_regions()`, `_display_calculated_hz()`.
- **GUI (`SolRegionsPanel`)**: seven data tabs (built once at construction; no inputs). **Phase O O6** makes it a `DiagramToggleMixin` with a **Show Diagrams** toggle adding the three ring tabs opts 9/10 have — **HZ Diagram**, **System Regions Diagram**, **Alternate HZ Diagram** — via the shared `gui/panels/star_regions.py::add_region_diagram_tabs` over the `compute_sol_regions()` dict (the same `prepare_hz_diagram` / `prepare_system_regions_diagram` / `prepare_alt_hz_diagram` preps; O6 added no new core code). The seven data tabs are unchanged. (The **HZ Diagram** tab later gained the app-wide **Phase 5 Rings/Strip toggle** — Sol is a single star, so its Strip shows the HZ bands with no planet markers; see `docs/star-databases.md`.)

## Science Fiction Features

### Option 14: Honorverse Hyper Limits by Spectral Class — `honorverse_hyper_limits()`
- Reads `spTypeHyperLM.csv` (no header; columns: Spectral Class, Light Minutes).
- Converts LM → AU: `au = lm / 8.3167`.
- Output table columns: Spectral Class | Light Minutes (2dp) | AUs (4dp).
- **GUI (`HonorverseHyperPanel`)**: the table is unchanged. **Phase O O10a** makes it a `DiagramToggleMixin` with a **Show Diagrams** toggle adding a **"Hyper Limits"** bar-chart tab (`core.viz.prepare_hyper_limits` → `make_hyper_bar_canvas`): all 44 classes as horizontal bars in LM with a secondary AU top axis, coloured by spectral class (hottest at top), scroll-wrapped.
- **Phase O O10b** (opts 8/9, not 14): `core.science.compute_hyper_limit_for_spectral_type(sp_type)` resolves a star's hyper limit from this table via the ceiling rule (O/B/A single-entry; F0–M9 subtyped, smallest subtype ≥ requested, falling to the next cooler letter, clamped to M9; `None` for a non-OBAFGKM type). Used by the Star System Regions hyper-limit ring — see `docs/star-system-regions.md`.

### Option 15: Honorverse Acceleration by Mass Table — `honorverse_acceleration_by_mass()`
- Hardcoded table of ship mass ranges and acceleration values (no external data file).
- Output table columns: Ship Mass (tons) | Warship (Normal Space) | Merchantship (Normal Space) | Warship (Hyper Space) | Merchantship (Hyper Space).
- Six rows covering mass ranges from FG/DD (< 80,000 tons) through SD (7,000,000–8,499,999 tons).

### Option 16: Honorverse Effective Speed by Hyper Band — `honorverse_effective_speed()`
- Hardcoded data; displays two tables. The columns below describe the **core/GUI** rendering (`core.science.compute_honorverse_effective_speed` → `HonorverseSpeedPanel`); the CLI function has its own stale inline copy — see the K0 note.
- **Table 1 "Effective Speed by Hyper Band"**: Alpha–Iota bands; columns: Band | Translation Bleed-Off | Velocity Multiplier | Warship (xC) | Merchantship (xC). Speeds shown as `{xc} ({xc / 8765.8128:.5f} ly/hr)`. Iota merchantship speed shown as "Currently Unattainable". Footnote about merchantmen not normally using Epsilon–Iota bands.
- **Table 2 "Effective Speed by Hyper Band (Expanded)"**: Alpha–Omega bands (24 total); columns: Band | Translation Bleed-Off | Velocity Multiplier | Warship (xC) | Merchantship (xC) — the same five as Table 1 (2026-07-27; it previously showed only Band | Warship | Merchantship). Same speed format as Table 1. Bleed-off values above Iota are **extrapolated**, suffixed `†` with a footnote naming the decay (see "Band-table formulas" below).
- **GUI (`HonorverseSpeedPanel`)** — layout fix, 2026-07-27: both tables are sized to exactly header + rows (`gui.panels.hypatia_tab.fit_table_height`) and stacked inside one `QScrollArea`, so the panel scrolls as a whole. Previously they were plain `QTableView`s in the panel's `QVBoxLayout`, which splits vertical space between them — the 9-row table was padded with dead space while the 24-row table was squeezed into a private scrollbar. Tests: `tests/test_honorverse_speed_panel.py` (columns + † marking + the fitted-height/scroll-area layout; all six fail against the pre-fix code). **The CLI's opt 16 is unchanged** — see the source-of-truth note under K0.

#### Band-table formulas (2026-07-27)

Both extrapolated columns turned out to follow exact laws that regenerate every canon
Alpha–Iota value, so the bands above Iota are the same rule continued rather than
free-hand numbers. They are *different kinds* of law — neither derives from the other.

- **Velocity multiplier — arithmetic, 7-band period.** `honorverse_band_multiplier(n)` =
  `62 + 4938·⌊k/7⌋ + _MULT_CYCLE[k mod 7] + (295 if n ≥ 9)`, with `k = n−1` and
  `_MULT_CYCLE = (0, 705, 1411, 2116, 2822, 3527, 4232)`. The canon Alpha→Theta ramp gains
  exactly **+4938 per seven bands** (avg step 705.43, published as the 705/706 alternation);
  Iota's canon break to 6000 is a **one-time +295** carried by every later band. This
  reproduces the nine canon multipliers and regenerates all 24 stored `warship_xc` /
  `merchant_xc` values exactly, so `_HONORVERSE_EXPANDED_MULTIPLIERS` is now **computed**
  from it rather than typed out. `warship = 0.6 × multiplier`, `merchant = 0.5 × multiplier`
  holds across all 24 bands.
- **Translation bleed-off — geometric decay.** `honorverse_band_bleed_off(n)` =
  `round(92 × 0.9215^(n−1))` percent, a ~7.85%-per-band decay (log-linear least-squares fit
  over the nine canon points: 91.93·0.92150^(n−1), max residual 0.33 pp — every value rounds
  to its published integer: 92 85 78 72 66 61 56 52 48). Canon publishes **no** bleed-off above
  Iota, so Kappa 44% … Omega 14% are derived; each expanded band carries a
  **`bleed_off_canon`** boolean so consumers can tell published from extrapolated.

Both formulas are pinned against the canon anchors in `tests/test_honorverse_expansion.py`.

## Honorverse Expansion (Phase K — GUI-only interactive calculators)

Three interactive Honorverse calculators (panels in `gui/panels/honorverse.py` under the existing "Science Fiction" nav category, alongside the three static tables above). Pure math, no network/DB-write. All three core functions **self-validate** (return `{"error": str}` for bad input). See `completed_plans/PHASE_K_PLAN.md`.

### Data centralization (K0)

The band/mass tables are now module-level constants in `core/science.py` — `_HONORVERSE_ACCEL_BANDS` (6 mass bands, **numeric** g-values + explicit `mass_min`/`mass_max` boundaries), `_HONORVERSE_BANDS` (Table 1, Alpha–Iota), `_HONORVERSE_EXPANDED_BANDS` (Table 2, 24 bands) — the single source of truth shared by the opt-15/16 **core** display functions (`compute_honorverse_acceleration_table` formats the numeric g-values back to the `"550 g"` strings it always returned) and the K calculators. Accessors `get_honorverse_accel_bands()` / `get_honorverse_expanded_bands()` expose them; `honorverse_band_multiplier()` / `honorverse_band_bleed_off()` expose the two generating formulas (see "Band-table formulas" above). Every GUI panel reads these.

> **Stale CLI copy (`main.py`, not fixed — the CLI menu is deprecated).** `main.py::honorverse_effective_speed()` (opt 16) never got the K0 centralization: it still carries its **own inline `band_data`/`cal_data` literals**, and that copy predates the 2026-06-13 Iota correction (its expanded Iota reads `3423.0` / `2852.5` against the corrected `3600.0` / `3000.0`). So the CLI opt 16 prints **stale numbers** and lacks the two Table-2 columns; `core.science` + the GUI are correct. Left alone deliberately — porting opt 16 onto `compute_honorverse_effective_speed()` would be the fix if the CLI is ever revived.

**Data note:** the 24-band Table 2 was corrected (2026-06-13) — Iota re-anchored to the canon `6000×` multiplier (Pearls of Weber), with `warship = 0.6 × multiplier`, `merchant = 0.5 × multiplier`; a prior −0.3 merchant transcription drift (Pi→Omega) is gone. Table 1's Iota stays "unattainable" (0) by design — Iota is unreachable in canon; bands above Iota are an extrapolation (whose generating rule was recovered on 2026-07-27 — see "Band-table formulas" above).

### K1 — `compute_hyper_translation_time(distance_ly, ship_type)` (`HonorverseHyperTimePanel`)

Travel time for a distance across all 24 hyper bands. `ship_type ∈ {"warship", "merchantship"}` (case-insensitive). Per band: `speed_ly_hr = speed_xc / 8765.8128`, `travel_hours = distance_ly / speed_ly_hr`, `travel_time = _format_travel_time(...)` (a 0-speed band → `"N/A"`). Returns `{distance_ly, ship_type, bands:[{band, speed_xc, speed_ly_hr, travel_hours, travel_time, note}], footnote}`. The merchant `*` bands (Epsilon onward) are flagged via a footnote, not dropped. Validation: `distance_ly > 0`, valid ship type.

### K2 — `compute_impeller_wedge(ship_mass_tons, ship_type, wedge_power_pct)` (`HonorverseImpellerPanel`)

Effective acceleration + max velocities at a wedge-power setting. Selects the mass band by `mass_min ≤ tons ≤ mass_max` (a mass above the heaviest band **clamps** to it, `clamped=True` — not an error). `effective_accel_g = base_accel_g × power/100`; `max_vel_normal_xc = (0.8 warship | 0.6 merchant) × power/100`; `time_to_max_vel` from `t = max_vel·c / (eff·g)`. Returns `{ship_mass_tons, mass_band, clamped, ship_type, wedge_power_pct, base_accel_g, effective_accel_g, max_vel_normal_xc, max_vel_hyper_xc, time_to_max_vel}`. Validation: mass > 0, `0 < power ≤ 100`, valid ship type. **GUI:** a `QSlider` for power with live recompute (no button).

### K3 — `compute_missile_intercept(launcher_vel_xc, missile_accel_g, missile_delta_v_xc, target_vel_xc, range_lm)` (`HonorverseMissilePanel`)

In **`core/calculators.py`** (reuses `_G_MS2`/`_C_MS`/`_M_PER_LM`). 1D head-on non-relativistic intercept: burn to delta-v exhaustion, then coast. `target_vel_xc > 0` = receding, `< 0` = head-on. `v_close = v_burnout − v_target`; `v_close ≤ 0` (and not caught during burn) → **no intercept** (`intercepts=False`, a normal result). Returns `{intercepts, intercept_phase ("burn"|"coast"|None), time_to_impact_s, time_to_impact_str, v_burnout_xc, v_close_xc, range_at_burnout_lm, burn_duration_s}`. Validation: `range_lm`/`missile_accel_g`/`missile_delta_v_xc > 0`. **GUI:** green/red verdict label + profile table.
