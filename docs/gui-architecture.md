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

core/                # Pure computation layer — no I/O, no Qt
  __init__.py
  calculators.py     # Speed, distance, travel time functions
  databases.py       # SIMBAD and archive query functions
  equations.py       # Planetary, habitat, HZ, luminosity equations
  regions.py         # Star system region calculations
  science.py         # Solar system data, main sequence, Honorverse tables
  shared.py          # Shared helpers (format_travel_time, etc.)
  viz.py             # Visualization data-prep (Phase E): star map, orbits, HZ, regions
  db.py              # SQLite connection (Phase F)

gui/                 # Qt presentation layer
  app.py             # MainWindow: QSplitter with nav tree + QStackedWidget
  nav.py             # NAVIGATION list + populate_nav(); maps labels → panel class names
  panels/
    __init__.py      # Exports all panel classes by name; lazy __getattr__ for viz panels
    base.py          # ResultPanel base class; Worker + run_in_background (Phase C+);
                     #   DiagramToggleMixin (Phase E+)
    # Phase B panels (no network calls):
    science_tables.py     # SolarSystemPanel (11), MainSequencePanel (12)
    sol_regions.py        # SolRegionsPanel (13)
    honorverse.py         # HonorverseHyperPanel (14), HonorverseAccelPanel (15),
                          #   HonorverseSpeedPanel (16)
    velocity.py           # VelocityLyHrPanel (20), VelocityTimesCPanel (21)
    distance.py           # DistanceLyHrPanel (22), DistanceTimesCPanel (23)
    travel_time.py        # TravelTimeLyHrPanel (24), TravelTimeTimesCPanel (25)
    orbit_calc.py         # OrbitPeriastronPanel (33), MoonDistance24Panel (34),
                          #   MoonDistanceXPanel (35)
    rotating_habitat.py   # GravityAccelPanel (36), GravityDistancePanel (37),
                          #   GravityRpmPanel (38)
    habitable_zone_calc.py # HabZonePanel (39), HabZoneSmaPanel (40)
    luminosity.py         # LuminosityPanel (41)
    # Phase C panels (SIMBAD / network):
    simbad.py            # SimbadPanel (1)
    star_regions.py      # StarRegionsAutoPanel (8), StarRegionsSemiManualPanel (9),
                         #   StarRegionsManualPanel (10)
    distance_stars.py    # DistanceBetweenStarsPanel (17), StarsWithinDistanceSolPanel (18),
                         #   StarsWithinDistanceStarPanel (19)
    # Phase D panels (multi-source / JPL Horizons):
    nasa_exoplanet.py    # NasaPlanetarySystemsPanel (3), NasaHwoExepPanel (4),
                         #   NasaMissionExocatPanel (5)
    catalogs.py          # HwcPanel (6)
    travel_time_stars.py # TravelTimeStarsLyHrPanel (26), TravelTimeStarsTimesCPanel (27)
    brachistochrone.py   # BrachistochroneAccelPanel (28), BrachistochroneAuPanel (29),
                         #   BrachistochroneLmPanel (30)
    system_travel.py     # SystemTravelSolarPanel (31), SystemTravelThrustPanel (32)
    csv_utility.py       # CsvUtilityPanel (50), ExportStarSystemsPanel (51),
                         #   ImportHwcPanel (52)
  visualizations/        # Phase E: shared rendering helpers + standalone panel stubs
    __init__.py
    plot_helpers.py      # mpl_available(), make_hz_canvas(), make_orbits_canvas(),
                         #   make_star_map_canvas(bg=), make_star_map_3d_canvas(bg=),
                         #   make_system_regions_canvas(), make_alt_hz_canvas(),
                         #   make_solar_travel_canvas(), make_solar_travel_canvas_3d()
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
                       then build_results_area(), then sets QPushButton children
                       to Fixed size policy (natural text width, not full screen width)
  reset()              removes old _container (deleteLater), calls _init_container()
                       — used by show_panel() when switching to a different panel
  build_inputs()       override: add form widgets above results
  build_results_area() override: add result display widgets (default: QTextEdit)
  make_table(headers, rows) → QTableView
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
| `VelocityLyHrPanel` | 20 | `panels/velocity.py` |
| `VelocityTimesCPanel` | 21 | `panels/velocity.py` |
| `DistanceLyHrPanel` | 22 | `panels/distance.py` |
| `DistanceTimesCPanel` | 23 | `panels/distance.py` |
| `TravelTimeLyHrPanel` | 24 | `panels/travel_time.py` |
| `TravelTimeTimesCPanel` | 25 | `panels/travel_time.py` |
| `OrbitPeriastronPanel` | 33 | `panels/orbit_calc.py` |
| `MoonDistance24Panel` | 34 | `panels/orbit_calc.py` |
| `MoonDistanceXPanel` | 35 | `panels/orbit_calc.py` |
| `GravityAccelPanel` | 36 | `panels/rotating_habitat.py` |
| `GravityDistancePanel` | 37 | `panels/rotating_habitat.py` |
| `GravityRpmPanel` | 38 | `panels/rotating_habitat.py` |
| `HabZonePanel` | 39 | `panels/habitable_zone_calc.py` |
| `HabZoneSmaPanel` | 40 | `panels/habitable_zone_calc.py` |
| `LuminosityPanel` | 41 | `panels/luminosity.py` |
| `SimbadPanel` | 1 | `panels/simbad.py` |
| `StarRegionsAutoPanel` | 8 | `panels/star_regions.py` |
| `StarRegionsSemiManualPanel` | 9 | `panels/star_regions.py` |
| `StarRegionsManualPanel` | 10 | `panels/star_regions.py` |
| `DistanceBetweenStarsPanel` | 17 | `panels/distance_stars.py` |
| `StarsWithinDistanceSolPanel` | 18 | `panels/distance_stars.py` |
| `StarsWithinDistanceStarPanel` | 19 | `panels/distance_stars.py` |
| `NasaPlanetarySystemsPanel` | 3 | `panels/nasa_exoplanet.py` |
| `NasaHwoExepPanel` | 4 | `panels/nasa_exoplanet.py` |
| `NasaMissionExocatPanel` | 5 | `panels/nasa_exoplanet.py` |
| `HwcPanel` | 6 | `panels/catalogs.py` |
| `TravelTimeStarsLyHrPanel` | 26 | `panels/travel_time_stars.py` |
| `TravelTimeStarsTimesCPanel` | 27 | `panels/travel_time_stars.py` |
| `BrachistochroneAccelPanel` | 28 | `panels/brachistochrone.py` |
| `BrachistochroneAuPanel` | 29 | `panels/brachistochrone.py` |
| `BrachistochroneLmPanel` | 30 | `panels/brachistochrone.py` |
| `SystemTravelSolarPanel` | 31 | `panels/system_travel.py` |
| `SystemTravelThrustPanel` | 32 | `panels/system_travel.py` |
| `CsvUtilityPanel` | 50 | `panels/csv_utility.py` |
| `ExportStarSystemsPanel` | 51 | `panels/csv_utility.py` |
| `ImportHwcPanel` | 52 | `panels/csv_utility.py` |

