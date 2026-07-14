# GUI Architecture Documentation

The GUI is a PySide6 desktop application that runs alongside the existing CLI (`main.py`). It shares all computation logic through the `core/` package — no display or input code lives in `core/`.

## Running the GUI

```bash
python gui_main.py
```

The app launches maximized (`window.showMaximized()`). It uses the Fusion Qt style with the default light palette — no dark palette is applied. Matplotlib figures also use a light background (`#f5f5f5`).

## Repo Structure

```
main.py              # CLI entry point (unchanged)
gui_main.py          # GUI entry point (Fusion style, launches maximized)
query.py             # JSON dispatcher — calls core/ functions, writes JSON to stdout (see docs/integration.md)

core/                # Pure computation layer — no I/O, no Qt
  __init__.py
  calculators.py     # Speed, distance, travel time functions; fetch_body_properties()
  databases.py       # SIMBAD and archive query functions
  equations.py       # Planetary, habitat, HZ, luminosity equations
  regions.py         # Star system region calculations
  science.py         # Solar system data, main sequence, Honorverse tables
  shared.py          # Shared helpers: _format_travel_time, _fval/_fmt, _kopparapu_seff,
                     #   spectral/designation parsing; network reliability helpers
                     #   (_with_retries, _timeout_ctx, _make_simbad, _network_error_msg)
                     #   imported by databases.py and calculators.py
  viz.py             # Visualization data-prep (Phase E): star map, orbits, HZ, regions
  report.py          # System dossier composer (Phase Q): build_system_dossier()
  generate.py        # Procedural system generator (Phase R1): generate_system() — synthetic + real-anchor
  priors.py          # Priors providers: DefaultPriors (R1) + ResearchPriors + get_priors() selector (R3)
  feasibility.py     # Constraint/feasibility engine (Phase R2): evaluate_feasibility() + G1/G2 physics + rule registry
  nbody.py           # Opt-in pure-numpy N-body confirmer (Phase R2-C4): integrate_coplanar()
  research_priors.py # Research-priors data contract (Phase R3): validate_priors_contract + the
                     #   importer compute_research_priors_ingest() + get_research_priors_status()
  projects.py        # Project workspaces (Phase S): CRUD over projects / project_members
                     #   (create/list/get/add_member/update_note/remove/rename/delete) +
                     #   generate.generate_from_spec(); report.build_generated_dossier (R→Q link)
                     #   + report.build_project_dossier (export fan-out) live in report.py
  cooling.py         # Cooling-primary (WD/BD) HZ-residence calculator (Phase U): compute_cooling_hz()
                     #   — snapshot / residence / CHZ modes; reuses compute_habitable_zone + compute_roche_limit
                     #   (Phase AD A0: WD-only --cooling-delay-gyr/--distillation-teff-k 22Ne pause via _warp_age)
  cooling_tables.py  # Phase U bundled static cooling tracks (Bedard 2020 WD + ATMO 2020 BD), closure-verified
  thermal.py         # Power/thermal/shielding calculators (Phase V): compute_waste_heat (F1) +
                     #   compute_radiator_area (F2, Stefan-Boltzmann) + compute_shielding_attenuation
                     #   (F3, Lambert-Beer photon / order-of-mag GCR); query.py-only, no GUI
  shielding_tables.py # Phase V bundled photon mu/rho grid (NIST XCOM) + GCR Lambda values, isolated
                     #   (Phase AD C6: + NIST PSTAR proton/water CSDA-range grid, lookup_csda_range)
  active_shield.py   # Active magnetic-shield rigidity cutoff (Phase AD C8): compute_active_shield()
                     #   — Stormer equatorial cutoff R_c=(mu0 c/16pi) m/r^2 + deflected fraction; query.py-only
  spin.py            # Rotating-habitat comfort calculator (Phase W): compute_spin_comfort()
                     #   — SpinCalc analog; exactly-two-anchor solver -> rim velocity / gravity gradient /
                     #   Coriolis ratio + tiered comfort verdict; query.py-only, no GUI
  spin_tables.py     # Phase W bundled comfort-criteria bands (Hall comfort-chart literature), isolated
  life_support.py    # Closed-loop life-support & bioregen calculators (Phase X): compute_life_support (X1)
                     #   + compute_bioregen_area (X2, PAR energy balance) + compute_population_capacity (X3);
                     #   query.py-only, no GUI
  life_support_tables.py # Phase X bundled BVAD Rev2 rates + closure scenarios + crop/lighting data
                     #   (+ MELiSSA/PBR algae), isolated
  db.py              # SQLite connection (Phase F); get_table_status() returns row counts for all app tables
                     #   (the opt-57 panel also appends core.dust.get_dust_map_status() — the cached map FILES)

gui/                 # Qt presentation layer
  app.py             # MainWindow: QSplitter with nav tree + QStackedWidget
  nav.py             # NAVIGATION list + populate_nav(); maps labels → panel class names
  help.py            # Phase O F2: show_help_dialog() + info_button() — reusable
                     #   "ℹ What is this?" help dialog (non-modal QTextBrowser dialog)
  help_text.py       # Phase O F2: rich-text help constants (e.g. TOOMRE_HELP_HTML for O11)
  panels/
    __init__.py      # Exports all panel classes by name; lazy __getattr__ for viz panels
    base.py          # ResultPanel base class; Worker + run_in_background (Phase C+);
                     #   DiagramToggleMixin (Phase E+)
    # Phase B panels (no network calls):
    science_tables.py     # SolarSystemPanel (11), MainSequencePanel (12)
    sol_regions.py        # SolRegionsPanel (13)
    honorverse.py         # HonorverseHyperPanel (14), HonorverseAccelPanel (15),
                          #   HonorverseSpeedPanel (16)
    velocity.py           # VelocityLyHrPanel (31), VelocityTimesCPanel (32)
    distance.py           # DistanceLyHrPanel (25), DistanceTimesCPanel (26)
    travel_time.py        # TravelTimeLyHrPanel (27), TravelTimeTimesCPanel (28)
    orbit_calc.py         # OrbitPeriastronPanel (33), MoonDistance24Panel (34),
                          #   MoonDistanceXPanel (35)
    rotating_habitat.py   # GravityAccelPanel (36), GravityDistancePanel (37),
                          #   GravityRpmPanel (38)
    habitable_zone_calc.py # HabZonePanel (39), HabZoneSmaPanel (40)
    luminosity.py         # LuminosityPanel (41)
    worldbuilding.py      # Phase H (GUI-only): RocheLimitPanel, TidalLockingPanel,
                          #   HillSpherePanel, BinaryOrbitPanel, AtmosphereRetentionPanel
    # Phase C panels (SIMBAD / network):
    simbad.py            # SimbadPanel (1) — tabs: Star Properties, Hypatia, Abundance Profile
    hypatia_tab.py       # Shared: build_hypatia_tab(), fit_table_height(); element metadata from core.hypatia_elements
                         #   used by simbad.py, star_regions.py, nasa_exoplanet.py, catalogs.py
    star_regions.py      # StarRegionsAutoPanel (8), StarRegionsSemiManualPanel (9),
                         #   StarRegionsManualPanel (10)
    distance_stars.py    # DistanceBetweenStarsPanel (17), StarsWithinDistanceSolPanel (18),
                         #   StarsWithinDistanceStarPanel (19)
    # Phase D panels (multi-source / JPL Horizons):
    nasa_exoplanet.py    # NasaPlanetarySystemsPanel (3), NasaHwoExepPanel (4),
                         #   NasaMissionExocatPanel (5)
    catalogs.py          # HwcPanel (6)
    travel_time_stars.py # TravelTimeStarsLyHrPanel (20), TravelTimeStarsTimesCPanel (21)
    brachistochrone.py   # BrachistochroneAccelPanel (24), BrachistochroneAuPanel (29),
                         #   BrachistochroneLmPanel (30)
    system_travel.py     # SystemTravelSolarPanel (22), SystemTravelThrustPanel (23)
    csv_utility.py       # CsvUtilityPanel (50), ExportStarSystemsPanel (51),
                         #   ImportHwcPanel (52), ImportMissionExocatPanel (53),
                         #   ImportMainSequencePanel (54), ImportSolarSystemPanel (55),
                         #   ImportHonorversePanel (56), DbStatusPanel (57),
                         #   ImportGcnsPanel (58), ImportHypatiaPanel (Phase L4),
                         #   FetchDustMapPanel (59, Phase T2 — optional dust extra),
                         #   ImportResearchPriorsPanel (Phase R3 — research-priors contract)
    search_common.py     # Phase G: SpectralClassControl, SearchPanelBase (inline drill-down tabs)
    search.py            # Phase G: StarSystemsSearchPanel (G1), HwcSearchPanel (G2),
                         #   NasaExoplanetSearchPanel (G3); Phase L4: HypatiaSearchPanel
    gcns.py              # Phase M: GcnsCensusBrowserPanel (M1), GcnsSourceLookupPanel (M2),
                         #   GcnsSystemViewerPanel (M3), GcnsDistancePanel (M4a),
                         #   GcnsTravelTimePanel (M4b), GcnsStarsWithinStarPanel (M4c)
    route_planning.py    # Phase I: MultiStopJourneyPanel (I1), NearestNeighborPanel (I2),
                         #   TradeRoutePlannerPanel (I3, stretch); route-overlay Star Chart tabs
    reports.py           # Phase Q: DossierExportPanel (System Dossier Export)
    generator.py         # Phase R1: SystemGeneratorPanel (System Generator)
    comparison.py        # Phase L: StarComparisonPanel (L1), EsiRankingPanel (L2),
                         #   StellarEvolutionPanel (L3)
  visualizations/        # Phase E: shared rendering helpers + standalone panel stubs
    __init__.py
    plot_helpers.py      # mpl_available(), make_hz_canvas(), make_orbits_canvas(),
                         #   make_star_map_canvas(bg=), make_star_map_3d_canvas(bg=),
                         #   make_system_regions_canvas(), make_alt_hz_canvas(),
                         #   make_solar_travel_canvas(), make_solar_travel_canvas_3d(),
                         #   make_abundance_canvas()
                         #   (make_solar_travel_canvas_3d is unused — 3D removed from opts 22–23)
    hz_diagram.py        # HabZoneDiagramPanel — standalone stub (not in nav)
    star_map.py          # StarMapPanel — standalone stub (not in nav)
    system_orbits.py     # SystemOrbitsPanel — standalone stub (not in nav)
```

## Core Layer Design

All functions in `core/` follow this contract:
- Accept plain Python values (floats, strings, lists)
- Return a `dict` (or list of dicts) with named keys
- Raise no Qt dependencies
- Return `{"error": "message"}` for recoverable failures (bad input, no SIMBAD match, missing CSV)

This makes core functions testable in isolation and callable from both the CLI and GUI.

**`core.calculators.fetch_body_properties(horizons_id)`** is a special-purpose helper used only by the GUI's body-info dialog. It queries JPL Horizons with `OBJ_DATA=YES, MAKE_EPHEM=NO` and parses the text response into a structured dict. Returns `{"body_type": "planet"|"moon"|"asteroid"|"comet"|"unknown", "raw_text": ..., ...type-specific fields...}` or `{"body_type": "unknown", "error": str}`. Cached per `horizons_id` for the session in `_BODY_PROPS_CACHE`.

## GUI Layer Design

### MainWindow (`gui/app.py`)

- Left pane: `QTreeWidget` navigation (220 px fixed)
- Right pane: `QStackedWidget` holding panel instances
- Panels are created **lazily** on first click and cached — `show_panel(panel_class)` handles creation and display
- Navigating to a **different** panel calls `panel.reset()` first, returning it to its initial blank state. Clicking the currently-visible nav entry does nothing.

### Navigation (`gui/nav.py`)

`NAVIGATION` is a list of `(category, [(label, panel_class_name), ...])` tuples. At click time, `_on_item_clicked` resolves the class name via `getattr(gui.panels, name)`. Entries whose class hasn't been created yet are silently ignored — this lets phases be added incrementally without breaking existing nav items.

Every nav entry maps to its own independent panel class. There are no shared tab-widget panels.

### Panel Base Class (`gui/panels/base.py`)

```
ResultPanel (QWidget)
  __init__             creates outer layout, calls _init_container()
  _init_container()    creates _container widget + self._layout, calls build_inputs()
                       then build_results_area(), then applies two post-build passes:
                       (1) sets QPushButton children to Fixed size policy (natural text width);
                       (2) sets setMaximumWidth(300) on all QLineEdit, QDateEdit, and QComboBox
                           children (unless the widget has property "no_width_cap" set to True)
  reset()              removes old _container (deleteLater), calls _init_container()
                       — used by show_panel() when switching to a different panel
  build_inputs()       override: add form widgets above results
  build_results_area() override: add result display widgets (default: QTextEdit)
  make_table(headers, rows) → QTableView  # rows displayed in insertion order; interactive column sorting enabled
  clear_results()      remove all widgets below the input section (_input_count)
  show_error(msg)      display red error label
  set_status(msg)      update MainWindow status bar
  # Phase C additions:
  run_in_background(fn, *args, on_result=None)
  _on_error(msg)
  _on_thread_done()
```

Phase C adds `Worker(QObject)` and `run_in_background()` to support network calls without freezing the UI. The pattern established in Phase C is reused by all subsequent network-bound panels (Phase D).

**Reset safety**: `_on_error` and `_on_thread_done` wrap `run_btn.setEnabled()` in `try/except RuntimeError` because a background thread can complete after a `reset()` has deleted the old button widget.

**`make_table` sort-indicator fix**: `QTableView::setSortingEnabled(True)` triggers an immediate sort using the header's default sort indicator (column 0, descending), which scrambles insertion order. `make_table` calls `horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)` first to reset the indicator to "no column", making `setSortingEnabled(True)` a no-op for the initial display. Rows are shown in the order passed in; users can still click any column header to interactively sort.

### DiagramToggleMixin (`gui/panels/base.py`)

`DiagramToggleMixin` is a Python multiple-inheritance mixin that adds a full-screen **Show Diagrams / Show Tables** toggle to any `ResultPanel` subclass. Used by all panels that have embedded matplotlib visualizations.

**Subclass contract** (wired up in `build_inputs()` / `build_results_area()`):

| Attribute | Type | Purpose |
|---|---|---|
| `_form_widget` | `QWidget` | Wraps the input form; hidden in diagram mode |
| `_tables_widget` | `QWidget` (or `QScrollArea`) | Wraps data/table results; hidden in diagram mode |
| `_show_diagrams_btn` | `QPushButton` | Lives inside `_form_widget`; starts hidden, revealed after a successful render with viz tabs |

Call `self._setup_diagram_view()` at the end of `build_results_area()` to create:
- `_viz_container` — hidden `QWidget` containing a "Show Tables" button bar + `_viz_tabs_widget`
- `_viz_tabs_widget` — `QTabWidget` that receives diagram canvases during `_render()`

**MRO ordering**: Always declare as `(DiagramToggleMixin, SomeBasePanel)` so the mixin's `reset()` runs before the base class re-creates the container.

**Typical `_render()` pattern**:
```python
def _render(self, result):
    self._prepare_render()          # exit diagram mode, hide btn, clear viz tabs
    # ... populate _tables_widget / _result_area with data ...
    # ... add viz QWidgets to self._viz_tabs_widget ...
    self._finish_render()           # show Show Diagrams btn if any viz tabs were added
```

**Mixin API**:

| Method | Description |
|---|---|
| `_setup_diagram_view()` | Creates `_viz_container` + `_viz_tabs_widget`; call at end of `build_results_area()` |
| `_clear_viz_tabs()` | Removes and deletes all tabs from `_viz_tabs_widget` |
| `_prepare_render()` | Calls `_exit_diagram_mode()`, hides `_show_diagrams_btn`, clears viz tabs |
| `_finish_render()` | Shows `_show_diagrams_btn` if `_viz_tabs_widget` has any tabs |
| `_enter_diagram_mode()` | Hides `nav_tree`, `_form_widget`, `_tables_widget`; shows `_viz_container` |
| `_exit_diagram_mode()` | Reverses: shows nav + form + tables; hides viz container |
| `reset()` | Restores `nav_tree` before `super().reset()` — safe if reset while in diagram mode |

**NasaPlanetarySystemsPanel (opt 3) exception**: This panel has an inline implementation of the same toggle pattern (not via mixin) because its results area uses `_scroll_area` rather than a generic `_tables_widget`. The behavior is identical to the mixin.

### Lazy import in `gui/panels/__init__.py`

`__init__.py` uses a module-level `__getattr__` to lazily import the three visualization panel classes (`StarMapPanel`, `SystemOrbitsPanel`, `HabZoneDiagramPanel`). This avoids a circular import: those panels inherit from `ResultPanel` in `gui.panels.base`, which is part of the `gui.panels` package — importing them at module load time would re-enter `gui.panels.__init__` before it had finished initializing.

```python
_VIZ_PANEL_MODULES = {
    "StarMapPanel":        "gui.visualizations.star_map",
    "SystemOrbitsPanel":   "gui.visualizations.system_orbits",
    "HabZoneDiagramPanel": "gui.visualizations.hz_diagram",
}
def __getattr__(name: str):
    if name in _VIZ_PANEL_MODULES:
        import importlib
        mod = importlib.import_module(_VIZ_PANEL_MODULES[name])
        cls = getattr(mod, name)
        globals()[name] = cls   # cache so subsequent getattr hits globals() directly
        return cls
    raise AttributeError(f"module 'gui.panels' has no attribute {name!r}")
```

## Panel Class → Option Mapping

