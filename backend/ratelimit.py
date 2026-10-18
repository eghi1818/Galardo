"""GALARDO - rate limit sederhana (token bucket per klien). Fail-open.

Aktif hanya bila GALARDO_RATE_LIMIT diisi. Format: "60/m", "120/60s", "10/2s",
"300/h", atau "0"/"off" (mati). Kunci = token Authorization bila ada, kalau tidak IP.
Rute health + file statis dikecualikan. Melebihi batas -> 429 + Retry-After.
"""
import os
import threading
import time

ENV = "GALARDO_RATE_LIMIT"
LOCK = threading.RLock()
_EMBER = {}
_HIT = {"lolos": 0, "batas": 0}


def spec():
    return (os.environ.get(ENV) or "").strip()


def parse(s):
    """'60/m' -> (60, 60.0). None bila mati / tidak valid."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ("0", "off", "mati"):
        return None
    if "/" not in s:
        try:
            n = float(s)
        except ValueError:
            return None
        return (n, 60.0) if n > 0 else None
    a, _, b = s.partition("/")
    try:
        n = float(a)
    except ValueError:
        return None
    b = b.strip()
    if b in ("m", "min", "menit"):
        per = 60.0
    elif b in ("h", "jam"):
        per = 3600.0
    elif b in ("s", "sec", "detik"):
        per = 1.0
    else:
        try:
            per = float(b.rstrip("s"))
        except ValueError:
            return None
    if n <= 0 or per <= 0:
        return None
    return (n, per)


def kunci(handler):
    try:
        auth = handler.headers.get("Authorization") or ""
    except Exception:
        auth = ""
    if auth:
        tok = auth.split(None, 1)[1] if " " in auth else auth   # buang skema (Bearer/dll)
        return "tok:" + tok[-24:]
    try:
        return "ip:" + (handler.client_address[0] if handler.client_address else "?")
    except Exception:
        return "ip:?"


def _ambil(key, n, per):
    """Kembalikan None bila boleh lewat, atau detik tunggu bila kena batas."""
    now = time.time()
    with LOCK:
        tokens, last = _EMBER.get(key, (n, now))
        tokens = min(n, tokens + (now - last) * (n / per))
        if tokens >= 1.0:
            _EMBER[key] = (tokens - 1.0, now)
            _HIT["lolos"] += 1
            return None
        _EMBER[key] = (tokens, now)
        _HIT["batas"] += 1
        return max(1, int(round((1.0 - tokens) * per / n)))


def cek(handler, path=None):
    """None = boleh lewat. Angka = detik tunggu (429)."""
    aturan = parse(spec())
    if not aturan:
        return None
    p = path or getattr(handler, "path", "") or ""
    if p.startswith("/api/v1/health") or p == "/health":
        return None
    if not p.startswith("/api/"):
        return None                      # file statis tidak dihitung
    n, per = aturan
    return _ambil(kunci(handler), n, per)


def status():
    with LOCK:
        return {"spec": spec(), "aktif": bool(parse(spec())), "kunci_aktif": len(_EMBER),
                "lolos": _HIT["lolos"], "kena_batas": _HIT["batas"],
                "contoh": sorted(_EMBER.keys())[:5]}


def reset():
    with LOCK:
        _EMBER.clear()
        _HIT["lolos"] = 0
        _HIT["batas"] = 0
