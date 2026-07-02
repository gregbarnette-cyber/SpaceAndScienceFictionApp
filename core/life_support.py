"""Phase X — closed-loop life-support & bioregenerative calculators (``query.py``-only).

Three pure-arithmetic / energy-balance calculators for the sibling ``scifiWorldBuilding-Claude``
repo (Packet 15), all backed by the bundled BVAD Rev2 + crop/lighting reference data in
``core.life_support_tables``:

- ``compute_life_support`` (X1) — crew consumables/waste budget with closure-loop makeup mass.
- ``compute_bioregen_area`` (X2) — grow area + lighting power to feed a crew (PAR energy
  balance, with a BVAD measured-productivity cross-check; algae take the productivity path).
- ``compute_population_capacity`` (X3) — sustainable population from resource budgets, reporting
  the binding constraint.

Self-validating (Phase-H/P contract → curated ``{"error"}``). No GUI, no CLI menu, no DB, no
network, no RNG, no clock. Phase-N/T/U/V/W lineage; same JSON-out contract as the calculator
family. All bundled efficiencies are overridable (Mature-Technology Assumption).
"""

from core import life_support_tables as _t

_KCAL_TO_KJ = _t._KCAL_TO_KJ
_PAR_J_PER_UMOL = _t._PAR_J_PER_UMOL
_SEC_PER_DAY = 86400.0


# ── X1 ────────────────────────────────────────────────────────────────────────

def compute_life_support(crew=1, days=1,
                         water_closure=None, o2_closure=None, food_closure=None,
                         closure_scenario=None,
                         o2_rate=None, co2_rate=None, potable_water_rate=None,
                         total_water_rate=None, food_dry_rate=None, kcal_per_day=None,
                         solid_waste_rate=None, liquid_waste_rate=None):
    """Crew consumables/waste budget + closure-loop makeup mass (BVAD Rev2 rates).

    Every rate defaults to the bundled BVAD Rev2 per-crewmember daily value and is overridable.
    ``closure_scenario`` sets water/o2/food recycle fractions; per-stream ``*_closure`` overrides
    win. Returns the budget dict or ``{"error": str}``.
    """
    if crew <= 0:
        return {"error": "crew must be > 0."}
    if days <= 0:
        return {"error": "days must be > 0."}

    # ── per-person daily rates: start from BVAD Rev2, apply overrides ──
    rates = _t.get_bvad_rates()
    overrides = {
        "o2_kg": o2_rate, "co2_kg": co2_rate, "potable_water_kg": potable_water_rate,
        "total_water_kg": total_water_rate, "food_dry_kg": food_dry_rate, "kcal": kcal_per_day,
        "solid_waste_kg": solid_waste_rate, "liquid_waste_kg": liquid_waste_rate,
    }
    for key, val in overrides.items():
        if val is not None:
            if val <= 0:
                return {"error": f"{key} rate override must be > 0."}
            rates[key] = float(val)

    # ── closure fractions: scenario then per-stream override ──
    scenarios = _t.get_closure_scenarios()
    scenario_name = closure_scenario if closure_scenario is not None else "open"
    if scenario_name not in scenarios:
        return {"error": f"Unknown closure_scenario '{closure_scenario}'. "
                         f"Choose one of: {', '.join(sorted(scenarios))}."}
    closure = dict(scenarios[scenario_name])
    for stream, val in (("water", water_closure), ("o2", o2_closure), ("food", food_closure)):
        if val is not None:
            if not (0.0 <= val <= 1.0):
                return {"error": f"{stream}_closure must be in [0, 1]."}
            closure[stream] = float(val)

    # ── totals (× crew × days) and closure-loop makeup mass ──
    factor = crew * days
    totals = {k: v * factor for k, v in rates.items()}
    makeup = {
        "o2": rates["o2_kg"] * factor * (1.0 - closure["o2"]),
        "water": rates["total_water_kg"] * factor * (1.0 - closure["water"]),
        "food": rates["food_dry_kg"] * factor * (1.0 - closure["food"]),
    }
    makeup["total"] = makeup["o2"] + makeup["water"] + makeup["food"]

    return {
        "crew": crew,
        "days": days,
        "per_person_daily": dict(rates),
        "totals": totals,
        "closure": closure,
        "scenario": scenario_name,
        "makeup_mass_kg": makeup,
        "model_note": _t._MODEL_NOTE,
        "notes": _t._NOTES,
    }


# ── X2 ────────────────────────────────────────────────────────────────────────

