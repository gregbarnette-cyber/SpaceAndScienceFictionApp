# PHASE_CR18_PLAN.md — bound-companion detection via the GCNS pairing layer + neighborhood transverse-separation honesty

**Status:** PLAN (awaiting Greg's build-go). Spec: `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR18-bound-companion-detection-via-gcns-pairing.md`. Rulings: coordination channel MSG 191 (spec) → MSG 192 (APP Qs) → **MSG 193 (WB rulings, Greg-signed, Q1–Q5 all confirm)**.

---

## 0. What CR-18 is (one breath)

A **hybrid two-part tool-level fix** for a real, currently-silent miss:

- **Part A — bound-companion detection + path agreement + signal.** Every multiplicity path (`multiplicity` subcommand + the `dossier --sections multiplicity` section) must report a system **multiple** when the GCNS pairing layer co-systems it (`gcns_stars.system_id` shared, `gcns_system_pairs` present) **even with no orbital solution** (SB9/WDS/NSS/ORB6 empty). The two paths must **agree**. Expose per companion the `bound` flag + **projected** `proj_sep_au` + a GCNS `multiplicity_basis` token. **Never fabricate** orbit-dependent quantities (a / e / component-mass partition / S_crit) for an orbit-less pair.
- **Part B — neighborhood separation honesty.** `stars-within-star` / `gcns-stars-within-star` report the **transverse** (angular × distance) separation, not the parallax-noise-dominated 3D Cartesian distance, and flag a `system_id`-sharing / bound neighbor as a bound companion.

**Anchors** (WB re-gates live on the sister venv): `dossier "* zet01 Ret" multiplicity` → Multiple? **yes** = `multiplicity "* zet01 Ret"`, companion `* zet02 Ret` proj_sep **3721.8**, bound, GCNS basis, **no** fabricated a/e/mass; `GJ 9588` (→ `G 19-16`) → companion `G 19-16 B` proj_sep **136.7**; `stars-within-star "GJ 9588" --ly 1` → `G 19-16 B` transverse ≈**137 AU** + bound flag (not the bare 0.332 ly); ε Eri optical double stays **not** a bound companion.

---

## 1. Invariants (violating any = CR-18 FAILURE)

1. **NUMERIC BATTERY BYTE-IDENTICAL.** No change to any mass / exclusion / stability NUMBER. The re-gate is scoped to the NUMBERS emitted by `exclusion-system` / `binary-stability-auto` / `binary-orbit` (WB MSG 193 Q4b) — **not** a byte-diff of the whole multiplicity-section JSON. Concretely the GCNS work must **not touch** `binary.stability_from_solutions`, `binary.select_stability_elements`, `binary._extract_stability_elements(_full)`, `stellar_mass.resolve_binary_components`, `exclusion_system`, or `binary.binary_orbit`'s solution logic. It is a **trailing additive read**.
2. **MONOTONIC VERDICT.** CR-18 may only **add** `is_multiple: true` (for co-systemed / bound orbit-less pairs); it must **not** flip any current `true`→`false`. Do **not** re-gate the existing detector to strict `bound=1` (MSG 193 Q4a).
3. **`binary-orbit --star` UNCHANGED.** Pure orbit reporter; honest "no solution" for ζ¹ Ret stays. No APP change (MSG 193 Q2). The `run-procedure.md` §6.2 wording fix is a WB BC-1 task.
4. **ε Eri UNTOUCHED (Q1 + Q3 guard).** ε Eri's pre-existing visual-basis `is_multiple: true` (`sep_au 0.0`, `gcns_n_components: null`, otype `BY*`, WDS-derived) is left as-is: **no** `bound`, **no** GCNS `proj_sep_au`, **no** escalation, and its component `basis` stays **`"visual"`** — the `"visual"→gcns_cpm` relabel touches the **GCNS route only** (a star with `gcns_n_components` null has no GCNS component to relabel).
5. **GCNS token = exact string `gcns_cpm`** (Q3) — BC-1…BC-5 pattern-match it verbatim.

**Deferred out of CR-18** (Greg-decides-post-flip, NOT build items): reconciling ε Eri's visual `is_multiple: true`, and pure-optical GCNS groupings (`n_components≥2`, all pairs `bound=0`) that keep reading "multiple" — now correctly annotated `bound=false`.

---

## 2. Current-state map (verified: Explore agent + live schema/data on HEAD `a1e369e`)

| Site | File · lines | Today | CR-18 gap |
|---|---|---|---|
| `multiplicity_summary` | `core/binary.py` 330–428 | resolves star→Gaia id→`compute_gcns_system`; keys `is_multiple` on `gcns_n>1`; **already folds `proj_sep_au`** into a component | mislabels the GCNS pair `basis="visual"`, **never reads `bound`**, emits no `gcns_cpm` |
| dossier multiplicity | `core/report.py` `_multiplicity_data_star` 622–701, `_blocks_multiplicity` 704–722 | verdict = SIMBAD otype `is_multiple` **OR** a stellar `binary_orbit` solution; `multiplicity_basis` names the **orbit** source only | **never consults GCNS** → the ζ¹ Ret disagreement |
| `binary_orbit` | `core/binary.py` 552–625 | pure orbit; honest "no solution" note; no GCNS | **no change** (invariant 3) |
| `compute_gcns_system` | `core/databases.py` 3036–3142 | returns per-pair `{source_id1,source_id2,separation_arcsec,mag_diff,proj_sep_au,bin,bound}` + members `{gaia_source_id,star_name,…}` + `n_components` | **the ready-made source** of the bound/sep signal |
| `stars-within-star` (opt 19) | `core/calculators.py` `compute_stars_within_distance_of_star` 421–509 | reads `star_systems` only; **no structured Gaia id** (only a `designations` text blob); 3D Euclidean; appends synthetic Sol | needs Gaia-id parse + GCNS cross-match + transverse calc |
| `gcns-stars-within-star` | `core/databases.py` `compute_gcns_stars_within_star` 3349–3447 | neighbors carry **structured `gaia_source_id` + `system_id` + `n_components`**; 3D Euclidean; synthetic Sol | one pair lookup away from bound + transverse |

**GCNS schema (live):** `gcns_system_pairs(system_id, source_id1, source_id2, separation_arcsec, mag_diff, proj_sep_au, bin, bound)` — 19,176 rows / **16,556 bound**. `gcns_stars(…, gaia_source_id, ra, dec, parallax, dist_pc, light_years, system_id, n_components)`.

**Anchor feasibility (verified in the live DB):**
- ζ Ret sys 11488: pair `bound=1, proj_sep_au=3721.8, separation_arcsec=309.11`; both components in `star_systems` with Gaia ids.
- GJ 9588 / G 19-16 sys 10640: pair `bound=1, proj_sep_au=136.68, separation_arcsec=5.92`; **`G 19-16` (`…280256`) and `G 19-16B` (`…281024`) both in `star_systems` with parseable `Gaia DR3` ids** → the SIMBAD-path anchor is achievable via the existing `Gaia\s+E?DR3\s+(\d+)` cross-match key.

---

## 2.5 Coverage & the Gaia-ID dependence (raised by Greg, 2026-09-01)

**Not all stars have a Gaia source_id — and the GCNS bound layer is keyed entirely on it.** Live counts:
- `gcns_stars`: **1,259 / 332,571 rows have NULL `gaia_source_id`** — the `gcns_missing_plx_inversion` (`missing_10mas`) objects Gaia saturated on / missed (Luhman 16 in the data; per project docs also **α Cen A/B**). `gcns_system_pairs` has **0** rows with a NULL `source_id1`/`source_id2`, so **an object with no Gaia source_id cannot appear in the bound-pair layer at all** (its `system_id`/`n_components` are NULL — e.g. Luhman 16). The Sun has none.
- `star_systems` (Part B neighbor pool): **253,486 / 256,003 (99.0%)** carry a parseable `Gaia DR3` id in `designations`; **2,517 (1.0%)** do not.

**Why this does NOT break CR-18:**
1. **No regression, graceful degradation (monotonic).** A0 routes a no-Gaia / not-co-systemed star → `(None, [])` → verdict **unchanged**, no `bound` field, no crash. A Part-B neighbor with no Gaia id → `bound=null` (Q5ii-sanctioned). A star is never *misreported*; it just doesn't gain the new signal.
2. **The anchors are unaffected** — ζ Ret and GJ 9588/G 19-16 all have Gaia ids (verified).
3. **No alternate join helps.** Even resolving a NULL-source object's `gcns_stars` row by name/2MASS yields `system_id = NULL` (it is in no resolvedss pair), so there is nothing to surface. The Gaia-id dependence is the **GCNS data boundary**, not a wiring choice the plan can engineer around.

**`bound` field semantics — TRI-STATE (WB MSG 195, must be pinned in docs/help):** `bound=true` = the GCNS pairing layer marks the pair gravitationally **bound**; `bound=false` = GCNS resolved it as an **optical / non-physical** pair; **`bound=null` (or the field absent) = OUTSIDE the Gaia-keyed GCNS layer → "unknown / not covered," NEVER "unbound."** α Cen is unambiguously bound (solved orbit) yet reads `bound=null` because it isn't in the Gaia layer — so **orbit-bound and GCNS-bound are two independent confirmations**; `null` must never be surfaced or consumed as "not bound." (WB MSG 195 also corrected its MSG-193 example: neither α Cen nor Sirius is GCNS-co-systemed — both primaries are Gaia-missing — so they carry no additive bound fields and stay byte-identical, confirmed live.)

**Residual limitation (documented, data-inherent — spec §"Known limits: resolved systems cover only Gaia-resolved multiples"):** a bound wide pair with **no orbit** whose component lacks a Gaia source_id (a bright Gaia-saturated pair, or a `missing_10mas` object) is **un-catchable via the GCNS bound layer** — a wide CPM pair is *identified by* Gaia's own shared-parallax + common-proper-motion, so a Gaia-missing component has no CPM detection to wire up. Such a pair is still caught by the **unchanged orbit path** if it has an orbit (α Cen, Sirius are orbit-detected). The plan surfaces this honestly (null bound, no false verdict), never fabricated boundedness. **Confirm with WB** (in the plan-status post) that this null-degrade on Gaia-missing objects is the accepted behavior — it matches their Known-Limits, so a quick confirm, not a scope change.

---

## 3. Design

### 3.A — Part A: detection + agreement + signal

**A0. One shared helper — single GCNS read, INCIDENT pairs only.**
New `core/binary.py`: `gcns_bound_companions(gaia_id) -> (gcns_n_components, companions)`.
- **Guards (review #7):** if `gaia_id` is falsy → `(None, [])`; wrap `int(gaia_id)` + `databases.compute_gcns_system(...)` in `try/except (TypeError, ValueError)` (mirrors the existing binary.py:360 guard) → `(None, [])` on bad id / no system. Note `compute_gcns_system` returns the pair/member data under the nested **`result["system"]`** key (`system["n_components"]`, `system["pairs"]`, `system["members"]`).
- **Incident-pair filter (review #3):** `compute_gcns_system` returns **every** pair in the connected component (a ≥3-star chain carries non-incident B–C edges). Emit a companion **only** for pairs where `int(gaia_id) ∈ {source_id1, source_id2}`, taking the OTHER endpoint. Each companion: `{source_id, star_name, bound (bool), proj_sep_au, separation_arcsec, basis:"gcns_cpm"}`, name joined from `system["members"]` by `gaia_source_id` with a **fallback to `str(source_id)` when the member is uncross-matched / `star_name` is None** (review #8). Deterministic order (proj_sep_au, then source_id).
- **Single read (review #6):** this helper is the **only** GCNS fetch for the `multiplicity` subcommand — it replaces the current lines 356–364 fetch too, so `gcns_n` and the companions come from one call (no divergence). Pure read; offline (DB only).

**A1. `multiplicity_summary` (binary.py).**
- Replace **both** the current GCNS fetch (356–364) **and** the mislabeled-`"visual"` fold (404–407) with one `gcns_n, gcns_comps = gcns_bound_companions(gaia_id)`.
- Compute `is_multiple` / `sb_flag` / `n_components` **exactly as today** — verdict still gates on `gcns_n and gcns_n > 1` (monotonic; **not** `bool(components)`). **After** that block (post lines 410–417, so they can't perturb `sb_flag`/`is_multiple` — review #10), extend `components` with one `gcns_cpm` component per companion: `{basis:"gcns_cpm", sb_flag:False, sep_au:proj_sep_au, proj_sep_au, bound, companion:star_name}`. (Built separately, **not** through the `_add` basis-dedupe.)
- Add top-level `multiplicity_basis:"gcns_cpm"` iff a gcns_cpm companion exists and no other basis is set (parity; the subcommand emits none today → purely additive).
- ε Eri (`gcns_n` null) → helper `(None, [])` → its WDS `basis="visual"` component untouched (invariant 4).

**A2. Dossier — a PER-RETURN-PATH augmentation, NOT a trailing block (review BLOCKER #1).**
`_multiplicity_data_star` (622–701) has **five** `return data` statements, four on star-bearing paths: 638 (except), 640 (error), **648 (`if not stellar`) — the ζ¹ Ret exit** (its `binary_orbit` returns empty → `stellar=[]`), and 701 (end). A block appended after line 700 is **dead code for ζ¹ Ret** — the exact anchor CR-18 fixes. So extract `_augment_gcns_multiplicity(data, simbad)` and call it **immediately before each star-bearing return** (638 / 640 / 648 / 701), **wrapping — never replacing or pre-empting — the existing logic**:
- Resolve Gaia id from `simbad["designations"]` (`binary.gaia_source_id_from_designations`); `gcns_n, comps = binary.gcns_bound_companions(gaia_id)`.
- **Monotonic verdict (Q4a):** `if gcns_n and gcns_n > 1: data["is_multiple"] = True` (only ever True).
- **Additive:** `data["gcns_companions"] = comps`.
- **`multiplicity_basis` fill-None (inside the helper — reviews #1/#2):** `if not data.get("multiplicity_basis") and comps: data["multiplicity_basis"] = "gcns_cpm"`. The orbit string is set at line 691 **only on the 701 path**, so the fill must live in the helper (which runs on every path) — it preserves α Cen/Sirius's orbit string and fills only the None (ζ¹ Ret, 648-path) case.
- **No-fabrication note** when `comps` and no orbital solution: append `"orbit-dependent quantities (a, e, component-mass partition, S_crit) not computable without an orbital solution"`.
- **CRITICAL — numeric battery (invariant 1):** the helper is a **pure read + additive write; it must NOT early-return.** On the 701 (orbit) path it runs **after** the stability chain, so α Cen/Sirius still execute `select_stability_elements` / `resolve_binary_components` / `stability_from_solutions` **byte-identically** — the danger the review flags is an implementer "hoisting" it to return early on a false→true flip, which would skip the chain and break the battery. The 638/640/648 paths have no stability chain to preserve. All existing returns + logic stay intact; the helper only adds keys / flips `is_multiple` false→true.
- `_blocks_multiplicity`: add a `("Bound companion (GCNS)", "<name> — proj_sep <x> AU, bound")` row per `gcns_companions` (label projected, not SMA).

**A3. Agreement.** Both paths call the **same helper** and the **same `gcns_n>1` gate**, and — with A2 fixed to run on the 648 path — both reach the verdict for ζ¹ Ret. Pinned by a test asserting `dossier(...)["multiplicity"]["is_multiple"] == multiplicity(...)["is_multiple"]` across ζ¹ Ret / α Cen / a single star / ε Eri.

### 3.B — Part B: neighborhood transverse separation

**Shared math helpers** (new, pure, `core/shared.py` — no matplotlib/DB dep; both callers import):
- `transverse_separation_au(ra1_deg, dec1_deg, ra2_deg, dec2_deg, dist_pc)` — great-circle angular sep (haversine, deg→arcsec) × `dist_pc` → AU. **Distance choice (review #5):** the `computed_angular` fallback (non-co-systemed neighbors) uses the **center's** `dist_pc` (frame = "separation as seen from the center system"); documented in the output/docs. Co-systemed pairs bypass this and take `proj_sep_au` directly (= angular×dist by construction; 5.92″ × 23.1 pc ≈ 136.7 AU).
- **`radial_parallax_dominated` criterion (reviews F3/#4 — concrete):** radial `r_ly = |dist_pc_n − dist_pc_c| × 3.26156`; transverse `t_ly = transverse_sep_au / 63241.077`. Flag `= r_ly > t_ly` (radial dominates). **Where parallax errors exist** (B1 — `gcns_stars.parallax_error`), additionally require `|plx_n − plx_c|` within the combined 1σ (radial offset statistically consistent with zero = pure noise) — matching the spec's "more than the parallax errors justify." B2 (`star_systems` has no `parallax_error`) uses `r_ly > t_ly` alone. Finalized/justified at CP2. (GJ 9588: 0.332 ly ≫ 0.0022 ly → flagged.)

**B1. `gcns-stars-within-star` (databases.py) — GCNS-native, additive keys.**
- Center already resolved to a `gcns_stars` row (`gaia_source_id`, `system_id`).
- One query: `gcns_system_pairs WHERE system_id = center.system_id`; build the map **only from pairs INCIDENT on the center** (`center_sid ∈ {source_id1, source_id2}` — review #3; a ≥3-star chain's B–C edges are excluded), keyed by the OTHER endpoint → `{other_source_id: {bound, proj_sep_au, separation_arcsec}}`.
- Per neighbor: shares `center.system_id` **and** in the incident map → `transverse_sep_au = proj_sep_au`, `bound`, `is_bound_companion = (bound and shared)`, `sep_method = "gcns_proj_sep"`. Else `transverse_sep_au = transverse_separation_au(...)`, `bound = None`, `is_bound_companion = False`, `sep_method = "computed_angular"`.
- Keep the existing `Distance` (3D ly); add `transverse_sep_au`, `transverse_sep_ly`, `bound`, `is_bound_companion`, `sep_method`, `radial_parallax_dominated`. **Additive keys only**; existing shape/order preserved. **Synthetic Sol row (review #9):** stamp all new keys onto it (`bound=None`, `is_bound_companion=False`, transverse from geometry, `sep_method="computed_angular"`) so every `stars[]` row shares one shape.

**B2. `stars-within-star` (calculators.py) — SIMBAD path, additive keys.**
- Center Gaia id: one `databases.compute_simbad_lookup(center_star)` → `designations["Gaia EDR3"]` → `gcns_stars.system_id` (center `ra/dec/ly` still come from the unchanged `compute_lookup_star_for_distance`; the extra lookup fires only to enable the bound feature). **Sol/Sun center → `compute_simbad_lookup` errors** → degrade bound features to `null`, transverse still computed from geometry.
- Per neighbor: parse the Gaia id from its `designations` **text** via the established `Gaia\s+E?DR3\s+(\d+)` cross-match regex. Batch neighbor Gaia ids → `gcns_stars(gaia_source_id, system_id)` in one `IN (...)` query. Neighbor shares center `system_id` → look up the incident pair `bound`/`proj_sep_au` (transverse = `proj_sep_au`; lands 136.7 for GJ 9588). Else transverse via `transverse_separation_au(...)` (center distance); `bound=None` / `is_bound_companion=False` where no cross-match (Q5ii).
- Keep the 3D `Distance`; add the same six keys as B1. **Synthetic Sol row (review #9):** stamp the new keys onto it too. **Offline** except the one center SIMBAD lookup (neighbor cross-match is pure DB).

---

## 4. Contract / docs

No new subcommands. **Additive JSON keys** on `multiplicity`, the dossier multiplicity section, `stars-within-star`, `gcns-stars-within-star`. Update: `docs/integration.md` (a CR-18 block — the new keys + the transverse/bound semantics), `docs/star-databases.md` (GCNS within-star surfaces), `docs/calculators.md` (opt 19 transverse note), `docs/testing.md` (the new `Cr18*` classes), `CLAUDE.md` (test count + CR-18 summary sentence + the multiplicity/within-star notes).

---

## 5. Tests (`Cr18*` classes — offline-first, deterministic)

GCNS tables are **not** auto-seeded, so offline tests **seed a minimal GCNS fixture** into a tmp DB (monkeypatch `core.db._DB_PATH`, seeding disabled — the `test_gcns.py` pattern): 2 systems (11488 ζ Ret, 10640 GJ 9588) × their `gcns_stars` + `gcns_system_pairs` rows, plus a pure-optical fixture (`n_components=2`, pair `bound=0`). For the within-star paths a **fuller `star_systems` seeder** is needed than the existing 4-column `_seed_star_systems` — rows must carry `ra`/`dec`/`parallax`/`designations` (with the `Gaia DR3 <id>` token B2 parses); the schema supports it (`db.py` 140–325). Mock `compute_simbad_lookup` / `binary_orbit` where a network identity/orbit is needed (e.g. `GJ 9588 → G 19-16 → Gaia …280256` for the A-path GJ 9588 case).

Offline cases:
- **helper** `gcns_bound_companions` → correct companion/bound/proj_sep for ζ Ret; `(None, [])` for no-Gaia / non-co-systemed; **incident-only** (a 3-star fixture: a non-incident B–C edge is not emitted as a center companion).
- **A1** `multiplicity_summary` ζ Ret → `is_multiple` true, component `basis="gcns_cpm"`, `bound` true, `proj_sep_au` 3721.8; **no** `"visual"` mislabel.
- **A1 ε Eri guard** — fixture with `gcns_n` null + a WDS visual solution → component stays `basis="visual"`, no bound field, no relabel.
- **A2** dossier ζ Ret → `is_multiple` true, `multiplicity_basis == "gcns_cpm"`, `gcns_companions` present, **no** `elements`/a/e/mass (no fabrication), no-orbit note present.
- **A2 GJ 9588 Part-A anchor (review F1 — was live-only):** dossier + multiplicity for `GJ 9588` (mock SIMBAD → `G 19-16`, Gaia …280256) → bound companion `G 19-16 B`, `proj_sep_au` **136.7**, `bound` true. Seeded system 10640 already supports it; this pins the SIMBAD-identity→Gaia→GCNS resolution on the A-path offline.
- **A2 orbit-detected fixture** (orbit + GCNS co-membership) → `multiplicity_basis` **unchanged** (orbit string, not overwritten); gcns fields additive.
- **A3 agreement** — dossier verdict == subcommand verdict for ζ Ret / α Cen / single / ε Eri.
- **monotonicity** — pure-optical grouping (`bound=0`) → `is_multiple` stays true (unchanged), companion `bound=false`, `is_bound_companion=false`, no escalation.
- **B1** gcns-within-star GJ 9588 → neighbor `transverse_sep_au≈136.7`, `bound` true, `is_bound_companion`, `sep_method="gcns_proj_sep"`; Sol row carries the new keys.
- **B2** stars-within-star GJ 9588 → neighbor transverse ≈137, bound true; a no-Gaia-id neighbor → `bound=None`; 3D `Distance` present + `radial_parallax_dominated` labeled; Sol row carries the new keys.
- **transverse helper** math anchor (5.92″ × 23.1 pc ≈ 136.7 AU); **`radial_parallax_dominated`** deterministic anchor.

**Existing-test audit (review watch-item).** A1's relabel + additive fields change the `multiplicity` / dossier **JSON shape** for GCNS-paired stars (e.g. a component `basis` that was `"visual"` → `"gcns_cpm"`, new `bound`/`gcns_companions`/`multiplicity_basis`). This is a Q3/Q4b-sanctioned shape change, **not** the numeric battery. Grep the existing `multiplicity`/dossier tests for assertions pinning the old GCNS `"visual"` basis or component shape and update them as part of CR-18 (the `m2_solar_lower` values — e.g. CR-16 `"Sirius B"` 0.4577 — are untouched and must stay pinned).

Live-gated anchors (`SPACE_APP_RUN_LIVE=1`, in `test_query_dossier_live.py` / a within-star live file): the exact ζ Ret / GJ 9588 / stars-within-star values against real `query.py`.

**Byte-identity guard:** the full existing offline suite (currently **3250 pass / 88 skip**) must stay green — the frozen CR-13/14/15.4/16 anchor tests are the byte-identity tripwire on my side; the authoritative battery re-gate is WB's on the sister venv.

---

## 6. `/code-review` checkpoints

- **CP1 — after Part A** (`binary.py` + `report.py`), effort **high**. Focus: (a) the stability/exclusion path is **untouched** (no reordering/altering of `stability_from_solutions` / `resolve_binary_components` / `select_stability_elements` — invariant 1); (b) monotonicity (only sets True); (c) ε Eri relabel guard; (d) agreement-by-construction (shared helper + shared gate); (e) `multiplicity_basis` fill-None rule doesn't overwrite an orbit string; (f) no fabricated mass on the no-orbit path; (g) **the augmentation WRAPS every star-bearing return (638/640/648/701) and never early-returns / pre-empts the stability chain on the orbit path** (review BLOCKER #1) — verify the ζ¹ Ret 648-path is actually reached; (h) **verify `data["is_multiple"]` is not consumed to compute a mass/stability output ANYWHERE outside the multiplicity block** (review F4 — the WB numeric re-gate is scoped to the exclusion/stability tools, not the dossier, so a fabrication triggered elsewhere by the false→true flip would not be caught there).
- **CP2 — after Part B** (`databases.py` + `calculators.py`), effort **high**. Focus: transverse math correctness; **finalize the error-aware `radial_parallax_dominated` criterion** (review F3/#4); **center-incident pair filtering** (review #3 — no B–C edge mis-keyed onto a neighbor); the **center-`dist_pc` choice** for the `computed_angular` fallback (review #5); **synthetic-Sol row carries all new keys** on both paths (review #9); **offline-only** neighbor cross-match (no per-neighbor network — only the single center SIMBAD lookup, with the **Sol-center `compute_simbad_lookup` error → null-degrade** guard); additive-key backward-compat (existing `Distance`/`count`/`stars` shape preserved); Gaia-id regex parse robustness.
- **CP3 — final** (tests + docs + full diff), effort **high**. Whole-diff pass: additive-only contract, zero numeric-battery change, docs accuracy, test coverage of every invariant.

Each CP: triage findings, fix in-tree, re-run the offline suite.

---

## 7. Sequencing & exit gates

1. Part A build → **CP1** → fix.
2. Part B build (incl. the shared transverse helper) → **CP2** → fix.
3. Tests (offline fixtures + live-gated anchors) → offline suite green.
4. Docs (§4).
5. **CP3** final review → fix.
6. Local anchor re-run under the venv: `multiplicity`/`dossier`/`stars-within-star`/`gcns-stars-within-star` for ζ Ret + GJ 9588 (assert the fix), and a battery spot-check (`binary-stability-auto "Sirius"`/`"alpha Cen B"`, `exclusion-system` α Cen, `binary-orbit "alpha Centauri"`) byte-identical.
7. Post to WB (channel) for the independent whole-battery + CR-18-anchor re-gate on the sister venv → hold for Greg's one **FULFILLED** flip → commit + push on Greg's authorization (message ends with the `Co-Authored-By` / `Claude-Session` trailers; nothing pushed before the flip).

---

## 8. Conscious decisions & risks

**Conscious decisions (sign-off, not accidental deviations):**
- **`is_bound_companion = bound AND shared` (review F2).** The spec Part B says "shares `system_id` **or** is bound." I use AND — a neighbor is a *bound companion* only when it is both co-systemed and `bound=1`. This is stricter than the OR wording but aligns with CR-18's bound-flag discipline and the deferred "pure-optical groupings correctly annotated `bound=false`" note (MSG 193). It breaks no anchor (GJ 9588 = bound+shared → true; ε Eri → false) and the **raw `bound` flag is still surfaced**, so no information is lost.
- **`multiplicity` JSON shape changes for GCNS-paired stars (review watch-item).** A1 relabels the GCNS component `basis` `"visual"→"gcns_cpm"` and adds `bound`/`gcns_companions`/`multiplicity_basis`. This is a **Q3/Q4b-sanctioned additive/relabel shape change — NOT the numeric battery.** The `m2_solar_lower` values (e.g. CR-16 `"Sirius B"` 0.4577) are untouched; existing shape-pinning tests are updated as part of CR-18 (§5 audit); WB's re-gate confirms the numeric anchors unchanged.

**Risks & mitigations:**
- **Dossier early-return (review BLOCKER #1)** — mitigated: the GCNS augmentation is a helper called on **every** star-bearing return path (638/640/648/701), never a trailing block; CP1(g) verifies the ζ¹ Ret 648-path is reached and the orbit path still runs the stability chain untouched.
- **SIMBAD-path Gaia-id fragility** — mitigated: verified `G 19-16 B` carries a parseable `Gaia DR3` id in `star_systems`; reuse the existing GCNS cross-match regex; degrade to `bound=null` (Q5ii) when absent.
- **Extra center SIMBAD lookup on `stars-within-star`** — one call, additive, only to enable GCNS features; center `ra/dec/ly` resolution unchanged; Sol-center error → null-degrade. CP2 scrutinizes.
- **`multiplicity_basis` overwrite** on orbit-detected systems — mitigated by the fill-None-only rule (inside the augmentation helper); pinned by the orbit-detected-fixture test.
- **Byte-identity drift** — the GCNS work is a **pure read + additive write** that never enters the stability/exclusion chain and never early-returns before it; the frozen anchor tests + CP1(a)/(g)/(h) guard it; WB re-gates authoritatively.
- **Multi-component chains (review #3)** — the incident-pair filter (A0 + B1) prevents a non-incident B–C edge's `proj_sep`/`bound` from being mis-assigned to a neighbor.
- **Test data** — GCNS not auto-seeded → tests seed a minimal GCNS fixture + a fuller `star_systems` fixture into a tmp DB (established `test_gcns.py` pattern).
