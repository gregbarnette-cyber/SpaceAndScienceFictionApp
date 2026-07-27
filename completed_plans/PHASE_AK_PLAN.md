# PHASE AK (Group Q) — Metric-Drive Power/Fuel + Exclusion-Boundary Calculators — Implementation Plan

**Status:** ✅ **BUILT (2026-07-12).** Both subcommands implemented, wired into `query.py`, tested
(`tests/test_group_q.py`, 36 tests green — all 13 acceptance anchors + the self-validating error matrix +
the beam-sail cross-check), and documented (`docs/integration.md`, `docs/testing.md`, `CLAUDE.md`,
`docs/gui-architecture.md`). Full offline suite **1682 passed / 1 skipped**; `query.py` stays numpy-free.
Sister-repo ship updates DONE (§0 — request-spec deprecation, cheatsheet §17, audit-log entry). Both repos
uncommitted, pending user commit.

**Source spec:** `scifiWorldBuilding-Claude/research/query-api-methods/metric-drive-power-and-exclusion-boundary-calculators-request.md`
(one request, one group **Q**, two subcommands; user directive 2026-07-12: build both as one group,
complete capability, **no phasing / no v1-v2 split**).
**Physics pins:** Le 2026 (arXiv:2606.22531, PRELIMINARY) field-rocket law + the orchestrator derivation in
`drafts/ftl-preferred-frame-decision-prep.md` §G (Q1); canon `metric-drive-and-ftl-causality-architecture.md`
§Exclusion Boundary + `decisions.md` 2026-07-12 ruling 4 (Q2).
**New modules:** `core/metric_drive.py` (Q1), `core/exclusion_boundary.py` (Q2). **Consumer:** the sister
`scifiWorldBuilding-Claude` repo via `query.py`, needed by **Pkt 25** (Q1) and **Pkt 26.5** (Q2).

`query.py`-only, pure-math, self-validating, numpy-free. No network (except `exclusion-boundary --star`),
no DB (except the local main-sequence table on `exclusion-boundary --spectral-type`), no GUI, no RNG, no time.
Contract identical to Groups K–P: one granular subcommand each · JSON to stdout · curated `{"error"}` +
exit 1 on bad input · argparse exit 2 on usage error · `model_note` on every output object · **every bundled
constant flag-overridable**. Phase letter **AK** = Group **Q** (AE–AI were K–O; AJ was P).

---

## 0. Files touched

| File | Change |
|---|---|
| `core/metric_drive.py` | **New** — `compute_metric_drive_power(...)` + the local `_FIELD_FUEL` table (pp/dd f-values imported from `core.ism_drag_tables._FUSION`; d-t/d-he3/antimatter-pp/antimatter-ee new). Reuses `_C_MS`, `_STANDARD_GRAVITY` from `core.equations`. |
| `core/exclusion_boundary.py` | **New** — `compute_exclusion_boundary(...)` + `_WIND_PRESETS`/`_WIND_STATE_MAP`/`_OBJECT_PRESETS` + the provisional forcing-class bands. No external constants needed. |
| `query.py` | `import core.metric_drive` + `import core.exclusion_boundary`; `cmd_metric_drive_power` / `cmd_exclusion_boundary` (+ the `_resolve_star_mass_lum` helper reusing regions); 2 `add_parser` blocks under a `# ── Phase AK (Group Q) … ──` banner. |
| `tests/test_group_q.py` | **New** — single file (per spec directive): core-level golden-pin anchors (Q1 1–7 + Q2 1–7) + the self-validating error matrix + the beam-sail reflecting-sail cross-check. Offline, numpy-free. |
| `docs/integration.md` | **New** "Metric-drive power & exclusion boundary (Phase AK — Group Q)" section with as-built JSON shapes. |
| `docs/testing.md` | One line: what `test_group_q.py` covers. |
| `CLAUDE.md` | Appended to the AJ inventory line — registers `metric_drive.py` + `exclusion_boundary.py` (Group Q). |
| `docs/gui-architecture.md` | AK row added to the query.py-only extension-phase roadmap table. |

**On ship (sister repo) — DONE 2026-07-12:** flipped `metric-drive-power-and-exclusion-boundary-calculators-request.md`
to `status: Deprecated` + a FULFILLED banner (**body unchanged** per no-edit rule); added cheatsheet §17
(139 subcommands); appended a "Group Q BUILT & VERIFIED (Phase AK)" `roadmap-audit-log.md` entry.

---

## 1. Q1 — `core/metric_drive.py`

