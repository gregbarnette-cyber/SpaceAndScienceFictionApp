# PHASE I-OPTS — Route Planning: Four New Options · Implementation Plan

> **Status:** mockup approved (`mockups/phase-i-opts.html`). This plan is approved-to-build pending review.
>
> **Scope:** Four **new** Route Planning options added **alongside** the existing Multi-Stop Journey (I1) /
> Nearest-Neighbor Chain (I2) / Trade-Route MST (I3) — **none of the existing three is modified or replaced.**
> Four new core functions in `core/calculators.py`, four new GUI panels in `gui/panels/route_planning.py` under
> the existing **"Route Planning"** nav category, an extension to `core.viz.prepare_route_map` + the `routes=`
> canvas overlay, **three new `query.py` subcommands (A, B, C)**, and a new offline test module. *(As originally
> planned, candidate **D** was GUI-only; post-implementation the user asked to expose it too, so `farthest-first`
> was added and I1/I2/I3 were backfilled — all seven Route Planning options now have a `query.py` subcommand.)*
>
> Reuses verbatim (no changes): `_resolve_star_position`, `_load_star_systems_positions`, `_map_node`,
> `_to_cartesian`, `format_travel_time`, `HOURS_PER_JULIAN_YEAR` (8765.8128), `_UnionFind`,
> `make_star_chart_canvas` / `make_star_chart_3d_canvas` (the dark-navy Star Chart + the additive `routes=` param).

---

## 1. What gets built

| # | Feature | New panel | New core function | query.py | Reused infra |
|---|---|---|---|---|---|
| **A** | Optimal Tour | `OptimalTourPanel` | `compute_optimal_tour(star_names, velocity_input, use_times_c, closed=False)` | `optimal-tour` | resolver, `format_travel_time`, 2-opt (new, local) |
| **B** | Jump-Range Pathfinding | `JumpRoutePanel` | `compute_jump_route(origin, destination, max_jump_ly, optimize="distance")` | `jump-route` | resolver, pool loader, Dijkstra/BFS (new, local) |
| **C** | Jump Network / Reachability | `JumpNetworkPanel` | `compute_jump_network(start, max_jump_ly, max_jumps=None)` | `jump-network` | resolver, pool loader, BFS (new, local) |
| **D** | Farthest-First Coverage | `FarthestFirstPanel` | `compute_farthest_first_chain(start, num_stops, max_reach_ly=None)` | `farthest-first` (added later) | resolver, pool loader, `_map_node` |
| — | Route overlay (shared) | — | `prepare_route_map` extension + `routes=` `"network"` style | — | `prepare_route_map`, the two canvases |

All four core functions are **new** → they **self-validate** and return `{"error": str}` for bad input (the modern
Phase-H/Phase-I contract), so both the GUI red error label and the `query.py` curated-error/exit-1 path work. Each
returns a result dict that includes a **star-map-compatible `stars` list** (via `_map_node`) so the viz layer needs no
re-derivation. **Nav order** (pair each new panel with its sibling):

```
Route Planning
  Multi-Stop Journey            (I1, existing)
  Optimal Tour                  (A, new)   ← set-based, like I1/I3
  Nearest-Neighbor Chain        (I2, existing)
  Farthest-First Coverage       (D, new)   ← I2's opposite
  Jump-Range Pathfinding        (B, new)   ← point-to-point
  Jump Network / Reachability   (C, new)   ← frontier mapping
  Trade-Route Network           (I3, existing)
```

---

## 2. Shared infrastructure (already exists — reused, not changed)

- **`_resolve_star_position(name) -> dict`** — DB-first (`star_systems.star_name`, offline, carries `sp_type`) →
  SIMBAD fallback (`compute_lookup_star_for_distance`, network) → `sol`/`sun` ⇒ origin. Returns
  `{name, x, y, z, ly, sp_type, desig, source}` or `{"error": str}`. Used by **A** (each star), **B** (both
  endpoints), **C** and **D** (the start).
