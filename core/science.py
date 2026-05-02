import csv
import os

from core.db import get_conn


def compute_main_sequence_table() -> list:
    """Return all rows from main_sequence_stars as a list of dicts.

    Dict keys match the original CSV column names so all callers work unchanged.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            spectral_class  AS "Spectral Class",
            b_v             AS "B-V",
            teff_k          AS "Teeff(K)",
            abs_mag_vis     AS "AbsMag Vis.",
            abs_mag_bol     AS "AbsMag Bol.",
            bc              AS "Bolo. Corr. (BC)",
            lum             AS "Lum",
            radius          AS "R",
            mass            AS "M",
            density         AS "p (g/cm3)",
            lifetime        AS "Lifetime (years)"
        FROM main_sequence_stars
    """).fetchall()
    return [dict(r) for r in rows]


def compute_solar_system_tables() -> dict:
    """Return solar system body data from the DB.

    Returns a dict with keys:
        planets       — list of dicts sorted ascending by Semimajor Axis
        moons         — dict mapping planet name → list of moon dicts sorted by SemiMajor Axis
        dwarf_planets — list of dicts sorted ascending by Semimajor Axis
        asteroids     — list of dicts sorted ascending by Semimajor Axis
    """
    conn = get_conn()

    planets = [dict(r) for r in conn.execute("""
        SELECT
            planet_name    AS "Planet",
            mass           AS "Mass",
            diameter       AS "Diameter",
            period         AS "Period",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            moons          AS "Moons"
        FROM planets
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    moons_raw = [dict(r) for r in conn.execute("""
        SELECT
            satellite_name    AS "Satellite Name",
            planet_name       AS "Planet Name",
            diameter_km       AS "Diameter (km)",
            mean_radius_km    AS "Mean Radius (km)",
            mass_kg           AS "Mass (kg)",
            perigee_km        AS "Perigee (km)",
            apogee_km         AS "Apogee (km)",
            semimajor_axis_km AS "SemiMajor Axis (km)",
            eccentricity      AS "Eccentricity",
            period_days       AS "Period (days)",
            gravity           AS "Gravity (m/s^2)",
            escape_velocity   AS "Escape Velocity (km/s)"
        FROM moons
        ORDER BY CAST(semimajor_axis_km AS REAL)
    """).fetchall()]

    planet_order = ["Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    moons = {}
    for planet in planet_order:
        planet_moons = [m for m in moons_raw if m.get("Planet Name", "").strip() == planet]
        if planet_moons:
            moons[planet] = planet_moons

    dwarf_planets = [dict(r) for r in conn.execute("""
        SELECT
            name           AS "Name",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            period         AS "Period",
            mass           AS "Mass",
            diameter       AS "Diameter",
            moons          AS "Moons"
        FROM dwarf_planets
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    asteroids = [dict(r) for r in conn.execute("""
        SELECT
            name           AS "Name",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            period         AS "Period",
            diameter       AS "Diameter"
        FROM asteroids
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    return {
        "planets": planets,
        "moons": moons,
        "dwarf_planets": dwarf_planets,
        "asteroids": asteroids,
    }


def compute_honorverse_hyper_limits() -> list:
    """Return Honorverse hyper limit data from the DB.

    Returns a list of dicts with keys: spectral_class (str), lm (float), au (float).
    """
    LM_PER_AU = 8.3167
    conn = get_conn()
    rows = conn.execute(
        "SELECT spectral_class, lm FROM honorverse_hyper"
    ).fetchall()
    return [
        {"spectral_class": r["spectral_class"], "lm": r["lm"], "au": r["lm"] / LM_PER_AU}
        for r in rows
    ]


def compute_honorverse_acceleration_table() -> list:
    """Return the Honorverse acceleration-by-mass table as a list of dicts.

    Each dict has keys: mass_range, warship_normal, merchant_normal,
                        warship_hyper, merchant_hyper.
    """
    raw = [
        ("0-79,999 (FG/DD)",           "550 g", "253 g", "5280 g", "2429 g"),
        ("80-499,999 (CL/CA)",         "520 g", "240 g", "5018 g", "2308 g"),
        ("500,000-1,499,999 (BC)",     "500 g", "230 g", "4825 g", "2215 g"),
        ("1,500,000-4,999,999 (BB)",   "470 g", "215 g", "4536 g", "2085 g"),
        ("5,000,000-6,999,999 (DN)",   "450 g", "207 g", "4345 g", "1990 g"),
        ("7,000,000-8,499,999 (SD)",   "420 g", "190 g", "4053 g", "1860 g"),
    ]
    return [
        {
            "mass_range": mass_range,
            "warship_normal": w_n,
            "merchant_normal": m_n,
            "warship_hyper": w_h,
            "merchant_hyper": m_h,
        }
        for mass_range, w_n, m_n, w_h, m_h in raw
    ]


def compute_honorverse_effective_speed() -> dict:
    """Return Honorverse effective speed data for both band tables.

    Returns a dict with keys:
        bands          — list of dicts for Alpha–Iota (Table 1)
        expanded_bands — list of dicts for Alpha–Omega (Table 2)

    Each band dict has keys: band, bleed_off (Table 1 only), multiplier (Table 1 only),
    warship_xc, merchant_xc, merchant_note.
    """
    HOURS_PER_YEAR = 8765.8128

    def _ly_hr(xc):
        return xc / HOURS_PER_YEAR if xc else 0.0

    band_data = [
        ("Alpha",   "92%", 62,   37.2,  31.0,  ""),
        ("Beta",    "85%", 767,  460.2, 383.5, ""),
        ("Gamma",   "78%", 1473, 883.8, 736.5, ""),
        ("Delta",   "72%", 2178, 1306.8, 1089.0, ""),
        ("Epsilon", "66%", 2884, 1730.4, 1442.0, " *"),
        ("Zeta",    "61%", 3589, 2153.4, 1794.5, " *"),
        ("Eta",     "56%", 4294, 2576.4, 2147.0, " *"),
        ("Theta",   "52%", 5000, 3000.0, 2500.0, " *"),
        ("Iota",    "48%", 6000, 0,     0,      "*"),
    ]

    bands = []
    for band, bleed, mult, war_xc, mer_xc, note in band_data:
        bands.append({
            "band": band,
            "bleed_off": bleed,
            "multiplier": mult,
            "warship_xc": war_xc,
            "warship_ly_hr": _ly_hr(war_xc),
            "merchant_xc": mer_xc,
            "merchant_ly_hr": _ly_hr(mer_xc),
            "merchant_note": note,
        })

    expanded_data = [
        ("Alpha",   37.2,   31.0,   ""),
        ("Beta",    460.2,  383.5,  ""),
        ("Gamma",   883.8,  736.5,  ""),
        ("Delta",   1306.8, 1089.0, ""),
        ("Epsilon", 1730.4, 1442.0, " *"),
        ("Zeta",    2153.4, 1794.5, " *"),
        ("Eta",     2576.4, 2147.0, " *"),
        ("Theta",   3000.0, 2500.0, " *"),
        ("Iota",    3423.0, 2852.5, " *"),
        ("Kappa",   3846.6, 3205.5, " *"),
        ("Lambda",  4269.6, 3558.0, " *"),
        ("Mu",      4693.2, 3911.0, " *"),
        ("Nu",      5116.2, 4263.5, " *"),
        ("Xi",      5539.2, 4616.0, " *"),
        ("Omicron", 5962.8, 4969.0, " *"),
        ("Pi",      6385.8, 5321.2, " *"),
        ("Rho",     6809.4, 5674.2, " *"),
        ("Sigma",   7232.4, 6026.7, " *"),
        ("Tau",     7656.0, 6379.7, " *"),
        ("Upsilon", 8079.0, 6732.2, " *"),
        ("Phi",     8502.0, 7084.7, " *"),
        ("Chi",     8925.6, 7437.7, " *"),
        ("Psi",     9348.6, 7790.2, " *"),
        ("Omega",   9772.2, 8143.2, " *"),
    ]

    expanded_bands = []
    for band, war_xc, mer_xc, note in expanded_data:
        expanded_bands.append({
            "band": band,
            "warship_xc": war_xc,
            "warship_ly_hr": _ly_hr(war_xc),
            "merchant_xc": mer_xc,
            "merchant_ly_hr": _ly_hr(mer_xc),
            "merchant_note": note,
        })

    return {"bands": bands, "expanded_bands": expanded_bands}
