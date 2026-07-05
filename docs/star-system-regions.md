# Star System Regions Feature Documentation

Options 8–10. All three variants produce identical output tables and share the same six rendering helpers. They change together when physics formulas or table layouts are revised.

## Star System Regions Feature

All three Star System Regions variants (options 8, 9, 10) produce identical output tables. They differ only in how their input values are obtained.

### Option 8: Star System Regions (SIMBAD) — `query_star_system_regions()`

- Menu option 8: fully automated — SIMBAD lookup + BC DB lookup; `sunlightIntensity = 1.0`, `bondAlbedo = 0.3` hardcoded.
- After the Calculated HZ table, the CLI queries the Hypatia Catalog for stellar properties and elemental abundances (see Hypatia Catalog section below). Hypatia errors are shown inline but do not abort the function.
- **Spectral type validation:** extracted from SIMBAD `sp_type`. If the type does not contain an OBAFGKM class letter (e.g. white dwarfs like DA, DZ), a message is printed and the function returns early.
- **DB lookup:** `_load_main_sequence_data()` queries the `main_sequence_stars` DB table (lazy, cached in `_MAIN_SEQUENCE_DATA`) and builds `{letter: [(subtype_float, row_dict), ...]}` sorted ascending by subtype. Row dicts use the original CSV column names so all callers work unchanged.
  - `_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")` — negative lookbehind prevents matching an OBAFGKM letter that is preceded by another uppercase letter (e.g. the `A` in `DA1.9` is excluded).
  - `_parse_spectral_class(sp_str)` uses `_SP_PATTERN.search()` to extract `(letter, subtype_float)`.
  - `_lookup_spectral_type(sp_str)` applies a **ceiling rule**: finds the smallest available subtype number ≥ the requested subtype (e.g. G1 → G2, G6 → G8, A4 → A5). If all entries in the class are cooler than requested (subtype exceeds all), advances to the next cooler letter class's hottest entry (e.g. F9 → G0). `_LETTER_SEQUENCE = ["O","B","A","F","G","K","M"]` defines the cross-letter fallthrough order.
- **Values extracted and validated** (all required; each triggers message + early return if missing):
  - `boloLum` — `Bolo. Corr. (BC)` from the matched DB row (float)
  - `temp` — temperature in K from SIMBAD `mesfe_h.teff`
  - `vmag` — apparent magnitude from SIMBAD `V`
  - `plx` — parallax in mas from SIMBAD `plx_value`; also rejected if `<= 0`
- **Constants:** `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`

### Option 9: Star System Regions (Semi-SIMBAD) — `query_star_system_regions_semi_manual()`

- Menu option 9: same SIMBAD lookup, checks, and BC DB lookup as option 8, but prompts the user for `sunlightIntensity` and `bondAlbedo` after all validations pass.
- Prompts (loop until valid float entered):
  - `Enter Sunlight Intensity (Terra = 1.0):` — blank defaults to `1.0`
  - `Enter Bond Albedo (Terra = 0.3, Venus = 0.9):` — blank defaults to `0.3`

### Option 10: Star System Regions (Manual) — `query_star_system_regions_manual()`

- Menu option 10: no SIMBAD lookup, no checks, no CSV lookup. All six input values are entered manually.
- Prompts (loop until valid float entered, no defaults):
  - `Apparent Magnitude (V)`
  - `Parallax (mas)` — rejected if `<= 0`
  - `Bolometric Correction (BC)`
  - `Star Effective Temperature (K)`
  - `Sunlight Intensity (Terra = 1.0)`
  - `Bond Albedo (Terra = 0.3, Venus = 0.9)`
- Uses a shared `prompt_float(label)` helper defined inside the function.
- **`query.py`:** the manual variant is exposed as `star-regions-manual --vmag --bc --teff --parallax [--sunlight-intensity --bond-albedo]` (core `regions.compute_star_system_regions(vmag, boloLum, temp, plx, sunlight_intensity=1.0, bond_albedo=0.3)`). Returns the same flat region-values dict as `sol-regions` / the SIMBAD `star-regions` (minus the `spectral_type`/`bc_key`/`simbad`/`hypatia` extras). Non-self-validating: `--parallax 0` → raw `"division by zero"` (exit 1), negative parallax → `"math domain error"`. See `docs/integration.md`.

### Shared calculations and output tables (all three options)

