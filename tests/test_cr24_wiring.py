# tests/test_cr24_wiring.py — CR-24.2 / .4 / .5 end to end, offline: the V_ISM precedence on both subcommands, the
# flags and their exit codes, the notes, presence, the D6 medium echo (A9), the D5 combined-wind zone (A6), the
# ⚑1 component fallback / D-C1 note (A3), A7's degrade hook, and A0 byte-identity on the no-lookup paths.
# The --star paths reuse test_cr25's stubbed SIMBAD identity / regions / FLAME and stub CR-24's two seams from the
# reference rows (tests/fixtures/cr24_simbad_velocity_rows.json).

import json
import math
import os
import unittest
from unittest import mock

import pytest

from core import exclusion_system as es
from core import ism_velocity as iv
from tests._cr24strip import strip
from tests._queryharness import run_query_inproc
from tests.test_cr24_velocity import identity_seam, velocity_seam
from tests.test_cr25 import _LISTS, _Cr25EnvMixin, _run_boundary, _star_mocks

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")
_TOKEN = "[[CR-24"
_A6 = ["id=A,mass=0.1225,class=M5.5V,pair=AB,sma=5.51,ecc=0.6185,otype=Er*,radius_rsun=0.165,log_fx=6.0395",
       "id=B,mass=0.1195,class=M6V,pair=AB,sma=5.51,ecc=0.6185,otype=Er*,radius_rsun=0.159,log_fx=6.0395"]


def _sys(*specs, **extra):
    args = [a for s in specs for a in ("--component", s)] + ["--alpha", "0.4"]
    for k, v in extra.items():
        args += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
    code, p, err = run_query_inproc("exclusion-system", *args)
    assert p is not None, err
    return code, p


def _comp(p, cid):
    return next(c for z in p["zones"] for c in z["components"] if c["id"] == cid)


def _no_token(test, obj):
    test.assertNotIn(_TOKEN, json.dumps(obj))


class A0ByteIdentityTest(unittest.TestCase):
    """A0: every no-lookup path (--spectral-type / --mass-msun / --object / --component without main_id=, a supplied
    --v-ism, the D5 zone below 30) is byte-identical to the pre-CR-24 tree but for CR-24's additive fields."""

    def test_no_lookup_paths(self):
        with open(os.path.join(_FIX, "cr24_a0_baseline.json"), encoding="utf-8") as fh:
            cases = json.load(fh)
        for case in cases:
            with self.subTest(args=case["args"]):
                code, payload, err = run_query_inproc(*case["args"])
                self.assertEqual(code, case["exit"])
                self.assertEqual(strip(json.loads(json.dumps(payload, default=str))), case["payload"])

    def test_additive_fields_on_a_no_lookup_path(self):
        code, p, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--alpha", "0.4")
        self.assertEqual((p["v_ism_kms"], p["v_ism_provenance"], p["v_cloud_used"], p["v_cloud_chi2"]),
                         (26.0, "assumed", None, None))
        self.assertEqual((p["velocity_status"], p["velocity_provenance"], p["space_velocity"]), ("not_run", None, None))
        self.assertEqual((p["v_ism_range_kms"], p["wall_range_vism_au"], p["wall_route_provisional"],
                          p["clic_domain"], p["v_ism_derived_kms"]), (None, None, False, None, None))
        self.assertAlmostEqual(p["m_f"], 1.3)
        self.assertEqual(p["verdict_marginal_reasons"], ["c_ms_straddle"])
        self.assertTrue(p["verdict_marginal"])


