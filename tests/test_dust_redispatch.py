"""Offline tests for the query.py dust re-dispatch shim (Windows micromamba routing).

The shim (`query._needs_dust` / `query._redispatch_to_dust_env`) lets a native-Windows
checkout serve the healpy-backed dust subcommands from an isolated conda-forge/micromamba
env via subprocess, while staying a pure no-op wherever the dust extra is importable
(WSL/Linux/macOS, and inside the conda child). These tests mock the dust-capability probe
(`core.dust._dustmaps_available`) and `subprocess.run`, so they need no network, no conda,
and no Qt — they must pass on every OS. See DUST_WINDOWS_MICROMAMBA_PLAN.md.
"""

import argparse
import os
import unittest
from unittest import mock

import query


class NeedsDustTest(unittest.TestCase):
    """`_needs_dust` classifies exactly the dust-map-loading invocations."""

    @staticmethod
    def _ns(**kw):
        return argparse.Namespace(**kw)

    def test_dust_query_subcommands_need_dust(self):
        self.assertTrue(query._needs_dust(self._ns(func=query.cmd_dust_sightline)))
        self.assertTrue(query._needs_dust(self._ns(func=query.cmd_dust_between)))

    def test_dust_and_blend_weights_need_dust(self):
        # weight is what matters here; func is a non-dust handler.
        self.assertTrue(query._needs_dust(self._ns(func=query.cmd_distance, weight="dust")))
        self.assertTrue(query._needs_dust(self._ns(func=query.cmd_distance, weight="blend")))

    def test_non_dust_invocations_do_not(self):
        self.assertFalse(query._needs_dust(self._ns(func=query.cmd_distance, weight="distance")))
        self.assertFalse(query._needs_dust(self._ns(func=query.cmd_distance, weight="hops")))
        self.assertFalse(query._needs_dust(self._ns(func=query.cmd_distance)))          # no weight attr


class RedispatchShimTest(unittest.TestCase):
    """`_redispatch_to_dust_env` routes only when it must, and preserves the exit code."""

    QUERY = os.path.abspath(query.__file__)

    def setUp(self):
        # Isolate the two env knobs from whatever the host environment carries.
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop(query._DUST_SUBPROCESS_SENTINEL, None)
        os.environ.pop(query._DUST_PYTHON_ENV, None)

    def tearDown(self):
        self._env.stop()

    def test_noop_when_dust_available(self):
        # Even with a dust interpreter configured, an importable dust extra wins → in-process,
        # and the decision is delegated to core.dust's own gate (no drift, checks dustmaps too).
        os.environ[query._DUST_PYTHON_ENV] = "should-not-be-used python"
        with mock.patch("core.dust._dustmaps_available", return_value=True) as avail, \
             mock.patch("subprocess.run") as run:
            self.assertIsNone(
                query._redispatch_to_dust_env(["dust-sightline", "--star", "Vega"]))
            run.assert_not_called()
            avail.assert_called_once()                         # probes the shared capability gate

    def test_sentinel_blocks_recursion(self):
        # The child (sentinel set) never re-spawns — and short-circuits BEFORE the probe.
        os.environ[query._DUST_SUBPROCESS_SENTINEL] = "1"
        os.environ[query._DUST_PYTHON_ENV] = "micromamba run -n dust python"
        with mock.patch("core.dust._dustmaps_available", return_value=False) as avail, \
             mock.patch("subprocess.run") as run:
            self.assertIsNone(
                query._redispatch_to_dust_env(["dust-sightline", "--star", "Vega"]))
            run.assert_not_called()
            avail.assert_not_called()

    def test_falls_through_when_no_dust_python(self):
        # Dust unavailable + nothing configured → return (downstream surfaces the curated error).
        with mock.patch("core.dust._dustmaps_available", return_value=False), \
             mock.patch("subprocess.run") as run:
            self.assertIsNone(
                query._redispatch_to_dust_env(["dust-between", "--star1", "Sol", "--star2", "Vega"]))
            run.assert_not_called()

    def test_routes_when_configured(self):
        os.environ[query._DUST_PYTHON_ENV] = "micromamba run -n dust python"
        fake = mock.Mock(returncode=0)
        with mock.patch("core.dust._dustmaps_available", return_value=False), \
             mock.patch("subprocess.run", return_value=fake) as run:
            with self.assertRaises(SystemExit) as cm:
                query._redispatch_to_dust_env(["dust-sightline", "--star", "Vega"])
            self.assertEqual(cm.exception.code, 0)
            run.assert_called_once()
            argv, kwargs = run.call_args
            spawned = argv[0]
            # tokenized command → query.py path → original argv, verbatim
            self.assertEqual(spawned[:5], ["micromamba", "run", "-n", "dust", "python"])
            self.assertEqual(spawned[5], self.QUERY)
            self.assertEqual(spawned[6:], ["dust-sightline", "--star", "Vega"])
            # child carries the recursion sentinel
            self.assertEqual(kwargs["env"][query._DUST_SUBPROCESS_SENTINEL], "1")

    def test_routes_preserves_nonzero_exit(self):
        os.environ[query._DUST_PYTHON_ENV] = "dustpy"          # single-token interpreter
        fake = mock.Mock(returncode=1)
        with mock.patch("core.dust._dustmaps_available", return_value=False), \
             mock.patch("subprocess.run", return_value=fake):
            with self.assertRaises(SystemExit) as cm:
                query._redispatch_to_dust_env(["dust-sightline", "--star", "NoSuchStar"])
            self.assertEqual(cm.exception.code, 1)

    def test_launch_failure_yields_curated_error(self):
        # A bad interpreter (subprocess raises) → curated {"error"} JSON + exit 1, NOT a traceback.
        os.environ[query._DUST_PYTHON_ENV] = "no-such-interpreter-xyz python"
        with mock.patch("core.dust._dustmaps_available", return_value=False), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError("not found")), \
             mock.patch("builtins.print") as pr:
            with self.assertRaises(SystemExit) as cm:
                query._redispatch_to_dust_env(["dust-sightline", "--star", "Vega"])
            self.assertEqual(cm.exception.code, 1)             # _out() exits 1 on error
            emitted = pr.call_args[0][0]                       # the JSON string _out printed
            self.assertIn('"error"', emitted)
            self.assertIn(query._DUST_PYTHON_ENV, emitted)


if __name__ == "__main__":
    unittest.main()
