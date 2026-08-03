# tests/test_strategic_geography.py — Phase AQ (Group T) strategic-geography graph analytics.
#
# Two layers, mirroring the module: (1) the DB-free PURE graph/geometry core, tested against the
# spec's deterministic anchors (the A–B–C–D chain; three origins 90° apart); (2) the catalog-backed
# wrappers compute_network_centrality (T1) / compute_arrival_corridors (T2) over a seeded tmp
# star_systems DB (the tests/test_route_planning_opts.py _SeededDBTest pattern, so data/space_app.db
# is never touched); plus the betweenness/min-cut scale-guard and the self-validating error matrix.

import math
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.calculators as calc
import core.db as db
import core.dust_routing as dr
import core.strategic_geography as G


# ─────────────────────────────── PURE GRAPH CORE ───────────────────────────────

class PureGraphCoreTest(unittest.TestCase):
    def _chain(self):
        # A(0)-B(1)-C(2)-D(3), undirected unit weights.
        return 4, [[(1, 1.0)], [(0, 1.0), (2, 1.0)], [(1, 1.0), (3, 1.0)], [(2, 1.0)]]

    def test_chain_anchor(self):
        n, adj = self._chain()
        self.assertEqual(G._degrees(adj), [1, 2, 2, 1])
        ap, bridges = G._articulation_and_bridges(n, adj)
        self.assertEqual(sorted(ap), [1, 2])                       # B, C
        self.assertEqual(sorted(bridges), [(0, 1), (1, 2), (2, 3)])  # AB, BC, CD
        self.assertEqual(G._betweenness(n, adj), [0.0, 2.0, 2.0, 0.0])
        _labels, ncomp = G._connected_components(n, adj)
        self.assertEqual(ncomp, 1)
        val, _cut = G._edge_min_cut(n, adj, 0, 3)
        self.assertEqual(val, 1)                                    # any single bridge

    def test_square_tie_handling(self):
        # 0-1-2-3-0: two equal geodesics on each diagonal → betweenness 0.5 each; no artic/bridges.
        sq = [[(1, 1.0), (3, 1.0)], [(0, 1.0), (2, 1.0)],
              [(1, 1.0), (3, 1.0)], [(2, 1.0), (0, 1.0)]]
        self.assertEqual(G._betweenness(4, sq), [0.5, 0.5, 0.5, 0.5])
        ap, bridges = G._articulation_and_bridges(4, sq)
        self.assertEqual(sorted(ap), [])
        self.assertEqual(bridges, [])
        self.assertEqual(G._edge_min_cut(4, sq, 0, 2)[0], 2)

    def test_disconnected_components(self):
        adj = [[(1, 1.0)], [(0, 1.0)], [(3, 1.0)], [(2, 1.0)]]   # two separate edges
        _labels, ncomp = G._connected_components(4, adj)
        self.assertEqual(ncomp, 2)
        self.assertEqual(G._edge_min_cut(4, adj, 0, 2)[0], 0)     # unreachable → cut 0

    def test_distance_weighted_betweenness(self):
        # Triangle where the direct A–C edge is longer than A–B–C: shortest A–C routes through B.
        adj = [[(1, 1.0), (2, 3.0)], [(0, 1.0), (2, 1.0)], [(1, 1.0), (0, 3.0)]]
        betw = G._betweenness(3, adj)
        self.assertGreater(betw[1], 0.0)      # B carries the A–C shortest path
        self.assertEqual(betw[0], 0.0)
        self.assertEqual(betw[2], 0.0)


# ─────────────────────────────── PURE GEOMETRY CORE ───────────────────────────────

