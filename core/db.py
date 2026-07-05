import sqlite3
import os
import pathlib
import csv
import threading

# DB location: overridable via the SPACE_APP_DB env var (used for test isolation
# and alternate data stores); defaults to data/space_app.db under the repo root.
_DB_PATH = pathlib.Path(
    os.environ.get(
        "SPACE_APP_DB",
        pathlib.Path(__file__).resolve().parent.parent / "data" / "space_app.db",
    )
)

# P2.4 — per-thread connections. The GUI runs DB work on background QThreads;
# sharing one sqlite3.Connection across threads (even with check_same_thread=False)
# lets transactions interleave and corrupt state. Each thread now gets its own
# connection, cached in `_local.entry = (path_str, conn)` and reopened when the DB
# path changes. `_open_lock` serializes the open+schema+seed critical section so
# two threads can't race the auto-seed on a fresh DB. `_conn` is retained as a
# module-global mirror of the most-recently-opened connection: nothing outside this
# module reads it, but the test suite snapshots/restores it and uses `_conn = None`
# as an explicit "reopen" signal (always paired with a `_DB_PATH` swap) — both
# still honored below.
_local = threading.local()
_open_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


def get_conn() -> sqlite3.Connection:
    global _conn
    path = str(_DB_PATH)
    entry = getattr(_local, "entry", None)
    # Fast path: this thread already holds a live connection to the current DB
    # path, and no test has reset the global reopen signal.
    if entry is not None and entry[0] == path and _conn is not None:
        return entry[1]
    with _open_lock:
        entry = getattr(_local, "entry", None)
        if entry is not None and entry[0] == path and _conn is not None:
            return entry[1]
        if entry is not None:
            try:
                entry[1].close()
            except Exception:
                pass
            _local.entry = None
        _DB_PATH.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL + NORMAL keeps committed-transaction durability (the GCNS/Hypatia
        # validate-before-destroy gates rely on it) while cutting fsync overhead
        # on the ~331k/245k-row single-transaction imports; temp_store=MEMORY
        # keeps sort/temp B-trees off disk.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        _create_schema(conn)
        _auto_seed(conn)
        _local.entry = (path, conn)
        _conn = conn
        return conn


def close_conn():
    global _conn
    with _open_lock:
        entry = getattr(_local, "entry", None)
        if entry is not None:
            try:
                entry[1].close()
            except Exception:
                pass
            _local.entry = None
        _conn = None


def rows_as_dicts(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def table_exists(table_name: str) -> bool:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()[0] > 0


import re as _re

# Only tables matching this exact pattern may ever be dropped by the pruner.
_BACKUP_TABLE_RE = _re.compile(r"^star_systems_backup_\d{8}$")


def prune_star_systems_backups(keep_n: int = 3) -> dict:
    """Drop all but the newest `keep_n` star_systems_backup_YYYYMMDD tables.

    Backups are ranked by their 8-digit date stamp (lexicographic order on
    YYYYMMDD == chronological order). Only tables whose name matches
    `^star_systems_backup_\\d{8}$` are ever considered or dropped — no other
    table is touched. A no-op when `keep_n` or fewer backups exist.

    Returns {"dropped": [table_name, ...], "kept": [table_name, ...]} with both
    lists ordered newest → oldest.
    """
    conn = get_conn()
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'star_systems_backup_%'"
        ).fetchall()
        if _BACKUP_TABLE_RE.match(row[0])
    ]
    # Newest first (date stamp descending).
    names.sort(reverse=True)

    kept    = names[:keep_n]
    dropped = names[keep_n:]

    if dropped:
        with conn:
            for name in dropped:
                # name is guaranteed to match the strict backup pattern above,
                # so this f-string interpolation cannot inject arbitrary SQL.
                conn.execute(f"DROP TABLE IF EXISTS {name}")

    return {"dropped": dropped, "kept": kept}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _create_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS star_systems (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            star_name     TEXT NOT NULL,
            designations  TEXT,
            spectral_type TEXT,
            parallax      REAL,
            parsecs       REAL,
            light_years   REAL,
            app_magnitude REAL,
            ra            TEXT,
            dec           TEXT
        );

        -- Speeds up the Phase G search + opts 18/19 (ORDER BY light_years LIMIT,
        -- and light-year range filters) so they don't full-scan + temp-sort the
        -- whole table. Added via CREATE INDEX IF NOT EXISTS so existing DBs pick
        -- it up on the next connect.
        CREATE INDEX IF NOT EXISTS idx_star_systems_ly
            ON star_systems (light_years);

        CREATE TABLE IF NOT EXISTS main_sequence_stars (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
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

        CREATE TABLE IF NOT EXISTS planets (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            planet_name    TEXT,
            mass           TEXT,
            diameter       TEXT,
            period         TEXT,
            periastron     TEXT,
            semimajor_axis TEXT,
            apastron       TEXT,
            eccentricity   TEXT,
            moons          TEXT
        );

        CREATE TABLE IF NOT EXISTS moons (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            satellite_name    TEXT,
            planet_name       TEXT,
            diameter_km       TEXT,
            mean_radius_km    TEXT,
            mass_kg           TEXT,
            perigee_km        TEXT,
            apogee_km         TEXT,
            semimajor_axis_km TEXT,
            eccentricity      TEXT,
            period_days       TEXT,
            gravity           TEXT,
            escape_velocity   TEXT
        );

        CREATE TABLE IF NOT EXISTS dwarf_planets (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT,
            periastron     TEXT,
            semimajor_axis TEXT,
            apastron       TEXT,
            eccentricity   TEXT,
            period         TEXT,
            mass           TEXT,
            diameter       TEXT,
            moons          TEXT
        );

        CREATE TABLE IF NOT EXISTS asteroids (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT,
            periastron     TEXT,
            semimajor_axis TEXT,
            apastron       TEXT,
            eccentricity   TEXT,
            period         TEXT,
            diameter       TEXT
        );

        CREATE TABLE IF NOT EXISTS honorverse_hyper (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            spectral_class TEXT,
            lm             REAL
        );

        -- Gaia Catalogue of Nearby Stars (GCNS) backbone. Isolated from
        -- star_systems; populated only by the GCNS import (CLI option 58),
        -- never auto-seeded. GCNS = astrometry/distances; the SIMBAD layer
        -- (spectral_type/star_name/app_magnitude) is attached by cross-match.
        CREATE TABLE IF NOT EXISTS gcns_stars (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            gaia_source_id       INTEGER,          -- Gaia EDR3/DR3 id; NULL for missing_10mas rows
            ra                   REAL,             -- ICRS deg (J2016.0)
            dec                  REAL,             -- ICRS deg (J2016.0)
            parallax             REAL,             -- mas
            parallax_error       REAL,             -- mas
            dist_pc              REAL,             -- Bayesian median (dist_50), pc
            dist_lo_pc           REAL,             -- 16th percentile, pc
            dist_hi_pc           REAL,             -- 84th percentile, pc
            light_years          REAL,             -- dist_pc * 3.26156
            phot_g_mean_mag      REAL,             -- Gaia G  (NOT Johnson V)
            phot_bp_mean_mag     REAL,             -- Gaia BP
            phot_rp_mean_mag     REAL,             -- Gaia RP
            rv_kms               REAL,             -- adopted radial velocity, km/s
            wd_prob              REAL,             -- probability white dwarf
            astrom_reliable_prob REAL,             -- GCNS prob. of reliable astrometry
            spectral_type        TEXT,             -- SIMBAD (cross-match); NULL if unmatched
            star_name            TEXT,             -- SIMBAD common name (cross-match); NULL if unmatched
            app_magnitude        REAL,             -- SIMBAD Johnson V (cross-match); NULL if unmatched
            in_gcns              INTEGER,           -- always 1 (row is GCNS-sourced)
            in_simbad            INTEGER,           -- 1 if cross-matched to star_systems
            distance_method      TEXT,             -- 'gcns_bayesian' | 'gcns_missing_plx_inversion'
            gcns_table           TEXT,              -- 'main' | 'missing_10mas'
            system_id            INTEGER,           -- gcns_systems.system_id if a resolved-system member; else NULL
            n_components         INTEGER            -- component count of that system; NULL if not a member
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_gcns_source_id
            ON gcns_stars (gaia_source_id);
        CREATE INDEX IF NOT EXISTS idx_gcns_light_years
            ON gcns_stars (light_years);
        -- P2.2: name-lookup index for _resolve_gcns_row's
        -- `WHERE star_name = ? COLLATE NOCASE` (was a ~331k-row full scan on every
        -- name-based GCNS lookup). Declared COLLATE NOCASE so the case-insensitive
        -- predicate can use it. _create_schema re-runs this script on every connect,
        -- so existing databases pick the index up automatically.
        CREATE INDEX IF NOT EXISTS idx_gcns_stars_star_name
            ON gcns_stars (star_name COLLATE NOCASE);

        -- Single key/value provenance record for the GCNS build.
        CREATE TABLE IF NOT EXISTS gcns_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- GCNS resolved multiple-star systems, derived from gcns.resolvedss.
        -- That source table is PAIR-keyed (one row per resolved pair, columns
        -- source_id1/source_id2) and has NO system identifier. Systems here are
        -- connected components over the pair graph; system_id is synthetic and
        -- stable per build (components ordered by their smallest member id).
        -- Isolated from gcns_stars; populated only by the GCNS import (opt 58).
        CREATE TABLE IF NOT EXISTS gcns_systems (
            system_id        INTEGER PRIMARY KEY,  -- synthetic; stable per build
            n_components     INTEGER,              -- distinct member source_ids
            n_pairs          INTEGER,              -- gcns.resolvedss pair rows in this system
            any_bin          INTEGER,              -- 1 if any pair flagged 'bin' (probable >2 stars)
            any_bound        INTEGER,              -- 1 if any pair flagged gravitationally bound
            all_bound        INTEGER,              -- 1 if all pairs flagged bound
            max_proj_sep_au  REAL,                 -- widest projected separation among pairs, AU
            min_proj_sep_au  REAL,                 -- closest projected separation among pairs, AU
            n_in_gcns_stars  INTEGER               -- members also present in gcns_stars
        );

        -- Membership join table: one row per (system, component source_id).
        -- in_gcns_stars flags whether the member's source_id exists in gcns_stars
        -- (resolvedss members not in gcns_stars are retained here, flagged 0).
        CREATE TABLE IF NOT EXISTS gcns_system_members (
            system_id      INTEGER,
            gaia_source_id INTEGER,                -- Gaia EDR3 source_id of the component
            in_gcns_stars  INTEGER                 -- 1 if present in gcns_stars, else 0
        );
        CREATE INDEX IF NOT EXISTS idx_gcns_sysmem_system
            ON gcns_system_members (system_id);
        CREATE INDEX IF NOT EXISTS idx_gcns_sysmem_source
            ON gcns_system_members (gaia_source_id);

        -- Raw resolvedss pair edges, mapped into their derived system.
        CREATE TABLE IF NOT EXISTS gcns_system_pairs (
            system_id         INTEGER,
            source_id1        INTEGER,             -- primary (Gaia EDR3)
            source_id2        INTEGER,             -- secondary (Gaia EDR3)
            separation_arcsec REAL,                -- angular separation, arcsec
            mag_diff          REAL,                -- Gaia G magnitude difference
            proj_sep_au       REAL,                -- projected separation, AU
            bin               INTEGER,             -- 1 if pair probably part of a >2-star system
            bound             INTEGER              -- 1 if pair probably gravitationally bound
        );
        CREATE INDEX IF NOT EXISTS idx_gcns_syspair_system
            ON gcns_system_pairs (system_id);

        -- Hypatia Catalog abundance cache (Phase L4). Two-table EAV: one row per
        -- star in hypatia_cache, one row per (star, element) in hypatia_abundance.
        -- Isolated and NOT auto-seeded (like the GCNS tables); populated only by
        -- the Import Hypatia Cache utility via the bulk GET /data endpoint. /data
        -- carries the catalog-averaged [X/H] MEAN per element (the search filter
        -- key); the spread (std/min/max/n) and UVW kinematics are NOT bulk-
        -- available (the u/v/w /data axes collide with the U/V/W element symbols),
        -- so those columns stay NULL — the live per-star compute_hypatia_data
        -- still serves the full detail. fe_h is denormalized from the 'Fe' row;
        -- light_years is precomputed as distance_pc * 3.26156.
        CREATE TABLE IF NOT EXISTS hypatia_cache (
            star_name    TEXT PRIMARY KEY,   -- SIMBAD main_id (whitespace-normalized)
            hip          TEXT,
            hd           TEXT,
            teff         REAL,
            logg         REAL,
            vmag         REAL,
            bv           REAL,
            distance_pc  REAL,
            disk         TEXT,               -- Hypatia disk code (0=thin, 1=thick, …)
            u_vel        REAL,               -- NULL (not bulk-available)
            v_vel        REAL,               -- NULL (not bulk-available)
            w_vel        REAL,               -- NULL (not bulk-available)
            pm_ra        REAL,
            pm_dec       REAL,
            fe_h         REAL,               -- denormalized [Fe/H] mean
            light_years  REAL,               -- distance_pc * 3.26156
            fetched_date TEXT
        );
        CREATE TABLE IF NOT EXISTS hypatia_abundance (
            star_name TEXT,
            element   TEXT,                  -- API casing: 'Fe', 'Mg', 'Ba_II'
            mean      REAL,                  -- [X/H] (Lodders 2009)
            std       REAL,                  -- NULL (not bulk-available)
            min       REAL,                  -- NULL (not bulk-available)
            max       REAL,                  -- NULL (not bulk-available)
            n         INTEGER,               -- NULL (not bulk-available)
            PRIMARY KEY (star_name, element)
        );
        CREATE TABLE IF NOT EXISTS hypatia_meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE INDEX IF NOT EXISTS idx_hyp_cache_feh  ON hypatia_cache(fe_h);
        CREATE INDEX IF NOT EXISTS idx_hyp_cache_teff ON hypatia_cache(teff);
        CREATE INDEX IF NOT EXISTS idx_hyp_cache_ly   ON hypatia_cache(light_years);
        CREATE INDEX IF NOT EXISTS idx_hyp_abund_elem ON hypatia_abundance(element, mean);

        -- Project Workspaces (Phase S). Two additive, NOT-auto-seeded tables: a
        -- named project collects real (looked-up) + procedurally-generated systems
        -- with freeform notes, exported as one multi-system dossier. A generated
        -- member stores its generate_system PARAMS (generated_spec JSON) so it
        -- re-creates byte-identically (the R determinism contract), never a frozen
        -- body. Mutations are GUI-only; query.py exposes read-only project-list /
        -- project-get.
        CREATE TABLE IF NOT EXISTS projects (
            project_id   INTEGER PRIMARY KEY,
            name         TEXT UNIQUE NOT NULL,
            description  TEXT,
            created_date TEXT
        );
        CREATE TABLE IF NOT EXISTS project_members (
            project_id     INTEGER NOT NULL,
            star_name      TEXT NOT NULL,
            note           TEXT,
            source         TEXT NOT NULL,        -- 'looked_up' | 'generated'
            generated_seed INTEGER,              -- generated only (display convenience)
            generated_spec TEXT,                 -- generated only: JSON of the generate_system params
            added_date     TEXT,
            PRIMARY KEY (project_id, star_name)
        );
        CREATE INDEX IF NOT EXISTS idx_project_members_pid ON project_members(project_id);
    """)
    conn.commit()
    _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection):
    """Additive column migrations for tables that may predate a newer schema.

    CREATE TABLE IF NOT EXISTS never alters an existing table, so columns added
    after a table was first created must be patched in via ALTER TABLE. Each is
    guarded by a PRAGMA check so re-running is a no-op.
    """
    def _has_col(table, col):
        return any(r["name"] == col
                   for r in conn.execute(f"PRAGMA table_info({table})").fetchall())

    for table, col, decl in [
        ("gcns_stars", "system_id",    "INTEGER"),
        ("gcns_stars", "n_components", "INTEGER"),
    ]:
        try:
            if not _has_col(table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()


# ---------------------------------------------------------------------------
# Auto-seed
# ---------------------------------------------------------------------------

_STATIC_TABLES = [
    ("main_sequence_stars", "propertiesOfMainSequenceStars.csv", "_seed_main_sequence"),
    ("planets",             "planetInfo.csv",                    "_seed_planets"),
    ("moons",               "moonInfo.csv",                      "_seed_moons"),
    ("dwarf_planets",       "dwarfPlanetInfo.csv",               "_seed_dwarf_planets"),
    ("asteroids",           "asteroidsInfo.csv",                 "_seed_asteroids"),
    ("honorverse_hyper",    "spTypeHyperLM.csv",                 "_seed_honorverse_hyper"),
]


def _auto_seed(conn: sqlite3.Connection):
    for table, csv_filename, seeder_name in _STATIC_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count > 0:
            continue
        csv_path = _PROJECT_ROOT / csv_filename
        if not csv_path.exists():
            continue
        seeder = globals()[seeder_name]
        try:
            with conn:
                seeder(conn, csv_path)
        except Exception as e:
            print(f"Warning: auto-seed of {table} failed: {e}")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_main_sequence(conn: sqlite3.Connection, csv_path: pathlib.Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    conn.executemany(
        """INSERT INTO main_sequence_stars
           (spectral_class, b_v, teff_k, abs_mag_vis, abs_mag_bol, bc,
            lum, radius, mass, density, lifetime)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r.get("Spectral Class", ""),
                r.get("B-V", ""),
                r.get("Teeff(K)", ""),
                r.get("AbsMag Vis.", ""),
                r.get("AbsMag Bol.", ""),
                r.get("Bolo. Corr. (BC)", ""),
                r.get("Lum", ""),
                r.get("R", ""),
                r.get("M", ""),
                r.get("p (g/cm3)", ""),
                r.get("Lifetime (years)", ""),
            )
            for r in rows
        ],
    )


