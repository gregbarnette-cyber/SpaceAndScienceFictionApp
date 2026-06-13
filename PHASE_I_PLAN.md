# PHASE I — Multi-System / Route Planning · Implementation Plan

> **Scope: GUI-only**, per `future_phases.md`. Three new core functions in `core/calculators.py`, one new
> viz-prep function in `core/viz.py`, an additive optional `routes=` parameter on the two star-map canvases, a
> new `gui/panels/route_planning.py` with three panels under a new **"Route Planning"** nav category, and
> `tests/test_route_planning.py`. **No CLI menu entries, no `query.py` subcommands** (Phase I's Remaining Steps
> list only GUI + `docs/calculators.md`). The existing opts 17–21 are **reused, not modified** — they already
> share `compute_lookup_star_for_distance`, `_to_cartesian`, and `format_travel_time`.
>
> **Companion mockup:** [`mockups/phase-i.html`](mockups/phase-i.html) — an interactive GUI mockup of all three
> panels (live JS over a small built-in nearby-star catalog), including the top-down route map. **No code is
> written until the mockup is approved.**

---

## 1. What gets built

| # | Feature | New panel | New core function | Reused infra |
|---|---|---|---|---|
| I1 | Multi-Stop Journey | `MultiStopJourneyPanel` | `compute_multi_stop_journey(star_names, velocity_input, use_times_c)` | resolver, `_to_cartesian`, `format_travel_time` |
| I2 | Nearest-Neighbor Chain | `NearestNeighborPanel` | `compute_nearest_neighbor_chain(start_star, num_hops, max_ly)` | resolver, `star_systems` table, `_to_cartesian` |
| I3 | Trade-Route MST **(stretch)** | `TradeRoutePlannerPanel` | `compute_trade_route_mst(star_names)` | resolver, Kruskal/union-find |
| — | Route overlay (shared) | — | `core.viz.prepare_route_map(result)` + `routes=` param on the two **GCNS Star-Chart** canvases | `make_star_chart_canvas`, `make_star_chart_3d_canvas` |

All three core functions are **new**, so — unlike the Phase-N legacy wrappers — they **self-validate** and return
`{"error": str}` for bad input (the modern Phase-H / search-function contract), so the GUI's red error label works
cleanly. Each returns a result dict that includes a **star-map-compatible `stars` list** so the viz layer needs no
re-derivation.

---

## 2. Shared resolution layer (WP1) — `core/calculators.py`

The brainstorm calls for "DB-first, SIMBAD-fallback" star resolution. Factor it once and reuse across I1/I2/I3.

### 2a. Module-level sexagesimal parsers (dedup)
`compute_stars_within_distance_of_sol`/`_of_star` each define **local** `_parse_ra`/`_parse_dec` copies. Add
module-level `_parse_db_ra(s) -> float` and `_parse_db_dec(s) -> float` (lifted verbatim from those inner copies:
`HH MM SS` → degrees ×15; `±DD MM SS` → signed degrees). The new code uses them. (Refactoring opts 18/19 to also
use them is a behavior-neutral cleanup — **left out of scope** to honor "opts 18–21 unchanged"; noted as optional.)

### 2b. `_resolve_star_position(name) -> dict`
Single-star resolver used by I1 (each stop), I3 (each node), and I2 (the start only).
- `"sun"`/`"sol"` (case-insensitive) → `{"name": <as typed>, "x":0.0,"y":0.0,"z":0.0,"ly":0.0,"sp_type":"G2V","desig":"","source":"sol"}` — **no DB, no network** (mirrors `compute_lookup_star_for_distance`).
- **DB-first:** `SELECT star_name, designations, spectral_type, parallax, light_years, ra, dec FROM star_systems WHERE lower(star_name)=lower(?) LIMIT 1`. On hit with usable `ra`/`dec` and (`light_years` or positive `parallax`): parse → `_to_cartesian` → return with `sp_type`/`desig` from the row, `source="db"`. (DB hit is an offline fast-path **and** the only way a node carries a spectral type for map colouring.)
- **SIMBAD fallback:** `compute_lookup_star_for_distance(name)` → on success `_to_cartesian(ra_deg,dec_deg,ly)`; `sp_type=""` (that helper does not return a type → grey map dot), `desig=desig_str`, `source="simbad"`. On its `{"error"}` → propagate.
- Returns `{"error": str}` only when both paths fail; the message names the unresolved input.

