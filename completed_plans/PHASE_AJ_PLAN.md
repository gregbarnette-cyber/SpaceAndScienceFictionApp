# PHASE AJ (Group P) — Planet-Formation Calculators — Implementation Plan

**Status:** ✅ **BUILT (2026-07-07).** All six subcommands implemented, wired into `query.py`, tested
(37 formation tests green), and documented (`docs/integration.md`, `docs/testing.md`, `CLAUDE.md`). Every
acceptance anchor + both followup-1 rulings pinned. Remaining: sister-repo ship updates (§0 — cheatsheet /
spec-deprecation / roadmap / audit-log), pending user commit. Original plan preserved below.

**Status (original):** Ready to build (all decisions frozen).
**Source spec:** `scifiWorldBuilding-Claude/research/query-api-methods/formation-calculators-request.md`
(one request, one group P, six subcommands).
**Golden-pin rulings:** `…/formation-calculators-followup-1.md` (P4 + P1 — authoritative, physics-verified).
**Physics pins:** claim-map cluster **F1–F6** (`…/star-and-planetary-system-generation/claim-map.md`).
**New module:** `core/formation.py`. **Consumer:** the sister `scifiWorldBuilding-Claude` repo via `query.py`.

`query.py`-only, pure-math, self-validating, numpy-free. No network, no DB, no GUI, no RNG, no time.
Contract identical to Groups K–O (`gravitation`/`relativity`/`warp`/`black_hole`): one granular subcommand
each · JSON to stdout · curated `{"error"}` + exit 1 on bad input · argparse exit 2 on usage error ·
`model_note` on every output object · **every bundled constant flag-overridable**. Build **P1 + P2 first**
(the "core" that sizes/spaces bodies), then P3–P6. Phase letter **AJ** = Group **P** (AE–AI were Groups K–O).

---

## 0. Files touched

| File | Change |
|---|---|
| `core/equations.py` | Add `_MU_GAS_DEFAULT = 2.34`, `_Z_SUN = 0.0134`. Reuse `_M_PROTON` as m_H; reuse `_G`, `_K_B`, `_SOLAR_MASS_KG`, `_EARTH_MASS_KG`, `_JUP_MASS_KG`, `_M_PER_AU`, `_KM_PER_AU`. |
| `core/formation.py` | **New** — 6 `compute_*` + shared helpers. |
| `query.py` | `import core.formation as formation`; 6 `cmd_*`; 6 `add_parser` blocks under a `# ── Phase AJ (Group P) — planet formation (Packet 3.5) ──` banner. |
| `tests/test_formation.py` | **New** — dual-runner golden-pin core tests (numpy-free). |
| `tests/test_query_formation.py` | **New** — subprocess contract + exit-code matrix (mirrors `test_query_gravitation.py`). |
| `docs/integration.md` | **New** "Planet formation (Phase AJ — Group P)" section with as-built JSON shapes. |
| `docs/testing.md` | Two lines: what the two new test files cover. |
| `CLAUDE.md` | One line registering `formation.py` (Group P) in the architecture blurb. |

**On ship (sister repo):** update `query-py-capability-cheatsheet.md`; flip
`formation-calculators-request.md` **and** `formation-calculators-followup-1.md` to Deprecated/fulfilled
with as-built shapes; mark the Packet 3.5 roadmap row "Group P built" + Phase-B3 audit-log entry.
**Do not edit** the request spec's body (no-edit rule) — record fulfillment via status/front-matter only.

---

## 1. Constants (`core/equations.py`)

Append to the exotic-physics constants block:
```python
_MU_GAS_DEFAULT = 2.34      # default mean molecular weight (H₂/He); Phase AJ formation disk model
_Z_SUN          = 0.0134    # solar metallicity / dust-to-gas ratio; Phase AJ (F1 pin)
```
m_H → reuse existing `_M_PROTON = 1.67262192369e-27` (the value that reproduces H/r ≈ 0.033).

---

## 2. Module design — `core/formation.py`

