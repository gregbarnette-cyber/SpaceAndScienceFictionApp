"""Phase AC — ISM-drag / magnetic-sail calculators (Group K of the Packet-16 STL work).

Two pure-math, self-validating (Phase-H/P contract) calculators for the magnetic interaction
of a vehicle with the interstellar medium — the one scope-shaping STL gap Groups G–J did not
enumerate. They complement Group G (``rocket-equation`` = "can you carry the fuel"; ``beam-sail``
= "can a photon beam push you"; **Group K = "what does the ISM do to you — brake you, or feed a
ramjet"**) and the ``dust-*`` subcommands (ISM *column* for extinction, not magnetic momentum
exchange).

  * ``compute_magsail``  (K1) — magnetic-sail braking against the ISM (magnetopause standoff →
    drag force ∝ v^(4/3) → deceleration → optional stopping distance/time).
  * ``compute_ramscoop`` (K2) — Bussard ramjet drag-vs-thrust verdict: F_net = ṁ(v_e − v) − F_drag
    → "drive"/"brake" + crossover velocity (the Zubrin & Andrews "brake not drive" result as a
    swept recompute).

No network, no DB, no RNG, no time. ``query.py``-only (no GUI). Shares ``_MU_0`` / ``_C_MS`` /
``_AMU_KG`` / ``_SEC_PER_YEAR`` with ``core.equations``; the bundled ISM/fusion constants live in
``core.ism_drag_tables`` (isolated, like ``core.propulsion_tables``). Momentum/energy balance only
— no reactor/coil/plasma engineering (Pkt 25). The ISM density is a caller-supplied parameter,
never re-derived. Self-validating: bad input returns a curated ``{"error": str}``.
"""

import math

from core.equations import _MU_0, _C_MS, _AMU_KG, _SEC_PER_YEAR
from core import ism_drag_tables as _t

_LY_M = _C_MS * _SEC_PER_YEAR   # metres per (Julian) light-year


def _resolve_velocity(velocity_kms, beta):
    """Return (v_ms, velocity_kms, beta) or a {"error"} dict. Exactly one anchor required."""
    if (velocity_kms is not None) + (beta is not None) != 1:
        return {"error": "Provide exactly one velocity anchor: --velocity-kms or --beta."}
    if beta is not None:
        if not (0.0 < beta < 1.0):
            return {"error": "beta must be in the range 0 < β < 1 (sublight)."}
        v_ms = beta * _C_MS
        return (v_ms, v_ms / 1000.0, beta)
    if velocity_kms <= 0:
        return {"error": "velocity_kms must be > 0."}
    v_ms = velocity_kms * 1000.0
    return (v_ms, velocity_kms, v_ms / _C_MS)


def _resolve_dipole(coil_current_a, coil_radius_m, magnetic_moment_am2):
    """Return (m_dip, coil_current_a, coil_radius_m) or a {"error"} dict.

    Exactly one sail anchor: the coil pair (current + radius) OR a magnetic moment.
    """
    coil_partial = (coil_current_a is not None) != (coil_radius_m is not None)
    if coil_partial:
        return {"error": "Provide both --coil-current-a and --coil-radius-m for the coil anchor."}
    have_coil = coil_current_a is not None and coil_radius_m is not None
    have_moment = magnetic_moment_am2 is not None
    if have_coil + have_moment != 1:
        return {"error": "Provide exactly one sail anchor: (--coil-current-a + --coil-radius-m) "
                         "or --magnetic-moment-am2."}
    if have_coil:
        if coil_current_a <= 0:
            return {"error": "coil_current_a must be > 0."}
        if coil_radius_m <= 0:
            return {"error": "coil_radius_m must be > 0."}
        m_dip = coil_current_a * math.pi * coil_radius_m ** 2
        return (m_dip, coil_current_a, coil_radius_m)
    if magnetic_moment_am2 <= 0:
        return {"error": "magnetic_moment_am2 must be > 0."}
    return (magnetic_moment_am2, None, None)


