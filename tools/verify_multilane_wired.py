#!/usr/bin/env python3
"""Verifier wiring multi-lane: orchestrator menjalankan engine dengan lane (gated env)."""
import ast
import inspect
import os
import re
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


def src(nama):
    with open(os.path.join(BACKEND, nama), encoding="utf-8") as fh:
        return fh.read()


def main():
    print("== verify_multilane_wired (AST + behavioral) ==")
    o = src("orchestrator.py")
    p = src("proxy.py")
    try:
        otree = ast.parse(o)
        cek("orchestrator.py valid secara AST", True)
    except SyntaxError as exc:
        cek("orchestrator.py valid secara AST", False, repr(exc))
        return 1

    cek("orchestrator punya _lanes_aktif()",
        any(isinstance(n, ast.FunctionDef) and n.name == "_lanes_aktif" for n in ast.walk(otree)))

    seg = None
    for node in ast.walk(otree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "LoadEngine":
            seg = ast.get_source_segment(o, node) or ""
            break
    cek("orchestrator memanggil LoadEngine", seg is not None)
    if seg:
        cek("LoadEngine dipanggil dengan lanes=", "lanes=" in seg)
        cek("lanes berasal dari _lanes_aktif()", "_lanes_aktif()" in seg)
        cek("arg lama tetap utuh (abort_check)", "abort_check" in seg)
        cek("arg lama tetap utuh (target canonical_origin)", "canonical_origin" in seg)

    cek("proxy.py punya def lanes_aktif",
        any(isinstance(n, ast.FunctionDef) and n.name == "lanes_aktif" for n in ast.walk(ast.parse(p))))
    cek("api.py masih punya route /lanes", '"/lanes"' in src("api.py"))

    import proxy as P
    cek("behavioral: proxy.lanes_aktif() -> list", isinstance(P.lanes_aktif(), list), repr(type(P.lanes_aktif())))
    cek("behavioral: lanes_aktif(None) aman", isinstance(P.lanes_aktif(None), list))

    import engine as E
    cek("behavioral: LoadEngine menerima lanes",
        "lanes" in inspect.signature(E.LoadEngine.__init__).parameters)

    import orchestrator as O
    ada = hasattr(O, "_lanes_aktif")
    cek("behavioral: orchestrator._lanes_aktif ada", ada)
    if ada:
        os.environ.pop("GALARDO_MULTILANE", None)
        cek("behavioral: env mati -> None", O._lanes_aktif() is None, repr(O._lanes_aktif()))
        os.environ["GALARDO_MULTILANE"] = "1"
        h = O._lanes_aktif()
        cek("behavioral: env hidup -> list/None", h is None or isinstance(h, list), repr(h))
        os.environ.pop("GALARDO_MULTILANE", None)

    env_path = os.path.join(ROOT, ".env")
    isi_env = ""
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            isi_env = fh.read()
    cek(".env memuat GALARDO_MULTILANE",
        re.search(r"(?m)^GALARDO_MULTILANE=", isi_env) is not None)

    print()
    if FAIL:
        print("  [MERAH] verify_multilane_wired: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_multilane_wired: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
