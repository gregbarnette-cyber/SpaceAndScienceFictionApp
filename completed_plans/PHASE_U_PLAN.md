# Phase U — Cooling-Primary HZ-Residence Calculator (`cooling-hz`)

**Status:** Built (2026-06-27). Implements the sister-project request
`scifiWorldBuilding-Claude/research/query-api-methods/cooling-hz-calculator-request.md`
(Pkts 6/7; feeds 12).

> **Phase AD A0 extension (2026-07-03):** added the WD-only **²²Ne distillation cooling pause**
> (`cooling-hz --cooling-delay-gyr Δ` / `--distillation-teff-k`, default off/5500 K). A
> wall-clock→track-age warp (`_warp_age` + a `pause=(a_pause, Δ)` tuple threaded through the
> interpolators/modes with default `None`) freezes (Teff, L, R) at the distillation-onset epoch
> for Δ Gyr, lengthening HZ residence and pushing the long-residence CHZ outward. **Δt=0 is
> byte-identical** to the original Phase U output. Onset 5500 K = the published 0.6 M☉ DA value
> (Vanderburg, Bédard, Becker & Blouin 2025, arXiv:2501.06613 §2); peak residence 6.3→16.3 Gyr at
> Δ=10 reproduces their Table 1 (6.67→15.56). See `PHASE_AD_PLAN.md` §Phase 5 + `docs/integration.md`.

