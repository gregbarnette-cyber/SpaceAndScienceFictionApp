---
type: plan
status: Open
packet: "3.5"
created: 2026-07-23
supersedes: docs/research-priors-v2-open-work.md (now closed — the round record)
related:
  - docs/research-priors-v2-open-work.md
  - docs/research-priors-contract.md
  - core/generate.py
  - ../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
---

# Research-priors v2 — what remains

The v2 build is **finished**: all nine blocks of `pkt3.5-v2.10.0-2026-07-23` validate, are exposed, and are
sampled, and the `close-binary-census` dedup rebuild that ran alongside it is done. Suite **2073 pass,
1 skipped**.

This file is only the live work. **`docs/research-priors-v2-open-work.md` is closed** and kept as the round
record — go there for *why* decisions were made (why no power-law tail, why the σ divergence stands, why the
close-pair rate was not recomputed). That reasoning stopped three separately-retracted claims from reaching
our code, so it is worth reading before reopening anything.

> **Section-number mapping — these items were renumbered when they moved here.** Session transcripts, commit
> messages and the closed plan's own §7 all refer to them by their *old* numbers, and both numbering schemes
> are live (the closed file keeps its §7 intact, so nothing dangles — but the same item has two names).
>
> | Closed plan | This file | |
> |---|---|---|
> | §7a — anchor-mode age path | **§1a** | open |
> | §7b — inner giants vs the spacing floor | **§1b** | open |
> | §7c — external dependencies (C55 gate, M-dwarf index) | — | **closed 2026-07-23; not carried over** |
>
> They lead here because they are the first thing in a document about what is left, rather than a footnote
> at the end of a finished one. Content is unchanged apart from dropping the "none of it was ever a B item"
> framing, which only made sense beside the B items.

---

## 1. Two actionable items

### 1a. Wire the anchor-mode age path · APP-only, no external input · small

