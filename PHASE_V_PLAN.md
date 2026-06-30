# Phase V — Power / Thermal / Shielding Calculators (`waste-heat` / `radiator-area` / `shielding-attenuation`)

Three new **`query.py`-only**, **pure-math**, self-validating calculators (the Phase-H/P
contract) plus **one isolated bundled constant table** (photon mass-attenuation
coefficients transcribed from NIST XCOM). Fulfils **Group F** of
`calculator-extensions-request.md`, specced in
`scifiWorldBuilding-Claude/research/query-api-methods/power-thermal-shielding-calculator-request.md`
(status *Proposed*; this is the **pre-scope-lock prerequisite for Packet 13**).

These model the **floor physics** — the radiative-rejection and attenuation limits no
future engineering can repeal. They are agnostic about mature-tech *implementation*
(droplet radiators, active heat pumps, magnetic deflection); the calculator gives the
present-day-physics **bound**, the packet prose develops how 2,500-yr engineering
approaches it.

**Lineage:** identical structure to **Phase U (`cooling-hz`)** — new core module +
isolated bundled data table + granular subcommands + **no GUI** (one completion row in
`docs/gui-architecture.md`, query.py-only). No network, no DB, no RNG, no time.

---

## Resolved implementer decisions (the request's four open items)

1. **GCR mode → SHIPPED in v1** (not photon-only). The `exp(−Σ/Λ)` formula is one line;
   Packet 13's shielding wall names cosmic rays as load-bearing; and the mode's real value
   is its mandatory `buildup_caveat` + `is_order_of_magnitude:true` fields, which exist
   precisely to stop a consumer trusting thin-shield GCR attenuation. Precedent: the
   already-shipped order-of-magnitude `tidal-heating` / `kozai-lidov`.
2. **Module home → new `core/thermal.py`** (F1–F3 functions) **+ new
   `core/shielding_tables.py`** (the bundled XCOM μ/ρ grid + GCR Λ values), mirroring the
   `core/cooling.py` / `core/cooling_tables.py` split. The lone constant `_STEFAN_BOLTZMANN`
   goes in `core/equations.py` (with `_G` etc.) so σ can't drift — per the request.
3. **Bundled XCOM grid → adopt the spec's grid as plan-of-record**: materials
   `{water, polyethylene, aluminum, regolith, lead, liquid_h2, iron}` × energies
   `{0.1, 0.5, 1, 2, 5, 10} MeV`; nearest-energy lookup with the chosen energy echoed +
   flagged when not exact; off-grid `--material`/`--energy-mev` → curated error. Two
   build-time caveats pinned now: **`regolith`** needs XCOM compound/mixture mode over a
   stated lunar-mare-analog silicate composition (recorded in the table provenance comment,
   not left implicit); **`liquid_h2`/`hydrogen`** (Z=1) gets an output note that its
   shielding edge is per-*gram*, not per-*cm* (the canonical best-mass / worst-volume case).
4. **F1→F2 chaining → `radiator-area` accepts the inline chain** (`--heat-watts` *or*
   `--input-power-watts`+`--efficiency`, computing `Q = P_in·(1−η)` internally) so F2 is
   usable standalone.

---

## 1. Files touched

| File | Change |
|---|---|
| `core/equations.py` | **+1 constant** in the module constants block: `_STEFAN_BOLTZMANN = 5.670374419e-8`  (W·m⁻²·K⁻⁴, CODATA). Nothing else. |
| `core/thermal.py` *(new)* | `compute_waste_heat` (F1), `compute_radiator_area` (F2), `compute_shielding_attenuation` (F3). Imports `_STEFAN_BOLTZMANN` from `equations`; imports the table module for F3. |
| `core/shielding_tables.py` *(new)* | `_XCOM_MU_RHO` (photon μ/ρ grid, transcribed from NIST XCOM) + `_GCR_LAMBDA` (attenuation lengths) + `_XCOM_SOURCE` / `_GCR_SOURCE` provenance strings + lookup helpers. Isolated like `cooling_tables.py`. |
| `query.py` | `import core.thermal as thermal`; 3 `cmd_*` handlers + 3 `add_parser` blocks (modeled on the `cooling-hz` block). |
| `tests/test_thermal.py` *(new)* | In-process core tests + table-integrity (HVL/TVL ↔ μ/ρ closure, anchor checks). |
| `tests/test_query_thermal.py` *(new)* | Subprocess contract: happy-path JSON + parity + exit-code matrix. |
| `docs/integration.md` | New "Power / Thermal / Shielding (Phase V)" section + 3 quick-reference rows; units on every field. |
| `docs/gui-architecture.md` | One Phase-V completion-status row (query.py-only, no GUI). |
| `CLAUDE.md` | Phase-V test bullet + `core/thermal.py` / `core/shielding_tables.py` note in the `core/` package list. |

