# PHASE_CR10_PLAN.md — Detection-floor & survey-disposition bundle (star_analysis CR-10)

**Status: WB-RE-GATED GREEN — all 3 items independently reproduced on the shipped tool (MSG 093). AWAITING Greg's one FULFILLED flip + commit go; commit HELD · 2026-08-20**
(Greg cleared 2026-08-20; #1 sibling-sweep = built, #2 tolerance ≈1.5%, #3 tier = core-tier.)

**Build results (per item):**
- **CR-10.2** — `tests/test_nuclear.py` + `test_query_nuclear.py`: **46 passed** (+8 new). Live-verified `--fe-h 0.60`.
- **CR-10.1** — `tests/test_exoplanet_batch.py`: **57 passed** (+15 new); live anchors
  `tests/test_query_exoplanet_batch_live.py::Cr10SurveyDispositionLiveTest`: **3 passed** (HD 148193→FP, Kepler-10→CONFIRMED, HD 69830→null); TOI-2084 verified live (2084.02 FP → host `survey_siblings`).
- **CR-10.4** — `tests/test_detection.py` + `test_query_detection.py`: **63 passed** (+12 new); live
  `tests/test_query_detection_live.py`: **2 passed** (HD 69830→0.86/archive ≡ batch).

**Gate-B code-review (high, 5 findings) — dispositions:**
- **FIXED #2** — CR-10.4 double SIMBAD round-trip: `fetch_archive_stellar_mass(host, simbad=None)` now reuses the
  wrapper's resolved `sl` (one lookup, not two).
- **FIXED #4** — CR-10.1 component-planet survey dispositions bound but not counted: the coverage summary now counts
  host + component planets, and the post-pass guard runs whenever hosts **or** component planets exist (consistent
  binding regardless of a planetless-primary batch).
- **NOT CHANGED #1** (age_soft → `per_output` "extrapolated") — **pre-existing CR-9/CQ-7-3c-2** behavior, untouched by
  CR-10.2, and defensible (a soft age is a reduced-reliability regime); out of CR-10 scope, not altering WB-fulfilled
  CR-9 behavior.
- **NOT CHANGED #5** (`per_output` mixes a bool among severity strings) — the **exact shape WB blessed in Q4** ("check
  the flag at both placements"); changing it fails their re-gate. Documented in the code comment.
- **NOT CHANGED #3** (core-tier network fan-out) — the survey pass on core is **by design** (WB Q3 + Greg #3); the
  component_planets fan-out is pre-existing CR-9. Not a bug.
- Post-fix: 166 affected offline tests + all 5 live anchors re-run GREEN.
**Spec (contract):** `/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR10-detection-floor-and-survey-disposition.md`
**Coordination:** `/home/greg/Claude/coordination-channel.md` — MSG 087 (WB hand-off) → MSG 088 (APP questions) → MSG 089 (WB answers — all adjudicated) → MSG 090 (APP ack + anchor echo) → **MSG 091 (WB: anchor reproduced archive-side + re-gate pre-pinned to the exact objects + faithful-surfacing rule locked)**. WB re-gates each item on the sister venv against the pinned anchors; Greg signs one FULFILLED flip.

> APP-side implementation plan (the "how"). Spec is the contract. Additive to CR-8/CR-9; edits no fulfilled spec/behavior.
> **No code is written until Greg approves.** WB's MSG 089 adjudications are within-contract "how" rulings — no
> acceptance criterion moves, no FULFILLED flip. This revision folds a live schema verification + FP-anchor selection +
> a red-team review of the plan (all 2026-08-20).

---

## 0. Scope

**First fire = CR-10.1 + CR-10.2 + CR-10.4** (all three; CR-10.4 in-scope, **not** optional — WB MSG 089).
**CR-10.3 HELD — untouched** (RV-precision catalog contract not locked; placeholder risks a rebuild). Do not create,
stub, or reference CR-10.3 code.

**Build order:** CR-10.2 (tiny, certain) → CR-10.1 (deciding item) → CR-10.4 (medium, live wiring). Order is APP's call.

---

## 1. Verified NASA-archive facts (live probes, 2026-08-20)

| Table | Disposition col | Value set (live DISTINCT) | Key ids present | Cross-match to `ps` |
|---|---|---|---|---|
| `toi` | `tfopwg_disp` | `{PC,CP,KP,FP,FA,APC}` **+ blank** | `tid` (TIC int), `toi`, `toipfx`, `pl_orbper` — **no `hostname`** | `ps.tic_id` == `'TIC '||toi.tid` (**id join**) |
| `cumulative` (KOI) | `koi_disposition` | `{CONFIRMED,CANDIDATE,FALSE POSITIVE}` | `kepid`, `kepoi_name`, `kepler_name`, `koi_period` | `ps.pl_name` == `cumulative.kepler_name` (**name join**) |
| `k2pandc` | `disposition` | `{CONFIRMED,CANDIDATE,FALSE POSITIVE,`**`REFUTED`**`}` | `pl_name`, `k2_name`, `epic_hostname`, `epic_candname`, `pl_orbper`, `tic_id` | `ps.pl_name` == `k2pandc.pl_name` **or** `k2_name` (**name join**) |

- **`ps` carries NO KIC/EPIC column** (only `tic_id`; `sy_kepmag*` is a magnitude). Kepler/K2 **must** name-join; TESS uses
  the TIC id. (Schema-forced — WB Q1a accepts this.)
- Use **`koi_disposition`** (Exoplanet-Archive Disposition), **not** `koi_pdisposition` (WB Q2). `cumulative` is the
  current-disposition authority (`q1_q17_dr25_koi` is a frozen statistics product — not used).
- **HD 69830** default `st_mass` = **0.86** in `ps` (default_flag=1, Lovis 2006) and `pscomppars`; non-default solutions
  differ (Rosenthal 2021 → 0.8898; Harada 2025 → null). Read the **same aggregation batch uses** (WB Q5 nit) — never
  hard-code 0.86; match batch and flag if it ever diverges.

### FP-TOI anchor (self-selected live; WB Q1c)
- **PRIMARY — `TOI 1836.02`** · TIC **207468071** · host **HD 148193** (= TOI-1836, V=9.77, HD-named) · `tfopwg_disp="FP"`
  · period **1.7727505 d** → **clean per-planet bind** to confirmed **TOI-1836 c** (`ps` period 1.77274710, rel diff
  1.9e-6). The "TESS-flagged-FP-but-confirmed-elsewhere" case → per-planet `disposition_code="FP"` (**satisfies
  validation #1**).
- **Backups:** `TOI 4594.01` → Kepler-1517 b (clean bind, unnamed host); `TOI 2084.02` → host-level-ambiguous
  demonstrator (`disposition_code=null`, `match_status="ambiguous"`).
- **Rare-population note:** only **3** FP TOIs sit on a `ps` host at all (2 clean binds, 1 ambiguous). Live tests must
  **pin these exact identifiers/periods** (stable archive values) — not discover such cases generically.
- **CONFIRMED-KOI anchor (WB-supplied):** **Kepler-10** (b & c CONFIRMED); backup Kepler-22 b.
- **Null anchors (spec):** HD 69830 b, GJ 832 c, HD 102365 b.

---

## 2. CR-10.2 — `nuclear-inventory` [Fe/H]-upper soft-flag  *(build first)*

**Goal:** `[Fe/H] > +0.5` stops globally voiding the output; it becomes a **soft per-output `feh_extrapolation`** on the
`[Fe/H]`-dependent channel (K-40 radiogenic heat) only. The `[Fe/H]`-independent fissile **fraction** stays valid.

**Files:** `core/nuclear_tables.py` (`gce_domain_ok`), `core/nuclear.py` (radiogenic provenance + output assembly),
`tests/test_nuclear.py`, `tests/test_query_nuclear.py`, `docs/integration.md`.

**Current behavior:** `nuclear_tables.py:128-130`: `[Fe/H]` outside `feh_range` (`[-2.5, 0.5]`, model constant at
`nuclear_tables.py:67`) sets `domain_out=True`; `domain_out` is **shared with age-out-of-range** → forces
`domain_ok=False` (`:169`) **and** all three `per_output` severities → `"void"` (`:177-190`). Over-voids the fraction.

**Design:**
1. **Split the [Fe/H]-upper check out of `domain_out`.** Age-out-of-range **stays** `domain_out` (genuinely voids the
   age-dependent GCE integral). New `feh_extrapolation` boolean raised only when `feh > +0.5`.
   - **Lower** edge (`feh < -2.5`) stays under `domain_out` (the CR names only the *upper* edge). Documented default.
2. `feh_extrapolation` does **not** set `domain_ok=False`; does **not** touch `isotope_ratio`/`tonnage` severities.
   `domain_ok` for a metal-rich, in-age, Eu-traced star → `True` (or `None` if no Eu tracer per CQ-7-3c-4) — never
   `False` from `[Fe/H]` alone.
3. **Placement (WB Q4-confirmed, checked at both; red-team #9):** `feh_extrapolation: true|false` as an **additive key**
   on **`radiogenic_heat.provenance`** (`nuclear.py:85-94`) **and** an additive key in `provenance.per_output` (never
   overwriting a severity string), plus carried in `detail["flags"]` so it flows cleanly. Fissile-fraction block +
   provenance stay valid. (Red-team #11: the `fusion` block is also `[Fe/H]`-dependent but is spec-scoped OUT — the flag
   stays K-40-only; fusion keeps its blanket `extrapolation` tag.)
4. Named constant `_DV5_FEH_SOFT_UPPER = 0.5` (distinct from the model's `feh_range[1]`, coincident today).

**Output shape (additive):** `radiogenic_heat.provenance.feh_extrapolation` (bool) + a `provenance.per_output` reflection.

**Validation (spec §CR-10.2 = WB re-gate):** (1) `--fe-h 0.55` ≡ `0.45` byte-identical `fissile_fraction`, not voided;
(2) `--fe-h 0.60` → `feh_extrapolation: true` on the heat output, fraction unflagged; (3) `domain_ok` not globally
`false` from `[Fe/H] > +0.5` alone (still `false` for real age-out).

**Tests:** mirror `Cq73c24DomainGuardTest` (`test_nuclear.py:181-234`). Add:
- **fraction-parity 0.45≡0.55 scoped to `result["fissile"]`** — NOT the whole dict; `provenance` differs by
  `feh_extrapolation` so a whole-dict `assertEqual` fails by design (red-team #10).
- `feh_extrapolation` true@0.60 on heat only; `domain_ok` True(Eu)/None(no Eu) at 0.6, never False-from-feh.
- **strict-`>` boundary** (`fe_h=0.5` exactly → NOT flagged; `0.50001` → flagged); `feh_extrapolation:false` **present**
  (not absent) for in-range `[Fe/H]`.
- **lower-edge guard** (`fe_h=-3.0`, in-age, Eu, no DV-2 → `domain_ok=False` from `[Fe/H]<-2.5` alone) — proves the split
  didn't soften the lower edge (red-team #8).
- Query-contract test in `test_query_nuclear.py`.

---

## 3. CR-10.1 — Native transit-survey FP/candidate disposition  *(deciding item)*

**Goal:** native survey disposition per planet for the transit-survey subset, **additive** to CR-9's disposition layer;
`null` for RV-only (never an error, never omitted). Moves no existing FP verdict — Q9 absence-triage stays primary.

**Files:** `core/exoplanet_batch.py` (new survey helpers + `_planet_record` init + a post-pass + coverage plumbing),
`tests/test_exoplanet_batch.py` (offline, `_query_tap` fake-row seam), `tests/test_query_exoplanet_batch_live.py`
(live anchors), `docs/integration.md`.

**Scope (WB Q3-confirmed):** `planetary-systems-batch` only. Single-host `planetary-systems`/`pscomppars` out of scope.

**Insertion mechanism (two-phase — red-team #2):** `_planet_record(row, field_scope)` (`exoplanet_batch.py:226-282`)
receives a single `ps` row and has **no** access to the batched survey rows or the host `tic_id`, so it only
**initializes** `rec["survey_disposition"]` present-but-`null` (core-tier sibling to `disposition{}`/`limits{}`, after the
`limits` assignment `:255`). A **new post-pass** — run for **both** `core` and `full` (NOT `_enrich_full`, which is
`full`-only `:775`) — fills `matched`/`ambiguous` on each planet, keyed on host `tic_id` (TESS) + planet
`pl_orbper`/`pl_name` (Kepler/K2), after all `ps` rows are fetched. It also covers behavior-#3
`coverage.component_planets[]` (red-team #12) so those carry the field too.

**Output shape (WB Q1b/Q3-approved, additive):**
```
survey_disposition: {
  source_catalog: "toi"|"koi"|"k2pandc"|null,
  disposition_code: <code>|null,      # FP / CONFIRMED / REFUTED / … / null
  disposition_text: <verbatim>|null,
  catalog_id: <TOI/kepoi_name/epic_candname>|null,
  match_status: "matched"|"ambiguous"|null,   # additive (WB Q1b)
  match_note: <str>|null                       # additive (WB Q1b)
}
```
**`null` (present-but-null), never omitted** — CR-9 tri-state discipline (WB Q3): `null` = "checked, not a survey
target", distinct from an absent field = "not checked".

**Cross-match (schema-forced; WB Q1a-accepted):**
- **TESS (`toi`) — id join.** `ps.tic_id` (`'TIC NNN'`) → strip → `toi.tid`. Bind a `ps` planet to a TOI on that TIC by
  **`pl_orbper` match** (relative tolerance, tunable, default ≈1–2%). `catalog_id` = `"TOI <toi>"`.
- **Kepler (`cumulative`) — name join.** `ps.pl_name` == `cumulative.kepler_name`. `catalog_id` = `kepoi_name`.
- **K2 (`k2pandc`) — name join + alias.** `ps.pl_name` == `k2pandc.pl_name` **or** `k2_name`. `catalog_id` =
  `epic_candname` (else `pl_name`).

**Binding semantics — the resolved three-state model (WB Q1b):**
1. **Clean 1:1 match** (period for TESS; exact name for Kepler/K2) → bind: `disposition_code` = the row's disposition,
   `match_status: "matched"`, `match_note` = "TIC …/TOI …/Δperiod …" (or the name key).
2. **Ambiguous** (multiple TOIs on the TIC, no unique period bind) → `disposition_code: null`,
   `match_status: "ambiguous"`, `match_note` listing the host's TOIs + dispositions + why no letter bind. Host-level info
   preserved but **informational only — never moves a per-planet reliability tier**.
3. **No survey entry (RV-only)** → clean `null`, **no note** (validation #3/#4).

**Value handling (live schema):** `toi.tfopwg_disp` **blank** → no-disposition (`null`, not error);
`k2pandc.disposition` **`REFUTED`** — valid 4th code, pass through; `disposition_text` verbatim; `disposition_code` =
raw code; `source_catalog` uses `"koi"` for the `cumulative` source.

**Faithful surfacing — NO reconciliation (WB MSG 091, LOCKED).** The tool emits the survey disposition **verbatim even
when it conflicts with the archive confirmation** — e.g. TOI-1836 c is archive-CONFIRMED (`true_mass`, Heidari 2025) yet
TFOPWG-`FP`, and the tool **must emit `FP`, not suppress it**. The tool never reconciles/downgrades: a
survey-`FP`-on-a-confirmed-planet is surfaced as-is; the caution-flag-vs-downgrade conflict resolution is the
**consumer's §6.7 skill wiring, not a tool decision**. **Do not let a future red-team / code-review "fix" this into a
suppression** — WB pinned it explicitly against exactly that.

**Edge cases (red-team #3/#4):**
- **Multi-catalog collision** — if a planet binds in ≥2 survey tables, `source_catalog` is single-valued, so apply fixed
  precedence: the **uniquely-binding** table wins; on a tie, order **`koi` > `k2pandc` > `toi`** (name-join exact matches
  beat a TESS period bind). Tested.
- **Host with an FP TOI but zero confirmed `ps` planets** — no planet record exists (host → `coverage.zero_planet`,
  `:446`). Surface the survey disposition as a **host-level note in the coverage block**, so the FP isn't invisible.
  (The selected anchor HD 148193/TOI-1836 *does* have a confirmed planet, so validation #1's per-planet path is
  exercised; this rule covers the orphan case.)

**Documented asymmetry (WB Q1a boundary, acceptable):** name-join reaches only *confirmed/named* Kepler/K2 planets → the
per-planet signal **corroborates confirmed** and will **not** surface a **sibling FP KOI** (an FP has no `kepler_name`
and isn't a `ps` planet). TESS's TIC route **can** surface a sibling FP TOI on a confirmed host (→ `match_status:
"ambiguous"` host-note). Acceptable for the additive purpose (absence-triage primary; audit FP cases are all RV → `null`).
- **Host-level sibling-FP sweep — IN SCOPE (Greg approved 2026-08-20).** A best-effort sweep to surface Kepler/K2
  **sibling FPs** (an FP KOI / K2 candidate on a host that *also* has a confirmed planet) as a **host-level note** — the
  Kepler/K2 analogue of what the TESS TIC-join already does. Mechanism: pivot on the `kepid` / `epic_hostname` carried by
  the confirmed-match rows already fetched → a second batched query returning **all** dispositions for those host ids
  (incl. FP/REFUTED siblings that have no `kepler_name`) → attach the non-confirmed ones as a host-level coverage note
  (never a per-planet code). Fall back to SIMBAD KIC/EPIC designations where no confirmed pivot exists. Best-effort +
  degrade-to-null, like the primary sweep.

**Batching + best-effort:** three extra TAP queries per run (not per host): `toi WHERE tid IN(...)`,
`cumulative WHERE kepler_name IN(...)`, `k2pandc WHERE pl_name IN(...) OR k2_name IN(...)`. Chunk at `_IN_CHUNK=100`.
Wrap each in the established **degrade-to-`null` + coverage note** pattern (the `_enrich_full` degradation *style*,
`:712-737`, but executed inside the new both-scopes post-pass — not inside `_enrich_full` itself) — a survey-table
failure never breaks the primary `ps` pull. Add a `survey_disposition` summary to the Mode-A coverage block (`:452-465`)
— per-catalog match counts + any fetch failures — so degradation is visible, never silent.

**Validation (spec §CR-10.1 = WB re-gate):**
1. A TOI marked `FP` → `disposition_code="FP"` — **anchor: TOI 1836.02 on HD 148193 clean-binds to confirmed TOI-1836 c**
   (verified live; red-team blocker #1 closed — a clean per-planet-FP case provably exists, not merely an FP host).
   Host-ambiguous branch anchor: TOI 2084.02.
2. A `koi_disposition="CONFIRMED"` KOI → `CONFIRMED` (anchor: **Kepler-10** b/c; backup Kepler-22 b).
3. RV-only **HD 69830 b** → `survey_disposition: null` (not error).
4. RV FPs **GJ 832 c, HD 102365 b** → `null`.

**Tests:**
- **Offline** (`test_exoplanet_batch.py`, `Cr10SurveyDispositionTest`): monkeypatch `_query_tap` so `fake_query` returns
  synthetic `toi`/`cumulative`/`k2pandc` rows keyed on `table`. Assert: TESS clean-period bind (`matched`, **explicit
  FP-code**); TESS ambiguous (`ambiguous` + null code + note, no tier move); Kepler/K2 name bind incl. the **`k2_name`
  alias** arm; `null` for RV-only (no note); `REFUTED`/blank handling; **multi-catalog precedence**;
  **FP-TOI-with-zero-`ps`-planet** orphan; **Mode-B present-but-null**; **period-tolerance boundary** (just-inside vs
  just-outside); best-effort degradation (survey query raises → null + coverage note, primary pull intact) (red-team #8).
- **Live** (`test_query_exoplanet_batch_live.py`, `SPACE_APP_RUN_LIVE=1`): the 4 spec anchors + Kepler-10 + the echoed
  FP-TOI **1836.02** — pin exact ids/periods (only 3 FP TOIs live on `ps` hosts).

---

## 4. CR-10.4 — `detection-completeness` archive-M★ preference

**Goal:** prefer archive/measured M★ over the sp-type→mass estimate for floor scaling (RV/astrometry ∝ √M★).
`detection-completeness --star "HD 69830"` → `star_mass_solar` **equal to what `planetary-systems-batch` reports**
(≈0.86), `star_mass_provenance="archive"`. Manual `--star-mass-solar` supersedes.

**Files:** `query.py` (`cmd_detection_completeness`, `--star` path `:1116-1137`), `core/detection.py` (`_resolve_star_mr`
`:169-181`, non-MS branch `:283-296`, output `:396-398`), `core/exoplanet_batch.py` (a thin shared M★ reader),
`tests/test_detection.py`, `tests/test_query_detection.py`, `docs/integration.md`. `core/detection.py` stays **free of a
`databases`/archive import** (pure-math) — the fetch happens in the `query.py` wrapper.

**Current behavior:** detection.py is pure-math; even `--star` resolves via SIMBAD (no mass) and backfills only
`sp_type`/`app_mag`/`distance_pc` (`query.py:1118-1128`). M★ is always the sp-type estimate (`_MS_MASS_RADIUS`,
`detection_tables.py:133-136`; G=0.95). No mass-provenance field today.

**Design:**
1. **`query.py` `--star` path — reuse the batch path, not a `pscomppars` re-implementation (red-team #6).** `compare_stars`
   reads `pscomppars` top-1; batch reads `ps` + `default_flag=1` — they can diverge for multi-reference hosts, and a
   `databases.py` helper can't import `exoplanet_batch`'s `_host_arms`/`_query_ps_in` without a cycle. So fetch M★ (and
   `st_rad`, needed for #5) via a thin `ps`+`default_flag=1` reader living in / imported from `core/exoplanet_batch.py`
   that applies **batch's own `_stellar` aggregation/ordering** — or call `compute_exoplanet_batch(hosts=[star],
   field_scope="core")` and read `hosts[0]["mass_solar"]`/`stellar_param_sources`. `query.py` already imports
   `exoplanet_batch`, so no cycle. Guarantees `detection` == `batch`; flag divergence rather than hard-code 0.86.
   Best-effort: archive miss / network fail → fall through, no error.
2. **Precedence:** manual `--star-mass-solar` **>** archive `st_mass` **>** sp-type estimate.
3. **New param + output field:** `compute_detection_completeness(..., star_mass_provenance=None)`; report
   `star_mass_provenance ∈ {"manual","archive","sp_type_estimate"}` beside `star_mass_solar` (`:397`). **Track provenance
   in BOTH the MS (`_resolve_star_mr`) and non-MS (`:283-296`) branches, and default to `sp_type_estimate` when mass
   falls through to the table** (red-team #7); report it even when `m_star is None`. Wrapper↔core split: the wrapper
   decides `manual > archive` and passes `star_mass_provenance`; the core overrides to `sp_type_estimate` when no mass
   was passed.
4. **Non-MS host — no regression (red-team #5).** Today a non-MS `--star` host with no manual mass gracefully
   flags/skips (`detection.py:314-324`); the non-MS branch (`:283-289`) *errors* unless it has **both** mass and radius.
   So **only inject archive mass when the host is MS (`host_class is None`)**; for a non-MS host, inject archive mass
   **only if archive `st_rad` is also present** (both → the existing explicit-M/R path), else keep the current
   graceful-skip. Never let an archive **mass-only** injection turn a graceful-skip into the `:287-289` error.

**Output shape (additive):** `star_mass_provenance` string; `star_mass_solar` now prefers archive when available.

**Validation (spec §CR-10.4 = WB re-gate, self-consistency with batch):** `detection-completeness --star "HD 69830"` →
`star_mass_solar` = batch's value (≈0.86), `star_mass_provenance="archive"`. No-archive star → `sp_type_estimate` (no
regression, G2V→0.95 kept). `--star-mass-solar 0.5` → `manual`.

**Tests (red-team #8):** offline unit tests for precedence + provenance by passing `star_mass_provenance`/mass directly to
the core (suite stays offline-clean); add a `provenance="sp_type_estimate"` assertion on the existing sp-type path
(`test_sp_type_resolves_mass_radius:89` checks value only today); provenance in the non-MS-with-explicit-M/R branch; the
**non-MS + archive-mass-only regression** (must NOT error, `sp_type="K0III"` + `--star`); keep
`test_sp_type_resolves_mass_radius` green. Live anchor (`SPACE_APP_RUN_LIVE=1`) `--star "HD 69830"` → equals batch's
value / `archive`, and a divergence-flag check.

---

## 5. Build sequence & quality gate

1. **CR-10.2** → offline `nuclear` tests.
2. **CR-10.1** → offline + live anchors (FP TOI 1836.02 + Kepler-10).
3. **CR-10.4** → offline + live anchor.
4. **Full offline suite** `venv/bin/python -m pytest -q` (baseline 2955 pass / 55 skip / 0 fail — must stay green). Then
   `SPACE_APP_RUN_LIVE=1` for new live anchors.
5. **Code-review gate (Gate-B, per CR-8/CR-9):** before "ready-for-re-gate", review the diff (`/code-review` or a review
   agent) — cross-match/period-bind correctness, the domain-split not regressing age-out or the lower edge, the CR-10.4
   precedence chain + non-MS non-regression + batch-equality, best-effort degradation, present-but-null discipline, no
   fulfilled-behavior drift. Fix findings, re-run suite.
6. **Post to WB** (per-item re-gate-ready, echoing the FP-TOI anchor). WB re-gates on the sister venv; Greg signs one
   FULFILLED flip for the three-item fire.
7. **Docs:** update `docs/integration.md` (three subcommand contracts) + `CLAUDE.md` blurb; on fulfilment move this plan
   to `completed_plans/`.

---

## 6. Self-test command reference

```bash
# CR-10.2
venv/bin/python query.py nuclear-inventory --fe-h 0.45 --age-gyr 5 --eu-h 0
venv/bin/python query.py nuclear-inventory --fe-h 0.55 --age-gyr 5 --eu-h 0     # fissile ≡, not voided
venv/bin/python query.py nuclear-inventory --fe-h 0.60 --age-gyr 5 --eu-fe 0.2  # feh_extrapolation:true on heat; domain_ok not False-from-feh
# CR-10.1 (live)
SPACE_APP_RUN_LIVE=1 venv/bin/python query.py planetary-systems-batch --hosts "Kepler-10" --fields core   # CONFIRMED KOI b/c
SPACE_APP_RUN_LIVE=1 venv/bin/python query.py planetary-systems-batch --hosts "HD 148193" --fields core    # TOI-1836 c → disposition_code FP
SPACE_APP_RUN_LIVE=1 venv/bin/python query.py planetary-systems-batch --hosts "HD 69830" --fields core      # RV-only → survey_disposition null
# CR-10.4 (live)
SPACE_APP_RUN_LIVE=1 venv/bin/python query.py detection-completeness --star "HD 69830"   # star_mass_solar ≈0.86 / archive (== batch)
venv/bin/python query.py detection-completeness --sp-type G2V --app-mag 6 --distance-pc 10 --star-mass-solar 0.5  # manual overrides archive (must include mag/distance — WB MSG 093 doc nit)
```

---

## 7. Risks & open items

- **Red-team review incorporated (2026-08-20)** — 12 findings folded: blocker #1 (validation-#1 satisfiability) **closed
  by the verified clean-bind anchor TOI 1836.02**; CR-10.1 insertion mechanism corrected to a two-phase init+post-pass
  (#2); multi-catalog precedence (#3) + orphan-host handling (#4) added; CR-10.4 M★ fetch re-routed through the batch
  path to avoid divergence + a circular import (#6), non-MS regression guarded (#5), provenance tracked in both branches
  (#7); test lists augmented (#8/#10). Confirmed sound on age-out hardness, lower-edge, tri-state, and no-drift dimensions.
- **WB adjudications folded (MSG 089)** — cross-match method, three-state binding, anchors, `koi_disposition`,
  present-but-null, per-reference `st_mass` all resolved. **No open blockers.**
- **Non-default archive solutions (CR-10.4)** — use batch's aggregation (default_flag=1); match batch, flag divergence,
  never hard-code 0.86.
- **Host-level sibling-FP sweep (CR-10.1)** — **IN SCOPE** (Greg approved 2026-08-20); best-effort host-level note,
  degrade-to-null.
- **No fulfilled-behavior drift** — single-host `planetary-systems`, existing disposition/limits blocks, the nuclear
  fissile fraction, and detection's sp-type path stay byte-identical where untouched.
- **Live-test flakiness / 8 GB box** — live anchors gated on `SPACE_APP_RUN_LIVE`; offline suite fully green +
  memory-safe (no heavy dust load).
- **Genuine per-planet `ambiguous` path is offline-tested but LIVE-unexercised** (WB MSG 093 coverage note) — a real
  `ps` planet period-matching ≥2 TOIs has no anchor in the current archive; `test_exoplanet_batch.py` mocks it, but no
  live anchor hits it. Shipped as-is; recorded as offline-verified, not live-verified.

## 8. Done criteria

Per item: spec validation passes on the live tool; offline suite green (+ new tests); code-review clean; WB independent
re-gate GREEN on the sister venv. Bundle: Greg's one FULFILLED flip → commit + push; docs updated; plan → `completed_plans/`.

---

## Appendix — Decisions for Greg's review

- **APPROVED to build (Greg 2026-08-20).** Design fully specified, WB-cleared, red-teamed; build in progress.
- **Small calls (resolved by Greg 2026-08-20):**
  1. **Host-level sibling-FP sweep** (CR-10.1 Q1a) — **BUILD IT** (in scope).
  2. **TESS period-match tolerance** ≈1–2% relative — **approved** (pin ~1.5% in build).
  3. CR-10.1 `survey_disposition` tier — **CORE-TIER** (Greg 2026-08-20; matches WB Q3 confirmation — no round-trip).
- **What ran while you were out:** live NASA-schema verification, FP-anchor selection (TOI 1836.02 verified), and a
  red-team of this plan — all read-only; **no `core/` code touched.**