class PureGeometryCoreTest(unittest.TestCase):
    def test_three_corridors_90deg(self):
        vecs = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]      # mutually 90°
        _labels, nclusters = G._cluster_bearings(vecs, 5.0)
        self.assertEqual(nclusters, 3)
        cov = G._cone_coverage_fraction(nclusters, 5.0)
        self.assertAlmostEqual(cov, 0.005707952862, places=10)     # ≈ 0.57 % of sky

    def test_clustering_merges_close_bearings(self):
        vecs = [(1, 0, 0), (1, 0.01, 0), (0, 1, 0)]   # first two within ~0.6°
        _labels, nclusters = G._cluster_bearings(vecs, 5.0)
        self.assertEqual(nclusters, 2)

    def test_angular_separation(self):
        self.assertAlmostEqual(G._angular_sep_deg((1, 0, 0), (0, 1, 0)), 90.0, places=6)
        self.assertAlmostEqual(G._angular_sep_deg((1, 0, 0), (1, 0, 0)), 0.0, places=6)

    def test_galactic_center_maps_to_origin(self):
        # Equatorial coords of the galactic centre (RA 266.405°, Dec −28.936°) → (l,b) ≈ (0,0).
        ra, dec = math.radians(266.405), math.radians(-28.936)
        x, y, z = math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)
        l, b = G._equatorial_to_galactic_lb(x, y, z)
        self.assertAlmostEqual(l, 0.0, delta=0.05)
        self.assertAlmostEqual(b, 0.0, delta=0.05)

    def test_coverage_fraction_formula(self):
        self.assertAlmostEqual(G._cone_coverage_fraction(1, 90.0), 0.5, places=10)  # hemisphere


# ─────────────────────────── catalog-backed integration ───────────────────────────

def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


def _radec_for_xyz(x, y, z):
    ly = math.sqrt(x * x + y * y + z * z)
    dec = math.degrees(math.asin(z / ly)) if ly else 0.0
    ra = math.degrees(math.atan2(y, x)) % 360.0
    rah = ra / 15.0
    h = int(rah); m = int((rah - h) * 60); s = ((rah - h) * 60 - m) * 60
    ad = abs(dec); dd = int(ad); dm = int((ad - dd) * 60); ds = ((ad - dd) * 60 - dm) * 60
    return (f"{h:02d} {m:02d} {s:08.4f}",
            f"{'-' if dec < 0 else '+'}{dd:02d} {dm:02d} {ds:07.4f}", ly)


class _SeededDBTest(unittest.TestCase):
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

    def _seed_xyz(self, name, x, y, z, sp="G2V"):
        ra, dec, ly = _radec_for_xyz(x, y, z)
        self.conn.execute(
            "INSERT INTO star_systems (star_name, designations, spectral_type, "
            "parallax, light_years, ra, dec) VALUES (?,?,?,?,?,?,?)",
            (name, f"NAME {name}", sp, _plx_for_ly(ly), ly, ra, dec))
        self.conn.commit()


class NetworkCentralityIntegrationTest(_SeededDBTest):
    def _seed_chain(self):
        # collinear chain offset from Sol: A(10)-B(13)-C(16)-D(19), adjacent spacing 3 ly.
        for nm, x in (("A", 10.0), ("B", 13.0), ("C", 16.0), ("D", 19.0)):
            self._seed_xyz(nm, x, 0.0, 0.0)

    def test_chain_via_catalog(self):
        self._seed_chain()
        r = G.compute_network_centrality(stars=["A", "B", "C", "D"], max_jump_ly=3.1,
                                         from_star="A", to_star="D")
        self.assertNotIn("error", r)
        self.assertEqual(r["graph"], {"n_nodes": 4, "n_edges": 3, "connected": True,
                                      "components": 1})
        self.assertEqual(r["articulation_points"], ["B", "C"])
        self.assertEqual(r["bridges"], [["A", "B"], ["B", "C"], ["C", "D"]])
        betw = {n["name"]: n["betweenness"] for n in r["nodes"]}
        self.assertEqual(betw["B"], 2.0)
        self.assertEqual(betw["C"], 2.0)
        self.assertEqual(betw["A"], 0.0)
        self.assertEqual(r["min_cut"]["value"], 1)

    def test_within_ly_of_sol(self):
        self._seed_chain()
        r = G.compute_network_centrality(within_ly=25, of="Sol", max_jump_ly=3.1)
        self.assertNotIn("error", r)
        # Sol(0) + A(10) are >3.1 apart from each other's neighbours; A-B-C-D chain present.
        self.assertGreaterEqual(r["graph"]["n_nodes"], 4)

    def test_scale_guard_nulls_betweenness(self):
        self._seed_chain()
        saved = G._BETWEENNESS_CAP
        try:
            G._BETWEENNESS_CAP = 3      # 4-node set now exceeds the cap
            r = G.compute_network_centrality(stars=["A", "B", "C", "D"], max_jump_ly=3.1,
                                             from_star="A", to_star="D")
            self.assertTrue(r["betweenness_capped"])
            self.assertTrue(all(n["betweenness"] is None for n in r["nodes"]))
            self.assertIsNone(r["min_cut"])                 # capped too
            self.assertEqual(r["articulation_points"], ["B", "C"])   # cheap metrics still run
            self.assertIn("cap", r["model_note"])
        finally:
            G._BETWEENNESS_CAP = saved

    def test_errors(self):
        self.assertIn("error", G.compute_network_centrality(max_jump_ly=5))          # no selector
        self.assertIn("error", G.compute_network_centrality(stars=["A", "B"], catalog=True,
                                                            max_jump_ly=5))            # two selectors
        self.assertIn("error", G.compute_network_centrality(stars=["A", "B"], max_jump_ly=0))
        self.assertIn("error", G.compute_network_centrality(stars=["A", "B"], max_jump_ly=5,
                                                            weight="bogus"))          # bad weight
        self.assertIn("error", G.compute_network_centrality(within_ly=10, max_jump_ly=5))  # no --of
        r = G.compute_network_centrality(stars=["A"], max_jump_ly=5)                  # <2 stars
        self.assertIn("error", r)