class FlagsAndExitCodesTest(unittest.TestCase):
    def test_cloud_is_a_real_flag(self):
        for sub, body in (("exclusion-boundary", ["--spectral-type", "K2V"]),
                          ("exclusion-system", ["--component", "id=S,mass=0.8,class=K2V"])):
            for bad in ("Foo", "300"):
                with self.subTest(sub=sub, bad=bad):
                    code, p, err = run_query_inproc(sub, *body, "--cloud", bad)
                    self.assertEqual(code, 2)
                    for name in ("LIC", "Hyades", "Cet", "Dor"):
                        self.assertIn(name, err)
        code, p, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--cloud-temp", "300")
        self.assertEqual(p["cloud_temp_k"], 300.0)                      # the real flag still works

    def test_positive_finite_validators(self):
        for sub, body in (("exclusion-boundary", ["--spectral-type", "K2V"]),
                          ("exclusion-system", ["--component", "id=S,mass=0.8,class=K2V"])):
            for flag, val in (("--v-ism", "0"), ("--v-ism", "-3"), ("--v-ism", "nan"), ("--clic-max-pc", "0"),
                              ("--clic-max-pc", "inf")):
                with self.subTest(sub=sub, flag=flag, val=val):
                    self.assertEqual(run_query_inproc(sub, *body, flag, val)[0], 2)
        for spec in ("id=S,mass=0.8,class=K2V,v_ism=0", "id=S,mass=0.8,class=K2V,lb_cavity=maybe"):
            with self.subTest(spec=spec):
                self.assertEqual(run_query_inproc("exclusion-system", "--component", spec)[0], 2)

    def test_ignored_flags_on_no_lookup_paths(self):
        code, p, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--alpha", "0.4",
                                      "--cloud", "G", "--clic-max-pc", "5", "--lb-cavity")
        notes = p["wind_model"]["notes"]
        self.assertIn(iv.NOTE_IGNORED_NO_LOOKUP.format(flag="--cloud"), notes)
        self.assertIn(iv.NOTE_IGNORED_NO_LOOKUP.format(flag="--clic-max-pc"), notes)
        self.assertIn(iv.NOTE_LB_IGNORED + " (V_ISM 26 either way)", notes)
        _c, p2, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--alpha", "0.4",
                                     "--lb-cavity", "--v-ism", "40")
        self.assertIn(iv.NOTE_LB_IGNORED, p2["wind_model"]["notes"])    # CP3/4: no "26 either way" beside 40
        self.assertEqual((p["v_ism_kms"], p["v_ism_provenance"]), (26.0, "assumed"))
        code, p = _sys("id=S,mass=0.8,class=K2V", cloud="G")
        self.assertIn(iv.NOTE_IGNORED_NO_LOOKUP.format(flag="--cloud"), _comp(p, "S")["wind_model"]["notes"])

    def test_supplied_v_ism(self):
        code, p, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--alpha", "0.4",
                                      "--v-ism", "40")
        self.assertEqual((p["v_ism_kms"], p["v_ism_provenance"], p["velocity_status"]), (40.0, "supplied", "not_run"))


