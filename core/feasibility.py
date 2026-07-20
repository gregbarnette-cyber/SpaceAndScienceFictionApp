# core/feasibility.py — Phase R2: constraint / feasibility engine.
#
# PURE: no Qt, no file I/O, no network of its own. Determinism is the headline
# contract — same (seed, anchor_star, constraint spec) → byte-identical output.
#
# R2-C1 scope (this file): the two new-physics helper groups, all Tier-A textbook
# celestial mechanics, NO research gate —
#   • G1 — multi-body packing stability (mutual Hill radius + Gladman/Chambers Δ).
#   • G2 — resonance / co-orbital diagnostics (period ratio → nearest MMR; the
#          Gascheau/Routh co-orbital L4/L5 criterion).
# They reuse the kg / solar-mass constants from core.equations (no reinvention).
#
# Later checkpoints append here: the constraint spec validator + rule registry +
# evaluate_feasibility (R2-C2), Layer-4 alternatives + Layer-3 origin (R2-C3),
# the optional N-body confirmer wiring (R2-C4), and multi-star S/P-type (R2-C5).

import math

from core.equations import (
    _EARTH_MASS_KG, _SOLAR_MASS_KG,
    compute_roche_limit, compute_hill_sphere, compute_atmosphere_retention,
    compute_solvent_zone, compute_binary_orbit_stability,
)
from core.priors import DefaultPriors, get_priors, PriorsUnavailable

# ── G1 — packing-stability thresholds ────────────────────────────────────────
# Gladman (1993) Hill-stability floor for an adjacent pair, Δ_crit = 2√3 ≈ 3.464;
# Chambers (1996) long-term N-planet separation, Δ_long ≈ 10 (Phase R2 plan D4).
# The gray band [Δ_crit, Δ_long) is "marginal" (→ optional N-body confirmation).
_DELTA_HILL_CRIT = 2.0 * math.sqrt(3.0)        # ≈ 3.4641
_DELTA_LONG_TERM = 10.0

# ── G2 — co-orbital (Trojan) stability ───────────────────────────────────────
# Gascheau / Routh critical mass ratio for L4/L5 linear stability:
# μ_crit = ½·(1 − √(23/27)) ≈ 0.03852. A co-orbital pair is L4/L5-stable when
# (m_host + m_companion) / M_star ≲ μ_crit.
_GASCHEAU_CRIT_MU = 0.5 * (1.0 - math.sqrt(23.0 / 27.0))   # ≈ 0.038521


# ── G1 · multi-body packing stability ────────────────────────────────────────

def mutual_hill(m1_earth, m2_earth, a1_au, a2_au, star_mass_solar):
    """Mutual Hill radius + separation Δ for an adjacent planet pair.

    R_H,m = ((m1 + m2) / (3·M★))^(1/3) · (a1 + a2)/2     (AU)
    Δ      = |a2 − a1| / R_H,m                            (dimensionless)

    Masses in Earth masses, semi-major axes in AU, star mass in solar masses.
    Returns ``{r_hill_mutual_au, delta, hill_stable, long_term_stable}`` —
    ``hill_stable`` is Δ ≥ 2√3 (Gladman), ``long_term_stable`` is Δ ≥ 10
    (Chambers; the Phase R2 long-term threshold) — or ``{"error": str}``.
    """
    if (m1_earth <= 0 or m2_earth <= 0 or a1_au <= 0 or a2_au <= 0
            or star_mass_solar <= 0):
        return {"error": "Masses, semi-major axes, and star mass must be positive."}

    mass_ratio = ((m1_earth + m2_earth) * _EARTH_MASS_KG) / (
        3.0 * star_mass_solar * _SOLAR_MASS_KG)
    r_hill_au = mass_ratio ** (1.0 / 3.0) * (a1_au + a2_au) / 2.0
    delta = abs(a2_au - a1_au) / r_hill_au
    return {
        "r_hill_mutual_au": r_hill_au,
        "delta": delta,
        "hill_stable": delta >= _DELTA_HILL_CRIT,
        "long_term_stable": delta >= _DELTA_LONG_TERM,
    }


# ── G2 · resonance / co-orbital diagnostics ──────────────────────────────────

def period_ratio(a_inner_au, a_outer_au, star_mass_solar=1.0):
    """Orbital period ratio (outer/inner ≥ 1) from the two semi-major axes.

    P ∝ a^(3/2)/√M; for two bodies around the *same* star the stellar mass
    cancels, so the ratio depends only on the SMAs — ``star_mass_solar`` is
    accepted for signature parity (Kepler's third law) but does not affect the
    result. Raises ``ValueError`` for a non-positive SMA.
    """
    if a_inner_au <= 0 or a_outer_au <= 0:
        raise ValueError("Semi-major axes must be positive.")
    lo, hi = sorted((a_inner_au, a_outer_au))
    return (hi / lo) ** 1.5


def nearest_mmr(ratio, max_order=5):
    """Nearest low-order mean-motion resonance p:q to a period ratio.

    Enumerates reduced fractions p/q with 1 < p/q and ``p, q ≤ max_order``
    (gcd(p, q) = 1), returning the closest. ``ratio`` < 1 is inverted first.
    Returns ``{p, q, ratio_str ("p:q"), offset_frac}`` where ``offset_frac`` is
    the *signed* fractional offset (ratio − p/q)/(p/q) of the actual ratio from
    the exact commensurability — or ``{"error": str}`` for a non-positive ratio.
    """
    if ratio <= 0:
        return {"error": "Period ratio must be positive."}
    r = ratio if ratio >= 1.0 else 1.0 / ratio

    best = None
    for q in range(1, max_order + 1):
        for p in range(q + 1, max_order + 1):
            if math.gcd(p, q) != 1:
                continue
            val = p / q
            off = (r - val) / val
            if best is None or abs(off) < abs(best["offset_frac"]):
                best = {"p": p, "q": q, "ratio_str": f"{p}:{q}", "offset_frac": off}
    return best


def in_mmr(a1_au, a2_au, star_mass_solar=1.0, ratio="2:1", tol=0.03):
    """Whether two bodies sit within ``tol`` (fractional) of the ``"p:q"`` MMR.

    Compares the period ratio (outer/inner) against p/q (order-independent —
    "2:1" and "1:2" are equivalent). A malformed ``ratio`` string → ``False``.
    """
    try:
        p_str, q_str = str(ratio).split(":")
        p, q = int(p_str), int(q_str)
    except (ValueError, AttributeError):
        return False
    if p <= 0 or q <= 0:
        return False
    pr = period_ratio(a1_au, a2_au, star_mass_solar)
    target = max(p, q) / min(p, q)
    return abs(pr - target) / target <= tol


