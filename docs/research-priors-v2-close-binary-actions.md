---
type: as-built-reply
status: Draft
packet: "3.5"
from: SpaceAndScienceFictionApp (generator / sister project)
to: scifiWorldBuilding-Claude Packet 3.5
created: 2026-07-22
related:
  - design-lab/close-binary-census-integration-change-set.md
  - research/nearby-close-binary-census-source-leads.md
  - research/query-api-methods/research-priors-v2-inner-giant-handoff.md
  - design-lab/star-system-generation-priors/research_priors_v2.json
  - docs/research-priors-contract.md
  - docs/research-priors-v2-b6-actions.md
---

# Close-binary round — `inner_giant_population` sampler + the two stellar blocks (v2.3.0 → v2.8.0)

**Status: Draft. APP-side durable record of the 2026-07-22 coordination round.**

> **Why this file exists.** The round ran over a live channel at `/home/greg/claude/coordination-channel.md`,
> which is **ephemeral by design** — the protocol at its head requires durable conclusions to be mirrored out
> before it is deleted (WB side → `sister-project-coordination.md`; APP side → here). Without this file, the
> only APP-side record of *why* the guards, divergences and held decisions below exist would be a scratch file
> intended for deletion, leaving the code without its reasons. That is the exact failure this round kept
> finding in other places, so it is worth not reproducing here.
>
> **Open work from this round is tracked separately in [`docs/research-priors-v2-open-work.md`](research-priors-v2-open-work.md)** — that is the hand-off plan; this file is the record of what happened and why.

Dataset moved **`pkt3.5-v2.3.0` → `v2.8.0`** across the round. No pinned coefficient was changed by APP; one
was *corrected* by WB (F-0) and one figure was *retracted* by WB (the solar anchor).

## 1. Built this round (APP code)

### `inner_giant_population` — validator + 7-step placement sampler (v2.3.0 hand-off)
- `_check_inner_giant_population` in `core/research_priors.py`, plus the document-level cross-block
  invariant (`occurrence_ref` points into `occurrence_by_metallicity`, so that block is a hard dependency).
- `_place_inner_giants` in `core/generate.py`, run after `_place_cold_giants`, sharing the host `[Fe/H]`.
  Own occurrence roll against the **literal FV05 `giant_fraction`** interpolated with **endpoints held**
  (`_interp_giant_fraction`) — deliberately a different number from `_occ_eff`'s rescaled cold curve, over a
  disjoint SMA zone, so the two rolls cannot double-count.
- Realized: ~4.5% of systems carry an inner giant (the curve is exactly 3.0% at solar; the sweep mean sits
  above it because `giant_fraction` is steeply convex and `feh_dist` spreads across it — expected).
- **`giant_switch` is untouched.** A regression test asserts any giant interior to the snow line is a *tagged*
  member of this population, never grid-grown.

**Two calibration defects found and fixed, both worth remembering:**
1. **The gap-anchored giant mass draw collapses close in.** Reusing the cold block's `_draw_giant_mass`
   (anchored on the F4 gap-opening mass) put every inner giant below the 0.3 M_J floor where the clamp pinned
   it — a delta function at the floor. The cause is physical: the Type-II knee scales with `a` and disk
   temperature, so it is genuinely tiny at 0.02–0.5 AU. Mass is now **log-uniform** across the block's range,
   since the block supplies a range and no shape.
2. **The e↔channel rule must not apply in the hot zone.** Applying it there handed ~100% of hot Jupiters to
   the 20% `in_situ` channel, inverting the block's 80/20 split — because `migrated_disk_or_high_e` merely has
   `high_e` in its *name*, while tidal circularization puts *both* hot channels at e ≈ 0. Hot now draws over
   the full mix; the e-gated group selection is warm-zone only.

**Ruling carried (WB):** keep the **e-first** draw order — "a generator should get its observables right and
let the unobservable labels fall out." Consequence made explicit rather than left implicit:
`formation_channel_mix` is marked `is_prior_field: false`, because Beta(1.00, 2.79) puts ~74% above e = 0.1
so the realized warm split is ~74/26 against the stated 55/45. If that gap is uncomfortable, the honest lever
is the **Beta parameters, not the draw order**.

### `stellar_multiplicity` + `stellar_activity` — validators (v2.4.0–v2.8.0)
Shape validators only; **no samplers** (see §4). Beyond shape, they **hard-enforce three structural guards**,
each with a negative test asserting the guard fails when subverted:

