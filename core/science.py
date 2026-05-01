# core/science.py — Solar system data, main sequence properties, Honorverse tables.
# Phase A: compute_main_sequence_table (option 13).
# Phase B: options 12, 15, 16, 17.

import csv
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")


def _read_csv(filename: str) -> list:
    """Read a CSV file from the project data directory and return a list of dicts."""
    path = os.path.join(_DATA_DIR, filename)
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"Warning: Could not load {filename}: {e}")
        return []


def compute_main_sequence_table() -> list:
    """Return all rows from propertiesOfMainSequenceStars.csv as a list of dicts.

    Each dict uses the raw CSV column names as keys. Returns an empty list if
    the file cannot be read.
    """
    return _read_csv("propertiesOfMainSequenceStars.csv")


def compute_solar_system_tables() -> dict:
    """Return solar system body data from CSV files.

    Returns a dict with keys:
        planets      — list of dicts (from planetInfo.csv)
        moons        — dict mapping planet name → list of moon dicts (from moonInfo.csv)
        dwarf_planets — list of dicts (from dwarfPlanetInfo.csv)
        asteroids    — list of dicts sorted ascending by Semimajor Axis (from asteroidsInfo.csv)
    """
    def _sma(row, key):
        try:
            return float(row.get(key, "0") or "0")
        except (ValueError, TypeError):
            return 0.0

    planets = _read_csv("planetInfo.csv")
    planets.sort(key=lambda r: _sma(r, "Semimajor Axis"))

    moons_raw = _read_csv("moonInfo.csv")
    planet_order = ["Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    moons = {}
    for planet in planet_order:
        planet_moons = [m for m in moons_raw if m.get("Planet Name", "").strip() == planet]
        if planet_moons:
            planet_moons.sort(key=lambda r: _sma(r, "SemiMajor Axis (km)"))
            moons[planet] = planet_moons

    dwarf_planets = _read_csv("dwarfPlanetInfo.csv")
    dwarf_planets.sort(key=lambda r: _sma(r, "Semimajor Axis"))

    asteroids = _read_csv("asteroidsInfo.csv")
    asteroids.sort(key=lambda r: _sma(r, "Semimajor Axis"))

    return {
        "planets": planets,
        "moons": moons,
        "dwarf_planets": dwarf_planets,
        "asteroids": asteroids,
    }


def compute_honorverse_hyper_limits() -> list:
    """Return Honorverse hyper limit data from spTypeHyperLM.csv.

    Returns a list of dicts with keys: spectral_class (str), lm (float), au (float).
    """
    LM_PER_AU = 8.3167
    path = os.path.join(_DATA_DIR, "spTypeHyperLM.csv")
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for line in csv.reader(f):
                if len(line) < 2:
                    continue
                sp_class = line[0].strip().strip('"')
                try:
                    lm = float(line[1])
                except ValueError:
                    continue
                rows.append({"spectral_class": sp_class, "lm": lm, "au": lm / LM_PER_AU})
    except Exception as e:
        print(f"Warning: Could not load spTypeHyperLM.csv: {e}")
    return rows


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
