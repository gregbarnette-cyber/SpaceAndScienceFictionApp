# PHASE CR-22.6 — `exclusion-boundary --mass-msun` must be finite and > 0 again (a CR-22 regression)

**Status: ✅ FULFILLED + SHIPPED (2026-09-24). WB independent re-gate GREEN (12/12 invalid inputs, NaN-row catalog, 20/20
byte-identical vs `2ecd4ea`) + Greg-FULFILLED (MSG 282). Suite 3574 passed / 102 skipped / 519 subtests / 0 failures.**

---

## 0. Confirmed diagnosis

- `query.py cmd_exclusion_boundary`, the bare-mass branch (`if args.mass_msun is not None:`, ~line 782), passes
  `args.mass_msun` straight to `exclusion_boundary.compute_two_layer_boundary`.
- `compute_two_layer_boundary` runs the FROZEN `compute_exclusion_boundary` only `if mass_msun is not None and
  mass_msun > 0`. Otherwise it takes the "no mass" branch (`r_ex_au`/`standoff_au`/`forcing_class` = null) and emits a
  full result, so the frozen generator's `M ≤ 0` check is unreachable from the CLI. `_out` sees no `error` key, so
  the exit code is 0.
- **APP probe at `2ecd4ea` (WB reproduced live):**

  | input | result |
  |---|---|
  | `0`, `-1`, `nan` | `domain main_sequence` + null standoff, exit 0 |
  | `inf` | `"r_ex_au": Infinity` (not strict JSON), `forcing_class "harbor"`, exit 0 |
- **For M ≤ 0, only the bare path is exposed.** `compute_two_layer_boundary` has one production caller (`query.py`,
  7 `two_layer(` call sites: lines 784/804/818/830/850/865/905). Every other path passes a positive mass or `None`:
  - `--object`: the preset masses are all positive.
  - `--spectral-type`: the MS table rows are parsed with `float(row.get("M"))` from the bundled table.
  - `--star`: `stellar_mass.resolve_component_mass` accepts only `> 0` at every tier, and so does
    `stellar_mass_tables` for catalog values.
  - `None` is the intended evolved-no-mass honest null, and it stays that way.
- **For NaN/inf, two other paths leak too** (plan-review finding, APP-verified and WB-verified live; both date from
  before CR-22, so neither is a CR-22 regression). MSG 274 wrongly said "no other path is exposed"; MSG 278 corrected
  it, and MSG 279 put both in scope (§3.5).
  - `exclusion-system --component "id=A,mass=inf"` (or `1e309`) gives `"r_ex_au": Infinity`, exit 0. The cause is
    `compose_exclusion_system`'s `m_ok` (`core/exclusion_system.py:318`), which checks only `m > 0`. NaN and 0 already
    error.
  - A `--star-mass-catalog` row with `"mass_solar": NaN`/`Infinity` passes `stellar_mass_tables.match_mass`'s
    `val <= 0` skip (line 112), and `json.load` accepts those tokens. The shared resolver then returns a non-finite
    `catalog` mass to every consumer: `exclusion-boundary`/`exclusion-system --star`, `dossier`, `compare-stars` and
    `binary-stability-auto`.
- **Why nothing caught it:** `test_group_q.py::ExclusionBoundaryErrors::test_mass_nonpositive` calls the frozen
  function directly. No CLI-level test covers M ≤ 0.

## 1. Contract (WB MSG 276, Greg's ruling)

The bare `--mass-msun M` path accepts only a **finite, positive** mass:

| input | output | exit |
|---|---|---|
| `M ≤ 0` (incl. `-0.0`, `-inf`) or `NaN` | exactly `{"error": "--mass-msun (or a resolved object mass) must be > 0."}` (the pre-CR-22 message) | 1 |
| `M = +inf` | exactly `{"error": "--mass-msun (or a resolved object mass) must be finite."}` | 1 |
| any finite `M > 0` | **byte-identical** to today | 0 |

The FROZEN `compute_exclusion_boundary` is untouched.

## 2. Design decision — where the guard goes

**A guard in `cmd_exclusion_boundary`'s bare-mass branch, before the `two_layer(...)` call.** This was proposed in
MSG 271 and WB agreed in MSG 276. Rejected alternative: loosening the core gate to `mass_msun is not None`. That gives
the same result for ≤ 0 today, but it changes a shared core function's contract, and it would still let NaN and +inf
through, because the frozen `M <= 0` check is False for both. The CLI guard is the narrowest change and puts the mass
error **first**, exactly as before CR-22 (then the CLI called the frozen generator, whose first check is `M ≤ 0`). So
`--mass-msun 0 --alpha -1` still reports the mass error, not the exponent error.

## 3. Changes

