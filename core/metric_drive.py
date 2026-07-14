"""Phase AK (Group Q) — metric-drive power / fuel calculator (Packet 25).

One ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculator for the
sibling ``scifiWorldBuilding-Claude`` repo: the OQ-MD-5 **field-rocket** law for the metric
drive. The drive is propellantless (no reaction mass) but **not powerless and not free** — it
changes velocity only by radiating structured four-momentum, at a geometrically-forced 3×
handicap (the "universal Tsiolkovsky constant k = 3") that the setting's Rung-3 B2 breakthrough
discounts (k < 3, never 0).

Physics pins (Le 2026, arXiv:2606.22531 [gr-qc], PRELIMINARY; orchestrator derivation in the
sibling ``drafts/ftl-preferred-frame-decision-prep.md`` §G):
  * **Power law** ``P_rad = k·F·c`` — the pure-outgoing-null flux amplitude
    ``4πn² = −ṁ − 3m·a·cosθ`` must be ≥ 0 at every angle → monopole ≥ dipole → ⟨cos²θ⟩ = 1/3 →
    effective exhaust velocity c/3 → ``P ≥ 3Fc ≈ 0.9 GW/N`` at k = 3.
  * **Fuel/mass bill** — rectilinear boost ``m_f/m_0 = e^(−k·Δη)`` → radiated-mass fraction
    ``f_rad = 1 − e^(−k·Δη)``; a turn costs strictly more (``∫|a|du ≥ |Δη|``).
  * **Hold-cruise** — constant velocity F = 0 ⇒ P_rad = 0 (a confined positive-energy drive
    radiates NO propulsive four-momentum at cruise; the dP/du = 0 boundary case).
  * **Beam-vs-onboard** — a reflecting sail on an external beam needs ``P_beam = F·c/2`` ≈ 0.15
    GW/N; onboard needs ``k·F·c``, so onboard beats beam only if ``k < 0.5``.

**Load-bearing caveat surfaced in every model_note:** this is the **subluminal / STL-mode law
ONLY** — the theorem's hypotheses (DEC-satisfying, spatially confined, asymptotically flat)
exclude the exotic-matter FTL mode by construction; do NOT inherit this cost law for FTL legs.

Fuel ``f_conv = f (mass→energy fraction) × η_dir (directed/usable fraction)``. The ``pp`` / ``dd``
mass→energy fractions are **imported from** ``core.ism_drag_tables._FUSION`` (DRY — single source
of truth); ``d-t`` / ``d-he3`` / the two antimatter keys are field-drive-specific and defined
here. All values are first-principles/ideal ancestors, MTA-movable, caller-overridable.

No network, no DB, no numpy, no RNG, no time.
"""

import math

from core.equations import _C_MS, _STANDARD_GRAVITY
from core.ism_drag_tables import _FUSION

# ── Field-rocket fuel table: key -> {f (mass→energy), eta_dir_default, note} ──────
# pp / dd f-values are REUSED from core.ism_drag_tables._FUSION so they can't drift.
_FIELD_FUEL = {
    "d-t": {
        "f": 0.00375,
        "eta_dir_default": 1.0,
        "note": "D+T→⁴He+n, 17.59 MeV / 5.030 amu = 0.375% mass→energy (confirmed 2026-07-12). "
                "η_dir default 1.0 (ideal); the fast neutron carries ~80% of Q and is hard to "
                "direct — a realistic η_dir is far below 1.",
    },
    "d-he3": {
        "f": 0.0039,
        "eta_dir_default": 1.0,
        "note": "D+³He→⁴He+p, 18.35 MeV / 5.030 amu = 0.39% mass→energy (atomic masses; "
                "confirmed 2026-07-12). Aneutronic → charged products easier to direct.",
    },
    "pp": {
        "f": _FUSION["pp"]["f"],           # 0.0071 — reused from ism_drag_tables
        "eta_dir_default": 1.0,
        "note": "4H→⁴He chain, 26.73 MeV = 0.71% mass→energy (reused from _FUSION['pp']). ~2% of "
                "Q leaves as solar neutrinos → usable ~0.70% at η_dir 1.0.",
    },
    "dd": {
        "f": _FUSION["dd"]["f"],           # 0.0038 — reused from ism_drag_tables
        "eta_dir_default": 1.0,
        "note": "catalyzed D-D cycle ≈ 0.38% mass→energy (reused from _FUSION['dd']); a single "
                "D-D reaction is only ~0.10%.",
    },
    "antimatter-pp": {
        "f": 1.0,
        "eta_dir_default": 0.5,
        "note": "proton-antiproton: full rest-mass annihilation (f=1), BUT the at-rest partition "
                "is ≈½ neutrinos (lost) / ⅓ γ / ⅙ e± (Segrè et al. 1959 Phys. Rev. 113 1615; UW "
                "Nuclear Physics Lab) → usable ≈ 0.5. Design-dependent: magnetic pion capture "
                "before decay can raise η_dir toward ~0.6–0.7; undirected γ can lower it.",
    },
    "antimatter-ee": {
        "f": 1.0,
        "eta_dir_default": 1.0,
        "note": "positron-electron → 2γ: f=1, in principle fully usable (η_dir ~1.0), BUT low "
                "volumetric energy density + storage-hard. Treat η_dir 1.0 as an idealized ceiling.",
    },
}

