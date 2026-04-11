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
    science_tables.py     # SolarSystemPanel (12), MainSequencePanel (13)
    sol_regions.py        # SolRegionsPanel (14)
    honorverse.py         # HonorverseHyperPanel (15), HonorverseAccelPanel (16),
                          #   HonorverseSpeedPanel (17)
    velocity.py           # VelocityPanel (21, 22)
    distance.py           # DistancePanel (23, 24)
    travel_time.py        # TravelTimePanel (25, 26)
    orbit_calc.py         # OrbitPeriastronPanel (34), MoonDistance24Panel (35),
                          #   MoonDistanceXPanel (36)
    rotating_habitat.py   # GravityAccelPanel (37), GravityDistancePanel (38),
                          #   GravityRpmPanel (39)
    habitable_zone_calc.py # HabZonePanel (40), HabZoneSmaPanel (41)
    luminosity.py         # LuminosityPanel (42)
    # Phase C panels (SIMBAD / network — added in Phase C):
    # simbad.py            SimbadPanel (1)
    # star_regions.py      StarRegionsPanel (9, 10, 11)
    # distance_stars.py    DistanceStarsPanel (18, 19, 20)
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

**Every nav entry maps to its own independent panel class.** Multiple entries never share the same class (tabs-within-a-panel were intentionally avoided so each feature opens cleanly on its own).

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
| `SolarSystemPanel` | 12 | `panels/science_tables.py` |
| `MainSequencePanel` | 13 | `panels/science_tables.py` |
| `SolRegionsPanel` | 14 | `panels/sol_regions.py` |
| `HonorverseHyperPanel` | 15 | `panels/honorverse.py` |
| `HonorverseAccelPanel` | 16 | `panels/honorverse.py` |
| `HonorverseSpeedPanel` | 17 | `panels/honorverse.py` |
| `VelocityPanel` | 21, 22 | `panels/velocity.py` |
| `DistancePanel` | 23, 24 | `panels/distance.py` |
| `TravelTimePanel` | 25, 26 | `panels/travel_time.py` |
| `OrbitPeriastronPanel` | 34 | `panels/orbit_calc.py` |
| `MoonDistance24Panel` | 35 | `panels/orbit_calc.py` |
| `MoonDistanceXPanel` | 36 | `panels/orbit_calc.py` |
| `GravityAccelPanel` | 37 | `panels/rotating_habitat.py` |
| `GravityDistancePanel` | 38 | `panels/rotating_habitat.py` |
| `GravityRpmPanel` | 39 | `panels/rotating_habitat.py` |
| `HabZonePanel` | 40 | `panels/habitable_zone_calc.py` |
| `HabZoneSmaPanel` | 41 | `panels/habitable_zone_calc.py` |
| `LuminosityPanel` | 42 | `panels/luminosity.py` |
| `SimbadPanel` *(Phase C)* | 1 | `panels/simbad.py` |
| `StarRegionsPanel` *(Phase C)* | 9, 10, 11 | `panels/star_regions.py` |
| `DistanceStarsPanel` *(Phase C)* | 18, 19, 20 | `panels/distance_stars.py` |

## Phase Completion Status

| Phase | Status | Covers |
|---|---|---|
| A | Complete | Project skeleton, core stubs, GUI shell, nav tree |
| B | Complete | Static display + pure-math calculators (opts 12–17, 21–26, 34–42) |
| C | Pending | SIMBAD-based features + QThread threading pattern (opts 1, 9–11, 18–20) |
| D | Pending | Multi-source features, JPL Horizons, option 50 (opts 2–8, 27–33, 50) |
| E | Pending | Visualizations: star map, orbital diagram, HZ diagram |
| F | Pending | SQLite migration — replaces all CSV files with `data/space_app.db` |
