# tests/_queryharness.py — shared query.py test harness (IMPROVEMENT_PLAN Phase 3).
#
# Not a test module: pytest only collects `test_*.py`, and the underscore prefix keeps
# stdlib unittest discovery off it too. Consolidates the ~24 duplicate
# module-level `_run` helpers that each spawned `query.py` as a subprocess. Two key
# wins baked in over the ad-hoc copies:
#   1. a `timeout=` on every spawn (the copies had none — a hung query.py would hang
#      the whole suite), and
#   2. `tempfile.gettempdir()` for throwaway DBs instead of hardcoded Linux-only
#      `/tmp/...` paths (cross-OS).
#
# It also offers an in-process dispatcher (`run_query_inproc`) that skips the ~0.1 s
# Python-import cost per spawn — used by the self-validating exit-code matrices, which
# never touch the DB. Real-subprocess happy-path/parity tests keep using `run_query`.
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = 60  # seconds — no query.py call should take this long offline.


def make_env(db_name=None, db_path=None, **extra):
    """Build a minimal env dict pointing SPACE_APP_DB at a throwaway DB.

    `db_name` -> a basename under tempfile.gettempdir(); `db_path` -> used verbatim.
    With neither, a per-pid throwaway name is used so a stray seed never touches
    data/space_app.db.
    """
    env = {"PATH": os.environ.get("PATH", "")}
    if db_path is None:
        if db_name is None:
            db_name = f"query_throwaway_{os.getpid()}.db"
        db_path = os.path.join(tempfile.gettempdir(), db_name)
    env["SPACE_APP_DB"] = str(db_path)
    env.update(extra)
    return env


def run_query(*args, env=None, db_path=None, db_name=None, timeout=DEFAULT_TIMEOUT):
    """Spawn `query.py` as a subprocess; return (returncode, parsed_json_or_None, stderr)."""
    if env is None:
        env = make_env(db_name=db_name, db_path=db_path)
    proc = subprocess.run(
        [sys.executable, str(REPO / "query.py"), *map(str, args)],
        capture_output=True, text=True, cwd=str(REPO), env=env, timeout=timeout,
    )
    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = None
    return proc.returncode, payload, proc.stderr


def run_query_inproc(*args):
    """Dispatch query.py's argparse in-process; return (exit_code, payload, stderr_text).

    Caches the `query` import after the first call — the whole point (no per-call
    interpreter startup). Shares the parent's SPACE_APP_DB / core.db._DB_PATH state,
    so ONLY use this for matrices that never touch the DB (the pure-math validation
    and argparse exit-code cases). DB-seeded / parity tests must use run_query.
    """
    import query  # cached after first import
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            query.main(list(map(str, args)))
        except SystemExit as e:
            code = int(e.code or 0)
    try:
        payload = json.loads(out.getvalue())
    except (json.JSONDecodeError, ValueError):
        payload = None
    return code, payload, err.getvalue()


def save_cr30_cache():
    """CR-30: snapshot and clear the md5-verified reference-table cache (``core.ms_reference_tables``) so a test
    pointing ``SPACE_APP_CR30_DATA_DIR`` elsewhere re-reads the files; pair with ``restore_cr30_cache``. (The
    pre-CR-30 main-sequence DB caches are gone — the region lookup reads S1, never a DB table.)"""
    import core.ms_reference_tables as mrt
    saved = dict(mrt._CACHE)
    mrt._CACHE.clear()
    return saved


def restore_cr30_cache(saved):
    import core.ms_reference_tables as mrt
    mrt._CACHE.clear()
    mrt._CACHE.update(saved)


# Pre-CR-30 names, kept for the existing callers (the old caches no longer exist).
save_main_sequence_cache = save_cr30_cache
restore_main_sequence_cache = restore_cr30_cache
