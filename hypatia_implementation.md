# Hypatia Catalog Integration — Phase 1: Option 8 (Star System Regions Auto)

This document is the implementation plan for integrating the Hypatia Catalog API into
Option 8 (Star System Regions Auto) only. Once validated here, the pattern rolls out to
opts 1, 3, 4, 5, 6, and the CLI/query.py for opts 2 and 8.

---

## What gets added

- A new **"Hypatia"** data tab in the opt 8 result QTabWidget (tab 8 of 8+).
- A new **"Abundance Profile"** viz tab in the DiagramToggle view (tab 4 of 4).
- CLI opt 8 prints Hypatia tables after the existing region output.
- `query.py` `star-regions` subcommand includes Hypatia data in its JSON output.

---

## API summary

Base URL: `https://hypatiacatalog.com/hypatia/api/v2`  
No API key required.

Two endpoints used per star:

| Endpoint | Call | Returns |
|---|---|---|
| `/star` | `GET /star?name=HIP 12345` | Stellar properties (T_eff, log g, V/B mag, B-V, distance, disk, UVW, proper motion) |
| `/composition` | `GET /composition?name[]=...&element[]=...&solarnorm[]=...` | Per-element abundances (mean, median, min, max, ±std, n_catalogs) |

Elements queried (19 total, batched in one `/composition` call, Lodders 2009 normalization):
`fe, mg, si, ca, ti, o, c, n, na, al, s, ni, co, cr, mn, ba, y, sr, eu`

Star name priority for lookup: HIP → HD → MAIN_ID (all accepted as SIMBAD names).

Coverage note: FGKM stars within 500 pc + all exoplanet hosts. Stars outside this
(hot OB stars, white dwarfs, very distant targets) may return no data — handled
gracefully as a "No Hypatia data available" message in the tab.

---

## Files changed

1. `core/databases.py` — new `compute_hypatia_data()`
2. `core/viz.py` — new `prepare_abundance_profile()`
3. `gui/visualizations/plot_helpers.py` — new `make_abundance_canvas()`
4. `gui/panels/star_regions.py` — extend `_compute_auto_regions()` + `_build_region_tabs()`
5. `main.py` — extend `query_star_system_regions()` with Hypatia output
6. `query.py` — extend `star-regions` subcommand to include Hypatia data
7. `docs/star-system-regions.md` — document new tab
8. `docs/gui-architecture.md` — update viz tab table and plot_helpers list

---

## Step 1 — `core/databases.py`: add `compute_hypatia_data()`

Add the constant and function near the top of the file alongside existing archive helpers.

### Constants (module-level)

```python
_HYPATIA_BASE = "https://hypatiacatalog.com/hypatia/api/v2"
_HYPATIA_ELEMENTS = [
    "fe", "mg", "si", "ca", "ti", "o",  "c",  "n",
    "na", "al", "s",  "ni", "co", "cr", "mn",
    "ba", "y",  "sr", "eu",
]
```

### `_parse_hypatia_star(data)` — private helper

Accepts the raw `/star` JSON response (a list; take `data[0]` if non-empty).
Returns a flat dict with normalized keys:

```
teff, logg, spectral_type, vmag, bmag, bv, distance_pc,
disk, u_vel, v_vel, w_vel, pm_ra, pm_dec
```

All values are `float | str | None`. Use safe `.get()` throughout — field names in
the Hypatia response need to be confirmed against a live test call. Expected field
names based on API docs: `temperature`, `logg`, `spectral_type`, `vmag`, `bmag`,
`bv`, `dist`, `disk`, `u`, `v`, `w`, `pm_ra`, `pm_dec`. Adjust after first test call.

### `_parse_hypatia_composition(data)` — private helper

Accepts the raw `/composition` JSON response (a list of per-element dicts).
Returns a list of dicts, one per element that has a mean value:

```python
{
    "element": "Fe",   # capitalized for display
    "mean":    -0.02,
    "std":      0.05,
    "min":     -0.10,
    "max":      0.03,
    "n":        4,     # number of catalogs
}
```

Elements with no data (not in the response or mean is None) are omitted entirely.
Sort by the order of `_HYPATIA_ELEMENTS` (preserves the chemical grouping above).

### `compute_hypatia_data(simbad_result)` — public function

