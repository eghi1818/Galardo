#!/usr/bin/env python3
"""Verifier wiring endpoint bukti (AST + behavioral). Tahan variasi bentuk import."""
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


def modul_diimpor(tree, nama):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == nama or a.name.endswith("." + nama) for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if any(a.name == nama for a in node.names):
                return True
    return False


def blok_route(tree, src, route):
    kandidat = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(src, node) or ""
            if route in seg and "api_path" in seg:
                kandidat.append(seg)
    return kandidat


def main():
    print("== verify_bukti_wired (AST) ==")
    src = open(os.path.join(BACKEND, "api.py"), encoding="utf-8").read()
    try:
        tree = ast.parse(src)
        cek("api.py valid AST", True)
    except SyntaxError as exc:
        cek("api.py valid AST", False, repr(exc)); return 1

    for mod in ("verdict", "falsify", "bukti"):
        cek("api.py mengimpor %s" % mod, modul_diimpor(tree, mod))
    cek("api.py masih mengimpor evidence (route /evidence lama)", modul_diimpor(tree, "evidence"))

    for route, panggil in (("/verdict", "verdict.nilai_dari"), ("/falsify", "falsify.jalankan"),
                           ("/bukti", "bukti.buat")):
        blok = blok_route(tree, src, route)
        cek("route %s ada" % route, len(blok) > 0)
        if blok:
            cek("  %s terikat POST + %s" % (route, panggil),
                any("POST" in b and panggil in b for b in blok), repr(panggil))
            cek("  %s punya jalur 422" % route, any("422" in b for b in blok))

    import bukti as B
    cek("behavioral: bukti.buat + verifikasi_rantai",
        B.verifikasi_rantai([B.buat("x", {"a": "b"})])["ok"] is True)
    import falsify as F
    cek("behavioral: falsify.jalankan", isinstance(F.jalankan({"mode": "HIDUP"}, {}), dict))

    print()
    if FAIL:
        print("  [MERAH] verify_bukti_wired: %d hijau, %d GAGAL" % (PASS, FAIL)); return 1
    print("  [ok]   verify_bukti_wired: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