def compute_bioregen_area(kcal_per_day=None, crew=1, crop=None,
                          ppfd_umol=None, photoperiod_h=16.0, dli_mol=None, par_wm2=None,
                          photo_efficiency=None, harvest_index=None,
                          artificial=False, led_par_efficiency=None, f_edible_energy=1.0):
    """Grow area + lighting power to feed a crew.

    Default area path is the PAR energy balance ``A = E_d / (PAR_energy · η_photo · HI ·
    f_edible)``; when a BVAD ``crop`` is named its measured edible productivity is reported as a
    cross-check (``area_m2_per_person_measured``). Algae crops take the productivity path as the
    primary area (no HI/PAR chain). Exactly one light anchor is required. Returns the dict or
    ``{"error": str}``.
    """
    kcal = 2500.0 if kcal_per_day is None else float(kcal_per_day)
    led_eff = _t._LED_PAR_EFF_DEFAULT if led_par_efficiency is None else float(led_par_efficiency)
    eta = _t._PHOTO_EFFICIENCY_DEFAULT if photo_efficiency is None else float(photo_efficiency)

    # ── scalar validation ──
    if kcal <= 0:
        return {"error": "kcal_per_day must be > 0."}
    if crew <= 0:
        return {"error": "crew must be > 0."}
    if not (0.0 < photoperiod_h <= 24.0):
        return {"error": "photoperiod_h must be in (0, 24]."}
    if not (0.0 < eta <= 1.0):
        return {"error": "photo_efficiency must be in (0, 1]."}
    if not (0.0 < led_eff <= 1.0):
        return {"error": "led_par_efficiency must be in (0, 1]."}
    if not (0.0 < f_edible_energy <= 1.0):
        return {"error": "f_edible_energy must be in (0, 1]."}

    # ── crop resolution ──
    crops = _t.get_crops()
    crop_row = None
    if crop is not None:
        if crop not in crops:
            return {"error": f"Unknown crop '{crop}'. Choose one of: {', '.join(sorted(crops))}."}
        crop_row = crops[crop]
    is_algae = crop_row is not None and crop_row["source_tag"] == "algae"

    # ── harvest index (energy-balance path needs one) ──
    hi = harvest_index
    if hi is None and crop_row is not None and crop_row["hi"] is not None:
        hi = crop_row["hi"]
    if hi is not None and not (0.0 < hi <= 1.0):
        return {"error": "harvest_index must be in (0, 1]."}
    if not is_algae and hi is None:
        return {"error": "harvest_index is required when no BVAD crop is given (energy-balance path)."}

    # ── light anchor (exactly one) → DLI [mol/m²·d] ──
    anchors = [a for a in (ppfd_umol, dli_mol, par_wm2) if a is not None]
    if len(anchors) != 1:
        return {"error": "Provide exactly one light anchor: ppfd_umol, dli_mol, or par_wm2."}
    if ppfd_umol is not None:
        if ppfd_umol <= 0:
            return {"error": "ppfd_umol must be > 0."}
        dli = ppfd_umol * photoperiod_h * 3600.0 / 1e6
    elif dli_mol is not None:
        if dli_mol <= 0:
            return {"error": "dli_mol must be > 0."}
        dli = float(dli_mol)
    else:
        if par_wm2 <= 0:
            return {"error": "par_wm2 must be > 0."}
        dli = par_wm2 * photoperiod_h * 3600.0 / _PAR_J_PER_UMOL / 1e6

    # PAR energy that must be delivered per m² per day [kJ/m²·d] and the equivalent PAR
    # irradiance averaged over the photoperiod [W/m²].
    par_energy_kj_m2 = dli * _PAR_J_PER_UMOL * 1000.0
    ppfd_echo = dli * 1e6 / (photoperiod_h * 3600.0)
    par_wm2_delivered = par_energy_kj_m2 * 1000.0 / (photoperiod_h * 3600.0)

    # ── area (per person, then × crew) ──
    demand_kj = kcal * _KCAL_TO_KJ
    area_measured = None
    if is_algae:
        # productivity path is primary for algae (no HI/PAR chain)
        edible_kj_m2 = crop_row["edible_dry_g_m2_d"] * crop_row["energy_density_kcal_g"] * _KCAL_TO_KJ
        area_pp = demand_kj / edible_kj_m2
        area_measured = area_pp
        hi = None
    else:
        area_pp = demand_kj / (par_energy_kj_m2 * eta * hi * f_edible_energy)
        if crop_row is not None:
            edible_kj_m2 = crop_row["edible_dry_g_m2_d"] * crop_row["energy_density_kcal_g"] * _KCAL_TO_KJ
            area_measured = demand_kj / edible_kj_m2
    area_total = area_pp * crew

    # ── lighting power (only when artificial) ──
    if artificial:
        par_power_pp_w = par_energy_kj_m2 * area_pp * 1000.0 / _SEC_PER_DAY
        elec_pp = par_power_pp_w / led_eff
        elec_total = elec_pp * crew
    else:
        elec_pp = None
        elec_total = None

    # ── gas exchange + transpiration (from the crop, over the total area) ──
    if crop_row is not None:
        gas = {
            "o2_kg_day": crop_row["o2_g_m2_d"] * area_total / 1000.0,
            "co2_kg_day": crop_row["co2_g_m2_d"] * area_total / 1000.0,
        }
        water_uptake = crop_row["water_uptake_kg_m2_d"]
        transpiration = None if water_uptake is None else water_uptake * area_total
    else:
        gas = {"o2_kg_day": None, "co2_kg_day": None}
        transpiration = None

    return {
        "kcal_per_day": kcal,
        "crew": crew,
        "crop": crop,
        "area_m2_per_person": area_pp,
        "area_m2_total": area_total,
        "area_m2_per_person_measured": area_measured,
        "dli_mol": dli,
        "ppfd_umol": ppfd_echo,
        "photoperiod_h": photoperiod_h,
        "photo_efficiency": None if is_algae else eta,
        "harvest_index": hi,
        "f_edible_energy": f_edible_energy,
        "lighting": {
            "artificial": artificial,
            "par_wm2_delivered": par_wm2_delivered,
            "electrical_power_w_per_person": elec_pp,
            "electrical_power_w_total": elec_total,
            "led_par_efficiency": led_eff,
        },
        "crop_gas_exchange": gas,
        "transpiration_water_kg_day": transpiration,
        "model_note": _t._MODEL_NOTE,
        "par_is_input_note": ("PAR is a caller-supplied light parameter, not resolved from a "
                              "star/spectral type (stellar-type-resolved PAR is Packet 18)."),
        "notes": _t._NOTES,
    }


