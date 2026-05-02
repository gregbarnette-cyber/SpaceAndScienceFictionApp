# Phase F — SQLite Migration Plan

## Overview

Phase F replaces all CSV-based persistent storage with a single SQLite database at
`data/space_app.db`. Every file in the project root that is currently read at runtime
is migrated to a DB table. Read functions in `core/science.py` and `core/databases.py`
are updated to query the DB instead of the file system. New import utility options
(53–56) are added so users can (re)load the static CSV files into the DB. Options 50–52
(already partially documented) are completed as part of this phase.

**Database path:** `data/space_app.db` (relative to project root; `data/` directory
created by `core/db.py` on first use if absent)

---

## Tables

| Table | Source CSV | Populated By |
|---|---|---|
| `star_systems` | `starSystems.csv` | Opt 50 (SIMBAD query runner) |
| `star_systems_backup_YYYYMMDD` | ← `star_systems` rows | Opt 50 backup step |
| `hwc` | `hwc.csv` | Opt 52 import |
| `mission_exocat` | `missionExocat.csv` | Opt 53 import |
| `main_sequence_stars` | `propertiesOfMainSequenceStars.csv` | Opt 54 import / auto-seed |
| `planets` | `planetInfo.csv` | Opt 55 import / auto-seed |
| `moons` | `moonInfo.csv` | Opt 55 import / auto-seed |
| `dwarf_planets` | `dwarfPlanetInfo.csv` | Opt 55 import / auto-seed |
| `asteroids` | `asteroidsInfo.csv` | Opt 55 import / auto-seed |
| `honorverse_hyper` | `spTypeHyperLM.csv` | Opt 56 import / auto-seed |

### Auto-seed rule
On `core/db.py` init, if a static table (`main_sequence_stars`, `planets`, `moons`,
`dwarf_planets`, `asteroids`, `honorverse_hyper`) is empty **and** the corresponding CSV
file exists in the project root, the CSV is loaded automatically. This means a fresh
install works without any manual import step. The import menu options exist to let users
refresh the data after updating a CSV file.

---

## Schema

### `star_systems`
```sql
CREATE TABLE IF NOT EXISTS star_systems (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    star_name    TEXT NOT NULL,
    designations TEXT,
    spectral_type TEXT,
    parallax     REAL,
    parsecs      REAL,
    light_years  REAL,
    app_magnitude REAL,
    ra           TEXT,
    dec          TEXT
);
```
Column mapping from existing CSV: `Star Name` → `star_name`, `Star Designations` →
`designations`, `Spectral Type` → `spectral_type`, `Parallax` → `parallax`,
`Parsecs` → `parsecs`, `Light Years` → `light_years`, `Apparent Magnitude` →
`app_magnitude`, `RA` → `ra`, `DEC` → `dec`.

Backup tables (`star_systems_backup_YYYYMMDD`) use the same column layout and are
created by `CREATE TABLE ... AS SELECT * FROM star_systems` before the existing rows
are deleted.

### `hwc`
All columns from `hwc.csv` stored verbatim as TEXT (the existing code accesses them
by column name string, so no type coercion needed at the DB layer). Primary key:
`rowid` (SQLite implicit). Lookup indices built in Python as before — the `_load_hwc`
cache is replaced by a DB query that returns all rows, then the same in-memory index
dicts are built from the result set.

### `mission_exocat`
All columns from `missionExocat.csv` stored verbatim as TEXT. `rowid` is the CSV's own
`rowid` column (INTEGER PRIMARY KEY). Lookup indices (hip/hd/gj) rebuilt from DB rows
the same way `_load_mission_exocat` currently works.

