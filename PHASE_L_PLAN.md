# Phase L — Exoplanet Comparison Dashboard — Implementation Plan

**Status:** ✅ **L1–L3 IMPLEMENTED (2026-06-13)** — `core/databases.compare_stars`,
`core/equations.compute_stellar_evolution`, `EsiRankingPanel` over `search_hwc`,
the `stellar-evolution` query.py subcommand, three panels in
`gui/panels/comparison.py` (new "Comparison" nav category), the two `core/viz`
preps + two `plot_helpers` canvases, and `tests/test_comparison.py` (15 tests,
green). Docs updated. **L4 remains DEFERRED** (see "L4 — DEFERRED").
**Build scope (this pass):** L1–L3 only + one `query.py` subcommand
(`stellar-evolution`).

This plan supersedes the brainstorm in `future_phases.md` § Phase L where they
differ. Three decisions were folded in after validating against the current code:

1. **L2 adds no core function.** Phase G2's `search_hwc` (shipped after the
   brainstorm) already does ESI-threshold filtering + `P_ESI DESC` sort. L2 is a
   GUI panel over `search_hwc`; the proposed `rank_hwc_by_esi` is dropped, and so
   is the proposed `esi-ranking` query.py subcommand (already reachable via
   `search-hwc --esi-min`).
2. **The G1 `fe_h` stub does not exist.** If/when L4 is built it must add the
   `fe_h` filter + the `hypatia_cache` JOIN to `search_star_systems` from scratch
   (a small additive change), and correct the stale claim in `docs/star-databases.md`.
3. **L4 is decoupled and deferred.** L1–L3 need no cache and ship independently.
   The Hypatia cache is justified by **one** feature — abundance *search* — which
   is impossible against the per-star live API. Before committing to L4 we must
   (a) verify the bulk `GET /data` import path and (b) confirm Hypatia's
   rate-limit / acceptable-use posture so a batch pull can't get us IP-blocked.
   Details in the L4 section.

---

## Verified dependencies (all confirmed present)

| Dependency | Location | Used by |
|---|---|---|
| `compute_simbad_lookup(star_name) -> dict` | `core/databases.py:115` | L1 |
| → returns `main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, designations, desig_str, gcns` | | L1 reads `sp_type/teff/vmag/ly/designations` |
| `compute_hypatia_data(simbad_result) -> dict` | `core/databases.py:1376` | L1, L4 |
| → returns `{star_name, properties, abundances}` or `{error}` | | |
| `compute_habitable_zone(teff, luminosity) -> list` | `core/equations.py` (query.py `habitable-zone`) | L1 HZ bounds |
| → 6 zone dicts `{zone_name, key, au, lm, seff}`; keys `rv, rg5, rg, rg01, mg, em` | | extract `rg` (cons. inner) + `mg` (cons. outer) |
| `search_hwc(filters) -> dict` | `core/databases.py:2594` | **L2 (sole core dep)** |
| → `{count, capped, cap, stars[]}`, sorted `P_ESI DESC`, cap 500 | | filters: `esi_min, habitable, habzone_con, habzone_opt, ly_max, …` |
| `search_star_systems(filters) -> dict` | `core/databases.py:2539` | L4 G1 integration |
| MS-lifetime formula `10^10 × (1/M)^2.5` | `core/regions.py:142` (`mainSeqLifeSpan`) | L3 |
| `make_abundance_canvas(parent, abundances, star_name)` | `gui/visualizations/plot_helpers.py` | L1 reference for the new comparison canvas |
| query.py equation subcommand pattern + `_out()` | `query.py:20-25`, `:774-778` | `stellar-evolution` |

---

## L1 — Side-by-Side Star Comparison

**Panel:** `StarComparisonPanel` (Comparison nav). Network (SIMBAD + Hypatia + optional NASA supplement).

### Core — `core/databases.py::compare_stars(names: list[str]) -> dict`

