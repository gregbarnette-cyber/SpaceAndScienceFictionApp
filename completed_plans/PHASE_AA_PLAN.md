# Phase AA — PAR / Photosynthesis by Stellar Type (`par-flux`)

**Group I of the combined "settlement / propulsion / astrobiology / terraforming" request**
(Packet 18, Astrobiology / Planetary Protection). One new **`query.py`-only**, **pure-math**,
self-validating calculator (the Phase-H/P contract). **No bundled table** — the one physical
constant it needs beyond `_C_MS` is Planck's constant (added to `core/equations.py`). Answers
the *natural-light* / native-photosynthesis question: PAR (photosynthetically active radiation,
~400–700 nm) is a *fraction* of a star's output that shifts by spectral type — G ≈ 0.4, but
K/M shift redward so far fewer usable PAR photons reach a leaf per W/m² of insolation (the
red-dwarf photosynthesis-deficit question Pkt 18 owns). **This is the PAR piece fenced out of
the Phase-X `bioregen-area` tool** — its PPFD output **feeds back** into `bioregen-area`, which
takes PAR as a caller-supplied input.

Specced in
`scifiWorldBuilding-Claude/research/query-api-methods/settlement-transformation-calculators-request.md`
(§Group I; status *Proposed*; the **lowest-urgency group** — one tool in an otherwise-qualitative
packet — but with clean synergy to Phase X). The **physics is durable** (the Planck function +
PAR-band integration); the **blackbody SED is an explicit approximation** (real stellar SEDs,
esp. M-dwarf line blanketing, deviate — real-spectrum refinement is a v2 note).

**Lineage:** Phase V/W/X — a new core module + one granular subcommand + **no GUI** (one
completion row in `docs/gui-architecture.md`, query.py-only). No DB, no RNG, no time; **network
only** on the `--star` Teff-resolution path. **Complements** `star-luminosity` /
the detection tools and **feeds** `bioregen-area`. **Build after Phase Y/Z, before AB** (packet
order — Group I is low-urgency but sits before J).

---

## Resolved implementer decisions

Locked with the user 2026-07-01 (naming) + carried from the request:

1. **Phase letter → AA** (G→Y, H→Z, I→AA, J→AB).
2. **Home module → new `core/par_flux.py`** (`compute_par_flux`). No bundled table (unlike Y/Z) —
   the SED is computed from the Planck function; the only new constant is `_PLANCK_H`.
3. **SED model → blackbody at Teff, flagged as an approximation** in `sed_model`/`model_note`.
   Real-spectrum (PHOENIX / BT-Settl) SEDs are a v2 note, out of scope here.
4. **Teff sources:** `--teff-k` (offline) / `--spectral-type` (→ `science.compute_main_sequence_table`,
   offline local DB) / `--star` (→ SIMBAD, the only networked path).
5. **Output → JSON only** (parity with V/W/X); `feeds_note` explicitly points PPFD at
   `bioregen-area`'s PAR input.

---

## 1. Files touched

| File | Change |
|---|---|
| `core/equations.py` | **+2 constants:** `_PLANCK_H = 6.62607015e-34` (J·s) and `_AVOGADRO = 6.02214076e23` (mol⁻¹) in the constants block, for the PPFD photon-count conversion. `_C_MS` promoted here in Phase Y is reused. `_K_B` (present) is the Boltzmann constant for the Planck curve. |
| `core/par_flux.py` *(new)* | `compute_par_flux(...)` — numeric Planck-band integration → f_PAR, PAR irradiance, PPFD, G2 deficit. Imports `_PLANCK_H`, `_C_MS`, `_K_B`, `_AVOGADRO`, `_STEFAN_BOLTZMANN` from `equations`; `compute_main_sequence_table` / SIMBAD for Teff resolution. |
| `query.py` | `import core.par_flux as par_flux`; one `cmd_par_flux` handler + one `add_parser(...)` block. |
| `tests/test_par_flux.py` *(new)* | In-process core tests: acceptance anchors (Sun/M-dwarf f_PAR + deficit + PPFD), Teff-source paths, band override, PPFD cross-check, validation matrix, determinism. |
| `tests/test_query_par_flux.py` *(new)* | Subprocess contract: happy-path JSON + core parity + exit-code matrix (SIMBAD path reachability-gated). |
| `docs/integration.md` | New "PAR / photosynthesis (Phase AA)" section + one quick-ref row; units on every field; the `feeds → bioregen-area` cross-reference. |
| `docs/gui-architecture.md` | One Phase-AA completion-status row (query.py-only). |
| `CLAUDE.md` | Phase-AA test bullet + `core/par_flux.py` in the `core/` list. |

