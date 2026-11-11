# CDS outage fallback — build notes (Part A: A0 / A0b / A1, the call-shape list, the 2MASS anchors)

Working notes for `CDS_OUTAGE_FALLBACK_PLAN.md` v7, for the CP1 review and the post-build WB message. **TEMPORARY**:
this file goes with mirror mode (`CDS_RESTORE_PLAN.md`).

## A0 — every SIMBAD access, and how mirror mode reaches it

| Site | Kind | Mirror routing (`core/cds_mirror.apply_simbad()`) |
|---|---|---|
| `shared._make_simbad` (`shared.py:1432`) → `compute_simbad_lookup` (`databases.py:308/314`), `calculators.py:240` | astroquery `SimbadClass` (new instance) | `apply_simbad()` at the top of `_make_simbad` sets `conf.server` (copied at `__init__`) |
| `Simbad.query_objectids` (`databases.py:310`, `calculators.py:242`) | the import-time module instance | always after `_make_simbad` in the same function, so `apply_simbad()` has already set the module instance's `.server` |
| `databases.py` option-50 importer (`Simbad()`, `:1931` at HEAD) | new instance | `apply_simbad()` added before `Simbad()` |
| `_simbad_otypes_tap` (otype join) | raw TAP, `conf.server` | `apply_simbad()` inside the seam; **in mirror mode it is replaced by `_simbad_otypes_split`** (three flat queries via `_simbad_tap_rows`, which also applies) |
| `_simbad_cr26_tap` (astrometry / parent / velocity / cone; CR-24 `ism_velocity` goes through it) | raw TAP, `conf.server` | `apply_simbad()` inside the seam; run as written (A1: 0.29–1.37 s on CfA) |
| `xray_catalog._identity_lookup`, `twomass`, `ism_velocity` identity | through `compute_simbad_lookup` | covered by `_make_simbad` |
| `gui/`, `query.py` | none direct | everything goes through `core/` |
| `main.py` (deprecated) | direct module `Simbad` | **not wired** (stays on CDS; the CLI is deprecated) |

## Every VizieR call, by search shape (WB MSG 380 amendment 2)

| Call site | Catalog | Shape |
|---|---|---|
| `binary.py:745` | `B/sb9/main` | cone |
| `binary.py:762` | `B/sb9/orbits` (`Seq:=`) | small-catalog filter |
| `binary.py:797` | `B/wds/wds` | cone |
| `binary.py:817` | `B/orb6/orbits` | cone (absent on IDIA **and** CDS — no change) |
| `binary.py:1505` | `B/sb9/main` (census, whole) | small-catalog read |
| `binary.py:1527` | `B/sb9/orbits` (census, `Per<…`) | small-catalog filter |
| `debris_disk.py:104` | `J/ApJS/211/25/catalog`, `J/ApJS/225/15/table3` | cone |
| `debris_disk.py:113` | `II/328/allwise` | cone |
| `twomass.py:70` (HEAD path) | `II/246/out` by `2MASS=` designation | **large-catalog non-position** → in mirror mode replaced by `twomass.py:85`, a 3″ cone at the decoded position |
| `xray_catalog.py:148` | `IV/39/tic82` | cone (direct `Vizier`) |
| `query.py:2030` `vizier-query` | any (user-given) | free-form: may be large non-position; a mirror cut-off there is a loud error |
| `gui/` | — | none |

**So in mirror mode the only large-catalog non-position query left is the free-form `vizier-query`.**

## A0b — catalog coverage on IDIA

All core catalogs present (MSG 377): II/246, IV/39/tic82, II/328/allwise, J/ApJS/211/25, J/ApJS/225/15, B/sb9 (main,
orbits), B/wds, B/cb, I/311, I/355. `B/orb6/orbits` absent on IDIA and on CDS. The CR-29 case files pass no
`vizier-query` user catalog (no `vizier-query` case in `cr29_regate_cases.json` / `cr29_regate_population.json`).

## A1 — exact-text timings (2026-11-11, 2 passes, 10 anchors; seconds)