### 2c. `_load_star_systems_positions() -> list[dict] | {"error": str}`
For I2's candidate pool: read **all** `star_systems` rows once, parse each to `{name, desig, sp_type, ly, x, y, z}`,
skipping rows with non-positive parallax or unparseable `ra`/`dec` (same skip rules as opt 19). Empty table →
`{"error": "star_systems table is empty — run option 50 first to populate it."}` (verbatim opts-18/19 message).

### 2d. How stars are entered (the resolution UX)
Stars are **free-hand typed by name** — exactly like the existing star-lookup panels (opts 17–21). There is **no
dropdown/picker/autocomplete**; the user types a name and the panel resolves it. Per panel:
- **I1 / I3** — a `QPlainTextEdit`, **one star name per line** (the ordered stop list / the system set).
- **I2** — a single `QLineEdit` for the **start** star (the rest of the chain comes from the local `star_systems` table, not typed).

Each typed name is resolved by `_resolve_star_position` in this order (so **most names never hit the network**):
1. **`sol` / `sun`** → the origin `(0,0,0)` instantly — no DB, no SIMBAD.
2. **Local `star_systems` table (DB-first)** — a case-insensitive exact match on `star_name` (the SIMBAD `main_id`
   captured by opt 50, e.g. `"GJ 411"`, `"* alf Cen A"`). Instant, offline, and the only path that also yields a
   spectral type for the map dot's colour.
3. **SIMBAD (live network, fallback only)** — if the DB misses, `compute_lookup_star_for_distance(name)` queries
   SIMBAD (the same call opts 17–21 use; resolves common names/designations like `"Lalande 21185"`). Runs on the
   panel's background `run_in_background` thread so the UI stays responsive.

A name that matches **neither** the DB nor SIMBAD is unresolvable → the function returns
`{"error": "Stop N ('name'): …"}` (I1/I3 name the offending entry) or a start-star error (I2), shown in the panel's
red label; the user fixes that line and re-runs. So the flow is: **type names → DB-first lookup → SIMBAD fallback
for anything the DB doesn't have → clean per-name error if a name resolves nowhere.** *(Typeahead/autocomplete over
`star_systems` is a possible future nicety but is **out of scope** here — see §12.)*

---

## 3. I1 — `compute_multi_stop_journey(star_names, velocity_input, use_times_c)` (WP2)

Cumulative travel time along an ordered list of stops. Same 3D-Euclidean + `format_travel_time` math as opts 20/21.

- **Validate:** `len(star_names) >= 2` (else `{"error":"Enter at least two stops."}`); `velocity_input > 0` (else `{"error":"Velocity must be positive."}`).
- **Velocity:** `use_times_c` → `ly_hr = velocity_input / HOURS_PER_JULIAN_YEAR`, `times_c = velocity_input`; else `ly_hr = velocity_input`, `times_c = velocity_input * HOURS_PER_JULIAN_YEAR` (constant `8765.8128`, already in module).
- **Resolve every stop** via `_resolve_star_position`. **First failure → `{"error": "Stop N ('name'): <reason>"}`** (fail-fast). *Deviation from the brainstorm's "ask skip/abort":* a pure core function cannot prompt, and this is GUI-only — the panel surfaces the error and the user edits the list and re-runs. Documented in `docs/calculators.md`.
- **Legs:** for each consecutive pair `i → i+1`: `distance_ly = euclidean(node_i, node_{i+1})`; `hours = distance_ly / ly_hr`; accumulate `cumulative_hours`.
- **Returns:**
  ```
  {"legs": [{"leg": int, "origin": str, "dest": str, "distance_ly": float,
             "ly_hr": float, "times_c": float, "hours": float,
             "cumulative_hours": float, "travel_time": str, "cumulative_time": str}],
   "total_ly": float, "total_hours": float, "total_time": str,
   "stars": [<star-map dicts: name, desig, sp_type, color, ly, x, y, z>]}
  ```
  `stars` lists the resolved stops in order (index 0 = origin → highlighted on the map); `color` from `_SPECTRAL_COLORS` (Sol/`G`→its colour, untyped→grey); `ly` = distance from Sol = `sqrt(x²+y²+z²)`.

