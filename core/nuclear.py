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
  3. **radiogenic_heat_W_per_kg** — U+Th+K decay heat of a rocky body at the star's age. **The U/Th
     (r-process) channels scale with the star's [Eu/H]-driven GCE actinide inventory** relative to the
     BSE solar anchor (~5×10⁻¹² W/kg at solar), K-40 by a 10^[Fe/H] proxy; **withheld when no [Eu/H]
     tracer is given** (CQ-7-3c-1 / WB MSG 079 — no longer the Eu-blind co-formation form; see the
     ``radiogenic_heat`` detail block).

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


def _radiogenic_provenance(domain_detail):
    """Domain flags the radiogenic heat inherits (WB MSG 079: it is an [Eu/H] abundance consumer, DV-6)."""
    if not domain_detail:
        return None
    return {
        "severity": domain_detail["per_output"]["radiogenic_heat"],
        "domain_ok": domain_detail["domain_ok"],
        "inherits": ["DV-2", "DV-3", "DV-4", "DV-6"],
        "flags": domain_detail["flags"],
    }


def _radiogenic_heat(age_gyr, fe_h, eu_h, population=None, domain_detail=None):
    """U+Th+K decay-heat rate (W/kg of rock) at the star's age → detail dict.

    **CQ-7-3c-1 (WB MSG 079)** — the U-235/U-238/Th-232 (actinide, r-process) channels are scaled by
    the star's **actinide inventory relative to the solar anchor**,
    ``g_i(A)/g_i(solar) · exp(λ_i·(solar−A)) · 10^[Eu/H]`` — NOT by ``10^[Fe/H]`` (the old form was
    Eu-blind / co-formation, inverting DV-6). The decay term ``exp(λ_i·(solar−A))`` appears **once** (no
    double-count with the g-ratio). K-40 is **not** r-process → it keeps its ``10^[Fe/H]`` metallicity
    *proxy* + its own decay factor, labelled proxy-grade. When [Eu/H] is unavailable the actinide
    inventory is **not computable** → the heat is **withheld** (``value_W_per_kg=None``), never silently
    back-filled with ``10^[Fe/H]`` (that fallback IS the original defect). Returns
    ``{value_W_per_kg, computable, components_W_per_kg, actinide_scaling, note, provenance}``."""
    solar = nt._SOLAR_AGE_GYR
    comp = {}
    # K-40 — metallicity proxy (not r-process; outside the actinide inventory). 10^[Fe/H] + own decay.
    k_massfrac = nt._BSE["K_mass_frac"] * nt._PRESENT_ISO_FRAC["K40"]
    k_decay = math.exp(nt._LAMBDA_PER_GYR["K40"] * (solar - age_gyr))
    comp["K40"] = (10.0 ** fe_h) * k_massfrac * k_decay * nt._HEAT_W_PER_KG_ISOTOPE["K40"]

    if eu_h is None:
        for iso in ("U235", "U238", "Th232"):
            comp[iso] = None
        return {
            "value_W_per_kg": None,
            "computable": False,
            "components_W_per_kg": comp,
            "actinide_scaling": "withheld",
            "note": ("radiogenic heat WITHHELD: no r-process tracer ([Eu/H] or [Eu/Fe]) → the U/Th "
                     "actinide inventory is not computable; NOT back-filled with 10^[Fe/H] (that "
                     "co-formation fallback is the original Eu-blind defect — DV-6 / CQ-7-3c-1). "
                     f"K-40-only partial ≈ {comp['K40']:.3e} W/kg (the non-actinide channel, ~19% of the "
                     "BSE budget at solar; U/Th withheld) shown for reference."),
            "provenance": _radiogenic_provenance(domain_detail),
        }

    elem_of = {"U235": "U_mass_frac", "U238": "U_mass_frac", "Th232": "Th_mass_frac"}
    metal_actinide = 10.0 ** eu_h
    total = comp["K40"]
    for iso in ("U235", "U238", "Th232"):
        present_massfrac = nt._BSE[elem_of[iso]] * nt._PRESENT_ISO_FRAC[iso]
        # g_ratio: star's g_i vs the solar anchor (thin, [Eu/H]=0). pop/feh are passed to match
        # _fissile_block so the radiogenic and fissile paths stay on the SAME g_i if the model ever
        # becomes population/[Fe/H]-dependent (today gce_enrichment_factor uses age only → byte-identical).
        g_ratio = (nt.gce_enrichment_factor(iso, age_gyr, population=population, feh=fe_h)
                   / nt.gce_enrichment_factor(iso, solar, population="thin", feh=0.0))
        decay = math.exp(nt._LAMBDA_PER_GYR[iso] * (solar - age_gyr))
        comp[iso] = metal_actinide * g_ratio * present_massfrac * decay * nt._HEAT_W_PER_KG_ISOTOPE[iso]
        total += comp[iso]
    return {
        "value_W_per_kg": total,
        "computable": True,
        "components_W_per_kg": comp,
        "actinide_scaling": "eu_h_gce_actinide_inventory",
        "note": ("U/Th scaled by the [Eu/H]-driven GCE actinide inventory vs the solar anchor "
                 "(g_i(A)/g_i(solar)·exp(λ_i(solar−A))·10^[Eu/H]); K-40 by a 10^[Fe/H] proxy + own decay."),
        "provenance": _radiogenic_provenance(domain_detail),
    }


