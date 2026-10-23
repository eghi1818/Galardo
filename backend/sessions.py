"""GALARDO - sesi login: id sesi acak, terpisah dari token pengguna."""
import json
import os
import secrets
import threading
import time

TTL = int(os.environ.get("GALARDO_SESSION_TTL", "604800") or 604800)
_LOCK = threading.Lock()


def _path():
    base = os.environ.get("GALARDO_DATA_DIR")
    if not base:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "sessions.json")


def _load():
    try:
        with open(_path()) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    p = _path()
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def gc(d=None):
    now = int(time.time())
    d = _load() if d is None else d
    return dict((k, v) for k, v in d.items() if int(v.get("exp", 0)) > now)


def create(uid, ttl=None):
    sid = secrets.token_hex(24)
    with _LOCK:
        d = gc()
        d[sid] = {"uid": uid, "exp": int(time.time()) + int(ttl or TTL)}
        _save(d)
    return sid


def get(sid):
    if not sid:
        return None
    with _LOCK:
        d = _load()
        rec = d.get(sid)
        if not rec:
            return None
        if int(rec.get("exp", 0)) <= int(time.time()):
            del d[sid]
            _save(d)
            return None
        return rec.get("uid")


def drop(sid):
    with _LOCK:
        d = _load()
        if sid in d:
            del d[sid]
            _save(d)


def drop_uid(uid):
    with _LOCK:
        d = _load()
        for k in [k for k, v in d.items() if v.get("uid") == uid]:
            del d[k]
        _save(d)


def list_sessions():
    return gc()