`age_dist` is a **synthetic-mode** axis. A real anchor carries `age_gyr = null` — correct (an observed
star's age must not come from a synthetic SFH) but incomplete. Observed ages exist on **HWC `S_AGE`** and
**Mission Exocat `st_age`**.

**Smaller than it looks:** `_generate_real_anchor` **already calls `compute_hwc(simbad)`** for planet rows
and discards the returned `star_row`, which is where `S_AGE` lives — so the HWC half is reading a field
*already fetched*, at zero extra network cost. Mission Exocat as a second fallback is one new call
(`compute_mission_exocat` is not imported there today).

Shape: a `_resolve_anchor_age` mirroring `_resolve_anchor_feh` (HWC → Exocat, `age_source` tagged), then
let `_draw_activity` run for anchors — it cannot today, which is the last thing keeping the activity chain
off real stars.

**Two things to settle first, both ours:**
1. **Units.** Confirm `S_AGE` / `st_age` are Gyr *before* anything consumes them. A wrong unit here
   produces silently wrong activity, not an error.
2. **Tagging.** For an M-dwarf anchor the chain **draws** P_rot from the bimodal population — a synthetic
   act on an observed star. It needs its own source tag so a modelled `p_rot_days` can never be read as
   observed. Same discipline as `feh_source` / `age_source`.

### 1b. Decide: do decoupled inner giants respect the grid's spacing floor? · a decision + a narrow ask

The v2.3 inner-giant population is placed independently of the `n_planet_dist` grid, so an inner giant can
land closer to a grid planet than the peas-in-a-pod spacing floor allows. The spacing-floor test is scoped
to the grid rather than silently deciding this. (The related *ordering* bug — decoupled populations
appended without re-sorting — was found and fixed during B1; this is the question underneath it.)

**Do not frame this as "should we enforce mutual Hill."** That is the weaker framing: mutual Hill
(Gladman 2√3 / Chambers Δ≥10, already in `core/feasibility.py` G1) is a **stability floor** — it says what
cannot survive, not what actually occurs.

**The question is empirical:** *do close-in giants coexist with inner small planets, and at what spacing?*
There is a literature on this and it reportedly **splits hot vs warm** — hot Jupiters notably "lonely",
warm Jupiters more often accompanied. **That split maps onto a tag `inner_giant_population` already
carries (`giant_zone: hot|warm`)**, so if the answer splits that way the implementation is nearly free.

> **Status of that recollection: UNVERIFIED.** The association (Huang / Wu / Triaud) is memory, not a pin.
> It is a **lead for the sister project to check**, never something to implement from as-is. The ask is
> narrow: does the observed population support inner small planets coexisting with a *warm* giant, and does
> it differ for *hot* giants? **Not yet sent.**

---

## 2. Four dormant refinements — none is a task until its precondition lands

Each is currently blocked on the sister project pinning one specific thing. **The precondition is the
point**: implementing any of these *without* it would repeat the invented-join-weight error the whole v2
round was spent avoiding.

| If a … is pinned | Then | Where it bites today |
|---|---|---|
| **f(e) shape** for `ecc_dist` | replace B1's app-side Rayleigh(σ = 0.21) above the boundary / half-normal(σ = 0.01) below | `_draw_companion_ecc`; the emitted note names these as ours |
| **survival decay law** for wide pairs | replace B3's hard truncation with smooth attenuation | `_draw_multiplicity`; `a_half` is a **half-life** — ~half the pairs there really survive, and the source finds no cutoffs, so the cut is a labelled convenience |
| **join normalization** between log-normal and tail | a two-break power-law tail becomes buildable — and would fix the solar-host over-production | B3's recorded solar-host caveat (log-normal runs shallower than the measured −0.60 out to ~3000 AU) |
| **per-population SFHs** (thin/thick/halo) | `age_dist` draws population → age from *that* population's distribution | today the **blended** histogram is used; the block explicitly sanctions this for the activity chain alone |

Two constraints travel with the third row and were established late, so they are easy to lose: a **single**
power law is excluded (Tian 2020 favour **two** breaks, ~10^3.8 and ~10^4.5 AU), and the index is **not**
mass-dependent (M dwarfs −1.62 ± 0.16 vs solar-type −1.58 ± 0.09). The **frequency** mass-dependence is a
different quantity and still stands — never apply *that* flat.

---

## 3. Before trusting this build — the two hazards

**Re-ingest whenever the sister dataset moves.** `data/research_priors/` is gitignored and **silent about
being stale**: it sat on `pkt3.5-v1.0.2-2026-07-09` — a *v1* file — until 2026-07-23, so every
strict-policy run in between used v1 axes. Check `meta.json`'s `dataset_version` before trusting any
strict-policy output.

**A contract break fails the suite; a value change does not.** A revised coefficient, boundary or
distribution shape passes every test and just makes the output quietly wrong. Value revisions are exactly
what the sister shipped repeatedly during the v2 round (`ecc_dist` alone went 12 d → 6 d mid-round). Most
exposed: **`ecc_dist`'s ~6 d boundary** and **`age_dist`'s histogram** (the newest block). B3's `1.212` is
no longer on that list — the primary was opened and it is verified.

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

---

## 4. Invariants — do not restate them here

The standing constraints on this code (three validator-enforced structural guards with negative tests; two
shapes that look wrong and are correct; the three-constants-are-one-fitted-package warning; the σ divergence
marked *do not "fix"*) live in **`docs/research-priors-v2-open-work.md` §3–§4**.

**They are deliberately not copied into this file.** Invariants duplicated across two documents drift, and
the v2 round produced three separate instances of exactly that — a correction applied in one place while a
summary elsewhere kept asserting the superseded version. One home, referenced from everywhere else.

---

## 5. Coordination

The sister project is reached via an ephemeral channel at `/home/greg/Claude/coordination-channel.md`
(capital C — the shared parent of both repos, outside either git tree). It is scratch: both sides mirror
anything durable into their own repo before discarding it, so **its absence is not lost work**. An earlier
lowercase path (`/home/greg/claude/…`) is gone; do not look there.

Nothing is outstanding in either direction as of 2026-07-23. The one un-sent item is **1b's empirical
question**, held deliberately.

> **The finding both sides reached independently, worth carrying into any future round:**
> ***a characterisation is a lead, not a measurement.*** Five of five sister-side defects came from
> trusting a secondary source's description of a paper; our own census-dedup finding had the same shape —
> a catalogue's `solution_type` and grade were the signal, while the *derived* period was what misled.
