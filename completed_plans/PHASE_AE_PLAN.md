# Phase AE–AI — Exotic-Physics / Relativity / FTL-Precursor Calculators (Pkts 20–24)

**Status:** PLANNED (2026-07-06). `query.py`-only, no GUI / no CLI-menu / no DB / no RNG / no time /
**no network** (all five groups are closed-form physics on fundamental constants).
**Request:** `scifiWorldBuilding-Claude/research/query-api-methods/exotic-physics-relativity-ftl-calculators-request.md`
(Proposed 2026-07-05; verification pass 2026-07-05 — anchors recomputed from CODATA-2018, 7 numeric errors fixed).
**Lineage:** Phase-U/V/W/X/Y/Z/AA/AB/AC/AD (same pure-math + isolated-constants pattern). Extends the
`lorentz-factor` / `relativistic-brachistochrone` seeds already in `core/calculators.py`.

---

## 0. Why & scope

One combined request, **five groups (K–O) = 28 new `query.py` subcommands**, spanning the Pre-FTL
arrival-geography pass (Pkt 20) and the exotic-vacuum → Alcubierre → causality → black-hole arc (Pkts
21–24). Per the standing user directive (2026-07-05): **build the whole set at once, before Packet 20
opens — no deferral, no v2.** Groups L–O are an entirely new physics layer; Group K is a small
gravitational-geometry top-up over the existing `gravity-*` / `hill-sphere` / `roche-limit` set.

| Group | Phase | Packet | Module | Subcommands |
|---|---|---|---|---|
| **K** — arrival geometry & gravitation | **AE** | 20 | `core/gravitation.py` | `escape-velocity`, `gravitational-potential`, `sphere-of-influence`, `hyperbolic-approach` |
| **L** — relativity & causality | **AF** | 23 | `core/relativity.py` | `time-dilation`, `length-contraction`, `velocity-addition`, `relativistic-doppler`, `rapidity`, `relativistic-energy-momentum`, `lorentz-transform`, `causality-check` |
| **M** — exotic vacuum & cosmology | **AG** | 21 | `core/exotic_physics.py` | `casimir`, `vacuum-energy`, `schwinger-limit`, `hubble-flow` |
| **N** — Alcubierre / metric drive | **AH** | 22 | `core/warp.py` | `alcubierre-energy`, `warp-metric` |
| **O** — black holes & relativistic thermo | **AI** | 24 | `core/black_hole.py` | `schwarzschild-radius`, `hawking-temperature`, `black-hole-evaporation`, `bekenstein-hawking-entropy`, `isco`, `kerr-horizon`, `bh-tidal-force`, `eddington-luminosity`, `unruh-temperature`, `bekenstein-bound` |

### Locked decisions (user, 2026-07-06)
1. **Module layout:** 5 new `core/*` modules (one per group) + one shared helper `core/astro_bodies.py`
   (mass/radius/body-preset resolution reused by K, L-grav, N, O).
2. **Phasing:** group-by-group under phase letters **AE (K) · AF (L) · AG (M) · AH (N) · AI (O)**; each
   group is built, tested green, and committed independently, though all five ship before Packet 20.
3. **Constants:** extend `core/equations.py` only — **no second constants module.** Every bundled
   constant is overridable by a flag.
4. **Author-facing boundary:** these tools compute **real physics**; whether the setting's FTL/metric
   drive *uses* these mechanisms is the packets' job and is **not** asserted by the tools. Every output
   object carries a `model_note` naming the formula, regime, and assumptions.

### Contract (same as Groups F–J / U–AD)
Granular subcommand (house style) · **JSON to stdout** · curated `{"error": "..."}` + **exit 1** on bad
input · **argparse exit 2** on usage error · **self-validating** (Phase-H/P contract) · `model_note` on
every object · all constants flag-overridable · **golden-pin `tests/`** (dual-runner: `venv/bin/python -m
pytest` **and** `python -m unittest discover -s tests`) asserting every acceptance anchor below · new
`core/*` modules, no live dataset · documented in `docs/integration.md` (as-built shapes) + `docs/testing.md`.

