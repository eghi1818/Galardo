#!/usr/bin/env python3
"""Verifier: `make dev-up` benar-benar melayani HTTP (penjaga run_local.py).

Motivasi: make test tidak pernah menyalakan server, sehingga run_local.py bisa rusak
sementara seluruh gate tetap hijau (kejadian nyata di STEP-74).
"""
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "http://127.0.0.1:8090/api/v1/health"
DEVNULL = subprocess.DEVNULL
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


subprocess.run(["make", "dev-down"], cwd=ROOT, stdout=DEVNULL, stderr=DEVNULL)
proc = subprocess.Popen(["make", "dev-up"], cwd=ROOT, stdout=DEVNULL, stderr=subprocess.STDOUT)
try:
    kode = None
    for _ in range(25):
        try:
            with urllib.request.urlopen(URL, timeout=3) as r:
                kode = r.status
            if kode == 200:
                break
        except Exception:
            kode = None
        time.sleep(1)
    check("dev-up melayani GET /api/v1/health 200", kode == 200, kode)
    if kode == 200:
        try:
            with urllib.request.urlopen(URL, timeout=3) as r:
                body = r.read().decode("utf-8", "replace")
            check("body health memuat status ok", '"status": "ok"' in body or '"status":"ok"' in body, body[:120])
        except Exception as exc:
            check("body health memuat status ok", False, exc)
finally:
    subprocess.run(["make", "dev-down"], cwd=ROOT, stdout=DEVNULL, stderr=DEVNULL)
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
