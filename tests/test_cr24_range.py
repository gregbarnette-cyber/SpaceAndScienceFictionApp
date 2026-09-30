# tests/test_cr24_range.py — CR-24.2 DQ2 / DQ3 and the zone lower bound: the exact range evaluator (extremes at the
# route boundaries), the O-2 field semantics, D-C3's per-edge band, D-G2-1's lower edge, D-W3-1 / WB MSG 328's
# provisional closed form, and the DQ2 cloud-set range + branch rule. Pure `[hand]` anchors (the contract's inputs;
# the rates / standoffs from the live CR-26 outputs the spec quotes). Offline.

import json
import os
import unittest

import pytest

from core import exclusion_wall as ew
from core import ism_velocity as iv
from core import shared

_WSUN = ew._WDOT_SOLAR          # 2e-14 M☉/yr = 1 Ṁ☉


def _inputs(wdot, v_ism, **kw):
    d = {"wdot": wdot, "v_wind": 400.0, "t_phase": None, "v_ism": v_ism, "c_ms": 20.0, "n_cloud": 0.1,
         "f_shock": 1.5, "m_shock_min": 1.5, "c_ms_band": ew._C_MS_BAND}
    d.update(kw)
    return d


def _lb_vres(floor):
    return {"mode": "lower_bound", "v_ism_kms": floor, "v_ism_provenance": "derived_tangential_lower_bound",
            "cloud_points": None, "derived_xcheck": None}


class Ez_AqrLowerBoundTest(unittest.TestCase):
    """A3 — EZ Aqr on the --star path: floor 34.94 (RV gated), rate 0.1924 Ṁ⊙ (stored wall 2.6317611601220543)."""
    WDOT = (2.6317611601220543 / 6.0) ** 2 * _WSUN
    REX, FLOOR = 23.42, 34.94

    def test_reported_wall_range_band_and_reasons(self):
        inp = _inputs(self.WDOT, self.FLOOR)
        floor_wall = iv.wall_at(inp, self.FLOOR, self.REX)
        w, extra, band, notes = iv.apply_v_ism(floor_wall, inp, self.REX, None, _lb_vres(self.FLOOR),
                                               band_rate=0.1924 * _WSUN,
                                               band_dex=[__import__("math").log10(0.02386 / 0.1924),
                                                         __import__("math").log10(3.349 / 0.1924)],
)
        self.assertEqual(w["wall_route"], "wind_term")
        self.assertAlmostEqual(w["wall_au"], 2.632, delta=0.01 * 2.632)
        self.assertAlmostEqual(w["wall_band_au"][0], 1.755, delta=0.01 * 1.755)   # the band AT the reported wall
        self.assertAlmostEqual(w["wall_band_au"][1], 3.509, delta=0.01 * 3.509)
        self.assertAlmostEqual(w["r_ap_au"], 39.2, delta=0.1)                     # O-2: r_ap at the floor
        self.assertAlmostEqual(extra["wall_range_vism_au"][0], 1.369, delta=0.03 * 1.369)
        self.assertAlmostEqual(extra["wall_range_vism_au"][1], 2.632, delta=0.03 * 2.632)
        self.assertTrue(extra["wall_route_provisional"])
        self.assertEqual(extra["verdict_marginal_reasons"], ["lower_bound_provisional"])   # floor triggers only
        self.assertTrue(w["verdict_marginal"])
        self.assertAlmostEqual(band["wall_band_wind_au"][0], 0.618, delta=0.01 * 0.618)
        self.assertAlmostEqual(band["wall_band_wind_au"][1], 14.639, delta=0.01 * 14.639)
        self.assertNotIn("wall_band_wind_routes", band)
        self.assertTrue(any("the route is provisional" in n for n in notes))
        self.assertTrue(any("V_max = 1000" in n for n in notes))                 # D-G2-1: the capped wall

    def test_vmax_390_variant(self):
        inp = _inputs(self.WDOT, self.FLOOR)
        fn = (lambda v: iv.wall_at(inp, v, self.REX))
        _hi, lo = iv.extremes(fn, lambda w: w["wall_au"], self.FLOOR, 390.0, iv.breakpoints(inp, self.WDOT, self.REX))
        self.assertAlmostEqual(lo[0], 1.415, delta=0.005)                         # just under the burial speed 87.7
        self.assertAlmostEqual(iv.burial_speed(inp, self.WDOT, self.REX), 87.7, delta=0.1)


