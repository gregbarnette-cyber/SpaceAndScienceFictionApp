# Phase Y — STL Mission Energetics (`rocket-equation`, `beam-sail`)

**Group G of the combined "settlement / propulsion / astrobiology / terraforming" request**
(Packet 16, STL Colonization Propulsion). Two new **`query.py`-only**, **pure-math**,
self-validating calculators (the Phase-H/P contract) plus **one isolated bundled constant
table** — ideal fuel exhaust velocities. Adds the **mass/energy** side of sub-light travel:
`query.py` today has only *kinematics* (`brachistochrone-*`, `distance-at-acceleration`,
`travel-time-custom-thrust` — distance/time/velocity given an acceleration) and **no rocket
equation, mass ratio, or beam/sail energetics**. Energetics = "can you carry the fuel";
kinematics = "how long is the trip" — the two complement each other.

Specced in
`scifiWorldBuilding-Claude/research/query-api-methods/settlement-transformation-calculators-request.md`
(§Group G; status *Proposed*; the STL scoping *envelope* — full propulsion taxonomy defers to
Pkt 25). The **physics is durable** (Tsiolkovsky, the relativistic rocket equation); the
bundled fuel exhaust velocities are **present-day ideal ancestors, overridable** (the
Mature-Technology-Assumption framing).

**Lineage:** identical structure to **Phase V (thermal)** / **Phase W (`spin-comfort`)** — a
new core module + an isolated bundled data table + granular subcommands + **no GUI** (one
completion row in `docs/gui-architecture.md`, query.py-only). No network, no DB, no RNG, no
time. **Extends, does not replace** the `brachistochrone-*` kinematics (cross-reference them in
the help). **First of the four groups — build before Z / AA / AB** (Packet 16 is next).

---

## Resolved implementer decisions

Locked with the user 2026-07-01 (naming) + carried from the request:

1. **Phase letter → Y** (G→Y, H→Z, I→AA, J→AB — two-letter continuation past Z).
2. **Home module → new `core/propulsion.py`** (`compute_rocket_equation`, `compute_beam_sail`)
   **+ new `core/propulsion_tables.py`** (the ideal-`v_e` fuel presets + provenance/`model_note`
   strings), mirroring the `core/thermal.py` / `core/shielding_tables.py` split.
3. **`_C_MS` (speed of light) → promote from `core/calculators.py` into `core/equations.py`**
   (with `_STEFAN_BOLTZMANN`, `_STANDARD_GRAVITY`, `_G`) so G (relativistic rocket) and Phase AA
   (Planck) share one constant. `calculators.py` re-imports it from `equations` (verify no
   import cycle — `equations.py` must not import `calculators`; it currently does not).
   *(Fallback if any cycle surfaces: define `_C_MS` locally in `propulsion.py`.)*
4. **Regime selection → the velocity anchor's form.** `--delta-v-kms` → classical branch;
   `--beta` (final v/c) → relativistic branch. `--relativistic` is accepted for explicitness and
   documented to auto-engage when β>0.01 (below that the two forms agree to <1%). This keeps the
   frame-dependent Δv out of the relativistic mass-ratio math (which is defined against β).
5. **Output → JSON only** (parity with V/W/X); anchors echoed.

---

## 1. Files touched

