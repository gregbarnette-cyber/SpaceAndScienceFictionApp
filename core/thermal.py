"""Phase V — power / thermal / shielding calculators (Group F of the calculator-extensions
request; the pre-scope-lock prerequisite for Packet 13).

Three pure-math, self-validating (Phase-H/P contract) calculators modelling the *floor
physics* that no future engineering can repeal — the radiative-rejection and
attenuation limits — agnostic about mature-technology *implementation*:

  * ``compute_waste_heat``           (F1) — power → rejected-heat budget, with Carnot ceiling.
  * ``compute_radiator_area``        (F2) — Stefan–Boltzmann thermal-rejection wall.
  * ``compute_shielding_attenuation``(F3) — Lambert–Beer photon (exact) / GCR (order-of-mag).

No network, no DB, no RNG, no time. ``query.py``-only (no GUI). The Stefan–Boltzmann
constant lives in ``core.equations`` (with the other physical constants) so it can't
drift; the F3 coefficient tables live in ``core.shielding_tables`` (isolated, like
``core.cooling_tables``). Self-validating: bad input returns a curated ``{"error": str}``.
"""

import math

from core.equations import _STEFAN_BOLTZMANN
from core import shielding_tables


# ── F1 — waste-heat budget (with Carnot ceiling) ─────────────────────────────