class ComponentPathTest(unittest.TestCase):
    """A4's --component cases, lb_cavity=, and the A9 D6 echo parity."""

    def test_measured_main_id_takes_the_row(self):
        code, p = _sys("id=E,mass=0.8112,class=K2V,main_id=* eps Eri")
        c = _comp(p, "E")
        self.assertEqual((c["v_ism_kms"], c["v_ism_provenance"], c["velocity_status"], c["v_ism_derived_kms"]),
                         (27.0, "measured_row", "not_run", None))
        self.assertIn(iv.NOTE_ISM_MEASURED.format(n=27, v=27.0, prov="measured_row"), c["wind_model"]["notes"])
        _no_token(self, p)
        code, p = _sys("id=B,mass=0.5362,class=K7V,main_id=* 61 Cyg B")
        c = _comp(p, "B")
        self.assertEqual((c["v_ism_kms"], c["v_ism_provenance"], c["velocity_status"]), (26.0, "assumed", "not_run"))

    def test_lb_cavity_key_and_system_flag(self):
        code, p = _sys("id=E,mass=0.8112,class=K2V,main_id=* eps Eri,lb_cavity=true")
        c = _comp(p, "E")
        self.assertEqual((c["v_ism_kms"], c["v_ism_provenance"]), (26.0, "assumed"))
        self.assertTrue(any("--lb-cavity" in n and "27" in n for n in c["wind_model"]["notes"]))
        code, p = _sys("id=E,mass=0.8112,class=K2V,main_id=* eps Eri", "id=F,mass=0.8,class=K2V,lb_cavity=false",
                       lb_cavity=True)
        self.assertEqual(_comp(p, "E")["v_ism_provenance"], "assumed")      # the system flag reached E
        self.assertEqual(_comp(p, "F")["v_ism_provenance"], "assumed")      # 26 either way

    def test_d6_echo_parity_with_exclusion_boundary(self):
        keys = ("mass_loss_msun_yr", "mass_loss_provenance", "wind_speed_kms", "wind_speed_provenance",
                "v_ism_kms", "v_ism_provenance", "c_ms_kms", "c_ms_provenance", "n_cloud_cm3", "n_cloud_provenance",
                "cloud_temp_k", "cloud_temp_provenance", "wind_phase_yr", "wind_phase_provenance", "f_shock",
                "f_shock_provenance", "m_shock_min", "m_shock_min_provenance", "mass_loss_source",
                "mass_loss_source_provenance")
        code, s = _sys("id=S,mass=0.8,class=K2V,c_ms=15")
        c = _comp(s, "S")
        self.assertEqual((c["c_ms_kms"], c["c_ms_provenance"]), (15.0, "supplied"))
        for k in ("v_ism_provenance", "n_cloud_provenance", "cloud_temp_provenance", "f_shock_provenance",
                  "m_shock_min_provenance"):
            self.assertEqual(c[k], "assumed", k)
        self.assertEqual(c["wind_speed_provenance"], "astrosphere_wood_forced")
        code, b, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "K2V", "--alpha", "0.4", "--c-ms", "15")
        for k in keys:
            self.assertEqual(c[k], b[k], k)
        code, s2 = _sys("id=S,mass=0.8,class=K2V", c_ms=15)
        self.assertEqual(_comp(s2, "S")["c_ms_provenance"], "supplied")
        code, s3 = _sys("id=S,mass=0.8,class=K2V,b_field=3")
        c3 = _comp(s3, "S")
        self.assertIn("b_field_ug", c3)
        self.assertIn("c_ms_band_derived", c3)
        code, u = _sys("id=S,mass=0.47,class=sdB")
        cu = _comp(u, "S")
        self.assertEqual(cu["wall_route"], "none_unmodeled")
        for k in ("v_ism_kms", "c_ms_kms", "wind_speed_kms", "m_f", "wall_route_provisional"):
            self.assertNotIn(k, cu)
        self.assertEqual(cu["velocity_status"], "not_run")

    def test_cr31_forced_speed_echo(self):
        """CR-31 acc 1 through the D6 echo (the stage-2 test asserted it in core)."""
        code, p = _sys("id=S,mass=1.0,wind_state=solar,wind_speed=800")
        c = _comp(p, "S")
        self.assertEqual((c["wind_speed_kms"], c["wind_speed_provenance"]), (400.0, "astrosphere_wood_forced"))
        code, p = _sys("id=S,mass=1.0,wind_state=solar,mass_loss_msun_yr=4e-14,wind_speed=800")
        c = _comp(p, "S")
        self.assertEqual((c["wind_speed_kms"], c["wind_speed_provenance"], c["mass_loss_source"],
                          c["mass_loss_source_provenance"]), (800.0, "supplied", "astrosphere_wood", "class_default"))


