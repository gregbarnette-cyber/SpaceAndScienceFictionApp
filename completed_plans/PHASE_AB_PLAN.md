# Phase AB — Planetary Energy Balance / Terraforming (`equilibrium-temp`, `insolation-shift`, `atmosphere-mass`)

**Group J of the combined "settlement / propulsion / astrobiology / terraforming" request**
(Packet 19, Planetary Transformation / Terraforming). Three new **`query.py`-only**,
**pure-math**, self-validating calculators (the Phase-H/P contract). **No bundled table** — the
constants (σ, Earth's atmospheric mass) are reused/inline. Adds the terraforming
**radiative/mass balance**: can a planet be warmed to habitable temperatures, how much
greenhouse forcing or mirror area that takes, and how much volatile mass an atmosphere/ocean
needs. `query.py` has only `atmosphere-retention` (Jeans escape) nearby.

Specced in
`scifiWorldBuilding-Claude/research/query-api-methods/settlement-transformation-calculators-request.md`
(§Group J; status *Proposed*; the feasibility/prerequisites calc — technique families,
magnetosphere substitutes, ecology, ocean chemistry defer to later; **volatile *supply* =
volatile-geography canon**, J reports *demand* only). The **physics is durable** (`T_eq=[S(1−A)/4σ]^¼`,
grey-atmosphere greenhouse, hydrostatic `m=4πR²P/g`); present-day albedos are overridable ancestors.

**Lineage:** Phase V/W/X — a new core module + granular subcommands + **no GUI** (one completion
row in `docs/gui-architecture.md`, query.py-only). No network, no DB, no RNG, no time.
**Complements** `atmosphere-retention` / `habitable-zone` (cross-reference in the help). **Build
last (after Y/Z/AA)** — packet order (Packet 19).

---

## Resolved implementer decisions

Locked with the user 2026-07-01 (naming) + carried from the request:

1. **Phase letter → AB** (G→Y, H→Z, I→AA, J→AB).
2. **Home module → new `core/terraforming.py`** (`compute_equilibrium_temp`,
   `compute_insolation_shift`, `compute_atmosphere_mass`). **No bundled table** — reuses
   `_STEFAN_BOLTZMANN` (+ `_M_PER_AU`, `_EARTH_RADIUS_*`, `_G` etc.) from `equations`; the one
   fixed reference (`_EARTH_ATM_MASS_KG = 5.15e18`) goes inline as a module constant with a comment.
3. **Reuse `_STEFAN_BOLTZMANN`** for the equilibrium/grey-atmosphere temperature and the same
   `luminosity_lsun + distance_au → S` chain as Phase AA (share the expression / a small helper).
4. **Output → JSON only** (parity with V/W/X); inputs echoed.

---

## 1. Files touched

| File | Change |
|---|---|
| `core/terraforming.py` *(new)* | The three `compute_*` functions + `_EARTH_ATM_MASS_KG = 5.15e18` (module constant, commented). Imports `_STEFAN_BOLTZMANN`, `_M_PER_AU`, planet-radius/`_G` constants from `equations`. |
| `query.py` | `import core.terraforming as terraforming`; three `cmd_*` handlers + three `add_parser(...)` blocks. |
| `tests/test_terraforming.py` *(new)* | In-process core tests: acceptance anchors (Earth/Mars T_eq, Mars atmo mass), forcing forms, inverse solves, mirror/shade signs, validation matrix, determinism. |
| `tests/test_query_terraforming.py` *(new)* | Subprocess contract: happy-path JSON + core parity + exit-code matrix. |
| `docs/integration.md` | New "Planetary energy balance / terraforming (Phase AB)" section + three quick-ref rows; units on every field. |
| `docs/gui-architecture.md` | One Phase-AB completion-status row (query.py-only). |
| `CLAUDE.md` | Phase-AB test bullet + `core/terraforming.py` in the `core/` list. |

---

## 2. Formulas

σ = `_STEFAN_BOLTZMANN`.

**J1 equilibrium-temp.** `T_eq = [ S·(1−A) / (4·σ) ]^¼` (S = insolation W/m², A = Bond albedo).
Surface temp via **one** forcing form: simple offset `T_s = T_eq + ΔT_greenhouse`; grey-atmosphere
`T_s = T_eq·(1 + ¾τ)^¼` (optical depth τ); **inverse** — given `target_surface_k`, solve the
required forcing (ΔT = target − T_eq, and the equivalent τ from the grey form).

**J2 insolation-shift.** To change the *planet-average* absorbed flux by `ΔS` (W/m², sphere-
averaged), redirect `ΔS·4πR_p²` of power → mirror/shade area `A_m = ΔS·4πR_p² / solar_flux`
(mirror at the planet's orbit). Signed ΔS: + = mirror (warm), − = shade/soletta (cool). Report
`area_vs_planet_cross_section = A_m / (πR_p²)`.

**J3 atmosphere-mass.** Hydrostatic `m = 4πR²·P / g`; inverse `P = m·g/(4πR²)`. g from
`--planet-mass-earth` if not given (`g = G·M/R²`). `atmosphere_mass_earth_atm = m / 5.15e18`.

**Insolation source (J1/J2):** `--insolation-wm2`/`--solar-flux-wm2` directly, or `--luminosity-lsun`
+ `--distance-au` → `S = L_sun·L / (4π·(d·AU)²)` (the shared Phase-AA expression).

---

## 3. Signatures, output shapes, validation

**`compute_equilibrium_temp(insolation_wm2=None, luminosity_lsun=None, distance_au=None,
albedo=0.3, greenhouse_delta_k=None, optical_depth=None, target_surface_k=None)`**
- Insolation source (one); **exactly one forcing form** (`greenhouse_delta_k` / `optical_depth`
  / `target_surface_k`).
- **Out:** `{insolation_wm2, albedo, t_eq_k, greenhouse_delta_k|null, optical_depth|null,
  t_surface_k, required_forcing|null, model_note}`. `required_forcing` (when `target_surface_k`
  given) = `{greenhouse_delta_k, optical_depth}` needed to reach the target.
- **Validation:** insolation ≤ 0 (or L/distance ≤ 0); albedo∉[0,1); not exactly one insolation
  source / one forcing form; optical_depth < 0; target_surface_k ≤ 0.
- **Anchors:** Earth (S1361, A0.3) → T_eq ≈ 255 K; +Δ33 → T_s ≈ 288 K. Mars (S589, A0.25) →
  T_eq ≈ 210 K.

**`compute_insolation_shift(planet_radius_km, delta_insolation_wm2, solar_flux_wm2=None,
luminosity_lsun=None, distance_au=None)`**
- **Out:** `{mirror_area_m2, mirror_area_km2, area_vs_planet_cross_section, delta_insolation_wm2,
  mode ("mirror"|"shade"), model_note}`. mode from the sign of ΔS.
- **Validation:** planet_radius_km ≤ 0; solar-flux source (one; positive); ΔS = 0 (no-op → error).
- **Anchor:** a modest ΔS over Mars's `4πR²≈1.44e14 m²` → mirror area of that order.

**`compute_atmosphere_mass(planet_radius_km, surface_gravity_ms2=None, planet_mass_earth=None,
pressure_bar=None, volatile_mass_kg=None, species=None)`**
- g from `surface_gravity_ms2` or derived from `planet_mass_earth`. **Exactly one of**
  `pressure_bar` (→ mass) / `volatile_mass_kg` (→ pressure).
- **Out:** `{atmosphere_mass_kg, atmosphere_mass_earth_atm, surface_pressure_bar,
  planet_radius_km, surface_gravity_ms2, species, model_note}`.
- **Validation:** planet_radius_km ≤ 0; not exactly one gravity source; not exactly one of
  pressure/mass; non-positive pressure/mass/g; unknown `--species` (choices n2/co2/o2/h2o).
- **Anchor:** Mars 1 bar (R 3390 km, g 3.71) → m ≈ 3.9e18 kg (~0.76 Earth atmo mass).

---

## 4. `query.py` wiring (modeled on the `radiator-area` / `atmosphere-retention` blocks)

Three `add_parser` blocks. `equilibrium-temp`: `--insolation-wm2` / (`--luminosity-lsun` +
`--distance-au`); `--albedo` `default=0.3`; `--greenhouse-delta-k` / `--optical-depth` /
`--target-surface-k` (the "exactly one forcing form" check in the core, curated exit-1).
`insolation-shift`: `--planet-radius-km` + `--delta-insolation-wm2` required (signed); the
solar-flux source. `atmosphere-mass`: `--planet-radius-km` required; `--surface-gravity-ms2` /
`--planet-mass-earth`; `--pressure-bar` / `--volatile-mass-kg`; `--species` `choices=[n2,co2,o2,h2o]`.

---

## 5. Validation contract (self-validating, Phase-H/P)

- **Core `{"error"}` exit 1:** the §3 range / source-count / forcing-form checks; unknown species.
- **Argparse exit 2:** a bad `--species` choice; any non-numeric value. *(The "exactly one
  insolation source / forcing form / pressure-or-mass" rules are **core** checks → exit 1.)*

---

## 6. Tests

**`tests/test_terraforming.py`** (in-process):
- **J1 anchors:** Earth S1361/A0.3 → T_eq ≈ 255 K (±1); +Δ33 → T_s ≈ 288 K; Mars S589/A0.25 →
  T_eq ≈ 210 K.
- **J1 forcing forms:** offset vs grey-atmosphere (a τ that reproduces a given ΔT); **inverse** —
  `target_surface_k=288` → required ΔT ≈ 33 K (and the equivalent τ).
- **J1 insolation source:** `luminosity_lsun=1, distance_au=1` → S ≈ 1361 → T_eq ≈ 255 (parity).
- **J2:** mirror (ΔS>0) vs shade (ΔS<0) mode + sign; area vs cross-section ratio sane; the Mars
  order-of-magnitude anchor.
- **J3:** Mars 1 bar → m ≈ 3.9e18 kg (~0.76 Earth atm); inverse mass→pressure round-trips; g
  derived from `planet_mass_earth` matches an explicit g.
- **Validation matrix:** albedo=1.0; two forcing forms; neither insolation source; ΔS=0;
  radius=0; two of pressure/mass; unknown species; optical_depth<0.
- **Determinism:** deep-equal on repeat.

**`tests/test_query_terraforming.py`** (subprocess, mirrors `test_query_thermal.py`):
- Happy-path JSON + core parity for `equilibrium-temp --insolation-wm2 1361 --albedo 0.3
  --greenhouse-delta-k 33`, `insolation-shift`, `atmosphere-mass --planet-radius-km 3390
  --surface-gravity-ms2 3.71 --pressure-bar 1`.
- Exit-code matrix: exit-1 (`--albedo 1.0`, two forcing forms, radius=0, two of pressure/mass);
  exit-2 (bad `--species`, non-numeric `--insolation-wm2`).

---

## 7. Success criteria

- Reproduces every §3 acceptance anchor (Earth/Mars T_eq, Mars atmosphere mass).
- J1 three forcing forms determinate incl. the inverse (target → required forcing).
- J2 mirror/shade sign + cross-section ratio correct; J3 mass↔pressure round-trips.
- No bundled table — constants reused from `equations`; `_EARTH_ATM_MASS_KG` inline + commented.
- Validation matrix passes (core exit-1 / argparse exit-2 split per §5).
- Documented in `docs/integration.md` with **units on every field**; one `gui-architecture.md`
  completion row; one `CLAUDE.md` bullet.
- On shipment: flip Group J in the request file to `Deprecated — FULFILLED` — **completing the
  four-group request**; record the as-built per-key shapes.

---

## 8. Open items / risks (verify at build)

1. Lowest-risk of the four groups — all three are textbook closed forms (`T_eq`, grey-atmosphere,
   hydrostatic) over verified constants.
2. **Grey-atmosphere form** — confirm the `T_s = T_eq·(1+¾τ)^¼` convention matches the packet's
   intended greenhouse model (vs a bare ΔT offset); expose both, note the difference in `model_note`.
3. **`_EARTH_ATM_MASS_KG`** — pin at 5.15e18 kg (the request's reference) with a comment; used only
   for the `atmosphere_mass_earth_atm` fraction.

~1 focused session (or bundle with Phase AB's siblings — all three subcommands are small).

## References (verify at implementation; none a load-bearing canon claim)
Planetary equilibrium temperature & grey-atmosphere greenhouse (planetary-science texts);
mirror/shade terraforming (Zubrin & McKay); atmospheric mass `m=4πR²P/g` (hydrostatic). Present-day
albedos are overridable ancestors; volatile *supply* is the volatile-geography canon's authority
(J reports demand only).