| Query (exact text the code sends) | Host | n | max | median |
|---|---|---|---|---|
| otype split step 1 (`ident`, HEAD's WHERE) | CfA | 20 | 0.49 | 0.31 |
| otype split step 2 (`otypes … IN`) | CfA | 20 | 0.46 | 0.31 |
| otype split step 3 (`basic … IN`) | CfA | 20 | 0.42 | 0.29 |
| CR-26 astrometry (`ident ⋈ basic ⟕ flux`) | CfA | 20 | 1.37 | 0.32 |
| CR-26 astrometry by `Gaia DR3 <id>` | CfA | 2 | 0.32 | 0.32 |
| CR-26 parent (`ident ⋈ h_link ⋈ basic`) | CfA | 20 | 0.38 | 0.29 |
| CR-24 velocity (`basic WHERE main_id`) | CfA | 2 | 0.29 | 0.29 |
| CR-26 cone (`basic CONTAINS`) | CfA | 2 | 0.32 | 0.32 |
| `query_object` (+`mesfe_h`) | CfA | 8 | 0.20 | 0.10 |
| `query_objectids` | CfA | 8 | 0.37 | 0.06 |
| 2MASS 3″ cone | IDIA | 8 | 4.70 | 2.99 |
| TIC 5″ cone | IDIA | 8 | 3.99 | 2.64 |
| WDS cone | IDIA | 8 | 3.56 | 2.01 |
| SB9 cone | IDIA | 8 | 3.54 | 2.74 |
| AllWISE cone | IDIA | 8 | 4.29 | 1.59 |
| Chen 2014 cone | IDIA | 8 | 5.83 | 1.97 |
| Cotten & Song 2016 cone | IDIA | 8 | 3.98 | 1.79 |
| SB9 `Seq=` filter | IDIA | 2 | 1.39 | 1.39 |
| census `B/sb9/main` whole | IDIA | 2 | 1.87 | 1.87 |
| census `B/sb9/orbits` `Per<30` | IDIA | 2 | 1.77 | 1.77 |
| ORB6 cone (absent) | IDIA | 2 | 1.54 | 1.54 |

**Limits (the plan's A1 rule: ≥ 1.5 × slowest, rounded up to 30 s):**
- SIMBAD / xray rows: slowest 1.37 s → 30 s = **the built-in values; no limit hooks are added** (`timeout_default()`
  dropped from the design — a smaller Part A and a smaller revert).
- VizieR: fixed at **60 s** per request (2 attempts, each wall-bounded at 70 s); slowest real answer **5.83 s**.
- **Cut-off threshold (amendment 3): 60 s per attempt**, against a slowest real answer of 5.83 s and IDIA's 68.8 s
  cut-off.

## 2MASS-cone anchors (WB MSG 380)

The 2MASS route is reached from regions, the dossier, `stellar_mass`, `par_flux` and `generate` for any K / M `--star`
run. **306 of `cr29-s151/base1`'s runs** carry 2MASS output (`twomass_status` / the M_Ks route) — the full id list is
saved for the post-build message. By star (runs): G 44-42 (8), Proxima Centauri (6), EZ Aqr (5), 61 Cyg B (4),
Ross 154 (4), Wolf 359 (4), GJ 699 (4), Lacaille 9352 (3), VB 10 (3), Ross 47 (3), 61 Cyg A (3), ε Eri (3),
HD 209100 / ε Ind (3), Lalande 21185 (3), EV Lac (3), and ~45 more with 1–2 runs each (GJ 725 A/B, σ Dra, Ross 128,
Ross 248, GJ 1061, SCR J1845-6357, GJ 866 A/B/C, BD+59 1915, …).

## CP1 — `/code-review high` on the Part A working tree (2026-11-11)

10 findings. **Fixed (7):**
1. The VizieR mirror breaker is keyed **per catalog**, so a timed-out large-catalog query never blocks other catalogs'
   cones.
2. X-Match is **skipped at once** in mirror mode. `xmatch_query` returns "Could not connect to CDS X-Match: it has
   no mirror", so the census no longer waits minutes on the dead host.
3. A malformed cone is parsed **before** the bounded call, so it fails at once and is never retried.
4. The 2MASS cone result keeps HEAD's `row_limit=5` / `truncated` semantics.
5. Option 50 (the `star_systems` importer) is **refused in mirror mode**, so mirror rows are never persisted in the DB.
6. `_simbad_tap_rows` reuses `_simbad_cr26_tap`. One TAP body, and a masked cell becomes `None`, which gives a
   result error, not "unreachable".
7. One `_otypes_where` helper is shared by the join and the split. `_otypes_query`'s ADQL is unchanged and pinned
   by a literal test.

**Rejected (3), with reasons:**
- #8 "the explicit VizieR timeout is overridden": no caller passes one, and `vizier-query` has no timeout flag (the
  plan fixes 60 s).
- #9 "env-from-scratch subprocess tests see the real flag": VA1 ran the whole suite **with a flag file present** and
  they pass. They never reach a SIMBAD or VizieR call.
- #10 "TIC lacks the ≥ 60 s backup": TIC's 30 s watchdog fires first, so the backup is unreachable (ruled in
  round 3).

