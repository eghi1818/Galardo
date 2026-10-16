#!/usr/bin/env python3
"""Pastikan HANYA SATU penanda cache buster di seluruh repo."""
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import cachebuster as cb        # noqa: E402
import external_probe as ep     # noqa: E402

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


def keys_of(url):
    return [k for k, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)]


print("== A. penanda kanonik ==")
check("A BUSTER_KEY adalah __gb", cb.BUSTER_KEY == "__gb", cb.BUSTER_KEY)
u, v = cb.decorate("https://a.test/p")
check("A decorate pakai __gb", keys_of(u) == ["__gb"] and v, u)

print("== B. external_probe ikut kanonik ==")
u2 = ep.cache_buster_path("https://a.test/p")
check("B probe pakai __gb", "__gb=" in u2, u2)
check("B probe TIDAK pakai _gcb", "_gcb" not in u2, u2)
check("B query lama dipertahankan", "__gb=" in ep.cache_buster_path("https://a.test/p?x=1")
      and "x=1" in ep.cache_buster_path("https://a.test/p?x=1"), "")
t1 = ep.cache_buster_token()
t2 = ep.cache_buster_token()
check("B token probe unik", t1 != t2, (t1, t2))
check("B token bisa dipaksa", "ZZZ" in ep.cache_buster_path("https://a.test/p", token="ZZZ"),
      ep.cache_buster_path("https://a.test/p", token="ZZZ"))

print("== C. penanda lama tetap dikenali ==")
legacy = "https://a.test/p?_gcb=old"
check("C is_decorated mengenali _gcb", cb.is_decorated(legacy) is True, legacy)
back, found = cb.strip(legacy)
check("C strip membuang _gcb", not cb.is_decorated(back) and "_gcb" not in back, back)
check("C strip mengembalikan url bersih", back == "https://a.test/p", back)
both = "https://a.test/p?__gb=new&_gcb=old&z=9"
back2, _ = cb.strip(both)
check("C strip membuang keduanya, sisakan yang lain", back2 == "https://a.test/p?z=9", back2)
check("C LEGACY_KEYS terdaftar", "_gcb" in cb.LEGACY_KEYS, cb.LEGACY_KEYS)

print("== D. tidak ada urlencode(_gcb) tersisa di sumber ==")
src = open(os.path.join(ROOT, "backend", "external_probe.py"), encoding="utf-8").read()
check("D external_probe tidak menulis _gcb sendiri",
      'urlencode({"_gcb"' not in src, "masih ada urlencode({'_gcb'")
check("D external_probe memakai cachebuster", "cachebuster as _cb" in src, "import hilang")

print("== E. probe hidup: nonce sampai ke server ==")
seen = []


class S(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        seen.append(self.path)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


srv = ThreadingHTTPServer(("127.0.0.1", 0), S)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

p = ep.ExternalProbe("http://127.0.0.1:%d/healthz" % port, interval=0.25, timeout=2.0)
p.start()
time.sleep(1.4)
p.stop.set()
time.sleep(0.4)
srv.shutdown()

check("E probe mengirim request", len(seen) >= 2, len(seen))
check("E semua request membawa __gb=", seen and all("__gb=" in s for s in seen), seen[:3])
check("E tidak ada _gcb di request", all("_gcb" not in s for s in seen), seen[:3])
check("E nonce berbeda tiap request", len(set(seen)) == len(seen), seen[:3])

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
