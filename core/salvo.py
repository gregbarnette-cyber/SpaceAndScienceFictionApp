"""Phase AT (Packet 38.1) — the Hughes salvo model of missile combat (W1).

A ``query.py``-only, pure-math, self-validating (Phase-H/P contract: curated ``{"error"}`` → exit 1,
argparse → exit 2) discrete-pulse force-on-force exchange between two combatant forces A and B, from
Wayne P. Hughes Jr., *Fleet Tactics*, Ch. 13. The reconstructed equations are validated against the
Ch. 13 worked results (pixel-confirm of the source equation images is a WB CP2 job — see
``PHASE_AT_PLAN.md``).

Base engine (per-unit striking α/β, defence a₃/b₃, staying a₁/b₁; scouting σ, alertness δ, leak L):

    ΔB = clamp( max(σ_A·α·A − δ_B·b₃·B ,  L_A·σ_A·α·A) / b₁ ,  0, B )
    ΔA = clamp( max(σ_B·β·B − δ_A·a₃·A ,  L_B·σ_B·β·B) / a₁ ,  0, A )

Modes: simultaneous · first-strike · sequential-waves (two-sided, WB MSG 025) · break-even ·
solve-force · distribute · layered-defense (WB MSG 027). Leak is a cross-cutting modifier (any mode
with L>0). No network/DB/RNG/wall-clock/numpy. Companion weapon-physics: ``core.weapons``.
"""

import math

MODES = ("simultaneous", "first-strike", "sequential-waves", "break-even", "solve-force",
         "distribute", "layered-defense")


# ── striking-power resolution + the base one-sided salvo ──────────────────────

def _resolve_striking(direct, salvo, hitprob, label):
    """→ per-unit striking power (α or β), or a ``{"error"}`` dict. Either --…-striking directly or
    --…-salvo × --…-hitprob (H)."""
    have_direct = direct is not None
    have_pair = salvo is not None or hitprob is not None
    if have_direct and have_pair:
        return {"error": f"Side {label}: provide EITHER striking power directly OR salvo+hitprob, not both."}
    if have_pair:
        if salvo is None or hitprob is None:
            return {"error": f"Side {label}: salvo form needs BOTH the salvo size and the hit probability H."}
        if salvo < 0:
            return {"error": f"Side {label}: salvo size must be ≥ 0."}
        if not (0.0 <= hitprob <= 1.0):
            return {"error": f"Side {label}: hit probability H must be in [0, 1]."}
        return salvo * hitprob
    if have_direct:
        if direct < 0:
            return {"error": f"Side {label}: striking power must be ≥ 0."}
        return float(direct)
    return None


def _one_side(atk_force, atk_alpha, atk_sigma, atk_leak, def_force, def_defense, def_delta, def_staying):
    """Effect of one force's salvo on the other. Returns the clamped Δ + diagnostics."""
    raw = atk_sigma * atk_alpha * atk_force - def_delta * def_defense * def_force
    floor = atk_leak * atk_sigma * atk_alpha * atk_force
    eff = max(raw, floor)
    unclamped = eff / def_staying
    delta = min(max(unclamped, 0.0), def_force)
    return {
        "delta": delta,
        "delta_unclamped": unclamped,
        "overkill": max(0.0, unclamped - def_force),
        "raw_hits": raw,
        "effective_hits": eff,
        "leak_floor": floor,
    }


def _frac(delta, force):
    return (delta / force) if force > 0 else None


# ── the seven modes ───────────────────────────────────────────────────────────

def _mode_simultaneous(A, B):
    """Both salvos resolve against pre-salvo forces (the base case)."""
    rb = _one_side(A["force"], A["alpha"], A["sigma"], A["leak"], B["force"], B["defense"], B["delta"], B["staying"])
    ra = _one_side(B["force"], B["alpha"], B["sigma"], B["leak"], A["force"], A["defense"], A["delta"], A["staying"])
    da, db = ra["delta"], rb["delta"]
    return {
        "mode": "simultaneous",
        "delta_a": da, "delta_b": db,
        "frac_loss_a": _frac(da, A["force"]), "frac_loss_b": _frac(db, B["force"]),
        "overkill_a": ra["overkill"], "overkill_b": rb["overkill"],
        "survivors_a": A["force"] - da, "survivors_b": B["force"] - db,
        "exchange_ratio": (db / da) if da > 0 else None,
        "exchange_ratio_note": None if da > 0 else "ΔA = 0 — exchange ratio undefined (A took no losses).",
    }


