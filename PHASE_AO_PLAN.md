# Phase AO — Gould Designations (Uranometria Argentina)

**Status:** PLANNED (not started)
**Date drafted:** 2026-07-28 · **Revised 2026-07-28** after adversarial pre-implementation review
**Scope:** `core/db.py`, `core/databases.py`, a bundled CSV, `gui/panels/`, `core/shared.py` (§2), tests, docs
**Sequencing (decided 2026-07-28): this phase ships FIRST**, ahead of `PHASE_AN_PLAN.md`.
**Depends on:** nothing. The one external need — a constellation-genitive lookup — is **owned by this
phase** (§2) rather than by AN3, which is what makes shipping first coherent.

> **Revision note.** Pre-implementation review found one blocking dependency, one factual error, and
> four unspecified mechanics. Corrections are marked **[R1]**…**[R6]** and summarized in §10. The
> plan's central claim — that the change is fully additive — was **independently verified true**
> (§9). Per the house convention (`completed_plans/README.md`), corrections stay visible.

---

## ⚠ DECISIONS REQUIRED BEFORE STARTING

Three open decisions. **None gates the start** — AO0 and AO1's schema can proceed today — but each
must be settled before the part it gates. Recommendations are given; the call is the maintainer's.

| # | Decision | Gates | Options | Recommendation |
|---|---|---|---|---|
| **D1** | **Auto-seed or import utility?** (§4, AO1a) | **AO1** | **(a)** Auto-seed via `_STATIC_TABLES` — works on first run, no user action. **(b)** CLI opt 60 + `ImportGouldPanel`, like opts 52-56. **(c)** Both — seed on create, importer for manual refresh | **(a) auto-seed.** The catalogue is frozen at 1879; an import step for data that can never change is ceremony. `"60"` is confirmed free if you prefer (b) |
| **D2** | **Separate `gould` key, or folded into `designations`?** (§6, AO3a) | **AO3** | **(a)** Separate top-level `result["gould"]` — needs a per-panel edit to display. **(b)** Fold into the `designations` dict — appears in every banner free | **(a) separate.** `designations` means "what SIMBAD returned"; folding in a VizieR value would make `desig_str` misattribute provenance and would put a non-SIMBAD string into `star_systems.designations` semantics |
| **D3** | **Does Gould reach the Phase Q dossier?** (§6 [R6]) | **AO3** | **(a)** Include in `core/report.py:114-129` `_identity_data_star`. **(b)** GUI panels only | **Weak lean (a).** A system dossier is arguably *the* place a historical designation belongs — but it widens the export contract, so it is a deliberate call, not a default |

**Settled, no input needed** (recorded here so they are not re-litigated mid-build):

- **Ownership of the constellation-genitive table** → this phase (§2). Decided 2026-07-28 with the
  AO-first sequencing; `PHASE_AN_PLAN.md` §7 is already aligned.
- **Bundle vs live VizieR query** → bundle (§3).
- **`table_exists()` vs the GCNS `COUNT(*)` guard** → `table_exists()` (§5 [R4]). Implementer's call;
  the recommendation stands unless there is reason to mirror the precedent exactly.
- **SAO tie-break** → **not a decision, a measurement.** Resolved by the AO0 duplicate count (§5, R5).

---

## 0. Problem statement

Gould designations are absent from the app. Reference cases:

- **HD 102365** should read **66 G. Centauri**
- **GJ 432 A** (= HD 100623) should read **289 G. Hydrae**

**Root cause: SIMBAD has no Gould data at all.** Verified against the live SIMBAD TAP `ident` table
(2026-07-28):

```
SELECT id FROM ident WHERE id LIKE 'G. %'     ->  0 rows
SELECT id FROM ident WHERE id LIKE '% G. %'   ->  0 rows
SELECT id FROM ident WHERE id LIKE '%Gould%'  ->  2 rows
                                                  "NAME Gould Belt", "NAME Gould's Belt"
```

