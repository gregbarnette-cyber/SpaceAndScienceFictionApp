# IMPROVEMENT_PLAN — Accuracy, Efficiency & Consistency Pass

**Status:** planned 2026-07-04, not yet implemented.
**Provenance:** full-project review (6-way parallel audit of core/, query.py, gui/, docs/, tests/) run on
commit `ed0b1d1`. Line numbers below are as of that commit — **always re-locate with the given grep
pattern before editing**; do not trust raw line numbers.

## Ground rules for the implementer

1. **Do NOT touch `main.py` feature functions or anything OEC-related.** The CLI menu is no longer
   used (user decision 2026-07-04) and OEC (opt 7) is broken pending a ground-up rebuild. Bugs that
   exist in both `core/` and `main.py` copies get fixed **only in `core/`**. Leave `OecPanel`
   (`gui/panels/catalogs.py`), `main.py:2129`'s OEC import, and `MENU_OPTIONS["7"]` alone.
2. **Interpreter:** run everything with `venv/bin/python` (system python lacks PySide6/pyvo).
   Full suite: `venv/bin/python -m pytest` (also verify `venv/bin/python -m unittest discover -s tests`
   still collects — the suite is pure unittest and must stay dual-runner).
3. **Downstream consumer:** the sibling `scifiWorldBuilding-Claude` repo shells out to `query.py`
   and parses the JSON. Any change to a subcommand's flags, keys, exit codes, or numeric output
   **must** be reflected in `docs/integration.md` (the contract file — read the relevant section
   before touching any subcommand). Never remove a flag or key; add aliases/keys instead.
4. **Test anchors are golden pins.** Many tests pin exact numeric outputs. When a legitimate
   accuracy fix changes an output, update the pin **and** say so in the commit message; when a test
   pin encodes the *old wrong* value, that is expected collateral — but if a fix breaks a pin you
   didn't predict, stop and investigate before "fixing" the test.
5. **Commit per phase** (repo convention: one commit per completed phase, e.g.
   `"Improvement plan Phase 1 implemented"`). Run the full suite before each commit.
6. Work through phases in order. Within a phase, items are independent unless noted.

## Decision points (defaults chosen; flag to the user only if you disagree)

- **D1 — year constant (P1.3):** Option A (relabel/comment-fix only, no numeric change) is the
  default. Option B (unify all conversions on the true Julian 8766.0) changes ~0.002% of every
  ly/hr↔×c output, breaks golden pins in the calculator/Honorverse/route tests, and changes values
  the downstream repo may have cached — **do not do Option B without asking the user.**
- **D2 — legacy regions calibration (P1.5):** document, don't change. The `2.52` luminosity base,
  `4.85` zero-point, and mismatched M–L exponents (`0.2632` vs `3.5`) are legacy conventions the
  alternate-HZ divisors were tuned against. Changing them shifts every region table. Comment-only.
- **D3 — CLAUDE.md context diet (P5.4):** creating `docs/testing.md` and trimming CLAUDE.md is
  in-scope; **demoting the five `@`-included docs is NOT** — leave the `@docs/...` lines alone
  unless the user separately approves.
- **D4 — output-shape standardization (P4.4):** additive only. Add missing `model_note` keys;
  never rename or remove existing note keys.

---

## Phase 1 — Confirmed accuracy bugs

### P1.1 Angular-diameter exponentiation bug (HIGH)
- **File:** `core/regions.py` (~line 157). Grep: `57.3 \*\* (`
- **Bug:** `starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)` — exponentiation where the
  small-angle formula needs multiplication. Sun renders ~1.04° instead of ~0.53°, and the error is
  non-linear across stars.
- **Fix:** `57.3 ** (...)` → `57.3 * (...)`. (Optionally use `math.degrees(d/D)` = 57.2958 —
  but 57.3 is the documented convention; keep `57.3 *` to minimize doc churn.)
- **Do not** fix the four `main.py` copies (ground rule 1).
- **Verify:**
  - `grep -rn "57.3" tests/` — update any pinned `starAngularDiameter`/"Size of Sun" values in
    `tests/test_regions.py` (and anywhere else) to the corrected numbers. Compute expected by hand:
    Sol path (opt-13 constants) should now give ≈ 0.53°.
  - `docs/star-system-regions.md` documents the formula as `57.3 ** (...)` in the
    Earth-Equivalent-Orbit section — grep `57.3` in `docs/` and fix the formula text to `57.3 ×`.
  - Run: `venv/bin/python -m pytest tests/test_regions.py tests/test_query_expanded.py tests/test_query_exposure_additions.py tests/test_report.py`
  - Spot-check: `venv/bin/python query.py sol-regions` — `sizeOfSun`-related field ≈ 0.53°.

