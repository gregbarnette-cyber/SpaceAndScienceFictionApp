"""CR-26 — the network layer (core/xray_catalog.py + the CR-26 SIMBAD helpers), every seam mocked
(plan §4, test group 12). No socket is opened: each test patches the seams it exercises."""

import math
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import pytest

from core import catalog_cache
from core import databases
from core import stellar_wind as sw
from core import xray_catalog as xc
from core.stellar_wind import MDOT_SUN

_HOOKS = ("SPACE_APP_XRAY_FORCE_UNREACHABLE", "SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE",
          "SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE", "SPACE_APP_TIC_FORCE_UNREACHABLE",
          "SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE", "SPACE_APP_BLEND_FORCE_UNREACHABLE",
          "SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE", "SPACE_APP_GAIA_FORCE_UNREACHABLE")

_GCNS_COLS = ("gaia_source_id INTEGER, ra REAL, dec REAL, parallax REAL, parallax_error REAL, pmra REAL, "
              "pmdec REAL, phot_g_mean_mag REAL, dist_pc REAL, wd_prob REAL, spectral_type TEXT, star_name TEXT, "
              "gcns_table TEXT, system_id INTEGER")


def make_gcns(rows):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE gcns_stars ({_GCNS_COLS})")
    keys = [c.split()[0] for c in _GCNS_COLS.split(", ")]
    for r in rows:
        con.execute(f"INSERT INTO gcns_stars ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                    [r.get(k) for k in keys])
    con.commit()
    con.close()
    return path


class _Base(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"SPACE_APP_CATALOG_CACHE": "0"})
        self._env.start()
        for h in _HOOKS:
            os.environ.pop(h, None)
        xc.reset_cr26_circuits()
        xc._REACH.clear()
        databases.reset_simbad_cr26_circuit()
        self.addCleanup(self._env.stop)
        self.addCleanup(xc.reset_cr26_circuits)
        self.addCleanup(databases.reset_simbad_cr26_circuit)
        self.addCleanup(xc._REACH.clear)


def _star(ra=100.0, dec=10.0, pmra=0.0, pmdec=0.0, epoch=2016.0, **kw):
    return {"ra": ra, "dec": dec, "pmra": pmra, "pmdec": pmdec, "epoch": epoch, "plx": 100.0, "plx_err": 0.1, **kw}


def _mjd(year):
    return (year - 2000.0) * 365.25 + 51544.5


class _Heasarc:
    """A fake HEASARC seam: table name → rows; records every ADQL."""

    def __init__(self, tables):
        self.tables, self.calls = tables, []

    def __call__(self, adql):
        self.calls.append(adql)
        for t, rows in self.tables.items():
            if f" FROM {t} " in adql:
                if isinstance(rows, Exception):
                    raise rows
                return {"answered": True, "sources": rows}
        return {"answered": True, "sources": []}


@pytest.mark.cr26_network
class LadderMatchingTest(_Base):
    def test_propagation_and_nearest(self):
        # a 1″/yr star: at 1990.8 it sat 25.2″ south of its 2016 position; the 2RXS row there matches
        a = _star(pmdec=1000.0)
        ra_r, dec_r = xc.propagate(100.0, 10.0, 0.0, 1000.0, 2016.0, 1990.8)
        fake = _Heasarc({"rass2rxs": [
            {"name": "far", "ra": ra_r, "dec": dec_r + 50 / 3600, "time": _mjd(1990.8), "onerxs_count_rate": 1.0},
            {"name": "near", "ra": ra_r, "dec": dec_r + 2 / 3600, "time": _mjd(1990.8), "onerxs_count_rate": 0.5}]})
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=10.0):
            rungs = xc.xray_ladder(a)
        r0 = rungs[0]
        self.assertEqual(r0["status"], "detection")
        self.assertEqual(r0["cand"]["source_id"], "near")
        self.assertAlmostEqual(r0["cand"]["separation_arcsec"], 2.0, places=2)
        self.assertEqual(r0["cand"]["rung_label"], "2RXS_1RXS")
        self.assertAlmostEqual(r0["cand"]["f_x"], 0.5 * 6e-12)
        self.assertEqual(rungs[1]["status"], "out_of_footprint")

    def test_widened_prefilter(self):
        # Barnard's star (≈10.4″/yr): the pre-filter cone widens by |μ|·span
        a = _star(pmra=-800.0, pmdec=10360.0)
        fake = _Heasarc({})
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=200.0):
            xc.xray_ladder(a)
        r_2rxs = float(fake.calls[0].rsplit(",", 1)[1].strip(" ))=1"))
        self.assertGreater(r_2rxs * 3600, 60 + 10.3)

    def test_count_rate_and_erass1_and_xmm_conversions(self):
        a = _star()
        fake = _Heasarc({
            "rass2rxs": [{"name": "r", "ra": 100.0, "dec": 10.0, "time": _mjd(1990.8), "count_rate": 1.0,
                          "onerxs_count_rate": None}],
            "erass1main": [{"name": "e", "ra": 100.0, "dec": 10.0, "time": _mjd(2020.2), "b1_flux": 1e-13}],
            "xmmssc": [{"srcid": 7, "name": "x", "ra": 100.0, "dec": 10.0, "time": _mjd(2005), "end_time": _mjd(2015),
                        "ep_1_flux": 1e-14, "ep_2_flux": 2e-14, "ep_3_flux": 3e-14, "ep_det_ml": 40, "sum_flag": 0}]})
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=200.0):
            rungs = xc.xray_ladder(a)
        self.assertEqual(rungs[0]["cand"]["rung_label"], "2RXS")
        self.assertAlmostEqual(rungs[0]["cand"]["f_x"], 10 ** -0.063 * 6e-12)
        self.assertAlmostEqual(rungs[1]["cand"]["f_x"], 1e-13 * 10 ** 0.052)
        self.assertAlmostEqual(rungs[2]["cand"]["f_x"], 6e-14 * 10 ** 0.087)
        self.assertEqual((rungs[2]["cand"]["sum_flag"], rungs[2]["cand"]["det_ml"]), (0, 40))
        # eRASS1 match radius is 15″
        fake.tables["erass1main"][0]["dec"] = 10.0 + 16 / 3600
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=200.0):
            self.assertEqual(xc.xray_ladder(a)[1]["status"], "no_detection")

    def test_xmm_tolerance_grows_with_span(self):
        a = _star(pmra=0.0, pmdec=2000.0)                   # 2″/yr
        mid = 2010.0
        ra_m, dec_m = xc.propagate(100.0, 10.0, 0.0, 2000.0, 2016.0, mid)
        row = {"srcid": 1, "name": "x", "ra": ra_m, "dec": dec_m + 18 / 3600, "time": _mjd(2005), "end_time": _mjd(2015),
               "ep_1_flux": 1e-14, "ep_2_flux": 0, "ep_3_flux": 0, "ep_det_ml": 40, "sum_flag": 0}
        fake = _Heasarc({"xmmssc": [row]})                   # tol = 10 + 2·10/2 = 20″ → matches at 18″
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=10.0):
            self.assertEqual(xc.xray_ladder(a)[2]["status"], "detection")
        row["end_time"] = _mjd(2006)                         # tol ≈ 11″ → no match
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=10.0):
            self.assertEqual(xc.xray_ladder(a)[2]["status"], "no_detection")


