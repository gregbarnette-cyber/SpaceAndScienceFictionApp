# CDS outage fallback + ESA Gaia login — implementation plan

**Status:** DRAFT v7 (2026-11-11).
- **Folded in:**
  - **three** plan-review rounds (§8)
  - Greg's rulings D1–D3 (§7)
  - WB's answers MSG 376 (§10), MSG 378 (option A, §11) and MSG 380 (§12)
- **Nothing is open on the channel.** One APP-side naming change (Part B's stderr prefix becomes `[gaia-login]`,
  §2.1) goes to WB in the post-build message.
- **The build is HELD until Greg approves v7. Nothing has been built yet.**

**Context:** CDS Strasbourg (SIMBAD, VizieR, X-Match) has been down since at least 2026-10-28 after a cybersecurity
incident (https://cds.unistra.fr/, notice updated 2026-11-09, no restoration date). This blocks WB's CR-29 pre-fire
review (session 171).

| Part | What | Lifetime |
|---|---|---|
| **A** | Mirror mode: **all SIMBAD → `simbad.harvard.edu`**, with the otype lookup as three flat queries (§2.2). **VizieR → `vizier.idia.ac.za`**, with 2MASS by decoded-position cone (§2.3b). A loud failure on IDIA's empty-200 cut-off. Bounded limits | **Temporary.** Removed by `CDS_RESTORE_PLAN.md` when CDS returns (§5, §6 step 15) |
| **B** | ESA Gaia login from Greg's credentials file; cleanup of the app's own async jobs (ruling A); `query.py gaia-jobs` (D2) | **Permanent.** It stays after CDS returns, and the credentials file is kept |

Each part is built, reviewed and committed **separately, with its own docs, test-harness hunks and tests inside its
own commit**, so removing A never touches B.

---

## 1. Evidence (gathered 2026-11-11, read-only; details in MSG 375 / 377 / 379)

- **Mirror data equals CDS data.**
  - IDIA's `B/wds/wds`, `B/sb9/main` and `B/sb9/orbits` match WB's 2026-10-22 CDS pulls row for row. WB re-pulled
    them with its own script and got byte-identical md5s (MSG 376).
  - 43 mirror-served runs against `base1`: SIMBAD fields 73/73 on CfA and 28/28 on IDIA, with **0 value mismatches**
    (MSG 377).
- **VizieR coverage (checked; MSG 377).**
  - On IDIA: II/246, IV/39/tic82, II/328/allwise, J/ApJS/211/25, J/ApJS/225/15, B/sb9, B/wds, B/cb, I/311, I/355.
  - `B/orb6/orbits` is absent, as it is on CDS (no change).
  - The three debris-disk cases are byte-identical to `base1` (released by WB, MSG 378).
  - User catalogs passed to the free-form `vizier-query` remain A0b's to check.
- **SIMBAD.**
  - `simbad.harvard.edu` (CfA) has data to **2026-10-14**, the closest to `base1`. `simbad.idia.ac.za` has data to
    **2026-04-22** (`MAX(update_date)`).
  - astroquery 0.4.11 accepts only `simbad.cds.unistra.fr` / `simbad.harvard.edu`.
  - On CfA, flat or `ident`-keyed queries answer in about 0.2 s. **Joining `otypes` to `basic` 504s at 60 s**,
    whether through the full three-way join or with a `b.oid IN (…)` list.
  - All four CR-26 / CR-24 seam shapes answer on CfA in 0.20–0.26 s (round-2 review probes).
  - IDIA completes the single otype join in about 110 s. **It is used only for VA5's equivalence check.**
- **IDIA VizieR query shapes (§2.3b).**
  - Cones take 1.5–3.5 s. Small-catalog reads take 1.8–4.1 s.
  - A non-position query on a huge catalog gets an **empty 200 after about 68.8 s (a server cut-off)**. astroquery
    then returns **`None`**, where a genuine empty answer returns an empty `TableList`.
- **The 40-run anchor comparison (pre-fix):** 28 byte-identical; 12 differ only by degrade markers (otype timeouts;
  the 2MASS cut-off; ESA FLAME blips and 429s).
- **ESA quotas:**

  | | Anonymous | Logged in |
  |---|---|---|
  | Queued | 50, shared by all anonymous users | 50 own |
  | Active | 100 shared | 5 |
  | Async timeout | 1 min | 120 min |
  | Rows | 50,000 | unlimited |
  | Retention | 24 h | until deleted |

  - A logged-in sync query leaves no stored job. Only async jobs persist (`binary.py:1422`, `gaia-tap --async`).
  - Greg's account login works.
  - ESA maintenance is scheduled for 2026-11-12 16:00 CET. ESA's "release 3.15 breaking changes" is checked in B0.
- **WB's runner** removes `SPACE_APP_*`. It has `TIMEOUT_S = 900` per run (`run_cr29_cases.py:48`) and defaults to
  `--workers 4`. Its scorer's `error_text` (`score_cr30.py:462-466`) includes **stderr** for non-JSON errors
  (`score_cr29.py:667-669`).

---

## 2. Part A — mirror mode (TEMPORARY)

### 2.1 The switch, and its stderr lines

- **One module, `core/cds_mirror.py`,** holds:
  - the hosts and `enabled()`
  - `vizier_server_kwargs()`, `vizier_timeout()`, `apply_simbad()`, `timeout_default()`, `announce()`
  - the cache-skip service list and the 2MASS decoder

  No other module hard-codes a mirror host.
- **Mirror mode is on** when the flag file `~/.config/space_app/cds_mirror` exists or `SPACE_APP_CDS_MIRROR=1` is
  set.
  - `SPACE_APP_CDS_MIRROR=0` forces it off.
  - Off is byte-identical to HEAD.
  - **`enabled()` is latched once per process, under a `threading.Lock`.**
- **The mode line.** Exactly one per process, written by a latched `announce()`.
  - It is called from `apply_simbad()`, `vizier_server_kwargs()` and the X-Match emitter (§2.6). Those are the
    points where a mirror-routed client is built or a mirror event happens. Every SIMBAD and VizieR path passes
    through one of them; the round-3 review checked this site by site.
  - Its check-and-set and the write sit under one `threading.Lock`. Seams run in CR-19 daemon threads, and the GUI
    runs workers in parallel.
  - So the line means "a mirror-routed client was built in this process". A run served entirely from cache prints
    none.
  - argparse / usage errors never reach those points, so their stderr stays byte-identical to HEAD (WB's
    `error_text` includes stderr for non-JSON errors).
  - The two texts:
    - Flag file: `[cds-mirror] SIMBAD→simbad.harvard.edu VizieR→vizier.idia.ac.za — temporary, on since 2026-11-12 (3 d)`
    - Env only: `[cds-mirror] SIMBAD→simbad.harvard.edu VizieR→vizier.idia.ac.za — temporary, on via SPACE_APP_CDS_MIRROR`
- **Event lines** may follow the mode line: the X-Match line (§2.6).
- **GUI:** "CDS MIRROR MODE" in the main window title.
- **Windows:** **no marker.** Nothing reaches the network before `query.py` re-dispatches to the dust env
  (`query.py:5258-5262`), so the parent never prints the line and the child prints it once. v6's marker would have
  suppressed the only line.
- **Prefixes.** Part A's lines start with `[cds-mirror] `.
  - **Part B's start with `[gaia-login] `, not `[gaia] `.** HEAD's CR-19 already writes
    `[gaia] sync TAP bounded (timeout) — degrading: …` (`catalog.py:220, 251`), and a strip of `[gaia]` lines would
    remove those real degrade lines.
  - The post-build message asks WB to strip **only** `^\[(cds-mirror|gaia-login)\] ` lines in its `error_text`
    reader, and tells WB about the rename from MSG 376's `[gaia] …` examples.
- **The wording rule — stderr only.** No new **stderr** line, in any variant with plausible values filled in, may
  match **either** WB pattern. Both are copied verbatim into the tests, with their sources cited:
  - `score_cr30.py:69-71` (`SERVICE`)
  - `score_cr30.py:119` (the stderr degrade regex)
  - So: no exception class names, no `5xx` status, no standalone `502` / `503` / `504`, no "gateway",
    "unreachable" or "timed out".
  - File modes print as **4-digit octal** (`0644`), which can never hit `\b50[234]\b`.
- **Stdout error strings are the opposite.** A mirror *failure* must be visible to WB's scorer. WB detects it only
  by `SERVICE` matching the error text in `route_errors` / `error` (`score_cr30.py:74-91`), so the stdout error
  strings for new mirror failures **must** match `SERVICE` (§2.3b).

### 2.2 SIMBAD — all on CfA (option A; WB pre-fire ruling 61, MSG 378)

| Access | Sites | How it reaches CfA |
|---|---|---|
| astroquery `SimbadClass` (new instances) | `_make_simbad` (`shared.py:1432`), `databases.py:1931` | `astroquery.simbad.conf.server = "simbad.harvard.edu"` (copied at `__init__`, `simbad/core.py:119`) |
| astroquery module instance | `Simbad.query_objectids` (`databases.py:310`, `calculators.py:242`) | set `astroquery.simbad.Simbad.server` (it is created at import) |
| raw TAP: otype lookup | `fetch_star_otypes` (`databases.py:~716`) → `_simbad_otypes_tap` (`:573-590`) | `conf.server`; **in mirror mode, the three-query split below** |
| raw TAP: CR-26 / CR-24 seams | `databases.py:~753` (`_simbad_cr26_tap`): astrometry, parent, velocity, cone | `conf.server`. **Run as written**; all four shapes measured at 0.20–0.26 s on CfA |

- **`apply_simbad()` is idempotent and lazy.** It is called at every site above, *including the two raw-TAP seams*,
  so no first access can reach CDS. When off it is a no-op.
- **The otype lookup in mirror mode: three flat queries, joined in Python** (round-2 HIGH; the `IN`-list join
  504s on CfA):
  - **Why the old two-step was wrong.** HEAD's `_otypes_query` (`databases.py:592-607`) queries **one or two ids**
    (`i.id = '<main_id>' OR i.id = '<A-candidate>'`). It returns `qid = i.id`, the **stored identifier that matched,
    not the query string**. `_interpret_otype_rows` (`:619-662`) groups rows per object by these qids. My two-step
    would have lost that.
  - **The new function `_simbad_otypes_split(ids)`** in `databases.py` (mirror mode only). `_otypes_query` also returns
    its `ids`; it stays pure, and its ADQL is unchanged.
    1. `SELECT oidref, id FROM ident WHERE <HEAD's exact WHERE over ids>`. **Empty → return `[]`, with no further
       query.** That is the join's own empty answer, so downstream it is `_interpret` → `_OtypeResultError` →
       HEAD's status.
    2. `SELECT oidref, otype FROM otypes WHERE oidref IN (<distinct oidrefs>)`
    3. `SELECT oid, main_id FROM basic WHERE oid IN (<distinct oidrefs>)`
  - **Output:** one `(main_id[oid], ident.id, otype)` tuple for each ident row × otype row of that oid. That is the
    inner join's exact row multiset, including duplicates, an id with several oids, and both ids hitting the same
    oid. Objects are never merged.
  - **Integration:**
    - `fetch_star_otypes` chooses `_simbad_otypes_split` or `_simbad_otypes_tap` **inside the same
      `_bounded_call(..., retries=2, fatal=(_OtypeResultError,))`**, so one watchdog, one breaker and one status
      mapping cover all three calls.
    - Each sub-call maps `DALQueryError` / `KeyError` to `_OtypeResultError` exactly as `_simbad_otypes_tap` does.
    - `_simbad_otypes_tap` itself is untouched (`test_cr25.py:712-727` calls it directly).
    - Step 1 keeps HEAD's alias (`FROM ident AS i WHERE i.id = …`), so HEAD's WHERE text is reused exactly.
    - Any oid missing from step 3 is dropped, as the inner join would drop it (no `KeyError`).
    - The three sub-queries go through **one module-level seam, `_simbad_tap_rows(adql)`**, so `tests/conftest.py`
      and the new tests can stub them. The existing otype stubs patch `_simbad_otypes_tap`, which the split
      bypasses.
    - The cache key is unchanged, and the cached row shape is the same.
- **The CR-26 / CR-24 seams need no split.**
  - Measured: astrometry 0.26 s, parent 0.21 s, velocity 0.20 s, cone 0.20 s.
  - A1 re-times them, including the `Gaia DR3 <id>` idents (`xray_catalog.py:695/747`).
  - **Rule:** if any seam later fails on CfA and has no exact flat split, its family is reported to WB as "not
    covered in mirror mode; waits for CDS". This doesn't block the build.
- **A0:** the build re-greps all SIMBAD access (`core/`, `query.py`, `gui/`) and lists every site in the CP1 notes.
  `main.py` (deprecated) is not wired.

### 2.3 VizieR — `vizier.idia.ac.za`

- **Two `Vizier(` sites,** and none in `gui/` or `query.py`.
  - **`catalog.vizier_query` (`catalog.py:121-159`), in mirror mode only, uses a new producer.** This is round-3's
    HIGH fix: wrapping HEAD's `_run` in a watchdog would leave an abandoned thread still retrying and resetting the
    process-wide socket timeout.
    - Inside the same `catalog_cache.cached("vizier", params, …)` call, the producer runs
      `_bounded_call(_mirror_attempt, timeout=vizier_timeout()+10, retries=2, backoff=…, fatal=(_VizierCutOff,))`.
      That is CR-19's pattern.
    - Each `_mirror_attempt` builds a **fresh** `Vizier(columns=…, column_filters=…, row_limit=…,
      timeout=vizier_timeout(), **vizier_server_kwargs())` and makes **one** query: `query_region` or
      `query_constraints`, `cache=False`.
    - There is **no `_timeout_ctx` and no `_with_retries`** on this path. An abandoned attempt holds only its own
      client and its own socket, and makes no further attempts.
    - **Flag off → HEAD's `_run` unchanged, byte-identical.**
    - `vizier_timeout()` is read in `vizier_query`'s body, never inside `_run`, to avoid `UnboundLocalError`. It
      honours `SPACE_APP_VIZIER_TIMEOUT` **only when mirror mode is on**.
  - **`xray_catalog._tic_query` (`xray_catalog.py:147`)** gains `**vizier_server_kwargs()` (`{}` when off) and keeps
    its `_family_call` bounds (30 s, 2 attempts).
- **Every VizieR call by search shape** (WB MSG 380 amendment 2). The CP1 notes list every call site in `core/`,
  `query.py` and `gui/` as one of:
  - cone
  - small-catalog read or filter
  - large-catalog non-position query

  They confirm the third kind is only `twomass.py:67` (a cone in mirror mode, §2.3b) and the free-form
  `vizier-query`.
- **A0b:** each catalog used is confirmed on IDIA. This is done for the core set (§1). The CP1 notes add any user
  catalog that the case files pass to `vizier-query`.

### 2.3b IDIA's cut-off: 2MASS by cone, and every failure loud

**The cut-off.**
- A non-position query on a huge catalog gets no answer for about 68.8 s, then an empty HTTP 200.
- With the request timeout at 60 s, below the cut-off, the client **raises a read timeout at about 60 s**. It never
  sees the empty 200, so the cut-off stays a loud failure. (In the probes the client waited longer.)
- An empty or otherwise unparseable body makes astroquery return **`None`** (`vizier/core.py:755-774`), where a
  genuine empty answer is an empty `TableList`. That is a **guard**, unit-tested, not the expected path.

**2MASS lookup in mirror mode** (WB pre-fire ruling 62, MSG 380). It lives inside `twomass._ii246_seam`, so the CR-30
seam rule holds.
- **Decode** the key, which is `designation.split("J",1)[1]`, e.g. `18365633+3847012` (no dots), against the
  pinned regex `^(\d\d)(\d\d)(\d\d)(\d\d)([+-])(\d\d)(\d\d)(\d\d)(\d)$`.
  - The sign comes from the character, never from `int("-00")`.
  - **Designations truncate, they don't round.** The decoded position is the truncated value, within about 0.2″ of
    the true position.
- **The query:** a **3″ cone** on `II/246/out` with `row_limit=50`, then keep only rows whose `2MASS` column equals
  the key exactly, then apply HEAD's `row_limit=5` to that set.
- **A regex miss** → `{"error": …}` → HEAD's `twomass_status: unreachable`. It never falls back to the designation
  query.
  - Disclosed: that marker does not clear on rerun.
- **Flag off** → HEAD's designation query, byte-identical.
- **Disclosed:** the cone's cache key differs from the designation key, so 2MASS rows cached from CDS aren't reused.

**Making failures loud** (round-3 fixes, plus WB MSG 380 amendment 3).
- **In `vizier_query`'s mirror producer:**
  - **`res is None`** → raise `_VizierCutOff("VizieR mirror unreachable: empty answer (server cut-off)")`.
    `_bounded_call` treats it as **fatal**: no retry, because the cut-off is deterministic for that query shape.
  - **The backup (amendment 3)** is timed **per attempt, inside the attempt**, around the single astroquery call. An
    attempt that returns **0 rows after ≥ 60 s of its own elapsed time** raises the same `_VizierCutOff`.
    - A failed first attempt plus backoff never counts toward the next attempt's elapsed time. This fixes a v6 bug
      that would have flagged a genuine empty SB9 / WDS cone after a retry.
    - With a 60 s request timeout the backup rarely fires. It is kept as amendment 3's safety net.
    - The threshold sits between the slowest real answer (4.1 s; A1 re-measures) and the cut-off, and is reported
      to WB.
- **In `_tic_query`:** `None` → raise a plain exception, so `_family_call` retries and then gives HEAD's
  `unreachable` with its `[cr26] tic bounded (unreachable) — degrading` line.
  - Today `None` becomes `{"answered": True, "sources": []}` (`xray_catalog.py:151`), a silent "no TIC row".
  - There is no "fatal" and no 60 s backup for TIC: `_family_call` (shared with HEASARC) is untouched, the 30 s
    watchdog fires first, and TIC is a 5″ cone, which the cut-off doesn't affect.
- **Stdout error strings for WB's scorer.** `vizier_query` returns `_route_error(_network_error_msg(e, "CDS VizieR"))`.
  - `_VizierCutOff`'s message contains "unreachable", so `_network_error_msg` gives
    **"Could not connect to CDS VizieR…"**: an intended `SERVICE` match.
  - A `_bounded_call` wall-bound timeout or an open breaker yields **"CDS VizieR request timed out. Try again."**
    (HEAD's own wording). The producer maps `_WatchdogTimeout` and breaker-open to a `requests` `Timeout` before
    `_network_error_msg`, so the bare watchdog text never reaches stdout.
  - Unit tests pin both strings against `SERVICE`.
- **The free-form `vizier-query`** goes through the same path, so a cut-off errors loudly. v5's separate note is
  dropped.

### 2.4 Time limits, attempts, breakers (mirror mode; off = today's values)

**Precedence:** explicit env > mirror default > built-in. Every mirror-only env var (`SPACE_APP_VIZIER_TIMEOUT`) is
ignored when off.

| Limit | Code | Today | Mirror mode |
|---|---|---|---|
| VizieR per request | `catalog.py:121` | 60 s, 3 attempts (2 + 4 s backoff), `_timeout_ctx`, no wall bound | **60 s, fixed** (≤ the cut-off; **not** set by A1). The §2.3 producer gives 2 attempts, each wall-bounded at 70 s by `_bounded_call`; the call's worst case is 2 × 70 s + backoff ≈ 142 s |
| VizieR breaker (mirror only) | new, in the §2.3 producer | — | **Trips on timeout only, never on a cut-off** (CR-19's rule, `catalog.py:224-231`). The cut-off is already fatal per query, and tripping on it would block valid cones in a long GUI session. Checked **before** the producer, with a `cache_get` fallback, as the Gaia breaker does (`catalog.py:429-435`). Auto re-arms after a 60 s cool-down. Its open state yields HEAD's "timed out" string |
| TIC (`SPACE_APP_TIC_TIMEOUT`) | `xray_catalog.py:90-98` | 30 s watchdog, 2 attempts | **unchanged** |
| SIMBAD raw TAP (otype, CR-26) — `SPACE_APP_SIMBAD_TIMEOUT` | `databases.py:528/566`, used `:716/:776` | 30 s, 2 attempts | **from A1**; expected unchanged (otype split 3 × ~0.2 s; seams 0.20–0.26 s) |
| CR-26 identity outer watchdog | `xray_catalog.py:35/75-77/197` (by env name; `SPACE_APP_XRAY_TIMEOUT` / HEASARC unchanged) | 30 s | ≥ the sum of the inner lookup's calls (from A1) |
| Main SIMBAD lookup socket bound `_timeout_ctx(30)` | `databases.py:303`, `calculators.py:236` | 30 s | from A1 (CfA about 0.2 s; likely unchanged) |
| SIMBAD / xray breaker cool-downs | `databases.py:530`, `xray_catalog.py:36` | 60 s | ≥ the per-attempt bound |

- **A1 — measure (light load)** on the exact hosts and query texts. Time 2× on the 10 slowest CR-29 anchors:
  - the otype split's three queries
  - the four CR-26 / CR-24 seams, including the `Gaia DR3 <id>` idents
  - `query_object` (`mesfe_h`), `query_objectids`
  - the 2MASS cone
  - **every VizieR shape:** the TIC, WDS, SB9 and **AllWISE** cones; the **SB9 `Seq=` filter**; the census SB9
    reads; the **two debris-disk small reads** (`J/ApJS/211/25`, `J/ApJS/225/15`)
- **The A1 rule** sets **the SIMBAD and xray rows only**: ≥ 1.5 × the slowest observed time, rounded up to 30 s.
  **The VizieR per-request limit is fixed at 60 s.** A1's VizieR timings feed the threshold report and VA4.
- **The budget is a hard rule: every run ≤ 720 s** (0.8 × WB's 900 s).
  - VA4 shows it **analytically**: Σ bounds × attempts + backoff, with breakers, **counting each cut-off as a
    timed-out VizieR call (2 × 70 s + backoff)**. It covers `binary-orbit` (4 VizieR calls), the census and
    `exclusion-system --star` with two components.
  - VA4 also shows it **observed** over WB's full equivalence sample at 4-way parallel.

### 2.5 Unchanged by mirror mode

- **Stdout JSON:** no new keys.
- **Untouched:** the FROZEN `compute_exclusion_boundary`, the md5-checked data, and the one-module guardrails.
- **`catalog_cache`:** mirror mode skips cache **writes** inside `catalog_cache.cached(service, …)` (`:100`, the
  only caller of `cache_put`, which only sees a hash).
  - Explicit service list: `vizier`, `cr26_tic`, `simbad_otypes`, `simbad_cr26_astrom`, `simbad_cr26_cone`,
    `simbad_cr26_parent`, `simbad_cr24_velocity`.
  - Reads are kept, because rows cached from CDS are valid.
  - Gaia and HEASARC caching is unaffected.

### 2.6 X-Match: no mirror

- In mirror mode, `close-binary-census` writes
  `[cds-mirror] X-Match has no mirror — census SB9 rows dropped; this census output is not valid` when
  `binary.py:1555-1557` drops rows. Its emitter calls `announce()` first, so the mode line always precedes it.
- WB holds its two census cases (MSG 376 item 4). CR-33.1 waits for CDS.

---

## 3. Part B — ESA Gaia login (PERMANENT)

### 3.1 Credentials (`core/gaia_auth.py`)

- **Lookup order:**
  1. `SPACE_APP_GAIA_CREDENTIALS=<path>`. Empty means anonymous; this is the tests' off-switch.
  2. The default `~/.config/space_app/gaia_credentials`, if it exists.
  3. Anonymous, identical to HEAD.
- **The app never reads the password.** It passes `credentials_file=` to astroquery and always uses
  `verbose=False`.
- **Mode check.** If the mode isn't 600, it writes `[gaia-login] credentials file is readable by group or others (mode 0644)` (the real mode
  filled in as 4-digit octal; the contents are never read). It fires when **any group or other permission bit is set**,
  so a stricter `0400` passes.
- The password never appears in any output, log, exception text or cache key. A sentinel-password test asserts this.
- Windows checkouts and other users have no default file, so they stay anonymous.

### 3.2 Login

- **`TapPlus.login(client, credentials_file=…)`:** TAP only, one POST, and it raises on a wrong password.
  `GaiaClass.login` swallows that error (`gaia/core.py:105-119`).
- The app confirms the logged-in state after the call.
- **Login and `remove_jobs` run inside `_gaia_stdout_to_stderr()`.** Otherwise astropy INFO lines and
  `tapconn.py:686-688`'s print would land on stdout.
- **Sync path:** each fresh CR-19 client logs in inside `_attempt`. Per-process session reuse (through private
  `_Tap__connHandler`) is not planned unless B1 shows per-attempt login is too slow; that would be a CP2 ruling.
- **Async path:** a fresh logged-in `GaiaClass`. The legacy sync path (`SPACE_APP_GAIA_TIMEOUT<=0`) stays anonymous.
- **The login-state line**, once per process at the **first Gaia call** (WB MSG 376 item 3b). Exactly one of:
  - `[gaia-login] logged in`
  - `[gaia-login] anonymous (no credentials)`
  - `[gaia-login] anonymous (login not used — continuing anonymous)`. The exception class appears only under
    `SPACE_APP_GAIA_DEBUG=1`, which WB's runner strips.
  - `[gaia-login] anonymous (login paused by back-off marker)`
  - `[gaia-login] anonymous (legacy unbounded path)`: for the `SPACE_APP_GAIA_TIMEOUT<=0` path, which stays
    anonymous even when credentials exist.
  - **No line means the run made no Gaia call**, not "unknown". The post-build message tells WB this.
- **Failure handling:**
  - A login failure gives the third line, then the HEAD path. A login problem never turns a working query into an
    error.
  - **Per-process latch:** after one failure, the process stays anonymous.
  - **Cross-process back-off on 401/403:** `~/.config/space_app/gaia_login_failed` (a timestamp), 6 h, reported by
    the fourth line. Deleting the marker clears it.
  - No line carries an HTTP status.

### 3.3 Quotas

- **Queued 50:** per account.
- **Async 120 min:** the census pull gets it. The app-side `_timeout_ctx(300)` is an idle bound; B1 checks the pull
  completes under it.
- **Active 5 — D1 (ruled): a documented rule.** Gaia-heavy runs use `--workers ≤ 4` with the GUI closed; no code
  enforces it.
  - **B1 concurrency check** (WB MSG 376 item i): run the 10 Gaia anchors as 4 parallel processes, once anonymous and
    once logged in, and count the 429s. Also find out whether ESA's "active" count includes sync jobs (docs, then
    6 parallel logged-in sync calls).
  - If logged-in runs draw more 429s, report it, and WB runs Gaia-heavy passes at `--workers 2`.
- **429s:** today's marked degrade (`Retry-After` honoured).
- **Cache key:** the Gaia cache key gains `"auth": true` only when logged in, so anonymous keys are unchanged.

### 3.4 Async jobs (ruling A + D2)

- **Every async launch is named `space_app-<uuid4>`.** The job id is captured as soon as the job exists.
- **Cleanup runs in a `finally`:**
  - After `get_results()`, it runs `remove_jobs([job.jobid])`.
  - On failure after the job exists, it deletes every job this call created.
  - A failed delete writes `[gaia-login] job cleanup skipped — job <id> left on the account`.
- **Never "delete all".** Anonymous runs make no delete call.
- **`query.py gaia-jobs [--cleanup]`** (D2, permanent):
  - It lists `space_app-*` jobs.
  - `--cleanup` deletes only those that are `space_app-*` **and** (finished **or** older than 2 h). It never touches
    jobs without the prefix.
  - Not logged in → `{"error"}`, exit 1.
  - Output is JSON on stdout.
  - Indexed in `docs/integration.md` and `docs/query-commands-index.md` (182 → 183).

---

## 4. Tests (offline; never the real files; flag off = HEAD)

- **Harness off-switch, by part.**
  - `tests/_queryharness.py` `make_env` and a session-scoped `tests/conftest.py` fixture set:
    - `SPACE_APP_CDS_MIRROR=0` (Part A's commit)
    - `SPACE_APP_GAIA_CREDENTIALS=` (Part B's commit)

    Each is on its own line, in both files.
  - The build audits all 52 subprocess-using test files.
  - In-process tests monkeypatch both default paths.
  - No test body is edited.
- **The wording test is split by part.** Each file carries its own verbatim copy of both WB regexes, with their
  sources cited, so removing Part A never removes Part B's check.
- **`tests/test_cds_mirror.py` (Part A):**
  - **Switch:**
    - off → `vizier_server_kwargs() == {}`, `conf.server` / `Simbad.server` untouched, built-in limits, no stderr
      line, and `SPACE_APP_VIZIER_TIMEOUT` ignored
    - on via env and via a tmp flag file; `=0` beats the file; `enabled()` latched; `apply_simbad()` idempotent
      (each test restores `conf.server` / `Simbad.server`); limit precedence
  - **The mode line:**
    - **exactly one line under concurrent threads** (the lock)
    - none on a cache-only run
    - the X-Match line is preceded by the mode line
    - **a mirror-mode argparse error has stderr byte-identical to HEAD**
    - one subprocess test with a planted flag file under a tmp HOME, asserting the harness keeps it off
  - **The otype split** (stub `_simbad_tap_rows`), each compared with the join's multiset and with
    `_interpret_otype_rows`'s result:
    - no ident row → `[]` → HEAD's status
    - one id with several oids
    - head and candidate on different oids
    - both ids on the same oid
    - a candidate resolving to the head
    - an oid missing from step 3 → dropped
    - a sub-call error → `_OtypeResultError`
    - step 1 keeps the `i` alias
    - flag off → HEAD's ADQL byte-identical
  - **The VizieR mirror producer** (stub `Vizier`):
    - a fresh client per attempt
    - one query per attempt
    - no `_timeout_ctx` and no `_with_retries` on the mirror path
    - 2 attempts
    - `_VizierCutOff` fatal (1 attempt only)
    - **a genuine 0-row cone returned after a failed first attempt plus backoff is a real empty**, not a cut-off
    - an attempt with 0 rows after ≥ 60 s of its own elapsed time → cut-off
    - `None` → cut-off
    - the breaker trips on timeout, never on a cut-off; it re-arms after its cool-down; an open breaker falls back
      to `cache_get`
    - **the stdout error strings match `SERVICE`** (`Could not connect to CDS VizieR…`; `CDS VizieR request timed
      out. Try again.`), and the bare `_WatchdogTimeout` text never appears
    - flag off → HEAD's `_run` path untouched
  - **TIC:**
    - `None` → plain raise → retried → `unreachable` with HEAD's `[cr26]` line
    - flag off → HEAD's `[]` behaviour unchanged
  - **The 2MASS decode:**
    - **truncation**, including a negative declination near a digit boundary and `-00…`
    - the `J` prefix with and without it
    - a regex miss → `{"error"}` with no fallback
    - cone `row_limit=50` then exact match then 5, with crowding
    - flag off → HEAD's designation filter unchanged
  - the cache-write skip for exactly the 7 services
  - the GUI title helper
  - **The Part A wording test:** the two mode-line forms (ages 0, 1, 3 and 14 d) and the X-Match line, against both
    WB regexes.
- **`tests/test_gaia_login.py` (Part B;** stubs mimic astroquery's real behaviour, including `GaiaClass.login`'s
  swallow):
  - no credentials → no login
  - env and default path → `TapPlus.login` per fresh client
  - wrong password → anonymous, the line, the latch
  - 401 → the back-off marker
  - stdout is valid JSON in every case
  - the sentinel password appears nowhere
  - named async launch; own-id delete; delete in `finally` on failure
  - a failed delete → the line
  - anonymous → no delete
  - the `auth` cache key
  - the mode-bit line (`0644` / `0640` / `0604` fire; `0600` / `0400` don't)
  - the five login-state lines
  - **HEAD's `[gaia] sync TAP bounded …` lines are unchanged**
  - **The Part B wording test:** every `[gaia-login]` literal (job ids such as `1731338474562O`, modes `0644` /
    `0504`), plus the debug-off `ConnectionError` case, against both WB regexes.
- **`tests/test_gaia_jobs.py` (D2):**
  - list-only deletes nothing
  - finished or > 2 h `space_app-*` jobs are deleted
  - running `space_app-*` jobs under 2 h are kept
  - **jobs without the prefix are never touched**
  - one failed delete → reported, the rest continue
  - not logged in → `{"error"}`, exit 1
  - stdout is valid JSON

## 5. Backout of Part A (cross-check list; the restore plan is built from the commit diff — step 15)

- **When:** WB's `service_probe.py check simbad` / `check vizier` are healthy on CDS, and the notice is lifted.
- **Steps:**
  1. **Instant:**
     - `rm ~/.config/space_app/cds_mirror`
     - unset `SPACE_APP_CDS_MIRROR`, `SPACE_APP_VIZIER_TIMEOUT` and any manual `SPACE_APP_*_TIMEOUT`
     - **restart any open GUI** (the switch is latched per process)
  2. **Clean:** revert Part A's commit(s). If the revert conflicts, remove every Part A site:
     - `core/cds_mirror.py` (including `announce()` and its lock)
     - the `announce()` / `apply_simbad()` call sites, including the raw-TAP seams and the X-Match emitter
     - `_simbad_otypes_split`, `_simbad_tap_rows`, the branch in `fetch_star_otypes`, and `_otypes_query`'s added
       `ids` return
     - the `_ii246_seam` cone branch and its decoder (`cds_mirror.decode_2mass_key`)
     - `vizier_query`'s mirror producer:
       - `_mirror_attempt`, `_VizierCutOff`, the per-attempt elapsed check
       - the mirror VizieR breaker and its `cache_get` fallback
       - the `_WatchdogTimeout` → `Timeout` mapping
       - the `vizier_timeout()` read
     - the `vizier_server_kwargs()` splat at **both** `catalog.py` and `xray_catalog.py:147`, and `_tic_query`'s
       `None` raise
     - the `timeout_default()` hooks for the §2.4 SIMBAD / xray rows: `databases.py:528/530/566`,
       `xray_catalog.py:35-36/75-77`, `calculators.py:236`, `databases.py:303`
     - the `catalog_cache.cached` skip
     - the X-Match line
     - the GUI title
     - the harness `SPACE_APP_CDS_MIRROR=0` lines in `_queryharness.py` **and** `conftest.py` (beside Part B's
       lines; resolve by hand)
     - `tests/test_cds_mirror.py`
     - the Part A docs: the `docs/integration.md` block, `docs/core-modules.md`, the `docs/testing.md` history
       entry, the `CLAUDE.md` count

     Part B is untouched.
  3. **Verify:**
     - The suite is green at its pre-A count plus B's.
     - A grep for `cds_mirror`, `cds-mirror`, `harvard.edu`, `idia.ac.za`, `_simbad_otypes_split`,
       `_simbad_tap_rows`, `decode_2mass_key`, `_VizierCutOff`, `_mirror_attempt` and `SPACE_APP_VIZIER_TIMEOUT`
       across `core/`, `query.py`, `gui/` **and `tests/`** finds nothing.
     - **6 CDS anchors** are byte-identical to `base1`, including GJ 65 or EZ Aqr (otype / active wind) and ε Ind
       or EZ Aqr (2MASS M_Ks).
  4. **WB:** the restore message names the restore commit (MSG 376 item iii).

## 6. Build order, checkpoints, validation

### Pre-build — done
- The pre-build WB messages: MSG 375 / 377 / 379 posted; WB answered in MSG 376 / 378 / 380. **Done.**

### Part A
2. **A0:**
   - the SIMBAD sites
   - every VizieR call by shape, `gui/` included
   - A0b (catalogs, including any `vizier-query` user catalogs in the case files)
   - **the 2MASS-cone anchor list:** every CR-29 case whose run reaches `_ii246_seam`, found from the case files'
     argv and a code read

   **A1:** exact-text timings (§2.4).
3. Code, tests (§4, Part A) and **Part A's docs**:
   - the dated "Temporary: CDS mirror mode" block in `docs/integration.md`
   - `docs/core-modules.md`
   - the `CLAUDE.md` count and `docs/testing.md` history
4. **/code-review CP1** on the Part A working tree. Its notes hold the A0 / A0b / call-shape / 2MASS-anchor lists and
   A1's numbers.
5. **Validation VA:**
   - **VA1:** default suite: 4180 + new passed / 126 skipped / 0 failures, **with the real flag file present**.
   - **VA2 (off = HEAD):** the build (off) against a HEAD worktree, **both under `unshare -rn`**. Stdout
     byte-identical.
     - The sample is the **first 20 runs of `cr29-s151/base1/_runs.json` in file order**: a fixed, reproducible
       set.
   - **VA3 (on):** WB's equivalence sample, against `base1`:
     - the 40 anchors (they contain the 10 Gaia-touching anchors VB2 reuses; the build confirms this and lists them)
     - **the SIMBAD-heavy cases**, defined as every `simbad-lookup`, `dossier` and `exclusion-system --star` case in
       the 40 plus WB's active-wind anchors (EZ Aqr, GJ 65, EV Lac)
     - **every A0 2MASS-cone anchor** (including EZ Aqr, σ CrB C, ε Ind)
     - the three debris-disk cases

     **Scoring:** WB's own `score_cr30.service_hits(raw, obj, err)`, `degrade_reasons(obj, err, rc, names)` (with
     `names` from `cr30_app_names.json` or `{}`) and `error_text(raw, err, obj)`.
     - They are loaded read-only via `importlib.util.spec_from_file_location` with `sys.dont_write_bytecode = True`,
       so nothing is written into WB's tree.
     - The stderr handed to them has **`^\[(cds-mirror|gaia-login)\] ` lines stripped**, because WB's strip
       doesn't exist yet.
     - Values are compared with a JSON diff that ignores only the marker keys WB's helpers classify.
     - Pass: 0 value differences, and markers clear within 2 reruns.
   - **VA4 (budget):** the analytic worst case (§2.4) for `binary-orbit`, the census and two-component
     `exclusion-system` ≤ 720 s, **and** every VA3 run ≤ 720 s at 4-way parallel.
   - **VA5 (otype equivalence, MSG 378 condition 1):** the split against the single join, **both on
     `simbad.idia.ac.za`**, for the CR-29 anchors plus ≥ 1 no-ident id, ≥ 1 multi-oid id and G 272-61 (head /
     candidate).
     - Pass: identical `{(main_id, qid, otype)}` multisets and identical `_interpret_otype_rows` output.
     - If no real multi-oid id is found, that is reported, and the unit test stands in for it.
   - **VA6 (seams, condition 2):** each CR-26 / CR-24 seam completes on CfA within the A1 bound and gives a known
     answer.
     - **If one fails:** split it if an exact flat split exists, with unit tests like the otype split plus a VA6
       known answer. Otherwise report its family to WB as "not covered; waits for CDS". This doesn't block the
       build.
   - **VA7 (cut-off):** a deliberate non-position query on `II/246/out` in mirror mode through `vizier-query` →
     **a loud, scorer-visible error string** (`SERVICE` matches it), **never `count: 0`**.
     - Expected path: a read timeout at about 60 s (×2) → "CDS VizieR request timed out. Try again."
     - The `None` / `_VizierCutOff` path is covered by unit tests.
6. Commit Part A, with its docs (Greg commits and pushes).

### Part B
7. **B0:** ESA release 3.15 against astroquery 0.4.11 (`TapPlus.login`, `launch_job_async(name=)`,
   `remove_jobs`). Avoid the 2026-11-12 16:00 CET maintenance hour.
   **B1:**
   - login cost
   - the census async pull under login (completion; row count against anonymous)
   - **the concurrency check:** the 10 Gaia anchors × 4 parallel processes, anonymous then logged in, counting 429s;
     and whether ESA's "active" count includes sync jobs
8. Code, tests (§4, Part B) and **Part B's docs**:
   - the "Gaia login" block in `docs/integration.md` (the D1 rule, `gaia-jobs`, the `[gaia-login]` lines)
   - `docs/query-commands-index.md`
   - `docs/core-modules.md`
   - the `CLAUDE.md` count and `docs/testing.md`
9. **/code-review CP2** on the Part B working tree.
10. **Validation VB:**
    - **VB1:** suite green, **with the real credentials file present**.
    - **VB2 (MSG 376 item 2):** the 10 Gaia anchors, **mirror on, logged in**, against `base1` **and** against
      VA3's anonymous outputs (isolating the login delta). Each run ≤ 720 s.
    - **VB3:** a census run. Its named job is visible while running and `total="0"` after. Row count equals
      anonymous, or the difference is disclosed.
    - **VB4:** a wrong-password tmp credentials file → output equals anonymous; stdout valid JSON; the lines, latch
      and back-off work; no password anywhere.
    - **VB5:** the D1 rule is documented. `gaia-jobs` lists a left-over `space_app-*` test job and `--cleanup`
      removes it; a job without the prefix (if Greg makes one) survives.
11. Commit Part B, with its docs.

### Close
12. Docs check: each part's docs are in its own commit, and the counts are consistent.
13. **/code-review CP3** on the whole delta, including rehearsing §5's instant step (S6).
    - **CP3 fixes land as separate Part A-only and Part B-only commits.** Step 15 reads the Part A fix commits.
14. **Post-build message to WB** (only at Greg's go). It covers:
    - the commit SHAs and the flag path
    - **the measured limits** (A1)
    - **the cut-off threshold** (amendment 3): per-attempt elapsed time, 60 s, against the slowest real answer and
      the 68.8 s cut-off
    - **the VizieR call-shape list** (amendment 2) and the A0b coverage list
    - **the probe endpoints:**
      - `https://simbad.harvard.edu/simbad/sim-tap/sync`
      - `https://vizier.idia.ac.za/viz-bin/votable`
    - **the stderr lines and prefixes:**
      - **the rename of Part B's lines to `[gaia-login] `** (HEAD's `[gaia] sync TAP bounded …` lines stay real
        degrade lines)
      - the wording test against both regexes
      - the ask to strip **only** `^\[(cds-mirror|gaia-login)\] ` lines in `error_text`
      - a missing `[gaia-login]` line means no Gaia call
    - **the stdout error strings** for mirror failures (they match `SERVICE` by design)
    - **the concurrency result** (item i): 429 counts at 4 processes, anonymous vs logged in, and whether ESA's
      active count includes sync jobs
    - **VB2** (item 2)
    - **condition 1:** VA5
    - **condition 2:** per seam, "as written" or split, with known answers
    - **condition 3:** the anchors reaching each path — the otype split, each seam, `query_object`,
      `query_objectids`, the 2MASS cone
    - the IDIA SIMBAD snapshot (2026-04-22) and MSG 377's tally (restated), plus the VA3 tally on CfA
    - that the VizieR limit is not relied on for 2MASS, and v5's `vizier-query` note was replaced by the loud
      failure
    - that a 2MASS regex miss gives a non-clearing `unreachable`
    - the X-Match line
15. **After the build is done, every test has run and Greg has approved: write `CDS_RESTORE_PLAN.md`.**
    - It reverts **Part A only**. The ESA login, `gaia-jobs` and the credentials file stay.
    - **Its removal list is built from Part A's actual commit diff** (`git show --stat` plus the full diff of the
      Part A commit, and of every Part A fix commit including CP3's) **as the authoritative source**. §5 is only a
      cross-check, and any site in the diff that §5 doesn't list is called out in the restore plan.
    - It expands §5 with validation, success criteria and a /code-review checkpoint.
    - It drafts the WB message naming the restore commit (MSG 376 item iii).

### Success criteria

| # | Criterion | Pass when |
|---|---|---|
| S1 | Off changes nothing | VA1 green with the flag file present; VA2 byte-identical; the argparse-error stderr test passes; no test body edited |
| S2 | Mirror output = CDS output | VA3 (scored with WB's helpers): 0 value differences; markers clear within 2 reruns; EZ Aqr, σ CrB C, ε Ind exit 0 with their `base1` J / Ks |
| S3 | Bounded and loud | VA4 analytic and observed ≤ 720 s; VA7 loud (never `count: 0`); the mode line and GUI title shown; the X-Match line on census |
| S4 | Otype split exact | VA5 identical multisets and identical interpretation; the unit edge cases pass |
| S5 | Seams covered | VA6: each seam as written (or split) with a known answer, or reported to WB as not covered |
| S6 | Removal works | §5's instant step rehearsed at CP3 under VA2's `unshare -rn` conditions → no line, outputs equal VA2's |
| S7 | Login safe | VB4; sentinel tests; stdout always JSON; no credentials → identical to HEAD; HEAD's `[gaia]` lines unchanged |
| S8 | Login measured and helping | B1's paired 429 counts and the sync-in-active answer **measured and reported** (if logged-in draws more, WB is told to use `--workers 2`); VB2 equals `base1` except clearing markers; VB3 deletes exactly its own job; VB5 |
| S9 | Reviews clean | CP1–CP3 findings fixed or ruled by Greg |

---

## 7. Decisions — RULED by Greg 2026-11-11: D1, D2, D3 all as recommended

- **D1 — the active-job cap: a documented rule** (`--workers ≤ 4`, GUI closed); no semaphore.
- **D2 — orphaned async jobs:** the manual `query.py gaia-jobs [--cleanup]` (§3.4).
- **D3 — a pre-build WB message,** posted at Greg's go. Done: MSG 375; follow-ups 377 / 379.

## 8. Review record

- **Round 1 (v1 → v2):** two reviews, code and validation. Found:
  - the otype host
  - subprocess tests reading the real files
  - `GaiaClass.login` swallowing errors and printing to stdout
  - orphaned async jobs
  - the attempt count
  - and more (MEDs / LOWs)

  All folded in.
- **Round 2 (v5 → v6),** after WB's MSG 376 / 378 / 380. Two reviews, code (with light mirror probes) and
  consistency. The HIGHs:
  - the `IN`-list otype join 504s on CfA → three flat queries
  - `qid` is the stored matched id, and HEAD queries two ids → the exact multiset reshape
  - `**vizier_kwargs(timeout=…)` → `TypeError` → rebind instead
  - the always-on mode line breaks WB's `error_text` for non-JSON errors → emitted at the first network call, plus a
    strip ask
  - the build gate ignored the open MSG 379 question → resolved by MSG 380

  MEDs: the `None` cut-off signal (replaces the >10 M list); the exact 2MASS decode; cache-skip placement and the
  `simbad_cr24_velocity` service; VizieR's missing wall bound and breaker; the TIC limit; the budget arithmetic;
  VA5 / VA6 missing; §4 stale; backout not listing v5 sites; docs ordered after commits; stale text. LOWs:
  unspecified literals; flaky 429 criterion; S6 conditions. All folded in.
- **Round 3 (v6 → v7):** two reviews of v6's new mechanisms (code) and consistency.
  - **HIGHs (code):**
    - Wrapping `_run` in a watchdog leaves an abandoned thread retrying and resetting the process-wide socket
      timeout → a mirror producer with a fresh client per attempt under `_bounded_call` (CR-19's pattern).
    - `_with_retries` has no "fatal", and the ≥ 60 s backup timed across attempts would flag a genuine empty cone →
      per-attempt elapsed time, and `_VizierCutOff` in `fatal=`.
  - **MEDs:**
    - the 60 s read timeout means the cut-off arrives as a timeout, so `None` is a guard and VA7 expects the timeout
    - the stdout error strings must match `SERVICE` (specified)
    - TIC: a plain raise → HEAD's `unreachable`, with no "fatal" and `_family_call` untouched
    - the breaker trips on timeout only, with a `cache_get` fallback
    - the Windows marker dropped
    - `announce()` hooks and a lock
    - VA3 must strip the new lines before WB's `error_text`
    - **the `[gaia]` prefix collides with HEAD's CR-19 lines → `[gaia-login]`**
    - consistency: the wording test split by part; VizieR 60 s fixed against the A1 rule; wall time defined;
      cut-off exception text; the §5 list completed; S8 aligned with WB's ruling
  - **LOWs:**
    - the `i` alias; missing-oid drop; one `_simbad_tap_rows` seam
    - the `vizier_timeout()` placement and its env var
    - A1's missing shapes
    - VA2 / VA3 sample definitions
    - VA5 fallback; the seam-split contingency
    - mode-bit rule and 4-digit octal; the legacy-path login line
    - the CP3 fix-commit rule
    - stale status and step text
  - All folded in.
- **Round-2 measurements:**
  - CR-26 / CR-24 seams 0.20–0.26 s on CfA (no split)
  - the flat otype queries about 0.2 s each
  - astroquery `None` on IDIA's 0-byte body
  - every drafted literal matches neither WB regex

---

## 9. Pre-build message to WB — POSTED as MSG 375 (2026-11-11, at Greg's go)

The text below is MSG 375 as posted (the header keeps its `<next>` placeholder; the channel copy reads MSG 375).

```
## MSG <next> · FROM: APP · TO: WB · 🛰️ CDS outage — APP proposes a temporary mirror mode + a permanent ESA Gaia login; your rulings needed before APP builds

**Background — what happened to CDS.** On or before 2026-10-28, the Centre de Données astronomiques de Strasbourg
(CDS) had a cybersecurity incident in its Strasbourg server network. CDS took its systems offline as a precaution.
Its notice (https://cds.unistra.fr/, last updated 2026-11-09) calls access to SIMBAD, VizieR, Aladin and X-Match
"degraded", and lists as unavailable: the CDS portal, X-Match, VizieR uploads, SIMBAD updates, HATS products,
CDS catalogue HiPS and the VizieR publishing registry. It gives **no restoration date** and links no status page.

Your session 170 logged every CDS address (130.79.128.x) timing out from 14:02 on 2026-10-28. APP's probes on
2026-11-11 found the same: `simbad.cds.unistra.fr` and `vizier.cds.unistra.fr` return 404 pages, and X-Match times
out. That is about two weeks down. Your pre-fire ruling 44 ("the CfA mirror not used — wait for CDS") was made at
session 165 for a two-hour VizieR outage, before anyone knew this one would last this long.

**What CDS itself recommends.** The notice points users to mirrors:
- SIMBAD at CfA Harvard (`simbad.cfa.harvard.edu`, data to 2026-10-14) and IDIA South Africa (`simbad.idia.ac.za`)
- VizieR at IDIA, CfA, NAOJ and China-VO, with the warning that large catalogues such as Gaia DR3 (`I/355`) aren't
  on every mirror
- Gaia data straight from ESA's archive (`gea.esac.esa.int`)

It names no mirror for X-Match and suggests cross-matching locally with TOPCAT / Aladin.

**Why APP is proposing changes.** CR-29's pre-fire review (your session 171: σ CrB A's `exclusion-system` run, the
scorer on the real baselines, R0) needs SIMBAD and VizieR. While CDS is down the APP can't serve them, and the
CR-28 + CR-33 bundle and CR-34 sit behind CR-29. Greg asked APP to find out (read-only, nothing built) whether the
mirrors could stand in. What APP found, against your own CDS-era files:

1. **The mirror data is CDS's data.**
   - IDIA's `B/wds/wds`, `B/sb9/main` and `B/sb9/orbits` match your session-156 CDS pulls
     (`cr26-pipeline-cache/cr29-s156/pull/`) row for row: 157,990 / 4,079 / 5,099 rows. The only difference is one
     blank-vs-`--` SpType cell.
   - IDIA also serves II/246, I/311, I/355, IV/39/tic82 and B/cb.
   - CfA lacks I/355 and IV/39/tic82. NAOJ timed out.
2. **The outputs match, apart from timeouts.**
   - 40 CR-29 acceptance runs went through the mirrors (runtime patch only, sister `8452e8e`, nothing in the repo
     changed), compared byte for byte with `cr29-s151/base1`.
   - **28 were byte-identical. The other 12 differed only by degrade markers, never by a value:**
     - SIMBAD otype timeouts (the mirrors take ~110 s on the `ident ⋈ otypes` join; APP's limit is 30 s)
     - IDIA 2MASS-by-designation timeouts (~69 s against 60 s), which make **EZ Aqr, σ CrB C and ε Ind exit 1**
     - ESA FLAME blips
     - ESA HTTP 429s
   - A recheck reproduced every timeout. IDIA's otype answer for GJ 65 (`Er*`) is the baseline's.
3. **The mirrors are slower, not wrong.** They appear not to have CDS's capacity or indexes: simple lookups are
   fast, while the heavy joins and searches on non-indexed columns crawl.
4. **The ESA 429s are separate from the CDS outage, but also shared.** ESA's anonymous queue is **one pool of 50
   jobs shared by all anonymous users worldwide**, and it is likely busier with CDS down. A logged-in account gets
   its own queue of 50, a 120-minute async limit (against 1 minute), no 50,000-row cap, and 5 active jobs. Greg has
   registered an ESA account on this box.

**What APP proposes** (plan: `CDS_OUTAGE_FALLBACK_PLAN.md` in the APP repo, revised after two independent reviews;
Greg has approved its design decisions; **nothing built yet**):

- **Part A — TEMPORARY mirror mode**, off by default.
  - Turned on by a flag file, `~/.config/space_app/cds_mirror`, so it reaches your runner even though the runner
    strips `SPACE_APP_*`.
  - Routes astroquery SIMBAD → `simbad.harvard.edu`, raw SIMBAD TAP → `simbad.idia.ac.za`, VizieR →
    `vizier.idia.ac.za`.
  - Raises the time limits to what the mirrors need, measured, and keeps every run's worst case **≤ 720 s, inside
    your 900 s `TIMEOUT_S`**.
  - With the flag absent, output is byte-identical to HEAD.
  - Mirror runs write a stderr line `[cds-mirror] … temporary, on since <date>` and add **no new stdout keys**.
  - It is removed in full when CDS returns, under a separate restore plan.
- **Part B — PERMANENT ESA Gaia login** from a credentials file on this box.
  - Anonymous when the file is absent.
  - A login failure falls back to anonymous and never errors.
  - The app deletes each async job it creates right after reading it, and only its own.
  - A manual `query.py gaia-jobs [--cleanup]` clears leftover `space_app-*` jobs.
  - **Rule: Gaia-heavy runs at `--workers ≤ 4` with the GUI closed** (ESA's 5-active-job limit).

**What APP needs from WB before building** — your rulings:

1. **Mirror mode for CR-29 at all?** Pre-fire ruling 44 is yours to revisit. APP only makes mirror mode available;
   whether CR-29's records accept mirror-served runs is WB's call.
2. **Login on by default for your runs.** Part B makes this box's runs logged in. Your baselines are anonymous.
   APP will check logged-in output against `base1` (10 Gaia-touching anchors). With no 50,000-row cap,
   `close-binary-census`'s NSS pull could return more rows; APP will report any difference. Do you accept logged-in
   runs, or want them gated?
3. **Your tooling under mirror mode:**
   - (a) `service_probe.py` probes `simbad.cds.unistra.fr` / `vizier.cds.unistra.fr` by name, so `watch` would TERM
     every mirror-mode re-gate. Point it at the mirror hosts, or skip it, in mirror mode?
   - (b) record flag-file and login state in `_meta.json`?
   - (c) a fresh outdir per mode, so resume can't mix CDS and mirror runs?
4. **X-Match has no mirror.** In mirror mode, `close-binary-census` silently loses the SB9 rows whose parallax comes
   from X-Match. APP will print a stderr line saying the census output is not valid. CR-33.1's acceptance stays
   blocked until CDS returns.
5. **Catalog coverage.** APP will confirm every catalog the app queries on IDIA (including `debris_disk`'s
   J/ApJS/211/25, J/ApJS/225/15 and II/328/allwise). A catalog a mirror lacks answers *empty*, not with an error,
   so APP will list any that aren't covered.
6. **Stderr wording.** The new `[cds-mirror]` / `[gaia]` lines avoid "timed out", "timeout", "unreachable",
   "connection error" and "degrading", so `score_cr30.py`'s SERVICE / degrade regexes don't fire on them. Shout if
   your scorers match anything else.

APP will not build until you answer. Questions on any of the evidence: the 40 mirror runs and the diff tallies are
reproducible from APP's side.

**AWAITING:** WB — rulings 1–6.
```

---

## 10. WB's answers — MSG 376 (2026-11-11, Greg ruled items 1–2; WB's answers 3–6 approved by Greg)

1. **Mirror mode for CR-29: ACCEPTED behind WB's own equivalence check.** Ruling 44 is reopened and superseded.
   - After the build, WB runs the 40 anchors, the SIMBAD-heavy cases and the 10 Gaia-touching anchors in mirror mode
     against `cr29-s151/base1`.
   - The pass condition is zero value differences, with degrade markers clearing within 2 reruns.
   - Only then do mirror-served runs enter WB's records, starting with σ CrB A's run.
   - A family showing a value difference waits for CDS.
   - WB keeps `research/star-analysis-cr-queue/cds-restore-retest-list.md` for re-testing on CDS.
   - WB re-pulled WDS/SB9 from IDIA with its own script and got **byte-identical** md5s to its CDS pull.
2. **Login on by default: ACCEPTED, ungated.** Per-run login state comes from the stderr line (§3.2). Run VB2 and
   report it.
3. **Tooling:**
   - (a) WB changes its own probe to read the flag file. APP provides the exact endpoints.
   - (b) WB's runner records flag and credentials presence in `_meta.json`. APP provides fixed-prefix stderr lines,
     including the login state.
   - (c) WB uses a fresh output folder per mode, and its runner refuses to mix them.
4. **X-Match: ACCEPTED.** WB holds the two census cases (`path-close-binary-census`, `acc-7.3i`) until CDS returns.
5. **Coverage: ACCEPTED**, with the CR-29 case files' catalogs added (A0b). If a debris-disk catalog is missing,
   WB holds those three cases.
6. **Wording: CORRECTED.** No line may match either of WB's verbatim patterns, and there are no class names (§2.1).
- **Items for the build:**
  - (i) concurrency at 4 processes, logged-in vs anonymous (B1)
  - (ii) IDIA's SIMBAD snapshot date, and the per-host SIMBAD tally (post-build message)
  - (iii) the restore plan carries a WB message naming the restore commit (step 15)

## 11. WB's answers — MSG 378 (2026-11-11, Greg ruled option A as WB pre-fire ruling 61)

- **Option A:** all SIMBAD goes to `simbad.harvard.edu`; the two-step otype lookup runs in mirror mode only (§2.2).
  B (IDIA's April data) and C (hold the otype families) were not taken.
- **Condition 1:** the two-step matches the join on the no-`ident` and multi-`oidref` edge cases, in unit tests and
  in a live check against the join on IDIA.
- **Condition 2:** report per CR-26 / CR-24 seam whether it was split.
- **Condition 3:** list the anchors per path. WB adds active-wind anchors (EZ Aqr, GJ 65, EV Lac and similar) to its
  check.
- **Debris-disk cases released** (still in WB's sample). Only the two census cases stay held.

## 12. WB's answers — MSG 380 (2026-11-11; Greg ruled accept-with-amendments, WB pre-fire ruling 62)

- **The mirror-only 2MASS cone lookup: ACCEPTED** (§2.3b). Flag off = HEAD's designation query.
- **Amendment 1:** decode tests pin **truncation**, including a negative declination near a digit boundary and the
  `J` prefix with and without it.
- **Amendment 2:** every VizieR call (`core/`, `query.py`, `gui/`) listed by search shape in the CP1 notes. Only the
  2MASS seam and `vizier-query` may be large-catalog non-position.
- **Amendment 3:** in mirror mode, 0 rows after ≥ 60 s wall time = unreachable (a loud degrade). The threshold is
  measured and reported.
- **WB's equivalence sample adds** every anchor APP lists as reaching the 2MASS cone.