---

## 2. Bundled data (sourced, not fabricated)

### `core/shielding_tables.py` — photon μ/ρ (NIST XCOM)

```python
_XCOM_SOURCE = (
    "NIST XCOM (Berger et al., NIST Standard Reference Database 8) / "
    "NIST XAAMDI (Hubbell & Seltzer); mass-attenuation coeff μ/ρ [cm²/g]."
)
# _XCOM_MU_RHO[material][energy_mev] = mu_over_rho_cm2_g
# Materials: water, polyethylene, aluminum, regolith, lead, liquid_h2 (alias hydrogen), iron
# Energies (MeV): 0.1, 0.5, 1.0, 2.0, 5.0, 10.0
# regolith := XCOM compound mode over a lunar-mare-analog silicate (composition in the
#   provenance comment); transcribe/verify each value against §10 anchors at build.
```

Every transcribed value is anchor-checked at build (water @1 MeV → HVL≈9.8 cm; see §10).
The closure `HVL = ln2/(μ/ρ)`, `TVL = ln10/(μ/ρ)` is asserted in `test_thermal.py` (a
mistranscribed μ/ρ breaks the HVL anchor), mirroring Phase U's table-closure test.

### GCR attenuation lengths Λ

```python
_GCR_SOURCE = "NCRP Report 153 / NASA HRP space-radiation references (order-of-magnitude Λ)."
# _GCR_LAMBDA[material] = lambda_gcm2  for water/polyethylene/aluminum/regolith
```

Explicitly order-of-magnitude; users may override via `--attenuation-length-gcm2`.

---

## 3. Core API (`core/thermal.py`)

```python
def compute_waste_heat(input_power_watts=None, useful_power_watts=None,
                       efficiency=None, hot_temp_k=None, cold_temp_k=None) -> dict
def compute_radiator_area(heat_watts=None, input_power_watts=None, efficiency=None,
                          radiator_temp_k=None, emissivity=0.9, sides=2,
                          sink_temp_k=0.0, areal_mass_kgm2=None) -> dict
def compute_shielding_attenuation(areal_density_gcm2=None, thickness_cm=None,
                                  density_gcm3=None, mass_atten_coeff_cm2g=None,
                                  attenuation_length_gcm2=None, material=None,
                                  energy_mev=None, mode="photon") -> dict
```

---

## 4. Physics / algorithm per calculator

### F1 `waste-heat`
- Power anchor (mutex, one required): `input_power_watts` (gross) **or** `useful_power_watts` (net).
- Efficiency anchor (mutex): `efficiency` (0<η≤1) **or** `hot_temp_k`+`cold_temp_k` → `η_carnot = 1 − T_cold/T_hot` (reject `T_hot ≤ T_cold`).
- Device waste heat: from net `Q = P_useful·(1−η)/η`; from gross `Q = P_in·(1−η)`, `P_useful = P_in·η`.
- Carnot floor (when temps given): `Q_min = P_useful · T_cold/(T_hot − T_cold)`; `carnot_limited = (stated η > η_carnot)` → physically-impossible device flag, **still return**.
- Both `efficiency` **and** temps given → report device waste-heat *and* the Carnot floor.

