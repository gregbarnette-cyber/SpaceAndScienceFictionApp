# tests/_oeccheck.py — gate for OEC tests that need the real downloaded cache
# (mirrors _dustcheck.py / _netcheck.py).
#
# The fixture half of every OEC view test always runs; assertions that walk the
# real catalogue (~4,000 systems) need `data/oec/systems.xml.gz`, which a fresh
# checkout does not have. Those skip cleanly rather than failing.


def oec_cache_present() -> bool:
    """True iff the downloaded OEC cache file exists locally."""
    try:
        import os
        import core.databases as databases
        return os.path.exists(databases._OEC_CACHE_FILE)
    except Exception:
        return False


def qt_available() -> bool:
    """True iff PySide6 + matplotlib are importable (the GUI view tests)."""
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False
