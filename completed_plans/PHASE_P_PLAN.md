# PHASE P — Snow Lines & Alternative-Solvent Habitable Zones · Implementation Plan

> **Scope.** Grounds the app's existing **Alternate Habitable Zone Regions** table + snow-line outputs in
> astrobiology literature, fixes the divisors that fail a physics check, and adds a reusable solvent-zone
> engine + ice-line calculator + static reference table. **GUI-only feature work + `query.py` parity** (the
> CLI menu is frozen at opts 1–58). Source files touched: `core/equations.py` (two new self-validating
> functions + a shared solvent table), `core/regions.py` (P1 corrections + P2/P3 additive keys + P7
> annotations), `core/viz.py` (alt-HZ +4 bands, system-regions relabels, new solvent/ice-line/bar preps — §13),
> `gui/visualizations/plot_helpers.py` (new ring/bar canvases + additive `snow_au`/`solvent_bands` on
> `make_orbits_canvas`), new `gui/panels/solvent_zones.py` (three panels) + `gui/panels/__init__.py` +
> `gui/nav.py` (three new entries appended to the **existing "Worldbuilding" category** — no new category),
> `query.py` (two subcommands), docs, and tests.
>
> **Companion mockup:** `mockups/phase-p.html` (to be built & approved before code — the house rule). No code
> until the mockup is signed off.
>
> **Provenance settled (2026-06-19 Gillett scan).** See `future_phases.md` Phase P provenance note + the
> `phase-p-divisor-provenance` memory. The two facts that drive this plan:
> 1. The six alt-HZ bands are **Asimov's six biochemistries** ("Not As We Know It," 1962), not Gillett's; there
>    is **no canonical printed divisor table** to be faithful to. P1 has **no maintainer gate**.
> 2. The divisors were built on the app's **own** `planetaryTemperature` model — `T = 411.4 × (1 − A) × S^0.25`
>    (`= 374 × 1.1 × (1−A) × S^0.25`, `core/regions.py:150`), which at the default `A = 0.3` is **288 K × S^0.25**.
>    Under 288 K, water/ammonia/methane land on their exact 1-atm boil/freeze points. **All Phase P math uses
>    this model — never the airless 278.5 K constant the old draft assumed.**

---

## 0. Two temperature models (scientific correction — read first)

Phase P uses **two physically-distinct temperature models**, one per phenomenon. The legacy alt-HZ table
conflated them, which is exactly why the snow line came out wrong (see §1, `snowLine`). Both fix the app's
**albedo bug**: radiative equilibrium scales as `(1−A)^0.25` (a fourth root), **not** the `(1−A)¹` in the
legacy `planetaryTemperature` (`core/regions.py:150`) — the linear form is badly wrong away from A≈0.3
(for Venus, A≈0.77, it predicts ~110 K — below even the 227 K bare-equilibrium temperature; the fourth-root
law restores physical behavior). Shared: `S_eff(T) = (T / T_ref)^4`;
`AU(S_eff, L) = sqrt(L / S_eff)` (L = bcLuminosity, solar = 1). A band's **inner** edge = the solvent's
**boiling** point, **outer** edge = its **freezing** point.

**(M1) Surface model — solvent liquid bands (habitability).** Whether a solvent is liquid on a planet
*surface* depends on surface temperature = equilibrium **+ greenhouse**. Earth-calibrated (288 K at A=0.3,
S=1), correct albedo exponent:
```
T_surf = 314.9 × (1−A)^0.25 × S^0.25       # = 288 × ((1−A)/0.7)^0.25 × S^0.25 ; → 288.0 K at A=0.3, S=1
```
Used by: the alternate-HZ **solvent bands** (P1a, P2), `compute_solvent_zone` (P4), and the corrected
`planetaryTemperature` display (P1e). At A=0.3 it reproduces every sound legacy divisor (water 2.8/0.8,
ammonia 0.48/0.21, methane 0.023/0.0094) — the existing bands assume **Earth-like greenhouse**, the
documented simplification. (`314.9 / 278.5 ≈ 1.13` is a uniform ~13% greenhouse warming calibrated to Earth.)

**(M2) Equilibrium model — snow / ice / condensation lines.** Ice condenses in vacuum / thin disk gas with
**no greenhouse**, so these use the standard radiative-equilibrium temperature:
```
T_eq = 278.5 × (1−A)^0.25 × S^0.25         # 278.5 K at A=0, S=1 (255 K at A=0.3 — Earth's textbook eq. temp)
```
Used by: the snow line (P1c), `lh2Line` (P1b), the P3 ice fronts, and `compute_ice_lines` (P5). With A≈0,
water frost at 170 K lands at **2.68 AU** — the canonical snow line (Hayashi 1981; asteroid-belt C/S
transition). This is why the legacy `snowLine` (0.04 → 5.0 AU, 129 K) is **wrong**: it applied the warmer
greenhouse-baked surface model to an ice-condensation line. See §1.

> **Why two models, not one:** ice stability (no atmosphere → no greenhouse → M2) and surface liquid-solvent
> habitability (greenhouse matters → M1) are different physics. Using one model for both is what produced the
> 5 AU snow-line error. Each model is used only for its appropriate phenomenon and is labeled as such in the
> output (P7).

---

## 1. P1 — corrections to existing divisors (behavior-changing, `core/regions.py:160–177`)

