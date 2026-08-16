# Star-Analysis Change-Request Implementation Plan (CR-1 … CR-7)

**Source contract:** `/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-spec.md`
(Draft, 2026-08-15). SpaceApp (`query.py`) owns implementation, sampling, data-source choice, code
structure — the spec pins **inputs / what it computes / validation / output format**, not *how*.

**Framing (user, 2026-08-15):** build **all six/seven CRs at once** — no phasing, no v2, no deferral.
Everything is a `query.py`-only contract for the sibling `scifiWorldBuilding-Claude` consumer (no new GUI
required; CR-2 and CR-5 touch shared readers whose GUI surfaces are additive-safe — see each CR).

**Two coupling points with the WB project (both PINNED in the spec, both built provisional-then-swapped —
✅ 3c FINAL *and* 3a FINAL `v1.1.0` are now BOTH DELIVERED + integrated; the "swap when … lands" notes below
are DONE — see the BUILD STATE section):**
- **Interface A — 3c fissile GCE model → CR-4 fissile output.** WB delivers a versioned static bundle;
  CR-4 implements the documented decay formula from it. Build now with a **provisional bundle**
  (`nuclear_tables._GCE_MODEL_PROVISIONAL`) tuned so the solar anchor validates; swap when 3c lands. ✅ DONE (3c FINAL integrated).
- **Interface B — 3a survey-completeness reference → CR-6 defaults.** WB delivers a static defaults
  table (survey capability by method + magnitude). Build now with a **provisional defaults table**;
  swap when 3a lands. ✅ DONE (3a FINAL `v1.1.0` integrated + CR-6-AMEND).
- **Neither gates the kickoff.** CR-1/2/3/5/7 are fully independent; CR-4/CR-6 build to full function on
  the provisional bundles and only their *finalized* default numbers wait on WB.

**Coordination channel** `/home/greg/Claude/coordination-channel.md` is **idle** (stood down after Phase AT,
MSG 032). Re-open it (append `## MSG NNN · FROM: APP · TO: WB · <topic>`, run a `Monitor`) only for a
planning question the pinned interface shapes didn't anticipate — see **Open decisions** §9. Do not decide
cross-repo ambiguities unilaterally.

---

## 1. Cross-cutting conventions (apply to every CR)

- **Error contract.** Pure-math calculators (CR-4, CR-6, CR-7-core) follow the **Phase-H/P self-validating
  contract**: curated `{"error": str}` → exit 1; argparse rejects bad/missing args → exit 2. Live-network
  readers (CR-1, CR-2, CR-3) follow the **Phase-AM contract**: any failure → `{"error", "route_tried":[…]}`
  exit 1; an **empty-but-valid** result is *not* an error (normal shape, `count:0` / empty list / a `note`).
- **"Non-detection ≠ null" (spec-wide rule).** Every reader that can miss must return an **upper limit or an
  explicit empty with a reason**, never a bare `null`/omission — so the consumer's "graded by
  informativeness" reads work. This is the load-bearing behavioural rule across CR-1, CR-2, CR-5, CR-6.
- **Provenance tags.** Following the Phase-AS precedent, every derived/assumed number carries a provenance
  tag ∈ {`physics-limit`, `present-datapoint`, `policy`, `required-breakthrough`, `extrapolation`,
  `catalogue`}. Interface bundles A/B carry `model_version`/`reference_version` + a `confidence` tag +
  a **domain-of-validity guard** (flag, never clamp/extrapolate past the fit regime).
- **Module placement.** New pure-math packs get their own `core/<name>.py` (+ `core/<name>_tables.py` for
  bundled static data), mirroring `radiation.py`/`salvo.py`/`sensing.py`. Live readers mirror
  `core/catalog.py` / `core/binary.py` (lazy astroquery imports so non-catalog `query.py` calls stay fast
  and offline-importable). `query.py` handlers stay thin wrappers; each `cmd_*` + one `sub.add_parser(...)`
  + `p.set_defaults(func=…)`.
- **Test gating** (`docs/testing.md`). Offline logic/anchor tests run by default (`venv/bin/python -m
  pytest`). Live-network anchors gate on `tests/_netcheck.live_enabled()` (`SPACE_APP_RUN_LIVE=1`) + host
  reachability. Subprocess `query.py` tests use `tests/_queryharness.py` + a throwaway `SPACE_APP_DB`.
- **Docs to update per CR:** `docs/integration.md` (the consumer contract — authoritative), `CLAUDE.md`
  (architecture paragraph), `docs/testing.md` (per-file test descriptions). Live readers also note the
  network class.
- **FULFILLED handshake.** When all 7 land + green, post one channel MSG to WB listing subcommands + anchor
  results; WB re-gates independently; Greg signs off; the request doc flips to FULFILLED (the Phase-AT flow).

---

## 2. CR-7 — Kinematics / population classification  *(build first — pure, feeds CR-4 + CR-5)*