_TSIOLKOVSKY_K_BASELINE = 3.0          # GR geometric baseline ⟨cos²θ⟩=1/3 → c/3
_BEAM_CROSSOVER_K = 0.5                # onboard beats beam only if k < this

_SELF_CONSISTENT_NOTE = (
    "First-order bill valid for fuel ≪ ship; self-consistent mode taxes carried fuel/ash and η_dir "
    "waste (effective exponent k/η_dir). Ash-vent mode treats vented mass as a zero-velocity dump "
    "only — ash used as reaction mass (hybrid field+material thrust) is NOT modeled here."
)

_MODEL_NOTE = (
    "Metric-drive field-rocket law (Le 2026 arXiv:2606.22531, PRELIMINARY). "
    "SUBLUMINAL / STL-MODE LAW ONLY: the theorem's hypotheses (DEC-satisfying, spatially "
    "confined, asymptotically flat) exclude the exotic-matter FTL mode by construction — do NOT "
    "use this power/fuel law for FTL legs. P_rad = k·F·c with k = 3 the GR geometric baseline "
    "(⟨cos²θ⟩ = 1/3 → effective exhaust c/3 → ≈0.9 GW/N); k < 3 is the setting's Rung-3 B2 exotic "
    "discount, never 0 (reactionless is forbidden — k > 0 required). This is the STEERING/ACCEL "
    "bill only: field-formation & hotel loads are separate (Pkt 26/27), and constant velocity "
    "(F = 0) ⇒ zero propulsive power. Fuel f_conv = f(mass→energy) × η_dir(directed/usable); the "
    "pp/dd fractions are reused from core.ism_drag_tables, all values are first-principles/ideal "
    "ancestors, MTA-movable, caller-overridable (--f-conv / --eta-dir / --k)."
)


def _resolve_mass_kg(mass_kg, mass_tonnes):
    """(mass_kg | mass_tonnes) → kg or {"error"} or None (no mass supplied)."""
    if mass_kg is not None and mass_tonnes is not None:
        return {"error": "Provide either --mass-kg or --mass-tonnes, not both."}
    if mass_kg is not None:
        if mass_kg <= 0:
            return {"error": "--mass-kg must be > 0."}
        return float(mass_kg)
    if mass_tonnes is not None:
        if mass_tonnes <= 0:
            return {"error": "--mass-tonnes must be > 0."}
        return mass_tonnes * 1000.0
    return None


def _atanh_beta(beta, label):
    """Exact-relativistic rapidity atanh(β) with a curated domain error."""
    if abs(beta) >= 1.0:
        return {"error": f"{label} must satisfy |β| < 1 (sublight); got {beta}."}
    return math.atanh(beta)


