# Research-Priors Data Contract (Phase R3)

The **formation-priors data contract** is the versioned JSON document that feeds the R3
`ResearchPriors` provider — the research-calibrated sibling of `core.priors.DefaultPriors`. A
consumer (eventually the sister `scifiWorldBuilding-Claude` project) produces it; a GUI utility
(**Import Research Priors**, Phase R3-C3) validates and caches it; the procedural generator
(`core/generate.py`) and the feasibility engine (`core/feasibility.py`) draw from it when
`research_policy="strict"`.

> **Status (R3 complete):** the full hook ships — this contract + the validator, the importer
> (`compute_research_priors_ingest`) + status reader, the `ResearchPriors` provider + `get_priors`
> selector (`core/priors.py`), the `research_policy="strict"` wiring through `core/generate.py` +
> `core/feasibility.py` (Layer-3), the `query.py generate-system --research-policy` flag, and the
> GUI (Import Research Priors panel + the generator's research-policy selector + the DbStatus row).
> The committed `tests/fixtures/research_priors_sample.json` is a **synthetic placeholder** — real
> sister-project research content lands later as a **data swap, not a code change** (same schema).
> See `completed_plans/PHASE_R3_PLAN.md`.

## Why a contract

R1/R2 run on `DefaultPriors` — literature-informed *defaults*, every emitted synthetic field and
Layer-3 origin hypothesis honestly tagged `grounding="default-extrapolation"`. The contract lets a
real population model be dropped in **without an engine change**: it mirrors the `DefaultPriors`
attribute surface 1:1 (so the two providers are interchangeable) and adds one new axis,
`origin_priors`, for the calibrated Layer-3 narrative, plus version/provenance metadata.

## Document shape

A single JSON object:

```jsonc
{
  "schema_version": "1.0",                 // REQUIRED. Gates ingest; major must be known ("1.x").
  "dataset_version": "sample-2026-06-24",  // REQUIRED. Opaque provenance string; echoed into output
                                           //   notes and folded into the determinism tuple.
  "provenance": {                          // optional, free-form
    "source": "...", "description": "...", "citations": [ ... ]
  },

  // ── Sampling priors — the DefaultPriors attribute surface (all REQUIRED) ──
  "spectral_class_weights": { "M": 0.74, "K": 0.12, "G": 0.076, "F": 0.03, "A": 0.006, "B": 0.0013 },
  "n_planet_dist":          { "0": 0.05, "1": 0.10, "2": 0.18, "3": 0.20, "4": 0.16,
                              "5": 0.12, "6": 0.08, "7": 0.05, "8": 0.03, "9": 0.02, "10": 0.01 },
  "spacing_ratio":          [1.4, 2.0],
  "mass_by_zone":           { "hot": [0.05, 6.0], "hz": [0.10, 8.0],
                              "cold": [0.50, 600.0], "far": [0.30, 80.0] },
  "moon_count":             [0, 5],
  "moon_mass_frac":         [1e-5, 5e-4],

  // ── NEW in R3 — calibrated Layer-3 formation-pathway priors (OPTIONAL) ──
  "origin_priors": {
    "<context_key>": [ { "pathway": "in-situ accretion beyond the snow line",
                         "plausibility": "high" }, ... ],
    ...
  }
}
```

### Field rules (enforced by `validate_priors_contract`)

| Field | Rule |
|---|---|
| `schema_version` | required string; **major** (before the first `.`) must be in the known set (`{"1", "2"}` today — v2 is the additive superset below). An unknown major → error (the importer refuses to store data it can't interpret). |
| `dataset_version` | required non-empty string; opaque. Echoed into every output's `notes`; part of the determinism tuple (two datasets differing only in numbers produce distinguishable, reproducible output). |
| `provenance` | optional; free-form (not validated). Real datasets list sources/citations here. |
| `spectral_class_weights` | non-empty object `{class: weight>0}`. |
| `n_planet_dist` | non-empty object `{count(int-coercible): weight≥0}`; at least one weight `>0`. |
| `spacing_ratio` | `[lo, hi]` numbers, `0 < lo ≤ hi`. |
| `mass_by_zone` | object with **exactly** the zones `hot, hz, cold, far`; each `[lo, hi]`, `0 < lo ≤ hi` (Earth masses). |
| `moon_count` | `[lo, hi]` whole numbers, `0 ≤ lo ≤ hi`. |
| `moon_mass_frac` | `[lo, hi]` numbers, `0 < lo ≤ hi` (moon mass / host-planet mass). |
| `origin_priors` | optional object `{context_key: [ {pathway: str, plausibility ∈ {low, medium, high}} ]}`; each context's list non-empty. An **omitted** context falls back per-key to the `DefaultPriors` heuristic — never an error. |

Any violation → a curated `{"error": "research-priors contract: <what>"}` (the repo's Phase-H
self-validating idiom); the importer stores nothing on failure (validate-before-store, Gate-1).

### `origin_priors` context keys (vocabulary v1)

The Layer-3 narrative in `core/feasibility.py` is keyed by **constraint type + situation**. R3-C5
maps the inline heuristics onto these keys; `origin_priors` calibrates any subset of them (an
omitted key keeps the heuristic, still tagged `default-extrapolation` for that row):

| Context key | When it applies |
|---|---|
| `planet_at_location:in_situ_beyond_snow` | a feasible body placed at/beyond the snow line |
| `planet_at_location:in_situ_inner` | a feasible body placed interior to the snow line |
| `planet_at_location:resonant_migration` | additive when the body is protected by a mean-motion resonance |
| `planet_at_location:infeasible` | the requested body does not survive |
| `trojan:feasible` / `trojan:infeasible` | a co-orbital companion at L4/L5 |
| `moon:feasible` / `moon:infeasible` | a moon of the host giant |
| `resonance:feasible` / `resonance:infeasible` | the requested p:q resonance |

`plausibility` keeps R2's `{low, medium, high}` enum (a numeric-probability axis would be a future
contract minor-version).

**Metallicity-qualified variants (v2, B4).** A v2 dataset may add a `<base_key>:metal_rich` or
`<base_key>:metal_poor` entry for any context key above; the feasibility engine prefers it over the base
key when the host's `[Fe/H]` falls in that tail (thresholds `≥ +0.15` / `≤ −0.35`), else the base key.
These are additive and validated like any `origin_priors` key. The delivered dataset defines only base
keys (→ unchanged narrative); the sister can supply the qualified entries when metallicity-conditioned
narratives are wanted.

## Storage / lifecycle

- The live cache is `data/research_priors/` (`priors.json` + a `meta.json` stamp), **gitignored**
  like `data/dust/`. The importer (R3-C3) validates a contract file and writes the cache;
  `ResearchPriors.load()` reads it (defensively re-validating).
- Committed artifacts are the **sample** (`tests/fixtures/research_priors_sample.json`, perturbed)
  and the **identity** fixture (`tests/fixtures/research_priors_identity.json`, DefaultPriors clone)
  — `data/` being wholly gitignored, the canonical sample lives in `tests/fixtures/`. To try the
  hook before real data exists, the importer can ingest the sample fixture directly.
- **To load the real research-calibrated dataset (Packet 3.5):** ingest from the sibling
  `scifiWorldBuilding-Claude` repo —
  `compute_research_priors_ingest(path='../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v1.json')`
  (or the GUI **Import Research Priors** panel → that file). Because `data/` is gitignored, this cache is a
  per-machine build — re-run once after cloning and after any dataset-version bump (a new `dataset_version`). Full
  refresh workflow + verify steps live in that repo's
  `research/star-and-planetary-system-generation/sister-project-coordination.md` §Phase I.

## Policy interaction

| `research_policy` | priors loaded? | Behaviour |
|---|---|---|
| `permissive` (default) | — | `DefaultPriors`; `grounding=default-extrapolation`. Byte-identical to R1/R2. |
| `strict` | yes | `ResearchPriors`; sampling + Layer-3 from the dataset; `grounding=research-calibrated`; notes name `dataset_version`. |
| `strict` | no | curated error (run the Import Research Priors utility) — no silent fallback, no fabricated tag. |

## v2 — the additive superset (`schema_version` "2.0", Phase R3-V2)

The sister project's **v2 contract request**
(`scifiWorldBuilding-Claude/research/query-api-methods/research-priors-v2-contract-request.md`)
extends the contract with **four optional sister-project blocks** (`mass_model`,
`occurrence_by_metallicity`, `intra_system_correlation`, `cold_giant_population`) that express formation
physics v1's flat marginals cannot, plus one app-side axis (`feh_dist`). The blocks arrived across three
point releases: **v2.0** (the first three sampling blocks + `feh_dist`), **v2.1** (the nested
`mass_model.disk.disk_mass_dist`, a per-system log-normal disk-mass lever), and **v2.2** (the top-level
`cold_giant_population` block). **v2 is a strict, additive superset:** `_KNOWN_SCHEMA_MAJORS` now holds
`{"1", "2"}`; every v1.0 dataset still validates/ingests unchanged, and a dataset that omits a block falls
back to the corresponding v1 field. Each block is validated **only when present** (curated `{"error"}`
otherwise) and exposed on `ResearchPriors` as a same-named attribute (`None` when absent; `DefaultPriors`
carries them as `None` too, so `getattr` is uniform).

| Block | Falls back to | Shape (validated) |
|---|---|---|
| `mass_model` (F1) | `mass_by_zone` | `{type ∈ {isolation-scaling}, disk:{sigma0_gcm2>0, sigma_slope, temp0_k>0, temp_slope, disk_mass_mmsn>0 [, disk_mass_dist]}, feeding_zone_hill>0, giant_switch:str[, notes]}` |
| ↳ `disk.disk_mass_dist` (v2.1) | scalar `disk_mass_mmsn` | `{dist ∈ {lognormal}, log10_mean:#, log10_sigma>0, min?>0, max?>0}` (`min ≤ max`) — per-system MMSN multiplier `clamp(10^𝒩(log10_mean, log10_sigma), min, max)` scaling Σ_solid |
| `occurrence_by_metallicity` (F2) | flat `n_planet_dist` | `{feh_grid:[≥2 ascending #], giant_fraction:[same len, each ∈ 0..1], superearth_floor_feh?:#, n_planet_dist_shift?:str}` |
| `intra_system_correlation` (F3) | independent per-planet draws | `{size_ratio_dist:{mean>0, sigma≥0}, period_ratio_dist:{0<min≤mode≤tail}, ordering?:str, note?:str}` |
| `cold_giant_population` (v2.2) | grid giant switch (giants grown from the inner grid) | `{sma_dist:{dist="powerlaw", inner ∈ {"snow_line" \| #>0}, outer_au>0, slope_dn_dlna:#}, multiplicity:{count(int): weight≥0, ≥1 positive}}` |
| `inner_giant_population` (v2.3) | nothing — v2.2 placed ~zero close-in giants | `{sma_dist:{dist="mixture", 0<inner_edge_au<1, outer="snow_line", components:[{name, dist ∈ {lognormal_au, powerlaw}, weight>0, …}] summing to 1}, occurrence_ref="occurrence_by_metallicity.giant_fraction" (**hard dependency**), mass_range_mjup:[0<lo<hi≤13], eccentricity_dist:{warm:beta(α,β>0), hot:rayleigh(0<σ<1)}, formation_channel_mix:{<zone>:{channel: frac∈[0,1]} summing to 1}}` |
| `feh_dist` (app-side) | synthetic host `[Fe/H]` = `None` (F2 inert) | `{mean:#, sigma>0, min?:#, max?:#}` — synthetic-mode metallicity source |
| `stellar_multiplicity` (v2.4) | `star["multiplicity"]` stays `None` in synthetic mode (GCNS-derived under `--anchor-star`) | `{multiplicity_fraction:{mass_msun_grid ascending, fraction (same len, 0..1), sigma?}, companion_frequency?, higher_order_fraction?:{value 0..1}, mass_ratio_dist:{dist="powerlaw_q", slope, 0<q_min<q_max≤1, twin_excess_*?}, separation_dist:{dist="mixture", components:[…] weights summing to 1}, ecc_dist?, consumer_contract?}` |
| `stellar_activity` (v2.4) | nothing — no XUV environment was set for any generated star | `{rotation_activity:{saturation_log_lx_lbol<0, saturation_rossby>0, unsaturated_slope<0, ro_valid_range?, log_lx_lbol_valid_range? (may be descending), relation_rms_dex?}, convective_turnover:{relation:str, valid_mass_msun, mass_msun_grid/tau_days (parallel, may descend in mass)}, rotation_age_singles?, rotation_age_fgk?, tidal_locking?, circumbinary_xuv:{component_count_scaling==1.0, xray_to_euv?}, expected_locked_vs_single_delta?:{is_prior_field==false}}` |

The importer's `meta.json` and `get_research_priors_status()` gain a **`v2_blocks`** list (`[]` for a v1
dataset / a pre-V2 cache); the opt-57 DbStatus row and the Import Research Priors panel surface it.

