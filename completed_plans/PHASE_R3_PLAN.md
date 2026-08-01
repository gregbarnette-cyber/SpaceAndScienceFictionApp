# PHASE R3 — Research-Priors Hook · Implementation Plan

> **Scope.** R3 is the **third of three sub-phases** (R1 engine → R2 constraint/feasibility engine →
> **R3 research-priors hook**; split locked in `PHASE_R_MOCKUP.md` §6). R3 **fills the seam R1/R2
> already built** — it adds a second priors provider (`ResearchPriors`), a versioned formation-priors
> **data contract** + a GCNS/Hypatia-style importer, a **functional `strict` policy**, and a
> **grounding re-tag** (`default-extrapolation → research-calibrated`). **No engine rework, no new
> astronomy, no new physics** — the provider object, the `research_policy` param, and the grounding
> tagging are all in place; R3 plugs a real provider + an ingest path + real `strict` semantics into
> existing seams.
>
> **Data decision (resolved 2026-06-24, by the user):** the sister project has only **prose**
> research today — no machine-readable formation-priors contract. So R3 builds the **full hook
> against a sample/synthetic priors file** (same schema, placeholder numbers); landing real
> sister-project priors later is a **data swap, not a code change**.
>
> **Source files:** edits to `core/priors.py` (add `ResearchPriors` + `get_priors` selector), new
> `core/research_priors.py` *or* additions to `core/databases.py` (the importer — see §0 D-storage),
> edits to `core/generate.py` (thread `research_policy` into the two synth/anchor sites + read
> `priors.grounding`), edits to `core/feasibility.py` (Layer-3 reads `origin_priors`; functional
> `strict`), `query.py` (`--research-policy` flag on the existing `generate-system`),
> `gui/panels/csv_utility.py` (`ImportResearchPriorsPanel` + `DbStatus` row), `gui/panels/generator.py`
> (research-policy selector + badge flip), a new data-contract doc + a sample file under
> `data/research_priors/`, `docs/` updates, new `tests/test_research_priors.py` (+ additions to
> `tests/test_generate.py` / `tests/test_query_generate.py` / `tests/test_generator_panel.py`).
>
> **Companion mockups (approved 2026-06-24):** `PHASE_R3_MOCKUP.md` (design + analysis) and
> `mockups/PHASE_R3_MOCKUP.html` (panel + data-contract layout). **No code until this plan is signed off**
> (house rule).
>
> **As-built correction (2026-06-24):** this plan references a committed sample template at
> `data/research_priors.sample.json`, but `data/` is **wholly gitignored** (discovered at C1), so the
> committed sample actually ships at **`tests/fixtures/research_priors_sample.json`** (+ the identity
> fixture `tests/fixtures/research_priors_identity.json`); the importer's default source points there.
> Also added beyond this plan: the **`SPACE_RESEARCH_PRIORS_DIR`** env override (mirroring
> `SPACE_APP_DB`) for relocating the cache (needed by the subprocess test). The shipped docs
> (`CLAUDE.md`, `docs/integration.md`, `docs/gui-architecture.md`, `docs/research-priors-contract.md`)
> reflect the as-built locations.

---

## 0. Decisions carried in (locked 2026-06-24 — user took the recommendations)

