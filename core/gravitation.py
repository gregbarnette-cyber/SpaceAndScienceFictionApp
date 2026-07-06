"""Phase AE (Group K) — arrival geometry & gravitation (Packet 20).

Four ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculators for the
gravitational-well + capture geometry an STL ship needs on arrival/departure — complementing
the existing ``gravity-*`` / ``hill-sphere`` / ``roche-limit`` set, which has no escape
velocity, well-depth energetics, Laplace sphere-of-influence, or hyperbolic-capture Δv.

Physics (durable, closed-form on fundamental constants — nothing fitted):
  * **K1 escape-velocity** — v_esc = √(2GM/r); v_circ = √(GM/r) = v_esc/√2; specific escape
    energy = ½v_esc².
  * **K2 gravitational-potential** — Φ = −GM/r (J/kg); well-depth r₁→r₂ = GM(1/r₁ − 1/r₂);
    binding energy of a payload = payload·well-depth; Δv-equivalent = √(2·|well-depth|).
  * **K3 sphere-of-influence** — Laplace r_SOI = a·(m/M)^(2/5), reported beside the Hill radius
    r_Hill = a·(m/3M)^(1/3) (the two answer different capture questions; the packet needs both).
  * **K4 hyperbolic-approach** — at periapsis r_p, v_p = √(v∞² + 2GM/r_p); C₃ = v∞²; capture Δv
    = v_p − v_capture (circular √(GM/r_p) | parabolic √(2GM/r_p) | elliptical vis-viva).

Masses/radii are resolved through ``core.astro_bodies`` (shared multi-unit gate + presets), so
K's units and body table stay consistent with Groups L/N/O. Constants come from
``core.equations``. No network, no DB, no RNG, no time.
"""

import math

from core.equations import _G, _C_MS, _KM_PER_AU, _M_PER_AU
import core.astro_bodies as astro_bodies

_NOTE_ESC = ("Newtonian escape/circular speed v_esc = √(2GM/r), v_circ = v_esc/√2. Point-mass "
             "(spherically-symmetric) field; non-relativistic. Preset radii are the body's mean "
             "surface radius except giant planets, which use the 1-bar EQUATORIAL radius — so a "
             "gas-giant v_esc is the equatorial-surface value.")
_NOTE_POT = ("Newtonian gravitational potential Φ = −GM/r; well-depth between two radii "
             "GM(1/r_from − 1/r_to) (r_to = ∞ → GM/r_from). Δv-equivalent = √(2·|well-depth|) is "
             "the speed matching that energy per kg from rest; point-mass field, non-relativistic.")
_NOTE_SOI = ("Laplace sphere of influence r_SOI = a·(m/M)^(2/5) (patched-conic hand-off radius), "
             "reported beside the Hill radius r_Hill = a·(m/3M)^(1/3). Circular-orbit form (no "
             "eccentricity term); m ≪ M assumed.")
_NOTE_HYP = ("Hyperbolic capture geometry: v_p = √(v∞² + 2GM/r_p), C₃ = v∞²; capture Δv = v_p − "
             "v_capture for the chosen bound target (circular/parabolic/elliptical vis-viva). "
             "Impulsive single-burn at periapsis; point-mass field, non-relativistic; ignores "
             "drag/oblateness/third-body effects.")


def _resolve_length(name, required, *unit_specs):
    """Resolve a length given in exactly one of several units → metres, or {"error"}.

    ``unit_specs`` = (value, factor_to_m, unit_label) triples. When ``required`` is False and
    none is supplied, returns None (caller supplies the default, e.g. ∞).
    """
    given = [(v, f, u) for (v, f, u) in unit_specs if v is not None]
    units = "/".join(u for _, _, u in unit_specs)
    if not given:
        return {"error": f"Provide {name} ({units})."} if required else None
    if len(given) > 1:
        return {"error": f"Provide only one {name} unit ({units})."}
    value, factor, _ = given[0]
    if value <= 0:
        return {"error": f"{name} must be positive."}
    return value * factor


def _mass_from_args(mass_kg, mass_msun, mass_mearth, mass_mjup, body, name="mass"):
    """Resolve a mass from either a --body preset or the multi-unit mass flags.

    Returns (mass_kg, body_display|None) or a {"error"} dict. A preset and explicit mass
    flags together is an error.
    """
    have_explicit = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup))
    if body is not None:
        if have_explicit:
            return {"error": f"Provide --body OR explicit {name} flags, not both."}
        preset = astro_bodies.body_preset(body)
        if "error" in preset:
            return preset
        return (preset["mass_kg"], preset["display"])
    resolved = astro_bodies.resolve_mass(mass_kg, mass_msun, mass_mearth, mass_mjup, name=name)
    if isinstance(resolved, dict):
        return resolved
    return (resolved[0], None)


