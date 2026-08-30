# Implementation Plan — W1 `salvo-exchange` Doctrine CR-A + CR-B (Packet 38.2)

**Status:** ✅ BUILT + FULFILLED (2026-08-29). Plan reviewed pre-build by 2 forks (spec-fidelity "faithful &
complete" + algorithmic-soundness "math sound, all 3 anchors reproduce"); built through 3 `/code-review high`
checkpoints (CP1/CP2/CP3) + a final pass; full offline suite **3235 passed / 85 skipped / 0 failures**; WB
independent re-gate GREEN (MSG 164); Greg signed the FULFILLED flip (MSG 165) + gave the direct commit
go-ahead. Committed + pushed to `main`. Channel MSG 154–166.
**Source contract:** WB coordination-channel MSG 156 (spec) + MSG 158 (all 12 Q&A pinned, Greg-approved).
**All WB confirms CLOSED (MSG 160):** `--target-agility` default = `agility_ref`; σ-monotonicity δ-only acked; saturation-stream micro-item confirmed; `floor ≤ σ₀` guard approved. 12 Q&A + 3 follow-ups all pinned. No open WB items.
**Scope rule:** complete contract in **one build** — both CRs, every input/output, no phasing / no v2 / no
dropped sub-feature. **Re-gate:** WB re-gates independently on the sister venv over the **full W1 golden-pin
battery + cross-tool anchors** before any FULFILLED flip.

Touch surface (all additive): `core/salvo.py`, `query.py`, `docs/integration.md`, `tests/test_salvo.py`,
`tests/test_query_salvo.py`, `CLAUDE.md`. **No existing mode, field, or 38.1 recompute cell changes.**

---

## 0. Backward-compatibility guarantee (the load-bearing invariant)

1. **New mode absent** → the existing 7 modes are byte-identical (new `MODES` entry + new branch; no shared-path
   edits except new params with inert defaults).
2. **`--light-lag off` (default)** → every existing output is byte-identical. Light-lag is a preprocessing step
   gated on `light_lag=True`; when off, σ/δ enter the engine exactly as today and no new output keys are emitted.
3. **`resolved_inputs` gating is TWO independent conditions (per-group OR), not one flag** (R1-6):
   - CR-A keys (`stream_rings`, `arrival_rate`, `stream_total`, `dwell_intervals`, `profile`) are added **only
     when `mode == "saturation-stream"`**.
   - CR-B keys (`light_lag`, ranges, `target_agility`, `agility_ref`, decays, `decay_scale`, `decay_exponent`,
     floors) are added **only when `light_lag == True`**.
   So a force-mode + `--light-lag on` run echoes the CR-B keys (R3 transparency) while a
   saturation-stream + light-lag-off run echoes the CR-A keys — and a plain existing-mode off-run's dict is
   byte-identical.
4. Pinned by `test_backward_compat_off_is_byte_identical` (full-dict compare on a representative existing call
   with all new params defaulted) + the unchanged existing `test_salvo.py` golden pins.

---

## 1. Locked design (MSG 158) + APP defaulting decisions + review refinements

### CR-A — `saturation-stream` mode

| Item | Resolution |
|---|---|
| Mode | new `"saturation-stream"` appended to `MODES` (→ 8) |
| Ring flag | **new** `--stream-rings "cap:regen:leak, …"` (own parser; `--rings` unchanged) |
| Stream size | `--arrival-rate r` (⇒ `T = r·N`, flat) **XOR** `--stream-total T`; `--dwell-intervals N` **required** in both; both-given = curated error |
| Profile | `--profile {flat,front-loaded,ramp}` default `flat`. flat = T/N; ramp w_i=i; front-loaded w_i=N+1−i (i=1..N, normalized to T; fractional, Σ=T). `--arrival-rate` forces flat, and `resolved_inputs` echoes the **effective** `profile="flat"` (R1-9). |
| Reservoir (per ring, per interval) | `res` init = `cap`; per interval, per ring outermost→inner: `intercepted = min(res, incoming − leak·incoming)`; `survivors = incoming − intercepted`; **fire-then-regen** `res ← min(cap, res − intercepted + regen)`. Reservoirs carry across intervals. |
| σ | **σ-free** (σ=1); σ only via CR-B `--light-lag on` (then σ_eff pre-multiplies arrivals) |
| Target staying | `--target-staying` (optional, >0) → `delta_target = cumulative_leak / target_staying` |
| Outputs | `cumulative_leak`, `per_interval_leak[]` (len N), `per_interval_ring_state[]` (each ring's `res` per interval), `equivalent_pulse_leak`, `duration_advantage = equivalent_pulse_leak − cumulative_leak` (positive = pulse leaks more) |
| `equivalent_pulse_leak` | the **same cap-model** as a **single pulse**: whole T through the rings once, each ring intercepting up to full `cap` (res=cap). NOT a `layered-defense` re-call. |
| Degenerate pin | N=1, regen=0, `cap = δ·b₃`, σ=1 ≡ `layered-defense` survivors_to_target exactly (proven: `incoming − min(cap, incoming−leak·incoming) ≡ max(incoming−cap, leak·incoming)`). |

### CR-B — `--light-lag` σ/δ degradation

| Item | Resolution |
|---|---|
| Gate | `--light-lag {on,off}` default `off` → byte-identical |
| Decay variable | `x = τ` (one-way lag, **seconds**), τ = R/c; `--decay-scale` in **seconds** |
| Agility coupling | `x_eff = τ · (target_agility / agility_ref)`; `--target-agility` (m/s²), `--agility-ref` (m/s²) |
| Laws (σ shown, δ mirror) | `f = floor + (σ₀ − floor)·g(x_eff/scale)`; `linear g = max(0, 1 − x_eff/scale)`; `exp g = exp(−x_eff/scale)`; `power g = (1 + x_eff/scale)^(−k)`, k = `--decay-exponent` |
| σ vs δ threading | **σ = single pre-multiply** by the **engagement-range τ** (`--range-m`, or per-side `--range-a-m/--range-b-m`); **δ = per-ring** by each ring's τ (`--ring-ranges`). Force-on-force: σ_side, δ_side each decay by that side's τ. Layered-defense **σ₀ = the provided `--scouting` value (default 1.0)**, then decayed (R2-4); saturation-stream σ₀ = 1.0. |
| Accepted modes | valid on **{simultaneous, first-strike, sequential-waves, layered-defense, saturation-stream}**; **curated-error** on break-even / solve-force / distribute |
| ring-range order | `--ring-ranges "R1,R2,…"` outermost→inner (R1 = longest = largest τ = most-decayed) |
| Outputs (light-lag on) | `sigma_effective` (scalar/per-side), `delta_effective` (per-ring for ring-mode δ, per-side for force modes), `tau_s[]` (per ring/side), **`light_travel_time_s`** (scalar = the **engagement-range τ**, R1-5; `tau_s[]` carries the per-ring/side detail — reuses the `core/weapons.py` field name), `first_mover_advantage` |
| `first_mover_advantage` | `Δ_second − Δ_first`; "first" = **shorter-effective-τ side for every applicable mode (incl. first-strike)**. Reporting gate: **`null` iff τ is symmetric** (shared `--range-m`, or equal per-side ranges) — gated on **range/τ symmetry, NOT on Δ-equality** (R1-1, R2-5a). Non-zero only under per-side τ asymmetry. It is the **raw** OOA differential, so it **may be negative** when force/α asymmetry outweighs the lag effect (doc note, R2-5b). `null` for the one-sided modes **layered-defense and saturation-stream** (R1-3, R2-6). |
| σ-monotonicity note | The MSG-156 monotonicity anchor ("outer ring σ, δ ≤ inner") is carried by **`δ_eff[]` + `tau_s[]` only**; under B3 σ is a single pre-multiply, so **per-ring σ-monotonicity is N/A** — WB's re-gate should not expect per-ring σ decay (R1-2). |

### APP defaulting decisions (sane, echoed; analyst-overridable per CR-B scope note)

- `--sigma-decay` / `--delta-decay` default **`exp`**; `--decay-scale` default **1.0 s**; `--decay-exponent`
  default **2** (WB-pinned, `power` only); `--sigma-floor` / `--delta-floor` default **0** (WB-confirmed);
  `--agility-ref` default **49.0 m/s²** (WB-pinned).
- **`--target-agility` default = `agility_ref` — CONFIRMED (WB MSG 160)** ⇒ `x_eff = τ` (the neutral pure-lag
  default; WB rejected default-0 as a footgun and rejected require-it). The one default that moves σ/δ numbers,
  now locked.

### Validation additions (from the review pass)

- **`floor ≤ σ₀` guard (R2-1, correctness):** reject (curated error) `sigma_floor > σ₀` and `delta_floor > δ₀`
  — otherwise σ/δ *rise* with lag (e.g. scouting 0.3 + floor 0.5). Checked per side/ring against the actual σ₀/δ₀.
- **`--dwell-intervals` is an int ≥ 1** (R1-4, R2-2; mirrors the `int(n_waves)==n_waves` check) — profile weights
  index i=1..N.
- **`--stream-rings`:** cap ≥ 0, regen ≥ 0, leak ∈ [0,1]; empty → error. `regen > cap` is **allowed and clamped**
  by the `min(cap, …)` recurrence — **documented** in the field note (R1-8).
- **Light-lag range requirements:** `--light-lag on` needs an engagement-range source for σ (`--range-m` or a
  per-side pair); ring modes additionally need `--ring-ranges` for δ (else curated error — no silent τ=0).
- Decay-law valid; `--decay-scale > 0`; `--decay-exponent > 0`; floors ∈ [0,1]; `--agility-ref > 0`;
  `--target-agility ≥ 0`; ranges > 0.

### Micro-item — CONFIRMED by WB (MSG 160)

**saturation-stream + `--light-lag on`:** rings are `cap:regen:leak` (**no δ**) → per-ring δ-decay is vacuous.
Behavior = **σ pre-multiply only** (arrivals × σ_eff, σ₀=1, engagement-range τ); `tau_s[]` still echoed per ring;
`delta_effective` = N/A; `first_mover_advantage` = null. Invents no cap-degradation. **WB confirmed this is intended.**

---

## 2. `core/salvo.py` change map

- **Module:** `MODES` += `"saturation-stream"`; add local `_C_MS = 299_792_458.0` (keep salvo dependency-free,
  mirroring `core/weapons.py`); keep `_MODEL_NOTE` byte-identical (new notes live inside new outputs).
- **New helpers:** `_parse_stream_rings`, `_arrival_profile(total,n,profile)`, `_stream_cascade(arrivals,rings,
  sigma_pre=1.0)`, `_single_pulse_cap_leak(total,rings,sigma_pre=1.0)`, `_decay(base,tau,scale,law,exponent,
  floor,agility,agility_ref)` (with the `floor ≤ base` guard applied by the caller/validator), `_tau(range_m)`.
- **New mode fn:** `_mode_saturation_stream(...)` — validates stream inputs, builds arrivals, runs cascade +
  single-pulse, assembles the CR-A dict; takes `sigma_pre`/`ring_tau` from the light-lag preprocessor (inert defaults).
- **Light-lag preprocessor:** `_apply_light_lag(mode, A, B, rings_parsed, stream_rings_parsed, params)` — reject
  break-even/solve-force/distribute first; compute τ per side/ring, `x_eff`, σ_eff/δ_eff; substitute into A/B
  bundles (force), the ring δ list (layered), or `sigma_pre` (saturation); return the light_lag block
  (`sigma_effective`, `delta_effective`, `tau_s`, `light_travel_time_s`, `first_mover_advantage`).
- **`compute_salvo_exchange` new params (all defaulted/inert):**
  `arrival_rate, stream_total, dwell_intervals, profile="flat", stream_rings,` and
  `light_lag=False, range_m, range_a_m, range_b_m, ring_ranges, target_agility, agility_ref=49.0,
  sigma_decay="exp", delta_decay="exp", decay_scale=1.0, decay_exponent=2.0, sigma_floor=0.0, delta_floor=0.0`.
  Wiring: validate new-modifier ranges → resolve striking → (if light_lag) reject-mode check + `_apply_light_lag`
  → dispatch mode (incl. saturation-stream branch) → attach `resolved_inputs` (per-group gating §0.3) → attach
  light_lag block when `light_lag=True`.

## 3. `query.py` — add the argparse options (all inert defaults); `--mode` auto-includes `saturation-stream` via
`list(salvo.MODES)`; `cmd_salvo_exchange` passes them through and maps `--light-lag on/off` → bool.
## 4. `docs/integration.md` — extend the W1 contract row + detail block (new mode + option, every new field).
## 5. `CLAUDE.md` — one Packet-38.2 summary line under the Phase AT entry.

---

## 6. Test plan (`tests/test_salvo.py` + `tests/test_query_salvo.py`) — existing tests stay green unchanged

**CR-A:** degenerate-reproduces-layered (cap=δ·b₃, N=1, regen=0); hand anchor T=400/N=4/ring 20:20:0 →
320 / 380 / 60; reservoir endpoints (regen=0 one-shot, regen=cap full-recover); **partial-regen** hand-pin;
profiles sum-to-T + shape (ramp↑ / front-loaded↓); arrival-rate ≡ stream-total-flat; duration_advantage sign;
validation (both stream forms, missing/non-int/≤0 dwell, malformed/empty/negative stream-rings, target-staying≤0).

**CR-B:** degenerate scale→∞; degenerate floors=1 (σ₀=1); **τ-band with tolerance** — R=1e9 m → 3.3356 s and
R=3e8 m → ≈1.0 s asserted with `places=2`/`delta` (exact c, R2-3); monotonicity outer-ring δ_eff ≤ inner (δ only,
per the σ-N/A note); first-mover grows with τ; **first-mover null under symmetric τ — one case a *first-strike*
run** (proves strike-order alone doesn't populate it, R1-1); first-mover null for layered-defense &
saturation-stream; per-side ranges give distinct τ_s; agility coupling (agility=agility_ref ⇒ x_eff=τ);
power-exponent curvature; **layered-defense scouting≠1 + light-lag** (σ₀ = the scouting value, decayed, R2-4);
saturation-stream light-lag = σ-only (no δ decay); **`floor > σ₀` → curated error** (R2-1); mode-rejection
(break-even/solve-force/distribute + light-lag → error); missing-range errors.

**Cross-cutting:** `test_backward_compat_off_is_byte_identical` (full-dict); determinism extended to
saturation-stream + light-lag; `test_query_salvo.py` subprocess smoke — `--mode saturation-stream` (exit 0),
`--light-lag on` (exit 0, keys present), rejected-mode `--light-lag on` (exit 1 curated error).

---

## 7. Build sequence + `/code-review` checkpoints (nothing runs until Greg authorizes)

- **Stage 1 — CR-A core** (`_parse_stream_rings`, `_arrival_profile`, `_stream_cascade`,
  `_single_pulse_cap_leak`, `_mode_saturation_stream`, entry branch + `resolved_inputs`) + CR-A tests. →
  **CP1: `/code-review high`** on the CR-A diff.
- **Stage 2 — CR-B core** (`_decay`, `_tau`, `_apply_light_lag`, per-mode σ/δ threading, first_mover, light-lag
  output block, floor-guard, mode-rejection) + CR-B tests. → **CP2: `/code-review high`** on the CR-B diff.
- **Stage 3 — Integration** (`query.py` argparse + cmd; `docs/integration.md`; `test_query_salvo.py`;
  `CLAUDE.md`). → **CP3: `/code-review high`** on the integration diff **+ full suite**
  (`venv/bin/python -m pytest`) — regression gate: existing 7 modes + all 38.1 cells + every prior salvo pin
  byte-identical; light-lag-off byte-identical.
- **Stage 4 — Handoff** — post "built + green" to WB; WB re-gates independently (full W1 golden-pin battery +
  cross-tool anchors); Greg signs one FULFILLED flip; then commit + push + move this plan into the repo as
  `PHASE_AT2_W1_DOCTRINE_CR_PLAN.md`.

---

## 8. Risks / watch-items (post-review; all resolved in plan text or pinned by a test)

- Reservoir recurrence (A2) — **hand-verified** by review (320/380/60); guarded by CP1 + partial-regen test.
- `equivalent_pulse_leak` internal consistency (A3) — **proven** cap-model≡layered algebraically; degenerate test.
- σ pre-multiply vs δ per-ring (B3) — separate paths; scouting≠1 + saturation-σ-only tests guard it.
- **`floor ≤ σ₀`** — the one real correctness guard; now a validation + test.
- `first_mover_advantage` null-gate on τ-symmetry (not Δ) + one-sided-mode null + possible-negative — now
  explicit in the CR-B table + tests.
- Backward-compat — §0 gate + full-dict test.
- **Closed (WB MSG 160):** `--target-agility` default = agility_ref; saturation-stream σ-only; `floor ≤ σ₀`
  guard approved; σ-monotonicity δ-only acked. **No open WB items — plan is build-ready pending Greg's go.**
