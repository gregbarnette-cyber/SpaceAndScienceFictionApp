# GUI Architecture Documentation

The GUI is a PySide6 desktop application that runs alongside the existing CLI (`main.py`). It shares all computation logic through the `core/` package — no display or input code lives in `core/`.

## Running the GUI

```bash
python gui_main.py
```

## Repo Structure

```
main.py              # CLI entry point (unchanged)
gui_main.py          # GUI entry point

core/                # Pure computation layer — no I/O, no Qt
  __init__.py
  calculators.py     # Speed, distance, travel time functions
  databases.py       # SIMBAD and archive query functions
  equations.py       # Planetary, habitat, HZ, luminosity equations
  regions.py         # Star system region calculations
  science.py         # Solar system data, main sequence, Honorverse tables
  shared.py          # Shared helpers (format_travel_time, etc.)
  db.py              # SQLite connection (Phase F)
  viz.py             # Visualization helpers (Phase E)

gui/                 # Qt presentation layer
  app.py             # MainWindow: QSplitter with nav tree + QStackedWidget
  nav.py             # NAVIGATION list + populate_nav(); maps labels → panel class names
  panels/
    __init__.py      # Exports all panel classes by name (used by nav.py)
    base.py          # ResultPanel base class; Worker + run_in_background (Phase C+)
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
  visualizations/         # Phase E
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

> **Note**: `NasaAllTablesPanel` (opt 2) and `OecPanel` (opt 7) are implemented in `nasa_exoplanet.py` and `catalogs.py` respectively, but are **not exported** from `panels/__init__.py` and do not appear in the GUI nav. Both options remain fully functional in the CLI.

## Star Regions Panel Layout Notes

### Star Regions Panels (`panels/star_regions.py`)

Three independent panels for opts 8 (Auto/SIMBAD), 9 (Semi-Manual), and 10 (Manual). All produce the same result tab set (`_build_region_tabs`); they differ only in how input values are collected (fully automated vs. partially prompted vs. fully manual).

- **Auto (opt 8)** — one `QLineEdit` for star name; hardcoded `sunlight=1.0`, `albedo=0.3`. Single background worker combines SIMBAD lookup + region computation.
- **Semi-Manual (opt 9)** — star name + sunlight intensity + bond albedo inputs. Same combined background worker.
- **Manual (opt 10)** — six `QLineEdit` fields (vmag, parallax, BC, teff, sunlight, albedo); pure math, no network call.

All three share `_build_region_tabs(d)` which produces a nested `QTabWidget` with seven result tabs: Star System Properties, Stellar Properties, Star Distance, Earth Equiv. Orbit, System Regions, Alternate HZ Regions, Calculated HZ.

## Phase Completion Status

| Phase | Status | Covers |
|---|---|---|
| A | Complete | Project skeleton, core stubs, GUI shell, nav tree |
| B | Complete | Static display + pure-math calculators (opts 11–16, 20–25, 33–41) |
| C | Complete | SIMBAD-based features + QThread threading pattern (opts 1, 8–10, 17–19) |
| D | Complete | Multi-source features, JPL Horizons, option 50 (opts 3–6, 26–32, 50); opts 2 and 7 implemented but not in GUI nav |
| E | Pending | Visualizations: star map, orbital diagram, HZ diagram |
| F | Pending | SQLite migration — replaces all CSV files with `data/space_app.db` |
