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
  db.py              # SQLite connection (Phase F); get_table_status() returns row counts for all app tables

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
                         #   ImportGcnsPanel (58), ImportHypatiaPanel (Phase L4)
    search_common.py     # Phase G: SpectralClassControl, SearchPanelBase (inline drill-down tabs)
    search.py            # Phase G: StarSystemsSearchPanel (G1), HwcSearchPanel (G2),
                         #   NasaExoplanetSearchPanel (G3); Phase L4: HypatiaSearchPanel
    gcns.py              # Phase M: GcnsCensusBrowserPanel (M1), GcnsSourceLookupPanel (M2),
                         #   GcnsSystemViewerPanel (M3), GcnsDistancePanel (M4a),
                         #   GcnsTravelTimePanel (M4b), GcnsStarsWithinStarPanel (M4c)
    route_planning.py    # Phase I: MultiStopJourneyPanel (I1), NearestNeighborPanel (I2),
                         #   TradeRoutePlannerPanel (I3, stretch); route-overlay Star Chart tabs
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
| `DbStatusPanel` | 57 (GUI only) | `panels/csv_utility.py` |
| `ImportGcnsPanel` | 58 | `panels/csv_utility.py` |
| `ImportHypatiaPanel` | — (GUI-only, Phase L4) | `panels/csv_utility.py` |
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

Three map canvases are added to `_viz_tabs_widget` and are only visible in diagram mode: "Map X–Y (top-down)", "Map X–Z (edge-on)", and "Map 3D". The 3D tab includes three Qt viewpoint preset buttons (Top View, Side View, 3D Perspective) above the matplotlib toolbar. All three canvases use a light gray background (`bg="#ebebeb"`) rather than the default `#f5f5f5`.

## Phase E Visualization Integration

Phase E adds matplotlib-based visualizations embedded inside existing option panels. All diagrams are accessed via the **Show Diagrams** button (see `DiagramToggleMixin` above) — they are hidden by default and expand to fill the window when activated. No new top-level nav entries were created.

### Shared rendering layer (`gui/visualizations/plot_helpers.py`)

`mpl_available()` returns `True` when `matplotlib` and `PySide6` are both importable. All viz-tab code is guarded by this check so the app works without matplotlib installed.

All canvas helpers return `(FigureCanvasQTAgg, NavigationToolbar2QT)`. Figures use a light theme (`facecolor="#f5f5f5"`, labels `#333333`, grid `#cccccc`).