---

## 1. Phase 0 — shared infrastructure (prerequisite for all groups)

### 1a. Constants → `core/equations.py`
Already present (reuse): `_G`, `_C_MS`, `_C_KMS`, `_K_B`, `_PLANCK_H`, `_STEFAN_BOLTZMANN`, `_MU_0`,
`_M_PROTON`, `_SOLAR_MASS_KG`, `_EARTH_MASS_KG`, `_EARTH_RADIUS_M`, `_M_PER_AU`, `_KM_PER_AU`, `_LY_M`,
`_SEC_PER_YEAR`.

Add (CODATA-2018, documented inline like the existing block):
- `_HBAR = 1.054571817e-34` — reduced Planck constant, J·s (`_PLANCK_H / 2π`)
- `_M_ELECTRON = 9.1093837015e-31` — electron mass, kg
- `_ELEMENTARY_CHARGE = 1.602176634e-19` — C
- `_EPSILON_0 = 8.8541878128e-12` — vacuum permittivity, F/m
- `_THOMSON_CROSS_SECTION = 6.6524587321e-29` — σ_T, m²
- `_PLANCK_LENGTH = 1.616255e-35` — l_p, m
- `_JUP_MASS_KG = 1.898e27`; `_SUN_RADIUS_M = 6.957e8`; `_JUP_RADIUS_M = 7.1492e7` (1-bar equatorial)
- `_MPC_M = 3.0857e22` — metres per megaparsec
- `_HUBBLE_DEFAULT_KMS_MPC = 67.4`; `_OMEGA_LAMBDA_DEFAULT = 0.685`; `_OMEGA_M_DEFAULT = 0.315`

### 1b. Shared resolver → new `core/astro_bodies.py`
- `resolve_mass(kg=None, msun=None, mearth=None, mjup=None) -> (mass_kg, source)` — exactly one required;
  0/≥2 supplied → `{"error"}`. Non-positive → `{"error"}`.
- `resolve_radius(m=None, rsun=None, rearth=None, au=None) -> (radius_m, source)` — same rule.
- `_BODY_PRESETS` (Sun, Earth, Mars, Jupiter, Moon, Ceres …) → `{mass_kg, radius_m}` for K's `--body`.
- `_OBJECT_PRESETS` (Sun, Sgr A* = 4.15e6 M☉, M87* = 6.5e9 M☉ …) → `{mass_kg}` for O's `--object`.
- These return `{"error"}` dicts on conflict; callers propagate (so the exit-1 contract holds). Argparse
  `type=float` + `choices=` still catch non-numeric / bad-preset at exit 2 before the resolver runs.

> **Design note (for sign-off):** `astro_bodies.py` is the only net-new *shared* infrastructure; the U–AD
> packs are otherwise fully self-contained. Justified here because 4 of 5 groups take the identical
> multi-unit mass flag and the `--body`/`--object` presets must agree across them.

---

## 2. Group K → Phase AE — `core/gravitation.py` (Packet 20)

### K1 — `escape-velocity`
- **Formula:** v_esc = √(2GM/r); v_circ = √(GM/r) = v_esc/√2; specific energy = ½v_esc².
- **Inputs:** mass (`--mass-kg|--mass-msun|--mass-mearth|--mass-mjup`); radius
  (`--radius-m|--radius-rsun|--radius-rearth|--distance-au`); optional `--body <preset>` (fills both).
- **Outputs:** `{escape_velocity_kms, escape_velocity_c, circular_velocity_kms, specific_energy_j_per_kg,
  mass_kg, radius_m, body|null, model_note}`.