**Goal.** New subcommand returning U/V/W, Toomre velocity, and a **thin/thick/halo verdict + probability**.
The U/V/W *data* is already exposed (`hypatia-data`); the GUI Toomre tab (`make_toomre_canvas`) only *draws*
50/100/180 km/s arcs — **no verdict logic exists anywhere** (confirmed: `prepare_toomre` returns plot coords
+ `total`, and passes Hypatia's `disk` code straight through; no Bensby-style probability in the repo).

**Files.** New `core/kinematics.py` (pure-math, no network for the U/V/W-direct path). Reuse the sole
Schönrich+2010 LSR constant `_SOLAR_MOTION_UVW = (11.1, 12.24, 7.25)` — lift it from `core/viz.py:774` to
`core/shared.py` (or re-import) so viz + kinematics can't drift.

**Core fn.** `kinematics.classify_population(u=None, v=None, w=None, star=None)`:
1. If `star` given and U/V/W not: `databases.compute_simbad_lookup(star)` → `compute_hypatia_data` →
   `properties.u_vel/v_vel/w_vel`. (Live network only on the `--star` path.)
2. LSR-correct (add solar motion). Toomre velocity `T = √(U_lsr² + W_lsr²)`; `V_lsr`; total `√(U²+V²+W²)`.
3. **Membership probability** via the Bensby et al. (2003/2014) TD/D/H scheme: each population has a
   Gaussian velocity ellipsoid (σ_U, σ_V, σ_W, asymmetric drift V_asym) + a local number-density fraction
   X_thin/X_thick/X_halo; `P_pop ∝ X_pop · f_pop(U,V,W)`; verdict = arg-max, `membership_prob` = normalised
   `P`. Bundle the ellipsoid constants in `kinematics.py` (Bensby 2014 Table A1) with a `confidence` tag.
   Cross-check against the GUI's 50/100/180 heuristic band (validation criterion 3).

**Subcommand.** `population-classify` *(NOT `population`/`toomre` — `toomre-q` already exists for disk
stability; distinct name avoids confusion)*. Args: `--star` **xor** (`--u --v --w`, km/s).
**Output:** `{star, u_vel_kms, v_vel_kms, w_vel_kms, toomre_velocity_kms, population: thin|thick|halo,
membership_prob, probabilities:{thin,thick,halo}, provenance}`.

**Validation anchors.** Sun (U/V/W≈0) → **thin-disk**, high prob; a known high-Toomre halo star → **halo**;
verdict agrees with the GUI Toomre band for the same star. Offline tests drive U/V/W directly; one
`SPACE_APP_RUN_LIVE=1` anchor drives `--star`.

---

## 3. CR-4 — Nuclear-fuel & radiogenic inventory  *(build second — pure; Interface A provisional now)*

**Goal.** One calculator emitting three outputs from Hypatia-available scalars: fusion fuel, fissile
fraction (resolves the Q15 method gap), radiogenic heat. Multi-output.

**Files.** New `core/nuclear.py` (pure-math, self-validating) + `core/nuclear_tables.py` (bundled decay
constants + primordial/GCE coefficients + the **provisional 3c bundle** `_GCE_MODEL_PROVISIONAL` in the
pinned Interface-A shape).

**Core fn.** `nuclear.compute_nuclear_inventory(fe_h, age_gyr, eu_h=None, eu_fe=None, star_mass_solar=None,
population=None)`:
1. **Fusion** (`{D_over_H, He3_est, Li6, Li7, B11}`): primordial anchors (BBN D/H ≈ 2.5e-5, ³He) + a
   metallicity/age astration term + a wind-implanted ³He term. Li/B may be labelled from GCE trends;
   provenance `extrapolation`. (Li/B are also Hypatia species — the fusion block computes from the scalar
   inputs per the contract, not by re-reading Hypatia.)
2. **Fissile** (`{U235_frac, U238_frac, Th232_frac, U235_U238_ratio}`): implement the **Interface-A formula
   verbatim, PER-ISOTOPE** (WB MSG 035 refinement — a single scalar enrichment is physically wrong because
   ²³⁵U/²³⁸U accumulate differently in the ISM *before* formation). Per isotope i ∈ {U235, U238, Th232}:
   `N_i,present / N_Eu = (i_over_Eu)_prod × g_i(age, pop, [Fe/H]) × exp(−λ_i·age_gyr)`, where
   `(i_over_Eu)_prod` are **linear** number-abundance ratios (`production_ratios.{U235_over_Eu, U238_over_Eu,
   Th232_over_Eu, U235_over_U238_initial≈1.3, basis}`), `g_i` = `gce_enrichment.factors.{U235,U238,Th232}`
   (`form:"parametric"`, `population_source:"CR-7 verdict"`, `domain`), `λ_i` from `decay_halflives_gyr`. Then
   `U235_frac = N235/(N235+N238)`, `U235_U238_ratio = N235/N238`. `[Eu/H]→linear Eu` first. Reads
   `nuclear_tables._GCE_MODEL_PROVISIONAL` (provisional, per-isotope shape) → swap in the real 3c bundle when
   it lands (one constant change; `provenance.gce_model_version` records which).
3. **Radiogenic** (`radiogenic_heat_W_per_kg`): U+Th+K decay-heat at the star's age, scaled to
   [Fe/H]/abundances, using bundled specific-heat constants (U238 9.46e-5, U235 5.69e-4, Th232 2.64e-5,
   K40 2.92e-5 W/kg-of-isotope) × present isotopic fractions × crustal/BSE reference abundance.

**Subcommand.** `nuclear-inventory`. Args: `--fe-h --age-gyr [--eu-h | --eu-fe] [--star-mass-solar]
[--population thin|thick|halo]`. **Output:** `{fusion:{…}, fissile:{…}, radiogenic_heat_W_per_kg,
provenance:{gce_model_version, confidence, domain_ok}}`.

**Validation anchors** (offline, exact): solar inputs ([Fe/H]=0, solar [Eu/H], age 4.57 Gyr) →
**U-235/U-238 ≈ 0.0072** (the shared Interface-A validation) + solar r-process U/Eu, Th/Eu; a *younger*
star → *higher* U-235/U-238; an r-process-poor star → *lower* absolute U/Th; radiogenic heat ~10⁻¹¹ W/kg
order (BSE). Domain guard flags inputs outside the 3c fit regime rather than extrapolating.

---

## 4. CR-6 — `detection-completeness`  *(build third — pure composition; Interface B provisional now)*

**Goal.** Compose the four existing forward detection calculators, **inverted**, into a per-target
completeness map: min detectable planet (mass M⊕ or radius R⊕) vs orbital SMA (AU), per method.

**Existing forward calculators to invert** (`core/calculators.py`): `compute_rv_semi_amplitude` (K∝Mp →
invert for Mp at the RV precision floor), `compute_transit_signal` (δ=(Rp/R*)² → invert for Rp at the
photometric-precision floor + geometric-probability gate), `compute_astrometric_signal` (α∝Mp → invert for
Mp at the astrometric floor), `compute_direct_imaging` (contrast∝Rp² + IWA=λ/D gate → invert for Rp at the
contrast-curve floor, gated on resolvable).

**Files.** New `core/detection.py` (pure-math core; optional `--star` SIMBAD resolve is the only network) +
bundled 3a defaults in the pinned Interface-B shape in `detection_tables.py` (**built provisional; now the
WB 3a FINAL `3a-v1.1.0` bundle — see BUILD STATE**). Reuse `sensing._rayleigh_theta` for the IWA (as
`compute_direct_imaging` already does).

**Core fn.** `detection.compute_detection_completeness(app_mag, distance_pc, sp_type=None,
star_mass_solar=None, star_radius_solar=None, methods=None, survey_params=None, sma_grid=None)`:
- Derive star mass/radius from `sp_type` (main-sequence ladder — reuse `binary.m1_from_spectral_type` +
  a radius map) when not supplied.
- Per method, per SMA on a log grid: apply the method's survey floor (per-star override → else the
  Interface-B default keyed by `app_mag`) and solve the inverted relation for the min detectable planet.
