# PHASE CR-20 PLAN (v1) — multiplicity **verdict honesty** (additive tri-state `multiplicity_class`/`bound_multiple`) + **astrometric-backbone completeness** (persist Gaia PM into `gcns_stars`)

Baseline: CR-19 `origin/main c2de72e`. Spec: `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR20-multiplicity-verdict-honesty-and-nongcns-bound-coverage.md` + `cr20-handoff-kit.md`. Channel Q&A: MSG 214–217. **R3 (Gaia-missing + orbit-less bound coverage) is a SEPARATE CR-21 — NOT this CR.**

## 0. Summary

Two additive, byte-identical-safe components:
- **C1 — verdict honesty (R1+R2).** Add a top-level tri-state **`multiplicity_class ∈ {"bound","optical","unknown"}`** + convenience **`bound_multiple`** (`true`/`false`/`null`) on **both** `multiplicity` (`binary.multiplicity_summary`) **and** `dossier --sections multiplicity` (`report._multiplicity_data_star` → `_augment_gcns_multiplicity`), computed by **one shared classifier** in `core/binary.py`. `is_multiple` and every existing field/number stay **byte-identical** — CR-20 only *adds* keys; nothing flips.
- **C2 — astrometric backbone.** Persist `pmra, pmdec, pmra_error, pmdec_error, ruwe` into `gcns_stars` from the `gcns.main` GAVO query. Schema-additive; **no existing subcommand output changes** (readers use the explicit `_GCNS_ROW_COLS`, which does **not** gain the PM columns). Population via a **targeted `ALTER` + PM-only backfill** (not a full opt-58 re-ingest — that would rebuild the resolved-system tables and risk shifting the CR-18 anchors).

## 0.1 Locked contract (MSG 214 spec + MSG 216/217 answers)

- **D1 = additive/monotonic (LOCKED, Greg 2026-09-03).** No verdict flips; whole CR-13+CR-14+CR-15.4+CR-16 battery + 4 CR-18 anchors byte-identical.
- **Q1 key names — CONFIRMED verbatim:** `multiplicity_class` / `bound_multiple`, exact strings.
- **Q2 single star — CONFIRMED present-but-null:** `is_multiple:false` → `multiplicity_class:null`, `bound_multiple:null` (never omitted).
- **Q3 truth table — CONFIRMED** (see §3), with **Guardrail 1** (SB/eclipsing trigger = a NARROW confirmed-binary otype set; `RS*`/`El*`/`BY*` rotational/ellipsoidal variables + `?`-candidates + `EP*` planet-eclipse all EXCLUDED) and **Guardrail 2** (classify on an actual fitted SOLUTION in `bo["solutions"]`, never on an available `binary_orbit_routes` entry).
- **Q4 C2 population — CONFIRMED targeted backfill;** shared `data/space_app.db` on this box (APP runs the backfill as part of delivery); WB verifies PM by direct sqlite; PM not surfaced in any CR-20 subcommand (backbone for CR-21). Operational note: the DB is machine-local (gitignored) — the backfill fulfills CR-20 for THIS box; another machine gets PM only when the git-synced extended ADQL/INSERT is re-run there.

## 0.2 Plan-review integration (3 adversarial review agents, 2026-09-03)

