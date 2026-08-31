# PHASE CR-16 — letterless-primary component resolution (secondary-named query resolves via the primary)

**Status: FULFILLED 2026-08-30 — WB independent whole-battery re-gate GREEN (MSG 187) + Greg-signed flip (MSG 188); committed + pushed to `main`.** WB rulings received + Greg-signed (coordination channel **MSG 183 + 185**); build-go given in-session. Built 2026-08-30: changes A/B/C + CP1/CP3 `/code-review` + 11 `Cr16*` tests; full offline suite **3250 passed / 88 skipped / 0 failures**; all 7 acceptance targets live-verified on this box and independently WB-re-gated on the sister venv (every frozen CR-13/CR-14 anchor byte-identical by construction). Coordination MSG 181–188. CR-16 is the tool-level closure for the letterless-primary gap CR-15 Option A parked. **Not additive** — it corrects `binary-stability-auto`/`binary-orbit`/`dossier` for a secondary-named query of a letterless-primary system, and the WB re-gate is the **whole CR-13 + CR-14 battery byte-identical**.

Contract: `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR16-letterless-primary-component-resolution.md` (+ `cr16-handoff-kit.md`). Channel MSG 181 (reopen) → 182 (APP Q&A) → **183 (WB rulings)**.

---

## 1. The verified defect (live-reproduced on this box, `git 363aadb`, SIMBAD+SB9 up)

Both `"Sirius"` and `"Sirius B"` resolve the **same** SB9 orbit (P=18276.7 d, e=0.59, mass-function f=0.0137786). The entire divergence is the primary mass fed to the SB1 solve `m2 = solve(f, m1)`, where `m1 = m1_from_spectral_type(ident.sp_type)`:

| query | ident.sp_type | m1 source | m1 / m2 | stype / ptype |
|---|---|---|---|---|
| `binary-stability-auto "Sirius"` | A0mA1Va | 2.18 (sp) → 2.063 (cat override) | 2.063 / **0.4577** | 2.3136 / 74.142 |
| `binary-stability-auto "Sirius B"` | **DA1.9** (WD → default 1.0) | 1.0 | **1.0 / 0.283** | 1.788 / 59.31 |
| `… "Sirius" --star-mass-catalog` | A0mA1Va | catalog | 2.063 / 1.018 | — |
| `… "Sirius B" --star-mass-catalog` | DA1.9 | catalog (WRONG slot) | **1.018 / 1.018** | — |
| `binary-orbit "Sirius B"` (raw) | DA1.9 | 1.0 | **1.0 / 0.283** | — |

Two independent failure mechanisms, both rooted in the **queried secondary's identity driving the mass/orbit derivation**:

- **Orbit m1/m2 (no-catalog):** the SB1 companion mass in `binary_orbit` uses `m1_from_spectral_type(ident.sp_type)`. Sirius B's `DA1.9` (white dwarf — no OBAFGKM class) → the `_DEFAULT_M1_MSUN = 1.0` fallback → m2 = solve(f, 1.0) = 0.283. The primary's `A0mA1Va` → 2.18 → m2 = solve(f, 2.18) = 0.4577. `component_candidate_ids`/`match_mass` **never touch this** (it is baked into the solution at `binary_orbit` time). Recomputing m2 at the *catalog* 2.063 gives 0.4422, ≠ 0.4577 — the 0.4577 lives at the *spectral-type* m1=2.18, confirming the fix must be at the orbit/identity layer, not the catalog layer.
- **Catalog slot A (with/without catalog):** `resolve_binary_components` builds slot A from the queried `main_id * alf CMa B`; `component_candidate_ids("* alf CMa B","A") = * alf CMa A` **misses** the letterless catalog row `* alf CMa`. With a catalog, slot A instead matches the *secondary's* row `* alf CMa B` (via the queried main_id in its id set) → 1.018 in both slots.

