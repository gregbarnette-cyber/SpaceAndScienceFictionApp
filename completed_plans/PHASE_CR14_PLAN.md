# PHASE CR-14 — shared `_extract_stability_elements` correctness (solution selection + catalog-aware mass + degenerate flagging)

**Status: REVISED after plan-review — NOT approved to build.** Two independent plan-review agents ran.
Spec/re-gate coverage = 0 HIGH. Feasibility = **1 HIGH (H1) + 5 MEDIUM + 4 LOW** (see §10). H1 is a real
correctness defect in WB's Q1 "reuse the regions primary mass" optimization — **resolved in this plan**
(the optimization is dropped/guarded; WB endorsed the fix, MSG 141). M4 is **resolved → (a)** (WB MSG 141).
**Greg CLEARED THE BUILD (in-session) and approved folding in (b)** — so CR-14 = CR-14.1/.2/.3 **+
CR-14.4 (the (b) filter narrowing)**. Build authorized; **no commit / no FULFILLED flip** until Greg's
sign-off. WB informed (MSG 143). The exclusion path is therefore **no longer strictly byte-identical** — it
adopts the (b) filter too (uniform), so its re-gate becomes "anchors UNCHANGED under the (b) filter + the
(b) improvement correct," not "byte-identical."

**BUILD COMPLETE (2026-08-29).** All parts implemented + the CR-14 offline tests green (`test_binary_stability_auto.py`
Cr14* classes; exclusion suite unchanged-green). The (b) filter was refined during build (a fulfilled CR-13 test caught
that a naïve "drop degenerate-only" would let an SB1 minimum preempt a real SB2 — now: degenerate always dropped, SB1-min
dropped when a real SB2 exists, clean astrometric abs kept; WB told, MSG 145/146). Full offline suite run + CLAUDE.md
summary + the two live re-gate anchor-star names pending; **holding for Greg's commit/flip sign-off + WB's live re-gate**.
Files changed: `core/binary.py`, `core/stellar_mass.py`, `core/exclusion_system.py`, `core/report.py`, `query.py`,
`tests/test_binary_stability_auto.py`, `tests/test_exclusion_system.py`, `docs/integration.md`.

*(One build-time TODO: name the concrete non-seeded binary for the H1 / CR-14.3-#4 re-gate anchor — a
primary not in the seed but with a Gaia FLAME mass — verified live at build; WB re-gates whatever is named.)*

Contract: WB's `spaceapp-change-request-CR14-shared-solution-selection-degenerate-flag.md`
(coordination-channel MSG 136). Same collaboration shape as CR-13:
APP Q&A → APP builds CR-14.1/.2/.3 → WB re-gates live (both **with** and **without** the catalog) →
Greg signs one FULFILLED flip.

---

## 1. The verified finding (WB, live 2026-08-29, α Centauri)

When `binary_orbit` returns several solutions, the shared `binary._extract_stability_elements` takes
the **first**, which for α Cen is a **placeholder `mass_ratio_q = 1.0`** (SB9 seq 815, P=29650.4 d) —
while later solutions carry the real ratio (~0.84, P≈29187 d). Every consumer inherits the equal-split:

| Invocation | Live output | Correct? |
|---|---|---|
| `binary-stability-auto --star "alpha Centauri"` | `m1 1.02 / m2 1.02` | ✗ degenerate equal split |
| `dossier --sections multiplicity --star "alpha Centauri"` | `1.02 / 1.02`, sma 23.778, stype_critical 2.596, ptype_critical 87.005, basis "SB9 seq 815" | ✗ all on the degenerate solution |
| `multiplicity --star "alpha Centauri"` (standalone) | classification only — **no per-component masses** | ✓ **not a defect — DO NOT touch (regression-guarded)** |

Real α Cen ratio: m2/m1 = 0.909/1.079 = **0.843**; the degenerate solution forces μ=0.5 instead of the
true **μ=0.457**, which is why the Holman–Wiegert critical SMAs are also wrong (dynamical, not cosmetic).