def compute_waste_heat(input_power_watts=None, useful_power_watts=None,
                       efficiency=None, hot_temp_k=None, cold_temp_k=None,
                       peak_w=None, mean_w=None, duty=None, pulse_period_s=None,
                       storage_mass_kg=None, specific_heat_jkgk=None):
    """Waste heat a device must reject, given a power figure + an efficiency.

    Power anchor (exactly one): ``input_power_watts`` (gross input/thermal) OR
    ``useful_power_watts`` (net output). Efficiency anchor: ``efficiency`` (0<η≤1) OR a
    reservoir pair ``hot_temp_k``/``cold_temp_k`` (→ Carnot η). If both an explicit
    efficiency and the reservoir temps are given, the device waste heat uses ``efficiency``
    and the Carnot floor is reported alongside; ``carnot_limited`` flags a device whose
    stated efficiency exceeds the Carnot ceiling (physically impossible — flagged, still
    returned).

    C9 — transient/pulsed mode: supply ``peak_w``, ``mean_w``, ``duty`` (on-fraction),
    ``pulse_period_s``, ``storage_mass_kg`` and ``specific_heat_jkgk`` (all together) to size
    a thermal buffer. The radiator handles the time-average ``mean_w``; the excess
    (``peak_w − mean_w``) charges the buffer during the on-phase → per-cycle
    ``temp_swing_k`` and a ``buffer_time_s`` ride-through.
    """
    # ── C9 — transient/pulsed thermal-buffer mode ──
    transient = [peak_w, mean_w, duty, pulse_period_s, storage_mass_kg, specific_heat_jkgk]
    if any(v is not None for v in transient):
        if any(v is None for v in transient):
            return {"error": "Transient mode needs all of peak_w, mean_w, duty, pulse_period_s, "
                             "storage_mass_kg, specific_heat_jkgk."}
        if peak_w <= 0 or mean_w <= 0:
            return {"error": "peak_w and mean_w must be > 0."}
        if peak_w < mean_w:
            return {"error": "peak_w must be >= mean_w."}
        if not (0.0 < duty <= 1.0):
            return {"error": "duty must be in (0, 1]."}
        if pulse_period_s <= 0:
            return {"error": "pulse_period_s must be > 0."}
        if storage_mass_kg <= 0 or specific_heat_jkgk <= 0:
            return {"error": "storage_mass_kg and specific_heat_jkgk must be > 0."}
        on_time_s = duty * pulse_period_s
        excess_w = peak_w - mean_w
        heat_cap = storage_mass_kg * specific_heat_jkgk           # J/K
        temp_swing_k = excess_w * on_time_s / heat_cap
        # ride-through: how long the charged buffer covers the mean load if rejection stops
        buffer_time_s = heat_cap * temp_swing_k / mean_w if mean_w > 0 else None
        return {
            "mode": "transient",
            "peak_power_w": peak_w,
            "mean_power_w": mean_w,
            "duty": duty,
            "pulse_period_s": pulse_period_s,
            "on_time_s": on_time_s,
            "excess_power_w": excess_w,
            "storage_mass_kg": storage_mass_kg,
            "specific_heat_jkgk": specific_heat_jkgk,
            "heat_capacity_j_per_k": heat_cap,
            "buffered_energy_j": excess_w * on_time_s,
            "temp_swing_k": temp_swing_k,
            "buffer_time_s": buffer_time_s,
            "notes": ["Radiator sized for the time-average mean_w; the buffer absorbs the "
                      "(peak−mean) excess over each on-phase. temp_swing_k is the per-cycle "
                      "swing; buffer_time_s is the ride-through if rejection stops. Steady "
                      "refrigeration/pump work is out of scope (packet prose)."],
        }

    # ── power anchor ──
    if (input_power_watts is None) == (useful_power_watts is None):
        return {"error": "Provide exactly one of input_power_watts or useful_power_watts."}
    if input_power_watts is not None and input_power_watts <= 0:
        return {"error": "input_power_watts must be > 0."}
    if useful_power_watts is not None and useful_power_watts <= 0:
        return {"error": "useful_power_watts must be > 0."}

    # ── Carnot ceiling (optional) ──
    carnot_efficiency = None
    if hot_temp_k is not None or cold_temp_k is not None:
        if hot_temp_k is None or cold_temp_k is None:
            return {"error": "Provide both hot_temp_k and cold_temp_k for the Carnot ceiling."}
        if hot_temp_k <= 0 or cold_temp_k <= 0:
            return {"error": "hot_temp_k and cold_temp_k must be > 0."}
        if hot_temp_k <= cold_temp_k:
            return {"error": "hot_temp_k must be > cold_temp_k."}
        carnot_efficiency = 1.0 - cold_temp_k / hot_temp_k

    # ── efficiency anchor: explicit η, else derive from Carnot ──
    eta = efficiency
    if eta is None:
        if carnot_efficiency is None:
            return {"error": "Provide an efficiency, or hot_temp_k+cold_temp_k for the Carnot efficiency."}
        eta = carnot_efficiency
    elif not (0.0 < eta <= 1.0):
        return {"error": "efficiency must be in (0, 1]."}

    # ── device waste heat ──
    if input_power_watts is not None:
        p_in = input_power_watts
        p_useful = p_in * eta
        waste = p_in * (1.0 - eta)
    else:
        p_useful = useful_power_watts
        p_in = p_useful / eta
        waste = p_useful * (1.0 - eta) / eta

    # ── Carnot floor on unavoidable waste heat ──
    carnot_min_waste = None
    carnot_limited = None
    notes = []
    if carnot_efficiency is not None:
        carnot_min_waste = p_useful * cold_temp_k / (hot_temp_k - cold_temp_k)
        carnot_limited = eta > carnot_efficiency + 1e-12
        if carnot_limited:
            notes.append(
                "stated efficiency exceeds the Carnot ceiling — physically impossible device.")

    return {
        "waste_heat_w": waste,
        "useful_power_w": p_useful,
        "input_power_w": p_in,
        "efficiency": eta,
        "carnot_efficiency": carnot_efficiency,
        "carnot_min_waste_heat_w": carnot_min_waste,
        "carnot_limited": carnot_limited,
        "hot_temp_k": hot_temp_k,
        "cold_temp_k": cold_temp_k,
        "notes": notes,
        "model_note": ("Energy-balance efficiency split: waste = P·(1−η); when reservoir "
                       "temps are given, η is capped at the Carnot ceiling 1−T_cold/T_hot "
                       "(carnot_limited flags a stated η above it)."),
    }


