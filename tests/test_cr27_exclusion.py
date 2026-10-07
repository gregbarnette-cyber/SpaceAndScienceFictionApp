"""CR-27.3 (+ CR-27.4 from stage 3) — exclusion: the mass ladder is not gated on the luminosity; luminosity = best
available + provenance (plan §3). Offline, in-process: SIMBAD / regions / FLAME / the catalog are stubbed at their
module seams; every expected standoff is recomputed through the FROZEN generator from the stubbed inputs."""
import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

import query
import core.exclusion_boundary as eb
import core.exclusion_system as es

_R_V = "Apparent Magnitude (V) not available"


def _rex(mass, alpha=0.4, lum=1.0, beta=0.0):
    return eb.compute_exclusion_boundary(mass_msun=mass, luminosity_lsun=lum, alpha=alpha, beta=beta)["r_ex_au"]


def _catalog(rows):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump({"stars": [{"main_id": m, "mass_solar": v} for m, v in rows]}, fh)
    return path


def _args(**over):
    a = argparse.Namespace(
        mass_msun=None, object=None, star=None, spectral_type=None, luminosity_lsun=None,
        mass_loss_msun_yr=None, wind_state=None, wind_speed=None, v_ism=None, c_ms=None,
        b_field=None, n_cloud=None, cloud_temp=None, wind_phase_yr=None, f_shock=None,
        m_shock_min=None, mass_loss_source=None, dial=None, calibration_au=47.5,
        alpha=0.4, beta=0.0, gamma=0.0, scan_alpha=False, star_mass_catalog=None, gaia_timeout=None)
    for k, v in over.items():
        setattr(a, k, v)
    return a


class _Star:
    """One stubbed star: its SIMBAD record, its regions result, its FLAME answer (or a bounded reason)."""

    def __init__(self, name, main_id, sp, regions=None, mass_flame=None, lum_flame=None, gaia_id="1",
                 bounded=None, otype="PM*"):
        self.name, self.main_id = name, main_id
        self.sl = {"main_id": main_id, "sp_type": sp, "otype": otype, "plx_value": 100.0, "ra": 1.0, "dec": 2.0,
                   "designations": {"MAIN_ID": main_id, "Gaia EDR3": f"Gaia DR3 {gaia_id}" if gaia_id else None}}
        self.regions = regions if regions is not None else {"error": _R_V}
        self.mass_flame, self.lum_flame, self.gaia_id, self.bounded = mass_flame, lum_flame, gaia_id, bounded
        self.gaia_calls = 0

    def _ga(self, **k):
        self.gaia_calls += 1
        if self.bounded:
            return {"error": f"Gaia TAP {self.bounded}", "gaia_bound_reason": self.bounded}
        if self.mass_flame is None and self.lum_flame is None:
            return {"parameters": None}
        return {"parameters": {"mass_flame": self.mass_flame, "lum_flame": self.lum_flame}}

    def patches(self):
        return [
            mock.patch("core.databases.compute_simbad_lookup",
                       lambda n: dict(self.sl) if n == self.name else {"error": f"No results for '{n}'"}),
            mock.patch("core.regions.compute_star_system_regions_from_simbad", lambda sl: dict(self.regions)),
            mock.patch("core.binary.gaia_source_id_from_designations", lambda d: self.gaia_id),
            mock.patch("core.catalog.gaia_astrophysical", self._ga),
            mock.patch("core.databases.fetch_star_otypes",
                       lambda main_id, primary_otype=None, component_rule=True: None),
            mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": []}),
        ]


def _boundary(star, cat=None, **over):
    cap = {}
    ps = star.patches() + [mock.patch("query._out", lambda r: cap.__setitem__("r", r))]
    for p in ps:
        p.start()
    try:
        query.cmd_exclusion_boundary(_args(star=star.name, star_mass_catalog=cat, **over))
    finally:
        for p in reversed(ps):
            p.stop()
    return cap["r"]


def _system(star, cat=None, alpha=0.4):
    ps = star.patches()
    for p in ps:
        p.start()
    try:
        return es.compute_exclusion_system(star=star.name, star_mass_catalog=cat, alpha=alpha)
    finally:
        for p in reversed(ps):
            p.stop()


def BL_CET(**k):
    return _Star("BL Cet", "BL Cet", "M5.5Ve", **k)