| Guard | Why |
|---|---|
| `ecc_dist.consumer_must_not_default_to_zero` is **true** | A silent `e = 0` makes every drawn binary maximally planet-friendly and inflates stable-HZ rates. Eccentricity, not separation, is the habitability killer for close pairs (GJ 570 BC has no stable circumbinary HZ at e = 0.765 despite an unremarkable 0.79 AU separation). |
| `circumbinary_xuv.component_count_scaling` is **1.0** | The §9.4 geometric result: doubled emitters cancel exactly against doubled HZ distance, so XUV at a circumbinary HZ depends on `L_X/L_bol` only. A ratio identity — it holds in any band. |
| `expected_locked_vs_single_delta.is_prior_field` is **false** | It is what the Rossby chain *produces*. Marking it an input double-counts the delta against the computation that generates it. |

Two further tests exist to stop the validator being **over**-strict: `log_lx_lbol_valid_range` is legitimately
**descending** (`−4 > log R_X > −6.3`), and Wright 2018's τ table runs **hot-to-cool** so its mass grid
descends. A naive ascending-order check rejects both, and a future tidy-up "fixing" them into ascending order
would be a regression.

## 2. Findings absorbed from WB's review (F-0 … F-5)

| # | Finding | Resolution |
|---|---|---|
| **F-0** | The Wright constants were **cross-fitted**: `Ro_sat = 0.13` belongs to β = −2, not β = −2.70. | Self-consistent triple **(β = −2.70, Ro_sat = 0.16, log sat = −3.13)**; τ table was fitted *assuming* it, so the three travel together. Path A's central value moved 320× → **180×**. |
| **F-1** | `ecc` was emitted with nothing defining it. | Explicit `ecc_dist`; UNPINNED at first, then RESEARCH-GRADE once Raghavan landed. |
| **F-2** | **APP's bug.** The close-pair branch sat *on top of* an untruncated log-normal that already produced short-period pairs — realizing **2.37× the target rate for M dwarfs** (77% of draws). | Wide component truncated below 62.6 d and renormalized so the two are disjoint. APP's stated rationale was also wrong: canon's own parameters give 6.4–6.6% against the observed 8.7% ± 3.1% — **statistically indistinguishable**, so §3 is a *consistency check canon passes*, not information the log-normal lacks. |
| **F-3** | Newton 2016 spin-down is an M-dwarf result applied to G/K — out of domain by 15–100×, inflating the G-host delta to ~4900×. | Scoped to M; separate Skumanich FGK branch anchored on the Sun. |
| **F-4** | Multiplicity interpolated linearly in mass. | Linear in **log₁₀ M**. |
| **F-5** | The M-dwarf σ was borrowed from solar types; at σ = 1.53 the mean/median gap is **496×**, not an approximation. | σ → **1.16** (Winters 2019, body-verified). Root cause turned out to be canon's — see §3. |

**F-2 is the one to remember.** It is structurally the same double-count APP had twice warned WB about, in
writing, for giant occurrence — and APP did not catch it in its own block. It was also missed a second time
when APP reconstructed the findings from the reservoir's §10 before the channel message body had landed, and
presented a partial list as the list. **An artifact left by a process is not the process's report.**

## 3. Corrections that moved published numbers

- **C-4 — instantaneous vs cumulative.** The §9.3 10²–10³ is an *instantaneous, matched-age* ratio. Feeding it
  to the cosmic-shoreline (escape) chain implied a **~67–550 M⊕ "rocky" world** — an unphysical claim that
  would otherwise have reached canon via D3. Integrated, the ratio is only ~3–10×. The clean split: the
  **ozone/SEP** argument runs on the instantaneous ratio and holds; the **escape/shoreline** argument runs on
  integrated fluence and is far weaker.
- **The Sun unit test.** v2.5.0 recorded it as *failing* against an "observed −6.5 to −7.0" that WB then
  **retracted as memory-grade** — and which sat *below the relation's own −6.3 validity floor*, i.e. the fit
  was being asked to reproduce values outside its fitted range. The Sun is a **1.24 dex band** (Peres 2000,
  **abstract-grade**: log R_X −7.15 to −5.91); this chain's −5.99 is inside it, and over-predicting the Sun is
  a **self-reported property** of the β = −2.70 fit (Wright 2011: 0.2 dex, ~0.3 dex rms). The test now asserts
  four band/domain/scatter/direction conditions and passes all four.
  **The constants were never tuned to close the apparent gap** — bending a body-verified fitted set to hit one
  star is how a cross-fit gets reintroduced, which is what F-0 had just removed. The gap resolved in the
  sources' favour instead.
- **X-ray ≠ XUV.** `circumbinary_xuv` was labelled XUV and derived on an X-ray quantity with no conversion.
  The physics runs opposite to intuition — **α Cen B is 91% EUV, AB Dor 23%** — so quiet stars are
  EUV-dominated and saturated stars X-ray-dominated, which bites here because a locked pair is saturated for
  life while its comparator spins down. Converting properly softens the contrast: **182× (L_X) → 93×
  (Sanz-Forcada 2011) or 38× (Johnstone 2021)**. The relations **disagree and are not averaged** — the spread
  is the uncertainty. The §9.4 geometry is unaffected (ratio identity), only the band label was wrong.
