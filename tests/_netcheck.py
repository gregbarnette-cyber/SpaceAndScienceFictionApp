# tests/_netcheck.py — shared helper: is the Hypatia API reachable?
import socket


def hypatia_reachable(host="hypatiacatalog.com", port=443, timeout=3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