| # | Decision |
|---|---|
| D1 — storage | **A cached, validated JSON file** under `data/research_priors/` (the **dust-map-cache** pattern), **not** a SQLite table. The priors are one small versioned document read whole at generation time, not a queryable rowset; `ResearchPriors.load()` stays a trivial offline file read. The importer validates + copies the contract into the cache and writes a `data/research_priors/meta.json` stamp (`dataset_version` / `schema_version` / `stored_at`). `data/research_priors/` is **gitignored** (consumer-supplied data), like `data/dust/`. |
| D2 — `query.py` surface | **Just the `--research-policy {permissive,strict}` flag** on the existing `generate-system` subcommand. No `query.py` ingest or status subcommand in R3 (the importer is a GUI utility, like GCNS/dust; `query.py` is read-only over what's ingested). A `research-priors-status` reader is an additive later add only if the consumer asks. |
| D3 — sample dataset | **Two fixtures.** (a) A **perturbed** sample (`data/research_priors/priors.json` shipped as the default — tighter `mass_by_zone`, a `giant_beyond_snow_line` skew, calibrated `origin_priors`) so tests can **prove** `strict` changes sampling deterministically. (b) An **"identity"** test fixture (values cloned from `DefaultPriors`, `origin_priors` matching the heuristics) so a test can assert `strict`-output == `permissive`-output **except** the grounding badge/version — proving the *only* difference under identity priors is the tag. |
| D4 — plausibility type | **Keep R2's `{low, medium, high}` enum** for `origin_priors` plausibilities (no engine change; matches R2's Layer-3 vocabulary). A numeric-probability axis is a contract **minor-version** when real data warrants it. |
| D5 — strict scope | **`strict` gates BOTH** the generation sampling (class weights / planet count / spacing / mass-by-zone / moon priors) **and** the Layer-3 origin narrative. "Research-grounded everywhere priors are consumed" — the honest reading. |
| D6 — contract location | **Fixed default path** `data/research_priors/priors.json` for the importer + an **optional `path=` argument** on `compute_research_priors_ingest` (tests pass a tmp file). `ResearchPriors.load()` reads the **cache** (`data/research_priors/`, written by the importer), not the raw contract path. No env var. |
| D7 — Send to Dossier | **Still deferred** (the standing R1/R2 decision). Out of R3 scope. |

Standing invariants (not contested): **`permissive` is the default and is byte-identical to R1/R2**;
the determinism contract extends to include the loaded `dataset_version`; physics layers (1/2/4) are
never priors-derived and never re-tagged.

---

## 1. Design summary (the one rule)

R3 keeps `core/priors.py` and `core/generate.py`/`core/feasibility.py` **pure** (no Qt). The only
new I/O is the importer's file read/validate/copy and `ResearchPriors.load()`'s cache read — both
local, no network. **Determinism stays the headline contract, now widened by one term:** same
`(seed [, anchor], constraints, research_policy)` **and** the same loaded cache `dataset_version` →
**byte-identical** output. The provider swaps *sampling values*, never the seeded-RNG draw order;
`dataset_version` is echoed in `notes` and is part of the reproducibility tuple.

**The single swap point** is a new selector in `core/priors.py`:

```python
def get_priors(research_policy="permissive"):
    """Return the priors provider for a policy.
       permissive            -> DefaultPriors()                  # today, byte-identical
       strict + cache loaded -> ResearchPriors.load()
       strict + no cache     -> raise PriorsUnavailable(...)     # functional strict (§5)
    """
```

`core/generate.py` replaces its two `DefaultPriors()` literals (`:416`, `:595`) with
`get_priors(research_policy)`, and threads `research_policy` into `_generate_synthetic` /
`_generate_real_anchor` (additive signature; default `"permissive"`). Every existing
`priors.<attr>` access works unchanged — only the values differ. The grounding literal
(`generate.py:266`, notes at `:449,:697`; `feasibility.py:177,:733–775`) is read from
`priors.grounding` (+ `priors.version` where a dataset is loaded).

**`permissive` (default) → `DefaultPriors` → every R1/R2 output byte-identical.** The R1/R2
deep-equal determinism tests run on the default path and **must stay green untouched** — that is the
additivity proof.

---

## 2. The data contract + sample file — `data/research_priors/`

### 2a. The contract (per `PHASE_R3_MOCKUP.md` §3)

A single validated JSON object mirroring the `DefaultPriors` attribute surface 1:1, plus the new
`origin_priors` axis and provenance:

```jsonc
{
  "schema_version": "1.0",                 // gates ingest (unknown major → error)
  "dataset_version": "sample-2026-06-24",  // opaque provenance + determinism term
  "provenance": { "source": "...", "description": "...", "citations": [...] },

  "spectral_class_weights": { "M":…, "K":…, "G":…, "F":…, "A":…, "B":… },
  "n_planet_dist":          { "0":…, "1":…, … },          // string keys (JSON) → int on load
  "spacing_ratio":          [lo, hi],
  "mass_by_zone":           { "hot":[lo,hi], "hz":[…], "cold":[…], "far":[…] },
  "moon_count":             [lo, hi],
  "moon_mass_frac":         [lo, hi],

  "origin_priors": {                                       // NEW in R3 (calibrated Layer-3)
    "<context_key>": [ {"pathway": str, "plausibility": "low|medium|high"}, … ],
    …                                                       // omitted context → per-key heuristic fallback
  }
}
```

### 2b. Two shipped/fixture files (D3)

- **`data/research_priors/priors.json`** (shipped sample, gitignored dir but committed as a
  template? — **no**: dir is gitignored; instead ship `data/research_priors.sample.json` as a
  committed template the importer/tests/consumer copy from). The **perturbed** dataset.
- **`tests/fixtures/research_priors_identity.json`** — the **identity** fixture (DefaultPriors
  values + heuristic-matching `origin_priors`) for the "strict == permissive except the badge" test.

> **Repo note:** `data/research_priors/` (the live cache) is **gitignored** like `data/dust/`. The
> committed artifacts are the **sample template** (`data/research_priors.sample.json`) + the schema
> doc + the test fixtures. The importer copies a contract file into the gitignored cache.

### 2c. Schema validation helper

`validate_priors_contract(obj) -> None | {"error": str}` (self-validating, Phase H contract):
- `schema_version` present + a known major (`"1.x"`);
- every `DefaultPriors` axis present + well-typed: weights a non-empty `{str: positive float}`;
  `n_planet_dist` non-empty `{int-coercible: non-negative float}`; `spacing_ratio`/`moon_count`/
  `moon_mass_frac` a `[lo, hi]` with `lo ≤ hi`; `mass_by_zone` has the 4 zone keys, each `[lo ≤ hi]`;
- `origin_priors` (if present) a `{str: [ {pathway:str, plausibility ∈ {low,medium,high}} ]}`.
- Any failure → a curated `{"error": "research-priors contract: <what>"}`. Used by both the importer
  (before storing) and `ResearchPriors.load()` (defensive re-check of the cache).

---

## 3. `core/priors.py` — `ResearchPriors` + `get_priors`

### 3a. `ResearchPriors` (sibling provider — same surface)

```python
class ResearchPriors:
    name = "RESEARCH"
    grounding = "research-calibrated"
    # identical attribute surface to DefaultPriors:
    #   spectral_class_weights, n_planet_dist, spacing_ratio, mass_by_zone, moon_count, moon_mass_frac
    # + new:
    #   origin_priors            # {context_key: [{pathway, plausibility}, …]}
    #   version                  # = dataset_version of the loaded cache
    @classmethod
    def load(cls, cache_dir=_DEFAULT_CACHE_DIR):
        # read data/research_priors/priors.json (+ meta.json); validate_priors_contract; build.
        # raise PriorsUnavailable if the cache is absent; {"error"-style} ValueError if invalid.
```

`n_planet_dist` string keys are coerced to int on load (so the generator's
`sorted(priors.n_planet_dist.items())` draw is identical in shape to `DefaultPriors`).

### 3b. `get_priors` selector + `PriorsUnavailable`

```python
class PriorsUnavailable(Exception): ...

def get_priors(research_policy="permissive"):
    if research_policy == "permissive":
        return DefaultPriors()
    if research_policy == "strict":
        return ResearchPriors.load()       # raises PriorsUnavailable if no cache
    raise ValueError(f"unknown research_policy: {research_policy!r}")
```

The callers convert `PriorsUnavailable` into the curated `{"error"}` (§5) so the pure-function
contract holds.

### 3c. Provider-parity test (C2)

A test asserts `ResearchPriors.load(identity_fixture)` exposes **exactly** the `DefaultPriors`
attribute set (same keys, same types) + `origin_priors`/`version`/`grounding` — the contract that
keeps the two interchangeable in `generate.py`.

---

## 4. The importer + storage (D1) — `compute_research_priors_ingest`