- **Constants defined for later sections:** `sunlightIntensity` and `bondAlbedo` (source varies by option)
- **Star System Properties table** — rendered by `_display_star_system_properties()` after all validations pass:
  - `parsecs = 1000.0 / plx`
  - `absMagnitude = vmag + 5 - (5 × log10(parsecs))`
  - `bcAbsMagnitude = absMagnitude + boloLum`
  - `bcLuminosity = 2.52 ** (4.85 - bcAbsMagnitude)`
  - `stellarMass = bcLuminosity ** 0.2632` (intermediate, not displayed)
  - `luminosityFromMass = stellarMass ** 3.5`
  - Table rows (label | value): Apparent Magnitude (3dp), Absolute Magnitude (3dp), Bolometric Absolute Magnitude (3dp), Bolometric Luminosity (6dp), Luminosity from Mass (5dp), BC (1dp), Star Temperature K (integer)
  - Column widths computed dynamically; labels left-justified, values right-justified, separated by ` | `
- **Stellar Properties table** — rendered by `_display_stellar_properties()` after the Star System Properties table; uses `_print_table()` (single header row, all columns right-aligned):
  - `stellarRadius = stellarMass ** 0.57` if `stellarMass >= 1`, else `stellarMass ** 0.8`
  - `stellarDiameterSol = ((5780²) / (temp²)) × √bcLuminosity`
  - `stellarDiameterKM = stellarDiameterSol × 1391600`
  - `mainSeqLifeSpan = 10¹⁰ × (1 / stellarMass) ** 2.5`
  - Columns: Stellar Mass (4dp), Stellar Radius (5dp), Stellar Diameter Sol (4dp), Stellar Diameter KM (5e), Main Sequence Life Span (5e)
- **Star Distance table** — rendered by `_display_star_distance()`; uses `_print_table()` (single header row, all columns right-aligned):
  - `trigParallax = plx / 1000`
  - `lightYears = 3.26156 / trigParallax`
  - `parsecs` already computed as `1000.0 / plx`
  - Columns: Parallax (2dp), Trig Parallax (4dp), Parsecs (4dp), Light Years (4dp)
- **Earth Equivalent Orbit Properties table** — rendered by `_display_earth_equivalent_orbit()`; uses `_print_table()` (two-line header row, all columns right-aligned):
  - `distAU = sqrt(bcLuminosity / sunlightIntensity)`
  - `distKM = distAU × 149597870.7` (the canonical `_KM_PER_AU`; was `149000000`, 0.4% low)
  - `planetaryYear = sqrt(distAU³ / stellarMass)`
  - `planetaryTemperature = 314.9 × (1 - bondAlbedo)^0.25 × sunlightIntensity^0.25` (Phase P P1e — the M1 surface model; the corrected `(1−A)^0.25` albedo exponent. Identical to the legacy `374 × 1.1 × (1−A) × S^0.25` at A=0.3 → 288 K, but physically correct at every other albedo — the old linear `(1−A)` collapsed unrealistically at high albedo, e.g. Venus → ~110 K below its 227 K equilibrium temp.)
  - `planetaryTemperatureC = planetaryTemperature - 273.15`
  - `planetaryTemperatureF = (planetaryTemperatureC × 9/5) + 32`
  - `starAngularDiameter = 57.3 × (stellarDiameterKM / distKM)` (small-angle rad→deg; was the buggy `57.3 **`, which rendered the Sun at ~1.04° instead of ~0.53°); `sizeOfSun = f"{starAngularDiameter:.2f}°"`
  - Columns: Distance AU (4dp), Distance KM (5e), Year (4dp), Temp K (2dp), Temp C (2dp), Temp F (2dp), Size of Sun (degree string)