### Shared module-level helpers (so P1/P3/P4/P5 can't drift)
- `_sound_speed(temp_k, mu)` → `√(k_B·T/(μ·m_H))` (m/s)
- `_omega(mstar_kg, a_m)` → `√(GM★/a³)` (rad/s)
- `_kepler_velocity(mstar_kg, a_m)` → `√(GM★/a)` (m/s)
- `_aspect_ratio(temp_k, mstar_kg, a_m, mu)` → `c_s / v_K`
- `_resolve_hr(hr, temp_k, mstar_msun, a_au, mu)` → H/r from direct `--hr` **or** derived from
  `(--temp-k, --mstar-msun, --a-au)`; `{"error"}` if neither/both. Lets P3/P4/P5 stand alone yet chain
  from `disk-model`.
- Per-function `_NOTE_*` `model_note` strings (formula + regime + assumptions), like `gravitation.py`.

### P1 — `compute_disk_model(...)` ⭐ (build first)
The profile engine every other formation calc (and the generator's `mass_by_zone`) reads. MMSN baseline,
scalable by disk mass / M★ / metallicity.

- **Inputs:** `r_au` XOR `r_grid=(lo,hi,n)` (log-spaced); `mstar_msun=1`; `disk_mass_mmsn=1` XOR
  `disk_mass_msun`; `lstar_lsun=1` XOR `ms_luminosity` (bool → L★=M★^3.5); `feh` XOR `z` (default `_Z_SUN`,
  `Z = Z_⊙·10^[Fe/H]`); `snowline_au` override XOR computed default; `snowline_temp_k=170`; `ice_factor=2`;
  `mu=2.34`; overrides `sigma0=1700`, `sigma_slope=-1.5`, `temp0=280`, `temp_slope=-0.5`.
- **Formulae (F1 canon baseline):**
  - `Σ_gas(r) = σ0·(M_disk/M_MMSN)·(r/AU)^p` (M_MMSN scaling: `disk_mass_mmsn`, or `disk_mass_msun/0.01`).
  - `T(r) = T0·(L★/L⊙)^{1/4}·(r/AU)^q`.
  - `Σ_solid(r) = Z·f_ice(r)·Σ_gas(r)`; `f_ice = 1` interior to snow line, `ice_factor` exterior.
  - `c_s`, `H/r`, `H` (AU), `Ω`, `v_K` from the shared helpers.
- **Snow line (Ruling 2 = Option A):** solved from P1's **own** T-law — `T(r)=snowline_temp_k` →
  `snowline_au = √(L★)·(T0/snowline_temp_k)²·[unit]` ⇒ **2.71 AU at L=1, 170 K**; scales `∝ L^{1/2}`.
  **No `compute_ice_lines` import.** `--snowline-au` overrides the radius; `--snowline-temp-k` (default 170)
  overrides the condensation temperature.
- **Outputs (per radius):** `{r_au, sigma_gas_gcm2, sigma_solid_gcm2, temp_k, sound_speed_ms,
  aspect_ratio_hr, scale_height_au, omega_per_s, kepler_velocity_kms, disk_mass_mmsn, metallicity_z,
  interior_to_snowline, snowline_au, model_note}`. `--r-grid` → `{radii:[…per-radius dicts…], snowline_au,
  disk_mass_mmsn, metallicity_z, model_note}`.
- **Σ_solid convention note (spec line 110):** MMSN defaults emit **22.8 g/cm²** at 1 AU (Z_⊙·1700). The
  P2 isolation anchors use a **10 g/cm²** planetesimal convention — a lower, standard MMSN variant recovered
  via `--z`/`--ice-factor`. `model_note` states the default emits the Z_⊙-scaled dust density.

### P2 — `compute_isolation_mass(...)` ⭐ (build first)
Oligarchic isolation mass (F2 — Armitage Eq. 201, after Lissauer 1993).
`M_iso = (8/√3)·π^{3/2}·C^{3/2}·M★^{−1/2}·Σ_p^{3/2}·a³` in SI (Σ_p g/cm² → ×10 kg/m²; a AU → m).
- **Inputs:** `sigma_p_gcm2`; `a_au`; `mstar_msun=1`; `feeding_zone_c=2√3` XOR `feeding_zone_b` (oligarchic
  mutual-Hill full width; `C = B/(2·2^{1/3})`); output unit toggle `to_jupiter_masses` (default both).
- **Outputs:** `{isolation_mass_mearth, isolation_mass_mjup, feeding_zone_width_hill,
  convention ("half-width-C"|"full-width-b"), sigma_p_gcm2, a_au, mstar_msun, model_note}`.

### P3 — `compute_pebble_isolation_mass(...)`
F3 — Bitsch 2018. `M_iso,peb = 25·f_fit·(H/r/0.05)³` M⊕, `f_fit = 0.34·(log(0.001)/log(α))⁴ + 0.66`.
`--simple` → Lambrechts `20·(H/r/0.05)³`, f_fit=1. Optional `--dlnp-dlnr` (default −2.5 → factor 1).
- **Inputs:** `--hr` XOR (`--temp-k --mstar-msun --a-au`) via `_resolve_hr`; `alpha=1e-3`; `simple`;
  `dlnp_dlnr=-2.5`; overrides `peb_norm` (25; `--simple`→20).
- **Outputs:** `{pebble_isolation_mass_mearth, hr, alpha, f_fit, mode ("bitsch2018"|"lambrechts2014"),
  model_note}`.

### P4 — `compute_gap_opening_mass(...)`
F4 — Crida 2006 Eq. 15. Solve `P(q) = 3H/(4R_H) + 50/(qR) = p_target` for q by **pure-Python bisection**
(P monotone-decreasing in q; bracket e.g. [1e-6, 1e-1], ~200 iters). `H = (H/r)`, `R_H = (q/3)^{1/3}`
(both in units of a), `R = a²Ω/ν`. `M_gap = q·M★`.
- **Ruling 1 (a):** headline `gap_opening_mass_mjup` = the **solved marginal threshold** at `--p-target`
  (default 1.0). Must equal the mass at the reported `threshold_q`.
- **Inputs:** `--hr` XOR (`--temp-k --mstar-msun --a-au`); viscosity via `--alpha` (ν_code=α·(H/r)²,
  R=1/ν_code) XOR `--nu-code` (R=1/ν_code) XOR `--reynolds` (R direct); `mstar_msun=1`; `a_au` (for mass
  conversion); `p_target=1.0`.
- **Outputs:** `{gap_opening_mass_mearth, gap_opening_mass_mjup, threshold_q, hr, alpha_or_reynolds,
  p_value_at_threshold, model_note}`.
- **`model_note`:** the exact string in the ruling (marginal threshold; Case-1 q=1e-3→P=0.699 clear gap;
  Malik 2015 necessary-but-not-sufficient-for-migrating caveat).

### P5 — `compute_toomre_q(...)`
F5 — Armitage Eq. 164. `Q = c_s·Ω/(πGΣ)`; `unstable = Q < q_crit` (default 1); `λ_crit = 2c_s²/(GΣ)`;
`M_frag ≈ πΣ(λ_crit/2)²`.
- **Inputs:** `sigma_gcm2`; c_s from `--temp-k`(+`mu`) XOR `--cs-ms` XOR `--dispersion-ms`; `mstar_msun`;
  `a_au` (→ Ω); `mu=2.34`; `q_crit=1`.
- **Outputs:** `{toomre_q, unstable, q_crit, lambda_crit_au, fragment_mass_mjup, sound_speed_ms,
  omega_per_s, model_note}`.

### P6 — `compute_critical_core_mass(...)`
F6 — Armitage Eq. 236 (Ikoma+2000 fit). `M_crit = crit_norm·(Ṁ/1e-6)^index·(κ/1)^index` M⊕.
- **Inputs:** `mdot_core=1e-6` (M⊕/yr); `opacity=1` (cm²/g); `index=0.25`; `crit_norm=12`.
- **Outputs:** `{critical_core_mass_mearth, mdot_core, opacity, index, model_note}`.

---

## 3. Frozen golden pins (all numerically verified 2026-07-07)

| Cmd | Anchor (inputs) | Expected | Tol |
|---|---|---|---|
| **P1** | 1 AU, MMSN defaults | Σ_gas=**1700**, T=**280** | exact by construction |
| P1 | 1 AU, μ=2.34, M★=M⊙ | H/r=**0.0334** | ±0.001 |
| P1 | 5.2 AU | Σ_gas=**143.4**, T=**122.8** | ±0.5 |
| P1 | Σ_solid @1 AU, Z_⊙, interior | **22.78 g/cm²** | ±0.05 |
| P1 | snow line, L=1, 170 K | **2.713 AU**; interior@2.5=T, @3.0=F | ±0.01 |
| P1 | snow-line L-scaling | L=4→**5.43**, L=0.1→**0.858** | ±0.01 |
| **P2** | 1 AU, Σ_p=10, C=2√3, M⊙ | M_iso=**0.0659 M⊕** (≈0.07) | ±0.001 |
| P2 | 5.2 AU, Σ_p=10 | M_iso=**9.27 M⊕** (≈9) | ±0.05 |
| **P3** | H/r=0.05, α=1e-3 | **25 M⊕** (bitsch); **20** (`--simple`) | ±0.1 |
| P3 | H/r=0.03, α=1e-3 | **5.4 M⊕** | ±0.05 |
| **P4** | `--hr 0.05 --nu-code 3.162e-6 --p-target 1.0` | threshold_q=**4.978e-4**, gap_mjup=**0.52**, p_at_thr=**1.000** | q ±3e-6 |
| P4 | criterion unit-check P(q=1e-3) | **0.699** | ±0.001 |
| **P5** | 30 AU, MMSN (Σ≈10.35, T≈51.1) | Q=**23.7** | ±0.5 |
| **P6** | fiducial | **12 M⊕** | exact |
| P6 | Ṁ=1e-7 / κ=0.1 | **6.75 M⊕** each | ±0.05 |

**P4 ν pin — use `--nu-code 3.162e-6` (=10⁻⁵·⁵), NOT `--alpha`.** α=1e-3 gives ν_code=2.5e-6 (10⁻⁵·⁶⁰²)
→ wrong R → different threshold. (`--alpha 1.265e-3` would be numerically equivalent but non-obvious — do
not use it for the pin.)

---

## 4. `query.py` wiring
`import core.formation as formation`. New banner + 6 `cmd_*` handlers (each just unpacks args → the
`compute_*` → `_out(...)`) + 6 `add_parser` blocks. `disk-model` uses `--r-au` and `--r-grid LO HI N`
(`nargs=3`, `type=float`); the rest per §2. Reuse the existing `_out()` (exit 1 on `{"error"}`, else 0;
argparse gives exit 2 for free).

## 5. Tests
- **`tests/test_formation.py`** — one `TestCase` per subcommand: the §3 anchors (`assertAlmostEqual` at the
  listed tolerances), `--r-grid` shape, P4's criterion unit-check, and the self-validating error matrix
  (each gate: missing input, duplicate-unit XOR violation, non-positive, `e ∉ [0,1)` where relevant).
  Dual-runner (`if __name__ == "__main__": unittest.main()`), numpy-free.
- **`tests/test_query_formation.py`** — subprocess happy-path + core-parity + exit-1(curated)/exit-2(argparse)
  matrix via `tests/_queryharness.py` (`run_query` / `run_query_inproc`), mirroring `test_query_gravitation.py`.

## 6. Build & verify order
1. equations.py constants → `core/formation.py` **P1 + P2** → wire in query.py → write P1/P2 tests →
   `venv/bin/python -m pytest tests/test_formation.py tests/test_query_formation.py`.
2. Add **P3–P6** → wire → extend both test files → run them, then the **full suite** for no regressions
   (`venv/bin/python -m pytest`).
3. `docs/integration.md` + `docs/testing.md` + `CLAUDE.md` lines.
4. Sister-repo ship updates (§0).

## 7. Decisions of record (frozen)
- **P4 headline** = solved marginal threshold at `--p-target` (default 1.0): 0.52 M_Jup at the reference
  case; `model_note` documents the q=1e-3 clear-gap cross-check. (followup-1 Ruling 1a.)
- **P4 ν** pinned via `--nu-code 3.162e-6`, not `--alpha`. (followup-1 Ruling 1.)
- **P1 snow line** = self-consistent own-T-profile solve, no `ice-lines` import; default 170 K → 2.71 AU,
  `∝ L^{1/2}`; `--snowline-au` / `--snowline-temp-k` override. (followup-1 Ruling 2 / Option A.)
- **Σ_solid default** emits the Z_⊙-scaled 22.8 g/cm² at 1 AU; the 10 g/cm² isolation convention is a
  lower MMSN variant recovered via `--z`/`--ice-factor`. (spec line 110.)
- **F1/F4 claim-map pins unchanged** — only the spec's P4 anchor *prose* was off, corrected in followup-1.