```python
def compare_stars(names: list[str]) -> dict:
    # Validate: 2 <= len(names) <= 4  -> else {"error": "..."}
    # Per star (NEVER aborts the whole call on a single failure):
    #   1. sl = compute_simbad_lookup(name)        # sp_type, teff, vmag, ly, designations
    #   2. if teff or radius missing -> optional NASA pscomppars supplement
    #      via best designation (HIP -> HD -> TIC -> Gaia EDR3) to fill
    #      st_teff / st_rad / st_mass / st_lum   (reuse _query_tap / _get_archive_query_params)
    #   3. luminosity: prefer st_rad^2 * (teff/5778)^4; else 10**st_lum; else None
    #   4. HZ inner/outer: compute_habitable_zone(teff, luminosity) -> pull key "rg" (cons inner)
    #      and "mg" (cons outer); None if teff or luminosity is None
    #   5. hyp = compute_hypatia_data(sl)          # {star_name, properties, abundances} | {error}
    #   each star carries its own "error" key (None on success); missing fields = None
    return {"stars": [ {
        "name", "sp_type", "teff", "luminosity", "mass", "radius",
        "hz_inner_au", "hz_outer_au", "ly", "app_magnitude",
        "hypatia",   # raw compute_hypatia_data result dict, or None
        "error",     # per-star error string, or None
    }, ... ]}
```

- **Validation:** only top-level error is the arg-count check (`2 ≤ len ≤ 4`).
  Every per-star network failure is isolated in that star's `"error"`.
- **HZ bounds:** Conservative Inner (`rg`, Runaway Greenhouse) + Conservative
  Outer (`mg`, Maximum Greenhouse) — the same two the single-star HZ tables use.

### GUI — `StarComparisonPanel`

- Inputs: star-1 `QLineEdit` always visible; "Add Star" button reveals star-3 and
  star-4 fields (max 4); star-1/2 required.
- "Compare" fires one `run_in_background` worker that loops the (≤4) names through
  `compare_stars` (sequential inside the worker — keeps the existing single-worker
  threading pattern; no need to fan out QThreads).
- **Transposed `make_table()`** — properties as rows, stars as columns:
  Spectral Type | Temp (K) | Luminosity (L☉) | Mass (M☉) | Radius (R☉) |
  HZ Inner (AU) | HZ Outer (AU) | Distance (LY) | Apparent Magnitude. Then, only
  if ≥1 star has Hypatia data, a separator row + Hypatia rows: log g | Disk |
  Fe/H | Mg/H | Si/H | O/H | U (km/s) | V (km/s) | W (km/s). Missing → "N/A";
  per-star error cells shown in red.
- **Diagram tab "Abundance Profiles"** (`DiagramToggleMixin`, when `mpl_available()`
  and ≥1 star has abundances): grouped horizontal bar chart comparing [X/H] across
  stars for the union of measured elements; one color per star; `axvline` at 0.
  New helper `make_abundance_comparison_canvas(parent, stars_data)` in
  `gui/visualizations/plot_helpers.py` (model it on the existing
  `make_abundance_canvas`, but plot N series grouped per element).

---

## L2 — Exoplanet ESI Ranking *(presentation-only)*

**Panel:** `EsiRankingPanel` (Comparison nav). **No network, no new core function.**

- "Rank" button (synchronous local-DB read) calls the existing
  `databases.search_hwc({"esi_min": …, "habitable": …, "habzone_con": …, "ly_max": …})`.
  Result is already `{count, capped, cap, stars[]}` sorted `P_ESI DESC`.
- Panel prepends a 1-based **Rank** column over the returned order and computes
  Distance (LY) = `S_DISTANCE (pc) × 3.26156`.
- **Columns:** Rank | Planet (`P_NAME`) | ESI (4dp) | Habitable? | In Con HZ? |
  In Opt HZ? | Temp K (0dp, `P_TEMP_EQUIL`) | Star (`S_NAME`) | Spectral Type
  (`S_TYPE`) | Distance (LY, 4dp). Sortable `make_table()`.
- Inputs: ESI `QDoubleSpinBox` (0.0–1.0, default 0.8, step 0.05); "Habitable only"
  `QCheckBox` → `habitable`; "Conservative HZ only" `QCheckBox` → `habzone_con`;
  optional max-LY `QLineEdit` → `ly_max`.
