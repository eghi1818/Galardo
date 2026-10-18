#!/usr/bin/env python3
"""Verifier integrasi tool eksternal: parser, fail-open, batas waktu, live traceroute."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import exttool as xt  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


# A. registry & status
check("A registry memuat 3 tool", set(xt.TOOLS) == {"subfinder", "nikto", "traceroute"}, sorted(xt.TOOLS))
st = xt.status()
check("A status melaporkan available boolean",
      all(isinstance(v.get("available"), bool) for k, v in st.items() if not k.startswith("_")), st)
check("A status punya timeout default", isinstance(st.get("_timeout_default"), float), st.get("_timeout_default"))

# B. parser
tr = """traceroute to 127.0.0.1 (127.0.0.1), 64 hops max, 52 byte packets
 1  localhost (127.0.0.1)  0.064 ms  0.052 ms  0.048 ms
 2  10.0.0.1 (10.0.0.1)  1.204 ms  1.100 ms  1.050 ms
"""
p = xt.parse("traceroute", tr)
check("B parser traceroute: 2 hop", p.get("count") == 2, p)
check("B parser traceroute: host & rtt", p["hops"][1]["host"] == "10.0.0.1" and p["hops"][1]["rtt_ms"][0] == 1.204, p["hops"][1])

sf = """[INF] loading provider config
a.koler.space
b.koler.space

c.koler.space
"""
p2 = xt.parse("subfinder", sf)
check("B parser subfinder: 3 subdomain", p2.get("count") == 3, p2)

nk = """- Nikto v2.5.0
+ Target IP: 127.0.0.1
+ Target Port: 80
+ Server: nginx
+ /admin: Terdapat 404
"""
p3 = xt.parse("nikto", nk)
check("B parser nikto: 4 temuan", p3.get("count") == 4, p3)

# C. fail-open: biner tak ada
asli_which = xt.shutil.which
try:
    xt.shutil.which = lambda b: None
    r = xt.run("subfinder", target="koler.space")
    check("C tool hilang -> ok False, available False", r["ok"] is False and r["available"] is False, r)
    check("C alasan menyebut PATH", "PATH" in r.get("reason", ""), r.get("reason"))
finally:
    xt.shutil.which = asli_which

# D. tool tak dikenal
r2 = xt.run("tidak-ada")
check("D tool tak dikenal -> daftar tersedia", r2["ok"] is False and "tersedia" in r2, r2)

# E. batas waktu (pakai python3 sebagai biner palsu)
try:
    xt.TOOLS["_tidur"] = {"bin": "python3", "goal": "uji", "desc": "tidur", "butuh": "-"}
    r3 = xt.run("_tidur", args=["-c", "import time; time.sleep(3)"], timeout=1.0)
    check("E timeout dipatuhi", r3["ok"] is False and "timeout" in r3.get("reason", ""), r3.get("reason"))
    check("E elapsed dekat timeout", r3.get("elapsed", 9) < 2.5, r3.get("elapsed"))
    r4 = xt.run("_tidur", args=["-c", "print('halo')"], timeout=10.0)
    check("E sukses normal -> ok True + output", r4["ok"] is True and "halo" in r4.get("output", ""), r4.get("rc"))
finally:
    xt.TOOLS.pop("_tidur", None)

# F. live: traceroute ke loopback (bila biner ada)
if xt.tersedia("traceroute"):
    t0 = time.time()
    r5 = xt.run("traceroute", args=["-n", "-m", "3"], target="127.0.0.1", timeout=15.0)
    check("F live traceroute ok", r5.get("ok") is True, r5.get("reason"))
    check("F live traceroute ada hop", r5.get("parsed", {}).get("count", 0) >= 1, r5.get("parsed"))
    check("F live traceroute tidak menggantung", time.time() - t0 < 16, round(time.time() - t0, 2))
else:
    check("F live traceroute (biner tak ada -> dilewati)", True, "traceroute tak ada")

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
