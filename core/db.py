import sqlite3
import os
import pathlib
import csv

# DB location: overridable via the SPACE_APP_DB env var (used for test isolation
# and alternate data stores); defaults to data/space_app.db under the repo root.
_DB_PATH = pathlib.Path(
    os.environ.get(
        "SPACE_APP_DB",
        pathlib.Path(__file__).resolve().parent.parent / "data" / "space_app.db",
    )
)
_conn: sqlite3.Connection | None = None

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


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


def rows_as_dicts(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def table_exists(table_name: str) -> bool:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()[0] > 0


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
        ("hwc",                "Habitable Worlds Catalog"),
        ("mission_exocat",     "Mission Exocat"),
        ("main_sequence_stars","Main Sequence Stars"),
        ("planets",            "Planets"),
        ("moons",              "Moons"),
        ("dwarf_planets",      "Dwarf Planets"),
        ("asteroids",          "Asteroids"),
        ("honorverse_hyper",   "Honorverse Hyper Limits"),
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
