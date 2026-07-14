# Phase AL — Power Generation / Storage / Thermal Calculators (Group R; Pkt 27)

**Status: Complete (built 2026-07-14) — 12 subcommands, full offline suite 1762 passed / 1 skipped.**
**Source spec:** `scifiWorldBuilding-Claude/research/query-api-methods/power-generation-storage-thermal-calculator-request.md`
**Requester grouping:** "Group R" · **Repo phase:** **AL** (Phase R is taken — the R1–R3 procedural
generator, `PHASE_R_PLAN.md`; latest completed phase is AK/Group Q, so this is AL).

Ten new `query.py`-only calculators + two bundled-table subcommands + one extension of the AK
`metric-drive-power` calc + one fuel-table add. For the sibling `scifiWorldBuilding-Claude` repo's
**Packet 27** (Power Generation, Storage, Distribution, Thermal Management). Pre-staged the same way
Group F preceded Pkt 13 (Phase V) and Group Q preceded Pkt 25 (Phase AK).

## Contract (inherited — Phase V / Group Q)

Every item is **pure-math, self-validating, `query.py`-only**: no network, no DB, no GUI, no CLI menu,
no RNG, no time, no numpy. Bad input → curated `{"error": str}` (exit 1); malformed args → argparse
(exit 2). Every result dict carries a `model_note`. Every first-principles constant is MTA-movable and
**caller-overridable**; every bundled table row is "transcribed, not fitted" with a `source_tag` + a
curated `note` + an override flag. Load-bearing numbers the spec marks **[pin @ open]** ship as
illustrative defaults flagged un-promoted in their `note`/`source_tag` — never as hard cited figures.

## Item map

| ID | Subcommand | Module | Kind |
|----|-----------|--------|------|
| R1 | `annihilation-power-train` | `core/power.py` (new) | new calc |
| R2 | `antimatter-production` | `core/power.py` | new calc |
| R3 | `heat-pump` | `core/thermal.py` (extend) | new calc |
| R4 | `reactor-net-power` | `core/power.py` | new calc |
| R5 | *(fission `f` rows)* | `core/ism_drag_tables.py` (extend, new `_FISSION`) | table add |
| R6 | `metric-drive-power --self-consistent` | `core/metric_drive.py` (extend) | extension |
| R7 | `beamed-power-delivery` | `core/power.py` | new calc |
| R8 | `flywheel-storage` | `core/energy_storage.py` (new) | new calc |
| R9 | `smes-storage` | `core/energy_storage.py` | new calc |
| R10 | `fusion-lawson` | `core/power.py` | new calc |
| T1 | `energy-storage` | `core/power_tables.py` (new) | table subcommand |
| T2 | `reactor-power` | `core/power_tables.py` | table subcommand |

**Approved design choices (2026-07-14):** (1) R5 fission `f` → a new `_FISSION` dict **beside**
`_FUSION` in `core/ism_drag_tables.py` (not polluting the `_FUSION` literal, not `_FIELD_FUEL`).
(2) Module split → `core/power.py` (generation + beamed delivery: R1/R2/R4/R7/R10) **and**
`core/energy_storage.py` (storage: R8/R9), so the σ/ρ strength-limited family stays together.

## Constants to add (`core/equations.py`)

Already present and reused: `_C_MS`, `_C_KMS`, `_MU_0`, `_M_PROTON`, `_AMU_KG`, `_STANDARD_GRAVITY`,
`_STEFAN_BOLTZMANN`. Add:

- `_MEV_J = 1.602176634e-13` — J per MeV (R5 `f = MeV/(u·931.494)`; R2 threshold arithmetic).
- `_MP_C2_MEV = 938.272` — proton rest energy, MeV (R2 exact `2 m_p / 6 m_p = 0.3333` threshold floor).

All new physical constants CODATA-sourced with an inline comment, kept in `equations.py` so they can't
drift (the Phase V/AC precedent).

---

## A. Calculators (floor physics)

