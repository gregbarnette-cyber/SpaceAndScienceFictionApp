"""core/nuclear.py — CR-4: nuclear-fuel & radiogenic inventory (multi-output, pure-math).

Self-validating (Phase-H/P contract: curated ``{"error"}`` → exit 1). No network, no DB. One call
emits three outputs from Hypatia-available scalars ([Fe/H], age, [Eu/H], mass):

  1. **fusion**  — D/H, ³He, ⁶Li/⁷Li/¹¹B natal-gas estimates (order-of-magnitude; Li/B suffer stellar
     depletion not modelled).
  2. **fissile** — present U-235/U-238/Th-232 fractions + U-235/U-238 ratio, via the **per-isotope**
     Interface-A GCE model (WB **3c FINAL**, integrated 2026-08-15): per isotope
     ``N_i/N_Eu = (i_over_Eu)_prod × g_i(age,pop,feh) × exp(−λ_i·age)`` — the age-dependent g_i carry
     the formation-epoch offset, so decaying production alone (which gives ~0.030, not 0.00725) is not
     what happens. Absolute U/Th (from [Eu/H]) are additive so "r-process-poor → lower absolute U/Th"
     is expressible.
  3. **radiogenic_heat_W_per_kg** — U+Th+K decay heat of a rocky body at the star's age, scaled by
     10^[Fe/H] and back-decayed from the BSE present-day anchor (~5×10⁻¹² W/kg at solar).

The 3c FINAL model bundle is consumed through ``nuclear_tables._GCE_MODEL`` (the WB-delivered
per-isotope bundle, `3c-v1.0.0`); a future WB revision swaps that one constant with no code change.
"""

import math

import core.nuclear_tables as nt


def _fusion_block(fe_h, age_gyr):
    """Natal-gas fusion-fuel abundances from [Fe/H] (order-of-magnitude, tagged extrapolation)."""
    z_rel = 10.0 ** fe_h                       # Z/Z_sun proxy
    d_over_h = nt._PRIMORDIAL_D_H * max(0.5, 1.0 - nt._D_ASTRATION_SLOPE * z_rel)
    he3 = nt._PRIMORDIAL_HE3_H * (1.0 + nt._HE3_METAL_SLOPE * z_rel)
    a_li7 = min(nt._LI7_SOLAR, nt._LI7_PLATEAU + (nt._LI7_SOLAR - nt._LI7_PLATEAU) * z_rel)
    a_li6 = a_li7 + math.log10(nt._LI6_OVER_LI7)
    a_b11 = nt._B11_SOLAR + fe_h               # GCE ~1:1 with [Fe/H]
    return {
        "D_over_H": d_over_h,
        "He3_est": he3,
        "Li6": a_li6,
        "Li7": a_li7,
        "B11": a_b11,
        "units": {"D_over_H": "number ratio", "He3_est": "number ratio (³He/H)",
                  "Li6": "A(X)=12+log10(N/H) dex", "Li7": "A(X) dex", "B11": "A(X) dex"},
        "provenance": "extrapolation (natal-gas trends; Li/B stellar depletion not modelled)",
        "note": "primordial anchors are BBN (D/H 2.53e-5), not protosolar",
    }


def _fissile_block(age_gyr, eu_h, fe_h, population):
    """Present U/Th isotopic inventory via the per-isotope Interface-A GCE model."""
    if eu_h is None:
        return {
            "U235_frac": None, "U238_frac": None, "Th232_frac": None, "U235_U238_ratio": None,
            "note": "no r-process tracer ([Eu/H] or [Eu/Fe]) provided — fissile inventory not computable",
        }
    pr = nt._GCE_MODEL["production_ratios"]
    lam = nt._LAMBDA_PER_GYR
    n = {}                                     # present N_i / N_Eu, per isotope
    for iso, key in (("U235", "U235_over_Eu"), ("U238", "U238_over_Eu"), ("Th232", "Th232_over_Eu")):
        g = nt.gce_enrichment_factor(iso, age_gyr, population=population, feh=fe_h)
        n[iso] = pr[key] * g * math.exp(-lam[iso] * age_gyr)
    u_total = n["U235"] + n["U238"]
    actinide = u_total + n["Th232"]
    # Absolute U/Th from [Eu/H] (additive — lets "r-process-poor → lower absolute U/Th" be expressed).
    eu_over_h = 10.0 ** (nt._EU_SOLAR_DEX + eu_h - 12.0)
    u_over_h = u_total * eu_over_h
    th_over_h = n["Th232"] * eu_over_h
    return {
        "U235_frac": n["U235"] / u_total,          # isotopic fraction of uranium
        "U238_frac": n["U238"] / u_total,
        "Th232_frac": n["Th232"] / actinide,       # Th fraction of the U+Th actinide inventory
        "U235_U238_ratio": n["U235"] / n["U238"],
        "u_over_h": u_over_h,                       # additive absolute abundances (number ratios)
        "th_over_h": th_over_h,
        "a_u": 12.0 + math.log10(u_over_h) if u_over_h > 0 else None,
        "a_th": 12.0 + math.log10(th_over_h) if th_over_h > 0 else None,
        "units": {"*_frac": "dimensionless", "U235_U238_ratio": "number ratio",
                  "u_over_h": "number ratio (U/H)", "a_u": "A(X)=12+log10(N/H) dex"},
        "definitions": {"U235_frac": "N235/(N235+N238) isotopic",
                        "Th232_frac": "N232/(N235+N238+N232) actinide-inventory"},
    }


