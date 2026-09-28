"""Suite-wide isolation for the CR-26 wind model's network layer (plan §7 "Isolation").

An autouse fixture, for every test NOT marked ``@pytest.mark.cr26_network``:

1. wraps ``core.xray_catalog.resolve_star_wind_inputs`` so ``allow_network`` is **forced** False (a lambda,
   not ``functools.partial`` — an explicit ``allow_network=True`` must not override it). Callers always go
   through the module attribute, so an in-process ``--star`` test never reaches a CR-26 catalog;
2. replaces every CR-26 network seam with a stub that records the call in a leak list and raises. The
   teardown fails the test if the list is non-empty — a raised exception alone would be swallowed by the
   families' degrade handlers (``except Exception`` / the watchdog), so the list is what makes a leak loud.

Subprocess tests are unaffected by in-process patches; no offline subprocess test uses ``--star``, and the
``--component`` / ``--spectral-type`` paths never call a fetcher.
"""
import pytest

_SEAMS = (
    ("core.databases", "_simbad_cr26_tap"),
    ("core.xray_catalog", "_heasarc_tap"),
    ("core.xray_catalog", "_tic_query"),
    ("core.xray_catalog", "_identity_lookup"),
    ("core.xray_catalog", "_gaia_astrom_seam"),
    ("core.xray_catalog", "_gaia_radius_seam"),
    ("core.xray_catalog", "_partner_mass_seam"),
)


_ISO_DIR = []


def _iso_cache_dir(factory):
    """ONE session-scoped empty cache dir for every unmarked test (pytest cleans it up)."""
    if not _ISO_DIR:
        _ISO_DIR.append(factory.mktemp("cr26_iso_cache"))
    return _ISO_DIR[0]


@pytest.fixture(autouse=True)
def _cr26_socket_guard(request, monkeypatch):
    """The offline ``test_cr26_*`` files (not ``test_cr26_live``) must never open a socket."""
    import os
    import socket
    name = os.path.basename(str(request.node.fspath))
    if name.startswith("test_cr26_") and "live" not in name:
        def _no_socket(self, *a, **k):
            raise AssertionError(f"socket opened in an offline CR-26 test: {request.node.nodeid}")
        monkeypatch.setattr(socket.socket, "connect", _no_socket)
        monkeypatch.setattr(socket.socket, "connect_ex", _no_socket)
    yield


@pytest.fixture(autouse=True)
def _cr26_network_isolation(request, monkeypatch, tmp_path_factory):
    if request.node.get_closest_marker("cr26_network"):
        yield
        return
    import importlib
    leaks = []
    for mod_name, attr in _SEAMS:
        mod = importlib.import_module(mod_name)

        def _stub(*a, _n=f"{mod_name}.{attr}", **k):
            leaks.append(_n)
            raise AssertionError(f"CR-26 network seam called in an offline test: {_n}")
        monkeypatch.setattr(mod, attr, _stub)
    # a warm live catalog cache must not answer for a stubbed seam (the cache is consulted before the seam)
    cc = importlib.import_module("core.catalog_cache")
    monkeypatch.setattr(cc, "_CACHE_DIR", _iso_cache_dir(tmp_path_factory))
    xc = importlib.import_module("core.xray_catalog")
    orig = xc.resolve_star_wind_inputs
    monkeypatch.setattr(xc, "resolve_star_wind_inputs",
                        lambda *a, **k: orig(*a, **{**k, "allow_network": False}))
    yield
    if leaks:
        pytest.fail(f"CR-26 network seam(s) reached in an offline test: {sorted(set(leaks))}")
