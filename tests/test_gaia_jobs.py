"""Part B / D2 (PERMANENT) — `query.py gaia-jobs [--cleanup]`: the ESA account's own leftover `space_app-*` async
jobs. Offline: the job listing is a stubbed seam; the real credentials file is never read."""

import json
import pathlib
import subprocess
import sys

import pytest

from core import gaia_auth

REPO = pathlib.Path(__file__).resolve().parent.parent
NOW = 1_800_000_000.0                                    # fixed clock


def _iso(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


JOBS = {   # id → (phase, name, age seconds)
    "a-O": ("COMPLETED", "space_app-11111111-1111-1111-1111-111111111111", 1200),     # finished 20 min ago → deleted
    "b-O": ("EXECUTING", "space_app-22222222-2222-2222-2222-222222222222", 600),        # live run → kept
    "c-O": ("EXECUTING", "space_app-33333333-3333-3333-3333-333333333333", 3 * 3600),   # stuck > 2 h → deleted
    "d-O": ("COMPLETED", "my own analysis", 60),                                         # never touched
    "e-O": ("ERROR", "", 99999),                                                          # no name → never touched
    "f-O": ("ABORTED", "space_app-66666666-6666-6666-6666-666666666666", 30),        # just finished → kept
}
NS = 'xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0" xmlns:xlink="http://www.w3.org/1999/xlink"'


class _Client:
    def __init__(self, fail=()):
        self.removed, self.fail = [], set(fail)

    def remove_jobs(self, ids):
        (jid,) = ids
        if jid in self.fail:
            raise RuntimeError("delete failed")
        self.removed.append(jid)


def _seam(client, path):
    if path == "async":
        refs = "".join(f'<uws:jobref id="{j}" xlink:href="x"><uws:phase>{p}</uws:phase></uws:jobref>'
                       for j, (p, _, _) in JOBS.items())
        return f'<uws:jobs {NS} total="{len(JOBS)}">{refs}</uws:jobs>'
    jid = path.split("/", 1)[1]
    phase, name, age = JOBS[jid]
    return (f"<uws:job {NS}><uws:jobId>{jid}</uws:jobId><uws:creationTime>{_iso(NOW - age)}</uws:creationTime>"
            f'<uws:parameters><uws:parameter id="jobname"><![CDATA[{name}]]></uws:parameter></uws:parameters></uws:job>')


@pytest.fixture
def creds(monkeypatch, tmp_path):
    p = tmp_path / "gaia_credentials"
    p.write_text("u\np\n")
    p.chmod(0o600)
    monkeypatch.setenv(gaia_auth.CRED_ENV, str(p))
    monkeypatch.setattr(gaia_auth, "_job_seam", _seam)


def test_list_only_deletes_nothing(creds):
    c = _Client()
    out = gaia_auth.list_app_jobs(cleanup=False, client=c, now=NOW)
    assert sorted(r["id"] for r in out["listed"]) == ["a-O", "b-O", "c-O", "f-O"]
    assert c.removed == [] and out["deleted"] == [] and out["cleanup"] is False


def test_cleanup_deletes_only_finished_or_old_space_app_jobs(creds):
    c = _Client()
    out = gaia_auth.list_app_jobs(cleanup=True, client=c, now=NOW)
    assert sorted(c.removed) == ["a-O", "c-O"]
    assert sorted(k["id"] for k in out["kept"]) == ["b-O", "f-O"]          # a live run; a just-finished job
    assert "d-O" not in c.removed and "e-O" not in c.removed         # no prefix → never touched


def test_one_failed_delete_is_reported_and_the_rest_continue(creds):
    c = _Client(fail={"a-O"})
    out = gaia_auth.list_app_jobs(cleanup=True, client=c, now=NOW)
    assert out["errors"] == [{"id": "a-O", "error": "delete failed"}]
    assert sorted(c.removed) == ["c-O"]


def test_an_error_page_is_an_error_not_no_jobs(creds, monkeypatch):
    def bad(client, path):
        raise gaia_auth._ListingError("HTTP 503")
    monkeypatch.setattr(gaia_auth, "_job_seam", bad)
    assert "error" in gaia_auth.list_app_jobs(cleanup=True, client=_Client(), now=NOW)


def test_not_logged_in_is_an_error():
    out = gaia_auth.list_app_jobs(cleanup=True, client=_Client())   # conftest: no credentials
    assert "error" in out


def test_subcommand_without_credentials_exits_1_with_json():
    from tests._queryharness import make_env
    p = subprocess.run([sys.executable, str(REPO / "query.py"), "gaia-jobs", "--cleanup"], capture_output=True,
                       text=True, cwd=str(REPO), env=make_env(), timeout=60)
    assert p.returncode == 1 and "error" in json.loads(p.stdout)
