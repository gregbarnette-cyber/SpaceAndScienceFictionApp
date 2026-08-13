"""Phase AS (Packet 34) — radiation physical-dose → per-clade biological-ceiling converter.

A ``query.py``-only, pure-math, self-validating (Phase-H/P contract: curated ``{"error"}`` →
exit 1, argparse → exit 2) calculator that takes a physical radiation exposure (an absorbed
dose in Gy, a particle fluence + LET, or a composite LET spectrum), a temporal profile
(acute / chronic), and a crew substrate ("clade"), and returns the exposure's standing on
**two independent biological ceilings at once**:

  * **Axis A** — acute / deterministic ceiling (**Gy**, RBE-weighted): tissue-reaction / ARS
    survival, anchored on ARS onset and LD50.
  * **Axis B** — stochastic / cancer budget (**Sv**, vs a career REID budget): cumulative
    lifetime cancer-mortality risk, anchored on the career dose policy.

The two axes are NOT two views of one number and must not collapse to a scalar. Each clade
carries a modifier **pair** ``(m_A, m_B)`` composed from lever-tagged biology (§2.3): the
p53/apoptosis lever forces the axes apart (acute up ⇒ cancer up), while the repair-fidelity
lever may improve both. The ``upload`` clade (and the cyborg hardware fraction) is scored on a
**SEU / bit-error budget** — a different physical quantity — and emits no Gy/Sv.

All anchors, tables, and the clade ladder live in ``core.radiation_tables``. No network, DB,
RNG, time, or numpy. See ``docs/integration.md`` (radiation-ceiling) and
``completed_plans/PHASE_AS_PLAN.md``.
"""

import core.radiation_tables as t


# ── Exposure resolution ───────────────────────────────────────────────────────

def _parse_let_spectrum(spec):
    """Parse an ``"LET:fluence, LET:fluence"`` string → list of ``(let, fluence)`` or a
    ``{"error"}`` dict. Both values must be > 0."""
    bins = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            return {"error": f"Malformed --let-spectrum token '{token}' (expected 'LET:fluence')."}
        a, b = token.split(":", 1)
        try:
            let = float(a)
            flu = float(b)
        except ValueError:
            return {"error": f"Non-numeric --let-spectrum token '{token}' (expected 'LET:fluence')."}
        if let <= 0 or flu <= 0:
            return {"error": f"--let-spectrum LET and fluence must be > 0 (got '{token}')."}
        bins.append((let, flu))
    if not bins:
        return {"error": "--let-spectrum is empty."}
    return bins


def _resolve_exposure(absorbed_dose_gy, fluence, let_kev_um, particle_type,
                      energy_mev_amu, let_spectrum):
    """Resolve the exposure to ``(dose_gy, rbe_eff, q_eff, let_repr, out_of_range, form)``.

    Dose-weights RBE and Q across a composite LET spectrum. Returns a ``{"error"}`` dict on any
    validation failure (missing quality, both magnitude forms, non-positive values, …).
    """
    # Composite LET spectrum — self-contained (carries LET + fluence per bin).
    if let_spectrum is not None:
        if absorbed_dose_gy is not None or fluence is not None or let_kev_um is not None \
                or particle_type is not None:
            return {"error": "--let-spectrum is exclusive — do not combine it with "
                             "--absorbed-dose-gy / --fluence / --let-kev-um / --particle-type."}
        bins = _parse_let_spectrum(let_spectrum)
        if isinstance(bins, dict):
            return bins
        total_dose = 0.0
        rbe_num = q_num = 0.0
        out_of_range = False
        for let, flu in bins:
            d_i = t.FLUENCE_DOSE_K * let * flu
            rbe_i, oor = t.rbe_for_let(let)
            out_of_range = out_of_range or oor
            total_dose += d_i
            rbe_num += d_i * rbe_i
            q_num += d_i * t.q_for_let(let)
        if total_dose <= 0:
            return {"error": "--let-spectrum integrates to zero dose."}
        return (total_dose, rbe_num / total_dose, q_num / total_dose,
                f"spectrum ({len(bins)} bins)", out_of_range, "let_spectrum")

    # Otherwise a quality input is required to weight the dose.
    let = None
    if let_kev_um is not None:
        if let_kev_um <= 0:
            return {"error": "--let-kev-um must be > 0."}
        let = float(let_kev_um)
        let_repr = f"{let:g} keV/um"
    elif particle_type is not None:
        if particle_type not in t._PARTICLE_LET:
            return {"error": f"Unknown --particle-type '{particle_type}'. Choose one of "
                             f"{', '.join(t.particle_names())} or supply --let-kev-um."}
        let = t.let_for_particle(particle_type, energy_mev_amu)
        let_repr = f"{particle_type} (~{let:g} keV/um preset)"
    else:
        return {"error": "A radiation-quality input is required to weight the dose: supply "
                         "--let-kev-um, --particle-type, or --let-spectrum. (A raw fluence or Gy "
                         "cannot be weighted without it.)"}

    # Magnitude — exactly one of absorbed dose or fluence.
    have_dose = absorbed_dose_gy is not None
    have_fluence = fluence is not None
    if have_dose and have_fluence:
        return {"error": "Provide exactly one of --absorbed-dose-gy or --fluence, not both."}
    if have_dose:
        if absorbed_dose_gy < 0:
            return {"error": "--absorbed-dose-gy must be >= 0."}
        dose = float(absorbed_dose_gy)
        form = "absorbed_dose"
    elif have_fluence:
        if fluence < 0:
            return {"error": "--fluence must be >= 0."}
        dose = t.FLUENCE_DOSE_K * let * fluence
        form = "fluence"
    else:
        return {"error": "An exposure magnitude is required: supply --absorbed-dose-gy or "
                         "--fluence (with a quality input)."}

    rbe, oor = t.rbe_for_let(let)
    return (dose, rbe, t.q_for_let(let), let_repr, oor, form)