| File | Change |
|---|---|
| `core/equations.py` | **Move** `_C_MS = 299_792_458.0` here (from `calculators.py`); add a one-line comment. Nothing else. |
| `core/calculators.py` | Replace the local `_C_MS = …` with `from core.equations import _C_MS` (re-export); all existing references unchanged. |
| `core/propulsion.py` *(new)* | `compute_rocket_equation(...)`, `compute_beam_sail(...)`. Imports `_C_MS`, `_STANDARD_GRAVITY` from `equations`; fuel presets from `propulsion_tables`. |
| `core/propulsion_tables.py` *(new)* | `_FUELS` (ideal `v_e` per fuel + per-fuel note) + `_MODEL_NOTE`/`_SOURCES` provenance strings. Isolated like `shielding_tables.py`. |
| `query.py` | `import core.propulsion as propulsion`; `cmd_rocket_equation` + `cmd_beam_sail` handlers; two `add_parser(...)` blocks. |
| `tests/test_propulsion.py` *(new)* | In-process core tests: acceptance anchors, all two-of-three solves, legs, fuel presets, validation matrix, table integrity, determinism. |
| `tests/test_query_propulsion.py` *(new)* | Subprocess contract: happy-path JSON + core parity + exit-code matrix. |
| `docs/integration.md` | New "STL mission energetics (Phase Y)" section + two quick-ref rows; units on every field. |
| `docs/gui-architecture.md` | One Phase-Y completion-status row (query.py-only). |
| `CLAUDE.md` | Phase-Y test bullet + `core/propulsion.py` / `core/propulsion_tables.py` in the `core/` list. |

---

## 2. Bundled data — `core/propulsion_tables.py` (ideal exhaust velocities; verify at build)

Every value is the **ideal** exhaust velocity — real drives reach a fraction — and is flagged
present-day/MTA-movable. **Verify each against a nuclear/astronautics reference at build**
(the most likely deviation point; see the request open items).

```python
# ideal exhaust velocity, km/s. Marked ideal — real drives are a fraction; MTA-movable.
_FUELS = {
    "chemical":         {"v_e_kms": 4.4,       "note": "chemical (H2/O2 ideal); real ~4.4 km/s"},
    "fission-thermal":  {"v_e_kms": 9.0,       "note": "solid-core NTR ideal ~9 km/s; ideal fission-FRAGMENT far higher"},
    "fusion-dt":        {"v_e_kms": 0.03*_C_KMS,"note": "D-T fusion; bundled at effective v_e≈0.03c (the acceptance anchor). Ideal band ~0.05-0.09c, but realistic burn/directionality losses drop the effective value — see below."},
    "fusion-catalyzed": {"v_e_kms": 0.12*_C_KMS,"note": "advanced/catalyzed fusion, higher burn fraction — extrapolated"},
    "antimatter":       {"v_e_kms": 0.30*_C_KMS,"note": "antimatter-heated exhaust up to ~0.3c+; ideal, MTA"},
}
```

`fusion-dt` is set to **0.03c ≈ 8 994 km/s** so the "generation ship is marginal" acceptance
anchor reproduces (MR≈28 flyby / ~800 rendezvous at β 0.1 — verified: 0.05c gives only MR≈7.4,
so the request's own "v_e≈0.03c" anchor parenthetical is authoritative over its looser
"~0.05–0.09c ideal" prose). The per-fuel note records the tension. A
`test_propulsion.py` golden test pins `_FUELS` to these literals (drift guard, like Phase V's
`test_nist_pinned_grid`).

---

## 3. Formulas

`c` = `_C_MS`; `g₀` = `_STANDARD_GRAVITY`; `MR` = wet/dry mass ratio for **one** burn (flyby).

**Classical (Tsiolkovsky):** `MR = exp(Δv / v_e)`; inverse `v_e = Δv / ln(MR)`, `Δv = v_e·ln(MR)`.
**Relativistic (constant `v_e`, final `β`):** `MR = exp((c/v_e)·atanh(β))`; photon rocket
(`v_e=c`): `MR = √((1+β)/(1−β))`; inverse `β = tanh((v_e/c)·ln(MR))`.
**Specific impulse:** `v_e = isp·g₀`.
**Legs multiplier** on `MR` (a single-burn value): flyby → `MR`; rendezvous (accel+decel) →
`MR²`; round-trip → `MR⁴`. `propellant_fraction = 1 − 1/MR_total`.
**Mass budget (optional):** with `payload_mass_t` + `structure_fraction s`:
dry = payload/(1−s)? — **v1 simplification:** treat payload as the dry mass, `wet = payload·MR_total`,
`propellant = wet − payload`; `structure_fraction` echoed as a note only (full structural
staging defers to Pkt 25). *(Confirm this simplification at build; document in `model_note`.)*

