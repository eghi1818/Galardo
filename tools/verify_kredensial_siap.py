#!/usr/bin/env python3
"""Pengunci kontrak pra-kredensial: jalur rotasi egress harus siap SEBELUM kredensial masuk."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

PASS = 0
FAIL = 0


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


def baca(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def main():
    print("== verify_kredensial_siap (offline) ==")
    for nama in ("tools/verify_egress_rotation.py", "backend/gateway.py", "backend/egress.py",
                 "backend/proxypool.py", "backend/proxy.py", "docs/KREDENSIAL-ANYIP.md"):
        cek("%s ada" % nama, os.path.exists(os.path.join(ROOT, nama)))

    g = baca(os.path.join(BACKEND, "gateway.py"))
    a = baca(os.path.join(BACKEND, "api.py"))
    rot = baca(os.path.join(ROOT, "tools", "verify_egress_rotation.py"))
    dok = baca(os.path.join(ROOT, "docs", "KREDENSIAL-ANYIP.md"))

    cek("gateway.py membaca GALARDO_GATEWAY_URL", "GALARDO_GATEWAY_URL" in g)
    cek("gateway.py mendukung user:pass@host:port & socks", "@" in g and "socks" in g.lower())
    cek("api.py punya boot gateway", "GALARDO_GATEWAY_BOOT" in a)
    cek("api.py punya route /egress/status", "egress/status" in a)
    cek("verifier rotasi punya jalur SKIP (aman tanpa kredensial)", "skip" in rot.lower())
    cek("checklist menyebut GALARDO_GATEWAY_URL", "GALARDO_GATEWAY_URL" in dok)
    cek("checklist menyebut syarat IP unik >= 2", "unik" in dok.lower() and "2" in dok)

    try:
        import gateway as G
        fn = None
        for kandidat in ("parse", "parse_spec", "spec", "parse_url"):
            if callable(getattr(G, kandidat, None)):
                fn = getattr(G, kandidat)
                break
        cek("gateway punya fungsi parse spec", fn is not None)
        if fn is not None:
            try:
                hasil = fn("user:pass@host.example:8080")
            except TypeError:
                hasil = fn("user:pass@host.example:8080", None)
            cek("parse spec user:pass@host:port tidak melempar", hasil is not None, repr(hasil)[:120])
    except Exception as exc:
        cek("import gateway + parse spec", False, repr(exc))

    print()
    if FAIL:
        print("  [MERAH] verify_kredensial_siap: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_kredensial_siap: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