Three reviewers (classifier-correctness, byte-identity, code-grounding) hardened this plan. Confirmed sound: the tri-state truth table + ordering + all 5 anchor traces; both guardrails (narrow `_BOUND_OTYPES` with no `sb_flag` leak; solution-not-route); C1 two-keys-only additivity + no JSON scratch-key leak; C2 `_GCNS_ROW_COLS` sole reader source with **no `SELECT *`** anywhere + backfill isolation preserving the CR-18 resolved-system tables; every cited line/signature accurate. Integrated fixes (marked `REVIEW-FIX` inline):
1. **Planet-class cross-path bug (3× flagged)** — bake the planet-class exclusion into `is_orbit_solution` (§2.1) so the summary path matches the dossier's planet-filtered `stellar`; a planet-only NSS host (GJ 876) reads `unknown`/`optical`, never `bound`, on both paths. + a GJ 876 test (§7).
2. **Present-but-null hole (2× flagged)** — default the two keys to `None` in the `data = {...}` literal (§2.3) so the `if not star`/`--star ""` early return can't omit them.
3. **Drop the `_blocks_multiplicity` display row** — it would change the markdown/html dossier document string (byte-identity failure); the JSON carries the keys (§2.3).
4. **Drop the `query.py gcns-pm-backfill` subcommand** — no precedent (GCNS/dust writes are CLI/GUI-only); the backfill is a core function invoked directly for delivery (§2.6).
5. **Backfill precision** — `executemany` tuple with `source_id` LAST; single-key `gcns_meta` UPSERT; PM columns at END of CREATE TABLE (fresh ≡ migrated column order); verify live GAVO column names before the delivery pull (§2.4/§2.6).
6. **`**` DROPPED from `_BOUND_OTYPES`** — WB MSG 219 ruled drop (converged with both reviewers); final set `{SB*, EB*, Al*, bL*, WU*}`, a bare-`**` star reads `unknown`/`optical`. No open otype questions.

## 0.3 Post-CP3 refinement — close-binary hint blocks `optical` (WB MSG 222, Greg approved)

After the CP-checkpoints + WB's GREEN re-gate on `145fb68`, WB/Greg approved one refinement (my flagged F5 edge): at the **`optical`** branch, a close-binary otype **hint** ∈ **`_HINT_OTYPES = {SB?, EB?, RS*, El*}`** (spectroscopic/eclipsing candidates + rotational/ellipsoidal variables — they set `is_multiple`/`sb_flag` but are NOT confirmed-bound) downgrades **`optical` → `unknown`** (a hint may be an unresolved bound close companion, so a consumer must not read "optical / no bound companion"). The wide `**`/`**?` do NOT block (same channel as the GCNS optical pair). Implemented as `binary.is_close_binary_hint_otype` + a `has_close_binary_hint` arg on `classify_multiplicity`, wired into all three call sites; +7 tests (41 → **48**); anchors unmoved (StKM 1-79 → `optical`, ε Eri → `unknown`). Commit `145fb68` → **`fea47bd`** (C1-only + docs). See `docs/integration.md` CR-20 block.

## 1. Current state + call map (code-grounded, HEAD `c2de72e`)

**C1 — the two paths and their signal sources.**
- `binary.multiplicity_summary` (`core/binary.py:387`) builds `out` (`:522`) with `is_multiple`/`n_components`/`components`/`sb_flag`/`sources`. It has in scope: `bo = binary_orbit(...)` (`:426`, per-solution `source`), `gcns_comps` (`:423`, incident GCNS pairs with tri-state `bound`), `otype_block` (`:414`, SIMBAD otype).
- `report._multiplicity_data_star` (`core/report.py:651`) builds `data`; `_augment_gcns_multiplicity` (`:624`) is the **single choke point** called before every star-bearing return (`:667,674,682,739`) — it holds `comps` (recomputed via `binary.gcns_bound_companions`). The final return (`:739`) has `stellar` (the non-planet `binary_orbit` solutions) and `data["otype"]`.
- **The orbit-vs-bare-catalog discriminator lives only in `bo["solutions"][].source`.** `_wds_orb6_solutions` (`:587`): `source=="wds"` = a bare WDS catalog double (`period_d:None`, `companion:None`) — **not** an orbit (ε Eri); `source=="orb6"` = a Sixth-Catalog fitted visual orbit; `sb9`/`gaia-nss*` = spectroscopic/astrometric orbits. `multiplicity_summary._add` (`:429`) collapses BOTH `wds` and `orb6` → `basis:"visual"`, so the component basis alone cannot tell them apart → **classify from `bo["solutions"]`, not from `components[]`**.
- The SIMBAD otype→multiplicity map (`core/databases.py:401`): `_OTYPE_SPECTROSCOPIC = {"SB*","SB?","RS*","El*"}` → `sb_flag:true,is_multiple:true`; `_OTYPE_ECLIPSING = {"EB*","Al*","bL*","WU*","EB?"}`; `_OTYPE_VISUAL_MULTIPLE = {"**","**?"}`; else default `sb_flag:false,is_multiple:false`. **`RS*`/`El*` already carry `sb_flag:true` — unchangeable (byte-identical)** — so the C1 bound-trigger keys on a NEW narrow set, NOT the broad `sb_flag`. `BY*` (ε Eri) is in NO set → default → `sb_flag:false`.
- **Dossier→JSON:** `build_system_dossier` (`report.py:1348-1350`) emits `"data": {k: data[k] for k in rendered}` — the section `data` dict verbatim. ⇒ adding keys to `data` surfaces them in `dossier --fmt json`; **any scratch/private key in `data` would ALSO leak** ⇒ compute the class without leaving intermediates in `data`.

