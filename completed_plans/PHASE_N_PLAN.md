# PHASE N — query.py Integration Expansion · Implementation Plan

> **Scope: integration-surface only.** Phase N adds **five new `query.py` subcommands**, each wrapping an
> **already-existing `core/` function verbatim**. There are **no GUI, CLI-menu, `core/`, or DB changes** — the
> only source files touched are `query.py` (dispatcher + argparse), `docs/integration.md` (contract docs), a
> new `tests/test_query_phase_n.py`, and one bullet in `CLAUDE.md`'s test list. This mirrors the precedent set
> by Phase M5 (which already extended `query.py` over an existing core function).
>
> **Companion mockup:** [`mockups/phase-n.html`](mockups/phase-n.html) — an interactive CLI/JSON *contract preview*
> (no GUI to mock; the "UI" here is the command line + the JSON it emits). **No code is written until the mockup
> is approved.**

---

## 1. The five subcommands

Every subcommand wraps one existing core function with **no changes to that function**. Column "Validates?" is the
crux of this phase's contract (see §3).

| # | Subcommand | Core function (existing) | Args | Network | Validates? |
|---|---|---|---|---|---|
| N1 | `habitable-zone-sma` | `equations.compute_habitable_zone_sma(teff, luminosity, sma)` | `--teff --luminosity --sma` | none | no (legacy fn) |
| N2 | `star-luminosity` | `equations.compute_star_luminosity(radius, temp)` | `--radius --teff` | none | no (legacy fn) |
| N3 | `brachistochrone-au` | `calculators.compute_travel_time_system_au(accel_g, distance_au)` | `--accel-g --au` | none | no (legacy fn) |
| N4 | `brachistochrone-lm` | `calculators.compute_travel_time_system_lm(accel_g, distance_lm)` | `--accel-g --lm` | none | no (legacy fn) |
| N5 | `travel-time-solar` | `calculators.compute_travel_time_solar_objects(origin, destination, accel_g, v_cap_pct=3.0, departure_date=None)` | `--origin --destination --accel-g [--v-cap-pct] [--date]` | **JPL Horizons (live)** | yes (returns `{"error"}`) |

### Exact output keys (what each core function returns *today*, serialized verbatim)

- **N1** → `{"zones": [6 zone dicts], "planet_seff": float, "verdict": str}`; each zone dict = `{zone_name, key, au, lm, seff}`.
- **N2** → `{"radius": float, "temp": float, "luminosity": float}`.
- **N3 / N4** → `{"accel_g": float, "distance_au": float, "distance_lm": float, "profiles": [3 profile dicts]}`;
  each profile dict = `{label: str, hours: float, travel_time_str: str, max_vel: str}` (`max_vel` ∈ `"N/A"`/`"Y"`/`"N"`).
  These are the **travel-time-given-distance** profiles (confirmed from `core/calculators.py::_brachistochrone_profiles`,
  `:765–784`) — *not* the distance-only shape opt 24 uses.
- **N5** → `{origin, destination, accel_g, distance_au, distance_lm, v_cap_pct, departure_date, profiles, origin_xyz, dest_xyz, planet_positions, origin_id, dest_id}` **or** `{"error": str}` (+ embedded disambiguation text on ambiguous Horizons names). N5's `profiles` carry the same `{label, hours, travel_time_str, max_vel}` shape as N3/N4. JSON consumers may ignore `origin_xyz/dest_xyz/planet_positions/origin_id/dest_id`.

---

## 2. `query.py` edits (WP1)

Two additions per subcommand, following the file's existing idiom exactly (compare the Phase-H block at
`query.py:131–165` and its subparsers at `:308–353`).

### 2a. Handlers — insert a new "Integration expansion (Phase N)" section after the Phase-H handlers (after line 165)

```python
# ── Integration expansion (Phase N) ───────────────────────────────────────────

def cmd_habitable_zone_sma(args):
    _out(equations.compute_habitable_zone_sma(args.teff, args.luminosity, args.sma))


def cmd_star_luminosity(args):
    # --teff is mapped to the function's `temp` parameter (naming parity with N1/habitable-zone).
    _out(equations.compute_star_luminosity(args.radius, args.teff))


def cmd_brachistochrone_au(args):
    _out(calculators.compute_travel_time_system_au(args.accel_g, args.au))


def cmd_brachistochrone_lm(args):
    _out(calculators.compute_travel_time_system_lm(args.accel_g, args.lm))


def cmd_travel_time_solar(args):
    # progress_callback is GUI-only and is deliberately NOT passed (defaults to None).
    _out(calculators.compute_travel_time_solar_objects(
        args.origin, args.destination, args.accel_g,
        v_cap_pct=args.v_cap_pct, departure_date=args.date,
    ))
```

