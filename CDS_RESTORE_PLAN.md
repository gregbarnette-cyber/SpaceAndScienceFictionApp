# CDS restore plan — remove the TEMPORARY CDS mirror mode (Part A) when CDS Strasbourg returns

**Status:** READY (D-R1 / D-R2 ruled 2026-11-11), written 2026-11-11 after Greg approved the CDS-outage build and it was pushed (`8452e8e..5967f2b`).
It runs **when CDS is back**, not before. Every step marked **(Greg)** needs his go.

**Scope.** This plan removes **Part A only**, the mirror mode of `CDS_OUTAGE_FALLBACK_PLAN.md`. **Part B stays:**
the ESA Gaia login (`core/gaia_auth.py`), `query.py gaia-jobs`, the credentials file and their tests and docs. Nothing
in this plan touches them, apart from removing mirror-mode words from three Part B doc sentences (§3.3).

**Sources.**
- The removal list (§2) is built from **Part A's actual commit diff**, which is the authoritative source.
- `CDS_OUTAGE_FALLBACK_PLAN.md` §5 is only a cross-check. §2.3 lists every place where the two disagree.
- WB's asks: MSG 376 item iii (a restore message naming the restore commit) and MSG 384 (re-run all 57 row-order
  cases on CDS).

---

## 1. When to run it (the trigger)

All of these must hold:
1. **CDS is healthy.** WB's `service_probe.py check simbad` and `check vizier` pass against CDS
   (`simbad.cds.unistra.fr`, `vizier.cds.unistra.fr`), and X-Match answers.
2. **CDS has lifted its incident notice.**
3. **Greg gives the go.** He also decides with WB whether WB must finish any mirror-served work first.

## 2. What Part A is: the removal list

### 2.1 The Part A commits

| Commit | What | Files |
|---|---|---|
| `f0b1652` | Part A: mirror mode | 17 files (below) |
| `74a014c` | Part A notes (Part B validation, CP2 record) | `CDS_OUTAGE_BUILD_NOTES.md` |
| `99c0db9` | CP3 fix: drop an unused fixture parameter; notes | `tests/conftest.py`, `CDS_OUTAGE_BUILD_NOTES.md` |
| `80c840f` | Notes: the 33-case check + the message draft | `CDS_OUTAGE_BUILD_NOTES.md` |
| `2ddb450` | Mirror-mode doc updates for WB | `CLAUDE.md`, `SETUP.md`, `docs/integration.md`, `docs/star-databases.md`, `docs/gui-architecture.md` |

**Any later Part A fix commit is added to this table before the restore runs.** Re-check with
`git log --oneline 5967f2b..HEAD` for commits whose subject starts `CDS outage Part A`.

### 2.2 Every site, from the diff

**Code (`f0b1652`):**