### F2 `radiator-area`
- Heat load: `heat_watts` **or** inline chain `Q = input_power_watts·(1−efficiency)`.
- Net flux `q = ε·σ·(T_rad⁴ − T_sink⁴)·n_sides` [W/m²]; area `A = Q/q`; `A_km2 = A/1e6`.
- `blackside_flux_wm2 = σ·T_rad⁴` (makes the `T⁴` dependence legible).
- `sides ∈ {1,2}` (default 2 — flat panel radiates both faces; 1 = wall into one hemisphere).
- Optional mass `m = A·areal_mass_kgm2` (else `radiator_mass_kg` null).
- `scaling_note`: `A ∝ T⁻⁴` (halving T_rad → 16× area); the Carnot coupling (radiating hotter shrinks area but a hotter cold-reservoir cuts engine η and *raises* Q); the `T_sink → T_rad` flux collapse.

### F3 `shielding-attenuation`
- **Photon mode (default, exact Lambert–Beer):** `I/I₀ = exp(−(μ/ρ)·Σ)`; `HVL = ln2/(μ/ρ)`, `TVL = ln10/(μ/ρ)` [g/cm²]; when thickness+density given, also linear `HVL_cm = HVL_gcm2/ρ`. Narrow-beam — `buildup_caveat` notes broad-beam buildup is unmodeled.
- **GCR mode (order-of-magnitude):** `D/D₀ = exp(−Σ/Λ)`; **mandatory** `buildup_caveat` (thin shields can *raise* dose via secondary production) + `is_order_of_magnitude:true`.
- Thickness via `areal_density_gcm2` **or** `thickness_cm`·`density_gcm3` (→ Σ = ρ·x).
- Coefficient via explicit value **or** `material`+`energy_mev` bundled lookup (nearest energy echoed + `energy_exact` flag; off-grid → error).

---

## 5. `query.py` wiring (modeled on the `cooling-hz` block)

Three handlers + three parsers. F1/F2 use `add_mutually_exclusive_group()` for the power
and efficiency/temp anchors; F3 uses `--mode {photon,gcr}` (default photon) and
`choices`-validated `--material`. Pattern:

```python
def cmd_waste_heat(args):           _out(thermal.compute_waste_heat(...))
def cmd_radiator_area(args):        _out(thermal.compute_radiator_area(...))
def cmd_shielding_attenuation(args):_out(thermal.compute_shielding_attenuation(...))
```

`--sides` `type=int, choices=[1,2]`; `--mode` `choices=["photon","gcr"]`; `--material`
`choices=[…]`. Numeric inputs `type=float`.

---

## 6. Validation contract (self-validating, Phase-H/P → curated `{"error"}` exit 1)

- **F1:** non-positive powers; `η ∉ (0,1]`; `T_hot ≤ T_cold`; neither power anchor given.
- **F2:** non-positive heat/temp/area; `ε ∉ (0,1]`; `sides ∉ {1,2}`; `T_sink ≥ T_rad` (no net rejection); `T_sink < 0`; neither heat anchor resolvable.
- **F3:** non-positive areal density / thickness / density / coefficient / Λ; off-grid `--material`/`--energy-mev`; (transmitted fraction is always returned in (0,1]).
- **Argparse exit 2:** missing required args, bad `--mode`/`--material`/`--sides` choice, non-numeric values, both/neither in a mutex group.

---

## 7. Output shapes (→ `docs/integration.md` for the authoritative per-key schema)

- **F1:** `{waste_heat_w, useful_power_w, input_power_w, efficiency, carnot_efficiency|null, carnot_min_waste_heat_w|null, carnot_limited|null, notes}` + echoed inputs.
- **F2:** `{radiator_area_m2, radiator_area_km2, flux_wm2, blackside_flux_wm2, heat_watts, radiator_temp_k, sink_temp_k, emissivity, sides, radiator_mass_kg|null, areal_mass_kgm2|null, scaling_note}`.
- **F3:** `{transmitted_fraction, attenuation_factor, areal_density_gcm2, half_value_layer_gcm2, tenth_value_layer_gcm2, mass_atten_coeff_cm2g|attenuation_length_gcm2, material|null, energy_mev|null, energy_exact|null, mode, model_note, buildup_caveat, is_order_of_magnitude}` (+ `thickness_cm`, `density_gcm3`, linear `half_value_layer_cm`/`tenth_value_layer_cm` when thickness+density given).

