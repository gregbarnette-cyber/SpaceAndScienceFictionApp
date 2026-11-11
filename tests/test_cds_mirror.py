"""TEMPORARY — CDS-outage mirror mode (CDS_OUTAGE_FALLBACK_PLAN.md Part A). Offline: every network call is stubbed.

Remove with mirror mode (CDS_RESTORE_PLAN.md). Covers: the switch + latch, the one mode line, SIMBAD routing, the
three-query otype split (vs the single join), the VizieR mirror producer (fresh client per attempt, cut-off loud,
breaker on timeout only, no cache write), TIC's cut-off, the 2MASS decoded-position cone, the X-Match line, the
GUI title, and the wording rule against WB's two scorer regexes (copied verbatim)."""

import collections
import io
import os
import pathlib
import re
import subprocess
import sys
import threading
import unittest
from unittest import mock

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core import cds_mirror as cm          # noqa: E402
from core import catalog, catalog_cache, databases, twomass, xray_catalog   # noqa: E402

# WB's scorer patterns, VERBATIM — scifiWorldBuilding-Claude/research/star-analysis-cr-queue/cr30-regate/score_cr30.py
# L69-71 (SERVICE) and L119 (the stderr degrade check). A new stderr line must match NEITHER; a mirror FAILURE's
# stdout error string MUST match SERVICE (so WB's scorer reads it as a degrade, not a value change).
WB_SERVICE = re.compile(r"could not connect|timed out|time-out|\btimeout\b|HTTP(?: error)?\s*5\d\d|\b50[234]\b|gateway|"
                        r"connection (?:refused|reset|aborted|error)|temporarily unavailable|service unavailable|"
                        r"max retries|remote end closed|name or service not known|unreachable", re.I)
WB_STDERR_DEGRADE = re.compile(r"degrading|timed out|Read timed out|HTTP Error 5\d\d|ConnectionError")


def _mirror_on(monkeypatch, flag=None):
    """Turn mirror mode on for one test (the conftest fixture turns it off again)."""
    if flag is None:
        monkeypatch.setenv(cm.ENV, "1")
    else:
        monkeypatch.delenv(cm.ENV, raising=False)
        monkeypatch.setattr(cm, "_flag_path", lambda: flag)
    cm._reset_for_tests()


# ── the switch ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_off_by_default_is_head(monkeypatch, capsys):
    monkeypatch.setenv(cm.VIZIER_TIMEOUT_ENV, "45")
    from astroquery.simbad import conf
    before = conf.server
    assert cm.enabled() is False
    assert cm.vizier_server_kwargs() == {}
    assert cm.vizier_timeout(60) == 60                 # the mirror-only env var is ignored when off
    assert cm.skip_cache_write("vizier") is False
    assert cm.window_title_suffix() == ""
    cm.apply_simbad(); cm.announce(); cm.xmatch_unavailable_note()
    assert conf.server == before
    assert capsys.readouterr().err == ""


def test_on_via_env_and_via_flag(monkeypatch, tmp_path):
    _mirror_on(monkeypatch)
    assert cm.enabled() and cm._STATE["source"] == "env"
    flag = tmp_path / "cds_mirror"
    flag.write_text("")
    _mirror_on(monkeypatch, flag=flag)
    assert cm.enabled() and cm._STATE["source"] == "flag"


def test_env_zero_beats_the_flag_and_latch_holds(monkeypatch, tmp_path):
    flag = tmp_path / "cds_mirror"
    flag.write_text("")
    monkeypatch.setattr(cm, "_flag_path", lambda: flag)
    monkeypatch.setenv(cm.ENV, "0")
    cm._reset_for_tests()
    assert cm.enabled() is False
    monkeypatch.delenv(cm.ENV)
    assert cm.enabled() is False                       # latched: a mid-process change is not seen
    cm._reset_for_tests()
    assert cm.enabled() is True
    flag.unlink()
    assert cm.enabled() is True                        # still latched on until the process restarts


def test_apply_simbad_points_both_at_cfa_and_is_idempotent(monkeypatch):
    _mirror_on(monkeypatch)
    from astroquery.simbad import conf
    import astroquery.simbad as sm
    cm.apply_simbad(); cm.apply_simbad()
    assert conf.server == cm.SIMBAD_MIRROR
    assert sm.Simbad.server == cm.SIMBAD_MIRROR