Each subsection: **signature → law → outputs → validation → anchor(s) → tests.** Laws/anchors are from
the spec §A; the anchors are golden-pinned.

### R1 — `annihilation-power-train` (`core/power.py`)

`compute_annihilation_power_train(mass_flow_kgs=None, power_total_w=None, species="pp", eta_dir=None)`

- **Law:** `P_total = ṁ·c²` (or taken directly from `power_total_w`). Partition the rest energy by the
  at-rest branching: **`pp` → ½ ν (lost) / ⅓ γ (penetrating heat) / ⅙ e± (directable)** — VERIFIED
  2026-07-14 (U. Washington NPL; Segrè et al. 1959 Phys. Rev. 113 1615). `directed = η_dir·P_total`
  (η_dir default **0.5** for `pp`, capturable ~0.6–0.7); `gamma = ⅓·P_total`; `neutrino = ½·P_total`.
  `ee → 2γ`, η_dir ceiling ~1.0 (default 1.0), no neutrino channel.
- **Outputs:** `{power_total_w, power_directed_w, power_gamma_w, power_neutrino_w, eta_dir, species,
  model_note}`.
- **Validation:** exactly one of `mass_flow_kgs`/`power_total_w` (both/neither → error); the supplied
  one `> 0`; `species ∈ {pp, ee}`; `eta_dir` (if given) in `(0, 1]`.
- **Anchor:** `pp`, ṁ = 1e-9 kg/s (1 µg/s) → `P_total = 8.988e7 W`; η_dir 0.5 → directed 4.494e7,
  γ-heat 2.996e7, ν-loss 4.494e7 W. **Pin SATISFIED** (split verified; no open pin).

### R2 — `antimatter-production` (`core/power.py`)

`compute_antimatter_production(stored_mass_kg=None, stored_energy_j=None, production_efficiency, trap_field_t=None)`

- **Law — production:** `energy_stored_j = stored_mass_kg·c²` (or `stored_energy_j` directly);
  `energy_in_j = energy_stored_j / production_efficiency`;
  `threshold_floor_efficiency = 2·m_p / 6·m_p = 0.3333…` (exact, first-principles — the baryon-conserving
  `p+p → p+p+p+p̄` threshold: usable 2 m_p c² per stored 6 m_p c² input at threshold).
  `energy_ratio_in_per_stored = 1/production_efficiency`.
- **Law — storage (optional):** if `trap_field_t` given → magnetic confinement pressure `B²/2µ₀` →
  a stored-mass-per-volume ceiling (`storage_density_kg_m3`); else `null`.
- **Outputs:** `{energy_in_j, energy_stored_j, production_efficiency, threshold_floor_efficiency,
  energy_ratio_in_per_stored, storage_density_kg_m3|null, model_note}`.
- **Validation:** exactly one of `stored_mass_kg`/`stored_energy_j` (both/neither → error), `> 0`;
  **`production_efficiency` is required, un-defaulted** (0 < η ≤ 1 → and warn/flag if η >
  `threshold_floor_efficiency` in the note since that exceeds the ideal ceiling); `trap_field_t` (if
  given) `> 0`.
- **[pin @ open]:** the real/projected `production_efficiency` band (Frisbee 2008; Schmidt/Gerrish/Martin
  NASA) is the **H-25-1 decision input** — the tool must **not** ship a default; the caller supplies it.
  Only `threshold_floor_efficiency = 0.333` is a hard first-principles number.
- **Anchor:** `stored_mass_kg = 1e-9`, `production_efficiency = 1e-4` → `energy_stored_j = 8.988e7`,
  `energy_in_j = 8.988e11`, `threshold_floor_efficiency = 0.3333`, `energy_ratio_in_per_stored = 1e4`.

### R3 — `heat-pump` (`core/thermal.py`, beside `compute_waste_heat`)

`compute_heat_pump(cold_temp_k, hot_temp_k, heat_lifted_w=None, work_w=None, efficiency_fraction=1.0)`

