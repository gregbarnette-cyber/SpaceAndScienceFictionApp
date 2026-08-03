"""Phase AQ (Group T) — strategic-geography graph analytics (Packets 32 / 38).

Two pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculators that add an
**analytic layer** over the *same* jump graph the routing group already builds (nodes = stars in a
bounding volume / a supplied list / the whole catalog; edges = star pairs within ``--max-jump`` ly):

  * ``compute_network_centrality`` (T1) — degree + Freeman betweenness (route value / chokepoints),
    Hopcroft–Tarjan articulation points + bridges (true topological cut-vertices), optional
    Menger min-cut between two systems. The STL/lane-era chokepoint tool.
  * ``compute_arrival_corridors`` (T2) — the FTL-emergence / picket geometry: cluster the origin
    bearings into corridors and size the picket solid angle ("un-wallable, but the corridors are ε
    of the sky").

Textbook graph theory + spherical geometry only. Reads the catalog through the routing group's own
helpers in ``core.calculators`` (``_resolve_star_position`` / ``_load_star_systems_positions`` /
``_SpatialGrid`` / ``_node_dist`` / ``_merge_endpoint``) — no new dataset, same read path as
``jump-network``. The graph algorithms are **iterative** (explicit stacks) so they survive the
~256k-row ``star_systems`` table without blowing Python's recursion limit. No network/DB write, no
RNG, no wall-clock, no numpy.

Scale guard (T1): degree / articulation points / bridges / components are O(V+E) and run on any node
set; **betweenness and min-cut are O(V·E) / per-pair and are capped at ``_BETWEENNESS_CAP`` nodes** —
above it they return ``null`` with a ``model_note`` rather than hang (narrow ``--within-ly`` or pass
``--stars``).
"""

import heapq
import math

import core.calculators as calc

# Above this node count, betweenness + min-cut degrade to null (graceful, not an error).
_BETWEENNESS_CAP = 2000
_DEFAULT_TOP = 25            # default number of highest-centrality nodes reported


# ══════════════════════════════ PURE GRAPH CORE ══════════════════════════════
# All operate on `adj` = list (len n) of lists of (neighbor_index, weight). Undirected: every edge
# appears in both endpoints' lists. Directly unit-testable with no DB (the A–B–C–D chain anchor).

def _degrees(adj):
    return [len(a) for a in adj]


def _connected_components(n, adj):
    """→ (labels[n], n_components). Iterative BFS flood-fill."""
    labels = [-1] * n
    comp = 0
    for s in range(n):
        if labels[s] != -1:
            continue
        stack = [s]
        labels[s] = comp
        while stack:
            u = stack.pop()
            for v, _w in adj[u]:
                if labels[v] == -1:
                    labels[v] = comp
                    stack.append(v)
        comp += 1
    return labels, comp


def _articulation_and_bridges(n, adj):
    """Hopcroft–Tarjan articulation points + bridges, iterative (recursion-safe on 256k nodes).

    → (set of articulation-point indices, list of bridge (u,v) index pairs with u<v)."""
    disc = [-1] * n
    low = [0] * n
    parent = [-1] * n
    ap = set()
    bridges = []
    timer = [0]
    for start in range(n):
        if disc[start] != -1:
            continue
        # Explicit DFS stack of (node, iterator-index into adj[node], child-count).
        stack = [(start, 0, 0)]
        disc[start] = low[start] = timer[0]
        timer[0] += 1
        root_children = 0
        while stack:
            u, i, _children = stack[-1]
            if i < len(adj[u]):
                stack[-1] = (u, i + 1, _children)
                v = adj[u][i][0]
                if v == parent[u]:
                    continue
                if disc[v] == -1:
                    parent[v] = u
                    disc[v] = low[v] = timer[0]
                    timer[0] += 1
                    if u == start:
                        root_children += 1
                    stack.append((v, 0, 0))
                else:
                    if disc[v] < low[u]:
                        low[u] = disc[v]
                        stack[-1] = (u, i + 1, _children)
            else:
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    if low[u] < low[p]:
                        low[p] = low[u]
                    if parent[p] != -1 and low[u] >= disc[p]:
                        ap.add(p)
                    if low[u] > disc[p]:
                        bridges.append((min(p, u), max(p, u)))
        if root_children >= 2:
            ap.add(start)
    return ap, bridges


