# tests/test_query_exclusion_system.py — CR-11.3 exclusion-system query.py contract.
#
# Offline tests (subprocess, plus in-process `run_query_inproc` for the CR-22.6 mass-guard matrix): happy-path
# JSON (the Sirius & α Cen --component anchors), core parity, and the self-validating exit-code matrix (exit 1
# curated / exit 2 argparse). The live --star path is gated in test_query_exclusion_system_live.py.

import json
import unittest

import core.exclusion_boundary as xb
import core.exclusion_system as es

from tests._queryharness import make_env, run_query, run_query_inproc

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
        self.assertEqual(b["domain"], "windless_free_harbor")   # CR-22: WD → free harbor
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


class Cr23MassProvenanceCliTest(unittest.TestCase):
    """CR-23.2: mass_provenance on every exclusion-boundary path, end-to-end through the CLI (no network)."""

    def test_mass_msun_manual(self):
        rc, d, _ = _run("exclusion-boundary", "--mass-msun", "2", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mass_provenance"], "manual")

    def test_object_preset(self):
        rc, d, _ = _run("exclusion-boundary", "--object", "sun", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mass_provenance"], "object_preset")

    def test_object_windless_object_preset(self):
        rc, d, _ = _run("exclusion-boundary", "--object", "brown-dwarf", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mass_provenance"], "object_preset")

    def test_spectral_type_table(self):
        rc, d, _ = _run("exclusion-boundary", "--spectral-type", "G2V", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mass_provenance"], "spectral_type_table")

    def test_spectral_type_windless_null_key_present(self):
        rc, d, _ = _run("exclusion-boundary", "--spectral-type", "DA2", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertIn("mass_provenance", d)
        self.assertIsNone(d["mass_provenance"])

    def test_gaia_timeout_arg_accepted(self):
        rc, d, _ = _run("exclusion-boundary", "--mass-msun", "1", "--alpha", "0.4", "--gaia-timeout", "5")
        self.assertEqual(rc, 0)         # arg parses (exit 0, not argparse exit 2)

    def test_exclusion_system_evolved_component_standoff_note(self):   # CR-23.3 via --component (offline)
        rc, d, _ = _run("exclusion-system", "--component", "id=Delta,mass=0.991,lum=1.2,type=G8IV",
                        "--alpha", "0.4")
        self.assertEqual(rc, 0)
        c = d["zones"][0]["components"][0]
        self.assertEqual(c["domain"], "evolved")
        self.assertIsNotNone(c["standoff_au"])
        self.assertIsNotNone(c["standoff_note"])
        self.assertIn("research-grade", c["standoff_note"])

    def test_exclusion_system_ms_component_standoff_note_null(self):   # CR-23.3 control
        rc, d, _ = _run("exclusion-system", "--component", "id=e,mass=0.811,lum=0.32,type=K2V",
                        "--alpha", "0.4")
        self.assertEqual(rc, 0)
        c = d["zones"][0]["components"][0]
        self.assertEqual(c["domain"], "main_sequence")
        self.assertIsNone(c["standoff_note"])


_GT0 = {"error": "--mass-msun (or a resolved object mass) must be > 0."}
_FINITE = {"error": "--mass-msun (or a resolved object mass) must be finite."}
_NO_MASS = "component 'A' has no resolvable mass"


class Cr226MassGuardCliTest(unittest.TestCase):
    """CR-22.6: the bare `exclusion-boundary --mass-msun` path accepts only a finite, positive mass (a CR-22
    regression — compute_two_layer_boundary treats M ≤ 0 as "no mass", so the frozen M ≤ 0 check had become
    unreachable and 0 / -1 / nan exited 0 with a null standoff), and a non-finite `exclusion-system
    --component mass=` is unresolvable like `mass=nan`. Offline; the bare-mass path never opens the DB."""

    def _boundary(self, mass_token, *extra):
        # `mass_token` is passed as `--mass-msun=<v>` so a leading-minus value (e.g. -inf, which is not
        # number-shaped) is always read as the value, never as a flag
        return run_query_inproc("exclusion-boundary", f"--mass-msun={mass_token}", *extra)

    def test_non_positive_and_nan_get_the_pre_cr22_error(self):
        for tok in ("0", "-1", "-0.0", "nan", "-inf", "-1e309"):
            with self.subTest(mass=tok):
                rc, d, _ = self._boundary(tok)
                self.assertEqual(rc, 1)
                self.assertEqual(d, _GT0)            # exactly the error — no partial result keys

    def test_positive_infinity_gets_the_finite_error(self):
        for tok in ("inf", "Infinity", "1e309"):     # 1e309 overflows float → inf (a realistic typo)
            with self.subTest(mass=tok):
                rc, d, _ = self._boundary(tok)
                self.assertEqual(rc, 1)
                self.assertEqual(d, _FINITE)

    def test_message_matches_the_frozen_generator(self):
        # drift guard: the CLI copy of the "> 0" string must stay the FROZEN generator's own message
        self.assertEqual(_GT0, xb.compute_exclusion_boundary(mass_msun=0))

    def test_mass_error_keeps_pre_cr22_precedence(self):
        # pre-CR-22 the frozen generator checked M ≤ 0 first, ahead of the exponent check
        rc, d, _ = self._boundary("0", "--alpha", "-1")
        self.assertEqual((rc, d), (1, _GT0))

    def test_real_subprocess_exit_code(self):
        rc, d, _ = _run("exclusion-boundary", "--mass-msun", "0")
        self.assertEqual((rc, d), (1, _GT0))

    def test_finite_positive_masses_are_byte_identical(self):
        # the guard passes every finite positive mass straight through: the CLI payload equals the core
        # wrapper's (JSON round-tripped), incl. the smallest positive double and a huge finite value
        for tok, alpha in (("0.3", 0.4), ("1e-9", 1.0 / 3.0), ("5e-324", 1.0 / 3.0), ("1e30", 1.0 / 3.0)):
            with self.subTest(mass=tok):
                rc, d, _ = self._boundary(tok, "--alpha", repr(alpha))
                self.assertEqual(rc, 0)
                core = xb.compute_two_layer_boundary(mass_msun=float(tok), mass_provenance="manual",
                                                     alpha=alpha)
                self.assertEqual(d, json.loads(json.dumps(core)))
                self.assertIsNotNone(d["r_ex_au"])

    def test_wb_anchors_unchanged(self):
        rc, d, _ = self._boundary("0.3", "--alpha", "0.4")
        self.assertEqual(rc, 0)
        self.assertEqual(d["r_ex_au"], 29.345540401952064)
        rc, d, _ = run_query_inproc("exclusion-boundary", "--object", "sun")
        self.assertEqual(rc, 0)
        self.assertEqual(d["r_ex_au"], 47.5)
        self.assertEqual(d["wall_au"], 6.0)

    def test_exclusion_system_non_finite_component_mass_is_unresolvable(self):
        for tok in ("inf", "1e309", "nan"):          # nan: the pre-existing behavior inf now matches
            with self.subTest(mass=tok):
                rc, d, _ = _run("exclusion-system", "--component", f"id=A,mass={tok}")
                self.assertEqual(rc, 1)
                self.assertTrue(d["error"].startswith(_NO_MASS), d)

    def test_compose_backstop_rejects_a_non_finite_component_dict(self):
        # a directly-built component dict bypasses the resolver — compose's m_ok still refuses inf
        r = es.compose_exclusion_system([{"id": "A", "mass_solar": float("inf"), "sp_type": "G2V"}])
        self.assertEqual(r, {"error": "component 'A' needs a finite mass_solar (got inf)."})
        # the pre-existing ≤ 0 message is unchanged
        r = es.compose_exclusion_system([{"id": "A", "mass_solar": 0.0, "sp_type": "G2V"}])
        self.assertEqual(r, {"error": "component 'A' needs a positive mass_solar (got 0.0)."})

    def test_compose_lone_out_of_domain_non_finite_mass_drops_stale_provenance(self):
        r = es.compose_exclusion_system([{"id": "A", "mass_solar": float("inf"), "sp_type": "K0III",
                                          "mass_provenance": "ms_luminosity_inversion"}])
        self.assertNotIn("error", r)
        c = r["zones"][0]["components"][0]
        self.assertIsNone(c["mass_solar"])
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")

    def test_compose_lone_out_of_domain_empty_provenance_still_unresolved(self):
        # the pre-CR-22.6 truthiness rule is kept: a falsy ("") provenance with no mass → unresolved_out_of_domain
        r = es.compose_exclusion_system([{"id": "A", "sp_type": "DA2", "mass_provenance": ""}])
        self.assertEqual(r["zones"][0]["components"][0]["mass_provenance"], "unresolved_out_of_domain")

    def test_exclusion_system_non_finite_lum_is_unresolvable(self):
        # the L^0.2632 inversion route: lum=inf → an inf inversion mass → rejected by the resolver like mass=inf
        for tok in ("inf", "1e309"):
            with self.subTest(lum=tok):
                rc, d, _ = _run("exclusion-system", "--component", f"id=A,lum={tok},class=G2V")
                self.assertEqual(rc, 1)
                self.assertTrue(d["error"].startswith(_NO_MASS), d)


if __name__ == "__main__":
    unittest.main()
