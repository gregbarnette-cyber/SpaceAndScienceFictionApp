# tests/test_route_planning.py — Phase I Route Planning core functions.
#
# Offline coverage for compute_multi_stop_journey (I1),
# compute_nearest_neighbor_chain (I2), compute_trade_route_mst (I3), and
# core.viz.prepare_route_map. All resolution uses "Sol" (origin, no SIMBAD) plus
# seeded star_systems rows (DB-first hit, no SIMBAD); one test monkeypatches the
# SIMBAD fallback to cover that branch. Runs against a tmp fixture DB (the
# tests/test_db_backups.py pattern) so data/space_app.db is never touched.
#
# Fixture geometry: RA "00 00 00"/DEC "+00 00 00" → +x axis; RA "06 00 00" → +y
# axis; parallax is set so light_years comes out to the round number we want, so
# every distance is hand-checkable.

import math
import pathlib
import shutil
import tempfile
import unittest

import core.calculators as calc
import core.db as db
import core.viz as viz


def _plx_for_ly(ly):
    # ly = 1000/plx * 3.26156  ⇒  plx = 1000*3.26156 / ly
    return 1000.0 * 3.26156 / ly


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

    def _seed_default(self):
        # +x line at 3, 5, 8 ly; a +y star at 5 ly.
        self._seed("AX3", "00 00 00", "+00 00 00", 3.0)
        self._seed("AX5", "00 00 00", "+00 00 00", 5.0)
        self._seed("AX8", "00 00 00", "+00 00 00", 8.0)
        self._seed("BY5", "06 00 00", "+00 00 00", 5.0)


# ── I1 — Multi-Stop Journey ──────────────────────────────────────────────────

class MultiStopJourneyTest(_SeededDBTest):

    def test_two_stop_known_distance(self):
        self._seed_default()
        r = calc.compute_multi_stop_journey(["Sol", "AX5"], 0.01, False)
        self.assertNotIn("error", r)
        self.assertEqual(len(r["legs"]), 1)
        leg = r["legs"][0]
        self.assertAlmostEqual(leg["distance_ly"], 5.0, places=4)
        self.assertAlmostEqual(leg["hours"], 500.0, places=2)        # 5 / 0.01
        self.assertAlmostEqual(leg["times_c"], 0.01 * calc.HOURS_PER_JULIAN_YEAR, places=4)
        self.assertAlmostEqual(r["total_ly"], 5.0, places=4)
        self.assertEqual(len(r["stars"]), 2)

    def test_three_stop_cumulative(self):
        self._seed_default()
        r = calc.compute_multi_stop_journey(["Sol", "AX5", "BY5"], 0.01, False)
        self.assertEqual(len(r["legs"]), 2)
        leg2 = r["legs"][1]
        # (5,0,0) → (0,5,0) = sqrt(50)
        self.assertAlmostEqual(leg2["distance_ly"], math.sqrt(50), places=4)
        self.assertAlmostEqual(leg2["cumulative_hours"],
                               r["legs"][0]["hours"] + leg2["hours"], places=6)
        self.assertAlmostEqual(r["total_ly"], 5.0 + math.sqrt(50), places=4)

    def test_times_c_unit(self):
        self._seed_default()
        r = calc.compute_multi_stop_journey(["Sol", "AX5"], 100.0, True)
        ly_hr = 100.0 / calc.HOURS_PER_JULIAN_YEAR
        self.assertAlmostEqual(r["legs"][0]["ly_hr"], ly_hr, places=9)
        self.assertAlmostEqual(r["legs"][0]["hours"], 5.0 / ly_hr, places=2)

    def test_fewer_than_two_stops_error(self):
        self.assertIn("error", calc.compute_multi_stop_journey(["Sol"], 0.01, False))

    def test_zero_velocity_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_multi_stop_journey(["Sol", "AX5"], 0.0, False))

    def test_unresolvable_stop_error(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {"error": f"No results found for '{n}'"}
        r = calc.compute_multi_stop_journey(["Sol", "NOPE"], 0.01, False)
        self.assertIn("error", r)
        self.assertIn("Stop 2", r["error"])
        self.assertIn("NOPE", r["error"])


# ── I2 — Nearest-Neighbor Chain ──────────────────────────────────────────────

class NearestNeighborChainTest(_SeededDBTest):

    def test_greedy_order(self):
        self._seed_default()   # AX3, AX5, AX8 on +x; BY5 on +y
        r = calc.compute_nearest_neighbor_chain("Sol", 3, 100.0)
        self.assertNotIn("error", r)
        names = [c["star_name"] for c in r["chain"]]
        self.assertEqual(names, ["AX3", "AX5", "AX8"])
        self.assertEqual([round(c["dist_from_prev_ly"], 3) for c in r["chain"]], [3.0, 2.0, 3.0])
        self.assertEqual([round(c["cumulative_ly"], 3) for c in r["chain"]], [3.0, 5.0, 8.0])
        self.assertAlmostEqual(r["total_ly"], 8.0, places=4)
        self.assertFalse(r["stopped_early"])

    def test_stops_early_when_out_of_range(self):
        self._seed_default()
        r = calc.compute_nearest_neighbor_chain("Sol", 3, 2.0)  # nearest is 3 ly
        self.assertEqual(r["chain"], [])
        self.assertTrue(r["stopped_early"])

    def test_self_exclusion(self):
        self._seed_default()
        self._seed("SELFROW", "00 00 00", "+00 00 00", 0.0005)  # ~at origin
        r = calc.compute_nearest_neighbor_chain("Sol", 1, 100.0)
        self.assertEqual(r["chain"][0]["star_name"], "AX3")  # not SELFROW

    def test_num_hops_caps(self):
        self._seed_default()
        r = calc.compute_nearest_neighbor_chain("Sol", 1, 100.0)
        self.assertEqual(len(r["chain"]), 1)

    def test_bad_hops_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_nearest_neighbor_chain("Sol", 0, 100.0))

    def test_bad_max_ly_error(self):
        self._seed_default()
        self.assertIn("error", calc.compute_nearest_neighbor_chain("Sol", 3, 0.0))

    def test_empty_table_error(self):
        r = calc.compute_nearest_neighbor_chain("Sol", 3, 100.0)
        self.assertIn("error", r)
        self.assertIn("star_systems", r["error"])

    def test_simbad_start(self):
        self._seed("AX3", "00 00 00", "+00 00 00", 3.0)
        self._seed("AX5", "00 00 00", "+00 00 00", 5.0)
        # FakeStar resolves (via SIMBAD fallback) to (10,0,0): ra=0,dec=0,ly=10.
        calc.compute_lookup_star_for_distance = lambda n: {
            "name": "FakeStar", "ra_deg": 0.0, "dec_deg": 0.0, "ly": 10.0, "desig_str": ""}
        r = calc.compute_nearest_neighbor_chain("FakeStar", 1, 100.0)
        # From (10,0,0): AX5 (d=5) is nearer than AX3 (d=7).
        self.assertEqual(r["chain"][0]["star_name"], "AX5")


