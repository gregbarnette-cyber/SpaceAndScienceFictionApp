# Phase AD — Calculator Completeness Follow-ups (Pkts 16–19)

**Status:** PLANNED (2026-07-02). `query.py`-only, no GUI/CLI-menu/DB/RNG/time (network only where noted:
none new — `active-shield`/`dust-impact`/`pellet-stream`/`orbital-ring`/`volatile-delivery` are all offline).
**Request:** `scifiWorldBuilding-Claude/research/query-api-methods/calculator-completeness-followups-request.md`
(Proposed 2026-07-02).
**Related requests:** `ism-drag-magsail-calculator-request.md` (A1/A3), `cooling-hz-calculator-request.md`
§Out-of-scope (A0 sub-spec), `power-thermal-shielding-calculator-request.md` (C6/C7/C8/C9),
`settlement-transformation-calculators-request.md` (C4/C5), `closed-loop-life-support-calculator-request.md`
(C10), `dust-map-query-request.md` (C11).
**Lineage:** Phase-N/T/U/V/W/X/Y/Z/AA/AB/AC. Same pure-math + isolated-bundled-table pattern as the family.

---

## 0. Why & scope

An audit (2026-07-02) of every Pkt-16–19 calculator vs. the built `query.py` found: all *named*
subcommands shipped, but (1) three implement-everything capabilities did not ship, (2) five candidate tools
were judgment-deferred, and (3) a full-corpus sweep found further deferred enhancements to shipped tools.
This phase builds the full set **before Packet 16 opens**, per the standing "implement everything, no v2
hedges" instruction (a deferral is legitimate only when the excluded thing is a *different consuming tool*
or a *surfaced decision* — never a silent v2).

**15 buildable items + 1 reword + 1 declined.** All decisions locked (user, 2026-07-02).

| Item | Kind | Module(s) | Origin phase |
|---|---|---|---|
| **A0** `cooling-hz --cooling-delay-gyr` (²²Ne pause) | extend | `core/cooling.py` | U |
| **A1** magsail exact on-axis loop field | fix | `core/ism_drag.py` (+tables note) | AC |
| **A2** magsail braking-profile wording | reword only | `core/ism_drag_tables.py` note | AC |
| **A3** `--ionization-fraction` (magsail + ramscoop) | extend | `core/ism_drag.py` | AC |
| **B**  `equilibrium-temp` bare airless T_eq | fix | `core/terraforming.py` | AB |
| **C1** `par-flux --sed {blackbody,real}` | extend + new table | `core/par_flux.py` + `core/par_flux_tables.py` | AA |
| **C2** `pellet-stream` | new subcommand | `core/propulsion.py` | Y |
| **C3** `dust-impact` | new module | `core/dust_impact.py` | AD |
| **C4** `orbital-ring` | new subcommand | `core/megastructure.py` | Z |
| **C5** `volatile-delivery` | new module | `core/volatile_delivery.py` | AD |
| **C6** `shielding-attenuation --particle` (CSDA) | extend + new table | `core/thermal.py` + `core/shielding_tables.py` | V |
| **C7** `shielding-attenuation --layers` | extend | `core/thermal.py` | V |
| **C8** `active-shield` | new module | `core/active_shield.py` | AD |
| **C9** `waste-heat` transient mode | extend | `core/thermal.py` | V |
| **C10** `bioregen-area --crops` mix | extend | `core/life_support.py` | X |
| **C11** route-cost extinction blend | extend | `core/dust_routing.py` | T2 |
| **C12** `spin-comfort` vestibular outputs | **DECLINED** — Pkt-14 four-axis scope-lock stands | — | W |

**Phase letter AD** (umbrella). Each item is also cross-recorded against its origin phase in
`docs/integration.md`; A1/A3 fold back into the Group-K (`ism-drag-magsail`) record.

### Locked decisions (user, 2026-07-02)
1. Phase letter = **AD**.
2. A0 `--distillation-teff-k` **default 5500 K** (0.6 M☉), documented; derive-from-mass is a follow-up.
3. C10 ships the **calorie-split area sum now**; the protein/vitamin-target **LP is a named v2 decision**
   (surfaced, not silently deferred).
