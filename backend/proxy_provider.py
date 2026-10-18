"""GALARDO - adapter provider proxy/residential (fail-open).

Melengkapi backend/proxypool.py: proxypool tahu CARA memakai proxy (parse + register),
modul ini yang MENGAMBIL daftar dari API pihak ketiga dan merotasinya.

Aktif hanya bila GALARDO_PROXY_URL diisi. Kosong / gagal / timeout -> daftar lama
dipertahankan dan jalur probe jatuh ke koneksi langsung (tidak melempar).

Env:
    GALARDO_PROXY_URL      base URL API provider (wajib untuk aktif)
    GALARDO_PROXY_KEY      API key / token
    GALARDO_PROXY_AUTH     header auth, default "Authorization: Bearer {key}"
    GALARDO_PROXY_POOL     nama pool yang didaftarkan, default "residential"
    GALARDO_PROXY_TTL      detik cache daftar, default 300
    GALARDO_PROXY_TIMEOUT  detik timeout fetch, default 8
"""
import json
import os
import threading
import time
import urllib.request

import netssl as _ns
import proxypool

URL_ENV = "GALARDO_PROXY_URL"
KEY_ENV = "GALARDO_PROXY_KEY"
AUTH_ENV = "GALARDO_PROXY_AUTH"
POOL_ENV = "GALARDO_PROXY_POOL"
TTL_ENV = "GALARDO_PROXY_TTL"
TMO_ENV = "GALARDO_PROXY_TIMEOUT"

LOCK = threading.RLock()
_DAFTAR = []          # list (host, port, user, password)
_IDX = 0
_AT = 0.0
_ERR = ""
_SUMBER = ""


def _env(nama, default=None):
    v = (os.environ.get(nama) or "").strip()
    return v or default


def pool_name():
    return _env(POOL_ENV, "residential")


def ttl():
    try:
        return float(_env(TTL_ENV, "300"))
    except ValueError:
        return 300.0


def timeout():
    try:
        return float(_env(TMO_ENV, "8"))
    except ValueError:
        return 8.0


def enabled():
    return bool(_env(URL_ENV))


def status():
    with LOCK:
        return {"configured": enabled(), "pool": pool_name(), "count": len(_DAFTAR),
                "ttl": ttl(), "last_fetch": _AT, "age": (round(time.time() - _AT, 1) if _AT else None),
                "index": _IDX, "error": _ERR, "source": _SUMBER,
                "endpoint": _endpoint(_DAFTAR[_IDX] if _DAFTAR else None)}


def _endpoint(item):
    if not item:
        return None
    host, port, user, password = item
    return {"host": host, "port": port, "user": user, "password_set": bool(password)}


# ------------------------------------------------------------------ parser

def _kandidat(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("data", "proxies", "results", "list", "items", "proxy_list", "rows", "nodes"):
            v = obj.get(k)
            if isinstance(v, (list, dict)):
                got = _kandidat(v)
                if got:
                    return got
    return []


def _spec_dari_item(it):
    if isinstance(it, str):
        s = it.strip()
        if not s:
            return None
        if "@" not in s and s.count(":") == 3:      # host:port:user:pass
            h, p, u, pw = s.split(":")
            s = "%s:%s@%s:%s" % (u, pw, h, p)
        return s
    if isinstance(it, dict):
        host = it.get("host") or it.get("ip") or it.get("address") or it.get("server") or ""
        port = it.get("port") or it.get("http_port") or it.get("https_port") or ""
        user = it.get("user") or it.get("username") or it.get("login") or ""
        pwd = it.get("pass") or it.get("password") or it.get("pwd") or ""
        if not host or not port:
            return None
        host, port = str(host), str(port)
        if ":" in host and not user:
            host, _, p2 = host.partition(":")
            port = port or p2
        return ("%s:%s@%s:%s" % (user, pwd, host, port)) if user else ("%s:%s" % (host, port))
    return None


def parse_daftar(teks):
    """Respons provider (JSON atau teks) -> list (host, port, user, password)."""
    out = []
    if not teks:
        return out
    obj = None
    try:
        obj = json.loads(teks)
    except Exception:
        obj = None
    kandidat = _kandidat(obj) if obj is not None else [l.strip() for l in teks.splitlines() if l.strip()]
    for it in kandidat:
        spec = _spec_dari_item(it)
        if not spec:
            continue
        try:
            ep = proxypool.parse_spec(spec)
        except Exception:
            continue
        if ep not in out:
            out.append(ep)
    return out


# ------------------------------------------------------------------ fetch

def _header():
    key = _env(KEY_ENV)
    if not key:
        return {}
    bentuk = _env(AUTH_ENV, "Authorization: Bearer {key}")
    nama, _, nilai = bentuk.partition(":")
    return {nama.strip(): nilai.strip().replace("{key}", key)}


def _fetch(url=None, tmo=None):
    """Kembalikan teks respons. Melempar bila gagal (ditangkap pemanggil)."""
    u = url or _env(URL_ENV)
    req = urllib.request.Request(u, headers=_header())
    with urllib.request.urlopen(req, timeout=float(tmo or timeout()), context=_ns.context()) as r:
        return r.read().decode("utf-8", "replace")


def refresh(force=False, fetcher=None):
    """Ambil daftar dari provider. Fail-open: daftar lama dipertahankan bila gagal."""
    global _DAFTAR, _AT, _ERR, _SUMBER, _IDX
    if not enabled() and fetcher is None:
        with LOCK:
            _ERR = "GALARDO_PROXY_URL kosong"
        return status()
    with LOCK:
        if not force and _DAFTAR and (time.time() - _AT) < ttl():
            return status()
    fn = fetcher or _fetch
    try:
        teks = fn()
        daftar = parse_daftar(teks)
        if not daftar:
            raise ValueError("respons provider tidak memuat proxy yang bisa diparse")
        with LOCK:
            _DAFTAR = daftar
            _IDX = 0
            _AT = time.time()
            _ERR = ""
            _SUMBER = _env(URL_ENV, "fetcher")
            proxypool.register(pool_name(), _spec_dari_item(_spec_str(daftar[0])))
        return status()
    except Exception as exc:
        with LOCK:
            _ERR = "%s: %s" % (type(exc).__name__, exc)
        return status()


def _spec_str(item):
    host, port, user, password = item
    return ("%s:%s@%s:%s" % (user, password, host, port)) if user else ("%s:%s" % (host, port))


def rotate():
    """Pindah ke proxy berikutnya (round-robin) dan daftarkan sebagai pool aktif."""
    global _IDX
    with LOCK:
        if not _DAFTAR:
            return status()
        _IDX = (_IDX + 1) % len(_DAFTAR)
        proxypool.register(pool_name(), _spec_str(_DAFTAR[_IDX]))
    return status()


def ensure(nama=None, fetcher=None):
    """Dipakai proxypool.resolve(): pastikan pool ini terdaftar. True bila ada."""
    if nama and nama != pool_name():
        return False
    if not enabled() and fetcher is None:
        return False
    refresh(fetcher=fetcher)
    with LOCK:
        if not _DAFTAR:
            return False
        proxypool.register(pool_name(), _spec_str(_DAFTAR[_IDX]))
        return True
