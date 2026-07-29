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
> both `databases.py:304` `keys_order`/`:312` `prefix_map` **and** the shared `_CSV_PREFIX_MAP`), so
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
> **Baseline moved:** the suite is now **2174 passed, 1 skipped** (§8 cites 2120). AN's differential
> harness (AN4.1) must be built against the current tree, and `tests/test_gould.py` /
> `test_gould_display.py` are new files it should not be surprised by.

> **Revision note.** The first draft of this plan was materially wrong in **eight** places, all found
> by pre-implementation review and all verified against the source before this rewrite. Corrections
> are marked **[R1]**…**[R8]** inline and summarized in §10. Per the house convention
> (`completed_plans/README.md`, `SPECTRAL_CLASS_PLAN.md`), the corrected numbers are the load-bearing
> record and the original errors are kept visible rather than quietly overwritten.

---

## ⚠ DECISIONS REQUIRED BEFORE STARTING

**D1 blocks the phase.** It sets AN0's scope — a three-site or a six-site refactor — and it touches a
standing policy, so it is not an implementer's call. The rest gate individual parts.

| # | Decision | Gates | Options | Recommendation |
|---|---|---|---|---|
| **D1** ✅ **DECIDED (a), 2026-07-29** | **Does `main.py` come along?** (§2a — full options table there) | **AN0 — the whole phase** | **(a)** Exempt `main.py` per policy **except copy #5** (CLI opt 50). **(b)** Full consolidation, all 6 copies. **(c)** Strict policy — leave all of `main.py` | **(a).** `IMPROVEMENT_PLAN.md` ground rule 1 says don't touch `main.py` feature functions (your 2026-07-04 call), but copy #5 writes the **same `star_systems.designations` column** as GUI opt 50 — leaving it makes the two entry points write different content into one column. **(c) is not acceptable** unless CLI opt 50 is formally retired |
| **D2** | **`V*` and `**` handling** (§4, AN1a) | **AN1** | **(a)** Drop both. **(b)** Drop `**`, capture `V*` as a `"Variable"` key | **(a) drop both.** `**` is a double-*system* id, not a name for this star. `V*` is a genuine designation but redundant with the Bayer form for most stars — widens the `query.py` contract for little gain. Revisit separately if wanted |
| **D3** | **MAIN_ID duplication** (§5, AN2d) | **AN2** | **(a)** Suppress the keyed copy when it equals MAIN_ID. **(b)** Drop MAIN_ID from the `desig_str` join entirely. **(c)** Accept the duplicate | **(a).** (b) removes MAIN_ID from all four GUI banners — a visible regression. (c) renders `* alf CMi, NAME Procyon, * alf CMi, …`. This changes what every panel displays, so it is a product call, not a cleanup |
| **D4** | **Opt-50 rebuild: defer or gate?** (§5, AN2c) | **AN2** | **(a)** Defer — lookup surfaces get the names now, DB-backed surfaces catch up at the next rebuild. **(b)** Gate the phase on a full opt-50 rebuild (17 SIMBAD queries, ~238k rows, hours) | **(a) defer.** A stale `designations` column is already an accepted state in this repo (the NAME-first change left the same debt). **Note:** the rebuild changes **row count**, not just column text — re-measure the `PLX …` discard delta when it happens |
| **D5** | **Adjudicate the drift table** (§6) | **AN2e** | Five behavioural differences between the copies — the `key in …` guard, `"N/A"` vs `""` empty case, MAIN_ID in the join, MAIN_ID source, MAIN_ID-missing semantics. Each is keep-or-fix | **Per §1 lesson 1, judge each on merit — do not preserve drift reflexively.** P4.6 tried that and the preserved drift *was* the bug. The `"N/A"` vs `""` split is most likely a latent bug (a literal `"N/A"` reaching a DB column or JSON consumer) |
| **D6** | **Component-suffix preference** (§4, AN1b) | AN1 | Prefer `* alf CMi` over `* alf CMi A`, or take first match | **Prefer component-less.** Low stakes, but first-match-wins is non-deterministic across SIMBAD releases. Effectively an implementer's call |

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
`core.shared._CSV_DESIG_KEYS` — true of the **opt-50 builder** path (`databases.py:1234`, `:1240`
delegate), but **the inline map inside `compute_simbad_lookup` (`databases.py:222-261`) was never
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