def gascheau_coorbital_stable(host_mass_earth, companion_mass_earth, star_mass_solar):
    """Gascheau/Routh L4/L5 (Trojan) linear-stability test for a co-orbital pair.

    Stable when (m_host + m_companion)/M★ < μ_crit = ½·(1 − √(23/27)) ≈ 0.0385.
    The companion (Trojan) may be massless (``companion_mass_earth = 0``).
    Returns ``{mass_ratio, criterion, stable}`` — or ``{"error": str}``.
    """
    if host_mass_earth <= 0 or companion_mass_earth < 0 or star_mass_solar <= 0:
        return {"error": "Host mass and star mass must be positive; "
                         "companion mass must be ≥ 0."}
    mass_ratio = ((host_mass_earth + companion_mass_earth) * _EARTH_MASS_KG) / (
        star_mass_solar * _SOLAR_MASS_KG)
    return {
        "mass_ratio": mass_ratio,
        "criterion": _GASCHEAU_CRIT_MU,
        "stable": mass_ratio < _GASCHEAU_CRIT_MU,
    }


# ── R2-C2 · constraint spec validator + rule registry + evaluator ────────────
#
# evaluate_feasibility builds the base system via R1's generate_system (no
# constraints → no recursion), then dispatches each constraint through a rule in
# _RULE_REGISTRY. R2-C2 emits Layers 1–2 (verdict + mechanism); Layers 3 (origin)
# and 4 (alternatives) are stubbed here and populated in R2-C3.

# Representative masses (Earth masses) when a constraint names a body *type* but
# not a mass (e.g. a trojan companion). Order-of-magnitude class midpoints.
_TYPE_MASS_EARTH = {
    "terrestrial": 1.0, "rocky": 1.0, "super_earth": 5.0, "ice": 15.0,
    "gas": 100.0, "super_jovian": 700.0, "brown_dwarf": 5000.0,
}

# Low-order resonances probed for "protecting" a tight packing gap.
_PROTECTING_RATIOS = ("2:1", "3:2", "4:3", "5:3", "5:2", "3:1")

_LIQUID_LO_K, _LIQUID_HI_K = 250.0, 330.0   # "temperate" band for a terraformable moon


# ── result assembly ──────────────────────────────────────────────────────────

def _result(c, verdict, layer1, layer2, layer3=None, layer4=None):
    """Assemble a per-constraint result. Layers 3/4 default to R2-C3 stubs."""
    return {
        "id": c.get("id"),
        "type": c.get("type"),
        "verdict": verdict,
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3 if layer3 is not None
                  else {"hypotheses": [], "grounding": "default-extrapolation"},
        "layer4": layer4 if layer4 is not None else {"alternatives": []},
    }


def _not_evaluated(c, reason):
    """A constraint that could not be judged (unknown type / unresolvable ref) —
    a neutral verdict, never a hard error."""
    return _result(
        c, "not_evaluated",
        {"stable": None, "reason": reason},
        {"mechanism": None, "checked": [], "note": None})


# ── reference / location resolution ──────────────────────────────────────────

def _resolve_ref(ref, planets, derived):
    """Resolve a constraint reference to a planet dict, or None.

    Accepts a planet letter ('b' = innermost by SMA), an exact/suffix name match
    ('47 UMa b'), or a symbolic anchor (outermost / innermost / giant_in_hz /
    super_jovian_in_hz). Unresolvable → None (caller emits not_evaluated)."""
    if not planets:
        return None
    s = str(ref).strip()
    low = s.lower()

    if low == "outermost":
        return max(planets, key=lambda p: p.get("a_au") or 0.0)
    if low == "innermost":
        return min(planets, key=lambda p: p.get("a_au") or float("inf"))
    if low in ("giant", "giant_in_hz", "super_jovian_in_hz"):
        types = ({"super_jovian"} if low == "super_jovian_in_hz"
                 else {"gas", "super_jovian"})
        giants = [p for p in planets if p.get("type") in types and p.get("a_au")]
        if not giants:
            return None
        in_hz = [p for p in giants if p.get("in_hz")]
        pool = in_hz if in_hz else giants
        lo, hi = derived.get("hz_cons_inner"), derived.get("hz_cons_outer")
        if lo and hi:
            center = 0.5 * (lo + hi)
            return min(pool, key=lambda p: abs(p["a_au"] - center))
        return pool[0]

    for p in planets:                       # exact / suffix name match
        nm = str(p.get("name", ""))
        if nm == s or nm.lower() == low or nm.lower().endswith(" " + low):
            return p

    if len(low) == 1 and "a" <= low <= "z":   # planet letter (b = innermost)
        ordered = sorted((p for p in planets if p.get("a_au") is not None),
                         key=lambda p: p["a_au"])
        idx = ord(low) - ord("b")
        if 0 <= idx < len(ordered):
            return ordered[idx]
    return None


def _brackets(target_au, planets):
    """Nearest interior / exterior planet to a target SMA (each may be None)."""
    interior = [p for p in planets if p.get("a_au") is not None and p["a_au"] < target_au]
    exterior = [p for p in planets if p.get("a_au") is not None and p["a_au"] > target_au]
    inner = max(interior, key=lambda p: p["a_au"]) if interior else None
    outer = min(exterior, key=lambda p: p["a_au"]) if exterior else None
    return inner, outer


def _resolve_location(loc, planets, derived):
    """Resolve a constraint location → (target_au, inner_bracket, outer_bracket, error)."""
    kind = (loc.get("kind") or "").lower()
    if kind == "at":
        au = loc.get("au")
        if not isinstance(au, (int, float)) or au <= 0:
            return None, None, None, "location 'at' needs a positive 'au'."
        inner, outer = _brackets(au, planets)
        return float(au), inner, outer, None
    if kind == "between":
        a = _resolve_ref(loc.get("ref_a"), planets, derived)
        b = _resolve_ref(loc.get("ref_b"), planets, derived)
        if a is None or b is None or a.get("a_au") is None or b.get("a_au") is None:
            return None, None, None, "location 'between' references could not be resolved."
        target = 0.5 * (a["a_au"] + b["a_au"])
        inner, outer = (a, b) if a["a_au"] < b["a_au"] else (b, a)
        return target, inner, outer, None
    if kind in ("interior_to", "exterior_to"):
        ref = _resolve_ref(loc.get("ref"), planets, derived)
        if ref is None or ref.get("a_au") is None:
            return None, None, None, f"location '{kind}' reference could not be resolved."
        target = ref["a_au"] / 1.6 if kind == "interior_to" else ref["a_au"] * 1.6
        inner, outer = _brackets(target, planets)
        return target, inner, outer, None
    if kind == "in_hz":
        which = (loc.get("hz") or "cons").lower()
        if which.startswith("opt"):
            lo, hi = derived.get("hz_opt_inner"), derived.get("hz_opt_outer")
        else:
            lo, hi = derived.get("hz_cons_inner"), derived.get("hz_cons_outer")
        if not lo or not hi:
            return None, None, None, "habitable-zone bounds unavailable."
        target = 0.5 * (lo + hi)
        inner, outer = _brackets(target, planets)
        return target, inner, outer, None
    if kind == "in_zone":
        zone = (loc.get("zone") or "hz").lower()
        snow = derived.get("snow_line")
        opt_out = derived.get("hz_opt_outer") or 0.0
        if zone == "hot":
            target = 0.5 * (derived.get("hz_opt_inner") or 0.5)
        elif zone == "cold":
            target = 0.5 * (opt_out + (snow or opt_out * 2.0))
        elif zone == "far":
            target = 2.0 * (snow or opt_out * 2.0)
        else:   # hz
            lo, hi = derived.get("hz_cons_inner"), derived.get("hz_cons_outer")
            target = 0.5 * ((lo or 0.0) + (hi or 1.0))
        if target <= 0:
            return None, None, None, "could not resolve zone target."
        inner, outer = _brackets(target, planets)
        return target, inner, outer, None
    return None, None, None, f"unsupported location kind: {kind!r}"


