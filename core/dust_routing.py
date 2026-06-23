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


def _total_av_along(seq, map_sel, step_pc):
    """Total integrated A_V along an ordered node sequence (for the distance-
    optimal comparison). Returns (total_av, all_covered) or (None, None) on error."""
    total = 0.0
    covered = True
    for i in range(len(seq) - 1):
        s = _seg(seq[i], seq[i + 1], map_sel, step_pc)
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


def _compare(our_total_ly, our_total_av, dist_seq, map_sel, step_pc, dist_total_ly):
    """Build the distance-optimal comparison block from the distance route's node
    sequence (its dust column integrated). dist_total_ly is the distance route's
    own geometric length."""
    d_av, _cov = _total_av_along(dist_seq, map_sel, step_pc)
    if d_av is None:
        d_av = our_total_av
    return {
        "distance_optimal_ly": dist_total_ly,
        "distance_optimal_av": d_av,
        "extra_ly": our_total_ly - dist_total_ly,
        "saved_av": d_av - our_total_av,
    }


# ── B (flagship): jump-route --weight dust ───────────────────────────────────

def compute_jump_route_dust(origin, destination, max_jump_ly, optimize="distance",
                            map_sel="auto", dust_step_pc=5.0):
    """Least-extinction route origin→destination over the same jump-limited graph
    as `compute_jump_route`. `optimize="distance"` → Dijkstra over A_V (least
    total extinction); `optimize="jumps"` → BFS (fewest jumps, dust reported)."""
    pf = _preflight(map_sel)
    if pf:
        return pf
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "Max jump distance must be positive."}
    if optimize not in ("distance", "jumps"):
        return {"error": "optimize must be 'distance' or 'jumps'."}

    o = _resolve_star_position(origin)
    if "error" in o:
        return {"error": f"Origin: {o['error']}"}
    d = _resolve_star_position(destination)
    if "error" in d:
        return {"error": f"Destination: {d['error']}"}
    if o["name"].strip().lower() == d["name"].strip().lower() or _node_dist(o, d) <= 1e-3:
        return {"error": "Origin and destination are the same star."}

    pool_res = _load_star_systems_positions()
    nodes = list(pool_res["stars"]) if "stars" in pool_res else []
    s = _merge_endpoint(nodes, o)
    t = _merge_endpoint(nodes, d)
    grid = _SpatialGrid(nodes, max_jump_ly)

    cost_cache, errors = {}, []

    def dust_cost(u, v, w):
        key = (u, v) if u < v else (v, u)
        if key in cost_cache:
            return cost_cache[key]
        seg = _seg(nodes[u], nodes[v], map_sel, dust_step_pc)
        val = float("inf") if "error" in seg else seg["a_v"]
        if "error" in seg:
            errors.append(seg["error"])
        cost_cache[key] = val
        return val

    prev, dist_arr = _grid_search(nodes, grid, s, t, max_jump_ly, optimize, dust_cost)
    if errors:
        return {"error": errors[0]}

    direct_ly = _node_dist(o, d)
    reachable = dist_arr[t] != float("inf")
    if not reachable:
        return {
            "origin_info": o, "dest_info": d, "reachable": False, "weight": "dust",
            "optimize": optimize, "jumps": 0, "total_ly": 0.0, "total_av": 0.0,
            "direct_ly": direct_ly, "route": [], "max_jump_ly": max_jump_ly,
            "map": map_sel, "stars": [_map_node(o), _map_node(d)],
        }

    path = []
    cur = t
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    seq = [nodes[i] for i in path]

    route = []
    cum_ly = cum_av = cum_var = 0.0
    all_cov = True
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg(a, b, map_sel, dust_step_pc)
        cum_ly += ly
        cum_av += seg["a_v"]
        cum_var += max(0.0, seg["a_v_hi"] - seg["a_v"]) ** 2
        all_cov = all_cov and seg["covered"]
        route.append({
            "jump": i + 1, "from": a["name"], "to": b["name"], "jump_ly": ly,
            "a_v": seg["a_v"], "a_v_lo": seg["a_v_lo"], "a_v_hi": seg["a_v_hi"],
            "fully_covered": seg["covered"], "weight_value": seg["a_v"],
            "cumulative_ly": cum_ly, "cumulative_av": cum_av,
        })

    # Distance-optimal comparison: the min-ly route over the same graph.
    dref = calc.compute_jump_route(origin, destination, max_jump_ly, "distance")
    if "error" not in dref and dref.get("reachable"):
        cmp = _compare(cum_ly, cum_av, _nodes_from_stars(dref["stars"]),
                       map_sel, dust_step_pc, dref["total_ly"])
    else:
        cmp = {"distance_optimal_ly": None, "distance_optimal_av": None,
               "extra_ly": None, "saved_av": None}

    sig = math.sqrt(cum_var)
    return {
        "origin_info": o, "dest_info": d, "reachable": True, "weight": "dust",
        "optimize": optimize, "jumps": len(path) - 1, "total_ly": cum_ly,
        "total_av": cum_av, "total_av_lo": max(0.0, cum_av - sig),
        "total_av_hi": cum_av + sig, "all_legs_covered": all_cov,
        "direct_ly": direct_ly, "route": route, "max_jump_ly": max_jump_ly,
        "map": map_sel, "stars": [_map_node(n) for n in seq], **cmp,
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
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        ly = _node_dist(a, b)
        seg = _seg(a, b, map_sel, dust_step_pc)
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

    # A_V cost matrix (symmetric).
    av = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            seg = _seg(nodes[i], nodes[j], map_sel, dust_step_pc)
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

    # 2-opt (start fixed at index 0).
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                if tour_av(cand) + 1e-12 < tour_av(order):
                    order = cand
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
        seg = _seg(a, b, map_sel, dust_step_pc)
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
                       map_sel, dust_step_pc, dref["optimized_total_ly"])
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
    for hop in range(1, num_hops + 1):
        best = None  # (a_v, idx, ly, seg)
        for v, w in grid.neighbors(cur, max_ly):
            if v in visited:
                continue
            seg = _seg(nodes[cur], nodes[v], map_sel, dust_step_pc)
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
                       map_sel, dust_step_pc, dref["total_ly"])
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

    candidates = []  # (a_v, i, j, ly, seg)
    for i in range(n):
        for j in range(i + 1, n):
            seg = _seg(nodes[i], nodes[j], map_sel, dust_step_pc)
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
                d_av += _seg(a, b, map_sel, dust_step_pc)["a_v"]
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