| File | Site | What it does in mirror mode |
|---|---|---|
| `core/cds_mirror.py` | the whole module (new) | the flag, the latch, `announce()` and its lock, `apply_simbad()`, `vizier_server_kwargs()`, `vizier_timeout()`, `skip_cache_write()`, `decode_2mass_key()`, `window_title_suffix()`, `xmatch_unavailable_note()`, the host constants |
| `core/shared.py` | `_make_simbad`: `cds_mirror.apply_simbad()` | astroquery SIMBAD → CfA |
| `core/databases.py` | `_simbad_otypes_tap`: `apply_simbad()` | raw-TAP seam → CfA |
| `core/databases.py` | `_simbad_cr26_tap`: `apply_simbad()` | raw-TAP seam → CfA |
| `core/databases.py` | `_otypes_where` (extracted from `_otypes_query`) | builds the shared WHERE clause; behaviour-neutral |
| `core/databases.py` | `_simbad_tap_rows`, `_simbad_otypes_split` | the three-query otype split |
| `core/databases.py` | `_otypes_fetcher`, and its call in `fetch_star_otypes` | picks the split or the join |
| `core/databases.py` | `compute_star_systems_csv`: the option-50 refusal | refuses option 50 |
| `core/catalog.py` | `_VIZIER_MIRROR_COOLDOWN_S`, `_VIZIER_MIRROR_BACKOFF`, `_vizier_mirror_down`, `_VizierCutOff`, `_vizier_mirror_breaker_open`, `_vizier_mirror_result` (its nested `_attempt`, the `None` / ≥ 60 s-empty cut-off, the `_WatchdogTimeout` → `Timeout` mapping) | the VizieR mirror producer |
| `core/catalog.py` | `vizier_query`: `enabled()` / `vizier_timeout()` and the mirror branch in `_run`; the `_shape_vizier` split-out | routes VizieR; the split-out is behaviour-neutral |
| `core/catalog.py` | `xmatch_query`: the mirror fail-fast | X-Match errors at once |
| `core/catalog_cache.py` | `cached`: the `skip_cache_write` guard | mirror answers are never cached |
| `core/binary.py` | `_census_sb9`: `xmatch_unavailable_note()` | the census X-Match line |
| `core/twomass.py` | `_ii246_seam`'s mirror branch, `_MIRROR_CONE_ARCSEC`, `_ii246_mirror_cone` | 2MASS by decoded cone |
| `core/xray_catalog.py` | `_tic_query`: `vizier_server_kwargs()` and the `None` → raise | TIC → IDIA; cut-off is loud |
| `gui/app.py` | the window-title suffix | " — CDS MIRROR MODE" |

**Tests (`f0b1652`, `99c0db9`):**
- `tests/test_cds_mirror.py`: the whole file (**55 tests**).
- `tests/conftest.py`: the `_cds_mirror_off` autouse fixture.
- `tests/_queryharness.py`: the `env["SPACE_APP_CDS_MIRROR"] = "0"` line.

**Docs (`f0b1652`, `2ddb450`):**
- `docs/integration.md`:
  - the `## TEMPORARY — CDS mirror mode` section;
  - the `[cds-mirror]` sub-bullet of "New stderr lines";
  - the "While CDS is down" bullet in the catalog-tier ¶ paragraph;
  - the CR-25 TEMPORARY note;
  - the "2026-11 additions" mirror bullet.
- `docs/core-modules.md`: the `TEMPORARY — core/cds_mirror.py` section.
- `docs/testing.md`: the `test_cds_mirror.py` entry. The suite-count history entries stay (D-R1).
- `SETUP.md`: the "TEMPORARY — CDS mirror mode" section.
- `CLAUDE.md`: the TEMPORARY guardrail, the `cds_mirror` module-map entry, the `CDS_OUTAGE_FALLBACK_PLAN.md`
  plan-file listing, and the test count.
- `docs/star-databases.md`: the option-50 note.
- `docs/gui-architecture.md`: the title note.

**Files that leave the repo root:**
- `CDS_OUTAGE_BUILD_NOTES.md` (in `f0b1652` and the three notes commits): **deleted**.
- `CDS_OUTAGE_RESUME_PROMPT.md` (untracked): **deleted**.
- `CDS_OUTAGE_FALLBACK_PLAN.md` (`0567ae0`, a plan commit, not Part A code): **moved** to `completed_plans/`.
- This file: **moved** to `completed_plans/` once the restore is verified.

### 2.3 The diff against plan §5 (the cross-check)

**In the diff but missing from §5 (each is in §2.2):**
1. **The option-50 refusal** in `databases.compute_star_systems_csv`. §5 doesn't list it at all.
2. **`xmatch_query`'s mirror fail-fast** in `catalog.py`. §5's "the X-Match line" covers only the `binary.py` emitter.
3. **`databases._otypes_where`.** §5 expected "`_otypes_query`'s added `ids` return", but the build extracted a
   shared WHERE helper instead. The revert restores the inline WHERE.