α Cen is unaffected today because (a) its catalog rows are letter-symmetric (`* alf Cen A`/`* alf Cen B` both present → `component_candidate_ids` hits) and (b) its secondary `K1V` yields a valid MS mass. **Verified live:** `binary-stability-auto` for `"alpha Cen B"` = `"alpha Cen A"` = `"alpha Cen"` = `"* alf Cen"` → all **1.079 / 0.909 / 2.749 / 86.652**.

## 2. The ruling (channel MSG 183, Greg-signed)

- **Q1 → (A) primary-identity resolution.** On a secondary-named query, resolve the **primary's identity/sp_type for the mass + orbit derivation** (redirect secondary→primary for that path only). Target byte-exact: no-catalog `"Sirius B"` = `"Sirius"` = **2.063 / 0.4577 / 2.3136 / 74.142**; with-catalog `"Sirius B"` = **2.063 / 1.018**. **Keep the query echo transparent** (output still records the query was `"Sirius B"`). APP owns the exact layer.
- **Q2 → (i) binary-orbit stays a RAW reporter** (no chain, no preferred mass, **no catalog**). `binary-orbit "Sirius B"` → **2.18 / 0.4577** (= `binary-orbit "Sirius"`), NOT 2.063. The spec's "→2.063" line is corrected to →2.18. Do **not** give `binary_orbit` catalog resolution.
- **Q3 → BYTE-IDENTICAL.** The frozen CR-14 `"Sirius"` anchor must NOT move; option (B) (re-pin m2) declined; **no frozen anchor re-pins**. Whole CR-13 + CR-14 battery reproduces byte-identical.
- **Endorsed:** with-catalog robustness — slot A resolves the primary from the derived primary ids only, not the queried secondary's main_id (order-independent).

## 3. Design — degenerate-secondary → primary-identity redirect at the `binary_orbit` layer

**Core mechanism.** When a query resolves to a **secondary** whose spectral type is **degenerate/unparseable** (no OBAFGKM class — WD/BD/blank), resolve the **primary's** identity (main_id, sp_type, designations) via one SIMBAD lookup of the letter-stripped bare form, and use it for:
1. the **companion-mass `m1`** in the orbit solutions (`_nss_two_body_solutions` / `_sb9_solutions`) → fixes `binary-orbit "Sirius B"` raw output to 2.18/0.4577, which propagates to the tier-1 selection in every consumer; and
2. the **catalog `primary_sl`** in `resolve_binary_components` → slot A resolves the primary catalog row (2.063), slot B the secondary (1.018 / orbit).

The queried star's `main_id`/`ra`/`dec`/`sp_type` and `result["query"]` are **kept unchanged** (identity echo transparent); the primary is exposed additively as `identity["primary"]` + a `mass_resolved_via_primary` marker. The **cone search stays at the queried secondary's coordinates**, so the *same* orbit solutions (P, e, f) are found — only the companion `m1`/`m2` change.

### 3.1 Why this scoping guarantees the frozen anchors are byte-identical

The trigger is **secondary main_id (`\s[B-Z]$`) AND `_parse_spectral_class(secondary_sp_type)` returns no class**:
- **Fires** for Sirius B (`DA1.9`) and Procyon B (`DQZ`) — the exact acceptance + generality cases (both WD secondaries of letterless primaries).
- **Does NOT fire** for α Cen B (`K1V` — a valid MS class) → α Cen B (and every MS–MS letter-symmetric pair) takes the **unchanged** path → byte-identical, not even a float-ULP shift. (A universal redirect would leave α Cen B mathematically identical but change the last-ULP summation order; the sp-type gate avoids even that.)
- The CR-13 exclusion anchors (α Cen 48.967/45.721, Proxima 20.482) and the CR-14 `"alpha Cen B"` anchor are all MS or system/primary-named → untouched. `binary-orbit "alpha Centauri"` (seq 815) is a primary/system name (main_id not `\s[B-Z]$`) → untouched. The CR-15.4 `identity.designations` key is additive-preserved (the redirect only **adds** `identity["primary"]`).

