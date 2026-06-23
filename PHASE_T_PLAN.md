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