### 2b. Subparsers — add after the `atmosphere-retention` subparser (after line 353), before `args = parser.parse_args()`

```python
    # habitable-zone-sma
    p = sub.add_parser("habitable-zone-sma",
                       help="HZ boundaries + object's Seff and HZ-membership verdict")
    p.add_argument("--teff",       required=True, type=float, help="Stellar temperature in K")
    p.add_argument("--luminosity", required=True, type=float, help="Stellar luminosity in solar units")
    p.add_argument("--sma",        required=True, type=float, help="Object's semi-major axis in AU")
    p.set_defaults(func=cmd_habitable_zone_sma)

    # star-luminosity
    p = sub.add_parser("star-luminosity",
                       help="Stellar luminosity from radius and temperature: L = R²·(T/5778)⁴")
    p.add_argument("--radius", required=True, type=float, help="Stellar radius in solar radii (R☉)")
    p.add_argument("--teff",   required=True, type=float, help="Effective temperature in K")
    p.set_defaults(func=cmd_star_luminosity)

    # brachistochrone-au
    p = sub.add_parser("brachistochrone-au",
                       help="Brachistochrone travel time for three profiles, distance in AU")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--au",      required=True, type=float, help="Distance in AU")
    p.set_defaults(func=cmd_brachistochrone_au)

    # brachistochrone-lm
    p = sub.add_parser("brachistochrone-lm",
                       help="Brachistochrone travel time for three profiles, distance in light minutes")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--lm",      required=True, type=float, help="Distance in light minutes")
    p.set_defaults(func=cmd_brachistochrone_lm)

    # travel-time-solar
    p = sub.add_parser("travel-time-solar",
                       help="Brachistochrone travel time between two solar-system bodies (live JPL Horizons)")
    p.add_argument("--origin",      required=True, help="Origin body name or Horizons ID")
    p.add_argument("--destination", required=True, help="Destination body name or Horizons ID")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--v-cap-pct", dest="v_cap_pct", type=float, default=3.0,
                   help="Coast-phase velocity cap as %% of c (default 3.0)")
    p.add_argument("--date", default=None, help="Departure date ISO YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_travel_time_solar)
```

No other change to `query.py`. The existing top-level `try/except` in `main()` (`query.py:356–359`) already converts
any uncaught exception into `{"error": str(e)}` + exit 1 — that is the mechanism N1–N4 rely on for bad numeric input (§3).

---

## 3. Validation & exit-code contract — the one real design decision

The Phase-N sketch in `future_phases.md` says *"semantically invalid values → the core function's `{"error": …}` dict on
stdout, exit 1."* **That is only literally true for N5.** N1–N4 wrap the *older, non-self-validating* equation/calculator
functions (unlike the Phase-H functions, which self-validate). With **no core changes** (the phase's hard constraint),
out-of-range numbers for N1–N4 surface through `main()`'s top-level handler as `{"error": str(e)}` with a **raw Python
exception message** rather than a curated sentence.

**Decision (recommended, baked into the plan & mockup): Option A — honor the no-core-change constraint; document the real behavior.**
This is consistent with the existing blessed precedent: `tests/test_equations.py::test_bad_input_raises` already documents
that `compute_habitable_zone(5778, -1.0)` raises `ValueError` and "query.py's top-level handler turns this into an
`{"error": …}` dict." Adding per-subcommand validation in `query.py` (Option B) would duplicate physics-range knowledge
into the dispatcher and break the "every subcommand is a thin verbatim wrapper" property. **The exact behavior is
surfaced in `docs/integration.md` and the mockup so external callers know what to expect.**

### Per-subcommand exit-code matrix (Option A)

| Input class | N1 `habitable-zone-sma` | N2 `star-luminosity` | N3/N4 `brachistochrone-*` | N5 `travel-time-solar` |
|---|---|---|---|---|
| **Valid** | exit 0, result dict | exit 0, result dict | exit 0, result dict | exit 0, result dict |
| **Missing / non-numeric arg** | argparse → **exit 2**, stderr | exit 2 | exit 2 | exit 2 |
| **Zero where it divides** | `--sma 0` → ZeroDivisionError → **exit 1** `{"error":"float division by zero"}` | — (no division) | `--accel-g 0` → **exit 1** `{"error":"float division by zero"}` | `--accel-g 0` → **exit 1** (after the network calls) |
| **Negative → sqrt domain** | `--luminosity -1` → **exit 1** `{"error":"math domain error"}` | — (radius² makes any radius valid; returns a number) | negative `--au`/`--lm`/`--accel-g` → **exit 1** `{"error":"math domain error"}` | n/a |
| **Semantic (network/ambiguous/self)** | n/a | n/a | n/a | **exit 1**, curated `{"error": …}` (ambiguous-name disambiguation, same-object, network-down — produced by the core fn) |

> **N2 has no error path at all** beyond argparse: `L = radius²·(temp/5778)⁴` returns a finite number for any float input
> (a negative radius yields a positive luminosity because it is squared). This is documented honestly rather than
> papered over — N2's contract is "argparse rejects non-numbers; everything else computes."

This matrix is reproduced verbatim in the mockup's "Validation & exit codes" panel and in `docs/integration.md`'s Phase-N
implementation note, so the behavior is part of the approved contract, not a surprise.

---

## 4. Tests (WP3) — `tests/test_query_phase_n.py`

Offline by default. Pattern lifted from `tests/test_gcns.py`'s `GcnsQueryCliTest` (subprocess against `query.py`,
`cwd=_REPO`, throwaway `SPACE_APP_DB`). N5's live path is gated by `tests/_netcheck.py` exactly like `test_gcns_live.py`.

