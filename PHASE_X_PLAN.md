# PHASE_X_PLAN.md — Closed-Loop Life-Support & Bioregenerative Calculators

**Status:** Planned — awaiting go-ahead to implement.
**Designation:** Phase X (next free letter after Phase W `spin-comfort`).
**Consumer:** sibling repo `scifiWorldBuilding-Claude`, Packet 15.
**Request spec:** `scifiWorldBuilding-Claude/research/query-api-methods/closed-loop-life-support-calculator-request.md`.

Three new **`query.py`-only** subcommands — **`life-support`** (X1), **`bioregen-area`** (X2),
**`population-capacity`** (X3). Pure arithmetic / energy-balance math + one bundled static reference
table. **No GUI, no CLI menu, no DB, no network, no RNG.** Phase-N/T/U/V/W lineage. Same JSON-out /
`{"error"}`+exit-1 / argparse-exit-2 / self-validating (Phase-H/P) contract as the rest of the
calculator family.

---

## 0. Verification result (done 2026-07-02 — primary sources read)

The spec's bundled figures are an **older BVAD edition**. Verified against the authoritative current
edition **NASA BVAD Rev2 (NASA/TP-2015-218570/REV2, Feb 2022)**, Tables 3-31 / 4-20 / 4-90 / 4-91
(PDF read directly). **We bundle Rev2 verbatim** (transcribe-not-fitted), echo the edition, flag the
delta in `model_note`, and let the caller override every rate.

| X1 stream | spec assumed | **BVAD Rev2 (bundle this)** | table |
|---|---|---|---|
| O₂ consumed | 0.816 | **0.895** kg/CM·d | 3-31 |
| CO₂ produced | 1.0 | **1.085** kg/CM·d (RQ 0.860) | 3-31 |
| Food solids (dry) | 0.617 | **0.800** kg/CM·d | 3-31 |
| Food energy | 2500 kcal | **12.778 MJ ≈ 3054 kcal** | 3-31 |
| Drinking water | 2.0 | **2.00** kg/CM·d | 3-31 / 4-20 |
| Potable water content | — | **3.217** (2.0 drink + 0.5 food-prep + 0.717 exercise) | 3-31 |
| Total human consumption | — | **2.50** kg/CM·d (drink + food rehydration) | 4-20 |
| **Total water incl. full hygiene** | **26 (WRONG)** | **9.12** kg/CM·d (Mature Planetary Base; ~15 w/ medical) | 4-20 |
| Urine / fecal / resp+persp water | — | **1.420 / 0.101 / 2.946** kg/CM·d | 3-31 |
| Fecal / urine / perspiration solids (dry) | — | **0.032 / 0.061 / 0.027** kg/CM·d | 3-31 |
| Metabolic water (internal) | — | **0.490** kg/CM·d | 3-31 |

**Crops (X2)** — BVAD Rev2 directly bundles the spec's crops (Table 4-90 HI + edible dry
productivity; Table 4-91 gas exchange + water uptake):

| Crop | HI % | Edible dry [g dw/m²·d] | O₂ [g/m²·d] | CO₂ [g/m²·d] | Water uptake [kg/m²·d] |
|---|---|---|---|---|---|
| Wheat | 40 | 20.0 | 56.0 | 77.0 | 11.79 |
| White Potato | 70 | 21.06 | 32.23 | 45.23 | 4.00 |
| Sweet Potato | 60 | 24.7 | 41.12 | 56.54 | 2.88 |
| Soybean | 40 | 4.54 | 13.91 | 19.13 | 4.70 |
| Lettuce | 90 | 6.57 | 7.78 | 10.70 | 2.10 |

**Algae (chlorella/spirulina) are NOT in BVAD** → separate provenance line from MELiSSA / closed-PBR
literature: areal productivity ~20–30 g/m²·d nominal (range 5–52), energy density ~3.8 kcal/g,
~60 % protein. Tagged `_ALGAE_SOURCE`, flagged distinct from the BVAD crop rows.

**Lighting (X2)** — PAR photon energy at 550 nm confirmed by first principles
`h·c·N_A/λ = 217.7 kJ/mol = 0.2177 J/µmol`. LED default `η_led = 0.4` (≈1.9 µmol/J wall-plug→PAR
efficacy — defensible present-day mid value; modern top fixtures ~3.0–3.5 µmol/J → η≈0.65, so 0.4 is
conservative). `DLI = PPFD·photoperiod_s / 1e6` standard.

