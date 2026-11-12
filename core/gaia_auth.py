"""ESA Gaia archive login (CDS_OUTAGE_FALLBACK_PLAN.md Part B — PERMANENT).

A logged-in ESA account gets its own 50-job queue (anonymous users share ONE 50-job pool worldwide), a 120-minute
async limit (anonymous: 1 min) and no 50,000-row cap. With no credentials the app is anonymous, byte-identical to
before. A login problem NEVER turns a working query into an error: it falls back to anonymous.

Credentials (the app never reads the password — astroquery reads the file):
  1. ``SPACE_APP_GAIA_CREDENTIALS=<path>`` (an EMPTY value = anonymous — the tests' off-switch);
  2. else ``~/.config/space_app/gaia_credentials`` if it exists (two lines: user, password; mode 0600);
  3. else anonymous.

Login is TAP-only ``TapPlus.login`` (it raises on a wrong password; ``GaiaClass.login`` swallows it), once per
process (its session cookie is reused on each fresh client for 30 min), under its own 15 s bound, with its
stdout captured and discarded (astroquery prints the 401 page and INFO lines to stdout). One login-state line per
process on the first Gaia call: ``[gaia-login] logged in`` / ``[gaia-login] anonymous (…)``. A failure latches the
process anonymous; a 401/403 also writes a 6-hour back-off marker so a bad password cannot be retried thousands of
times across a batch run (account lock-out). No line carries an exception class name or an HTTP status unless
``SPACE_APP_GAIA_DEBUG=1``.
"""

import contextlib
import os
import pathlib
import stat
import threading
import time

CRED_ENV = "SPACE_APP_GAIA_CREDENTIALS"
DEBUG_ENV = "SPACE_APP_GAIA_DEBUG"
BACKOFF_S = 6 * 3600.0
JOB_PREFIX = "space_app-"
LOGIN_TIMEOUT_S = 15.0            # its own bound: a slow login must never use up a query's wall-clock bound
SESSION_REUSE_S = 30 * 60.0       # one login per process; the session cookie is reused on fresh clients this long

_LOCK = threading.Lock()
_STATE = {"line": False, "failed": False, "mode_warned": False, "cookie": None, "cookie_at": 0.0, "ok": False}


def _default_path():
    return pathlib.Path(os.path.expanduser("~/.config/space_app/gaia_credentials"))


def _marker_path():
    return pathlib.Path(os.path.expanduser("~/.config/space_app/gaia_login_failed"))


def _reset_for_tests():
    with _LOCK:
        _STATE.update(line=False, failed=False, mode_warned=False, cookie=None, cookie_at=0.0, ok=False)


def _warn(msg):
    from core.shared import _stderr_warn
    _stderr_warn("gaia-login", msg)


def credentials_path():
    """The credentials file to use, or ``None`` (anonymous)."""
    env = os.environ.get(CRED_ENV)
    if env is not None:
        p = pathlib.Path(os.path.expanduser(env)) if env.strip() else None
    else:
        p = _default_path()
    try:
        return p if (p is not None and p.is_file()) else None
    except OSError:
        return None


def _paused():
    try:
        m = _marker_path()
        return m.is_file() and (time.time() - m.stat().st_mtime) < BACKOFF_S
    except OSError:
        return False


def auth_expected():
    """True iff this process will try (or has) logged in — used to key the Gaia cache (logged-in results are not
    capped at 50,000 rows, so they must never share a key with an anonymous result)."""
    with _LOCK:
        failed = _STATE["failed"]
    return (not failed) and credentials_path() is not None and not _paused()


def _state_line(text):
    with _LOCK:
        if _STATE["line"]:
            return
        _STATE["line"] = True
    _warn(text)


def logged_in_ok():
    """True iff a login succeeded in this process and has not failed since (the logged-in cache write gate)."""
    with _LOCK:
        return _STATE["ok"] and not _STATE["failed"]


def _check_mode(p):
    if os.name == "nt":                             # native Windows st_mode is always 0o666 — not meaningful
        return
    with _LOCK:
        if _STATE["mode_warned"]:
            return
        _STATE["mode_warned"] = True
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except OSError:
        return
    if mode & 0o077:
        _warn(f"credentials file is readable by group or others (mode {mode:04o})")


@contextlib.contextmanager
def _quiet():
    """Discard THIS thread's stdout during login / job deletion (the 401 HTML page, INFO lines) — thread-scoped
    (CR-32's router), never a process-global redirect."""
    from core.catalog import _discard_thread_stdout
    with _discard_thread_stdout():
        yield


def note_legacy_path():
    """The bound-disabled sync path (``SPACE_APP_GAIA_TIMEOUT<=0``) stays anonymous; say so once if credentials
    exist."""
    if credentials_path() is not None:
        _state_line("anonymous (legacy unbounded path)")