- **`_load_star_systems_positions() -> {"stars":[…]} | {"error": str}`** — all `star_systems` rows as
  `{name, desig, sp_type, ly, x, y, z}` (skips non-positive parallax / unparseable RA·DEC). Empty table →
  `{"error": "star_systems table is empty — run option 50 first to populate it."}`. Candidate pool for **B/C/D**.
- **`_map_node(n) -> dict`** — `{name, desig, sp_type, color, ly, x, y, z}` (spectral-class colour). All four feed
  their result `stars` through this; **C overrides `color`** with a per-tier colour after mapping.

### 2a. Spatial-grid neighbour helper (new, module-level) — `_SpatialGrid(nodes, cell)`
Shared by **B** and **C**. `star_systems` is **~238k rows** (not the "few thousand" first assumed), so an O(n²)
all-pairs adjacency build (~2.8×10¹⁰ pairs ≈ 3.5 h) is infeasible. Instead a uniform 3D grid with `cell = max_jump_ly`
buckets the nodes once (O(n)); `grid.neighbors(i, max_dist)` then yields within-radius neighbours by scanning only the
27 cells around node `i` (correct because any pair within `cell` ly differs by ≤1 cell per axis). B's Dijkstra/BFS and
C's BFS expand nodes lazily over the grid (exiting early once the target pops in B), so each runs in ~2–5 s. B/C still
run in a **background thread** (they may also need SIMBAD for a name endpoint). A spatial-grid optimization is **out of scope** (noted in §11).

The node list for B/C is the pool **plus the resolved endpoint(s)**, de-duplicated: a resolved endpoint that matches
a pool row (case-insensitive name **or** within `1e-3` ly) reuses the pool node so it connects into the graph rather
than floating as a duplicate. Sol (origin `0,0,0`) is **not** a pool row, so it is always added as an extra node.

---

## 3. Candidate A — `compute_optimal_tour(star_names, velocity_input, use_times_c, closed=False)`

**Purpose:** visit a given set of stars in the order that minimizes **total** trip distance.

**Validation** (→ `{"error": str}`):
- Case-insensitive dedup, preserving order; require `>= 2` distinct names (else `"Enter at least two stars."`).
- `velocity_input > 0` (else `"Velocity must be positive."`).
- Resolve every name via `_resolve_star_position`; **first failure** → `{"error": "'<name>': <reason>"}`.

**Algorithm:**
1. `ly_hr` / `times_c` from `velocity_input` + `use_times_c` via `HOURS_PER_JULIAN_YEAR` (mirror I1).
2. `naive_total_ly = tour_len(typed_order, closed)` — the as-typed baseline for the "saved" report.
3. **Nearest-neighbor seed** starting from the **fixed first node** (`typed[0]`).
4. **2-opt**: repeatedly reverse segments `[i..k]` for `1 ≤ i < k ≤ n-1` (the start stays index 0) while it lowers
   `tour_len`; stop at a full pass with no improvement. `tour_len(order, closed)` sums consecutive legs and, when
   `closed`, the wrap leg `order[-1]→order[0]`.
5. Build legs from the optimized order (consecutive; **+ a return leg** when `closed`).

**Returns:**
```
{legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours,
        travel_time, cumulative_time}],
 total_ly, total_hours, total_time,
 naive_total_ly, optimized_total_ly, saved_ly, saved_pct,
 closed, stars:[map dicts in optimized visit order]}
```
`stars[0]` is the fixed start (gold in the panel). `saved_ly = max(naive−optimized, 0)`; `saved_pct` likewise.

---

## 4. Candidate B — `compute_jump_route(origin, destination, max_jump_ly, optimize="distance")`

**Purpose:** route origin→destination through intermediate stars, each single jump ≤ `max_jump_ly`.

**Validation** (→ `{"error": str}`):
- `max_jump_ly > 0`; `optimize ∈ {"distance","jumps"}` (else error).
- Resolve `origin`, `destination`; either failure → its error.
- `origin`/`destination` the same star (same name or within `1e-3` ly) → `"Origin and destination are the same star."`
- Pool needed for intermediates; an empty `star_systems` only errors if neither endpoint can connect — but in
  practice the BFS/Dijkstra over `{origin,dest}` alone simply yields unreachable unless within one jump.