def _protecting_mmr(a1, a2, star_mass, tol=0.03):
    """First low-order MMR (from _PROTECTING_RATIOS) the pair sits in, or None."""
    for ratio in _PROTECTING_RATIOS:
        if in_mmr(a1, a2, star_mass, ratio=ratio, tol=tol):
            return ratio
    return None


# ── multi-star S/P-type gate (R2-C5) ─────────────────────────────────────────

def _binary_gate(target_au, star_mass_solar, companion):
    """Holman & Wiegert S/P-type stability of a body at ``target_au`` against a
    companion hint ``{mass_solar, sma_au[, ecc]}``. Returns the
    ``compute_binary_orbit_stability`` dict, or None when there is no companion /
    the computation errors (gate then does not apply)."""
    if not companion:
        return None
    res = compute_binary_orbit_stability(
        star_mass_solar, companion.get("mass_solar"), companion.get("sma_au"),
        target_au, eccentricity=companion.get("ecc", 0.0) or 0.0)
    return None if "error" in res else res


def _apply_binary_gate(res, target_au, derived):
    """Fold a multi-star S/P-type verdict into a placed-body result. Binary
    instability is decisive (overrides a feasible/marginal packing verdict →
    infeasible); a stable binary region annotates the result. No companion →
    ``res`` unchanged."""
    gate = _binary_gate(target_au, derived["mass_solar"], derived.get("companion"))
    if gate is None:
        return res
    otype = gate["orbit_type"]
    crit = (gate["stype_critical_sma_au"] if otype == "S-type"
            else gate["ptype_critical_sma_au"])
    res = dict(res)
    l1 = dict(res["layer1"]); l2 = dict(res["layer2"])
    l1["metrics"] = dict(l1.get("metrics") or {})
    l1["metrics"]["binary_orbit_type"] = otype
    l1["metrics"]["binary_critical_au"] = round(crit, 4) if crit is not None else None
    checked = list(l2.get("checked") or [])
    if "binary_stability" not in checked:
        checked.append("binary_stability")
    l2["checked"] = checked

    if not gate["is_stable"]:
        res["verdict"] = "infeasible"
        l1["stable"] = False
        l1["reason"] = (l1.get("reason", "") + f" Binary truncation: at {target_au:.3f} AU this "
                        f"is an {otype} orbit, unstable against the companion "
                        f"(critical {otype} SMA ≈ {crit:.3f} AU — {gate['stable_region_description']}).")
        l2["mechanism"] = None
    else:
        l1["reason"] = (l1.get("reason", "") + f" Also within the binary {otype} stable region "
                        f"(critical ≈ {crit:.3f} AU).")
    res["layer1"] = l1
    res["layer2"] = l2
    return res


# ── the four core rules (Layers 1–2) ─────────────────────────────────────────

def _rule_planet_at_location(c, base, derived):
    planets = base["planets"]
    star_mass = derived["mass_solar"]
    ptype = c.get("planet_type", "terrestrial")
    mass = c.get("mass_earth")
    if mass is None:
        mass = _TYPE_MASS_EARTH.get(ptype, 1.0)
    if not isinstance(mass, (int, float)) or mass <= 0:
        return _not_evaluated(c, "planet_at_location needs a positive 'mass_earth'.")

    target, inner, outer, err = _resolve_location(c.get("location") or {}, planets, derived)
    if err:
        return _not_evaluated(c, err)

    metrics = {"target_au": round(target, 5)}
    deltas = []
    for label, nb in (("interior", inner), ("exterior", outer)):
        if nb is not None and nb.get("mass_earth") and nb.get("a_au"):
            mh = mutual_hill(mass, nb["mass_earth"], target, nb["a_au"], star_mass)
            if "error" not in mh:
                deltas.append((nb, mh["delta"]))
                metrics[f"delta_to_{label}"] = round(mh["delta"], 3)
    checked = ["hill_packing"]

    if not deltas:
        res = _result(
            c, "feasible",
            {"stable": True,
             "reason": f"{mass:g} M⊕ {ptype} at {target:.3f} AU has no massive neighbour "
                       "to destabilise it (isolated).",
             "metrics": metrics},
            {"mechanism": "isolated", "checked": checked,
             "note": "no adjacent planet within the system"})
    else:
        min_nb, min_delta = min(deltas, key=lambda t: t[1])
        metrics["min_delta"] = round(min_delta, 3)

        if min_delta >= _DELTA_LONG_TERM:
            res = _result(
                c, "feasible",
                {"stable": True,
                 "reason": f"{mass:g} M⊕ at {target:.3f} AU is {min_delta:.1f} mutual Hill radii "
                           f"from {min_nb['name']} (≥ {int(_DELTA_LONG_TERM)} → long-term stable).",
                 "metrics": metrics},
                {"mechanism": "hill_packing", "checked": checked, "note": None})
        else:
            checked.append("mean_motion_resonance")
            mmr = _protecting_mmr(target, min_nb["a_au"], star_mass)
            if min_delta >= _DELTA_HILL_CRIT:
                reason = (f"{mass:g} M⊕ at {target:.3f} AU is {min_delta:.2f} mutual Hill radii "
                          f"from {min_nb['name']} — above the {_DELTA_HILL_CRIT:.2f} Hill floor but "
                          f"below the {int(_DELTA_LONG_TERM)} long-term threshold "
                          "(marginal; N-body to confirm).")
                mech = "hill_packing"
                if mmr:
                    mech = "mean_motion_resonance"
                    reason += f" A {mmr} resonance with {min_nb['name']} could protect it."
                res = _result(c, "marginal", {"stable": None, "reason": reason, "metrics": metrics},
                              {"mechanism": mech, "checked": checked,
                               "note": "gray band [2√3, 10) mutual Hill radii"})
            elif mmr:
                res = _result(
                    c, "marginal",
                    {"stable": None,
                     "reason": f"{mass:g} M⊕ at {target:.3f} AU is only {min_delta:.2f} mutual Hill "
                               f"radii from {min_nb['name']} (below the {_DELTA_HILL_CRIT:.2f} floor), "
                               f"but a {mmr} mean-motion resonance could protect it.",
                     "metrics": metrics},
                    {"mechanism": "mean_motion_resonance", "checked": checked,
                     "note": "resonant protection plausible despite tight packing"})
            else:
                res = _result(
                    c, "infeasible",
                    {"stable": False,
                     "reason": f"{mass:g} M⊕ at {target:.3f} AU sits only {min_delta:.2f} mutual Hill "
                               f"radii from {min_nb['name']} — below the {_DELTA_HILL_CRIT:.2f} "
                               "Hill-stability floor, and no protecting resonance was found.",
                     "metrics": metrics},
                    {"mechanism": None, "checked": checked,
                     "note": "no protecting mean-motion resonance near the gap"})

    # Multi-star gate (R2-C5): a companion hint truncates where a body can survive.
    return _apply_binary_gate(res, target, derived)


