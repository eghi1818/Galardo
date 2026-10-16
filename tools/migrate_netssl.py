#!/usr/bin/env python3
"""Migrasi modul HTTPS ke netssl.context() secara aman.

Hanya mengganti PEMBUATAN context:
    ssl.create_default_context(        ->  _ns.context(
    ssl._create_unverified_context()   ->  _ns.context(verify=False)

Override check_hostname / verify_mode setelahnya TETAP berlaku, jadi tidak
perlu diubah. Setiap file: backup -> tulis -> py_compile -> kalau gagal, pulihkan.
"""
import os
import pathlib
import py_compile
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT = ROOT / ".out"
OUT.mkdir(exist_ok=True)
DRY = "--dry-run" in sys.argv

TARGETS = ["engine.py", "observer.py", "routeoverride.py", "safety.py",
           "srccap.py", "step_load.py", "transport.py", "external_probe.py"]

IMPORT_BLOCK = ("\ntry:\n    from . import netssl as _ns\nexcept ImportError:\n"
                "    import netssl as _ns\n")


def insert_import(src):
    if "netssl as _ns" in src:
        return src, False
    lines = src.splitlines(True)
    last = 0
    for i, ln in enumerate(lines[:90]):
        if re.match(r"^(import|from)\s", ln):
            last = i
    lines.insert(last + 1, IMPORT_BLOCK)
    return "".join(lines), True


def compile_ok(path):
    try:
        py_compile.compile(str(path), doraise=True)
        return True, ""
    except Exception as e:
        return False, str(e)[:160]


results = []
for name in TARGETS:
    p = BACKEND / name
    if not p.is_file():
        results.append((name, "TIDAK ADA", 0, "-"))
        continue
    src = p.read_text(encoding="utf-8")
    orig = src
    if "netssl as _ns" in src and "ssl.create_default_context" not in src \
            and "ssl._create_unverified_context" not in src:
        results.append((name, "sudah", 0, "-"))
        continue

    src, added = insert_import(src)
    src, n1 = re.subn(r"ssl\.create_default_context\(", "_ns.context(", src)
    src, n2 = re.subn(r"ssl\._create_unverified_context\(\)",
                      "_ns.context(verify=False)", src)
    total = n1 + n2

    if src == orig:
        results.append((name, "tidak berubah", 0, "-"))
        continue

    if DRY:
        results.append((name, "AKAN diubah", total, "+import" if added else ""))
        continue

    shutil.copy2(str(p), str(OUT / (name + ".bak-migrasi")))
    p.write_text(src, encoding="utf-8")
    ok, err = compile_ok(p)
    if not ok:
        shutil.copy2(str(OUT / (name + ".bak-migrasi")), str(p))
        results.append((name, "GAGAL -> dipulihkan", total, err))
    else:
        results.append((name, "DIUBAH", total, "+import" if added else ""))

print("=== %s ===" % ("DRY-RUN" if DRY else "MIGRASI"))
for name, status, n, note in results:
    print("  %-22s %-20s ganti=%-3d %s" % (name, status, n, note))
bad = [r for r in results if "GAGAL" in r[1]]
print("  gagal: %d" % len(bad))
sys.exit(1 if bad else 0)
