# PHASE CR-27: `--star` resolution gaps (OQ-SA-RESOLVE1)

**Status:** COMPLETE — built 2026-10-07; WB re-gate GREEN (MSG 352); Greg FULFILLED 2026-10-07; committed + pushed `8288397` (tree `ff8fde1e`, parent `eba8b1a`).
**Contract:** WB `design-lab/star-system-analysis/spaceapp-change-request-CR27-star-resolution-gaps.md` (as amended
through S83, Greg's rulings 1–12). Where this plan and the contract differ, the contract wins.
**Channel:** MSG 341 (ping), 342 (hand-off), 343 (APP's Q1–Q9), 344 (WB's answers; no contract change), 345 / 346 (the Q7 follow-up: the caller fixes, gated on the retry).
**Base:** `eba8b1a`, tree clean. Suite 3850 / 118 / 609.
**WB baseline:** 172 calls on `eba8b1a`, every "was" value reproduced.

CR-27 is one CR, so it is one commit (git-held until WB's re-gate is GREEN and Greg signs FULFILLED). It is built
in four stages, matching the four sub-CRs, with a `/code-review` checkpoint after each.

---

## 0. Ground truth (verified at `eba8b1a`)

- **Cause 1.** `core/databases.py:217` `compute_simbad_lookup` builds, through astroquery,
  `… FROM basic JOIN allfluxes … LEFT JOIN mesfe_h … JOIN ident …`. This was checked by printing
  `query_object(..., get_query_payload=True)`. **`V` is the only `allfluxes` field.** `sp_type`, `plx_value` and
  `otype` come from `basic`. Dropping `V` gives `FROM basic LEFT JOIN mesfe_h JOIN ident`, so a zero-flux object
  survives.
- **Cause 2.** `row = result[0]`, and `_safe()` reads `mesfe_h.teff` and `mesfe_h.fe_h` from that row only.
- **Cause 3.** In `query.py` `_exclusion_boundary_result`, the MS branch (≈ L1104) runs
  `regions.compute_star_system_regions_from_simbad(sl)` and returns its error **before**
  `stellar_mass.resolve_component_mass`. The evolved branch passes `lum` (manual or None) and calls
  `_cheap(lum if lum is not None else 1.0)`. `core/exclusion_boundary.py` `compute_two_layer_boundary` (≈ L424)
  passes `luminosity_lsun or 1.0` to the FROZEN generator and copies the generator's `luminosity_lsun` echo (the
  fabricated 1.0) into the result.
- **Cause 4.**
  - `ism_velocity.resolve_a_record(head, reuse)` returns one of `own` / `a` / `same` / `empty` / `failed`. Its
    lookup is `xray_catalog._identity_lookup`, which is a bounded `compute_simbad_lookup`, so an `a` outcome returns
    the **full** lookup dict for component A.
  - Today the A step feeds only CR-24's velocity (`target_velocity`) and CR-26's G12 identity (`inp.a_record`).
- **`exclusion-system`.**
  - `_resolve_system_from_star` (`core/exclusion_system.py` ≈ L1173) routes as follows:
    `_is_secondary_component` (off-MS or lettered secondary) → `_single_body_component`. Otherwise it calls
    `binary.binary_orbit(star)` and selects an orbit; if none is usable, or only a wide bond, it again goes to
    `_single_body_component`. Otherwise it composes A and B.
  - The single-body mass error text says "no Gaia FLAME" unconditionally.
  - Errors pass through `compute_exclusion_system` as whole dicts (L1389).
- **Offline isolation.**
  - `tests/conftest.py` stubs `ism_velocity._identity_seam` and `xray_catalog._identity_lookup` as **leak
    stubs** for every test.
  - It replaces `target_velocity` with an `own` no-op for tests not marked `cr24_velocity`.
  - ⚠ Consequence: a new A step on the `--star` paths would hit the leak stub in every existing offline
    in-process `--star` test. §4.6 adds a conftest default for it.
- **FLAME.** `catalog.gaia_astrophysical` returns `parameters.mass_flame` and `parameters.lum_flame`. A bounded call
  carries `gaia_bound_reason` ∈ {`timeout`, `unreachable`}, and `SPACE_APP_GAIA_FORCE_UNREACHABLE` drives it.
  `stellar_mass.resolve_component_mass` fetches FLAME only when neither a manual mass nor a catalog row hits. It
  writes `status_out["flame_status"]` only when the fetch was bounded and no mass came back.
- **The `--luminosity-lsun` help text** (`query.py:3614`) reads "Body luminosity, L_sun (default 1)".

## R. WB answers index (MSG 344). Each is folded into the body at the § given.

| Q | Ruling | § |
|---|---|---|
| Q1 | `luminosity_status` ∈ {timeout, unreachable}, top-level, present only when the luminosity-tier fetch was bounded | 3.3 |
| Q2 | `component_a_status` on the failed-A error, plus the quoted text | 4.2 |
| Q3 | `system_entry` top-level on **every** result of both subcommands (`null` by default); `{main_id, component_used, note}` when set; on `exclusion-system` the note is also appended to `notes` | 4.3, 4.4 |
| Q4 | `luminosity_provenance` only beside an emitted `luminosity_lsun`; neither key where neither exists today; no FLAME luminosity fetch on the paths that emit none | 3.3 |
| Q5 | `object` stays the user's `--star` string | 4.3 |
| Q6 | A zero-flux A candidate now reads `a`. This is intended. WB re-ran 73 names: 0 flips, and the only zero-flux objects are heads (`*  61 Cyg`, `BD+59  1915`, `* zet UMa`) | 1, 9 |
| Q7 | Callers keep their own curated missing-field error or warning. **Never "No results found"** for a now-resolving object, never a substituted default (e.g. debris-disk's 5778 K). Each caller is listed in the build report | 1.3 |
| Q8 | The mass-error text as proposed. On `exclusion-system`, the bounded wording replaces "no Gaia FLAME" **only when the fetch was bounded** | 3.2, 3.4 |
| Q7-follow-up (MSG 345/346) | Gate both caller fixes on 27.1's retry (internal `simbad_lookup_ex`), not a field signature; debris-disk error confirmed; NSS masses **null** + note (not a flag) | 1.3 |
| Q9 | The branch is chosen on the head; the single body is built from A's record, **and its domain is classified on A's record**; `binary-orbit` is not re-run; the head's `gaia_status` and no-orbit note are kept | 4.4 |

---

## 1. CR-27.1: a zero-flux object resolves (`core/databases.py`)

### 1.1 Route
In `compute_simbad_lookup`, inside the existing `_timeout_ctx(30)` and `try`:

```python
custom_simbad = _make_simbad("sp_type", "plx_value", "V", "mesfe_h", "otype")
result     = _with_retries(custom_simbad.query_object, star_name)
ids_result = _with_retries(Simbad.query_objectids, star_name)
via_retry = False
if (result is None or len(result) == 0) and ids_result is not None and len(ids_result) > 0:
    # CR-27.1: SIMBAD's allfluxes INNER JOIN drops an object with no flux row in any band (V is the
    # only allfluxes field). The name resolved (ids answered), so re-ask without V; vmag is then null.
    result = _with_retries(_make_simbad("sp_type", "plx_value", "mesfe_h", "otype").query_object, star_name)
    via_retry = True
```

- Every object that resolves today takes the unchanged first query, so its fields are byte-identical by
  construction.
- The retry runs only when the main query returns zero rows **and** `query_objectids` answered, i.e. SIMBAD knows
  the name. That is exactly the zero-flux set. A genuinely unknown name, including every `empty` A candidate,
  makes the same two calls as today and gets the same error, so it costs nothing new inside
  `_identity_lookup`'s 30 s wall-clock watchdog (CP0 F-B4 / F-C M5). Only the order of the two calls changes,
  and that changes no field.
- The retry's `result` has no `V` column, so `_safe("V")` → `None` → `vmag: null`.

### 1.2 Row reading
`row = result[0]` stays. Every per-object field (`main_id`, `ra`, `dec`, `sp_type`, `plx_value`, `V`, `otype`) is
the same on every row, because only `mesfe_h` multiplies rows.

### 1.3 Caller audit (Q7)
An audit agent read all 28 `core/` + `query.py` call sites and the 6 `gui/` sites (2026-10-07). It checked each
for what the site does with an **all-null record**: `main_id`, `ra`, `dec`, `otype` and designations set;
`sp_type`, `plx_value`, `vmag`, `ly`, `parsecs`, `teff` and `fe_h` all `None`.

**No crash anywhere.** Every `float()`, arithmetic op and string method on these fields is guarded. Most sites
either pass `None` through or reach the curated missing-field errors of
`regions.compute_star_system_regions_from_simbad` ("Temperature / Apparent Magnitude (V) / spectral type not
available").

| Verdict | Sites |
|---|---|
| SAFE (pass-through / designations only) | `databases.compute_oec`, `_resolve_gcns_row`, `binary.multiplicity_summary`, `binary_orbit` (CR-16 redirect), `binary_stability_auto`, `calculators` CR-18 centre id, `catalog.gaia_astrophysical`, `exoplanet_batch` ×3, `stellar_mass.resolve_binary_components` (B), `wikipedia`, `xray_catalog._identity_lookup`, `query._simbad_then`, `simbad-lookup`, GUI opts 1 / 2 / 3 / HWC / system-orbits |
| SAFE, curated error / warning (Q7's rule) | `exclusion_system` (head + B), `generate` real anchor, `kinematics`, `par_flux`, `report` dossier (identity "—", regions → `warn`), `star-regions`, `exclusion-boundary`, `circumbinary-hz`, `detection-completeness` (its own "app_mag is required" / "Provide --sp-type" errors), GUI opts 8 / 9 |
| **SILENT-DEFAULT, fixed in CR-27** | **`core/debris_disk.py:146 → :115`**: `teff or 5778.0` would compute a W4 upper limit for `*  61 Cyg` on an assumed solar Teff. It errored ("No results found") before. The dossier's disk section inherits it (`report.py:878`). |
| **SILENT-DEFAULT (narrow), fixed in CR-27** | **`core/binary.py:276 → :350`**: `m1_from_spectral_type(None)` → 1.0 M☉ on the Gaia NSS route, with no marker, and tier 1 of the stability selection would take those masses as ordinary `binary_orbit_m1/m2`. This fires only for a now-resolving zero-flux object that carries a Gaia DR3 id (a system entry rarely does). The SB9 route uses SB9's `Sp1`, and the WDS route handles a null distance. |

**The gate (WB MSG 346): the record came through 27.1's zero-row retry.** Gating on a field-null signature is
not exact. An object that resolves today through a non-V flux row with no spectral type, parallax or Teff would
match the signature and change, so the plan does not use it. The retry set is, by construction, exactly the set
that returned "No results found" before CR-27.1. The fact is carried **internally**, never as an emitted field:
`simbad-lookup`'s shape is unchanged.

- **Mechanism (as built).**
  - The body moved to `_simbad_lookup_impl(name) → (result, via_retry)`.
  - `compute_simbad_lookup(name)` returns the result and records `via_retry` in a thread-local
    (`databases._LOOKUP_TLS`).
  - `simbad_lookup_ex(name)` resets the flag, calls `compute_simbad_lookup` **through the module attribute**, and
    returns `(result, flag)`.
  - So every existing mock of `compute_simbad_lookup` still applies (the flag then stays False), and no test is
    repointed. That replaces the first sketch of "the sibling holds the implementation", which bypassed the mocks
    in `test_binary` and `test_binary_stability_auto` (found while building).
  - `debris_disk` and `binary._resolve_binary_identity` call `simbad_lookup_ex`.
- **Fix 1, confirmed (`debris_disk` + the dossier's disk section).** The guard sits **at the upper-limit branch**
  (where `_wise_upper_limit`'s `teff or 5778.0` would fire), not at entry, so a genuine Chen / Cotten detection at
  the head's position is still reported (CP0 F-B9). `via_retry` there → the curated route error
  `"debris-disk: '<main_id>' has no Teff, spectral type, V or parallax in SIMBAD (a multiple-system entry?) — the W4
  upper limit needs the star's Teff; query a component (e.g. '<main_id> A')"` (route `["simbad"]`). It is never
  "No results found" and never the 5778 K default. The dossier shows it as its disk-section warning. Every result
  that resolves today, including the pre-existing 5778 K fallback, is byte-identical.
- **Fix 2, redirected (`binary` Gaia NSS route): null the masses, don't flag them.** A flag would not reach the
  consumers: tier 1 of `_extract_stability_elements_full` (≈ L906) takes `companion.m1_solar` / `.m2_solar` straight
  into the selected elements, and `_mass_flags` reads only `mass_basis`.
  - `_resolve_binary_identity` reads `via_retry` from `simbad_lookup_ex`, only in its successful-lookup branch
    (never on the `--source-id` / `--ra --dec` routes; CP0 F-C M1). It passes it as a new
    `_nss_two_body_solutions(..., m1_unknown=False)` argument. `ident` is emitted verbatim as `identity`, so no
    key goes into it (CP0 F-B5).
  - `_nss_two_body_solutions` then leaves `companion.m1_solar` / `m2_solar` (and every mass derived from m1) as
    `null`. For the Thiele–Innes and SB1 branches, `comp` is `{"method", "m1_solar": null, "m2_solar": null,
    "class": null, "caveat": <note>}`, using the existing `caveat` key (solution dicts have no notes list). SB2 uses
    no m1 and is unchanged. `_apply_binary_masses` may still fill Gaia's own `binary_masses`, which is a real,
    m1-independent measurement; the build checks that path keeps its own provenance. It keeps the period and
    elements, and adds the note *"companion mass not computed — SIMBAD holds no
    spectral type for this object (a multiple-system entry?), so the primary mass is unknown"*.
  - Tier 1 then skips (it needs both masses), and tiers 2 and 3 already skip with no `sp_type` (≈ L895). The
    system falls to its no-usable-orbit path, which for a system entry is component A's single body under CR-27.4.
  - Reach today: none of the three known zero-flux heads carries a Gaia id (WB's TAP read). This guards a path
    and moves no anchor.

**Other behaviour changes (not risks; disclosed in the build report):**
- (a) The zero-flux objects now succeed: compare-stars gets an all-null entry; batch mode A moves a host from
  `unresolved` to resolved; the exclusion-system B lookup and the CR-26 identity treat a zero-flux component as a
  real record (guarded `plx`).
- (b) The 27.2 median now unblocks the regions / HZ / mass for stars with an empty row-0 Teff (Vega …). Its
  provenance labels stay `"simbad"`: the value is still SIMBAD's measurement, and the contract adds no source key
  (CR-27.2 "Output: unchanged shape").

Tests (`test_cr27_simbad.py`):
- T1.5: `debris_disk` with `via_retry` → the curated error, and `_wise_upper_limit` is not called. A today-resolving
  record with every field null but `via_retry` False still takes 5778 (byte-identical; WB's IR-only case).
- T1.6: the NSS route with `_zero_flux_retry` → `m1_solar` / `m2_solar` null plus the note; elements kept;
  `_extract_stability_elements_full` skips tier 1 → no selection. A normal star is byte-identical. The private key
  is not emitted.
- T1.8: `simbad_lookup_ex` returns `via_retry` True only on the retry path; `compute_simbad_lookup` equals `[0]`.
- T1.7: the dossier on an all-null record → exit 0, identity "—", and section warnings, with no traceback.

### 1.4 Tests (offline; `tests/test_cr27_simbad.py`, new)
`astroquery.simbad.Simbad` / `_make_simbad` are patched with a fake whose `query_object` answers by the
requested field set:

- T1.1: the zero-flux object. The first query returns an empty table; the no-`V` retry returns one row with
  null fields. Assert `main_id "*  61 Cyg"`, `otype "**"`, and `vmag`, `sp_type`, `plx_value`, `ly`, `parsecs`,
  `teff`, `fe_h` all `None`, no `error`, and exactly two `query_object` calls.
- T1.2: the first query hits, so there is exactly **one** `query_object` call and the result dict equals the
  pre-change function's output (byte-identity, recorded from the unchanged code on the same fake).
- T1.3: both queries are empty → the same `SIMBAD_NO_RESULTS_PREFIX` error text as today.
- T1.4: the retry raises → the `_network_error_msg` classification, as today.

---

## 2. CR-27.2: row 0, else the median (`core/databases.py`)

A helper beside `_safe`:

```python
def _per_measurement(col):
    """CR-27.2 — row 0's value when it holds one (byte-identical), else the median of the field's non-null values
    over every row (an even count → the mean of the two central values, in double precision), else None."""
    v0 = _safe_at(0, col)
    if v0 is not None:
        return v0
    vals = []
    for i in range(1, len(result)):
        v = _safe_at(i, col)
        if v is not None:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    return statistics.median(vals) if vals else None
```

- `_safe` is generalised to `_safe_at(i, col)` (the same mask, empty-string and `nan` checks), and `_safe(col)` =
  `_safe_at(0, col)`, so every per-object read is unchanged.
- The row-0 value goes through the same `float()` cast as today, so it stays byte-identical.
- `statistics.median` over Python floats is exact double precision, and its even-count result is
  `(a + b) / 2`. On HD 79210 it gives `-0.06000000052154064` from `-0.07000000029802322` and
  `-0.05000000074505806`.
- Applied to `mesfe_h.teff` and `mesfe_h.fe_h` only. These are the only `mesfe_h` values the lookup surfaces.
  The contract's "any other `mesfe_h.*` value" clause is vacuous today; a docstring note covers it.

**Tests** (`test_cr27_simbad.py`, fake tables mirroring WB's reads):
- T2.1: Vega-shaped (row 0 Teff empty, 47 non-null; row-0 fe_h set) → teff = the median; fe_h = row 0, unchanged.
- T2.2: VB 10: [—, 4008, 2700, 2745] → 2745.0.
- T2.3: an even count, using HD 79210's two central values → `-0.06000000052154064` exactly.
- T2.4: independence (teff from row 0, fe_h from the median).
- T2.5: no non-null rows → `None`.
- T2.6: row 0 non-null → that value even when the median differs.
- T2.7: masked and `"--"` cells are skipped.

---

## 3. CR-27.3: the mass ladder is not gated on luminosity; luminosity = best available + provenance

### 3.1 Shared helpers (`core/stellar_mass.py`)
- **`resolve_component_mass(..., status_out=…)`.** When it fetched FLAME, it also records
  `status_out["_lum_flame"]` (a positive finite `lum_flame`, else absent) and `status_out["_flame_fetched"] = True`.
  These are underscore keys: no caller copies `status_out` wholesale (verified: every reader picks `flame_status` /
  `otype_status` by name). This lets the luminosity tier reuse the mass tier's Gaia call, which matters under
  `SPACE_APP_CATALOG_CACHE=0`.
- **`flame_luminosity(designations)` → `(lum_or_None, status_or_None)`.** It gets the source id with
  `binary.gaia_source_id_from_designations`. With no Gaia DR3 id it returns `(None, None)` and makes no fetch (the
  Procyon leg). Otherwise it calls `catalog.gaia_astrophysical(source_id=…)` and returns `lum_flame` if positive and
  finite, else `None`, with `status = gaia_bound_reason` when the call was bounded. This is the same CR-19
  discipline (bounded, retry, circuit breaker) as the mass tier, because it is the same function.

### 3.2 `exclusion-boundary --star`, main-sequence branch (`query.py`)
The new order (the A step in §4 comes before all of this):

1. `reg = regions.compute_star_system_regions_from_simbad(sl)`. On error, **keep its message** as `reg_reason`
   and do not return. `star_lum = reg["bcLuminosity"]` when present, else `None`.
2. Load the catalog. Build `spec` with `luminosity_lsun = star_lum`. This is the **`regions_bc` luminosity only**:
   the supplied `--luminosity-lsun` never enters, and a FLAME luminosity never enters (rulings 7, 9(a)).
   `mass, mprov, mnote = resolve_component_mass(spec, catalog, allow_flame=True, status_out=_st)`.
3. `mass is None` → the **curated mass error** (Q8):
   > `could not resolve a mass for '<star>' (SIMBAD: <main_id>) — tried: the mass catalog, Gaia DR3 FLAME (<no
   > FLAME mass | the FLAME fetch <status>>), and the main-sequence luminosity inversion (<reg_reason | no usable
   > luminosity>); pass --star-mass-catalog with a row for it, or use --mass-msun <M☉> instead of --star`

   The error carries `flame_status` when `_st` has one, plus `system_entry` if set (§4.3). It exits 1.
   Today's behaviour is unchanged for every star whose regions step succeeds: `star_lum > 0` means the inversion
   tier always resolves, so this error is reachable only where the regions step failed.
4. **Luminosity** (`_resolve_luminosity`, a small local helper shared with the evolved branch):
   `lum_arg` → `manual`; else `star_lum` → `regions_bc`; else the FLAME luminosity → `gaia_flame`. The FLAME
   luminosity is reused from `_st["_lum_flame"]` when the mass tier fetched; otherwise it comes from
   `flame_luminosity(designations)`, which only runs when the catalog decided the mass. Else `None` / `None`.
   A bounded luminosity fetch sets `lum_status`.
   **Before the FLAME luminosity fetch** (step 4's only network call), run `standoff_arg_error` with β treated as
   0, i.e. every non-β check. A bad `--alpha`, `--dial` or `--calibration-au` then never costs a Gaia call,
   keeping CR-26 M-6 for that fetch (CP0 F-A7).
5. `err = _cheap(lum_eff)`. On the β ≠ 0 error, add `luminosity_status = lum_status` when set.
6. Continue as today, **in today's order** (CP0 F-B7): `exclusion_system.resolve_star_wind` (CR-25 otype list)
   is called before `_cheap`, as at `query.py:1122`; then the CR-26 model and two_layer. `luminosity_lsun = lum_eff` (may be `None`), plus the
   new `luminosity_provenance=` kwarg. Set `res["luminosity_status"]` when `lum_status` is set and there is no
   error.

Byte-identity check for stars that resolve today:
- `regions_bc` succeeded, so `star_lum` is the same number, the mass is the same, and `lum_eff` is the same.
- The supplied-L case is unchanged: `lum_eff = lum`.
- The FROZEN standoff gets the same luminosity, so r_ex is the same.
- The only differences are the new keys.

### 3.3 Evolved branch, other paths, and `compute_two_layer_boundary`
- **Evolved `--star`.** The mass is resolved as today. Luminosity is `manual`, else `gaia_flame` (reused from
  `_st` or fetched), else `None`. No `regions_bc` here; the contract limits it to the MS path (Procyon → `null`).
  The luminosity is resolved only **when a mass resolved**, because an evolved host with no mass emits no
  `luminosity_lsun` (Q4: no fetch). `_cheap(lum_eff)` replaces `_cheap(lum or 1.0)`, so β ≠ 0 with no source gives
  the error plus `luminosity_status`. **On a result**, a bounded luminosity fetch sets `luminosity_status` too
  (δ Pav at β 0 under the Gaia hook → `luminosity_lsun: null` + `"unreachable"`; CP0 F-A6). `two_layer(luminosity_lsun=lum_eff, luminosity_provenance=…)`.
- **Bare `--mass-msun`.** `lum` → `manual`, else `None`/`None`. Before calling two_layer, check **only** the
  β / luminosity condition (β ≠ 0 and no luminosity → the existing message), so no other error's precedence
  moves (CP0 F-A10). Today the call relies on the FROZEN generator's own check, which passes on the substituted 1.0 —
  that is the bug. Ordering stays CR-22.6's: the mass guards first.
- **`--object`.** `lum` → `manual`, else the preset → `object_preset`. Windless presets emit no `luminosity_lsun`,
  so no provenance either.
- **`--spectral-type`.** `lum` → `manual`, else the table → `spectral_type_table`. The evolved, windless and
  unmodeled spectral types emit none.
- **`compute_two_layer_boundary`** gains `luminosity_provenance=None`.
  - It is a caller-only echo. The FROZEN call still gets `luminosity_lsun if not None else 1.0`, so the `β = 0`
    standoff is untouched.
  - After the copy loop, on the with-mass path: `result["luminosity_lsun"] = luminosity_lsun` (the caller's
    value, `None` when unknown) and `result["luminosity_provenance"] = luminosity_provenance if luminosity_lsun is
    not None else None`.
  - **A defensive β guard (CP0 F-C M3):** before the FROZEN call, `beta != 0 and luminosity_lsun is None` → the
    same "--luminosity-lsun must be > 0 when --beta ≠ 0." error. A direct caller can then never get an r_ex
    computed on L = 1 beside a `null` luminosity.
  - The no-mass, windless and unmodeled paths do not emit `luminosity_lsun` today, so they gain neither key (Q4).
  - **Direct callers**: only `query.py` and the tests (`exclusion_system` calls the FROZEN generator directly).
    No test asserts `luminosity_lsun == 1.0` directly. The 1.0 lives in the A0 / CR-31 byte-identity fixtures
    (§4.8).
- **`flame_luminosity`** takes the **same** `augment_designations(...)` set the mass tier used, so the source id
  cannot differ (CP0 F-A10).
- **Help text.** `--luminosity-lsun` becomes "Body luminosity, L_sun (manual override; default: the best available
  — the SIMBAD Teff/V/parallax derivation, then Gaia DR3 FLAME — else none)".

### 3.4 `exclusion-system --star`, single-body mass error (`core/exclusion_system.py`)
The mass ladder and the inversion input are unchanged: `regions_bc` only, and no FLAME luminosity is introduced.
That is ruling 9(a) and it already holds. Only the error text and fields change:
- `_single_body_component`'s error: when `status_out.get("flame_status")` is set (the FLAME fetch was bounded),
  the text's "no Gaia FLAME" becomes "the Gaia FLAME fetch <status> (no FLAME answer)", and the error dict carries
  `flame_status`. Otherwise today's text is unchanged and there is no key (Q8 clarification).
- The off-MS lone-body note at `exclusion_system.py:1199`, "(no catalog row, no Gaia FLAME)", gets the same
  bounded wording when `_sf["flame_status"]` is set (CP0 F-A1; Q8 covers "the two existing texts"). It is
  tested.
- The no-orbit fallback's `(no usable close-companion orbit: …)` suffix keeps `flame_status` (and the
  `component_a_status` / `system_entry` keys of §4) on the rebuilt dict, instead of dropping the extra keys.

### 3.5 Tests (offline; `tests/test_cr27_exclusion.py`, new)
- The SIMBAD lookup, regions, catalog and FLAME are patched through the existing seams
  (`databases.compute_simbad_lookup`, `catalog.gaia_astrophysical`, `binary.gaia_source_id_from_designations`).
- Each test asserts the **exact** contract number by recomputing `47.5·M^α` and the walls through the real code
  path with the stubbed inputs, plus provenance and status keys.
- Coverage:
  - Acceptance 1, 2, 4: a catalog star with V null → catalog mass, `luminosity_lsun` `None` / `None`, with no
    regions call errors surfacing.
  - Acceptance 3, 5, 6: regions succeeds → `regions_bc`, and the inversion when there is no catalog row.
  - Acceptance 7, 15: FLAME mass plus `lum_flame`, reused with **one** `gaia_astrophysical` call.
  - Acceptance 8: precedence, `regions_bc` over FLAME.
  - Acceptance 9: evolved → `gaia_flame` / `None`.
  - Acceptance 10, 11, 16: the β ≠ 0 error vs supplied; the bare / `--spectral-type` / `--object` provenances.
  - Acceptance 12: EV Lac unchanged.
  - Acceptance 13:
    - the forced-unreachable mass error carries `flame_status`;
    - BL Cet gets `luminosity_status` and no `flame_status`;
    - δ Pav at β 0.5 gives the β error plus `luminosity_status`;
    - 61 Cyg A gets `flame_status` (the mass falls to the inversion).
  - Acceptance 14: the no-route stars on both subcommands. Includes HD 79210 with a FLAME luminosity but no mass,
    which errors; HD 79211 with `--luminosity-lsun 0.5`, which errors; and HD 79211 with `--beta 0.5`, which gives
    the mass error, not the β error.
  - Acceptance 17: EZ Aqr `--luminosity-lsun 0.5` → the inversion of `regions_bc`, `luminosity_lsun 0.5 manual`.
- `compute_two_layer_boundary` unit tests:
  - `luminosity_lsun=None` → result `None` / `None`, with r_ex equal to the 1.0 call at β 0;
  - the windless / no-mass paths gain no luminosity key.

---

## 4. CR-27.4: a system entry resolves to its component A

### 4.1 One shared identity step (`core/exclusion_system.py`)
```python
def resolve_star_identity(sl):
    """CR-27.4 — the --star identity in use: a letterless head runs the head → A step (ism_velocity.resolve_a_record,
    the rule CR-24 runs). Returns (sl_used, system_entry_or_None, a_lookup, error_or_None):
      own / same / empty → (sl, None, (rec, st), None)  — the head is the star (byte-identical identity)
      a                  → (A's lookup dict, {"main_id": head, "component_used": A}, (rec, st), None)
      failed             → (None, None, None, {"error": …, "component_a_status": st})"""
```
- This is the **only** place the CR-27.4 decision is made. `exclusion-boundary` (query.py) and both
  `exclusion-system` single-body paths call it. It sits beside `resolve_star_wind`, which query.py already imports.
- **A's record.** `resolve_a_record`'s `a` record is `_identity_lookup(cand)` = `compute_simbad_lookup(cand)`,
  which is the full lookup dict for A (CR-27.1 and 27.2 included). It is used directly with no second query, so
  "every numeric field = `--star "<A>"`" holds when the candidate and the A name resolve to the same SIMBAD object.
- **No recursion (CP0 F-A2 / F-B6).** The `a` record is used **as returned**, even when A's `main_id` is itself
  letterless (`BD+59  1915` → `HD 173739`) or still yields a candidate (`* alf Gem Aa`). The step runs once and
  never errors on such a record. CR-24 and CR-26 may then run their own A step for A, exactly as
  `--star "<A>"` does, so numeric parity holds. The "one lookup per call" guarantee covers the **head's** step only.
- **Reuse (CP0 F-A3 / F-B2 / F-B10).** The head's `(rec, st)` is handed on explicitly, so the head's candidate
  lookup runs **once** per call on every branch:
  - `query.py` `_ism(main_id, model, windless=False, reuse=None)`. An explicit `reuse=a_lookup` takes precedence
    over `model["_a_record"]`. This covers the windless, unmodeled and evolved branches, where `model` is `None` or
    CR-26 never ran L974.
  - `exclusion_system._single_body_component` puts `reuse` into the component's `_cr24_vel` plan, and
    `_cr24_lookup` prefers it over `wind_inputs.a_record`.
  - CR-26: `_identity()` / `_cr26_identity()` carry `a_prefetch=(rec, st)` for a `same` / `empty` head. In
    `xray_catalog.resolve_star_wind_inputs`, **only at L974** (L928 is the composed `component_a` branch, which is
    untouched), `a_prefetch` is used in place of `_identity_lookup(cand)` **only when `allow_network` is True**, so
    offline behaviour is unchanged. It also sets `inp.a_record`. `None` means absent.
  - For a system entry (`a`), A's record is the identity in use, so there is no head candidate left to reuse.
  - Equivalence: `a_candidate(head)` is the same string at every site, so a reused `(rec, st)` is what a second
    call would return when SIMBAD agrees.

### 4.2 The failed-A error (Q2)
```
{"error": "could not resolve '<star>': the SIMBAD identity lookup for the A candidate '<cand>' of '<head>' failed
 (<status>) — whether '<head>' is a multiple-system entry cannot be decided; retry when SIMBAD answers",
 "component_a_status": "<timeout|unreachable>"}
```
It exits 1. It fires on every letterless head (`same` / `empty` heads included) where the step decides identity:
- every `exclusion-boundary --star` branch: MS, evolved, windless and unmodeled. The step runs right after the
  head lookup and before classification;
- both `exclusion-system` single-body paths.

It does **not** fire on an orbit-composed `exclusion-system` system, which stays unchanged, with A's
`velocity_status` flagged by CR-24 as today.

### 4.3 `exclusion-boundary --star` (query.py)
- Right after `sl = compute_simbad_lookup(args.star)`, call `sl, sysent, a_lookup, err = resolve_star_identity(sl)`
  and return `err` if set. Everything after that reads `sl`, which is A's record for a system entry: `sp`, `ot`,
  `main_id`, `plx`, the classification, the regions luminosity, the mass ladder (designations: A's), CR-25's
  otype list (`resolve_star_wind(sp, ot, A)`), CR-26 (`_identity` → `main_id` A, so `candidate` is `None`), and
  CR-24 (`_ism(A main_id)` → `own`).
- **`--v-ism` / `--lb-cavity` (ruling 9(e)).** The A step now runs regardless. CR-24's velocity *skip* rule
  (`star_v_ism`) is untouched: the velocity lookup is still skipped for a non-measured star with a wall. Only the
  identity step runs, and under the identity hook it errors (Sirius `--v-ism 26` → the failed-A error).
- **`object`** stays `args.star` (Q5).
- **`system_entry`** is set on **every** `exclusion-boundary` result, through `_exclusion_boundary_result`'s
  single exit in `cmd_exclusion_boundary`. It is `null`, or `{"main_id", "component_used", "note"}` where `note` =
  "resolved to component A of the multiple-system entry <head> — for the merged system zone use exclusion-system
  (or --component when no fitted orbit exists)". **Errors (one rule for both subcommands; CP0 F-A5 / F-B11 /
  F-C M4):** once the A step has resolved a system entry, **every error that call returns carries the non-null
  `system_entry`**: the mass error, the β ≠ 0 error, argument errors and the catalog-load error. No error ever
  carries `system_entry: null`, so today's error dicts stay exactly equal (e.g. `test_query_exclusion_system.py`
  L204 / L207). Every non-`--star` success gets `"system_entry": null`.
- **No combined-light inversion.** This is structural: the regions step runs on A's record, never the head's.

### 4.4 `exclusion-system --star` (`core/exclusion_system.py`)
- In `_resolve_system_from_star`, the branch is chosen on the head, as today (Q9). On the off-MS branch, and on
  the no-orbit / wide-bond branch **before** `_single_body_component`:
  `sl_used, sysent, a_lookup, err = resolve_star_identity(sl)`. On `err`, return it; the no-orbit suffix keeps
  `component_a_status`.
- `_single_body_component(sl_used, …)` classifies the domain on A's record (Q9 clarification). Its velocity target
  and `_cr26_identity` are A's (`own`). `a_lookup` is passed through `_cr26_identity` as `a_prefetch` for a
  `same` / `empty` head.
- The head's `gaia_status` and no-orbit note are kept. `binary-orbit` is not re-run on A.
- `system_entry` goes into the 3-tuple meta, with the note appended to the top-level **`resolution_notes`** (CP0
  F-A9). The off-MS branch's "resolved to the single component <id>" note names A's `main_id` for a system
  entry. `compute_exclusion_system` emits
  `"system_entry"` top-level on every result (`null` by default: composed, `--component`).
- **The composed path is untouched.**

### 4.5 `dossier`
No CR-27.4 rule applies. `dossier --star "61 Cyg"` gets CR-27.1's resolving head, and its sections give their
existing curated warnings (covered by §1.3's audit and a test).

### 4.6 Offline isolation (`tests/conftest.py`)
A new autouse default, for every test **not** marked `@pytest.mark.cr27_identity`: it patches
`exclusion_system.resolve_star_identity` to `lambda sl, *a, **k: (sl, None, None, None)` (identity unchanged, no network).
This keeps every existing offline `--star` test byte-identical and leak-free. The `_identity_seam` /
`_identity_lookup` leak stubs stay. `cr27_identity` tests drive the real step by stubbing `resolve_a_record`. The
marker is registered in `pytest.ini`.

### 4.7 Tests (`tests/test_cr27_exclusion.py`, `cr27_identity`-marked)
- Acceptance 1, 2, 3, 4: a system entry → A. Every numeric field of the result equals the same stubbed run with
  `--star "<A>"`. The test runs both and compares every key except `object` and `system_entry`.
  - α Cen uses A's `regions_bc` and catalog mass, never the head's combined light.
  - 70 Oph uses FLAME, never the inversion.
- Acceptance 5: `exclusion-system` GJ 65 / 61 Cyg take the single body A, with `system_entry` set, the note in
  `notes`, and the no-orbit note kept.
- Acceptance 6: the `same` / `empty` / `own` heads get `system_entry: null`, and the result is unchanged.
- Acceptance 7: the `failed` outcome:
  - `exclusion-boundary` α Cen and δ Pav give the error plus `component_a_status`;
  - `exclusion-system` GJ 65 gives the error, not the mass error;
  - Sirius with `--v-ism 26` and with `--lb-cavity` give the error;
  - `exclusion-system` Luhman 16 (off-MS) gives the error;
  - composed α Cen gives exit 0, unchanged.
- The Q9 mirror: an off-MS-classed head with an MS A gets A's MS chain.
- The reuse test (CP0 F-C H2) is marked `cr27_identity` + `cr24_velocity` + `cr26_network`, so both duplicate
  sites are live. It counts at `xray_catalog._identity_lookup` (`ism_velocity._identity_seam` delegates to it) and
  mocks `_identity_seam` / `_velocity_seam`.
  - **Red first:** without the reuse it shows 2 lookups.
  - Cases: an MS head, a windless head, a measured-table head and an evolved head, on both subcommands.
- The `a_prefetch` test: at L974 with `allow_network=True` the prefetch replaces the call and sets
  `inp.a_record`; with `allow_network=False` it is ignored.
- An HD 173739-shaped case: the A record is letterless and used as returned, with no error.

---

### 4.8 Existing tests that move (CP0 F-B1 / F-C H1 / F-A8 / F-C L2)
- **Byte-identity fixtures, not re-recorded** (re-recording would discard the pre-change anchor):
  - `test_cr24_wiring.py::A0ByteIdentityTest::test_no_lookup_paths` (28 cases, `fixtures/cr24_a0_baseline.json`);
  - `test_cr31_wind_speed.py::Cr31ByteIdentityTest::test_no_wind_speed_byte_identical` (27 cases,
    `fixtures/cr31_no_wind_speed_baseline.json`).

  `tests/_cr24strip.py` gains a CR-27 step that runs before the compare:
  - assert `system_entry is None`, then drop `system_entry`, `luminosity_provenance` and `luminosity_status`;
  - on an `exclusion-boundary --mass-msun` case with no `--luminosity-lsun`, assert `luminosity_lsun is None` on
    the build side, then drop the key from both sides.

  Every other byte of the 55 payloads must still match. The cases whose luminosity moved from 1.0 to null are
  listed in the build report.
- **Tests that pin retired behaviour.** These are `--star` tests that assert the failed-A path exits 0 with
  `NOTE_A_FAILED` on `exclusion-boundary`, or on an `exclusion-system` single body. The build greps for
  `NOTE_A_FAILED` / `velocity_status` "unreachable" assertions on those paths and converts each to
  `cr27_identity` plus the new error. The `cr24_velocity` tests that pin a head-identity path stay valid under the
  default stub; one CR-27 counterpart is added (head → A, then `target_velocity(A)`). Each is listed in §6.
- **Other tests** that patch `databases.compute_simbad_lookup` for `debris_disk` / `binary` are repointed to
  `simbad_lookup_ex`.
- **Socket guard:** `_cr26_socket_guard`'s prefix check becomes `("test_cr26_", "test_cr27_")` (CP0 F-C M2), so
  an unmocked Gaia, VizieR or SIMBAD call in a CR-27 test fails loud.
- **Module-attribute calls (CP0 F-C M6):** `resolve_star_identity`, `ism_velocity.resolve_a_record` and
  `stellar_mass.flame_luminosity` are always called through the module, never through a `from … import`, so the
  stubs apply.
- **More tests (CP0 F-C L2):**
  - T1.7 reuses `test_report.py`'s offline harness, with the all-null `simbad=`;
  - `system_entry is None` on every non-`--star` path;
  - the no-orbit suffix keeps `flame_status`, `component_a_status` and `system_entry`;
  - compare-stars and `planetary-systems-batch` mode A on an all-null record;
  - `star-regions` on a median-filled Vega record;
  - T1.2's pre-change output is captured into `tests/fixtures/cr27_simbad_prechange.json` by running the
    **unchanged** function on the fake before the edit;
  - T1.4 patches `time.sleep` / `_with_retries` backoff so it does not wait about 6 s.

  A GUI smoke test is not added: the six GUI sites were read-verified as pass-through or curated, and a headless
  Qt run is a known memory risk on the 8 GB box.

## 5. Files touched

| File | Change |
|---|---|
| `core/databases.py` | 27.1 retry; 27.2 `_safe_at` / `_per_measurement` |
| `core/stellar_mass.py` | `_lum_flame` / `_flame_fetched` in `status_out`; `flame_luminosity()` |
| `core/exclusion_boundary.py` | `compute_two_layer_boundary(luminosity_provenance=)`; reports the caller's luminosity (**FROZEN generator untouched**) |
| `core/exclusion_system.py` | `resolve_star_identity`; single-body A wiring; error text and keys; `system_entry` meta and emission |
| `core/xray_catalog.py` | optional `a_prefetch` identity key (two call sites) |
| `query.py` | `_exclusion_boundary_result` reorder (A step, ladder-first, luminosity resolution, β check); `system_entry` on every result; help text |
| `core/debris_disk.py`, `core/binary.py` | §1.3: the retry-gated guards (curated error; null NSS masses + note) |
| `tests/conftest.py`, `pytest.ini` | the `cr27_identity` default and marker; the socket-guard prefix |
| `tests/_cr24strip.py` | the CR-27 strip and assert step (§4.8); the two A0 / CR-31 fixtures **unchanged** |
| `tests/test_cr27_simbad.py`, `tests/test_cr27_exclusion.py` (new); deliberate-change updates in `test_cr22.py` / `test_cr23.py` / `test_cr26_wiring.py` / … (listed in the build report) | |
| `docs/integration.md` (CR-27 block: the new keys, the error, the order, the hooks), `docs/testing.md` (file catalog + suite history), `CLAUDE.md` (suite count), `docs/core-modules.md` (`resolve_star_identity`, `flame_luminosity`) | |

---

## 6. Deliberate changes (the build report lists each with its test)

1. A zero-flux object resolves, with null fields: `simbad-lookup`, `dossier`, every caller.
2. An empty row-0 Teff or [Fe/H] is filled with the median, on every caller (Vega's regions and HZ now compute).
3. `exclusion-boundary --star` no longer errors on a missing Teff, V or parallax when the catalog or FLAME holds
   the mass; the new curated mass error replaces the V / Teff / spectral-table errors on no-route stars.
4. `luminosity_lsun` is `null` (never a fabricated 1.0) when nothing is known; `luminosity_provenance` is new; a
   FLAME luminosity is reported.
5. β ≠ 0 with no luminosity source → the luminosity error (bare `--mass-msun`, evolved with no FLAME L, etc.).
6. A system entry on `exclusion-boundary` gives component A (α Cen 50.22 → 48.97; 70 Oph 45.47 → 43.996).
7. A failed A lookup → exit 1 on the paths named in §4.2, including `--v-ism` / `--lb-cavity` runs.
8. The `exclusion-system` single-body mass error says "the FLAME fetch <status>" and carries `flame_status` when
   bounded.
9. `system_entry: null` appears on every successful result of both subcommands; a system entry's errors carry it
   non-null.
10. **Ordering (CP0 F-B3, F-B8), disclosed:**
    - The A step (a SIMBAD lookup) now runs before the argument checks on a letterless head. A bad `--dial` /
      `--beta` there costs one identity lookup, and under a SIMBAD outage the failed-A error comes before today's
      argument error. A full up-front check is not possible, because windless bodies are not validated today and
      the β check needs the luminosity.
    - On the MS branch, a bad `--star-mass-catalog` now errors before a regions failure (today the regions error
      came first).
11. **`debris-disk` / dossier disk** on a zero-flux object: the curated error (Q7, MSG 346).
12. **`binary-orbit` NSS** on a zero-flux object with a Gaia id: null companion masses plus the caveat (MSG 346).

---

## 7. `/code-review` checkpoints (`/code-review high` on the working tree; findings triaged and folded before the next stage)

| CP | After | Focus |
|---|---|---|
| **CP0** | this plan | 2–3 independent plan-review agents: contract coverage (27.1 acc 1–2, 27.2 acc 1–7, 27.3 acc 1–17, 27.4 acc 1–9); the order in §3.2 / §4.3; byte-identity arguments; isolation |
| **CP1** | §1 + §2 (the lookup) + the §1.3 caller fixes | the retry's byte-identity; the median; every caller on an all-null record |
| **CP2** | §3 (CR-27.3) | the ladder order, luminosity precedence, the β check placement, status keys, FROZEN untouched |
| **CP3** | §4 (CR-27.4) + conftest | the identity step on every branch, failed-A coverage, reuse, `system_entry` on every result, the composed path untouched |
| **CP4** | the whole diff, before the build report | a cross-section review plus the full default suite, and the §8 live pre-check |

## 8. Live pre-check (APP, before the build report; one heavy job at a time; `SPACE_APP_CATALOG_CACHE=0 --gaia-timeout 120 --star-mass-catalog <WB cat>`)
- `simbad-lookup` on all of WB's anchors (27.1 / 27.2 acc).
- A byte-identity sweep of `simbad-lookup` on the 22 cards' `--star` names plus the anchors. The baseline comes from
  a `git worktree add` at `eba8b1a` (main venv) and is compared with the build. **Both runs use
  `SPACE_APP_DB=<main data/space_app.db>`**, because a worktree has no DB; auto-seeding would be slow and would
  diff the Gould / GCNS-backed designations (CP0 F-C L3). The baseline sweep, the build sweep and the full suite
  run strictly one after another.
- A timing check: three `empty`-candidate heads (ε Indi, δ Pav, τ Cet) through `_identity_lookup`, to confirm the
  call count and wall time are unchanged.
- Every 27.3 / 27.4 acceptance item, live, on both subcommands, including the three forced-failure hooks.
- The regression battery (Sol, ε Eri, Proxima, EV Lac α 1/3 and 0.4, the presets, M5V, G2V, Sirius, Procyon,
  δ Pav, composed α Cen and 70 Oph, EZ Aqr).
- `61 Cyg` through every §1.3 caller that a `--star`-style CLI reaches.

## 9. Risks and accepted caveats
- **One extra SIMBAD query, only for a zero-flux object** (the retry is gated on `query_objectids` answering). An
  unknown name or an `empty` candidate costs nothing new. `_timeout_ctx(30)` is a per-socket default, not a wall
  clock; the wall clock is `_identity_lookup`'s 30 s watchdog, which an `empty` candidate does not newly stress.
- **A SIMBAD outage now fails a letterless `--star`** where it used to return head values. This is deliberate
  (rulings 2, 9(b), 9(e), 10(b)).
- **One extra Gaia call** where a catalog mass meets a missing `regions_bc` luminosity (BL Cet, UV Cet, Ross 248,
  δ Pav, Procyon has no id so no call). Bounded, and flagged on `luminosity_status`.
- **Live catalog drift.** WB's anchors rest on SIMBAD and Gaia content at the review. A moved value is checked
  against a fresh read first.
- **No known star exercises the Q9 mirror.** It is covered by a unit test only.

## 10. Build sequence (after the CP0 fold and Greg's go)
1. §1 + §2 with their tests (red first: T1.1 and T2.1–T2.3 fail on the unchanged code), then the §1.3 caller
   fixes, then **CP1**.
2. §3 and its tests, then **CP2**.
3. §4, the conftest default and the tests, then **CP3**.
4. Docs, then **CP4**, the full default suite, the §8 live pre-check, then the build report on the channel
   (fingerprint `git diff eba8b1a | md5sum` and a `write-tree`), all git-held.
5. WB re-gate, then Greg's FULFILLED, then one commit (CR-27 only; this plan file excluded and moved to
   `completed_plans/` in a close-out docs commit), then the push and the SHA to the channel.

## 11. Review record
**CP0, 2026-10-07: three independent review agents** (contract coverage; code correctness and byte-identity;
tests and isolation), plus the Q7 follow-up with WB (MSG 345 / 346). There were 2 HIGH findings, both test-side,
and every finding is folded:

| ID | Sev | Finding | Fold |
|---|---|---|---|
| C-H1 / B-1 | HIGH | A0 (28) and CR-31 (27) byte-identity fixtures fail on the new keys and the 1.0 → null change | §4.8 strip step; fixtures kept |
| C-H2 | HIGH | the reuse-count test is vacuous under the conftest (network off, `target_velocity` stubbed) | §4.7 markers, counting site, red first |
| A-1 | MED | the off-MS note at L1199 still says "no Gaia FLAME" when bounded | §3.4 |
| A-2 / B-6 | MED/LOW | "A's main_id carries a letter" is false (HD 173739) | §4.1 no recursion; test |
| A-3 / B-2 / B-10 | MED | reuse not wired on the windless / evolved / measured-hit branches; L928 is dead | §4.1 explicit `reuse=`; `a_prefetch` at L974 only |
| A-4 / C-M1 / B-5 | MED/LOW | the binary flag was a substituted default; it leaked into `identity`; the coords routes | MSG 346 redirect: null masses + `caveat`, gated on the retry |
| A-5 / B-11 / C-M4 | MED | `system_entry` on errors unspecified | §4.3 one rule |
| B-3 | MED | the A step comes before the arg checks (CR-26 M-6) | §6 item 10, disclosed |
| B-4 / C-M5 | MED | the retry doubles `empty`-candidate cost under the 30 s watchdog | §1.1 retry gated on `query_objectids` |
| C-M2 | MED | no socket guard on `test_cr27_*`; T1.7 offline harness | §4.8 |
| C-M3 | MED | β ≠ 0 with a null luminosity passes inside `compute_two_layer_boundary` | §3.3 defensive guard |
| C-M6 | MED | the conftest lambda signature; module-attribute calls; `a_prefetch` offline semantics | §4.6, §4.8, §4.1 |
| A-6 | LOW | the evolved result's `luminosity_status` | §3.3 |
| A-7 | LOW | the FLAME luminosity fetch before the arg checks | §3.2 non-β checks first |
| A-8 / C-L2 | LOW | tests pinning the retired failed-A exit 0; coverage gaps | §4.8 |
| A-9 | LOW | `resolution_notes`, not `notes`; the head-named note | §4.4 |
| A-10 | LOW | `flame_luminosity` designations; the bare-mass β-only check | §3.3 |
| B-7 | LOW | CR-25 order relative to `_cheap` | §3.2 step 6 |
| B-8 | LOW | catalog-load vs regions error precedence | §6 item 10 |
| B-9 | LOW | debris guard placement (it would suppress a detection) | §1.3 at the UL branch |
| C-L3 | LOW | worktree baseline DB; sequencing | §8 |

## 12. Build log (2026-10-07, Greg's go, also relayed by WB in MSG 348; MSG 349 "build started")

### Stage 1: CR-27.1 + 27.2 + the §1.3 caller fixes
- **Red first:** `tests/test_cr27_simbad.py` failed 14 of 18 on the unchanged code. The pre-change fixture
  `tests/fixtures/cr27_simbad_prechange.json` was captured from the **unchanged** function on
  `tests/_cr27fakes.py`.
- **Built:**
  - `databases._simbad_lookup_impl` holds the retry, gated on `query_objectids`.
  - `_per_measurement` reads row 0, else the median.
  - The rows are bound to `table`, because `result` is later rebound to the output dict and `_safe("otype")`
    runs after that.
  - The thread-local `simbad_lookup_ex` (§1.3 as built).
  - The debris-disk guard sits at the upper-limit branch; the binary NSS change gives null masses plus the
    caveat.
- **CP1 (`/code-review high`), 9 findings:**
  - **Fixed:**
    - #1 the Gaia `binary_masses` FILL was lost behind the placeholder. The placeholder is now applied only
      after `_apply_binary_masses(None, …)`.
    - #2 the SB9 SB1 route had the same 1.0 default when `Sp1` is blank. It now takes `m1_unknown` too.
    - #3 the gate is now "the sp type decodes no mass" (`_m1_decodes`), not "sp empty".
    - #4 the debris text overclaimed. It is now "has no Teff in SIMBAD and no flux row …", and `route_tried`
      keeps the VizieR routes. This rewords the MSG 345 text; the build report notes it.
    - #6 / #7 the placeholder `method` follows the real branch order, and `class` / `low_significance` come from
      `classify_companion(None)` ("unknown", False).
  - **No change:**
    - #5: an emitted marker instead of the thread-local. WB MSG 346 ruled the fact internal, and the 28 + 6
      caller audit covers every other caller.
    - #8: Teff and [Fe/H] read independently. The contract says so explicitly: "A star's `teff` and `fe_h` may
      now come from different rows".
  - **Deferred to stage 4:** #9 the docs and suite count.
  - New tests: the Gaia fill, the SB9 blank `Sp1`, `DA` undecodable, the SB1-row label and class.
- Stage-1 tests: `test_cr27_simbad.py` 25 passed. The binary, CR-19, stability-auto, debris, designation-harness
  and databases suites are green.

### Stage 2: CR-27.3
- **Built:**
  - `stellar_mass._fetch_flame` is the **one** FLAME fetch, used by both the mass tier and `flame_luminosity`.
  - `status_out` gains the private keys `_flame_fetched`, `_lum_flame` and `_lum_flame_status`.
  - `flame_fetch_phrase` gives the one bounded wording.
  - `compute_two_layer_boundary(luminosity_provenance=)` passes the luminosity **through unchanged**: the FROZEN
    generator already refuses β ≠ 0 with `None`, in its own order. The result echoes the caller's value.
  - `query._exclusion_boundary_result`:
    - the MS branch is ladder-first, with the regions reason kept for the mass error;
    - `_resolve_lum` gives manual > regions_bc > gaia_flame > None;
    - `_pre_lum_checks` (`_cheap(1.0)`) runs before the luminosity fetch;
    - `luminosity_status` goes only on a result or the β/L error;
    - the evolved branch is resolved only with a mass.
  - `system_entry: null` is emitted on every success of both subcommands. It was pulled forward from stage 3 so
    the A0 / CR-31 fixtures could be checked.
  - The `exclusion_system` single-body error and the off-MS note use the bounded wording only when
    `flame_status` is set, and the no-orbit suffix keeps the marker keys.
- **Tests:**
  - `tests/test_cr27_exclusion.py` (stage-2 classes).
  - `_cr24strip.cr27_normalise` covers the A0 (28) and CR-31 (27) fixtures, which are unchanged.
  - `test_query_exclusion_system.py::Cr226MassGuardCliTest::test_finite_positive_masses_are_byte_identical` now
    expects `system_entry: null` on the CLI side. This is a deliberate test update.
  - The socket guard covers `test_cr27_*`.
- **CP2 (`/code-review high`), 10 findings, all fixed:**
  - #1 `luminosity_status` was leaking onto unrelated argument errors.
  - #2 the pre-fetch check missed the mass-loss / wind-state checks. It is now the full `_cheap(1.0)`. A run with
    both β ≠ 0 / no luminosity and a bad `--mass-loss-msun-yr` now reports the mass-loss error first; that is an
    edge case.
  - #3 a raising mass fetch was retried by the luminosity tier. An attempt now counts as fetched.
  - #4 the duplicate β guard is removed; the frozen generator does it.
  - #5 the duplicate FLAME fetch is replaced by `_fetch_flame`.
  - #6 / #7 the normaliser now checks provenance-beside-luminosity and a manual provenance on a supplied
    luminosity; bare detection is no longer positional.
  - #8 the wording is now "the Gaia FLAME fetch timed out / was unreachable".
  - #9 the MS branch's dead state is removed.
  - #10 the `compute_two_layer_boundary` docstring is updated.

### Stage 3: CR-27.4
- **Built:**
  - `exclusion_system.resolve_star_identity`, the one decision. It returns `system_entry` with its note.
  - `a_prefetch(main_id, a_lookup)` is keyed by the candidate string.
  - `_with_system_entry` / `_note_system_entry`.
  - Both single-body paths run the A step, branching on the head; the off-MS note names A.
  - `_cr24_vel.reuse`.
  - `query._exclusion_boundary_result` is a thin wrapper over `_exclusion_boundary_core(args, cr27)`. It runs the
    A step right after the head lookup and attaches `system_entry` to every result and every error of the call.
  - `_ism(reuse=…)` and `_identity(a_prefetch=…)`.
  - `xray_catalog` L974 uses the keyed prefetch only for the same candidate and only online. L928 (composed
    `component_a`) is untouched.
  - `compute_exclusion_system` attaches `system_entry` to every error after resolution, including a CR-26 data
    error.
  - conftest `_cr27_identity_isolation` and the `cr27_identity` marker.
- **Tests:**
  - `test_cr27_exclusion.py` CR-27.4 classes. The one-lookup test is **red first** (2 lookups without the
    reuse, verified with a temporary plugin).
  - `test_cr26_network.py::IdentityTest::test_no_results_prefix_drift` now inspects `_simbad_lookup_impl` (the
    body moved). This is a deliberate test update.
  - No existing test pinned the retired failed-A exit 0. The grep for `NOTE_A_FAILED` / `SIMBAD_IDENT_FORCE` found
    none outside `test_cr26_network`'s seam test.
- **CP3 (`/code-review high`), 9 findings:**
  - **Fixed:**
    - #1 and #4: `system_entry` was missing on later errors (exclusion-system compose / argument errors; a CR-26
      data error on both subcommands). Both wrappers now attach it.
    - #3: the end-to-end hand-off test was missing. `Cr274HandoffTest` spies `resolve_star_wind_inputs` on both
      subcommands.
    - #5: the misleading comment.
    - #6: the prefetch is now keyed by its candidate string.
    - #7: the note is built once, in `resolve_star_identity`.
    - #9: the offline-prefetch test was vacuous. It now asserts on `measured_ids`, and a different-candidate case
      was added.
  - **No change:**
    - #2: the A step runs before the argument checks. This was disclosed in plan §6 item 10 and accepted by WB in
      MSG 347 / 348.
    - #8: the `cr27` holder is a stylistic choice. It is documented and carries state across the many early
      returns.

### Stage 4: docs, CP4, live pre-check
- **Docs:**
  - `docs/integration.md`: the `exclusion-boundary` contract paragraph, `simbad-lookup` CR-27.1 / 27.2, and a new
    CR-27 block after CR-24.
  - `docs/testing.md`: the CR-27 file entry and the suite-history line.
  - `docs/core-modules.md`.
  - `CLAUDE.md`: the suite count, and the live estimate ~4024.
- **Full default suite (before CP4):** 3910 passed, 118 skipped, 626 subtests, 0 failures. A
  `QThread: Destroyed while thread '' is still running` core dump appears **after** pytest's summary, at Qt
  teardown from the GUI tests; whether `eba8b1a` does the same is still to be checked.
- **CP4 (`/code-review high`, whole diff), 10 findings; no cross-stage bug:**
  - **Fixed:**
    - #2 the Gaia `binary_masses` m1-only cross-check is kept on the placeholder.
    - #3 a malformed FLAME `parameters` payload is a miss, not a crash.
    - #4 the thread-local's same-thread requirement is documented.
    - #6 `exclusion_boundary.BETA_LUM_ERROR` is one constant, pinned equal to the FROZEN text by a test.
    - #9 the dead outer `except` is removed.
    - Three tests were added.
  - **No change:**
    - #1 a zero-flux A candidate now reads `a`: WB Q6 ruled this intended, and found 0 among 73 names.
    - #5 the provenance tag is the caller's by design.
    - #7 a zero-flux head pays the double lookup every head already pays.
    - #8 the same / empty path is covered by the `cr27_identity` tests and the live check.
    - #10 the conditional SB9 call keeps the existing 3-argument test mocks.
- **Live pre-check (§8; WB's catalog, `SPACE_APP_CATALOG_CACHE=0`, `--gaia-timeout 120`), 70 calls:**
  - **These match WB's anchors:**
    - every 27.1 / 27.2 item;
    - every 27.3 standoff, mass, luminosity and provenance (BL Cet / UV Cet / Ross 248 null L; Vega 80.394…
      `regions_bc`; HD 219134 and VB 10 on both subcommands; HD 19902 and ρ CrB `gaia_flame`; 61 Cyg A
      `regions_bc`; δ Pav 1.2535083293914795; Procyon null);
    - the β cases (δ Pav 52.98911711054116);
    - the hook cases (`flame_status` / `luminosity_status` placement exactly as acceptance 13);
    - the 14 no-route errors;
    - every 27.4 item, including both subcommands, the hooks, and composed α Cen / 70 Oph unchanged;
    - the dossier; the battery (Sol, ε Eri 43.68623962821011, Proxima + wall, EV Lac α 0.4 / ⅓ + wall, M5V,
      G2V, the presets, Sirius + wall, α Cen walls);
    - debris-disk's curated error.
  - **These differ from the contract:** the walls of BL Cet (3.4067 vs 2.9205), UV Cet (2.5253 vs 2.1438),
    Ross 248 (1.8870 vs 2.4744), HD 19902 (6.2229 vs 18.9520) and EZ Aqr (3.4067 vs 2.6318).
    - The cause: HEASARC was unreachable during the run (`wind_model.xray.status: "unreachable"`), so the CR-26
      tier fell to `class_default`.
    - The same run on `eba8b1a`'s `exclusion-system --star "BL Cet"` gives the identical 3.40666710760275.
    - `exclusion-boundary` equals `exclusion-system` on the same run (cross-path parity holds).
    - This is archive state, not CR-27. WB is to score the walls on a responsive HEASARC.
- **`simbad-lookup` sweep:** 74 names; 60 identical, 11 with a null `teff` / `fe_h` filled, 3 newly resolving
  (`61 Cyg`, `BD+59 1915`, `Mizar`), 0 other differences.
- **The `eba8b1a` worktree** gives the identical walls for UV Cet, Ross 248, HD 19902 and EZ Aqr with xray
  unreachable. Its suite gives 3850 / 118 / 609 and the **same QThread teardown dump**, so the dump is
  pre-existing.
- **Final suite:** 3913 passed, 118 skipped, 626 subtests, 0 failures.
- **Build:** tree `ff8fde1e68c5f50a40a7cf9f252db716336826c7`, diff md5 `4ca45bb596f8973db3bc9b6fde04c194`, 23
  files.
- **The build report went to WB as MSG 350.** Git-held.

- **Close:** WB re-gate GREEN (MSG 352, live with HEASARC healthy; all five walls exact). Greg signed FULFILLED. The CR-27
  commit is `8288397` (tree `ff8fde1e`, parent `eba8b1a`), pushed `eba8b1a..8288397`. Two items went to later CRs (WB MSG
  352): CR-29 — `exclusion-system --star "Mizar"` takes the single body `* zet01 UMa` (the SB2 pair's light);
  CR-33 — `resolve_mass` labels a null mass `ms_luminosity_inversion` (this predates CR-27).