@pytest.mark.cr26_network
class HooksAndPlumbingTest(_Base):
    def test_rung_hook_list(self):
        os.environ["SPACE_APP_XRAY_FORCE_UNREACHABLE"] = "2rxs,XMM"
        fake = _Heasarc({})
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=200.0):
            rungs = xc.xray_ladder(_star())
        self.assertEqual([r["status"] for r in rungs], ["unreachable", "no_detection", "unreachable"])
        for v in ("1", "0", "all"):
            os.environ["SPACE_APP_XRAY_FORCE_UNREACHABLE"] = v
            with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=200.0):
                self.assertEqual({r["status"] for r in xc.xray_ladder(_star())}, {"unreachable"}, v)

    def test_retry_once_and_answered_error_not_retried(self):
        calls = []

        def flaky(adql):
            calls.append(1)
            raise ConnectionError("down")
        with mock.patch.object(xc, "_heasarc_tap", flaky), mock.patch.object(xc, "galactic_l", return_value=10.0), \
                mock.patch("core.shared.time.sleep"):
            rungs = xc.xray_ladder(_star())
        self.assertEqual(rungs[0]["status"], "unreachable")
        self.assertEqual(len(calls), 2 * 2)                  # 2RXS + XMM, two attempts each
        calls.clear()

        def answered(adql):
            calls.append(1)
            raise xc._Answered("bad adql")
        with mock.patch.object(xc, "_heasarc_tap", answered), mock.patch.object(xc, "galactic_l", return_value=10.0):
            rungs = xc.xray_ladder(_star())
        self.assertEqual(rungs[0]["status"], "error")
        self.assertEqual(len(calls), 2)                      # one attempt per rung

    def test_breaker_trips_on_timeout(self):
        from core.shared import _WatchdogTimeout
        calls = []

        def slow(adql):
            calls.append(1)
            raise _WatchdogTimeout()
        with mock.patch.object(xc, "_heasarc_tap", slow), mock.patch.object(xc, "galactic_l", return_value=10.0), \
                mock.patch("core.shared._call_with_watchdog", side_effect=lambda fn, timeout: fn()), \
                mock.patch("core.shared.time.sleep"):
            rungs = xc.xray_ladder(_star())
        self.assertEqual([r["status"] for r in rungs], ["timeout", "out_of_footprint", "timeout"])
        self.assertEqual(len(calls), 2)                      # XMM short-circuited by the open breaker

    def test_cache_answered_empty_written_failure_not(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(catalog_cache, "_CACHE_DIR",
                                                                   __import__("pathlib").Path(d)):
            os.environ["SPACE_APP_CATALOG_CACHE"] = "1"
            with mock.patch.object(xc, "_heasarc_tap", _Heasarc({})), \
                    mock.patch.object(xc, "galactic_l", return_value=10.0):
                xc.xray_ladder(_star())
            self.assertEqual(len(os.listdir(d)), 2)          # 2RXS + XMM answered-empty → cached
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
            with mock.patch.object(xc, "_heasarc_tap", side_effect=ConnectionError("x")), \
                    mock.patch.object(xc, "galactic_l", return_value=10.0), mock.patch("core.shared.time.sleep"):
                xc.xray_ladder(_star(ra=101.0))
            self.assertEqual(os.listdir(d), [])

    def test_limit_hook_and_medians(self):
        fake = _Heasarc({"rass2rxs": [{"exposure": 100.0}, {"exposure": 300.0}, {"exposure": 200.0}],
                         "erass1main": [{"b1_exposure": 150.0, "b1_flux": 2e-13, "b1_count_rate": 1.0},
                                        {"b1_exposure": 250.0, "b1_flux": 4e-13, "b1_count_rate": 2.0}]})
        with mock.patch.object(xc, "_heasarc_tap", fake):
            lim = xc.survey_limit(_star(), in_footprint=False)
            self.assertEqual(lim["survey"], "RASS")
            self.assertAlmostEqual(lim["f_limit"], 6.0 / 200.0 * 10 ** -0.063 * 6e-12)
            lim = xc.survey_limit(_star(), in_footprint=True)
            e1 = 6.0 / 200.0 * 2e-13 * 10 ** 0.052
            self.assertEqual(lim["survey"], "RASS" if lim["f_limit"] < e1 else "eRASS1")
            self.assertAlmostEqual(lim["f_limit"], min(e1, 6.0 / 200.0 * 10 ** -0.063 * 6e-12))
        with mock.patch.object(xc, "_heasarc_tap", _Heasarc({})):
            lim = xc.survey_limit(_star(), in_footprint=True)
        self.assertAlmostEqual(lim["f_limit"], 6.0 / 380.15 * 10 ** -0.063 * 6e-12)   # no eRASS1 source → RASS
        os.environ["SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(xc.survey_limit(_star(), True)["status"], "unreachable")


@pytest.mark.cr26_network
class AstrometryTest(_Base):
    def _db(self, rows):
        path = make_gcns(rows)
        self.addCleanup(os.remove, path)
        return path

    def test_gcns_row_first(self):
        db = self._db([{"gaia_source_id": 5, "ra": 1.0, "dec": 2.0, "pmra": 3.0, "pmdec": 4.0, "parallax": 50.0,
                        "parallax_error": 0.1, "phot_g_mean_mag": 9.0, "gcns_table": "main"}])
        a = xc.star_astrometry({"main_id": "X", "gaia_sid": "5"}, db_path=db)
        self.assertEqual((a["ra"], a["epoch"], a["g"], a["status"]), (1.0, 2016.0, 9.0, None))

    def test_gaia_fails_then_simbad(self):
        db = self._db([])
        with mock.patch.object(xc, "_gaia_astrom_seam", return_value={"error": "x", "gaia_bound_reason": "timeout"}), \
                mock.patch.object(databases, "simbad_astrometry", return_value=(
                    {"ra": 5.0, "dec": 6.0, "pmra": 1.0, "pmdec": 1.0, "plx_value": 10.0, "plx_err": 0.5,
                     "g": 8.0, "oid": 42}, None)):
            a = xc.star_astrometry({"main_id": "X", "gaia_sid": "5"}, db_path=db)
        self.assertEqual((a["epoch"], a["g"], a["oid"], a["status"]), (2000.0, 8.0, 42, None))
        self.assertTrue(any("live Gaia DR3 astrometry failed" in n for n in a["notes"]))

    def test_all_failed(self):
        db = self._db([])
        with mock.patch.object(xc, "_gaia_astrom_seam", return_value={"error": "x", "gaia_bound_reason": "timeout"}), \
                mock.patch.object(databases, "simbad_astrometry", return_value=(None, "unreachable")):
            a = xc.star_astrometry({"main_id": "X", "gaia_sid": "5"}, db_path=db)
        self.assertEqual(a["status"], "unreachable")
        os.environ["SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(xc.star_astrometry({"main_id": "X"}, db_path=db)["status"], "unreachable")

    def test_r6_zero_pm(self):
        db = self._db([])
        with mock.patch.object(databases, "simbad_astrometry", return_value=(
                {"ra": 5.0, "dec": 6.0, "pmra": None, "pmdec": None, "plx_value": 10.0, "g": 8.0}, None)):
            a = xc.star_astrometry({"main_id": "X"}, db_path=db)
        self.assertEqual((a["pmra"], a["pmdec"]), (0.0, 0.0))
        self.assertTrue(any("no proper motion" in n for n in a["notes"]))

    def test_h6_g_hook(self):
        # =g fails ONLY the SIMBAD-G fetch: a non-Gaia star keeps its SIMBAD astrometry, G fails
        db = self._db([])
        os.environ["SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE"] = "g"
        with mock.patch.object(databases, "simbad_astrometry", return_value=(
                {"ra": 5.0, "dec": 6.0, "pmra": 1.0, "pmdec": 1.0, "plx_value": 10.0, "g": 12.0}, None)):
            a = xc.star_astrometry({"main_id": "X"}, db_path=db)
        self.assertEqual((a["status"], a["g"], a["g_status"]), (None, None, "unreachable"))
        # …and never blocks the local GCNS step
        db2 = self._db([{"gaia_source_id": 5, "ra": 1.0, "dec": 2.0, "pmra": 3.0, "pmdec": 4.0, "parallax": 50.0,
                         "parallax_error": 0.1, "phot_g_mean_mag": 9.0, "gcns_table": "main"}])
        a = xc.star_astrometry({"main_id": "X", "gaia_sid": "5"}, db_path=db2)
        self.assertEqual((a["status"], a["g"], a["g_status"]), (None, 9.0, None))

    def test_h6_through_the_model(self):
        # XMM is the candidate and the G fetch failed → the XMM rung is failed (never guard-demoted)
        cand = {"f_x": 1e-12, "rung_label": "XMM", "sum_flag": 0, "det_ml": 50}
        rungs = [{"rung": "2RXS", "status": "no_detection", "cand": None},
                 {"rung": "eRASS1", "status": "out_of_footprint", "cand": None},
                 {"rung": "XMM", "status": "detection", "cand": cand}]
        r = sw.resolve_wind_model(sw.StarWindInputs(sp_type="K2V", network=True, d_pc=10.0, rungs=rungs,
                                                    g_status="unreachable"))
        self.assertEqual(r["mass_loss_tier"], "class_default")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])
        self.assertEqual(r["wind_model"]["xray"]["rungs"][2]["status"], "unreachable")
        self.assertNotIn("xmm_guard_demoted", r["wind_model"]["flags"])


@pytest.mark.cr26_network
class BlendTest(_Base):
    T = {"main_id": "* T", "sid": 1, "mass": 0.8, "system_id": None}

    def _run(self, rows, cand=None, *, simbad=None, parents=None, ident=None, d_pc=10.0, a=None):
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        cand = cand or {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0}
        simbad = simbad or {}
        with mock.patch.object(databases, "simbad_astrometry",
                               side_effect=lambda i, family=None: (simbad.get(i), None)
                               if not isinstance(simbad.get(i), str) else (None, simbad[i])), \
                mock.patch.object(databases, "simbad_parent",
                                  side_effect=lambda i, family=None: ((parents or {}).get(i, []), None)), \
                mock.patch.object(xc, "_identity_lookup", side_effect=lambda i: ((ident or {}).get(i), None)), \
                mock.patch.object(xc, "_partner_mass_seam", return_value=(0.7, "catalog", None)), \
                mock.patch.object(xc, "_gaia_radius_seam", return_value={"parameters": {}}), \
                mock.patch.object(xc, "_tic_query", return_value={"answered": True, "sources": []}):
            return xc.blend_partners(a or _star(), cand, d_pc, self.T, None, db_path=db)

    @staticmethod
    def _row(sid, dra=0.0, ddec=0.0, **kw):
        base = {"gaia_source_id": sid, "ra": 100.0 + dra / 3600, "dec": 10.0 + ddec / 3600, "parallax": 100.0,
                "parallax_error": 0.1, "pmra": 0.0, "pmdec": 0.0, "phot_g_mean_mag": 10.0, "dist_pc": 10.0,
                "gcns_table": "main", "star_name": f"S{sid}", "spectral_type": "K5V"}
        base.update(kw)
        return base

    def test_target_removed_and_p_partner(self):
        b = self._run([self._row(1, star_name="* T"), self._row(2, dra=20)])
        self.assertEqual([p["name"] for p in b["partners"]], ["S2"])
        self.assertEqual(b["field_stars"], [])

    def test_field_star(self):
        b = self._run([self._row(1), self._row(3, dra=20, parallax=20.0, pmra=5000.0)])
        self.assertEqual(b["partners"], [])
        self.assertEqual(b["field_stars"], ["S3"])

    def test_main_rows_never_merged(self):
        # L1 (MSG 305): two main-table rows are distinct Gaia sources — a twin under 2″ and a shared
        # cross-matched name (the live HD 281650 pair) both survive as partners
        rows = [self._row(1), self._row(2, dra=20), self._row(3, dra=20.5, phot_g_mean_mag=10.3)]
        self.assertEqual(len(self._run(rows)["partners"]), 2)
        rows = [self._row(1), self._row(2, dra=20, star_name="HD 281650"),
                self._row(3, dra=20.45, star_name="HD 281650", phot_g_mean_mag=10.54)]
        self.assertEqual(len(self._run(rows)["partners"]), 2)

    def test_target_removed_by_sid_not_by_name(self):
        # a companion carrying the target's own cross-matched name is NOT the target (L1 / CP2 finding 1)
        b = self._run([self._row(1, star_name="* T"), self._row(2, dra=1, star_name="* T")])
        self.assertEqual(len(b["partners"]), 1)

    def test_target_missing_copy_removed(self):
        # the 10 Tau case: the target's own missing_10mas copy merges into its main row, then both go
        miss = {"gaia_source_id": None, "ra": 100.0 + 0.5 / 3600, "dec": 10.0, "parallax": 100.0,
                "gcns_table": "missing_10mas", "star_name": "* T", "dist_pc": 10.0}
        b = self._run([self._row(1, star_name="* T"), miss], simbad={"* T": {"pmra": 0.0, "pmdec": 0.0}})
        self.assertEqual((b["partners"], b["field_stars"]), ([], []))

    def test_g13_missing_vs_main(self):
        miss = {"gaia_source_id": None, "ra": 100.0 + 20 / 3600, "dec": 10.0, "parallax": 100.0, "gcns_table": "missing_10mas",
                "star_name": "OTHER NAME", "dist_pc": 10.0}
        rows = [self._row(1), self._row(2, dra=20), miss]
        same = {"OTHER NAME": {"pmra": 0.0, "pmdec": 0.0, "plx_value": 100.0, "plx_err": 0.1, "main_id": "* P"},
                "Gaia DR3 2": {"main_id": "* P"}}
        self.assertEqual(len(self._run(rows, simbad=same)["partners"]), 1)
        diff = dict(same, **{"Gaia DR3 2": {"main_id": "* Q"}})
        self.assertEqual(len(self._run(rows, simbad=diff)["partners"]), 2)
        failed = dict(same, **{"Gaia DR3 2": "timeout"})
        b = self._run(rows, simbad=failed)
        self.assertTrue(b["partial"])                       # a failed G13 lookup → distinct + not_authoritative

    def test_s_by_designation_and_m(self):
        # parallax unusable (no error) → (P) not evaluable; PM equal → (M) passes
        rows = [self._row(1), self._row(2, dra=20, parallax_error=None)]
        b = self._run(rows)
        self.assertEqual(len(b["partners"]), 1)
        self.assertFalse(b["partners"][0]["by_designation"])
        # no PM and no parallax error: only a component-letter designation qualifies it
        rows = [self._row(1), self._row(2, dra=20, parallax_error=None, pmra=None, pmdec=None, star_name="* T B")]
        b = self._run(rows, simbad={"Gaia DR3 2": {"main_id": "* T B"}})
        self.assertTrue(b["partners"][0]["by_designation"])

    def test_s1_system_entry_is_not_a_star(self):
        # MSG 306 S1: a missing_10mas `** …` system entry on one of its own components is dropped
        miss = {"gaia_source_id": None, "ra": 100.0 + 20.1 / 3600, "dec": 10.0, "parallax": 100.0,
                "gcns_table": "missing_10mas", "star_name": "** LDS 823", "dist_pc": 10.0}
        b = self._run([self._row(1), self._row(2, dra=20), miss], simbad={"** LDS 823": {"otype": "**"}})
        self.assertEqual((len(b["partners"]), b["field_stars"]), (1, []))
        miss2 = dict(miss, star_name="CD-38 1297")                      # resolves to otype ** (S1's second form)
        b = self._run([self._row(1), self._row(2, dra=20), miss2], simbad={"CD-38 1297": {"otype": "**"}})
        self.assertEqual((len(b["partners"]), b["field_stars"]), (1, []))

    def test_l1_no_sid_target_removes_a_main_row_by_identity_only(self):
        T = dict(self.T, sid=None)
        rows = [self._row(1, star_name="S1"), self._row(2, dra=20)]
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        sim = {"Gaia DR3 1": {"main_id": "* T"}, "Gaia DR3 2": {"main_id": "* P"}}
        with mock.patch.object(databases, "simbad_astrometry",
                               side_effect=lambda i, family=None: (sim.get(i), None)), \
                mock.patch.object(databases, "simbad_parent", return_value=([], None)), \
                mock.patch.object(xc, "_partner_mass_seam", return_value=(0.7, "catalog", None)), \
                mock.patch.object(xc, "_gaia_radius_seam", return_value={"parameters": {}}), \
                mock.patch.object(xc, "_tic_query", return_value={"answered": True, "sources": []}):
            b = xc.blend_partners(_star(), {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0},
                                  10.0, T, None, db_path=db)
        self.assertEqual([p["name"] for p in b["partners"]], ["* P"])   # row 1 IS the target (by identity)

    def test_s3_partner_never_takes_the_targets_radius(self):
        rows = [self._row(1), self._row(2, dra=1, spectral_type=None, star_name="HD X B", parallax_error=None,
                                         pmra=None, pmdec=None)]
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        tic = {"answered": True, "sources": [{"rad": 0.94, "sep": 0.01, "tic": "394547839", "gaia": "1"}]}
        with mock.patch.object(databases, "simbad_astrometry",
                               side_effect=lambda i, family=None: ({"main_id": "* T B"} if i == "Gaia DR3 2" else None,
                                                                   None)), \
                mock.patch.object(databases, "simbad_parent", return_value=([], None)), \
                mock.patch.object(xc, "_partner_mass_seam", return_value=(0.07, "catalog", None)), \
                mock.patch.object(xc, "_gaia_radius_seam", return_value={"parameters": {}}), \
                mock.patch.object(xc, "_tic_query", return_value=tic):
            b = xc.blend_partners(_star(), {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0},
                                  10.0, dict(self.T, main_id="* T"), None, db_path=db)
        self.assertEqual(len(b["partners"]), 1)
        self.assertEqual(b["partners"][0]["radius_candidates"], [])       # the target's own TIC row rejected

    def test_wd_partner(self):
        b = self._run([self._row(1), self._row(2, dra=20, wd_prob=0.9)])
        self.assertTrue(b["partners"][0]["wd"])

    def test_empty_table_is_failed_and_reach(self):
        b = self._run([])
        self.assertEqual(b["status"], "failed")
        b = self._run([self._row(9, dist_pc=50.0)], d_pc=80.0)
        self.assertEqual(b["status"], "not_run")

    def test_blend_hook(self):
        os.environ["SPACE_APP_BLEND_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(self._run([self._row(1)])["status"], "failed")

    def test_r4_partial(self):
        rows = [self._row(1), self._row(2, dra=20)]
        b = self._run(rows, simbad={"Gaia DR3 2": "timeout"})
        self.assertTrue(b["partial"])
        self.assertEqual([p["name"] for p in b["partners"]], ["S2"])      # named by its GCNS identifier

    def test_r3_two_msun_note(self):
        rows = [self._row(1), self._row(2, dra=20, parallax_error=None)]
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry", return_value=({"main_id": "* P"}, None)), \
                mock.patch.object(databases, "simbad_parent", return_value=([], None)), \
                mock.patch.object(xc, "_partner_mass_seam", return_value=(None, None, None)), \
                mock.patch.object(xc, "_gaia_radius_seam", return_value={"parameters": {}}), \
                mock.patch.object(xc, "_tic_query", return_value={"answered": True, "sources": []}):
            b = xc.blend_partners(_star(), {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0},
                                  10.0, self.T, None, db_path=db)
        self.assertTrue(any("2 M☉" in n for n in b["notes"]))


@pytest.mark.cr26_network
class IdentityTest(_Base):
    def test_adapter(self):
        with mock.patch.object(databases, "compute_simbad_lookup",
                               return_value={"error": f"{databases.SIMBAD_NO_RESULTS_PREFIX} 'x'"}):
            self.assertEqual(xc._identity_lookup("x"), (None, None))
        with mock.patch.object(databases, "compute_simbad_lookup", return_value={"error": "Could not connect"}):
            self.assertEqual(xc._identity_lookup("x"), (None, "unreachable"))
        with mock.patch.object(databases, "compute_simbad_lookup", return_value={"main_id": "* X"}):
            self.assertEqual(xc._identity_lookup("x"), ({"main_id": "* X"}, None))
        os.environ["SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(xc._identity_lookup("x"), (None, "unreachable"))

    def test_no_results_prefix_drift(self):
        import inspect
        # CR-27.1: the lookup body moved into _simbad_lookup_impl (compute_simbad_lookup is its thin wrapper)
        src = inspect.getsource(databases._simbad_lookup_impl)
        self.assertIn("SIMBAD_NO_RESULTS_PREFIX", src)

    def test_h1_and_k3(self):
        # a failed component lookup: the string match finds the row → measured, note, not not_authoritative
        inp = xc.resolve_star_wind_inputs(
            {"sp_type": "M3.5V", "main_id": None, "candidate": "HD 1326 B", "sl_failed": True, "domain": "main_sequence"},
            {}, allow_network=False)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "measured")
        self.assertNotIn("not_authoritative", r["wind_model"]["flags"])
        self.assertTrue(any("identity lookup" in n for n in r["wind_model"]["notes"]))
        # GJ 860 A via G12: letterless head, the A-candidate lookup failed → K3 string hit
        with mock.patch.object(xc, "_identity_lookup", return_value=(None, "timeout")):
            inp = xc.resolve_star_wind_inputs(
                {"sp_type": "M3V", "main_id": "HD 239960", "candidate": "HD 239960 A", "domain": "main_sequence"},
                {}, allow_network=True)
        self.assertIn("HD 239960A", inp.measured_ids)
        # no hit → not_authoritative
        inp = xc.resolve_star_wind_inputs(
            {"sp_type": "K2V", "main_id": None, "candidate": "* zzz B", "sl_failed": True, "domain": "main_sequence"},
            {}, allow_network=False)
        self.assertTrue(inp.measured_miss_not_authoritative)
        self.assertIn("not_authoritative", sw.resolve_wind_model(inp)["wind_model"]["flags"])

    def test_s2_blend_target_is_the_resolved_a(self):
        seen = {}

        def fake_blend(a, cand, d_pc, target, catalog, db_path=None):
            seen.update(target)
            return {"status": None, "partners": [], "field_stars": [], "notes": [], "partial": False}
        a_rec = {"main_id": "* 70 Oph A", "designations": {"Gaia EDR3": "Gaia DR3 4468557611984384512"}}
        with mock.patch.object(xc, "_identity_lookup", return_value=(a_rec, None)), \
                mock.patch.object(xc, "star_astrometry", return_value={
                    "ra": 1.0, "dec": 2.0, "epoch": 2000.0, "pmra": 0.0, "pmdec": 0.0, "notes": [], "status": None}), \
                mock.patch.object(xc, "radius_candidates", return_value=([], {}, False, False)), \
                mock.patch.object(xc, "xray_ladder", return_value=[
                    {"rung": "2RXS", "status": "detection", "cand": {"f_x": 1e-12, "epoch": 1990.8, "ra": 1.0,
                                                                      "dec": 2.0, "match_radius": 60.0}},
                    {"rung": "eRASS1", "status": "out_of_footprint", "cand": None},
                    {"rung": "XMM", "status": "no_detection", "cand": None}]), \
                mock.patch.object(xc, "blend_partners", side_effect=fake_blend), \
                mock.patch.object(xc, "_gcns_row_by_sid", return_value=None):
            xc.resolve_star_wind_inputs({"sp_type": "K0V", "main_id": "*  70 Oph", "candidate": "*  70 Oph A",
                                         "domain": "main_sequence", "d_pc": 5.1}, {}, allow_network=True)
        self.assertEqual((seen["main_id"], seen["sid"]), ("* 70 Oph A", "4468557611984384512"))

    def test_g12_letterless_head(self):
        with mock.patch.object(xc, "_identity_lookup", return_value=({"main_id": "* alf Cen A"}, None)):
            inp = xc.resolve_star_wind_inputs(
                {"sp_type": "G2V", "main_id": "* alf Cen", "candidate": "* alf Cen A", "domain": "main_sequence"},
                {}, allow_network=True)
        self.assertEqual(sw.resolve_wind_model(inp)["mass_loss_tier"], "measured")
        self.assertTrue(any("letterless head" in n for n in inp.notes))


@pytest.mark.cr26_network
class OrchestratorTest(_Base):
    def test_offline_never_calls_a_fetcher(self):
        with mock.patch.object(xc, "star_astrometry", side_effect=AssertionError("network")):
            inp = xc.resolve_star_wind_inputs({"sp_type": "K2V", "main_id": "* x", "domain": "main_sequence"},
                                              {}, allow_network=False)
        self.assertEqual((inp.network, inp.not_run_reason), (False, "network_disabled"))

    def test_supplied_log_fx_runs_radius_only(self):
        with mock.patch.object(xc, "radius_candidates", return_value=([{"source": "tic", "value": 0.8}], {}, False,
                                                                      False)) as rc, \
                mock.patch.object(xc, "xray_ladder", side_effect=AssertionError("ladder")):
            inp = xc.resolve_star_wind_inputs(
                {"sp_type": "K2V", "main_id": "* x", "domain": "main_sequence", "ra": 1.0, "dec": 2.0, "d_pc": 10.0},
                {"log_fx": 5.0}, allow_network=True)
        rc.assert_called_once()
        self.assertEqual(inp.not_run_reason, "supplied")
        self.assertEqual(sw.resolve_wind_model(inp)["wind_model"]["radius"]["radius_source"], "tic")

    def test_no_distance(self):
        inp = xc.resolve_star_wind_inputs({"sp_type": "K2V", "main_id": "* x", "domain": "main_sequence"}, {},
                                          allow_network=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "class_default")
        self.assertIn(sw.NOTE_NO_DISTANCE, r["wind_model"]["notes"])
        self.assertNotIn("not_authoritative", r["wind_model"]["flags"])

    def test_astrometry_failure_flows_to_model(self):
        with mock.patch.object(xc, "star_astrometry", return_value={"status": "timeout", "notes": []}):
            inp = xc.resolve_star_wind_inputs(
                {"sp_type": "K2V", "main_id": "* x", "domain": "main_sequence", "d_pc": 10.0}, {}, allow_network=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "class_default")
        self.assertEqual(r["wind_model"]["xray"]["status"], "timeout")
        self.assertEqual([x["status"] for x in r["wind_model"]["xray"]["rungs"]], ["not_queried"] * 3)
        self.assertIn("not_authoritative", r["wind_model"]["flags"])


@pytest.mark.cr26_network
class SimbadCr26PlumbingTest(_Base):
    """databases._simbad_cr26_call — retry once, an answered error never retried, per-family breaker (timeout
    only), answered-empty cached / a failure never (CP2 finding 7)."""

    def test_retry_and_answered(self):
        calls = []

        def down(adql):
            calls.append(1)
            raise ConnectionError("x")
        with mock.patch.object(databases, "_simbad_cr26_tap", down), mock.patch("core.shared.time.sleep"), \
                mock.patch.object(databases, "_simbad_warn"):
            self.assertEqual(databases.simbad_astrometry("X"), (None, "unreachable"))
        self.assertEqual(len(calls), 2)
        calls.clear()

        def answered(adql):
            calls.append(1)
            raise databases._Cr26SimbadAnswered("bad")
        with mock.patch.object(databases, "_simbad_cr26_tap", answered):
            self.assertEqual(databases.simbad_astrometry("X"), (None, "error"))
        self.assertEqual(len(calls), 1)
        with mock.patch.object(databases, "_simbad_cr26_tap", return_value=[]):
            self.assertEqual(databases.simbad_astrometry("X"), (None, None))       # answered, no object

    def test_breaker_is_per_family(self):
        from core.shared import _WatchdogTimeout
        with mock.patch.object(databases, "_simbad_cr26_tap", side_effect=_WatchdogTimeout()), \
                mock.patch("core.shared._call_with_watchdog", side_effect=lambda fn, timeout: fn()), \
                mock.patch("core.shared.time.sleep"), mock.patch.object(databases, "_simbad_warn"):
            self.assertEqual(databases.simbad_cone_stars(1.0, 2.0, 5.0)[1], "timeout")     # radius family
        seen = []
        with mock.patch.object(databases, "_simbad_cr26_tap", side_effect=lambda q: seen.append(q) or []):
            self.assertEqual(databases.simbad_cone_stars(1.0, 2.0, 5.0), (None, "timeout"))  # breaker open
            self.assertEqual(databases.simbad_astrometry("X", family="blend"), (None, None))  # other family runs
        self.assertEqual(len(seen), 1)

    def test_cache(self):
        import pathlib
        with tempfile.TemporaryDirectory() as d, mock.patch.object(catalog_cache, "_CACHE_DIR", pathlib.Path(d)):
            os.environ["SPACE_APP_CATALOG_CACHE"] = "1"
            with mock.patch.object(databases, "_simbad_cr26_tap", return_value=[]):
                databases.simbad_parent("X")
            self.assertEqual(len(os.listdir(d)), 1)                                     # answered-empty cached
            with mock.patch.object(databases, "_simbad_cr26_tap", side_effect=ConnectionError("x")), \
                    mock.patch("core.shared.time.sleep"), mock.patch.object(databases, "_simbad_warn"):
                databases.simbad_parent("Y")
            self.assertEqual(len(os.listdir(d)), 1)                                     # failure not cached

    def test_cone_filter_r12(self):
        rows = [{"oid": 1, "main_id": "* T", "otype": "PM*"}, {"oid": 2, "main_id": "* T B", "otype": "BY*"},
                {"oid": 3, "main_id": "1RXS J..", "otype": "X"}, {"oid": 4, "main_id": "IRAS ..", "otype": "IR"},
                {"oid": 5, "main_id": "** WDS", "otype": "**"}, {"oid": 6, "main_id": "TT cand", "otype": "TT?"}]
        with mock.patch.object(databases, "_simbad_cr26_tap", return_value=rows):
            got, st = databases.simbad_cone_stars(1.0, 2.0, 5.0, exclude_oid=1)
        self.assertEqual([r["oid"] for r in got], [2, 6])
        with mock.patch.object(databases, "_simbad_cr26_tap", return_value=rows):
            got, st = databases.simbad_cone_stars(1.0, 2.0, 5.0, exclude_main_id="*  T")
        self.assertEqual([r["oid"] for r in got], [2, 6])

    def test_parent_filter_j3(self):
        rows = [{"parent": 10, "otype": "**"}, {"parent": 11, "otype": "Cl*"}, {"parent": 12, "otype": "MGr"},
                {"parent": 13, "otype": "SB?"}]
        with mock.patch.object(databases, "_simbad_cr26_tap", return_value=rows):
            self.assertEqual(databases.simbad_parent("X"), ([10, 13], None))


@pytest.mark.cr26_network
class GcnsSqlTest(_Base):
    def test_ra_wrap(self):
        db = make_gcns([{"gaia_source_id": 1, "ra": 359.999, "dec": 0.0, "gcns_table": "main"},
                        {"gaia_source_id": 2, "ra": 0.001, "dec": 0.0, "gcns_table": "main"},
                        {"gaia_source_id": 3, "ra": 180.0, "dec": 0.0, "gcns_table": "main"}])
        self.addCleanup(os.remove, db)
        rows = xc._gcns_rows_near(0.0, 0.0, 60.0, db_path=db)
        self.assertEqual(sorted(r["gaia_source_id"] for r in rows), [1, 2])

    def test_missing_db_and_reach_not_memoised(self):
        self.assertIsNone(xc.gcns_reach(db_path="/nonexistent/x.db"))
        self.assertNotIn("/nonexistent/x.db", xc._REACH)

    def test_cache_dir_env(self):
        import subprocess
        import sys
        out = subprocess.run([sys.executable, "-c", "import core.catalog_cache as c; print(c._CACHE_DIR)"],
                             capture_output=True, text=True, env={**os.environ, "SPACE_APP_CATALOG_CACHE_DIR": "/tmp/xyz"},
                             cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent))
        self.assertEqual(out.stdout.strip(), "/tmp/xyz")

    def test_null_flux_rung_errors(self):
        fake = _Heasarc({"xmmssc": [{"srcid": 1, "name": "x", "ra": 100.0, "dec": 10.0, "time": _mjd(2005),
                                     "end_time": _mjd(2006), "ep_1_flux": None, "ep_2_flux": None,
                                     "ep_3_flux": None, "ep_det_ml": 40, "sum_flag": 0}]})
        with mock.patch.object(xc, "_heasarc_tap", fake), mock.patch.object(xc, "galactic_l", return_value=10.0), \
                mock.patch.object(xc, "_warn"):
            self.assertEqual(xc.xray_ladder(_star())[2]["status"], "error")

    def test_simbad_pm_fills_a_gaia_row_without_pm(self):
        db = make_gcns([{"gaia_source_id": 5, "ra": 1.0, "dec": 2.0, "parallax": 50.0, "parallax_error": 0.1,
                         "phot_g_mean_mag": 9.0, "gcns_table": "main"}])
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry",
                               return_value=({"pmra": 500.0, "pmdec": -300.0, "g": 9.1}, None)):
            a = xc.star_astrometry({"main_id": "X", "gaia_sid": "5"}, db_path=db)
        self.assertEqual((a["pmra"], a["pmdec"], a["epoch"]), (500.0, -300.0, 2016.0))
        self.assertFalse(any("no proper motion" in n for n in a["notes"]))