- **Anchors:** Earth → **11.19 km/s**; Sun → **617.7 km/s**; Jupiter (1-bar eq. R=71 492 km) → **59.5 km/s**
  (volumetric-mean R → ~60.2; `model_note` states which R the preset uses); Earth surface specific energy
  ≈ **6.26×10⁷ J/kg**.

### K2 — `gravitational-potential`
- **Formula:** Φ = −GM/r (J/kg); well-depth r₁→r₂ = GM(1/r₁ − 1/r₂); binding energy = GMm/r (if payload);
  Δv from the two-point energy (√(2·well_depth)).
- **Inputs:** mass (as K1); `--r-from-m|--r-from-au`; optional `--r-to-m|--r-to-au` (default ∞); `--payload-kg`.
- **Outputs:** `{potential_j_per_kg, well_depth_j_per_kg, binding_energy_j|null, delta_v_kms, model_note}`.
- **Anchors:** Earth surface→∞ = 6.26×10⁷ J/kg (= K1 ½v_esc²); Sun surface→∞ = **1.91×10¹¹ J/kg**.

### K3 — `sphere-of-influence`
- **Formula:** Laplace r_SOI = a·(m/M)^(2/5); report alongside Hill r_Hill = a·(m/3M)^(1/3).
- **Inputs:** `--body-mass-*` + `--primary-mass-*`, `--semimajor-au`; optional `--primary <preset>`.
- **Outputs:** `{soi_laplace_au, soi_laplace_km, hill_radius_au, hill_radius_km, ratio_soi_hill, model_note}`.
- **Anchors:** Earth about Sun → SOI ≈ **0.924×10⁶ km (0.00618 AU)**, Hill ≈ 1.50×10⁶ km; Jupiter → SOI ≈ **4.82×10⁷ km**.

### K4 — `hyperbolic-approach`
- **Formula:** v_p = √(v∞² + 2GM/r_p); C₃ = v∞²; capture Δv = v_p − v_capture (v_capture = √(GM/r_p) for
  circular, √(2GM/r_p) for parabolic, vis-viva for elliptical with `--target-apoapsis`).
- **Inputs:** mass (as K1); `--v-infinity-kms` **or** (`--arrival-speed-kms` + `--r-from`);
  `--periapsis-km|--periapsis-rbody`; optional `--target {circular|parabolic|elliptical}` + `--target-apoapsis`.
- **Outputs:** `{v_periapsis_kms, capture_delta_v_kms, c3_km2s2, v_infinity_kms, periapsis_km, model_note}`.
- **Anchor:** v∞ = 3 km/s at Earth, periapsis = 6771 km → v_p ≈ **11.26 km/s**, capture-to-circular Δv ≈ **3.59 km/s**.

---

## 3. Group L → Phase AF — `core/relativity.py` (Packet 23)

Builds on `calculators.compute_lorentz_factor`; import the γ helper rather than re-deriving.

- **L1 `time-dilation`** — Δt = γΔτ; gravitational √(1−r_s/r); optional `--combined` product.
  Inputs `--velocity-c|--velocity-kms`, one of `--proper-time`/`--coordinate-time`, optional grav
  `--mass`+`--radius`/`--distance`. Anchors: β=0.866 → γ=2.000; β=0.99 → γ≈7.089; Earth-surface grav
  factor ≈ 1 − 6.95×10⁻¹⁰.
- **L2 `length-contraction`** — L = L₀/γ. Anchor: β=0.866 → L = 0.5 L₀.
- **L3 `velocity-addition`** — w = (u+v)/(1+uv/c²); optional `--perpendicular`. Anchors: 0.75c⊕0.75c = **0.96c**; c⊕x = c.
- **L4 `relativistic-doppler`** — longitudinal √((1+β)/(1−β)) / inverse; transverse 1/γ; general `--angle-deg`.
  Optional `--rest-wavelength-nm|--rest-frequency-hz`. Anchors: β=0.6 approach → factor **2.0** (z=−0.5);
  transverse β=0.6 → 0.8.
