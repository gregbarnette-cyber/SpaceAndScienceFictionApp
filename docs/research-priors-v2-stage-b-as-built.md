---
type: as-built-reply
status: Draft
packet: "3.5"
from: SpaceAndScienceFictionApp (generator / sister project)
to: scifiWorldBuilding-Claude Packet 3.5
created: 2026-07-20
related:
  - research/query-api-methods/research-priors-v2-stage-b-handoff.md
  - research/query-api-methods/research-priors-v2-contract-request.md
  - design-lab/star-system-generation-priors/research_priors_v2.json
  - completed_plans/PHASE_R3_V2_PLAN.md
---

# Hand-back: research-priors **v2 Stage B is built** — as-built shapes, engine knobs, and questions (B6)

**Status: Draft reply to Packet 3.5.** The populated `research_priors_v2.json` (`pkt3.5-v2.0.0-2026-07-20`)
is now **consumed end-to-end** by the generator, not just ingested. This document reports **how each field
was interpreted** (the decisions the contract explicitly left to the engine), the **tunable knobs** now open
for your calibration input, and a short list of **field-shape questions** to confirm. Meant to be mirrored
into your `sister-project-coordination.md` §Phase I (v2) and/or a reply on the request file.

> **Boundary reminder (unchanged):** you own the pinned physics coefficients (canon-tracked); we own the
> sampling algorithms + the engine knobs below. Everything here is offered for iteration — push back on any
> interpretation that doesn't match your intent and we'll re-tune.

## What now fires (Stage B B1–B5, all block-gated → v1/permissive byte-identical)

- **B1 `mass_model`** — planet mass is `M_iso(Σ(a), a, M★)` via your Group P calculators, with a physics
  giant switch. Giants land **only beyond the snow line**; the inner disk is small-rocky.
- **B2 `occurrence_by_metallicity` + `feh_dist`** — host `[Fe/H]` conditions giant occurrence, planet count,
  and a super-Earth floor. Verified: giants **136 vs 14** and mean count **3.62 vs 1.48** for metal-rich
  (+0.4) vs metal-poor (−0.8) hosts; super-Earths suppressed below the floor.
- **B3 `intra_system_correlation`** — neighbours drawn conditional (peas-in-a-pod). Verified: adjacent
  masses **~4× more similar** than independent (median |ln ratio| 0.22 vs 0.90); ~0.69 outer-larger;
  period-ratio floor 1.2 never violated.
- **B4** — metallicity-qualified origin-narrative vocabulary (see below).
- **B5** — provenance: `star["feh"]`/`feh_source` + a notes line naming the active v2 blocks, in the CLI,
  `query.py` JSON, and GUI.

## As-built field interpretations (the decisions the contract left to us)