These shift CLI opts 8–10/13 output, the two GUI ring diagrams (opts 8/9/10/13 — the snow-line ring moves in the
**System Regions Diagram**), and `query.py star-regions` / `sol-regions` / `star-regions-manual`. **Each
correction ships with its `docs/star-system-regions.md` update + a `tests/test_worldbuilding.py` re-anchor in
the same commit** (the Phase H pattern). The sound **solvent** bands stay put — **do not touch
water/ammonia/methane** (`prw*`/`pra*`/`pm*`). Solvent bands use **M1** (surface); snow/ice lines use **M2**
(equilibrium).

| Key | Current divisor | Model | Status | Action | Corrected divisor | Corrected band |
|---|---|---|---|---|---|---|
| `phInner` | 0.0025 (64 K) | M1 | ❌ supercritical (H₂ crit 33 K) | move to H₂ boil 20.3 K | **0.0000247** | inner = 20.3 K, ≈ 201 AU (solar) |
| `phOuter` | 0.000024 (20 K) | M1 | ⚠️ sits at H₂ **boil** (belongs at inner) | move to H₂ freeze 13.8 K | **0.0000053** | outer = 13.8 K, ≈ 436 AU (solar) |
| `snowLine` | 0.04 (5.0 AU) | M2 | ❌ **wrong** — 5 AU / 129 K is not the water snow line | **fix value** to the canonical 170 K snow line | **0.139** | 170 K / **2.68 AU** (solar) |
| `lh2Line` | 0.0025 | M2 | ✓ **correct value** — under M2 this is 62 K / 20 AU | **relabel only** "N₂/CO (1-atm) condensation (~62 K)" | unchanged (0.0025) | 62 K / 20 AU (solar) |
| `ffInner`/`ffOuter` | 52 / 29.9 | M1 | ⚠️ hotter than real silicones | **label only** "hypothetical high-T silicone analog" (faithful to Asimov's hot band — do **not** retune) | unchanged | 674–773 K |

- **P1a (hydrogen)** — divisor change (M1/surface): `phInner = sqrt(bcLuminosity / 0.0000247)`,
  `phOuter = sqrt(bcLuminosity / 0.0000053)`; band relocates to ~200–440 AU. Retuning only `phInner` (leaving
  `phOuter` at 20 K) collapses the band to ~0 width — fix both.
- **P1b (`lh2Line`)** — **relabel only.** Under M2 the existing 0.0025 *is* correct: `278.5 × 0.0025^0.25` = 62 K,
  at 20 AU — the 1-atm N₂/CO surface-frost regime. State it's a *different* convention from P3a's disk frosts
  (CO/N₂ at ~20 K). No number change.
- **P1c (`snowLine`)** — **divisor change** (M2): `0.04 → 0.139`. The canonical water snow line is ~170 K at
  **2.68 AU** (`(278.5/170)² = 2.68`; Hayashi 1981 minimum-mass nebula; asteroid-belt C/S transition). The legacy
  5.0 AU / 129 K was the greenhouse-baked surface model misapplied to an ice line. The "dual snow line" idea is
  **dropped** — present-day irradiation and formation-era both fall at ~2.7 AU for the current Sun (see §3).
- **P1d (fluorosilicone)** — **label only**; faithful to Asimov's intended very-hot band.
- **P1e (`planetaryTemperature` albedo fix)** — **the function fix.** Replace `374 × 1.1 × (1−A) × S^0.25` with
  the M1 form `314.9 × (1−A)^0.25 × S^0.25` (`= 288 × ((1−A)/0.7)^0.25 × S^0.25`). Identical at A=0.3 (→ 288 K,
  so opts 8/13 default output is unchanged), but **physically correct at every other albedo** — fixes the
  Earth-equivalent-orbit Temp K/C/F columns for opt 9 (user-entered albedo) and opt 10 (manual). The legacy
  linear `(1−A)` term made the value collapse at high albedo (Venus → ~110 K, an impossible value below the
  227 K equilibrium temp); the fourth-root form gives a sensible Earth-greenhouse-scaled surface proxy
  (~256 K for Venus). `planetaryTemperatureC`/`F` derive from it unchanged. Re-anchor any test that exercised a
  non-0.3 albedo.

> **Decision recorded (Package A, 2026-06-19):** `snowLine` is a genuine **value** error (5 AU → 2.68 AU) — the
> divisors were built on the surface model (M1, greenhouse-baked) but a snow line is an ice-condensation line
> (M2, no greenhouse). `lh2Line` is **correct** under M2 and only needs relabeling. Hydrogen is a real value
> error. `planetaryTemperature`'s `(1−A)¹` is a real physics bug (P1e). Solvent bands keep their M1 numbers
> (Earth-like-greenhouse habitability is a defensible, labeled convention).

---

## 2. P2 — new alternative-solvent bands (additive, `core/regions.py` + `core/viz.py`)

New keys in the regions result dict + new rows in `_display_alternate_hz_regions` and the `core/viz.py`
`prepare_alt_hz_diagram` zone list (`core/viz.py:443–456`). These are **solvent surface-liquid bands → M1**
(surface model); each derived from its 1-atm liquid range via `divisor = S_eff(T_edge)` at A = 0.3 (= the
288 K reference). Naming convention mirrors the existing `xxInner`/`xxOuter` keys.

| Band | New keys | T edges (boil/freeze, 1 atm) | Divisors (M1, A=0.3) | Notes |
|---|---|---|---|---|
| P2a — CO₂ (**pressure-conditional**, ≥ 5.2 atm) | `co2Inner`/`co2Outer` | 304.1 K (crit) / 216.6 K (triple) | 1.235 / 0.325 | No 1-atm liquid (sublimes 194.7 K) — flag `pressure_conditional=True`; band meaningless without the assumed pressure |
| P2b — liquid sulfur | `sInner`/`sOuter` | 717.8 K (boil) / 388.4 K (melt) | 38.5 / 3.31 | The physically-correct sub-band of the broad fluorocarbon-sulfur band; outer edge ≈ the existing `fsOuter` |
| P2c — water-ammonia eutectic | `waInner`/`waOuter` | ~273 K / ~176 K (eutectic, ~−97 °C) | ~0.82 / ~0.14 | Titan-relevant; stays liquid well below pure-water freeze. Eutectic temp is composition-dependent — cite + flag approximate |
| P2d — concentrated sulfuric acid | `saInner`/`saOuter` | ~610 K (boil, 337 °C) / 283.6 K (freeze) | 20.1 / 0.94 | One of two solvents Bains 2024 rates functional **and** plausibly abundant on rocky worlds |

Add each to: the regions dict, `_display_alternate_hz_regions` (display label + AU/LM formatting like the existing
rows), and `prepare_alt_hz_diagram` (label + color + inner/outer keys), ordered hot→cold among the existing six.

---

## 3. P3 — condensation fronts (additive, `core/regions.py`) — all on **M2** (equilibrium)

Ice/condensation fronts are vacuum phenomena → **M2** (`T_eq = 278.5 × (1−A)^0.25 × S^0.25`, A≈0), the same
model as the corrected `snowLine` (P1c). Each placed by `AU = sqrt(L) × (T_ref / T_cond)²`.

- **P3a — ice-line set.** New keys for the condensation fronts of CO₂, NH₃, CO, N₂ alongside the corrected water
  snow line. Anchor values (solar L, A=0): water 170 K → 2.68 AU; CO₂ ~70 K → 15.8 AU; NH₃ ~80 K → 12.1 AU;
  N₂ ~22 K → ~160 AU; CO ~20 K → ~194 AU.
- **P3b — front temperature annotations.** Display each front's condensation T beside its AU (the P7a display
  change applied to the snow/ice lines).
