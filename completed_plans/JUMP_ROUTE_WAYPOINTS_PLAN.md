# Jump-Route Waypoints Plan

**Status: COMPLETE — all four phases built 2026-07-31**, both `/code-review` checkpoints run and
their findings folded in (§12 Checkpoint A, §13 Checkpoint B). Moved to `completed_plans/` on
completion. Phase 1 = core + tests + `docs/calculators.md` §B +
`CLAUDE.md` (Checkpoint A run, findings folded in — see §12; parts of Phase 3's contract/echo work
were pulled forward there). Phase 2 = the GUI Via field, the ◆ marker + visit-order line, the
unreachable-branch rework, `docs/gui-architecture.md`, `tests/test_route_chart_tabs.py`; verified in
the app (Sol → 38 Vir via 70 Vir at max-jump 15 → 10 jumps, 119.670 ly, ◆ on `*  70 Vir`).
**Phases 3 and 4 were merged into one pass** (user decision, 2026-07-31) — Phase 3 had shrunk to the
`--via` flag alone (its contract/echo work was pulled forward into Phase 1's Checkpoint-A fixes), and
Phase 4 turned out to be fully verifiable in that session (`dustmaps`/`healpy` installed, **both maps
already fetched**), so the plan's "Phase 4 last, it may be unverifiable" rationale did not apply.
Merging means the §5 **interim `--via` + `--weight dust|blend` → exit 1 restriction was never
written**, and neither was its doc note — removing the §9 doc-drift risk it created. The
`IMPROVEMENT_PLAN.md` P2.6 collision (§4) was also moot: P2.6 is **already built** (`seg_memo` /
`_seg_cached` / `_compare(..., memo=)` are in `core/dust_routing.py`), though its
`IMPROVEMENT_PLAN.md:199` entry still reads as pending and wants a separate cleanup. Investigated 2026-07-31;
revised the same day after a three-reviewer pass (see §11).

> ⛔ **Build gates (both discharged 2026-07-31):** this plan had two mandatory `/code-review` stops —
> after **Phase 1** and after **Phase 4**. Both were run by the user and every finding was fixed
> inside the phase that produced it; see **§12** and **§13** for the dispositions, including the two
> findings that were *rejected on measurement* rather than applied. The §6 gate procedure is kept
> below as the historical record.

Add **required intermediate stars** ("via" waypoints) to the Phase I-OPTS **B — Jump-Range
Pathfinding** planner: route Sol → 38 Virginis with a hard requirement that the path passes
through 70 Virginis, every single jump still ≤ the max jump range.

---

## 0. Decisions (settled 2026-07-31)

| # | Decision | Choice |
|---|---|---|
| D1 | Modify in place vs. a second planner | **Modify** `compute_jump_route` with an additive, defaulted `via=None` |
| D2 | Ordered (as typed) vs. unordered waypoints | **Unordered, always** — waypoints are a *set*; the planner picks the cheapest order |
| D3 | Do the dust/blend forks get `via`? | **Yes** — via a shared helper all three call |
| D4 | Output shape | **Flat + additive** — `route[]` stays as-is; three new always-present keys |
| D5 | Duplicate / self-referential waypoint | **Error**, checked on **post-merge node indices** (see §7) |
| D6 | Waypoint cap | **8**, justified against stage-1 search cost (see §1) |

**D1 rationale.** The Phase T precedent of *forking* rather than parameterizing
(`future_phases.md:130`) was driven entirely by keeping the optional `dustmaps`/`healpy` import out
of `core/calculators.py`. Waypoints add no dependency, no data source and no new output *kind* —
they add one input. A duplicate planner would multiply the surfaces in §4 and would force the dust
and blend forks to duplicate too: 2 → 6 near-identical functions. The additive-defaulted parameter
is the established idiom here (H3's Domingos keys, the `routes=` chart kwarg, `_grid_search`'s own
`edge_cost` seam).

**D2 rationale.** The requirement is "these stars must be visited", not "in this sequence". The
ordering stage minimizes whatever the existing **Optimize For** dropdown already selects, so no new
control is needed — `--via-order fixed|optimal` is **explicitly not built** (§10).

**D3 note.** The dust weighting is a **`query.py`-only** surface — `JumpRoutePanel` calls
`core.calculators.compute_jump_route` directly (`gui/panels/route_planning.py:896-899`) and has no
weight control. `--weight dust|blend` exists only on `query.py jump-route`, and needs the optional
WSL/Linux-only `dustmaps` extra.

---

## 1. Algorithm

A **fixed-endpoint Hamiltonian path over the metric closure** of the terminals — a small TSP-path.
Three stages, all under whatever metric `optimize` selects.

### Stage 1 — metric closure (pairwise shortest paths)

Terminals = origin + destination + k waypoints (k+2 nodes). Run the **existing**
`_grid_search` (`core/calculators.py:2004`) between each terminal pair.

- Pairs needed: `C(k+2, 2) − 1` — the direct origin↔destination pair is never used, since with
  k ≥ 1 the path must route through waypoints. k=1 → 2 searches, k=2 → 5, k=3 → 9, k=8 → 44.
- **Costs are symmetric**, so each unordered pair is computed once and the stored path reversed for
  the opposite direction. Adjacency is symmetric (`_SpatialGrid.neighbors`,
  `core/calculators.py:1981-1999`, computes `d` with identical term order both ways; cell size ==
  jump radius guarantees mutual visibility), and the dust cache is already keyed on a sorted index
  pair (`core/dust_routing.py:182`, `:295`).
  - **Precision caveat.** `cost(i,j) == cost(j,i)` holds only up to float summation order — Dijkstra
    accumulates `du + edge_cost(...)` along the path, so reversing can differ by ULPs. Harmless
    except in a near-tie. Likewise, the *reversed stored path* is always a **valid** optimal path,
    but not necessarily the same path a forward search would return: Dijkstra tie-breaks on heap
    order over `(dist, index)` (`:2032-2046`) and BFS `prev` is first-discovery order (`:2028`).
    Do not assert path equality in tests; assert cost equality with a tolerance.
- `nodes` / `grid` are built **once** and shared across every pairwise search. **All terminals must
  be merged into `nodes` before the grid is constructed** — `_SpatialGrid.__init__`
  (`core/calculators.py:1971-1979`) indexes at construction time, so a node appended afterwards is
  silently invisible to `neighbors()`.
- **Reconstruct each pair's path immediately** and discard its `prev` array. Retaining 44 `prev`
  arrays of ~256k ints is ~90 MB.

**Why not k+2 exhaustive single-source sweeps?** *(rationale corrected — the original claim was
wrong)* It does **not** require changing `_grid_search`: passing a sentinel target that is not a
valid index (e.g. `-1`) makes `if u == t: break` never fire, yielding a full sweep. The honest
trade is 10 full sweeps versus 44 partial ones, and the early exit **only fires on success** — an
unreachable leg expands the entire reachable component regardless. So the pairwise approach is not
clearly cheaper in the worst case. It is chosen because it reuses the existing call shape verbatim
and reconstructs less state; **if measured latency disappoints, switching to sweeps is a small,
localized change**, not a redesign.

> **SETTLED BY MEASUREMENT (2026-07-31, Checkpoint A).** The sweep closure was actually built and
> timed against the live 256k-row pool, and it is **far worse**: Sol → 38 Vir via 70 Vir at
> `max_jump 20` took **227 s** as k+2 sweeps versus **4.96 s** as pairs (k=3 pairs: 11.7 s;
> un-waypointed: ~7 s). The asymmetry the plan text missed is that the early exit fires on the
> *common* case — `_grid_search` stops when the target pops, while a sweep must settle the entire
> reachable component, which at any usable jump range is most of the catalogue. Pairwise stays.
> The comment in `_route_through` records this so it is not "optimized" back.

### Stage 2 — order selection

Brute force over the `k!` permutations of waypoints (origin pinned first, destination pinned last),
summing the stage-1 pair costs; keep the minimum. At the cap of 8 that is 40 320 table lookups —
negligible. **Permutations are not the bottleneck** and never were; stage 1 is (see D6). Held–Karp
is therefore *not* the natural upgrade path — raising the cap is bounded by search count, not by
`k!`.

**Tie-breaking must be deterministic.** Under `optimize="jumps"` the objective is an integer hop sum
over ≤ 8 waypoints, so ties are common and the "optimal" order is frequently non-unique. Break ties
on the permutation's tuple of waypoint indices so repeated runs return the same route.

### Stage 3 — stitch

Concatenate the winning order's stored per-leg node paths, **de-duplicating the junction node** at
each seam. The result is a flat list of node indices exactly as the current single-search
reconstruction produces, so `stars[]` stays `len == jumps + 1` in path order.

### Accepted caveats (document, do not "fix")

- **The stitched route is not a simple path.** Legs may reuse stars, so a star can appear twice in
  `route[]`/`stars[]`. Per-leg optimal ≠ globally optimal for the whole trip. Inherent to waypoint
  routing; forcing node-disjointness makes it NP-hard. **This is `jump-route`'s first-ever repeated
  star** — `multi-stop`/`optimal-tour` already do it, `jump-route` never has — so it must be called
  out in the panel `DESCRIPTION`, `docs/calculators.md`, **and** the `docs/integration.md` change
  note (§3).
- **`optimize="jumps"` ignores `edge_cost` entirely** (`core/calculators.py:2018-2029`: the BFS
  branch never calls it). So `--weight dust --optimize jumps` is unaffected by dust *today*, with or
  without waypoints, and no dust memoization warms across legs in that mode. Pre-existing behaviour;
  worth stating because waypoints make it more visible.

---

## 2. Core API

```python
def compute_jump_route(origin, destination, max_jump_ly,
                       optimize="distance", via=None) -> dict
```

`via` is `None` or a list of star names.

### The `via=None` guard, stated precisely

With `via=None` **every pre-existing key must be byte-identical to today's output**; the three new
keys of §3 are the only difference. (The earlier draft said "byte-identical", which contradicted
§3's always-present `via: []`. The test must be written to the precise form or it will be wrong.)

Note that `tests/test_dust_routing.py:300-311` — cited in the first draft as an existing guard — is
**not** one: it only asserts `assertNotIn("total_av", …)`, `assertNotIn("weight", …)` and
`reachable`. It compares no route content and would not detect drift in `route[]`, `stars[]`,
`total_ly` or `jumps`. The real guard is new work in Phase 1.

### Shared helper (new, in `core/calculators.py`)

```python
def _route_through(nodes, grid, s, t, via_idx, max_jump_ly, optimize, edge_cost):
    """Stages 1-3. Returns (path_indices, unreachable_leg) where unreachable_leg is
    None on success or {"from": name, "to": name} naming the pair that has no route."""
```

Called by all three of `compute_jump_route`, `compute_jump_route_dust`
(`core/dust_routing.py:151`) and `compute_jump_route_blend` (`:255`), each passing its own
`edge_cost` exactly as it already passes one to `_grid_search`. Each caller keeps its own leg-detail
building (the dust forks add per-leg A_V), so the forks' distinctive output is untouched.

With `via_idx` empty the helper is a straight passthrough to the existing single `_grid_search` call
+ reconstruction — one code path, no `if via` branch triplicated.

**Refactor safety** (verified): `compute_jump_route` (`:2174-2244`) is a clean
validate → resolve → pool → merge → grid → search → reconstruct sequence; extracting the last two
steps preserves float op order. All callers pass ≤ 4 positionals
(`gui/panels/route_planning.py:896`, `query.py:1238`, `core/dust_routing.py:234`/`:351`), so a 5th
defaulted parameter is safe. `_grid_search` is safe to call repeatedly: it allocates fresh
`prev`/`dist_arr` per call (`:2016-2017`), holds no module state, and both early exits leave
reconstruction correct (the Dijkstra break fires *after* `done[u] = True`; BFS sets `prev[v]` and
`dist_arr[v]` together, so `dist_arr[t] == inf ⟺ prev[t] == -1`).

---

## 3. Output contract (additive)

Unchanged and byte-identical: `origin_info`, `dest_info`, `reachable`, `optimize`, `jumps`,
`total_ly`, `direct_ly`, `max_jump_ly`, `route[]`, `stars[]`. `route[]` stays **flat and
continuously numbered** (`jump: 1..n`) across the whole trip.

**Three new keys, all always present** — no present-or-absent optionals. Every other boolean in this
family is always present (`fully_covered` on each dust route row `core/dust_routing.py:225`,
`reachable`, `stopped_early`, `clamped`, `capped`), and optional keys break typed deserialization
and tabular flattening:

| Key | Always present | Meaning |
|---|---|---|
| `via: []` | yes | Resolved waypoint names in the **chosen visit order**; `[]` when unused |
| `via_legs: []` | yes | Per waypoint-to-waypoint summary `{from, to, jumps, ly}`; `[]` when unused |
| `unreachable_leg: null` | yes | `{from, to}` naming the failed hop when `reachable: false`; `null` otherwise |

And one new **always-present boolean** on every `route[]` row:

| Field | Meaning |
|---|---|
| `waypoint: false` | `true` on the row that **arrives at a waypoint at a leg boundary** — flagged **by route index, not by name match**, so a leg that incidentally passes back through a waypoint is *not* flagged. Invariant: `count(waypoint == true) == len(via)`. |

`route[]` invariants worth promising to consumers: `route[i]["from"] == route[i-1]["to"]`, and
`len(stars) == jumps + 1`.

**Consumer hazard to announce explicitly** (this is the part that bites): because a route may
revisit a star, `len({s["name"] for s in stars}) != len(stars)` is now possible, and any
`{s["name"]: s for s in stars}` index silently loses route position. That belongs in the
`docs/integration.md` change note, not only in the panel description.

**Not** nesting `route[]` into legs — it would break every existing consumer and the
`prepare_route_map` B-branch.

### Unreachable

Today's branch returns `stars=[origin, dest]` with an empty `route`. Extend to return **all
terminals** (origin + waypoints + destination) so the chart still shows the requested stars, plus
`unreachable_leg`. Any permutation containing an infinite-cost pair is infinite; if every permutation
is infinite, report the first infinite pair found. **This changes the shipping unreachable shape**,
so it touches the GUI branch, the docs and two test fixtures (§4, §8).

### Visualization

`prepare_route_map`'s B-branch (`core/viz.py:1385-1395`) needs **no change** — verified: it is purely
index-parallel (`stars[i] → stars[i+1]`, guarded by `if i + 1 < len(stars)`), so a revisiting route
still produces correct edges. Downstream survives duplicates too: canvas coord maps are name-keyed
(`gui/visualizations/plot_helpers.py:1455`, `:1647`) and `_dedupe_find_rows`
(`gui/panels/diagram_tabs.py:466-478`) already exists because Multi-Stop/Optimal Tour emit repeated
names.

**Cosmetic consequences to accept and document** (not in the first draft): a revisited star is
scattered and labelled **twice at identical coordinates**, so its label renders doubled; if the route
revisits the **origin**, only index 0 becomes the gold ★ (`plot_helpers.py:1866`
`body_stars = plotted[1:]`), so the second copy paints an ordinary dot and label on top of it; and
duplicates count toward `_ROUTE_SPARSE_MAX_NODES = 25` (`gui/panels/route_planning.py:173`), the
label-declutter threshold. Legend counts are unaffected. *Optional nicety:* recolour waypoint dots —
deliberately **out of scope** (§10).

---

## 4. Surfaces to touch

The first draft's table missed most of the documentation surface. Full inventory:

### Code

| Surface | File | Change |
|---|---|---|
| Core | `core/calculators.py:2174` | `via=None`; extract `_route_through` |
| Dust fork | `core/dust_routing.py:151` | `via=None`; call `_route_through` with `dust_cost`; **thread `via` into the `dref` comparison call at `:230`** |
| Blend fork | `core/dust_routing.py:255` | same, `blend_cost`; **`dref` at `:346`** |
| GUI form | `gui/panels/route_planning.py:851-875` | One `QLineEdit` "Via (optional, comma-separated):" between Destination and Max Jump; split, strip blanks, pass the list; add to `enter_fields`; extend `DESCRIPTION` |
| GUI unreachable branch | `gui/panels/route_planning.py:911-921` | The amber note hardcodes `f"No route from {o} to {d}"` — must render `unreachable_leg` instead, since the failed hop may be `Sol→70 Vir`. Also revisit `find_box=False` (`:918`): its stated rationale is "the chart is just the two endpoints" (`:198-200`), which is false with k+2 terminals |
| `query.py` | `cmd_jump_route:1217`, parser `:3248` | `--via` (`nargs="+"`, default `None`) threaded to all three branches |

**The `dref` bug is the plan's most important late catch.** Both forks build their distance-optimal
comparison as `calc.compute_jump_route(origin, destination, max_jump_ly, "distance")` with no `via`
(`core/dust_routing.py:230`, `:346`), feeding `dref["stars"]` to `_compare` (`:132-146`). Without
threading `via`, the documented `extra_ly` / `saved_av` compare a **waypoint-constrained** dust route
against an **unconstrained** distance route — both numbers become meaningless.

### Docs

| File | Lines | Change |
|---|---|---|
| `docs/integration.md` | `:260` | Quick-reference row: `[--via N [N …]]` + the new keys |
| `docs/integration.md` | `:2539-2551` | The full `jump-route` section: core signature, output key list, and the "unreachable → empty `route`" sentence §3 amends |
| `docs/integration.md` | `:3042-3059` | Dust-weighted routing section (fork list + `_grid_search` seam) — Phase 4 |
| `docs/integration.md` | `:3072-3084` | `--weight blend` section carries `compute_jump_route_blend(...)`'s signature — Phase 4 |
| `docs/integration.md` | top | **A dated `### ` change note**, per the convention at `:47`, `:60`, `:83` — states what changed, that it is additive, and the consumer bullets (the revisit hazard above). Phase 3 deliverable, not a follow-up |
| `docs/calculators.md` | `:328` | §B signature gains `via=None` |
| `docs/calculators.md` | `:333-334` | States unreachable is `stars=[origin, dest]` — contradicted by §3 |
| `docs/calculators.md` | `:338` | GUI table line — waypoint marker if surfaced |
| `docs/calculators.md` | `:422-431` | Dust-weighted variants: repeats the fork list + the `_grid_search` byte-identity claim `_route_through` supersedes — Phase 4 |
| `docs/gui-architecture.md` | `:835` | States verbatim *"Jump Route's `reachable=False` two-endpoint chart passes `find_box=False`"* — stale under §3 |
| `docs/gui-architecture.md` | `:917` | Phase I-OPTS row summarizing `compute_jump_route` + the B-branch |
| `docs/testing.md` | `:35`, `:42`, `:45` | Per-file test descriptions for the three test files that gain cases |
| `CLAUDE.md` | `:49` | "Dust-weighted routing reuses a `_grid_search` seam extracted from `compute_jump_route`" — after §2 the shared seam is `_route_through` |

### Coordination

- **`IMPROVEMENT_PLAN.md:199-214` (P2.6) is a pending, unbuilt refactor of the same two fork
  functions Phase 4 rewrites** — it stashes the full `_seg` dict in `cost_cache` and has the
  post-search route-detail loop read from it, with a constraint that `_seg` stay mock-patchable.
  Phase 4 must either absorb P2.6 or explicitly sequence against it; they collide on the same lines
  and neither currently cites the other.
- `.claude/settings.local.json:97-98` pre-approves two exact `query.py jump-route …` strings;
  Phase 3's `--via` verification commands won't match and will prompt. Trivial, noted for
  expectation-setting only — **no settings change is proposed here.**

**No new GUI control beyond the textbox** — no toggle, no checkbox, no second dropdown. An empty Via
field *is* the off switch (the `JumpNetworkPanel` blank-"Max Jumps" idiom), and **Optimize For**
already supplies the objective the ordering stage minimizes.

---

## 5. Build phasing

Four phases. **Each leaves the tree green and is independently shippable.** Phases 2–4 depend on
Phase 1 and nothing else. Caveat: Phases 2 and 3 both edit `docs/calculators.md` §B, so they will
conflict if done in parallel.

### Phase 1 — Core + tests *(prerequisite for everything)*

Extract `_route_through`, add `via=None`, implement the three stages and the §7 validation. Update
`docs/calculators.md` §B (signature, unreachable shape) and `CLAUDE.md:49`.

- **Files:** `core/calculators.py`, `docs/calculators.md`, `CLAUDE.md`,
  `tests/test_route_planning_opts.py`
- **Done when:** the §2 guard test passes (every pre-existing key identical under `via=None`)
  alongside the new waypoint tests, and the full suite is green.
- **User-visible:** nothing.
- **Why first:** the guard is the feature's one real regression risk (§9), and no such guard exists
  today (§2). Pin it before anything depends on the function.
- ⛔ **GATE — do not start Phase 2.** Stop and tell the user, verbatim:
  > *Phase 1 is complete and the suite is green. This is Checkpoint A — please run `/code-review`
  > before I start Phase 2. Tell me to continue when it's done, or say "skip review" to waive it.*

  Wait for the answer. If findings come back, fix them **inside Phase 1** and re-offer the gate.

### Phase 2 — GUI *(the payoff)*

The Via textbox, the `DESCRIPTION` rewrite (what it does, the revisit caveat, the cap), **and the
unreachable-branch rework** (`route_planning.py:911-921` — render `unreachable_leg`; decide
`find_box`). `docs/gui-architecture.md:835`, `:917`.

- **Files:** `gui/panels/route_planning.py`, `docs/gui-architecture.md`, `docs/calculators.md:338`,
  `tests/test_route_chart_tabs.py`
- **Done when:** Sol → 38 Virginis via 70 Virginis routes through 70 Vir in the app, and the
  unreachable fixture in `test_route_chart_tabs.py:93-103` is updated to the new shape.
- **Verify in the app**, not only via tests — this is what the request was about.

### Phase 3 — `query.py` + integration contract

`--via` on the plain path; the `docs/integration.md` row, the full `:2539` section, and the **dated
change note**. Add the `via: []` / `via_legs: []` / `unreachable_leg: null` echo to the two forks
here as well (a few lines, no `dustmaps` involvement) so the always-present promise of §3 holds
across every `--weight` value even before Phase 4.

- **Files:** `query.py`, `docs/integration.md`, `core/dust_routing.py` (echo only),
  `tests/test_query_route_opts.py`
- **Done when:** `jump-route --origin Sol --destination "38 Vir" --max-jump 9 --via "70 Vir"` returns
  a route containing 70 Vir, and the exit-code cases hold.
- **Interim rule if Phase 4 is deferred:** `--via` with `--weight dust|blend` must **error**, not be
  silently ignored. Specifically: in `cmd_jump_route` (`query.py:1217`) **before the fork dispatch**,
  emit `{"error": "--via is not supported with --weight dust|blend."}` → **exit 1** (this family's
  curated-error convention, `docs/integration.md:2519-2523`; *not* argparse exit 2). The doc must
  describe **what ships** — an interim restriction note in Phase 3 that Phase 4 then *removes* and
  replaces with a composition note. (The first draft had §4 and §5 contradicting each other here.)

### Phase 4 — Dust / blend forks *(last, deliberately)*

`via` on `compute_jump_route_dust` / `_blend`, the `dref` fix, the `--weight` wiring, gated tests,
`docs/integration.md:3042`/`:3072`, `docs/calculators.md:422`.

- **Done when:** the gated dust tests pass **in the WSL venv with the `dustmaps` extra** and skip
  cleanly without it, and `extra_ly`/`saved_av` compare like-for-like.
- **Why last:** the only phase unverifiable on a Windows checkout (`tests/_dustcheck.py` gating), so
  a Windows-only session can still complete Phases 1–3 in full.
- **Sequence against `IMPROVEMENT_PLAN.md` P2.6** before starting.
- ⛔ **GATE — do not consider the feature done.** Stop and tell the user, verbatim:
  > *Phase 4 is complete. This is Checkpoint B — please run `/code-review` on the fork changes.
  > Tell me to continue when it's done, or say "skip review" to waive it.*

  Then offer the optional final pass (§6) if the phases landed as separate commits over time.

---

## 6. Code-review checkpoints

`/code-review` is user-triggered and billed, so these are **prompts for you to run it**, not
something the build does on its own. Two checkpoints plus one optional final pass — not one per
phase, because Phases 2 and 3 are mechanical wiring where review yield is low.

**Obligation on whoever is building.** The two checkpoints are ⛔ **hard stops**, marked in §5 at the
end of Phase 1 and Phase 4. At each one: halt, surface the reminder, and **do not begin the next
phase** until the user says the review ran or explicitly waives it. Do not silently skip a gate
because the suite is green — the suite passing is the *precondition* for the gate, not a substitute
for it. If review findings come back, fix them inside the phase that produced them and re-offer the
gate rather than carrying them forward.

### Checkpoint A — end of Phase 1 *(the important one)*

Run `/code-review` on the working diff before Phase 2 starts. This is where essentially all the risk
lives: a new graph algorithm, a refactor that must not perturb existing output, and the validation
rules. Reviewing here also means Phases 2–4 build on reviewed foundations rather than compounding a
defect across four phases.

**Prompt to give the user at this gate:**

> Phase 1 is complete and the suite is green. This is Checkpoint A — please run `/code-review`
> before I start Phase 2. Tell me to continue when it's done, or say "skip review" to waive it.

Ask the review to weigh specifically:
- the `via=None` path against §2's precise guard (every pre-existing key identical);
- stage-3 stitching when legs overlap — off-by-one at the junction de-dupe;
- stage-2 tie-breaking determinism under `optimize="jumps"`;
- the post-merge duplicate-terminal check (§7) — the subtle one the first draft got wrong;
- that all terminals are merged **before** `_SpatialGrid` construction.

### Checkpoint B — end of Phase 4

**Prompt to give the user at this gate:**

> Phase 4 is complete. This is Checkpoint B — please run `/code-review` on the fork changes.
> Tell me to continue when it's done, or say "skip review" to waive it.

Run `/code-review` on the fork changes. Narrower but high-consequence: the `dref` threading, the
shared-helper call sites, and whatever P2.6 coordination was chosen. The dust path has the weakest
automated coverage (gated tests, WSL-only), so human/AI review substitutes for CI here more than
elsewhere.

### Optional — final pass before merge

If the four phases land as separate commits over time, `/code-review ultra` on the whole branch
before merge catches cross-phase drift — chiefly docs that describe an interim state (the Phase 3
restriction note that Phase 4 should have removed) and contract text that disagrees between the
quick-reference row and the detailed `:2539` section. Skip it if the phases land close together and
Checkpoints A and B were both clean.

**`/security-review` is not applicable** — no network surface, no auth, no untrusted input beyond
star names that already flow through the existing resolvers.

---

## 7. Validation / edge cases

- **Cap:** more than **8** waypoints → `{"error": "At most 8 waypoints."}`. **Enforced before
  resolution**, so 9 waypoints don't fire 9 SIMBAD lookups before erroring. Count after dropping
  whitespace-only entries; the `"Waypoint N"` index in messages is 1-based over the **stripped**
  list.
- **Type:** `via` must be `None` or a list of strings. A bare string iterates as characters —
  `query.py`'s `nargs="+"` protects that surface, but the GUI splits a textbox and the core function
  is called directly by three modules. Coerce or reject.
- **Unresolvable waypoint** → `{"error": "Waypoint 2 ('…'): <reason>"}`, matching
  `compute_multi_stop_journey`'s "Stop N" fail-fast wording.
- **Duplicate / self-referential terminal — check on post-merge node indices (D5, corrected).** The
  first draft compared *resolved records* pairwise at 1e-3 ly, mirroring the existing
  origin-vs-destination check (`core/calculators.py:2192`). That is insufficient: `_merge_endpoint`
  (`:1950-1958`) matches against **pool rows** by name **or** ≤ 1e-3 ly, so two terminals each within
  1e-3 ly of the *same* pool star can be up to 2e-3 apart from each other — they pass the pairwise
  check and still merge to one index. That yields `s == t` for a stage-1 pair, a 1-node path, and a
  seam that silently de-dupes to nothing. **Rule: error if any two terminals resolve to the same node
  index after merge.**
- **`"Sol"`/`"Sun"`** both resolve to the origin (`core/calculators.py:1613-1615`), so
  `origin="Sol", via=["Sun"]` is caught by the coordinate arm even though the name arm misses.
  State it as *tested* — it is the obvious reviewer question.
- **Alias divergence (accepted caveat, not a fix).** `_resolve_star_position` returns DB coordinates
  for a name in `star_systems` and SIMBAD coordinates otherwise, so two aliases of one star resolving
  via different paths can land > 1e-3 ly apart and merge as **two** nodes. The route then "visits" a
  phantom duplicate over a ~0.005 ly jump. Pre-existing, but waypoints are the first feature where a
  user is likely to type an alias — say so rather than stay silent.
- `via=[]` / `via=None` / whitespace-only entries → no waypoints.
- **Performance note:** `_merge_endpoint` is an O(n) scan with `.strip().lower()` + `_node_dist` per
  row (`:1954-1956`). Going from 2 to 10 terminals is ~2.5M iterations before any search starts.
  Acceptable, but measure it rather than assume.

---

## 8. Tests

| File | Add |
|---|---|
| `tests/test_route_planning_opts.py` (`JumpRouteTest`, `:142`) | Route through a seeded waypoint visits it; **the §2 guard** (every pre-existing key identical under `via=None`) — the load-bearing test; reordering (two waypoints typed in the expensive order return the cheap order); tie-break determinism under `jumps`; unreachable waypoint → `reachable=False` + `unreachable_leg`; each §7 validation error incl. the **post-merge** duplicate case and `Sol`/`Sun`; the cap |
| `tests/test_route_planning_opts.py` (viz section, `:366`) | **New coverage gap:** `prepare_route_map` on a route whose `stars[]` repeats a star. Nothing tests this today, and it is exactly what §3's "no change required" asserts |
| `tests/test_query_route_opts.py` (`:103`) | `--via` reachable exit 0; bad waypoint exit 1; over-cap exit 1; the Phase-3 interim `--via` + `--weight dust` error → exit 1 |
| `tests/test_route_chart_tabs.py` | **Omitted from the first draft entirely.** `_unreachable_jump_route()` (`:93-103`) hardcodes `stars=[origin, dest]`, `route=[]` — the exact shape §3 changes; consumed at `:161`, `:217-224`. `_ROUTE_PANELS` (`:374`) drives `RouteDescriptionTest`, which the Phase 2 DESCRIPTION rewrite runs through |
| `tests/test_dust_routing.py` (gated, `:98`/`:147`) | `--weight dust --via` visits the waypoint; `extra_ly`/`saved_av` compare against a **via-constrained** reference; `--weight distance --via` matches `compute_jump_route(..., via=…)` |
| `tests/test_route_find.py` (`:104`) | No change — added keys are additive |

Run: `venv/bin/python -m pytest` (with `QT_QPA_PLATFORM=offscreen` for the GUI tests).

---

## 9. Risks

- **Stage-1 cost, worst case.** 44 searches at k=8 over the ~256k pool, and the early exit fires
  **only on success** — an unreachable leg expands the whole reachable component. So the worst case
  is 44 full sweeps, which is also precisely the far-flung-waypoint scenario below. Measure before
  trusting the cap; the mitigation is the sweep-based closure (§1), not a smaller cap.
- **Phase 4 cost is worse than the plain path by roughly the per-edge dust integration.** Each new
  frontier edge triggers `_seg` → `dust.integrate_segment_av` (`core/dust_routing.py:56-60`,
  `:185`); `cost_cache` only helps on repeated pairs, and 44 searches expand largely disjoint
  frontiers.
- **A far-flung waypoint quietly makes everything unreachable.** Adding a waypoint can disconnect a
  route that worked without it. `unreachable_leg` is what makes that legible — required, not
  optional, and it must actually reach the GUI (§4).
- **Guard regression.** The `via=None` path must not drift, and no existing test would catch it
  (§2). Pin it explicitly.
- **Doc drift across phases.** Thirteen documentation sites (§4). The interim Phase 3 restriction
  note is the one most likely to be left stale — hence Checkpoint B / the optional final pass (§6).

---

## 10. Explicitly out of scope

- `--via-order fixed|optimal` (D2) — the stitching stage would support it; not built.
- Held–Karp ordering — brute force suffices, and the bottleneck is stage 1 anyway (§1).
- Node-disjoint (non-revisiting) routes — NP-hard, and not what the feature is for.
- Waypoint highlighting / de-duplicated labels on the star charts (§3 cosmetics).
- Waypoints on any other planner (`jump-network`, `farthest-first`, …).
- Any `.claude/settings.local.json` change.

---

## 11. Review record

Revised 2026-07-31 after three parallel reviewers (algorithmic verification, surface sweep,
contract/phasing critique) checked the first draft against the source. Material corrections folded
in:

1. **`via: []` always-present contradicted the "byte-identical" guard** — guard restated precisely (§2).
2. **The `dref` bug** — the forks' `extra_ly`/`saved_av` would compare a constrained route against an
   unconstrained one (§4).
3. **The exhaustive-sweep alternative was rejected on a false premise** — it needs no `_grid_search`
   change, and the early exit only fires on success (§1).
4. **The duplicate-waypoint check was on the wrong identity** — must be post-merge node indices (§7).
5. **`waypoint` made an always-present boolean**, flagged by route index, with the
   `count == len(via)` invariant (§3).
6. **`via_legs` / `unreachable_leg` promoted from optional to always-present** (§3).
7. **Missed surfaces added**: three further `docs/integration.md` sections, four
   `docs/calculators.md` sites, `docs/gui-architecture.md`, `docs/testing.md`, `CLAUDE.md:49`, the
   GUI unreachable branch, `tests/test_route_chart_tabs.py`, and the `IMPROVEMENT_PLAN.md` P2.6
   collision (§4).
8. **The `docs/integration.md` dated change-note convention** was missing entirely (§4, Phase 3).
9. **§4/§5 contradicted each other** on the Phase-3-without-Phase-4 interim; the error path is now
   specified with message, exit code and call site (§5).
10. **The cap was justified against the wrong bottleneck** (`k!` rather than search count) (§1, D6).
11. **Symmetry claim softened** — costs symmetric to within ULPs; reversed paths valid but not
    identical (§1).
12. **Revisit cosmetics on the charts** documented (§3), plus the new viz test gap (§8).

---

## 12. Checkpoint A record (Phase 1, 2026-07-31)

`/code-review` on the Phase 1 diff returned eight findings; all were addressed **inside Phase 1**
before Phase 2 was offered.

| Finding | Resolution |
|---|---|
| `via=None` behaviour change: endpoints colliding only *after* merge now error instead of returning a degenerate 1-node route | **Kept** (it is the correct answer) but now **documented** in `docs/calculators.md` §B and **pinned** by `test_endpoints_colliding_only_after_merge_now_error` |
| `docs/integration.md` stale — the four new keys ship in Phase 1, not Phase 3 | **Pulled forward**: quick-reference row, the `:2539` section, and the dated change note (incl. the revisit + unreachable-shape consumer hazards) written now; only the `--via` *flag* stays Phase 3 |
| Cross-`--weight` shape divergence (`dust`/`blend` lacked the keys) | **Pulled forward** from Phase 3: `_VIA_ECHO` + a literal `waypoint: False` on both fork route rows and `unreachable_leg` on all four fork returns; pinned by a non-gated test |
| `CLAUDE.md` + `docs/calculators.md` claimed the forks call `_route_through` | **Corrected** — they call `_grid_search` directly until Phase 4 |
| Unreachable branch named waypoints from resolved records, not merged nodes | **Fixed** — waypoints now reported from `nodes[via_idx[i]]`, matching the reachable branch (endpoints keep their pre-existing resolved-record form) |
| Stage 1 "does ~4× more search than sweeps would" | **Rejected on measurement** — sweeps are 46× *slower* here; see the §1 note. The reviewer's 4× estimate did not account for the early exit |
| `_normalize_via` accepted a `set`, breaking tie-break determinism | **Fixed** — ordered `list`/`tuple` only, with a test |

## 13. Checkpoint B record (Phases 3+4, 2026-07-31)

`/code-review` on the merged Phase 3+4 diff returned four findings; all addressed in-phase.

| Finding | Resolution |
|---|---|
| `docs/calculators.md` §B still said the forks don't call `_route_through` / don't take `via` — false after Phase 4, and contradicted three other docs | **Fixed** — §B now states the helper is shared by all three planners |
| One unreachable terminal cost k+1 **full** component sweeps (the early exit fires only on success), and stranding a route with a far-flung waypoint is a *documented, expected* outcome | **Fixed** — stage 1 **short-circuits on the first infinite pair**: reachability is an equivalence relation, so one disconnected terminal makes every order infeasible. Pairs are origin-first, so it is caught on the first search. Measured: a stranded Vega at `max_jump 4.5` over the 256k pool now returns in ~8 s. Stage 2's infinite-cost handling and the "every permutation infinite" block became dead code and were removed; pinned by `test_one_stranded_waypoint_short_circuits_the_closure` (asserts exactly one `_grid_search` call) |
| The `dref` comparison re-entered `calc.compute_jump_route` with raw **names** — re-resolving up to 10 terminals (some over the network) and re-running the whole closure on a fresh pool/grid | **Fixed** — new `_distance_reference` runs the min-ly route over the fork's **own** `nodes`/`grid` and the same `via_idx`. Same graph and terminals ⇒ same route; real-data numbers unchanged (`dref_ly` 54.82, `extra_ly` 2.236 before and after) |
| `via` meant "chosen order" when reachable but "typed order" when not, while the docs said "chosen" unconditionally | **Documented** rather than changed — the requested order is the useful echo when no order was chosen (`via_legs` is `[]` there). Both docs updated; pinned by `test_unreachable_via_is_the_requested_order_not_a_chosen_one` |
