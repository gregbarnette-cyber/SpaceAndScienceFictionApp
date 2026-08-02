# Science and Science Fiction Feature Documentation

Options 11–16. All features here display data from local CSV files or hardcoded tables. No external API calls. Lowest change frequency of all feature groups.

> **`query.py`:** options 11–13 are also exposed as subcommands — `solar-system` (11), `main-sequence` (12), and `sol-regions` (13) — see `docs/integration.md`. The Honorverse tables (options 14–16) remain GUI/CLI-only.

## Science Features

### Option 11: Solar System Planet/Dwarf Planets/Asteroids — `solar_system_data_tables()`

**Data source: the SQLite tables `planets` / `moons` / `dwarf_planets` / `asteroids`, not the CSVs.**
`core.science.compute_solar_system_tables()` is pure SQL, and it is what the GUI panel,
`query.py solar-system`, `core.viz.prepare_solar_system_orbits` and the Phase Q dossier all read.
The four CSVs are the **seed/import source only** — auto-seeded on first `get_conn()` via
`_STATIC_TABLES` (`core/db.py`), or replaced wholesale by option 55. *(`main.py`'s CLI copy still
reads the CSVs directly; it was never migrated and the CLI menu is deprecated — see the K0-style
note under option 16.)*

- Displays four sequential data tables, each sorted ascending by Semimajor Axis.
- **Solar System Planets Data** — `planets` (8 rows); columns: Planet Name, Mass (J), Diameter (J), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity, Moons. AU values formatted as `{v:g} ({v × 8.3167:.3f} LM)`.
- **Moon Data tables** — `moons` (**43 rows**); grouped by planet in order: Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto; each planet's moons sorted ascending by SemiMajor Axis (km); columns: Satellite Name, Diameter (km), Mass (kg), Perigee (km), Apogee (km), SemiMajor Axis (km), Eccentricity, Period (days), Gravity (m/s^2), Escape Velocity (km/s).
- **Solar System Dwarf Planets Data** — `dwarf_planets` (5 rows); same columns as planets table but header row says "Dwarf Planet Name" and Mass is in Earth masses.
- **Solar System Major Asteroids Data** — `asteroids` (**259 rows**); columns: Asteroid Name, Diameter (KM), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity. Despite the name the table also carries TNOs/centaurs (Sedna, Quaoar, Orcus, Gonggong, Varuna, Ixion, Chaos…) — it is "notable small bodies", not main-belt only. Nine of those TNO rows carry `Diameter = "N/A"` (a literal string, not a blank): no diameter has been published for them, **which is why the table is not size-ranked** — see the curation note below.
  - **The table shows all 259; the Orbital Diagram's "(major)" view plots ~39.** The cap is a *display* concern only, and the combo's **"(all)"** entry plots every one — see `prepare_solar_system_orbits` under the JPL expansion below.

#### JPL expansion (2026-08-02)

The four CSVs were hand-built and incomplete. They were **appended to** (never rewritten — every
pre-existing row is byte-identical) from JPL machine-readable sources:

| table | was | now | source |
|---|---|---|---|
| `moons` | 21 | **43** | JPL SSD [`/sats/elem/`](https://ssd.jpl.nasa.gov/sats/elem/) mean elements + [`/sats/phys_par/`](https://ssd.jpl.nasa.gov/sats/phys_par/) GM/radius |
| `asteroids` | 22 | **259** | SBDB Query API, `diameter >= 100 km` (250) + 9 named spacecraft targets |
| `planets` / `dwarf_planets` | 8 / 5 | unchanged | JPL adds nothing — see below |

**Completeness rule: a body is only added if every column can be filled.** For a moon that means JPL
must publish **both** GM and mean radius, from which mass (`GM/G`), gravity (`GM/R²`), escape velocity
(`√(2GM/R)`), diameter (`2R`) and perigee/apogee (`a(1∓e)`) are derived. There are **0 blank cells**
across all 43 moons and all 259 asteroids. JPL lists mean elements for 459 satellites, but the other
~413 have no measured physical data and are deliberately **not** emitted as sparse rows.

Three moons are excluded for the same reason and must not be "fixed" by inventing a value:
**Nereid** (GM published as `0.00000`) and **Kerberos** / **Styx** (`<0.0002` / `<0.0003` — upper
limits, not measurements).

**Asteroid curation: keep-all-22 + a 100 km size cutoff, NOT a top-N ranking.** Two rules constrain
any future re-cut:

1. **Never rank the table by diameter.** Nine of the original rows (Sedna, Quaoar, Orcus, Gonggong,
   Ixion, Chaos, 2012 VP113, 2018 VG18, 2018 AG37) have `Diameter = "N/A"` — no published value — so
   a size ranking silently *deletes* them. A pure "top 30 by diameter" drops **15 of the 22**
   originals. Always keep the existing rows and filter only the candidates being added.
2. **Watch the `dwarf_planets` overlap.** A 100 km cutoff pulled **Ceres** into `asteroids` while it
   was already a `dwarf_planets` row, so option 11 listed it twice and the orbital diagram drew its
   orbit twice. Ceres is legitimately both, but the duplicate was an accident; it was removed from
   `asteroidsInfo.csv`. Re-check `set(asteroids) & set(dwarf_planets)` after any re-cut.

**The 259 rows made the Orbital Diagram unreadable and slow — that was fixed in the VIEW, not by
shrinking the data.** `core.viz.prepare_solar_system_orbits` draws one 361-point ellipse per body, so
264 orbits collapsed the 2–3.5 AU main belt into a solid band. It now takes a
`max_asteroids=_SS_DIAGRAM_MAX_ASTEROIDS` (25) kwarg that caps the **`dwarfs_asteroids` plot only**:
it keeps the largest by diameter **plus every asteroid with no published diameter** (rule 1 again —
size-ranking would delete the nine TNOs), always keeps all 5 dwarf planets, and returns
`asteroids_shown`/`asteroids_total` so the caller can label the view. `SolarSystemPanel` appends
`"(34 of 259 asteroids — largest, plus all TNOs)"` to the diagram title. Net: **~39 orbits plotted,
all 259 rows still listed in the table**. `max_asteroids=None` disables the cap; the `planets` and
`moons:<planet>` kinds ignore it entirely. Pinned by `tests/test_viz_phase_o.py`
(`test_dwarfs_asteroids_plot_is_capped_but_the_table_is_not`,
`test_capped_plot_never_drops_a_body_that_has_no_diameter`).

**Nothing the cap hides is unreachable, and the diagrams now zoom.** The Orbital Diagram combo carries
three entries — Planets · Dwarf Planets + Asteroids **(major)** · Dwarf Planets + Asteroids **(all)** —
the last mapping to the `dwarfs_asteroids:all` kind, which plots all 259. And `make_orbits_canvas`
gained **scroll-wheel zoom** the same day (it previously had only the toolbar's rectangle-zoom, which is
far too coarse here): wheel-zoom around the cursor, both axes scaled together to preserve the equal
aspect, with the nav stack seeded so **Home** restores the initial frame. This matters because these
diagrams span ~3 orders of magnitude — Sedna's ~1180 AU apastron sets the frame while the main belt sits
at 2–3.5 AU, so the inner system is a smudge until you magnify it. For a jump that large the toolbar's
rectangle-zoom is still the quicker tool; the wheel is for fine adjustment.

**The Phase Q Sol dossier caps the asteroid table too, for a different reason.** A dossier is a
*rendered document* (markdown / HTML / a static PNG export) — it cannot page or scroll, so every row
lands in the output. The expansion silently took its "Major Asteroids" section from 22 rows to 259
(**269 markdown table rows in the planets section alone**). `core.report._dossier_asteroids` now trims
it to the `_DOSSIER_MAX_ASTEROIDS` (25) largest **plus every no-published-diameter body** — rule 1
again — heads it `Major Asteroids · 34 of 259`, and adds a line saying what was dropped and where the
full list lives. It reuses `core.viz._ss_diameter_km` rather than growing a second `"N/A"` parser
(`core.viz` imports no matplotlib at module level, so that stays a cheap pure-core import). Measured:
269 → 53 table rows. Pinned by `tests/test_report.py::SolAsteroidCap`.

**Bodies are labelled on the plot, not just in the legend.** Each orbit carries a name label pinned to
its topmost point, shown while at most `_ORBIT_LABEL_MAX_IN_VIEW` (40) label anchors are in frame and
hidden above that — the orbital-diagram analogue of the opt-18/19 star charts' 15 ly gate (an absolute
AU threshold cannot work across diagrams spanning four orders of magnitude). In practice: **Planets (8),
Moon Systems (≤16) and Dwarf Planets + Asteroids (major) (39) are all labelled immediately**; the
**(all)** view stays unlabelled until you zoom to roughly 0.5 AU across, since 259 names cannot share a
frame. `_ORBIT_LABEL_MAX_IN_VIEW` in `gui/visualizations/plot_helpers.py` is the dial.