CDS never ingested Gould's *Uranometria Argentina* cross-identifications. **No parser change can
surface them** — this must be a separate data layer.

---

## 1. Source — located and verified

**VizieR `V/135A/catalog`** — *Uranometria Argentina catalog of bright southern stars* (Gould, 1879).
Profiled live 2026-07-28:

```
rows                 8471
G   (Gould number)   7756 non-null   int16      <- 715 rows have NO Gould number
cst (constellation)  7756            <U3
HD                   8409            int32      <- primary join key
SAO                  8415            int32      <- fallback join key
F   (Flamsteed)      1097
let (Bayer)          1451            LaTeX form, e.g. "\alpha1"
Name                 8471            pre-formatted, e.g. "66G Cen"
Vmag                 8456
m_HD (HD component)    15
```

| HD | G | cst | `Name` | Expected |
|---|---|---|---|---|
| 102365 | 66 | Cen | `66G Cen` | 66 G. Centauri ✓ |
| 100623 (GJ 432 A) | 289 | Hya | `289G Hya` | 289 G. Hydrae ✓ |
| 128620 (α Cen A) | 363 | Cen | `363G Cen` | 363 G. Centauri ✓ |
| 22049 (ε Eri) | 101 | Eri | `101G Eri` | 101 G. Eridani ✓ |

**Not available elsewhere:** VizieR `V/50` (Bright Star Catalogue) carries Flamsteed/Bayer in its
`Name` column (`18Eps Eri`) but **zero** of its 9110 rows contain `G.`. `V/135A` is the source.

---

## 2. **[R1] Blocking dependency — the constellation-genitive table** ⚠️

The first draft claimed *"Depends on AN3 only… AO can ship before AN"* and simultaneously specified
`"constellation": "Centaurus"` and `"display": "66 G. Centauri"` as part of the `gould` contract.
**Those are contradictory.** The IAU-abbreviation → genitive mapping **does not exist anywhere in the
repo** (verified: no `genitive` anywhere under `core/`, `gui/`, `query.py`), and AN3 — where it was to
be built — is itself PLANNED and not started.

So as originally written, AO2 and AO3 could not produce their documented fields without unshipped
work from another phase.

**Resolution — own the table here.** The 88-entry abbreviation→genitive map is small, static, and
entirely self-contained. Build it **in this phase**, in `core/shared.py` beside the designation
helpers, and let Phase AN3 *consume* it rather than the reverse. AN3's other half (the Greek
abbreviation→letter table) stays in AN, where it is actually needed.

This inverts the dependency: **AO now genuinely ships independently, and AN3 gets one of its two
tables for free.** Update `PHASE_AN_PLAN.md` §7 to match when this lands.

*(Fallback if the table is deferred: scope `constellation` and `display` out of AO2's contract and
emit only `designation: "66 G. Cen"`. Less useful, but honest.)*

---

## 3. Part AO0 — Bundle the catalogue, do not query it live

**Decision: bundle it.** Gould 1879 is a closed historical catalogue; 8471 rows ≈ 400 KB, comparable
to CSVs already committed. A per-star network round-trip to render a designation string would make
the SIMBAD panel's latency depend on CDS availability, and the panel already makes two live calls
(SIMBAD + Hypatia). Keeping it offline matches the `_simbad_gcns_block` precedent.

The Phase AM VizieR gateway (`core/catalog.py::vizier_query`) is the right tool for the **one-time
export** → `gouldDesignations.csv` at the repo root beside `hwc.csv`.

**Export columns:** `g_number, cst, hd, sao, flamsteed, bayer, name, vmag`.
**Provenance:** VizieR catalog id + export date + Gould 1879 citation, in a header comment and the docs.

---

## 4. Part AO1 — Schema + load

