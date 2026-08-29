# PHASE CR-13 — `exclusion-system --star` live-resolution robustness

**Status:** BUILT + GREEN (2026-08-29). CR-13.1/.2/.3 + C1→(A) implemented in `core/exclusion_system.py` (the only core
file changed). **Full offline suite: 3189 passed, 85 skipped, 0 failures** (+25 offline, +3 live-gated). CP1 `/code-review
high` done — 5 findings (F1 sdB fabricated-mass, F2 `--component` C1→A parity, F4 redundant FLAME, F5 note, F3 accepted) all
resolved. CP2 = clean self-audit. All re-gate targets reproduce (α Cen 49.0/45.7/{54,65}/62.5, Sirius 63.5/{66,74},
Proxima 20.48 cat / 21.57 bare, Sirius-B WD-null, SB1/degenerate flags). `docs/integration.md` CR-13 block staged; live
anchors in `test_query_exclusion_system_live.py`. **HELD: the WB build-complete channel post (WB is mid-task — Greg
2026-08-29); CLAUDE.md summary + plan→`completed_plans/` until re-gate GREEN + FULFILLED flip.**
**Spec:** `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR13-exclusion-system-star-resolution.md`
(channel MSG 124). **Data-half already seeded by WB** (Sirius B 1.018 · Bond 2017; Proxima 0.1221 · Kervella 2017 /
Mann 2015) in `stellar-mass-catalog.json` — no APP data round.

**Scope guardrail:** additive to the CR-11.3 `exclusion-system` contract. The `--component` deterministic core, the frozen
single-body `exclusion-boundary` generator, the union/merge composition, and the barycenter model are **CORRECT and
UNTOUCHED** — WB re-confirmed every pinned card value reproduces exactly through `--component` this session. CR-13 hardens
**only** the `--star` auto-resolve layer (`_resolve_system_from_star` and the per-component mass chain feeding it).

---

## 1. Defect diagnosis (mapped to the current code)

All four live-reproduced defects trace to `core/exclusion_system.py::_resolve_system_from_star` (lines ~407–466) and the
mass chain it calls.

| # | Symptom | Root cause (line) |
|---|---|---|
| D1 | `--star "Sirius B"` → members `"* alf CMa B"` + `"Sirius B B"`, placeholder 1.0, WD mislabeled primary | Input names a **secondary**; `binary_orbit("Sirius B")` still returns the AB orbit so `elements` ≠ None → binary branch composes garbage. Companion id = `f"{star} B"` = `"Sirius B B"` (L460); `f"{star} B"` SIMBAD lookup = `"Sirius B B"` (L441); primary = `sl.main_id` = the WD (L456). |
| D2 | `--star "Proxima Centauri"` → crash "could not resolve a mass … none carries the masses + period …" | Wide bond → `_extract_stability_elements` returns `elements=None` (single-body branch, L427). But that branch needs `prim_mass`, and the `--star` path **passes no `lum`** to `_resolve_component_mass` (L424–426), so inversion can't fire; pre-seed no catalog row → `prim_mass=None` → L430 error. |
| D3 | `--star "alpha Centauri" --star-mass-catalog` → both 1.02 M☉ (47.88/47.88) | Primary `main_id="* alf Cen"` (system id) ≠ catalog key `"* alf Cen A"` → catalog miss (L352/`match_mass`). **Companion never runs the mass chain at all** — built directly from `elements["m2_solar"]`/`binary_orbit_m2` (L460–462). |
| D4 | `--star "alpha Centauri"` picks degenerate `q=1.0`; `--star "Sirius"` → B = 0.458 SB1-min, silent | `_extract_stability_elements` returns the **first** qualifying solution (L603–619); degenerate `q≈1.0` and SB1-minimum masses are surfaced with no flag. |

**Structural keystone:** the `--star` companion is built inline (L460) and **never** passes through `_resolve_component_mass`
— so the catalog/FLAME/inversion chain currently reaches the primary only. CR-13.2 = route **both** components through the
chain. Compose (`compose_exclusion_system`) does **not** re-resolve masses (L221–228 reads `c["mass_solar"]` as given), so
the fix must land in `_resolve_system_from_star`, not compose.