def test_vizier_timeout_in_mirror_mode(monkeypatch):
    _mirror_on(monkeypatch)
    assert cm.vizier_timeout(60) == 60.0
    monkeypatch.setenv(cm.VIZIER_TIMEOUT_ENV, "45")
    assert cm.vizier_timeout(60) == 45.0


def test_cache_skip_is_exactly_the_seven_cds_services(monkeypatch):
    assert cm.CACHE_SKIP_SERVICES == {"vizier", "cr26_tic", "simbad_otypes", "simbad_cr26_astrom",
                                      "simbad_cr26_cone", "simbad_cr26_parent", "simbad_cr24_velocity"}
    _mirror_on(monkeypatch)
    assert cm.skip_cache_write("vizier") and not cm.skip_cache_write("gaia_tap")


def test_gui_title_suffix(monkeypatch):
    assert cm.window_title_suffix() == ""
    _mirror_on(monkeypatch)
    assert cm.window_title_suffix() == " — CDS MIRROR MODE"


# ── the mode line ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_exactly_one_mode_line_under_threads(monkeypatch, capsys):
    _mirror_on(monkeypatch)
    ts = [threading.Thread(target=cm.announce) for _ in range(24)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    cm.vizier_server_kwargs(); cm.apply_simbad()
    err = capsys.readouterr().err
    assert err.count("[cds-mirror] ") == 1
    assert err.startswith("[cds-mirror] SIMBAD→simbad.harvard.edu VizieR→vizier.idia.ac.za — temporary, on via "
                          "SPACE_APP_CDS_MIRROR")


def test_mode_line_carries_the_flag_age(monkeypatch, tmp_path, capsys):
    flag = tmp_path / "cds_mirror"
    flag.write_text("")
    t = os.path.getmtime(flag) - 3 * 86400 - 60
    os.utime(flag, (t, t))
    _mirror_on(monkeypatch, flag=flag)
    cm.announce()
    assert re.search(r"on since \d{4}-\d\d-\d\d \(3d\)\n$", capsys.readouterr().err)


def test_xmatch_line_follows_the_mode_line_once(monkeypatch, capsys):
    _mirror_on(monkeypatch)
    cm.xmatch_unavailable_note(); cm.xmatch_unavailable_note()
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 2 and lines[0].startswith("[cds-mirror] SIMBAD→")
    assert lines[1] == ("[cds-mirror] X-Match has no mirror — census SB9 rows dropped; this census output is "
                        "not valid")


def test_no_line_on_a_cache_only_vizier_run(monkeypatch, capsys):
    _mirror_on(monkeypatch)
    monkeypatch.setattr(catalog_cache, "cache_get", lambda key, ttl_s=None: {"service": "vizier", "rows": [{"a": 1}]})
    out = catalog.vizier_query("B/sb9/main", cone="1 2 0.006")
    assert out["rows"] == [{"a": 1}]
    assert capsys.readouterr().err == ""


# ── the wording rule (stderr lines must match neither WB regex) ───────────────────────────────────────────────────
def _mode_lines():
    head = "[cds-mirror] SIMBAD→simbad.harvard.edu VizieR→vizier.idia.ac.za — temporary, "
    out = [head + "on via SPACE_APP_CDS_MIRROR"]
    out += [head + f"on since 2026-11-{d:02d} ({n}d)" for d, n in ((12, 0), (11, 1), (9, 3), (28, 14))]
    out += [head + "on since 2026-11-12 (502d)"]       # an implausible age is still clean (no '50x' word-boundary)
    return out


@pytest.mark.parametrize("line", _mode_lines() + [
    "[cds-mirror] X-Match has no mirror — census SB9 rows dropped; this census output is not valid"])
def test_part_a_stderr_lines_match_neither_wb_regex(line):
    assert not WB_SERVICE.search(line), line
    assert not WB_STDERR_DEGRADE.search(line), line


def test_part_a_stdout_failure_strings_match_service():
    import requests
    from core.shared import _network_error_msg
    cut = _network_error_msg(catalog._VizierCutOff("VizieR mirror unreachable: empty answer (server cut-off)"),
                             "CDS VizieR")
    to = _network_error_msg(requests.exceptions.Timeout("x"), "CDS VizieR")
    assert cut.startswith("Could not connect to CDS VizieR") and WB_SERVICE.search(cut)
    assert to == "CDS VizieR request timed out. Try again." and WB_SERVICE.search(to)


# ── the otype split vs the single join ────────────────────────────────────────────────────────────────────────────
class _FakeSimbad:
    """A tiny SIMBAD: ident (oid, stored id) / otypes (oid, otype) / basic (oid, main_id). ident matching is
    space-insensitive and returns the STORED id, as SIMBAD TAP does."""

    def __init__(self, ident, otypes, basic):
        self.ident, self.otypes, self.basic = ident, otypes, basic
        self.calls = []

    @staticmethod
    def _k(s):
        return "".join(str(s).split()).casefold()

    def join(self, ids):
        want = {self._k(i) for i in ids}
        out = []
        for oid, sid in self.ident:
            if self._k(sid) in want and oid in dict(self.basic):
                for o, ot in self.otypes:
                    if o == oid:
                        out.append((dict(self.basic)[oid], sid, ot))
        return out

    def rows(self, adql):
        self.calls.append(adql)
        if adql.startswith("SELECT i.oidref, i.id FROM ident AS i WHERE "):
            want = {self._k(x.replace("''", "'")) for x in re.findall(r"i\.id = '((?:[^']|'')*)'", adql)}
            return [{"oidref": oid, "id": sid} for oid, sid in self.ident if self._k(sid) in want]
        oids = {int(x) for x in re.search(r"IN \(([^)]*)\)", adql).group(1).split(",")}
        if adql.startswith("SELECT oidref, otype FROM otypes"):
            return [{"oidref": o, "otype": ot} for o, ot in self.otypes if o in oids]
        if adql.startswith("SELECT oid, main_id FROM basic"):
            return [{"oid": o, "main_id": m} for o, m in self.basic if o in oids]
        raise AssertionError(adql)


_CASES = {
    "no_ident": (_FakeSimbad([], [], []), ["Nobody", None]),
    "head_and_candidate_distinct": (_FakeSimbad([(1, "G 272-61"), (2, "G 272-61A")],
                                                [(1, "**"), (2, "Er*"), (2, "PM*")],
                                                [(1, "G 272-61"), (2, "G 272-61A")]), ["G 272-61", "G 272-61 A"]),
    "both_ids_same_oid": (_FakeSimbad([(5, "* alf CMa"), (5, "* alf CMa A")], [(5, "SB*"), (5, "PM*")],
                                      [(5, "* alf CMa")]), ["* alf CMa", "* alf CMa A"]),
    "one_id_several_oids": (_FakeSimbad([(7, "X 1"), (8, "X 1")], [(7, "*"), (8, "PM*")], [(7, "X 1"), (8, "X 1 B")]),
                            ["X 1", None]),
    "candidate_is_head": (_FakeSimbad([(9, "Y 2"), (9, "Y 2 A")], [(9, "BY*")], [(9, "Y 2")]), ["Y 2", "Y 2 A"]),
    "oid_missing_from_basic": (_FakeSimbad([(3, "Z 3"), (4, "Z 3 A")], [(3, "*"), (4, "Fl*")], [(3, "Z 3")]),
                               ["Z 3", "Z 3 A"]),
}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_split_equals_the_join(name, monkeypatch):
    fake, (main_id, cand) = _CASES[name]
    ids = [main_id] + ([cand] if cand else [])
    monkeypatch.setattr(databases, "_simbad_tap_rows", fake.rows)
    got = databases._simbad_otypes_split(main_id, cand)
    assert collections.Counter(got) == collections.Counter(fake.join(ids))
    if not got:
        assert len(fake.calls) == 1                     # no ident row → no further query (the join's empty answer)
        return
    assert fake.calls[0].startswith("SELECT i.oidref, i.id FROM ident AS i WHERE i.id = ")   # HEAD's `i` alias

    def interp(rows):
        try:
            return databases._interpret_otype_rows(rows, main_id, cand)
        except databases._OtypeResultError:
            return "error"
    assert interp(got) == interp(fake.join(ids))


def test_split_maps_a_bad_column_to_result_error(monkeypatch):
    monkeypatch.setattr(databases, "_simbad_tap_rows", lambda adql: [{"wrong": 1}])
    with pytest.raises(databases._OtypeResultError):
        databases._simbad_otypes_split("A", None)


def test_fetch_star_otypes_uses_the_split_only_in_mirror_mode(monkeypatch):
    monkeypatch.setenv("SPACE_APP_CATALOG_CACHE", "0")     # the off-run's rows would otherwise answer from the cache
    databases.reset_simbad_otypes_circuit()
    seen = {}
    monkeypatch.setattr(databases, "_simbad_otypes_tap", lambda adql: seen.setdefault("tap", adql) and
                        [("G 272-61A", "G 272-61A", "Er*")])
    src = _CASES["head_and_candidate_distinct"][0]
    fake = _FakeSimbad(src.ident, src.otypes, src.basic)
    monkeypatch.setattr(databases, "_simbad_tap_rows", fake.rows)
    off = databases.fetch_star_otypes("G 272-61", "**")
    assert seen["tap"] == databases._otypes_query("G 272-61", True)[0]     # HEAD's ADQL, byte-identical
    assert fake.calls == []
    _mirror_on(monkeypatch)
    on = databases.fetch_star_otypes("G 272-61", "**")
    assert fake.calls and on["codes"] == ["Er*", "PM*"] and on["source_main_id"] == "G 272-61A"
    assert off["source_main_id"] == "G 272-61A"


# ── the VizieR mirror producer ────────────────────────────────────────────────────────────────────────────────────
class _FakeVizier:
    """Stands in for astroquery's Vizier; a script of per-attempt outcomes."""
    made = []
    script = []

    def __init__(self, **kw):
        self.kw = kw
        _FakeVizier.made.append(kw)

    def _next(self):
        step = _FakeVizier.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step

    def query_region(self, *a, **k):
        return self._next()

    def query_constraints(self, *a, **k):
        return self._next()


def _table():
    from astropy.table import Table
    return [Table({"2MASS": ["18365633+3847012"], "Kmag": [0.129]})]


@pytest.fixture
def fake_vizier(monkeypatch):
    import astroquery.vizier as av
    _FakeVizier.made, _FakeVizier.script = [], []
    monkeypatch.setattr(av, "Vizier", _FakeVizier)
    monkeypatch.setattr(catalog, "_VIZIER_MIRROR_BACKOFF", 0.0)
    monkeypatch.setattr(catalog, "_vizier_mirror_down", {})
    return _FakeVizier


def test_mirror_fresh_client_per_attempt_and_no_head_helpers(monkeypatch, fake_vizier):
    import requests
    _mirror_on(monkeypatch)
    monkeypatch.setattr(catalog, "_with_retries", lambda *a, **k: (_ for _ in ()).throw(AssertionError("retries")))
    monkeypatch.setattr(catalog, "_timeout_ctx", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ctx")))
    fake_vizier.script = [requests.exceptions.ConnectionError("x"), _table()]
    out = catalog.vizier_query("II/246/out", cone="279.23 38.78 0.0008")
    assert out["count"] == 1
    assert len(fake_vizier.made) == 2
    assert all(m["vizier_server"] == "vizier.idia.ac.za" and m["timeout"] == 60.0 for m in fake_vizier.made)


def test_mirror_none_is_a_fatal_loud_cutoff(monkeypatch, fake_vizier):
    _mirror_on(monkeypatch)
    fake_vizier.script = [None, _table()]
    out = catalog.vizier_query("II/246/out", filters=["2MASS=18365633+3847012"])
    assert "error" in out and out["error"].startswith("Could not connect to CDS VizieR")
    assert WB_SERVICE.search(out["error"])
    assert len(fake_vizier.made) == 1                  # fatal: never retried
    assert catalog._vizier_mirror_down == {}           # a cut-off never trips the breaker


def test_genuine_empty_after_a_failed_attempt_is_an_empty_answer(monkeypatch, fake_vizier):
    import requests
    _mirror_on(monkeypatch)
    fake_vizier.script = [requests.exceptions.ConnectionError("x"), []]
    out = catalog.vizier_query("B/sb9/main", cone="1 2 0.006")
    assert out == {"service": "vizier", "catalog": "B/sb9/main", "count": 0, "truncated": False, "rows": []}


def test_zero_rows_after_the_threshold_is_a_cutoff(monkeypatch, fake_vizier):
    _mirror_on(monkeypatch)
    monkeypatch.setattr(cm, "CUTOFF_ELAPSED_S", 0.0)
    fake_vizier.script = [[]]
    out = catalog.vizier_query("II/246/out", filters=["2MASS=1"])
    assert out["error"].startswith("Could not connect to CDS VizieR")


def test_timeouts_trip_the_breaker_which_rearms(monkeypatch, fake_vizier):
    import requests
    _mirror_on(monkeypatch)
    fake_vizier.script = [requests.exceptions.ReadTimeout("r"), requests.exceptions.ReadTimeout("r")]
    out = catalog.vizier_query("B/wds/wds", cone="1 2 0.006")
    assert out["error"] == "CDS VizieR request timed out. Try again."
    n = len(fake_vizier.made)
    out2 = catalog.vizier_query("B/wds/wds", cone="3 4 0.006")
    assert out2["error"] == "CDS VizieR request timed out. Try again." and len(fake_vizier.made) == n
    fake_vizier.script = [_table()]
    assert catalog.vizier_query("B/sb9/main", cone="3 4 0.006")["count"] == 1     # per catalog: others unaffected
    catalog._vizier_mirror_down["B/wds/wds"] = catalog.time.monotonic() - 61
    fake_vizier.script = [_table()]
    assert catalog.vizier_query("B/wds/wds", cone="5 6 0.006")["count"] == 1   # re-armed after the cool-down


def test_watchdog_text_never_reaches_stdout(monkeypatch, fake_vizier):
    from core.shared import _WatchdogTimeout
    _mirror_on(monkeypatch)

    def _boom(*a, **k):
        raise _WatchdogTimeout("call exceeded 70.0s wall-clock bound")
    monkeypatch.setattr(catalog, "_bounded_call", _boom)
    out = catalog.vizier_query("B/wds/wds", cone="1 2 0.006")
    assert out["error"] == "CDS VizieR request timed out. Try again."


def test_mirror_answers_are_not_cached_but_head_answers_are(monkeypatch, fake_vizier):
    monkeypatch.setenv("SPACE_APP_CATALOG_CACHE", "1")
    params = {"catalog": "B/sb9/main", "columns": None, "filters": None, "cone": "1 2 0.006", "row_limit": 2000}
    key = catalog_cache.cache_key("vizier", params)
    _mirror_on(monkeypatch)
    fake_vizier.script = [_table()]
    assert catalog.vizier_query("B/sb9/main", cone="1 2 0.006")["count"] == 1
    assert catalog_cache.cache_get(key) is None
    monkeypatch.setenv(cm.ENV, "0")
    cm._reset_for_tests()
    monkeypatch.setattr(catalog, "_with_retries", lambda fn, *a, **k: fn(*a, **k))
    fake_vizier.script = [_table()]
    assert catalog.vizier_query("B/sb9/main", cone="1 2 0.006")["count"] == 1
    assert catalog_cache.cache_get(key) is not None


def test_flag_off_keeps_heads_vizier_call(monkeypatch, fake_vizier):
    monkeypatch.setenv(cm.VIZIER_TIMEOUT_ENV, "45")
    used = []
    monkeypatch.setattr(catalog, "_with_retries", lambda fn, *a, **k: used.append(1) or fn(*a, **k))
    fake_vizier.script = [_table()]
    catalog.vizier_query("II/246/out", filters=["2MASS=x"], row_limit=5)
    assert used and fake_vizier.made == [{"columns": ["*"], "column_filters": {"2MASS": "x"}, "row_limit": 5,
                                          "timeout": 60}]


def test_vizier_timeout_env_honoured_in_mirror_mode(monkeypatch, fake_vizier):
    _mirror_on(monkeypatch)
    monkeypatch.setenv(cm.VIZIER_TIMEOUT_ENV, "45")
    fake_vizier.script = [_table()]
    catalog.vizier_query("II/246/out", cone="1 2 0.001")
    assert fake_vizier.made[0]["timeout"] == 45.0


# ── TIC (the real _tic_query: opt out of the conftest's CR-26 seam stubs) ─────────────────────────────────────────
@pytest.mark.cr26_network
def test_tic_none_is_unreachable_in_mirror_mode_only(monkeypatch, fake_vizier):
    xray_catalog.reset_cr26_circuits()
    monkeypatch.setattr(xray_catalog, "_BACKOFF", 0.0)
    fake_vizier.script = [None]
    assert xray_catalog._tic_query(1.0, 2.0) == {"answered": True, "sources": []}          # HEAD
    assert "vizier_server" not in fake_vizier.made[-1]
    _mirror_on(monkeypatch)
    fake_vizier.script = [None, None]
    res, code = xray_catalog._family_call("tic", "cr26_tic", {"ra": 1.0, "dec": 2.0},
                                          lambda: xray_catalog._tic_query(1.0, 2.0), "SPACE_APP_TIC_TIMEOUT")
    assert res is None and code == "unreachable"
    assert fake_vizier.made[-1]["vizier_server"] == "vizier.idia.ac.za"


# ── 2MASS: decode (truncation) and the decoded-position cone ──────────────────────────────────────────────────────
def test_decode_truncated_position():
    ra, dec = cm.decode_2mass_key("18365633+3847012")
    assert ra == pytest.approx((18 + 36 / 60 + 56.33 / 3600) * 15, abs=1e-12)
    assert dec == pytest.approx(38 + 47 / 60 + 1.2 / 3600, abs=1e-12)
    assert cm.decode_2mass_key("J18365633+3847012") == (ra, dec)            # with and without the J prefix


def test_decode_negative_near_a_digit_boundary_and_minus_zero():
    ra, dec = cm.decode_2mass_key("05595999-0959599")
    assert ra == pytest.approx((5 + 59 / 60 + 59.99 / 3600) * 15, abs=1e-12)
    assert dec == pytest.approx(-(9 + 59 / 60 + 59.9 / 3600), abs=1e-12)
    assert cm.decode_2mass_key("12000000-0000001")[1] == pytest.approx(-0.1 / 3600, abs=1e-15)
    assert cm.decode_2mass_key("12000000+0000001")[1] > 0


@pytest.mark.parametrize("bad", ["1836563+3847012", "18365633 3847012", "18365633+384701", "", "2MASS J1"])
def test_decode_rejects_malformed_keys(bad):
    assert cm.decode_2mass_key(bad) is None


@pytest.mark.cr30_twomass
def test_twomass_seam_uses_the_cone_in_mirror_mode(monkeypatch):
    calls = []

    def fake_vq(cat, **kw):
        calls.append((cat, kw))
        rows = [{"2MASS": "18365630+3847099", "Kmag": 9.9}, {"2MASS": "18365633+3847012", "Kmag": 0.129}]
        return {"service": "vizier", "catalog": cat, "count": 2, "row_limit": 50, "truncated": False, "rows": rows}
    monkeypatch.setattr(catalog, "vizier_query", fake_vq)
    _mirror_on(monkeypatch)
    out = twomass._ii246_seam("2MASS J18365633+3847012")
    (cat, kw), = calls
    assert cat == "II/246/out" and kw["row_limit"] == 50 and "filters" not in kw
    ra, dec, r = (float(x) for x in kw["cone"].split())
    assert r == pytest.approx(3.0 / 3600) and ra == pytest.approx(279.2347083, abs=1e-6)
    assert out["rows"] == [{"2MASS": "18365633+3847012", "Kmag": 0.129}] and out["count"] == 1


@pytest.mark.cr30_twomass
def test_twomass_seam_head_path_and_regex_miss(monkeypatch):
    calls = []
    monkeypatch.setattr(catalog, "vizier_query", lambda cat, **kw: calls.append(kw) or {"rows": []})
    twomass._ii246_seam("2MASS J18365633+3847012")
    assert calls[-1] == {"columns": ["2MASS", "Jmag", "e_Jmag", "Kmag", "e_Kmag", "Qflg", "Rflg"],
                         "filters": ["2MASS=18365633+3847012"], "row_limit": 5}
    _mirror_on(monkeypatch)
    n = len(calls)
    out = twomass._ii246_seam("2MASS J1836563+3847012")
    assert "error" in out and len(calls) == n                # never falls back to the designation query


# ── processes: the harness keeps it off; an argparse error's stderr is HEAD's ──────────────────────────────────────
def _py(code, env):
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO), env=env,
                          timeout=60)


