# tests/test_cr25_live.py — CR-25 exclusion wind-wiring fix: LIVE anchors (SIMBAD + Gaia).
#
# Opt-in: gated on SPACE_APP_RUN_LIVE=1 AND SIMBAD reachability (tests/_netcheck). Runs query.py as a
# subprocess with the catalog cache OFF (SPACE_APP_CATALOG_CACHE=0), so a warm cache can never stand in
# for SIMBAD. Anchors: completed_plans/PHASE_CR25_PLAN.md §7 (live) / §9 — the WB re-gate targets (MSG 262 + 264 + 266).
# The standoff (r_ex) anchors are α-TAGGED: exclusion-boundary defaults α=1/3, exclusion-system α=0.4.
# `--star-mass-catalog`: $SPACE_APP_WB_MASS_CATALOG, else the sister repo's deliverable if present.

import os
import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr25_live_throwaway.db", SPACE_APP_CATALOG_CACHE="0",
                HOME=os.environ.get("HOME", ""))
_WB_CAT = os.environ.get("SPACE_APP_WB_MASS_CATALOG") or (
    "/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/"
    "stellar-mass-catalog.json")
_HAVE_CAT = os.path.isfile(_WB_CAT)
_WALL_ACTIVE = 6.0 * 5 ** 0.5          # 13.416… (Ẇ = 1e-13, v = 400) — α-independent
_WALL_QUIET = 6.0 * 0.005 ** 0.5       # 0.424… (Ẇ = 1e-16)