- **Law:** `COP_cool_carnot = T_c/(T_h−T_c)`, `COP_heat_carnot = T_h/(T_h−T_c)`;
  `COP_cool_actual = efficiency_fraction·COP_cool_carnot`; from the given anchor:
  `W = Q_c/COP_cool_actual` (Q_c given) or `Q_c = W·COP_cool_actual` (W given);
  `heat_rejected_w = Q_c + W` (feeds `radiator-area` at `T_h`). Fills the hole `waste-heat`'s own
  model_note names ("Steady refrigeration/pump work is out of scope").
- **Outputs:** `{cop_cool_carnot, cop_heat_carnot, cop_cool_actual, work_w, heat_lifted_w,
  heat_rejected_w, cold_temp_k, hot_temp_k, efficiency_fraction, model_note}`.
- **Validation:** `T_c > 0`, `T_h > 0`, `T_h > T_c` (a heat pump rejects to a **warmer** reservoir);
  exactly one of `heat_lifted_w`/`work_w`, `> 0`; `efficiency_fraction` in `(0, 1]`.
- **Anchor:** lift 1 W from 300 K, reject at 320 K, ideal → `COP_cool_carnot = 300/20 = 15`,
  `W = 0.06667 W`, `heat_rejected_w = 1.06667 W`, `COP_heat_carnot = 16`.

### R4 — `reactor-net-power` (`core/power.py`)

`compute_reactor_net_power(gross_power_w, thermal_efficiency, q_plasma=None, recirculating_fraction=0.0)`

- **Law:** `electric_power_w = gross_power_w·η_th`; `engineering_breakeven_q = 1/η_th`;
  `net_power_w = electric·(1 − recirc) − (fusion Q-tax: electric/Q_plasma when q_plasma given)`.
  Ignition at `Q → ∞` (Q-tax → 0). Net-energy accounting **only** — W/kg is deliberately in T2, not here.
- **Outputs:** `{gross_power_w, electric_power_w, net_power_w, engineering_breakeven_q,
  thermal_efficiency, q_plasma|null, recirculating_fraction, model_note}`.
- **Validation:** `gross_power_w > 0`; `thermal_efficiency` in `(0, 1]`; `q_plasma` (if given) `> 0`;
  `recirculating_fraction` in `[0, 1)`.
- **Anchor:** 1e9 W thermal, η_th 0.4, Q_plasma 10, recirc 0 → electric 4.0e8 W; engineering breakeven
  Q = 2.5; net = 4.0e8·(1−0) − 4.0e8/10 = 3.6e8 W.

### R5 — fission `f` (table add, `core/ism_drag_tables.py`)