**Edible energy density [kcal/g dry]** (standard food-composition, bundled per crop): wheat 3.40,
white potato 3.55, sweet potato 3.60, soybean 4.40, lettuce 2.50, chlorella 3.80, spirulina 3.85.

---

## 1. Design decisions (baked in; all overridable)

- **D1 — X1 default kcal:** bundle **Rev2's 3054 kcal** exercising-82-kg-reference set as the default
  (authoritative, cited). The older 2500 kcal sedentary set is reachable via `--kcal-per-day 2500`
  and `--<stream>-rate`. `model_note` states the "exercising reference astronaut, present-day
  ancestor (MTA)" caveat.
- **D2 — X2 area method:** default to the spec's **PAR energy-balance chain**
  `A = E_d / (PAR_daily_energy_per_m2 · η_photo · HI · f_edible_energy)`; BVAD's measured edible
  productivity is bundled as a **cross-check field** (`area_m2_per_person_measured`) and is the sole
  path for algae (areal-productivity × energy-density). Both reported; neither silently hidden.
- **D3 — X3 calls X1/X2 internally** for per-person defaults (spec open-item 4, "recommended"): if a
  per-person requirement flag is omitted, derive it from a nominal X1 (BVAD) / X2 run; any flag
  overrides. Echo which came from defaults vs. flags.
- **D4 — closure scenarios** bundled as documented estimates (cited, flagged approximate):
  `open` 0/0/0 · `iss` water 0.90 / O₂ 0.42 / food 0 · `advanced` water 0.98 / O₂ 0.75 / food 0 ·
  `bioregen` water 0.98 / O₂ 0.98 / food 0.90. Per-stream `--*-closure` flags override the scenario.
- **D5 — hard Pkt-18 boundary:** `bioregen-area` **rejects** any `--star`/`--spectral-type`
  (argparse: those flags do not exist; a stray attempt fails as unknown-arg exit 2). PAR is a
  caller-supplied parameter, echoed with `par_is_input_note`.

---

## 2. Files

**New**
- `core/life_support_tables.py` — isolated bundled data (provenance header naming BVAD Rev2 + the
  MELiSSA/PBR algae sources + the lighting/energy references). Exports:
  `_BVAD_RATES` (dict, Rev2 per-person daily), `_CLOSURE_SCENARIOS` (dict of dicts),
  `_CROPS` (dict: HI, edible_dry_g_m2_d, o2_g_m2_d, co2_g_m2_d, water_uptake_kg_m2_d,
  energy_density_kcal_g, source_tag), `_PAR_J_PER_UMOL = 0.2177`, `_LED_PAR_EFF_DEFAULT = 0.4`,
  `_KCAL_TO_KJ = 4.184`, `_BVAD_SOURCE`/`_CROP_SOURCE`/`_ALGAE_SOURCE`/`_LIGHTING_SOURCE` strings,
  `_MODEL_NOTE`, `_NOTES`. Accessors `get_bvad_rates()`, `get_crops()`, `get_closure_scenarios()`.
- `core/life_support.py` — `compute_life_support(...)`, `compute_bioregen_area(...)`,
  `compute_population_capacity(...)`. Reuse `core/equations.py` constants; add none unless the plan
  finds drift (none expected — all constants live in the tables module).
- `tests/test_life_support.py` — in-process core suite.
- `tests/test_query_life_support.py` — subprocess `query.py` contract (mirrors `test_query_spin.py`).

**Edited**
- `query.py` — `import core.life_support as life_support`; three `cmd_*` handlers; three argparse
  subparsers; the X2 light-anchor required-mutex group.
- `docs/integration.md` — three quick-reference rows + a full contract-by-reference section
  (units on every field, BVAD **Rev2** edition + provenance).
- `docs/gui-architecture.md` — one Phase X completion row (query.py-only), Phase-U/V/W style.

No edits to any GUI, CLI menu, DB, or network module.

---

## 3. Function contracts

### X1 — `compute_life_support(crew=1, days=1, water_closure=None, o2_closure=None, food_closure=None, closure_scenario=None, o2_rate=None, co2_rate=None, potable_water_rate=None, total_water_rate=None, food_dry_rate=None, kcal_per_day=None, solid_waste_rate=None, liquid_waste_rate=None)`

