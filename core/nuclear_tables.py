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


def gce_domain_ok(age_gyr, feh, eu_fe=None, model=_GCE_MODEL):
    """3c FINAL domain rules → ``(ok: bool, reason: str|None, bands: list[str])``.

    ``domain_ok=false`` when age is outside [0, 13.6] Gyr, [Fe/H] outside [-2.5, 0.5], or **[Eu/Fe]
    ≳ +0.7** (actinide-boost / r-II star — the production ratio is event-class-dependent, so BOTH the
    U-235/U-238 ratio AND the tonnage are unreliable, DV-2). ``bands`` flags reduced-reliability
    regimes (young / ISM-mixing / old joint band, DV-4/DV-7) as additive metadata; central values are
    still emitted (flag, never clamp)."""
    dom = model["gce_enrichment"]["domain"]
    lo_f, hi_f = dom["feh_range"]
    lo_a, hi_a = dom["age_range_gyr"]
    reason = None
    if not (lo_a <= age_gyr <= hi_a):
        reason = f"age {age_gyr} Gyr outside the GCE fit domain {[lo_a, hi_a]}"
    elif feh is not None and not (lo_f <= feh <= hi_f):
        reason = f"[Fe/H] {feh} outside the GCE fit domain {[lo_f, hi_f]}"
    elif eu_fe is not None and eu_fe >= 0.7:
        reason = ("[Eu/Fe] ≳ +0.7 (actinide-boost / r-II): production ratio is event-class-dependent "
                  "— BOTH the U-235/U-238 ratio and the tonnage are unreliable")
    bands = []
    if age_gyr < 4.0:
        bands.append("age ≲4 Gyr: young band (uniform-ψ biased high ~1.4–2.5×)")
    if 9.0 <= age_gyr <= 11.5:
        bands.append("age ~9–11.5 Gyr: ISM-mixing band (~±60% per-star)")
    if age_gyr > 8.0:
        bands.append("age ≳8 Gyr: joint (P, D_eff) band, order-of-magnitude")
    return (reason is None), reason, bands
