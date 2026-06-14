# tests/test_comparison.py — Phase L1–L3 (Exoplanet Comparison Dashboard).
#
# Offline. Locks:
#   * compute_stellar_evolution (L3): stage formulas for 1 M☉, monotonic
#     non-overlapping boundaries summing to total_gyr, current_stage selection,
#     the low-mass (< 0.8) and high-mass (> 8) special-case branches, and the
#     self-validating out-of-range error.
#   * compare_stars (L1): per-star error isolation, the NASA pscomppars
#     supplement + luminosity/HZ path, and the carried-through Hypatia sub-dict —
#     all with compute_simbad_lookup / compute_hypatia_data / _query_tap mocked.
#   * core.viz.prepare_evolution_diagram and prepare_abundance_comparison shapes.
#   * the stellar-evolution query.py subcommand contract + exit-code matrix
#     (subprocess; same pattern as tests/test_query_phase_n.py).
#
# L2 (ESI ranking) adds no core function — it reuses search_hwc, already covered
# by tests/test_query_expanded.py — so it gets no core test here.

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import core.databases as databases
import core.equations as equations
import core.viz as viz

_REPO = Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_l_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


# ── L3: compute_stellar_evolution ────────────────────────────────────────────

class StellarEvolutionTest(unittest.TestCase):

    def test_sun_main_sequence_anchor(self):
        r = equations.compute_stellar_evolution(1.0)
        self.assertNotIn("error", r)
        # T_ms = 10^10 * (1/1)^2.5 = 10 Gyr; MS is the second stage (after 0.01·T_ms).
        self.assertAlmostEqual(r["ms_end_gyr"], 0.1 + 10.0, places=6)
        self.assertEqual(len(r["stages"]), 6)
        self.assertFalse(r["low_mass"])
        self.assertFalse(r["high_mass"])

    def test_stage_boundaries_monotonic_and_sum(self):
        r = equations.compute_stellar_evolution(1.0)
        total = 0.0
        prev_end = 0.0
        for s in r["stages"]:
            self.assertAlmostEqual(s["start_gyr"], prev_end, places=9)  # contiguous
            self.assertGreater(s["end_gyr"], s["start_gyr"])            # forward
            self.assertAlmostEqual(s["end_gyr"] - s["start_gyr"], s["duration_gyr"], places=9)
            total += s["duration_gyr"]
            prev_end = s["end_gyr"]
        self.assertAlmostEqual(total, r["total_gyr"], places=9)

    def test_current_stage_in_ms_and_beyond(self):
        self.assertEqual(equations.compute_stellar_evolution(1.0, 4.6)["current_stage"],
                         "Main Sequence")
        self.assertEqual(equations.compute_stellar_evolution(1.0, 999)["current_stage"],
                         "Beyond AGB")
        self.assertIsNone(equations.compute_stellar_evolution(1.0)["current_stage"])

    def test_low_mass_branch(self):
        r = equations.compute_stellar_evolution(0.5)
        self.assertTrue(r["low_mass"])
        self.assertEqual([s["name"] for s in r["stages"]],
                         ["Pre-Main Sequence", "Main Sequence"])

    def test_high_mass_branch(self):
        r = equations.compute_stellar_evolution(10.0)
        self.assertTrue(r["high_mass"])
        self.assertEqual(r["stages"][-1]["name"], "Supergiant → Supernova")

    def test_out_of_range_errors(self):
        self.assertIn("error", equations.compute_stellar_evolution(0))
        self.assertIn("error", equations.compute_stellar_evolution(50))
        self.assertIn("error", equations.compute_stellar_evolution(1.0, -1))

    def test_prepare_evolution_diagram_shape(self):
        d = viz.prepare_evolution_diagram(equations.compute_stellar_evolution(1.0, 4.6))
        self.assertEqual(set(d) >= {"stages", "current_age_gyr", "x_max_gyr"}, True)
        self.assertGreater(d["x_max_gyr"], d["total_gyr"])
        self.assertIn("error", viz.prepare_evolution_diagram({"error": "boom"}))


# ── L1: compare_stars (network mocked) ───────────────────────────────────────

def _fake_simbad(name):
    table = {
        "tau ceti": {"main_id": "* tau Cet", "sp_type": "G8.5V", "teff": 5344.0,
                     "vmag": 3.5, "ly": 11.91, "plx_value": None, "parsecs": None,
                     "designations": {"HIP": "HIP 8102", "HD": "HD 10700"}},
        "sirius":   {"main_id": "* alf CMa", "sp_type": "A1V", "teff": 9940.0,
                     "vmag": -1.46, "ly": 8.60, "plx_value": None, "parsecs": None,
                     "designations": {"HIP": "HIP 32349", "HD": "HD 48915"}},
        # A non-planet-host (absent from NASA pscomppars → _fake_tap returns []).
        "18 scorpii": {"main_id": "* 18 Sco", "sp_type": "G2Va", "teff": 5799.0,
                       "vmag": 5.5, "ly": 45.7, "plx_value": 70.7, "parsecs": 14.14,
                       "designations": {"HD": "HD 146233"}},
    }
    k = name.lower()
    if k in table:
        return dict(table[k])
    return {"error": f"No SIMBAD match for {name!r}"}


