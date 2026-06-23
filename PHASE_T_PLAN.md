# Phase T — `query.py` Research-Tooling Extensions — Build Plan

> **Status: Planned (2026-06-22).** Requested by the sibling worldbuilding repo
> `scifiWorldBuilding-Claude` as two companion request specs (each carrying a full Q&A +
> implementer-decisions thread, all resolved 2026-06-22):
> - `…/scifiWorldBuilding-Claude/research/query-api-methods/calculator-extensions-request.md`
> - `…/scifiWorldBuilding-Claude/research/query-api-methods/dust-map-query-request.md`
>
> Overview + priority live in `future_phases.md` (Phase T section). This file is the build-ready spec.
> **T1a is fully detailed below; T1b / T1c / T2 are stubbed** (built out before their respective builds).

## Surface & posture (applies to all of Phase T)

- **`query.py`-surface work** (Phase-N-style), **not** GUI. The consumer drives every feature through the
  venv/JSON contract. **No native-Windows GUI; no `wsl.exe` bridge** (declined). Dust (T2) runs in the
  WSL/Linux venv, gated absent on a native-Windows pip checkout.
- **Two independent tracks: T1 (calculators/census, pure-math/local-DB) → then T2 (dust, new optional dep).**
- All new subcommands are **self-validating** (Phase-H/P contract): curated `{"error": str}` → exit 1;
  argparse → exit 2; success dict → exit 0. Documented contract-by-reference in `docs/integration.md`,
  units declared per field, order-of-magnitude outputs labelled.
- **Reuse the verified R2/H core wherever it exists.** On a request-vs-existing convention conflict, the
  **R2 / cited-source form wins** (state the chosen form in `docs/integration.md`).

### `query.py` idiom (verified 2026-06-22)

```python
# registration
p = sub.add_parser("name", help="…")
p.add_argument("--foo", required=True, type=float)
p.add_argument("--bar", type=float, default=0)
p.set_defaults(func=cmd_name)

# handler
def cmd_name(args):
    _out(module.compute_thing(args.foo, bar=args.bar))

# _out() (existing): prints json.dumps(result, indent=2, default=str);
#   sys.exit(1) if isinstance(result, dict) and "error" in result, else sys.exit(0)
```

### Test idiom (verified — mirror `tests/test_query_phase_n.py`)

```python
_ENV = {"SPACE_APP_DB": "<throwaway>.db", "PATH": os.environ.get("PATH", "")}
def _run(*cmd_args):
    proc = subprocess.run([sys.executable, str(_REPO/"query.py"), *cmd_args],
                          capture_output=True, text=True, cwd=str(_REPO), env=_ENV)
    try: payload = json.loads(proc.stdout)
    except Exception: payload = None
    return proc.returncode, payload, proc.stderr
```

---

# Phase T1 — Calculator & census extensions (pure-math / local-DB; no new datasets)

Sub-staged by confidence: **T1a** near-free reuse wrappers → **T1b** new pure-math → **T1c** census filters.

## Phase T1a — near-free reuse wrappers (DETAILED)

5 items, sequenced by risk: items 1–3 are purely additive (touch nothing existing); items 4–5 modify
existing functions (additively).

### Verified existing signatures (the reuse surface)

| Function | File:loc | Signature | Returns |
|---|---|---|---|
| `gascheau_coorbital_stable` | `core/feasibility.py:127` | `(host_mass_earth, companion_mass_earth, star_mass_solar)` | `{mass_ratio, criterion (≈0.038521), stable}` or `{error}` |
| `compute_hill_sphere` | `core/equations.py:584` | `(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0)` | `{…inputs, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au}` or `{error}` |
| `compute_habitable_zone` | `core/equations.py:416` | `(teff, luminosity)` | **list** of 6 `{zone_name, key, au, lm, seff}` |
| `compute_gcns_within_sol` | `core/databases.py:2298` | `(limit_ly)` → returns full `_GCNS_ROW_COLS` (incl. `wd_prob`) | `{limit_ly, count, snapshot_date, gcns_version, stars[]}` |

