# Phase AC — ISM-Drag / Magnetic-Sail Calculators (Group K)

**Status:** BUILT 2026-07-02 (Phase AC complete — 32 tests, full suite green). `query.py`-only, no
GUI/CLI-menu/DB/network/RNG/time.
**Request:** `scifiWorldBuilding-Claude/research/query-api-methods/ism-drag-magsail-calculator-request.md`
(Pkt 16, Group K — Proposed 2026-07-02).
**Lineage:** Phase-N/T/U/V/W/X/Y/Z/AA/AB. Same pure-math + one bundled static table pattern as
`propulsion` (Group G) / `thermal` (Group F) / `cooling` (U).

---

## 0. Why & scope

Closes the one scope-shaping STL gap the Groups-G–J forward batch did not enumerate: the **magnetic
interaction of a vehicle with the interstellar medium (ISM)**. Two `query.py`-only subcommands:

- **`magsail`** (K1) — magnetic-sail *braking* against the ISM: magnetopause standoff → drag force
  (∝ v^4/3) → deceleration → optional stopping distance/time.
- **`ramscoop`** (K2) — Bussard ramjet *drag-vs-thrust* verdict: `F_net = ṁ(v_e − v) − F_drag` →
  `"drive"`/`"brake"` + crossover velocity (the Zubrin & Andrews "brake not drive" result as a swept
  recompute).