**Algorithm:**
1. Build node list = pool ∪ {origin, dest} (deduped, §2a); `_SpatialGrid(nodes, max_jump_ly)` for neighbour queries.
2. `optimize="distance"` → **Dijkstra** (heap, edge weight = ly); `optimize="jumps"` → **BFS** (unit cost), with
   `prev[]` for path reconstruction; both expand neighbours lazily via `grid.neighbors` and exit early at the target.
3. If destination unreachable → `reachable=False`, empty `route`.
4. Else reconstruct the path; legs = consecutive nodes.

**Returns:**
```
{origin_info, dest_info,          # full resolved dicts (name,x,y,z,ly,sp_type,desig,source)
 reachable (bool), optimize,
 jumps (int), total_ly, direct_ly,    # direct_ly = straight-line origin→dest
 route:[{jump, from, to, jump_ly, cumulative_ly}],
 max_jump_ly,
 stars:[map dicts along the route]}   # for unreachable: just [origin, dest] for context
```
`reachable=False` is a **clear result, not an error** (the GUI shows an amber note; `query.py` returns the dict,
exit 0). The panel additionally draws the in-range **lattice** (`"network"` style edges) behind the route for context.

---

## 5. Candidate C — `compute_jump_network(start, max_jump_ly, max_jumps=None)`

**Purpose:** from `start`, at jump range `max_jump_ly`, map every reachable star and its minimum jump count (tier).

**Validation** (→ `{"error": str}`):
- `max_jump_ly > 0`; `max_jumps` is `None` **or** an int `>= 1` (else error).
- Resolve `start`; failure → its error. Empty pool → the opt-50 message.

**Algorithm:** node list = pool ∪ {start} (deduped); `_SpatialGrid`; **BFS** from start labelling each node with
its tier (min jumps); stop expanding past `max_jumps` when set. Group reachable nodes by tier; the rest are
"out of range".

**Returns:**
```
{start_name, max_jump_ly, max_jumps, max_tier,
 reachable_count, total_in_pool, unreachable_count,
 tiers:[{jumps, stars:[{star_name, desig, sp_type, dist_from_start_ly, ly_from_sol}]}],  # ascending
 stars:[map dicts]}    # color OVERRIDDEN per-tier (TIER_COLORS[min(tier, last)]); start = gold
```
Module-level `TIER_COLORS = ["#FFD700", "#7fd3ff", "#7fe0a0", "#ffd27f", "#ff9bce", "#c8a2ff", …]` (tier 0 = start
gold). The panel builds a dynamic legend from `max_tier` + an "out of range" swatch and draws the reachable lattice
(`"network"` edges).

---

## 6. Candidate D — `compute_farthest_first_chain(start, num_stops, max_reach_ly=None)` *(GUI-only as planned; `farthest-first` subcommand added later)*

**Purpose:** de-clustering exploration — each step picks the unvisited star **farthest** from the visited set.

**Validation** (→ `{"error": str}`):
- `num_stops` an int `>= 1` (else error); `max_reach_ly` is `None` or `> 0`.
- Resolve `start`; failure → its error. Empty pool → opt-50 message.

**Algorithm:** pool minus the start's own row (within `1e-3` ly self-exclusion, like I2). Repeat up to `num_stops`:
for each unvisited candidate compute `min_dist` to the visited set and the **nearest visited index**; among those
with `min_dist ≤ max_reach_ly` (no cap if `None`), pick the **maximum** `min_dist`; attach a tree edge
`nearest_visited → new`. If none within reach → `stopped_early=True`, stop (not an error).

**Returns:**
```
{chain:[{step, star_name, desig, sp_type, sep_to_visited_ly, dist_from_start_ly, ly_from_sol}],
 tree_edges:[{from_index, to_index}],   # indices into stars; the exploration tree
 stars:[map dicts, start at index 0 (gold)],
 widest_ly, stopped_early, start_name}
```

---

## 7. Shared visualization

