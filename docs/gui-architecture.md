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
    velocity.py           # VelocityPanel (20, 21)
    distance.py           # DistancePanel (22, 23)
    travel_time.py        # TravelTimePanel (24, 25)
    orbit_calc.py         # OrbitPeriastronPanel (33), MoonDistance24Panel (34),
                          #   MoonDistanceXPanel (35)
    rotating_habitat.py   # GravityAccelPanel (36), GravityDistancePanel (37),
                          #   GravityRpmPanel (38)
    habitable_zone_calc.py # HabZonePanel (39), HabZoneSmaPanel (40)
    luminosity.py         # LuminosityPanel (41)
    # Phase C panels (SIMBAD / network):
    simbad.py            # SimbadPanel (1)
    star_regions.py      # StarRegionsPanel (8, 9, 10)
    distance_stars.py    # DistanceStarsPanel (17, 18, 19)
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

### Navigation (`gui/nav.py`)

`NAVIGATION` is a list of `(category, [(label, panel_class_name), ...])` tuples. At click time, `_on_item_clicked` resolves the class name via `getattr(gui.panels, name)`. Entries whose class hasn't been created yet are silently ignored — this lets phases be added incrementally without breaking existing nav items.

Most nav entries map to their own independent panel class. Phase C panels (`StarRegionsPanel`, `DistanceStarsPanel`) are exceptions — they use `QTabWidget` internally to host multiple related features (opts 8/9/10 and opts 17/18/19 respectively). Clicking any of their nav entries opens the same panel; the user switches between features via tabs.

### Panel Base Class (`gui/panels/base.py`)

```
ResultPanel (QWidget)
  __init__         calls build_inputs() then build_results_area()
  build_inputs()   override: add form widgets above results
  build_results_area()  override: add result display widgets
  make_table(headers, rows) → QTableView
  clear_results()  remove all widgets below the input section
  show_error(msg)  display red error label
  set_status(msg)  update MainWindow status bar
  # Phase C additions:
  run_in_background(fn, *args, on_result=None)
  _on_error(msg)
  _on_thread_done()
```

Phase C adds `Worker(QObject)` and `run_in_background()` to support network calls without freezing the UI. The pattern established in Phase C is reused by all subsequent network-bound panels (Phase D).

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
| `StarRegionsPanel` | 8, 9, 10 | `panels/star_regions.py` |
| `DistanceBetweenStarsPanel` | 17 | `panels/distance_stars.py` |
| `StarsWithinDistanceSolPanel` | 18 | `panels/distance_stars.py` |
| `StarsWithinDistanceStarPanel` | 19 | `panels/distance_stars.py` |
| `NasaAllTablesPanel` | 2 | `panels/nasa_exoplanet.py` |
| `NasaPlanetarySystemsPanel` | 3 | `panels/nasa_exoplanet.py` |
| `NasaHwoExepPanel` | 4 | `panels/nasa_exoplanet.py` |
| `NasaMissionExocatPanel` | 5 | `panels/nasa_exoplanet.py` |
| `HwcPanel` | 6 | `panels/catalogs.py` |
| `OecPanel` | 7 | `panels/catalogs.py` |
| `TravelTimeStarsLyHrPanel` | 26 | `panels/travel_time_stars.py` |
| `TravelTimeStarsTimesCPanel` | 27 | `panels/travel_time_stars.py` |
| `BrachistochroneAccelPanel` | 28 | `panels/brachistochrone.py` |
| `BrachistochroneAuPanel` | 29 | `panels/brachistochrone.py` |
| `BrachistochroneLmPanel` | 30 | `panels/brachistochrone.py` |
| `SystemTravelSolarPanel` | 31 | `panels/system_travel.py` |
| `SystemTravelThrustPanel` | 32 | `panels/system_travel.py` |
| `CsvUtilityPanel` | 50 | `panels/csv_utility.py` |

## Tab-Based Panel Layout Notes

### DistanceStarsPanel (`panels/distance_stars.py`)

Three tabs sharing one `DistanceStarsPanel` instance:

- **Between 2 Stars (opt 17)** — two `QLineEdit` inputs in a `QFormLayout`, Calculate button below the form in the main `QVBoxLayout`, 2-row result table + distance label in a `_result_area` sub-layout.
- **Within Distance of Sol (opt 18)** — one `QLineEdit` input in a `QFormLayout`; Search button added as the last row of the `QFormLayout` (no label) so it sits flush below the input. Result count label + table in `_result_area`, which has stretch factor 1 so the table expands to fill available height.
- **Within Distance of Star (opt 19)** — same layout pattern as opt 18: two `QLineEdit` inputs in a `QFormLayout`, Search button as last form row, expanding result table.

The expanding-table pattern (result layout with stretch=1, table view with `Expanding` size policy) is used in opts 18 and 19 because they can return many rows. Opt 17 returns exactly 2 rows so no expansion is needed.

### StarRegionsPanel (`panels/star_regions.py`)

Three tabs for opts 8 (Auto/SIMBAD), 9 (Semi-Manual), and 10 (Manual). All tabs produce identical output tables; they differ only in how input values are collected (fully automated vs. partially prompted vs. fully manual).

## Phase Completion Status

| Phase | Status | Covers |
|---|---|---|
| A | Complete | Project skeleton, core stubs, GUI shell, nav tree |
| B | Complete | Static display + pure-math calculators (opts 11–16, 20–25, 33–41) |
| C | Complete | SIMBAD-based features + QThread threading pattern (opts 1, 8–10, 17–19) |
| D | Complete | Multi-source features, JPL Horizons, option 50 (opts 2–7, 26–32, 50) |
| E | Pending | Visualizations: star map, orbital diagram, HZ diagram |
| F | Pending | SQLite migration — replaces all CSV files with `data/space_app.db` |
