"""Phase X — bundled closed-loop life-support reference data (isolated static tables).

Transcribed (not fitted) from the authoritative current edition of NASA's Baseline Values
and Assumptions Document — **BVAD Rev2** (NASA/TP-2015-218570/REV2, Feb 2022), Tables 3-31
(human metabolic loads), 4-20 (water balance), 4-90 (crop harvest index + edible dry
productivity) and 4-91 (crop gas exchange + water uptake). Isolated in its own module (like
``core.spin_tables`` / ``core.cooling_tables`` / ``core.shielding_tables``) so the numbers
have a single provenance-stamped home and every rate stays caller-overridable.

Algae (chlorella / spirulina) are **not** in BVAD — their rows carry a separate provenance
line (``_ALGAE_SOURCE``) from the ESA MELiSSA loop and the closed-photobioreactor microalgae
literature, and are flagged ``source_tag="algae"`` so a consumer never mistakes them for the
BVAD crop set.

Per the Mature-Technology Assumption (MTA), the bundled efficiencies are **present-day
ancestors, not 2,500-yr ceilings** — every rate/efficiency is overridable at the call site.
"""

# ── unit constants ───────────────────────────────────────────────────────────
_KCAL_TO_KJ = 4.184                 # thermochemical kcal → kJ
# PAR photon energy at 550 nm, first principles h·c·N_A/λ = 217.7 kJ/mol = 0.2177 J/µmol.
_PAR_J_PER_UMOL = 0.2177
# Wall-plug → PAR efficacy of a defensible present-day mid-grade horticultural LED fixture
# (~1.9 µmol/J). Modern top fixtures reach ~3.0–3.5 µmol/J (η≈0.65), so 0.4 is conservative.
_LED_PAR_EFF_DEFAULT = 0.4
# Crop biomass energy captured per unit incident PAR energy (biomass-energy / PAR-energy).
# Derived from a canonical controlled-environment radiation-use efficiency: wheat canopy RUE
# ≈ 1.35 g dry biomass / mol PAR × ~17 kJ/g biomass ÷ 217.7 kJ/mol PAR ≈ 0.105. This is a
# PAR-referenced figure (crops are ~3% of *total incident solar*, but PAR is only ~45% of
# solar and controlled-environment absorption is high, so the PAR-referenced value is ~3×).
# Calibrated: at DLI 30 mol/m²·d, wheat HI 0.40, 2500 kcal/day the energy-balance area lands
# at ~40 m²/person — matching both the 30–50 m² acceptance anchor and the BVAD measured
# edible-productivity cross-check (~37 m²).
_PHOTO_EFFICIENCY_DEFAULT = 0.10

# ── X1: BVAD Rev2 per-crewmember daily rates (Table 3-31 / 4-20) ─────────────
# Keys mirror the compute_life_support per_person_daily output keys.
_BVAD_RATES = {
    "o2_kg": 0.895,             # O₂ consumed, Table 3-31
    "co2_kg": 1.085,            # CO₂ produced, Table 3-31 (RQ 0.860)
    "potable_water_kg": 2.0,    # drinking water, Table 3-31 / 4-20
    "total_water_kg": 9.12,     # total incl. full hygiene, Mature Planetary Base, Table 4-20
    "food_dry_kg": 0.800,       # food solids (dry), Table 3-31
    "kcal": 3054.0,             # food energy 12.778 MJ ≈ 3054 kcal, Table 3-31
    "solid_waste_kg": 0.120,    # dry metabolic solids: fecal 0.032 + urine 0.061 + persp 0.027
    "liquid_waste_kg": 4.467,   # water outputs: urine 1.420 + fecal 0.101 + resp+persp 2.946
}

# Total human water consumption (drink + food rehydration), Table 4-20 — the metabolic-floor
# default used for the X3 population-capacity per-person water requirement.
_CONSUMPTION_WATER_KG = 2.50

# ── X1: closure scenarios (documented estimates, flagged approximate) ────────
# Fraction of each stream recovered/recycled; makeup mass = rate·(1−closure).
_CLOSURE_SCENARIOS = {
    "open":     {"water": 0.0,  "o2": 0.0,  "food": 0.0},   # no recycling
    "iss":      {"water": 0.90, "o2": 0.42, "food": 0.0},   # ISS ECLSS approx
    "advanced": {"water": 0.98, "o2": 0.75, "food": 0.0},   # advanced physico-chemical
    "bioregen": {"water": 0.98, "o2": 0.98, "food": 0.90},  # bioregenerative loop
}