### P1.2 `compute_cooling_hz` raw KeyError (HIGH)
- **File:** `core/cooling.py` (~lines 326-328). Grep: `ctrl_entry_teff`
- **Bug:** `_chz_band`'s `hi <= lo` early return emits keys `ctrl_entry_teff`/`ctrl_exit_teff`, but
  the consumer `_mode_chz` (grep `band\["ctrl_inner_oor"\]`, ~lines 548-549) unconditionally reads
  `ctrl_inner_oor`/`ctrl_outer_oor` (the keys the sibling return at ~line 338-339 correctly uses).
  On that branch the self-validating module raises an uncaught `KeyError`.
- **Fix:** change the early return to
  `{"chz_inner_au": None, "chz_outer_au": None, "ctrl_inner_oor": None, "ctrl_outer_oor": None}`.
- **Verify:** add a unit test in `tests/test_cooling_hz.py` calling `_chz_band` directly with inputs
  forcing `hi <= lo` (or, if unreachable via public API with the bundled tracks, test the private
  function with a synthetic degenerate track) and assert the returned dict has the
  `ctrl_inner_oor`/`ctrl_outer_oor` keys. Run `tests/test_cooling_hz.py tests/test_query_cooling_hz.py`
  in full — the Phase U/AD golden pins (incl. the Δt=0 byte-identical pin) must be untouched.

### P1.3 Year-constant mislabel (Option A — relabel only, no numeric change)
- **Files:** `core/calculators.py` (~line 17, grep `HOURS_PER_JULIAN_YEAR =`),
  `core/science.py` (~line 11, same grep), `core/calculators.py` (~line 109, grep `# 8765.82`).
- **Bug:** `HOURS_PER_JULIAN_YEAR = 8765.8128  # 365.25 * 24` — the comment is false
  (365.25 × 24 = 8766.0); 8765.8128 ≈ the tropical year (365.2422 × 24). Meanwhile
  `format_travel_time`'s `HOURS_PER_YEAR = 365.25 * 24` (= 8766.0, its `# 8765.82` comment is also
  wrong), `equations._SEC_PER_YEAR`, and `calculators._SEC_PER_JULIAN_YEAR` all use the Julian year.