```
Args:  simbad_result dict from compute_simbad_lookup()
Returns:
  {
    "star_name":   str,          # name used for the lookup
    "properties":  dict,         # from _parse_hypatia_star()
    "abundances":  list[dict],   # from _parse_hypatia_composition()
  }
  or {"error": "message"}
```

Implementation notes:
- Name resolution: `desig.get("HIP") or desig.get("HD") or simbad_result.get("main_id")`
- Use `_with_retries` + `_timeout_ctx(30)` on both HTTP calls, same pattern as
  existing `_query_tap` calls.
- The `/composition` call uses parallel lists:
  `params = {"name": [star_name]*19, "element": _HYPATIA_ELEMENTS, "solarnorm": ["lodders09"]*19}`
- If `/star` returns an empty list → `{"error": "No Hypatia data for '<name>'"}`
- If `/composition` call fails, return `properties` with `abundances: []` rather than
  failing the whole function — partial data is better than nothing.
- Classify network errors via `_network_error_msg(e, "Hypatia Catalog")`.

---

## Step 2 — `core/viz.py`: add `prepare_abundance_profile()`

```
Args:  hypatia_result dict (the return value of compute_hypatia_data)
Returns:
  {
    "elements":   list[str],   # element symbols in display order
    "means":      list[float],
    "stds":       list[float], # 0.0 where std is None
    "star_name":  str,
  }
  or {"error": "message"}
```

Filters to elements that have a non-None mean. Preserves the `_HYPATIA_ELEMENTS`
ordering (chemical grouping). Returns `{"error": "No abundance data"}` if the
`abundances` list is empty or `hypatia_result` contains an error key.

---

## Step 3 — `gui/visualizations/plot_helpers.py`: add `make_abundance_canvas()`

```
Signature: make_abundance_canvas(parent, abundances_data, star_name) -> (canvas, toolbar)

abundances_data: the return value of prepare_abundance_profile()
```

Chart type: horizontal bar chart (elements on Y-axis, [X/H] on X-axis).

Rendering details:
- Figure background: `#f5f5f5` (matches all other canvases in this file).
- Y-axis: element symbols, bottom-to-top order matching `_HYPATIA_ELEMENTS` order
  (so Fe is near top, Eu near bottom — iron-peak at top, s-process at bottom).
- X-axis: [X/H] value; zero line drawn in dark gray (solar reference).
- Bars: single color (`#4a90d9`) for positive abundances, `#e06c4a` for negative.
- Error bars: horizontal, using `std` values; color `#333333`, capsize 4.
- Title: `f"[X/H] Elemental Abundances — {star_name}"`.
- Axis label: `[X/H] (Lodders 2009)`.
- Grid: vertical lines only, `#cccccc`, alpha 0.5.
- If `abundances_data` contains an error key, return a canvas with a centered
  error-message text annotation instead of raising.

---

## Step 4 — `gui/panels/star_regions.py`: extend auto panel

### 4a — extend `_compute_auto_regions()`

Current:
```python
def _compute_auto_regions(name: str) -> dict:
    simbad = core.databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    return core.regions.compute_star_system_regions_from_simbad(simbad)
```

New:
```python
def _compute_auto_regions(name: str) -> dict:
    simbad = core.databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    result = core.regions.compute_star_system_regions_from_simbad(simbad)
    if "error" in result:
        return result
    result["hypatia"] = core.databases.compute_hypatia_data(simbad)
    return result
```

Key point: a Hypatia error is stored in `result["hypatia"]` as `{"error": "..."}` and
does not prevent the regions result from being returned. The render layer handles it.

### 4b — extend `_build_region_tabs()`

Add a `hypatia=None` parameter.

After the existing 7 data tabs (before the viz section), add:

```python
if hypatia is not None:
    tabs.addTab(_build_hypatia_tab(hypatia), "Hypatia")
```

`_build_hypatia_tab(hypatia)` is a new private function (see below).

In the viz section, after the existing HZ / System Regions / Alt HZ diagram tabs:

```python
if mpl_available() and hypatia and "error" not in hypatia:
    ab_data = core.viz.prepare_abundance_profile(hypatia)
    if "error" not in ab_data:
        ab_w = QWidget()
        ab_layout = QVBoxLayout(ab_w)
        canvas, toolbar = make_abundance_canvas(
            target, ab_data, hypatia.get("star_name", "")
        )
        ab_layout.addWidget(toolbar)
        ab_layout.addWidget(canvas)
        target.addTab(ab_w, "Abundance Profile")
```