**Engine consumption (`core/generate.py`, all block-gated).** With `mass_model`, planet mass is drawn from
the isolation-mass physics (`_mass_model_draw`) instead of `mass_by_zone`; three coupled levers layer on:
(1) the **disk-mass lever** — a per-system MMSN multiplier from `disk_mass_dist` (`_draw_disk_mass_mult`)
scaling Σ_solid, paired with `Σ_solid ∝ 10^[Fe/H]`, lifting the small-planet mass scale; (2) the
**growth-race giant gate** — giant formation is a *per-system* roll (`_roll_system_forms_giants`) against a
**saturating occurrence curve** `occ([Fe/H]) = C·x/(K+x)`, `x = 10^(2·[Fe/H])` (`_occ_eff`; C=0.30, K=2.0 —
the FV05 curve), replacing the old per-orbit `min(1, gf/gf₀)`; (3) **giant mass** is log-normal anchored on
the F4 gap-opening mass, clamped to `[M_crit, ~13 M_J]` (`_draw_giant_mass`). With `cold_giant_population`
present, **cold giants are placed by a decoupled population** (`_place_cold_giants`: count from
`multiplicity`, SMA from `sma_dist` beyond the snow line within `outer_au`, mass from the peaked function)
**independent of the detection-biased inner `n_planet_dist` grid**, and the grid's own giant switch is
suppressed to avoid double-counting. With `inner_giant_population` present (v2.3), a **decoupled close-in giant population** is placed interior to
the snow line (`_place_inner_giants`, run after the cold block and sharing the host `[Fe/H]`): its own
per-system occurrence roll against the **literal FV05 `giant_fraction`** interpolated on `feh_grid` with the
**endpoints held** (`_interp_giant_fraction`; ~3% at solar — deliberately a *different* number from `_occ_eff`'s
rescaled ~10%-solar cold curve, over a disjoint SMA zone, so the two rolls cannot double-count); SMA from the
`sma_dist` mixture (hot-Jupiter log-normal pileup + the rising `a^+0.53` warm branch); a `formation_channel`
tag drawn from `formation_channel_mix` **consistent with the drawn eccentricity** (warm zone: e selects the
excited/quiescent group, then the block's own weights pick within it; hot zone: tides erase the e signature, so
the full mix is used). Each such planet carries `formation_channel` + `giant_zone` (`"hot"`/`"warm"`). This
**bypasses the B1 `giant_switch` for a controlled sub-population — the gate itself is unchanged**, and a giant
interior to the snow line is always a tagged member of this population, never grid-grown.
**`stellar_multiplicity` is SAMPLED (Phase R3-V2 B1); `stellar_activity` is not.** These are the first
*stellar* axes in the contract (every other block is planetary — note the `multiplicity` key inside
`cold_giant_population` is a *giant* count). Both validate, appear in `v2_blocks`, and are exposed on
`ResearchPriors`.