def _betweenness(n, adj):
    """Freeman betweenness (unnormalized, undirected), weighted Dijkstra-Brandes.

    Edge weights must be positive, so every predecessor on a shortest path has strictly smaller
    distance (finalized first) — which is what makes the lazy tie accumulation correct. For unit
    weights this reproduces the unweighted (BFS) betweenness. Undirected → the raw directed sum is
    halved."""
    cb = [0.0] * n
    for s in range(n):
        stack_order = []
        pred = [[] for _ in range(n)]
        sigma = [0.0] * n
        sigma[s] = 1.0
        dist = [math.inf] * n
        dist[s] = 0.0
        final = [False] * n
        pq = [(0.0, s)]
        while pq:
            d, v = heapq.heappop(pq)
            if final[v]:
                continue
            final[v] = True
            stack_order.append(v)
            for w, wt in adj[v]:
                nd = d + wt
                if nd < dist[w] - 1e-12:
                    dist[w] = nd
                    sigma[w] = sigma[v]
                    pred[w] = [v]
                    heapq.heappush(pq, (nd, w))
                elif abs(nd - dist[w]) <= 1e-12 and not final[w]:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = [0.0] * n
        while stack_order:
            w = stack_order.pop()
            for v in pred[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]
    return [c / 2.0 for c in cb]


def _edge_min_cut(n, adj, s, t):
    """Menger edge-connectivity between s and t: min #edges whose removal disconnects them.

    Unit-capacity max-flow (Edmonds–Karp / BFS augmenting paths) on the undirected graph — each
    undirected edge {u,v} becomes capacity-1 arcs u→v and v→u. → (value, cut_edges[(u,v) u<v])."""
    if s == t:
        return (0, [])
    from collections import defaultdict, deque
    cap = defaultdict(int)
    adjset = [set() for _ in range(n)]
    for u in range(n):
        for v, _w in adj[u]:
            cap[(u, v)] += 1
            adjset[u].add(v)
    flow = 0
    while True:
        # BFS for an augmenting path in the residual graph.
        parent = [-1] * n
        parent[s] = s
        q = deque([s])
        while q:
            u = q.popleft()
            if u == t:
                break
            for v in adjset[u]:
                if parent[v] == -1 and cap[(u, v)] > 0:
                    parent[v] = u
                    q.append(v)
        if parent[t] == -1:
            break
        # Augment by 1 (unit capacities).
        v = t
        while v != s:
            u = parent[v]
            cap[(u, v)] -= 1
            cap[(v, u)] += 1
            v = u
        flow += 1
    # Min-cut edges = original edges from the reachable (residual) side to the unreachable side.
    reach = [False] * n
    dq = [s]
    reach[s] = True
    while dq:
        u = dq.pop()
        for v in adjset[u]:
            if not reach[v] and cap[(u, v)] > 0:
                reach[v] = True
                dq.append(v)
    cut_edges = set()
    for u in range(n):
        if not reach[u]:
            continue
        for v, _w in adj[u]:
            if not reach[v]:
                cut_edges.add((min(u, v), max(u, v)))
    return (flow, sorted(cut_edges))


# ═══════════════════════════ PURE GEOMETRY CORE ══════════════════════════════

# J2000 ICRS equatorial-rectangular → galactic-rectangular rotation (Hipparcos/Perryman). The
# catalog's x/y/z (core.shared._to_cartesian) are ICRS equatorial, so R·(x,y,z) → galactic.
_EQ2GAL = (
    (-0.0548755604162154, -0.8734370902348850, -0.4838350155487132),
    (+0.4941094278755837, -0.4448296299600112, +0.7469822444972189),
    (-0.8676661490190047, -0.1980763734312015, +0.4559837761750669),
)


def _equatorial_to_galactic_lb(x, y, z):
    """Equatorial-rectangular unit vector → galactic (l, b) in degrees, l ∈ [0,360), b ∈ [-90,90]."""
    r = math.sqrt(x * x + y * y + z * z)
    if r == 0:
        return (0.0, 0.0)
    xe, ye, ze = x / r, y / r, z / r
    xg = _EQ2GAL[0][0] * xe + _EQ2GAL[0][1] * ye + _EQ2GAL[0][2] * ze
    yg = _EQ2GAL[1][0] * xe + _EQ2GAL[1][1] * ye + _EQ2GAL[1][2] * ze
    zg = _EQ2GAL[2][0] * xe + _EQ2GAL[2][1] * ye + _EQ2GAL[2][2] * ze
    l = math.degrees(math.atan2(yg, xg)) % 360.0
    b = math.degrees(math.asin(max(-1.0, min(1.0, zg))))
    return (l, b)