def compute_nuclear_inventory(fe_h, age_gyr, eu_h=None, eu_fe=None,
                              star_mass_solar=None, population=None,
                              ba_eu=None, age_soft=False):
    """Fusion + fissile + radiogenic inventory from stellar scalars. See module docstring.

    Inputs: ``fe_h`` (dex), ``age_gyr`` (Gyr), one of ``eu_h`` (dex) / ``eu_fe`` (dex) as the
    r-process tracer (absent → fissile AND radiogenic heat not computable, never fabricated), optional
    ``star_mass_solar``, optional ``population`` ∈ {thin, thick, halo} (the CR-7 verdict string),
    optional ``ba_eu`` ([Ba/Eu] dex — the preferred DV-3 s-process discriminant), optional
    ``age_soft`` (bool — DV-1: the age is a population/[Fe/H] prior, not a measurement). Returns
    ``{fusion, fissile, radiogenic_heat_W_per_kg, radiogenic_heat, provenance, inputs}`` or
    ``{"error": str}``.
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

    # [Eu/Fe] for the 3c DV-2/DV-3 domain checks: given directly, else [Eu/H] − [Fe/H].
    eu_fe_eff = eu_fe if eu_fe is not None else (
        resolved_eu_h - fe_h if resolved_eu_h is not None else None)
    domain_ok, domain_reason, domain_bands, domain_detail = nt.gce_domain_ok(
        age_gyr, fe_h, eu_fe=eu_fe_eff, population=population, ba_eu=ba_eu,
        age_soft=age_soft, eu_available=(resolved_eu_h is not None))
    radiogenic = _radiogenic_heat(age_gyr, fe_h, resolved_eu_h, population, domain_detail)
    return {
        "fusion": _fusion_block(fe_h, age_gyr),
        "fissile": _fissile_block(age_gyr, resolved_eu_h, fe_h, population),
        "radiogenic_heat_W_per_kg": radiogenic["value_W_per_kg"],   # back-compat headline (float | None)
        "radiogenic_heat": radiogenic,                              # CQ-7-3c-1 detail (Eu-wired + withhold)
        "provenance": {
            "gce_model_version": nt._GCE_MODEL["model_version"],
            "confidence": nt._GCE_MODEL["confidence"],
            "domain_ok": domain_ok,            # TRI-STATE True/False/None (CQ-7-3c-4)
            "domain_note": domain_reason,      # None when in-domain; ALL fired reasons joined otherwise
            "domain_reasons": domain_detail["reasons"],   # multi-reason list, no elif-shadowing (CQ-7-3c-4)
            "per_output": domain_detail["per_output"],    # isotope_ratio / tonnage / radiogenic_heat severity
            "flags": domain_detail["flags"],   # age_soft / s_process / actinide_boost / domain_out
            "bands": domain_bands,             # reduced-reliability regimes (young / ISM-mixing / old) +
                                               # the DV-1 age_soft advisory string when --age-soft is set
            "radiogenic_basis": "actinide inventory: U/Th scaled by the [Eu/H]-driven GCE abundance vs the "
                                "solar anchor, K-40 by 10^[Fe/H] proxy — BSE present-day anchor ~5e-12 W/kg "
                                "at solar (CQ-7-3c-1: no longer Eu-blind; withheld when [Eu/H] is absent)",
        },
        "inputs": {"fe_h": fe_h, "age_gyr": age_gyr, "eu_h": resolved_eu_h, "eu_fe": eu_fe,
                   "ba_eu": ba_eu, "age_soft": age_soft,
                   "star_mass_solar": star_mass_solar, "population": population},
    }