def _standoff_radius_m(mu0, m_dip, k, rho, v_ms):
    """R_mp = [ μ₀·m_dip² / (8π²·k·ρv²) ]^(1/6)."""
    return (mu0 * m_dip ** 2 / (8.0 * math.pi ** 2 * k * rho * v_ms ** 2)) ** (1.0 / 6.0)


# ── K1 — magnetic-sail braking against the ISM ────────────────────────────────

def compute_magsail(ism_density_cm3=None, ion_mass_amu=None, velocity_kms=None, beta=None,
                    coil_current_a=None, coil_radius_m=None, magnetic_moment_am2=None,
                    standoff_coeff=None, drag_coeff=None, vehicle_mass_t=None,
                    velocity_final_kms=None):
    """Magsail braking: magnetopause standoff → drag force (∝ v^(4/3)) → deceleration →
    optional stopping distance/time.

    ISM defaults flag to the Local Interstellar Cloud (n ≈ 0.1 cm⁻³, mean ion mass ≈ 1.3 amu);
    k/C_d default to the confirmed order-unity coefficients. See ``core.ism_drag_tables``.
    """
    density = _t._DEFAULT_N_CM3 if ism_density_cm3 is None else ism_density_cm3
    ion_mass = _t._MEAN_ION_MASS_AMU if ion_mass_amu is None else ion_mass_amu
    k = _t._STANDOFF_COEFF_K if standoff_coeff is None else standoff_coeff
    cd = _t._DRAG_COEFF_CD if drag_coeff is None else drag_coeff

    if density <= 0:
        return {"error": "ism_density_cm3 must be > 0."}
    if ion_mass <= 0:
        return {"error": "ion_mass_amu must be > 0."}
    if k <= 0:
        return {"error": "standoff_coeff (k) must be > 0."}
    if cd <= 0:
        return {"error": "drag_coeff (C_d) must be > 0."}

    vel = _resolve_velocity(velocity_kms, beta)
    if isinstance(vel, dict):
        return vel
    v_ms, velocity_kms_out, beta_out = vel

    dip = _resolve_dipole(coil_current_a, coil_radius_m, magnetic_moment_am2)
    if isinstance(dip, dict):
        return dip
    m_dip, coil_current_out, coil_radius_out = dip

    if vehicle_mass_t is not None and vehicle_mass_t <= 0:
        return {"error": "vehicle_mass_t must be > 0."}
    if velocity_final_kms is not None:
        if vehicle_mass_t is None:
            return {"error": "velocity_final_kms requires --vehicle-mass-t (for the stopping "
                             "distance/time integration)."}
        if velocity_final_kms <= 0:
            return {"error": "velocity_final_kms must be > 0 (the v^(4/3) drag law never fully "
                             "stops in finite time)."}
        if velocity_final_kms >= velocity_kms_out:
            return {"error": "velocity_final_kms must be < the current velocity (this is braking)."}

    # ── momentum balance ──
    rho = density * 1e6 * ion_mass * _AMU_KG            # kg/m³ (cm⁻³ → m⁻³ = ×1e6)
    r_mp_m = _standoff_radius_m(_MU_0, m_dip, k, rho, v_ms)
    ram_pressure_pa = rho * v_ms ** 2                   # ρv² momentum-flux ram pressure
    eff_area_m2 = math.pi * r_mp_m ** 2
    drag_force_n = cd * 0.5 * rho * v_ms ** 2 * eff_area_m2

    deceleration_ms2 = stopping_distance_ly = stopping_time_yr = None
    if vehicle_mass_t is not None:
        m_kg = vehicle_mass_t * 1000.0
        deceleration_ms2 = drag_force_n / m_kg
        if velocity_final_kms is not None:
            # F_drag = β_coef · v^(4/3); β_coef pinned so F_drag(v₀) matches.
            beta_coef = drag_force_n / v_ms ** (4.0 / 3.0)
            vf_ms = velocity_final_kms * 1000.0
            t_s = 3.0 * m_kg / beta_coef * (vf_ms ** (-1.0 / 3.0) - v_ms ** (-1.0 / 3.0))
            x_m = 3.0 * m_kg / (2.0 * beta_coef) * (v_ms ** (2.0 / 3.0) - vf_ms ** (2.0 / 3.0))
            stopping_time_yr = t_s / _SEC_PER_YEAR
            stopping_distance_ly = x_m / _LY_M

    near_field_warning = None
    if coil_radius_out is not None and r_mp_m <= coil_radius_out:
        near_field_warning = (
            "R_mp (%.3g m) ≲ R_coil (%.3g m): the far-field dipole assumption breaks down — the "
            "standoff/drag are unreliable in this regime (raise the field or lower v/ρ)."
            % (r_mp_m, coil_radius_out))

    return {
        "ism_density_cm3": density,
        "ion_mass_amu": ion_mass,
        "ism_mass_density_kgm3": rho,
        "velocity_kms": velocity_kms_out,
        "beta": beta_out,
        "magnetic_moment_am2": m_dip,
        "coil_current_a": coil_current_out,
        "coil_radius_m": coil_radius_out,
        "magnetopause_radius_km": r_mp_m / 1000.0,
        "ram_pressure_pa": ram_pressure_pa,
        "effective_area_km2": eff_area_m2 / 1e6,
        "standoff_coeff": k,
        "drag_coeff": cd,
        "drag_force_n": drag_force_n,
        "drag_scaling_note": "F ∝ v^4/3 (R_mp ∝ v^(−1/3) → effective area ∝ v^(−2/3)); drag falls "
                             "as the ship slows — fast initial braking, long tail.",
        "deceleration_ms2": deceleration_ms2,
        "stopping_distance_ly": stopping_distance_ly,
        "stopping_time_yr": stopping_time_yr,
        "near_field_warning": near_field_warning,
        "ionization_note": _t._IONIZATION_NOTE,
        "model_note": _t._MODEL_NOTE_MAGSAIL,
    }


