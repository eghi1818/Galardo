#!/usr/bin/env python3
"""Uji cache buster + deteksi cache HIT. Stdlib only."""
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import cachebuster as cb   # noqa: E402

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


print("== A. dekorasi URL ==")
u, v = cb.decorate("https://contoh.test/api/heavy")
check("A param buster ditambahkan", cb.is_decorated(u) and v, u)
check("A nonce masuk ke query", ("%s=%s" % (cb.BUSTER_KEY, v)) in u, u)
u2, v2 = cb.decorate("https://contoh.test/a?x=1&y=2")
check("A query lama dipertahankan", "x=1" in u2 and "y=2" in u2, u2)
check("A fragment dipertahankan",
      cb.decorate("https://contoh.test/p#frag")[0].endswith("#frag"), "")
u3, _ = cb.decorate("https://contoh.test/p?a=1")
u3b, _ = cb.decorate(u3)
check("A tidak menumpuk buster dobel",
      sum(1 for k, _ in __import__("urllib.parse", fromlist=["parse_qsl"])
          .parse_qsl(__import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(u3b).query)
          if k == cb.BUSTER_KEY) == 1, u3b)
back, got = cb.strip(u3b)
check("A strip membalikkan dekorasi", not cb.is_decorated(back) and got, back)
check("A is_decorated false untuk url bersih", cb.is_decorated("https://a.test/p") is False)
check("A url bersih utuh setelah strip",
      cb.strip("https://a.test/p?k=1")[0] == "https://a.test/p?k=1",
      cb.strip("https://a.test/p?k=1")[0])

print("== B. nonce ==")
vals = set(cb.random_nonce() for _ in range(2000))
check("B 2000 nonce unik", len(vals) == 2000, len(vals))
check("B counter_nonce deterministik",
      cb.counter_nonce("r1", 7) == cb.counter_nonce("r1", 7))
check("B counter_nonce beda antar seq",
      cb.counter_nonce("r1", 7) != cb.counter_nonce("r1", 8))

print("== C. klasifikasi cache ==")
check("C cf HIT", cb.cache_verdict({"cf-cache-status": "HIT"})["verdict"] == "HIT")
check("C cf MISS", cb.cache_verdict({"cf-cache-status": "MISS"})["verdict"] == "MISS")
check("C cf DYNAMIC -> MISS",
      cb.cache_verdict({"cf-cache-status": "DYNAMIC"})["verdict"] == "MISS")
check("C x-cache Hit cloudfront",
      cb.cache_verdict({"x-cache": "Hit from cloudfront"})["verdict"] == "HIT")
check("C x-cache Miss cloudfront",
      cb.cache_verdict({"x-cache": "Miss from cloudfront"})["verdict"] == "MISS")
check("C akamai TCP_HIT",
      cb.cache_verdict({"akamai-cache-status": "TCP_HIT"})["verdict"] == "HIT")
check("C age>0 -> HIT_AGE",
      cb.cache_verdict({"age": "42"})["verdict"] == "HIT_AGE")
check("C tanpa header -> UNKNOWN",
      cb.cache_verdict({})["verdict"] == "UNKNOWN")
check("C deteksi cloudflare via cf-ray",
      cb.detect_cdn({"cf-ray": "abc"}) == "cloudflare")
check("C deteksi akamai via server",
      cb.detect_cdn({"server": "AkamaiGHost"}) == "akamai")
check("C deteksi cloudfront via x-amz-cf-id",
      cb.detect_cdn({"x-amz-cf-id": "x"}) == "cloudfront")

print("== D. pierce_ok ==")
check("D HIT -> bukan pierce", cb.pierce_ok({"cf-cache-status": "HIT"}) is False)
check("D MISS -> pierce", cb.pierce_ok({"cf-cache-status": "MISS"}) is True)
check("D tanpa penanda -> dianggap pierce",
      cb.pierce_ok({}) is True)

print("== E. Piercer ==")
p = cb.Piercer(run_id="rtest")
u, n1 = p.decorate("https://a.test/p")
u, n2 = p.decorate("https://a.test/p")
check("E nonce per-request berbeda", n1 != n2, (n1, n2))
check("E run_id terbawa di nonce", n1.startswith("rtest-"), n1)
p.observe({"cf-cache-status": "MISS"}, url=u)
p.observe({"cf-cache-status": "MISS"}, url=u)
p.observe({"cf-cache-status": "HIT"}, url=u)
s = p.stats()
check("E hit/miss tercatat", s["hits"] == 1 and s["misses"] == 2, s)
check("E hit_ratio benar", s["hit_ratio"] == round(1 / 3.0, 4), s["hit_ratio"])
check("E verdict sebagian_kena_cache", s["verdict"] == "sebagian_kena_cache", s["verdict"])
check("E sampel HIT tersimpan", len(s["hit_samples"]) == 1, s["hit_samples"])
p2 = cb.Piercer(run_id="roff", enabled=False)
u_off, n_off = p2.decorate("https://a.test/p")
check("E disabled -> url tidak diubah", u_off == "https://a.test/p" and n_off is None, u_off)
p3 = cb.Piercer(run_id="rallhit")
p3.observe({"cf-cache-status": "HIT"})
check("E semua HIT -> cache_diabaikan", p3.stats()["verdict"] == "cache_diabaikan",
      p3.stats()["verdict"])

print("== F. uji hidup lewat server lokal ==")
seen = []


class S(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        seen.append(self.path)
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


srv = ThreadingHTTPServer(("127.0.0.1", 0), S)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

import urllib.request  # noqa: E402
live = cb.Piercer(run_id="rlive")
for i in range(3):
    url, _n = live.decorate("http://127.0.0.1:%d/api/heavy" % port, seq=i)
    with urllib.request.urlopen(url, timeout=5) as r:
        r.read()
check("F 3 request sampai ke server", len(seen) == 3, seen)
check("F server melihat param buster di semua request",
      all(cb.BUSTER_KEY in p for p in seen), seen)
check("F ketiga query unik", len(set(seen)) == 3, seen)
srv.shutdown()

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