4. New isolated modules: `dust_impact`, `volatile_delivery`, `active_shield`. Extend in place: `pellet-stream`
   → `propulsion`, `orbital-ring` → `megastructure`.
5. A1: coil-pair anchor uses the **exact on-axis loop field**; the **moment-only anchor keeps the far-field
   dipole** (no geometry → no exact field), stated in `model_note`.
6. C1: a non-default `--par-band-nm` with `--sed real` **errors** (the bundled f_PAR table is band-fixed) —
   directs to `--sed blackbody`; no silent fallback.
7. C4: **no `_BODIES` table edit** — gravity at the ring radius is `g(r)=g0·(R/r)²` from the existing
   `g0`+`R_km` (GM≡g0·R² if ever needed).

### Boundary guards (bake in; do NOT cross)
- Self-validating throughout: curated `{"error": str}` (exit 1) for out-of-range; argparse (exit 2) for bad
  `choices`/mutex/non-numeric. Every result carries a `model_note`.
- Order-of-magnitude items label themselves: **A0** (pause), **C3** (impact energetics fine; *penetration*
  handed off), **C8** (rigidity cutoff).
- Bundled tables are transcribed-and-cited static data (like `shielding_tables`/`cooling_tables`), isolated in
  a `*_tables.py` sibling; provenance declared in a `_SOURCE`/`_SOURCES` string surfaced in `model_note` +
  `docs/integration.md`.

---

## Build order

**Phase 1 (Pkt-16 gates — cheap, mostly closed-form): B, A1, A2, A3, C6, C7, C9, C8.**
**Phase 2 (new momentum/impact tools): C2, C3.**
**Phase 3 (megastructure/terraforming tools): C4, C5.**
**Phase 4 (table/routing extensions): C1, C10, C11.**
**Phase 5 (largest, needs paper-reading): A0.**

Run each item's two test files (and the touched phase's existing suites) before moving on. Defaults must
keep every existing anchor byte-identical (regression-pin the touched suites).

---

## Testing & validation contract (applies to every item)

Each item's two test files must contain the standard case list below; per-item sections list only the
**specific** cases/rejections beyond this template.

**`tests/test_<module>.py` (in-process):**
1. **Anchors** — assert each numeric acceptance value in that item's *Acceptance* line.
2. **Core-parity** — derived quantities self-consistent (e.g. round-trips, cross-check fields).
3. **Determinism** — same inputs → deep-equal output (no RNG/time).
4. **Validation matrix** — every listed exit-1 case returns a dict with an `"error"` key (never raises).
5. **Table integrity / golden pin** — for items with a new bundled table: assert the transcribed values +
   any closure identity (the `cooling_tables`/`shielding_tables` pattern).
6. **Regression pin** — for *extended* tools: with the new arg omitted/at its default, output is
   byte-identical to the pre-Phase-AD result.

**`tests/test_query_<cmd>.py` (subprocess, mirrors the existing `test_query_*` harness):**
1. **Happy-path** — valid invocation → exit 0, JSON parses, headline keys present.
2. **Core-parity** — subprocess JSON equals the in-process core dict for the same inputs.
3. **Clean-negative** — normal non-success results stay exit 0 (e.g. `verdict:"no-thrust"`,
   `feasible:false`, `reachable:false`), not exit 1.
4. **Exit-1 matrix** — each curated-error case → `{"error"}` on stdout, exit 1.
5. **Exit-2 matrix** — bad `choices`, a real argparse mutex, a non-numeric value, and a missing *required*
   arg → stderr message, exit 2 (do **not** JSON-parse stdout for these).

**Global validation contract:** "exactly one of N anchors" and range checks are **core** checks → exit 1;
only `choices`, `add_mutually_exclusive_group`, `type=float` coercion, and `required=True` are argparse →
exit 2. This matches `par-flux`/`spin-comfort`/`equilibrium-temp`.

---

## Phase 1 — Pkt-16 gates

