"""Phase AL (Group R) — power generation / delivery floor-physics calculators (Packet 27).

Five pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculators for the sibling
``scifiWorldBuilding-Claude`` repo — the generation / conversion / delivery floor laws no future
engineering repeals:

  * ``compute_annihilation_power_train`` (R1) — antimatter directed/γ/ν power partition (Frisbee L3).
  * ``compute_antimatter_production``    (R2) — production energy floor + Penning-trap storage ceiling.
  * ``compute_reactor_net_power``        (R4) — Q-gate / net-energy accounting (net-energy only).
  * ``compute_beamed_power_delivery``    (R7) — diffraction-limited link efficiency (λL/D wall).
  * ``compute_fusion_lawson``            (R10) — Lawson triple-product → Q (general-power side).

Bundled specific-power / specific-energy TABLES (no clean floor law) live in ``core.power_tables``;
the two storage ceilings that ARE laws (flywheel σ/ρ, SMES B²/2µ₀) live in ``core.energy_storage``;
active refrigeration (heat-pump) lives in ``core.thermal``. No network/DB/RNG/time/numpy. All
first-principles constants MTA-movable / caller-overridable.
"""

import math

from core.equations import _C_MS, _MP_C2_MEV, _EPSILON_0, _LY_M


# ── R1 — annihilation power train (directed / γ / ν partition) ───────────────

# p–p̄ at-rest branching (VERIFIED 2026-07-14, U. Washington NPL / Segrè et al. 1959 Phys. Rev. 113
# 1615): ≈ ½ neutrinos (lost) / ⅓ prompt γ (penetrating radiator burden) / ⅙ e± (directable). The
# directed fraction η_dir (default 0.5, capturable ~0.6–0.7 via magnetic pion capture) is a
# design-dependent report — NOT a strict partition with the fixed γ/ν branching channels.
_PP_GAMMA_FRAC = 1.0 / 3.0
_PP_NEUTRINO_FRAC = 1.0 / 2.0
_ETA_DIR_DEFAULT = {"pp": 0.5, "ee": 1.0}


def compute_annihilation_power_train(mass_flow_kgs=None, power_total_w=None,
                                     species="pp", eta_dir=None):
    """Antimatter annihilation power partition: directed / γ-heat / ν-loss.

    ``P_total = ṁ·c²`` (or given directly). For ``pp`` the at-rest partition is ≈½ ν / ⅓ γ / ⅙ e±;
    the directed (usable) power is η_dir·P_total (design-capturable, default 0.5). ``ee → 2γ`` has no
    neutrino channel and an η_dir ceiling ~1.0 (storage-hard).
    """
    if species not in ("pp", "ee"):
        return {"error": "species must be 'pp' or 'ee'."}
    if (mass_flow_kgs is None) == (power_total_w is None):
        return {"error": "Provide exactly one of mass_flow_kgs or power_total_w."}
    if mass_flow_kgs is not None:
        if mass_flow_kgs <= 0:
            return {"error": "mass_flow_kgs must be > 0."}
        p_total = mass_flow_kgs * _C_MS ** 2
    else:
        if power_total_w <= 0:
            return {"error": "power_total_w must be > 0."}
        p_total = float(power_total_w)

    eta = eta_dir if eta_dir is not None else _ETA_DIR_DEFAULT[species]
    if not (0.0 < eta <= 1.0):
        return {"error": "eta_dir must be in (0, 1]."}

    directed = eta * p_total
    if species == "pp":
        gamma = _PP_GAMMA_FRAC * p_total
        neutrino = _PP_NEUTRINO_FRAC * p_total
        note = ("p–p̄ at-rest annihilation: fixed branching ≈ ½ ν (lost) / ⅓ prompt γ (penetrating "
                "heat, a radiator burden) / ⅙ e± (VERIFIED — U. Washington NPL; Segrè et al. 1959 "
                "Phys. Rev. 113 1615). power_directed_w = η_dir·P_total is the DESIGN-CAPTURABLE "
                "fraction (default 0.5, ~0.6–0.7 with magnetic pion capture before decay) — it "
                "overlaps the γ/e± channels rather than being a strict partition, so directed + γ + "
                "ν need not sum to P_total.")
    else:  # ee
        gamma = p_total
        neutrino = 0.0
        note = ("e⁺e⁻ → 2γ: all rest energy as photons (no neutrino channel), in principle fully "
                "directable (η_dir ceiling ~1.0) but storage-hard / low volumetric density. "
                "power_gamma_w is the full 2γ output; power_directed_w = η_dir·P_total.")

    return {
        "power_total_w": p_total,
        "power_directed_w": directed,
        "power_gamma_w": gamma,
        "power_neutrino_w": neutrino,
        "eta_dir": eta,
        "species": species,
        "model_note": note + " P_total = ṁ·c². η_dir is MTA-movable / caller-overridable.",
    }


