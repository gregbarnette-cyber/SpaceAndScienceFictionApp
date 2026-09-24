# PHASE CR-23 — exclusion mass-chain harmonization (Option A) + `mass_provenance` surface + evolved `standoff_note`

**Status: ✅ FULFILLED + SHIPPED — committed `9722ea4` (WB re-gate GREEN + Greg-FULFILLED, MSG 256). Built + suite-GREEN (3465 passed / 91 skipped / 0 failures, 2026-09-20).**
Scope-locked **Option A (full harmonization)** by Greg (2026-09-20). Prerequisite CR-22 is FULFILLED
(SHA `710e7cb`, origin/main). Priority **LOW** (a modest accuracy/consistency fix on *non-cataloged*
stars). Channel Q&A: MSG 250 (spec) / 251 (diagnosis+Qs) / 252 (rulings). Contract:
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR23-exclusion-mass-chain-harmonization.md`;
fire kit `cr23-handoff-kit.md`.

CR-23 is **code-only** (no WB data half). It harmonizes the exclusion tool's stellar-mass resolution
with `dossier` and surfaces provenance. Three sub-CRs ship together, nothing deferred.

---

## 0. Confirmed diagnosis (spec's first deliverable — MSG 251, WB-accepted MSG 252)

Cause **(a)** with a **(c)** manifestation, isolated to one branch:

- **`query.py cmd_exclusion_boundary`, the `if args.star:` MAIN-SEQUENCE fall-through (lines ~855–866):**
  resolves mass straight from `regions.compute_star_system_regions_from_simbad(sl)` →
  `stellarMass = bcLuminosity ** 0.2632` (raw **L-inversion**). It never consults `--star-mass-catalog`
  **or** Gaia FLAME, and passes no `mass_provenance` to `two_layer`. → ε Eri 0.7576540 → **42.51**, no
  provenance, no flag. **This is the entire divergence.**
- **NOT cause (b):** FLAME is never called on that branch — there is nothing to time out.
- **The sibling paths are already correct** (nothing to fix in them for CR-23.1 *values*):
  - `exclusion-boundary --star` **EVOLVED** (lines ~840–853) already routes through
    `stellar_mass.resolve_component_mass(spec, catalog, allow_flame=True)` (full ladder + FLAME) and
    passes `mass_provenance`/`mass_note`.
  - `exclusion-system` **every path** (`--star` single via `_single_body_component`, `--star` binary via
    `_resolve_system_from_star`, `--component` via `_resolve_component_mass`) already routes mass through
    the shared `stellar_mass.resolve_component_mass` chain (FLAME wired). So
    `exclusion-system --star "epsilon Eridani"` has returned **0.811 / gaia_flame / 43.69** since the
    CR-13 anchor. Acceptance case 3 ("both subcommands agree") is a consistency control — the fix brings
    `exclusion-boundary --star` up to it.

**Scope-of-change (WB-accepted, MSG 252):** rewiring the one MS branch to the tier ladder changes:
1. non-cataloged **FLAME-resolved** MS stars on `exclusion-boundary --star`: ε Eri 42.51 → 43.69
   (+ σ Dra, Lalande 21185 per the spec scope note);
2. a **cataloged** single MS star run via `exclusion-boundary --star <s>`: inversion → catalog (that
   branch ignores the catalog today). Same bug, correct Option-A behavior. **⚑ This includes the 4-star
   internal seed** returned by `load_mass_catalog(None)` — **Sirius A (2.063), Vega (2.135), α Cen A
   (1.079), α Cen B (0.909)** — so `exclusion-boundary --star "Sirius A"|"Vega"|"alpha Cen A"|"alpha Cen
   B"` shifts inversion→catalog **even with NO `--star-mass-catalog` flag** (the seed always loads). e.g.
   `exclusion-boundary --star "Sirius A" --alpha 0.4` ≈ 66.7 (inversion ~2.34) → **63.5** (seed 2.063).
   None of these is a byte-identical anchor (the α Cen / Sirius anchors run via `exclusion-system` on the
   binary, which already uses the seed), but WB's re-gate must expect them if it spot-checks single-star
   `exclusion-boundary --star`.

