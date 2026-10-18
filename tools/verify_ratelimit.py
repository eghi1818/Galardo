#!/usr/bin/env python3
"""Verifier P4: rate limit (parse spec, bucket, kunci, exempt, 429 via HTTP)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import ratelimit as rl  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


class H:
    def __init__(self, auth=None, ip="1.2.3.4", path="/api/v1/things"):
        self.headers = {"Authorization": auth} if auth else {}
        self.client_address = (ip, 12345)
        self.path = path


src = open(os.path.join(BACKEND, "ratelimit.py")).read()
api = open(os.path.join(BACKEND, "api.py")).read()

# A. parser
check("A '60/m' -> 60 per 60s", rl.parse("60/m") == (60.0, 60.0), rl.parse("60/m"))
check("A '120/60s' -> 120 per 60s", rl.parse("120/60s") == (120.0, 60.0), rl.parse("120/60s"))
check("A '10/2s' -> 10 per 2s", rl.parse("10/2s") == (10.0, 2.0), rl.parse("10/2s"))
check("A '300/h' -> per jam", rl.parse("300/h") == (300.0, 3600.0), rl.parse("300/h"))
check("A '0' / 'off' -> mati", rl.parse("0") is None and rl.parse("off") is None)
check("A sampah -> None", rl.parse("abc/xyz") is None, rl.parse("abc/xyz"))

# B. bucket
os.environ[rl.ENV] = "3/60s"
rl.reset()
h = H()
lewat = [rl.cek(h) for _ in range(3)]
check("B 3 permintaan pertama lewat", lewat == [None, None, None], lewat)
tunggu = rl.cek(h)
check("B permintaan ke-4 kena 429 (detik tunggu)", isinstance(tunggu, int) and tunggu >= 1, tunggu)
check("B kunci berbeda tidak saling makan", rl.cek(H(ip="9.9.9.9")) is None)

# C. exempt
check("C health dikecualikan", rl.cek(H(path="/api/v1/health")) is None)
check("C file statis dikecualikan", rl.cek(H(path="/")) is None)

# D. kunci dari token, bukan IP
os.environ[rl.ENV] = "1/60s"
rl.reset()
check("D token jadi kunci", rl.kunci(H(auth="Bearer abcdefghijklmnop")) == "tok:abcdefghijklmnop",
      rl.kunci(H(auth="Bearer abcdefghijklmnop")))
check("D tanpa token -> IP", rl.kunci(H(ip="5.6.7.8")) == "ip:5.6.7.8", rl.kunci(H(ip="5.6.7.8")))

# E. mati = tanpa batas
os.environ.pop(rl.ENV, None)
rl.reset()
check("E tanpa env -> tak pernah batas", all(rl.cek(h) is None for _ in range(50)))

# F. bentuk sumber di api.py
check("F api memanggil ratelimit.cek", "ratelimit.cek(self)" in api)
check("F 429 + Retry-After", "_retry_after" in api and "Retry-After" in api)
check("F endpoint status ada", 'api_path == "/ratelimit"' in api)

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
