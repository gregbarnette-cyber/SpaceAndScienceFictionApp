# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI app
python main.py

# Run the GUI app
python gui_main.py

# Query core functions as JSON (integration tool)
python query.py <subcommand> [arguments]

# Run the test suite (pytest is the runner — always invoke via the VENV)
venv/bin/python -m pytest
# NOTE: use the venv python, not a bare `pytest` — a system-wide pytest runs on
# system Python, which lacks this project's deps (numpy, astroquery, …) and fails
# at collection. pytest is a test-only dep in requirements.txt (the app doesn't need it).
```

### Development environment

The repo is developed on both Windows and WSL2; keep commands/scripts cross-OS (the `query.py`
invocation already handles the Windows `venv/Scripts/python.exe` vs Linux `venv/bin/python` split and
the base-folder case fallback — see `docs/integration.md`).

**Phase T dust path (`dustmaps`/`healpy`) is WSL/Linux-only.** `healpy` has **no Windows pip wheel**, so
`pip install dustmaps` fails on a native-Windows checkout. (Native Windows *can* still serve the dust
subcommands via a conda-forge/micromamba env reached by the `query.py` `SPACE_APP_DUST_PYTHON`
re-dispatch shim — `_needs_dust`/`_redispatch_to_dust_env`, a **no-op wherever the dust extra imports**
(probed via `core.dust._dustmaps_available`), so WSL/Linux/macOS are byte-identical; setup in
`DUST_WINDOWS_MICROMAMBA_PLAN.md`.) Build, run, and test the Phase T **dust**
subcommands (`dust-sightline` / `dust-between`; CLI option-59 dust-fetch; and the dust-weighted routing
`--weight dust` on `jump-route`/`optimal-tour`/`multi-stop`/`nearest-neighbor`/`trade-route`, in
`core/dust_routing.py`) from the **WSL/Linux venv** — which is also the path the sister consumer repo invokes. The optional
extra is **`requirements-dust.txt`** (`dustmaps, healpy, h5py, scipy, progressbar2, six, tqdm`) — installed on
top of base `requirements.txt`, **never** in it; there is no `setup.py`/`pyproject.toml`, so the
`extras_require['dust']` form is aspirational. `core/dust.py` is the **only** module that imports
`dustmaps`/`healpy`, lazily, so the stellar layer stays importable on a Windows checkout; dust tests gate on
`dustmaps` importability (`tests/_dustcheck.py`, like the `*_live.py` network gate) so a Windows checkout skips
them cleanly; the **real-map-loading anchors additionally gate on an opt-in `SPACE_APP_RUN_HEAVY_DUST=1`**
(`_dustcheck.heavy_dust_enabled()`), so a routine `pytest -q` never loads the multi-GB cube — loading it
mid-sweep OOM-crashed the 8 GB WSL box (2026-08-02); the dust logic stays covered by the mocked tests.
**Maps:** Leike 2020 (`leike2020`) + **Edenhofer 2024 — the dustmaps key/module is
`edenhofer2023`** (paper 2024, arXiv/dustmaps 2023). Output is standardized to **A_V (mag, R_V=3.1)** via pinned
per-map scalars (Edenhofer `A_V=2.8·E`; Leike `A_V=1.0857·1.202·τ_G`), with a `native_value`/`native_quantity`
echo. The cache lives in `data/dust/` (gitignored, native WSL FS). This scopes to the dust path only — the rest
of the app (including all of Phase T's pure-math calculators) remains fully cross-OS. See `completed_plans/PHASE_T_PLAN.md`
(Part A + Part B built 2026-06-23 — Phase T complete) and `docs/integration.md` (Dust / ISM section).
Dust-weighted routing reuses a `_grid_search` seam extracted from `compute_jump_route` (byte-identical for
`--weight distance`, guarded by the route tests). A second, higher-level seam — **`_route_through`**
(the required-`via` waypoint metric closure / ordering / stitching, a passthrough to a single
`_grid_search` when no waypoints are given; see `docs/calculators.md` §B "Required waypoints") — wraps
`_grid_search` and is shared by **all three** jump-route planners, each passing its own `edge_cost`, so
`jump-route --via` composes with every `--weight` value and the waypoint order is chosen under the
selected metric (`completed_plans/JUMP_ROUTE_WAYPOINTS_PLAN.md`, built 2026-07-31).
`--weight dust` minimizes integrated A_V over the same
graph (reachability stays geometric) and reports a distance-optimal `extra_ly`/`saved_av` comparison. Tests:
`tests/_dustcheck.py` (the gate), `tests/test_dust_query.py` (Part A), `tests/test_dust_routing.py` (Part B).
The **fetch utility** (option 59) also has a GUI panel — `FetchDustMapPanel` (Utilities nav,
`ImportGcnsPanel`-style, gated on the dust extra); the dust *query* subcommands stay `query.py`-only. The
maps live on **Zenodo**, which bandwidth-throttles large downloads (~0.5 MB/s) and the dustmaps fetcher can't
resume — so the panel shows a copyable **"Manual download"** box with resumable `aria2c -c`/`wget -c` commands
(into `data/dust/{leike_2020,edenhofer_2023}/`, then **Check Status** verifies the md5). See the Zenodo-throttle
note in `docs/integration.md` (Dust / ISM). The **Database Table Status** panel (option 57, `DbStatusPanel`) also
lists the two cached map **files** (presence + size in MB) beneath the DB tables, via the pure-pathlib
`core.dust.get_dust_map_status()` (no `dustmaps` import, so it reports even without the extra) — the maps are
files, not a SQLite table, so this is file-presence status rather than a row count.

### Tests

Tests live in `tests/`. The bulk are **offline** and need no network or Qt. Tests that touch the SQLite store never mutate `data/space_app.db`: in-process tests monkeypatch `core.db._DB_PATH` to a tmp file with auto-seeding disabled (pattern in `tests/test_gcns.py`, `tests/test_regions.py`, `tests/test_db_backups.py`), and the `query.py` subprocess tests pass a throwaway DB via the `SPACE_APP_DB` environment variable (via the shared `tests/_queryharness.py` harness). The twelve `*_live.py` files (`test_catalog_live`, `test_cr25_live`, `test_designation_live`, `test_gcns_live`, `test_hypatia_live`, `test_oec_live`, `test_query_detection_live`, `test_query_dossier_live`, `test_query_exclusion_system_live`, `test_query_exoplanet_batch_live`, `test_query_stellar_mass_live`, `test_wikipedia_live`) **and** the live-gated classes in `test_query_expanded`/`test_query_phase_n`/`test_cr19`/`test_debris_disk`/`test_query_debris`/`test_multiplicity`/`test_query_multiplicity`/`test_kinematics`/`test_binary_stability_auto`/`test_query_binary_stability` hit the **live network**. As of 2026-08-03 they are **opt-in**: every one gates on `tests/_netcheck.live_enabled()` (**`SPACE_APP_RUN_LIVE=1`**) *and* host reachability (exception: `test_query_par_flux.py::StarPathLiveTest` gates on its own `RUN_NETWORK_TESTS=1`), so a routine `pytest -q` skips all of them without opening a socket (the reachability probe is short-circuited). Set `SPACE_APP_RUN_LIVE=1 venv/bin/python -m pytest` to run them — they add ~7–8 min and still skip cleanly if a service is down. This mirrors the `SPACE_APP_RUN_HEAVY_DUST=1` dust gate; the two local probes (`_reachable`/`_horizons_reachable`) short-circuit on the same flag, and the `query.py` runtime reachability gates that reuse `_netcheck.reachable()` are unaffected (they never consult `live_enabled()`).

**`pytest` is the runner.** The tests are written as `unittest.TestCase` classes, which pytest collects natively (`pytest.ini` sets `testpaths = tests`). Always invoke via `venv/bin/python -m pytest` — a bare `pytest` may resolve to system Python without this project's deps.

Current state (default `pytest -q`, live tests skipped): **3574 passed, 102 skipped, 519 subtests, 0 failures** (2026-09-24, after CR-22.6). Of the 102 skips, **2** are the opt-in real-dust-map tests (`SPACE_APP_RUN_HEAVY_DUST=1`), **1** is `test_query_par_flux.py::StarPathLiveTest` (`RUN_NETWORK_TESTS=1`), and **99** are the opt-in live-network tests (`SPACE_APP_RUN_LIVE=1`). With `SPACE_APP_RUN_LIVE=1` and the network up it is ~3673 passed / 3 skipped and takes ~18–22 min; the default run takes ~11–14 min and is memory-safe on the 8 GB WSL box (it never loads the multi-GB dust cube — that OOM-crashed WSL 2026-08-02 — and never opens a socket). When a change adds tests, update the count here and append the history entry to `docs/testing.md` (**Suite-count history** — the per-CR record of how the count grew); per-CR contracts live in `docs/integration.md` and plans in `completed_plans/`.

**Per-test-file descriptions live in `docs/testing.md`** (read-on-demand — read it before adding or modifying tests).

## Architecture

The project has three entry points that share all computation through the `core/` package:

- **`main.py`** — CLI. All features are top-level functions registered in `MENU_OPTIONS`.
- **`gui_main.py`** — PySide6 GUI. Navigation tree on the left, panel stack on the right.
- **`query.py`** — JSON dispatcher. Calls `core/` functions and writes JSON to stdout; used by the `scifiWorldBuilding-Claude` repo (current consumer; formerly `ScienceFictionResearch-Claude`) via its Bash tool / `bin/sfq` wrapper.
- **`core/`** — Pure computation layer (no I/O, no Qt), called by all three entry points. Short map below; the full per-module description with phase/CR provenance is in **`docs/core-modules.md`** (read-on-demand).
  - **Foundation:** `equations.py` (physics constants, HZ/Kopparapu Seff, solvent/ice lines, worldbuilding + stellar-evolution calculators), `calculators.py` (distance/travel-time/brachistochrone/route planning + JPL Horizons), `regions.py` (star-system regions), `science.py` (Honorverse + main-sequence/solar-system tables), `shared.py` (network retry/timeout helpers, designation + spectral parsing, search-filter SQL, the one spectral palette, the `_SOL_*` constants), `databases.py` (SIMBAD/NASA/HWC/Mission-Exocat/GCNS/Hypatia/OEC readers + importers), `db.py` (SQLite schema/connection), `viz.py` (matplotlib data prep).
  - **GUI + query features:** `report.py` (system dossier), `generate.py`/`priors.py`/`feasibility.py`/`nbody.py`/`research_priors.py` (procedural generator + research-priors v2 — contract in `docs/research-priors-contract.md`), `projects.py`, `hypatia_elements.py`, `dust.py`/`dust_routing.py`, `oec_derived.py` (OEC System View derived layer), `wikipedia.py` (GUI Wikipedia-tab resolver).
  - **`query.py`-only calculator packs** (for the sibling repo; several ship an `*_tables.py` of bundled data): `cooling`, `thermal`, `spin`, `life_support`, `propulsion`, `megastructure`, `par_flux`, `terraforming`, `ism_drag`, `active_shield`, `dust_impact`, `volatile_delivery` (Phases U–AD); `astro_bodies`, `gravitation`, `relativity`, `exotic_physics`, `warp`, `black_hole` (AE–AI); `formation` (AJ); `metric_drive`, `exclusion_boundary`, `exclusion_wall`, `exclusion_system` (AK + CR-11/22/23/25); `power`, `energy_storage`, `power_tables` (AL); `catalog_cache`, `catalog`, `binary`, `besancon` (AM — the live catalog tier); `sensing`, `strategic_geography` (AP–AR); `radiation` (AS); `salvo`, `weapons` (AT); `debris_disk`, `kinematics`, `nuclear`, `detection`, `exoplanet_batch`, `stellar_mass`, `stellar_mass_tables`, `rv_precision_tables` (star-analysis CRs).
- **`gui/`** — Qt presentation layer: `app.py` (MainWindow), `nav.py` (navigation tree), `panels/` (one class per feature; `panels/oec_detail.py` is the exception — a per-tag field registry + section builders for opt 7's detail pane, plus the shared OEC value formatters that `panels/catalogs.py` imports; `panels/wikipedia_tab.py` is the shared in-app **Wikipedia article tab** — `WikipediaView` + `WikipediaButtonMixin` + `open_or_focus_wiki_tab`, backed by the Qt-free `core/wikipedia.py` resolver/fetcher and the `base.run_in_thread`/`_BgDeliveryMixin` shared threading; wired into the six star-facing panels — see `docs/gui-architecture.md` and `docs/star-databases.md`).

**Read-on-demand references (deliberately NOT auto-loaded — large; read them before the relevant work so the session context stays light):**
- `docs/integration.md` — the `query.py` subcommand contract (arguments + JSON output keys + exit-code behavior). **Read it before adding, modifying, or verifying any `query.py` subcommand** (it is the contract the `scifiWorldBuilding-Claude` consumer reads).
- `docs/gui-architecture.md` — the full GUI structure, panel class → option mapping, and phase completion status. **Read it before touching `gui/` panels or the phase-status table.**
- `docs/testing.md` — the per-test-file catalog (what each `tests/test_*.py` covers). **Read it before adding or modifying tests.**
- **Per-feature references (formerly auto-imported; read before working on that feature):** `docs/star-databases.md` (opts 1–7, 50–59, GCNS, Gould, Search & Filter, Comparison, Hypatia cache, Wikipedia tab), `docs/star-system-regions.md` (opts 8–10, Hypatia tab), `docs/science-and-scifi.md` (opts 11–16, Honorverse), `docs/calculators.md` (opts 17–32, Route Planning, dust routing, detectability), `docs/equations.md` (opts 33–41, worldbuilding, solvent zones, research-tooling calculators).
- `docs/core-modules.md` — the full `core/` module description with phase/CR provenance.
- `docs/query-commands-index.md` — a one-line-per-subcommand index of all 182 `query.py` subcommands, grouped by family (a navigation aid; `docs/integration.md` stays the contract).
- `completed_plans/` — implementation plans + mockups for **shipped** work (74 files, indexed in `completed_plans/README.md`). Moved out of the repo root 2026-07-27. Plans for work that is *not* finished stay at the root: `future_phases.md` (roadmap), `IMPROVEMENT_PLAN.md` (P4.6 still PARTIALLY DONE — the **sexagesimal RA/Dec** half; its *designation* half closed 2026-07-29 with Phase AN0), `DUST_WINDOWS_MICROMAMBA_PLAN.md` (code shipped; native-Windows Part A/E2 pending) and `DOSSIER_EXTENSION_INVESTIGATION.md` (notes, not a plan). **`completed_plans/PHASE_AN_PLAN.md`** (Bayer & Flamsteed designations) **completed 2026-07-29** — all nine parts, all nine decisions. What it leaves behind, in force: `core.shared` is the single designation parser — **do not add a local prefix map or key list anywhere**; `compute_simbad_lookup`'s `designations` carries `Bayer`/`Flamsteed` from the `_classify_star_id` `* ` pre-pass, deduped against `MAIN_ID` in the rendered `desig_str` only; rendering (`core.shared.format_star_designation` → `10 Canis Minoris`, and the four-banner GUI line `gui.panels.base.add_designation_names_line`) is **display-only and never stored**, so the raw SIMBAD string stays the identifier; `core.shared.strip_star_prefix` is the one prefix stripper — open-coding the slice reintroduces the Flamsteed double-space bug. **The D4 deferral is discharged** — option 50 was re-run 2026-07-29, so `star_systems.designations` carries the new keys (2135 rows; 256,003 rows before and after, 0 discarded) and every DB-backed surface sees them. This folder also absorbed the former `archive/` directory (pre-`PHASE_*`-era plans).
- `completed_plans/SPECTRAL_CLASS_PLAN.md` — the spectral-class **prefix** rule (built 2026-07-27): why the search chips use case-sensitive `GLOB` rather than `LIKE`, the `_SP_CLASS_PREFIXES` / `_SP_DISPLAY_LETTERS` two-alphabet split, and the colour/legend bucketing. **Read it before touching `spectral_where`, `spectral_leading_class`, `sp_color`/`_sp_color`, `_display_class`, or any spectral-type string handling** (the `_star_map_color` second palette it describes was deleted 2026-07-27 — see `completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` Phase 3) — the load-bearing detail is that SQLite `LIKE` is case-**insensitive**, so it cannot tell the lowercase *dwarf* prefix `d` (`dM6` = Wolf 359) from the uppercase *degenerate* prefix `D` (`DA` = a white dwarf).
- `completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` — **COMPLETE, built 2026-07-27**: the 7 Route Planning star charts now go
  through the shared `_build_iso_chart_tab` (via an additive `routes=` passthrough on it and
  `_build_star_chart_3d_tab`), so they carry the O16 legend filter, the O17 isochrone control and the 3D
  presets; the duplicate `_route_chart_3d_tab` is gone. Two seams to know: `_build_iso_chart_tab` takes
  `legend_filter=True` (**`JumpNetworkPanel` passes `False`** — its dots are per-tier coloured, so a
  class-grouped legend would mislabel them), and the O15 linking helpers take `name_col=0` (**the route
  tables pass 1** — they all lead with an index column, `Hop #`/`Step`/`Jumps`). Tests:
  `tests/test_route_chart_tabs.py` (these tabs had no coverage at all before). **Panel descriptions
  (2026-07-27, separate from the refactor):** each of the seven panels carries a `DESCRIPTION` class
  attribute rendered as a hidden label at the **top of the results pane**, toggled by a Show/Hide
  Description button in `_button_row`. The seam to respect: `_clear_tables_layout` now clears from
  `panel._tables_keep`, **not** index 0, so a Run can't delete the label out from under its button
  (`RouteDescriptionTest` pins it). **Phase 3 (same date) retired the
  second palette**: `core.calculators._star_map_color` is **deleted** and the one app-wide palette now lives in
  **`core/shared.py`** (`_SPECTRAL_COLORS` + `sp_color()`), beside the `spectral_leading_class`/`_SP_DISPLAY_LETTERS`
  rule it keys off, so colour and bucketing can't drift apart again; `core/viz.py` re-exports it under its historical
  `_SPECTRAL_COLORS`/`_sp_color` names, so no display site changed. **Do not add a local palette anywhere** —
  `tests/test_search.py::test_there_is_exactly_one_spectral_palette` fails if you do. This repainted four values
  (G/M/D + the unknown grey) on the 7 route panels, opts 17/20/21, and the `stars[].color` of the route
  `query.py` subcommands (noted in `docs/integration.md`).

