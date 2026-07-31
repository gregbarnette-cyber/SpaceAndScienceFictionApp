"""Dust-weighted route planning (Phase T2 Part B).

The five Core route planners re-cast with **integrated dust extinction A_V** as
the edge weight instead of 3D distance — least-extinction corridors that thread
low-dust paths around clouds and the Local Bubble wall. Forked (per the locked
T2 architecture decision) rather than threaded into `core/calculators.py`, so the
optional `dustmaps`/`healpy` import stays out of the stellar layer.

Each function is the `--weight dust` half of its `query.py` planner; `--weight
distance` (the default) is served by the unchanged `core/calculators.py` sibling.
This module REUSES the verified non-weight helpers from `core/calculators.py`
(`_resolve_star_position`, `_load_star_systems_positions`, `_SpatialGrid`,
`_merge_endpoint`, `_map_node`, `_node_dist`, `_grid_search`, `_UnionFind`,
`HOURS_PER_JULIAN_YEAR`, `format_travel_time`) and the per-leg A_V cost primitive
`core.dust.integrate_segment_av`.

Key invariants (request §B.2/§B.4):
  - A_V is a non-negative additive edge weight → Dijkstra/MST-correct.
  - Reachability stays GEOMETRIC: `--max-jump` / `--max-ly` govern which edges
    exist (dust-independent); dust only weights edges that already exist.
  - Every result carries a distance-optimal comparison (`distance_optimal_ly`,
    `distance_optimal_av`, `extra_ly`, `saved_av`) — run the distance planner over
    the same graph and integrate dust along ITS route (request §B.7).
"""

import math

import core.calculators as calc
import core.dust as dust
from core.calculators import (
    _resolve_star_position, _load_star_systems_positions, _map_node, _node_dist,
    _merge_endpoint, _SpatialGrid, _grid_search, _UnionFind,
    _normalize_via, _resolve_via, _check_terminal_indices, _route_through,
    HOURS_PER_JULIAN_YEAR, format_travel_time,
)


# ── shared plumbing ──────────────────────────────────────────────────────────

def _preflight(map_sel):
    """Validate the map selector + ensure the dust extra and map data are
    available (preloaded once, so failures surface as a single clean error).
    Returns None on success or an {"error": str} dict."""
    if map_sel not in ("near-field", "edenhofer", "auto"):
        return {"error": "map must be 'near-field', 'edenhofer', or 'auto'."}
    if not dust._dustmaps_available():
        return {"error": dust._DUST_EXTRA_MSG}
    keys = (["leike2020", "edenhofer2023"] if map_sel == "auto"
            else [dust._MAP_KEY[map_sel]])
    for mk in keys:
        _q, err = dust._load_map(mk)
        if err:
            return err
    return None


def _seg(a, b, map_sel, step_pc):
    """Integrated A_V between two node dicts (x/y/z in light-years)."""
    p1 = (a["x"] / dust._LY_PER_PC, a["y"] / dust._LY_PER_PC, a["z"] / dust._LY_PER_PC)
    p2 = (b["x"] / dust._LY_PER_PC, b["y"] / dust._LY_PER_PC, b["z"] / dust._LY_PER_PC)
    return dust.integrate_segment_av(p1, p2, step_pc=step_pc, map_sel=map_sel)


def _seg_cached(a, b, map_sel, step_pc, memo):
    """Memoizing wrapper over `_seg` for a single planner invocation (P2.6).

    Keyed on the unordered name pair — A_V is symmetric and stars are uniquely
    named within one route, so this matches the pairs the Dijkstra cost caches and
    the O(n²) A_V matrices already integrate. A miss simply recomputes via `_seg`
    (identical value), so this only removes redundant re-integration of edges — it
    can never change a result. `_seg`'s own signature is untouched (the tests patch
    `_seg` directly and mock it deterministically per pair)."""
    key = frozenset((a["name"], b["name"]))
    seg = memo.get(key)
    if seg is None:
        seg = _seg(a, b, map_sel, step_pc)
        memo[key] = seg
    return seg