```sql
CREATE TABLE IF NOT EXISTS gould_designations (
    g_number   INTEGER,      -- NULL for the 715 rows without one  (see AO1b)
    cst        TEXT,         -- IAU 3-letter, 1875 boundaries (see AO4b)
    hd         INTEGER,      -- primary join key
    sao        INTEGER,      -- fallback join key
    flamsteed  INTEGER,
    bayer      TEXT,         -- LaTeX form as published, e.g. "\alpha1"
    name       TEXT,
    vmag       REAL
);
CREATE INDEX IF NOT EXISTS idx_gould_hd  ON gould_designations(hd);
CREATE INDEX IF NOT EXISTS idx_gould_sao ON gould_designations(sao);
```

**Resolved concern — existing databases pick this up automatically.** `get_conn()` calls
`_create_schema(conn)` on **every** connection open (`core/db.py:61`), so `CREATE TABLE IF NOT EXISTS`
lands on an already-populated `data/space_app.db` with no `_migrate_schema` entry. (`_migrate_schema`
is only for adding *columns* to existing tables.) No action needed.

**`get_table_status()`** (`core/db.py:588`) — add `("gould_designations", "Gould Designations")`.

**[R2] Factual correction — there is no "opt 57."** The first draft said the table would appear "in
opt 57 / `DbStatusPanel`." `main.py`'s menu dict jumps **56 → 58**; `57` is unused. `get_table_status()`
has exactly one caller repo-wide: `gui/panels/csv_utility.py:417`, reached via `gui/nav.py:128`
("Database Table Status"). It is **GUI-only**. *(CLAUDE.md's menu table labels 57 "GUI only," which is
what the draft misread as a CLI option.)*

### AO1a — decision: auto-seed or import utility?
**Recommendation: auto-seed** via `_STATIC_TABLES` (`core/db.py:430-437`) + a `_seed_gould` function.
The catalogue is frozen; an import step for data that can never change is ceremony. If an importer is
also wanted, `"60"` is confirmed free in `main.py`'s menu dict (50-56, 58, 59 used).

### AO1b — **[R3] Type coercion must be specified; both precedents are wrong here** ⚠️
The schema promises `g_number` is `NULL` for 715 rows. **Neither cited precedent achieves that:**

- `_seed_main_sequence` (`core/db.py:460-484`) inserts **raw `DictReader` strings** with `""` defaults
  — blank cells land as empty-string TEXT, **not NULL**.
- `_seed_honorverse_hyper` (`core/db.py:618-631`) does `float()` conversion but **`continue`s the whole
  row** on `ValueError` — wrong here, since a row with no Gould number must still be kept (it may
  carry Flamsteed/Bayer data, and it is one of the 8471 stars).

**Consequence:** copying either naively breaks **AO2a's tie-break**. SQLite orders
`NULL < INTEGER/REAL < TEXT`, so a mixed TEXT/INTEGER column makes `ORDER BY g_number LIMIT 1`
behave unpredictably.

**Required:** an explicit per-column coercion — blank/`--` → `None`, else `int()`/`float()`, keeping
the row either way. Specify it in the seeder; do not "mirror" a precedent.

---

## 5. Part AO2 — The lookup block

`_simbad_gould_block(designations)` in `core/databases.py`, attached in `compute_simbad_lookup` beside
`result["gcns"] = …` (`databases.py:292`).

```
result["gould"] = {
    "g_number": 66,
    "cst": "Cen",
    "constellation": "Centaurus",      # via the §2 genitive table
    "designation": "66 G. Cen",
    "display": "66 G. Centauri",
    "hd": 102365,
    "matched_on": "hd",                # "hd" | "sao"
    "source": "VizieR V/135A (Gould 1879)",
}
```

Contract: **non-fatal and silent** — `None` on no HD/SAO, no match, empty/missing table, or any error.
Never raises, never blocks the lookup.

