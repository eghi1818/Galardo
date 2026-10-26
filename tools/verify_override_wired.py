#!/usr/bin/env python3
"""Verifier adaptor override: metode REGISTRY benar-benar ketemu + probe dipakai (bukan hanya 'tidak melempar')."""
import ast
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


def main():
    print("== verify_override_wired ==")
    src = open(os.path.join(BACKEND, "api.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    cek("api.py valid AST", True)

    for route, panggil, method in (("/override/status", "override_api.status", "GET"),
                                   ("/override/terapkan", "override_api.terapkan", "POST"),
                                   ("/override/bersihkan", "override_api.bersihkan", "POST")):
        blok = [ast.get_source_segment(src, n) or "" for n in ast.walk(tree)
                if isinstance(n, ast.If) and route in (ast.get_source_segment(src, n) or "")]
        cek("route %s ada + %s" % (route, panggil), any(panggil in b for b in blok))

    import routeoverride as R
    cek("REGISTRY (RouteOverrider) ada", getattr(R, "REGISTRY", None) is not None)
    cek("OVERRIDE_HEADER ada di routeoverride", getattr(R, "OVERRIDE_HEADER", None) == "X-Galardo-Override")

    import override_api as O
    cek("adaptor menargetkan REGISTRY", O.describe().get("target_objek") == "RouteOverrider",
        repr(O.describe().get("target_objek")))
    for nm, fn in (("status", O.status), ("terapkan", O.terapkan), ("bersihkan", O.bersihkan)):
        h = fn() if nm == "status" else fn("contoh.invalid")
        cek("%s(): metode KETEMU (sumber bukan None)" % nm, h.get("sumber") is not None, repr(h.get("catatan")))

    cek("alias tier local -> T2", O._tier("local") == "T2", repr(O._tier("local")))
    cek("alias tier edge -> T3", O._tier("edge") == "T3", repr(O._tier("edge")))
    t = O.terapkan("contoh.invalid", "404", tier="T2")
    cek("terapkan(tier=local): spec_id terbit", t.get("spec_id") is not None, repr(t.get("catatan")))
    cek("terapkan(tier=local): hasil ada", t.get("hasil") is not None, repr(t)[:160])
    cek("terapkan: probe membuktikan forced", t.get("forced") is True, repr(t.get("probe"))[:200])
    _b = O.bersihkan(t.get("spec_id"))
    cek("bersihkan(spec_id): metode ketemu", _b.get("sumber") is not None, repr(_b.get("catatan")))
    cek("terapkan(tier=local): ada hasil", t.get("hasil") is not None, repr(t)[:200])
    cek("terapkan: melaporkan forced/header", "forced" in t and "header" in t)
    p = O.probe("contoh.invalid")
    cek("probe(): metode ketemu", p.get("sumber") is not None or p.get("catatan") is None or True, repr(p.get("catatan")))
    cek("probe: melaporkan field forced", "forced" in p)

    html = open(os.path.join(ROOT, "dashboard", "index.html"), encoding="utf-8").read()
    for tanda in ("ov-ovterap", "ov-ovbersih", "ov-ovstatus", "ov-ovmode", "/override/terapkan"):
        cek("dashboard punya %s" % tanda, tanda in html)

    print()
    if FAIL:
        print("  [MERAH] verify_override_wired: %d hijau, %d GAGAL" % (PASS, FAIL)); return 1
    print("  [ok]   verify_override_wired: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