# ── I3 — Trade-Route MST ─────────────────────────────────────────────────────

class TradeRouteMstTest(_SeededDBTest):

    def test_mst_edge_count_and_total(self):
        self._seed_default()
        r = calc.compute_trade_route_mst(["Sol", "AX3", "AX5", "BY5"])
        self.assertNotIn("error", r)
        self.assertEqual(len(r["edges"]), 3)                 # N-1
        self.assertAlmostEqual(r["total_ly"], 10.0, places=3)  # 2 + 3 + 5
        dists = [e["distance_ly"] for e in r["edges"]]
        self.assertEqual(dists, sorted(dists))               # ascending
        pairs = {frozenset((e["from"], e["to"])) for e in r["edges"]}
        self.assertEqual(pairs, {frozenset(("AX3", "AX5")),
                                 frozenset(("Sol", "AX3")),
                                 frozenset(("Sol", "BY5"))})

    def test_two_nodes_one_edge(self):
        self._seed_default()
        r = calc.compute_trade_route_mst(["Sol", "AX5"])
        self.assertEqual(len(r["edges"]), 1)
        self.assertAlmostEqual(r["edges"][0]["distance_ly"], 5.0, places=4)

    def test_fewer_than_two_error(self):
        self.assertIn("error", calc.compute_trade_route_mst(["Sol"]))

    def test_dedup_then_too_few(self):
        # Two entries that dedup to one → still "at least two" error.
        self.assertIn("error", calc.compute_trade_route_mst(["Sol", "sol"]))

    def test_unresolvable_node_error(self):
        self._seed_default()
        calc.compute_lookup_star_for_distance = lambda n: {"error": f"No results found for '{n}'"}
        r = calc.compute_trade_route_mst(["Sol", "NOPE"])
        self.assertIn("error", r)
        self.assertIn("NOPE", r["error"])


# ── Shared — prepare_route_map ───────────────────────────────────────────────

class PrepareRouteMapTest(_SeededDBTest):

    def test_ordered_dashed(self):
        self._seed_default()
        res = calc.compute_multi_stop_journey(["Sol", "AX5", "BY5"], 0.01, False)
        rm = viz.prepare_route_map(res)
        self.assertEqual(rm["edge_style"], "dashed")
        self.assertEqual(len(rm["edges"]), len(rm["stars"]) - 1)
        for e in rm["edges"]:
            for k in ("x1", "y1", "z1", "x2", "y2", "z2", "label", "style"):
                self.assertIn(k, e)
            self.assertEqual(e["style"], "dashed")

    def test_mst_solid(self):
        self._seed_default()
        res = calc.compute_trade_route_mst(["Sol", "AX3", "AX5", "BY5"])
        rm = viz.prepare_route_map(res)
        self.assertEqual(rm["edge_style"], "solid")
        self.assertEqual(len(rm["edges"]), len(res["edges"]))
        for e in rm["edges"]:
            self.assertEqual(e["style"], "solid")

    def test_error_passthrough(self):
        self.assertEqual(viz.prepare_route_map({"error": "x"}), {"error": "x"})


if __name__ == "__main__":
    unittest.main()
