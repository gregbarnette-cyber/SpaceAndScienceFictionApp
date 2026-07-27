# Phase T — `query.py` Research-Tooling Extensions — Build Plan

> **Status: Planned (2026-06-22).** Requested by the sibling worldbuilding repo
> `scifiWorldBuilding-Claude` as two companion request specs (each carrying a full Q&A +
> implementer-decisions thread, all resolved 2026-06-22):
> - `…/scifiWorldBuilding-Claude/research/query-api-methods/calculator-extensions-request.md`
> - `…/scifiWorldBuilding-Claude/research/query-api-methods/dust-map-query-request.md`
>
> Overview + priority live in `future_phases.md` (Phase T section). This file is the build-ready spec.
> **T1a (built 2026-06-23), T1b, and T1c are fully detailed below; T2 is stubbed** (built out before its
> build). T1b's three pinned coefficients were verified against the cited papers 2026-06-23 (see the T1b
> coefficient table). T1c is two convenience census presets whose defining requirement is the **in-JSON**
> population/completeness caveat fields (locked answers #3/#4).
>
> **T2 detailed 2026-06-23** — the dust/ISM track is now a build-ready spec (was a stub). Its dependency,
> map-API, units, seam, and cache seams were **verified against the `dustmaps` 1.0.14 wheel + the WSL venv**
> before writing (see "T2.0 — Verified seam facts"), surfacing two corrections to the stub: the map key is
> `edenhofer2023` (not `edenhofer2024`), and the seam is handled by differential-density per-segment integration
> (not dustmaps' `integrated=True` add-back). The only open build-time item is the per-map native→A_V scalar
> (the T2 analog of T1b's coefficient pin), specified with sources. **Not yet built.**

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

## Phase T1b — new pure-math (DETAILED)

8 new self-validating `query.py` calculators in four groups (A detectability ×4, B1 tidal-heating,
C2 kozai-lidov, D1 relativistic-brachistochrone) **+** the deferred `circumbinary-hz --star1 --star2`
SIMBAD-resolve mode. Unlike T1a (reuse wrappers), this is **new physics** — three coefficients are
**verified against the cited papers below before coding** (done 2026-06-23, see the pinned table).

### Coefficients verified against the papers (pinned 2026-06-23)

| Item | Constant / convention | Source verified | Note |
|---|---|---|---|
| B1 `tidal-heating` | leading **`21/2`**; `Ė = (21/2)·(G·k₂·M_p²·R_s⁵·n·e²)/(Q·a⁶)` | Peale & Cassen 1978 form, as compiled in Henning et al. 2009 / **Heller & Barnes 2013** (arXiv:1209.5323) | `n=√(GM_p/a³)`; order-of-mag |
| C2 `kozai-lidov` | leading **`8/15π`** (≈0.16977); `(M₁+M₂+M₃)/M₃` mass factor in denominator | **Antognini 2015** (MNRAS 452, 3610; arXiv:1504.05957), Eq. 42 (`8/15π·(1+m₁/m₃)·P²_out/P_in·(1−e²_out)^{3/2}`); general mass factor = Kiseleva 1998 | order-of-mag (paper: exact period within "a factor of a few") |
| A4 `direct-imaging` IWA | **`IWA = λ/D`** rad → arcsec (the 1·λ/D convention) | request-locked; real coronagraphs use a 1–4 λ/D multiple | document the multiple caveat |

> **Anchors re-derived from the formulas below (all pass):** RV Earth→Sun ≈ **0.0895 m/s**; transit
> depth Earth→Sun = (R⊕/R☉)² ≈ **83.8 ppm**; astrometric Jupiter→Sun @10 pc ≈ **496 µas**; reflected
> contrast Earth→Sun (A_g=0.3) ≈ **5.4e-10**.

### Reuse surface (verified — no re-derivation)

| Existing | Use |
|---|---|
| `calculators._C_MS` (299792458), `HOURS_PER_JULIAN_YEAR` | D1 relativistic kinematics (ly_m = c × 31 557 600 s/yr) |
| `equations._G, _K_B, _EARTH_MASS_KG, _SOLAR_MASS_KG, _M_PER_AU, _KM_PER_AU, _SEC_PER_YEAR` | B1/A/C2 unit work |
| `equations.compute_circumbinary_hz` (T1a) | **unchanged**; the `--star1/--star2` mode is a `query.py`-layer resolver |
| `databases.compute_simbad_lookup` → `regions.compute_star_system_regions_from_simbad` (`temp`, `bcLuminosity`) | the per-star **(teff, lum) derive helper** for `circumbinary-hz --star1/--star2` |

Constant to add: `_M_JUP_EARTH = 317.828` (M_Jup in Earth masses) and `_M_SUN_EARTH = 332946.0` (or reuse
existing solar/earth mass kg constants and divide). `_LY_M = _C_MS × _SEC_PER_YEAR` for D1.

---

### A — Planet detectability (4 new pure-compute subcommands)

#### A1 · `rv-semi-amplitude`
- **Core (new):** `calculators.compute_rv_semi_amplitude(planet_mass_earth, star_mass_solar, period_days=None, sma_au=None, ecc=0, inclination_deg=90)`.
  - Lovis & Fischer 2010: `K = 28.4329 · (1/√(1−e²)) · (Mp·sin i / M_Jup) · ((M*+Mp)/M_sun)^(−2/3) · (P/1yr)^(−1/3)` m/s.
  - **Input `--planet-mass-earth` → M_Jup internally** (`/317.828`); `Mp` in solar = `planet_mass_earth/332946`.
  - Either `--period-days` **or** `--sma-au` (derive `P_yr = √(a_au³/(M*+Mp)_solar)` via Kepler III; conversely `a_au = ((M*+Mp)·P_yr²)^{1/3}`). `--ecc` default 0, `--inclination-deg` default 90.
- **Output:** `{k_ms, period_days, sma_au, ecc, inclination_deg, planet_mass_earth, star_mass_solar}`.
- **Validation:** `planet_mass_earth>0`, `star_mass_solar>0`, `0≤e<1`; exactly one of period/sma (>0).
- **Anchor:** Earth→Sun (P=365.25 d, i=90, e=0) → `k_ms ≈ 0.0895`.

#### A2 · `transit-signal`
- **Core (new):** `calculators.compute_transit_signal(planet_radius_earth, star_radius_solar, sma_au=None, period_days=None, star_mass_solar=None)`.
  - Winn 2010: depth `δ=(Rp/R*)²`; geometric prob `p≈R*/a` (circular); duration `T≈(P/π)·arcsin(R*/a)`.
  - Units: `R* = star_radius_solar × 0.00465047 AU`; `Rp = planet_radius_earth × 4.25875e-5 AU`. When `--sma-au` absent, derive `a` from `--period-days` + `--star-mass-solar` via Kepler III; `P_days = 365.25·√(a³/M*)`.
- **Output:** `{depth_ppm, depth_frac, transit_prob, duration_hours, sma_au, period_days, planet_radius_earth, star_radius_solar}`.
- **Validation:** radii `>0`; either `--sma-au` (>0) or (`--period-days>0` **and** `--star-mass-solar>0`).
- **Anchor:** Earth→Sun → `depth_ppm ≈ 83.8`, `transit_prob ≈ 0.0047`, `duration_hours ≈ 13`.

#### A3 · `astrometric-signal`
- **Core (new):** `calculators.compute_astrometric_signal(planet_mass_earth, star_mass_solar, sma_au, distance_pc)`.
  - `α[arcsec] = (Mp/M*)·(a_AU/d_pc)`; `Mp/M* = (planet_mass_earth/332946)/star_mass_solar`. Report **µas** (`×1e6`) headline + arcsec echo.
- **Output:** `{signal_microarcsec, signal_arcsec, planet_mass_earth, star_mass_solar, sma_au, distance_pc}`.
- **Validation:** all four `>0`.
- **Anchor:** Jupiter (317.8 M⊕) → Sun, a=5.2, d=10 → `signal_microarcsec ≈ 496`.

#### A4 · `direct-imaging`
- **Core (new):** `calculators.compute_direct_imaging(sma_au, distance_pc, planet_radius_earth, albedo=0.3, telescope_diameter_m=None, wavelength_um=None)`.
  - Sep `θ_arcsec = a_AU/d_pc`; reflected contrast `C = A_g·(Rp/a)²` with **Rp→AU** (`planet_radius_earth × 4.25875e-5`); optional `IWA = (λ/D) rad × 206264.806 arcsec` when **both** telescope args given; `resolvable = θ ≥ IWA` (else both `null`).
- **Output:** `{angular_sep_arcsec, contrast_reflected, iwa_arcsec, resolvable, sma_au, distance_pc, planet_radius_earth, albedo}`.
- **Validation:** `sma_au>0`, `distance_pc>0`, `planet_radius_earth>0`, `albedo>0`; if either telescope arg given, **both** required and `>0` (else argparse exit 2). Note the 1·λ/D convention + 1–4 λ/D real-coronagraph caveat in docs.
- **Anchor:** Earth→Sun, A_g=0.3 → `contrast_reflected ≈ 5.4e-10`; a=1, d=10 → `angular_sep_arcsec = 0.1`.

### B1 · `tidal-heating`
- **Core (new):** `equations.compute_tidal_heating(primary_mass_earth, satellite_radius_km, sma_km, ecc, k2=0.3, tidal_q=100)`.
  - **`Ė = (21/2)·(G·k₂·M_p²·R_s⁵·n·e²)/(Q·a⁶)`** (verified — Peale & Cassen 1978 / Heller & Barnes 2013); `n = √(G·M_p/a³)` rad/s; `surface_flux = Ė/(4π R_s²)` W/m²; `io_flux_ratio = surface_flux / 2.0` (Io ≈ 2 W/m²).
  - Units: `M_p = primary_mass_earth × _EARTH_MASS_KG`, `R_s = satellite_radius_km×1000`, `a = sma_km×1000`.
- **Output (order-of-magnitude — label):** `{heating_power_w, surface_flux_wm2, mean_motion_rad_s, io_flux_ratio, primary_mass_earth, satellite_radius_km, sma_km, ecc, k2, tidal_q}`.
- **Validation:** `primary_mass_earth>0`, `satellite_radius_km>0`, `sma_km>0`, `0≤e<1`, `k2>0`, `tidal_q>0`.
- **Anchor:** Io-like (M_p=317.8 M⊕, R_s=1821 km, a=421 700 km, e=0.0041, k2=0.3, Q=100) → flux within ~1 order of Io's ~2 W/m² → `io_flux_ratio` O(1); `mean_motion_rad_s ≈ 4.1e-5`.

### C2 · `kozai-lidov`
- **Core (new):** `equations.compute_kozai_lidov(m1_solar, m2_solar, m3_solar, period_inner_yr=None, period_outer_yr=None, sma_inner_au=None, sma_outer_au=None, ecc_outer=0)`.
  - **`T_KL = (8/15π)·((M₁+M₂+M₃)/M₃)·(P_out²/P_in)·(1−e_out²)^{3/2}`** years (verified — Antognini 2015 / Kiseleva 1998). When SMAs given instead of periods: `P_in_yr = √(a_in³/(m1+m2))`, `P_out_yr = √(a_out³/(m1+m2+m3))`.
- **Output (order-of-magnitude — label):** `{timescale_years, m1_solar, m2_solar, m3_solar, period_inner_yr, period_outer_yr, ecc_outer}`.
- **Validation:** masses `>0`, `0≤e_out<1`; require either (`--period-inner-yr` **and** `--period-outer-yr`) or (`--sma-inner-au` **and** `--sma-outer-au`), each `>0`.
- **Anchor:** m1=1, m2=1, m3=1 M☉, P_in=1 yr, P_out=100 yr, e_out=0 → `T_KL = (8/15π)·3·(100²/1) ≈ 5093 yr`.

### D1 · `relativistic-brachistochrone`
- **Core (new):** `calculators.compute_relativistic_brachistochrone(accel_g, distance_ly)`.
  - Constant **proper** acceleration, flip at half-distance. Let `a = accel_g·9.80665` m/s², `D = distance_ly·_LY_M`, half `D/2`. `X = arccosh(1 + a·(D/2)/c²)`; per-half proper `τ_h=(c/a)·X`, coordinate `t_h=(c/a)·sinh X`; midpoint `peak_velocity_c = tanh X`, `peak_lorentz_factor = cosh X = 1 + a·(D/2)/c²`. Total = 2× each half.
  - `coord_time_yr = 2·t_h/_SEC_PER_YEAR`; `proper_time_yr = 2·τ_h/_SEC_PER_YEAR`. Lifts the 3%c Newtonian cap of the existing brachistochrone subcommands.
- **Output:** `{accel_g, distance_ly, coord_time_yr, proper_time_yr, peak_velocity_c, peak_lorentz_factor}`.
- **Validation:** `accel_g>0`, `distance_ly>0`.
- **Anchor:** 1 g over 4.37 ly (α Cen) → `coord_time_yr ≈ 5.9`, `proper_time_yr ≈ 3.5`, `peak_velocity_c ≈ 0.95`; **low-speed limit** (tiny distance) → `coord_time ≈ proper_time ≈ 2√(D/a)` (the Newtonian flip-burn); near c, proper < coordinate.

### Deferred-from-T1a · `circumbinary-hz --star1 --star2`
- **No core change.** A `query.py`-layer resolver `_resolve_star_teff_lum(name) → (teff, lum)` runs
  `compute_simbad_lookup` → `compute_star_system_regions_from_simbad`, reading `temp` + `bcLuminosity`;
  feeds the existing `equations.compute_circumbinary_hz(teff1, lum1, teff2, lum2)`. `--teff1…--lum2` and
  `--star1/--star2` are mutually-exclusive input modes (numeric stays offline; `--star` adds SIMBAD network).
- A SIMBAD failure on either endpoint → that error returned immediately (the `_simbad_then` pattern).

### T1b — consolidated deliverables

- **Code:** `core/calculators.py` (+`compute_rv_semi_amplitude`, `compute_transit_signal`,
  `compute_astrometric_signal`, `compute_direct_imaging`, `compute_relativistic_brachistochrone`,
  + `_M_JUP_EARTH`/`_LY_M` constants); `core/equations.py` (+`compute_tidal_heating`,
  `compute_kozai_lidov`); `query.py` (+8 subcommands, + the `circumbinary-hz --star1/--star2` resolver
  branch on the existing subparser). **No new modules.**
- **Docs:** `docs/integration.md` — 8 quick-ref rows + per-subcommand sections (units per field, the
  three pinned constants + sources stated, order-of-mag flags on B1/C2, the IWA caveat); the
  `circumbinary-hz` row gains the `--star1/--star2` mode. `docs/equations.md` — `compute_tidal_heating`,
  `compute_kozai_lidov` (with the pinned constants); `docs/calculators.md` — the 4 detectability calcs +
  `relativistic-brachistochrone`. Mark T1b built in `future_phases.md`.

### T1b — test plan (extend `tests/test_query_phase_t.py`)

- **A1–A4:** happy-path key sets; the four anchors above (RV 0.0895 m/s, transit 83.8 ppm, astrometric
  496 µas, contrast 5.4e-10); period↔SMA derivation parity (give P, then the derived `a`, expect equal K);
  A4 `iwa_arcsec`/`resolvable` null when telescope args absent, populated + boolean when present; core-parity;
  exit 1 (e∉[0,1), non-positive); exit 2 (missing arg / both-or-neither period/sma).
- **B1:** `io_flux_ratio` O(1) for the Io anchor; `surface_flux = Ė/(4πR²)` internal consistency;
  order-of-mag note present; e∉[0,1)/k2≤0/Q≤0 → exit 1.
- **C2:** the 5093 yr anchor; SMA-vs-period parity; e_out∉[0,1) → exit 1; both-or-neither input group → exit 2.
- **D1:** the α-Cen anchor (proper < coord); low-speed agreement with `compute_travel_time_system_*`'s
  Newtonian flip-burn (Profile 1, `t=2√(D/a)`) within tolerance; `peak_velocity_c < 1` always; accel/dist ≤0 → exit 1.
- **circumbinary `--star` mode:** mocked `compute_simbad_lookup` + `compute_star_system_regions_from_simbad`
  → parity with the numeric mode; SIMBAD error passthrough; numeric/`--star` mutual-exclusion → exit 2.

### T1b — validation contract (per subcommand, all self-validating Phase-H/P)

| Subcommand | exit 1 (`{error}`) | exit 2 (argparse) |
|---|---|---|
| `rv-semi-amplitude` | mass ≤0, e∉[0,1) | missing/non-numeric; both/neither period+sma |
| `transit-signal` | radius ≤0 | missing/non-numeric; neither sma nor (period+star-mass) |
| `astrometric-signal` | any input ≤0 | missing/non-numeric |
| `direct-imaging` | sma/dist/radius ≤0, albedo ≤0 | missing/non-numeric; only one telescope arg given |
| `tidal-heating` | mass/radius/sma ≤0, e∉[0,1), k2≤0, Q≤0 | missing/non-numeric |
| `kozai-lidov` | mass ≤0, e_out∉[0,1) | missing/non-numeric; both/neither period+sma group |
| `relativistic-brachistochrone` | accel-g ≤0, distance-ly ≤0 | missing/non-numeric |
| `circumbinary-hz --star1/--star2` | SIMBAD/regions failure | both numeric+`--star` modes given |

### T1b — success criteria / acceptance (done when)

- The 8 calculators return the signals with declared units, matching the verified anchors; B1/C2 outputs
  labelled order-of-magnitude; D1 agrees with the Newtonian brachistochrone at low speed and gives proper
  < coordinate time near c; `circumbinary-hz --star1/--star2` resolves real stars to the same zones the
  numeric mode produces.
- The three pinned constants (21/2, 8/15π, λ/D) and their sources are recorded in `docs/integration.md`.
- Each honors the validation matrix above (curated exit 1 / argparse exit 2).
- Full suite green; documented contract-by-reference; T1b marked built in `future_phases.md`.

## Phase T1c — census filters (DETAILED)

2 new local-DB census subcommands — `solar-analogs` (E2) and `substellar` (E3). Both are **convenience
presets over existing census tables** (no new datasets, no network), self-validating (Phase-H/P), and — the
defining T1c requirement (locked answers #3/#4) — **each carries its population/completeness caveat as a
JSON field**, not only in the docs, because the external consumer reads JSON at query time. The E1
white-dwarf filter already shipped in **T1a** (item 5: `gcns-within-sol --wd-prob-min/max`).

### Verified backing surface (no re-derivation)

| Table (file) | Columns used | Reuse |
|---|---|---|
| `hypatia_cache` (`core/db.py:288`) | `teff, logg, fe_h, distance_pc, light_years` (+ `vmag, bv, disk`, abundance pivots) | `_range_clause`, `_SEARCH_CAP` (500), the `search_hypatia_cache` query idiom (`core/databases.py:2996`) |
| `gcns_stars` (`core/db.py`) | `spectral_type` (SIMBAD cross-match — partial), `light_years`, `_GCNS_ROW_COLS`, `_gcns_row_to_dict` | the `compute_gcns_within_sol` reader idiom + empty-table error |
| `star_systems.designations` | Gaia EDR3/DR3 id | `_GCNS_GAIA_ID_RE` (`core/databases.py:2510`) for the optional `solar-analogs --gcns-distance` join |

### Implementer's-call decisions (recorded — like T1a-5)

- **`solar-analogs` backs on `hypatia_cache`, not `gcns_stars`** — Teff/logg/[Fe/H] live only in the Hypatia
  cache (locked answer #3). The population field discloses the ~14k-star Hypatia limit.
- **The GCNS Bayesian-distance join is opt-in + best-effort** (`--gcns-distance`). The default uses the
  cache's own `light_years` (Hypatia distance); the join is a 3-hop cross-match
  (`hypatia_cache.star_name → star_systems.designations → Gaia id → gcns_stars.gaia_source_id`) that is
  **lossy** (NULL where any hop breaks). It is decoupled from the twin/analog core so it can be deferred at
  build without blocking E2 — if deferred, drop the flag and the `dist_pc_gcns` key, keep everything else.
- **`substellar` backs on `gcns_stars` by `spectral_type` prefix** (the census the completeness caveat is
  about). `--teff-max` (request alt) is **not offered** — `gcns_stars` has no `teff`. A BP–RP colour route
  (`phot_bp/rp_mean_mag`, which would catch un-typed red sources) is an explicitly-considered **deferred**
  enhancement; v1 ships the literal "spectral-class L/T/Y filter". The `completeness_note` + `population`
  fields make the spectral-type-cross-match undercount explicit (honest lower bound).

---

### T1c-1 · `solar-analogs` (E2) — solar twin/analog box over `hypatia_cache`

- **Core (new):** `databases.compute_solar_analogs(mode="twin", teff_tol=None, logg_tol=None, feh_tol=None, ly_max=None, gcns_distance=False)`.
  - Solar reference centres (module constants): `_SUN_TEFF = 5772.0` (IAU nominal), `_SUN_LOGG = 4.44`, `_SUN_FEH = 0.0`.
  - **Presets:** `mode="twin"` → tol `Teff ±100, logg ±0.1, [Fe/H] ±0.1`; `mode="analog"` → `Teff ±500, logg ±0.4, [Fe/H] ±0.3`. Any explicit `*_tol` overrides that axis (per-axis); `ly_max` filters `light_years`.
  - Box query over `hypatia_cache` reusing `_range_clause` (`teff` in `[centre−tol, centre+tol]`, same for `logg`/`fe_h`; a NULL value on a filtered axis is excluded), `_SEARCH_CAP`, sorted `fe_h DESC` NULL-last. Rows carry the same columns as `search_hypatia_cache` (incl. `mg_h/si_h/o_h` pivots).
  - **`gcns_distance=True`:** best-effort attach `dist_pc_gcns` per row via `_GCNS_GAIA_ID_RE` over the matched `star_systems` row (NULL when unresolved); `population.gcns_distance_matched` reports the join coverage.
- **Output:** `{mode, criteria:{teff_center, teff_tol, logg_center, logg_tol, feh_center, feh_tol, ly_max}, population:{source:"hypatia_cache", total_in_cache:int, returned:int, gcns_distance_matched:int|null, note:str}, count, capped, cap, stars:[…]}`. The **`population.note`** is the locked caveat, e.g. *"Solar analogs are drawn from the ~14k Hypatia-cached stars (those with measured abundances); this is not a complete solar-neighbourhood census."*
- **Validation (self-validating):** empty `hypatia_cache` → `{"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}` (exit 1, mirrors `search-hypatia`); any explicit `*_tol ≤ 0` or `ly_max ≤ 0` → curated `{"error"}` exit 1. Bad `--mode` (argparse `choices`) / non-numeric tol → exit 2.
- **`query.py`:** `solar-analogs` — `--mode {twin,analog}` (default twin), `--teff-tol`, `--logg-tol`, `--feh-tol`, `--ly-max` (all optional floats), `--gcns-distance` (store-true).

### T1c-2 · `substellar` (E3) — L/T/Y census over `gcns_stars`

- **Core (new):** `databases.compute_substellar_census(ly_max=None, include_late_m=False, classes=None)`.
  - Selection: `spectral_type` begins with one of the substellar classes — default `("L", "T", "Y")`; `include_late_m=True` adds `M7/M8/M9` (the M/L boundary); `classes` overrides the set. Parameterized `spectral_type LIKE 'L%'` OR-group (leading-letter, like `spectral_where`), `spectral_type IS NOT NULL` (only cross-matched rows carry a type). `ly_max` filters `light_years`. Cap `_SEARCH_CAP`, sort `light_years ASC`. Rows = `_gcns_row_to_dict` shape.
- **Output:** `{classes, ly_max, count, capped, cap, completeness_note, population:{total_in_gcns:int, with_spectral_type:int, returned:int}, snapshot_date, gcns_version, stars:[…]}`. The **`completeness_note`** is the locked caveat, e.g. *"GCNS (Gaia-only) substellar completeness falls off beyond ~10–25 pc; L/T/Y dwarfs are too faint for Gaia farther out, and only SIMBAD-cross-matched rows carry a spectral type — this list is a lower bound."*
- **Validation (self-validating):** empty `gcns_stars` → `{"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}` (exit 1); `ly_max ≤ 0` → curated `{"error"}` exit 1. Non-numeric `--ly-max` → exit 2.
- **`query.py`:** `substellar` — `--ly-max` (optional float), `--include-late-m` (store-true), `--classes` (optional `nargs="+"`, default `L T Y`).

### T1c — consolidated deliverables

- **Code:** `core/databases.py` (+`compute_solar_analogs`, `compute_substellar_census`, + the `_SUN_*`
  constants; reuse `_range_clause`/`_SEARCH_CAP`/`_GCNS_ROW_COLS`/`_gcns_row_to_dict`/`_GCNS_GAIA_ID_RE`);
  `query.py` (+2 subcommands `solar-analogs` / `substellar`). **No new modules; no GUI; no new datasets.**
- **Docs:** `docs/integration.md` — 2 quick-ref rows + per-subcommand sections, documenting the **in-JSON**
  `population` / `completeness_note` caveat fields and the self-validating contract. Mark T1c built in
  `future_phases.md`. (`docs/star-databases.md` gets a one-line pointer under the Hypatia/GCNS sections.)

### T1c — test plan (extend `tests/test_query_phase_t.py`)

Offline subprocess contracts over **seeded throwaway DBs** (the `GcnsWdProbFilterTest` pattern: set
`db._DB_PATH`, `_auto_seed = noop`, seed the table, point `SPACE_APP_DB` at the file).

- **`solar-analogs`** (seed `hypatia_cache`): a Sun-like row (5772/4.44/0.0, inside the twin box), a mild
  off row (5650/4.50/−0.2, inside analog but outside twin), and a giant (4800/2.5/0.1, outside both).
  - twin mode → only the Sun-like row; `analog` → Sun-like + the off row; `criteria` echoes the preset
    tolerances; a `--teff-tol` override widens/narrows the Teff axis only.
  - **`population.source == "hypatia_cache"`, `total_in_cache == 3`, `note` present** (the locked caveat).
  - `--ly-max` filters on `light_years`; empty cache → exit 1; `--teff-tol 0` → exit 1; bad `--mode` → exit 2.
  - `--gcns-distance` branch (also seed `star_systems` with a Gaia-id designation + `gcns_stars` with that
    `gaia_source_id`): `dist_pc_gcns` attached for the matched star, `None` for the unmatched, and
    `population.gcns_distance_matched` counts the hits. *(Skip/curtail this sub-test if the join is deferred.)*
- **`substellar`** (seed `gcns_stars`): an L dwarf (`L5`, 8 ly), a T dwarf (`T2`, 30 ly), an M5V (not
  substellar), an M8V (late-M), one beyond a tested `--ly-max`.
  - default `L T Y` → L+T only; `--include-late-m` adds the M8V; `--classes M` (override) behaviour;
    `--ly-max 20` drops the 30-ly T dwarf.
  - **`completeness_note` present in every result**, `population.with_spectral_type` counts typed rows;
    empty `gcns_stars` → exit 1; `--ly-max -1` → exit 1; non-numeric `--ly-max` → exit 2.

### T1c — validation contract (per subcommand, self-validating Phase-H/P)

| Subcommand | exit 1 (`{error}`) | exit 2 (argparse) |
|---|---|---|
| `solar-analogs` | empty `hypatia_cache`; any `*_tol ≤ 0`; `ly_max ≤ 0` | bad `--mode` (choices); non-numeric tol/`--ly-max` |
| `substellar` | empty `gcns_stars`; `ly_max ≤ 0` | non-numeric `--ly-max` |

### T1c — success criteria / acceptance (done when)

- `solar-analogs` returns Hypatia-cached solar twins (tight box) / analogs (loose box) with the
  **`population` block (source + size + caveat note) in the JSON**; twin⊂analog; per-axis tol overrides work;
  the optional `--gcns-distance` join attaches a Bayesian distance where the cross-match resolves (or is
  cleanly deferred).
- `substellar` returns `L/T/Y` (+ optional late-M) `gcns_stars` within range, **every result set carrying
  `completeness_note` in the JSON** (the locked lower-bound disclosure) plus a `population` block.
- Both self-validating (curated exit 1 / argparse exit 2); an empty backing table → the curated
  run-the-importer error.
- Full suite green; both documented contract-by-reference in `docs/integration.md`; T1c marked built in
  `future_phases.md`.

---

# Phase T2 — Dust / ISM query path (DETAILED — new OPTIONAL dependency, forked)

Full request: `dust-map-query-request.md` (§§4–14; answers §13, implementer calls §14). Gate Part B on the
unit/seam contract proven in Part A. T2 is the only remaining Phase-T track (T1a/T1b/T1c built 2026-06-23).

## T2.0 — Verified seam facts (pinned 2026-06-23 against the dustmaps 1.0.14 wheel + WSL venv)

These were proven before writing the spec (the T2 analog of the T1b coefficient verification). The wheel
source (`dustmaps/leike2020.py`, `dustmaps/edenhofer2023.py`, `config.py`, `std_paths.py`) is authoritative;
two facts **correct the earlier stub**.

| Seam | Verified fact | Source |
|---|---|---|
| **Dependency installs** | `dustmaps==1.0.14` (`py3-none-any`) + `healpy 1.19.0` resolve a **`cp312-manylinux2014_x86_64`** wheel in the WSL venv (Python 3.12.3) — `pip download` pulls them with no build step. | `pip download dustmaps healpy --no-deps` (run 2026-06-23) |
| **New deps (full set)** | dustmaps `Requires-Dist`: astropy, h5py, healpy, numpy, progressbar2, requests, scipy, six, tqdm. **Already in base `requirements.txt`:** astropy, numpy, requests. **New for `requirements-dust.txt`:** `dustmaps, healpy, h5py, scipy, progressbar2, six, tqdm`. | wheel `METADATA` |
| **Map key — Leike** | `dustmaps.leike2020.Leike2020Query` (key `leike2020`); `leike2020.fetch(fetch_samples=False)` → `mean_std.h5` (Zenodo 3993082; samples=14 GB, skip). | `leike2020.py` |
| **Map key — Edenhofer (CORRECTION)** | The map is **`edenhofer2023` / `dustmaps.edenhofer2023.Edenhofer2023Query`**, **not** `edenhofer2024`. (A&A paper is 2024; arXiv 2308.01295 / dustmaps module are 2023.) `edenhofer2023.fetch()` → `mean_and_std_healpix.fits` (**≈3.2 GB**; Zenodo 8187943; samples=19 GB, skip). Use the `main` flavor (69 pc → 1.25 kpc). | `edenhofer2023.py` |
| **Leike native quantity** | `query(coords, component='mean'|'std')` → extinction **density**, **`e-foldings / kpc` in the Gaia G band** (differential, not integrated). Cartesian box, lower edge `(−370,−370,−270)` pc, **1-pc voxels**; **out-of-box → NaN**. | `Leike2020Query.query` docstring + `_coords2idx` |
| **Edenhofer native quantity** | `Edenhofer2023Query(load_samples=False, integrated=False, flavor='main').query(coords, mode='mean'|'std')` → density in **`E` of Zhang, Green & Rix (2023) per parsec** (differential). HEALPix sphere; radii **~69 pc → 1.25 kpc**; outside the shell → **NaN**. `mode='std'` works **without** the samples file. | `Edenhofer2023Query.__init__`/`.query` |
| **Inner-<69 pc add-back (CORRECTION to seam handling)** | The add-back happens **only in `integrated=True`** (`data[...,0,:] += data0`, then `cumsum`). **We query differential density (`integrated=False`) and integrate per-segment ourselves**, which (a) never triggers the add-back → no double-count, and (b) Edenhofer differential is NaN inside ~69 pc, so Leike owns 0–69 and Edenhofer owns >69 with zero overlap. This is the clean realization of locked decision Q2. | `Edenhofer2023Query.__init__` (the `if integrated is True:` branch) |
| **Cache location is settable** | `dustmaps.config['data_dir']` (in-process) or `DUSTMAPS_CONFIG_FNAME`→`~/.dustmapsrc` overrides the data dir. `core/dust.py` sets it to a repo-local `data/dust/` on the **native WSL FS** before any fetch/query. | `config.py`, `std_paths.data_dir()` |

### The one genuine build-time pin — native → A_V scalars (R_V=3.1)

Neither map is A_V; locked decision Q1 standardizes output to **A_V (mag), R_V=3.1**, with a `native_quantity`
echo per bin + a top-level `units`. The differential-density × path integration is settled (below); **the two
per-map scalar conversions to A_V are the T2 coefficient pin — confirm each against its cited extinction curve
at build, exactly as T1b pinned 21/2 and 8/15π before coding.** Specify in `core/dust.py` as named module
constants with the source in a comment:

- **Edenhofer (ZGR23 `E`) → A_V:** `A_V = _AV_PER_ZGR23_E × E`. The ZGR23 extinction curve (the `R(λ)` table at
  https://doi.org/10.5281/zenodo.6674521, also referenced in the `Edenhofer2023Query` docstring) gives `A(V)/E`
  at 550 nm for R_V=3.1. Pin `_AV_PER_ZGR23_E` from that table at build (do **not** hard-code a remembered
  value).
- **Leike (Gaia-G `e-foldings`) → A_V:** integrating density (e-foldings/kpc) over path (kpc) yields the **Gaia-G
  optical depth τ_G in e-foldings (natural log)**. `A_G = (2.5/ln 10)·τ_G = 1.0857·τ_G`; then
  `A_V = A_G / (A_G/A_V)` using the Gaia-G/V extinction ratio at R_V=3.1 from a cited law (Wang & Chen 2019, or
  the Gaia DR2/EDR3 G-band extinction coefficients). Pin `_AV_G_BAND_RATIO` at build.

Echo per bin: `a_v` (mag, R_V=3.1) + `native_value` + `native_quantity`
(`"leike2020_density_efoldings_per_kpc_gaiaG"` / `"edenhofer2023_ZGR23_E_per_pc"`); top-level `units:"A_V_mag_RV3.1"`.

### Integration & uncertainty model (settled — no build pin needed)

- **Per-bin differential → column:** sample each map's *density* at the bin center (Leike Cartesian / Edenhofer
  HEALPix-interp, both built into `query`), multiply by the bin's physical length, convert to A_V via the scalar
  above. Local legs are a few pc over 1–2 pc resolution → a handful of samples per leg (request §B.6) — cheap.
- **Per-bin σ:** the `std` component/mode (free in both mean+std files) × bin length × scalar → `a_v_lo/_hi`.
- **Cumulative σ:** quadrature sum of per-bin σ (independent-bin approximation) — **document that it understates
  correlated uncertainty**; the exact path (integrate each of Edenhofer's posterior samples, 19 GB, then take
  the spread) is a **deferred** enhancement, noted in `docs/integration.md`. Leike ships no light-weight samples,
  so Leike cumulative σ is quadrature-only (mirrors the GCNS "no propagated interval" restraint).
- **Deep cavity:** covered-but-near-zero → return the small A_V with wide `*_lo/_hi` + a `low_dust_high_uncertainty`
  note (Q3 refinement b). **NaN from either map** (out-of-box / out-of-shell) → per-bin `a_v=null` + a non-fatal
  `out_of_coverage` note; **never clamp-to-edge** (Q3). All-bins-null is acceptable (top-level note) rather than
  a hard error.

---

## T2 Part A — read-only dust queries (`core/dust.py` + CLI option 59)

New module **`core/dust.py`** isolates all `dustmaps`/`healpy` imports (function-local / lazy), so the stellar
layer (`core/calculators.py` etc.) stays importable on a native-Windows checkout without the optional dep. A
top-of-module `_require_dustmaps()` raises a curated `{"error": "Dust maps require the optional 'dust' extra …"}`
when the import fails, so a dust subcommand on a non-dust checkout exits 1 cleanly (not a traceback).

### Shared dust engine (internal to `core/dust.py`)

- `_set_cache_dir()` — point `dustmaps.config['data_dir']` at repo-local `data/dust/` (native WSL FS), idempotent.
- `_load_map(map_key)` — lazy-construct + process-cache `Leike2020Query()` / `Edenhofer2023Query(integrated=False)`;
  raises curated `{"error": "map data not fetched — run option 59 (dust-fetch) first."}` on `FileNotFoundError`.
- `_integrate_sightline(l_deg, b_deg, dist_start_pc, dist_end_pc, n_steps, map_sel)` — the core engine shared by
  both subcommands: builds the per-bin distance grid, for each bin picks the owning map under `auto`
  (Leike ≤ ~69 pc, Edenhofer > ~69 pc; `seam` flag on bins straddling the handover), queries `mean`+`std`,
  converts to A_V, accumulates cumulative A_V + quadrature σ, attaches per-bin `out_of_coverage`/
  `low_dust_high_uncertainty`/`seam` notes. Returns the `bins[]` + `cumulative_*` + `units` block reused verbatim
  by `dust-sightline` and `dust-between`.

### T2A-1 · `dust-sightline` — extinction profile along one direction

- **Core (new):** `dust.compute_dust_sightline(l=None, b=None, ra=None, dec=None, star=None, id=None, dist_start_pc=0.0, dist_end_pc=..., n_steps=..., step_pc=None, map_sel="auto")`.
  - Direction input is **exactly one** of: Galactic `--l --b`, equatorial `--ra --dec`, or a `--star`/`--id`
    whose resolved position **sets the direction** (its galactic l/b; distance range still from `--dist-*`).
    `--star`/`--id` reuse `calculators._resolve_star_position` (DB→SIMBAD, `Sol`→origin) / `_resolve_gcns_row`.
  - `--steps` (count) **or** `--step-pc` (spacing) — mutually exclusive; default a sane `--steps` (e.g. 50).
- **Output:** `{map, frame, l, b, dist_start_pc, dist_end_pc, n_steps, bins:[{dist_pc, dist_ly, a_v, a_v_lo, a_v_hi, native_value, native_quantity, seam, notes}], cumulative_a_v, cumulative_a_v_lo, cumulative_a_v_hi, units, notes}`.
- **Validation (self-validating):** exactly one direction mode (else argparse-style exit 2); `dist_end>dist_start≥0`,
  `n_steps≥1` / `step_pc>0` (curated exit 1); `map_sel ∈ {near-field, edenhofer, auto}` (argparse `choices`,
  exit 2). A sightline leaving coverage is **not** an error (null bins + note).

### T2A-2 · `dust-between` — extinction along a star-to-star line

- **Core (new):** `dust.compute_dust_between(star1=None, id1=None, star2=None, id2=None, n_steps=..., step_pc=None, map_sel="auto")`.
  - Endpoints reuse the existing resolvers (`_resolve_star_position` for `--star…`; `_resolve_gcns_row` for
    `--id…`; `Sol`/`Sun` → origin) — the same dual name/id convention as `gcns-distance`. Direction + length come
    from the two resolved positions; then `_integrate_sightline` runs along that segment.
- **Output:** the `dust-sightline` block **plus** `{star1_info, star2_info, separation_pc, separation_ly}`. This
  is the direct per-corridor input for Packet 1.
- **Validation:** one endpoint mode per side (exit 2 on both/neither); a resolver error on either side returned
  immediately (exit 1); same direction-coverage rules as A-1.

### T2A-3 · CLI **option 59** `dust-fetch` (import utility — NOT a `query.py` subcommand)

- **CLI (new):** `main.py::dust_fetch_data()` registered as menu **option 59** in `MENU_OPTIONS` + added to
  `_UTILITY_KEYS` (lineage of opts 52–58; GCNS opt-58 is the direct precedent — the import-utility carve-out, not
  a feature-menu addition). **Update (2026-06-23):** a GUI surface for the *fetch utility only* was added —
  `FetchDustMapPanel` (Utilities nav, `ImportGcnsPanel`-style, gated on `dustmaps` importability). The dust
  *query* subcommands stay `query.py`-only per §14; only the download utility (like GCNS opt-58) is in the GUI.
- **Core (new):** `dust.compute_dust_fetch(map_sel="auto", check_only=False, progress_callback=None)` —
  `_set_cache_dir()` then call `leike2020.fetch()` / `edenhofer2023.fetch()` (both for `auto`); `--check` reports
  per-map cached/size/path without downloading. Wrap `_require_dustmaps()`; classify network failures with the
  shared `_network_error_msg`. Returns `{map, fetched:[{map, status, path, size_mb}], cache_dir}` or `{"error"}`.
- **Sizes/notes (verified via Zenodo HEAD):** Leike `mean_std.h5` ≈ **2.4 GB** + Edenhofer
  `mean_and_std_healpix.fits` ≈ **3.2 GB** (`auto` ≈ 5.6 GB); document size + location like GCNS opt-58.
  Cache is gitignored (`data/dust/` — already covered by the `data/` ignore rule), fetch-once/offline-after.
- **Zenodo throttle / manual download (documented in `docs/integration.md` + the GUI panel).** Zenodo
  (CERN open-data host) bandwidth-throttles large anonymous downloads (~0.5 MB/s observed), and the dustmaps
  fetcher can't resume — so the in-app fetch of these files is slow. The recommended path is a **resumable**
  manual `aria2c -c`/`wget -c` into `data/dust/{leike_2020,edenhofer_2023}/` then `dust-fetch --check`
  (dustmaps verifies the md5 and reuses it). `FetchDustMapPanel` surfaces these commands in a copyable box.

> **✅ Part A BUILT (2026-06-23).** `core/dust.py` (engine + `compute_dust_sightline` / `compute_dust_between` /
> `compute_dust_fetch`), `query.py` `dust-sightline` / `dust-between`, `main.py` CLI **option 59** `dust_fetch_data`
> (+ `_UTILITY_KEYS`), `requirements-dust.txt`, and `tests/_dustcheck.py` + `tests/test_dust_query.py` (14 tests:
> isolation, extra-missing, the engine math/seam/coverage via a **mocked map**, the validation/exit-code matrix,
> and a fetch-gated real-data anchor). Conversion scalars pinned from primary sources: Edenhofer **A_V = 2.8·E**
> (Edenhofer 2024 / ZGR23), Leike **A_V = 1.0857·1.202·τ_G** (O'Neill+ 2024). Full suite green at **867 tests
> (1 skipped — the un-fetched anchor)**; the stellar layer does not import `dustmaps` (subprocess-guarded). **Part
> B (routing `--weight dust`) is the remaining T2 work.**

---

## T2 Part B — dust-weighted routing (`core/dust_routing.py`)

New module **`core/dust_routing.py`** (forked, per locked decision — *not* `--weight` threaded into
`core/calculators.py` in place). It **reuses** the verified non-weight helpers from `core/calculators.py`
(`_resolve_star_position`, `_load_star_systems_positions`, `_SpatialGrid`, `_merge_endpoint`, `_map_node`,
`_node_dist`, `_UnionFind`, `HOURS_PER_JULIAN_YEAR`, `format_travel_time`) and the dust engine from `core/dust.py`
(`compute_dust_between`'s `_integrate_sightline` for per-leg A_V). Keeping the forked planners here keeps
`dustmaps` out of `core/calculators.py`.

### B.0 — the `_dijkstra` seam extraction (the one in-place change, guarded byte-identical)

`compute_jump_route` (`core/calculators.py:2077`) currently inlines both the BFS (`optimize="jumps"`) and the
Dijkstra (`optimize="distance"`) loops over `_SpatialGrid.neighbors(u, max_jump_ly)`, whose edge weight is the
geometric `w` (ly). **Extract the search into a cost-injected helper**

```python
def _grid_search(nodes, grid, s, t, max_jump_ly, optimize, edge_cost):
    # edge_cost(u, v, w_ly) -> non-negative additive cost
    #   distance routing passes edge_cost = lambda u,v,w: w  → byte-identical today
    #   dust routing      passes edge_cost = per-leg integrated A_V (≥0, additive)
```

so the existing `compute_jump_route` calls it with `edge_cost=lambda u,v,w: w` (BFS stays hop-count). **The
existing `tests/test_route_planning_opts.py` / `tests/test_query_route_opts.py` guard byte-identical output** —
no behavioral change. Dust routing's `jump-route --weight dust` calls the same helper with a memoized per-edge
A_V cost (`compute_dust_between`-style integration over the leg, cached by ordered node pair). **Reachability
(`--max-jump`) stays geometric** (governs which edges exist, dust-independent — request §B.4); dust only weights
existing edges. A_V is a non-negative additive edge weight → Dijkstra-correct (request §B.2).

### B.1 — forked planner entry points (`core/dust_routing.py`)

Each mirrors its `core/calculators.py` sibling's signature with an added `weight` (default `"distance"`) and
`map_sel`/`dust_step_pc`, returns the same shape **plus** dust fields. `weight="distance"` delegates to the
existing calculator (so the stellar path is literally unchanged); `weight="dust"` runs the forked cost path.

| Planner (forked) | Dust behavior | Reuses |
|---|---|---|
| `compute_jump_route_weighted` | `_grid_search` with A_V edge cost (flagship least-dust path) | `_SpatialGrid`, `_grid_search` |
| `compute_optimal_tour_weighted` | NN-seed + 2-opt over an **A_V cost matrix** (2-opt is metric-agnostic) | `compute_optimal_tour` skeleton |
| `compute_multi_stop_weighted` | cumulative A_V over the ordered legs | ordered-leg loop |
| `compute_nearest_neighbor_weighted` | "nearest" = least-A_V unvisited (still `_load_star_systems_positions` pool) | greedy loop |
| `compute_trade_route_weighted` | Kruskal MST over A_V edge costs | `_UnionFind` |

**Deferred (locked §13-Q9, §14):** `blend` weight, `--max-leg-av` pruning, `jump-network` cost-budget,
`farthest-first`.

### B.2 — output additions (per request §B.7)

- **Per leg:** existing fields + `a_v`, `a_v_lo`, `a_v_hi`, `weight_value`, `cumulative_av`, `cumulative_cost`.
- **Top level:** `weight`, `total_ly`, `total_av`, `total_cost`, and the **distance-optimal comparison** —
  `distance_optimal_ly`, `distance_optimal_av`, `extra_ly`, `saved_av` (run the distance-weighted planner over
  the same graph, integrate dust along *its* legs, and diff). This comparison is the deliverable's interpretive
  payoff (it replaces the dropped `blend`).
- **`--map auto` per leg** so seam-crossing legs integrate across both maps (§B.8).

> **✅ Part B BUILT (2026-06-23).** `_grid_search` extracted from `compute_jump_route` in `core/calculators.py`
> (byte-identical — guarded green by `test_route_planning_opts` + `test_query_route_opts`, 66 tests); new
> `core/dust_routing.py` with the 5 forked weighted planners (`compute_jump_route_dust` /
> `compute_optimal_tour_dust` / `compute_multi_stop_dust` / `compute_nearest_neighbor_dust` /
> `compute_trade_route_dust`) reusing the calculators helpers + `core.dust.integrate_segment_av`; `query.py`
> `--weight {distance,dust}` / `--map` / `--dust-step-pc` on the 5 subparsers (distance → unchanged calculators;
> dust → dust_routing) via `_add_dust_weight_flags`. Each result adds per-leg `a_v`/`cumulative_av`/`weight_value`
> + top-level `total_av` + the **distance-optimal comparison** (`extra_ly`/`saved_av`). Tests:
> `tests/test_dust_routing.py` (12 — routing logic via a mocked `_seg`, the flagship least-dust detour with the
> comparison, the integration-wiring constant-density check, preflight/exit-code matrix, and the weight=distance
> delegation guard). Reachability stays geometric; `--weight distance` byte-identical. Deferred per the locked
> decisions: `blend`, `--max-leg-av`, `jump-network` cost-budget, `farthest-first`. **T2 (and Phase T) complete.**

### B.3 — `query.py` surface

Add the flag set to the five Core planner subparsers (reuse the existing planners — no new subcommand):
`--weight {distance,dust}` (default `distance`; argparse `choices`), `--map {near-field,edenhofer,auto}`
(default `auto`), `--dust-step-pc` (default ~5 pc, coarser than a reported corridor — §B.6). Each handler routes
to `core.dust_routing.*` when `--weight dust`, else the existing `core.calculators.*` (so `--weight distance`
callers are byte-identical). `--weight distance` stays the default everywhere.

---

## T2 — consolidated deliverables

- **Code:** new `core/dust.py` (Part A engine + `compute_dust_sightline` / `compute_dust_between` /
  `compute_dust_fetch`); new `core/dust_routing.py` (5 forked weighted planners); `core/calculators.py`
  (extract `_grid_search` from `compute_jump_route` — byte-identical); `main.py` (option 59 `dust_fetch_data` +
  `_UTILITY_KEYS`); `query.py` (+`dust-sightline` / `dust-between` subcommands; +`--weight`/`--map`/
  `--dust-step-pc` on the 5 Core planner subparsers). **New optional dep file** `requirements-dust.txt`
  (`dustmaps, healpy, h5py, scipy, progressbar2, six, tqdm`). `.gitignore` += `data/dust/`. No GUI; no
  `core/calculators.py` `dustmaps` import.
- **Packaging note:** the repo has **no `setup.py`/`pyproject.toml`**, so the optional extra ships as
  **`requirements-dust.txt`** (the `extras_require['dust']` form in CLAUDE.md is aspirational — there is no
  setup to hang it on). Documented as `pip install -r requirements-dust.txt` in the WSL venv.
- **Docs:** `docs/integration.md` — a "Dust / ISM (optional `dustmaps` extra)" section: per-key schemas for
  `dust-sightline` / `dust-between`, the `--weight`/`--map`/`--dust-step-pc` flags on the 5 planners, the
  declared `units` (A_V mag, R_V=3.1) + `native_quantity` echo, the two pinned conversion scalars + sources, the
  WSL-venv-only / import-gated contract, and the cumulative-σ quadrature caveat. `CLAUDE.md` already carries the
  Phase-T dust WSL/Linux-only note — update it to say `edenhofer2023` and `requirements-dust.txt`. Mark T2 built
  in `future_phases.md`.

## T2 — test plan (gated on `dustmaps` importability — mirrors the `*_live.py` gate)

A shared gate `tests/_dustcheck.py::dustmaps_importable()` (try `import dustmaps, healpy`); tests use
`@unittest.skipUnless(dustmaps_importable() and _maps_fetched(), …)` so a native-Windows pip checkout **and** a
WSL checkout that hasn't fetched the (3.6 GB) maps both skip cleanly — the maintainer baseline of ≤3 skips
becomes "≤3 net + the dust suite when maps are absent."

- **`tests/test_dust_query.py`** (Part A, gated): `dust-sightline` happy-path key set + a known sightline anchor
  (a literature A_V toward a mapped cloud, e.g. toward the ρ Oph / Local Bubble wall within ~150 pc — pin the
  reference value at build); `auto` seam — a 0→120 pc sightline shows `seam`-flagged bins at ~69 pc and no inner
  double-count (cumulative A_V continuous across the handover); explicit `--map near-field` loads only Leike;
  out-of-coverage (a Z-exit beyond ±270 pc) → null bins + `out_of_coverage` note, exit 0; `dust-between` adds
  `star*_info`/`separation_*` and resolves `Sol`→origin; the validation matrix (exit 1/2). A **non-gated**
  sub-test asserts `core/dust.py` import does **not** drag `dustmaps` into `core/calculators.py` (guards the
  isolation) and that a dust subcommand on a no-dustmaps checkout returns the curated extra-missing error.
- **`tests/test_dust_routing.py`** (Part B, gated): `jump-route --weight dust` returns the least-A_V path over
  the **same reachable graph** as `--weight distance` (same `--max-jump`), with per-leg + cumulative A_V and the
  `extra_ly`/`saved_av` comparison; `--weight distance` is byte-identical to `compute_jump_route`; the four other
  weighted planners return their shape + dust fields; an all-dust-equal toy graph makes dust and distance routes
  coincide (sanity).
- **Regression (non-gated, MUST stay green):** the existing `tests/test_route_planning_opts.py` +
  `tests/test_query_route_opts.py` after the `_grid_search` extraction — the byte-identical guard for the seam.

## T2 — validation contract (per surface, self-validating Phase-H/P)

| Surface | exit 1 (`{error}`) | exit 2 (argparse) |
|---|---|---|
| `dust-sightline` | dust extra missing; map not fetched; `dist_end≤dist_start`/`<0`; `n_steps<1`/`step_pc≤0`; resolver error | not exactly one direction mode; bad `--map`; non-numeric; both `--steps`+`--step-pc` |
| `dust-between` | dust extra missing; map not fetched; resolver error on either endpoint | not one endpoint mode per side; bad `--map`; non-numeric |
| `dust-fetch` (opt 59 CLI) | dust extra missing; download/verify failure (classified) | n/a (CLI menu) |
| `jump-route`/`optimal-tour`/`multi-stop`/`nearest-neighbor`/`trade-route` `--weight dust` | dust extra missing; map not fetched; existing planner errors | bad `--weight`/`--map`; non-numeric `--dust-step-pc` |

Geometry leaving a map box is **never** an error (null bin + note) — only invalid *inputs* are.

## T2 — success criteria / acceptance (done when)

- **Part A:** `dust-sightline` / `dust-between` return per-bin **A_V (mag, R_V=3.1)** + native echo + per-bin/cumulative
  σ across the ~69 pc seam for both maps, with the inner column counted exactly once (differential integration);
  star/`Sol` endpoints resolve through the existing resolvers; option-59 fetch/cache works offline-after on the
  native WSL FS; out-of-coverage is null+note, deep cavity is small+wide-σ+note.
- **Part B:** `jump-route --weight dust` returns the least-extinction path over the same reachable graph as
  `--weight distance`, with per-leg + cumulative A_V and the `extra_ly`/`saved_av` distance-optimal comparison;
  `--weight distance` is byte-identical (guarded by the existing route tests); `--max-jump` still governs
  reachability; the other four Core planners accept `--weight dust`.
- The two native→A_V scalars are pinned against their cited extinction curves (ZGR23 / Gaia-G law) and recorded
  in `docs/integration.md`; `edenhofer2023` (not 2024) is used throughout.
- `dustmaps`/`healpy` stay out of `core/calculators.py`; a native-Windows checkout imports the stellar layer and
  skips the gated dust tests; the WSL venv runs the full dust path. Full non-gated suite green.

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
| T2 architecture | Forked (`core/dust.py` + `core/dust_routing.py`); reuse non-weight helpers; extract `_grid_search` (the cost-injected Dijkstra/BFS seam) from `compute_jump_route`; fork the rest |
| T2 map key (verified) | Edenhofer = **`edenhofer2023` / `Edenhofer2023Query`**, not `edenhofer2024` (paper 2024, arXiv/dustmaps 2023) |
| T2 seam realization (verified) | Query **differential density (`integrated=False`) and integrate per-segment** — avoids dustmaps' `integrated=True` inner-<69 pc add-back entirely; Edenhofer differential is NaN inside ~69 pc so Leike owns 0–69, Edenhofer >69, no overlap |
| T2 native→A_V (build pin) | Standardize to A_V (mag, R_V=3.1) via two per-map scalars pinned at build against the cited curves — ZGR23 `E`→A_V (zenodo 6674521) for Edenhofer; Gaia-G e-foldings→τ_G→A_G→A_V for Leike; echo `native_quantity` + `units` |
| T2 optional extra (verified) | No `setup.py`/`pyproject.toml` exists → ship **`requirements-dust.txt`** (`dustmaps, healpy, h5py, scipy, progressbar2, six, tqdm`); `extras_require['dust']` in CLAUDE.md is aspirational. healpy 1.19.0 has a cp312 manylinux wheel — installs clean in the WSL venv |

## Suggested build order

T1a (5 items, sequenced 1→5) → T1b (new pure-math) → T1c (census filters) → T2 Part A (Leike → Edenhofer/seam)
→ T2 Part B (forked Core planners; `_grid_search` extraction first, guarded by the existing route tests). T1 and
T2 are independent; T1a was the lowest-risk starting point. **T1, T2 Part A, and T2 Part B all built (2026-06-23) — Phase T complete.**