def _total_av_along(seq, map_sel, step_pc, memo=None):
    """Total integrated A_V along an ordered node sequence (for the distance-
    optimal comparison). Returns (total_av, all_covered) or (None, None) on error.
    When `memo` is supplied, edges already integrated by the caller are reused."""
    total = 0.0
    covered = True
    for i in range(len(seq) - 1):
        s = (_seg_cached(seq[i], seq[i + 1], map_sel, step_pc, memo)
             if memo is not None else _seg(seq[i], seq[i + 1], map_sel, step_pc))
        if "error" in s:
            return None, None
        total += s["a_v"]
        covered = covered and s["covered"]
    return total, covered


def _nodes_from_stars(star_dicts):
    """Map a planner result's `stars` list (map dicts with x/y/z) to the minimal
    node shape `_seg` needs — for integrating dust along a distance route."""
    return [{"name": s["name"], "x": s["x"], "y": s["y"], "z": s["z"]}
            for s in star_dicts]


def _vel(velocity_input, use_times_c):
    if use_times_c:
        return velocity_input / HOURS_PER_JULIAN_YEAR, velocity_input
    return velocity_input, velocity_input * HOURS_PER_JULIAN_YEAR


def _resolve_named(star_names, dedup):
    """Resolve a name list to node records (DB→SIMBAD). Returns (nodes, None) or
    (None, {"error"}). `dedup` collapses case-insensitive duplicates (tour/MST)."""
    if dedup:
        seen, names = set(), []
        for nm in (star_names or []):
            k = (nm or "").strip().lower()
            if k and k not in seen:
                seen.add(k)
                names.append(nm)
    else:
        names = list(star_names or [])
    if len(names) < 2:
        return None, {"error": "Enter at least two systems."}
    nodes = []
    for nm in names:
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return None, {"error": f"'{nm}': {rec['error']}"}
        nodes.append(rec)
    return nodes, None


def _compare(our_total_ly, our_total_av, dist_seq, map_sel, step_pc, dist_total_ly,
             memo=None):
    """Build the distance-optimal comparison block from the distance route's node
    sequence (its dust column integrated). dist_total_ly is the distance route's
    own geometric length. `memo` (P2.6) lets edges shared with our route reuse the
    integrals already computed."""
    d_av, _cov = _total_av_along(dist_seq, map_sel, step_pc, memo=memo)
    if d_av is None:
        d_av = our_total_av
    return {
        "distance_optimal_ly": dist_total_ly,
        "distance_optimal_av": d_av,
        "extra_ly": our_total_ly - dist_total_ly,
        "saved_av": d_av - our_total_av,
    }


# ── B (flagship): jump-route --weight dust ───────────────────────────────────

def _jump_setup(origin, destination, max_jump_ly, optimize, via):
    """Shared validate → resolve → pool → merge → grid front half of both jump
    forks, mirroring `compute_jump_route`'s (same order, same messages, same
    post-merge terminal check). Returns (ctx, None) or (None, {"error"})."""
    if max_jump_ly is None or max_jump_ly <= 0:
        return None, {"error": "Max jump distance must be positive."}
    if optimize not in ("distance", "jumps"):
        return None, {"error": "optimize must be 'distance' or 'jumps'."}
    via_names, err = _normalize_via(via)
    if err:
        return None, err

    o = _resolve_star_position(origin)
    if "error" in o:
        return None, {"error": f"Origin: {o['error']}"}
    d = _resolve_star_position(destination)
    if "error" in d:
        return None, {"error": f"Destination: {d['error']}"}
    if o["name"].strip().lower() == d["name"].strip().lower() or _node_dist(o, d) <= 1e-3:
        return None, {"error": "Origin and destination are the same star."}
    via_recs, err = _resolve_via(via_names)
    if err:
        return None, err

    pool_res = _load_star_systems_positions()
    nodes = list(pool_res["stars"]) if "stars" in pool_res else []
    # All terminals merged BEFORE the grid is built (it indexes at construction).
    s = _merge_endpoint(nodes, o)
    t = _merge_endpoint(nodes, d)
    via_idx = [_merge_endpoint(nodes, w) for w in via_recs]
    err = _check_terminal_indices(s, t, via_idx, via_names)
    if err:
        return None, err
    return {"o": o, "d": d, "nodes": nodes, "s": s, "t": t, "via_idx": via_idx,
            "grid": _SpatialGrid(nodes, max_jump_ly)}, None