**Invariants that keep the byte-identical anchors byte-identical:**
- A FLAME-**miss** star (cool dwarf, no FLAME mass — e.g. Proxima) falls to inversion =
  `bcLuminosity ** 0.2632` = the **exact** old regions number. So only FLAME-**hit** or **cataloged**
  single MS stars move on this path.
- Sol (`--object`), α Cen / Sirius (binaries → `exclusion-system`), Proxima (`exclusion-system`,
  FLAME-miss), δ Pav / Procyon A (evolved, `exclusion-system`, cataloged) never run through the
  `exclusion-boundary --star` single-MS branch → unchanged values.

---

## 1. CR-23.1 — exclusion mass chain = the dossier tier ladder

### 1a. `query.py cmd_exclusion_boundary` — rewire the `--star` MAIN-SEQUENCE branch
Replace the raw-regions mass with the shared resolver (mirroring the EVOLVED branch immediately above
it), keeping `bcLuminosity` for both the L-inversion tier and the wall/luminosity term:

```python
# main sequence: CR-23.1 tier ladder — manual > catalog > Gaia FLAME > L-inversion(bcLuminosity),
# so exclusion-boundary --star == exclusion-system --star == dossier for the same star.
reg = regions.compute_star_system_regions_from_simbad(sl)
if isinstance(reg, dict) and "error" in reg:
    _out(reg); return
star_lum = reg.get("bcLuminosity")
if star_lum is None:
    _out({"error": f"Could not derive luminosity for '{args.star}'."}); return
catalog = stellar_mass_tables.load_mass_catalog(args.star_mass_catalog)
if isinstance(catalog, dict) and "error" in catalog:
    _out(catalog); return
spec = {"name": sl.get("main_id"), "sp_type": sp, "luminosity_lsun": star_lum,
        "designations": stellar_mass.augment_designations(sl.get("designations"),
                                                          {sl.get("main_id")})}
_st = {}
mass, mprov, mnote = stellar_mass.resolve_component_mass(
    spec, catalog, allow_flame=True, status_out=_st)   # inversion tier available (star_lum>0) → never None
res = two_layer(mass_msun=mass, luminosity_lsun=(lum if lum is not None else star_lum),
                sp_type=sp, otype=ot, object_name=args.star,
                mass_provenance=mprov, mass_note=mnote, **cls_kw, **wind_kw)
if _st.get("flame_status"):
    res["flame_status"] = _st["flame_status"]           # CR-23.2 (non-blocker 2): degrade flag
_out(res)
```

- **Byte-identity for FLAME-miss:** `resolve_component_mass`'s inversion = `spec["luminosity_lsun"] **
  0.2632` = `bcLuminosity ** 0.2632` = the exact `regions.stellarMass`. So a FLAME-miss/no-catalog star
  is byte-identical to today.
- `resolve_component_mass` matches `--star-mass-catalog` internally (`smt.match_mass`) → a cataloged MS
  star now correctly short-circuits at tier-2 (the disclosed change).

### 1b. `query.py cmd_exclusion_boundary` — thread `flame_status` on the EVOLVED branch
The EVOLVED branch already uses `resolve_component_mass` but drops the degrade flag. Add `status_out`
and surface it (non-blocker 2, evolved variant):

```python
_st = {}
mass, mprov, mnote = stellar_mass.resolve_component_mass(spec, catalog, allow_flame=True, status_out=_st)
res = two_layer(mass_msun=mass, luminosity_lsun=lum, sp_type=sp, otype=ot,
                object_name=args.star, mass_provenance=mprov, mass_note=mnote, **cls_kw, **wind_kw)
if _st.get("flame_status"):
    res["flame_status"] = _st["flame_status"]