### B — `equilibrium-temp` bare airless T_eq (`core/terraforming.py`)
Relax the forcing guard from "exactly one" to "**at most one**". In `compute_equilibrium_temp`: if `>1`
forcing form → keep the error; if `0` → skip forcing, `t_surface_k = t_eq`, forcing keys `None`, add
`regime: "airless"`. Tag the existing branches `regime ∈ {"offset","grey","inverse"}`.
- **Acceptance:** `--insolation-wm2 1361 --albedo 0.3` → `t_eq_k≈254.6`, `t_surface_k≈254.6`, no error;
  Mars `589/0.25` → `210.1`; two forms still error; existing forcing cases byte-identical.
- **Validation (exit 1):** `albedo ∉ [0,1)`; **>1** forcing form; no insolation source / both insolation
  sources; `optical_depth < 0`; `target_surface_k ≤ 0`. **0 forcing forms is now VALID** (the fix).
- **Test cases:** airless anchor (`1361/0.3` → `254.6`, `regime:"airless"`, forcing keys `null`); Mars
  airless (`589/0.25` → `210.1`); each existing forcing branch unchanged + carries its `regime` tag
  (offset/grey/inverse) — **regression pin**; two-forms-still-error; query parity + the exit-1 matrix above
  + exit-2 for non-numeric.
- **Files:** `core/terraforming.py`; **flip** the (now-passing) no-forcing case in
  `tests/test_terraforming.py` + `tests/test_query_terraforming.py`; `docs/integration.md`
  `equilibrium-temp` section (+`regime` key).

### A1 + A2 + A3 — magsail/ramscoop completion (`core/ism_drag.py`, `core/ism_drag_tables.py`)
- **A1 (exact on-axis loop field, coil-pair anchor only).** Replace the standoff for the coil path with the
  exact on-axis loop field `B(z)=μ₀·I·R²/(2(R²+z²)^{3/2})`. Solving `B(R_mp)²/2μ₀ = kρv²` is
  **algebraically invertible** (no root-find): `R_mp = sqrt([μ₀ I² R⁴/(8kρv²)]^{1/3} − R²)`. Keep the
  far-field `[μ₀I²R⁴/(8kρv²)]^{1/6}` as a returned cross-check (`magnetopause_radius_farfield_km`). If the
  bracket `< R²` (magnetopause inside the coil) clamp `R_mp` toward `R_coil` and keep an *informational*
  note. **Moment-only anchor keeps the dipole `_standoff_radius_m`** (no geometry). Provide a 1-D monotonic
  root-find as the general fallback so non-unity `standoff_coeff` conventions still resolve. Drop the
  `near_field_warning` correctness caveat (may remain informational).
- **A2 (reword).** Edit `_MODEL_NOTE_MAGSAIL`: remove "first estimate" hedging on the constant-ISM stopping
  distance/time (it is exact); note multi-leg varying-ISM optimization is a separate consuming tool.
- **A3 (`--ionization-fraction`).** Add param (default **1.0**) to `compute_magsail` + `compute_ramscoop`;
  `rho = density*1e6*ion_mass*_AMU_KG*x_ion`; validate `0 < x_ion ≤ 1`; echo `ionization_fraction`. Add the
  flag to both parsers + `cmd_magsail`/`cmd_ramscoop`.
- **Acceptance:** near-field finite drag, no correctness caveat; far-field vs exact agree <1% once
  `R_mp≳3·R_coil`; `--ionization-fraction 0.5` halves drag; default `x_ion=1.0` byte-identical to Phase AC.
- **Validation (exit 1):** all existing (`density/ion_mass/k/cd ≤ 0`; velocity anchor not exactly one; sail
  anchor partial/none/both; `vehicle_mass_t ≤ 0`; `velocity_final` ≥ current / ≤ 0 / without mass) **plus new**
  `ionization_fraction ∉ (0,1]`. Velocity mutex (`--velocity-kms`/`--beta`) stays argparse **exit 2**.
- **Test cases:** A1 — near-field case (`R_mp ≲ R_coil`) returns finite drag with no correctness caveat;
  far-field vs exact <1% once `R_mp ≳ 3·R_coil`; moment-only anchor uses the dipole form (parity vs pre-AC).
  A3 — `x_ion=0.5` halves `drag_force_n` / `collected_mass_flux_kgs`; **`x_ion=1.0` (default) reproduces the
  Phase-AC anchors byte-identically (regression pin)** on both magsail + ramscoop. All existing Phase-AC
  anchors stay green; query exit-2 for the velocity mutex + non-numeric.