def _via_block(nodes, path, seams, route, via_idx):
    """The `via` / `via_legs` half of a fork's result (A_V-aware `via_legs`)."""
    legs = []
    for i in range(len(seams) - 1):
        p0, p1 = seams[i], seams[i + 1]
        legs.append({
            "from": nodes[path[p0]]["name"], "to": nodes[path[p1]]["name"],
            "jumps": p1 - p0,
            "ly": sum(r["jump_ly"] for r in route[p0:p1]),
            "a_v": sum(r["a_v"] for r in route[p0:p1]),
        })
    return {"via": [nodes[path[p]]["name"] for p in seams[1:-1]],
            "via_legs": legs if via_idx else []}


def _distance_reference(ctx, max_jump_ly, our_ly, our_av, map_sel, step_pc, memo):
    """The distance-optimal comparison block for a jump fork.

    Runs the min-ly route over the fork's OWN `nodes`/`grid` under the SAME
    waypoint constraint, rather than re-entering `calc.compute_jump_route` with
    the raw names. Two reasons: (1) correctness — `extra_ly`/`saved_av` must
    compare like with like, so the reference has to be waypoint-constrained too;
    (2) cost — re-entering would re-resolve every terminal (up to 10 DB/SIMBAD
    lookups, some of them network) and re-run the whole stage-1 closure on a
    freshly built pool and grid, on top of the dust-weighted closure just done.
    Same graph, same terminals ⇒ the same route, for a fraction of the work.
    """
    path, _seams, unreachable = _route_through(
        ctx["nodes"], ctx["grid"], ctx["s"], ctx["t"], ctx["via_idx"],
        max_jump_ly, "distance", lambda u, v, w: w)
    if unreachable is not None:
        return {"distance_optimal_ly": None, "distance_optimal_av": None,
                "extra_ly": None, "saved_av": None}
    seq = [ctx["nodes"][i] for i in path]
    d_ly = sum(_node_dist(seq[i], seq[i + 1]) for i in range(len(seq) - 1))
    return _compare(our_ly, our_av, seq, map_sel, step_pc, d_ly, memo=memo)