class ArrivalCorridorsIntegrationTest(_SeededDBTest):
    def test_three_origins_90deg(self):
        # Sol at origin; three origins on the +x/+y/+z axes → mutually 90°.
        self._seed_xyz("O1", 4.0, 0.0, 0.0)
        self._seed_xyz("O2", 0.0, 4.0, 0.0)
        self._seed_xyz("O3", 0.0, 0.0, 4.0)
        r = G.compute_arrival_corridors(system="Sol", origins=["O1", "O2", "O3"],
                                        corridor_halfwidth_deg=5.0, cluster_deg=5.0)
        self.assertNotIn("error", r)
        self.assertEqual(r["n_origins"], 3)
        self.assertEqual(r["n_distinct_corridors"], 3)
        self.assertAlmostEqual(r["angular_coverage_fraction"], 0.005707952862, places=8)
        self.assertEqual(len(r["corridors"]), 3)
        for c in r["corridors"]:
            self.assertAlmostEqual(c["distance_ly"], 4.0, places=3)
            self.assertAlmostEqual(c["light_lag_yr"], c["distance_ly"], places=9)

    def test_within_ly(self):
        self._seed_xyz("O1", 4.0, 0.0, 0.0)
        self._seed_xyz("O2", 0.0, 4.0, 0.0)
        self._seed_xyz("Far", 0.0, 0.0, 40.0)
        r = G.compute_arrival_corridors(system="Sol", within_ly=10.0)
        self.assertEqual(r["n_origins"], 2)       # Far (40 ly) excluded

    def test_range_gate(self):
        self._seed_xyz("Near", 2.0, 0.0, 0.0)
        self._seed_xyz("Mid", 6.0, 0.0, 0.0)
        r = G.compute_arrival_corridors(system="Sol", within_ly=20.0, min_jump=3.0, max_jump=10.0)
        self.assertEqual(r["n_origins"], 1)       # only Mid (6 ly) survives [3,10]

    def test_errors(self):
        self.assertIn("error", G.compute_arrival_corridors(within_ly=10))            # no system
        self.assertIn("error", G.compute_arrival_corridors(system="Sol"))            # no origin sel
        self.assertIn("error", G.compute_arrival_corridors(system="Sol", within_ly=10,
                                                          origins=["O1"]))            # both
        self.assertIn("error", G.compute_arrival_corridors(system="Sol", within_ly=10,
                                                          corridor_halfwidth_deg=0))
        self.assertIn("error", G.compute_arrival_corridors(system="Sol", within_ly=10,
                                                          min_jump=5, max_jump=3))


