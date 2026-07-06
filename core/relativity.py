"""Phase AF (Group L) — special relativity & causality (Packet 23; feeds 22 and 24).

Eight ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculators: the full
special-relativity toolkit plus the load-bearing ``causality-check`` guardrail for the
no-FTL-communication premise. Extends the ``lorentz-factor`` (γ) seed in ``core.calculators``.

Physics (durable, closed-form):
  * **L1 time-dilation** — special Δt = γΔτ; gravitational Δτ/Δt = √(1 − r_s/r) (r_s = 2GM/c²);
    optional combined coordinate-per-proper factor γ/√(1 − r_s/r).
  * **L2 length-contraction** — L = L₀/γ.
  * **L3 velocity-addition** — collinear w = (u+v)/(1+uv/c²); perpendicular w = √(v² + u²(1−v²)).
  * **L4 relativistic-doppler** — f_obs/f_src = 1/(γ(1 − β cosθ)) (θ=0 approach, 180° recede, 90°
    transverse = 1/γ); redshift z = 1/factor − 1.
  * **L5 rapidity** — φ = artanh(β); β = tanh(φ); rapidities add linearly.
  * **L6 relativistic-energy-momentum** — E = γmc², p = γmv, KE = (γ−1)mc², E² = (pc)² + (mc²)².
  * **L7 lorentz-transform** — t' = γ(t − vx/c²), x' = γ(x − vt); inverse; simultaneity offset.
  * **L8 causality-check** ⭐ — an FTL signal of speed u with a return leg from a frame at v permits
    a closed causal loop (tachyonic antitelephone) when u·v > c²; v_crit = c²/u; a universal
    preferred FTL frame removes the loop.

Masses (L1 gravitational) resolve through ``core.astro_bodies``; constants from ``core.equations``.
No network, no DB, no RNG, no time.
"""

import math

from core.equations import _C_MS, _G, _ELEMENTARY_CHARGE, _SEC_PER_YEAR, _LY_M
import core.astro_bodies as astro_bodies

_BETA_KMS_FACTOR = 1000.0 / _C_MS


def _gamma(beta):
    """Lorentz factor γ = 1/√(1−β²) (assumes 0 ≤ |β| < 1; callers validate)."""
    return 1.0 / math.sqrt(1.0 - beta * beta)


def _beta_from(velocity_c, velocity_kms, required=True):
    """Resolve β from exactly one of --velocity-c / --velocity-kms. Returns β (float),
    None (when not required and absent), or a {"error"} dict."""
    given = [(v, f) for (v, f) in ((velocity_c, 1.0), (velocity_kms, _BETA_KMS_FACTOR))
             if v is not None]
    if not given:
        return {"error": "Provide --velocity-c or --velocity-kms."} if required else None
    if len(given) > 1:
        return {"error": "Provide only one of --velocity-c / --velocity-kms."}
    beta = given[0][0] * given[0][1]
    if beta < 0 or beta >= 1:
        return {"error": "Velocity must be sublight: 0 ≤ β < 1."}
    return beta


def _resolve_grav(mass_kg, mass_msun, mass_mearth, mass_mjup, body,
                  radius_m, radius_rsun, radius_rearth, distance_au):
    """Resolve an optional gravitational source → (mass_kg, radius_m), None (absent), or
    {"error"}. --body fills both; else --mass-* + one radius flag."""
    have_mass = any(v is not None for v in (mass_kg, mass_msun, mass_mearth, mass_mjup))
    have_radius = any(v is not None for v in (radius_m, radius_rsun, radius_rearth, distance_au))
    if body is None and not have_mass and not have_radius:
        return None
    if body is not None:
        if have_mass or have_radius:
            return {"error": "Provide --body OR explicit mass+radius flags for the gravitational source, not both."}
        preset = astro_bodies.body_preset(body)
        if "error" in preset:
            return preset
        return (preset["mass_kg"], preset["radius_m"])
    m = astro_bodies.resolve_mass(mass_kg, mass_msun, mass_mearth, mass_mjup)
    if isinstance(m, dict):
        return m
    r = astro_bodies.resolve_radius(radius_m, radius_rsun, radius_rearth, distance_au)
    if isinstance(r, dict):
        return r
    return (m[0], r[0])


