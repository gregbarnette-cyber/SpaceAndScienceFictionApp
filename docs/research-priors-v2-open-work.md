---
type: plan
status: Closed
packet: "3.5"
created: 2026-07-22
updated: 2026-07-23
closed: 2026-07-23
superseded_by: docs/research-priors-v2-remaining.md
related:
  - docs/research-priors-v2-close-binary-actions.md
  - docs/research-priors-contract.md
  - core/research_priors.py
  - core/generate.py
  - core/besancon.py
  - ../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
  - ../scifiWorldBuilding-Claude/research/star-and-planetary-system-generation/age-dist-prior-T8.md
  - ../scifiWorldBuilding-Claude/design-lab/close-binary-census-integration-change-set.md
---

# Research-priors v2 — open work (hand-off plan) · **CLOSED 2026-07-23**

> **This plan is finished — every item in it is built or ruled closed.** Live work moved to
> **`docs/research-priors-v2-remaining.md`**. This file is kept as the **round record**: it is where the
> *reasoning* lives (why no power-law tail, why the σ divergence stands, why the close-pair rate was not
> recomputed, which claims were retracted and by whom). That reasoning stopped three separately-retracted
> claims from reaching the code, so read it before reopening anything.
>
> **§3–§4 are still live**: the standing divergence and the invariants are referenced from the new file
> rather than copied, so they have exactly one home. Do not delete them.

**Read `docs/research-priors-v2-close-binary-actions.md` first.** It is the round record and explains
*why* the decisions below were made. This file is only what remains.

Written 2026-07-22 at the end of the close-binary round. **Revised 2026-07-23** against the sister
project's completed follow-up research (WB commits `0e566e9` → `9cd7310`), which **cleared three of the
four blockers** the original hand-off listed. Assume the reader has no memory of either round.

## 0. Where things stand

- Sister dataset: **`pkt3.5-v2.10.0-2026-07-23`** at
  `../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json`
  (was `v2.8.0-2026-07-22` when this file was first written — **two dataset revisions have landed**).
- **Nine** v2 top-level blocks in the file, and as of 2026-07-23 **all nine validate, are exposed, and are
  sampled**. `age_dist` (new in v2.10.0) gained `_check_age_dist` in B2, so it now appears in
  `present_v2_blocks` rather than falling through the unknown-key path.
- Verified locally 2026-07-23 against the new dataset: `validate_priors_contract` → **VALID**;
  ingest → `pkt3.5-v2.10.0-2026-07-23`, 6 v1 axes / 10 origin contexts / **9** v2 blocks;
  `generate-system --seed 3 --research-policy strict` → normal output.
  Suite green: **2073 pass, 1 skipped** (1960 → 2014 Phase AM → 2033 B1 → 2053 B2 → 2061 B3 →
  2073 dedup rebuild).
- **Strict-mode output for a given seed CHANGED with B1/B2/B3.** The age, multiplicity and activity draws
  consume rng before planet placement, so every strict-policy system moved. This is expected (the same thing happened when `feh_dist`
  and the giant populations landed) and is why the dataset version is folded into the determinism tuple.
  **Permissive mode is byte-identical** — the sampler consumes no rng without the block.
- **The local ingest cache had gone stale.** `data/research_priors/meta.json` still held
  `pkt3.5-v1.0.2-2026-07-09` (a **v1** file) until it was re-ingested on 2026-07-23. The cache is
  gitignored and silent about being out of date — **re-run the ingest whenever the sister dataset
  moves**, and check `meta.json`'s `dataset_version` before trusting a strict-policy generation run.
- **Coordination channel.** The close-binary round used an ephemeral file at
  `/home/greg/claude/coordination-channel.md` (lowercase) which is **gone**. The 2026-07-23 round used a
  new one at **`/home/greg/Claude/coordination-channel.md`** (capital C — the shared parent of both repos,
  outside either git tree), carrying **MSG 001–011**: the B3 fetch request and its delivery, WB's
  adversarial refute-pass corrections, the B5 ruling, the FK Aqr / BY Dra adjudications, and the EUV
  finding. Both are ephemeral scratch and both sides mirror anything durable into their own repo (APP →
  this file + the actions doc; WB → `sister-project-coordination.md`), so **do not treat the channel's
  absence as lost work** — but do check the capital-C path before assuming a question was never asked.

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

## 1. Committed — and the stale text that survived it

**The "UNCOMMITTED — do this first" item is DONE.** Both repos are clean:

- **APP:** `cae961e` *v2 priors work* (2026-07-22, the 9 close-binary-round files), then `171988c`
  *Phase AM implemented* and `a3e7acd` *doc update*.
- **WB:** `0e566e9` *SpaceApp project research* (2026-07-22, the v2.8.0 state) and `9cd7310`
  *census work done and SpaceApp research finished* (2026-07-23 — v2.9.0 + v2.10.0, the three canon
  bundles, the census sweep, and the T8 deliverable).

Backups of v2.3.0–v2.7.0 were in a session scratchpad and are gone — **git is the only history**.

### 1a. Stale APP-side prose — **FIXED 2026-07-23** ✅ (kept as a record)

Two places still state the *reason* the multiplicity sampler was held, and that reason no longer exists
(the 12 d boundary was superseded by a source-backed M-dwarf ~6 d — see B1):

