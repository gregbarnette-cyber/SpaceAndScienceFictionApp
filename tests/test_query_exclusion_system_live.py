# tests/test_query_exclusion_system_live.py — CR-11.3 + CR-13 live --star anchors.
#
# Hits live SIMBAD + binary-orbit. Opt-in: gated on SPACE_APP_RUN_LIVE=1 AND host reachability.
# The Sirius WD-guard behavior is the key live anchor: A resolves main-sequence off its catalog
# mass, B is auto-detected out-of-domain (white dwarf) and contributes no sphere, and the two merge
# into one A-dominated zone whose barycenter still uses B's real mass. Exact long-axis numbers track
# the LIVE binary-orbit elements (which differ from the card's a=19.8/e=0.59); the α Cen + Proxima
# triple needs the --component path (no catalogued Proxima orbit) and is covered offline.

import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr113_excl_live_throwaway.db")


def _reachable(host="simbad.u-strasbg.fr", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    for h in (host, "simbad.cds.unistra.fr"):
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _run(*args):
    return run_query(*args, env=_ENV, timeout=300)


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr113StarSiriusLive(unittest.TestCase):

    def test_sirius_wd_guard_merged(self):
        rc, d, err = _run("exclusion-system", "--star", "Sirius")
        self.assertEqual(rc, 0, err)
        self.assertEqual(d["n_zones"], 1)
        z = d["zones"][0]
        self.assertEqual(z["status"], "merged")
        self.assertEqual(len(z["members"]), 2)
        domains = {c["domain"] for c in z["components"]}
        self.assertEqual(domains, {"main_sequence", "out_of_domain"})   # A MS, B WD-guarded
        wd = next(c for c in z["components"] if c["domain"] == "out_of_domain")
        self.assertIsNone(wd["r_ex_au"])                                # sphere withheld
        ms = next(c for c in z["components"] if c["domain"] == "main_sequence")
        self.assertGreater(ms["r_ex_au"], 55.0)                         # A's sphere (measured ~2.06 M☉)
        # the zone is larger than any single component and breathes
        self.assertGreater(z["long_axis_au"]["apastron"], ms["r_ex_au"])


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr13StarResolutionLive(unittest.TestCase):
    """CR-13 --star robustness — the three headline defects, live, WITHOUT the WB external catalog
    (the internal seed carries α Cen A/B + Sirius A, but not Sirius B or Proxima). The exact-value
    with-catalog anchors (49.0/45.7, {66,74}, 20.48) are WB's re-gate over stellar-mass-catalog.json;
    these verify the fixes are well-formed live and free of the pre-CR-13 garbage/crash."""

    def test_sirius_b_component_name_resolves_single_wd(self):     # D1: no "Sirius B B" / placeholder
        rc, d, err = _run("exclusion-system", "--star", "Sirius B", "--alpha", "0.4")
        self.assertEqual(rc, 0, err)
        self.assertEqual(d["n_components"], 1)
        c = d["zones"][0]["components"][0]
        self.assertIsNone(c["r_ex_au"])                            # WD guard, no sphere
        self.assertEqual((c.get("class_note") or "").lower(), "white dwarf")
        # bare (no external catalog): B is absent from the seed → mass unresolved, not fabricated
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")
        self.assertNotIn("Sirius B B", str(d["zones"][0]["members"]))   # the old doubled designation

    def test_proxima_wide_member_computes_single_body(self):       # D2: no crash, single M-dwarf body
        rc, d, err = _run("exclusion-system", "--star", "Proxima Centauri", "--alpha", "0.4")
        self.assertEqual(rc, 0, err)
        self.assertEqual(d["n_components"], 1)
        c = d["zones"][0]["components"][0]
        # bare → the tool's L-inversion mass (~0.139) → r_ex ~21.6 (WB re-gates the 20.48 catalog value)
        self.assertEqual(c["mass_provenance"], "ms_luminosity_inversion")
        self.assertIsNotNone(c["r_ex_au"])
        self.assertGreater(c["r_ex_au"], 18.0)
        self.assertLess(c["r_ex_au"], 24.0)

    def test_alpha_centauri_star_resolves_real_masses(self):       # D3: not a silent 1.02/1.02
        rc, d, err = _run("exclusion-system", "--star", "alpha Centauri", "--alpha", "0.4")
        self.assertEqual(rc, 0, err)
        self.assertEqual(d["n_components"], 2)                     # A + B (Proxima needs --component)
        masses = sorted(c["mass_solar"] for z in d["zones"] for c in z["components"])
        # seed carries α Cen A 1.079 / B 0.909 — the per-component key-match (CR-13.2) now hits them,
        # so the components are NOT both ~1.02 from the degenerate binary-orbit split.
        self.assertAlmostEqual(masses[0], 0.909, delta=0.05)
        self.assertAlmostEqual(masses[1], 1.079, delta=0.05)
        provs = {c["mass_provenance"] for z in d["zones"] for c in z["components"]}
        self.assertEqual(provs, {"catalog"})


if __name__ == "__main__":
    unittest.main()
