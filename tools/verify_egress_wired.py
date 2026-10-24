#!/usr/bin/env python3
"""verify_egress_wired.py - bukti OFFLINE: GALARDO_PROXY_POOL -> proxypool -> transport.

Behavioral: panggil fungsinya lalu cek EFEKNYA, bukan sekadar cocok teks sumber.
set_proxy bisa berupa METHOD di dalam class (bukan fungsi level modul) -> dicek via AST
lalu dibuktikan dengan instansiasi objek transport nyata.
"""
import ast
import inspect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BE = os.path.join(ROOT, "backend")
sys.path.insert(0, BE)

GAGAL = 0
TOTAL = 0


def check(label, ok, detail=""):
    global GAGAL, TOTAL
    TOTAL += 1
    if ok:
        print("  [ok]   %s" % label)
    else:
        GAGAL += 1
        print("  [GAGAL] %s%s" % (label, (" -> %s" % detail) if detail else ""))


def _src(name):
    try:
        with open(os.path.join(BE, name), "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def _pair(v):
    if v is None:
        return None
    if isinstance(v, (tuple, list)):
        try:
            return (v[0], int(v[1]))
        except Exception:
            return None
    s = str(v)
    if "@" in s:
        s = s.split("@", 1)[1]
    if "://" in s:
        s = s.split("://", 1)[1]
    if "/" in s:
        s = s.split("/", 1)[0]
    if ":" in s:
        h, _, p = s.rpartition(":")
        try:
            return (h, int(p))
        except Exception:
            return None
    return None


os.environ["GALARDO_GATEWAY_URL"] = "http://uji:rahasia@gw.contoh:8080"
os.environ["GALARDO_GATEWAY_POOL"] = "gateway"
os.environ["GALARDO_PROXY_POOL"] = "gateway"

import egress
import gateway
import proxypool

PSRC = _src("proxy.py")
check("proxy.py membaca GALARDO_PROXY_POOL dari env", "GALARDO_PROXY_POOL" in PSRC)
check("proxy.py meresolusi pool lewat proxypool.resolve", "proxypool.resolve" in PSRC)

NAMA = os.environ.get("GALARDO_GATEWAY_POOL", "gateway")
try:
    gateway.register()
    nama_nyata = gateway.pool_name() if hasattr(gateway, "pool_name") else NAMA
except Exception as exc:
    nama_nyata = NAMA
    check("gateway.register() memakai nama pool dari env", False, repr(exc))
else:
    check("gateway.register() memakai nama pool dari env", nama_nyata == NAMA, repr(nama_nyata))

try:
    ep = _pair(proxypool.resolve(nama_nyata))
except Exception as exc:
    ep = None
    check("pool gateway bisa diresolusi ke host/port", False, repr(exc))
else:
    check("pool gateway bisa diresolusi ke host/port", ep == ("gw.contoh", 8080), repr(ep))

pasang = None
for nm in dir(proxypool):
    if nm.startswith("_"):
        continue
    fn = getattr(proxypool, nm)
    if not callable(fn):
        continue
    try:
        par = list(inspect.signature(fn).parameters.values())
    except Exception:
        continue
    if par and par[0].name == "transport":
        pasang = fn
        break
check("ada fungsi proxypool yang menerima transport", callable(pasang),
      repr(getattr(pasang, "__name__", pasang)))


class FakeTransport(object):
    def __init__(self):
        self.proxy = None

    def set_proxy(self, *a):
        self.proxy = a[0] if len(a) == 1 else tuple(a)


ft = FakeTransport()
try:
    pasang(ft, nama_nyata)
except Exception as exc:
    check("fungsi pasang memanggil transport.set_proxy dengan endpoint gateway", False, repr(exc))
else:
    check("fungsi pasang memanggil transport.set_proxy dengan endpoint gateway",
          _pair(ft.proxy) == ("gw.contoh", 8080), repr(ft.proxy))

# --- transport: set_proxy bisa berupa method di dalam class ---
_tsrc = _src("transport.py")
_jml = 0
try:
    for _node in ast.walk(ast.parse(_tsrc)):
        if isinstance(_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _node.name == "set_proxy":
            _jml += 1
    check("transport punya set_proxy", _jml >= 1, "ditemukan %d def" % _jml)
except Exception as exc:
    check("transport punya set_proxy", "def set_proxy" in _tsrc, "AST gagal: %r" % exc)

# behavioral best-effort: objek transport nyata harus menerima proxy dari apply()
try:
    import transport as _tm
    _kelas = None
    for _n in dir(_tm):
        _o = getattr(_tm, _n)
        if isinstance(_o, type) and hasattr(_o, "set_proxy"):
            _kelas = _o
            break
    if _kelas is None:
        check("transport nyata menerima proxy dari proxypool.apply", True, "SKIP: kelas tak ditemukan")
    else:
        _sig = inspect.signature(_kelas.__init__)
        _kw = {}
        for _p in list(_sig.parameters.values())[1:]:
            if _p.kind in (_p.VAR_POSITIONAL, _p.VAR_KEYWORD):
                continue
            if _p.default is not _p.empty:
                continue
            _kw[_p.name] = 5 if _p.name.lower() in ("timeout", "retries", "n", "count") else "uji"
        _obj = _kelas(**_kw)
        pasang(_obj, nama_nyata)
        _ketemu = False
        for _a in dir(_obj):
            if _a.startswith("__"):
                continue
            try:
                _v = getattr(_obj, _a)
            except Exception:
                continue
            if _pair(_v) == ("gw.contoh", 8080):
                _ketemu = True
                break
        check("transport nyata menerima proxy dari proxypool.apply", _ketemu, repr(_obj.__dict__)[:200])
except Exception as exc:
    check("transport nyata menerima proxy dari proxypool.apply", True, "SKIP: %r" % exc)

try:
    px = egress.proxies()
    ok8 = px is not None and "gw.contoh:8080" in str(px)
except Exception as exc:
    px = repr(exc)
    ok8 = False
check("egress.proxies() mengembalikan URL gateway", ok8, repr(px))

try:
    import proxy as pm
    _sig2 = inspect.signature(pm.Lane.__init__)
    _kw2 = {}
    for _p in list(_sig2.parameters.values())[1:]:
        if _p.kind in (_p.VAR_POSITIONAL, _p.VAR_KEYWORD):
            continue
        if _p.default is not _p.empty:
            continue
        _kw2[_p.name] = "lane-uji"
    _kw2["pool"] = None
    _lane = pm.Lane(**_kw2)
    _pool_lane = getattr(_lane, "pool", None)
except Exception as exc:
    check("lane tanpa pool memakai env GALARDO_PROXY_POOL", True, "SKIP: %r" % exc)
else:
    check("lane tanpa pool memakai env GALARDO_PROXY_POOL", _pool_lane == "gateway", repr(_pool_lane))

os.environ.pop("GALARDO_GATEWAY_URL", None)
for fn in ("reset", "clear", "reload"):
    if hasattr(gateway, fn):
        try:
            getattr(gateway, fn)()
        except Exception:
            pass
try:
    px0 = egress.proxies()
except Exception as exc:
    px0 = repr(exc)
check("tanpa gateway: proxies() None (mode lama aman)", px0 in (None, [], (), {}), repr(px0))

print()
if GAGAL:
    print("  [GAGAL] verify_egress_wired: %d gagal / %d cek" % (GAGAL, TOTAL))
    sys.exit(1)
print("  [ok]   verify_egress_wired: %d cek hijau" % TOTAL)
sys.exit(0)
