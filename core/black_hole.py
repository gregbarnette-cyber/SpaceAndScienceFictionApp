"""Phase AI (Group O) — black holes & relativistic thermodynamics (Packet 24).

Ten ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculators: the horizon /
Hawking-thermodynamics / accretion / analog-horizon toolkit that feeds the Alcubierre
field-permeability / heat-isolation analogues (Group N) and the relativistic-thermo thread.

Physics (durable, closed-form on fundamental constants):
  * **O1 schwarzschild-radius** — r_s = 2GM/c².
  * **O2 hawking-temperature** — T_H = ℏc³/(8πGMk_B) (invertible).
  * **O3 black-hole-evaporation** — P = ℏc⁶/(15360πG²M²); τ = 5120πG²M³/(ℏc⁴) (invertible).
  * **O4 bekenstein-hawking-entropy** — S = k_B·A/(4l_p²), A = 4πr_s².
  * **O5 isco** — Schwarzschild r_ISCO = 6GM/c² = 3r_s; Kerr via Bardeen-Press-Teukolsky (spin a*).
  * **O6 kerr-horizon** — r± = (GM/c²)(1 ± √(1−a*²)); equatorial ergosphere r_E = 2GM/c².
  * **O7 bh-tidal-force** — Δa = 2GM·Δr/r³ (at the horizon Δa = Δr·c⁶/(4G²M²)); spaghettification radius.
  * **O8 eddington-luminosity** — L_Edd = 4πGM m_p c/σ_T; Ṁ_Edd = L_Edd/(ηc²).
  * **O9 unruh-temperature** — T_U = ℏa/(2πck_B) (invertible).
  * **O10 bekenstein-bound** — S ≤ 2πk_B RE/(ℏc); I ≤ 2πRE/(ℏc·ln2) bits.

Masses resolve through ``core.astro_bodies`` (multi-unit + object presets: Sun, Sgr A*, M87*, …);
constants from ``core.equations``. All non-rotating unless a spin input is given. No network, no DB,
no RNG, no time.
"""

import math

from core.equations import (
    _G, _C_MS, _HBAR, _K_B, _PLANCK_LENGTH, _M_PROTON, _THOMSON_CROSS_SECTION,
    _SOLAR_MASS_KG, _SOLAR_LUMINOSITY_W, _SEC_PER_YEAR, _STANDARD_GRAVITY, _M_PER_AU,
)
import core.astro_bodies as astro_bodies

_8PI_G_KB = 8.0 * math.pi * _G * _K_B
_LN2 = math.log(2.0)


def _resolve_object_mass(mass_kg, mass_msun, mass_mearth, mass_mjup, obj):
    """Resolve a mass from the multi-unit flags or an --object preset. Returns
    (mass_kg, object_display|None) or a {"error"} dict."""
    have_explicit = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup))
    if obj is not None:
        if have_explicit:
            return {"error": "Provide --object OR explicit mass flags, not both."}
        preset = astro_bodies.object_preset(obj)
        if "error" in preset:
            return preset
        return (preset["mass_kg"], preset["display"])
    m = astro_bodies.resolve_mass(mass_kg, mass_msun, mass_mearth, mass_mjup)
    if isinstance(m, dict):
        return m
    return (m[0], None)


def _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, obj):
    """Common (M, object_label) resolution shared by O1/O2/O4/O5/O6/O7/O8; error propagates."""
    return _resolve_object_mass(mass_kg, mass_msun, mass_mearth, mass_mjup, obj)


# ── O1 ───────────────────────────────────────────────────────────────────────
def compute_schwarzschild_radius(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                 object=None):
    """Schwarzschild radius r_s = 2GM/c² (O1)."""
    m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
    if isinstance(m, dict):
        return m
    M, label = m
    r_s = 2.0 * _G * M / _C_MS ** 2
    return {
        "schwarzschild_radius_m": r_s,
        "schwarzschild_radius_km": r_s / 1000.0,
        "schwarzschild_radius_au": r_s / _M_PER_AU,
        "mass_kg": M,
        "object": label,
        "model_note": "Schwarzschild radius r_s = 2GM/c² (non-rotating, uncharged event horizon).",
    }