def _mode_first_strike(A, B, first):
    """One side strikes; the loser's survivors return fire (aggregate striking scales with survivors)."""
    if first not in ("a", "b"):
        return {"error": "first-strike mode needs --first {a,b}."}
    atk, dfn = (A, B) if first == "a" else (B, A)
    p1 = _one_side(atk["force"], atk["alpha"], atk["sigma"], atk["leak"],
                   dfn["force"], dfn["defense"], dfn["delta"], dfn["staying"])
    dfn_surv = dfn["force"] - p1["delta"]
    p2 = _one_side(dfn_surv, dfn["alpha"], dfn["sigma"], dfn["leak"],
                   atk["force"], atk["defense"], atk["delta"], atk["staying"])
    atk_surv = atk["force"] - p2["delta"]
    # map attacker/defender back to A/B
    if first == "a":
        da, db = p2["delta"], p1["delta"]
        fa, fb = atk_surv, dfn_surv
        ova, ovb = p2["overkill"], p1["overkill"]
    else:
        da, db = p1["delta"], p2["delta"]
        fa, fb = dfn_surv, atk_surv
        ova, ovb = p1["overkill"], p2["overkill"]
    return {
        "mode": "first-strike",
        "first": first,
        "pulses": [
            {"pulse": 1, "attacker": first, "delta_defender": p1["delta"], "overkill": p1["overkill"]},
            {"pulse": 2, "attacker": ("b" if first == "a" else "a"),
             "delta_defender": p2["delta"], "overkill": p2["overkill"],
             "returning_force": dfn_surv},
        ],
        "delta_a": da, "delta_b": db,
        "frac_loss_a": _frac(da, A["force"]), "frac_loss_b": _frac(db, B["force"]),
        "overkill_a": ova, "overkill_b": ovb,
        "final_survivors_a": fa, "final_survivors_b": fb,
    }


def _mode_sequential(A, B, first, wave_size, n_waves, defender_magazine, defender_preempts):
    """Two-sided wave attack (WB MSG 025 + 029): each wave is a SIMULTANEOUS base-engine exchange
    between the wave and the current defender — the wave's FULL already-launched salvo hits the
    defender, reduced only by the defender's DEFENCE a₃ (not suppressed by the defender's offence),
    while the defender's offence kills wave ships. PD (defence) reloads every wave; the defender's
    offensive magazine optionally depletes; defender staying-power hits accumulate. `defender_preempts`
    (the out-ranging case) instead lets only the wave's OFFENCE-survivors deliver."""
    if wave_size is None or wave_size <= 0:
        return {"error": "sequential-waves needs --wave-size > 0."}
    if n_waves is None or n_waves < 1 or int(n_waves) != n_waves:
        return {"error": "sequential-waves needs an integer --n-waves ≥ 1."}
    if defender_magazine is not None and (defender_magazine < 0 or int(defender_magazine) != defender_magazine):
        return {"error": "--defender-magazine must be an integer ≥ 0 (omit for unlimited/reloading)."}
    atk, dfn = (A, B) if first in (None, "a") else (B, A)

    pool = atk["force"]
    dfn_force = dfn["force"]
    magazine = defender_magazine
    waves = []
    atk_lost_total = 0.0
    dfn_delta_total = 0.0
    for i in range(1, int(n_waves) + 1):
        if pool <= 1e-12:
            break
        this_wave = min(wave_size, pool)
        pool -= this_wave
        # defender fires offensively at the incoming wave (magazine-limited)
        if magazine is None or magazine > 0:
            wr = _one_side(dfn_force, dfn["alpha"], dfn["sigma"], dfn["leak"],
                           this_wave, atk["defense"], atk["delta"], atk["staying"])
            wave_delta = wr["delta"]
            wave_overkill = wr["overkill"]
            fired = True
            if magazine is not None:
                magazine -= 1
        else:
            wave_delta = 0.0
            wave_overkill = 0.0
            fired = False
        survivors_wave = this_wave - wave_delta
        atk_lost_total += wave_delta
        # Wave salvo on the defender — SIMULTANEOUS by default (WB MSG 029): the FULL wave's
        # already-launched salvo hits, reduced only by the defender's DEFENCE a₃, against the
        # pre-wave defender force. --defender-preempts (out-ranging) lets only the offence-survivors
        # deliver. The wave always strikes even when the defender's offensive magazine is dry
        # (defence via a₃ still works — the shot-your-bolt dynamic). Defence reloads each wave.
        strike_force = survivors_wave if defender_preempts else this_wave
        if strike_force > 1e-12:
            sr = _one_side(strike_force, atk["alpha"], atk["sigma"], atk["leak"],
                           dfn_force, dfn["defense"], dfn["delta"], dfn["staying"])
            dfn_delta = sr["delta"]
            dfn_overkill = sr["overkill"]
        else:
            dfn_delta = 0.0
            dfn_overkill = 0.0
        dfn_force -= dfn_delta
        dfn_delta_total += dfn_delta
        waves.append({
            "wave": i, "committed": this_wave, "wave_losses": wave_delta,
            "wave_overkill": wave_overkill, "survivors": survivors_wave,
            "defender_delta": dfn_delta, "defender_overkill": dfn_overkill,
            "defender_remaining": dfn_force, "defender_fired": fired,
            "magazine_remaining": magazine,
        })
    atk_survivors = atk["force"] - atk_lost_total
    result = {
        "mode": "sequential-waves",
        "attacker": "a" if first in (None, "a") else "b",
        "defender_preempts": defender_preempts,
        "waves": waves,
        "waves_resolved": len(waves),
        "attacker_committed": atk["force"] - pool,
        "attacker_uncommitted": pool,
    }
    # map attacker/defender totals back to A/B
    if first in (None, "a"):
        result.update({
            "delta_a": atk_lost_total, "delta_b": dfn_delta_total,
            "final_survivors_a": atk_survivors, "final_survivors_b": dfn_force,
            "frac_loss_a": _frac(atk_lost_total, A["force"]), "frac_loss_b": _frac(dfn_delta_total, B["force"]),
        })
    else:
        result.update({
            "delta_a": dfn_delta_total, "delta_b": atk_lost_total,
            "final_survivors_a": dfn_force, "final_survivors_b": atk_survivors,
            "frac_loss_a": _frac(dfn_delta_total, A["force"]), "frac_loss_b": _frac(atk_lost_total, B["force"]),
        })
    return result


