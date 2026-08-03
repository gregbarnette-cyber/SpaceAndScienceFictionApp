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

> **STATUS — ALL COMPLETE (2026-08-03).** Everything this file tracked is built: **1a** (anchor-mode age
> path) and the **v2.11.0 Q1–Q5** round (§1b + all four §2 refinements) are shipped, tested, and green
> against the live `pkt3.5-v2.11.0-2026-08-03` dataset; the coordination round is closed on both sides (§5).
> Default suite **2659 pass, 42 skipped**. The open-item text below is **retained for provenance** — read it
> for the questions as they were posed; each now carries a ✅ resolution.

The v2 build was **finished** at `pkt3.5-v2.10.0-2026-07-23` (all nine blocks validate / expose / sample); the
**v2.11.0** round then built the five items below.

This file was the live work. **`docs/research-priors-v2-open-work.md` is closed** and kept as the round record
— go there for *why* the earlier decisions were made. (One thing it says is now **superseded**: its "why no
power-law tail" reasoning was reversed by v2.11.0 **Q4**, which adds the tail via the **continuity splice** the
sister later supplied — the frozen record is not edited, but the tail IS now built.)

> **Section-number mapping — these items were renumbered when they moved here.** Session transcripts, commit
> messages and the closed plan's own §7 all refer to them by their *old* numbers, and both numbering schemes
> are live (the closed file keeps its §7 intact, so nothing dangles — but the same item has two names).
>
> | Closed plan | This file | |
> |---|---|---|
> | §7a — anchor-mode age path | **§1a** | ✅ DONE 2026-08-03 |
> | §7b — inner giants vs the spacing floor | **§1b** | ✅ DONE 2026-08-03 (v2.11.0 Q1) |
> | §7c — external dependencies (C55 gate, M-dwarf index) | — | **closed 2026-07-23; not carried over** |
>
> They lead here because they are the first thing in a document about what is left, rather than a footnote
> at the end of a finished one. Content is unchanged apart from dropping the "none of it was ever a B item"
> framing, which only made sense beside the B items.

---

## 1. Two actionable items

### 1a. Wire the anchor-mode age path · ✅ **DONE 2026-08-03** · APP-only, no external input

**As built (`core/generate.py`):** `_resolve_anchor_age(simbad)` mirrors `_resolve_anchor_feh` — **HWC
`S_AGE` → Mission Exocat `st_age`**, both **confirmed Gyr** (HWC 0.001–14.9 median ≈ 4.0; Exocat 0.4–15.0
median ≈ 6.0, measured against the CSVs), both local reads (no network), non-positive treated as absent,
`age_source` tagged `"hwc"` / `"mission_exocat"`. The anchor now populates `age_gyr`/`age_source`
(ungated, like `feh` — so a permissive anchor gets them too) and **reconstructs `activity` from that age
after all planet/moon infill**, so the synthetic-body rng stream is byte-identical to before. The anchor
builds no companion, so only the single-star P_rot branches apply. **Both prerequisites settled:** units
verified Gyr; tagging = a new constant `p_rot_source="modelled"` on the activity dict (both modes) so a
modelled `p_rot_days` can never be read as observed. `_v2_blocks_note` now claims `stellar_activity` on an
anchor only when activity actually ran, never `age_dist`. Tests: 4 added to `tests/test_generate.py`
(`TestAgeAndActivity`); full default suite **2659 passed / 42 skipped / 0 failures** (after Q1–Q5). Contract doc updated
(`docs/integration.md`, the `generate-system` `star.age_*`/`activity` block). *Original plan below, retained
for provenance.*

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

### 1b. Decide: do decoupled inner giants respect the grid's spacing floor? · ✅ **RESOLVED 2026-08-03 (v2.11.0 Q1)**

