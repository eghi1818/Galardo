#!/usr/bin/env python3
"""Verifier wiring POST /checkhost (AST + behavioral). Pelajaran #22: cek struktur via AST."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import checkhost as C  # noqa: E402

API = os.path.join(BACKEND, "api.py")
CH = os.path.join(BACKEND, "checkhost.py")
ROUTE = "/checkhost"
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
    print("== verify_checkhost_wired (AST + behavioral) ==")
    src = open(API, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
        cek("api.py valid secara AST", True)
    except SyntaxError as exc:
        cek("api.py valid secara AST", False, repr(exc))
        return 1

    ada = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            ada = ada or any(a.name == "checkhost" or a.name.endswith(".checkhost") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            ada = ada or any(a.name == "checkhost" for a in node.names)
    cek("api.py mengimpor checkhost", ada)

    seg = None
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            t = ast.get_source_segment(src, node) or ""
            if ROUTE in t:
                seg = t
                break
    cek("route %s ada" % ROUTE, seg is not None)
    if seg:
        cek("route terikat POST", "POST" in seg)
        cek("route memakai api_path", "api_path" in seg)
        cek("handler memakai self._body", "self._body" in seg)
        cek("handler memanggil checkhost.probe", "checkhost.probe" in seg)
        cek("handler punya jalur 422 url wajib", "url wajib" in seg)
        cek("handler punya jalur sukses 200", "_json(200" in seg)
    cek("cabang proxy/status utuh", "/proxy/status" in src)
    cek("cabang /lanes utuh", '"/lanes"' in src)

    ctree = ast.parse(open(CH, encoding="utf-8").read())
    cek("checkhost.py punya def probe",
        any(isinstance(n, ast.FunctionDef) and n.name == "probe" for n in ast.walk(ctree)))
    h = C.probe("contoh.invalid", max_nodes=1, batas=0.1)
    cek("behavioral: probe() tetap mengembalikan struktur walau jaringan apa pun",
        set(("url", "baris", "ringkasan", "catatan")).issubset(h.keys()))
    print()
    if FAIL:
        print("  [MERAH] verify_checkhost_wired: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_checkhost_wired: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