- **P3c — single canonical water snow line (no dual line).** P1c already sets `snowLine` to the canonical
  170 K / 2.68 AU. The earlier "dual snow line" plan is **dropped**: under M2 the present-day irradiation snow
  line and the formation-era line both fall at ~2.7 AU for the current Sun (`(278.5/170)² = 2.68`; Hayashi's
  minimum-mass nebula gives ~2.7 AU at 170 K), so a second key would be redundant. Footnote that disk models put
  the formation line anywhere ~2–3 AU across the disk's lifetime.

> **Disk vs surface caveat (docs + output):** the deep-cold fronts CO (~20 K) and N₂ (~22 K) are really set by
> *disk-midplane* temperature, not stellar irradiation, so their M2 placement (~160–194 AU) is **illustrative**.
> Flag them `disk_line=True`. Note that `lh2Line` (P1b, ~62 K / 20 AU) is the **1-atm N₂/CO surface-frost**
> reading — a different, complementary convention to these disk fronts; both are shown and both are correct for
> what they represent.

These are additive keys; the only existing value they touch is `snowLine` (changed in P1c).

---

## 4. P4 — Solvent Habitable Zone engine (`core/equations.py` + GUI + `query.py`) — the headline

### 4a. Shared built-in solvent table (`core/equations.py`)

Module-level constant `_SOLVENTS` — the single source of truth shared by P4/P5/P6. One entry per solvent:
`{key, name, t_low_k, t_high_k, pressure_conditional (bool), assumed_pressure_atm (None unless conditional),
citation}`. `t_low_k` = freezing/lower edge, `t_high_k` = boiling/upper edge (both at 1 atm unless conditional).

| key | name | t_low_k | t_high_k | conditional | citation |
|---|---|---|---|---|---|
| `water` | Water | 273.15 | 373.15 | no | CRC; Asimov 1962 |
| `ammonia` | Ammonia | 195.45 | 239.75 | no | Gillett (−77.7/−33.4 °C); Asimov 1962 |
| `methane` | Methane | 90.69 | 111.65 | no | CRC; Asimov 1962 |
| `ethane` | Ethane | 90.36 | 184.55 | no | CRC; Titan (ethane lakes) |
| `water_ammonia` | Water-ammonia eutectic | 176.0 | 273.0 | no (approx) | Gillett (eutectic ~−97 °C); Titan |
| `so2` | Sulfur dioxide | 197.6 | 263.1 | no | Gillett (−75.5/−10 °C) |
| `co2` | Carbon dioxide | 216.6 | 304.1 | **yes** (≥ 5.2 atm) | Bains 2024; CRC (triple/critical) |
| `sulfuric_acid` | Concentrated sulfuric acid | 283.6 | 610.0 | no | Bains 2024; Gillett (~337 °C) |
| `sulfur` | Molten sulfur | 388.4 | 717.8 | no | CRC |
| `hydrogen` | Hydrogen | 13.80 | 20.28 | no | CRC; Asimov 1962 |
| `nitrogen` | Nitrogen | 63.15 | 77.36 | no | CRC |
| `hf` | Hydrogen fluoride | 189.8 | 292.7 | no | CRC |
| `formamide` | Formamide | 275.7 | 493.0 | no | Bains 2024 (NH-solvent) |

