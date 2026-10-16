#!/usr/bin/env python3
"""Uji resolver pool proxy. Tanpa jaringan, tanpa kredensial."""
import inspect
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import proxypool as pp  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS %s" % name)
    else:
        FAIL += 1
        print("FAIL %s   <-- %s" % (name, str(detail)[:180]))


check("parse host:port", pp.parse_spec("127.0.0.1:8888") == ("127.0.0.1", 8888, None, None))
check("parse user:pass@host:port",
      pp.parse_spec("budi:rahasia@10.0.0.1:1080") == ("10.0.0.1", 1080, "budi", "rahasia"))
check("parse skema http://", pp.parse_spec("http://u:p@h.example:3128")[0] == "h.example")
check("parse user tanpa password", pp.parse_spec("budi@h:1")[2] == "budi")

for bad, why in (("", "kosong"), ("h", "tanpa port"), ("h:abc", "port bukan angka"),
                 (":80", "host kosong"), ("h:99999", "port di luar rentang")):
    try:
        pp.parse_spec(bad)
        check("tolak %r" % (bad or "<kosong>"), False, "tidak menolak")
    except pp.PoolError:
        check("tolak %r (%s)" % (bad or "<kosong>", why), True)

pp.clear()
for k in list(os.environ):
    if k.startswith(pp.PREFIX):
        os.environ.pop(k)

check("tanpa isi -> resolve None", pp.resolve("residential") is None)
check("nama kosong -> None", pp.resolve("") is None)
check("pool tidak dikenal -> None", pp.resolve("entah") is None)

pp.register("lab", "127.0.0.1:8081")
check("register -> resolve", pp.resolve("lab") == ("127.0.0.1", 8081))
check("known memuat pool", pp.known() == ["lab"], pp.known())

os.environ[pp.env_key("residential")] = "203.0.113.9:9000"
check("env -> resolve", pp.resolve("residential") == ("203.0.113.9", 9000))
check("env kredensial", pp.credentials("residential") == (None, None))

pp.register("rumah", "andi:sandi@198.51.100.7:1080")
check("kredensial terbaca", pp.credentials("rumah") == ("andi", "sandi"))
check("resolve pakai host:port saja", pp.resolve("rumah") == ("198.51.100.7", 1080))

try:
    import transport
    print("   transport.Transport%s" % str(inspect.signature(transport.Transport)))
    t = None
    for args in ((), ("127.0.0.1", 1)):
        try:
            t = transport.Transport(*args)
            break
        except Exception as e:
            print("   Transport%r -> %s" % (args, e))
    if t is None:
        check("Transport bisa dibuat", False, "semua bentuk gagal")
    else:
        ep = pp.apply(t, "lab")
        got = getattr(t, "proxy", None) or getattr(t, "_proxy", None)
        print("   atribut proxy setelah apply: %r" % (got,))
        check("apply memasang endpoint", ep == ("127.0.0.1", 8081) and got == ("127.0.0.1", 8081),
              "ep=%r proxy=%r" % (ep, got))
        check("apply pool kosong -> None", pp.apply(t, "entah") is None)
except Exception as e:
    check("modul transport bisa diimpor", False, "%s: %s" % (type(e).__name__, e))

pp.clear()
print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