def _fake_hypatia(sl):
    if sl.get("main_id") == "* tau Cet":
        return {"star_name": "HIP 8102",
                "properties": {"logg": 4.53, "disk": "thin disk",
                               "u_vel": -23.0, "v_vel": -37.0, "w_vel": -13.0},
                "abundances": [{"element": "Fe", "mean": -0.49},
                               {"element": "Mg", "mean": -0.28},
                               {"element": "Si", "mean": -0.34},
                               {"element": "O",  "mean": -0.30}]}
    return {"error": "not in Hypatia"}


def _fake_tap(table, where, **kwargs):
    if "8102" in where or "10700" in where:
        return [{"st_teff": "5344", "st_rad": "0.79", "st_mass": "0.78", "st_lum": "-0.28"}]
    if "32349" in where or "48915" in where:
        return [{"st_teff": "9940", "st_rad": "1.71", "st_mass": "2.06", "st_lum": "1.43"}]
    return []


class CompareStarsTest(unittest.TestCase):

    def setUp(self):
        self._p = [
            mock.patch.object(databases, "compute_simbad_lookup", _fake_simbad),
            mock.patch.object(databases, "compute_hypatia_data", _fake_hypatia),
            mock.patch.object(databases, "_query_tap", _fake_tap),
        ]
        for p in self._p:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._p])

    def test_arg_count_guard(self):
        self.assertIn("error", databases.compare_stars(["only one"]))
        self.assertIn("error", databases.compare_stars(["a", "b", "c", "d", "e"]))

    def test_two_star_shape_and_supplement(self):
        r = databases.compare_stars(["Tau Ceti", "Sirius"])
        self.assertNotIn("error", r)
        self.assertEqual(len(r["stars"]), 2)
        tau = r["stars"][0]
        # NASA supplement filled radius/mass; luminosity from radius²·(teff/5778)⁴.
        self.assertAlmostEqual(tau["radius"], 0.79, places=6)
        self.assertAlmostEqual(tau["mass"], 0.78, places=6)
        self.assertAlmostEqual(tau["luminosity"], 0.79 ** 2 * (5344 / 5778.0) ** 4, places=6)
        # HZ bounds present and ordered inner < outer.
        self.assertIsNotNone(tau["hz_inner_au"])
        self.assertLess(tau["hz_inner_au"], tau["hz_outer_au"])
        # Hypatia carried through.
        self.assertEqual(tau["hypatia"]["star_name"], "HIP 8102")

    def test_photometric_fallback_for_non_planet_host(self):
        # 18 Sco isn't in NASA pscomppars (_fake_tap returns []), so mass/radius
        # come from the Star System Regions photometric method, not N/A.
        import core.regions as regions

        def fake_regions(sl, **kw):
            if sl.get("main_id") == "* 18 Sco":
                return {"stellarMass": 1.03, "stellarRadius": 1.01, "bcLuminosity": 1.05}
            return {"error": "not main sequence"}

        with mock.patch.object(regions, "compute_star_system_regions_from_simbad",
                               fake_regions):
            r = databases.compare_stars(["18 Scorpii", "Tau Ceti"])
        sco = r["stars"][0]
        self.assertIsNone(sco["error"])
        self.assertAlmostEqual(sco["mass"], 1.03, places=4)
        self.assertAlmostEqual(sco["radius"], 1.01, places=4)
        # luminosity recomputed from radius²·(teff/5778)⁴; HZ then derivable.
        self.assertAlmostEqual(sco["luminosity"], 1.01 ** 2 * (5799 / 5778.0) ** 4, places=4)
        self.assertIsNotNone(sco["hz_inner_au"])

    def test_per_star_error_isolated(self):
        r = databases.compare_stars(["Tau Ceti", "Nonexistent Star"])
        self.assertEqual(len(r["stars"]), 2)
        self.assertIsNone(r["stars"][0]["error"])          # good star unaffected
        self.assertIsNotNone(r["stars"][1]["error"])       # bad star isolated
        self.assertIsNone(r["stars"][1]["teff"])

    def test_prepare_abundance_comparison(self):
        r = databases.compare_stars(["Tau Ceti", "Sirius"])  # only Tau Ceti has Hypatia
        ac = viz.prepare_abundance_comparison(r)
        self.assertNotIn("error", ac)
        self.assertEqual(ac["star_names"], ["* tau Cet"])
        # Union of elements ordered by atomic number: O(8), Mg(12), Si(14), Fe(26).
        self.assertEqual(ac["elements"], ["O", "Mg", "Si", "Fe"])
        self.assertEqual(len(ac["matrix"]), 4)

    def test_sol_special_case(self):
        # "Sol"/"Sun" don't resolve in SIMBAD — they use injected reference values.
        for alias in ("Sol", "Sun"):
            sun = databases.compare_stars([alias, "Tau Ceti"])["stars"][0]
            self.assertIsNone(sun["error"])
            self.assertEqual(sun["name"], "Sun")
            self.assertEqual(sun["sp_type"], "G2V")
            self.assertEqual((sun["teff"], sun["mass"], sun["radius"], sun["luminosity"]),
                             (5778.0, 1.0, 1.0, 1.0))
            self.assertEqual(sun["ly"], 0.0)
            self.assertIsNotNone(sun["hz_inner_au"])
            # Solar normalisation → every [X/H]_sun ≡ 0; full 104-species baseline.
            ab = {a["element"]: a["mean"] for a in sun["hypatia"]["abundances"]}
            self.assertEqual(ab["Fe"], 0.0)
            self.assertEqual(len(sun["hypatia"]["abundances"]), 104)
            # Heliocentric U/V/W reference frame → Sun ≡ 0 (no N/A kinematics).
            props = sun["hypatia"]["properties"]
            self.assertEqual((props["u_vel"], props["v_vel"], props["w_vel"]),
                             (0.0, 0.0, 0.0))

    def test_sol_baseline_does_not_bloat_chart(self):
        r = databases.compare_stars(["Sol", "Tau Ceti"])
        ac = viz.prepare_abundance_comparison(r)
        self.assertEqual(ac["star_names"], ["Sun", "* tau Cet"])
        # Chart spans only Tau Ceti's measured elements, NOT the Sun's 104 zeros.
        self.assertEqual(ac["elements"], ["O", "Mg", "Si", "Fe"])
        self.assertEqual(ac["matrix"][0], [0.0, -0.30])   # O: Sun baseline, Tau Ceti measured


