"""TEMPORARY — CDS-outage mirror mode (CDS_OUTAGE_FALLBACK_PLAN.md Part A; remove via CDS_RESTORE_PLAN.md).

CDS Strasbourg (SIMBAD / VizieR / X-Match) went down after a cybersecurity incident (~2026-10-28). While the
flag is on, every SIMBAD access goes to the CfA mirror (``simbad.harvard.edu``) and every VizieR access to the
IDIA mirror (``vizier.idia.ac.za``). With the flag OFF every function here is a no-op / returns the HEAD value,
so the app is byte-identical to its pre-outage behaviour.

The switch: the flag file ``~/.config/space_app/cds_mirror`` OR ``SPACE_APP_CDS_MIRROR=1``;
``SPACE_APP_CDS_MIRROR=0`` forces it off. Latched once per process (``enabled()``), so SIMBAD, VizieR and the
limits can never disagree inside one process. This is the ONLY module that names a mirror host.
"""

import os
import pathlib
import re
import threading
import time

SIMBAD_MIRROR = "simbad.harvard.edu"      # CfA — data to 2026-10-14 (the closest to WB's CDS baselines)
VIZIER_MIRROR = "vizier.idia.ac.za"       # IDIA — every VizieR catalog the app queries (ORB6 absent, as on CDS)
ENV = "SPACE_APP_CDS_MIRROR"
VIZIER_TIMEOUT_ENV = "SPACE_APP_VIZIER_TIMEOUT"   # honoured ONLY in mirror mode
VIZIER_TIMEOUT_S = 60.0                   # fixed: below IDIA's ~68.8 s empty-200 cut-off, so a cut-off stays loud
CUTOFF_ELAPSED_S = 60.0                   # MSG 380 amendment 3: 0 rows after >= this (per attempt) = the cut-off

# catalog_cache services that a mirror answer must never be written under (CDS-backed); reads are kept.
CACHE_SKIP_SERVICES = frozenset({
    "vizier", "cr26_tic", "simbad_otypes", "simbad_cr26_astrom", "simbad_cr26_cone", "simbad_cr26_parent",
    "simbad_cr24_velocity",
})

_LOCK = threading.Lock()
_STATE = {"enabled": None, "source": None, "announced": False, "xmatch_noted": False}


def _flag_path():
    """The flag file (a function, so tests can monkeypatch it)."""
    return pathlib.Path(os.path.expanduser("~/.config/space_app/cds_mirror"))


def _decide():
    env = os.environ.get(ENV)
    if env is not None and env.strip() == "0":
        return False, None
    try:
        if _flag_path().is_file():
            return True, "flag"
    except OSError:
        pass
    if env is not None and env.strip() == "1":
        return True, "env"
    return False, None


def enabled():
    """True iff mirror mode is on for this process (decided once, then latched)."""
    with _LOCK:
        if _STATE["enabled"] is None:
            _STATE["enabled"], _STATE["source"] = _decide()
        return _STATE["enabled"]


def _reset_for_tests():
    """Drop the latch (tests only)."""
    with _LOCK:
        _STATE.update(enabled=None, source=None, announced=False, xmatch_noted=False)


def _mode_line():
    head = f"SIMBAD→{SIMBAD_MIRROR} VizieR→{VIZIER_MIRROR} — temporary, "
    if _STATE["source"] == "flag":
        try:
            mtime = _flag_path().stat().st_mtime
            days = max(0, int((time.time() - mtime) // 86400))
            return head + f"on since {time.strftime('%Y-%m-%d', time.localtime(mtime))} ({days}d)"
        except OSError:
            pass
    return head + f"on via {ENV}"


def announce():
    """Write the one ``[cds-mirror]`` mode line (once per process; thread-safe). No-op when off."""
    if not enabled():
        return
    with _LOCK:
        if _STATE["announced"]:
            return
        _STATE["announced"] = True
        line = _mode_line()
    from core.shared import _stderr_warn
    _stderr_warn("cds-mirror", line)


def apply_simbad():
    """Point astroquery SIMBAD (``conf.server`` for new instances + the import-time module instance) at the
    mirror. Idempotent; a no-op when off. The raw-TAP seams read ``conf.server`` at call time."""
    if not enabled():
        return
    announce()
    from astroquery.simbad import conf
    import astroquery.simbad as _sm
    if conf.server != SIMBAD_MIRROR:
        conf.server = SIMBAD_MIRROR
    if getattr(_sm.Simbad, "server", None) != SIMBAD_MIRROR:
        _sm.Simbad.server = SIMBAD_MIRROR


def vizier_server_kwargs():
    """``{"vizier_server": mirror}`` in mirror mode (announcing), else ``{}`` (splat-safe)."""
    if not enabled():
        return {}
    announce()
    return {"vizier_server": VIZIER_MIRROR}


def vizier_timeout(builtin):
    """The VizieR per-request bound: ``builtin`` when off; in mirror mode the fixed 60 s (or a positive
    ``SPACE_APP_VIZIER_TIMEOUT``)."""
    if not enabled():
        return builtin
    from core.shared import _env_timeout
    return _env_timeout(VIZIER_TIMEOUT_ENV, VIZIER_TIMEOUT_S) or VIZIER_TIMEOUT_S


def skip_cache_write(service):
    """True iff a fresh result for ``service`` must NOT be written to the catalog cache (mirror mode only)."""
    return service in CACHE_SKIP_SERVICES and enabled()


# 2MASS designations truncate (never round) their J2000 coordinates: J hhmmss.ss ±ddmmss.s → "hhmmsscc±ddmmssd".
_TWOMASS_KEY_RE = re.compile(r"^(\d\d)(\d\d)(\d\d)(\d\d)([+-])(\d\d)(\d\d)(\d\d)(\d)$")


def decode_2mass_key(key):
    """A 2MASS key (``18365633+3847012``, optionally ``J``-prefixed) → its truncated J2000 ``(ra_deg, dec_deg)``,
    or ``None`` if it does not match the pinned pattern. The sign comes from the character (``-00…`` is
    southern)."""
    k = str(key or "").strip()
    if k[:1] in ("J", "j"):
        k = k[1:]
    m = _TWOMASS_KEY_RE.match(k)
    if not m:
        return None
    hh, mm, ss, cs, sgn, dd, am, asec, ds = m.groups()
    ra = (int(hh) + int(mm) / 60.0 + (int(ss) + int(cs) / 100.0) / 3600.0) * 15.0
    dec = int(dd) + int(am) / 60.0 + (int(asec) + int(ds) / 10.0) / 3600.0
    return ra, (-dec if sgn == "-" else dec)


def window_title_suffix():
    """The GUI title suffix while mirror mode is on."""
    return " — CDS MIRROR MODE" if enabled() else ""


def xmatch_unavailable_note():
    """The census X-Match event line (mirror mode only), always after the mode line."""
    if not enabled():
        return
    announce()
    with _LOCK:
        if _STATE.get("xmatch_noted"):
            return
        _STATE["xmatch_noted"] = True
    from core.shared import _stderr_warn
    _stderr_warn("cds-mirror", "X-Match has no mirror — census SB9 rows dropped; this census output is not valid")
