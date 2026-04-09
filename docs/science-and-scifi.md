# Science and Science Fiction Feature Documentation

Options 12–17. All features here display data from local CSV files or hardcoded tables. No external API calls. Lowest change frequency of all feature groups.

## Science Features

### Option 12: Solar System Planet/Dwarf Planets/Asteroids — `solar_system_data_tables()`
- Displays four sequential data tables from CSV files in the project directory.
- **Solar System Planets Data** — from `planetInfo.csv`; columns: Planet Name, Mass (J), Diameter (J), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity, Moons. AU values formatted as `{v:g} ({v × 8.3167:.3f} LM)`.
- **Moon Data tables** — from `moonInfo.csv`; grouped by planet in order: Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto; columns: Satellite Name, Diameter (km), Mass (kg), Perigee (km), Apogee (km), SemiMajor Axis (km), Eccentricity, Period (days), Gravity (m/s^2), Escape Velocity (km/s).
- **Solar System Dwarf Planets Data** — from `dwarfPlanetInfo.csv`; same columns as planets table but header row says "Dwarf Planet Name" and Mass is in Earth masses.
- **Solar System Major Asteroids Data** — from `asteroidsInfo.csv`; sorted ascending by Semimajor Axis; columns: Asteroid Name, Diameter (KM), Period, Periastron (AU), Semimajor Axis (AU), Apastron (AU), Eccentricity.

### Option 13: Main Sequence Star Properties — `main_sequence_star_properties()`
- Reads `propertiesOfMainSequenceStars.csv` and displays all rows in a single table.
- Columns: Spectral Class, B-V, Teff (K), Abs Mag Vis, Abs Mag Bol, BC, Lum, R, M, p (g/cm3), Lifetime (years).

### Option 14: Sol Solar System Regions — `sol_solar_system_regions()`
- Displays all Star System Regions output tables for the Sun using hardcoded solar constants: `vmag = -26.74`, `boloLum = -0.07`, `temp = 5778 K`, `sunlightIntensity = 1.0`, `bondAlbedo = 0.3`.
- Parallax back-computed from absolute magnitude: `plx = 1000 / (10^((vmag - absMag + 5) / 5))` ≈ 206265 mas.
- Calls the same shared display helpers documented in `docs/star-system-regions.md`: `_display_star_system_properties()`, `_display_stellar_properties()`, `_display_star_distance()`, `_display_earth_equivalent_orbit()`, `_display_solar_system_regions()`, `_display_alternate_hz_regions()`, `_display_calculated_hz()`.

## Science Fiction Features

### Option 15: Honorverse Hyper Limits by Spectral Class — `honorverse_hyper_limits()`
- Reads `spTypeHyperLM.csv` (no header; columns: Spectral Class, Light Minutes).
- Converts LM → AU: `au = lm / 8.3167`.
- Output table columns: Spectral Class | Light Minutes (2dp) | AUs (4dp).

### Option 16: Honorverse Acceleration by Mass Table — `honorverse_acceleration_by_mass()`
- Hardcoded table of ship mass ranges and acceleration values (no external data file).
- Output table columns: Ship Mass (tons) | Warship (Normal Space) | Merchantship (Normal Space) | Warship (Hyper Space) | Merchantship (Hyper Space).
- Six rows covering mass ranges from FG/DD (< 80,000 tons) through SD (7,000,000–8,499,999 tons).

### Option 17: Honorverse Effective Speed by Hyper Band — `honorverse_effective_speed()`
- Hardcoded data; displays two tables.
- **Table 1 "Effective Speed by Hyper Band"**: Alpha–Iota bands; columns: Band | Translation Bleed-Off | Velocity Multiplier | Warship (xC) | Merchantship (xC). Speeds shown as `{xc} ({xc / 8765.8128:.5f} ly/hr)`. Iota merchantship speed shown as "Currently Unattainable". Footnote about merchantmen not normally using Epsilon–Iota bands.
- **Table 2 "Effective Speed by Hyper Band (Expanded)"**: Alpha–Omega bands (24 total); columns: Band | Warship (xC) | Merchantship (xC). Same speed format as Table 1.
