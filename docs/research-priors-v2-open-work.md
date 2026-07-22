---
type: plan
status: Open
packet: "3.5"
created: 2026-07-22
related:
  - docs/research-priors-v2-close-binary-actions.md
  - docs/research-priors-contract.md
  - core/research_priors.py
  - core/generate.py
  - ../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
  - ../scifiWorldBuilding-Claude/design-lab/close-binary-census-integration-change-set.md
---

# Research-priors v2 — open work (hand-off plan)

**Read `docs/research-priors-v2-close-binary-actions.md` first.** It is the round record and explains
*why* the decisions below were made. This file is only what remains.

Written 2026-07-22 at the end of the close-binary round. Assume the reader has no memory of it.

## 0. Where things stand

- Sister dataset: **`pkt3.5-v2.8.0-2026-07-22`** at
  `../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json`
- **Eight** v2 blocks, all validated and exposed. Six are **sampled**; two are **not** (§2 below).
- Suite green: **1960 pass, 1 skipped**.
- Coordination ran over an **ephemeral** channel at `/home/greg/claude/coordination-channel.md`.
  Both sides are mirrored (APP → the actions doc; WB → `sister-project-coordination.md`), so the
  channel may already be gone. **Do not treat its absence as lost work.**

Re-verify the whole chain in one go:

```
V2=../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
venv/bin/python -c "import json,sys; sys.path.insert(0,'.'); \
  from core.research_priors import validate_priors_contract, present_v2_blocks, compute_research_priors_ingest; \
  d=json.load(open('$V2')); print(validate_priors_contract(d) or 'VALID'); print(present_v2_blocks(d)); \
  print(compute_research_priors_ingest(path='$V2')['dataset_version'])"
venv/bin/python query.py generate-system --seed 3 --research-policy strict
QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests
```

> **If `data/research_priors/` is empty** (it is gitignored, so a fresh clone has no cache), run the
> ingest line above once before anything else will work under `--research-policy strict`.

## 1. UNCOMMITTED — do this first

At the time of writing, **nothing from this round was committed**; the user intended to commit
manually.

- **APP (9 files):** `CLAUDE.md`, `core/generate.py`, `core/priors.py`, `core/research_priors.py`,
  `docs/research-priors-contract.md`, `tests/fixtures/research_priors_v2_sample.json`,
  `tests/test_generate.py`, `tests/test_research_priors.py`, and the new
  `docs/research-priors-v2-close-binary-actions.md`.
- **WB (12 files):** the dataset + its README, `canon/multiple-star-systems.md`, the D1 promotion
  record, `consistency-reference.md`, `decisions.md`, `open-questions.md`, `claim-map.md`, the
  reservoir (§10/§10.8), the change set, `SUMMARY.md`, `sister-project-coordination.md`.

The WB side contains an executed **canon promotion** and probably deserves its own commit, separate
from the priors work. Backups of v2.3.0–v2.7.0 were in a session scratchpad and are **gone** — git is
now the only history.

## 2. The blocked items, and exactly what clears each

### B1 — `stellar_multiplicity` sampler · blocked on a JUDGEMENT, not a fetch · **cheapest unblock**

**Blocker.** `ecc_dist`'s 12 d circularization boundary is a **solar-type** result (Raghavan 2010,
*abstract-grade*). The generated census is **~77% M dwarfs**. No M-dwarf circularization period exists
anywhere in the corpus — confirmed absent, not merely unsearched (Winters 2019 carries no
eccentricity data at all).

**What clears it — either:**
- **(a)** An M-dwarf circularization period gets pinned (WB fetch), **or**
- **(b)** The user makes an **explicit, recorded** decision to extrapolate the solar-type boundary
  knowingly. This costs nothing but a tag and is available immediately.