- **Rates:** start from `_BVAD_RATES`; each `--*-rate` overrides its field. `--kcal-per-day` scales
  the food-energy field only (not mass; mass has its own override).
- **Closure:** `closure_scenario` sets water/o2/food fractions from `_CLOSURE_SCENARIOS`; any explicit
  `--*-closure` overrides that stream. Default scenario `open` (all 0) if neither given.
- **Math:** `totals[x] = rate[x]·crew·days`; `makeup[x] = rate[x]·crew·days·(1−closure[x])`
  (water/o2/food streams; `makeup.total = o2+water+food`).
- **Output:** `{crew, days, per_person_daily:{o2_kg, co2_kg, potable_water_kg, total_water_kg,
  food_dry_kg, kcal, solid_waste_kg, liquid_waste_kg}, totals:{…×crew×days}, closure:{water, o2,
  food}, makeup_mass_kg:{o2, water, food, total}, scenario, model_note}`. Echo inputs.
- **Validation:** `crew>0`, `days>0`, every rate `>0` if overridden, each closure ∈ [0,1], scenario ∈
  `_CLOSURE_SCENARIOS` → else curated `{"error"}`.

### X2 — `compute_bioregen_area(kcal_per_day=None, crew=1, crop=None, ppfd_umol=None, photoperiod_h=16, dli_mol=None, par_wm2=None, photo_efficiency=None, harvest_index=None, artificial=False, led_par_efficiency=0.4, f_edible_energy=1.0)`

- **Demand:** `E_d [kJ/day] = (kcal_per_day or 2500)·crew·_KCAL_TO_KJ`.
- **Light (exactly one anchor):** `--ppfd-umol` (+`--photoperiod-h`) → `dli = ppfd·photoperiod_h·3600/1e6`;
  or `--dli-mol`; or `--par-wm2` → `dli = par_wm2·photoperiod_h·3600/1e6 / _PAR_J_PER_UMOL·1e-6…`
  (convert W/m² PAR → mol/m²·d via the 0.2177 J/µmol). `PAR_daily_energy_per_m2 [kJ/m²·d] =
  dli·_PAR_J_PER_UMOL·1000`.
- **Area (energy-balance, default):** `A = E_d / (PAR_daily_energy_per_m2 · η_photo · HI ·
  f_edible_energy)`. `η_photo` default 0.03 (biomass-energy/incident-PAR), `HI` default from `--crop`
  (Table 4-90) else required. **Cross-check:** `area_measured = E_d /
  (edible_dry_g_m2_d · energy_density_kcal_g · _KCAL_TO_KJ)` when `--crop` given.
- **Algae mode** (`--crop chlorella|spirulina`): area from areal productivity × energy density only
  (no HI/PAR chain); still reports gas exchange.
- **Lighting power** (`--artificial`): `P_light_per_person [W] = PAR_energy_delivered_over_area /
  η_led`, `PAR_energy_delivered_over_area = PAR_daily_energy_per_m2·A / 86400·1000`; `×crew` for total.
  Omit `--artificial` → `electrical_power_* = null` (natural/concentrated-light habitat).
- **Gas/water** (from `--crop`, scaled by area): `crop_gas_exchange:{o2_kg_day, co2_kg_day}`,
  `transpiration_water_kg_day`.
- **Output:** `{kcal_per_day, crew, crop, area_m2_per_person, area_m2_total,
  area_m2_per_person_measured, dli_mol, ppfd_umol, photoperiod_h, photo_efficiency, harvest_index,
  lighting:{artificial, par_wm2_delivered, electrical_power_w_per_person, electrical_power_w_total,
  led_par_efficiency}, crop_gas_exchange:{o2_kg_day, co2_kg_day}, transpiration_water_kg_day,
  model_note, par_is_input_note}`.
- **Validation:** exactly one light anchor (argparse required-mutex → exit 2); `kcal_per_day>0`,
  `crew>0`, `photoperiod_h ∈ (0,24]`, `photo_efficiency ∈ (0,1]`, `harvest_index ∈ (0,1]`,
  `led_par_efficiency ∈ (0,1]`, `f_edible_energy ∈ (0,1]`, `crop ∈ _CROPS` → else curated `{"error"}`.
  **No `--star`/`--spectral-type`.**