# ── K1 ───────────────────────────────────────────────────────────────────────
def compute_escape_velocity(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                            radius_m=None, radius_rsun=None, radius_rearth=None, distance_au=None,
                            body=None):
    """Escape / circular speed from a body or at a distance in its field (K1)."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup))
    have_radius = any(v is not None for v in (radius_m, radius_rsun, radius_rearth, distance_au))
    if body is not None:
        if have_mass or have_radius:
            return {"error": "Provide --body OR explicit mass+radius flags, not both."}
        preset = astro_bodies.body_preset(body)
        if "error" in preset:
            return preset
        M, R, body_label = preset["mass_kg"], preset["radius_m"], preset["display"]
    else:
        m = astro_bodies.resolve_mass(mass_kg, mass_msun, mass_mearth, mass_mjup)
        if isinstance(m, dict):
            return m
        r = astro_bodies.resolve_radius(radius_m, radius_rsun, radius_rearth, distance_au)
        if isinstance(r, dict):
            return r
        M, R, body_label = m[0], r[0], None

    v_esc = math.sqrt(2.0 * _G * M / R)
    v_circ = math.sqrt(_G * M / R)
    return {
        "escape_velocity_kms": v_esc / 1000.0,
        "escape_velocity_c": v_esc / _C_MS,
        "circular_velocity_kms": v_circ / 1000.0,
        "specific_energy_j_per_kg": 0.5 * v_esc * v_esc,
        "mass_kg": M,
        "radius_m": R,
        "body": body_label,
        "model_note": _NOTE_ESC,
    }


# ── K2 ───────────────────────────────────────────────────────────────────────
def compute_gravitational_potential(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                    body=None, r_from_m=None, r_from_au=None,
                                    r_to_m=None, r_to_au=None, payload_kg=None):
    """Gravity-well depth, binding energy, and Δv to climb between two radii (K2)."""
    m = _mass_from_args(mass_kg, mass_msun, mass_mearth, mass_mjup, body)
    if isinstance(m, dict):
        return m
    M, body_label = m

    r_from = _resolve_length("--r-from", True, (r_from_m, 1.0, "m"), (r_from_au, _M_PER_AU, "au"))
    if isinstance(r_from, dict):
        return r_from
    r_to = _resolve_length("--r-to", False, (r_to_m, 1.0, "m"), (r_to_au, _M_PER_AU, "au"))
    if isinstance(r_to, dict):
        return r_to
    if r_to is None:
        r_to = math.inf
    if payload_kg is not None and payload_kg <= 0:
        return {"error": "Payload mass must be positive."}

    potential = -_G * M / r_from
    inv_to = 0.0 if math.isinf(r_to) else 1.0 / r_to
    well_depth = _G * M * (1.0 / r_from - inv_to)
    delta_v = math.sqrt(2.0 * abs(well_depth))
    return {
        "potential_j_per_kg": potential,
        "well_depth_j_per_kg": well_depth,
        "binding_energy_j": payload_kg * well_depth if payload_kg is not None else None,
        "delta_v_kms": delta_v / 1000.0,
        "r_from_m": r_from,
        "r_to_m": None if math.isinf(r_to) else r_to,
        "mass_kg": M,
        "body": body_label,
        "model_note": _NOTE_POT,
    }


# ── K3 ───────────────────────────────────────────────────────────────────────
def compute_sphere_of_influence(body_mass_kg=None, body_mass_msun=None, body_mass_mearth=None,
                                body_mass_mjup=None,
                                primary_mass_kg=None, primary_mass_msun=None,
                                primary_mass_mearth=None, primary_mass_mjup=None,
                                primary=None, semimajor_au=None):
    """Laplace sphere of influence + Hill radius for a body orbiting a primary (K3)."""
    bm = astro_bodies.resolve_mass(body_mass_kg, body_mass_msun, body_mass_mearth,
                                   body_mass_mjup, name="body mass")
    if isinstance(bm, dict):
        return bm
    pm = _mass_from_args(primary_mass_kg, primary_mass_msun, primary_mass_mearth,
                         primary_mass_mjup, primary, name="primary mass")
    if isinstance(pm, dict):
        return pm
    m, M = bm[0], pm[0]
    primary_label = pm[1]
    if semimajor_au is None or semimajor_au <= 0:
        return {"error": "Semi-major axis must be positive (--semimajor-au)."}

    a_au = semimajor_au
    soi_au = a_au * (m / M) ** 0.4
    hill_au = a_au * (m / (3.0 * M)) ** (1.0 / 3.0)
    return {
        "soi_laplace_au": soi_au,
        "soi_laplace_km": soi_au * _KM_PER_AU,
        "hill_radius_au": hill_au,
        "hill_radius_km": hill_au * _KM_PER_AU,
        "ratio_soi_hill": soi_au / hill_au,
        "body_mass_kg": m,
        "primary_mass_kg": M,
        "primary": primary_label,
        "semimajor_au": a_au,
        "model_note": _NOTE_SOI,
    }


# ── K4 ───────────────────────────────────────────────────────────────────────
def compute_hyperbolic_approach(mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None,
                                body=None, v_infinity_kms=None, arrival_speed_kms=None,
                                r_from_km=None, r_from_au=None,
                                periapsis_km=None, periapsis_rbody=None,
                                target="circular",
                                target_apoapsis_km=None, target_apoapsis_au=None):
    """Braking-corridor geometry for a hyperbolic arrival: v_p, C₃, capture Δv (K4)."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup))
    if body is not None:
        if have_mass:
            return {"error": "Provide --body OR explicit mass flags, not both."}
        preset = astro_bodies.body_preset(body)
        if "error" in preset:
            return preset
        M, R_body, body_label = preset["mass_kg"], preset["radius_m"], preset["display"]
    else:
        m = astro_bodies.resolve_mass(mass_kg, mass_msun, mass_mearth, mass_mjup)
        if isinstance(m, dict):
            return m
        M, R_body, body_label = m[0], None, None

    # v∞ — exactly one of direct v∞ or (arrival speed + r_from)
    mode_direct = v_infinity_kms is not None
    mode_arrival = arrival_speed_kms is not None
    if mode_direct == mode_arrival:
        return {"error": "Provide exactly one of --v-infinity-kms or --arrival-speed-kms."}
    if mode_direct:
        if v_infinity_kms < 0:
            return {"error": "Hyperbolic excess speed must be ≥ 0 (--v-infinity-kms)."}
        v_inf = v_infinity_kms * 1000.0
    else:
        r_from = _resolve_length("--r-from", True, (r_from_km, 1000.0, "km"),
                                 (r_from_au, _M_PER_AU, "au"))
        if isinstance(r_from, dict):
            return r_from
        if arrival_speed_kms <= 0:
            return {"error": "Arrival speed must be positive (--arrival-speed-kms)."}
        v_arr = arrival_speed_kms * 1000.0
        v_inf_sq = v_arr * v_arr - 2.0 * _G * M / r_from
        if v_inf_sq <= 0:
            return {"error": "Arrival speed is at/below escape speed at --r-from — the "
                             "trajectory is bound, not hyperbolic."}
        v_inf = math.sqrt(v_inf_sq)

    # periapsis — exactly one of km or body-radii
    if (periapsis_km is not None) == (periapsis_rbody is not None):
        return {"error": "Provide exactly one of --periapsis-km or --periapsis-rbody."}
    if periapsis_km is not None:
        if periapsis_km <= 0:
            return {"error": "Periapsis must be positive (--periapsis-km)."}
        r_p = periapsis_km * 1000.0
    else:
        if periapsis_rbody <= 0:
            return {"error": "Periapsis (body radii) must be positive (--periapsis-rbody)."}
        if R_body is None:
            return {"error": "--periapsis-rbody needs a known body radius; use --body, or "
                             "give --periapsis-km directly."}
        r_p = periapsis_rbody * R_body

    v_p = math.sqrt(v_inf * v_inf + 2.0 * _G * M / r_p)
    if target == "circular":
        v_capture = math.sqrt(_G * M / r_p)
    elif target == "parabolic":
        v_capture = math.sqrt(2.0 * _G * M / r_p)
    elif target == "elliptical":
        r_a = _resolve_length("--target-apoapsis", True, (target_apoapsis_km, 1000.0, "km"),
                              (target_apoapsis_au, _M_PER_AU, "au"))
        if isinstance(r_a, dict):
            return r_a
        if r_a <= r_p:
            return {"error": "Target apoapsis must exceed periapsis."}
        a_sma = 0.5 * (r_p + r_a)
        v_capture = math.sqrt(_G * M * (2.0 / r_p - 1.0 / a_sma))
    else:
        return {"error": "Target must be one of: circular, parabolic, elliptical."}

    return {
        "v_periapsis_kms": v_p / 1000.0,
        "capture_delta_v_kms": (v_p - v_capture) / 1000.0,
        "c3_km2s2": (v_inf / 1000.0) ** 2,
        "v_infinity_kms": v_inf / 1000.0,
        "periapsis_km": r_p / 1000.0,
        "target": target,
        "mass_kg": M,
        "body": body_label,
        "model_note": _NOTE_HYP,
    }
