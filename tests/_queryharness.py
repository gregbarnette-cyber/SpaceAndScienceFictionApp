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


def save_main_sequence_cache():
    """Snapshot BOTH module-level main-sequence caches (core.regions AND core.shared,
    each populated independently by their own _lookup_spectral_type) and clear them,
    forcing a reload from the current _DB_PATH. Pair with restore_main_sequence_cache
    in setUp/tearDown so an in-process test seeding its own main_sequence_stars can't
    poison the caches for a later test (IMPROVEMENT_PLAN P3.3)."""
    import core.regions as regions
    import core.shared as shared
    saved = (regions._MAIN_SEQUENCE_DATA, shared._MAIN_SEQUENCE_DATA)
    regions._MAIN_SEQUENCE_DATA = None
    shared._MAIN_SEQUENCE_DATA = None
    return saved


def restore_main_sequence_cache(saved):
    import core.regions as regions
    import core.shared as shared
    regions._MAIN_SEQUENCE_DATA, shared._MAIN_SEQUENCE_DATA = saved