def _mode_break_even(A, B):
    """Force-count ratio B:A giving equal fractional loss under unequal per-unit quality."""
    if A["alpha"] <= 0 or B["alpha"] <= 0:
        return {"error": "break-even needs both striking powers > 0."}
    # b₁·β·r² + (a₁·b₃ − b₁·a₃)·r − a₁·α = 0,  r = B/A (A the reference).
    qa = B["staying"] * B["alpha"]
    qb = A["staying"] * B["defense"] - B["staying"] * A["defense"]
    qc = -A["staying"] * A["alpha"]
    disc = qb * qb - 4.0 * qa * qc
    if disc < 0 or qa == 0:
        return {"error": "break-even has no positive real force ratio for these coefficients."}
    r = (-qb + math.sqrt(disc)) / (2.0 * qa)
    if r <= 0:
        return {"error": "break-even force ratio is non-positive for these coefficients."}
    return {
        "mode": "break-even",
        "break_even_force_ratio": r,
        "governing_note": ("B:A count ratio for parity in fractional losses. The more numerous side's "
                           "numerical advantage must be matched by the product of the other side's "
                           "per-unit striking × defensive × staying advantages (Hughes' "
                           "numerical-superiority theorem: n× the numbers ⇒ each unit needs n× α, a₃, a₁)."),
    }