> Numbers above are the **anchor values** the tests lock; the implementer confirms each against CRC at build time
> and fixes any to 2 dp. For `co2`, `assumed_pressure_atm = 5.2` and the band is the triple→critical range.

### 4b. `compute_solvent_zone(luminosity_solar, solvent=None, t_low_k=None, t_high_k=None, albedo=0.3) -> dict`

- Pick a named `solvent` from `_SOLVENTS` **or** supply a custom `t_low_k`/`t_high_k` range (mutually
  sufficient: named solvent fills the temps; explicit temps override / enable custom). Hydrogen uses 13.8/20.3 K
  (**not** the legacy 64 K).
- **M1 surface model** (solvent liquid = surface habitability): `T_ref = 314.9 × (1 − albedo)^0.25`
  (`= 288 × ((1−albedo)/0.7)^0.25`; → 288.0 K at albedo 0.3, the existing alt-HZ convention).
  `s_eff_inner = (t_high_k / T_ref)^4`, `s_eff_outer = (t_low_k / T_ref)^4`;
  `inner_au = sqrt(luminosity_solar / s_eff_inner)`, `outer_au = sqrt(.../ s_eff_outer)`; `*_lm = *_au × 8.3167`.
- **Self-validates** (Phase H contract): `luminosity_solar > 0`, `0 ≤ albedo < 1`, `0 < t_low_k < t_high_k`,
  and (named path) `solvent in _SOLVENTS`; else `{"error": str}`.
- At albedo 0.3 this reproduces the legacy alt-HZ divisors (water 373/273 K → 2.8/0.8). The shared
  `T_ref` helper (M1 for P4, M2 for P5) lives in `core/equations.py` so the two calculators can't drift.
- Returns `{solvent, name, t_low_k, t_high_k, albedo, t_ref_k, luminosity_solar, inner_au, outer_au, inner_lm,
  outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm,
  citation}`. (`t_eq_*` echo the edge temps for transparency / round-trip checking.)

### 4c. GUI — `SolventZonePanel`

Pure-math `ResultPanel` (the `LuminosityPanel` pattern; no `DiagramToggleMixin` initially). Inputs: luminosity
`QLineEdit`; solvent `QComboBox` (the `_SOLVENTS` names + a "Custom…" entry that reveals two temperature
`QLineEdit`s); optional albedo `QLineEdit` (placeholder "0.3"). Output table: Solvent | Liquid Range (K) |
Albedo | Inner (AU/LM) | Outer (AU/LM) | S_eff in/out, plus a citation line and (when conditional) an amber
"pressure-conditional — assumes N atm" note. **Stretch:** a ring-diagram tab reusing `make_alt_hz_canvas`.

---

## 5. P5 — Ice-Line Calculator (`core/equations.py` + GUI + `query.py`)

`compute_ice_lines(luminosity_solar, albedo=0.0) -> dict` — water snow line (170 K, the single canonical line —
no dual line, see P3c) plus CO₂/NH₃/N₂/CO condensation fronts. **M2 equilibrium model** (no greenhouse —
default `albedo=0.0` for ice grains): `T_ref = 278.5 × (1−albedo)^0.25`; `AU = sqrt(L) × (T_ref / T_cond)²`,
each with its condensation T annotated and a `disk_line=True` flag on the deep-cold CO/N₂ fronts (placement
illustrative — see §3 caveat). Self-validating (`luminosity_solar > 0`, `0 ≤ albedo < 1`). Returns
`{luminosity_solar, albedo, t_ref_k, lines:[{species, t_cond_k, au, lm, kind ("snow_line"|"front"), disk_line,
note}]}`.

GUI — `IceLineCalculatorPanel`: luminosity + optional albedo → table (Species | Cond. T (K) | Distance (AU/LM) |
Type | Note). Pure math.

---

## 6. P6 — Solvent Reference Table (`SolventReferencePanel`, static GUI)

Static display à la `MainSequencePanel` (opt 12). Reads `_SOLVENTS` (no computation). Columns: Solvent | Liquid
Range (K, 1 atm) | Equilibrium-T Band (the 288 K T-edge band) | Plausibility (Bains 2024 four-criterion verdict
string, stored alongside each `_SOLVENTS` entry as `plausibility`) | Key Citation. Houses the "only water +
concentrated sulfuric acid are plausibly abundant on rocky worlds; ammonia fails occurrence; CO₂ is the standout
non-protonating solvent" findings as the verdict column.

---

## 7. P7 — Transparency annotations (low-risk, `core/regions.py` + diagrams)

- **P7a** — show the implied edge temperature next to every AU value, **using the right model per row**:
  solvent bands → **M1** `T_surf = 314.9 × (1−A)^0.25 × S^0.25` (288 K at A=0.3); snow/ice lines → **M2**
  `T_eq = 278.5 × (1−A)^0.25 × S^0.25`. Applied in the CLI display helpers + the ring-diagram labels.