### 3.1 `query.py` — the guard (the only behaviour change)
Add `import math` (stdlib; alphabetical with the existing `argparse/json/os/sys` block).
```python
    # ── bare mass: no class info (classifier → main_sequence, no wall) ──
    if args.mass_msun is not None:
        # CR-22.6: compute_two_layer_boundary treats a non-positive mass as "no mass" (null standoff, exit 0), so the
        # FROZEN generator's M ≤ 0 check is unreachable from here — restore it, and require a finite mass.
        # `not (m > 0)` also catches NaN and -inf; +inf is the only non-finite value left.
        if not (args.mass_msun > 0):
            _out({"error": "--mass-msun (or a resolved object mass) must be > 0."})
            return
        if not math.isfinite(args.mass_msun):
            _out({"error": "--mass-msun (or a resolved object mass) must be finite."})
            return
        _out(two_layer(...))                                   # unchanged
        return
```
- The "> 0" message is copied from the frozen generator, which stays untouched, so no shared constant can be hoisted
  out of it. A test (§3.3) asserts the CLI string equals `compute_exclusion_boundary(mass_msun=0)["error"]`, so the
  two can't drift apart. The "finite" message is new and WB-specified, and has no frozen counterpart.
- **Out of scope, not touched:**
  - Huge finite masses that overflow `M**α` (e.g. `1e308` with a large `--alpha`).
  - Non-finite values on other flags (`--luminosity-lsun`, `--dial`, …).
  - The shared resolver's **manual** tier (`manual > 0`, e.g. `dossier --mass-solar inf`) and, more broadly, argparse
    `type=float` accepting `nan`/`inf` on many flags app-wide. Skipping a non-finite manual mass would silently swap in
    another tier's mass, which is worse; the right fix is a per-subcommand CLI guard. This is a separate, app-wide issue.
    It is noted as an FYI in the build-complete MSG (a CR-27 candidate), not fixed here.

### 3.2 `core/exclusion_boundary.py` — docstring only
`compute_two_layer_boundary`'s docstring ends: "Returns the result dict, or the frozen generator's curated
`{"error": …}` (mass ≤ 0, out-of-band exponents) for an in-domain body." That is false for mass ≤ 0, and it helped the
regression hide. Reword it so that:
- a `None`, non-positive **or NaN** mass takes the null-standoff branch (the evolved no-mass case), and **+inf is not
  rejected** by the core: it reaches the frozen generator;
- the frozen generator's curated error is returned only on the **main_sequence / evolved** domains (windless and
  unmodeled return before any validation, e.g. `--spectral-type DA2 --alpha -1` exits 0), for a positive mass with
  invalid exponents, dial, calibration, `β ≠ 0` with L ≤ 0, `mass_loss_msun_yr ≤ 0` or an unknown wind_state;
- validating a **user-supplied** mass (finite, > 0) is the caller's job (`query.py`'s bare-mass guard, CR-22.6).

No code change in this file. The FROZEN `compute_exclusion_boundary` is untouched.

### 3.3 Tests — `tests/test_query_exclusion_system.py`, new class `Cr226MassGuardCliTest`
This sits next to `Cr23MassProvenanceCliTest` (the existing CLI-level `exclusion-boundary` tests). Offline and DB-free
(the reviewer confirmed that the bare-mass and `--object sun` paths never open the DB). Also update the file's header
comment ("Offline subprocess tests"), since this class adds in-process tests.
- **Error matrix** (in-process `run_query_inproc`, the harness's path for self-validating exit-code matrices that
  never touch the DB). Each case must give exit **1** and a payload that `==` exactly the error dict (no other keys):
  - `--mass-msun 0`, `-1`, `-0.0`, `nan`, `=-inf` → the "> 0" error.
  - `--mass-msun inf` and `1e309` (float overflow → inf, a realistic typo) → the "finite" error.
  - **Verified at planning time:** `--mass-msun -1` and `-0.0` parse as values, but `--mass-msun -inf` is argparse
    **exit 2** ("expected one argument"), because `-inf` isn't number-shaped. So the test passes `--mass-msun=-inf`
    (today that gives exit 0 with a null standoff). The space-separated `-inf` staying at exit 2 is argparse
    behaviour, not a CR-22.6 concern.
- **Drift guard:** the "> 0" string `==` `xb.compute_exclusion_boundary(mass_msun=0)["error"]`.
- **Precedence:** `--mass-msun 0 --alpha -1` gives the mass error (the pre-CR-22 order), not the exponent error.
- **One real subprocess** (`run_query`) for `--mass-msun 0`: the true process exit code is 1 and stdout parses as the
  JSON error.