## Validation (Part A)

- **VA1:** full suite with a mirror flag file present (under a scratch `HOME`): **4228 passed / 126 skipped / 703
  subtests / 0 failures**. After the CP1 fixes: **4235 passed / 126 skipped / 0 failures** (+7 tests).
  - The `QThread: Destroyed while thread '' is still running` core dump at interpreter exit is **pre-existing**:
    HEAD in a clean worktree gives 4180 passed and the same dump.
- **VA2 (off = HEAD):** the first 20 runs of `base1/_runs.json`, the build (off) against a HEAD worktree, both under
  `unshare -rn`: **20/20 byte-identical**.
- **VA3 (on, against `base1`, scored with WB's `score_cr30` helpers loaded read-only):** 289 runs. These were the
  40 anchors, the EV Lac runs, the 3 debris-disk cases, and **one run per 2MASS-route star**, not all 306 2MASS
  runs, to keep load on the volunteer mirrors down.
  - **256 byte-identical, 0 degraded / rerun.**
  - **33 value differences, all `star-regions` bench cases (B12 / B13 / M15), every one traced to `teff` / `fe_h`.**
    SIMBAD's `mesfe_h` rows carry no `ORDER BY`, and CR-27.2 fills from row 0. CfA returns the same rows in a
    different order.
    - Both `base1` values (e.g. GJ 15A 3609, GJ 205 3737) are present in CfA's rows.
    - `base1` = `base2` (CDS, the same day).
    - Diameter, luminosity and `sizeOfSun` follow from `teff`.
  - **This is the known row-order drift** (CR-30 post-flip close, fire record §20.6, routed to the CR-28 + CR-33
    bundle), exposed by the server change. It is not mirror data and not Part A code.
- **VA4 (budget):** the slowest observed run was **48.7 s** (≤ 720 s) at 4-way parallel.
  - Analytically, the worst VizieR call is 2 × 70 s + 2 s backoff ≈ 142 s, and the per-catalog breaker then
    short-circuits that catalog.
  - `binary-orbit`'s 4 calls are on 4 catalogs, so the worst case is ≈ 568 s plus SIMBAD (≤ 2 × 30 s per family,
    then a breaker) ≈ 628 s, which is ≤ 720 s.
- **VA5 (otype split = join, both on IDIA):** **13/13 identical** rows and interpretation. The set covered:
  - head and candidate on different objects (G 272-61)
  - both ids on one object (`* alf CMa`)
  - an id that matches nothing
  - the active-wind stars EZ Aqr, 61 Cyg and EV Lac

  No real multi-oid id was found, so that case rests on its unit test. The join took 64–88 s on IDIA; each split
  query takes about 0.3 s on CfA.
- **VA6 (seams on CfA):** **5/5**. Vega's astrometry (plx 130.23, A0V), velocity (−13.5 km/s) and 60″ cone, and
  α Cen A's multiple-star parent. The `Gaia DR3 <id>` query shape completed, but the test id returned "no object",
  so that proves only the shape. **No seam needed a split.**
- **VA7 (a cut-off is loud):** `vizier-query --catalog II/246/out --filters 2MASS=…` in mirror mode → exit 1,
  `"CDS VizieR request timed out. Try again."` after 125 s, never `count: 0`.