> **Phase P — two temperature models (M1 / M2).** The region rows below split across two
> physically-distinct reference temperatures, centralized as `core.equations._t_ref_surface`
> / `_t_ref_equilibrium` (so the calculators and the regions display can't drift). Both fix the
> legacy albedo bug — radiative equilibrium scales as `(1−A)^0.25` (a fourth root), **not** the
> old linear `(1−A)`:
> - **M1 surface** `T_ref = 314.9 × (1−A)^0.25` (= 288 K at A=0.3): equilibrium **+ Earth-like
>   greenhouse**. Used for the **solvent liquid bands** (the Alternate HZ Regions table) and the
>   corrected `planetaryTemperature` (P1e). Solvent-band implied-T is shown at the A=0.3 / 288 K
>   reference.
> - **M2 equilibrium** `T_ref = 278.5 × (1−A)^0.25` (278.5 K at A=0): bare radiative equilibrium,
>   **no greenhouse**. Used for the **snow / ice condensation lines** (`snowLine`, `lh2Line`, the
>   P3 ice fronts). Implied-T shown at A=0.
>
> Shared: `S_eff(T) = (T/T_ref)^4`, `AU = sqrt(L / S_eff)`. The P7a implied-edge-T helper
> `implied_edge_temp(au, L, model)` inverts this to annotate each row. See `docs/equations.md`
> (the two calculators) and `PHASE_P_PLAN.md` §0.

- **Solar System Regions table** — rendered by `_display_solar_system_regions()`; uses `_print_table()` (Region | AU, left-aligned); AU formatted as `{val:.4f} ({val × 8.3167:.3f} LM)`:
  - `sysilGrav = 0.2 × stellarMass`, `sysilSunlight = sqrt(bcLuminosity/16)`
  - `hzil = sqrt(bcLuminosity/1.1)`, `hzol = sqrt(bcLuminosity/0.53)`
  - `snowLine = sqrt(bcLuminosity/0.139)`, `lh2Line = sqrt(bcLuminosity/0.0025)`, `sysol = 40 × stellarMass`
    - **Phase P P1c (snow line):** the divisor was corrected `0.04 → 0.139` — the canonical **170 K water snow line at ~2.68 AU** (M2 equilibrium model; Hayashi 1981). The legacy `0.04` (5.0 AU / 129 K) was the greenhouse-baked **surface** model misapplied to an ice-condensation line. The display label is **"Water Snow Line"** (was "Snow Line").
    - **Phase P P1b (lh2Line):** value **unchanged** — under the M2 equilibrium model the `0.0025` divisor is correct (62 K / 20 AU = the **N₂/CO 1-atm surface-frost line**); only the display label changed to **"N₂/CO (1-atm) Condensation"** (was "Liquid Hydrogen (LH2) Line").
- **Solar System Alternate Habitable Zone Regions table** — rendered by `_display_alternate_hz_regions()`; AU + an implied-T column (Phase P P7a) sorted by **AU ascending**; values computed as `sqrt(bcLuminosity / divisor)`. The six Asimov bands plus the Phase P P2 additions (10 bands / 20 edges):
  - Fluorosilicone-Fluorosilicone Inner/Outer (÷52, ÷29.9) — **hypothetical high-T silicone analog** (~670–770 K; Phase P P1d label-only), Fluorocarbon-Sulfur Inner/Outer (÷38.7, ÷3.2)
  - Protein-Water Inner/Outer (÷2.8, ÷0.8), Protein-Ammonia Inner/Outer (÷0.48, ÷0.21)
  - Polylipid-Methane Inner/Outer (÷0.023, ÷0.0094), **Polylipid-Hydrogen Inner/Outer (÷0.0000247, ÷0.0000053)** — Phase P P1a value correction (was ÷0.0025, ÷0.000024; the legacy inner edge was supercritical and the outer sat at the boil point; now the real H₂ 1-atm liquid range ≈ 200–440 AU)
  - **Phase P P2 (additive, M1):** Carbon Dioxide Inner/Outer (÷1.243, ÷0.320 — pressure-conditional, ≥5.2 atm), Liquid Sulfur (÷38.59, ÷3.309), Water-Ammonia Eutectic (÷0.8075, ÷0.1395), Sulfuric Acid (÷20.13, ÷0.940). These are derived from the shared `core.equations._SOLVENTS` liquid ranges via `compute_solvent_zone` at A=0.3, so they can't drift from the Solvent Habitable Zone calculator.
  - **Phase P P3 (additive, M2):** the ice-condensation fronts `iceLineNH3`/`iceLineCO2`/`iceLineN2`/`iceLineCO` (CO₂/NH₃/N₂/CO; N₂/CO are disk-set) are added to the regions dict via `compute_ice_lines` and flow through `query.py` (not displayed as table rows).
- **Calculated Habitable Zone table** — rendered by `_display_calculated_hz()`; uses `_print_table()` (4 columns: Zone + 3 luminosity AU columns, all left-aligned); AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`:
  - `calculatedLuminosity = stellarRadius² × (temp/5778)⁴`
  - Uses same Kopparapu et al. coefficients as `_display_habitable_zone()` in `docs/star-databases.md`
  - Three columns: Bolometric Luminosity (`bcLuminosity`), Luminosity from Mass (`luminosityFromMass`), Calculated Luminosity
  - Six zones in order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars)

## Hypatia Catalog (opt 8 only)

Opt 8 appends Hypatia Catalog data after the Calculated HZ output in both the CLI and GUI.

> See `docs/hypatia_catalog_api.md` for a reference overview of the external Hypatia Catalog data source and its public API (what it covers, endpoints, no API key required). That file is reference-only — it is not `@`-loaded by CLAUDE.md.

### CLI output (`query_star_system_regions()`)

After `_display_calculated_hz()`, a `simbad_compat` dict is built from the SIMBAD result variables already in scope (`designations`, `result[0]["main_id"]`) and passed to `core.databases.compute_hypatia_data()`. Output:

- **Header**: `Hypatia Catalog Data` / `--------------------`
- **Properties + Kinematics table** (single row via `_print_table`): T_eff (K), log g, Spectral Type, V mag, B-V, Distance (pc), Disk, U (km/s), V (km/s), W (km/s), PM RA (mas/yr), PM Dec (mas/yr).
- **Elemental Abundances** — grouped by nucleosynthetic family. For each non-empty category (in `core.hypatia_elements.CATEGORIES` order: Light, Volatile (CNO), Alpha, Odd-Z, Iron-peak, s-process (light), s/r-process (heavy), r-process / rare earth, Heavy / actinide), prints a category sub-header line followed by its own `_print_table`: Element (e.g. `Ba II`), Name, [X/H] Mean (±-prefixed), ±Std, Min (±-prefixed), Max (±-prefixed), # Catalogs. Printed only when the abundances list is non-empty; otherwise prints `"No elemental abundance data available for this star."`. `# Catalogs` is now populated from the response's `catalogs_linear` length. Element symbol → full name comes from `core.hypatia_elements.display_symbol` / the per-row `name` field (no local name dict).
- Hypatia errors print inline without blocking the `input()` prompt.

### GUI tabs (`_build_region_tabs()` in `gui/panels/star_regions.py`)

`_build_region_tabs(d, viz_widget=None)` reads `d.get("hypatia")`. When present:

- **Data tab "Hypatia"** — `QScrollArea` with three sections built by `_build_hypatia_tab(hypatia)`:
  - **Stellar Properties table** (`make_table`): T_eff (K), log g, Spectral Type, V mag, B-V, Distance (pc), Disk.
  - **Kinematics table** (`make_table`): U (km/s), V (km/s), W (km/s), PM RA (mas/yr), PM Dec (mas/yr).
  - **Elemental Abundances (Lodders 2009)** — grouped by nucleosynthetic family: one bold category header (`CATEGORIES` label) plus its own `make_table` per non-empty category, with columns Element (`display_symbol`, e.g. `Ba II`), Name, [X/H] Mean, ±Std, Min, Max, # Catalogs. The `±Std` value is the Hypatia `plusminus` spread (dex), **not** the API's own `std` field — that field is `log₁₀` of the linear-space scatter and is negative for almost every element, so `_parse_hypatia_composition` reads `plusminus` instead. If abundances list is empty, shows a gray italic label instead.
  - Error state: single gray italic label with the error message.
- **Viz tab "Abundance Profile"** (added to `viz_widget` when `mpl_available()` and abundances list non-empty) — horizontal bar chart via `make_abundance_canvas()` in `gui/visualizations/plot_helpers.py`: bars colored by **nucleosynthetic-family category** (colors from `CATEGORIES`; a one-row gap separates groups), with a category legend, `axvline` at 0 (solar reference), and error bars from the `std` field (the Hypatia `plusminus` spread; `make_abundance_canvas` clamps any negative value to 0 defensively, since matplotlib ≥ 3.6 rejects negative `xerr`). With up to ~100 bars the canvas is wrapped via `wrap_scrollable()` so it scrolls vertically instead of squashing. Title: `[X/H] Elemental Abundances — {star_name}`. This is one of opt 8's Hypatia-dependent viz tabs — it joins the always-present HZ Diagram, System Regions Diagram, and Alternate HZ Diagram (see `docs/gui-architecture.md`). Opts 9/10 show only those first three.
- **Viz tab "Kinematics"** (Phase O O11; added beside Abundance Profile when Hypatia returns all three U/V/W velocities) — a Toomre / galactic-kinematics diagram via `core.viz.prepare_toomre` → `make_toomre_canvas` (`make_kinematics_tab` builds the tab, including an "ℹ What is this?" Explain button). x = V (km/s, LSR-corrected — Schönrich+ 2010 solar motion), y = √(U²+W²); dashed constant-total-velocity arcs at 50/100/180 km/s centred at the LSR origin label the thin/thick/halo populations; the star is a gold ★ with Hypatia's `disk` class in the subtitle. Opt 8 only (opts 9/10 don't call the Hypatia API).

