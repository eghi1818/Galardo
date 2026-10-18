#!/usr/bin/env python3
"""Verifier F-3/F-4: header keamanan + CORS terkonfigurasi (offline + boot nyata)."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:8090"
URL = BASE + "/api/v1/health"
DEVNULL = subprocess.DEVNULL
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


def head(url, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}


def boot(extra=None):
    subprocess.run(["make", "dev-down"], cwd=ROOT, stdout=DEVNULL, stderr=DEVNULL)
    env = dict(os.environ)
    env.update(extra or {})
    proc = subprocess.Popen(["make", "dev-up"], cwd=ROOT, env=env, stdout=DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(25):
        try:
            with urllib.request.urlopen(URL, timeout=3) as r:
                if r.status == 200:
                    break
        except Exception:
            pass
        time.sleep(1)
    return proc


src = open(os.path.join(ROOT, "backend", "api.py"), encoding="utf-8").read()

# A. bentuk sumber
check("A _cors_allow ada", "def _cors_allow(" in src)
check("A mode CORS dari env GALARDO_CORS_ORIGINS", 'CORS_ENV = "GALARDO_CORS_ORIGINS"' in src)
check("A origin tak terdaftar -> None (strict)", "else None" in src)
check("A Vary hanya saat mode bukan *", '_mode != "*"' in src)
check("A CSP terpasang pada HTML", 'send_header("Content-Security-Policy", CSP)' in src)
check("A header keamanan lengkap",
      all(h in src for h in ("X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options")))
check("A preflight OPTIONS balas 204", "def do_OPTIONS(self):" in src and "send_response(204)" in src)
_html = open(os.path.join(ROOT, "dashboard", "index.html"), encoding="utf-8").read()
check("A dashboard tanpa aset eksternal (CSP 'self' aman)", 'src="http' not in _html)

# B. default (tanpa env) -> "*" tanpa Vary
proc = boot()
try:
    st, h = head(URL)
    check("B health 200", st == 200, st)
    check("B ACAO default *", h.get("access-control-allow-origin") == "*", h.get("access-control-allow-origin"))
    check("B tanpa Vary saat mode *", "vary" not in h, h.get("vary"))
    check("B nosniff ada", h.get("x-content-type-options") == "nosniff", h.get("x-content-type-options"))
    check("B X-Frame-Options DENY", h.get("x-frame-options") == "DENY", h.get("x-frame-options"))
    check("B Referrer-Policy no-referrer", h.get("referrer-policy") == "no-referrer", h.get("referrer-policy"))
    st2, h2 = head(BASE + "/")
    csp = h2.get("content-security-policy", "")
    check("B dashboard punya CSP", "default-src 'self'" in csp, csp[:80])
    check("B CSP memblokir frame", "frame-ancestors 'none'" in csp, csp[:80])
    st3, h3 = head(URL, method="OPTIONS", headers={"Origin": "https://x.test"})
    check("B preflight 204", st3 == 204, st3)
    check("B preflight mengizinkan Authorization",
          "authorization" in h3.get("access-control-allow-headers", "").lower(),
          h3.get("access-control-allow-headers"))
finally:
    subprocess.run(["make", "dev-down"], cwd=ROOT, stdout=DEVNULL, stderr=DEVNULL)
    proc.wait(timeout=10)

# C. mode daftar -> echo untuk yang terdaftar, omit untuk yang tidak
proc = boot({"GALARDO_CORS_ORIGINS": "https://a.test,https://b.test"})
try:
    st, h = head(URL, headers={"Origin": "https://a.test"})
    check("C origin terdaftar di-echo", h.get("access-control-allow-origin") == "https://a.test",
          h.get("access-control-allow-origin"))
    check("C Vary: Origin ada", h.get("vary") == "Origin", h.get("vary"))
    st2, h2 = head(URL, headers={"Origin": "https://jahat.test"})
    check("C origin tak terdaftar diomit",
          h2.get("access-control-allow-origin") is None, h2.get("access-control-allow-origin"))
    check("C tetap ada Vary", h2.get("vary") == "Origin", h2.get("vary"))
finally:
    subprocess.run(["make", "dev-down"], cwd=ROOT, stdout=DEVNULL, stderr=DEVNULL)
    proc.wait(timeout=10)

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