- **Files:** `core/ism_drag.py`, `core/ism_drag_tables.py` (notes), `query.py` (2 handlers + 2 parsers);
  extend `tests/test_ism_drag.py` + `tests/test_query_ism_drag.py`; `docs/integration.md` (fold into Group K).

### C6 + C7 + C9 — thermal/shielding extensions (`core/thermal.py`, `core/shielding_tables.py`)
- **C6 (CSDA charged-particle range).** New bundled `_PSTAR_RANGE`/`_ASTAR_RANGE` (proton/alpha CSDA range
  g/cm² vs energy MeV) transcribed from **NIST PSTAR/ASTAR** + a `_PSTAR_SOURCE`, with `lookup_csda_range()`
  (nearest-energy, like `lookup_mu_rho`). Add `--particle {photon,proton,alpha,ion}` + `--energy-mev`;
  charged particles → `csda_range_gcm2`, `csda_range_cm` (with density). Photon path (default) unchanged.
  **Anchor:** 100 MeV proton / water ≈ 10 g/cm² (verify vs PSTAR at build).
- **C7 (multi-layer stacks).** Add `--layers "mat:gcm2, mat:gcm2, …"` → per-layer Lambert–Beer/GCR factor,
  return `layers[]` + `total_attenuation` (product). Single layer reproduces the current single-material result.
- **C9 (`waste-heat` transient).** Add transient mode `--peak-w --mean-w --duty --storage-mass-kg
  --specific-heat-jkgk` → `temp_swing_k=(P_peak−P_mean)·t_on/(m·c)`, `buffer_time_s`. Steady-state path
  unchanged; refrigeration work-penalty stays packet prose.
- **Validation (exit 1):** C6 — `energy_mev ≤ 0`; off-grid material; a charged particle with no energy /
  no bundled range. C7 — malformed `--layers` token; unknown material in a layer; non-positive layer g/cm².
  C9 — incomplete transient set (all of peak/mean/duty/mass/specific-heat required together);
  `peak < mean`; `duty ∉ (0,1]`; non-positive mass/specific-heat. **Exit 2:** bad `--particle` choice.
- **Test cases:** C6 — **PSTAR 100 MeV proton/water ≈ 10 g/cm²** anchor; `csda_range_cm` with density;
  new range-table **golden pin + closure**; photon default path byte-identical (**regression pin**).
  C7 — **single layer == the current single-material result (parity)**; two layers = per-layer product;
  order-independence of `total_attenuation`. C9 — `temp_swing_k`/`buffer_time_s` anchors; steady-state path
  unchanged; query exit-1/exit-2 matrices.
- **Files:** `core/thermal.py`, `core/shielding_tables.py`, `query.py` (extend `cmd_shielding_attenuation` +
  `cmd_waste_heat` parsers/handlers); extend `tests/test_thermal.py` + `tests/test_query_thermal.py`;
  `docs/integration.md` (both sections).

### C8 — `active-shield` (new `core/active_shield.py`)
New subcommand. Given a magnetic dipole moment (or field×scale) → **rigidity cutoff** `R_c` (GV) below which
particles deflect, the deflected fraction of a supplied GCR/SEP rigidity spectrum, and a field/mass estimate.
Reuse the A1 on-axis loop-field closed form (factor a small shared helper in `ism_drag` or duplicate).
- **Output:** `{rigidity_cutoff_gv, deflected_fraction, magnetic_field_t, model_note}`.
- **Verify at build:** cite a published active-shield study for the order-of-magnitude anchor.
- **Validation (exit 1):** non-positive moment / field / scale; `deflected_fraction` requested with no
  supplied spectrum; the anchor-count rule (exactly one field source). **Exit 2:** non-numeric.
- **Test cases:** `rigidity_cutoff_gv` order-of-magnitude vs the cited study; `deflected_fraction` monotone in
  `R_c` and ∈ [0,1]; determinism; query happy-path + exit-1/exit-2 matrices.
