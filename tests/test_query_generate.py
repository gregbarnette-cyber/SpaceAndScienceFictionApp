# tests/test_query_generate.py — Phase R1-C4 query.py `generate-system` contracts.
#
# Offline subprocess tests over the synthetic-from-seed path (no --anchor-star, so
# no network). Lock: the happy-path JSON contract + known anchor values, seed
# determinism across processes, the curated-error exit-1 matrix (self-validating,
# unlike the Phase-N raw-exception wrappers), and argparse exit-2 for
# missing/non-integer args. The real-anchor (network) path and the GUI smoke are
# exercised elsewhere (tests/test_generate.py mocked readers; C5 panel smoke).
#
# Harness mirrors tests/test_query_phase_n.py: subprocess against query.py with
# cwd=_REPO and a throwaway SPACE_APP_DB (auto-seeded reference tables, so the
# synthetic main-sequence interpolation works without touching data/space_app.db).

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_r_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


_TOP_KEYS = {"seed", "mode", "anchor_star", "star", "planets", "warnings", "notes"}


class GenerateSystemHappyPath(unittest.TestCase):
    def test_synthetic_contract(self):
        code, payload, _ = _run("generate-system", "--seed", "88",
                                "--spectral-class", "K2V", "--planets", "5")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), _TOP_KEYS)
        self.assertEqual(payload["mode"], "synthetic")
        self.assertIsNone(payload["anchor_star"])
        self.assertEqual(payload["seed"], 88)
        # K2V matches a table row exactly → known stellar values (CSV seed).
        self.assertEqual(payload["star"]["spectral_class"], "K2V")
        self.assertAlmostEqual(payload["star"]["teff"], 4800.0, places=1)
        self.assertAlmostEqual(payload["star"]["mass_solar"], 0.72, places=2)
        self.assertEqual(len(payload["planets"]), 5)
        for p in payload["planets"]:
            self.assertEqual(p["source"], "synthetic")

    def test_subprocess_determinism(self):
        _, a, _ = _run("generate-system", "--seed", "88", "--spectral-class", "K2V", "--planets", "4")
        _, b, _ = _run("generate-system", "--seed", "88", "--spectral-class", "K2V", "--planets", "4")
        self.assertEqual(a, b)

    def test_sampled_no_class(self):
        code, payload, _ = _run("generate-system", "--seed", "123")
        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "synthetic")
        self.assertRegex(payload["star"]["spectral_class"], r"^[BAFGKM]\d+V$")

    def test_require_habitable(self):
        code, payload, _ = _run("generate-system", "--seed", "7",
                                "--spectral-class", "G2V", "--require-habitable")
        self.assertEqual(code, 0)
        self.assertTrue(any(
            p["type"] in ("rocky", "super_earth") and p["hz_class"] == "conservative"
            for p in payload["planets"]))


class GenerateSystemErrorMatrix(unittest.TestCase):
    # Self-validating → curated {"error"} on stdout, exit 1.
    def test_bad_spectral_class_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "Z9V")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_o_class_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "O5V")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        self.assertIn("O", payload["error"])

    def test_planets_out_of_range_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1",
                                "--spectral-class", "G2V", "--planets", "20")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_require_habitable_zero_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "G2V",
                                "--planets", "0", "--require-habitable")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


class GenerateSystemArgparse(unittest.TestCase):
    # Malformed/missing args → argparse exit 2 (stderr), not JSON.
    def test_missing_seed_exit2(self):
        code, payload, err = _run("generate-system", "--spectral-class", "K2V")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)

    def test_noninteger_seed_exit2(self):
        code, _, _ = _run("generate-system", "--seed", "x")
        self.assertEqual(code, 2)

    def test_noninteger_planets_exit2(self):
        code, _, _ = _run("generate-system", "--seed", "1", "--planets", "x")
        self.assertEqual(code, 2)


# ── Phase R2-C6 · generate-system --constraint / --companion / --nbody ───────

_FEAS_KEYS = _TOP_KEYS | {"feasible", "constraints"}
_LAYER_KEYS = {"id", "type", "verdict", "layer1", "layer2", "layer3", "layer4"}