# ── F2 — radiator area (Stefan–Boltzmann rejection wall) ─────────────────────

def compute_radiator_area(heat_watts=None, input_power_watts=None, efficiency=None,
                          radiator_temp_k=None, emissivity=0.9, sides=2,
                          sink_temp_k=0.0, areal_mass_kgm2=None):
    """Radiating area (and optional mass) needed to reject a heat load.

    Heat load: ``heat_watts`` directly, OR the F1 chain ``input_power_watts``+``efficiency``
    (→ Q = P_in·(1−η)). Net flux q = ε·σ·(T_rad⁴ − T_sink⁴)·n_sides; area A = Q/q. Exposes
    ``blackside_flux_wm2`` = σ·T_rad⁴ so the T⁴ dependence is legible.
    """
    # ── heat load anchor ──
    if heat_watts is not None and input_power_watts is not None:
        return {"error": "Provide either heat_watts or (input_power_watts + efficiency), not both."}
    if heat_watts is None:
        if input_power_watts is None or efficiency is None:
            return {"error": "Provide heat_watts, or input_power_watts + efficiency."}
        if input_power_watts <= 0:
            return {"error": "input_power_watts must be > 0."}
        if not (0.0 < efficiency <= 1.0):
            return {"error": "efficiency must be in (0, 1]."}
        heat_watts = input_power_watts * (1.0 - efficiency)
    if heat_watts <= 0:
        return {"error": "heat_watts must be > 0."}

    # ── radiator parameters ──
    if radiator_temp_k is None or radiator_temp_k <= 0:
        return {"error": "radiator_temp_k must be > 0."}
    if not (0.0 < emissivity <= 1.0):
        return {"error": "emissivity must be in (0, 1]."}
    if sides not in (1, 2):
        return {"error": "sides must be 1 or 2."}
    if sink_temp_k < 0:
        return {"error": "sink_temp_k must be >= 0."}
    if sink_temp_k >= radiator_temp_k:
        return {"error": "sink_temp_k must be < radiator_temp_k (a radiator cannot reject "
                         "below its environment temperature; net flux collapses to <= 0)."}

    blackside_flux = _STEFAN_BOLTZMANN * radiator_temp_k ** 4
    flux = emissivity * _STEFAN_BOLTZMANN * (radiator_temp_k ** 4 - sink_temp_k ** 4) * sides
    area_m2 = heat_watts / flux
    radiator_mass_kg = area_m2 * areal_mass_kgm2 if areal_mass_kgm2 is not None else None

    scaling_note = (
        "Radiator area scales as A ∝ T_rad⁻⁴ (halving the radiator temperature → 16× the "
        "area). Radiating hotter shrinks area but raising the engine's cold-reservoir "
        "temperature cuts its Carnot efficiency and so RAISES the heat Q to reject (couples "
        "to waste-heat F1). Net flux collapses to zero as sink_temp_k → radiator_temp_k."
    )

    return {
        "radiator_area_m2": area_m2,
        "radiator_area_km2": area_m2 / 1e6,
        "flux_wm2": flux,
        "blackside_flux_wm2": blackside_flux,
        "heat_watts": heat_watts,
        "radiator_temp_k": radiator_temp_k,
        "sink_temp_k": sink_temp_k,
        "emissivity": emissivity,
        "sides": sides,
        "radiator_mass_kg": radiator_mass_kg,
        "areal_mass_kgm2": areal_mass_kgm2,
        "scaling_note": scaling_note,
        "model_note": ("Gray-body Stefan–Boltzmann rejection: A = Q / (ε·σ·(T_rad⁴ − T_sink⁴)·sides). "
                       "Assumes uniform radiator temperature and a diffuse gray surface."),
    }


# ── F3 — shielding attenuation (Lambert–Beer photon / GCR order-of-mag) ──────

