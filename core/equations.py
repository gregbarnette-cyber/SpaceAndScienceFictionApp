# core/equations.py — Planetary, rotating habitat, and misc equation functions.
# Phase A: compute_star_luminosity (option 42).
# Phase B: options 34–41.

import math


# ── Kopparapu et al. 2014 HZ coefficients ────────────────────────────────────

_KOPPARAPU_PARAMS = {
    "rv":   (1.776,  2.136e-4,  2.533e-8,  -1.332e-11, -3.097e-15),
    "rg5":  (1.188,  1.433e-4,  1.707e-8,  -8.968e-12, -2.084e-15),
    "rg01": (0.99,   1.209e-4,  1.404e-8,  -7.418e-12, -1.713e-15),
    "rg":   (1.107,  1.332e-4,  1.580e-8,  -8.308e-12, -1.931e-15),
    "mg":   (0.356,  6.171e-5,  1.698e-9,  -3.198e-12, -5.575e-16),
    "em":   (0.320,  5.547e-5,  1.526e-9,  -2.874e-12, -5.011e-16),
}

_ZONE_DEFS = [
    ("Optimistic Inner HZ (Recent Venus)",                          "rv"),
    ("Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",   "rg5"),
    ("Conservative Inner HZ (Runaway Greenhouse)",                  "rg"),
    ("Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)", "rg01"),
    ("Conservative Outer HZ (Maximum Greenhouse)",                  "mg"),
    ("Optimistic Outer HZ (Early Mars)",                            "em"),
]


def _kopparapu_seff(teff: float, zone: str) -> float:
    """Return Kopparapu et al. 2014 Seff boundary for the given zone key."""
    tS = teff - 5780.0
    SeffSUN, a, b, c, d = _KOPPARAPU_PARAMS[zone]
    return SeffSUN + a * tS + b * tS**2 + c * tS**3 + d * tS**4


# ── Star luminosity ───────────────────────────────────────────────────────────

def compute_star_luminosity(radius: float, temp: float) -> dict:
    """Compute stellar luminosity from radius and temperature.

    Args:
        radius: stellar radius in solar radii (R☉)
        temp:   effective temperature in Kelvin

    Returns:
        dict with keys: radius, temp, luminosity (all floats)
    """
    luminosity = radius ** 2 * (temp / 5778.0) ** 4
    return {"radius": radius, "temp": temp, "luminosity": luminosity}


# ── Planetary orbit ───────────────────────────────────────────────────────────

def compute_orbit_periastron_apastron(sma: float, ecc: float) -> dict:
    """Compute periastron, apastron, and eccentricity in AU.

    Args:
        sma: semi-major axis in AU (> 0)
        ecc: orbital eccentricity (0 ≤ e < 1)

    Returns:
        dict with keys: sma, ecc, periastron, apastron, ecc_au (all floats)
    """
    return {
        "sma": sma,
        "ecc": ecc,
        "periastron": sma * (1.0 - ecc),
        "apastron": sma * (1.0 + ecc),
        "ecc_au": sma * ecc,
    }


def compute_moon_orbital_distance(planet_mass_earth: float, day_hours: float) -> dict:
    """Orbital distance of an Earth-sized moon for a given planetary mass and day length.

    Uses Kepler's third law: r = (G × M × T² / (4π²))^(1/3)

    Args:
        planet_mass_earth: planetary mass in Earth masses (> 0)
        day_hours:         desired day length in hours (> 0)

    Returns:
        dict with keys: planet_mass_earth, day_hours, orbital_distance_km (all floats)
    """
    EARTH_MASS_KG = 5.972e24
    G = 6.674e-11
    T_sec = day_hours * 3600.0
    M_kg = planet_mass_earth * EARTH_MASS_KG
    r_m = (G * M_kg * T_sec ** 2 / (4.0 * math.pi ** 2)) ** (1.0 / 3.0)
    return {
        "planet_mass_earth": planet_mass_earth,
        "day_hours": day_hours,
        "orbital_distance_km": r_m / 1000.0,
    }


# ── Rotating habitat ──────────────────────────────────────────────────────────