- Transit returns `"not applicable / not covered"` honestly when not a transit target (spec criterion 2).

**Subcommand.** `detection-completeness`. Args: `--star` **or** (`--app-mag --distance-pc [--sp-type
--star-mass-solar --star-radius-solar]`); optional per-method survey params (`--rv-precision-ms
--rv-baseline-yr --transit-precision-ppm --transit-coverage-days --imaging-contrast …`); `--methods`
subset; `--sma-grid`. **Output:** `{star, methods:[{method, detectable_vs_sma:[{sma_au, min_mass_earth?,
min_radius_earth?}], applicable, floor_source}], assumptions, provenance:{reference_version, confidence}}`.

**Validation anchors** (offline): Sun-like at 10 pc, RV ~1 m/s decade baseline → Earth@1AU **below** floor,
hot-Jupiter **above**; map **monotone** (harder at wider SMA / smaller mass); transit "not applicable" path.

---

## 5. CR-3 — Auto-pipe `binary-orbit` → `binary-stability`  *(build fourth — live composition)*

**Goal.** One call fetches the binary's elements and feeds them straight into Holman-Wiegert stability — no
manual re-entry (the 36 Oph card did this by hand today).

**Files.** Extend `core/binary.py` with `binary_stability_auto(...)`. **Reuse the exact precedent**
`oec_derived._binary_separation_au` / `_derive_binary_stability` (core/oec_derived.py:657-718): derive
`binary_sma_au` from `semimajoraxis → separation_au → Kepler III (period_d + total mass)`, handle
needs-2-masses / no-a / bad-ecc absent-cases, call `equations.compute_binary_orbit_stability(m1, m2, a_bin,
a_bin, ecc)`.

**Algorithm.** Call `binary.binary_orbit(star=…)` → pick the **best solution** (grade/route priority);
masses from `solution["companion"]["m1_solar"/"m2_solar"]` (or the Gaia `binary_masses` cross-check block);
`ecc = solution["eccentricity"]`; `a_bin` via the derivation above (NSS/SB9 → Kepler III from `period_d` +
`m1+m2`; the `companion.a1_au` is the *photocenter* orbit, **not** the relative `a` — do not use it).
Feed → `compute_binary_orbit_stability`. **Edge cases the pipe must handle honestly:** SB2 gives only
`mass_ratio_q` (no absolute masses) → report elements + "no absolute masses, stability not computable";
WDS/orb6 give projected/angular separation only → same honest gap; `binary_orbit` empty → report honestly
(no fabricated elements).

**Subcommand.** `binary-stability-auto`. Args: `--star` (or `--ra/--dec`/`--source-id`) + optional
`--test-sma-au`. **Output:** `{star, elements:{m1_solar, m2_solar, sma_au, ecc, source, grade},
stype_critical_au, ptype_critical_au, test_sma_au, test_verdict: stable|unstable, note?}`.

**Validation anchors** (live-gated): reproduce the **36 Oph** manual result — M1=M2=0.85 M☉, a=48–75 AU,
e=0.92 → S-type crit **0.30–0.47 AU**, P-type crit ~202–316 AU, test 1.0 AU = **unstable**; carry through
the ORB6 grade + flag grade-4/disputed; empty `binary-orbit` → honest report. Offline tests can drive the
`_derive_binary_stability`-style wiring with synthetic solution dicts; the 36 Oph anchor is live-gated.

---

## 6. CR-2 — Multiplicity / SB flag surfaced by default  *(build fifth — live + cheap default block)*

**Goal.** Surface a multiplicity summary in the standard lookup path so an aggregator read alone can't miss
a known binary; explicit `sb_flag`; SB1 masses labelled **lower bound**.

