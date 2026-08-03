# tests/_netcheck.py — shared helper: is the Hypatia API reachable?
import os
import socket


def live_enabled() -> bool:
    """Opt-in gate for the live-network test suite (mirrors ``_dustcheck.heavy_dust_enabled``).

    Every ``*_live.py`` file plus the NASA/JPL query-subprocess tests hit real external
    services (SIMBAD / CDS / VizieR / GAVO / ESA Gaia / HEASARC / Hypatia / GitHub-OEC /
    NASA Exoplanet Archive / JPL Horizons). On a reachable network they add several minutes
    to a run, so a routine ``pytest -q`` must **not** fire them — they run only when
    ``SPACE_APP_RUN_LIVE=1`` is set **and** the host is reachable; otherwise they skip
    cleanly (the reachability probe is short-circuited, so no socket is even opened).
    Set it explicitly to exercise the live paths, e.g.::

        SPACE_APP_RUN_LIVE=1 venv/bin/python -m pytest tests/test_catalog_live.py

    Kept beside the reachability probes (not in ``_dustcheck``) because it gates the same
    ``skipUnless`` sites they feed; the ``query.py`` reachability gates that reuse
    ``reachable()`` are unaffected (they never consult this).
    """
    return os.environ.get("SPACE_APP_RUN_LIVE") == "1"


def hypatia_reachable(host="hypatiacatalog.com", port=443, timeout=3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def gavo_reachable(host="dc.g-vo.org", port=443, timeout=3.0) -> bool:
    """Is the GAVO Data Center (GCNS TAP service) reachable?"""
    return reachable(host, port, timeout)


def reachable(host, port=443, timeout=3.0) -> bool:
    """Generic TCP-reachability probe (shared by the query.py reachability gates)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def simbad_reachable(timeout=3.0) -> bool:
    """Is SIMBAD reachable? Gate for the Phase AN designation live tests."""
    return reachable("simbad.u-strasbg.fr", 443, timeout)


def cds_reachable(timeout=3.0) -> bool:
    """Is CDS (VizieR + X-Match) reachable? Gate for the Phase AM catalog live tests."""
    return reachable("vizier.cds.unistra.fr", 443, timeout)


def esa_gaia_reachable(timeout=3.0) -> bool:
    """Is the ESA Gaia TAP archive reachable? Gate for the Phase AM Gaia live tests."""
    return reachable("gea.esac.esa.int", 443, timeout)