def _rule_trojan(c, base, derived):
    planets = base["planets"]
    star_mass = derived["mass_solar"]
    host = _resolve_ref(c.get("host"), planets, derived)
    if host is None:
        return _not_evaluated(c, f"trojan host {c.get('host')!r} could not be resolved "
                                 "(no matching body in the system).")
    if not host.get("mass_earth"):
        return _not_evaluated(c, f"trojan host {host['name']} has no known mass.")
    ctype = c.get("companion_type", "terrestrial")
    cmass = c.get("mass_earth", _TYPE_MASS_EARTH.get(ctype, 1.0))
    point = (c.get("point") or "L4").upper()

    g = gascheau_coorbital_stable(host["mass_earth"], cmass, star_mass)
    if "error" in g:
        return _not_evaluated(c, g["error"])
    checked = ["gascheau_coorbital", "lagrange_L4_L5"]
    metrics = {"mass_ratio": g["mass_ratio"], "criterion": g["criterion"], "host": host["name"]}

    if g["stable"]:
        return _result(
            c, "feasible",
            {"stable": True,
             "reason": f"(host {host['name']} + {cmass:g} M⊕ companion)/M★ = {g['mass_ratio']:.4g} "
                       f"< Gascheau limit {g['criterion']:.4g}; {point} linearly stable.",
             "metrics": metrics},
            {"mechanism": "trojan", "checked": checked,
             "note": f"co-orbital libration about {point}"})
    return _result(
        c, "infeasible",
        {"stable": False,
         "reason": f"(host {host['name']} + {cmass:g} M⊕)/M★ = {g['mass_ratio']:.4g} exceeds the "
                   f"Gascheau {point} stability limit {g['criterion']:.4g}.",
         "metrics": metrics},
        {"mechanism": None, "checked": checked,
         "note": "host too massive for stable co-orbital companions"})


def _rule_moon(c, base, derived):
    planets = base["planets"]
    star_mass = derived["mass_solar"]
    host = _resolve_ref(c.get("host"), planets, derived)
    if host is None:
        return _not_evaluated(c, f"moon host {c.get('host')!r} could not be resolved.")
    if not host.get("mass_earth") or not host.get("a_au"):
        return _not_evaluated(c, f"moon host {host['name']} has no known mass / SMA.")

    moon_mass = c.get("mass_earth", 0.05)
    roche = compute_roche_limit(host["mass_earth"], 3.0, host.get("radius_earth"))
    hill = compute_hill_sphere(star_mass, host["mass_earth"], host["a_au"], host.get("ecc") or 0.0)
    if "error" in roche or "error" in hill:
        return _not_evaluated(c, "could not compute Roche/Hill bounds for the host.")

    inner_au = roche["fluid_au"]
    outer_au = hill["stable_orbit_limit_au"]
    checked = ["roche_limit", "hill_stable_zone"]
    metrics = {"roche_fluid_au": round(inner_au, 6), "stable_outer_au": round(outer_au, 6),
               "host": host["name"]}

    if outer_au <= inner_au:
        return _result(
            c, "infeasible",
            {"stable": False,
             "reason": f"{host['name']}'s ½-Hill stable limit ({outer_au:.4f} AU) is inside its "
                       f"fluid Roche limit ({inner_au:.4f} AU) — no stable satellite annulus.",
             "metrics": metrics},
            {"mechanism": None, "checked": checked, "note": "empty stable annulus"})

    if not c.get("terraformable"):
        return _result(
            c, "feasible",
            {"stable": True,
             "reason": f"a {moon_mass:g} M⊕ moon fits between {host['name']}'s fluid Roche limit "
                       f"({inner_au:.4f} AU) and ½-Hill stable limit ({outer_au:.4f} AU).",
             "metrics": metrics},
            {"mechanism": "bound_satellite", "checked": checked, "note": None})

    # terraformable: temperate + holds an atmosphere at the host's orbit.
    from core.generate import _equilibrium_temp, _radius_earth_for_type
    t_eq = _equilibrium_temp(host["a_au"], derived["luminosity"])
    metrics["t_eq_k"] = round(t_eq, 2) if t_eq else None
    checked.append("equilibrium_temp")
    retained = []
    if t_eq:
        ret = compute_atmosphere_retention(moon_mass, _radius_earth_for_type("rocky", moon_mass), t_eq)
        if "error" not in ret:
            retained = [g["gas"] for g in ret["gases"] if g["status"] == "Retained"]
    temperate = bool(t_eq and _LIQUID_LO_K <= t_eq <= _LIQUID_HI_K)

    if temperate and retained:
        return _result(
            c, "marginal",
            {"stable": None,
             "reason": f"a {moon_mass:g} M⊕ moon fits the stable annulus; at {host['name']}'s orbit "
                       f"T_eq ≈ {t_eq:.0f} K (temperate) and it retains {', '.join(retained)}. "
                       "Marginal: tidal-heating budget is not modelled in R2.",
             "metrics": metrics},
            {"mechanism": "bound_satellite", "checked": checked,
             "note": "moon habitability not fully confirmed (no tidal-heating model)"})
    teq_str = f"{t_eq:.0f} K" if t_eq else "unknown"
    return _result(
        c, "infeasible",
        {"stable": False,
         "reason": f"a {moon_mass:g} M⊕ moon is dynamically placeable, but at {host['name']}'s "
                   f"orbit T_eq ≈ {teq_str} is outside the temperate band / it cannot hold a "
                   "substantial atmosphere — not terraformable as requested.",
         "metrics": metrics},
        {"mechanism": "bound_satellite", "checked": checked,
         "note": "stable orbit exists but the terraformable condition fails"})