**Beam-sail (G2):** reflective thrust `F = 2·P·R/c` (absorptive `F = P·R/c` as R→0, R =
reflectivity); `a = F/m`, `m = sail_mass + payload_mass`, sail_mass from `areal_mass_gm2·area`
or explicit. Optional final velocity: over `accel_distance` → `v = √(2·a·d)`; over `accel_time`
→ `v = a·t` (non-relativistic first order; note the cap). Diffraction beam-range note:
spot size ≈ `λ·range/aperture` — report the range at which the spot exceeds the sail.

---

## 4. `rocket-equation` — signature, shape, validation

`compute_rocket_equation(delta_v_kms=None, beta=None, exhaust_velocity_kms=None, isp_s=None,
fuel=None, mass_ratio=None, relativistic=None, legs="flyby", payload_mass_t=None,
structure_fraction=None)`

- **Anchor resolution — exactly two of the three groups** {velocity: Δv|β}, {exhaust:
  v_e|isp|fuel}, {mass_ratio}. Resolve the missing third. Regime from the velocity form (§dec 4).
- **Out:** `{mass_ratio (total, incl. legs), mass_ratio_single_burn, propellant_fraction,
  delta_v_kms, beta, exhaust_velocity_kms, isp_s, fuel, legs, relativistic, payload_mass_t|null,
  propellant_mass_t|null, wet_mass_t|null, structure_fraction, model_note}`.
- **Validation (curated exit-1):** wrong count of anchors (not exactly two groups; or >1 form
  within the exhaust group); β∉[0,1); non-positive Δv/v_e/isp/mass_ratio/payload; mass_ratio<1;
  `structure_fraction`∉[0,1); unknown `--fuel`.
- **Anchors:** Δv30/v_e30→MR≈2.718, frac≈0.632. β0.1/v_e0.1c→MR≈2.73 flyby, ≈7.4 rendezvous.
  β0.1/`fuel fusion-dt`→MR≈28 flyby, ~800 rendezvous. β0.1/photon(v_e=c)→MR≈1.105.

## 4b. `beam-sail` — signature, shape, validation

`compute_beam_sail(beam_power_w, sail_area_m2=None, areal_mass_gm2=None, sail_mass_kg=None,
payload_mass_kg=0.0, reflectivity=0.9, wavelength_nm=None, transmit_aperture_m=None,
accel_distance_au=None, accel_time_days=None)`

- Sail mass from `areal_mass_gm2·sail_area_m2` (needs area) or explicit `sail_mass_kg`.
- **Out:** `{thrust_n, acceleration_ms2, final_velocity_kms|null, beta|null, beam_energy_j|null,
  sail_area_m2, total_mass_kg, sail_mass_kg, payload_mass_kg, reflectivity, beam_range_note, model_note}`.
- **Validation (curated exit-1):** non-positive beam_power/area/mass; reflectivity∉[0,1]; both
  `accel_distance` and `accel_time` given; `wavelength_nm` xor `transmit_aperture_m` (need both
  for the range note or neither).
- **Anchor:** P=100 GW, reflective → F≈667 N (`2·1e11/3e8`).

---

## 5. `query.py` wiring (modeled on the `waste-heat` block)

Two `add_parser` blocks. `rocket-equation`: `--delta-v-kms`/`--beta` (both optional floats — the
"exactly two" check is in the core, curated exit-1); an exhaust mutex group holding
`--exhaust-velocity-kms`/`--isp-s`/`--fuel` (`--fuel` `choices` from `_FUELS`); `--mass-ratio`;
`--relativistic` store-true; `--legs` `choices=[flyby,rendezvous,round-trip]` `default=flyby`;
`--payload-mass-t`, `--structure-fraction`. `beam-sail`: `--beam-power-w` required; the rest per
§4b; `accel-distance`/`accel-time` as a (non-required) mutex group. `cmd_*` handlers convert
`--fuel`→v_e in the handler (or pass the fuel key to the core — implementer's call; keep parity
with how `shielding-attenuation` passes `--material` into the core).

