# Integration Tool Documentation — `query.py`

`query.py` is a thin JSON dispatcher at the repo root. It allows the `scifiWorldBuilding-Claude` repo (the current consumer — it sits alongside this checkout under `.../Claude/` and calls in through its `bin/sfq` wrapper; formerly the `ScienceFictionResearch-Claude` repo) and any other caller to invoke `core/` functions via a Bash command and receive structured JSON on stdout without needing a copy of the core code.

## Invocation

```bash
# Using the repo's venv directly (preferred from external repos):
# NOTE: the base folder is named "claude" on some machines and "Claude" on others.
# Linux paths are case-sensitive, so try both casings if one fails:
/home/greg/claude/SpaceAndScienceFictionApp/venv/bin/python \
  /home/greg/claude/SpaceAndScienceFictionApp/query.py \
  <subcommand> [arguments]
# or, if that path does not exist:
/home/greg/Claude/SpaceAndScienceFictionApp/venv/bin/python \
  /home/greg/Claude/SpaceAndScienceFictionApp/query.py \
  <subcommand> [arguments]

# From within this repo:
python query.py <subcommand> [arguments]
```

## Output and exit codes

- Always writes JSON to **stdout** — result dict (or list for `habitable-zone`) on success, `{"error": "..."}` on failure.
- Exits **0** on success, **1** on error.
- Output is pretty-printed: `json.dumps(result, indent=2, default=str)`. `default=str` ensures numpy/astropy masked values from archive queries are serialized as strings rather than crashing.
- astroquery warnings (e.g. `NoResultsWarning`) go to **stderr** and do not affect stdout JSON.

## Quick reference

Every success result is a JSON **dict** unless noted. Every failure is `{"error": "<message>"}` with exit code 1. Always check for an `"error"` key before reading other fields.

| Subcommand | Required args | Network | Output top-level keys (success) |
|---|---|---|---|
| `simbad-lookup` | `--star` | SIMBAD | `main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, designations, desig_str, gcns` (`gcns` optional — Phase M5, `null` when absent) |
| `star-regions` | `--star` | SIMBAD + Hypatia | region values (see below) + `simbad` + `hypatia` |
| `star-regions-manual` | `--vmag --bc --teff --parallax` [`--sunlight-intensity --bond-albedo`] | none | flat dict of region values (`hzil, hzol, snowLine, stellarMass, distAU, …`) + echoed inputs |
| `distance` | `--star1 --star2` | SIMBAD† | `star1_info, star2_info, distance_ly, distance_au` |
| `stars-within-sol` | `--ly` | none (local DB) | `limit_ly, count, stars[]` |
| `stars-within-star` | `--star --ly` | SIMBAD | `center, center_x/y/z, limit_ly, count, stars[]` |
| `travel-time` | `--star1 --star2` + (`--ly-hr` \| `--times-c`) | SIMBAD† | `origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str` |
| `habitable-zone` | `--teff --luminosity` | none | **list** of 6 zone dicts (not a dict) |
| `exoplanets` | `--star` | SIMBAD + archives | `simbad, planets[], hwo, exocat` |
| `planetary-systems` | `--star` | SIMBAD + archive | `simbad, planets[]` |
| `hwo-exep` | `--star` | SIMBAD + archive | `simbad, hwo[]` |
| `mission-exocat` | `--star` | SIMBAD (then local DB) | `simbad, exocat` |
| `hwc` | `--star` | SIMBAD (then local DB) | `simbad, star_row, planet_rows[]` |
| `hypatia-data` | `--star` | SIMBAD + Hypatia | `star_name, properties, abundances[]` |
| `gcns-within-sol` | `--ly` | none (local DB) | `limit_ly, count, snapshot_date, gcns_version, stars[]` |
| `gcns-source` | `--id` | none (local DB) | `snapshot_date, gcns_version, star` |
| `gcns-system` | `--id` | none (local DB) | `snapshot_date, gcns_version, query_source_id, system` |
| `gcns-distance` | (`--star1`\|`--id1`) (`--star2`\|`--id2`) | SIMBAD‡ (local DB) | `star1_info, star2_info, distance_ly, distance_au, snapshot_date, gcns_version` |
| `gcns-travel-time` | (`--star1`\|`--id1`) (`--star2`\|`--id2`) + (`--ly-hr`\|`--times-c`) | SIMBAD‡ (local DB) | `origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str, snapshot_date, gcns_version` |
| `gcns-stars-within-star` | (`--star`\|`--id`) `--ly` | SIMBAD‡ (local DB) | `center, center_x/y/z, limit_ly, count, snapshot_date, gcns_version, stars[]` |
| `roche-limit` | `--primary-mass-earth --satellite-density` [`--primary-radius-earth`] | none | `rigid_km, rigid_au, fluid_km, fluid_au, primary_density_gcc, …` |
| `tidal-locking` | `--primary-mass-earth --satellite-mass-earth --sma-km --rotation-hours` [`--rigidity-pa --tidal-q`] | none | `lock_time_years, lock_time_gyr, satellite_radius_km, …` |
| `hill-sphere` | `--star-mass-solar --planet-mass-earth --sma-au` [`--eccentricity`] | none | `hill_radius_km, hill_radius_au, stable_orbit_limit_km/au, …` |
| `binary-stability` | `--mass1-solar --mass2-solar --binary-sma-au --test-sma-au` [`--eccentricity`] | none | `mass_ratio, stype_critical_sma_au, ptype_critical_sma_au, orbit_type, is_stable, …` |
| `atmosphere-retention` | `--planet-mass-earth --planet-radius-earth --temperature-k` | none | `v_escape_kms, gases[]` |
| `solvent-zone` | `--luminosity` + (`--solvent NAME` \| `--t-low --t-high`) [`--albedo`] | none | `solvent, name, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm, citation, t_ref_k` |
| `ice-lines` | `--luminosity` [`--albedo`] | none | `luminosity_solar, albedo, t_ref_k, lines[]` |
| `dossier` | `--star` [`--fmt markdown\|html\|json` `--sections …`] | SIMBAD + NASA + Hypatia (none for `Sol`/`Sun`) | `star, fmt, sections, warnings, notes` + `document` (md/html) \| `data` (json) |
| `generate-system` | `--seed` [`--anchor-star` `--spectral-class` `--planets` `--require-habitable` `--constraint…` `--companion` `--nbody`] | none (synthetic) · SIMBAD + NASA + HWC (with `--anchor-star`) | `seed, mode, anchor_star, star, planets[], warnings, notes` — plus `feasible, constraints[]` with `--constraint` |
| `habitable-zone-sma` | `--teff --luminosity --sma` | none | `zones[], planet_seff, verdict` |
| `star-luminosity` | `--radius --teff` | none | `radius, temp, luminosity` |
| `stellar-evolution` | `--mass-solar` [`--current-age-gyr`] | none | `stages[], total_gyr, ms_end_gyr, current_stage, low_mass, high_mass` |
| `brachistochrone-au` | `--accel-g --au` | none | `accel_g, distance_au, distance_lm, profiles[]` |
| `brachistochrone-lm` | `--accel-g --lm` | none | `accel_g, distance_au, distance_lm, profiles[]` |
| `distance-at-acceleration` | `--accel-g --hours` | none | `accel_g, hours, travel_time_str, profiles[]` |
| `ly-hr-to-times-c` | `--ly-hr` | none | `ly_hr, times_c` |
| `times-c-to-ly-hr` | `--times-c` | none | `times_c, ly_hr` |
| `distance-traveled-ly-hr` | `--ly-hr --hours` | none | `ly_hr, hours, distance_ly` |
| `distance-traveled-times-c` | `--times-c --hours` | none | `times_c, ly_hr, hours, distance_ly` |
| `travel-time-ly-hr` | `--distance-ly --ly-hr` | none | `distance_ly, ly_hr, times_c, total_hours, travel_time_str` |
| `travel-time-times-c` | `--distance-ly --times-c` | none | `distance_ly, times_c, ly_hr, total_hours, travel_time_str` |
| `travel-time-solar` | `--origin --destination --accel-g` [`--v-cap-pct --date`] | **JPL Horizons (live)** | `origin, destination, accel_g, distance_au, distance_lm, v_cap_pct, departure_date, profiles[], …` |
| `optimal-tour` | `--stars N [N …]` (`--ly-hr` \| `--times-c`) [`--closed`] | SIMBAD† (names) | `legs[], total_ly, total_time, naive_total_ly, optimized_total_ly, saved_ly, saved_pct, closed, stars[]` |
| `jump-route` | `--origin --destination --max-jump` [`--optimize distance\|jumps`] | SIMBAD† (names) | `origin_info, dest_info, reachable, jumps, total_ly, direct_ly, route[], stars[]` |
| `jump-network` | `--start --max-jump` [`--max-jumps`] | SIMBAD† (names) | `start_name, max_tier, reachable_count, total_in_pool, unreachable_count, tiers[], stars[]` |
| `multi-stop` | `--stars N [N …]` (`--ly-hr` \| `--times-c`) | SIMBAD† (names) | `legs[], total_ly, total_hours, total_time, stars[]` |
| `nearest-neighbor` | `--start --hops --max-ly` | SIMBAD† (names) | `chain[], stars[], total_ly, stopped_early, start_name` |
| `farthest-first` | `--start --stops` [`--max-reach`] | SIMBAD† (names) | `chain[], tree_edges[], stars[], widest_ly, stopped_early, start_name` |
| `trade-route` | `--stars N [N …]` | SIMBAD† (names) | `nodes[], edges[], total_ly, stars[]` |
| `search-star-systems` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `search-hwc` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `search-exoplanets` | _(all optional filters)_ | **NASA TAP (live)** | `count, capped, cap, stars[]` |
| `search-hypatia` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `compare-stars` | `--stars N [N …]` (2–4) | SIMBAD + NASA + Hypatia | `stars[]` (per-star error isolation) |
| `main-sequence` | _(none)_ | none (local DB) | **list** of 24 spectral-class rows |
| `solar-system` | _(none)_ | none (local DB) | `planets[], moons[], dwarf_planets[], asteroids[]` |
| `sol-regions` | _(none)_ | none | flat dict of Sol region values (`hzil, hzol, snowLine, …`) |
| `orbit-distance` | `--sma --ecc` | none | `sma, ecc, periastron, apastron, ecc_au` |
| `moon-orbital-distance` | `--planet-mass-earth` [`--day-hours`] | none | `planet_mass_earth, day_hours, orbital_distance_km` |
| `gravity-acceleration` | `--rpm --radius-m` | none | `rpm, radius_m, accel_ms2` |
| `gravity-distance` | `--rpm --accel-ms2` | none | `rpm, accel_ms2, radius_m` |
| `gravity-rpm` | `--accel-ms2 --radius-m` | none | `accel_ms2, radius_m, rpm` |
| `travel-time-custom-thrust` | `--origin --destination --accel-g --burn-value` [`--burn-unit --v-cap-pct --date`] | **JPL Horizons (live)** | `origin, destination, distance_au, …, travel_time_str, …` |

