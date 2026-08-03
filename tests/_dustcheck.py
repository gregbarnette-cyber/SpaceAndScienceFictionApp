# tests/_dustcheck.py — gate for the Phase T2 dust tests (mirrors _netcheck.py).
#
# The dust path needs the optional 'dust' extra (dustmaps + healpy), which has no
# native-Windows pip wheel, so dust tests are skipped on a checkout without it —
# exactly like the *_live.py network tests skip when the service is unreachable.

import os


def dustmaps_importable() -> bool:
    """True iff the optional dust extra (dustmaps + healpy) is importable."""
    try:
        import dustmaps  # noqa: F401
        import healpy     # noqa: F401
        return True
    except Exception:
        return False


def maps_fetched() -> bool:
    """True iff the Leike map data has been fetched into the dust cache (the
    real-data anchor tests need it; CLI option 59 downloads it)."""
    try:
        import core.dust as dust
        return dust._map_path("leike2020").is_file()
    except Exception:
        return False


def heavy_dust_enabled() -> bool:
    """True only when a test may LOAD a real multi-GB dust map. Opt-in via
    SPACE_APP_RUN_HEAVY_DUST=1, on top of the extra + fetched maps.

    Loading the full Leike/Edenhofer 3D cube mid-sweep OOM-crashed the 8 GB WSL box
    (2026-08-02), so map-loading tests are kept OUT of a routine `pytest -q` — the dust
    LOGIC is covered offline by mocked tests (test_dust_routing.py / DustEngineMathTest /
    test_strategic_geography.py::DustWeightTest). Run the real-map anchors on demand:
    `SPACE_APP_RUN_HEAVY_DUST=1 venv/bin/python -m pytest tests/test_dust_query.py`."""
    return (dustmaps_importable() and maps_fetched()
            and os.environ.get("SPACE_APP_RUN_HEAVY_DUST") == "1")