# ── Clade / lever composition ─────────────────────────────────────────────────

def _compose_modifiers(clade_def, lever_type, lever_m_a, lever_m_b, allow_p53_double_improve):
    """Compose ``(m_a, m_b, levers, coupling_enforced, p53_overridden)`` or a ``{"error"}`` dict.

    Enforces the p53 trade: a p53 lever with ``f_a > 1`` may not carry ``f_b < 1`` (that would
    improve both axes) unless explicitly overridden.
    """
    levers = [dict(lv) for lv in clade_def["levers"]]
    if lever_type is not None:
        f_a = 1.0 if lever_m_a is None else float(lever_m_a)
        f_b = 1.0 if lever_m_b is None else float(lever_m_b)
        if f_a <= 0 or f_b <= 0:
            return {"error": "--lever-m-a and --lever-m-b must be > 0."}
        levers.append({"type": lever_type, "f_a": f_a, "f_b": f_b,
                       "confidence": "extrapolation", "note": "caller-specified lever."})

    coupling_enforced = False
    p53_overridden = False
    for lv in levers:
        if lv["type"] == t.LEVER_P53 and lv["f_a"] > 1.0:
            coupling_enforced = True
            if lv["f_b"] < 1.0:
                if not allow_p53_double_improve:
                    return {"error": "The p53/apoptosis-suppression lever cannot improve BOTH axes: "
                                     "raising acute tolerance by suppressing radiation-triggered "
                                     "apoptosis (culling fewer damaged cells) RAISES stochastic "
                                     "cancer risk (S15). Set --allow-p53-double-improve to override "
                                     "(S15 is abstract-only; re-open before canon)."}
                p53_overridden = True

    m_a = clade_def["base_m_a"]
    m_b = clade_def["base_m_b"]
    for lv in levers:
        m_a *= lv["f_a"]
        m_b *= lv["f_b"]
    return m_a, m_b, levers, coupling_enforced, p53_overridden


# ── Axis A / Axis B / SEU scorers ─────────────────────────────────────────────

