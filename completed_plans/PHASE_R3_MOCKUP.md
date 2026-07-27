# PHASE R3 — Research-Priors Hook · Analysis + Mockup

> **This is the analysis + mockup gate for R3 — design only, NO code.** Companion to
> [`PHASE_R3_MOCKUP.html`](PHASE_R3_MOCKUP.html) (panel + data-contract layout). The numbered,
> build-ready `PHASE_R3_PLAN.md` is the **next** gate and is written only after this mockup is
> signed off (house rule: no code until the plan is approved).
>
> **Builds on R1 (shipped 2026-06-22) + R2 (shipped 2026-06-23).** R1 delivered the deterministic
> generator (`core/generate.py` + `core/priors.py` `DefaultPriors`) and the R3 *seam*; R2 added the
> constraint/feasibility engine (`core/feasibility.py` + `core/nbody.py`) with a confidence-tagged
> Layer-3 origin narrative and the already-plumbed `research_policy` param. **R3 fills the seam —
> it does not rework R1 or R2.** See `PHASE_R_MOCKUP.md` §6 (the R1/R2/R3 split, locked 2026-06-21),
> `PHASE_R_PLAN.md` §2a (`core/priors.py` as "the R3 seam"), and `PHASE_R2_MOCKUP.md` §4e (Layer-3
> tagged origin, "R3 swaps in research-calibrated probabilities **without an engine change**").
>
> **Data decision (resolved 2026-06-24, by the user):** the sister project
> `scifiWorldBuilding-Claude/research` has only **prose** research today — no machine-readable
> formation-priors data contract. So R3 builds the **full hook scaffold against a sample/synthetic
> priors file** (versioned data-contract schema + importer + functional `strict` policy + grounding
> re-tag), with **real research content deferred** to a later pass. The scaffold proves the seam
> end-to-end with a placeholder dataset; dropping in real priors later is a data swap, not a code
> change.

---

## 0. What R3 is (one paragraph)