| Panel Class | Option(s) | File |
|---|---|---|
| `SolarSystemPanel` | 11 | `panels/science_tables.py` |
| `MainSequencePanel` | 12 | `panels/science_tables.py` |
| `SolRegionsPanel` | 13 | `panels/sol_regions.py` |
| `HonorverseHyperPanel` | 14 | `panels/honorverse.py` |
| `HonorverseAccelPanel` | 15 | `panels/honorverse.py` |
| `HonorverseSpeedPanel` | 16 | `panels/honorverse.py` |
| `HonorverseHyperTimePanel` | — (GUI-only, Phase K1) | `panels/honorverse.py` |
| `HonorverseImpellerPanel` | — (GUI-only, Phase K2) | `panels/honorverse.py` |
| `HonorverseMissilePanel` | — (GUI-only, Phase K3) | `panels/honorverse.py` |
| `VelocityLyHrPanel` | 31 | `panels/velocity.py` |
| `VelocityTimesCPanel` | 32 | `panels/velocity.py` |
| `DistanceLyHrPanel` | 25 | `panels/distance.py` |
| `DistanceTimesCPanel` | 26 | `panels/distance.py` |
| `TravelTimeLyHrPanel` | 27 | `panels/travel_time.py` |
| `TravelTimeTimesCPanel` | 28 | `panels/travel_time.py` |
| `OrbitPeriastronPanel` | 33 | `panels/orbit_calc.py` |
| `MoonDistance24Panel` | 34 | `panels/orbit_calc.py` |
| `MoonDistanceXPanel` | 35 | `panels/orbit_calc.py` |
| `GravityAccelPanel` | 36 | `panels/rotating_habitat.py` |
| `GravityDistancePanel` | 37 | `panels/rotating_habitat.py` |
| `GravityRpmPanel` | 38 | `panels/rotating_habitat.py` |
| `HabZonePanel` | 39 | `panels/habitable_zone_calc.py` |
| `HabZoneSmaPanel` | 40 | `panels/habitable_zone_calc.py` |
| `LuminosityPanel` | 41 | `panels/luminosity.py` |
| `RocheLimitPanel` | — (GUI + `query.py roche-limit`, Phase H) | `panels/worldbuilding.py` |
| `TidalLockingPanel` | — (GUI + `query.py tidal-locking`, Phase H) | `panels/worldbuilding.py` |
| `HillSpherePanel` | — (GUI + `query.py hill-sphere`, Phase H) | `panels/worldbuilding.py` |
| `BinaryOrbitPanel` | — (GUI + `query.py binary-stability`, Phase H) | `panels/worldbuilding.py` |
| `AtmosphereRetentionPanel` | — (GUI + `query.py atmosphere-retention`, Phase H) | `panels/worldbuilding.py` |
| `SolventZonePanel` | — (GUI + `query.py solvent-zone`, Phase P P4) | `panels/solvent_zones.py` |
| `IceLineCalculatorPanel` | — (GUI + `query.py ice-lines`, Phase P P5) | `panels/solvent_zones.py` |
| `SolventReferencePanel` | — (GUI-only, Phase P P6) | `panels/solvent_zones.py` |
| `SimbadPanel` | 1 | `panels/simbad.py` |
| `StarRegionsAutoPanel` | 8 | `panels/star_regions.py` |
| `StarRegionsSemiManualPanel` | 9 | `panels/star_regions.py` |
| `StarRegionsManualPanel` | 10 | `panels/star_regions.py` |
| `DistanceBetweenStarsPanel` | 17 | `panels/distance_stars.py` |
| `StarsWithinDistanceSolPanel` | 18 | `panels/distance_stars.py` |
| `StarsWithinDistanceStarPanel` | 19 | `panels/distance_stars.py` |
| `NasaPlanetarySystemsPanel` | 3 | `panels/nasa_exoplanet.py` |
| `NasaPlanetarySystemsMapPanel` | 3 (GUI-only variant w/ System Map) | `panels/nasa_exoplanet.py` |
| `NasaHwoExepPanel` | 4 | `panels/nasa_exoplanet.py` |
| `NasaMissionExocatPanel` | 5 | `panels/nasa_exoplanet.py` |
| `HwcPanel` | 6 | `panels/catalogs.py` |
| `TravelTimeStarsLyHrPanel` | 20 | `panels/travel_time_stars.py` |
| `TravelTimeStarsTimesCPanel` | 21 | `panels/travel_time_stars.py` |
| `BrachistochroneAccelPanel` | 24 | `panels/brachistochrone.py` |
| `BrachistochroneAuPanel` | 29 | `panels/brachistochrone.py` |
| `BrachistochroneLmPanel` | 30 | `panels/brachistochrone.py` |
| `SystemTravelSolarPanel` | 22 | `panels/system_travel.py` |
| `SystemTravelThrustPanel` | 23 | `panels/system_travel.py` |
| `CsvUtilityPanel` | 50 | `panels/csv_utility.py` |
| `ExportStarSystemsPanel` | 51 | `panels/csv_utility.py` |
| `ImportHwcPanel` | 52 | `panels/csv_utility.py` |
| `ImportMissionExocatPanel` | 53 | `panels/csv_utility.py` |
| `ImportMainSequencePanel` | 54 | `panels/csv_utility.py` |
| `ImportSolarSystemPanel` | 55 | `panels/csv_utility.py` |
| `ImportHonorversePanel` | 56 | `panels/csv_utility.py` |
| `DbStatusPanel` | 57 (GUI only) | `panels/csv_utility.py` — DB-table row counts + the cached dust-map files (`core.dust.get_dust_map_status()`) + the research-priors cache status (`core.research_priors.get_research_priors_status()`, Phase R3) |
| `ImportGcnsPanel` | 58 | `panels/csv_utility.py` |
| `ImportHypatiaPanel` | — (GUI-only, Phase L4) | `panels/csv_utility.py` |
| `FetchDustMapPanel` | 59 (GUI + CLI; Phase T2 — optional dust extra) | `panels/csv_utility.py` |
| `ImportResearchPriorsPanel` | — (GUI-only, Phase R3 — research-priors contract import) | `panels/csv_utility.py` |
| `StarSystemsSearchPanel` | — (GUI + `query.py search-star-systems`, Phase G1) | `panels/search.py` |
| `HwcSearchPanel` | — (GUI + `query.py search-hwc`, Phase G2) | `panels/search.py` |
| `NasaExoplanetSearchPanel` | — (GUI + `query.py search-exoplanets`, Phase G3) | `panels/search.py` |
| `HypatiaSearchPanel` | — (GUI + `query.py search-hypatia`, Phase L4) | `panels/search.py` |
| `GcnsCensusBrowserPanel` | — (GUI + `query.py gcns-within-sol`, Phase M1) | `panels/gcns.py` |
| `GcnsSourceLookupPanel` | — (GUI + `query.py gcns-source`, Phase M2) | `panels/gcns.py` |
| `GcnsSystemViewerPanel` | — (GUI + `query.py gcns-system`, Phase M3) | `panels/gcns.py` |
| `GcnsDistancePanel` | — (GUI + `query.py gcns-distance`, Phase M4a) | `panels/gcns.py` |
| `GcnsTravelTimePanel` | — (GUI + `query.py gcns-travel-time`, Phase M4b) | `panels/gcns.py` |
| `GcnsStarsWithinStarPanel` | — (GUI + `query.py gcns-stars-within-star`, Phase M4c) | `panels/gcns.py` |
| `MultiStopJourneyPanel` | — (GUI + `query.py multi-stop`, Phase I1) | `panels/route_planning.py` |
| `OptimalTourPanel` | — (GUI + `query.py optimal-tour`, Phase I-OPTS A) | `panels/route_planning.py` |
| `NearestNeighborPanel` | — (GUI + `query.py nearest-neighbor`, Phase I2) | `panels/route_planning.py` |
| `FarthestFirstPanel` | — (GUI + `query.py farthest-first`, Phase I-OPTS D) | `panels/route_planning.py` |
| `JumpRoutePanel` | — (GUI + `query.py jump-route`, Phase I-OPTS B) | `panels/route_planning.py` |
| `JumpNetworkPanel` | — (GUI + `query.py jump-network`, Phase I-OPTS C) | `panels/route_planning.py` |
| `TradeRoutePlannerPanel` | — (GUI + `query.py trade-route`, Phase I3, stretch) | `panels/route_planning.py` |
| `StarComparisonPanel` | — (GUI + `query.py compare-stars`, Phase L1) | `panels/comparison.py` |
| `EsiRankingPanel` | — (GUI-only, Phase L2) | `panels/comparison.py` |
| `StellarEvolutionPanel` | — (GUI + `query.py stellar-evolution`, Phase L3) | `panels/comparison.py` |
| `DossierExportPanel` | — (GUI + `query.py dossier`, Phase Q) | `panels/reports.py` |
| `ProjectPanel` | — (GUI + `query.py project-list`/`project-get`, Phase S) | `panels/projects.py` |
| `SystemGeneratorPanel` | — (GUI + `query.py generate-system`, Phase R1) | `panels/generator.py` |

> **Note**: `NasaAllTablesPanel` (opt 2) and `OecPanel` (opt 7) are implemented in `nasa_exoplanet.py` and `catalogs.py` respectively, but are **not exported** from `panels/__init__.py` and do not appear in the GUI nav. Both options remain fully functional in the CLI.

> **Note**: `StarMapPanel`, `SystemOrbitsPanel`, and `HabZoneDiagramPanel` live in `gui/visualizations/` and are exported via the lazy `__getattr__` in `panels/__init__.py`. They are **not in the nav tree** — visualizations appear as embedded tabs inside the relevant option panels rather than as standalone nav entries.

## Search & Filter Panels (Phase G — `panels/search.py`, `panels/search_common.py`)

The three **Search & Filter** nav entries (`StarSystemsSearchPanel`,
`HwcSearchPanel`, `NasaExoplanetSearchPanel`) introduce an **inline drill-down
tab** pattern — new vs. the rest of the GUI, which shows one panel at a time.

- **`SearchPanelBase(ResultPanel)`** (`panels/search_common.py`) hosts an inner
  `QTabWidget` with a permanent **"Search Results"** tab (index 0 — its close
  button is stripped) plus **closable detail tabs** added on demand, so the user
  can open multiple stars/planets at once and switch between them. `open_detail_tab(key, title, factory)`
  re-focuses an already-open `key` instead of duplicating it; `tabCloseRequested`
  refuses index 0 and defensively restores `window.nav_tree` (in case a detail
  panel was closed while in full-screen diagram mode). Subclasses implement
  `build_search_ui(layout)` and use `_build_results_scaffold(layout)` +
  `_render_table(headers, display_rows, records, open_label, on_open, noun)`.
  `_render_table` stashes each record on its column-0 item via `Qt.UserRole`, so
  row selection survives interactive column sorting. `run_btn` is the standard
  `ResultPanel` attribute, so background searches (G1/G3) auto-disable it.
- **`SpectralClassControl(QWidget)`** (`panels/search_common.py`) is the shared
  `O B A F G K M Other` chip row + refine box used by all three panels. API:
  `.classes()`, `.refine()`, `.is_empty()`, `.clear()`, and a `changed` signal
  (drives G1's "≥1 filter" button gating). It mirrors the core
  `spectral_where` / `spectral_adql` semantics (see `docs/star-databases.md`).
- **Detail tabs reuse existing panels** by embedding an instance: G1 →
  `SimbadPanel`, G2 → `HwcPanel`, G3 → `NasaPlanetarySystemsPanel`. The factory
  constructs the panel with the shared `window`, sets its name field
  (`_name_input` / `_name`), and calls `_search()` to run the normal lookup
  (Hypatia / diagrams come along for free). G1's `SimbadPanel` has no full-screen
  diagram toggle so it embeds cleanly; the G2/G3 targets carry their own
  Show Diagrams toggle, which operates within the detail tab.

## GCNS Panels (Phase M — `panels/gcns.py`)

Six **GUI-only** panels (no menu numbers) under a new **"GCNS"** nav category that
surface the GCNS census (opt 58) — previously reachable only via `query.py`'s
`gcns-*` subcommands. **All call the existing `core.databases.compute_gcns_*`
functions verbatim**; the file adds no new core code. The only new `core/` code in
Phase M is M5 (the `compute_simbad_lookup` `"gcns"` enrichment — see below).

- **Dual name/id resolution model.** M2/M3/M4 panels expose **both** a name
  `QLineEdit` (resolved via SIMBAD → Gaia id) and a raw Gaia source_id `QLineEdit`
  (offline) per endpoint; **the id wins if both are filled**. The shared
  `_GcnsFormPanel._endpoint()` returns `('id'|'name'|'empty'|'err', value)`, and
  `_go(fn, kwargs, network)` branches: **any name endpoint → `run_in_background`**
  (SIMBAD network), **all-id → synchronous instant** call. The `compute_gcns_*`
  functions do the actual resolution internally (their `star=`/`id=`/`source_id=`
  params), so the panels add no resolution logic. Core errors (not-in-GCNS,
  ambiguous name, empty table) surface in the panel's red `_err` label.
- **`GcnsCensusBrowserPanel` (M1)** and **`GcnsStarsWithinStarPanel` (M4c)** inherit
  `(DiagramToggleMixin, ResultPanel)` and reuse the opt-18/19 map infrastructure —
  a module-level `_gcns_map_stars(result, center=)` adapts the GCNS rows (snake_case
  `star_name`/`spectral_type`/`light_years` + `x`/`y`/`z`) into the
  `{name, color, ly, x, y, z}` shape, and `_add_chart_tabs(panel, stars, limit_ly)`
  adds the labeled dark-navy **"Star Chart"** + **"Star Chart 3D"** tabs
  (`make_star_chart_canvas` / `_build_star_chart_3d_tab`, the opts-18/19 diagrams;
  3D with Top/Side/Perspective presets) to `_viz_tabs_widget` — the center (Sol or
  the queried star) is the gold ★ at the origin. M1 is an **instant** local read
  (no thread, like opt 18); M4c
  threads only when the center is a name. The **−σ / +σ (pc)** uncertainty columns
  (`dist_lo_pc`/`dist_hi_pc`, `—` for `missing_10mas`) are the headline — the app's
  only distance error bar.
- **`GcnsSourceLookupPanel` (M2)**, **`GcnsSystemViewerPanel` (M3)**,
  **`GcnsDistancePanel` (M4a)**, **`GcnsTravelTimePanel` (M4b)** inherit the
  `_GcnsFormPanel` scaffold (red `_err` label + a `_box` result container rebuilt
  per run, `_kv()` for Field/Value tables). M2 renders a Bayesian-distance-with-σ
  headline + detail (Gaia G/BP/RP kept explicitly separate from Johnson V) + a
  resolved-system pointer when `system_id` is set, or a muted "not part of a
  Gaia-resolved multiple system (single or unresolved)" note otherwise (so the
  multiplicity status is explicit and agrees with the System Viewer); M3 renders
  System Summary + Members (▶ on the queried
  component) + Pairs; M4a/M4b render the distance / travel-time results.

### M5 — opt-1 SIMBAD GCNS cross-reference

`compute_simbad_lookup` gains a **non-fatal, silent** top-level `"gcns"` key
(`core/databases.py::_simbad_gcns_block`): the Gaia id is parsed from the
designations and looked up via `compute_gcns_by_source_id` (one indexed local read,
no extra network); `None` when there is no Gaia id / not in GCNS / table empty.
`SimbadPanel.render` adds a **"GCNS" tab** (after Star Properties) when
`result["gcns"]` is present, showing the **Bayesian distance with 16th/84th
uncertainty beside opt 1's naive 1/ϖ distance**, `distance_method`,
`astrom_reliable_prob`, `wd_prob`, Gaia G/BP/RP, and a resolved-system pointer.
`query.py simbad-lookup` emits the key with **no dispatcher change** (it serializes
the core dict verbatim).

## Star Regions Panel Layout Notes

### Star Regions Panels (`panels/star_regions.py`)

Three independent panels for opts 8 (Auto/SIMBAD), 9 (Semi-Manual), and 10 (Manual). All inherit `(DiagramToggleMixin, ResultPanel)` and produce the same result tabs; they differ only in how input values are collected.

- **Auto (opt 8)** — one `QLineEdit` for star name; hardcoded `sunlight=1.0`, `albedo=0.3`. Single background worker combines SIMBAD lookup + region computation.
- **Semi-Manual (opt 9)** — star name + sunlight intensity + bond albedo inputs. Same combined background worker.
- **Manual (opt 10)** — six `QLineEdit` fields (vmag, parallax, BC, teff, sunlight, albedo); pure math, no network call.

`build_results_area()` calls `_build_results_area_regions(panel)` which creates:
- `_tables_widget` — `QWidget` wrapping `_result_area` (a `QVBoxLayout`); holds the seven data tabs.
- `_viz_container` + `_viz_tabs_widget` — created by `_setup_diagram_view()`.

All three share `_build_region_tabs(d, viz_widget=None)` which produces a `QTabWidget` with seven always-present data tabs. When `viz_widget` is provided (a `_viz_tabs_widget` from the mixin), the diagram tabs are added there instead of the data tabs. The diagram-tab block itself is the module-level `star_regions.add_region_diagram_tabs(target, d, hypatia=None)` (Phase O O6), **reused verbatim** by `SolRegionsPanel` (opt 13) so Sol gets HZ / System Regions / Alternate HZ ring parity with opts 9/10 (opt 13 passes `hypatia=None`, so it never gets the Abundance Profile tab):

Always present in data tabs (7): Star System Properties, Stellar Properties, Star Distance, Earth Equiv. Orbit, System Regions, Alternate HZ Regions, Calculated HZ.