> **Note**: `NasaAllTablesPanel` (opt 2) and `OecPanel` (opt 7) are implemented in `nasa_exoplanet.py` and `catalogs.py` respectively, but are **not exported** from `panels/__init__.py` and do not appear in the GUI nav. Both options remain fully functional in the CLI.

> **Note**: `StarMapPanel`, `SystemOrbitsPanel`, and `HabZoneDiagramPanel` live in `gui/visualizations/` and are exported via the lazy `__getattr__` in `panels/__init__.py`. They are **not in the nav tree** — visualizations appear as embedded tabs inside the relevant option panels rather than as standalone nav entries.

## Star Regions Panel Layout Notes

### Star Regions Panels (`panels/star_regions.py`)

Three independent panels for opts 8 (Auto/SIMBAD), 9 (Semi-Manual), and 10 (Manual). All inherit `(DiagramToggleMixin, ResultPanel)` and produce the same result tabs; they differ only in how input values are collected.

- **Auto (opt 8)** — one `QLineEdit` for star name; hardcoded `sunlight=1.0`, `albedo=0.3`. Single background worker combines SIMBAD lookup + region computation.
- **Semi-Manual (opt 9)** — star name + sunlight intensity + bond albedo inputs. Same combined background worker.
- **Manual (opt 10)** — six `QLineEdit` fields (vmag, parallax, BC, teff, sunlight, albedo); pure math, no network call.