def compute_jump_route_dust(origin, destination, max_jump_ly, optimize="distance",
                            map_sel="auto", dust_step_pc=5.0, via=None):
    """Least-extinction route origin→destination over the same jump-limited graph
    as `compute_jump_route`. `optimize="distance"` → Dijkstra over A_V (least
    total extinction); `optimize="jumps"` → BFS (fewest jumps, dust reported).

    `via` (required intermediate waypoints) behaves exactly as on
    `compute_jump_route` — same helper, same validation, ordered by least A_V
    here rather than least distance."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    ctx, err = _jump_setup(origin, destination, max_jump_ly, optimize, via)
    if err:
        return err
    o, d, nodes = ctx["o"], ctx["d"], ctx["nodes"]
    s, t, via_idx, grid = ctx["s"], ctx["t"], ctx["via_idx"], ctx["grid"]

    cost_cache, errors, seg_memo = {}, [], {}

    def dust_cost(u, v, w):
        key = (u, v) if u < v else (v, u)
        if key in cost_cache:
            return cost_cache[key]
        seg = _seg(nodes[u], nodes[v], map_sel, dust_step_pc)
        seg_memo[frozenset((nodes[u]["name"], nodes[v]["name"]))] = seg  # P2.6 reuse
        val = float("inf") if "error" in seg else seg["a_v"]
        if "error" in seg:
            errors.append(seg["error"])
        cost_cache[key] = val
        return val

    path, seams, unreachable_leg = _route_through(
        nodes, grid, s, t, via_idx, max_jump_ly, optimize, dust_cost)
    if errors:
        return {"error": errors[0]}

    direct_ly = _node_dist(o, d)
    if unreachable_leg is not None:
        return {
            "origin_info": o, "dest_info": d, "reachable": False, "weight": "dust",
            "optimize": optimize, "jumps": 0, "total_ly": 0.0, "total_av": 0.0,
            "direct_ly": direct_ly, "route": [], "max_jump_ly": max_jump_ly,
            "map": map_sel,
            "stars": ([_map_node(o)] + [_map_node(nodes[i]) for i in via_idx]
                      + [_map_node(d)]),
            "via": [nodes[i]["name"] for i in via_idx], "via_legs": [],
            "unreachable_leg": unreachable_leg,
        }

    seq = [nodes[i] for i in path]
    waypoint_at = set(seams[1:-1])

    route = []
    cum_ly = cum_av = cum_var = 0.0
    all_cov = True
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg_cached(a, b, map_sel, dust_step_pc, seg_memo)  # P2.6: reuse Dijkstra integrals
        cum_ly += ly
        cum_av += seg["a_v"]
        cum_var += max(0.0, seg["a_v_hi"] - seg["a_v"]) ** 2
        all_cov = all_cov and seg["covered"]
        route.append({
            "jump": i + 1, "from": a["name"], "to": b["name"], "jump_ly": ly,
            "a_v": seg["a_v"], "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "weight_value": seg["a_v"],
            "cumulative_ly": cum_ly, "cumulative_av": cum_av,
            "waypoint": (i + 1) in waypoint_at,
        })

    cmp = _distance_reference(ctx, max_jump_ly, cum_ly, cum_av, map_sel,
                              dust_step_pc, seg_memo)

    sig = math.sqrt(cum_var)
    return {
        "origin_info": o, "dest_info": d, "reachable": True, "weight": "dust",
        "optimize": optimize, "jumps": len(path) - 1, "total_ly": cum_ly,
        "total_av": cum_av, "total_av_lo": max(0.0, cum_av - sig),
        "total_av_hi": cum_av + sig, "all_legs_covered": all_cov,
        "direct_ly": direct_ly, "route": route, "max_jump_ly": max_jump_ly,
        "map": map_sel, "stars": [_map_node(n) for n in seq], **cmp,
        **_via_block(nodes, path, seams, route, via_idx), "unreachable_leg": None,
    }


# ── C11 (Phase AD): jump-route --weight blend (α·distance + β·A_V) ────────────

def compute_jump_route_blend(origin, destination, max_jump_ly, optimize="distance",
                             alpha=1.0, beta=1.0, map_sel="auto", dust_step_pc=5.0,
                             via=None):
    """Blended-cost route origin→destination: each edge costs ``α·distance_ly + β·A_V``,
    fed to the same Dijkstra (`_grid_search`) as `compute_jump_route`/`_dust`.

    ``β=0`` reproduces the distance-optimal route; ``α=0`` reproduces the least-dust
    (`--weight dust`) route; an intermediate blend is a compromise between the two.
    Reachability stays geometric (``max_jump_ly`` unchanged). Mirrors the dust variant's
    output plus the echoed ``alpha``/``beta``/``total_blend_cost``.
    """
    pf = _preflight(map_sel)
    if pf:
        return pf
    # Kept ahead of the α/β checks so the message precedence is unchanged
    # (`_jump_setup` re-checks both, harmlessly).
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "Max jump distance must be positive."}
    if optimize not in ("distance", "jumps"):
        return {"error": "optimize must be 'distance' or 'jumps'."}
    if alpha is None or beta is None or alpha < 0 or beta < 0:
        return {"error": "alpha and beta must be ≥ 0."}
    if alpha == 0 and beta == 0:
        return {"error": "alpha and beta cannot both be 0 (a zero cost has no optimum)."}
    ctx, err = _jump_setup(origin, destination, max_jump_ly, optimize, via)
    if err:
        return err
    o, d, nodes = ctx["o"], ctx["d"], ctx["nodes"]
    s, t, via_idx, grid = ctx["s"], ctx["t"], ctx["via_idx"], ctx["grid"]

    cost_cache, errors, seg_memo = {}, [], {}

    def blend_cost(u, v, w):
        key = (u, v) if u < v else (v, u)
        if key in cost_cache:
            return cost_cache[key]
        seg = _seg(nodes[u], nodes[v], map_sel, dust_step_pc)
        seg_memo[frozenset((nodes[u]["name"], nodes[v]["name"]))] = seg  # P2.6 reuse
        if "error" in seg:
            errors.append(seg["error"])
            val = float("inf")
        else:
            val = alpha * w + beta * seg["a_v"]
        cost_cache[key] = val
        return val

    path, seams, unreachable_leg = _route_through(
        nodes, grid, s, t, via_idx, max_jump_ly, optimize, blend_cost)
    if errors:
        return {"error": errors[0]}

    direct_ly = _node_dist(o, d)
    if unreachable_leg is not None:
        return {
            "origin_info": o, "dest_info": d, "reachable": False, "weight": "blend",
            "alpha": alpha, "beta": beta, "optimize": optimize, "jumps": 0,
            "total_ly": 0.0, "total_av": 0.0, "total_blend_cost": 0.0,
            "direct_ly": direct_ly, "route": [], "max_jump_ly": max_jump_ly,
            "map": map_sel,
            "stars": ([_map_node(o)] + [_map_node(nodes[i]) for i in via_idx]
                      + [_map_node(d)]),
            "via": [nodes[i]["name"] for i in via_idx], "via_legs": [],
            "unreachable_leg": unreachable_leg,
        }

    seq = [nodes[i] for i in path]
    waypoint_at = set(seams[1:-1])

    route = []
    cum_ly = cum_av = cum_cost = cum_var = 0.0
    all_cov = True
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg_cached(a, b, map_sel, dust_step_pc, seg_memo)  # P2.6: reuse Dijkstra integrals
        cum_ly += ly
        cum_av += seg["a_v"]
        cum_cost += alpha * ly + beta * seg["a_v"]
        cum_var += max(0.0, seg["a_v_hi"] - seg["a_v"]) ** 2
        all_cov = all_cov and seg["covered"]
        route.append({
            "jump": i + 1, "from": a["name"], "to": b["name"], "jump_ly": ly,
            "a_v": seg["a_v"], "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "weight_value": alpha * ly + beta * seg["a_v"],
            "cumulative_ly": cum_ly, "cumulative_av": cum_av,
            "waypoint": (i + 1) in waypoint_at,
        })

    cmp = _distance_reference(ctx, max_jump_ly, cum_ly, cum_av, map_sel,
                              dust_step_pc, seg_memo)

    sig = math.sqrt(cum_var)
    return {
        "origin_info": o, "dest_info": d, "reachable": True, "weight": "blend",
        "alpha": alpha, "beta": beta, "optimize": optimize, "jumps": len(path) - 1,
        "total_ly": cum_ly, "total_av": cum_av, "total_blend_cost": cum_cost,
        "total_av_lo": max(0.0, cum_av - sig), "total_av_hi": cum_av + sig,
        "all_legs_covered": all_cov, "direct_ly": direct_ly, "route": route,
        "max_jump_ly": max_jump_ly, "map": map_sel,
        "stars": [_map_node(n) for n in seq], **cmp,
        **_via_block(nodes, path, seams, route, via_idx), "unreachable_leg": None,
    }


# ── multi-stop --weight dust (ordered, no route choice) ──────────────────────

def compute_multi_stop_dust(star_names, velocity_input, use_times_c,
                            map_sel="auto", dust_step_pc=5.0):
    """Cumulative dust + travel time along a FIXED ordered list of stops. The
    order is the user's, so the distance-optimal comparison is degenerate (same
    route → extra_ly/saved_av = 0)."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    if not star_names or len(star_names) < 2:
        return {"error": "Enter at least two stops."}
    if velocity_input is None or velocity_input <= 0:
        return {"error": "Velocity must be positive."}
    ly_hr, times_c = _vel(velocity_input, use_times_c)

    seq = []
    for i, nm in enumerate(star_names):
        rec = _resolve_star_position(nm)
        if "error" in rec:
            return {"error": f"Stop {i + 1} ('{nm}'): {rec['error']}"}
        seq.append(rec)

    legs = []
    cum_ly = cum_av = cum_var = cum_hours = 0.0
    all_cov = True
    seg_memo = {}
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg_cached(a, b, map_sel, dust_step_pc, seg_memo)
        hours = ly / ly_hr
        cum_ly += ly
        cum_av += seg["a_v"]
        cum_var += max(0.0, seg["a_v_hi"] - seg["a_v"]) ** 2
        cum_hours += hours
        all_cov = all_cov and seg["covered"]
        legs.append({
            "leg": i + 1, "origin": a["name"], "dest": b["name"],
            "distance_ly": ly, "ly_hr": ly_hr, "times_c": times_c, "hours": hours,
            "a_v": seg["a_v"], "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "weight_value": seg["a_v"],
            "cumulative_ly": cum_ly, "cumulative_av": cum_av,
            "cumulative_hours": cum_hours, "travel_time": format_travel_time(hours),
            "cumulative_time": format_travel_time(cum_hours),
        })

    sig = math.sqrt(cum_var)
    return {
        "weight": "dust", "map": map_sel, "legs": legs, "total_ly": cum_ly,
        "total_av": cum_av, "total_av_lo": max(0.0, cum_av - sig),
        "total_av_hi": cum_av + sig, "all_legs_covered": all_cov,
        "total_hours": cum_hours, "total_time": format_travel_time(cum_hours),
        "distance_optimal_ly": cum_ly, "distance_optimal_av": cum_av,
        "extra_ly": 0.0, "saved_av": 0.0,
        "stars": [_map_node(n) for n in seq],
    }


