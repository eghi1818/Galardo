#!/usr/bin/env python3
"""Verifier F-7: pagar waktu total probe_all (budget) benar-benar berlaku."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import udp_probe as up  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


src = open(os.path.join(BACKEND, "udp_probe.py")).read()
api = open(os.path.join(BACKEND, "api.py")).read()

# A. bentuk sumber
check("A probe_all punya parameter budget", "def probe_all(" in src and "budget=None" in src)
check("A budget default dari GALARDO_UDP_BUDGET", "GALARDO_UDP_BUDGET" in src)
check("A ada penanda skipped", '"skipped": "budget"' in src)
check("A stage fan-out dibatasi deadline", "deadline=deadline" in src and src.count(">= deadline") >= 2)
check("A timeout per-target dibatasi sisa deadline", "min(timeout, deadline - time.time())" in src)
check("A setiap tahap pakai min(timeout, sisa())", src.count("min(timeout, sisa())") >= 3, src.count("min(timeout, sisa())"))
check("A endpoint meneruskan budget", "budget=float(" in api and "b.get(\"budget\")" in api)
check("A spoof dibatasi", "spoof_timeout" in api)

import ast as _ast
_bad = []
for _n in _ast.walk(_ast.parse(api)):
    if (isinstance(_n, _ast.Call) and isinstance(_n.func, _ast.Attribute)
            and _n.func.attr == "get" and _n.keywords):
        _bad.append(_n.lineno)
check("A tidak ada dict.get dengan keyword", not _bad, _bad)


# B. fungsional: tahap lambat -> pagar dihormati
asli = {n: getattr(up, n) for n in
        ("probe_dns_best", "probe_dns", "probe_ntp", "probe_ssdp", "rotate_source_ports")}


def lambat(tidur):
    def f(*a, **k):
        time.sleep(tidur)
        return {"responded": False, "best": {}}
    return f


try:
    for n in ("probe_dns_best", "probe_dns"):
        setattr(up, n, lambat(0.5))
    up.probe_ntp = lambat(0.5)
    up.probe_ssdp = lambat(0.5)
    up.rotate_source_ports = lambat(0.5)

    t0 = time.time()
    r = up.probe_all(budget=1.0)
    el = time.time() - t0
    check("B wall time <= budget + margin", el <= 2.2, round(el, 2))
    check("B ada tahap ditandai skipped", bool(r.get("skipped")), r.get("skipped"))
    check("B elapsed dilaporkan", isinstance(r.get("elapsed"), (int, float)), r.get("elapsed"))
    check("B budget dilaporkan", r.get("budget") == 1.0, r.get("budget"))

    for n in ("probe_dns_best", "probe_dns"):
        setattr(up, n, lambat(0.05))
    up.probe_ntp = lambat(0.05)
    up.probe_ssdp = lambat(0.05)
    up.rotate_source_ports = lambat(0.05)
    r2 = up.probe_all(budget=5.0)
    check("B tahap cepat tidak di-skip", not r2.get("skipped"), r2.get("skipped"))
finally:
    for n, f in asli.items():
        setattr(up, n, f)

# C. env dipakai sebagai default
os.environ["GALARDO_UDP_BUDGET"] = "0.5"
try:
    t0 = time.time()
    r3 = up.probe_all()
    check("C budget default diambil dari env", r3.get("budget") == 0.5, r3.get("budget"))
    check("C pagar berlaku walau probe nyata", time.time() - t0 <= 1.2, round(time.time() - t0, 2))
finally:
    os.environ.pop("GALARDO_UDP_BUDGET", None)

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