def _rule_resonance(c, base, derived):
    planets = base["planets"]
    star_mass = derived["mass_solar"]
    bodies = c.get("bodies") or []
    if len(bodies) != 2:
        return _not_evaluated(c, "resonance needs exactly two body references.")
    p1 = _resolve_ref(bodies[0], planets, derived)
    p2 = _resolve_ref(bodies[1], planets, derived)
    if p1 is None or p2 is None or p1.get("a_au") is None or p2.get("a_au") is None:
        return _not_evaluated(c, "resonance body references could not be resolved.")
    ratio = c.get("ratio", "2:1")

    pr = period_ratio(p1["a_au"], p2["a_au"], star_mass)
    nm = nearest_mmr(pr)
    nearest = nm.get("ratio_str") if isinstance(nm, dict) and "error" not in nm else None
    checked = ["mean_motion_resonance"]
    metrics = {"period_ratio": round(pr, 4), "nearest_mmr": nearest}

    if in_mmr(p1["a_au"], p2["a_au"], star_mass, ratio=ratio):
        return _result(
            c, "feasible",
            {"stable": True,
             "reason": f"{p1['name']} and {p2['name']} have period ratio {pr:.3f}, within "
                       f"tolerance of the {ratio} resonance.",
             "metrics": metrics},
            {"mechanism": "mean_motion_resonance", "checked": checked, "note": f"in {ratio} MMR"})
    return _result(
        c, "infeasible",
        {"stable": False,
         "reason": f"{p1['name']} and {p2['name']} have period ratio {pr:.3f} (nearest MMR "
                   f"{nearest}), not the requested {ratio}.",
         "metrics": metrics},
        {"mechanism": None, "checked": checked, "note": "bodies are not in the requested resonance"})


_RULE_REGISTRY = {
    "planet_at_location": _rule_planet_at_location,
    "trojan": _rule_trojan,
    "moon": _rule_moon,
    "resonance": _rule_resonance,
}


# ── spec validation + the evaluator ──────────────────────────────────────────

def validate_constraints(constraints, companion):
    """Shape-level validation of the constraint list + optional companion hint.
    Returns ``{"error": str}`` for a malformed spec, else ``None``."""
    if not constraints or not isinstance(constraints, (list, tuple)):
        return {"error": "evaluate_feasibility requires a non-empty 'constraints' list."}
    for i, c in enumerate(constraints):
        if not isinstance(c, dict):
            return {"error": f"constraint {i} must be an object."}
        if not c.get("type"):
            return {"error": f"constraint {i} is missing 'type'."}
    if companion is not None:
        if not isinstance(companion, dict):
            return {"error": "companion must be an object {mass_solar, sma_au[, ecc]}."}
        for k in ("mass_solar", "sma_au"):
            v = companion.get(k)
            if not isinstance(v, (int, float)) or v <= 0:
                return {"error": f"companion.{k} must be a positive number."}
        ecc = companion.get("ecc")
        if ecc is not None and (not isinstance(ecc, (int, float)) or not (0 <= ecc < 1)):
            return {"error": "companion.ecc must be in the range 0 ≤ e < 1."}
    return None


def _derived_from_star(star):
    """Rebuild the physics-values bundle the rules need from a (public) star dict —
    avoids reaching into R1's internals. Uses the star's rounded values (still
    deterministic)."""
    return {
        "luminosity": star.get("luminosity"),
        "mass_solar": star.get("mass_solar"),
        "hz_cons_inner": star.get("hz_inner_au"),
        "hz_cons_outer": star.get("hz_outer_au"),
        "hz_opt_inner": star.get("hz_opt_inner_au"),
        "hz_opt_outer": star.get("hz_opt_outer_au"),
        "snow_line": star.get("snow_line_au"),
        "teff": star.get("teff"),
        "feh": star.get("feh"),          # R3-V2 B4: metallicity-aware origin narrative
    }


def evaluate_feasibility(seed, anchor_star=None, spectral_class=None, n_planets=None,
                         require_habitable=False, constraints=None, companion=None,
                         research_policy="permissive", nbody=False):
    """Evaluate a constraint spec against a (deterministically) generated base system.

    Builds the base via R1's ``generate_system`` (no constraints → no recursion),
    then dispatches each constraint through ``_RULE_REGISTRY``. R2-C2 emits the
    verdict + Layers 1–2; Layers 3 (origin) and 4 (alternatives) are stubbed and
    filled in R2-C3. The optional N-body confirmer (``nbody=True``) lands in R2-C4.
    Self-validating: a malformed spec → ``{"error": str}``; an unresolvable ref or
    unknown constraint type is *not* an error (that constraint is ``not_evaluated``).
    """
    err = validate_constraints(constraints, companion)
    if err:
        return err

    # Resolve the priors provider — research-calibrated under strict (gates BOTH the
    # base-system sampling and the Layer-3 narrative, D5). strict with no ingested
    # dataset → curated error (no silent fallback).
    try:
        priors = get_priors(research_policy)
    except PriorsUnavailable as e:
        return {"error": str(e)}

    # Function-local import keeps the generate↔feasibility relationship one-way at
    # module load (generate.py imports feasibility only inside generate_system).
    from core.generate import generate_system
    base = generate_system(seed, anchor_star=anchor_star, spectral_class=spectral_class,
                           n_planets=n_planets, require_habitable=require_habitable,
                           research_policy=research_policy)
    if "error" in base:
        return base

    derived = _derived_from_star(base["star"])
    derived["companion"] = companion          # multi-star gate (R2-C5); None when absent
    notes = list(base.get("notes", []))
    warnings = list(base.get("warnings", []))

    # Multi-star handling (D3): a supplied companion hint drives the quantitative
    # S/P-type gate; a known real-anchor multiple with no hint falls back to R1's
    # conservative safe-cap, with a note pointing at the hint.
    if companion:
        notes.append(f"Binary S/P-type stability evaluated against the supplied companion "
                     f"hint (M = {companion['mass_solar']} M☉, a = {companion['sma_au']} AU"
                     + (f", e = {companion['ecc']}" if companion.get("ecc") else "") + ").")
    else:
        mult = base["star"].get("multiplicity") or {}
        if mult.get("is_multiple"):
            notes.append("Anchor is a known multiple; supply a 'companion' hint "
                         "{mass_solar, sma_au[, ecc]} for a quantitative S/P-type verdict. "
                         "Synthetic bodies use the R1 conservative safe-cap (companion "
                         "truncation not modelled without the hint).")

    results = []
    for i, c in enumerate(constraints):
        rule = _RULE_REGISTRY.get(c.get("type"))
        if rule is None:
            res = _not_evaluated(c, f"unsupported constraint type: {c.get('type')!r}")
        else:
            try:
                res = rule(c, base, derived)
            except Exception as e:                       # never let one rule abort the report
                res = _not_evaluated(c, f"could not evaluate: {type(e).__name__}: {e}")
        if not res.get("id"):
            res["id"] = f"c{i + 1}"
        # Optional N-body confirmation of a marginal packing verdict (R2-C4), then
        # Layer 3 (origin) for any evaluated constraint and Layer 4 (alternatives)
        # only when the verdict is not feasible (rule is non-None here).
        if res["verdict"] != "not_evaluated":
            if nbody and res["verdict"] == "marginal":
                res = _nbody_confirm(res, c, base, derived)
            res["layer3"] = _origin_hypotheses(c, base, derived, res, priors)
            if res["verdict"] in ("infeasible", "marginal"):
                res["layer4"] = _alternatives(c, base, derived, rule, res["verdict"])
        results.append(res)

    evaluated = [r for r in results if r["verdict"] != "not_evaluated"]
    feasible = bool(evaluated) and all(r["verdict"] == "feasible" for r in evaluated)
    _ver = getattr(priors, "version", None)
    notes.append("Four-layer feasibility report; Layer-3 origin narrative "
                 f"grounding={priors.grounding}"
                 + (f" (dataset {_ver})." if _ver else "."))

    return {
        "seed": seed,
        "mode": base.get("mode"),
        "anchor_star": base.get("anchor_star"),
        "star": base["star"],
        "planets": base["planets"],
        "feasible": feasible,
        "constraints": results,
        "warnings": warnings,
        "notes": notes,
    }