Additional guard: the redirect only proceeds if the **primary** lookup succeeds AND the primary itself has a real MS spectral class (`_parse_spectral_class(primary_sp)` truthy). A failed/typeless primary lookup → no redirect (fall back to today's behavior), so the change can never make a currently-working case worse.

### 3.2 Exact changes

**A. `core/binary.py` — `binary_orbit` (the single interception point).** After `_resolve_binary_identity` returns `ident`, compute the mass-sp-type + optional primary block (`binary_orbit` must add a local `from core import databases` — today only `_resolve_binary_identity` imports it):

```python
from core import databases                              # local, in binary_orbit
mass_sp = ident.get("sp_type")
if _is_letterless_primary_secondary(ident):             # secondary main_id + DEGENERATE secondary sp
    bare = re.sub(r"\s+[B-Z]$", "", ident["main_id"]).strip()
    psl = databases.compute_simbad_lookup(bare)
    if (isinstance(psl, dict) and "error" not in psl
            and _parse_spectral_class(psl.get("sp_type") or "")[0] is not None):   # primary has a real MS class
        ident["primary"] = {"main_id": psl.get("main_id"), "sp_type": psl.get("sp_type"),
                            "designations": psl.get("designations") or {}}
        ident["mass_resolved_via_primary"] = psl.get("main_id")
        mass_sp = psl.get("sp_type")
```

Pass `mass_sp` (not `ident.get("sp_type")`) to `_nss_two_body_solutions(source_id, mass_sp, plx)` (2nd positional) and `_sb9_solutions(ident["ra"], ident["dec"], mass_sp)` (3rd positional) — the only two solution builders that take a spectral type (`_wds_orb6_solutions` is visual-only). Everything else in `binary_orbit` is unchanged.

Helper `_is_letterless_primary_secondary(ident)` (new, module-level, pure): `main_id` matches `\s+[B-Z]$` **and** the secondary spectral type has no OBAFGKM class. **⚠ `_parse_spectral_class` returns a 2-tuple `(letter, subtype)` — a tuple is ALWAYS truthy (even `(None, None)`), so test element `[0]`, never the tuple itself:** the gate is `_parse_spectral_class(ident.get("sp_type") or "")[0] is None` (degenerate secondary) and the primary guard above is `[0] is not None` (real MS primary). Mirror the existing correct usage in `m1_from_spectral_type` (`core/binary.py:54` — `letter, subtype = _parse_spectral_class(...)` then `if letter is None`). Use the same `\s+[B-Z]$` for both the detect and the strip, and factor it into one module-level constant/helper shared with the strip (the `\s[B-Z]$` idiom already lives in `exclusion_system._is_secondary_component` — three sites now; a shared `binary._is_secondary_component` these all call keeps the "is this a secondary" definition single-sourced).

**Naming:** at build, rename the helper to reflect the *actual* gate — it is **"a `\s+[B-Z]$` secondary with a degenerate spectral type,"** NOT a literal letterless-primary check (the primary's letterless-ness is decided downstream by the lookup + `[0] is not None` guard). `_secondary_needs_primary_sp` (or similar) reads truer than `_is_letterless_primary_secondary`; document that it fires on any degenerate secondary of a `\s+[B-Z]$` pair (for a hypothetical letter-symmetric WD-secondary it would also fire and still be correct — slot A resolves the real primary — but no such frozen anchor exists).

*Result:* `binary-orbit "Sirius B"` solutions carry companion `m1=2.18, m2=0.4577` (raw; = `binary-orbit "Sirius"`), `identity.main_id` still `* alf CMa B`, plus `identity.primary = {* alf CMa, A0mA1Va, …}`. Raw reporter preserved (still sp-type-derived, no catalog).

**B. `core/binary.py` — `binary_stability_auto`.** When `ident.get("primary")` is present, build `primary_sl` from it and use the primary sp_type for the selection:

```python
prim = ident.get("primary")
sel_sp = (prim["sp_type"] if prim else ident.get("sp_type"))
sel, sel_note = select_stability_elements(solutions, sel_sp)
preferred = None                                         # ⚠ KEEP: default before the guards below
if sel is not None and (star or ident.get("main_id")):  # ⚠ KEEP existing CR-15.4 guard
    if prim:
        primary_sl = {"main_id": prim["main_id"], "sp_type": prim["sp_type"],
                      "designations": prim["designations"]}
    elif ident.get("designations") is not None:
        primary_sl = {...ident...}                        # existing CR-15.4 path
    else:
        primary_sl = databases.compute_simbad_lookup(star or ident.get("main_id"))
    if isinstance(primary_sl, dict) and "error" not in primary_sl:   # ⚠ KEEP existing guard
        preferred = stellar_mass.resolve_binary_components(
            primary_sl, sel, catalog,
            system_name=(prim["main_id"] if prim else (star or ident.get("main_id"))))
```

**⚠ Do not drop the guards.** The build MUST keep `preferred = None` as the default, the `if sel is not None and (star or ident.get("main_id"))` wrapper, and the `if isinstance(primary_sl, dict) and "error" not in primary_sl` check (all in today's `binary_stability_auto`, `core/binary.py:862-875`). A no-orbit input (`sel is None`) or a bad primary lookup must leave `preferred=None` (the orbit masses stand, L3 graceful fallback) — else `resolve_binary_components` hits `sel.get(...)` on `None`. Only the `prim` branch is new; the rest is verbatim.

**Fix scope by tier (narrative correction):** for an **SB9/NSS-orbit** system (Sirius) the fix rides tier-1, which reads the solution's precomputed companion masses — so change A alone already makes the companion `m2` correct, and `sel_sp` is belt-and-suspenders. For a **WDS/orb6-only** system (Procyon, if it has no SB9/NSS companion mass — `_wds_orb6_solutions` emits `companion:None`), resolution is **tier-3 (equal-mass), driven by the `sel_sp` passed to `select_stability_elements`** — so there change B/C's `sel_sp = prim["sp_type"]` is load-bearing, not change A. Both cases are handled; the WB re-gate runs the live Procyon B path. `resolve_binary_components` is **unchanged** — it receives the primary's sl, so slot A resolves the primary catalog row and slot B the secondary, and the queried secondary main_id is never in slot A's id set (the WB-endorsed robustness, satisfied by construction).

**C. `core/report.py` — `_multiplicity_data_star` (dossier).** The binary_orbit result's `ident` now carries `"primary"` when redirected. Use it for the selection sp_type and the `primary_sl`:

```python
ident = result.get("identity", {})
prim = ident.get("primary")
sel, sel_note = binary.select_stability_elements(stellar, (prim["sp_type"] if prim else simbad.get("sp_type")))
if sel is not None:
    primary_sl = prim if prim else simbad
    preferred = stellar_mass.resolve_binary_components(
        primary_sl, sel, mass_catalog, system_name=(prim["main_id"] if prim else star))
```

(`prim` already has the `{main_id, sp_type, designations}` shape `resolve_binary_components` reads.) The CR-15.1 "no primary_override" comment stays accurate; add a CR-16 note.

**D. Transparency / echo.** `result["query"]` unchanged (raw input). `identity.main_id`/`ra`/`dec`/`sp_type` remain the queried secondary. `identity.primary` + `identity.mass_resolved_via_primary` are additive markers so a consumer can see masses were resolved via the primary. `docs/integration.md` (binary-orbit / binary-stability-auto / dossier) gets the new keys + a CR-16 note.

### 3.3 What is deliberately NOT changed

- `component_candidate_ids` / `match_mass` are **untouched.** Under the redirect, `primary_sl.main_id` is the actual letterless primary (`* alf CMa`), which `match_mass` hits directly — no bare-form injection needed. (The contract framed the fix around those two functions; WB's Q1→(A) ruling authorizes the identity-layer redirect instead — "you own the exact layer.") This keeps the CR-13/CR-14 shared-resolver surface frozen, which is exactly what the whole-battery re-gate wants.
- `binary_orbit` gains **no catalog** (Q2→(i)) — it borrows the primary's *spectral type* (identity resolution it already does), staying a raw reporter.
- The frozen `_extract_stability_elements` / `stability_from_solutions` mass tiers and `recompute_sma_kepler3` are unchanged.

## 4. Acceptance (re-gate targets, MSG 183)

1. no-catalog `binary-stability-auto "Sirius B"` → **2.063 / 0.4577 / 2.3136 / 74.142** (= `"Sirius"` byte-exact)
2. with-catalog `binary-stability-auto "Sirius B"` → **2.063 / 1.018**
3. `binary-orbit "Sirius B"` → **2.18 / 0.4577** (raw; = `binary-orbit "Sirius"`)
4. `dossier "Sirius B" multiplicity` (± `--star-mass-catalog`) → same masses as `"Sirius"`; and `multiplicity "Sirius B"` `m2_solar_lower` → **0.4577** (disclosed shift, WB-signed-off MSG 185)
5. generality (directional): `binary-stability-auto "Procyon B"` resolves its primary (F-type) correctly (= `"Procyon"`)
6. α Cen letter-symmetric unchanged: `"alpha Cen B"` → 1.079 / 0.909 / 2.749 / 86.652
7. **WHOLE CR-13 + CR-14 battery BYTE-IDENTICAL:** exclusion α Cen A 48.967 / B 45.721, Proxima 20.482; stability `"Sirius"` 2.063/0.4577/2.3136/74.142, `"alpha Cen B"` 1.079/0.909/2.749/86.652; `binary-orbit "alpha Centauri"` seq 815 (q 1.0/0.836/0.846) + the CR-15.4 `identity.designations` key.

## 5. Tests (offline, mocked SIMBAD/orbit — the anchors are live-gated in WB's re-gate)

New `Cr16*` classes (in `tests/test_binary_stability_auto.py` + `tests/test_report.py`; live anchors in `tests/test_query_dossier_live.py` / a `test_query_binary_live.py` if present):
- **Trigger unit** (the gate helper): **fires** for (`* alf CMa B`, `DA1.9`) and (`* alf CMi B`, `DQZ`); does **NOT** fire for (`* alf Cen B`, `K1V`) [MS secondary], (`* alf Cen A`, `G2V`) [**trailing `A` — the regex excludes A**], (`* alf CMa`, `A0mA1Va`) [primary, no trailing letter], (`* alf Cen C`/Proxima `M5.5V`) [MS], or a secondary with a valid MS sp. Also assert the **tuple-truthiness** guard directly (`_parse_spectral_class("DA1.9")[0] is None`, `("K1V")[0] is not None`) so a future refactor can't reintroduce the always-truthy bug.
- `binary_orbit` redirect (mocked identity + solutions): a WD-secondary letterless case attaches `identity.primary` + uses the primary sp for the companion `m1`; the companion `m2` recomputes via the mass function at the primary `m1`; α Cen-like MS-secondary case attaches **no** `primary` and is byte-identical.
- `binary_stability_auto` (mocked `binary_orbit` + seed/injected catalog): redirected case → slot A = primary catalog mass, slot B = secondary; non-redirected case unchanged. Include a **no-orbit input** case (`sel is None`) asserting `preferred=None` (the dropped-guard regression from the design review).
- **WDS-only / tier-3 case** (mocked, Procyon-shape): a redirected secondary whose only solution is a WDS/orb6 visual pair (`companion:None`) resolves via `sel_sp = prim.sp_type` (tier-3 equal-mass) → primary F-type mass, matching the primary-name query — pins that change B/C's `sel_sp`, not change A, carries this case.
- Cross-path equality (offline, mocked): a redirected secondary and its primary produce identical `elements`.
- Dossier `_multiplicity_data_star` (mocked): redirected case uses `ident.primary` for `primary_sl`; a letter-symmetric case uses `simbad` (unchanged).
- **`multiplicity_summary` pin** (the disclosed downstream shift, WB-signed-off MSG 185 → (a)): `multiplicity --star` on a WD-secondary letterless shape reports `m2_solar_lower` at the primary-mass SB1 bound (Sirius B → **0.4577**, not 0.283); a letter-symmetric shape is unchanged.
- **No-movement guards (pin the byte-identity guarantee offline):** (a) an MS-secondary letter-symmetric input (α Cen B shape) produces byte-identical `elements` to the pre-change path; (b) an **`exclusion_system` guard** — `binary_orbit("alpha Cen A")` / `("alpha Cen B")` solutions are unchanged (exclusion is an un-obvious `binary_orbit` consumer at `core/exclusion_system.py:504`; the CR-13 anchors flow through it, and they are safe ONLY because the gate excludes trailing-`A` and MS secondaries — this test locks that so a gate-regex regression can't silently move 48.967/45.721/20.482).

## 6. `/code-review` checkpoints

- **CP1 — after the `binary_orbit` redirect + helper (change A):** review the trigger scoping (does it fire exactly for degenerate-secondary letterless primaries and never for MS secondaries / primaries?), the `mass_sp` threading into both solution builders, the additive `identity.primary` shape, and the +1 SIMBAD-lookup cost/guarding. Confirm `binary-orbit` stays catalog-free (Q2) and the identity echo is preserved.
- **CP2 — after the two consumer wirings (changes B + C):** review that `binary_stability_auto` and the dossier both consume `ident.primary` consistently (same `primary_sl` shape, same `system_name`), that `resolve_binary_components` is genuinely unchanged, and that no consumer path regresses when `ident.primary` is absent (coordinate-only input, MS secondaries, primary/system names).
- **CP3 — final pass (whole diff + tests):** byte-identity discipline for the frozen battery, dead-code/DRY (share the redirect detection if it would otherwise be duplicated between `binary_stability_auto` and the dossier — prefer reading `ident.primary` in both rather than re-deriving), docs, and the test matrix coverage (every acceptance line + the no-movement guard).

## 7. Risks / residuals (documented, not silently accepted)

- **+1 SIMBAD lookup** per degenerate-secondary letterless query (the primary resolution). Rare path; guarded (only on the trigger). Not on any hot/loop path.
- **⚠ Disclosed downstream behavior change — the standalone `multiplicity` subcommand (`multiplicity_summary`, `core/binary.py:367`) — needs a WB ruling.** It is a THIRD passive consumer of `binary_orbit`'s solutions (it reads `m2_solar_lower = comp.get("m2_solar")` for an SB1 basis, `core/binary.py:396`) and needs **no code change** — but for a degenerate-secondary letterless query (`multiplicity --star "Sirius B"`) its `m2_solar_lower` shifts **0.283 → 0.4577** (the SB1 lower bound now solved at the correct primary mass). It is **not** in the frozen re-gate battery and the new value is *more* consistent, not wrong — **but it contradicts the standing invariant in `CLAUDE.md`** that "the standalone `multiplicity` subcommand exposes no per-component masses and stays byte-identical" (a CR-14 note). **WB ruling (MSG 185) → (a) SIGNED OFF: let `multiplicity "Sirius B"` `m2_solar_lower` report 0.4577.** Build items: (i) **update that CLAUDE.md `multiplicity`-byte-identical note** to record the CR-16 exception + the reason (WD-mis-seeded 0.283 → correct-primary-mass SB1 bound 0.4577), and (ii) pin the 0.4577 value with a `Cr16` test (§5). No code change to `multiplicity_summary` itself (passive consumer — it reads the now-corrected solution masses). `close_binary_census` is **safe** (uses `_census_nss`/`_census_sb9`, never `binary_orbit`).
- **Orbit-row stability:** the redirect keeps the queried secondary's coordinates, so the same SB9/NSS/WDS solutions are found; only companion `m1`/`m2` change. If a future system's secondary cone returned a *different* orbit row than its primary cone, the cross-path equality would be approximate — the WB whole-battery re-gate (running `query.py` on both names) is the backstop. (For Sirius, both names already return the identical SB9 seq — verified.)
- **MS-secondary letterless primary (out of scope, documented):** the sp-type-gated trigger deliberately does not fire for a letterless primary whose *secondary* has a valid MS type (none in the acceptance or the WB catalog). If WB ever adds such a system, the trigger widens to "secondary main_id + primary is letterless-only" — a one-line change flagged here. Chosen this way because Q3's byte-identity requirement makes "never touch an MS secondary" the safest scoping.
- **Composite primary sp (Procyon `F5IV-V+DQZ`):** `_parse_spectral_class` takes the leading `F5` (the primary component) → ~1.5 M☉, matching a `"Procyon"` query. Correct for the generality target.
- **CP3 scope-boundary findings (documented, not fixed — none is a regression or an acceptance/frozen-anchor case):**
  - **(#2, precision) The gate fires for a `\s+[B-Z]$` secondary with NO OBAFGKM class — WD/degenerate OR a blank/missing sp**, not WDs only. This is **by design intent** (the defect is "the secondary can't seed the primary mass," which a blank sp equally cannot). A blank-sp *MS* secondary would therefore redirect and borrow the primary's mass — an **improvement** over the old default `m1=1.0`, and it moves **no** frozen anchor (α Cen B/Proxima carry real MS types; every frozen query is MS/primary/system-named). The plan's "MS secondary never trips it" is precise only for a secondary carrying a **real MS class**; a classless secondary trips it intentionally. **Flagged to WB** in the build-complete message.
  - **(#1, hierarchical) A B-internal sub-orbit gets the primary's `m1`.** The orbit search uses the secondary's coords/source_id, but the companion classifier is fed the primary's sp-type; if a solution at those coords is actually intrinsic to the secondary (B is itself a spectroscopic sub-binary), its visible-star `m1` is tagged with the primary's mass. This is a **pre-existing** coordinate-resolution ambiguity (the old path fed the WD-default `1.0` to the same solution) — not a CR-16 regression; fixing it needs per-solution component attribution (matching each solution's source to A vs B), well beyond this CR. No hierarchical-triple anchor exists in the acceptance/catalog.
  - **(#3, detection) A secondary whose SIMBAD main_id carries no trailing component letter is not caught** (e.g. a secondary primarily named by a WD-catalog id `WD hhmm±ddd`, otype `WD*`, with no `\s+[B-Z]$`). `_is_secondary_component` returns False → no redirect → the old `m1=1.0`. Sirius B / Procyon B both resolve to `* … B` and ARE caught. Widening to an otype-aware detector (like `exclusion_system`'s) is a larger change; none of these is in the acceptance/catalog.

## 8. Build sequence

1. Change A (`binary_orbit` + helper) → **CP1**.
2. Changes B + C (consumers) → **CP2**.
3. Tests (§5) + `docs/integration.md` + CLAUDE.md suite-count note.
4. Full offline suite green + **CP3** → post-review fixes.
5. Live spot-check on this box (Sirius B ±catalog, binary-orbit Sirius B, dossier Sirius B, Procyon B, α Cen B unchanged) before handing to WB.
6. Channel: APP posts BUILT + GREEN → **WB independent whole-battery re-gate on the sister venv** → **Greg's one FULFILLED flip** → commit + push → move this plan to `completed_plans/` (+ README index).

**Hold for Greg's build-go before step 1.**