class ZoneTest(unittest.TestCase):
    """A6 — the combined-wind zone's route test (D5), the DQ4 rules, and the lower-bound medium by the test hook."""

    def _zone(self, *specs, env=None):
        with mock.patch.dict(os.environ, env or {}):
            code, p = _sys(*specs)
        z = [z for z in p["wall_zones"] if z.get("combined_wind_wall_au") is not None]
        self.assertEqual(len(z), 1)
        return p, z[0]

    def test_v_ism_45(self):
        p, z = self._zone(*(s + ",v_ism=45" for s in _A6))
        self.assertAlmostEqual(_comp(p, "A")["wall_au"], 1.682, places=3)
        self.assertAlmostEqual(_comp(p, "B")["wall_au"], 1.621, places=3)
        self.assertEqual(z["combined_wind_wall_route"], "bow_shock")
        self.assertAlmostEqual(z["combined_wind_wall_au"], 3.7021 / 1.5848, delta=0.001)
        self.assertAlmostEqual(z["combined_wind_band_au"][0], 1.557, places=3)
        self.assertAlmostEqual(z["combined_wind_band_au"][1], 3.115, places=3)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][0], 0.590, places=3)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 13.03, delta=0.01)
        self.assertEqual(z["combined_wind_wall_band_wind_routes"], ["wind_term", "bow_shock"])
        self.assertFalse(z["combined_wind_band_exceeds_standoff"])
        self.assertAlmostEqual(z["combined_wind_route_comparator_au"], 20.51, delta=0.01)
        self.assertFalse(z["combined_wind_route_geometry_marginal"])
        self.assertEqual((z["combined_wind_medium_member"], z["combined_wind_route_provisional"],
                          z["combined_wind_wall_range_vism_au"]), ("A", False, None))

    def test_no_v_ism_is_todays_zone(self):
        p, z = self._zone(*_A6)
        self.assertAlmostEqual(z["combined_wind_wall_au"], 3.702, places=3)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 20.643, places=3)
        self.assertTrue(z["combined_wind_band_exceeds_standoff"])
        self.assertEqual(z["combined_wind_wall_route"], "wind_term")

    def test_dq4_comparator_and_medium_member(self):
        p, z = self._zone(*(s + ",v_ism=125" for s in _A6))
        self.assertEqual(z["combined_wind_wall_route"], "bow_shock_marginal")
        self.assertAlmostEqual(z["combined_wind_wall_au"], 1.921, delta=0.002)
        self.assertTrue(z["combined_wind_route_geometry_marginal"])
        p, z = self._zone(_A6[0] + ",v_ism=25", _A6[1] + ",v_ism=45")
        self.assertAlmostEqual(z["combined_wind_wall_au"], 3.702, places=3)
        self.assertEqual((z["combined_wind_wall_route"], z["combined_wind_medium_member"]), ("wind_term", "A"))

    def test_lower_bound_medium_by_the_hook(self):
        env = {"SPACE_APP_CR24_COMPONENT_VISM_FLOOR": "A=34.9"}
        p, z = self._zone(*_A6, env=env)
        a = _comp(p, "A")
        self.assertEqual((a["v_ism_kms"], a["v_ism_provenance"], a["v_ism_range_kms"], a["velocity_status"]),
                         (34.9, "derived_tangential_lower_bound", [34.9, 1000.0], "not_run"))
        self.assertAlmostEqual(z["combined_wind_wall_au"], 3.702, places=3)
        self.assertEqual(z["combined_wind_wall_route"], "wind_term")
        self.assertAlmostEqual(z["combined_wind_band_au"][0], 2.468, places=3)
        self.assertAlmostEqual(z["combined_wind_band_au"][1], 4.936, places=3)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][0], 0.590, delta=0.01 * 0.590)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 14.542, delta=0.01 * 14.542)
        self.assertFalse(z["combined_wind_band_exceeds_standoff"])
        self.assertTrue(z["combined_wind_route_provisional"])
        self.assertAlmostEqual(z["combined_wind_wall_range_vism_au"][0], 1.906, delta=0.005 * 1.906)
        self.assertAlmostEqual(z["combined_wind_wall_range_vism_au"][1], 3.702, delta=0.005 * 3.702)
        self.assertTrue(any("medium member 'A' has a lower-bound V_ISM" in n for n in a["wind_model"]["notes"]))
        p, z = self._zone(*_A6, env={"SPACE_APP_CR24_COMPONENT_VISM_FLOOR": "A=200"})
        self.assertFalse(z["combined_wind_route_provisional"])
        self.assertAlmostEqual(z["combined_wind_wall_range_vism_au"][0], 1.925, delta=0.005 * 1.925)
        self.assertTrue(any("no bow-shock route is possible above the floor" in n
                            for n in _comp(p, "A")["wind_model"]["notes"]))
        p, z = self._zone(*_A6, env={"SPACE_APP_CR24_COMPONENT_VISM_FLOOR": "A=45"})
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 13.673, delta=0.01 * 13.673)
        self.assertEqual(z["combined_wind_wall_band_wind_routes"], ["wind_term", "capped_astropause"])