# ── X3 ────────────────────────────────────────────────────────────────────────

def compute_population_capacity(crop_area_m2=None, power_w=None, water_kg_day=None,
                                fixed_nitrogen_kg_yr=None, food_dry_kg_day=None,
                                per_person_area_m2=None, per_person_power_w=None,
                                per_person_water_kg_day=None, per_person_nitrogen_kg_yr=None,
                                per_person_food_kg_day=None):
    """Sustainable population from resource budgets; reports the binding constraint.

    Any omitted per-person requirement is filled from a nominal X1 (BVAD water/food) / X2
    (area/power) run + the bundled per-person fixed-nitrogen figure; any flag overrides. Only
    resources with a supplied budget are evaluated. Returns the dict or ``{"error": str}``.
    """
    # ── per-person defaults (D3): derive area/power from a nominal X2, water/food from BVAD ──
    nominal_area = None
    nominal_power = None
    if per_person_area_m2 is None or per_person_power_w is None:
        bio = compute_bioregen_area(kcal_per_day=_t._BVAD_RATES["kcal"], crew=1, crop="wheat",
                                    dli_mol=30.0, artificial=True)
        nominal_area = bio["area_m2_per_person"]
        nominal_power = bio["lighting"]["electrical_power_w_per_person"]

    defaults = {
        "crop_area": nominal_area,
        "power": nominal_power,
        "water": _t._CONSUMPTION_WATER_KG,
        "fixed_nitrogen": _t._PER_PERSON_NITROGEN_KG_YR,
        "food": _t._BVAD_RATES["food_dry_kg"],
    }
    pp_flags = {
        "crop_area": per_person_area_m2,
        "power": per_person_power_w,
        "water": per_person_water_kg_day,
        "fixed_nitrogen": per_person_nitrogen_kg_yr,
        "food": per_person_food_kg_day,
    }
    budgets = {
        "crop_area": crop_area_m2,
        "power": power_w,
        "water": water_kg_day,
        "fixed_nitrogen": fixed_nitrogen_kg_yr,
        "food": food_dry_kg_day,
    }

    if all(v is None for v in budgets.values()):
        return {"error": "Provide at least one resource budget "
                         "(crop_area_m2, power_w, water_kg_day, fixed_nitrogen_kg_yr, food_dry_kg_day)."}

    per_resource = {}
    for key, budget in budgets.items():
        if budget is None:
            continue
        if budget <= 0:
            return {"error": f"{key} budget must be > 0."}
        if pp_flags[key] is not None:
            per_person = float(pp_flags[key])
            source = "flag"
        else:
            per_person = defaults[key]
            source = "default"
        if per_person is None or per_person <= 0:
            return {"error": f"per-person {key} requirement must be > 0."}
        per_resource[key] = {
            "budget": float(budget),
            "per_person": per_person,
            "source": source,
            "population": budget / per_person,
        }

    binding = min(per_resource, key=lambda k: per_resource[k]["population"])
    sustainable = per_resource[binding]["population"]
    slack = {k: v["population"] - sustainable for k, v in per_resource.items() if k != binding}

    return {
        "per_resource": per_resource,
        "sustainable_population": sustainable,
        "binding_constraint": binding,
        "slack": slack,
        "model_note": _t._MODEL_NOTE,
        "notes": _t._NOTES,
    }