- **P7b** — per-zone citation footnotes (Asimov 1962, Bains 2024, NAS *Limits of Organic Life*).
- **P7c** — a one-line **model disclaimer** stating which rows are M1 (surface, Earth-like greenhouse — these run
  closer-in than greenhouse-corrected Kopparapu HZs: water band 0.60–1.12 AU vs Kopparapu ~0.95–1.37 AU) vs M2
  (equilibrium ice condensation, no greenhouse). Makes the two-model split explicit to the user.

---

## 8. `query.py` subcommands (Phase H/N conventions)

Two new subcommands (the dispatcher + argparse idiom of the Phase-H block, `query.py:131–165` / `:308–353`).
Both wrap **self-validating** core functions, so they follow the **Phase H** contract (curated `{"error"}`),
**not** the Phase N raw-exception contract.

| Subcommand | Core fn | Args | Network | Output keys |
|---|---|---|---|---|
| `solvent-zone` | `equations.compute_solvent_zone` | `--luminosity` + (`--solvent NAME` \| `--t-low --t-high`) [`--albedo`] | none | `solvent, name, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, citation, …` |
| `ice-lines` | `equations.compute_ice_lines` | `--luminosity` [`--albedo`] | none | `luminosity_solar, albedo, t_ref_k, lines[]` |

`solvent-zone` defaults `--albedo` to **0.3** (M1); `ice-lines` defaults `--albedo` to **0.0** (M2, ice grains).

- `--solvent` and the `--t-low/--t-high` pair are **mutually exclusive**; supplying neither → argparse error
  (exit 2) unless a sensible default is chosen (recommend: require one of them, exit 2 if absent).
- Contract: malformed/missing/non-numeric args → **argparse exit 2** (stderr); out-of-range (luminosity ≤ 0,
  albedo ∉ [0,1), t_low ≥ t_high, unknown solvent) → `{"error": str}` **exit 1**; success → dict **exit 0**.
- **Docs:** add both to `docs/integration.md` (quick-reference table + a subcommand section under a new
  "Solvent zones (Phase P)" group), noting they wrap self-validating fns (curated errors, unlike Phase N).
- **Existing region subcommands change OUTPUT (no dispatcher change).** `star-regions` / `sol-regions` /
  `star-regions-manual` `_out(...)` the whole regions dict verbatim (`query.py:50` / `:57` / `cmd_sol_regions`),
  so the **P1 corrected values** (`snowLine` 0.04→0.139, `phInner`/`phOuter`, and `planetaryTemperature`/`C`/`F`
  — the last only at **non-0.3** albedo, so `star-regions-manual --bond-albedo …` shifts while the A=0.3
  defaults of `star-regions`/`sol-regions` are unchanged) and the **P2/P3 new dict keys** (`co2*`, `s*`, `wa*`,
  `sa*`, the CO₂/NH₃/N₂/CO ice-front keys) flow through automatically. **These are consumer-facing output
  changes** for the `scifiWorldBuilding-Claude` repo — call them out in `docs/integration.md`.
- **P7 does NOT affect `query.py`.** P7 is display-only (CLI text + ring-diagram labels); it adds no dict keys,
  so the JSON output is unchanged by it. Consumers derive their own implied-T from the divisor + luminosity
  (or recompute via `solvent-zone`/`ice-lines`). *(If the downstream repo later wants implied-T in the JSON,
  that would be a separate additive key — out of scope here.)*

---

## 9. Validation contract (summary)

- **`compute_solvent_zone` / `compute_ice_lines`** — self-validating, return `{"error": str}` for: non-positive
  luminosity; `albedo ∉ [0, 1)`; `t_low_k` not `0 < t_low < t_high`; unknown named solvent. (Phase H pattern.)
- **`core/regions.py` (P1/P2/P3/P7)** — no new validation; the regions function is non-self-validating legacy
  code and P1–P3/P7 only change divisors/labels/added keys. (Its existing `star-regions-manual` raw-exception
  behavior is unchanged — documented in `docs/integration.md`.)
- **GUI panels** — the three new panels surface `{"error"}` in the standard red `_err` label; `SolventZonePanel`
  shows the pressure-conditional warning as a non-error amber note.

---

## 10. Tests (`tests/test_solvent_zones.py`, offline; + re-anchors in `tests/test_worldbuilding.py`)

New file `tests/test_solvent_zones.py`:
- **M1 anchor** — `compute_solvent_zone` reproduces the legacy alt-HZ divisors at A=0.3: water → inner_au /
  outer_au matching `sqrt(1/2.8)` / `sqrt(1/0.8)`; ammonia → `sqrt(1/0.48)` / `sqrt(1/0.21)`; methane → 0.023 /
  0.0094 equivalents. Asserts `t_eq_inner ≈ t_high_k` and `t_eq_outer ≈ t_low_k` (round-trip), `t_ref_k ≈ 288.0`.
- **M1 albedo exponent** — at A=0 the surface T_ref ≈ 314.9 K (not 411.4); halving `(1−A)` shifts the band by the
  `(1−A)^0.5` factor in AU (the corrected fourth-root law), **not** the legacy `(1−A)²`.