def test_harness_keeps_mirror_off_even_with_a_planted_flag(tmp_path):
    from tests._queryharness import make_env
    home = tmp_path / "home"
    (home / ".config" / "space_app").mkdir(parents=True)
    (home / ".config" / "space_app" / "cds_mirror").write_text("")
    code = "import sys; sys.path.insert(0, '.'); import core.cds_mirror as m; print(m.enabled())"
    env = make_env(HOME=str(home))
    assert _py(code, env).stdout.strip() == "False"
    env.pop("SPACE_APP_CDS_MIRROR")
    assert _py(code, env).stdout.strip() == "True"           # the planted flag would otherwise switch it on


def test_argparse_error_stderr_is_identical_in_mirror_mode():
    from tests._queryharness import make_env
    def run(flag):
        p = subprocess.run([sys.executable, str(REPO / "query.py"), "vizier-query", "--no-such-flag"],
                           capture_output=True, text=True, cwd=str(REPO), env=make_env(SPACE_APP_CDS_MIRROR=flag),
                           timeout=60)
        return p.returncode, p.stdout, p.stderr
    assert run("1") == run("0")


# ── CP1 fixes ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_otype_adql_is_heads_literal():
    assert databases._otypes_query("G 272-61", True)[0] == (
        "SELECT b.main_id, i.id AS qid, o.otype FROM ident AS i JOIN basic AS b ON b.oid = i.oidref JOIN otypes AS o "
        "ON o.oidref = b.oid WHERE i.id = 'G 272-61' OR i.id = 'G 272-61 A'")
    assert databases._otypes_query("* alf Cen B", True)[0].endswith("WHERE i.id = '* alf Cen B'")