| # | Location | Serves | State |
|---|---|---|---|
| 1 | `core/shared.py:35-71` — `_CSV_PREFIX_MAP` + `_CSV_DESIG_KEYS` | opt-50 builder via `databases.py:1240`; `shared._parse_designations` | canonical (P4.6) |
| 2 | `core/databases.py:222-261` | **`compute_simbad_lookup`** — GUI SIMBAD panel **and** `query.py simbad-lookup` | inline duplicate; module imports shared names at `:15-16`, uses them at `:1234`/`:1240` but **not here** |
| 3 | `main.py:60-114` | CLI opt 1 | inline duplicate *(original plan cited `60-105`; the match loop is `108-112`, outside that range)* |
| 4 | `core/calculators.py:271-284` | opts 17/19/20/21 + all seven route planners | **narrow** — `NAME/HD/HR/GJ/Wolf` |
| **5** | **`main.py:2229` `_CSV_PREFIX_MAP` + `:2261` `_CSV_DESIG_KEYS` + `:2268-2283` parser** | **CLI opt 50** via `main.py:2321` → `_run_simbad_csv_query` → `query_star_systems_csv` (`main.py:2390`, menu `:5516`) | **complete standalone re-implementation** |
| **6** | **`main.py:2693-2711`** | **CLI opts 17/19/20/21** via `_lookup_star_for_distance` (`main.py:2642`; call sites `:2737`, `:2906`, `:3259`) | second narrow `NAME/HD/HR/GJ/Wolf` map |
| 7 | `main.py:139-144` | CLI opt 1 "STAR DESIGNATIONS:" banner | not a prefix map — a hardcoded 20-key `keys_order` used only to build the display join. **Must be edited in AN2 or the CLI banner silently omits the new keys.** |

**Verified: `main.py` imports nothing from `core.shared`.** The original plan's claim that
"`main.py:2268` already delegates" was **false** — `main.py:2268` reads `main.py`'s *own* locals.

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

**This decision gates AN0's scope and must be made before work starts.**

---

## 3. Part AN0 — Consolidate onto `core/shared.py`

**Goal:** the copies in scope (per §2a) delegate to `core.shared`; copies 4 and 6 stay narrow but stop
re-typing the map.

### AN0a — ordering constraint (hard) **[R3]**

Copies 2, 3 and 5 match with **no `key in designations` guard** (`databases.py:267`, `main.py:110`,
`main.py:2279`), unlike shared (`shared.py:186`, `:213`). **The moment a `* `-shaped entry is added to
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
iteration**, so output order is `desig_found`'s insertion order, set at `calculators.py:271`:
**`NAME, HD, HR, GJ, Wolf`**. Filtering `shared._CSV_PREFIX_MAP` (order `NAME, GJ, HD, HIP, HR, Wolf`)
yields **`NAME, GJ, HD, HR, Wolf`** — GJ moves 4th→2nd, HD 2nd→3rd.

Procyon's `desig_str` would change from
`NAME Procyon, HD 61421, HR 2943, GJ 280` → `NAME Procyon, GJ 280, HD 61421, HR 2943`
on every consumer: `gui/panels/distance_stars.py:106-108`, `gui/panels/travel_time_stars.py:114-116`,
`gui/panels/route_planning.py:258`, `core/calculators.py:1620`.

**Fix:** pass an explicit ordered key list; never derive order from the map. Note copy #6
(`main.py:2708-2711`) re-loops an explicit `("NAME","HD","HR","GJ","Wolf")` tuple, so it is *not*
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

