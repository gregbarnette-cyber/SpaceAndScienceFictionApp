# tests/test_route_planning_opts.py — Phase I-OPTS route planners (A/B/C/D).
#
# Offline coverage for compute_optimal_tour (A), compute_jump_route (B),
# compute_jump_network (C), compute_farthest_first_chain (D), and the
# core.viz.prepare_route_map branches for each. All resolution uses "Sol"
# (origin, no SIMBAD) plus seeded star_systems rows (DB-first hit); one test per
# function monkeypatches the SIMBAD fallback. Runs against a tmp fixture DB (the
# tests/test_db_backups.py / test_route_planning.py pattern) so data/space_app.db
# is never touched.

import math
import pathlib
import shutil
import tempfile
import unittest

import core.calculators as calc
import core.db as db
import core.viz as viz


def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


def _radec_for_xyz(x, y, z):
    """Inverse of _to_cartesian: (x,y,z) ly → ('HH MM SS.ssss', '±DD MM SS.ssss', ly)."""
    ly = math.sqrt(x * x + y * y + z * z)
    dec = math.degrees(math.asin(z / ly)) if ly else 0.0
    ra = math.degrees(math.atan2(y, x)) % 360.0
    rah = ra / 15.0
    h = int(rah); m = int((rah - h) * 60); s = ((rah - h) * 60 - m) * 60
    ra_str = f"{h:02d} {m:02d} {s:08.4f}"
    sign = "-" if dec < 0 else "+"
    ad = abs(dec); dd = int(ad); dm = int((ad - dd) * 60); ds = ((ad - dd) * 60 - dm) * 60
    dec_str = f"{sign}{dd:02d} {dm:02d} {ds:07.4f}"
    return ra_str, dec_str, ly