- **Files:** new `core/active_shield.py`, `query.py` (handler + parser), new `tests/test_active_shield.py` +
  `tests/test_query_active_shield.py`; `docs/integration.md` new section.

---

## Phase 2 — new momentum / impact tools

### C2 — `pellet-stream` (`core/propulsion.py`)
`compute_pellet_stream(stream_velocity_kms, mass_flow_rate_kgs=None, pellet_mass_kg=None,
pellet_rate_hz=None, velocity_kms=None, beta=None, coupling="reflect", vehicle_mass_t=None)`. `u=v_s−v`;
`g=2`(reflect)/`1`(absorb); `F=g·ṁ·u`; `P=½ṁu²`; `verdict="drive" if v_s>v else "no-thrust"`;
`crossover=v_s`; `a=F/M`. Mass-flow anchor = `--mass-flow-rate-kgs` **or** (`--pellet-mass-kg`+`--pellet-rate-hz`).
Velocity = `--velocity-kms`/`--beta` (argparse mutex). Mass analog of `ramscoop` — mirror its structure.
- **Output:** `{stream_velocity_kms, vehicle_velocity_kms, relative_velocity_kms, mass_flow_rate_kgs,
  coupling, thrust_n, delivered_power_w, verdict, crossover_velocity_kms, acceleration_ms2, model_note}`.
- **Anchor:** `v_s 30000, ṁ 1, β 0.05, reflect` → `u≈15000 km/s`, `F≈3.0×10⁷ N`; `β 0.1` → `no-thrust`, F→0.
- **Validation (exit 1):** `stream_velocity_kms ≤ 0`; mass-flow anchor not exactly one (partial
  pellet-mass/rate pair); velocity anchor not exactly one; `β ∉ (0,1)`; `vehicle_mass_t ≤ 0`. **Exit 2:**
  velocity mutex, bad `--coupling` choice, non-numeric.
- **Test cases:** drive anchor (`F≈3.0×10⁷ N`, `verdict:"drive"`); **`v=v_s` → `verdict:"no-thrust"`,
  `thrust_n→0` at exit 0 (clean-negative)**; `absorb` (g=1) = half the `reflect` thrust; `acceleration_ms2`
  `null` without `--vehicle-mass-t`; the two mass-flow anchors agree; query mutex/choices exit 2.
- **Files:** `core/propulsion.py`, `query.py`; extend `tests/test_propulsion.py` +
  `tests/test_query_propulsion.py`; `docs/integration.md`.

### C3 — `dust-impact` (new `core/dust_impact.py`)
`compute_dust_impact(grain_radius_um=None, grain_density_kgm3=None, grain_mass_kg=None, velocity_kms=None,
beta=None, dust_density_m3=None, frontal_area_m2=None, path_length_ly=None)`. `m=(4/3)πr³ρ` or explicit;
KE non-rel `½mv²`, rel `(γ−1)mc²` (auto when β>~0.01); momentum `mv`/`γmv`; TNT-kg `=E/4.184e12`; cumulative
`N=n·A·L`, fluence `=N·E/A`. **No penetration depth** — `penetration_handoff_note` → Pkt-13
`shielding-attenuation`/`radiator-area`. Reuses `_C_MS`, `_LY_M`(=`_C_MS·_SEC_PER_YEAR`) from `core.equations`.
- **Output:** `{grain_mass_kg, velocity_kms, beta, relativistic, impact_energy_j, impact_energy_tnt_kg,
  momentum_kgms, impacts_total, energy_fluence_j_m2, penetration_handoff_note, model_note}`.
- **Anchor:** 1 µm / 1000 kg·m⁻³ grain (`m≈4.19e-15 kg`) at β 0.1 → `E≈1.9×10² J` (~40 mg TNT); β 0.2 → rel
  begins; fluence scales linearly with `n·A·L`; no penetration key.
- **Validation (exit 1):** grain anchor not exactly one (radius+density pair vs `grain_mass_kg`); non-positive
  radius/density/mass; velocity anchor not exactly one; `β ∉ (0,1)`; a **partial** cumulative set (need all of
  `dust_density_m3`+`frontal_area_m2`+`path_length_ly`, or none). **Exit 2:** velocity mutex, non-numeric.