**C2 — the ingest + schema.**
- `_GCNS_MAIN_ADQL` (`databases.py:2397`) selects 15 columns; the GAVO `gcns.main` table also exposes `pmra,pmdec,pmra_error,pmdec_error,ruwe` (never SELECTed). Insert tuple built at `:2757` (main) / `:2788` (missing); INSERT column list at `:2817` (explicit — no `SELECT *`). `_GCNS_ROW_COLS` (`:2911`) is the explicit reader column list used by every GCNS reader (`:2968,3017,3230,3416,3452,3999`).
- Schema `gcns_stars` (`core/db.py:238`); idempotent `_migrate_schema` ALTER list (`:433`) — CR-18 added `system_id`/`n_components` here; same template for the 5 PM columns.

## 2. Design (the "how" — APP owns it)

### 2.1 C1 — the shared classifier (`core/binary.py`, new)

```python
# Confirmed-binary SIMBAD otypes = an affirmative BOUND signal on their own (a spectroscopic /
# eclipsing / visual binary is definitionally a bound pair). Deliberately NARROWER than
# databases._OTYPE_SPECTROSCOPIC (which also carries RS*/El* rotational/ellipsoidal VARIABLES under
# sb_flag:true) — those assert a variability mechanism, not a confirmed orbit, so they must NOT read
# `bound` (WB CR-20 Guardrail 1). Candidates (SB?/EB?/**?), EP* (star eclipsed by its PLANET, not a
# stellar binary), AND the bare `**` "double or multiple" (catalog STATUS, not a boundedness
# determination — WB MSG 219, converged with both reviewers) are excluded too. Detection-of-orbital-
# motion binaries only: a bare-`**` star reads `unknown` (or `optical` under a GCNS all-bound=0).
_BOUND_OTYPES = frozenset({"SB*", "EB*", "Al*", "bL*", "WU*"})
_ORBIT_SOURCES = frozenset({"sb9", "orb6"})

def is_bound_otype(otype):        # confirmed-binary otype (affirmative bound signal)
    return (otype or "") in _BOUND_OTYPES

def is_orbit_solution(sol):       # a fitted STELLAR orbit = an affirmative bound signal (Guardrail 2: a solution, not a route)
    src = (sol or {}).get("source") or ""
    if not (src in _ORBIT_SOURCES or src.startswith("gaia-nss")):
        return False
    comp = (sol or {}).get("companion")                 # REVIEW-FIX (3× flagged): exclude a PLANET-class NSS/SB
    return not comp or comp.get("class") != "planet"    # "orbit" (e.g. GJ 876) — a planetary orbit is NOT a stellar-multiplicity bound signal

def classify_multiplicity(is_multiple, *, has_fitted_orbit, has_binary_otype, gcns_comps):
    """CR-20 additive tri-state bound-vs-optical verdict honesty → (multiplicity_class, bound_multiple).
    ("bound",True)  any GCNS pair bound=1 OR a fitted orbit OR a confirmed-binary otype.
    ("optical",False) is_multiple AND a GCNS determination (>=1 incident pair, ALL bound=0) AND no bound signal.
    ("unknown",None)  is_multiple but boundedness undetermined (no GCNS pair; bare visual/wds; candidate/variable otype).
    (None,None)       not multiple (single star) — present-but-null on every output.
    Never consulted for is_multiple/sb_flag/any existing field (additive-only)."""
    if not is_multiple:
        return None, None
    has_gcns_bound = any(c.get("bound") is True for c in (gcns_comps or []))
    if has_gcns_bound or has_fitted_orbit or has_binary_otype:
        return "bound", True
    if gcns_comps and all(c.get("bound") is False for c in gcns_comps):   # GCNS determined unbound
        return "optical", False
    return "unknown", None
```

