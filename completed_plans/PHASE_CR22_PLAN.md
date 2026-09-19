# PHASE CR-22 PLAN — two-layer exclusion boundary: regulated STANDOFF + research-grade physical WALL

**Status: PLAN (v2, plan-review-hardened) — awaiting Greg's go to build.** Spec: `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR22-exclusion-two-layer-wall.md` (v4 DRAFT). Kit: `.../cr22-handoff-kit.md`. Q&A: channel MSG 238–240 (all answered). Two plan-review agents (architect + spec-fidelity) run against v1; every finding folded in here — see §16 changelog.

CR-22 gives `exclusion-boundary` (single-body) **and** `exclusion-system` (multi) a **two-layer** output: the unchanged canon **STANDOFF** (`r_ex = 47.5·(M/M☉)^0.4`) plus a second **research-grade physical WALL** (the deeper, inner medium-readability surface), plus off-MS/evolved classification fixes. Five sub-CRs (22.1–22.5).

---

## 0. Governing invariants + WB-confirmed scope

**Two invariants (spec §"Governing invariant"):**
1. **Honest about uncertainty** — every research-grade quantity is a **band with an overridable default**, provenance echoed, `verdict_marginal: true` where a verdict flips near a cut, and a wall is **never** canon (`wall_note` always contains "research-grade").
2. **Every rule states its TRIGGER and full CLASS COVERAGE** — no effect without the flag that fires it; no recognized class without a mapping.

**Confirmed by WB (MSG 240):** Q1 both-subcommand scope (+ `exclusion-boundary` gains `--star-mass-catalog` + `domain`; standoff byte-identical); Q2 **defer** the `--star` vectorial V_ISM derive → ship `V_ISM=26` (`assumed`+flag), `--v-ism` override (WB filed `OQ-SA-EXCL2`); Q3 `--component` takes `class=<sp_type>` or explicit `wind_class=<row>`, bare `class=giant`→`giant_overwindy`, WR/AGB via `otype`; Q4 the "1.38 WD refuse" = the domain-based WD→free-harbor guard (no numeric cap). All 5 assumptions accepted.

**The hard line:** any success-path **standoff** shift = FAILURE. The standoff **numeric** battery is byte-identical **by construction** — we branch around the MS `r_ex` arithmetic and never edit `r_ex = 47.5·M^0.4`.

---

## 1. Architecture (dependency DAG: `exclusion_wall` ← `exclusion_boundary` ← `exclusion_system`)

```
core/exclusion_wall.py   NEW — pure physics + classification (no I/O/net/DB/RNG/time). Imports only core.equations.
                          · wind-class table (15 rows) + classify_domain_wind() tri-state classifier
                          · c_ms_from_bfield() + c_ms band  · compute_wall() (route/band/cap/hazard/verdict_marginal)
core/exclusion_boundary.py   compute_exclusion_boundary()  FROZEN — untouched, still pure r_ex (byte-identical).
                          NEW compute_two_layer_boundary(...) — single-body orchestrator: classify → standoff
                          (calls the frozen fn for MS+evolved; null for windless) → compose wall via exclusion_wall
                          → assemble the two-layer dict. THIS is what query.py calls; the frozen fn stays pure.
core/exclusion_system.py     EXTEND — tri-state domain guard, per-component wall (composed via exclusion_wall in
                          the caller, NOT inside the frozen fn), parallel wall-zone merge, combined-wind, phase.
query.py                 EXTEND — both subparsers gain the CR-22.4 wind/medium flags; exclusion-boundary gains
                          --star-mass-catalog; dispatch resolves identity/class per input path (no physics).
docs/integration.md      EXTEND — additive fields + the domain enum break + the 2 new enum values, both subcommands.
tests/test_cr22.py       NEW — the CR-22 behavior battery.  + additive/guard edits to existing exclusion tests.
```

**MAJOR-7 (architect) adopted:** the ~10 wind/medium params are **NOT** threaded through the frozen `compute_exclusion_boundary`. The wall is **composed in the caller layer** (`compute_two_layer_boundary` for single-body; `compose_exclusion_system` per component). The evolved **standoff** needs no new params — it is `47.5·M^0.4` on the measured mass; the only composition change is that `_component_rex` stops returning `None` for `evolved` (keeps `None` only for `windless_free_harbor`, preserving Sirius B null). This keeps the frozen generator's arithmetic + signature literally untouched — the single biggest byte-identity de-risk. All new physics + classification lives in pure functions; `query.py` only resolves identity + parses flags.

