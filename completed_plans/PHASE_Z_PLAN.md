# Phase Z — Rotating-Structure & Megastructure Scale (`spin-stress`, `tether-taper`, `dyson-collector`)

**Group H of the combined "settlement / propulsion / astrobiology / terraforming" request**
(Packet 17, Settlement / Megastructure). Three new **`query.py`-only**, **pure-math**,
self-validating calculators (the Phase-H/P contract) plus **one isolated bundled constant
table** — material densities + tensile strengths (and small body-gravity presets). Adds the
**structural** feasibility limit: `spin-comfort` (Phase W) sets the *minimum* habitat radius
(human comfort); the **material** sets the *maximum* — hoop stress in a spinning shell caps
size for a given tensile strength (why steel O'Neills top out at a few km and ringworlds need
unobtanium). `query.py` has no structural calc.

Specced in
`scifiWorldBuilding-Claude/research/query-api-methods/settlement-transformation-calculators-request.md`
(§Group H; status *Proposed*; the size/feasibility *envelope* — megastructure economics /
ring-shell dynamics / station-keeping defer to later packets). The **physics is durable** (hoop
stress `σ=ρv²`, taper `exp(∫ρg dh/σ)`); the material strengths are **present-day/near-term
ancestors, overridable** (MTA framing; nanomaterials flagged lab/extrapolated).

**Lineage:** identical structure to **Phase V/W** — a new core module + an isolated bundled data
table + granular subcommands + **no GUI** (one completion row in `docs/gui-architecture.md`,
query.py-only). No network *(except `dyson-collector --star`)*, no DB, no RNG, no time.
**Extends, does not replace** `spin-comfort` (H1's `r_max` is the ceiling to `spin-comfort`'s
comfort floor — cross-reference in the help). **Build after Phase Y, before AA/AB** (packet order).

---

## Resolved implementer decisions

Locked with the user 2026-07-01 (naming) + carried from the request:

1. **Phase letter → Z** (G→Y, H→Z, I→AA, J→AB).
2. **Home module → new `core/megastructure.py`** (`compute_spin_stress`, `compute_tether_taper`,
   `compute_dyson_collector`) **+ new `core/materials_tables.py`** (the material ρ/σ table + the
   body g/rotation presets + `_MODEL_NOTE`), mirroring `core/thermal.py` / `core/shielding_tables.py`.
3. **`dyson-collector --star` resolves via the query.py handler** (`_resolve_star_teff_lum` →
   SIMBAD + `regions.compute_star_system_regions_from_simbad`'s `bcLuminosity`, the same path
   `circumbinary-hz --star` uses) so SIMBAD stays out of the core; `--luminosity-lsun` is the
   offline path. This is the group's only networked entry. (The core takes `luminosity_lsun`
   directly and converts to watts with a local `_L_SUN_W = 3.828e26`.)
4. **Reuse `_STANDARD_GRAVITY`** from `equations` for the g-target → v_max → r_max chain.
5. **Output → JSON only** (parity with V/W/X); inputs echoed.

---

## 1. Files touched

| File | Change |
|---|---|
| `core/megastructure.py` *(new)* | The three `compute_*` functions. Imports `_STANDARD_GRAVITY` + `_M_PER_AU` from `equations` (+ a local `_L_SUN_W`); the tables from `materials_tables`. The `--star`→luminosity resolution lives in the query.py handler, not the core. |
| `core/materials_tables.py` *(new)* | `_MATERIALS` (ρ kg/m³ + σ_tensile MPa per material, with brittle/nanomaterial flags) + `_BODIES` (surface g + geo/rotation params for the tether presets) + `_MODEL_NOTE`/`_SOURCES`. Isolated like `shielding_tables.py`. |
| `query.py` | `import core.megastructure as megastructure`; three `cmd_*` handlers + three `add_parser(...)` blocks. |
| `tests/test_megastructure.py` *(new)* | In-process core tests: acceptance anchors, all H1 solve forms, taper feasibility bands, Dyson area/mass, validation matrix, table integrity, determinism. |
| `tests/test_query_megastructure.py` *(new)* | Subprocess contract: happy-path JSON + core parity + exit-code matrix. |
| `docs/integration.md` | New "Megastructure scale (Phase Z)" section + three quick-ref rows; units on every field. |
| `docs/gui-architecture.md` | One Phase-Z completion-status row (query.py-only). |
| `CLAUDE.md` | Phase-Z test bullet + `core/megastructure.py` / `core/materials_tables.py` in the `core/` list. |