---

## 6. Validation contract (self-validating, Phase-H/P)

- **Core `{"error"}` exit 1:** the per-subcommand ranges in §4/§4b (anchor counts, β/reflectivity
  ranges, non-positive quantities, mass_ratio<1, unknown fuel).
- **Argparse exit 2:** a bad `--fuel`/`--legs` choice; both members of a mutex group; any
  non-numeric value. *(The "exactly two anchors" rule is a **core** check → exit 1, not exit 2 —
  the four velocity/exhaust/MR flags are all argparse-optional, like `spin-comfort`'s anchors.)*

---

## 7. Tests

**`tests/test_propulsion.py`** (in-process):
- Every §4/§4b acceptance anchor (classical, relativistic flyby/rendezvous, fusion, photon,
  beam-sail thrust).
- **All two-of-three solves:** (Δv,v_e)→MR, (Δv,MR)→v_e, (v_e,MR)→Δv; and the β equivalents.
- **Legs:** rendezvous = flyby MR²; round-trip = flyby MR⁴ (same base MR).
- **Fuel presets:** `--fuel` resolves the table v_e; golden-pin `_FUELS`.
- **Mass budget:** payload+MR → wet/propellant consistent (`propellant = wet − payload`).
- **Validation matrix:** each `{"error"}` path in §4/§4b (β=1, β=1.2, MR=0.5, one anchor, all
  three anchors, unknown fuel, reflectivity=1.5, both accel modes).
- **Determinism:** same inputs twice → deep-equal.

**`tests/test_query_propulsion.py`** (subprocess, mirrors `test_query_thermal.py`):
- Happy-path JSON + core parity for `rocket-equation` (classical + `--fuel fusion-dt --legs
  rendezvous`) and `beam-sail`.
- Exit-code matrix: exit-1 curated `{"error"}` (β 1.0, one anchor, unknown fuel); exit-2 argparse
  (bad `--legs`, bad `--fuel`, non-numeric `--beta`).

---

## 8. Success criteria

- Reproduces every §4/§4b acceptance anchor numerically.
- Two-of-three anchor resolution determinate for all valid pairs; regime selected by velocity form.
- `legs` squares/4th-powers the single-burn MR correctly; propellant fraction consistent.
- Fuel presets bundled + golden-pinned; each flagged ideal/MTA in the `model_note`.
- Validation matrix passes (core exit-1 / argparse exit-2 split per §6).
- Documented in `docs/integration.md` with **units on every field**; one `gui-architecture.md`
  completion row; one `CLAUDE.md` bullet.
- On shipment: flip Group G in the request file to `Deprecated — FULFILLED`, record the as-built
  per-key shapes + the fuel-preset values used + the payload/structure v1 simplification.

---

## 9. Open items / risks (verify at build)

1. **Fuel `v_e` values** — the one load-bearing verification; `fusion-dt` is bundled at **0.03c**
   (as-built) to reproduce the "marginal generation ship" anchor (MR≈28 flyby). The request's
   looser "~0.05–0.09c ideal" prose is in tension with its own 0.03c anchor — flag to the
   requester on shipment. Confirm against a nuclear/fusion reference.
2. **`_C_MS` promotion** — grep-confirm `equations.py` doesn't import `calculators` before moving.
3. **Payload/structure mass model** — v1 treats payload as dry mass; full staging is Pkt 25.
   Document the simplification; don't over-build.

Everything else is closed-form (Tsiolkovsky + F=2P/c) over verified constants. ~1 focused session.

## References (verify at implementation; none a load-bearing canon claim)
Tsiolkovsky & the relativistic rocket equation (any astronautics text; relativistic form
`MR = [(1+β)/(1−β)]^(c/2v_e)` = `exp((c/v_e)·atanh β)`); fuel specific energies
(nuclear/fusion/antimatter references — the values are ideal and MTA-movable).