- **Test cases:** 1 µm anchor (`E≈1.9×10² J`, `impact_energy_tnt_kg` cross-check); `relativistic:false` at
  β 0.05, `true` at β 0.2 (auto-switch boundary); momentum `mv` vs `γmv`; **fluence linear in `n·A·L`**;
  cumulative keys `null` when the set is omitted; **`penetration_*` absent + `penetration_handoff_note`
  present**; query exit-1/exit-2 matrices.
- **Files:** new `core/dust_impact.py`, `query.py`, new `tests/test_dust_impact.py` +
  `tests/test_query_dust_impact.py`; `docs/integration.md`.

---

## Phase 3 — megastructure / terraforming tools

### C4 — `orbital-ring` (`core/megastructure.py`, uses `materials_tables._BODIES`)
`compute_orbital_ring(body=None, surface_gravity_ms2=None, body_radius_km=None, altitude_km,
ring_mass_per_length_kgm, rotor_mass_per_length_kgm=None)`. `r=R+alt`; `g=g0·(R/r)²`; `v_orb=√(gr)`;
`v_rotor=√(r·g·(1+λ_ring/λ_rotor))` (λ_rotor default=λ_ring → √2·v_orb); `rotor_ke_per_length=½λ_rotor v_rotor²`;
feasibility note (rigid shells → statite case, ref `dyson-collector`). Body from `_BODIES` (`g0`,`R_km`) or
explicit `--surface-gravity-ms2`+`--body-radius-km`.
- **Output:** `{orbital_radius_km, local_gravity_ms2, orbital_velocity_kms, rotor_velocity_kms,
  rotor_velocity_over_orbital, rotor_ke_per_length_jm, support_ratio, model_note}`.
- **Anchor:** Earth, alt 300 km, λ_rotor=λ_ring → `v_orb≈7.7`, `v_rotor≈10.9 km/s`, ratio≈1.414; doubling
  λ_ring (rotor fixed) raises `v_rotor` by `√1.5≈1.22×`.
- **Validation (exit 1):** body anchor not exactly one (bundled `--body` vs explicit
  `--surface-gravity-ms2`+`--body-radius-km` pair, or a partial pair); unknown `--body`; non-positive
  `altitude_km` / `ring_mass_per_length_kgm` / `rotor_mass_per_length_kgm` / g / R. **Exit 2:** bad `--body`
  choice, missing required `--altitude-km`/`--ring-mass-per-length-kgm`, non-numeric.
- **Test cases:** Earth alt-300 anchor (`v_orb 7.7`, `v_rotor 10.9`, `ratio 1.414`); doubling λ_ring →
  `√1.5×`; explicit-body parity vs the bundled `earth` row; `rotor_ke_per_length_jm` cross-check; query
  exit-1/exit-2 matrices.
- **Files:** `core/megastructure.py`, `query.py`; extend `tests/test_megastructure.py` +
  `tests/test_query_megastructure.py`; `docs/integration.md`.

### C5 — `volatile-delivery` (new `core/volatile_delivery.py`)
`compute_volatile_delivery(body_mass_kg, volatile_fraction=0.5, delta_v_kms=None, impact_velocity_kms=None,
target_atmosphere_mass_kg=None, fuel=None, exhaust_velocity_kms=None)`. `m_vol=f·M`; redirect mass ratio via
classical Tsiolkovsky reusing `propulsion_tables` presets + `compute_rocket_equation`; `E=½Mv_impact²`;
`bodies_needed=M_atm_target/m_vol`. Composes rocket-equation + ½mv² + atmosphere-mass.
- **Output:** `{body_mass_kg, volatile_fraction, delivered_volatile_mass_kg, delta_v_kms,
  redirect_mass_ratio, impact_energy_j, impact_energy_tnt_kg, bodies_needed, model_note}`.
- **Anchor:** `M 1e15, f 0.5, v_impact 20` → delivered ≈5e14 kg, `E≈2×10²³ J`; target 5.15e18 →
  `bodies_needed≈10⁴`; `--delta-v-kms 1 --fuel fusion-dt` → modest redirect mass ratio.
