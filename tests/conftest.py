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
    """The offline ``test_cr26_*`` / ``test_cr27_*`` files (not ``*_live``) must never open a socket."""
    import os
    import socket
    name = os.path.basename(str(request.node.fspath))
    if name.startswith(("test_cr26_", "test_cr27_")) and "live" not in name:     # CR-27 plan §4.8 (CP0 F-C M2)
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


# ── CR-24: the per-star V_ISM's velocity lookup (plan §3.3) ─────────────────────────────────────────────────────
# For every test NOT marked ``@pytest.mark.cr24_velocity``: an in-process ``--star`` run's velocity lookup is
# "not run" (``target_velocity`` / ``lookup_velocity`` return no velocity → V_ISM by the precedence without a derive:
# the measured row, else 26 assumed) — so the pre-CR-24 offline ``--star`` tests keep their stubbed identities and
# never reach SIMBAD; and the two CR-24 network seams are leak stubs (a test that bypasses the defaults fails loud).
# A ``cr24_velocity`` test keeps the real resolution logic and mocks the seams itself.
_CR24_SEAMS = (("core.ism_velocity", "_velocity_seam"), ("core.ism_velocity", "_identity_seam"))


@pytest.fixture(autouse=True)
def _cr24_velocity_isolation(request, monkeypatch):
    import importlib
    iv = importlib.import_module("core.ism_velocity")
    marked = bool(request.node.get_closest_marker("cr24_velocity"))
    leaks = []
    for mod_name, attr in _CR24_SEAMS:
        mod = importlib.import_module(mod_name)

        def _stub(*a, _n=f"{mod_name}.{attr}", **k):
            leaks.append(_n)
            raise AssertionError(f"CR-24 network seam called in an offline test: {_n}")
        monkeypatch.setattr(mod, attr, _stub)
    if not marked:
        monkeypatch.setattr(iv, "target_velocity", lambda main_id, reuse=None: (None, "own", None))
        monkeypatch.setattr(iv, "lookup_velocity", lambda main_id, primary=None: None)
    yield
    if leaks:
        pytest.fail(f"CR-24 network seam(s) reached in an offline test: {sorted(set(leaks))}")


# ── CR-27.4: the --star identity step (plan §4.6) ───────────────────────────────────────────────────────────────────
# For every test NOT marked ``@pytest.mark.cr27_identity``: ``exclusion_system.resolve_star_identity`` keeps the head's
# own identity and makes no lookup (``own``-equivalent) — so the pre-CR-27 offline ``--star`` tests keep their stubbed
# identities and never reach the CR-24 / CR-26 identity seams (which stay leak stubs). A ``cr27_identity`` test drives
# the real step and stubs ``ism_velocity.resolve_a_record`` (or the seams) itself.
@pytest.fixture(autouse=True)
def _cr27_identity_isolation(request, monkeypatch):
    if request.node.get_closest_marker("cr27_identity"):
        yield
        return
    import importlib
    es = importlib.import_module("core.exclusion_system")
    monkeypatch.setattr(es, "resolve_star_identity", lambda sl, *a, **k: (sl, None, None, None))
    yield