`build_results_area()` calls `_build_results_area_regions(panel)` which creates:
- `_tables_widget` — `QWidget` wrapping `_result_area` (a `QVBoxLayout`); holds the seven data tabs.
- `_viz_container` + `_viz_tabs_widget` — created by `_setup_diagram_view()`.

All three share `_build_region_tabs(d, viz_widget=None)` which produces a `QTabWidget` with seven always-present data tabs. When `viz_widget` is provided (a `_viz_tabs_widget` from the mixin), the two diagram tabs are added there instead of the data tabs:

Always present in data tabs (7): Star System Properties, Stellar Properties, Star Distance, Earth Equiv. Orbit, System Regions, Alternate HZ Regions, Calculated HZ.

Added to `viz_widget` when `mpl_available()` (2):
- **HZ Diagram** — concentric ring diagram using `d["calculatedLuminosity"]` and `d["temp"]`; marks `d["distAU"]` as the EEID.
- **System Regions Diagram** — concentric ring diagram (√AU scale) showing all seven system boundary zones. Built from `core.viz.prepare_system_regions_diagram(d)` → `make_system_regions_canvas()`.

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
| `make_orbits_canvas(parent, orbits, hz_zones, max_au, star_name, eeid_au)` | NASA opts 3, 6 | Keplerian orbital ellipses with HZ annulus overlay |
| `make_star_map_canvas(parent, stars, title, xk, yk, xlabel, ylabel, bg)` | Stars Within Distance 18, 19 | 2D scatter, spectral-class colours, hover annotation; `bg` overrides figure background colour |
| `make_star_map_3d_canvas(parent, stars, title, bg)` | Stars Within Distance 18, 19 | 3D scatter with drag-to-rotate (`azel` rotation style); returns `(canvas, toolbar, ax)` so caller can bind viewpoint preset buttons; `bg` overrides figure background colour |
| `make_system_regions_canvas(parent, data)` | Star Regions 8–10 | Concentric ring diagram (√AU scale) with zone fills + boundary labels |
| `make_alt_hz_canvas(parent, zones, max_au, title, eeid_au)` | Star Regions 8–10 | Concentric ring diagram (⁴√AU scale) for alternate biochemistry HZ zones |
| `make_solar_travel_canvas(parent, data)` | System Travel 31, 32 | 2D top-down (XY ecliptic) solar system map: planet dots + reference orbit circles + origin ★ + dest ■ + dashed travel path; click-to-info on any body |
| `make_solar_travel_canvas_3d(parent, data)` | System Travel 31, 32 | 3D version of the solar system travel map (`azel` rotation); returns `(canvas, toolbar, ax)` for preset buttons; no floating 3D text labels — body info shown via hover/click `text2D` tooltips only |

All ring diagrams support click-to-info: clicking a region or orbit shows a details box in the lower-left corner; clicking empty space dismisses it. The EEID circle (dark teal `#006644`) is also clickable.