_out(res)
```
(No `luminosity_lsun` in the evolved `spec` → inversion tier stays unavailable → mass stays measured or
None → r_ex/standoff_note behavior unchanged. Values byte-identical; only the flag is added.)

### 1c. `core/exclusion_system.py` — capture `flame_status` on the single-body `--star` path (non-blocker 3)
`_single_body_component` calls `_resolve_component_mass(spec, catalog)` with no `status_out`, dropping the
degrade flag. Add an optional `status_out`:

- `_single_body_component(sl, catalog, star, status_out=None)` → pass `status_out=status_out` on the
  **first** `_resolve_component_mass` call (the FLAME-eligible one; the L-inversion retry keeps
  `allow_flame=False`, so it never resets the flag).
- `_resolve_system_from_star`: build the single-body meta with the flag. The two single-body return
  sites become:
  - secondary/off-MS branch: `_sf = {}; built = _single_body_component(sl, catalog, star, status_out=_sf)`
    → `return [comp], notes, ({"flame_status": _sf["flame_status"]} if _sf.get("flame_status") else {})`
  - wide/no-orbit branch: merge `flame_status` into the existing `{"gaia_status": bo_status}` meta.
- `compute_exclusion_system` already copies `star_meta` keys `("gaia_status", "flame_status_a",
  "flame_status_b")` onto the result. Extend that tuple to include **`flame_status`** (the single-body
  singular form) so it surfaces. Binary `--star` keeps `flame_status_a/_b` (unchanged).

**Exclusion-system mass VALUES are unchanged by CR-23.1** — the chain was already wired; this only adds
the previously-dropped single-body degrade flag.

---

## 2. CR-23.2 — surface `mass_provenance` (+ CR-19 `flame_status`) on every exclusion output

### 2a. `core/exclusion_boundary.py compute_two_layer_boundary` — always emit `mass_provenance`
Today `mass_provenance` is added only `if mass_provenance:` (line ~264). Make the key **always present**
(value or `None`) so "no missing-field cases" holds (Q2/Greg):
- In the `WINDLESS` early-return (line ~219) and `UNMODELED` early-return (line ~228) `base.update`
  blocks, add `"mass_provenance": mass_provenance` (so a windless/unmodeled body still carries the key —
  `object_preset` for `--object brown-dwarf/rogue-planet`, else `None`).
- In the main path, replace `if mass_provenance: result["mass_provenance"] = mass_provenance` with an
  unconditional `result["mass_provenance"] = mass_provenance` (may be `None` for the evolved-no-mass case).

### 2b. `query.py cmd_exclusion_boundary` — pass a descriptive `mass_provenance` on the non-ladder paths (Q2=B)
- `--mass-msun` branch (line ~784): `two_layer(..., mass_provenance="manual")`.
- `--object` branch (line ~800): `two_layer(..., mass_provenance="object_preset")` (both the standoff
  and windless-preset objects).
- `--spectral-type` branches: MS-table branch (line ~822) → `mass_provenance="spectral_type_table"`;
  the windless/unmodeled/evolved `--spectral-type` early branch (line ~810) has no resolved mass →
  pass `mass_provenance=None` (key present, value null — honest: no mass looked up). **The no-mass `null`
  is WB-CONFIRMED (Greg, MSG 254) — see §8.**
- `--star` MS/EVOLVED branches: the ladder value from `resolve_component_mass` (§1a/1b); windless/unmodeled
  `--star` (line ~837) → `mass_provenance=None`.

**Enum after CR-23.2:** `{manual, catalog, gaia_flame, ms_luminosity_inversion, object_preset,
spectral_type_table}` (Q1: `ms_luminosity_inversion`, the string the shared resolver + dossier already
emit — **no** new `inversion` literal, **no** app-wide rename). `None` on the no-mass domains.

### 2c. `mass_note` alongside `mass_provenance` (non-blocker 4)
`two_layer` already accepts `mass_note`. §1a/1b pass it. It is surfaced today only on the evolved-no-mass
branch; extend `compute_two_layer_boundary` so `mass_note` (when truthy) is surfaced on the MS/evolved
**with-mass** path too (additive `result["mass_note"] = mass_note`). Harmless, honest.

### 2d. exclusion-system `mass_provenance`
Already present per component (`compose` line ~386 sets `"mass_provenance": m.get("mass_provenance")`).
No change needed except the single-body `flame_status` from §1c. The new `object_preset` /
`spectral_type_table` values are exclusion-boundary-only input modes (no exclusion-system analog), so no
cross-tool break.

### 2e. `--gaia-timeout` on `exclusion-boundary` (non-blocker 1)
Add `p.add_argument("--gaia-timeout", dest="gaia_timeout", type=float, default=None, help=...)` to the
`exclusion-boundary` parser (exclusion-system/dossier already have it). The central dispatch already
calls `_catalog.set_gaia_timeout(args.gaia_timeout)` for any subcommand carrying the arg (query.py
~line 4477), so no other wiring is needed. This makes CR-23.2's forced-timeout acceptance runnable on
`exclusion-boundary`. (`SPACE_APP_GAIA_TIMEOUT` env + the `SPACE_APP_GAIA_FORCE_UNREACHABLE` CR-19 hook
still work as before, used by the offline degrade test.)

---

## 3. CR-23.3 — populate the evolved-host `standoff_note` on `exclusion-system` (note-only)

`exclusion-boundary --star <evolved>` already emits `standoff_note` (two_layer sets `_EVOLVED_STANDOFF_NOTE`
since CR-22) — **unchanged**. The gap is `exclusion-system`: `compose_exclusion_system`'s per-component
dict (lines ~385–397) has no `standoff_note`.

- In `compose_exclusion_system`, add to the per-component dict:
  ```python
  "standoff_note": (
      eb._EVOLVED_STANDOFF_NOTE if m["domain"] == ew.EVOLVED and m["r_ex_au"] is not None
      else eb._EVOLVED_NO_MASS_NOTE if m["domain"] == ew.EVOLVED   # evolved, no measured mass → no standoff
      else None),
  ```
  Reusing `eb._EVOLVED_STANDOFF_NOTE` / `eb._EVOLVED_NO_MASS_NOTE` guarantees identical wording to
  `exclusion-boundary` (single source of truth). `main_sequence` → `None`; `windless_free_harbor` /
  `unmodeled` → `None` (null standoff by construction).
- **Q3: per-component only** — no top-level echo (WB MSG 252).
- **No numeric change** anywhere (note-field-only).

---

## 4. Files touched

| File | Change |
|---|---|
| `query.py` | `cmd_exclusion_boundary`: rewire `--star` MS branch (§1a); thread `flame_status` on `--star` EVOLVED (§1b); `mass_provenance` on `--mass-msun`/`--object`/`--spectral-type` (§2b); add `--gaia-timeout` arg (§2e) |
| `core/exclusion_boundary.py` | `compute_two_layer_boundary`: always-emit `mass_provenance` incl. windless/unmodeled (§2a); surface `mass_note` on the with-mass path (§2c) |
| `core/exclusion_system.py` | `_single_body_component` + `_resolve_system_from_star` single-body `flame_status` capture (§1c); `compose_exclusion_system` per-component `standoff_note` (§3); extend the surfaced meta tuple with `flame_status` |
| `tests/test_cr23.py` | **new** — offline (mocked) CR-23.1/23.2/23.3 |
| `tests/test_query_exclusion_system.py` | subprocess: `mass_provenance` on every `exclusion-boundary` path; forced-degrade `flame_status` via `SPACE_APP_GAIA_FORCE_UNREACHABLE=1`; exclusion-system single-body `standoff_note`/`flame_status` |
| `tests/test_query_exclusion_system_live.py` | live-gated (`SPACE_APP_RUN_LIVE=1`): ε Eri → 0.811/gaia_flame/43.69 on both subcommands |
| `docs/integration.md` | CR-23 blocks under `exclusion-boundary` + `exclusion-system`; the 6-value `mass_provenance` enum; `flame_status`/`--gaia-timeout` on exclusion-boundary; evolved `standoff_note` |
| `docs/testing.md` | `test_cr23.py` entry + suite count delta |
| `docs/query-commands-index.md` | `exclusion-boundary` gains `--gaia-timeout` + `mass_provenance`/`flame_status` output |
| `CLAUDE.md` | CR-23 summary + new baseline suite count |

**No change to** the FROZEN `compute_exclusion_boundary` (single-body standoff generator) — untouched, as
in CR-22. `core/stellar_mass.py` unchanged (the chain already does everything CR-23.1 needs); CR-23 only
*calls* it from the one branch that wasn't.

---

## 5. `/code-review high` checkpoints

- **CP1 — the mass-chain rewire (CR-23.1).** After §1a/1b/1c. Focus: the `exclusion-boundary --star` MS
  branch resolves via the ladder; FLAME-miss byte-identity (inversion == old `regions.stellarMass`);
  cataloged single MS star hits tier-2; the single-body `flame_status` capture in exclusion-system has no
  arity/return regression; no import cycle (query.py calls `stellar_mass` directly, not exclusion_system's
  privates).
- **CP2 — `mass_provenance` + `flame_status` surface (CR-23.2).** After §2. Focus: every
  `exclusion-boundary` path emits `mass_provenance` (the 6-value enum + `None` on no-mass domains); the
  always-emit change in `two_layer` doesn't perturb any CR-22 field ordering/values; the forced-degrade
  (`SPACE_APP_GAIA_FORCE_UNREACHABLE`) surfaces `flame_status` and falls to `ms_luminosity_inversion` on
  both subcommands' single-body paths; `--gaia-timeout` wiring.
- **CP3 — CR-23.3 `standoff_note` + whole-CR pass.** After §3. Focus: evolved component gets the
  research-grade note, `main_sequence` stays `null`, windless/unmodeled `null`; note wording identical to
  exclusion-boundary (shared constants); no numeric drift anywhere; full offline suite + the CR-13/14/16/22
  battery byte-identical except the intended ε Eri/FLAME + cataloged-single-MS shifts.

Each checkpoint's findings are triaged and folded before the next. A final whole-diff pass at CP3.

---

## 6. Test plan

**Offline `tests/test_cr23.py`** (in-process, mocked — reuse the `test_exclusion_system.py` harness:
patch `core.databases.compute_simbad_lookup`, `core.binary.gaia_source_id_from_designations`,
`core.regions.compute_star_system_regions_from_simbad`, and **`core.catalog.gaia_astrophysical`**):
- **CR-23.1 FLAME hit:** ε Eri fixture (K2V, a Gaia id) + `gaia_astrophysical` → `{"parameters":
  {"mass_flame": 0.811}}` → `cmd_exclusion_boundary(--star)` gives `mass_msun≈0.811`,
  `mass_provenance=gaia_flame`, `r_ex_au≈43.69`; `compute_exclusion_system(star=...)` single-body →
  same 0.811/gaia_flame/43.69. Assert the two agree.
- **Hand-derived anchor:** `47.5 * 0.811**0.4` ≈ 43.69 (α=1/3 default → check the actual default-α value;
  the 43.69 anchor is α=0.4 per the spec's arithmetic — verify which α the acceptance uses and pin the
  matching number). *(exclusion-boundary default α=1/3; the spec's 43.69 uses `^0.4`. Pin both: α=1/3 and
  α=0.4 values, and confirm with WB which the re-gate runs — see Risks.)*
- **CR-23.1 FLAME miss:** a cool-dwarf fixture, `gaia_astrophysical` → no `mass_flame` → falls to
  `ms_luminosity_inversion` = `bcLuminosity**0.2632`; assert byte-identical to the pre-CR-23 regions value.
- **CR-23.1 cataloged:** pass a catalog row for the star → `catalog` tier, standoff from the catalog mass.
- **CR-23.2 forced degrade:** `SPACE_APP_GAIA_FORCE_UNREACHABLE=1` (or mock `gaia_astrophysical` →
  `{"error":..., "gaia_bound_reason":"unreachable"}`) → `mass_provenance=ms_luminosity_inversion`,
  `flame_status="unreachable"`, on both `exclusion-boundary --star` and `exclusion-system --star`.
- **CR-23.2 every-path provenance:** `--mass-msun`→`manual`; `--object sun`→`object_preset`;
  `--object brown-dwarf`→`object_preset` (windless, key present); `--spectral-type G2V`→
  `spectral_type_table`; `--spectral-type DA2`→`mass_provenance=None` (windless).
- **CR-23.3 standoff_note:** `compute_exclusion_system(star="Delta Pavonis")` (G8IV fixture + catalog
  mass) → the evolved component's `standoff_note` non-null == `eb._EVOLVED_STANDOFF_NOTE`, standoff
  unchanged; **`compute_exclusion_system(star="Procyon A")`** (F5IV-V fixture + catalog mass) → evolved
  component `standoff_note` non-null, standoff 55.53 unchanged (acceptance case 2 — a **second** evolved
  fixture guarding against a δ-Pav-specific artifact, F3); ε Eri MS control → component
  `standoff_note is None`; Sirius B windless → `None`.
- **CR-23.1 cross-tool (F4):** transitively covered — the FLAME-hit test already asserts
  `exclusion-boundary --star == exclusion-system --star` on the same 0.811 value, and both call the shared
  `resolve_component_mass` that `dossier` uses; WB's live re-gate does the direct
  `exclusion-boundary --star ε Eri == dossier --star ε Eri` (0.811) cross-tool check.

**Offline `tests/test_query_exclusion_system.py`** (subprocess, no network): `mass_provenance` on
`exclusion-boundary --mass-msun/--object/--spectral-type`; `--gaia-timeout` present; forced-degrade via
env; `exclusion-system --star <evolved>` `standoff_note` (using `--component` fixtures where a name would
hit the network — supply the evolved mass via `--component class=subgiant,mass=...` to keep it offline).

**Live `tests/test_query_exclusion_system_live.py`** (`SPACE_APP_RUN_LIVE=1`, opt-in): the real acceptance
anchors — `exclusion-boundary --star "epsilon Eridani" --star-mass-catalog <cat>` → 0.811/gaia_flame/≈43.69;
`exclusion-system --star "epsilon Eridani"` → same.

Run via `venv/bin/python -m pytest`. Target: full offline suite green; the whole CR-13/14/16/22 battery
byte-identical except the intended shifts.

---

## 7. Re-gate expectations (WB, live on the sister venv — for the plan-review + the build's own verify)

- **Byte-identical (α 0.4 where applicable):** Sol 47.5; α Cen A 48.966852 / B 45.721362 + bands
  54.09694 / 65.16768; Sirius A 63.45901 + B windless; Proxima 20.482354; δ Pav 47.33 + Procyon A 55.53
  (values — the last two **gain** a non-null research-grade `standoff_note`).
- **Intended CHANGES (all at `--alpha 0.4`, the re-gate convention — see §8):** ε Eri 42.51 → 43.69
  (`ms_luminosity_inversion` → `gaia_flame`) on `exclusion-boundary --star`, agreeing with
  `exclusion-system --star` + `dossier`; σ Dra / Lalande 21185 likewise; any cataloged single MS star via
  `exclusion-boundary --star` shifting inversion → catalog — **including the 4 seed stars with NO catalog
  flag**: `exclusion-boundary --star "Sirius A"` ≈ 66.7 → 63.5 (seed 2.063), `"Vega"` (seed 2.135),
  `"alpha Cen A"` (1.079), `"alpha Cen B"` (0.909). (The α Cen / Sirius *binary* anchors via
  `exclusion-system` are unchanged — they already use the seed.)
- **`mass_provenance`** on every exclusion output (the 6-value enum); **`flame_status`** surfaced on a
  forced-short `--gaia-timeout`/unreachable, both subcommands' single-body paths (never silently dropped).

---

## 8. Risks / accepted caveats

- **α for the 43.69 anchor — RESOLVED at α=0.4 (WB-CONFIRMED, MSG 254).** `exclusion-boundary` default α = **1/3**,
  but the re-gate runs this command at **`--alpha 0.4`**, and that is *provable* from WB's own numbers:
  the OLD baseline `exclusion-boundary --star ε Eri` = **42.51** = `47.5 × 0.7576540^0.4` (α=1/3 would be
  43.30), and the NEW anchor 43.69 = `47.5 × 0.811^0.4` (α=1/3 would be 44.30). Both the old and new
  anchors are α=0.4 values, and MSG 252's byte-identical list is headed "α 0.4 where applicable." So the
  build pins **43.69 at `--alpha 0.4`** for ε Eri; 44.30 is only the separate default-α spot value. **The
  load-bearing acceptance is the FLAME mass 0.811 / `gaia_flame` (α-independent); the standoff follows
  deterministically from the mass and the α passed.** No open α question — the test pins the α=0.4 anchor.
- **`mass_provenance` on a no-mass domain (windless / unmodeled / evolved-no-mass) — RESOLVED: `null`
  (WB-CONFIRMED, Greg, MSG 254).** On those domains the output has `mass_msun: null` and no standoff, so
  emit `mass_provenance: null` on `--star`/`--spectral-type` (honest: no mass resolved; identical to the
  existing `exclusion-system` per-component `mass_provenance: null` for a windless component — the
  harmonization CR-23 exists to achieve). `--object <windless>` (brown-dwarf/rogue-planet) stays
  **`object_preset`** because a preset always carries a mass (`mass_msun` is non-null there — the mass
  exists, it's just unused for a standoff). So the field is **present on every path**, `null` only where
  no mass was resolved.
- **Always-emit `mass_provenance` in `two_layer`** touches the windless/unmodeled early returns (also hit
  by `--object`/`--spectral-type`/`--star <wd>`). Additive key only; guarded by CP2 + the CR-22 battery.
- **evolved-no-mass `standoff_note` in `compose`** uses the base `_EVOLVED_NO_MASS_NOTE` (no `mass_note`
  append, unlike two_layer). Cosmetic; not in any acceptance. Documented.
- **No import cycle:** query.py (not exclusion_system) calls `stellar_mass.resolve_component_mass` for the
  exclusion-boundary MS path, so exclusion_boundary keeps importing only exclusion_wall.

---

## 9. Build sequence

1. CR-23.1 (§1a/1b/1c) → run `test_exclusion_system` + `test_query_exclusion_system` + a first cut of
   `test_cr23` → **CP1**.
2. CR-23.2 (§2a–2e) → extend `test_cr23` + subprocess tests → **CP2**.
3. CR-23.3 (§3) → finish `test_cr23` → full offline suite → **CP3** (+ whole-diff pass).
4. Docs (`integration.md`, `testing.md`, `query-commands-index.md`, `CLAUDE.md`).
5. Post build-complete on the channel (+ the α-anchor note); **hold the commit** for WB's GREEN re-gate
   + Greg's FULFILLED flip; then commit CR-23-only + push + post the SHA.

**AWAITING:** Greg — go to build (after plan-review agents run on this plan).

---

## 10. Re-gate result — ✅ FULFILLED (WB MSG 256, Greg signed, 2026-09-20)

WB ran `query.py` live on the sister venv, every input path, against the uncommitted CR-23 working tree — **GREEN**:
- Byte-identical (exact): Sol 47.5; α Cen A 48.966852301574924 / B 45.72136239364217; Sirius A 63.45901120705829 + B
  windless; δ Pav 47.32853607079087 + Procyon A 55.53456613072628 (+ non-null research-grade `standoff_note`).
- CR-23.1: `exclusion-boundary --star "epsilon Eridani"` → **0.811199 / gaia_flame / 43.686** (was 42.51), matching
  `exclusion-system --star` + `dossier` live; seed shift confirmed on Sirius A / α Cen A / α Cen B.
- CR-23.2/23.3 + all four non-blockers verified (mass_provenance every path incl. `null`; `flame_status` never silent,
  both subcommands' single-body paths; `--gaia-timeout`; `mass_note`; evolved `standoff_note`).

**Two PRE-EXISTING notes WB isolated against CR-22 `710e7cb` — NEITHER a CR-23 defect:**
1. **Proxima is a non-deterministic live-inversion anchor.** `exclusion-system --star "Proxima Centauri"` reads
   **21.582239** now (an `ms_luminosity_inversion` under a Gaia-NSS TAP timeout degrade), vs the 20.482354 recorded at the
   CR-22 re-gate — **CR-22 and CR-23 produce the identical 21.582239 right now**. It drifts with Gaia latency; not a CR-23
   change. (§7's "Proxima 20.482354 byte-identical" holds only when the Gaia NSS call succeeds → the catalog tier.)
2. **`exclusion-boundary --star "Vega"` errors `{"error":"Temperature not available …"}`** — identically on CR-22, on
   every Vega identifier. A pre-existing `regions` no-Teff data issue, before the mass chain. So although Vega IS in the
   4-star seed, it never reaches the standoff; the seed shift is demonstrated by **Sirius A / α Cen A / α Cen B** only.
   (§0/§7 name Vega as a seed star — accurate for the seed *membership*, but it errors before computing; a future
   no-Teff-handling item, out of CR-23 scope.)

Committed CR-23-only + pushed on the flip; SHA posted to the channel (MSG 257).