**Nine bodies are in the table by NAME, not by the cutoff — do not drop them in a re-cut.** A size
threshold cannot reach the famous *small* bodies, so **Lutetia** (98 km — it missed the 100 km cutoff
by 2 km), **Mathilde** (52.8), **Ida** (32), **Gaspra** (12.2), **Steins** (5.16), **Ryugu** (0.90),
**Bennu** (0.48), **Apophis** (0.34) and **Itokawa** (0.33) were appended individually (2026-08-02),
taking the table from 250 to **259**. All nine are spacecraft targets or well-known NEOs, all carry
complete SBDB rows, and all nine were already in `_HORIZONS_ID_MAP` — so opts 22/23 could fly to them
while the reference table did not list them. They are **invisible to the "(major)" orbital diagram** by
design (every one ranks out of the top-25 by diameter), and four are NEOs at `a < 1.4 AU`, so they plot
inside Mercury's orbit on the "(all)" view. Re-running the ≥100 km SBDB query alone will **not**
reproduce them.

**Why planets and dwarf planets gained nothing.** JPL's satellite count is *lower* than the CSV's
`Moons` column (72 vs 80 for Jupiter, 66 vs 83 for Saturn) because it only lists moons with
ephemerides — so adopting it would be a regression. For dwarf planets the IAU recognises exactly 5
and all 5 are already present; the usual "candidates" (Sedna, Quaoar, Gonggong, Orcus…) are already
rows in the **asteroid** table. Critically, **SBDB publishes no diameter or GM for the TNO dwarfs**
(Pluto, Eris, Haumea, Makemake — only Ceres has both; verified against `sbdb.api` and
`astroquery.jplsbdb`), so those CSV diameters are hand-curated literature values that JPL cannot
replace. Do not "refresh" them from JPL — the data is not there.

**Two transcription errors corrected in the original rows** (the only non-additive change): the
Moon's `Period (days)` `37.322 → 27.322` (the sidereal month; a digit transposition), and **Ariel**'s
`Diameter`/`Mean Radius` `2324`/`1162.2 → 1157.8`/`578.9` (both were exactly doubled — its mass,
gravity and escape velocity were already correct, and neighbouring Umbriel was unaffected).
Eccentricities that differ from JPL were **left alone deliberately**: the `/sats/elem/` page rounds
`e` to 3 decimals, so the CSV values (`0.0041` vs `0.004`) are the more precise ones.

> **Syncing another machine:** `data/space_app.db` is **gitignored**, so pulling the repo brings the
> CSVs but *not* the rebuilt tables — and `_auto_seed` only fires on an **empty** table, so an
> existing DB will not pick the new rows up on its own. Run **option 55 / Utilities → Import Solar
> System Data** after pulling; `import_solar_system_csvs` does `DELETE` + bulk `INSERT` for all four
> tables in one transaction.
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
- **Class-grouped ring tabs (2026-07-31).** Two additional Show-Diagrams tabs sit **before** the bar chart — **"Class Rings"** (default) and **"Class Sectors"** — both `core.viz.prepare_hyper_limit_rings` → `make_hyper_ring_canvas`, drawing the limits as dotted rings around a central star on a √AU scale (the Ice-Line / System-Regions idiom) grouped into O·B·A·F·G·K·M·Red Giant. Each carries a row of **eight per-class checkboxes** plus **Select All / Clear All**; unchecking a class rescales the dial to what is left, and clearing every class shows a "No spectral classes selected." card. **The 44-bar chart is retained unchanged** — it still answers "what is the exact limit for K3" better than any ring.
  - **Why grouping was needed:** 40 of the 44 limits (F0–M9) lie between **1.11 and 3.18 AU** — at a typical canvas size full circles for all of them land under 2 px apart. *Ghost* mode de-emphasises the subtypes (faint hairlines) and labels only each class's hottest/coolest; *Sector* mode separates the classes **by angle instead of radius** (one wedge each, arcs at true radius), which is the only view where all 44 are simultaneously visible, individually labelled and hoverable.
  - **"Red Giant" stays grey.** It is not a spectral class, so `sp_color` returns the unknown `#AAAAAA` and that is kept deliberately — see `docs/gui-architecture.md` (`prepare_hyper_limit_rings`).
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