Added to `viz_widget` when `mpl_available()` — three always, plus Abundance Profile and Kinematics (opt 8 only, each gated on its Hypatia data), so **up to 5 tabs for opt 8** and **3 for opts 9/10**:
- **HZ Diagram** — concentric ring diagram using `d["calculatedLuminosity"]` and `d["temp"]`; marks `d["distAU"]` as the EEID.
- **System Regions Diagram** — concentric ring diagram (√AU scale) showing all seven system boundary zones. Built from `core.viz.prepare_system_regions_diagram(d)` → `make_system_regions_canvas()`.
- **Alternate HZ Diagram** — concentric ring diagram (⁴√AU scale) for the six alternate-biochemistry HZ zones. Built from `core.viz.prepare_alt_hz_diagram(d)` → `make_alt_hz_canvas()`.
- **Abundance Profile** — horizontal [X/H] bar chart via `make_abundance_canvas()`; added only on opt 8 when `d.get("hypatia")` carries a non-empty abundances list. Opts 9/10 never call the Hypatia API, so they never get this tab.
- **Kinematics** (Phase O O11) — Toomre / galactic-kinematics diagram via `make_kinematics_tab(d["hypatia"])` (`core.viz.prepare_toomre` → `make_toomre_canvas` + the F2 "ℹ What is this?" Explain button); added only on opt 8 when Hypatia returns all three U/V/W velocities. Opts 9/10 never get it.

### Distance Stars Panels (`panels/distance_stars.py`)

`StarsWithinDistanceSolPanel` (18) and `StarsWithinDistanceStarPanel` (19) inherit `(DiagramToggleMixin, ResultPanel)`.

`build_results_area()` calls `_build_results_area_distance(panel)` which creates:
- `_tables_widget` — `QWidget` wrapping `_tables_layout` (a `QVBoxLayout`); count label and the star table are added here directly.
- `_viz_container` + `_viz_tabs_widget` — created by `_setup_diagram_view()`.

`_input_count` is updated **after** `build_results_area()` completes, so `clear_results()` never destroys the persistent `_tables_widget` or `_viz_container`.

The diagram tabs are added to `_viz_tabs_widget` (visible only in diagram mode) in display order by `_add_map_tabs(panel, map_stars, limit, title, result)`: **Star Chart**, **Star Chart 3D**, **HR Diagram**, **Night Sky**, **Map X–Y (top-down)**, **Map X–Z (edge-on)**, **Map 3D** — with **Star Chart selected by default** (`setCurrentIndex(0)`). HR Diagram + Night Sky are built inside `_add_map_tabs` (it takes the raw `result`) so they slot between the star charts and the maps. The Map 3D tab includes three Qt viewpoint preset buttons (Top View, Side View, 3D Perspective) above the matplotlib toolbar; the three Map canvases use a light gray background (`bg="#ebebeb"`) rather than the default `#f5f5f5`.

## Phase E Visualization Integration

Phase E adds matplotlib-based visualizations embedded inside existing option panels. All diagrams are accessed via the **Show Diagrams** button (see `DiagramToggleMixin` above) — they are hidden by default and expand to fill the window when activated. No new top-level nav entries were created.

### Shared rendering layer (`gui/visualizations/plot_helpers.py`)

`mpl_available()` returns `True` when `matplotlib` and `PySide6` are both importable. All viz-tab code is guarded by this check so the app works without matplotlib installed.

All canvas helpers return `(FigureCanvasQTAgg, NavigationToolbar2QT)`. Figures use a light theme (`facecolor="#f5f5f5"`, labels `#333333`, grid `#cccccc`).