**3D rotation style**: All 3D canvas functions (`make_star_map_3d_canvas`, `make_solar_travel_canvas_3d`) set `matplotlib.rcParams['axes3d.mouserotationstyle'] = 'azel'` so horizontal drag = azimuth change and vertical drag = elevation change — the natural, predictable rotation behaviour. Preset buttons also deactivate any active toolbar zoom/pan mode before applying the viewpoint so 3D rotation works immediately after pressing a preset.

### Panels with embedded viz tabs

Viz tabs are populated during `_render()` and placed in `_viz_tabs_widget` (via mixin) or the panel's own inline equivalent. The **Show Diagrams** button appears next to **Search/Calculate** only after a successful render that produced at least one viz tab.

| Panel | Viz tab(s) | Toggle mechanism |
|---|---|---|
| `NasaPlanetarySystemsPanel` (3) | "Orbital Diagram", "HZ Diagram" | Inline (uses `_scroll_area`) |
| `NasaHwoExepPanel` (4) | "HZ Diagram" (EEID from `st_eei_orbsep`) | `DiagramToggleMixin` |
| `NasaMissionExocatPanel` (5) | "HZ Diagram" (EEID from `st_eeidau`; lum = `st_lbol` direct Lsun) | `DiagramToggleMixin` |
| `HwcPanel` (6) | "Orbital Diagram", "HZ Diagram" (lum = `S_LUMINOSITY` direct Lsun) | `DiagramToggleMixin` |
| `StarRegionsAutoPanel` (8) | "HZ Diagram", "System Regions Diagram" | `DiagramToggleMixin` |
| `StarRegionsSemiManualPanel` (9) | "HZ Diagram", "System Regions Diagram" | `DiagramToggleMixin` |
| `StarRegionsManualPanel` (10) | "HZ Diagram", "System Regions Diagram" | `DiagramToggleMixin` |
| `StarsWithinDistanceSolPanel` (18) | "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" | `DiagramToggleMixin` |
| `StarsWithinDistanceStarPanel` (19) | "Map X–Y (top-down)", "Map X–Z (edge-on)", "Map 3D" | `DiagramToggleMixin` |
| `SystemTravelSolarPanel` (31) | "Solar System Map", "3D View" | `DiagramToggleMixin` |
| `SystemTravelThrustPanel` (32) | "Solar System Map", "3D View" | `DiagramToggleMixin` |

### `core/viz.py` public API

| Function | Description |
|---|---|
| `prepare_star_map(csv_path=None)` | Reads `starSystems.csv`; returns `{"stars": list, "count": int}` or `{"error": str}`. Sol prepended at origin. Each star dict: `name, desig, sp_type, color, ly, x, y, z`. |
| `prepare_system_orbits(planets)` | Takes NASA-archive planet list (dicts with `pl_orbsmax`, `pl_orbeccen`, `pl_name`, `st_teff`, `st_rad`). Returns `{"orbits", "hz_zones", "max_au", "star_name"}` or `{"error": str}`. |
| `prepare_hz_diagram(teff, luminosity)` | Returns `{"zones": list, "max_au": float}` or `{"error": str}`. Each zone dict: `key, label, outer (AU), color`. |
| `prepare_star_map_from_result(result)` | Converts `compute_stars_within_distance_of_sol/star` result dict to star-map format. Center star placed at origin; surrounding stars' coordinates shifted accordingly. |
| `prepare_system_regions_diagram(d)` | Extracts seven labelled boundary AU values + Kopparapu HZ zones + EEID from a star-regions result dict. Returns `{"regions", "hz_zones", "eeid_au", "max_au"}`. |
| `prepare_solar_travel_diagram(result)` | Converts a `compute_travel_time_solar_objects` or `compute_travel_time_custom_thrust` result dict into solar-map viz data. Returns `{"origin_name", "dest_name", "origin_xyz", "dest_xyz", "planets", "planet_orbits", "max_au"}` or `{"error": str}`. `planet_orbits` contains only planets whose SMA ≤ `max_au × 1.1`. |

### System Travel Panels (`panels/system_travel.py`)