- **Validation (exit 1):** `body_mass_kg ≤ 0`; `volatile_fraction ∉ (0,1]`; `impact_velocity_kms ≤ 0`;
  `target_atmosphere_mass_kg ≤ 0`; `delta_v_kms` given with neither `--fuel` nor `--exhaust-velocity-kms`
  (or both); unknown `--fuel`. **Exit 2:** bad `--fuel` choice, non-numeric.
- **Test cases:** anchor (delivered `5e14`, `E≈2×10²³ J`, `impact_energy_tnt_kg` cross-check);
  `bodies_needed≈10⁴` with the target; `redirect_mass_ratio` from `--delta-v-kms`+`--fuel`; **`redirect_mass_ratio`
  / `bodies_needed` `null` when their inputs are omitted**; query exit-1/exit-2 matrices.
- **Files:** new `core/volatile_delivery.py`, `query.py`, new `tests/test_volatile_delivery.py` +
  `tests/test_query_volatile_delivery.py`; `docs/integration.md`.

---

## Phase 4 — table / routing extensions

### C1 — `par-flux --sed {blackbody,real}` (`core/par_flux.py` + new `core/par_flux_tables.py`)
New bundled `_REAL_SED_FPAR` (Teff-indexed f_PAR pre-integrated over the default 400–700 nm band from
**PHOENIX/BT-Settl**; transcribe + cite `_SOURCE`). Add `--sed {blackbody,real}` (default **real**); `real`
interpolates the table. **A non-default `--par-band-nm` with `--sed real` errors** (band-fixed table) —
directs to `--sed blackbody`. Echo `sed_model` accordingly.
- **Acceptance:** `--teff-k 3000 --sed real` → f_PAR **below** blackbody 0.081 (larger deficit); `--sed
  blackbody` reproduces shipped values; Sun `real`≈0.40–0.45.
- **Verify at build:** source/transcribe the spectral-library table (the one real-dataset task).
- **Validation (exit 1):** `--sed real` with a **non-default `--par-band-nm`** (band-fixed table → directs to
  `--sed blackbody`); a `--sed real` Teff off the table grid (or interpolate + flag — decide at build, state
  it); all existing teff/insolation source checks. **Exit 2:** bad `--sed` choice.
- **Test cases:** **`--teff-k 3000 --sed real` → f_PAR < the blackbody 0.081** (larger deficit); `--sed
  blackbody` reproduces the shipped values (**regression pin**); Sun `real` ≈ 0.40–0.45; band-fixed error path;
  new table **golden pin**; query parity + exit-1/exit-2 matrices.
- **Files:** `core/par_flux.py`, new `core/par_flux_tables.py`, `query.py` (parser `--sed`/handler); extend
  `tests/test_par_flux.py` + `tests/test_query_par_flux.py`; `docs/integration.md`.

### C10 — `bioregen-area --crops` diet mix (`core/life_support.py`)
Add `--crops "wheat:0.5, potato:0.3, soybean:0.2"` (fractional calorie split) → per-crop area at each crop's
RUE/HI; `total_area_m2=Σ`, `per_crop_area_m2`. Single crop reproduces the current result. **The
protein/vitamin-target LP is a surfaced v2 decision** (documented, not silently deferred).
- **Validation (exit 1):** malformed `--crops` token; unknown crop in the list; a negative fraction;
  fractions not summing to 1 (**decide at build: reject vs normalize — state it**; recommend reject with a
  clear message). **Exit 2:** non-numeric shared args.
- **Test cases:** **single crop `--crops "wheat:1.0"` == the current single-`--crop` result (parity)**; a mix =
  the calorie-weighted per-crop area sum; `per_crop_area_m2` present + sums to `total_area_m2`; the LP-deferral
  note present in `model_note`; query exit-1/exit-2 matrices.
- **Files:** `core/life_support.py`, `query.py`; extend `tests/test_life_support.py` +
  `tests/test_query_life_support.py`; `docs/integration.md`.