- **L5 `rapidity`** — φ = artanh(β); `--add "0.6,0.6,0.6"` composes linearly. Anchor: β=0.6 → φ≈0.6931;
  three → φ=2.079 → β≈0.9695.
- **L6 `relativistic-energy-momentum`** — E=γmc², p=γmv, KE=(γ−1)mc², E²=(pc)²+(mc²)². Inputs
  `--mass-kg|--mass-mev` + one of `--velocity-c|--gamma|--kinetic-energy-j|--momentum`. Anchor: proton at
  β=0.99 → γ≈7.089, KE≈**5.72 GeV**.
- **L7 `lorentz-transform`** — t'=γ(t−vx/c²), x'=γ(x−vt); `--inverse`; `--event2` → simultaneity offset
  −γvΔx/c². Inputs SI or `--x-ly --t-yr`. Anchor: β=0.6, event (t=0, x=1 ly) → t'=−0.75 yr, x'=1.25 ly.
- **L8 `causality-check` ⭐** — FTL antitelephone guardrail. Loop possible when **u·v > c²** (β_sig·β_frame > 1);
  v_crit = c²/u. Inputs `--signal-speed-c` (or `--instant`), `--frame-velocity-c`, `--preferred-frame`
  (universal FTL frame → loop removed), `--two-jump`. Outputs `{loop_possible, condition_value,
  critical_frame_velocity_c, margin, preferred_frame_safe, explanation, model_note}`. Anchors: u=2c,v=0.6c
  → 1.2>1 → **loop=true**, v_crit=0.5c; u=2c,v=0.4c → false; `--instant --frame-velocity-c 0.01` → true;
  `--preferred-frame` → preferred_frame_safe=true regardless.

---

## 4. Group M → Phase AG — `core/exotic_physics.py` (Packet 21)

- **M1 `casimir`** — P = π²ℏc/(240 d⁴); F = P·A; u = −π²ℏc/(720 d³); E = u·A·d. `--geometry
  {parallel-plate|sphere-plate}` (sphere-plate ≈ −(π³/360)R/d³). Anchors: d=1 µm → P ≈ **1.30×10⁻³ Pa**;
  d=10 nm → P ≈ **1.30×10⁵ Pa** (∝1/d⁴); u@1 µm ≈ **−4.33×10⁻¹⁰ J/m³**.
- **M2 `vacuum-energy`** — ρ_Λ=Ω_Λ·ρ_crit, ρ_crit=3H₀²/8πG, Λ=8πGρ_Λ/c⁴; QED cutoff estimate + catastrophe
  ratio. Inputs `--omega-lambda` (0.685), `--hubble-kms-mpc` (67.4), `--cutoff {planck|electroweak|qcd|GeV}`.
  Anchors: ρ_Λ ≈ **5.3×10⁻¹⁰ J/m³**; ρ_crit ≈ 7.7×10⁻¹⁰; Planck ratio ~10¹²².
- **M3 `schwinger-limit`** — E_c = m_e²c³/(eℏ); I_c = ½ε₀cE_c². Optional `--field-vm|--intensity-wcm2` →
  ratio. Anchors: E_c ≈ **1.32×10¹⁸ V/m** (B_c ≈ 4.41×10⁹ T); I_c ≈ **2.3×10²⁹ W/cm²** (½ convention;
  `model_note` flags the ~4.6×10²⁹ no-½ convention).
- **M4 `hubble-flow`** — v=H₀·d; binding test via turnaround radius r_ta ≈ (GM/(Λc²/3))^(1/3). Inputs
  `--distance-mpc|--distance-ly` (recession) OR `--mass-msun`+`--radius-ly|--radius-mpc` (binding);
  `--hubble-kms-mpc`, `--omega-lambda`, `--omega-m`. Anchors: d=100 Mpc → v ≈ **6740 km/s**; Local Group
  (~3×10¹² M☉, ~1 Mpc) → bound, r_ta ≈ 1–2 Mpc.