`SystemTravelSolarPanel` (31) and `SystemTravelThrustPanel` (32) both inherit `(DiagramToggleMixin, ResultPanel)`.

`build_results_area()` creates:
- `_tables_widget` — `QWidget` wrapping `_tables_layout` (a `QVBoxLayout`); all result tables and labels are added here.
- `_viz_container` + `_viz_tabs_widget` — created by `_setup_diagram_view()`.

`_input_count` is reset at the end of `build_results_area()` so `clear_results()` never destroys the persistent widget infrastructure. A module-level `_clear_tables_layout(panel)` helper (defined in `system_travel.py`) clears the `_tables_layout` between renders.

Both panels accept a **Departure Date** (`QDateEdit`, calendar popup, defaults to today) in their input form, positioned between Destination and Acceleration. The selected date is passed to the core function as an ISO string `"YYYY-MM-DD"` and displayed as a label above the result tables.

**Opt 31 result layout**: "Departure Date" label → Summary table (Origin | Destination | Acceleration | Distance AU | Distance LM) → Profiles table (Acceleration Profile | Travel Time Hours | Travel Time | Max Vel).

**Opt 32 result layout**: "Departure Date" label → Summary table (Origin | Destination | Acceleration | Distance AU | Distance LM | Total Travel Time Hours | Total Travel Time) → Burn Profile table (Req. Burn | Eff. Burn | Max Vel Cap | Max Vel Reached | Time to Max Vel | Coast Velocity) → optional fallback note → Phase Breakdown table (Phase | Duration | Distance AU | Distance LM, rows: Acceleration / Coast / Deceleration / Total) → iterations note.

Two diagram tabs are added to `_viz_tabs_widget` when `mpl_available()` and the result contains `origin_xyz`:
- **Solar System Map** — 2D XY ecliptic view via `make_solar_travel_canvas()`.
- **3D View** — 3D view via `make_solar_travel_canvas_3d()`, with Top View / Side View / 3D Perspective preset buttons above the toolbar. Preset button callbacks deactivate any active toolbar zoom/pan mode before calling `view_init()`.

**Planet position cache**: `core.calculators._fetch_planet_positions(epoch_jd)` fetches heliocentric positions for all 8 planets and caches the result for 30 minutes (`_PLANET_POS_CACHE_TTL = 1800 s`). The cache is keyed by epoch: it is only reused when the requested `epoch_jd` is within 0.02 JD (~29 min) of the cached epoch. Past or future departure dates always trigger a fresh Horizons fetch for that epoch.

**`_PLANET_IDS` / `_PLANET_COLORS`**: Module-level constants in `core/calculators.py` listing the 8 planets with their Horizons IDs and display colours; also mirrored as `_PLANET_SMAS` / `_PLANET_COLORS_VIZ` in `core/viz.py` for the canvas rendering layer.

## Phase Completion Status

| Phase | Status | Covers |
|---|---|---|
| A | Complete | Project skeleton, core stubs, GUI shell, nav tree |
| B | Complete | Static display + pure-math calculators (opts 11–16, 20–25, 33–41) |
| C | Complete | SIMBAD-based features + QThread threading pattern (opts 1, 8–10, 17–19) |
| D | Complete | Multi-source features, JPL Horizons, option 50 (opts 3–6, 26–32, 50); opts 2 and 7 implemented but not in GUI nav |
| E | Complete | Visualizations embedded in existing panels: star map 2D + 3D (18–19), orbital diagrams (3, 6), HZ diagrams (3–6, 8–10), system regions diagram (8–10), solar system travel map 2D + 3D (31–32); Show Diagrams/Show Tables toggle on all viz panels; light theme; 3D viewpoint preset buttons (18–19, 31–32); `azel` rotation style for all 3D views |
| F | Pending | SQLite migration — replaces all CSV files with `data/space_app.db`; opt 50 rewritten to write to DB; opt 51 (Export Star Systems to CSV) and opt 52 (Import HWC Data) added |
