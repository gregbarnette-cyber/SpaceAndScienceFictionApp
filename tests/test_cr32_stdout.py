# tests/test_cr32_stdout.py — CR-32: a Gaia TAP timeout during the archive-client build must leave the
# JSON result on stdout (CR-32.1), with the ESA banner / diagnostics still off stdout (CR-32.2).
#
# The bug: ``_gaia_stdout_to_stderr`` was a process-global ``redirect_stdout(sys.stderr)`` entered on the
# CR-19 watchdog thread; an abandoned (timed-out) attempt never left it, so stdout stayed pointed at stderr.
# The fix is a thread-scoped diversion (a transparent ``sys.stdout`` proxy that routes to stderr only the
# writes of a thread currently inside the diversion). Offline: every Gaia client is a fake module.

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

from core import catalog

# imported up front: a first import inside mock.patch.dict(sys.modules) would be unloaded on exit and numpy
# refuses a second load ("cannot load module more than once per process")
import astropy.table  # noqa: F401,E402


def _fake_gaia(init_hook=None, async_hook=None):
    mod = types.ModuleType("astroquery.gaia")

    def _job():
        from astropy.table import Table
        return types.SimpleNamespace(get_results=lambda: Table({"x": [1]}))

    class _G:
        def __init__(self, **kw):
            print("In preparation for Gaia DR4 (banner)")
            if init_hook:
                init_hook()

        def launch_job(self, q):
            print("sync job diagnostic")            # the widened diversion covers the job too
            return _job()

    class _Legacy:
        ROW_LIMIT = 50

        def launch_job(self, q):
            return _job()

        def launch_job_async(self, q):
            if async_hook:
                async_hook()
            from astroquery import log               # astroquery's real logger (astropy handler → sys.stdout)
            log.info("Query finished.")
            return _job()
    mod.GaiaClass = _G
    mod.Gaia = _Legacy()
    return mod


class _Env:
    """A harness mirroring query.py's stdout/stderr, plus the fake Gaia module and no cache."""

    def __init__(self, mod, **env):
        self.mod, self.env = mod, dict({"SPACE_APP_CATALOG_CACHE": "0"}, **env)
        self.out, self.err = io.StringIO(), io.StringIO()

    def __enter__(self):
        self._stack = contextlib.ExitStack()
        self._stack.enter_context(mock.patch.dict(sys.modules, {"astroquery.gaia": self.mod}))
        self._stack.enter_context(mock.patch.dict(os.environ, self.env))
        self._stack.enter_context(contextlib.redirect_stdout(self.out))
        self._stack.enter_context(contextlib.redirect_stderr(self.err))
        catalog.reset_gaia_sync_circuit()
        return self

    def __exit__(self, *exc):
        self._stack.close()
        catalog.set_gaia_timeout(None)
        catalog.reset_gaia_sync_circuit()