---

## 2. Bundled data — `core/materials_tables.py` (RESEARCHED 2026-07-02 — values locked)

Confirmed via WebSearch against materials databases / the space-elevator literature (see §9 for
the sources). `σ/ρ` is the sole figure of merit (flows straight into `v_max=√(σ/ρ)`); the two
anchor-pinned rows (steel, carbon-fiber) reproduce the H1 acceptance anchors exactly. Locked
values:

```python
# ρ kg/m³, σ_tensile MPa. specific strength σ/ρ is the sole figure of merit (thin-shell).
_MATERIALS = {
    "structural-steel":   {"rho": 7850, "sigma_mpa": 400,    "flag": None},   # UTS 300–900; 400 = typical structural (anchor-pinned)
    "titanium-alloy":     {"rho": 4430, "sigma_mpa": 950,    "flag": None},   # Ti-6Al-4V, UTS ~900–1000
    "aluminium-alloy":    {"rho": 2700, "sigma_mpa": 500,    "flag": None},   # 7075-class high-strength (Al alloys 60–570)
    "carbon-fiber":       {"rho": 1600, "sigma_mpa": 4000,   "flag": "RAW FILAMENT (T700-class ~4900 MPa); resin-matrix laminate is far lower ~600–1500"},  # anchor-pinned
    "kevlar":             {"rho": 1440, "sigma_mpa": 3600,   "flag": None},   # Kevlar 49 ~3620 MPa
    "uhmwpe":             {"rho": 970,  "sigma_mpa": 2700,   "flag": None},   # Dyneema/Spectra fiber ~2700–3400
    "basalt-fiber":       {"rho": 2700, "sigma_mpa": 4100,   "flag": None},   # continuous basalt fiber 3000–4840 (source 4849/2750)
    "silicon-carbide":    {"rho": 3200, "sigma_mpa": 400,    "flag": "BRITTLE: compressive (~2500 MPa) >> tensile (~350–400)"},
    "cnt-theoretical":    {"rho": 1350, "sigma_mpa": 100000, "flag": "theoretical intrinsic 100–200 GPa (armchair ~120/zigzag ~94); single-tube measured ~63, defect-free bundles >80 (Nature Nanotech 2018); BULK yarns ~1–8 GPa — FAR lower. MTA/extrapolated"},
    "graphene-theoretical":{"rho": 2200,"sigma_mpa": 130000, "flag": "measured intrinsic ~130 GPa (Lee et al. Science 2008); theoretical 100–150 GPa; BULK far lower. MTA/extrapolated"},
}
_BODIES = {  # R = mean surface radius (km); Rs = synchronous-orbit radius from center (km);
             # g0 = surface gravity (m/s²); rot_h = rotation period (h). See §3 for the taper form.
    "earth": {"R_km": 6371, "Rs_km": 42164, "g0": 9.81, "rot_h": 23.934},
    "mars":  {"R_km": 3390, "Rs_km": 20428, "g0": 3.71, "rot_h": 24.623},
    "ceres": {"R_km": 473,  "Rs_km": 1192,  "g0": 0.28, "rot_h": 9.074},
    "moon":  {"R_km": 1737, "Rs_km": 88400, "g0": 1.62, "rot_h": 655.7,  # 27.32 d
              "note": "naive lunar-synchronous radius (~88 400 km) lies beyond the Hill sphere / near Earth-Moon L1; a real lunar elevator is the Pearson L1/L2 form, not this simple synchronous taper. Reported with a caveat."},
}
```