---

## 5. Group N → Phase AH — `core/warp.py` (Packet 22) ⭐ highest risk, build last

### N1 — `alcubierre-energy`
- **`original` (Alcubierre 1994):** compute from T⁰⁰ = −(c²/8πG)·v_s²(y²+z²)/(4r_s²)·(df/dr_s)²;
  total E = −(c²v_s²/12G)·∫₀^∞ (df/dr_s)² r_s² dr_s with the tanh shape function. **Numeric integral in
  plain Python** (Simpson/adaptive — no numpy, to keep query.py fast). Signed J + kg-equiv (E/c²); E ∝ −v_s²R²/Δ.
  > **Erratum 2026-07-11:** the original build used c⁴ (not c²) in the SI energy, an extra factor of c² — so
  > the joule value was reported in the `energy_kg_equiv` field and `energy_j` was that × c². Corrected against
  > the Pfenning–Ford ~¼ M☉ anchor (Δ=1 m). The geometrized→SI conversion is E_SI = E_geom·c⁴/G with v_s→v_s/c,
  > i.e. E = −(c²·v_s²/12G)·∫…. Anchors below updated (they previously "verified the bug against itself").
- **Reduction formulations** (`van-den-broeck`, `krasnikov`, `white`, `bobrick-martire`, `physical-2024`,
  `lentz`): report **published literature figures + source + energy-condition status**, hardcoded, with a
  `model_note` marking them literature values (not per-metric recomputation).
- **Regime flag (Santiago–Schuster–Visser 2021):** any v_s ≥ c → `energy_condition_status =
  "NEC-violating-exotic"`; v_s < c with `bobrick-martire`/`physical-2024` → `"positive-energy-possible"`.
- **Inputs:** `--bubble-radius-m`, `--velocity-c` (allow >1), `--wall-thickness-m`, `--formulation`
  (default `original`), optional `--neck-radius-m` (VdB).
- **Outputs:** `{energy_j, energy_kg_equiv (both signed), formulation, bubble_radius_m, velocity_c,
  wall_thickness_m, subluminal, energy_condition_status, published_figure|null, positive_energy_j|null,
  source, model_note}`.
- **Anchors:** `original` R=100 m, v_s=c, Δ=10 m → |E| ≈ **3.4×10⁴⁵ J** (≈ 3.75×10²⁸ kg-equiv); Δ=1 m →
  **3.4×10⁴⁶ J** ≈ 3.74×10²⁹ kg ≈ **0.19 M☉** (Pfenning–Ford ~¼ M☉) (∝1/Δ).
  `van-den-broeck` → ~few M☉; `krasnikov` → ~few mg; `white` → ~700 kg (10 m/v=10c); `bobrick-martire`
  subluminal → positive-energy. v_s≥c → NEC-violating-exotic.

### N2 — `warp-metric`
- **Formula:** f(r_s) = [tanh(σ(r_s+R)) − tanh(σ(r_s−R))]/[2 tanh(σR)]; θ = v_s·(x_s/r_s)·(df/dr_s);
  `--variant natario` → zero-expansion (θ=0), report divergence-free flow instead.
- **Inputs:** `--bubble-radius-m`, `--wall-thickness-sigma`, `--velocity-c`, optional `--r-eval-m` or `--profile`.
- **Outputs:** `{f_at_r|null, df_dr_at_r|null, theta_at_r|null, wall_inner_m, wall_outer_m, max_expansion,
  max_contraction, profile[]|null, model_note}`.
- **Anchor:** f(0) ≈ 1, f(≫R) ≈ 0, θ antisymmetric front/back.

---

## 6. Group O → Phase AI — `core/black_hole.py` (Packet 24)