This is the exact defect CR-13.3 fixed **scoped** to the `exclusion-system --star` resolver. CR-14 fixes
it at the **shared root** for the OTHER consumers: `binary-stability-auto` (CR-3), the dossier
`multiplicity` **section** (CR-10.5), and `binary-orbit` (marker only — pending Q3).

**Scope (from the contract):** CR-3 + CR-10.5 (+ `binary-orbit` marker). **NOT CR-2** — the standalone
`multiplicity` subcommand exposes no per-component masses and stays byte-identical.

**Verified offline (this session):** the internal seed (`stellar_mass_tables._SEED_CATALOG`) holds
α Cen A/B + Sirius A but **NOT Sirius B** → re-gate target #5's "no B row" condition is true by default.

---

## 2. Q1–Q3 — RESOLVED (WB, channel MSG 138)

- **Q1 — dossier chain depth → FULL CHAIN ON BOTH.** `manual > catalog/seed > FLAME > orbit/inversion` on
  `binary-stability-auto` **and** the dossier `multiplicity` section, accepting the added per-component
  network. Required by the cross-path-consistency guarantee (#3): capping the dossier at offline would make
  a *non-seeded* star read an orbit mass in the dossier while the other two paths read FLAME — the exact
  split CR-14.3 kills. α Cen/Sirius (the regeneration set) are seeded → offline, **zero** added cost.
  **Optimization (WB Q1) — GUARDED per plan-review H1 (§10):** the dossier's regions-primary mass_block
  consults FLAME only when `("regions" in requested)` (report.py:1011), so on `--sections multiplicity`
  a *non-seeded* primary is an **inversion** mass, not FLAME — reusing it verbatim reintroduces the split.
  So: resolve both multiplicity components through the shared full chain (`allow_flame=True`) independently,
  and reuse the regions primary **only** when its provenance is a *measured* tier (manual/catalog/gaia_flame),
  never inversion. Seeded anchors stay offline; a non-seeded binary stays consistent.
- **Q2 — Sirius B flag → HONEST TIER, and it must EQUAL exclusion's flag.** B carries whichever
  degenerate/lower-bound flag matches its **actual** orbit tier — never a fabricated `sb1_min`. **Expected
  value:** the CR-13 exclusion re-gate gave `exclusion-system --star "Sirius"` (no B row) → Sirius B
  `0.458` / `binary_orbit_sb1_min`; since CR-14.3 routes `binary-stability-auto` through the **same**
  selector + chain, it must reproduce **`binary_orbit_sb1_min` / 0.458**. A *different* honest tier is a
  **divergence to reconcile** (flag it — the two paths must agree on Sirius B), not two correct answers.
  Honest flag first; cross-path consistency is the check.
- **Q3 — `binary-orbit` scope → (a).** Raw-orbit reporter + an additive **degenerate marker** only; **no**
  chain, no `--star-mass-catalog`, no preferred-mass field. WB fixed the spec's internal tension (dropped
  `binary-orbit` from the chain-routed set).

---

## 3. Architecture locks (APP-owned; disclosed MSG 137 for veto)

- **L1 — `_extract_stability_elements` STAYS FROZEN / byte-identical.** The "shared fix" is a **pre-filter
  upstream of** `_extract`, not an edit to it. Hoist the CR-13.3 selector + flagger into a single shared
  home; `_extract`'s body is unchanged (its anchors stay byte-identical). **WB endorsed this (MSG 138) and
  is ADDING a CR-13 `--star` + `--component` exclusion byte-identical re-check to the CR-14 re-gate** — the
  exclusion path now delegates to the hoisted selector, so its output must be proven unchanged.
- **L2 — `stability_from_solutions` stays PURE.** Per-component chain resolution happens in the callers
  (`binary_stability_auto`, `report._multiplicity_data_star`), which pass preferred masses in. The chain
  routine is shared, not duplicated.
- **L3 — Kepler-III sma-consistency recompute (mirrors CR-13.3).** `sma_au` recomputed at the selected
  real-ratio period from the **preferred** masses so mass + sma + barycenter + Holman–Wiegert share one
  mass set (μ=0.457 for α Cen). Exact sma pinned by WB at re-gate.
