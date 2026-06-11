# Phase H — Worldbuilding Calculators · Implementation Plan

Detailed, build-ready plan for Phase H of `future_phases.md`. Five pure-math
calculators for authors/worldbuilders. **No network, no CSV, no DB.** Each is a
new `core/equations.py` function + a `ResultPanel` subclass (no
`DiagramToggleMixin` — none have visualizations), plus a `query.py` subcommand
(Phase N forward-note: H functions get their integration surface at build time).

> Status: **plan only — not implemented.** Pointer lives in the Phase H section of
> `future_phases.md`. Companion mockup: `mockups/phase-h.html`.

---

## ⚠️ Two formula corrections vs. future_phases.md

The brainstorm in `future_phases.md` has two transcription errors that this plan
**corrects** (both verified numerically against known reference values):

1. **H1 Roche — rigid coefficient.** future_phases uses `2.44` for the rigid limit
   and `2.456` for fluid, making them nearly identical (physically meaningless —
   the rigid and fluid limits differ by ~factor 1.95). The correct **rigid
   coefficient is `1.26`** (= `2^(1/3)`), fluid stays `2.456`. Verified: Earth
   (ρ≈5.51 g/cm³) with a Moon-density satellite (3.34 g/cm³) gives rigid ≈ **9,487 km**
   (known Earth–Moon rigid Roche ≈ 9,492 km) and fluid ≈ **18,492 km** (≈ 18,470 km). ✓

2. **H4 Binary — P-type mass-ratio sign.** future_phases writes `… − 4.12μ …`,
   which yields a **negative** critical SMA for an equal-mass circular binary
   (−1.73·a_b — nonsense). The Holman & Wiegert (1999) circumbinary fit is
   **`+ 4.12μ`**, giving `a_c,P ≈ 2.388·a_b` for μ=0.5, e=0. ✓ (The S-type
   polynomial in future_phases is already correct.)

---

## Grounding facts (verified in code)

| Area | Reality |
|---|---|
| Core module | `core/equations.py` — `import math`; compute fns return a `dict` (or `list`); constants currently defined inline per-fn (`EARTH_MASS_KG = 5.972e24`, `G = 6.674e-11` inside `compute_moon_orbital_distance`). |
| Pure-math panel pattern | `LuminosityPanel` / `HabZone*Panel`: `build_inputs()` sets `self._input_count`, builds a `QFormLayout` + Calculate `QPushButton`, wires `returnPressed → btn.click`. `build_results_area()` adds a hidden red `_err` `QLabel` + a result-container `QVBoxLayout` + `addStretch()`. `_calculate()` does `float()` try/except, calls the core fn, rebuilds a `QStandardItemModel`/`QTableView`. No background thread (synchronous). |
| Table coloring | Panels build their own `QStandardItemModel`; cells are `QStandardItem`. Color via `item.setForeground(QBrush(QColor(...)))`. `make_table` (base) is not used by these panels. |
| nav | `gui/nav.py` `NAVIGATION = [(category, [(label, "PanelClassName"), …])]`; resolved via `getattr(gui.panels, name)`. |
| exports | `gui/panels/__init__.py` explicit `from gui.panels.x import Y`. |
| query.py | thin JSON dispatcher; argparse subparsers; numeric args; prints `json.dumps(result, indent=2, default=str)`; exit 0/1; `{"error"}` on failure. Tests use `SPACE_APP_DB` env / subprocess (none needed here — no DB). |