def compute_metric_drive_power(
        mass_kg=None, mass_tonnes=None,
        thrust_n=None, accel_g=None, accel_ms2=None,
        delta_v_kms=None, delta_v_c=None, rapidity=None, duration_days=None,
        k=3.0, fuel=None, f_conv=None, eta_dir=None,
        turn=False, integrated_rapidity=None, beam_compare=False,
        self_consistent=False, ash="keep"):
    """Field-rocket radiated power + fuel-mass bill for the metric drive (OQ-MD-5).

    See the module docstring for the full physics. Returns the JSON result dict, or a curated
    ``{"error": str}`` on missing/contradictory maneuver inputs, f_conv ≤ 0, or k ≤ 0.

    R6 (Phase AL) — ``self_consistent`` adds the Packet-25 fuel-wall accounting (Le 2026 exact law
    ``m_f/m_0 = e^(−k∫|a|du)`` with the conversion split): the first-order bill treats ship mass as
    fixed, but carried fuel + retained ash + η_dir waste are all part of the Bondi mass the law taxes.
    ``ash='keep'`` (default) yields the feasibility wall ``X = (1−e^(−k·Δη/η_dir))/f < 1`` and reports
    ``k_wall`` + ``lifetime_delta_v_budget_kms``; ``ash='vent'`` (zero-relative-velocity dump) has no
    wall. The existing first-order fields are unchanged (sc → first-order as Δη → 0).
    """
    # ── k ──
    if k is None or k <= 0:
        return {"error": "--k (Tsiolkovsky constant) must be > 0 — reactionless (k=0) is forbidden."}

    # ── self-consistent mode (R6) — ash retention validation ──
    if ash not in ("keep", "vent"):
        return {"error": "--ash must be 'keep' or 'vent'."}
    if ash == "vent" and not self_consistent:
        return {"error": "--ash vent is only used with --self-consistent."}

    # ── mass ──
    m0 = _resolve_mass_kg(mass_kg, mass_tonnes)
    if isinstance(m0, dict):
        return m0

    # ── thrust source: --thrust-n XOR (--accel-* × mass) ──
    if accel_g is not None and accel_ms2 is not None:
        return {"error": "Provide either --accel-g or --accel-ms2, not both."}
    accel_val = accel_ms2 if accel_ms2 is not None else (
        accel_g * _STANDARD_GRAVITY if accel_g is not None else None)

    has_leg = duration_days is not None
    if thrust_n is not None and accel_val is not None and not has_leg:
        return {"error": "Provide thrust via --thrust-n OR --accel-g/--accel-ms2, not both."}

    thrust = None
    if thrust_n is not None:
        if thrust_n < 0:
            return {"error": "--thrust-n must be ≥ 0."}
        thrust = float(thrust_n)
    elif accel_val is not None:
        if m0 is None:
            return {"error": "Deriving thrust from --accel-* needs a ship mass (--mass-kg/--mass-tonnes)."}
        thrust = m0 * accel_val

    # ── rapidity source: at most one of {rapidity, Δv_c, Δv_kms} OR a leg ──
    rap_sources = [v for v in (rapidity, delta_v_c, delta_v_kms) if v is not None]
    if len(rap_sources) > 1:
        return {"error": "Provide only one of --rapidity, --delta-v-c, or --delta-v-kms."}
    if rap_sources and has_leg:
        return {"error": "Provide a rapidity/Δv OR a leg (--accel-* + --duration-days), not both."}
    if has_leg and duration_days <= 0:
        return {"error": "--duration-days must be > 0."}

    eta = None                                   # net rapidity Δη
    if rapidity is not None:
        eta = float(rapidity)
    elif delta_v_c is not None:
        eta = _atanh_beta(delta_v_c, "--delta-v-c")
    elif delta_v_kms is not None:
        eta = _atanh_beta(delta_v_kms * 1000.0 / _C_MS, "--delta-v-kms")
    elif has_leg:
        if accel_val is None:
            return {"error": "A leg needs an acceleration (--accel-g/--accel-ms2) with --duration-days."}
        dv = accel_val * (duration_days * 86400.0)
        eta = _atanh_beta(dv / _C_MS, "the leg Δv")
    if isinstance(eta, dict):
        return eta

    # ── turn penalty (integrated arc ≥ |Δη|) ──
    if turn:
        if integrated_rapidity is None:
            return {"error": "--turn requires --integrated-rapidity (the ∫|a|du arc ≥ |Δη|)."}
        if integrated_rapidity <= 0:
            return {"error": "--integrated-rapidity must be > 0."}
        if eta is not None and integrated_rapidity < abs(eta) - 1e-12:
            return {"error": "--integrated-rapidity must be ≥ |Δη| (a turn costs at least the net "
                             f"rapidity {abs(eta):.6g})."}
        eta_used = float(integrated_rapidity)
    elif integrated_rapidity is not None:
        return {"error": "--integrated-rapidity is only used with --turn."}
    else:
        eta_used = eta if eta is not None else 0.0

    # ── power ──
    power_gw_per_n = k * _C_MS / 1e9
    propulsion_power_w = (k * thrust * _C_MS) if thrust is not None else None

    # ── radiated-mass fraction / leg energy ──
    f_rad = 1.0 - math.exp(-k * eta_used)
    leg_energy_j = (f_rad * m0 * _C_MS ** 2) if m0 is not None else None

    # ── fuel bill ──
    fuel_key = None
    resolved_eta_dir = None
    resolved_f_conv = None
    if f_conv is not None:
        if f_conv <= 0:
            return {"error": "--f-conv (effective mass→directed-energy fraction) must be > 0."}
        resolved_f_conv = float(f_conv)
    elif fuel is not None:
        if fuel not in _FIELD_FUEL:
            return {"error": f"Unknown --fuel '{fuel}'. Choose from: {', '.join(sorted(_FIELD_FUEL))}."}
        fuel_key = fuel
        preset = _FIELD_FUEL[fuel]
        resolved_eta_dir = eta_dir if eta_dir is not None else preset["eta_dir_default"]
        if resolved_eta_dir <= 0:
            return {"error": "--eta-dir (directed/usable fraction) must be > 0."}
        resolved_f_conv = preset["f"] * resolved_eta_dir
        if resolved_f_conv <= 0:
            return {"error": "Resolved f_conv (f × η_dir) must be > 0."}
    elif eta_dir is not None:
        return {"error": "--eta-dir needs a --fuel preset (it scales the fuel's mass→energy fraction)."}

    fuel_mass_fraction = fuel_mass_kg = None
    if resolved_f_conv is not None:
        fuel_mass_fraction = f_rad / resolved_f_conv
        if m0 is not None:
            fuel_mass_kg = fuel_mass_fraction * m0

    # ── self-consistent fuel-bill (R6) — taxes carried fuel/ash + η_dir waste ──
    sc_block = None
    if self_consistent:
        if eta_used <= 0:
            return {"error": "--self-consistent needs a maneuver with Δη > 0 (supply "
                             "--delta-v-*/--rapidity or a leg via --accel-* + --duration-days)."}
        if ash == "keep":
            # keep mode needs f (mass→energy) and η_dir SEPARATELY, not just their product f_conv.
            if fuel_key is not None:
                f_fuel = _FIELD_FUEL[fuel_key]["f"]
                eta_dir_val = resolved_eta_dir
            else:
                return {"error": "--self-consistent 'keep' mode needs a --fuel preset (to separate "
                                 "the mass→energy fraction f from η_dir); --f-conv alone cannot be "
                                 "split. Use --ash vent for the f_conv-only dump model."}
            X = (1.0 - math.exp(-k * eta_used / eta_dir_val)) / f_fuel
            feasible = X < 1.0
            fuel_mass_fraction_sc = X / (1.0 - X) if feasible else None
            if f_fuel >= 1.0:
                # full annihilation → ln(1−f) diverges: no finite wall (always feasible), and
                # the Δv budget saturates at c (tanh → 1).
                k_wall = None
                budget_kms = _C_MS / 1000.0
            else:
                k_wall = -eta_dir_val * math.log(1.0 - f_fuel) / eta_used
                budget_kms = _C_MS * math.tanh(-eta_dir_val * math.log(1.0 - f_fuel) / k) / 1000.0
            sc_block = {
                "self_consistent": True,
                "ash": "keep",
                "feasible": feasible,
                "fuel_mass_fraction_sc": fuel_mass_fraction_sc,
                "wall_ratio_x": X,
                "k_wall": k_wall,
                "lifetime_delta_v_budget_kms": budget_kms,
            }
        else:  # vent — zero-relative-velocity dump, no wall
            if resolved_f_conv is None:
                return {"error": "--self-consistent 'vent' mode needs a fuel (--fuel or --f-conv) "
                                 "for the effective f_conv."}
            fuel_mass_fraction_sc = math.exp(k * eta_used / resolved_f_conv) - 1.0
            sc_block = {
                "self_consistent": True,
                "ash": "vent",
                "feasible": True,
                "fuel_mass_fraction_sc": fuel_mass_fraction_sc,
                "wall_ratio_x": None,
                "k_wall": None,
                "lifetime_delta_v_budget_kms": None,
            }

    model_note = _MODEL_NOTE
    if self_consistent:
        model_note = _MODEL_NOTE + " " + _SELF_CONSISTENT_NOTE

    result = {
        "propulsion_power_w": propulsion_power_w,
        "power_gw_per_n": power_gw_per_n,
        "thrust_n": thrust,
        "rapidity_delta": eta_used,
        "radiated_mass_fraction": f_rad,
        "leg_energy_j": leg_energy_j,
        "fuel_mass_fraction": fuel_mass_fraction,
        "fuel_mass_kg": fuel_mass_kg,
        "fuel_key": fuel_key,
        "f_conv": resolved_f_conv,
        "eta_dir": resolved_eta_dir,
        "k": k,
        "ship_mass_kg": m0,
        "turn": turn,
        "model_note": model_note,
    }

    if sc_block is not None:
        result.update(sc_block)

    # ── beam-vs-onboard crossover ──
    if beam_compare:
        beam_gw_per_n = _C_MS / 2.0 / 1e9      # reflecting sail: 2P/c momentum → P = F·c/2
        result["beam_vs_onboard"] = {
            "beam_power_gw_per_n": beam_gw_per_n,
            "onboard_power_gw_per_n": power_gw_per_n,
            "crossover_k": _BEAM_CROSSOVER_K,
            "winner": "onboard" if k < _BEAM_CROSSOVER_K else "beam",
        }

    return result
