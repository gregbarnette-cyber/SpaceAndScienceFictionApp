# PHASE R3-V2 — Research-Priors Contract v2 (schema_version "2.0")

Implementation plan for the sister project's **v2 contract hand-off**
(`scifiWorldBuilding-Claude/research/query-api-methods/research-priors-v2-contract-request.md`,
full spec `design-lab/star-system-generation-priors/v2-contract-proposal.md`). Extends the
R3 research-priors hook (`docs/research-priors-contract.md`, `PHASE_R3_PLAN.md`) from v1.0's
**marginals** to v2's **physics**, as an **additive, optional superset** — v1.0 datasets keep
validating/ingesting and permissive output stays byte-identical.

> **Provenance boundary (locked, do not re-litigate).** Packet 3.5 supplies the *populated*
> v2 dataset and the pinned physics coefficients (canon-tracked in
> `canon/planetary-formation-mechanisms.md` §10); **we own** the schema acceptance, the sampling
> algorithms, the feasibility interplay, the RNG/determinism, and the GUI. Iterate field shapes
> back to them; never hand-edit their coefficients.

---

## Decisions taken (2026-07-20)

- **Scope:** Stage A (schema/plumbing) **built now**; Stage B (engine sampling) deferred until Packet 3.5
  delivers a populated v2 dataset.
- **Synthetic-mode `[Fe/H]` (F2):** the new optional **`feh_dist`** contract axis (Gaussian mean/sigma
  + optional clamp). Synthetic hosts draw from it; when absent, `star["feh"]=None` → F2 inert.
- **Live v1 cache refreshed** off the `sample-2026-06-24` placeholder onto the sister's real
  `pkt3.5-v1.0.2-2026-07-09` (data swap, gitignored — re-ingest to change).

**Stage B unblocked (2026-07-20).** Packet 3.5 delivered the populated
`research_priors_v2.json` (`pkt3.5-v2.0.0-2026-07-20`) — validates/ingests clean against Stage A, all
four blocks. Hand-off + 7 calibration gotchas:
`scifiWorldBuilding-Claude/research/query-api-methods/research-priors-v2-stage-b-handoff.md`.

**Stage B-B1 (mass_model / F1) — BUILT (2026-07-20).** `core/generate.py`: `_mass_model_draw` gated on
`getattr(priors,"mass_model",None)`. Σ_solid(a)→M_iso (mutual-Hill `feeding_zone_b` — **gotcha #1
encoded**) + giant switch (pebble-isolation ≥ critical core AND beyond snow line → gas runaway); solid
bodies scatter about M_iso, giants log-uniform to the cold ceiling. Engine knobs (scatter band, giant
ceiling) documented, not pinned. `mass_solar` added to real-anchor `derived`. `TestMassModelDraw` +
suite green. Verified: giants land only beyond the snow line; permissive/v1 byte-identical (identity
test unchanged).