@pytest.mark.cr24_velocity
class StarPathTest(_Cr25EnvMixin, unittest.TestCase):
    """exclusion-boundary --star through the stubbed identity (test_cr25) + CR-24's stubbed seams."""

    def _star(self, name, **kw):
        ps = _star_mocks({"V* EV Lac": _LISTS["EV Lac"]}) + [
            mock.patch.object(iv, "_velocity_seam", velocity_seam),
            mock.patch.object(iv, "_identity_seam", identity_seam)]
        for p in ps:
            p.start()
        try:
            return _run_boundary(**{"star": name, "alpha": 0.4, "cloud": None, "clic_max_pc": None,
                                    "lb_cavity": False, **kw})
        finally:
            for p in reversed(ps):
                p.stop()

    def test_measured_row_and_its_derive(self):
        r = self._star("EV Lac")
        self.assertEqual((r["v_ism_kms"], r["v_ism_provenance"], r["velocity_provenance"], r["velocity_status"]),
                         (45.0, "measured_row", "uvw", "ok"))
        self.assertAlmostEqual(r["v_ism_derived_kms"], 43.43, delta=1.0)
        self.assertEqual(r["wall_route"], "bow_shock")
        self.assertEqual((r["v_cloud_used"], r["clic_domain"], r["v_ism_range_kms"]), (None, None, None))
        self.assertIn(iv.NOTE_ISM_MEASURED.format(n=45, v=45.0, prov="measured_row"), r["wind_model"]["notes"])
        _no_token(self, r)

    def test_overrides_on_a_measured_star(self):
        s = self._star("EV Lac", v_ism=40.0)
        self.assertEqual((s["v_ism_kms"], s["v_ism_provenance"], s["velocity_status"]), (40.0, "supplied", "ok"))
        self.assertIsNotNone(s["v_ism_derived_kms"])                   # Q2: the derive still runs
        self.assertTrue(any("inferred at V_ISM 45" in n and "--v-ism 40" in n for n in s["wind_model"]["notes"]))
        self.assertIn(iv.NOTE_ISM_MEASURED.format(n=45, v=40.0, prov="supplied"), s["wind_model"]["notes"])
        lb = self._star("EV Lac", lb_cavity=True)
        self.assertEqual((lb["v_ism_kms"], lb["v_ism_provenance"]), (26.0, "assumed"))
        c = self._star("EV Lac", cloud="LIC")
        self.assertEqual((c["v_ism_provenance"], c["v_cloud_used"], c["v_cloud_chi2"]), ("derived", "LIC", 2.2))
        self.assertAlmostEqual(c["v_ism_kms"], 43.43, delta=1.0)
        self.assertTrue(any("the caller's cloud (LIC)" in n for n in c["wind_model"]["notes"]))

    def test_a7_velocity_hook_keeps_the_row(self):
        with mock.patch.dict(os.environ, {"SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE": "1"}):
            r = self._star("EV Lac")
        self.assertEqual((r["velocity_status"], r["velocity_provenance"], r["v_ism_provenance"]),
                         ("unreachable", "unavailable", "measured_row"))
        self.assertIsNone(r["v_ism_derived_kms"])
        self.assertTrue(any("velocity lookup" in n and "failed" in n for n in r["wind_model"]["notes"]))

    def test_non_measured_star_supplied_skips_the_lookup(self):
        r = self._star("Barnard", v_ism=40.0)             # Barnard's is a measured row → the lookup still runs
        self.assertEqual(r["velocity_status"], "ok")
        t = self._star("GJ 65", v_ism=40.0)               # not a measured row → not_run (Q2)
        self.assertEqual((t["velocity_status"], t["v_ism_provenance"]), ("not_run", "supplied"))

    def test_skipped_lookup_notes_the_unused_flags(self):
        """CP5: --cloud / --clic-max-pc (and --lb-cavity beside --v-ism) on a --star whose lookup step 1 skipped."""
        t = self._star("GJ 65", v_ism=40.0, cloud="G", clic_max_pc=5.0, lb_cavity=True)
        self.assertEqual(t["velocity_status"], "not_run")
        n = t["wind_model"]["notes"]
        for flag in ("--cloud", "--clic-max-pc", "--lb-cavity"):
            self.assertIn(iv.NOTE_IGNORED_BY_STEP.format(flag=flag, by="--v-ism"), n)

    def test_windless_star_reports_its_velocity_only(self):
        r = self._star("Sirius B")
        self.assertEqual(r["wall_route"], "none_windless")
        self.assertIn(r["velocity_provenance"], ("tangential_lower_bound", "unavailable"))
        for k in ("v_ism_kms", "m_f", "v_cloud_used", "wall_route_provisional"):
            self.assertNotIn(k, r)