**Two-layer design** (both needed — the cheap layer is the "surfaced by default", the full layer is the
detail):
- **Layer A — cheap default block on `compute_simbad_lookup`.** SIMBAD `otype` is **not fetched today**
  (`_make_simbad("sp_type","plx_value","V","mesfe_h")`; return dict has no otype). Add `otype`/`otypes` to
  `_make_simbad(...)` and a non-fatal, silent `result["multiplicity"]` block (mirroring the existing
  `_simbad_gcns_block` / `_simbad_gould_block` pattern) that reads otype markers (`**` double/multiple,
  `SB*` spectroscopic, `EB*` eclipsing) + the offline GCNS system data (`compute_gcns_system` →
  `n_components`, per-`pairs` `proj_sep_au`) keyed by the Gaia id. This gives `is_multiple` / `sb_flag` /
  `basis` cheaply on every lookup with **no extra live binary_orbit call**.
- **Layer B — full summary via `binary.multiplicity_summary(star)`.** Composes Layer-A's otype/GCNS with a
  `binary.binary_orbit(star=…)` tool-split to fill per-component `basis` (astrom→astrometric,
  spec-min→SB1, SB2→SB2, WDS→visual, otype EB*→eclipsing), `sb_flag`, and `m2_solar_lower` (from the SB1
  `spec-min` lower-bound classifier — always labelled lower bound, sin i = 1). This backs the
  `multiplicity` subcommand and the CR-5 dossier section.

**Files.** Extend `core/databases.py` (otype fetch + `_simbad_multiplicity_block`) and `core/binary.py`
(`multiplicity_summary`). New subcommand handler in `query.py`.

**Subcommand.** `multiplicity`. Args: `--star` (or `--source-id`). **Output:** `{star, is_multiple,
n_components, components:[{basis, sb_flag, sep_au?, m2_solar_lower?}], sb_flag}`.

**GUI note.** Adding `result["multiplicity"]` to `compute_simbad_lookup` is additive — the four SIMBAD-fed
panels ignore unknown keys. Optionally add a "Multiplicity" line/tab later; **not required** for the CRs.

**Validation anchors** (live-gated): a known SB → `sb_flag=true` + correct basis; a known single →
`is_multiple=false`; a known wide visual binary → `is_multiple=true`, `basis: visual`; SB1 masses labelled
**lower bound**, never determined. Offline tests cover the otype→basis mapping + the block shaping with
synthetic inputs.

---

## 7. CR-1 — Debris-disk / IR-excess observational data  *(build sixth — highest risk: new data source)*

**Goal.** The single highest-value CR — nothing in `query.py` carries observed circumstellar-dust data
(`disk-model` is theoretical MMSN). Return per-component `L_IR/L*`, warm/cold class, `T_dust`, `R_disk`,
band/instrument/ref; on non-detection an **upper limit** (never null).

**Files.** New `core/debris_disk.py` (live-network, lazy astroquery — mirror `core/catalog.py` discipline:
result-caching via `catalog_cache`, `_route_error` shape, `_with_retries`/`_timeout_ctx`).

**Data source (WB MSG 035 confirmed + nudge).** Cross-match the star (SIMBAD identity → coords/ids)
against VizieR IR-excess/debris catalogs via the existing `catalog.vizier_query` cone/id path.
**Warm/primary (WB-accepted):** **Cotten & Song 2016** (`J/ApJS/225/15`, ~1750 stars, warm+cold components,
fractional luminosity, dust temperature) + **Chen et al. 2014** (`J/ApJS/211/25`, Spitzer IRS two-temperature
blackbody fits). **Cold far-IR (WB nudge — the outer-reservoir / skill-Q11 read):** WISE cannot see the
T≈40–70 K Kuiper-analog dust, so **add far-IR cold-disk coverage — Herschel DEBRIS / DUNES (or equivalent)
via VizieR** — with WISE + the per-star upper-limit as the fallback. Resolve `R_disk` from `T_dust` + `L*`
when the catalogue gives only temperature (`R ≈ (L*/16πσT⁴)^½`, an estimate, tagged).

**Non-detection upper limit — full build, no defer (Greg, 2026-08-15: no phasing / no v2 / build everything).**
When the star is absent from the excess catalogue, return `detection: upper_limit` with a **real per-star
computed upper limit** on `L_IR/L*`: pull the star's AllWISE W3/W4 (and Spitzer/Herschel where present)
photometry, predict the photosphere from V/Teff/distance, and take the excess non-detection ceiling —
provenance-tagged, *never* a null. A static documented survey-sensitivity floor is the **fallback only** when
per-star photometry is itself unavailable (still an explicit upper limit, tagged as such). Both detections and
non-detections are first-class outputs — there is no "lite" path. *(The genuine remaining choice is a
data/method choice — D1 below — not a scope defer.)*

**Subcommand.** `debris-disk`. Args: `--star` (or `--source-id`/`--ra`/`--dec`). **Output:** `{star,
components:[{type: warm|cold, L_IR_over_Lstar, T_dust_K, R_disk_au, band, ref}], detection:
detected|upper_limit, upper_limit_L_IR_over_Lstar}`.

**Validation anchors** (live-gated): a known disk (**Vega**, **Fomalhaut**, **HD 69830** warm belt) →
`L_IR/L*` + `T_dust` in the literature range; a known disk-free star → **non-detection upper limit**, not
null; warm-vs-cold classification matches the literature for a two-belt system.

---

## 8. CR-5 — Extend `dossier` with binary + age/population + disk  *(build last — composes CR-1/2/7)*