### 7a. `core.viz.prepare_route_map(result)` — extend (additive)
Today it normalizes I1/I2 (consecutive dashed) and I3 (solid MST). Add three branches, keyed off the result shape:
- **A** (`legs` present, has `closed`): dashed consecutive edges with `①②③…` labels; when `closed`, append the wrap
  edge `stars[-1]→stars[0]`.
- **B** (`route` present): dashed consecutive edges labelled with per-jump ly; plus a `"network"`-style edge set =
  the in-range lattice among the result `stars` (faint, unlabeled, context).
- **C** (`tiers` present): no ordered edges; emit the reachable **lattice** as `"network"` edges; nodes keep their
  per-tier `color`.
- **D** (`tree_edges` present): dashed edges from `tree_edges` (non-consecutive), labelled with the step number.

Output shape unchanged: `{stars, edges:[{x1,y1,z1,x2,y2,z2,label,style}], edge_style}`; `{"error"}` passes through.

### 7b. `make_star_chart_canvas` / `make_star_chart_3d_canvas` — extend the `routes=` style handling (additive)
Add a third edge style **`"network"`** alongside the existing `"dashed"` / `"solid"`: a **thin, faint, unlabeled**
line (`stroke ≈ #2a3a64`, width 1, low opacity), drawn **under** the route edges. Existing callers (opts 18/19, GCNS,
I1–I3) pass only dashed/solid and are **unaffected**. No other canvas change.

---

## 8. `query.py` subcommands (A, B, C in this pass)

New thin dispatchers (mirroring the Phase-H/N pattern) + subparsers; **D was omitted in this pass** (GUI-only as
planned; `farthest-first` + the I1/I2/I3 backfill were added afterward — see the scope note above). All three call the
**self-validating** core functions, so out-of-range input → curated `{"error": str}` (exit 1); argparse rejects
missing/malformed args (exit 2). They resolve **names** → SIMBAD for non-Sol/non-DB endpoints (network — marked `†`).

```
optimal-tour   --stars NAME [NAME ...]  (--ly-hr V | --times-c V)  [--closed]
jump-route     --origin NAME  --destination NAME  --max-jump LY  [--optimize distance|jumps]
jump-network   --start NAME   --max-jump LY  [--max-jumps N]
```
- `optimal-tour`: `--stars` is `nargs='+'`; `--ly-hr`/`--times-c` a **required mutually-exclusive group** (maps to
  `velocity_input` + `use_times_c`, like `travel-time`); `--closed` is `store_true`. → `compute_optimal_tour`.
- `jump-route`: `--optimize` default `"distance"`. → `compute_jump_route`. (`reachable:false` is a normal exit-0 dict.)
- `jump-network`: `--max-jumps` optional int. → `compute_jump_network`.

Each `cmd_*` is one line: `_out(calculators.compute_*(...))`. `docs/integration.md` gains a row per subcommand in the
quick-reference table + a short section each (args, network flag, output keys), and the `†` SIMBAD-for-names note.

---

## 9. GUI wiring — `gui/panels/route_planning.py` + nav + exports

Four new panel classes appended to the existing file, all `(DiagramToggleMixin, ResultPanel)` (same as I1–I3), each
with **Star Chart** + **Star Chart 3D** viz tabs fed by `prepare_route_map`. A shared `_RouteFormPanel` scaffold (or
reuse of the existing route-panel helpers) factors the form/error/`run_in_background` boilerplate. Resolution that may
hit SIMBAD runs in a **background thread** (mirror I1–I3); Sol/DB-only inputs still go through the same path.

| Panel | Inputs | Result tables | Map |
|---|---|---|---|
| `OptimalTourPanel` (A) | stars textarea (1/line, first=start), velocity unit + value, **Closed loop** checkbox | legs table + totals (optimized vs as-typed "saved X ly / Y%") | dashed ordered + closed wrap |
| `FarthestFirstPanel` (D) | start, stops, max reach (blank=∞) | chain table + widest-from-start; amber note when `stopped_early` | dashed exploration tree (step labels) |
| `JumpRoutePanel` (B) | origin, destination, max jump, optimize dropdown | route table + jumps/total/direct; **amber "unreachable" note** when `reachable=False` | dashed route + faint lattice; endpoints only when unreachable |
| `JumpNetworkPanel` (C) | start, max jump, max jumps (blank=∞) | tier-grouped reachability table + reachable/out-of-range counts | tier-coloured nodes + faint lattice; dynamic tier legend |