# ── R2-C3 · Layer-3 origin (tagged) + Layer-4 alternatives (deterministic) ────
#
# Layer 3 attaches confidence-tagged formation-pathway hypotheses from simple
# DefaultPriors-backed heuristics — every hypothesis carries
# grounding="default-extrapolation" (R3 swaps in research-calibrated priors with
# no engine change). Layer 4 runs a fixed, ordered single-parameter relaxation
# scan and reports the first improvement per axis, each as {change, result,
# spec_patch} — spec_patch being the exact mutation the GUI's clickable-apply
# (D6) re-runs. Both are deterministic (no RNG, ordered scans).

# Heuristic origin priors per context key — the DefaultPriors fallback. R3 lets an
# ingested ResearchPriors dataset override any context via `origin_priors`; an omitted
# context falls back to this table, tagged grounding="default-extrapolation" even under
# strict (honest mixed tagging). The identity fixture mirrors this table exactly, so a
# strict run against it reproduces the heuristic narrative (badge aside).
# R3-V2 B4: metallicity-qualified origin vocabulary. Any base context key may carry a
# "<key>:metal_rich" / "<key>:metal_poor" variant in a v2 origin_priors block; when the
# host's [Fe/H] falls in the corresponding tail AND the dataset defines the variant, it
# is preferred over the base key (else the base key / heuristic is used — fully backward-
# compatible with datasets that define only the base v1 keys). Thresholds are documented
# engine knobs (the spectral×zone×metallicity conditioning the v2 request sketched).
_FEH_METAL_RICH = 0.15
_FEH_METAL_POOR = -0.35


def _metallicity_tag(feh):
    """'metal_rich' / 'metal_poor' / None for a host [Fe/H] (None when absent)."""
    if feh is None:
        return None
    if feh >= _FEH_METAL_RICH:
        return "metal_rich"
    if feh <= _FEH_METAL_POOR:
        return "metal_poor"
    return None


_DEFAULT_ORIGIN = {
    "planet_at_location:in_situ_beyond_snow": [("in-situ accretion beyond the snow line", "high")],
    "planet_at_location:in_situ_inner":       [("in-situ accretion", "medium")],
    "planet_at_location:resonant_migration":  [("convergent migration into resonance", "medium")],
    "planet_at_location:infeasible":          [("captured / scattered survivor", "low")],
    "trojan:feasible":                        [("in-situ co-accretion / capture into the Lagrange point", "medium")],
    "trojan:infeasible":                      [("no stable co-orbital pathway (host too massive)", "low")],
    "moon:feasible":                          [("capture / circumplanetary-disk formation", "medium")],
    "moon:infeasible":                        [("no stable satellite pathway", "low")],
    "resonance:feasible":                     [("convergent migration into resonance", "high")],
    "resonance:infeasible":                   [("would require migration / capture into resonance", "low")],
}


def _origin_context_keys(c, derived, res):
    """The ordered origin-context key(s) for an evaluated constraint (R3 vocabulary)."""
    t = c.get("type")
    v = res["verdict"]
    keys = []
    if t == "planet_at_location":
        if v == "infeasible":
            keys.append("planet_at_location:infeasible")
        else:
            target = (res["layer1"].get("metrics") or {}).get("target_au")
            snow = derived.get("snow_line")
            if snow and target and target >= snow:
                keys.append("planet_at_location:in_situ_beyond_snow")
            else:
                keys.append("planet_at_location:in_situ_inner")
            if res["layer2"].get("mechanism") == "mean_motion_resonance":
                keys.append("planet_at_location:resonant_migration")
    elif t == "trojan":
        keys.append("trojan:feasible" if v != "infeasible" else "trojan:infeasible")
    elif t == "moon":
        keys.append("moon:feasible" if v != "infeasible" else "moon:infeasible")
    elif t == "resonance":
        keys.append("resonance:feasible" if v == "feasible" else "resonance:infeasible")
    # Stretch system-shape rules (habitable_world / alt_solvent_world / architecture)
    # describe occupancy, not a single body's pathway → no origin narrative.
    return keys


def _origin_hypotheses(c, base, derived, res, priors=None):
    """Ranked, confidence-tagged origin hypotheses for an evaluated constraint.

    R3: an ingested ``ResearchPriors`` dataset (``priors.origin_priors``) overrides a
    context — those hypotheses carry ``priors.grounding``; an omitted context falls
    back to the DefaultPriors heuristic, tagged ``default-extrapolation`` even under
    strict (honest mixed tagging). ``priors=None`` → ``DefaultPriors`` (permissive,
    byte-identical to R2: empty ``origin_priors`` → every context uses the heuristic).
    """
    if priors is None:
        priors = DefaultPriors()
    origin_priors = getattr(priors, "origin_priors", None) or {}
    tag = _metallicity_tag(derived.get("feh"))          # R3-V2 B4
    hyps = []
    for key in _origin_context_keys(c, derived, res):
        # Prefer a metallicity-qualified variant "<key>:<tag>" when the dataset defines
        # one for this metal-rich/metal-poor host; else the base key; else the heuristic.
        qualified = f"{key}:{tag}" if tag else None
        source_key = qualified if (qualified and qualified in origin_priors) else key
        if source_key in origin_priors:
            for h in origin_priors[source_key]:
                hyps.append({"pathway": h["pathway"], "plausibility": h["plausibility"],
                             "grounding": priors.grounding})
        else:
            for pathway, plaus in _DEFAULT_ORIGIN.get(key, []):
                hyps.append({"pathway": pathway, "plausibility": plaus,
                             "grounding": "default-extrapolation"})
    return {"hypotheses": hyps, "grounding": priors.grounding}


