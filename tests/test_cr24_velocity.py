# tests/test_cr24_velocity.py — CR-24.1: the SIMBAD velocity resolver (PM + parallax + RV → heliocentric Galactic
# UVW), the RV gate, the sky-plane lower bound, whose record (a letterless head's A record; the ⚑1 primary-RV
# fallback), and the CR-19 discipline + hooks. Offline: the two CR-24 SIMBAD seams are stubbed from reference rows
# captured live (tests/fixtures/cr24_simbad_velocity_rows.json).

import json
import math
import os
import unittest
from unittest import mock

import pytest

from core import ism_velocity as iv
from core import ism_velocity_tables as ivt
from core import shared

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "cr24_simbad_velocity_rows.json")
with open(_FIX, encoding="utf-8") as _fh:
    ROWS = {shared.collapse_ws(k): v for k, v in json.load(_fh).items()}

# CR-26's identity resolver (astroquery query_object) normalises spacing; the stub maps each A candidate as live
# SIMBAD does (session 58 / CP0): a distinct A record, the head's own record, or answered-empty.
IDENT = {"* alf Cen A": "* alf Cen A", "* 70 Oph A": "*  70 Oph A", "* alf CMa A": "* alf CMa",
         "* alf CMi A": "* alf CMi", "V* EZ Aqr A": None}


def velocity_seam(main_id):
    r = ROWS.get(shared.collapse_ws(main_id))
    return (dict(r) if r else None), None


def identity_seam(ident):
    mid = IDENT.get(ident)                    # any other A candidate: SIMBAD answers "no such object"
    return ({"main_id": mid} if mid else None), None


def seams():
    return mock.patch.multiple(iv, _velocity_seam=velocity_seam, _identity_seam=identity_seam)


def _lic(vel):
    return iv.v_ism_from(vel, "LIC")


