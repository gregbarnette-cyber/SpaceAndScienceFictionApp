# core/equations.py — Planetary, rotating habitat, and misc equation functions.
# Phase A: compute_star_luminosity (option 42).
# Phase B: options 34–41.

import math


# ── Physical constants (Phase H — Worldbuilding Calculators) ─────────────────
# Module-level so H1–H5 share one definition and cannot drift. The older
# functions above keep their inline constants (out of scope).

_G               = 6.674e-11          # gravitational constant, m³ kg⁻¹ s⁻²
_K_B             = 1.380649e-23       # Boltzmann constant, J/K
_EARTH_MASS_KG   = 5.972e24
_EARTH_RADIUS_KM = 6371.0
_EARTH_RADIUS_M  = 6.371e6
_SOLAR_MASS_KG   = 1.989e30
_M_PER_AU        = 149_597_870_700.0
_KM_PER_AU       = 149_597_870.7
_AMU_KG          = 1.66054e-27
_SEC_PER_YEAR    = 3.15576e7          # Julian year (365.25 d)


def _rocky_radius_km(mass_earth: float) -> float:
    """Approximate rocky-body radius from mass (R ∝ M^0.55). Shared by H1, H2."""
    return _EARTH_RADIUS_KM * mass_earth ** 0.55


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


# ── Worldbuilding calculators (Phase H) ──────────────────────────────────────
# Five pure-math tools for authors/worldbuilders. Unlike the older equation
# functions, these self-validate physical ranges and return {"error": str} for
# bad input, because they are also exposed via query.py subcommands.


def compute_roche_limit(primary_mass_earth: float, satellite_density_gcc: float,
                        primary_radius_earth: float = None) -> dict:
    """Rigid-body and fluid Roche limits for a satellite orbiting a primary.

    Works for planet–moon or star–planet scenarios.

    Args:
        primary_mass_earth:   primary body mass in Earth masses (> 0)
        satellite_density_gcc: satellite bulk density in g/cm³ (> 0)
        primary_radius_earth: primary radius in Earth radii (> 0); if omitted,
                              estimated from mass via R ∝ M^0.55

    Returns:
        dict with keys: primary_mass_earth, primary_radius_km, primary_density_gcc,
        satellite_density_gcc, rigid_km, rigid_au, fluid_km, fluid_au — or {"error": str}.
    """
    if primary_mass_earth <= 0 or satellite_density_gcc <= 0:
        return {"error": "Primary mass and satellite density must be positive."}
    if primary_radius_earth is not None and primary_radius_earth <= 0:
        return {"error": "Primary radius must be positive."}

    if primary_radius_earth is not None:
        R_km = primary_radius_earth * _EARTH_RADIUS_KM
    else:
        R_km = _rocky_radius_km(primary_mass_earth)
    R_m = R_km * 1000.0

    M_kg = primary_mass_earth * _EARTH_MASS_KG
    rho_primary_gcc = (3.0 * M_kg / (4.0 * math.pi * R_m ** 3)) / 1000.0
    ratio = (rho_primary_gcc / satellite_density_gcc) ** (1.0 / 3.0)

    rigid_km = R_km * 1.26 * ratio    # rigid coefficient = 2^(1/3) ≈ 1.26
    fluid_km = R_km * 2.456 * ratio

    return {
        "primary_mass_earth": primary_mass_earth,
        "primary_radius_km": R_km,
        "primary_density_gcc": rho_primary_gcc,
        "satellite_density_gcc": satellite_density_gcc,
        "rigid_km": rigid_km,
        "rigid_au": rigid_km / _KM_PER_AU,
        "fluid_km": fluid_km,
        "fluid_au": fluid_km / _KM_PER_AU,
    }


