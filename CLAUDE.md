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

# Run the test suite (pytest or the stdlib runner both work)
pytest                      # or: python -m unittest discover -s tests
```

### Tests

Tests live in `tests/`. The bulk are **offline** and need no network or Qt:

- `test_equations.py`, `test_calculators.py`, `test_regions.py` — pure math/physics core (HZ + Kopparapu Seff, brachistochrone profiles, velocity/coordinate conversions, planetary & rotating-habitat equations, the spectral-type ceiling rule).
- `test_worldbuilding.py` — the Phase H worldbuilding calculators (Roche limit, tidal-locking timescale, Hill sphere, binary orbit stability, atmosphere retention) in `core/equations.py`; anchored to reference values and locks the two formula corrections (rigid Roche coeff 1.26, binary P-type `+4.12μ`).
- `test_solvent_zones.py` — the Phase P (Snow Lines & Alternative-Solvent HZs) core + query.py + viz contracts (offline). `compute_solvent_zone` (P4, M1 surface model): the legacy alt-HZ divisor anchors at A=0.3 (water/ammonia/methane), the corrected `(1−A)^0.25` albedo exponent, custom ranges, the CO₂ pressure-conditional flag, the corrected hydrogen band, the validation matrix, and the `solvent-zone` subcommand (subprocess happy-path/parity + the exit-code matrix — curated `{"error"}` exit-1, mutex/missing-arg exit-2). `compute_ice_lines` (P5, M2 equilibrium): the 278.5 K `T_ref`, the canonical 170 K / 2.68 AU water snow line, the CO₂/NH₃/N₂/CO fronts (N₂/CO flagged `disk_line`), no dual/formation line, + the `ice-lines` subcommand. The P1 value re-anchors (hydrogen ÷0.0000247/÷0.0000053, snowLine ÷0.139, `planetaryTemperature` `(1−A)^0.25`), the P2/P3 additive region keys (derivation parity + sound-bands regression guard), and the viz preps `prepare_solvent_ranges` (V5), `prepare_ice_line_diagram` (V4), `prepare_orbit_overlays` (V6/V7, all solvent zones default-off). The V1 10-band alt-HZ / V2 system-regions relabels are exercised via `core.viz`. (The Phase O `test_viz_phase_o.py` additivity guard covers `make_orbits_canvas` with no `snow_au`/`solvent_bands`.)
- `test_db_backups.py` — the opt-50 backup pruner (`core.db.prune_star_systems_backups`).
- `test_search.py` — the Phase G search/filter core: `core.shared.spectral_where` / `spectral_adql` (pure clause builders), the DB-backed `search_star_systems` / `search_hwc` (temp DB, auto-seed disabled, no network — incl. the `ss`-aliased query), and `search_exoplanets` with the NASA TAP fetch mocked. (The Phase L4 `search_star_systems` `fe_h` JOIN is exercised separately in `test_hypatia_cache.py`.)
- `test_gcns.py` — GCNS ingest/query path with the GAVO TAP fetch mocked.
- `test_simbad_gcns_enrichment.py` — the Phase M5 `compute_simbad_lookup` `"gcns"` cross-reference (non-fatal/silent when no Gaia id / not in GCNS / table empty); SIMBAD mocked, seeded temp `gcns_stars`.
- `test_hypatia_elements.py`, `test_parse_composition.py`, `test_prepare_abundance_profile.py`, `test_gui_hypatia.py` — Hypatia element table, composition parsing, and abundance-profile prep.
- `test_route_planning.py` — the Phase I route-planning core (`compute_multi_stop_journey`, `compute_nearest_neighbor_chain`, `compute_trade_route_mst`) + `core.viz.prepare_route_map`; offline via a tmp seeded `star_systems` (the `test_db_backups.py` pattern) with `Sol`-origin resolution and one mocked-SIMBAD-fallback branch; hand-checkable fixture geometry.
- `test_route_planning_opts.py` — the Phase I-OPTS route planners (`compute_optimal_tour` NN+2-opt, `compute_jump_route` Dijkstra/BFS, `compute_jump_network` BFS tiers, `compute_farthest_first_chain`) + their `core.viz.prepare_route_map` branches; same offline seeded-`star_systems` pattern (Sol origin + one mocked-SIMBAD branch), with a `_radec_for_xyz` helper to place stars at arbitrary 3D points (the jumps-vs-distance fixture).
- `test_honorverse_expansion.py` — the Phase K Honorverse calculators (`compute_hyper_translation_time`, `compute_impeller_wedge` in `core/science.py`; `compute_missile_intercept` in `core/calculators.py`) + the K0 refactor parity (opt-15/16 output byte-identical after the band/mass tables were hoisted to module constants; the 24-band expanded table locked by value incl. the Iota=6000 / merchant-drift correction). Pure math, offline (no DB/network).
- `test_query_expanded.py` — the `query.py` expansion subcommand contracts: Search & Filter (`search-star-systems`, `search-hwc`, `search-exoplanets`), reference data (`main-sequence`, `solar-system`, `sol-regions`), and the planetary/rotating-habitat equations (`orbit-distance`, `moon-orbital-distance`, `gravity-acceleration`/`-distance`/`-rpm`, `travel-time-custom-thrust`). Class-level throwaway `SPACE_APP_DB` (auto-seeded reference tables + seeded `star_systems` + imported `hwc.csv`); offline happy-path + argparse exit-2 matrix; the two network entries (`search-exoplanets` NASA TAP, `travel-time-custom-thrust` JPL Horizons) are reachability-gated. Documents that the equation wrappers are **non-self-validating** (Phase-N-style: raw-exception exit-1 or nonsense exit-0).
- `test_query_route_opts.py` — the `query.py` Route Planning subcommand contracts for **all seven** planners (`optimal-tour`, `jump-route`, `jump-network` + the backfilled `multi-stop`, `nearest-neighbor`, `farthest-first`, `trade-route`): offline subprocess happy-path + the exit-code matrix (curated `{"error"}` exit-1 for out-of-range since these wrap self-validating functions; `jump-route` unreachable & `stopped_early` chains are exit-0; argparse exit-2 for bad `--optimize`/non-int `--hops`/missing/both-velocity). Seeds a throwaway `SPACE_APP_DB`.
- `test_query_phase_n.py` — the Phase N `query.py` subcommand contracts (`habitable-zone-sma`, `star-luminosity`, `brachistochrone-au`/`-lm`, `travel-time-solar`): offline subprocess happy-path + parity + the exit-code matrix (raw-exception exit-1 for the non-validating wrappers; `star-luminosity`'s no-error-path; argparse exit-2), plus the mocked `travel-time-solar` dispatch wiring (arg mapping; `progress_callback` never passed). The live Horizons round-trip is gated on JPL reachability (skips offline).
- `test_query_exposure_additions.py` — two `query.py` subcommands added after a coverage audit to close exposure gaps, each a thin verbatim wrapper over a **non-self-validating** legacy core function (so they share the Phase-N contract: happy-path exit 0, raw-exception `{"error"}` exit 1 for an out-of-range numeric, argparse exit 2): `distance-at-acceleration` (`calculators.compute_distance_at_acceleration` — opt 24, accel + time → 3-profile distances; the inverse of `brachistochrone-au/-lm`) and `star-regions-manual` (`regions.compute_star_system_regions` — opt 10, manual vmag/BC/teff/parallax → full region values, no SIMBAD). Offline subprocess happy-path + core-parity + the exit-code matrix (zero-accel / zero-or-negative-parallax raw exceptions; defaults + override of `--sunlight-intensity`/`--bond-albedo`; argparse missing/non-numeric exit 2). Same subprocess harness as `test_query_phase_n.py`. **Also** the six **Group-A velocity/distance/time converters** (opts 25–28/31/32 — `ly-hr-to-times-c`, `times-c-to-ly-hr`, `distance-traveled-ly-hr`/`-times-c`, `travel-time-ly-hr`/`-times-c`; another audit-driven exposure-gap close), each a thin wrapper over a non-self-validating `core.calculators` converter: happy-path + core-parity, the travel-time pair's zero-velocity division-by-zero exit 1, and argparse exit 2 for missing/non-numeric args.
- `test_comparison.py` — the Phase L1–L3 (Comparison Dashboard) core + integration contracts, offline. `compute_stellar_evolution` (L3): the 1 M☉ MS anchor, contiguous/non-overlapping stage boundaries summing to `total_gyr`, `current_stage` selection (in-MS / Beyond AGB), the low-mass (< 0.8, only Pre-MS+MS) and high-mass (> 8, "Supergiant → Supernova") branches, and the self-validating out-of-range errors. `compare_stars` (L1, network mocked — SIMBAD/Hypatia/`_query_tap`): per-star error isolation, the NASA pscomppars supplement + `radius²·(teff/5778)⁴` luminosity + HZ-bound path, the carried-through Hypatia sub-dict, and the **Sol/Sun reference-constant special-case** (SIMBAD-bypassing injected Sun values + the `[X/H]≡0`, `n=0` solar baseline that `prepare_abundance_comparison` fills-but-doesn't-bloat). The `core.viz.prepare_evolution_diagram` / `prepare_abundance_comparison` shapes. The `stellar-evolution` query.py subcommand happy-path + parity + exit-code matrix (curated-error exit-1 since it self-validates; argparse exit-2). L2 (ESI ranking) adds no core fn — it reuses `search_hwc` (covered by `test_query_expanded.py`); its L2 bar-chart prep `core.viz.prepare_esi_bar_chart` (ESI filter/sort/top-N cap, habitable flag, error passthrough) is covered here too. The L1 `compare-stars` query.py subcommand is covered by a subprocess contract (offline happy path via the Sol/Sun reference-constant special-case; arg-count exit-1 for < 2 / > 4; argparse exit-2).
- `test_hypatia_cache.py` — the Phase L4 (Hypatia abundance cache + search) core + integration contracts, offline. `import_hypatia_cache` with the bulk `GET /data` fetch (`_hypatia_data_fetch`) mocked: row assembly (props + denormalized `fe_h` + precomputed `light_years` + disk int-formatting), idempotency / no-orphans, a non-fatal element-axis failure (`errors` count), and the validate-before-destroy **Gate 1** (a short download leaves the cache intact). `search_hypatia_cache`: the filter matrix (`fe_h`/`teff`/`ly_max`/`disk`/`element`-EXISTS), `fe_h DESC` NULL-last ordering, the pivoted `mg_h`/`si_h`/`o_h`, and the empty-table error. The `search_star_systems` **`fe_h` JOIN** (activates only with a populated `hypatia_cache`; matches nothing — not an error — when empty; the non-fe_h path is unaffected by the `ss`-alias rewrite). The `search-hypatia` query.py subcommand (subprocess happy-path + no-filter + argparse exit-2). The L4 scatter-diagram prep `core.viz.prepare_hypatia_scatter` (rows dropped when either axis is non-numeric; bad-axis/empty errors). Same DB-isolation pattern as `test_db_backups.py` (in-process tmp DB) + `SPACE_APP_DB` subprocess.
- `test_viz_phase_o.py` — the Phase O (visualization expansion) test scaffold; offline + offscreen (`QT_QPA_PLATFORM=offscreen`). **Sub-phase O-1 (Shared Foundations)**: **F1** — the additive `app_magnitude`/`parsecs` keys on the opts-18/19 result rows (`compute_stars_within_distance_of_sol`/`_of_star`; tmp `star_systems` DB, SIMBAD-mocked centre, asserts the new keys *and* that pre-existing keys are untouched); **F2** — the reusable help-dialog component (`gui/help.py` `show_help_dialog`/`info_button` + `gui/help_text.py` `TOOMRE_HELP_HTML`) via an offscreen `QApplication` smoke; **F3** — the shared `build_canvas_ok` offscreen helper + the additivity-regression guard that builds every shared canvas (`make_star_chart_canvas`/`_3d`, `make_star_map_canvas`/`_3d`, `make_orbits_canvas`) with no new kwargs (guards opts 18/19 / GCNS / Phase-I callers against future signature breaks). **Sub-phase O-2 (Star-Map Data Products)**: `core.viz.prepare_sky_from_star` (O1 — vantage RA/Dec + distance-modulus magnitude, `skipped_no_mag`, mag-limit filter, Sol appended), `prepare_hr_main_sequence` (O2a — tmp DB w/ seeded `main_sequence_stars`, hot→cool sort, empty-table error) and `prepare_hr_from_stars` (O2b — `M_V` + ceiling-rule Teff, skip counts; resets `core.regions._MAIN_SEQUENCE_DATA`); `make_hr_canvas`/`make_sky_canvas` offscreen smokes; and a panel-wiring smoke that constructs `MainSequencePanel`/`StarsWithinDistance{Sol,Star}Panel` and exercises the `_add_hr_tab`/`_add_night_sky_tab` builders. Later O-sub-phases append their `prepare_*` unit tests here. See `PHASE_O_PLAN.md`.

- `test_report.py`, `test_reports_panel.py` — the Phase Q **System Dossier** (`core/report.py` + `DossierExportPanel`), offline (mocked readers; the Sol path runs offline against an auto-seeded throwaway `SPACE_APP_DB`). `test_report.py` covers `build_system_dossier`: the normal-star path (identity / regions + full Phase P solvent+ice surface / Kopparapu HZ / planets — **both** NASA pscomppars [priority 1] + HWC [priority 2] sub-tables / Hypatia all-species grouped by family / the M5 GCNS block), the **markdown / html / json** renderers (json = structured `data` only; html self-contained text+tables, **no `<img>`**), the three-tier validation (hard `{"error"}` for SIMBAD-fail / bad fmt / bad section; `warnings[]` for a per-source failure or a requested-but-unavailable section; `notes[]` for by-design omissions), determinism, the **Sol/Sun reference-origin path** (offline — no SIMBAD; `compute_sol_regions` + real `compute_solar_system_tables` planets/dwarfs/asteroids + the `_sun_hypatia_baseline` zero-point + GCNS-N/A note; `moons` opt-in), and the `query.py dossier` subprocess contract (happy-path / json-shape / section subset / argparse exit-2 / unknown-section exit-1). `test_reports_panel.py` is the headless GUI smoke (offscreen): panel construction, default/`moons` section selection, the markdown/html render path (option-A inline base64 figures spliced into HTML when matplotlib is present), error/warning status surfacing, and the nav/export registration.
- `test_generate.py`, `test_query_generate.py`, `test_generator_panel.py` — the Phase R1 **procedural system generator** (`core/generate.py` + `core/priors.py` + `SystemGeneratorPanel`), offline. `test_generate.py` (the core suite): `DefaultPriors` (the R3 seam) + the two new astronomy helpers `_classify_planet` (G3 — mass-class boundaries + snow-line modifier + per-type radius) and `_equilibrium_temp` (G4 — the Phase P `implied_edge_temp` equilibrium wrapper); the **synthetic mode** of `generate_system` (the headline **determinism** contract — same seed → deep-equal output; star Teff/M/R/L consistent with the main-sequence interpolation + `compute_star_luminosity`; HZ flags from `compute_habitable_zone`; `n_planets` honoured; classifier boundaries; moons strictly between `compute_roche_limit` and `compute_hill_sphere`; `t_eq_k` falls with `a_au`; `require_habitable` delivers a conservative-HZ rocky world or errors after bounded retries; bad inputs → `{"error"}`); and the **real-anchor mode** with `compute_simbad_lookup` / `compute_star_system_regions_from_simbad` / `compute_planetary_systems_composite` / `compute_hwc` **mocked** (observed planets flagged `source:"observed"`, synthetic extensions `source:"synthetic"`, synthetic SMAs never colliding with observed, multiplicity via a mocked GCNS `n_components=2` → warning + safe-cap, a white-dwarf-regions anchor → error). `test_query_generate.py` is the offline `query.py generate-system` subprocess contract (synthetic happy-path JSON + anchor values, cross-process seed determinism, the curated-error exit-1 matrix — self-validating, unlike the Phase-N raw-exception wrappers — and argparse exit-2 for missing/non-integer args; harness mirrors `test_query_phase_n.py` with a throwaway `SPACE_APP_DB`). `test_generator_panel.py` is the headless GUI smoke (offscreen): construction/mode-enable (anchor field vs spectral chips), single-select chips + class building, a synthetic generate building the Planet Table + Orbit Diagram / HZ Ring viz tabs, the Auto (sampled) planet count, bad-seed + error-result paths, and nav/export registration. (Phase R2 extends `test_query_generate.py` with the `--constraint` DSL / feasibility contract and `test_generator_panel.py` with the constraint-builder + four-layer cards — see the next bullet.)
- `test_feasibility.py`, `test_nbody.py` — the Phase R2 **constraint / feasibility engine** (`core/feasibility.py` + `core/nbody.py`), offline. `test_feasibility.py`: the new-physics helpers **G1** (`mutual_hill` — the Gladman 2√3 Hill floor + Chambers Δ≥10 long-term threshold; anchored to Solar-System pairs incl. Jupiter–Saturn in the gray band) and **G2** (`period_ratio`/`nearest_mmr`/`in_mmr` + the Gascheau/Routh `gascheau_coorbital_stable` co-orbital criterion; Jupiter-Trojan, Neptune/Pluto 3:2, 2:1); the **rule registry + `evaluate_feasibility`** for the core-4 vocab (`planet_at_location`/`trojan`/`moon`/`resonance`) + the stretch vocab (`habitable_world`/`alt_solvent_world`/`architecture`) — verdict + the four layers, the Δ-band boundaries, `_resolve_ref`/`_resolve_location`, the **determinism** contract, unknown-type/unresolvable-ref → `not_evaluated`, base-error passthrough, and **0-constraint parity** (`generate_system` with no constraints = the R1 path, byte-identical); **Layer-3** tagged origin (`grounding=default-extrapolation`); **Layer-4** deterministic alternatives whose `spec_patch` re-runs to feasible; **R2-C4** `_nbody_confirm` upgrading/downgrading a marginal packing verdict under `nbody=True`; **R2-C5** the multi-star S/P-type gate (`_binary_gate`/`_apply_binary_gate` over `compute_binary_orbit_stability` + a spec `companion` hint, the no-hint real-anchor-multiple note via mocked `core.generate.*` readers). `test_nbody.py`: the pure-numpy leapfrog `integrate_coplanar` — determinism (no RNG), a widely-separated system surviving the bounded run, packed giants flagged unstable (close encounter), and the trivial/bad-input short-circuits. Phase R2 also extends `test_query_generate.py` (the `generate-system --constraint` DSL parse + feasibility envelope contract, companion gate, unknown→not_evaluated, malformed-constraint/companion/bad-ecc exit-1, 0-constraint parity) and `test_generator_panel.py` (the constraint-builder rows + `to_spec`, feasibility cards, clickable-apply alternatives, the depth cap, N-body checkbox).
- The `*_live.py` files (`test_gcns_live.py`, `test_hypatia_live.py`) hit the **live network** and are gated by `tests/_netcheck.py` via `@unittest.skipUnless(...)` (skipped automatically when GAVO/Hypatia is unreachable). Tests that touch the SQLite store never mutate `data/space_app.db`: in-process tests monkeypatch `core.db._DB_PATH` to a tmp file with auto-seeding disabled (pattern in `tests/test_gcns.py`, `tests/test_regions.py`, `tests/test_db_backups.py`), and the `query.py` subprocess tests pass a throwaway DB via the `SPACE_APP_DB` environment variable.

## Architecture

The project has three entry points that share all computation through the `core/` package:

- **`main.py`** — CLI. All features are top-level functions registered in `MENU_OPTIONS`.
- **`gui_main.py`** — PySide6 GUI. Navigation tree on the left, panel stack on the right.
- **`query.py`** — JSON dispatcher. Calls `core/` functions and writes JSON to stdout; used by the `scifiWorldBuilding-Claude` repo (current consumer; formerly `ScienceFictionResearch-Claude`) via its Bash tool / `bin/sfq` wrapper.
- **`core/`** — Pure computation layer (no I/O, no Qt). Called by all three entry points. (Includes `core/report.py` — the Phase Q system-dossier composer; `core/generate.py` + `core/priors.py` — the Phase R1 deterministic system generator + its `DefaultPriors` provider; and `core/feasibility.py` + `core/nbody.py` — the Phase R2 constraint/feasibility engine + its opt-in pure-numpy N-body confirmer.)
- **`gui/`** — Qt presentation layer: `app.py` (MainWindow), `nav.py` (navigation tree), `panels/` (one class per feature).

See `@docs/gui-architecture.md` for the full GUI structure, panel class → option mapping, and phase completion status.
See `@docs/integration.md` for `query.py` subcommands, arguments, and JSON output format.

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
Q.  Quit                                            Misc. Equations
                                                    ---------------
                                                    39. Habitable Zone Calculator
                                                    40. Habitable Zone Calculator w/SMA
                                                    41. Star Luminosity
```

> Option 4 is abbreviated above to fit the two-column layout; its full in-app
> label (as registered in `MENU_OPTIONS`) is "NASA Exoplanet Archive: HWO ExEP
> Precursor Science Stars".

@docs/star-databases.md
@docs/star-system-regions.md
@docs/science-and-scifi.md
@docs/calculators.md
@docs/equations.md
@docs/gui-architecture.md
@docs/integration.md