def note_account_refusal():
    """The logged-in async job was refused by the ACCOUNT (401 / 403 / 429 / a full queue or quota) — the call falls
    back to the anonymous path; say so once."""
    _warn("logged-in job not accepted by the account — continuing anonymous")


def login(client):
    """Log ``client`` (a fresh ``GaiaClass``) into the ESA TAP server. Returns True iff it is logged in; False →
    use it anonymously. Never raises."""
    p = credentials_path()
    if p is None:
        _state_line("anonymous (no credentials)")
        return False
    _check_mode(p)
    with _LOCK:
        failed = _STATE["failed"]
    if failed:
        return False
    if _paused():
        _state_line("anonymous (login paused by back-off marker)")
        return False
    if _reuse_session(client):                      # one real login per process; fresh clients reuse its session
        return True
    status = None
    try:
        from astroquery.utils.tap.core import TapPlus
        from core.shared import _call_with_watchdog

        def _do():
            with _quiet():                          # thread-scoped: inside the worker thread that prints
                TapPlus.login(client, credentials_file=str(p), verbose=False)
        _call_with_watchdog(_do, timeout=LOGIN_TIMEOUT_S)
        ok = bool(getattr(client, "_TapPlus__isLoggedIn", False))
        err = None
        if ok:
            _remember_session(client)
    except Exception as e:                          # noqa: BLE001 — a login problem must never break a query
        ok, err = False, e
        status = _auth_status(e)
    if ok:
        with _LOCK:
            _STATE["ok"] = True
        _state_line("logged in")
        return True
    with _LOCK:
        _STATE["failed"] = True
        _STATE["cookie"] = None
    if status in (401, 403):
        try:
            m = _marker_path()
            m.parent.mkdir(parents=True, exist_ok=True)
            m.write_text(f"{time.time():.0f}\n")
        except OSError:
            pass
    detail = f" [{type(err).__name__}]" if (err is not None and os.environ.get(DEBUG_ENV) == "1") else ""
    _state_line(f"anonymous (login not used — continuing anonymous){detail}")
    return False


_AUTH_ERR_RE = __import__("re").compile(r"(?:^|\n)\s*(?:Error|HTTP Status)\s+(401|403)\b")


def _auth_status(e):
    """401 / 403 from the exception's HTTP status, or astroquery's own ``Error 401:`` / ``HTTP Status 401`` form —
    never a stray ``401`` elsewhere in an error page."""
    code = getattr(getattr(e, "response", None), "status_code", None)
    if code in (401, 403):
        return code
    m = _AUTH_ERR_RE.search(str(e))
    return int(m.group(1)) if m else None


def ensure_session():
    """Establish this process's ESA session OUTSIDE any query bound (one real login per process; refreshed after
    ``SESSION_REUSE_S``). Returns True iff a session is available for ``attach_session``. Writes the login-state line
    (logged in / no credentials / paused / not used). Never raises."""
    p = credentials_path()
    if p is None:
        _state_line("anonymous (no credentials)")
        return False
    with _LOCK:
        failed = _STATE["failed"]
        fresh = _STATE["cookie"] and (time.monotonic() - _STATE["cookie_at"]) < SESSION_REUSE_S
    if failed:
        return False
    if fresh:
        return True
    if _paused():
        _state_line("anonymous (login paused by back-off marker)")
        return False
    from core.catalog import _new_gaia_client           # core.catalog is the one Gaia gateway (CR-32's guard)
    try:
        client = _new_gaia_client()
    except Exception:                                    # noqa: BLE001
        return False
    return login(client)


def attach_session(client):
    """Put the established session on a fresh client — no network. True iff the client is now logged in."""
    return _reuse_session(client)


def _connhandler(client):
    return client._TapPlus__getconnhandler()        # astroquery's per-client connection handler (name-mangled)


def _remember_session(client):
    try:
        cookie = _connhandler(client)._TapConn__cookie
    except Exception:                               # noqa: BLE001 — reuse is an optimisation only
        return
    if cookie:
        with _LOCK:
            _STATE["cookie"], _STATE["cookie_at"] = cookie, time.monotonic()


def _reuse_session(client):
    """Put this process's live session cookie on a fresh client (no new login). False → log in normally."""
    with _LOCK:
        cookie, at = _STATE["cookie"], _STATE["cookie_at"]
    if not cookie or (time.monotonic() - at) >= SESSION_REUSE_S:
        return False
    try:
        _connhandler(client).set_cookie(cookie)
        client._TapPlus__isLoggedIn = True
    except Exception:                               # noqa: BLE001
        return False
    return True