- **L4 — enums verbatim + additive keys.** `binary_orbit_equal_split_unresolved` /
  `binary_orbit_sb1_min` reused verbatim; the `elements` block gains per-component
  `mass_provenance_a` / `mass_provenance_b` + a `resolution_notes` list. Additive; existing keys unchanged.
- **L5 — `multiplicity_basis` aligned to the selected solution** (no longer names the degenerate SB9 as
  the mass source; α Cen basis P=29650 → P≈29187). Visible string change on α Cen — disclosed.
- **L6 — `--star-mass-catalog` on `binary-stability-auto`** = same loader / REPLACE / loud-bad-path as
  `dossier` / `exclusion-system`.
- **L7 — single-source-of-truth for the mass chain AND the per-component identity derivation (M1).** Hoist
  the exclusion path's `_resolve_component_mass` + `_augment_designations` **+ `_component_candidate_ids` +
  the companion-identity derivation** into a neutral home (`core/stellar_mass.py`, which already owns
  `resolve_mass`) as public helpers; `exclusion_system` delegates (byte-identical — keep the
  `_component_candidate_ids` name, which `test_exclusion_system.py` calls directly; and
  guarded by the CR-11/CR-13 exclusion tests). This is what lets `binary`/`report`/`exclusion` all report
  the **same** per-component masses (the cross-path-consistency guarantee) from one code path. L7 rides
  under the **same** byte-identical-delegation guarantee WB endorsed for L1 (the CR-13 exclusion re-check
  covers it).

---

## 4. Implementation

### CR-14.1 — shared solution selection (real ratio over degenerate `q≈1.0`)

- **`core/binary.py`:** add a shared selector (hoisted from `exclusion_system._select_orbit_masses` +
  `_mass_flags` + the `_degenerate_sb2`/`_real_sb2`/`_abs_masses` helpers + `_Q_DEGEN_EPS`). It filters
  the degenerate placeholder (and, where a real SB2 exists, the competing tier-1 absolute-mass rows that
  would preempt it) **before** the frozen `_extract_stability_elements`, then returns the selected
  elements + per-component provenance flags. `_extract` itself is untouched (L1).
- **`stability_from_solutions`** (binary.py:628) calls the shared selector instead of `_extract` directly,
  and gains an optional `preferred_masses=(m1, m2, prov_a, prov_b, notes)` param (default `None` → today's
  orbit-derived behavior, so it stays PURE — L2). When the caller passes chain-resolved masses in, they
  override the orbit m1/m2, sma is recomputed via `a ∝ M_tot^⅓`, and Holman–Wiegert runs on the preferred
  set. Its `elements` block gains `mass_provenance_a`/`mass_provenance_b`/`resolution_notes` (L4).
- **`exclusion_system._select_orbit_masses`** becomes a thin delegate to the hoisted binary version
  (byte-identical; exclusion re-gate stays green).
- α Cen note (spec §CR-14.1): once CR-14.3 lands, α Cen masses come from the **catalog** tier, so CR-14.1's
  *mass* effect isn't observable on α Cen there — on α Cen it governs the **sma/period** (real-ratio
  P≈29187, not P=29650). Mass-selection is validated on `binary-orbit` ordering + a **non-seeded** binary.

### CR-14.2 — degenerate / SB1 flagging (verbatim enums)

- Reuse `binary_orbit_equal_split_unresolved` (degenerate `q≈1.0` or an invented `m2=m1` tier-3 fallback)
  and `binary_orbit_sb1_min` (SB1 sin i=1 lower bound), + a `resolution_notes` caution, wherever
  `binary-stability-auto` / the dossier `multiplicity` section emit a per-component mass. A mass superseded
  by a real-ratio solution (CR-14.1) or by a catalog/FLAME tier (CR-14.3) carries its ordinary provenance;
  the flag appears only when a degenerate/lower-bound value is genuinely the best available.
- The flag text/strings match CR-13.3's `_mass_flags` verbatim (now the shared function — same source).