| Helper | Panels that use it | Output |
|---|---|---|
| `make_hz_canvas(parent, zones, max_au, title, eeid_au)` | NASA opts 3–5, HWC (6), Star Regions 8–10 | Concentric ring HZ diagram; optional EEID circle |
| `make_orbits_canvas(parent, orbits, hz_zones, max_au, star_name, eeid_au, markers, solar_overlay=False, title=None, km_axis=False, hyper_au=None, snow_au=None, solvent_bands=None)` | NASA opts 3, 6, Map panel; Solar System (11) — Phase O O7 | Keplerian orbital ellipses with HZ annulus overlay. **Phase O O4** `solar_overlay=True` (additive): dashed grey reference circles at the Solar planets' SMAs (`core.viz._PLANET_SMAS`) that fit `max_au×1.1`, with end-of-orbit labels (drawn under the planet orbits); default `False` → byte-identical to before. Driven by the `wrap_orbits_with_solar_toggle` checkbox. **Phase O O7** (additive): `title` overrides the "Planetary Orbits" diagram title; `km_axis=True` adds a secondary top x-axis in km (AU × 1.496e8) for moon-system diagrams; both default off → byte-identical. **Phase O O10b** (additive): `hyper_au` > 0 draws a dashed-red Honorverse hyper-limit ring at that AU (expanding the frame to fit it); default `None` → byte-identical. **Phase P V6** (additive): `snow_au` > 0 draws a dashed-cyan water-snow-line ring (M2). **Phase P V7** (additive): `solvent_bands` (list of `{name, inner_au, outer_au, color}`) shades translucent solvent annuli behind the orbits; both default `None`/empty → byte-identical (the V6/V7 checkboxes default off via `wrap_orbits_with_solar_toggle`'s `snow_au`/`solvent_options` params, fed by `core.viz.prepare_orbit_overlays`). |
| `make_star_map_canvas(parent, stars, title, xk, yk, xlabel, ylabel, bg)` | Stars Within Distance 18, 19 | 2D scatter, spectral-class colours, hover annotation; `bg` overrides figure background colour |
| `make_star_map_3d_canvas(parent, stars, title, bg)` | Stars Within Distance 18, 19 | 3D scatter with drag-to-rotate (`azel` rotation style); returns `(canvas, toolbar, ax)` so caller can bind viewpoint preset buttons; `bg` overrides figure background colour; rectangle Zoom button removed from toolbar; scroll wheel zoom wired via `ax._zoom_data_limits()`; `toolbar.push_current()` called at creation so Home restores initial view; **cursor-anchored** hover tooltip (follows the pointer via `_anchor_hover_to_cursor`) |
| `make_star_chart_canvas(parent, stars, limit_ly, routes=None)` | Stars Within Distance 18, 19; Route Planning (Phase I) | Labeled X–Y star chart in the dark navy palette of `generate_star_map_html.py`; no title; scaled grid/major-tick/distance-ring intervals; per-star `"Name (Z=±X.XXX)"` labels anchored with a **fixed pixel offset** (`annotate(textcoords="offset points")`, so labels track their dots on zoom rather than drifting) plus screen-space collision-nudging and a `path_effects` stroke for readability; **all in-plot text (star/Sol labels + axis tick numbers, axis titles, and ring `N ly` labels) uses `clip_on=True`** (with `annotation_clip=True` on the annotations) so nothing leaks into the black margin when panned/zoomed — only the axes-fraction click-info box stays unclipped; center star drawn as a gold ★ at the origin (Sol for opt 18, queried star for opt 19); hover tooltip, click info box, scroll-wheel zoom around cursor; `toolbar.push_current()` seeds Home; xlim/ylim callbacks toggle label visibility based on a 15 ly half-range threshold. **Phase I `routes=`** (optional, additive): a list of `{x1,y1,z1,x2,y2,z2,label,style}` edge dicts drawn over the dots — dashed for ordered legs / solid (`_SC_MST`) for MST edges; route lines stay visible at all zooms while the per-segment labels follow the same zoom-driven decluttering as the star labels. Existing opt-18/19 callers pass no `routes` and are unaffected. **Shared with Phase O8.** |
| `make_star_chart_3d_canvas(parent, stars, limit_ly, routes=None)` | Stars Within Distance 18, 19; Route Planning (Phase I) | 3D companion to `make_star_chart_canvas` (same additive `routes=` overlay): dark navy panes + grid, gold ★ center marker, spectral-class star dots, per-star `"Name (Z=±X.XXX)"` labels **anchored at each star's exact 3D point with left/bottom alignment** (so they track the dot on rotation and zoom instead of drifting on a fixed data-space offset), zoom-driven via `xlim_changed`/`ylim_changed`/`zlim_changed` against `max((x1-x0)/2, (y1-y0)/2, (z1-z0)/2) ≤ 15 ly`; faint wireframe reference spheres at every `major_step` ly out to the limit; **cursor-anchored** hover tooltip (follows the pointer via `_anchor_hover_to_cursor`) + click info box (text2D pinned lower-left); `azel` drag rotation; scroll-wheel zoom via `ax._zoom_data_limits`; rectangle Zoom removed from the toolbar; returns `(canvas, toolbar, ax)` so caller can bind viewpoint preset buttons (Top / Side / 3D Perspective) |
| `make_system_regions_canvas(parent, data, show_hyper=False)` | Star Regions 8–10, 13 | Concentric ring diagram (√AU scale) with zone fills + boundary labels. **Phase O O10b** `show_hyper=True` (additive) draws a dashed-red Honorverse hyper-limit ring when `data["hyper_limit"]` is present; default `False` → byte-identical (no ring). Driven by `wrap_system_regions_with_hyper_toggle`'s checkbox. |
| `make_alt_hz_canvas(parent, zones, max_au, title, eeid_au)` | Star Regions 8–10 | Concentric ring diagram (⁴√AU scale) for alternate biochemistry HZ zones |
| `make_solar_travel_canvas(parent, data, on_body_click=None)` | System Travel 22, 23 | 2D top-down (XY ecliptic) solar system map: planet dots + reference orbit circles + origin ★ + dest ■ + dashed travel path; click calls `on_body_click(body_info)` if provided, otherwise shows inline info box. **Phase O O5b:** attaches an additive `canvas._scrub` bundle (per-body `(role,name) → {scatter, label, id}` handles + `ax`/`max_au`) so `_SolarMapScrubber` can re-offset markers from a cached ephemeris; non-animating callers ignore it (render byte-identical). |
| `make_exoplanet_system_canvas(parent, data, on_planet_click=None)` | NASA Planetary Systems Map | 2D top-down map of an exoplanet system at a given epoch: host star ★ at origin + per-planet dashed orbit ellipses (rotated by pl_orblper) + planet markers at date-resolved positions; planets with no usable epoch are marked with an open-ring overlay and placed at periastron; hover tooltip, click → `on_planet_click(planet_info)` or inline info box. **Phase O O5a:** attaches an additive `canvas._scrub` bundle (per-planet `{scatter, label, ring, epoch_known}` + `ax`/`max_au`/`title_base`) so `_SystemMapScrubber` re-offsets epoch-known markers per scrubbed date. |
| `make_solar_travel_canvas_3d(parent, data, on_body_click=None)` | *(unused — 3D removed from opts 22–23)* | 3D version of the solar system travel map (`azel` rotation); returns `(canvas, toolbar, ax)` for preset buttons; no floating 3D text labels — click calls `on_body_click(body_info)` if provided, otherwise shows `text2D` tooltip |
| `make_abundance_canvas(parent, abundances_data, star_name="")` | SIMBAD 1, NASA opts 3–6, Star Regions 8 | Horizontal bar chart of [X/H] elemental abundances (up to all 104 measured species); bars colored by **nucleosynthetic-family category** (colors from `core.hypatia_elements.CATEGORIES`), with a one-row gap + legend per category; `axvline` at 0; error bars from `std`; figure height scales with element count. Embedding panels wrap it in `wrap_scrollable()` so a tall chart scrolls. |
| `make_abundance_comparison_canvas(parent, data)` | Star Comparison (L1) | **Grouped** horizontal [X/H] bar chart comparing 1–4 stars — one bar per star within each element group, `axvline` at 0, per-star legend. Input from `core.viz.prepare_abundance_comparison()`. Wrapped in `wrap_scrollable()`. |
| `make_evolution_canvas(parent, data)` | Stellar Evolution (L3) | Horizontal stacked-bar evolutionary timeline — one colored segment per stage (`start_gyr`/`duration_gyr`), centered stage labels when wide enough, dashed red current-age marker. Input from `core.viz.prepare_evolution_diagram()`. |
| `make_esi_bar_canvas(parent, data)` | ESI Ranking (L2) | Horizontal top-N planets-by-ESI bar chart; bars colored by habitable flag (green/gray), value labels, highest ESI on top, habitable/not legend. Input from `core.viz.prepare_esi_bar_chart()`. Wrapped in `wrap_scrollable()`. |
| `make_scatter_canvas(parent, data)` | Hypatia Abundance Search (L4) | Generic 2D scatter with a nearest-point hover tooltip; one point per result star. Input from `core.viz.prepare_hypatia_scatter()` (axes chosen via the panel's X/Y dropdowns). Wrapped in `wrap_scrollable()`. |
| `make_hr_canvas(parent, data, overlay_points=None)` | Main Sequence (12), Stars Within Distance (18, 19) — Phase O O2 | HR / colour–magnitude diagram: Teff (log, inverted — hot left) vs absolute visual magnitude (inverted — bright top); main-sequence reference line + labelled points from `core.viz.prepare_hr_main_sequence()`, a secondary top axis of spectral-class letters, and optional `overlay_points` (`core.viz.prepare_hr_from_stars()["points"]`) — result stars as red dots, and any point flagged `highlight` (the Sol / queried-centre reference) as a gold ★. Light theme. |
| `make_sky_canvas(parent, data)` | Stars Within Distance (18, 19) — Phase O O1 | Night-sky RA/Dec view from the vantage (Sol for opt 18, the queried star for opt 19): RA reversed (sky convention), dark-navy Star-Chart palette, marker size by brightness, spectral-class colour, hover tooltip anchored to the hovered star (name + apparent magnitude), `skipped_no_mag` annotation in the title. Input from `core.viz.prepare_sky_from_star()`. |
| `make_mass_radius_canvas(parent, data)` | NASA opts 3, 6, Map panel — Phase O O3 | Log–log mass (M⊕) vs radius (R⊕) scatter: 4 dashed constant-density composition curves (`R=(M/(ρ/ρ⊕))^(1/3)`, ρ⊕=5.51 — iron/rock/water/Jupiter-ρ, labelled "constant density"), the 8 Solar-System reference points (grey), and the system planets (blue) with a dot-anchored hover tooltip. Light theme. Input from `core.viz.prepare_mass_radius()`. |
| `make_transit_canvas(parent, data)` | NASA opt 3, Map panel — Phase O O13 | Transit-geometry view: x = semi-major axis (AU, log), y = impact parameter `b` (R★); the `|b| ≤ 1` band is shaded "transiting" (the stellar disk) with dashed limb lines; planets green inside / red outside (clamped to a capped y-range, true `b` in the dot-anchored hover), an italic "node unknown" caveat + an inclination-less-skip footnote. Input from `core.viz.prepare_transit_geometry()`. |
| `make_size_comparison_canvas(parent, planets, radius_key, name_key)` | NASA opts 3, 6, Map panel — Phase O O14 | To-scale planet size strip: one row of circles (radius ∝ R⊕) for the radius-having planets + grey Earth (1 R⊕) / Jupiter (11.21 R⊕) reference anchors, sorted small→large on a baseline, name + radius labels, equal-aspect/no-ticks, dot-anchored hover. Takes the **raw** rows + column keys (no `prepare_*`; generic over NASA `pl_rade`/`pl_name` and HWC `P_RADIUS`/`P_NAME`); returns `(None, None)` when no planet has a radius (host panel skips the tab). Radius-less planets footnoted. |
| `make_hyper_bar_canvas(parent, data)` | Honorverse Hyper Limits (14) — Phase O O10a | Horizontal Honorverse hyper-limit bar chart: bars in light-minutes (LM) with a secondary top axis in AU (÷8.3167), coloured by spectral class, hottest (O) at top. 44 bars → tall figure wrapped in `wrap_scrollable`. Input from `core.viz.prepare_hyper_limits()`. |
| `make_toomre_canvas(parent, data)` | SIMBAD 1, NASA 3–5, HWC 6, Star Regions 8 — Phase O O11 | Toomre / galactic-kinematics diagram: x = V (km/s, LSR), y = √(U²+W²); dashed constant-total-velocity arcs at 50/100/180 km/s centred at the LSR origin; heuristic thin/thick/halo caption; the star a gold ★ (hover anchored to the dot); subtitle = Hypatia `disk` class; footnote flags the LSR correction. Light theme. Input from `core.viz.prepare_toomre()`. Returns an error-card canvas on `{"error"}`. |
| `make_kinematics_tab(hypatia)` | SIMBAD 1, NASA 3–5, HWC 6, Star Regions 8 — Phase O O11 | Builds the shared **"Kinematics"** viz-tab `QWidget` — an F2 "ℹ What is this?" `info_button` (`gui.help` / `TOOMRE_HELP_HTML`) over the Toomre canvas + toolbar — from a `compute_hypatia_data` result, or **None** when matplotlib is unavailable or `prepare_toomre` errors (U/V/W not all present), so each host adds the tab only when it qualifies. Calls `core.viz.prepare_toomre` + `make_toomre_canvas` internally. |
| `make_hwc_temp_canvas(parent, data)` | HWC 6 — Phase O O12 | Per-planet temperature-range bars: an equilibrium bar (orange) and/or surface bar (red) per planet with a central-value tick, plus a shaded 273–373 K "liquid water" band with dashed edges. x = Temperature (K). Light theme; tall figures wrapped in `wrap_scrollable`. Input from `core.viz.prepare_hwc_temps()`. |
| `make_hwc_esi_canvas(parent, data)` | HWC 6 — Phase O O12 | ESI-vs-orbit scatter: x = semi-major axis (AU, log when `log_x`), y = ESI; the host's optimistic (lighter) + conservative (darker) HZ as shaded green `axvspan` bands; points green (habitable) / grey, dot-anchored hover. Light theme. Input from `core.viz.prepare_hwc_esi()`. |
| `wrap_system_regions_with_hyper_toggle(parent, data)` | Star Regions 8, 9 (10/13 plain) — Phase O O10b | Wraps the System Regions canvas in a tab; when `data` carries a `hyper_limit` (opts 8/9 with a resolvable spectral type) adds a **"Show Honorverse Hyper Limit (fiction)"** `QCheckBox` (default off) that rebuilds the canvas with `show_hyper=True`; no hyper limit (opts 10/13) → no checkbox, plain canvas. Mirrors `wrap_orbits_with_solar_toggle`. Returns the container `QWidget` or `None`. |
| `make_profile_canvas(parent, data)` | System Travel 22, 23; Brachistochrone 24, 29, 30 — Phase O O9 | Two stacked subplots sharing the time (hours) axis: top = velocity (km/s, with a secondary `% c` right axis); bottom = cumulative distance (AU, with a secondary LM right axis). One light-theme line per brachistochrone profile (fixed colour per index — P1 red `#c0392b` / P2 blue `#2980b9` / P3 green `#27ae60`). Input from `core.viz.prepare_brachistochrone_profiles()` (reconstructs each profile's piecewise v(t)/d(t)). Returns an error-card canvas (not `(None,None)`) on `{"error"}`. No hover (continuous curves identified by the legend). |
| `wrap_orbits_with_solar_toggle(parent, build_canvas, hyper_au=None)` | NASA opts 3, 6, Map panel — Phase O O4 / O10b | Wraps an orbital-diagram canvas in a tab with a "Show Solar System reference" `QCheckBox`; `build_canvas(solar_overlay: bool, show_hyper: bool) -> (canvas, toolbar)` is rebuilt in place on toggle. **Phase O O10b:** when `hyper_au` > 0 a second "Show Honorverse Hyper Limit (fiction)" checkbox is added (default off → `show_hyper=False`); with `hyper_au=None` there is no second checkbox. Returns the container `QWidget`, or `None` if the canvas can't build. |
| `wrap_scrollable(parent, canvas, toolbar)` | all panels embedding `make_abundance_canvas` | Returns a `QWidget` with the toolbar pinned on top and the canvas in a `QScrollArea` sized to the figure's natural pixel height — short charts look unchanged; tall ones (50+ bars) scroll instead of compressing |

All ring diagrams support click-to-info: clicking a region or orbit shows a details box in the lower-left corner; clicking empty space dismisses it. The EEID circle (dark teal `#006644`) is also clickable.

**3D rotation style**: `make_star_map_3d_canvas` sets `matplotlib.rcParams['axes3d.mouserotationstyle'] = 'azel'` so horizontal drag = azimuth change and vertical drag = elevation change — the natural, predictable rotation behaviour. Preset buttons also deactivate any active toolbar zoom/pan mode before applying the viewpoint so 3D rotation works immediately after pressing a preset.

**3D toolbar and zoom**: The rectangle Zoom button is removed from the 3D toolbar (`toolbar.removeAction(action)`) because it cannot map a 2D screen rectangle back to 3D data coordinates. Scroll wheel zoom is wired explicitly with `canvas.mpl_connect('scroll_event', ...)` calling `ax._zoom_data_limits(scale, scale, scale)` — matplotlib 3.10 removed the native `Axes3D._on_scroll` handler so it must be wired manually. Scale `0.9` zooms in (shrinks axis range to 90%); `1/0.9 ≈ 1.11` zooms out. `toolbar.push_current()` is called immediately after creating the toolbar to seed the nav stack with the initial xlim/ylim/zlim + elev/azim/roll; without this the stack is empty and the Home button (`_nav_stack.home()`) has nothing to restore and silently does nothing.

**3D hover tooltip**: The hover `text2D` is **cursor-anchored** — `_anchor_hover_to_cursor(hover_text, ax, event)` converts the cursor's display-pixel position (`event.x`/`event.y`, reliable in 3D unlike `event.xdata`/`ydata`) into the axes' 2D fraction frame and repositions the label next to the hovered dot, flipping `ha`/`va` by quadrant and clamping to `[0.02, 0.98]` so it never runs off-canvas. (It previously sat fixed at `(0.98, 0.97)`; the cursor-anchored form matches the 2D Star Chart and the Phase O dot-anchored hover convention.) The click info box stays pinned at the lower-left (`0.02, 0.02`).

### Panels with embedded viz tabs

Viz tabs are populated during `_render()` and placed in `_viz_tabs_widget` (via mixin) or the panel's own inline equivalent. The **Show Diagrams** button appears next to **Search/Calculate** only after a successful render that produced at least one viz tab.

| Panel | Viz tab(s) | Toggle mechanism |
|---|---|---|
| `SimbadPanel` (1) | "Star Properties", "GCNS" (when `result["gcns"]` present — Phase M5), "Hypatia", "Abundance Profile" + "Kinematics" (Phase O O11, when Hypatia data / U·V·W available) — inline `QTabWidget`, no Show Diagrams button | Inline (all tabs always visible) |
| `NasaPlanetarySystemsPanel` (3) | "Orbital Diagram" (+ Phase O O4 solar-overlay checkbox & O10b hyper-limit checkbox), "HZ Diagram", "Mass–Radius" (Phase O O3), "Transit Geometry" (Phase O O13), "Size Comparison" (Phase O O14), "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | Inline (uses `_scroll_area`) |
| `NasaPlanetarySystemsMapPanel` | "System Map" (+ Phase O O5a date scrubber), "Orbital Diagram" (+ O4 solar-overlay & O10b hyper-limit checkboxes), "HZ Diagram", "Mass–Radius" (O3), "Transit Geometry" (O13), "Size Comparison" (O14), "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | Inline (uses `_scroll_area`) |
| `NasaHwoExepPanel` (4) | "HZ Diagram" (EEID from `st_eei_orbsep`), "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | `DiagramToggleMixin` |
| `NasaMissionExocatPanel` (5) | "HZ Diagram" (EEID from `st_eeidau`; lum = `st_lbol` direct Lsun), "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | `DiagramToggleMixin` |
| `HwcPanel` (6) | "Orbital Diagram" (+ Phase O O4 solar-overlay & O10b hyper-limit checkboxes), "HZ Diagram" (lum = `S_LUMINOSITY` direct Lsun), "Mass–Radius" (Phase O O3), "Size Comparison" (Phase O O14), "Temperature Ranges" + "ESI vs Orbit" (Phase O O12, per qualifying planets), "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | `DiagramToggleMixin` |
| `StarRegionsAutoPanel` (8) | "HZ Diagram", "System Regions Diagram" (+ Phase O O10b "Show Honorverse Hyper Limit" checkbox), "Alternate HZ Diagram", "Abundance Profile" + "Kinematics" (Phase O O11) (when Hypatia data / U·V·W available) | `DiagramToggleMixin` |
| `StarRegionsSemiManualPanel` (9) | "HZ Diagram", "System Regions Diagram" (+ Phase O O10b "Show Honorverse Hyper Limit" checkbox), "Alternate HZ Diagram" | `DiagramToggleMixin` |
| `StarRegionsManualPanel` (10) | "HZ Diagram", "System Regions Diagram", "Alternate HZ Diagram" | `DiagramToggleMixin` |
| `SolarSystemPanel` (11) | "Orbital Diagram" (combo: Planets / Dwarf Planets + Asteroids), "Moon Systems" (combo: per-planet moons, km secondary axis) — Phase O O7 | `DiagramToggleMixin` |
| `MainSequencePanel` (12) | "HR Diagram" (Phase O O2a — main-sequence reference) | `DiagramToggleMixin` |
| `SolRegionsPanel` (13) | "HZ Diagram", "System Regions Diagram" (+ Phase O O10b "Show Honorverse Hyper Limit" checkbox — `compute_sol_regions` sets `spectral_type="G2V"`), "Alternate HZ Diagram" (Phase O O6 — parity with opts 9/10, via `star_regions.add_region_diagram_tabs`) | `DiagramToggleMixin` |
| `HonorverseHyperPanel` (14) | "Hyper Limits" (Phase O O10a — hyper-limit bar chart, LM + secondary AU axis) | `DiagramToggleMixin` |
| `StarsWithinDistanceSolPanel` (18) | "Star Chart" (default), "Star Chart 3D", "HR Diagram" (Phase O O2b), "Night Sky" (Phase O O1 — vantage = Sol), "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" | `DiagramToggleMixin` |
| `StarsWithinDistanceStarPanel` (19) | "Star Chart" (default), "Star Chart 3D", "HR Diagram" (Phase O O2b), "Night Sky" (Phase O O1 — mag-limit re-runnable), "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" | `DiagramToggleMixin` |
| `DistanceBetweenStarsPanel` (17) | "Star Chart", "Star Chart 3D" (Phase O O8 — two-star map via Phase I `routes=`) | `DiagramToggleMixin` |
| `TravelTimeStarsLyHrPanel` (20) / `TravelTimeStarsTimesCPanel` (21) | "Star Chart", "Star Chart 3D" (Phase O O8 — edge labelled with distance + travel time + ×c) | `DiagramToggleMixin` |
| `SystemTravelSolarPanel` (22) | "Solar System Map" (+ Phase O O5b date scrubber), "Acceleration Profiles" (Phase O O9) | `DiagramToggleMixin` |
| `SystemTravelThrustPanel` (23) | "Solar System Map" (+ Phase O O5b date scrubber), "Acceleration Profiles" (Phase O O9 — single custom-thrust profile) | `DiagramToggleMixin` |
| `BrachistochroneAccelPanel` (24) / `BrachistochroneAuPanel` (29) / `BrachistochroneLmPanel` (30) | "Acceleration Profiles" (Phase O O9) | `DiagramToggleMixin` |
| `StarComparisonPanel` (L1) | "Abundance Profiles" (when ≥1 star has abundances) | `DiagramToggleMixin` |
| `EsiRankingPanel` (L2) | "ESI Chart" (top-N planets-by-ESI bar chart) | `DiagramToggleMixin` |
| `StellarEvolutionPanel` (L3) | "Evolution Diagram" | `DiagramToggleMixin` |
| `HypatiaSearchPanel` (L4) | "📈 Plot" (selectable X/Y scatter of the result set) | `SearchPanelBase` closable detail tab (X/Y dropdowns + "Show Plot") |
| `SystemGeneratorPanel` (R1/R2/R3) | "Orbit Diagram" (`make_orbits_canvas`, observed-green vs synthetic-blue orbits + HZ annulus + snow-line ring), "HZ Ring" (`make_hz_canvas`); **Phase R2** adds an in-place constraint builder (`_ConstraintRow`) + a four-layer feasibility banner/cards (verdict chip, Layer-1 reason, Layer-2 mechanism, Layer-3 tagged origin, Layer-4 clickable-apply alternative buttons) when ≥1 constraint is present; **Phase R3** adds a **Research policy** combo (`permissive`/`strict`) + a status pill (`DEFAULTS` / `RESEARCH · <version>` / `RESEARCH · none ingested`) — `strict` draws research-calibrated priors (the result grounding badges flip automatically), or surfaces a curated error when no dataset is ingested | `DiagramToggleMixin` |

### `core/viz.py` public API

| Function | Description |
|---|---|
| `prepare_star_map(csv_path=None)` | Reads `starSystems.csv`; returns `{"stars": list, "count": int}` or `{"error": str}`. Sol prepended at origin. Each star dict: `name, desig, sp_type, color, ly, x, y, z`. |
| `prepare_system_orbits(planets)` | Takes NASA-archive planet list (dicts with `pl_orbsmax`, `pl_orbeccen`, `pl_name`, `st_teff`, `st_rad`). Returns `{"orbits", "hz_zones", "max_au", "star_name"}` or `{"error": str}`. |
| `prepare_solar_system_orbits(kind="planets")` | **Phase O O7.** Solar-system orbital-ellipse data from `core.science.compute_solar_system_tables()`. `kind ∈ {"planets", "dwarfs_asteroids", "moons:<planet>"}` — moon SMAs are km (÷1.496e8 → AU). Same orbit-dict shape as `prepare_system_orbits` plus `{hz_zones: [], max_au, star_name}` (no HZ) or `{"error": str}`. Feeds `make_orbits_canvas` (opt 11). |
| `prepare_hz_diagram(teff, luminosity)` | Returns `{"zones": list, "max_au": float}` or `{"error": str}`. Each zone dict: `key, label, outer (AU), color`. |
| `prepare_star_map_from_result(result)` | Converts `compute_stars_within_distance_of_sol/star` result dict to star-map format. Center star placed at origin; surrounding stars' coordinates shifted accordingly. |
| `prepare_system_regions_diagram(d)` | Extracts seven labelled boundary AU values + Kopparapu HZ zones + EEID from a star-regions result dict. Returns `{"regions", "hz_zones", "eeid_au", "max_au"}`. **Phase O O10b:** when `d["spectral_type"]` resolves (opts 8/9), also attaches a separate `"hyper_limit": {label, au, color, matched_class}` overlay key (via `core.science.compute_hyper_limit_for_spectral_type`, ceiling rule) — **not** part of `regions`; the canvas draws it only with `show_hyper=True`. Absent for opt-10/opt-13 dicts (no `spectral_type`) or an unresolvable type. |
| `prepare_hyper_limits()` | **Phase O O10a.** Honorverse hyper-limit bar-chart data from `core.science.compute_honorverse_hyper_limits()` (44 classes). Returns parallel lists `{classes, lm, au, colors}` in table order (hot→cool), coloured by leading spectral class. Feeds `make_hyper_bar_canvas`. |
| `prepare_toomre(hypatia_result)` | **Phase O O11.** Toomre / galactic-kinematics data from a `compute_hypatia_data` result. Hypatia's U/V/W are heliocentric, so they are **LSR-corrected** (add `_SOLAR_MOTION_UVW` = Schönrich+ 2010) before computing `uw = √(U²+W²)` and `total = √(U²+V²+W²)`. Returns `{v, uw, total, disk, star_name}` (all LSR-frame km/s) or `{"error": str}` when any of U/V/W is null. Feeds `make_toomre_canvas`. |
| `prepare_hwc_temps(planet_rows)` | **Phase O O12.** Per-planet equilibrium (`P_TEMP_EQUIL_MIN/MAX`, centre `P_TEMP_EQUIL`) + surface (`P_TEMP_SURF_MIN/MAX`, centre `P_TEMP_SURF`) temperature ranges from HWC planet rows. A planet qualifies with ≥1 complete min/max pair; the rest go in `skipped`. Returns `{planets:[{name, eq_min, eq, eq_max, surf_min, surf, surf_max}], skipped}` or `{"error": str}` when none qualify. Feeds `make_hwc_temp_canvas`. |
| `prepare_hwc_esi(star_row, planet_rows)` | **Phase O O12.** ESI-vs-orbit data: per planet `P_SEMI_MAJOR_AXIS` (AU) vs `P_ESI`, coloured by `P_HABITABLE`; the host's optimistic (`S_HZ_OPT_MIN/MAX`) + conservative (`S_HZ_CON_MIN/MAX`) HZ as bands; `log_x` when the SMA span > 10×. Planets missing SMA or ESI go in `skipped`. Returns `{planets:[{name, a_au, esi, habitable}], hz_opt, hz_con, log_x, skipped}` or `{"error": str}` when none qualify. Feeds `make_hwc_esi_canvas`. |
| `prepare_alt_hz_diagram(d)` | Extracts the six alternate-biochemistry HZ zones from a star-regions result dict (Fluorosilicone-Fluorosilicone, Fluorocarbon-Sulfur, Protein-Water, Protein-Ammonia, Polylipid-Methane, Polylipid-Hydrogen). Returns `{"zones", "max_au"}` or `{"error": str}`; each zone dict: `label, inner_au, outer_au, color`, ordered hot→cold. Feeds `make_alt_hz_canvas()`. |
| `prepare_abundance_profile(hypatia_result)` | Converts a `compute_hypatia_data` result into bar-chart data for `make_abundance_canvas()`. Returns parallel lists `{"elements", "names", "means", "stds", "categories", "colors", "star_name"}` or `{"error": str}`; `elements` uses readable symbols (`Ba II`), `colors` is the per-element category color; filters to species with a non-None mean, preserving the `core.hypatia_elements` master display order. |
| `prepare_abundance_comparison(compare_result)` | Converts a `compare_stars` result into grouped [X/H] data for `make_abundance_comparison_canvas()`. Returns `{"star_names", "colors", "elements", "matrix"}` or `{"error": str}`; `elements` is the union of measured species across stars in master display order; `matrix[i][j]` is star j's [X/H] for element i (`None` when absent). Only stars with ≥1 non-None abundance are included. |
| `prepare_evolution_diagram(result)` | Normalizes a `compute_stellar_evolution` result for `make_evolution_canvas()`. Returns `{"stages", "current_age_gyr", "x_max_gyr", "mass_solar", "total_gyr", "ms_end_gyr", "current_stage", "low_mass", "high_mass"}` or `{"error": str}`; `x_max_gyr = max(total, current_age) × 1.1`. |
| `prepare_esi_bar_chart(result, top_n=20)` | Converts a `search_hwc` result (L2) into top-N ESI bar-chart data for `make_esi_bar_canvas()`. Returns `{"names", "esi", "habitable", "shown", "total"}` (parallel lists, highest ESI first; only numeric-ESI planets) or `{"error": str}`. |
| `prepare_hypatia_scatter(result, x_key, y_key)` | Converts a `search_hypatia_cache` result (L4) into scatter data for `make_scatter_canvas()`. `x_key`/`y_key` are from `HYPATIA_SCATTER_AXES` (fe_h, teff, logg, light_years, vmag, bv, mg_h, si_h, o_h). Returns `{"xs", "ys", "labels", "x_label", "y_label", "count"}` (only rows where both axes are numeric) or `{"error": str}`. |
| `prepare_sky_from_star(result, mag_limit=6.5)` | **Phase O O1.** Converts a stars-within result into night-sky data for `make_sky_canvas()`. Vantage = the queried centre star (opt 19) or **Sol at the origin** (opt 18, the Sol-centric result with no `center`). Each star's vector from the vantage → RA/Dec; apparent magnitude from the vantage via the distance modulus; Sol appended (M_V 4.83) **except** when the vantage *is* Sol. NULL-V-mag stars are counted in `skipped_no_mag` (never fabricated). Returns `{"vantage_name", "mag_limit", "skipped_no_mag", "stars":[{name, ra_deg, dec_deg, mag, sp_class, color}]}` or `{"error": str}`. Needs the F1 `app_magnitude`/`parsecs` row keys. |
| `prepare_hr_main_sequence()` | **Phase O O2a.** Reads `main_sequence_stars` → `{"points":[{label, teff, abs_mag, bv, lum, color}]}` (sorted hot→cool) or `{"error": str}` (empty table). |
| `prepare_hr_from_stars(result)` | **Phase O O2b.** Overlay points from a stars-within result: per star `M_V = app_magnitude + 5 − 5·log₁₀(parsecs)` (F1 keys) + Teff via the canonical `core.regions._lookup_spectral_type`. Missing mag/parsecs or non-OBAFGKM Teff → skipped + counted. Also appends a **reference anchor** flagged `"highlight"` — **Sol** for the opt-18 Sol-centric result, or the queried **centre star** for opt 19 (best-effort `star_systems` lookup via `_hr_center_point`, skipped if absent) — which the canvas draws as a gold ★. Returns `{"points":[{name, teff, abs_mag, color, sp_type[, highlight]}], "skipped": int}` or `{"error": str}`. |
| `prepare_solar_travel_diagram(result)` | Converts a `compute_travel_time_solar_objects` or `compute_travel_time_custom_thrust` result dict into solar-map viz data. Returns `{"origin_name", "dest_name", "origin_id", "dest_id", "origin_xyz", "dest_xyz", "planets", "planet_orbits", "max_au"}` or `{"error": str}`. `origin_id`/`dest_id` are Horizons IDs passed through from the core result. `planet_orbits` contains only planets whose SMA ≤ `max_au × 1.1`. |
| `prepare_mass_radius(planets, mass_key, radius_key, name_key)` | **Phase O O3.** Mass–radius scatter data, generic over NASA (`pl_bmasse`/`pl_rade`/`pl_name`) and HWC (`P_MASS`/`P_RADIUS`/`P_NAME`) rows. Filters to planets with BOTH a positive mass and radius (Earth units); the rest go in `skipped`. Returns `{"planets":[{name, mass_e, radius_e}], "skipped": int}` or `{"error": str}` when none qualify. Feeds `make_mass_radius_canvas()`. |
| `prepare_transit_geometry(planets)` | **Phase O O13.** Impact-parameter data: needs host `st_rad` (R☉; scanned across rows) + per-planet `pl_orbsmax`/`pl_orbincl`. `R★ = st_rad × 0.00465 AU`; `b = (a/R★)·cos i`. Inclination/SMA-less planets go in `skipped`. Returns `{"star_radius_au", "planets":[{name, a_au, incl_deg, b}], "skipped"}` or `{"error": str}` when `st_rad` is missing/≤0 or no planet has an inclination. Feeds `make_transit_canvas()`. (O14's size strip has **no** `prepare_*` — `make_size_comparison_canvas` consumes raw rows directly.) |
| `prepare_brachistochrone_profiles(result, n_samples=200)` | **Phase O O9.** Reconstructs each brachistochrone profile's piecewise `v(t)`/`d(t)` from `accel_g` + the per-profile total time + profile type, using the exact phase structure in `docs/calculators.md`. Auto-detects the source result shape: **opts 22/29/30** (top-level `distance_au`, profiles carry `hours`), **opt 24** (top-level shared `hours`, P1 continuous-no-decel), **opt 23** custom-thrust (single profile, no `profiles` list). Returns `{accel_g, profiles:[{label, color, t_hours, v_kms, d_au}]}` (parallel sample lists; colours fixed per index) or `{"error": str}`. Feeds `make_profile_canvas()`. |
| `prepare_exoplanet_system_diagram(planets, date_iso=None)` | Builds top-down system-map data for `NasaPlanetarySystemsMapPanel`. For each planet, solves Kepler's equation using `pl_orbtper` (epoch of periastron, JD) when present, else derives an epoch from `pl_tranmid` via `ν_tran = π/2 − ω`. When neither is available, the planet is placed at periastron and `epoch_known` is False. Orbits are coplanar 2D ellipses (Ω is never measured for exoplanets), rotated by `pl_orblper` (argument of periastron). Returns `{"orbits", "planets", "star_name", "max_au", "epoch_iso"}` or `{"error": str}`. Each orbit dict has `x_pts`/`y_pts` polylines; each planet dict has `x`/`y`/`z=0`, `epoch_known`, and an `info` field that carries the raw pscomppars row through for the click dialog. |

### System Travel Panels (`panels/system_travel.py`)

`SystemTravelSolarPanel` (22) and `SystemTravelThrustPanel` (23) both inherit `(DiagramToggleMixin, ResultPanel)`.

`build_results_area()` creates:
- `_tables_widget` — `QWidget` wrapping `_tables_layout` (a `QVBoxLayout`); all result tables and labels are added here.
- `_viz_container` + `_viz_tabs_widget` — created by `_setup_diagram_view()`.

`_input_count` is reset at the end of `build_results_area()` so `clear_results()` never destroys the persistent widget infrastructure. A module-level `_clear_tables_layout(panel)` helper (defined in `system_travel.py`) clears the `_tables_layout` between renders.

Both panels accept a **Departure Date** (`QDateEdit`, calendar popup, defaults to today) in their input form, positioned between Destination and Acceleration. The selected date is passed to the core function as an ISO string `"YYYY-MM-DD"` and surfaced as a persistent `_date_lbl` label inside the form (hidden until first successful render).

**Opt 22 result layout**: combined table (3 rows — one per profile): Acceleration Profile | Max Vel | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Total Travel Time (Hours) | Total Travel Time.

**Opt 23 result layout**: combined Phase + Summary table (4 rows — Acceleration, Coast, Deceleration, Total): Phase | Duration | Origin | Destination | Acceleration (G's) | Distance (AU) | Distance (LM) | Total Travel Time (Hours) | Total Travel Time → Burn Profile table (Req. Burn | Eff. Burn | Max Vel Cap | Max Vel Reached | Time to Max Vel | Coast Velocity) → iterations note → optional fallback note.

One diagram tab is added to `_viz_tabs_widget` when `mpl_available()` and the result contains `origin_xyz`:
- **Solar System Map** — 2D XY ecliptic view via `make_solar_travel_canvas(…, on_body_click=…)`.

Clicking any body (planet, origin, or destination) on the canvas calls `_show_body_dialog(parent, body_info)` — a non-modal `QDialog` that shows heliocentric position in the header, then fetches and displays physical properties (radius, mass, density, gravity, etc.) from JPL Horizons in a background `QThread` via `_BodyInfoWorker`. The dialog renders different field sets depending on `body_type` (`"planet"`, `"moon"`, `"asteroid"`, `"comet"`, `"unknown"`). `_DialogBridge` (a main-thread `QObject`) relays the worker's `finished` signal to the populate callback across the thread boundary. Results are cached session-wide in `core.calculators._BODY_PROPS_CACHE`. Live `(thread, worker, bridge)` triples are kept in module-level `_dialog_threads` until the OS thread exits.

**Planet position cache**: `core.calculators._fetch_planet_positions(epoch_jd)` fetches heliocentric positions for all 8 planets and caches the result for 30 minutes (`_PLANET_POS_CACHE_TTL = 1800 s`). The cache is keyed by epoch: it is only reused when the requested `epoch_jd` is within 0.02 JD (~29 min) of the cached epoch. Past or future departure dates always trigger a fresh Horizons fetch for that epoch. Each planet dict now includes a `horizons_id` field used by `_show_body_dialog`.

**`_PLANET_IDS` / `_PLANET_COLORS`**: Module-level constants in `core/calculators.py` listing the 8 planets with their Horizons IDs and display colours; also mirrored as `_PLANET_SMAS` / `_PLANET_COLORS_VIZ` in `core/viz.py` for the canvas rendering layer.

**`_fit_table_height(view)`**: Module-level helper in `system_travel.py` that sets a `QTableView` to a fixed height equal to its header plus all row heights. Fires once immediately and once via `QTimer.singleShot(0, …)` so the horizontal scrollbar's visibility is included in the final measurement.

## Phase Completion Status

| Phase | Status | Covers |
|---|---|---|
| A | Complete | Project skeleton, core stubs, GUI shell, nav tree |
| B | Complete | Static display + pure-math calculators (opts 11–16, 20–25, 33–41) |
| C | Complete | SIMBAD-based features + QThread threading pattern (opts 1, 8–10, 17–19) |
| D | Complete | Multi-source features, JPL Horizons, option 50 (opts 3–6, 26–32, 50); opts 2 and 7 implemented but not in GUI nav |
| E | Complete | Visualizations embedded in existing panels: star map 2D + 3D (18–19), orbital diagrams (3, 6), HZ diagrams (3–6, 8–10), system regions diagram (8–10), alternate HZ diagram (8–10), solar system travel map 2D (22–23); Show Diagrams/Show Tables toggle on all viz panels; light theme; 3D viewpoint preset buttons (18–19); `azel` rotation style for all 3D views |
| F | Complete | SQLite migration — all static tables auto-seeded from CSVs on first connect; opt 50 writes to `star_systems` DB table; opts 51–56 added (Export Star Systems to CSV, Import HWC, Import Mission Exocat, Import Main Sequence, Import Solar System, Import Honorverse Hyper Limits); opt 57 `DbStatusPanel` added (GUI only) — displays row counts and populated/empty status for all DB tables via `core.db.get_table_status()`; opts 18–19 migrated from `starSystems.csv` to the `star_systems` DB table in both CLI and GUI |
| post-F | Complete | **GCNS** (Gaia Catalogue of Nearby Stars): opt 58 `ImportGcnsPanel` / `import_gcns_data` ingests ~331k sources into the isolated `gcns_stars` table (+ `gcns_meta`) via GAVO TAP, plus the Gaia-resolved multiples from `gcns.resolvedss` into `gcns_systems` / `gcns_system_members` / `gcns_system_pairs` (systems = connected components over the resolvedss pairs); exposed only through `query.py` (readers `gcns-within-sol`, `gcns-source`, `gcns-system`; GCNS-backed calculators `gcns-distance`, `gcns-travel-time`, `gcns-stars-within-star`) — no existing option displays it; `get_table_status()` lists GCNS Stars + GCNS Systems + GCNS Meta. See `docs/star-databases.md` (ingest) and `docs/integration.md` (query contract). |
| G | Complete | **Interactive Search & Filtering**: "Search & Filter" nav category — `StarSystemsSearchPanel` (local `star_systems`), `HwcSearchPanel` (local `hwc`), `NasaExoplanetSearchPanel` (live NASA `pscomppars` TAP). Shared `SpectralClassControl` chips + refine box and inline drill-down detail tabs (`SearchPanelBase`). Core fns `search_star_systems` / `search_hwc` / `search_exoplanets` + `spectral_where` / `spectral_adql`. GUI panels plus `query.py` subcommands (`search-star-systems` / `search-hwc` / `search-exoplanets`, added later). See `docs/star-databases.md`, `docs/integration.md`. |
| H | Complete | **Worldbuilding Calculators** (GUI + `query.py`): "Worldbuilding" nav category — `RocheLimitPanel`, `TidalLockingPanel`, `HillSpherePanel`, `BinaryOrbitPanel`, `AtmosphereRetentionPanel` (pure math, no `DiagramToggleMixin`). Backed by five self-validating `core/equations.py` functions (`compute_roche_limit`, `compute_tidal_locking_time`, `compute_hill_sphere`, `compute_binary_orbit_stability`, `compute_atmosphere_retention`) also exposed as `query.py` subcommands (`roche-limit`, `tidal-locking`, `hill-sphere`, `binary-stability`, `atmosphere-retention`). See `docs/equations.md` (formulas + the two corrections) and `docs/integration.md` (query contract). |
| I | Complete | **Multi-System / Route Planning** (GUI; `query.py` subcommands added later — see I-OPTS): new "Route Planning" nav category — `MultiStopJourneyPanel` (I1), `NearestNeighborPanel` (I2), `TradeRoutePlannerPanel` (I3, stretch) in `panels/route_planning.py`. Backed by three new self-validating `core/calculators.py` functions (`compute_multi_stop_journey`, `compute_nearest_neighbor_chain`, `compute_trade_route_mst`) + a shared `_resolve_star_position` (DB-first → SIMBAD) and `core.viz.prepare_route_map`. Maps reuse the dark-navy **Star Chart** / **Star Chart 3D** canvases with a new additive `routes=` overlay (shared with Phase O8). See `PHASE_I_PLAN.md`, `docs/calculators.md` (Route Planning). Tests: `tests/test_route_planning.py`. *(Later given `query.py` subcommands `multi-stop` / `nearest-neighbor` / `trade-route` alongside the Phase I-OPTS pass — see below.)* |
| I-OPTS | Complete | **Route Planning — four new options** added alongside I1–I3 (none replaced): `OptimalTourPanel` (A), `FarthestFirstPanel` (D), `JumpRoutePanel` (B), `JumpNetworkPanel` (C) in `panels/route_planning.py`, paired in the nav with their siblings. Backed by four self-validating `core/calculators.py` functions (`compute_optimal_tour` NN+2-opt, `compute_jump_route` Dijkstra/BFS, `compute_jump_network` BFS tiers, `compute_farthest_first_chain`) + helpers `_SpatialGrid`/`_merge_endpoint`/`TIER_COLORS`; `core.viz.prepare_route_map` extended (A dashed+wrap / B dashed route / C tier-coloured nodes / D dashed tree). **All Route Planning options are now `query.py` subcommands**: A/B/C (`optimal-tour`/`jump-route`/`jump-network`) shipped with this pass, and `multi-stop`/`nearest-neighbor`/`farthest-first`/`trade-route` were backfilled afterwards (so the original I1/I2/I3 + D now have JSON surfaces too). No canvas change (C uses tier-coloured nodes, not a lattice — scales to large pools). B/C use a `_SpatialGrid` (not an O(n²) build) to stay usable against the ~238k-row `star_systems` table. See `PHASE_I_OPTS_PLAN.md`, `docs/calculators.md`, `docs/integration.md`. Tests: `tests/test_route_planning_opts.py`, `tests/test_query_route_opts.py`. |
| K | Complete | **Honorverse Expansion** (GUI-only): three interactive calculators in the existing "Science Fiction" nav category — `HonorverseHyperTimePanel` (K1), `HonorverseImpellerPanel` (K2, live slider), `HonorverseMissilePanel` (K3) in `panels/honorverse.py`. Backed by self-validating `core/science.py` functions (`compute_hyper_translation_time`, `compute_impeller_wedge`) + `core/calculators.py::compute_missile_intercept`, plus a K0 data-centralization refactor (the band/mass tables hoisted to module constants `_HONORVERSE_*` + `get_honorverse_*` accessors, shared by the opt-15/16 display functions — byte-identical output). The 24-band expanded speed table was corrected (Iota → canon 6000× / merchant drift fixed). Pure math, no network/DB-write. See `PHASE_K_PLAN.md`, `docs/science-and-scifi.md`. Tests: `tests/test_honorverse_expansion.py`. |
| L (L1–L3) | Complete | **Exoplanet Comparison Dashboard** (GUI; one `query.py` subcommand): new "Comparison" nav category — `StarComparisonPanel` (L1), `EsiRankingPanel` (L2), `StellarEvolutionPanel` (L3) in `panels/comparison.py`. L1 `core/databases.compare_stars` fans SIMBAD + NASA-supplement + HZ + Hypatia per star (per-star error isolation) → transposed table + grouped abundance-comparison chart (`core.viz.prepare_abundance_comparison` → `make_abundance_comparison_canvas`); later given a `compare-stars` query.py subcommand. L2 is **presentation-only over the Phase G2 `search_hwc`** (no new core fn, no `esi-ranking` subcommand). L3 `core/equations.compute_stellar_evolution` (self-validating) backs the panel + the `stellar-evolution` query.py subcommand + the timeline diagram (`core.viz.prepare_evolution_diagram` → `make_evolution_canvas`). See `docs/equations.md`, `docs/star-databases.md` (Phase L), `docs/integration.md`. Tests: `tests/test_comparison.py`. |
| L4 | Complete | **Hypatia Abundance Cache & Search** (GUI + `query.py`; verification spike passed 2026-06-14): two-table EAV cache (`hypatia_cache` / `hypatia_abundance` + `hypatia_meta` in `core/db.py`, not auto-seeded) populated by `core/databases.import_hypatia_cache` — bulk `GET /data` (8 stellar-property axes + 104 element axes, ~112 throttled calls; mean-only — `std`/`min`/`max`/`n` + UVW kinematics stay NULL; GCNS-style Gate 1/atomic-replace/Gate 2). `search_hypatia_cache` (G1/G2 helper reuse; fe_h/teff/ly/disk/element-EXISTS; pivoted Mg/Si/O) + the `search_star_systems` `fe_h` JOIN (now wired — the G1 panel's Fe/H field is live). `ImportHypatiaPanel` (Utilities, mirrors `ImportGcnsPanel`) + `HypatiaSearchPanel` (Search & Filter, `SearchPanelBase` drill-down → `SimbadPanel`, plus a selectable-X/Y **scatter "Plot" tab** via `core.viz.prepare_hypatia_scatter` → `make_scatter_canvas`) + the `search-hypatia` query.py subcommand. Live build: 14,085 stars / 244,867 abundance rows. Two L1–L3 diagram add-ons shipped in the same pass: the **L2 ESI Ranking** panel gained a top-N ESI bar chart (`prepare_esi_bar_chart` → `make_esi_bar_canvas`, now `DiagramToggleMixin`). See `PHASE_L_PLAN.md`, `docs/star-databases.md` (Phase L4), `docs/integration.md`. Tests: `tests/test_hypatia_cache.py`. |
| M | Complete | **GCNS Interactive Surfacing** (GUI-only): new "GCNS" nav category — `GcnsCensusBrowserPanel` (M1), `GcnsSourceLookupPanel` (M2), `GcnsSystemViewerPanel` (M3), `GcnsDistancePanel` (M4a), `GcnsTravelTimePanel` (M4b), `GcnsStarsWithinStarPanel` (M4c) in `panels/gcns.py`, all reusing the existing `compute_gcns_*` readers verbatim (no new core code for M1–M4). Dual name/id input with an instant-vs-background branch; M1/M4c reuse the opt-18/19 map tabs and surface the GCNS −σ/+σ distance uncertainty. **M5**: `compute_simbad_lookup` gains a non-fatal top-level `"gcns"` key (`_simbad_gcns_block`); `SimbadPanel` shows it as a "GCNS" tab; `query.py simbad-lookup` emits it with no dispatcher change. See `PHASE_M_PLAN.md`, `docs/star-databases.md` (display surfaces), and `docs/integration.md` (the `"gcns"` key). Tests: `tests/test_simbad_gcns_enrichment.py`. |
| N | Complete | **query.py Integration Expansion** (integration-surface only — no GUI/CLI/`core/`/DB changes): five new `query.py` subcommands, each a thin verbatim wrapper over an existing `core/` function — `habitable-zone-sma` (`equations.compute_habitable_zone_sma`), `star-luminosity` (`equations.compute_star_luminosity`), `brachistochrone-au` / `brachistochrone-lm` (`calculators.compute_travel_time_system_au` / `_lm`), and `travel-time-solar` (`calculators.compute_travel_time_solar_objects` — the only network-bound one, live JPL Horizons). N1–N4 wrap non-self-validating legacy functions, so out-of-range numerics surface as raw-exception `{"error": str(e)}` (exit 1); `star-luminosity` has no out-of-range error path; only `travel-time-solar` emits curated error dicts. See `PHASE_N_PLAN.md` and `docs/integration.md` ("Integration expansion (Phase N)" + the validation note). Tests: `tests/test_query_phase_n.py`. |
| O | Complete | **Visualization Expansion** (viz-layer only — additive, no computation/DB/menu changes; one exception: F1 added the additive `app_magnitude`/`parsecs` keys to the opts-18/19 result rows, surfaced in `query.py stars-within-sol`/`stars-within-star`). 18 items + F1–F3 foundations across 8 sub-phases: **O-1** F1 row-keys / F2 help-dialog (`gui/help.py`, `gui/help_text.py`) / F3 test scaffold; **O-2** Night Sky (`prepare_sky_from_star`/`make_sky_canvas`, opts 18/19) + HR diagram (`prepare_hr_main_sequence`/`prepare_hr_from_stars`/`make_hr_canvas`, opts 12/18/19); **O-3** Star-Chart interactivity (`highlight_star`/`on_star_click`/opt-in per-class `legend_filter`/`isochrone=` on the four shared map canvases — O15 row↔map link, O16 legend filter, O17 isochrone rings, O18 find-box); **O-4** Mass–Radius / Solar-overlay / Transit Geometry / Size strip (opts 3/6/Map); **O-5** Brachistochrone profiles (`prepare_brachistochrone_profiles`/`make_profile_canvas`, opts 22–24/29/30) + date scrubbers (offline exoplanet `_SystemMapScrubber`; ephemeris-batch `_SolarMapScrubber` + `compute_solar_ephemeris_track`) + two-star maps (opts 17/20/21 via Phase-I `routes=`); **O-6** Sol-region ring parity (opt 13) / solar-system orbital diagrams (opt 11) / Honorverse (opt-14 bar + opts 8/9/13 & 3/6/Map opt-in hyper-limit rings); **O-7** Toomre kinematics (`prepare_toomre`/`make_toomre_canvas`/`make_kinematics_tab` + F2 Explain dialog, opts 1/3–6/8; U/V/W LSR-corrected); **O-8** HWC habitability visuals (`prepare_hwc_temps`/`prepare_hwc_esi` + `make_hwc_temp_canvas`/`make_hwc_esi_canvas`, opt 6). See `PHASE_O_PLAN.md` (Master Matrix) and `future_phases.md`. Tests: `tests/test_viz_phase_o.py` (152). |
| P | Complete | **Snow Lines & Alternative-Solvent Habitable Zones** (GUI + `query.py`; grounds the alt-HZ table in astrobiology literature + fixes physics-failing divisors). New "Worldbuilding" panels `SolventZonePanel` (P4), `IceLineCalculatorPanel` (P5), `SolventReferencePanel` (P6) in `panels/solvent_zones.py`. Two **temperature models** centralized in `core/equations.py` (`_t_ref_surface` M1 surface / `_t_ref_equilibrium` M2 equilibrium) + the `_SOLVENTS` table; self-validating `compute_solvent_zone` (P4) / `compute_ice_lines` (P5) → the `solvent-zone` / `ice-lines` subcommands. **P1 value corrections** in `core/regions.py` (hydrogen ÷0.0000247/÷0.0000053, snowLine ÷0.04→÷0.139 = 170 K / 2.68 AU, `planetaryTemperature` `(1−A)^0.25`; lh2Line/fluorosilicone relabel-only) + **P2/P3 additive keys** (CO₂/sulfur/water-ammonia/sulfuric-acid M1 bands; CO₂/NH₃/N₂/CO M2 ice fronts) flow through opts 8–10/13 + `query.py star-regions`/`sol-regions`/`star-regions-manual`. **P7** implied-edge-T annotations + citations on the region tables. Viz: V1 (alt-HZ → 10-band ring, inner-focus + Full-range toggle), V2 (system-regions relabels), V3 (`make_solvent_zone_canvas`), V4 (`make_ice_line_canvas`), V5 (`make_solvent_bar_canvas`), V6/V7 (additive `snow_au=`/`solvent_bands=` on `make_orbits_canvas`, opt-in default-off on opts 3/6/Map). See `PHASE_P_PLAN.md`, `docs/equations.md`, `docs/star-system-regions.md`, `docs/integration.md`. Tests: `tests/test_solvent_zones.py`. |
| Q | Complete | **System Dossier Export & Reporting** (GUI + `query.py`; pure composition over existing readers — no new astronomy). New **"Reports"** nav category — `DossierExportPanel` in `panels/reports.py`. New `core/report.py` `build_system_dossier(star, sections=None, fmt="markdown")` orchestrates `compute_simbad_lookup` → regions + Kopparapu HZ + the NASA pscomppars (priority 1) + HWC (priority 2) planet catalogs + Hypatia (all species) + the M5 GCNS block into one **markdown / html / json** document. **Three-tier validation:** hard `{"error"}` (SIMBAD-fail / bad fmt / bad section), `warnings[]` (a per-source reader failed/empty — section dropped, dossier still renders), `notes[]` (by-design omission). **`--star Sol`/`Sun`** is the offline reference-origin path (`compute_sol_regions` + the real `compute_solar_system_tables` planets/dwarfs/asteroids + the `_sun_hypatia_baseline` zero-point + a GCNS-N/A note; `moons` opt-in). `fmt=json` is structured `data` only; HTML is self-contained text+tables. **Option A** (GUI-only): `DossierExportPanel` splices inline base64 HZ-ring + abundance figures into its own HTML preview/save (`query.py dossier --fmt html` stays text-only); the panel also has a **Batch** mode (newline list → one file each). One refactor: `_sun_hypatia_baseline` factored out of `_sol_compare_entry` (byte-identical, guarded by `test_comparison.py`). The `query.py dossier` subcommand. See `PHASE_Q_PLAN.md`, `PHASE_Q_MOCKUP.md`, `docs/integration.md`. Tests: `tests/test_report.py`, `tests/test_reports_panel.py`. |
| R1 | Complete | **Procedural System Generation — engine + panel** (GUI + `query.py`; first of R1/R2/R3). New **"Generator"** nav category — `SystemGeneratorPanel` (`DiagramToggleMixin`) in `panels/generator.py`. New `core/generate.py` `generate_system(seed, anchor_star=None, spectral_class=None, n_planets=None, require_habitable=False)` — **deterministic** (same seed (+ anchor) → byte-identical), two modes: **synthetic** (star from the main-sequence interpolation + `compute_star_luminosity` / `compute_habitable_zone` / `compute_ice_lines`; planets sampled, classified, T_eq via the Phase-P `implied_edge_temp`, moons between `compute_roche_limit` and `compute_hill_sphere`) and **real-anchor** (real specs via SIMBAD + `compute_star_system_regions_from_simbad`, observed planets from NASA pscomppars / HWC, synthetic infill de-conflicted against observed SMAs; multiplicity detect/warn/safe-cap). New `core/priors.py` `DefaultPriors` (the R3 seam; every synthetic field tagged `grounding=default-extrapolation`). The only new astronomy is `_classify_planet` (G3) + `_equilibrium_temp` (G4); everything else reuses verified `core/`. The `query.py generate-system` subcommand (self-validating — Phase H contract). Panel renders a Source-coloured Planet Table + Orbit Diagram / HZ Ring viz tabs + Copy JSON; **"Send to Dossier" deferred** (a later Q extension). R2 (constraint/feasibility + stability + N-body) and R3 (research-priors hook) build on this. See `PHASE_R_PLAN.md`, `PHASE_R_MOCKUP.md`/`PHASE_R_MOCKUP.html`, `docs/integration.md`. Tests: `tests/test_generate.py`, `tests/test_query_generate.py`, `tests/test_generator_panel.py`. |
| R2 | Complete | **Constraint / Feasibility Engine** (GUI + `query.py`; second of R1/R2/R3 — builds on R1, no rework). New `core/feasibility.py`: `evaluate_feasibility(...)` builds the R1 base then dispatches a **structured constraint spec** (vocab v1: `planet_at_location`/`trojan`/`moon`/`resonance` + stretch `habitable_world`/`alt_solvent_world`/`architecture`) through a **rule registry** to a **four-layer verdict per constraint** — ① stable? (new physics **G1** mutual-Hill/Gladman-Chambers packing + **G2** MMR / Gascheau co-orbital, reusing `compute_hill_sphere`/`compute_roche_limit`/`compute_binary_orbit_stability`/`compute_solvent_zone`), ② mechanism, ③ **tagged origin** (`grounding=default-extrapolation` — the R3 seam), ④ deterministic **alternatives** (`spec_patch`). Multi-star **S/P-type gate** via a spec `companion` hint; a no-hint real-anchor multiple → the R1 safe-cap + a note. New `core/nbody.py` `integrate_coplanar()` — opt-in, **pure-numpy, deterministic** KDK-leapfrog screen for **marginal** packing verdicts (`--nbody`). `generate_system` gained additive kwargs (`constraints`/`companion`/`research_policy`/`nbody`) and **delegates** when constraints are present (function-local import; **0 constraints = the R1 path, byte-identical**). `query.py generate-system` extended with a repeatable `--constraint` DSL + `--companion` + `--nbody` (no new subcommand). `SystemGeneratorPanel` extended **in place** with a constraint builder (`_ConstraintRow`) + four-layer banner/cards + **clickable-apply** alternatives. **Send to Dossier still deferred.** See `PHASE_R2_PLAN.md`, `PHASE_R2_MOCKUP.md`/`PHASE_R2_MOCKUP.html`, `docs/integration.md` (Feasibility mode). Tests: `tests/test_feasibility.py`, `tests/test_nbody.py` (+ R2 additions to `tests/test_query_generate.py`, `tests/test_generator_panel.py`). |
| R3 | Complete | **Research-Priors Hook** (GUI + `query.py`; third of R1/R2/R3 — fills the R1/R2 seam, no engine rework). New `core/research_priors.py`: a **versioned formation-priors data contract** (`docs/research-priors-contract.md`) + `validate_priors_contract` + the importer `compute_research_priors_ingest` (validate-before-store, Gate-1) + `get_research_priors_status`; storage is a cached JSON file in the gitignored `data/research_priors/` (override `SPACE_RESEARCH_PRIORS_DIR`). `core/priors.py` gains **`ResearchPriors`** (same attribute surface as `DefaultPriors` + `origin_priors`/`version`, `grounding=research-calibrated`) and the **`get_priors(research_policy)`** selector — the single swap point. `generate.py` threads `research_policy` through both synth/anchor sites + reads `priors.grounding` (the re-tag); `feasibility.py`'s Layer-3 reads `origin_priors` with **per-key heuristic fallback** (`default-extrapolation` even under strict — honest mixed tagging). **Functional `strict`:** research-calibrated when a dataset is ingested, else a curated error (no silent fallback). **`permissive` (default) is byte-identical to R1/R2** (the deep-equal determinism tests are untouched). `query.py generate-system --research-policy {permissive,strict}`; GUI `ImportResearchPriorsPanel` (Utilities) + a research-policy selector/pill in `SystemGeneratorPanel` + a `DbStatus` research-priors row. **Scaffold:** ships a synthetic SAMPLE dataset (committed `tests/fixtures/research_priors_sample.json`); real sister-project priors land later as a **data swap, not a code change**. **Send to Dossier still deferred. Phase R complete.** See `PHASE_R3_PLAN.md`, `PHASE_R3_MOCKUP.md`/`PHASE_R3_MOCKUP.html`, `docs/research-priors-contract.md`, `docs/integration.md`. Tests: `tests/test_research_priors.py` (+ R3 additions to `tests/test_generate.py`, `tests/test_feasibility.py`, `tests/test_query_generate.py`, `tests/test_generator_panel.py`). |
| S | Complete | **Project Workspaces** (campaign / novel manager — GUI + `query.py`). New top-level **"Projects"** nav category — `ProjectPanel` (master-detail) in `panels/projects.py`. Two additive, not-auto-seeded `core/db.py` tables (`projects`, `project_members`) + `core/projects.py` self-validating CRUD (create/list/get/add_member/update_note/remove/rename/delete; idempotent membership + a `" (N)"` collision suffix). A **generated** member stores its `generated_spec` JSON (not a frozen body) → re-creates **byte-identically** via `generate.generate_from_spec` (the R determinism contract). `core/report.py` gains `build_generated_dossier` (the long-deferred **R→Q "Send to Dossier"** link — renders a `generate_system` result, no re-analysis) + `build_project_dossier` (the **Export Project Dossier** fan-out: real members → Q's `build_system_dossier`, generated → `build_generated_dossier`; combined or per-file; per-member failure isolated). The panel has inline note editing, per-row Open (real → embedded `SimbadPanel`; generated → re-created view), Remove, and the export dialog (format · sections · combined-vs-per-file). **"Add to project"** entry points added to `SimbadPanel` (looked-up) + `SystemGeneratorPanel` (generated, snapshots the spec); `DbStatus` lists the two tables. `query.py` read-only `project-list` / `project-get` (mutations GUI-only). **No existing behaviour changes** (additive tables + nav category + ≤1 button per touched panel). **Phase S completes the planned roadmap (A–S; J declined).** Phases U–AK (below) are subsequent `query.py`-only extension phases for the sibling scifiWorldBuilding repo; the GUI roadmap remains complete at S. See `PHASE_S_PLAN.md`, `PHASE_S_MOCKUP.md`/`PHASE_S_MOCKUP.html`, `docs/integration.md` (Project workspaces). Tests: `tests/test_projects.py`, `tests/test_query_projects.py`, `tests/test_projects_panel.py` (+ S additions to `tests/test_report.py`). |
| T (complete) | Complete (T1 + T2 Part A + Part B) | **`query.py` Research-Tooling Extensions** (integration-surface only — **no GUI**; pure-math / local-DB additions for the sibling `scifiWorldBuilding-Claude` repo, in the Phase-N lineage). All self-validating (Phase-H/P: curated `{"error"}` exit 1 / argparse exit 2). **T1a** (near-free reuse): `trojan-stability` (wraps R2 `gascheau_coorbital_stable`), `lorentz-factor`, `circumbinary-hz` (`compute_circumbinary_hz` — lum-weighted eff-Teff, flags `out_of_range_teff`), the additive `hill-sphere` **Domingos 2006** exomoon keys (`compute_hill_sphere` gains `moon_inclination_deg`/`prograde` → `stable_fraction`/`stable_moon_limit_au`), and `gcns-within-sol --wd-prob-min/max`. **T1b** (new pure-math): `rv-semi-amplitude`/`transit-signal`/`astrometric-signal`/`direct-imaging` + `tidal-heating` (`compute_tidal_heating`, leading 21/2, order-of-mag) + `kozai-lidov` (`compute_kozai_lidov`, leading 8/15π, order-of-mag) + `relativistic-brachistochrone` + the deferred `circumbinary-hz --star1/--star2` SIMBAD-resolve mode (core fn unchanged); the three coefficients verified vs the cited papers (Peale & Cassen 1978 / Heller & Barnes 2013; Antognini 2015 / Kiseleva 1998; λ/D IWA). **T1c** (census presets): `solar-analogs` (`compute_solar_analogs` — Hypatia twin/analog box + opt-in best-effort GCNS distance join + a `population` caveat block) and `substellar` (`compute_substellar_census` — L/T/Y over `gcns_stars` by spectral-type prefix + a `completeness_note`) — both carry the population/completeness caveat **in the JSON**. No new modules, no GUI, no new datasets. **T2 Part A (dust/ISM read-only) BUILT (2026-06-23):** new `core/dust.py` (the only module importing the optional `dustmaps`/`healpy` extra, lazily; engine + `compute_dust_sightline`/`compute_dust_between`/`compute_dust_fetch`) → `query.py dust-sightline`/`dust-between` + CLI **option 59** `dust-fetch`. Output standardized to **A_V (mag, R_V=3.1)** from Leike 2020 (`leike2020`) / Edenhofer 2024 (`edenhofer2023`) via differential-density per-segment integration (auto-seam ≈ 69 pc, no inner double-count), pinned scalars (Edenhofer 2.8·E; Leike 1.0857·1.202·τ_G), native echo, quadrature σ, null+note out-of-coverage. WSL/Linux-venv-only (`requirements-dust.txt`), gated tests (`tests/_dustcheck.py` + `tests/test_dust_query.py`). **The one GUI surface:** `FetchDustMapPanel` (Utilities nav, `ImportGcnsPanel`-style download/check utility for the option-59 fetch, gated on the dust extra) — the dust *query* subcommands stay `query.py`-only. (The opt-57 `DbStatusPanel` also lists the two cached map files via the pure-pathlib `core.dust.get_dust_map_status()`, alongside the DB tables — file-presence/size, not a row count.) **T2 Part B (dust-weighted routing) BUILT (2026-06-23):** a `_grid_search` seam extracted from `compute_jump_route` (byte-identical, route tests guard it) + new `core/dust_routing.py` (5 forked planners reusing the calculators helpers + `dust.integrate_segment_av`); `query.py` `--weight {distance,dust}`/`--map`/`--dust-step-pc` on `jump-route`/`optimal-tour`/`multi-stop`/`nearest-neighbor`/`trade-route` (distance = unchanged calculators path; dust = least-A_V edges, reachability stays geometric, + a distance-optimal `extra_ly`/`saved_av` comparison). `tests/test_dust_routing.py` (12, non-gated via a mocked `_seg`). **Phase T complete.** See `PHASE_T_PLAN.md`, `docs/integration.md` (Dust / ISM). Tests: `tests/test_query_phase_t.py`, `tests/test_dust_query.py`, `tests/test_dust_routing.py`. |
| U (complete) | Complete (WD + BD grids) | **`query.py` Cooling-Primary HZ-Residence Calculator** (integration-surface only — **no GUI**; pure-math + bundled-static-table, for the sibling `scifiWorldBuilding-Claude` repo; Phase-N/T lineage). A cooling WD/BD has no equilibrium luminosity, so its HZ migrates inward as it cools. New `core/cooling.py` + `core/cooling_tables.py` (bundled **Bédard et al. 2020 / Montreal** WD sequences 0.4–1.0 M☉ + **ATMO 2020 / Phillips et al. 2020** BD tracks ~13.6–75.4 M_Jup, parsed/transcribed from the published files + closure-verified row-by-row) → one `query.py cooling-hz --track {wd,bd}` subcommand with three modes (snapshot / residence / CHZ band), reusing `compute_habitable_zone` (per-epoch band) + `compute_roche_limit` (CHZ inner-edge fluid-Roche tidal-disruption check) verbatim. Self-validating (curated `{"error"}` exit 1 / argparse exit 2). L derived from interpolated (Teff,R) via the closure (self-consistent). **Asymmetric Kopparapu gating:** hot side (>7200 K) gated (polynomial goes negative) — fixes a far-orbit false-positive; cool side (<2600 K) allowed + flagged `*_out_of_range` (gentle extrapolation, needed for cooling-dwarf residence). Reproduces Agol 2011 CHZ (~0.005–0.02 AU across 0.4–0.9 M☉) + Fossati 2012 WD residence (~8 Gyr, optimistic) + Pkt-7-R2 Roche collision + Bolmont 2011/2017 BD residence (~0.3 Gyr at 13.6 M_Jup → ~9 Gyr at 75 M_Jup). Tests: `tests/test_cooling_hz.py`, `tests/test_query_cooling_hz.py`. See `PHASE_U_PLAN.md`, `docs/integration.md` (Cooling-primary HZ). |
| V (complete) | Complete (photon + GCR) | **`query.py` Power / Thermal / Shielding Calculators** (integration-surface only — **no GUI**; pure-math + one bundled static table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 13 mission-engineering work; Phase-N/T/U lineage). Fulfils **Group F** of the calculator-extensions request — the pre-scope-lock prerequisite for Packet 13. New `core/thermal.py` (3 self-validating functions) + `core/shielding_tables.py` (bundled **NIST XCOM** photon μ/ρ grid: water/PE/Al/regolith/lead/liquid_h2/iron × 0.1–10 MeV; + order-of-magnitude **NCRP-153/NASA-HRP** GCR Λ values) → three `query.py`-only subcommands. **`waste-heat`** (F1): power → rejected-heat budget with an optional Carnot ceiling (`carnot_limited` flag). **`radiator-area`** (F2, headline): Stefan–Boltzmann thermal-rejection wall `q = ε·σ·(T⁴−T_sink⁴)·n_sides`, exposing the `A ∝ T⁻⁴` scaling + `blackside_flux_wm2` + the `T_sink→T_rad` collapse; the σ constant added to `core/equations.py`. **`shielding-attenuation`** (F3): exact Lambert–Beer photon mode (μ/ρ → transmitted fraction + HVL/TVL) and an explicitly order-of-magnitude GCR mode (`is_order_of_magnitude:true` + mandatory `buildup_caveat`). Self-validating (curated `{"error"}` exit 1 / argparse exit 2). Models the **floor physics** (radiative + attenuation limits no engineering can repeal), agnostic about mature-tech implementation. Anchors verified: 3 GW @ η=0.4 → 1.8 GW waste; 1 GW @ 300 K double-sided → ≈1.21 km² radiator; water @1 MeV → HVL ≈ 9.8 cm. Tests: `tests/test_thermal.py`, `tests/test_query_thermal.py`. See `PHASE_V_PLAN.md`, `docs/integration.md` (Power / Thermal / Shielding). |
| W (complete) | Complete | **`query.py` Rotating-Habitat Comfort Calculator** (integration-surface only — **no GUI**; pure-math + one bundled comfort-band table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 14 "Engineered Habitat Human Baseline"; Phase-N/T/U/V lineage). The in-house analog of Theodore Hall's *SpinCalc*. New `core/spin.py` (`compute_spin_comfort`) + `core/spin_tables.py` (bundled comfort-criteria bands, transcribed from the comfort-chart literature — Hill & Schnitzer 1962 / Gilruth 1969 / Gordon & Gervais 1969 / Stone 1973 / Cramer 1985, synthesized in Hall 1999 Table 1) → one `query.py`-only subcommand **`spin-comfort`**. Given **exactly two** of the four spin-state anchors {radius, spin rate, centrifugal gravity, rim tangential velocity} it solves the other two **plus** the three comfort quantities the existing `gravity-*` solves don't expose — **rim tangential velocity, head-to-foot gravity gradient, and Coriolis ratio for a walking occupant** — then classifies against tiered comfort bands (conservative/moderate/relaxed; every threshold overridable). **Extends, does not replace** `gravity-acceleration`/`-distance`/`-rpm`. Self-validating (curated `{"error"}` exit 1 / argparse exit 2 for the `--gravity-g`/`--accel-ms2` mutex + bad `--criteria`). The `_STANDARD_GRAVITY` constant added to `core/equations.py`. The bands are a human-factors **choice, not physics** (exact kinematics; a 1 % band-comparison tolerance so a nominal-1 g design isn't spuriously failed); `model_note` carries the six-study provenance + the three softest-cap footnotes. Anchors verified: 224 m @ 2 rpm → 1.0019 g / v 46.9 m/s / gradient 0.80 % / Coriolis 4.26 % (conservative PASS); 10 m @ 1 g → 9.46 rpm / gradient 18 % (all tiers fail). Tests: `tests/test_spin.py`, `tests/test_query_spin.py`. See `PHASE_W_PLAN.md`, `docs/integration.md` (Rotating-habitat comfort). |
| X (complete) | Complete | **`query.py` Closed-Loop Life-Support & Bioregenerative Calculators** (integration-surface only — **no GUI, no CLI menu, no DB, no network, no RNG**; pure-math + one bundled static reference table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 15; Phase-N/T/U/V/W lineage). New `core/life_support.py` + `core/life_support_tables.py` (bundled **NASA BVAD Rev2**, NASA/TP-2015-218570/REV2 Feb 2022, Tables 3-31/4-20/4-90/4-91, transcribed verbatim + closure scenarios + crop/lighting data; algae from ESA MELiSSA / closed-PBR literature, flagged distinct) → three `query.py`-only subcommands. **`life-support`** (X1): crew consumables/waste budget (O₂ 0.895 / CO₂ 1.085 / food 0.800 kg/CM·d / 3054 kcal / water 2.0 drink, 9.12 full-hygiene) with closure-scenario (open/iss/advanced/bioregen) makeup mass. **`bioregen-area`** (X2): grow area + optional LED power to feed a crew via a PAR energy-balance chain (`A = E_d/(PAR·η·HI·f)`; BVAD measured edible-productivity cross-check; algae take the productivity path), exactly-one-light-anchor (PPFD/DLI/PAR-W·m⁻²); PAR is a caller-supplied parameter — **`--star`/`--spectral-type` are rejected** (stellar-resolved PAR is Packet 18). **`population-capacity`** (X3): sustainable population from resource budgets (crop area / power / water / fixed-N / food), reporting the binding constraint; omitted per-person requirements filled from nominal X1/X2 runs. Self-validating (curated `{"error"}` exit 1 / argparse exit 2). Every bundled rate/efficiency overridable (Mature-Technology Assumption; `model_note` names BVAD Rev2 + the exercising-reference-astronaut caveat). **Deviation from the plan's stated η_photo=0.03:** the biomass-energy/incident-PAR default is **0.10** (RUE-derived, calibrated so the energy-balance area matches both the 30–50 m² acceptance anchor and the BVAD measured cross-check — 0.03 gave ~130 m²). Anchors verified: X1 per person/open/1 day = the Rev2 set, ISS-365 water makeup = 0.10× open; X2 2500 kcal/DLI 30/wheat → ≈ 40 m²/person (measured ≈ 37) + ≈ 7.6 kW/person artificial, algae smaller; X3 1 MW / 10 kW·person → 100 (power-bound), tight N flips the binding constraint. Tests: `tests/test_life_support.py`, `tests/test_query_life_support.py`. See `PHASE_X_PLAN.md`, `docs/integration.md` (Closed-loop life support). |
| Y (complete) | Complete | **`query.py` STL Mission Energetics** (integration-surface only — **no GUI, no CLI menu, no DB, no network, no RNG**; pure-math + one bundled fuel-preset table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 16 STL Colonization Propulsion; **Group G** of the combined settlement/propulsion/astrobiology/terraforming request; Phase-N/T/U/V/W/X lineage). Adds the **mass/energy** side of sub-light travel — `query.py` had only kinematics (`brachistochrone-*` etc.). New `core/propulsion.py` + `core/propulsion_tables.py` (bundled ideal fuel exhaust velocities) → two `query.py`-only subcommands. **`rocket-equation`** (G1): Tsiolkovsky classical `MR=exp(Δv/v_e)` + relativistic `MR=exp((c/v_e)·atanh β)` (photon `√((1+β)/(1−β))`) from any two of {velocity, exhaust, mass_ratio}; `--legs {flyby,rendezvous,round-trip}` raises the single-burn MR (MR¹/MR²/MR⁴); optional payload→propellant/wet mass. Regime chosen by the velocity form (`--beta`→relativistic, `--delta-v-kms`→classical). Bundled fuels chemical/fission-thermal/fusion-dt/fusion-catalyzed/antimatter (ideal v_e, MTA-movable). **`beam-sail`** (G2): thrust `F=(1+R)·P/c`, acceleration, optional final velocity (accel length/time), diffraction beam-range note. Self-validating (curated `{"error"}` exit 1 / argparse exit 2). `_C_MS` promoted from `core/calculators.py` to `core/equations.py` (single source; calculators re-imports). **Deviation from the plan's first draft:** `fusion-dt` bundled at **0.03c** (effective), not 0.05c — the request's own acceptance anchor (MR≈28 flyby / ~804 rendezvous at β 0.1) requires 0.03c; 0.05c gives only MR≈7.4. Documented tension with the request's looser "~0.05–0.09c ideal" prose; flag to requester on shipment. Anchors verified: Δv30/v_e30→MR≈2.718/frac 0.632; β0.1/v_e0.1c→2.73 flyby/7.44 rendezvous; β0.1/fusion-dt→28/804; photon→1.105; 100 GW reflective→F≈667 N. Tests: `tests/test_propulsion.py`, `tests/test_query_propulsion.py`. See `PHASE_Y_PLAN.md`, `docs/integration.md` (STL mission energetics). |
| Z (complete) | Complete | **`query.py` Megastructure Scale** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG**; pure-math + one bundled material/body table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 17 Settlement/Megastructure; **Group H** of the combined request; Phase-N/T/U/V/W/X/Y lineage). The **material** size limit that pairs with `spin-comfort`'s human-comfort minimum. New `core/megastructure.py` + `core/materials_tables.py` (10 materials ρ/σ + earth/mars/moon/ceres body params, researched 2026-07-02) → three `query.py`-only subcommands. **`spin-stress`** (H1): hoop stress `σ=ρv²` → max habitat radius (`--target-gravity-g`) / max gravity (`--radius-m`) / actual stress+margin (`--rpm`+`--radius-m`); `v_max=√(σ_allow/ρ)`. **`tether-taper`** (H2): Pearson uniform-stress space-elevator taper ratio `T=exp[(ρg₀/σ)(R−1.5R²/R_s+0.5R⁴/R_s³)]`, overflow→`taper_ratio:null`/`feasible:false` (normal result); **network only** for `dyson-collector --star`. **`dyson-collector`** (H3): `P=f·L`, `A=f·4πR²`, mass, incident flux (reuses the SIMBAD→luminosity resolver for `--star`). Self-validating (curated `{"error"}` exit 1 / argparse exit 2). **Researched deviations from the plan draft:** CNT/graphene bundled at literature theoretical/intrinsic strength (100/130 GPa, not the request's conservative 50 GPa), hard-flagged bulk-far-weaker; carbon-fiber clarified as raw filament. Anchors verified: steel SF1/1g→v_max≈226 m/s/r_max≈5.2 km, carbon-fiber→1580 m/s/254 km; Earth steel taper→infeasible, Earth CNT@100 GPa SF1→taper≈1.9 (canonical), graphene≈2.3; Sun f0.01/1 AU→P≈3.83e24 W/area≈2.81e21 m²/flux 1361. Tests: `tests/test_megastructure.py`, `tests/test_query_megastructure.py` (30, offline). See `PHASE_Z_PLAN.md`, `docs/integration.md` (Megastructure scale). |
| AA (complete) | Complete | **`query.py` PAR / Photosynthesis by Stellar Type** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time**; pure-math, for the sibling `scifiWorldBuilding-Claude` repo's Packet 18 Astrobiology; **Group I** of the combined request; Phase-N/T/U/V/W/X/Y/Z lineage). One `query.py`-only subcommand **`par-flux`** answering the *natural-light* / red-dwarf photosynthesis-deficit question — PAR (~400–700 nm) is a spectral-type-dependent *fraction* of a star's output; its **PPFD output feeds back into Phase-X `bioregen-area`** (which takes PAR as a caller-supplied input). New `core/par_flux.py` (`compute_par_flux`) — **no bundled table**: the SED is computed from the **Planck function** (blackbody at Teff, flagged an approximation in `sed_model`/`model_note`) integrated 400–700 nm over the Stefan–Boltzmann total; PPFD via the band-mean photon energy (~0.219 J/µmol); deficit vs G2 = f_PAR(5772)/f_PAR(Teff). **Teff — exactly one of** `--teff-k` (offline) / `--spectral-type` (→ `main_sequence_stars` ceiling rule, offline) / `--star` (→ SIMBAD + regions, **the only networked path**); **insolation — exactly one of** `--insolation-wm2` / (`--luminosity-lsun` + `--distance-au`). Three new constants in `core/equations.py` (`_PLANCK_H`, `_AVOGADRO`, `_SOLAR_LUMINOSITY_W`); reuses Phase-Y's `_C_MS`, `_K_B`, `_STEFAN_BOLTZMANN`, `_M_PER_AU`. Self-validating (curated `{"error"}` exit 1 / argparse exit 2). **Deviation from the plan's stated anchors:** the plan's M-dwarf band (f_PAR 0.04–0.07 / deficit 6–10 at "3000 K") is a **real-SED** figure; under the mandated **blackbody** SED a 3000 K blackbody correctly gives f_PAR≈0.081/deficit≈4.5, and that band is reproduced at **Teff≈2700 K** (a late-M dwarf) — the tests anchor there and `model_note` documents that blackbody is *optimistic* for red dwarfs (real line-blanketed SEDs give a *larger* deficit). Anchors verified: Sun (5772 K) → f_PAR≈0.366, at 1361 W/m² → PAR≈499 W/m² / PPFD≈2277 µmol·m⁻²·s⁻¹ / J/µmol=0.219 (cross-check exact); late-M (2700 K) → f_PAR≈0.050 / deficit≈7.3; 1 L☉@1 AU → S≈1361 W/m². Tests: `tests/test_par_flux.py`, `tests/test_query_par_flux.py` (21, offline; `--star` reachability-gated). See `PHASE_AA_PLAN.md`, `docs/integration.md` (PAR / photosynthesis). |
| AB (complete) | Complete | **`query.py` Planetary Energy Balance / Terraforming** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time, no network**; pure-math, for the sibling `scifiWorldBuilding-Claude` repo's Packet 19 Planetary Transformation / Terraforming; **Group J** of the combined request — **the final group, completing it**; Phase-N/T/U/V/W/X/Y/Z/AA lineage). Three `query.py`-only subcommands modelling the terraforming **radiative/mass balance** (demand side only — volatile *supply* is the volatile-geography canon's authority). New `core/terraforming.py` — **no bundled table**: reuses `_STEFAN_BOLTZMANN`/`_M_PER_AU`/`_G`/`_EARTH_MASS_KG`/`_SOLAR_LUMINOSITY_W` from `core/equations.py` + one inline `_EARTH_ATM_MASS_KG = 5.15e18`. **`equilibrium-temp`** (J1): `T_eq=[S(1−A)/4σ]^¼` + a greenhouse surface temp via one forcing form — additive offset `T_eq+ΔT` / grey-atmosphere `T_eq(1+¾τ)^¼` / **inverse** (`--target-surface-k` → required ΔT & τ, with a `cooling_required` flag when the target is below equilibrium). **`insolation-shift`** (J2): orbital mirror/shade area `A_m=|ΔS|·4πR²/solar_flux` (signed ΔS → `mode` mirror/shade). **`atmosphere-mass`** (J3): hydrostatic `m=4πR²P/g` ↔ `P=mg/4πR²` (g from `--planet-mass-earth` if not given; `--species` an echoed label — column mass is species-independent). The `--luminosity-lsun`+`--distance-au`→S conversion is shared with Phase-AA `par-flux`. Self-validating (curated `{"error"}` exit 1 / argparse exit 2). Anchors verified: Earth (S1361/A0.3)→T_eq≈255 K, +Δ33→288 K (τ≈0.85 reproduces 288); Mars (S589/A0.25)→T_eq≈210 K; Mars 1 bar (R3390/g3.71)→m≈3.9e18 kg (~0.76 Earth atm), P round-trips, g-from-mass 3.711. Tests: `tests/test_terraforming.py`, `tests/test_query_terraforming.py` (22, offline). See `PHASE_AB_PLAN.md`, `docs/integration.md` (Planetary energy balance / terraforming). |
| AC (complete) | Complete | **`query.py` ISM-Drag / Magnetic-Sail Calculators** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time, no network**; pure-math + one bundled ISM/fusion constant table, for the sibling `scifiWorldBuilding-Claude` repo's Packet 16 STL Colonization Propulsion; **Group K** of the combined request — the magnetic interaction of a vehicle with the ISM, the one scope-shaping STL gap Groups G–J did not enumerate; Phase-N/T/U/V/W/X/Y/Z/AA/AB lineage). Complements Group G (`rocket-equation`/`beam-sail`) and the `dust-*` column tools. Two `query.py`-only subcommands. New `core/ism_drag.py` + `core/ism_drag_tables.py` (isolated bundled constants, like `core/propulsion_tables.py`); `_MU_0`/`_M_PROTON` added to `core/equations.py`. **`magsail`** (K1): magnetic-sail braking — magnetopause standoff `R_mp=[μ₀m_dip²/(8π²kρv²)]^(1/6)` → drag `F=C_d·½ρv²·πR_mp²` (∝ v^(4/3)) → deceleration + optional single-law stopping distance/time. **`ramscoop`** (K2): Bussard ramjet drag-vs-thrust verdict `F_net=ṁ(v_e−v)−F_drag` → "drive"/"brake" + crossover `v_e/(1+C_d/2)` (the Zubrin & Andrews "brake not drive" result as a swept recompute). Self-validating (curated `{"error"}` exit 1 / argparse exit 2). ISM density is a caller parameter, never re-derived (defaults flag to the sibling Local-Interstellar-Environment packet: n 0.1 cm⁻³ LIC, ion mass 1.3 amu); every output carries an `ionization_note` (the LIC is only ~22% ionized → "fully ionized" overestimates the interacting density ~4×). Coefficients web-confirmed 2026-07-02: C_d=1.0 (Zubrin & Andrews explicit), k=1.0 (simple pressure balance; compressed factor f=2/2.44 documented), fusion p-p/CNO 0.71% / D-D 0.38% (reconciled down from the request's 0.43% — flagged), η 0.1 low (ideal η=1 → pp v_e≈0.12c). Anchors verified: K1 n0.1/β0.1/R_coil 1e5/I 1e5 → R_mp≈101 km, drag≈2.38 kN, a≈2.4e-3 m/s² @10³ t, β-halving ~2^(4/3)≈2.52×; K2 pp@β0.1 → brake (even the ideal η=1 v_e>v margin is flipped by drag), low-β+high-η → drive. Tests: `tests/test_ism_drag.py`, `tests/test_query_ism_drag.py` (32, offline). See `PHASE_AC_PLAN.md`, `docs/integration.md` (ISM drag / magnetic sail). |
| AD (complete) | Complete (all 5 phases; 15 items shipped, C12 declined) | **`query.py` Calculator-Completeness Follow-ups** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time**; **`active-shield`/`dust-impact`/`orbital-ring`/`volatile-delivery` offline, no new network**; a completeness sweep over Packets 16–19 vs the built `query.py`, per the "implement everything, no v2 hedges" instruction). All self-validating (curated `{"error"}` exit 1 / argparse exit 2). **Phase 1 (2026-07-03):** **B** `equilibrium-temp` bare airless T_eq (0 forcing forms → `regime:"airless"`); **A1/A2/A3** `magsail` exact on-axis loop-field standoff + reworded stopping note + `--ionization-fraction` on `magsail`/`ramscoop`; **C6/C7/C9** `shielding-attenuation --particle` (NIST PSTAR CSDA range) + `--layers` stacks + `waste-heat` transient mode; **C8** new `core/active_shield.py` (`active-shield` — Störmer rigidity cutoff). **Phase 2:** **C2** `pellet-stream` (`core/propulsion.py` — momentum-beam drive, the mass analog of `ramscoop`); **C3** new `core/dust_impact.py` (`dust-impact` — grain impact energy/momentum/TNT + fluence, penetration handed off to Pkt-13 shielding). **Phase 3:** **C4** `orbital-ring` (`core/megastructure.py`, bundled `_BODIES`); **C5** new `core/volatile_delivery.py` (`volatile-delivery` — cometary-bombardment supply side; composes `rocket-equation` + ½mv²). **Phase 4:** **C10** `bioregen-area --crops` diet mix; **C11** `jump-route --weight blend` (α·distance + β·A_V, jump-route only); **C1** `par-flux --sed real` — new `core/par_flux_tables.py` `_REAL_SED_FPAR` **computed at build from the BT-Settl (CIFIST2011) grid via the SVO Theoretical Spectra service** (log g 4.5, [M/H] 0, 2600–7000 K). **Two user decisions (2026-07-03):** C1 default stays `--sed blackbody` (backward-compatible; plan said "real"), and C1 sourced by computing from the BT-Settl grid. **Declined:** C12 (spin-comfort vestibular — DECLINED, Pkt-14 scope-lock). **Phase 5 (2026-07-03): A0** `cooling-hz --cooling-delay-gyr`/`--distillation-teff-k` (`core/cooling.py`) — the WD-only ²²Ne distillation cooling pause: a wall-clock→track-age warp (`_warp_age`) freezes (Teff,L,R) at the distillation onset (default **5500 K**, Vanderburg+2025 arXiv:2501.06613) for the delay, lengthening HZ residence + pushing the long-residence CHZ outward; **Δt=0 byte-identical** to Phase U; peak residence 6.3→16.3 Gyr at Δ=10 (their Table 1: 6.67→15.56). Tests: `test_active_shield`/`test_dust_impact`/`test_volatile_delivery` (+ `test_query_*`), and extensions to `test_thermal`/`test_ism_drag`/`test_propulsion`/`test_megastructure`/`test_terraforming`/`test_life_support`/`test_dust_routing`/`test_par_flux`/`test_cooling_hz` (+ their `test_query_*`). Full offline suite (under `venv/bin/python`) **1381 passed / 1 skipped**. **Phase AD complete.** See `PHASE_AD_PLAN.md`, `docs/integration.md`. |
| AE–AI (complete) | Complete (all 5 groups; 28 subcommands) | **`query.py` Exotic-Physics / Relativity / FTL / Black-Hole track** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time, no network, no numpy**; closed-form physics on fundamental constants, for the sibling `scifiWorldBuilding-Claude` repo's Packets 20–24; five groups K–O of `exotic-physics-relativity-ftl-calculators-request.md`; Phase-N/T/U…AD lineage). All self-validating (curated `{"error"}` exit 1 / argparse exit 2), every object carries a `model_note`, every bundled constant flag-overridable. **Phase 0** — CODATA constants added to `core/equations.py` (ℏ, m_e, e, ε₀, σ_T, l_p, M_jup, R_sun/jup, Mpc, H₀, Ω_Λ/Ω_m) + shared `core/astro_bodies.py` (multi-unit mass/radius gate + body/object presets incl. Sgr A*/M87*/TON 618). **AE / Group K** `core/gravitation.py` — `escape-velocity`/`gravitational-potential`/`sphere-of-influence`/`hyperbolic-approach` (arrival/departure energetics). **AF / Group L** `core/relativity.py` — `time-dilation`/`length-contraction`/`velocity-addition`/`relativistic-doppler`/`rapidity`/`relativistic-energy-momentum`/`lorentz-transform` + `causality-check` (the tachyonic-antitelephone / preferred-frame FTL loop-safety guardrail); extends the `lorentz-factor` seed. **AG / Group M** `core/exotic_physics.py` — `casimir`/`vacuum-energy`/`schwinger-limit`/`hubble-flow`. **AH / Group N** `core/warp.py` — `alcubierre-energy` (`original` = plain-Python Simpson T⁰⁰ integral hitting −3.37×10⁴⁵ J (≈ −3.75×10²⁸ kg-equiv) @R100/v_s c/Δ10, ∝1/Δ; six reduction formulations van-den-broeck…lentz **report** published figures/sources + the Santiago–Schuster–Visser NEC regime flag) + `warp-metric` (tanh shape fn, expansion scalar θ, Natário zero-expansion variant); built in 3 checkpoints with an independent literature-ladder verification pass. **AI / Group O** `core/black_hole.py` — `schwarzschild-radius`/`hawking-temperature`/`black-hole-evaporation`/`bekenstein-hawking-entropy`/`isco` (Kerr Bardeen-Press-Teukolsky)/`kerr-horizon`/`bh-tidal-force`/`eddington-luminosity`/`unruh-temperature`/`bekenstein-bound`. Every corrected acceptance anchor from the spec's verification pass is a golden-pin dual-runner test; full offline suite **1608 passed / 1 skipped**; query.py stays numpy-free. Tests: `test_astro_bodies`, `test_gravitation`/`test_query_gravitation`, `test_relativity`/`test_query_relativity`, `test_exotic_physics`/`test_query_exotic_physics`, `test_black_hole`/`test_query_black_hole`, `test_warp`/`test_query_warp`. See `PHASE_AE_PLAN.md` (§7a checkpoints + Definition of Done), `docs/integration.md` (five § "Arrival geometry…" / "Special relativity…" / "Exotic vacuum…" / "Alcubierre…" / "Black holes…"). |
| AJ (complete) | Complete (Group P; 6 subcommands) | **`query.py` Planet-Formation Calculators** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time, no network, no numpy**; closed-form on the F1–F6 claim-map pins, for the sibling `scifiWorldBuilding-Claude` repo's Packet 3.5; **Group P** of `formation-calculators-request.md` + the frozen `formation-calculators-followup-1.md` golden-pin rulings; Phase-N/T/U…AI lineage). All self-validating (curated `{"error"}` exit 1 / argparse exit 2), every object carries a `model_note`, every bundled constant flag-overridable. New `core/formation.py`; `_MU_GAS_DEFAULT=2.34` + `_Z_SUN=0.0134` added to `core/equations.py`. Built in two stages — **AJ-1 core** (P1 `disk-model` MMSN-scalable Σ_gas/Σ_solid/T/(H-r) profile [defaults reproduce Approved-Canon MMSN exactly; snow line solved from its **own** T-law → 2.71 AU at L=1/170 K ∝ L^½, no `ice-lines` import — followup-1 Ruling 2] + P2 `isolation-mass` [Armitage Eq. 201, both feeding-zone conventions]) then **AJ-2** (P3 `pebble-isolation-mass` [Bitsch 2018], P4 `gap-opening-mass` [Crida 2006 Eq. 15, pure-Python bisection for the marginal-threshold q — followup-1 Ruling 1a: headline = solved threshold 0.52 M_Jup via `--nu-code 3.162e-6`, criterion check P(1e-3)=0.699], P5 `toomre-q` [Armitage Eq. 164], P6 `critical-core-mass` [Ikoma+2000]). The disk+mass spine the generator's `mass_by_zone`/`spacing_ratio`/`origin_priors` derive from; calculators chain (disk-model emits `sigma_solid`/`temp_k`/`aspect_ratio_hr` for the others, also accepted as direct flags). Every acceptance anchor + both rulings are golden-pin dual-runner tests; full offline suite **1645 passed / 1 skipped**; query.py stays numpy-free. Tests: `test_formation`/`test_query_formation` (37, offline). See `PHASE_AJ_PLAN.md`, `docs/integration.md` (Planet formation). |
| AK (complete) | Complete (Group Q; 2 subcommands) | **`query.py` Metric-Drive Power/Fuel + Exclusion-Boundary Calculators** (integration-surface only — **no GUI, no CLI menu, no DB (except the local main-sequence table on `exclusion-boundary --spectral-type`), no RNG, no time, no numpy; network only on `exclusion-boundary --star`**; for the sibling `scifiWorldBuilding-Claude` repo's Packets 25 / 26.5 — **Group Q** of `metric-drive-power-and-exclusion-boundary-calculators-request.md`, built as one group with **no phasing / no v1-v2** per user directive 2026-07-12; Phase-N/T/U…AJ lineage). Both self-validating (curated `{"error"}` exit 1 / argparse exit 2), every object carries a `model_note` with the two load-bearing caveats (Q1 = **subluminal/STL-mode law only**; Q2 = **Rung-3 in-universe dial**, not physics), every bundled constant flag-overridable. New `core/metric_drive.py` (**Q1 `metric-drive-power`** — field-rocket `P_rad=k·F·c` [k=3 GR baseline ≈0.9 GW/N; k<3 = the B2 exotic discount, never 0], radiated-mass fraction `f_rad=1−e^(−kΔη)`, per-fuel `fuel_mass_fraction=f_rad/f_conv` with `f_conv=f×η_dir` [local `_FIELD_FUEL`; pp/dd f-values **imported from `core/ism_drag_tables.py` `_FUSION`** for DRY; antimatter's f=1 separated from η_dir≈0.5], the beam-vs-onboard crossover [onboard wins only if k<0.5], F=0 hold-cruise ⇒ zero power) + `core/exclusion_boundary.py` (**Q2 `exclusion-boundary`** — FTL "Alcubierre Limit" `r_ex=DIAL·(M/M☉)^α·(L/L☉)^β·(Ẇ/Ẇ_☉)^γ`, auto-calibrated so r_ex(Sun)=the Kuiper-edge anchor 47.5 AU unless `--dial` set; α mass-exponent canon [1/3,1/2] default 1/3 [`--scan-alpha` reports both edges], β/γ luminosity/wind default off; graded-forcing class harbor/checkpoint/optional — provisional bands, Pkt-26.5-owned). All 13 acceptance anchors + the error matrix + a beam-sail reflecting-sail cross-check are golden-pin tests; full offline suite **1682 passed / 1 skipped**; query.py stays numpy-free. Tests: `test_group_q` (36, offline). See `PHASE_AK_PLAN.md`, `docs/integration.md` (Metric-drive power & exclusion boundary). |
| AL (complete) | Complete (Group R; 12 subcommands) | **`query.py` Power Generation / Storage / Thermal Calculators** (integration-surface only — **no GUI, no CLI menu, no DB, no RNG, no time, no network, no numpy**; pure-math floor physics, for the sibling `scifiWorldBuilding-Claude` repo's Packet 27 — **Group R** of `power-generation-storage-thermal-calculator-request.md`; note the requester's "Group R" maps to repo **Phase AL** because Phase R is the procedural generator; Phase-N/T/U…AK lineage). All self-validating (curated `{"error"}` exit 1 / argparse exit 2), every object carries a `model_note`, every bundled row/constant flag-overridable; load-bearing `[pin @ open]` values flagged un-promoted. New `core/power.py` (**R1 `annihilation-power-train`** directed/γ/ν partition; **R2 `antimatter-production`** production floor 2m_p/6m_p=0.333 + Brillouin ε₀B²/2 storage ceiling, `--production-efficiency` un-defaulted H-25-1 input; **R4 `reactor-net-power`** Q-gate net-energy; **R7 `beamed-power-delivery`** diffraction λL/D wall; **R10 `fusion-lawson`** triple-product→Q, general-power scope guard), `core/energy_storage.py` (**R8 `flywheel-storage`** K·σ/ρ; **R9 `smes-storage`** B²/2µ₀ + structure-limited σ/ρ), `core/thermal.py` (**R3 `heat-pump`** Carnot COP, the inverse of `waste-heat`), `core/power_tables.py` (**T1 `energy-storage`** `_STORAGE` battery/chemical/thermal + sensible/latent compute; **T2 `reactor-power`** `_REACTOR_SPECIFIC_POWER` α=P/m + mandatory thermal pointer). **R5** adds fission `f` rows (`_FISSION`: u235 9.14e-4, pu239 9.3e-4) to `core/ism_drag_tables.py`; **R6** extends `metric-drive-power` with `--self-consistent` (`--ash {keep,vent}` — the Packet-25 feasibility wall `X=(1−e^(−kΔη/η_dir))/f`, `k_wall`, `lifetime_delta_v_budget_kms`; fulfils `metric-drive-power-followups.md`). `_MEV_J`/`_MP_C2_MEV` added to `core/equations.py`. Every acceptance anchor + the R6 followups' 7 anchors + error matrix are golden pins; full offline suite **1762 passed / 1 skipped**; query.py stays numpy-free. Tests: `test_power`/`test_query_power` (R1/R2/R4/R7/R10), `test_energy_storage` (R8/R9), `test_power_tables` (T1/T2), `test_thermal` (R3), `test_group_q` (R6), `test_ism_drag` (R5). See `PHASE_AL_PLAN.md`, `docs/integration.md` (Power generation / storage / thermal). |