R1 answers *"generate a plausible system"* and R2 answers *"is THIS system possible, and what's the
nearest thing that is."* Both run on **`DefaultPriors`** — literature-informed *defaults*, every
emitted synthetic field and every Layer-3 origin hypothesis honestly tagged
`grounding="default-extrapolation"` ("an informed guess, not a research-derived population model").
**R3 makes that honesty *upgradeable*: it adds a second priors provider, `ResearchPriors`, fed by a
versioned formation-priors *data contract* (ingested like GCNS/Hypatia), and a `research_policy`
switch that selects it.** When research-calibrated priors are loaded and the policy is `strict`, the
generator and the feasibility engine draw from them and re-tag everything they emit
`grounding="research-calibrated"` (with the dataset's version stamped in). **No engine rework** —
the provider object, the `research_policy` param, and the grounding tagging are already in place
from R1/R2; R3 plugs a real provider + an ingest path + a real `strict` semantics into seams that
exist. Because the real sister-project dataset isn't ready, R3 ships against a **sample priors
file** with the same schema, so the wiring is proven now and the data lands later.

---

## 1. Scope — in R3 vs. deferred

| In R3 | Deferred |
|---|---|
| A **versioned formation-priors data contract** — a JSON schema (§3) covering the `DefaultPriors` attribute surface + calibrated Layer-3 origin probabilities + provenance/version metadata | New prior *axes* beyond the v1 attribute surface (additive later; an unknown axis falls back to the default value, never an error) |
| A **sample/synthetic priors file** that validates against the contract (so the hook is testable end-to-end now) | The **real** sister-project formation-priors content (a later data swap — same schema, real numbers; no app code change) |
| `core/priors.py` **`ResearchPriors`** — sibling to `DefaultPriors`, **same attribute surface** + the new `origin_priors` map; loads the ingested data | An ML/Bayesian population *fit* — R3 ingests a curated prior table, it does not fit one |
| A **provider selector** (`get_priors(policy, …)`) threaded through `generate.py`'s two synthetic/anchor sites + `feasibility.py`'s Layer-3 — the single swap point | — |
| An **importer** (`compute_research_priors_ingest`) in the GCNS/Hypatia ingest lineage (validate-before-store, version stamp) + storage (§5) | A live remote fetch — the contract file is local (placed by the consumer); no network |
| **Functional `strict` policy:** strict + priors loaded → research-calibrated; strict + **no** priors → curated `{"error"}` (today it silently falls back) | A per-axis "strictness" knob — `strict` is all-or-nothing in R3 |
| **Grounding re-tag:** the star `grounding`, the generator `notes`, and Layer-3 `grounding` flip `default-extrapolation → research-calibrated` (read from `priors.grounding`, not hardcoded) | Re-tagging the *physics* layers (1/2/4 are pure mechanics — never priors-derived, never re-tagged) |
| GUI: an **Import Research Priors** utility panel + a **research-policy selector** in `SystemGeneratorPanel` + a `DbStatus` status row | — |
| `query.py generate-system **--research-policy** {permissive,strict}` (the flag the param already expects) | — |

**Hard rules carried from R1/R2:**
1. **Determinism** stays the headline contract — same `(seed [, anchor], spec, research_policy)` +
   same loaded priors dataset → byte-identical output. The provider only changes the *sampling
   constants*, not the RNG draw order; a given dataset version is part of the determinism tuple.
2. **`permissive` is byte-identical to today.** The default policy is `permissive`; with it, the
   selector returns `DefaultPriors()` and every R1/R2 output is unchanged. R3 is fully additive on
   the default path (the R1/R2 deep-equal determinism tests must stay green untouched).
3. **Never assert an un-sourced fact.** A research-calibrated grounding is emitted *only* when a
   versioned dataset is actually loaded; otherwise the honest `default-extrapolation` (permissive)
   or a hard error (strict) — never a fabricated "calibrated" tag.

---

## 2. Reuse / seam inventory (verified in `core/` 2026-06-24)

The seam is **already built** — R3 is mostly wiring + a new provider + an ingest path. Exact sites:

**Already in place (R1/R2 — reused, lightly extended):**

| Seam | Where | R3 action |
|---|---|---|
| Priors provider object | `core/priors.py` `DefaultPriors` (documented attribute surface: `spectral_class_weights`, `n_planet_dist`, `spacing_ratio`, `mass_by_zone`, `moon_count`, `moon_mass_frac`; `name`, `grounding`) | **Add `ResearchPriors`** with the **same** surface + `origin_priors` |
| Provider instantiation (synthetic) | `core/generate.py:416` `priors = DefaultPriors()` | Replace with `priors = get_priors(research_policy)` |
| Provider instantiation (anchor) | `core/generate.py:595` `priors = DefaultPriors()` | Same swap |
| `research_policy` param | `generate_system(...)` (`generate.py:713`) — currently passed **only** into `evaluate_feasibility` | **Thread into** `_generate_synthetic` / `_generate_real_anchor` too (additive signature; `permissive` default) |
| Grounding literal (star) | `core/generate.py:266` `"grounding": "default-extrapolation"` | Read `priors.grounding` |
| Grounding literals (notes) | `core/generate.py:449,697` | Read `priors.grounding` / dataset version |
| Layer-3 origin heuristics + grounding | `core/feasibility.py:733–775` (`_layer3_*`), `:177` | Source pathway plausibilities from `priors.origin_priors`; tag `priors.grounding` |
| `strict` fallback note | `core/feasibility.py:710–714` (today: append note, fall back to permissive) | Make functional (strict + data → calibrated; strict + no data → error) |
| `--nbody` flag (pattern) | `query.py:1526` | Add the sibling `--research-policy` flag |

**Confirmed gaps (all new in R3, no astronomy — data plumbing + a thin provider):**

| New | Module | What it is |
|---|---|---|
| `ResearchPriors` | `core/priors.py` | Sibling provider; same attribute surface, loads ingested data, exposes `origin_priors`, `grounding="research-calibrated"`, `name`, `version` |
| `get_priors(policy, …)` | `core/priors.py` | The selector/factory — the single swap point (returns `DefaultPriors` for permissive / no data; `ResearchPriors` for strict-with-data) |
| `compute_research_priors_ingest(...)` | `core/databases.py` (or a small `core/research_priors.py`) | The importer — validate-before-store, version stamp; GCNS/Hypatia lineage |
| The data contract + a sample file | `data/research_priors/` (+ a JSON Schema doc) | The versioned formation-priors contract (§3) + a placeholder dataset |

> **Finding:** R3 introduces **zero new astronomy** and **zero new physics**. It is a provider +
> a data contract + an importer + a policy switch + a re-tag. The hardest design choices are the
> *contract schema* (§3), the *storage* (§5), and the *strict semantics* (§6) — not code volume.

---

## 3. The formation-priors data contract (the versioned schema)

A single, validated JSON object. The consumer (sister project, eventually) produces it; the
importer ingests it; `ResearchPriors` reads it. **R3 ships a sample file in this exact shape so the
hook is exercised end-to-end before real numbers exist.** It mirrors the `DefaultPriors` attribute
surface 1:1 (so the providers are interchangeable) and adds calibrated Layer-3 `origin_priors` +
provenance.

```jsonc
{
  "schema_version": "1.0",                 // contract version — validated on ingest
  "dataset_version": "sample-2026-06-24",  // this dataset's stamp (→ output provenance + determinism tuple)
  "provenance": {
    "source": "SAMPLE / synthetic placeholder — not research-derived",
    "description": "Scaffold dataset proving the R3 hook; real priors land as a data swap.",
    "citations": []                        // real datasets list sources here (occurrence-rate papers, etc.)
  },

  // ── Sampling priors — the DefaultPriors attribute surface, calibrated ──
  "spectral_class_weights": { "M": 0.74, "K": 0.12, "G": 0.076, "F": 0.03, "A": 0.006, "B": 0.0013 },
  "n_planet_dist": { "0": 0.05, "1": 0.10, "2": 0.18, "3": 0.20, "4": 0.16,
                     "5": 0.12, "6": 0.08, "7": 0.05, "8": 0.03, "9": 0.02, "10": 0.01 },
  "spacing_ratio": [1.4, 2.0],
  "mass_by_zone": { "hot": [0.05, 6.0], "hz": [0.10, 8.0],
                    "cold": [0.50, 600.0], "far": [0.30, 80.0] },
  "moon_count": [0, 5],
  "moon_mass_frac": [1e-5, 5e-4],

  // ── NEW in R3 — calibrated Layer-3 formation-pathway priors ──
  // Per context key, ranked pathway plausibilities (the engine reads these instead of the
  // hardcoded DefaultPriors heuristics). Keys mirror the Layer-3 contexts R2 already branches on.
  "origin_priors": {
    "giant_beyond_snow_line":   [ { "pathway": "in_situ",   "plausibility": "high" },
                                  { "pathway": "migrated",  "plausibility": "med"  } ],
    "giant_inside_snow_line":   [ { "pathway": "migrated",  "plausibility": "high" },
                                  { "pathway": "scattered", "plausibility": "med"  } ],
    "terrestrial_in_mmr":       [ { "pathway": "migration_capture", "plausibility": "high" } ],
    "hot_terrestrial":          [ { "pathway": "in_situ",   "plausibility": "med"  },
                                  { "pathway": "migrated",  "plausibility": "med"  } ]
    // … one entry per Layer-3 context key R2 emits; an absent key → the DefaultPriors heuristic
    //    for that context (graceful per-key fallback, never an error)
  }
}
```

**Contract rules:**
- **`schema_version`** gates ingest — an unknown major version → curated `{"error"}` (the importer
  refuses to store data it can't interpret). **`dataset_version`** is opaque provenance, echoed into
  every output's `notes` and folded into the determinism tuple (so two datasets that differ only in
  numbers produce distinguishable, reproducible output).
- **Attribute-surface parity is enforced on ingest:** the importer validates that every
  `DefaultPriors` axis is present and well-typed (weights positive, ranges `[lo ≤ hi]`, distributions
  non-empty). A missing/malformed axis → curated error *before* anything is stored
  (validate-before-store, the GCNS/Hypatia Gate-1 pattern).
- **`origin_priors` is the only genuinely new axis.** It is a map from a Layer-3 **context key**
  (the same keys R2's `_layer3_*` heuristics already switch on) to a ranked pathway list. A context
  the dataset omits falls back **per-key** to the `DefaultPriors` heuristic — so a thin dataset still
  works, it just calibrates fewer contexts. `plausibility ∈ {low, med, high}` (R3 keeps the R2
  vocabulary; a numeric-probability axis is a later contract minor-version).

---

## 4. `ResearchPriors` + the provider selector + grounding re-tag

### 4a. `ResearchPriors` (sibling to `DefaultPriors`)

```
class ResearchPriors:
    name = "RESEARCH"
    grounding = "research-calibrated"
    version = <dataset_version from the loaded contract>
    # identical attribute surface to DefaultPriors:
    spectral_class_weights, n_planet_dist, spacing_ratio, mass_by_zone, moon_count, moon_mass_frac
    # + the new axis:
    origin_priors            # {context_key: [{pathway, plausibility}, …]}
    # load() reads the ingested dataset (§5); raises if absent/invalid.
```

Same shape as `DefaultPriors`, so every existing `generate.py` site (`priors.mass_by_zone[zone]`,
`priors.spacing_ratio`, …) works **unchanged** — only the *values* differ, and `grounding`/`version`
flow into the provenance.

### 4b. The selector — the single swap point

```
get_priors(research_policy="permissive") -> provider
  permissive            → DefaultPriors()                       # today's behaviour, byte-identical
  strict + data loaded  → ResearchPriors(load the dataset)
  strict + NO data      → raise / return {"error": …}           # see §6 — strict is now real
```

`generate.py` replaces its two `DefaultPriors()` literals with `get_priors(research_policy)`, and
`research_policy` is threaded into `_generate_synthetic` / `_generate_real_anchor` (additive; default
`permissive`). `feasibility.py`'s Layer-3 reads `priors.origin_priors` (falling back per-key to the
`DefaultPriors` heuristic) and tags `priors.grounding`. **That's the whole engine change.**

### 4c. Grounding re-tag (read, don't hardcode)

Every place that currently writes the literal `"default-extrapolation"` instead reads
`priors.grounding`:
- the synthetic star's `grounding` field (`generate.py:266`);
- the generator `notes` (`generate.py:449,697`) — and gains the `dataset_version` when research-backed;
- Layer-3 `grounding` (`feasibility.py:177,733–775`).

So under `permissive` everything still reads `default-extrapolation` (unchanged); under
`strict`-with-data everything reads `research-calibrated (sample-2026-06-24)`. **The physics layers
(1/2/4) are never re-tagged** — they are pure mechanics and carry no grounding.

---

## 5. The importer + storage

### 5a. Importer — `compute_research_priors_ingest(path=None, progress_callback=None)`

In the **GCNS/Hypatia ingest lineage** (validate-before-store; surfaced as a GUI utility panel):
1. **Read** the local contract file (default `data/research_priors/priors.json`; the consumer drops
   it there — no network).
2. **Gate 1 (validate-before-store):** `schema_version` known; every `DefaultPriors` axis present +
   well-typed; `origin_priors` well-shaped. Any failure → curated `{"error"}`, **nothing stored**.
3. **Store** the validated dataset + `dataset_version` + provenance (§5b).
4. Return `{schema_version, dataset_version, source, axes_loaded, origin_contexts, stored_at}` or
   `{"error"}`.

### 5b. Storage — **decision D1 (proposed: a cached JSON file, not a DB table)**

Two options, mirroring two existing patterns in the repo:
- **(A — proposed) A validated cached file** under `data/research_priors/` (the **dust-map cache**
  pattern): the importer validates + copies the contract into the cache; `ResearchPriors.load()`
  reads it; a `data/research_priors/meta.json` stamps `dataset_version`/`stored_at`. Lightweight,
  human-inspectable, no schema migration, naturally versioned by file.
- **(B) A SQLite table** `research_priors` + `research_priors_meta` (the **GCNS/Hypatia** pattern):
  consistent with the other ingests and `get_table_status()`, but heavier — the priors are a single
  small structured document, not rows to query, so EAV/relational storage is overkill.

**Proposed: (A).** The priors are one small versioned document read whole at generation time, not a
queryable rowset — a cached file fits the data shape and keeps `ResearchPriors.load()` trivial and
offline. (The `DbStatus`/utility surfaces still report it; see §7.) **Open for your call (D1).**

---

## 6. `strict` policy semantics (made functional)

Today `research_policy="strict"` **silently falls back** to permissive with a note
(`feasibility.py:710`). R3 makes it real and honest:

| Policy | Priors dataset loaded? | Behaviour |
|---|---|---|
| `permissive` (default) | — | `DefaultPriors`; `grounding=default-extrapolation`. **Byte-identical to today.** |
| `strict` | **yes** | `ResearchPriors`; `grounding=research-calibrated (<dataset_version>)`. |
| `strict` | **no** | **Curated `{"error": "research_policy='strict' requires research priors — run the Import Research Priors utility."}` (exit 1).** No silent fallback, no fabricated tag. |

`strict`-with-data flows through *both* the generation sampling (mass/spacing/count/class weights
from the dataset) **and** the Layer-3 origin narrative (calibrated pathway plausibilities) — the two
places priors are consumed. This is the user-visible payoff: ask for `strict` and you either get
research-grounded output or an explicit "no priors loaded" error, never a quiet guess wearing a
calibrated badge.

---

## 7. GUI surfaces

R3 is mostly backend, but three small, pattern-matching GUI touches make the hook usable:

1. **`ImportResearchPriorsPanel`** (Utilities nav; `gui/panels/csv_utility.py`) — mirrors
   `ImportGcnsPanel` / `ImportHypatiaPanel` / `FetchDustMapPanel`: a "Choose contract file" / default
   path + **Check** / **Import** buttons + a background `QThread` + a completion summary
   (`dataset_version`, axes loaded, origin contexts). Calls `compute_research_priors_ingest`.
2. **`SystemGeneratorPanel`** gains a **"Research policy"** selector (a `permissive | strict`
   combo/radio) beside the existing controls. `strict` with no priors loaded → the panel shows the
   curated error (it does not silently generate). The Source-coloured Planet Table + the existing
   four-layer cards stay as-is; the only visible change under `strict` is the **grounding badges flip
   to `research-calibrated (<version>)`** and the notes name the dataset.
3. **`DbStatusPanel`** (opt 57) — appends a **Research Priors** status line (loaded? + dataset
   version), via a pure-`pathlib`/JSON status read (no `ResearchPriors` import needed), exactly as it
   appends the cached dust-map files today.

> The mockup HTML (`PHASE_R3_MOCKUP.html`) lays out the importer panel, the policy selector + badge
> flip in the generator, and the data-contract schema card.

---

## 8. `query.py` — `generate-system --research-policy`

Extends the **existing** `generate-system` subcommand (no new subcommand): add
`--research-policy {permissive,strict}` (default `permissive`), passed straight into
`generate_system(..., research_policy=…)`. The param is already accepted; R3 just exposes the flag
(the `--nbody` pattern at `query.py:1526`). Contract:
- `permissive` (or omitted) → byte-identical to today.
- `strict` + priors loaded → research-calibrated output, `grounding`/`notes` carry the dataset
  version.
- `strict` + no priors → curated `{"error"}` exit 1 (self-validating, Phase-H contract); a bad
  `--research-policy` value → argparse exit 2.

No new ingest subcommand is needed for `query.py` (the importer is a GUI utility, like the GCNS/dust
imports — `query.py` is read-only over what's been ingested). **Open for your call (D2):** whether
to *also* expose a `query.py research-priors-status` reader for the external consumer.

---

## 9. Determinism & validation contract

- **Determinism:** same `(seed [, anchor], constraints, research_policy)` **and** same loaded
  dataset `dataset_version` → byte-identical JSON. The provider swaps *values*, never the seeded RNG
  draw order; `dataset_version` is part of the reproducibility tuple and is echoed in `notes`. The
  R1/R2 deep-equal determinism tests run on `permissive` and **must stay green untouched** (proves
  additivity). A new test pins a `strict`-with-sample-data run deep-equal across two invocations.
- **Validation (self-validating — Phase H, not the Phase-N raw-exception path):** a bad contract on
  ingest (unknown `schema_version`, missing/malformed axis) → curated `{"error"}`. `strict` with no
  priors → curated `{"error"}` (§6). A bad `--research-policy` CLI value → argparse exit 2. An
  `origin_priors` context the dataset omits is **not** an error — per-key fallback to the
  `DefaultPriors` heuristic (graceful, the open-vocabulary rule from R2).

---

## 10. Decisions to resolve before `PHASE_R3_PLAN.md`

| # | Question | Proposed default |
|---|---|---|
| D1 | **Storage** — cached validated JSON file (`data/research_priors/`, dust-map-cache pattern) vs a SQLite `research_priors` table (GCNS/Hypatia pattern)? | **Cached file** — the priors are one small versioned document read whole, not a queryable rowset; keeps `ResearchPriors.load()` trivial + offline (§5b). |
| D2 | **`query.py` surface** — just the `--research-policy` flag on `generate-system`, or also a `research-priors-status` reader for the external consumer? | **Just the flag** in R3; add a status reader only if the consumer asks (additive later). |
| D3 | **Sample dataset values** — clone `DefaultPriors` verbatim (so `strict` output == permissive except the badge, making the additivity diff trivial to verify), or perturb them (so `strict` is visibly different)? | **A perturbed sample** (e.g. tighter `mass_by_zone`, a `giant_beyond_snow_line` skew) so tests can *prove* `strict` actually changes sampling — but ship a second "identity" fixture for the byte-identical-except-badge assertion. |
| D4 | **`origin_priors` plausibility type** — keep R2's `{low,med,high}` enum, or move to numeric probabilities now? | **Keep the enum** (no engine change, matches R2's Layer-3 vocabulary); numeric is a contract minor-version when real data warrants it. |
| D5 | **Strict scope** — does `strict` gate *both* generation sampling and Layer-3, or Layer-3 only? | **Both** (§6) — `strict` means "research-grounded everywhere priors are consumed", the honest reading. |
| D6 | **Contract location** — fixed repo path (`data/research_priors/priors.json`) vs a configurable path / env override (like `SPACE_APP_DB`)? | **Fixed default path + an optional `--path` on the importer** (tests pass a tmp file); no env var unless needed. |
| D7 | **"Send to Dossier"** — still deferred from R1/R2; does R3 want it now? | **Still deferred** (the standing R1/R2 decision); out of R3 scope. |

---

## 11. Proposed checkpoint preview (the numbered plan is the next gate)

Not build-ready yet — this is the shape `PHASE_R3_PLAN.md` will formalise (one checkpoint at a time,
full suite green at each, manual GUI verify at the panel checkpoint, 3 live-net baseline):

| CP | Deliverable |
|---|---|
| R3-C1 | **Data contract** (the JSON Schema doc) + a **sample priors file** (perturbed) + an "identity" fixture; a schema-validation helper + unit tests (good file validates; each malformed axis → curated error). No engine wiring yet. |
| R3-C2 | **`ResearchPriors` + `get_priors(policy)` selector** in `core/priors.py` (loads the sample, exposes the surface + `origin_priors` + `grounding`/`version`) + provider-parity tests (same attribute surface as `DefaultPriors`). |
| R3-C3 | **Importer** `compute_research_priors_ingest` + storage (§5, per D1) + validate-before-store tests (the GCNS Gate-1 pattern) + `DbStatus` status read. |
| R3-C4 | **Thread the selector** through `generate.py` (the 2 sites + `research_policy` into synth/anchor) + **functional `strict`** (§6) + **grounding re-tag** (read `priors.grounding`) + tests: **`permissive` byte-identical** (R1/R2 deep-equal untouched), `strict`-with-sample changes sampling deterministically, `strict`-no-data → curated error. |
| R3-C5 | **Layer-3 calibration** in `feasibility.py` (read `origin_priors`, per-key fallback, tag `priors.grounding`) + tests (calibrated context vs fallback context; determinism). |
| R3-C6 | **`query.py generate-system --research-policy`** flag + subprocess contract tests (permissive parity; strict-with-data; strict-no-data exit 1; bad value exit 2). |
| R3-C7 | GUI: **`ImportResearchPriorsPanel`** + the **research-policy selector** + grounding-badge flip in `SystemGeneratorPanel` + headless smokes; **manual GUI verify**. |
| R3-C8 | Docs (`CLAUDE.md` test inventory + the WSL/data note, `docs/integration.md` `--research-policy` + the data-contract surface, `docs/gui-architecture.md` the new panel + selector, `future_phases.md`/PHASE_R status → R3 done) + final full-suite green. |

---

## 12. Success criteria (R3)

A worldbuilder (or the sister project) can drop a versioned formation-priors contract file in,
import it (validate-before-store, GCNS-style), and then generate / check-feasibility under
`research_policy="strict"` to get output **sampled from and narrated by those priors**, with every
synthetic field and origin hypothesis re-tagged `research-calibrated (<dataset_version>)` and the
dataset version stamped into the provenance `notes`. `strict` with **no** priors loaded is an
explicit, honest **error** — never a quiet guess wearing a calibrated badge. **`permissive`
(the default) is byte-identical to R1/R2** — the additivity is proven by the untouched deep-equal
determinism tests. Because the real sister-project dataset isn't ready, R3 proves the whole hook
against a **sample file**; landing real priors later is a **data swap, not a code change** — the
seam was built for exactly this. Suite green (offscreen, 3 live-net baseline).