### X3 — `compute_population_capacity(crop_area_m2=None, power_w=None, water_kg_day=None, fixed_nitrogen_kg_yr=None, food_dry_kg_day=None, per_person_area_m2=None, per_person_power_w=None, per_person_water_kg_day=None, per_person_nitrogen_kg_yr=None, per_person_food_kg_day=None)`

- **Per-person defaults (D3):** omitted requirements filled from a nominal X1 (BVAD water/food) / X2
  run (area/power); fixed-nitrogen default from a documented per-person figure (bundled, cited);
  any flag overrides. Track `source` (`default`|`flag`) per resource.
- **Math:** for each resource `R` with a supplied budget, `pop_R = budget_R / per_person_R`;
  `sustainable_population = min pop_R`; `binding_constraint = argmin`; `slack[R] = pop_R −
  sustainable_population` for non-binding R. Resources with no budget are omitted (not zero).
- **Output:** `{per_resource:{crop_area:{budget, per_person, source, population}, power:{…}, water:{…},
  fixed_nitrogen:{…}, food:{…}}, sustainable_population, binding_constraint, slack:{…}, model_note}`.
- **Validation:** at least one resource budget supplied; every supplied budget `>0` and every
  per-person requirement `>0` → else curated `{"error"}`.

---

## 4. Test plan

### `tests/test_life_support.py` (in-process, offline)

- **Bundled-table integrity:** `_BVAD_RATES` matches the Rev2 values in §0 exactly; `_CROPS` HI/
  productivity/gas/water rows match Table 4-90/4-91; energy densities present for every crop;
  `_PAR_J_PER_UMOL` within 1e-4 of the recomputed `h·c·N_A/550nm`; closure scenarios in [0,1].
- **X1 anchors:** per person / open / 1 day → `o2_kg≈0.895`, `co2_kg≈1.085`, `food_dry_kg≈0.800`,
  `kcal≈3054`, `potable_water_kg≈2.0`. `--kcal-per-day 2500` scales energy, not O₂. `crew=6, days=180`
  scales linearly. `--closure-scenario iss --days 365` → water makeup ≈ 0.10× the open-loop water
  total (0.90 recycle); `open` makeup == total.
- **X1 overrides:** `--o2-rate 0.816 --food-dry-rate 0.617 --kcal-per-day 2500` reproduces the older
  textbook set exactly (proves override path).
- **X2 anchors:** 2500 kcal/day, DLI≈30 mol/m²·d, `η_photo=0.03`, wheat HI 0.40 → `area_m2_per_person`
  lands in **30–50 m²** (spec anchor). `--artificial --led-par-efficiency 0.4` →
  `electrical_power_w_per_person` in **5,000–15,000 W** (spec anchor). PPFD↔DLI↔PAR-W/m² parity
  (three light anchors that describe the same light give the same area). `--crop chlorella` → smaller
  area than wheat at equal demand. `par_is_input_note` present; `area_m2_per_person_measured` within a
  factor ~2 of the energy-balance area for the BVAD crops (sanity, not equality — different models).
- **X3 anchors:** `--power-w 1e6 --per-person-power-w 1e4` → `sustainable_population==100`,
  `binding_constraint=="power"`. Add a tight `--fixed-nitrogen-kg-yr` budget → binding flips to
  `"fixed_nitrogen"`; slack reported on the others. D3: omitting a per-person flag pulls the BVAD/X2
  default and marks `source=="default"`.
- **Validation matrix** (each → `{"error"}`): non-positive crew/days/area/power/rate; closure ∉ [0,1];
  photo_efficiency/HI/led_par_efficiency/f_edible_energy ∉ (0,1]; unknown crop; unknown scenario;
  zero light anchors / two light anchors in X2 (in-process the mutex is enforced too); no resource
  budget in X3.
- **Determinism:** same args → deep-equal output (no RNG, no clock).

### `tests/test_query_life_support.py` (subprocess, offline; `test_query_spin.py` harness)

- `_run("life-support", "--crew", "6", "--days", "180")` → exit 0, JSON parses, core-parity with the
  in-process call; the three X1/X2/X3 anchors above reproduced through the subprocess.
