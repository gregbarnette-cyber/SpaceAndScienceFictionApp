# PHASE CR-10 SECOND FIRE — Implementation Plan (CR-10.3 + CR-10.5)

**Status:** ✅ **FULFILLED 2026-08-22** (Greg signed the one-shot flip, WB MSG 102; WB re-gated GREEN both sides — MSG 099 + 101, incl. the Pollux fix + GJ 1214 Teff-null control). Option **(a) only** (no L_bol seed — §3). Full offline suite **3037 passed / 70 skipped / 494 subtests / 0 fail**; `/code-review high` clean (2 fixed). **Commit: HELD for Greg's MANUAL commit+push** (Greg commits himself; the working tree is ready). Includes a disclosed pre-existing **SB9-resolver fix** (fulfilled CR-2/CR-3 behavior change — a follow-up sweep of any CR-2/CR-3 card that recorded "no SB9 orbit/single" is worthwhile). **Pollux #2 (WB MSG 099):** the evolved self-flag is now Teff-independent (structured on the region-error branch, not just a warning) — `luminosity_class`/`evolved_star_flag` fire for a null-Teff evolved star, `luminosity_consistency` null.

**Build progress (2026-08-22):** Step A (CR-10.3) ✅ · Step B (CR-10.5 Part 1) ✅ · Step C (CR-10.5 Part 2 + `stability_from_solutions` refactor) ✅ · tests ✅ · docs (integration/testing) ✅ · **Step B0 live consistency anchor = HD 185351** (FLAME L_bol≈14.8 L☉, calc_L≈1.16, ratio 0.078 → flagged) ✅ · full offline suite **3033 passed / 60 skipped / 494 subtests / 0 fail** ✅ · Gate-B code review ✅ (fixes folded, below).

**Gate-B review (general-purpose second opinion; /code-review to run as the authoritative gate on the final diff):** 1 SHOULD-FIX + 3 NITs, all addressed. (1) **[SHOULD-FIX] bad `--rv-precision-catalog` path now validated even with a manual `--rv-precision-ms`** (WB Q2 "loud on a bad path") — `query.py cmd_detection_completeness` loads/validates whenever a path is passed; +test `test_bad_catalog_path_loud_even_with_manual_override`. (2) reverted the manual-RV `floor_source` to `"per-star override"` (consistent with transit/astrometry; `floor_provenance` is the machine signal). (3) `multiplicity_basis` helpers now handle `visual_period` + label `wds`→`WDS`. Clean dimensions confirmed: parser, null-handling, **byte-identical `stability_from_solutions`**, graceful degradation, MS-additivity.

**SB9-resolver fix (discovered during live B0/Spica verification — DISCLOSE to WB):** `binary-orbit`'s SB9 orbits lookup used a **bare** VizieR filter `Seq = {seq}` → `{"Seq":"766"}`, which VizieR does NOT exact-match on a numeric column (returns 0). Fixed to the passthrough `Seq:={seq}` → `{"Seq":"=766"}` (verified: `Seq = 766`→0, `Seq:=766`→Spica orbit Per=4.0145). This is a **pre-existing bug in the shared resolver behind fulfilled CR-2/CR-3** — `binary-orbit`/`multiplicity`/`binary-stability-auto` were silently dropping SB9 orbits; they now return them (Spica → `multiple/sb`, `SB9 seq 766 (P=4.01 d, SB2)`). **The cone radius (`_SB9_CONE_DEG`) was NOT the bug** — a mid-debug "0.006° returns empty" reading was **astroquery HTTP-cache noise** (it caches transiently-empty/throttled responses for ~7 days; `~/.astropy/cache/astroquery/`), confirmed by a clean-cache paced retest (0.006° reliably returns Spica). Cone left at 0.006°. **Cache caveat for WB re-gate:** a throttle-induced empty can be cached; if a live anchor shows unexpectedly absent, clear the astroquery cache + re-run. (Potential app-wide hardening follow-up: retry-with-cache-bypass on an empty catalog result — not part of this fire.)
**Source contract:** `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR10-detection-floor-and-survey-disposition.md` (§CR-10.3, §CR-10.5).
**Coordination:** channel MSG 095 (hand-off) → MSG 096 (APP Qs) → **MSG 097 (WB adjudication — Q1/Q2/Q3 + all "how" decisions CONFIRMED)**.
**Directive:** build **BOTH** items, **full scope, no staging / no v2 / no defer** (`wb-cr-build-everything-no-defer`). CR-10.6 stays **DROPPED** (not touched).