@pytest.mark.cr26_network
class ReGateFixesTest(_Base):
    """WB re-gate MSG 311 — RG1 / RG3 / RG4 / RG7, pinned."""

    T = BlendTest.T
    _run = BlendTest._run
    _row = staticmethod(BlendTest._row)

    @staticmethod
    def _miss(name, dra=0.0):
        return {"gaia_source_id": None, "ra": 100.0 + dra / 3600, "dec": 10.0, "parallax": 100.0,
                "gcns_table": "missing_10mas", "star_name": name, "dist_pc": 10.0}

    _SIM = {"pmra": 0.0, "pmdec": 0.0, "plx_value": 100.0, "plx_err": 0.1}

    def test_rg1_sid_target_without_main_row_drops_its_missing_copy(self):
        # GJ 860 A: a Gaia id, no GCNS main row — only its own missing_10mas copy + B's
        b = self._run([self._miss("* T", 0.3), self._miss("* T B", 3.0)],
                      simbad={"* T": dict(self._SIM, main_id="* T"), "* T B": dict(self._SIM, main_id="* T B")})
        self.assertEqual([p["name"] for p in b["partners"]], ["* T B"])
        # EZ Aqr: the lone copy, matched by its SIMBAD main_id (G13's identity half) → no self-partner
        b = self._run([self._miss("GJ 9999", 0.3)], simbad={"GJ 9999": dict(self._SIM, main_id="* T")})
        self.assertEqual((b["partners"], b["field_stars"]), ([], []))

    def test_rg4_k3_despaced_name_removes_the_copy(self):
        self.T = {"main_id": "HD 239960 A", "sid": None, "mass": 0.3, "system_id": None, "degraded": True,
                  "alt_names": ["HD 239960"]}
        b = self._run([self._miss("HD 239960A", 0.3), self._miss("HD 239960B", 3.0)],
                      simbad={"HD 239960A": dict(self._SIM, main_id="HD 239960A"),
                              "HD 239960B": dict(self._SIM, main_id="HD 239960B")})
        self.assertEqual([p["name"] for p in b["partners"]], ["HD 239960B"])

    def test_rg4_degraded_h1_keeps_the_stars_own_sid(self):
        seen = {}

        def fake_blend(a, cand, d_pc, target, catalog, db_path=None):
            seen.update(target)
            return {"status": None, "partners": [], "field_stars": [], "notes": [], "partial": False}
        with mock.patch.object(xc, "_identity_lookup", return_value=(None, "unreachable")), \
                mock.patch.object(xc, "star_astrometry", return_value={
                    "ra": 1.0, "dec": 2.0, "epoch": 2000.0, "pmra": 0.0, "pmdec": 0.0, "notes": [], "status": None}), \
                mock.patch.object(xc, "radius_candidates", return_value=([], {}, False, False)), \
                mock.patch.object(xc, "xray_ladder", return_value=[
                    {"rung": "2RXS", "status": "detection", "cand": {"f_x": 1e-12, "epoch": 1990.8, "ra": 1.0,
                                                                      "dec": 2.0, "match_radius": 60.0}},
                    {"rung": "eRASS1", "status": "out_of_footprint", "cand": None},
                    {"rung": "XMM", "status": "no_detection", "cand": None}]), \
                mock.patch.object(xc, "blend_partners", side_effect=fake_blend), \
                mock.patch.object(xc, "_gcns_row_by_sid", return_value=None):
            xc.resolve_star_wind_inputs({"sp_type": "M6V", "main_id": "Wolf  359", "candidate": "Wolf 359 A",
                                         "designations": {"Gaia EDR3": "Gaia DR3 3864972938605115520"},
                                         "domain": "main_sequence", "d_pc": 2.4}, {}, allow_network=True)
        self.assertEqual((seen["main_id"], seen["sid"]), ("Wolf 359 A", "3864972938605115520"))

    def _neighbour(self, rows, simbad):
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry",
                               side_effect=lambda i, family=None: (simbad.get(i), None)
                               if not isinstance(simbad.get(i), str) else (None, simbad[i])):
            return xc._gcns_neighbour(_star(), 1, "HD 19902", db_path=db)

    def test_rg3_system_entry_is_not_a_neighbour(self):
        self.assertFalse(self._neighbour([self._row(1), self._miss("** LDS 9146", 0.2)], {}))
        self.assertFalse(self._neighbour([self._row(1), self._miss("CD-38 1297", 0.2)],
                                         {"CD-38 1297": {"otype": "**"}}))
        self.assertTrue(self._neighbour([self._row(1), self._miss("CD-38 1297", 0.2)],
                                        {"CD-38 1297": {"otype": "*"}}))
        self.assertTrue(self._neighbour([self._row(1), self._miss("CD-38 1297", 0.2)],
                                        {"CD-38 1297": "timeout"}))           # a failed lookup keeps the flag

    def test_rg4_degraded_name_half_takes_the_head(self):
        # a letterless no-main-row star under the ident hook: its copy is named after the head, not the candidate
        self.T = {"main_id": "V* EZ Aqr A", "sid": 7, "mass": 0.1, "system_id": None, "degraded": True,
                  "alt_names": ["V* EZ Aqr"]}
        b = self._run([self._miss("V* EZ Aqr", 0.3)], simbad={"V* EZ Aqr": dict(self._SIM, main_id="V* EZ Aqr")})
        self.assertEqual((b["partners"], b["field_stars"]), ([], []))

    def test_k3_only_on_the_degraded_path(self):
        rows = [self._miss("* T B", 3.0), self._miss("* TB", 0.3)]
        sim = {"* T B": dict(self._SIM, main_id="* T B"), "* TB": dict(self._SIM, main_id="* TB")}
        self.T = {"main_id": "* T B", "sid": 1, "mass": 0.3, "system_id": None}
        self.assertEqual(len(self._run(rows, simbad=sim)["partners"] + self._run(rows, simbad=sim)["field_stars"]), 1)
        self.T = dict(self.T, degraded=True)
        b = self._run(rows, simbad=sim)
        self.assertEqual((b["partners"], b["field_stars"]), ([], []))

    def test_neighbour_skips_the_targets_own_copy(self):
        # by SIMBAD identity (G13's identity half), and by K3 on a degraded path
        db = make_gcns([self._row(1), self._miss("GJ 9999", 0.2)])
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry",
                               return_value=({"main_id": "V* EZ Aqr", "otype": "Er*"}, None)):
            self.assertFalse(xc._gcns_neighbour(_star(), 1, "V* EZ Aqr", db_path=db))
        db = make_gcns([self._row(1), self._miss("HD 239960A", 0.2)])
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry", return_value=({"main_id": "X", "otype": "*"}, None)):
            self.assertTrue(xc._gcns_neighbour(_star(), 1, "HD 239960", db_path=db))
            self.assertFalse(xc._gcns_neighbour(_star(), 1, "HD 239960", db_path=db,
                                                own_names=["HD 239960 A", "HD 239960"], degraded=True))

    def test_neighbour_lookup_honours_the_tic_hook(self):
        os.environ["SPACE_APP_TIC_FORCE_UNREACHABLE"] = "1"
        db = make_gcns([self._row(1), self._miss("CD-38 1297", 0.2)])
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry", side_effect=AssertionError("network")):
            self.assertTrue(xc._gcns_neighbour(_star(), 1, "HD 19902", db_path=db))

    def _partner_notes(self, gaia_res=None):
        rows = [self._row(1), self._row(2, dra=20)]
        db = make_gcns(rows)
        self.addCleanup(os.remove, db)
        with mock.patch.object(databases, "simbad_astrometry", return_value=({"main_id": "* P"}, None)), \
                mock.patch.object(databases, "simbad_parent", return_value=([], None)), \
                mock.patch.object(xc, "_partner_mass_seam", return_value=(0.7, "catalog", None)), \
                mock.patch.object(xc, "_gaia_radius_seam", return_value=gaia_res or {"parameters": {}}), \
                mock.patch.object(xc, "_tic_query", return_value={"answered": True, "sources": []}):
            b = xc.blend_partners(_star(), {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0},
                                  10.0, self.T, None, db_path=db)
        self.assertEqual([p["name"] for p in b["partners"]], ["* P"])
        return [n for n in b["notes"] if n.startswith("blend partner")]

    def test_rg8_partner_radius_failures_are_noted(self):
        self.assertEqual(self._partner_notes(), [])                                   # a normal run: none
        self.assertEqual(self._partner_notes({"error": "x", "gaia_bound_reason": "timeout"}),
                         [xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="Gaia", st="timeout")])
        os.environ["SPACE_APP_TIC_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(self._partner_notes(), [xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="TIC",
                                                                               st="unreachable")])
        os.environ.pop("SPACE_APP_TIC_FORCE_UNREACHABLE")
        os.environ["SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE"] = "1"
        self.assertEqual(self._partner_notes(), [xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="Gaia",
                                                                               st="unreachable")])

    def test_rg8_real_family_failure_is_noted(self):
        # the re-gate's shape: only the partner's TIC call fails (a raised error through _family_call)
        with mock.patch.object(xc, "_BACKOFF", 0.0):
            rows = [self._row(1), self._row(2, dra=20)]
            db = make_gcns(rows)
            self.addCleanup(os.remove, db)
            with mock.patch.object(databases, "simbad_astrometry", return_value=({"main_id": "* P"}, None)), \
                    mock.patch.object(databases, "simbad_parent", return_value=([], None)), \
                    mock.patch.object(xc, "_partner_mass_seam", return_value=(0.7, "catalog", None)), \
                    mock.patch.object(xc, "_gaia_radius_seam", return_value={"parameters": {}}), \
                    mock.patch.object(xc, "_tic_query", side_effect=OSError("down")):
                b = xc.blend_partners(_star(), {"epoch": 2016.0, "ra": 100.0, "dec": 10.0, "match_radius": 60.0},
                                      10.0, self.T, None, db_path=db)
        self.assertIn(xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="TIC", st="unreachable"), b["notes"])

    def test_rg8_guard_demotion_keeps_the_blend_notes(self):
        note = xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="TIC", st="timeout")
        blend = {"status": None, "partners": [], "field_stars": [], "partial": False, "notes": [note]}
        rungs = [{"rung": "2RXS", "status": "no_detection", "cand": None},
                 {"rung": "eRASS1", "status": "out_of_footprint", "cand": None},
                 {"rung": "XMM", "status": "detection",
                  "cand": {"f_x": 1e-13, "sum_flag": 3, "det_ml": 20, "blend": blend, "epoch": 2005.0}}]
        inp = sw.StarWindInputs(sp_type="K2V", network=True, d_pc=10.0, rungs=rungs, g_mag=5.0,
                                radius_candidates=[{"source": "tic", "value": 0.75}],
                                limit={"status": None, "f_limit": 1e-14, "survey": "2RXS"})
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["wind_model"]["xray"]["xmm_guard"]["result"], "xmm_guard_demoted")
        self.assertIn(note, r["wind_model"]["notes"])

    def test_rg8_note_reaches_the_model_without_a_flag(self):
        blend = {"status": None, "partners": [{"name": "* P", "sp_type": "K5V", "radius_candidates": [],
                                                "by_designation": False, "wd": False}],
                 "field_stars": [], "partial": False,
                 "notes": [xc.NOTE_PARTNER_RADIUS.format(name="* P", fam="TIC", st="timeout")]}
        _rsq, flags, notes, _names = sw._eval_blend(sw.StarWindInputs(sp_type="K5V"), blend, 0.7, None)
        self.assertIn(blend["notes"][0], notes)
        self.assertNotIn("not_authoritative", flags)

    def test_rg7_astrometry_fail_radius_not_queried(self):
        with mock.patch.object(xc, "star_astrometry", return_value={"status": "unreachable", "notes": []}):
            inp = xc.resolve_star_wind_inputs(
                {"sp_type": "M4V", "main_id": "* x", "domain": "main_sequence", "d_pc": 4.1}, {}, allow_network=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["wind_model"]["radius"]["status"],
                         {"tic": "not_queried", "gaia": "not_queried", "simbad_cone": "not_queried"})
        self.assertEqual(r["wind_model"]["radius"]["radius_source"], "subtype_median")


class ConftestIsolationTest(unittest.TestCase):
    """Unmarked: the conftest forces allow_network=False and stubs every seam."""

    def test_forced_offline(self):
        inp = xc.resolve_star_wind_inputs({"sp_type": "K2V", "main_id": "* x", "domain": "main_sequence",
                                           "d_pc": 10.0}, {}, allow_network=True)
        self.assertFalse(inp.network)

    def test_seams_are_stubbed(self):
        for mod, attr in (("core.databases", "_simbad_cr26_tap"), ("core.xray_catalog", "_heasarc_tap"),
                          ("core.xray_catalog", "_tic_query"), ("core.xray_catalog", "_identity_lookup"),
                          ("core.xray_catalog", "_gaia_astrom_seam"), ("core.xray_catalog", "_gaia_radius_seam"),
                          ("core.xray_catalog", "_partner_mass_seam")):
            self.assertEqual(getattr(__import__(mod, fromlist=[attr]), attr).__name__, "_stub", attr)

if __name__ == "__main__":
    unittest.main()