**Goal.** `dossier` today composes identity + regions + HZ + planets + Hypatia + GCNS; add **multiplicity**,
**age/population**, and **disk** so a full per-system read is one call.

**Files.** Extend `core/report.py` only. Per the mapped 5-edit section pattern, for each new section:
(1) add key to `_SECTION_ORDER` + `_ALL_SECTIONS`; (2) add `_SECTION_TITLES` entry; (3) write
`_<name>_data(...)` + `_blocks_<name>(d)` (returns `(title, blocks)` using existing block types
`kv`/`table` — renderers untouched); (4) register in `_SECTION_BLOCKS`; (5) populate `data`/`status` in
**both** `_assemble_star` and `_assemble_sol`.

**Composition (direct core calls, as the dossier already does — NOT via query.py subprocess):**
- `multiplicity` → `binary.multiplicity_summary` (CR-2) + the GCNS system data already riding in the
  `simbad` dict.
- `age_population` → `catalog.gaia_astrophysical` (FLAME age, with its model-dependence caveat) +
  `kinematics.classify_population` (CR-7) + optional `besancon.besancon_query` field-population context.
- `disk` → `debris_disk` (CR-1).

**⚠ Contract conflict to resolve (Open decision D2).** The dossier's current error model **omits** an
absent section into `warnings[]` (no placeholder). CR-5 requires the new sections render as **"explicit
empties / upper limits, not omissions"** for a bare single star. **Recommended:** for these three sections
only, set `status=("ok", …)` with an explicit empty/upper-limit `data[key]` (e.g. `disk` →
`{detection: upper_limit, …}`; `multiplicity` → `{is_multiple:false, …}`; `age_population` → the values
or an explicit "not determined") so they always render — rather than changing the global warn-omit
behaviour for the six existing sections. Sol special-case in `_assemble_sol`: multiplicity = single-star
note; age/population = ~4.6 Gyr / thin-disk; disk = zodiacal/Kuiper note or explicit empty.

**Subcommand.** No new subcommand — `dossier` gains `multiplicity age_population disk` as `--sections`
values (default-on via `_ALL_SECTIONS`). GUI `reports.py` panel: optionally add the three to its hardcoded
`_SECTIONS`/`_SECTION_LABELS` checkboxes (additive; the panel passes its own subset so core is unaffected
either way).

**Validation anchors:** dossier for a known binary → populated binary section; for a known disk host →
populated disk section; for a bare single star → the three new sections as **explicit empties/upper limits,
not omissions** (this is the D2 behaviour above).

---

## 9. Open decisions (recommendations made; flag for Greg / WB sign-off)

**RESOLVED by WB MSG 035 (2026-08-15):** **D1** — Cotten & Song 2016 + Chen 2014 accepted as warm/primary;
**add Herschel DEBRIS/DUNES far-IR cold-disk coverage** for the cold reservoir (per-star WISE upper-limit
fallback). **D2** — non-detection-≠-null scoped to the **three new** dossier sections only (planet
non-detection is carried by CR-6, not the dossier). **D3** — all six subcommand names accepted, no
collisions. **D4** — Interface A refined to **per-isotope** (see CR-4 §3); Interface B bin edges pinned
{≤6,6–8,8–10,10–12,12–15,>15}, imaging = Δmag-vs-host (no rescale). **D5 (MSG 037) — RATIFIED, all additive
keys kept:** CR-4 `provenance.{confidence, domain_ok}` (**`domain_ok=false` when star inputs fall outside the
3c `gce_enrichment.domain` — load-bearing, surface it**); CR-7 `probabilities` vector kept; CR-6
`applicable`+`floor_source` folded into `assumptions`; CR-3 `note?`; CR-1 strictly pinned. **D6 (MSG 037) —
CONFIRMED:** Bensby classifier is the authority; criterion-3 = agrees with Toomre band for clearly-in-band
stars, borderline probabilistic. CR-4 reads the CR-7 **verdict string** (probabilities is an optional 3c
weighting bonus, not required for v1). **ALL CONTRACT DECISIONS CLOSED — clear to build.**