`model_note` names NIST XCOM (photon) / NCRP-153 (gcr), like `cooling-hz`'s table source.

---

## 8. Tests

**`tests/test_thermal.py`** (in-process):
- F1: 3 GW @ η=0.4 → useful 1.2e9 / waste 1.8e9; Carnot T_hot=1500/T_cold=300 → η_carnot=0.8; claimed η=0.9 → `carnot_limited:true`. Validation matrix.
- F2: σT⁴ = 459 W/m² @300 K, 5.67e4 @1000 K (ε=1, 1 side); **1 GW @300 K, ε=0.9, 2-sided → ≈1.21e6 m² (≈1.21 km²)**; `scaling_note` present; `T_sink ≥ T_rad` → error.
- F3: water @1 MeV → HVL≈9.8 cm, TVL≈32.6 cm (ρ=1); 20 g/cm² water → transmitted≈0.243; lead @1 MeV linear HVL≈0.86 cm (ρ=11.35); `gcr` mode → `buildup_caveat` + `is_order_of_magnitude:true`; off-grid material → error. **Table closure:** HVL/TVL ↔ μ/ρ for every bundled row.

**`tests/test_query_thermal.py`** (subprocess, mirrors `test_query_cooling_hz.py`):
happy-path JSON + core-parity for all three; exit-code matrix (curated `{"error"}` exit 1
for out-of-range; argparse exit 2 for missing/bad-choice/non-numeric/mutex violations).

---

## 9. Success criteria (Packet 13's acceptance)

- F1/F2/F3 reproduce every §Acceptance anchor in the request (verified above).
- F3 photon coefficients transcribed from NIST XCOM and pinned by anchor + closure tests.
- GCR mode carries the buildup caveat + order-of-magnitude flag.
- All three documented in `docs/integration.md` contract-by-reference with units on every field; F3 provenance in code (`_XCOM_SOURCE`) and in each F3 `model_note`.

---

## 10. Risks & sequencing

**Sequencing:** σ constant in `equations.py` → `shielding_tables.py` (transcribe + closure/anchor-check) → `core/thermal.py` (F1, F2, F3) → `query.py` wiring → tests → docs.

**Build note (2026-06-30):** the photon μ/ρ grid was **reconciled cell-by-cell against the
live NIST XAAMDI tables** after the first transcription — 5 of 7 materials matched verbatim;
**polyethylene** was corrected (recall values were ~9% high) and **regolith** was re-pinned by
*computing* SiO₂ from the NIST elemental Si+O tables via the mixture rule. A golden test
(`test_nist_pinned_grid`) now locks all 42 cells against drift. The XCOM-transcription risk
below is therefore retired.

**Risks:**
- *XCOM transcription* was the only non-mechanical step — now retired (reconciled against live NIST + golden-pinned; see the build note). `regolith` is a computed SiO₂ analog, flagged in the output `notes`.
- *GCR Λ values* are order-of-magnitude by nature — flagged in-output, not a correctness risk.
- Everything else is closed-form arithmetic over verified constants; ~1 focused session.

---

## References (verify at implementation; none is a load-bearing canon claim)

- **Stefan–Boltzmann / spacecraft thermal:** Incropera, *Fundamentals of Heat and Mass Transfer*; Gilmore, *Spacecraft Thermal Control Handbook*. `σ = 5.670374419×10⁻⁸ W·m⁻²·K⁻⁴` (CODATA).
- **Carnot:** standard thermodynamics, `η = 1 − T_cold/T_hot`.
- **Photon μ/ρ:** NIST XCOM (Berger et al., NSRDB 8) / NIST XAAMDI (Hubbell & Seltzer) — the authority for the bundled table.
- **GCR dose vs depth / buildup:** NCRP Report 153 / NASA HRP space-radiation references.