def _layer_transmitted(material, sigma, energy_mev, mode):
    """Per-layer transmitted fraction for the C7 multi-layer path → (frac, info) or {"error"}."""
    if sigma <= 0:
        return {"error": f"layer '{material}': areal density must be > 0."}
    if mode == "photon":
        if energy_mev is None:
            return {"error": "photon layers require --energy-mev for the bundled μ/ρ lookup."}
        found = shielding_tables.lookup_mu_rho(material, energy_mev)
        if found is None:
            return {"error": f"layer material '{material}' is not in the bundled XCOM table "
                             f"(have: {', '.join(shielding_tables.material_names())})."}
        mu_rho, chosen_e, exact = found
        frac = math.exp(-mu_rho * sigma)
        return frac, {"material": material, "areal_density_gcm2": sigma,
                      "mass_atten_coeff_cm2g": mu_rho, "energy_mev": chosen_e,
                      "energy_exact": exact, "transmitted_fraction": frac}
    lam = shielding_tables.lookup_gcr_lambda(material)
    if lam is None:
        return {"error": f"layer material '{material}' has no bundled GCR attenuation length "
                         f"(have: {', '.join(shielding_tables.gcr_material_names())})."}
    frac = math.exp(-sigma / lam)
    return frac, {"material": material, "areal_density_gcm2": sigma,
                  "attenuation_length_gcm2": lam, "transmitted_fraction": frac}


def _parse_layers(spec):
    """Parse a C7 --layers spec → list of (material, areal_density_gcm2) or {"error"}.

    Accepts a string "mat:gcm2, mat:gcm2, …" or an already-parsed list of (material, σ) pairs.
    """
    if isinstance(spec, (list, tuple)):
        out = []
        for item in spec:
            try:
                mat, sigma = item
                out.append((str(mat), float(sigma)))
            except (TypeError, ValueError):
                return {"error": f"malformed layer entry {item!r} (want (material, areal_density))."}
        if not out:
            return {"error": "layers is empty."}
        return out
    layers = []
    for tok in str(spec).split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.count(":") != 1:
            return {"error": f"malformed --layers token '{tok}' (want 'material:areal_density_gcm2')."}
        mat, s = tok.split(":")
        mat = mat.strip()
        if not mat:
            return {"error": f"malformed --layers token '{tok}' (empty material)."}
        try:
            sigma = float(s.strip())
        except ValueError:
            return {"error": f"malformed --layers token '{tok}' (areal density not a number)."}
        layers.append((mat, sigma))
    if not layers:
        return {"error": "--layers is empty."}
    return layers


