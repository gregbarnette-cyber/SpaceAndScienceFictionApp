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
solve-force · distribute · layered-defense (WB MSG 027) · saturation-stream (sustained-stream /
saturation-over-dwell, Packet 38.2 CR-A). Leak is a cross-cutting modifier (any mode with L>0). No
network/DB/RNG/wall-clock/numpy. Companion weapon-physics: ``core.weapons``.
"""

import math

_C_MS = 299_792_458.0   # speed of light (m/s); local, to keep salvo dependency-free (cf. core/weapons.py)

MODES = ("simultaneous", "first-strike", "sequential-waves", "break-even", "solve-force",
         "distribute", "layered-defense", "saturation-stream")


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


def _mode_layered(rings_spec, inbound_salvo, inbound_from_alpha, scouting, target_staying,
                  delta_eff=None, ring_tau=None):
    """One inbound salvo cascaded through K defensive rings (chained-leaker, WB MSG 027). ``delta_eff``
    (CR-B light-lag) overrides each ring's alertness δ with its lag-decayed value; ``ring_tau`` echoes the
    per-ring one-way lag. Both default None → the pre-CR-B behavior is byte-identical."""
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
        d_use = delta_eff[j - 1] if delta_eff is not None else d
        survivors = max(incoming - d_use * b3, lk * incoming)
        entry = {
            "ring": j, "incoming": incoming, "delta": d_use, "b3": b3, "leak": lk,
            "defensive_power": d_use * b3,
            "destroyed": incoming - survivors, "leaked": survivors,
        }
        if ring_tau is not None:
            entry["tau_s"] = ring_tau[j - 1]
        ring_out.append(entry)
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


# ── CR-A: saturation-stream (sustained-stream / saturation-over-dwell) ─────────

def _parse_stream_rings(spec):
    """Parse ``"cap:regen:leak, …"`` → list of (cap, regen, leak) or a ``{"error"}`` dict.

    Distinct from ``_parse_rings`` (``δ:b₃:leak``): here ``cap`` = interceptors available per interval,
    ``regen`` = interceptor capacity regenerated per interval (``regen ≥ cap`` = full recovery — the
    reservoir is clamped at ``cap``; ``regen = 0`` = a one-shot magazine that depletes), ``leak`` = the
    fractional saturation floor L (0–1)."""
    rings = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        parts = tok.split(":")
        if len(parts) != 3:
            return {"error": f"Malformed --stream-rings token '{tok}' (expected 'cap:regen:leak')."}
        try:
            cap, regen, lk = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return {"error": f"Non-numeric --stream-rings token '{tok}'."}
        if cap < 0:
            return {"error": f"Ring interceptor cap must be ≥ 0 (got '{tok}')."}
        if regen < 0:
            return {"error": f"Ring regen must be ≥ 0 (got '{tok}')."}
        if not (0.0 <= lk <= 1.0):
            return {"error": f"Ring leak fraction must be in [0, 1] (got '{tok}')."}
        rings.append((cap, regen, lk))
    if not rings:
        return {"error": "--stream-rings is empty."}
    return rings


def _arrival_profile(total, n, profile):
    """Distribute ``total`` inbound missiles over ``n`` intervals per ``profile`` → a length-n list of
    fractional per-interval counts summing to ``total`` (no integer rounding), or a ``{"error"}`` dict.
    flat = T/N; ramp = linearly increasing (w_i = i); front-loaded = linearly decreasing (w_i = N+1−i)."""
    if profile == "flat":
        weights = [1.0] * n
    elif profile == "ramp":
        weights = [float(i) for i in range(1, n + 1)]
    elif profile == "front-loaded":
        weights = [float(n + 1 - i) for i in range(1, n + 1)]
    else:
        return {"error": f"--profile must be one of flat, front-loaded, ramp (got '{profile}')."}
    s = sum(weights)
    return [total * w / s for w in weights]


def _stream_cascade(arrivals, rings, sigma_pre=1.0):
    """The per-interval, per-ring reservoir cascade. ``arrivals`` = per-interval inbound counts; ``rings``
    = [(cap, regen, leak)]; ``sigma_pre`` multiplies each interval's arrivals (1.0 unless CR-B light-lag
    supplies a decayed scouting σ). Returns ``(per_interval_leak[], per_interval_ring_state[])``.

    Per ring, per interval (outermost→inner): ``intercepted = min(res, incoming − leak·incoming)``;
    ``survivors = incoming − intercepted``; then **fire-then-regen** ``res ← min(cap, res − intercepted +
    regen)``. Reservoirs carry across intervals."""
    res = [cap for (cap, regen, lk) in rings]      # reservoir per ring, init = cap
    per_interval_leak = []
    per_interval_ring_state = []
    for a in arrivals:
        incoming = sigma_pre * a
        state = []
        for j, (cap, regen, lk) in enumerate(rings):
            avail = res[j]
            floor = lk * incoming
            intercepted = min(avail, max(0.0, incoming - floor))
            survivors = incoming - intercepted
            res[j] = min(cap, avail - intercepted + regen)
            state.append({"ring": j + 1, "available": avail, "incoming": incoming,
                          "intercepted": intercepted, "leaked": survivors,
                          "reservoir_after": res[j]})
            incoming = survivors
        per_interval_leak.append(incoming)
        per_interval_ring_state.append(state)
    return per_interval_leak, per_interval_ring_state


def _single_pulse_cap_leak(total, rings, sigma_pre=1.0):
    """``equivalent_pulse_leak``: the whole stream total delivered as ONE pulse, cascaded through the same
    rings once with each reservoir at full ``cap`` (a single interception opportunity). Same cap-model as
    the stream — NOT a re-invocation of ``layered-defense``."""
    incoming = sigma_pre * total
    for (cap, regen, lk) in rings:
        floor = lk * incoming
        intercepted = min(cap, max(0.0, incoming - floor))
        incoming = incoming - intercepted
    return incoming


def _mode_saturation_stream(stream_rings, arrival_rate, stream_total, dwell_intervals, profile,
                            target_staying, sigma_pre=1.0):
    """Sustained-stream / saturation-over-dwell (CR-A): a missile stream over a dwell window scored against
    a per-interval-regenerating ring defense — the 'duration beats density' trade the single-pulse
    ``layered-defense`` snapshot can't score. ``sigma_pre`` comes from the CR-B light-lag preprocessor
    (1.0 = σ-free base)."""
    if stream_rings is None:
        return {"error": "saturation-stream needs --stream-rings 'cap:regen:leak, …'."}
    rings = _parse_stream_rings(stream_rings)
    if isinstance(rings, dict):
        return rings
    if dwell_intervals is None or dwell_intervals < 1 or int(dwell_intervals) != dwell_intervals:
        return {"error": "saturation-stream needs an integer --dwell-intervals ≥ 1."}
    n = int(dwell_intervals)
    have_rate = arrival_rate is not None
    have_total = stream_total is not None
    if have_rate and have_total:
        return {"error": "provide EITHER --arrival-rate OR --stream-total, not both."}
    if not have_rate and not have_total:
        return {"error": "saturation-stream needs --arrival-rate OR --stream-total (with --dwell-intervals)."}
    if have_rate:
        if arrival_rate < 0:
            return {"error": "--arrival-rate must be ≥ 0."}
        if profile != "flat":
            return {"error": "--arrival-rate implies a flat per-interval distribution; omit --profile "
                             "(or use --stream-total for a shaped stream)."}
        total = arrival_rate * n
        eff_profile = "flat"                       # a constant arrival rate is flat by construction (A6)
    else:
        if stream_total < 0:
            return {"error": "--stream-total must be ≥ 0."}
        total = stream_total
        eff_profile = profile
    arrivals = _arrival_profile(total, n, eff_profile)
    if isinstance(arrivals, dict):
        return arrivals
    if target_staying is not None and target_staying <= 0:
        return {"error": "--target-staying must be > 0."}

    per_interval_leak, per_interval_ring_state = _stream_cascade(arrivals, rings, sigma_pre)
    cumulative = sum(per_interval_leak)
    equivalent_pulse = _single_pulse_cap_leak(total, rings, sigma_pre)
    out = {
        "mode": "saturation-stream",
        "stream_total": total,
        "dwell_intervals": n,
        "profile": eff_profile,
        "arrivals_per_interval": arrivals,
        "n_rings": len(rings),
        "cumulative_leak": cumulative,
        "per_interval_leak": per_interval_leak,
        "per_interval_ring_state": per_interval_ring_state,
        "equivalent_pulse_leak": equivalent_pulse,
        "duration_advantage": equivalent_pulse - cumulative,
        "note": ("a stream of stream_total spread over dwell_intervals vs a per-interval-regenerating ring "
                 "defense; each ring holds a reservoir (init cap) firing up to cap/interval and "
                 "regenerating regen/interval (regen≥cap = full recovery, regen=0 = one-shot magazine). "
                 "duration_advantage = equivalent_pulse_leak − cumulative_leak (positive = the same total "
                 "as a single pulse leaks MORE — 'duration beats density', §4.4). Disjoint from "
                 "layered-defense (single-pulse snapshot) and sequential-waves (attacker-force depletion)."),
    }
    if target_staying is not None:
        out["target_staying"] = target_staying
        out["delta_target"] = cumulative / target_staying
    return out


# ── CR-B: light-lag σ/δ degradation (opt-in; default off → byte-identical) ─────

def _tau(range_m):
    """One-way light-lag τ = R/c (seconds)."""
    return range_m / _C_MS


def _decay(base, tau, law, scale, exponent, floor, agility, agility_ref):
    """Decayed σ or δ under one-way lag. Effective decay variable ``x_eff = τ·(agility/agility_ref)`` (B2);
    ``f = floor + (base − floor)·g(x_eff/scale)`` with g = linear / exp / power. ``scale→∞ ⇒ g→1 ⇒ f=base``
    (the degenerate/constant case). Caller guarantees ``floor ≤ base``, so ``f ∈ [floor, base] ⊆ [0, 1]``."""
    x = tau * (agility / agility_ref)
    r = x / scale
    if law == "linear":
        g = max(0.0, 1.0 - r)
    elif law == "exp":
        g = math.exp(-r)
    else:  # power
        g = (1.0 + r) ** (-exponent)
    return floor + (base - floor) * g


def _parse_ranges(spec, label):
    """Parse ``"R1,R2,…"`` (metres, outermost→inner) → list of floats > 0, or a ``{"error"}`` dict."""
    vals = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            return {"error": f"Non-numeric {label} value '{tok}'."}
        if v <= 0:
            return {"error": f"{label} values must be > 0 metres (got '{tok}')."}
        vals.append(v)
    if not vals:
        return {"error": f"{label} is empty."}
    return vals


def _floor_guard(floor, bases, msg):
    """CR-B: reject a σ/δ floor that exceeds its base — otherwise decay would make σ/δ *rise* with lag
    (R2-1). ``bases`` is the per-side or per-ring list of base values the floor must not exceed. Returns a
    ``{"error"}`` dict or None."""
    return {"error": msg} if any(floor > b for b in bases) else None


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
        rings=None, inbound_salvo=None, scouting=1.0, target_staying=None,
        arrival_rate=None, stream_total=None, dwell_intervals=None, profile="flat", stream_rings=None,
        light_lag=False, range_m=None, range_a_m=None, range_b_m=None, ring_ranges=None,
        target_agility=None, agility_ref=49.0, sigma_decay="exp", delta_decay="exp",
        decay_scale=1.0, decay_exponent=2.0, sigma_floor=0.0, delta_floor=0.0):
    """Hughes salvo exchange between forces A and B. See the module docstring / ``docs/integration.md``
    for the full contract. Returns a structured dict, or ``{"error": str}`` on any validation failure."""
    if mode not in MODES:
        return {"error": f"mode must be one of {', '.join(MODES)}."}

    def _cr_b_resolved():
        """The CR-B light-lag keys for resolved_inputs (echoed only when light_lag is on — §0.3 gating)."""
        return {
            "light_lag": light_lag, "range_m": range_m, "range_a_m": range_a_m, "range_b_m": range_b_m,
            "ring_ranges": ring_ranges, "target_agility": target_agility, "agility_ref": agility_ref,
            "sigma_decay": sigma_decay, "delta_decay": delta_decay, "decay_scale": decay_scale,
            "decay_exponent": decay_exponent, "sigma_floor": sigma_floor, "delta_floor": delta_floor,
        }

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

    # CR-B light-lag — common validation (mode rejection + decay-param ranges). Family-specific τ/decay
    # (per-side for force modes, per-ring δ for layered, σ pre-multiply for saturation) lives in each branch.
    ll_agility = None

    def _dec(base, tau, law, floor):
        """Decay one base σ/δ by lag τ under the run's validated light-lag params (closure over them, so the
        _decay contract is called from ONE place across the force / layered / saturation branches)."""
        return _decay(base, tau, law, decay_scale, decay_exponent, floor, ll_agility, agility_ref)

    if light_lag:
        if mode in ("break-even", "solve-force", "distribute"):
            return {"error": f"--light-lag is not supported for mode '{mode}' (valid on simultaneous, "
                             "first-strike, sequential-waves, layered-defense, saturation-stream)."}
        for nm, v in (("sigma-decay", sigma_decay), ("delta-decay", delta_decay)):
            if v not in ("linear", "exp", "power"):
                return {"error": f"--{nm} must be one of linear, exp, power."}
        if decay_scale is None or decay_scale <= 0:
            return {"error": "--decay-scale must be > 0 (seconds)."}
        if "power" in (sigma_decay, delta_decay) and (decay_exponent is None or decay_exponent <= 0):
            return {"error": "--decay-exponent must be > 0 (used by the 'power' decay law)."}
        for nm, v in (("sigma-floor", sigma_floor), ("delta-floor", delta_floor)):
            if v is None or not (0.0 <= v <= 1.0):
                return {"error": f"--{nm} must be in [0, 1]."}
        if agility_ref is None or agility_ref <= 0:
            return {"error": "--agility-ref must be > 0 (m/s²)."}
        ll_agility = agility_ref if target_agility is None else target_agility  # default = agility_ref (WB MSG 160)
        if ll_agility < 0:
            return {"error": "--target-agility must be ≥ 0 (m/s²)."}
    elif any(v is not None for v in (range_m, range_a_m, range_b_m, ring_ranges, target_agility)):
        return {"error": "light-lag inputs (--range-m/--range-a-m/--range-b-m/--ring-ranges/--target-agility) "
                         "require --light-lag on."}

    al = _resolve_striking(alpha, a_salvo, a_hitprob, "A")
    if isinstance(al, dict):
        return al
    be = _resolve_striking(beta, b_salvo, b_hitprob, "B")
    if isinstance(be, dict):
        return be

    # layered-defense is a defensive-cascade mode — it doesn't need the paired A/B coefficient set.
    if mode == "layered-defense":
        inbound_from_alpha = (al * a_force) if (al is not None and a_force is not None) else None
        delta_eff = ll_ring_tau = eng_tau = None
        scouting_used = scouting
        if light_lag:
            if range_m is None or range_m <= 0:
                return {"error": "--light-lag on layered-defense needs --range-m (engagement range, m)."}
            if rings is None:
                return {"error": "layered-defense needs --rings 'delta:b3:leak, …'."}
            parsed = _parse_rings(rings)
            if isinstance(parsed, dict):
                return parsed
            if ring_ranges is None:
                return {"error": "--light-lag on layered-defense needs --ring-ranges 'R1,R2,…' "
                                 "(m, outermost→inner) to decay per-ring δ."}
            rr = _parse_ranges(ring_ranges, "--ring-ranges")
            if isinstance(rr, dict):
                return rr
            if len(rr) != len(parsed):
                return {"error": f"--ring-ranges has {len(rr)} value(s) but --rings has {len(parsed)} ring(s)."}
            err = (_floor_guard(sigma_floor, [scouting], "--sigma-floor must be ≤ the base σ (--scouting).")
                   or _floor_guard(delta_floor, [d for (d, b3, lk) in parsed],
                                   "--delta-floor must be ≤ each ring's base δ."))
            if err:
                return err
            eng_tau = _tau(range_m)
            scouting_used = _dec(scouting, eng_tau, sigma_decay, sigma_floor)
            ll_ring_tau = [_tau(r) for r in rr]
            delta_eff = [_dec(d, ll_ring_tau[i], delta_decay, delta_floor)
                         for i, (d, b3, lk) in enumerate(parsed)]
        res = _mode_layered(rings, inbound_salvo, inbound_from_alpha, scouting_used, target_staying,
                            delta_eff=delta_eff, ring_tau=ll_ring_tau)
        if "error" in res:
            return res
        res["resolved_inputs"] = {
            "mode": mode, "rings": rings, "inbound_salvo": inbound_salvo, "scouting": scouting,
            "alpha": al, "a_force": a_force, "target_staying": target_staying,
        }
        if light_lag:
            res["sigma_effective"] = scouting_used          # σ is a single pre-multiply (B3)
            res["delta_effective"] = delta_eff              # δ decays per ring (B3)
            res["tau_s"] = ll_ring_tau
            res["light_travel_time_s"] = eng_tau            # engagement-range τ (R1-5)
            res["first_mover_advantage"] = None             # one-sided defensive-cascade mode
            res["resolved_inputs"].update(_cr_b_resolved())
        res["model_note"] = _MODEL_NOTE
        return res

    # saturation-stream is a defensive-scoring mode (CR-A) — like layered-defense it doesn't need the
    # paired A/B coefficient set; the stream is scored against its own cap:regen:leak rings.
    if mode == "saturation-stream":
        if scouting != 1.0:
            return {"error": "saturation-stream is σ-free — --scouting applies to layered-defense; "
                             "use --light-lag for σ degradation."}
        sigma_pre = 1.0
        eng_tau = ll_ring_tau = None
        if light_lag:
            if range_m is None or range_m <= 0:
                return {"error": "--light-lag on saturation-stream needs --range-m (engagement range, m)."}
            eng_tau = _tau(range_m)
            sigma_pre = _dec(1.0, eng_tau, sigma_decay, sigma_floor)
        res = _mode_saturation_stream(stream_rings, arrival_rate, stream_total, dwell_intervals,
                                      profile, target_staying, sigma_pre=sigma_pre)
        if "error" in res:
            return res
        if light_lag and ring_ranges is not None:           # optional per-ring τ echo (no δ to decay here)
            rr = _parse_ranges(ring_ranges, "--ring-ranges")
            if isinstance(rr, dict):
                return rr
            if len(rr) != res["n_rings"]:                   # ring count from the mode's own parse (no re-parse)
                return {"error": f"--ring-ranges has {len(rr)} value(s) but --stream-rings has "
                                 f"{res['n_rings']} ring(s)."}
            ll_ring_tau = [_tau(r) for r in rr]
        res["resolved_inputs"] = {
            "mode": mode, "stream_rings": stream_rings, "arrival_rate": arrival_rate,
            "stream_total": stream_total, "dwell_intervals": dwell_intervals,
            "profile": res["profile"], "target_staying": target_staying,   # effective profile (A6)
        }
        if light_lag:
            res["sigma_effective"] = sigma_pre              # σ pre-multiply (σ₀ = 1.0)
            res["delta_effective"] = None                   # cap:regen:leak rings carry no δ (WB MSG 160)
            res["tau_s"] = ll_ring_tau                       # per-ring τ echo (None if --ring-ranges omitted)
            res["light_travel_time_s"] = eng_tau
            res["first_mover_advantage"] = None              # one-sided mode
            res["resolved_inputs"].update(_cr_b_resolved())
        res["model_note"] = _MODEL_NOTE
        return res

    # All other modes: build the A/B coefficient bundles (staying required — it divides).
    if a1_staying is None or b1_staying is None:
        return {"error": "staying power is required: --a1-staying and --b1-staying (> 0)."}
    a3 = 0.0 if a3_defense is None else float(a3_defense)
    b3 = 0.0 if b3_defense is None else float(b3_defense)

    # CR-B light-lag for the force-on-force modes (simultaneous / first-strike / sequential-waves): decay
    # each side's σ,δ by that side's engagement τ (per-side range overrides the shared --range-m). The
    # decayed values feed the bundles; resolved_inputs still echoes the user-supplied (undecayed) σ,δ.
    sig_a, sig_b, del_a, del_b = sigma_a, sigma_b, delta_a, delta_b
    ll_block = None
    ll_tau_a = ll_tau_b = None
    if light_lag:
        ra = range_a_m if range_a_m is not None else range_m
        rb = range_b_m if range_b_m is not None else range_m
        if ra is None or rb is None:
            return {"error": "--light-lag needs an engagement range: --range-m (shared) or "
                             "--range-a-m/--range-b-m (per side)."}
        if ra <= 0 or rb <= 0:
            return {"error": "engagement range must be > 0 (m)."}
        err = (_floor_guard(sigma_floor, [sigma_a, sigma_b], "--sigma-floor must be ≤ the base σ (sigma_a/sigma_b).")
               or _floor_guard(delta_floor, [delta_a, delta_b], "--delta-floor must be ≤ the base δ (delta_a/delta_b)."))
        if err:
            return err
        ll_tau_a, ll_tau_b = _tau(ra), _tau(rb)
        sig_a = _dec(sigma_a, ll_tau_a, sigma_decay, sigma_floor)
        sig_b = _dec(sigma_b, ll_tau_b, sigma_decay, sigma_floor)
        del_a = _dec(delta_a, ll_tau_a, delta_decay, delta_floor)
        del_b = _dec(delta_b, ll_tau_b, delta_decay, delta_floor)
        ll_block = {
            "sigma_effective": {"a": sig_a, "b": sig_b},
            "delta_effective": {"a": del_a, "b": del_b},
            "tau_s": {"a": ll_tau_a, "b": ll_tau_b},
            # engagement-lag scalar: the shared --range-m τ, else the max per-side τ (never null when tau_s is set)
            "light_travel_time_s": (_tau(range_m) if range_m is not None else max(ll_tau_a, ll_tau_b)),
            "first_mover_advantage": None,      # filled after dispatch (needs Δ_a/Δ_b)
        }
    A = {"force": a_force, "alpha": al, "defense": a3, "staying": a1_staying,
         "sigma": sig_a, "delta": del_a, "leak": leak_a}
    B = {"force": b_force, "alpha": be, "defense": b3, "staying": b1_staying,
         "sigma": sig_b, "delta": del_b, "leak": leak_b}

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

    # CR-B: first-mover advantage (force modes) — Δ_second − Δ_first, "first" = shorter-effective-τ side;
    # null under symmetric τ (B5 / R1-1: gated on τ symmetry, NOT Δ-equality). Attach the light-lag block.
    if ll_block is not None:
        da_r, db_r = res.get("delta_a"), res.get("delta_b")
        if (ll_tau_a is None or ll_tau_b is None or abs(ll_tau_a - ll_tau_b) < 1e-12
                or da_r is None or db_r is None):
            ll_block["first_mover_advantage"] = None                 # symmetric τ ⇒ no first mover
        elif ll_tau_a < ll_tau_b:                                    # A first (shorter τ), B second
            ll_block["first_mover_advantage"] = db_r - da_r
        else:                                                        # B first (shorter τ), A second
            ll_block["first_mover_advantage"] = da_r - db_r
        res.update(ll_block)

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
    if light_lag:
        res["resolved_inputs"].update(_cr_b_resolved())
    res["model_note"] = _MODEL_NOTE
    return res


_MODEL_NOTE = (
    "Hughes Ch. 13 salvo model. ΔB = clamp(max(σ_A·α·A − δ_B·b₃·B, L_A·σ_A·α·A)/b₁, 0, B) and the "
    "mirror for ΔA. Striking α/β and defence a₃/b₃ are PER UNIT (aggregate = ×force); staying a₁/b₁ "
    "is hits-to-OOA. σ scouting, δ alertness, L leaker floor (perfect-until-saturated). Losses may be "
    "fractional (aggregated task elements). Reconstructed equations validated against Ch. 13 worked "
    "results; the setting-facing doctrine translation is a separate Packet 38.2 job.")