---

## 2. Formulas

Spectral radiance (per wavelength) `B_λ(T) = (2hc²/λ⁵) · 1/(exp(hc/λk_BT) − 1)`.

- **PAR fraction:** `f_PAR = ∫_{400}^{700 nm} B_λ dλ / ∫_0^∞ B_λ dλ`. Numerator by numeric
  integration over 400–700 nm; denominator = `σT⁴/π` (Stefan–Boltzmann closes the total, avoiding
  an unbounded integral). Both are per-steradian energy — the ratio cancels geometry.
- **PAR irradiance:** `par_irradiance_wm2 = S · f_PAR` (S = total insolation W/m²).
- **PPFD** [µmol photons/m²/s]: the in-band **photon** flux. Photon count ∝ `∫_{400}^{700}
  B_λ·(λ/hc) dλ` (each photon carries `hc/λ`, so energy→count divides by it). Convert the band
  energy `par_irradiance_wm2` to a photon rate via the **band-mean photon energy**
  `Ē_photon = (∫B_λ dλ)/(∫B_λ·λ/hc dλ)`, then `PPFD = par_irradiance / Ē_photon / _AVOGADRO ·1e6`.
  Cross-check against the standard PAR mean ≈ **0.219 J/µmol** and the ≈2000 µmol full-sun anchor.
- **Deficit vs G2:** `par_deficit_vs_g2 = f_PAR(5772 K) / f_PAR(Teff)` (how many × more insolation
  a redder star needs for the same PAR).

**Insolation source:** `--insolation-wm2` directly, or `--luminosity-lsun` + `--distance-au`
→ `S = L_sun·L / (4π·(d·AU)²)` (reuse the AU constant from `equations`).

---

## 3. Signature, output shape, validation

`compute_par_flux(teff_k=None, spectral_type=None, star=None, insolation_wm2=None,
luminosity_lsun=None, distance_au=None, par_band_nm=(400.0, 700.0))`

- **Teff — exactly one source:** `teff_k` / `spectral_type` (→ main-sequence table) / `star`
  (→ SIMBAD). **Insolation — exactly one source:** `insolation_wm2` / (`luminosity_lsun` +
  `distance_au`).
- **Out:** `{teff_k, par_fraction, insolation_wm2, par_irradiance_wm2, ppfd_umol_m2_s,
  par_deficit_vs_g2, band_nm, sed_model: "blackbody (approx — real SED deviates)",
  feeds_note: "PPFD → bioregen-area PAR input", model_note}`.
- **Validation (curated exit-1):** teff_k ≤ 0; insolation_wm2 ≤ 0; luminosity_lsun ≤ 0 or
  distance_au ≤ 0; not exactly one Teff source / one insolation source; band lo ≥ hi or ≤ 0;
  an unresolvable `--spectral-type` / a SIMBAD failure on `--star` (returned immediately).
- **Anchors:** Sun (`teff_k 5772`) → f_PAR ≈ 0.36–0.40 (blackbody; note real solar ≈ 0.40–0.45);
  M dwarf (`teff_k 3000`) → f_PAR ≈ 0.04–0.07, `par_deficit_vs_g2 ≈ 6–10×` (the load-bearing
  red-dwarf deficit); S = 1361 W/m² → PAR ≈ 540 W/m², PPFD ≈ 2000+ µmol/m²/s.

---

## 4. `query.py` wiring (modeled on the `cooling-hz` Teff-vs-star block)