class Cr273LadderNotGatedTest(unittest.TestCase):
    """acc 1, 2, 4: a catalog star with no V row resolves its mass; luminosity null (no FLAME values)."""

    def setUp(self):
        self.cat = _catalog([("BL Cet", 0.1225), ("* alf Lyr", 2.135), ("* del Pav", 0.99)])

    def tearDown(self):
        os.unlink(self.cat)

    def test_catalog_star_with_no_v(self):
        s = BL_CET()
        r = _boundary(s, self.cat)
        self.assertNotIn("error", r)
        self.assertEqual(r["mass_provenance"], "catalog")
        self.assertEqual(r["mass_msun"], 0.1225)
        self.assertEqual(r["r_ex_au"], _rex(0.1225))
        self.assertIsNone(r["luminosity_lsun"])
        self.assertIsNone(r["luminosity_provenance"])
        self.assertNotIn("luminosity_status", r)
        self.assertNotIn("flame_status", r)
        self.assertEqual(s.gaia_calls, 1)                    # the new luminosity-tier fetch (mass came from catalog)

    def test_regions_bc_luminosity_with_catalog_mass(self):   # acc 3 (Vega): no Gaia call at all
        s = _Star("Vega", "* alf Lyr", "A0Va", regions={"bcLuminosity": 80.39434637781383})
        r = _boundary(s, self.cat)
        self.assertEqual((r["mass_provenance"], r["mass_msun"]), ("catalog", 2.135))
        self.assertEqual(r["r_ex_au"], _rex(2.135))
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (80.39434637781383, "regions_bc"))
        self.assertEqual(s.gaia_calls, 0)

    def test_bad_argument_never_costs_the_flame_fetch(self):  # CP0 F-A7
        s = BL_CET()
        r = _boundary(s, self.cat, alpha=-1.0)
        self.assertIn("Scaling exponents", r["error"])
        self.assertEqual(s.gaia_calls, 0)

    def test_luminosity_status_never_on_an_unrelated_argument_error(self):   # CP2 #1 / #2
        s = BL_CET(bounded="unreachable")
        r = _boundary(s, self.cat, mass_loss_msun_yr=-1.0)
        self.assertEqual(r["error"], "--mass-loss-msun-yr must be > 0.")
        self.assertNotIn("luminosity_status", r)
        self.assertEqual(s.gaia_calls, 0)                    # the full arg check runs before the FLAME fetch

    def test_a_raising_mass_fetch_is_not_repeated(self):      # CP2 #3
        s = _Star("HD 219134", "HD 219134", "K3V", regions={"error": _R_V})
        calls = {"n": 0}

        def _boom(**k):
            calls["n"] += 1
            raise RuntimeError("parse error")
        ps = s.patches()
        for p in ps:
            p.start()
        try:
            from core import catalog, stellar_mass
            with mock.patch.object(catalog, "gaia_astrophysical", _boom):
                st = {}
                spec = {"name": "HD 219134", "designations": {"MAIN_ID": "HD 219134"}}
                self.assertEqual(stellar_mass.resolve_component_mass(spec, None, status_out=st)[0], None)
                self.assertEqual(stellar_mass.flame_luminosity(spec["designations"], status_out=st), (None, None))
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(calls["n"], 1)

    def test_bounded_luminosity_fetch_flagged_on_own_key(self):   # acc 13 (BL Cet leg)
        s = BL_CET(bounded="unreachable")
        r = _boundary(s, self.cat)
        self.assertEqual(r["r_ex_au"], _rex(0.1225))
        self.assertIsNone(r["luminosity_lsun"])
        self.assertEqual(r["luminosity_status"], "unreachable")
        self.assertNotIn("flame_status", r)

    def test_evolved_flame_luminosity_and_beta(self):          # acc 9, 10, 13 (δ Pav legs)
        s = _Star("delta Pav", "* del Pav", "G8IV", regions={"bcLuminosity": 1.6}, lum_flame=1.2535083293914795)
        r = _boundary(s, self.cat)
        self.assertEqual(r["domain"], "evolved")
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (1.2535083293914795, "gaia_flame"))
        self.assertEqual(r["r_ex_au"], _rex(0.99))           # β = 0: the standoff does not use L
        r = _boundary(s, self.cat, beta=0.5)
        self.assertEqual(r["r_ex_au"], _rex(0.99, lum=1.2535083293914795, beta=0.5))
        sb = _Star("delta Pav", "* del Pav", "G8IV", bounded="unreachable")
        r = _boundary(sb, self.cat, beta=0.5)
        self.assertEqual(r["error"], "--luminosity-lsun must be > 0 when --beta ≠ 0.")
        self.assertEqual(r["luminosity_status"], "unreachable")
        self.assertNotIn("flame_status", r)
        r = _boundary(sb, self.cat)                          # β 0 under the hook: a result, the null flagged
        self.assertIsNone(r["luminosity_lsun"])
        self.assertEqual(r["luminosity_status"], "unreachable")

    def test_evolved_no_gaia_id_is_null_and_beta_errors(self):  # acc 9, 10 (Procyon legs)
        s = _Star("delta Pav", "* del Pav", "G8IV", gaia_id=None)
        r = _boundary(s, self.cat)
        self.assertIsNone(r["luminosity_lsun"])
        self.assertNotIn("luminosity_status", r)
        self.assertEqual(s.gaia_calls, 0)
        r = _boundary(s, self.cat, beta=0.5)
        self.assertEqual(r["error"], "--luminosity-lsun must be > 0 when --beta ≠ 0.")
        self.assertNotIn("luminosity_status", r)