† `distance` and `travel-time` skip the SIMBAD call for an endpoint named `"Sol"`/`"Sun"` (treated as the origin at 0,0,0). The seven Route Planning subcommands (`optimal-tour`, `jump-route`, `jump-network`, `multi-stop`, `nearest-neighbor`, `farthest-first`, `trade-route`) likewise resolve each star **DB-first** (`star_systems.star_name`, offline) then **SIMBAD** for names not in the table; `"Sol"`/`"Sun"` → the origin with no lookup. They read the local `star_systems` table for intermediate/candidate stars (run option 50 to populate it).
‡ The `gcns-*` calculators use SIMBAD **only** for `--star` endpoints (to resolve a name to a Gaia id); `--id` endpoints are fully offline. There is **no** `"Sol"`/`"Sun"` special case — Sol is not a GCNS row, so a Sol endpoint returns an error (use `gcns-within-sol` for Sol-centered census queries).

Shared shapes:
- The `simbad` sub-dict embedded in `star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, and `hwc` has the **same shape as `simbad-lookup`'s output** (top-level keys above).
- `planets[]`, `hwo[]`, `exocat`, `star_row`, `planet_rows[]` are dicts/lists of **raw archive or CSV column fields** — for the exact column names see `docs/star-databases.md` (NASA pscomppars, HWO ExEP `di_stars_exep`, Mission Exocat CSV, HWC CSV).

## Subcommands

### Star data

#### `simbad-lookup`
SIMBAD star lookup — returns full star info and all known designations.
```bash
query.py simbad-lookup --star "Tau Ceti"
```
Core function: `databases.compute_simbad_lookup(star)`
Output: `{main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, desig_str, designations, gcns}`. `designations` is a dict keyed by catalog (`MAIN_ID, NAME, GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS`); a catalog with no id is `null`. Numeric fields may be `null`.
- **Gaia id**: the `"Gaia EDR3"` key holds the Gaia source id as SIMBAD now formats it — `"Gaia DR3 <id>"` (SIMBAD renamed EDR3→DR3 in its id output; the source_ids are identical). To get the bare numeric id, strip the `"Gaia DR3 "` / `"Gaia EDR3 "` prefix. This is the same id used as `--id` for `gcns-source`.
- **`gcns`** (Phase M5): an **optional top-level GCNS cross-reference** — the matching `gcns_stars` row (same shape as `gcns-source`'s `star`: Bayesian `dist_pc` + `dist_lo_pc`/`dist_hi_pc`, `distance_method`, Gaia G/BP/RP, `astrom_reliable_prob`, `wd_prob`, `system_id`/`n_components`, …), giving a Bayesian distance **with 16th/84th-percentile uncertainty** beside the naive `1/ϖ` `ly`/`parsecs`. The key is **always present** but is `null` when the star has no Gaia id, is not in GCNS, or the `gcns_stars` table is empty/missing — **non-fatal and silent** (a single indexed local-DB read; no extra network). Built inside `compute_simbad_lookup`, so every `simbad`-embedding subcommand below carries it too.

#### `star-regions`
Star system regions: HZ boundaries, snow line, stellar mass/luminosity/radius, alternate biochemistry zones, plus Hypatia Catalog stellar properties and elemental abundances.
Uses hardcoded `sunlight_intensity=1.0`, `bond_albedo=0.3`.
```bash
query.py star-regions --star "61 Cygni A"
```
Core functions: `databases.compute_simbad_lookup` → `regions.compute_star_system_regions_from_simbad` + `databases.compute_hypatia_data`

Output: a flat dict of computed region values — stellar (`stellarMass, stellarRadius, bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, …`), distance (`parsecs, lightYears, distAU, distKM`), Earth-equivalent orbit (`planetaryYear, planetaryTemperature{,C,F}, sizeOfSun`), and zone boundaries in AU (`hzil, hzol, snowLine, lh2Line, sysol, sysilGrav, sysilSunlight`, plus the alternate-biochemistry pairs `ffInner/ffOuter, fsInner/fsOuter, prwInner/prwOuter, praInner/praOuter, pmInner/pmOuter, phInner/phOuter`) — plus `spectral_type`, `bc_key`, and the embedded `simbad` dict.
The result dict also includes a top-level `"hypatia"` key: `{"star_name", "properties", "abundances"}` on success, or `{"error": str}` if the Hypatia API call fails. The regions result is always returned even when Hypatia fails.

#### `star-regions-manual`
The **manual-input** variant of `star-regions` (the opt-10 calculation): no SIMBAD, no Hypatia — you supply the six raw inputs directly. Returns the same flat region-values dict as `star-regions`/`sol-regions`, **without** the `spectral_type`/`bc_key`/`simbad`/`hypatia` extras (those come only from the SIMBAD path).
```bash
query.py star-regions-manual --vmag 5.5 --bc -0.1 --teff 5500 --parallax 100
query.py star-regions-manual --vmag 5.5 --bc -0.1 --teff 5500 --parallax 100 --sunlight-intensity 1.0 --bond-albedo 0.9
```
Core function: `regions.compute_star_system_regions(vmag, boloLum, temp, plx, sunlight_intensity=1.0, bond_albedo=0.3)`. `--bc` maps to the function's `boloLum` (bolometric correction); `--sunlight-intensity` / `--bond-albedo` default to `1.0` / `0.3`. **No network.** Output: the echoed inputs (`vmag, boloLum, temp, plx, sunlight_intensity, bond_albedo`) plus every computed region value — stellar (`stellarMass, stellarRadius, bcLuminosity, luminosityFromMass, calculatedLuminosity, …`), distance (`parsecs, lightYears, trigParallax`), Earth-equivalent orbit (`distAU, distKM, planetaryYear, planetaryTemperature{,C,F}, sizeOfSun`), and the zone boundaries (`sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol` + the alternate-biochemistry pairs `ffInner/ffOuter, …, phInner/phOuter`).
> **Validation:** this wraps a **non-self-validating** legacy function (like the Phase-N pure-compute wrappers). Out-of-range numerics surface as a **raw-exception** `{"error": str(e)}` (exit 1) — e.g. `--parallax 0` → `"division by zero"`, a negative parallax → `"math domain error"` — **not** a curated message; argparse rejects missing/non-numeric args (exit 2). Key on `"error"` + exit code, not the message text.

### Distance and proximity

#### `distance`
3D Euclidean distance in light years between two stars. Use `"Sol"` or `"Sun"` for the solar system origin.
```bash
query.py distance --star1 "Sol" --star2 "GJ 876"
```
Core function: `calculators.compute_distance_between_stars(star1, star2)`
Output: `{star1_info, star2_info, distance_ly, distance_au}`. Each `*_info` is `{name, ra_deg, dec_deg, ly, desig_str, ra_hms, dec_dms}`. `distance_au` is `null` unless the two stars are < 0.5 ly apart.

#### `stars-within-sol`
All stars in the `star_systems` DB table within N light years of Sol. No network call.
```bash
query.py stars-within-sol --ly 15
```
Core function: `calculators.compute_stars_within_distance_of_sol(ly)`
Output: `{limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Light Years", app_magnitude, parsecs, x, y, z}` (x/y/z are heliocentric light-year coords, may be `null`; `app_magnitude` = Johnson V, `parsecs` = stored distance — both may be `null`). Sorted ascending by Light Years. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)*

#### `stars-within-star`
All stars in the `star_systems` DB table within N light years of a named star. Queries SIMBAD for the center star.
```bash
query.py stars-within-star --star "Epsilon Eridani" --ly 5
```
Core function: `calculators.compute_stars_within_distance_of_star(star, ly)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Distance", app_magnitude, parsecs, x, y, z}` (`Distance` in ly from the center star; `app_magnitude` = Johnson V, `parsecs` = `1000/parallax` — both may be `null`). Sorted ascending by Distance. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)*

### Travel time

#### `travel-time`
FTL travel time between two stars. Supply exactly one of `--ly-hr` or `--times-c`.
```bash
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --times-c 100
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --ly-hr 0.01
```
Core function: `calculators.compute_travel_time_between_stars(star1, star2, ly_hr=..., times_c=...)`
Output: `{origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str}`. `*_info` shape matches `distance` above; `travel_time_str` is a human-readable breakdown (e.g. `"5 Months, 24 Days, 11 Hours"`).

### Habitable zone

#### `habitable-zone`
Kopparapu et al. HZ boundaries for all six zones from stellar parameters. Returns a **list** (not a dict) — one entry per zone.
```bash
query.py habitable-zone --teff 4900 --luminosity 0.15
```
Core function: `equations.compute_habitable_zone(teff, luminosity)`
Output: a **list** of 6 dicts, each `{zone_name, key, au, lm, seff}` (`key` ∈ `rv, rg5, rg, rg01, mg, em`; `au`/`lm` are the boundary distance). On bad input still returns `{"error": str}` (a dict, not a list) — check the type/error key.

### Worldbuilding calculators (Phase H — no network)

Five pure-math calculators (`core/equations.py`); see `docs/equations.md` for full formulas, the two formula corrections, and the model-limitation notes. Standard contract: malformed/missing args → argparse **exit 2** (stderr); out-of-range values (≤ 0 where positive required, `e ∉ [0,1)`) → `{"error": str}` on stdout, **exit 1**; success → the core function's dict, **exit 0**.

#### `roche-limit`
Rigid-body and fluid Roche limits for a satellite orbiting a primary.
```bash
query.py roche-limit --primary-mass-earth 1.0 --satellite-density 3.34
query.py roche-limit --primary-mass-earth 317.8 --satellite-density 0.5 --primary-radius-earth 11.2
```
Core function: `equations.compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None)`. `--primary-radius-earth` is optional (estimated from mass via `R ∝ M^0.55` if omitted). Output: `{primary_mass_earth, primary_radius_km, primary_density_gcc, satellite_density_gcc, rigid_km, rigid_au, fluid_km, fluid_au}`.

