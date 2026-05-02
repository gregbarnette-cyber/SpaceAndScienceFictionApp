import sqlite3
import os
import pathlib
import csv

_DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "space_app.db"
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
    """)
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