### `main_sequence_stars`
```sql
CREATE TABLE IF NOT EXISTS main_sequence_stars (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    spectral_class TEXT,
    b_v            TEXT,
    teff_k         TEXT,
    abs_mag_vis    TEXT,
    abs_mag_bol    TEXT,
    bc             TEXT,
    lum            TEXT,
    radius         TEXT,
    mass           TEXT,
    density        TEXT,
    lifetime       TEXT
);
```
Column mapping from CSV: `Spectral Class`, `B-V`, `Teeff(K)`, `AbsMag Vis.`,
`AbsMag Bol.`, `Bolo. Corr. (BC)`, `Lum`, `R`, `M`, `p (g/cm3)`, `Lifetime (years)`.
All stored as TEXT because the existing code accesses them by column name; the
`_lookup_spectral_type` logic reads `Bolo. Corr. (BC)` as a float at use-time via
`float(row["Bolo. Corr. (BC)"])`.

### `planets`
```sql
CREATE TABLE IF NOT EXISTS planets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    planet_name  TEXT,
    mass         TEXT,
    diameter     TEXT,
    period       TEXT,
    periastron   TEXT,
    semimajor_axis TEXT,
    apastron     TEXT,
    eccentricity TEXT,
    moons        TEXT
);
```
Column mapping from `planetInfo.csv`: `Planet`, `Mass`, `Diameter`, `Period`,
`Periastron`, `Semimajor Axis`, `Apastron`, `Eccentricity`, `Moons`.

### `moons`
```sql
CREATE TABLE IF NOT EXISTS moons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    satellite_name  TEXT,
    planet_name     TEXT,
    diameter_km     TEXT,
    mean_radius_km  TEXT,
    mass_kg         TEXT,
    perigee_km      TEXT,
    apogee_km       TEXT,
    semimajor_axis_km TEXT,
    eccentricity    TEXT,
    period_days     TEXT,
    gravity         TEXT,
    escape_velocity TEXT
);
```
Column mapping from `moonInfo.csv`: `Satellite Name`, `Planet Name`, `Diameter (km)`,
`Mean Radius (km)`, `Mass (kg)`, `Perigee (km)`, `Apogee (km)`, `SemiMajor Axis (km)`,
`Eccentricity`, `Period (days)`, `Gravity (m/s^2)`, `Escape Velocity (km/s)`.

### `dwarf_planets`
```sql
CREATE TABLE IF NOT EXISTS dwarf_planets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    periastron   TEXT,
    semimajor_axis TEXT,
    apastron     TEXT,
    eccentricity TEXT,
    period       TEXT,
    mass         TEXT,
    diameter     TEXT,
    moons        TEXT
);
```
Column mapping from `dwarfPlanetInfo.csv`: `Name`, `Periastron`, `Semimajor Axis`,
`Apastron`, `Eccentricity`, `Period`, `Mass`, `Diameter`, `Moons`.

### `asteroids`
```sql
CREATE TABLE IF NOT EXISTS asteroids (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    periastron   TEXT,
    semimajor_axis TEXT,
    apastron     TEXT,
    eccentricity TEXT,
    period       TEXT,
    diameter     TEXT
);
```
Column mapping from `asteroidsInfo.csv`: `Name`, `Periastron`, `Semimajor Axis`,
`Apastron`, `Eccentricity`, `Period`, `Diameter`.

### `honorverse_hyper`
```sql
CREATE TABLE IF NOT EXISTS honorverse_hyper (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    spectral_class TEXT,
    lm             REAL
);
```
`spTypeHyperLM.csv` has no header row; `core/science.py` parses it with bare
`csv.reader`. Each row is `[spectral_class_str, lm_str]`. The `au` column is computed
at display time as `lm / 8.3167` and is not stored.

---

## `core/db.py` Implementation

Populate the stub with:

```python
import sqlite3, os, pathlib, csv

_DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "space_app.db"
_conn: sqlite3.Connection | None = None

def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _create_schema(_conn)
        _auto_seed(_conn)
    return _conn

def close_conn():
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
```

`_create_schema(conn)` — runs all `CREATE TABLE IF NOT EXISTS` statements above in a
single transaction.