**Output table** (GUI): Leg # | Origin | Destination | Distance (LY) | LY/HR | ×c | Travel Time | Cumulative Time.
Footers: `Total Distance: X LY` and `Total Travel Time: …`.

---

## 4. I2 — `compute_nearest_neighbor_chain(start_star, num_hops, max_ly)` (WP3)

Greedy nearest-unvisited traversal from a start star.

- **Validate:** `num_hops >= 1` int (else error); `max_ly > 0` (else error).
- **Start:** `_resolve_star_position(start_star)` → its `(x,y,z)`; propagate `{"error"}`.
- **Candidates:** `_load_star_systems_positions()` (propagate empty-table error). **Self-exclusion:** drop any candidate within `1e-3` ly of the start position (the opt-19 epsilon — removes the start's own DB row so it can't be hop 1).
- **Greedy loop:** `visited=set()`; current = start pos. Up to `num_hops` times: over unvisited candidates compute Euclidean distance from current; pick the minimum **with `dist <= max_ly`**; if none in range → set `stopped_early=True` and break. Append the pick; mark visited; advance current.
- **Returns:**
  ```
  {"chain": [{"hop": int, "star_name": str, "desig": str, "sp_type": str,
              "dist_from_prev_ly": float, "cumulative_ly": float, "ly_from_sol": float}],
   "stars": [<map dicts incl. the start as index 0, gold>],
   "total_ly": float, "stopped_early": bool, "start_name": str}
  ```

**Output table:** Hop # | Star Name | Designations | Spectral Type | Dist from Prev (LY) | Cumulative Dist (LY) | Dist from Sol (LY).
Footer: `N hops` + `total distance`; an italic note when `stopped_early` (`"No unvisited star within max hop distance — chain ended early."`).

---

## 5. I3 — `compute_trade_route_mst(star_names)` (WP4, **stretch**)

Minimum spanning tree connecting a set of systems (Kruskal + union-find).

- **Validate:** `len(star_names) >= 2`; resolve each via `_resolve_star_position` (first failure → `{"error": …}` naming it). Dedup identical names (case-insensitive) before resolving.
- **MST:** build all `N·(N−1)/2` candidate edges with Euclidean ly weights; sort ascending; add via union-find skipping cycle-forming edges until `N−1` accepted. Add `_UnionFind` (find/union by rank) and `_kruskal_mst(nodes) -> edges` private helpers.
- **Returns:**
  ```
  {"nodes": [{"name","x","y","z","sp_type","desig"}],
   "edges": [{"from": str, "to": str, "distance_ly": float}],   # N-1 edges, ascending
   "total_ly": float,
   "stars": [<map dicts>]}
  ```

**Output table:** From | To | Distance (LY). Footer: `N nodes, N−1 edges, Total Network Distance: X LY`.

> **Stretch gating:** I3 (core fn + `TradeRoutePlannerPanel` + its tests) is a self-contained final work package.
> If deferred, I1/I2 ship complete; the nav category simply lists two entries. The mockup includes all three so the
> maintainer can approve or drop I3 from the preview.

---

## 6. Shared visualization (WP5)

### 6a. `core/viz.py` — `prepare_route_map(result) -> dict`
Normalizes any of the three result dicts into map + edge geometry:
- `stars` = `result["stars"]` passed through (already map-shaped).
- **Ordered routes (I1/I2):** detect via `result.get("legs")` or `result.get("chain")`; build `edges` between **consecutive** `stars` entries — `{x1,y1,z1,x2,y2,z2,label}` where `label` = leg distance (I1: `"3.2 ly"`) or hop index (I2: `"①"`,`"②"`,…); `edge_style="dashed"`.
- **MST (I3):** map each `result["edges"]` `{from,to}` to coordinates by matching `stars` name; `label` = edge ly; `edge_style="solid"`.
- Returns `{"stars": list, "edges": [...], "edge_style": "dashed"|"solid"}` or `{"error": str}` (passthrough).