Module constants available in `core/equations.py:12`: `_G, _K_B, _EARTH_MASS_KG, _EARTH_RADIUS_KM,
_EARTH_RADIUS_M, _SOLAR_MASS_KG, _M_PER_AU, _KM_PER_AU, _AMU_KG, _SEC_PER_YEAR`; helper `_rocky_radius_km`.

---

### T1a-1 · `trojan-stability` — wrap R2 `gascheau_coorbital_stable` (zero new physics)

- **Core:** none new. Faithful wrapper over `gascheau_coorbital_stable` (already self-validating).
- **Convention (APPROVED — R2 form wins):** use the R2 signature, **not** the request's generic
  `--mass1/--mass2`. Same Gascheau/Routh criterion (μ = (m_host+m_companion)/m_star ≈ m_planet/m_star <
  0.0385) but correctly folds the co-orbital body's own mass into the numerator.
- **`query.py`:** subcommand `trojan-stability`; required floats `--host-mass-earth`, `--companion-mass-earth`,
  `--star-mass-solar`; `cmd_trojan_stability` → `_out(feasibility.gascheau_coorbital_stable(...))`.
- **Output:** the core dict `{mass_ratio, criterion, stable}` verbatim.
- **Validation:** inherited from the core fn — host & star mass > 0, companion ≥ 0, else `{error}` exit 1.
- **Touch-points:** none existing.

### T1a-2 · `lorentz-factor` — new trivial pure-math (D2)

- **Core (new):** `core/calculators.py::compute_lorentz_factor(velocity_c)` (lives with the velocity
  converters). `γ = 1/√(1−β²)`; `time_dilation_pct = (γ−1)·100`. Return
  `{velocity_c, lorentz_factor, time_dilation_pct}`.
- **Validation (self-validating):** `0 ≤ velocity_c < 1` else `{"error": "Velocity must be in the range
  0 ≤ β < 1 (sublight)."}`.
- **`query.py`:** subcommand `lorentz-factor`; required float `--velocity-c`.
- **Touch-points:** none. Keep explicitly distinct from the FTL `times-c`/`ly-hr` converters (docs note).

### T1a-3 · `circumbinary-hz` — new, reuses `compute_habitable_zone` (C1)