**Do not** just build the sampler and pick a default quietly. The whole point of `ecc_dist` carrying
`consumer_must_not_default_to_zero` is that a silent `e = 0` makes every drawn binary maximally
planet-friendly and inflates stable-HZ rates — eccentricity, not separation, is the habitability
killer for close pairs (GJ 570 BC has no stable circumbinary HZ at e = 0.765 despite an unremarkable
0.79 AU separation). Note also **BY Dra: e = 0.300 at P = 5.98 d**, a K-dwarf pair well inside the
boundary and demonstrably not circularized — the boundary is soft.

**Value when unblocked:** generated companions in the shape the existing `--companion` hint takes
(`{mass_solar, sma_au, ecc}`), feeding `feasibility._binary_gate` → Holman–Wiegert S/P-type stability
with **no parallel code path**. Independent of anything activity-related.

**Guard:** a synthetic multiplicity draw must **never** overwrite an observed GCNS multiplicity in
`--anchor-star` mode (`star["multiplicity"]` is GCNS-derived there).

### B2 — `stellar_activity` sampler · blocked TWICE

**Blocker (i) — there is no stellar age in the generator.** `core/generate.py` has no age axis and
the star dict has no age key, in either mode. The block's chain is
**age → P_rot → Ro = P_rot/τ → L_X/L_bol**, so the single-star branch cannot run at all. The locked
branch is computable in principle (`P_rot = P_orb`) but depends on **B1**.

**What clears it:** an `age_dist` block from WB — requested 2026-07-22, **accepted and deferred**.
Three constraints were sent with the request and should be honoured by whatever lands:
1. **Conditional on mass, not marginal.** Mass is drawn before age, and an unconditioned draw
   produces stars older than their own main-sequence lifetimes. `compute_stellar_evolution(mass_solar,
   current_age_gyr)` (`core/equations.py`, Phase L3) returns `ms_end_gyr` for the truncation — but
   only apply it if the block says truncation is intended.
2. **It interacts with `feh_dist`.** There is an age–metallicity relation; drawing both independently
   produces combinations the population does not contain (old metal-rich thin-disk stars). "Independent
   enough at this precision" is an acceptable answer — but it must be a recorded answer, not an
   assumption.
3. **Population structure** (thin/thick/halo) may or may not matter at this precision.

**Anchor path is APP's to wire and is not blocked:** observed ages exist on HWC (`S_AGE`) and Mission
Exocat (`st_age`); mirror the Hypatia→SIMBAD `fe_h` fallback pattern.

**Blocker (ii):** `p_orb_days` comes from B1.

### B3 — the >500 AU model over-extension · blocked on a pinned Öpik normalization

At σ = 1.16, **~4.4%** of drawn wide companions land beyond ~500 AU, where canon §2 now places an
Öpik-like distribution instead of the log-normal. Recorded as
`stellar_multiplicity.separation_dist.components[1].domain_overextension`, **flagged not clamped** —
because there is nothing to clamp *to*. D&K's "0.2–0.3 pc for early-M primaries" is a **lead, not a
fit**.

**What clears it:** a pinned Öpik normalization + outer cutoff. Then upper-bound the wide component
at ~500 AU with an Öpik tail beyond, matching canon's structure. **This also mostly retires the σ
divergence (§3 below)** — one fetch closes two open items.

### B4 — WB's own queue (reservoir §10.7)

Not APP work, but it gates D1–D4 and some of the above. In WB's stated priority:
1. **Huang et al. 2020 body** — the ~10× eclipsing-binary flare rate. Needs a **journal-side or ADS
   route; not on arXiv.**
2. **§7.2 Winters-2020 parallax defect** — needs a Gaia DR3 re-check. Cheap.
3. **ξ UMa Ba/Bb, δ Tri, 44 Boo B** — still `[LEAD]`; try Gaia DR3 NSS.
4. **§9.8 ADS-native search** — tool-blocked, needs an ADS path.
5. **§9.3 Path B** — low value now that C-5 gave Path A body-verified constants.

**Also outstanding on the WB side:** N2's *migration* half (the verification landed as reservoir §10;
`research/binary-and-multiple-star-systems/source-ledger.md` and `claim-map.md` were never extended),
plus **N3** and **N5** of the change set.

