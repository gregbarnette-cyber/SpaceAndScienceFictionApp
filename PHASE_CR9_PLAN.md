# PHASE CR-9 PLAN — Disposition & quality fields for the batch exoplanet pull

**Status: PLANNED (contract locked). Not yet built.**
Extends **CR-8** (`core/exoplanet_batch.py` / `query.py planetary-systems-batch`, FULFILLED, `94784f1`).
CR-9 is a **new, additive output-field CR** — same inputs, same modes, more fields. Nothing in CR-8 is
re-negotiated; the single-host `planetary-systems` (`pscomppars`) path stays byte-identical.

- **Contract (authority):** `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR9-disposition-quality-fields.md`
- **Negotiation:** coordination-channel MSG 067 (WB fires CR-9) → 068 (APP: 5 questions) → 069×2 (crossed:
  WB answers / APP withdraws Q2) → 070 (APP: adopt WB's rulings). All five resolved; see Locked Decisions.
- **Schema pre-check (APP, live `TAP_SCHEMA`, this session):** all 65 §3 fields exist; the ps-vs-pscomppars
  split the CR asserts is exactly right — the 8 composite fields (`pl_angsep`(+lim), `pl_tsm`, `pl_esm`, the
  four `pl_nobs_jwst_*`) are **pscomppars-only**; `soltype` is **ps-only**; everything else is in `ps`.
  No field-list renegotiation needed.
- **Why it matters:** it is the data layer for the `star_analysis` skill's **Q9 disposition/detection spine**,
  a HARD-WAIT gate on the final skill build (clean-room against the native pull, not build-then-swap).

---

## 0. Locked decisions (from the MSG 068→070 exchange)

| # | Decision | Source |
|---|---|---|
| **D1 (Q1=A)** | The bulk pull surfaces `pl_controv_flag` (per-solution) + `soltype` faithfully. The archive **overview** disposition (`Confirmed:Controversial`, e.g. GJ 667 C c) is **provably not a TAP column** — verified: c reads `pl_controv_flag=0` on all four ps solutions — so it is **out of scope for the bulk pull**; the skill owns it as targeted per-anchor LEAD re-queries over the small flagged set. The flag is a **floor** the overview/literature may tighten; load-bearing direction is under-capture. **(B) rejected.** | MSG 069(WB) Q1 |
| **D1a** | An **opt-in, non-default** per-planet overview-disposition fetch (single planet / short explicit list, **outside** the bulk path) for the skill's targeted re-queries. WB called it "welcome convenience, your call," but per the build-everything rule it **is built** — WB's only hard constraint is "**must not delay CR-9-proper**," a *sequencing* point (build it after the core, which is now done), not a licence to skip. **Technical note:** the overview disposition is **not a TAP column** (GJ 667 C c is `pl_controv_flag=0` on all solutions), so D1a needs the archive per-planet *overview* source, not `ps`/`pscomppars` — determine the mechanism at build time; if it is HTML-only with no clean endpoint, surface that to WB. | MSG 069(WB) Q1 |
| **D2 (Q2)** | `--fields core` = **Tier-1** disposition/quality (incl. `soltype` + the −1 tri-state `*lim`). `--fields full` = superset = Tier-2 + the 8 composite fields + the OEC block + the existing raw `ps` row. **All built + delivered in one build** — flag-gating is a verbosity default, **not** deferral (confirmed by both WB and Greg). The Q9 clean-room reads Tier-1 from core. | MSG 069(WB) Q2 |
| **D3 (Q3)** | Riders **trail** CR-9-proper (spec D3). **Companion CR #1** (jitter bumps): build the *structure* only; the bump **magnitude is an un-cleared LEAD** → ship an explicit, documented, **overridable placeholder flagged advisory**, no baked number (WB pins the jitter–L/M scaling in Phase 5). **3c defects**: my side = the **four code fixes CQ-7-3c-1…4** (`nuclear.py`/`nuclear_tables.py`); CQ-7-3c-5…7 are WB's model-doc amendments. | MSG 069(WB) Q3 |
| **D4 (Q4)** | Pull-behaviors #2/#3 = **best-effort + explicit coverage manifest**, **plus two hard §5 regression anchors**: #2 `GJ 667 C → b/c/e/f/g present`; #3 `26 Dra (HD 160269) → GJ 685 b surfaced under component_planets`. Everything beyond those two = best-effort, no hard gate. Gaia co-motion *binding* check stays a consumer job (not the pull's). | MSG 069(WB) Q4 |
| **D5 (Q5)** | **Batch-only.** CR-9 extends `planetary-systems-batch`; single-host `planetary-systems` (pscomppars) stays byte-identical (a single-host CR-9 need goes through the batch tool with a one-host list). | MSG 069(WB) Q5 |
| **D6** | **−1 tri-state preserved.** `*lim` fields carry the raw int `+1 upper / 0 measurement / −1 lower / null`, never collapsed to bool "has-a-limit". A dedicated int helper, **not** the existing bool `_flag()`. | CR §3 + §5.11 |
| **D7 (record shape, APP's call)** | CR-9 disposition/quality/limit fields keep their **archive column names verbatim** as keys (so §5 anchors map 1:1 and the skill's clean-room is exact). CR-8's derived architecture fields keep their existing friendly names. New keys are grouped in additive sub-blocks; existing consumers ignore unknown keys. | APP, MSG 070 |

---

## 1. Architecture

**Extend `core/exoplanet_batch.py` in place** (no new subcommand — D5; CR-9 is additive fields on the same
reader). The record builders, column sets, and helpers grow; the public entry point
`compute_exoplanet_batch(...)` signature is unchanged (same args). `query.py planetary-systems-batch` needs
**no new required flags** — `--fields {core,full}` already exists and now selects the CR-9 tiers.

Data flow per invocation:

```
Mode A (hosts)                             Mode B (filter)
  resolve each host (SIMBAD)                 build WHERE over ps
  + alias/hostname join (behavior #2)        │
  + component enumeration (behavior #3)      │
        │                                    │
        └──────────┬─────────────────────────┘
                   ▼
        ps query  → per-solution rows  (core = Tier-1; full adds Tier-2 ps cols)
                   ▼
   [--fields full only] pscomppars query keyed by pl_name  → 8 composite fields  → merge, tag source:composite
                   ▼
   [--fields full only] OEC lookup (compute_oec, allow_simbad=False; 7-day cache, cold-cache 1st-use fetch) → list + structure → SECONDARY
                   ▼
        assemble records  → coverage manifest (+ component_planets, + resolution triage)
```

**Query count:** `core` stays one ps round-trip (per IN-chunk) — unchanged cost. `full` adds one pscomppars
round-trip + OEC walks (`compute_oec` with **`allow_simbad=False`**, so no per-host SIMBAD calls; a local 7-day
cache, with a one-time GitHub fetch of the OEC gzip on a **cold cache** — so `full` is not strictly a
ps+pscomppars-only pull on first run; core is). The composite pull and OEC walk are **skipped entirely** under
`--fields core`.

---

## 2. Column-set changes (`_HOST_CORE_COLS` / `_PLANET_CORE_COLS` + new sets)

### 2a. Tier-1 → added to the **core** SELECT (per-planet, all `ps`)
`pl_controv_flag, soltype, ttv_flag, cb_flag,`
`tran_flag, rv_flag, ima_flag, ast_flag, micro_flag, obm_flag, etv_flag, ptv_flag, pul_flag, dkin_flag,`
`pl_dens, pl_denslim, pl_bmasselim, pl_masselim, pl_msinielim, pl_radelim, pl_orbeccenlim,`
`pl_orbincllim, pl_orbinclerr1, pl_orbinclerr2, pl_orbsmaxlim, pl_orbperlim, pl_orblperlim,`
`pl_imppar, pl_impparlim`
(`tran_flag` already selected by CR-8. `default_flag` already selected.)

### 2b. Tier-2 → added to the **full** SELECT only
- **per-planet (ps):** `pl_ratdor(+lim), pl_ratror(+lim), pl_insol(+lim), pl_eqt(+lim), pl_trandep(+lim),
  pl_trandur(+lim), pl_tranmid(+lim), pl_projobliq(+lim), pl_trueobliq(+lim), pl_orbtper(+lim),
  disc_year, disc_facility, disc_telescope, disc_instrument, disc_pubdate, disc_refname,
  pl_pubdate, rowupdate, releasedate, pl_ntranspec, pl_nespec, pl_ndispec, pl_nnotes`
- **per-host (ps):** `st_rotp(+lim), st_vsin(+lim), st_age(+lim), st_dens(+lim), st_nrvc, st_nphot, st_nspec,
  sy_snum, sy_mnum, sy_pmra(+err1/2), sy_pmdec(+err1/2), sy_pm, sy_plx(+err1/2), st_radv(+err1/2)`
- Under `--fields full` the SELECT is already `*`, so these arrive for free in `raw`; the plan **also promotes
  them to named keys** so `full` gives structured Tier-2, not just a raw dump. (Keep the `raw` block too.)
- **Already CR-8-native (intentionally not re-listed):** `pl_refname` (contract §3 Tier-2 "parameter reference")
  is already in `_PLANET_CORE_COLS` and surfaced as the planet `provenance` key; `st_refname` likewise → host
  `provenance`. They are delivered, not dropped — omitted from the add-list only because CR-8 already carries them.

### 2c. Composite (pscomppars, **full** only) — second query
`pl_angsep, pl_angseplim, pl_tsm, pl_esm, pl_nobs_jwst_tran, pl_nobs_jwst_e, pl_nobs_jwst_pc, pl_nobs_jwst_di`
+ per-value `*_reflink` where present. Keyed by `pl_name IN (...)` over the returned planets; merged into each
planet under a `composite` block. **`soltype` is NOT selected from pscomppars** (ps-only — a 400 otherwise).

---

## 3. Record schema (additive keys — D7: archive-named)

### 3a. `planets[]` — Tier-1 (core)
```jsonc
{
  // ...all existing CR-8 keys unchanged...
  "disposition": {                 // core
    "soltype": "Published Confirmed",
    "pl_controv_flag": 0,          // int 0/1/null (raw)
    "ttv_flag": 0,
    "cb_flag": 0,
    "detection": {                 // the 10 method flags, raw 0/1/null
      "tran_flag": 1, "rv_flag": 1, "ima_flag": 0, "ast_flag": 0, "micro_flag": 0,
      "obm_flag": 0, "etv_flag": 0, "ptv_flag": 0, "pul_flag": 0, "dkin_flag": 0
    },
    "detection_methods": ["transit","rv"]   // convenience: the flags == 1, spelled out
  },
  "limits": {                      // core — TRI-STATE ints: +1 upper / 0 meas / -1 lower / null (D6)
    "pl_bmasselim": 0, "pl_masselim": null, "pl_msinielim": null, "pl_radelim": 0,
    "pl_orbeccenlim": 1, "pl_orbincllim": 0, "pl_orbsmaxlim": 0, "pl_orbperlim": 0,
    "pl_orblperlim": 0, "pl_denslim": 0, "pl_impparlim": 0
  },
  "pl_dens": 6.9,                  // core, g/cm³ (null-safe)
  "pl_imppar": 0.32,               // core
  "pl_orbinclerr1": 0.8,           // core — W3 discriminator; null when blank
  "pl_orbinclerr2": -0.8           // core
}
```
- Flags/limits are **raw ints**, not bools — the consumer spec is written in `=0/=1/=−1` terms (§5.11: a
  consumer coding `if ==1` must be able to see the `−1`). Kept null-safe via a new `_intval()` helper.

### 3b. `planets[]` — Tier-2 + composite + OEC (**full** only)
```jsonc
{
  "transit_geometry": { "pl_ratdor": ..., "pl_ratror": ..., "pl_trandep": ..., "pl_trandur": ...,
                        "pl_tranmid": ..., "*_lim": ... },
  "environment":      { "pl_insol": ..., "pl_eqt": ... },
  "obliquity":        { "pl_projobliq": ..., "pl_trueobliq": ... },
  "ephemeris":        { "pl_orbtper": ... },
  "discovery":        { "disc_year": ..., "disc_facility": ..., "disc_telescope": ...,
                        "disc_instrument": ..., "disc_pubdate": ..., "disc_refname": ... },
  "record":           { "pl_pubdate": ..., "rowupdate": ..., "releasedate": ...,
                        "pl_ntranspec": ..., "pl_nespec": ..., "pl_ndispec": ..., "pl_nnotes": ... },
  "composite": {                   // pscomppars — every value here is source:composite
    "source": "composite",
    "pl_angsep": ..., "pl_angseplim": ..., "pl_tsm": ..., "pl_esm": ...,
    "pl_nobs_jwst_tran": ..., "pl_nobs_jwst_e": ..., "pl_nobs_jwst_pc": ..., "pl_nobs_jwst_di": ...
  },
  "oec": {                         // SECONDARY / verify-at-primary; null when no OEC match
    "source": "oec", "authority": "SECONDARY",
    "lists": ["Confirmed planets", "Planets in binary systems, S-type"],
    "discoveryyear": ..., "lastupdate": ..., "description": ...
  }
}
```

### 3c. `hosts[]` — Tier-2 per-host (**full** only)
```jsonc
{
  // ...existing CR-8 host keys...
  "stellar_extra": { "st_rotp": ..., "st_vsin": ..., "st_age": ..., "st_dens": ..., "*_lim": ... },
  "coverage_counts": { "st_nrvc": ..., "st_nphot": ..., "st_nspec": ... },
  "system": { "sy_snum": ..., "sy_mnum": ... },
  "kinematics": {                  // Gaia-sourced; st_radv coverage patchy (blank e.g. GJ 685)
    "sy_pmra": ..., "sy_pmraerr1": ..., "sy_pmraerr2": ...,
    "sy_pmdec": ..., "sy_pmdecerr1": ..., "sy_pmdecerr2": ...,
    "sy_pm": ..., "sy_plx": ..., "sy_plxerr1": ..., "sy_plxerr2": ...,
    "st_radv": ..., "st_radverr1": ..., "st_radverr2": ...
  },
  "oec_structure": { ... }          // full only — system tree / binary nesting, SECONDARY
}
```

### 3d. Coverage manifest — behaviors #2/#3
- `coverage.resolution` gains a **triage** field per host: `matched_on` (`hip|hd|tic|gaia|hostname|alias`),
  so behavior #2's alias/hostname fallback is auditable.
- `coverage.component_planets` (behavior #3): `[{primary, component, component_planets:[names], source, note}]`
  — the wide-companion planets recovered by component enumeration, each flagged SECONDARY-attribution + the
  co-motion caveat ("Gaia binding check is the consumer's job").
- `coverage.archive_absence` (contract §4 row #8 — best-effort, **not** a hard gate): **candidate-grade rows are
  carried** — a `soltype='Candidate'` planet still has a `default_flag=1` row, so it surfaces via Mode A even
  under `--solution-scope default` (e.g. Proxima Cen c). The three archive-absence *flavors* —
  FP-with-overview / removed-targets / never-ingested-candidate — are **out of the bulk pull's reach** (same
  rationale as D1: the overview + removed-targets lists aren't bulk TAP columns), surfaced only as
  coverage-manifest flags where detectable.

---

## 4. Pull-behaviors (D4 — best-effort + 2 hard anchors)

### 4a. Behavior #2 — host name-resolution (fixes GJ 667 C false-drop)
**Root cause (reproduced this session):** GJ 667 C's ps rows carry `hd_name=NULL, hip_name=NULL`; my Mode-A
join keys on HD>HIP>TIC>Gaia only, so the resolved SIMBAD key (`HD 156384`) matches nothing → `zero_planet`.
**Fix:** in `_run_mode_a`, build the archive-key candidate set from **all** resolved designations **plus the
bare requested string and the SIMBAD main_id/aliases**, and add a **`hostname IN (...)`** arm to the ps query
(the NASA-PS table keys GJ 667 C's planets under `hostname='GJ 667 C'`). Record which arm matched
(`coverage.resolution.matched_on`). **Implementation note:** `_ps_archive_key` (today returns a single
`(col, val)`) and `_run_mode_a`'s resolve/group loop must move to a **multi-arm candidate set**, with
**cross-arm dedup** — a host matching both `hd_name` and `hostname` must not double-count its planets.
**Hard anchor:** `GJ 667 C → b/c/e/f/g present`.

### 4b. Behavior #3 — component enumeration (fixes 26 Dra → GJ 685 b)
**Root cause:** 26 Dra A (`HD 160269`) is genuinely planet-less; the system's only planet (GJ 685 b) orbits the
wide M-dwarf companion GJ 685, never queried. **Fix (best-effort):** for a resolved Mode-A host, enumerate
sibling/child components via **(a) the OEC system tree** (`compute_oec`, `allow_simbad=False`) and **(b) the
`binary.py` companion readers** (CR-2 `multiplicity` / CR-3 companion enumeration) — **not** SIMBAD, whose
`compute_simbad_lookup` resolves one object's IDs, not a component tree (there is no SIMBAD hierarchy seam);
query ps for each candidate component; attach any planets found under `coverage.component_planets` + the host
record. **Do not** attempt the Gaia co-motion binding check in the pull (consumer's job, §7#3).
**Hard anchor:** `26 Dra → GJ 685 b under component_planets` — **spike-gated (below); not guaranteed-green until
the spike confirms the path reaches GJ 685.**
> ⚠ **Build-time spike required (step 6):** confirm the OEC-tree + `binary.py`-companion path actually surfaces
> `GJ 685` from a `26 Dra`/`HD 160269` query. If neither authority cleanly enumerates the wide companion, ping WB
> (MSG) on the enumeration authority before hard-gating the anchor — this is the highest-uncertainty piece.

---

## 5. Helpers & value handling

- **New `_intval(v)`** → `int(v)` or `None` (null-safe). Used for all `*_flag` (0/1) and all `*lim` (−1/0/1).
  **Do not** route these through the existing bool `_flag()` (it would collapse the −1 and the 0-vs-1).
- **Reuse `_num()`** for `pl_dens`, `pl_imppar`, errors, all Tier-2 floats.
- **Reuse `_parse_reflink()`** for `disc_refname` and the per-value `*_reflink`.
- **`_composite_pull(planet_names, select)`** — new: one pscomppars query keyed by `pl_name IN(...)`
  (chunked like `_query_ps_in`), returns `{pl_name: {composite cols}}` for the merge. Full-only.
- **`_oec_enrich(host_record)`** — new: `compute_oec(name, allow_simbad=False)` (identity already resolved → no
  per-host SIMBAD round-trip; local 7-day cache, cold-cache 1st-use GitHub fetch) → list membership + structure.
  Full-only, best-effort, wrapped so an OEC miss/exception is a silent `null` (never fatal — SECONDARY grade).

---

## 6. `query.py` surface

- **No new required flags.** `--fields {core,full}` already selects the tiers (D2).
- **D1a:** add `--overview-disposition NAME [NAME…]` — an **opt-in, non-default** flag that, for a short
  explicit planet list, does the per-planet overview-disposition fetch **outside** the bulk path. Built after
  CR-9-proper + regression green (WB's must-not-delay sequencing); **not skipped**. Fetch source TBD at build
  time — not a TAP column (see D1a in §0).
- Help text for `--fields` updated (`core = CR-8 + CR-9 Tier-1 disposition/quality; full = + Tier-2 + composite
  + OEC + raw`).

---

## 7. Validation (§5 — the pull is correct iff all pass)

All run **live** (I can execute every anchor via `_query_tap`; WB re-gates independently on delivery):

| # | Anchor | Field |
|---|---|---|
| 1 | `GJ 667 C e/f/g → pl_controv_flag=1`; `b/c → 0` | pre-verified ✓ (this session) |
| 2 | `LP 890-9 b/c → pl_bmasselim=1` | mass upper-limit |
| 3 | `TRAPPIST-1 b–h → ttv_flag=1` (all 7) | TTV |
| 4 | `LTT 1445 A c → pl_orbeccenlim=1` | ecc upper-limit |
| 5 | `Kepler-16 b → cb_flag=1`; single-star → 0 | circumbinary |
| 6 | `GJ 367 b pl_dens≈6.9`, `GJ 1214 b≈2.26` | density |
| 7 | `GJ 436 b → tran_flag=1 AND rv_flag=1` | multi-method |
| 8 | `GJ 1214 b` composite fields present + `source:composite` — **run under `--fields full`** | composite labelling |
| 9 | `GJ 667 C c` OEC list ⊇ `"Planets in binary systems, S-type"`; controversial → `Controversial` list — **`--fields full`** | OEC |
| 10 | null preservation + **batch≡single on HD 136352** | inherit CR-8 |
| 11 | `HD 219134 d & f → pl_bmasselim=−1` (not 1, not 0); `HD 128311 b → pl_orbincllim=−1` | −1 tri-state |
| 12 | `HD 192310 b/c → inclination_deg=90.0` exactly + `mass_prov_raw="Msin(i)/sin(i)"` | assumed-edge-on |
| **+A** | **behavior #2:** `GJ 667 C → b/c/e/f/g present** (not zero_planet) | D4 anchor |
| **+B** | **behavior #3:** `26 Dra → GJ 685 b under component_planets` | D4 anchor |

---

## 8. Tests & docs

- **`tests/test_exoplanet_batch.py`** (offline): extend with fixture-driven ps/pscomppars rows exercising the
  new builders — the `_intval` tri-state (incl. −1), the composite merge + `source:composite` tag, the OEC
  block, the `disposition`/`limits`/`kinematics` shapes, core-vs-full gating, and the behavior-#2 alias/hostname
  join + behavior-#3 `component_planets` assembly (mocked resolvers). No network.
- **`tests/test_query_exoplanet_batch_live.py`** (`SPACE_APP_RUN_LIVE=1`): add the 14 §5 anchors above.
- **`docs/integration.md`** CR-8 block → append a **CR-9 sub-section**: the new record keys, the ps/pscomppars
  split, the core/full tiering, the two behaviors + coverage manifest, the 14 anchors.
- **`CLAUDE.md`** (`core/` blurb + test-count line), **`docs/star-databases.md`** (the pscomppars-vs-ps note),
  and the roadmap table.

---

## 9. Riders (trail CR-9-proper — D3; a separate sub-deliverable)

**STATUS: BUILT + tested 2026-08-20** (all riders green; CR-9-proper stays banked-GREEN, MSG 078). Both
9a (Companion CR#1 jitter structure) and 9b (CQ-7-3c-1…4) are in the working tree; unpinned magnitudes are
advisory placeholders as specified. WB re-gates each rider as it lands (MSG 080); Greg batches ONE FULFILLED
flip for the whole bundle (CR-9-proper + riders); commit held until that flip. Rider build detail:
- **CQ-7-3c-1** — `nuclear._radiogenic_heat` rewired to the [Eu/H]-driven GCE actinide inventory vs the solar
  anchor (K-40 stays a 10^[Fe/H] proxy); **withheld** (`null`) when no [Eu/H] tracer — no 10^[Fe/H] fallback.
  Both WB MSG 079 defaults wired (solar-anchor reference; star's own isotopic split via per-isotope R_i) + the
  three caveats (K-40 proxy-labelled; decay counted once — no double-count; heat inherits DV-2/3/4/6 flags).
- **CQ-7-3c-2** — `gce_domain_ok` gains DV-1 `age_soft` (advisory band, via `--age-soft`) + DV-3 s-process
  (`--ba-eu` preferred; else the §8 thin-disk [Eu/Fe]≳+0.4 proxy).
- **CQ-7-3c-3** — DONE prior (band `>=`/`<=` boundary fixes in `nuclear_tables.py`).
- **CQ-7-3c-4** — tri-state `domain_ok` (True/False/**None**-unevaluable) + `per_output` severities +
  multi-reason `domain_reasons` (no `elif` shadowing).
- **Companion CR#1** — `detection_tables._DETECTION_DEFAULTS["rv"]["jitter_bumps"]` (evolved + active/young
  advisory placeholders) consumed by `detection._rv_jitter_floor(... host_class, activity)`; the RV method dict
  carries `jitter_advisory`/`jitter_note` when a bump fires. `--activity {active,young,quiet}` on the query.
- Tests: `test_nuclear.py` (+14 CQ-7-3c) / `test_query_nuclear.py` (+2) / `test_detection.py` (+6 CR#1) /
  `test_query_detection.py`.

Built **after** CR-9-proper is green, so they can't delay the build-gate. Split them out to Phase 5 if either
threatens the core.

### 9a. Companion CR #1 — jitter-floor bumps (`core/detection_tables.py` + `core/detection.py`)
- **Structure:** the RV jitter map (`_DETECTION_DEFAULTS["rv"]["jitter_floor_by_sptype_m_s"]`, currently the
  Kraft hot-host bump O/B/A=5, F=3, G/K/M=1.5) gains **two symmetric floors**: an **evolved-star** bump
  (`is_evolved`/logg-keyed → an elevated `jitter_floor_evolved_m_s`, p-mode + granulation) and an
  **active/young-cool-dwarf** bump. Consumed in `detection.py::_rv_jitter_floor`.
- **Magnitude = un-cleared LEAD (D3):** ship the bump values as an **explicit, documented, overridable
  placeholder flagged advisory** (rough literature ranges only: subgiant ~few–10 m/s, red giant tens–hundreds).
  **Do not bake a real number.** The skill treats an un-pinned bump as advisory (flag, not hard
  `likely-absent`), like the §5.4 activity guard. WB pins the jitter–L/M scaling in Phase 5.
- Tests: `tests/test_detection.py` / `test_query_detection.py` — assert the structure + the advisory flag, not
  a specific magnitude.

### 9b. 3c defects — the four code fixes (`core/nuclear.py` + `core/nuclear_tables.py`)
Read `171-card-audit/candidate-queue.md` **889–895** + `cp7-report.md` **§4 (DEFECT-1…4)/§7** at build time.
- **CQ-7-3c-1 (load-bearing):** `nuclear.py` `_radiogenic_heat` (**L82–92**, sig `(age_gyr, fe_h)` — no Eu
  tracer, scales by `10**fe_h`) is Eu-blind / co-formation-based → wire the heat to the actual
  r-process/actinide inventory (consume the already-delivered 3c FINAL / CR-4 fissile actinide scaling — a
  **wiring** fix, not new physics). Breaches Interface A `compute_recipe` (a **WB-side interface name**, not an
  app symbol — grep finds nothing in `core/`), inverts DV-6. **→ ping WB if the Interface-A boundary isn't
  self-evident.**
- **CQ-7-3c-2 (code portion):** `nuclear_tables.py::gce_domain_ok` (**L90–116** — `false_when` is the CR/WB
  spec's term for its veto conditions, not a code symbol) implements only 3 of 4 rules → add the DV-1 age-soft
  path + a DV-3 s-process proxy/disclosure.
- **CQ-7-3c-3:** DV-4/DV-7 band boundaries are strict-inequality-holed (`age>8.0` …) → `>=`/`<=` fixes.
- **CQ-7-3c-4:** `domain_ok=true` when guards are unevaluable + multi-violations shadowed to one reason →
  tri-state / per-output flag.
- (CQ-7-3c-5…7 are WB's `fissile-fraction-gce-model.md §8` doc amendments — **not my code.**)
- Tests: extend `tests/test_nuclear.py` / `test_query_nuclear.py`.

---

## 10. Build sequence

1. **Helpers + Tier-1 core** — `_intval`; extend `_planet_record` with `disposition`/`limits`/`pl_dens`/
   `pl_imppar`/`pl_orbinclerr1/2`; extend `_PLANET_CORE_COLS`. Run offline tests.
2. **Behavior #2** (alias + `hostname` join) in `_run_mode_a` + `matched_on` triage. Live-verify GJ 667 C.
3. **Tier-2 named keys (full)** — per-planet + per-host blocks; extend `_host_record`; SELECT stays `*` for full.
4. **Composite pull (full)** — `_composite_pull` (pscomppars, chunked), merge under `composite` + `source` tag.
5. **OEC enrichment (full)** — `_oec_enrich`, best-effort, SECONDARY; planet `lists` + system structure.
6. **Behavior #3** — component enumeration (**spike first** — confirm 26 Dra→GJ 685 reachable), `component_planets`.
7. **Validation** — run all 14 §5 anchors live; fix to green.
8. **Tests + docs** — offline fixtures, live anchors, integration.md CR-9 sub-section, CLAUDE.md, roadmap.
9. **▶ GATE A — code-review (before hand-off).** `/code-review` on the CR-9-proper diff, focused on
   **null/provenance faithfulness**, the **−1 tri-state** (no bool collapse), **composite `source:composite`
   labelling**, and the **two best-effort behaviors #2/#3**. A consumer-facing data layer — a collapsed
   tri-state / mislabeled composite value / fabricated null silently corrupts WB's Q9 skill, so this gate is
   not optional. The heavier `ultrareview` (multi-agent cloud) here is **Greg's trigger, not mine.** Address
   findings → re-green. (Orthogonal gates already in place: the step-7 live-anchor run, and WB's independent
   §5 re-gate on delivery.)
10. **Riders (D3, trailing):** 9b (3c code fixes CQ-7-3c-1…4) then 9a (jitter structure + advisory placeholder).
    **▶ GATE B — code-review the riders**, focused on the `nuclear.py` radiogenic-heat rewiring
    (**CQ-7-3c-1 — load-bearing, inverts DV-6**) + the `detection_tables.py` jitter-table change. Address → re-green.
11. **D1a — DROPPED (WB MSG 075).** Its premise was falsified live: the overview disposition **equals**
    `pl_controv_flag` (already delivered in Tier-1) for both row-#4 cases (GJ 667 C c plain-Confirmed; τ Cet
    f/g/h Controversial), across ps/pscomppars/OEC/overview — and it is **not a TAP column**, so it would be a
    fragile scraper re-deriving a delivered value with zero new signal. Row #4's real third surface is
    **literature** (47 UMa d), the skill's LEAD, unreachable by any pull. A decision on a falsified premise,
    **not** a defer (APP verified → WB adjudicated, MSG 074/075).
12. **Hand-off** — post the build summary + the anchors' results to the channel; WB re-gates → Greg's FULFILLED
    flip. (If a rider would delay, hand off CR-9-proper first per D3; the rider follows in a later delivery.)

**Open pings (raise in-channel when reached):** the CQ-7-3c-1 Interface-A `compute_recipe` boundary (the exact
U/Th-heat-vs-actinide-inventory scaling is ambiguous — ping WB when building the rider); the behavior-#3
component-enumeration authority — RESOLVED by the spike + WB MSG 073 (option A; 26 Dra is a documented
limitation, α Cen the hard anchor).

## Gate A — code-review findings (2026-08-19, `@code-review high`)

7 findings on `core/exoplanet_batch.py`; triaged:
- **FIXED (CR-9):** #1 behavior-#3 **double-count** — a planet already returned as its own top-level host in
  the batch was re-surfaced under `component_planets` (querying both α Cen A + Proxima). Now excluded via a
  batch-wide `already` set; regression test `test_no_double_count_when_component_also_queried` + live-verified.
- **FIXED (adjacent):** #5 dead `result["solution_scope"]/["field_scope"]` assignments removed; #7
  `compute_simbad_lookup` in `_run_mode_a` wrapped so a *raised* SIMBAD failure marks one host unresolved
  instead of killing the batch.
- **KEPT + documented:** #4 behavior #3 runs in core too (completeness). Evaluated: the per-host OEC resolution
  is offline (negligible); the SIMBAD+ps component queries fire **only** for the rare OEC-grouped-multi-component
  case; the one always-on cost is a single OEC cache load, which no-ops gracefully if unavailable. Kept — the
  audit reads core and needs the completeness.
- **PRE-EXISTING CR-8, NOT changed (out of CR-9 scope; CR-8's contract is WB-re-gated):** #2 `total_planets`
  counts solution-rows not distinct planets under `--solution-scope all` (≠ `num_planets`); #3 Mode-B
  `filters={}` → full ps scan (the `query.py` wrapper guards it via `or None`); #6 `returned_host_count` ==
  `total_hosts`. Recorded as candidate CR-8 cleanups, deliberately not silently altered here.

## Gate B — code-review findings (2026-08-20, `@code-review high` on the rider diff)

6 findings on `core/nuclear.py` / `core/nuclear_tables.py` / `core/detection.py`; triaged:
- **FIXED #1** (`nuclear_tables.py` DV-3 [Ba/Eu]) — the `ba_eu >= 0.0` threshold flagged a **solar** star
  ([Ba/Eu]=0, the anchor) as s-process. Raised to **+0.5** (the CEMP-s cut, Beers & Christlieb 2005); solar
  (0) and pure-r (≈ −0.7) are now clean. Regression test `test_dv3_ba_eu_solar_reference_not_flagged`.
- **FIXED #3** (`detection.py` `_rv_jitter_floor`) — `advisory=True` was set unconditionally for an
  evolved/active host even when `max()` did not raise the floor (missing key / base ≥ bump), so the note
  claimed a bump that wasn't applied. Now flags advisory **only when the placeholder actually raises the
  floor**. Test `test_bump_that_does_not_raise_the_floor_is_not_advisory`.
- **FIXED #4** (`nuclear.py` withheld note) — dropped the hardcoded "~19% of BSE heat" (only true at solar
  [Fe/H]/age) → "the non-actinide channel, ~19% of the BSE budget **at solar**; U/Th withheld".
- **FIXED #5** (`nuclear.py` `_radiogenic_heat`) — `gce_enrichment_factor` was called without `population`/`feh`
  while `_fissile_block` passes them (agree only because the fn ignores them today). Now threads them
  (numerator = star's pop/feh, denominator = solar anchor thin/0) so the fissile ↔ radiogenic g_i can never
  silently diverge if the GCE model becomes pop/[Fe/H]-dependent. **Byte-identical today.**
- **FIXED #6** (`nuclear.py` provenance comment) — the `bands` comment now notes it also carries the DV-1
  `age_soft` advisory string.
- **KEPT (intended, not a bug) #2** — `provenance.domain_ok` returning **`None`** for an in-domain star with
  **no** Eu tracer is exactly the CQ-7-3c-4 fix (DEFECT-4's "no-Eu → `true`" was the defect); the tri-state is
  documented in `docs/integration.md` + the docstring, and the no-Eu case also carries `fissile.note` /
  withheld heat, so the signals are consistent. Boolean consumers must read the tri-state (a deliberate,
  spec-mandated contract change).
