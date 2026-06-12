# Integration Tool Documentation — `query.py`

`query.py` is a thin JSON dispatcher at the repo root. It allows the ScienceFictionResearch repo (and any other caller) to invoke `core/` functions via a Bash command and receive structured JSON on stdout without needing a copy of the core code.

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
| `simbad-lookup` | `--star` | SIMBAD | `main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, designations, desig_str` |
| `star-regions` | `--star` | SIMBAD + Hypatia | region values (see below) + `simbad` + `hypatia` |
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

† `distance` and `travel-time` skip the SIMBAD call for an endpoint named `"Sol"`/`"Sun"` (treated as the origin at 0,0,0).
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
Output: `{main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, desig_str, designations}`. `designations` is a dict keyed by catalog (`MAIN_ID, NAME, GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS`); a catalog with no id is `null`. Numeric fields may be `null`.
- **Gaia id**: the `"Gaia EDR3"` key holds the Gaia source id as SIMBAD now formats it — `"Gaia DR3 <id>"` (SIMBAD renamed EDR3→DR3 in its id output; the source_ids are identical). To get the bare numeric id, strip the `"Gaia DR3 "` / `"Gaia EDR3 "` prefix. This is the same id used as `--id` for `gcns-source`.

#### `star-regions`
Star system regions: HZ boundaries, snow line, stellar mass/luminosity/radius, alternate biochemistry zones, plus Hypatia Catalog stellar properties and elemental abundances.
Uses hardcoded `sunlight_intensity=1.0`, `bond_albedo=0.3`.
```bash
query.py star-regions --star "61 Cygni A"
```
Core functions: `databases.compute_simbad_lookup` → `regions.compute_star_system_regions_from_simbad` + `databases.compute_hypatia_data`

Output: a flat dict of computed region values — stellar (`stellarMass, stellarRadius, bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, …`), distance (`parsecs, lightYears, distAU, distKM`), Earth-equivalent orbit (`planetaryYear, planetaryTemperature{,C,F}, sizeOfSun`), and zone boundaries in AU (`hzil, hzol, snowLine, lh2Line, sysol, sysilGrav, sysilSunlight`, plus the alternate-biochemistry pairs `ffInner/ffOuter, fsInner/fsOuter, prwInner/prwOuter, praInner/praOuter, pmInner/pmOuter, phInner/phOuter`) — plus `spectral_type`, `bc_key`, and the embedded `simbad` dict.
The result dict also includes a top-level `"hypatia"` key: `{"star_name", "properties", "abundances"}` on success, or `{"error": str}` if the Hypatia API call fails. The regions result is always returned even when Hypatia fails.

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
Output: `{limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Light Years", x, y, z}` (x/y/z are heliocentric light-year coords, may be `null`). Sorted ascending by Light Years.

#### `stars-within-star`
All stars in the `star_systems` DB table within N light years of a named star. Queries SIMBAD for the center star.
```bash
query.py stars-within-star --star "Epsilon Eridani" --ly 5
```
Core function: `calculators.compute_stars_within_distance_of_star(star, ly)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Distance", x, y, z}` (`Distance` in ly from the center star). Sorted ascending by Distance.

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

## Two-step subcommands

For subcommands that run SIMBAD first (`star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, `hwc`, `hypatia-data`): if the SIMBAD lookup returns `{"error": ...}`, that error is returned immediately and the second core function is never called.

The `gcns-within-sol`, `gcns-source`, and `gcns-system` subcommands are **local DB reads** (no SIMBAD step). The `gcns-distance` / `gcns-travel-time` / `gcns-stars-within-star` calculators are local DB reads **except** for `--star…` endpoints, which add a SIMBAD name-resolution step (a SIMBAD error on any `--star…` endpoint is returned immediately). The DB path can be overridden with the `SPACE_APP_DB` environment variable (used by tests).

## Implementation notes

- No `sys.path` manipulation — Python prepends the script's own directory automatically when run directly, so `import core.X` works without changes.
- Unexpected exceptions from core functions are caught by a top-level handler in `main()` and returned as `{"error": str(e)}` with exit code 1.
- `--ly-hr` and `--times-c` for `travel-time` are a mutually exclusive required group; supplying both or neither is rejected by `argparse` with exit code 2.
- The `gcns-*` calculators use one required mutually-exclusive group **per endpoint** (`--star1`/`--id1`, `--star2`/`--id2`, or `--star`/`--id`), plus the `--ly-hr`/`--times-c` group for `gcns-travel-time`. Supplying both or neither within any group is rejected by `argparse` with **exit code 2** and a message on **stderr** — this is the argparse path, **not** the JSON-`{"error"}`/exit-1 path, so do not parse stdout as JSON for those invocations. A resolvable-but-invalid request (e.g. a name not in GCNS, an ambiguous name, or an empty `gcns_stars` table) instead returns `{"error": ...}` on stdout with exit 1.