**[R4] The GCNS precedent does more than the draft claimed.** The draft called it "a single indexed
local read." In fact `_simbad_gcns_block` (`databases.py:93-116`) → `compute_gcns_by_source_id`
(`:2865-2894`) runs **three queries across two tables**: a full-table `SELECT COUNT(*) FROM gcns_stars`
as its is-it-seeded guard, the indexed `WHERE gaia_source_id = ?`, and `_gcns_meta_dict()` for
provenance — wrapped in nested try/except at both layers.

The behavioural claims (silent, non-fatal, `None` on every failure, no network) **do** hold, and the
cited lines are exact. But AO2 should **decide deliberately** about the `COUNT(*)`: it is an O(n) scan
used only as an emptiness guard. A `sqlite_master` existence check is cheaper and covers the
missing-table case more directly. Recommendation: use `table_exists()` (already in `core/db.py:85`)
rather than mirroring the count.

**Join key:** HD primary, SAO fallback. Parse the integer out of `designations["HD"]` (the dict holds
`"HD 102365"`, not `102365`). Stars with no HD get `None` — Gould covers bright southern stars
(V ≲ 7), essentially all of which carry HD numbers.

**AO2a — duplicate keys.** 11 HD values appear on two rows (`m_HD`-flagged components). Tie-break:
**lowest `g_number` wins**, in SQL, pinned by a test — and only correct once AO1b lands.
**[R5] SAO duplicates are unaddressed.** The same multi-component ambiguity may exist for SAO-only
matches. **Measure SAO duplicate counts in the source during AO0** and give SAO its own tie-break if
they exist; do not assume congruence with the HD duplicates.

**Free for `query.py`:** `cmd_simbad_lookup` (`query.py:77-78`) serializes the dict verbatim — the
`gould` key appears with no dispatcher change, exactly as `gcns` did in M5.

---

## 6. Part AO3 — Display surfaces

**AO3a — separate top-level key (recommended).** `designations` means *"what SIMBAD returned"*;
folding in a VizieR-derived value would make `desig_str` misattribute provenance. Cost: it does not
appear in banners automatically.

Rendering — a distinct line beneath the existing banner:

```
STAR DESIGNATIONS:
NAME Ran, *  18 Eri, GJ 144, HD 22049, HIP 16537, …
Gould: 101 G. Eridani
```

GUI panels (all render `desig_str` today): `gui/panels/simbad.py:157-158` ← **ship against this one
first**; `star_regions.py:396-397`; `nasa_exoplanet.py:61`; `catalogs.py:200`.

**[R6] Non-GUI surfaces the draft omitted.** Two more consumers build curated views of the SIMBAD dict
and are places a user could reasonably expect a Gould designation to reach:
- **`core/report.py:114-129`** (`_identity_data_star` → the Phase Q system-dossier `identity` block).
  A dossier export is arguably *the* place a historical designation belongs. **Include or exclude
  deliberately.**
- `core/generate.py:1830` — reads `simbad` for `teff`/`stellarMass`, not identity. Low priority.

Neither breaks (both use `.get()`), but "it doesn't appear automatically" was incomplete as a cost
statement.

**AO3b — format.** The source's `Name` is `66G Cen`. Build `66 G. Cen` / `66 G. Centauri` from
`g_number` + `cst` rather than reusing `Name`, so the format is ours and consistent.

---

## 7. Part AO4 — Documented caveats (not bugs)

**AO4a — coverage is intentionally partial.** Bright southern stars only; 7756 of 8471 rows carry a G
number. Most stars correctly return `None`. State this so an absent designation isn't read as failure.

**AO4b — 1875 constellation boundaries** ⚠️ Gould predates the IAU. **HD 100623 is `Hya` in the
catalogue but sits in Crater today** — SIMBAD's own Flamsteed id is `*  20 Crt`. The app will display
**both** "20 Crateris" and "289 G. Hydrae" for the same star. **This is correct and must not be
"reconciled."** Document it, or a future maintainer will "fix" it into being wrong.

**AO4c — cross-check bonus.** `V/135A`'s `F`/`let` columns give an independent southern-hemisphere
Flamsteed/Bayer set — useful for validating Phase AN1's classifier against real data.

