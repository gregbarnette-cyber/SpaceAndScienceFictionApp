"""Phase AD (C5) — volatile delivery / cometary bombardment for terraforming.

A ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculator for the *supply*
side of terraforming an atmosphere by redirecting icy bodies (comets / Kuiper objects) onto a
target world — the mass/energy complement to Phase AB's ``atmosphere-mass`` (the *demand* side)
and ``insolation-shift``.

It composes three durable pieces already in the codebase:
  * the redirect burn's mass ratio — classical Tsiolkovsky ``MR = exp(Δv/v_e)`` via
    ``propulsion.compute_rocket_equation`` (reusing the bundled ideal-fuel ``v_e`` presets);
  * the impact energy ``½·M·v_impact²`` (+ TNT-equivalent ``E/4.184e6`` kg);
  * the number of bodies for a target atmosphere ``N = M_atm_target / m_vol``.

No network, no DB, no RNG, no time. Reuses ``core.propulsion`` (+ its ``propulsion_tables`` fuel
presets). Self-validating: bad input returns a curated ``{"error": str}``.
"""

from core import propulsion

_TNT_J_PER_KG = 4.184e6   # 1 kg TNT ≡ 4.184e6 J (4.184 kJ/g); E/this → kg TNT

_MODEL_NOTE = (
    "Volatile delivery (cometary / icy-body bombardment): a redirected body of mass M delivers "
    "m_vol = f·M of volatiles. The redirect burn's mass ratio is the classical Tsiolkovsky "
    "MR = exp(Δv/v_e) (shared with rocket-equation; bundled ideal-fuel v_e presets, MTA-movable). "
    "Impact energy ½·M·v_impact² (whole-body kinetic energy deposited; TNT-equivalent E/4.184e6 kg) "
    "— an upper bound ignoring atmospheric ablation, escaping ejecta, and re-radiation. Bodies "
    "needed N = target atmosphere mass / m_vol (pairs with atmosphere-mass's demand side). "
    "Delivery cadence/logistics, post-impact volatile retention, and thermal processing are out of "
    "scope."
)


def compute_volatile_delivery(body_mass_kg=None, volatile_fraction=0.5, delta_v_kms=None,
                              impact_velocity_kms=None, target_atmosphere_mass_kg=None,
                              fuel=None, exhaust_velocity_kms=None):
    """Delivered volatile mass + optional redirect mass ratio / impact energy / bodies needed.

    ``body_mass_kg`` × ``volatile_fraction`` → delivered volatile mass. Optional add-ons:
    ``delta_v_kms`` (+ exactly one of ``fuel`` / ``exhaust_velocity_kms``) → ``redirect_mass_ratio``;
    ``impact_velocity_kms`` → ``impact_energy_j`` / TNT; ``target_atmosphere_mass_kg`` →
    ``bodies_needed``. Each add-on's outputs are ``null`` when its input is omitted.
    """
    if body_mass_kg is None or body_mass_kg <= 0:
        return {"error": "body_mass_kg must be > 0."}
    if not (0.0 < volatile_fraction <= 1.0):
        return {"error": "volatile_fraction must be in (0, 1]."}
    delivered = volatile_fraction * body_mass_kg

    # ── redirect Δv → mass ratio (optional; needs exactly one exhaust anchor) ──
    redirect_mass_ratio = None
    if delta_v_kms is not None:
        if delta_v_kms <= 0:
            return {"error": "delta_v_kms must be > 0."}
        have_fuel = fuel is not None
        have_ve = exhaust_velocity_kms is not None
        if have_fuel + have_ve != 1:
            return {"error": "delta_v_kms needs exactly one exhaust anchor: --fuel or "
                             "--exhaust-velocity-kms."}
        rocket = propulsion.compute_rocket_equation(
            delta_v_kms=delta_v_kms, fuel=fuel, exhaust_velocity_kms=exhaust_velocity_kms)
        if "error" in rocket:
            return rocket
        redirect_mass_ratio = rocket["mass_ratio"]
    elif fuel is not None or exhaust_velocity_kms is not None:
        return {"error": "--fuel / --exhaust-velocity-kms apply only with --delta-v-kms."}

    # ── impact energy (optional) ──
    impact_energy_j = impact_energy_tnt_kg = None
    if impact_velocity_kms is not None:
        if impact_velocity_kms <= 0:
            return {"error": "impact_velocity_kms must be > 0."}
        v = impact_velocity_kms * 1000.0
        impact_energy_j = 0.5 * body_mass_kg * v ** 2
        impact_energy_tnt_kg = impact_energy_j / _TNT_J_PER_KG

    # ── bodies needed for a target atmosphere (optional) ──
    bodies_needed = None
    if target_atmosphere_mass_kg is not None:
        if target_atmosphere_mass_kg <= 0:
            return {"error": "target_atmosphere_mass_kg must be > 0."}
        bodies_needed = target_atmosphere_mass_kg / delivered

    return {
        "body_mass_kg": body_mass_kg,
        "volatile_fraction": volatile_fraction,
        "delivered_volatile_mass_kg": delivered,
        "delta_v_kms": delta_v_kms,
        "fuel": fuel,
        "exhaust_velocity_kms": exhaust_velocity_kms,
        "redirect_mass_ratio": redirect_mass_ratio,
        "impact_velocity_kms": impact_velocity_kms,
        "impact_energy_j": impact_energy_j,
        "impact_energy_tnt_kg": impact_energy_tnt_kg,
        "target_atmosphere_mass_kg": target_atmosphere_mass_kg,
        "bodies_needed": bodies_needed,
        "model_note": _MODEL_NOTE,
    }
