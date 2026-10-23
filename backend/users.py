"""GALARDO - penyimpanan pengguna: nama, peran, sandi PBKDF2, token per pengguna."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

ROLES = ("VIEWER", "OPERATOR", "ADMIN", "SUPERADMIN")
RANK = {"VIEWER": 1, "OPERATOR": 2, "ADMIN": 3, "SUPERADMIN": 4}
ITER = 200000
_LOCK = threading.Lock()


def _path():
    base = os.environ.get("GALARDO_DATA_DIR")
    if not base:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "users.json")


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


def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), salt.encode(), ITER).hex()
    return "%s$%d$%s" % (salt, ITER, h)


def verify_password(pw, stored):
    try:
        salt, it, h = (stored or "").split("$")
        calc = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), salt.encode(), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except Exception:
        return False


def _slug(s):
    out = "".join(c if c.isalnum() or c in "-_" else "-" for c in (s or "").lower()).strip("-")
    return out or "user"


def allows(role, need):
    return RANK.get(role or "", 0) >= RANK.get(need or "VIEWER", 1)


def create(name, username, role="VIEWER", password=None):
    if role not in ROLES:
        raise ValueError("peran tidak dikenal: %s" % role)
    with _LOCK:
        d = _load()
        uname = (username or _slug(name)).lower()
        if any(u.get("username") == uname for u in d.values()):
            raise ValueError("username sudah dipakai: %s" % uname)
        uid, n = "usr-" + _slug(uname), 1
        while uid in d:
            n += 1
            uid = "usr-%s-%d" % (_slug(uname), n)
        rec = {"id": uid, "name": name or uname, "username": uname, "role": role,
               "active": True, "created_at": int(time.time()),
               "password": hash_password(password) if password else "",
               "token": secrets.token_hex(16)}
        d[uid] = rec
        _save(d)
        return dict(rec)


def get(uid):
    return _load().get(uid)


def list_users():
    d = _load()
    out = []
    for u in sorted(d.values(), key=lambda x: x.get("username") or ""):
        out.append({"id": u.get("id"), "name": u.get("name"), "username": u.get("username"),
                    "role": u.get("role"), "active": u.get("active", True),
                    "created_at": u.get("created_at"), "token": u.get("token"),
                    "punya_sandi": bool(u.get("password"))})
    return out


def by_username(username):
    u = (username or "").lower()
    for rec in _load().values():
        if rec.get("username") == u:
            return rec
    return None


def by_token(tok):
    if not tok:
        return None
    for rec in _load().values():
        if rec.get("token") and hmac.compare_digest(rec["token"], tok):
            return rec
    return None


def role_of(uid):
    rec = get(uid)
    return rec.get("role") if rec else None


def _mut(uid, fn):
    with _LOCK:
        d = _load()
        rec = d.get(uid)
        if not rec:
            return None
        fn(rec)
        d[uid] = rec
        _save(d)
        return dict(rec)


def set_role(uid, role):
    if role not in ROLES:
        raise ValueError("peran tidak dikenal: %s" % role)
    return _mut(uid, lambda r: r.__setitem__("role", role))


def set_password(uid, pw):
    return _mut(uid, lambda r: r.__setitem__("password", hash_password(pw)))


def rotate_token(uid):
    return _mut(uid, lambda r: r.__setitem__("token", secrets.token_hex(16)))


def set_active(uid, aktif):
    return _mut(uid, lambda r: r.__setitem__("active", bool(aktif)))


def delete(uid):
    with _LOCK:
        d = _load()
        if uid not in d:
            return False
        del d[uid]
        _save(d)
        return True
