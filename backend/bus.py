"""Bus event opsional lewat NATS. Fail-open: broker mati tidak menghalangi apa pun.

Aktif hanya bila GALARDO_NATS_URL diisi. Tanpa itu -> no-op (polling tetap jalan).
"""
from __future__ import annotations

import os
import threading

PREFIX = "galardo.events."
_LOCK = threading.Lock()
_CLIENT = None
_URL = None
STATS = {"published": 0, "failed": 0, "skipped": 0, "last_error": None}


def enabled():
    return bool((os.environ.get("GALARDO_NATS_URL") or "").strip())


def subject(event_type):
    return PREFIX + (str(event_type).strip() if event_type else "unknown")


def reset():
    global _CLIENT, _URL
    with _LOCK:
        _CLIENT = None
        _URL = None


def _client():
    global _CLIENT, _URL
    url = (os.environ.get("GALARDO_NATS_URL") or "").strip()
    if not url:
        return None
    with _LOCK:
        if _CLIENT is not None and _URL == url:
            return _CLIENT
        try:
            import nats_client
            _CLIENT = nats_client.try_connect(url, name="galardo-bus")
            if _CLIENT is None:
                STATS["last_error"] = "try_connect mengembalikan None untuk " + url
        except Exception as exc:
            STATS["last_error"] = "%s: %s" % (type(exc).__name__, exc)
            _CLIENT = None
        _URL = url
        return _CLIENT


def publish(event_type, payload):
    """(ok, info). Tidak pernah melempar."""
    if not enabled():
        STATS["skipped"] += 1
        return False, "nats nonaktif"
    c = _client()
    if c is None:
        STATS["failed"] += 1
        if not STATS.get("last_error"):
            STATS["last_error"] = "klien nats tidak tersedia"
        return False, STATS["last_error"]
    try:
        c.publish(subject(event_type), payload)
        STATS["published"] += 1
        return True, subject(event_type)
    except Exception as exc:
        STATS["failed"] += 1
        STATS["last_error"] = "%s: %s" % (type(exc).__name__, exc)
        reset()
        return False, STATS["last_error"]


def stats():
    return dict(STATS)