class Cr273FlameAndInversionTest(unittest.TestCase):
    """acc 5, 6, 7, 8, 13, 14, 15, 17."""

    def test_inversion_of_regions_bc(self):                  # acc 5 / 6
        s = _Star("HD 219134", "HD 219134", "K3V", regions={"bcLuminosity": 0.4594210608083141})
        r = _boundary(s)
        m = 0.4594210608083141 ** 0.2632
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(r["mass_msun"], m)
        self.assertEqual(r["r_ex_au"], _rex(m))
        self.assertEqual(r["luminosity_provenance"], "regions_bc")
        sysr = _system(s)
        c = sysr["zones"][0]["components"][0]
        self.assertEqual((c["mass_solar"], c["r_ex_au"]), (m, r["r_ex_au"]))   # the same on exclusion-system

    def test_flame_mass_and_luminosity_one_fetch(self):       # acc 7 / 15 (HD 19902, ρ CrB)
        s = _Star("HD 19902", "HD 19902", "G5V", mass_flame=0.900922954082489, lum_flame=0.7385019)
        r = _boundary(s)
        self.assertEqual((r["mass_provenance"], r["mass_msun"]), ("gaia_flame", 0.900922954082489))
        self.assertEqual(r["r_ex_au"], _rex(0.900922954082489))
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (0.7385019, "gaia_flame"))
        self.assertEqual(s.gaia_calls, 1)                    # the mass tier's fetch is reused

    def test_regions_bc_precedes_flame_luminosity(self):     # acc 8 (61 Cyg A)
        s = _Star("61 Cyg A", "*  61 Cyg A", "K5V", regions={"bcLuminosity": 0.182265261647455},
                  mass_flame=0.7, lum_flame=0.15068895)
        r = _boundary(s)
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (0.182265261647455, "regions_bc"))
        self.assertEqual(r["mass_provenance"], "gaia_flame")

    def test_bounded_flame_falls_to_inversion_with_flame_status(self):   # acc 13 (61 Cyg A leg)
        s = _Star("61 Cyg A", "*  61 Cyg A", "K5V", regions={"bcLuminosity": 0.182265261647455},
                  bounded="unreachable")
        r = _boundary(s)
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(r["flame_status"], "unreachable")
        self.assertEqual(r["luminosity_provenance"], "regions_bc")
        self.assertNotIn("luminosity_status", r)

    def test_bounded_flame_mass_error_both_subcommands(self):  # acc 13 (HD 19902 legs)
        s = _Star("HD 19902", "HD 19902", "G5V", bounded="unreachable")
        r = _boundary(s)
        self.assertTrue(r["error"].startswith("could not resolve a mass for 'HD 19902'"))
        self.assertIn("the Gaia FLAME fetch was unreachable", r["error"])
        self.assertIn("--mass-msun <M☉> instead of --star", r["error"])
        self.assertIn(_R_V, r["error"])
        self.assertEqual(r["flame_status"], "unreachable")
        r = _system(s)
        self.assertIn("the Gaia FLAME fetch was unreachable", r["error"])
        self.assertNotIn("no Gaia FLAME", r["error"])
        self.assertEqual(r["flame_status"], "unreachable")

    def test_no_route_stars_both_subcommands(self):           # acc 14 (HD 79210 has a FLAME L, never inverted)
        s = _Star("HD 79210", "HD 79210", "M0V", lum_flame=0.0813)
        r = _boundary(s)
        self.assertIn("could not resolve a mass", r["error"])
        self.assertIn("no FLAME mass", r["error"])
        self.assertNotIn("flame_status", r)
        r = _system(s)
        self.assertIn("no Gaia FLAME", r["error"])          # Q8: today's text when the archive answered
        self.assertNotIn("flame_status", r)
        s = _Star("HD 79211", "HD 79211", "M0V")
        for over in ({"luminosity_lsun": 0.5}, {"beta": 0.5}):   # ruling 10(a): never inverted; ladder first
            with self.subTest(**over):
                r = _boundary(s, **over)
                self.assertIn("could not resolve a mass", r["error"])

    def test_supplied_luminosity_never_feeds_the_inversion(self):   # acc 17 (EZ Aqr)
        s = _Star("EZ Aqr", "EZ Aqr", "M5V", regions={"bcLuminosity": 0.0012})
        r = _boundary(s, luminosity_lsun=0.5)
        m = 0.0012 ** 0.2632
        self.assertEqual((r["mass_msun"], r["mass_provenance"]), (m, "ms_luminosity_inversion"))
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (0.5, "manual"))
        self.assertEqual(r["r_ex_au"], _rex(m))


