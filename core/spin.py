"""Phase W — rotating-habitat comfort calculator (``spin-comfort``).

The in-house analog of Theodore Hall's *SpinCalc*: given exactly **two** of the four
spin-state variables {radius, spin rate, centrifugal gravity, rim tangential velocity} it
solves the other two **plus** the three comfort-relevant derived quantities the existing
``gravity-acceleration`` / ``gravity-distance`` / ``gravity-rpm`` solves do not expose — rim
tangential velocity, head-to-foot gravity gradient, and Coriolis ratio for a walking occupant
— then classifies the design against the tiered comfort bands in ``core.spin_tables``.

Pure-math, self-validating (Phase-H/P contract → curated ``{"error"}``), ``query.py``-only.
No network, no DB, no RNG, no time. Extends (does not replace) the three ``gravity-*`` solves.
All kinematics are exact; only the pass/fail bands are a human-factors choice (see
``spin_tables._MODEL_NOTE``).
"""

import math

from core.equations import _STANDARD_GRAVITY as _G0
from core import spin_tables

_TWO_PI = 2.0 * math.pi


def _rpm_to_omega(rpm):
    return rpm * _TWO_PI / 60.0


def _omega_to_rpm(omega):
    return omega * 60.0 / _TWO_PI


def compute_spin_comfort(radius_m=None, rpm=None, accel_ms2=None,
                         tangential_velocity_ms=None,
                         occupant_height_m=1.8, walk_speed_ms=1.0,
                         criteria="all",
                         max_rpm=None, min_gravity_g=None, max_gravity_g=None,
                         min_tangential_velocity_ms=None,
                         max_gradient_pct=None, max_coriolis_pct=None):
    """Full rotating-habitat comfort readout + tiered criteria verdict.

    Supply exactly two of ``radius_m`` / ``rpm`` / ``accel_ms2`` /
    ``tangential_velocity_ms`` (the gravity anchor arrives here as ``accel_ms2`` — the
    ``query.py`` handler converts a ``--gravity-g`` value first). Returns a dict of solved +
    derived quantities and a per-tier verdict, or ``{"error": str}``.
    """
    # ── validate the supplied state anchors (each > 0) ──
    supplied = []
    for name, val in (("radius_m", radius_m), ("rpm", rpm),
                      ("accel_ms2", accel_ms2), ("tangential_velocity_ms", tangential_velocity_ms)):
        if val is not None:
            if val <= 0:
                return {"error": f"{name} must be > 0."}
            supplied.append(name)

    if len(supplied) != 2:
        return {"error": ("Provide exactly two state anchors from {radius_m, rpm, gravity, "
                          f"tangential_velocity_ms}}; got {len(supplied)}.")}

    # ── validate the occupant / reference parameters ──
    if occupant_height_m <= 0:
        return {"error": "occupant_height_m must be > 0."}
    if walk_speed_ms <= 0:
        return {"error": "walk_speed_ms must be > 0."}

    # ── validate the optional per-threshold overrides ──
    overrides = {
        "max_rpm": max_rpm, "min_gravity_g": min_gravity_g, "max_gravity_g": max_gravity_g,
        "min_tangential_velocity_ms": min_tangential_velocity_ms,
        "max_gradient_pct": max_gradient_pct, "max_coriolis_pct": max_coriolis_pct,
    }
    overridden = [k for k, v in overrides.items() if v is not None]
    for k in overridden:
        if overrides[k] <= 0:
            return {"error": f"{k} override must be > 0."}
    for k in ("max_gradient_pct", "max_coriolis_pct"):
        if overrides[k] is not None and overrides[k] > 100:
            return {"error": f"{k} override must be a percentage in (0, 100]."}

    # ── validate the criteria selector ──
    if criteria not in ("all",) + spin_tables._TIERS:
        return {"error": "criteria must be one of: conservative, moderate, relaxed, all."}

    # ── solve (ω, r) from the two anchors ──
    anchors = frozenset(supplied)
    if anchors == {"radius_m", "rpm"}:
        r = radius_m
        omega = _rpm_to_omega(rpm)
    elif anchors == {"radius_m", "accel_ms2"}:
        r = radius_m
        omega = math.sqrt(accel_ms2 / r)
    elif anchors == {"radius_m", "tangential_velocity_ms"}:
        r = radius_m
        omega = tangential_velocity_ms / r
    elif anchors == {"rpm", "accel_ms2"}:
        omega = _rpm_to_omega(rpm)
        r = accel_ms2 / omega ** 2
    elif anchors == {"rpm", "tangential_velocity_ms"}:
        omega = _rpm_to_omega(rpm)
        r = tangential_velocity_ms / omega
    else:  # {"accel_ms2", "tangential_velocity_ms"}
        r = tangential_velocity_ms ** 2 / accel_ms2
        omega = tangential_velocity_ms / r

    # ── occupant height must lie inside the radius (uses the SOLVED r) ──
    if occupant_height_m >= r:
        return {"error": f"occupant_height_m ({occupant_height_m}) must be < radius ({r:.6g} m)."}

    # ── derived quantities (exact rotational kinematics) ──
    a = omega ** 2 * r
    v = omega * r
    a_head = omega ** 2 * (r - occupant_height_m)
    gradient_fraction = occupant_height_m / r          # = (a − a_head) / a
    a_cor = 2.0 * omega * walk_speed_ms
    coriolis_ratio = a_cor / a                         # = 2u / v

    values = {
        "rpm": _omega_to_rpm(omega),
        "gravity_g": a / _G0,
        "tangential_velocity_ms": v,
        "gravity_gradient_pct": gradient_fraction * 100.0,
        "coriolis_ratio_pct": coriolis_ratio * 100.0,
    }

    # ── tiered comfort verdict ──
    tiers = spin_tables._TIERS if criteria == "all" else (criteria,)
    tol = spin_tables._BAND_TOL
    criteria_out = {}
    for tier in tiers:
        checks = {}
        tier_pass = True
        for name, direction, value_key in spin_tables._CHECKS:
            threshold = overrides[name] if overrides[name] is not None else spin_tables._COMFORT_BANDS[tier][name]
            value = values[value_key]
            if threshold is None:
                passed = None
            elif direction == "max":
                passed = value <= threshold * (1.0 + tol)
            else:  # "min"
                passed = value >= threshold * (1.0 - tol)
            checks[name] = {"value": value, "threshold": threshold, "pass": passed}
            if passed is False:
                tier_pass = False
        criteria_out[tier] = {"pass": tier_pass, "checks": checks}

    return {
        "radius_m": r,
        "rpm": values["rpm"],
        "angular_velocity_rads": omega,
        "accel_ms2": a,
        "gravity_g": values["gravity_g"],
        "tangential_velocity_ms": v,
        "occupant_height_m": occupant_height_m,
        "head_accel_ms2": a_head,
        "head_gravity_g": a_head / _G0,
        "gravity_gradient_fraction": gradient_fraction,
        "gravity_gradient_pct": values["gravity_gradient_pct"],
        "walk_speed_ms": walk_speed_ms,
        "coriolis_accel_ms2": a_cor,
        "coriolis_ratio": coriolis_ratio,
        "coriolis_ratio_pct": values["coriolis_ratio_pct"],
        "anchors": supplied,
        "criteria": criteria_out,
        "overridden_thresholds": overridden,
        "model_note": spin_tables._MODEL_NOTE,
        "notes": list(spin_tables._NOTES),  # normalize tuple → list (P4.4, JSON-identical)
    }
