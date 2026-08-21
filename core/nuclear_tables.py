"""core/nuclear_tables.py — CR-4 bundled constants + the PROVISIONAL Interface-A (3c) bundle.

The fusion + radiogenic constants are APP-owned (pinned to primary sources; order-of-magnitude where
noted). The fissile path consumes the WB **3c FINAL** *fissile-fraction GCE model* through ``_GCE_MODEL``
(model_version ``3c-v1.0.0-2026-08-15``, integrated from the delivered
``fissile-fraction-gce-model.json``), the **per-isotope** Interface-A shape pinned in coordination
MSG 035/042; a future WB revision swaps this one constant, no code change. (``_GCE_MODEL_PROVISIONAL``
remains a back-compat alias.)
"""

import math

# ── Decay (Interface-A decay_halflives_gyr + K-40 for radiogenic) ──────────────
# Half-lives in Gyr. U/Th values are the spec's Interface-A pins; K-40 for the radiogenic block.
_HALFLIFE_GYR = {"U235": 0.7038, "U238": 4.468, "Th232": 14.05, "K40": 1.251}
_LAMBDA_PER_GYR = {k: math.log(2.0) / v for k, v in _HALFLIFE_GYR.items()}

# Specific radiogenic heat production, W per kg OF THE ISOTOPE (Van Schmus 1995; Rybach 1988).
# Domain-review-confirmed (2026-08-15): U238 9.46e-5, U235 5.69e-4, Th232 2.64e-5, K40 2.92e-5.
_HEAT_W_PER_KG_ISOTOPE = {"U238": 9.46e-5, "U235": 5.69e-4, "Th232": 2.64e-5, "K40": 2.92e-5}

# Bulk-silicate-Earth reference (present-day) — the radiogenic solar anchor basis.
# Elemental mass fractions: U 20 ppb, Th 80 ppb, K 280 ppm. Present isotopic fractions:
# U235/U 0.72%, U238/U 99.27%, K40/K 0.0117%, Th all ²³²Th. Σ heat ≈ 5.0e-12 W/kg (BSE ~20 TW).
_BSE = {"U_mass_frac": 20.0e-9, "Th_mass_frac": 80.0e-9, "K_mass_frac": 280.0e-6}
_PRESENT_ISO_FRAC = {"U235": 0.0072, "U238": 0.992745, "Th232": 1.0, "K40": 1.17e-4}

_SOLAR_AGE_GYR = 4.567          # radiogenic + fissile solar anchor age

# ── Fusion-fuel anchors (APP-owned; order-of-magnitude, feh/age trends tagged) ──
# BBN primordial values — label PRIMORDIAL-BBN, not protosolar (protosolar D/H ≈ 2.0e-5).
_PRIMORDIAL_D_H = 2.53e-5        # BBN D/H number ratio (Cooke et al. 2018)
_PRIMORDIAL_HE3_H = 1.0e-5       # BBN ³He/H number ratio
_D_ASTRATION_SLOPE = 0.40        # D/H depletion vs Z/Z_sun (stellar astration), illustrative
_HE3_METAL_SLOPE = 0.50          # wind-implanted / stellar ³He enhancement vs Z, illustrative
# Lithium/boron on the A(X) = 12 + log10(N_X/N_H) abundance scale. Spite plateau A(Li)≈2.2 at
# low [Fe/H] rising to ~3.3 (meteoritic) at solar; 6Li/7Li ISM ≈ 0.06; A(B)_sun ≈ 2.7, GCE-rising.
_LI7_PLATEAU = 2.2
_LI7_SOLAR = 3.3
_LI6_OVER_LI7 = 0.06
_B11_SOLAR = 2.66               # A(B)_sun ≈ 2.7; ¹¹B/B ≈ 0.80
_EU_SOLAR_DEX = 0.52           # A(Eu)_sun (Lodders 2009) — [Eu/H] → linear Eu for absolute U/Th