class Cr273OtherPathsTest(unittest.TestCase):
    """acc 10, 11, 16 and the compute_two_layer_boundary echo."""

    def _run(self, **over):
        cap = {}
        with mock.patch("query._out", lambda r: cap.__setitem__("r", r)):
            query.cmd_exclusion_boundary(_args(**over))
        return cap["r"]

    def test_bare_mass(self):
        r = self._run(mass_msun=0.3)
        self.assertEqual(r["r_ex_au"], 29.345540401952064)
        self.assertIsNone(r["luminosity_lsun"])
        self.assertIsNone(r["luminosity_provenance"])
        self.assertEqual(self._run(mass_msun=0.3, beta=0.5)["error"], "--luminosity-lsun must be > 0 when --beta ≠ 0.")
        self.assertEqual(self._run(mass_msun=0.3, beta=0.5, luminosity_lsun=0.5)["r_ex_au"], 20.75043061580411)
        self.assertEqual(self._run(mass_msun=0.3, beta=0.5, luminosity_lsun=1.0)["r_ex_au"], 29.345540401952064)
        r = self._run(mass_msun=0.3, luminosity_lsun=0.5)
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"], r["r_ex_au"]),
                         (0.5, "manual", 29.345540401952064))
        self.assertIn("Scaling exponents", self._run(mass_msun=0.3, beta=0.5, alpha=-1.0)["error"])  # order kept

    def test_spectral_type_and_object(self):
        r = self._run(spectral_type="M5V")
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"], r["r_ex_au"]),
                         (0.013, "spectral_type_table", 30.112970656761156))
        r = self._run(object="sun")
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"], r["r_ex_au"]), (1.0, "object_preset", 47.5))
        r = self._run(object="brown-dwarf")
        self.assertNotIn("luminosity_lsun", r)
        self.assertNotIn("luminosity_provenance", r)
        self.assertIsNone(r["system_entry"])

    def test_two_layer_reports_the_callers_luminosity(self):
        a = eb.compute_two_layer_boundary(mass_msun=0.5, alpha=0.4)
        b = eb.compute_two_layer_boundary(mass_msun=0.5, luminosity_lsun=1.0, alpha=0.4, luminosity_provenance="manual")
        self.assertEqual(a["r_ex_au"], b["r_ex_au"])
        self.assertIsNone(a["luminosity_lsun"])
        self.assertIsNone(a["luminosity_provenance"])
        self.assertEqual((b["luminosity_lsun"], b["luminosity_provenance"]), (1.0, "manual"))
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=0.5, beta=0.5)["error"],
                         "--luminosity-lsun must be > 0 when --beta ≠ 0.")
        w = eb.compute_two_layer_boundary(sp_type="DA")
        self.assertNotIn("luminosity_lsun", w)


class Cr273OffMsNoteTest(unittest.TestCase):
    """CP0 F-A1: the off-MS lone-body note names a bounded FLAME fetch (Q8's second text)."""

    def test_off_ms_note_bounded(self):
        s = _Star("Sirius B", "* alf CMa B", "DA2", bounded="timeout")
        r = _system(s)
        self.assertTrue(any("the Gaia FLAME fetch timed out" in n for n in r["resolution_notes"]))
        self.assertEqual(r["flame_status"], "timeout")
        s = _Star("Sirius B", "* alf CMa B", "DA2")
        r = _system(s)
        self.assertTrue(any("no Gaia FLAME" in n for n in r["resolution_notes"]))


if __name__ == "__main__":
    unittest.main()


# ── CR-27.4 (plan §4.7): the real identity step, driven through the CR-24 identity seam ─────────────────────────────
import pytest  # noqa: E402
from core import ism_velocity as iv  # noqa: E402