# ── optimal-tour --weight dust (NN seed + 2-opt over an A_V cost matrix) ──────

def compute_optimal_tour_dust(star_names, velocity_input, use_times_c, closed=False,
                              map_sel="auto", dust_step_pc=5.0):
    """Visit a set of stars in the least-total-extinction order (NN seed from the
    fixed first stop, then 2-opt over the A_V cost matrix; 2-opt is metric-agnostic)."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    if velocity_input is None or velocity_input <= 0:
        return {"error": "Velocity must be positive."}
    nodes, err = _resolve_named(star_names, dedup=True)
    if err:
        return err
    ly_hr, times_c = _vel(velocity_input, use_times_c)
    n = len(nodes)

    # A_V cost matrix (symmetric). seg_memo (P2.6) lets the leg-detail loop and the
    # distance-optimal comparison reuse these integrals instead of recomputing them.
    seg_memo = {}
    av = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            seg = _seg_cached(nodes[i], nodes[j], map_sel, dust_step_pc, seg_memo)
            av[i][j] = av[j][i] = seg["a_v"]

    def tour_av(order):
        c = sum(av[order[k]][order[k + 1]] for k in range(len(order) - 1))
        if closed and len(order) > 1:
            c += av[order[-1]][order[0]]
        return c

    # Nearest-neighbor seed from the fixed first node.
    unvisited = set(range(1, n))
    order = [0]
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: av[last][j])
        order.append(nxt)
        unvisited.discard(nxt)

    # 2-opt (start fixed at index 0). P2.7: hoist the current-tour cost out of the
    # O(n²) (i,k) loop, recomputing only on an accepted swap — behavior-identical
    # (cur_av always equals tour_av(order), same acceptance/tie-breaking).
    cur_av = tour_av(order)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                cand_av = tour_av(cand)
                if cand_av + 1e-12 < cur_av:
                    order = cand
                    cur_av = cand_av
                    improved = True

    seq = [nodes[i] for i in order]
    if closed:
        seq = seq + [nodes[order[0]]]

    legs = []
    cum_ly = cum_av = cum_var = cum_hours = 0.0
    all_cov = True
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg_cached(a, b, map_sel, dust_step_pc, seg_memo)  # P2.6: reuse matrix integrals
        hours = ly / ly_hr
        cum_ly += ly
        cum_av += seg["a_v"]
        cum_var += max(0.0, seg["a_v_hi"] - seg["a_v"]) ** 2
        cum_hours += hours
        all_cov = all_cov and seg["covered"]
        legs.append({
            "leg": i + 1, "origin": a["name"], "dest": b["name"],
            "distance_ly": ly, "ly_hr": ly_hr, "times_c": times_c, "hours": hours,
            "a_v": seg["a_v"], "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "weight_value": seg["a_v"],
            "cumulative_ly": cum_ly, "cumulative_av": cum_av,
            "cumulative_hours": cum_hours, "travel_time": format_travel_time(hours),
            "cumulative_time": format_travel_time(cum_hours),
        })

    dref = calc.compute_optimal_tour(star_names, velocity_input, use_times_c, closed=closed)
    if "error" not in dref:
        cmp = _compare(cum_ly, cum_av, _nodes_from_stars(dref["stars"]),
                       map_sel, dust_step_pc, dref["optimized_total_ly"], memo=seg_memo)
    else:
        cmp = {"distance_optimal_ly": None, "distance_optimal_av": None,
               "extra_ly": None, "saved_av": None}

    sig = math.sqrt(cum_var)
    return {
        "weight": "dust", "map": map_sel, "closed": closed, "legs": legs,
        "total_ly": cum_ly, "total_av": cum_av, "total_av_lo": max(0.0, cum_av - sig),
        "total_av_hi": cum_av + sig, "all_legs_covered": all_cov,
        "total_hours": cum_hours, "total_time": format_travel_time(cum_hours),
        "stars": [_map_node(n) for n in seq], **cmp,
    }


# ── nearest-neighbor --weight dust (least-A_V unvisited within max_ly) ────────

def compute_nearest_neighbor_dust(start_star, num_hops, max_ly,
                                  map_sel="auto", dust_step_pc=5.0):
    """Greedy chain picking the least-extinction unvisited star still within
    `max_ly` (geometric reachability) of the current star."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    try:
        num_hops = int(num_hops)
    except (TypeError, ValueError):
        return {"error": "Number of hops must be a positive integer."}
    if num_hops < 1:
        return {"error": "Number of hops must be a positive integer."}
    if max_ly is None or max_ly <= 0:
        return {"error": "Max hop distance must be positive."}

    start = _resolve_star_position(start_star)
    if "error" in start:
        return start
    pool_res = _load_star_systems_positions()
    if "error" in pool_res:
        return pool_res
    nodes = list(pool_res["stars"])
    s = _merge_endpoint(nodes, start)
    grid = _SpatialGrid(nodes, max_ly)

    visited = {s}
    cur = s
    cum_ly = cum_av = 0.0
    chain, chain_nodes = [], [nodes[s]]
    stopped_early = False
    seg_memo = {}
    for hop in range(1, num_hops + 1):
        best = None  # (a_v, idx, ly, seg)
        for v, w in grid.neighbors(cur, max_ly):
            if v in visited:
                continue
            seg = _seg_cached(nodes[cur], nodes[v], map_sel, dust_step_pc, seg_memo)
            if best is None or seg["a_v"] < best[0]:
                best = (seg["a_v"], v, w, seg)
        if best is None:
            stopped_early = True
            break
        a_v, idx, ly, seg = best
        visited.add(idx)
        cum_ly += ly
        cum_av += a_v
        cand = nodes[idx]
        chain.append({
            "hop": hop, "star_name": cand["name"], "desig": cand.get("desig", ""),
            "sp_type": cand.get("sp_type", ""), "dist_from_prev_ly": ly,
            "a_v_from_prev": a_v, "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "cumulative_ly": cum_ly,
            "cumulative_av": cum_av, "ly_from_sol": cand.get("ly", 0.0),
        })
        chain_nodes.append(cand)
        cur = idx

    stars = [_map_node(nodes[s])]
    stars[0]["color"] = "#FFD700"
    for c in chain_nodes[1:]:
        stars.append(_map_node(c))

    dref = calc.compute_nearest_neighbor_chain(start_star, num_hops, max_ly)
    if "error" not in dref:
        cmp = _compare(cum_ly, cum_av, _nodes_from_stars(dref["stars"]),
                       map_sel, dust_step_pc, dref["total_ly"], memo=seg_memo)
    else:
        cmp = {"distance_optimal_ly": None, "distance_optimal_av": None,
               "extra_ly": None, "saved_av": None}

    return {
        "weight": "dust", "map": map_sel, "chain": chain, "stars": stars,
        "total_ly": cum_ly, "total_av": cum_av, "stopped_early": stopped_early,
        "start_name": start["name"], **cmp,
    }