> **Build notes (deviations from the plan, all validated):**
> - **Cooling track:** WD = **Bédard et al. 2020 / Montreal** thick-H sequences (the modern
>   successor to Fontaine 2001, served at the same site); BD = **ATMO 2020** CEQ tracks. Both
>   transcribed/parsed from the published files and **closure-verified row-by-row**
>   (`L=(R/R☉)²(Teff/T☉)⁴`), which auto-caught and dropped several extractor-mangled rows.
>   Grid: WD 0.4–1.0 M☉ (7 masses), BD ~13.6–75.4 M_Jup (7 masses).
> - **L is derived from interpolated (Teff, R) via the closure**, not interpolated
>   independently — removes a sparse-grid drift that was failing the snapshot anchor.
> - **Asymmetric Kopparapu gate** (vs the plan's symmetric §5 idea): the *hot* side (>7200 K)
>   is gated (the polynomial goes negative there — fixes a far-orbit false-positive), but the
>   *cool* side (<2600 K) is **allowed and flagged** `*_out_of_range` (gentle extrapolation,
>   and required to reproduce Bolmont's Gyr-scale cooling-BD residence). Snapshot keeps pure
>   flag-don't-clamp.
> - **Roche cross-check uses the fluid** (rubble-pile) limit as the tidal-disruption radius,
>   which surfaces the Pkt-7-R2 cool-WD collision.
> - Residence flags are `entry/exit_out_of_range` + `truncated_at_age_max`.

**Designation:** next free phase letter after T → **Phase U**. Integration-surface only
(no GUI, no DB, no live network), in the Phase-N/T lineage. One `query.py` subcommand, a new
core module, and bundled static cooling tables.

## Resolved implementer decisions (the request's three open items)

1. **Out-of-range (Kopparapu validity) policy** — flag at every point that feeds a reported
   number, never clamp/error (extends the `circumbinary-hz` convention).
2. **Cooling track** — **bundled static cooling tables** (Montreal WD + Baraffe/ATMO BD),
   transcribed from the published grids as inline Python constants. The accurate, literature-
   faithful path (the request's recommendation; chosen over analytic Mestel/fit).
3. **Dispatch** — **one** subcommand `cooling-hz --track {wd,bd}`; mode chosen by a single
   argparse mutex group `{--teff, --cooling-age-gyr, --sma-au}`; mass via a second mutex group
   `{--mass-solar, --mass-mjup}` (BD primary = `--mass-mjup`). Folds in the request's Open
   items #2 (one subcommand) and #3 (BD units).

---

## 1. Files touched

| File | Change |
|---|---|
| `core/cooling.py` | **New.** The engine + `compute_cooling_hz(...)`. Imports `compute_habitable_zone` / `compute_roche_limit` from `core.equations` (reuse, never re-derive). |
| `core/cooling_tables.py` | **New.** The digitized Montreal (WD) + Baraffe/ATMO (BD) grids as inline Python constants, isolated from logic so the data is auditable and swappable. |
| `query.py` | Add `cmd_cooling_hz(args)` + the `cooling-hz` argparse parser with the two mutex groups. |
| `tests/test_cooling_hz.py` | **New.** Core unit tests (offline, in-process). |
| `tests/test_query_cooling_hz.py` | **New.** Subprocess contract tests (mirrors `tests/test_query_phase_t.py`'s `_run` harness). |
| `docs/integration.md` | New "Cooling-primary HZ" subsection: per-key schema, adopted table sources/versions, root-find tolerance, BD mass conversion, the Phase-U quick-reference row. |
| `docs/gui-architecture.md` | One Phase-U row in the completion-status table (no GUI — "query.py-only"). |

Why a dedicated module (not `equations.py`): the bundled grids are bulky and the integration/
root-finding is substantial — same rationale as `core/dust.py` / `core/feasibility.py` being
separate. `equations.py` stays the home of the *reused* primitives.

## 2. Bundled cooling tables (the data, sourced not fabricated)

`core/cooling_tables.py` holds two dicts, mass → list of `(age_gyr, teff_k, log10_l_lsun,
radius_rsun)` rows:

```python
# Fontaine, Brassard & Bergeron 2001 / Montreal cooling sequences (DA, thick H).
_WD_COOLING = { 0.4: [...], 0.5: [...], 0.6: [...], 0.7: [...], 0.8: [...], 0.9: [...], 1.0: [...] }
# Baraffe et al. 2003 (COND) / Phillips et al. 2020 (ATMO 2020).
_BD_COOLING = { 13: [...], 20: [...], 30: [...], 40: [...], 50: [...], 65: [...], 80: [...] }  # M_Jup
_WD_TABLE_SOURCE = "Fontaine, Brassard & Bergeron 2001 (Montreal cooling sequences, DA/thick-H)"
_BD_TABLE_SOURCE = "ATMO 2020 (Phillips et al. 2020)"
```

**Sourcing discipline (load-bearing):** the row values are transcribed from the published grids
at implementation — numbers are **not** invented. Each grid carries Teff, L, and radius (Montreal
gives log g → R; ATMO gives R directly), so the table subsumes the request's "mass–radius" step 1
and supplies the Roche cross-check radius. The §6 acceptance benchmarks are the correctness gate
on the transcription. Each dict gets a one-line provenance comment; sources echo into
`docs/integration.md` and the per-response `model_note`.

## 3. Core API (`core/cooling.py`)

```python
def compute_cooling_hz(track, mass_solar=None, mass_mjup=None,
                       cooling_age_gyr=None, teff=None, sma_au=None,
                       chz_threshold_gyr=3.0, hz_edge="conservative",
                       age_max_gyr=13.8, satellite_density=5.5) -> dict
```

Private helpers, all in this module:
- `_interp_track(track, mass_solar, age_gyr) -> (teff_k, lum_lsun, radius_rsun)` — bilinear
  interpolation in (mass, age), **log-space for L**, linear for Teff/R; bisect within the
  per-mass age grid. Off-grid mass/age → sentinel → `{"error"}`.
- `_track_age_for_teff(track, mass_solar, teff) -> age_gyr` — invert the (monotonic-cooling)
  Teff(age) for the `--teff` epoch in mode 1.
- `_hz_edges_au(teff, lum, hz_edge) -> (inner_au, outer_au)` — calls `compute_habitable_zone`,
  picks `rg`/`mg` (conservative) or `rv`/`em` (optimistic) from the `_ZONE_DEFS` keys
  (`equations.py:286`).
- `_residence_at(track, mass_solar, sma_au, hz_edge, age_max_gyr) -> dict` — the mode-2 root-find.
- `_TEFF_SUN_K = 5772.0` for the `L↔Teff` consistency check (the table supplies both, so closure
  is a guard, not the primary path).

## 4. Physics / algorithm per mode

**Crossing geometry (load-bearing direction):** the dwarf cools → L decreases monotonically →
both HZ edges shrink in AU. For a planet at fixed `a`:
- `inner_au(age) = √(L(age)/Seff_inner)` (hot edge), `outer_au(age) = √(L(age)/Seff_outer)`
  (cold edge), both decreasing.
- Young: `a < inner_au` → **too hot**. → `inner_au` shrinks to `a`: **entry**. → habitable while
  `inner_au < a < outer_au`. → `outer_au` shrinks to `a`: **exit** (too cold).
- `entry_age` = root of `inner_au(age)=a`; `exit_age` = root of `outer_au(age)=a`;
  `residence = exit − entry`.

**Mode 1 — snapshot.** Epoch from `--cooling-age-gyr` (direct interp) or `--teff` (invert track).
→ `(teff_k, lum_lsun, radius_rsun)` → `compute_habitable_zone(teff, lum)` → zones. Flag
`out_of_range_teff` (echo teff) when teff ∉ [2600, 7200], **still return zones** — the
`circumbinary-hz` convention (`equations.py:514`).

**Mode 2 — residence at `a`.** Bisection on age over `[0, age_max_gyr]` for each crossing
(L(age) monotonic ⇒ unique roots), tolerance **1e-4 Gyr** (documented in `integration.md`). Edge
cases as explicit booleans, never errors:
- a never habitable → `ever_habitable=False`, ages/residence `null`.
- inside HZ at age 0 → `entry_age_gyr=0.0`, note `entry_before_track_start`.
- exit beyond `age_max` → `exit_age_gyr=null`, `truncated_at_age_max=True`, residence is a lower
  bound.
- Carry `entry_teff_k`/`exit_teff_k` + `entry_out_of_range`/`exit_out_of_range` (the §5 policy —
  the crossings determine trustworthiness).

**Mode 3 — CHZ band.** Sweep `a` on a log grid spanning the youngest-epoch HZ out to the
oldest-epoch HZ; compute `residence(a)` via mode-2 logic; report `chz_inner_au` / `chz_outer_au`
= extremal `a` with `residence ≥ chz_threshold_gyr`. Roche cross-check via
`compute_roche_limit(primary_mass_earth = mass_solar·332946, satellite_density,
primary_radius_earth = radius_rsun·109.2)` at the cool epoch; if `chz_inner_au < rigid_au` set
`inner_edge_roche_limited=True` + echo `roche_limit_au` (rocky `rigid_au` floor; documented). Flag
`chz_inner/outer_out_of_range` from the controlling crossings.

## 5. Out-of-range policy (Decision #1, applied)

Per-point flagging, never clamp/error: mode 1 → `out_of_range_teff`; mode 2 →
`entry/exit_out_of_range`; mode 3 → `chz_inner/outer_out_of_range`; **all modes** → top-level
`any_out_of_range` (bool) + `hz_model_valid_teff_k: [2600, 7200]`. Young-hot-WD epochs
(Teff > 7200 K) self-flag without poisoning the cool-epoch residence numbers.

## 6. `query.py` wiring (Decision #3, applied)

One subcommand `cooling-hz`. Two argparse mutex groups give the whole dispatch for free:

```python
p = sub.add_parser("cooling-hz", help="Cooling-primary (WD/BD) HZ residence & CHZ")
p.add_argument("--track", required=True, choices=["wd", "bd"])
m = p.add_mutually_exclusive_group()                 # mass, ≤1 (default per track)
m.add_argument("--mass-solar", type=float)
m.add_argument("--mass-mjup", type=float)            # BD primary unit
mode = p.add_mutually_exclusive_group()              # mode selector, ≤1
mode.add_argument("--teff", type=float)              # → mode 1
mode.add_argument("--cooling-age-gyr", type=float)   # → mode 1
mode.add_argument("--sma-au", type=float)            # → mode 2;  none → mode 3
p.add_argument("--chz-threshold-gyr", type=float, default=3.0)
p.add_argument("--hz-edge", choices=["conservative","optimistic"], default="conservative")
p.add_argument("--age-max-gyr", type=float, default=13.8)
p.add_argument("--satellite-density", type=float, default=5.5)
p.set_defaults(func=cmd_cooling_hz)
```

Dispatch truth table (enforced by the `mode` group):

| supplied | mode |
|---|---|
| `--teff` **or** `--cooling-age-gyr` | 1 snapshot |
| `--sma-au` | 2 residence |
| none | 3 CHZ (default) |

`cmd_cooling_hz` passes args to the core, which self-validates and returns the dict; `_out`
handles exit 0/1 (`query.py:26`). Bad `--track`/`--hz-edge`, both mass args, two mode args, or
non-numeric values → argparse **exit 2** automatically. BD `--mass-mjup` primary (conversion
1 M_Jup = 9.543e-4 M☉, documented); defaults WD 0.6 M☉ / BD 50 M_Jup.

## 7. Validation contract (self-validating, Phase-H/P)

Curated `{"error"}` + exit 1 from the core for: `--track ∉ {wd,bd}`; mass off the bundled grid
(range stated in the message + docs); `cooling_age_gyr ≤ 0`; `teff ≤ 0`; `sma_au ≤ 0`;
`chz_threshold_gyr ≤ 0`; `age_max_gyr ≤ 0`; `satellite_density ≤ 0`. Geometry leaving the HZ /
orbit never habitable → **booleans, not errors**. `model_note` present in every response.

## 8. Output shapes (→ `docs/integration.md` for the authoritative per-key schema)

- **Mode 1:** `{track, mass_solar, cooling_age_gyr, teff_k, lum_lsun, radius_rsun, zones[],
  out_of_range_teff, any_out_of_range, hz_model_valid_teff_k, model_note, …inputs}`.
- **Mode 2:** `{track, mass_solar, sma_au, hz_edge, ever_habitable, entry_age_gyr, exit_age_gyr,
  residence_gyr, entry_teff_k, exit_teff_k, entry_out_of_range, exit_out_of_range,
  truncated_at_age_max, inside_roche, any_out_of_range, hz_model_valid_teff_k, model_note,
  …inputs}`.
- **Mode 3:** `{track, mass_solar, chz_threshold_gyr, hz_edge, chz_inner_au, chz_outer_au,
  inner_edge_roche_limited, roche_limit_au, chz_inner_out_of_range, chz_outer_out_of_range,
  any_out_of_range, hz_model_valid_teff_k, model_note, …inputs}`.
- `zones[]` matches `compute_habitable_zone` (`{zone_name, key, au, lm, seff}`).

## 9. Tests

**`tests/test_cooling_hz.py` (core, in-process, offline):**
1. Table integrity — every grid row monotone-cooling (Teff & L decrease with age); interpolation
   reproduces grid nodes exactly; off-grid mass/age → `{"error"}`.
2. `_hz_edges_au` picks `rg`/`mg` vs `rv`/`em` correctly; matches a direct `compute_habitable_zone`.
3. Mode 1 determinism + the `L↔Teff` closure consistency (table L vs `(R/R☉)²(T/T☉)⁴`).
4. Mode 2 crossing direction (synthetic monotone track: entry at hot edge, exit at cold edge,
   residence > 0); the three edge-case booleans.
5. Mode 3 band ordering (`chz_inner < chz_outer`) + Roche flag wiring (force a sub-Roche inner edge).
6. Validation matrix (every `{"error"}` branch).

**`tests/test_query_cooling_hz.py` (subprocess, `_run` harness from `test_query_phase_t.py`):**
- Happy-path exit 0 + JSON shape for each mode; core-parity (subprocess == in-process).
- Exit-code matrix: curated-error exit 1 (off-grid mass, `--sma-au 0`); argparse exit 2 (bad
  `--track`, both mass args, `--teff`+`--sma-au` together, non-numeric).
- `model_note` + `hz_model_valid_teff_k` present; `any_out_of_range` toggles for a hot-young-WD
  snapshot.

**Acceptance benchmarks (asserted, order-of-magnitude tolerance where the request says so):**

| Test | Assertion |
|---|---|
| WD snapshot | 0.6 M☉ @ 5000 K → `lum_lsun` ≈ 9.2e-5 (±10%), conservative HZ ≈ 0.0095–0.017 AU (±10%) — *exact, table-independent closure (verified by hand at planning)*. |
| WD residence | 0.6 M☉, a=0.01 AU → `residence_gyr` ≈ 8 (within ×1.5). |
| WD CHZ | 0.6 M☉, τ=3 → `chz_inner_au`/`chz_outer_au` ≈ 0.005–0.02 AU; reproduces across 0.4–0.9 M☉. |
| BD residence | fixed-orbit residence tens–hundreds Myr; ≥1 Gyr only for mass > 0.05 M☉ (~52 M_Jup). |
| Caveats | `inner_edge_roche_limited=True` for the cool-WD CHZ inner edge; `out_of_range_teff=True` for a hot young WD; `model_note` non-empty in every response. |

## 10. Success criteria

1. All five acceptance benchmarks pass at their stated tolerance (snapshot exact; residence/CHZ
   to order-of-magnitude).
2. `pytest tests/test_cooling_hz.py tests/test_query_cooling_hz.py` green; full suite still green
   (additive — `equations.py` reuse is read-only).
3. Exit-code contract holds: 0 success / 1 curated-error / 2 argparse, verified by the matrix.
4. `docs/integration.md` documents every output key, the adopted **table sources + versions**,
   the root-find tolerance, the BD mass conversion, and the Phase-U quick-reference row —
   contract-by-reference, matching the T1a/T1b precedent.
5. No GUI/DB/CLI-menu/network surface added; `core.cooling` importable without the GUI/Qt stack;
   off-grid masses rejected cleanly (no silent extrapolation).
6. Determinism: identical inputs → byte-identical JSON (no RNG, no time/network).

## 11. Risks & sequencing

- **Top risk: table transcription accuracy.** Mitigation: the acceptance benchmarks gate it;
  build the 0.6 M☉ WD track first and confirm the snapshot/residence/CHZ trio before filling the
  rest of the grid.
- **BD non-power-law cooling** is exactly why tables were chosen — interpolation handles it; the
  BD acceptance benchmark is the check.
- **Sequencing:** (a) `cooling_tables.py` with the 0.6 M☉ WD row + interpolation; (b)
  `compute_cooling_hz` modes 1→2→3 against that single track; (c) acceptance trio passes; (d) fill
  remaining WD masses + BD grid; (e) query.py wiring + subprocess tests; (f) docs.

## References (verify at implementation)

- WD cooling/mass–radius: Fontaine, Brassard & Bergeron 2001 + the Montreal cooling sequences;
  Nauenberg 1972 / Eggleton (mass–radius).
- BD/substellar cooling: Baraffe et al. 2003 (COND/DUSTY); Phillips et al. 2020 (ATMO 2020).
- HZ boundaries: Kopparapu et al. 2013/2014 (already in `compute_habitable_zone`).
- Benchmark habitability numbers (acceptance targets, not formula sources): Agol 2011 (ApJL
  731:L31); Fossati et al. 2012 (MNRAS); Bolmont et al. 2011/2017.