- **Fix (behavior-preserving):**
  1. Correct both comments on the 8765.8128 constant to:
     `# 8765.8128 = 365.2422 × 24 (tropical year) — legacy ly/hr↔×c anchor; NOT 365.25×24 (=8766.0).`
     `# Golden pins and the downstream consumer depend on this exact value; see IMPROVEMENT_PLAN D1.`
  2. Fix the `format_travel_time` comment `# 8765.82` → `# 8766.0 (Julian year)`.
  3. Do **not** rename the constant (it's referenced across calculators/science/tests/docs); the
     corrected comment carries the fact.
  4. `docs/calculators.md` "Shared velocity conversion constant" section states
     `8765.8128 = hours in a Julian year (365.25 × 24)` — correct that sentence (grep `8765.8128`
     in `docs/`), noting it is the tropical-year value kept for output stability.
- **Verify:** no test changes expected (`git diff` should show comments/docs only). Run
  `tests/test_calculators.py tests/test_honorverse_expansion.py` as a canary.

### P1.4 Imprecise AU→km in regions (MED)
- **File:** `core/regions.py` (~line 149). Grep: `149000000`
- **Bug:** `distKM = distAU * 149000000.0` is 0.4% low — the only AU value in the app that isn't
  `_KM_PER_AU` (149597870.7). Feeds the displayed Distance KM and the (now-fixed) angular diameter.
- **Fix:** import/use the canonical value: `distKM = distAU * 149597870.7` (or import `_KM_PER_AU`
  from `core.equations` — preferred, single source of truth).
- **Verify:** grep tests for pinned `distKM`/Distance-KM values (likely `test_regions.py`,
  `test_query_expanded.py` `star-regions-manual`/`sol-regions` pins) and update. Update the
  formula line in `docs/star-system-regions.md` (`distKM = distAU × 149000000`). Combined with
  P1.1, re-verify the Sol angular size ≈ 0.53°.

### P1.5 Legacy regions calibration — document only (D2)
- **File:** `core/regions.py` (~lines 136-141).
- Add a short comment block above `bcLuminosity` noting, without changing values:
  - base `2.52` vs exact `100^(1/5) = 2.511886` (+~0.3%/mag compounding),
  - zero-point `4.85` (legacy M_bol,☉; IAU 2015 is 4.74) → Sol computes to ≈1.085 L☉,
  - `stellarMass = L**0.2632` (1/3.8) vs `luminosityFromMass = M**3.5` intentionally don't invert,
  - the alternate-HZ divisors are calibrated against these conventions — do not "fix" piecemeal.
- Also: reconcile the solar-Teff comment story — Kopparapu's 5780 is correct per the paper (leave);
  add a one-line comment where 5778 is used (`compute_star_luminosity`, regions `calculatedLuminosity`)
  that 5778 is the legacy convention vs IAU nominal 5772 used by `cooling`/`par_flux`. No numeric changes.
- **Verify:** comments only; `git diff` must show no executable-line changes in this item.

---

## Phase 2 — SQLite & dust efficiency

### P2.1 Connection PRAGMAs
- **File:** `core/db.py`, in `get_conn()` right after `sqlite3.connect(...)` (grep `check_same_thread`).
- **Add:**
  ```python
  conn.execute("PRAGMA journal_mode=WAL")
  conn.execute("PRAGMA synchronous=NORMAL")
  conn.execute("PRAGMA temp_store=MEMORY")
  ```
  Rationale: the GCNS (~331k-row) and Hypatia (~245k-row) single-transaction imports currently run
  under DELETE-journal + `synchronous=FULL`. WAL+NORMAL keeps committed-transaction durability
  (the validate-before-destroy gates rely on transaction atomicity, which WAL preserves) while
  cutting fsync overhead substantially.
- **Caution:** WAL creates `-wal`/`-shm` sidecar files next to `space_app.db` (gitignored `data/`
  — confirm `.gitignore` covers `data/` wholesale; it does). Tests point `SPACE_APP_DB`/`_DB_PATH`
  at tmp files — sidecars there are harmless.
- **Verify:** full suite; then time an import-shaped operation if convenient (not required).

### P2.2 `gcns_stars.star_name` index
- **File:** `core/db.py`. Two touch points: the `CREATE TABLE gcns_stars` DDL block's index list, and
  the idempotent `_migrate_schema` (grep `_migrate_schema`) so existing databases pick it up.
- **Add:** `CREATE INDEX IF NOT EXISTS idx_gcns_stars_star_name ON gcns_stars (star_name COLLATE NOCASE)`.
  Rationale: `_resolve_gcns_row` (grep `COLLATE NOCASE` in `core/databases.py`) full-scans ~331k rows
  on every name-based GCNS lookup.
- **Caution:** the query must actually use the index — the lookup is `WHERE star_name = ? COLLATE NOCASE`;
  an index declared `COLLATE NOCASE` matches it. Confirm with
  `EXPLAIN QUERY PLAN` in a scratch script against the real `data/space_app.db` (read-only check).
- **Verify:** `tests/test_gcns.py tests/test_simbad_gcns_enrichment.py tests/test_query_phase_t.py`.

### P2.3 `compute_gcns_system` N+1
- **File:** `core/databases.py` (grep `def compute_gcns_system`). Replace the per-member
  `SELECT ... WHERE gaia_source_id = ?` loop with one
  `SELECT ... WHERE gaia_source_id IN (<placeholders>)` and a dict keyed by source_id.
  Preserve output ordering and the `in_gcns_stars = 0` retained-member behavior exactly.
- **Verify:** `tests/test_gcns.py` (system-viewer contracts) must pass unchanged.

### P2.4 Thread-safety: shared connection + global socket timeout
- **File:** `core/db.py`: the module-global `_conn` is shared across GUI worker threads with
  `check_same_thread=False` and no serialization.
  **Fix:** add a module-level `threading.RLock`; acquire it inside `get_conn()`-returning wrapper?
  No — simplest robust fix: expose a `db_lock = threading.RLock()` and take it in the write paths
  (importers) while leaving short reads unlocked, **or** (preferred, still simple) make `get_conn()`
  return thread-local connections (`threading.local()` holding one connection per thread; WAL makes
  concurrent readers + one writer safe). Choose the thread-local approach; keep `_DB_PATH`
  monkeypatchability intact (tests swap `core.db._DB_PATH` — the thread-local cache must key on the
  path or be reset when `_DB_PATH` changes: store `(path, conn)` and reopen if path differs).
- **File:** `core/shared.py` `_timeout_ctx` (grep `setdefaulttimeout`): mutates the process-global
  socket timeout — races between concurrent GUI network threads.
  **Fix (conservative):** keep `_timeout_ctx` for the astroquery paths that offer no per-request
  timeout (SIMBAD `query_object`), but add a module `threading.Lock` held for the duration of the
  context so two threads can't interleave set/restore. Do not attempt to remove it wholesale.
- **Verify:** full suite (tests monkeypatch `_DB_PATH` heavily — the thread-local keying on path is
  the part most likely to break them; `tests/test_db_backups.py`, `tests/test_gcns.py`,
  `tests/test_hypatia_cache.py`, `tests/test_projects.py` are the canaries).

### P2.5 `search_star_systems` COUNT outside try
- **File:** `core/databases.py` (grep `star_systems table is empty` then look above for the
  `COUNT(*)` that runs after the try/except). Move the empty-table check inside the guarded region
  (or wrap it) so a failure returns `{"error": ...}` per contract instead of raising.
- **Verify:** `tests/test_search.py`.

### P2.6 Dust-routing segment-integral reuse
- **File:** `core/dust_routing.py`.
- **Fix 1 (route-detail reuse):** in `compute_jump_route_dust` and `compute_jump_route_blend`, the
  Dijkstra edge-cost closure caches integrals (grep `cost_cache`), but the final route-detail loop
  calls `_seg(a, b, ...)` fresh per edge (grep `_seg(` occurrences after the search). Change the
  cost closure to stash the **full** seg dict in the cache (keyed by the node-index pair, both
  orientations) and have the detail loop read from it, falling back to `_seg` only on a miss.
- **Fix 2 (comparison reuse):** the tour/MST builders compute an O(n²) A_V matrix via `_seg`, then
  the distance-optimal comparison helpers (grep `_total_av_along` / `_compare`) re-integrate edges
  already in the matrix. Thread the matrix (or a shared memo dict keyed on
  `(round(x1,6),...,map_sel,step_pc)`) into those helpers.
- **Constraint:** results must be numerically identical (same integrals, just not recomputed) —
  the mocked-`_seg` tests in `tests/test_dust_routing.py` count/shape behavior; read them first and
  keep the `_seg` call signature untouched so the mocks still patch cleanly. If the tests assert
  `_seg` call counts, update deliberately and note it.
- **Verify:** `tests/test_dust_routing.py tests/test_query_route_opts.py tests/test_route_planning_opts.py`.

### P2.7 Minor compute (do all; each is a few lines)
- **2-opt invariant hoist:** `core/calculators.py` (grep `_tour_len(cand`) and
  `core/dust_routing.py` (grep `tour_av(cand`): current tour length is recomputed inside the (i,k)
  double loop — hoist it to the loop head and update it on accepted swaps (or implement the
  standard two-edge delta). Behavior-identical tours required (same tie-breaking): verify against
  `tests/test_route_planning_opts.py` pinned tours.
- **par_flux Simpson:** `core/par_flux.py` — drop `_N_SIMPSON` 1000 → 200 **only if** the Sun/M-dwarf
  anchors in `tests/test_par_flux.py` still pass at their stated tolerances (they pin ranges, not
  exact floats — check first); cache the default-band G2 reference `_f_par(_T_SUN_PAR_REF, ...)`
  in a module-level dict keyed by `(lo_m, hi_m)`.
- **cooling `_interp_age` bisect:** optional; skip unless trivially safe — the CHZ sweep is bounded.

---

## Phase 3 — Test-suite harness & speed

### P3.1 Shared subprocess harness `tests/_queryharness.py`
Create (underscore prefix so unittest discovery skips it):
```python
# tests/_queryharness.py
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 60  # seconds — no query.py call should take longer offline

def make_env(db_path=None, **extra):
    env = {"PATH": os.environ.get("PATH", "")}
    if db_path is None:
        db_path = os.path.join(tempfile.gettempdir(), f"query_throwaway_{os.getpid()}.db")
    env["SPACE_APP_DB"] = str(db_path)
    env.update(extra)
    return env

def run_query(*args, env=None, db_path=None, timeout=DEFAULT_TIMEOUT):
    """Run query.py; return (returncode, parsed_json_or_None, stderr)."""
    if env is None:
        env = make_env(db_path)
    proc = subprocess.run(
        [sys.executable, "query.py", *map(str, args)],
        capture_output=True, text=True, cwd=str(REPO), env=env, timeout=timeout,
    )
    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = None
    return proc.returncode, payload, proc.stderr
```
Migrate the ~18 files with a byte-identical module-level `_run` (grep -l `def _run(` in `tests/`)
to `from tests._queryharness import run_query, make_env` — mechanical, one file at a time, keeping
each file's own DB filename where its tests seed data. **Key wins baked in:** a `timeout=` on every
spawn (currently none exist anywhere) and `tempfile.gettempdir()` instead of the 16 hardcoded
Linux-only `/tmp/...` paths (cross-OS fix).
- Fold the three duplicate reachability gates into `tests/_netcheck.py`: it already has
  `hypatia_reachable`/`gavo_reachable`; add a generic `reachable(host, port, timeout=3)` and point
  `test_query_phase_n.py`'s `_horizons_reachable` and `test_query_expanded.py`'s `_reachable` at it.
- **Do not** change any test's assertions in this step — harness swap only.
- **Verify:** full suite, twice (second run catches tmp-file collision regressions).

### P3.2 In-process exit-code matrices (the big speedup)
~500-700 subprocess spawns × ~0.10 s import overhead ≈ 60-85 s/run of pure import cost. The
in-process pattern already exists and passes (see `tests/test_query_phase_n.py`, the mocked-dispatch
tests using `query.cmd_*` + `contextlib.redirect_stdout` + `assertRaises(SystemExit)`).
- Add to `_queryharness.py`:
  ```python
  import contextlib, io
  def run_query_inproc(*args):
      """Dispatch query.py's argparse in-process. Returns (exit_code, payload, stderr_text)."""
      import query  # cached after first import — this is the whole point
      out, err = io.StringIO(), io.StringIO()
      code = 0
      with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
          try:
              query.main(list(map(str, args)))   # see note below
          except SystemExit as e:
              code = int(e.code or 0)
      try:
          payload = json.loads(out.getvalue())
      except ValueError:
          payload = None
      return code, payload, err.getvalue()
  ```
  **Note:** `query.main()` currently reads `sys.argv` — add an optional `argv=None` parameter to
  `query.main` (default preserves current behavior; `parse_args(argv)`), a 2-line additive change.
  Also note in-process runs share the parent's `SPACE_APP_DB`/`core.db._DB_PATH` state — for
  matrices that never touch the DB (the vast majority: pure-math validation errors) this is fine;
  DB-touching matrices stay subprocess.
- **Pilot first:** convert only `tests/test_query_thermal.py` and `tests/test_query_spin.py`
  matrices; measure (`time venv/bin/python -m pytest tests/test_query_thermal.py`). If green and
  faster, roll out to the remaining `test_query_*.py` exit-code matrices, **keeping ≥1 real
  subprocess happy-path test per subcommand** (the CLI-wiring smoke) and keeping all
  parity-vs-core and DB-seeded tests as-is.
- **Verify:** full suite; confirm both runners still work (`python -m unittest discover -s tests`).

### P3.3 `core.regions._MAIN_SEQUENCE_DATA` global-cache guard
The snapshot/restore of this module-level cache exists only in `tests/test_regions.py`
(grep `_MAIN_SEQUENCE_DATA` in `tests/`). Any other test seeding a different `main_sequence_stars`
table can poison it order-dependently. **Fix:** since the suite must stay dual-runner (no pytest
fixtures), add the save/None/restore to `setUp`/`tearDown` of every test class that seeds
`main_sequence_stars` or swaps `_DB_PATH` and calls into `core.regions`/`core.shared` lookups
(grep `main_sequence_stars` in `tests/` for the list), via a tiny helper in `tests/_queryharness.py`
(e.g. `reset_main_sequence_cache()` used in setUp+tearDown).
- **Verify:** run the suite with `pytest -p no:randomly` default order AND once with
  `--deselect`-free reversed file order (`pytest tests/ --collect-only -q | ...` not needed — just
  run `pytest tests/test_viz_phase_o.py tests/test_regions.py` back-to-back both orders as canary).

---

## Phase 4 — query.py contract & core-helper consistency

### P4.1 Exit-code outliers (stderr/exit-2 → JSON/exit-1)
- **File:** `query.py`. Grep: `sys.exit(2)` inside `cmd_circumbinary_hz` and `cmd_solvent_zone`
  (~lines 238-257 and 589-592).
- **Bug:** these two handlers print plain text to stderr with exit 2 for *validation* failures the
  siblings report as JSON `{"error"}` on stdout with exit 1. The docstring documents only 0/1.
- **Fix:** route through `_out({"error": <same message>})`. Argparse's own missing/typed-arg errors
  (real exit-2 territory) are untouched.
- **Update:** `docs/integration.md` sections for `circumbinary-hz` and `solvent-zone` — their
  exit-code tables must move those cases from exit-2 to exit-1. Check
  `tests/test_query_phase_t.py` (circumbinary) and `tests/test_solvent_zones.py` (solvent-zone
  mutex/missing-arg exit-2 rows) — the pinned exit codes for **these specific cases** flip to 1;
  update those pins deliberately (they're contract pins, and the contract is being corrected).
- **Downstream note:** consumer impact is exit-code-only on error paths; flag in the commit message.

### P4.2 `--luminosity` aliases (additive)
- **File:** `query.py`. The four subcommands using bare `--luminosity` (grep
  `add_argument("--luminosity"`) get an **alias** so both spellings work:
  `parser.add_argument("--luminosity", "--luminosity-lsun", dest=..., ...)` (argparse supports
  multiple option strings; keep the original as primary so `--help` output changes minimally).
  Do the reverse (add `--luminosity` alias) on the four `--luminosity-lsun` commands ONLY if it
  can't collide with an existing flag — check each parser first; skip on any doubt.
- **Update:** `docs/integration.md` — note the accepted alias per affected subcommand.
- **Verify:** happy-path tests for `habitable-zone`, `solvent-zone`, `ice-lines`, `par-flux`,
  `equilibrium-temp` etc. (grep the four each way) + one new alias test per direction.

### P4.3 Centralize the velocity resolver (fixes a real validation inconsistency)
- **Files:** `core/propulsion.py` (`_resolve_vehicle_velocity`, grep it), `core/ism_drag.py`
  (`_resolve_velocity`), `core/dust_impact.py` (`_resolve_velocity`).
- **Bug:** three near-identical `(velocity_kms | beta) → (v_ms, v_kms, beta)` helpers;
  propulsion's accepts `velocity_kms == 0`, the other two reject it; `compute_rocket_equation`
  admits `beta == 0` while `compute_pellet_stream`'s resolver rejects it.
- **Fix:** add ONE canonical resolver to `core/equations.py`:
  `def _resolve_velocity(velocity_kms=None, beta=None, *, allow_zero=False) -> dict|(floats)` —
  exactly-one-source gate, `0 ≤ β < 1` (or `0 < β < 1` when `allow_zero=False`), curated error
  strings. Point all three modules at it, choosing `allow_zero` per current *documented* behavior:
  - `pellet-stream` explicitly documents `--velocity-kms 0` allowed → propulsion keeps zero-allowed.
  - ism_drag/dust_impact keep zero-rejected (their tests pin it).
  - `compute_rocket_equation` β=0: keep accepting (MR=1 is a harmless degenerate) — note it.
  **The rule: preserve every current accept/reject decision that a test or integration.md pins;**
  this item removes the *duplication*, and only unifies behavior where nothing pins a difference.
  Keep thin module-local wrappers if error-message wording is pinned per-module.
- **Verify:** `tests/test_propulsion.py tests/test_ism_drag.py tests/test_dust_impact.py` + their
  `test_query_*` twins — zero assertion changes expected.

### P4.4 Insolation helper + note-key hygiene (additive, D4)
- **Insolation:** `core/par_flux.py` `_resolve_insolation` and `core/terraforming.py` `_solar_flux`
  both compute `S = L·L☉/(4π(d·AU)²)` behind an exactly-one-source gate. Hoist one helper into
  `core/equations.py` (e.g. `insolation_from_lum_dist`), delegate both, preserve each module's
  exact error strings (they're pinned).
- **Dipole moment:** `ism_drag._resolve_dipole` and `active_shield._resolve_moment` share
  `m = I·π·R²` — same treatment, small shared helper or leave with a cross-reference comment if
  signatures diverge too much (implementer's call; don't force it).
- **`model_note`:** add a `model_note` key to `compute_waste_heat` and `compute_radiator_area`
  (`core/thermal.py`) summarizing the model (Carnot-capped efficiency split; gray-body σ(T⁴−T_sink⁴)
  radiator). Keep the existing `notes`/`scaling_note` keys untouched. Normalize `notes` values to
  `list` at return time where modules currently return tuples (`core/spin.py`,
  `core/life_support.py` — grep `_NOTES`): wrap in `list(...)` (JSON-identical, type-consistent).
- **Update:** `docs/integration.md` for the two new `model_note` keys.
- **Verify:** the six module test files + query twins; additive keys can't break "key present"
  assertions but check for any `assertEqual(sorted(result.keys()), ...)`-style exact-shape pins.

### P4.5 Constant dedup (safe imports only)
All same-value duplicates — replace local definitions with imports from `core.equations`
(add to equations.py where no canonical home exists):
- `megastructure._L_SUN_W` → import `_SOLAR_LUMINOSITY_W`.
- `_TNT_J_PER_KG` (dust_impact, volatile_delivery) → add `_TNT_J_PER_KG = 4.184e6` to equations.py,
  import in both.
- `_LY_M` (ism_drag, dust_impact, calculators) → add `_LY_M = _C_MS * _SEC_PER_YEAR` to equations.py,
  import everywhere (verify calculators' `_LY_M` uses the same Julian-year definition — it does).
- `_C_KMS` (propulsion, propulsion_tables, ism_drag_tables) → equations.py.
- `science.py`'s local `_C_MS`/`9.80665` → import from equations.py.
- `core/dust.py` `_LY_PER_PC = 3.2615637771` vs `core/shared.py LY_PER_PC = 3.26156`: do **not**
  unify numerically (3.26156 is pinned all over tests/docs); add a comment in dust.py noting the
  deliberate precision difference and sub-ppm effect.
- **Verify:** full suite — all changes are value-identical, so zero pin changes expected. Any
  failure here means a value was NOT identical: stop and report.

### P4.6 Parser/helper dedup in the data layer (bigger; do last in this phase)
- **Designation parsing:** `core/shared.py` has `_parse_designations_from_ids` + prefix map;
  `core/databases.py` has its own copies (grep `_CSV_PREFIX_MAP` and the inline map in
  `compute_simbad_lookup`), which have **already drifted** (the `NAME` key present in shared.py's
  key list, absent in databases.py's `_CSV_DESIG_KEYS`). Consolidate on ONE map + parser in
  `core/shared.py` with an explicit `keys=` parameter so each caller keeps its current key set —
  **preserving the drift as configuration, not silently changing either caller's output.**
- **`_kopparapu_seff`:** canonical copy in `core/equations.py`; make `core/shared.py` and
  `core/viz.py` import it (verify the three bodies are value-identical first — diff them).
- **`_to_cartesian` / sexagesimal RA/Dec:** `core/viz.py` duplicates `core/calculators.py` —
  import from calculators (or move the pair to `core/shared.py`; keep it one hop, no new module).
- **`_fval`/`_fmt`:** point `core/databases.py`'s copies at `core/shared.py`'s.
- **Two `compute_habitable_zone`s:** `databases.py`'s tuple-returning variant vs
  `equations.py`'s dict-returning one. Do NOT merge signatures (three GUI panels consume the tuple
  shape). Instead: reimplement `databases.compute_habitable_zone` as a thin adapter over
  `equations.compute_habitable_zone` (map dicts → tuples, preserve the `st_rad`/log-lum input
  handling), so the Kopparapu math exists once.
- **Verify:** full suite + a manual GUI smoke is NOT required (offscreen panel tests cover the
  consumers that exist); `tests/test_search.py`, `tests/test_gcns.py`, `tests/test_comparison.py`,
  `tests/test_viz_phase_o.py` are the canaries.

---

## Phase 5 — Documentation fixes

### P5.1 L4 "deferred" contradiction (one line)
- `docs/star-databases.md` (~line 344, grep `is \*\*deferred\*\*`): replace with
  `L4 (Hypatia cache + abundance search) is **complete** — see the "Phase L4 — Hypatia Abundance Cache & Search" section below.`

### P5.2 CLAUDE.md menu-label truncations
- Option 3 row: append to the existing option-4 truncation footnote (grep `abbreviated above`) that
  option 3's full label is "NASA Exoplanet Archive: Planetary Systems Composite".
- Option 11 row: same footnote treatment for "…Asteroids Data Table" (or restore the words inline
  if column width allows).

### P5.3 gui-architecture.md staleness
- Grep `62nd` / `63rd` — drop the ordinals ("the `dossier` subcommand" etc.).
- Line ~640 "Phase S completes the planned roadmap (A–S; J declined)": append one sentence —
  "Phases U–AD (below) are subsequent `query.py`-only extension phases for the sibling
  scifiWorldBuilding repo; the GUI roadmap remains complete at S."

### P5.4 CLAUDE.md context diet (scope per D3)
- Create `docs/testing.md` containing the entire per-test-file description block currently in
  CLAUDE.md's "### Tests" section (the ~40 dense bullets from `test_equations.py` through
  `test_viz_phase_o.py`/`test_report.py`/… — cut verbatim, do not rewrite).
- Replace the block in CLAUDE.md with:
  - the 6-line intro that's already there (offline/network-gated split, DB-isolation patterns,
    `SPACE_APP_DB`), and
  - a pointer: "Per-test-file descriptions live in `docs/testing.md` (read-on-demand — read it
    before adding or modifying tests)," listed alongside the existing `integration.md`/
    `gui-architecture.md` read-on-demand bullet.
- Similarly compress the giant single-paragraph Architecture bullet for `core/` (grep
  `core/report.py — the Phase Q`): keep the module → one-clause list; move the per-phase prose
  history into `docs/testing.md` or leave it to the PHASE_*_PLAN files it already duplicates.
  Conservative rule: **delete nothing that exists nowhere else** — verify each clause appears in a
  phase plan or docs/ file before removing it from CLAUDE.md; anything unique gets moved, not cut.
- **Do NOT** touch the five `@docs/...` include lines (D3).

---

## Phase 6 — Robustness & hardening

### P6.1 Centralize Retry-After handling
- **File:** `core/shared.py` `_with_retries` (grep it). Currently only `_hypatia_data_fetch`
  (`core/databases.py`) honors 429/503 `Retry-After`.
- **Fix:** teach `_with_retries` an optional hook: if the raised exception is a
  `requests.HTTPError` whose response has a `Retry-After` header (int seconds form), sleep
  `min(retry_after, 60)` instead of the exponential backoff for that attempt. Keep
  `_hypatia_data_fetch`'s local handling (it's more specific) — this just extends the default for
  NASA TAP / SIMBAD-over-requests paths. No caller signature changes.