New `_FISSION` dict beside `_FUSION` (same "bundled mass→energy fractions, transcribed-not-fitted,
MTA-movable" file). Rows carry `f` = **recoverable** mass→energy fraction + a `note` flagging the
antineutrino loss.

- **Rows:** `u235`: `f = 9.14e-4` (200 MeV recoverable / (235.04 u · 931.494 MeV/u)); `pu239`:
  `f ≈ 9.3e-4` (~207 MeV / (239.05 u · 931.494)). Note: **~8.8 MeV/fission** leaves as antineutrinos
  (unrecoverable; of ~210 MeV total) — the `f` is the recoverable fraction.
- **Free consequence:** fission storage energy density `f·c² ≈ 8.21e13 J/kg` (U-235) — no separate calc.
- **Cross-check (verified 2026-07-14):** precise per-atom 202.5 MeV → 8.31e13 J/kg (Wikipedia
  *Uranium-235*); the 200-MeV round value agrees within ~1.2 %.
- **Surfacing:** referenced from the T1 `energy-storage` note (nuclear ceilings come free from `f·c²`);
  no standalone subcommand for R5 (the fuel-table pattern; consumed by whoever reads the table).

### R6 — `metric-drive-power --self-consistent` (extend `core/metric_drive.py`)

Fulfils `metric-drive-power-followups.md` (Proposed). Adds `self_consistent=False, ash="keep"` params
to `compute_metric_drive_power`; **build-gate CLEARED** (Pkt 25 CONVERGED, M1 audit passed). Keeps all
existing first-order fields unchanged (back-compat + small-Δη agreement check).

- **Requires** a `--fuel` preset **or** explicit `f` + `η_dir` — the self-consistent law needs the fuel's
  mass→energy fraction `f` and directed fraction `η_dir` **separately** (not just their product `f_conv`).
  Guard: `--self-consistent` without a way to resolve both → curated error.
- **ash keep:** `X = (1 − e^(−k·Δη/η_dir)) / f`; `feasible = X < 1`;
  `fuel_mass_fraction_sc = X/(1−X)` (only when feasible; else report infeasible);
  `k_wall = −η_dir·ln(1−f)/Δη`; `lifetime_delta_v_budget_kms = c·tanh(−η_dir·ln(1−f)/k)/1000`.
- **ash vent** (zero-relative-velocity dump): `fuel_mass_fraction_sc = e^(k·Δη/f_conv) − 1` (no wall).
- **model_note addition:** "First-order bill valid for fuel ≪ ship; self-consistent mode taxes carried
  fuel/ash and η_dir waste (effective exponent k/η_dir). Ash-vent mode treats vented mass as
  zero-velocity dump only — ash used as reaction mass (hybrid field+material thrust) is NOT modeled."
- **Error:** `--ash vent` without `--self-consistent` → curated error.
- **Anchors (hand-derived; verified in this plan):**
  1. D-T (f 0.00375, η 1), 1 g-day, k=3 → `feasible: false`; `k_wall ≈ 1.329`;
     `lifetime_delta_v_budget_kms ≈ 375.4`.
  2. D-T, 1 g-day, k=1 → `fuel_mass_fraction_sc ≈ 3.04` (first-order field 0.753).
  3. antimatter-pp (f 1, η_dir 0.5), 25 g-day, k=3 → sc ≈ 0.529 (first-order 0.383).
  4. antimatter-pp, 50 g-day, k=3 → sc ≈ 1.35; k=1 → sc ≈ 0.329.
  5. Vent: D-T, 1 g-day, k=3 → sc = e^(3·0.0028263/0.00375) − 1 ≈ 8.59.
  6. Small-Δη agreement: any fuel, Δη ≤ 1e-4 → |sc − first-order|/first-order < 1 %.
  7. Error: `--ash vent` without `--self-consistent` → curated error.

### R7 — `beamed-power-delivery` (`core/power.py`)

`compute_beamed_power_delivery(wavelength_m=None, frequency_hz=None, tx_aperture_m, rx_aperture_m, range_m, tx_power_w=None, pointing_efficiency=1.0)`

- **Law:** `λ = c/frequency_hz` if frequency given; full-null spot `D_spot = 2.44·λ·L/D_t`;
  `capture_fraction = min(1, (D_r/D_spot)²)` (top-hat approx); `aperture_product_m2 = D_t·D_r`;
  `full_coupling_product_m2 = 2.44·λ·L`; `coupling_margin = aperture_product / full_coupling_product`;
  `delivered_power_w = tx_power_w·capture_fraction·pointing_efficiency` (or `null`).
- **Outputs:** `{spot_diameter_m, capture_fraction, delivered_power_w|null, aperture_product_m2,
  full_coupling_product_m2, coupling_margin, wavelength_m, model_note}`.
- **Validation:** exactly one of `wavelength_m`/`frequency_hz`, `> 0`; `tx_aperture_m`, `rx_aperture_m`,
  `range_m` all required `> 0`; `tx_power_w` (if given) `> 0`; `pointing_efficiency` in `(0, 1]`.
- **Anchor:** λ = 1e-6 m, D_t = 10 m, L = 1.496e11 m (1 AU) → `D_spot ≈ 3.65e4 m` (36.5 km);
  D_r = 100 m → `capture_fraction ≈ 7.5e-6` (the diffraction wall).

### R8 — `flywheel-storage` (`core/energy_storage.py`)

`compute_flywheel_storage(tensile_strength_pa, density_kgm3, shape_factor=0.5, mass_kg=None)`

- **Law:** `e_specific = K·σ/ρ` [J/kg]; `specific_energy_wh_kg = e_specific/3600`;
  `stored_energy_j = e_specific·mass_kg` (or `null`). MTA-movable via σ — ties to the materials packet
  and `spin-stress` σ values (same rim strength ceiling).
- **Outputs:** `{specific_energy_j_kg, specific_energy_wh_kg, stored_energy_j|null, shape_factor,
  tensile_strength_pa, density_kgm3, model_note}`.
- **Validation:** `tensile_strength_pa > 0`, `density_kgm3 > 0`, `shape_factor` in `(0, 1]`, `mass_kg`
  (if given) `> 0`.
- **Anchor:** σ = 5e9 Pa, ρ = 1800, K = 0.5 → `e = 1.389e6 J/kg` (386 Wh/kg); K = 0.3 → 8.33e5 J/kg.

### R9 — `smes-storage` (`core/energy_storage.py`)

`compute_smes_storage(field_t, critical_field_t=None, tensile_strength_pa=None, density_kgm3=None, volume_m3=None)`

- **Law:** volumetric `energy_density_j_m3 = B²/(2·µ₀)`; `stored_energy_j = u·volume_m3` (or `null`).
  **Physics catch:** the magnetic pressure `B²/2µ₀` must be held by structure, so the **specific**
  (per-kg) energy is again strength-limited `≈ σ/ρ` (same family as R8) — `specific_energy_j_kg = σ/ρ`
  when both σ and ρ given, else `null`. Flag `critical_field_exceeded` when `B > B_c`.
- **Outputs:** `{energy_density_j_m3, stored_energy_j|null, specific_energy_j_kg|null, field_t,
  critical_field_exceeded|null, model_note}`.
- **Validation:** `field_t > 0`; `critical_field_t`, `volume_m3` (if given) `> 0`; if one of σ/ρ given,
  **both** required and `> 0`.
- **Anchor:** B = 20 T → `u = 400/(2·4πe-7) = 1.592e8 J/m³` (159 MJ/m³).

### R10 — `fusion-lawson` (`core/power.py`)

`compute_fusion_lawson(fuel, density_m3=None, temp_kev=None, confinement_s=None, triple_product=None, confinement_boost=1.0)`

- **Law:** triple product `n·T·τ` (from n, T, τ) **or** `triple_product` directly, scaled by
  `confinement_boost` (the AG multiplier on n·τ, echoed). Compare to the per-fuel ignition threshold
  `(n·T·τ)_ignition(fuel)` → `q_fusion` (ratio) + `ignited` (bool, `≥` threshold). D-T ignition
  ≈ 3e21 keV·s·m⁻³ near the ~14 keV minimum.
- **Scope guard (mandatory in model_note):** general-power / **civilian-reactor side ONLY**. The
  metric-drive task-(d) (AG-boosted fusion closing the *drive* gap) stays REFUTED on `f`-wall grounds —
  this calc does not reopen it; `confinement_boost` is a confinement (nTτ) lever feeding **R4's
  `--q-plasma`**, never a drive-closure route.
- **Outputs:** `{triple_product_kev_s_m3, ignition_threshold, q_fusion, ignited, confinement_boost,
  fuel, model_note}`.
- **Validation:** `fuel ∈ {d-t, d-he3, d-d, p-b11}`; either a complete `(n, T, τ)` triple **or**
  `triple_product` (partial/both → error), all `> 0`; `confinement_boost > 0`.
- **[pin @ open]:** per-fuel ignition thresholds vs. a plasma-physics reference (Wesson *Tokamaks*;
  Lawson 1957); aneutronic (p-B11) ~10³× harder → carries that cited caveat in its row note.
- **Anchor:** D-T at T = 14 keV with n·τ giving n·T·τ = 3e21 → `q_fusion ≈ 1` (`ignited` boundary);
  `confinement_boost 3` → triple product ×3, Q rises ×3.

---

## B. Bundled-table subcommands (`core/power_tables.py`)

Both surfaced as thin `query.py` subcommands (the `main-sequence`/`substellar` pattern). Common contract:
no `--class` → **all rows**; `--class NAME` → the single row; `--override-*` (per-field) replaces a
value with the caller's number and echoes the substitution; every row carries `source_tag` + a curated
`note`; unknown class → curated `{"error"}` listing valid keys (the `_FUSION`/`_FIELD_FUEL` error idiom).
Dict literals isolated from calculator logic; golden-pinned.

### T1 — `energy-storage` (backed by `_STORAGE`)

- **Rows:** `li-ion` (~0.25 MJ/kg current → ~1 MJ/kg advanced ceiling), `supercapacitor`,
  `chemical-fuel` (H₂/O₂, CH₄/O₂), `sensible-thermal`, `latent-thermal`, `gravitational`. Each:
  specific energy (J/kg, Wh/kg), volumetric (Wh/L where meaningful), round-trip efficiency,
  self-discharge/leak note, `source_tag`. **[pin @ open]** each row's source.
- **Compute branch** (sensible/latent rows): `--mass-kg --specific-heat-jkgk --delta-t-k` → sensible
  `E = m·c_p·ΔT`; `--mass-kg --latent-heat-jkg` → latent `E = m·L` (the `waste-heat` C9 physics,
  surfaced as stored-energy sizing). No compute args → pure lookup.
- **Outputs:** lookup: `{class, specific_energy_j_kg, specific_energy_wh_kg, volumetric_wh_l|null,
  round_trip_efficiency|null, leak_note, source_tag, note}`; compute: `+ stored_energy_j`.
- **Nuclear/antimatter note:** the note points the caller to `f·c²` (R5 `_FISSION` / `_FUSION` /
  `_FIELD_FUEL`) for the nuclear/antimatter ceilings that come free — they are deliberately NOT `_STORAGE`
  rows (no clean floor-law where a table is needed; R8/R9 cover the two that do have laws).

### T2 — `reactor-power` (backed by `_REACTOR_SPECIFIC_POWER`)

- **Rows** (`α = P/m`, kW/kg): `fission` (SP-100 ~0.03 kW/kg → advanced), `fusion` (projected ~1–10
  kW/kg mature), `antimatter` (beamed-core; Frisbee estimates), `rtg` (~5 W/kg), `solar-thermal`. Each
  MTA-movable + cited `source_tag`. **[pin @ open]** each α value.
- **`--gross-power-w P`:** echo the implied **core mass** `core_mass_kg = P/α` — but **every** result
  carries the **mandatory `thermal_pointer` note**: the real binding ceiling at high P is thermal, not
  core-mass — a reactor emitting P rejects `P·(1−η)` and radiator mass dominates; size it by composing
  `reactor-net-power`/`waste-heat` → `radiator-area`.
- **Outputs:** `{class, specific_power_kw_kg, core_mass_kg|null, source_tag, note, thermal_pointer}`.

---

## C. Documented exclusions (prose only — NO code)

Per the standing principle, excluded **by decision**, not omission (each is civilization-layer
engineering/law with no repeal-proof floor law implementable in a `query.py` tool):

- Grid architecture / transmission loss / load balancing / fault isolation — network engineering (Pkt 27
  prose). (Superconducting *cable* current limits are materials-packet table territory.)
- Superconductor critical-current / quench — materials-packet engineering (the one superconductor *floor*
  that IS a law — B²/2µ₀ — is captured in R9).
- Grid authority / rationing / blackout law / liability / seizure / priority — law/institutions (Pkt 37 +
  Pkt 27 prose).
- Reactor specific power (W/kg) — table **T2 + thermal pointer**, not a calculator.

---

## `query.py` wiring

Import `core.power`, `core.energy_storage`, `core.power_tables` at the top (`core.thermal` and
`core.metric_drive` already imported). Add ~12 `cmd_*` thunks after the AK block (~line 483) and ~12
`sub.add_parser(...)` blocks after the AK parsers (~line 2564), each ending in `p.set_defaults(func=…)`.
Use **argparse mutually-exclusive groups** for every "exactly one of" input anchor (the `waste-heat`
power-anchor precedent) so the wrong-count case exits 2 and the semantic/range errors exit 1.

## Docs to update

- **`docs/integration.md`** — new "### Power Generation / Storage / Thermal (Phase AL — no network)"
  section, one `####` block per subcommand (args + output keys + validation + anchor), + 12 quick-ref
  table rows. **This is the consumer contract — mandatory** (CLAUDE.md rule: update before/while adding
  any `query.py` subcommand).
- **`docs/gui-architecture.md`** — one "AL (complete)" roadmap-table row.
- **`docs/testing.md`** — per-test-file descriptions for the new test files.
- **`CLAUDE.md`** — one clause in the `query.py`-only calculator-packs paragraph naming
  `power.py` / `energy_storage.py` / `power_tables.py` and the `_FISSION` add.

---

## Test plan

All tests **offline**, no network/Qt/DB, run under `venv/bin/python -m unittest` (and pytest when
present). Follow the `test_thermal.py` (in-process core) + `test_query_thermal.py` (subprocess contract
via `tests/_queryharness.py`) split. Every spec anchor → a golden-pin assertion; every calc → its
error-matrix (curated exit 1 / argparse exit 2 / subprocess==in-process parity).

**New / extended test files:**

| File | Covers |
|------|--------|
| `tests/test_power.py` (new) | R1, R2, R4, R7, R10 core — anchors + validation + `model_note` presence |
| `tests/test_query_power.py` (new) | R1/R2/R4/R7/R10 subprocess: JSON shape, core parity, exit-code matrix |
| `tests/test_energy_storage.py` (new) | R8, R9 core — anchors (1.389e6 J/kg; 1.592e8 J/m³) + σ/ρ specific-energy branch + `B>B_c` flag |
| `tests/test_query_energy_storage.py` (new) | R8/R9 + T1/T2 subprocess: lookup-all, `--class`, `--override-*` echo, compute branch, unknown-class error |
| `tests/test_power_tables.py` (new) | T1 `_STORAGE` / T2 `_REACTOR_SPECIFIC_POWER` golden row pins, accessor + error idiom |
| `tests/test_thermal.py` / `test_query_thermal.py` (extend) | R3 heat-pump — 300→320 K anchor (COP 15, W 0.0667, reject 1.0667), `T_h≤T_c` error, one-of(Q_c\|W) |
| `tests/test_group_q.py` (extend) | R6 — **all 7 followups anchors** incl. small-Δη→first-order agreement (<1 %) and the `--ash vent`-without-`--self-consistent` error |
| `tests/test_ism_drag.py` (extend) | R5 — `_FISSION` golden pins: `u235` f = 9.14e-4, `f·c²` = 8.21e13 J/kg, `pu239` f ≈ 9.3e-4 |

**Per-item test obligations (must all pass):**

- **R1:** ṁ 1 µg/s `pp` → total 8.988e7, directed 4.494e7, γ 2.996e7, ν 4.494e7; `ee` no-ν; `power_total_w` path == `mass_flow` path; both/neither anchor → error; bad species → error.
- **R2:** anchor ratios; `threshold_floor_efficiency == 0.3333` (exact); **no default** `production_efficiency` (omitted → argparse error); storage branch `null` without `--trap-field-t`.
- **R3:** 300→320 anchor; `T_h ≤ T_c` → error; both/neither of Q_c/W → error; W-given and Q_c-given give consistent `heat_rejected_w`.
- **R4:** anchor electric 4.0e8 / breakeven 2.5 / net 3.6e8; recirc ∈ [0,1) enforced; no-Q_plasma path (no Q-tax).
- **R5:** golden f/f·c² pins; row note flags antineutrino loss; both rows present.
- **R6:** all 7 anchors; **existing first-order fields byte-identical** when `--self-consistent` absent (regression pin against current `test_group_q` output); requires-fuel guard.
- **R7:** anchor D_spot 36.5 km / capture 7.5e-6; frequency==wavelength path; `coupling_margin`; `delivered_power_w` null without `--tx-power-w`.
- **R8:** 1.389e6 J/kg (K 0.5) + 8.33e5 (K 0.3); `stored_energy_j` null without mass.
- **R9:** 1.592e8 J/m³; `specific_energy_j_kg` null without σ+ρ; `critical_field_exceeded` flag when B > B_c; one-of-σ/ρ → error.
- **R10:** D-T ignition-boundary q≈1; `confinement_boost 3` → ×3; bad fuel → error; partial (n,T,τ) → error; scope-guard string present in `model_note`.
- **T1:** all-rows vs `--class li-ion`; `--override-wh-kg` echo; sensible/latent compute branch `E=mc_pΔT` / `E=mL`; unknown class → error listing keys.
- **T2:** all-rows vs `--class fusion`; `--gross-power-w` → `core_mass_kg`; **`thermal_pointer` present on every result**; unknown class → error.

---

## Success criteria

The phase is **done** when **all** hold:

1. **Functional:** all 10 calculators + 2 table subcommands + R5 rows + R6 extension are callable via
   `query.py`; each produces the spec's anchor value(s) to the stated precision.
2. **Contract:** every subcommand self-validates — bad input → curated `{"error"}` exit 1; malformed
   args → argparse exit 2; every result dict carries a `model_note` (and T2 a `thermal_pointer`).
3. **Provenance discipline:** no `[pin @ open]` number ships as a hard cited figure — R2
   `production_efficiency` is un-defaulted/caller-supplied; T1/T2 rows and R10 thresholds carry
   `source_tag`/notes flagging them illustrative; every first-principles constant is caller-overridable.
4. **Back-compat:** the existing `metric-drive-power` first-order output is **unchanged** without
   `--self-consistent` (regression-pinned); no existing subcommand's behavior changes; `query.py` stays
   numpy-free.
5. **Tests:** the full **offline suite passes** (current baseline + all new/extended tests, 0 new
   failures/errors, ≤ existing live-network skips); every spec anchor and every error path is a golden
   pin; subprocess results match in-process for each new subcommand.
6. **Docs:** `docs/integration.md` documents all 12 subcommands (args + outputs + validation + anchor)
   and carries their quick-ref rows; `docs/gui-architecture.md`, `docs/testing.md`, and `CLAUDE.md` are
   updated. The consumer (`scifiWorldBuilding-Claude`) can call every subcommand from the contract alone.
7. **Verified end-to-end:** a manual `query.py` invocation of each new subcommand (happy path + one error
   path) is exercised and its JSON confirmed against the anchor before sign-off.

---

## Build order (spec §"Build order / readiness")

1. **R6** (`--self-consistent`) + **R5** (fission `f`) — highest priority (demand-table integrity for
   Pkt 27); gate cleared, anchors pinned; R5 trivial. First vertical slice.
2. **R3, R7, R8, R9** — clean first-principles laws, anchors derivable now.
3. **R1, R4, R10** — first-principles; R10 → R4 hand-off; R10 carries the general-power scope guard.
4. **R2** — mechanics now; `production_efficiency` stays an un-defaulted required research input (H-25-1).
5. **T1, T2** — bundled tables, rows populated with `[pin @ open]` flags.

## Cross-references

- Spec: `power-generation-storage-thermal-calculator-request.md`; sub-spec fulfilled by R6:
  `metric-drive-power-followups.md`.
- Handoffs: `propulsion-systems/research-brief.md` §11; `open-questions.md` OQ-MD-5 (b/e), OQ-AG-3;
  `decisions.md` 2026-07-13 (Pkt 25 close).
- Pattern precedents: Phase V (`PHASE_V_PLAN.md`, `core/thermal.py`), Phase AK (`PHASE_AK_PLAN.md`,
  `core/metric_drive.py`), the bundled-table modules (`core/propulsion_tables.py`,
  `core/shielding_tables.py`, `core/ism_drag_tables.py`).