**Phase O O10b — Honorverse hyper-limit ring (opts 8/9).** The **System Regions Diagram** tab is built by `wrap_system_regions_with_hyper_toggle`. When the star's spectral type resolves a Honorverse hyper limit (opts 8/9 — `compute_star_system_regions_from_simbad` sets `spectral_type`), `prepare_system_regions_diagram` attaches a separate `hyper_limit` overlay key and the tab gains a **"Show Honorverse Hyper Limit (fiction)"** checkbox — **unchecked by default**, so the diagram is unchanged until ticked. Ticking it rebuilds `make_system_regions_canvas(show_hyper=True)`, drawing one **dashed-red** ring (`#cc2222`) at the hyper limit's √AU radius with a fiction-flagged legend entry — styled distinctly so it reads as fiction next to the physical zones. The hyper limit is a **separate overlay**, never appended to the physical `regions` list (the canvas indexes those positionally + uses the outermost as the √AU scale). **Opt 13 (Sol)** also gets the checkbox: `compute_sol_regions()` now sets `spectral_type="G2V"` (the Sun's hyper limit ≈ 2.54 AU). **Opt 10 (Manual)** carries no `spectral_type`, so it gets no `hyper_limit` and **no checkbox** — unchanged. See `docs/science-and-scifi.md` (the ceiling-rule lookup) and `docs/gui-architecture.md`.

**Orbital Diagram ring (opts 3 / 6 / Map).** The same Honorverse hyper limit is also offered on the **Orbital Diagram** (`make_orbits_canvas`, which shows the actual planet orbits): when the host spectral type resolves (NASA `st_spectype` / HWC `S_TYPE`), `wrap_orbits_with_solar_toggle` adds a second **"Show Honorverse Hyper Limit (fiction)"** checkbox alongside the O4 "Show Solar System reference" one. Ticking it passes `make_orbits_canvas(hyper_au=…)`, drawing the dashed-red ring at the limit's AU (the frame expands to fit it) so you can see where it falls **relative to the real planets**. Default off → unchanged; unresolvable type (e.g. a white dwarf) → no second checkbox.

Opts 9 and 10 do not call the Hypatia API — `d.get("hypatia")` returns `None` and no Hypatia tab is added.

### `core/databases.compute_hypatia_data(simbad_result)`

- API base: `https://hypatiacatalog.com/hypatia/api/v2`
- Name resolution: uses `simbad_result["designations"].get("HIP")` → `"HD"` → `simbad_result["main_id"]`.
- HTTP calls via `_with_retries(requests.get, ...)` with `timeout=30`:
  - `/star?name=<name>` → stellar properties and kinematics via `_parse_hypatia_star()`
  - `/composition?name=<name>&element=...` → elemental abundances via `_parse_hypatia_composition()` (failure → `abundances=[]`, not fatal). All 104 species are requested, but the server caps the GET request line at ~4094 bytes, so they're fetched in **chunks of `_HYPATIA_COMPOSITION_CHUNK` (30)** and the responses concatenated before parsing.
- Returns `{"star_name", "properties", "abundances"}` or `{"error": str}`. Each abundance dict: `{element, name, z, category, mean, std, min, max, n}` (see `docs/integration.md`).
- Element set: the full **104 species** (Lodders 2009 normalisation), including singly-ionized species — defined in `core/hypatia_elements.py` (`HYPATIA_REQUEST_SYMBOLS`), which is the single source of truth shared by the CLI, GUI, and `query.py`. A live drift test asserts this matches `GET /element`.

### `core/viz.prepare_abundance_profile(hypatia_result)`

- Returns `{"elements", "names", "means", "stds", "categories", "colors", "star_name"}` or `{"error": str}` (parallel lists).
- `elements` uses human-readable symbols (`display_symbol`, e.g. `Ba II`); `colors` is the per-element category color. Filters to species with non-None mean; preserves the master display order.