---

## 2. Resolved decisions (WB MSG 126) + APP-locked decisions

**WB answers (MSG 126 — settled, plan is written to these):**

- **Q1 → Option B.** Keep `binary._extract_stability_elements` **FROZEN**; apply the real-ratio preference +
  degenerate/SB1 flags **only in the `exclusion-system --star` resolver**. Strictly additive, zero blast radius. Option A
  is explicitly OFF — changing the shared function is a CR-2/CR-3/CR-10.5 behavior change outside CR-13 scope. The same
  degenerate pick latent in `binary-stability-auto`/`multiplicity`/CR-10.5 is a **WB-tracked candidate SEPARATE CR** (not
  fixed here; those three stay as-is by design).
- **Q2 → wire the L-inversion; TWO-target gate.** Feed the `--star` single-body chain's inversion tier with
  `regions.compute_star_system_regions_from_simbad(sl)["bcLuminosity"]` (the same bolometric derivation the dossier
  inverts to 0.139 for Proxima), passed as the chain's `luminosity_lsun`. Result:
  **no-catalog Proxima → M=0.139 → r_ex 21.5725** (deterministic inversion-path self-consistency pin) and
  **with-catalog → M=0.1221 → r_ex 20.4824** (`mass_provenance:"catalog"`, the authoritative value). Both at α=0.4,
  calibration 47.5. (21.5725 is the tool's own dossier-flagged inversion — a self-consistency gate, not the "correct"
  value; the card will carry 20.48.) *(An earlier draft wrongly claimed `regions` returns no `bcLuminosity` key — both
  plan reviewers confirmed it does, `regions.py:247`; the key is used directly, no back-compute, no `regions.py` change.)*
- **Q3 → verbatim strings + flag tier-3.** Adopt `binary_orbit_equal_split_unresolved` and `binary_orbit_sb1_min`
  verbatim, each with a `resolution_notes` caution. The equal-split flag covers **both** the degenerate `q≈1.0` orbit
  **and** the tier-3 no-secondary `m2=m1` fallback; the note should name **which** degenerate path produced it (q=1.0
  orbit vs no-secondary fallback) for provenance honesty. WB has no code switching on these strings (cards read
  `mass_provenance` human-facing) — requirement is only that they're stable + self-descriptive; additive is safe.

**APP-locked (MSG 125; WB confirmed all 4, MSG 126):**
1. `--star "Sirius B"` → **single WD component** (mass 1.018 catalog, out-of-domain WD guard, `r_ex_au: null`), not the
   parent system.
2. Component-detection: input resolving to a **secondary** (`main_id` = space + non-`A` component letter, and/or off-MS
   otype) → single-body path; a wide-member (`elements is None`) → single-body (already the code shape). **WB watch
   (MSG 126):** a **primary**-named input (`"Sirius A"`, `"alpha Cen A"` → `main_id` ending `" A"`) must NOT be caught by
   the secondary detector (the regex `\s[B-Z]$` excludes `A` by construction) — it resolves as single-component-A or a
   composed system. Regression anchor added (§9).
3. Single-body `--star` output = the `exclusion-system` `n_components:1` shape (not raw `exclusion-boundary` JSON).
4. Companion routed through `_resolve_component_mass` with per-component identity from the system id + component suffix
   (`"* alf Cen"` → also `"* alf Cen A"/"B"`) + a light SIMBAD component lookup for its alias set.

---

## 3. Design — CR-13.1 (component / wide-member resolution)

**New pure helper (offline-testable), `core/exclusion_system.py`:**
- `_is_secondary_component(main_id, otype=None, sp_type=None) -> bool` — True when `main_id` ends in a space + a single
  uppercase component letter other than `A` (regex `r"\s[B-Z]$"`), OR the otype/sp_type marks it off-MS (WD/BD). Pure
  string logic → unit-testable with no network.

