# Phase AT (Packet 38.1) — Weapons, defenses & engagement-physics calculators

**Status: COMPLETE — FULFILLED 2026-08-14** (Greg signed off; WB flipped the request file to FULFILLED
after a full independent live re-gate — all pins + cross-tool anchors green, the `sequential-waves`
defender-damage fix + `--defender-preempts` confirmed, zero regressions — MSG 024–032). All 4
calculators + 4 test files built and green (64 tests; the full W1 golden gate + W2/W3/W4 identities
pass; full app suite 2764 passed / 0 failures). Code-review clean (1 pass, 3 fixes applied). The MSG 029
fix made each wave a **simultaneous** exchange (the wave's full salvo damages the defender via a₃, not
just offence-survivors) + added `--defender-preempts`; both new pins (defender_delta 7 and 8.2)
reproduce. Docs updated (`docs/integration.md`, `docs/testing.md`, `CLAUDE.md`, `docs/gui-architecture.md`).
Possible future re-open: Packet 38.2 doctrine layer may request salvo-exchange mode extensions. Four `query.py`-only, pure-math, self-validating calculators for
the sibling `scifiWorldBuilding-Claude` repo, implementing
`research/query-api-methods/weapons-defenses-and-engagement-physics-calculators-request.md` **in
full, no v2/deferral hedges** (its own §"How to read" mandate). No GUI, no CLI menu, no DB, no RNG,
no time, no network, no numpy. Phase-N/T/U…AS lineage.