def _mode_solve_force(A, B, solve_for, target_delta, target_frac_loss, target_side):
    """Invert for the force size achieving a target loss (absolute Δ or fractional) on a side."""
    if solve_for not in ("a", "b"):
        return {"error": "solve-force needs --solve-for {a,b}."}
    if (target_delta is None) == (target_frac_loss is None):
        return {"error": "solve-force needs exactly one of --target-delta or --target-frac-loss."}
    if target_frac_loss is not None and not (0.0 <= target_frac_loss <= 1.0):
        return {"error": "--target-frac-loss must be in [0, 1]."}
    if target_delta is not None and target_delta < 0:
        return {"error": "--target-delta must be ≥ 0."}
    # default target side: opposite of solve_for for absolute Δ; the solved side for fractional.
    if target_side is None:
        target_side = ("a" if solve_for == "b" else "b") if target_delta is not None else solve_for
    if target_side not in ("a", "b"):
        return {"error": "--target-side must be {a,b}."}

    # Δ_target = c_A·A + c_B·B (linear in both forces).
    if target_side == "b":
        if A["alpha"] is None or A["alpha"] <= 0:
            return {"error": "solve-force targeting ΔB needs A's striking power α > 0."}
        cA = A["sigma"] * A["alpha"] / B["staying"]
        cB = -B["delta"] * B["defense"] / B["staying"]
    else:
        if B["alpha"] is None or B["alpha"] <= 0:
            return {"error": "solve-force targeting ΔA needs B's striking power β > 0."}
        cA = -A["delta"] * A["defense"] / A["staying"]
        cB = B["sigma"] * B["alpha"] / A["staying"]
    # RHS = rConst + rA·A + rB·B.
    if target_delta is not None:
        rConst, rA, rB = float(target_delta), 0.0, 0.0
    else:
        rConst = 0.0
        rA = target_frac_loss if target_side == "a" else 0.0
        rB = target_frac_loss if target_side == "b" else 0.0
    dA, dB = cA - rA, cB - rB     # dA·A + dB·B = rConst

    if solve_for == "b":
        known = A["force"]
        if known is None or known <= 0:
            return {"error": "solve-force for B needs A's force size (--a-force > 0)."}
        if abs(dB) < 1e-15:
            return {"error": "solve-force: the target is independent of B's force (no solution)."}
        req = (rConst - dA * known) / dB
    else:
        known = B["force"]
        if known is None or known <= 0:
            return {"error": "solve-force for A needs B's force size (--b-force > 0)."}
        if abs(dA) < 1e-15:
            return {"error": "solve-force: the target is independent of A's force (no solution)."}
        req = (rConst - dB * known) / dA
    if req <= 0:
        return {"error": "no positive force achieves the target loss with these coefficients."}
    return {
        "mode": "solve-force",
        "solve_for": solve_for,
        "target_side": target_side,
        "target_delta": target_delta,
        "target_frac_loss": target_frac_loss,
        "required_force_exact": req,
        "integer_wave": int(math.ceil(req - 1e-12)),
        "note": ("inverts the un-clamped base striking term for the force achieving the target loss; "
                 "leaker floor and force clamps are not applied to the solve."),
    }


def _mode_distribute(A, B, first, fire_fraction):
    """Concentration of fire: the attacker's whole salvo onto a fraction f of the enemy (subset defends)."""
    if fire_fraction is None or not (0.0 < fire_fraction <= 1.0):
        return {"error": "distribute needs --fire-fraction in (0, 1]."}
    atk, dfn = (A, B) if first in (None, "a") else (B, A)
    targeted = fire_fraction * dfn["force"]
    r = _one_side(atk["force"], atk["alpha"], atk["sigma"], atk["leak"],
                  targeted, dfn["defense"], dfn["delta"], dfn["staying"])
    out = {
        "mode": "distribute",
        "attacker": "a" if first in (None, "a") else "b",
        "fire_fraction": fire_fraction,
        "targeted_count": targeted,
        "delta_targeted": r["delta"],
        "overkill_targeted": r["overkill"],
        "frac_loss_targeted": _frac(r["delta"], targeted),
        "survivors_targeted": targeted - r["delta"],
        "note": ("attacker concentrates its whole salvo on f·force of the enemy; only the targeted "
                 "subset's defence resists (no mutual support — WB MSG 025 ruling A)."),
    }
    if first in (None, "a"):
        out["delta_b"] = r["delta"]
    else:
        out["delta_a"] = r["delta"]
    return out


def _parse_rings(spec):
    """Parse ``"δ:b₃:leak, …"`` → list of (delta, b3, leak) or a ``{"error"}`` dict."""
    rings = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        parts = tok.split(":")
        if len(parts) != 3:
            return {"error": f"Malformed --rings token '{tok}' (expected 'delta:b3:leak')."}
        try:
            d, b3, lk = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return {"error": f"Non-numeric --rings token '{tok}'."}
        if not (0.0 <= d <= 1.0):
            return {"error": f"Ring alertness δ must be in [0, 1] (got '{tok}')."}
        if b3 < 0:
            return {"error": f"Ring defensive power b₃ must be ≥ 0 (got '{tok}')."}
        if not (0.0 <= lk <= 1.0):
            return {"error": f"Ring leak fraction must be in [0, 1] (got '{tok}')."}
        rings.append((d, b3, lk))
    if not rings:
        return {"error": "--rings is empty."}
    return rings