Notes: `bound` uses `is True` / `optical` uses `all(... is False)`, so a tri-state `bound` of `None` never forces either. **α Cen reaches `bound` via its SB9 orbit with an EMPTY `gcns_comps`** — its Gaia-missing primaries make `gcns_bound_companions` return `(None, [])` (there is NO `bound=None` entry). The `bound=None`-*entry* path (a GCNS pair whose boundedness is unknown) is a distinct case exercised ONLY by the synthetic "mixed True/None → bound" and "mixed False/None → unknown" unit tests (§7), NOT by the α Cen anchor. (Review-corrected prose.)

### 2.2 C1 — `multiplicity_summary` wiring (`core/binary.py`)

Just before the `out = {...}` literal (`:522`), compute and inject the two keys (all inputs in scope):
```python
otype = otype_block.get("otype") if otype_block else None
_solutions = bo.get("solutions") or [] if isinstance(bo, dict) else []
mc, bm = classify_multiplicity(
    is_multiple,
    has_fitted_orbit=any(is_orbit_solution(s) for s in _solutions),
    has_binary_otype=is_bound_otype(otype),
    gcns_comps=gcns_comps)
```
Add `"multiplicity_class": mc, "bound_multiple": bm,` into the `out` dict literal (near `is_multiple`). No existing key/value touched. `is_orbit_solution` now excludes planet-class internally (§2.1), so this scan over the raw `bo["solutions"]` matches the dossier's planet-filtered `stellar` → cross-path parity (a planet-only NSS host reads `unknown`/`optical`, never `bound`, on BOTH paths).

### 2.3 C1 — dossier wiring (`core/report.py`)

- Change `_augment_gcns_multiplicity(data, simbad)` → `_augment_gcns_multiplicity(data, simbad, has_fitted_orbit=False)`. At the tail (after `is_multiple` is finalized, before `return data`) add:
```python
mc, bm = binary.classify_multiplicity(
    data.get("is_multiple", False),
    has_fitted_orbit=has_fitted_orbit,
    has_binary_otype=binary.is_bound_otype(data.get("otype")),
    gcns_comps=comps)
data["multiplicity_class"] = mc
data["bound_multiple"] = bm
```
- **Present-but-null by construction (REVIEW-FIX, 2× flagged):** initialize `"multiplicity_class": None, "bound_multiple": None` in the `data = {...}` literal at `_multiplicity_data_star` (`:659-660`), so EVERY return path carries the two keys — including the `if not star: return data` early return (`:661-662`), which does NOT pass through `_augment_gcns_multiplicity` and is reachable via `--star ""` (argparse `required=True` does not forbid an empty, falsy string). The augment tail then OVERWRITES them with the classifier result on the paths that reach it.
- Early-return callers (`:667,674,682`) keep the 2-arg form → `has_fitted_orbit=False` (those paths have no fitted orbit; a confirmed-binary otype still reaches `bound` via `data["otype"]`, correct).
- The final caller (`:739`) passes `has_fitted_orbit=any(binary.is_orbit_solution(s) for s in stellar)` (`stellar` = the non-planet solutions already computed at `:680`; `is_orbit_solution` also re-excludes planets internally, so this is idempotent).
- `_multiplicity_data_sol` (`:869`) — Sol is single: add `"multiplicity_class": None, "bound_multiple": None`.
- No scratch keys left in `data` (the orbit flag is a function argument, never a `data[...]` entry) → no JSON leak.
- **`_blocks_multiplicity` (display, `:742`) is NOT changed (REVIEW-FIX — byte-identity):** adding a KV row would alter the markdown/html dossier `document` STRING for every bound/optical star (e.g. α Cen) — a changed EXISTING output = byte-identity failure. The tri-state surfaces in the JSON `data` payload ONLY (what WB re-gates + the consumer reads); the rendered markdown/html document stays byte-identical.