def _seed_planets(conn: sqlite3.Connection, csv_path: pathlib.Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    conn.executemany(
        """INSERT INTO planets
           (planet_name, mass, diameter, period, periastron,
            semimajor_axis, apastron, eccentricity, moons)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r.get("Planet", ""),
                r.get("Mass", ""),
                r.get("Diameter", ""),
                r.get("Period", ""),
                r.get("Periastron", ""),
                r.get("Semimajor Axis", ""),
                r.get("Apastron", ""),
                r.get("Eccentricity", ""),
                r.get("Moons", ""),
            )
            for r in rows
        ],
    )


def _seed_moons(conn: sqlite3.Connection, csv_path: pathlib.Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    conn.executemany(
        """INSERT INTO moons
           (satellite_name, planet_name, diameter_km, mean_radius_km, mass_kg,
            perigee_km, apogee_km, semimajor_axis_km, eccentricity,
            period_days, gravity, escape_velocity)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r.get("Satellite Name", ""),
                r.get("Planet Name", ""),
                r.get("Diameter (km)", ""),
                r.get("Mean Radius (km)", ""),
                r.get("Mass (kg)", ""),
                r.get("Perigee (km)", ""),
                r.get("Apogee (km)", ""),
                r.get("SemiMajor Axis (km)", ""),
                r.get("Eccentricity", ""),
                r.get("Period (days)", ""),
                r.get("Gravity (m/s^2)", ""),
                r.get("Escape Velocity (km/s)", ""),
            )
            for r in rows
        ],
    )