**`_resolve_system_from_star` control flow (rewritten):**
1. `sl = compute_simbad_lookup(star)`.
2. **If `_is_secondary_component(sl.main_id, sl.otype, sl.sp_type)`** → single-body path on **that component's own
   identity** (its `main_id`, sp_type, designations) via the CR-13.2 mass chain; off-MS class tag flows to the domain
   guard. **Never** compose. Emit `n_components:1`. (Fixes D1 — "Sirius B" → the single WD.)
3. Else run `binary_orbit(star)` + `_extract_stability_elements`:
   - `elements is None` (single star OR wide-bond member) → single-body path on the resolved primary, **now with a
     working mass** (CR-13.2 chain incl. the L-inversion, Q2). (Fixes D2 — Proxima single-body.)
   - **⚑ Plan-review m1 defensive guard:** treat a resolved orbit as a **wide member → single body** when its `sma_au`
     exceeds a wide threshold (e.g. ≫ a few hundred AU) **or** `mass_basis` is the tier-3 equal-mass fallback with a huge
     `sma_au`. Proxima crashes *today* because `_extract` returns `None` for its ~13,000 AU bond, but
     `m1_from_spectral_type` always returns a value, so a future catalogue that gave that bond a period would make tier-3
     fire and compose a spurious 2-body system. This one-line guard closes the gap for other wide members WB won't
     re-gate.
   - `elements` present (and not wide) → the multi-component branch, but with **both** components routed through the mass
     chain (CR-13.2) and the real-ratio-preferring selection (CR-13.3).
4. **No `f"{star} B"` string-building.** The companion's identity comes from the system `main_id` + " B" suffix
   normalization (`"* alf CMa"` → `"* alf CMa B"`), never `f"{raw_input} B"` — so `"Sirius B"` can't become `"Sirius B B"`.
   (Belt-and-suspenders on D1: even if a secondary slips past step 2, the suffix normalizer dedupes a trailing " B".)
5. **Unresolvable → error names the resolved target + remedy:** `f"could not resolve '{star}' (SIMBAD: {main_id}) to a
   system or a single body — pass the system name (e.g. 'Sirius') or use --component"`. (Criterion 3.)

**Single-body output:** the existing `compose_exclusion_system([one_component], …)` already yields the `n_components:1`
form (L150 barycenter = the star). Off-MS single body → `r_ex_au:null` + `class_note` via the existing `_component_domain`
guard. No compose change.

---

## 4. Design — CR-13.2 (per-component mass provenance in `--star`)

**Route the companion through the chain.** Replace the inline companion build (L460–462) with a
`_resolve_component_mass({name, sp_type, designations, class}, catalog)` call, exactly as the primary already does — so
`manual → catalog → FLAME → inversion/orbit` fires for B too. When the chain yields nothing measured, **fall back to the
binary-orbit-derived mass with the CR-13.3 provenance flag** (not a silent clean value).

**Per-component catalog key-matching (the α Cen fix).** The catalog match must try, per component:
- the component's resolved `main_id`,
- its `designations` values,
- **the per-component designation derived from the system id** (`"* alf Cen"` + `" A"`/`" B"` → `"* alf Cen A"`). ⚑
  **Plan-review M4:** `_component_candidate_ids` must **strip any existing trailing `" [A-Z]"` from the base `main_id`
  before appending** — a primary-named input can resolve to a `main_id` already ending in a letter (`"* alf Cen A"`), and
  a naive append yields `"* alf Cen A B"`. Strip → normalize to the bare system id → append the suffix. (Unit test in §8.)