- **Valid-input controls (byte-identical — pin the WHOLE payload, not just `r_ex_au`):** for `0.3` (with
  `--alpha 0.4`), `1e-9`, `5e-324` (the smallest positive double) and `1e30`, compare the CLI JSON `==` a direct
  `xb.compute_two_layer_boundary(mass_msun=m, mass_provenance="manual", alpha=…, calibration_au=47.5, beta=0, gamma=0)`
  after a `json.loads(json.dumps(...))` round-trip (the same kwargs the bare branch passes). Also pin the WB anchors
  directly:
  - `--mass-msun 0.3 --alpha 0.4` → `r_ex_au == 29.345540401952064`.
  - `--object sun` → `r_ex_au 47.5` / `wall_au 6.0`.

### 3.4 Docs
- `docs/integration.md`, base `exclusion-boundary` **Validation** line: remove the "Known gap (CR-22 regression)"
  sentences and restore the pre-audit wording, with the finite rule. It should read: "`--mass-msun` ≤ 0 or NaN
  (`must be > 0`) or +inf (`must be finite`), negative exponents, non-positive dial/calibration, `β ≠ 0` with L ≤ 0, or
  a wind exponent (`γ ≠ 0`) with no wind input → exit 1", plus a one-clause provenance note: "(CR-22.6 restored the
  mass check — the CR-22 two-layer wrapper had bypassed it)".
- `docs/testing.md`: the file is one bullet per CR (the CR-11/22/23 bullets at ~lines 69/77/78 name this test file),
  so add a short **CR-22.6** bullet in that style.
- `CLAUDE.md` line 80: update the offline count (3554 → 3554 + N), the "~3653 passed" live estimate ("the 3554
  offline plus the 99 live-gated"), the "most recent addition is CR-25" lead-in (→ CR-22.6, one short sentence;
  CR-25 moves to "Before that"), and the subtest count if the matrix uses `self.subTest`. Keep it short: this is a
  regression fix, not a feature.
- Memory note `mass-msun-nonpositive-regression.md`: status updates as the arc progresses.

### 3.5 The two pre-existing non-finite-mass leaks — folded in (Greg's ruling (B), MSG 279)
- **`core/stellar_mass_tables.py` `match_mass`** (line ~112): skip a non-finite `mass_solar` row exactly as a `≤ 0` row
  is skipped: `… or val <= 0 or not math.isfinite(val)`. Add `import math`. `val <= 0` is False for NaN, so the explicit
  `isfinite` is what catches NaN and ±inf. Resolution then falls through to the next tier (FLAME → inversion). Every
  finite catalog stays byte-identical.
- **`core/exclusion_system.py` `compose_exclusion_system`** `m_ok` (line ~318): add `and math.isfinite(m)` (`math` is
  already imported). `mass=inf` / `1e309` then get the existing "component '<id>' has no resolvable mass …" error,
  exit 1, as NaN does today.
  - Check during the build: `m_ok` also gates `lone_ood_unresolved` and the in-domain point-mass sum. A lone
    out-of-domain body with inf mass now takes the "unresolved" branch. That's the correct honest-null behaviour and
    matches NaN.
- **Tests** (offline):
  - `match_mass` skips a `NaN` and an `Infinity` row loaded via `json.loads` (returns `None` for that star, and still
    matches a finite row for another star in the same catalog).
  - `resolve_component_mass` with a NaN-row catalog + `luminosity_lsun` → the inversion tier, not `catalog`.
  - CLI `exclusion-system --component "id=A,mass=inf"` and `"mass=1e309"` → the "no resolvable mass" error, exit 1.
  - The existing CR-13/14/22/23/25 anchor tests guard byte-identity for finite catalogs and components.
- **Docs:** the CR-11.2 `--star-mass-catalog` validation note and the CR-11.3 `exclusion-system --component`
  validation line in `docs/integration.md` (a non-finite catalog mass is skipped like a ≤ 0 one; a non-finite
  `mass=` is unresolvable).

## 4. `/code-review` checkpoints
- **CP1 — after §3.1 + §3.2 + §3.3** (code + tests, targeted tests green): `/code-review high` on the working tree.
  Focus: the guard's placement and precedence, the predicate (NaN / ±inf / −0.0), byte-identity of every finite
  positive input, and that the docstring now matches the code.
- **CP2 — final, after §3.4 + the full suite:** `/code-review high` on the whole diff (code + tests + docs), checking
  doc/contract accuracy against the code.

Fold each finding in or decline it with a stated reason, and re-run the affected tests after each fold.