`stellar_multiplicity` is now drawn in **synthetic mode** (`_draw_multiplicity`): multiplicity roll
(mass-dependent, linear in log₁₀ M) → mass ratio `q` → the close-pair / wide-log-normal separation mixture →
eccentricity, emitted in the block's own `consumer_contract` shape `{mass_solar, sma_au, ecc, p_orb_days,
close_pair}`. That is exactly the `--companion` hint shape, so a drawn companion reaches
`feasibility._binary_gate` (Holman–Wiegert S/P-type) through the existing path — an explicit hint always
overrides it. **Real-anchor mode is untouched**: its multiplicity is GCNS-derived and is never overwritten.
The sampler was unblocked by dataset **v2.9.0**, which replaced the borrowed *solar-type* 12 d circularization
boundary with a source-backed **M-dwarf ~6 d** (Packet-4 C52: Zanazzi 2022 + EBLM XVII + the local 57-system
e–P transition) — the gap that had held it. Two behaviours are contractual and tested: eccentricity is
**never identically zero**, and the boundary is **statistical, never a cut** (BY Dra is `e = 0.300` at
`P = 5.98 d`). Above the boundary the **`f(e) ∝ e^η`** shape is **source-pinned** (Moe & Di Stefano 2017; η period +
primary-mass-dependent — v2.11.0 Q2, replacing the earlier app-side Rayleigh(σ = 0.21)); the emitted
note names the source, and `p`/coefficients are drift-guarded against the dataset's formula strings.

****Wide-companion survival roll-off + tail (B3 + v2.11.0 Q3/Q4).** The wide component's outer behaviour is
a **smooth survival roll-off** `S(a) = 0.5^((a/a_half)^p)` (p ≈ 1.35, a tunable convenience) around the
half-life scale `a_half ≈ 1.212 × (M_tot / t)` pc (Weinberg 1987 eq. 28) — the scale at which roughly **half**
the population has been disrupted by age *t*, **not** a wall: the source reports "no evidence of breaks or
cutoffs", so **v2.11.0 Q3 replaced the old hard truncation** with this smooth thinning-by-separation (it
moves with mass and age and is `null`/inert without an age axis). **A two-break power-law tail IS now added**
(v2.11.0 Q4): beyond a **continuity splice** at ~1000 AU the tail's PDF is set equal to the log-normal at the
splice (Tian 2020 recipe → normalization with **zero free parameters**, so the "unknown join weight" blocker
dissolves — no invented weight), slope γ₁ −1.55 → γ₂ −2.07 (disk). This **corrects the recorded solar-host
over-production** (the log-normal ran shallower than the measured −0.60 slope out to ~3000 AU); M-dwarf
centres are steeper and left unthinned (err safe). The `a_half` coefficient is **primary-verified** (an
earlier ~4% slack, carried while the paper was known only via a secondary source, was **retracted** once it
was opened). Per WB canon `multiple-star-systems.md` §13 (the X9 a_half domain amendment, 2026-08-02 — a
**disclosure only**, the coefficient is unchanged), the 1.212 form is typed **stars-only**,
**environment-indexed** (normalized to the local *stellar-mass* density — Bahcall & Soneira 1980 — **not** a
stellar *number* density) and **orientation-blind**; the generator applies it inside its own
solar-neighbourhood census domain, so the normalization is correct-by-domain, not a hidden assumption. A
second-order interaction is recorded, not corrected: v2.11.0 Q5's thin/thick/halo age draws mean a
halo-aged host uses the disk-density-normalized coefficient — no corrected multiplier exists to apply. The
`domain_overextension` flag in the dataset is **not** a
misuse by the sampler: Winters' σ = 1.16 is a whole-range *untruncated* fit out to a 7500 AU horizon, so the
flag records a source-vs-source model disagreement (D&K's two components vs Winters' one), which the modern
Gaia data do not settle in D&K's favour.

`stellar_activity` is now sampled too (Phase R3-V2 B2)**, because the v2.10 **`age_dist`** block supplied
the input it named and nothing produced. `age_dist` is the mirror of `feh_dist` but is **not** a Gaussian: a
population-weighted SFH **histogram**, drawn then **MS-lifetime-truncated** against the Phase-L3
`compute_stellar_evolution` (`truncate_and_renormalize` — no star older than its own main sequence). Its
validator (`_check_age_dist`) enforces two structural guards: histogram bins must be **contiguous** (a gap
silently drops probability mass), and an interior **zero-fraction bin requires an `sfh_smoothing_note`** — the
BGM zeroes 7–8 Gyr and piles up 8–9 Gyr as a discrete-age-bin artifact, and a consumer sampling that literally
reproduces a hole the real SFH does not have. Requiring the note means the artifact cannot arrive undocumented.

The chain is age → P_rot → Ro = P_rot/τ(M) → log(L_X/L_bol) → [X-ray→EUV] → XUV. P_rot has three branches:
a **tidally locked** B1 close pair (`P_rot = P_orb` — saturated for life, and the only branch needing **no**
age), **Skumanich** t^½ for 0.6–1.36 M☉, and the **bimodal** M-dwarf fast/slow sequences for 0.08–0.6 M☉
(never interpolated across the gap — that gap is a real population feature). Out-of-domain values are
**flagged, never clamped**; the X-ray→EUV conversion is **contested** in the dataset, so the applied relation
is named and its alternative carried rather than averaged. The dataset's own **`unit_test_sun`** is a
regression test here (M=1 at 4.57 Gyr → P_rot 25.4 d, τ 13.8 d, Ro 1.84, log R_X −5.99, inside the observed
solar band), and `expected_locked_vs_single_delta` is asserted as an **emergent** property, never fed in
(`is_prior_field: false`).

**Per-population SFHs (v2.11.0 Q5):** the block's `populations` sub-block now supplies the thin/thick/halo
split, so age is drawn **population → that population's SFH** (thin ≈ the blended histogram restricted to
≤ 11 Gyr; thick/halo = truncated Gaussians peaked ~10.5/~12.5 Gyr) rather than one blended histogram. Without
the sub-block (a v2.10 dataset) the blended histogram is used, as before — the block had sanctioned that
simplification for the activity chain alone ("for the stellar_activity chain ALONE a single blended
distribution is adequate"). The queued BGM per-population pull (which would refine thick/halo) timed out and
is closed; the literature-anchored forms are final. See `docs/research-priors-v2-open-work.md` §B2.

Their validators additionally **hard-enforce three structural guards**, so a future dataset edit cannot
silently subvert them (each has a negative test): `ecc_dist.consumer_must_not_default_to_zero` must be **true**
(a silent `e = 0` makes every drawn binary maximally planet-friendly and inflates stable-HZ rates);
`circumbinary_xuv.component_count_scaling` must be **1.0** (the geometric result that doubled emitters cancel
against doubled HZ distance, so circumbinary XUV depends on `L_X/L_bol` only — a ratio identity, band
independent); and `expected_locked_vs_single_delta.is_prior_field` must be **false** (it is what the Rossby
chain *produces*, so treating it as an input double-counts it). Two shapes that look wrong but are correct and
must not be "tidied": `log_lx_lbol_valid_range` is stated **descending** (`−4 > log R_X > −6.3`), and the
Wright 2018 τ table runs **hot-to-cool** so its mass grid descends.

**One app-side modelling choice to know:** the block supplies a mass *range* (`mass_range_mjup`) but no shape,
and the cold block's gap-anchored `_draw_giant_mass` collapses this close in (the F4 Type-II knee scales with
`a` and disk temperature, so every draw fell below the 0.3 M_J floor and clamped there — a delta function at
the floor). Inner-giant mass is therefore drawn **log-uniform** across the range, the v1 `mass_by_zone`
convention, deliberately flat rather than inventing a centre the dataset does not pin. Flagged to the sister
project as a candidate for a real inner-giant mass function.
`occurrence_by_metallicity` also conditions the planet count and a
super-Earth floor on `[Fe/H]`; `intra_system_correlation` draws neighbours peas-in-a-pod correlated. The
real-anchor host `[Fe/H]` is **Hypatia-preferred, SIMBAD `mesfe_h.fe_h` fallback**, tagged in
`star["feh_source"]`; the `notes` gain a `"v2 physics in effect: …"` line naming the active blocks.

> **Stage status — COMPLETE.** Stage A (schema/plumbing) + Stage B (engine consumption) are **built and
> calibrated against the delivered `research_priors_v2.json` (v2.2.0)**: **B1** (`mass_model` isolation-mass
> draw + physics giant switch), **B2** (`occurrence_by_metallicity` + `feh_dist`, Hypatia-preferred [Fe/H]),
> **B3** (`intra_system_correlation` peas-in-a-pod), **B4** (metallicity-qualified origin keys), **B5**
> (`v2 physics` provenance notes in CLI/`query.py`/GUI), and **B6/L2** (the v2.1 disk-mass lever, the
> saturating growth-race occurrence curve, and the v2.2 decoupled cold-giant placement). Realized
> calibration meets the sister's targets: small-planet mass ~1.5 M⊕, giant mass function ~Saturn-modal +
> super-Jupiters to 13 M_J, cold-giant occurrence on the FV05 curve (solar ~9% / +0.5 ~21% / −0.5 ~1.7%).
> All consumption is block-gated → a v1.0 dataset and `permissive` stay byte-identical (`star["feh"]=None`).
> Only optional second-order items remain (metallicity-dependent SMA/multiplicity, hot-Jupiter channel,
> `feh_dist` thin/thick mixture). Full plan + checkpoints: `completed_plans/PHASE_R3_V2_PLAN.md`; the B6 collaboration
> record: `docs/research-priors-v2-b6-actions.md`.