In the GCNS/Hypatia ingest lineage (validate-before-store). Placed in `core/research_priors.py`
(a small new module — keeps `databases.py` from growing; the dust path set the precedent of a
dedicated module for an optional/auxiliary data path).

```python
def compute_research_priors_ingest(path=None, progress_callback=None) -> dict:
    # 1. resolve path (default data/research_priors.sample.json or a user-chosen file)
    # 2. read JSON; validate_priors_contract(obj)         -> {"error"} on any failure, nothing stored
    # 3. write data/research_priors/priors.json (the cache) + meta.json (version/schema/stored_at)
    # 4. return {schema_version, dataset_version, source, axes_loaded, origin_contexts, stored_at}
def get_research_priors_status(cache_dir=_DEFAULT_CACHE_DIR) -> dict:
    # pure-pathlib/JSON read of meta.json — {loaded: bool, dataset_version, schema_version} ;
    # NO ResearchPriors import (so DbStatus reports without building a provider).
```

- **Gate-1 (validate-before-store):** the contract is validated *before* the cache is written, so a
  malformed file leaves any existing cache intact (GCNS Gate-1 pattern).
- **Cache dir** `data/research_priors/` (gitignored). `get_research_priors_status` is the
  `DbStatus`/CLI status surface, mirroring `core.dust.get_dust_map_status()`.

---

## 5. Functional `strict` policy (made real)

Today `research_policy="strict"` silently falls back (`feasibility.py:710`). R3 makes it honest:

| Policy | Cache loaded? | Behaviour |
|---|---|---|
| `permissive` (default) | — | `DefaultPriors`; `grounding=default-extrapolation`. **Byte-identical to today.** |
| `strict` | yes | `ResearchPriors`; sampling + Layer-3 from the dataset; `grounding=research-calibrated`; `notes` name `dataset_version`. |
| `strict` | no | **curated `{"error": "research_policy='strict' requires research priors — run the Import Research Priors utility (CLI/GUI)."}`** (exit 1). No silent fallback, no fabricated tag. |

Both `generate_system` paths and `evaluate_feasibility` catch `PriorsUnavailable` from `get_priors`
and return the curated error. The R2 silent-fallback note (`feasibility.py:710–714`) is **removed**
(replaced by the real selector). `strict` gates **both** sampling and Layer-3 (D5).

---

## 6. Wiring `generate.py` + `feasibility.py` (the only engine edits)

### 6a. `core/generate.py`

- `_generate_synthetic(seed, spectral_class, n_planets, require_habitable, research_policy="permissive")`
  and `_generate_real_anchor(..., research_policy="permissive")` gain the additive kwarg;
  `generate_system` passes `research_policy` to both (it already accepts it).
- `priors = DefaultPriors()` at `:416` and `:595` → `priors = get_priors(research_policy)`
  (wrapped so `PriorsUnavailable` → the curated `{"error"}`).
- The star `grounding` (`:266`) and the synthetic/anchor `notes` (`:449,:697`) read `priors.grounding`
  and append `priors.version` (when set) — e.g. `"realism priors = ResearchPriors
  (research-calibrated, sample-2026-06-24)."`.

### 6b. `core/feasibility.py`

- `_build_base_system` already routes through `generate_system`'s internals → it threads
  `research_policy` through to the base build (so sampling is calibrated under `strict`).
