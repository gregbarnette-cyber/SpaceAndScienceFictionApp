# Phase AN — Bayer & Flamsteed Designations

**Status:** PLANNED (not started)
**Date drafted:** 2026-07-28 · **Revised 2026-07-28** after adversarial pre-implementation review
**Scope:** `core/shared.py`, `core/databases.py`, `core/calculators.py`, `main.py` (policy decision — §2a), tests, docs
**Sequencing (decided 2026-07-28): `PHASE_AO_PLAN.md` ships FIRST.** AN follows.
**Depends on:** the constellation-genitive table, **built by Phase AO** (`AO §2`) and consumed here by
AN3. Not blocking for AN0/AN1/AN2 — see §7a.

> ### ✅ AO SHIPPED 2026-07-29 — AN is unblocked
>
> `completed_plans/PHASE_AO_PLAN.md`. What AN inherits:
>
> - **The genitive table exists**, at the location this plan's §7 specifies:
>   `core.shared._CONSTELLATION_GENITIVES` (88 entries) + `constellation_genitive(abbr)`
>   (case/whitespace-insensitive, `None` for unknown — never invents a name). **AN3 builds only the
>   Greek abbreviation→letter table. Do not rebuild the genitive one.** The AO §11 obligation to
>   reconcile the two plans is discharged: no edit to §7 was needed.
> - **`compute_simbad_lookup` gained a `"gould"` key.** It is a *sibling* of `designations`, not part
>   of it, so it does not touch AN0's six-copy census, `desig_str`, or the AN2d duplication problem.
>   Confirmed by `test_gould.py::test_gould_is_not_folded_into_designations`.
> - **AO4c's cross-check bonus is now available offline.** The bundled `gouldDesignations.csv` carries
>   `flamsteed` (1097 rows) and `bayer` (LaTeX form, e.g. `\alpha1`) — an independent southern-sky
>   Bayer/Flamsteed set to validate **AN1's `* ` classifier** against real data, no network needed.
>   Note `* alf01 Cen` ↔ the catalogue's `\alpha1` is exactly the AN1 superscript-numeral case.
>
> **D1 decided 2026-07-29: option (a)** — `main.py` is exempt per policy **except copy #5**
> (`main.py:2229`/`:2268`, CLI opt 50), which delegates to `core.shared` so the two opt-50 builders
> stop writing different content into one `star_systems.designations` column. Copies 3/6/7 stay as-is.
> **AN0's scope is therefore copies 1, 2, 4 and 5.** The rest of the decision table (D2–D6) is
> unchanged and still open.
>
> **AO left AN one open question — a candidate `SAO` key.** AO shipped an SAO fallback join, and
> `/code-review` found it **unreachable**: `designations` never carries an `"SAO"` key (absent from
> both `databases.py:315` `keys_order`/`:323` `prefix_map` **and** the shared `_CSV_PREFIX_MAP`), so
> the branch was dead and its test passed only against a hand-built dict shape the pipeline cannot
> produce. AO removed it rather than implement it, **because implementing it is AN2's job**: SIMBAD
> *does* emit `SAO nnnnn`, but capturing it adds a key to the designation set, which injects
> `SAO nnnnn` into `desig_str` on all four GUI banners and into the `query.py` contract — the exact
> "key insertion + ripple" AN2 owns, over the exact map AN0 consolidates. **Consider it alongside
> `Bayer`/`Flamsteed` in AN2, as a third candidate key with the same ripple.** Measured payoff: 26
> Gould rows have an SAO number but no HD, of which **3** carry a Gould number — so this is a
> tie-breaker at best, not a reason on its own. `tests/test_gould.py::test_sao_is_absent_from_the_designation_key_set`
> will fail the moment AN captures SAO, which is the prompt to re-enable AO's join.
>
> **A method note for AN4.** AO's §9 verified the change was *fully additive* and concluded nothing
> could break — true, and it still missed the above, because **a block can be additive and inert**.
> The differential harness AN4.1 specifies compares outputs before/after; it would not have caught
> this either, since dead code changes no output. **What catches this class is checking that a
> consumer's assumed input shape is one the producer can actually emit** — worth an explicit pass
> over AN's own new keys, which are consumed in more places than AO's were.
>
> **Baseline moved:** the suite is now **2174 passed, 1 skipped** (§8 cites 2120; re-confirmed by a
> full run 2026-07-29). AN's differential harness (AN4.1) must be built against the current tree, and
> `tests/test_gould.py` / `test_gould_display.py` are new files it should not be surprised by.
>
> **⚠ AO shifted the line numbers this plan cites.** AO inserted ~52 lines into `core/shared.py` (the
> genitive table, `:83-133`) and ~93 into `core/databases.py` (`_simbad_gould_block`, `:146-215`).
> **Every citation into those two files below the insertion point was re-anchored 2026-07-29** and
> re-verified against the source. `main.py`, `core/calculators.py`,
> `gui/visualizations/plot_helpers.py` and `generate_star_map_html.py` were untouched by AO — those
> citations were checked and are still exact. To stop this recurring, §2/§6/§7 now anchor on the
> **enclosing function or block**, with line numbers kept only where the evidence *is* a specific
> expression (a guard, a join, an empty-case literal). §5's verified-safe sweep is deliberately left
> un-renumbered — it is a one-shot census that AN4.1's harness supersedes; **re-run the sweep at
> implementation time rather than trusting its coordinates.**
>
> **AO also added a seventh consumer of the `designations` dict** — see §5 "Verified safe" and AN4.
> `_simbad_gould_block` reads `designations["HD"]`, so AN0 changing that slot's *shape* (a bare
> `102365` rather than `"HD 102365"`) would silently return `None` for every Gould lookup with no
> test failure. This is exactly the additive-and-inert class AO's closing lesson names, and a
> differential harness that only diffs `designations` itself would not see it.

> **Revision note.** The first draft of this plan was materially wrong in **eight** places, all found
> by pre-implementation review and all verified against the source before this rewrite. Corrections
> are marked **[R1]**…**[R8]** inline and summarized in §10. Per the house convention
> (`completed_plans/README.md`, `SPECTRAL_CLASS_PLAN.md`), the corrected numbers are the load-bearing
> record and the original errors are kept visible rather than quietly overwritten.

---

## ✅ DECISIONS — **ALL SETTLED** (D1 2026-07-29 · D2–D6 2026-07-29, maintainer)

**Nothing in this table blocks the phase any more.** D1 set AN0's scope; D2–D6 were settled against
the AN4.1 harness baseline rather than by argument — the four counts in §8 turned D3 and D5 from
judgement calls into measurements. Original recommendation text is retained in each row, per the
house convention.

| # | Decision | Chosen |
|---|---|---|
| **D1** | Does `main.py` come along? | **(a)** — exempt `main.py` per policy **except copy #5** (CLI opt 50), which delegates to `core.shared`. Copies 3/6/7 stay as-is. **Harness evidence:** copy 5's output is **identical to shared's on all 43/43** fixture stars, so this is a no-op refactor today; the split-brain only appears once AN2 adds keys, which is precisely why it is cheap to close now |
| **D2** | `V*` and `**` handling | **(a) drop both.** `**` is a double-*system* id (35 in the corpus, none a name for the star queried). `V*` is defensible — 14 ids, and for a variable star it is a real designation — but redundant with the Bayer form on essentially all of them (`V* eps Eri` beside `* eps Eri`). The classifier still **returns `"Variable"` as a distinct value**, so promoting it to a key later is one line and needs no re-classification |
| **D3** | MAIN_ID duplication (AN2d) | **(a) suppress the keyed copy when it equals MAIN_ID.** **Harness evidence: 22/43 (51%) of the corpus has a `* `-form MAIN_ID** — the duplicate is the common case, not an edge case. (c) would disfigure half of all bright-star banners; (b) drops MAIN_ID from four panels on *every* star. The harness will name exactly which stars change |
| **D4** | Opt-50 rebuild: defer or gate? | **(a) defer** — with **explicit firing triggers**, see §5 AN2c-T below. A stale `designations` column is already an accepted state here (the NAME-first change left the same debt). **Sequencing caveat:** the AN2c `PLX …` discard-delta must be re-measured **after** D5's `"N/A"`→`""` fix lands, not before — the fix is on the value that rule tests |
| **D5** | Adjudicate the drift table (§6) | **Fix the empty case to `""`; keep the rest; assert the MAIN_ID-missing divergence deliberately.** **Harness evidence: the `"N/A"` case fires on 0/43** — real in code, dormant in practice, and its only reachable path is the opt-50 discard rule's `desig_str == ""` test, which a literal `"N/A"` would defeat. No consumer wants the string `"N/A"`, so there is nothing to preserve. MAIN_ID-missing→query-string stays (it is wire-visible through `query.py`) but must be pinned by AN0d rather than inherited by accident |
| **D6** | Component-suffix preference | **Prefer the component-less form** (`* alf CMi` over `* alf CMi A`). Procyon's list carries both; first-match-wins depends on SIMBAD's id ordering, which is not a stable contract |
| **D7** *(2026-07-29, AN0→AN1 sweep)* | Does `_NARROW_DESIG_KEYS` gain `Bayer`/`Flamsteed`? | **No — keep the narrow set narrow.** Opts 17/19/20/21 and the seven route planners already render the star's MAIN_ID in a **separate name column**, which for bright stars *is* the Bayer string — so adding the key would reproduce the AN2d duplication on ten more surfaces, and **D3's dedupe lives in `compute_simbad_lookup`, so it would not reach this path**. Also avoids a golden regen, keeps the AN0b order tuple stable, and keeps exempt CLI copy 6 (which hardcodes the same five keys) in sync with the GUI. **The plan never named this constant** — the gap was found by the sweep, not by the plan |
| **D8** *(2026-07-29, AN0→AN1 sweep)* | Tie-break when a star offers several competing `* ` ids | **An explicit precedence rule, in two clauses** (needs a *replace-if-better* pass — `_match_designations` is structurally first-match-wins). **(i) Bayer: prefer the candidate with no trailing component letter.** **(ii) Flamsteed: prefer the candidate whose constellation matches the chosen Bayer's**, else first. Ties → first, which is stable because tied candidates are equal-shaped. See §4b for why one clause covers all three measured cases |
| **D9** *(2026-07-29, AN0→AN1 sweep)* | Flamsteed's double space (`*  18 Eri`) | **Store verbatim; fix the display layer in AN3.** §7a makes the raw SIMBAD string the identifier — verbatim and round-trippable. The four strippers do `name[len("* "):]` with no follow-up strip and render `" 18 Eri"`; **this already misrenders 796 live `star_systems` rows today**, so it is a pre-existing display bug worth fixing on its own merits, not a Bayer/Flamsteed cost |