# ── X2: crops (BVAD Rev2 Table 4-90 HI + edible dry productivity; 4-91 gas + water) ─
# Algae rows are NOT BVAD — separate provenance (_ALGAE_SOURCE), flagged source_tag="algae":
# edible_dry_g_m2_d = nominal areal productivity (~20–30 g/m²·d, mid 25); gas exchange from a
# nominal photosynthetic quotient (~1.6 g O₂ / 1.9 g CO₂ per g dry biomass); no HI (all
# biomass edible) and no transpiration water-uptake regime (culture medium, not soil).
_CROPS = {
    "wheat":        {"hi": 0.40, "edible_dry_g_m2_d": 20.00, "o2_g_m2_d": 56.00, "co2_g_m2_d": 77.00, "water_uptake_kg_m2_d": 11.79, "energy_density_kcal_g": 3.40, "source_tag": "bvad"},
    "white_potato": {"hi": 0.70, "edible_dry_g_m2_d": 21.06, "o2_g_m2_d": 32.23, "co2_g_m2_d": 45.23, "water_uptake_kg_m2_d": 4.00,  "energy_density_kcal_g": 3.55, "source_tag": "bvad"},
    "sweet_potato": {"hi": 0.60, "edible_dry_g_m2_d": 24.70, "o2_g_m2_d": 41.12, "co2_g_m2_d": 56.54, "water_uptake_kg_m2_d": 2.88,  "energy_density_kcal_g": 3.60, "source_tag": "bvad"},
    "soybean":      {"hi": 0.40, "edible_dry_g_m2_d": 4.54,  "o2_g_m2_d": 13.91, "co2_g_m2_d": 19.13, "water_uptake_kg_m2_d": 4.70,  "energy_density_kcal_g": 4.40, "source_tag": "bvad"},
    "lettuce":      {"hi": 0.90, "edible_dry_g_m2_d": 6.57,  "o2_g_m2_d": 7.78,  "co2_g_m2_d": 10.70, "water_uptake_kg_m2_d": 2.10,  "energy_density_kcal_g": 2.50, "source_tag": "bvad"},
    "chlorella":    {"hi": None, "edible_dry_g_m2_d": 25.00, "o2_g_m2_d": 40.00, "co2_g_m2_d": 48.00, "water_uptake_kg_m2_d": None,  "energy_density_kcal_g": 3.80, "source_tag": "algae"},
    "spirulina":    {"hi": None, "edible_dry_g_m2_d": 25.00, "o2_g_m2_d": 40.00, "co2_g_m2_d": 48.00, "water_uptake_kg_m2_d": None,  "energy_density_kcal_g": 3.85, "source_tag": "algae"},
}

# ── X3: bundled per-person fixed-nitrogen demand (documented nominal, cited) ──
# Dietary protein nitrogen floor: ~13 g N/day (≈80 g protein/day × 16% N) ≈ 4.7 kg N/yr;
# rounded to 5.0 kg N/person·yr as a nominal agricultural fixed-nitrogen requirement. Flagged
# approximate — real closed-loop N demand depends on crop N-use efficiency and recovery.
_PER_PERSON_NITROGEN_KG_YR = 5.0

# ── provenance strings (cited in results + docs/integration.md) ──────────────
_BVAD_SOURCE = ("NASA BVAD Rev2 (NASA/TP-2015-218570/REV2, Feb 2022), Tables 3-31, 4-20, "
                "4-90, 4-91.")
_CROP_SOURCE = ("Crop harvest index, edible dry productivity, gas exchange and water uptake "
                "from BVAD Rev2 Tables 4-90/4-91 (Wheeler et al. MEC crop models; Drysdale 2001).")
_ALGAE_SOURCE = ("Microalgae (chlorella/spirulina) NOT in BVAD: nominal areal productivity "
                 "~20–30 g/m²·d, energy density ~3.8 kcal/g, ~60% protein from the ESA MELiSSA "
                 "loop and closed-photobioreactor microalgae literature.")
_LIGHTING_SOURCE = ("PAR photon energy h·c·N_A/550nm = 0.2177 J/µmol (first principles); "
                    "horticultural LED wall-plug→PAR efficacy ~1.9 µmol/J (η≈0.4), modern "
                    "~3.0–3.5 µmol/J (Nature s41438-020-0283-7).")

_MODEL_NOTE = (
    "Human metabolic/water/waste loads and crop productivity are BVAD Rev2 "
    "(NASA/TP-2015-218570/REV2, Feb 2022) — the exercising ~82 kg reference astronaut set "
    "(3054 kcal/day; the older 2500 kcal sedentary set is reachable via --kcal-per-day). Per "
    "the Mature-Technology Assumption these are present-day ANCESTOR values, not 2,500-yr "
    "ceilings; every rate, closure fraction and efficiency is overridable. Closure fractions "
    "(open/iss/advanced/bioregen) are documented estimates, flagged approximate. Algae rows "
    "are not BVAD (separate provenance)."
)

_NOTES = (
    "Steady-state, single-crop-or-mix-by-parameter model. Trace nutrients, full soil "
    "chemistry, multi-crop diet optimization, microbial ecology, transient/seasonal dynamics "
    "and closed-loop failure modes are out of scope (packet prose). Radiator sizing / "
    "waste-heat rejection for grow lighting is handled by Phase V (waste-heat, radiator-area) "
    "— X2 reports the electrical/PAR load and hands heat off."
)


def get_bvad_rates():
    """Return a fresh copy of the BVAD Rev2 per-crewmember daily rate dict."""
    return dict(_BVAD_RATES)


def get_crops():
    """Return a fresh copy of the crop table (each value a fresh dict)."""
    return {k: dict(v) for k, v in _CROPS.items()}


def get_closure_scenarios():
    """Return a fresh copy of the closure-scenario table (each value a fresh dict)."""
    return {k: dict(v) for k, v in _CLOSURE_SCENARIOS.items()}