- Layer-3 (`_layer3_*`, `:733–775`) reads `priors.origin_priors[context_key]` when present (the
  provider passed in), falling back **per-key** to the existing `DefaultPriors` heuristic for an
  omitted context; the `grounding` it emits is `priors.grounding` (and the per-row grounding is the
  heuristic's `default-extrapolation` for a fallback row even under `strict` — honest mixed tagging).
- The strict-fallback note block (`:710–714`) is replaced by the `get_priors` selector + the curated
  `PriorsUnavailable` error.

**Determinism:** the provider changes values only; the RNG draw order is unchanged. A new test pins a
`strict`-with-perturbed-sample run deep-equal across two invocations, and asserts it **differs** from
the `permissive` run (proving `strict` actually re-samples).

---

## 7. `query.py` — `generate-system --research-policy` (D2)

Add `--research-policy {permissive,strict}` (default `permissive`) to the existing `generate-system`
subcommand (the `--nbody` pattern at `query.py:1526`), passed straight into
`generate_system(..., research_policy=…)`:

```bash
query.py generate-system --seed 88 --spectral-class K2V --planets 6                       # permissive (default), byte-identical
query.py generate-system --seed 88 --spectral-class K2V --planets 6 --research-policy strict   # calibrated (if priors loaded) / error (if not)
```

- `permissive`/omitted → byte-identical to today.
- `strict` + cache → research-calibrated; `grounding`/`notes` carry the dataset version.
- `strict` + no cache → curated `{"error"}` exit 1 (self-validating, Phase H).
- A bad `--research-policy` value → argparse exit 2.

No ingest/status subcommand (D2).

---

## 8. GUI — importer panel + policy selector (in place)

### 8a. `ImportResearchPriorsPanel` (`gui/panels/csv_utility.py`, Utilities nav)

Mirrors `ImportGcnsPanel` / `ImportHypatiaPanel` / `FetchDustMapPanel`: a contract-file field
(default path + Browse) + **Check** / **Import** buttons + a background `QThread` (`_ResearchPriorsWorker`)
+ a progress/status label + a completion summary (`dataset_version`, axes loaded, origin contexts).
Calls `compute_research_priors_ingest`. Registered in nav + `panels/__init__.py`.

### 8b. `SystemGeneratorPanel` research-policy selector (`gui/panels/generator.py`, in place)

- A **"Research policy"** combo (`permissive | strict`) added to the form (additive; default
  `permissive` → unchanged R1/R2 behaviour). Passed into the `generate_system(..., research_policy=…)`
  call the panel already makes.
- `strict` with no priors loaded → the panel surfaces the curated error (it does **not** silently
  generate).
- The existing Source-coloured Planet Table + four-layer cards are unchanged; under `strict` the
  **grounding badges read `research-calibrated (<version>)`** and the notes name the dataset (driven
  entirely by the core output — no new GUI logic beyond rendering the string already present).

### 8c. `DbStatusPanel` (opt 57) row

Append a **Research Priors** status line (`Loaded` + `dataset_version`, or `Missing`) via
`get_research_priors_status()` — a pure-pathlib/JSON read, no `ResearchPriors` import — exactly as the
panel appends the cached dust-map files today.

---

## 9. Tests (offline; no network)

- **`tests/test_research_priors.py`** (new)
  - **Contract validation:** the sample + identity fixtures validate; each malformed axis (missing,
    wrong type, `lo > hi`, unknown `schema_version`, bad `plausibility`) → curated `{"error"}`.
  - **`ResearchPriors.load`:** builds from the identity fixture; **provider parity** (exposes the
    full `DefaultPriors` surface + `origin_priors`/`version`/`grounding`); `n_planet_dist` keys are int.
  - **`get_priors`:** permissive → `DefaultPriors`; strict + cache → `ResearchPriors`; strict + no
    cache → `PriorsUnavailable`.
  - **Importer (`compute_research_priors_ingest`):** happy path writes cache + meta; **Gate-1** — a
    malformed contract leaves an existing cache intact; `get_research_priors_status` shape.
    (Cache dir monkeypatched to a tmp dir — the `data/dust` test pattern.)
- **`tests/test_generate.py`** (additions)
  - **`permissive` byte-identical:** the existing R1 determinism deep-equal tests stay green
    untouched (additivity proof).
  - **`strict` + identity fixture:** output == the `permissive` output **except** the star
    `grounding` / notes (the "only the badge changes under identity priors" assertion).
  - **`strict` + perturbed sample:** deterministic (deep-equal across two calls) **and** differs from
    `permissive` (sampling actually re-drawn); `grounding` reads `research-calibrated`, notes name the
    version.
  - **`strict` + no cache → curated `{"error"}`** (cache dir pointed at an empty tmp dir).
- **`tests/test_query_generate.py`** (additions) — `--research-policy` subprocess contract:
  permissive parity (== no-flag), strict-with-cache (via a seeded tmp cache + `SPACE_APP_DB`-style
  override), strict-no-cache exit 1, bad value exit 2.
- **`tests/test_generator_panel.py`** (additions) — the policy selector emits the kwarg; a `strict`
  render flips the grounding badge; `strict`-no-cache surfaces the error; `ImportResearchPriorsPanel`
  construction + the worker happy/error render (mocked ingest); the `DbStatus` row.

---

## 10. Numbered checkpoints (one at a time; full suite green at each; stop for review)

> Run headless: `QT_QPA_PLATFORM=offscreen python -m pytest -q -k "not live"`. **3 live-network
> failures are the expected baseline**, not regressions. Each checkpoint ends with a GUI test plan
> where relevant (nav path, tabs, exact values, error cases, what changed vs. didn't).

| CP | Deliverable | Gate |
|---|---|---|
| **R3-C1** | **Data contract**: the schema doc (`docs/research-priors-contract.md` or a section in `docs/integration.md`) + the committed **sample template** (`data/research_priors.sample.json`, perturbed) + the **identity** test fixture + `validate_priors_contract` + its unit tests (good validates; each malformed axis → curated error). **No engine wiring.** | suite green; pure/offline |
| **R3-C2** | `core/priors.py` **`ResearchPriors` + `get_priors` selector + `PriorsUnavailable`** + provider-parity / selector tests. | suite green |
| **R3-C3** | `core/research_priors.py` **importer (`compute_research_priors_ingest`) + storage (cached file, D1) + `get_research_priors_status`** + validate-before-store / status tests (tmp cache dir). | suite green |
| **R3-C4** | **Thread the selector** through `core/generate.py` (2 sites + `research_policy` into synth/anchor) + **functional `strict`** + **grounding re-tag** (read `priors.grounding`/`version`) + tests: **`permissive` byte-identical** (R1/R2 deep-equal untouched), `strict`+identity == permissive-except-badge, `strict`+perturbed deterministic-and-different, `strict`+no-cache → curated error. | suite green |
| **R3-C5** | **Layer-3 calibration** in `core/feasibility.py` (read `origin_priors`, per-key fallback, tag `priors.grounding`; remove the silent-fallback note block) + tests (calibrated context vs fallback context; determinism; `strict`-no-cache error through the feasibility path). | suite green |
| **R3-C6** | `query.py generate-system **--research-policy**` flag + subprocess contract tests (permissive parity, strict-with-cache, strict-no-cache exit 1, bad value exit 2). | suite green |
| **R3-C7** | GUI: **`ImportResearchPriorsPanel`** + the **research-policy selector** + grounding-badge flip in `SystemGeneratorPanel` + **`DbStatus`** row + headless smokes. | suite green; **manual GUI verify** |
| **R3-C8** | Docs (`CLAUDE.md` test inventory + the R3 data-path note, `docs/integration.md` `--research-policy` + the data-contract surface, `docs/gui-architecture.md` the new panel + selector, `future_phases.md`/the PHASE-status table R3→done) + final full-suite green. | suite green |

---

## 11. Success criteria (R3)

A worldbuilder (or the sister project) can drop a versioned formation-priors contract file in, import
it (validate-before-store, GCNS-style, into a gitignored cache), and then generate / check-feasibility
under `research_policy="strict"` to get output **sampled from and narrated by those priors**, with
every synthetic field and origin hypothesis re-tagged `research-calibrated (<dataset_version>)` and the
version stamped into the provenance `notes`. **`strict` with no priors loaded is an explicit, honest
error** — never a quiet guess wearing a calibrated badge. **`permissive` (the default) is byte-identical
to R1/R2** — proven by the untouched deep-equal determinism tests. Because the real sister-project
dataset isn't ready, R3 proves the whole hook against a **sample file**; landing real priors later is a
**data swap, not a code change** — the seam was built for exactly this. Suite green (offscreen, 3
live-net baseline). **R3 completes Phase R.**