| File | What it says | Why it's now wrong |
|---|---|---|
| `docs/research-priors-contract.md` (the "two stellar blocks … NOT yet sampled" paragraph) | "the block's 12 d circularization boundary is measured on *solar-type* primaries … and no M-dwarf circularization period exists in the source corpus" | Both clauses are superseded: the boundary is now **~6 d, M-dwarf-measured**, and the corpus gap is **closed** (C52). |
| `CLAUDE.md` (the `core/` research-priors-v2 paragraph) | "deliberately not sampled yet: their 12 d circularization boundary is a solar-type result and the generated census is ~77% M dwarfs" | Same. The census is still ~77% M dwarfs; that is no longer a *blocker*, only context. |

Both were corrected when B1 landed: the contract doc now describes the sampler (and scopes the
"not sampled" claim to `stellar_activity` alone), and `CLAUDE.md` records the ~6 d M-dwarf pin. Kept here
because the *shape* recurs — a retired blocker left written down as current is how a future session
re-derives a decision that was already made.

## 2. The blocked items — **ALL FIVE CLOSED 2026-07-23**

B1 ✅ built · B2 ✅ built · B3 ✅ delivered (WB) + built (APP) · B4 ✅ cleared (WB) · B5 ✅ ruled closed (WB).
The `close-binary-census` dedup rebuild that was tracked alongside them is **also done** (§5 item 5).
What genuinely remains is in **§7** — **two** open follow-ups (7a, 7b), neither ever a B item and neither
blocking. The third (7c) closed on 2026-07-23 when WB opened the Weinberg primary.

### B1 — `stellar_multiplicity` sampler · **BUILT 2026-07-23** ✅

**Done.** `core.generate._draw_multiplicity` samples the block in **synthetic mode**: multiplicity roll →
mass ratio `q` → the close-pair / wide-log-normal separation mixture → eccentricity, emitted in the block's
own `consumer_contract` shape. `core.feasibility.evaluate_feasibility` consumes a drawn companion through
the **existing** `_binary_gate` (an explicit `--companion` overrides it); real-anchor GCNS multiplicity is
untouched. Suite **2033 pass / 1 skip**; docs updated (`docs/integration.md`, `docs/research-priors-contract.md`,
`docs/testing.md`, `CLAUDE.md` — the §1a stale text is gone).

Verified against the block's own targets (200k draws/mass): multiplicity fraction reproduces
`multiplicity_fraction` to ≤ 0.002 at every mass; close-pair share of multiples = **0.087–0.088** (the
by-construction F-2 rate); **zero** draws with `e == 0`; **zero** wide draws below the 62.6 d truncation;
f(e) above the boundary has median **0.247** (block: "~0.25") with the tail clamped at 0.9; below the 3 d
envelope, median **0.007** and minimum 0.001 (CM Dra's 0.005 is a typical draw). In the 3–6 d transition,
**21%** of draws exceed e = 0.25 — so BY Dra is an ordinary draw, not an outlier, which is the whole point
of the boundary being statistical.

**Two app-side modelling choices** (the block states f(e) in prose, not parametrically — the sampler names
them as ours in the emitted note, and they are the first thing to revisit if WB ever pins a shape):
Rayleigh(σ = 0.21) clamped at 0.9 above the boundary; a half-normal (σ = 0.01) floored at 0.001 below the
envelope, with a linear ramp between.

**One pre-existing defect found and fixed in passing:** `_synth_planets` appended the v2.2/v2.3 decoupled
giant populations **without re-sorting**, so a synthetic system containing an inner giant emitted planets
out of orbital order (the real-anchor path has always sorted). Latent since v2.3 and invisible until B1's
rng shift moved a K2V seed into that branch. Now sorted in both modes.

*Everything below is the original blocker record, kept because it is why the sampler could be built at
all — not because anything in it is still open.*

---

**The judgement call is off the table — the number was found instead.** WB's OPEN-item-C pass (Packet-4
**claim-map C52**, reservoir §12) resolved M-dwarf circularization to **~6 d**, superseding the borrowed
solar-type 12 d. Three independent lines converge:

- **Zanazzi 2022** (ApJL 927, L15; arXiv:2112.05868) — Kepler/TESS **field** EBs: "an average
  circularization period of ~6 days, as well as a short circularization period of ~3 days", and
  explicitly attributes the longer published values to small spectroscopic samples.
- **EBLM XVII** (Sethi et al. 2026, MNRAS accepted; arXiv:2603.04554) — low-mass secondaries: ~75%
  circularized, eccentric systems **confined to P ≳ 3 d**, e < 0.25.
- The census's **own 57-system K/M-dwarf e–P transition** at ~5–7 d (86–89% circular below 5 d → 33%
  circular at 5–10 d).

Physically expected: smaller M-dwarf radii → weaker tide → **shorter** P_circ than solar-type.

**What the dataset now carries** (`stellar_multiplicity.ecc_dist`, all new/changed in v2.9.0):

