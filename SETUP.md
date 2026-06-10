# Setup Guide

## Requirements

- **Python 3.10+** (developed and tested on Python 3.12.3)
- **libxcb-cursor0** (Linux only — required by PySide6/Qt for the GUI):

```bash
sudo apt install libxcb-cursor0
```

## Python Libraries

| Library | Version | Purpose |
|---|---|---|
| `astroquery` | 0.4.11 | SIMBAD star lookups, NASA Exoplanet Archive queries, JPL Horizons ephemeris, Open Exoplanet Catalogue |
| `astropy` | 7.2.0 | Required by astroquery; astronomical data types and units |
| `requests` | 2.33.1 | HTTP calls to Hypatia Catalog API and NASA TAP endpoints |
| `PySide6` | 6.11.0 | Qt-based GUI (`gui_main.py`) |
| `matplotlib` | 3.10.8 | Embedded visualizations in the GUI (HZ diagrams, orbital maps, star maps, abundance charts) |
| `numpy` | 2.4.4 | Numeric arrays for the 3D star-map and abundance visualizations (imported directly by `gui/visualizations/plot_helpers.py`) |

## Installation

1. **Clone or download** the repository to your local machine.

2. **Create and activate a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

3. **Install dependencies** using pip:

```bash
pip install -r requirements.txt
```

## Running the Application

**GUI (recommended):**
```bash
python gui_main.py
```

**CLI:**
```bash
python main.py
```

**JSON dispatcher** (for integration with other tools):
```bash
python query.py <subcommand> [arguments]
```

See `docs/integration.md` for all `query.py` subcommands and output format.

## Data Files

The following CSV files must be present in the project directory. They are auto-imported into the local SQLite database on first run:

| File | Used By |
|---|---|
| `propertiesOfMainSequenceStars.csv` | Options 8, 9, 12 — Star System Regions (SIMBAD/Semi-SIMBAD), Main Sequence Star Properties |
| `spTypeHyperLM.csv` | Option 14 — Honorverse Hyper Limits |
| `missionExocat.csv` | Options 2, 5 — Mission Exocat Stars |
| `hwc.csv` | Option 6 — Habitable Worlds Catalog |
| `planetInfo.csv` | Option 11 — Solar System Planets |
| `moonInfo.csv` | Option 11 — Moon Data |
| `dwarfPlanetInfo.csv` | Option 11 — Dwarf Planets |
| `asteroidsInfo.csv` | Option 11 — Major Asteroids |

> **Note:** The `star_systems` database table is populated by running **Option 50 (Star Systems DB Query)** from the menu. Options 18 and 19 (Stars within a Distance) require this table to have data. Option 51 can export the table to `starSystems.csv` if needed.

## Notes

- An internet connection is required for SIMBAD, NASA Exoplanet Archive, JPL Horizons, Open Exoplanet Catalogue, and Hypatia Catalog queries.
- The Open Exoplanet Catalogue data is downloaded once per session and cached in memory.
- The local SQLite database is created automatically on first run at `data/space_app.db` under the repo root (the `data/` directory is gitignored). Set the `SPACE_APP_DB` environment variable to override this path (see `docs/integration.md`).
- The `backups/` directory holds manual CSV snapshots (e.g. `starSystemsBackup-*.csv`, `templateStarSystems.csv`) that are **not** read by the app — they are retained for reference only.