def _score_axis_a(dose_gy, rbe, m_a, dmf_applied, clade_conf, profile,
                  dose_rate_gy_day, allow_rb):
    """Axis A deterministic ceiling. Chronic delivery does NOT bind the acute ceiling (§2.1)."""
    ceiling = t.LD50_REFERENCE_GY * m_a * dmf_applied
    required_breakthrough = ceiling > t.DEINOCOCCUS_CEILING_GY
    if required_breakthrough and not allow_rb:
        return {"error": f"Axis-A ceiling {ceiling:.1f} Gy exceeds the Deinococcus existence-proof "
                         f"sanity ceiling ({t.DEINOCOCCUS_CEILING_GY:.0f} Gy, S11). A whole-mechanism "
                         "organism-scale transplant is a required-breakthrough — set "
                         "--allow-required-breakthrough to emit an organism-scale ceiling."}

    if profile == "chronic":
        rate_check = None
        if dose_rate_gy_day is not None:
            sub = dose_rate_gy_day < t.TISSUE_REACTION_RATE_THRESHOLD_GY_PER_DAY
            rate_check = {
                "dose_rate_gy_per_day": dose_rate_gy_day,
                "threshold_gy_per_day": t.TISSUE_REACTION_RATE_THRESHOLD_GY_PER_DAY,
                "sub_threshold": sub,
                "assessment": ("below the repair-rate threshold — no acute tissue reaction expected"
                               if sub else
                               "above the repair-rate threshold — possible acute tissue reaction; "
                               "evaluate tissue-resolved thresholds"),
            }
        return {
            "applicable": False,
            "reason": "chronic delivery: the cumulative dose does NOT bind the acute deterministic "
                      "ceiling (repair keeps pace below the rate threshold) — scored on Axis B plus a "
                      "tissue-reaction-rate check, never summed against the acute Gy ceiling (§2.1).",
            "clade_acute_ceiling_gy": ceiling,
            "tissue_reaction_rate_check": rate_check,
            "provenance": {"clade_acute_ceiling_gy": clade_conf,
                           "ars_thresholds": "physics-limit"},
        }

    d_a = dose_gy * rbe
    return {
        "applicable": True,
        "clade_acute_ceiling_gy": ceiling,
        "acute_equivalent_dose_gy": d_a,
        "rbe_used": rbe,
        "margin_gy": ceiling - d_a,
        "fraction_of_ceiling": (d_a / ceiling) if ceiling > 0 else None,
        "ars_severity_band": t.ars_band(d_a),
        "ars_band_note": "The ARS band is scored against ABSOLUTE baseline photon-equivalent ARS/LD50 "
                         "thresholds (a clinical descriptor); it can diverge from the clade-relative "
                         "fraction_of_ceiling — a radiosensitive clade at 100% of its own (lowered) "
                         "ceiling may still read a mild band. Read the two together, not the band alone.",
        "dmf_applied": dmf_applied,
        "provenance": {
            "clade_acute_ceiling_gy": clade_conf,
            "ars_thresholds": "physics-limit",
            "rbe_used": "extrapolation",   # high-LET RBE elevated + uncertain (S8)
            "dmf_applied": "present-datapoint",
        },
    }


def _score_axis_b(dose_gy, q, m_b, profile, ddref, budget_key):
    """Axis B stochastic / cancer budget. H = D * Q; REID scales from the 600 mSv @ 3% anchor."""
    h_sv = dose_gy * q                       # cumulative equivalent dose (Sv)
    h_eff_sv = h_sv / ddref if profile == "chronic" else h_sv
    h_eff_msv = h_eff_sv * 1000.0

    reid_pct = t.REID_ANCHOR_PCT * (h_eff_msv / t.REID_ANCHOR_MSV) * m_b
    policy = t.CAREER_BUDGETS[budget_key]
    budget_sv = policy["budget_msv"] / 1000.0
    # A clade with better repair (m_b < 1) reaches the policy REID acceptance at a larger dose.
    clade_budget_sv = budget_sv / m_b if m_b > 0 else None
    fraction = (h_eff_sv / clade_budget_sv) if clade_budget_sv else None

    return {
        "applicable": True,
        "career_budget_sv": budget_sv,
        "career_budget_policy": policy["label"],
        "clade_adjusted_budget_sv": clade_budget_sv,
        "cumulative_equivalent_dose_sv": h_eff_sv,
        "q_used": q,
        "w_r_note": "ICRP quality factor Q(LET) — distinct from the deterministic RBE (Axis A).",
        "reid_percent": reid_pct,
        "fraction_of_budget": fraction,
        "remaining_budget_sv": (clade_budget_sv - h_eff_sv) if clade_budget_sv is not None else None,
        "ddref_used": ddref,
        "ddref_note": t.DDREF_SOURCE if ddref != t.DDREF_DEFAULT else None,
        "provenance": {
            # REID is a LINEAR projection off the 600 mSv @ 3% POLICY anchor (not a measured
            # limit) — an extrapolation, sharpest at high acute dose where LNT is out of regime.
            "career_budget_policy": "policy",
            "reid_percent": "extrapolation",
            "q_used": "physics-limit",
            # 600 mSv / m_b is a POLICY budget (optionally clade-scaled), never physics-limit.
            "clade_adjusted_budget_sv": "policy",
            "ddref_used": "extrapolation",   # DDREF disputed
        },
    }