# ── L3: stellar-evolution query.py subcommand ────────────────────────────────

class StellarEvolutionQueryTest(unittest.TestCase):

    def test_happy_path(self):
        code, payload, _ = _run("stellar-evolution", "--mass-solar", "1.0",
                                "--current-age-gyr", "4.6")
        self.assertEqual(code, 0)
        self.assertEqual(payload["current_stage"], "Main Sequence")
        self.assertEqual(len(payload["stages"]), 6)

    def test_parity_with_core(self):
        code, payload, _ = _run("stellar-evolution", "--mass-solar", "2.0")
        self.assertEqual(code, 0)
        self.assertEqual(payload["total_gyr"],
                         equations.compute_stellar_evolution(2.0)["total_gyr"])

    def test_out_of_range_exit_1(self):
        code, payload, _ = _run("stellar-evolution", "--mass-solar", "50")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_bad_arg_exit_2(self):
        code, payload, stderr = _run("stellar-evolution", "--mass-solar", "abc")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)


class CompareStarsQueryCliTest(unittest.TestCase):
    """compare-stars query.py subcommand (Phase L1). Offline: Sol/Sun are
    reference-constant special-cased, so the happy path needs no network; the
    error paths (arg count, argparse) are likewise offline."""

    def test_happy_sol_sun_offline(self):
        code, payload, _ = _run("compare-stars", "--stars", "Sol", "Sun")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["stars"]), 2)
        for s in payload["stars"]:
            self.assertEqual(s["sp_type"], "G2V")
            self.assertEqual(s["teff"], 5778.0)
            self.assertIsNone(s["error"])

    def test_too_few_exit_1(self):
        code, payload, _ = _run("compare-stars", "--stars", "Sol")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_too_many_exit_1(self):
        code, payload, _ = _run("compare-stars", "--stars", "Sol", "Sun", "a", "b", "c")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_missing_arg_exit_2(self):
        code, payload, _ = _run("compare-stars")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)


class EsiBarPrepTest(unittest.TestCase):
    """core.viz.prepare_esi_bar_chart (Phase L2 diagram data)."""

    def setUp(self):
        import core.viz as viz
        self.viz = viz

    def test_filters_and_top_n(self):
        result = {"stars": [
            {"P_NAME": "b", "P_ESI": "0.91", "P_HABITABLE": "1"},
            {"P_NAME": "c", "P_ESI": "0.80", "P_HABITABLE": "0"},
            {"P_NAME": "d", "P_ESI": "",     "P_HABITABLE": "1"},  # blank ESI dropped
        ]}
        d = self.viz.prepare_esi_bar_chart(result, top_n=20)
        self.assertEqual(d["names"], ["b", "c"])
        self.assertEqual(d["esi"], [0.91, 0.80])
        self.assertEqual(d["habitable"], [True, False])
        self.assertEqual((d["shown"], d["total"]), (2, 2))

    def test_top_n_caps(self):
        result = {"stars": [{"P_NAME": str(i), "P_ESI": str(1 - i * 0.01),
                             "P_HABITABLE": "0"} for i in range(30)]}
        d = self.viz.prepare_esi_bar_chart(result, top_n=10)
        self.assertEqual(d["shown"], 10)
        self.assertEqual(d["total"], 30)

    def test_error_passthrough_and_empty(self):
        self.assertIn("error", self.viz.prepare_esi_bar_chart({"error": "x"}))
        self.assertIn("error", self.viz.prepare_esi_bar_chart({"stars": []}))


if __name__ == "__main__":
    unittest.main()