**Plan-review pass (2 agents, folded in before this draft was finalized):** contract-completeness + codebase-fit. **No code-level BLOCKERs** (all seams/signatures/guarding tests verified real). One design BLOCKER fixed — the `Ia-Iab` compound luminosity token needs a **new** parser, not `detection.py`'s single-token regex (§2.1.1). SHOULD-FIXes folded: `region_basis` present on all branches (§2.1.3); the "one shared Gaia call" is a real refactor of the CR-5 age_population path + gated to avoid an always-on fetch (§2.1.2, §5.2); the Part-2 winning-solution pick reuses existing tier ordering, not an invented cross-source grade (§2.2.2); `stability_from_solutions` carries the full byte-identity signature (§2.2.3); **the `test_report._patched` harness must gain a `binary_orbit` patch or offline tests go live** (§2.2.3, §4 Step C, §5.3a). NITs folded (§1.4 floor_provenance-on-non-applicable + floor_kind phrasing; §2.2.4 #7 "verdict unchanged").

WB adjudication locked (MSG 097):
- **Q1** — `floor_provenance` reflects the **true tier per method**: `manual` when *that method's own* override is supplied, `catalog` only ever on `rv`, else `generic-3a`.
- **Q2** — `--rv-precision-catalog <path>` **REPLACES** the internal seed wholesale; a bad path / malformed-top-level file → **curated `{"error"}`** (never silent fallback to seed); a malformed **single row** in an otherwise-valid file → skip best-effort.
- **Q3** — build **(a)** Gaia FLAME + graceful-null. Validation #4 **amended** (see §CR-10.5 acceptance). Option **(b)** (a seeded L_bol for Polaris/Betelgeuse) is a **Greg decision at approval only** — WB recommends **against** it (Betelgeuse L_bol genuinely disputed); default build is (a).

---

## 0. Scope, non-goals, invariants

**In scope (two independent `query.py` items):**
1. **CR-10.3** — `detection-completeness` tier-2 per-star RV-precision auto-lookup (new catalog reader + precedence + `floor_provenance`).
2. **CR-10.5** — `dossier` robustness bundle: **Part 1** luminosity-class region guard (F1/OQ-SA-LUM1) + **Part 2** multiplicity-flag cross-check (F3). Both edit the one `dossier` command.

**Non-goals / must-not-touch:**
- CR-10.6 (measured-atmosphere) — do not build.
- `compute_star_system_regions_from_simbad` (`core/regions.py`) region VALUES must stay **byte-identical** — the CR-10.5 guard lives in the **`report.py` dossier layer**, so opts 8/9 + the GUI region features and `star-regions` are unchanged.
- The single-host `planetary-systems` / `pscomppars` paths, and all CR-8/9/10.1/10.2/10.4 outputs — untouched.
- `detection.py`'s existing `_host_class`/`_LUM_CLASS_RE` (CR-6) — **reuse**, do not refactor its behavior (guard by tests).

**Cross-cutting invariants (project contract):**
- Self-validating: curated `{"error": str}` (exit 1), never a raw traceback for a foreseeable bad input; argparse for bad args (exit 2).
- Never fabricate data: a value we cannot source is `null` + a stated reason, never a silent 0 or an invented number.
- Network only where already paid for (SIMBAD/NASA/Gaia/VizieR live paths); offline tests never hit the network; live anchors gated by `SPACE_APP_RUN_LIVE=1`.

---

## 1. CR-10.3 — `detection-completeness` per-star RV-precision auto-lookup

### 1.1 Behavior (contract)

RV-floor selection precedence, per the locked `rv-precision-catalog.json` contract:
1. **manual** `--rv-precision-ms <X>` (always supersedes) → `floor_provenance="manual"`.
2. **catalog** — a per-star row matched in the RV-precision catalog → `floor_provenance="catalog"`.
3. **generic-3a** — the existing `max(photon[mag], jitter[sp_type, activity])` 3a default → `floor_provenance="generic-3a"`.

`floor_provenance` is **per method** (Q1): `manual` on any method whose own override is supplied (`rv` / `transit` / `astrometry` / `imaging`), `catalog` only ever on `rv`, else `generic-3a`. Transit/astrometry/imaging never get `catalog`.

`floor_source` string names the tier + provenance, e.g.
- catalog: `"per-star catalog: HD 69830 residual RMS 0.81 m/s [Lovis 2006]"`
- manual: `"manual override: 0.5 m/s"`
- generic: `"3a-default RV (mag≤6.0): max(precision …, jitter …) = 1.5 m/s"` (unchanged).

