# tests/_netcheck.py — shared helper: is the Hypatia API reachable?
import socket


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