**Refinement to the future_phases sketch:** the H core functions will **validate
physical ranges and return `{"error": str}`** for bad input (≤0 where a positive
is required, `e ∉ [0,1)`). This serves both the GUI (panel shows the red label)
and the Phase-N `query.py` subcommands, and matches the `{"error"}` contract used
by the `search_*` functions. (Existing equations fns don't self-validate; the H
ones will, because they're also exposed via `query.py`.)

---

## Work Package 0 — Shared constants + helper (`core/equations.py`)

Add a module-level constants block at the top (the file currently has only
`_KOPPARAPU_PARAMS`), so H1–H5 don't each re-declare `G`/`EARTH_MASS_KG`/etc. and
drift:

```python
_G              = 6.674e-11          # gravitational constant, m³ kg⁻¹ s⁻²
_K_B            = 1.380649e-23       # Boltzmann constant, J/K
_EARTH_MASS_KG  = 5.972e24
_EARTH_RADIUS_KM= 6371.0
_EARTH_RADIUS_M = 6.371e6
_SOLAR_MASS_KG  = 1.989e30
_M_PER_AU       = 149_597_870_700.0
_KM_PER_AU      = 149_597_870.7
_AMU_KG         = 1.66054e-27
_SEC_PER_YEAR   = 3.15576e7          # Julian year (365.25 d)

def _rocky_radius_km(mass_earth: float) -> float:
    """Approximate rocky-body radius from mass (R ∝ M^0.55). Shared by H1, H2."""
    return _EARTH_RADIUS_KM * mass_earth ** 0.55
```

> The shared `_rocky_radius_km` removes the H1/H2 duplication flagged in the Phase H
> brainstorm. (Leave the existing inline constants in the older functions alone —
> out of scope; only the new H functions use the module-level block.)

---

## WP1 — H1 Roche Limit (`RocheLimitPanel`)

### Core: `compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None) -> dict`
- Validate: `primary_mass_earth > 0`, `satellite_density_gcc > 0`, and (if supplied) `primary_radius_earth > 0` → else `{"error": "…must be positive."}`.
- `R_km = primary_radius_earth*_EARTH_RADIUS_KM` if supplied else `_rocky_radius_km(primary_mass_earth)`; `R_m = R_km*1000`.
- `M_kg = primary_mass_earth*_EARTH_MASS_KG`; `ρ_primary_gcc = (3*M_kg/(4πR_m³)) / 1000`.
- `ratio = (ρ_primary_gcc / satellite_density_gcc)**(1/3)`.
- **`rigid_km = R_km * 1.26 * ratio`** (corrected); **`fluid_km = R_km * 2.456 * ratio`**.
- `*_au = *_km / _KM_PER_AU`.
- Return `{primary_mass_earth, primary_radius_km, primary_density_gcc, satellite_density_gcc, rigid_km, rigid_au, fluid_km, fluid_au}`.

### GUI: `RocheLimitPanel(ResultPanel)`
- Inputs: primary mass `QLineEdit`, satellite density `QLineEdit`, primary radius `QLineEdit` (label "Primary Radius (R⊕) — optional, estimated from mass if blank").
- Output: one-row `QTableView`: Primary Mass · Primary Radius (km) · Primary Density (g/cm³) · Satellite Density · Rigid Roche (km) · Rigid Roche (AU) · Fluid Roche (km) · Fluid Roche (AU), 4dp.

---

## WP2 — H2 Tidal Locking Timescale (`TidalLockingPanel`)

### Core: `compute_tidal_locking_time(primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa=3e10, tidal_q=100) -> dict`
- Validate all four primaries `> 0`; `tidal_q > 0`, `rigidity_pa > 0`.
- `ω₀ = 2π/(initial_rotation_hours*3600)`; `a_m = sma_km*1000`.
- `R_sat_m = _rocky_radius_km(satellite_mass_earth)*1000`; `M_sat = satellite_mass_earth*_EARTH_MASS_KG`; `M_pri = primary_mass_earth*_EARTH_MASS_KG`.
- `I = 0.4*M_sat*R_sat_m²` (uniform sphere); `k₂ = 0.3` (rocky-body approximation).
- `T_sec = (ω₀ * a_m⁶ * I * tidal_q) / (3 * _G * M_pri² * k₂ * R_sat_m⁵)`; `years = T_sec/_SEC_PER_YEAR`; `gyr = years/1e9`.
- Return `{primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa, tidal_q, satellite_radius_km, lock_time_years, lock_time_gyr}`.
- **Note:** `rigidity_pa` is accepted and echoed for transparency but `k₂` is fixed at `0.3` (the MacDonald rocky-body simplification); documented as an order-of-magnitude estimate. (Reserved for a future Love-number refinement; flagged so it doesn't read as silently-unused.)

### GUI: `TidalLockingPanel(ResultPanel)`
- Inputs: 4 required `QLineEdit` (primary mass, satellite mass, SMA km, initial rotation hr) + a `QGroupBox("Advanced Parameters")` holding rigidity + Q `QLineEdit`s **pre-filled** with `3e10` / `100`.
- Output: one-row table: the inputs + Sat Radius (km) + Lock Time (yr, scientific `:.3e`) + Lock Time (Gyr, 4dp).

---

## WP3 — H3 Hill Sphere (`HillSpherePanel`)

### Core: `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0) -> dict`
- Validate `star_mass_solar>0`, `planet_mass_earth>0`, `sma_au>0`, `0 ≤ e < 1`.
- `M_star = star_mass_solar*_SOLAR_MASS_KG`; `M_p = planet_mass_earth*_EARTH_MASS_KG`; `a_m = sma_au*_M_PER_AU`.
- `r_H_m = a_m*(1-e)*(M_p/(3*M_star))**(1/3)`; km + AU; `stable_limit = 0.5*r_H`.
- Return `{star_mass_solar, planet_mass_earth, sma_au, eccentricity, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au}`.
- **Reference anchor (test):** Earth (1 M☉, 1 M⊕, 1 AU, e=0) → `hill_radius_km ≈ 1,496,000` (0.0100 AU), stable ≈ 748,000 km.

### GUI: `HillSpherePanel(ResultPanel)`
- Inputs: star mass, planet mass, SMA (required) + eccentricity (optional, placeholder "0 if circular").
- Output: one-row table: inputs + Hill Radius (km/AU) + Stable Orbit Limit (km/AU), 4dp.

---

## WP4 — H4 Binary Orbit Stability (`BinaryOrbitPanel`)

### Core: `compute_binary_orbit_stability(mass1_solar, mass2_solar, binary_sma_au, test_sma_au, eccentricity=0) -> dict`
- Validate masses `>0`, `binary_sma_au>0`, `test_sma_au>0`, `0 ≤ e < 1`.
- Order so `M1 ≥ M2` (swap if needed); `μ = M2/(M1+M2)`; `e = eccentricity`.
- `a_c_stype = (0.464 − 0.380μ − 0.631e + 0.586μe + 0.150e² − 0.198μe²) * binary_sma_au`.
- **`a_c_ptype = (1.60 + 5.10e − 2.22e² + 4.12μ − 4.27eμ − 5.09μ² + 4.61e²μ²) * binary_sma_au`** (corrected `+4.12μ`).
- `orbit_type = "S-type" if test_sma_au < binary_sma_au/2 else "P-type"` (heuristic).
- `is_stable = test_sma_au < a_c_stype` (S-type) **or** `test_sma_au > a_c_ptype` (P-type).
- `stable_region_description` — human string, e.g. `"S-type orbits stable within {a_c_stype:.3f} AU of either star; P-type orbits stable beyond {a_c_ptype:.3f} AU from the binary barycenter."`
- Return `{mass1_solar, mass2_solar, mass_ratio, binary_sma_au, eccentricity, stype_critical_sma_au, ptype_critical_sma_au, test_sma_au, orbit_type, is_stable, stable_region_description}`.
- **Reference anchor (test):** μ=0.5, e=0 → `a_c_stype ≈ 0.274·a_b`, `a_c_ptype ≈ 2.388·a_b`.

### GUI: `BinaryOrbitPanel(ResultPanel)`
- Inputs: mass1, mass2, binary SMA, test SMA (required) + eccentricity (optional, default 0).
- Output: a **green/red verdict label** (`Stable` / `Unstable`) above the table, then a one-row table: Mass1 · Mass2 · Mass Ratio (μ) · Binary SMA · Eccentricity · S-Type Critical SMA · P-Type Critical SMA · Test SMA · Orbit Type · Stable?, then the description line.

---

## WP5 — H5 Atmosphere Retention (`AtmosphereRetentionPanel`)

### Core: `compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k) -> dict`
- Validate all `> 0`.
- `M = planet_mass_earth*_EARTH_MASS_KG`; `R = planet_radius_earth*_EARTH_RADIUS_M`.
- `v_escape_kms = sqrt(2*_G*M/R)/1000`.
- Gases (amu): H₂ 2, He 4, CH₄ 16, H₂O 18, N₂ 28, O₂ 32, CO₂ 44.
- Per gas: `m = amu*_AMU_KG`; `λ = (_G*M*m)/(_K_B*temperature_k*R)`; `v_thermal_kms = sqrt(2*_K_B*temperature_k/m)/1000`; status: `λ>6` → "Retained", `3<λ≤6` → "Escaping slowly", `λ≤3` → "Lost rapidly".
- Return `{planet_mass_earth, planet_radius_earth, temperature_k, v_escape_kms, gases:[{gas, mol_mass_amu, lambda, v_thermal_kms, status}]}`.
- **Note (document in `docs/equations.md`):** uses the planet's *equilibrium* temperature, which underestimates exospheric temperature, so the simplified Jeans model is **optimistic about retention** — a worldbuilding heuristic, not an exospheric-escape simulation. Reference: Earth (1,1,255) → `v_escape ≈ 11.19 km/s`; λ scales linearly with molecular mass (λ_CO2 = 22·λ_H2).

### GUI: `AtmosphereRetentionPanel(ResultPanel)`
- Inputs: 3 `QLineEdit` (mass, radius, temp).
- Output: an escape-velocity `QLabel` above a per-gas `QTableView`: Gas · Mol. Mass (amu) · Jeans λ (2dp) · Escape Vel (km/s) · Thermal Vel (km/s) · Status — with the **Status cell color-coded** (green Retained / amber Escaping slowly / red Lost rapidly).

---

## WP6 — Shared GUI helper + wiring

### Color-cell helper (in `gui/panels/worldbuilding.py`)
```python
from PySide6.QtGui import QStandardItem, QBrush, QColor
_STATUS_COLORS = {"Retained": "#2e8b57", "Escaping slowly": "#b8860b", "Lost rapidly": "#b03030"}
def _status_item(text, color):
    it = QStandardItem(text); it.setEditable(False)
    it.setForeground(QBrush(QColor(color))); return it
```
Used for H5 status cells and the H4 verdict label (`label.setStyleSheet("color: #2e8b57;"|"#b03030;")`).

### Files
- **`gui/panels/worldbuilding.py`** (new) — the five panel classes + `_status_item`. All inherit `ResultPanel` directly. Reuse the `LuminosityPanel` structure (`_input_count`, form + Calculate, hidden `_err`, result container, rebuild table on each calc, check the core result for `"error"` and show it in `_err`).
- **`gui/panels/__init__.py`** — `from gui.panels.worldbuilding import (RocheLimitPanel, TidalLockingPanel, HillSpherePanel, BinaryOrbitPanel, AtmosphereRetentionPanel)`.
- **`gui/nav.py`** — new **"Worldbuilding"** category, five entries (Roche Limit, Tidal Locking, Hill Sphere, Binary Orbit Stability, Atmosphere Retention).

---

## WP7 — query.py subcommands (Phase N integration, built with H)

Five subparsers in `query.py`, each wrapping a core fn verbatim (numeric args;
malformed → argparse exit 2; out-of-range → the core `{"error"}` dict, exit 1):

| Subcommand | Args |
|---|---|
| `roche-limit` | `--primary-mass-earth --satellite-density [--primary-radius-earth]` |
| `tidal-locking` | `--primary-mass-earth --satellite-mass-earth --sma-km --rotation-hours [--rigidity-pa --tidal-q]` |
| `hill-sphere` | `--star-mass-solar --planet-mass-earth --sma-au [--eccentricity]` |
| `binary-stability` | `--mass1-solar --mass2-solar --binary-sma-au --test-sma-au [--eccentricity]` |
| `atmosphere-retention` | `--planet-mass-earth --planet-radius-earth --temperature-k` |

---

## WP8 — Docs

- **`docs/equations.md`** — new "Worldbuilding Calculators (Phase H)" section: each function's full formula, the constants block + `_rocky_radius_km`, output-dict schema, **the two corrections vs the brainstorm**, and the H2/H5 model-limitation notes.
- **`docs/integration.md`** — five rows in the quick-reference table (all "Network: none") + one subcommand section each.
- **`docs/gui-architecture.md`** — add the five panels to the panel→option mapping table (option column "— (GUI-only, Phase H)") and `worldbuilding.py` to the repo-structure block.

---

## Tests & Validation

### `tests/test_worldbuilding.py` (new, offline, pure math — no Qt, no DB)
Anchored to the verified reference values above:
- **Roche:** Earth primary + 3.34 g/cm³ satellite → `rigid_km ≈ 9487` and `fluid_km ≈ 18492` (±1%); `primary_density_gcc ≈ 5.51`; rigid < fluid always.
- **Hill:** Earth (1,1,1,0) → `hill_radius_km ≈ 1.496e6` (±1%), `hill_radius_au ≈ 0.0100`, `stable_orbit_limit_km ≈ 7.48e5`.
- **Binary:** μ=0.5,e=0 → `stype_critical_sma_au ≈ 0.274·a_b`, `ptype_critical_sma_au ≈ 2.388·a_b` (asserts the `+4.12μ` correction — a `−4.12μ` regression would go negative); `is_stable`/`orbit_type` logic for a test SMA on each side; mass1<mass2 input is swapped so μ≤0.5.
- **Atmosphere:** Earth (1,1,255) → `v_escape_kms ≈ 11.19`; `λ` strictly increases with molecular mass; `λ_CO2 / λ_H2 ≈ 22`; each `status` matches its λ bucket.
- **Tidal:** Moon-like params → `lock_time_gyr` finite & > 0; doubling `sma_km` multiplies `lock_time_years` by ≈ 64 (the a⁶ dependence).
- **Error paths:** non-positive mass/radius/temp/SMA → `{"error"}`; `eccentricity ≥ 1` (H3/H4) → `{"error"}`.

### `tests/test_query_worldbuilding.py` (optional, subprocess like `test_gcns`)
- Each subcommand via subprocess: valid args → exit 0, JSON has the expected keys; out-of-range → exit 1 + `{"error"}`; missing required arg → exit 2.

### Manual / GUI validation
- `python gui_main.py` → Worldbuilding category → each panel: a representative calc, bad input shows the red error label, H4 verdict label flips green/red across the critical SMA, H5 status cells colored.
- `pytest` full suite green (Phase H adds no coupling to existing code beyond the new constants block).

---

## Success Criteria
- Five `compute_*` functions return the documented dicts and `{"error"}` on invalid input; outputs match the verified anchors (Roche 9.5k/18.5k km, Hill 1.496e6 km, Binary 0.274/2.388·a_b, Earth v_esc 11.19 km/s).
- The two formula corrections are implemented (rigid coeff 1.26; P-type `+4.12μ`) and locked by tests.
- Five GUI panels under a "Worldbuilding" nav category, following the existing pure-math panel pattern; H4 green/red verdict and H5 colored status render.
- Five `query.py` subcommands with the standard exit-code contract.
- New offline tests pass; full existing suite stays green; docs updated.

**Suggested build order:** WP0 (constants/helper) → WP1 (Roche: proves the core-fn + pure-math-panel + query.py vertical) → WP2–WP5 → WP6 wiring → WP7 query.py → WP8 docs → tests throughout.