### 1.2 Catalog data + reader (new)

**Internal seed (shipped, flag-less default).** New module **`core/rv_precision_tables.py`** — a Python dict mirroring the WB JSON's authoritative shape, containing **only the HD 69830 anchor row** (0.81 m/s, Lovis 2006). This is the flag-less default catalog. (Mirrors the `*_tables.py` bundled-static-data pattern: `detection_tables.py`, `radiation_tables.py`, etc.)

**External file (Q2 = REPLACE).** New flag `--rv-precision-catalog <path>` on the `detection-completeness` subparser. When passed, the tool reads that JSON and **uses it wholesale** (the internal seed is ignored — no merge). Contract details:
- Parse `{"stars": [ {id, main_id, aliases[], rv_precision_ms, floor_kind, citation, source, confidence, …}, … ]}`.
- **Bad path / not-readable / not-valid-JSON / no `stars` array → curated `{"error": "…"}`** (Q2 — loud, never silent fallback to seed).
- A malformed **single row** (missing/non-numeric `rv_precision_ms`, or missing `main_id`) → **skip that row**, continue; the primary computation is never touched.
- Reader lives in `core/rv_precision_tables.py` as `load_rv_precision_catalog(path=None) -> {"stars":[…]} | {"error":str}` (path `None` → the internal seed dict).

### 1.3 Match logic (my "how", WB-confirmed)

- Match key: the resolved star's **whitespace-collapsed, case-insensitive** identifier set = `{norm(main_id)} ∪ {norm(v) for v in designations.values() if v}` vs each catalog row's `norm(main_id)` ∪ `{norm(a) for a in aliases}`. First matching row wins.
- `norm(s)` = collapse internal whitespace runs to a single space, `.strip()`, `.upper()`. (Handles SIMBAD `"HD  69830"` double-space vs `"HD 69830"`.)
- The catalog tier fires **only on the `--star` path** — SIMBAD resolution supplies `main_id` + `designations` there, exactly as CR-10.4's archive-M★ does. A bare `--sp-type/--app-mag/--distance-pc` invocation (no star name, no main_id) stays `generic-3a`.
- Precedence guard: manual `--rv-precision-ms` short-circuits before the catalog lookup (no wasted match work).

### 1.4 Code changes (CR-10.3)

**`core/rv_precision_tables.py` (new)** — the seed dict + `load_rv_precision_catalog(path=None)` + a `match_rv_precision(catalog, main_id, designations) -> row|None` helper (pure, offline-testable).