#### `tidal-locking`
Tidal-locking timescale of a satellite (MacDonald 1964 model; order-of-magnitude).
```bash
query.py tidal-locking --primary-mass-earth 1.0 --satellite-mass-earth 0.0123 --sma-km 384400 --rotation-hours 24
```
Core function: `equations.compute_tidal_locking_time(primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa=3e10, tidal_q=100)`. `--rigidity-pa` / `--tidal-q` default to `3e10` / `100`. Output: `{…inputs…, satellite_radius_km, lock_time_years, lock_time_gyr}`.

#### `hill-sphere`
Hill sphere (gravitational sphere of influence) of a planet; stable satellite orbits within ~0.5 × Hill radius.
```bash
query.py hill-sphere --star-mass-solar 1.0 --planet-mass-earth 1.0 --sma-au 1.0
```
Core function: `equations.compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0)`. `--eccentricity` defaults to 0. Output: `{…inputs…, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au}`.

#### `binary-stability`
Planet orbit stability in a binary (Holman & Wiegert 1999). S-type = orbits one star; P-type = circumbinary.
```bash
query.py binary-stability --mass1-solar 1.0 --mass2-solar 0.5 --binary-sma-au 20 --test-sma-au 5
```
Core function: `equations.compute_binary_orbit_stability(mass1_solar, mass2_solar, binary_sma_au, test_sma_au, eccentricity=0)`. Masses are reordered internally so `M1 ≥ M2`. Output: `{mass1_solar, mass2_solar, mass_ratio, binary_sma_au, eccentricity, stype_critical_sma_au, ptype_critical_sma_au, test_sma_au, orbit_type, is_stable, stable_region_description}`.

#### `atmosphere-retention`
Which atmospheric gases a planet retains against Jeans escape (optimistic — uses equilibrium temperature).
```bash
query.py atmosphere-retention --planet-mass-earth 1.0 --planet-radius-earth 1.0 --temperature-k 255
```
Core function: `equations.compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k)`. Output: `{planet_mass_earth, planet_radius_earth, temperature_k, v_escape_kms, gases[]}` where each gas is `{gas, mol_mass_amu, lambda, v_thermal_kms, status}` (status ∈ Retained / Escaping slowly / Lost rapidly) for H₂, He, CH₄, H₂O, N₂, O₂, CO₂.

### Solvent zones (Phase P — no network)

Two pure-math calculators backing the Worldbuilding "Solvent Habitable Zone" and
"Ice Line Calculator" panels. Both wrap **self-validating** core functions, so they
follow the **Phase H** contract (curated `{"error"}` exit 1, **not** the Phase N
raw-exception path): malformed/missing/non-numeric args → argparse **exit 2** (stderr);
out-of-range (luminosity ≤ 0, albedo ∉ [0, 1), `t_low ≥ t_high`, unknown solvent) →
`{"error": str}` **exit 1**; success → dict **exit 0**. Phase P uses **two temperature
models**: **M1 surface** `T_ref = 314.9 × (1−A)^0.25` (= 288 K at A=0.3, the alt-HZ
convention; solvent liquid bands) and **M2 equilibrium** `T_ref = 278.5 × (1−A)^0.25`
(no greenhouse; snow/ice condensation). See `docs/equations.md` / `docs/star-system-regions.md`.

#### `solvent-zone`
The AU band where a solvent is liquid on a planet surface (M1 surface model). Pick a
**named** `--solvent` from the built-in table (water, ammonia, methane, ethane,
water_ammonia, so2, co2, sulfuric_acid, sulfur, hydrogen, nitrogen, hf, formamide) **or**
supply a custom `--t-low`/`--t-high` liquid range (mutually exclusive; supplying both or
neither → exit 2). `--albedo` defaults to **0.3**.
```bash
query.py solvent-zone --luminosity 1.0 --solvent water
query.py solvent-zone --luminosity 1.0 --t-low 273.15 --t-high 373.15 --albedo 0.0
```
Core function: `equations.compute_solvent_zone(luminosity_solar, solvent=None, t_low_k=None, t_high_k=None, albedo=0.3)`. The band's inner edge = the solvent's boiling point (closer in), outer edge = its freezing point. Output: `{solvent, name, t_low_k, t_high_k, albedo, t_ref_k, luminosity_solar, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm, citation}` (`t_eq_*` round-trip the edge temps; `co2` is `pressure_conditional` with `assumed_pressure_atm = 5.2`).

#### `ice-lines`
The single canonical water snow line (170 K) plus the CO₂/NH₃/N₂/CO condensation fronts (M2 equilibrium model). `--albedo` defaults to **0.0** (bare ice grains).
```bash
query.py ice-lines --luminosity 1.0
query.py ice-lines --luminosity 0.5 --albedo 0.1
```
Core function: `equations.compute_ice_lines(luminosity_solar, albedo=0.0)`. Output: `{luminosity_solar, albedo, t_ref_k, lines}` where each line is `{species, t_cond_k, au, lm, kind ("snow_line"|"front"), disk_line, note}`. `AU = sqrt(L) × (T_ref / T_cond)²`; the water snow line lands at ~2.68 AU at L=1. The deep-cold N₂/CO fronts carry `disk_line=true` (disk-midplane-set; their ~160–194 AU placement is illustrative).

> **Region-output change (Phase P, consumer-facing).** The existing `star-regions` /
> `sol-regions` / `star-regions-manual` subcommands serialize the whole regions dict
> verbatim, so the Phase P **P1 value corrections** and **P2/P3 additive keys** now flow
> through their JSON automatically (no dispatcher change):
> - **Changed values:** `snowLine` (5.0 → **2.68 AU** at L=1, divisor 0.04 → 0.139),
>   `phInner`/`phOuter` (the hydrogen band → **~200–440 AU**, divisors 0.0000247 / 0.0000053),
>   and `planetaryTemperature`/`C`/`F` — the last only at **non-0.3** albedo (the
>   `(1−A)^0.25` fix; A=0.3 output is unchanged). `lh2Line` value is unchanged (relabel-only).
> - **New keys:** the P2 solvent bands `co2Inner`/`co2Outer`, `sInner`/`sOuter`,
>   `waInner`/`waOuter`, `saInner`/`saOuter` (M1) and the P3 ice fronts `iceLineNH3`,
>   `iceLineCO2`, `iceLineN2`, `iceLineCO` (M2).

### System dossier (Phase Q — no network for Sol)

#### `dossier`
Render a complete, self-contained **system dossier** by composing the existing readers
(`simbad-lookup` → regions + Kopparapu HZ + the NASA/HWC planet catalogs + Hypatia
abundances + the M5 GCNS cross-reference) into one document. This is the one call that
returns a whole system writeup instead of stitching 5+ subcommand outputs together. Pure
composition — **no new astronomy**.
```bash
query.py dossier --star "Tau Ceti"
query.py dossier --star "Tau Ceti" --fmt json
query.py dossier --star "Tau Ceti" --fmt html --sections identity regions planets
query.py dossier --star Sol                       # fully offline (Solar System)
query.py dossier --star Sol --sections planets moons
```
Core function: `report.build_system_dossier(star, sections=None, fmt="markdown")`.

- **`--fmt`** (default `markdown`): `markdown` / `html` emit a rendered **`document`** string
  (HTML is self-contained — inline `<style>`, no external assets, **text + tables only**: the
  HZ-ring / abundance figures are a GUI-only enrichment, never in the `query.py` output).
  `json` emits a structured **`data`** dict (the per-section data dicts) and **no** `document`.
- **`--sections`** (default: all available): any subset of `identity regions habitable_zone
  planets hypatia gcns moons`. `moons` is a **Sol-only opt-in** (large; never in the default
  set).
- **Sections.** `identity`, `regions` (stellar properties + system regions + the full Phase P
  alternate-solvent bands & ice/condensation lines), `habitable_zone` (Kopparapu, 3 luminosity
  columns), `planets` (**both** NASA pscomppars [priority 1] and HWC [priority 2] sub-tables
  when both resolve), `hypatia` (all measured species, grouped by nucleosynthetic family), and
  `gcns` (Bayesian distance + σ).
- **`Sol`/`Sun`** is the **offline reference-origin path**: identity from solar constants,
  regions/HZ from `compute_sol_regions`, `planets` from the real Solar System tables (Planets /
  Dwarf Planets / Major Asteroids; `moons` opt-in), Hypatia from the solar [X/H]≡0 zero-point,
  and **GCNS is not applicable** (a `notes[]` entry, not a warning). No SIMBAD/network call.
- **Output envelope:** `{star, fmt, sections, warnings, notes}` plus `document` (md/html) or
  `data` (json). `sections` lists the sections actually rendered.

> **Validation (self-validating — Phase H contract):** a **SIMBAD-lookup failure** for a real
> star, an unknown `--sections` value, or (via the core) a bad call → `{"error": str}` on
> stdout, **exit 1**. A bad `--fmt` (not markdown/html/json) is rejected by argparse → **exit
> 2** (stderr). A real star that is simply **missing a source** (no planets / no Hypatia / a
> white-dwarf regions failure) is **not** an error: that section is dropped to a **`warnings[]`**
> entry and the dossier still renders the rest (exit 0). Intentional omissions (GCNS-N/A on
> Sol) are **`notes[]`**, separate from warnings.

### Procedural system generation (Phase R1 + R2 — no network for synthetic mode)

#### `generate-system`
Deterministically generate a plausible planetary system — the inverse of the analysis
tools. Two modes: **synthetic-from-seed** (offline) and **real-anchor** (extends a real
star/system, networked). With one or more **`--constraint`** flags it becomes a
**constraint/feasibility analyzer** (Phase R2) — see "Feasibility mode" below. **Headline
contract: same `--seed` (+ same `--anchor-star` + same constraints) → byte-identical
output.** Pure composition over verified `core/` functions — the only new astronomy is a
planet classifier + a Phase-P equilibrium-temperature wrapper (R1) plus packing / resonance
/ co-orbital diagnostics + an opt-in pure-numpy N-body screen (R2).
```bash
query.py generate-system --seed 88 --spectral-class K2V --planets 5 --require-habitable   # synthetic, offline
query.py generate-system --seed 4173                                                       # synthetic, sampled class/count
query.py generate-system --seed 4173 --anchor-star "Tau Ceti"                              # real-anchor (+ network)
```
Core function: `generate.generate_system(seed, anchor_star=None, spectral_class=None, n_planets=None, require_habitable=False, constraints=None, companion=None, research_policy="permissive", nbody=False)`.