class _World:
    """Several SIMBAD records keyed by query name, regions by main_id, FLAME by main_id, and the A-candidate answers
    (``idents``: candidate → record / None (empty) / "timeout" | "unreachable" (failed))."""

    def __init__(self, records, regions=None, flame=None, idents=None, orbit=None):
        self.records, self.regions, self.flame = records, regions or {}, flame or {}
        self.idents = idents or {}
        self.orbit = orbit
        self.ident_calls = []

    def _sl(self, name):
        r = self.records.get(name)
        return dict(r) if r else {"error": f"No results for '{name}'"}

    def _ident(self, cand):
        self.ident_calls.append(cand)
        v = self.idents.get(cand)
        if isinstance(v, str):
            return None, v
        return (dict(v) if v else None), None

    def _ga(self, source_id=None, **k):
        mf, lf = self.flame.get(source_id, (None, None))
        return {"parameters": {"mass_flame": mf, "lum_flame": lf}} if (mf or lf) else {"parameters": None}

    def patches(self):
        return [
            mock.patch("core.databases.compute_simbad_lookup", self._sl),
            mock.patch("core.regions.compute_star_system_regions_from_simbad",
                       lambda sl: dict(self.regions.get(sl.get("main_id"), {"error": _R_V}))),
            mock.patch("core.binary.gaia_source_id_from_designations",
                       lambda d: (d or {}).get("MAIN_ID")),            # the main_id stands in for the Gaia id
            mock.patch("core.catalog.gaia_astrophysical", self._ga),
            mock.patch("core.databases.fetch_star_otypes",
                       lambda main_id, primary_otype=None, component_rule=True: None),
            mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": []}),
            mock.patch.object(iv, "_identity_seam", self._ident),
        ] + ([mock.patch.object(es, "_select_orbit_masses", lambda sols, sp: (self.orbit, None))] if self.orbit else [])

    def run(self, fn):
        ps = self.patches()
        for p in ps:
            p.start()
        try:
            return fn()
        finally:
            for p in reversed(ps):
                p.stop()


def _rec(main_id, sp, otype="PM*", plx=100.0):
    return {"main_id": main_id, "sp_type": sp, "otype": otype, "plx_value": plx, "ra": 1.0, "dec": 2.0,
            "designations": {"MAIN_ID": main_id}}


_HEAD_GJ65 = _rec("G 272-61", "M5.5V+M6V", otype="**")
_A_GJ65 = _rec("G 272-61A", "M5.5Ve", otype="Er*")
_HEAD_ACEN = _rec("* alf Cen", "G2V+K1V", otype="**")
_A_ACEN = _rec("* alf Cen A", "G2V")
_HEAD_70OPH = _rec("*  70 Oph", "K0V+K4V", otype="**")
_A_70OPH = _rec("*  70 Oph A", "K0V")


def _b(world, name, cat=None, **over):
    cap = {}

    def go():
        with mock.patch("query._out", lambda r: cap.__setitem__("r", r)):
            query.cmd_exclusion_boundary(_args(star=name, star_mass_catalog=cat, **over))
        return cap["r"]
    return world.run(go)


def _s(world, name, cat=None):
    return world.run(lambda: es.compute_exclusion_system(star=name, star_mass_catalog=cat, alpha=0.4))


def _numeric_equal(test, a, b):
    """Every key except the input echo (object) and system_entry is equal (CR-27.4 'every numeric field')."""
    strip = lambda d: {k: v for k, v in d.items() if k not in ("object", "system_entry")}
    test.assertEqual(json.loads(json.dumps(strip(a), default=str)), json.loads(json.dumps(strip(b), default=str)))