# ── O2 ───────────────────────────────────────────────────────────────────────
def compute_hawking_temperature(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                object=None, temperature_k=None):
    """Hawking temperature T_H = ℏc³/(8πGMk_B), or the inverse T → M (O2)."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup, object))
    if have_mass == (temperature_k is not None):
        return {"error": "Provide either a mass (--mass-*/--object) OR --temperature-k, not both."}
    if temperature_k is not None:
        if temperature_k <= 0:
            return {"error": "Temperature must be positive."}
        M = _HBAR * _C_MS ** 3 / (_8PI_G_KB * temperature_k)
        label = None
        T = temperature_k
    else:
        m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
        if isinstance(m, dict):
            return m
        M, label = m
        T = _HBAR * _C_MS ** 3 / (_8PI_G_KB * M)
    return {
        "hawking_temperature_k": T,
        "mass_kg": M,
        "mass_msun": M / _SOLAR_MASS_KG,
        "object": label,
        "model_note": "Hawking temperature T_H = ℏc³/(8πGMk_B); Schwarzschild, semiclassical.",
    }


# ── O3 ───────────────────────────────────────────────────────────────────────
def compute_black_hole_evaporation(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                   object=None, lifetime_yr=None):
    """Hawking power + evaporation lifetime, or the inverse τ → M (O3)."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup, object))
    if have_mass == (lifetime_yr is not None):
        return {"error": "Provide either a mass (--mass-*/--object) OR --lifetime-yr, not both."}
    coeff_tau = 5120.0 * math.pi * _G ** 2 / (_HBAR * _C_MS ** 4)
    if lifetime_yr is not None:
        if lifetime_yr <= 0:
            return {"error": "Lifetime must be positive."}
        M = (lifetime_yr * _SEC_PER_YEAR / coeff_tau) ** (1.0 / 3.0)
        label = None
    else:
        m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
        if isinstance(m, dict):
            return m
        M, label = m
    power = _HBAR * _C_MS ** 6 / (15360.0 * math.pi * _G ** 2 * M ** 2)
    tau_s = coeff_tau * M ** 3
    return {
        "power_w": power,
        "lifetime_s": tau_s,
        "lifetime_yr": tau_s / _SEC_PER_YEAR,
        "mass_kg": M,
        "object": label,
        "model_note": ("Hawking P = ℏc⁶/(15360πG²M²); lifetime τ = 5120πG²M³/(ℏc⁴). The 5120π "
                       "coefficient is PHOTON-ONLY; with the full Standard-Model particle content "
                       "radiating, the coefficient falls and a black hole expiring now is a "
                       "few×10¹¹ kg."),
    }