| Helper | Panels that use it | Output |
|---|---|---|
| `make_hz_canvas(parent, zones, max_au, title, eeid_au)` | NASA opts 3–5, HWC (6), Star Regions 8–10 | Concentric ring HZ diagram; optional EEID circle |
| `make_orbits_canvas(parent, orbits, hz_zones, max_au, star_name, eeid_au, markers, solar_overlay=False, title=None, km_axis=False, hyper_au=None)` | NASA opts 3, 6, Map panel; Solar System (11) — Phase O O7 | Keplerian orbital ellipses with HZ annulus overlay. **Phase O O4** `solar_overlay=True` (additive): dashed grey reference circles at the Solar planets' SMAs (`core.viz._PLANET_SMAS`) that fit `max_au×1.1`, with end-of-orbit labels (drawn under the planet orbits); default `False` → byte-identical to before. Driven by the `wrap_orbits_with_solar_toggle` checkbox. **Phase O O7** (additive): `title` overrides the "Planetary Orbits" diagram title; `km_axis=True` adds a secondary top x-axis in km (AU × 1.496e8) for moon-system diagrams; both default off → byte-identical. **Phase O O10b** (additive): `hyper_au` > 0 draws a dashed-red Honorverse hyper-limit ring at that AU (expanding the frame to fit it); default `None` → byte-identical. |
| `make_star_map_canvas(parent, stars, title, xk, yk, xlabel, ylabel, bg)` | Stars Within Distance 18, 19 | 2D scatter, spectral-class colours, hover annotation; `bg` overrides figure background colour |
| `make_star_map_3d_canvas(parent, stars, title, bg)` | Stars Within Distance 18, 19 | 3D scatter with drag-to-rotate (`azel` rotation style); returns `(canvas, toolbar, ax)` so caller can bind viewpoint preset buttons; `bg` overrides figure background colour; rectangle Zoom button removed from toolbar; scroll wheel zoom wired via `ax._zoom_data_limits()`; `toolbar.push_current()` called at creation so Home restores initial view; hover tooltip at upper-right to avoid the spectral class legend |
| `make_star_chart_canvas(parent, stars, limit_ly, routes=None)` | Stars Within Distance 18, 19; Route Planning (Phase I) | Labeled X–Y star chart in the dark navy palette of `generate_star_map_html.py`; no title; scaled grid/major-tick/distance-ring intervals; per-star `"Name (Z=±X.XXX)"` labels anchored with a **fixed pixel offset** (`annotate(textcoords="offset points")`, so labels track their dots on zoom rather than drifting) plus screen-space collision-nudging and a `path_effects` stroke for readability; **all in-plot text (star/Sol labels + axis tick numbers, axis titles, and ring `N ly` labels) uses `clip_on=True`** (with `annotation_clip=True` on the annotations) so nothing leaks into the black margin when panned/zoomed — only the axes-fraction click-info box stays unclipped; center star drawn as a gold ★ at the origin (Sol for opt 18, queried star for opt 19); hover tooltip, click info box, scroll-wheel zoom around cursor; `toolbar.push_current()` seeds Home; xlim/ylim callbacks toggle label visibility based on a 15 ly half-range threshold. **Phase I `routes=`** (optional, additive): a list of `{x1,y1,z1,x2,y2,z2,label,style}` edge dicts drawn over the dots — dashed for ordered legs / solid (`_SC_MST`) for MST edges; route lines stay visible at all zooms while the per-segment labels follow the same zoom-driven decluttering as the star labels. Existing opt-18/19 callers pass no `routes` and are unaffected. **Shared with Phase O8.** |
| `make_star_chart_3d_canvas(parent, stars, limit_ly, routes=None)` | Stars Within Distance 18, 19; Route Planning (Phase I) | 3D companion to `make_star_chart_canvas` (same additive `routes=` overlay): dark navy panes + grid, gold ★ center marker, spectral-class star dots, per-star `"Name (Z=±X.XXX)"` labels **anchored at each star's exact 3D point with left/bottom alignment** (so they track the dot on rotation and zoom instead of drifting on a fixed data-space offset), zoom-driven via `xlim_changed`/`ylim_changed`/`zlim_changed` against `max((x1-x0)/2, (y1-y0)/2, (z1-z0)/2) ≤ 15 ly`; faint wireframe reference spheres at every `major_step` ly out to the limit; hover tooltip + click info (text2D pinned upper-right / lower-left); `azel` drag rotation; scroll-wheel zoom via `ax._zoom_data_limits`; rectangle Zoom removed from the toolbar; returns `(canvas, toolbar, ax)` so caller can bind viewpoint preset buttons (Top / Side / 3D Perspective) |
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

**3D hover tooltip**: The hover `text2D` is positioned at `(0.98, 0.97)` with `ha="right"` (upper-right corner) so it does not overlap the spectral class legend, which occupies `loc="upper left"`.

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
| `StarsWithinDistanceSolPanel` (18) | "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D", "Star Chart", "Star Chart 3D", "HR Diagram" (Phase O O2b), "Night Sky" (Phase O O1 — vantage = Sol) | `DiagramToggleMixin` |
| `StarsWithinDistanceStarPanel` (19) | "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D", "Star Chart", "Star Chart 3D", "HR Diagram" (Phase O O2b), "Night Sky" (Phase O O1 — mag-limit re-runnable) | `DiagramToggleMixin` |
| `DistanceBetweenStarsPanel` (17) | "Star Chart", "Star Chart 3D" (Phase O O8 — two-star map via Phase I `routes=`) | `DiagramToggleMixin` |
| `TravelTimeStarsLyHrPanel` (20) / `TravelTimeStarsTimesCPanel` (21) | "Star Chart", "Star Chart 3D" (Phase O O8 — edge labelled with distance + travel time + ×c) | `DiagramToggleMixin` |
| `SystemTravelSolarPanel` (22) | "Solar System Map" (+ Phase O O5b date scrubber), "Acceleration Profiles" (Phase O O9) | `DiagramToggleMixin` |
| `SystemTravelThrustPanel` (23) | "Solar System Map" (+ Phase O O5b date scrubber), "Acceleration Profiles" (Phase O O9 — single custom-thrust profile) | `DiagramToggleMixin` |
| `BrachistochroneAccelPanel` (24) / `BrachistochroneAuPanel` (29) / `BrachistochroneLmPanel` (30) | "Acceleration Profiles" (Phase O O9) | `DiagramToggleMixin` |
| `StarComparisonPanel` (L1) | "Abundance Profiles" (when ≥1 star has abundances) | `DiagramToggleMixin` |
| `EsiRankingPanel` (L2) | "ESI Chart" (top-N planets-by-ESI bar chart) | `DiagramToggleMixin` |
| `StellarEvolutionPanel` (L3) | "Evolution Diagram" | `DiagramToggleMixin` |
| `HypatiaSearchPanel` (L4) | "📈 Plot" (selectable X/Y scatter of the result set) | `SearchPanelBase` closable detail tab (X/Y dropdowns + "Show Plot") |

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
