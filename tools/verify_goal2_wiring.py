#!/usr/bin/env python3
"""Uji: tidak ada penanda buster sisa + atribusi lapisan pada probe."""
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import external_probe as ep   # noqa: E402

PASS = 0
FAIL = 0
ALLOW = {"cachebuster.py", "verify_buster_unified.py", "verify_goal2_wiring.py"}


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


print("== A. tidak ada _gcb sisa di seluruh kode ==")
offenders = []
for sub in ("backend", "tools"):
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".py") or fn in ALLOW:
            continue
        txt = open(os.path.join(d, fn), encoding="utf-8").read()
        if "_gcb" in txt:
            offenders.append("%s/%s" % (sub, fn))
check("A tidak ada _gcb di luar allowlist", offenders == [], offenders)
check("A routeoverride memakai cachebuster",
      "cachebuster as _cb" in open(os.path.join(ROOT, "backend", "routeoverride.py"),
                                   encoding="utf-8").read())
check("A routeoverride tidak lagi menulis _gcb",
      "_gcb=" not in open(os.path.join(ROOT, "backend", "routeoverride.py"),
                          encoding="utf-8").read())

print("== B. atribusi lapisan dari hasil probe ==")
mk = lambda **kw: dict({"ok": False, "reason": None, "status": None, "error": None}, **kw)
check("B OK -> healthy", ep.attribute(mk(ok=True, reason="OK"))["layer"] == "healthy")
check("B DNS gagal -> dns", ep.attribute(mk(reason="DNS"))["layer"] == "dns")
check("B timeout tanpa CDN -> origin", ep.attribute(mk(reason="TIMEOUT"))["layer"] == "origin")
check("B timeout dengan CDN -> edge",
      ep.attribute(mk(reason="TIMEOUT"), cdn="cloudflare")["layer"] == "edge")
check("B CONN tanpa CDN -> origin", ep.attribute(mk(reason="CONN"))["layer"] == "origin")
check("B TLS dengan CDN -> edge",
      ep.attribute(mk(reason="TLS"), cdn="akamai")["layer"] == "edge")
check("B HTTP 503 tanpa CDN -> origin",
      ep.attribute(mk(reason="HTTP_STATUS", status=503))["layer"] == "origin")
check("B HTTP 503 dengan CDN -> edge",
      ep.attribute(mk(reason="HTTP_STATUS", status=503), cdn="cloudflare")["layer"] == "edge")
check("B HTTP 404 -> app", ep.attribute(mk(reason="HTTP_STATUS", status=404))["layer"] == "app")
check("B kontrol gagal -> ours", ep.attribute(mk(reason="TIMEOUT"), control_ok=False)["layer"] == "ours")
check("B CRASH -> tidak crash", isinstance(ep.attribute(mk(reason="CRASH"))["layer"], str))
check("B atribut ikut terbawa di dict",
      all(k in ep.attribute(mk(reason="DNS")) for k in
          ("layer", "layer_reason", "layer_confidence", "layer_hint")))

print("== C. probe_http live ==")
srv = ThreadingHTTPServer(("127.0.0.1", 0), type("S", (BaseHTTPRequestHandler,), {
    "log_message": lambda self, *a: None,
    "do_GET": lambda self: (self.send_response(200),
                            self.send_header("Content-Length", "2"),
                            self.end_headers(), self.wfile.write(b"ok"))}))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

r = ep.probe_http("http://127.0.0.1:%d/" % port, timeout=3)
check("C probe hidup -> ok", r["ok"] is True, r)
check("C probe hidup -> layer healthy", r.get("layer") == "healthy", r)

r = ep.probe_http("http://127.0.0.1:1/", timeout=2)
check("C port mati -> gagal", r["ok"] is False, r)
check("C port mati -> lapisan terisi", r.get("layer") in ("origin", "edge", "unknown"), r)

srv.shutdown()

print("== D. state machine membawa lapisan ==")
sm = ep.DownStateMachine(failure_threshold=2, min_down_seconds=0.0)
sm.on_sample(False, "CONN", "origin")
sm.on_sample(False, "CONN", "origin")
check("D state jadi SUSPECT", sm.state == "SUSPECT", sm.state)
check("D last_layer tercatat di evidence", sm.evidence().get("last_layer") == "origin",
      sm.evidence().get("last_layer"))

w = ep.DownWatcher("http://127.0.0.1:1/", interval=0.2, timeout=1,
                   failure_threshold=2, min_down_seconds=0.0)
w.start()
time.sleep(0.9)
w.stop()
time.sleep(0.2)
check("D watcher snapshot memuat last_layer", "last_layer" in w.snapshot(), list(w.snapshot())[:6])

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