@pytest.mark.cr27_identity
class Cr274SystemEntryTest(unittest.TestCase):

    def setUp(self):
        self.cat = _catalog([("G 272-61A", 0.1225), ("* alf Cen A", 1.079)])

    def tearDown(self):
        os.unlink(self.cat)

    def test_gj65_resolves_to_component_a(self):                     # acc 1
        w = _World({"GJ 65": _HEAD_GJ65, "G 272-61A": _A_GJ65}, idents={"G 272-61 A": _A_GJ65})
        r = _b(w, "GJ 65", self.cat)
        self.assertEqual(r["system_entry"]["main_id"], "G 272-61")
        self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
        self.assertIn("resolved to component A of the multiple-system entry G 272-61", r["system_entry"]["note"])
        self.assertIn("for the merged system zone use exclusion-system", r["system_entry"]["note"])
        self.assertEqual((r["mass_provenance"], r["mass_msun"]), ("catalog", 0.1225))
        self.assertEqual(r["r_ex_au"], _rex(0.1225))
        self.assertEqual(r["object"], "GJ 65")                          # Q5: the input echo
        _numeric_equal(self, r, _b(w, "G 272-61A", self.cat))

    def test_alpha_cen_never_inverts_combined_light(self):          # acc 3
        w = _World({"alpha Cen": _HEAD_ACEN, "alpha Cen A": _A_ACEN},
                   regions={"* alf Cen": {"bcLuminosity": 1.6972331397713882},
                            "* alf Cen A": {"bcLuminosity": 1.5694037031455939}},
                   idents={"* alf Cen A": _A_ACEN})
        r = _b(w, "alpha Cen", self.cat)
        self.assertEqual(r["system_entry"]["component_used"], "* alf Cen A")
        self.assertEqual(r["sp_type"] if "sp_type" in r else _A_ACEN["sp_type"], "G2V")
        self.assertEqual((r["mass_provenance"], r["mass_msun"]), ("catalog", 1.079))
        self.assertEqual(r["r_ex_au"], 48.966852301574924)
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (1.5694037031455939, "regions_bc"))
        _numeric_equal(self, r, _b(w, "alpha Cen A", self.cat))

    def test_70_oph_takes_a_flame_mass(self):                        # acc 4
        w = _World({"70 Oph": _HEAD_70OPH, "70 Oph A": _A_70OPH},
                   regions={"*  70 Oph": {"bcLuminosity": 0.6}},
                   flame={"*  70 Oph A": (0.8256458044052124, 0.5142145156860352)},
                   idents={"* 70 Oph A": _A_70OPH})
        r = _b(w, "70 Oph")
        self.assertEqual((r["mass_provenance"], r["mass_msun"]), ("gaia_flame", 0.8256458044052124))
        self.assertEqual(r["r_ex_au"], _rex(0.8256458044052124))
        self.assertEqual((r["luminosity_lsun"], r["luminosity_provenance"]), (0.5142145156860352, "gaia_flame"))
        self.assertNotEqual(r["r_ex_au"], _rex(0.6 ** 0.2632))

    def test_exclusion_system_single_body_a(self):                   # acc 5
        w = _World({"GJ 65": _HEAD_GJ65}, idents={"G 272-61 A": _A_GJ65})
        r = _s(w, "GJ 65", self.cat)
        self.assertNotIn("error", r)
        self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
        self.assertTrue(any("resolved to component A of the multiple-system entry G 272-61" in n
                            for n in r["resolution_notes"]))
        c = r["zones"][0]["components"][0]
        self.assertEqual((c["mass_solar"], c["mass_provenance"]), (0.1225, "catalog"))
        self.assertEqual(c["r_ex_au"], _rex(0.1225))

    def test_same_empty_own_heads_unchanged(self):                   # acc 6
        sirius = _rec("* alf CMa", "A0mA1Va")
        w = _World({"Sirius": sirius}, regions={"* alf CMa": {"bcLuminosity": 25.0}},
                   idents={"* alf CMa A": sirius})
        r_same = _b(w, "Sirius", self.cat)
        self.assertIsNone(r_same["system_entry"])
        dpav = _rec("* del Pav", "G8IV")
        w2 = _World({"delta Pav": dpav}, idents={"* del Pav A": None})
        self.assertIsNone(_b(w2, "delta Pav", self.cat)["system_entry"])
        w3 = _World({"61 Cyg A": _rec("*  61 Cyg A", "K5V")}, regions={"*  61 Cyg A": {"bcLuminosity": 0.18}})
        r = _b(w3, "61 Cyg A")
        self.assertIsNone(r["system_entry"])
        self.assertEqual(w3.ident_calls, [])                             # own → no lookup

    def test_failed_a_lookup_errors_everywhere_it_decides_identity(self):   # acc 7
        acen = _World({"alpha Cen": _HEAD_ACEN}, idents={"* alf Cen A": "unreachable"})
        dpav = _World({"delta Pav": _rec("* del Pav", "G8IV")}, idents={"* del Pav A": "unreachable"})
        sirius = _World({"Sirius": _rec("* alf CMa", "A0mA1Va")}, idents={"* alf CMa A": "unreachable"})
        for name, w, over in (("alpha Cen", acen, {}), ("delta Pav", dpav, {}),
                              ("Sirius", sirius, {"v_ism": 26.0}), ("Sirius", sirius, {"lb_cavity": True})):
            with self.subTest(star=name, **over):
                r = _b(w, name, self.cat, **over)
                self.assertIn("the SIMBAD identity lookup for the A candidate", r["error"])
                self.assertIn("(unreachable)", r["error"])
                self.assertEqual(r["component_a_status"], "unreachable")
        gj = _World({"GJ 65": _HEAD_GJ65}, idents={"G 272-61 A": "timeout"})
        r = _s(gj, "GJ 65", self.cat)
        self.assertEqual(r["component_a_status"], "timeout")
        self.assertNotIn("could not resolve a mass", r["error"])
        luh = _World({"Luhman 16": _rec("NAME Luhman 16", "L7.5+T0.5", otype="BD*")},
                     idents={"NAME Luhman 16 A": "unreachable"})
        r = _s(luh, "Luhman 16")
        self.assertEqual(r["component_a_status"], "unreachable")     # the off-MS single body (ruling 10(b))

    def test_composed_system_unchanged_under_a_failed_lookup(self):     # acc 7 (composed leg)
        orbit = {"m1_solar": 1.1, "m2_solar": 0.9, "mass_prov_a": "binary_orbit_m1",
                 "mass_prov_b": "binary_orbit_m2", "sma_au": 23.4, "ecc": 0.52, "mass_basis": "x", "notes": []}
        w = _World({"alpha Cen": _HEAD_ACEN, "* alf Cen B": _rec("* alf Cen B", "K1V")},
                   idents={"* alf Cen A": "unreachable"}, orbit=orbit)
        r = _s(w, "alpha Cen", self.cat)
        self.assertNotIn("error", r)
        self.assertIsNone(r["system_entry"])
        comps = [c for z in r["zones"] for c in z["components"]]
        self.assertEqual(comps[0]["mass_solar"], 1.079)                   # A's own catalog mass (composed path)
        self.assertEqual(len(comps), 2)

    def test_q9_mirror_off_ms_head_with_ms_a(self):                  # Q9 clarification
        head = _rec("WD 9999", "DA+M3V", otype="**")
        a = _rec("WD 9999A", "M3V")
        cat = _catalog([("WD 9999A", 0.3)])
        try:
            w = _World({"WD 9999": head}, idents={"WD 9999 A": a})
            r = _s(w, "WD 9999", cat)
        finally:
            os.unlink(cat)
        c = r["zones"][0]["components"][0]
        self.assertEqual((c["mass_solar"], c["domain"]), (0.3, "main_sequence"))
        self.assertEqual(r["system_entry"]["component_used"], "WD 9999A")

    def test_letterless_a_record_used_as_returned(self):            # CP0 F-A2 (BD+59 1915 → HD 173739)
        head = _rec("BD+59  1915", None, otype="**")
        a = _rec("HD 173739", "M3V")
        cat = _catalog([("HD 173739", 0.3)])
        try:
            w = _World({"BD+59 1915": head}, idents={"BD+59 1915 A": a})
            r = _b(w, "BD+59 1915", cat)
        finally:
            os.unlink(cat)
        self.assertEqual(r["system_entry"]["component_used"], "HD 173739")
        self.assertEqual(r["mass_msun"], 0.3)

    def test_system_entry_rides_on_errors(self):                     # the one rule (CP0 F-A5)
        w = _World({"GJ 65": _HEAD_GJ65}, idents={"G 272-61 A": _A_GJ65})
        r = _b(w, "GJ 65")                                             # no catalog row, V-less A → mass error
        self.assertIn("could not resolve a mass", r["error"])
        self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
        r = _s(w, "GJ 65")
        self.assertIn("could not resolve a mass", r["error"])
        self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
        plain = _World({"X": _rec("HD 1", "M3V")}, idents={"HD 1 A": None})
        r = _b(plain, "X")
        self.assertNotIn("system_entry", r)                              # no error ever carries a null