@pytest.mark.cr24_velocity
class VelocityMathTest(unittest.TestCase):
    def test_frame_is_heliocentric_galactic_not_lsr(self):
        # zero PM + zero RV → exactly zero heliocentric velocity (an LSR frame would add the solar motion)
        u, v, w = iv.space_velocity(10.0, 20.0, 100.0, 0.0, 0.0, 0.0)
        self.assertLess(abs(u) + abs(v) + abs(w), 1e-9)
        # a pure RV toward the Galactic centre (l=0, b=0 → RA 266.405, Dec −28.936) is +U
        u, v, w = iv.space_velocity(266.40499, -28.93617, 100.0, 0.0, 0.0, 10.0)
        self.assertAlmostEqual(u, 10.0, places=3)

    def test_a2_reference_uvw(self):
        with seams():
            b = iv.lookup_velocity("NAME Barnard's star")
            k = iv.lookup_velocity("HD 33793")
            e = iv.lookup_velocity("V* EV Lac")
        for vel, uvw, tot, der in ((b, (-140.95, 5.14, 18.56), 142.26, 120.65),
                                   (k, (19.84, -288.05, -52.52), 293.47, 292.23),
                                   (e, (19.77, 3.60, -1.71), None, 43.43)):
            sv = vel["space_velocity"]
            self.assertEqual((vel["provenance"], sv["rv_source"], sv["rv_used"]), ("uvw", "own", True))
            for got, want in zip((sv["U"], sv["V"], sv["W"]), uvw):
                self.assertAlmostEqual(got, want, delta=1.0)
            if tot:
                self.assertAlmostEqual(sv["total"], tot, delta=1.0)
            self.assertAlmostEqual(_lic(vel)[0], der, delta=1.0)
            self.assertEqual(sv["convention"], iv.CONVENTION)

    def test_gate_grade_and_floor(self):
        with seams():
            ez = iv.lookup_velocity("V* EZ Aqr")
            b70 = iv.lookup_velocity("*  70 Oph B")
            gj860b = iv.lookup_velocity("HD 239960B")
        self.assertEqual(ez["provenance"], "tangential_lower_bound")
        self.assertEqual((ez["space_velocity"]["rv_used"], ez["space_velocity"]["rv_source"]), (False, None))
        self.assertIn(iv.NOTE_RV_GRADE.format(rv=6824.7, g="D"), ez["notes"])
        f, prov = _lic(ez)
        self.assertEqual(prov, "derived_tangential_lower_bound")
        self.assertAlmostEqual(f, 34.94, delta=0.05)
        # the sky-plane projection, not the naive |v★_t − v_cloud|
        self.assertAlmostEqual(_lic(b70)[0], 33.43, delta=0.05)
        naive = math.dist(b70["v0"], ivt.cloud_vector("LIC"))
        self.assertAlmostEqual(naive, 40.04, delta=0.05)
        self.assertAlmostEqual(_lic(gj860b)[0], 45.0, delta=1.0)

    def test_ceiling_and_null_grade_and_rv0_ceiling(self):
        row = dict(ROWS[shared.collapse_ws("* sig Dra")])
        self.assertTrue(iv.resolve_velocity(row)["space_velocity"]["rv_used"])
        hi = iv.resolve_velocity(dict(row, rvz_radvel=5000.0, rvz_qual="A"))
        self.assertEqual(hi["provenance"], "tangential_lower_bound")
        self.assertTrue(any("above 1000, not used" in n for n in hi["notes"]))
        self.assertAlmostEqual(_lic(hi)[0], 67.47, delta=0.1)          # σ Dra's floor (A3 hook case)
        ng = iv.resolve_velocity(dict(row, rvz_qual=None))
        self.assertTrue(ng["space_velocity"]["rv_used"])                # F3: a null grade passes
        self.assertIn(iv.NOTE_RV_NO_GRADE.format(rv=26.734), ng["notes"])
        fast = iv.resolve_velocity(dict(row, pmra=5e5, pmdec=0.0, plx_value=50.0))
        self.assertEqual(fast["provenance"], "unavailable")             # F4: RV-0 speed > 1000
        self.assertTrue(any("RV 0" in n for n in fast["notes"]))

    def test_f4_floor_at_the_ceiling_is_unavailable_with_no_fallback(self):
        """F4 (WB MSG 326): a sky-plane floor ≥ 1000 against the cloud in use → unavailable; no other derive."""
        row = dict(ROWS[shared.collapse_ws("* sig Dra")], rvz_qual="E")
        vel = iv.resolve_velocity(row)
        vel["v0"] = (990.0, 0.0, 0.0)                      # a floor ≥ 1000 against Aql (V0 58.6), < 1000 vs LIC
        vel["los"] = (0.0, 0.0, 1.0)
        f_aql = iv.sky_plane_floor(vel["v0"], iv.ivt.cloud_vector("Aql"), vel["los"])
        self.assertGreaterEqual(f_aql, 1000.0)
        vres = iv.resolve_v_ism(path="star", vel=vel, cloud="Aql")
        self.assertEqual((vel["provenance"], vel["space_velocity"]), ("unavailable", None))
        self.assertEqual((vres["v_ism_provenance"], vres["v_cloud_used"]), ("assumed", None))   # not the LIC derive
        self.assertTrue(any("above 1000" in n for n in vres["notes"]))

    def test_unavailable_rules(self):
        row = dict(ROWS[shared.collapse_ws("* sig Dra")])
        for bad in ({"plx_value": None}, {"plx_value": -1.0}, {"plx_value": 0.0}, {"pmra": None}):
            with self.subTest(bad=bad):
                v = iv.resolve_velocity(dict(row, **bad))
                self.assertEqual((v["provenance"], v["space_velocity"]), ("unavailable", None))
                self.assertIsNone(_lic(v))