4. **`databases._otypes_fetcher`**, which is how "the branch in `fetch_star_otypes`" was built.
5. **`catalog._shape_vizier`**, a behaviour-neutral split-out of `vizier_query._run`'s shaping code.
6. **The VizieR producer's actual names.** §5 says `_mirror_attempt`; the build has `_vizier_mirror_result` with a
   nested `_attempt`, plus `_vizier_mirror_breaker_open`, `_vizier_mirror_down` and the two constants.
7. **`twomass._ii246_mirror_cone` and `_MIRROR_CONE_ARCSEC`.** §5 says "the cone branch and its decoder".
8. **The CP3 fixture change** (`99c0db9`).
9. **`2ddb450`'s docs:** the `SETUP.md` section, the star-databases and gui-architecture notes, the CR-25 note, the
   stderr bullet, the "2026-11 additions" bullet and the CLAUDE.md guardrail. §5's doc list names only the
   integration block, core-modules, the testing history and the CLAUDE count.
10. **`CDS_OUTAGE_BUILD_NOTES.md`.**

**In §5 but not in the diff (nothing to remove):**
- **The `timeout_default()` hooks** (`databases.py:528/530/566`, `xray_catalog.py:35-36/75-77`,
  `calculators.py:236`, `databases.py:303`). **These were never built.** A1 kept the built-in SIMBAD and xray limits
  (build notes, "Limits").
- **The VizieR breaker's "`cache_get` fallback".** There is no separate code for it: HEAD's `catalog_cache.cached`
  already checks the cache before the producer runs.

### 2.4 What the revert does not need

- **No cache purge.** Mirror answers were never written to `data/catalog_cache/` (`skip_cache_write`), so every
  cache entry is a CDS answer.
- **No DB repair.** Option 50 was refused in mirror mode, so `star_systems` holds no mirror rows.
- **No config file to clear.** `apply_simbad()` set astroquery's SIMBAD server in-process only, and wrote nothing to
  astroquery's config.

## 3. Steps

### R0. Refresh before running (this plan was written at `5967f2b`)

Other CRs (CR-28 + CR-33, CR-29, …) may land before CDS returns. Four parts of this plan are tied to the tree at
`5967f2b`; R0 brings them up to date. **Do all of it, even if nothing seems to have changed.**
1. **Hook search: mirror code outside the Part A commits.** Mirror mode is "don't extend", but a CR built during the
   outage may still have added a hook (for example a new SIMBAD or VizieR call with `apply_simbad()`,
   `vizier_server_kwargs()` or an `enabled()` branch), or a test that leans on `_cds_mirror_off` / `make_env`'s
   mirror line. A revert of the five commits would not remove those.

   ```bash
   git log --oneline 5967f2b..HEAD
   git log -p 5967f2b..HEAD | grep -nE '^\+.*(cds_mirror|cds-mirror|CDS_MIRROR|harvard\.edu|idia\.ac\.za)'
   ```

   - **Every hit goes into §2.2**, marked "added by `<sha>` (`<CR>`)".
   - Its removal is a hand edit in R3, not a revert, because its commit also carries the CR's own work.
   - Commits whose subject starts `CDS outage Part A` are fix commits: add them to §2.1 and revert them in R2.
2. **Re-rehearse the revert at `PRE`.** Use a throwaway worktree (`git worktree add --detach <scratch> HEAD`) and run
   R2's five reverts plus any §2.1 additions. Then:
   - rebuild R2's "revert cleanly" note and conflict table from what actually happens;
   - for each new conflict in a file a CR changed, write down which lines are the CR's (kept) and which are Part A's
     (dropped);
   - remove the worktree.
3. **Re-derive the test target.**
   - Record the default-suite count at `PRE` (from CLAUDE.md, confirmed by the last full run).
   - Record `test_cds_mirror.py`'s count: `venv/bin/python -m pytest --collect-only -q tests/test_cds_mirror.py`,
     55 at `5967f2b`.
   - **V2's target is `PRE` minus that**, plus or minus any tests from R0.1's hook removals.
