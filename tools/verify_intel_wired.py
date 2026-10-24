#!/usr/bin/env python3
"""Verifier WIRING /intel/preflight (AST + behavioral, tanpa HTTP).

Mengunci: api.py mengimpor intel, route POST /intel/preflight ada, handler memanggil
intel.preflight, punya jalur 200 + 422, dan tidak merusak cabang proxy/status.
Pelajaran #22: cek struktur kode lewat AST, bukan teks mentah.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import intel as I  # noqa: E402

API = os.path.join(BACKEND, "api.py")
INTEL = os.path.join(BACKEND, "intel.py")
ROUTE = "/intel/preflight"

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


def baca(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def seg_untuk_route(tree, src, route):
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(src, node) or ""
            if route in seg:
                return node, seg
    return None, None


def main():
    print("== verify_intel_wired (AST + behavioral) ==")
    src = baca(API)
    isrc = baca(INTEL)

    try:
        tree = ast.parse(src)
        cek("api.py tetap valid secara AST", True)
    except SyntaxError as exc:
        cek("api.py tetap valid secara AST", False, repr(exc))
        tree = None

    if tree is not None:
        ada_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                ada_import = ada_import or any(a.name == "intel" or a.name.endswith(".intel") for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                ada_import = ada_import or any(a.name == "intel" for a in node.names)
        cek("api.py mengimpor intel", ada_import)

        node, seg = seg_untuk_route(tree, src, ROUTE)
        cek("route %s ada sebagai cabang If" % ROUTE, seg is not None)

        if seg is not None:
            test_src = ast.get_source_segment(src, node.test) or ""
            cek("route terikat method POST", "POST" in test_src, repr(test_src))
            cek("route memakai api_path", "api_path" in test_src, repr(test_src))
            cek("handler membaca body lewat self._body", "self._body" in seg)
            cek("handler memanggil intel.preflight", "intel.preflight" in seg)
            cek("handler punya jalur sukses 200", "_json(200" in seg)
            cek("handler punya jalur error 422", "422" in seg)

        cek("cabang proxy/status tidak rusak", '/proxy/status' in src or '"/proxy/status"' in src)
        cek("cabang gateway/status tidak rusak", "/gateway/status" in src)

    itree = ast.parse(isrc)
    ada_preflight = any(isinstance(n, ast.FunctionDef) and n.name == "preflight" for n in ast.walk(itree))
    cek("intel.py masih punya def preflight", ada_preflight)

    # behavioral: jalur yang dipakai handler benar-benar bekerja
    try:
        pf = I.preflight({"domain": "a.example", "origin": "1.2.3.4"},
                         {"origins": ["9.9.9.9"], "egress": ["1.2.3.4"]})
        peta = {r["field"]: r["verdict"] for r in pf["divergensi"]}
        cek("behavioral: preflight mengembalikan divergensi", len(pf["divergensi"]) == len(I.FIELDS_DIBANDING))
        cek("behavioral: beda origin terdeteksi", peta["origins"] == I.VERDICT_BEDA, repr(peta))
        cek("behavioral: ringkasan konsisten", pf["ringkasan"]["total"] == len(pf["divergensi"]))
    except Exception as exc:
        cek("behavioral: preflight berjalan", False, repr(exc))

    try:
        pf2 = I.preflight("domain: b.example\norigin: 5.5.5.5\nsumber: rea", ukur=False)
        cek("behavioral: payload teks + ukur=False aman", pf2["ringkasan"]["total"] == len(I.FIELDS_DIBANDING))
    except Exception as exc:
        cek("behavioral: payload teks + ukur=False aman", False, repr(exc))

    print()
    if FAIL:
        print("  [MERAH] verify_intel_wired: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_intel_wired: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