Complements Group G (`rocket-equation` = "can you carry the fuel"; `beam-sail` = "can a photon beam
push you"; **Group K = "what does the ISM do to you — brake you, or feed a ramjet"**) and the
`dust-*` subcommands (ISM *column* for extinction, not magnetic momentum exchange).

**Phase letter AC** (Group G=Y, H=Z, I=AA, J=AB → K=AC).

### Boundary guards (bake in; do NOT cross)
1. **ISM density is a parameterized input** (defaults flagged to Local-Bubble bands), never re-derived.
2. **Momentum/energy balance only** — no reactor/coil/plasma engineering, no ionization chemistry
   (assume fully ionized; flag). Coil mass/quench/structure defer to packet prose / Pkt 25.
3. **Dust impact stays deferred** (OQ-D/OQ-F reasoning task) — this is the *magnetic/plasma* interaction.
4. **Trajectory integration is v1-lite** — instantaneous force + one optional single-law stopping
   estimate; note the limitation in output. No multi-leg optimization.

---

## 1. Locked physics

Shared: `ρ = n·m̄` (`n` cm⁻³ → ×1e6 m⁻³; `m̄` amu → ×`_AMU_KG`). `m_dip = I·π·R_coil²` or supplied.
Velocity from `--velocity-kms` or `--beta` (×`_C_MS`).

### K1 `magsail`
```
R_mp   = [ μ₀ · m_dip² / (8π² · k · ρv²) ]^(1/6)      magnetopause standoff
F_drag = C_d · ½ · ρv² · π · R_mp²                     drag force
```
Since `R_mp ∝ v^(−1/3)` ⟹ `R_mp² ∝ v^(−2/3)` ⟹ **`F_drag ∝ v^(4/3)`** (fast initial braking, long
tail — emit `drag_scaling_note`). `a = F_drag / M_vehicle` (optional). Optional stopping distance/time
integrating `M dv/dt = −F_drag(v)` with the `v^(4/3)` law, **analytic closed form** (write
`F_drag = β·v^(4/3)` with β evaluated so `F_drag(v₀)` matches, then):
```
t_stop = 3M/β · (v_f^(−1/3) − v₀^(−1/3))         (both terms → t>0 for braking v_f<v₀)
x_stop = 3M/(2β) · (v₀^(2/3) − v_f^(2/3))
```
Flag as a single-law estimate (β frozen at the v₀ coefficient; boundary guard #4).

### K2 `ramscoop`
```
A_mp   = π R_mp²    (K1 standoff)  OR  supplied --scoop-area-km2
ṁ      = ρ · v · A_mp                              collected mass flux
v_e    = √(2 · η · f · c²)   OR  supplied --exhaust-velocity-kms
F_reaction = ṁ · v_e ;  F_collect = ṁ · v ;  F_drag = C_d · ½ ρv² A_mp
F_net  = ṁ(v_e − v) − F_drag
verdict = "drive" if F_net > 0 else "brake"
```
**Crossover velocity** (`F_net → 0`): bracketed **bisection** on `F_net(v)` over `[v_lo, v_e]`;
`null` + note if no sign change in range. (When `--scoop-area-km2` is fixed, `ṁ ∝ v` and the drag
term’s v-dependence still needs the root-find; keep one code path.)

### Anchor verification (from the spec; I re-derived K1 and it holds)
- **K1:** `n0.1 / m1.0 / β0.1 / R_coil 1e5 m / I 1e5 A` → m_dip ≈ 3.14e15 A·m², **R_mp ≈ 100 km**,
  ram pressure ≈ 1.49e-7 Pa, **F_drag ≈ 2.3 kN** (C_d=k=1), **a ≈ 2.3e-3 m/s²** for 10³ t. Halving β
  drops drag ~2^(4/3) ≈ 2.5×. Matches spec order-of-magnitude anchors.
- **K2:** `--fuel pp` (v_e ≈ c·√(2·0.0071) ≈ 0.12c) @ β0.1 → ideal drag-free margin razor-thin; adding
  drag **or** any realistic `η<1` flips `verdict` → `"brake"` with a low crossover; low β + high η →
  `"drive"`.

---

## 2. Files

| File | Action |
|---|---|
| `core/equations.py` | **Add** `_MU_0 = 4π×10⁻⁷` (T·m/A) and `_M_PROTON = 1.67262192e-27` (kg). `_AMU_KG`, `_C_MS`, `_SEC_PER_YEAR` already present; `_LY_M` exists in `core/calculators.py` (import or add to equations). |
| `core/ism_drag_tables.py` | **New.** Bundled ISM/fusion constants + provenance header + model-notes (mirrors `propulsion_tables.py`). |
| `core/ism_drag.py` | **New.** `compute_magsail(...)`, `compute_ramscoop(...)`. |
| `query.py` | `cmd_magsail` / `cmd_ramscoop` handlers (after the Group-G block) + two `add_parser` blocks; `from core import ism_drag`. |
| `tests/test_ism_drag.py` | **New.** In-process anchors + validation matrix + determinism + golden pins. |
| `tests/test_query_ism_drag.py` | **New.** Subprocess contract (mirrors `test_query_propulsion.py`). |
| `docs/integration.md` | Quick-ref rows + "ISM drag / magnetic sail (Phase AC)" contract-by-reference (units on every field). |
| `docs/gui-architecture.md` | One completion-status row (query.py-only; Phase-Y/Z/AA/AB precedent). |
| the request file | On shipment → `Deprecated — FULFILLED` + as-built shapes + final `k`/`C_d`/`η`/`f`. |

---

## 3. `core/ism_drag_tables.py` — bundled constants (all overridable; MTA-flagged)

**Web-confirmed 2026-07-02** (transcribe citations into the provenance header, like
`propulsion_tables.py`). All four Open items are now resolved:

- `_MEAN_ION_MASS_AMU = 1.3` — **RESOLVED (Open #3)** from the sibling Local-Interstellar-Environment
  packet: H+He, He/H≈0.1 → (1+0.1×4)/1.1 ≈ 1.27 amu. Overridable.
- `_DEFAULT_N_CM3 = 0.1` — **RESOLVED (Open #3)**: the Local Interstellar Cloud n(H I) ≈ 0.1 cm⁻³
  (0.03–0.2 directional; the Sun's actual medium). Second documented band: Local Bubble interior
  ~0.005 cm⁻³ (hot cavity). Flagged, overridable.
- **`_IONIZATION_NOTE` (new — nuance the spec missed):** the real LIC is only ~22% H / ~39% He
  ionized, and a magsail/ramscoop couples to *charged* particles only, so boundary-guard #2's
  "assume fully ionized" **overestimates the interacting density ~4× in the LIC**. Emit an
  `ionization_note` in both outputs advising callers who care about accuracy to pass the *ion*
  density as `--ism-density-cm3` rather than total `n`. (Source: LIE packet claim-map C5, Established.)
- `_DRAG_COEFF_CD = 1.0` — **CONFIRMED (Open #1)**: Zubrin & Andrews' explicit convention — "a drag
  coefficient of unity for the area defined by the magsail's magnetospheric boundary" (Wikipedia
  *Magnetic sail*; Andrews & Zubrin 1990/1991).
- `_STANDOFF_COEFF_K = 1.0` — **CONFIRMED (Open #1)**: simple pressure balance `B_dipole²/2μ₀ = ρv²`
  hits the spec's R_mp ≈ 100 km acceptance anchor exactly. Documented alternative for the caller: the
  compressed-to-dipole field factor is **f = 2** (dipole vs infinite conducting plane) / **2.44**
  (Chapman-Ferraro spherical problem) — a caller wanting the compressed-field convention sets
  `--standoff-coeff` accordingly (Samsonov 2020, *GRL* 47 e2019GL086474; standard magnetospheric
  physics). Note in `model_note`.
- `_FUSION = {"pp": 0.0071, "cno": 0.0071, "dd": 0.0038}` — mass→energy fractions (Open #2).
  **CONFIRMED:** p-p/CNO ≈ **0.71%** (Atomic Rockets / Energy Education: "p-p chain to ⁴He is 0.7%
  efficient"; = 26.73 MeV / 4×938.27 MeV; ~72% of the 0.97% Fe-56 ceiling). D-T ≈ 0.375% (mass defect
  0.018882 / 5.029053 AMU). **D-D reconciled DOWN from the spec's 0.43% → 0.0038** (catalyzed D-D
  cycle, ≈ D-T scale, consistent with `propulsion_tables.py`'s D-T 0.38%); the *single* D-D reaction
  is only ~0.10% (avg 3.65 MeV / 3751 MeV). The spec's 0.43% matches neither single-reaction nor
  standard catalyzed-cycle values — **flag this deviation to the requester on shipment.** p-p (the
  physically load-bearing fuel — the ISM is >90% protons) is rock-solid, so the ramjet verdict is
  unaffected by the D-D choice.
- `_DEFAULT_FUSION_EFFICIENCY = 0.1` (η) — **CONFIRMED low (Open #2)**: directed-exhaust fraction.
  Ideal η=1 gives pp `v_e = √(2·0.0071)·c ≈ 0.119c` (matches the spec's "p-p ideal ≈ 0.12c"); η=0.1
  gives ≈ 0.038c, reproducing the acceptance behavior (brake at β=0.1, drive only at low β). Zubrin &
  Andrews 1985 assumed a realistic exhaust ~100 km/s vs collected solar-wind ions ~500 km/s → drag >
  thrust ("brake not drive"); the low η encodes that realism.
- `_SOURCES` provenance string + `_MODEL_NOTE_MAGSAIL` / `_MODEL_NOTE_RAMSCOOP`.

---

## 4. Subcommand contracts

### `magsail`
Inputs: `--ism-density-cm3` (default 0.1), `--ion-mass-amu` (default 1.3); velocity **mutex**
`--velocity-kms | --beta`; sail **mutex** `(--coil-current-a + --coil-radius-m) | --magnetic-moment-am2`;
`--standoff-coeff` (k), `--drag-coeff` (C_d); optional `--vehicle-mass-t`, `--velocity-final-kms`
(requires `--vehicle-mass-t`).

Output: `{ism_density_cm3, ion_mass_amu, ism_mass_density_kgm3, velocity_kms, beta,
magnetic_moment_am2, coil_current_a|null, coil_radius_m|null, magnetopause_radius_km, ram_pressure_pa,
effective_area_km2, drag_coeff, standoff_coeff, drag_force_n, drag_scaling_note ("F ∝ v^4/3"),
deceleration_ms2|null, stopping_distance_ly|null, stopping_time_yr|null, near_field_warning|null,
ionization_note, model_note}`.

### `ramscoop`
Inputs: `--ism-density-cm3`, `--ion-mass-amu`; velocity **mutex**; scoop **mutex**
`(--coil-current-a + --coil-radius-m) | --scoop-area-km2 | --magnetic-moment-am2`; exhaust **mutex**
`(--fuel {pp,cno,dd} + --fusion-efficiency) | --exhaust-velocity-kms`; `--standoff-coeff`, `--drag-coeff`.

Output: `{velocity_kms, beta, ism_density_cm3, ion_mass_amu, magnetopause_radius_km, scoop_area_km2,
collected_mass_flux_kgs, fuel, fusion_yield_fraction, fusion_efficiency, exhaust_velocity_kms,
exhaust_beta, reaction_thrust_n, collection_drag_n, magnetic_drag_n, net_force_n,
verdict ("drive"|"brake"), crossover_velocity_kms|null, ionization_note, model_note}`.

---

## 5. Validation (self-validating — curated `{"error"}` exit 1; argparse exit 2)

**Exit 1 (core):** non-positive density/velocity/current/radius/area/mass/moment; `β ∉ (0,1)`; η ∉ (0,1];
`C_d`/`k` ≤ 0 (allow > 1 — order-unity, not bounded to 1); not exactly one velocity/sail/scoop/exhaust
anchor; unknown `--fuel`; `--velocity-final-kms` without `--vehicle-mass-t` (K1).
**Exit 2 (argparse):** the `--velocity-kms`/`--beta` mutex; single-alternative mutex groups where
practical; non-numeric; bad `--fuel` choice.
**Near-field:** when `R_mp ≲ R_coil` the far-field-dipole assumption weakens → `near_field_warning` note
(Open #4: warn, don't error).

---

## 6. Tests

- **`test_ism_drag.py`** (in-process): K1 anchor (R_mp ~100 km / F_drag ~1–10 kN / a ~1e-3 @ 10³ t;
  `drag_scaling_note` present; β-halving ~2.5× drag drop; stopping-distance/time closed form + the
  `--velocity-final-kms`-without-mass error), K2 anchor (pp → brake once drag/η folded in; low-β+high-η
  → drive; crossover reported/null), `v_e = √(2ηf c²)` ≈ 0.12c for pp, mean-ion-mass/moment/area math,
  the full validation matrix, near-field warning, bundled-table golden pins, determinism.
- **`test_query_ism_drag.py`** (subprocess, mirrors `test_query_propulsion.py`): happy-path JSON +
  core-parity for both; curated-error exit-1 matrix (bad anchors / β=1 / unknown fuel / final-velocity-
  without-mass / two velocity anchors handled as exit 1 or 2 per grouping); argparse exit-2 matrix
  (velocity mutex, non-numeric, bad `--fuel`).

---

## 7. Order of work (on approval)

1. **WebSearch research pass** — pin `k`, `C_d`, fusion `f` (cross-check propulsion_tables), `η`, mean
   ion mass, default `n`; transcribe with citations into the table header. *(Locked — decided
   "WebSearch-confirm before coding", not defaults.)*
2. Add `_MU_0` / `_M_PROTON` to `core/equations.py`.
3. Write `core/ism_drag_tables.py` (constants + provenance).
4. Write `core/ism_drag.py` (both functions; analytic stopping law + bisection crossover).
5. Wire `query.py` (2 handlers + 2 parser blocks).
6. Write both test files; run the two new suites + the full offline suite (no regressions).
7. Docs: `integration.md` (rows + section), `gui-architecture.md` (completion row).
8. Flip the request file to `Deprecated — FULFILLED` (phase letter + as-built shapes + final
   `k`/`C_d`/`η`/`f` values + any requester-flagged deviations, esp. the D-D fraction).

---

## 8. Open items carried (spec §"Open items for the implementing project")

| # | Item | Plan default (research-confirmable at build) |
|---|---|---|
| 1 | Standoff `k`, drag `C_d` | **RESOLVED** — C_d=1.0 (Zubrin & Andrews explicit); k=1.0 (simple balance, hits anchor; compressed factor f=2/2.44 documented for `--standoff-coeff`) |
| 2 | Fusion `f` (pp/cno/dd), scoop `η` | **RESOLVED** — pp/cno 0.0071 (verified), dd 0.0038 (reconciled down from spec's 0.43% → flag requester), η 0.1 low (ideal pp v_e≈0.12c) |
| 3 | Mean ion mass, default `n` | **RESOLVED** — 1.27→1.3 amu / 0.1 cm⁻³ (LIC) via sibling LIE packet; + `ionization_note` (LIC only ~22% H ionized) |
| 4 | `R_mp ≲ R_coil` near-field | `near_field_warning` field (warn, not error) |
| — | Stopping law | analytic closed form (β frozen at v₀); flag single-law estimate |
| — | Crossover velocity | bisection on `F_net(v)`; null + note if no sign change |