# ── Interface-A (3c FINAL) bundle — PER-ISOTOPE (coordination MSG 042, 2026-08-15) ──
# Swapped in from scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/
# fissile-fraction-gce-model.json (model_version 3c-v1.0.0). The gce_enrichment g_i is the
# AGE-DEPENDENT uniform-production mean-survival integral — NOT the constant provisional form; the
# two agree only at the solar g-ratio (0.238 → present U235/U238 0.007258). Solar anchor holds.
# confidence: extrapolation.
_D_EFF_GYR = 11.55                       # effective enrichment span (onset→present); calibrated to
                                         # solar initial 235U/238U=0.321 given P=1.35, degenerate with P.

_GCE_MODEL = {
    "model_version": "3c-v1.0.0-2026-08-15",
    "production_ratios": {                       # LINEAR N ratios at fresh r-process production (per Eu)
        "U235_over_Eu": 0.393,
        "U238_over_Eu": 0.291,
        "Th232_over_Eu": 0.51,
        "U235_over_U238_initial": 1.35,          # ±0.30; degenerate with D_eff; no empirical stellar check
        "basis": "Th/Eu del Peloso 2005; U/Th Dauphas 2005 (P_U/Th=0.571); U235/U238 Cowan-Thielemann-"
                 "Truran 1991 (see fissile-fraction-gce-model.json)",
    },
    "gce_enrichment": {
        "form": "parametric",
        "d_eff_gyr": _D_EFF_GYR,
        "population_source": "CR-7 verdict string (thin|thick|halo)",
        "domain": {"feh_range": [-2.5, 0.5], "age_range_gyr": [0.0, 13.6]},
    },
    "solar_anchor": {"U235_U238_present": 0.0072558, "Eu_H_dex": 0.0, "age_gyr": _SOLAR_AGE_GYR,
                     "U235_U238_initial": 0.321},
    "confidence": "extrapolation",
}
# Back-compat alias (nuclear.py + tests reference the historical name).
_GCE_MODEL_PROVISIONAL = _GCE_MODEL


def gce_enrichment_factor(isotope, age_gyr, population=None, feh=None, model=_GCE_MODEL):
    """Per-isotope GCE mean-survival factor g_i(age) — 3c FINAL uniform-production integral.

    ``D = max(0, D_eff − age)``; ``g_i = (1 − e^(−λ_i·D)) / (λ_i·D)`` for D>0; ``g_i = 1`` for
    ``age ≥ D_eff`` (halo / fresh-production floor). Reproduces the 3c derived table (solar age →
    g_U235=0.1452, g_U238=0.6105, g_Th232=0.8458)."""
    d = model["gce_enrichment"]["d_eff_gyr"] - age_gyr
    if d <= 0:
        return 1.0
    lam = _LAMBDA_PER_GYR[isotope]
    return (1.0 - math.exp(-lam * d)) / (lam * d)


# ── §8 domain-guard screen thresholds (documented; fissile-fraction-gce-model.md §8) ──
_DV2_EU_FE_ACTINIDE_BOOST = 0.7   # [Eu/Fe] ≳ +0.7 → r-II / actinide-boost: voids the RATIO *and* tonnage.
_DV3_EU_FE_S_PROCESS = 0.4        # runbook Eu-artifact proxy: distrust [Eu/Fe] ≳ +0.4 …
_DV3_FEH_MIN = -0.5               # … on a thin-disk, NOT metal-poor ([Fe/H] ≳ this) star ⇒ s-process, not r.
_DV3_BA_EU_S_DOMINANCE = 0.5      # if [Ba/Eu] supplied: ≥ +0.5 ⇒ s-process dominance (CEMP-s cut, Beers &
                                  # Christlieb 2005). Solar ≈ 0 and pure-r ≈ −0.7 are NOT flagged.
_DV5_FEH_SOFT_UPPER = 0.5         # CR-10.2 / CQ-7-3c-6: [Fe/H] ABOVE this is a SOFT per-output flag
                                  # (feh_extrapolation) on the [Fe/H]-dependent K-40 radiogenic-heat
                                  # channel — NOT a hard void. Coincident with the model feh_range upper
                                  # edge today, but a distinct soft-extrapolation threshold: the fissile
                                  # FRACTION is [Fe/H]-independent, so it is never voided by [Fe/H].


