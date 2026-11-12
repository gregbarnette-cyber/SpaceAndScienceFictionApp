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

## Part B — B0 / B1 / validation / CP2 (2026-11-11)

- **B0** (ESA release 3.15 against astroquery 0.4.11, live on Greg's account):
  - `TapPlus.login`: 0.71 s.
  - A wrong password raises `HTTPError` (401). astroquery prints the 401 page to **stdout**, which the app discards
    thread-scoped.
  - `launch_job_async(name=…)`, `remove_jobs` and the job listing all work.
  - The job name is only in the job's detail page (`<uws:parameter id="jobname">`).
- **B1 concurrency** (10 Gaia anchors × 4 processes, mirror on): **0 × HTTP 429 anonymous, 0 logged in**. The
  slowest run took 57–64 s.
  - Whether ESA's "active" count includes sync jobs was not determinable: no 429s were observed either way, and the
    docs are silent.
- **VB1:** the full suite with the real credentials file present: 4265 passed plus 1 CR-32 guardrail failure
  (`core/gaia_auth.py` imported `astroquery.gaia`). The client build moved into `catalog._new_gaia_client`, so the
  count is **4266**.
- **VB2:** the 10 Gaia anchors, mirror on and logged in: **10/10 byte-identical** to `base1`, to the anonymous run
  and to VA3.
- **VB3:** `close-binary-census --include nss` logged in: identical to anonymous (0 NSS rows at 15 ly / 30 d, so the
  row-cap difference isn't exercised), and **0 jobs** left on the account. Rechecked after CP2.
- **VB4:** a wrong password gives output identical to anonymous, valid JSON and the "login not used" line, with no
  password anywhere. The 401 back-off marker was written, then removed so the real login isn't paused.
- **VB5:** `gaia-jobs` lists a left `space_app-*` job and list-only deletes nothing. `--cleanup` removes it; after
  CP2 it keeps a job finished < 10 min ago, as designed. The test job was then removed by id.
- **CP2 `/code-review high`:** 10 findings. **Fixed (9):**
  - background launch, so the id is recorded before the wait
  - the auth cache key is written only after a real login
  - the login has its own 15 s bound
  - a failed logged-in async path falls back to anonymous
  - `Retry-After` and jitter on the async retries
  - `gaia-jobs` checks the HTTP status and parses the XML with ElementTree
  - a 10-min minimum age for finished jobs
  - no mode check on native Windows
  - **one login per process** with the session cookie reused (30 min)

  **Rejected (1):** `search_async_jobs`, because astroquery's `Job` objects don't expose the job name.
  - Also fixed: the anonymous async path now prints its login-state line.

## CP3 — `/code-review high 8452e8e..HEAD` (the whole delta, 2026-11-11)

10 findings. **Fixed (8):**
1. The logged-in cache write is gated **per call**: an anonymous fallback after a good login is never cached under
   `auth`.
2. **The session is established before and outside every query bound** (`gaia_auth.ensure_session`, one real login
   per process). Attempts only attach the cookie, so a slow login can no longer trip the CR-19 breaker.
3. The "paused" line is now written on the async path too.
4. The anonymous fallback happens **only on an account refusal** (401 / 403 / 429 / full queue or quota), with a
   line. Other failures are raised as HEAD would raise them, and the retries use `_with_retries`.
5. 401 / 403 come from the HTTP status or astroquery's `Error 401` form, never from stray digits.
6. A finished job with no creation time is cleaned, and the kept reasons are per phase.
7. `--cleanup` is one batched delete, falling back to per-id deletes to report a failure.
8. A dead fixture parameter was removed, and one `_new_gaia_client` builder is used throughout.

**Rejected (2):**
- #5 route TIC through the VizieR mirror producer: TIC keeps its own 30 s bounds by design, and its watchdog makes
  the 60 s rule unreachable (ruled in round 3 and at CP1).
- #9 a shared breaker helper: it would refactor four existing breakers, which is out of scope for a temporary fix.

**S6 (removal rehearsal, under VA2's `unshare -rn` conditions):** flag present → 1 mode line; flag removed → 0
lines, and stdout is byte-identical to VA2's flag-off output.


## Draft post-build message to WB — HELD (post only at Greg's go)

```
## MSG <next> · FROM: APP · TO: WB · 📦 CDS outage — Parts A + B built, reviewed (CP1–CP3), validated; every MSG 376 / 378 / 380 / 382 item

**Commits** (local `main`, push: Greg):
| Commit | What |
|---|---|
| `f0b1652` | Part A, mirror mode |
| `0567ae0` | the plan (v7) |
| `99309c6` | Part B, the ESA login |
| `74a014c` / `99c0db9` | Part A notes + CP3 fix |
| `c62ab15` | Part B CP3 fixes |

Part A is `f0b1652` + `74a014c` + `99c0db9`, so a revert of those leaves Part B intact. Suite at `c62ab15`:
**4276 passed / 126 skipped / 703 subtests / 0 failures**. Full record: `CDS_OUTAGE_BUILD_NOTES.md`.

**Switch.** The flag file `~/.config/space_app/cds_mirror` (or `SPACE_APP_CDS_MIRROR=1`; `=0` forces it off),
latched per process. **APP has not created the flag file**: mirror mode is off on this box until Greg, or WB for
its runs, creates it.

**Probe endpoints (MSG 376 item 3a):**
- SIMBAD (all of it, option A): `https://simbad.harvard.edu/simbad/sim-tap/sync`
- VizieR: `https://vizier.idia.ac.za/viz-bin/votable`

**Limits (A1, the exact query texts, 2 passes × 10 anchors):**
- Every SIMBAD query on CfA took ≤ 1.37 s, so every SIMBAD / xray limit is **unchanged**. This includes the otype
  split's three queries (≤ 0.49 s each), the four CR-26 / CR-24 seams (0.29–1.37 s), `query_object` and
  `query_objectids`.
- VizieR on IDIA: slowest real answer **5.83 s**. The limit is **60 s fixed** per request, 2 attempts, each
  wall-bounded at 70 s, with a per-catalog breaker that trips on timeouts only.
- **Cut-off threshold (MSG 380 amendment 3): 60 s, per attempt.** That sits between the 5.83 s slowest real answer
  and IDIA's 68.8 s cut-off. In practice the 60 s request timeout fires first, so a cut-off reads
  "CDS VizieR request timed out. Try again." (VA7: 125 s, exit 1, never `count: 0`).

**VizieR calls by search shape (amendment 2;** `core/`, `query.py`, `gui/` — `gui/` has none):
| Shape | Call sites |
|---|---|
| Cone | `binary.py:745` SB9, `:797` WDS, `:817` ORB6 (absent on IDIA and CDS); `debris_disk.py:104` J/ApJS/211/25 and J/ApJS/225/15, `:113` II/328/allwise; `xray_catalog.py:148` IV/39/tic82 |
| Small-catalog filter / read | `binary.py:762` SB9 `Seq:=`; `:1505` / `:1527` the census SB9 reads |
| Large-catalog non-position | `twomass.py:70`, **now a 3″ cone at the decoded position in mirror mode**; and the free-form `vizier-query` (no CR-29 case uses it) |

**Coverage (A0b):** every catalog above is on IDIA except ORB6, which isn't on CDS either. Your three debris-disk
cases: byte-identical (MSG 377).

**Stderr lines (items 3b, 6):**
- `[cds-mirror] SIMBAD→simbad.harvard.edu VizieR→vizier.idia.ac.za — temporary, on since <date> (<n>d)` (or
  `… on via SPACE_APP_CDS_MIRROR`), once per process, at the first mirror-routed client
- `[cds-mirror] X-Match has no mirror — census SB9 rows dropped; this census output is not valid`
- **Part B's lines are `[gaia-login] …`, renamed from MSG 376's `[gaia] …` examples**, because HEAD's CR-19 already
  writes `[gaia] sync TAP bounded (timeout) — degrading: …` real-degrade lines. The per-process state line is one
  of:
  - `[gaia-login] logged in`
  - `… anonymous (no credentials)`
  - `… anonymous (login not used — continuing anonymous)`
  - `… anonymous (login paused by back-off marker)`
  - `… anonymous (legacy unbounded path)`

  Plus `[gaia-login] logged-in job not accepted by the account — continuing anonymous` and
  `[gaia-login] job cleanup skipped — job <id> left on the account`. **No `[gaia-login]` line means the run made
  no Gaia call.**
- Every literal is tested against your `score_cr30.py:69-71` and `:119` patterns, verbatim: none matches.
- **Ask:** strip only `^\[(cds-mirror|gaia-login)\] ` lines in your `error_text` reader.
- Stdout error strings for mirror failures **do** match `SERVICE` by design: "Could not connect to CDS VizieR…",
  "CDS VizieR request timed out…", "Could not connect to CDS X-Match: it has no mirror…".

**Concurrency (item i):** the 10 Gaia anchors × 4 parallel processes gave **0 × 429 anonymous, 0 × 429 logged in**.
Whether ESA's "active" count includes sync jobs is **not determinable**: no 429 either way, and the docs are silent.
Logged in, there is **one ESA login per process**, outside every query bound, with the session reused on fresh
clients.

**VB2 (item 2):** the 10 Gaia anchors, mirror on and logged in: **10/10 byte-identical** to `base1`, to the
anonymous run and to VA3. Census `--include nss` logged in matches anonymous; 0 NSS rows at 15 ly / 30 d, so the
50k-row-cap difference isn't exercised. 0 jobs were left on the account.

**Condition 1 (VA5):** the otype split against the single join, both on IDIA: **13/13 identical** row multisets and
`_interpret_otype_rows` output. That set includes G 272-61 (head / candidate), `* alf CMa` (both ids on one oid),
an id that matches nothing, and EZ Aqr / 61 Cyg / EV Lac. No real multi-oid id was found, so that case is
unit-tested only.

**Condition 2 (VA6):** all four CR-26 / CR-24 seams **run as written on CfA; none needed a split**. Known answers:
Vega's astrometry (plx 130.23, A0V), velocity (−13.5) and 60″ cone, and α Cen A's parent. The `Gaia DR3 <id>`
query shape completed, but its test id returned no object, so it is a shape check only.

**Condition 3 (the anchors per path):**
- **The otype split:** every `exclusion-system` / `exclusion-boundary` `--star` run (the CR-25 active-wind
  auto-detect). Examples: GJ 65 (`a1.1-live-es`), `a4.8-es-70oph`, `a2.6-2plus2`, EV Lac.
- **The seams** (astrometry / parent / velocity / cone): the same `exclusion-system --star` runs with the per-star
  wind model.
- **`query_object` / `query_objectids`:** every `--star` run.
- **The 2MASS cone: 306 `base1` runs**, listed below; every K / M `--star` run with a 2MASS id.

**VA3 tally on CfA:** 289 mirror runs against `base1`, scored with your helpers: 256 byte-identical, 0 degraded,
33 `star-regions` `teff` / `fe_h` row-order cases (MSG 381, ruled (a)).
**The per-case list you asked for (MSG 382):** the `base1` and mirror values, each checked against a fresh read of
the star's `mesFe_h` rows on CfA. **29/33 have every value present.** The four that don't:
- **G 169-29:** the mirror `teff` 3244.5 is the **median** of its 6 CfA rows. Row 0 is empty, so CR-27.2's
  median rule applied; that is the rule's own output, not a row.
- **HD 16765, `* sig CrB C`, G 70-50:** the `base1` `fe_h` (−0.0417, −0.1400, −0.1200) is neither a CfA row nor
  CfA's median. By your rule 3 these are **content differences** (CDS-side data CfA lacks) and wait for CDS:
  3 stars.

(✗ = not a row value in CfA's `mesFe_h` rows for that star; every unmarked value is present.)

| Case | Star | teff base1 | teff mirror | fe_h base1 | fe_h mirror |
|---|---|---|---|---|---|
| bench-B12-37 | GJ 15A | 3609 | 3603 | -0.300 | -0.280 |
| bench-B12-41 | GJ 205 | 3737 | 3701 | 0.210 | 0.210 |
| bench-B12-47 | GJ 526 | 3950 | 3694 | -0.230 | -0.380 |
| bench-B12-54 | GJ 725B | 3519 | 3500 | -0.360 | -2.340 |
| bench-B12-63 | GJ 53A | 5178 | 5250 | -0.750 | -0.620 |
| bench-B12-75 | GJ 436 | 3507 | 3469 | -0.220 | 0.040 |
| bench-B12-88 | GJ 764 | 5246 | 5143 | -0.270 | -0.250 |
| bench-B13-119 | HD 103095 | 5095 | 5110 | -1.290 | -1.350 |
| bench-B13-165 | HD 157214 | 5825 | 5714 | -0.390 | -0.380 |
| bench-B13-41 | HD 5015 | 5986 | 6196 | -0.309 | 0.000 |
| bench-B13-42 | HD 6210 | 6148 | 6065 | -0.150 | -0.170 |
| bench-B13-50 | HD 10697 | 5605 | 5610 | 0.090 | 0.161 |
| bench-B13-54 | HD 11964 | 5013 | 5332 | 0.090 | 0.080 |
| bench-B13-57 | HD 16765 | 6356 | 6236 | -0.042 ✗ | 0.030 |
| bench-B13-88 | HD 49933 | 6609 | 6635 | -0.430 | -0.430 |
| bench-M15-114 | Ross   47 | 3391 | 3321 | -0.160 | -0.210 |
| bench-M15-133 | Wolf 1421 | 3565 | 3576 | -0.470 | -0.450 |
| bench-M15-150 | Wolf  358 | 3265 | 3200 | 0.086 | 0.160 |
| bench-M15-151 | G  44-42 | 3372 | 3416 | -0.030 | -0.260 |
| bench-M15-156 | BD+44  2051B | 3000 | 3167 | -0.390 | -0.630 |
| bench-M15-168 | HD 115404B | 3852 | 3709 | -0.331 | -0.120 |
| bench-M15-171 | BD+11  2576 | 3721 | 3699 | -0.150 | -0.150 |
| bench-M15-176 | * tet Boo B | 3500 | 3479 | -0.110 | -0.110 |
| bench-M15-182 | * sig CrB C | 3540 | 3594 | -0.140 ✗ | -0.220 |
| bench-M15-183 | G 202-48 | 3412 | 3557 | -0.270 | -0.401 |
| bench-M15-185 | G 169-29 | 3100 | 3244.5 ✗ | -0.120 | -0.030 |
| bench-M15-186 | Ross  644 | 3934 | 5542 | -0.517 | -0.453 |
| bench-M15-191 | G 203-47 | 3284 | 3218 | 0.200 | 0.330 |
| bench-M15-204 | HD 165222 | 4991 | 3614 | -0.105 | -0.220 |
| bench-M15-71 | HD   1326B | 3250 | 3218 | -0.300 | -0.300 |
| bench-M15-74 | HD   6660B | 4699 | 3282 | 0.191 | 0.210 |
| bench-M15-76 | G  70-50 | 3930 | 3935 | -0.120 ✗ | 0.010 |
| bench-M15-85 | G 159-46 | 3257 | 3257 | 0.090 | 0.160 |

**Also changed since MSG 379:**
- X-Match is skipped at once in mirror mode, so the census no longer waits on the dead host.
- Option 50 is refused in mirror mode.
- The VizieR limit is **not** relied on for 2MASS (the cone is); v5's `vizier-query` note is replaced by the loud
  failure.
- A 2MASS key that doesn't decode gives `twomass_status: unreachable`, which **won't clear on rerun**.

**D1 rule:** run Gaia-heavy passes at `--workers ≤ 4` with the GUI closed.
**`query.py gaia-jobs [--cleanup]`:** lists or cleans this account's own `space_app-*` jobs only (finished
≥ 10 min, or older than 2 h).

**2MASS-cone anchor runs (306, `base1` ids):** a2.1-eb-gjB, a2.1-eb-glB, a2.1-eb-glieseB, a2.1-eb-sys, a2.3-eb, a2.5-cyg1-eb, a2.5-cyg3-eb, a2.5-cyg4-eb, a2.5-ez1-eb, a2.5-ez5-eb, a2.5-ez6-eb, a2.5-stf1-eb, a2.5-stf3-eb, a2.5-stf4-eb, a3.2-lac-eb, a3.2-ross-eb, acc-2.1b, acc-2.4b, acc-3.2, acc-3.3, acc-3.3b, acc-3.4a, acc-3.4b, acc-3.6a, acc-3.6b, acc-3.6c, acc-3.8, acc-4.4a, acc-4.4b, acc-4.6b, acc-4.7a, acc-4.7b, acc-4.7c, acc-4.8a, acc-4.8b, acc-5.2a-json, acc-5.2b-json, acc-5.4-json, acc-6.11a, acc-6.11c, acc-6.11d, acc-6.11e, acc-6.11f, acc-6.11g, acc-6.11h, acc-6.12a, acc-6.12b, acc-6.12c, acc-6.12d, acc-6.12e, acc-6.12i, acc-6.12m, acc-6.12o, acc-6.2c, acc-6.2d, acc-6.6f, acc-6.6g, acc-6.7c, acc-6.8d, acc-6.8h-json, acc-6.8j, acc-6.9a, acc-6.9b, acc-6.9c, acc-6.9d, acc-6.9h, acc-6.9i, acc-6.T1-eb, acc-6.T10-eb, acc-6.T11-eb, acc-6.T12-eb, acc-6.T13-eb, acc-6.T14-eb, acc-6.T15-eb, acc-6.T16-eb, acc-6.T17-eb, acc-6.T2-eb, acc-6.T22-eb, acc-6.T23-eb, acc-6.T24-eb, acc-6.T25-eb, acc-6.T3-eb, acc-6.T4-eb, acc-6.T5-eb, acc-6.T6-eb, acc-6.T7-eb, acc-6.T8-eb, acc-6.T9-eb, b-epseri, b-proxima, bench-B12-37, bench-B12-38, bench-B12-40, bench-B12-41, bench-B12-44, bench-B12-47, bench-B12-48, bench-B12-50, bench-B12-53, bench-B12-54, bench-B12-56, bench-B12-57, bench-B12-63, bench-B12-64, bench-B12-67, bench-B12-75, bench-B12-80, bench-B12-81, bench-B12-82, bench-B12-88, bench-B12-90, bench-B12-92, bench-B12-94, bench-B12-97, bench-B13-102, bench-B13-103, bench-B13-104, bench-B13-105, bench-B13-115, bench-B13-116, bench-B13-118, bench-B13-119, bench-B13-123, bench-B13-126, bench-B13-129, bench-B13-130, bench-B13-138, bench-B13-141, bench-B13-142, bench-B13-147, bench-B13-152, bench-B13-165, bench-B13-170, bench-B13-171, bench-B13-186, bench-B13-187, bench-B13-194, bench-B13-201, bench-B13-202, bench-B13-203, bench-B13-204, bench-B13-206, bench-B13-213, bench-B13-215, bench-B13-35, bench-B13-38, bench-B13-39, bench-B13-41, bench-B13-42, bench-B13-45, bench-B13-48, bench-B13-50, bench-B13-51, bench-B13-54, bench-B13-57, bench-B13-58, bench-B13-63, bench-B13-65, bench-B13-74, bench-B13-79, bench-B13-80, bench-B13-88, bench-B13-91, bench-M15-100, bench-M15-103, bench-M15-104, bench-M15-105, bench-M15-106, bench-M15-107, bench-M15-108, bench-M15-109, bench-M15-110, bench-M15-112, bench-M15-114, bench-M15-115, bench-M15-116, bench-M15-122, bench-M15-123, bench-M15-125, bench-M15-128, bench-M15-129, bench-M15-132, bench-M15-133, bench-M15-135, bench-M15-140, bench-M15-142, bench-M15-143, bench-M15-145, bench-M15-147, bench-M15-149, bench-M15-150, bench-M15-151, bench-M15-156, bench-M15-157, bench-M15-158, bench-M15-165, bench-M15-166, bench-M15-167, bench-M15-168, bench-M15-171, bench-M15-172, bench-M15-174, bench-M15-175, bench-M15-176, bench-M15-177, bench-M15-182, bench-M15-183, bench-M15-184, bench-M15-185, bench-M15-186, bench-M15-187, bench-M15-188, bench-M15-190, bench-M15-191, bench-M15-194, bench-M15-195, bench-M15-196, bench-M15-198, bench-M15-199, bench-M15-201, bench-M15-204, bench-M15-206, bench-M15-208, bench-M15-212, bench-M15-213, bench-M15-214, bench-M15-215, bench-M15-221, bench-M15-224, bench-M15-225, bench-M15-229, bench-M15-231, bench-M15-232, bench-M15-234, bench-M15-235, bench-M15-236, bench-M15-237, bench-M15-242, bench-M15-244, bench-M15-248, bench-M15-68, bench-M15-71, bench-M15-74, bench-M15-75, bench-M15-76, bench-M15-77, bench-M15-79, bench-M15-80, bench-M15-81, bench-M15-82, bench-M15-83, bench-M15-84, bench-M15-85, bench-M15-91, bench-M15-93, bench-M15-96, bench-M15-97, bench-M15-99, card-61-cygni__do_61CygA_120-json, card-61-cygni__do_61CygB_120-json, card-61-cygni__eb_61CygA_04120, card-61-cygni__eb_61Cyg_04120, card-alpha-cent__do_ProximaCentauri_120-json, card-alpha-cent__exclus_ProximaCentauri041204e15, card-barnards-s__do_GJ699_120-json, card-barnards-s__eb_GJ699_04120, card-barnards-s__exclus_GJ699041204e15, card-epsilon-er__do_EpsilonEridani_120-json, card-epsilon-er__eb_EpsilonEridani_04120, card-epsilon-in__do_HD209100_120-json, card-epsilon-in__eb_HD209100_04120, card-epsilon-in__exclus_HD209100041201e14, card-ez-aquarii__do_EZAqr_120-json, card-ez-aquarii__eb_EZAqr_04120, card-gj-65__do_GJ65_120-json, card-lacaille-9__do_Lacaille9352_120-json, card-lacaille-9__exclus_Lacaille9352041201e14, card-lalande-21__do_Lalande21185_120-json, card-lalande-21__eb_Lalande21185_04120, card-lalande-21__exclus_Lalande21185041202e15, card-ross-128__do_Ross128_120-json, card-ross-128__eb_Ross128_04120, card-ross-154__do_Ross154_120-json, card-ross-248__do_Ross248_120-json, card-ross-248__eb_Ross248_04120, card-sigma-drac__do_SigmaDraconis_120-json, card-sigma-drac__eb_SigmaDraconis_04120, card-struve-239__do_GJ725A_120-json, card-struve-239__do_GJ725B_120-json, card-struve-239__eb_BD591915_04120, card-struve-239__eb_GJ725A_04120, card-struve-239__eb_GJ725B_04120, card-wolf-359__do_Wolf359_120-json, card24-epseri_eb_supplied, cr27-eb_61_cyg_a_gaiahook, cr27-eb_denis_j104814_6_395606, cr27-eb_epsilon_indi, cr27-eb_ev_lac, cr27-eb_ev_lac_a13, cr27-eb_ev_lac_b05, cr27-eb_ez_aqr_b05, cr27-eb_ez_aqr_l05, cr27-eb_hd_79210, cr27-eb_hd_79211, cr27-eb_hd_79211_l05, cr27-eb_proxima_cen

**AWAITING:** WB — your equivalence check on mirror mode, once Greg or WB creates the flag file.
```