**Deviations from the plan's first-draft provisional values (research-driven, 2026-07-02):**
- **`cnt-theoretical` σ 50 → 100 GPa** and **`graphene-theoretical` ρ 1350 → 2200, σ 50 → 130 GPa** —
  the keys are named `-theoretical`, so the bundled value is now the literature *theoretical /
  measured-intrinsic* strength (CNT 100–200 GPa; graphene ~130 GPa, Lee 2008), not the request's
  conservative 50 GPa. Both are hard-flagged that **bulk macroscopic material is 1–2 orders of
  magnitude weaker**. (This is what makes the taper anchor land — CNT@100 GPa → taper ≈ 1.9, the
  canonical "modest taper, excellent material" result; see §3.) Overridable via `--tensile-strength-mpa`.
- **`carbon-fiber` clarified as RAW FILAMENT** (T700-class ~4900 MPa), not a resin-matrix laminate
  (~600–1500). Value unchanged (anchor-pinned at 4000); the flag now states the distinction so a
  reader doesn't confuse the fiber figure of merit with a buildable laminate.
- `basalt-fiber` source added (4849 MPa / 2750 kg/m³; bundled 4100/2700 as a representative mid-grade).

A `test_megastructure.py` golden test pins `_MATERIALS` + `_BODIES` (drift guard, like Phase V's
`test_nist_pinned_grid`).

---

## 3. Formulas

`g₀` = `_STANDARD_GRAVITY`; SF = safety factor; σ_allow = σ_tensile/SF.

**H1 spin-stress.** Hoop stress of a thin spinning shell `σ = ρ·v²` (v = rim tangential velocity).
Max velocity `v_max = √(σ_allow/ρ)`. Since `v = √(a·r)`: **max radius at target gravity**
`r_max = v_max²/a`; **max gravity at a fixed radius** `a_max = v_max²/r`. From rpm+radius:
`v = (rpm·2π/60)·r`, `σ = ρv²`, margin `= σ_allow/σ`. Specific strength `σ/ρ` is the sole figure
of merit (thickness cancels for a thin shell — note this).

**H2 tether-taper.** The **Pearson (1975) uniform-constant-stress** taper ratio (area at the
synchronous orbit / area at the surface), RESEARCHED + validated 2026-07-02:

```
T = exp[ (ρ/σ_allow) · ( g₀·R·(1 − R/R_s) − (ω²/2)·(R_s² − R²) ) ]
```

with `R` = surface radius, `R_s` = synchronous-orbit radius (from centre), `ω = 2π/rot_period`,
`g₀` = surface gravity (all from `_BODIES`, or accept `--surface-gravity-ms2` + `--geo-radius-km`
+ `--rotation-h`). Equivalent to the sourced `T = exp(K/L_c)` with the characteristic (breaking)
length `L_c = σ_allow/(ρ·g₀)` and `K = R(1−R/R_s) − (ω²/2g₀)(R_s²−R²)`; characteristic velocity
`v_c = √(σ_allow/ρ)`. **Overflow guard:** when the exponent exceeds ~700, `taper_ratio` is
reported as `infinity`/`null` with `feasible=False` (the material can't span the well — e.g.
steel on Earth, exponent ≈ 950). **Validated:** Earth steel → impossible (∞); Earth CNT@100 GPa →
**taper ≈ 1.9** (the canonical "modest taper ratio, excellent material" result); graphene@130 GPa
→ ≈ 2.3; kevlar/carbon-fiber → ~10⁸ (impractical). Feasibility band:
taper ≲2 practical, ≫10 impractical.

**H3 dyson-collector.** Intercepted power `P = f·L_star`; collector area at orbit R to intercept
fraction f `A = f·4πR²`; mass `= A·areal_mass`; incident flux `= L/(4πR²)`. L from
`--luminosity-lsun` (× `_L_SUN_W`) or, via `--star`, the handler's SIMBAD + regions resolver.

---

## 4. Signatures, output shapes, validation

**`compute_spin_stress(material=None, density_kgm3=None, tensile_strength_mpa=None,
safety_factor=3.0, target_gravity_g=None, radius_m=None, rpm=None)`**
- Material from `--material` (table) **or** explicit ρ+σ. One solve form: `target_gravity_g`
  (→r_max), `radius_m` alone (→a_max), or `rpm`+`radius_m` (→hoop stress + margin).
