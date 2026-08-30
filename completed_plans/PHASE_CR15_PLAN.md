# Implementation Plan — CR-15 (CR-14 amendment): dossier secondary-target + cross-path fallback + de-dup

**Status:** ✅ BUILT + FULFILLED (Option A, 2026-08-29). Suite 3238/88/0; two plan-review forks (correctness +
risk) pre-build; one end `/code-review high` (4 findings triaged); WB independent re-gate GREEN (MSG 178); Greg
signed the flip + gave the direct commit go. Committed + pushed to `main`. Channel MSG 170–179.
**Source:** WB coordination-channel MSG 170 (spec) + the repo contract
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR15-….md`;
**Q1–Q4 confirmed MSG 172** (Greg-approved). **Q5 → OPTION A (MSG 174, Greg-approved):** drop-override only;
**do NOT touch `component_candidate_ids`/`match_mass`** — the letterless-primary correctness gap (Sirius B) is a
**separate follow-up CR-16** (WB spec'ing). **CR-15.4 additive `binary_orbit identity.designations` key APPROVED
(MSG 174).** **All 5 parts in one build, no phasing.**
**Not byte-identical by design:** 15.1/.2 change *wrong* outputs → correct; 15.3/.4/.5 behavior-preserving.
**Re-gate:** WB independently on the sister venv (CR-15.1/.2 anchors + the full star_analysis pin battery) → Greg's one FULFILLED flip.

Touch surface: `core/report.py` (15.1, 15.5), `core/stellar_mass.py` (15.2 fallback, 15.3 helper),
`core/exclusion_system.py` (15.3 delegate — frozen CR-13 anchors PINNED unchanged), `core/binary.py`
(15.3 delegate, 15.4 dedup) + tests. `docs/integration.md` only if an output key changes (goal: none).

---

## Root-cause trace (verified in-session against `c984ecf`)

`binary-stability-auto --star "alpha Cen B"` is **correct** (1.079/0.909) because `resolve_binary_components`
resolves A via `prim_spec` whose designations are augmented with `component_candidate_ids(main_id="* alf Cen B",
"A")` → strips " B" → **"* alf Cen A"** → the catalog matches the true primary (1.079). B resolves via
`component_candidate_ids(…, "B")` → "* alf Cen B" → 0.909.

The **dossier** fails **only** because `report._multiplicity_data_star` passes a `primary_override` (the target's
regions mass) that **short-circuits** that A resolution (`stellar_mass.resolve_binary_components` L248-249:
`if primary_override is not None: m1, prov_a = primary_override`). For a secondary target the regions mass is B's
→ slot A = 0.909. Its dossier `simbad` is already the same input-star lookup `binary-stability-auto` uses, and
`component_candidate_ids` already handles secondary→primary derivation — so **dropping the override is the whole
fix** (no identity re-plumbing needed). `alpha Cen A` is unchanged because there the override value (A's regions
mass) equals what the chain resolves anyway.

---

## CR-15.1 — drop the dossier `primary_override` (#1, Medium)

- **`core/report.py` `_multiplicity_data_star`:** remove the override-building block (L668-672) and pass **no**
  `primary_override` to `resolve_binary_components` (L673-674). The now-unused `regions_mass_block` param is
  removed (from the signature L622 and the caller L1135) — it is used ONLY to build the override (verified: no
  other reference in the function).
- Result: A resolves via `prim_spec` (component_candidate_ids injects the primary designation) → matches
  `binary-stability-auto` exactly. **Anchor (build-time acceptance):** `dossier --star "alpha Cen B" --sections
  multiplicity` → **1.079 + 0.909**, sma ≈ 23.3, stype **2.749**, ptype **86.652**, μ 0.457. **Regression:**
  `dossier --star "alpha Cen A"` stays 1.079+0.909 / 2.75 / 86.7; `binary-stability-auto` + exclusion unchanged.
- **Sirius B (refined acceptance, MSG 174 Option A):** `dossier "Sirius B" --sections multiplicity` must
  **EQUAL `binary-stability-auto "Sirius B"`** (both m1=1.0 — **cross-path consistency**, the CR-14.3 goal), NOT the
  correct 2.06. The letterless-primary correctness gap (seed Sirius A `main_id` is letterless `* alf CMa`, so
  `binary-stability-auto` itself gives 1.0) is a **pre-existing defect PARKED to CR-16** — **CR-15 must NOT touch
  `component_candidate_ids`/`match_mass`** (they feed the frozen CR-13 exclusion + CR-14 binary anchors). So for
  Sirius B, dropping the override simply makes the dossier match binary-stability-auto (both 1.0) — cross-path
  consistent, correctness deferred to CR-16.
- **H1-comment concern (why the override existed):** it avoided re-resolving A / a possible FLAME round-trip and
  guarded against an L-inversion mass under `--sections multiplicity` alone. Dropping it means A routes through
  `resolve_component_mass(allow_flame=True)` → measured-preferring (catalog/FLAME), which is *more* correct;
  cost is A's resolution round-trip (see 15.5). WB Q1: collateral is caught by the full re-gate.
- **NOTE (honesty):** the fixed output (1.079/0.909) is asserted by the build-time anchor test + a live
  `query.py dossier` run before handoff — NOT pre-claimed. (My earlier MSG-167 0.698 was a mis-configured
  in-process artifact; the fix is verified through the real subcommand this time.)

## CR-15.2 — empty/None `main_id` fallback consistent across paths (#4, Edge/low)

- **`core/stellar_mass.resolve_binary_components`:** add a `system_name=None` param; change the B fallback (L258)
  from `…, None)` to `…, (f"{system_name} B" if system_name else None))` — matching
  `exclusion_system._resolve_system_from_star` (L533 `…, f"{star} B")`). Then both paths attempt `"{name} B"`,
  look it up, and fall to the orbit split only on failure (prefer measured). Callers pass the star/system name:
  `binary.binary_stability_auto` (has `star`), `report._multiplicity_data_star` (has `star`).
- The A-side is already consistent (both build `prim_spec` with `component_candidate_ids(main_id,"A")`, empty when
  main_id empty → orbit split) — only the B fallback differed.
- **Acceptance:** a unit test constructs an empty/None `main_id` case and asserts `resolve_binary_components` and
  `_resolve_system_from_star` return the **identical** component-B mass. Normal (non-empty) cases unchanged.

## CR-15.3 — one shared Kepler-III SMA helper (#2, quality)

- Two identical copies today: `binary.py:783-784` (`stability_from_solutions`) and `exclusion_system.py:561-562`
  (`_resolve_system_from_star`), both `sma = sma * (pref_mtot/sel_mtot)**(1/3)` when `sma and sel_mtot>0 and
  pref_mtot>0`. (Contract said "~3"; the 3rd was a comment/approximation — I consolidate the 2 real copies and
  grep-confirm no others at build.)
- **`core/stellar_mass.py`:** add `recompute_sma_kepler3(sma, sel_mtot, pref_mtot) -> float`. **Guard on
  TRUTHINESS exactly as both copies do** (Reviewer-2 MED): `if sma and sel_mtot > 0 and pref_mtot > 0: return sma
  * (pref_mtot/sel_mtot)**(1.0/3.0)` else `return sma` — **NOT `if sma is not None`** (a `None`/`0.0` sma must pass
  through unchanged; `is not None` would crash on `None` and change `0.0`). `binary.py` + `exclusion_system.py`
  delegate. **Behavior-preserving** (identical arithmetic) → exclusion's frozen CR-13 anchors byte-identical (pinned).

## CR-15.4 — dedupe redundant primary SIMBAD lookup in `binary-stability-auto` (#3, quality)

- Today: `binary_orbit` → `_resolve_binary_identity` does `compute_simbad_lookup(star)` (binary.py:221) and
  **discards** designations; `binary_stability_auto` (binary.py:865) does a **2nd** `compute_simbad_lookup(star
  or ident.main_id)` to get the primary_sl (needs designations); `resolve_binary_components` does a 3rd for B.
  Lookups #1 and #2 are the same star. `compute_simbad_lookup` is **not cached** (verified) → the 2nd is a real
  network hit.
- **REFRAMED (Reviewer-2 HIGH):** the "internal sl-passthrough that keeps `binary_orbit` byte-identical" is
  **INFEASIBLE** — `binary_stability_auto` calls `binary_orbit(...)` and only sees its public `result` (keys
  `query`/`identity`/`solutions`/`route_tried`, **no sl**); the sl is trapped inside `binary_orbit`. Removing the
  L865 lookup therefore REQUIRES exposing the primary designations in `binary_orbit`'s output — an **additive
  `identity.designations` key** (no existing value moves). **This touches `binary_orbit`'s output, so it needs
  WB's explicit ok** (asked as the CR-15.4 follow-up).
- **APPROVED (MSG 174): additive `identity.designations` key.** Add `designations` (the full dict) to the
  identity built in `_resolve_binary_identity` (it already has the sl in hand at L226 — `desig = sl.get(...)`).
  `binary_stability_auto` builds `primary_sl` from `ident` (main_id + sp_type + designations) → **removes the
  L865 re-lookup**. WB confirms this is behavior-preserving (a NEW field; existing outputs unchanged).
  **Gate:** verify the `binary_orbit` pin battery is key-specific (not full-dict) so the additive key breaks no
  pin; report −1 primary SIMBAD lookup per `binary_stability_auto --star` run.

## CR-15.5 — trim extra `dossier --sections multiplicity` round-trips (#5, quality)

- The dossier already holds the target `simbad` (its own lookup) and passes it to `resolve_binary_components`
  (reused, not re-fetched). Dropping the override (15.1) adds A's chain resolution. Net round-trips per run are
  reported before/after; reduce only what is cleanly behavior-preserving (e.g. ensure no double-lookup of B; reuse
  the already-fetched target simbad). **Directional/optional metric** per the contract — no output change.

---

## Test plan
- **CR-15.1 (behavior change → correct):** `test_dossier_secondary_target_orbit_normalizes` — offline/mocked +
  a live-gated anchor: `dossier "alpha Cen B"` → 1.079/0.909, 2.749/86.652 == `binary-stability-auto` ==
  `dossier "alpha Cen A"`; regression: `dossier "alpha Cen A"` unchanged.
- **CR-15.2:** `test_empty_main_id_cross_path_equal` — constructed empty-main_id → `resolve_binary_components` B
  mass == `_resolve_system_from_star` B mass.
- **CR-15.3:** `test_kepler3_sma_helper` — helper matches the pre-refactor formula on sample inputs + guard
  no-op; exclusion + binary anchors unchanged.
- **CR-15.4:** a lookup-count assertion (monkeypatch/count `compute_simbad_lookup`) showing `binary_stability_auto
  --star` issues one fewer primary lookup; output unchanged.
- **Regression:** the full existing salvo/star-analysis/exclusion/binary/report pin battery green
  (`venv/bin/python -m pytest`); the CR-13 exclusion anchors byte-identical.

## Build sequence + gates (APPROVED: one end `/code-review` + intermediate TEST gates; nothing runs until Greg authorizes)
- **Stage 1 — CR-15.1** (drop override + remove `regions_mass_block` plumbing) + tests →
  **GATE (test):** live `dossier "alpha Cen B"` = **1.079/0.909, 2.749/86.652**; `dossier "alpha Cen A"`
  unchanged; **`dossier "Sirius B"` == `binary-stability-auto "Sirius B"`** (both 1.0 — cross-path consistency
  per Option A; letterless correctness parked to CR-16); **primary-target regressions on the seed anchors**
  (α Cen A, Sirius A, Vega — proves dropping the override doesn't shift a primary's A mass/source). Stop if any
  wrong before building further.
- **Stage 2 — CR-15.2 + 15.3** (fallback consistency + shared truthiness-guarded Kepler-III helper + delegates)
  + tests → **GATE (test):** frozen CR-13 exclusion anchors + binary anchors byte-identical.
- **Stage 3 — CR-15.4 (+ 15.5)** (lookup dedup per WB's 15.4 ruling — additive key or defer + report count)
  + count tests → **GATE (test):** `binary_orbit` pin battery unchanged.
- **End — ONE `/code-review high` on the full accumulated diff + full `venv/bin/python -m pytest`** (the whole
  star-analysis/exclusion/binary/report + salvo battery green).
- **Stage 4 — Handoff:** post "built + green" + before/after round-trip counts to WB; WB independent re-gate;
  Greg's FULFILLED flip → commit + push to `main` + CLAUDE.md summary + move this plan to `completed_plans/`.

## Risks
- **15.1 collateral** on non-α-Cen systems (dropping the override changes A's source from regions-mass to the
  chain) — caught by WB's full re-gate + the `alpha Cen A` regression pin; the live anchor verify at Stage 1 is
  the first gate. **Do NOT pre-claim the fixed numbers** (MSG-167 lesson) — verify via the real subcommand.
- **15.4** must not change `binary_orbit`'s output — the sl-passthrough (byte-identical) is preferred over an
  additive key; flagged for review + WB.
- **15.3** exclusion frozen CR-13 anchors — identical arithmetic, pinned.