### 2.4 C2 — schema + migration (`core/db.py`)

- `gcns_stars` CREATE TABLE: add the 5 columns **at the END, after `n_components` (`:263`, the last column before the closing `);` at `:264`)** — NOT before `system_id` — so a fresh-DB `CREATE TABLE` and a migrated-DB `ALTER` (which always appends) produce the SAME physical column order (REVIEW-FIX):
  `pmra REAL, pmdec REAL, pmra_error REAL, pmdec_error REAL, ruwe REAL` (Gaia PM mas/yr; NULL for missing_10mas; `ruwe` = renormalised unit weight error).
- `_migrate_schema` list (`:433`): append the 5 `("gcns_stars", "<col>", "REAL")` rows (idempotent PRAGMA-guarded ALTER — the CR-18 template). Add a one-line docstring note: *the DB is machine-local/gitignored — an existing DB gains the columns here but they stay NULL until the PM backfill (or a full opt-58 re-ingest under the extended ADQL) runs on that box.*

### 2.5 C2 — extend the full ingest (`core/databases.py`)

- `_GCNS_MAIN_ADQL` (`:2397`): add `pmra, pmdec, pmra_error, pmdec_error, ruwe` to the SELECT.
- Main insert tuple (`:2757`): append `_fval(row["pmra"]), _fval(row["pmdec"]), _fval(row["pmra_error"]), _fval(row["pmdec_error"]), _fval(row["ruwe"])`.
- Missing insert tuple (`:2788`): append `None, None, None, None, None` (missing_10mas has no PM — no fabrication).
- INSERT column list + placeholders (`:2817`): add the 5 columns + 5 `?`.
- **`_GCNS_ROW_COLS` (`:2911`): UNCHANGED** — the PM columns are deliberately NOT added, so every GCNS reader (`gcns-source`/`gcns-system`/`gcns-within-sol`/`gcns-stars-within-star`/`dossier`) stays byte-identical. This is the load-bearing byte-identity guard (no `SELECT *` exists on this path; readers select `_GCNS_ROW_COLS` explicitly).

### 2.6 C2 — targeted PM-only backfill (`core/databases.py`, new)

`backfill_gcns_proper_motion(progress_callback=None) -> {updated, matched, total_main, snapshot_date} | {"error"}`:
1. `get_conn()` (runs `_migrate_schema` → columns exist). If `gcns_stars` is empty → `{"error": "gcns_stars is empty — run the GCNS import (option 58) first."}`.
2. Async GAVO pull via the existing `_gcns_fetch` helper: `SELECT source_id, pmra, pmdec, pmra_error, pmdec_error, ruwe FROM gcns.main` (maxrec = `_GCNS_MAXREC`). **Validate-before-write** gate: abort (no DB write) on OVERFLOW or row count < `_GCNS_MAIN_MIN_ROWS`.
3. In ONE transaction: `executemany("UPDATE gcns_stars SET pmra=?, pmdec=?, pmra_error=?, pmdec_error=?, ruwe=? WHERE gaia_source_id=?", rows)` where **each row tuple is `(pmra, pmdec, pmra_error, pmdec_error, ruwe, source_id)` — `source_id` LAST** even though the SELECT returns it FIRST (reorder in the build; a positional slip would silently write PM into the wrong columns — REVIEW-FIX). Touches **only** the 5 PM columns keyed by the UNIQUE `gaia_source_id` → exactly one row per id; every other column and every other GCNS table byte-identical **by construction**; `missing_10mas` rows (NULL `gaia_source_id`) never match → stay PM-null.
4. UPSERT **only** the `gcns_pm_backfill_date` key into `gcns_meta` — never re-touch `snapshot_date`/`gcns_version` (every GCNS reader surfaces those; overwriting either would change existing reader output — REVIEW-FIX).
- **Runnable entry point — a CORE FUNCTION ONLY, no `query.py` subcommand (REVIEW-FIX).** Neither the full GCNS ingest (`compute_gcns_ingest`, opt 58) nor the dust fetch (opt 59) has a `query.py` wrapper — GCNS/dust data operations are CLI/GUI-only by established convention, and a live-network WRITE subcommand would be a new query.py category (cutting against the pattern). APP populates THIS box's shared DB for delivery by invoking `core.databases.backfill_gcns_proper_motion()` directly (a one-off `venv/bin/python -c …`, exactly how `compute_gcns_ingest` is invoked by its callers); WB verifies via direct sqlite (Q4b). (Network op, but ~331k rows × 6 cols — far lighter than the full ingest; memory-safe per "one heavy job at a time".) **Before the delivery pull, verify the live GAVO column names (`pmra`/`pmdec`/`pmra_error`/`pmdec_error`/`ruwe`) against `gcns.main`'s `TAP_SCHEMA`** — a wrong name aborts at the validate-before-write gate (no partial write), but this is the delivery path.