- **Custom range** — `t_low/t_high` path matches a named solvent with the same temps.
- **CO₂ pressure-conditional** — `pressure_conditional=True`, `assumed_pressure_atm=5.2`, band = triple→critical.
- **Hydrogen** — uses 13.8/20.3 K (band far out, ~200–440 AU at L=1, A=0.3), **not** the legacy 64 K.
- **Validation matrix** — luminosity ≤ 0, albedo 1.0 / −0.1, t_low ≥ t_high, unknown solvent → `{"error"}`.
- **`compute_ice_lines` (M2)** — `t_ref_k ≈ 278.5` at A=0; **water snow line ≈ 2.68 AU** at L=1 (170 K); CO₂ ≈
  15.8 AU, NH₃ ≈ 12.1 AU; CO/N₂ carry `disk_line=True`; **no** dual/formation water key; validation for bad
  luminosity/albedo.
- **`query.py` contracts** (subprocess, the `test_query_phase_n.py` harness): `solvent-zone` / `ice-lines`
  happy-path exit 0 + parity with the core fn; out-of-range → `{"error"}` exit 1; bad/missing/both-of-mutex args
  → exit 2.

Re-anchors in `tests/test_worldbuilding.py` (or a P1 section there):
- **P1a hydrogen** — `compute_star_system_regions(...)` `phInner`/`phOuter` match the corrected 0.0000247 /
  0.0000053 divisors (band ~200–440 AU at solar L). Locks the hydrogen value change.
- **P1c snow line** — `snowLine` now ≈ `sqrt(bcLuminosity / 0.139)` (≈ 2.68 AU at solar L), **not** the old
  5.0 AU. Locks the value change + that the System-Regions ring moved.
- **P1e `planetaryTemperature`** — at A=0.3 unchanged (≈ 288 K at S=1, regression guard for opts 8/13); at a
  **non-0.3** albedo it now follows `314.9 × (1−A)^0.25 × S^0.25` (e.g. A=0.7 gives ~233 K, not the legacy
  ~123 K). Locks the albedo-exponent fix; `planetaryTemperatureC`/`F` derive correctly.
- **P2 new bands** — `co2*`, `s*`, `wa*`, `sa*` keys present with the expected AU for a solar-L fixture.
- **P3a ice fronts** — CO₂/NH₃/N₂/CO front keys present; the deep-cold ones flagged `disk_line`.
- **Sound bands untouched** — `prw*`/`pra*`/`pm*`/`ff*`/`fs*` byte-identical to pre-P1 (regression guard).
- Add the new file to the `CLAUDE.md` test-list bullet.

---

## 11. Success criteria

1. `compute_solvent_zone` (M1 surface model) reproduces the existing six alt-HZ bands exactly at A=0.3 (proving
   model continuity) and generalizes to all 13 `_SOLVENTS` + custom ranges; self-validating.
2. Value corrections land: the **hydrogen band** is physically correct (~200–440 AU); the **snow line** is the
   canonical 170 K / 2.68 AU (was 5.0 AU); **`planetaryTemperature`** uses the correct `(1−A)^0.25` (unchanged at
   A=0.3, correct elsewhere). Water/ammonia/methane/fluorosilicone/`lh2Line` divisors are byte-identical to today
   (`lh2Line`/fluorosilicone relabeled only).
3. P2/P3 add the CO₂/sulfur/water-ammonia/sulfuric-acid solvent bands (M1) + the CO₂/NH₃/N₂/CO ice fronts (M2),
   all additive; the only existing values changed are hydrogen, `snowLine`, and `planetaryTemperature`'s albedo
   term — the `prw/pra/pm/ff/fs` regression test passes.
4. `query.py solvent-zone` and `ice-lines` exist with the Phase-H contract; `star-regions`/`sol-regions`/
   `star-regions-manual` carry the corrections + new keys with no dispatcher change.
5. The three GUI panels work (Solvent Zone, Ice Line, Solvent Reference) **folded into the existing
   "Worldbuilding" nav category** (alongside Roche Limit / Tidal Locking / Hill Sphere / Binary Orbit /
   Atmosphere Retention — the Phase H panels); P7 annotations show implied T + citations on the existing ring
   diagrams.
5b. Visualizations (§13) land: V1 (alt-HZ +4 bands) + V2 (system-regions snow-line ring moves + relabels) update
   the existing opt-8/9/10/13 diagrams; V3/V4/V5 give the three new panels their ring/bar diagrams; V6/V7 add the
   opt-in snow-line + solvent-zone overlays to the opt-3/6/Map orbital diagrams (default off → byte-identical).
   `make_orbits_canvas` with no `snow_au`/`solvent_bands` is unchanged (additivity guard passes).
6. Docs updated: `docs/star-system-regions.md` (the two-model framework M1/M2, corrected divisor list incl. the
   `snowLine` fix, the `planetaryTemperature` albedo correction, the T-edge/citation table), `docs/equations.md`
   + `docs/integration.md` (the two calculators + subcommands), `CLAUDE.md` test-list bullet, and the
   `future_phases.md` Phase P header flipped to ✅ IMPLEMENTED.
7. Full suite green headless (`QT_QPA_PLATFORM=offscreen`), modulo the known 3 live-network baseline skips.

---

## 12. Sequencing & checkpoints

Per the maintainer's one-checkpoint-at-a-time cadence (stop for manual verify after each), in ascending risk.
The §13 visualizations are bundled into the step they ship with; **hover (§13 Interactivity) is built into each
new canvas as it's created — not a separate step**.

0. **M1/M2 model helpers** — add the two `T_ref` helpers to `core/equations.py` first (zero behavior change;
   nothing calls them yet). Everything else references them so the two models can't drift.