def _score_seu(fluence_total, seu_cross_section_cm2, memory_bits, ecc_margin):
    """SEU / bit-error budget for the hardware substrate (upload / cyborg hardware fraction)."""
    if fluence_total is None:
        return {
            "applicable": True,
            "different_physical_quantity": True,
            "seu_rate_per_bit": None,
            "reason": "supply --fluence (a particle fluence) to score the SEU/bit-error budget.",
            "note": t.SEU_SOURCE,
            "confidence": "engineering",
            "provenance": {"seu_budget": "present-datapoint"},
        }
    xs = t.SEU_CROSS_SECTION_DEFAULT_CM2 if seu_cross_section_cm2 is None else seu_cross_section_cm2
    rate_per_bit = fluence_total * xs
    expected_upsets = rate_per_bit * memory_bits if memory_bits is not None else None
    within = None
    if ecc_margin is not None and expected_upsets is not None:
        within = expected_upsets <= ecc_margin
    return {
        "applicable": True,
        "different_physical_quantity": True,
        "fluence_cm2": fluence_total,
        "cross_section_cm2": xs,
        "cross_section_is_default": seu_cross_section_cm2 is None,
        "seu_rate_per_bit": rate_per_bit,
        "memory_bits": memory_bits,
        "expected_upsets": expected_upsets,
        "ecc_margin": ecc_margin,
        "within_ecc_margin": within,
        "note": t.SEU_SOURCE,
        "confidence": "engineering",
        "provenance": {"seu_budget": "present-datapoint"},
    }


def _dose_rate_to_gy_day(dose_rate, dose_rate_unit):
    """Convert a chronic dose rate to Gy/day (Sv≈Gy for the low-LET rate screen)."""
    if dose_rate is None:
        return None
    if dose_rate_unit == "sv/yr":
        return dose_rate / 365.25
    return dose_rate   # gy/day (default)


# ── Public entry point ────────────────────────────────────────────────────────