## 3. Behavior matrix (the truth table + anchors)

| signal present (evaluated in order) | `multiplicity_class` | `bound_multiple` |
|---|---|---|
| `is_multiple:false` (single) | `null` | `null` |
| any GCNS incident pair `bound is True` **OR** a fitted orbit (`is_orbit_solution`: sb9/orb6/gaia-nss*) **OR** a confirmed-binary otype (`_BOUND_OTYPES`) | `"bound"` | `true` |
| `is_multiple` **AND** ≥1 GCNS incident pair **AND** all `bound is False` **AND** none of the bound signals | `"optical"` | `false` |
| `is_multiple` else (no GCNS pair; bare `wds`/visual; candidate/variable otype; a fitted-orbit *route* but no solution) | `"unknown"` | `null` |

**Anchors (all reachable via GCNS-bound + fitted-orbit alone; the otype trigger is never needed for these):**
- **ε Eri** — `BY*` (default `sb_flag:false`), only a bare `wds` solution, no GCNS pair, `gaia-nss` route but no solution → **`unknown`**.
- **StKM 1-79** (`--source-id 2782899393446682368`) — GCNS `gcns_n=2`, all pairs `bound=0`, no orbit/bound-otype → **`optical`**.
- **ζ¹ Ret** — GCNS `bound=1` (a bound CPM pair) → **`bound`**.
- **α Cen** — SB9 seq 815 fitted orbit (its GCNS `bound` is null, Gaia-missing primaries) → **`bound`**.
- **61 Cyg A** — merged GCNS-bound + orbit → **`bound`**.

## 4. Byte-identity guarantees

- **C1 is additive-only:** the classifier NEVER reads/writes `is_multiple`/`sb_flag`/`n_components`/`components`/`sources`/existing basis/`gcns_confirmed`; it only appends `multiplicity_class`/`bound_multiple`. No number in the CR-13/14/15.4/16 mass/exclusion/stability battery is computed here. `gcns_confirmed` NOT renamed (61 Cyg A anchor intact).
- **No scratch-key leak** on the dossier path (the orbit flag is a parameter, not a `data` key) → the JSON `data` dict gains exactly two keys.
- **C2 existing-output byte-identity:** `_GCNS_ROW_COLS` untouched ⇒ every reader selects the same columns ⇒ identical output; no `SELECT *` on the GCNS read path. The targeted backfill `UPDATE`s only the 5 new columns keyed by `source_id` ⇒ existing `gcns_stars` values + `gcns_systems`/`gcns_system_members`/`gcns_system_pairs` byte-identical ⇒ CR-18 anchors (GJ 9588 transverse, 61 Cyg A de-dup) unmoved.
- **CR-18 4 anchors + whole battery** re-run byte-identical (WB independently re-gates on the sister venv).

## 5. Change surface

