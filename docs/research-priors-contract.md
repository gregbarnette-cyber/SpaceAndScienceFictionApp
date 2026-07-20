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
> See `PHASE_R3_PLAN.md`.

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
| `feh_dist` (app-side) | synthetic host `[Fe/H]` = `None` (F2 inert) | `{mean:#, sigma>0, min?:#, max?:#}` — synthetic-mode metallicity source |

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
suppressed to avoid double-counting. `occurrence_by_metallicity` also conditions the planet count and a
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
> `feh_dist` thin/thick mixture). Full plan + checkpoints: `PHASE_R3_V2_PLAN.md`; the B6 collaboration
> record: `docs/research-priors-v2-b6-actions.md`.