def compute_tidal_locking_time(primary_mass_earth: float, satellite_mass_earth: float,
                               sma_km: float, initial_rotation_hours: float,
                               rigidity_pa: float = 3e10, tidal_q: float = 100) -> dict:
    """Estimate the tidal-locking timescale of a satellite (MacDonald 1964 model).

    Order-of-magnitude estimate: the Love number k₂ is fixed at 0.3 (rocky-body
    simplification); rigidity_pa is echoed for transparency but not yet used in k₂.

    Args:
        primary_mass_earth:     primary mass in Earth masses (> 0)
        satellite_mass_earth:   satellite mass in Earth masses (> 0)
        sma_km:                 orbital semi-major axis in km (> 0)
        initial_rotation_hours: satellite's initial rotation period in hours (> 0)
        rigidity_pa:            satellite rigidity in Pa (> 0; default 3e10)
        tidal_q:                tidal quality factor (> 0; default 100)

    Returns:
        dict with keys: primary_mass_earth, satellite_mass_earth, sma_km,
        initial_rotation_hours, rigidity_pa, tidal_q, satellite_radius_km,
        lock_time_years, lock_time_gyr — or {"error": str}.
    """
    if (primary_mass_earth <= 0 or satellite_mass_earth <= 0 or sma_km <= 0
            or initial_rotation_hours <= 0):
        return {"error": "Masses, SMA, and rotation period must be positive."}
    if rigidity_pa <= 0 or tidal_q <= 0:
        return {"error": "Rigidity and tidal Q must be positive."}

    omega0 = 2.0 * math.pi / (initial_rotation_hours * 3600.0)
    a_m = sma_km * 1000.0
    R_sat_m = _rocky_radius_km(satellite_mass_earth) * 1000.0
    M_sat = satellite_mass_earth * _EARTH_MASS_KG
    M_pri = primary_mass_earth * _EARTH_MASS_KG

    I = 0.4 * M_sat * R_sat_m ** 2     # uniform sphere
    k2 = 0.3                            # rocky-body approximation

    T_sec = (omega0 * a_m ** 6 * I * tidal_q) / (3.0 * _G * M_pri ** 2 * k2 * R_sat_m ** 5)
    years = T_sec / _SEC_PER_YEAR

    return {
        "primary_mass_earth": primary_mass_earth,
        "satellite_mass_earth": satellite_mass_earth,
        "sma_km": sma_km,
        "initial_rotation_hours": initial_rotation_hours,
        "rigidity_pa": rigidity_pa,
        "tidal_q": tidal_q,
        "satellite_radius_km": R_sat_m / 1000.0,
        "lock_time_years": years,
        "lock_time_gyr": years / 1e9,
    }


def compute_hill_sphere(star_mass_solar: float, planet_mass_earth: float,
                        sma_au: float, eccentricity: float = 0) -> dict:
    """Hill sphere (gravitational sphere of influence) of a planet in a star system.

    Args:
        star_mass_solar:   host star mass in solar masses (> 0)
        planet_mass_earth: planet mass in Earth masses (> 0)
        sma_au:            planet's semi-major axis in AU (> 0)
        eccentricity:      orbital eccentricity (0 ≤ e < 1)

    Returns:
        dict with keys: star_mass_solar, planet_mass_earth, sma_au, eccentricity,
        hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au
        — or {"error": str}.
    """
    if star_mass_solar <= 0 or planet_mass_earth <= 0 or sma_au <= 0:
        return {"error": "Star mass, planet mass, and SMA must be positive."}
    if not (0 <= eccentricity < 1):
        return {"error": "Eccentricity must be in the range 0 ≤ e < 1."}

    M_star = star_mass_solar * _SOLAR_MASS_KG
    M_p = planet_mass_earth * _EARTH_MASS_KG
    a_m = sma_au * _M_PER_AU

    r_H_m = a_m * (1.0 - eccentricity) * (M_p / (3.0 * M_star)) ** (1.0 / 3.0)
    r_H_km = r_H_m / 1000.0
    stable_km = 0.5 * r_H_km

    return {
        "star_mass_solar": star_mass_solar,
        "planet_mass_earth": planet_mass_earth,
        "sma_au": sma_au,
        "eccentricity": eccentricity,
        "hill_radius_km": r_H_km,
        "hill_radius_au": r_H_m / _M_PER_AU,
        "stable_orbit_limit_km": stable_km,
        "stable_orbit_limit_au": (0.5 * r_H_m) / _M_PER_AU,
    }