4. **Note which landed CRs change V5/V6 outputs on purpose.**
   - The main one is CR-28 + CR-33: WB named the fixed SIMBAD row order as that bundle's design item, so all 57
     row-order cases would move by design.
   - Any such CR makes the comparison against `base1` a report for WB (V5b), not a gate. V5a's comparison of `PRE`
     against the restore commit is the gate either way.

### R1. Instant switch-off (Greg)
- `rm ~/.config/space_app/cds_mirror`. The flag file is Greg's and WB's: APP doesn't remove it.
- Unset `SPACE_APP_CDS_MIRROR`, `SPACE_APP_VIZIER_TIMEOUT` and any manual `SPACE_APP_*_TIMEOUT` in any shell or
  runner.
- **Restart any open GUI.** The switch is latched per process.

From here on every process takes HEAD's CDS path. Flag off has been shown byte-identical to the pre-Part-A code
(S1, S6).

### R1b. Baseline on CDS at the pre-restore commit (before R2)

Once the flag is off and CDS is up, record the **pre-restore commit** (`PRE` = `HEAD` before R2). On `PRE` with the
flag off, run V5a's runs (the 54 row-order runs and the V6 anchors) on CDS and keep the outputs as `pre/`, using `SPACE_APP_CATALOG_CACHE=0`
and `--workers ≤ 4`. These are V5a's reference outputs. Flag off is HEAD's CDS path, so this records what the code
gives on CDS *with* every CR that landed during the outage, before the restore touches anything.

### R2. Revert Part A (one restore commit)

**Rehearsed 2026-11-11 in a throwaway worktree at `5967f2b`.** If any commit landed after `5967f2b`, the R0.2
rehearsal at `PRE` replaces this section's notes and table.
1. Revert in reverse order:

   ```bash
   git revert --no-commit 2ddb450
   git revert --no-commit 80c840f
   git revert --no-commit 99c0db9
   git revert --no-commit 74a014c
   git revert --no-commit f0b1652
   ```

   A single `git revert --no-commit` with all five stops at the first conflict, so run them one at a time and resolve
   as you go.
2. **All of `core/`, `gui/app.py`, `tests/test_cds_mirror.py` and `CDS_OUTAGE_BUILD_NOTES.md` revert cleanly**,
   including `core/catalog.py`, which Part B also changed.
3. **Expected conflicts.** They are all Part B text sitting next to Part A text. Resolve each by **keeping Part B's
   lines and dropping Part A's**:

   | File | Keep (Part B) | Drop (Part A) |
   |---|---|---|
   | `tests/_queryharness.py` | `env["SPACE_APP_GAIA_CREDENTIALS"] = ""` | `env["SPACE_APP_CDS_MIRROR"] = "0"` |
   | `tests/conftest.py` | the `_gaia_login_off` fixture | the `_cds_mirror_off` fixture |
   | `docs/core-modules.md` | the `core/gaia_auth.py` section | the `TEMPORARY — core/cds_mirror.py` section |
   | `docs/testing.md` | the `test_gaia_login.py` and `test_gaia_jobs.py` entries | the `test_cds_mirror.py` entry |
   | `CLAUDE.md` | the `gaia_auth` map entry, the Gaia-login guardrail | the `cds_mirror` map entry, the TEMPORARY guardrail, the plan-file listing |
   | `SETUP.md` | the "Optional — ESA Gaia archive login" section | the TEMPORARY section |
   | `docs/integration.md` | the `[gaia-login]` sub-bullet, the Gaia ¶ bullet, the Gaia "2026-11 additions" bullet | the mirror equivalents |

### R3. Hand edits the revert can't make