# ── R2 — antimatter production energy floor + storage density ────────────────

# Baryon-conserving threshold p+p → p+p+p+p̄: usable 2 m_p c² per stored 6 m_p c² input at threshold
# → ideal ceiling = 2/6 = 0.3333 (exact, first-principles; the m_p cancels).
_THRESHOLD_FLOOR_EFFICIENCY = (2.0 * _MP_C2_MEV) / (6.0 * _MP_C2_MEV)


def compute_antimatter_production(stored_mass_kg=None, stored_energy_j=None,
                                  production_efficiency=None, trap_field_t=None):
    """Antimatter production energy floor + Penning-trap storage-density ceiling.

    ``energy_in = stored_energy / production_efficiency``. The hard thermodynamic floor is the
    baryon-conserving threshold ≈ 2/6 = 0.3333 (real accelerators ~10⁻⁹; optimistic mature ~10⁻⁴).
    ``production_efficiency`` is REQUIRED and un-defaulted — it is the H-25-1 decision input and must
    be a cited caller number, never a shipped default. Optional ``trap_field_t`` → the Brillouin
    space-charge storage-mass-density ceiling ε₀·B²/2.
    """
    if (stored_mass_kg is None) == (stored_energy_j is None):
        return {"error": "Provide exactly one of stored_mass_kg or stored_energy_j."}
    if stored_mass_kg is not None:
        if stored_mass_kg <= 0:
            return {"error": "stored_mass_kg must be > 0."}
        energy_stored = stored_mass_kg * _C_MS ** 2
    else:
        if stored_energy_j <= 0:
            return {"error": "stored_energy_j must be > 0."}
        energy_stored = float(stored_energy_j)

    if production_efficiency is None:
        return {"error": "production_efficiency is required (wall-plug → stored; the H-25-1 research "
                         "input — no default is shipped). Supply a cited value in (0, 1]."}
    if not (0.0 < production_efficiency <= 1.0):
        return {"error": "production_efficiency must be in (0, 1]."}
    if trap_field_t is not None and trap_field_t <= 0:
        return {"error": "trap_field_t must be > 0."}

    energy_in = energy_stored / production_efficiency
    storage_density = (_EPSILON_0 * trap_field_t ** 2 / 2.0
                       if trap_field_t is not None else None)
    notes = []
    if production_efficiency > _THRESHOLD_FLOOR_EFFICIENCY:
        notes.append("production_efficiency exceeds the 0.333 baryon-conserving ideal ceiling — "
                     "physically impossible (flagged, still computed).")

    return {
        "energy_in_j": energy_in,
        "energy_stored_j": energy_stored,
        "production_efficiency": production_efficiency,
        "threshold_floor_efficiency": _THRESHOLD_FLOOR_EFFICIENCY,
        "energy_ratio_in_per_stored": 1.0 / production_efficiency,
        "storage_density_kg_m3": storage_density,
        "trap_field_t": trap_field_t,
        "notes": notes,
        "model_note": ("Production floor: energy_in = stored / η_prod; the hard thermodynamic "
                       "ceiling is the baryon-conserving threshold p+p→p+p+p+p̄ = 2 m_p / 6 m_p = "
                       "0.3333 (exact). Real accelerators ~10⁻⁹; optimistic mature ~10⁻⁴ — "
                       "η_prod is the caller-supplied H-25-1 research input, NOT a shipped default. "
                       "Storage ceiling (if --trap-field-t): the Brillouin space-charge mass density "
                       "ε₀·B²/2 [kg/m³] — species-independent, vanishingly dilute (traps hold almost "
                       "nothing). [pin @ open] the η_prod band (Frisbee 2008; Schmidt/Gerrish/Martin "
                       "NASA)."),
    }


# ── R4 — reactor net-power / Q-gate accounting ───────────────────────────────

