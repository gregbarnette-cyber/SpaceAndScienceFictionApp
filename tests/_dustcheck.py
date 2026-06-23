# tests/_dustcheck.py — gate for the Phase T2 dust tests (mirrors _netcheck.py).
#
# The dust path needs the optional 'dust' extra (dustmaps + healpy), which has no
# native-Windows pip wheel, so dust tests are skipped on a checkout without it —
# exactly like the *_live.py network tests skip when the service is unreachable.


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