def _resonant_au(a_neighbor, ratio_str, interior):
    """SMA that puts a body in the ``p:q`` MMR with a neighbour at ``a_neighbor``
    (``interior`` = the body orbits inside the neighbour)."""
    p, q = (int(x) for x in ratio_str.split(":"))     # p > q (outer/inner)
    factor = (q / p) ** (2.0 / 3.0) if interior else (p / q) ** (2.0 / 3.0)
    return a_neighbor * factor


def _short(r2):
    """A compact result phrase for a relaxed-constraint re-evaluation."""
    if r2["verdict"] == "feasible":
        s = "feasible"
    else:
        s = "marginally stable"
    if r2["layer2"].get("mechanism") == "mean_motion_resonance":
        s += " (resonant protection)"
    return s


def _first_improvement(rule, c, base, derived, patch_list, accept_marginal):
    """First patch in ``patch_list`` that re-evaluates to feasible (preferred) — or,
    when ``accept_marginal``, the first that reaches marginal. None if neither."""
    marginal = None
    for change, patch in patch_list:
        r2 = rule({**c, **patch}, base, derived)
        v = r2["verdict"]
        if v == "feasible":
            return {"change": change, "result": _short(r2), "spec_patch": patch}
        if accept_marginal and v == "marginal" and marginal is None:
            marginal = {"change": change, "result": _short(r2), "spec_patch": patch}
    return marginal


def _alt_planet(c, base, derived):
    planets = base["planets"]
    ptype = c.get("planet_type", "terrestrial")
    m = c.get("mass_earth") or _TYPE_MASS_EARTH.get(ptype, 1.0)
    target, inner, outer, err = _resolve_location(c.get("location") or {}, planets, derived)

    axes = []
    mass_patches = [(f"mass → {round(m * f, 4):g} M⊕", {"mass_earth": round(m * f, 4)})
                    for f in (0.5, 0.1)]
    mass_patches.append(("mass → 0.001 M⊕ (test particle)", {"mass_earth": 0.001}))
    axes.append(("mass", mass_patches))

    if (c.get("location") or {}).get("kind") != "in_hz":
        axes.append(("location", [("location → habitable zone", {"location": {"kind": "in_hz"}})]))

    if not err and target:
        nb = inner or outer
        if nb is not None and nb.get("a_au"):
            try:
                nm = nearest_mmr(period_ratio(target, nb["a_au"], derived["mass_solar"]))
            except Exception:
                nm = None
            if isinstance(nm, dict) and "error" not in nm:
                ratio = nm["ratio_str"]
                au = _resonant_au(nb["a_au"], ratio, interior=target < nb["a_au"])
                axes.append(("resonance",
                             [(f"lock into {ratio} MMR with {nb['name']} ({au:.3f} AU)",
                               {"location": {"kind": "at", "au": round(au, 5)}})]))
    return axes


def _alt_trojan(c, base, derived):
    planets = base["planets"]
    cur = _resolve_ref(c.get("host"), planets, derived)
    cur_name = cur["name"] if cur else None
    patches = [(f"host → {p['name']}", {"host": p["name"]})
               for p in sorted((p for p in planets if p.get("mass_earth")),
                               key=lambda p: p["mass_earth"])
               if p["name"] != cur_name]
    return [("host", patches)] if patches else []


def _alt_moon(c, base, derived):
    planets = base["planets"]
    cur = _resolve_ref(c.get("host"), planets, derived)
    cur_name = cur["name"] if cur else None
    axes = []
    if c.get("terraformable"):
        axes.append(("terraform", [("drop the terraformable requirement",
                                    {"terraformable": False})]))
    hosts = [(f"host → {p['name']}", {"host": p["name"]})
             for p in sorted((p for p in planets
                              if p.get("type") in ("gas", "super_jovian", "ice")
                              and p.get("mass_earth") and p.get("a_au")),
                             key=lambda p: -p["a_au"])
             if p["name"] != cur_name]
    if hosts:
        axes.append(("host", hosts))
    return axes


def _alt_resonance(c, base, derived):
    planets = base["planets"]
    bodies = c.get("bodies") or []
    if len(bodies) != 2:
        return []
    p1 = _resolve_ref(bodies[0], planets, derived)
    p2 = _resolve_ref(bodies[1], planets, derived)
    if not p1 or not p2 or not p1.get("a_au") or not p2.get("a_au"):
        return []
    nm = nearest_mmr(period_ratio(p1["a_au"], p2["a_au"], derived["mass_solar"]))
    if isinstance(nm, dict) and "error" not in nm:
        return [("ratio", [(f"ratio → {nm['ratio_str']} (their actual near-commensurability)",
                            {"ratio": nm["ratio_str"]})])]
    return []


def _alt_habitable(c, base, derived):
    axes = []
    if not (c.get("hz") or "cons").lower().startswith("opt"):
        axes.append(("hz", [("relax HZ → optimistic", {"hz": "opt"})]))
    axes.append(("count", [("require only 1 world", {"min_count": 1})]))
    return axes


_ALT_BUILDERS = {
    "planet_at_location": _alt_planet,
    "trojan": _alt_trojan,
    "moon": _alt_moon,
    "resonance": _alt_resonance,
    "habitable_world": _alt_habitable,
}


def _alternatives(c, base, derived, rule, original_verdict):
    """Deterministic Layer-4 relaxation scan → first improvement per axis (cap 3)."""
    builder = _ALT_BUILDERS.get(c.get("type"))
    if builder is None:
        return {"alternatives": []}
    accept_marginal = original_verdict == "infeasible"
    alts = []
    for _axis, patch_list in builder(c, base, derived):
        imp = _first_improvement(rule, c, base, derived, patch_list, accept_marginal)
        if imp:
            alts.append(imp)
        if len(alts) >= 3:
            break
    return {"alternatives": alts}


# ── R2-C3 · stretch-vocab rules (D1) ─────────────────────────────────────────