1. **P7** — transparency annotations (zero numeric risk; pure display + the per-row implied-T helper). Wires the
   M1/M2 labels into the displays before any value moves.
2. **P4** — `_SOLVENTS` table + `compute_solvent_zone` (M1) + `SolventZonePanel` + `solvent-zone` subcommand + tests.
   The biggest win; everything downstream reuses `_SOLVENTS`. **Viz: V3** solvent-zone ring (auto-fit, hover).
3. **P6** — `SolventReferencePanel` (static, reuses `_SOLVENTS`). **Viz: V5** liquid-range bar chart (hover).
4. **P5** — `compute_ice_lines` (M2) + `IceLineCalculatorPanel` + `ice-lines` subcommand + tests. **Viz: V4**
   ice-line ring (inner-focus ≤ 18 AU + Full-range toggle + hover).
5. **P2 / P3** — additive solvent bands (M1) + ice-front keys (M2) in `core/regions.py` (+ `core/viz.py`).
   **Viz: V1** alt-HZ → 10 bands (inner-focus ≤ 12 AU + Full-range toggle + hover); **V2** system-regions *label*
   edits ("LH₂ Line" → "N₂/CO (1-atm)", "Snow Line" → "Water snow line").
6. **P1** — the value corrections last (the behavior-changing step): **P1a** hydrogen divisor, **P1c** snow-line
   divisor (5.0 → 2.68 AU), **P1e** `planetaryTemperature` albedo exponent, plus the P1b/P1d relabels — each with
   its docs update + `test_worldbuilding.py` re-anchor in the same commit. *(This is where the snow-line ring
   physically moves in the V1 alt-HZ + V2 system-regions diagrams — the P1c value change drives it.)*
7. **V6 / V7 — orbital overlays** — additive `snow_au=` (V6 snow-line ring) + `solvent_bands=[…]` (V7
   multi-select solvent shading, hover) on `make_orbits_canvas`, wired to opts 3/6/Map with the O4/O10b-style
   checkboxes. Default off → byte-identical to today; the additivity guard (§10) passes.
8. **Docs + wrap-up** — `docs/equations.md` + `docs/integration.md` (the two subcommands + the region-output-change
   note) + `CLAUDE.md` test bullet; flip the `future_phases.md` Phase P header to ✅ IMPLEMENTED; full suite green
   headless.

> **Mockup gate:** build & get sign-off on `mockups/phase-p.html` (Solvent Zone calc + Ice Line calc + the
> corrected/extended Alternate-HZ ring with P7 annotations + the §13 diagrams: inner-focus toggles, the orbital
> overlays, and hover tooltips) **before** step 1.

---

## 13. Visualizations (GUI — additive, reuse existing canvases)

Phase P is viz-heavy: the ring-diagram machinery already exists, so most of this is data wiring + small additive
canvas changes. Everything follows the **additive / opt-in** rule (no existing caller breaks) and the
established **O4/O10b optional-checkbox overlay** pattern. Tiers map to effort/value.

### Tier 1 — forced by the data changes (must do with P1/P2/P3)

- **V1 — Alternate HZ Diagram +4 bands (`make_alt_hz_canvas`, opts 8/9/10/13).** `prepare_alt_hz_diagram`
  (`core/viz.py:444–455`) hardcodes the 6 Asimov bands; P2 adds CO₂/sulfur/water-ammonia/sulfuric-acid →
  **10-ring** ⁴√AU diagram. Extend the canvas colour cycle; the hydrogen band now reaches ~200–440 AU (still
  fine on the ⁴√ scale). P7a adds the implied-T (M1) to each ring label.
- **V2 — System Regions Diagram label/ring fix (`make_system_regions_canvas`, opts 8/9/10/13).**
  `prepare_system_regions_diagram` (`core/viz.py:407–408`) draws hardcoded **"Snow Line"** + **"LH₂ Line"**
  rings. The snow-line ring **moves inward** (5.0 → 2.68 AU) automatically from P1c; the **labels must change**:
  "LH₂ Line" → "N₂/CO (1-atm)" (P1b), "Snow Line" → "Water snow line" (P1c). P7a adds the implied-T (M2) labels.

### Tier 2 — new diagrams for the new panels (build with P4/P5/P6)

- **V3 — Solvent Zone ring (`SolventZonePanel`, P4)** *(promoted from the §4c stretch to standard)*. The chosen
  solvent's band drawn as a shaded annulus on a ⁴√AU ring, with the **water HZ behind it for reference** and the
  star at centre. Reuse `make_alt_hz_canvas` (single band + a reference ring) or a thin new
  `make_solvent_zone_canvas`. A `DiagramToggleMixin` tab.
- **V4 — Ice-Line ring (`IceLineCalculatorPanel`, P5).** Concentric "frost-line map" — water snow line +
  CO₂/NH₃/N₂/CO fronts as labelled rings (dashed for the disk-set CO/N₂). Reuse the ring style;
  `core.viz.prepare_ice_line_diagram(result)` → a ring canvas.
- **V5 — Solvent Reference bar chart (`SolventReferencePanel`, P6).** Horizontal **liquid-range bars on a
  Temperature (K) axis** (one bar per solvent, freeze→boil), coloured by plausibility — mirrors
  `make_hyper_bar_canvas` (Honorverse, O10a) exactly. `core.viz.prepare_solvent_ranges()` → `make_solvent_bar_canvas`.

