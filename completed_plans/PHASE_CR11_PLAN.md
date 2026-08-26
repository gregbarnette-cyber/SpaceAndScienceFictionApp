# PHASE CR-11 — WD cooling-grid extension, stellar-mass provenance & binary/multi-star exclusion composition

**Built 2026-08-26** for the sibling `scifiWorldBuilding-Claude` repo's `star_analysis` skill. Three items,
all first-fire, full scope, no staging. Additive to CR-8/CR-9/CR-10; **edits no fulfilled spec.** Contract:
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR11-wd-cooling-grid-and-mass-provenance.md`.
Coordination: `/home/greg/claude/coordination-channel.md` (MSG 001–004; WB decision **A** on the CR-11.1 Sirius B age).

## CR-11.1 — WD cooling-track high-mass extension

- **`core/cooling_tables.py`** — the `_WD_COOLING` grid extended **0.40 → 1.30 M☉** by transcribing the same
  Bedard 2020 / Montreal DA thick-H sequences (`seq_105/110/115/120/125/130_thick.txt`). The transcription
  pipeline was validated to reproduce the bundled **1.00** rows **exactly** (max Teff diff 0.0000 K); every new
  row passes the radiative-equilibrium closure identity `L=(R/R☉)²(Teff/5772)⁴` to **< 1e-4 dex**. The 0.40–1.00
  rows are **byte-identical** (no ≤1.0 regression). Real WDs above ~1.05 M☉ may host ONe cores — a second-order
  cooling-age effect the CO grid does not resolve (documented, not modelled).
- **`core/cooling.py`** — `_WD_CHANDRASEKHAR_MSUN = 1.38`. A WD mass `1.30 < M ≤ 1.38` **clamps** to the 1.30
  sequence (no error); `M > 1.38` **refuses** (`"…exceeds the Chandrasekhar limit…"`). BD grid cap unchanged.
  Snapshot mode adds one advisory `notes` entry `young_teff_cooling_age_inflation` **only for M > 1.0 at
  Teff > 12000 K** (WB MSG 004 optional; gated so ≤1.0 stays byte-identical).
- **Anchors** (`tests/test_cooling_hz.py::Cr111HighMassWDTest`): Sirius B `1.018/25970` → no error,
  `radius_rsun ≈ 0.008`, `cooling_age_gyr ≈ 0.146` (< the 0.151 M=1.0 grid value); radius monotone-decreasing in
  mass; ≤1.0 byte-identical; > 1.38 refuses.
- **Sirius B age = 0.146, not the literal ~0.12** (WB decision **A**): the tool is anchored on the frozen sparse
  1.00 sequence (criterion 4). The dense-correct 1.018 value is ~0.119; reaching it needs re-sampling the ≤1.0
  grid, which criterion 4 forbids and which shifts the contract's own 0.151 reference. Logged as WB follow-up
  **OQ-SA-WDAGE1**, out of CR-11.1 scope.

## CR-11.2 — stellar-mass provenance (`dossier` + `compare-stars`)

- **`core/stellar_mass.py`** (new, pure — reusable resolver) + **`core/stellar_mass_tables.py`** (new — internal
  seed + `--star-mass-catalog` loader/matcher, mirroring CR-10.3's `rv_precision_tables`). Precedence: manual →
  catalog → Gaia FLAME (injected by the caller, so the resolver stays offline-testable) → `L^0.2632` inversion.
  `massL_inversion_caution` = inversion-source **AND** (hot upper-MS O/B/A **or** Am `m`/Ap `p` token);
  `peculiar_star_flag` from the `m`/`p` tokens only.
- **`core/report.py`** — when a **measured** mass is preferred, `_patch_regions_for_mass` recomputes reg's
  **mass-derived** fields (radius `M^0.57`, `luminosity_from_mass`, `calculated_luminosity` → the secondary
  Calculated-HZ, MS-lifespan, `0.2·M`/`40·M`) **before** the region tables are built, so mass ↔ radius are coherent
  (**WB decision B**, MSG 006); an inversion-source star is byte-unchanged, the bcLuminosity-based primary HZ / snow
  line / ice lines are untouched, and the CR-10.5 `luminosity_consistency` stays pinned to the inversion radius.
  `_resolve_star_mass_block`/`_attach_mass_block` do the FLAME-gated resolve + attach; `build_system_dossier` gains
  `--star-mass-catalog`/`--mass-solar`. **`regions.py` untouched** (opts 8/9/10/13 + GUI byte-identical).
  **`core/databases.py`** — `compare_stars` gains the per-star block additively (legacy `mass` unchanged) +
  `--star-mass-catalog`; `_flame_mass_for` best-effort FLAME.
- **Parity** by construction: both paths use the same resolver with the same inversion mass (regions
  `stellarMass`), catalog, and FLAME → identical `mass_solar`/`mass_provenance`.
- **Anchors** (`tests/test_stellar_mass.py`, `tests/test_query_stellar_mass_live.py`): Sirius A default seed →
  `catalog` 2.063 + `peculiar_star_flag`; empty catalog → `ms_luminosity_inversion` ≈ 2.59 + caution (the silent
  2.59 no longer persists); Vega hot-MS caution, `peculiar_star_flag=false`; α Cen A/B both flags false; bad path
  → loud error.

## CR-11.3 — `exclusion-system` (binary / multi-star exclusion composition)

- **`core/exclusion_system.py`** (new) — composes the **FROZEN** `core/exclusion_boundary.py` per component (no
  second calibration). Default `--alpha 0.4` (reproduces the hand cards). Per-component mass = the CR-11.2 chain
  (shared resolver). Off-MS domain guard withholds the r_ex **sphere**, not the **mass** (barycenter uses the real
  mass). Merge-grouping = union-find over the periastron overlap test. Envelope: `long_axis = max_i(offset_i +
  r_i)`, `minor = max in-domain r_i`. `point_mass_r_ex_au` = in-domain members only (an out-of-domain mass is never
  summed in — the Sirius 3.081→74.5 all-mass hand-number is the superseded erratum). Two input modes: `--star`
  (best-effort live SIMBAD + binary-orbit; wide hierarchical companions need `--component`) and the deterministic
  repeatable `--component`. Single-star input reproduces `exclusion-boundary`.
- **Anchors** (`tests/test_exclusion_system.py`, `tests/test_query_exclusion_system*.py`): Sirius one merged zone
  (A 63.5, B `out_of_domain`/null, long-axis 66→74, point-mass 63.5); α Cen two zones (AB merged A 49.0/B 45.7,
  long-axis 54→65, point-mass 62.5; Proxima separate 20.5). Live `--star Sirius`: A MS + B WD-guarded, merged.

## Docs

`docs/integration.md` (CR-11 block — the WB consumer contract). This file. CLAUDE.md core-module notes + test count.