### 6b. `gui/visualizations/plot_helpers.py` — additive `routes=` param on the **GCNS Star-Chart** canvases
The route maps reuse the **dark-navy GCNS "Star Chart"** diagrams — `make_star_chart_canvas(parent, stars, limit_ly)`
(2D) and `make_star_chart_3d_canvas(parent, stars, limit_ly)` (3D) — the same charts the GCNS Census Browser /
"Stars within a Star" panels and opts 18/19 use. Add an **optional** `routes: list | None = None` trailing kwarg to
both (→ **all existing callers unaffected**). When provided, after the dots are drawn, render each route segment as a
line (`linestyle="--"` dashed for ordered I1/I2 routes / `"-"` solid for the I3 MST, read from each edge dict's
`style`) in a muted route colour, with a small label at the segment midpoint (`ax.annotate`, 2D / `ax.text`, 3D).
- **Centering & scale:** the chart centers on `stars[0]` (origin/start/hub — the gold ★) and is passed
  `limit_ly = max node distance from that center × 1.1`, so the concentric **distance rings** and grid/ring intervals
  scale to fit the whole route (these chart helpers already derive ring/label spacing from `limit_ly`).
- **Label decluttering (reuse, don't reinvent):** `make_star_chart_canvas` already governs per-star
  `"Name (Z=±X.XXX)"` label visibility by the **visible half-range** (labels appear once the user zooms in past the
  ~15 ly half-range threshold via the `xlim_changed`/`ylim_changed` callbacks, with screen-space collision-nudging and
  a `path_effects` stroke; the 3D companion uses `xlim/ylim/zlim_changed`). **The route overlay must inherit this
  same behavior** — the per-node labels are the chart's existing labels (untouched), and the only *new* labels are the
  short per-segment route labels (leg # / hop ②③ / edge ly), which are anchored at segment midpoints with the same
  fixed-pixel-offset + `annotation_clip=True` convention so they track on zoom and don't render off-axis. So a busy
  route (many stops/hops) starts uncluttered and reveals labels as you zoom — no all-labels-at-once dump.
> **Phase O8 shared dependency** (noted in both phases): O8 (two-star maps for opts 17/20/21) uses this **same**
> `routes=` parameter. **Phase I builds it first**; O8 reuses it unchanged. Recorded in `docs/gui-architecture.md`.

---

## 7. GUI wiring (WP6) — `gui/panels/route_planning.py` + nav + exports

All three panels inherit `(DiagramToggleMixin, ResultPanel)` and follow the **opts-18/19 pattern**
(`gui/panels/distance_stars.py`): `build_inputs()` builds the form inside `_form_widget`; `build_results_area()`
creates `_tables_widget` + calls `_setup_diagram_view()`; `_search()` fires `run_in_background(core_fn, …)`;
`_render(result)` calls `_prepare_render()`, fills the table(s), then for each projection builds a map canvas with
`routes=` from `prepare_route_map(result)` and adds it to `_viz_tabs_widget`, then `_finish_render()`.

| Panel | Inputs | Viz tabs |
|---|---|---|
| `MultiStopJourneyPanel` | `QPlainTextEdit` (stops, one per line) · velocity-unit `QComboBox` (LY/HR ‖ ×c) · velocity `QLineEdit` | "Star Chart", "Star Chart 3D" (dashed numbered legs, gold ★ origin) |
| `NearestNeighborPanel` | star-name `QLineEdit` · hop-count `QSpinBox` (1–50) · max-hop-distance `QLineEdit` | "Star Chart", "Star Chart 3D" (dashed hop route, gold ★ start) |
| `TradeRoutePlannerPanel` *(stretch)* | `QPlainTextEdit` (systems) | "Star Chart", "Star Chart 3D" (solid MST edges, gold ★ center) |

- **`gui/panels/__init__.py`** — export the three panel classes.
- **`gui/nav.py`** — add a **"Route Planning"** category with the three entries (two if I3 deferred).
- **Maps are the dark-navy GCNS "Star Chart" + "Star Chart 3D" diagrams** (per the approved `mockups/phase-i-alt.html`):
  concentric distance rings, gold ★ center, spectral-class dots, `Name (Z=±X.XXX)` labels — with the route overlay
  (§6b) on top. They render full-window behind the **Show Diagrams** toggle (`DiagramToggleMixin`), so the live charts
  are large, zoomable (scroll-wheel), pannable, hover/click-interactive, and (3D) drag-to-rotate with Top/Side/
  Perspective presets — not the small fixed inline SVG of the mockup.

---

## 8. Validation matrix (all self-validating → `{"error": str}` + red GUI label)

| Condition | I1 | I2 | I3 |
|---|---|---|---|
| Too few inputs | `< 2` stops → error | — | `< 2` systems → error |
| Bad numeric | `velocity ≤ 0` → error | `num_hops < 1` or `max_ly ≤ 0` → error | — |
| Unresolvable star | first bad stop → error naming it | bad start → error | first bad node → error naming it |
| Empty `star_systems` | only if a stop needs the DB pool¹ | empty table → "run option 50" error | only if a node needs the DB pool¹ |
| No reachable candidate | n/a | `stopped_early=True` (not an error) | n/a |

¹ I1/I3 resolve names individually — a stop typed as `"Sol"` or resolvable via SIMBAD doesn't touch the DB pool. The
"empty table" message surfaces only when a name misses SIMBAD **and** the DB is empty; otherwise the per-name error wins.

---

## 9. Tests (WP7) — `tests/test_route_planning.py`

**Offline**, using the temp-DB seeding pattern from `tests/test_db_backups.py` (swap `db._DB_PATH`/`db._conn`/
`db._auto_seed`, seed a tiny `star_systems`, restore in `tearDown`). All star resolution uses **`"Sol"` (origin,
no SIMBAD)** plus **seeded DB rows** (DB-first hit, no SIMBAD) — so the suite never hits the network. One test
monkeypatches `calculators.compute_lookup_star_for_distance` to cover the SIMBAD-fallback branch deterministically.

**Seed fixture** — a handful of rows at exactly-known positions via crafted `ra`/`dec`/`parallax`. RA `"00 00 00"`,
DEC `"+00 00 00"` ⇒ direction +x; parallax chosen so `light_years = 1000/plx·3.26156` is a round number (e.g.
`plx` giving `ly=5`). A second star on `+y` (RA `"06 00 00"` = 90°), a third farther on `+x`. This makes every
distance hand-checkable.

### I1 — `MultiStopJourneyTest`
- `test_two_stop_known_distance` — `["Sol","AX5"]` (AX5 at 5 ly on +x), `ly_hr=0.01` → one leg, `distance_ly≈5`, `hours≈500`, `times_c≈87.658`, `total_ly≈5`; `stars` has 2 entries, index 0 named like Sol.
- `test_three_stop_cumulative` — `["Sol","AX5","BY5"]` → 2 legs; `cumulative_hours` of leg 2 = leg1+leg2; `total_ly` = leg1+leg2.
- `test_times_c_unit` — same stops with `use_times_c=True, velocity_input=100`; assert `ly_hr=100/8765.8128` and hours scale accordingly.
- `test_fewer_than_two_stops_error` / `test_zero_velocity_error` / `test_unresolvable_stop_error` (a name absent from DB; monkeypatch the SIMBAD fallback to return `{"error":…}`) → each returns `{"error":…}`, message names the stop for the last.

### I2 — `NearestNeighborChainTest`
- `test_greedy_order` — seed 3 stars at increasing distance on a line from Sol; `start="Sol", num_hops=3, max_ly=1e9` → chain visits them nearest-first; `cumulative_ly` monotonic; `dist_from_prev_ly` of hop 1 = nearest distance.
- `test_stops_early_when_out_of_range` — `max_ly` smaller than the nearest candidate → `chain==[]`, `stopped_early=True` (not an error).
- `test_self_exclusion` — seed a row at Sol's position (ra/dec/plx → ~origin); `start="Sol"` → that row is **not** hop 1 (excluded by the `1e-3` ly rule).
- `test_num_hops_caps` — `num_hops=1` returns exactly 1 hop even with more candidates.
- `test_bad_hops_error` / `test_bad_max_ly_error` / `test_empty_table_error`.
- `test_simbad_start` — monkeypatch `compute_lookup_star_for_distance` to a fixed non-Sol position; assert the chain is computed relative to it.

### I3 — `TradeRouteMstTest` *(stretch — include iff I3 is built)*
- `test_mst_edge_count_and_total` — 4 nodes (`Sol` + 3 seeded) in a known geometry → `len(edges)==3`, no cycle (union-find leaves one component), `total_ly == sum(edge ly)`, edges ascending, and `total_ly` equals the hand-computed minimal tree.
- `test_two_nodes_one_edge` — `["Sol","AX5"]` → 1 edge = 5 ly.
- `test_fewer_than_two_error` / `test_unresolvable_node_error`.

### Shared — `PrepareRouteMapTest`
- `test_ordered_dashed` — feed an I1 result → `edge_style=="dashed"`, `len(edges)==len(stars)-1`, each edge has `x1/y1/z1/x2/y2/z2/label`.
- `test_mst_solid` — feed an I3 result → `edge_style=="solid"`, edges match node coordinates by name.
- `test_error_passthrough` — `{"error":"x"}` in → same out.

*(No `make_*_canvas` test — matplotlib rendering isn't unit-tested elsewhere; the `routes=` param is covered via
`prepare_route_map` shape + a manual mockup check.)*

---

## 10. Work-package order

1. **WP1** resolver + parsers (`_parse_db_ra/_dec`, `_resolve_star_position`, `_load_star_systems_positions`).
2. **WP2** `compute_multi_stop_journey` → its tests green.
3. **WP3** `compute_nearest_neighbor_chain` → tests green.
4. **WP5a** `prepare_route_map` → tests green.
5. **WP5b** `routes=` param on the two canvases (manual mockup-parity check).
6. **WP6** panels + nav + exports (`MultiStopJourneyPanel`, `NearestNeighborPanel`).
7. **WP4 + I3 panel** `compute_trade_route_mst` + `TradeRoutePlannerPanel` (**stretch** — last).
8. **WP8 docs** — `docs/calculators.md` (3 functions, resolution order, schemas, the skip/abort deviation), `docs/gui-architecture.md` (3 panel→nav rows, the `routes=` canvas-param + Phase-O8 note, a Phase I completion row), `future_phases.md` (mark Phase I ✅ at completion).
9. Full suite: `pytest`.

---

## 11. Success criteria

- [ ] Three core functions return the documented dict shapes; each **self-validates** (bad input → `{"error": str}`, never an exception leak).
- [ ] I1 cumulative time/distance match hand-computed values; `times_c`/`ly_hr` derived via `8765.8128`; first unresolvable stop → error naming it.
- [ ] I2 greedy order, `1e-3`-ly self-exclusion, `num_hops` cap, and `stopped_early` (not an error) all hold; empty table → the opt-50 message.
- [ ] I3 (if built) emits `N−1` acyclic edges, ascending, `total_ly` = Σ edges, matching the hand-computed MST.
- [ ] `prepare_route_map` yields dashed ordered edges for I1/I2 and solid MST edges for I3; the `routes=` overlay renders over the dark-navy **Star Chart** / **Star Chart 3D** with the chart's existing zoom-driven label decluttering preserved, **and all existing `make_star_chart_canvas` / `make_star_chart_3d_canvas` callers unaffected** (opts 18/19 + GCNS panels still pass their tests / render unchanged).
- [ ] New "Route Planning" nav category with the panels; each shows its table + the **Star Chart** + **Star Chart 3D** viz tabs (route overlay); Show Diagrams toggle works; red error label on `{"error"}`.
- [ ] **No changes to opts 17–21 behavior** (their tests stay green); `core/`, `gui/`, and docs are the only edits; **no `query.py`/CLI-menu changes**.
- [ ] Whole suite green; new tests offline (Sol + seeded DB + one mocked-SIMBAD branch), no network dependency.

---

## 12. Out of scope

- `query.py` subcommands for the three functions (Phase I is GUI-only; revisit under a future Phase N-style pass if external callers want them).
- Refactoring opts 18/19 to use the new module-level `_parse_db_ra/_dec` (behavior-neutral dedup; optional).
- Designation-based DB resolution (resolver matches `star_name` only; SIMBAD fallback covers the rest).
- Name typeahead / autocomplete over `star_systems` (free-hand text entry only, per §2d — a possible future nicety).
- The light-grey scatter "Map X–Y / X–Z / Map 3D" tabs (opts 18/19's other map style); the route maps use the dark-navy **Star Chart** + **Star Chart 3D** diagrams only.
- Real-time animation of a journey (belongs to Phase O5).