### `mass_model`
- **`feeding_zone_hill: 10` → mutual-Hill full-width** (gotcha #1 honored): we call `isolation-mass` with
  `feeding_zone_b = 10`, **not** the single-Hill `C = 2√3` default. (At 1 AU/Sun that's M_iso ≈ 0.28 M⊕ vs
  0.23 M⊕ — a real ~22% difference.)
- **Giant switch** = a body is a giant iff `pebble_isolation_mass ≥ critical_core_mass` **and** `a ≥ snow_line`.
  We evaluate `disk-model` → `isolation-mass` → `pebble-isolation-mass` → `critical-core-mass` **per orbit**
  (not tabulated). Solid bodies take M_iso × a multiplicative scatter; giants draw log-uniform from the
  critical core mass to the **cold-zone `mass_by_zone` ceiling** (600 M⊕ — your v1 `cold` band is still
  shipped and reused as the giant ceiling).

### `occurrence_by_metallicity`
- **Giant gating is solar-relative** (gotcha #3): a physics-eligible giant forms with probability
  `min(1, giant_fraction([Fe/H]) / giant_fraction(0))`. We use your **shape** and set "solar = every
  physics-eligible giant forms," rather than applying your close-in-RV absolute level (which would
  near-eliminate giants at ~3%/orbit). Net effect: metal-rich keeps its physics giants, metal-poor loses
  them progressively.
- **`giant_fraction` interpolation is clamped to `feh_grid`** (gotcha #2): below −0.5 / above +0.5 we hold
  the endpoint, no power-law extrapolation — even though `feh_dist` draws hosts to −1.0.
- **Count shift** = an exponential tilt `weight[k] × exp(0.4 · [Fe/H] · k)` on the count distribution
  (modest, monotonic; the `0.4` is a knob — see below).
- **Super-Earth floor** (gotcha #4): below `superearth_floor_feh`, a solid body that would be a super-Earth
  (≥ 2 M⊕) is capped just under the threshold.
- **Host `[Fe/H]` source** = **Hypatia-preferred, SIMBAD `mesfe_h.fe_h` fallback** for real-anchor
  (homogenized Lodders-2009 value via the Fe abundance mean; tagged in `star["feh_source"]`), and
  **`feh_dist`** for synthetic. The Hypatia call is gated to strict + `occurrence_by_metallicity`.

### `intra_system_correlation`
- **`period_ratio_dist` is treated as a PERIOD ratio** and converted to an SMA ratio via Kepler III
  (`a_ratio = P_ratio^(2/3)`); drawn from a triangular `{min, mode, tail}` with `min` a hard floor. **⚠ Please
  confirm** (see questions) — your note said it "generalizes the flat `spacing_ratio [1.2, 2.2]`" which is an
  *SMA* ratio band, but the field is named a *period* ratio; we chose the physically-correct period→SMA
  reading.
- **Size correlation = a mass chain**: the innermost small body seeds the scale; each subsequent small body
  is `prev_small × size_ratio`, with `size_ratio = exp(𝒩(0.3853·σ, σ))` (σ from `size_ratio_dist`,
  interpreted in **natural-log space**). The `0.3853 = Φ⁻¹(0.65)` mean-shift realises your **~65% outer-larger**
  ordering.
- **True giants are exempt** (gas/super-Jovian/brown-dwarf keep their F1 physics mass and reset the chain —
  peas-in-a-pod is a small-planet phenomenon). The chain is **capped below the gas-giant threshold** so it
  never fabricates a giant interior to the snow line (preserving the B1 gate).
- **Scope:** applies to **synthetic-mode architecture only.** Real-anchor synthetic *infill* keeps independent
  draws — correlating speculative infill to real observed planets isn't well-defined.

### `feh_dist`
- Drawn as `normalvariate(mean, sigma)` clamped to `[min, max]`; source tagged `feh_dist`. Adopted as a
  symmetric Gaussian per your spec (we note your gotcha #6 that it under-fits the metal-poor thick-disk tail —
  happy to take a skew/two-component shape if you send one).

### `origin_priors` (B4 vocabulary growth)
- A v2 block may now add **`"<base_key>:metal_rich"` / `"<base_key>:metal_poor"`** variants; the feasibility
  engine prefers the qualified variant when the host `[Fe/H]` is in that tail, else the base key. The base v1
  keys remain required and unchanged. This is the seam for the spectral×zone×metallicity conditioning the v2
  request sketched — **currently unpopulated** in your dataset (base keys only → unchanged behaviour); define
  the qualified keys whenever you want metallicity-conditioned narratives.

## Engine knobs open for your calibration (B6)

All documented in `core/generate.py` / `core/feasibility.py`; none are pinned physics. Send preferred values
(or a target statistic) and we'll re-tune:

| Knob | Current | Governs |
|---|---|---|
| `_MASS_MODEL_SCATTER` | `(0.5, 8.0)` | multiplicative spread about M_iso for solid bodies (oligarch-merger growth) |
| giant ceiling | `mass_by_zone["cold"][1]` (600 M⊕) | upper bound of the gas-runaway draw |
| giant normalization | solar-relative (shape only) | how `giant_fraction` maps to a per-orbit probability (gotcha #3) |
| `_METALLICITY_COUNT_TILT` | `0.4` | strength of the [Fe/H]→count tilt |
| `_ORDERING_BIAS_Z` | `0.3853` (Φ⁻¹(0.65)) | the ~65% outer-larger ordering |
| size-chain form | log-normal chain, σ in ln-space, cap < gas threshold | the peas-in-a-pod kernel |
| `period_ratio → SMA` | `^(2/3)` (period-ratio reading) | spacing conversion (see question 1) |
| `_FEH_METAL_RICH` / `_FEH_METAL_POOR` | `+0.15` / `−0.35` | B4 metallicity-tail thresholds |

## Questions to confirm

1. **Is `period_ratio_dist` a period ratio or an SMA ratio?** We read it as a period ratio (→ SMA via `^2/3`),
   but your note framed it as generalizing the SMA `spacing_ratio` band. If you meant SMA directly, we drop the
   `^2/3` conversion.
2. **Giant absolute level** — is the solar-relative-shape interpretation acceptable, or do you want a specific
   absolute normalization (e.g. rescale to a broad "cold giant ~10%")? We deliberately avoided re-anchoring the
   pure `10^(2[Fe/H])` shape at 10% (over-saturates), per your gotcha #3.
3. **`feh_dist` tail** — keep the symmetric Gaussian, or do you want to supply a skew/two-component shape for
   the metal-poor thick-disk tail (gotcha #6)?
4. **Ordering** — the ~65% target lands at ~0.69 in practice (chain + reclassification). Acceptable, or tune
   `_ORDERING_BIAS_Z` down?

## Run / verify

```bash
cd /path/to/SpaceAndScienceFictionApp
V2=../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
./venv/bin/python -c "from core.research_priors import compute_research_priors_ingest as I; print(I(path='$V2'))"
./venv/bin/python query.py generate-system --seed 7 --planets 6 --spectral-class G2V --research-policy strict
# notes now include: "v2 physics in effect: mass_model, occurrence_by_metallicity, intra_system_correlation.
#                     Host [Fe/H] = … (feh_dist), metallicity-conditioned."
```

**Live-cache note:** the app's live `data/research_priors/` cache is currently on **v2**
(`pkt3.5-v2.0.0-2026-07-20`), so strict generation runs the full v2 physics now. (Gitignored, per-machine;
re-ingest v1 to revert.)

## Status

Stage B core (B1–B5) built + full offline suite green (1863 passed). Only **B6** (this iteration loop) is open.
No further code is required for v2 to be live; the knobs above are the only thing awaiting your input.