# ── trade-route --weight dust (MST over A_V edges) ───────────────────────────

def compute_trade_route_dust(star_names, map_sel="auto", dust_step_pc=5.0):
    """Minimum spanning tree connecting a set of systems with A_V (least total
    extinction) edge weights (Kruskal)."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    nodes, err = _resolve_named(star_names, dedup=True)
    if err:
        return err
    n = len(nodes)

    seg_memo = {}  # P2.6: reused by the distance-optimal MST comparison below
    candidates = []  # (a_v, i, j, ly, seg)
    for i in range(n):
        for j in range(i + 1, n):
            seg = _seg_cached(nodes[i], nodes[j], map_sel, dust_step_pc, seg_memo)
            candidates.append((seg["a_v"], i, j, _node_dist(nodes[i], nodes[j]), seg))
    candidates.sort(key=lambda e: e[0])

    uf = _UnionFind(n)
    edges, total_av, total_ly = [], 0.0, 0.0
    all_cov = True
    for a_v, i, j, ly, seg in candidates:
        if uf.union(i, j):
            edges.append({"from": nodes[i]["name"], "to": nodes[j]["name"],
                          "distance_ly": ly, "a_v": a_v, "a_v_lo": seg["a_v_lo"],
                          "a_v_hi": seg["a_v_hi"], "fully_covered": seg["covered"]})
            total_av += a_v
            total_ly += ly
            all_cov = all_cov and seg["covered"]
            if len(edges) == n - 1:
                break

    # Distance-optimal comparison: the min-ly MST's dust column.
    dref = calc.compute_trade_route_mst(star_names)
    if "error" not in dref:
        name_to_node = {nd["name"]: nd for nd in nodes}
        d_av = 0.0
        for e in dref["edges"]:
            a = name_to_node.get(e["from"])
            b = name_to_node.get(e["to"])
            if a and b:
                d_av += _seg_cached(a, b, map_sel, dust_step_pc, seg_memo)["a_v"]
        cmp = {"distance_optimal_ly": dref["total_ly"], "distance_optimal_av": d_av,
               "extra_ly": total_ly - dref["total_ly"], "saved_av": d_av - total_av}
    else:
        cmp = {"distance_optimal_ly": None, "distance_optimal_av": None,
               "extra_ly": None, "saved_av": None}

    return {
        "weight": "dust", "map": map_sel,
        "nodes": [{"name": nd["name"], "x": nd["x"], "y": nd["y"], "z": nd["z"],
                   "sp_type": nd.get("sp_type", ""), "desig": nd.get("desig", "")}
                  for nd in nodes],
        "edges": edges, "total_ly": total_ly, "total_av": total_av,
        "all_legs_covered": all_cov, "stars": [_map_node(nd) for nd in nodes], **cmp,
    }