# ── L1 ───────────────────────────────────────────────────────────────────────
def compute_time_dilation(velocity_c=None, velocity_kms=None, proper_time=None, coordinate_time=None,
                          mass_kg=None, mass_msun=None, mass_mearth=None, mass_mjup=None, body=None,
                          radius_m=None, radius_rsun=None, radius_rearth=None, distance_au=None,
                          combined=False):
    """Special and/or gravitational time dilation (L1)."""
    beta = _beta_from(velocity_c, velocity_kms, required=False)
    if isinstance(beta, dict):
        return beta
    grav = _resolve_grav(mass_kg, mass_msun, mass_mearth, mass_mjup, body,
                         radius_m, radius_rsun, radius_rearth, distance_au)
    if isinstance(grav, dict):
        return grav
    if beta is None and grav is None:
        return {"error": "Provide a velocity (--velocity-c/--velocity-kms) and/or a gravitational "
                         "source (--body or --mass-* + radius)."}

    gamma = _gamma(beta) if beta is not None else 1.0
    grav_factor = None
    if grav is not None:
        M, R = grav
        r_s = 2.0 * _G * M / _C_MS ** 2
        if R <= r_s:
            return {"error": "Radius is at/below the Schwarzschild radius — gravitational factor undefined."}
        grav_factor = math.sqrt(1.0 - r_s / R)

    combined_factor = None
    if combined:
        if beta is None or grav is None:
            return {"error": "--combined needs both a velocity and a gravitational source."}
        combined_factor = gamma / grav_factor

    if combined_factor is not None:
        effective = combined_factor
    elif beta is not None:
        effective = gamma
    else:
        effective = 1.0 / grav_factor

    if proper_time is not None and coordinate_time is not None:
        return {"error": "Provide only one of --proper-time / --coordinate-time."}
    pt = ct = None
    if proper_time is not None:
        if proper_time < 0:
            return {"error": "Proper time must be ≥ 0."}
        pt, ct = proper_time, effective * proper_time
    elif coordinate_time is not None:
        if coordinate_time < 0:
            return {"error": "Coordinate time must be ≥ 0."}
        ct, pt = coordinate_time, coordinate_time / effective

    return {
        "gamma": gamma,
        "dilation_factor": effective,
        "proper_time": pt,
        "coordinate_time": ct,
        "gravitational_factor": grav_factor,
        "combined_factor": combined_factor,
        "model_note": ("Special Δt = γΔτ (γ = 1/√(1−β²)); gravitational Δτ/Δt = √(1 − r_s/r), "
                       "r_s = 2GM/c². dilation_factor is the coordinate-per-proper factor actually "
                       "applied (γ, 1/√(1−r_s/r), or γ/√(1−r_s/r) with --combined). Weak-field "
                       "Schwarzschild static-observer form; non-rotating."),
    }


# ── L2 ───────────────────────────────────────────────────────────────────────
def compute_length_contraction(velocity_c=None, velocity_kms=None,
                               proper_length=None, contracted_length=None):
    """Relativistic length contraction L = L₀/γ (L2)."""
    beta = _beta_from(velocity_c, velocity_kms)
    if isinstance(beta, dict):
        return beta
    if proper_length is not None and contracted_length is not None:
        return {"error": "Provide only one of --proper-length / --contracted-length."}
    gamma = _gamma(beta)
    pl = cl = None
    if proper_length is not None:
        if proper_length <= 0:
            return {"error": "Proper length must be positive."}
        pl, cl = proper_length, proper_length / gamma
    elif contracted_length is not None:
        if contracted_length <= 0:
            return {"error": "Contracted length must be positive."}
        cl, pl = contracted_length, contracted_length * gamma
    return {
        "gamma": gamma,
        "proper_length": pl,
        "contracted_length": cl,
        "contraction_factor": 1.0 / gamma,
        "model_note": "Length contraction L = L₀/γ along the direction of motion; γ = 1/√(1−β²).",
    }


