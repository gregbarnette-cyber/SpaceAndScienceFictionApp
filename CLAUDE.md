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
`pip install dustmaps` fails on a native-Windows checkout. Build, run, and test the Phase T **dust**
subcommands (`dust-sightline` / `dust-between`; CLI option-59 dust-fetch; and the dust-weighted routing
`--weight dust` on `jump-route`/`optimal-tour`/`multi-stop`/`nearest-neighbor`/`trade-route`, in
`core/dust_routing.py`) from the **WSL/Linux venv** — which is also the path the sister consumer repo invokes. The optional
extra is **`requirements-dust.txt`** (`dustmaps, healpy, h5py, scipy, progressbar2, six, tqdm`) — installed on
top of base `requirements.txt`, **never** in it; there is no `setup.py`/`pyproject.toml`, so the
`extras_require['dust']` form is aspirational. `core/dust.py` is the **only** module that imports
`dustmaps`/`healpy`, lazily, so the stellar layer stays importable on a Windows checkout; dust tests gate on
`dustmaps` importability (`tests/_dustcheck.py`, like the `*_live.py` network gate) so a Windows checkout skips
them cleanly. **Maps:** Leike 2020 (`leike2020`) + **Edenhofer 2024 — the dustmaps key/module is
`edenhofer2023`** (paper 2024, arXiv/dustmaps 2023). Output is standardized to **A_V (mag, R_V=3.1)** via pinned
per-map scalars (Edenhofer `A_V=2.8·E`; Leike `A_V=1.0857·1.202·τ_G`), with a `native_value`/`native_quantity`
echo. The cache lives in `data/dust/` (gitignored, native WSL FS). This scopes to the dust path only — the rest
of the app (including all of Phase T's pure-math calculators) remains fully cross-OS. See `completed_plans/PHASE_T_PLAN.md`
(Part A + Part B built 2026-06-23 — Phase T complete) and `docs/integration.md` (Dust / ISM section).
Dust-weighted routing reuses a `_grid_search` seam extracted from `compute_jump_route` (byte-identical for
`--weight distance`, guarded by the route tests); `--weight dust` minimizes integrated A_V over the same
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

Tests live in `tests/`. The bulk are **offline** and need no network or Qt. Tests that touch the SQLite store never mutate `data/space_app.db`: in-process tests monkeypatch `core.db._DB_PATH` to a tmp file with auto-seeding disabled (pattern in `tests/test_gcns.py`, `tests/test_regions.py`, `tests/test_db_backups.py`), and the `query.py` subprocess tests pass a throwaway DB via the `SPACE_APP_DB` environment variable (via the shared `tests/_queryharness.py` harness). The `*_live.py` files (`test_gcns_live.py`, `test_hypatia_live.py`) hit the **live network**, gated by `tests/_netcheck.py` via `@unittest.skipUnless(...)` (skipped when GAVO/Hypatia is unreachable).

**`pytest` is the runner.** The tests are *written* as `unittest.TestCase` classes — pytest collects them natively, so that is a style choice, not a second runner to maintain (`pytest.ini` sets `testpaths = tests`). Current state: **2120 passed, 1 skipped, 0 failures** (2026-07-27). Always invoke through the venv (`venv/bin/python -m pytest`); a bare `pytest` may resolve to a system install on system Python without this project's deps. *(The stdlib `unittest discover` still happens to work, since nothing uses pytest-only features — but it is not verified against and no doc should promise parity; don't spend a run on it.)*

**Per-test-file descriptions live in `docs/testing.md`** (read-on-demand — read it before adding or modifying tests).

## Architecture

The project has three entry points that share all computation through the `core/` package:

- **`main.py`** — CLI. All features are top-level functions registered in `MENU_OPTIONS`.
- **`gui_main.py`** — PySide6 GUI. Navigation tree on the left, panel stack on the right.
- **`query.py`** — JSON dispatcher. Calls `core/` functions and writes JSON to stdout; used by the `scifiWorldBuilding-Claude` repo (current consumer; formerly `ScienceFictionResearch-Claude`) via its Bash tool / `bin/sfq` wrapper.
- **`core/`** — Pure computation layer (no I/O, no Qt), called by all three entry points. **Foundation:** `equations.py` (physics constants + HZ/Kopparapu Seff, solvent/ice lines, worldbuilding + stellar-evolution calculators, the shared `_resolve_velocity`/`_resolve_insolation` gates + `_kopparapu_seff`), `calculators.py` (distance/travel-time/brachistochrone/route-planning + JPL Horizons), `regions.py` (star-system regions), `science.py` (Honorverse + main-sequence/solar-system tables), `shared.py` (network retry/timeout helpers, designation/spectral parsing, search-filter SQL, `_to_cartesian`/`_fval`/`_fmt`), `databases.py` (SIMBAD/NASA/HWC/Mission-Exocat/GCNS/Hypatia/OEC readers + importers; OEC = the recursive Open Exoplanet Catalogue tree, opt 7 — see `completed_plans/PHASE_OEC_PLAN.md`), `db.py` (SQLite schema/connection), `viz.py` (matplotlib data-prep). **GUI+query feature modules:** `report.py` (Phase Q system dossier), `generate.py`+`priors.py`+`feasibility.py`+`nbody.py`+`research_priors.py` (Phase R1–R3 procedural generator + constraint/feasibility engine + research-priors hook; **research-priors v2** (`completed_plans/PHASE_R3_V2_PLAN.md`, `docs/research-priors-contract.md`) adds an additive-superset contract — **eight** optional blocks `mass_model`/`occurrence_by_metallicity`/`intra_system_correlation`/`feh_dist`/`cold_giant_population` (+ nested `disk_mass_dist`)/`inner_giant_population`/`stellar_multiplicity`/`stellar_activity` that `generate.py` consumes under `research_policy="strict"` to draw planet mass from isolation-mass physics, condition giant occurrence + planet count on host [Fe/H] (synthetic via `feh_dist`, real-anchor via Hypatia→SIMBAD `fe_h`), correlate adjacent planets peas-in-a-pod, place a decoupled cold-giant population, and place a decoupled **inner**-giant population interior to the snow line with in-situ-vs-migrated `formation_channel` tags (its own FV05 occurrence roll over a disjoint zone — it bypasses the B1 `giant_switch` for that tagged sub-population without changing the gate). The two **stellar** blocks (`stellar_multiplicity`/`stellar_activity` — the first non-planetary axes) both validate and are exposed; **`stellar_multiplicity` is now SAMPLED in synthetic mode** (B1 — `_draw_multiplicity`: mass-dependent multiplicity roll → mass ratio → the close-pair/wide-log-normal separation mixture → eccentricity, emitted in the block's `consumer_contract` shape `{mass_solar, sma_au, ecc, p_orb_days, close_pair}`, which *is* the `--companion` hint shape, so a drawn companion feeds `feasibility._binary_gate` with no parallel code path; an explicit `--companion` overrides it, and real-anchor GCNS multiplicity is never overwritten). It was unblocked by dataset **v2.9.0**, which replaced the borrowed solar-type 12 d circularization boundary with a source-backed M-dwarf **~6 d** (Packet-4 C52). **`stellar_activity` is now sampled too** (B2), unblocked by the **ninth** block **`age_dist`** (v2.10, T8 — the synthetic-mode host age, `feh_dist`'s mirror but an SFH *histogram*, MS-lifetime-truncated via `compute_stellar_evolution`; its validator enforces contiguous bins + requires an `sfh_smoothing_note` whenever an interior zero bin is present, so the BGM discrete-age-bin artifact cannot arrive undocumented). **B3** truncates the wide companion at the moving survival **half-life** scale `a_half ≈ 1.212 × (M_tot/t)` pc (Weinberg 1987 eq. 28 — where ~half the population is disrupted, **not** a boundary; the source reports no breaks or cutoffs, so the cut is a labelled modelling convenience, `null` without an age axis) and deliberately adds **no power-law tail**: the measured index is −1.6 in dN/ds, but the log-normal↔tail join normalization is declared *unknown* by the source lineage, so a mixture would need an invented weight. The coefficient is primary-verified (an earlier ~4% slack was retracted on opening the source). It emits a solar-host shape caveat (shallower than the measured −0.60 slope out to ~3000 AU → over-produces there; M hosts err safe). The activity chain is age → P_rot → Ro = P_rot/τ(M) → log(L_X/L_bol) → [contested X-ray→EUV] → XUV, with three P_rot branches (tidally-locked close pair = the only one needing no age · Skumanich FGK · the bimodal M-dwarf fast/slow, never interpolated across the gap); out-of-domain values are flagged, never clamped, and the dataset's own `unit_test_sun` is a regression test. Their validators hard-enforce three structural guards (no silent `e = 0`; circumbinary XUV must not scale with component count; the locked-vs-single delta stays an acceptance target, not an input). Round record: `docs/research-priors-v2-close-binary-actions.md`; `feasibility.py` gains metallicity-qualified `<key>:metal_rich`/`:metal_poor` origin-narrative keys — omitting every v2 block is byte-identical to v1), `projects.py` (Phase S workspaces), `hypatia_elements.py`, `dust.py`+`dust_routing.py` (Phase T2 dust/ISM extinction + dust-weighted routing). **`query.py`-only calculator packs** (Phases U–AD, for the sibling scifiWorldBuilding repo; several ship an `*_tables.py` of bundled static data — `cooling_tables`/`shielding_tables`/`spin_tables`/`life_support_tables`/`propulsion_tables`/`materials_tables`/`par_flux_tables`/`ism_drag_tables`): `cooling.py` (U + AD-A0 WD/BD HZ-residence + ²²Ne pause), `thermal.py` (V power/thermal/shielding), `spin.py` (W rotating-habitat comfort), `life_support.py` (X closed-loop life support), `propulsion.py` (Y STL rocket/beam-sail + AD pellet-stream), `megastructure.py` (Z spin-stress/tether/dyson + AD orbital-ring), `par_flux.py` (AA PAR-by-stellar-type), `terraforming.py` (AB energy-balance), `ism_drag.py` (AC magsail/ramscoop), `active_shield.py` (AD Störmer cutoff), `dust_impact.py`+`volatile_delivery.py` (AD impact energetics + cometary delivery). **Phase AE–AI exotic-physics / relativity / FTL / black-hole track** (Pkts 20–24 for the sibling repo; closed-form on fundamental constants, no bundled datasets; a shared `astro_bodies.py` mass/radius/body-preset helper + CODATA constants added to `equations.py`): `gravitation.py` (AE — escape-velocity/gravitational-potential/sphere-of-influence/hyperbolic-approach), `relativity.py` (AF — the special-relativity toolkit + `causality-check`), `exotic_physics.py` (AG — casimir/vacuum-energy/schwinger-limit/hubble-flow), `warp.py` (AH — alcubierre-energy [numeric `original` + reported reduction ladder] / warp-metric), `black_hole.py` (AI — 10 horizon/Hawking-thermo/accretion subcommands). **Phase AJ (Group P) planet-formation track** (Packet 3.5 for the sibling repo; closed-form on the F1–F6 claim-map pins, numpy-free, `_MU_GAS_DEFAULT`/`_Z_SUN` added to `equations.py`): `formation.py` (AJ — `disk-model` MMSN Σ/T/(H-r) profile [defaults reproduce Approved-Canon MMSN; own-T-law snow line, no `ice-lines` import] / `isolation-mass` / `pebble-isolation-mass` / `gap-opening-mass` [Crida root-find] / `toomre-q` / `critical-core-mass`; the disk+mass spine the generator's `mass_by_zone`/`spacing_ratio`/`origin_priors` derive from). **Phase AK (Group Q) metric-drive / FTL-boundary track** (Pkts 25 / 26.5 for the sibling repo; closed-form, self-validating, no datasets): `metric_drive.py` (Q1 — `metric-drive-power`: field-rocket `P_rad=k·F·c` radiated power + fuel/mass bill [`f_rad=1−e^(−kΔη)`, per-fuel `f_conv=f×η_dir`; pp/dd f-values reused from `ism_drag_tables._FUSION`], the B2 discount `--k`, the beam-vs-onboard crossover; **STL-mode law only**) + `exclusion_boundary.py` (Q2 — `exclusion-boundary`: FTL "Alcubierre Limit" `r_ex = DIAL·(M/M☉)^α·(L/L☉)^β·(Ẇ/Ẇ_☉)^γ`, Kuiper-edge auto-calibrated, graded-forcing classification; a Rung-3 in-universe dial, not physics). **Phase AL (Group R) power generation / storage / thermal track** (Packet 27 for the sibling repo; pure-math floor physics, self-validating, no datasets; "Group R" → repo Phase **AL** since Phase R is the procedural generator; `_MEV_J`/`_MP_C2_MEV` added to `equations.py`): `power.py` (R1 `annihilation-power-train` directed/γ/ν partition · R2 `antimatter-production` 2m_p/6m_p=0.333 floor + Brillouin ε₀B²/2 storage, `--production-efficiency` un-defaulted H-25-1 input · R4 `reactor-net-power` Q-gate net-energy · R7 `beamed-power-delivery` diffraction λL/D wall · R10 `fusion-lawson` triple-product→Q, general-power scope guard), `energy_storage.py` (R8 `flywheel-storage` K·σ/ρ · R9 `smes-storage` B²/2µ₀ + structure-limited σ/ρ), `thermal.py`'s R3 `heat-pump` (Carnot COP, the inverse of `waste-heat`), and `power_tables.py` (T1 `energy-storage` `_STORAGE` + sensible/latent compute · T2 `reactor-power` `_REACTOR_SPECIFIC_POWER` α=P/m + mandatory thermal pointer). R5 adds fission `f` rows (`_FISSION`) to `ism_drag_tables.py`; R6 extends `metric_drive.py`'s `metric-drive-power` with `--self-consistent` (`--ash {keep,vent}` feasibility wall; fulfils `metric-drive-power-followups.md`). **Phase AM (catalog-access tier) — the first `query.py`-only family that makes LIVE catalog queries** (CDS VizieR + ESA Gaia TAP + HEASARC via the already-present `astroquery`; same network class as the dust/GCNS paths, no new dep, no GUI): `catalog_cache.py` (generic hash+TTL JSON file cache under gitignored `data/catalog_cache/`; never caches errors/empties; `SPACE_APP_CATALOG_CACHE=0` disables), `catalog.py` (the Tier-1 generic gateways `vizier-query`/`gaia-tap`/`heasarc-query` + the CDS `xmatch` helper + Tier-3 `gaia-astrophysical` GSP-Phot/FLAME per-source pull), and `binary.py` (the load-bearing §3.3 **companion-mass classifier** — Thiele-Innes→a₀→mass-function→cubic, SB1 sin i=1 lower bound, star/BD/planet thresholds 0.075/0.013 M☉, verification tags — plus the Tier-2 orchestrators `binary-orbit` [the encoded Gaia-NSS→SB9→WDS/orb6 tool-split with the planet filter baked in so GJ 876's 61 d NSS "orbit" classifies as `planet`, + the independent Gaia `binary_masses` mass cross-check via `catalog.gaia_binary_masses`] and `close-binary-census` [the population sweep: async NSS + SB9 with Hipparcos/Gaia parallax → X-Match dedup → classify → drop-planets → honest coverage block with `requested_not_implemented` for un-wired `--include` sources]). Plus `besancon.py` (Tier-3 `besancon-query` — the Besançon Galaxy Model **m1612** field-population route that builds the sibling repo's T8 `age_dist` prior; drives the **modern UWS 1.0 REST service** at `model.obs-besancon.fr/ws/` directly — NOT the dead `astroquery.besancon` 2003 email/FTP path — with account auth from `BESANCON_USER`/`BESANCON_PASS` and a full safeguard set: 30-day result cache, 30 s poll cadence, one job at a time, always-DELETE cleanup, `sendmail=0`, `--area` cap, server-side `EXECUTIONDURATION`, identifying User-Agent; output is model-derived → carries a `verify_against_observation` flag). Reuses `compute_simbad_lookup` for identity and `_with_retries`/`_timeout_ctx`/`_network_error_msg`/`_route_error` from `shared.py`; the classifiers + cache + Besançon parsing/age-dist math are offline-tested (`tests/test_binary.py`/`test_catalog_cache.py`/`test_besancon.py`), the live anchors gated in `tests/test_catalog_live.py`. Implements `catalog-access-and-binary-census-request.md` in full (all seven subcommands); see `completed_plans/PHASE_AM_PLAN.md`. Full per-phase provenance/citations live in the `docs/gui-architecture.md` roadmap table and the `PHASE_*_PLAN.md` files.
- **`gui/`** — Qt presentation layer: `app.py` (MainWindow), `nav.py` (navigation tree), `panels/` (one class per feature).

**Read-on-demand references (deliberately NOT auto-loaded — large; read them before the relevant work so the session context stays light):**
- `docs/integration.md` — the `query.py` subcommand contract (arguments + JSON output keys + exit-code behavior). **Read it before adding, modifying, or verifying any `query.py` subcommand** (it is the contract the `scifiWorldBuilding-Claude` consumer reads).
- `docs/gui-architecture.md` — the full GUI structure, panel class → option mapping, and phase completion status. **Read it before touching `gui/` panels or the phase-status table.**
- `docs/testing.md` — the per-test-file catalog (what each `tests/test_*.py` covers). **Read it before adding or modifying tests.**
- `completed_plans/` — implementation plans + mockups for **shipped** work (44 files, indexed in `completed_plans/README.md`). Moved out of the repo root 2026-07-27. Plans for work that is *not* finished stay at the root: `future_phases.md` (roadmap) and `IMPROVEMENT_PLAN.md` (P4.6 still PARTIALLY DONE). This folder also absorbed the former `archive/` directory (pre-`PHASE_*`-era plans).
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
  `query.py` subcommands (noted in `docs/integration.md`). The plan is COMPLETE and ready to move to
  `completed_plans/`.

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

@docs/star-databases.md
@docs/star-system-regions.md
@docs/science-and-scifi.md
@docs/calculators.md
@docs/equations.md

<!-- docs/gui-architecture.md and docs/integration.md are intentionally NOT @-loaded here
     (they are the two largest docs, ~29K + ~46K tokens). They are read on demand — see the
     "Read-on-demand references" note above. This keeps the auto-loaded session context light. -->