def _reachable(host="simbad.cds.unistra.fr", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    for h in (host, "simbad.u-strasbg.fr"):
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _run(*args, env=None):
    return run_query(*args, env=env or _ENV, timeout=400)


def _b(star, *extra):
    rc, d, err = _run("exclusion-boundary", "--star", star, *extra)
    assert rc == 0 and d is not None and "error" not in d, (star, extra, d, err[-400:])
    return d


def _s(*args):
    rc, d, err = _run("exclusion-system", *args)
    assert rc == 0 and d is not None and "error" not in d, (args, d, err[-400:])
    return d


def _comps(d):
    return {c["id"]: c for z in d["zones"] for c in z["components"]}


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr25BoundaryLive(unittest.TestCase):

    def test_ev_lac_headline(self):
        d = _b("EV Lac")
        self.assertEqual((d["wind_class"], d["wind_class_provenance"], d["wind_otype"], d["wind_otype_source"]),
                         ("active", "otype_auto", ["Er*"], None))
        self.assertAlmostEqual(d["wall_au"], _WALL_ACTIVE, places=6)
        self.assertEqual(d["wall_route"], "wind_term")
        self.assertAlmostEqual(d["r_ex_au"], 32.73, delta=0.01)          # @α=1/3 — standoff unchanged
        self.assertNotIn("otype_status", d)

    def test_ev_lac_overrides(self):
        a = _b("EV Lac", "--wind-state", "active")
        self.assertEqual((a["wind_class"], a["wind_class_provenance"], a["wind_otype"]),
                         ("active", "manual", ["Er*"]))
        q = _b("EV Lac", "--wind-state", "quiet")
        self.assertEqual((q["wind_class"], q["wind_class_provenance"]), ("quiet", "manual"))
        self.assertAlmostEqual(q["wall_au"], _WALL_QUIET, places=6)
        r = _b("EV Lac", "--mass-loss-msun-yr", "1e-13")                  # E1: the label stays identity
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["mass_loss_provenance"]),
                         ("active", "otype_auto", "supplied"))
        self.assertAlmostEqual(r["wall_au"], _WALL_ACTIVE, places=6)

    def test_active_set(self):
        for star, code in (("Proxima Centauri", "Er*"), ("Wolf 359", "Er*"), ("Ross 154", "Er*"),
                           ("AD Leo", "Er*"), ("AU Mic", "Er*"), ("Barnard's star", "BY*"),
                           ("epsilon Eridani", "BY*")):
            d = _b(star)
            self.assertEqual((d["wind_class"], d["wind_class_provenance"]), ("active", "otype_auto"), star)
            self.assertIn(code, d["wind_otype"], star)
            self.assertNotIn("otype_status", d, star)       # a degrade must not pass via the primary BY*
            self.assertAlmostEqual(d["wall_au"], _WALL_ACTIVE, places=6, msg=star)

    def test_eps_eri_standoff_unchanged(self):
        d = _b("epsilon Eridani", "--alpha", "0.4")
        self.assertAlmostEqual(d["r_ex_au"], 43.69, delta=0.1)
        self.assertEqual(d["wind_class"], "active")

    def test_unchanged_stars(self):
        t = _b("tau Ceti")
        self.assertEqual((t["wind_class"], t["wind_class_provenance"], t["wind_otype"]),
                         ("solar", "class_default", None))
        self.assertAlmostEqual(t["wall_au"], 6.0, places=6)
        self.assertEqual(_b("tau Ceti", "--wind-state", "active")["wind_class"], "active")
        for star in ("kap01 Cet", "EK Dra"):                               # Q1: G stars stay solar
            d = _b(star)
            self.assertEqual((d["wind_class"], d["wind_otype"]), ("solar", None), star)
        k = _b("Kapteyn's star")
        self.assertEqual((k["wind_class"], k["wind_class_provenance"]), ("quiet", "class_default"))
        self.assertAlmostEqual(k["wall_au"], _WALL_QUIET, places=6)

    def test_spectral_type_override(self):
        rc, d, err = _run("exclusion-boundary", "--spectral-type", "M4V", "--wind-state", "active")
        self.assertEqual((rc, d["wind_class"], d["wind_class_provenance"]), (0, "active", "manual"), err)
        self.assertEqual(d["mass_loss_msun_yr"], 1e-13)

    @unittest.skipUnless(_HAVE_CAT, "WB stellar-mass-catalog.json not available")
    def test_q7_gamma_pins(self):                                         # EV Lac, α=0.4, γ=0.2 (WB-verified)
        base = ("exclusion-boundary", "--star", "EV Lac", "--alpha", "0.4", "--gamma", "0.2",
                "--star-mass-catalog", _WB_CAT)
        rc, d, err = _run(*base)
        self.assertIn("wind exponent set without", d["error"])            # otype_auto never feeds it
        rc, q, err = _run(*base, "--wind-state", "quiet")
        rc, a, err = _run(*base, "--wind-state", "active")
        self.assertAlmostEqual(q["r_ex_au"], 10.529, delta=0.01)
        self.assertAlmostEqual(a["r_ex_au"], 41.918, delta=0.01)
        self.assertAlmostEqual(a["wall_au"], _WALL_ACTIVE, places=6)

    def test_degrade_hook(self):
        env = dict(_ENV, SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE="1")
        rc, d, err = _run("exclusion-boundary", "--star", "EV Lac", env=env)
        self.assertEqual((rc, d["wind_class"], d["otype_status"]), (0, "quiet", "unreachable"), err)
        for star in ("Barnard's star", "epsilon Eridani"):                # the primary BY* still detects
            rc, d, err = _run("exclusion-boundary", "--star", star, env=env)
            self.assertEqual((d["wind_class"], d["otype_status"]), ("active", "unreachable"), star)


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr25SystemLive(unittest.TestCase):

    def test_ev_lac_consumer_path(self):
        d = _s("--star", "EV Lac")
        c = _comps(d)["V* EV Lac"]
        self.assertEqual((c["wind_class"], c["wind_class_provenance"], c["wind_otype"]),
                         ("active", "otype_auto", ["Er*"]))
        self.assertEqual(c["mass_loss_msun_yr"], 1e-13)
        self.assertAlmostEqual(c["wall_au"], _WALL_ACTIVE, places=6)
        self.assertAlmostEqual(c["r_ex_au"], 30.38, delta=0.01)          # @α=0.4
        q = _comps(_s("--star", "EV Lac", "--wind-state", "quiet"))["V* EV Lac"]
        self.assertEqual((q["wind_class"], q["wind_class_provenance"]), ("quiet", "manual"))

    def test_component_overrides_discriminating_pair(self):              # E6
        g = _comps(_s("--component", "class=G2V,mass=1.0,wind_state=active"))
        m = _comps(_s("--component", "class=M4V,mass=0.2,wind_state=solar"))
        self.assertEqual(list(g.values())[0]["wind_class"], "active")
        self.assertEqual(list(m.values())[0]["wind_class"], "solar")

    @unittest.skipUnless(_HAVE_CAT, "WB stellar-mass-catalog.json not available")
    def test_standoffs_byte_identical(self):                             # @α=0.4
        ac = _comps(_s("--star", "alpha Centauri", "--star-mass-catalog", _WB_CAT))
        self.assertAlmostEqual(ac["* alf Cen"]["r_ex_au"], 48.9669, delta=1e-3)
        self.assertAlmostEqual(ac["* alf Cen B"]["r_ex_au"], 45.7214, delta=1e-3)
        self.assertEqual(ac["* alf Cen B"]["wind_class"], "quiet")
        si = _comps(_s("--star", "Sirius", "--star-mass-catalog", _WB_CAT))
        self.assertAlmostEqual(si["* alf CMa"]["r_ex_au"], 63.46, delta=0.01)
        self.assertEqual(si["* alf CMa B"]["domain"], "windless_free_harbor")
        pr = _comps(_s("--star", "Proxima Centauri", "--star-mass-catalog", _WB_CAT))
        p = list(pr.values())[0]
        self.assertAlmostEqual(p["r_ex_au"], 20.4824, delta=1e-3)
        self.assertEqual(p["wind_class"], "active")


if __name__ == "__main__":
    unittest.main()