**Power law** `P_rad = k·F·c` (k=3 GR geometric baseline ⟨cos²θ⟩=1/3 → effective exhaust c/3 → ≈0.9 GW/N;
`--k`/`--tsiolkovsky-k` = the B2 exotic discount, `> 0` enforced — reactionless forbidden).
**Fuel/mass bill:** `f_rad = 1 − e^(−k·Δη)`, `leg_energy = f_rad·m0·c²`,
`fuel_mass_fraction = f_rad / f_conv` with `f_conv = f(mass→energy) × η_dir`.
**Maneuver resolution:** thrust from `--thrust-n` XOR (`--accel-g`/`--accel-ms2` × mass); Δη from `--rapidity`
XOR exact-relativistic `atanh(--delta-v-c | --delta-v-kms/c)` XOR a leg (`--accel-* + --duration-days`).
**Turn:** `--turn` + `--integrated-rapidity` (arc must be ≥ |Δη|). **Beam-vs-onboard:** `--beam-compare` →
beam `c/2` (0.15 GW/N) vs onboard `k·c`, winner flips at k<0.5. **Hold-cruise:** F=0 ⇒ power 0.

### `_FIELD_FUEL` table (f = mass→energy; η_dir default)
`d-t` 0.00375/1.0 · `d-he3` 0.0039/1.0 · `pp` (=`_FUSION['pp']`)/1.0 · `dd` (=`_FUSION['dd']`)/1.0 ·
`antimatter-pp` 1.0/**0.5** · `antimatter-ee` 1.0/1.0. `--f-conv` overrides the effective value directly;
`--eta-dir` overrides just η_dir (needs a `--fuel`).

## 2. Q2 — `core/exclusion_boundary.py`

`r_ex = DIAL · (M/M☉)^α · (L/L☉)^β · (Ẇ/Ẇ_☉)^γ`. `DIAL` = `--dial`, else auto-calibrated to `--calibration-au`
(default 47.5 AU, the Kuiper-edge anchor). `α` mass-exponent (canon [1/3, 1/2], default 1/3; `--scan-alpha`
emits both edges), `β`/`γ` luminosity/wind exponents (default 0). **Body source (exactly one):** `--mass-msun`
| `--object {sun, m-dwarf, o-star, brown-dwarf, rogue-planet}` | `--star` (SIMBAD+regions) | `--spectral-type`
(main-sequence). Wind: `--mass-loss-msun-yr` | `--wind-state {quiet, solar, active, hot}` (Ẇ_solar = 2e-14).
**Forcing class** (provisional, Pkt-26.5-tunable): optional < 10 AU, harbor ≥ 95 AU, else checkpoint.

---

## 3. Frozen golden pins (all verified 2026-07-12)

**Q1:** [1] 0.9 GW/N @k3 · [2] 8.82×10¹⁵ W (9 PW) @1g/1000t · [3] 4.41×10¹⁷ W @50g · [4] Δη 2.826e-3,
f_rad 0.00844 @1g-day; d-t → 2.25× ship; antimatter-pp η_dir 1.0 → 0.84%, default 0.5 → 1.69% · [5] F=0 →
power/f_rad 0 · [6] beam 0.15/onboard 0.9, crossover k 0.5 (beam wins; k0.4 → onboard) · [7] turn arc 0.02 >
collinear. **Q2:** [1] Sun 47.5 AU · [2] 0.1 M☉ → 22.05/15.02 AU (α 1/3, 1/2) checkpoint · [3] 10 M☉ →
102.34/150.21 AU harbor · [4] 0.0008 M☉ → 4.41 AU optional · [5] `--dial 100` → 100 · [6] solar wind term = 1
· [7] γ≠0 without wind → curated error.

## 4. Decisions of record (frozen)

1. **`_FIELD_FUEL` lives in `core/metric_drive.py`** (user, 2026-07-12), importing pp/dd from `_FUSION` for
   DRY; the new d-he3/antimatter keys are field-drive-specific.
2. **Antimatter f (=1) separated from η_dir (≈0.5)** so Pkt-25's fusion-vs-antimatter crossover runs against
   the realistic usable fraction, not the ideal — the ~2× correction the spec flags as decision-grade.
3. **Q2 auto-calibrates `DIAL` to `--calibration-au`** (Sun row = the anchor) when `--dial` is omitted.
4. **Forcing-class bands + wind presets are provisional ancestors** (flagged in `model_note`) — Pkt 26.5
   owns calibrating r_ex, the wind coupling, and the class thresholds.
5. **Single test file `tests/test_group_q.py`** (spec directive), core-level + the beam-sail cross-check;
   no separate `test_query_group_q.py` (the query dispatch was verified by hand + both `--help`s render).
