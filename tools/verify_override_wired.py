#!/usr/bin/env python3
"""Verifier wiring panel override edge (AST + behavioral offline)."""
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
    print("== verify_override_wired (AST + behavioral) ==")
    src = open(os.path.join(BACKEND, "api.py"), encoding="utf-8").read()
    try:
        tree = ast.parse(src)
        cek("api.py valid AST", True)
    except SyntaxError as exc:
        cek("api.py valid AST", False, repr(exc)); return 1

    ada = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            ada = ada or any(a.name == "override_api" for a in node.names)
    cek("api.py mengimpor override_api", ada)

    for route, panggil, method in (("/override/status", "override_api.status", "GET"),
                                   ("/override/terapkan", "override_api.terapkan", "POST"),
                                   ("/override/bersihkan", "override_api.bersihkan", "POST")):
        blok = [ast.get_source_segment(src, n) or "" for n in ast.walk(tree)
                if isinstance(n, ast.If) and route in (ast.get_source_segment(src, n) or "") and "api_path" in (ast.get_source_segment(src, n) or "")]
        cek("route %s ada" % route, len(blok) > 0)
        if blok:
            cek("  %s %s + %s" % (route, method, panggil),
                any(method in b and panggil in b for b in blok))

    import override_api as O
    cek("header pembeda terdefinisi", isinstance(O.HEADER, str) and len(O.HEADER) > 3, repr(O.HEADER))
    cek("4 mode override tersedia", set(O.MODE) == {"404", "410", "503", "blank"}, repr(O.MODE))
    s = O.status()
    cek("status() tidak melempar + dict", isinstance(s, dict) and "header" in s, repr(s)[:120])
    t = O.terapkan("contoh.invalid", "404")
    cek("terapkan() tidak melempar + dict", isinstance(t, dict) and t.get("mode") == "404", repr(t)[:120])
    b = O.bersihkan("contoh.invalid")
    cek("bersihkan() tidak melempar + dict", isinstance(b, dict), repr(b)[:120])
    cek("describe menyebut header pembeda", O.HEADER in O.describe()["prinsip"])

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