def test_split_tap_rows_maps_an_answered_error(monkeypatch):
    def boom(adql):
        raise databases._Cr26SimbadAnswered("bad ADQL")
    monkeypatch.setattr(databases, "_simbad_cr26_tap", boom)
    with pytest.raises(databases._OtypeResultError):
        databases._simbad_tap_rows("SELECT 1")


def test_masked_oidref_is_a_result_error_not_unreachable(monkeypatch):
    monkeypatch.setattr(databases, "_simbad_tap_rows", lambda adql: [{"oidref": None, "id": "A"}])
    with pytest.raises(databases._OtypeResultError):
        databases._simbad_otypes_split("A", None)


def test_malformed_cone_fails_at_once(monkeypatch, fake_vizier):
    _mirror_on(monkeypatch)
    out = catalog.vizier_query("B/wds/wds", cone="10 20")
    assert "error" in out and fake_vizier.made == []


def test_xmatch_is_skipped_in_mirror_mode(monkeypatch):
    import astroquery.xmatch as ax
    monkeypatch.setattr(ax, "XMatch", None)            # any use would fail; mirror mode must not reach it
    _mirror_on(monkeypatch)
    out = catalog.xmatch_query([{"ra": 1.0, "dec": 2.0}], cat2="vizier:I/311/hip2")
    assert "error" in out and "no mirror" in out["error"] and WB_SERVICE.search(out["error"])


def test_option_50_is_refused_in_mirror_mode(monkeypatch):
    _mirror_on(monkeypatch)
    out = databases.compute_star_systems_csv()
    assert "error" in out and "mirror mode" in out["error"]


@pytest.mark.cr30_twomass
def test_twomass_cone_keeps_heads_row_limit_shape(monkeypatch):
    rows = [{"2MASS": "18365633+3847012", "Kmag": float(i)} for i in range(6)]
    monkeypatch.setattr(catalog, "vizier_query", lambda cat, **kw: {"service": "vizier", "catalog": cat, "count": 6,
                                                                      "row_limit": 50, "truncated": False, "rows": rows})
    _mirror_on(monkeypatch)
    out = twomass._ii246_seam("2MASS J18365633+3847012")
    assert out["row_limit"] == 5 and out["truncated"] is True and out["count"] == 5 and len(out["rows"]) == 5