def _radiogenic_heat(age_gyr, fe_h):
    """U+Th+K decay-heat rate (W/kg of rock) at the star's age (BSE-anchored, 10^[Fe/H]-scaled)."""
    total = 0.0
    elem_of = {"U235": "U_mass_frac", "U238": "U_mass_frac",
               "Th232": "Th_mass_frac", "K40": "K_mass_frac"}
    metal = 10.0 ** fe_h
    for iso in ("U235", "U238", "Th232", "K40"):
        present_massfrac = nt._BSE[elem_of[iso]] * nt._PRESENT_ISO_FRAC[iso]
        age_factor = math.exp(nt._LAMBDA_PER_GYR[iso] * (nt._SOLAR_AGE_GYR - age_gyr))
        total += metal * present_massfrac * age_factor * nt._HEAT_W_PER_KG_ISOTOPE[iso]
    return total


def compute_nuclear_inventory(fe_h, age_gyr, eu_h=None, eu_fe=None,
                              star_mass_solar=None, population=None):
    """Fusion + fissile + radiogenic inventory from stellar scalars. See module docstring.

    Inputs: ``fe_h`` (dex), ``age_gyr`` (Gyr), one of ``eu_h`` (dex) / ``eu_fe`` (dex) as the
    r-process tracer (absent → fissile not computable, never null), optional ``star_mass_solar``,
    optional ``population`` ∈ {thin, thick, halo} (the CR-7 verdict string). Returns
    ``{fusion, fissile, radiogenic_heat_W_per_kg, provenance, inputs}`` or ``{"error": str}``.
    """
    if age_gyr is None or age_gyr <= 0:
        return {"error": "age_gyr must be positive."}
    if fe_h is None:
        return {"error": "fe_h ([Fe/H], dex) is required."}
    if eu_fe is not None and eu_h is not None:
        return {"error": "Provide only one of --eu-h / --eu-fe."}
    if star_mass_solar is not None and star_mass_solar <= 0:
        return {"error": "star_mass_solar must be positive."}
    if population is not None and population not in ("thin", "thick", "halo"):
        return {"error": "population must be one of thin / thick / halo."}

    resolved_eu_h = eu_h if eu_h is not None else (
        eu_fe + fe_h if eu_fe is not None else None)

    # [Eu/Fe] for the 3c DV-2 domain check: given directly, else [Eu/H] − [Fe/H].
    eu_fe_eff = eu_fe if eu_fe is not None else (
        resolved_eu_h - fe_h if resolved_eu_h is not None else None)
    domain_ok, domain_reason, domain_bands = nt.gce_domain_ok(age_gyr, fe_h, eu_fe=eu_fe_eff)
    return {
        "fusion": _fusion_block(fe_h, age_gyr),
        "fissile": _fissile_block(age_gyr, resolved_eu_h, fe_h, population),
        "radiogenic_heat_W_per_kg": _radiogenic_heat(age_gyr, fe_h),
        "provenance": {
            "gce_model_version": nt._GCE_MODEL["model_version"],
            "confidence": nt._GCE_MODEL["confidence"],
            "domain_ok": domain_ok,
            "domain_note": domain_reason,      # None when in-domain; the DV-2/domain reason otherwise
            "bands": domain_bands,             # reduced-reliability regimes (young / ISM-mixing / old)
            "radiogenic_basis": "bulk-silicate-Earth present-day anchor (~5e-12 W/kg at solar)",
        },
        "inputs": {"fe_h": fe_h, "age_gyr": age_gyr, "eu_h": resolved_eu_h,
                   "eu_fe": eu_fe, "star_mass_solar": star_mass_solar, "population": population},
    }
