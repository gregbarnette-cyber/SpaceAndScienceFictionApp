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

† `distance` and `travel-time` skip the SIMBAD call for an endpoint named `"Sol"`/`"Sun"` (treated as the origin at 0,0,0).

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
Output: `{main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, desig_str, designations}`. `designations` is a dict keyed by catalog (`MAIN_ID, NAME, GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS`); absent catalogs are omitted. Numeric fields may be `null`.

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

## Two-step subcommands

For subcommands that run SIMBAD first (`star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, `hwc`, `hypatia-data`): if the SIMBAD lookup returns `{"error": ...}`, that error is returned immediately and the second core function is never called.

## Implementation notes

- No `sys.path` manipulation — Python prepends the script's own directory automatically when run directly, so `import core.X` works without changes.
- Unexpected exceptions from core functions are caught by a top-level handler in `main()` and returned as `{"error": str(e)}` with exit code 1.
- `--ly-hr` and `--times-c` for `travel-time` are a mutually exclusive required group; supplying both or neither is rejected by `argparse` with exit code 2.