- **Out (as-built):** `{material, density_kgm3, tensile_strength_mpa, safety_factor,
  allowable_stress_mpa, max_tangential_velocity_ms, target_gravity_g, radius_m, rpm,
  max_radius_m|null, max_radius_km|null, max_gravity_g|null, hoop_stress_mpa|null, margin|null,
  specific_strength_note, notes, model_note}` (echoed inputs + the non-active-form keys `null`).
- **Validation:** unknown `--material`; ρ or σ ≤ 0; SF < 1; target_gravity/radius/rpm ≤ 0; not
  exactly one solve form (or material *and* explicit ρ/σ both/neither given).
- **Anchors:** steel SF1 target-g1 → v_max≈226 m/s, r_max≈5.2 km; carbon-fiber → v_max≈1580 m/s,
  r_max≈254 km.

**`compute_tether_taper(material=None, density_kgm3=None, tensile_strength_mpa=None,
safety_factor=3.0, body=None, surface_gravity_ms2=None, surface_radius_km=None,
geo_radius_km=None)`** — the explicit body path needs **`--surface-radius-km`** too (the well depth
depends on both surface and synchronous radius); a minor addition to the request's `g0+geo-radius`.
- **Out (as-built):** `{material, density_kgm3, tensile_strength_mpa, safety_factor, body,
  surface_gravity_ms2, surface_radius_km, geo_radius_km, characteristic_velocity_ms,
  characteristic_length_km, taper_ratio|null, feasible, notes, model_note}` (`taper_ratio` is
  `null` on overflow → `feasible:false`).
- **Validation:** material/ρ+σ as H1; not exactly one body source (`--body` xor
  `g0`+`surface-radius`+`geo-radius`); SF<1; non-positive g/R/R_s; `geo_radius ≤ surface_radius`.

**`compute_dyson_collector(luminosity_lsun=None, fraction=None, orbit_au=None,
areal_mass_kgm2=0.01)`** — the `--star` → luminosity resolution lives in the **query.py handler**
(reuses `_resolve_star_teff_lum`, SIMBAD stays out of the core, like `circumbinary-hz`), so the
core takes `luminosity_lsun` directly.
- **Out (as-built):** `{intercepted_power_w, collector_area_m2, collector_area_au2,
  collector_mass_kg, incident_flux_wm2, fraction, orbit_au, luminosity_lsun, areal_mass_kgm2,
  model_note}`.
- **Validation:** `luminosity_lsun` ≤ 0; fraction∉(0,1]; orbit_au ≤ 0; areal_mass ≤ 0. The handler's
  `--luminosity-lsun`/`--star` mutex + a SIMBAD failure surface as argparse exit 2 / `{"error"}`.
- **Anchor:** Sun, f0.01, orbit1 → intercepted≈3.8e24 W, area≈2.8e21 m².

---

## 5. `query.py` wiring (modeled on the `shielding-attenuation`/`radiator-area` blocks)

Three `add_parser` blocks. `spin-stress`: `--material` (`choices` from `_MATERIALS`) /
`--density-kgm3`+`--tensile-strength-mpa`; `--safety-factor` `default=3`; `--target-gravity-g`,
`--radius-m`, `--rpm` (the "one solve form" check is in the core). `tether-taper`: material
inputs; `--body` (`choices`) / `--surface-gravity-ms2`+`--geo-radius-km`; `--safety-factor`.
`dyson-collector`: `--luminosity-lsun`/`--star`; `--fraction`, `--orbit-au` required; `--areal-mass-kgm2`
`default=0.01`. `cmd_*` handlers pass `--material`/`--body` keys into the core (like
`shielding-attenuation` passes `--material`).

---

## 6. Validation contract (self-validating, Phase-H/P)

- **Core `{"error"}` exit 1:** all §4 range/anchor-count/unknown-key checks; a SIMBAD failure on
  `dyson-collector --star`.
- **Argparse exit 2:** a bad `--material`/`--body` choice; any non-numeric value.

---

## 7. Tests

**`tests/test_megastructure.py`** (in-process):
- Every §4 acceptance anchor (steel/carbon-fiber r_max; Sun Dyson area).
- **H1 solve forms:** target-g→r_max, radius→a_max, rpm+radius→hoop stress+margin (all three);
  explicit ρ/σ path == the matching `--material`.