`databases.py:271` joins over `keys_order`, whose **first element is `MAIN_ID`** (`:222`).
`shared.py:216` joins over `_CSV_DESIG_KEYS`, which has **no `MAIN_ID`** (`:67-71`).

So a shared `build_desig_str(designations, keys)` is byte-identical **only** if `compute_simbad_lookup`
passes `["MAIN_ID"] + _CSV_DESIG_KEYS`. Passing `_CSV_DESIG_KEYS` silently drops MAIN_ID from **every**
GUI banner (`simbad.py:157`, `star_regions.py:396`, `nasa_exoplanet.py:61`, `catalogs.py:200`).

### AN0d — the proposed golden test is invalid as written **[R6]**

The original plan proposed asserting `compute_simbad_lookup` and `shared._parse_designations` produce
the same dict. **They legitimately do not.** On a masked/blank `main_id`:

- shared (`shared.py:177`) → `MAIN_ID` stays `None`
- databases (`databases.py:169`, `:228`) → `MAIN_ID` becomes **the user's query string**, set unconditionally

That is a real contract difference, wire-visible through `query.py:78`. The equivalence test must
either exclude `MAIN_ID` or assert the divergence deliberately.

**Acceptance for AN0:** no output change on any in-scope call site, except where §6 identifies a
difference judged to be a bug — each such case decided explicitly and recorded here.

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

1. `startswith("** ")` → `None`. **Must be tested before `* `** — `** LDS 6248A` also satisfies
   `startswith("* ")`. Load-bearing ordering; pin it.
2. `startswith("V* ")` → `"Variable"` (see AN1a).
3. `startswith("* ")` → strip, split, token 0 all-digits → `"Flamsteed"`, else `"Bayer"`.
4. else → `None`, fall through to the prefix map.

Integrate as a **pre-pass** in the shared loop so all in-scope call sites inherit it from AN0.

**AN1a — decision:** `**` → drop (recommended). `V*` → drop in AN1, revisit separately.
**AN1b — component suffixes:** prefer the component-less form (`* alf CMi` over `* alf CMi A`);
first-match-wins is non-deterministic across SIMBAD releases. Pin with Procyon's real id list.

---

## 5. Part AN2 — Key insertion and the ripple

