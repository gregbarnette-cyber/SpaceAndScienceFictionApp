# tests/test_dust_routing.py — Phase T2 Part B (dust-weighted routing) contracts.
#
# Two non-gated styles (no dustmaps DATA needed):
#   - ROUTING-LOGIC tests mock core.dust_routing._seg (the per-leg A_V cost) with
#     a controlled edge cost, so the Dijkstra/MST/NN/2-opt logic + the distance-
#     optimal comparison are verified deterministically against a seeded offline
#     star_systems DB (the test_route_planning_opts pattern). Also mocks the dust
#     availability/preflight so they run even without the optional extra.
#   - An INTEGRATION-WIRING test mocks core.dust._query_native (constant density)
#     so `_seg`→A_V flows end-to-end; constant density ⇒ A_V ∝ ly ⇒ the dust route
#     coincides with the distance route (saved_av ≈ 0).
# Plus the preflight/exit-code matrix and a weight=distance delegation guard.

import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

import core.calculators as calc
import core.db as db
import core.dust as dust
import core.dust_routing as dr
from tests._dustcheck import dustmaps_importable

from tests._queryharness import run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _plx_for_ly(ly):
    return 1000.0 * 3.26156 / ly


def _radec_for_xyz(x, y, z):
    ly = math.sqrt(x * x + y * y + z * z)
    dec = math.degrees(math.asin(z / ly)) if ly else 0.0
    ra = math.degrees(math.atan2(y, x)) % 360.0
    rah = ra / 15.0
    h = int(rah); m = int((rah - h) * 60); s = ((rah - h) * 60 - m) * 60
    sign = "-" if dec < 0 else "+"
    ad = abs(dec); dd = int(ad); dm = int((ad - dd) * 60); ds = ((ad - dd) * 60 - dm) * 60
    return f"{h:02d} {m:02d} {s:08.4f}", f"{sign}{dd:02d} {dm:02d} {ds:07.4f}", ly


def _seg_factory(cost_by_pair, default_factor=0.1):
    """A fake _seg: A_V = cost_by_pair[frozenset(names)] or default_factor·ly."""
    def _fake(a, b, map_sel, step_pc):
        ly = math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2
                       + (a["z"] - b["z"]) ** 2)
        av = cost_by_pair.get(frozenset({a["name"], b["name"]}), default_factor * ly)
        return {"a_v": av, "a_v_lo": max(0.0, av * 0.9), "a_v_hi": av * 1.1,
                "covered": True}
    return _fake