# ── K2 — Bussard ramjet drag-vs-thrust verdict ────────────────────────────────

def compute_ramscoop(ism_density_cm3=None, ion_mass_amu=None, velocity_kms=None, beta=None,
                     coil_current_a=None, coil_radius_m=None, scoop_area_km2=None,
                     magnetic_moment_am2=None, fuel=None, fusion_efficiency=None,
                     exhaust_velocity_kms=None, standoff_coeff=None, drag_coeff=None):
    """Bussard ramjet drag-vs-thrust: F_net = ṁ(v_e − v) − F_drag → "drive"/"brake" + crossover.

    Scoop area from the coil/moment magnetopause (like K1) or a supplied physical --scoop-area-km2.
    Exhaust from a bundled fuel (v_e = √(2·η·f·c²)) or an explicit --exhaust-velocity-kms.
    """
    density = _t._DEFAULT_N_CM3 if ism_density_cm3 is None else ism_density_cm3
    ion_mass = _t._MEAN_ION_MASS_AMU if ion_mass_amu is None else ion_mass_amu
    k = _t._STANDOFF_COEFF_K if standoff_coeff is None else standoff_coeff
    cd = _t._DRAG_COEFF_CD if drag_coeff is None else drag_coeff

    if density <= 0:
        return {"error": "ism_density_cm3 must be > 0."}
    if ion_mass <= 0:
        return {"error": "ion_mass_amu must be > 0."}
    if k <= 0:
        return {"error": "standoff_coeff (k) must be > 0."}
    if cd <= 0:
        return {"error": "drag_coeff (C_d) must be > 0."}

    vel = _resolve_velocity(velocity_kms, beta)
    if isinstance(vel, dict):
        return vel
    v_ms, velocity_kms_out, beta_out = vel

    # ── scoop anchor: coil pair | magnetic moment | physical area ──
    have_area = scoop_area_km2 is not None
    have_field = (coil_current_a is not None or coil_radius_m is not None
                  or magnetic_moment_am2 is not None)
    if have_area and have_field:
        return {"error": "Provide one scoop anchor: --scoop-area-km2, or the field "
                         "(--coil-current-a + --coil-radius-m / --magnetic-moment-am2), not both."}
    rho = density * 1e6 * ion_mass * _AMU_KG
    if have_area:
        if scoop_area_km2 <= 0:
            return {"error": "scoop_area_km2 must be > 0."}
        a_mp_m2 = scoop_area_km2 * 1e6
        r_mp_m = math.sqrt(a_mp_m2 / math.pi)
        m_dip = None
    else:
        dip = _resolve_dipole(coil_current_a, coil_radius_m, magnetic_moment_am2)
        if isinstance(dip, dict):
            return dip
        m_dip = dip[0]
        r_mp_m = _standoff_radius_m(_MU_0, m_dip, k, rho, v_ms)
        a_mp_m2 = math.pi * r_mp_m ** 2

    # ── exhaust anchor: bundled fuel + η  OR  explicit v_e ──
    have_fuel = fuel is not None
    have_ve = exhaust_velocity_kms is not None
    if have_fuel + have_ve != 1:
        return {"error": "Provide exactly one exhaust anchor: --fuel (+ --fusion-efficiency) "
                         "or --exhaust-velocity-kms."}
    if have_fuel:
        if fuel not in _t._FUSION:
            return {"error": "Unknown fuel '%s'. Known: %s." %
                    (fuel, ", ".join(sorted(_t._FUSION)))}
        eta = _t._DEFAULT_FUSION_EFFICIENCY if fusion_efficiency is None else fusion_efficiency
        if not (0.0 < eta <= 1.0):
            return {"error": "fusion_efficiency (η) must be in (0, 1]."}
        f = _t._FUSION[fuel]["f"]
        v_e_ms = _C_MS * math.sqrt(2.0 * eta * f)
    else:
        if fusion_efficiency is not None:
            return {"error": "fusion_efficiency applies only to --fuel; drop it with "
                             "--exhaust-velocity-kms."}
        if exhaust_velocity_kms <= 0:
            return {"error": "exhaust_velocity_kms must be > 0."}
        eta = f = None
        v_e_ms = exhaust_velocity_kms * 1000.0

    # ── force balance ──
    m_dot = rho * v_ms * a_mp_m2                          # collected mass flux, kg/s
    reaction_thrust_n = m_dot * v_e_ms
    collection_drag_n = m_dot * v_ms
    magnetic_drag_n = cd * 0.5 * rho * v_ms ** 2 * a_mp_m2
    net_force_n = reaction_thrust_n - collection_drag_n - magnetic_drag_n
    verdict = "drive" if net_force_n > 0 else "brake"

    # Crossover: F_net(v) = 0. With A_mp fixed OR field-derived (∝ v^(−2/3)) the common v^(1/3)
    # factors out, so F_net = 0 ⟹ v_e − v(1 + C_d/2) = 0 ⟹ v_crossover = v_e / (1 + C_d/2).
    crossover_v_ms = v_e_ms / (1.0 + cd / 2.0)

    return {
        "velocity_kms": velocity_kms_out,
        "beta": beta_out,
        "ism_density_cm3": density,
        "ion_mass_amu": ion_mass,
        "magnetopause_radius_km": r_mp_m / 1000.0,
        "magnetic_moment_am2": m_dip,
        "scoop_area_km2": a_mp_m2 / 1e6,
        "collected_mass_flux_kgs": m_dot,
        "fuel": fuel,
        "fusion_yield_fraction": f,
        "fusion_efficiency": eta,
        "exhaust_velocity_kms": v_e_ms / 1000.0,
        "exhaust_beta": v_e_ms / _C_MS,
        "standoff_coeff": k,
        "drag_coeff": cd,
        "reaction_thrust_n": reaction_thrust_n,
        "collection_drag_n": collection_drag_n,
        "magnetic_drag_n": magnetic_drag_n,
        "net_force_n": net_force_n,
        "verdict": verdict,
        "crossover_velocity_kms": crossover_v_ms / 1000.0,
        "ionization_note": _t._IONIZATION_NOTE,
        "model_note": _t._MODEL_NOTE_RAMSCOOP,
    }