`_auto_seed(conn)` — for each static table (`main_sequence_stars`, `planets`, `moons`,
`dwarf_planets`, `asteroids`, `honorverse_hyper`), if `SELECT COUNT(*) = 0` and the
corresponding CSV exists in the project root, calls the matching `_seed_*` helper.
Seeding is wrapped in a single transaction so a partial failure leaves the table empty
(will retry next launch).

`_seed_*(conn, csv_path)` helpers — one per static table; reads the CSV with
`csv.DictReader` (or bare `csv.reader` for `spTypeHyperLM.csv`) and bulk-inserts with
`executemany`.

`def rows_as_dicts(cursor) -> list[dict]` — converts a `sqlite3.Cursor` result to a
list of plain dicts (removes `sqlite3.Row` dependency from callers).

---

## `core/science.py` Changes

Replace all `_read_csv(...)` calls with DB queries via `core.db.get_conn()`.

### `compute_main_sequence_table()`
**Before:** `return _read_csv("propertiesOfMainSequenceStars.csv")`
**After:**
```python
conn = get_conn()
rows = conn.execute("SELECT * FROM main_sequence_stars").fetchall()
return [dict(r) for r in rows]
```
Column names in the dict must match the original CSV header strings so callers
(option 12 display, `_lookup_spectral_type`) work unchanged. Use `AS` aliases or a
reverse-mapping dict to restore the original CSV column names.

### `compute_solar_system_tables()`
**Before:** four `_read_csv(...)` calls.
**After:** four DB queries (`SELECT * FROM planets ORDER BY semimajor_axis + 0`,
`SELECT * FROM moons ORDER BY semimajor_axis_km + 0`,
`SELECT * FROM dwarf_planets ORDER BY semimajor_axis + 0`,
`SELECT * FROM asteroids ORDER BY semimajor_axis + 0`).
Return dicts keyed the same as current CSV column names so callers work unchanged.

### `compute_honorverse_hyper_limits()`
**Before:** bare `csv.reader` parse of `spTypeHyperLM.csv`.
**After:**
```python
rows = conn.execute("SELECT spectral_class, lm FROM honorverse_hyper").fetchall()
return [{"spectral_class": r["spectral_class"], "lm": r["lm"],
         "au": r["lm"] / 8.3167} for r in rows]
```

### Remove `_read_csv()` and `_DATA_DIR`
Both become dead code once all callers are migrated.

---

## `core/databases.py` Changes

### `_load_hwc()` and `_load_mission_exocat()`
Replace CSV file reads with DB queries. The index-building logic (case-insensitive
dicts keyed by HIP/HD/GJ) stays identical — it just operates on `dict(row)` objects
from the DB cursor instead of `csv.DictReader` rows.

```python
def _load_hwc():
    global _HWC_DATA
    if _HWC_DATA is not None:
        return _HWC_DATA
    from core.db import get_conn
    rows = [dict(r) for r in get_conn().execute("SELECT * FROM hwc").fetchall()]
    # ... existing index-building logic unchanged ...
    _HWC_DATA = (hip_idx, hd_idx, name_idx)
    return _HWC_DATA
```

Same pattern for `_load_mission_exocat()`.

Cache invalidation: when opt 52 or 53 replaces a table's rows, set `_HWC_DATA = None`
or `_MISSION_EXOCAT = None` respectively so the next lookup re-builds the index from
the new DB data.

### `compute_star_systems_csv()` (Opt 50 rewrite)
**Behavior change:** instead of writing `starSystems.csv`, writes to the `star_systems`
DB table.

**Backup step (new):** if `SELECT COUNT(*) FROM star_systems > 0`, run:
```sql
CREATE TABLE star_systems_backup_YYYYMMDD AS SELECT * FROM star_systems;
DELETE FROM star_systems;
```
where `YYYYMMDD` is today's date string.

**Row insertion:** each accepted row (currently appended to a list for CSV writing) is
instead inserted into `star_systems` via `INSERT INTO star_systems (star_name, ...) VALUES (?, ...)`.

**Return dict:** add `"backup_table"` key (name of the backup table created, or `None`
if no prior rows existed).

