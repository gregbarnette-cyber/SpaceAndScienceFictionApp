"""Part B (PERMANENT) — the ESA Gaia login (CDS_OUTAGE_FALLBACK_PLAN.md §3). Offline: astroquery.gaia is replaced by
a fake (importing the real one makes a network call), and TapPlus.login is stubbed to mimic astroquery's real
behaviour (a wrong password prints the 401 page to stdout and raises HTTPError). The real credentials file is never
read (conftest `_gaia_login_off`); each test opting in writes its own tmp file."""

import os
import re
import sys
import types

import pytest

from core import catalog, gaia_auth

WB_SERVICE = re.compile(r"could not connect|timed out|time-out|\btimeout\b|HTTP(?: error)?\s*5\d\d|\b50[234]\b|gateway|"
                        r"connection (?:refused|reset|aborted|error)|temporarily unavailable|service unavailable|"
                        r"max retries|remote end closed|name or service not known|unreachable", re.I)
WB_STDERR_DEGRADE = re.compile(r"degrading|timed out|Read timed out|HTTP Error 5\d\d|ConnectionError")
SENTINEL = "s3ntinel-PASSWORD-q7"


def _table():
    from astropy.table import Table
    return Table({"source_id": [1, 2]})


class _Job:
    def __init__(self, jobid=None, fail=False):
        self.jobid, self.fail = jobid, fail

    def get_results(self):
        if self.fail:
            raise RuntimeError("results lost")
        return _table()


class _Conn:
    def __init__(self):
        self._TapConn__cookie = None

    def set_cookie(self, c):
        self._TapConn__cookie = c


class _FakeGaia:
    made, launched, removed = [], [], []
    async_fail = False
    remove_fail = False

    def __init__(self, show_server_messages=False):
        self.ROW_LIMIT = 50
        self._conn = _Conn()
        _FakeGaia.made.append(self)

    def _TapPlus__getconnhandler(self):
        return self._conn

    def login(self, *a, **k):                         # GaiaClass.login swallows errors — the app must not use it
        raise AssertionError("GaiaClass.login must not be used")

    def launch_job(self, q):
        _FakeGaia.launched.append(("sync", q, getattr(self, "_TapPlus__isLoggedIn", False)))
        return _Job()

    def launch_job_async(self, q, name=None, background=False):
        jid = f"job{len(_FakeGaia.launched)}-O"
        _FakeGaia.launched.append(("async", name, getattr(self, "_TapPlus__isLoggedIn", False)))
        return _Job(jid, fail=_FakeGaia.async_fail)

    def remove_jobs(self, ids):
        if _FakeGaia.remove_fail:
            raise RuntimeError("remove failed")
        _FakeGaia.removed.append(list(ids))


@pytest.fixture
def fake(monkeypatch, tmp_path):
    mod = types.ModuleType("astroquery.gaia")
    mod.GaiaClass = _FakeGaia
    mod.Gaia = _FakeGaia()
    monkeypatch.setitem(sys.modules, "astroquery.gaia", mod)
    _FakeGaia.made, _FakeGaia.launched, _FakeGaia.removed = [], [], []
    _FakeGaia.async_fail = _FakeGaia.remove_fail = False
    monkeypatch.setenv("SPACE_APP_CATALOG_CACHE", "0")
    monkeypatch.setattr(catalog, "_gaia_sync_down", None)
    monkeypatch.setattr(gaia_auth, "_marker_path", lambda: tmp_path / "gaia_login_failed")
    calls = []

    def login(client, credentials_file=None, verbose=False):
        calls.append(credentials_file)
        if fake.mode == "ok":
            client._TapPlus__isLoggedIn = True
            client._conn.set_cookie("JSESSIONID=abc")
            print("INFO: OK")                           # astroquery's stdout chatter
            return
        print("401 Error 401:\n<!doctype html><title>HTTP Status 401 – Unauthorized</title>")
        import requests
        if fake.mode == "bad":
            raise requests.exceptions.HTTPError("Error 401:\nUnauthorized")
        raise requests.exceptions.ConnectionError("Connection aborted")
    from astroquery.utils.tap.core import TapPlus
    monkeypatch.setattr(TapPlus, "login", staticmethod(login))
    fake.mode = "ok"
    fake.calls = calls
    return fake


def _creds(monkeypatch, tmp_path, mode=0o600):
    p = tmp_path / "gaia_credentials"
    p.write_text(f"someuser\n{SENTINEL}\n")
    os.chmod(p, mode)
    monkeypatch.setenv(gaia_auth.CRED_ENV, str(p))
    return p


