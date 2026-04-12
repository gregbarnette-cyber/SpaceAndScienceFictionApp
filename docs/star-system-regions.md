# Star System Regions Feature Documentation

Options 8–10. All three variants produce identical output tables and share the same six rendering helpers. They change together when physics formulas or table layouts are revised.

## Star System Regions Feature

All three Star System Regions variants (options 8, 9, 10) produce identical output tables. They differ only in how their input values are obtained.

### Option 8: Star System Regions (SIMBAD) — `query_star_system_regions()`

- Menu option 8: fully automated — SIMBAD lookup + BC CSV lookup; `sunlightIntensity = 1.0`, `bondAlbedo = 0.3` hardcoded.
- **Spectral type validation:** extracted from SIMBAD `sp_type`. If the type does not contain an OBAFGKM class letter (e.g. white dwarfs like DA, DZ), a message is printed and the function returns early.
- **CSV lookup:** `_load_main_sequence_data()` loads `propertiesOfMainSequenceStars.csv` (lazy, cached in `_MAIN_SEQUENCE_DATA`) into `{letter: [(subtype_float, row_dict), ...]}` sorted ascending by subtype.
  - `_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")` — negative lookbehind prevents matching an OBAFGKM letter that is preceded by another uppercase letter (e.g. the `A` in `DA1.9` is excluded).
  - `_parse_spectral_class(sp_str)` uses `_SP_PATTERN.search()` to extract `(letter, subtype_float)`.
  - `_lookup_spectral_type(sp_str)` applies a **ceiling rule**: finds the smallest available subtype number ≥ the requested subtype (e.g. G1 → G2, G6 → G8, A4 → A5). If all entries in the class are cooler than requested (subtype exceeds all), advances to the next cooler letter class's hottest entry (e.g. F9 → G0). `_LETTER_SEQUENCE = ["O","B","A","F","G","K","M"]` defines the cross-letter fallthrough order.
- **Values extracted and validated** (all required; each triggers message + early return if missing):
  - `boloLum` — `Bolo. Corr. (BC)` from the matched CSV row (float)
  - `temp` — temperature in K from SIMBAD `mesfe_h.teff`
  - `vmag` — apparent magnitude from SIMBAD `V`
  - `plx` — parallax in mas from SIMBAD `plx_value`; also rejected if `<= 0`
- **Constants:** `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`

### Option 9: Star System Regions (Semi-SIMBAD) — `query_star_system_regions_semi_manual()`

- Menu option 9: same SIMBAD lookup, checks, and BC CSV lookup as option 8, but prompts the user for `sunlightIntensity` and `bondAlbedo` after all validations pass.
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
  - `lightYears = 3.2616 / trigParallax`
  - `parsecs` already computed as `1000.0 / plx`
  - Columns: Parallax (2dp), Trig Parallax (4dp), Parsecs (4dp), Light Years (4dp)
- **Earth Equivalent Orbit Properties table** — rendered by `_display_earth_equivalent_orbit()`; uses `_print_table()` (two-line header row, all columns right-aligned):
  - `distAU = sqrt(bcLuminosity / sunlightIntensity)`
  - `distKM = distAU × 149000000`
  - `planetaryYear = sqrt(distAU³ / stellarMass)`
  - `planetaryTemperature = 374 × 1.1 × (1 - bondAlbedo) × sunlightIntensity ** 0.25`
  - `planetaryTemperatureC = planetaryTemperature - 273.15`
  - `planetaryTemperatureF = (planetaryTemperatureC × 9/5) + 32`
  - `starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)`; `sizeOfSun = f"{starAngularDiameter:.2f}°"`
  - Columns: Distance AU (4dp), Distance KM (5e), Year (4dp), Temp K (2dp), Temp C (2dp), Temp F (2dp), Size of Sun (degree string)
- **Solar System Regions table** — rendered by `_display_solar_system_regions()`; uses `_print_table()` (Region | AU, left-aligned); AU formatted as `{val:.4f} ({val × 8.3167:.3f} LM)`:
  - `sysilGrav = 0.2 × stellarMass`, `sysilSunlight = sqrt(bcLuminosity/16)`
  - `hzil = sqrt(bcLuminosity/1.1)`, `hzol = sqrt(bcLuminosity/0.53)`
  - `snowLine = sqrt(bcLuminosity/0.04)`, `lh2Line = sqrt(bcLuminosity/0.0025)`, `sysol = 40 × stellarMass`
- **Solar System Alternate Habitable Zone Regions table** — rendered by `_display_alternate_hz_regions()`; same 2-column format as Solar System Regions; all 12 values computed as `sqrt(bcLuminosity / divisor)`:
  - Fluorosilicone-Fluorosilicone Inner/Outer (÷52, ÷29.9), Fluorocarbon-Sulfur Inner/Outer (÷38.7, ÷3.2)
  - Protein-Water Inner/Outer (÷2.8, ÷0.8), Protein-Ammonia Inner/Outer (÷0.48, ÷0.21)
  - Polylipid-Methane Inner/Outer (÷0.023, ÷0.0094), Polylipid-Hydrogen Inner/Outer (÷0.0025, ÷0.000024)
- **Calculated Habitable Zone table** — rendered by `_display_calculated_hz()`; uses `_print_table()` (4 columns: Zone + 3 luminosity AU columns, all left-aligned); AU formatted as `{au:.3f} ({au × 8.3167:.3f} LM)`:
  - `calculatedLuminosity = stellarRadius² × (temp/5778)⁴`
  - Uses same Kopparapu et al. coefficients as `_display_habitable_zone()` in `docs/star-databases.md`
  - Three columns: Bolometric Luminosity (`bcLuminosity`), Luminosity from Mass (`luminosityFromMass`), Calculated Luminosity
  - Six zones in order: Optimistic Inner HZ (Recent Venus), Conservative Inner HZ (RG 5 Earth Mass), Conservative Inner HZ (Runaway Greenhouse), Conservative Inner HZ (RG 0.1 Earth Mass), Conservative Outer HZ (Maximum Greenhouse), Optimistic Outer HZ (Early Mars)