def compute_radiation_ceiling(
        absorbed_dose_gy=None, fluence=None,
        let_kev_um=None, particle_type=None, energy_mev_amu=None, let_spectrum=None,
        profile="acute", dose_rate=None, dose_rate_unit="gy/day", duration=None, duration_unit="days",
        clade="baseline-human",
        pharmacological_dmf=None, career_budget_policy=None, ddref=None,
        lever=None, lever_m_a=None, lever_m_b=None,
        allow_p53_double_improve=False, allow_required_breakthrough=False,
        seu_cross_section_cm2=None, memory_bits=None, ecc_margin=None):
    """Convert a physical radiation exposure to a per-clade two-axis biological ceiling.

    See the module docstring / ``docs/integration.md`` for the full contract. Returns a
    structured two-axis dict, or ``{"error": str}`` on any validation failure.
    """
    if clade not in t.CLADES:
        return {"error": f"Unknown clade '{clade}'. Choose one of {', '.join(t.CLADE_NAMES)}."}
    if profile not in ("acute", "chronic"):
        return {"error": "profile must be 'acute' or 'chronic'."}
    if lever is not None and lever not in t.LEVER_TYPES:
        return {"error": f"Unknown lever '{lever}'. Choose one of {', '.join(t.LEVER_TYPES)}."}
    if dose_rate_unit not in ("gy/day", "sv/yr"):
        return {"error": "dose_rate_unit must be 'gy/day' or 'sv/yr'."}
    if dose_rate is not None and dose_rate <= 0:
        return {"error": "--dose-rate must be > 0."}
    if duration is not None and duration <= 0:
        return {"error": "--duration must be > 0."}

    budget_key = t.DEFAULT_CAREER_BUDGET if career_budget_policy is None else str(career_budget_policy)
    if budget_key not in t.CAREER_BUDGETS:
        return {"error": f"career_budget_policy must be one of {', '.join(t.CAREER_BUDGETS)} (mSv)."}

    # Pharmacological DMF — clamped at the S10 ceiling (a cap, per §3 case 8), never silently.
    dmf_capped = False
    if pharmacological_dmf is None:
        dmf_applied = 1.0
    else:
        if pharmacological_dmf <= 0:
            return {"error": "--pharmacological-dmf must be > 0."}
        dmf_applied = pharmacological_dmf
        if dmf_applied > t.DMF_MAX:
            dmf_applied = t.DMF_MAX
            dmf_capped = True

    ddref_used = t.DDREF_DEFAULT if ddref is None else ddref
    if ddref_used <= 0:
        return {"error": "--ddref must be > 0."}

    clade_def = t.CLADES[clade]

    # Resolve the exposure (dose + the two quality weightings). A fluence total is kept for the
    # SEU path even when the biological axes are N/A.
    exposure = _resolve_exposure(absorbed_dose_gy, fluence, let_kev_um, particle_type,
                                 energy_mev_amu, let_spectrum)
    fluence_total_for_seu = fluence
    if isinstance(exposure, dict):
        # For upload with no biological weighting, a bare --fluence is still valid (SEU-only).
        if clade == "upload" and fluence is not None and let_kev_um is None \
                and particle_type is None and let_spectrum is None and absorbed_dose_gy is None:
            exposure = None
        else:
            return exposure

    out = {
        "clade": clade,
        "clade_note": clade_def["note"],
        "clade_confidence": clade_def["confidence"],
        "profile": profile,
        "is_order_of_magnitude": True,
        "model_note": t.MODEL_NOTE,
        "provenance_legend": t.PROVENANCE_LEGEND,
    }

    # ── Biological clade: score both axes ─────────────────────────────────────
    if clade_def["biological"]:
        comp = _compose_modifiers(clade_def, lever, lever_m_a, lever_m_b, allow_p53_double_improve)
        if isinstance(comp, dict):
            return comp
        m_a, m_b, levers, coupling_enforced, p53_overridden = comp

        if exposure is None:
            return {"error": "An exposure is required to score a biological clade "
                             "(supply --absorbed-dose-gy / --fluence / --let-spectrum with a quality)."}
        dose_gy, rbe_eff, q_eff, let_repr, out_of_range, form = exposure
        dose_rate_gy_day = _dose_rate_to_gy_day(dose_rate, dose_rate_unit)

        axis_a = _score_axis_a(dose_gy, rbe_eff, m_a, dmf_applied, clade_def["confidence"],
                               profile, dose_rate_gy_day, allow_required_breakthrough)
        if isinstance(axis_a, dict) and "error" in axis_a:
            return axis_a
        axis_b = _score_axis_b(dose_gy, q_eff, m_b, profile, ddref_used, budget_key)

        required_breakthrough = (axis_a.get("clade_acute_ceiling_gy", 0) > t.DEINOCOCCUS_CEILING_GY)

        out.update({
            "exposure": {
                "absorbed_dose_gy": dose_gy,
                "quality": let_repr,
                "rbe_effective": rbe_eff,
                "q_effective": q_eff,
                "source_form": form,
            },
            "axis_a_deterministic": axis_a,
            "axis_b_stochastic": axis_b,
            "clade_modifiers": {
                "m_a": m_a, "m_b": m_b, "levers": levers,
                "coupling_enforced": coupling_enforced,
            },
            "seu_budget": None,
            "flags": {
                "out_of_range_let": out_of_range,
                "required_breakthrough": required_breakthrough,
                "dmf_capped": dmf_capped,
                "p53_double_improve_overridden": p53_overridden,
            },
        })

        # Cyborg: the hardware fraction ALSO carries a SEU budget.
        if clade_def["hardware_fraction"]:
            out["seu_budget"] = _score_seu(fluence_total_for_seu, seu_cross_section_cm2,
                                           memory_bits, ecc_margin)
        return out

    # ── Non-biological clade (upload): N/A both axes → SEU budget only ─────────
    na_a = {"applicable": False,
            "reason": "upload clade — the biological acute (deterministic) ceiling is N/A; the "
                      "substrate is a required-breakthrough (S61). No Gy emitted.",
            "provenance": {"axis": "required-breakthrough"}}
    na_b = {"applicable": False,
            "reason": "upload clade — the biological stochastic (cancer) budget is N/A; scored on "
                      "the SEU/bit-error budget instead. No Sv emitted.",
            "provenance": {"axis": "required-breakthrough"}}
    out.update({
        "exposure": {"source_form": "fluence" if fluence is not None else None,
                     "fluence_cm2": fluence},
        "axis_a_deterministic": na_a,
        "axis_b_stochastic": na_b,
        "clade_modifiers": {"m_a": None, "m_b": None, "levers": [], "coupling_enforced": False},
        "seu_budget": _score_seu(fluence_total_for_seu, seu_cross_section_cm2, memory_bits, ecc_margin),
        "flags": {
            "out_of_range_let": False,
            "required_breakthrough": True,
            "dmf_capped": dmf_capped,
            "p53_double_improve_overridden": False,
        },
    })
    return out