- **`--seed`** (required, int): the RNG seed — the system's identity.
- **`--anchor-star`** (optional): a real star name → **real-anchor mode** (pulls real
  specs via SIMBAD + `compute_star_system_regions_from_simbad`, the real known planets via
  NASA pscomppars / HWC flagged `source:"observed"`, then extends with synthetic infill
  flagged `source:"synthetic"`). Omit → **synthetic mode** (fully offline).
- **`--spectral-class`** (synthetic only): e.g. `K2V`; sampled from `DefaultPriors` weights
  if omitted. Ignored in real-anchor mode (the anchor's real class is used). `O`-class is
  rejected.
- **`--planets`** (optional, 0–15): the synthetic planet count (or the synthetic-infill
  count when anchored); sampled from the planet-count distribution if omitted.
- **`--require-habitable`** (store-true): retry (bounded) until a conservative-HZ rocky
  world is placed, else a curated error.
- **Output:** `{seed, mode ("synthetic"|"real_anchor"), anchor_star, star, planets[],
  warnings[], notes[]}`. `star` carries `name, spectral_class, teff, mass_solar,
  radius_solar, luminosity, hz_inner_au/hz_outer_au` (conservative) + `hz_opt_inner_au/
  hz_opt_outer_au` (optimistic) + `snow_line_au, source, grounding, multiplicity`. Each
  planet carries `name, a_au, mass_earth, radius_earth, ecc, type
  (rocky|super_earth|ice|gas|super_jovian|brown_dwarf), t_eq_k, in_hz, hz_class
  (conservative|optimistic|null), source, atmosphere, moons[]`. Every synthetic field is
  grounded `default-extrapolation` (the `DefaultPriors` provider — research-calibrated
  priors are Phase R3). Multi-star anchors are **detected, warned, and safe-capped** (no
  synthetic body beyond a conservative cap; observed bodies are never capped); a quantitative
  S/P-type verdict needs a `--companion` hint (Phase R2 — below).

> **Validation (self-validating — Phase H contract, *not* the Phase-N raw-exception path):**
> bad input → a curated `{"error": str}` on stdout, **exit 1** — a bad `--spectral-class`, an
> `--planets` outside 0–15, `--require-habitable` exhausted after bounded retries, an
> unresolvable `--anchor-star`, a non-OBAFGKM (e.g. white-dwarf) anchor primary, a **malformed
> `--constraint` / `--companion` DSL**, or an out-of-range `--companion` eccentricity. Argparse
> rejects a missing or non-integer `--seed` / `--planets` → **exit 2** (stderr).

##### Feasibility mode (Phase R2 — `--constraint` / `--companion` / `--nbody`)

Describe the system you *want* as structured constraints and get a **four-layer verdict per
constraint** — stable? · why? · how could it arise? · nearest feasible alternative? — plus
the satisfied system. **Zero `--constraint` flags → the R1 generation path, byte-identical**
(all three flags are additive).
```bash
query.py generate-system --seed 4173 --anchor-star "47 Ursae Majoris" \
  --constraint 'planet_at_location:terrestrial,1.0,between:b:c' \
  --constraint 'trojan:terrestrial,giant_in_hz,L4' --nbody
query.py generate-system --seed 88 --spectral-class K2V --planets 6 \
  --constraint 'resonance:c,d,2:1' --companion '0.5,20,0.1'
```

- **`--constraint`** (repeatable) — a compact DSL `type:field,field[,…]` (comma-separated;
  location / ratio fields may themselves contain `:`). Vocabulary v1:
  - `planet_at_location:<type>,<mass_earth>,<location>` — `<location>` ∈ `in_hz` | `at:AU` |
    `between:A:B` | `interior_to:REF` | `exterior_to:REF` | `in_zone:ZONE` | `in_hz:opt`.
  - `trojan:<companion_type>,<host>,[L4|L5]` · `moon:<host>[,<mass_earth>][,terraformable]` ·
    `resonance:<bodyA>,<bodyB>,<p:q>`.
  - stretch: `habitable_world[:cons|opt[,min_count]]` · `alt_solvent_world:<solvent>[,<mass>]`
    · `architecture:<giant_beyond_snow_line|no_hot_jupiter>`.
  - Refs are a planet letter (`b` = innermost by SMA), an observed planet name, or a symbolic
    anchor (`giant_in_hz`, `super_jovian_in_hz`, `outermost`/`innermost`). An **unresolvable
    ref or an unknown constraint type is *not* an error** — that constraint is
    `verdict:"not_evaluated"` and the rest still evaluate. A **malformed** DSL → curated
    `{"error"}` exit 1.
- **`--companion 'mass_solar,sma_au[,ecc]'`** — a multi-star hint; a placed body must pass the
  Holman & Wiegert S-type (inside the critical SMA) / P-type (circumbinary, outside it) test.
  Binary instability is decisive (overrides a stable packing verdict → infeasible).
- **`--nbody`** (store-true) — run a **bounded, deterministic, pure-numpy** N-body screen on a
  **marginal** packing verdict (the Δ ∈ [2√3, 10) gray band) to resolve it to feasible /
  infeasible. Opt-in; a short-integration screen, **not** a Gyr stability proof.

- **Feasibility output** (only with `--constraint`): the R1 envelope **plus** `feasible`
  (bool — all *evaluated* constraints feasible; marginal/infeasible make it false;
  `not_evaluated` is neutral) and `constraints[]`, one entry per constraint:
  `{id, type, verdict ("feasible"|"marginal"|"infeasible"|"not_evaluated"),
  layer1 {stable, reason, metrics}, layer2 {mechanism, checked, note},
  layer3 {hypotheses:[{pathway, plausibility, grounding}], grounding}, layer4
  {alternatives:[{change, result, spec_patch}]}}`. Layer-3 hypotheses are **always tagged
  `grounding="default-extrapolation"`** (R3 swaps in research-calibrated priors with no engine
  change); each Layer-4 `spec_patch` is the exact spec mutation that flips the constraint.

### Integration expansion (Phase N)

Five subcommands that each wrap an **existing `core/` function verbatim** — no new output shapes; each returns
exactly what its core function returns today, pretty-printed. Four are pure-compute (no network); `travel-time-solar`
is the **only network-bound** entry (live JPL Horizons).

> **⚠️ Validation contract — read this before relying on exit codes.** Unlike the Phase-H worldbuilding calculators
> (which **self-validate** and return a curated `{"error": str}` for out-of-range input), the four pure-compute Phase-N
> subcommands wrap the project's **older, non-self-validating** equation/calculator functions, and Phase N adds **no
> validation** (it is a thin verbatim wrapper). The exit-code behavior is therefore:
>
> - **Malformed / missing / non-numeric arg** → argparse rejection, **exit 2**, message on **stderr** (not JSON) — all five.
> - **Out-of-range numeric** for `habitable-zone-sma`, `brachistochrone-au`, `brachistochrone-lm` → the wrapped function
>   **raises**, and `query.py`'s top-level handler turns it into `{"error": str(e)}` on stdout, **exit 1** — but the
>   message is a **raw Python exception string** (e.g. `"math domain error"` for a negative luminosity/distance,
>   `"float division by zero"` for `--sma 0` or `--accel-g 0`), **not** a curated sentence. Do not pattern-match on the
>   exact text; key on the presence of `"error"` + exit 1.
> - **`star-luminosity` has no out-of-range error path at all**: `L = R²·(T/5778)⁴` returns a finite number for any
>   float (a negative radius yields a positive luminosity because it is squared), so the only non-zero exit it produces
>   is argparse's **exit 2**.
> - **`travel-time-solar`** is the exception: it **does** return curated `{"error": str}` dicts (ambiguous Horizons
>   name — with a disambiguation hint — same-object, and network failures), **exit 1**.
>
> This was a deliberate decision (honor "no `core/` changes"; the raw-exception path is the already-blessed behavior —
> see `tests/test_equations.py::test_bad_input_raises`). Tests: `tests/test_query_phase_n.py` (offline subprocess
> contracts + the mocked `travel-time-solar` wiring; live Horizons round-trip gated on reachability).

#### `habitable-zone-sma`
Kopparapu HZ boundaries **plus** the object's S_eff at its orbit and a plain-language HZ-membership verdict (the opt-40 calculation). Complements `habitable-zone`, which lacks the per-object Seff/verdict.
```bash
query.py habitable-zone-sma --teff 4900 --luminosity 0.15 --sma 0.45
```
Core function: `equations.compute_habitable_zone_sma(teff, luminosity, sma)`. No network. Output: `{zones, planet_seff, verdict}` — `zones` is the same 6-element list as `habitable-zone` (each `{zone_name, key, au, lm, seff}`); `planet_seff = (1/sma)² · luminosity`; `verdict` is a human-readable HZ-membership string.

#### `star-luminosity`
Stellar luminosity from radius and temperature: `L = R² × (T/5778)⁴` (the opt-41 calculation).
```bash
query.py star-luminosity --radius 0.82 --teff 5344
```
Core function: `equations.compute_star_luminosity(radius, temp)`. No network. Arg is `--teff` (consistency with `habitable-zone` / `habitable-zone-sma`), mapped to the function's `temp` parameter. Output: `{radius, temp, luminosity}`.

#### `stellar-evolution`
Evolutionary-stage durations and timeline for a star of a given mass (Phase L3). **Self-validating** (unlike the Phase-N legacy wrappers): a mass outside `0.1–20 M☉` returns a curated `{"error": str}` (exit 1); argparse rejects missing/non-numeric args (exit 2).
```bash
query.py stellar-evolution --mass-solar 1.0
query.py stellar-evolution --mass-solar 1.0 --current-age-gyr 4.6
```
Core function: `equations.compute_stellar_evolution(mass_solar, current_age_gyr=None)`. No network. `--current-age-gyr` is optional (marks the stage containing that age, or `"Beyond AGB"` past all stages). Output: `{mass_solar, stages:[{name, start_gyr, end_gyr, duration_gyr, color}], total_gyr, ms_end_gyr, current_age_gyr, current_stage, low_mass, high_mass}`. `T_ms = 10¹⁰ × (1/M)^2.5 yr`; stage fractions Pre-MS 0.01 · MS 1.0 · Subgiant 0.15 · RGB 0.10 · HB 0.10 · AGB 0.02. Special cases are **values, not errors**: `mass < 0.8` → `low_mass=true`, only Pre-MS + MS stages emitted (post-MS not reachable in a Hubble time); `mass > 8` → `high_mass=true`, the AGB stage becomes `"Supergiant → Supernova"`.

#### `brachistochrone-au` and `brachistochrone-lm`
All three brachistochrone acceleration profiles for a given distance (the opt-29 / opt-30 calculations).
```bash
query.py brachistochrone-au --accel-g 1.0 --au 5.2
query.py brachistochrone-lm --accel-g 0.5 --lm 43.2
```
Core functions: `calculators.compute_travel_time_system_au(accel_g, distance_au)` / `compute_travel_time_system_lm(accel_g, distance_lm)`. No network. Output: `{accel_g, distance_au, distance_lm, profiles}` (`distance_lm` ↔ `distance_au` are inter-derived). `profiles` is a list of 3 dicts, each `{label, hours, travel_time_str, max_vel}` (`max_vel` ∈ `"N/A"`/`"Y"`/`"N"`): ① continuous-to-halfway, ② accel¼/coast½/decel¼, ③ accel-to-3%c/coast/decel.

#### `distance-at-acceleration`
*(Added later to close an exposure gap — not one of the original Phase-N five above, but it shares their non-self-validating contract and sits with its brachistochrone siblings.)* The **inverse** of the brachistochrone subcommands — given an acceleration **and a travel time**, the distance covered by three profiles (the opt-24 calculation).
```bash
query.py distance-at-acceleration --accel-g 1.0 --hours 24
```
Core function: `calculators.compute_distance_at_acceleration(accel_g, hours)`. No network. Output: `{accel_g, hours, travel_time_str, profiles}` — `profiles` is a list of 3 dicts, each `{label, distance_au, distance_lm, max_vel}` (`max_vel` is `"N/A"` for profiles ① continuous-accel-for-the-whole-time and ② accel¼/coast½/decel¼; `"Y"`/`"N"` for profile ③ accel-to-3%c/coast, indicating whether the 3% c cap was reached in the window).
> **Validation:** non-self-validating (like the Phase-N pure-compute wrappers). An out-of-range numeric surfaces as a **raw-exception** `{"error": str(e)}` (exit 1) — e.g. `--accel-g 0` → `"division by zero"`; argparse rejects missing/non-numeric args (exit 2).

#### Velocity & constant-speed travel converters (opts 25–28, 31, 32)
Six thin wrappers over the simple constant-velocity calculators (the CLI menu opts 25–28 / 31 / 32), added to close an exposure gap. No network. **Non-self-validating** (Phase-N contract): the conversion / distance wrappers have **no error path** (any float is finite); the two travel-time wrappers raise `{"error": "float division by zero"}` (exit 1) on a zero velocity. Argparse rejects missing/non-numeric args (exit 2). Velocity ↔ c uses the Julian-year constant `8765.8128` (hours/yr).
```bash
query.py ly-hr-to-times-c --ly-hr 0.01                       # opt 31
query.py times-c-to-ly-hr --times-c 100                      # opt 32
query.py distance-traveled-ly-hr --ly-hr 0.01 --hours 100    # opt 25
query.py distance-traveled-times-c --times-c 100 --hours 50  # opt 26
query.py travel-time-ly-hr --distance-ly 4.37 --ly-hr 0.01   # opt 27
query.py travel-time-times-c --distance-ly 4.37 --times-c 100 # opt 28
```
Core functions: `calculators.compute_ly_hr_to_times_c(ly_hr)` → `{ly_hr, times_c}`; `compute_speed_of_light_to_ly_hr(times_c)` → `{times_c, ly_hr}`; `compute_distance_traveled_ly_hr(ly_hr, hours)` → `{ly_hr, hours, distance_ly}`; `compute_distance_traveled_times_c(times_c, hours)` → `{times_c, ly_hr, hours, distance_ly}`; `compute_travel_time_ly_hr(distance_ly, ly_hr)` → `{distance_ly, ly_hr, times_c, total_hours, travel_time_str}`; `compute_travel_time_times_c(distance_ly, times_c)` → `{distance_ly, times_c, ly_hr, total_hours, travel_time_str}` (`travel_time_str` is a human-readable breakdown, e.g. `"18 Days, 5 Hours"`).

#### `travel-time-solar`
Brachistochrone travel time between two solar-system bodies at a departure epoch (the opt-22 calculation). **Live JPL Horizons network call** — the only network-bound entry in this phase.
```bash
query.py travel-time-solar --origin Earth --destination Mars --accel-g 1.0
query.py travel-time-solar --origin Earth --destination "Jupiter" --accel-g 0.3 --v-cap-pct 5 --date 2027-03-15
```
Core function: `calculators.compute_travel_time_solar_objects(origin, destination, accel_g, v_cap_pct=3.0, departure_date=None)`. `--v-cap-pct` defaults to `3.0`; `--date` is ISO `YYYY-MM-DD`, defaulting to today (mapped to `departure_date`). The GUI-only `progress_callback` is never passed. Output: `{origin, destination, accel_g, distance_au, distance_lm, v_cap_pct, departure_date, profiles, origin_xyz, dest_xyz, planet_positions, origin_id, dest_id}` — `profiles` carries the same `{label, hours, travel_time_str, max_vel}` shape as the brachistochrone subcommands; JSON consumers may ignore `origin_xyz`/`dest_xyz`/`planet_positions`/`origin_id`/`dest_id`. Ambiguous Horizons names return the disambiguation error already produced by the core function.

### Route Planning additions (Phase I-OPTS)

The three Phase I-OPTS subcommands below (`optimal-tour`, `jump-route`, `jump-network`) wrap the **self-validating**
Route Planning functions (so out-of-range numerics return a curated `{"error": str}`, exit 1, unlike the Phase-N legacy
wrappers; argparse rejects missing/malformed args with exit 2 and a stderr message). Each resolves every star
**DB-first** (`star_systems.star_name`) then **SIMBAD** for names not in the table; `"Sol"`/`"Sun"` → the origin with no
lookup. Candidate/intermediate stars come from the local `star_systems` table (run **option 50** to populate it). The
fourth I-OPTS planner, Farthest-First Coverage (`farthest-first`), is documented with the original I1/I2/I3 planners in
the next section.

#### `optimal-tour`
Shortest-total-distance visit order for a set of stars (NN seed + 2-opt; the first star is the fixed start). Supply
exactly one of `--ly-hr` / `--times-c`; `--closed` adds a return-to-start leg.
```bash
query.py optimal-tour --stars Sol "Alpha Centauri" Sirius Procyon --ly-hr 0.01
query.py optimal-tour --stars Sol Sirius Procyon --times-c 100 --closed
```
Core function: `calculators.compute_optimal_tour(star_names, velocity_input, use_times_c, closed=False)`. Output:
`{legs[], total_ly, total_hours, total_time, naive_total_ly, optimized_total_ly, saved_ly, saved_pct, closed, stars[]}` —
each leg is `{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time, cumulative_time}`
(includes the wrap leg when `--closed`). `< 2` distinct stars or a non-positive velocity → `{"error"}` exit 1.

#### `jump-route`
Route origin→destination through intermediate stars, each jump ≤ `--max-jump` ly. `--optimize distance` (default,
Dijkstra) or `jumps` (BFS).
```bash
query.py jump-route --origin Sol --destination Procyon --max-jump 9
query.py jump-route --origin Sol --destination "Epsilon Indi" --max-jump 7 --optimize jumps
```
Core function: `calculators.compute_jump_route(origin, destination, max_jump_ly, optimize="distance")`. Output:
`{origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly, route:[{jump, from, to, jump_ly,
cumulative_ly}], max_jump_ly, stars[]}`. **An unreachable destination is a normal result** (`reachable=false`, empty
`route`, **exit 0**) — not an error. Same origin/destination, `max_jump ≤ 0`, or an unresolvable endpoint → `{"error"}`
exit 1; `--optimize` other than `distance`/`jumps` is an argparse exit 2.

#### `jump-network`
BFS reachability tiers from a start star at jump range `--max-jump`; optional `--max-jumps` cap.
```bash
query.py jump-network --start Sol --max-jump 6
query.py jump-network --start "Alpha Centauri" --max-jump 5 --max-jumps 3
```
Core function: `calculators.compute_jump_network(start, max_jump_ly, max_jumps=None)`. Output: `{start_name,
max_jump_ly, max_jumps, max_tier, reachable_count, total_in_pool, unreachable_count, tiers:[{jumps, stars:[{star_name,
desig, sp_type, dist_from_start_ly, ly_from_sol}]}], stars[]}`. `reachable_count` includes the start; `unreachable_count`
is over the original `star_systems` rows. Each star in `stars[]` carries a per-tier `color` and `tier`. `max_jump ≤ 0`
or `max_jumps < 1` → `{"error"}` exit 1; empty `star_systems` → the opt-50 message, exit 1.

### Route Planning — original four (Phase I planners, now also via `query.py`)

The original Phase I planners (`compute_multi_stop_journey`, `compute_nearest_neighbor_chain`,
`compute_trade_route_mst`) plus the Phase I-OPTS Farthest-First Coverage (`compute_farthest_first_chain`, previously
GUI-only) are exposed here as subcommands — the same self-validating contract (curated `{"error"}` exit 1; argparse
exit 2 for missing/malformed args). Name resolution is DB-first → SIMBAD, as above.

#### `multi-stop`
Cumulative travel time along an **ordered** list of stops (you supply the order). One of `--ly-hr` / `--times-c`.
```bash
query.py multi-stop --stars Sol "Alpha Centauri" Sirius Procyon --times-c 100
```
Core function: `calculators.compute_multi_stop_journey(star_names, velocity_input, use_times_c)`. Output:
`{legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time, cumulative_time}],
total_ly, total_hours, total_time, stars[]}`. `< 2` stops or non-positive velocity → `{"error"}` exit 1; the first
unresolvable stop → `{"error": "Stop N ('name'): …"}`.

#### `nearest-neighbor`
Greedy nearest-unvisited chain from a start star over the `star_systems` pool.
```bash
query.py nearest-neighbor --start Sol --hops 6 --max-ly 6
```
Core function: `calculators.compute_nearest_neighbor_chain(start_star, num_hops, max_ly)`. Output:
`{chain:[{hop, star_name, desig, sp_type, dist_from_prev_ly, cumulative_ly, ly_from_sol}], stars[], total_ly,
stopped_early, start_name}`. No unvisited star within `--max-ly` → `stopped_early=true` (a normal result, **exit 0**).
`hops < 1` or `max_ly ≤ 0` → `{"error"}` exit 1; non-integer `--hops` → argparse exit 2; empty `star_systems` → the
opt-50 message, exit 1.

#### `farthest-first`
De-clustering coverage chain — each step picks the star **farthest** from the visited set (optional `--max-reach`).
```bash
query.py farthest-first --start Sol --stops 5
query.py farthest-first --start Sol --stops 8 --max-reach 13
```
Core function: `calculators.compute_farthest_first_chain(start, num_stops, max_reach_ly=None)`. Output:
`{chain:[{step, star_name, desig, sp_type, sep_to_visited_ly, dist_from_start_ly, ly_from_sol}], tree_edges[], stars[],
widest_ly, stopped_early, start_name}`. Nothing within reach → `stopped_early=true` (exit 0). `stops < 1` or
`max_reach ≤ 0` → `{"error"}` exit 1; empty `star_systems` → the opt-50 message, exit 1.

#### `trade-route`
Minimum spanning tree connecting a set of systems (Kruskal).
```bash
query.py trade-route --stars Sol Sirius Procyon "61 Cygni" "Epsilon Eridani"
```
Core function: `calculators.compute_trade_route_mst(star_names)`. Output: `{nodes:[{name,x,y,z,sp_type,desig}],
edges:[{from,to,distance_ly}] (N−1, ascending), total_ly, stars[]}`. After case-insensitive dedup, `< 2` systems →
`{"error"}` exit 1; the first unresolvable system → `{"error": "'name': …"}`.

### Exoplanet archives (network)

#### `exoplanets`
NASA Exoplanet Archive — all tables (pscomppars + HWO ExEP + Mission Exocat). Live network call.
```bash
query.py exoplanets --star "Epsilon Eridani"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_exoplanet_archive`
Output: `{simbad, planets[], hwo, exocat}`. `planets[]` are pscomppars rows (sorted by `pl_orbsmax`); `hwo` is a list of `di_stars_exep` rows or `null` if no match; `exocat` is a single Mission Exocat row dict or `null`. Field names = raw archive/CSV columns (see `docs/star-databases.md`).

#### `planetary-systems`
NASA Exoplanet Archive — planetary systems composite (pscomppars only). Live network call.
```bash
query.py planetary-systems --star "Epsilon Eridani"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_planetary_systems_composite`
Output: `{simbad, planets[]}` — `planets[]` are pscomppars rows (raw archive columns), sorted by `pl_orbsmax`.

#### `hwo-exep`
HWO ExEP precursor science star list. Live network call.
```bash
query.py hwo-exep --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hwo_exep`
Output: `{simbad, hwo[]}` — `hwo[]` are `di_stars_exep` rows (raw archive columns), sorted by `sy_dist`.

### Local DB archives (no network after first import)

#### `mission-exocat`
NASA Mission Exocat — queries the local `mission_exocat` DB table (2,396 rows). No network call after data is imported.
```bash
query.py mission-exocat --star "Epsilon Indi"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_mission_exocat`
Output: `{simbad, exocat}` — `exocat` is a single Mission Exocat CSV row dict (raw columns).

#### `hwc`
Habitable Worlds Catalog — queries the local `hwc` DB table (5,599 rows). No network call after data is imported.
```bash
query.py hwc --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hwc`
Output: `{simbad, star_row, planet_rows[]}` — `star_row` holds star-level HWC fields; `planet_rows[]` are per-planet rows (raw HWC CSV columns), sorted by `P_SEMI_MAJOR_AXIS`.

### Hypatia Catalog (live network)

#### `hypatia-data`
Hypatia Catalog stellar properties and elemental abundances (Lodders 2009 normalisation). Live network call.
```bash
query.py hypatia-data --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hypatia_data`

Returns `{"star_name", "properties", "abundances"}` on success.
- `properties`: `{teff, logg, spectral_type, vmag, bmag, bv, distance_pc, disk, u_vel, v_vel, w_vel, pm_ra, pm_dec}` (any field may be `null`).
- `abundances`: list of `{element, name, z, category, mean, std, min, max, n}` for the full **104-species** Hypatia set (all elements the API exposes via `GET /element`, including singly-ionized species such as `Ba_II`); only species with a non-null mean are included. `element` preserves the API casing (`Fe`, `Ba_II`); `name` is the full element name (ionized → e.g. `Barium II`); `z` is the atomic number; `category` is the nucleosynthetic-family key (`light`, `cno`, `alpha`, `oddz`, `iron`, `s_light`, `s_heavy`, `ree`, `heavy`). `n` (# catalogs) is derived from the response's `catalogs_linear` length. The species set, names, atomic numbers, and categories are defined in `core/hypatia_elements.py`. Results are ordered by that table's display order (category light→heavy, then atomic number). The 104 species can't be requested in one call (the server caps the GET request line at ~4094 bytes), so `compute_hypatia_data` fetches them in chunks of 30 and concatenates the responses.

### GCNS — Gaia Catalogue of Nearby Stars (local DB, no network)

Reads the `gcns_stars` / `gcns_systems` / `gcns_system_members` / `gcns_system_pairs` DB tables, populated by CLI **option 58** (Import GCNS Data) — the GCNS backbone (331,312 sources to 100 pc) with **Bayesian distances + uncertainties**, plus a SIMBAD identity layer (spectral type / common name / Johnson V) attached by cross-match, plus the **resolved multiple-star systems** derived from `gcns.resolvedss`. No network call after the import. If the relevant table is empty, the `gcns_stars`-backed subcommands return `{"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}` and `gcns-system` returns the analogous `gcns_systems table is empty …`, both with exit 1. See `docs/star-databases.md` for the ingest/build, the cross-match, the resolved-system derivation, and the documented completeness limits.

**Per-star fields** (snake_case; any numeric field may be `null`):

| Field | Type | Meaning |
|---|---|---|
| `gaia_source_id` | int \| null | Gaia EDR3/DR3 source id. `null` for `missing_10mas` rows. |
| `ra`, `dec` | float | ICRS position, degrees (J2016.0). |
| `parallax`, `parallax_error` | float | mas. |
| `dist_pc` | float | **Bayesian** median distance (pc). For `missing_10mas` rows this is `1000/parallax` (1/ϖ inversion). |
| `dist_lo_pc`, `dist_hi_pc` | float \| null | 16th / 84th percentile distance (pc). `null` for `missing_10mas` (no Bayesian PDF). |
| `light_years` | float | `dist_pc × 3.26156`. |
| `phot_g_mean_mag`, `phot_bp_mean_mag`, `phot_rp_mean_mag` | float \| null | **Gaia bands — NOT Johnson V.** `null` for `missing_10mas`. |
| `rv_kms` | float \| null | Adopted radial velocity (km/s). |
| `wd_prob` | float \| null | Probability the source is a white dwarf. |
| `astrom_reliable_prob` | float \| null | GCNS probability the astrometry is reliable. |
| `spectral_type` | str \| null | SIMBAD spectral type (cross-match). `null` when unmatched — never fabricated. |
| `star_name` | str \| null | SIMBAD common name (cross-match); for `missing_10mas` defaults to the GCNS `main_id`. |
| `app_magnitude` | float \| null | SIMBAD **Johnson V** (cross-match). Distinct from the Gaia bands. |
| `in_gcns` | bool | Always `true` (row is GCNS-sourced). |
| `in_simbad` | bool | `true` if cross-matched to a `star_systems` row. |
| `distance_method` | str | `"gcns_bayesian"` (main) \| `"gcns_missing_plx_inversion"` (missing_10mas). |
| `gcns_table` | str | `"main"` \| `"missing_10mas"`. |
| `system_id` | int \| null | `gcns_systems.system_id` if this source is a member of a Gaia-resolved system; `null` otherwise (single/unresolved, or a `missing_10mas` row with no source_id). Join key for `gcns-system`. |
| `n_components` | int \| null | Component count of that resolved system; `null` if not a member. |

**Populating it:** the table is built by CLI **option 58** (Import GCNS Data) — a one-time ~331k-row pull from GAVO. GCNS is Gaia EDR3-based and static, so the data only changes when re-imported; `snapshot_date`/`gcns_version` record which build a result came from. `in_simbad` coverage depends on the `star_systems` build carrying Gaia/2MASS keys (currently ~70%). See `docs/star-databases.md`.

#### `gcns-within-sol`
All GCNS sources within N light years of Sol, sorted ascending by `light_years`.
```bash
query.py gcns-within-sol --ly 15
```
Core function: `databases.compute_gcns_within_sol(ly)`
Output: `{limit_ly, count, snapshot_date, gcns_version, stars[]}`. Each star carries the fields above plus heliocentric `x`/`y`/`z` (ly) for map parity with `stars-within-sol`. Example (abridged):
```json
{
  "limit_ly": 6.0,
  "count": 4,
  "snapshot_date": "2026-06-05",
  "gcns_version": "GCNS / Smart et al. 2021 A&A 649 A6 (VizieR J/A+A/649/A6) via GAVO gcns.main + gcns.missing_10mas + gcns.resolvedss",
  "stars": [
    {
      "gaia_source_id": 5853498713190525696,
      "ra": 217.3923, "dec": -62.6761,
      "parallax": 768.0665, "parallax_error": 0.0499,
      "dist_pc": 1.3019, "dist_lo_pc": 1.2771, "dist_hi_pc": 1.3020,
      "light_years": 4.2464,
      "phot_g_mean_mag": 8.9847, "phot_bp_mean_mag": 11.3731, "phot_rp_mean_mag": 7.5685,
      "rv_kms": -22.4, "wd_prob": 0.2144, "astrom_reliable_prob": 1.0,
      "spectral_type": "M5.5Ve", "star_name": "NAME Proxima Centauri", "app_magnitude": 11.13,
      "in_gcns": true, "in_simbad": true,
      "distance_method": "gcns_bayesian", "gcns_table": "main",
      "system_id": null, "n_components": null,
      "x": -1.55, "y": -1.18, "z": -3.77
    }
    // … α Cen A/B appear here as gcns_table "missing_10mas" with
    //   distance_method "gcns_missing_plx_inversion" and dist_lo_pc/dist_hi_pc = null
  ]
}
```

#### `gcns-source`
Single GCNS row by Gaia EDR3/DR3 `source_id` (the cross-match join key). EDR3 and DR3 source_ids are identical. The id can be taken from `simbad-lookup`'s `designations["Gaia EDR3"]` (strip the `"Gaia DR3 "` prefix).
```bash
query.py gcns-source --id 5853498713190525696
```
Core function: `databases.compute_gcns_by_source_id(id)`
Output: `{snapshot_date, gcns_version, star}` — `star` is a single dict with the fields above (no `x`/`y`/`z`) — or `{"error": ...}` if the id is not present (exit 1).

#### `gcns-system`
The resolved multiple-star system containing a Gaia EDR3/DR3 `source_id`. Derived from `gcns.resolvedss` (pair-keyed; systems are connected components — see `docs/star-databases.md`). Pass the `source_id` of **any** component; the whole system is returned.
```bash
query.py gcns-system --id 1872046609345556480   # 61 Cygni A → the 61 Cyg system
```
Core function: `databases.compute_gcns_system(id)`
Output: `{snapshot_date, gcns_version, query_source_id, system}`, or `{"error": ...}` (exit 1) when the id is in **no** resolved system (single/unresolved object) or the `gcns_systems` table is empty.

`system` is a dict:
- `system_id` (int, synthetic & stable per build), `n_components` (int), `n_pairs` (int).
- `any_bin`, `any_bound`, `all_bound` — bool|null, aggregated over the system's pairs (`bin` = pair probably part of a >2-star system; `bound` = probably gravitationally bound).
- `max_proj_sep_au`, `min_proj_sep_au` — float|null, projected separation extremes (AU).
- `n_in_gcns_stars` (int) — members that link to a `gcns_stars` row.
- `members` — list, one per component, sorted by `gaia_source_id`: `{gaia_source_id, in_gcns_stars (bool), is_query (bool — true for the queried id), star_name, spectral_type, dist_pc, light_years}`. The last four are joined from `gcns_stars` and are `null` for a member not present there (retained, not dropped).
- `pairs` — list of the raw `gcns.resolvedss` edges in this system, sorted by `proj_sep_au`: `{source_id1, source_id2, separation_arcsec, mag_diff, proj_sep_au, bin (bool|null), bound (bool|null)}`.

Example (61 Cygni, abridged):
```json
{
  "snapshot_date": "2026-06-05",
  "query_source_id": 1872046609345556480,
  "system": {
    "system_id": 1234, "n_components": 2, "n_pairs": 1,
    "any_bin": true, "any_bound": true, "all_bound": true,
    "max_proj_sep_au": 110.47, "min_proj_sep_au": 110.47, "n_in_gcns_stars": 2,
    "members": [
      {"gaia_source_id": 1872046574983497216, "in_gcns_stars": true, "is_query": false,
       "star_name": null, "spectral_type": null, "dist_pc": 3.4966, "light_years": 11.4042},
      {"gaia_source_id": 1872046609345556480, "in_gcns_stars": true, "is_query": true,
       "star_name": null, "spectral_type": null, "dist_pc": 3.4966, "light_years": 11.4042}
    ],
    "pairs": [
      {"source_id1": 1872046609345556480, "source_id2": 1872046574983497216,
       "separation_arcsec": 31.59, "mag_diff": 0.68, "proj_sep_au": 110.47,
       "bin": true, "bound": true}
    ]
  }
}
```

### GCNS-backed calculators (distance / travel-time / within-star)

GCNS-sourced versions of `distance`, `travel-time`, and `stars-within-star`, using the GCNS census (Bayesian distances + uncertainties) from the `gcns_stars` table instead of the SIMBAD-derived `star_systems` table. The existing SIMBAD-based subcommands are unchanged. Each endpoint accepts a **name** (`--star…`, resolved through SIMBAD) or a **Gaia EDR3/DR3 source_id** (`--id…`, fully offline). Populated by CLI **option 58** (Import GCNS Data); see `docs/star-databases.md`.

**Endpoint resolution** (`_resolve_gcns_row` in `core/databases.py`):
- `--id…`: direct `gcns_stars` fetch by `gaia_source_id` (offline). `missing_10mas` rows have a NULL `gaia_source_id` and are **not** id-addressable.
- `--star…`: SIMBAD lookup → extract the Gaia id from its designations → fetch by id. If SIMBAD itself errors (network/no-match), that error is returned (no fallback). If the resolved id is absent from `gcns_stars`, it falls through to an exact `star_name` match (case-insensitive) — this is how `missing_10mas` rows (e.g. Alpha Cen A/B) resolve.
- A star **truly absent** from GCNS returns `{"error": "… is not in the GCNS catalog …"}` — it is **never** silently substituted with a SIMBAD distance. An **ambiguous** name (matching >1 `gcns_stars` row) returns an error naming the candidate source_ids.

**Uncertainty:** every endpoint info block carries `distance_method` (`gcns_bayesian` vs `gcns_missing_plx_inversion`) plus `dist_pc` and `dist_lo_pc`/`dist_hi_pc` (the latter two are `null` for `missing_10mas` endpoints — point value only, no error bar). **No** combined/propagated separation or travel-time interval is computed — that is left to the consumer.

#### `gcns-distance`
3D Euclidean distance in light years between two GCNS stars.
```bash
query.py gcns-distance --id1 5853498713190525696 --id2 5853498618164729728
query.py gcns-distance --star1 "Proxima Centauri" --id2 5853498618164729728
```
Core function: `databases.compute_gcns_distance(star1=, id1=, star2=, id2=)`
Output: `{star1_info, star2_info, distance_ly, distance_au, snapshot_date, gcns_version}`. Each `*_info` block is the full GCNS per-star dict (the same fields as `gcns-source`'s `star`: `gaia_source_id, ra, dec, parallax, dist_pc, dist_lo_pc, dist_hi_pc, light_years, distance_method, spectral_type, star_name, …`) **plus** `ra_hms`/`dec_dms`. `distance_au` is `null` unless the two stars are `< 0.5` ly apart. A self-distance (same endpoint twice) returns `distance_ly ≈ 0` (not an error).

#### `gcns-travel-time`
GCNS-backed FTL travel time between two stars. Supply exactly one of `--ly-hr` or `--times-c`.
```bash
query.py gcns-travel-time --id1 5853498713190525696 --id2 5853498618164729728 --times-c 100
```
Core function: `databases.compute_gcns_travel_time(star1=, id1=, star2=, id2=, ly_hr=, times_c=)`
Output: `{origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str, snapshot_date, gcns_version}`. `origin_info` = endpoint 1 (`--star1`/`--id1`), `dest_info` = endpoint 2; both are the same info-block shape as `gcns-distance`. A zero (or negative) velocity returns an error.

#### `gcns-stars-within-star`
All GCNS stars within N light years of a center star, sorted ascending by 3D `Distance`.
```bash
query.py gcns-stars-within-star --star "Alpha Centauri A" --ly 1
query.py gcns-stars-within-star --id 5853498713190525696 --ly 5
```
Core function: `databases.compute_gcns_stars_within_star(star=, source_id=, limit_ly=)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, snapshot_date, gcns_version, stars[]}`. `center` is the resolved center row (with its own `x`/`y`/`z` added). Each star in `stars[]` mirrors `gcns-within-sol`'s row shape (the full GCNS fields + `system_id`/`n_components` + heliocentric `x`/`y`/`z`) **plus** a per-row `Distance` (ly from the center). The center itself is excluded **precisely** by `gaia_source_id` (with a `Distance < 1e-9` exact-self skip for a `missing_10mas` center that has no id), so Gaia-resolved **close companions remain** in the results — unlike the SIMBAD `stars-within-star`, which drops everything within `0.001` ly (~63 AU) of the center.

### Search & Filter (Phase G — local DB, except `search-exoplanets`)

The three interactive-search functions, exposed with **all filters optional** (omitting every filter returns the
first page up to the cap). Each returns `{count, capped, cap, stars[]}` (`capped=true` means the result hit the cap) or
`{"error": str}`. Spectral-class filtering uses the friendly **chips + refine** model: `--spectral-classes` takes one
or more of `O B A F G K M Other` (OR-ed leading-letter matches), and `--spectral-refine` is a case-insensitive
contains-match on the rest of the type (e.g. `V` for the luminosity class). See `docs/star-databases.md` (Phase G).

#### `search-star-systems`
Filter the local `star_systems` table (no network). Cap 500; sorted by light years.
```bash
query.py search-star-systems --spectral-classes M K --ly-max 20 --mag-max 10
```
Core function: `databases.search_star_systems(filters)`. Flags → filter keys: `--spectral-classes`/`--spectral-refine`,
`--ly-min`/`--ly-max`, `--mag-min`/`--mag-max`, `--designation-prefix`, and (Phase L4) `--fe-h-min`/`--fe-h-max` (an
inner JOIN onto `hypatia_cache` — matches nothing when that cache is empty; run **Import Hypatia Cache** first). Each
star: `{star_name, designations, spectral_type, parallax, parsecs, light_years, app_magnitude, ra, dec}`. Empty
`star_systems` → the opt-50 error.

#### `search-hwc`
Filter the local Habitable Worlds Catalog (no network). Cap 500; sorted by ESI descending.
```bash
query.py search-hwc --esi-min 0.8 --habitable --spectral-classes K G
```
Core function: `databases.search_hwc(filters)`. Flags: `--esi-min`; `--habitable` / `--habzone-con` / `--habzone-opt`
(store-true booleans); `--mass-min`/`--mass-max` (`P_MASS`), `--radius-min`/`--max` (`P_RADIUS`),
`--temp-min`/`--max` (`P_TEMP_EQUIL`); `--spectral-classes`/`--spectral-refine` (`S_TYPE`); `--ly-max`. Empty `hwc` →
the opt-52 error.

#### `search-exoplanets`
Filter the **live** NASA `pscomppars` archive via TAP. Cap 200; sorted by `pl_orbsmax`.
```bash
query.py search-exoplanets --radius-min 0.5 --radius-max 1.6 --dist-max-pc 15 --method "Transit"
```
Core function: `databases.search_exoplanets(filters)`. Flags → ADQL columns: `--mass-min`/`--max` (`pl_bmasse`),
`--radius-min`/`--max` (`pl_rade`), `--period-min`/`--max` (`pl_orbper`), `--teff-min`/`--max` (`st_teff`),
`--dist-max-pc` (`sy_dist`, **parsecs**), `--method` (`discoverymethod`, exact), `--spectral-classes`/`--spectral-refine`
(`st_spectype`). Network failures are classified to `{"error": str}`.

#### `search-hypatia`
Filter the **local Hypatia abundance cache** (Phase L4 — no network; populated by the GUI **Import Hypatia Cache**
utility / `databases.import_hypatia_cache`). Cap 500; sorted by Fe/H descending (NULL fe_h last).
```bash
query.py search-hypatia --fe-h-min 0.3 --ly-max 60 --element Mg --element-min 0.2
```
Core function: `databases.search_hypatia_cache(filters)`. Flags → filter keys: `--fe-h-min`/`--fe-h-max` (`[Fe/H]`),
`--teff-min`/`--teff-max`, `--ly-max` (`light_years`), `--disk` (exact Hypatia disk code, e.g. `0`=thin / `1`=thick),
`--element` (species symbol in API casing, e.g. `Mg`, `Ba_II`) + `--element-min`/`--element-max` (that species' [X/H],
via an `EXISTS` subquery). Each star: `{star_name, hip, hd, teff, logg, vmag, bv, distance_pc, disk, fe_h, light_years,
mg_h, si_h, o_h}` (`mg_h`/`si_h`/`o_h` are pivoted convenience [X/H] values; any may be `null`). Empty cache →
`{"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}`, exit 1.

> **Bulk-path caveat:** the cache carries the catalog-averaged **[X/H] mean** per element (the filter key) but not the
> spread (`std`/`min`/`max`/`n`) or UVW kinematics — those come from the live per-star `hypatia-data` subcommand. The
> Star Systems search also gained `--fe-h-min`/`--fe-h-max` (an inner JOIN onto this cache; matches nothing when the
> cache is empty).

#### `compare-stars`
Side-by-side comparison of **2–4 stars** in one structured result (Phase L1). Live network (SIMBAD + an optional NASA
pscomppars supplement + Hypatia). This is the one call that bundles work an external caller would otherwise have to
reassemble from `simbad-lookup` + `planetary-systems` + `hypatia-data` per star **and** re-derive itself: the NASA
radius/mass/(teff/lum) supplement, the photometric mass/radius/luminosity fallback, and the conservative HZ inner/outer
bounds.
```bash
query.py compare-stars --stars "Tau Ceti" Sol "18 Sco" "Delta Pavonis"
```
Core function: `databases.compare_stars(names)`. Output: `{stars: [{name, sp_type, teff, luminosity, mass, radius,
hz_inner_au, hz_outer_au, ly, app_magnitude, hypatia, error}, …]}` — `hypatia` is the raw `hypatia-data` result dict
(or `null`). **Per-star failures are isolated**: each star carries its own `error` (`null` on success) with missing
numerics `null`; the **only top-level `{"error"}` (exit 1)** is the arg-count check (< 2 non-blank names, or > 4).
`"Sol"`/`"Sun"` are injected from reference constants (G2V, 5778 K, 1 M/R/L☉, [X/H]≡0 baseline) with no SIMBAD call, so
`--stars Sol Sun` resolves fully offline. Missing/non-numeric `--stars` (or fewer than one value) is an argparse
**exit 2**.

### Reference data (Phase B — local DB / hardcoded, no arguments)

#### `main-sequence`
Main-sequence star properties table. Returns a **list** of 24 rows, one per spectral class, with the raw CSV columns
(`Spectral Class, B-V, Teeff(K), AbsMag Vis., AbsMag Bol., Bolo. Corr. (BC), Lum, R, M, p (g/cm3), Lifetime (years)`).
```bash
query.py main-sequence
```
Core function: `science.compute_main_sequence_table()`.

#### `solar-system`
Solar-system reference data. Output `{planets[], moons[], dwarf_planets[], asteroids[]}` (raw CSV columns per body).
```bash
query.py solar-system
```
Core function: `science.compute_solar_system_tables()`.

#### `sol-regions`
Sol's full system-regions computation from hardcoded solar constants (the opt-13 calculation). Output is the same flat
region dict as `star-regions` (`hzil, hzol, snowLine, lh2Line, bcLuminosity, stellarMass, distAU, the alternate-
biochemistry pairs, …`) but for the Sun, with no SIMBAD/Hypatia step.
```bash
query.py sol-regions
```
Core function: `regions.compute_sol_regions()`.

### Planetary / rotating-habitat equations (Phase B — pure math, no network)

> **Validation:** like the Phase-N pure-compute subcommands, these wrap the project's **older, non-self-validating**
> equation functions. Argparse rejects missing/non-numeric args (**exit 2**). Out-of-range values do **not** yield a
> curated error: where the math raises (e.g. `--rpm 0` → division by zero in `gravity-distance`), the top-level handler
> returns `{"error": str(e)}` (raw message, **exit 1**); where it doesn't (e.g. `orbit-distance --ecc 1.5` just yields a
> negative periastron), the result is returned as-is with **exit 0**. Validate ranges on the caller side.

#### `orbit-distance`
Periastron / apastron from semi-major axis + eccentricity (opt 33).
```bash
query.py orbit-distance --sma 1.0 --ecc 0.0167
```
Core function: `equations.compute_orbit_periastron_apastron(sma, ecc)`. Output: `{sma, ecc, periastron, apastron, ecc_au}`.

#### `moon-orbital-distance`
Orbital distance of an Earth-sized moon for a given day length (opts 34/35). `--day-hours` defaults to 24.
```bash
query.py moon-orbital-distance --planet-mass-earth 1.0 --day-hours 24
```
Core function: `equations.compute_moon_orbital_distance(planet_mass_earth, day_hours)`. Output:
`{planet_mass_earth, day_hours, orbital_distance_km}`.

#### `gravity-acceleration` / `gravity-distance` / `gravity-rpm`
The three rotating-habitat solves (opts 36/37/38) — each solves for the missing one of {rpm, radius, gravity}.
```bash
query.py gravity-acceleration --rpm 2 --radius-m 224     # → accel_ms2
query.py gravity-distance --rpm 2 --accel-ms2 9.81       # → radius_m
query.py gravity-rpm --accel-ms2 9.81 --radius-m 224     # → rpm
```
Core functions: `equations.compute_centrifugal_gravity_acceleration(rpm, radius_m)` /
`_distance(rpm, accel_ms2)` / `_rpm(accel_ms2, radius_m)`. Each output echoes all three values
(`{rpm, radius_m, accel_ms2}`) with the computed one filled in.

#### `travel-time-custom-thrust`
Travel time between two solar-system bodies with a **custom burn duration** (accelerate for the burn, coast, decelerate
for the same burn — the opt-23 calculation). **Live JPL Horizons** (the only network entry in this group).
```bash
query.py travel-time-custom-thrust --origin Earth --destination Mars --accel-g 1.0 --burn-value 2 --burn-unit D
```
Core function: `calculators.compute_travel_time_custom_thrust(origin, destination, accel_g, burn_duration_s,
v_cap_pct=3.0, burn_value=…, burn_unit_label=…, departure_date=None)`. `--burn-unit` is `H`/`D`/`W` (Hours/Days/Weeks,
default `D`); the CLI converts `--burn-value` + `--burn-unit` to `burn_duration_s` and passes the value/label through for
display. `--v-cap-pct` defaults to `3.0`; `--date` is ISO `YYYY-MM-DD` (default today). The GUI-only `progress_callback`
is never passed. Output: the full phase/burn-profile dict (`travel_time_str, t_total_hours, distance_au, distance_lm,
eff_burn_s, v_coast_ms, fallback, iterations_done, …`). Ambiguous Horizons names return the disambiguation error from
the core function.

## Two-step subcommands

For subcommands that run SIMBAD first (`star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, `hwc`, `hypatia-data`): if the SIMBAD lookup returns `{"error": ...}`, that error is returned immediately and the second core function is never called.

`dossier` (Phase Q) runs SIMBAD first for a real star and aborts with that error if it fails; per-section sources that fail *after* SIMBAD resolves become warnings, not errors. `dossier --star Sol`/`Sun` runs no SIMBAD/network step at all (the offline reference-origin path; it reads the local Solar System tables, overridable via `SPACE_APP_DB`).

`generate-system` (Phase R1) runs **no network in synthetic mode** (no `--anchor-star`). With `--anchor-star` it runs SIMBAD first (then `compute_star_system_regions_from_simbad` + NASA pscomppars / HWC); an unresolvable anchor or a non-OBAFGKM (e.g. white-dwarf) regions failure is returned immediately as `{"error": ...}`, while missing observed planets is a `warnings[]` entry, not an error.

The `gcns-within-sol`, `gcns-source`, and `gcns-system` subcommands are **local DB reads** (no SIMBAD step). The `gcns-distance` / `gcns-travel-time` / `gcns-stars-within-star` calculators are local DB reads **except** for `--star…` endpoints, which add a SIMBAD name-resolution step (a SIMBAD error on any `--star…` endpoint is returned immediately). The DB path can be overridden with the `SPACE_APP_DB` environment variable (used by tests).

## Implementation notes

- No `sys.path` manipulation — Python prepends the script's own directory automatically when run directly, so `import core.X` works without changes.
- Unexpected exceptions from core functions are caught by a top-level handler in `main()` and returned as `{"error": str(e)}` with exit code 1.
- `--ly-hr` and `--times-c` are a mutually exclusive required group for `travel-time`, `optimal-tour`, and `multi-stop`; supplying both or neither is rejected by `argparse` with exit code 2.
- The `gcns-*` calculators use one required mutually-exclusive group **per endpoint** (`--star1`/`--id1`, `--star2`/`--id2`, or `--star`/`--id`), plus the `--ly-hr`/`--times-c` group for `gcns-travel-time`. Supplying both or neither within any group is rejected by `argparse` with **exit code 2** and a message on **stderr** — this is the argparse path, **not** the JSON-`{"error"}`/exit-1 path, so do not parse stdout as JSON for those invocations. A resolvable-but-invalid request (e.g. a name not in GCNS, an ambiguous name, or an empty `gcns_stars` table) instead returns `{"error": ...}` on stdout with exit 1.
- **Phase N validation asymmetry** (see "Integration expansion (Phase N)" above): the pure-compute Phase-N subcommands (`habitable-zone-sma`, `star-luminosity`, `brachistochrone-au`, `brachistochrone-lm`) wrap **non-self-validating** legacy core functions, so out-of-range numerics surface via the generic top-level handler as `{"error": str(e)}` with a **raw exception message** (not a curated sentence), exit 1 — except `star-luminosity`, which has no out-of-range error path (only argparse exit 2). Only `travel-time-solar` returns curated `{"error": ...}` dicts. This is intentional (Phase N adds no `core/` validation); key on `"error"` + exit code, never on the message text.