- **Verify:** add a unit test in a new `tests/test_shared.py` (see P7.1) with a fake exception
  carrying a mock response; assert sleep path chosen (patch `time.sleep`).

### P6.2 ADQL literal escaping
- **File:** `core/databases.py`. Add `def _adql_quote(value: str) -> str` that doubles single
  quotes (mirroring what `search_exoplanets` already does — grep `''` in its filter builder) and
  strips control chars. Apply at the four unescaped interpolation sites (grep
  `f"` + `='` around `hip_name|hd_name|tic_id|gaia_id` in `compute_exoplanet_archive`,
  `compute_planetary_systems_composite`, `compute_hwo_exep`, `compare_stars`).
- **Verify:** existing mocked-TAP tests (`tests/test_search.py`, `tests/test_comparison.py`) —
  built queries for normal designations must be byte-identical (quoting only activates on `'`).

### P6.3 CSV-header identifier whitelist
- **File:** `core/databases.py`, `import_hwc_csv` + `import_mission_exocat_csv` (grep
  `CREATE TABLE` in each). Before interpolating headers into DDL/DML, validate every header against
  `re.fullmatch(r"[A-Za-z0-9_ .\-/()%]+", h)` (derive the exact allowed set from the two real CSVs'
  headers first — widen only as needed) and return `{"error": "invalid column header: ..."}` on
  failure.
