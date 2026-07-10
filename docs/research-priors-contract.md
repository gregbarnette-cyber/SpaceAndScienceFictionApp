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
| `schema_version` | required string; **major** (before the first `.`) must be in the known set (`{"1"}` today). An unknown major → error (the importer refuses to store data it can't interpret). |
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