def _mode_layered(rings_spec, inbound_salvo, inbound_from_alpha, scouting, target_staying):
    """One inbound salvo cascaded through K defensive rings (chained-leaker, WB MSG 027)."""
    if rings_spec is None:
        return {"error": "layered-defense needs --rings 'delta:b3:leak, …'."}
    rings = _parse_rings(rings_spec)
    if isinstance(rings, dict):
        return rings
    if inbound_salvo is not None and inbound_from_alpha is not None:
        return {"error": "Provide the inbound salvo EITHER as --inbound-salvo OR via --alpha + --a-force, not both."}
    if inbound_salvo is not None:
        base = inbound_salvo
    elif inbound_from_alpha is not None:
        base = inbound_from_alpha
    else:
        return {"error": "layered-defense needs the inbound salvo: --inbound-salvo N, or --alpha + --a-force."}
    if base < 0:
        return {"error": "inbound salvo must be ≥ 0."}
    if scouting is None or not (0.0 <= scouting <= 1.0):
        return {"error": "--scouting σ must be in [0, 1]."}
    if target_staying is not None and target_staying <= 0:
        return {"error": "--target-staying must be > 0."}

    incoming = scouting * base
    ring_out = []
    for j, (d, b3, lk) in enumerate(rings, start=1):
        survivors = max(incoming - d * b3, lk * incoming)
        ring_out.append({
            "ring": j, "incoming": incoming, "delta": d, "b3": b3, "leak": lk,
            "defensive_power": d * b3,
            "destroyed": incoming - survivors, "leaked": survivors,
        })
        incoming = survivors
    out = {
        "mode": "layered-defense",
        "inbound_salvo_effective": scouting * base,
        "scouting": scouting,
        "n_rings": len(rings),
        "rings": ring_out,
        "survivors_to_target": incoming,
        "note": ("one inbound salvo cascaded outermost→inner; per ring "
                 "survivors = max(incoming − δ·b₃, L·incoming) (Hughes 'Massing for Defense' — "
                 "perfect until saturated, but at least L always leaks). Disjoint from "
                 "sequential-waves (two-sided attacker-waves)."),
    }
    if target_staying is not None:
        out["target_staying"] = target_staying
        out["delta_target"] = incoming / target_staying
    return out


# ── public entry point ────────────────────────────────────────────────────────