(`target` is `viz_widget` when provided, else the `tabs` widget itself — same pattern
as the existing HZ and System Regions diagram tabs.)

### 4c — new `_build_hypatia_tab(hypatia)` helper

Returns a `QWidget` (wrapped in a `QScrollArea`) containing:

**If `hypatia` has an `"error"` key:**
- Single `QLabel` showing the error message in gray italic.

**Otherwise, two sections:**

Section 1 — "Stellar Properties" label + table via `_tbl()`:

| Column | Source field | Format |
|---|---|---|
| T_eff (K) | `properties["teff"]` | integer |
| log g | `properties["logg"]` | 3 dp |
| Spectral Type | `properties["spectral_type"]` | string |
| V mag | `properties["vmag"]` | 3 dp |
| B-V | `properties["bv"]` | 3 dp |
| Distance (pc) | `properties["distance_pc"]` | 2 dp |
| Disk | `properties["disk"]` | string (thin / thick / halo) |

Section 2 — "Kinematics" label + table:

| Column | Source field | Format |
|---|---|---|
| U (km/s) | `properties["u_vel"]` | 2 dp |
| V (km/s) | `properties["v_vel"]` | 2 dp |
| W (km/s) | `properties["w_vel"]` | 2 dp |
| PM RA (mas/yr) | `properties["pm_ra"]` | 3 dp |
| PM Dec (mas/yr) | `properties["pm_dec"]` | 3 dp |

Section 3 — "Elemental Abundances (Lodders 2009)" label + table:

| Column | Source | Format |
|---|---|---|
| Element | `a["element"]` | string |
| [X/H] Mean | `a["mean"]` | +0.000 (always show sign) |
| ±Std | `a["std"]` | 0.000 |
| Min | `a["min"]` | +0.000 |
| Max | `a["max"]` | +0.000 |
| # Catalogs | `a["n"]` | integer |

All three sections are present only when the corresponding data exists. Missing
individual field values show "N/A".

### 4d — update `StarRegionsAutoPanel._render()`

Pass `result.get("hypatia")` into `_build_region_tabs()`:

```python
tabs = _build_region_tabs(result, viz_widget=viz_widget, hypatia=result.get("hypatia"))
```