- the alias set from a **light SIMBAD lookup of that component id** (yields `HD 128620`/`GJ 559 A` for α Cen A, matching
  the catalog row's aliases).

Implementation options for the reviewers to weigh:
- **(4a)** Add candidate ids to the `spec["designations"]` passed into `_resolve_component_mass` (a synthetic
  `{"_component_id": "* alf Cen A", …}` merged with real designations) so the existing `match_mass` (which already scans
  `main_id` + all `designations` values vs row `main_id` + `aliases`) hits with **no `match_mass` change**. Cleanest.
- **(4b)** Extend `match_mass` with an optional `extra_ids` set. More explicit, touches a CR-11.2 function.

**Default = (4a)** — no CR-11.2 function change; the whole fix stays inside the `--star` resolver. The light per-component
SIMBAD lookup is best-effort (wrapped, failure → skip that alias source, never fatal), mirroring the existing companion
otype/sp_type lookup.

**Bolometric-L for the single-body inversion (Q2 wiring).** `compute_star_system_regions_from_simbad` returns
`"bcLuminosity"` directly (`regions.py:247`) and returns `{"error": …}` for a non-OBAFGKM sp_type. So, in the single-body
branch:
1. `reg = regions.compute_star_system_regions_from_simbad(sl)`; if `"error" in reg` (WD/BD/no V/no plx) → skip the L
   tier (an off-MS single body needs no inversion; its domain guard fires on class — **but see C1 below**: a lone WD then
   has no mass source at all).
2. Else set `spec["luminosity_lsun"] = reg["bcLuminosity"]` — the chain then computes `luminosity_lsun**0.2632 =
   stellarMass = 0.139` for Proxima. (Directly reuse the key; **no back-compute, no `0.2632` re-hardcode**.)
3. `_resolve_component_mass(spec, catalog)` runs the **full chain unchanged** — catalog wins when present (Proxima
   0.1221 → `catalog`), inversion (0.139 → `ms_luminosity_inversion`) when not. Precedence preserved; **no chain
   duplication, no `regions.py` change** (read-only).

**Lone out-of-domain body — C1 → Option (A) compose-tolerance (WB MSG 128, Greg MSG 129).** A directly-named WD/BD/rogue/
giant single body (e.g. bare `--star "Sirius B"`) may reach `_resolve_component_mass` with **no** resolvable mass (no
catalog flag, no FLAME for a WD, inversion skipped on the non-MS sp_type). Today `compose_exclusion_system` errors on its
`mass_solar>0` guard (`exclusion_system.py:224–225`). Fix: **when the system has exactly one component AND it is
out-of-domain AND its mass is unresolved**, skip that guard and emit `r_ex_au:null` + `class_note` +
`mass_provenance:"unresolved_out_of_domain"` + a `resolution_notes` entry — never an error, never an invented mass. The
mass is numerically inert here (single-component barycenter = the star, `in_dom` empty → no point-mass). This is the
**only** change to `compose_exclusion_system`; it is **additive** (relaxes a guard for a currently-erroring input, moves
no existing input's behavior) and WB-approved as consistent with "core untouched" (§11).

---

## 5. Design — CR-13.3 (binary-orbit mass quality) — Option B, scoped to `core/exclusion_system.py`

`binary._extract_stability_elements` stays **FROZEN** (Q1→B). A new pure selector in `exclusion_system.py`:
`_select_orbit_masses(solutions, ident) -> {m1, m2, sma_au, ecc, mass_prov_a, mass_prov_b, notes}` that:
1. **Prefers a real-ratio solution by FILTERING, not reordering** (plan-review M2 — reorder is insufficient). Both
   reviewers confirmed the tier crossing: `companion_mass_from_sb1` / `companion_mass_from_thiele_innes` populate **both**
   `m1_solar` and `m2_solar`, so an SB1/astrometric solution satisfies `_extract` **tier 1**, which is scanned before the
   SB2-`mass_ratio_q` **tier 2** — so a mere reorder can never demote a tier-1 SB1-min below a tier-2 real ratio. The
   selector therefore **drops** degenerate solutions (a `mass_ratio_q` ≈ 1.0 within an epsilon with no supporting
   spectroscopy; and, where a resolved SB2 ratio exists, the competing SB1 tier-1 rows) from the list **before** calling
   the frozen `binary._extract_stability_elements`. (For α Cen *today* the pick is already tier-2, so this is defensive as
   well as correct; the general mechanism must not rely on that.)
2. **Tags the result — recoverable from `_extract`'s RETURN, no refactor** (plan-review m5). Read
   `elements["mass_basis"]`: a `"…equal-mass assumption…"` basis → tier-3 no-secondary fallback; for a tier-2 pick,
   `elements["m2_solar"]/elements["m1_solar"]` **is** `q` exactly (`m2 = m1_sp·q`), so `≈1.0` ⇒ degenerate. Either →
   `binary_orbit_equal_split_unresolved` + a `resolution_notes` entry **naming which path** ("degenerate q=1.0 orbit
   solution" vs "no secondary mass — equal-mass assumption"). SB1 minimum → the companion's
   `caveat == "SB1 minimum mass (sin i = 1 lower bound)…"` (`binary.py:152`) is the reliable signal →
   `binary_orbit_sb1_min` + note. Otherwise `binary_orbit_m1`/`_m2`. The frozen function needs **no** change and needs
   **no** solution-identity match-back — every flag is derivable from what it already returns (+ the pre-filter the
   selector applied). **Fully offline-testable** with synthetic `solutions` lists (no network).

**Enum additivity:** the two new `mass_provenance` values are additive — no existing value changes meaning; WB has no code
switching on them (cards read `mass_provenance` human-facing), so the only requirement is stable + self-descriptive
strings (MSG 126 Q3a).

---

## 6. Refactor-for-testability seams (so the LIVE path has offline coverage)

`--star` is a live path; the pure decision logic is extracted so `pytest -q` covers it with no network (mirrors binary's
offline classifier tests + the live-gated anchors):
- `_is_secondary_component(...)` — string/otype logic.
- `_component_candidate_ids(system_main_id, suffix)` — the per-component id/alias derivation for 4a.
- `_select_orbit_masses(solutions, ident)` — solution preference + provenance flags, fed synthetic `solutions`.
- single-body composition already covered by the offline `--component` tests (a WD/M-dwarf single component).

---

## 7. Files touched

- **`core/exclusion_system.py`** — the whole change (resolver rewrite, 3 new pure helpers, companion-through-the-chain,
  L-inversion wiring, + the C1→A lone-out-of-domain compose-tolerance in `compose_exclusion_system`). The **only** core
  file changed.
- **`core/binary.py`** — NOT changed (Q1→B keeps `_extract_stability_elements` frozen).
- **`tests/test_exclusion_system.py`** — offline unit tests for the 3 new helpers + single-body WD/M-dwarf composition.
- **`tests/test_query_exclusion_system_live.py`** — live-gated `--star` anchors (α Cen / Sirius / Sirius B / Proxima),
  `SPACE_APP_RUN_LIVE=1`.
- **`docs/integration.md`** — CR-13 block: new `mass_provenance` enum values, `resolution_notes` additions, the `--star`
  single-body behavior, the "either single component or parent system for a named secondary" note.
- **CLAUDE.md** — CR-13 summary line (after re-gate GREEN).

No change to `--component`, `compose_exclusion_system`, the frozen generator, `binary.py`, `regions.py`, or
`stellar_mass*.py` (approach 4a / Option B). `regions.py` is *read* (`stellarMass`, back-computed to `luminosity_lsun`),
not modified.

---

## 8. Test plan

**Offline (`pytest -q`, no network):**
- `_is_secondary_component`: `"* alf CMa B"`→True, `"* alf Cen"`→False, `"* alf Cen A"`→False, WD otype→True, `"Sol"`→False.
- `_component_candidate_ids("* alf Cen","B")` ⊇ `{"* alf Cen B"}`; `"A"` ⊇ `{"* alf Cen A"}`; **M4:**
  `_component_candidate_ids("* alf Cen A","B")` ⊇ `{"* alf Cen B"}` (a letter-bearing base id is stripped first, **not**
  `"* alf Cen A B"`).
- `_select_orbit_masses`: synthetic solutions where a degenerate `q=1.0` and a real `q≈0.84` are both tier-2 → picks the
  real ratio; **a tier-1 SB1 (m1+m2 set) alongside a tier-2 real ratio → the SB1 is FILTERED so the real ratio wins**
  (M2 regression); all-`q=1.0` → `binary_orbit_equal_split_unresolved` + note; SB1-caveat companion →
  `binary_orbit_sb1_min` + note; tier-3 equal-mass basis → `binary_orbit_equal_split_unresolved` + "no secondary mass" note.
- Single-body compose: one WD component → `r_ex_au:null` + WD `class_note`; one M-dwarf at M=0.1221 → r_ex ≈ 20.482
  (already the `--component` anchor).
- Catalog key-match via 4a: a mock catalog keyed `"* alf Cen A"` matched from a synthetic component whose designations
  include `"* alf Cen A"`.
- **m3 — mocked integration test of `_resolve_system_from_star`** (mock `compute_simbad_lookup` / `binary_orbit` /
  `regions.compute_star_system_regions_from_simbad`): (a) `elements is None` single-body sets `luminosity_lsun =
  bcLuminosity` and resolves the inversion mass; (b) the binary branch routes the **companion** through
  `_resolve_component_mass` with the 4a candidate ids; (c) the secondary-named branch → single component. This covers the
  branch-selection + L-fetch + companion-through-chain wiring that would otherwise be live-only.
- **m7 — Proxima both id forms:** `main_id="NAME Proxima Centauri"` (→ wide-member/`elements is None` branch) **and**
  `main_id="* alf Cen C"` (→ secondary-detector branch) both resolve to a single M-dwarf body at the same mass.

**Live-gated (`SPACE_APP_RUN_LIVE=1`, `test_query_exclusion_system_live.py`):** the re-gate cases in §9 (the four star
anchors — α Cen / Sirius / Sirius B / Proxima — each with + without catalog where §9 lists both) + the primary-named
regression anchors. **m4 — verify the existing bare `--star "Sirius"` live anchor stays green:** it asserts r_ex>55 /
WD-null / merged / 2 members and does **not** assert `mass_provenance`, so B's `binary_orbit_m2 → binary_orbit_sb1_min`
flag change (CR-13.3) leaves it green; confirm at build.

---

## 9. Re-gate criteria (WB runs `query.py` on the sister venv, both `--star` and `--component`)

| Case | Expected |
|---|---|
| `--star "alpha Centauri" --alpha 0.4 --star-mass-catalog <cat>` | A 1.079/catalog/**49.0**; B 0.909/catalog/**45.7**; merged **{54,65}**; **minor axis ≈ 49**; point-mass **62.5** |
| `--star "Sirius" --alpha 0.4 --star-mass-catalog <cat>` | A 2.063/catalog/**63.5**; B **1.018** from catalog (WD guard, r_ex null); merged **{66,74}** |
| `--star "Sirius B" --alpha 0.4` (**bare**) | single WD component: `r_ex_au:null`, `class_note:"white dwarf"`, **`mass_provenance:"unresolved_out_of_domain"`** + note, **no error**, never `"Sirius B B"`/placeholder (C1→A) |
| `--star "Sirius B" --alpha 0.4 --star-mass-catalog <cat>` | single WD component: `r_ex_au:null`, mass **1.018**/`catalog`, WD guard (C1→A) |
| `--star "Proxima Centauri" --alpha 0.4 --star-mass-catalog <cat>` | single-body, 0.1221/`catalog`/**r_ex 20.4824**, no error |
| `--star "Proxima Centauri" --alpha 0.4` (**no** catalog) | single-body, inverted **0.139**/`ms_luminosity_inversion`/**r_ex 21.5725** (deterministic inversion-path pin — WB MSG 126 Q2), no error |
| `--star "alpha Centauri" --alpha 0.4` (no catalog) | not a silent 1.02/1.02 — real-ratio solution (A≈1.08/B≈0.91) **or** equal-split masses flagged `binary_orbit_equal_split_unresolved` + note |
| `--star "Sirius" --alpha 0.4` (no B row) | B's 0.458 flagged `binary_orbit_sb1_min` + note (inert but present) |

*(All r_ex pins at α=0.4, calibration 47.5 = the `exclusion-boundary` default `_KUIPER_EDGE_AU`; 20.4824 / 21.5725
reconfirmed live by WB on the sister venv, MSG 126.)*

**Regression anchors (must not move):** `--star "Sol"` / `--star "epsilon Eridani"` (single MS) unchanged;
**`--star "Sirius A"` / `--star "alpha Cen A"` (primary-named) resolve sanely — NOT caught by the secondary detector**
(WB MSG 126 watch); all `--component` α Cen / Sirius / Proxima reference values unchanged; `>1.38 M☉` WD refuse +
out-of-domain guards intact.

---

## 10. `/code-review` checkpoints

- **CP1 — after CR-13.1 + CR-13.2** (`/code-review high`). The riskiest surface: identity resolution of
  component/wide-member names, the per-component catalog key-matching, the L-inversion wiring, the network-touching
  best-effort lookups. Review target = the `core/exclusion_system.py` diff.
- **CP2 — final `/code-review high` over the whole CR-13 diff** (includes CR-13.3 — the scoped selector is small +
  offline-tested, so it folds in here rather than a standalone checkpoint) before handoff. The CR-11 precedent: a
  full-diff high pass caught a 2-body geometry bug, an sdB/sdO guard gap, a point-mass edge, and a double catalog scan.

*(Two checkpoints, not three: Q1→B removed the shared-`binary.py` change that would have needed its own blast-radius
review.)*

---

## 11. Blast radius / disclosure

- **Option B / 4a (chosen):** change is confined to `core/exclusion_system.py::_resolve_system_from_star` + new pure
  helpers. **No fulfilled-CR behavior change.** `--star` had **no production consumer** depending on the current (broken)
  output — the two cards use `--component`.
- **One approved additive touch to `compose_exclusion_system`** (C1→A, WB MSG 128 / Greg MSG 129): a lone out-of-domain
  component with an unresolved mass skips the `mass_solar>0` guard (→ `r_ex_au:null` + `unresolved_out_of_domain`) instead
  of erroring. It changes **no existing computation** and moves **no existing input's** behavior (the input currently
  errors), so it stays consistent with "the union/merge composition is untouched"; disclosed, not silent. New additive
  enum value `mass_provenance:"unresolved_out_of_domain"`.
- **The degenerate-pick latent in the shared `binary._extract_stability_elements`** (affecting `binary-orbit`/
  `multiplicity`/`binary-stability-auto`/CR-10.5 dossier) is deliberately **NOT** touched here — it's a WB-tracked
  candidate SEPARATE CR (MSG 126 Q1). Those three keep their current behavior by design.
- **New `mass_provenance` enum values** are additive; WB confirmed no code switches on them (MSG 126 Q3a).
- **No card *value* changes are APP's job** — Proxima's 21.6→~20.5 card edit + the `⚠ re-verify-live` flag-clears are WB
  post-flip tasks.

---

## 12. Build order

1. CR-13.1 resolver rewrite + `_is_secondary_component` + single-body routing.
2. CR-13.2 companion-through-the-chain + 4a per-component key-matching + Q2 L-inversion wiring (back-compute).
3. **CP1** (`/code-review high` — resolver + mass chain, the identity/network-risk surface).
4. CR-13.3 `_select_orbit_masses` + provenance flags.
5. Offline tests green (`venv/bin/python -m pytest tests/test_exclusion_system.py -q`), then full `pytest -q`.
6. **CP2** (final `/code-review high` over the whole CR-13 diff).
7. Post APP-built MSG → WB re-gates on the sister venv (both `--star` and `--component`) → Greg signs one FULFILLED flip.

**Nothing here executes until Greg gives the build go-ahead** (WB has answered Q1/Q2/Q3 — MSG 126).

---

## 13. Plan-review outcome (2 independent agents, 2026-08-29)

Two agents reviewed the finalized plan — one code-grounded (does the plan's read of the code hold?), one
contract-compliance (does it satisfy every CR-13.1/.2/.3 criterion + re-gate + WB MSG 126?). Both verdicts:
**yes-with-fixes**. They converged on one CRITICAL (C1, → WB) and folded-in Moderates/Minors:

- **C1 (CRITICAL — RESOLVED → Option (A), WB MSG 128; Greg-ratified MSG 129):** a bare `--star "Sirius B"` (no
  `--star-mass-catalog`) — a lone WD — has **no mass source**: manual none, catalog none (no flag), Gaia FLAME does not
  mass WDs, and the Q2 L-inversion is skipped because `regions` `{"error"}`s on a WD `sp_type` (`DA2`).
  `compose_exclusion_system`'s `mass_solar>0` guard would error → contradicts spec criterion 2 / §9 row 3. The mass is
  **numerically inert** for a lone out-of-domain body (r_ex null by the class guard, barycenter = the star, no
  point-mass sum). **Fix (A), approved:** a small **additive compose-tolerance** — when the single component is
  out-of-domain (WD/BD/rogue/giant) **and** its mass is unresolved, skip the `mass_solar>0` guard and emit
  `r_ex_au:null` + `class_note` + **`mass_provenance:"unresolved_out_of_domain"`** + a note, instead of erroring. This
  changes **no existing computation** (r_ex math, union/merge, barycenter, point-mass all untouched) — it only relaxes a
  guard for an input that **currently errors**, so no existing input's behavior moves (WB MSG 128 confirmed this stays
  consistent with "core untouched"; disclosed additive change, see §7/§11). Honours locked decision #1 on **both** paths:
  bare → r_ex null + `unresolved_out_of_domain`; with `--star-mass-catalog` → r_ex null + 1.018/`catalog`. See §9 row 3.
- **M1/M3 (FIXED):** the plan's "audit correction" was itself wrong — `bcLuminosity` **is** returned (`regions.py:247`).
  Reverted to `spec["luminosity_lsun"] = reg["bcLuminosity"]` (direct; no back-compute, no `0.2632` re-hardcode, no
  `regions.py` change). §2/§4 corrected.
- **M2 (FIXED):** CR-13.3 must **filter** degenerate/competing-SB1 solutions before the frozen `_extract` (SB1/astrometric
  solutions hit tier-1 ahead of tier-2, so a reorder can't cross the tier boundary). §5 rewritten; flags shown recoverable
  from `_extract`'s return (`mass_basis` + the tier-2 m2/m1 ratio + the SB1 companion `caveat`) with **no** function
  change and **no** solution match-back.
- **M4 (FIXED):** `_component_candidate_ids` strips an existing trailing `" [A-Z]"` before appending the suffix (else
  `"* alf Cen A"+" B" → "* alf Cen A B"`). §4 + §8 test.
- **m1 (FIXED):** defensive wide-`sma_au` guard so a future period on a wide bond can't compose a spurious 2-body. §3.
- **m2 (FIXED):** added `minor axis ≈ 49` to §9 row 1.
- **m3 (FIXED):** added a mocked offline integration test of `_resolve_system_from_star` (branch selection + L-fetch +
  companion-through-chain). §8.
- **m4 (FIXED):** noted the existing bare `--star "Sirius"` live anchor stays green (no `mass_provenance` assertion). §8.
- **m7 (FIXED):** test both Proxima `main_id` forms (`"NAME Proxima Centauri"` / `"* alf Cen C"`). §8.

**Verified-correct by both reviewers (no change needed):** 4a designation-injection key-match (no `match_mass` change);
the L→mass round-trip + catalog precedence; the `\s[B-Z]$` regex on all the core cases; single-file blast radius;
faithful execution of MSG 126 (Q1→B / Q2→two-target / Q3→verbatim + tier-3 flag); the WB primary-named watch honoured;
all re-gate values consistent with the contract's deterministic reference.

**Gate to build:** C1 answered → Option (A) (WB MSG 128, Greg-ratified MSG 129). Plan is review-clean and build-ready.
Awaiting Greg's **direct in-session** build go-ahead (WB's MSG 129 relays it, but the standing rule is to wait for Greg's
own word here).