def gce_domain_ok(age_gyr, feh, eu_fe=None, population=None, ba_eu=None,
                  age_soft=False, eu_available=True, model=_GCE_MODEL):
    """3c FINAL domain rules → ``(ok, reason, bands, detail)``.

    Implements all **four** §8 ``false_when`` guards (was 3 of 4 — DEFECT-2):
    - **DV-5** age/[Fe/H] outside the fit domain ([0, 13.6] Gyr / [-2.5, 0.5]) → void the fissile model;
    - **DV-2** [Eu/Fe] ≳ +0.7 (actinide-boost / r-II) → production ratio event-class-dependent, voids
      BOTH the U-235/U-238 ratio AND the tonnage;
    - **DV-3** [Eu/H] must be a genuine r-process tracer: s-process (AGB/Ba) pollution makes [Eu/H]
      over-state the r-process → voids the *tonnage* (not the isotope ratio). Preferred discriminant
      [Ba/Eu] ≳ 0; else the runbook proxy [Eu/Fe] ≳ +0.4 on a thin-disk, non-metal-poor star;
    - **DV-1** ``age_soft`` — an *advisory* flag (order-of-magnitude, not a veto) when the age is a
      population/[Fe/H] prior rather than a measurement.

    ``ok`` is **tri-state** (CQ-7-3c-4): ``True`` in-domain, ``False`` on a veto, ``None`` when the
    Eu-dependent guards (DV-2/DV-3) are **unevaluable** (no r-process tracer) so "ok" cannot be
    asserted. ALL fired vetoes are collected — no ``elif`` shadowing (DEFECT-4). ``detail`` carries the
    per-output severities (``isotope_ratio`` / ``tonnage`` / ``radiogenic_heat``) + the guard flags.
    ``bands`` flags the DV-4/DV-7 reduced-reliability regimes (young / ISM-mixing / old) — central
    values are still emitted (flag, never clamp)."""
    dom = model["gce_enrichment"]["domain"]
    lo_f = dom["feh_range"][0]
    lo_a, hi_a = dom["age_range_gyr"]
    reasons = []
    domain_out = actinide_boost = s_process = feh_extrapolation = False

    # DV-5 — fitted age / [Fe/H] domain. Age-out and the LOWER [Fe/H] edge stay HARD (they void the
    # age-dependent GCE integral / a metal-poor extrapolation). The UPPER [Fe/H] edge is now a SOFT
    # per-output flag (CR-10.2 / CQ-7-3c-6): the fissile FRACTION is [Fe/H]-independent, so [Fe/H] > +0.5
    # must NOT void it — only the [Fe/H]-dependent K-40 radiogenic-heat channel is flagged extrapolated.
    if not (lo_a <= age_gyr <= hi_a):
        reasons.append(f"age {age_gyr} Gyr outside the GCE fit domain {[lo_a, hi_a]} (DV-5)")
        domain_out = True
    if feh is not None and feh < lo_f:
        reasons.append(f"[Fe/H] {feh} below the GCE fit domain (< {lo_f}) (DV-5)")
        domain_out = True
    if feh is not None and feh > _DV5_FEH_SOFT_UPPER:
        # Soft flag ONLY: no reason appended (domain_note stays for hard/veto issues), no domain_out, no
        # ratio/tonnage severity change, no bands entry (which would wrongly extrapolate-flag the ratio).
        feh_extrapolation = True

    # DV-2 — actinide-boost / r-II: production ratio is event-class-dependent → ratio AND tonnage void.
    if eu_fe is not None and eu_fe >= _DV2_EU_FE_ACTINIDE_BOOST:
        reasons.append("[Eu/Fe] ≳ +0.7 (actinide-boost / r-II): production ratio is event-class-dependent "
                       "— BOTH the U-235/U-238 ratio and the tonnage are unreliable (DV-2)")
        actinide_boost = True

    # DV-3 — [Eu/H] must be a genuine r-process tracer. Preferred: measured [Ba/Eu]; else the runbook
    # proxy (a high [Eu/Fe] on a thin-disk, non-metal-poor star is likely s-process/Ba pollution → the
    # Eu tracer over-states the r-process, so the [Eu/H]-scaled TONNAGE is unreliable; the ratio is not).
    if ba_eu is not None:
        if ba_eu >= _DV3_BA_EU_S_DOMINANCE:
            reasons.append(f"[Ba/Eu] {ba_eu} ≳ {_DV3_BA_EU_S_DOMINANCE}: s-process dominance — [Eu/H] "
                           "over-states the r-process → tonnage unreliable (DV-3)")
            s_process = True
    elif (eu_fe is not None and eu_fe >= _DV3_EU_FE_S_PROCESS
          and population == "thin" and feh is not None and feh >= _DV3_FEH_MIN):
        reasons.append(f"[Eu/Fe] ≳ +{_DV3_EU_FE_S_PROCESS} on a thin-disk [Fe/H]≳{_DV3_FEH_MIN} star: likely "
                       "s-process (AGB/Ba) pollution, not r-process — [Eu/H] over-states the r-process → "
                       "tonnage unreliable (DV-3 proxy; supply [Ba/Eu] to confirm)")
        s_process = True

    bands = []
    # CQ-7-3c-3 (DEFECT-3): boundaries were strict-inequality-holed — age exactly 4.0/8.0 and the
    # 11.5<A<11.55 sliver fell in NO band. Fixes: <= young edge, >= joint edge, ISM upper → D_eff (11.55).
    if age_gyr <= 4.0:
        bands.append("age ≲4 Gyr: young band (uniform-ψ biased high ~1.4–2.5×)")
    if 9.0 <= age_gyr <= 11.55:
        bands.append("age ~9–11.55 Gyr: ISM-mixing band (~±60% per-star)")
    if age_gyr >= 8.0:
        bands.append("age ≳8 Gyr: joint (P, D_eff) band, order-of-magnitude")
    # DV-1 — age_soft advisory (order-of-magnitude, NOT a veto).
    if age_soft:
        bands.append("age_soft: age is a population/[Fe/H] prior, not a measurement — the age-driven "
                     "fissile axis is order-of-magnitude (DV-1)")

    # Tri-state ok + per-output severities (CQ-7-3c-4). The radiogenic heat is an [Eu/H] abundance
    # consumer (DV-6), so it inherits the tonnage severity.
    if domain_out or actinide_boost:
        ok = False
    elif not eu_available:
        ok = None                       # DV-2/DV-3 cannot be evaluated without an r-process tracer
    elif s_process:
        ok = False
    else:
        ok = True
    ratio_sev = ("void" if (domain_out or actinide_boost)
                 else "unevaluable" if not eu_available
                 else "extrapolated" if bands else "ok")
    tonnage_sev = ("void" if (domain_out or actinide_boost)
                   else "unevaluable" if not eu_available
                   else "unreliable" if s_process
                   else "extrapolated" if bands else "ok")
    detail = {
        "domain_ok": ok,
        "reasons": reasons,
        "flags": {"age_soft": bool(age_soft), "s_process": s_process,
                  "actinide_boost": actinide_boost, "domain_out": domain_out,
                  "feh_extrapolation": feh_extrapolation},
        "per_output": {"isotope_ratio": ratio_sev, "tonnage": tonnage_sev,
                       "radiogenic_heat": tonnage_sev,
                       # CR-10.2 / CQ-7-3c-6: additive boolean (NOT a severity-string overwrite) — the
                       # [Fe/H]-dependent K-40 radiogenic-heat channel is extrapolated at [Fe/H] > +0.5.
                       "feh_extrapolation": feh_extrapolation},
        "bands": bands,
    }
    return ok, ("; ".join(reasons) if reasons else None), bands, detail