def test_no_credentials_is_anonymous_and_says_so(fake, capsys):
    out = catalog.gaia_tap(adql="SELECT 1")
    assert out["count"] == 2 and fake.calls == []
    assert _FakeGaia.launched == [("sync", "SELECT 1", False)]
    assert capsys.readouterr().err.strip() == "[gaia-login] anonymous (no credentials)"


def test_one_login_per_process_session_reused_on_fresh_clients(fake, monkeypatch, tmp_path, capsys):
    p = _creds(monkeypatch, tmp_path)
    catalog.gaia_tap(adql="SELECT 1"); catalog.gaia_tap(adql="SELECT 2")
    assert fake.calls == [str(p)]                            # one real login; the 2nd fresh client reuses the session
    assert len(_FakeGaia.made) == 2                          # two fresh clients, one login
    assert _FakeGaia.made[-1]._conn._TapConn__cookie == "JSESSIONID=abc"
    assert all(logged for _, _, logged in _FakeGaia.launched)
    monkeypatch.setattr(gaia_auth, "SESSION_REUSE_S", 0.0)  # past the reuse window → a fresh login
    catalog.gaia_tap(adql="SELECT 3")
    assert fake.calls == [str(p), str(p)]
    cap = capsys.readouterr()
    assert cap.err.count("[gaia-login] logged in") == 1 and "INFO: OK" not in cap.out