- Row double-click: `show_panel(HwcPanel)` with `S_NAME` pre-filled + lookup fired.
- Empty `hwc` → opt-52 error surfaced straight from `search_hwc`.

> **query.py:** none. `search-hwc --esi-min 0.8 [--habitable] [--habzone-con] [--ly-max]`
> already covers this.

---

## L3 — Stellar Evolution Timeline

**Panel:** `StellarEvolutionPanel` (Comparison nav). Pure math, no thread.

### Core — `core/equations.py::compute_stellar_evolution(mass_solar, current_age_gyr=None) -> dict`

- **Self-validating:** `0.1 ≤ mass_solar ≤ 20` → else `{"error": "mass_solar must be
  between 0.1 and 20 M☉"}` (do **not** extrapolate). `current_age_gyr` optional,
  may exceed total lifetime (`current_stage="Beyond AGB"`, not an error).
- `T_ms = 1e10 * (1/mass_solar)**2.5` years → Gyr (mirror `core/regions.py:142`).
- Stage durations (× `T_ms`): Pre-MS 0.01 · MS 1.0 · Subgiant 0.15 · RGB 0.10 ·
  HB 0.10 · AGB 0.02. Cumulative start/end Gyr; `ms_end_gyr` = end of MS.
- **Special cases (values, not errors):**
  - `mass < 0.8`: MS lifetime > age of universe → `total_gyr` flagged "> 13.8 Gyr";
    post-MS stages not reachable (omit or mark unreachable).
  - `mass > 8`: replace AGB with "Supergiant → Supernova"; add a note; total ~few Myr.
- Stage colors: Pre-MS `#aaaaaa`, MS `#ffe066`, Subgiant `#ffaa33`, RGB `#ff6600`,
  HB `#ff99cc`, AGB `#cc3300`.
- **Returns** `{mass_solar, stages:[{name, start_gyr, end_gyr, duration_gyr, color}],
  total_gyr, ms_end_gyr, current_age_gyr, current_stage}`.

### Viz — `core/viz.py::prepare_evolution_diagram(result) -> dict`
`{stages, current_age_gyr, x_max_gyr}`; `x_max_gyr = max(total_gyr, current_age_gyr or 0) × 1.1`.

### Canvas — `gui/visualizations/plot_helpers.py::make_evolution_canvas(parent, data)`
Horizontal stacked bar (one segment per stage, stage-colored); x = Gyr; dashed
vline at `current_age_gyr` labeled "Current Age: X.XX Gyr"; stage labels centered
(omitted if too narrow); light theme `#f5f5f5`.

### GUI — `StellarEvolutionPanel`
Mass `QDoubleSpinBox` + optional age `QDoubleSpinBox` (gated by an "Enter current
age" `QCheckBox`). Stage table (Stage | Start (Gyr) | End (Gyr) | Duration (Gyr),
current row bold) + "Evolution Diagram" viz tab (`DiagramToggleMixin`).

### query.py — `stellar-evolution`  ✅ the only new subcommand in Phase L
```python
def cmd_stellar_evolution(args):
    _out(equations.compute_stellar_evolution(args.mass_solar, args.current_age_gyr))
# argparse:
p = sub.add_parser("stellar-evolution",
                   help="Stellar evolutionary-stage timeline from mass (0.1–20 M☉)")
p.add_argument("--mass-solar",      required=True, type=float)
p.add_argument("--current-age-gyr", type=float)   # optional
p.set_defaults(func=cmd_stellar_evolution)
```
Self-validating → curated `{"error"}` exit 1 for out-of-range mass; argparse exit 2
for missing/non-numeric args. Add the row to `docs/integration.md`.

---

## L4 — Hypatia Catalog Cache & Abundance Search — ⛔ DEFERRED (do NOT build yet)

**L4 is out of scope for this pass.** L1–L3 ship without it. L4 builds only after
the verification spike below passes. This section is the captured design + the
gating checklist — not a build instruction.