> **APP cannot do any of B4.** This session has only `WebFetch`/`WebSearch`, which the sister's
> `hard-sf-research` skill explicitly disqualifies for evidence capture (it returns a small-model
> summary, not the page's text, so it "NEVER counts as opening or inspecting a source"). Research
> goes through the sister repo's MCP servers. Hand it over; do not attempt it here.

## 3. Standing divergence — deliberate, do not "fix"

`separation_dist.wide_lognormal.log10_sigma_au = 1.16` (Winters 2019) **differs from canon §2's
σ_logP ≈ 1.3 = σ_log10(a) 0.867** (Duchêne & Kraus 2013). This is recorded in
`sigma_diverges_from_canon` and is **intentional**:

- Canon kept D&K for **corpus hygiene** — smallest blast radius for what was a transcription fix.
  Explicitly **not** because the number is better.
- The two σ's are **not competing estimates of one quantity**: D&K's is fitted under a <500 AU
  truncation, Winters' on an untruncated sample. Canon states a truncated log-normal so the truncated
  σ is domain-matched *there*; this component has no upper truncation so the untruncated fit is
  domain-matched *here*.
- **Scale:** σ has **no effect** on the realized close-pair rate (the F-2 truncation pins it at 0.087
  by construction). It moves canon §6's fully-suppressed <1 AU bin by ~6 pp.

A future session finding two σ's and "harmonising" them would be undoing a considered decision.

## 4. Invariants a future session must not break

**Three structural guards** are hard-enforced by the validators, each with a negative test asserting
it fails when subverted. They are not style; each encodes a defect that actually occurred:

| Guard | Breaking it causes |
|---|---|
| `ecc_dist.consumer_must_not_default_to_zero` is **true** | Every binary maximally planet-friendly; stable-HZ rates inflated |
| `circumbinary_xuv.component_count_scaling` is **1.0** | XUV scaled by star count, contradicting the geometric cancellation (a ratio identity — band independent) |
| `expected_locked_vs_single_delta.is_prior_field` is **false** | The locked-vs-single delta double-counted against the Rossby chain that produces it |

**Two shapes that look wrong and are correct** — tests exist to stop them being "tidied":
- `rotation_activity.log_lx_lbol_valid_range` is **descending** (`−4 > log R_X > −6.3`).
- `convective_turnover.mass_msun_grid` runs **hot-to-cool** (descending), matching Wright 2018's table.

**Three constants are one fitted package:** `(β = −2.70, Ro_sat = 0.16, log(L_X/L_bol)_sat = −3.13)`.
Wright 2018's τ(mass) table was fitted *assuming* them. Updating any one from a different paper
reintroduces the cross-fit that F-0 removed. The same warning is now in the sister's N4 table.

**`giant_switch` is not relaxed.** Inner giants bypass it as a controlled, tagged sub-population;
the gate itself is unchanged, and a regression test asserts any giant interior to the snow line
carries `giant_zone`.

**The `[2,3]` acceptance band is X-ray contrast, not XUV**, and is *instantaneous, matched-age* — it
must not be fed to cumulative-fluence arguments (doing so implied a ~67–550 M⊕ "rocky" world).

## 5. Recommended order

1. **Commit** (§1). Two repos, canon promotion probably separate.
2. **Decide B1's extrapolation question** — the only item needing nobody but the user, and it
   delivers a real capability.
3. **Hand B4 to the sister session**, priority as listed. B3's Öpik fetch is worth adding since it
   closes two items at once.
4. **B2 waits on `age_dist`**, which is correctly deferred — `stellar_activity` is a capability
   nothing in the setting consumes yet.

## 6. The pattern this round found four times — worth checking for deliberately

Four separate defects shared one shape: **something complete from one side, missing its other half.**
Canon carried a distribution centre without its width. `ecc` was emitted with nothing defining it.
`L_X` was labelled XUV with no conversion applied. `stellar_activity` named an input (age) that
nothing produces.

The cheap mechanical check that would have caught all four: **for every input a block names, ask which
block or code path produces it — and for every figure, ask whether its companion parameters came with
it.**