- **O1 `schwarzschild-radius`** — r_s = 2GM/c². `--object <preset>`. Anchors: Sun → **2.953 km**; Earth →
  8.87 mm; Sgr A* → ≈ **0.082 AU**.
- **O2 `hawking-temperature`** — T_H = ℏc³/(8πGMk_B); inverse `--temperature-k` → M. Anchors: 1 M☉ →
  **6.17×10⁻⁸ K**; CMB 2.725 K → M ≈ **4.5×10²² kg**.
- **O3 `black-hole-evaporation`** — P = ℏc⁶/(15360πG²M²); τ = 5120πG²M³/(ℏc⁴); inverse `--lifetime-yr` → M.
  Anchors: 1 M☉ → τ ≈ **2.1×10⁶⁷ yr**; M ≈ **1.7×10¹¹ kg** → τ ≈ age of universe (photon-only 5120π
  coefficient; `model_note` states the particle-content assumption).
- **O4 `bekenstein-hawking-entropy`** — S = k_B·A/(4l_p²), A = 4πr_s². `--radius-m` alt input. Anchor:
  1 M☉ → S/k_B ≈ **1.05×10⁷⁷**.
- **O5 `isco`** — Schwarzschild r_ISCO = 6GM/c² = 3r_s; Kerr(a*). `--spin`, `--prograde|--retrograde`.
  Anchors: Schwarzschild 1 M☉ → **8.86 km** (η=5.7%); extremal Kerr prograde → η=**42%**.
- **O6 `kerr-horizon`** — r₊ = (GM/c²)(1+√(1−a*²)); ergosphere r_E = 2GM/c². `--spin`. Anchors: a*=0 → r₊=r_s;
  a*=1 → r₊=GM/c², ergosphere=2GM/c².
- **O7 `bh-tidal-force`** — Δa = 2GM·Δr/r³; at horizon Δa = Δr·c⁶/(4G²M²); `--threshold-g` →
  spaghettification radius. Anchors: 10 M☉ horizon, 1.8 m body → ≈ **2×10⁷ g**; 10⁸ M☉ SMBH horizon →
  ≈ **2×10⁻⁷ g** (radius inside horizon).
- **O8 `eddington-luminosity`** — L_Edd = 4πGM m_p c/σ_T; Ṁ_Edd = L_Edd/(ηc²) (η=0.1). Anchors: 1 M☉ →
  L_Edd ≈ **1.26×10³¹ W** (≈3.3×10⁴ L☉); Ṁ ≈ **1.4×10¹⁵ kg/s**.
- **O9 `unruh-temperature`** — T_U = ℏa/(2πck_B); inverse; `--acceleration-g`. Anchors: a=2.47×10²⁰ m/s² →
  **1 K**; 1 g → 4.0×10⁻²⁰ K.
- **O10 `bekenstein-bound`** — S ≤ 2πk_B RE/(ℏc); I ≤ 2πRE/(ℏc ln2) bits. Inputs `--radius-m` +
  (`--energy-j|--mass-kg`). Anchors: 1 kg/0.1 m → I ≈ **2.58×10⁴² bits**; human (70 kg/1 m) → ≈ **1.80×10⁴⁵ bits**.

---

## 7. Per-group deliverable checklist

For **each** of AE–AI:
1. `core/<module>.py` — self-validating functions + module-level `_MODEL_NOTE`; constants from `equations.py`.
2. Constants added to `core/equations.py` (Phase 0, done once up front).
3. `query.py` — `import core.<module> as <module>`; `cmd_*` handlers; `add_parser` blocks with the
   multi-unit mass/radius flags + presets.
4. `tests/test_<group>.py` (core parity + every anchor) and `tests/test_query_<group>.py` (subprocess
   contract + exit-1-curated / exit-2-argparse matrix), via `tests/_queryharness.py`.
5. `docs/integration.md` — one `### <Group> (Phase A*)` subsection, as-built JSON shapes + bash examples.
6. `docs/testing.md` — descriptions of the two new test files.

