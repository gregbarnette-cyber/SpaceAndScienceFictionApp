# CDS outage work — resume prompt (written 2026-11-11, end of session 1)

Read this whole file first, then `CDS_OUTAGE_FALLBACK_PLAN.md` (v7, the plan) and `CDS_OUTAGE_BUILD_NOTES.md` (the
build record), as needed. **TEMPORARY file:** it goes with mirror mode (`CDS_RESTORE_PLAN.md` removes it).

## What this is

CDS Strasbourg (SIMBAD / VizieR / X-Match) has been down since about 2026-10-28 after a cybersecurity incident. That
blocks WB's CR-29 pre-fire review. APP built two parts:
- **Part A (TEMPORARY):** mirror mode.
  - Flag file `~/.config/space_app/cds_mirror`, or `SPACE_APP_CDS_MIRROR=1`.
  - All SIMBAD → `simbad.harvard.edu` (otype lookup as 3 flat queries); VizieR → `vizier.idia.ac.za` (2MASS by
    decoded-position cone; IDIA's ~69 s empty-200 cut-off is a loud failure).
  - X-Match skipped; option 50 refused; mirror answers never cached.
- **Part B (PERMANENT):** ESA Gaia login from `~/.config/space_app/gaia_credentials` (Greg's account).
  - One login per process, outside every CR-19 bound; the session cookie is reused for 30 min.
  - Named `space_app-<uuid>` async jobs are deleted after reading.
  - `query.py gaia-jobs [--cleanup]`.

## State at the end of session 1

- **The build is complete.** CP1–CP3 `/code-review` are done; VA1–VA7 and VB1–VB5 all pass; S6 (the removal
  rehearsal) passes. Suite: **4276 passed / 126 skipped / 703 subtests / 0 failures**.
- **7 local commits on `main`, NOT pushed** (on top of `8452e8e`):

  | Commit | What |
  |---|---|
  | `f0b1652` | Part A |
  | `0567ae0` | the plan doc |
  | `99309c6` | Part B |
  | `74a014c` | Part A notes |
  | `99c0db9` | Part A CP3 fix + notes |
  | `c62ab15` | Part B CP3 fixes |
  | `80c840f` | Part A notes: the 33-case check + message draft |

  **Part A = `f0b1652`, `74a014c`, `99c0db9`, `80c840f`. Part B = `99309c6`, `c62ab15`.** They never share a commit.
- **Uncommitted in the working tree: doc updates made for WB.** They touch `docs/integration.md`, `SETUP.md`,
  `CLAUDE.md`, `docs/star-databases.md` and `docs/gui-architecture.md`, and they **mix Part A and Part B text**.
  When committing, **split them into a Part A-only commit and a Part B-only commit**:
  - **Part A hunks** are anything marked TEMPORARY / CDS mirror mode:
    - the `[cds-mirror]` bullet in integration.md "Output and exit codes"
    - the mirror sentence in the ¶ paragraph and the catalog-tier "2026-11 additions" mirror bullet
    - the CR-25 TEMPORARY note
    - SETUP's "TEMPORARY — CDS mirror mode" section
    - CLAUDE.md's TEMPORARY guardrail, its `cds_mirror` module-map entry, and the plan-file listing
    - star-databases' option-50 note and gui-architecture's title note
  - **Part B hunks** are the rest:
    - the `[gaia-login]` bullet and the `gaia-jobs` quick-reference row
    - the Gaia-login sentences, and the CR-19 login-outside-the-bound note
    - SETUP's "Optional — ESA Gaia archive login" section
    - CLAUDE.md's Gaia-login guardrail and its `gaia_auth` module-map entry
  - `git add -p` is interactive, so it isn't available: build the split with temporary patch files
    (`git diff > all.patch`, edit it into two, then `git apply --cached` each).
- **The channel** (`/home/greg/Claude/coordination-channel.md`), MSGs 375–383:

  | MSG | From | Content |
  |---|---|---|
  | 375 | APP | the proposal |
  | 376 | WB | accepted, with asks |
  | 377 | APP | the pre-build checks |
  | 378 | WB | option A: all SIMBAD on CfA |
  | 379 | APP | the IDIA cut-off |
  | 380 | WB | the 2MASS cone, with 3 amendments |
  | 381 | APP | the `teff` / `fe_h` row-order finding |
  | 382 | WB | ruling (a): server row order, checked by WB's own fresh read |
  | 383 | APP | the full post-build message, including the 33-case list (29/33 all-present; G 169-29 a CR-27.2 median; HD 16765, σ CrB C and G 70-50 content differences) |

- **WB is running its equivalence check now.** The flag file `~/.config/space_app/cds_mirror` exists (created
  2026-11-11 19:46:54, not by APP), so **mirror mode is ON for every process on this box**. The flag file is
  WB's / Greg's to manage: don't create or remove it unless Greg says so.
- **The NASA Exoplanet Archive** was reported down by WB. APP's probes at about 20:13 EST found it up (TAP,
  `pscomppars` / `ps` / `stellarhosts`, and an end-to-end mirror-mode dossier). Greg is telling WB.
- **The ESA account is clean** (0 `space_app-*` jobs). The 401 back-off marker from VB4 was removed.

## Next steps, in order (each needs Greg's go where marked)

1. **Read WB's reply to MSG 383**: the equivalence-check results, questions or changes. Summarize them for Greg.
   If WB asks for code changes, plan them first. They are Part A or Part B fixes, committed separately.
2. **After WB's check is finished** (WB's runner records the app HEAD and dirty state at run start, so don't commit
   mid-run): **commit the uncommitted doc updates as one Part A-only and one Part B-only commit** (Greg's go).
3. **Greg pushes** `main` (APP's session can't push).
4. **Greg's approval** of the build.
5. **Then write `CDS_RESTORE_PLAN.md`**, the plan to move back to the main CDS services when CDS returns. Rules:
   - **Its removal list is built from Part A's actual commit diff**: `f0b1652`, `74a014c`, `99c0db9`, `80c840f`,
     plus the Part A doc commit from step 2 and any later Part A fix commits. That is the authoritative source;
     plan §5 is only a cross-check, and any site the diff has that §5 lacks gets called out.
   - It **reverts Part A only**. The ESA Gaia login (Part B), `gaia-jobs` and the credentials file **stay**.
   - It includes validation, success criteria and a `/code-review` checkpoint.
   - It includes a drafted WB message naming the restore commit (WB MSG 376 item iii). That is WB's trigger to switch
     its probe back and work its `cds-restore-retest-list.md`.
   - Its removal of the temporary files: `CDS_OUTAGE_BUILD_NOTES.md`, this resume prompt, the TEMPORARY doc blocks,
     `tests/test_cds_mirror.py` and `core/cds_mirror.py`. The plan file moves to `completed_plans/`.

## Standing rules

- **Post to the channel only at Greg's explicit go.** Draft first.
- **Never print or read the contents of `~/.config/space_app/gaia_credentials`.**
- **Greg pushes.** Commit only at his go (`main` only, no branches). Every commit message ends with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **One heavy job at a time** (8 GB WSL box). The full suite takes about 6 min:
  `venv/bin/python -m pytest -q -p no:cacheprovider`. The `QThread … dumped core` at interpreter exit is
  **pre-existing** (HEAD does it too).
- **Use light load on the volunteer mirrors and ESA.**
- Validation scripts from session 1 were in the session's scratchpad, which won't survive. Rebuild from
  `CDS_OUTAGE_BUILD_NOTES.md` if needed.
- Memory: `cds-outage-fallback-plan.md` holds the same state in short form.