class SigDraHookTest(unittest.TestCase):
    """A3's σ Dra hook case (D-C3 single star): floor 67.47, point 1.466 Ṁ⊙, the band edges' rates."""

    def test_band_edges_at_their_largest(self):
        rex, floor = 44.06, 67.47
        inp = _inputs(1.466 * _WSUN, floor)
        lb = iv.lower_bound_wall(inp, rex, None, floor)
        self.assertAlmostEqual(lb["wall"]["wall_au"], 7.265, delta=0.01 * 7.265)
        self.assertEqual(lb["wall"]["wall_route"], "wind_term")
        (lo_v, lo_r), (hi_v, hi_r) = iv.lower_bound_band_edges(inp, rex, None, floor, (1.792 / 4) ** 2 * _WSUN,
                                                               4.75068e-13)
        self.assertAlmostEqual(lo_v, 1.792, delta=0.01 * 1.792)
        self.assertEqual(lo_r, "wind_term")
        self.assertAlmostEqual(hi_v, 29.37, delta=0.01 * 29.37)                   # r_ex/f at the capped peak
        self.assertEqual(hi_r, "capped_astropause")


class ZoneLowerBoundTest(unittest.TestCase):
    """A6 by construction (D-W2-2): the GJ 65 pair's summed 7.614e-15 against the comparator 20.509."""
    REX = 20.509

    def _zone(self, floor):
        inp = _inputs(7.614e-15, floor)
        lb = iv.lower_bound_wall(inp, self.REX, None, floor)
        edges = iv.lower_bound_band_edges(inp, self.REX, None, floor, 0.02177 * _WSUN, 1.3316e-13)
        return lb, edges

    def test_floor_34_9(self):
        lb, ((lo_v, lo_r), (hi_v, hi_r)) = self._zone(34.9)
        self.assertAlmostEqual(lb["wall"]["wall_au"], 3.702, delta=0.001 * 3.702)
        self.assertEqual(lb["wall"]["wall_route"], "wind_term")
        self.assertAlmostEqual(lb["wall"]["wall_band_au"][0], 2.468, delta=0.01 * 2.468)
        self.assertAlmostEqual(lb["wall"]["wall_band_au"][1], 4.936, delta=0.01 * 4.936)
        self.assertAlmostEqual(lb["range"][0], 1.906, delta=0.005 * 1.906)       # ±0.5 %
        self.assertAlmostEqual(lb["range"][1], 3.702, delta=0.005 * 3.702)
        self.assertEqual(lb["lower_kind"], "just_under_burial")
        self.assertTrue(lb["provisional"])
        self.assertAlmostEqual(lo_v, 0.590, delta=0.01 * 0.590)
        self.assertEqual((lo_r, hi_r), ("wind_term", "bow_shock"))
        self.assertAlmostEqual(hi_v, 14.542, delta=0.01 * 14.542)

    def test_floor_45_capped_peak(self):
        lb, ((lo_v, _lo_r), (hi_v, hi_r)) = self._zone(45.0)
        self.assertAlmostEqual(lb["range"][0], 1.906, delta=0.005 * 1.906)
        self.assertTrue(lb["provisional"])
        self.assertAlmostEqual(hi_v, 13.673, delta=0.01 * 13.673)
        self.assertEqual(hi_r, "capped_astropause")

    def test_floor_200_not_provisional(self):
        lb, _edges = self._zone(200.0)
        self.assertAlmostEqual(lb["wall"]["wall_au"], 3.702, delta=0.001 * 3.702)
        self.assertAlmostEqual(lb["range"][0], 1.925, delta=0.005 * 1.925)
        self.assertEqual(lb["lower_kind"], "at_vmax")
        self.assertFalse(lb["provisional"])                                        # only the cap changes the route

    def test_dense_grid_cross_check(self):
        """The exact breakpoint evaluation equals (≥) a dense grid everywhere (a missed breakpoint would show)."""
        for floor in (34.9, 45.0, 200.0):
            inp = _inputs(7.614e-15, floor)
            lb = iv.lower_bound_wall(inp, self.REX, None, floor)
            n = 20000
            vals = [iv.wall_at(inp, floor + (1000.0 - floor) * i / n, self.REX)["wall_au"] for i in range(n + 1)]
            self.assertGreaterEqual(lb["range"][1] + 1e-12, max(vals))
            self.assertLessEqual(lb["range"][0] - 1e-12, min(vals))
            self.assertLess(min(vals) - lb["range"][0], 0.01)