These are Part B text, or text written after Part A, that still mentions mirror mode:
1. **`docs/integration.md`, "New stderr lines":**
   - Strip rule: `^\[(cds-mirror|gaia-login)\] ` → `^\[gaia-login\] `.
   - "All of them are tested to match neither of WB's scorer patterns" stays true (the `[gaia-login]` tests are Part
     B's).
2. **`docs/integration.md`, the CR-19 `--gaia-timeout` note and the "Gaia login" block:** re-read both for any
   mirror wording. The rehearsal grep found none.
3. **`CLAUDE.md`, the test count:**
   - The new count is **R0.3's target**: 4221 passed, 126 skipped, 703 subtests if nothing landed after `5967f2b`
     (4276 minus `test_cds_mirror.py`'s 55). Confirm it from the actual run at R4.
   - Rewrite the provenance clause so it names only Part B (+41) and the restore.
4. **`docs/testing.md` suite-count history (D-R1):** keep Part A's entries; append one restore entry (`PRE`'s count
   → R0.3's target; 4276 → 4221 if nothing landed).
5. **R0.1's hook removals:** remove each mirror hook a CR commit added, keeping the CR's own code.
6. **Plan files:**
   - `git mv CDS_OUTAGE_FALLBACK_PLAN.md completed_plans/`.
   - `git rm CDS_OUTAGE_BUILD_NOTES.md`, if the revert hasn't already removed it.
   - Delete `CDS_OUTAGE_RESUME_PROMPT.md`.
   - Add the plan to `completed_plans/README.md`.
   - Update CLAUDE.md's completed-plan count (78 → 80, counting this plan once it moves).
   - Drop the root-plan listing.
   - Fix any reference to `CDS_RESTORE_PLAN.md` / `CDS_OUTAGE_FALLBACK_PLAN.md` paths that moved, for example
     Part B's guardrail.
7. **Memory:** close `cds-outage-fallback-plan.md` (APP's memory, not the repo).

### R4. Validate (each check is in §4)
1. Run V1 (the grep).
2. Run V2 (the full suite). **One heavy job at a time:** run the suite alone, with WB's runner idle.
3. Run V3–V7 at light load: `--workers ≤ 4`, GUI closed. Run V5a's restore-side runs soon after R1b's `pre/` runs,
   so CDS's own data has little time to drift between the two.

### R5. `/code-review` checkpoint CR-R1
- Review the restore working tree before committing. `/code-review` reviews the working tree here, as at CR-23.
- Focus areas:
  - nothing Part B lost in the conflict resolution;
  - no leftover mirror branch, import or `cds_mirror` reference;
  - the `_otypes_where` / `_shape_vizier` inlines restored to the code as it would be without Part A (`8452e8e`'s,
    plus any later CR changes);
  - R0.1's hook removals, if any, leaving each CR's own behaviour intact;
  - doc counts consistent.
- **Fix findings in the same restore commit**, or rule them with Greg.

### R6. Commit and push (Greg)
- One commit, `CDS restore: remove the TEMPORARY CDS mirror mode (Part A)`. It contains the revert, the conflict
  resolutions, the R3 edits and any CR-R1 fixes.
- Its message lists the five reverted Part A SHAs, says Part B is kept, and gives the suite count.
- Greg pushes, or has APP push at his explicit go.
- Then this plan moves to `completed_plans/` in a small follow-up commit.

### R7. Tell WB (Greg's go): the §6 message names the restore commit.

## 4. Validation

| # | Check | Pass when |
|---|---|---|
| V1 | **Grep.** Search `core/`, `query.py`, `gui/`, `tests/` and the docs (excluding `completed_plans/`) for: `cds_mirror`, `cds-mirror`, `CDS_MIRROR`, `harvard.edu`, `idia.ac.za`, `_simbad_otypes_split`, `_simbad_tap_rows`, `_otypes_fetcher`, `_otypes_where`, `decode_2mass_key`, `_VizierCutOff`, `_vizier_mirror`, `_ii246_mirror_cone`, `_MIRROR_CONE_ARCSEC`, `SPACE_APP_VIZIER_TIMEOUT`, `MIRROR MODE`, `mirror mode` | **No hits**, apart from the two pre-existing ADS links (`adsabs.harvard.edu` in `data/cr30/…` and `tests/test_exoplanet_batch.py`) |
| V2 | **Suite.** `venv/bin/python -m pytest -q -p no:cacheprovider` | **R0.3's target, with 0 failures**: 4221 passed / 126 skipped / 703 subtests if nothing landed after `5967f2b` (4276 − 55). The `QThread … dumped core` at interpreter exit is pre-existing |
| V3 | **The restore commit removes Part A and nothing else.** Run `git diff PRE <restore>`, and for each Part A file compare it with the reverse of the Part A commits' diff for that file (`git diff 5967f2b <restore of only the five commits>` from R0.2's worktree) | It touches **only** the §2.2 sites (including R0.1's additions), the R0.2 conflict resolutions and the R3 edits. Every Part A hunk is reversed. No CR line and no Part B line is changed. **If nothing landed after `5967f2b`**, it also holds that `git diff 8452e8e -- core/ gui/ tests/ query.py` is Part B's code and tests only (`core/gaia_auth.py`, its `core/catalog.py` hunks, `query.py` `gaia-jobs`, `tests/test_gaia_*`, the two Part B harness lines), and `databases.py`, `shared.py`, `twomass.py`, `xray_catalog.py`, `catalog_cache.py`, `binary.py` and `gui/app.py` are identical to `8452e8e` |
| V4 | **A stale flag does nothing.** Run `touch` on a temp flag path plus `SPACE_APP_CDS_MIRROR=1`, then run one SIMBAD case and one VizieR case | No `[cds-mirror]` line; output equals the same run without them; option 50 is no longer refused (checked by the error string; option 50 itself is not run) |
| V5a | **GATE — the restore changes no CDS output.** The runs are WB's 57 row-order cases: the `FAIL` lines of `cr26-pipeline-cache/cr29-s171/mirror1_raw.txt` (57), mapped through `mirror1/_runs.json`'s `cases` to **54 runs** (re-derive both counts and stop if either differs), **plus the V6 anchors**. Replay each run's `argv` / `env` with `SPACE_APP_CATALOG_CACHE=0` on the restore commit, `--workers ≤ 4`, and compare with R1b's `pre/` | **Byte-identical stdout and the same exit code** for every run. This holds whatever CRs landed, because flag off on `PRE` is the same CDS path as the restore commit. A difference is re-run once on both commits, since CDS can change between runs. A difference that persists **blocks**: the restore changed behaviour |
| V5b | **REPORT for WB — the 57 cases against `base1` (MSG 384, ruling 66).** Compare V5a's restore-side outputs with `cr29-s151/base1/<run>.out` | For each case, report whether it **matches `base1`**, or **passes R10** (every moved `teff` / `fe_h` value is one of the star's current CDS `mesFe_h` rows, or their median, on a fresh direct TAP read of `simbad.cds.unistra.fr`, and every derived value recomputes from that move alone), or neither. Run and report **the three held cases** (`bench-B13-57` HD 16765, `bench-M15-182` σ CrB C, `bench-M15-76` G 70-50) too. **Not a gate:** WB scores them, and a CR from R0.4 (CR-28 + CR-33's fixed row order) moves these values by design |
| V6 | **The mirror-only paths' anchors** (§5's six CDS anchors; WB's list rows 6–7). They include **GJ 65** and **EZ Aqr**, which reached the otype split (wind class / active wind); **ε Ind**, **EZ Aqr** and **σ CrB C**, which reached the 2MASS cone (same J / Ks, `twomass_status` resolved); and one VizieR cone case (WDS or SB9) | **Gate:** identical to `pre/`, as part of V5a. **Also:** byte-identical to `base1` unless an R0.4 CR changes them by design; a difference from `base1` with no such CR is reported to WB and looked into |
| V7 | **Part B is intact** | `test_gaia_login.py` and `test_gaia_jobs.py` pass (in V2); one logged-in Gaia case prints `[gaia-login] logged in`; `query.py gaia-jobs` lists 0 leftover `space_app-*` jobs, or cleans them |

**Success criteria.** V1, V2, V3, V4, V5a, V6's gate and V7 pass, and CR-R1's findings are fixed or ruled. V5b and V6's
`base1` comparison are reported to WB, not gated.
- **If a V5b case passes neither test** (and no R0.4 CR explains it), it is CDS's own drift, not the restore: report it
  to WB. If it also changed under the mirror, it is a CR-28 + CR-33 row-order item.
- **If V5a or V6's gate shows a difference that persists**, that blocks: the restore has changed behaviour, or Part A
  left something behind.

Scripts for V5a, V5b and V6 go in the session scratchpad. They reuse the plan's light-load rule.

## 5. Decisions — RULED by Greg 2026-11-11 (both as recommended)

- **D-R1 — the suite-count history: KEEP.** `docs/testing.md` keeps Part A's entries (4228 and 4235, plus CP fixes)
  as history, and the restore adds one entry (4276 → 4221, −55 `test_cds_mirror.py`). The history is a record of how
  the count moved, and Part B's entries (4276) only add up with Part A's in place. (This overrides the fallback
  plan's §5, which said to delete them.)
- **D-R2 — the build notes: DELETE.** `CDS_OUTAGE_BUILD_NOTES.md` (the A1 timings, the VA/VB records and the
  33-case check) is deleted, as the outage plan says. Its key content is in WB's channel (MSG 381–384) and git
  history.

## 6. Draft message to WB (post only at Greg's go, after R6)

```
## MSG <next> · FROM: APP · TO: WB · 🔁 CDS restore — mirror mode removed in `<restore SHA>`; switch your probe back to CDS and work your retest list

CDS is back, and APP has removed the TEMPORARY mirror mode (Part A of `CDS_OUTAGE_FALLBACK_PLAN.md`) in **`<restore SHA>`**
(pushed). This is the restore commit MSG 376 item iii asked APP to name.

**What changed:**
- The commit reverts Part A's five commits (`f0b1652`, `74a014c`, `99c0db9`, `80c840f`, `2ddb450`). All SIMBAD,
  VizieR and X-Match calls are back on CDS, and the app's code outside Part B is identical to `8452e8e`.
- **No `[cds-mirror]` line any more.** The flag file `~/.config/space_app/cds_mirror` and `SPACE_APP_CDS_MIRROR` are
  ignored. The flag file has been removed (R1).
- **Part B stays.** The ESA Gaia login, its `[gaia-login]` stderr line and `query.py gaia-jobs` are unchanged.
  - Your strip rule narrows to `^\[gaia-login\] `.
- Option 50 is enabled again. X-Match works again, so the census is valid again.
- Suite: <count>.

**APP's restore verify (your MSG 384 ask, ruling 66):**
- **The restore changes no CDS output:** the 54 row-order runs and the anchors give byte-identical stdout and exit
  codes on CDS at the pre-restore commit `<PRE>` (flag off) and at `<restore SHA>`.
- The 57 row-order cases against `base1`: <n> match `base1`, <n> pass R10 on a fresh CDS read, <n> neither (listed,
  with values). <Name any CR landed since `5967f2b` that moves them by design, e.g. CR-28 + CR-33's row order.>
- The three held cases (HD 16765, σ CrB C, G 70-50): <results, for your scoring>.
- The mirror-only paths' anchors (otype split: GJ 65, EZ Aqr; 2MASS cone: ε Ind, EZ Aqr, σ CrB C; a VizieR cone):
  identical before and after the restore; against `base1`: <result>.

**Over to you:**
- Switch `service_probe.py` back to CDS.
- Work `cds-restore-retest-list.md`: rows 1–3 and 9 (σ CrB A's `exclusion-system` on CDS into `base1`; the two
  census runs), rows 6–8 (your own re-test of the mirror paths and the 57 cases) and the three held cases.

**AWAITING:** WB — your retest results, and whether anything mirror-served needs re-running in your records.
```