class GenerateSystemFeasibility(unittest.TestCase):
    def test_feasibility_contract(self):
        code, payload, _ = _run(
            "generate-system", "--seed", "7", "--spectral-class", "G2V", "--planets", "5",
            "--constraint", "planet_at_location:terrestrial,1.0,in_hz",
            "--constraint", "trojan:terrestrial,outermost,L4")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), _FEAS_KEYS)
        self.assertIn(payload["feasible"], (True, False))
        self.assertEqual(len(payload["constraints"]), 2)
        for c in payload["constraints"]:
            self.assertEqual(set(c), _LAYER_KEYS)
            self.assertEqual(c["layer3"]["grounding"], "default-extrapolation")

    def test_zero_constraint_parity(self):
        # No --constraint → the R1 path: original top keys, no feasibility envelope.
        code, payload, _ = _run("generate-system", "--seed", "7",
                                "--spectral-class", "G2V", "--planets", "5")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), _TOP_KEYS)
        self.assertNotIn("feasible", payload)

    def test_constraint_determinism(self):
        args = ("generate-system", "--seed", "7", "--spectral-class", "G2V", "--planets", "5",
                "--constraint", "resonance:b,c,2:1", "--companion", "0.5,20", "--nbody")
        _, a, _ = _run(*args)
        _, b, _ = _run(*args)
        self.assertEqual(a, b)

    def test_companion_gate_and_note(self):
        code, payload, _ = _run(
            "generate-system", "--seed", "7", "--spectral-class", "G2V", "--planets", "5",
            "--constraint", "planet_at_location:terrestrial,1.0,at:9.0", "--companion", "0.5,20")
        self.assertEqual(code, 0)
        c1 = payload["constraints"][0]
        self.assertEqual(c1["verdict"], "infeasible")          # S-type, beyond critical SMA
        self.assertIn("Binary truncation", c1["layer1"]["reason"])
        self.assertTrue(any("companion hint" in n for n in payload["notes"]))

    def test_unknown_constraint_not_evaluated(self):
        code, payload, _ = _run("generate-system", "--seed", "7",
                                "--spectral-class", "G2V", "--planets", "3",
                                "--constraint", "frobnicate:x")
        self.assertEqual(code, 0)
        self.assertEqual(payload["constraints"][0]["verdict"], "not_evaluated")


class GenerateSystemConstraintErrors(unittest.TestCase):
    def test_malformed_constraint_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "G2V",
                                "--constraint", "planet_at_location:terrestrial")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        self.assertIn("Malformed --constraint", payload["error"])

    def test_malformed_companion_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "G2V",
                                "--constraint", "planet_at_location:terrestrial,1.0,in_hz",
                                "--companion", "0.5")
        self.assertEqual(code, 1)
        self.assertIn("Malformed --companion", payload["error"])

    def test_bad_companion_ecc_exit1(self):
        code, payload, _ = _run("generate-system", "--seed", "1", "--spectral-class", "G2V",
                                "--constraint", "planet_at_location:terrestrial,1.0,in_hz",
                                "--companion", "0.5,20,1.5")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


# ── R3-C6 · --research-policy subprocess contract ────────────────────────────
import shutil
import tempfile

from core.research_priors import compute_research_priors_ingest

_SAMPLE_FIX = str(_REPO / "tests" / "fixtures" / "research_priors_sample.json")


def _run_priors(cache_dir, *cmd_args):
    """Run query.py with SPACE_RESEARCH_PRIORS_DIR pointed at cache_dir."""
    env = {**_ENV, "SPACE_RESEARCH_PRIORS_DIR": cache_dir}
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=env,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


class GenerateSystemResearchPolicy(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def test_permissive_equals_no_flag(self):
        base = ("generate-system", "--seed", "88", "--spectral-class", "K2V", "--planets", "5")
        c0, a, _ = _run(*base)
        c1, b, _ = _run(*base, "--research-policy", "permissive")
        self.assertEqual((c0, c1), (0, 0))
        self.assertEqual(a, b)
        self.assertEqual(a["star"]["grounding"], "default-extrapolation")

    def test_strict_with_cache(self):
        res = compute_research_priors_ingest(path=_SAMPLE_FIX, cache_dir=self.cache)
        self.assertNotIn("error", res)
        code, payload, _ = _run_priors(
            self.cache, "generate-system", "--seed", "88",
            "--spectral-class", "K2V", "--planets", "5", "--research-policy", "strict")
        self.assertEqual(code, 0)
        self.assertEqual(payload["star"]["grounding"], "research-calibrated")
        self.assertTrue(any("sample-2026-06-24" in n for n in payload["notes"]))

    def test_strict_without_cache_exit1(self):
        code, payload, _ = _run_priors(
            self.cache, "generate-system", "--seed", "1",
            "--spectral-class", "K2V", "--planets", "3", "--research-policy", "strict")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        self.assertIn("strict", payload["error"])

    def test_bad_policy_exit2(self):
        code, payload, err = _run("generate-system", "--seed", "1",
                                  "--spectral-class", "K2V", "--research-policy", "bogus")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