---

## 2. `core/exclusion_wall.py` — the shared engine (CR-22.3 + 22.4)

### 2.1 Constants (all pinned in the spec; verified correct)
`_WDOT_SOLAR=2e-14`, `_V_SUN=400`, `_WALL_BASE=(4.0,8.0)`, `_R_AP_ANCHOR=120.0`, `_V_ISM_DEF=26.0`, `_C_MS_DEF=20.0`, `_C_MS_BAND=(14.0,22.5)`, `_N_CLOUD_DEF=0.1`, `_CLOUD_T_DEF=6300.0`, `_F_SHOCK_DEF=1.5`, `_M_SHOCK_MIN=1.5`, `_GAMMA_AD=5/3`, `_MU_I=1.4`, `_MU_C=0.6`, `_M_P`/`_K_B` (reuse `core.equations`).

### 2.2 Wind-class table (spec CR-22.4 — 15 rows, verified byte-match)
`_WIND_CLASS = {wind_class: {"wdot","v_wind","t_phase"|None,"mass_loss_source"}}` — solar 2e-14/400/—/astrosphere_wood; quiet 1e-16/400/—/astrosphere_wood; active 1e-13/400/—/astrosphere_wood; a_dwarf 1e-14/700/—/recipe; f_dwarf 5e-15/500/—/recipe; b_hot 1e-8/1200/—/recipe; o_hot 5e-7/1800/—/recipe; wr_overwindy 3e-5/2000/1e5/recipe; subgiant_mild 5e-14/350/1e9/recipe; giant_mild 1e-10/100/1e8/recipe; giant_overwindy(K) 1e-9/30/1e8/recipe; giant_overwindy(M/early-AGB) 1e-7/15/1e6/recipe; agb_overwindy 1e-6/10/1e5/recipe; bsg_overwindy 1e-7/300/1e5/recipe; rsg_overwindy 2e-6/20/1e5/recipe. (K vs M `giant_overwindy` share the string; colour selects the row.)