# ── L3 ───────────────────────────────────────────────────────────────────────
def compute_velocity_addition(u_c, v_c, perpendicular=False):
    """Relativistic velocity addition (L3). Collinear by default, or --perpendicular."""
    if u_c is None or v_c is None:
        return {"error": "Provide --u-c and --v-c (fractions of c)."}
    if not (-1.0 <= u_c <= 1.0) or not (-1.0 <= v_c <= 1.0):
        return {"error": "Velocities must satisfy −1 ≤ β ≤ 1 (fractions of c)."}
    if perpendicular:
        w = math.sqrt(v_c * v_c + u_c * u_c * (1.0 - v_c * v_c))
        formula = "perpendicular: w = √(v² + u²(1−v²))"
    else:
        w = (u_c + v_c) / (1.0 + u_c * v_c)
        formula = "collinear: w = (u+v)/(1+uv/c²)"
    gamma_combined = _gamma(w) if abs(w) < 1.0 else None
    return {
        "combined_velocity_c": w,
        "combined_velocity_kms": w * _C_MS / 1000.0,
        "gamma_combined": gamma_combined,
        "model_note": f"Relativistic velocity addition, {formula}; the result never exceeds c "
                      "(gamma_combined is null at exactly c).",
    }


# ── L4 ───────────────────────────────────────────────────────────────────────
def compute_relativistic_doppler(velocity_c=None, velocity_kms=None, approach=False, recede=False,
                                 angle_deg=None, rest_wavelength_nm=None, rest_frequency_hz=None):
    """Relativistic Doppler factor + shifted wavelength/frequency (L4)."""
    beta = _beta_from(velocity_c, velocity_kms)
    if isinstance(beta, dict):
        return beta
    modes = [m for m, on in (("approach", approach), ("recede", recede),
                             ("angle", angle_deg is not None)) if on]
    if len(modes) != 1:
        return {"error": "Provide exactly one of --approach / --recede / --angle-deg."}
    if rest_wavelength_nm is not None and rest_frequency_hz is not None:
        return {"error": "Provide only one of --rest-wavelength-nm / --rest-frequency-hz."}

    theta = {"approach": 0.0, "recede": 180.0}.get(modes[0], angle_deg or 0.0)
    gamma = _gamma(beta)
    factor = 1.0 / (gamma * (1.0 - beta * math.cos(math.radians(theta))))

    obs_wl = obs_freq = None
    if rest_wavelength_nm is not None:
        if rest_wavelength_nm <= 0:
            return {"error": "Rest wavelength must be positive."}
        obs_wl = rest_wavelength_nm / factor
    if rest_frequency_hz is not None:
        if rest_frequency_hz <= 0:
            return {"error": "Rest frequency must be positive."}
        obs_freq = rest_frequency_hz * factor

    return {
        "doppler_factor": factor,
        "angle_deg": theta,
        "observed_wavelength_nm": obs_wl,
        "observed_frequency_hz": obs_freq,
        "redshift_z": 1.0 / factor - 1.0,
        "model_note": ("Relativistic Doppler f_obs/f_src = 1/(γ(1 − β cosθ)) (θ=0 approach, 180° "
                       "recede, 90° transverse = 1/γ). redshift_z = λ_obs/λ_src − 1 = 1/factor − 1 "
                       "(negative = blueshift)."),
    }


# ── L5 ───────────────────────────────────────────────────────────────────────
def compute_rapidity(velocity_c=None, rapidity=None, add=None):
    """Rapidity φ = artanh(β); linear composition via --add (L5)."""
    sources = [s for s, on in (("velocity_c", velocity_c is not None),
                               ("rapidity", rapidity is not None),
                               ("add", add is not None)) if on]
    if len(sources) != 1:
        return {"error": "Provide exactly one of --velocity-c / --rapidity / --add."}

    composed = None
    if velocity_c is not None:
        if velocity_c < 0 or velocity_c >= 1:
            return {"error": "Velocity must be sublight: 0 ≤ β < 1."}
        beta = velocity_c
        phi = math.atanh(beta)
    elif rapidity is not None:
        phi = rapidity
        beta = math.tanh(phi)
    else:
        betas = add if isinstance(add, (list, tuple)) else [add]
        for b in betas:
            if b < 0 or b >= 1:
                return {"error": "Each --add velocity must be sublight: 0 ≤ β < 1."}
        phi = sum(math.atanh(b) for b in betas)
        beta = math.tanh(phi)
        composed = beta

    return {
        "rapidity": phi,
        "velocity_c": beta,
        "gamma": math.cosh(phi),
        "composed_velocity_c": composed,
        "model_note": ("Rapidity φ = artanh(β), β = tanh(φ), γ = cosh(φ); collinear boosts add "
                       "linearly in φ. --add composes a list of β into tanh(Σ artanh(βᵢ))."),
    }