@pytest.mark.cr27_identity
@pytest.mark.cr24_velocity
class Cr274OneLookupPerCallTest(unittest.TestCase):
    """CP0 F-C H2: the head's candidate is asked ONCE per --star call — the identity step's answer is reused by the
    CR-24 velocity (red without the reuse: 2). CR-26's half is its own test below (a_prefetch)."""

    def test_one_identity_lookup(self):
        heads = (("Sirius", _rec("* alf CMa", "A0mA1Va"), "* alf CMa A", {"* alf CMa": {"bcLuminosity": 25.0}}),
                 ("delta Pav", _rec("* del Pav", "G8IV"), "* del Pav A", {}),
                 ("Luhman 16", _rec("NAME Luhman 16", "L7.5+T0.5", otype="BD*"), "NAME Luhman 16 A", {}),
                 ("EV Lac", _rec("EV Lac", "M4.0Ve", otype="Er*"), "EV Lac A", {"EV Lac": {"bcLuminosity": 0.014}}))
        for name, head, cand, regions in heads:
            with self.subTest(star=name):
                same = head if name == "Sirius" else None
                w = _World({name: head}, regions=regions, idents={cand: same})
                with mock.patch.object(iv, "_velocity_seam", lambda mid: (None, None)):
                    _b(w, name)
                self.assertEqual(w.ident_calls, [cand])
                w.ident_calls.clear()
                with mock.patch.object(iv, "_velocity_seam", lambda mid: (None, None)):
                    _s(w, name)
                self.assertEqual(w.ident_calls, [cand])