### New function: `export_star_systems_csv(output_dir: str) -> dict`
```python
def export_star_systems_csv(output_dir):
    rows = get_conn().execute(
        "SELECT * FROM star_systems ORDER BY light_years ASC"
    ).fetchall()
    if not rows:
        return {"error": "star_systems table is empty. Run option 50 first."}
    path = os.path.join(output_dir, "starSystems.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Star Name", "Star Designations", "Spectral Type",
            "Parallax", "Parsecs", "Light Years", "Apparent Magnitude", "RA", "DEC"
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "Star Name": r["star_name"],
                "Star Designations": r["designations"],
                ...
            })
    return {"path": path, "count": len(rows)}
```

### New function: `import_hwc_csv(csv_path: str) -> dict`
Already documented. Implementation:
1. Validate file exists.
2. Read header row; check for required HWC columns (`P_NAME`, `S_NAME`, `S_NAME_HIP`, `S_NAME_HD`).
3. In a transaction: `DELETE FROM hwc`, then bulk-insert all rows.
4. Set `_HWC_DATA = None`.
5. Return `{"count": N, "path": csv_path}` or `{"error": msg}`.

### New function: `import_mission_exocat_csv(csv_path: str) -> dict`
Same pattern as `import_hwc_csv`. Required column check: `star_name`, `hip_name`,
`hd_name`, `gj_name`. Clears `_MISSION_EXOCAT = None` after import.

### New function: `import_main_sequence_csv(csv_path: str) -> dict`
Validates header contains `Spectral Class` and `Bolo. Corr. (BC)`. Replaces all rows
in `main_sequence_stars`.

### New function: `import_solar_system_csvs(data_dir: str) -> dict`
Imports all four solar system CSVs in one call. Validates each file exists before
starting any replacements. Replaces rows in `planets`, `moons`, `dwarf_planets`,
`asteroids`. Returns `{"planets": N, "moons": N, "dwarf_planets": N, "asteroids": N}`
or `{"error": msg}`.

### New function: `import_honorverse_hyper_csv(csv_path: str) -> dict`
Reads headerless CSV with bare `csv.reader`. Replaces all rows in `honorverse_hyper`.

---

## New Menu Options

### Option 53: Import Mission Exocat Data — `import_mission_exocat_data()`
- Mirrors opt 52 structure.
- Looks for `missionExocat.csv` in the project directory.
- Calls `core.databases.import_mission_exocat_csv(csv_path)`.
- Prints row count on success; prints error on failure.
- **GUI panel:** `ImportMissionExocatPanel` in `gui/panels/csv_utility.py`.

### Option 54: Import Main Sequence Star Properties — `import_main_sequence_data()`
- Looks for `propertiesOfMainSequenceStars.csv` in the project directory.
- Calls `core.databases.import_main_sequence_csv(csv_path)`.
- Prints row count on success.
- **GUI panel:** `ImportMainSequencePanel` in `gui/panels/csv_utility.py`.

### Option 55: Import Solar System Data — `import_solar_system_data()`
- Looks for `planetInfo.csv`, `moonInfo.csv`, `dwarfPlanetInfo.csv`,
  `asteroidsInfo.csv` in the project directory.
- Calls `core.databases.import_solar_system_csvs(data_dir)`.
- Prints per-table row counts on success.
- **GUI panel:** `ImportSolarSystemPanel` in `gui/panels/csv_utility.py`.

### Option 56: Import Honorverse Hyper Limits — `import_honorverse_hyper_data()`
- Looks for `spTypeHyperLM.csv` in the project directory.
- Calls `core.databases.import_honorverse_hyper_csv(csv_path)`.
- Prints row count on success.
- **GUI panel:** `ImportHonorversePanel` in `gui/panels/csv_utility.py`.

---

## GUI Panel Changes

### `gui/panels/csv_utility.py` additions

All four new panels follow the same pattern as the existing `ImportHwcPanel`:
- Single "Import" button.
- `run_in_background()` calls the relevant `core.databases.import_*` function.
- On success: shows row count in result area.
- On error: `show_error(msg)`.