# ── L6 ───────────────────────────────────────────────────────────────────────
def compute_relativistic_energy_momentum(mass_kg=None, mass_mev=None, velocity_c=None, gamma=None,
                                         kinetic_energy_j=None, momentum=None):
    """Relativistic energy, momentum, and kinetic energy of a massive particle (L6)."""
    mass_given = [k for k, v in (("kg", mass_kg), ("mev", mass_mev)) if v is not None]
    if len(mass_given) != 1:
        return {"error": "Provide exactly one of --mass-kg / --mass-mev."}
    if mass_given[0] == "kg":
        if mass_kg <= 0:
            return {"error": "Mass must be positive."}
        m = mass_kg
    else:
        if mass_mev <= 0:
            return {"error": "Mass must be positive."}
        m = mass_mev * 1e6 * _ELEMENTARY_CHARGE / _C_MS ** 2

    state = [k for k, v in (("velocity_c", velocity_c), ("gamma", gamma),
                            ("kinetic_energy_j", kinetic_energy_j), ("momentum", momentum))
             if v is not None]
    if len(state) != 1:
        return {"error": "Provide exactly one of --velocity-c / --gamma / --kinetic-energy-j / --momentum."}

    rest_energy = m * _C_MS ** 2
    if state[0] == "velocity_c":
        if velocity_c < 0 or velocity_c >= 1:
            return {"error": "Velocity must be sublight: 0 ≤ β < 1."}
        g = _gamma(velocity_c)
    elif state[0] == "gamma":
        if gamma < 1:
            return {"error": "Lorentz factor γ must be ≥ 1."}
        g = gamma
    elif state[0] == "kinetic_energy_j":
        if kinetic_energy_j < 0:
            return {"error": "Kinetic energy must be ≥ 0."}
        g = 1.0 + kinetic_energy_j / rest_energy
    else:
        if momentum < 0:
            return {"error": "Momentum must be ≥ 0."}
        g = math.sqrt(1.0 + (momentum / (m * _C_MS)) ** 2)

    beta = math.sqrt(1.0 - 1.0 / (g * g))
    return {
        "gamma": g,
        "total_energy_j": g * rest_energy,
        "rest_energy_j": rest_energy,
        "kinetic_energy_j": (g - 1.0) * rest_energy,
        "momentum_kgms": g * m * beta * _C_MS,
        "velocity_c": beta,
        "mass_kg": m,
        "model_note": ("E = γmc², p = γmv, KE = (γ−1)mc², E² = (pc)² + (mc²)². State resolved from "
                       "whichever of velocity/γ/KE/momentum is supplied."),
    }