@pytest.mark.cr26_network
class Cr274A26PrefetchTest(unittest.TestCase):
    """CR-26 L974: the keyed prefetch replaces the candidate lookup (allow_network True, same candidate) and sets
    inp.a_record; a different candidate or offline → ignored, as the call would be (CP3 #6 / #9)."""

    _A = {"main_id": "* alf Cen Aa", "designations": {}}            # distinct from the candidate string

    def _run(self, allow, cand="* alf Cen A"):
        from core import xray_catalog as xc
        calls = []
        ident = {"sp_type": "A0V", "main_id": "* alf Cen", "domain": "main_sequence", "candidate": "* alf Cen A",
                 "designations": {}, "a_prefetch": {"candidate": cand, "answer": (dict(self._A), None)}}
        with mock.patch.object(xc, "_identity_lookup", lambda c: calls.append(c) or (None, None)):
            inp = xc.resolve_star_wind_inputs(ident, {}, allow_network=allow)
        return inp, calls

    def test_prefetch_used_online(self):
        inp, calls = self._run(True)
        self.assertEqual(calls, [])
        self.assertEqual(inp.a_record, (self._A, None))
        self.assertIn("* alf Cen Aa", inp.measured_ids)                 # the prefetched record was read

    def test_prefetch_ignored_offline(self):
        inp, calls = self._run(False)
        self.assertEqual(calls, [])
        self.assertNotIn("* alf Cen Aa", inp.measured_ids)              # never read offline
        self.assertIsNone(getattr(inp, "a_record", None))

    def test_prefetch_for_another_candidate_is_not_trusted(self):
        inp, calls = self._run(True, cand="* alf Cen B")
        self.assertEqual(calls, ["* alf Cen A"])                        # the real lookup runs


@pytest.mark.cr27_identity
class Cr274HandoffTest(unittest.TestCase):
    """CP3 #3: the identity step's answer reaches CR-26 (a_prefetch, keyed) on both subcommands — end to end."""

    def _spy(self):
        from core import xray_catalog as xc
        seen, orig = [], xc.resolve_star_wind_inputs
        return seen, mock.patch.object(xc, "resolve_star_wind_inputs",
                                       lambda ident, *a, **k: seen.append(ident) or orig(ident, *a, **k))

    def test_boundary_and_system_hand_off_the_prefetch(self):
        evlac = _rec("EV Lac", "M4.0Ve", otype="Er*")
        for run in (_b, _s):
            with self.subTest(run=run.__name__):
                w = _World({"EV Lac": evlac}, regions={"EV Lac": {"bcLuminosity": 0.014}}, idents={"EV Lac A": None})
                seen, spy = self._spy()
                with spy:
                    run(w, "EV Lac")
                pre = [i.get("a_prefetch") for i in seen if i.get("main_id") == "EV Lac"]
                self.assertTrue(pre)
                self.assertEqual(pre[0], {"candidate": "EV Lac A", "answer": (None, None)})


@pytest.mark.cr27_identity
class Cr274ErrorsCarrySystemEntryTest(unittest.TestCase):
    """CP3 #1 / #4: every error after a resolved system entry carries it — both subcommands, incl. a CR-26 data
    error."""

    def test_later_errors(self):
        from core import stellar_wind_tables as swt
        cat = _catalog([("G 272-61A", 0.1225)])
        try:
            w = _World({"GJ 65": _HEAD_GJ65}, idents={"G 272-61 A": _A_GJ65})
            r = w.run(lambda: es.compute_exclusion_system(
                star="GJ 65", star_mass_catalog=cat, alpha=0.4, dial=-1.0))
            self.assertIn("--dial must be > 0", r["error"])
            self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
            with mock.patch("query._cr26_model", side_effect=swt.Cr26DataError("corrupt cr26 file")):
                r = _b(w, "GJ 65", cat)
            self.assertEqual(r["error"], "corrupt cr26 file")
            self.assertEqual(r["system_entry"]["component_used"], "G 272-61A")
        finally:
            os.unlink(cat)


class Cr27Cp4Test(unittest.TestCase):
    """CP4 folds: the shared β/L constant equals the FROZEN generator's text; a malformed FLAME payload is a miss."""

    def test_beta_lum_constant_is_the_frozen_text(self):
        r = eb.compute_exclusion_boundary(mass_msun=1.0, luminosity_lsun=None, beta=0.5)
        self.assertEqual(r["error"], eb.BETA_LUM_ERROR)

    def test_malformed_flame_payload_is_a_miss(self):
        from core import stellar_mass
        with mock.patch("core.binary.gaia_source_id_from_designations", lambda d: "1"), \
             mock.patch("core.catalog.gaia_astrophysical", lambda **k: {"parameters": ["bad"]}):
            m, prov, _n = stellar_mass.resolve_component_mass(
                {"name": "X", "designations": {"MAIN_ID": "X"}, "luminosity_lsun": 0.5}, None, status_out={})
        self.assertEqual(prov, "ms_luminosity_inversion")