class DustWeightTest(_SeededDBTest):
    """T1 `--weight dust` (Phase AQ) — betweenness over integrated A_V. The §E golden pin WB asked
    for: a dust wall on one corridor moves the chokepoint off the geometric centre. Dust is mocked
    (deterministic per-pair A_V + preflight), so these run offline/cross-platform with no dustmaps."""

    def test_dust_wall_moves_chokepoint_pure(self):
        # Weighted 4-cycle S(0)-M(1)-T(2)-D(3)-S with a wall on the M corridor (S-M, M-T = 10;
        # T-D, D-S = 1). S-T routes via D (cost 2 < 20) → D is the chokepoint; M drops to 0.
        adj = [[(1, 10.0), (3, 1.0)], [(0, 10.0), (2, 10.0)],
               [(1, 10.0), (3, 1.0)], [(2, 1.0), (0, 1.0)]]
        betw = G._betweenness(4, adj)
        self.assertEqual(betw, [0.5, 0.0, 0.5, 1.0])   # S, M, T, D → D is the dust-aware chokepoint
        # Contrast: unit weights (hops) tie all four at 0.5 — the wall is what breaks the symmetry.
        unit = [[(1, 1.0), (3, 1.0)], [(0, 1.0), (2, 1.0)],
                [(1, 1.0), (3, 1.0)], [(2, 1.0), (0, 1.0)]]
        self.assertEqual(G._betweenness(4, unit), [0.5, 0.5, 0.5, 0.5])

    def test_dust_wall_moves_chokepoint_wrapper(self):
        # Square (side 3, diagonals 4.24): S(10,0)-M(13,0)-T(13,3)-D(10,3); max_jump 3.5 → 4-cycle.
        for nm, x, y in (("S", 10, 0), ("M", 13, 0), ("T", 13, 3), ("D", 10, 3)):
            self._seed_xyz(nm, float(x), float(y), 0.0)
        wall = {frozenset(("S", "M")): 10.0, frozenset(("M", "T")): 10.0,
                frozenset(("T", "D")): 1.0, frozenset(("D", "S")): 1.0}

        def fake_seg(a, b, map_sel, step):
            return {"a_v": wall[frozenset((a["name"], b["name"]))]}

        with mock.patch.object(dr, "_preflight", lambda m: None), \
             mock.patch.object(dr, "_seg", fake_seg):
            r = G.compute_network_centrality(stars=["S", "M", "T", "D"], max_jump_ly=3.5,
                                             weight="dust")
        self.assertNotIn("error", r)
        self.assertEqual(r["weight"], "dust")
        self.assertEqual(r["graph"]["n_edges"], 4)
        betw = {n["name"]: n["betweenness"] for n in r["nodes"]}
        self.assertEqual(betw["D"], 1.0)      # dust chokepoint
        self.assertEqual(betw["M"], 0.0)      # the walled corridor carries no shortest path
        # min-cut stays topological (weight-independent): the 4-cycle needs 2 edges cut.
        with mock.patch.object(dr, "_preflight", lambda m: None), \
             mock.patch.object(dr, "_seg", fake_seg):
            rc = G.compute_network_centrality(stars=["S", "M", "T", "D"], max_jump_ly=3.5,
                                              weight="dust", from_star="S", to_star="T")
        self.assertEqual(rc["min_cut"]["value"], 2)

    def test_dust_extra_unavailable_is_graceful(self):
        # When the dust extra/map is absent, _preflight returns a curated error → propagated cleanly.
        self._seed_xyz("A", 10.0, 0.0, 0.0)
        self._seed_xyz("B", 13.0, 0.0, 0.0)
        with mock.patch.object(dr, "_preflight", lambda m: {"error": "dust extra not installed"}):
            r = G.compute_network_centrality(stars=["A", "B"], max_jump_ly=3.5, weight="dust")
        self.assertIn("error", r)
        self.assertIn("dust extra", r["error"])

    def test_dust_step_pc_validation(self):
        self._seed_xyz("A", 10.0, 0.0, 0.0)
        self._seed_xyz("B", 13.0, 0.0, 0.0)
        with mock.patch.object(dr, "_preflight", lambda m: None):
            r = G.compute_network_centrality(stars=["A", "B"], max_jump_ly=3.5, weight="dust",
                                             dust_step_pc=0)
        self.assertIn("error", r)


class MinCutLocalFirstTest(_SeededDBTest):
    """WB MSG 018 note: min-cut endpoints resolve local-first (node set before SIMBAD), so a
    within-set min-cut needs no network even if compute_lookup_star_for_distance is unavailable."""

    def test_endpoints_resolve_without_network(self):
        for nm, x in (("A", 10.0), ("B", 13.0), ("C", 16.0)):
            self._seed_xyz(nm, x, 0.0, 0.0)

        def _boom(*a, **k):
            raise AssertionError("SIMBAD should not be called — endpoints are in the node set")

        calc.compute_lookup_star_for_distance = _boom   # tearDown restores it
        r = G.compute_network_centrality(stars=["A", "B", "C"], max_jump_ly=3.5,
                                         from_star="A", to_star="C")
        self.assertNotIn("error", r)
        self.assertEqual(r["min_cut"]["value"], 1)      # chain A-B-C


if __name__ == "__main__":
    unittest.main()