- **Verify:** `tests/test_query_expanded.py` (hwc import path) + a new bad-header unit test.

### P6.4 Module-cache locks
- **File:** `core/databases.py`. Add one `threading.Lock` per lazy cache (`_HWC_DATA`,
  `_MISSION_EXOCAT`) with double-checked locking in the `_load_*` helpers, and take the lock in
  `import_hwc_csv`'s cache flush. Delete the duplicate `_MISSION_EXOCAT = None` declaration (grep
  `_MISSION_EXOCAT = None` — keep the first). Skip `_OEC_DATA` (OEC is out of scope).
- **Verify:** behavior-identical single-threaded; full suite.

### P6.5 NULL-not-empty-string numeric writes
- **File:** `core/databases.py` `_run_simbad_csv_query` (grep `""` around the parallax/ly row
  assembly). Failed numeric parses currently store `""` into REAL columns, papered over later by
  `NULLIF(col,'')`. Write `None` instead. **Keep the `NULLIF` guards in `_range_clause`** (existing
  rows in user databases still contain `""`).
- **Verify:** `tests/test_search.py` (range filters), `tests/test_db_backups.py`.

---

## Phase 7 — Coverage additions

### P7.1 `tests/test_shared.py` (new)
Unit tests for `core/shared.py`'s currently-untested helpers: `_parse_designations` (incl. the
`Gaia DR3`/`EDR3` prefix rule), `_parse_spectral_class`/`_lookup_spectral_type` (ceiling rule +
cross-letter fallthrough, `D…` white-dwarf rejection), `_with_retries` (success-after-failure,
exhaustion, and the new P6.1 Retry-After path — patch `time.sleep`), `_network_error_msg`
classification matrix. Pure offline.