**A fifth §6 divergence, found by the harness after these decisions were framed** — the copies
disagree on **table indexing** (column-first in `shared`, row-first in `databases`/`calculators`;
§8). Harmless today, but AN0 must not assume one style when converging them. Not a decision, a
constraint.

<details>
<summary><b>Original decision table, retained for the record</b> (options + pre-harness recommendations)</summary>

**D1 blocks the phase.** It sets AN0's scope — a three-site or a six-site refactor — and it touches a
standing policy, so it is not an implementer's call. The rest gate individual parts.

| # | Decision | Gates | Options | Recommendation |
|---|---|---|---|---|
| **D1** | **Does `main.py` come along?** (§2a — full options table there) | **AN0 — the whole phase** | **(a)** Exempt `main.py` per policy **except copy #5** (CLI opt 50). **(b)** Full consolidation, all 6 copies. **(c)** Strict policy — leave all of `main.py` | **(a).** `IMPROVEMENT_PLAN.md` ground rule 1 says don't touch `main.py` feature functions (your 2026-07-04 call), but copy #5 writes the **same `star_systems.designations` column** as GUI opt 50 — leaving it makes the two entry points write different content into one column. **(c) is not acceptable** unless CLI opt 50 is formally retired |
| **D2** | **`V*` and `**` handling** (§4, AN1a) | **AN1** | **(a)** Drop both. **(b)** Drop `**`, capture `V*` as a `"Variable"` key | **(a) drop both.** `**` is a double-*system* id, not a name for this star. `V*` is a genuine designation but redundant with the Bayer form for most stars — widens the `query.py` contract for little gain. Revisit separately if wanted |
| **D3** | **MAIN_ID duplication** (§5, AN2d) | **AN2** | **(a)** Suppress the keyed copy when it equals MAIN_ID. **(b)** Drop MAIN_ID from the `desig_str` join entirely. **(c)** Accept the duplicate | **(a).** (b) removes MAIN_ID from all four GUI banners — a visible regression. (c) renders `* alf CMi, NAME Procyon, * alf CMi, …`. This changes what every panel displays, so it is a product call, not a cleanup |
| **D4** | **Opt-50 rebuild: defer or gate?** (§5, AN2c) | **AN2** | **(a)** Defer — lookup surfaces get the names now, DB-backed surfaces catch up at the next rebuild. **(b)** Gate the phase on a full opt-50 rebuild (17 SIMBAD queries, ~238k rows, hours) | **(a) defer.** A stale `designations` column is already an accepted state in this repo (the NAME-first change left the same debt). **Note:** the rebuild changes **row count**, not just column text — re-measure the `PLX …` discard delta when it happens |
| **D5** | **Adjudicate the drift table** (§6) | **AN2e** | Five behavioural differences between the copies — the `key in …` guard, `"N/A"` vs `""` empty case, MAIN_ID in the join, MAIN_ID source, MAIN_ID-missing semantics. Each is keep-or-fix | **Per §1 lesson 1, judge each on merit — do not preserve drift reflexively.** P4.6 tried that and the preserved drift *was* the bug. The `"N/A"` vs `""` split is most likely a latent bug (a literal `"N/A"` reaching a DB column or JSON consumer) |
| **D6** | **Component-suffix preference** (§4, AN1b) | AN1 | Prefer `* alf CMi` over `* alf CMi A`, or take first match | **Prefer component-less.** Low stakes, but first-match-wins is non-deterministic across SIMBAD releases. Effectively an implementer's call |

*(D1 was marked ✅ DECIDED (a) in this table on 2026-07-29, ahead of D2–D6.)*

</details>


**Settled, no input needed:**

- **Sequencing** → `PHASE_AO_PLAN.md` ships first (decided 2026-07-28).
- **Genitive-table ownership** → AO builds it, AN3 consumes it (§7). AN3 builds only the Greek table.
- **AN0 ordering constraint** → not a choice. AN0 must land completely before AN1 adds any prefix
  entry, or three unguarded copies raise `KeyError` (§3, AN0a).
- **Harness before AN0** → not a choice (§8). It cannot be built after the refactor it verifies.

---

## 0. Problem statement

SIMBAD returns Bayer and Flamsteed designations for most bright stars, and the app
**silently discards them**. They are present in the `Simbad.query_objectids()` response
under an asterisk-space prefix, but `core/shared.py::_CSV_PREFIX_MAP` has no `* ` entry,
so the `startswith` loop never matches and the id is dropped.

Verified against live SIMBAD (2026-07-28):

| Star | ids SIMBAD returns | what the app keeps |
|---|---|---|
| ε Eridani | `* eps Eri`, `*  18 Eri`, `V* eps Eri`, `NAME Ran` | MAIN_ID `* eps Eri`, NAME `NAME Ran` — **`*  18 Eri` dropped** |
| Procyon | `* alf CMi`, `*  10 CMi`, `* alf CMi A`, `NAME Procyon` | MAIN_ID `* alf CMi` — **`*  10 CMi` dropped** |
| τ Ceti | `* tau Cet`, `*  52 Cet` | MAIN_ID `* tau Cet` — **`*  52 Cet` dropped** |
| GJ 432 A | `*  20 Crt` | shows **only** because SIMBAD happened to pick it as `main_id` |

**[R1] Correction to the original framing.** The first draft said a Bayer name is "absent from the
`designations` dict." It is **not** — it is present in the `MAIN_ID` slot whenever SIMBAD picks it as
`main_id`, which is most bright stars. What is missing is capture as a designation *type*. This
distinction matters: it is the direct cause of the duplication bug in §5 (AN2d), which the original
plan did not foresee.

> **Out of scope — Gould.** SIMBAD's `ident` table contains **zero** Gould (`G.`) identifiers in any
> format (`id LIKE 'G. %'` → 0; `id LIKE '% G. %'` → 0; `id LIKE '%Gould%'` → 2 rows, both
> `NAME Gould('s) Belt`, the nebular structure). No change here can surface them. See `PHASE_AO_PLAN.md`.

---

## 1. Prior art — this is the unfinished half of IMPROVEMENT_PLAN P4.6

`IMPROVEMENT_PLAN.md:407-420` already specifies this consolidation under **P4.6 "Designation
parsing."** Its SUPERSEDED note (2026-07-26) records that `core/databases.py` now uses
`core.shared._CSV_DESIG_KEYS` — true of the **opt-50 builder** path (`databases.py:1334` aliases the
shared key list, `:1379` calls the shared parser), but **the inline map inside `compute_simbad_lookup`
(`databases.py:315-365`) was never
consolidated**, and neither were any of the `main.py` copies. So P4.6's designation bullet is itself
only partially done, and P4.6 does not say so.

**Two lessons from P4.6 that bind this phase:**

1. **"Preserve the drift as configuration" was the original P4.6 instruction — and was later
   superseded because preserving the drift *was* the bug.** It meant SIMBAD's common name was parsed
   out of `ids` then dropped, so no `star_systems.designations` value ever carried one. **Therefore:
   byte-identical is the default, not the goal.** Each difference found in §6 must be judged on its
   merits; at least one of them was a bug last time.
2. **The sibling consolidation stalled and caused a live crash.** P4.6's sexagesimal RA/Dec bullet is
   still **PARTIALLY DONE** — four copies across six call sites with *three different failure
   contracts*, and that divergence aborted opt 19 on a blank `ra`. This is direct evidence that parser
   consolidation in this repo is exactly as risky as AN0 is rated, and that it is the kind of task
   that stalls half-finished.

**Action:** when AN0 lands, update `IMPROVEMENT_PLAN.md` P4.6's designation bullet to point here, or
the two documents will describe the same work independently.

---

## 2. The real blocker — **six** drifted copies, not four **[R2]**

The original plan claimed four copies. **There are six functional copies plus a seventh hardcoded key
list.** All verified in source 2026-07-28.