| Field | Value |
|---|---|
| `circularization_period_days` | **6.0** (was 12.0) |
| `circularization_period_range_days` | `[5.0, 7.0]` |
| `fully_circular_envelope_days` | **3.0** |
| `f_e_above_boundary` | `broad_median_~0.25_trending_thermal_tail_to_~0.9` |
| `below_boundary` | concentrated near zero — **never `e == 0` identically** (CM Dra is e = 0.005) |
| `domain` | **M-dwarf / low-mass pairs** (Raghavan's 12 d is now the separate solar-type reference) |
| `implement_as` | `statistical_boundary_NOT_a_threshold` (unchanged) |
| `queued_sources` → `pinned_sources` + `context_sources` | Raghavan/Winters **demoted to context**; Zanazzi / EBLM XVII / Meibom & Mathieu 2005 / the local census are pinned |

**BY Dra (e = 0.300 at P = 5.98 d) is no longer an anomaly** — it now sits inside the 3–6 d transition
zone, which is the whole reason the boundary must stay statistical. **Never default to `e = 0`**: a silent
zero makes every drawn binary maximally planet-friendly and inflates stable-HZ rates (GJ 570 BC has no
stable circumbinary HZ at e = 0.765 despite an unremarkable 0.79 AU separation).

**Residual caveat, recorded not blocking:** the pure **M+M** value is an extrapolation — no dedicated
large-sample M+M circularization study exists; the 57-system census is catalogue-grade and is the closest
anchor.

**Value when built:** generated companions in the shape the existing `--companion` hint takes
(`{mass_solar, sma_au, ecc}`), feeding `feasibility._binary_gate` → Holman–Wiegert S/P-type stability with
**no parallel code path**. It also produces `p_orb_days`, which B2's locked branch needs.

**Guard:** a synthetic multiplicity draw must **never** overwrite an observed GCNS multiplicity in
`--anchor-star` mode (`star["multiplicity"]` is GCNS-derived there).

### B2 — `age_dist` + `stellar_activity` sampler · **BUILT 2026-07-23** ✅

**Done.** `_check_age_dist` + `_draw_age` + `_draw_activity`, all in synthetic mode. The age is drawn from
the SFH histogram and **MS-lifetime-truncated** (no star older than its own main sequence, via the Phase-L3
`compute_stellar_evolution`); the activity chain runs age → P_rot → Ro → log(L_X/L_bol) → XUV with three
P_rot branches (locked / Skumanich FGK / bimodal M-dwarf).

**The dataset's own `unit_test_sun` reproduces exactly** — M=1 at 4.57 Gyr → P_rot 25.4 d, τ 13.8038 d
(dataset 13.8), Ro 1.8401 (1.84), log R_X −5.9939 (−5.99), inside the observed solar cycle band, no domain
flags. `expected_locked_vs_single_delta` is asserted as **emergent** (`is_prior_field: false`): the chain
produces an X-ray contrast of **288×**, inside the block's [10², 10³] band, and the XUV contrast is
**softer** (141×) with the saturated star **less** EUV-dominated than the quiet one — the block's
counter-intuitive headline claim, reproduced rather than assumed.

**Two structural validator guards**, each with a negative test: histogram bins must be **contiguous** (a gap
silently drops probability mass), and an interior **zero-fraction bin requires an `sfh_smoothing_note`** — so
the BGM discrete-age-bin artifact cannot arrive undocumented, and the sampler smooths only when the dataset
declares it intended.

**App-side simplification, named:** the block recommends drawing population then age from *that population's*
distribution but ships only the blended SFH. It sanctions the simplification for this consumer, so the
blended histogram is used and the omission is stated.

**Still open (small, and never blocked):** the **anchor-mode age path**. Observed ages exist on HWC (`S_AGE`)
and Mission Exocat (`st_age`); real anchors currently carry `age_gyr = null` rather than a synthetic draw,
which is correct but incomplete. Mirror the Hypatia→SIMBAD `fe_h` fallback pattern.

*Everything below is the original blocker record, kept for the reasoning — not because anything in it is
still open.*

---

**Blocker (i) — the missing stellar age — is answered on the data side.** The `age_dist` block APP
requested was **delivered 2026-07-23** as dataset **v2.10.0** (WB's T8; full method in
`../scifiWorldBuilding-Claude/research/star-and-planetary-system-generation/age-dist-prior-T8.md`).

It is the **mirror of `feh_dist`** — an APP-side synthetic-mode axis — but **not** a Gaussian. Shape:

- `method`: `population_weighted_sfh_histogram__mass_conditional__MS_truncated`; mean **4.97 Gyr**,
  median **4.04 Gyr**.
- `sfh_histogram`: 14 × 1-Gyr bins. **Bimodal-ish** — a young thin-disk component peaking ~2–5 Gyr plus an
  old component ~8–12 Gyr, declining to the present.
- `sfh_smoothing_note` — **read this before sampling.** The `7–8 Gyr` bin is `0.0` and `8–9` piles up; that
  is a **BGM discrete-age-bin artifact, not a real gap**. Smooth across ~7–10 Gyr; do not reproduce the
  zero literally.
- `mass_conditional`: `truncate_and_renormalize` — reject any draw with `age > ms_end_gyr(mass)`, then
  renormalize. APP already has `compute_stellar_evolution(mass_solar, current_age_gyr) → ms_end_gyr`
  (`core/equations.py`, Phase L3). The `mass_conditional_age` table (5 mass bins) already *encodes* the
  truncation — 1.0–1.5 M☉ mean 3.55 Gyr **<** 0–0.5 M☉ mean 5.48 Gyr, because massive stars die young.
- `population_mix_recommended_local`: thin **0.88** / thick **0.10** / halo **0.01** (the BGM near-plane
  0.826/0.154 reweighted to the local census). **Keep the split** — the thick disk *is* the old tail, so
  the mix sets the shape. For the `stellar_activity` chain *alone* a single blended distribution is
  adequate (thick/halo are old → unsaturated regardless).
- `amr`: `independent_of_feh_for_bulk` — draw age and [Fe/H] independently for 0–8 Gyr (flat mean
  −0.04…−0.09, ~0.16–0.20 dex fixed-age scatter, migration-blurred; Feuillet 2019). Independence
  **breaks** in the old tail (>8 Gyr: mean −0.29…−0.76), absorbed by drawing `feh_dist`
  population-conditioned.
- `verify_against_observation`: **`"satisfied"`** — the BGM `m1612` pull (`query.py besancon-query`, the
  Phase AM tool) was cross-checked against three independent observational anchors: **Alzate 2021**
  (Gaia SFH within 100 pc — the primary shape anchor), **Rowell 2013** (WDLF-inverted SFH), **Feuillet
  2019** (AMR). The tool's model-derived flag is **discharged**; this is no longer "a model output".
- `acceptance`: no star older than its own MS lifetime (structural, via the rejection); the Sun at 1 M☉ /
  4.57 Gyr is an **unremarkable** draw against the 0.8–1.0 M☉ bin (mean 5.04 / median 4.11). MSG-006 met
  **as a band, not a point**.

**All three constraints APP sent with the request were honoured and answered explicitly** —
mass-conditional (not marginal), the AMR interaction (independent for the bulk, *recorded* not assumed),
and population structure (keep it).

**What is left is entirely APP-side, and it is real work:**

1. `_check_age_dist` in `core/research_priors.py` + expose the block in `present_v2_blocks` /
   `ResearchPriors` (same pattern as `_check_stellar_multiplicity`). Until then the block is invisible.
2. **An age axis in `core/generate.py`** — the star dict has no age key in either mode. This is the actual
   structural gap; the data no longer is.
3. The sampler: draw population → age from that population's SFH → reject against `ms_end_gyr(mass)` →
   renormalize.
4. **Blocker (ii) — `p_orb_days` — clears with B1.** Build B1 first and the locked branch (`P_rot = P_orb`)
   becomes computable; the single-star branch needs only the age axis.

**Anchor path is APP's to wire and was never blocked:** observed ages exist on HWC (`S_AGE`) and Mission
Exocat (`st_age`); mirror the Hypatia→SIMBAD `fe_h` fallback pattern.

### B3 — the wide-companion outer bound · **DELIVERED (WB) + BUILT (APP) 2026-07-23** ✅

**Both halves done.** WB scope-locked and ran the fetch (`wide-separation-tail-brief.md`, claims C53–C57,
sources S70–S73, four sources body-opened), then ran a **cross-family adversarial refute-pass** on their own
brief which found 2 HIGH / 11 MEDIUM defects in it — four touching us. APP then built the result.

**What the fetch actually returned — it reshaped the plan, not just the numbers:**

| Asked | Answered |
|---|---|
| Functional form | **dN/ds ∝ s^−1.6**, *not* Öpik's −1. In log space dN/dlog s ∝ s^−0.6 — declining, not flat. |
| Outer cutoff | **There isn't one.** `a_max ≈ 1.212 × (M_tot/t)` pc — a *moving* boundary from cumulative encounters. **Provenance corrected 2026-07-23 (MSG 012 §5):** *theory with partial, indirect observational support*, **not** "observed, not just modelled" as first sent — the ~0.1 pc-break leg is dead, the disk-vs-halo shape leg ambiguous, only a frequency-vs-age leg survives. Law, coefficient and truncation unaffected. |
| Join normalization | **Declared UNKNOWN by the lineage** — "it remains unclear whether and how these two distributions are physically connected." |
| Mass dependence | **Flat is EXCLUDED for the FREQUENCY** — our stated fallback was the one option ruled out. ~1.1% mid-K–mid-M vs ~9–10% solar-type, an *upper* bound on the gap (MSG 012 §4 resolved Dhital's 1.1% as a **lower** limit, so the gap **shrinks**). **Retracted 2026-07-23:** the claim that the M tail declines *more steeply* — El-Badry 2019 fits M dwarfs **−1.62 ± 0.16** vs solar-type **−1.58 ± 0.09**, indistinguishable. Frequency depends on mass; the **index does not**. |
| Variable | Projected separation; **P(s) ≈ P(a)** for the tail (one conversion problem, not two) — but this does *not* extend to a centre. |

**The decision that follows, and it is a reversal:** *no tail component.* A mixture needs a join weight; the
join weight does not exist; inventing one is the same defect class as the F-2 double-count. So **one
log-normal, truncated at the disruption boundary** — which B2's age axis, landed hours earlier, made
implementable as the (M_tot, age) form rather than a ~0.1 pc constant.

**The half-life correction (MSG 014, the sixth and final B3 pass).** WB opened the primary and found the
quantity is not what either side thought: Weinberg's `t½` is the time by which **half** the pairs at a
separation are disrupted, and the paper reports *"no evidence of breaks or cutoffs."* The "widest binary
surviving at age t" gloss came from the secondary source and we inherited it verbatim. **No behaviour
change** (the affected mass is 0.1–3% of draws, and smooth attenuation would need a survival law nobody has
pinned — inventing one is the join-weight error again), but the field is renamed
**`wide_disruption_half_life_au`** and every label now says *modelling convenience*, not *boundary*. Two
source caveats came with it: eq. 28 is the paper's **naive** estimate (its own Monte Carlo gives
`t½ ∝ a₀^−1.34` in this range, but that fit has **no M_tot dependence**, so eq. 28 is the only
mass-dependent form available and the practical difference **changes sign with mass**), and eq. 28 is
**stars-only** while the paper finds stellar and GMC encounters *"cannot be understood individually."*

**Two things recorded rather than smoothed over** (both from WB's refute-pass):
1. ~~**~4% prefactor slack.**~~ **RETRACTED 2026-07-23** once the primary was opened (MSG 014): eq. 28
   reproduces the paper's own reference point, so Dhital's incoherent `Λ = 1` substitution is immaterial.
   `1.212` is **primary-verified** and no band is emitted. Kept in the record because the *reason* it was
   carried — a coefficient known only through a secondary source — is the pattern, not the number.
2. **Solar-host shape caveat, erring UNSAFE.** Local slope of this σ = 1.16 log-normal vs the measured
   −0.60: M centres are −0.64 at 500 AU and steepen (**under**-produce — safe, and 66.5% of companions);
   solar centres are −0.35 at 500 AU and stay shallower until ~3000 AU (**over**-produce — ~10.4% of
   companions). The one regime where one component is genuinely worse than a power law. Recorded because
   the alternative needs the join weight that does not exist, not because it is fine.

**`domain_overextension` was MIS-FRAMED, and that is the durable lesson.** Winters' σ = 1.16 is a
whole-range **untruncated** fit out to a 7500 AU horizon — it was never a below-500 AU quantity we were
over-extending. The flag records a **source-vs-source model disagreement** (D&K's two components vs
Winters' one), which the modern Gaia data do not settle in D&K's favour. We spent two rounds treating a
model disagreement as our own misuse.

*Everything below is the original blocker record, kept because it is what the fetch was scoped against —
not because anything in it is still open.*

---

At σ = 1.16, **~4.4%** of drawn wide companions land beyond ~500 AU, where canon §2 places an Öpik-like
distribution instead of the log-normal. Recorded as
`stellar_multiplicity.separation_dist.components[1].domain_overextension`, **flagged not clamped** —
because there is nothing to clamp *to*. D&K's "0.2–0.3 pc for early-M primaries" is a **lead, not a fit**.
Confirmed still unpinned on 2026-07-23 (canon §2, the coordination doc, and the change set all still say
"no Öpik normalization has been pinned").

**What clears it:** a pinned Öpik normalization + outer cutoff. Then upper-bound the wide component at
~500 AU with an Öpik tail beyond, matching canon's structure.

> **Correction to the original hand-off:** this **no longer "closes two items at once."** The σ question
> (§3) was settled independently by canon Bundle β, which *confirmed* the divergence as correct. The Öpik
> fetch now retires **this flag only** — still worth doing, but it is a single-item fetch, not a twofer.

### B4 — WB's own queue · **CLEARED 2026-07-23**

Every item on the original list is done, and more besides. The census addendum is **CLOSED**; all three
canon bundles are **Approved Canon**.

| Original item | Outcome |
|---|---|
| 1. **Huang et al. 2020 body** (the ~10× EB flare rate) | **T5** — upgraded to `[V-PRIMARY-abstract]` (S57). Body remains IOP-blocked → manual PDF drop only if a canon claim headlines the 10×. Domain pinned: **12 Algol-type M0–M3 EBs**, *not* the mid-late-M census. |
| 2. **§7.2 Winters-2020 parallax defect** | **T2** — done via Gaia DR3. LP 734-34 / G 258-17 / LP 655-43 all outside 15 pc (45.5 / 33.4 / 27.2 mas, `astrom_reliable_prob = 1.0`) → the *pre-Gaia* parallax was inflated. Became the worked example in canon Bundle **γ** (`detection-and-survey-limits.md`). Source note `S35-winters-2020-body.md` added. |
| 3. **ξ UMa Ba/Bb, δ Tri, 44 Boo B** `[LEAD]` | **T6** — **all 9** census `[LEAD]` periods cleared (7 via SB9, 2 via dedicated primaries: GJ 866 = Delfosse 1999 S64, CU Cnc = Ribas 2003 S65). The census carries no bare `[LEAD]`. Bonus: Castor Aa/Ab is eccentric (e = 0.5). |
| 4. **§9.8 ADS-native search** | **T1** — ADS + OpenAlex/Crossref routes provisioned (skill v0.1.50/51, both API keys live). The gap **HOLDS on a 4th pass** — characterized, not falsified: the twin-M circumbinary model is a legitimate re-instantiation. |
| 5. **§9.3 Path B** | **T7** — retired, not pinned (as predicted). |
| **N2 migration half** | **T4** — reservoir → Packet 4: `source-ledger.md` S33–S65, `claim-map.md` C40–C50. |
| **N3 / N5** | Both executed — `open-questions.md` (incl. the C52 circularization entry) and `glossary.md` updated. |

**Also landed, beyond the original list:**

- **Item A — census-expansion sweep.** Systematic Gaia-DR3-NSS + SB9 pull to **65 ly** found **50 new
  close binaries** (39 stellar / 10 BD / 1 WD), **tripling the count within 50 ly (15 → ~40)**. Packet 4
  S66 + C51, reservoir §11.
- **Canon Bundle α** — the close-binary radiation-habitability spine (C42–C50) promoted, with the max-seat
  reshaping the original C50 verdict.
- **Canon Bundle β** — census + demographics + the ⭐ separation-peak adjudication (see §3).
- **Canon Bundle γ** — the selection-bias worked example.

> **APP still cannot do B4-class work.** This session has only `WebFetch`/`WebSearch`, which the sister's
> `hard-sf-research` skill explicitly disqualifies for evidence capture (it returns a small-model summary,
> not the page's text, so it "NEVER counts as opening or inspecting a source"). Research goes through the
> sister repo's MCP servers. Hand it over; do not attempt it here.

### B5 — the close-pair rate vs the expanded census · **RULED CLOSED by WB 2026-07-23** ✅

**No change: 0.087 stands, "differently selected."** WB's containment test settled it — of the 50 new
systems in the 65 ly sweep, only three fall inside González-Payo's 10 pc sphere, and only one of those is
solid (Wolf 227 rests on a grade-37.9 targeted-search solution with a substellar companion *estimate*;
G 184-19 is the one clean case). Ceiling: **8 → 9 of 92 = 9.8%**, inside the 8.7% ± 3.1% Poisson band.
APP's confirmatory run in their exact cell returned **4 distinct systems ≤ 8**, and — the detail that
settles it from the inside — **GJ 867 BD at 1.795 d, the shortest-period system in the volume, is not
recovered by NSS+SB9 at all**, so the sweep is demonstrably a floor rather than a census.

The original framing is kept below because the *reasoning* is what transfers, not the verdict.

---

`separation_dist.components[0].close_pair.weight` is still **0.087** — the González-Payo 2026 figure
(8 short-period SBs among 92 multiples **within 10 pc**). WB's item-A sweep has since **tripled the known
close-binary count within 50 ly**, so the obvious question is whether that rate moves.

**Do not just recompute it here.** The two samples have different selection functions (a 10 pc
volume-complete multiplicity census vs. a Gaia-NSS/SB9 detection sweep to 65 ly), so the new count is
**not** a drop-in numerator. This is a question **for WB**: *does S66/C51 revise the 8/92 close-pair
fraction, or is it a differently-selected sample that leaves the rate as-is?*

Scale note before spending anything on it: the realized close-pair rate is **0.087 by construction** (the
F-2 truncation pins it), so this changes an *input we can already state*, not an emergent property — and
the same note records that canon's own solar-type parameters independently predict 6.4–6.6% for this
window, statistically indistinguishable from 8.7% ± 3.1%. **Low priority; recorded so it isn't rediscovered.**

## 3. Standing divergence — now canon-*confirmed*, still do not "fix"

`separation_dist.wide_lognormal.log10_sigma_au = 1.16` (Winters 2019) **differs from canon §2's
σ_logP ≈ 1.3 = σ_log10(a) 0.867** (Duchêne & Kraus 2013). Recorded in `sigma_diverges_from_canon` and
**intentional**:

- Canon kept D&K for **corpus hygiene** — smallest blast radius for what was a transcription fix.
  Explicitly **not** because the number is better.
- The two σ's are **not competing estimates of one quantity**: D&K's is fitted under a <500 AU truncation,
  Winters' on an untruncated sample. Each is domain-matched to a different consumer.
- **Scale:** σ has **no effect** on the realized close-pair rate (F-2 pins it at 0.087 by construction).
  It moves canon §6's fully-suppressed <1 AU bin by ~6 pp.

> **New 2026-07-23 — this is now canon-backed, not merely recorded.** Bundle β's
> `decision-attacker-max` seat **independently re-derived the truncated-vs-untruncated domain argument and
> validated it**: canon keeps σ_logP 1.3 for its <500 AU-truncated log-normal, the dataset keeps 1.16 for
> its untruncated wide component. **The correct domain-matched state, not a defect.** A future session
> "harmonising" them would be undoing a decision that has now survived an adversarial canon review.

**The separation *centre* question is also RESOLVED** (`center_au_status`, rewritten in v2.9.0). Bundle β
reconciled canon §2's M-dwarf centre to a **few AU (~4–5)**: D&K's period-derived **5.3 AU** and Winters'
nearby-10 pc **4 AU** *agree*, while Winters' 25 pc **20 AU** peak is a **survey-coverage artifact** (his
own 10 pc subsample drops to 4 AU). `center_au` stays **5.3** as the D&K anchor at the upper end of that
range. The earlier "open, pending a D1 pass" framing is **superseded** — a shift toward ~4–5 would be a
second-order refinement with no effect on the by-construction close-pair rate.

## 4. Invariants a future session must not break

**Three structural guards** are hard-enforced by the validators, each with a negative test asserting it
fails when subverted. They are not style; each encodes a defect that actually occurred:

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
reintroduces the cross-fit that F-0 removed. The same warning is in the sister's N4 table.

**The circularization boundary is 6 d, not 12 d** (v2.9.0). Any APP text, test, or comment still quoting
**12 d as the M-dwarf boundary is stale** — 12 d is now only the *solar-type* reference. The validator
enforces the field's *presence* when the block is RESEARCH-GRADE, not its value, so a stale number will not
fail a test; it will just be wrong. See §1a.

**`giant_switch` is not relaxed.** Inner giants bypass it as a controlled, tagged sub-population; the gate
itself is unchanged, and a regression test asserts any giant interior to the snow line carries `giant_zone`.

**The `[2,3]` acceptance band is X-ray contrast, not XUV**, and is *instantaneous, matched-age* — it must
not be fed to cumulative-fluence arguments (doing so implied a ~67–550 M⊕ "rocky" world).

## 5. Recommended order

1. **Re-ingest** whenever the dataset moves (§0 — the cache was silently a full major version behind).
2. ~~**Build the B1 multiplicity sampler.**~~ **DONE 2026-07-23** — including the §1a prose fix.
   It now produces the `p_orb_days` that B2's locked branch consumes.
3. ~~**Wire `age_dist` (B2)**~~ — **DONE 2026-07-23**: validator + generator age axis + sampler, and the
   `stellar_activity` chain with it (both branches computable).
4. ~~**Hand B3's Öpik fetch to the sister session**~~ — **sent 2026-07-23** (channel MSG 001/003);
   WB is scope-locking the fetch. **B5 is RULED CLOSED by WB** (MSG 002/004/006): no change, 0.087 stands,
   "differently selected" — the ceiling was 8 → 9 of 92, inside the 8.7% ± 3.1% band. See §B5.
5. ~~**Deferred, tracked separately:**~~ **DONE 2026-07-23** — the `close-binary-census` dedup rebuild
   (intra-source multi-solution + identity-first cross-route; 62 rows → 54 systems on WB's cell). It was
   never blocked and never urgent — WB confirmed their C51 count came from an
   independent identity-first pull and was never affected. Regression cases: FK Aqr (SB2C 4.083196151 d
   gr 205 vs OrbitalTargetedSearch 7.980586 d gr 43) and BY Dra (SB2 5.9773 d gr 141 vs
   OrbitalTargetedSearch 32.2660 d gr 17). **Counter-instance that must survive untouched:** G 184-19, a
   *single* SB2 solution at grade 125.86 with e = 0.685 at 2.535 d — the signal is `solution_type` plus
   whether a competing row exists on the same source, never period or grade alone.

## 6. The pattern this round found four times — worth checking for deliberately

Four separate defects shared one shape: **something complete from one side, missing its other half.**
Canon carried a distribution centre without its width. `ecc` was emitted with nothing defining it.
`L_X` was labelled XUV with no conversion applied. `stellar_activity` named an input (age) that nothing
produces.

The cheap mechanical check that would have caught all four: **for every input a block names, ask which
block or code path produces it — and for every figure, ask whether its companion parameters came with it.**

> **2026-07-23 addendum — the check paid out twice more.** `stellar_activity`'s missing age is now
> supplied (`age_dist`, B2) and `ecc_dist`'s undefined eccentricity is now pinned (B1) — both because the
> gap had been *written down as a named missing input* rather than quietly defaulted. Worth noting which
> half of that is the durable habit: naming the producer, not finding the number.

## 7. What actually remains (none of it a B item, none of it blocking)

> **⚠ RENUMBERED — the live copy of this section is elsewhere.** 7a and 7b moved to
> **`docs/research-priors-v2-remaining.md`**, where they are **that file's §1a and §1b** — *not* to be
> confused with **this** file's §1a, which is the unrelated stale-prose record. **7c is closed**
> (2026-07-23, when WB opened the Weinberg primary) and was not carried over. What follows is the frozen record. **Do not work
> from it** — the new file is the one that gets updated.

Everything in the original hand-off is built. These three were discovered *during* the build and are
recorded so they are not rediscovered from scratch. Sized and scoped 2026-07-23.

> ### ⚠ READ FIRST — WB's in-flight work LANDED (MSG 012, 2026-07-23). Here is what it changed.
>
> When §7 was first written the sister project had work in progress that could have changed something
> already built. **It landed the same day** as a consolidated B3 correction — five successive
> pre-promotion audit passes, five defects, one of them a **retraction** of something we had been sent.
>
> **Nothing built here changed behaviour.** The disruption law, the `1.212` coefficient and the truncation
> are untouched, and the retraction (a *single* power law is excluded; Tian 2020 favour **two** breaks)
> does not reach us **precisely because we draw a log-normal truncated at `a_max` and never evaluate an
> index**. The MSG 008 decision to refuse an invented join weight paid off twice: it also kept us clear of
> a shape claim that has since been withdrawn.
>
> **Four pieces of text were wrong and are now corrected** (provenance only, no code behaviour):
> the "observed, not merely modelled" provenance in `core/generate.py` and in B3's table → *theory with
> partial, indirect observational support*; the "M tail declines more steeply" claim → **retracted**, the
> index is mass-independent; and §7c's "shallow bound" ask → **closed**, with a new two-break condition in
> its place. We never claimed "six independent studies", so MSG 012 §2 cost us nothing.
>
> **The standing hazard is unchanged and still worth reading before trusting this build.** A contract break
> fails the suite; a **value** change (a coefficient, a boundary, a distribution shape) passes silently and
> just makes the output wrong. If the dataset version moved past `pkt3.5-v2.10.0-2026-07-23`,
> **re-ingest first** (§0 — the cache is silent about being stale) and re-run the verification chain. Most
> exposed, in order: **B1's `ecc_dist` ~6 d boundary** (already revised once, 12 d → 6 d);
> **B2's `age_dist` histogram** (newest block, landed the same day). **B3's `1.212` is no longer on this
> list** — MSG 014 opened Weinberg 1987, discharging WB's C55 gate: the coefficient is primary-verified and
> the ~4% slack is retracted (§7c). What that pass *did* change was the meaning: `t½` is a **half-life**,
> not a boundary, and every label now says so.
>
> **The methodological finding, which is the durable part.** All five defects came from opening a paper a
> secondary source had characterised — reviews and abstracts were wrong or flattened **five times out of
> five**. WB's formulation: ***a characterisation is a lead, not a measurement.*** That is the same shape
> as this session's census-dedup finding, where a catalogue's own `solution_type` and grade turned out to
> be the signal and the derived period was the thing that misled.

### 7a. The anchor-mode age path is unwired · APP-only, **no WB input** · small

`age_dist` is a **synthetic-mode** axis. A real anchor carries `age_gyr = null`, which is correct (an
observed star's age must not come from a synthetic SFH) but incomplete: observed ages exist on **HWC
`S_AGE`** and **Mission Exocat `st_age`**.

**Smaller than it looks:** `_generate_real_anchor` **already calls `compute_hwc(simbad)`** for planet rows
and discards the returned `star_row` — which is where `S_AGE` lives. The HWC half is therefore reading a
field *already fetched*, at **zero extra network cost**. Mission Exocat as a second fallback is one new
call (`compute_mission_exocat` is not currently imported there).

Shape: a `_resolve_anchor_age` mirroring the existing `_resolve_anchor_feh` (HWC → Exocat, with
`age_source` tagged), then let `_draw_activity` run for anchors — it currently cannot, which is the last
thing keeping the activity chain off real stars.

**Two things to settle first, both ours:**
1. **Units.** Confirm `S_AGE` / `st_age` are Gyr *before* anything consumes them. An unchecked unit here
   produces silently wrong activity, not an error.
2. **Tagging.** For an M-dwarf anchor the chain **draws** P_rot from the bimodal population — a synthetic
   act on an observed star. It needs an explicit source tag so a modelled `p_rot_days` can never be read
   as an observed one. Same discipline as `feh_source` / `age_source`.

### 7b. Decoupled inner giants vs the grid's spacing floor · **a decision + a narrow WB ask**

B1's rng shift exposed a latent ordering bug (fixed — synthetic planets now emit in orbital order, as the
real-anchor path always did). Underneath it sits a real question that was **deliberately not answered**:
the v2.3 decoupled inner-giant population is placed independently of the `n_planet_dist` grid, so an inner
giant can land closer to a grid planet than the peas-in-a-pod spacing floor allows. The spacing-floor test
was scoped to the grid rather than silently deciding this.

**Do not frame this as "should we enforce mutual Hill."** That was the first framing and it is the weaker
one: mutual Hill (Gladman 2√3 / Chambers Δ≥10, already in `core/feasibility.py` G1) is a **stability
floor** — it says what cannot survive, not what actually occurs.

**The question is empirical:** *do close-in giants coexist with inner small planets, and at what spacing?*
There is a literature on exactly this, and it reportedly **splits hot vs warm** — hot Jupiters notably
"lonely", warm Jupiters more often accompanied. **That split maps onto a tag `inner_giant_population`
already carries (`giant_zone: hot|warm`)**, so if the answer splits that way the implementation is nearly
free.

**Status of that recollection: UNVERIFIED.** The association (Huang / Wu / Triaud) is memory, not a pin —
recorded as a lead for WB to check, never to be implemented from as-is. **The ask for WB is narrow:** does
the observed population support inner small planets coexisting with a *warm* giant, and does it differ for
*hot* giants? **Not yet sent** — deliberately held while WB's in-flight work lands (see the box above).

### 7c. Two external dependencies our code rested on · **BOTH CLOSED 2026-07-23** ✅ (kept as the record)

- ~~**The B3 coefficient gate.**~~ **DISCHARGED 2026-07-23 (MSG 014).** WB opened Weinberg 1987 (via an
  ADS OCR scan — OpenAlex reports `best_oa_location: null` for pre-1995 ApJ, a **false negative** worth
  remembering). Eq. 28 reproduces the paper's own reference point, the `Λ = 1` incoherence is immaterial,
  and the **~4% slack is RETRACTED** — `1.212` is primary-verified and no uncertainty band is emitted.
  **But the gate fired on something else** (see the B3 section): `t½` is a **half-life**, not a boundary,
  and the paper's headline is *"no evidence of breaks or cutoffs."* Our hard truncation is now labelled a
  modelling convenience everywhere it appears.
- ~~**The M-dwarf tail index is explicitly NOT requested.**~~ **CLOSED 2026-07-23 (MSG 012 §4) — and WB's
  own "shallow bound" warning to us was wrong.** El-Badry 2019 fits γ_s across 35 bins of primary mass ×
  separation including 0.1–0.4 M☉: M dwarfs **−1.62 ± 0.16** vs solar-type **−1.58 ± 0.09**,
  indistinguishable (*"any trends with primary mass at fixed separation are weak"*). **−1.6 applies to M
  primaries too**; nothing further is wanted from WB on this.
  **But a NEW condition now travels with any reversal to a tail** (MSG 012 §1, which *retracts* what we
  were sent): a **single** power law is excluded — Tian 2020 favour **two** breaks (~10^3.8 AU and
  ~10^4.5 AU), and ER18's single-slope −1.6 is a **domain result** valid for a disk-dominated sample over
  **500–50,000 AU**. So a reversal needs a two-break tail, not the one-component tail we declined.

### Also recorded, needing no action

`age_dist`'s **population split is not separately sampled** — the block recommends drawing thin/thick/halo
then age from that population's distribution, but ships only the blended SFH, and per-population age
distributions are not in the dataset. The block explicitly sanctions the simplification for this consumer
("for the `stellar_activity` chain ALONE a single blended distribution is adequate"). If WB ever supplies
per-population SFHs, this becomes a straightforward refinement.