### Guardrails (load-bearing rules — details in the linked docs)

- **One designation parser:** `core.shared` owns the designation prefix map/key lists — never add a local copy (in `main.py`, `core/databases.py`, or anywhere); `core.shared.strip_star_prefix` is the one prefix stripper. Bayer/Flamsteed/Gould rendering is display-only, never stored. The 88 constellation genitives live in `core/shared.py`. Gould's 1875 boundaries disagree with the IAU's for some stars — correct, don't reconcile. (`docs/star-databases.md`)
- **One spectral palette + GLOB, not LIKE:** `core.shared._SPECTRAL_COLORS`/`sp_color` is the only palette (a test fails on a second one). Spectral-class SQL uses case-sensitive `GLOB` because `LIKE` can't tell `dM6` from `DA`. Read `completed_plans/SPECTRAL_CLASS_PLAN.md` before touching spectral-type handling.
- **Frozen generator:** `compute_exclusion_boundary` is FROZEN — layer new behaviour in the callers (`compute_two_layer_boundary`, `exclusion_system`), keeping the standoff anchors byte-identical.
- **Dust isolation:** `core/dust.py` is the only module that imports `dustmaps`/`healpy`.
- **Solar-system tables:** never rank the asteroid table by diameter (nine TNOs have `N/A`); nine famous small bodies are included by name, not by the size cutoff; watch the `asteroids` ∩ `dwarf_planets` overlap. Numbered small-body Horizons ids need the trailing `;`. (`docs/science-and-scifi.md`, `docs/calculators.md`)
- **Seeded DB tables:** `data/space_app.db` is gitignored and auto-seeding fires only on an **empty** table — after pulling changed CSVs, re-run the matching import option (e.g. 55).
- **Synthetic Sol:** opt 19 and GCNS M4c append a synthetic Sol row; `prepare_sky_from_star` must not add its own.
- **Cross-repo:** spec ambiguities go to the sibling repo via the coordination channel `/home/greg/Claude/coordination-channel.md`, not decided unilaterally. The `main.py` CLI is deprecated — fix `core/`, not its inline copies.

