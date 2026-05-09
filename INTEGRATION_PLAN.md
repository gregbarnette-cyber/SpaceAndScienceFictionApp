# Integration Plan: SpaceAndScienceFictionApp → ScienceFictionResearch

## Context

The `core/` modules already expose clean Python APIs returning plain Python dicts. The goal
is a thin CLI script that calls those functions and writes JSON to stdout, so the
ScienceFictionResearch repo can invoke them via its Bash tool without any web searching for
stellar data.

---

## Phase 1 — Fix `core/regions.py` (one function, one file)

**File:** `core/regions.py`
**Function:** `_load_main_sequence_data()`

Currently reads `propertiesOfMainSequenceStars.csv` directly. The `main_sequence_stars` DB
table already has these 24 rows (auto-seeded at startup). Fix: query the DB and reconstruct
row dicts using the original CSV column names that the rest of `regions.py` already expects
(`"Spectral Class"`, `"Bolo. Corr. (BC)"`, etc.). The column mapping is fully known from
`db.py`'s `_seed_main_sequence`.

No other changes to `regions.py` or any other file. Everything that calls
`_load_main_sequence_data()` continues to work unchanged.

---

## Phase 2 — Write `query.py` at the repo root

A single dispatcher script. Accepts subcommands with named arguments, calls the appropriate
`core/` function, and prints `json.dumps(result, indent=2)` to stdout. Exits with code 1 if
the result contains `{"error": ...}`.

### Subcommands

| Subcommand | Arguments | Core function(s) called |
|---|---|---|
| `simbad-lookup` | `--star` | `databases.compute_simbad_lookup` |
| `star-regions` | `--star` | `compute_simbad_lookup` → `regions.compute_star_system_regions_from_simbad` |
| `distance` | `--star1`, `--star2` | `calculators.compute_distance_between_stars` |
| `stars-within-star` | `--star`, `--ly` | `calculators.compute_stars_within_distance_of_star` |
| `stars-within-sol` | `--ly` | `calculators.compute_stars_within_distance_of_sol` |
| `travel-time` | `--star1`, `--star2`, `--ly-hr` OR `--times-c` | `calculators.compute_travel_time_between_stars` |
| `habitable-zone` | `--teff`, `--luminosity` | `equations.compute_habitable_zone` |
| `exoplanets` | `--star` | `compute_simbad_lookup` → `databases.compute_exoplanet_archive` |
| `planetary-systems` | `--star` | `compute_simbad_lookup` → `databases.compute_planetary_systems_composite` |
| `hwo-exep` | `--star` | `compute_simbad_lookup` → `databases.compute_hwo_exep` |
| `mission-exocat` | `--star` | `compute_simbad_lookup` → `databases.compute_mission_exocat` |
| `hwc` | `--star` | `compute_simbad_lookup` → `databases.compute_hwc` |

### Implementation notes

- Script lives at repo root; `import core.X` works without any `sys.path` manipulation since
  the script's own directory is automatically on the path when run directly
- Always JSON to stdout — errors included as `{"error": "..."}`, consistent with how core
  functions already signal failure
- Exit code 0 on success, 1 on error — lets the calling Bash tool detect failures cleanly
- For two-step functions (simbad → target), the intermediate `simbad_result` error is caught
  and returned before calling the second function

---

## Phase 3 — How the research repo calls it

From the ScienceFictionResearch repo, via the Bash tool:

```bash
/home/greg/Claude/SpaceAndScienceFictionApp/venv/bin/python \
  /home/greg/Claude/SpaceAndScienceFictionApp/query.py \
  <subcommand> [arguments]
```

### Examples

```bash
# Full star data from SIMBAD
query.py simbad-lookup --star "Epsilon Indi"

# System regions: HZ boundaries, snow line, stellar mass/luminosity/radius
query.py star-regions --star "61 Cygni A"

# 3D distance between two stars
query.py distance --star1 "Sol" --star2 "GJ 876"

# All stars within 5 ly of Epsilon Eridani
query.py stars-within-star --star "Epsilon Eridani" --ly 5

# All stars within 15 ly of Sol
query.py stars-within-sol --ly 15

# FTL travel time at 100×c
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --times-c 100

# FTL travel time at 0.01 ly/hr
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --ly-hr 0.01

# Habitable zone boundaries from stellar parameters
query.py habitable-zone --teff 4900 --luminosity 0.15

# Confirmed HZ planets from local DB (5,599 rows, no network needed)
query.py hwc --star "Tau Ceti"

# NASA Mission Exocat from local DB (2,396 rows, no network needed)
query.py mission-exocat --star "Epsilon Indi"

# NASA Exoplanet Archive — all tables (live network call)
query.py exoplanets --star "Epsilon Eridani"

# NASA Exoplanet Archive — planetary systems composite only (live network call)
query.py planetary-systems --star "Epsilon Eridani"

# HWO ExEP direct-imaging target list (live network call)
query.py hwo-exep --star "Tau Ceti"
```

---

## What is not changing

- No changes to `main.py`, the GUI, or any existing `core/` function signatures
- No changes to the DB or CSV files
- No `setup.py` or `pyproject.toml` needed
- The ScienceFictionResearch repo does not get a copy of any `core/` code

---

## File summary

| File | Action |
|---|---|
| `core/regions.py` | Edit — `_load_main_sequence_data()` only |
| `query.py` | Create new |