def test_wrong_password_falls_back_latches_and_backs_off(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    fake.mode = "bad"
    out = catalog.gaia_tap(adql="SELECT 1")
    assert out["count"] == 2 and _FakeGaia.launched[-1][2] is False          # anonymous, never an error
    catalog.gaia_tap(adql="SELECT 2")
    assert len(fake.calls) == 1                                               # latched: no second login attempt
    assert (tmp_path / "gaia_login_failed").is_file()                         # 401 → the back-off marker
    cap = capsys.readouterr()
    assert "401" not in cap.out and "doctype" not in cap.out                  # the 401 page never reaches stdout
    assert cap.err.strip() == "[gaia-login] anonymous (login not used — continuing anonymous)"
    gaia_auth._reset_for_tests()
    catalog.gaia_tap(adql="SELECT 3")
    assert len(fake.calls) == 1                                               # a new process: still paused
    assert "login paused by back-off marker" in capsys.readouterr().err


def test_connection_error_has_no_class_name_unless_debug(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    fake.mode = "conn"
    catalog.gaia_tap(adql="SELECT 1")
    err = capsys.readouterr().err
    assert "ConnectionError" not in err and not WB_STDERR_DEGRADE.search(err) and not WB_SERVICE.search(err)
    assert not (tmp_path / "gaia_login_failed").exists()                      # not a 401/403 → no marker
    gaia_auth._reset_for_tests()
    monkeypatch.setenv(gaia_auth.DEBUG_ENV, "1")
    catalog.gaia_tap(adql="SELECT 2")
    assert "[ConnectionError]" in capsys.readouterr().err


def test_sentinel_password_never_appears(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    for mode in ("ok", "bad", "conn"):
        gaia_auth._reset_for_tests()
        (tmp_path / "gaia_login_failed").unlink(missing_ok=True)
        fake.mode = mode
        res = catalog.gaia_tap(adql="SELECT 1", use_async=(mode == "ok"))
        cap = capsys.readouterr()
        assert SENTINEL not in cap.out + cap.err + repr(res)


def test_async_logged_in_named_job_deleted_after_reading(fake, monkeypatch, tmp_path):
    _creds(monkeypatch, tmp_path)
    out = catalog.gaia_tap(adql="SELECT 1", use_async=True, row_limit=-1)
    assert out["count"] == 2
    (kind, name, logged), = _FakeGaia.launched
    assert kind == "async" and logged and name.startswith("space_app-")
    assert _FakeGaia.removed == [["job0-O"]]


def test_async_failure_deletes_every_job_it_created_then_falls_back(fake, monkeypatch, tmp_path):
    _creds(monkeypatch, tmp_path)
    monkeypatch.setattr(catalog, "_gaia_async_logged_in",
                        lambda q, rl, attempts=3, base_delay=0.0, _f=catalog._gaia_async_logged_in: _f(q, rl, attempts, 0.0))
    monkeypatch.setattr(catalog, "_with_retries", lambda fn, *a, retries=3, base_delay=0, **k: fn(*a, **k))
    _FakeGaia.async_fail = True
    out = catalog.gaia_tap(adql="SELECT 1", use_async=True)
    assert _FakeGaia.removed == [["job0-O", "job1-O", "job2-O"]]
    assert _FakeGaia.launched[-1] == ("async", None, False)       # then HEAD's anonymous path ran
    assert "error" in out                                          # (it fails here too: the fake always fails)


def test_slow_login_has_its_own_bound(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    monkeypatch.setattr(gaia_auth, "LOGIN_TIMEOUT_S", 0.2)
    import time as _t
    from astroquery.utils.tap.core import TapPlus
    monkeypatch.setattr(TapPlus, "login", staticmethod(lambda *a, **k: _t.sleep(2)))
    out = catalog.gaia_tap(adql="SELECT 1")
    assert out["count"] == 2 and _FakeGaia.launched[-1][2] is False       # anonymous, the query bound untouched
    assert "login not used" in capsys.readouterr().err


def test_logged_in_cache_written_only_after_a_real_login(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("SPACE_APP_CATALOG_CACHE", "1")
    _creds(monkeypatch, tmp_path)
    fake.mode = "conn"                                                     # login fails → anonymous fallback
    catalog.gaia_tap(adql="SELECT 9")
    params = {"adql": "SELECT 9", "table": None, "columns": None, "where": None, "cone": None,
              "row_limit": 2000, "async": False, "auth": True}
    assert catalog.catalog_cache.cache_get(catalog.catalog_cache.cache_key("gaia", params)) is None


def test_failed_delete_leaves_result_and_says_so(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    _FakeGaia.remove_fail = True
    out = catalog.gaia_tap(adql="SELECT 1", use_async=True)
    assert out["count"] == 2
    assert "[gaia-login] job cleanup skipped — job job0-O left on the account" in capsys.readouterr().err


def test_anonymous_async_uses_heads_path_and_deletes_nothing(fake, capsys):
    out = catalog.gaia_tap(adql="SELECT 1", use_async=True)
    assert out["count"] == 2 and _FakeGaia.removed == []
    assert _FakeGaia.launched == [("async", None, False)]
    assert capsys.readouterr().err.strip() == "[gaia-login] anonymous (no credentials)"   # the state line here too


@pytest.mark.parametrize("mode,warns", [(0o644, True), (0o640, True), (0o604, True), (0o600, False), (0o400, False)])
def test_mode_bit_warning(fake, monkeypatch, tmp_path, capsys, mode, warns):
    _creds(monkeypatch, tmp_path, mode)
    catalog.gaia_tap(adql="SELECT 1")
    err = capsys.readouterr().err
    assert (f"(mode {mode:04o})" in err) is warns


def test_legacy_unbounded_path_stays_anonymous(fake, monkeypatch, tmp_path, capsys):
    _creds(monkeypatch, tmp_path)
    monkeypatch.setenv("SPACE_APP_GAIA_TIMEOUT", "0")
    catalog.gaia_tap(adql="SELECT 1")
    assert fake.calls == [] and "anonymous (legacy unbounded path)" in capsys.readouterr().err


def test_auth_cache_key_only_when_logged_in(fake, monkeypatch, tmp_path):
    seen = []
    real_key = catalog.catalog_cache.cache_key
    monkeypatch.setattr(catalog.catalog_cache, "cache_key", lambda svc, params: seen.append(dict(params)) or real_key(svc, params))
    catalog.gaia_tap(adql="SELECT 1")
    _creds(monkeypatch, tmp_path)
    gaia_auth._reset_for_tests()
    catalog.gaia_tap(adql="SELECT 1")
    assert "auth" not in seen[0] and seen[1]["auth"] is True


def test_heads_gaia_degrade_line_is_unchanged(capsys):
    catalog._bounded_error("timeout", "SELECT 1")
    assert capsys.readouterr().err.startswith("[gaia] sync TAP bounded (timeout) — degrading: SELECT 1")


@pytest.mark.parametrize("line", [
    "[gaia-login] logged in",
    "[gaia-login] anonymous (no credentials)",
    "[gaia-login] anonymous (login not used — continuing anonymous)",
    "[gaia-login] anonymous (login paused by back-off marker)",
    "[gaia-login] anonymous (legacy unbounded path)",
    "[gaia-login] credentials file is readable by group or others (mode 0644)",
    "[gaia-login] credentials file is readable by group or others (mode 0504)",
    "[gaia-login] job cleanup skipped — job 1731338474562O left on the account",
    "[gaia-login] job cleanup skipped — job 8b29f800-de29-11f1-a3a4-bc97e148b76b-O left on the account",
])
def test_part_b_stderr_lines_match_neither_wb_regex(line):
    assert not WB_SERVICE.search(line), line
    assert not WB_STDERR_DEGRADE.search(line), line