### CLI Architecture

`main.py` is the single entry point for the CLI. All features live as functions in this file (for now) and are registered in the `MENU_OPTIONS` dict at the bottom, which drives the main menu loop.

```
MENU_OPTIONS = {
    "1": ("SIMBAD Lookup Query", query_star),
    # add new features here
}
```

The main menu loop calls whichever function the user picks, then returns to the menu after the function ends. Every feature function must call `input("\nPress Enter to Return to the Main Menu")` before returning.

## Adding New Features

1. Write the feature as a top-level function.
2. Register it in `MENU_OPTIONS` with the next available key and a short label.
3. End the function with the "Press Enter to Return to the Main Menu" prompt.
4. Screen clearing rules:
   - If the function has **no user inputs** (pure data display): call `os.system("cls" if os.name == "nt" else "clear")` at the very start of the function, before any output.
   - If the function **collects user inputs first**: call `os.system("cls" if os.name == "nt" else "clear")` after all inputs are collected and before the first output `print()`.
   - The main menu loop clears the screen at the top of each iteration, so functions do **not** need to clear after the "Press Enter" prompt.

## Menu Options

```
  Star Databases                                    Calculators
  --------------                                    -----------
1. SIMBAD Lookup Query                              17. Distance Between 2 Stars
2. NASA Exoplanet Archive: All Tables               18. Stars within a Certain Distance of Sol
3. NASA Exoplanet Archive: Planetary Systems        19. Stars within a Certain Distance of a Star
4. NASA Exoplanet Archive: HWO ExEP Stars           20. Travel Time Between 2 Stars (LYs/HR)
5. NASA Exoplanet Archive: Mission Exocat Stars     21. Travel Time Between 2 Stars (X Times the Speed of Light)
6. Habitable Worlds Catalog                         22. Travel Time Between 2 System Objs (Planet/Moon/Asteroid)
7. Open Exoplanet Catalogue                         23. Travel Time Between 2 System Objs (Custom Thrust Duration)
                                                    24. Distance Traveled at an Acceleration Within a Certain Time
  Star System Regions                               25. Distance Traveled at a certain ly/hr within a certain time
  ------------------                                26. Distance Traveled at a certain X times the speed of light within a certain time
8.  Star System Regions (SIMBAD)                    27. Time to Travel # of Light Years at X LY/HR
9.  Star System Regions (Semi-SIMBAD)               28. Time to Travel # of Light Years at X Times the Speed of Light
10. Star System Regions (Manual)                    29. Travel Time Between 2 System Objs (Generic, Distance in AUs)
                                                    30. Travel Time Between 2 System Objs (Generic, Distance in LMs)
  Science                                           31. Light Years per Hour to X Times the Speed of Light
  -------                                           32. X Times the Speed of Light to Light Years per Hour
11. Solar System Planet/Dwarf Planets/Asteroids
12. Main Sequence Star Properties                   Planetary Equations
13. Sol Solar System Regions                        -------------------
                                                    33. Planetary Orbit Periastron & Apastron Distance Calculator
  Science Fiction                                   34. Orbital Distance of an Earth-sized Moon with a 24 hour day
  ---------------                                   35. Orbital Distance of an Earth-sized Moon with a X hour day
14. Honorverse Hyper Limits by Spectral Class
15. Honorverse Acceleration by Mass Table           Rotating Habitat Equations
16. Honorverse Effective Speed by Hyper Band        --------------------------
                                                    36. Centrifugal Artificial Gravity Acceleration at Point X (m/s^2)
  Utilities                                         37. Distance from Point X to the Center of Rotation (m)
  ---------                                         38. Rotation Rate at Point X (rpm)
50. Star Systems DB Query
51. Export Star Systems to CSV
52. Import HWC Data
53. Import Mission Exocat Data
54. Import Main Sequence Star Props
55. Import Solar System Data
56. Import Honorverse Hyper Limits
57. Database Table Status (GUI only)
58. Import GCNS Data
59. Fetch Dust Map Data (WSL/Linux-only; import utility for the Phase T2 dust path)
Q.  Quit                                            Misc. Equations
                                                    ---------------
                                                    39. Habitable Zone Calculator
                                                    40. Habitable Zone Calculator w/SMA
                                                    41. Star Luminosity
```

> Options 3, 4, and 11 are abbreviated above to fit the two-column layout; their
> full in-app labels (as registered in `MENU_OPTIONS`) are "NASA Exoplanet Archive:
> Planetary Systems Composite" (3), "NASA Exoplanet Archive: HWO ExEP Precursor
> Science Stars" (4), and "Solar System Planet/Dwarf Planets/Asteroids Data Table" (11).



<!-- docs/gui-architecture.md and docs/integration.md are intentionally NOT @-loaded here
     (they are the two largest docs, ~29K + ~46K tokens). They are read on demand — see the
     "Read-on-demand references" note above. This keeps the auto-loaded session context light. -->