def compute_reactor_net_power(gross_power_w=None, thermal_efficiency=None,
                              q_plasma=None, recirculating_fraction=0.0):
    """Net-energy accounting: how much of gross reactor output survives recirculation.

    ``P_electric = P_gross·η_th``; engineering breakeven at Q = 1/η_th; for a fusion plant the
    plasma-heating recirculation is a Q-tax ``P_electric/Q_plasma`` (→ 0 at ignition Q → ∞).
    ``P_net = P_electric·(1 − recirc) − Q-tax``. Specific power (W/kg) is deliberately NOT here — it
    is the ``reactor-power`` table + thermal pointer.
    """
    if gross_power_w is None or gross_power_w <= 0:
        return {"error": "gross_power_w must be > 0."}
    if thermal_efficiency is None or not (0.0 < thermal_efficiency <= 1.0):
        return {"error": "thermal_efficiency must be in (0, 1]."}
    if q_plasma is not None and q_plasma <= 0:
        return {"error": "q_plasma must be > 0."}
    if not (0.0 <= recirculating_fraction < 1.0):
        return {"error": "recirculating_fraction must be in [0, 1)."}

    electric = gross_power_w * thermal_efficiency
    engineering_breakeven_q = 1.0 / thermal_efficiency
    q_tax = electric / q_plasma if q_plasma is not None else 0.0
    net = electric * (1.0 - recirculating_fraction) - q_tax

    return {
        "gross_power_w": gross_power_w,
        "electric_power_w": electric,
        "net_power_w": net,
        "engineering_breakeven_q": engineering_breakeven_q,
        "thermal_efficiency": thermal_efficiency,
        "q_plasma": q_plasma,
        "recirculating_fraction": recirculating_fraction,
        "model_note": ("Net-energy accounting: P_elec = P_gross·η_th; engineering breakeven at "
                       "Q = 1/η_th; the fusion Q-tax P_elec/Q_plasma (plasma-heating recirculation) "
                       "→ 0 at ignition (Q → ∞). P_net = P_elec·(1−recirc) − Q-tax. NET-ENERGY only "
                       "— specific power W/kg is the reactor-power table + thermal pointer, and the "
                       "high-P binding ceiling is thermal (compose waste-heat → radiator-area). "
                       "q_plasma can be fed from fusion-lawson."),
    }


# ── R7 — beamed-power delivery (diffraction-limited link) ────────────────────

def compute_beamed_power_delivery(wavelength_m=None, frequency_hz=None, tx_aperture_m=None,
                                  rx_aperture_m=None, range_m=None, tx_power_w=None,
                                  pointing_efficiency=1.0):
    """Diffraction-limited beamed-power link efficiency (the λL/D wall).

    Full-null spot ``D_spot = 2.44·λ·L/D_t``; top-hat capture ``η ≈ min(1, (D_r/D_spot)²)``;
    full-coupling relation ``D_t·D_r ≳ 2.44·λ·L``. Supplies the delivery efficiency ``beam-sail``
    currently assumes on its --beam-power-w input.
    """
    if (wavelength_m is None) == (frequency_hz is None):
        return {"error": "Provide exactly one of wavelength_m or frequency_hz."}
    if wavelength_m is not None:
        if wavelength_m <= 0:
            return {"error": "wavelength_m must be > 0."}
        lam = float(wavelength_m)
    else:
        if frequency_hz <= 0:
            return {"error": "frequency_hz must be > 0."}
        lam = _C_MS / frequency_hz
    if tx_aperture_m is None or tx_aperture_m <= 0:
        return {"error": "tx_aperture_m must be > 0."}
    if rx_aperture_m is None or rx_aperture_m <= 0:
        return {"error": "rx_aperture_m must be > 0."}
    if range_m is None or range_m <= 0:
        return {"error": "range_m must be > 0."}
    if tx_power_w is not None and tx_power_w <= 0:
        return {"error": "tx_power_w must be > 0."}
    if not (0.0 < pointing_efficiency <= 1.0):
        return {"error": "pointing_efficiency must be in (0, 1]."}

    spot_diameter = 2.44 * lam * range_m / tx_aperture_m
    capture = min(1.0, (rx_aperture_m / spot_diameter) ** 2)
    aperture_product = tx_aperture_m * rx_aperture_m
    full_coupling_product = 2.44 * lam * range_m
    coupling_margin = aperture_product / full_coupling_product
    delivered = (tx_power_w * capture * pointing_efficiency
                 if tx_power_w is not None else None)

    return {
        "spot_diameter_m": spot_diameter,
        "capture_fraction": capture,
        "delivered_power_w": delivered,
        "aperture_product_m2": aperture_product,
        "full_coupling_product_m2": full_coupling_product,
        "coupling_margin": coupling_margin,
        "wavelength_m": lam,
        "range_m": range_m,
        "pointing_efficiency": pointing_efficiency,
        "model_note": ("Diffraction wall: full-null spot D_spot = 2.44·λ·L/D_t; top-hat capture "
                       "η_capture = min(1, (D_r/D_spot)²) (an Airy encircled-energy refinement is "
                       "optional); full coupling needs D_t·D_r ≳ 2.44·λ·L (coupling_margin ≥ 1). "
                       "P_rx = P_tx·η_capture·η_pointing. λL/D is a floor no engineering repeals — "
                       "long-range beamed power needs huge apertures or short range."),
    }