Nav: insert the four entries into the **"Route Planning"** category in the order of §1. Export the four classes from
`gui/panels/__init__.py`. `docs/gui-architecture.md` gains four panel→nav rows + a viz-tab row each + the
`prepare_route_map`/`routes="network"` note + the Phase-I-OPTS completion row; `docs/calculators.md` gains the four
core functions (signatures, resolution order, return shapes); `docs/integration.md` gains the three subcommands.

---

## 10. Validation matrix (all self-validating → `{"error": str}` + red GUI label / exit-1 JSON)

| Condition | A · Optimal Tour | B · Jump-Route | C · Jump-Network | D · Farthest-First |
|---|---|---|---|---|
| Too few inputs | `< 2` distinct stars → error | — | — | — |
| Bad numeric | `velocity ≤ 0` → error | `max_jump ≤ 0` → error | `max_jump ≤ 0`; `max_jumps < 1` → error | `num_stops < 1`; `max_reach ≤ 0` → error |
| Bad enum | — | `optimize ∉ {distance,jumps}` → error | — | — |
| Same endpoints | — | origin==dest → error | — | — |
| Unresolvable star | first bad star → error naming it | bad origin/dest → error | bad start → error | bad start → error |
| Empty `star_systems` | only if a star needs the DB pool¹ | endpoints resolvable but no intermediates → `reachable=False` | empty pool → opt-50 error | empty pool → opt-50 error |
| No reachable target | n/a | `reachable=False` (**not** an error) | tier set may be just `{start}` (not an error) | `stopped_early=True` (**not** an error) |

¹ A/B resolve names individually — `"Sol"` or a SIMBAD-resolvable name doesn't touch the DB pool; the opt-50 message
surfaces only when a name misses both DB and SIMBAD (the per-name error wins first).

---

## 11. Tests — `tests/test_route_planning_opts.py` (offline) + `tests/test_query_route_opts.py` (subprocess)

**Pattern:** the temp-DB seeding from `tests/test_route_planning.py` / `tests/test_db_backups.py` (swap
`db._DB_PATH`/`db._conn`/`db._auto_seed`, seed a tiny `star_systems`, restore in `tearDown`). All resolution uses
**`"Sol"` (origin, no SIMBAD)** + **seeded DB rows** (DB-first hit) so the suite is **offline**; one test per
function monkeypatches `calculators.compute_lookup_star_for_distance` for the SIMBAD-fallback branch.

**Seed fixture** — stars at exactly-known positions via crafted RA·DEC·parallax (RA `"00 00 00"`/DEC `"+00 00 00"` ⇒
+x; RA `"06 00 00"` ⇒ +y; parallax chosen so `ly` is a round number). Geometry hand-checkable. Include a **tight
cluster** (two rows ~0.1 ly apart) + **spread** rows so A's 2-opt, B's multi-hop, C's tiers, and D's de-clustering
all have something to bite on.

### A — `OptimalTourTest`
- `test_two_star_known_distance` — `["Sol","AX5"]` (AX5 at 5 ly +x), `ly_hr=0.01` → 1 leg `≈5 ly`, `hours≈500`,
  `total_ly≈5`; `stars[0]` is Sol.
- `test_2opt_beats_naive_order` — feed a deliberately bad-order set whose optimal reorder is known →
  `optimized_total_ly < naive_total_ly`, `saved_ly > 0`, and `optimized_total_ly` equals the hand-computed optimum.
- `test_closed_loop_adds_return_leg` — `closed=True` → one extra leg, `total_ly` includes the wrap `last→start`.
- `test_start_fixed` — `stars[0]` is always the first typed star regardless of geometry.
- `test_times_c_unit` / `test_fewer_than_two_error` / `test_zero_velocity_error` / `test_unresolvable_star_error`.