**All design rulings settled** (WB **MSG 025** + **MSG 027**) — `layered-defense` ruled first-class.
No open design items; ready to build on user green-light. (CP2 pixel-confirm / literature pins are
WB's job, not this packet — see Open items.)

## Provenance & rulings of record

- **Contract:** the request file above. **W1 salvo equations** are reconstructed-and-validated (the
  two source equations are JPEG images `image_rsrc59P/59R.jpeg`; pixel confirmation is WB's CP2 job,
  explicitly non-load-bearing here). The reconstructed forms + Hughes' printed worked results are the
  contract-of-record; hand-verified to reproduce V1/V2/V3/V6/V7 exactly before planning.
- **WB rulings (MSG 025):** `distribute`=(A) subset-only defense; `sequential-waves`=two-sided
  per-wave exchange (**not** one-sided) + `--defender-magazine`; V5 pinned hard from a recovered
  Hughes composite table; W3 crater exponent n=2/3 **relabelled** (spacecraft-shielding regime, not
  gravity-regime), labelled OOM. Whipple Al thresholds tagged *present-day-Al reference*.
- **WB ruling (MSG 027):** `layered-defense`=(A) **first-class dedicated mode** (semantics + 2 golden
  pins below), disjoint from `sequential-waves`. Rationale: it is 38.1 engagement physics (the
  interception-geometry seed's concentric-rings gauntlet), the capability the Exclusions promised, and
  hand-chaining `--leak` K times would violate R3 tool-invocation-transparency for a decision-grade cell.

## Files

| File | Contents |
|---|---|
| `core/salvo.py` | **W1** `compute_salvo_exchange(...)` — Hughes engine + a reusable internal `_resolve_exchange()` that all modes call; the mode dispatch |
| `core/weapons.py` | **W2** `compute_beam_weapon_engagement`, **W3** `compute_kinetic_kill`, **W4** `compute_warhead_effects` |
| `core/weapons_tables.py` | W4 per-channel partition fractions (fission/fusion/antimatter/kinetic-plasma); W3 Whipple Al shatter/vaporize thresholds + reference densities/sound speeds — every row source+confidence tagged, `*-theoretical`/labelled-illustrative, overridable |
| `query.py` | `import core.salvo`, `core.weapons`; 4 `cmd_*` wrappers → `_out(...)`; 4 subparsers |
| `tests/test_salvo.py`, `tests/test_weapons.py` | core acceptance (golden pins + validation matrix + determinism) |
| `tests/test_query_salvo.py`, `tests/test_query_weapons.py` | subprocess contract + exit-code matrix (exit 1 curated / exit 2 argparse) |
| docs | `docs/integration.md` (row + section ×4), `docs/testing.md`, `CLAUDE.md` (core paragraph), `docs/gui-architecture.md` (roadmap row), `completed_plans/README.md` (on completion) |

## W1 — `salvo-exchange` (`core/salvo.py`)

**Base engine** (the internal `_resolve_exchange`, σ/δ/leak included):

```
raw_B = σ_A·α·A − δ_B·b₃·B     eff_B = max(raw_B, L_A·σ_A·α·A)     ΔB = clamp(eff_B / b₁, 0, B)
raw_A = σ_B·β·B − δ_A·a₃·A     eff_A = max(raw_A, L_B·σ_B·β·B)     ΔA = clamp(eff_A / a₁, 0, A)
overkill_* = (eff/staying − force) when > 0
```

**Core signature:**
`compute_salvo_exchange(a_force, b_force, alpha=None, beta=None, a_salvo=None, b_salvo=None,
a_hitprob=None, b_hitprob=None, a1_staying, b1_staying, a3_defense, b3_defense, sigma_a=1.0,
sigma_b=1.0, delta_a=1.0, delta_b=1.0, leak_a=0.0, leak_b=0.0, mode="simultaneous", first=None,
wave_size=None, n_waves=None, defender_magazine=None, target_delta=None, solve_for=None,
fire_fraction=None, rings=None, inbound_salvo=None, target_staying=None)` → dict or `{"error"}`. (`α = a_salvo·a_hitprob` when the salvo/hitprob form is
given; providing both α and the salvo pair → error.)

**Modes (all ship):**
1. **simultaneous** — base case, both salvos vs pre-salvo forces.
2. **first-strike** — `--first` fires full; the struck side's survivors return fire with striking &
   defensive power ×(survivors/force). Reports both pulses + `final_survivors_*`.
3. **sequential-waves** — **two-sided, SIMULTANEOUS per wave (MSG 025 + 029):** attacker commits
   K=`--n-waves` waves of `--wave-size` ships. Each wave is a **simultaneous** base-engine exchange
   vs the **current** defender: the wave's **full already-launched salvo** hits the defender reduced
   only by the defender's **defence a₃** (offence kills wave *ships* but does not suppress the salvo);
   defence **reloads every wave**; defender staying-power hits **accumulate**. `--defender-magazine`
   caps the defender's offensive return salvos (a dry magazine still defends + still takes wave
   damage — shot-your-bolt). `--defender-preempts` = the out-ranging case (offence-survivors only;
   default off). Reports per-wave + cumulative. *(MSG 029 corrected the initial offence-first reading,
   which under-damaged the defender.)*
4. **break-even** — solve `b₁·β·r² + (a₁·b₃ − b₁·a₃)·r − a₁·α = 0` (r = B:A) for equal fractional
   loss; report `break_even_force_ratio` + the governing unit-quality-product statement.
5. **solve-force** — invert: `A = (b₁·target + δ_B·b₃·B)/(σ_A·α)` (or the B-side form). Report
   `required_force_exact` + `integer_wave` (ceil).
6. **distribute** — **RULED (A):** whole salvo onto subset f·B; `ΔB_sub = (σ_A·α·A − δ_B·b₃·(f·B))/b₁`,
   clamp to f·B (no mutual support from un-targeted ships).
7. **leaker** — the `max(…, L·σ·α·A)` floor above; composable with any mode.
8. **layered-defense** — **RULED first-class (MSG 027):** one inbound salvo cascaded through K
   defensive rings (disjoint from `sequential-waves`, which is two-sided attacker-waves). Inbound =
   raw good-shot count **or** `σ·α·A`; optional `--scouting σ` applied once at the front. K rings via
   `--rings "δ:b₃:leak, …"` (the `--let-spectrum` compact-string idiom). Cascade outer→inner:
   `survivors_j = max(incoming_j − δ_j·b₃_j, L_j·incoming_j)`, `incoming_{j+1} = survivors_j`.
   Outputs: per-ring `{incoming, destroyed, leaked}`, `survivors_to_target`, and `delta_target =
   survivors_to_target / a₁` when `--target-staying a₁` given; echo all K resolved `(δ, b₃, L)`
   including defaults (R3).

**Outputs:** `delta_a/b`, `frac_loss_a/b`, `overkill_a/b`, `exchange_ratio` (null + flag when ΔA=0),
`survivors_a/b`; per-pulse/per-wave arrays + `final_survivors_*`; `required_force_exact`/`integer_wave`;
`break_even_force_ratio`; full resolved-input echo incl. defaulted σ/δ/leak (R3); `model_note`.

## W2 — `beam-weapon-engagement` (`core/weapons.py`)

`θ = k·M²·λ/D` via `sensing._rayleigh_theta(λ, D, coefficient=rayleigh_k·M²)`; `d_spot = 2θR`.
`f_on`: top-hat `η·min(1,(s/d_spot)²)` **and** a Gaussian encircled-energy `η·(1−exp(−2(s/2)²/w²))`
(Airy noted in `model_note`; stdlib has no Bessel). `I = f_on·P/A_target`, `A_target=π(s/2)²`.
`t_kill = Φ_kill/I` (Φ_kill supplied, or `enthalpy_jkg × areal_density_kgm2`). `R_eff` at d_spot=s and
at t_kill=max-dwell. Echoes `light_travel_time = R/c`. Frequency↔wavelength accepted.

## W3 — `kinetic-kill` (`core/weapons.py`)

KE classical `½mv²` **and** relativistic `(γ−1)mc²` (compose
`relativity.compute_relativistic_energy_momentum(mass_kg=m, velocity_c=β)`) with a regime flag at
β>0.1; `tnt_equiv_t = KE/4.184e9`; `specific_energy = KE/m`; `momentum` (mv → γmv). Penetration
headline = hydrodynamic long-rod `P ≈ L·√(ρ_i/ρ_t)` (needs rod geometry → null+reason if only mass
given); crater form `P/d ∝ (ρ_i/ρ_t)^0.5·(v/c_t)^n`, **n=2/3 default relabelled** *"hypervelocity
penetration correlation ~v^(2/3), spacecraft-shielding regime (Cour-Palais/MMOD)"* — labelled OOM,
overridable, CP2 pins. Strength-vs-hydrodynamic regime from v vs target sound speed. Monolithic
`perforates` vs `--armor-thickness-m`; Whipple `impactor_shattered` (v vs bundled Al thresholds,
tagged *present-day-Al reference*) + `rearwall_defeated` (spread cloud vs `thermal.compute_shielding_attenuation`).
(Note: `dust_impact` deliberately does NOT do penetration — this is new physics, as the spec expects.)

## W4 — `warhead-effects-at-standoff` (`core/weapons.py`)

`Φ_i = f_i·Y/(4πR²)`; `R_kill,i = √(f_i·Y/(4π·Φ_th,i))`; per-channel + overall `killed_at_range`;
`binding_channel` (largest kill radius). Yield from `--yield-j`/`--yield-kt`. Partition fractions from
a `--warhead-type` default table (bundled, **labelled-illustrative**, source-tagged, per-channel
overridable via `--f-xray/--f-neutron/--f-debris/--f-gamma`). Complete because the fractions are
inputs; `metric-drive-power`/`annihilation-power-train` are the *yield* source (cross-ref, no code
composition).

## Golden-pin gate

**W1 (~15 pins; WB runs the full set at review before scope-lock):**

| Pin | Inputs | Expected |
|---|---|---|
| V1 | A=B=10, α=β=3, a₁=b₁=2, a₃=b₃=2 | ΔA=ΔB=5 |
| V2 | A=10, B=15, else V1 | ΔB=0; ΔA=12.5→clamp 10, overkill 2.5 |
| V3 | β=6, a₁=1, a₃=1, A=3, B=1 | ΔA=3 |
| V4 | V3 with b₁=2 | ΔB halved vs b₁=1 (relational) |
| **V5** | A=7, α_agg=30, a₁=1, a₃=1; per-T β=3.88; solve ΔA=7 | required_force_exact=3.61, integer_wave=4 |
| V6 | A=1, a₃=16, α≈24; enemy β=6,b₃=1,b₁=1 | ΔB/B=1→12 kills; ΔA/A=1→B needs 3–4 |
| V7 | A qual 2× on α/a₃/a₁, B count 2× | parity (equal frac loss) |
| V8 | L=0.10, B fires 12 good ASCMs at A=1 | ≈1 leaker |
| grand-melee | β_agg=97, a₃·S=7, a₁=1 | ΔS=90 → 12.9× (clamp 7) |
| melee | α_agg=30, b₃·T=37.5, b₁=1.5 | ΔT=0 (none hit) |
| distribute-12 | salvo 30 on 12 targets, b₃=1.5, b₁=1.5 | ΔT=8 |
| distribute-10 | salvo 30 on 10 targets | ΔT=10 |
| wave-4 (two-sided) | wave of 4 vs S: (30−1.5·4)/1.5 | 16 → clamp 4, overkill 12 (defender offence) |
| wave-4 defender | wave of 4 vs S=7 (a₃=1.0): (3.88·4−1.0·7) | defender_delta=8.52 → clamp 7, overkill 1.52 (MSG 029) |
| wave defender=simul | S=50 vs 15-wave: (3.88·15−1.0·50) | defender_delta=8.2 = base simultaneous (MSG 029) |
| layered-3ring | inbound 100, 3 rings each δ·b₃=30, L=0.1 | 70→40→10, survivors_to_target=10 |
| layered-saturation | inbound 20, one ring δ·b₃=30, L=0.1 | max(20−30, 2)=2 (leak floor dominates) |

**W2/W3/W4:** θ=1.22λ/D matches `angular-resolution` (cross-tool); `I=P/A`, `t=Φ/I` identities.
KE=½mv² & (γ−1)mc² match `relativistic-energy-momentum` (cross-tool); TNT-equiv conversion (1 kg @
100 km/s → 5e9 J ≈ 1.2 t); ρ-ratio penetration OOM. `Φ=f·Y/4πR²` & `R_kill=√(f·Y/4πΦ_th)` geometric
identities; one worked kt case. Each ships ≥1 anchor independent of its own computation.

## Work sequence

1. `core/weapons_tables.py` (small) → 2. **W2/W3/W4 `core/weapons.py`** (unblocked now) → 3. **W1
`core/salvo.py`** base engine + all settled modes (incl. `--mode layered-defense`) → 4. query.py wiring (4 cmds + 4 subparsers) →
5. tests (4 files) → 6. docs. WB then runs the V1–V8 +
distribute gate live before flipping the spec to FULFILLED.

## Open items

- **CP2 (WB, not this packet):** pixel-confirm the two salvo equation images; pin W4 partition
  fractions + W3 crater exponent against the impact/nuclear-effects literature (they ship as labelled
  overridable defaults until then).