# ── R10 — Lawson triple-product → Q (general-power / reactor side ONLY) ──────

# Per-fuel ignition triple-product thresholds n·T·τ [keV·s·m⁻³], near each fuel's temperature
# minimum. [pin @ open] — illustrative first-principles anchors (Lawson 1957; Wesson *Tokamaks*),
# NOT verified promotions; aneutronic p-B11 is ~10³× harder and carries that caveat.
_LAWSON_IGNITION = {
    "d-t":   {"threshold": 3e21,  "note": "D-T ignition ≈ 3×10²¹ keV·s·m⁻³ near the ~14 keV minimum "
                                          "(the canonical, easiest fuel). [pin @ open]."},
    "d-he3": {"threshold": 6e22,  "note": "D-³He ≈ 1–2 orders harder than D-T (higher T, lower "
                                          "reactivity); aneutronic-leaning. [pin @ open]."},
    "d-d":   {"threshold": 1e23,  "note": "D-D ≈ ~30× harder than D-T. [pin @ open]."},
    "p-b11": {"threshold": 3e24,  "note": "p-¹¹B aneutronic ≈ 10³× harder than D-T (bremsstrahlung- "
                                          "and temperature-limited) — carries this cited caveat. "
                                          "[pin @ open]."},
}


def compute_fusion_lawson(fuel=None, density_m3=None, temp_kev=None, confinement_s=None,
                          triple_product=None, confinement_boost=1.0):
    """Lawson triple-product → fusion gain Q (grounds reactor-net-power's --q-plasma input).

    Triple product n·T·τ (from n, T, τ) OR ``triple_product`` directly, scaled by
    ``confinement_boost`` (the AG confinement multiplier on n·τ, echoed). Q ≈ triple-product /
    per-fuel ignition threshold; ``ignited`` when ≥ threshold.

    SCOPE GUARD — general-power / civilian-reactor side ONLY. The metric-drive task-(d) (AG-boosted
    fusion closing the DRIVE gap) stays refuted on f-wall grounds; confinement_boost is a Q lever
    feeding reactor-net-power, never a drive-closure route.
    """
    if fuel not in _LAWSON_IGNITION:
        return {"error": f"Unknown fuel '{fuel}'. Choose from: {', '.join(sorted(_LAWSON_IGNITION))}."}
    if confinement_boost is None or confinement_boost <= 0:
        return {"error": "confinement_boost must be > 0."}

    triple_parts = [density_m3, temp_kev, confinement_s]
    have_parts = [v is not None for v in triple_parts]
    if triple_product is not None and any(have_parts):
        return {"error": "Provide either --triple-product OR the (n, T, τ) triple, not both."}
    if triple_product is not None:
        if triple_product <= 0:
            return {"error": "triple_product must be > 0."}
        base_triple = float(triple_product)
    else:
        if not all(have_parts):
            return {"error": "Provide all of density_m3, temp_kev, confinement_s (or --triple-product)."}
        if density_m3 <= 0 or temp_kev <= 0 or confinement_s <= 0:
            return {"error": "density_m3, temp_kev, confinement_s must all be > 0."}
        base_triple = density_m3 * temp_kev * confinement_s

    # confinement_boost scales n·τ (not T) → scales the triple product.
    triple = base_triple * confinement_boost
    threshold = _LAWSON_IGNITION[fuel]["threshold"]
    q_fusion = triple / threshold
    ignited = triple >= threshold

    return {
        "triple_product_kev_s_m3": triple,
        "ignition_threshold": threshold,
        "q_fusion": q_fusion,
        "ignited": ignited,
        "confinement_boost": confinement_boost,
        "fuel": fuel,
        "model_note": ("Lawson triple product n·T·τ vs the per-fuel ignition threshold → gain Q "
                       "(ignited at Q ≥ 1). confinement_boost scales n·τ (an AG-derived confinement "
                       "gain), hand off to reactor-net-power --q-plasma. SCOPE GUARD: general-power "
                       "/ civilian-reactor side ONLY — this does NOT reopen the metric-drive task-(d) "
                       "(the DRIVE feasibility wall is bounded by the fuel's mass→energy fraction f, "
                       "which no confinement changes). Thresholds are [pin @ open] illustrative "
                       "anchors (Lawson 1957; Wesson Tokamaks); p-B11 aneutronic ~10³× harder. "
                       + _LAWSON_IGNITION[fuel]["note"]),
    }