- **H2:** taper ratio + feasibility band on a practical (composite) and an impractical (steel,
  Earth) case.
- **H3:** area/mass/flux consistent; `--luminosity-lsun` path (offline).
- **Validation matrix:** unknown material, ρ=0, SF=0.5, two solve forms, material+explicit-ρ both,
  fraction=1.5, orbit=0.
- **Table integrity:** golden-pin `_MATERIALS`. **Determinism:** deep-equal on repeat.

**`tests/test_query_megastructure.py`** (subprocess, mirrors `test_query_thermal.py`):
- Happy-path JSON + core parity for `spin-stress` (steel target-g) + `tether-taper` +
  `dyson-collector --luminosity-lsun 1`.
- Exit-code matrix: exit-1 (`--safety-factor 0.5`, unknown material, `--fraction 1.5`); exit-2
  (bad `--material`, bad `--body`, non-numeric `--radius-m`).

---

## 8. Success criteria

- Reproduces every §4 acceptance anchor numerically (steel = km-scale, composite = 100-km-scale).
- H1 all three solve forms determinate; specific-strength note present.
- Material table bundled + golden-pinned; SiC brittle + nanomaterials lab/MTA flagged in-band.
- `dyson-collector --star` resolves luminosity via the handler's SIMBAD + regions path
  (`_resolve_star_teff_lum`); the offline `--luminosity-lsun` path works standalone.
- Validation matrix passes (core exit-1 / argparse exit-2 split per §6).
- Documented in `docs/integration.md` with **units on every field**; one `gui-architecture.md`
  completion row; one `CLAUDE.md` bullet.
- On shipment: flip Group H in the request file to `Deprecated — FULFILLED`, record the as-built
  material table values used (the flagged deviation point).

---

## 9. Open items / risks — RESEARCHED 2026-07-02 (both resolved)

1. **Material ρ/σ table — DONE.** Confirmed against materials databases + the nanomaterial/basalt
   literature (§References). All 10 rows locked in §2; the two anchor-pinned rows (steel, carbon-fiber)
   reproduce the H1 anchors; nanomaterials use literature theoretical values (CNT 100 GPa, graphene
   130 GPa) hard-flagged that bulk material is 1–2 orders weaker. Deviations from the first draft
   documented in §2.
2. **Tether-taper closed form — DONE.** The Pearson uniform-constant-stress form is locked in §3 and
   **validated** (Earth steel → impossible; Earth CNT@100 GPa → taper ≈ 1.9, the canonical result;
   graphene ≈ 2.3). `_BODIES` constants for earth/mars/ceres set; the Moon carries a caveat (its
   naive synchronous radius is beyond the Hill sphere — a real lunar elevator is the L1/L2 form).
3. Everything else is `σ=ρv²` + `A=f·4πR²` over verified constants. **Ready to build** — no
   remaining research. ~1 focused session.

## References (researched 2026-07-02; none a load-bearing canon claim)
- **Hoop stress** `σ=ρv²` (mechanics of materials); **Dyson collector** `A=f·4πR²` (standard geometry).
- **Materials:** metal-strength charts (steel UTS 300–900, Ti-alloy ~950–1400, Al-alloy ~500) &
  material-density references (steel 7850 / Al 2700); Kevlar 49 ~3620 MPa / 1440; basalt fiber
  ~4849 MPa / 2750 (ScienceDirect 2023); CNT single-tube ~63 GPa & defect-free bundles >80 GPa
  (Bai et al., *Nature Nanotechnology* 2018), theoretical 100–200 GPa; graphene intrinsic ~130 GPa
  (Lee, Wei, Kysar & Hone, *Science* 2008). Material strengths are present-day ancestors, MTA-movable;
  nanomaterials flagged lab/extrapolated (bulk far weaker).
- **Space-elevator taper:** the Pearson (1975) uniform-constant-stress closed form
  `T = exp(K/L_c)`, `L_c = σ/(ρg)` (Aravind, *The Physics of the Space Elevator*, Am. J. Phys. 2007;
  ISEC / space-elevator literature). Body constants (synchronous radii, rotation) are standard
  astronomical values.