def _angular_sep_deg(u, v):
    """Angle (deg) between two 3-vectors (need not be unit)."""
    du = math.sqrt(sum(c * c for c in u))
    dv = math.sqrt(sum(c * c for c in v))
    if du == 0 or dv == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(u, v)) / (du * dv)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _cluster_bearings(vectors, cluster_deg):
    """Greedy angular clustering: assign each bearing to the first cluster whose representative
    (its first member) is within cluster_deg, else start a new cluster. → labels[len(vectors)]."""
    reps = []           # representative vector per cluster
    labels = []
    for vec in vectors:
        placed = None
        for ci, rep in enumerate(reps):
            if _angular_sep_deg(vec, rep) < cluster_deg:
                placed = ci
                break
        if placed is None:
            placed = len(reps)
            reps.append(vec)
        labels.append(placed)
    return labels, len(reps)


def _cone_coverage_fraction(n_cones, halfwidth_deg):
    """Σ Ω_cone / 4π for n identical cones; Ω_cone = 2π(1−cos hw). = n·(1−cos hw)/2."""
    return n_cones * (1.0 - math.cos(math.radians(halfwidth_deg))) / 2.0


# ══════════════════════════ T1 — network-centrality ══════════════════════════

def _resolve_t_node_set(stars, within_ly, of, catalog):
    """→ (nodes[list of pool dicts], model_note_prefix) or {"error": str}.

    Node set via --stars (resolve each), --within-ly N --of <star> (bounding volume), or --catalog
    (whole pool). Exactly one selector."""
    n_sel = sum([bool(stars), within_ly is not None or of is not None, bool(catalog)])
    if n_sel != 1:
        return {"error": "Provide exactly one node-set selector: --stars, "
                         "--within-ly with --of, or --catalog."}
    if stars:
        if len(stars) < 2:
            return {"error": "--stars needs at least 2 stars."}
        nodes = []
        seen = set()
        for i, name in enumerate(stars):
            if not name or not name.strip():
                return {"error": f"Star {i + 1} is blank."}
            rec = calc._resolve_star_position(name)
            if "error" in rec:
                return {"error": f"'{name.strip()}': {rec['error']}"}
            key = rec["name"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            nodes.append(rec)
        if len(nodes) < 2:
            return {"error": "Fewer than 2 distinct stars resolved."}
        return (nodes, "supplied star set")
    if within_ly is not None or of is not None:
        if within_ly is None or not of:
            return {"error": "--within-ly and --of must be given together."}
        if within_ly <= 0:
            return {"error": "--within-ly must be > 0."}
        centre = calc._resolve_star_position(of)
        if "error" in centre:
            return centre
        pool_res = calc._load_star_systems_positions()
        if "error" in pool_res:
            return pool_res
        nodes = [p for p in pool_res["stars"] if calc._node_dist(p, centre) <= within_ly]
        calc._merge_endpoint(nodes, centre)     # ensure the centre is in the set
        if len(nodes) < 2:
            return {"error": f"Fewer than 2 stars within {within_ly} ly of '{centre['name']}'."}
        return (nodes, f"{len(nodes)} stars within {within_ly} ly of {centre['name']}")
    # catalog
    pool_res = calc._load_star_systems_positions()
    if "error" in pool_res:
        return pool_res
    nodes = list(pool_res["stars"])
    if len(nodes) < 2:
        return {"error": "Catalog has fewer than 2 stars."}
    return (nodes, "full catalog")


def compute_network_centrality(stars=None, within_ly=None, of=None, catalog=False,
                               max_jump_ly=None, weight="hops", from_star=None, to_star=None,
                               top=None, dust_map="auto", dust_step_pc=5.0):
    """Graph analytics over a jump-limited star network: degree + betweenness (route value /
    chokepoints), articulation points + bridges (true topological cut-vertices), optional min-cut.

    Node set: --stars | --within-ly N --of <star> | --catalog. Edges = pairs within --max-jump ly.
    --weight {hops,distance,dust} selects the betweenness shortest-path metric — dust minimises the
    integrated A_V corridor (composes the dust-routing edge cost; needs the WSL/Linux dust extra,
    curated error otherwise). --from/--to → a pairwise edge min-cut (topological; weight-independent).
    --top N caps the reported highest-centrality nodes (default 25).
    """
    if max_jump_ly is None or max_jump_ly <= 0:
        return {"error": "--max-jump must be > 0."}
    if weight not in ("hops", "distance", "dust"):
        return {"error": "--weight must be 'hops', 'distance', or 'dust'."}
    if top is not None:
        try:
            top = int(top)
        except (TypeError, ValueError):
            return {"error": "--top must be a positive integer."}
        if top < 1:
            return {"error": "--top must be a positive integer."}
    resolved = _resolve_t_node_set(stars, within_ly, of, catalog)
    if isinstance(resolved, dict):      # {"error": ...}
        return resolved
    nodes, set_note = resolved
    n = len(nodes)

    # Dust weighting composes the dust-routing layer's A_V edge cost (kept OUT of the graph layer —
    # dustmaps is imported lazily, only inside core.dust, so this module stays importable on Windows).
    dust_errors = []
    dust_seg = None
    if weight == "dust":
        if dust_step_pc is None or dust_step_pc <= 0:
            return {"error": "--dust-step-pc must be > 0."}
        import core.dust_routing as dust_routing
        pf = dust_routing._preflight(dust_map)      # validates map + dust-extra availability
        if pf is not None:
            return pf
        _dust_memo = {}

        def dust_seg(a_node, b_node):
            seg = dust_routing._seg_cached(a_node, b_node, dust_map, dust_step_pc, _dust_memo)
            if "error" in seg:
                dust_errors.append(seg["error"])
                return None                          # unknown extinction → routed around (inf weight)
            return seg["a_v"]

    # Build undirected edges via the spatial grid (dedupe u<v). This yields a SIMPLE graph — no
    # self-loops (grid.neighbors skips j==i) and no parallel edges (u<v dedup). That invariant is
    # LOAD-BEARING: _articulation_and_bridges' parent-skip and _edge_min_cut's cut_set==value
    # equality both assume simple; introducing parallel edges into `adj` would silently break them.
    # Only _betweenness reads the weight; degree/articulation/bridges/components/min-cut are
    # topological, so a dust-unavailable edge (inf weight) is still counted for those.
    grid = calc._SpatialGrid(nodes, max_jump_ly)
    adj = [[] for _ in range(n)]
    n_edges = 0
    for u in range(n):
        for v, w in grid.neighbors(u, max_jump_ly):
            if u < v:
                if weight == "hops":
                    wt = 1.0
                elif weight == "distance":
                    wt = max(w, 1e-9)
                else:  # dust — integrated A_V, floored positive so Brandes' tie logic holds
                    av = dust_seg(nodes[u], nodes[v])
                    wt = math.inf if av is None else max(av, 1e-9)
                adj[u].append((v, wt))
                adj[v].append((u, wt))
                n_edges += 1

    degrees = _degrees(adj)
    ap_idx, bridges_idx = _articulation_and_bridges(n, adj)
    labels, n_comp = _connected_components(n, adj)

    # from/to min-cut (index lookup by resolved position).
    min_cut = None
    cut_capped = False
    if from_star is not None or to_star is not None:
        if from_star is None or to_star is None:
            return {"error": "--from and --to must be given together."}
        # Local-first: if the endpoint is already a node (by name), skip the SIMBAD round-trip — this
        # lets a --within-ly min-cut run without the optional astroquery dep (WB MSG 018 note).
        si, err = _resolve_endpoint_index(from_star, nodes)
        if err is not None:
            return {"error": f"--from '{from_star}': {err}"}
        ti, err = _resolve_endpoint_index(to_star, nodes)
        if err is not None:
            return {"error": f"--to '{to_star}': {err}"}
        if si is None:
            return {"error": f"--from '{from_star.strip()}' is not in the node set."}
        if ti is None:
            return {"error": f"--to '{to_star.strip()}' is not in the node set."}
        if si == ti:
            return {"error": "--from and --to resolve to the same node."}
        if n > _BETWEENNESS_CAP:
            cut_capped = True
        else:
            val, cut_edges = _edge_min_cut(n, adj, si, ti)
            min_cut = {"value": val,
                       "cut_set": [{"from": nodes[a]["name"], "to": nodes[b]["name"]}
                                   for a, b in cut_edges]}

    # Betweenness (capped).
    capped = n > _BETWEENNESS_CAP
    betw = None if capped else _betweenness(n, adj)

    node_rows = [{"name": nodes[i]["name"], "degree": degrees[i],
                  "betweenness": (None if betw is None else betw[i])} for i in range(n)]
    node_rows.sort(key=lambda r: (r["betweenness"] if r["betweenness"] is not None else -1,
                                  r["degree"]), reverse=True)
    reported = node_rows[:(top if top is not None else _DEFAULT_TOP)]

    note = ("Models a jump-limited-route topology (STL lanes, beamrider corridors, fuel-range "
            "networks) where movement IS edge-constrained. In the mature FTL free-emergence regime a "
            "ship is NOT forced through cut-vertices — there the operative chokepoint is the "
            "arrival-corridor geometry (arrival-corridors) + the exclusion boundary, not betweenness. "
            "Degree/articulation/bridges/components are O(V+E) and always computed; betweenness and "
            "min-cut are capped at " + str(_BETWEENNESS_CAP) + " nodes.")
    if capped:
        note += (f" This set has {n} nodes (> cap), so betweenness is null — narrow --within-ly or "
                 "pass --stars for a route-value ranking.")
    if cut_capped:
        note += " min_cut is null for the same reason."
    if weight == "dust":
        note += (" Betweenness minimises integrated dust extinction A_V per edge (composes the "
                 "dust-routing cost; the graph layer never imports dustmaps). An edge whose sightline "
                 "the dust map cannot integrate is routed around (inf weight) but still counted for "
                 "degree/articulation/bridges; such edges, if any, are listed in dust_errors.")

    result = {
        "nodes": reported,
        "n_reported": len(reported),
        "articulation_points": sorted(nodes[i]["name"] for i in ap_idx),
        "bridges": sorted([nodes[a]["name"], nodes[b]["name"]] for a, b in bridges_idx),
        "min_cut": min_cut,
        "graph": {"n_nodes": n, "n_edges": n_edges, "connected": n_comp == 1,
                  "components": n_comp},
        "node_set": set_note,
        "max_jump_ly": max_jump_ly,
        "weight": weight,
        "betweenness_capped": capped,
        "model_note": note,
    }
    if weight == "dust":
        result["dust_map"] = dust_map
        result["dust_step_pc"] = dust_step_pc
        if dust_errors:
            # dedupe, cap — a systemic map-coverage miss shouldn't flood the payload
            result["dust_errors"] = sorted(set(dust_errors))[:10]
    return result


def _index_of(nodes, rec):
    """Index of the node matching rec by name (ci) or within 1e-3 ly, else None."""
    nm = rec["name"].strip().lower()
    for i, p in enumerate(nodes):
        if p["name"].strip().lower() == nm or calc._node_dist(p, rec) <= 1e-3:
            return i
    return None


def _resolve_endpoint_index(name, nodes):
    """Min-cut endpoint → node index. Local-first: match the built node set by name (offline) before
    a SIMBAD round-trip (WB MSG 018 — lets a --within-ly min-cut run without astroquery).
    → (index|None, error_str|None)."""
    if not name or not name.strip():
        return (None, "blank star name")
    nm = name.strip().lower()
    for i, p in enumerate(nodes):
        if p["name"].strip().lower() == nm:
            return (i, None)
    rec = calc._resolve_star_position(name)     # DB-first, then SIMBAD
    if "error" in rec:
        return (None, rec["error"])
    return (_index_of(nodes, rec), None)


# ══════════════════════════ T2 — arrival-corridors ═══════════════════════════

def compute_arrival_corridors(system=None, within_ly=None, origins=None,
                              corridor_halfwidth_deg=5.0, cluster_deg=5.0,
                              min_jump=None, max_jump=None):
    """FTL-emergence / picket geometry for a system: enumerate origin bearings, cluster them into
    corridors, and size the picket solid angle.

    Origins via --within-ly N (all systems within N ly) or --origins <list>. Bearings are unit
    vectors system→origin reported as galactic (l,b); light_lag_yr = distance_ly. --cluster-deg
    merges origins whose bearings differ by less than it; --corridor-halfwidth-deg sizes each
    picket cone. angular_coverage_fraction = Σ Ω_cone/4π — the "un-wallable but ε of the sky" number.
    """
    if not system or not system.strip():
        return {"error": "--system is required."}
    if corridor_halfwidth_deg <= 0 or corridor_halfwidth_deg > 180:
        return {"error": "--corridor-halfwidth-deg must be in (0, 180]."}
    if cluster_deg <= 0 or cluster_deg > 180:
        return {"error": "--cluster-deg must be in (0, 180]."}
    if (within_ly is not None) == bool(origins):
        return {"error": "Provide exactly one origin selector: --within-ly N or --origins <list>."}
    if min_jump is not None and min_jump < 0:
        return {"error": "--min-jump must be ≥ 0."}
    if max_jump is not None and max_jump <= 0:
        return {"error": "--max-jump must be > 0."}
    if min_jump is not None and max_jump is not None and min_jump >= max_jump:
        return {"error": "--min-jump must be < --max-jump."}

    sys_rec = calc._resolve_star_position(system)
    if "error" in sys_rec:
        return sys_rec

    # Candidate origins as (name, distance_ly, bearing_vector).
    cand = []
    if within_ly is not None:
        if within_ly <= 0:
            return {"error": "--within-ly must be > 0."}
        pool_res = calc._load_star_systems_positions()
        if "error" in pool_res:
            return pool_res
        for p in pool_res["stars"]:
            d = calc._node_dist(p, sys_rec)
            if d <= 1e-3:               # the system itself
                continue
            if d <= within_ly:
                cand.append((p["name"], d, p))
    else:
        for i, name in enumerate(origins):
            if not name or not name.strip():
                return {"error": f"Origin {i + 1} is blank."}
            rec = calc._resolve_star_position(name)
            if "error" in rec:
                return {"error": f"Origin {i + 1} ('{name.strip()}'): {rec['error']}"}
            d = calc._node_dist(rec, sys_rec)
            if d <= 1e-3:
                return {"error": f"Origin {i + 1} ('{name.strip()}') is the system itself."}
            cand.append((rec["name"], d, rec))

    # Range gate.
    def in_range(d):
        if min_jump is not None and d < min_jump:
            return False
        if max_jump is not None and d > max_jump:
            return False
        return True
    cand = [c for c in cand if in_range(c[1])]
    if not cand:
        return {"error": "No candidate origins after the distance/range filters."}

    # Bearings (unit vectors system→origin) + galactic (l,b).
    vectors = []
    for _name, _d, rec in cand:
        vectors.append((rec["x"] - sys_rec["x"], rec["y"] - sys_rec["y"], rec["z"] - sys_rec["z"]))
    labels, n_clusters = _cluster_bearings(vectors, cluster_deg)

    corridors = []
    for (name, d, _rec), vec, lbl in sorted(zip(cand, vectors, labels), key=lambda t: t[0][1]):
        l, b = _equatorial_to_galactic_lb(*vec)
        corridors.append({"origin": name, "distance_ly": d, "bearing_lb": {"l": l, "b": b},
                          "light_lag_yr": d, "cluster_id": lbl})

    coverage = _cone_coverage_fraction(n_clusters, corridor_halfwidth_deg)
    return {
        "system": sys_rec["name"],
        "corridors": corridors,
        "n_origins": len(cand),
        "n_distinct_corridors": n_clusters,
        "corridor_halfwidth_deg": corridor_halfwidth_deg,
        "cluster_deg": cluster_deg,
        "angular_coverage_fraction": coverage,
        "model_note": ("Geometry only: it enumerates and clusters origin bearings (galactic l,b via "
                       "the J2000 equatorial→galactic rotation) and sizes the picket solid angle "
                       "Σ Ω_cone/4π, Ω_cone = 2π(1−cos halfwidth). light_lag_yr = distance_ly "
                       "(detect-at-emergence lag). It does NOT decide interdiction DOCTRINE "
                       "(mobile sensor-cued screens, corridor width vs runner speed, leakage to "
                       "route-flexible traffic) — that is Pkt 38. Assumes arrivals approach along the "
                       "bearing to their origin system; route-flexible or multi-leg arrivals widen "
                       "the effective corridor set."),
    }