# ── U2 (Phase AR, Group U) — beamrider relay-node spacing (Pkt 33) ────────────

def compute_beamrider_relay_spacing(wavelength_m=None, frequency_hz=None, tx_aperture_m=None,
                                    rx_aperture_m=None, delivered_fraction_threshold=0.5,
                                    total_range_ly=None, total_range_m=None):
    """Diffraction-limited beamrider relay-node spacing — the inverse of ``beamed-power-delivery``.

    Full-capture (transition) range ``L_t = D_t·D_r/(2.44·λ)`` (spot = collector); beyond it the
    delivered fraction falls as ``η ≈ (L_t/L)²``, so the relay spacing at a delivered-fraction
    threshold is ``L_relay = L_t/√threshold``. Optional --total-range → node count ceil(total/spacing).
    The relay nodes are the canon STL-waystation skeleton; this sizes their spacing.
    """
    if (wavelength_m is None) == (frequency_hz is None):
        return {"error": "Provide exactly one of wavelength_m or frequency_hz."}
    if wavelength_m is not None:
        if wavelength_m <= 0:
            return {"error": "wavelength_m must be > 0."}
        lam = float(wavelength_m)
    else:
        if frequency_hz <= 0:
            return {"error": "frequency_hz must be > 0."}
        lam = _C_MS / frequency_hz
    if tx_aperture_m is None or tx_aperture_m <= 0:
        return {"error": "tx_aperture_m must be > 0."}
    if rx_aperture_m is None or rx_aperture_m <= 0:
        return {"error": "rx_aperture_m must be > 0."}
    if not (0.0 < delivered_fraction_threshold <= 1.0):
        return {"error": "delivered_fraction_threshold must be in (0, 1]."}
    if total_range_ly is not None and total_range_m is not None:
        return {"error": "Provide at most one of total_range_ly or total_range_m."}
    if total_range_ly is not None and total_range_ly <= 0:
        return {"error": "total_range_ly must be > 0."}
    if total_range_m is not None and total_range_m <= 0:
        return {"error": "total_range_m must be > 0."}

    transition_range = tx_aperture_m * rx_aperture_m / (2.44 * lam)
    relay_spacing = transition_range / math.sqrt(delivered_fraction_threshold)

    n_relays = None
    if total_range_ly is not None or total_range_m is not None:
        total_m = total_range_m if total_range_m is not None else total_range_ly * _LY_M
        n_relays = math.ceil(total_m / relay_spacing)

    return {
        "transition_range_m": transition_range,
        "relay_spacing_m": relay_spacing,
        "relay_spacing_ly": relay_spacing / _LY_M,
        "delivered_fraction_threshold": delivered_fraction_threshold,
        "n_relays": n_relays,
        "wavelength_m": lam,
        "tx_aperture_m": tx_aperture_m,
        "rx_aperture_m": rx_aperture_m,
        "model_note": ("Inverts beamed-power-delivery's diffraction wall: transition range "
                       "L_t = D_t·D_r/(2.44·λ) (spot = collector); beyond it delivered fraction "
                       "≈ (L_t/L)², so relay spacing at a threshold = L_t/√threshold. A relay may "
                       "REGENERATE (receive → re-emit; this spacing) or REFOCUS (a passive "
                       "lens/mirror re-collimates — can extend spacing). Big optics / short λ extend "
                       "spacing (L ∝ D_t·D_r/λ). Composes beamed-power-delivery as an inverse solve, "
                       "not a new law."),
    }