### Why deferred — the cache is justified by exactly one feature
The Hypatia `/star` and `/composition` endpoints are **per-star**: there is no
endpoint that answers *"every star with Fe/H < −0.3 and Mg/H > 0."* So
abundance **search / filter / ranking** across many stars is impossible against
the live API — that is the *only* thing that requires a local cache. Everything
else (L1 comparison; the opt-1/3/4/5/6/8 displays) already works live, per-star,
and would gain only reduced latency from a cache. **No abundance search ⇒ no L4.**

### Pre-L4 verification spike (gate — must pass before any L4 code)

**Status (2026-06-14): Step 0a ✅ PASSED. Step 0b (`/data` star-id) + Step 0c
(confirm demand) still OPEN.**

1. **⚠️ Rate limit / acceptable-use / IP-block check — ✅ PASSED (2026-06-14).**
   Read-only probes of `hypatiacatalog.com` found **risk LOW, GO**:
   - **`robots.txt` → 404** (none published): no `Disallow`, no `Crawl-delay`.
   - **No WAF / bot-protection.** Server is plain `nginx/1.31.1` + `web2py`; no
     `X-RateLimit-*`, no `Retry-After`, no Cloudflare. (API needs a **trailing
     slash** — `/hypatia/api/v2/star/`; without it → 301.)
   - **Programmatic access is explicitly blessed** — the homepage states data
     "can be downloaded … through the terminal via our API for use in external
     plotting routines and data analysis." No published rate limits.
   - **Citation requested** (Hinkel et al. 2014 AJ 148,54 + the 2017 database
     paper, arXiv 1712.04944); contact **hypatiacatalog@gmail.com**. Record the
     citation + snapshot date in `hypatia_meta`.
   - **Catalog scale (current):** ~5,986 stars / 72 elements / 347 planet hosts —
     so the cache target is the *whole* catalog (~6k stars), not just a
     `star_systems` intersection.
   - **Locked throttle envelope** for `import_hypatia_cache`: serial (concurrency
     1); inter-request delay ~0.5–1 s; backoff on 429/503 via `_with_retries`
     **+ honor `Retry-After`** (add — current helper ignores it); hard per-run
     request cap; descriptive `User-Agent` with app name + contact email; resumable
     so a pause never forces a full re-pull. A courtesy heads-up email before the
     full pull is optional (not required, given the explicit API blessing).
2. **Bulk import path via `GET /data` — ⏳ OPEN (next step).**
   `GET /hypatia/api/v2/data/?xaxis1=Fe&yaxis1=Si` returns 200 (confirmed live).
   **CRITICAL unknown still to probe:** does each point carry a **star identifier**
   (name / HIP)? If yes → import is ~72 element-keyed calls over the whole catalog
   (preferred). If anonymous x/y only → fall back to per-star (~6k–24k throttled
   calls) and reassess. **Alternate bulk source found:** the reduced catalog is on
   **VizieR `J/AJ/148/54`** (free bulk access, zero per-request risk) — but it's the
   **2014 snapshot** (3,058 stars / 50 elements) vs the live catalog above. Source
   preference: `/data` bulk (live, current) → VizieR (bulk-safe, older) → per-star
   (live, current, slow fallback).
3. **Confirm demand. ⏳ OPEN.** Verify abundance search is actually wanted before
   paying for the cache + import UI + maintenance.

### Captured design (apply only if the spike passes)

> **Re-validated against L1–L3 / GCNS (2026-06-13).** All foundations the design
> rests on are confirmed present and unchanged (`compute_hypatia_data` returns the
> exact `{element, name, z, category, mean, std, min, max, n}` records the EAV table
> stores; the shared search helpers, the GCNS-ingest template, and the network
> helpers are all in place). The refinements below were folded in: a `hypatia_meta`
> provenance table, the GCNS check-gate/atomic-replace import structure, the exact
> reusable helpers, the `distance_pc`-based ly filter (no `star_systems` join), and
> the GCNS-mirroring import panel.