class _DustRoutingBase(unittest.TestCase):
    """Seeded offline star_systems DB + mocked dust availability/preflight."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()
        # Dust extra + maps "available" (preflight passes); per-leg cost is mocked.
        self._patches = [
            mock.patch.object(dust, "_dustmaps_available", lambda: True),
            mock.patch.object(dust, "_load_map", lambda mk: ("FAKE", None)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
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


class JumpRouteDustTest(_DustRoutingBase):

    def _seed_detour(self):
        # Direct corridor M (6,0,0) is dusty; detour N (6,5,0) is clear; D at (12,0,0).
        self._seed_xyz("M", 6.0, 0.0, 0.0)
        self._seed_xyz("N", 6.0, 5.0, 0.0)
        self._seed_xyz("D", 12.0, 0.0, 0.0)

    def test_least_dust_detours_around_corridor(self):
        self._seed_detour()
        cost = {frozenset({"Sol", "M"}): 1.0, frozenset({"M", "D"}): 1.0,
                frozenset({"Sol", "N"}): 0.2, frozenset({"N", "D"}): 0.2}
        with mock.patch.object(dr, "_seg", _seg_factory(cost)):
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                           optimize="distance", map_sel="auto")
        self.assertNotIn("error", r)
        self.assertTrue(r["reachable"])
        self.assertEqual(r["weight"], "dust")
        hops = [leg["to"] for leg in r["route"]]
        self.assertEqual(hops, ["N", "D"])           # dust-optimal detours via N
        self.assertAlmostEqual(r["total_av"], 0.4, places=6)
        # distance-optimal (Sol→M→D, 12 ly) carries 2.0 mag of dust.
        self.assertAlmostEqual(r["distance_optimal_ly"], 12.0, places=4)
        self.assertAlmostEqual(r["distance_optimal_av"], 2.0, places=6)
        self.assertAlmostEqual(r["saved_av"], 1.6, places=6)
        self.assertGreater(r["extra_ly"], 0.0)       # the detour is longer
        # per-leg dust fields present.
        self.assertIn("a_v", r["route"][0])
        self.assertIn("cumulative_av", r["route"][0])

    def test_uniform_dust_coincides_with_distance(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory({})):  # A_V = 0.1·ly
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                           optimize="distance", map_sel="auto")
        hops = [leg["to"] for leg in r["route"]]
        self.assertEqual(hops, ["M", "D"])            # least dust == least ly
        self.assertAlmostEqual(r["saved_av"], 0.0, places=6)
        self.assertAlmostEqual(r["extra_ly"], 0.0, places=4)

    def test_unreachable_is_clean_result(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=3.0,
                                           optimize="distance", map_sel="auto")
        self.assertFalse(r["reachable"])
        self.assertEqual(r["route"], [])
        self.assertEqual(r["unreachable_leg"], {"from": "Sol", "to": "D"})

    def test_via_routes_through_the_waypoint_under_dust(self):
        # N is the clear detour, M the dusty direct corridor. Forcing --via M
        # must put M on the route even though the dust optimum avoids it.
        self._seed_detour()
        cost = {frozenset({"Sol", "M"}): 1.0, frozenset({"M", "D"}): 1.0,
                frozenset({"Sol", "N"}): 0.2, frozenset({"N", "D"}): 0.2}
        with mock.patch.object(dr, "_seg", _seg_factory(cost)):
            free = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                              optimize="distance", map_sel="auto")
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                           optimize="distance", map_sel="auto",
                                           via=["M"])
        self.assertEqual([leg["to"] for leg in free["route"]], ["N", "D"])
        self.assertTrue(r["reachable"])
        self.assertEqual(r["via"], ["M"])
        # The least-A_V way to visit M is out via the clear N and back (0.2+0.5
        # each way = 1.4) rather than the dusty direct corridor (2.0) — so the
        # route legitimately RE-VISITS N. That is the documented waypoint
        # behaviour, not a bug.
        self.assertEqual([leg["to"] for leg in r["route"]], ["N", "M", "N", "D"])
        self.assertEqual([leg["to"] for leg in r["route"] if leg["waypoint"]], ["M"])
        self.assertAlmostEqual(r["total_av"], 1.4, places=6)
        # via_legs carry A_V as well as ly on the dust fork.
        self.assertAlmostEqual(sum(l["a_v"] for l in r["via_legs"]),
                               r["total_av"], places=6)

    def test_via_comparison_is_like_for_like(self):
        # The dref bug: without threading `via`, extra_ly/saved_av would compare
        # a waypoint-CONSTRAINED dust route against an UNCONSTRAINED distance
        # one. --via N discriminates: the unconstrained distance route is
        # Sol→M→D (12.0 ly), the N-constrained one is Sol→N→D (~15.6 ly).
        self._seed_detour()
        cost = {frozenset({"Sol", "M"}): 1.0, frozenset({"M", "D"}): 1.0,
                frozenset({"Sol", "N"}): 0.2, frozenset({"N", "D"}): 0.2}
        with mock.patch.object(dr, "_seg", _seg_factory(cost)):
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                           optimize="distance", map_sel="auto",
                                           via=["N"])
        unconstrained = calc.compute_jump_route("Sol", "D", 9.0, "distance")
        constrained = calc.compute_jump_route("Sol", "D", 9.0, "distance",
                                              via=["N"])
        self.assertAlmostEqual(unconstrained["total_ly"], 12.0, places=4)
        self.assertGreater(constrained["total_ly"], 15.0)
        # The comparison must be against the CONSTRAINED route.
        self.assertAlmostEqual(r["distance_optimal_ly"], constrained["total_ly"],
                               places=6)
        self.assertNotAlmostEqual(r["distance_optimal_ly"],
                                  unconstrained["total_ly"], places=3)
        # Both routes are then the same one, so the deltas are honestly zero —
        # with the unconstrained reference they would have been ~3.6 / ~1.6.
        self.assertAlmostEqual(r["extra_ly"], 0.0, places=6)
        self.assertAlmostEqual(r["saved_av"], 0.0, places=6)

    def test_via_unreachable_names_the_leg(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=3.0,
                                           optimize="distance", map_sel="auto",
                                           via=["M"])
        self.assertFalse(r["reachable"])
        self.assertEqual(r["unreachable_leg"], {"from": "Sol", "to": "M"})
        self.assertEqual([s["name"] for s in r["stars"]], ["Sol", "M", "D"])

    def test_via_validation_matches_the_plain_planner(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            over = dr.compute_jump_route_dust("Sol", "D", 9.0, map_sel="auto",
                                              via=[f"W{i}" for i in range(9)])
            dupe = dr.compute_jump_route_dust("Sol", "D", 9.0, map_sel="auto",
                                              via=["M", "m"])
            same = dr.compute_jump_route_blend("Sol", "D", 9.0, map_sel="auto",
                                               via=["D"])
        self.assertEqual(over["error"], "At most 8 waypoints.")
        self.assertIn("waypoint 1", dupe["error"])
        self.assertIn("destination", same["error"])

    def test_via_keys_present_on_both_forks(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            dust_r = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=9.0,
                                                optimize="distance", map_sel="auto")
            blend_r = dr.compute_jump_route_blend("Sol", "D", max_jump_ly=9.0,
                                                  optimize="distance", map_sel="auto")
            unreach = dr.compute_jump_route_dust("Sol", "D", max_jump_ly=3.0,
                                                 optimize="distance", map_sel="auto")
        plain = calc.compute_jump_route("Sol", "D", 9.0, "distance")
        for r in (dust_r, blend_r, unreach):
            self.assertEqual(r["via"], [])
            self.assertEqual(r["via_legs"], [])
            self.assertIn("unreachable_leg", r)
            for row in r["route"]:
                self.assertFalse(row["waypoint"])
        self.assertIsNone(dust_r["unreachable_leg"])
        # Every via-related key on the plain path exists on the forks too.
        for k in ("via", "via_legs", "unreachable_leg"):
            self.assertIn(k, dust_r)
            self.assertIn(k, blend_r)
        self.assertEqual(set(plain["route"][0]) - set(dust_r["route"][0]), set())


class JumpRouteBlendTest(_DustRoutingBase):
    """C11 (Phase AD) — the α·distance + β·A_V blended route."""

    def _seed_detour(self):
        self._seed_xyz("M", 6.0, 0.0, 0.0)          # dusty direct corridor
        self._seed_xyz("N", 6.0, 5.0, 0.0)          # clean detour
        self._seed_xyz("D", 12.0, 0.0, 0.0)

    _COST = {frozenset({"Sol", "M"}): 1.0, frozenset({"M", "D"}): 1.0,
             frozenset({"Sol", "N"}): 0.2, frozenset({"N", "D"}): 0.2}

    def test_beta_zero_reproduces_distance_route(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory(self._COST)):
            b = dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=1.0, beta=0.0, map_sel="auto")
            dist = calc.compute_jump_route("Sol", "D", 9.0, "distance")
        self.assertEqual(b["weight"], "blend")
        self.assertEqual(b["alpha"], 1.0)
        self.assertEqual(b["beta"], 0.0)
        b_hops = [leg["to"] for leg in b["route"]]
        d_hops = [leg["to"] for leg in dist["route"]]
        self.assertEqual(b_hops, d_hops)             # β=0 → distance-optimal path
        self.assertEqual(b_hops, ["M", "D"])
        self.assertAlmostEqual(b["total_ly"], dist["total_ly"], places=4)
        # blended cost = α·ly + β·A_V (β=0 → just ly)
        self.assertAlmostEqual(b["total_blend_cost"], b["total_ly"], places=6)

    def test_alpha_zero_reproduces_dust_route(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory(self._COST)):
            b = dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=0.0, beta=1.0, map_sel="auto")
            dust_r = dr.compute_jump_route_dust("Sol", "D", 9.0, "distance", map_sel="auto")
        b_hops = [leg["to"] for leg in b["route"]]
        self.assertEqual(b_hops, [leg["to"] for leg in dust_r["route"]])   # α=0 → least-dust path
        self.assertEqual(b_hops, ["N", "D"])
        self.assertAlmostEqual(b["total_av"], dust_r["total_av"], places=6)
        self.assertAlmostEqual(b["total_blend_cost"], b["total_av"], places=6)

    def test_beta_flips_route_between_the_two(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory(self._COST)):
            low = dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=1.0, beta=1.0, map_sel="auto")
            high = dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=1.0, beta=100.0, map_sel="auto")
        # small β → distance corridor; large β → dust detour (the blend spans the two)
        self.assertEqual([leg["to"] for leg in low["route"]], ["M", "D"])
        self.assertEqual([leg["to"] for leg in high["route"]], ["N", "D"])
        # blended cost self-consistency: α·total_ly + β·total_av
        self.assertAlmostEqual(high["total_blend_cost"],
                               1.0 * high["total_ly"] + 100.0 * high["total_av"], places=4)
        # a compromise never beats either pure optimum in its own metric
        self.assertGreaterEqual(high["total_ly"], low["total_ly"] - 1e-9)

    def test_validation_matrix(self):
        self._seed_detour()
        with mock.patch.object(dr, "_seg", _seg_factory(self._COST)):
            self.assertIn("error", dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=-1, beta=1))
            self.assertIn("error", dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=1, beta=-1))
            self.assertIn("error", dr.compute_jump_route_blend("Sol", "D", 9.0, alpha=0, beta=0))
            self.assertIn("error", dr.compute_jump_route_blend("Sol", "D", 0.0))   # bad max jump


class OtherPlannersDustTest(_DustRoutingBase):

    def test_multi_stop_ordered(self):
        self._seed_xyz("A", 4.0, 0.0, 0.0)
        self._seed_xyz("B", 8.0, 0.0, 0.0)
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            r = dr.compute_multi_stop_dust(["Sol", "A", "B"], 0.01, False, map_sel="auto")
        self.assertNotIn("error", r)
        self.assertEqual(len(r["legs"]), 2)
        self.assertIn("a_v", r["legs"][0])
        self.assertIn("cumulative_av", r["legs"][1])
        # fixed order → distance-optimal == this route.
        self.assertEqual(r["extra_ly"], 0.0)
        self.assertEqual(r["saved_av"], 0.0)
        self.assertAlmostEqual(r["total_av"], r["distance_optimal_av"], places=6)

    def test_trade_route_mst_uses_av_edges(self):
        self._seed_xyz("A", 4.0, 0.0, 0.0)
        self._seed_xyz("B", 8.0, 0.0, 0.0)
        # B–A is geometrically short but dusty; Sol–B is long but clean → MST
        # should prefer the low-A_V edges.
        cost = {frozenset({"A", "B"}): 5.0, frozenset({"Sol", "A"}): 0.1,
                frozenset({"Sol", "B"}): 0.2}
        with mock.patch.object(dr, "_seg", _seg_factory(cost)):
            r = dr.compute_trade_route_dust(["Sol", "A", "B"], map_sel="auto")
        self.assertEqual(len(r["edges"]), 2)          # N-1 edges
        pairs = {frozenset({e["from"], e["to"]}) for e in r["edges"]}
        self.assertEqual(pairs, {frozenset({"Sol", "A"}), frozenset({"Sol", "B"})})
        self.assertAlmostEqual(r["total_av"], 0.3, places=6)
        self.assertIn("distance_optimal_av", r)

    def test_nearest_neighbor_picks_least_dust(self):
        self._seed_xyz("CLOSE", 3.0, 0.0, 0.0)      # nearest by ly, but dusty
        self._seed_xyz("FAR", 5.0, 0.0, 0.0)        # farther, but clean
        cost = {frozenset({"Sol", "CLOSE"}): 2.0, frozenset({"Sol", "FAR"}): 0.1}
        with mock.patch.object(dr, "_seg", _seg_factory(cost)):
            r = dr.compute_nearest_neighbor_dust("Sol", 1, 8.0, map_sel="auto")
        self.assertEqual(r["chain"][0]["star_name"], "FAR")  # least dust, not least ly
        self.assertIn("a_v_from_prev", r["chain"][0])

    def test_optimal_tour_shape(self):
        self._seed_xyz("A", 4.0, 0.0, 0.0)
        self._seed_xyz("B", 8.0, 0.0, 0.0)
        with mock.patch.object(dr, "_seg", _seg_factory({})):
            r = dr.compute_optimal_tour_dust(["Sol", "A", "B"], 0.01, False, map_sel="auto")
        self.assertNotIn("error", r)
        self.assertIn("a_v", r["legs"][0])
        self.assertIn("distance_optimal_av", r)
        self.assertIn("saved_av", r)


class DustRoutingIntegrationWiringTest(_DustRoutingBase):
    """End-to-end through the real _seg → integrate_segment_av with a mocked map
    query (constant density). Constant density ⇒ A_V ∝ ly ⇒ dust == distance."""

    def test_constant_density_av_proportional_to_ly(self):
        self._seed_xyz("A", 4.0, 0.0, 0.0)
        self._seed_xyz("B", 8.0, 0.0, 0.0)

        def _fake_query(mk, q, coords):
            n = len(coords)
            return np.full(n, 10.0), np.full(n, 1.0)   # Leike-like constant density

        with mock.patch.object(dust, "_query_native", _fake_query):
            r = dr.compute_multi_stop_dust(["Sol", "A", "B"], 0.01, False,
                                           map_sel="near-field")
        self.assertNotIn("error", r)
        # both legs are 4 ly with identical density → identical A_V.
        self.assertAlmostEqual(r["legs"][0]["a_v"], r["legs"][1]["a_v"], places=6)
        self.assertGreater(r["legs"][0]["a_v"], 0.0)


class DustRoutingPreflightTest(unittest.TestCase):

    def test_extra_missing(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: False):
            r = dr.compute_jump_route_dust("Sol", "Sirius", 5.0, map_sel="auto")
        self.assertIn("error", r)
        self.assertIn("dust", r["error"].lower())

    def test_bad_map(self):
        with mock.patch.object(dust, "_dustmaps_available", lambda: True):
            r = dr.compute_trade_route_dust(["Sol", "Sirius"], map_sel="bogus")
        self.assertIn("error", r)

    def test_subprocess_weight_argparse(self):
        # bad --weight value → argparse exit 2 (rejected before any DB access).
        code, _, _ = run_query_inproc("jump-route", "--origin", "Sol",
                                      "--destination", "Sirius", "--max-jump", "5",
                                      "--weight", "bogus")
        self.assertEqual(code, 2)


class WeightDistanceDelegationTest(_DustRoutingBase):
    """--weight distance must be the unchanged calculators path (delegation)."""

    def test_jump_route_distance_matches_calculators(self):
        self._seed_xyz("M", 6.0, 0.0, 0.0)
        self._seed_xyz("D", 12.0, 0.0, 0.0)
        direct = calc.compute_jump_route("Sol", "D", 9.0, "distance")
        # The query handler routes weight=distance → calculators; here we assert the
        # calculators result itself is untouched (no dust keys).
        self.assertNotIn("total_av", direct)
        self.assertNotIn("weight", direct)
        self.assertTrue(direct["reachable"])


if __name__ == "__main__":
    unittest.main()