- `core/binary.py` — `_BOUND_OTYPES`/`_ORBIT_SOURCES`/`is_bound_otype`/`is_orbit_solution`/`classify_multiplicity` + `multiplicity_summary` inject (§2.1/2.2).
- `core/report.py` — `_augment_gcns_multiplicity` param + tail class; final-caller `has_fitted_orbit`; `data` literal present-but-null defaults (`:659-660`); `_multiplicity_data_sol` nulls. **`_blocks_multiplicity` NOT changed** (would break markdown/html byte-identity — §2.3).
- `core/db.py` — 5 schema columns (at END of CREATE TABLE) + 5 `_migrate_schema` rows + docstring note (§2.4).
- `core/databases.py` — `_GCNS_MAIN_ADQL` + both insert tuples + INSERT list; new `backfill_gcns_proper_motion` (§2.5/2.6). **`_GCNS_ROW_COLS` unchanged.**
- `query.py` — **no change** (no new subcommand; the backfill is a core function invoked directly for delivery).
- `tests/test_cr20.py` (new) — §7.
- Docs — `docs/star-databases.md` (Component 2 + PM columns + machine-local note), `docs/integration.md` (CR-20 block: `multiplicity_class`/`bound_multiple` contract + `gcns-pm-backfill`), `CLAUDE.md` (suite count), `docs/testing.md` (test_cr20.py), `completed_plans/README.md` at fulfillment.

## 6. `/code-review high` checkpoints

Each runs on the **uncommitted working-tree diff on `main`** in THIS session, **before** committing — verify `git status` + `git --no-pager diff --stat` shows exactly the intended CR-20 files first; never delegate to a worktree-isolated agent. (CR-19 lesson: the stale `origin/master` that caused a wrong-branch review is deleted; repo is main-only, `origin/HEAD→main`.)
- **CP1 — after C1 (classifier + both wirings + C1 tests).** Verify: truth-table correctness; Guardrail 1 (`_BOUND_OTYPES` excludes RS*/El*/BY*/candidates/EP*; bound-trigger does NOT reuse `sb_flag`); Guardrail 2 (classify on `bo["solutions"]`, not routes); **planet-class excluded in `is_orbit_solution` so the summary path matches the dossier's planet-filtered `stellar` (GJ 876 → not bound on EITHER path)**; additive-only (no existing key/value read or mutated); cross-path agreement (`multiplicity_summary` ≡ dossier) incl. the planet-only case; **`_blocks_multiplicity` NOT changed (markdown/html byte-identity)**; no dossier scratch-key leak; **present-but-null on EVERY return path (incl. `if not star`/`--star ""`), on singles + Sol**.
- **CP2 — after C2 (schema + migration + ADQL + inserts + backfill + C2 tests).** Verify: `_GCNS_ROW_COLS` untouched / no reader output change; migration idempotency; PM columns at END of CREATE TABLE (fresh-DB ≡ migrated-DB column order); targeted backfill touches only PM columns in one transaction with a validate-before-write gate + `source_id`-LAST tuple order + single-key `gcns_meta` UPSERT; missing_10mas → PM null; full-ingest tuple/column-list arity matches.
- **CP3 — final full-diff pass.** Byte-identity across the surface; docs current; test suite green; `query.py gcns-pm-backfill` wiring.

## 7. Test plan (`tests/test_cr20.py`, offline; a couple live-gated anchors)