(The other two region panels — Semi-Manual (9) and Manual (10) — do not get Hypatia
in this phase. They don't call `_compute_auto_regions()`.)

---

## Step 5 — `main.py`: extend `query_star_system_regions()`

Locate the existing `query_star_system_regions()` function (CLI opt 8). After the final
table is displayed and before the "Press Enter to Return" prompt:

1. Call `compute_hypatia_data(simbad_result)`.
   - `simbad_result` is already available in the function from the SIMBAD lookup.
2. Print `"\nHypatia Catalog Data"` header.
3. If error: print the error message and continue to the prompt.
4. If OK: print two tables using the existing `_print_table()` helper pattern:
   - **Stellar Properties table**: T_eff, log g, Spectral Type, V mag, B-V,
     Distance (pc), Disk, U (km/s), V (km/s), W (km/s), PM RA, PM Dec.
   - **Elemental Abundances table**: Element | [X/H] Mean | ±Std | Min | Max | # Catalogs.

The same graceful-skip behavior applies: a Hypatia network error must not crash or
suppress the existing region tables that were already printed.

---

## Step 6 — `query.py`: new `hypatia-data` subcommand + extend `star-regions`

### 6a — new `hypatia-data` subcommand

This is a standalone lookup — SIMBAD first, then Hypatia. It follows the exact same
two-step pattern as `hwo-exep`, `mission-exocat`, and `hwc`.

**New handler (add alongside the other `cmd_*` functions):**
```python
def cmd_hypatia_data(args):
    _out(_simbad_then(args.star, databases.compute_hypatia_data))
```

`_simbad_then` already handles the SIMBAD error path, so this is a one-liner.

**New parser entry (add in `main()` alongside the other subparsers):**
```python
# hypatia-data
p = sub.add_parser("hypatia-data",
                   help="Hypatia Catalog stellar properties and elemental abundances")
p.add_argument("--star", required=True)
p.set_defaults(func=cmd_hypatia_data)
```

**Invocation:**
```bash
python query.py hypatia-data --star "Tau Ceti"
python query.py hypatia-data --star "61 Cygni A"
python query.py hypatia-data --star "HIP 64394"
```

**JSON output on success:**
```json
{
  "star_name": "HIP 64394",
  "properties": {
    "teff": 5344,
    "logg": 4.49,
    "spectral_type": "G8V",
    "vmag": 3.49,
    "bmag": 4.22,
    "bv": 0.73,
    "distance_pc": 3.65,
    "disk": "thin",
    "u_vel": -18.5,
    "v_vel": -16.4,
    "w_vel": -2.1,
    "pm_ra": -1721.05,
    "pm_dec": 853.32
  },
  "abundances": [
    {"element": "Fe", "mean": -0.35, "std": 0.06, "min": -0.43, "max": -0.27, "n": 5},
    {"element": "Mg", "mean":  0.01, "std": 0.04, "min": -0.02, "max":  0.05, "n": 3},
    {"element": "Si", "mean": -0.10, "std": 0.03, "min": -0.13, "max": -0.08, "n": 4}
  ]
}
```

**JSON output on error** (star not in catalog, network failure, SIMBAD miss):
```json
{"error": "No Hypatia data for 'HIP 99999'"}
```
Exit code 1, consistent with all other error paths.

---

### 6b — extend `cmd_star_regions()`

`cmd_star_regions` currently uses `_simbad_then`, which only passes the SIMBAD result
to one function. Since we need to call both `compute_star_system_regions_from_simbad`
and `compute_hypatia_data` on the same SIMBAD result, expand it to a full handler:

```python
def cmd_star_regions(args):
    simbad = databases.compute_simbad_lookup(args.star)
    if "error" in simbad:
        _out(simbad)
        return
    result = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" not in result:
        result["hypatia"] = databases.compute_hypatia_data(simbad)
    _out(result)
```

Key behaviors:
- If SIMBAD fails → return the SIMBAD error immediately (unchanged from current).
- If regions computation fails → return the regions error immediately (no Hypatia call).
- If regions succeeds but Hypatia fails → `result["hypatia"]` is `{"error": "..."}`;
  the regions data is still returned and exit code is 0 (regions succeeded).
- If both succeed → `result["hypatia"]` is the full Hypatia dict.

**JSON output shape** (abbreviated — full regions dict unchanged, hypatia appended):
```json
{
  "vmag": -26.74,
  "absMagnitude": 4.83,
  "bcLuminosity": 0.999543,
  "... all existing region keys ...": "...",
  "hypatia": {
    "star_name": "HIP 71683",
    "properties": { "..." },
    "abundances": [ "..." ]
  }
}
```

**Backward compatibility:** Callers that already consume `star-regions` output and
ignore unknown keys are unaffected. The `hypatia` key is always present in successful
results; callers must check `"error" in result["hypatia"]` before using it.

---

### 6c — `docs/integration.md` additions

Two entries to add:

**Under "Star data" section:**
```
#### `hypatia-data`
Hypatia Catalog stellar properties and elemental abundances (live network call).
```bash
query.py hypatia-data --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hypatia_data`
```

**Update the `star-regions` entry** to note that a successful result now includes a
top-level `"hypatia"` key containing stellar properties and elemental abundances.
Note that callers should check `result["hypatia"]` for a nested `"error"` key, since
Hypatia data is fetched independently and may fail even when regions data succeeds.

**Under "Two-step subcommands" note** — add `hypatia-data` to the list.

---

## Step 7 — Documentation updates

### `docs/star-system-regions.md`

Add a new subsection under Option 8 ("Star System Regions (SIMBAD)"):

**Hypatia Catalog tab (opt 8 only):**
- Fetched via `compute_hypatia_data(simbad_result)` after region computation.
- Data tab 8: "Hypatia" — Stellar Properties table (T_eff, log g, spectral type, V mag,
  B-V, distance, disk membership), Kinematics table (U/V/W, proper motion), Elemental
  Abundances table (19 elements, Lodders 2009, mean/std/min/max/n).
- Viz tab 4: "Abundance Profile" — horizontal bar chart of [X/H] per element.
- If Hypatia returns no data for the star, the tab shows a message; remaining tabs
  are unaffected.

### `docs/gui-architecture.md`

- Add `make_abundance_canvas(parent, abundances_data, star_name)` to the plot_helpers
  table with description "Horizontal bar chart of [X/H] per element with ±std error bars".
- Update the `StarRegionsAutoPanel` row in the "Panels with embedded viz tabs" table:
  change `"HZ Diagram", "System Regions Diagram"` to
  `"HZ Diagram", "System Regions Diagram", "Abundance Profile" (when Hypatia data available)`.
- Update `_build_region_tabs()` description to note the `hypatia=None` parameter and
  the two new tabs it adds.
- Add `prepare_abundance_profile(hypatia_result)` to the `core/viz.py` public API table.

### `docs/integration.md`

- Add `hypatia-data` subcommand entry under the "Star data" section (see Step 6c).
- Update the `star-regions` entry to document the new `hypatia` key in the output.
- Add `hypatia-data` to the "Two-step subcommands" list.

---

## Implementation order

1. `core/databases.py` — `compute_hypatia_data()` and helpers. **Test with a live
   API call before touching any GUI code** (verify actual JSON field names from
   the `/star` and `/composition` responses).
2. `query.py` — add `hypatia-data` subcommand (Step 6a). This lets you test the core
   function end-to-end from the command line immediately: `python query.py hypatia-data
   --star "Tau Ceti"`. Validates field names, JSON shape, and error paths before any
   GUI or CLI work.
3. `core/viz.py` — `prepare_abundance_profile()`.
4. `gui/visualizations/plot_helpers.py` — `make_abundance_canvas()`.
5. `gui/panels/star_regions.py` — `_build_hypatia_tab()`, then `_build_region_tabs()`
   extension, then `_compute_auto_regions()` extension, then `_render()` update.
6. `main.py` — CLI Hypatia output in `query_star_system_regions()`.
7. `query.py` — extend `cmd_star_regions()` (Step 6b).
8. `docs/` updates (Steps 7 + 6c).

---

## Testing checklist

**`query.py hypatia-data` (validate core before GUI work):**
- [ ] `python query.py hypatia-data --star "Tau Ceti"` — full JSON with properties +
      abundances; confirm actual API field names match `_parse_hypatia_star()`.
- [ ] `python query.py hypatia-data --star "61 Cygni A"` — rich abundance data star.
- [ ] `python query.py hypatia-data --star "Vega"` — hot A-type; confirm graceful
      `{"error": ...}` with exit code 1.
- [ ] `python query.py hypatia-data --star "XYZZY NotAStar"` — SIMBAD miss; confirm
      SIMBAD error returned, exit code 1.

**`query.py star-regions` (extended output):**
- [ ] `python query.py star-regions --star "Tau Ceti"` — output includes `hypatia` key
      with full data alongside all existing region keys.
- [ ] `python query.py star-regions --star "Vega"` — output includes `hypatia` key
      with `{"error": "..."}` but all region keys are present and exit code is 0.

**GUI opt 8:**
- [ ] Known FGKM star with rich data (e.g., Tau Ceti, 61 Cygni A) — all three Hypatia
      tables populate correctly; Abundance Profile tab renders.
- [ ] Star with sparse element data (few elements measured) — partial abundances table;
      no crash; Abundance Profile shows only available elements.
- [ ] Star not in Hypatia catalog (e.g., a hot O-type or white dwarf) — "No Hypatia data"
      message in the Hypatia tab; all 7 existing region tabs unaffected.
- [ ] Network failure (run with network disabled) — error message in Hypatia tab; other
      tabs still render from the successful regions computation.
- [ ] GUI reset — clicking a new star after a previous search correctly clears and
      re-renders the Hypatia tab.

**CLI opt 8:**
- [ ] Hypatia tables print after region tables for a known FGKM star.
- [ ] Error path (star not in catalog) prints a single message; region tables already
      printed above are unaffected.

---

## Future phases (not in scope here)

After opt 8 is validated:
- **Opts 4, 5, 6** (DiagramToggleMixin panels): convert `_tables_widget` from scroll area
  to QTabWidget; add Hypatia tab + Abundance Profile viz tab.
- **Opt 3** (NasaPlanetarySystemsPanel): same tab conversion around existing inline toggle.
- **Opt 1** (SimbadPanel): convert plain result area to QTabWidget; add DiagramToggleMixin.
- **Opt 2** (CLI only): append Hypatia tables to `query_exoplanets()` output.
- **Full-catalog scatter** (`/data` endpoint): [Fe/H] vs [X/H] with queried star
  highlighted — deferred until single-star feature is stable.