**`core/detection.py` — `compute_detection_completeness`:**
- Add param `rv_precision_provenance=None` (like `star_mass_provenance`). When `rv_precision_ms` is passed:
  - `floor_provenance = rv_precision_provenance or "manual"` (query.py passes `"catalog"` on a catalog hit; a bare direct call defaults to `"manual"`).
  - `floor_source` string built per provenance (manual vs catalog wording; catalog wording carries the row's `main_id`/`floor_kind`/value/`citation` — passed in via a small `rv_precision_meta` param, see below).
- Add `rv_precision_meta=None` (the matched catalog row dict, for the `floor_source` string) — only used to compose the catalog `floor_source`. The catalog `floor_source` renders `floor_kind` via a small phrasing map `{"measured_residual_rms":"residual RMS", "yu2018_fit":"oscillation-jitter (Yu 2018 fit)"}` (fallback: the raw `floor_kind`), giving `"per-star catalog: HD 69830 residual RMS 0.81 m/s [Lovis 2006]"` (plan-review NIT #6).
- **Emit `floor_provenance` on every method entry:** `rv` → manual/catalog/generic-3a; `transit`/`astrometry` → `manual` when their `*_precision_*` override is set else `generic-3a`; `imaging` → always `generic-3a` (confirmed: imaging has **no** per-star override arg today — verified `detection.py:388-398`). On a **non-applicable** entry (`floor_source is None`, e.g. a not-covered transit target) → **`floor_provenance: None`** (mirrors `floor_source`) (plan-review NIT #5).
- Keep the existing `jitter_advisory` / non-MS-host behavior unchanged.

**`query.py` — `cmd_detection_completeness`:**
- Add `args.rv_precision_catalog` (path) handling. On the `--star` path, after SIMBAD resolve (`sl`), if `args.rv_precision_ms is None`:
  - `cat = rv_precision_tables.load_rv_precision_catalog(args.rv_precision_catalog)` — if `"error"` in cat → `_out(cat); return`.
  - `row = rv_precision_tables.match_rv_precision(cat, sl["main_id"], sl["designations"])`.
  - If `row`: pass `rv_precision_ms=row["rv_precision_ms"]`, `rv_precision_provenance="catalog"`, `rv_precision_meta=row`.
- Manual `--rv-precision-ms` still supersedes (short-circuit — no catalog load).
- Argparse: `p.add_argument("--rv-precision-catalog", help="Path to a WB-owned per-star RV-precision catalog JSON (tier-2 lookup). Replaces the internal seed.")`.

### 1.5 CR-10.3 acceptance (WB re-gate targets)

1. `detection-completeness --star "HD 69830" --rv-precision-catalog <seed.json>` → `rv` `floor_source` names the Lovis-2006 row, floor ≈ **0.81 m/s**, `floor_provenance="catalog"`; its three confirmed planets bin easily/marginal correctly (the 3b §5.4 pessimistic self-test no longer fires spuriously).
   - Same result **flag-less** (`detection-completeness --star "HD 69830"`) via the internal seed.
2. A star **not** in the catalog → `generic-3a` fallback, `floor_provenance="generic-3a"` — **no regression** vs today's numbers.
3. `--rv-precision-ms 0.5` on any star → `floor_provenance="manual"`, overrides both tiers.
4. **(Q1 extra)** an overridden non-RV method (`--transit-precision-ppm …`) → that method's `floor_provenance="manual"`; an untouched method → `generic-3a`; `catalog` never appears off-`rv`.
5. **(Q2 extra)** `--rv-precision-catalog /nonexistent.json` → curated `{"error"}` (not a silent seed fallback); a valid file with one malformed row still serves its good rows.

---

## 2. CR-10.5 — `dossier` robustness bundle

Both parts edit **`core/report.py`** only (the dossier layer). `regions.py`/`binary.py` core math is reused, not modified (Part 2 may need a tiny, test-guarded seam — see §2.2.4).

### 2.1 Part 1 — luminosity-class-aware region guard (F1 / OQ-SA-LUM1)

#### 2.1.1 Luminosity-class token parser (NEW parser — not a drop-in `_LUM_CLASS_RE` reuse)

> **Plan-review BLOCKER (fixed here).** `detection.py`'s single-token `_LUM_CLASS_RE`'s `(?:ab|a|b|0)?` matches **one** suffix and stops — `M1-M2Ia-Iab` yields `"Ia"`, not the WB-required `"Ia-Iab"`. So this is a **new, purpose-built parser** in `core/shared.py` (it *borrows* the `[^A-Za-z]` boundary-anchoring idiom that makes `IIIb`→`III` safe, but is not the same regex). `detection._host_class`/`_LUM_CLASS_RE` (CR-6) are **left untouched** — pinned by `test_detection`.

Add `luminosity_class(sp_type) -> (token: str|None, evolved: bool)` in **`core/shared.py`** (`report.py` must add `from core import shared`).

- **UNIT** = one luminosity token: `(?P<core>VII|VI|IV|V|III|II|I)(?P<sub>ab|a|b|0)?` (alternation longest-first so `III` wins over `I`).
- **SPAN** = the first boundary-anchored run of hyphen/slash-joined units: `(?<![A-Za-z])UNIT(?:[-/]UNIT)*`. Anchoring the *first* unit after a non-letter keeps the `M1-M2` spectral hyphen out (the run starts at `Ia`, then `[-/]UNIT` consumes `-Iab`). `token_raw` = the verbatim matched substring.
- **Normalization → returned `token`:**
  - If the span is **compound** (contains `-`/`/`, e.g. `Ia-Iab`) → return it **verbatim**.
  - Else a single unit: if `core == "I"` → return the whole unit (keep the suffix: `Ia`/`Iab`/`Ib`/`I`); if `core ∈ {II,III,IV,V,VI,VII}` → return **`core` only** (drop the sub-suffix: `IIIb`→`III`).
- **`evolved`** = any unit in the span has `core ∈ {I, II, III, IV}` (supergiant / bright giant / giant / subgiant). `V`/`VI`/`VII`/no-token → `evolved=False` (MS dwarf / subdwarf / WD — not this guard's concern).
- Worked cases (pinned in `test_shared_luminosity_class`): `F8Ib`→(`"Ib"`, True) · `K0IIIb`→(`"III"`, True) · `M1-M2Ia-Iab`→(`"Ia-Iab"`, True) · `K0III`→(`"III"`, True) · `G6V`→(`"V"`, False) · `G8:V`→(`"V"`, False, colon satisfies the boundary) · `DA2`/`""`/None→(None, False) · **boundary test `IIIb`≠`Ib`**.

#### 2.1.2 L_bol source (Q3 = FLAME + graceful-null)

> **Plan-review SHOULD-FIX (addressed here).** The "share one Gaia call" is a real **refactor of the working CR-5 `_age_population_data_star` path** (which today calls `catalog.gaia_astrophysical(star=star)` at `report.py:586` — by name, re-resolving SIMBAD internally), not a free memo. And it adds a **new fetch to the always-computed regions section**. Both are handled explicitly below and re-scored in §5.

- New helper `_gaia_astro(simbad, memo)` in `report.py`: resolve the Gaia source_id via the existing **`binary.gaia_source_id_from_designations(simbad["designations"])`** helper (not brittle literal indexing), call `catalog.gaia_astrophysical(source_id=…)` **once**, cache on `memo` (a dict created in `_assemble_star`). Returns the FLAME `parameters` (or `None`). L_bol = `parameters["lum_flame"]` (L_sun), `None` when absent.
- **Refactor `_age_population_data_star` to accept the shared FLAME result** (from `memo`) instead of its own `gaia_astrophysical(star=star)` call — so a full dossier makes **one** Gaia call, not two. Guarded byte-for-byte by `test_report`'s age_population coverage (extend the harness to stub `catalog.gaia_astrophysical` if it isn't already).
- **Cost gate:** `_gaia_astro` is invoked only when `"regions" in requested or "age_population" in requested` — so a cheap `--sections identity` dossier pays **no** new Gaia call. (Regions itself is computed unconditionally today; the FLAME fetch is what we gate.)
- FLAME is genuinely null for saturated supergiants (Polaris/Betelgeuse) → `L_bol=None` → the consistency block reports `{calc_L, L_bol:null, ratio:null, flagged:null}` (never a fabricated ratio).

#### 2.1.3 The guard (in `report.py`, `_assemble_star` regions section, replacing lines ~815-823)

Flow for a real star:
1. Call `compute_star_system_regions_from_simbad(simbad)` as today (its region values stay byte-identical for MS stars).
2. Parse `token, evolved = shared.luminosity_class(simbad.get("sp_type"))`.
3. Compute the **consistency diagnostic** whenever the region computation succeeded (so `stellarRadius`/Teff exist): `calc_L = stellarRadius² × (Teff/5772)⁴` (CR constant 5772 — recomputed here, not `reg["calculatedLuminosity"]` which uses 5778); fetch `L_bol` (§2.1.2); `ratio = calc_L / L_bol` when `L_bol` present; `flagged = (ratio > 2 or ratio < 0.5)` else `flagged=None`. Emit `luminosity_consistency = {calc_L, L_bol, ratio, flagged}`.
4. Branch on `evolved` and `--force-ms-inversion`:
   - **evolved and NOT `--force-ms-inversion`:** **refuse** the MS-inversion for the region OUTPUT. `data["regions"]` = additive evolved block: `{luminosity_class: token, evolved_star_flag: True, region_basis: "MS-inversion refused: sp_type luminosity class <token> → regions from literature L only (or withheld)", ms_inversion_withheld: True, luminosity_consistency}`. The bogus MS mass/radius/regions are **withheld** (not presented as authoritative). If `L_bol` is present, additionally emit an **L-driven HZ** (from `L_bol` via `compute_habitable_zone`/Kopparapu) as the `habitable_zone` section basis; else `habitable_zone` status → `("note", "MS-inversion refused for evolved star; no L_bol available for L-driven HZ")`.
   - **evolved and `--force-ms-inversion`:** proceed with the MS regions as today, but still attach `luminosity_class`, `evolved_star_flag: True`, `luminosity_consistency`, and a `region_basis: "MS-inversion forced (--force-ms-inversion) despite evolved class <token>"`.
   - **not evolved (MS dwarf / `V` / null token):** today's behavior, byte-identical region values, plus additive `luminosity_class: token|null`, `evolved_star_flag: False`, **`region_basis: "MS mass-inversion (main-sequence)"`** (present on *every* branch so there is no null-vs-absent re-gate ambiguity — plan-review SHOULD-FIX #3), and `luminosity_consistency` (when `L_bol` available → `flagged` bool; else `L_bol/ratio/flagged` null).
5. If `compute_star_system_regions_from_simbad` returned an `"error"` (as today — null/`V`-only sp_type, missing Teff/vmag/plx): keep today's `warn` status, **but** if the sp_type still carries an evolved luminosity token, add `luminosity_class`+`evolved_star_flag` to the warn note so an evolved star refused for a *different* reason is still labelled. (Additive; does not change the warn path.)

**`--force-ms-inversion`** — new boolean flag on `dossier` subparser, threaded `cmd_dossier → build_system_dossier → _assemble_star`.

#### 2.1.4 Part 1 acceptance (WB re-gate — Q3-amended #4)

1. **Polaris** (`F8Ib`) / **Betelgeuse** (`M1-M2Ia-Iab`) → `evolved_star_flag=True`, MS-inversion **refused** (no bogus 7.8 / 19.2 M☉), `luminosity_class` = `Ib` / `Ia-Iab`.
2. **Pollux** (`K0IIIb`) → `luminosity_class="III"` (**not** `Ib` — token-boundary test) → `evolved_star_flag=True`.
3. Normal MS dwarf **HD 20794** (`G6V`) → `evolved_star_flag=False`, region **values byte-identical** vs today (additive keys only), `luminosity_class` ∈ {`V`, null}.
4. **(Q3-amended)** consistency trip:
   - (i) On a **FLAME-covered** star whose `calc_L` vs `L_bol` disagree >2× → `luminosity_consistency.flagged=True`. **APP names + live-verifies the concrete anchor** (see §4 Step B0); WB re-gates that FLAME covers it and the trip fires.
   - (ii) A clean MS star with a FLAME `L_bol` → `flagged=False`.
   - (iii) **Polaris/Betelgeuse** → `luminosity_consistency.L_bol=null`, `ratio=null`, `flagged=null` (no fabricated ratio) — still refused-inverted via the token (#1).

### 2.2 Part 2 — multiplicity-flag cross-check (F3)

#### 2.2.1 Current state

`_multiplicity_data_star(simbad, star)` (`report.py:537`) reads `simbad["multiplicity"]` (**SIMBAD otype only** — misses an SB whose primary otype is a variability class), and only escalates to `binary.binary_stability_auto` **if already** `is_multiple`.

#### 2.2.2 New behavior

Cross-check against the **same catalogs `binary-orbit` consults** (SB9 / WDS-ORB6 / Gaia-DR3-NSS `two_body_orbit`) **regardless of otype**:
- Call `binary.binary_orbit(star=star)` **once** inside `_multiplicity_data_star`.
- Derive from its `solutions[]`: `cross_multiple = any solution present`; `cross_sb = any solution whose source is spectroscopic (sb9 / an NSS SB `solution_type`) or that carries a spectroscopic `companion`.
- **Winning-solution pick — reuse existing tier ordering, do NOT invent a cross-source "highest grade"** (plan-review SHOULD-FIX): grades are scale-heterogeneous (SB9 int `binary.py:462`, NSS float `significance` `:322`, orb6 letter `:499`) and not comparable. Use the **same tier + list-order selection `_extract_stability_elements` already applies** (`binary.py:599-621`); the M0 "downweight a conflicting/low-grade solution" applies only *within* a source where grade is comparable. The `multiplicity_basis` names that same selected solution.
- `is_multiple = otype_multiple OR cross_multiple`; `sb_flag = otype_sb OR cross_sb`.
- `multiplicity_basis` = a human string from the selected solution: `source`+`seq`+`period_d`+companion/`solution_type`, e.g. `"SB9 seq 766 (P=4.01 d, SB2)"` (SB2/SB1 from the companion classifier `method`); falls back to the otype basis when no catalog solution exists.
- Keep `otype` as a secondary field.

#### 2.2.3 Stability attachment (avoid a double network call)

Today: when `is_multiple`, the block calls `binary_stability_auto(star)` (which itself re-runs `binary_orbit` at `binary.py:636`). To keep the dossier to **one** `binary_orbit` call, extract `binary_stability_auto`'s **element→Holman-Wiegert** core into a pure helper **`binary.stability_from_solutions(star_label, identity, solutions, route_tried, test_sma_au=None)`** (no network — signature carries `star_label`=`result["query"]` and `route_tried` so its output is **byte-identical** to today's `binary_stability_auto`, per plan-review NIT). Both `binary_stability_auto` (rewired to call it after its own `binary_orbit`) and `_multiplicity_data_star` (calling it on the already-fetched result) use it. Guarded by `test_binary_stability_auto`, which **patches `core.binary.binary_orbit`** (`tests/test_binary_stability_auto.py:22,94`) → the refactor is genuinely pinned. **Gate B-refactor** (§4) diffs a fixture to confirm byte-identity.
- **⚠ Offline-suite regression to prevent (plan-review SHOULD-FIX — critical):** `tests/test_report.py`'s `_patched` harness (`:146`) currently patches `binary_stability_auto` but **not** `binary_orbit`. After this change `_multiplicity_data_star` calls `binary_orbit` directly, so **every offline report test would hit the live network** unless the harness is rewired to also `patch("core.binary.binary_orbit", …)` with a synthetic solutions list. This rewire is an explicit Step-C task (§4).
- *Fallback if the extraction proves risky:* accept a second `binary_orbit` call for confirmed-multiples only (single stars still pay one) — a documented network-cost note, not a correctness issue.

#### 2.2.4 Part 2 acceptance (WB re-gate)

5. **Spica** (`HD 116658`, otype `bC*`) → `multiple=True`, `sb_flag=True`, `multiplicity_basis` names the SB9 orbit (P≈4.01 d), agreeing with `binary-orbit`.
6. Genuine single star **HD 20794** (`G6V`) → `multiple=False` (no regression).
7. A star already caught via otype `**`/`SB*` (e.g. **GJ 473**) → **verdict unchanged** (`multiple=True`). Note: `multiplicity_basis` may now be *enriched* from the otype string to a catalog basis if `binary_orbit` returns a solution — a benign addition; "unchanged" here means the verdict, not every field (plan-review NIT #7).

---

## 3. Option (b) — Greg decision at approval (do NOT build unless elected)

WB recommends **against** a seeded L_bol catalog for Polaris/Betelgeuse (Betelgeuse's bolometric L is genuinely disputed — a semiregular variable spanning a wide literature band; pinning it as "catalog data" is shaky). Build **(a)** delivers the full mechanism; #4 is validated on a FLAME-covered anchor (§4 Step B0). Per the build-everything rule, (a) **is** the complete build of what WB is asking for — (b) is an optional data seed WB is declining to pin, not a deferred feature.

**→ Greg: elect (b) or not at approval.** If elected, it's a tiny additive `l_bol_seed` map (Polaris/Betelgeuse) read exactly like the RV catalog, forcing #4 green on the two named stars; if not, build (a) as specified. Default = **(a) only**.

---

## 4. Build sequence (with code-review gates)

Order is free (two independent items); proposed:

- **Step A (CR-10.3):** `core/rv_precision_tables.py` (seed + loader + matcher) → `detection.py` param/`floor_provenance` wiring → `query.py` `--rv-precision-catalog` + catalog-tier resolve. Offline tests: `tests/test_rv_precision.py` (loader/matcher/malformed-row/replace) + `tests/test_detection.py` extensions (`floor_provenance` per method, precedence) + `tests/test_query_detection.py` (the `--star`+catalog path, curated-error path). Live anchor (gated): `tests/test_query_detection_live.py` — HD 69830 catalog hit ≈0.81 m/s.
- **Step B0 (CR-10.5 anchor pick — LIVE):** run `gaia-astrophysical` over a shortlist of FLAME-covered evolved/subgiant stars (candidates: well-studied asteroseismic subgiants/giants with a Gaia FLAME `lum_flame` and a III/IV sp_type, e.g. **η Cep (HD 198149, K0IV)**, **HD 185351 (KOI-I subgiant)**, or a fainter K-giant), confirm FLAME returns `lum_flame` AND `calc_L` (MS-inversion) vs `L_bol` disagree >2×. **Name the chosen anchor in the delivery MSG** for WB's independent re-gate. (Falls back to another FLAME-covered star if the first isn't covered.)
- **Step B (CR-10.5 Part 1):** `shared.luminosity_class` + `report.py` `_gaia_astro` share + the region guard + `--force-ms-inversion`. Tests: `tests/test_shared_luminosity_class.py` (token boundary: `Ib`/`III`/`Ia-Iab`, `IIIb`≠`Ib`), `tests/test_report.py` extensions (evolved refusal, force-hatch, byte-identical MS regions, consistency null-on-FLAME-absent, flagged bool on a stubbed FLAME L_bol). Live anchor (gated): Polaris/Betelgeuse refusal + the §B0 anchor's >2× trip.
- **Step C (CR-10.5 Part 2):** `binary.stability_from_solutions` extraction (behavior-preserving, full signature) → `report.py` multiplicity cross-check + `multiplicity_basis` (tier-order solution pick, no invented cross-source grade). **Rewire `tests/test_report._patched` to also `patch("core.binary.binary_orbit", …)`** (critical — else offline report tests go live). Tests: `tests/test_report.py` (Spica-shaped stubbed `binary_orbit` → multiple/sb_flag/basis; single-star no-regression; otype-`**` verdict unchanged), `tests/test_binary_stability_auto.py` (**unchanged** — proves the refactor is byte-identical). Live anchor (gated): Spica agrees with `binary-orbit`.
- **Step D — docs + suite:** `docs/integration.md` CR-10 block (CR-10.3 fields + the `--rv-precision-catalog` flag + CR-10.5 `luminosity_class`/`evolved_star_flag`/`region_basis`/`luminosity_consistency`/`multiplicity_basis`/`--force-ms-inversion`); fix the stale `--sections` help string (`query.py:4026`, add `multiplicity age_population disk`); fix the MSG-092 doc example (`--distance-pc`/`--app-mag`); `CLAUDE.md` CR-10 line; `docs/testing.md` new test-file entries; mark this plan BUILT. Full offline suite green.

**Code-review gates (built into the sequence):**
- **Gate B-refactor** (before merging Step C): review `binary.stability_from_solutions` extraction proves CR-3 output byte-identical (run `test_binary_stability_auto` + a diff on a fixture).
- **Gate B (Gate-B high, whole diff)** after Steps A–C: a `code-review` pass (high) over the full diff — same discipline as CR-8/9/10-first-fire — for correctness (curated-error paths, no fabricated data, region byte-identity, network-cost/double-call), reuse/simplification, and provenance-string correctness. Fold fixes; re-run offline + live anchors green.
- **Plan review** (now, pre-build): §5.

---

## 5. Risks & review focus

1. **Region byte-identity for MS stars (#3).** The guard is additive-only in `report.py`; `regions.py` is untouched. Review must confirm no MS-dwarf region VALUE changes — only new keys.
2. **New network cost.** The regions section adds one Gaia FLAME fetch (for `luminosity_consistency`) — **gated on `"regions"|"age_population" in requested`** and shared (via `_gaia_astro` memo) with `_age_population_data_star` (whose own FLAME call is refactored away), so a full dossier makes **one** Gaia call and a `--sections identity` dossier makes **none**. The multiplicity section now always calls `binary_orbit` once (even for otype-single stars) — intrinsic to the CR (the only way to catch a variability-class-primary SB; WB blessed the core-tier posture on CR-10.1).
3. **CR-3 refactor regression** (`stability_from_solutions`, full signature) — guarded by `test_binary_stability_auto` (which patches `binary_orbit`) + Gate B-refactor fixture diff.
3a. **Offline-suite regression (critical):** the `test_report._patched` harness must gain a `binary_orbit` patch (Step C) or offline report tests hit the network. Verified: `test_report.py:146` patches `binary_stability_auto` only.
3b. **CR-5 age_population refactor:** `_age_population_data_star` is rewired to read the shared FLAME result — a change to a working CR-5 path; guarded by extending `test_report`'s age_population coverage to stub `gaia_astrophysical`.
4. **Token normalization edge cases** — compound/uncertain types (`M1-M2Ia-Iab`, `K0IIIb`, ranges, colons `G8:V`). Pinned by `test_shared_luminosity_class` against the three WB validation strings + `IIIb`≠`Ib`.
5. **Catalog match false-negative** — a row whose `aliases` omit the resolved id; mitigated by matching against **all** `designations` values (WB called this "more robust than my literal main_id+aliases").
6. **L_bol anchor availability (#4-i)** — resolved by the live Step B0 anchor pick; if no shortlisted star is FLAME-covered with a >2× discrepancy, widen the shortlist before delivery.

---

## 6. Delivery

Post-build MSG to WB (per CR-8/9/10-first-fire pattern): per-item re-gate blocks (the §1.5 / §2.1.4 / §2.2.4 anchors), the **named FLAME-covered consistency anchor** (Step B0), the Gate-B review summary, and the full offline suite count. **Commit held for Greg's one FULFILLED flip** on the two-item second fire. WB independently re-gates on the sister venv; Greg signs; then commit + push (one commit) + move this plan to `completed_plans/`.