**Module scaffold**
```python
import json, os, subprocess, sys, unittest
from pathlib import Path
_REPO = Path(__file__).resolve().parent.parent

def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO),
        env={"SPACE_APP_DB": "/tmp/phase_n_throwaway.db", "PATH": os.environ.get("PATH", "")},
    )
    try:    payload = json.loads(proc.stdout)
    except Exception: payload = None
    return proc.returncode, payload, proc.stderr
```

### 4a. Happy-path contract (offline, one per N1–N4)

| Test | Invocation | Asserts |
|---|---|---|
| `test_n1_hz_sma_contract` | `habitable-zone-sma --teff 5778 --luminosity 1 --sma 1` | exit 0; keys `{zones, planet_seff, verdict}`; `len(zones)==6`; each zone has `{zone_name,key,au,lm,seff}`; `planet_seff == 1.0`; verdict contains `"Conservative Habitable Zone"` |
| `test_n2_star_luminosity_contract` | `star-luminosity --radius 1 --teff 5778` | exit 0; keys `{radius,temp,luminosity}`; `luminosity == 1.0` (within 1e-9) |
| `test_n3_brachistochrone_au_contract` | `brachistochrone-au --accel-g 1 --au 1` | exit 0; keys `{accel_g,distance_au,distance_lm,profiles}`; `len(profiles)==3`; `distance_lm ≈ 8.3167` (within 1e-3) |
| `test_n4_brachistochrone_lm_contract` | `brachistochrone-lm --accel-g 1 --lm 8.3167` | exit 0; keys as N3; `distance_au ≈ 1.0` (within 1e-4) |

### 4b. Parity (output == wrapped core fn) — locks "verbatim wrapper"

`test_n1_parity`: import `core.equations`, compute `compute_habitable_zone_sma(5778,1,1)`, round-trip it through
`json.loads(json.dumps(core_result, default=str))`, and assert it `==` the subprocess JSON for the same args.
(One parity test on N1 is sufficient to prove the dispatcher adds/loses nothing; the per-command contract tests cover the rest.)

### 4c. Bad-input / exit-code (offline)