def _seed_dwarf_planets(conn: sqlite3.Connection, csv_path: pathlib.Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    conn.executemany(
        """INSERT INTO dwarf_planets
           (name, periastron, semimajor_axis, apastron, eccentricity,
            period, mass, diameter, moons)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r.get("Name", ""),
                r.get("Periastron", ""),
                r.get("Semimajor Axis", ""),
                r.get("Apastron", ""),
                r.get("Eccentricity", ""),
                r.get("Period", ""),
                r.get("Mass", ""),
                r.get("Diameter", ""),
                r.get("Moons", ""),
            )
            for r in rows
        ],
    )


def _seed_asteroids(conn: sqlite3.Connection, csv_path: pathlib.Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    conn.executemany(
        """INSERT INTO asteroids
           (name, periastron, semimajor_axis, apastron, eccentricity, period, diameter)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r.get("Name", ""),
                r.get("Periastron", ""),
                r.get("Semimajor Axis", ""),
                r.get("Apastron", ""),
                r.get("Eccentricity", ""),
                r.get("Period", ""),
                r.get("Diameter", ""),
            )
            for r in rows
        ],
    )


def get_table_status() -> list:
    """Return row counts for all application tables, in menu order."""
    conn = get_conn()
    tables = [
        ("star_systems",       "Star Systems"),
        ("gcns_stars",         "GCNS Stars"),
        ("gcns_systems",       "GCNS Systems"),
        ("gcns_meta",          "GCNS Meta"),
        ("hypatia_cache",      "Hypatia Cache"),
        ("hwc",                "Habitable Worlds Catalog"),
        ("mission_exocat",     "Mission Exocat"),
        ("main_sequence_stars","Main Sequence Stars"),
        ("planets",            "Planets"),
        ("moons",              "Moons"),
        ("dwarf_planets",      "Dwarf Planets"),
        ("asteroids",          "Asteroids"),
        ("honorverse_hyper",   "Honorverse Hyper Limits"),
        ("projects",           "Projects"),
        ("project_members",    "Project Members"),
    ]
    result = []
    for table, label in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            count = 0
        result.append({"table": label, "rows": count, "populated": count > 0})
    return result


def _seed_honorverse_hyper(conn: sqlite3.Connection, csv_path: pathlib.Path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for line in csv.reader(f):
            if len(line) < 2:
                continue
            sp_class = line[0].strip().strip('"')
            try:
                lm = float(line[1])
            except ValueError:
                continue
            rows.append((sp_class, lm))
    conn.executemany(
        "INSERT INTO honorverse_hyper (spectral_class, lm) VALUES (?, ?)",
        rows,
    )