def compute_salvo_exchange(
        a_force=None, b_force=None,
        alpha=None, beta=None, a_salvo=None, b_salvo=None, a_hitprob=None, b_hitprob=None,
        a1_staying=None, b1_staying=None, a3_defense=None, b3_defense=None,
        sigma_a=1.0, sigma_b=1.0, delta_a=1.0, delta_b=1.0, leak_a=0.0, leak_b=0.0,
        mode="simultaneous", first=None, wave_size=None, n_waves=None, defender_magazine=None,
        defender_preempts=False,
        target_delta=None, target_frac_loss=None, solve_for=None, target_side=None,
        fire_fraction=None,
        rings=None, inbound_salvo=None, scouting=1.0, target_staying=None):
    """Hughes salvo exchange between forces A and B. See the module docstring / ``docs/integration.md``
    for the full contract. Returns a structured dict, or ``{"error": str}`` on any validation failure."""
    if mode not in MODES:
        return {"error": f"mode must be one of {', '.join(MODES)}."}

    # Range checks on the always-optional modifiers.
    for name, v in (("sigma_a", sigma_a), ("sigma_b", sigma_b), ("delta_a", delta_a),
                    ("delta_b", delta_b), ("leak_a", leak_a), ("leak_b", leak_b)):
        if v is None or not (0.0 <= v <= 1.0):
            return {"error": f"{name} must be in [0, 1]."}
    for name, v in (("a1_staying", a1_staying), ("b1_staying", b1_staying)):
        if v is not None and v <= 0:
            return {"error": f"{name} (staying power) must be > 0."}
    for name, v in (("a3_defense", a3_defense), ("b3_defense", b3_defense)):
        if v is not None and v < 0:
            return {"error": f"{name} (defensive power) must be ≥ 0."}
    for name, v in (("a_force", a_force), ("b_force", b_force)):
        if v is not None and v < 0:
            return {"error": f"{name} must be ≥ 0."}

    al = _resolve_striking(alpha, a_salvo, a_hitprob, "A")
    if isinstance(al, dict):
        return al
    be = _resolve_striking(beta, b_salvo, b_hitprob, "B")
    if isinstance(be, dict):
        return be

    # layered-defense is a defensive-cascade mode — it doesn't need the paired A/B coefficient set.
    if mode == "layered-defense":
        inbound_from_alpha = (al * a_force) if (al is not None and a_force is not None) else None
        res = _mode_layered(rings, inbound_salvo, inbound_from_alpha, scouting, target_staying)
        if "error" in res:
            return res
        res["resolved_inputs"] = {
            "mode": mode, "rings": rings, "inbound_salvo": inbound_salvo, "scouting": scouting,
            "alpha": al, "a_force": a_force, "target_staying": target_staying,
        }
        res["model_note"] = _MODEL_NOTE
        return res

    # All other modes: build the A/B coefficient bundles (staying required — it divides).
    if a1_staying is None or b1_staying is None:
        return {"error": "staying power is required: --a1-staying and --b1-staying (> 0)."}
    a3 = 0.0 if a3_defense is None else float(a3_defense)
    b3 = 0.0 if b3_defense is None else float(b3_defense)
    A = {"force": a_force, "alpha": al, "defense": a3, "staying": a1_staying,
         "sigma": sigma_a, "delta": delta_a, "leak": leak_a}
    B = {"force": b_force, "alpha": be, "defense": b3, "staying": b1_staying,
         "sigma": sigma_b, "delta": delta_b, "leak": leak_b}

    # Force + striking presence checks for the force-on-force modes.
    if mode in ("simultaneous", "first-strike", "sequential-waves", "distribute"):
        if a_force is None or b_force is None:
            return {"error": f"mode '{mode}' needs both --a-force and --b-force."}
    if mode in ("simultaneous", "first-strike", "sequential-waves", "break-even"):
        if al is None or be is None:
            return {"error": f"mode '{mode}' needs both striking powers (--alpha/--beta or the salvo forms)."}

    if mode == "simultaneous":
        res = _mode_simultaneous(A, B)
    elif mode == "first-strike":
        res = _mode_first_strike(A, B, first)
    elif mode == "sequential-waves":
        res = _mode_sequential(A, B, first, wave_size, n_waves, defender_magazine, defender_preempts)
    elif mode == "break-even":
        res = _mode_break_even(A, B)
    elif mode == "solve-force":
        res = _mode_solve_force(A, B, solve_for, target_delta, target_frac_loss, target_side)
    else:  # distribute
        if al is None and first in (None, "a"):
            return {"error": "distribute (attacker A) needs A's striking power (--alpha or the salvo form)."}
        if be is None and first == "b":
            return {"error": "distribute (attacker B) needs B's striking power (--beta or the salvo form)."}
        res = _mode_distribute(A, B, first, fire_fraction)
    if "error" in res:
        return res

    res["resolved_inputs"] = {
        "mode": mode, "a_force": a_force, "b_force": b_force, "alpha": al, "beta": be,
        "a1_staying": a1_staying, "b1_staying": b1_staying, "a3_defense": a3, "b3_defense": b3,
        "sigma_a": sigma_a, "sigma_b": sigma_b, "delta_a": delta_a, "delta_b": delta_b,
        "leak_a": leak_a, "leak_b": leak_b, "first": first, "wave_size": wave_size,
        "n_waves": n_waves, "defender_magazine": defender_magazine,
        "defender_preempts": defender_preempts, "fire_fraction": fire_fraction,
        "solve_for": solve_for, "target_delta": target_delta, "target_frac_loss": target_frac_loss,
        "target_side": target_side,
    }
    res["model_note"] = _MODEL_NOTE
    return res


_MODEL_NOTE = (
    "Hughes Ch. 13 salvo model. ΔB = clamp(max(σ_A·α·A − δ_B·b₃·B, L_A·σ_A·α·A)/b₁, 0, B) and the "
    "mirror for ΔA. Striking α/β and defence a₃/b₃ are PER UNIT (aggregate = ×force); staying a₁/b₁ "
    "is hits-to-OOA. σ scouting, δ alertness, L leaker floor (perfect-until-saturated). Losses may be "
    "fractional (aggregated task elements). Reconstructed equations validated against Ch. 13 worked "
    "results; the setting-facing doctrine translation is a separate Packet 38.2 job.")