---

## 8. Part AO5 — Tests

New `tests/test_gould.py`, monkeypatching `core.db._DB_PATH` to a tmp file.

**[R3b] The isolation pattern needs TWO setups, not one.** `tests/test_gcns.py:154-164`,
`test_regions.py:31-52` and `test_simbad_gcns_enrichment.py:24-33` all monkeypatch
`db._auto_seed = lambda conn: None`, which disables **all** `_STATIC_TABLES` seeding. Those tests then
hand-`INSERT` fixture rows via SQL and **never exercise a seeder at all**. So:

- **Seeder test** — call `_seed_gould(conn, csv_path)` **directly**, not via `_auto_seed`, in its own
  fixture. Assert row count, non-null `g_number` count, **and raw column types** (the AO1b guard —
  `typeof(g_number)` must be `integer`/`null`, never `text`).
- **Block tests** — the disabled-auto-seed fixture + hand-inserted rows, per the existing pattern.

Cases: the two reference stars; `None` for no-HD / not-in-catalogue / empty table / **missing table**
(must not raise); AO2a HD tie-break determinism; **AO2a SAO tie-break**; SAO fallback fires;
`compute_simbad_lookup` still returns a full result when the Gould block fails; the AO3b formatter;
the §2 genitive table round-trip.

No live-network test needed — the path is offline by design.

Run: `venv/bin/python -m pytest` (baseline **2120 passed, 1 skipped**).

---

## 9. Verified: the "fully additive" claim holds ✅

Independently checked. Every consumer of `compute_simbad_lookup`'s return uses selective `.get()`:
`gui/panels/simbad.py:157-158`, `star_regions.py:396-397`, `nasa_exoplanet.py:61`, `catalogs.py:200`,
`core/report.py:594-599`, `core/generate.py:1830-1839`, `core/binary.py:220-229`,
`core/catalog.py:288-294`. `query.py:77-78` + `_out()` (`:59-64`) serialize verbatim with no key
filtering. **No test asserts on the exact key set** — every test file referencing
`compute_simbad_lookup` was searched for `assertEqual`/`assertDictEqual`/`sorted(keys())`/`len(result)`
against that dict; the `assertEqual(set(r), {...})` hits in `test_databases.py:131` are on a
*higher-level composite* where `"simbad"` is one sub-key, not on this dict's own keys.

**Adding `result["gould"]` breaks nothing.** The one residual risk is AO1b: a malformed seed could put
wrong types in the block silently, which no test guards — hence the type assertion in AO5.

---

## 10. Revision summary — what review changed

| Tag | Original claim | Verified reality |
|---|---|---|
| **[R1]** | "Depends on AN3 only; ships independently" | Contradictory — the genitive table doesn't exist and AN3 is unstarted. **Own it here**; AN3 consumes it |
| **[R2]** | Appears "in opt 57 / DbStatusPanel" | **No opt 57 exists** (menu jumps 56→58). GUI-only, via `gui/nav.py:128` |
| **[R3]** | "Mirror `_seed_honorverse_hyper`" | Both precedents give **wrong NULL handling**; breaks AO2a's `ORDER BY` (SQLite NULL<INT<TEXT). Coercion must be explicit |
| **[R3b]** | "Follow the `test_gcns.py` isolation pattern" | That pattern **disables the seeder**; testing it needs a second, separate setup |
| **[R4]** | GCNS block = "one indexed local read" | **Three queries, two tables**, incl. a full `COUNT(*)`. Use `table_exists()` instead |
| **[R5]** | Tie-break specified for HD only | SAO fallback may have its own duplicates — **measure in AO0** |
| **[R6]** | Display surfaces = 4 GUI panels | Also `core/report.py:114-129` (Phase Q dossier) — a deliberate include/exclude |
| — | "Fully additive" | ✅ **Verified true** |
| — | *(new)* | ✅ `_create_schema` runs on every `get_conn()` — new tables reach existing DBs, no migration needed |