On completion of all five:
- Update `research/query-api-methods/query-py-capability-cheatsheet.md` in the consumer repo.
- Add the "PRE-SCOPE-LOCK TOOLING" resolved-marker to the Pkt 20–24 roadmap rows.
- Deprecate-when-fulfilled: mirror the as-built shapes back into the request spec (Groups G–J pattern).

## 7a. Definition of Done (per group — explicit acceptance gate)

A group (AE/AF/AG/AH/AI) is **not** done until **all five** gates pass. These are checkable, not
implicit — run them before declaring a group complete:

1. **Both new test files green on both runners** — `venv/bin/python -m pytest tests/test_<group>.py
   tests/test_query_<group>.py` **and** `venv/bin/python -m unittest tests.test_<group>
   tests.test_query_<group>`. (The dual-runner is the request's contract.)
2. **Full offline suite green — no regressions** — `venv/bin/python -m pytest tests/ -q` (≈110 s;
   1 skip = the `_netcheck`-gated live test). Not a subset — the point is catching unpredicted breakage.
3. **`query.py` stays lean** — `import query` pulls **no numpy** (`'numpy' in sys.modules` is False) and
   `query.py --help` cold-start is unchanged (~0.1 s). Any new heavy import must be lazy-in-handler.
4. **Every subcommand registered** — each appears in `query.py --help`, and every acceptance anchor in
   §2–§6 is asserted by a golden pin (re-derive, don't loosen, if a tool disagrees).
5. **Docs updated** — `docs/integration.md` (as-built JSON shapes + bash + anchors) and `docs/testing.md`
   (the two new test files) both carry the group.

Status: **AE ✓ · AF ✓ · AG ✓ · AI ✓ · AH ✓ — ALL FIVE GROUPS COMPLETE** (all gates met; full-suite
run 2026-07-06 after AH·3: **1608 passed / 1 skipped**). AH was built in 3 checkpoints (AH·1 numeric
core → AH·2 literature ladder + NEC regime flag, independently subagent-verified → AH·3 warp-metric).
All 28 subcommands (K=4, L=8, M=4, O=10, N=2) shipped; query.py still numpy-free.

**Remaining (consumer-repo, cross-repo — awaiting go-ahead):** update
`scifiWorldBuilding-Claude/research/query-api-methods/query-py-capability-cheatsheet.md`, add the
"PRE-SCOPE-LOCK TOOLING" resolved-markers to the Pkt 20–24 roadmap rows, and the deprecate-when-fulfilled
mirror of the as-built shapes back into the request spec.

## 8. Build order
Phase 0 (constants + `astro_bodies.py`) → **AE (K)** → **AF (L)** → **AG (M)** → **AI (O)** → **AH (N)**.
N ships last: it is the highest-risk (numeric integral + literature ladder) and can reuse O's Schwarzschild
helper for the Garattini external-gravity tie-in. Each group is an independent, green-tested commit.

## 9. Key risks
- **N1 numeric integral** must reproduce 3.4×10⁴⁵ J (energy_j; ≈ 3.75×10²⁸ kg-equiv) at (100 m, c, 10 m) and
  scale ∝1/Δ — pin both. (See the N1 Erratum 2026-07-11 on the c²-vs-c⁴ unit correction.)
- **Corrected anchors are golden pins** (Schwinger ½-convention, evaporation 5120π photon-only coefficient,
  tidal Δr·c⁶/4G²M² at horizon). If a tool disagrees with an anchor, **re-derive before shipping** (spec rule).
- **Inverse-solve mutexes** (O2/O3/O9 forward↔inverse, casimir/hubble dual modes, K4 v∞ vs arrival-speed) →
  argparse mutex (exit 2) on conflict, curated exit 1 on out-of-range.
- **`astro_bodies.py` presets** must agree across groups (one `_BODY_PRESETS`/`_OBJECT_PRESETS` source).