**Storage — two-table EAV + a meta table** (not a 104-column wide table: the species
set is the full **104** in `core/hypatia_elements.py`, sparsely measured per star; a
wide table is mostly NULL, churns on catalogue changes, and can't filter "any
element" without dynamic SQL). Declared in `core/db.py::_create_schema` via
`CREATE TABLE IF NOT EXISTS` (the same place the GCNS tables live); **not**
auto-seeded (empty until the import runs), exactly like `gcns_stars`:
```sql
CREATE TABLE IF NOT EXISTS hypatia_cache (        -- star-level props, one row/star
    star_name TEXT PRIMARY KEY, hip TEXT, hd TEXT,
    teff REAL, logg REAL, vmag REAL, bv REAL, distance_pc REAL, disk TEXT,
    u_vel REAL, v_vel REAL, w_vel REAL, pm_ra REAL, pm_dec REAL,
    fe_h REAL,                                     -- denormalized from the 'Fe' row
    light_years REAL,                              -- distance_pc × _LY_PER_PC, precomputed
    fetched_date TEXT );
CREATE TABLE IF NOT EXISTS hypatia_abundance (    -- one row per (star, element)
    star_name TEXT, element TEXT,                 -- API casing: 'Fe', 'Mg', 'Ba_II'
    mean REAL, std REAL, min REAL, max REAL, n INTEGER,
    PRIMARY KEY (star_name, element) );
CREATE TABLE IF NOT EXISTS hypatia_meta (key TEXT PRIMARY KEY, value TEXT);  -- like gcns_meta
CREATE INDEX IF NOT EXISTS idx_hyp_cache_feh  ON hypatia_cache(fe_h);
CREATE INDEX IF NOT EXISTS idx_hyp_cache_teff ON hypatia_cache(teff);
CREATE INDEX IF NOT EXISTS idx_hyp_cache_ly   ON hypatia_cache(light_years);
CREATE INDEX IF NOT EXISTS idx_hyp_abund_elem ON hypatia_abundance(element, mean);
```
- **`fe_h` denormalized** onto the star table: it's the default sort, the dominant
  filter, and the G1 JOIN key, so keep it indexed there (Fe is *also* present as an
  `element='Fe'` row for uniformity). **Not** stored on abundance rows: `name`,
  `z`, `category` — those are static per element, derived from
  `core/hypatia_elements.py` at read time (avoid duplicating/drifting the canonical
  table).
- **`light_years` precomputed** as `distance_pc × _LY_PER_PC` (`core.shared._LY_PER_PC
  = 3.26156`): the ly filter then indexes `hypatia_cache.light_years` directly — **no
  `star_systems` join** (Hypatia carries its own `distance_pc`; the earlier
  join-`star_systems`-for-light_years note was unnecessary).
- **`hypatia_meta`** (key/value, mirroring `gcns_meta`): `snapshot_date`, `source`
  (catalogue/version string), `star_count`, `abundance_count`, `simbad_norm`
  (Lodders 2009) — provenance surfaced by the import panel and any future
  `search-hypatia` result.
- **Size:** the `star_systems`∩Hypatia(HIP/HD) overlap is ≈ 2–6k stars × ~25
  measured species ≈ 50–150k abundance rows ≈ a few MB (worst case 6k×104 ≈ 40 MB);
  negligible, and `data/space_app.db` is gitignored.

**Core fns** (`core/databases.py`) — model the import on `compute_gcns_ingest`
(`core/databases.py`), the proven network-ingest template:
- `import_hypatia_cache(progress_callback=None) -> dict` — `progress_callback(msg)`
  signature matches the GCNS import. Reuses `_with_retries` / `_timeout_ctx` /
  `_network_error_msg` from `core/shared.py` and the existing `_HYPATIA_BASE` +
  per-star parsers (`_parse_hypatia_star`, `_parse_hypatia_composition`). **Import
  structure depends on the spike's chosen path:**
  - **Bulk `/data` path (preferred):** download all → **Gate 1** (abort before any
    DB write if a pull truncated/under a floor) → transform → **DELETE + bulk INSERT
    of all three tables in ONE transaction** → **Gate 2** (post-commit row-count
    assert) → write `hypatia_meta`. This is the GCNS pattern verbatim (atomic
    replace; a mid-import crash rolls back and leaves the prior cache intact).
  - **Per-star fallback path:** thousands of slow throttled calls make atomic
    replace risky, so use a **resumable incremental upsert** — per star,
    `DELETE FROM hypatia_abundance WHERE star_name=?` then insert the star row + its
    element rows in one per-star transaction; `fetched_date` lets a resume skip
    recently-pulled stars. Per-star/API errors skipped + counted, never fatal.
  - Either path honours the Stage-0a throttle/backoff/cap and returns
    `{inserted, skipped, errors, total_candidates, snapshot_date, source}`.
- `search_hypatia_cache(filters) -> dict` — **reuse the exact G1/G2 helpers**:
  `_range_clause(col, vmin, vmax, params)` for `fe_h`/`teff`/`light_years` ranges,
  `_SEARCH_CAP` (500) for the cap (fetch `cap+1` to detect overflow), `get_conn`
  from `core.db`. `disk` is an exact match; `element`+`element_min/max` via an
  `EXISTS` subquery on `hypatia_abundance`. Display columns Mg/H, Si/H, O/H are
  **pivoted** with small correlated subqueries on `hypatia_abundance` (Fe/H is the
  denormalized column). Sort `fe_h DESC`, cap 500, same `{count, capped, cap,
  stars[]}` shape as `search_star_systems`. Empty cache → error directing the user
  to run the import (mirror the opt-50/opt-58 "table is empty" message style).
- **G1 integration:** add `fe_h_min`/`fe_h_max` to `search_star_systems` —
  `JOIN hypatia_cache hc ON ss.star_name = hc.star_name WHERE hc.fe_h BETWEEN ? AND ?`
  (confirmed: `search_star_systems` has **no JOIN today** and uses `get_conn` +
  parameterized clauses, so the addition slots in cleanly). Build from scratch (the
  assumed stub does not exist) and correct the false claim in
  `docs/star-databases.md` at the same time.

**Panels** (`gui/panels/`):
- `ImportHypatiaPanel` (Utilities) — **mirror `ImportGcnsPanel`** (`csv_utility.py`):
  a dedicated `_HypatiaWorker(QObject)` with `progress`/`finished`/`error` signals on
  a `QThread`, a busy/indeterminate `QProgressBar`, a status label fed by
  `progress_callback`, an up-front duration warning, and a completion summary built
  from the result dict (`inserted`/`skipped`/`errors` + `snapshot_date`).
- `HypatiaSearchPanel` (Search & Filter) — **reuse `SearchPanelBase`**
  (`gui/panels/search_common.py`): the inline "Search Results" + closable drill-down
  detail-tab pattern, with the "Open in SIMBAD" detail tab embedding a `SimbadPanel`
  (as G1 does). Filter form: Fe/H min/max, disk combo, teff min/max, element combo +
  value range, max-LY. No `SpectralClassControl` (Hypatia search has no spectral
  filter). Apply `_fit_table_height` + a scroll area as in the L1–L3 panels.

**query.py — deferred-within-deferred:** once `hypatia_cache` exists, reconsider a
`search-hypatia` subcommand over `search_hypatia_cache` (no-network local-DB read,
same `search-*` contract). Out of scope until the cache exists; the import stays
GUI-only.

---

## Validation & `{"error"}` contract summary *(L1–L3)*

- `compare_stars`: top-level error only on arg count (`2 ≤ len ≤ 4`); per-star
  failures isolated.
- L2: no new core fn — `search_hwc` already self-validates.
- `compute_stellar_evolution`: self-validating (`0.1–20 M☉`); special-case values
  (`<0.8` "> 13.8 Gyr", `>8` supergiant→SN, `Beyond AGB`) are values not errors.
- *(L4 deferred — its validation contract lives in the deferred section above.)*

## Tests — `tests/test_comparison.py` (offline; network mocked) *(L1–L3)*
- `compute_stellar_evolution`: 1 M☉ MS ≈ 10 Gyr; monotonic non-overlapping stage
  boundaries summing to `total_gyr`; `current_stage` for an age inside MS and past
  AGB; both special-case branches (0.5 M☉, 10 M☉); bad mass (0 / 50) → `{"error"}`.
- `compare_stars`: monkeypatch `compute_simbad_lookup` + `compute_hypatia_data` →
  2- and 4-star shapes; one bad name isolated; HZ bounds from the Kopparapu path;
  `hypatia` sub-dict carried through.
- L2: covered by existing `search_hwc` tests; light panel check of Rank column +
  ly conversion.
- `tests/test_query_*`: `stellar-evolution` happy path + out-of-range (exit 1) +
  argparse (exit 2).
- *(L4 tests deferred with the feature.)*

## Success criteria *(this pass = L1–L3)*
- [ ] `compare_stars` → transposed 2–4-col table, per-star error isolation,
      abundance-comparison diagram when ≥1 star has abundances.
- [ ] `EsiRankingPanel` ranks off `search_hwc` (no new core fn); row-drill opens `HwcPanel`.
- [ ] `compute_stellar_evolution` matches stage formulas + special cases; diagram marks current age.
- [ ] `stellar-evolution` query.py subcommand: self-validating, curated error, integration doc row.
- [ ] Whole suite green; offline tests mock all network.

**L4 gate (separate pass):** verification spike passes — `/data` bulk path
confirmed to carry star identifiers **and** Hypatia rate-limit / acceptable-use
posture checked so a batch pull can't get us IP-blocked — before any L4 build.

## Remaining-steps checklist — this pass (L1–L3)
- `gui/panels/comparison.py` — `StarComparisonPanel`, `EsiRankingPanel`,
  `StellarEvolutionPanel`.
- `gui/panels/__init__.py` — export the three new panels.
- `gui/nav.py` — "Comparison" category (L1–L3).
- `gui/visualizations/plot_helpers.py` — `make_abundance_comparison_canvas`,
  `make_evolution_canvas`.
- `core/viz.py` — `prepare_evolution_diagram`.
- `core/equations.py` — `compute_stellar_evolution`.
- `core/databases.py` — `compare_stars`.
- `query.py` — `stellar-evolution` subcommand only.
- `tests/test_comparison.py` — `compute_stellar_evolution` + `compare_stars`
  (mocked); `stellar-evolution` query.py contract.
- Docs — `equations.md` (`compute_stellar_evolution`), `star-databases.md`
  (`compare_stars` + L2 `search_hwc` reuse), `integration.md` (`stellar-evolution`
  row), `gui-architecture.md` ("Comparison" panels).

## Deferred checklist — L4 (only after the verification spike passes)
- Run the spike: `/data` star-identifier check **+** Hypatia rate-limit /
  acceptable-use / IP-block check.
- `core/db.py` — `hypatia_cache` + `hypatia_abundance` + `hypatia_meta` tables in
  `_create_schema` (not auto-seeded, like the GCNS tables).
- `core/databases.py` — `import_hypatia_cache` (modelled on `compute_gcns_ingest`:
  check-gates + atomic replace for the bulk path / resumable upsert for the per-star
  fallback; reuses `_with_retries`/`_timeout_ctx`/`_network_error_msg` +
  `_parse_hypatia_star`/`_parse_hypatia_composition`), `search_hypatia_cache`
  (reuses `_range_clause`/`_SEARCH_CAP`/`get_conn`; ly via the precomputed
  `light_years` column, no `star_systems` join), and the `search_star_systems`
  `fe_h` filter (built from scratch — no JOIN exists today).
- `gui/panels/csv_utility.py` — `ImportHypatiaPanel` (mirror `ImportGcnsPanel` +
  a `_HypatiaWorker`); `gui/panels/search.py` — `HypatiaSearchPanel` (reuse
  `SearchPanelBase` from `search_common.py`); `gui/panels/__init__.py` exports;
  `gui/nav.py` — L4 entries (Utilities / Search & Filter).
- `tests/test_hypatia_cache.py` — import (mocked Hypatia: inserted/skipped/errors +
  idempotency/no-orphans), `search_hypatia_cache` filter matrix, the G1 `fe_h` JOIN
  activating only with a populated cache; live round-trip reachability-gated.
- Docs — `star-databases.md` (import/search/EAV schema + `hypatia_meta` **+ correct
  the false `fe_h`-stub claim**); reconsider a `search-hypatia` query.py subcommand.