- **The pattern.** Three independent corrections all moved the headline the same way: 320× → 180× → ~3–10×
  cumulative → 38–93× in XUV. §9.3's "10²–10³, two orders as the conservative floor" now sits **at or below
  its own floor**. No new headline is proposed here — that needs a packet, not a channel round — but
  **D1/D3 must not quote 10²–10³ without §10's corrections attached**, and the acceptance band is relabelled
  explicitly **X-ray contrast**.

## 4. Deliberately not done

- **The `stellar_multiplicity` sampler.** `ecc_dist` is drawable, but the 12 d circularization boundary was
  measured on *solar-type* primaries (Raghavan 2010, abstract-grade) and the census is ~77% M dwarfs — with
  **BY Dra (K4Ve+K7.5Ve, e = 0.300 at P = 5.98 d)** already showing the boundary is soft for K dwarfs. Burying
  that extrapolation inside a sampler is how it stops being visible. **No M-dwarf circularization period
  exists anywhere in the corpus.** Waits for one, or for an explicit recorded decision to extrapolate
  knowingly.
- **An Öpik tail on the wide component.** The proper fix for the >500 AU over-extension (§5), but nothing is
  pinned to build it from — D&K's "0.2–0.3 pc for early-M primaries" is a lead, not a fit. Inventing a
  component to settle a second-order question would be the same error pointing the other way.

## 5. The σ divergence from canon — recorded, not incidental

Canon §2 (corrected by the D1 pass, 2026-07-22) carries **σ_logP ≈ 1.3 = σ_log10(a) 0.867**; this dataset
keeps **1.16**.

- **Why canon kept D&K 2013:** corpus hygiene — a canon *correction* should have the smallest blast radius
  that fixes the defect, and the defect traced entirely to one already-cited source. Importing Winters
  mid-correction would have expanded the pin surface and bundled a *substantive* question into a
  *transcription* fix. **Explicitly not** "the authors expect the number to move" — that reason *would* have
  transferred.
- **Why it does not bind the dataset:** the two σ's are **not competing estimates of one quantity**. D&K's is
  fitted *under* a <500 AU truncation; Winters' on an untruncated sample. Canon states a truncated log-normal,
  so the truncated σ is domain-matched *there*; this component has no upper truncation, so the untruncated fit
  is domain-matched *here*.
- **Scale:** σ has **no effect on the realized close-pair rate** (the F-2 truncation pins it at 0.087 by
  construction), so the 5.86%/10.40% in-window pair is an *untruncated diagnostic*, not an output. It bites
  canon §6's fully-suppressed <1 AU bin at ~6 pp. Second-order, with no observable in play to arbitrate it.
- **Live edge:** at 1.16, **~4.4%** of drawn wide companions land beyond 500 AU where canon places an
  Öpik-like distribution. **Flagged, not clamped** (`domain_overextension`).

**A reasoning error worth recording:** APP first argued the >500 AU domain point *against* keeping 1.16, then
had to concede it argues *for* it — the domain that matters is this component's, not canon's. Same fact,
opposite conclusion, wrong consumer matched against. This is the second instance of that shape in one round
(C-4 was the first: the same ratio right for ozone, wrong for escape). **A consideration is only "for" or
"against" relative to a domain, and naming the domain is what settles it.**

## 6. Canon defect surfaced (WB's D1 pass — APP did not touch canon)

Canon §2 took Duchêne & Kraus 2013's **centre** and **dropped the width**, while keeping the *solar-type*
width two clauses earlier — a **half-specified distribution**. The correct σ had been quote-pinned in Packet
4's `claim-map.md` **C4 the whole time**, one layer below canon, never promoted. The peak/mean mislabel APP
originally flagged was the smaller half of the defect. Promoted by WB with the user's scope-lock; APP's role
was to flag and to keep `center_au` unchanged so the priors did not pre-empt the ruling.

## 7. Verify

```
V2=../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
venv/bin/python -c "import json,sys; sys.path.insert(0,'.'); \
  from core.research_priors import validate_priors_contract, present_v2_blocks; \
  d=json.load(open('$V2')); print(validate_priors_contract(d) or 'VALID'); print(present_v2_blocks(d))"
# → VALID; all 8 blocks listed
venv/bin/python query.py generate-system --seed 3 --research-policy strict   # stamps pkt3.5-v2.8.0
QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests      # 1960 pass, 1 skipped
```