### 2.3 `classify_domain_wind(sp_type=None, otype=None, class_tag=None, wind_class=None, object_name=None, wind_state=None) -> (domain, wind_class, class_note)`
Tri-state classifier. Reuses `detection._host_class` + `shared.spectral_leading_class(sp, letters=_SP_DISPLAY_LETTERS)` + `detection._LUM_CLASS_RE`; **adds** the I/II/III split, WR, AGB, and the (lum×colour) composite `_host_class` lacks. Precedence:
1. **Explicit `wind_class=<row>`** → use it; domain inferred (subgiant/giant/agb/wr/bsg/rsg→evolved; else main_sequence).
2. **Windless** → `domain=windless_free_harbor`, `wind_class=None`, `class_note`. Fires on: `object_name ∈ {brown-dwarf, rogue-planet}`; `class_tag ∈ {wd, white-dwarf, brown-dwarf, bd, rogue, rogue-planet}`; **`detection._host_class(sp_type) ∈ {white_dwarf, brown_dwarf}`** (covers `D*`, **lum VII**, `L/T/Y`); or sp_type leading D/L/T/Y. (Windless ⇒ no wall regardless of `--v-ism`: Ẇ→0 ⇒ r_ap→0.)
2b. **Subdwarf split (WB MSG 242 Item 2 — three physically-different objects; do NOT lump):** when `detection._host_class(sp) == "subdwarf"`, branch on the leading colour:
   - **hot subdwarf (leading O/B — sdB/sdO)** → **`domain=unmodeled`** (⇐ **new 4th enum value**), `standoff/wall = null`, `class_note = "hot subdwarf — weak radiatively-driven wind, outside the current wind_class model; standoff/wall not computed"`. NOT windless — a hot subdwarf has a weak wind, so don't assert free-harbor accessibility. `forcing_class = null`.
   - **cool subdwarf (leading A/F/G/K/M — lum VI, sd/esd/usd G/K/M; Kapteyn's Star M1VI, Groombridge 1830)** → **`domain=main_sequence`**, colour wind_class (G→`solar`, F→`f_dwarf`, A→`a_dwarf`, K/M→`quiet`); the **MS standoff law applies with NO `standoff_note`** (metal-poor MS fusing stars with winds → a real standoff + small wall). If the mass is L-inverted, flag the usual MS-inversion caveat (cool subdwarfs are sub-luminous → inversion under-estimates mass; a measured mass is preferred).
   (`sdM3.0` — `sd` prefix, no roman lum class — already classifies main_sequence today, matching the pinned anchor; this clause additionally routes an explicit **lum VI** to main_sequence and keeps **sdB/sdO** out of a fabricated sphere via the honest `unmodeled` null.)
3. **Evolved** → `domain=evolved`:
   - lum **IV** → `subgiant_mild`, **EXCEPT colour O → `o_hot`, colour B → `b_hot`** (⇐ spec-fidelity MAJOR: the table's `V/IV,O`/`V/IV,B` rows; O/B subgiants keep the hot wind — flagged to WB as a table-vs-text contradiction, §14).
   - lum **III/II** by colour → G/F `giant_mild` · K/M `giant_overwindy`.
   - lum **I** by colour → O/B/A/F/G `bsg_overwindy` · K/M `rsg_overwindy`.
   - `otype` WR* → `wr_overwindy`; `otype` Mira/C-star → `agb_overwindy`.
   - Composite lum class (`F5IV-V`, Procyon A) → the **more-evolved** class (IV → subgiant_mild).
   - **Bare coarse `--component class=` tags** (no colour): `giant`→`giant_overwindy`, `supergiant`→`rsg_overwindy`, `agb`→`agb_overwindy`, `wolf-rayet`→`wr_overwindy`, `subgiant`→`subgiant_mild` (conservative = larger wall).
4. **Main sequence** → `domain=main_sequence`: lum V (or no lum class) by colour → O `o_hot`, B `b_hot`, A `a_dwarf`, F `f_dwarf`, G `solar`, K/M `quiet` (→ `active` iff `wind_state=="active"` or a flare/UV-Cet `otype`).

`_component_domain` (in `exclusion_system`) stays a **2-tuple** `(domain, class_note)` — a thin wrapper dropping wind_class from `classify_domain_wind` — so its keyword names + `[0]` indexing + every existing unpack site are untouched (⇐ MAJOR-3); its return VALUES become tri-state (the intended enum break). Callers needing wind_class call `classify_domain_wind` directly.

### 2.4 `c_ms_from_bfield(b_field_ug, n_cloud, cloud_temp) -> (c_ms, band)`
`v_A=B/√(4π ρ)`, `ρ=μ_i·m_p·n_cloud`; `c_s=√(γ k T/(μ_c m_p))`; `c_ms=√(v_A²+c_s²)`; band `c_ms ± ~2–3`. Anchor B=3,n=0.095,T=6300 → 20±2.

### 2.5 `compute_wall(...) -> dict`
Inputs: `wdot, v_wind, v_ism, c_ms, n_cloud, r_ex|None, wind_class, t_phase, f_shock, m_shock_min, c_ms_band`.
```
wind_term_lo/hi = √((wdot/2e-14)·(400/v_wind)) × (4, 8)          # AU
r_ap            = 120 · √((wdot/2e-14)·(v_wind/400)·(0.1/n_cloud)) · (26/v_ism)   # AU
M_f = v_ism/c_ms ;  C = 4·M_f²/(M_f²+3)   (γ=5/3, C≤4)
```
Route (spec CR-22.3): `M_f<m_shock_min` → **bow wave** (`wind_term`, "bow wave (M_f<M_shock_min, C≈1)"); `M_f≥min ∧ r_ex ∧ r_ap>r_ex` → **bow_shock** (`wind_term/√C`); `M_f≥min ∧ r_ex ∧ r_ap≤r_ex<f·r_ap` → **bow_shock_marginal** (`verdict_marginal`; `f·r_ap==r_ex` exactly → NOT bind); else (`f·r_ap≤r_ex`, or `r_ex is None`) → `wind_term` (r_ex None ⇒ reason "bow-shock binding untested — no standoff").
**Giant cap** (APP owns the numerics): `cap = min(r_ap, v_wind·t_phase)` when `t_phase` given, else `r_ap`. **Unit conversion pinned:** `v_wind` km/s · `t_phase` yr → AU via `× _SEC_PER_YEAR / _KM_PER_AU·1000`… i.e. `(v_wind_km_s · 3.15576e7 s/yr · t_phase_yr) km / _KM_PER_AU` (⇐ spec-fidelity MINOR; a CP1 check). If selected wall(band-hi) > cap → cap it: `wall_route ∈ {capped_astropause, capped_windtime}`, `wall_band=[min(lo,cap),cap]`, `wall_au=midpoint`, reason names the bound. Cap removes only the naive overshoot (ε Oph ~566–1131 AU uncapped Oort; 37 Oph capped r_ap ~52k AU ≈ 0.8 ly).
`verdict_marginal` = true also if `M_f` over `_C_MS_BAND` [14,22.5] straddles `m_shock_min`, or `f·r_ap` within ~10% of `r_ex`.
Output: `wall_au` (scalar midpoint|null), `wall_band_au [lo,hi]`, `wall_route`, `wall_reason`, `wall_note` ("research-grade / non-canon"), `verdict_marginal`, `r_ap_au`. The caller computes `wall_exceeds_standoff` + `wall_to_standoff_ratio` vs `r_ex` (null if either layer null).
Edge cases: **windless** → caller short-circuits (`wall_au=null`, `wall_route=none_windless`, "windless — free harbor"). **No-wind bare mass** (no wind_class/Ẇ/wind_state) → `wall_au=null`, `wall_route=none_no_wind` (**new enum value**, documented + flagged to WB, §14), "no wind input — wall needs a wind_class or Ẇ" — keeps a bare `--mass-msun` byte-identical + additively null-walled.

---

## 3. CR-22.1 — Free-harbor guard on ALL entry paths
- **Single-body** (`compute_two_layer_boundary`): classify first; `windless_free_harbor` → `standoff_au/r_ex_au=null`, `domain=windless_free_harbor`, `forcing_class="free_harbor"` (additive), `wall_au=null`, `wall_route=none_windless`, `class_note`. Fixes `--object brown-dwarf` (was checkpoint 17.5), `--object rogue-planet` (was optional 4.75), `--spectral-type DA2` (currently ERRORS → now free-harbor), `--star <WD>` (→ free-harbor).
- **Multi**: a `windless_free_harbor` component contributes no sphere + no wall; its real mass still sets the barycenter (Sirius B).
- **Validation (22.1×4):** `--object brown-dwarf`/`rogue-planet` → free-harbor; `--component class=wd` → free-harbor + "white dwarf"; `--spectral-type DA2` → free-harbor.

## 4. CR-22.2 — Evolved-host handling + domain enum split
- **Domain enum** tri-state `{main_sequence, evolved, windless_free_harbor}`. Carried **explicitly** on each component/body — **`exclusion_system.py:310` output-domain inference (`"main_sequence" if r_ex else "out_of_domain"`) is replaced** with the stored domain (⇐ MAJOR-3), since evolved now has an r_ex.
- **`_component_rex`** (exclusion_system.py:100-110): returns r_ex for `main_sequence` **and** `evolved`; `None` only for `windless_free_harbor` (Sirius B stays null).
- **Evolved standoff** = `47.5·M^0.4` on the **measured** mass (catalog/dynamical/asteroseismic), NOT MS L-inversion, + `standoff_note = "mass-law applied outside its canon MS domain (canon: MS-only); research-grade / regulatory assumption"`. No measured mass → the existing informative refusal naming the remedy, **but the mass-free wind-term wall is still emitted** (`wall_reason` "bow-shock binding untested — no standoff").
- **Class-flip:** all giant classes typically flip the wall above the standoff (`wall_exceeds_standoff` true) — `giant_mild` Oort-scale, `giant_overwindy`/`agb`/`rsg`/`bsg` ly-scale; **subgiant does NOT class-flip** (wall inside standoff).
- **Single-body `--star` MS-vs-evolved branch** (⇐ MAJOR-4, byte-identity of ε Eri): `cmd_exclusion_boundary` does one `compute_simbad_lookup` for sp_type/otype → classify. **MS → the existing `_resolve_star_mass_lum(args.star)` path, byte-identical** (it does its own lookup + regions mass math unchanged; the extra classification lookup does not touch the mass math). **Evolved → `stellar_mass.resolve_component_mass` with a designation-carrying spec** (mirror `exclusion_system._single_body_component`, so `--star-mass-catalog` matches Procyon A `* alf CMi`). **Windless → free-harbor.**
- **`--component` (multi):** `_component_domain` tri-state; evolved with a measured mass → standoff; evolved with no mass → informative refusal (mass-free wall still emitted per compose's C1→A tolerance).
- **point_mass semantics (⇐ MINOR-10):** once `evolved` is in-domain, evolved masses + winds **now sum into** `point_mass_r_ex_au` / `wind_in` (windless still excluded); update the module docstring + the "out-of-domain mass never summed" invariant to "windless mass never summed; evolved corroborates."
- **Validation (22.2×6):** δ Pav (0.991) → evolved/subgiant_mild, standoff ≈47 + note; Procyon A (1.478) → 55.5; Procyon B → windless; `--component class=subgiant,mass=0.98` → evolved (NOT MS 47.1); ε Oph (1.85) → evolved/giant_mild, standoff ≈61 + Oort wall + `wall_exceeds_standoff true`; 37 Oph (1.5 est) → evolved/giant_overwindy, standoff ≈56 + capped ly wall; regression: windless intact, WD refuse (null) intact.

## 5. CR-22.3 — The wall as a second output
Per §2.5, composed in the caller. Emitted by default on both subcommands. Load-bearing: `wall_exceeds_standoff` + `wall_to_standoff_ratio`. Evolved runs the same pipeline as MS (wind-term → bow route iff a standoff exists → cap). **Validation (22.3×8):** Sol bow-wave 6/[4,8]+`verdict_marginal`; Barnard's ≲1; **active M-dwarf 9–18 vs Proxima pinned Ṁ<0.2 → ≤3.6 (contrast)**; EV Lac bow_shock 2.5–5.0; δ Pav/Procyon A 6–14; ε Oph Oort; 37 Oph capped 0.8 ly; RSG capped few ly.

## 6. CR-22.4 — Wind/medium inputs, defaults, provenance, double-handling
- **New flags (both subcommands, optional, per-class defaults):** `--wind-speed`, `--v-ism`, `--c-ms` OR `--b-field`, `--n-cloud`, `--cloud-temp`, `--wind-phase-yr`, `--f-shock`, `--m-shock-min`, `--mass-loss-source {astrosphere_wood|recipe|measured_direct}`. Per-`--component` wind keys (`wind_class`, `wind_speed`, `v_ism`, `c_ms`, `b_field`, `n_cloud`, `cloud_temp`, `wind_phase_yr`, `mass_loss_source`) — extend `_parse_component_spec` `_known`/`_num`/`_alias`.
- **Provenance echo:** each input `_provenance ∈ {supplied, wind_state_preset, class_default, b_field_derived, assumed, astrosphere_wood_forced}`; `wall_note` aggregates assumed inputs.
- **Velocity double-handling:** `mass_loss_source==astrosphere_wood` → **force v_wind=400**, ignore `--wind-speed` (echo `wind_speed_provenance: astrosphere_wood_forced`). Defaults: MS `quiet/solar/active`→`astrosphere_wood`; all other rows→`recipe`; bare `--mass-loss-msun-yr`→`recipe`.
- **`--star` V_ISM (Q2/A):** `V_ISM=26` (`v_ism_provenance: assumed` + flag); `--v-ism` overrides; vectorial derive deferred (`OQ-SA-EXCL2`).
- **Validation (22.4×4):** wind-speed 15 vs 1500 (recipe) → 10× wall; `--b-field 3 --n-cloud 0.095 --cloud-temp 6300` → c_ms 20±2 (number+tolerance), re-gate shock at V_ISM 45 (unambiguous); default-driven wall echoes `class_default`+`verdict_marginal`; `--mass-loss-msun-yr 8e-13 --wind-speed 800 --mass-loss-source astrosphere_wood` → `astrosphere_wood_forced` (v held 400).

## 7. CR-22.5 — Multi-star wall merge (a PARALLEL structure)
⇐ MAJOR-6: the wall grouping is **NOT** hung on the standoff zones (a wall union-find can merge components across separate standoff zones). Emit a **parallel top-level `wall_zones` list**, alongside the existing standoff `zones`.
- **Per-component wall** (CR-22.3) composed for every component in `compose_exclusion_system`; ride as additive fields on each standoff-zone component too.
- **Wall union-find** over the **wall-overlap** test `d < (wall_hi_i + wall_hi_j)` at each phase → `wall_zones`. Each wall-zone: `members`, `wall_envelope_au{periastron,apastron}` (union of walls + orbital extent, breathes with `--phase both`; **absent at a phase where walls don't overlap** — report absence, don't assert), `combined_wind_wall_au` (single value on **summed Ẇ**, no phase dependence), `combined_wind_phase` (where sep ≲ walls — the **same** wall-overlap criterion drives combined-wind eligibility, unified per MAJOR-6), `wall_exceeds_standoff` at band-hi.
- **Mixed-domain:** MS/evolved contribute walls; windless none (can sit inside another's wall); giant/AGB/RSG/BSG/WR a large wall that can enclose the companion.
- **Validation (22.5×7):** Sirius A+B → A small, B null, no envelope; α Cen (Wood Ṁ=2) `--phase both` → overlap near peri only, `verdict_marginal`; EZ Aqr-like tight triple → combined_wind; 36 Oph (high-e) → combined_wind + envelope at peri; **70 Oph (Ṁ=100 DANGER)** → per-comp 28–57, envelope all phases, combined 40–80, `wall_exceeds_standoff true` band-hi, bow-shock binds; 61 Cyg (Ṁ=0.5) → no envelope; MS+giant → giant's capped wall not dropped.

## 8. query.py CLI surface
- **exclusion-boundary** (query.py:3281): add `--star-mass-catalog` + the §6 wind flags; `cmd_exclusion_boundary` resolves class/otype per input path (object name / sp_type / SIMBAD sp_type+otype) → calls the NEW `compute_two_layer_boundary`. α default stays 1/3.
- **exclusion-system** (query.py:3305): add the §6 wind flags (system-level) + per-`--component` wind keys.
- **Core signatures (⇐ MINOR-8):** `compose_exclusion_system` (exclusion_system.py:206) and `compute_exclusion_system` (:586) gain the system-level wind/medium params + pass-through to the per-component `compute_wall`.
- No physics in query.py.

## 9. Output contract (docs/integration.md)
Additive (per body/component/zone): `standoff_au` (= `r_ex_au` alias), `standoff_note`, `domain ∈ {main_sequence, evolved, windless_free_harbor, unmodeled}` (⇐ WB MSG 242: `unmodeled` = hot subdwarf / classes outside the wind model, honest null), `class_note` (⇐ MINOR), `wind_class`, `wall_au`, `wall_band_au`, `wall_route`, `wall_reason`, `wall_note`, `verdict_marginal`, `wall_exceeds_standoff`, `wall_to_standoff_ratio`, `r_ap_au`, wind-input echoes + `_provenance`, `v_ism_provenance`, `mass_provenance` (evolved). Parallel `wall_zones` list: `wall_envelope_au`, `combined_wind_wall_au`, `combined_wind_phase`. **Consumer-visible break:** `domain` enum (`out_of_domain` → **4 values** `{main_sequence, evolved, windless_free_harbor, unmodeled}`); `forcing_class` gains `free_harbor`; `wall_route` enum gains **`none_no_wind`** (§14 flag). Document the `OQ-SA-EXCL2` deferral + the honesty invariants.

## 10. Byte-identity strategy — NUMERIC anchors only
⇐ BLOCKER-1 + MAJOR-5. The **byte-identical guard set is the NUMERIC standoff anchors only**: `test_group_q.py` 47.5 / 22.05 / 102.34 / 150.21 / dial / wind / autocal; `test_exclusion_system.py` 63.46 (Sirius A), 48.97/45.72 (α Cen A/B), 62.53 (point-mass), 54.1/65.4 + 66.1/73.9 (long-axes), 20.4824 (Proxima); `test_query_exclusion_system.py` numerics. A **new guard test** asserts the additive fields don't perturb any pinned number, and that an MS component's standoff stays byte-identical when a giant merges into its neighbourhood.
**Expected-update tests (the intended enum break — NOT regressions):** every `domain`-STRING assertion moves here with its new value — Sirius B `out_of_domain`→`windless_free_harbor`; `K0III`/`class=giant`→`evolved`; `K0IV`/`class=subgiant`→`evolved`; `DA2`/`T5`→`windless_free_harbor`; **`sdB`/`sdO`→`unmodeled`** (WB MSG 242 — honest null, not windless); a **lum-VI cool subdwarf (e.g. `M1VI`) → `main_sequence`** (a CHANGE from the current `out_of_domain` — now earns a real standoff; `sdM3.0` stays main_sequence, unchanged); `--object brown-dwarf`/`rogue-planet` → free-harbor (was checkpoint/optional). Any test asserting `--object brown-dwarf`→17.5 / `rogue-planet`→4.75 is updated. `--mass-msun 0.0008` (a bare mass, no class) → stays MS, unchanged.
(There is **no** numeric 1.38 WD cap in exclusion — the WD refuse is the domain guard, mass-independent; Q4.)

## 11. Test plan
- **`tests/test_cr22.py`** (new): (a) `compute_wall` physics — Sol bow-wave/verdict_marginal, Barnard's, EV Lac bow_shock, ε Oph Oort uncapped, 37 Oph capped_astropause, RSG capped, wind-speed 10× scaling, **wind-time-cap unit conversion**, c_ms-from-B 20±2, astrosphere_wood force-400; (b) `classify_domain_wind` full matrix — V×colour, IV (incl. **O/B-IV → o_hot/b_hot**), III/II×colour, I×colour, WR otype, AGB otype, composite F5IV-V, bare giant/supergiant/agb/wolf-rayet defaults, windless incl. **sdB/sdO/lum VI/lum VII**; (c) free-harbor every path; (d) evolved standoff + note + no-mass mass-free wall; (e) domain tri-state; (f) multi-star — envelope/combined-wind/phase (α Cen, 70 Oph, 61 Cyg, Sirius, 36 Oph, **EZ-Aqr tight triple (22.5#3)**, **MS+giant capped-not-dropped (22.5#7)** mocked components), **active-M-dwarf-vs-Proxima contrast (22.3#3)** (⇐ spec-fidelity MINOR: these three now in the offline battery); (g) **MS+giant composed anchor** proving the merge-flip + a byte-identity guard on the MS component (⇐ coverage gap Q5).
- **Extend** `test_query_exclusion_system.py` (additive query-contract fields), `test_group_q.py` (exclusion-boundary wall + free-harbor + domain + the updated `--object` expectations), `test_query_exclusion_system_live.py` (evolved `--star` δ Pav / ε Oph anchors, gated).
- Research-grade cases → **banded** tolerances; standoff cases → byte-identical.

## 12. `/code-review high` checkpoints
- **CP1** (after §2 `exclusion_wall.py` + unit tests): the wall physics (route, C, r_ap, cap incl. **the v_wind·t_phase→AU unit conversion**, verdict_marginal band), the tri-state classifier + full matrix (esp. **O/B-IV** + **sdB/sdO/lumVI/VII**), c_ms-from-B.
- **CP2** (after §3–4 + §8 single-body): `compute_two_layer_boundary` free-harbor + evolved + wall + `--star-mass-catalog` + `domain`; **verify the frozen `compute_exclusion_boundary` is untouched + the MS `--star` ε Eri path byte-identical + Procyon A catalog keying**.
- **CP3** (after §5–7 multi-star): tri-state guard, `_component_rex` evolved change, `:310` domain fix + the 3 unpack sites, the parallel `wall_zones` merge + unified combined-wind criterion, point_mass evolved inclusion.
- **CP4** (final): docs/integration.md contract (incl. the 2 new enum values), full test battery, every input path (`--object`/`--component`/`--star`/`--spectral-type` incl. triples), the honesty/provenance invariants, the standoff numeric battery green.

## 13. Build sequence
1. `core/exclusion_wall.py` + `tests/test_cr22.py` physics/classifier → **CP1**.
2. `core/exclusion_boundary.py` `compute_two_layer_boundary` (frozen fn untouched) + query.py exclusion-boundary flags/`--star-mass-catalog`/dispatch + tests → **CP2**.
3. `core/exclusion_system.py` (tri-state, `_component_rex`, :310, unpack sites, per-component wall, parallel `wall_zones`, combined-wind, phase, point_mass) + query.py flags/`_parse_component_spec` + tests → **CP3**.
4. `docs/integration.md` + full suite + regression guard + CLAUDE.md/docs bookkeeping → **CP4**.
5. Full offline `venv/bin/python -m pytest` green; hand to WB for the live re-gate on every input path.

## 14. Risks / open items — the 3 flagged items are RESOLVED (WB MSG 242, Greg-ruled)
1. **O/B-IV subgiant — RESOLVED: the table wins.** O/B at lum IV → `o_hot`/`b_hot`; only A/F/G/K/M at IV → `subgiant_mild`. (WB confirmed the mapping-rule text was the error.)
2. **`none_no_wind` `wall_route` value — RESOLVED: confirmed.** Kept, documented in integration.md; distinguishes "no wall physically" (`none_windless`) from "no wind data supplied" (`none_no_wind`).
3. **Subdwarfs — RESOLVED: split three ways (not lumped windless).** lum VII/WD → `windless_free_harbor`; cool subdwarf (lum VI) → `main_sequence` + colour wind_class, real standoff, no `standoff_note`; hot subdwarf sdB/sdO → **`unmodeled`** (honest null, weak wind — not free-harbor). Folded into §2.3(2b), §9, §10.
Other: frozen-generator extension (mitigated — frozen fn untouched, wall composed in caller, guard tests); domain enum consumer break (the one intended break); `OQ-SA-EXCL2` (V_ISM auto-derive deferred, WB-side); `f=1.5` owed pin (marginal binders only); Procyon A keying (`* alf CMi`; verified at CP2); research-grade honesty (banded + `wall_note`).

## 15. WB re-gate battery (every input path, sister venv, `--alpha 0.4`)
- **(A) STANDOFF NUMERIC byte-identical:** `--object sun` 47.5; α Cen A 48.9669 / B 45.7214 + bands 54.097/65.168; Proxima 20.4824; Sirius A ~63.46; `--star "epsilon Eridani"` unchanged; single-body 47.5/22.05/102.34/150.21. (Domain-STRING labels change per §10 — expected.)
- **(B) OFF-MS/EVOLVED fixes:** `--object brown-dwarf`/`rogue-planet` → free-harbor; δ Pav/Procyon A → evolved/subgiant_mild 47/55.5 + note; Procyon B → windless; `--component class=subgiant,mass=0.98` → evolved; ε Oph → evolved/giant_mild 61 + Oort wall + `wall_exceeds_standoff true`; 37 Oph → evolved/giant_overwindy 56 + capped ly wall; WD null-r_ex refuse intact (now labeled windless_free_harbor).
- **(C) WALL (banded):** Sol bow-wave 6/[4,8]+`verdict_marginal true`+`wall_exceeds_standoff false`; EV Lac bow_shock 2.5–5.0; active M-dwarf 9–18 vs Proxima ≤3.6; 70 Oph danger (28–57, envelope all phases, combined 40–80, exceeds true); α Cen envelope peri-only; 61 Cyg no envelope.
- Every path: `--object`, `--component`, `--star`, `--spectral-type`, incl. triples via `--component`.

## 16. Plan-review changelog (v1 → v2)
- **Architecture:** wall composed in the caller; `compute_exclusion_boundary` FROZEN (new `compute_two_layer_boundary` orchestrator) — MAJOR-7.
- **Classifier hole fixed:** sdB/sdO + lum VI/VII → windless_free_harbor (was silent MS-sphere fabrication) — MAJOR-2; O/B-IV → o_hot/b_hot (spec table) — spec MAJOR.
- **Byte-identity re-scoped:** NUMERIC anchors only; every domain-STRING anchor moved to expected-update with its new value — BLOCKER-1 + MAJOR-5.
- **Wiring enumerated:** `_component_domain` stays 2-tuple + separate wind_class helper; the 3 unpack sites (:229/:447/:626) + :310 output-domain + the two core signatures (:206/:586) named — MAJOR-3 + MINOR-8.
- **Single-body `--star`:** MS→`_resolve_star_mass_lum` byte-identical, evolved→`resolve_component_mass` w/ designations (Procyon keying) — MAJOR-4.
- **CR-22.5 merge:** parallel `wall_zones` structure + unified combined-wind criterion — MAJOR-6.
- **point_mass:** evolved masses now corroborate (windless still excluded); docstring/invariant updated — MINOR-10.
- **Minors:** `class_note` in the field list; bare supergiant/agb/wolf-rayet defaults; wind-time-cap unit conversion pinned; the 3 re-gate-only validation cases (22.5#3, 22.5#7, 22.3#3) added to the offline battery; zone forcing_class `free_harbor` for all-windless.
- **3 items flagged to WB** (§14) — now **RESOLVED (WB MSG 242, Greg-ruled):** O/B-IV → table wins (o_hot/b_hot); `none_no_wind` confirmed; subdwarfs **split three ways** (lum VII→windless, cool lum-VI→main_sequence real standoff, hot sdB/sdO→new `unmodeled` honest null) — domain enum is now **4 values**.