def _rule_habitable_world(c, base, derived):
    which = (c.get("hz") or "cons").lower()
    optimistic = which.startswith("opt")
    min_count = c.get("min_count", 1)
    if not isinstance(min_count, int) or min_count < 1:
        min_count = 1

    def _ok(p):
        if p.get("type") not in ("rocky", "super_earth"):
            return False
        return bool(p.get("in_hz")) if optimistic else (p.get("hz_class") == "conservative")

    hits = [p["name"] for p in base["planets"] if _ok(p)]
    band = "optimistic" if optimistic else "conservative"
    checked = ["habitable_zone_occupancy"]
    metrics = {"count": len(hits), "min_count": min_count, "hz": band, "worlds": hits}
    if len(hits) >= min_count:
        return _result(
            c, "feasible",
            {"stable": True,
             "reason": f"{len(hits)} rocky world(s) in the {band} HZ (need {min_count}): "
                       f"{', '.join(hits) or '—'}.",
             "metrics": metrics},
            {"mechanism": "habitable_zone_occupancy", "checked": checked, "note": None})
    return _result(
        c, "infeasible",
        {"stable": False,
         "reason": f"only {len(hits)} rocky world(s) in the {band} HZ; {min_count} required.",
         "metrics": metrics},
        {"mechanism": None, "checked": checked, "note": "insufficient HZ occupancy"})


def _rule_alt_solvent_world(c, base, derived):
    solvent = c.get("solvent")
    if not solvent:
        return _not_evaluated(c, "alt_solvent_world needs a 'solvent' name.")
    zone = compute_solvent_zone(derived["luminosity"], solvent=solvent)
    if "error" in zone:
        return _not_evaluated(c, zone["error"])
    inner, outer = zone["inner_au"], zone["outer_au"]
    in_band = [p["name"] for p in base["planets"]
               if p.get("a_au") and inner <= p["a_au"] <= outer
               and p.get("type") in ("rocky", "super_earth", "ice")]
    checked = ["solvent_liquid_band"]
    metrics = {"solvent": zone.get("name", solvent),
               "band_inner_au": round(inner, 4), "band_outer_au": round(outer, 4),
               "worlds": in_band}
    if in_band:
        return _result(
            c, "feasible",
            {"stable": True,
             "reason": f"{', '.join(in_band)} sit in the {zone.get('name', solvent)} liquid band "
                       f"({inner:.3f}–{outer:.3f} AU).",
             "metrics": metrics},
            {"mechanism": "solvent_liquid_band", "checked": checked, "note": None})
    center = 0.5 * (inner + outer)
    return _result(
        c, "infeasible",
        {"stable": False,
         "reason": f"no world sits in the {zone.get('name', solvent)} liquid band "
                   f"({inner:.3f}–{outer:.3f} AU); place one near {center:.3f} AU.",
         "metrics": metrics},
        {"mechanism": None, "checked": checked, "note": "no world in the solvent band"})


def _rule_architecture(c, base, derived):
    rule_name = (c.get("rule") or "").lower()
    planets = base["planets"]
    snow = derived.get("snow_line")
    giants = [p for p in planets if p.get("type") in ("gas", "super_jovian") and p.get("a_au")]
    checked = ["system_architecture"]

    if rule_name == "giant_beyond_snow_line":
        hits = [p["name"] for p in giants if snow and p["a_au"] >= snow]
        metrics = {"snow_line_au": snow, "giants_beyond": hits}
        if hits:
            return _result(c, "feasible",
                           {"stable": True, "reason": f"giant(s) beyond the snow line "
                            f"({snow:.2f} AU): {', '.join(hits)}.", "metrics": metrics},
                           {"mechanism": "system_architecture", "checked": checked, "note": None})
        return _result(c, "infeasible",
                       {"stable": False, "reason": f"no giant beyond the snow line "
                        f"({snow:.2f} AU).", "metrics": metrics},
                       {"mechanism": None, "checked": checked, "note": None})

    if rule_name == "no_hot_jupiter":
        hj = [p["name"] for p in giants if p["a_au"] < 0.1]
        metrics = {"hot_jupiters": hj}
        if hj:
            return _result(c, "infeasible",
                           {"stable": False, "reason": f"hot Jupiter(s) present: {', '.join(hj)}.",
                            "metrics": metrics},
                           {"mechanism": None, "checked": checked, "note": None})
        return _result(c, "feasible",
                       {"stable": True, "reason": "no hot Jupiter (no giant inside 0.1 AU).",
                        "metrics": metrics},
                       {"mechanism": "system_architecture", "checked": checked, "note": None})

    return _not_evaluated(c, f"unsupported architecture rule: {rule_name!r}")


_RULE_REGISTRY.update({
    "habitable_world": _rule_habitable_world,
    "alt_solvent_world": _rule_alt_solvent_world,
    "architecture": _rule_architecture,
})


# ── R2-C4 · optional N-body confirmation of a marginal packing verdict ───────

def _nbody_confirm(res, c, base, derived):
    """Run the bounded N-body screen on a *marginal* ``planet_at_location`` verdict
    (the packing gray band) and resolve it to feasible / infeasible. Only this
    constraint type is screened — its marginal verdict is exactly the multi-body
    packing question N-body answers; other rules' marginals are not packing-driven.
    Returns ``res`` unchanged for non-packing types or when there is nothing to
    integrate."""
    if c.get("type") != "planet_at_location":
        return res
    metrics = res["layer1"].get("metrics") or {}
    target = metrics.get("target_au")
    if target is None:
        return res
    mass = c.get("mass_earth") or _TYPE_MASS_EARTH.get(c.get("planet_type", "terrestrial"), 1.0)

    bodies = [{"mass_earth": p["mass_earth"], "a_au": p["a_au"]}
              for p in base["planets"] if p.get("mass_earth") and p.get("a_au")]
    bodies.append({"mass_earth": mass, "a_au": target})
    if len(bodies) < 2:
        return res

    from core.nbody import integrate_coplanar
    sim = integrate_coplanar(derived["mass_solar"], bodies)

    res = dict(res)
    l1 = dict(res["layer1"]); l1["metrics"] = dict(metrics)
    l2 = dict(res["layer2"])
    checked = list(l2.get("checked") or [])
    if "nbody" not in checked:
        checked.append("nbody")
    l2["checked"] = checked
    l1["metrics"]["nbody_orbits"] = sim["orbits_run"]

    if sim["survived"]:
        res["verdict"] = "feasible"
        l1["stable"] = True
        l1["reason"] = (l1.get("reason", "") + f" N-body screen: survived {sim['orbits_run']} "
                        "orbits of the innermost body (bounded short-integration screen, "
                        "not a Gyr stability proof).")
    else:
        res["verdict"] = "infeasible"
        l1["stable"] = False
        l1["reason"] = (l1.get("reason", "") + f" N-body screen: {sim['reason']} after "
                        f"{sim['orbits_run']} orbits.")
    res["layer1"] = l1
    res["layer2"] = l2
    return res