**Anchors re-verified 2026-07-29 (post-AO).** Each row names the **enclosing block**, which is what
survives an insertion above it; line numbers appear only where the claim rests on a specific line.

| # | Location | Serves | State |
|---|---|---|---|
| 1 | `core/shared.py` — module-level `_CSV_PREFIX_MAP` (`:35`) + `_CSV_DESIG_KEYS` (`:67`) | opt-50 builder via `databases._parse_designations_from_ids`; `shared._parse_designations` (`:229`) | canonical (P4.6) |
| 2 | `core/databases.py` — the inline `keys_order` (`:315`) + `prefix_map` (`:323`) + match loop (`:359`) inside **`compute_simbad_lookup`** | GUI SIMBAD panel **and** `query.py simbad-lookup` | inline duplicate; module imports the shared names at `:16-17` and uses them at `:1334` but **not here**. *(Was cited `:222-261` pre-AO — and `:304`/`:312` in §5, two stale numbers for one map.)* |
| 3 | `main.py` — `keys_order` (`:62`) + `prefix_map` (`:76`) + loop (`:109`) in the opt-1 lookup | CLI opt 1 | inline duplicate *(original plan cited `60-105`; the match loop is outside that range)* |
| 4 | `core/calculators.py` — `desig_found` (`:272`) + `desig_prefix_map` (`:273`) + join (`:284`) in `compute_lookup_star_for_distance` | opts 17/19/20/21 + all seven route planners | **narrow** — `NAME/HD/HR/GJ/Wolf` |
| **5** | **`main.py` — `_CSV_PREFIX_MAP` (`:2229`) + `_CSV_DESIG_KEYS` (`:2261`) + `_parse_designations_from_ids` (`:2268`, body `:2273-2283`)** | **CLI opt 50** via `main.py:2321` → `_run_simbad_csv_query` → `query_star_systems_csv` | **complete standalone re-implementation** |
| **6** | **`main.py` — `desig_found` (`:2693`) + `desig_prefix_map` (`:2694`) in `_lookup_star_for_distance`** | **CLI opts 17/19/20/21** | second narrow `NAME/HD/HR/GJ/Wolf` map |
| 7 | `main.py:139-144` | CLI opt 1 "STAR DESIGNATIONS:" banner | not a prefix map — a hardcoded 20-key `keys_order` used only to build the display join. **Must be edited in AN2 or the CLI banner silently omits the new keys.** |

**Verified: `main.py` imports nothing from `core.shared`.** The original plan's claim that
"`main.py:2268` already delegates" was **false** — `main.py`'s own `_parse_designations_from_ids`
(`:2268`) reads `main.py`'s *own* module-level locals (`:2229`, `:2261`).

### 2a. Decision required — does `main.py` come along? ⚠️

`IMPROVEMENT_PLAN.md` ground rule 1 states: *"Do NOT touch `main.py` feature functions... The CLI menu
is no longer used (user decision 2026-07-04)."* That policy would drop copies 3, 5, 6 and 7 from
scope, roughly halving AN0.

**But copy #5 is not inert.** CLI opt 50 and GUI opt 50 write **the same `star_systems.designations`
column**. If AN2 adds `Bayer`/`Flamsteed` to `core/shared.py` only, the two builders produce
**different content in the same column** depending on which entry point ran. That is a worse state
than today's uniform omission.

Three options:

| | Action | Consequence |
|---|---|---|
| **A** *(recommended)* | Exempt `main.py` per policy, **except copy #5**, which is retired by making `main.py:2268` delegate to `core.shared` | Honours the policy's intent (don't touch *feature* functions) while closing the split-brain DB write. Copies 3/6/7 stay stale — acceptable, they are display-only in a deprecated CLI |
| B | Full consolidation including all `main.py` copies | Largest AN0; contradicts standing policy; `main.py` has **zero test coverage** (§7) |
| C | Strict policy — leave all of `main.py` | CLI opt 50 writes a different designations column than GUI opt 50. **Not acceptable** unless CLI opt 50 is formally retired |

**✅ DECIDED 2026-07-29: option A.** And the AN4.1 harness has since measured that copy 5's output is
**byte-identical to shared's on all 43/43** fixture stars — so the delegation changes nothing today,
and exists to stop the two opt-50 builders diverging the moment AN2 adds keys.

---

## 3. Part AN0 — Consolidate onto `core/shared.py`

**Goal:** the copies in scope (per §2a) delegate to `core.shared`; copies 4 and 6 stay narrow but stop
re-typing the map.

### AN0a — ordering constraint (hard) **[R3]**

Copies 2, 3 and 5 match with **no `key in designations` guard** (`databases.py:360`, `main.py:110`,
`main.py:2279`), unlike shared (`shared.py:248`, `:275`). **The moment a `* `-shaped entry is added to
`shared._CSV_PREFIX_MAP` while any unguarded copy still reads it, that copy raises `KeyError`.**

Copy #5 reads `main.py`'s own map, so it is insulated — but copies 2 and 3 would break if they were
ever pointed at the shared map mid-refactor.

**Therefore: AN0 must land completely for every in-scope copy before AN1 adds a single prefix entry.**
No partial ordering is safe. Pin this with a test that adds a synthetic entry to the shared map and
asserts every call site survives.

### AN0b — the narrow copies must receive an **explicit ordered key list** **[R4]**

The original plan said to build copy #4's map by *filtering* `shared._CSV_PREFIX_MAP`. **That is not
byte-identical.**

`calculators.py:284` is `", ".join(v for v in desig_found.values() if v)` — a **dict-values
iteration**, so output order is `desig_found`'s insertion order, set at `calculators.py:272`:
**`NAME, HD, HR, GJ, Wolf`**. Filtering `shared._CSV_PREFIX_MAP` (order `NAME, GJ, HD, HIP, HR, Wolf`)
yields **`NAME, GJ, HD, HR, Wolf`** — GJ moves 4th→2nd, HD 2nd→3rd.

Procyon's `desig_str` would change from
`NAME Procyon, HD 61421, HR 2943, GJ 280` → `NAME Procyon, GJ 280, HD 61421, HR 2943`
on every consumer: `gui/panels/distance_stars.py:106-108`, `gui/panels/travel_time_stars.py:114-116`,
`gui/panels/route_planning.py:258`, `core/calculators.py:1620`.

**Fix:** pass an explicit ordered key list; never derive order from the map. Note copy #6
(`main.py:2693-2711`) re-loops an explicit `("NAME","HD","HR","GJ","Wolf")` tuple, so it is *not*
order-fragile — the two narrow copies agree today but would diverge under two different "obvious"
fixes. That asymmetry is itself worth a regression test.

#### AN0b-note — copy #4 is also why opts 17/20/21 + the route planners show no Gould designation

**Recorded 2026-07-29, after Phase AO shipped.** Not a bug and not AO's omission — a structural
consequence of this copy, worth knowing before AN0 decides how far to converge it.