def compute_centrifugal_gravity_acceleration(rpm: float, radius_m: float) -> dict:
    """Centrifugal acceleration at a given radius and rotation rate.

    a = ω² × r,  where ω (rad/s) = rpm × 2π / 60

    Args:
        rpm:      rotation rate in revolutions per minute (> 0)
        radius_m: distance from the centre of rotation in metres (> 0)

    Returns:
        dict with keys: rpm, radius_m, accel_ms2 (all floats)
    """
    omega = rpm * 2.0 * math.pi / 60.0
    return {"rpm": rpm, "radius_m": radius_m, "accel_ms2": omega ** 2 * radius_m}


def compute_centrifugal_gravity_distance(rpm: float, accel_ms2: float) -> dict:
    """Distance from the centre of rotation given rotation rate and desired acceleration.

    r = a / ω²,  where ω (rad/s) = rpm × 2π / 60

    Args:
        rpm:       rotation rate in revolutions per minute (> 0)
        accel_ms2: desired centrifugal gravity in m/s² (> 0)

    Returns:
        dict with keys: rpm, accel_ms2, radius_m (all floats)
    """
    omega = rpm * 2.0 * math.pi / 60.0
    return {"rpm": rpm, "accel_ms2": accel_ms2, "radius_m": accel_ms2 / omega ** 2}


def compute_centrifugal_gravity_rpm(accel_ms2: float, radius_m: float) -> dict:
    """Rotation rate needed to produce a given acceleration at a given radius.

    ω = √(a / r),  rpm = ω × 60 / (2π)

    Args:
        accel_ms2: desired centrifugal gravity in m/s² (> 0)
        radius_m:  distance from the centre of rotation in metres (> 0)

    Returns:
        dict with keys: accel_ms2, radius_m, rpm (all floats)
    """
    omega = math.sqrt(accel_ms2 / radius_m)
    return {"accel_ms2": accel_ms2, "radius_m": radius_m, "rpm": omega * 60.0 / (2.0 * math.pi)}


# ── Habitable zone ────────────────────────────────────────────────────────────

def compute_habitable_zone(teff: float, luminosity: float) -> list:
    """Compute Kopparapu et al. HZ boundary distances for all six zones.

    Args:
        teff:       stellar effective temperature in K
        luminosity: stellar luminosity in solar units

    Returns:
        list of dicts, one per zone, each with keys:
            zone_name (str), key (str), au (float), lm (float), seff (float)
    """
    AU_TO_LM = 8.3167
    zones = []
    for zone_name, key in _ZONE_DEFS:
        seff = _kopparapu_seff(teff, key)
        au = math.sqrt(luminosity / seff)
        zones.append({
            "zone_name": zone_name,
            "key": key,
            "au": au,
            "lm": au * AU_TO_LM,
            "seff": seff,
        })
    return zones


def compute_habitable_zone_sma(teff: float, luminosity: float, sma: float) -> dict:
    """Compute HZ boundaries plus the object's Seff and HZ membership verdict.

    Args:
        teff:       stellar effective temperature in K
        luminosity: stellar luminosity in solar units
        sma:        object's semi-major axis in AU (> 0)

    Returns:
        dict with keys:
            zones         — list of zone dicts (same structure as compute_habitable_zone)
            planet_seff   — float, Seff at the object's orbit
            verdict       — str, human-readable HZ membership description
    """
    zones = compute_habitable_zone(teff, luminosity)
    planet_seff = ((1.0 / sma) ** 2) * luminosity

    # Build a quick lookup for verdict
    seff_map = {z["key"]: z["seff"] for z in zones}
    seff_rv = seff_map["rv"]
    seff_rg = seff_map["rg"]
    seff_mg = seff_map["mg"]
    seff_em = seff_map["em"]

    if planet_seff < seff_em:
        verdict = "This object is NOT in the Habitable Zone (Beyond Early Mars)"
    elif planet_seff <= seff_mg:
        verdict = "This object is in the Optimistic Habitable Zone (Between Maximum Greenhouse and Early Mars)"
    elif planet_seff <= seff_rg:
        verdict = "This object is in the Conservative Habitable Zone (Between Runaway Greenhouse and Maximum Greenhouse)"
    elif planet_seff <= seff_rv:
        verdict = "This object is in the Optimistic Habitable Zone (Between Recent Venus and Runaway Greenhouse)"
    else:
        verdict = "This object is NOT in the Habitable Zone (Interior to Recent Venus)"

    return {"zones": zones, "planet_seff": planet_seff, "verdict": verdict}
