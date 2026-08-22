"""core/catalog_cache.py — generic hash+TTL file cache for the Phase AM catalog-access tier.

The catalog subcommands (`vizier-query`, `gaia-tap`, `binary-orbit`, `close-binary-census`,
`gaia-astrophysical`, …) make LIVE network queries to CDS VizieR / ESA Gaia. Published-catalog
rows are effectively static, so a census re-run should not re-hit the archive. This module is a
small, dependency-free JSON-on-disk cache keyed by a stable hash of (service + query params),
with a per-read TTL.

Design rules (spec §5):
  - **Never cache errors or empties.** `cache_put` skips a falsy value, a dict carrying an
    "error" key, or an object with no rows — so a transient failure retries fresh next call
    (the `fetch_body_properties` lesson).
  - **Miss-graceful.** Any read/parse problem is a cache miss (returns None), never an exception.
  - **Offline / test friendly.** The cache dir lives under the gitignored `data/` tree; tests
    point `_CACHE_DIR` at a tmp path. Set `SPACE_APP_CATALOG_CACHE=0` to disable entirely.
"""

import hashlib
import json
import os
import pathlib
import time

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Gitignored (data/ is already in .gitignore), native filesystem — same model as data/dust,
# data/oec. Read as a module global inside the functions so tests can monkeypatch it.
_CACHE_DIR = _REPO_ROOT / "data" / "catalog_cache"

DEFAULT_TTL_S = 7 * 86400.0   # 7 days — published catalog rows are effectively static.


def _enabled() -> bool:
    """Cache is on unless SPACE_APP_CATALOG_CACHE is explicitly '0'/'false'/'no'."""
    return os.environ.get("SPACE_APP_CATALOG_CACHE", "1").lower() not in ("0", "false", "no")


def cache_key(service: str, params) -> str:
    """Stable SHA-256 hex key over (service, params). `params` is any JSON-able structure;
    dict key order is normalized so equivalent queries collide intentionally."""
    blob = json.dumps({"service": service, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _key_path(key: str) -> pathlib.Path:
    return _CACHE_DIR / f"{key}.json"


def _is_empty(obj) -> bool:
    """True if obj carries no payload worth caching (None, empty list/dict/str, or an
    'error' dict, or a rows-bearing dict whose rows are empty)."""
    if obj is None:
        return True
    if isinstance(obj, dict):
        if "error" in obj:
            return True
        rows = obj.get("rows")
        if rows is not None and len(rows) == 0:
            return True
        return len(obj) == 0
    try:
        return len(obj) == 0
    except TypeError:
        return False


def cache_get(key: str, ttl_s: float = DEFAULT_TTL_S):
    """Return the cached object for `key` if present and younger than `ttl_s`, else None.
    Any error (missing file, unreadable, bad JSON, disabled cache) is a miss."""
    if not _enabled():
        return None
    try:
        path = _key_path(key)
        if not path.is_file():
            return None
        if (time.time() - path.stat().st_mtime) >= ttl_s:
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def cache_put(key: str, obj) -> None:
    """Persist `obj` under `key` — unless it is empty or an error (never cache those).
    Best-effort: a write failure is swallowed (the value is still returned to the caller)."""
    if not _enabled() or _is_empty(obj):
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _key_path(key).with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(obj, fh, default=str)
        tmp.replace(_key_path(key))
    except Exception:
        return


def cached(service: str, params, producer, ttl_s: float = DEFAULT_TTL_S):
    """Convenience: return the cached result for (service, params) or call `producer()`,
    cache its (non-empty, non-error) result, and return it. `producer` is a zero-arg callable.
    The ergonomic entry the gateways use so caching is one wrapper, not three calls."""
    key = cache_key(service, params)
    hit = cache_get(key, ttl_s)
    if hit is not None:
        return hit
    result = producer()
    cache_put(key, result)
    return result


def clear_cache() -> int:
    """Delete all cached files; return the count removed. (Test/maintenance helper.)"""
    n = 0
    try:
        for p in _CACHE_DIR.glob("*.json"):
            p.unlink()
            n += 1
    except Exception:
        pass
    return n


def _astroquery_cache_dir():
    """The astroquery HTTP-cache root (`<astropy cache>/astroquery/`), or None if unavailable."""
    try:
        from astropy.config import get_cache_dir
        return pathlib.Path(get_cache_dir()) / "astroquery"
    except Exception:
        return None


def clear_all() -> dict:
    """Wipe BOTH cache layers: this app cache (`data/catalog_cache/`) AND **astroquery's own HTTP
    cache** (`~/.astropy/cache/astroquery/`). astroquery's cache is normally disabled by the
    `cache=False` calls in `core.catalog`, but a *residual* dir can persist from an earlier run (or
    another astroquery caller) and serve stale throttle-induced empties for ~7 days — this is the
    "dump the cache before working/testing" affordance. Returns
    `{app_cache_files_removed, astroquery_cache_dir, astroquery_cache_removed}`.
    """
    import shutil
    app_removed = clear_cache()
    aq_dir = _astroquery_cache_dir()
    aq_removed = False
    if aq_dir is not None and aq_dir.is_dir():
        shutil.rmtree(aq_dir, ignore_errors=True)
        aq_removed = not aq_dir.exists()
    return {"app_cache_files_removed": app_removed,
            "astroquery_cache_dir": (str(aq_dir) if aq_dir is not None else None),
            "astroquery_cache_removed": aq_removed}