@pytest.mark.cr24_velocity
class ComponentFallbackTest(unittest.TestCase):
    """⚑1 / D-W2-1 / D-W3-3 / D-C1 on exclusion-system --star's resolved components (the compose helpers directly)."""

    def _pair(self, head, comp):
        comps = [{"id": head, "domain": "main_sequence", "cr26": None, "_cr24_vel": {"role": "head", "target": head}},
                 {"id": comp, "domain": "main_sequence", "cr26": None,
                  "_cr24_vel": {"role": "companion", "target": comp, "name": comp}}]
        with mock.patch.object(iv, "_velocity_seam", velocity_seam), \
                mock.patch.object(iv, "_identity_seam", identity_seam):
            out = [es._cr24_component_ism(c, comps, {}, 2) for c in comps]
        return out

    def test_70_oph_head_and_companion(self):
        (hv, hvel), (bv, bvel) = self._pair("*  70 Oph", "*  70 Oph B")
        self.assertAlmostEqual(hv["v_ism_kms"], 36.44, delta=0.1)       # the head from its A record
        self.assertAlmostEqual(bv["v_ism_kms"], 35.62, delta=0.1)       # B borrows A's own −9.73 (not −5.8)
        self.assertEqual((bvel["space_velocity"]["rv_source"], bvel["space_velocity"]["rv_used"]), ("primary", False))

    def test_answered_empty_head_no_fallback_and_the_dc1_note(self):
        (hv, hvel), (bv, bvel) = self._pair("V* EV Lac", "*  70 Oph B")  # 'V* EV Lac A' answers empty
        self.assertTrue(any("is the target's own SIMBAD record" in n for n in hvel["notes"]))
        self.assertEqual(bvel["provenance"], "tangential_lower_bound")  # WB MSG 328: never the head's record
        # CP3/4: the note says its own RV is used — so not when that RV was gated (EZ Aqr's quality D)
        (hv, hvel), _b = self._pair("V* EZ Aqr", "*  70 Oph B")
        self.assertFalse(any("own SIMBAD record" in n for n in hvel["notes"]))

    def test_windless_component_gets_no_v_ism_notes(self):
        comps = [{"id": "WD", "domain": "windless", "cr26": None, "_cr24_vel": {"role": "head", "target": "* sig Dra"}}]
        with mock.patch.object(iv, "_velocity_seam", velocity_seam), \
                mock.patch.object(iv, "_identity_seam", identity_seam):
            vres, vel = es._cr24_component_ism(comps[0], comps, {"clic_max_pc": 1.0}, 1)
        self.assertEqual((vres["notes"], vres["v_ism_provenance"]), ([], "assumed"))
        self.assertEqual(vel["provenance"], "uvw")

    def test_failed_companion_carries_its_failure_class(self):
        self.assertEqual(es._failure_class("SIMBAD request timed out. Try again."), "timeout")
        self.assertEqual(es._failure_class("Could not connect to SIMBAD."), "unreachable")
        self.assertEqual(es._failure_class("boom"), "error")
        comps = [{"id": "H", "domain": "main_sequence", "cr26": None,
                  "_cr24_vel": {"role": "head", "target": "* sig Dra"}},
                 {"id": "B", "domain": "main_sequence", "cr26": None,
                  "_cr24_vel": {"role": "companion", "target": None, "failed": True, "name": "X B",
                                "status": "timeout"}}]
        with mock.patch.object(iv, "_velocity_seam", velocity_seam), \
                mock.patch.object(iv, "_identity_seam", identity_seam):
            _v, bvel = es._cr24_component_ism(comps[1], comps, {}, 2)
        self.assertEqual((bvel["provenance"], bvel["status"]), ("unavailable", "timeout"))

    def test_head_fetched_only_for_the_lend_reports_it(self):
        comps = [{"id": "*  70 Oph", "domain": "main_sequence", "cr26": None,
                  "_cr24_vel": {"role": "head", "target": "*  70 Oph"}},
                 {"id": "*  70 Oph B", "domain": "main_sequence", "cr26": None,
                  "_cr24_vel": {"role": "companion", "target": "*  70 Oph B", "name": "*  70 Oph B"}}]
        with mock.patch.object(iv, "_velocity_seam", velocity_seam), \
                mock.patch.object(iv, "_identity_seam", identity_seam):
            hv, hvel = es._cr24_component_ism(comps[0], comps, {"v_ism": 30.0}, 2)   # step 1 → not looked up
            self.assertIsNone(hvel)
            comps[0]["vel"] = hvel
            es._cr24_component_ism(comps[1], comps, {}, 2)                            # B's lend fetches the head
        comps[0].update(wall_inputs=None, cr26_fields={"wind_model": {"notes": []}})
        out = es._cr24_component_fields(comps[0])
        self.assertEqual(out["velocity_status"], "ok")

    def test_same_record_head_lends_without_a_note(self):
        (hv, hvel), (bv, bvel) = self._pair("* alf CMa", "*  70 Oph B")
        self.assertFalse(any("own SIMBAD record" in n for n in hvel["notes"]))
        self.assertEqual(bvel["space_velocity"]["rv_source"], "primary")

    def test_head_with_a_gated_a_record_takes_the_floor(self):
        with mock.patch.dict(os.environ, {"SPACE_APP_CR24_INJECT_RV": "*  70 Oph A=-9.73:E"}):
            (hv, hvel), (bv, bvel) = self._pair("*  70 Oph", "*  70 Oph B")
        self.assertEqual(hvel["provenance"], "tangential_lower_bound")  # D-W3-3: never borrows B's
        self.assertEqual(bvel["provenance"], "tangential_lower_bound")


if __name__ == "__main__":
    unittest.main()