# ── L7 ───────────────────────────────────────────────────────────────────────
def compute_lorentz_transform(velocity_c=None, t=None, x=None, t_yr=None, x_ly=None,
                              inverse=False, event2_t=None, event2_x=None):
    """Lorentz coordinate transform + relativity-of-simultaneity offset (L7)."""
    if velocity_c is None:
        return {"error": "Provide --velocity-c (boost velocity)."}
    if velocity_c < 0 or velocity_c >= 1:
        return {"error": "Boost velocity must be sublight: 0 ≤ β < 1."}

    si_mode = t is not None or x is not None
    astro_mode = t_yr is not None or x_ly is not None
    if si_mode and astro_mode:
        return {"error": "Do not mix SI (--t/--x) and astro (--t-yr/--x-ly) units."}
    if si_mode:
        if t is None or x is None:
            return {"error": "Provide both --t (s) and --x (m)."}
        t_s, x_m = t, x
    elif astro_mode:
        if t_yr is None or x_ly is None:
            return {"error": "Provide both --t-yr and --x-ly."}
        t_s, x_m = t_yr * _SEC_PER_YEAR, x_ly * _LY_M
    else:
        return {"error": "Provide an event: --t/--x (SI) or --t-yr/--x-ly (astro)."}

    v = velocity_c * _C_MS * (-1.0 if inverse else 1.0)
    g = _gamma(velocity_c)

    def transform(ts, xm):
        return g * (ts - v * xm / _C_MS ** 2), g * (xm - v * ts)

    tp, xp = transform(t_s, x_m)
    if astro_mode:
        t_prime, x_prime = tp / _SEC_PER_YEAR, xp / _LY_M
    else:
        t_prime, x_prime = tp, xp

    sim = None
    if event2_t is not None or event2_x is not None:
        if event2_t is None or event2_x is None:
            return {"error": "--event2 needs both t2 and x2."}
        if astro_mode:
            t2_s, x2_m = event2_t * _SEC_PER_YEAR, event2_x * _LY_M
        else:
            t2_s, x2_m = event2_t, event2_x
        tp2, _ = transform(t2_s, x2_m)
        d = tp2 - tp
        sim = d / _SEC_PER_YEAR if astro_mode else d

    return {
        "t_prime": t_prime,
        "x_prime": x_prime,
        "gamma": g,
        "simultaneity_offset": sim,
        "model_note": ("Lorentz boost t' = γ(t − vx/c²), x' = γ(x − vt) (--inverse applies the "
                       "inverse, +v). simultaneity_offset = t'(event2) − t'(event1) — the "
                       "relativity-of-simultaneity offset when the events are simultaneous in the "
                       "unprimed frame. Astro units use c = 1 ly/yr."),
    }


# ── L8 ───────────────────────────────────────────────────────────────────────
def compute_causality_check(signal_speed_c=None, instant=False, frame_velocity_c=None,
                            preferred_frame=False, two_jump=False):
    """FTL tachyonic-antitelephone causality guardrail (L8)."""
    if (signal_speed_c is not None) == instant:
        return {"error": "Provide exactly one of --signal-speed-c or --instant."}
    if not instant and signal_speed_c <= 0:
        return {"error": "Signal speed must be positive (--signal-speed-c, in units of c)."}
    if frame_velocity_c is None:
        return {"error": "Provide --frame-velocity-c (relative frame velocity, fraction of c)."}
    if frame_velocity_c < 0 or frame_velocity_c >= 1:
        return {"error": "Frame velocity must satisfy 0 ≤ β < 1."}

    if instant:
        condition = None
        v_crit = 0.0
        margin = None
        loop = frame_velocity_c > 0.0
    else:
        condition = signal_speed_c * frame_velocity_c
        v_crit = 1.0 / signal_speed_c
        margin = condition - 1.0
        loop = condition > 1.0

    if preferred_frame:
        expl = ("A single universal FTL rest frame is asserted: all jumps are referenced to it, so "
                "time-ordering is preserved and no closed causal loop forms regardless of the "
                "kinematic condition.")
    elif loop:
        expl = ("The FTL signal speed and relative frame velocity satisfy u·v > c² (β_signal·β_frame "
                "> 1), so a two-jump return leg can arrive before emission — a tachyonic "
                "antitelephone / closed causal loop is possible. Keep the relative frame velocity "
                f"below v_crit = c²/u = {v_crit:.4g} c to avoid it.")
    else:
        expl = ("u·v ≤ c²: no closed causal loop for this signal speed and frame velocity. A loop "
                f"would require a relative frame velocity above v_crit = c²/u = {v_crit:.4g} c.")
    if two_jump:
        expl += " (Two-jump antitelephone framing: both legs are FTL in their own emission frames.)"

    return {
        "loop_possible": loop,
        "condition_value": condition,
        "critical_frame_velocity_c": v_crit,
        "margin": margin,
        "preferred_frame_safe": bool(preferred_frame),
        "signal_speed_c": None if instant else signal_speed_c,
        "frame_velocity_c": frame_velocity_c,
        "instant": instant,
        "explanation": expl,
        "model_note": ("Closed-causal-loop (tachyonic antitelephone) condition u·v > c² for an FTL "
                       "signal of speed u and a return frame at relative velocity v; critical frame "
                       "velocity v_crit = c²/u. A universal preferred FTL frame removes the loop. "
                       "Special-relativistic kinematics; the loop is a possibility statement, not a "
                       "claim the setting builds one."),
    }