**Stage B-B2 (occurrence_by_metallicity + feh_dist / F2) — BUILT (2026-07-20).** Adds a nullable
`star["feh"]` + `star["feh_source"]`: synthetic draws from `feh_dist` (`_draw_feh`, `normalvariate`+clamp,
source `feh_dist`); real-anchor is **Hypatia-preferred, SIMBAD fallback** (`_resolve_anchor_feh` — Hypatia's
homogenized Lodders-2009 [Fe/H] via the Fe abundance mean, else SIMBAD `mesfe_h.fe_h` — new additive `fe_h`
key on `compute_simbad_lookup`; source tagged `hypatia`/`simbad`). The extra Hypatia network call is gated
to strict+`occurrence_by_metallicity` only (permissive gets the cheap SIMBAD read, no added call). Three gated effects:
**giant gating** relative-to-solar `giant_fraction([Fe/H])/giant_fraction(0)`, interpolated CLAMPED to
`feh_grid` (**gotchas #2/#3**); **count shift** exp-tilt toward higher counts with [Fe/H]
(`_metallicity_count_items`); **super-Earth floor** caps solid bodies below the super-Earth threshold
when `[Fe/H] < superearth_floor_feh` (**gotcha #4**). All gated on `occurrence_by_metallicity` + a host
[Fe/H] → permissive/v1 byte-identical (`star["feh"]=None`). Engine knobs (`_METALLICITY_COUNT_TILT`,
solar-relative giant normalization) documented, not pinned. `TestMetallicityConditioning` + suite green.
Verified: giants 136 vs 14 and mean count 3.62 vs 1.48 (metal-rich +0.4 vs metal-poor −0.8); super-Earths
suppressed below the floor.

**Stage B-B3 (intra_system_correlation / peas-in-a-pod / F3) — BUILT (2026-07-20).** The joint-draw shift.
`_synth_planets` now draws neighbours conditional on each other (gated → v1/permissive byte-identical):
**spacing** from the triangular `period_ratio_dist` {min hard floor, mode, tail} → SMA via Kepler III
(`_spacing_ratio_draw`, generalizes the flat `spacing_ratio` band); **size** a peas-in-a-pod mass chain
(`_apply_size_correlation`) — small bodies follow `prev × size_ratio`, log-normal median 1 (σ from
`size_ratio_dist`) biased ~65% outer-larger (`_ORDERING_BIAS_Z = Φ⁻¹(0.65)`; the `ordering` direction),
true giants (F1) exempt + chain-reset, capped below the gas threshold so no giant is fabricated inside the
snow line (**gotcha #5**). Synthetic-mode only (real-anchor infill keeps independent draws — documented).
`TestIntraSystemCorrelation` + suite green. Verified: period-ratio floor ≥ 1.2 respected; adjacent masses
~4× more similar than independent (median |ln ratio| 0.22 vs 0.90); 0.69 outer-larger; B1 no-giant-inside-snow
invariant preserved. Engine knobs (σ log-space, chain form, `_ORDERING_BIAS_Z`) documented for B6 iteration.
**All three sampling features (F1/F2/F3) built.**

**Stage B-B4 (feasibility origin-priors vocabulary) — BUILT (2026-07-20).** Metallicity-qualified origin
keys: a v2 `origin_priors` block may add `"<base_key>:metal_rich"` / `":metal_poor"` variants;
`_origin_hypotheses` prefers the variant when the host [Fe/H] falls in that tail (`_metallicity_tag`,
thresholds `_FEH_METAL_RICH=0.15` / `_FEH_METAL_POOR=-0.35`), else the base key — fully backward-compatible
(the delivered dataset defines only base keys → unchanged). `feh` threaded into `_derived_from_star`.
`TestLayer3MetallicityVariant` + suite green.

**Stage B-B5 (query.py / GUI surfacing + provenance) — BUILT (2026-07-20).** `_v2_blocks_note` appends a
notes line naming the active v2 sampling blocks + the host [Fe/H]/source when metallicity-conditioned
(flows to CLI, `query.py` JSON, and GUI automatically). GUI generator panel: `[Fe/H] (source)` on the star
card + a 🧬 v2-physics provenance line. `TestV2ProvenanceNotes` + suite green. Verified `query.py
generate-system --research-policy strict` serializes `feh`/`feh_source` + the v2 note.

**Stage B core complete (B1–B5). Remaining: B6 — iterate the documented engine knobs with the sister
(`_MASS_MODEL_SCATTER`, `_METALLICITY_COUNT_TILT`, solar-relative giant normalization, `_ORDERING_BIAS_Z`,
the size-chain form, the B4 metallicity thresholds) against their real dataset; ship the as-built field
shapes back to `docs/integration.md` + the request file.**

**Stage A — BUILT (2026-07-20).** `_KNOWN_SCHEMA_MAJORS={"1","2"}`; four block validators
(`mass_model`/`occurrence_by_metallicity`/`intra_system_correlation`/`feh_dist`) validated when present;
`present_v2_blocks` helper; `ResearchPriors`+`DefaultPriors` expose the four attrs; importer/status +
DbStatus + Import panel record `v2_blocks`; `tests/fixtures/research_priors_v2_sample.json`;
`TestV2Superset` in `tests/test_research_priors.py`. No engine reads the blocks → generation
byte-identical (verified). Suite green.

## 0. Status / scheduling call (read first)

- **v1.0 is live and complete.** This app needs nothing more for v1.0. v2 is the sister's *roadmap*
  ask, tracked as **OQ-SG-1** — not a blocker.
- **We cannot fully build+test the engine-consumption features without a representative v2 dataset.**
  Feature payloads (the pinned `giant_fraction` grid, the `size_ratio_dist`, the disk params) come
  from Packet 3.5 "when v2 is scheduled." So the plan **splits at the dataset boundary**:
  - **Stage A (schema/plumbing) needs nothing from them** — we author a synthetic v2 fixture and
    build the whole accept→store→expose path. Independent, low-risk, ships green.
  - **Stage B/C (engine sampling) needs their data** — build against our fixture, then iterate
    against their real dataset. Larger, and gated on the metallicity decision (§3).
- **Recommendation:** land **Stage A now** (it de-risks the hand-off and lets them validate their
  populated v2 dataset against real code the moment it exists), and **schedule Stage B/C when the
  populated v2 dataset arrives**. Confirm with the user before starting Stage B.

---

## 1. The three v2 features → where each lands

| # | v2 block | v1 field it augments | Consumption site (this repo) | Reuse available |
|---|---|---|---|---|
| **F1** | `mass_model` (isolation-scaling) | `mass_by_zone` (flat log-uniform band) | `core/generate.py::_make_synth_planet` mass draw (+ `_zone_for`) | **`core/formation.py`** Group P calcs — call, don't tabulate |
| **F2** | `occurrence_by_metallicity` | `n_planet_dist` + a new giant fraction | count selection in `_generate_synthetic`/`_generate_real_anchor`; giant gating in the mass draw | Hypatia `[Fe/H]` in real-anchor; **new draw needed** in synthetic (§3) |
| **F3** | `intra_system_correlation` (peas-in-a-pod) | independent per-planet draws | `_synth_planets` loop (size + spacing become conditional on the previous planet) | none — new joint-draw kernel |

All three are **optional**: a v2 dataset omitting a block falls back to the v1 field; a v1 dataset
(no blocks) is byte-identical to today. This is the load-bearing invariant.

---

## 2. Determinism strategy (the hard constraint)

`generate.py`'s headline contract is *same seed → byte-identical output*, proven by the untouched
deep-equal tests (`test_generate.py`). Every v2 feature adds RNG draws (a metallicity, a giant roll,
correlated neighbours). Rule:

> **New draws are gated behind "is the relevant v2 block present *and* research_policy strict".**
> Permissive always → `DefaultPriors` (no v2 blocks) → the exact current draw order. v1-strict
> (dataset without v2 blocks) → same. Only strict + a v2 block present perturbs the stream, and only
> for that feature's draws.

Implementation: the mass/count/spacing helpers branch on `getattr(priors, "mass_model", None)` etc.
When absent, the code path is the current one verbatim (no extra `rng.*` calls, so the draw sequence
is unchanged). Add a regression test asserting a v2 dataset with all blocks stripped is deep-equal to
the v1 identity run.

---

## 3. The metallicity gap (decision required before Stage B/F2)

The generator carries **no `[Fe/H]`** today (verified: no `feh`/`metallicity` in `generate.py`/`priors.py`).
F2 has nothing to condition on. Options:

- **Real-anchor mode:** pull host `[Fe/H]` from Hypatia (`core.databases.compute_hypatia_data`, already
  wired elsewhere) or the SIMBAD `mesfe_h` field. Preferred — real data.
- **Synthetic mode:** must **draw** a host `[Fe/H]`. Needs a metallicity distribution — either a new
  optional contract axis (`feh_dist`, sister-supplied) or a fixed literature default. This is a genuine
  new engine concept (a new field on `star{}` + a new fixed-order draw).

**Recommendation:** add a nullable `star["feh"]` (real-anchor: from Hypatia/SIMBAD, else `None`;
synthetic: drawn from an optional `feh_dist` block, else `None`). When `feh is None`, F2 is inert and
falls back to flat `n_planet_dist` — keeping F2 fully optional and determinism-safe. Surface this to the
user as an explicit choice (draw synthetic metallicity vs. real-anchor-only F2).

---

## 4. Checkpoint plan

Mirrors the R3-CP structure. Each CP ends suite-green (offscreen; the 3 live-net failures are the
expected baseline, not regressions). Run: `QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest -q -k "not live"`.

### Stage A — schema / plumbing (no sister data required)

| CP | Deliverable | Gate |
|---|---|---|
| **V2-A1** | **Validator superset** in `core/research_priors.py`: `_KNOWN_SCHEMA_MAJORS → {"1","2"}`; add optional-block validators `_check_mass_model` / `_check_occurrence_by_metallicity` / `_check_intra_system_correlation` (shape + pinned-key presence + numeric ranges), each invoked only when the block is present. **v1.0 docs stay valid; blocks absent → no-op.** Grow the `origin_priors` context-key vocabulary per the request (spectral×zone×metallicity keys, additive). | suite green; pure/offline |
| **V2-A2** | **Fixtures:** author `tests/fixtures/research_priors_v2_sample.json` (a synthetic but well-formed v2: v1 axes + all three blocks with plausible pinned-shaped numbers) and keep a v1 fixture. Unit tests: v2 validates; each malformed block → curated `{"error"}`; **v1 fixtures still validate**; a v2-with-blocks-stripped == v1. | suite green |
| **V2-A3** | **Provider surface** in `core/priors.py::ResearchPriors`: parse+expose `mass_model` / `occurrence_by_metallicity` / `intra_system_correlation` as attributes (deep-copied, `None` when absent). `DefaultPriors` grows the same attrs set to `None` so `getattr` is uniform. Provider-parity tests (v1 dataset → all three attrs `None`, byte-identical surface). | suite green |
| **V2-A4** | **Importer/status** (`compute_research_priors_ingest`, `get_research_priors_status`): `meta.json` records which v2 blocks are present (`v2_blocks: [...]`), schema_version echoed. Status reader surfaces it (opt-57 DbStatus). Validate-before-store still Gate-1. Tests over a tmp cache. | suite green |
| **V2-A5** | **Docs:** `docs/research-priors-contract.md` v2 section (the three blocks + rules table + fallback semantics), `docs/integration.md` note, `CLAUDE.md` R3 line touched. Mark the sister's request "accepted, Stage A built; Stage B pending populated dataset." | suite green |

**Stage A exit:** a v2 dataset ingests, is exposed on the provider, and is reported by status — but **no
engine reads the blocks yet**, so all generation output is byte-identical to today. This is the artifact
the sister validates their populated dataset against.

### Stage B — engine consumption (needs a representative v2 dataset; confirm scheduling)

| CP | Deliverable | Gate |
|---|---|---|
| **V2-B1 (F1 mass_model)** | In `core/generate.py`, when `priors.mass_model` present: replace the log-uniform `mass_by_zone` draw with an **isolation-mass evaluation** — build the disk Σ(a) from `mass_model.disk`, call `core.formation.compute_isolation_mass` (+ `compute_pebble_isolation_mass` for the giant switch, `compute_critical_core_mass` for the runaway trigger), then apply a seeded scatter term (our sampling choice). Giants land where the physics allows. Absent block → current path verbatim. | suite green; **determinism preserved for permissive/v1** |
| **V2-B2 (F2 occurrence)** | Add `star["feh"]` (§3) + the metallicity-conditioned count/giant gating: interpolate `giant_fraction` on `feh_grid`, apply the `superearth_floor_feh` cliff, shift `n_planet_dist`. `feh is None` → inert fallback. New draws gated + fixed-order. | suite green |
| **V2-B3 (F3 correlation)** | Rework `_synth_planets` so that, when `intra_system_correlation` present, neighbours are drawn **conditional** on a seed planet (size ratio ~ `size_ratio_dist`, period ratio ~ `period_ratio_dist`, ~65% outer-larger ordering). Absent block → independent draws verbatim. | suite green |
| **V2-B4** | **Feasibility Layer-3**: consume any grown `origin_priors` context keys (already generic in `_origin_hypotheses`; mostly a vocabulary + `_origin_context_keys` extension for the new keys). | suite green |
| **V2-B5** | `query.py generate-system` + GUI `SystemGeneratorPanel`: surface the v2 knobs that are user-facing (e.g. synthetic-metallicity toggle); provenance `notes` name the v2 blocks in effect. Subprocess + headless-GUI tests. | suite green; manual GUI verify |
| **V2-B6** | **Iterate with sister** against their real populated v2 dataset; mirror as-built field shapes back into `docs/integration.md` + reply on the request file. Final full-suite green. | suite green |

---

## 5. Files touched (map)

- `core/research_priors.py` — validator superset, schema majors, block validators, importer/status meta.
- `core/priors.py` — `ResearchPriors` + `DefaultPriors` attribute surface (three new nullable attrs).
- `core/generate.py` — mass draw (F1), count/giant gating + `star["feh"]` (F2), `_synth_planets` conditional draws (F3); all block-gated.
- `core/formation.py` — **called, not modified** (Group P calcs). Confirm signatures suffice for a Σ(a)→M_iso spine.
- `core/feasibility.py` — `_origin_context_keys` vocabulary growth only.
- `query.py`, `gui/panels/generator.py`, `gui/panels/csv_utility.py` — surface knobs + status.
- `tests/` — `test_research_priors.py`, `test_generate.py`, `test_feasibility.py`, `test_query_generate.py` + new v2 fixtures.
- `docs/research-priors-contract.md`, `docs/integration.md`, `CLAUDE.md`.

## 6. Success criteria

A v2 dataset drops in as a **data swap** (Stage A) and, once the engine reads it (Stage B), generation
draws mass from the isolation-mass physics, conditions planet count/giants on the host `[Fe/H]`, and
draws neighbours correlated peas-in-a-pod style — every field tagged `research-calibrated (<dataset_version>)`.
**A v1.0 dataset and `permissive` remain byte-identical to today**, proven by the untouched deep-equal
tests. `strict` with no cache stays an honest error. Landing the sister's real v2 dataset is a data swap
plus the Stage-B engine work — never a schema break.
