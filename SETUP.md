# Setup Guide

## Requirements

- **Python 3.10+** (developed and tested on Python 3.12–3.14)
- **libxcb-cursor0** (Linux only — required by PySide6/Qt for the GUI). **Not needed on macOS or Windows:**

```bash
sudo apt install libxcb-cursor0
```

> **macOS / Apple Silicon:** no extra system packages are required — all dependencies ship native arm64 wheels and install cleanly via pip. Use `python3` (not `python`) in the commands below, since macOS does not put `python` on the PATH by default.

## Python Libraries

| Library | Version | Purpose |
|---|---|---|
| `astroquery` | 0.4.11 | SIMBAD star lookups, NASA Exoplanet Archive queries, JPL Horizons ephemeris, Open Exoplanet Catalogue |
| `astropy` | 7.2.0 | Required by astroquery; astronomical data types and units |
| `requests` | 2.33.1 | HTTP calls to Hypatia Catalog API and NASA TAP endpoints |
| `PySide6` | 6.11.0 | Qt-based GUI (`gui_main.py`) |
| `matplotlib` | 3.10.8 | Embedded visualizations in the GUI (HZ diagrams, orbital maps, star maps, abundance charts) |
| `numpy` | 2.4.4 | Numeric arrays for the 3D star-map and abundance visualizations (imported directly by `gui/visualizations/plot_helpers.py`) |
| `pyvo` | 1.8.1 | GAVO TAP async jobs for the GCNS import (option 58 — Gaia Catalogue of Nearby Stars) |

> Versions above are the tested baseline; `requirements.txt` pins only the matplotlib range (`>=3.6,<4`) and otherwise installs the latest compatible release of each library.

### Optional — Dust / ISM extra (Phase T2, WSL/Linux only)

The 3D interstellar-dust query path — `query.py dust-sightline` / `dust-between`, the route planners'
`--weight dust`, and the dust-map fetch (CLI **option 59** / GUI **Utilities → Fetch Dust Map Data**) — needs
a separate **optional** extra, `requirements-dust.txt`:

| Library | Purpose |
|---|---|
| `dustmaps` | 3D Galactic dust maps (Leike 2020 + Edenhofer 2024) |
| `healpy` | HEALPix support required by `dustmaps` (Edenhofer map) |
| `h5py`, `scipy`, `progressbar2`, `six`, `tqdm` | `dustmaps` dependencies |

It is **not** in base `requirements.txt` and is **WSL/Linux-venv-only**: `dustmaps` requires `healpy`, which
has **no native-Windows pip wheel**. A native-Windows checkout keeps the entire stellar layer working and just
skips the dust path behind an import gate (the dust subcommands/panel return a clean "install the dust extra"
message). `astropy`/`numpy`/`requests` are already in the base requirements. Install it on top of the base —
see Installation step 4.

## Installation

1. **Clone or download** the repository to your local machine:

```bash
git clone https://github.com/gregbarnette-cyber/SpaceAndScienceFictionApp.git
cd SpaceAndScienceFictionApp
```

2. **Create and activate a virtual environment:**

```bash
python3 -m venv venv         # use python3 on macOS/Linux
source venv/bin/activate     # macOS/Linux
# venv\Scripts\activate      # Windows (PowerShell/cmd)
```

3. **Install dependencies** using pip:

```bash
pip install -r requirements.txt
```

4. **(Optional) Install the Dust / ISM extra** — only for the Phase T2 dust path, and only in a **WSL/Linux** venv (see the optional-extra note above):

```bash
pip install -r requirements-dust.txt
```

This pulls `dustmaps` + `healpy` (and `h5py`/`scipy`/…). On **native Windows it fails** (no `healpy` pip wheel) — that is expected; the rest of the app is unaffected. After installing, fetch the map data via **CLI option 59 (Fetch Dust Map Data)** or the GUI **Utilities → Fetch Dust Map Data** panel. The maps are large (Leike 2020 ~2.4 GB, Edenhofer 2024 ~3.2 GB) and hosted on **Zenodo**, which bandwidth-throttles large downloads (~0.5 MB/s) and can't resume a broken transfer — so the GUI panel shows copyable, **resumable** `aria2c -c` / `wget -c` commands for a faster manual download into `data/dust/` (then click **Check Status**, which verifies the md5 and reuses the file). See the "Dust / ISM" section of `docs/integration.md`.

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

## Migrating to a New Machine

The code comes down with `git clone`, but the **local SQLite database (`data/space_app.db`) is gitignored and does not transfer with the repo**. Rebuilding it from scratch is slow:

- **Option 50 (Star Systems DB Query)** runs 17 sequential SIMBAD criteria queries (several minutes, network-bound).
- **Option 58 (Import GCNS Data)** pulls ~331k rows from GAVO TAP (~55–65 MB added to the DB).
- **Import Hypatia Cache** (GUI utility) makes ~112 throttled API calls (~14k stars / ~245k abundance rows).
- **Option 59 (Fetch Dust Map Data)** — *only if you use the optional dust extra* — downloads ~5.6 GB of map files into `data/dust/` (also gitignored, WSL/Linux only). These don't live in `space_app.db`; copy the `data/dust/` directory across (or re-fetch) the same way.

To skip all of that, **copy the database file from the old machine to the new one** after cloning:

```bash
# On the new Mac, from the repo root, after `git clone` and the venv/pip steps:
mkdir -p data
# then copy the old data/space_app.db into ./data/ (via USB, scp, AirDrop, etc.)
```

The static reference CSVs (planets, moons, HWC, main-sequence, etc.) **do** travel with the repo and auto-seed on first run, so only the three network-built tables above are worth migrating. If you don't copy the DB, the app still works — you just re-run opts 50/58 and the Hypatia import when you need those features.

## Notes

- An internet connection is required for SIMBAD, NASA Exoplanet Archive, JPL Horizons, Open Exoplanet Catalogue, and Hypatia Catalog queries.
- The Open Exoplanet Catalogue data is downloaded once per session and cached in memory.
- The local SQLite database is created automatically on first run at `data/space_app.db` under the repo root (the `data/` directory is gitignored). Set the `SPACE_APP_DB` environment variable to override this path (see `docs/integration.md`).
- The `backups/` directory holds manual CSV snapshots (e.g. `starSystemsBackup-*.csv`, `templateStarSystems.csv`) that are **not** read by the app — they are retained for reference only.
- The **dust / ISM path is optional and WSL/Linux-only** (`requirements-dust.txt`; see above). Without it installed, every other feature works normally and the dust subcommands/panel are simply gated off. The dust map cache lives at `data/dust/` (gitignored) and is fetch-once/offline-after.
