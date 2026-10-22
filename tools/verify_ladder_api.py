#!/usr/bin/env python3
"""Uji ujung-ke-ujung endpoint tangga kepemilikan lewat HTTP."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BACKEND = os.path.join(ROOT, "backend")
PORT = int(os.environ.get("GALARDO_LADDER_TEST_PORT", "8123"))
SITE = int(os.environ.get("GALARDO_LADDER_SITE_PORT", "8124"))
ORIGIN = "http://127.0.0.1:%d" % SITE

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


class Site(BaseHTTPRequestHandler):
    echo_header = False

    def log_message(self, *a):
        pass

    def _send(self, code, body, extra=None):
        self.send_response(code)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        pre = "/.well-known/galardo-"
        if p.startswith(pre) and p.endswith(".txt"):
            token = p[len(pre):-len(".txt")]
            return self._send(200, ("galardo-verify=usr-operator:%s" % token).encode(),
                              {"Content-Type": "text/plain"})
        body = b"<html><head></head><body>ok</body></html>"
        extra = {"X-Galardo-Verify": self.path.strip("/")} if Site.echo_header else {}
        return self._send(200, body, extra)


def api(method, path, body=None):
    url = "http://127.0.0.1:%d/api/v1%s" % (PORT, path)
    data = json.dumps(body).encode() if body is not None else None
    _h = {"Content-Type": "application/json"}
    try:
        _h["Authorization"] = "Bearer " + TOKEN
    except NameError:
        pass
    req = urllib.request.Request(url, data=data, method=method, headers=_h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


site = ThreadingHTTPServer(("127.0.0.1", SITE), Site)
threading.Thread(target=site.serve_forever, daemon=True).start()

def _token_dari_env():
    t = os.environ.get("GALARDO_DEV_TOKEN")
    if t:
        return t
    for d in (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.getcwd()):
        f = os.path.join(d, ".env")
        if os.path.isfile(f):
            for line in open(f):
                if line.strip().startswith("GALARDO_DEV_TOKEN="):
                    return line.strip().split("=", 1)[1].strip()
    return "dev-token"


env = dict(os.environ)
TOKEN = _token_dari_env()
env["GALARDO_DEV_TOKEN"] = TOKEN
os.environ["GALARDO_DEV_TOKEN"] = TOKEN
env["GALARDO_API_PORT"] = str(PORT)
proc = subprocess.Popen([sys.executable, "api.py", "--port", str(PORT)],
                        cwd=BACKEND, env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

up = False
for _ in range(60):
    try:
        st, _b = api("GET", "/health")
        if st == 200:
            up = True
            break
    except Exception:
        pass
    time.sleep(0.25)

try:
    check("server API hidup", up is True)
    if not up:
        raise SystemExit(1)

    api("POST", "/seed")
    st, eng = api("POST", "/engagements", {"name": "ladder-uji"})
    check("engagement dibuat", st == 201, (st, eng))
    api("POST", "/engagements/%s/approve" % eng["id"])

    st, tgt = api("POST", "/targets", {"engagement_id": eng["id"],
                                       "canonical_origin": ORIGIN,
                                       "name": "ladder-target"})
    check("target dibuat", st == 201, (st, tgt))
    tid = tgt["id"]

    print("== rung 2: well-known file ==")
    st, r1 = api("POST", "/targets/%s/verify/file" % tid, {"base_url": ORIGIN})
    check("issue challenge -> 201 + token", st == 201 and r1.get("token"), (st, r1))
    st, r2 = api("POST", "/targets/%s/verify/file" % tid, {"base_url": ORIGIN})
    check("token terpasang -> VERIFIED", st == 200 and r2.get("verified") is True, (st, r2))
    check("method dan level benar",
          r2.get("method") == "well_known_file" and r2.get("level") == 3, r2)
    check("attestasi ditandai BUKAN bukti di level 3",
          r2.get("is_proof") is True, r2)

    st, own = api("GET", "/targets/%s/ownership" % tid)
    check("ownership menunjukkan status VERIFIED", st == 200 and own.get("status") == "VERIFIED", (st, own))
    check("available_levels lengkap", own.get("available_levels") ==
          ["dns_txt", "well_known_file", "http_echo", "operator_attestation"], own.get("available_levels"))

    print("== fail-closed ==")
    st, r3 = api("POST", "/targets/%s/verify/attest" % tid, {"min_level": "well_known_file"})
    check("attestasi DITOLAK kalau min well_known_file", st == 422, (st, r3))
    st, own2 = api("GET", "/targets/%s/ownership" % tid)
    check("target turun jadi UNVERIFIED setelah ditolak",
          own2.get("status") == "UNVERIFIED", own2.get("status"))

    st, r4 = api("POST", "/targets/%s/verify/attest" % tid, {"min_level": "operator_attestation"})
    check("attestasi diterima kalau min attestation", st == 200, (st, r4))
    check("attestasi berlabel BUKAN bukti", r4.get("is_proof") is False, r4)
    check("attestasi punya masa berlaku", r4.get("expires_at") is not None, r4)

    print("== rung 3: http echo ==")
    Site.echo_header = False
    st, _ = api("POST", "/targets/%s/verify/echo" % tid, {"base_url": ORIGIN, "reset": True})
    check("issue echo challenge -> 201", st == 201, st)
    st, r5 = api("POST", "/targets/%s/verify/echo" % tid, {"base_url": ORIGIN})
    check("tanpa token di header -> 422 (fail-closed)", st == 422, (st, r5))

    st, r6 = api("POST", "/targets/%s/verify/file" % tid, {"base_url": ORIGIN, "reset": True})
    st, r7 = api("POST", "/targets/%s/verify/file" % tid, {"base_url": ORIGIN})
    check("kembali ke file -> VERIFIED", st == 200 and r7.get("verified") is True, (st, r7))

    print("== min_level asing ==")
    st, r8 = api("POST", "/targets/%s/verify/file" % tid, {"min_level": "tidak_ada"})
    check("min_level asing -> 422", st == 422, (st, r8))

finally:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        pass
    site.shutdown()

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