### CR-14.3 — catalog-aware mass sourcing (GENERAL, all stars)

- **`core/stellar_mass.py`:** house the shared `resolve_component_mass(spec, catalog, allow_flame=True)`
  (hoisted from exclusion; chain = manual > catalog/seed > FLAME > orbit-ratio / MS L-inversion) +
  `augment_designations` (L7). `exclusion_system` delegates. **Airtight-consistency requirement (audit §9
  gap C):** the shared resolver — or a shared per-component *identity* helper beside it — must own the
  **designation derivation** too (resolved `main_id` → `designations` via `compute_simbad_lookup`, + the
  `A`/`B`-suffix augmentation via `augment_designations`), so `binary-stability-auto`, the dossier, and
  `exclusion-system` derive **identical** per-component designations → identical catalog hits → the same
  masses (#3). If each caller re-derived "star B" its own way, the catalog match could diverge.
- **`binary_stability_auto`** (binary.py:680): accepts a resolved/loaded catalog; for each component of the
  CR-14.1-selected solution, obtain the per-component designations via the shared identity helper (NOT by
  extending `binary_orbit`'s output — Q3=(a) keeps `binary-orbit` untouched; `binary_orbit`'s `identity`
  lacks the `designations` dict, so the **shared** identity helper (hoisted per M1/L7 — NOT a re-implemented
  "mirror") does the `compute_simbad_lookup` on the resolved `main_id` + `A`/`B` suffix, the SAME helper
  exclusion uses) and run the chain. The orbit still supplies the
  period; L3 recomputes sma from the preferred masses via the `a ∝ M_tot^⅓` scaling (no explicit period
  needed: `sma_pref = sma_orbit·(M_tot_pref/M_tot_orbit)^(1/3)`); Holman–Wiegert runs on
  {preferred m1, m2, recomputed sma, ecc}. Gains a `--star-mass-catalog` flag (L6).
- **`report._multiplicity_data_star`** (report.py:622): same per-component chain (full — Q1), threaded the
  dossier's existing `star_mass_catalog`. `stability_from_solutions` stays pure — the caller resolves +
  passes masses in (L2). **H1 guard (§10):** resolve both components through the shared full chain with
  `allow_flame=True` **independently** of `("regions" in requested)`; the regions-primary reuse is a pure
  optimization applied ONLY when `mass_block["mass_provenance"]` is a measured tier (manual/catalog/
  gaia_flame), never `MS_INVERSION`. `multiplicity_basis` built from the **selected** solution the shared
  selector returns (M3), not an independent `_pick_basis_solution` pass (L5).
- **`query.py`:** `cmd_binary_stability_auto` + the `binary-stability-auto` add_parser gain
  `--star-mass-catalog` (mirror the `dossier`/`exclusion-system` wiring at query.py:3242/4108).
  `cmd_binary_orbit` / the `binary-orbit` parser gain **nothing** under Q3=(a), WB-confirmed (marker only).
- **Cross-path consistency:** α Cen + Sirius per-component masses from `binary-stability-auto` /
  dossier-`multiplicity` now **equal** `exclusion-system`'s (all via the one chain).

### CR-14.4 — narrow the abs-mass-drop filter to degenerate-q only (the (b) improvement; Greg-approved)

The shared selector's pool filter **never discards a clean astrometric absolute-mass row** — it drops only
placeholders and lower-bounds. **REFINED during build (a fulfilled CR-13 test caught the naïve form):** the
old CR-13.3 filter dropped *all* abs-mass rows when a real SB2 exists
(`... or not (_degenerate_sb2(s) or _abs_masses(s))`), discarding clean astrometric masses too; but a naïve
"drop degenerate-q only" would let an **SB1 minimum** (sin i=1 lower bound) preempt a real SB2 ratio, which
is wrong (a real ratio beats a lower bound — pinned by `test_competing_tier1_sb1_does_not_preempt_real_sb2`).
The correct rule replaces `_abs_masses` with `_sb1_minimum` (an abs-mass row whose classifier `method ==
"spec-min"`):
```
if any(_real_sb2(s) for s in sols):
    pool = [s for s in sols if not (_degenerate_sb2(s) or _sb1_minimum(s))]
else:
    pool = [s for s in sols if not _degenerate_sb2(s)]
```
So: degenerate-`q≈1.0` is always dropped; an **SB1 minimum** is dropped when a real SB2 exists (a real ratio
wins — CR-13 preserved); a **clean astrometric** abs-mass row is **kept**, so `_extract` tier-1 (a real
measurement) wins over tier-2 (SB2-ratio × spectral-type primary). The ONLY behavior change vs CR-13.3 is the
real-SB2 + clean-astrometric-abs corner (now prefers the clean masses). WB told (MSG 145).

- **Applies to BOTH paths** (exclusion + stability) so they stay uniform / cross-path-consistent.
- **It is a behavior change to fulfilled CR-13.3.** The degenerate placeholder is still always removed (it is
  degenerate-SB2, so it's dropped regardless of whether it also carries abs masses — α Cen's `q=1.0` SB9 row
  cannot sneak back in via the abs-mass route). α Cen (real SB2 + no competing clean abs-mass) is **unchanged**
  by CR-14.4; only a star with a real-SB2 **and** a non-degenerate clean-abs-mass co-occurrence flips.
- **Re-gate (WB):** exclusion `--star`/`--component` anchors (α Cen / Sirius / Proxima / ε Eri) **UNCHANGED**
  under the (b) filter + a synthetic/real real-SB2-plus-clean-abs case now prefers the abs masses.

### `binary-orbit` (Q3=(a), WB-confirmed MSG 138)

- Add an additive `degenerate: true` (or `placeholder_q: true`) marker on a `q≈1.0`-no-spectroscopy
  solution in `binary_orbit`'s output. **No reorder** (order preserved), no chain, no new flag. Internal
  selection (CR-14.1) is what prevents a consumer from silently taking the degenerate one.

---

## 5. /code-review checkpoints

- **CP1 (high) — after CR-14.1 + the hoist/delegation (L1/L7).** Highest-risk part: it re-touches the
  fulfilled CR-13 `exclusion_system` and the shared root. Focus: `_extract` unchanged; exclusion delegation
  preserves the exact `mass_prov_a/mass_prov_b/notes` return keys (M2) and the filtered-empty→full **retry
  fallback** (M5); **exclusion anchors UNCHANGED under the CR-14.4 (b) filter** (α Cen/Sirius/Proxima/ε Eri
  — NOT strictly byte-identical code, but identical outputs on the anchors, since none carries a real-SB2 +
  clean-abs co-occurrence); **no import migrated to module top** during the closure restructure (the FLAME
  `from core import binary, catalog` MUST stay function-local — L1); the shared selector reproduces the
  exclusion behavior and the new stability-path behavior.
- **CP2 (high) — after CR-14.3.** Biggest behavior/contract change: the chain wiring into
  `binary_stability_auto` + the dossier, the pure-boundary preservation (L2), the added `--star-mass-catalog`
  flag, the sma-consistency recompute (L3), and cross-path consistency. Focus: no fabricated mass; provenance
  reports the actual tier; manual precedence unchanged; standalone `multiplicity` untouched.

---

## 6. Re-gate anchors (WB runs live, both WITH and WITHOUT the catalog)

- `binary-stability-auto --star "alpha Centauri" [--star-mass-catalog <cat>]` → A 1.079/`catalog`,
  B 0.909/`catalog`; sma/period from the real-ratio solution (P≈29187); stype/ptype recomputed from μ=0.457.
  Bare (seed) → same 1.079/0.909/`catalog`.
- `dossier --sections multiplicity --star "alpha Centauri" [--star-mass-catalog <cat>]` → 1.079/0.909,
  `mass_provenance catalog`, no degenerate SB9 as mass source.
- **Cross-path:** α Cen + Sirius masses from `binary-stability-auto` / dossier-`multiplicity` **equal**
  `exclusion-system`'s.
- `binary-orbit --star "alpha Centauri"` → degenerate `q=1.0` solution marked (Q3=(a)).
- `binary-stability-auto --star "Sirius"` (no seeded B) → Sirius B `0.458` / `binary_orbit_sb1_min` (Q2),
  **equal to** what `exclusion-system --star "Sirius"` reports (cross-path consistency; a different honest
  tier is a divergence to reconcile, not two answers).
- **Non-seeded binary (H1 guard + CR-14.3 #4 generality — added):** a binary whose primary is **not** in
  the catalog/seed but has a Gaia FLAME mass → the dossier `multiplicity` primary reads **`gaia_flame`**
  (NOT the L^0.2632 inversion), **equal** to what `binary-stability-auto` / `exclusion-system` report for it
  — proving the H1 guard resolves both consumers through the full chain and the paths don't diverge.
- **CR-13 exclusion byte-identical re-check (WB, added to CR-14 re-gate):** `exclusion-system --star` +
  `--component` for α Cen / Sirius / Proxima / ε Eri unchanged after the selector + chain are hoisted and
  exclusion delegates to them.
- **Regression:** standalone `multiplicity --star "alpha Centauri"` byte-identical; Sol / ε Eri unaffected;
  a clean-ratio binary unchanged through all consumers; the **CR-11/CR-13 exclusion suite stays green**
  (proves the delegation is byte-identical); ε Eri `binary-stability-auto` unchanged.

---

## 7. Test plan (offline unless gated)

- **`tests/test_binary.py` / `test_binary_stability_auto.py`** (offline, patch `binary_orbit`): the shared
  selector prefers a real ratio over a degenerate `q=1.0`; the sma-consistency recompute; the CR-14.2 flags
  on synthetic degenerate/SB1 solutions; the `--star-mass-catalog` chain (manual/catalog/orbit tiers with a
  mocked catalog) **plus a mocked-FLAME-injection case reading `gaia_flame`** (Reviewer A M1 / CR-14.3 #4);
  the **filtered-empty→full retry** fallback in the hoisted selector (M5); the pure `stability_from_solutions`
  still behaves when the caller passes masses in; the `binary-orbit` degenerate marker.
- **`tests/test_exclusion_system.py`** — unchanged; must stay green (byte-identical delegation guard;
  covers M2 return-keys, M5 retry, and `_component_candidate_ids` still callable after the hoist).
- **`tests/test_report.py`** — dossier `multiplicity` section chain + basis alignment (mocked).
- **`tests/test_query_*`** — arg-parse for the new `--star-mass-catalog` on `binary-stability-auto`.
- **Live-gated** (`SPACE_APP_RUN_LIVE=1`, `tests/test_query_*_live.py`): α Cen / Sirius anchors mirroring
  the re-gate targets.
- Docs: `docs/integration.md` CR-14 block; CLAUDE.md summary line; `PHASE_CR14_PLAN.md` →
  `completed_plans/` at close.

---

## 8. Out of scope / risks

- **Out of scope:** standalone `multiplicity` (regression-guarded byte-identical); `_extract_stability_elements`
  body (frozen); the existing α Cen/Sirius **cards** (they use deterministic `binary-stability` with
  hand-fed masses — CR-14 moves no card value; the card **regeneration** is WB's post-flip step).
- **Risk — circular import** from hoisting the chain into `stellar_mass.py` (it lazily imports
  `core.binary`/`core.catalog` for FLAME). Mitigated by keeping those imports function-local (as the
  exclusion copy already does). CP1 verifies.
- **Risk — added dossier network** (Q1). Mitigated: α Cen/Sirius resolve offline via seed; FLAME/inversion
  only for un-catalogued components. Final on WB's Q1 answer.
- **Risk — Sirius flag mismatch** (Q2). Mitigated: honest-tier flag, verified live at build; disclosed.

---

## 9. Self-audit against the code (APP, before plan-review)

Verified every load-bearing claim against the current source (line refs current as of this session):

- **Cited symbols exist as described:** `binary._extract_stability_elements` (582), `stability_from_solutions`
  (628), `binary_stability_auto` (680), `binary_orbit` (511), `gaia_source_id_from_designations` (203);
  `exclusion_system._select_orbit_masses` (487), `_mass_flags` (465), `_Q_DEGEN_EPS` (45),
  `_resolve_component_mass` (349), `_augment_designations` (454); `report._multiplicity_data_star` (622),
  `_pick_basis_solution` (609); `stellar_mass.resolve_mass` (69), `stellar_mass_tables.match_mass` /
  `load_mass_catalog` / `_SEED_CATALOG`; query.py `cmd_binary_stability_auto` (1269) + parser (3638),
  dossier `--star-mass-catalog` (4108).
- **No circular-import blocker (top risk — CLEARED).** `binary.py` module-top imports = `math`, `re`,
  `from core.shared import …` (no `stellar_mass`, no `exclusion_system`). `stellar_mass.py` module-top =
  `re`, `from core import shared`, `stellar_mass_tables` (no `binary`, no `catalog`). So L1 (selector →
  `binary.py`) and L7 (chain → `stellar_mass.py`) compose with **function-local** `from core import
  binary, catalog` for the FLAME tier (exactly as the exclusion copy already does) — no module-load cycle.
- **`_Q_DEGEN_EPS` (=1e-6) moves with the selector** (currently exclusion-local).
- **CR-2 regression-safe by construction:** `multiplicity_summary` (binary.py:329) references neither
  `_extract_stability_elements` nor `stability_from_solutions` — the hoist cannot touch it.
- **Enum strings are exact:** `binary_orbit_equal_split_unresolved` (473/481), `binary_orbit_sb1_min` (477);
  the SB1 detection keys on `"spec-min" in mass_basis` (`_extract` tier-1 `companion classifier (spec-min)`)
  — so Sirius B → `binary_orbit_sb1_min` iff its companion-classifier method is `spec-min` (Q2 live-verify).
- **Gap found + folded in (C):** `binary_orbit`'s `identity` carries `main_id`/`sp_type`/`gaia_source_id`
  but **not** the `designations` dict the catalog match needs → the shared resolver must own the
  designation derivation so all three paths derive identical designations → identical catalog hits (§4
  CR-14.3 amended; flagged for reviewers).
- **Minor (E):** `_degenerate_sb2`/`_real_sb2`/`_abs_masses` are local closures inside `_select_orbit_masses`
  — hoisting is a restructure into the shared home, not a lift-as-is.

Open live-only checks (deferred to build, not blocking the plan): exact α Cen post-fix `sma_au`
(WB pins at re-gate); Sirius B's actual orbit tier (Q2); that the real-ratio α Cen solutions are visual/WDS
(so `_pick_basis_solution` alignment must pass the *selected* solution, not re-run its spectroscopic-first
preference — L5).

---

## 10. Plan-review findings & resolutions (two independent agents)

Reviewer A (spec/re-gate coverage): **0 HIGH**. Reviewer B (feasibility/correctness): **1 HIGH + 5 MEDIUM
+ 4 LOW**. All folded below. Confirmed non-issues (Reviewer B): the pure `stability_from_solutions` +
`preferred_masses` param; the `sma_pref = sma_orbit·(M_tot_pref/M_tot_orbit)^⅓` recompute (byte-for-byte
what `exclusion._resolve_system_from_star` already does); the consumer list is complete
(`stability_from_solutions`, `binary_stability_auto`, `report._multiplicity_data_star`,
`exclusion._select_orbit_masses` — no GUI consumer; `multiplicity_summary` touches neither); the SB1
`spec-min` path is structurally sound; the report multiplicity planet-filter / is_multiple logic is
preserved (it sits *before* the stability call).

- **H1 (HIGH) — the Q1 regions-primary-reuse optimization reintroduces the cross-path split.** VERIFIED in
  code (report.py:1011 passes `("regions" in requested)` as the FLAME gate; :934 matches the catalog
  unconditionally → seeded anchors mask it). **RESOLVED:** §2 Q1 + §4 — resolve both components via the
  shared full chain (`allow_flame=True`) independently; reuse the regions primary only when its provenance
  is a measured tier; **add a non-seeded binary to the re-gate** (closes Reviewer A M1 too).
- **M1 — the per-component identity derivation must be HOISTED (one shared helper), not "mirrored."**
  RESOLVED: §4 CR-14.3 + L7 — hoist `_component_candidate_ids` + the companion-identity derivation into the
  shared home; exclusion delegates (keep the `_component_candidate_ids` name — `test_exclusion_system.py`
  calls it directly); forbid a parallel mirror in `binary_stability_auto`.
- **M2 — byte-identical delegation needs a reconciled selector return shape.** RESOLVED: the shared selector
  returns a **superset** — `m1_solar/m2_solar/sma_au/ecc/ecc_assumed/mass_basis` + `source/grade/a_basis`
  (needed by `stability_from_solutions`) + the provenance flags + the **selected `sol`** (M3). The exclusion
  delegate returns its **exact current keys** (`mass_prov_a/mass_prov_b/notes`, byte-identical — the CR-13
  tests assert them). The stability `elements` block uses `mass_provenance_a/_b` + `resolution_notes`;
  the per-component provenance **values** equal exclusion's (key names differ by path — resolves Reviewer A
  L-b).
- **M3 — L5 basis-alignment needs the selector to expose the picked solution.** RESOLVED: the selector
  returns the selected `sol` (M2 superset); `report` builds `multiplicity_basis` from it, not from an
  independent `_pick_basis_solution` pass.
- **M4 — the abs-mass-drop filter changes CR-3 for a real-SB2 + clean-astrometric co-occurrence.**
  **RESOLVED (WB MSG 141) → (a):** port the CR-13.3 `_select_orbit_masses` filter **as-is** (drop competing
  abs-mass rows when a real SB2 exists) — uniform, cross-path consistent, exclusion byte-identical — and
  **disclose** the CR-3 corner + add a regression anchor. The degraded corner (real SB2 + clean astrometric
  abs-mass + no catalog/FLAME mass) does **not** touch the card-regeneration set (α Cen/Sirius seeded;
  ε Eri/Sol single). **(b) is explicitly NOT in CR-14** — narrowing the drop is a behavior change to
  fulfilled CR-13.3 and, by the same logic that spun CR-14 out of CR-13's Q1, belongs in its own follow-up
  CR with its own re-gate; WB is flagging (b) to Greg as a candidate follow-up (a correctness nicety for a
  narrow corner, not required for anything current). **CR-14 builds (a).**
  **UPDATE (Greg, in-session): build (b) too** → folded in as **CR-14.4** (§4). The filter narrows to
  degenerate-q-only in both paths; exclusion is no longer strictly byte-identical (anchors-unchanged instead).
  WB informed (MSG 143) and re-gates the (b) exclusion change.
- **M5 — preserve the `_select_orbit_masses` filtered-empty→full retry.** RESOLVED: keep the retry verbatim
  in the hoisted selector; add a regression test for the filtered-empty-but-full-nonempty case.
- **L1 — circular-import guardrail:** keep the hoisted chain's `from core import binary, catalog`
  **function-local**; CP1 explicitly checks no imports migrated to module top during the closure restructure.
- **L2 — `binary_orbit` degenerate marker is additive/safe** (no test pins the solution-dict key set). Confirmed.
- **L3 — the chain has no `main_id` on `--ra/--dec/--source-id` input** (`_resolve_binary_identity` leaves
  `main_id=None`): graceful fallback to orbit masses (no catalog designations → no divergence); document the
  fallback.
- **L4 — keep the `test_sma_au <= 0` guard reachable BEFORE any catalog load** so the offline curated-exit-1
  test stays green (bad-path catalog load must not run before the guard).
- **Reviewer A M1 (FLAME/generality anchor + test)** — folded into H1's non-seeded re-gate anchor + a
  mocked-FLAME-injection test in §7.
- **Reviewer A L-a** — §4 wording "assumed Q3=(a)" → "Q3=(a), WB-confirmed MSG 138." (apply at finalize)