---

## 11. Review & verification checkpoints

**Already done — pre-implementation plan review (2026-07-28).** An adversarial agent sweep found the
seven items in §10 and independently confirmed the additive claim (§9). All findings were re-verified
against the source before being folded in.

### Checkpoint table

| Trigger | Tool | The specific question it answers |
|---|---|---|
| **During AO0** | **data check, not review** | Measure SAO duplicate counts in `V/135A` (R5). This is a `GROUP BY … HAVING COUNT(*) > 1` against the export, not something an agent should opine on |
| After AO1 + AO2 land | **`/code-review`** — one pass, both together | The diff is small and the two parts are coupled through AO1b (type coercion → `ORDER BY` correctness). Reviewing them separately splits the one question that matters |
| AO2's `None`-on-every-failure guarantee | **tests, not an agent** | The pre-implementation review already enumerated the exact cases (§8: no-HD, no-match, empty table, **missing table**). Once those are written, an agent adds nothing — **downgraded from the earlier recommendation** |
| After AO3 | — | Presentation only. The `report.py` include/exclude is a decision, not a review target |
| AO4, AO5, AO6 | — | Caveats, tests, docs |

**Total: 1 `/code-review` pass, 0 agent sweeps.** That is the honest call for this phase — every part
is additive, §9 verified nothing existing changes behaviour, and the review already converted its own
findings into specific test cases. Spending an agent here would be ceremony.

**Contrast with Phase AN**, which warrants 2 sweeps + 2–3 review passes. The difference is real and
worth preserving: AN is a behaviour-preserving refactor across six sites with four untested; AO adds
a table and a dict key.

### Sequencing rule

**`/code-review` → apply fixes → *then* refresh this plan.**

### Definition of done, per part

A part is not finished until this plan is updated to match what was built — corrections inline and
visible, per `completed_plans/README.md`. Done by whoever built the part, not delegated.

### One cross-phase obligation — **discharged at the plan level 2026-07-28**

§2 moves the constellation-genitive table **into this phase**. `PHASE_AN_PLAN.md` §7 has been updated
to match: AN3 builds only the Greek table and **consumes** the genitive one from here. The two plans
now agree on ownership.

Two things still to do when the table actually lands:
1. Confirm `PHASE_AN_PLAN.md` §7 still describes the shipped location/signature (it specifies
   `core/shared.py`, beside the designation helpers).
2. If the table ends up somewhere else, fix **both** plans in the same commit.

Two plans describing the same artifact differently is exactly the drift that left
`IMPROVEMENT_PLAN.md` P4.6 half-finished and undocumented — see `AN §1`.

---

## 12. Part / task summary

| Part | Title | Risk | Notes |
|---|---|---|---|
| §2 | Constellation-genitive table | Low | **Moved into AO**; inverts the AN3 dependency |
| AO0 | Export `V/135A` → bundled CSV | Low | **+ measure SAO duplicates** (R5) |
| AO1 | Schema + `get_table_status` + load | Low→**Medium** | AO1b coercion is load-bearing for AO2a |
| AO2 | `_simbad_gould_block` + attach | Low | R4: prefer `table_exists()` over `COUNT(*)` |
| AO3 | Display surfaces | Low | AO3a/AO3b + the `report.py` decision |
| AO4 | Caveat documentation | Low | AO4b (1875 boundaries) is the important one |
| AO5 | Tests | **Medium** *(was Low)* | Two fixtures; type assertions |
| AO6 | Docs | Low | `docs/star-databases.md`, `docs/integration.md`, `CLAUDE.md`, `completed_plans/README.md` |

**Order:** §2 → AO0 → AO1 → AO2 → AO5 → AO3 → AO4 → AO6.

**Overall risk: still low** — every part is additive and §9 confirms nothing existing changes
behaviour. But AO1b and AO5 are no longer trivial, and §2 must be settled before AO2 can emit its
documented contract.