## 5. Verification
1. Targeted tests: `venv/bin/python -m pytest -q tests/test_query_exclusion_system.py tests/test_group_q.py tests/test_cr22.py tests/test_cr23.py tests/test_cr25.py`.
2. Full suite, alone on the box (one heavy job at a time): `venv/bin/python -m pytest -q` → expect **3554 + N passed / 102 skipped / 0 failures**.
3. APP live pre-check of the WB re-gate list:
   - `exclusion-boundary --mass-msun 0` / `-1` / `nan` → the "> 0" error, exit 1.
   - `--mass-msun inf` → the "finite" error, exit 1.
   - `--mass-msun 0.3 --alpha 0.4` → 29.345540401952064.
   - `--object sun` → 47.5 / wall 6.0.
   - `exclusion-system --star "alpha Cen"` → 48.966852301574924 / 45.72136239364217 (live SIMBAD).
   - `exclusion-boundary --star "EV Lac"` → 32.7303444098 @α=1/3, `active`, wall 13.416407864998739 (live SIMBAD).
   - `--mass-msun=-inf` and `-0.0` → the "> 0" error, exit 1.
   - `exclusion-system --component "id=A,mass=inf"` / `"mass=1e309"` → the "no resolvable mass" error, exit 1.
   - A copy of WB's catalog with Barnard's `mass_solar` set to NaN → `exclusion-boundary --star "Barnard's star"`
     resolves a **finite** mass from the next tier (`mass_provenance` ≠ `catalog`). With the real catalog, Barnard's
     stays `catalog` 0.162 → 22.935045996 @α=0.4, unchanged.
   - `dossier` / `compare-stars` on a catalog star: byte-identical (spot-check one against HEAD `2ecd4ea` output).
4. Build-complete MSG to WB: suite numbers, the pre-check table, and the CP1/CP2 outcomes.

## 6. Ship
Git-hold until WB is GREEN and Greg signs the FULFILLED flip. Then commit **CR-22.6 only** on `main` (no side branch),
push, and post the SHA. Move this plan to `completed_plans/` and add it to `completed_plans/README.md` in the same
commit.

## 7. Build record

**Mechanism change vs §3.5 (disclosed to WB in MSG 280).** Tightening `m_ok` alone gave `--component mass=inf` the
message "needs a positive mass_solar", not the contract's "has no resolvable mass". To meet the contract:
- `resolve_component_mass`'s `manual_hit` requires a finite mass, so inf takes NaN's exact path (and `manual_hit`
  also gates the FLAME fetch).
- `m_ok` stays as a backstop for directly-built component dicts.

**CP1 (`/code-review high`, 7 findings).**

| # | finding | outcome |
|---|---|---|
| 1 | `lum=inf` inversion route | **fixed**, by #3 |
| 2 | a lone out-of-domain rejected numeric mass kept its stale provenance | **fixed**: now `unresolved_out_of_domain` |
| 3 | altitude: put the finite check in `resolve_mass._pos`, the one predicate every tier and consumer goes through | **fixed**. `dossier --mass-solar inf` no longer renders "inf M☉". (`compare-stars` has no `--mass-solar` flag. Full NaN parity for the dossier came only with CP2 #1, which fixed a missed `manual_hit` copy in `report.py`.) |
| 4 | docs unbuilt | the planned §3.4 step, done after CP1 |
| 5 | the compose message said "positive" for inf | **fixed**: inf → "needs a finite mass_solar"; the ≤ 0 message is unchanged |
| 6 | sibling float flags (`--luminosity-lsun inf`, `--mass-loss-msun-yr nan`) | **declined**: the app-wide argparse `type=float` issue; out of scope, documented as not covered, FYI'd to WB |
| 7 | altitude: validate inside `compute_two_layer_boundary` | **declined** (see below) |

Reasons for declining #7:
- the CLI placement is the one WB agreed (MSG 276);
- there is one production caller;
- the docstring now states the caller contract;
- the duplicated message is drift-guarded by a test.

**CP2 (`/code-review high`, 9 findings).**

| # | finding | outcome |
|---|---|---|
| 1 | a missed `manual_hit` copy in `report._resolve_star_mass_block`: inf counted as a manual hit and skipped FLAME, unlike NaN | **fixed** |
| 3 | the predicate was hand-copied at 5 sites | **fixed**: hoisted into `stellar_mass_tables.is_positive_finite`, now used by `match_mass`, `resolve_mass._pos`, `resolve_component_mass` (manual + FLAME), `compose_exclusion_system.m_ok` and the dossier `manual_hit` |
| 5 | the provenance fallback had moved from truthiness to `is None` | **fixed**: truthiness restored, so `""` still gets `unresolved_out_of_domain` |
| 6 | a caller-pre-matched `catalog_row` skipped the finite check | **fixed**: `_pos` is now applied to it |
| 8 | the CP1 record had inaccuracies | **fixed** (above) |
| 9 | extra blank lines | **fixed** |
| 2 | the dossier silently ignores a non-finite `--mass-solar` | **declined**: the same behaviour NaN has always had; a curated dossier CLI error is the FYI item for WB (CR-27 candidate), not in the ruled scope |
| 4 | altitude: validate inside the wrapper | **declined**, as CP1 #7 |
| 7 | the catalog is scanned twice in `resolve_component_mass` | **declined**: pre-existing perf, not a CR-22.6 defect |

Tests: +20 (12 CLI + 8 resolver/dossier).