def compute_shielding_attenuation(areal_density_gcm2=None, thickness_cm=None,
                                  density_gcm3=None, mass_atten_coeff_cm2g=None,
                                  attenuation_length_gcm2=None, material=None,
                                  energy_mev=None, mode="photon", particle="photon",
                                  csda_range_gcm2=None, layers=None):
    """Transmitted fraction + half/tenth-value layers through a shield.

    Photon mode (default, exact): I/I₀ = exp(−(μ/ρ)·Σ), HVL = ln2/(μ/ρ), TVL = ln10/(μ/ρ).
    GCR mode (order-of-magnitude): D/D₀ = exp(−Σ/Λ), with a mandatory buildup caveat.

    Thickness via ``areal_density_gcm2`` OR ``thickness_cm``+``density_gcm3`` (Σ = ρ·x).
    Coefficient via an explicit value, OR ``material``+``energy_mev`` bundled lookup.

    C6 — ``particle`` ∈ {photon, proton, alpha, ion}: a charged particle takes the CSDA-range
    path (a hard stopping depth, not exponential attenuation) via the bundled NIST PSTAR table
    (proton/water) or an explicit ``csda_range_gcm2``. C7 — ``layers`` (a "mat:gcm2, …" spec or
    list) computes a stacked-shield transmitted fraction (photon/GCR) as the per-layer product.
    """
    if mode not in ("photon", "gcr"):
        return {"error": "mode must be 'photon' or 'gcr'."}
    if particle not in ("photon",) + shielding_tables._CHARGED_PARTICLES:
        return {"error": "particle must be one of photon, proton, alpha, ion."}

    # ── C7 — multi-layer stack (photon/GCR) ──
    if layers is not None:
        parsed = _parse_layers(layers)
        if isinstance(parsed, dict):
            return parsed
        layer_out = []
        total = 1.0
        for mat, sigma in parsed:
            res = _layer_transmitted(mat, sigma, energy_mev, mode)
            if isinstance(res, dict):
                return res
            frac, info = res
            total *= frac
            layer_out.append(info)
        return {
            "mode": mode,
            "layers": layer_out,
            "total_transmitted_fraction": total,
            "total_attenuation": 1.0 / total,
            "total_areal_density_gcm2": sum(s for _, s in parsed),
            "is_order_of_magnitude": (mode == "gcr"),
            "model_note": (shielding_tables._XCOM_SOURCE if mode == "photon"
                           else shielding_tables._GCR_SOURCE),
        }

    # ── areal density Σ ──
    if areal_density_gcm2 is not None and (thickness_cm is not None or density_gcm3 is not None):
        return {"error": "Provide either areal_density_gcm2, or thickness_cm + density_gcm3, not both."}
    if areal_density_gcm2 is not None:
        if areal_density_gcm2 <= 0:
            return {"error": "areal_density_gcm2 must be > 0."}
        sigma = areal_density_gcm2
    else:
        if thickness_cm is None or density_gcm3 is None:
            return {"error": "Provide areal_density_gcm2, or both thickness_cm and density_gcm3."}
        if thickness_cm <= 0 or density_gcm3 <= 0:
            return {"error": "thickness_cm and density_gcm3 must be > 0."}
        sigma = density_gcm3 * thickness_cm

    # ── C6 — charged particle: CSDA range (hard stopping depth, not attenuation) ──
    if particle in shielding_tables._CHARGED_PARTICLES:
        if csda_range_gcm2 is not None:
            if csda_range_gcm2 <= 0:
                return {"error": "csda_range_gcm2 must be > 0."}
            rng = float(csda_range_gcm2)
            csda_material = None
            csda_energy = energy_mev
            csda_exact = None
        else:
            if energy_mev is None or energy_mev <= 0:
                return {"error": "Provide energy_mev (> 0) for the bundled CSDA-range lookup, "
                                 "or an explicit csda_range_gcm2."}
            if material is None:
                return {"error": "Provide material (+ energy_mev) for the bundled CSDA-range "
                                 "lookup, or an explicit csda_range_gcm2."}
            found = shielding_tables.lookup_csda_range(particle, material, energy_mev)
            if found is None:
                have = shielding_tables.csda_material_names(particle)
                have_str = ", ".join(have) if have else "(none)"
                return {"error": f"no bundled CSDA range for {particle} in '{material}' "
                                 f"(bundled {particle} materials: {have_str}). Supply an "
                                 f"explicit --csda-range-gcm2."}
            rng, csda_energy, csda_exact = found
            csda_material = material
        csda_notes = []
        if csda_exact is False:
            csda_notes.append(f"energy {energy_mev} MeV not on the grid; used nearest "
                              f"{csda_energy} MeV.")
        stops = sigma >= rng
        out = {
            "mode": "csda",
            "particle": particle,
            "material": csda_material,
            "energy_mev": csda_energy,
            "energy_exact": csda_exact,
            "areal_density_gcm2": sigma,
            "csda_range_gcm2": rng,
            "residual_range_gcm2": max(rng - sigma, 0.0),
            "stops_primary": stops,
            "penetrates": not stops,
            "is_order_of_magnitude": False,
            "model_note": shielding_tables._PSTAR_SOURCE,
            "buildup_caveat": ("CSDA is a hard range cutoff for the PRIMARY only; secondary "
                               "particles (spallation neutrons/fragments) produced in the shield "
                               "are not modelled — hand off to a transport code for dose behind "
                               "a stopping shield."),
        }
        if thickness_cm is not None:
            out["thickness_cm"] = thickness_cm
            out["density_gcm3"] = density_gcm3
            out["csda_range_cm"] = rng / density_gcm3
        out["notes"] = csda_notes
        return out

    out = {
        "areal_density_gcm2": sigma,
        "material": None,
        "energy_mev": None,
        "energy_exact": None,
        "mode": mode,
    }
    notes = []

    if mode == "photon":
        # coefficient: explicit μ/ρ, else bundled lookup by material + energy
        if mass_atten_coeff_cm2g is not None:
            if mass_atten_coeff_cm2g <= 0:
                return {"error": "mass_atten_coeff_cm2g must be > 0."}
            mu_rho = mass_atten_coeff_cm2g
        else:
            if material is None or energy_mev is None:
                return {"error": "Provide mass_atten_coeff_cm2g, or material + energy_mev "
                                 "for the bundled NIST XCOM lookup."}
            if energy_mev <= 0:
                return {"error": "energy_mev must be > 0."}
            found = shielding_tables.lookup_mu_rho(material, energy_mev)
            if found is None:
                return {"error": f"material '{material}' is not in the bundled XCOM table "
                                 f"(have: {', '.join(shielding_tables.material_names())})."}
            mu_rho, chosen_e, exact = found
            out["material"] = material
            out["energy_mev"] = chosen_e
            out["energy_exact"] = exact
            if not exact:
                notes.append(f"energy {energy_mev} MeV not on the grid; used nearest {chosen_e} MeV.")
            if shielding_tables._MATERIAL_ALIASES.get(material, material) == "liquid_h2":
                notes.append(shielding_tables._PER_GRAM_NOTE)
            if shielding_tables._MATERIAL_ALIASES.get(material, material) == "regolith":
                notes.append(shielding_tables._REGOLITH_NOTE)

        transmitted = math.exp(-mu_rho * sigma)
        hvl = math.log(2.0) / mu_rho
        tvl = math.log(10.0) / mu_rho
        out.update({
            "transmitted_fraction": transmitted,
            "attenuation_factor": 1.0 / transmitted,
            "half_value_layer_gcm2": hvl,
            "tenth_value_layer_gcm2": tvl,
            "mass_atten_coeff_cm2g": mu_rho,
            "model_note": shielding_tables._XCOM_SOURCE,
            "buildup_caveat": "Narrow-beam (Lambert–Beer); broad-beam geometry adds "
                              "unmodeled photon buildup.",
            "is_order_of_magnitude": False,
        })
        if thickness_cm is not None:
            out["thickness_cm"] = thickness_cm
            out["density_gcm3"] = density_gcm3
            out["half_value_layer_cm"] = hvl / density_gcm3
            out["tenth_value_layer_cm"] = tvl / density_gcm3

    else:  # gcr
        if attenuation_length_gcm2 is not None:
            if attenuation_length_gcm2 <= 0:
                return {"error": "attenuation_length_gcm2 must be > 0."}
            lam = attenuation_length_gcm2
        else:
            if material is None:
                return {"error": "Provide attenuation_length_gcm2, or material for the "
                                 "bundled GCR lookup."}
            lam = shielding_tables.lookup_gcr_lambda(material)
            if lam is None:
                return {"error": f"material '{material}' has no bundled GCR attenuation "
                                 f"length (have: {', '.join(shielding_tables.gcr_material_names())})."}
            out["material"] = material
        transmitted = math.exp(-sigma / lam)
        out.update({
            "transmitted_fraction": transmitted,
            "attenuation_factor": 1.0 / transmitted,
            "attenuation_length_gcm2": lam,
            "model_note": shielding_tables._GCR_SOURCE,
            "buildup_caveat": shielding_tables._GCR_BUILDUP_CAVEAT,
            "is_order_of_magnitude": True,
        })
        if thickness_cm is not None:
            out["thickness_cm"] = thickness_cm
            out["density_gcm3"] = density_gcm3

    out["notes"] = notes
    return out