**Unit:** `classify_multiplicity` full truth table (single→null,null; gcns bound True→bound; fitted orbit→bound; bound otype→bound; all-False gcns→optical; bare/undetermined→unknown; mixed True/None→bound; mixed False/None→unknown). `is_orbit_solution` (sb9/orb6/gaia-nss*→True; wds/None/""→False). `is_bound_otype` (SB*/EB*/Al*/bL*/WU*/**→True; RS*/El*/BY*/SB?/EB?/**?/EP*/None→False).
**Integration (mocked binary_orbit + gcns_bound_companions, tmp DB):** `multiplicity_summary` → ε Eri-like (wds-only)→unknown; StKM-like (gcns all bound=0)→optical; ζ¹ Ret-like (gcns bound=1)→bound; α Cen-like (sb9 orbit, EMPTY gcns_comps)→bound; single→null,null. **Planet-only NSS host (GJ 876-like:** `source:"gaia-nss:*"`, `companion:{class:"planet"}`, no other signal) → **NOT bound on EITHER path** (the planet-exclusion baked into `is_orbit_solution`). Guardrail 2: a `binary_orbit_routes` entry with NO matching solution → not bound. `report._multiplicity_data_star` → the same classes; the **`if not star` / `--star ""` early return → present-but-null,null** (via the `data` literal defaults, NOT via `_augment_gcns_multiplicity`); `_multiplicity_data_sol`→null,null. **Cross-path agreement** test — both paths → same class for identical mocked inputs, **INCLUDING the GJ 876 planet-only case**. **`bound=None`-entry** synthetic tests: mixed True/None→bound; mixed False/None→unknown (not all False). **Additive-identity** test: a single-star `multiplicity_summary` output's existing keys byte-identical vs a captured baseline; only the two new keys added.
**C2:** `_migrate_schema` adds the 5 columns (PRAGMA table_info on a fresh tmp DB); `_GCNS_ROW_COLS` does NOT contain any PM column (guards reader byte-identity); a mocked ingest carries PM on main rows / NULL on missing rows; `backfill_gcns_proper_motion` (mocked `_gcns_fetch`, tmp DB pre-seeded) UPDATEs only the 5 PM columns and leaves every other `gcns_stars` column + the resolved-system tables unchanged; empty-table → error; validate-before-write aborts on a short pull.
**Live-gated (`SPACE_APP_RUN_LIVE`):** `multiplicity --star "* eps Eri"` → `multiplicity_class:"unknown"`; `multiplicity --source-id 2782899393446682368` → `"optical"`; `multiplicity --star "zeta01 Ret"` → `"bound"`.

## 8. Re-gate handoff (WB, sister venv, after build)

WB independently re-gates on the sister venv reading live `query.py`: the ENTIRE CR-13+CR-14+CR-15.4+CR-16 battery + the 4 CR-18 anchors **byte-identical**, PLUS the CR-20 anchors (ε Eri→unknown, StKM 1-79→optical, ζ¹ Ret/61 Cyg A/α Cen→bound; single star→null on both paths) + C2 (`gcns_stars` PM populated matching `gcns.main` via direct sqlite, `missing_10mas` PM null, every existing subcommand byte-identical). Then Greg signs one FULFILLED flip → APP commit+push (held until the flip).

## 9. Risks / edge cases

- **Gaia-status degrade (CR-19):** a bounded orbit cross-check yields fewer bound signals → the class is conservatively `unknown`/`optical` from whatever resolved. Consistent with the existing degrade philosophy; not special-cased. (`gaia_status` already surfaced separately.)
- **`El*`/`EP*`/candidate membership** — proceed-unless-WB-objects (§MSG 217); one-line `_BOUND_OTYPES` edit if WB wants El*→bound. None affects an anchor.
- **`**` → SETTLED = DROPPED (WB MSG 219, converged with both reviewers).** SIMBAD `**` "double or multiple star" is a catalog STATUS, not a boundedness determination (can be a purely optical/visual double), so it is NOT in `_BOUND_OTYPES`; a bare-`**` star reads `unknown` (or `optical` under a GCNS all-`bound=0`). Detection-of-orbital-motion binaries only. `El*`/`EP*` also excluded (MSG 217). No open otype questions remain; no anchor affected.
- **Full re-ingest drift** — avoided by the targeted backfill; the extended ADQL/INSERT only matters on a *future* full opt-58 re-ingest (documented machine-local caveat).
- **Backfill on an unpopulated DB** — guarded (empty-table error); validate-before-write gate on the GAVO pull.

## 10. Out of scope

R3 (Gaia-missing + orbit-less bound coverage; needs a live external resolve) = **CR-21**. No new WB data, no new catalog. No change to `binary-orbit`/`binary-stability-auto`/`exclusion-system` outputs. PM not surfaced in any CR-20 subcommand (backbone for CR-21).