# ── O4 ───────────────────────────────────────────────────────────────────────
def compute_bekenstein_hawking_entropy(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                       object=None, radius_m=None):
    """Bekenstein-Hawking entropy S = k_B·A/(4l_p²) (O4)."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup, object))
    if have_mass == (radius_m is not None):
        return {"error": "Provide either a mass (--mass-*/--object) OR --radius-m, not both."}
    if radius_m is not None:
        if radius_m <= 0:
            return {"error": "Radius must be positive."}
        r_s = radius_m
        M = None
    else:
        m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
        if isinstance(m, dict):
            return m
        M = m[0]
        r_s = 2.0 * _G * M / _C_MS ** 2
    area = 4.0 * math.pi * r_s ** 2
    s_over_kb = area / (4.0 * _PLANCK_LENGTH ** 2)
    return {
        "entropy_j_per_k": _K_B * s_over_kb,
        "entropy_over_kb": s_over_kb,
        "horizon_area_m2": area,
        "schwarzschild_radius_m": r_s,
        "mass_kg": M,
        "model_note": "Bekenstein-Hawking entropy S = k_B·A/(4l_p²), horizon area A = 4πr_s².",
    }


# ── O5 ───────────────────────────────────────────────────────────────────────
def compute_isco(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None, object=None,
                 spin=0.0, prograde=True):
    """Innermost stable circular orbit (Schwarzschild or Kerr) + binding efficiency (O5)."""
    m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
    if isinstance(m, dict):
        return m
    M, label = m
    if spin is None:
        spin = 0.0
    if spin < -1.0 or spin > 1.0:
        return {"error": "Spin a* must be in [-1, 1]."}

    r_g = _G * M / _C_MS ** 2
    r_s = 2.0 * r_g
    a = abs(spin)
    s = 1.0 if prograde else -1.0
    z1 = 1.0 + (1.0 - a * a) ** (1.0 / 3.0) * ((1.0 + a) ** (1.0 / 3.0) + (1.0 - a) ** (1.0 / 3.0))
    z2 = math.sqrt(3.0 * a * a + z1 * z1)
    r_isco_geo = 3.0 + z2 - s * math.sqrt((3.0 - z1) * (3.0 + z1 + 2.0 * z2))
    r_isco = r_isco_geo * r_g

    radicand = r_isco_geo ** 1.5 - 3.0 * r_isco_geo ** 0.5 + 2.0 * s * a
    if radicand <= 1e-9:                       # prograde extremal limit
        e_isco = 1.0 / math.sqrt(3.0)
    else:
        e_isco = (r_isco_geo ** 1.5 - 2.0 * r_isco_geo ** 0.5 + s * a) / (r_isco_geo ** 0.75 * math.sqrt(radicand))

    # local static-observer orbital speed — exact only for Schwarzschild (a*=0)
    orbital_v = None
    if a == 0.0 and r_isco > r_s:
        orbital_v = math.sqrt(r_g / (r_isco - r_s))

    return {
        "isco_radius_m": r_isco,
        "isco_radius_rs": r_isco / r_s,
        "orbital_velocity_c": orbital_v,
        "binding_efficiency": 1.0 - e_isco,
        "spin": spin,
        "prograde": prograde,
        "mass_kg": M,
        "object": label,
        "model_note": ("Schwarzschild r_ISCO = 6GM/c² = 3r_s (efficiency 5.72%); Kerr via "
                       "Bardeen-Press-Teukolsky (extremal prograde → 42.3%). binding_efficiency = "
                       "1 − E_ISCO (accretion rest-mass→radiation efficiency). orbital_velocity_c is "
                       "the local static-observer speed, exact only for a*=0 (null for spin≠0, which "
                       "needs frame-dragging terms)."),
    }


# ── O6 ───────────────────────────────────────────────────────────────────────
def compute_kerr_horizon(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                         object=None, spin=0.0):
    """Kerr outer/inner horizons + equatorial ergosphere (O6)."""
    m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
    if isinstance(m, dict):
        return m
    M, label = m
    if spin is None:
        spin = 0.0
    if spin < -1.0 or spin > 1.0:
        return {"error": "Spin a* must be in [-1, 1]."}
    r_g = _G * M / _C_MS ** 2
    root = math.sqrt(1.0 - spin * spin)
    return {
        "outer_horizon_m": r_g * (1.0 + root),
        "inner_horizon_m": r_g * (1.0 - root),
        "ergosphere_equatorial_m": 2.0 * r_g,
        "extremal": abs(spin) >= 1.0,
        "spin": spin,
        "mass_kg": M,
        "object": label,
        "frame_dragging_note": ("Between the outer horizon and the ergosphere (the ergoregion) "
                                "frame-dragging forces all observers to co-rotate; energy can be "
                                "extracted via the Penrose process."),
        "model_note": ("Kerr horizons r± = (GM/c²)(1 ± √(1−a*²)); equatorial ergosphere r_E = "
                       "2GM/c². a* = Jc/GM². a*=0 → Schwarzschild (r₊ = r_s); |a*|=1 → extremal "
                       "(r₊ = GM/c²)."),
    }


# ── O7 ───────────────────────────────────────────────────────────────────────
def compute_bh_tidal_force(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                           object=None, distance_m=None, distance_rs=None,
                           object_length_m=1.8, threshold_g=None):
    """Tidal (spaghettification) gradient at a distance, and the threshold radius (O7)."""
    m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
    if isinstance(m, dict):
        return m
    M, label = m
    if object_length_m is None or object_length_m <= 0:
        return {"error": "Object length must be positive (--object-length-m)."}
    r_s = 2.0 * _G * M / _C_MS ** 2

    if distance_m is not None and distance_rs is not None:
        return {"error": "Provide only one of --distance-m / --distance-rs."}
    if distance_m is not None:
        if distance_m <= 0:
            return {"error": "Distance must be positive."}
        r = distance_m
    elif distance_rs is not None:
        if distance_rs <= 0:
            return {"error": "Distance (in r_s) must be positive."}
        r = distance_rs * r_s
    else:
        r = r_s                              # default: evaluate at the horizon

    tidal = 2.0 * _G * M * object_length_m / r ** 3
    spag_radius = inside = None
    if threshold_g is not None:
        if threshold_g <= 0:
            return {"error": "Threshold must be positive (--threshold-g)."}
        a_thr = threshold_g * _STANDARD_GRAVITY
        spag_radius = (2.0 * _G * M * object_length_m / a_thr) ** (1.0 / 3.0)
        inside = spag_radius < r_s
    return {
        "tidal_acceleration_ms2": tidal,
        "tidal_gees": tidal / _STANDARD_GRAVITY,
        "distance_m": r,
        "schwarzschild_radius_m": r_s,
        "object_length_m": object_length_m,
        "spaghettification_radius_m": spag_radius,
        "inside_horizon": inside,
        "mass_kg": M,
        "object": label,
        "model_note": ("Tidal acceleration Δa = 2GM·Δr/r³ across a body of length Δr (Newtonian "
                       "tidal limit; at the horizon Δa = Δr·c⁶/(4G²M²) ∝ 1/M²). "
                       "spaghettification_radius is where Δa reaches --threshold-g; when it is "
                       "inside_horizon the tidal force at the horizon is survivable (SMBH case)."),
    }


# ── O8 ───────────────────────────────────────────────────────────────────────
def compute_eddington_luminosity(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                 object=None, efficiency=0.1):
    """Eddington luminosity + accretion rate (O8)."""
    m = _mass_and_note(mass_kg, mass_msun, mass_mearth, mass_mjup, object)
    if isinstance(m, dict):
        return m
    M, label = m
    if efficiency is None:
        efficiency = 0.1
    if efficiency <= 0 or efficiency > 1:
        return {"error": "Efficiency must be in (0, 1]."}
    l_edd = 4.0 * math.pi * _G * M * _M_PROTON * _C_MS / _THOMSON_CROSS_SECTION
    mdot = l_edd / (efficiency * _C_MS ** 2)
    return {
        "eddington_luminosity_w": l_edd,
        "eddington_luminosity_lsun": l_edd / _SOLAR_LUMINOSITY_W,
        "eddington_accretion_rate_kg_s": mdot,
        "eddington_accretion_msun_yr": mdot * _SEC_PER_YEAR / _SOLAR_MASS_KG,
        "efficiency": efficiency,
        "mass_kg": M,
        "object": label,
        "model_note": ("Eddington luminosity L_Edd = 4πGM m_p c/σ_T (radiation-pressure limit for "
                       "ionised hydrogen); Ṁ_Edd = L_Edd/(ηc²), radiative efficiency η (default 0.1, "
                       "≈ Schwarzschild ISCO)."),
    }


# ── O9 ───────────────────────────────────────────────────────────────────────
def compute_unruh_temperature(acceleration_ms2=None, acceleration_g=None, temperature_k=None):
    """Unruh temperature T_U = ℏa/(2πck_B), or the inverse T → a (O9)."""
    given = [k for k, v in (("acceleration_ms2", acceleration_ms2), ("acceleration_g", acceleration_g),
                            ("temperature_k", temperature_k)) if v is not None]
    if len(given) != 1:
        return {"error": "Provide exactly one of --acceleration-ms2 / --acceleration-g / --temperature-k."}
    coeff = _HBAR / (2.0 * math.pi * _C_MS * _K_B)
    if temperature_k is not None:
        if temperature_k <= 0:
            return {"error": "Temperature must be positive."}
        a = temperature_k / coeff
        T = temperature_k
    else:
        a = acceleration_ms2 if acceleration_ms2 is not None else acceleration_g * _STANDARD_GRAVITY
        if a <= 0:
            return {"error": "Acceleration must be positive."}
        T = coeff * a
    return {
        "unruh_temperature_k": T,
        "acceleration_ms2": a,
        "acceleration_g": a / _STANDARD_GRAVITY,
        "model_note": "Unruh temperature T_U = ℏa/(2πck_B) seen by a uniformly accelerated observer.",
    }


# ── O10 ──────────────────────────────────────────────────────────────────────
def compute_bekenstein_bound(radius_m=None, energy_j=None, mass_kg=None):
    """Bekenstein bound on entropy/information in a region (O10)."""
    if radius_m is None or radius_m <= 0:
        return {"error": "Provide a positive --radius-m."}
    if (energy_j is not None) == (mass_kg is not None):
        return {"error": "Provide exactly one of --energy-j / --mass-kg."}
    if energy_j is not None:
        if energy_j <= 0:
            return {"error": "Energy must be positive."}
        E = energy_j
    else:
        if mass_kg <= 0:
            return {"error": "Mass must be positive."}
        E = mass_kg * _C_MS ** 2
    s_over_kb = 2.0 * math.pi * radius_m * E / (_HBAR * _C_MS)
    return {
        "max_entropy_j_per_k": _K_B * s_over_kb,
        "max_entropy_over_kb": s_over_kb,
        "max_information_bits": s_over_kb / _LN2,
        "radius_m": radius_m,
        "energy_j": E,
        "model_note": ("Bekenstein bound S ≤ 2πk_B RE/(ℏc); information I ≤ 2πRE/(ℏc·ln2) bits — the "
                       "maximum entropy/information in a region of radius R with total energy E."),
    }