Add `"Bayer"` / `"Flamsteed"` to `_CSV_DESIG_KEYS` / `keys_order` — **and to `main.py:139-144`**
(copy #7) if `main.py` is in scope.

### AN2-SAO — a **third** candidate key, inherited from Phase AO (recorded 2026-07-29)

**Decide this alongside `Bayer`/`Flamsteed`, not separately** — it is the same insertion, the same
ripple, and the same review pass.

AO built an SAO fallback join for its Gould lookup and `/code-review` found it **unreachable**:
`designations` carries no `"SAO"` key, in *any* copy — absent from `databases.py:304` `keys_order`
/ `:312` `prefix_map` **and** from the shared `_CSV_PREFIX_MAP`. AO removed the dead branch rather
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
(`databases.py:1281`, `main.py:2324`) is:

```python
if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":
```

Adding keys makes `desig_str` non-empty for stars that previously captured nothing, so rows previously
**discarded** are now **kept**. The next opt-50 rebuild therefore changes **row count**, not merely
column text. (Live measurement says `PLX …` main_ids are currently zero, so the practical delta is
likely nil — but the claim in the plan must be correct, and this must be re-measured at rebuild time.)

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
Exhaustive repo sweep confirms **nothing iterates the full `designations` dict** — every keyed
consumer uses `.get()` on a fixed name (`databases.py:300-322`, `:494`, `:551-553`, `:737-740`,
`:1885`, `binary.py:206`, `report.py:118` via the 5-key `_IDENTITY_DESIG_KEYS` at `report.py:46`,
`main.py:290-324`, `:373`, `:566`, `:710-712`, `:1856-1859`, `gui/panels/nasa_exoplanet.py:91-92`).
No `desig_str` positional split anywhere. The one dict-values iteration is `calculators.py:284`
(§AN0b). The G1 `designation_prefix` filter (`databases.py:3344-3352`) and the GCNS cross-match
regexes are unaffected.

---

## 6. Part AN2e — Catalogued drift between the copies

| Behaviour | shared | databases | main.py:60 | main.py:2268 | calculators / main.py:2693 |
|---|---|---|---|---|---|
| `key in …` guard | **yes** (`:186`,`:213`) | **no** (`:267`) | **no** (`:110`) | **no** (`:2279`) | no |
| empty case | `""` (`:217`) | `"N/A"` (`:272`) | `"N/A"` (`:146`) | `""` (`:2283`) | `""` |
| MAIN_ID in join | no | **yes** | **yes** (`:139`) | no | n/a |
| MAIN_ID source | raw `str(result["main_id"][0])` | `_safe("main_id") or star_name` | raw | n/a | `_safe(…) or designation` |
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
times**: `generate_star_map_html.py:30`, `gui/visualizations/plot_helpers.py:1869`, `:2291`,
`core/databases.py:598` (`_norm_oec_name`). **All four will start receiving Bayer/Flamsteed strings
after AN2** and must be audited — this is a fifth-copy problem in the display layer, and it was not in
scope before.

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
| 2 `databases.py:222-272` | ❌ **none.** `tests/test_databases.py:98` `_simbad()` builds a *synthetic* dict — never runs the parser. `tests/test_simbad_gcns_enrichment.py:92,117` assert only the `gcns` key |
| 3, 5, 6, 7 `main.py` | ❌ **zero — no test file imports `main.py` at all** |
| 4 `calculators.py:271-284` | ❌ **none.** `tests/test_calculators.py:104-118` covers only the Sol/Sun short-circuit (`calculators.py:213-221`), which returns before the parser; `tests/test_route_planning.py:40-43` and `tests/test_viz_phase_o.py:89-96` monkeypatch the whole function away |

**So the original plan's guard set covered the one call site already tested and none of the four that
weren't.** Required before AN0 touches anything:

1. A **differential harness** — capture `compute_simbad_lookup`'s full dict + `desig_str`,
   `shared._parse_designations`, and both narrow `desig_str` builders, for a few dozen real cached id
   lists. Replay after each AN0 commit; assert byte-identical modulo §6 decisions. **This, not an
   agent or a reviewer, is the primary safety net.**
2. First-ever unit tests for copies 2 and 4 (and 5 if in scope).
3. AN1: `**`-before-`* ` ordering pin; `*  18 Eri`→Flamsteed; `* alf CMi`→Bayer; `* alf01 Cen`→Bayer;
   component preference; the AN0a synthetic-entry KeyError pin.
4. AN2d: no duplicate token in `desig_str`.

Run: `venv/bin/python -m pytest` (baseline **2174 passed, 1 skipped** as of 2026-07-29, after Phase AO; the **2120** figure below predates it).

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
| **2a** | **Decide `main.py` scope (D1)** | — | **Gates everything.** Option (a) recommended — see the decisions block at the top |
| AN0 | Consolidate onto `core.shared` | **High** | AN0a ordering · AN0b explicit key order · AN0c MAIN_ID · AN0d test validity |
| AN1 | `* ` classifier | Medium | `**`-before-`* ` is load-bearing |
| AN2 | Key insertion + ripple | **Medium** *(was Low)* | AN2d duplication is a real behaviour change |
| AN2e | Adjudicate the §6 drift | Medium | Per P4.6's lesson, not all drift is worth preserving |
| AN3 | Greek table (genitive **inherited from AO**) | Low→**Medium** | +4 display helpers to audit (§7 [R8]) |
| AN4 | Tests | **High** | Differential harness first; 4 sites have no coverage at all |
| AN5 | Docs | Low | |

**Order:** §2a decision → AN4.1 (harness) → AN0 (complete, all in-scope copies) → AN1 → AN2 → AN2e →
AN3 → AN4 rest → AN5.

**The harness precedes AN0.** It cannot be built after the refactor it exists to verify.
