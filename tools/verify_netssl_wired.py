#!/usr/bin/env python3
"""Pastikan modul HTTPS ke luar memakai netssl, bukan context bawaan."""
import os
import ssl
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import netssl            # noqa: E402
import external_probe    # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


ep = open(os.path.join(ROOT, "backend", "external_probe.py"), encoding="utf-8").read()

print("== A. external_probe ==")
check("A memakai netssl", "netssl as _ns" in ep, "import netssl hilang")
check("A tidak memakai context bawaan", "create_default_context" not in ep,
      [l for l in ep.splitlines() if "create_default_context" in l])
check("A memakai _ns.context", "_ns.context(" in ep, "pemanggilan hilang")

print("== B. netssl sehat ==")
check("B ca_file ada dan berisi", bool(netssl.ca_file()) and os.path.isfile(netssl.ca_file()),
      netssl.ca_file())
ctx = netssl.context()
check("B context verifikasi aktif", ctx.verify_mode == ssl.CERT_REQUIRED, ctx.verify_mode)
ctxn = netssl.context(verify=False)
check("B verify=False -> CERT_NONE", ctxn.verify_mode == ssl.CERT_NONE, ctxn.verify_mode)
ok, detail = netssl.verify_probe()
check("B verify_probe berhasil", ok is True, detail)

print("== C. probe hidup ==")
r = external_probe.probe_http("http://127.0.0.1:1/", timeout=2)
check("C probe port mati tidak melempar", isinstance(r, dict) and r.get("ok") is False, r)
check("C hasil probe punya atribusi lapisan", "layer" in r, list(r)[:6])

print("== D. pemindaian: modul lain yang masih pakai context bawaan ==")
kandidat = []
for fn in sorted(os.listdir(os.path.join(ROOT, "backend"))):
    if not fn.endswith(".py"):
        continue
    txt = open(os.path.join(ROOT, "backend", fn), encoding="utf-8").read()
    if "create_default_context" in txt and fn not in ("netssl.py",):
        kandidat.append(fn)
print("  kandidat: %s" % (kandidat or "(bersih)"))
check("D external_probe tidak lagi jadi kandidat", "external_probe.py" not in kandidat, kandidat)
print("== E. urlopen tanpa context di backend ==")
pelanggar = []
for fn in sorted(os.listdir(os.path.join(ROOT, "backend"))):
    if not fn.endswith(".py") or fn == "netssl.py":
        continue
    for i, l in enumerate(open(os.path.join(ROOT, "backend", fn), encoding="utf-8").read().split("\n")):
        if "urlopen(" in l and "context=" not in l:
            pelanggar.append("%s:%d" % (fn, i + 1))
check("E tak ada urlopen tanpa context", not pelanggar, pelanggar)
for fn in ("ownership_ladder.py", "webhooks.py", "worker_daemon.py", "run_local.py"):
    t = open(os.path.join(ROOT, "backend", fn), encoding="utf-8").read()
    check("E %s memakai _ns.context" % fn, "_ns.context()" in t)

print("== F. fetch HTTPS nyata lewat ownership_ladder ==")
import ownership_ladder as ol   # noqa: E402
r = ol.default_fetcher("https://example.com/", 8)
check("F default_fetcher HTTPS berstatus 200",
      isinstance(r, dict) and r.get("status") == 200 and not r.get("error"),
      {k: r.get(k) for k in ("status", "error")} if isinstance(r, dict) else r)
print("== E2. AST: netssl diimpor di level modul ==")
import ast as _ast
for _fn in ("ownership_ladder.py", "webhooks.py", "worker_daemon.py", "run_local.py"):
    _t = _ast.parse(open(os.path.join(ROOT, "backend", _fn), encoding="utf-8").read())
    _al = [(a.asname or a.name) for n in _t.body if isinstance(n, _ast.Import) for a in n.names]
    check("E2 AST netssl level modul: %s" % _fn, "_ns" in _al or "netssl" in _al, _al)



print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