> **✅ RESOLVED.** The sister verified the Huang/Wu/Triaud lead against the primary source (Huang, Wu &
> Triaud 2016, ApJ 825, 98): **warm** giants coexist with inner small planets at the *normal* peas-in-a-pod
> floor (~50% are accompanied — no giant-specific rule needed); **hot** giants are *lonely*, so a synthetic
> hot giant now suppresses interior synthetic small planets < 0.25 AU (`_apply_hot_giant_loneliness`), with
> observed planets (a real WASP-47's companions) and in-HZ planets protected. It reads off the existing
> `giant_zone` tag — nearly free, as predicted. The original question is retained below for provenance.

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

## 2. Four dormant refinements — ✅ **ALL BUILT (v2.11.0 Q2–Q5, 2026-08-03)**

Each was blocked on the sister pinning one specific thing; the sister supplied all four in
`pkt3.5-v2.11.0`, and all four are now built and green. **The precondition mattered** — building any of
these *without* its pin would have repeated the invented-join-weight error the whole v2 round was spent
avoiding; each pin arrived first.

| Refinement | Pinned by sister → built as | Q |
|---|---|---|
| **f(e) shape** for `ecc_dist` | `f(e) ∝ e^η` (Moe & Di Stefano 2017) replaces the app-side Rayleigh(σ = 0.21) in `_draw_companion_ecc` | ✅ Q2 |
| **survival decay law** for wide pairs | smooth roll-off `S(a) = 0.5^((a/a_half)^p)` (p ≈ 1.35) replaces B3's hard truncation in `_draw_multiplicity` | ✅ Q3 |
| **join normalization** between log-normal and tail | two-break power-law tail spliced by **continuity** (zero free params — the blocker dissolved); corrects the solar-host over-production | ✅ Q4 |
| **per-population SFHs** (thin/thick/halo) | `age_dist.populations` → draw population, then that population's SFH, in `_draw_age` | ✅ Q5 |

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
QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest
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

The sister project is reached via an **append-only** channel at `/home/greg/claude/coordination-channel.md`
— the shared parent of both repos, outside either git tree. It is scratch: both sides mirror anything
durable into their own repo before discarding it, so **its absence is not lost work**.

> **Path correction (2026-08-03): the channel is lowercase `/home/greg/claude/`, not capital-C
> `/home/greg/Claude/`.** This file (and the CLAUDE.md memory note) previously said capital-C and that "an
> earlier lowercase path is gone; do not look there" — the reverse of reality on this WSL/Linux checkout.
> The filesystem is **case-sensitive**, capital-C `/home/greg/Claude/` does **not exist**, and the real
> ~25 KB channel lives at the lowercase path (verified 2026-08-03 — the same error broke a capital-C file
> path handed in at the start of that session). The sister repo is its sibling
> `/home/greg/claude/scifiWorldBuilding-Claude`. The capital-C form only resolves on a case-insensitive
> Windows checkout.

**Round closed 2026-08-03.** 1a is done (above), and the v2.11.0 round shipped all five: the sister answered
Q1 (verified the Huang/Wu/Triaud lead → hot-suppress / warm-coexist) and pinned Q2–Q5 (the `f(e) ∝ e^η`
shape, the wide-pair survival roll-off, the log-normal↔tail **continuity splice**, and the per-population
SFHs), bumping the dataset to `pkt3.5-v2.11.0-2026-08-03`; APP built + tested + mirrored all five (§1b, §2).
The sister confirmed every realized number lands on the pins. Three implementation dials (Q3 `p = 1.35`,
Q4 `s_join = 1000 AU`, Q4 `γ_mid`) are correctly APP-side and not source-pinnable — the boundary, not a gap.
The Q5 BGM per-population refinement is **closed** (the queued pull timed out server-side; the
literature-anchored thin/thick/halo forms are final). The ephemeral coordination channel was decommissioned
after both sides parked. **Nothing is outstanding on either side.**

> **The finding both sides reached independently, worth carrying into any future round:**
> ***a characterisation is a lead, not a measurement.*** Five of five sister-side defects came from
> trusting a secondary source's description of a paper; our own census-dedup finding had the same shape —
> a catalogue's `solution_type` and grade were the signal, while the *derived* period was what misled.
