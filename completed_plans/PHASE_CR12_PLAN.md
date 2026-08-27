# PHASE CR-12 — WD cooling-grid ≤1.00 M☉ cooling-age re-derivation (Bédard 2020 unification) + criterion-1 correction

**Status: BUILT + FULFILLED both sides 2026-08-26** (WB re-gated green end-to-end; Greg signed the combined
CR-12/CR-12.4 flip, MSG 119). Only Greg's manual commit+push remains.
> **Actuals vs this plan:** the dense grid landed at **1458 rows / ~77 nodes/mass** (the plan's ~600–950 estimate
> rose once the CP1 Teff-at-age bound + the 0.5% age fidelity were enforced — reviewer-predicted). All **3 code-review
> checkpoints ran (14 findings, all addressed)**; offline suite went 3160 → **3164** including the CR-12.4 follow-up.
> **CR-12.4** (an additive `one_core_uncertain` caveat for M>1.05 M☉, in all three modes — snapshot/residence/CHZ;
> cited to Camisassa et al. 2019) was a separate additive follow-up folded into the same flip; its contract lives in
> `docs/integration.md` (CR-12.4 block), not this plan. **Housekeeping (done at commit):** this plan now lives in
> `completed_plans/`; `CR12_montreal_files/` **stays at the repo root** as committed reproducibility data (matching the
> repo's data-at-root convention — `gouldDesignations.csv`/`missionExocat.csv` etc. — and keeping the
> `cooling_tables.py` provenance reference valid).
Correction CR for the sibling `scifiWorldBuilding-Claude` `star_analysis` skill. Contract:
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR12-wd-cooling-grid-rederivation.md`;
evidence `wd-cooling-grid-verification.md`. Coordination: `/home/greg/Claude/coordination-channel.md`
(CR-12 round; F3 accepted MSG 107, Q1=source-exact / Q2 / D-A / D-B blessed MSG 107, downstream re-check MSG 109).

CR-12 is **not additive**: it deliberately **supersedes** CR-11.1's "byte-identical ≤1.0" guarantee (which
protected known-wrong ages) and **amends** CR-11.1's validation criterion 1 (backwards physics). It is the
reviewed follow-up CR-11.1 decision A deferred. No production card carries the inflated value as fact
(`cards/sirius.md` already uses the literature 126 Myr and flags the tool's 151); WB re-checked — the age-axis
re-parameterization blasts **no** card beyond that (MSG 109).

> **Review pass (3 agents across 2 revs, folded in).** Reviewer A rebuilt the dense grid + ran the engine (caught
> rev-1's backwards residence physics); Reviewer B traced 38 tests (the structural None-guard finding). Because B
> reasoned from the wrong premise, a **third, fresh, measurement-grounded** reviewer re-ran the actual suite against
> a rebuilt table — **36 passed, 2 failed** — and caught the one gap the first two missed:
> `test_chz_reproduces_across_masses` **fails at m=0.40** (0.6 M☉ was measured, but 0.4 is the case in that test's
> loop). rev-3 folds that in (now MUST-CHANGE) plus two number fixes. Verified sound: format/units/closure to 9.9e-6
> over 4528 rows; F3 at +38%; every anchor literal; the two None-guard tests **pass** at the measured peak (6.98 >
> 6.0, +0.98 margin). Corrections in §4/§5/§2 below.

---

## 0. Root cause (F3 — confirmed from code, WB-reproduced MSG 107, reviewer-reproduced)

One interpolation path, not a separate age path. `_WD_COOLING` stores per-mass `(age_gyr, teff_k, log10_l,
radius_rsun)` tuples; a `--teff T` query bisects `_interp_track` for the age where the *linearly-in-age*
interpolated Teff = T. That reduces to **linear-in-Teff interpolation between bracketing nodes for every column**,
so age(T) and radius(T) come off the **same nodes**.

The ≤1.00 sequences are **too sparsely sampled**: 1.00 M☉ has **10 nodes** (vs 18 in the CR-11.1 ≥1.05 set) and
**skips the ~18k–30k K mid-track** — jumping 30234 K (0.0595 Gyr) straight to 18614 K (0.3101 Gyr). At 25970 K the
source has a node at 26239 K → 0.1055 Gyr, but the tool has none there, so it interpolates the chord →
**0.1514** (reviewer-reproduced 0.15144 = the tool's 0.15141) vs source **0.1095** = +38%. `age(Teff)` is
**convex** across such gaps → the chord over-reads, worst mid-track = the verification's **+2–86%**. `radius(Teff)`
survives because **R varies ~1% across a track**; age spans orders of magnitude and is convex. CR-11.1 never
caught it because its only ≤1.00 check was the closure identity `L=R²(Teff/T☉)⁴`, **which has no age term** — the
sparse rows passed on Teff/L/R while the age column went **uncertified**.

**Remedy (= CR-12.1 + 12.3):** re-transcribe the whole 0.40–1.30 grid as a **dense** resample of the Bédard 2020
`Age` column so linear interp reproduces the source Age to **~1%**. **Invariant (WB Q1, MSG 107):** radius/Teff/L
outputs stay **source-faithful — ≤0.05% radius / <0.5% age vs the seq files** — **not** literally 0% (a resampled
linear-in-Teff radius differs from the old chord value by ~1e-5, e.g. 0.6/25970 → 0.013899 vs old 0.013901) and
**not** bit-identical to today's sparse table. WB's re-gate compares within tolerance, never exact-match.
Correcting only the 10 existing node ages **cannot** reach ~2% (the chord over-read survives); a decoupled
dense-age lookup is rejected (two-source-of-truth) — **one generation, one node set**.

---

## 1. Scope — three items, one data change + a doc/test correction

| Item | What | Where |
|------|------|-------|
| **CR-12.1** | Re-derive the ≤1.00 (0.40–1.00) cooling-age from the dense source | `core/cooling_tables.py` (`_WD_COOLING`) |
| **CR-12.3** | Pin the ≥1.05 age nodes to the same source (converge ±0–9% → ~2%) | `core/cooling_tables.py` (`_WD_COOLING`) |
| **CR-12.2** | Rewrite the backwards criterion-1 physics (Sirius B *older*, retire 0.151) | code comments + tests (spec text = WB) |
| **D-A** | Uniform 0.05 M☉ spacing 0.40–1.30 (add source `seq_045…095`) | `core/cooling_tables.py` |
| **D-B** | Retire the now-false `young_teff_cooling_age_inflation` note | `core/cooling.py` |

CR-12.1 and CR-12.3 are the **same physical change** — one dense re-transcription — built as one pipeline but
validated/re-gated as two items (≤1.00 first, then ≥1.05; ship both). CR-12.2 on the APP side is code-comment +
test changes (the CR-11 **spec** criterion-1 text is WB's to amend; WB is doing that).

---

## 2. Data pipeline (`CR12_montreal_files/transcribe.py` — new, reproducible)

Source archived in `CR12_montreal_files/` (19 files + md5 `MANIFEST.txt`; §3.1 pins reproduce byte-for-byte).
`transcribe.py` regenerates the `_WD_COOLING` literal deterministically — offline, no network.

1. **Parse** each `seq_0XX_thick.txt`: skip the 5-line header; each model = **3 lines**; take the **first** line's
   `Teff [K]`, `R [cm]`, `Age [yr]`, `L [erg/s]` (1-based cols 2/4/5/6). 218–265 models/file (verified vs MANIFEST).
2. **Convert:** `teff_k=Teff`; `radius_rsun=R_cm/6.957e10`; `age_gyr=Age_yr/1e9`; `log10_l=log10(L_erg/3.828e33)`.
   (The tool **derives** L from R & Teff at runtime — `_interp_track` line 164 — so stored `log10_l` only feeds the
   closure integrity check; source values keep it exact. Reviewer confirmed closure holds to ratio 0.99998 over all
   4528 source rows.)
3. **Adaptive, error-bounded subsample** (the fix). Keep the endpoints, then greedily insert the source row with the
   largest **age-error of the current linear-in-Teff interpolant** until every gap is under tolerance. Use a
   **relative bound with an absolute-age floor** — `err_ok = |Δage| ≤ max(0.5%·age, ~1e-4 Gyr)` — **or** enforce the
   bound only within the **output-relevant Teff band (~2600–40000 K)**. This is a rev-2 fix: a pure *relative*
   metric explodes as age→0 at the sub-Myr young/hot tail (age = 6×10⁴ yr, Teff > 40000 K — above Kopparapu
   validity, consumed only by out-of-range-flagged young snapshots), forcing ~90 nodes/mass (~1700 total, ~7×
   today's ~250) with half of them certifying a regime nothing consumes. The floor/band cut it to **~30–50
   nodes/mass (~600–950 total)** while **focusing density on the mid-track + cool tail where age precision is
   consumed** (residence exit, distillation-pause Teff, snapshot age). Target ≤0.5% age keeps margin under the ~2%
   re-gate; radius stays ≤0.05% by construction (R nearly flat in Teff).
4. **Emit** the `_WD_COOLING` literal (19 masses), each sequence sorted ascending by age, Teff strictly decreasing.

> ⟢ **CODE-REVIEW CHECKPOINT CP1 (data pipeline — highest risk).** Review `transcribe.py` for: correct
> 3-line-per-model parsing (no continuation-line contamination), correct unit constants, the subsample bound
> (incl. the absolute-age floor) actually enforced, and a **by-hand spot-check of ≥3 masses against raw source
> rows** — incl. the §3.1 pins on 0.90/1.00/1.05 and the coincident-byte-size trio 100/105/115 (confirmed
> distinct md5/first-row already). A transcription bug is **silent and physical** — the closure identity will not
> catch a wrong age (the F3 lesson). Run `/code-review high` on `transcribe.py` + the regenerated table. Note the
> diff is **larger than rev-1 implied** (~600–950 rows, not ~500–850).

---

## 3. Files changed

### 3a. `core/cooling_tables.py` — `_WD_COOLING` regenerated (CR-12.1 + 12.3 + D-A)
- Replace `_WD_COOLING` with the dense re-derived grid: **19 masses** `0.40, 0.45, …, 1.30` (D-A adds
  `0.45/0.55/0.65/0.75/0.85/0.95` from the real source files — `0.95` is an **exact node**, WB's re-gate anchor).
- Update the provenance comment block (~lines 20–39): drop "0.40–1.00 rows are byte-identical" and the CR-11.1
  "extended 0.40→1.30" framing; state that **CR-12 re-derived the whole grid** as one dense Bédard 2020 generation
  (0.05 spacing, adaptive resample), archived + reproducible in `CR12_montreal_files/`. `_WD_TABLE_SOURCE` string
  stays "Bedard et al. 2020 … 0.40–1.30 M_sun" (now accurate for the whole grid).
- `_BD_COOLING` (ATMO 2020 BD track) **untouched**.

### 3b. `core/cooling.py` — retire the inflation note (D-B)
- Remove the `young_teff_cooling_age_inflation` `notes` block in `_mode_snapshot` (lines ~505–511) + its comment.
  After CR-12 the ages are source-faithful, so the note is **false**; pulled **as part of** the fix so it vanishes
  exactly when the inflation does (WB guard, MSG 107). No other logic changes — Chandrasekhar clamp/refuse
  (1.30–1.38 / >1.38), interpolators, the three modes, the A0 distillation pause, and the `model_note` builder are
  unchanged (they read the table, which is what changed).

### 3c. `tests/test_cooling_hz.py` — see §4.

### 3d. Docs
- `docs/integration.md` — cooling-hz block: CR-12 note (whole grid one dense Bédard 2020 generation; ≤1.00 age
  corrected up to ~86%; Sirius B ~0.118; provenance `CR12_montreal_files/`; the age-axis re-parameterization —
  residence/CHZ/snapshot-@age shift, Teff-only outputs unchanged).
- `CLAUDE.md` — cooling-module note + test count.
- `completed_plans/PHASE_CR11_PLAN.md` — one-line **"SUPERSEDED BY CR-12"** annotation on CR-11.1 (byte-identical
  ≤1.0 + criterion-1 + the 0.146 Sirius-B age).
- `docs/testing.md` — `test_cooling_hz.py` description for the new anchor test.
- `CR12_montreal_files/` — README + MANIFEST written; add `transcribe.py`.

---

## 4. Blast radius — every `test_cooling_hz.py` test classified (rev-2, reviewer-corrected)

The correction re-parameterizes the WD **age axis**, but the inflation is **Teff-localized, not uniform**
(measured 0.6 M☉: +40.7% @8000 K, +37.4% @6000 K, +6.1% @5000 K, −2.2% @4000 K). So **residence = age(T_exit) −
age(T_entry) changes by an orbit-dependent, sign-varying amount** — it is NOT a uniform shortening (rev-1's error).
Teff-only outputs (radius@teff, L@teff, HZ zones@teff) are source-faithful/unchanged.

**CHANGE — re-pin to source, recomputed at build (defect-encoding, must flip):**
- `Cr111HighMassWDTest.test_no_regression_below_one_msun` — pins `0.6/25970 → 0.021342`, `1.0/25970 → 0.151411`
  (byte-identical ≤1.0). Both ages drop **−28%** (measured: 0.6 → **0.01539**, 1.0 → **0.10947**). **Recompute BOTH
  the age AND the radius literals at build** — the source-faithful radius differs from the old chord value (0.6
  0.013901→**0.013899** Δ1.9e-6; 1.0 0.008295→**0.008294** Δ1.05e-6), **both exceeding the `places=6` 5e-7 gate**,
  so widening to `places=5` alone is insufficient — recompute. Rename → *source-faithful ≤1.0*.
- `Cr111HighMassWDTest.test_sirius_b_returns_without_error` — **semantic rewrite, not a suite-breaker** (measured age
  **0.11765** still satisfies `assertLess(…, 0.1514)`, so it passes as-is). But that assert references the retired
  0.1514 and encodes inverted physics, so rewrite → `age ≈ 0.118` (delta) **and** `≥ the clean M=1.00 value
  (~0.1095)` — monotonic older-with-mass. Radius (~0.008) stays.
- `Cr111HighMassWDTest.test_young_teff_note_gated_above_one_msun` — asserts the note **fires** for Sirius B. Rewrite
  → assert the note is **absent** everywhere (D-B removed it).
- `ModeChzTest.test_chz_reproduces_across_masses` (lines 146–152) — **the fresh review's one suite-breaking catch**
  (an earlier pass measured only 0.6 M☉, which is **not** in this test's mass loop `(0.40,0.50,0.70,0.80,0.90)`).
  Measured at **m=0.40**: `chz_inner_au` = **0.00286 (dense) / 0.00297 (subsample)**, both **below** the shared
  `0.003` lower bound (line 151) — the 0.40 CHZ inner edge migrates ~45% inward, a **real** physical shift (current
  table 0.00530). **Re-pin the m=0.40 lower bound to ≈0.0025** (justified vs Agol) or lower the shared floor; it is
  boundary-fragile, so pin with margin.

**VERIFY at build — measured to PASS UNCHANGED (do NOT pre-emptively re-pin; rev-1 wrongly said "re-pin downward"):**
- `ModeResidenceTest.test_acceptance_001au` — reviewer A measured 0.6 @0.01 AU: cons **4.49 → 5.83 (+30%)**, opt
  **→ 8.42** — both stay **inside** the current 3.5–6.0 / 6.0–9.0 ranges. Expected pass; re-pin **only if** the
  actual build lands outside, and then to the literature-consistent value.
- `ModeChzTest.test_acceptance_band` — 0.6 CHZ band (Agol 2011 0.005–0.02 AU). Measured **0.00716/0.01816**, inside
  the current windows. Expected pass; verify vs Agol. *(`test_chz_reproduces_across_masses` moved to MUST-CHANGE —
  it fails at m=0.40; see above.)*
- `DistillationPauseTest.test_peak_residence_matches_vanderburg` — measured std **6.27 → 6.97**, dist **16.26 →
  16.97** — both **inside** `5.5–7.5` / `14.0–18.0`. The residence *grows* here (opposite of rev-1). Expected pass;
  verify vs Vanderburg Table 1. **Do not re-pin `dist` to 14.97** (a rev-2 slip — real value ~16.97; 14.97 would
  fail the `assertGreater(dist, std+8.0)` clause).

**VERIFY at build — None-guard fragility (reviewer B; passes under the measured peak, but restructure the assert):**
- `ModeChzTest.test_higher_threshold_narrows_band` (line 139) — computes `hi["chz_outer_au"] - hi["chz_inner_au"]`
  at threshold 5.0. If the conservative peak residence ever falls **below 5.0**, `_chz_band` returns `None/None`
  (an empty band is not an error) and this line does `None − None` → **TypeError** (not a clean fail). Under the
  measured peak ~6.97 (> 5.0) the band is populated and the test **passes** — but **confirm the built peak > 5.0**
  and **guard the subtraction against `None`** so a future shift degrades cleanly.
- `DistillationPauseTest.test_chz_moves_outward` (line 303) — the fragile assertion is the **b6/p6** comparison
  (threshold **6.0**), not the b8 block rev-1 cited (b8 stays valid: empty→empty). `assertGreater(p6_outer,
  b6_outer)` becomes `assertGreater(number, None)` → TypeError if the no-pause threshold-6.0 band empties. Measured
  peak ~6.97 keeps b6 populated (thin ~0.97 Gyr margin). **Confirm b6 non-empty at build; guard the compare.**

**~UNCHANGED (reviewer downgraded from rev-1 CHANGE):**
- `ModeChzTest.test_roche_collision` — `roche_limit_au` is radius-based (unchanged); `inner_edge_roche_limited` is a
  robust boolean (cool-WD CHZ inner inside the disruption radius). Both pass unedited; verify only.

**UNCHANGED (structural / Teff-only / self-consistency — confirmed by both reviewers):**
- `TableIntegrityTest.*`, `InterpolationTest.*`, `ModeSnapshotTest.*` (all four: Teff-input L/zones, key-set,
  round-trip parity, hot-young flag), `ModeResidenceTest.test_crossing_direction` / `test_never_habitable_far_and_near`,
  `ModeChzTest.test_higher_threshold_narrows_band`'s *monotone property* itself, `Cr111HighMassWDTest.test_grid_extends_to_130`
  / `test_radius_monotone_decreasing_in_mass` / `test_high_masses…` / `test_chandrasekhar_clamp_and_refuse`,
  `DistillationPauseTest.test_delta_zero_byte_identical` / `test_pause_fields_present_and_consistent` /
  `test_residence_lengthens_by_delta` / `test_snapshot_through_pause` / `test_validation` / `test_determinism`,
  `BrownDwarfTest.*` (BD track untouched), `ValidationTest.*`, `ChzDegenerateBandTest.*`.
- Stale-comment fix: `ValidationTest.test_error_matrix` line comment "(WD grid 0.4-1.0)" → "0.4–1.30".

**NEW — `test_age_matches_source_at_anchors` (the missing check the CR turns on):**
Assert cooling-age matches the source within ~2% at **all four §3.1 Teff** (rev-2: reviewer A caught that rev-1
only pinned 25970/10000 — add **15000 K**, which holds the current **worst +86% error** at 1.00 M☉, and **6000 K**,
where the mass-turnover lives). Anchor masses are **exact grid nodes** after D-A, so `_age_for_teff` does age-only
interpolation (no mass smearing). Include **Sirius B 1.018/25970 → ~0.118** (mass-interp; reviewer 0.1178, ≥ the
1.00 node 0.1095, ≤ the 1.05 node 0.133). Plus a **monotonicity** assertion: age increases with mass up to the
**Teff-dependent turnover** (no turnover through 1.30 @25970; ~1.20 @10000; ~1.05 @6000). Note the monotone assert
relies on the **0.5% build tolerance**, not the 2% re-gate tolerance — near the flat turnover the mass-steps are
tiny (6000 K 1.00→1.05 = +1.7%; 10000 K 1.15→1.20 = +2.3%), so a 2% error could flip an ordering; either scope the
assert to the 0.5% build target or skip the turnover-straddling mass pair. Source values embedded as literals with
the §3.1 citation (WB re-derives independently).

> ⟢ **CODE-REVIEW CHECKPOINT CP2 (test correctness — rev-2 rewritten).** Verify each re-pin/verify is anchored to
> **source or literature MAGNITUDE**, in **either direction** — NOT to an assumed direction (rev-1's "confirm it
> moved shorter" was wrong and would have rejected the correct +30%/+11% values). Most residence/CHZ tests should
> **pass unchanged**; a change that *moves* them is suspect and must be justified against Fossati/Agol/Vanderburg.
> Confirm the two empty-band arithmetic sites (`test_higher_threshold_narrows_band`, `test_chz_moves_outward` b6/p6)
> are **None-guarded** and their bands non-empty at the built peak. Confirm radius literals were **recomputed**, not
> just loosened.

---

## 5. Risks (rev-2)

- **R1 (managed) — age-dependent modes shift by an orbit-dependent, sign-varying amount.** The inflation is
  **Teff-localized**, so residence/CHZ change direction depends on which Teff the two HZ crossings fall on (0.6 M☉:
  0.005 AU −5%, 0.01 AU +30%, 0.02 AU −45%; conservative **peak +11%**). The three acceptance tests **pass
  unchanged** (measured). **Mitigation:** verify each value against its literature **magnitude** (both directions),
  never re-pin toward an assumed direction; None-guard the two empty-band sites (§4). WB re-gates the direction
  (MSG 109). This is CP2's focus. *(Rev-1 claimed a uniform ~25–30% shortening — wrong; corrected here.)*
- **R2 — a silent transcription bug is physical, not a crash.** The closure identity does not test age. **Mitigation:**
  the new 4-Teff age-vs-source anchor test + CP1's by-hand raw-row spot-check; the coincident-byte trio 100/105/115
  explicitly diffed (confirmed distinct).
- **R3 — node-count / over-sampling.** A pure relative-age bound yields ~1700 rows (~7×) by over-sampling the
  sub-Myr hot tail. **Mitigation:** the absolute-age floor / Teff-band bound (§2 step 3) → ~600–950 rows, focused
  where age precision is consumed. No runtime concern (O(log n), n≤~50/mass).
- **R4 — Montreal site drift vs WB's copy.** Mitigated by the §3.1 byte-for-byte cross-check (both re-fetch;
  reconcile before trusting a pull — Q2/MSG 107). Confirmed aligned on this pull.
- **R5 — Sirius B target ~0.118, not the literal 0.126.** The tool interpolates the frozen source grid; ~0.118 is
  source-faithful (Bond 2017 ~0.126 is a full-model number). This is the **correct** CR-12 target (spec criterion
  2: within ~6% of Bond) — documented, not "fixed."

---

## 6. Build order & review gates (per spec; ship all three, no deferral)

1. Archive source (**done**) → write `transcribe.py` → regenerate `_WD_COOLING` **≤1.00 first** (CR-12.1), then
   **≥1.05** (CR-12.3) in the same pass; add D-A masses; absolute-age-floor subsample. → **CP1** (`/code-review high`).
2. Remove the inflation note (D-B) in `cooling.py`.
3. Re-pin/rewrite tests + add the 4-Teff age-vs-source anchor test (CR-12.2 physics in the Sirius-B assert);
   None-guard + confirm the two empty-band sites; recompute radius literals. → **CP2** (`/code-review high`).
4. Run the **full offline suite** (`venv/bin/python -m pytest`) — memory-safe default, no live/dust gates. §4
   predicts the exact change set; **any test outside it moving is a signal** to investigate (esp. an unexpected
   `None−None` TypeError = an emptied band). Confirm the anchor test passes at ~1% across all 4 Teff and Sirius B
   monotonic-older.
5. Docs (§3d). → **CP3** (`/code-review high` on the full diff) before hand-off.
6. Post to channel: build complete + a self-run of the WB re-gate anchors (§3.1 all 4 Teff + Sirius B + the
   measured residence/CHZ directions) → **WB independently re-gates** on the sister venv (re-deriving from the seq
   files) → **Greg signs one FULFILLED flip** → OQ-SA-WDAGE1 closes; WB updates `cards/sirius.md` (151 → ~110 /
   Sirius B ~118).

**Commit is Greg's manual step** (standing instruction). This plan moved to `completed_plans/` at FULFILLED;
`CR12_montreal_files/` stays at the repo root as committed reproducibility data.

## 7. Acceptance (what "done" means)

- `cooling-hz --track wd` cooling-age within **~2%** of source at **all four §3.1 Teff × all masses**, **whole
  0.40–1.30 grid one generation** (≥1.05 converged from ±0–9% to ~2%).
- **Sirius B (1.018/25970) ≈ 0.118**, **≥ the clean M=1.00 (~0.1095)** — monotonic older-with-mass; 0.151 retired.
- Radius/Teff/L outputs **source-faithful (≤0.05% radius / <0.5% age)**; `>1.38` refuses; 1.30–1.38 clamp intact.
- Inflation note gone; the new 4-Teff age-vs-source anchor test guards the age column; the two empty-band CHZ tests
  None-guarded; **full offline suite green** (only the §4-predicted set changed).