- **Exit-code matrix:** curated `{"error"}` exit 1 (non-positive crew/days; closure out of range;
  unknown crop/scenario; no X3 budget); **argparse exit 2** (missing required group, two X2 light
  anchors [`--ppfd-umol` + `--dli-mol`], bad `--crop`/`--closure-scenario` choice value, non-numeric
  value, an attempted `--star`/`--spectral-type` on `bioregen-area` → unknown-arg exit 2).
- `SPACE_APP_DB` throwaway env is set for parity with the family even though these read no DB.

Target: full offline suite, no network, no Qt (`QT_QPA_PLATFORM=offscreen` not even needed).

---

## 5. Validation contract (self-validating — Phase-H/P)

| Condition | Result | Exit |
|---|---|---|
| Success | result dict on stdout | 0 |
| Non-positive crew/days/area/power/rate; closure ∉ [0,1]; efficiency/HI ∉ (0,1]; unknown crop/scenario; no X3 budget | curated `{"error": str}` on stdout | 1 |
| Missing required arg/group; non-numeric; bad `--crop`/`--closure-scenario` choice; two X2 light anchors; `--star`/`--spectral-type` on X2 | argparse message on stderr | 2 |

Key on `"error"` + exit code, never on message text.

---

## 6. Success criteria (acceptance)

1. **X1** per person / open / 1 day: `o2_kg≈0.895`, `co2_kg≈1.085`, `potable_water_kg≈2.0`,
   `food_dry_kg≈0.800`, `kcal≈3054` (BVAD Rev2); `--closure-scenario iss --days 365` water makeup
   ≪ open-loop total; `--o2-rate 0.816 --kcal-per-day 2500` reproduces the older set.
2. **X2** 2500 kcal/day plant diet at DLI≈30 → **30–50 m²/person**; `--artificial
   --led-par-efficiency 0.4` → **5–15 kW/person**; three light anchors agree; `--crop chlorella` gives
   a smaller area; `par_is_input_note` present; **no `--star` accepted**.
3. **X3** `--power-w 1e6 --per-person-power-w 1e4` → ~100 (power-bound); a tight nitrogen budget →
   `binding_constraint=="fixed_nitrogen"`; slack reported.
4. Both test files pass offline; `python query.py <sub> …` matches in-process core; exit-code matrix
   holds.
5. `docs/integration.md` documents all three subcommands contract-by-reference (units on every field,
   **BVAD Rev2** edition + the 0.2177/0.4 provenance + the corrected ~9 kg water figure); one
   `docs/gui-architecture.md` Phase-X completion row; `model_note` in every result names BVAD Rev2 +
   the MTA "present-day ancestor" caveat.
6. No regression: full existing test suite still green; no GUI/CLI/DB/network file touched.

---

## 7. Out of scope / deferred (from the spec)

- Stellar-type-resolved PAR & photosynthesis-under-red-light → **Packet 18** (enters later as *inputs*,
  never a `--star` mode here).
- Nitrogen/water scarcity magnitudes & cosmochemistry → `canon/volatile-resource-geography.md` (tool
  does the demand side; reports which resource binds).
- Radiator sizing / waste-heat rejection for grow-lighting → already Phase V (`waste-heat`,
  `radiator-area`); X2 reports the power/PAR load and hands heat off.
- Microbial ecology, closed-loop failure modes, quarantine, agricultural politics, psychology → packet
  prose.
- Trace nutrients, full soil chemistry, multi-crop diet optimization, transient/seasonal dynamics →
  v1 is steady-state single-crop-or-mix by parameter; noted in output.

---

## 8. Provenance sources (cite in code + integration.md)

- **BVAD Rev2** — NASA/TP-2015-218570/REV2 (Feb 2022), Tables 3-31, 4-20, 4-90, 4-91.
- **Crops** — Wheeler et al. (BVAD MEC crop models) via Table 4-90/4-91; Drysdale 2001.
- **Algae** — ESA MELiSSA loop; closed-PBR microalgae productivity literature; standard microalgae
  food-composition (spirulina/chlorella ~3.8 kcal/g, ~60 % protein).
- **Lighting** — PAR photon energy `h·c·N_A/550nm = 0.2177 J/µmol` (first principles); horticultural
  LED wall-plug→PAR efficacy ~1.9 µmol/J (η≈0.4), modern ~3.0–3.5 µmol/J (Nature s41438-020-0283-7).
- **MTA caveat** — bundled efficiencies are present-day ancestors, not 2,500-yr ceilings; every
  parameter overridable.