### B — `JumpRouteTest`
- `test_direct_one_jump` — endpoints within `max_jump` → `jumps==1`, route len 2, `total_ly≈direct_ly`.
- `test_multi_hop_via_intermediate` — endpoints **beyond** `max_jump` but linked through a seeded waypoint →
  `reachable=True`, `jumps==2`, route passes through the waypoint; `total_ly` = sum of the two hops.
- `test_unreachable_returns_flag` — `max_jump` too small → `reachable=False`, empty `route`, **no exception**.
- `test_optimize_jumps_vs_distance` — a geometry where min-distance and fewest-jumps differ → the two `optimize`
  modes return different routes (jumps-mode `jumps ≤` distance-mode jumps).
- `test_same_endpoint_error` / `test_bad_max_jump_error` / `test_bad_optimize_error` / `test_unresolvable_endpoint_error`.
- `test_simbad_origin` — monkeypatch the SIMBAD fallback to a fixed position; route computed relative to it.

### C — `JumpNetworkTest`
- `test_tiers_bfs_order` — seeded chain Sol→a→b (each within `max_jump`, but Sol↛b directly) → tier 0 `{Sol}`,
  tier 1 `{a}`, tier 2 `{b}`; `reachable_count==3`, `max_tier==2`.
- `test_out_of_range_excluded` — a seeded star beyond any chain → in `unreachable_count`, not in any tier.
- `test_max_jumps_cap` — `max_jumps=1` → only tier 0 + tier 1 returned.
- `test_node_colors_per_tier` — `stars` colours equal `TIER_COLORS[tier]` (start gold).
- `test_bad_max_jump_error` / `test_bad_max_jumps_error` / `test_empty_table_error` / `test_unresolvable_start_error`.