class ProvisionalClosedFormTest(unittest.TestCase):
    def test_capped_bow_shock_still_provisional(self):
        """F2: a bow shock capped everywhere in the interval still makes the route provisional (closed form)."""
        inp = _inputs(4 * _WSUN, 800.0)
        self.assertTrue(iv.provisional(inp, 4 * _WSUN, 1.0, 800.0))
        w = iv.wall_at(inp, 900.0, 1.0)
        self.assertEqual((w["wall_route"], w["wall_route_precap"]), ("capped_astropause", "bow_shock"))

    def test_threshold_above_vmax_is_not_provisional(self):
        """WB MSG 328: a supplied M_shock_min·c_ms above 1000 → no bow shock possible → false."""
        inp = _inputs(4 * _WSUN, 50.0, m_shock_min=60.0)
        self.assertGreater(iv.burial_speed(inp, 4 * _WSUN, 1.0), 1200.0)
        self.assertFalse(iv.provisional(inp, 4 * _WSUN, 1.0, 50.0))

    def test_no_standoff(self):
        self.assertFalse(iv.provisional(_inputs(_WSUN, 30.0), _WSUN, None, 30.0))


@pytest.mark.cr24_velocity
class CloudSetRangeTest(unittest.TestCase):
    """DQ2 — the nine-cloud range and the branch rule (A5), from the reference astrometry."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "cr24_simbad_velocity_rows.json"),
                  encoding="utf-8") as fh:
            cls.rows = {shared.collapse_ws(k): v for k, v in json.load(fh).items()}

    def _dq2(self, mid, wdot, rex, v_wind=400.0):
        vel = iv.resolve_velocity(self.rows[shared.collapse_ws(mid)])
        vres = iv.resolve_v_ism(path="star", vel=vel)
        inp = _inputs(wdot, vres["v_ism_kms"], v_wind=v_wind)
        w, extra, _b, notes = iv.apply_v_ism(iv.wall_at(inp, vres["v_ism_kms"], rex), inp, rex, None, vres)
        return vres, w, extra, notes

    def test_sirius_branch_flag(self):
        vres, w, extra, notes = self._dq2("* alf CMa", 1e-14, 63.459, v_wind=700.0)
        self.assertAlmostEqual(vres["v_ism_kms"], 36.5, delta=1.0)
        self.assertAlmostEqual(vres["v_ism_range_kms"][0], 23.9, delta=1.0)
        self.assertAlmostEqual(vres["v_ism_range_kms"][1], 50.1, delta=1.0)
        self.assertAlmostEqual(extra["wall_range_vism_au"][0], 1.949, delta=0.03 * 1.949)
        self.assertAlmostEqual(extra["wall_range_vism_au"][1], 3.207, delta=0.03 * 3.207)
        self.assertEqual(extra["verdict_marginal_reasons"], ["cloud_set_branch"])
        self.assertTrue(any("Blue" in n and "Hyades" in n for n in notes))

    def test_wolf_359_one_branch(self):
        vres, w, extra, notes = self._dq2("Wolf 359", 2.2821967909473893e-15, 18.1297)
        self.assertAlmostEqual(w["wall_au"], 1.268, delta=0.01 * 1.268)
        self.assertAlmostEqual(extra["wall_range_vism_au"][0], 1.204, delta=0.03 * 1.204)
        self.assertAlmostEqual(extra["wall_range_vism_au"][1], 1.398, delta=0.03 * 1.398)
        self.assertEqual(extra["verdict_marginal_reasons"], [])
        self.assertFalse(w["verdict_marginal"])
        self.assertEqual(vres["clic_domain"], "within_7pc")

    def test_ross_248_burial_flip(self):
        vres, w, extra, notes = self._dq2("Ross 248", 3.401576471309428e-15, 21.9402)
        self.assertEqual(w["wall_route"], "wind_term")
        self.assertAlmostEqual(extra["wall_range_vism_au"][0], 1.331, delta=0.03 * 1.331)
        self.assertAlmostEqual(extra["wall_range_vism_au"][1], 2.474, delta=0.03 * 2.474)
        self.assertEqual(extra["verdict_marginal_reasons"], ["apex_near_standoff", "cloud_set_branch"])
        self.assertTrue(any(all(c in n for c in ("Blue", "Eri", "Aur", "Mic")) for n in notes))


if __name__ == "__main__":
    unittest.main()