- **Core (new):** `core/equations.py::compute_circumbinary_hz(teff1, lum1, teff2, lum2)`.
  - **eff-Teff convention (APPROVED — luminosity/flux-weighted):**
    `eff_teff = (lum1·teff1 + lum2·teff2)/(lum1+lum2)`. (For a circumbinary planet the binary separation ≪
    planet orbit, so flux-weighted ≡ luminosity-weighted; collapses to `teff1` as `lum2→0`.)
  - `combined_lum = lum1 + lum2`; `zones = compute_habitable_zone(eff_teff, combined_lum)`.
  - **Out-of-range flag (APPROVED — flag, don't clamp):** if `eff_teff < 2600 or eff_teff > 7200`, set
    `out_of_range_teff = True` and echo `eff_teff`; **still return** the zones (more conservative than
    single-star `habitable-zone`'s silent extrapolation — binaries trip this far more often).
  - Return `{teff1, lum1, teff2, lum2, combined_lum, eff_teff, out_of_range_teff, zones}`.
- **Validation (self-validating):** all four inputs `> 0` else `{error}` exit 1.
- **`query.py`:** subcommand `circumbinary-hz`; required floats `--teff1 --lum1 --teff2 --lum2`.
- **DEFERRED to T1b:** the `--star1 --star2` SIMBAD-resolve input mode (keeps T1a pure-math/offline; the
  **core function is unchanged** when that mode is added — it's a `query.py`-layer resolver reusing the
  T1b/A-group per-star derive helper).
- **Touch-points:** none existing (reuses `compute_habitable_zone` read-only).

### T1a-4 · `hill-sphere` B3 extra keys — modify `compute_hill_sphere` (additive)

- **Core change:** extend
  `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0, moon_inclination_deg=0, prograde=True)`.
  - Domingos et al. 2006 factor (deg→rad internally per units decision): prograde
    `f = 0.4895·(1 − 1.0305·e − 0.2738·i_rad)`; retrograde `f = 0.9309·(…)` — **pin the exact retrograde
    coefficients against Domingos 2006 at build** (the request gives only the leading 0.9309).
  - Add keys: `stable_moon_limit_au = f × hill_radius_au` (headline), `stable_moon_limit_km`,
    `stable_fraction = f`. **Retain** `stable_orbit_limit_au/km` (0.5×r_H) as the coarse cross-check.
- **Validation:** existing checks unchanged; add `moon_inclination_deg` in `[0, 180]`; `prograde` bool.
  When new args are omitted (defaults), the *existing* keys are byte-identical to today.
- **`query.py`:** add `--moon-inclination-deg` (default 0) and `--retrograde` (store-true → `prograde=False`;
  default prograde) to the existing `hill-sphere` subparser; thread through `cmd_hill_sphere`.
- **Touch-points / risk (the one real one in T1a):**
  - `tests/test_worldbuilding.py` anchors `compute_hill_sphere` — **update the expected key set** (values for
    existing keys unchanged → safe).
  - Any `hill-sphere` `query.py` key-set assertion (`tests/test_query_expanded.py` / exposure tests) — update.
  - GUI `HillSpherePanel` reads specific keys → unaffected (additive). Surfacing the new keys in the GUI is
    **out of T1a scope** (T1a is `query.py`-surface).

### T1a-5 · `gcns-within-sol --wd-prob-min/max` — extend existing reader+subcommand (E1)

- **Finding:** there is **no GCNS search function** — only point readers. So E1 attaches to
  `compute_gcns_within_sol` (the closest census primitive), **not** a `search-*` function.
- **Core change:** extend `compute_gcns_within_sol(limit_ly, wd_prob_min=None, wd_prob_max=None)` — add the
  two optional range clauses to the existing radius `WHERE` (`wd_prob` is already in `_GCNS_ROW_COLS`). Both
  `None` → byte-identical to today.
- **Validation:** optional floats; a min > max simply matches nothing (not an error), consistent with the
  other range filters.
- **`query.py`:** add `--wd-prob-min` / `--wd-prob-max` to the existing `gcns-within-sol` subparser; thread
  through `cmd_gcns_within_sol`. (White-dwarf census primitive: "WD-likely sources within N ly.")
- **Touch-points / risk:** `tests/test_gcns.py` exercises `compute_gcns_within_sol`; new params default
  `None` so existing calls are unaffected — add a filtered case.
- **Alternative considered, NOT chosen for T1a:** a new `search-gcns` filterable census over `gcns_stars`
  (a real search fn) — more surface; deferrable. The `gcns-within-sol` extension delivers Pkt 7's WD census
  for far less.

### T1a — consolidated deliverables

- **Code:** `core/calculators.py` (+`compute_lorentz_factor`); `core/equations.py`
  (+`compute_circumbinary_hz`, extend `compute_hill_sphere`); `core/databases.py`
  (extend `compute_gcns_within_sol`); `query.py` (+3 subcommands `trojan-stability` / `lorentz-factor` /
  `circumbinary-hz`; +args on `hill-sphere` and `gcns-within-sol`). **No new modules.**
- **Docs:** `docs/integration.md` — new quick-reference rows + per-subcommand sections (units per field,
  self-validating contract stated). `docs/equations.md` — `compute_circumbinary_hz`,
  `compute_lorentz_factor`, and the `compute_hill_sphere` new keys. Mark T1a built in `future_phases.md`.

### T1a — test plan

- **New `tests/test_query_phase_t.py`** (mirrors the `test_query_phase_n.py` subprocess harness):
  - `trojan-stability` — happy-path key set `{mass_ratio, criterion, stable}`; **flips at μ≈0.0385** (a case
    just below stable / just above unstable); core-parity; missing/non-numeric arg → exit 2; bad masses
    (host or star ≤ 0) → exit 1.
  - `lorentz-factor` — γ at β=0 (=1), β=0.6 (=1.25), β→0.999 (large); `time_dilation_pct` parity; β=1 or
    β<0 → exit 1; missing/non-numeric → exit 2.
  - `circumbinary-hz` — 6-zone shape `{zone_name, key, au, lm, seff}`; lum-weighted `eff_teff` parity
    (e.g. equal stars → eff_teff = their common teff; degenerate lum2→0 → eff_teff≈teff1); `out_of_range_teff`
    True for an eff_teff outside 2600–7200; any input ≤ 0 → exit 1; missing arg → exit 2.
  - `hill-sphere` extension — new keys present; `stable_fraction` = 0.4895 at e=0/i=0 prograde;
    `stable_moon_limit_au = stable_fraction × hill_radius_au`; **existing keys/values unchanged** when new
    args omitted; `--retrograde` changes `f`.
  - `gcns-within-sol` extension — `--wd-prob-min` filters to high-WD sources; omitting the new args returns
    the unfiltered census byte-identical (seeded throwaway `gcns_stars`).
- **Core unit tests** (extend `tests/test_worldbuilding.py` for hill-sphere; add anchors for the new fns):
  trojan μ flip; lorentz γ values; circumbinary eff_teff + out-of-range; Domingos `f` anchor.
- **Update existing exact-key-set assertions** for `compute_hill_sphere` (additive keys).

### T1a — validation contract (per subcommand)

All **self-validating** (Phase-H/P), summarized for `docs/integration.md`:

| Subcommand | exit 1 (`{error}`) | exit 2 (argparse) |
|---|---|---|
| `trojan-stability` | host/star mass ≤ 0 (companion < 0) | missing / non-numeric arg |
| `lorentz-factor` | `velocity_c` ∉ [0,1) | missing / non-numeric |
| `circumbinary-hz` | any of teff1/lum1/teff2/lum2 ≤ 0 | missing / non-numeric |
| `hill-sphere` (extended) | existing (mass/sma ≤ 0, e ∉ [0,1)) + inclination ∉ [0,180] | missing / non-numeric |
| `gcns-within-sol` (extended) | empty `gcns_stars` table (existing) | non-numeric `--ly`/`--wd-prob-*` |

### T1a — success criteria / acceptance (done when)

- `trojan-stability` flips at μ≈0.0385; `lorentz-factor` correct (γ→∞ as β→1); `circumbinary-hz` returns the
  6 Kopparapu zones from `combined_lum` + lum-weighted `eff_teff` and flags (not clamps) out-of-range Teff;
  `hill-sphere` returns Domingos `stable_moon_limit_au`/`stable_fraction` alongside the retained 0.5 limit;
  `gcns-within-sol --wd-prob-min` filters white dwarfs.
- All five honor the validation matrix above (curated exit 1 / argparse exit 2).
- **Regression-clean:** existing `hill-sphere` / `gcns-within-sol` output is byte-identical with the new args
  omitted; the full suite is green after the two `compute_hill_sphere` key-set assertion updates.
- All five documented contract-by-reference in `docs/integration.md`; the three calculators in
  `docs/equations.md`.

---

## Phase T1b — new pure-math (STUB)

**Scope:** detectability group `rv-semi-amplitude` / `transit-signal` / `astrometric-signal` /
`direct-imaging` (A1–A4); `tidal-heating` (B1, incl. `io_flux_ratio`, order-of-mag flagged); `kozai-lidov`
(C2, order-of-mag, leading constant pinned at build); `relativistic-brachistochrone` (D1, lifts the 3%c
Newtonian cap). **Also:** the deferred `circumbinary-hz --star1 --star2` SIMBAD-resolve mode (reuses the
A-group per-star derive helper; core fn unchanged).

**Units/conventions (locked in the request thread):** A1 input `--planet-mass-earth` → M_Jup internally,
`k_ms` out; A3 primary in **µas** + arcsec echo; A4 contrast `A_g·(Rp/a)²` with Rp→AU; B3-style deg→rad
internal where applicable. **Pin at build:** B1 (Peale & Cassen 1978 / Segatz 1988), C2 (Kiseleva 1998 /
Antognini 2015), the `direct-imaging` IWA convention — record the chosen form in `docs/integration.md`.

**Validation:** all self-validating (Phase-H/P) — `e ∉ [0,1)`, non-positive masses/radii/distances, and
`relativistic-brachistochrone` requires `accel-g > 0`, `distance-ly > 0`.
**Tests:** extend `tests/test_query_phase_t.py` with the subprocess contracts + sanity anchors (Earth→Sun
≈ 84 ppm transit / ~0.09 m/s RV / ~1e-10 contrast; Jupiter→Sun at 10 pc ≈ 500 µas astrometric; D1 agrees
with the Newtonian brachistochrone at low speed and proper < coordinate time near c).
**Success:** the eight return the signals above with declared units, sanity-checked against the known cases;
order-of-magnitude outputs labelled; all documented contract-by-reference.

## Phase T1c — census filters (STUB)

**Scope:** `solar-analogs` (Hypatia-cache-primary ~14k + optional GCNS distance join; **emits a population /
size field** so a short list isn't read as a complete census); substellar L/T/Y (or `--teff-max`) filter
(**emits a `completeness_note` JSON field** — GCNS substellar incompleteness beyond ~10–25 pc). The E1
white-dwarf filter ships in **T1a** (item 5).
**Backing:** `solar-analogs` reads `hypatia_cache` (teff/logg/fe_h) — **not** `gcns_stars` (no teff/logg) —
with an optional GCNS distance join; default solar-twin box (Teff 5772±100, logg 4.44±0.1, [Fe/H] 0±0.1),
looser flags for analog.
**Validation:** self-validating; empty `hypatia_cache` → curated error (mirrors `search-hypatia`).
**Tests:** offline subprocess contracts over a seeded throwaway cache; assert the caveat/population fields
are present in the JSON.
**Success:** both filters work; results carry their completeness/population caveats **in the JSON output**
(not only docs); documented contract-by-reference.

---

# Phase T2 — Dust / ISM query path (STUB — new OPTIONAL dependency, forked)

Full request: `dust-map-query-request.md` (§§4–14). Gate T2 on the unit/seam contract proven in Part A.

**Part A (read-only):** `dust-sightline`, `dust-between` (reuses GCNS/SIMBAD resolvers + Sol origin),
CLI **option 59** `dust-fetch` + `--check` (import-utility, GCNS opt-58 lineage — not a `query.py`
subcommand). **Part B (Core planners only):** `--weight distance|dust` on `jump-route` (flagship) /
`optimal-tour` / `multi-stop` / `nearest-neighbor` / `trade-route`, each with per-leg + cumulative A_V **and a
distance-optimal comparison** (`extra_ly`/`saved_av`). `distance` stays default. **Deferred:** `blend`
weight, `--max-leg-av`, `jump-network` cost-budget, `farthest-first`.

**Maps/output (locked):** Leike 2020 + Edenhofer 2024, `--map near-field|edenhofer|auto`. Output **A_V mag,
R_V=3.1** + native echo (`native_quantity`) + `units`. Auto seam: Leike 0–69 pc, Edenhofer **inner-subtracted**
beyond (no double-count), `seam` flag on crossing bins. Out-of-coverage → per-bin `null` + non-fatal
`out_of_coverage` note (no clamp); deep cavity → small value + wide σ + `low_dust_high_uncertainty` note.
Explicit `--map near-field|edenhofer` loads only that map.

**Architecture (risk control — locked):** **forked, not parameterized in place.** New `core/dust.py` (Part A)
+ `core/dust_routing.py` (Part B): **reuse** the existing non-weight route helpers (`_resolve_star_position`,
`_load_star_systems_positions`, `_SpatialGrid`, `_merge_endpoint`, `_map_node`); **extract a shared
cost-injected `_dijkstra` seam** for `jump-route` (guarded byte-identical by the existing route tests);
**fork** the other planners. New `dust-*` subcommands. This keeps `dustmaps`/`healpy` **out of
`core/calculators.py`** so the stellar layer stays importable everywhere.

**Dependency/runtime (locked):** `dustmaps`(+healpy) in an **optional extra** (`requirements-dust.txt` /
`extras_require['dust']`), never base `requirements.txt`. **Runs in the WSL/Linux venv** (manylinux healpy
wheels install cleanly; native-Windows pip has no healpy wheel — conda-forge has a win-64 build but that is
outside the pip venv; the maintainer develops on Windows + WSL2, so the WSL venv is the canonical home and
matches the consumer's invocation path). Dust cache on the **native WSL filesystem** (not `/mnt/c`),
gitignored, fetch-once/offline (GCNS `space_app.db` model).

**Validation:** self-validating where the request specifies; bad coords/args → exit 2; genuinely-invalid
inputs → exit 1; geometry leaving a box is **not** an error (null + note). **Tests:** new
`tests/test_dust_routing.py` + `tests/test_dust_query.py`, **gated on `dustmaps` importability** (mirrors the
`*_live.py` network gate) so a native-Windows pip checkout skips them; the existing route-planner tests must
stay green (the `_dijkstra` extraction is byte-identical). **Success:** Part A returns per-bin + cumulative
A_V with uncertainty across the 69-pc seam for both maps, star endpoints resolve, fetch/cache offline-after;
Part B `jump-route --weight dust` returns the least-extinction path over the same reachable graph with the
distance-optimal comparison, `--weight distance` unchanged, `--max-jump` still governs reachability; all
documented contract-by-reference with extinction units declared.

---

## Locked decisions (provenance — full threads in the two request files)

| Item | Decision |
|---|---|
| T1a-1 `trojan-stability` | Wrap R2 `gascheau_coorbital_stable` with its `--host/--companion/--star` signature (R2 form wins) |
| T1a-3 `circumbinary-hz` eff-Teff | Luminosity/flux-weighted `(L1·T1+L2·T2)/(L1+L2)`; flag `out_of_range_teff` (don't clamp); `--star` mode → T1b |
| T1a-4 B3 exomoon | Fold into `hill-sphere` as defaulted extra keys (not a new subcommand) |
| T1a-5 E1 white dwarf | Extend `compute_gcns_within_sol` / `gcns-within-sol` (no GCNS search exists to attach to) |
| T1c E2/E3 caveats | Population/completeness notes go **in the JSON**, not only docs |
| T2 `blend` weight | **Dropped from v1** — distance-optimal comparison delivers the payoff; no silent normalization |
| T2 dust-fetch | CLI **option 59** + `--check` (import-utility), not a `query.py` subcommand |
| T2 dependency/runtime | Optional extra, WSL/Linux-venv-primary, test-gated; no native-Windows GUI / no `wsl.exe` bridge |
| T2 architecture | Forked (`core/dust.py` + `core/dust_routing.py`); reuse non-weight helpers; extract `_dijkstra` seam; fork the rest |

## Suggested build order

T1a (5 items, sequenced 1→5) → T1b (new pure-math) → T1c (census filters) → T2 Part A (Leike → Edenhofer/seam)
→ T2 Part B (forked Core planners). T1 and T2 are independent; T1a is the lowest-risk starting point.