### P7.2 `tests/test_databases.py` (new; mocked network)
The highest-value gap: `core/databases.py`'s archive readers have no direct tests. Cover, with
`unittest.mock.patch` on `_query_tap` / SIMBAD / requests (mirror the existing mocking style in
`tests/test_search.py` and `tests/test_comparison.py`):
- `compute_exoplanet_archive` happy path + no-designation + TAP-error classification,
- `compute_planetary_systems_composite`, `compute_hwo_exep`, `compute_mission_exocat` (CSV-backed —
  temp CSV), `compute_hwc` (reuse the real `hwc.csv` load path against a temp DB),
- `_query_tap` retry exhaustion → `_network_error_msg` message shape,
- the P6.2 `_adql_quote` behavior.
Skip OEC entirely. Keep it all offline (no reachability gates).

### P7.3 GUI panel smokes — **defer**
27 of 31 panels lack offscreen smokes. This is real but big; do NOT bundle it into this pass.
Note it in `future_phases.md` as a candidate phase instead (one line).

---

## Phase 8 — Repo hygiene

- Delete `image.png` (283 KB — referenced by nothing; the two apparent hits in
  `gui/panels/reports.py` / `tests/test_reports_panel.py` are `data:image/png;base64` MIME strings,
  not this file. Re-verify with `grep -rn "image.png" --include="*.py" --include="*.md" .` first).