def _wait_for(pred, timeout=5.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


class AbandonedAttemptTest(unittest.TestCase):
    """T32-1 — both bounded attempts abandoned INSIDE the client build: the degraded result's later output
    (the JSON, in query.py) reaches stdout, and a late banner from an abandoned thread reaches stderr."""

    def test_timeout_inside_the_client_build_leaves_stdout_intact(self):
        release, lock, printed = threading.Event(), threading.Lock(), []

        def _block():
            release.wait(10)
            print("LATE banner from an abandoned attempt")
            with lock:
                printed.append(1)
        try:
            with _Env(_fake_gaia(init_hook=_block)) as h:
                catalog.set_gaia_timeout(0.2)
                res = catalog.gaia_tap(adql="SELECT 1")
                print("AFTER")                                  # stands in for query.py's _out(result)
                self.assertEqual(res.get("gaia_bound_reason"), "timeout")
                release.set()
                self.assertTrue(_wait_for(lambda: len(printed) == 2))     # both abandoned attempts
                time.sleep(0.2)                                            # let each leave its diversion
                self.assertIn("AFTER", h.out.getvalue())
                self.assertNotIn("AFTER", h.err.getvalue())
                self.assertIn("LATE banner", h.err.getvalue())
                self.assertNotIn("banner", h.out.getvalue())
        finally:
            release.set()


class RetryThenSuccessTest(unittest.TestCase):
    """T32-2 — CR-32 acc 2: the first attempt is abandoned inside the diversion, the retry succeeds → the result
    is not degraded, the breaker is not tripped, stdout is intact, and the late marker lands on stderr."""

    def test_first_attempt_hook(self):
        with _Env(_fake_gaia(), SPACE_APP_GAIA_FORCE_FIRST_ATTEMPT_TIMEOUT="1") as h:
            catalog.set_gaia_timeout(5)
            res = catalog.gaia_tap(adql="SELECT 1")
            print("AFTER")
            self.assertNotIn("error", res)
            self.assertNotIn("gaia_bound_reason", res)
            self.assertIsNone(catalog._gaia_circuit_reason())
            self.assertTrue(_wait_for(lambda: catalog._HOOK_MARKER in h.err.getvalue()))
            self.assertEqual(h.out.getvalue(), "AFTER\n")


class ProxyTest(unittest.TestCase):
    """T32-3 / T32-4 — the proxy is transparent (attribute passthrough, return values), idempotent, and
    thread-scoped under concurrent diversions."""

    def test_attribute_passthrough_and_return_values(self):
        with tempfile.TemporaryFile("w+", encoding="utf-8") as fh:
            p = catalog._ThreadRoutedStdout(fh)
            self.assertEqual(p.encoding, fh.encoding)
            self.assertIs(p.buffer, fh.buffer)
            self.assertEqual(p.fileno(), fh.fileno())
            self.assertEqual(p.isatty(), fh.isatty())
            self.assertEqual(p.write("abc"), 3)
            p.writelines(["d", "e"])
            p.flush()
            print("f", file=p)
            fh.seek(0)
            self.assertEqual(fh.read(), "abcdef\n")

    def test_install_is_idempotent_and_thread_scoped(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with catalog._gaia_stdout_to_stderr():
                first = sys.stdout
                with catalog._gaia_stdout_to_stderr():
                    self.assertIs(sys.stdout, first)            # no double wrap
                print("diverted")
            print("main")
            go = threading.Barrier(3)

            def _worker(tag):
                with catalog._gaia_stdout_to_stderr():
                    go.wait(5)
                    print(tag)
                    go.wait(5)
            ts = [threading.Thread(target=_worker, args=(f"w{i}",)) for i in range(2)]
            for t in ts:
                t.start()
            go.wait(5)
            print("main-during")
            go.wait(5)
            for t in ts:
                t.join(5)
        self.assertIsInstance(first, catalog._ThreadRoutedStdout)
        self.assertEqual(out.getvalue(), "main\nmain-during\n")
        self.assertIn("diverted", err.getvalue())
        self.assertIn("w0", err.getvalue())
        self.assertIn("w1", err.getvalue())

    def test_recursion_guards_and_isatty_follows_the_target(self):
        import copy
        out = io.StringIO()
        p = catalog._ThreadRoutedStdout(out)
        copy.copy(p)                                                # no __getattr__('_wrapped') recursion
        saved_out, saved_err = sys.stdout, sys.stderr
        try:
            sys.stdout = p
            sys.stderr = p                                          # a 2>&1-style capture
            with catalog._gaia_stdout_to_stderr():
                self.assertIs(p._target(), sys.__stderr__)          # no proxy → proxy recursion
                self.assertEqual(p.isatty(), sys.__stderr__.isatty())
        finally:
            sys.stdout, sys.stderr = saved_out, saved_err
        self.assertFalse(p.isatty())                                # StringIO

    def test_none_streams(self):
        """T32-7 — a pythonw-style None stdout is left alone; a diverted write to a None stderr is dropped."""
        saved_out, saved_err = sys.stdout, sys.stderr
        try:
            sys.stdout = None
            with catalog._gaia_stdout_to_stderr():
                self.assertIsNone(sys.stdout)
            sys.stdout = io.StringIO()
            sys.stderr = None
            with catalog._gaia_stdout_to_stderr():
                print("dropped")                                 # must not raise
            self.assertEqual(sys.stdout.getvalue(), "")
        finally:
            sys.stdout, sys.stderr = saved_out, saved_err


class LegacyPathTest(unittest.TestCase):
    """T32-6 — the async / unbounded legacy path: astroquery's "INFO: Query finished." (logged during
    launch_job_async, outside today's import-only diversion) goes to stderr — close-binary-census's stdout
    is JSON-only (WB MSG 326)."""

    def test_async_info_line_goes_to_stderr(self):
        with _Env(_fake_gaia()) as h:
            res = catalog.gaia_tap(adql="SELECT 1", use_async=True)
            self.assertNotIn("error", res)
        self.assertEqual(h.out.getvalue(), "")
        self.assertIn("Query finished", h.err.getvalue())

    def test_sync_job_diagnostics_go_to_stderr(self):
        with _Env(_fake_gaia()) as h:
            catalog.set_gaia_timeout(5)
            res = catalog.gaia_tap(adql="SELECT 1")
            self.assertNotIn("error", res)
        self.assertEqual(h.out.getvalue(), "")
        self.assertIn("sync job diagnostic", h.err.getvalue())


class QueryPyGatewayTest(unittest.TestCase):
    """T32-5 — through query.py in-process: the Gaia-direct subcommands keep their JSON on stdout under the
    retry-then-success hook, with no banner; every other Gaia-reaching subcommand shares this one gateway
    (pinned structurally: astroquery.gaia is imported nowhere else)."""

    def _run(self, *args):
        from tests._queryharness import run_query_inproc
        with mock.patch.dict(sys.modules, {"astroquery.gaia": _fake_gaia()}), \
                mock.patch.dict(os.environ, {"SPACE_APP_CATALOG_CACHE": "0",
                                             "SPACE_APP_GAIA_FORCE_FIRST_ATTEMPT_TIMEOUT": "1"}):
            catalog.reset_gaia_sync_circuit()
            try:
                return run_query_inproc(*args)
            finally:
                catalog.set_gaia_timeout(None)

    def test_gaia_tap_subcommand(self):
        with mock.patch.dict(os.environ, {"SPACE_APP_GAIA_TIMEOUT": "5"}):
            code, payload, err = self._run("gaia-tap", "--adql", "SELECT 1")
        self.assertEqual(code, 0)
        self.assertIsNotNone(payload)                           # stdout parsed as JSON — no preamble
        self.assertNotIn("error", payload)

    def test_gaia_astrophysical_subcommand(self):
        with mock.patch.dict(os.environ, {"SPACE_APP_GAIA_TIMEOUT": "5"}):
            code, payload, err = self._run("gaia-astrophysical", "--source-id", "1")
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(payload)                           # stdout parsed as JSON — no banner preamble
        self.assertNotIn("banner", json.dumps(payload))

    def test_single_gateway(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        hits = [str(p.relative_to(root)) for p in list((root / "core").glob("*.py")) + [root / "query.py"]
                if "astroquery.gaia" in p.read_text(encoding="utf-8")]
        self.assertEqual(hits, ["core/catalog.py"])


if __name__ == "__main__":
    unittest.main()