@pytest.mark.cr24_velocity
class WhoseRecordTest(unittest.TestCase):
    def test_letterless_head_takes_its_a_record(self):
        seen = []
        with mock.patch.object(iv, "_velocity_seam", lambda m: (seen.append(m), velocity_seam(m))[1]), \
                mock.patch.object(iv, "_identity_seam", identity_seam):
            v, kind, _ = iv.target_velocity("*  70 Oph")
            a, akind, _ = iv.target_velocity("* alf Cen")
        self.assertEqual(kind, "a")
        self.assertEqual(seen[0], "*  70 Oph A")                        # the RAW resolved id (CP0 F-A1)
        self.assertAlmostEqual(_lic(v)[0], 36.44, delta=0.05)
        self.assertTrue(any("letterless head" in n for n in v["notes"]))
        self.assertEqual(akind, "a")
        self.assertAlmostEqual(_lic(a)[0], 18.16, delta=0.05)

    def test_same_record_empty_and_failed(self):
        with seams():
            s, skind, _ = iv.target_velocity("* alf CMa")
            e, ekind, _ = iv.target_velocity("V* EZ Aqr")
        self.assertEqual((skind, s["record"]), ("same", "* alf CMa"))  # Sirius keeps its own record
        self.assertEqual((ekind, e["record"]), ("empty", "V* EZ Aqr"))
        with mock.patch.object(iv, "_identity_seam", lambda i: (None, "timeout")), \
                mock.patch.object(iv, "_velocity_seam", velocity_seam):
            f, fkind, _ = iv.target_velocity("*  70 Oph")
        self.assertEqual((fkind, f["provenance"], f["status"]), ("failed", "unavailable", "timeout"))
        self.assertTrue(any("is not used" in n for n in f["notes"]))    # Q1: never the system record

    def test_primary_rv_fallback_one_way(self):
        with seams():
            a = iv.lookup_velocity("*  70 Oph A")
            b = iv.lookup_velocity("*  70 Oph B", primary=iv.primary_rv_of(a))
        sv = b["space_velocity"]
        # F-A3: rv / rv_grade echo B's own; rv_used = B's own passed; rv_source primary
        self.assertEqual((b["provenance"], sv["rv"], sv["rv_grade"], sv["rv_used"], sv["rv_source"]),
                         ("uvw", -10.0, "E", False, "primary"))
        self.assertAlmostEqual(_lic(b)[0], 35.62, delta=0.05)
        self.assertTrue(any("*  70 Oph A" in n for n in b["notes"]))
        # a primary with no usable RV lends nothing (D-W3-3 — B takes the floor)
        self.assertIsNone(iv.primary_rv_of(None))
        with seams():
            ez = iv.lookup_velocity("V* EZ Aqr")
        self.assertIsNone(iv.primary_rv_of(ez))

    def test_single_component_and_named_record_only(self):
        with seams():
            v, kind, _ = iv.target_velocity("HD 239960B")              # a lettered id: no A candidate
        self.assertEqual((kind, v["provenance"]), ("own", "tangential_lower_bound"))


@pytest.mark.cr24_velocity
class HooksAndDisciplineTest(unittest.TestCase):
    def test_force_unreachable_and_injection(self):
        with seams(), mock.patch.dict(os.environ, {"SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE": "1"}):
            v = iv.lookup_velocity("* sig Dra")
        self.assertEqual((v["provenance"], v["status"]), ("unavailable", "unreachable"))
        with seams(), mock.patch.dict(os.environ, {"SPACE_APP_CR24_INJECT_RV": "5000"}):
            g = iv.lookup_velocity("* sig Dra")
        self.assertEqual(g["provenance"], "tangential_lower_bound")
        with seams(), mock.patch.dict(os.environ, {"SPACE_APP_CR24_INJECT_RV": "* 70 Oph A=-9:E"}):
            a = iv.lookup_velocity("*  70 Oph A")                        # the key is whitespace-collapsed too
            b = iv.lookup_velocity("*  70 Oph B")
        self.assertEqual((a["space_velocity"]["rv"], a["space_velocity"]["rv_grade"]), (-9.0, "E"))
        self.assertEqual(b["space_velocity"]["rv"], -10.0)             # other records untouched

    def test_failures_are_never_cached(self):
        """T-V6: the velocity family goes through the CR-26 SIMBAD wrapper — an answer is cached, a failure is
        not (catalog_cache.cached stores only a returned value)."""
        from core import catalog_cache, databases
        calls = []

        def tap(adql):
            calls.append(adql)
            if len(calls) <= 2:                                          # both bounded attempts of call 1
                raise ConnectionError("down")
            return [{"main_id": "X", "ra": 1.0, "dec": 1.0, "pmra": 1.0, "pmdec": 1.0, "plx_value": 10.0,
                     "rvz_radvel": 1.0, "rvz_qual": "A"}]
        with mock.patch.object(databases, "_simbad_cr26_tap", tap), \
                mock.patch.dict(os.environ, {"SPACE_APP_CATALOG_CACHE": "1"}), \
                mock.patch.object(databases, "_SIMBAD_RETRY_BACKOFF", 0.0):
            databases._simbad_cr26_down.clear()
            r1 = databases.simbad_velocity("X-cache-test", family="velocity_t")
            r2 = databases.simbad_velocity("X-cache-test", family="velocity_t")
            r3 = databases.simbad_velocity("X-cache-test", family="velocity_t")
        self.assertEqual(r1, (None, "unreachable"))
        self.assertEqual(r2[0]["main_id"], "X")                         # the failure was not cached → re-asked
        self.assertEqual(r3, r2)
        self.assertEqual(len(calls), 3)                                 # r3 is the cached answer
        databases._simbad_cr26_down.clear()


if __name__ == "__main__":
    unittest.main()