- Create `archive/` and `git mv` into it: `CONSISTENCY_PLAN.md`, `GCNS_EXTENSION_REQUEST.md`,
  `INTEGRATION_PLAN.md`, `hypatia_implementation.md`, `future_phases_archive.md`. Update the one
  live pointer: `future_phases.md` references `future_phases_archive.md` (grep and fix the path).
  Remove the stale `sed`-on-CONSISTENCY_PLAN allow-rule from `.claude/settings.local.json` (grep
  `CONSISTENCY_PLAN`).
- **Leave in place:** the `PHASE_*_PLAN/MOCKUP` files, `mockups/`, `backups/`,
  `stars_within_15ly.html`, `generate_star_map_html.py` (style-lineage references exist in
  docs/comments; moving them is churn without payoff — skip unless the user asks).
- **Verify:** full suite (nothing imports the moved files); `venv/bin/python query.py --help`.

---

## Explicitly OUT of scope (user decisions)

- `main.py` CLI feature functions (menu unused) — including its copies of the P1 bugs.
- Anything OEC (opt 7, `OecPanel`, `compute_oec`, the `main.py:2129` import) — pending rebuild.
- D1 Option B (numeric year-constant unification), D2 recalibration of the legacy regions
  luminosity conventions, demotion of CLAUDE.md `@`-includes, GUI panel smoke backfill (P7.3).

## Final acceptance checklist

1. `venv/bin/python -m pytest` — green, and note total runtime before/after Phase 3 (expect a
   material drop from the in-process matrices).
2. `venv/bin/python -m unittest discover -s tests` — still collects and passes (dual-runner intact).
3. `venv/bin/python query.py sol-regions` — angular size ≈ 0.53°; JSON shape otherwise unchanged.
4. `venv/bin/python query.py cooling-hz --track wd --mass-solar 0.6 --mode chz --threshold-gyr 8`
   (and a Δ-pause variant) — unchanged vs pre-plan output (P1.2 touches only the degenerate branch).
5. `git diff --stat` reviewed against this plan — no drive-by changes outside the listed files.
6. `docs/integration.md` updated wherever a subcommand's flags/keys/exit codes changed
   (P4.1, P4.2, P4.4) — this is the downstream contract; it must never lag the code.