| Test | Invocation | Asserts |
|---|---|---|
| `test_n1_sma_zero_exit1` | `habitable-zone-sma --teff 5778 --luminosity 1 --sma 0` | exit **1**; payload has `"error"` |
| `test_n1_negative_lum_exit1` | `habitable-zone-sma --teff 5778 --luminosity -1 --sma 1` | exit **1**; payload has `"error"` |
| `test_n3_accel_zero_exit1` | `brachistochrone-au --accel-g 0 --au 1` | exit **1**; payload has `"error"` |
| `test_missing_required_exit2` | `habitable-zone-sma --teff 5778 --luminosity 1` (no `--sma`) | exit **2**; stdout empty / unparseable; stderr non-empty |
| `test_n5_missing_origin_exit2` | `travel-time-solar --destination Mars --accel-g 1` | exit **2**; stderr non-empty |
| `test_n2_negative_radius_is_not_an_error` | `star-luminosity --radius -1 --teff 5778` | exit **0**; `luminosity == 1.0` (documents N2's "no error path") |

### 4d. N5 wiring (mocked, in-process — no network)

`test_n5_dispatch_wiring`: monkeypatch `query.calculators.compute_travel_time_solar_objects` with a recorder that
captures `(args, kwargs)` and returns a sentinel dict; build
`argparse.Namespace(origin="Earth", destination="Mars", accel_g=1.0, v_cap_pct=3.0, date="2027-03-15")`; call
`query.cmd_travel_time_solar(ns)` inside `assertRaises(SystemExit)` while capturing stdout with
`contextlib.redirect_stdout`. Assert:
- positional call `("Earth","Mars",1.0)`,
- kwargs exactly `{"v_cap_pct":3.0, "departure_date":"2027-03-15"}`,
- **`progress_callback` NOT in kwargs**,
- captured stdout parses to the sentinel dict,
- `SystemExit.code == 0`.

This fully validates N5's arg-mapping (`--date`→`departure_date`, `--v-cap-pct`→`v_cap_pct`, no `progress_callback`)
without touching the network.

### 4e. N5 live (gated, optional) — `test_query_phase_n_live.py` *(or a `@skipUnless` class in the same file)*

`@unittest.skipUnless(network_available(), …)` (reuse `tests/_netcheck.py`). Run
`travel-time-solar --origin Earth --destination Mars --accel-g 1`; assert exit 0, keys include `profiles`,
`distance_au > 0`. Skips automatically offline — never blocks `pytest`.

---

## 5. Docs (WP2) — `docs/integration.md`

1. **Quick-reference table** (the `| Subcommand | Required args | Network | Output keys |` table): add five rows,
   placed adjacent to their kin (N1 after `habitable-zone`; N2 near it; N3/N4 grouped; N5 after `travel-time`).
   **N5's Network cell flagged "JPL Horizons (live)"** — the only network-bound row added this phase.
2. **One subcommand section each**, following the existing format (bash example + core-function line + output description),
   inserted in the matching topical area (Habitable-zone section for N1; a "Stellar luminosity" entry for N2; a
   "Brachistochrone (given distance)" area for N3/N4; the Travel-time area for N5).
3. **Implementation-notes addendum**: a short paragraph stating the §3 validation reality — *N1–N4 wrap non-validating
   legacy functions, so out-of-range numerics surface as `{"error": str(e)}` (raw exception text) via the top-level
   handler, exit 1; only N5 emits curated error dicts; N2 has no error path beyond argparse.*

## 6. CLAUDE.md (WP4)

Add one bullet to the **Tests** list: `test_query_phase_n.py` — the Phase-N `query.py` subcommand contracts
(offline subprocess + N5 mocked-wiring), and note its `*_live.py` gated companion. (Doc-only; no behavior change.)

---

## 7. Work-package order

1. **WP1** — `query.py` handlers + subparsers (§2). Smoke-test each by hand (`python query.py habitable-zone-sma …`).
2. **WP3** — `tests/test_query_phase_n.py` (§4). Run `pytest tests/test_query_phase_n.py`.
3. **WP2** — `docs/integration.md` rows + sections + note (§5).
4. **WP4** — `CLAUDE.md` test bullet (§6).
5. Full suite: `pytest` (or `python -m unittest discover -s tests`) — confirm green, live tests skipped offline.

---

## 8. Success criteria

- [ ] All five subcommands invokable; valid input → **exit 0** and a JSON dict whose keys match §1 exactly.
- [ ] Subprocess output for each is **byte-identical** to `json.dumps(core_fn(...), indent=2, default=str)` (parity test 4b).
- [ ] Bad numeric input: N1 (`--sma 0`, `--luminosity -1`) and N3/N4 (`--accel-g 0`) → **exit 1** with an `"error"` key;
      N2 negative radius → **exit 0** (documented non-error); missing/non-numeric args → **exit 2** on stderr.
- [ ] N5: `--date`→`departure_date`, `--v-cap-pct`→`v_cap_pct` defaults (`None`/`3.0`) correct; `progress_callback`
      **never** passed (mocked test 4d); Network flagged in the quick-ref table; live test skips offline.
- [ ] **Zero diff** outside `query.py`, `docs/integration.md`, `tests/test_query_phase_n.py` (+ optional live file),
      and `CLAUDE.md`. `git diff --stat` shows no `core/`, `gui/`, `main.py`, or `core/db.py` changes.
- [ ] Pre-existing test suite remains green; new offline tests pass; the `argparse` help for all five reads cleanly
      (`python query.py <cmd> --help`).
- [ ] `docs/integration.md` documents the real §3 validation behavior (no aspirational "clean error dict" claim for N1–N4).

---

## 9. Out of scope (explicitly, per `future_phases.md` Phase N)

- Unit converters (ly/hr ↔ ×c, distance/time at constant velocity) — trivial arithmetic on `8765.8128`; callers do it themselves.
- Static data-table dumps (main-sequence properties, solar-system tables, Honorverse tables) — no computation to delegate.
- `star-regions-raw` (manual six-parameter regions) — the SIMBAD-backed `star-regions` already covers the integration need.
- **No** added validation in `core/` or `query.py` for N1–N4 (Option B rejected — see §3).
- The Phase-H subcommands are already shipped; Phase N does not retouch them.