### D — `FarthestFirstTest`
- `test_picks_farthest_first` — with a cluster + a far star, step 1 picks the **far** star (not the cluster) →
  de-clustering verified (the direct contrast with I2's `test_greedy_order`).
- `test_tree_edge_attaches_to_nearest_visited` — each `tree_edges[i].from_index` is the nearest already-visited node.
- `test_self_exclusion` — a seeded row at Sol's position is never chosen (the `1e-3` ly rule).
- `test_reach_limit_stops_early` — `max_reach_ly` smaller than the gap to any remaining star → `stopped_early=True`,
  `chain` short (not an error).
- `test_num_stops_cap` / `test_bad_stops_error` / `test_bad_reach_error` / `test_empty_table_error`.

### Shared — `PrepareRouteMapOptsTest`
- `test_optimal_dashed_closed` — A result with `closed=True` → dashed edges incl. the wrap; `len(edges)==len(stars)`.
- `test_jump_route_dashed_plus_network` — B result → dashed route edges **and** `"network"`-style lattice edges present.
- `test_jump_network_tier_nodes` — C result → `edge_style`/`"network"` lattice; node colours per tier; no ordered edges.
- `test_farthest_tree_edges` — D result → dashed edges matching `tree_edges` by node coordinates.
- `test_error_passthrough` — `{"error":"x"}` in → same out (all four shapes).

### `query.py` subprocess contracts — `tests/test_query_route_opts.py`
Mirror `tests/test_query_phase_n.py`: pass a throwaway seeded DB via the `SPACE_APP_DB` env var; assert offline
happy-path JSON for `optimal-tour` (with `--ly-hr` / `--times-c` parity + `--closed`), `jump-route` (reachable +
`reachable:false` both exit 0), `jump-network`; the curated-error/exit-1 matrix (bad numeric/enum → `{"error"}`); and
the argparse exit-2 matrix (missing `--max-jump`; both/neither of `--ly-hr`/`--times-c`). All endpoints use `"Sol"` +
seeded rows so the subprocess never hits the network.

---

## 12. Work-package order

1. **WP1** `_SpatialGrid` neighbour helper + module-level `TIER_COLORS`.
2. **WP2** `compute_optimal_tour` (A) → `OptimalTourTest` green.
3. **WP3** `compute_jump_route` (B) → `JumpRouteTest` green.
4. **WP4** `compute_jump_network` (C) → `JumpNetworkTest` green.
5. **WP5** `compute_farthest_first_chain` (D) → `FarthestFirstTest` green.
6. **WP6** `prepare_route_map` extension + `routes="network"` canvas style → `PrepareRouteMapOptsTest` green
   (+ manual mockup-parity check).
7. **WP7** four panels + nav entries + `__init__` exports.
8. **WP8** `query.py` `optimal-tour` / `jump-route` / `jump-network` + `tests/test_query_route_opts.py` green.
9. **WP9 docs** — `docs/calculators.md` (four functions), `docs/gui-architecture.md` (panels/nav/viz rows + the
   `routes="network"` note + completion row), `docs/integration.md` (three subcommands + the SIMBAD-for-names note).
10. Full suite: `pytest`.

---

## 13. Success criteria

- [ ] Four core functions return the documented dict shapes; each **self-validates** (bad input → `{"error": str}`,
      never an exception leak).
- [ ] **A**: 2-opt total ≤ the as-typed total on every fixture; `optimized_total_ly` equals the hand-computed
      optimum; start fixed at `stars[0]`; closed loop adds the wrap leg; `ly_hr`/`times_c` via `8765.8128`.
- [ ] **B**: direct, multi-hop-via-waypoint, and **unreachable** (`reachable=False`, no exception) all hold;
      `optimize="jumps"` never returns more jumps than `"distance"`; same-endpoint → error.
- [ ] **C**: BFS tiers correct; `max_jumps` cap honoured; out-of-range stars excluded from tiers and counted;
      node colours per-tier with start gold.
- [ ] **D**: farthest-first selection (de-clustering) verified against the I2 clustering case; `1e-3` self-exclusion;
      tree edges attach to the nearest visited; `stopped_early` (not an error); `num_stops` cap.
- [ ] `prepare_route_map` emits the right edges per candidate (dashed ordered / dashed tree / faint `"network"`
      lattice), and the `routes="network"` style renders under the route on **both** Star Chart canvases **with all
      existing `make_star_chart_canvas`/`make_star_chart_3d_canvas` callers unaffected** (opts 18/19 + GCNS + I1–I3
      still pass / render unchanged).
- [ ] Four new "Route Planning" nav entries in the §1 order; each panel shows its table(s) + Star Chart + Star
      Chart 3D viz tabs; Show Diagrams toggle works; red error label on `{"error"}`; B's unreachable + D's
      `stopped_early` show amber notes; C shows the dynamic tier legend.
- [ ] `query.py` `optimal-tour` / `jump-route` / `jump-network` return the core dicts; curated `{"error"}`/exit-1 on
      out-of-range; argparse exit-2 on missing/malformed; **D has no subcommand**.
- [ ] **Existing I1/I2/I3 and opts 17–21 behaviour unchanged** (their tests stay green); only `core/`, `gui/`,
      `query.py`, docs, and the two test modules are edited.
- [ ] Whole suite green; new tests offline (Sol + seeded DB + one mocked-SIMBAD branch per function), no network
      dependency.

---

## 14. Out of scope

- A k-d-tree / cached-grid acceleration beyond the `_SpatialGrid` (the uniform grid already makes B/C ~2–5 s at the
  real 238k-row scale; rebuilding the grid per call is acceptable for user-initiated, background-threaded actions).
- *(Done after the initial pass, on user request: **D** got a `query.py` subcommand (`farthest-first`) and I1/I2/I3 were backfilled (`multi-stop` / `nearest-neighbor` / `trade-route`) — all seven planners now have `query.py` surfaces.)*
- Designation-based DB resolution / name autocomplete (free-hand text + DB-name/SIMBAD only, per the existing resolver).
- A closed-loop / round-trip variant of B, or a weighted (fuel/time) jump cost beyond straight-line ly.
- Animation of a route; the light-grey scatter map tabs (route maps use the dark-navy Star Chart pair only).