New classes to add:
- `ImportMissionExocatPanel` (opt 53)
- `ImportMainSequencePanel` (opt 54)
- `ImportSolarSystemPanel` (opt 55)
- `ImportHonorversePanel` (opt 56)

Export all four from `gui/panels/__init__.py`.

### `gui/nav.py` changes

Add four entries under the **Utilities** category:

```python
("Import Mission Exocat Data",        "ImportMissionExocatPanel"),
("Import Main Sequence Star Props",   "ImportMainSequencePanel"),
("Import Solar System Data",          "ImportSolarSystemPanel"),
("Import Honorverse Hyper Limits",    "ImportHonorversePanel"),
```

Full Utilities section after Phase F:
```
Star Systems DB Query        CsvUtilityPanel
Export Star Systems to CSV   ExportStarSystemsPanel
Import HWC Data              ImportHwcPanel
Import Mission Exocat Data   ImportMissionExocatPanel
Import Main Sequence Star Props  ImportMainSequencePanel
Import Solar System Data     ImportSolarSystemPanel
Import Honorverse Hyper Limits  ImportHonorversePanel
```

---

## Updated CLI Menu (Utilities section)

```
  Utilities
  ---------
50. Star Systems CSV Query
51. Export Star Systems to CSV
52. Import HWC Data
53. Import Mission Exocat Data
54. Import Main Sequence Star Properties
55. Import Solar System Data
56. Import Honorverse Hyper Limits
```

---

## `gui/app.py` Changes

`close_conn()` is already called in `MainWindow.closeEvent`. No change needed — it
will actually close the connection once `core/db.py` is fully implemented.

---

## Files Changed Summary

| File | Change |
|---|---|
| `core/db.py` | Full implementation: connection, schema, auto-seed, helpers |
| `core/science.py` | Replace `_read_csv` calls with DB queries; remove `_read_csv` and `_DATA_DIR` |
| `core/databases.py` | Replace `_load_hwc` / `_load_mission_exocat` CSV reads with DB queries; rewrite `compute_star_systems_csv` to write to DB; add `export_star_systems_csv`, `import_hwc_csv`, `import_mission_exocat_csv`, `import_main_sequence_csv`, `import_solar_system_csvs`, `import_honorverse_hyper_csv` |
| `main.py` | Add `import_mission_exocat_data`, `import_main_sequence_data`, `import_solar_system_data`, `import_honorverse_hyper_data`; register opts 53–56 in `MENU_OPTIONS` |
| `gui/panels/csv_utility.py` | Add `ImportMissionExocatPanel`, `ImportMainSequencePanel`, `ImportSolarSystemPanel`, `ImportHonorversePanel` |
| `gui/panels/__init__.py` | Export four new panel classes |
| `gui/nav.py` | Add four new Utilities entries |
| `data/` | New directory (created by `core/db.py` at runtime; add to `.gitignore`) |

## `.gitignore` Addition

```
data/space_app.db
data/
```

The `data/` directory and the DB file are runtime artifacts — not committed to the
repo. The CSV source files in the project root remain committed as the canonical data
source for seeding.

---

## Implementation Order

1. `core/db.py` — schema + auto-seed (foundation everything else depends on)
2. `core/science.py` — swap read functions (verifiable immediately with opts 11–12, 14)
3. `core/databases.py` — swap `_load_hwc` / `_load_mission_exocat` (verify with opts 5, 6)
4. `core/databases.py` — rewrite `compute_star_systems_csv` opt 50 DB write
5. `core/databases.py` — add `export_star_systems_csv` (opt 51)
6. `core/databases.py` — add all `import_*` functions (opts 52–56)
7. `main.py` — add CLI functions for opts 51–56; register in `MENU_OPTIONS`
8. `gui/panels/csv_utility.py` — add `ExportStarSystemsPanel` + four import panels
9. `gui/panels/__init__.py` + `gui/nav.py` — wire up new panels