One `add_parser("par-flux", …)`: a Teff mutex/optional set `--teff-k` / `--spectral-type` /
`--star` (the "exactly one" check in the core, curated exit-1 — like `spin-comfort`'s anchors);
an insolation set `--insolation-wm2` / (`--luminosity-lsun` + `--distance-au`); `--par-band-nm`
`nargs=2 type=float default=[400,700]`. `cmd_par_flux` resolves `--spectral-type`/`--star` → Teff
in the handler *or* passes them into the core (implementer's call — keep parity with how
`circumbinary-hz --star1/--star2` resolves; a core-side resolve keeps the SIMBAD dependency out
of the dispatcher). All numerics `type=float`.

---

## 5. Validation contract (self-validating, Phase-H/P)

- **Core `{"error"}` exit 1:** the §3 range/count checks; a Teff-resolution or SIMBAD failure.
- **Argparse exit 2:** a non-numeric value; a malformed `--par-band-nm` (not two numbers).
  *(The "exactly one Teff / one insolation source" rules are **core** checks → exit 1.)*

---

## 6. Tests

**`tests/test_par_flux.py`** (in-process):
- **Sun anchor:** `teff_k=5772` → f_PAR in [0.36, 0.40]; at `insolation_wm2=1361` → PAR ≈ 540
  W/m² (±5%), PPFD ≈ 2000+ µmol/m²/s.
- **M-dwarf anchor:** `teff_k=3000` → f_PAR in [0.04, 0.07], `par_deficit_vs_g2` in [6, 10].
- **PPFD cross-check:** the integrated PPFD agrees with `par_irradiance / 0.219 J·µmol⁻¹` to
  within a few percent (guards the units of the photon integral — the §Open-item verification).
- **Teff sources:** `spectral_type="G2V"` and `teff_k=5772` land the same f_PAR (main-sequence
  path); `--star` path mocked (SIMBAD) or reachability-gated.
- **Insolation sources:** `luminosity_lsun=1, distance_au=1` → S ≈ 1361 W/m² (parity with the
  direct `insolation_wm2` path).
- **Band override:** `par_band_nm=(400,750)` raises f_PAR vs the default band.
- **Validation matrix:** teff_k=0; insolation_wm2=0; both Teff sources; neither insolation source;
  band (700,400); distance_au=0.
- **Determinism:** deep-equal on repeat (no RNG/time).

**`tests/test_query_par_flux.py`** (subprocess, mirrors `test_query_thermal.py`):
- Happy-path JSON + core parity for `par-flux --teff-k 5772 --insolation-wm2 1361`.
- Exit-code matrix: exit-1 (`--teff-k 0`, both Teff sources, neither insolation source); exit-2
  (non-numeric `--teff-k`, malformed `--par-band-nm`). The `--star` round-trip reachability-gated
  (skips offline), like `test_query_phase_n.py`'s Horizons entry.

---

## 7. Success criteria

- Reproduces the Sun and M-dwarf f_PAR + deficit anchors and the ≈2000 µmol full-sun PPFD.
- PPFD integral reconciles with the 0.219 J/µmol cross-check (the one numeric-integration risk).
- Three Teff sources + two insolation sources all determinate; `--star` is the only networked path.
- `sed_model` flags blackbody-approx; `feeds_note` points PPFD at `bioregen-area`'s PAR input.
- Validation matrix passes (core exit-1 / argparse exit-2 split per §5).
- Documented in `docs/integration.md` with **units on every field** + the `bioregen-area`
  cross-reference; one `gui-architecture.md` completion row; one `CLAUDE.md` bullet.
- On shipment: flip Group I in the request file to `Deprecated — FULFILLED`, record the as-built
  per-key shape + the blackbody-vs-real-SED choice + the f_PAR values obtained.

---

## 8. Open items / risks (verify at build)

1. **PPFD normalization** — the one genuinely fiddly numeric integral. Confirm the in-band photon
   integration against both the 0.219 J/µmol shortcut and the ≈2000 µmol anchor; watch the classic
   Planck-integration units trap (nm vs m, per-nm vs per-m spectral density).
2. **Blackbody f_PAR vs real solar** — blackbody 400–700 nm gives ≈0.36–0.40; real solar ≈0.40–0.45.
   Land the anchor in the blackbody band and note the real-SED gap in `model_note` (v2 refinement).
3. **Constant additions** — `_PLANCK_H` / `_AVOGADRO` to `equations.py`; reuse Phase-Y's `_C_MS`.

Everything else is the Planck function over verified constants. ~1 focused session (lowest-urgency
group).

## References (verify at implementation; none a load-bearing canon claim)
The Planck function & PAR-band integration (radiometry); PAR photon energy ≈ 0.219 J/µmol; note
real stellar SEDs (PHOENIX / BT-Settl) deviate from blackbody — a v2 refinement. The blackbody
choice is an explicit approximation, flagged in `sed_model`.
