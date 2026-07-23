"""tests/test_catalog_cache.py — offline coverage for the Phase AM catalog cache
(core/catalog_cache.py). Pure filesystem — no network. Always runs.

Locks the spec §5 caching rules: stable hashing, TTL expiry, never-cache-errors/empties,
miss-graceful reads, the cached() producer wrapper, and the env-disable switch. The cache dir
is redirected to a per-test tmp path so the real data/catalog_cache tree is never touched.
"""

import os
import pathlib
import tempfile
import unittest

from core import catalog_cache


class CatalogCacheTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = catalog_cache._CACHE_DIR
        catalog_cache._CACHE_DIR = pathlib.Path(self._tmp.name) / "catalog_cache"
        self._orig_env = os.environ.get("SPACE_APP_CATALOG_CACHE")
        os.environ.pop("SPACE_APP_CATALOG_CACHE", None)

    def tearDown(self):
        catalog_cache._CACHE_DIR = self._orig_dir
        if self._orig_env is None:
            os.environ.pop("SPACE_APP_CATALOG_CACHE", None)
        else:
            os.environ["SPACE_APP_CATALOG_CACHE"] = self._orig_env
        self._tmp.cleanup()

    def test_key_is_stable_and_order_independent(self):
        k1 = catalog_cache.cache_key("vizier", {"catalog": "B/sb9", "row_limit": 10})
        k2 = catalog_cache.cache_key("vizier", {"row_limit": 10, "catalog": "B/sb9"})
        self.assertEqual(k1, k2)
        k3 = catalog_cache.cache_key("vizier", {"catalog": "B/wds", "row_limit": 10})
        self.assertNotEqual(k1, k3)
        k4 = catalog_cache.cache_key("gaia", {"catalog": "B/sb9", "row_limit": 10})
        self.assertNotEqual(k1, k4)   # service is part of the key

    def test_put_then_get_roundtrip(self):
        key = catalog_cache.cache_key("vizier", {"catalog": "B/sb9"})
        obj = {"rows": [{"period_d": 10.02}], "count": 1}
        catalog_cache.cache_put(key, obj)
        self.assertEqual(catalog_cache.cache_get(key), obj)

    def test_ttl_expiry(self):
        key = catalog_cache.cache_key("vizier", {"x": 1})
        catalog_cache.cache_put(key, {"rows": [1]})
        self.assertIsNotNone(catalog_cache.cache_get(key, ttl_s=3600))
        self.assertIsNone(catalog_cache.cache_get(key, ttl_s=0.0))   # age >= 0 → expired

    def test_missing_key_is_miss(self):
        self.assertIsNone(catalog_cache.cache_get("deadbeef" * 8))

    def test_errors_and_empties_not_cached(self):
        for bad in ({"error": "boom"}, {"rows": []}, [], {}, None, ""):
            key = catalog_cache.cache_key("s", {"v": repr(bad)})
            catalog_cache.cache_put(key, bad)
            self.assertIsNone(catalog_cache.cache_get(key),
                              f"{bad!r} should not have been cached")

    def test_cached_wrapper_calls_producer_once(self):
        calls = {"n": 0}

        def producer():
            calls["n"] += 1
            return {"rows": [{"v": calls["n"]}]}

        first = catalog_cache.cached("vizier", {"catalog": "B/sb9"}, producer)
        second = catalog_cache.cached("vizier", {"catalog": "B/sb9"}, producer)
        self.assertEqual(first, second)
        self.assertEqual(calls["n"], 1)   # second call served from cache

    def test_cached_wrapper_does_not_cache_error(self):
        calls = {"n": 0}

        def producer():
            calls["n"] += 1
            return {"error": "network down"}

        catalog_cache.cached("vizier", {"catalog": "B/sb9"}, producer)
        catalog_cache.cached("vizier", {"catalog": "B/sb9"}, producer)
        self.assertEqual(calls["n"], 2)   # error not cached → producer re-run

    def test_disable_via_env(self):
        os.environ["SPACE_APP_CATALOG_CACHE"] = "0"
        key = catalog_cache.cache_key("vizier", {"catalog": "B/sb9"})
        catalog_cache.cache_put(key, {"rows": [1]})
        self.assertIsNone(catalog_cache.cache_get(key))

    def test_clear_cache(self):
        for i in range(3):
            catalog_cache.cache_put(catalog_cache.cache_key("s", {"i": i}), {"rows": [i]})
        removed = catalog_cache.clear_cache()
        self.assertEqual(removed, 3)


if __name__ == "__main__":
    unittest.main()