def compute_binary_orbit_stability(mass1_solar: float, mass2_solar: float,
                                   binary_sma_au: float, test_sma_au: float,
                                   eccentricity: float = 0) -> dict:
    """Dynamical stability of a planet's orbit in a binary (Holman & Wiegert 1999).

    S-type = planet orbits one star (stable when test SMA < S-type critical SMA);
    P-type = circumbinary (stable when test SMA > P-type critical SMA).

    Args:
        mass1_solar:   first star mass in solar masses (> 0)
        mass2_solar:   second star mass in solar masses (> 0)
        binary_sma_au: binary separation (semi-major axis) in AU (> 0)
        test_sma_au:   planet's test semi-major axis in AU (> 0)
        eccentricity:  binary eccentricity (0 ≤ e < 1)

    Returns:
        dict with keys: mass1_solar, mass2_solar, mass_ratio, binary_sma_au,
        eccentricity, stype_critical_sma_au, ptype_critical_sma_au, test_sma_au,
        orbit_type, is_stable, stable_region_description — or {"error": str}.
    """
    if mass1_solar <= 0 or mass2_solar <= 0 or binary_sma_au <= 0 or test_sma_au <= 0:
        return {"error": "Masses and semi-major axes must be positive."}
    if not (0 <= eccentricity < 1):
        return {"error": "Eccentricity must be in the range 0 ≤ e < 1."}

    # Order so M1 ≥ M2 (μ ≤ 0.5 by convention).
    m1, m2 = mass1_solar, mass2_solar
    if m2 > m1:
        m1, m2 = m2, m1
    mu = m2 / (m1 + m2)
    e = eccentricity

    a_c_stype = (0.464 - 0.380 * mu - 0.631 * e + 0.586 * mu * e
                 + 0.150 * e ** 2 - 0.198 * mu * e ** 2) * binary_sma_au
    a_c_ptype = (1.60 + 5.10 * e - 2.22 * e ** 2 + 4.12 * mu - 4.27 * e * mu
                 - 5.09 * mu ** 2 + 4.61 * e ** 2 * mu ** 2) * binary_sma_au

    orbit_type = "S-type" if test_sma_au < binary_sma_au / 2.0 else "P-type"
    if orbit_type == "S-type":
        is_stable = test_sma_au < a_c_stype
    else:
        is_stable = test_sma_au > a_c_ptype

    description = (
        f"S-type orbits stable within {a_c_stype:.3f} AU of either star; "
        f"P-type orbits stable beyond {a_c_ptype:.3f} AU from the binary barycenter."
    )

    return {
        "mass1_solar": m1,
        "mass2_solar": m2,
        "mass_ratio": mu,
        "binary_sma_au": binary_sma_au,
        "eccentricity": e,
        "stype_critical_sma_au": a_c_stype,
        "ptype_critical_sma_au": a_c_ptype,
        "test_sma_au": test_sma_au,
        "orbit_type": orbit_type,
        "is_stable": is_stable,
        "stable_region_description": description,
    }


# Gases evaluated for atmospheric retention, molecular mass in amu (H₂…CO₂).
_ATMOSPHERE_GASES = [
    ("H2", 2), ("He", 4), ("CH4", 16), ("H2O", 18),
    ("N2", 28), ("O2", 32), ("CO2", 44),
]


def compute_atmosphere_retention(planet_mass_earth: float, planet_radius_earth: float,
                                 temperature_k: float) -> dict:
    """Which atmospheric gases a planet retains against Jeans escape.

    Uses the planet's *equilibrium* temperature, which underestimates exospheric
    temperature — so this simplified Jeans model is optimistic about retention.
    A worldbuilding heuristic, not an exospheric-escape simulation.

    Args:
        planet_mass_earth:   planet mass in Earth masses (> 0)
        planet_radius_earth: planet radius in Earth radii (> 0)
        temperature_k:       equilibrium temperature in K (> 0)

    Returns:
        dict with keys: planet_mass_earth, planet_radius_earth, temperature_k,
        v_escape_kms, gases (list of {gas, mol_mass_amu, lambda, v_thermal_kms,
        status}) — or {"error": str}.
    """
    if planet_mass_earth <= 0 or planet_radius_earth <= 0 or temperature_k <= 0:
        return {"error": "Mass, radius, and temperature must be positive."}

    M = planet_mass_earth * _EARTH_MASS_KG
    R = planet_radius_earth * _EARTH_RADIUS_M
    v_escape_kms = math.sqrt(2.0 * _G * M / R) / 1000.0

    gases = []
    for name, amu in _ATMOSPHERE_GASES:
        m = amu * _AMU_KG
        lam = (_G * M * m) / (_K_B * temperature_k * R)
        v_thermal_kms = math.sqrt(2.0 * _K_B * temperature_k / m) / 1000.0
        if lam > 6:
            status = "Retained"
        elif lam > 3:
            status = "Escaping slowly"
        else:
            status = "Lost rapidly"
        gases.append({
            "gas": name,
            "mol_mass_amu": amu,
            "lambda": lam,
            "v_thermal_kms": v_thermal_kms,
            "status": status,
        })

    return {
        "planet_mass_earth": planet_mass_earth,
        "planet_radius_earth": planet_radius_earth,
        "temperature_k": temperature_k,
        "v_escape_kms": v_escape_kms,
        "gases": gases,
    }


