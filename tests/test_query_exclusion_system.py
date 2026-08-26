# tests/test_query_exclusion_system.py — CR-11.3 exclusion-system query.py contract.
#
# Offline subprocess tests: happy-path JSON (the Sirius & α Cen --component anchors), core parity,
# and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse). The live --star path
# is gated in test_query_exclusion_system_live.py.

import unittest

import core.exclusion_system as es

from tests._queryharness import make_env, run_query

_ENV = make_env("cr11_excl_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class ExclusionSystemQueryTest(unittest.TestCase):
    def test_sirius_happy_and_parity(self):
        rc, d, _ = _run("exclusion-system",
                        "--component", "id=A,mass=2.063,lum=25.4,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59",
                        "--component", "id=B,mass=1.018,class=wd,pair=AB,sma=19.8,ecc=0.59")
        self.assertEqual(rc, 0)
        self.assertEqual(d["n_zones"], 1)
        z = d["zones"][0]
        self.assertEqual(z["status"], "merged")
        self.assertAlmostEqual(z["long_axis_au"]["apastron"], 73.9, places=0)
        b = next(c for c in z["components"] if c["id"] == "B")
        self.assertEqual(b["domain"], "out_of_domain")
        self.assertIsNone(b["r_ex_au"])
        # parity with the core
        ref = es.compute_exclusion_system(component_specs=[
            "id=A,mass=2.063,lum=25.4,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59",
            "id=B,mass=1.018,class=wd,pair=AB,sma=19.8,ecc=0.59"])
        self.assertAlmostEqual(z["point_mass_r_ex_au"], ref["zones"][0]["point_mass_r_ex_au"], places=9)

    def test_alpha_cen_two_zones(self):
        rc, d, _ = _run("exclusion-system",
                        "--component", "id=A,mass=1.079,lum=1.5,class=G2V,pair=AB,sma=23.6,ecc=0.52",
                        "--component", "id=B,mass=0.909,lum=0.5,class=K1V,pair=AB,sma=23.6,ecc=0.52",
                        "--component", "id=Proxima,mass=0.122,lum=0.0017,class=M5.5V,orbits=AB,sma=13000,ecc=0.5")
        self.assertEqual(rc, 0)
        self.assertEqual(d["n_zones"], 2)
        ab = next(z for z in d["zones"] if sorted(z["members"]) == ["A", "B"])
        self.assertAlmostEqual(ab["point_mass_r_ex_au"], 62.53, places=1)
        px = next(z for z in d["zones"] if z["members"] == ["Proxima"])
        self.assertEqual(px["status"], "separate")

    def test_phase_narrowing(self):
        rc, d, _ = _run("exclusion-system", "--phase", "apastron",
                        "--component", "id=A,mass=1.079,class=G2V,pair=AB,sma=23.6,ecc=0.52",
                        "--component", "id=B,mass=0.909,class=K1V,pair=AB,sma=23.6,ecc=0.52")
        self.assertEqual(rc, 0)
        la = d["zones"][0]["long_axis_au"]
        self.assertIn("apastron", la)
        self.assertNotIn("periastron", la)

    def test_exit_code_matrix(self):
        rc, d, _ = _run("exclusion-system", "--component", "id=A,foo=1")   # curated error
        self.assertEqual(rc, 1)
        self.assertIn("error", d)
        rc, d, _ = _run("exclusion-system", "--component", "id=A,mass=1", "--alpha", "0.9")
        self.assertEqual(rc, 1)
        rc, _, _ = _run("exclusion-system")   # neither --star nor --component
        self.assertEqual(rc, 1)

    def test_bad_catalog_path_loud(self):
        rc, d, _ = _run("exclusion-system", "--star-mass-catalog", "/nope/x.json",
                        "--component", "id=A,mass=1,class=G2V")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)


if __name__ == "__main__":
    unittest.main()