def remove_own_jobs(client, job_ids):
    """Delete exactly ``job_ids`` (jobs this call created) from the account. Best-effort: a failure leaves the job
    and writes one line; the query result is never affected."""
    ids = [j for j in job_ids if j]
    if not ids:
        return
    try:
        with _quiet():
            client.remove_jobs(list(ids))
    except Exception:                               # noqa: BLE001
        for j in ids:
            _warn(f"job cleanup skipped — job {j} left on the account")


def new_job_name():
    import uuid
    return f"{JOB_PREFIX}{uuid.uuid4()}"


# ── D2: `query.py gaia-jobs [--cleanup]` — the app's own leftover async jobs (manual, never automatic) ─────────────
_FINISHED = frozenset({"COMPLETED", "ERROR", "ABORTED"})
CLEANUP_AGE_S = 2 * 3600.0
FINISHED_MIN_AGE_S = 10 * 60.0    # a just-finished job may still be about to be read by a live run


class _ListingError(Exception):
    """The archive did not answer the job listing with HTTP 200."""


def _job_seam(client, path):
    """One authenticated GET on the account's TAP ``async`` resource → the response text (a stubbable seam).
    A non-200 answer raises (an error page must never read as "no jobs")."""
    with _quiet():
        resp = _connhandler(client).execute_tapget(path, verbose=False)
        status = getattr(resp, "status", 200)
        body = resp.read().decode("utf-8", "replace")
    if status != 200:
        raise _ListingError(f"HTTP {status}")
    return body


_UWS = "{http://www.ivoa.net/xml/UWS/v1.0}"


def _parse_listing(xml):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    return [(ref.get("id"), (ref.findtext(f"{_UWS}phase") or "").strip()) for ref in root.iter(f"{_UWS}jobref")]


def _parse_detail(xml):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    name = ""
    for prm in root.iter(f"{_UWS}parameter"):
        if prm.get("id") == "jobname":
            name = (prm.text or "").strip()
    return name, (root.findtext(f"{_UWS}creationTime") or "").strip() or None


def _parse_iso(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def list_app_jobs(cleanup=False, client=None, now=None):
    """The account's async jobs named ``space_app-*`` → ``{cleanup, listed, deleted, kept, errors}``. With
    ``cleanup`` it deletes only those that are ``space_app-*`` AND (finished OR older than 2 h); a job without the
    prefix is never touched. Not logged in → ``{"error"}``."""
    if credentials_path() is None:
        return {"error": "gaia-jobs needs an ESA Gaia login: no credentials file (see docs/integration.md, Gaia login)"}
    if client is None:
        from core.catalog import _new_gaia_client      # core.catalog is the one Gaia gateway (CR-32's guard)
        client = _new_gaia_client()
        if not login(client):
            return {"error": "gaia-jobs needs an ESA Gaia login: the login was not used (anonymous jobs are not "
                             "stored per account)"}
    now = time.time() if now is None else now
    try:
        refs = _parse_listing(_job_seam(client, "async"))
    except Exception:                               # noqa: BLE001 — an unreadable listing is an error, never "no jobs"
        return {"error": "Could not connect to the ESA Gaia archive to list jobs"}
    listed, deleted, kept, errors, eligible = [], [], [], [], []
    for jid, phase in refs:
        try:
            name, created = _parse_detail(_job_seam(client, f"async/{jid}"))
        except Exception:                           # noqa: BLE001
            errors.append({"id": jid, "error": "could not read the job's details"})
            continue
        if not name.startswith(JOB_PREFIX):
            continue                                # never listed, never touched
        ts = _parse_iso(created)
        age = (now - ts) if ts is not None else None
        row = {"id": jid, "name": name, "phase": phase.strip(), "created": created}
        listed.append(row)
        if not cleanup:
            continue
        finished = row["phase"] in _FINISHED
        if age is None:                             # no / unparseable creation time
            if finished:
                eligible.append(jid)
            else:
                kept.append({"id": jid, "reason": f"phase {row['phase'] or 'unknown'} with no creation time"})
        elif age > CLEANUP_AGE_S or (finished and age > FINISHED_MIN_AGE_S):
            eligible.append(jid)
        elif finished:
            kept.append({"id": jid, "reason": "finished less than 10 min ago (a live run may still read it)"})
        else:
            kept.append({"id": jid, "reason": f"phase {row['phase'] or 'unknown'}, younger than 2 h (a live run)"})
    if eligible:
        try:
            with _quiet():
                client.remove_jobs(list(eligible))  # one request
            deleted.extend(eligible)
        except Exception:                           # noqa: BLE001 — retry one by one to say which failed
            for jid in eligible:
                try:
                    with _quiet():
                        client.remove_jobs([jid])
                    deleted.append(jid)
                except Exception:                   # noqa: BLE001
                    errors.append({"id": jid, "error": "delete failed"})
    return {"cleanup": bool(cleanup), "listed": listed, "deleted": deleted, "kept": kept, "errors": errors}