class _SeededDBTest(unittest.TestCase):
    """Base: a tmp star_systems DB with auto-seeding disabled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()
        self._saved_simbad = calc.compute_lookup_star_for_distance

    def tearDown(self):
        calc.compute_lookup_star_for_distance = self._saved_simbad
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, name, ra, dec, ly, sp="G2V"):
        self.conn.execute(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "parallax, light_years, ra, dec) VALUES (?,?,?,?,?,?,?)",
            (name, f"NAME {name}", sp, _plx_for_ly(ly), ly, ra, dec),
        )
        self.conn.commit()

    def _seed_xyz(self, name, x, y, z, sp="G2V"):
        ra, dec, ly = _radec_for_xyz(x, y, z)
        self._seed(name, ra, dec, ly, sp)

    def _seed_default(self):
        # +x line at 3, 5, 8 ly; a +y star at 5 ly.
        self._seed("AX3", "00 00 00", "+00 00 00", 3.0, "M3V")
        self._seed("AX5", "00 00 00", "+00 00 00", 5.0, "K2V")
        self._seed("AX8", "00 00 00", "+00 00 00", 8.0, "G5V")
        self._seed("BY5", "06 00 00", "+00 00 00", 5.0, "F5V")


# ── A — Optimal Tour ─────────────────────────────────────────────────────────

class OptimalTourTest(_SeededDBTest):

    def test_two_star_known_distance(self):
        self._seed_default()
        r = calc.compute_optimal_tour(["Sol", "AX5"], 0.01, False)
        self.assertNotIn("error", r)
        self.assertEqual(len(r["legs"]), 1)
        self.assertAlmostEqual(r["legs"][0]["distance_ly"], 5.0, places=4)
        self.assertAlmostEqual(r["legs"][0]["hours"], 500.0, places=2)
        self.assertAlmostEqual(r["total_ly"], 5.0, places=4)
        self.assertEqual(len(r["stars"]), 2)

    def test_2opt_beats_naive_order(self):
        self._seed_default()  # AX3/AX5/AX8 colinear on +x
        r = calc.compute_optimal_tour(["Sol", "AX8", "AX3", "AX5"], 0.01, False)
        # naive Sol→AX8→AX3→AX5 = 8 + 5 + 2 = 15; optimal Sol→AX3→AX5→AX8 = 8.
        self.assertAlmostEqual(r["naive_total_ly"], 15.0, places=4)
        self.assertAlmostEqual(r["optimized_total_ly"], 8.0, places=4)
        self.assertGreater(r["saved_ly"], 0)
        self.assertEqual([s["name"] for s in r["stars"]],
                         ["Sol", "AX3", "AX5", "AX8"])

    def test_closed_loop_adds_return_leg(self):
        self._seed_default()
        op = calc.compute_optimal_tour(["Sol", "AX3", "AX5", "AX8"], 0.01, False)
        cl = calc.compute_optimal_tour(["Sol", "AX3", "AX5", "AX8"], 0.01, False, True)
        self.assertEqual(len(cl["legs"]), len(op["legs"]) + 1)
        # closed = open (8) + return AX8→Sol (8) = 16.
        self.assertAlmostEqual(cl["total_ly"], 16.0, places=4)
        self.assertTrue(cl["closed"])

    def test_start_fixed(self):
        self._seed_default()
        r = calc.compute_optimal_tour(["AX8", "Sol", "AX3"], 0.01, False)
        self.assertEqual(r["stars"][0]["name"], "AX8")

    def test_times_c_unit(self):
        self._seed_default()
        r = calc.compute_optimal_tour(["Sol", "AX5"], 100.0, True)
        ly_hr = 100.0 / calc.HOURS_PER_JULIAN_YEAR
        self.assertAlmostEqual(r["legs"][0]["ly_hr"], ly_hr, places=9)

    def test_fewer_than_two_error(self):
        self.assertIn("error", calc.compute_optimal_tour(["Sol"], 1.0, False))

    def test_dedup_collapses_to_one(self):
        self.assertIn("error", calc.compute_optimal_tour(["Sol", "sol"], 1.0, False))

    def test_zero_velocity_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_optimal_tour(["Sol", "AX5"], 0.0, False))

    def test_unresolvable_star_error(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {"error": f"No results found for '{n}'"}
        r = calc.compute_optimal_tour(["Sol", "NOPE"], 1.0, False)
        self.assertIn("error", r)
        self.assertIn("NOPE", r["error"])


# ── B — Jump-Range Pathfinding ───────────────────────────────────────────────

class JumpRouteTest(_SeededDBTest):

    def test_direct_one_jump(self):
        self._seed_default()
        r = calc.compute_jump_route("Sol", "AX3", 4.0, "distance")
        self.assertTrue(r["reachable"])
        self.assertEqual(r["jumps"], 1)
        self.assertAlmostEqual(r["total_ly"], 3.0, places=4)

    def test_multi_hop_via_intermediate(self):
        self._seed_default()
        r = calc.compute_jump_route("Sol", "AX8", 4.0, "distance")
        self.assertTrue(r["reachable"])
        self.assertEqual(r["jumps"], 3)  # Sol→AX3→AX5→AX8
        self.assertEqual([h["to"] for h in r["route"]], ["AX3", "AX5", "AX8"])
        self.assertAlmostEqual(r["total_ly"], 8.0, places=4)

    def test_unreachable_returns_flag(self):
        self._seed_default()
        r = calc.compute_jump_route("Sol", "AX8", 2.0, "distance")
        self.assertFalse(r["reachable"])
        self.assertEqual(r["route"], [])
        self.assertEqual(len(r["stars"]), 2)

    def test_optimize_jumps_vs_distance(self):
        # Chain Sol→pA→pB→Dx (3 hops, total 8.0, nearly straight on +x) plus an
        # off-axis pM giving a 2-hop Sol→pM→Dx (total ~9.1). At max_jump 5:
        # distance-opt takes the 3-hop chain (8.0 < 9.1); jumps-opt takes pM (2).
        self._seed_xyz("Dx", 8.0, 0.0, 0.0)
        self._seed_xyz("pA", 2.67, 0.0, 0.0)
        self._seed_xyz("pB", 5.33, 0.0, 0.0)
        self._seed_xyz("pM", 3.95, 2.16, 0.0)
        dist_r = calc.compute_jump_route("Sol", "Dx", 5.0, "distance")
        jump_r = calc.compute_jump_route("Sol", "Dx", 5.0, "jumps")
        self.assertTrue(dist_r["reachable"] and jump_r["reachable"])
        self.assertEqual(dist_r["jumps"], 3)
        self.assertEqual(jump_r["jumps"], 2)
        self.assertLess(jump_r["jumps"], dist_r["jumps"])
        self.assertIn("pM", [h["to"] for h in jump_r["route"]])

    def test_same_endpoint_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_jump_route("Sol", "Sol", 5.0, "distance"))

    def test_bad_max_jump_error(self):
        self.assertIn("error", calc.compute_jump_route("Sol", "AX3", 0.0, "distance"))

    def test_bad_optimize_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_jump_route("Sol", "AX3", 5.0, "bogus"))

    def test_unresolvable_endpoint_error(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {"error": f"No results found for '{n}'"}
        r = calc.compute_jump_route("Sol", "NOPE", 5.0, "distance")
        self.assertIn("error", r)
        self.assertIn("Destination", r["error"])

    def test_simbad_origin(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {
            "name": "FARSTAR", "ra_deg": 0.0, "dec_deg": 0.0, "ly": 3.0, "desig_str": ""}
        # FARSTAR resolves to (3,0,0) = AX3's position; AX3 within 1e-3 → same star.
        r = calc.compute_jump_route("FARSTAR", "AX5", 5.0, "distance")
        self.assertTrue(r["reachable"])


# ── C — Jump Network / Reachability ──────────────────────────────────────────

class JumpNetworkTest(_SeededDBTest):

    def test_tiers_bfs_order(self):
        self._seed_default()  # AX3(3)/AX5(5)/AX8(8) on +x; BY5 on +y
        r = calc.compute_jump_network("Sol", 4.0)
        self.assertEqual(r["max_tier"], 3)
        tier_map = {t["jumps"]: [s["star_name"] for s in t["stars"]] for t in r["tiers"]}
        self.assertEqual(tier_map[0], ["Sol"])
        self.assertEqual(tier_map[1], ["AX3"])
        self.assertEqual(tier_map[2], ["AX5"])
        self.assertEqual(tier_map[3], ["AX8"])

    def test_out_of_range_excluded(self):
        self._seed_default()
        r = calc.compute_jump_network("Sol", 4.0)
        reached_names = {s["star_name"] for t in r["tiers"] for s in t["stars"]}
        self.assertNotIn("BY5", reached_names)   # +y at 5 ly, out of range
        self.assertEqual(r["unreachable_count"], 1)

    def test_max_jumps_cap(self):
        self._seed_default()
        r = calc.compute_jump_network("Sol", 4.0, max_jumps=1)
        self.assertEqual(r["max_tier"], 1)
        names = {s["star_name"] for t in r["tiers"] for s in t["stars"]}
        self.assertEqual(names, {"Sol", "AX3"})

    def test_node_colors_per_tier(self):
        self._seed_default()
        r = calc.compute_jump_network("Sol", 4.0)
        by_name = {s["name"]: s for s in r["stars"]}
        self.assertEqual(by_name["Sol"]["color"], calc.TIER_COLORS[0])
        self.assertEqual(by_name["AX3"]["color"], calc.TIER_COLORS[1])
        self.assertEqual(by_name["AX8"]["color"], calc.TIER_COLORS[3])

    def test_bad_max_jump_error(self):
        self.assertIn("error", calc.compute_jump_network("Sol", -1.0))

    def test_bad_max_jumps_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_jump_network("Sol", 4.0, max_jumps=0))

    def test_empty_table_error(self):
        r = calc.compute_jump_network("Sol", 4.0)
        self.assertIn("error", r)
        self.assertIn("star_systems", r["error"])

    def test_unresolvable_start_error(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {"error": f"No results found for '{n}'"}
        self.assertIn("error", calc.compute_jump_network("NOPE", 4.0))


# ── D — Farthest-First Coverage ──────────────────────────────────────────────

class FarthestFirstTest(_SeededDBTest):

    def test_picks_farthest_first(self):
        self._seed_default()  # AX3(3)/AX5(5)/AX8(8) on +x; BY5(5) on +y
        r = calc.compute_farthest_first_chain("Sol", 1, None)
        # nearest-neighbor would pick AX3 (3 ly); farthest-first picks AX8 (8 ly).
        self.assertEqual(r["chain"][0]["star_name"], "AX8")

    def test_tree_edge_attaches_to_nearest_visited(self):
        self._seed_default()
        r = calc.compute_farthest_first_chain("Sol", 3, None)
        # every tree edge's from_index points at an already-visited node (< to_index).
        for te in r["tree_edges"]:
            self.assertLess(te["from_index"], te["to_index"])

    def test_self_exclusion(self):
        self._seed_default()
        self._seed_xyz("ATSOL", 0.0005, 0.0, 0.0)  # within 1e-3 ly of Sol
        r = calc.compute_farthest_first_chain("Sol", 5, None)
        names = [c["star_name"] for c in r["chain"]]
        self.assertNotIn("ATSOL", names)

    def test_reach_limit_stops_early(self):
        self._seed_default()
        # max_reach 2 ly < the nearest star (AX3 at 3 ly) → nothing reachable.
        r = calc.compute_farthest_first_chain("Sol", 5, 2.0)
        self.assertTrue(r["stopped_early"])
        self.assertEqual(r["chain"], [])

    def test_num_stops_cap(self):
        self._seed_default()
        r = calc.compute_farthest_first_chain("Sol", 2, None)
        self.assertEqual(len(r["chain"]), 2)

    def test_bad_stops_error(self):
        self.assertIn("error", calc.compute_farthest_first_chain("Sol", 0, None))

    def test_bad_reach_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_farthest_first_chain("Sol", 3, -1.0))

    def test_empty_table_error(self):
        r = calc.compute_farthest_first_chain("Sol", 3, None)
        self.assertIn("error", r)
        self.assertIn("star_systems", r["error"])


# ── _SpatialGrid correctness (the O(n²)→grid scale fix) ──────────────────────

class SpatialGridTest(unittest.TestCase):
    """grid.neighbors must return exactly the brute-force within-radius set,
    including across cell boundaries and with negative coordinates."""

    def _brute(self, nodes, i, r):
        out = set()
        for j, q in enumerate(nodes):
            if j == i:
                continue
            d = math.sqrt((nodes[i]["x"] - q["x"]) ** 2 + (nodes[i]["y"] - q["y"]) ** 2
                          + (nodes[i]["z"] - q["z"]) ** 2)
            if d <= r:
                out.add(j)
        return out

    def test_matches_brute_force(self):
        import random
        rng = random.Random(1234)
        nodes = [{"x": rng.uniform(-50, 50), "y": rng.uniform(-50, 50),
                  "z": rng.uniform(-50, 50)} for _ in range(400)]
        r = 5.0
        grid = calc._SpatialGrid(nodes, r)
        for i in (0, 7, 123, 250, 399):
            got = {j for j, _d in grid.neighbors(i, r)}
            self.assertEqual(got, self._brute(nodes, i, r), f"node {i}")

    def test_cell_boundary_pair(self):
        # Two stars straddling a cell boundary but within the radius must still
        # see each other (cell = radius = 5; points at 4.9 and 5.1 on x).
        nodes = [{"x": 4.9, "y": 0.0, "z": 0.0}, {"x": 5.1, "y": 0.0, "z": 0.0}]
        grid = calc._SpatialGrid(nodes, 5.0)
        self.assertEqual({j for j, _ in grid.neighbors(0, 5.0)}, {1})


# ── prepare_route_map branches ───────────────────────────────────────────────

class PrepareRouteMapOptsTest(_SeededDBTest):

    def test_optimal_dashed_closed(self):
        self._seed_default()
        r = calc.compute_optimal_tour(["Sol", "AX3", "AX5", "AX8"], 0.01, False, True)
        rm = viz.prepare_route_map(r)
        self.assertEqual(rm["edge_style"], "dashed")
        # n-1 consecutive + 1 wrap = n edges.
        self.assertEqual(len(rm["edges"]), len(rm["stars"]))

    def test_optimal_open_no_wrap(self):
        self._seed_default()
        r = calc.compute_optimal_tour(["Sol", "AX3", "AX5", "AX8"], 0.01, False, False)
        rm = viz.prepare_route_map(r)
        self.assertEqual(len(rm["edges"]), len(rm["stars"]) - 1)

    def test_jump_route_dashed(self):
        self._seed_default()
        r = calc.compute_jump_route("Sol", "AX8", 4.0, "distance")
        rm = viz.prepare_route_map(r)
        self.assertEqual(rm["edge_style"], "dashed")
        self.assertEqual(len(rm["edges"]), len(rm["stars"]) - 1)

    def test_jump_route_unreachable_no_edges(self):
        self._seed_default()
        r = calc.compute_jump_route("Sol", "AX8", 2.0, "distance")
        rm = viz.prepare_route_map(r)
        self.assertEqual(rm["edges"], [])
        self.assertEqual(len(rm["stars"]), 2)

    def test_jump_network_nodes_only(self):
        self._seed_default()
        r = calc.compute_jump_network("Sol", 4.0)
        rm = viz.prepare_route_map(r)
        self.assertEqual(rm["edge_style"], "none")
        self.assertEqual(rm["edges"], [])
        # node colours carried through per tier.
        self.assertEqual(rm["stars"][0]["color"], calc.TIER_COLORS[0])

    def test_farthest_tree_edges(self):
        self._seed_default()
        r = calc.compute_farthest_first_chain("Sol", 3, None)
        rm = viz.prepare_route_map(r)
        self.assertEqual(rm["edge_style"], "dashed")
        self.assertEqual(len(rm["edges"]), len(r["tree_edges"]))

    def test_error_passthrough(self):
        self.assertEqual(viz.prepare_route_map({"error": "x"}), {"error": "x"})


if __name__ == "__main__":
    unittest.main()
