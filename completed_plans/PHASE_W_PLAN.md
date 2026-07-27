# Phase W — Rotating-Habitat Comfort Calculator (`spin-comfort`)

One new **`query.py`-only**, **pure-math**, self-validating calculator (the Phase-H/P
contract) plus **one isolated bundled constant table** — the artificial-gravity
comfort-criteria bands (transcribed from the comfort-chart literature, synthesized in
Theodore Hall's *SpinCalc* / *The Architecture of Artificial Gravity*). The in-house analog
of SpinCalc: given any **two** of the four spin-state variables {radius, spin rate,
centrifugal gravity, rim tangential velocity} it solves the other two **plus** the three
comfort-relevant derived quantities the existing `gravity-*` solves don't expose — **rim
tangential velocity, head-to-foot gravity gradient, Coriolis ratio for a walking occupant**
— then classifies the design against tiered, cited comfort bands (conservative / moderate /
relaxed).

Specced in
`scifiWorldBuilding-Claude/research/query-api-methods/spin-comfort-calculator-request.md`
(status *Proposed*; the **pre-scope-lock prerequisite for Packet 14**, "Engineered Habitat
Human Baseline"). The kinematic outputs are exact physics; only the pass/fail **bands** are a
human-factors *choice* (the Mature-Technology-Assumption framing — overridable, tiered).

**Lineage:** identical structure to **Phase U (`cooling-hz`)** / **Phase V (thermal)** — new
core module + isolated bundled data table + one granular subcommand + **no GUI** (one
completion row in `docs/gui-architecture.md`, query.py-only). No network, no DB, no RNG, no
time. **Extends, does not replace** `gravity-acceleration` / `gravity-distance` /
`gravity-rpm` (those stay the terse single-scalar solves; cross-reference them in the help).

---

## Resolved implementer decisions (the request's four open items + two ambiguities)

Locked with the user 2026-07-01:

1. **Home module → new `core/spin.py`** (the `compute_spin_comfort` function) **+ new
   `core/spin_tables.py`** (the bundled comfort bands + provenance/`model_note` string),
   mirroring the `core/cooling.py` / `core/cooling_tables.py` and `core/thermal.py` /
   `core/shielding_tables.py` splits. The lone constant `_STANDARD_GRAVITY = 9.80665` goes in
   `core/equations.py` (with `_G` etc.) so g₀ can't drift — it is **not currently present**
   there (the legacy `gravity-*` functions use inline `2π/60` and never reference g₀).
2. **Anchors → require exactly two.** Any third state anchor is an error even if consistent
   (a core-function count check). The request's "inconsistent over-determined trio" tolerance
   clause is therefore **moot** and not implemented.
3. **Gravity input surface → accept both `--gravity-g` and `--accel-ms2`** as an **argparse
   mutually-exclusive group** (both → exit 2, before the core runs). The core receives a
   single resolved `accel_ms2` (gravity form pre-converted in the `cmd_` handler).
4. **Output → JSON only** (no human-readable summary-line string), for parity with Phase U/V.
5. **Bundled bands → the request's numbers VERBATIM** (no adjustment). The band research
   (Hall JBIS-52 Table 1) is recorded only as three honest provenance footnotes in the output
   `model_note` — it changes **no value** (see §2).

---

## 1. Files touched

| File | Change |
|---|---|
| `core/equations.py` | **+1 constant** in the module constants block: `_STANDARD_GRAVITY = 9.80665` (standard gravity, CGPM). Nothing else. |
| `core/spin.py` *(new)* | `compute_spin_comfort(...)` — the 2-anchor solver → (ω, r) → {v, gradient, Coriolis} → tiered verdict. Imports `_STANDARD_GRAVITY` from `equations` + the bands from `spin_tables`. |
| `core/spin_tables.py` *(new)* | `_COMFORT_BANDS` (3 tiers × 6 thresholds, verbatim from the request) + `_MODEL_NOTE` / `_SOURCES` provenance strings + `_BAND_TOL`. Isolated like `cooling_tables.py`. |
| `query.py` | `import core.spin as spin`; one `cmd_spin_comfort` handler + one `add_parser("spin-comfort", …)` block (gravity mutex group; `--criteria` `choices`). |
| `tests/test_spin.py` *(new)* | In-process core tests: acceptance cases A/B/C, all 6 anchor pairings, validation matrix, band verdicts, overrides, determinism, band-table integrity. |
| `tests/test_query_spin.py` *(new)* | Subprocess contract: happy-path JSON + core parity + exit-code matrix. |
| `docs/integration.md` | New "Rotating-habitat comfort (Phase W)" section + one quick-reference row; units on every field. |
| `docs/gui-architecture.md` | One Phase-W completion-status row (query.py-only, no GUI). |
| `CLAUDE.md` | Phase-W test bullet + `core/spin.py` / `core/spin_tables.py` note in the `core/` package list. |

---

## 2. Bundled data — `core/spin_tables.py` (verbatim from the request)

```python
_BAND_TOL = 0.01   # relative tolerance on band comparisons (see §Spec reconciliation)

_COMFORT_BANDS = {
    "conservative": {  # 1960s unadapted
        "max_rpm": 2.0, "min_gravity_g": 0.30, "max_gravity_g": 1.0,
        "min_tangential_velocity_ms": 6.0, "max_gradient_pct": 10.0, "max_coriolis_pct": 25.0},
    "moderate": {      # adapted
        "max_rpm": 4.0, "min_gravity_g": 0.20, "max_gravity_g": 1.0,
        "min_tangential_velocity_ms": 3.0, "max_gradient_pct": 15.0, "max_coriolis_pct": 25.0},
    "relaxed": {       # modern / Hall–Globus
        "max_rpm": 6.0, "min_gravity_g": 0.10, "max_gravity_g": None,
        "min_tangential_velocity_ms": None, "max_gradient_pct": 25.0, "max_coriolis_pct": None},
}
```

`_MODEL_NOTE` names the lineage and the three provenance footnotes (verified at plan time
against Hall, JBIS 52, 1999, Table 1 — `artificial-gravity.com/JBIS-52-7-Hall.pdf`):

- Studies cited: Hill & Schnitzer 1962, Gilruth 1969, **Gordon & Gervais 1969**, Stone 1973,
  Cramer 1985 (synthesized in Hall 1997 / SpinCalc). *(Gordon & Gervais is Table 1's 6th study,
  added to the request's five.)*
- The RPM ladder (2 / 4 / 6) and the whole min-gravity column (0.30 / 0.20 / 0.10 g) are
  verbatim-published and fully confirmed.
- **Footnote 1:** the conservative gradient **10 %** has no direct published basis — Table 1
  gives 8 % (Gilruth, Gordon & Gervais) and 25 % (Stone); 10 % is a design choice between them.
- **Footnote 2:** published gradient caps are defined over a **2 m** head-to-foot span; the
  default `--occupant-height-m` is **1.8 m** (gradient scales linearly with h).
- **Footnote 3:** Stone's 25 % Coriolis/apparent-weight cap is defined at a **1.2 m/s** carry
  speed; the default `--walk-speed-ms` is **1.0 m/s**.
- The bands are a human-factors **choice, not physics**; every threshold is caller-overridable.

A `test_spin.py` golden test pins `_COMFORT_BANDS` to these exact values (drift guard, like
Phase V's `test_nist_pinned_grid`).

---

## 3. Formulas (exact rotational kinematics)

`ω` = angular velocity [rad/s]; `RPM = ω·60/2π`; `r` = radius to the feet [m]; `g₀ = 9.80665`.

- **Centrifugal gravity (feet):** `a = ω²·r`; `gravity_g = a / g₀`.
- **Rim tangential velocity:** `v = ω·r`.
- **Head-to-foot gradient:** at head height `h`, `a_head = ω²·(r − h)`;
  `gravity_gradient_fraction = (a − a_head)/a = h/r`; also report `head_accel_ms2`,
  `head_gravity_g`. (Reject `h ≥ r`.)
- **Coriolis on a walking occupant:** `a_cor = 2·ω·u` (u = `--walk-speed-ms`);
  `coriolis_ratio = a_cor/a = 2u/v`; report `coriolis_accel_ms2`, `coriolis_ratio`, `_pct`.

**Solve from any two anchors** — all six pairings are determinate; derive (ω, r) then the rest:

| Anchors | ω | r |
|---|---|---|
| (r, rpm) | `rpm·2π/60` | given |
| (r, a) | `√(a/r)` | given |
| (r, v) | `v/r` | given |
| (rpm, a) | `rpm·2π/60` | `a/ω²` |
| (rpm, v) | `rpm·2π/60` | `v/ω` |
| (a, v) | `v/r` | `v²/a` |

---

## 4. `query.py` wiring (modeled on the `cooling-hz` block)

```python
def cmd_spin_comfort(args):
    accel = args.accel_ms2
    if args.gravity_g is not None:
        accel = args.gravity_g * 9.80665          # gravity form → accel (argparse mutex guarantees not both)
    _out(spin.compute_spin_comfort(
        radius_m=args.radius_m, rpm=args.rpm, accel_ms2=accel,
        tangential_velocity_ms=args.tangential_velocity_ms,
        occupant_height_m=args.occupant_height_m, walk_speed_ms=args.walk_speed_ms,
        criteria=args.criteria,
        max_rpm=args.max_rpm, min_gravity_g=args.min_gravity_g, max_gravity_g=args.max_gravity_g,
        min_tangential_velocity_ms=args.min_tangential_velocity_ms,
        max_gradient_pct=args.max_gradient_pct, max_coriolis_pct=args.max_coriolis_pct))
```

Parser: four optional state anchors (`--radius-m`, `--rpm`, `--tangential-velocity-ms`, and a
`grav = add_mutually_exclusive_group()` holding `--gravity-g` / `--accel-ms2`); `--occupant-height-m`
`default=1.8`; `--walk-speed-ms` `default=1.0`; `--criteria` `choices=[conservative,moderate,relaxed,all]`
`default="all"`; six optional `--max-*/--min-*` override floats. All numerics `type=float`.

---

## 5. Output shape (→ `docs/integration.md` for the authoritative per-key schema)

```
{ radius_m, rpm, angular_velocity_rads, accel_ms2, gravity_g, tangential_velocity_ms,
  occupant_height_m, head_accel_ms2, head_gravity_g, gravity_gradient_fraction, gravity_gradient_pct,
  walk_speed_ms, coriolis_accel_ms2, coriolis_ratio, coriolis_ratio_pct,
  anchors: [<the two supplied>],
  criteria: { conservative: { pass: bool, checks: { max_rpm:{value,threshold,pass}, min_gravity_g:{…},
              max_gravity_g:{…}, min_tangential_velocity_ms:{…}, max_gradient_pct:{…}, max_coriolis_pct:{…} } },
              moderate:{…}, relaxed:{…} },
  overridden_thresholds: [ … ] or [],
  model_note, notes }
```

- All inputs echoed. A `null`-threshold check reports `pass: null` (not checked); a tier's
  `pass` = all non-null checks pass.
- `--criteria <tier>` returns only that tier's block; `all` (default) returns all three.

---

## 6. Validation contract (self-validating, Phase-H/P → curated `{"error"}` exit 1)

- **Core `{"error"}` exit 1:** any supplied anchor ≤ 0 (radius / rpm / gravity / accel /
  velocity); `occupant-height-m ≤ 0` or `≥ radius-m`; `walk-speed-ms ≤ 0`; **not exactly two**
  state anchors (0, 1, 3, or 4 → error); an override threshold ≤ 0; an override percentage
  outside (0, 100].
- **Argparse exit 2:** `--gravity-g` **and** `--accel-ms2` both given (mutex); a bad
  `--criteria` choice; any non-numeric value.

*(No "required" argparse arg — the four state anchors are all optional at the parser level;
"exactly two" is enforced in the core so the count error is a curated exit-1, not exit-2.)*

---

## 7. Spec reconciliation (two acceptance-section fixes — flag back to the requester on shipment)

Worked by hand at plan time; both are captured so the tests are correct and the request's
acceptance verdicts hold:

1. **Max-gravity boundary.** Cases A (r=224, rpm=2) and C (r=56, rpm=4) both compute
   `gravity_g = 1.0019 g` (round inputs land 0.19 % over 1 g), yet the request asserts they
   PASS tiers whose `max_gravity_g = 1.0`. **Resolution:** band comparisons use a small
   relative tolerance `_BAND_TOL = 0.01` — `max_*` passes if `value ≤ threshold·(1+TOL)`,
   `min_*` if `value ≥ threshold·(1−TOL)`. So a nominal-1 g design isn't spuriously failed by
   the 1 g ceiling; the real failures (Case B rpm 9.46 vs 2/6, gradient 18 vs 10) are 100s of
   % over and unaffected. *(Alternative if the user prefers strict `≤`: fix the request's
   Case A/C acceptance instead. Tolerance chosen as the lower-friction path.)*
2. **Case B "coriolis fail" prose.** The request's parenthetical lists Coriolis as a failing
   check, but `coriolis_ratio_pct ≈ 20.2 % < 25 %` cap → it **PASSES**. The Case B tier
   verdict FAIL still holds (driven by `max_rpm` and `max_gradient`). Tests assert the tier
   FAILs and that `max_rpm`/`max_gradient` fail — they do **not** assert Coriolis fails.

Both are recorded in the request-file handoff note on shipment (the requester updates the
acceptance section's max-gravity verdicts and the Case B parenthetical).

---

## 8. Tests

**`tests/test_spin.py`** (in-process; constants g₀=9.80665, h=1.8, u=1.0):

- **Acceptance A** — `compute_spin_comfort(radius_m=224, rpm=2.0)`: `accel_ms2≈9.8257`,
  `gravity_g≈1.0019`, `tangential_velocity_ms≈46.91`, `gravity_gradient_pct≈0.80`,
  `head_gravity_g≈0.994`, `coriolis_ratio_pct≈4.26`; `anchors==["radius_m","rpm"]`;
  `criteria.conservative.pass is True` (all checks, incl. max-gravity via `_BAND_TOL`).
- **Acceptance B** — `radius_m=10, accel_ms2=9.80665` (the `--gravity-g 1.0` path):
  `rpm≈9.457`, `tangential≈9.90`, `gradient_pct≈18.0`, `head_gravity_g≈0.820`,
  `coriolis_pct≈20.2`; `conservative.pass is False`; `relaxed.pass is False`; assert
  `conservative.checks.max_rpm.pass is False` **and** `max_gradient_pct.pass is False` **and**
  `max_coriolis_pct.pass is True` (guards reconciliation #2).
- **Acceptance C** — `radius_m=56, rpm=4.0`: `accel≈9.8257`, `tangential≈23.46`,
  `gradient_pct≈3.21`, `head_gravity_g≈0.970`, `coriolis_pct≈8.53`;
  `conservative.pass is False` (max_rpm), `moderate.pass is True`, `relaxed.pass is True`
  (guards reconciliation #1 — moderate passes despite 1.0019 g).
- **Solve pairings** — for a fixed design, all six anchor pairs recover the same (ω, r)
  within tolerance: feed (r,rpm), (r,a), (r,v), (rpm,a), (rpm,v), (a,v) drawn from the Case A
  design and assert `angular_velocity_rads`/`radius_m` agree.
- **Solve consistency** — `accel_ms2=9.80665, tangential_velocity_ms=6` → `radius_m≈3.67`,
  `rpm≈15.6` (the request's "meets tangential floor but blows the RPM ceiling" example).
- **Validation matrix** — each returns `{"error"}`: `occupant_height_m=12` with `radius_m=10`
  (h≥r); three anchors (r+rpm+v); one anchor (r only); zero anchors; `radius_m=0`; `rpm=-1`;
  `walk_speed_ms=0`; `max_rpm=0` override; `max_gradient_pct=150` override (>100).
- **Overrides** — `max_rpm=10` flips Case C conservative to pass; `overridden_thresholds`
  lists `"max_rpm"`; a non-overridden run has `overridden_thresholds == []`.
- **Single-tier** — `criteria="moderate"` → `criteria` dict has only the `moderate` key.
- **Determinism** — same inputs twice → deep-equal output (no RNG/time; parity with the suite).
- **Band-table integrity** — `_COMFORT_BANDS` equals the §2 literal exactly (golden pin).

**`tests/test_query_spin.py`** (subprocess, mirrors `test_query_thermal.py`):

- Happy-path JSON for Case A + core parity (`subprocess == compute_spin_comfort(...)`).
- Exit-code matrix: **exit 1** curated `{"error"}` for `--radius-m 0`, `h≥r`, one anchor,
  three anchors, a `--max-rpm 0` override; **exit 2** for `--gravity-g 1 --accel-ms2 9.8`
  (mutex), a bad `--criteria xyz` choice, and a non-numeric `--rpm abc`.

---

## 9. Success criteria (Packet 14's acceptance)

- Reproduces every acceptance anchor in the request — Cases A / B / C and the solve-consistency
  case — numerically, with the `_BAND_TOL` reconciliation documented (§7).
- All six anchor pairings determinate and mutually consistent; `anchors` echoes the supplied two.
- The three derived quantities (`tangential_velocity_ms`, `gravity_gradient_pct`,
  `coriolis_ratio_pct`) are exposed — the gap the `gravity-*` solves can't fill.
- Bands are verbatim from the request, pinned by the integrity test; `model_note` carries the
  full six-study provenance + the three footnotes + the "criteria are a choice" statement.
- Validation matrix passes (curated exit-1 / argparse exit-2 split per §6).
- Documented in `docs/integration.md` contract-by-reference with **units on every field**; one
  `docs/gui-architecture.md` completion row (query.py-only); one `CLAUDE.md` test bullet.
- The two §7 spec-reconciliation items flagged back to the requester on shipment.

---

## 10. Risks & sequencing

**Sequencing:** `_STANDARD_GRAVITY` in `equations.py` → `spin_tables.py` (bands + `_MODEL_NOTE`
+ golden pin) → `core/spin.py` (solver + derived + verdict) → `query.py` wiring → **run the
three acceptance cases against the live tool** (the verification gate, before tests) → tests →
docs (`integration.md`, `gui-architecture.md`, `CLAUDE.md`).

**Risks:**
- The only non-mechanical items are the **two spec inconsistencies** (§7) — resolved now
  (band tolerance + trust-the-math), not correctness risks; recorded for the requester.
- Everything else is closed-form rotational kinematics over verified constants; the bands are
  transcribed static data with a provenance note. ~1 focused session.

---

## References (verify at implementation; none is a load-bearing canon claim)

- **Rotational kinematics** (`a = ω²r`, `v = ωr`, Coriolis `a_cor = 2ωu`): any classical-
  mechanics text. `g₀ = 9.80665 m/s²` (standard gravity, CGPM).
- **Comfort chart / criteria bands:** Hill & Schnitzer 1962; Gilruth 1969; Gordon & Gervais
  1969; Stone 1973; Cramer 1985 — synthesized in Hall, T. W. (1997/1999), *The Architecture of
  Artificial Gravity* / "Artificial Gravity and the Architecture of Orbital Habitats," JBIS 52,
  Table 1 (`artificial-gravity.com/JBIS-52-7-Hall.pdf`), and Hall's *SpinCalc*. Band values
  confirmed against Table 1 at plan time (see §2). None is a load-bearing canon claim.