### Interactivity — cursor hover on every zone/line (all Phase P diagrams)

Every ring/bar/overlay diagram is **hoverable**: moving the cursor over a solvent **zone** (annulus), a snow/ice
**line** (ring), a planet, the star, or a reference-table **bar** pops a small **cursor-anchored tooltip** with
that element's details — name, AU range (or AU), edge temperatures, model (M1/M2), and the citation / status.
This is the app's established dot-anchored-hover convention (`make_star_chart_canvas`, `make_mass_radius_canvas`,
`make_toomre_canvas`, …); the existing ring canvases (`make_alt_hz_canvas` / `make_system_regions_canvas`) only
do **click-to-info today**, so V1–V7 add the matplotlib `motion_notify_event` hover annotation on top (keep the
click box too). Whole-annulus hit-testing (hover anywhere *in* a band, not just on its edge), off-scale items
excluded (they live in the legend). In the GUI canvases the tooltip anchors near the cursor and clamps to the
axes; the mockup renders the same behaviour with an SVG `[data-tip]` + a cursor-following div.

### Tier 3 — cross-feature overlays on real planet systems (highest worldbuilding value)

Reuse `make_orbits_canvas` (already takes `hyper_au=` and the O4 solar / O10b hyper-limit overlay checkboxes) on
opts **3 / 6 / Map**:

- **V6 — Snow-line overlay (low effort).** A "Show snow line" checkbox → one dashed ring at the host's water snow
  line (M2 from `st_teff`/`st_rad`-derived luminosity), so you see which planets are beyond it (icy/giant) vs
  inside (rocky). Mirrors the O10b hyper-limit ring; add `snow_au=` to `make_orbits_canvas` (additive).
- **V7 — Alternate-solvent-zone overlay (headline).** A **multi-select row of solvent checkboxes** (default
  water + ammonia + methane ticked, each with a distinct colour) → shade **several** solvent bands at once as
  translucent annuli **behind the real planet orbits**, answering "which biochemistry could each planet host?"
  across the whole system in one view. The Asimov bands mostly tile the AU axis without overlapping, so multiple
  bands read cleanly (translucent fill + outline rings handle the few that do overlap). Add `solvent_bands=[…]`
  (a list) to `make_orbits_canvas` (additive); empty list / none ticked → no annuli → byte-identical to today.

### Scale handling (RESOLVED 2026-06-19)

Hydrogen (200–440 AU) and the CO/N₂ fronts (~160–194 AU) dwarf the worldbuilding-relevant inner cluster
(fluorosilicone 0.14 → methane 10 AU, water snow line 2.68 AU). The data is two populations — a dense, important
inner cluster + a few sparse, peripheral outliers — so the diagrams optimise the default for the cluster:

- **Alt-HZ ring (V1) + Ice-Line ring (V4): inner-focus ⁴√ default + "Full range" toggle.**
  - Default radial cap ≈ the outermost *ordinary* band: **~12 AU** for the alt-HZ ring (through methane), **~18 AU**
    for the ice-line ring (through CO₂). This expands the inner bands from ~13–39 % of the radius (⁴√ at maxAU=440)
    to ~33–96 % — readable separation, no dead annulus.
  - **Off-scale items are not hidden:** any band/line beyond the cap (hydrogen ~200–440 AU; the N₂/CO line ~20 AU;
    the CO/N₂ disk fronts ~160–194 AU) is listed in the legend with a `▸ … off-scale` marker + its true AU, and
    the canvas shows a "view ≤ N AU" cap note.
  - A **"Full range" checkbox** (the established O4/O10b re-render pattern + `DiagramToggleMixin`) re-renders ⁴√
    out to the farthest band when the user wants the exotic ones to scale.
- **System Regions ring: unchanged (√AU).** It already handles `lh2Line` (~20 AU) / `sysol` (~40 AU) and has no
  160–440 AU outliers — no scale change, no toggle.
- **Solvent Zone ring (V3): auto-fit per solvent** (`maxAU = outer × 1.1`) — picking hydrogen simply zooms out;
  no toggle needed for a single-band view.
- **Log radial is rejected for the rings** — a ring diagram maps AU = 0 to the centre (the star); `log(0) = −∞`
  has no centre, breaking the star-at-centre metaphor and the gold ★ marker. (Log is correct for the **P6 bar
  chart**, a Cartesian axis with no centre — and is used there.)

> **Why inner-focus over plain ⁴√-everything:** at maxAU = 440 the ⁴√ chart wastes the ~40–80 %-radius annulus
> (the empty 10–160 AU gap) while squeezing the bands that matter; the toggle is ~free in this app (checkbox
> re-render); off-scale markers keep the exotic bands discoverable. The mockup renders this (inner-focus default +
> Full-range toggle + off-scale legend markers) on the Alt-HZ and Ice-Line panels.

> **Tests:** the new `prepare_*` viz preps get offline shape tests in `tests/test_viz_phase_o.py` (the Phase O viz
> scaffold) or a new `tests/test_viz_phase_p.py` — assert ring/band/bar data shape, the +4 alt-HZ bands, the V2
> relabels, and that `make_orbits_canvas` with no `snow_au`/`solvent_bands` is unchanged (additivity guard).