### C11 — route-cost extinction blend (`core/dust_routing.py`, `query.py` route parsers)
Extend `--weight` (`{distance,dust}`) with `blend` + `--alpha`/`--beta`: `cost=α·distance_ly+β·A_V`, fed to
`_grid_search`'s `edge_cost`. **`β=0` reproduces the distance-optimal route** (guarded by the existing route
suites). Deferred (`--max-leg-av`, `jump-network` budget, `farthest-first` dust) stay out per the Pkt-1 note.
- **Validation (exit 1):** negative `--alpha`/`--beta`; `--alpha`/`--beta` supplied without `--weight blend`;
  the dust path's existing preflight (missing dust extra / unfetched map). **Exit 2:** bad `--weight` choice.
- **Test cases:** **`--weight blend --beta 0` reproduces the `--weight distance` route (parity)**; `--alpha 0`
  == the `--weight dust` route; an intermediate blend picks a route between the two; the blend cost fields are
  echoed; query exit-1/exit-2 matrices.
- **Files:** `core/dust_routing.py`, `query.py`; extend `tests/test_dust_routing.py` +
  `tests/test_query_route_opts.py`; `docs/integration.md`.

---

## Phase 5 — A0 (largest; needs literature verification)

### A0 — `cooling-hz --cooling-delay-gyr` (`core/cooling.py`)
Insert a parametric ²²Ne distillation pause into the bundled Bédard WD track. New inputs
`--cooling-delay-gyr` (Δt≥0, default 0 = present behavior) and `--distillation-teff-k` (**default 5500 K**,
documented). In the age-stepping (`_interp_track` / `_residence_at` / the CHZ sweep), detect the age where
Teff crosses the distillation Teff and **hold (Teff,R,L) constant for Δt** before resuming (later ages shift
+Δt; dwell accumulates at the pause luminosity). New outputs `pause_teff_k`, `pause_duration_gyr`,
`pause_hz_inner_au`, `pause_hz_outer_au`; `model_note` = "distillation pause applied, order-of-magnitude".
- **Acceptance:** Δt=0 byte-identical (existing `test_cooling_hz.py` guards); multi-Gyr Δt moves the ≥3 Gyr
  CHZ **outward** and lengthens residence at that farther orbit (Vanderburg 2025 direction).
- **Verify at build:** read Vanderburg 2025's HZ-extension figure for one quantitative pin; confirm the
  0.6 M☉ distillation-onset Teff (Blouin/Bédard).
- **Validation (exit 1):** `cooling_delay_gyr < 0`; `distillation_teff_k ≤ 0`; **`--cooling-delay-gyr` on
  `--track bd`** (distillation is a WD mechanism → reject with a clear message); all existing `cooling-hz`
  checks unchanged. **Exit 2:** non-numeric.
- **Test cases:** **`--cooling-delay-gyr 0` byte-identical to the current output across all three modes
  (regression pin)**; a multi-Gyr Δt shifts mode-3 `chz_outer_au` **outward** and lengthens mode-2
  `residence_gyr` at that farther orbit (Vanderburg direction; pin one quantitative target at build);
  `pause_teff_k`/`pause_duration_gyr`/`pause_hz_inner_au`/`pause_hz_outer_au` present + consistent; the bd-track
  rejection; query parity + exit-1/exit-2 matrices.
- **Files:** `core/cooling.py`, `query.py` (extend `cmd_cooling_hz` + parser); extend `tests/test_cooling_hz.py`
  + `tests/test_query_cooling_hz.py`; `docs/integration.md` (Cooling-primary HZ section) + `PHASE_U_PLAN.md`.

---

## Build-time verification checklist (cite in `docs/integration.md`)
1. **C1** — PHOENIX/BT-Settl Teff→f_PAR table (source + version).
2. **C6** — NIST PSTAR/ASTAR CSDA range values (100 MeV proton/water ≈ 10 g/cm²).
3. **C8** — an active-shield study for the rigidity-cutoff anchor.
4. **A0** — Vanderburg 2025 HZ-extension figure + 0.6 M☉ distillation-onset Teff.
5. **C3/C5** — TNT conversion + impact-energy anchors.

## On completion
Flip each item to `Deprecated — FULFILLED` in the request file with as-built shapes + deviations; fold A1/A3
back into the Group-K record; add the Phase AD row to `docs/gui-architecture.md`'s status table; update
CLAUDE.md's tests bullet list for each touched suite.