# ── Stellar evolution timeline (Phase L3) ────────────────────────────────────
# Pure-math, self-validating (like the Phase H calculators) so it can back both
# the GUI panel and the `stellar-evolution` query.py subcommand.

# Stage fractions are multiples of the main-sequence lifetime T_ms. T_ms itself
# uses the same 10^10 × (1/M)^2.5 relation as core/regions.py (`mainSeqLifeSpan`).
_EVOLUTION_STAGES = [
    ("Pre-Main Sequence",        0.01, "#aaaaaa"),
    ("Main Sequence",            1.00, "#ffe066"),
    ("Subgiant Branch",          0.15, "#ffaa33"),
    ("Red Giant Branch",         0.10, "#ff6600"),
    ("Horizontal Branch",        0.10, "#ff99cc"),
    ("Asymptotic Giant Branch",  0.02, "#cc3300"),
]


def compute_stellar_evolution(mass_solar: float, current_age_gyr: float = None) -> dict:
    """Evolutionary-stage durations and timeline for a star of a given mass.

    Valid for 0.1 ≤ mass_solar ≤ 20 M☉ (self-validating — outside that range
    returns {"error": str} rather than extrapolating). `current_age_gyr` is
    optional and may exceed the total lifetime (current_stage = "Beyond AGB").

    Special cases (values, not errors):
        mass < 0.8 M☉ — main-sequence lifetime exceeds a Hubble time; only the
                        Pre-MS and MS stages are emitted (post-MS not reachable),
                        and `low_mass` is True.
        mass > 8 M☉   — the AGB stage is replaced by "Supergiant → Supernova"
                        and `high_mass` is True.

    Returns {mass_solar, stages:[{name, start_gyr, end_gyr, duration_gyr, color}],
    total_gyr, ms_end_gyr, current_age_gyr, current_stage, low_mass, high_mass}.
    """
    if mass_solar is None or mass_solar < 0.1 or mass_solar > 20:
        return {"error": "Stellar mass must be between 0.1 and 20 M☉."}
    if current_age_gyr is not None and current_age_gyr < 0:
        return {"error": "Current age must be ≥ 0 Gyr."}

    t_ms_gyr  = (1e10 * (1.0 / mass_solar) ** 2.5) / 1e9
    low_mass  = mass_solar < 0.8
    high_mass = mass_solar > 8.0

    stages, t = [], 0.0
    for name, frac, color in _EVOLUTION_STAGES:
        # Below ~0.8 M☉ the MS lifetime exceeds the age of the universe, so no
        # post-MS stage is reachable — emit only Pre-MS and MS.
        if low_mass and name not in ("Pre-Main Sequence", "Main Sequence"):
            continue
        stage_name, stage_color = name, color
        if high_mass and name == "Asymptotic Giant Branch":
            stage_name, stage_color = "Supergiant → Supernova", "#7a0000"
        dur = frac * t_ms_gyr
        stages.append({
            "name": stage_name,
            "start_gyr": t,
            "end_gyr": t + dur,
            "duration_gyr": dur,
            "color": stage_color,
        })
        t += dur

    total_gyr  = t
    ms_end_gyr = next(s["end_gyr"] for s in stages if s["name"] == "Main Sequence")

    current_stage = None
    if current_age_gyr is not None:
        for s in stages:
            if s["start_gyr"] <= current_age_gyr < s["end_gyr"]:
                current_stage = s["name"]
                break
        if current_stage is None and current_age_gyr >= total_gyr:
            current_stage = "Beyond AGB"

    return {
        "mass_solar":      mass_solar,
        "stages":          stages,
        "total_gyr":       total_gyr,
        "ms_end_gyr":      ms_end_gyr,
        "current_age_gyr": current_age_gyr,
        "current_stage":   current_stage,
        "low_mass":        low_mass,
        "high_mass":       high_mass,
    }