**MSG 039/040 (2026-08-15):** CR-4 **absolute-U/Th key ratified** (`fissile.{u_over_h,th_over_h,a_u,a_th}`
= the tonnage output, feeds radiogenic + ★ fissile-row). Provisional `g_U235/g_U238≈0.238` **matches 3c's
calibrated 0.2378**. **3c bundle DRAFTED** (`scifiWorldBuilding-Claude/design-lab/star-system-analysis/
deliverables/fissile-fraction-gce-model.json`: per-isotope, parametric `D_eff=11.55 Gyr` + halo floor, per-Eu
`{U235:0.393,U238:0.291,Th232:0.51}`, solar 235U/238U=0.007258) — **but its VALUES are pending WB's M1
adversarial audit. DO NOT hard-integrate 3c numbers into `_GCE_MODEL_PROVISIONAL` until WB posts "3c FINAL"**
(the swap-in signal; shape is identical so it's a one-constant change). Optional Th/U=3.6 renormalisation
offered for tighter tonnage at swap time. Likewise CR-6 defaults wait on WB **3a**.

**BUILD STATE (2026-08-15) — ALL SEVEN CRs BUILT + GREEN.**
- **Pure-math trio CR-7/CR-4/CR-6** — built, code-reviewed (medium; 4 findings fixed + test-covered:
  detection ≤0-override→curated-error, dead `--rv-baseline-yr`→now gates, astrometry `0`-baseline bug,
  kinematics partial-velocity silent-drop).
- **Live trio CR-3/CR-2/CR-1** — built; offline logic tests (monkeypatch/synthetic) + **`SPACE_APP_RUN_LIVE=1`
  anchors all green**: CR-3 36 Oph→unstable; CR-2 α Cen→multiple; CR-1 Vega/Fomalhaut detected in-range, Tau
  Ceti two-belt, 18 Sco upper-limit-not-null. CR-1 pinned Cotten `Tau`×1e-4 live against 5 disks.
- **CR-5** — `dossier` gains multiplicity/age_population/disk as explicit-empty sections (D2); Sol offline
  reference values; `test_report.py` extended (53 tests, socket-free).
- **Subcommands:** `population-classify`, `nuclear-inventory`, `detection-completeness`,
  `binary-stability-auto`, `multiplicity`, `debris-disk` + `dossier` sections. New modules: `core/kinematics.py`,
  `core/nuclear.py`+`_tables`, `core/detection.py`+`_tables`, `core/debris_disk.py`; `core/binary.py` +
  `core/databases.py` (otype/multiplicity block) + `core/report.py` extended.
- **Docs:** `docs/integration.md` (CR contract), `CLAUDE.md` (architecture), `docs/testing.md` (test entries) —
  DONE.
- **Reviews (MSG 041→):** `/security-review` clean; `/code-review` (medium, full branch) → orb6 `'m'`=minutes
  bug + dossier live-reader gating + otype double-eval fixed. **WB independent re-gate (MSG 043): 6/7 clean
  GREEN**; CR-3 = honest-null on live 36 Oph, **root-caused CORRECT** (36 Oph absent from orb6 / no period in any
  route → find≠fabricate; anchor numbers pinned by the offline tier-3 fixture + WB's manual byte-match; live
  tests strengthened to assert the honest-null).
- **3c FINAL integrated (MSG 042/044):** `_GCE_MODEL` = `3c-v1.0.0-2026-08-15`. **NOT zero-churn** — the real 3c
  `gce_enrichment` is the **age-dependent** survival integral `g_i=(1−e^(−λD))/(λD)`, `D=max(0,D_eff−age)`,
  `D_eff=11.55` (my provisional was constant-g; agree only at solar). Production ratios 0.393/0.291/0.51.
  Anchors re-green (solar 0.007263, younger→higher, r-poor→lower-abs). DV-2/DV-4/DV-7 domain rules + bands wired.
  Optional Th/U=3.6 renorm NOT applied (WB's call).
- **WB close-out (MSG 045):** all 7 CRs **independently verified** on WB's side; CR-3 resolved; "not zero-churn"
  acknowledged; formula authoritative (no re-round); Th renorm off. **"Nothing open between us."**
- **Post-3c full offline suite: 2868 passed / 53 skipped / 0 failures.**
- **CR-1…7 committed + pushed:** commit **`93f49cd` on `main`** (2026-08-15); branch `star-analysis-crs` deleted.
- **3a FINAL integrated (MSG 048/050), 2026-08-15 — built, WB-re-gated GREEN (MSG 052), committed `37692c6`.** WB delivered "3a
  FINAL" (MSG 048) + ruled 4 consumption calls APP routed (MSG 049→050), bumping the bundle to
  **`3a-v1.1.0-2026-08-15`**. **NOT a one-table drop-in** (like 3c): `detection_tables._DETECTION_DEFAULTS` swapped
  (internal `mag_max` shape mirrors WB's `mag_bin` strings) + `core/detection.py` wired 4 rulings — RV effective
  floor `max(precision, sp_type-keyed jitter)` (O/B/A=5·F=3·G/K/M=1.5; Kraft-break bump); **TESS-only** transit
  default (Kepler = per-star `--transit-precision-ppm` override); **noise-model-preferred faint tails** (TESS
  Kunimoto σ(Tmag) for transit >12 mag, Gaia analytic σϖ(G) for astrometry >15 mag — the binned scalar over-stated
  detection ~4× near G20); imaging **H-band self-luminous** `mechanism_caveat` (flagged, not reconciled — WB DV-7).
  Also switched RV baseline to **per-bin** (15/15/12/8/4/2, per the bundle's base shape). +15 CR-6 tests; docs
  updated (`detection*.py` docstrings, `docs/integration.md`, `CLAUDE.md`, `docs/testing.md`, this file).
  `/code-review high` → fixed the transit-monotonicity string + a dead `_MAG_BIN_EDGES`; #1/#3/#6 deferred
  (memory `code-review-deferred-findings`). **WB re-gate GREEN (MSG 052)** — 4 rulings + 2 readings independently
  verified (noise-model hand-recomputes matched), **per-bin RV baseline ENDORSED (keep it)**.
- **CR-6-AMEND — non-MS host guard (WB MSG 053, Greg's fix call), built 2026-08-15.** Code-review finding #2
  (WD→A-star fake) escalated to a fix: `_host_class` (on the case-sensitive `spectral_leading_class`, so `DA2`→WD,
  `dM6`→M-dwarf) detects **WD `D*` / hot-subdwarf `sdB·sdO` / giant-subgiant lum III·II·I·IV / brown-dwarf L·T·Y**
  → sets `host_class` + `out_of_domain=True` and **stops faking MS mass/radius/jitter** (no first-OBAFGKM-letter
  scan). Still computes on explicit `--star-mass-solar`/`--star-radius-solar` (flagged, **flat** RV jitter — the
  sp_type map is MS-only), else flags/skips the methods with a note. Same MS-only domain-of-validity guard as
  `exclusion-boundary`; **orthogonal to the 3a bundle** (no bundle change). +9 tests (5 WB validation cells + the
  `_host_class` classifier + the partial-M/R guard); docs updated. Rides in the **same commit** as the 3a swap
  (Greg's route 2a). **Full offline suite 2890 passed / 53 skipped / 0 failures** (+9 AMEND tests).
- **✅ FULLY CLOSED (2026-08-15).** WB re-gated GREEN twice (3a MSG 052, CR-6-AMEND MSG 055) and flipped the CR spec
  to **FULFILLED** (MSG 056); Greg signed off. The 3a swap + CR-6-AMEND are **committed + pushed to `main`
  (`37692c6`)** in one commit (route 2a); the CR-1…7 base was `93f49cd`. Channel closed (APP MSG 057). Nothing open
  either side. Deferred code-review items #1/#3/#6 (CR-1/CR-4 committed code) tracked in memory
  `code-review-deferred-findings` — not part of this plan.

- **D1 — CR-1 debris-disk data source + how the per-star upper limit is computed.** *Not a scope choice*
  (the full ask — detections + real per-star upper limit — is built either way, per the no-defer directive).
  The open items are purely data/method: **which detection catalogue(s)** are primary (recommend Cotten &
  Song 2016 `J/ApJS/225/15` + Chen 2014 `J/ApJS/211/25`), and **which photometry backs the per-star upper
  limit** (recommend AllWISE W3/W4 + a photospheric prediction; fold in Spitzer/Herschel/ALMA where a source
  exists). Data-source choice is explicitly SpaceApp's per the spec — proceed on the recommendation; a WB
  channel note for awareness of the chosen catalogues/method is courtesy, not a blocker.
- **D2 — CR-5 "explicit empties vs warn-omit."** *Recommend:* new sections render explicit empties/upper
  limits with `status=ok` (localised to the 3 new sections; six existing sections unchanged). Confirm this
  reading of the contract vs a global dossier behaviour change.
- **D3 — Subcommand names.** *Recommend:* `population-classify`, `nuclear-inventory`,
  `detection-completeness`, `binary-stability-auto`, `multiplicity`, `debris-disk`. (`population-classify`
  deliberately avoids the existing `toomre-q`.) Confirm before wiring — renaming later is a contract churn
  for the consumer.
- **D4 — Interface bundles.** CR-4-fissile and CR-6-defaults ship on **provisional** bundles now
  (versioned, `confidence:"extrapolation"`, domain-guarded). Confirm WB will deliver 3c / 3a to the pinned
  shapes; the swap is a one-constant change per bundle. No kickoff gate.
- **D5 — Additive output keys beyond the pinned contracts (raise with WB before wiring).** The plan emits
  keys the spec's pinned `Output format`s don't list — several are **required** because the spec's own
  validation criteria have no slot otherwise. This is the established **additive-superset** pattern (cf.
  research-priors v2), but WB re-gates the contract independently, so enumerate + ratify:
  - **CR-3** `note?` — honest "not computable" for SB2 (no absolute masses) / WDS-orb6 (projected sep only)
    / empty `binary-orbit`. *Required* by CR-3's validation ("empty → reports honestly").
  - **CR-6** per-method `applicable` (bool) + `floor_source` — *required* by CR-6 validation criterion 2
    ("transit returns 'not applicable / not covered' honestly"). *Recommend folding `floor_source` +
    `reference_version` + `confidence` into the pinned `assumptions` object rather than a new top-level
    `provenance`.*
  - **CR-4** `provenance.{confidence, domain_ok}` beyond the pinned `provenance.{gce_model_version}` —
    carries the spec-wide confidence + domain-of-validity guard. *Recommend* keeping under `provenance`.
  - **CR-7** `probabilities:{thin,thick,halo}` + `provenance` — additive-optional (pinned `membership_prob`
    is the winning prob). Drop to the pinned shape if WB prefers; keep only on ratification.
  - **CR-1** — keep strictly to the pinned per-component shape `{type, L_IR_over_Lstar, T_dust_K, R_disk_au,
    band, ref}`; provenance rides on values, no new per-component key.
  *Recommend:* propose the whole set as an additive superset in one channel MSG; wire only after WB ratifies
  or trims. Absent ratification, emit exactly the pinned keys.
- **D6 — CR-7 "matches the GUI Toomre tab" (validation criterion 3) — operational definition.** The GUI
  only *draws* the 50/100/180 km/s total-velocity arcs and passes Hypatia's `disk` code through — it computes
  no verdict. The spec output *requires* a `thin|thick|halo` verdict + `membership_prob`, which Hypatia's
  thin/thick `disk` code cannot supply, so a real classifier (Bensby ellipsoids) is necessary. *Recommend*
  reading criterion 3 as: the verdict agrees with the Toomre-diagram band (thin <50 / thick ~70–180 /
  halo >180 total velocity) for stars **clearly** in a band; borderline stars are probabilistic. Anchor
  tests pick clear-band stars. Confirm this reading with WB (they wrote the criterion).
- **D7 — CR-6 domain guard (implementation, no WB needed).** Flag an out-of-domain result when the target
  `app_mag` falls outside the 3a bundle's `domain.mag_range` — flag, never clamp/extrapolate (spec-wide §1).

---

## 10. Build order & dependency graph

```
CR-7 population-classify   (pure)                        ─┐
CR-4 nuclear-inventory     (pure; Interface A provisional) │  independent, any order
CR-6 detection-completeness(pure; Interface B provisional)─┘
CR-3 binary-stability-auto (live; reuses oec_derived precedent)   independent
CR-2 multiplicity          (live; + cheap otype block)            independent
CR-1 debris-disk           (live; new data source — highest risk) independent
CR-5 dossier extension     (composes CR-1 disk + CR-2 mult + CR-7 pop + gaia-astro/besancon) ── LAST
```
All ship together (no phasing). Order is dependency-driven: CR-5 consumes CR-1/CR-2/CR-7, so build those
first; CR-1 is the schedule risk (new data source + upper-limit design). CR-4/CR-6 are self-contained.

## 11. Per-CR deliverables checklist

| CR | New/edited core | New subcommand | Network | Tests (offline / live-gated) | Interface dep |
|----|-----------------|----------------|---------|------------------------------|---------------|
| 7  | `core/kinematics.py`; lift LSR const to shared | `population-classify` | only on `--star` | UVW-direct verdict+prob / `--star` anchor | — |
| 4  | `core/nuclear.py` + `core/nuclear_tables.py` | `nuclear-inventory` | no | solar anchor + monotonicity | A (3c) provisional |
| 6  | `core/detection.py` (+ defaults table) | `detection-completeness` | only on `--star` | Sun@10pc floor + monotone + N/A | B (3a) provisional |
| 3  | extend `core/binary.py` | `binary-stability-auto` | yes | synthetic wiring / 36 Oph anchor | — |
| 2  | extend `core/databases.py` + `core/binary.py` | `multiplicity` | yes | otype→basis map / SB & single anchors | — |
| 1  | `core/debris_disk.py` | `debris-disk` | yes | shaping/upper-limit / Vega·Fomalhaut anchors | — |
| 5  | extend `core/report.py` | (dossier `--sections`) | yes | empty-section render / binary+disk hosts | — |

Docs per CR: `docs/integration.md` (contract), `CLAUDE.md` (architecture line), `docs/testing.md`
(test-file note). Final: one WB channel MSG → independent re-gate → Greg sign-off → request doc FULFILLED.

---

## 12. Science-review corrections (adversarial domain review, 2026-08-15 — MUST fold into code)

The plan's data sources + method structure were verified against primary sources (both CR-1 catalogs exist
with the right columns; CR-3 Kepler-III relative-`a` reproduces 36 Oph = 72 AU; CR-4 heat constants +
half-lives exact; CR-7 Bensby + Schönrich LSR correct). These specific corrections are load-bearing:

- **CR-4 fissile — the formation-epoch offset is load-bearing, not decorative.** Decaying the production
  ratio (~1.35) over the star's age alone gives ~0.030 for the Sun, **not** 0.00725 (4× high). The correct
  chain is production 1.35 → **formation-epoch ratio ~0.32** (pre-formation ISM free-decay, ~1.7 Gyr
  effective) → decay over `age_gyr` → present 0.00725. In the WB per-isotope shape this means the provisional
  `gce_enrichment.factors` must yield **`g_U235/g_U238 ≈ 0.238` at solar age/pop/feh** (NOT `g_i = 1`), else
  the anchor fails. **The anchor test must exercise the full chain** (production × g_i × decay), never a bare
  "decay 1.35 → 0.0072". WB already committed to the 0.00725 anchor and the per-isotope shape encodes exactly
  this drift — no new WB question needed; 3c's factors must satisfy the same constraint.
- **CR-4 radiogenic anchor — pin ~5×10⁻¹² W/kg** (band 3–8×10⁻¹²), the present-day bulk-silicate-Earth value
  (20 TW / ~4×10²⁴ kg), **not** 1×10⁻¹¹ as the spec's "~10⁻¹¹ range" loosely says. Label D/H 2.5e-5 as
  **primordial-BBN** (protosolar/local-ISM is ~2.0e-5).
- **CR-3 — add an `e_out_of_hw_range` domain flag** on the stability output. Holman-Wiegert 1999 was fit for
  e ≤ ~0.7–0.8; 36 Oph's e=0.92 (the anchor!) is an extrapolation — the *verdict* is robust (a_c,S is tiny)
  but the exact critical-SMA is past the calibrated regime. Flag, never clamp (spec-wide §1).
- **CR-6 — monotonicity is PER-METHOD, not universal.** min planet mass/radius decreasing at *smaller planet*
  is universal, but the SMA direction differs: **RV/transit get harder at wider SMA; astrometry & direct
  imaging get EASIER at wider SMA** (α∝a; reflected-contrast + IWA both favor separation) — until a
  period/baseline turnover. The validation must assert per-method direction, not a blanket "harder at wider
  SMA." Also **add a P ≤ baseline gate to the astrometry inversion** (and RV) so the curve turns over instead
  of claiming ever-easier detection at arbitrary SMA.
- **CR-1 — tag the temperature/band regime each upper limit constrains.** An AllWISE W3/W4 non-detection
  bounds only **warm** dust (~150–400 K); cold Kuiper-analog belts (~24–70 K) are invisible to WISE and need
  the far-IR (Herschel) path (WB Q3 nudge). Do not report an AllWISE ceiling as an undifferentiated
  `upper_limit_L_IR_over_Lstar` — carry the band/T regime. Practical WISE warm ceilings land ~10⁻⁴–10⁻³
  (far above zodiacal ~10⁻⁷), so set expectations. The blackbody-radius fallback **underestimates** true
  radius (real grains run hotter than blackbody) — tag the systematic direction.
- **CR-7 — GUI arcs (50/100/180) are non-standard vs Bensby canonical (50/70/200).** So criterion-3 is a
  **loose** cross-check; the Bensby probabilistic verdict is the authority (reinforces D6). Anchor tests pick
  clearly-in-band stars; do not assert strict arc-equality.