Phase AO attaches its `"gould"` key inside **`compute_simbad_lookup`** (copy #2). But opts 17/20/21
and all seven route planners do not call that function at all — they go through
**`calculators.compute_lookup_star_for_distance`** (copy #4), a separate, narrower SIMBAD lookup
whose `desig_str` is `NAME/HD/HR/GJ/Wolf` only and which has no `gould` key to render. So those
panels are correctly Gould-less today, and no AO-side change could have fixed it.

**What this means for AN0's scope decision:**

- If AN0 converges copy #4 onto the shared parser but leaves the two lookup *functions* separate
  (the likely, minimal reading of this plan), **nothing changes** — those panels stay Gould-less,
  which is fine and should be stated rather than discovered.
- If AN0 goes further and the two lookups come to share a result shape, those ten surfaces become a
  **cheap follow-on**: `gui.panels.base.add_gould_line(layout, result)` already exists, is a no-op
  when the key is absent, and is wired into four panels. That is the entire cost.

**Do not "fix" this by calling `_simbad_gould_block` from `calculators.py`.** Copy #4's whole point
is that it is the cheap path — a second DB read per star on a route planner that resolves dozens of
stars is the wrong trade, and it would add a seventh place that knows about designation parsing,
which is the problem this phase exists to remove.

### AN0c — `desig_str` and `MAIN_ID` **[R5]**

`databases.py:364` joins over `keys_order`, whose **first element is `MAIN_ID`** (`:315`).
`shared.py:278-279` joins over `_CSV_DESIG_KEYS`, which has **no `MAIN_ID`** (`:67-71`).

So a shared `build_desig_str(designations, keys)` is byte-identical **only** if `compute_simbad_lookup`
passes `["MAIN_ID"] + _CSV_DESIG_KEYS`. Passing `_CSV_DESIG_KEYS` silently drops MAIN_ID from **every**
GUI banner (`simbad.py:157`, `star_regions.py:396`, `nasa_exoplanet.py:61`, `catalogs.py:200`).

### AN0d — the proposed golden test is invalid as written **[R6]**

The original plan proposed asserting `compute_simbad_lookup` and `shared._parse_designations` produce
the same dict. **They legitimately do not.** On a masked/blank `main_id`:

- shared (`shared.py:238-239`) → `MAIN_ID` stays `None` (set only when `main_id` is in the colnames)
- databases (`databases.py:263` `main_id = str(_safe("main_id") or star_name)`, assigned at `:321`) →
  `MAIN_ID` becomes **the user's query string**, set unconditionally

That is a real contract difference, wire-visible through `query.py:78`. The equivalence test must
either exclude `MAIN_ID` or assert the divergence deliberately.

**Acceptance for AN0:** no output change on any in-scope call site, except where §6 identifies a
difference judged to be a bug — each such case decided explicitly and recorded here.

### ✅ AN0 — BUILT 2026-07-29

**Acceptance met exactly: zero output change.** The AN4.1 golden baseline
(`designation_golden.json`) was **not regenerated** — it still matches byte-for-byte on all 43 stars
across every in-scope producer. Suite **2183 passed, 1 skipped** (2181 + the two pins below).
`/code-review` ran on the working diff and confirmed behavioural equivalence independently; its three
low-severity findings were applied before this entry was written (§11's sequencing rule).

**What landed.** One canonical matcher in `core/shared.py` — `_match_designations` /
`_join_designations` / `_designation_ids_from_rows`, plus `_NARROW_DESIG_KEYS` — with all four
in-scope copies delegating to it. Copy 2's 44-line inline prefix map, copy 4's 5-entry map, and copy
5's standalone map + parser are deleted; `main.py` now imports `core.shared` (a first).

**The four constraints, and where each is now held:**

| Constraint | How it is held |
|---|---|
| **AN0a** ordering | The `key in desig` guard exists in exactly one place, so all four sites are guarded. AN1's `* ` entry cannot `KeyError` anywhere |
| **AN0b** key order | `calculators` receives `_NARROW_DESIG_KEYS` explicitly; nothing derives order from the prefix map. `NarrowCopyOrderTest` still pins HD-before-GJ |
| **AN0c** MAIN_ID first | `keys_order = ["MAIN_ID"] + _CSV_DESIG_KEYS`; asserted directly in `MainIdDivergenceTest` |
| **AN0d** MAIN_ID divergence | Preserved **and now asserted** rather than inherited — `MainIdDivergenceTest` pins shared→`None` vs databases→the query string |

**One harness test had to change — and it was forced, not chosen.**
`SharedMapGuardTest::test_unguarded_copies_are_still_unguarded` asserted, by source inspection, that
`compute_simbad_lookup` still contained its own **unguarded** loop. That is precisely what AN0
removes, so no correct AN0 could keep it green; its own docstring anticipated this ("a copy grew a
guard — good news... verify before deleting"). It was replaced by two **stronger** pins, both
executable rather than textual:

- `test_every_in_scope_copy_survives_a_new_prefix_entry` — injects a synthetic prefix entry into the
  shared map and drives all four producers end to end. This is AN0a's actual requirement, where the
  old test was a proxy for it.
- `test_the_shared_matcher_is_the_only_designation_loop_in_core` — counts the loop **header**
  (`for prefix, key in`) per module: shared 1, databases 0, calculators 0, **main.py 2**. A first
  draft matched the guard *body* verbatim; `/code-review` correctly caught that every deleted copy
  spelled it with `designations` rather than `desig`, so a re-typed copy in the historic naming would
  have slipped past. The review also suggested covering `main.py` — correct in spirit, but the strict
  form would be wrong, since main.py legitimately **keeps** two copies; pinning the count is what
  makes a returning copy 5 fail while leaving copies 3/6 exempt.

**A finding worth carrying into AN1: copies 3 and 6 are insulated, not just exempt.** They loop over
their **own** local `prefix_map` (`main.py:110`, `:2670`), not the shared one, so AN1 adding a `* `
entry cannot `KeyError` there. Those CLI paths simply will not gain Bayer/Flamsteed — the accepted
D1(a) state, now verified rather than assumed.

**Docs corrected in the same pass** (both were made false by this diff, and both are read-on-demand
references that would have sent the next reader to re-add a local map):
`docs/star-databases.md` opt-50 helper bullet, and `databases._simbad_gould_block`'s docstring, which
still explained the dead SAO branch in terms of a module-local `prefix_map` that no longer exists.

---

## 4. Part AN1 — Classify the `* ` prefix

`* ` carries **two** designation systems plus two lookalikes that must not match:

```
*  20 Crt        Flamsteed   (DOUBLE space before the number)
*  18 Eri        Flamsteed
* alf CMi        Bayer
* alf CMi A      Bayer + component letter
* alf01 Cen      Bayer + superscript numeral (α¹)
V* eps Eri       variable-star designation
** LDS 6248A     DOUBLE-star system id — NOT a name for this star
```

Add a classifier, not more map rows:

```
_classify_star_id(id_str) -> "Bayer" | "Flamsteed" | "Variable" | None
```

1. `startswith("** ")` → `None`. ~~**Must be tested before `* `** — `** LDS 6248A` also satisfies
   `startswith("* ")`. Load-bearing ordering; pin it.~~ **[A4] — this premise is FALSE; see below.**
2. `startswith("V* ")` → `"Variable"` (see AN1a).
3. `startswith("* ")` → strip, split, token 0 all-digits → `"Flamsteed"`, else `"Bayer"`.
4. else → `None`, fall through to the prefix map.

Integrate as a **pre-pass** in the shared loop so all in-scope call sites inherit it from AN0.

> **[A4] Correction to step 1 (2026-07-29, found by AN1's own test).** The plan asserts three times —
> here, in §12, and in the AN4.1 harness docstring — that `** LDS 6248A` "also satisfies
> `startswith("* ")`", making the `** `-before-`* ` ordering **load-bearing**. **It does not, and it
> is not.** `"** LDS 6248A".startswith("* ")` is `False`: two asterisks then a space never matches
> asterisk-then-space. The `* ` branch could not claim a `**` id even if it ran first, so the
> ordering is free.
>
> **Keep the branch anyway — it guards something real, just not that.** The two other obvious ways to
> write this test *would* misfire: `startswith("*")` matches every `**` id, and stripping asterisks
> first (`"** SHB    1A".lstrip("*").strip()` → `"SHB    1A"`) yields a token that reads as a Bayer
> letter. Both are live hazards, and the display layer already contains asterisk-stripping helpers
> of exactly that shape (§7 [R8]/[A3]), so the mistake has precedent in this repo.
>
> The pin survives with a corrected premise:
> `tests/test_designation_ids.py::ClassifierTest::test_the_double_star_branch_guards_a_looser_implementation`
> now asserts the *true* facts (`** X` fails `startswith("* ")`, passes `startswith("*")`, and
> asterisk-stripping reads it as Bayer) rather than the false one. **This is the second plan claim
> disproved by writing its own test** — the first being [R6]'s non-existent byte-identical guard.

### 4a. AN0 → AN1 boundary sweep — findings (2026-07-29, post-AN0, Opus agent + builder verification)

The §11 sweep ran after AN0 landed. Every claim below was **re-verified by the builder against the
source** before being recorded; two cases were found by that verification and are not the agent's.

**Question (a) — does AN0's landed shape change how AN1's classifier integrates?**
**Mostly no, and it is better than §4 assumed** — the pre-pass has exactly one edit point,
`core.shared._match_designations`, and all four in-scope producers route through it. But three
things §4 takes for granted are false:

- **⚠ The AN0a guard is NOT inherited by a pre-pass.** `key in desig` is one conjunct of the `if`
  *inside* the `_CSV_PREFIX_MAP` loop — not a function-level invariant. A pre-pass written as
  `if k: desig[k] = id_str` raises **`KeyError: 'Bayer'`** on the narrow path (`_NARROW_DESIG_KEYS`
  has no such key). **The pre-pass must re-spell the guard itself**, and AN1 needs a narrow-path
  classifier test: the existing synthetic-entry pin exercises the *prefix loop*, so it cannot catch
  this.
- **`_NARROW_DESIG_KEYS` was unspecified** → now **D7 (no)**. With the guard correctly written the
  narrow path silently skips the new keys, which is safe — but it means those ten surfaces never gain
  the designations, and that had to be a decision rather than an accident.
- **D6 cannot be implemented as a pre-pass** — see D8 and the three cases below.

**The three tie-break cases (D8), measured against the committed corpus:**

| Case | Evidence | Why D6 alone is insufficient |
|---|---|---|
| Component suffix | **Procyon** `['*  10 CMi', '* alf CMi', '* alf CMi A', …]` vs **Sirius** `['** AGC 1A', '* alf CMa A', '* alf CMa', '*   9 CMa']` | The two stars order the suffixed and component-less forms **oppositely, in the same corpus**. First-match-wins gives Procyon the right answer and Sirius the wrong one. D6's worry is demonstrable today, not a future SIMBAD-release risk |
| Superscript numeral vs component | **α Cen A** `['* alf Cen A', '* alf01 Cen', …]` | "Prefer component-less" selects `* alf01 Cen` — **α¹ Cen, a different designation**, not the component-stripped form of `alf Cen A`. The plan's only worked example (Procyon) does not disambiguate this |
| Two Flamsteed ids | **Fomalhaut** `['*  24 PsA', '*  79 Aqr']` | Two Flamsteed numbers in **different constellations**. First-match-wins picks 24 PsA. Neither the plan nor the sweep flagged this; found during verification |

### 4b. The D8 precedence rule, resolved (2026-07-29)

**Clause (i) — Bayer: prefer the candidate with no trailing component letter.** One rule covers all
three measured cases, which is why D8 ended up cheaper than the sweep implied:

| Star | Candidates | Chosen | Note |
|---|---|---|---|
| Procyon | `* alf CMi`, `* alf CMi A` | `* alf CMi` | D6's original example |
| Sirius | `* alf CMa A`, `* alf CMa` | `* alf CMa` | **Ordered opposite to Procyon** — this is the case first-match-wins got wrong |
| α Cen A | `* alf Cen A`, **`* alf01 Cen`** | **`* alf01 Cen`** | The superscript form carries no component letter, so the same clause selects it |

**α Cen A was a real decision, not a mechanical fallout** (maintainer, 2026-07-29). Its MAIN_ID is
`* alf Cen A`, so choosing that form would make **D3 suppress it as a duplicate** and the star would
gain nothing from this phase. The superscript form differs from MAIN_ID, survives D3, and surfaces
α¹ Cen — a real designation the app discards today. Cost: **AN3's Greek table must handle the
superscript numeral (`alf01` → α¹) on a live path**, which §4 already lists as a shape to classify.

**Clause (ii) — Flamsteed: prefer the candidate whose constellation matches the chosen Bayer's.**
Fomalhaut's Bayer is `* alf PsA`, so this selects `*  24 PsA` over `*  79 Aqr` — correct, since 79 Aqr
is Flamsteed's historical cross-boundary duplicate. With no Bayer to key off, fall back to first.

**A consequence worth stating plainly, because it reframes the phase's payoff:** for every corpus star
except α Cen A, the Bayer candidate clause (i) selects **equals MAIN_ID** — so **D3 suppresses it and
it displays nowhere**. On the 22/43 `* `-MAIN_ID stars the visible gain from this phase is therefore
the **Flamsteed** ids (`10 CMi`, `9 CMa`, `3 Lyr`, `24 PsA`), which are never a main id. The Bayer key
still exists in the dict and reaches `query.py`'s consumers; it is the *banner* that is unchanged.

**Ordering vs the prefix map: safe, and now measured.** **No entry in `_CSV_PREFIX_MAP` starts with
`*` or `V`** (checked programmatically), and across the corpus zero of the 47 `* `, 14 `V*` and 35
`**` ids match any existing prefix. Classifier-before-loop and after-loop are behaviourally identical
today — pin it anyway, it is one line from being false. Two adjacent traps: the corpus contains
`VVO 20`/`VVO 21`/`VVO 23`, so a classifier testing `startswith("V")` rather than `startswith("V* ")`
misfires; and `** SHB    1A` carries runs of internal spaces, so `**` detection must not assume a
single space.

**Question (b) — is the census still complete?** **Yes, with one addition and one correction.**

- **CONFIRMED:** `main.py` retains exactly two match loops (`:110`, `:2670`), both over their **own**
  local maps, both with keys ⊆ their own key lists — **insulated**, cannot `KeyError` when AN1 adds a
  shared prefix entry.
- **CONFIRMED:** `designations["HD"]` still holds the prefixed `"HD 102365"` string, so
  `_simbad_gould_block` is intact (AN4.5 green).
- **CONFIRMED (§5 sweep re-run post-AN0):** nothing iterates the `designations` dict and nothing
  splits `desig_str` positionally. Every consumer is `.get()` on fixed keys.
- **NEW — copy 8:** `shared._parse_designations` (`core/shared.py:292-296`) carries its **own
  hardcoded `keys_order` literal** duplicating `["MAIN_ID"] + _CSV_DESIG_KEYS`. AN2 adding a key to
  `_CSV_DESIG_KEYS` but not here yields a dict whose new keys land at the **end** of insertion order
  (via the `.update()`) instead of the literal's position. **And the function has no production
  caller** — `main.py`'s eight `_parse_designations(...)` calls resolve to its *own* copy-3 local, not
  this one. It ships nothing but is a compared producer in the harness, so do not delete it casually.
- **⚠ §7 [R8] is factually wrong and is corrected below:** `_norm_oec_name` handles **all three**
  prefixes today, not `NAME ` only.
- **The straggler pin is narrower than it reads.**
  `test_the_shared_matcher_is_the_only_designation_loop_in_core` counts a literal string in **four
  named files**. A copy in `gui/`, `query.py`, or another `core/` module is invisible to it, as is one
  spelled `for pfx, k in`. It pins regression in the known files; it is **not** a census.
- **Two consumers that will stay inert unless explicitly edited:** `report.py:46`
  `_IDENTITY_DESIG_KEYS` (the Phase Q dossier's curated 5-key subset) and copy 7
  (`main.py:137-141`). Both are "safe" in the §5 sense and both will simply not show the new keys.

**AN1a — ✅ DECIDED (D2, 2026-07-29):** `**` → drop. `V*` → drop *as a key*, but the classifier still
**returns `"Variable"`**, so step 2 above stays — promoting it to a key later is one line and needs no
re-classification. Corpus: 35 `**` ids and 14 `V*` ids across the 43 fixtures.
**AN1b — ✅ DECIDED (D6, 2026-07-29):** prefer the component-less form (`* alf CMi` over
`* alf CMi A`); first-match-wins is non-deterministic across SIMBAD releases. Pin with Procyon's real
id list, which is in the AN4.0 corpus and carries both forms.

---

## 5. Part AN2 — Key insertion and the ripple

Add `"Bayer"` / `"Flamsteed"` to `_CSV_DESIG_KEYS` / `keys_order` — **and to `main.py:139-144`**
(copy #7) if `main.py` is in scope.

### AN2-SAO — a **third** candidate key, inherited from Phase AO (recorded 2026-07-29)

**Decide this alongside `Bayer`/`Flamsteed`, not separately** — it is the same insertion, the same
ripple, and the same review pass.

AO built an SAO fallback join for its Gould lookup and `/code-review` found it **unreachable**:
`designations` carries no `"SAO"` key, in *any* copy — absent from `databases.py:315` `keys_order`
/ `:323` `prefix_map` **and** from the shared `_CSV_PREFIX_MAP`. AO removed the dead branch rather
than implement it, precisely because implementing it is this part's work.

- **It is implementable.** SIMBAD *does* emit `SAO nnnnn` (verified live on HD 102365, 2026-07-28).
  A `("SAO ", "SAO")` prefix entry is all the parser needs.
- **The ripple is identical to Bayer/Flamsteed's** — a new key means `SAO nnnnn` in `desig_str` on
  all four GUI banners, in `star_systems.designations` at the next opt-50 rebuild, and in the
  `query.py` contract (AN2b's key-order note applies).
- **The payoff is small and measured: 3 stars.** 26 rows in `gouldDesignations.csv` carry an SAO
  number but no HD, and only 3 of those have a Gould number. **This is a tie-breaker, not a
  reason.** If `Bayer`/`Flamsteed` are going in anyway and SAO rides along for one map entry, fine;
  if it needs its own justification, it does not have one.
- **If AN does take it,** re-enable AO's join: restore the `("SAO","sao")` branch in
  `databases._simbad_gould_block` and revert the docs in `docs/star-databases.md` (Join bullet) +
  `docs/integration.md` (`matched_on` is currently documented as always `"hd"`).
- **The tripwire:** `tests/test_gould.py::test_sao_is_absent_from_the_designation_key_set` fails the
  moment SAO is captured. That failure is the prompt, not a bug — update it in the same commit.

### AN2a — display order, corrected **[R5]**
The original recommendation (`NAME, Bayer, Flamsteed, GJ, HD, …`) ignored that the rendered string
already **leads with MAIN_ID**. Actual current output for Procyon: `* alf CMi, NAME Procyon, …`.

### AN2b — `query.py` contract
`query.py:78` serializes the dict verbatim. New keys are additive, **but key insertion order is also
wire-visible** to the sibling repo — inserting after `NAME` reorders the JSON object. Document in
`docs/integration.md`.

### AN2c — opt-50 rebuild: row **count** changes, not just column text **[R7]**
The original plan said "existing rows keep the old content." True, but incomplete. The discard rule
(`databases.py:1381`, `main.py:2324`) is:

```python
if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":
```

Adding keys makes `desig_str` non-empty for stars that previously captured nothing, so rows previously
**discarded** are now **kept**. The next opt-50 rebuild therefore changes **row count**, not merely
column text. (Live measurement says `PLX …` main_ids are currently zero, so the practical delta is
likely nil — but the claim in the plan must be correct, and this must be re-measured at rebuild time.)

**Ordering, per D5:** the discard rule tests `desig_str == ""`, which is the exact value D5 changes
from `"N/A"` in copy 2. **Land the D5 fix first, then measure** — a delta measured against the
`"N/A"` behaviour would be measuring the wrong thing.

### AN2c-T — D4 deferral: the triggers that fire it ⚠️

**D4 = defer** (decided 2026-07-29). Deferral is only safe if it is *observable*, so the debt is
written down with the specific events that discharge it. A deferral with no trigger is how P4.6's
sexagesimal bullet sat PARTIALLY DONE for months (§1 lesson 2).

**The state being deferred:** after AN2, `compute_simbad_lookup` and the two narrow lookups emit
Bayer/Flamsteed immediately, but **`star_systems.designations` does not**, because that column is
written only by an opt-50 run. So lookup surfaces (opts 1, 3–6, 8–10) show the new designations while
DB-backed surfaces (opts 18/19, opt-51's CSV export, the seven route planners, the G1
`designation_prefix` search) do not, until a rebuild. **That asymmetry is the intended, accepted
state — not a bug to chase.**

| # | Trigger | Kind | What to do when it fires |
|---|---|---|---|
| **T1** | The AN2 test asserting the **opt-50 builder emits `Bayer`/`Flamsteed`** for a fixture ids string ever fails | **Mechanical — runs in CI every suite** | The deferral is **invalid**: the *code* is wrong, not just the data. Stop and fix; a rebuild would not help. This is the one trigger that fires by itself, and it is why it exists — everything below depends on a human noticing |
| **T2** | **Anyone runs option 50** (CLI or GUI), for any reason | Event | D4 discharges itself. **Record `count` + `discarded` before and after** and re-measure the AN2c `PLX …` delta (after D5 — see above). Update this section and `docs/star-databases.md` with the measured numbers in the same commit |
| **T3** | A Bayer/Flamsteed shows on a lookup surface but is **missing on a DB-backed one** (opt 18/19, the CSV export, a route-planner table, a G1 prefix search) | Symptom | **This is D4 firing as designed.** Do not debug the parser. Either accept it or run T2. Recognising this costs minutes; misdiagnosing it as a parser bug costs a day |
| **T4** | The **sibling repo** asks for Bayer/Flamsteed through `search-star-systems --designation-prefix`, the `starSystems.csv` export, or any `star_systems`-backed subcommand | Consumer demand | Escalates D4 from deferred to **required**. Run the rebuild (T2) before answering, or the consumer silently gets a false negative — a prefix search for `*` would return nothing and read as "this star has no Bayer designation" |
| **T5** | Any *other* work re-runs opt 50 — a SIMBAD refresh, a `PLX` rule change, a new designation key (**including the AN2-SAO candidate**) | Event | Fold the D4 measurement into that run rather than scheduling a second ~hours-long rebuild. Two rebuilds for one column is waste |

**T1 is the only self-firing trigger, so write it in AN2's test set, not as a note.** T2–T5 are
human-noticed; they are written here so the person who notices has the response ready instead of
re-deriving it.

### AN2d — **MAIN_ID duplication (new — not in the original plan)** ⚠️ **[R1]**
For essentially every bright star `MAIN_ID` *is* the Bayer string. After AN2 the `Bayer` key holds the
**same string**, so `desig_str` becomes:

```
* alf CMi, NAME Procyon, * alf CMi, …
```

on all four GUI banners, and `star_systems.designations` would carry the main_id a second time (the
`star_name` column already holds it). **A dedupe of MAIN_ID against the keyed slots is required** —
either suppress the keyed copy when it equals MAIN_ID, or drop MAIN_ID from the join. This is a
decision, not a detail: it changes what every panel renders.

### Verified safe
Exhaustive repo sweep (**run 2026-07-28, pre-AO**) confirms **nothing iterates the full
`designations` dict** — every keyed consumer uses `.get()` on a fixed name (`databases.py`
`_get_archive_query_params` / `_get_hwo_query_params` / the HWC + Exocat designation lookups,
`binary.gaia_source_id_from_designations`, `report.py:118` via the 5-key `_IDENTITY_DESIG_KEYS` at
`report.py:46`, several `main.py` sites, `gui/panels/nasa_exoplanet.py:91-92`). No `desig_str`
positional split anywhere. The one dict-values iteration is `calculators.py:284` (§AN0b). The G1
`designation_prefix` filter and the GCNS cross-match regexes are unaffected.

**Coordinates deliberately dropped, 2026-07-29.** AO shifted every `databases.py` line here by ~+93
and this census is a snapshot, not a contract. **Re-run the sweep at implementation time** — that is
cheaper and more trustworthy than maintaining ~14 line numbers across phases. The *conclusion*
(selective `.get()` everywhere, one dict-values iteration) was re-checked post-AO and still holds.

**⚠ AO added a consumer this sweep predates — `databases._simbad_gould_block` (`:146`), which reads
`designations["HD"]` via `_gould_catalog_number` (`:123`, called at `:180`).** It is `.get()`-shaped
so it cannot raise, and that is precisely the hazard: if AN0 changes what the `"HD"` slot *holds* —
a bare `102365` instead of `"HD 102365"` — every Gould lookup silently returns `None`, no test
fails, and the differential harness sees nothing because `designations` itself is unchanged. This is
the additive-and-inert class AO's own closing lesson names. **AN4 must pin it** (see AN4.5).

---

## 6. Part AN2e — Catalogued drift between the copies

Columns are the six copies of §2 (anchors re-verified 2026-07-29 post-AO).

| Behaviour | shared (copy 1) | databases (copy 2) | main.py opt-1 (copy 3) | main.py opt-50 (copy 5) | calculators (4) / main.py (6) |
|---|---|---|---|---|---|
| `key in …` guard | **yes** (`:248`,`:275`) | **no** (`:360`) | **no** (`:110`) | **no** (`:2279`) | no |
| empty case | `""` (`:279`) | `"N/A"` (`:365`) | `"N/A"` (`:146`) | `""` (`:2275`,`:2283`) | `""` (`calculators.py:284`) |
| MAIN_ID in join | no | **yes** (`:364`) | **yes** (`:139`) | no | n/a |
| MAIN_ID source | raw `str(result["main_id"][0])` (`:239`) | `_safe("main_id") or star_name` (`:263`) | raw | n/a | `_safe(…) or designation` (`:270`) |
| MAIN_ID missing → | `None` | **the query string** | `None` | n/a | n/a |

Per §1 lesson 1, each row is a decision. The `"N/A"` vs `""` split is the one most likely to be a
latent bug (a literal `"N/A"` reaching a DB column or a JSON consumer).

---

## 7. Part AN3 — Display-name tables

Two lookup tables are needed. **Ownership was settled 2026-07-28 when AO was sequenced first:**

1. **Greek abbreviation → letter** (`alf`→α … plus `alf01`→α¹) — **confirmed absent from the repo.**
   **Built here.** AO has no use for it.
2. **IAU 3-letter constellation → genitive** (`Cen`→Centauri, 88 entries) — **built by Phase AO**
   (`AO §2`), which needs it for its `display` contract (`66 G. Centauri`) and ships first.
   **AN3 consumes it; do not rebuild it.** It lives in `core/shared.py` beside the designation helpers.

*(The first draft had AN3 building both and AO depending on it. Pre-implementation review found that
AO's own output contract could not be emitted without the genitive table, making AO's "ships
independently" claim false. Inverting the ownership resolved it — see `AO §2` [R1].)*

### 7a. AN3 is not a blocker for the rest of AN

AN3 is **pretty-rendering only**. The raw SIMBAD string (`*  18 Eri`) is the identifier — stored
verbatim, round-trippable, and what AN0/AN1/AN2 capture and display. Turning it into `18 Eridani` is
polish. So **AN0 → AN1 → AN2 → AN2e can proceed whether or not AO has landed**; only AN3 waits, and it
is second-to-last in the order.

**[R8] Correction.** The original plan said the display helpers "don't exist in the repo." The
Greek/genitive tables indeed don't — but the **`* `/`NAME `/`V* `-stripping half already exists four
times**: `generate_star_map_html.py:28` (`short_name`, loop at `:30`), `gui/visualizations/plot_helpers.py:1869`,
`:2291` (both the identical `for prefix in ("NAME ", "* ", "V* ")` loop), and
`core/databases.py:665` (`_norm_oec_name`, loop at `:670`).
**All four will start receiving Bayer/Flamsteed strings after AN2** and must be audited — this is a
fifth-copy problem in the display layer, and it was not in scope before.

> **[A3] Correction to [R8] (2026-07-29, AN0→AN1 sweep).** [R8] described `_norm_oec_name` as
> **"`NAME ` only, no `* `/`V* ` handling"**. That is **wrong** — verified at `core/databases.py:665-670`,
> it loops `("V* ", "* ", "NAME ")`, case-insensitively, and then `re.sub`s out all whitespace,
> `-`, `_` and `*`. So it is the **one helper of the four that is already immune** both to the
> `* ` prefix and to D9's double space. It still differs in *shape* from the other three (it
> upper-cases and collapses whitespace, because it builds a normalised alias key rather than a
> display label) — that part of [R8] stands. Line numbers re-anchored: `:693` → `:665`.
>
> **Three further `NAME `-strippers and two `MAIN_ID` asterisk-strippers** belong to this family and
> were not in [R8]'s census: `core/databases.py:626` (`compute_hwc`), `main.py:1861` (`_query_hwc`),
> `core/report.py:117` (`_identity_data_star`); and `gui/panels/nasa_exoplanet.py:93`, `main.py:373`,
> `:566` (all `str(...).strip().lstrip("*").strip()`, which **does** handle D9's double space
> correctly). AN3's audit should cover all nine, not four.
>
> **D9 makes this concrete:** the three display strippers slice `name[len("* "):]` with no follow-up
> `.strip()`, so a Flamsteed id renders with a **leading space** (`" 18 Eri"`). Measured on the live
> DB: **796 `star_systems` rows already start with `*  ` (double space)** and misrender today, out of
> 2124 starting with `* `. AN3 fixes the strippers; the stored string stays verbatim.

**Scope guard:** the raw SIMBAD string (`*  18 Eri`) is the identifier — stored verbatim and
round-trippable. Pretty-rendering (`18 Eridani`) is a display-layer helper, never stored.

---

## 8. Part AN4 — Tests

**[R6] The plan's cited guard does not exist.** `tests/test_databases.py:24`
`test_normal_designation_is_byte_identical` lives in `class AdqlQuoteTest` and asserts
`databases._adql_quote("HIP 12345") == "HIP 12345"` — **SQL escaping, unrelated to designations.** The
name is a coincidence. **There is no existing byte-identical guard to extend.**

**Coverage reality — four of the six copies are untested:**

| Copy | Coverage |
|---|---|
| 1 `core/shared.py` | ✅ `tests/test_shared.py:97-186`; `databases._parse_designations_from_ids` indirectly at `tests/test_gcns.py:106-145` |
| 2 `databases.py` (`compute_simbad_lookup`'s inline map, `:315-365`) | ❌ **none.** `tests/test_databases.py:98` `_simbad()` builds a *synthetic* dict — never runs the parser. `tests/test_simbad_gcns_enrichment.py:92,117` assert only the `gcns` key. **Phase AO's 46 tests do not change this**: `tests/test_gould.py` + `test_gould_display.py` exercise `_simbad_gould_block`, the block *attached to* this function, and feed it hand-built designation dicts — the prefix loop above it is still never executed by any test |
| 3, 5, 6, 7 `main.py` | ❌ **zero — no test file imports `main.py` at all** |
| 4 `calculators.py:272-284` | ❌ **none.** `tests/test_calculators.py:104-118` covers only the Sol/Sun short-circuit (`calculators.py:213-221`), which returns before the parser; `tests/test_route_planning.py:40-43` and `tests/test_viz_phase_o.py:89-96` monkeypatch the whole function away |

**So the original plan's guard set covered the one call site already tested and none of the four that
weren't.** Required before AN0 touches anything:

0. **AN4.0 — capture the fixture corpus (added 2026-07-29; must precede AN4.1).** The harness replays
   real SIMBAD `ids` lists, which means those lists have to be **captured live once and committed**,
   before any refactor, or the baseline is unreproducible and the harness silently depends on SIMBAD
   uptime. This is a discrete step with a network dependency, not part of writing the harness.
   - Cover the shapes AN1 must classify (`* alf CMi` + its `A` component, `*  18 Eri`, `* alf01 Cen`,
     `V* eps Eri`, `** …`), the Gould anchors (HD 102365, HD 100623), and the ordinary catalogue
     cases (`NAME`-less stars, `BD±`, `LHS`, `Wolf`, Gaia-DR3-only, planet hosts for
     `Kepler`/`TOI`/`WASP`, and a masked-field star such as a white dwarf).
   - **`gouldDesignations.csv` is not a substitute.** It carries Bayer/Flamsteed *values* (AO4c) but
     not the raw pipe-separated `ids` strings the parsers consume — it validates AN1's classifier,
     it cannot drive the harness.
   - Commit the corpus as data. Keep the capture script beside it so a re-capture is reproducible,
     but the JSON is the artifact (the `gouldDesignations.csv` precedent).

1. A **differential harness** — capture `compute_simbad_lookup`'s full dict + `desig_str`,
   `shared._parse_designations`, and both narrow `desig_str` builders, for a few dozen real cached id
   lists. Replay after each AN0 commit; assert byte-identical modulo §6 decisions. **This, not an
   agent or a reviewer, is the primary safety net.**
2. First-ever unit tests for copies 2 and 4 (and 5 if in scope).
3. AN1: `**`-before-`* ` ordering pin; `*  18 Eri`→Flamsteed; `* alf CMi`→Bayer; `* alf01 Cen`→Bayer;
   the D6 component preference (`* alf CMi` wins over `* alf CMi A`); the AN0a synthetic-entry
   KeyError pin; and per **D2**, that `**`/`V*` ids produce **no key** while the classifier still
   returns `"Variable"` for a `V* ` string (so promoting it later needs no re-classification).
4. AN2d / **D3**: no duplicate token in `desig_str` — the keyed copy is suppressed when it equals
   MAIN_ID. Assert against a `* `-MAIN_ID star (22 of the 43 fixtures qualify) **and** a non-`* ` one,
   so the suppression can't be implemented as "always drop Bayer."
4b. **D5**: copy 2's empty case is `""`, not `"N/A"` — and the opt-50 discard rule still behaves
   (`desig_str == ""` on a star that captures nothing). Pin the deliberate MAIN_ID-missing
   divergence (shared → `None`, databases → the query string) rather than letting it drift.
4c. **AN2c-T1** — the self-firing D4 trigger: assert the **opt-50 builder** emits `Bayer`/`Flamsteed`
   for a fixture ids string. If this fails, the deferral is invalid because the code is wrong, not the
   data (see §5 AN2c-T).
5. **AN4.5 — the Gould producer/consumer pin (added 2026-07-29, post-AO).** Assert
   `compute_simbad_lookup(...)["gould"]` is non-null for **HD 102365** (`66 G. Centauri`) and
   **GJ 432 A** (`289 G. Hydrae`), before *and* after AN0, from a cached/synthetic ids list.
   `_simbad_gould_block` consumes `designations["HD"]` and expects the `"HD 102365"` string form
   (§5); a consolidation that changes that slot's shape returns `None` forever with **no test
   failure and no diff in the harness**, since `designations` itself is unchanged. A harness that
   only diffs outputs cannot see this — it is the one check that must assert a *downstream* effect.
   Generalise the idea: for each new AN key, verify some producer can actually emit the shape each
   consumer assumes (AO's closing lesson).

Run: `venv/bin/python -m pytest` (baseline **2174 passed, 1 skipped** — re-confirmed by a full run
2026-07-29 after Phase AO; the **2120** figure below predates it).

### AN4.0 + AN4.1 — BUILT 2026-07-29, and what the baseline immediately measured

Shipped: `tests/_capture_designation_fixtures.py` (one-shot, live) → `tests/fixtures/designation_ids.json`
(43 stars) → `tests/test_designation_harness.py` + `tests/fixtures/designation_golden.json`.
Suite **2181 passed, 1 skipped** (from 2174). Copies 2, 4 and 5 now have their first coverage of any
kind, and this is the first test in the repo that imports `main.py`.

**How to operate it — the four rules that are not obvious from reading the file.** *(Mechanics —
the fake-table shapes, the monkeypatch seams, the corpus format — live in the module docstring and
are not repeated here; that file is the source of truth for how, this is the source of truth for
when and why.)*

1. **Run it before touching anything, and treat red-on-arrival as a blocker.** A failing baseline
   before AN0 starts means the corpus or an unrelated change has already moved; diagnosing that
   mid-refactor is exactly the situation the harness exists to prevent.
2. **Regenerating the baseline is a decision, not a fix.** `AN_REGEN_GOLDEN=1` rewrites
   `designation_golden.json`. Do it **only** for an adjudicated §6/D-table change, and commit the
   regenerated file **in the same commit** as the code change so review sees both halves. A silent
   regen converts the harness into a rubber stamp — it will still pass, forever, having stopped
   asserting anything.
3. **A green harness is not always good news.** AN2e applies the D5 empty-case fix (`"N/A"` → `""`)
   and AN2 applies D3's dedupe — both are *intended* output changes. **If the harness stays green
   through those, the change did not land.** Expect red, inspect the diff, then regenerate per (2).
   The stars that should move are named: 22 for D3, and for D5 only a star that captures nothing at
   all (0 in the current corpus — so D5's diff is expected to be empty, which is itself the finding).
4. **Know what it structurally cannot catch, and compensate per key.** It diffs *outputs*. A change
   that leaves outputs identical while breaking a downstream consumer's assumed *input shape* is
   invisible to it — Phase AO shipped exactly that (green tests, working feature, dead branch).
   **AN4.5 is the counter-measure for the one known case** (Gould reading `designations["HD"]`);
   **add a sibling assertion for each new key AN introduces**, checking that some producer can
   actually emit the shape each consumer assumes.

**Four measurements over the corpus that bear directly on the open decisions — these are counts, not
estimates, and they replace guesswork in D3/D5:**

| Measured | Result | Bears on |
|---|---|---|
| copy 1 (`shared`) vs copy 5 (`main.py` opt-50) output | **identical on all 43/43** | **D1(a)** — copy 5 already emits exactly what shared does, so delegating it is a no-op refactor, not a behaviour change. The split-brain risk §2a warned about is *latent* (it appears only once AN2 adds keys), which makes fixing it now cheap |
| stars whose `MAIN_ID` is a `* `-form Bayer/Flamsteed string | **22 / 43 (51%)** | **D3 (AN2d)** — the duplication is not an edge case. Half the corpus would render `* alf CMi, NAME Procyon, * alf CMi, …` |
| stars with at least one `* ` id currently **discarded** | **18 / 43 (42%)** | The phase's actual payoff, quantified for the first time |
| stars hitting copy 2's `"N/A"` empty case | **0 / 43** | **D5** — the `"N/A"` vs `""` drift is real in code but never fires for a resolvable star. It can only surface for a star with no captured designation at all, so it is a latent bug, not an active one |

**A fifth divergence the harness surfaced, not previously in §6:** the copies disagree on **how they
index the SIMBAD table**. `shared._parse_designations` reads column-first
(`result["main_id"][0]`, astropy semantics); `databases` and `calculators` read row-first (`result[0]`
then `row[col]`). Harmless today — both work on a real astropy `Table` — but AN0 must not assume one
style when converging them, and any test double has to support both (the harness's does).

---

## 9. Part AN5 — Docs

`docs/star-databases.md` (SIMBAD section + opt-50 spec + AN2c) · `docs/integration.md` (AN2b) ·
`docs/testing.md` (new test files) · `CLAUDE.md` (one line) · **`IMPROVEMENT_PLAN.md` P4.6** (§1).

---

## 10. Revision summary — what review changed

| Tag | Original claim | Verified reality |
|---|---|---|
| **[R2]** | 4 parser copies | **6** (+1 hardcoded key list). `main.py:2229` is a full standalone parser; `main.py` imports nothing from `core.shared` |
| **[R4]** | Filter the shared map for the narrow copies | Reorders `desig_str` on opts 17/20/21 + 7 route planners. Must pass an explicit ordered key list |
| **[R5]** | `desig_str` order = `_CSV_DESIG_KEYS` | `compute_simbad_lookup` joins **MAIN_ID first**; a naive shared join drops it from all 4 banners |
| **[R1]** | Bayer absent from the dict | Present as MAIN_ID → **duplicate token** after AN2 (new part AN2d) |
| **[R6]** | Extend the existing byte-identical test | That test is `AdqlQuoteTest` — SQL escaping. **No such guard exists**; 4 of 6 copies untested |
| **[R7]** | Rebuild changes column text | Also changes **row count** via the `PLX …` discard rule |
| **[R3]** | *(absent)* | Adding a prefix entry before AN0 completes → **`KeyError`** in 3 unguarded copies. Hard ordering constraint |
| **[R8]** | Display helpers don't exist | The `* `-stripping half exists **4×** and will start receiving Bayer/Flamsteed strings |
| **[A1]** *(post-AO, 2026-07-29)* | Line numbers into `core/shared.py` + `core/databases.py` | Shifted by AO (+~52 / +~93). **All re-anchored and re-verified**; §2/§6/§7 now anchor on the enclosing block. `main.py` / `calculators.py` / the display helpers were unaffected and re-checked exact. §5's sweep is intentionally un-renumbered — **re-run it, don't trust it** |
| **[A2]** *(post-AO, 2026-07-29)* | §5's consumer census | AO added a **seventh** consumer, `_simbad_gould_block` → `designations["HD"]`. Additive, `.get()`-shaped, and **inert on a shape change** — invisible to both the test suite and AN4.1's harness. New pin **AN4.5** |

---

## 11. Review & verification checkpoints

**Already done — pre-implementation plan review (2026-07-28).** An adversarial agent sweep over this
plan against the source found the six errors in §10. Every finding was re-verified against the source
before being folded in. **This is why the plan is trustworthy now and was not before** — do not treat
§2's copy census or §8's coverage table as assumptions; they are measured.

### The hierarchy — what actually protects this phase

1. **The differential harness (AN4.1) is the primary safety net.** Not review, not an agent. Four of
   six call sites have *zero* coverage; a reviewer reading a diff cannot catch a reordered
   `desig_str` on a route-planner panel, but a replay harness catches it every run. **Build it first.**
2. **`/code-review` on the working diff** — for the change classes a harness can't see: error paths,
   import cycles, whether a fix introduced a new duplication.
3. **Agent sweeps** — only for questions requiring a *fresh census of the codebase*, where the answer
   might have changed since the plan was written.

### Checkpoint table

| Trigger | Tool | The specific question it answers |
|---|---|---|
| §2a decided | — | Decision, not code. No review |
| **Before AN0 starts** | harness (AN4.1) | Does a replayable byte-identical baseline exist for all in-scope call sites? **AN0 must not start without it** |
| **After AN0 lands** | **`/code-review`** — consider **`/code-review ultra`** | Highest-value single spend in the phase. AN0 is a behaviour-preserving refactor across up to 6 sites with 4 untested; the harness covers output equivalence, review covers everything else (error contracts, the §6 drift decisions, import cycles) |
| **AN0 → AN1 boundary** | **agent sweep (Opus)** | Two questions: (a) did AN0's *actual* landed shape change how AN1's classifier integrates, versus the pre-pass §4 assumes? (b) is the six-copy census still complete — did the refactor leave a straggler, or reveal a seventh? |
| After AN1 lands | **`/code-review`** | The ordering-bug class specifically: `**`-before-`* `, component-suffix determinism, the AN0a `KeyError` constraint holding |
| After AN2 | fold into the AN1 review | AN2d (MAIN_ID dedupe) is a visible behaviour change — verify against the harness, not by reading |
| **During AN3** | **agent sweep (Sonnet)** | **New surface, found only by the pre-implementation review** (§7 [R8]): four existing `* `-stripping display helpers will start receiving Bayer/Flamsteed strings. Which need changes — and are there others the review didn't reach? |
| AN2e, AN4 rest, AN5 | — | Self-verifying: decisions, tests, docs |

**Total: 2 agent sweeps + 2–3 `/code-review` passes.** Not one per part — most part boundaries here
have no real coupling, and plan churn has its own cost.

### Sequencing rule

**`/code-review` → apply fixes → *then* refresh this plan.** Refreshing against code that is about to
change from review findings wastes the pass.

### Definition of done, per part

A part is not finished until this plan is updated to match what was actually built — corrections
inline and visible, per `completed_plans/README.md` and the `SPECTRAL_CLASS_PLAN.md` precedent. That
update is done by whoever built the part, **not** delegated: an agent would have to reconstruct
context the builder already holds. Agents are spent on *independence*, not on knowledge.

---

## 12. Part / task summary

| Part | Title | Risk | Notes |
|---|---|---|---|
| **2a** | **Decide `main.py` scope (D1)** | — | ✅ **DECIDED (a), 2026-07-29.** All of D1–D6 are now settled — see the decisions block at the top |
| **AN0** | Consolidate onto `core.shared` | **High** | ✅ **BUILT 2026-07-29** — see §3. Zero output change; golden baseline **not** regenerated. `/code-review` passed (3 low-severity findings applied). Suite **2183 passed, 1 skipped** |
| **AN1** | `* ` classifier | Medium | ✅ **BUILT 2026-07-29** — `_classify_star_id` + D8 precedence in `core/shared.py`, wired into `_match_designations`; `tests/test_designation_ids.py` (17 tests). **Output-inert by construction** (the keys arrive in AN2), so the AN4.1 harness stayed green and the golden baseline was not regenerated. ~~`**`-before-`* ` is load-bearing~~ — **false, see [A4]** |
| AN2 | Key insertion + ripple | **Medium** *(was Low)* | AN2d duplication is a real behaviour change — **51% of stars** (D3). Carries **AN2c-T1**, the self-firing D4 trigger |
| AN2e | Adjudicate the §6 drift | Medium→**Low** | ✅ **D5 decided** — fix the empty case to `""` (fires on 0/43, so the change is safe *and* the bug is latent), keep the rest, pin the MAIN_ID divergence |
| AN3 | Greek table (genitive **inherited from AO**) | Low→**Medium** | +4 display helpers to audit (§7 [R8]) |
| **AN4.0** | **Capture the fixture corpus (live SIMBAD)** | Low | ✅ **BUILT 2026-07-29** — `tests/_capture_designation_fixtures.py` → `tests/fixtures/designation_ids.json`, 43 stars / 27 Bayer / 20 Flamsteed / 35 `**` / 14 `V*` ids |
| **AN4.1** | **Differential harness** | Medium | ✅ **BUILT 2026-07-29** — `tests/test_designation_harness.py` + `designation_golden.json`. First coverage for copies 2/4/5; includes the AN4.5 Gould pin. Suite **2181 passed, 1 skipped** |
| AN4 | Tests | **High** | Differential harness first; 4 sites have no coverage at all. **+ AN4.5** — the Gould producer/consumer pin the harness structurally cannot catch |
| AN5 | Docs | Low | |

**Order:** ~~§2a decision~~ ✅ → ~~**AN4.0** (fixture capture)~~ ✅ → ~~AN4.1 (harness)~~ ✅ →
~~AN0 (complete, all in-scope copies)~~ ✅ → ~~AN1~~ ✅ → **AN2 ← NEXT** → AN2e → AN3 → AN4 rest → AN5.

**All decisions (D1–D9) are settled, the harness is green, AN0 has landed with its `/code-review`
pass applied, and the §11 AN0 → AN1 agent sweep has run** (findings in **§4a**; it added D7/D8/D9 and
corrected §7 [R8]). **AN1 is unblocked.**

**Three things AN1 must carry from §4a, none of which §4 currently says:**

1. The classifier pre-pass must **re-spell the `key in desig` guard itself** — AN0a's protection is
   not a function-level invariant, and omitting it is a `KeyError` on the narrow path.
2. **D8 needs a replace-if-better pass**, not a pre-pass. `_match_designations` is structurally
   first-match-wins, and Sirius already contradicts Procyon inside the current corpus.
3. Add a **narrow-path classifier test**. The existing synthetic-entry pin covers the prefix loop
   only, so it cannot catch either of the above.

**The harness precedes AN0.** It cannot be built after the refactor it exists to verify. **And the
fixtures precede the harness** — they need live SIMBAD, so capturing them is its own step, done
before any code moves.
