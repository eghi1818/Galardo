#!/usr/bin/env python3
"""Verifier pengunci item 2/3 (lane proxy) + item 4 (label lane evidence).

Offline: pool di-register in-memory, ConnectionPool transport diganti stub.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import proxypool
import proxy as lanes
import transport as T

PASS, FAIL = [], []


def check(nama, ok, detail=""):
    (PASS if ok else FAIL).append(nama)
    print(("  ok   " if ok else "  FAIL ") + nama +
          (("  | " + str(detail)) if detail and not ok else ""))


class FakeRaw(object):
    def __init__(self, body=b"ok"):
        self.status, self.reason, self.version, self.will_close = 200, "OK", 11, False
        self._body = body

    def read(self, n):
        return self._body

    def getheaders(self):
        return [("Content-Length", str(len(self._body)))]


class FakeConn(object):
    def request(self, method, path, body=None, headers=None):
        self.seen = (method, path)

    def getresponse(self):
        return FakeRaw()

    def close(self):
        pass


class FakePool(object):
    def __init__(self):
        self.keys = []

    def acquire(self, scheme, host, port, connect_ip, proxy, timeout):
        self.keys.append((scheme, host, port, connect_ip, proxy))
        return FakeConn(), False

    def release(self, key, conn):
        pass

    def close_all(self):
        pass


class FakeResp(object):
    def __init__(self, status=200, sent=10, recv=20, err=None):
        self.status, self.bytes_sent, self.bytes_received = status, sent, recv
        self.elapsed_ms, self.error = 5.0, err


def transport_baru():
    tr = T.Transport()
    tr._pool = FakePool()
    return tr


print("A. default direct, rotasi opt-in")
check("konstanta lane", (lanes.DIRECT, lanes.ROTATE, lanes.RESIDENTIAL) ==
      ("direct", "rotate", "residential"))
reg = lanes.LaneRegistry()
check("mode awal direct", reg.mode == "direct")
check("hanya lane direct terdaftar", reg.lanes() == ["direct"])
lane0 = reg.current()
check("lane direct tanpa endpoint", lane0.endpoint() is None)
check("evidence direct", lane0.evidence()["egress"] == "direct")
try:
    reg.set_mode("rotate")
    check("set_mode rotate tanpa lane -> LaneError", False)
except lanes.LaneError:
    check("set_mode rotate tanpa lane -> LaneError", True)
try:
    reg.set_mode("ngawur")
    check("mode tidak dikenal -> LaneError", False)
except lanes.LaneError:
    check("mode tidak dikenal -> LaneError", True)

print("B. rotasi opt-in dan fail-open tanpa kredensial")
proxypool.register("pool-uji", "user:pass@127.0.0.1:8080")
check("resolve pool-uji", proxypool.resolve("pool-uji") == ("127.0.0.1", 8080))
check("credentials pool-uji", proxypool.credentials("pool-uji") == ("user", "pass"))
reg.add_lane("rotate", "rotate", pool="pool-uji")
check("set_mode rotate", reg.set_mode("rotate") == "rotate")
lr = reg.get("rotate")
check("endpoint lane rotate", lr.endpoint() == ("127.0.0.1", 8080))
check("evidence lane rotate egress proxy", lr.evidence()["egress"] == "proxy")
check("evidence lane rotate menyebut proxy", lr.evidence()["proxy"] == "127.0.0.1:8080")
reg.add_lane("belum-diisi", "rotate", pool="pool-kosong")
check("pool kosong -> endpoint None", reg.get("belum-diisi").endpoint() is None)
check("pool kosong -> egress direct (fail-open)",
      reg.get("belum-diisi").evidence()["egress"] == "direct")
try:
    reg.get("tidak-ada")
    check("lane tidak ada -> LaneError", False)
except lanes.LaneError:
    check("lane tidak ada -> LaneError", True)

print("C. statistik lane terpisah dari statistik target")
lr.record(FakeResp(sent=10, recv=20))
lr.record(FakeResp(sent=30, recv=40, err="boom"))
st = lr.stats()
check("counter lane requests", st["requests"] == 2)
check("counter lane errors", st["errors"] == 1)
check("counter lane bytes", (st["bytes_sent"], st["bytes_received"]) == (40, 60))
check("lane direct tetap nol", reg.get("direct").stats()["requests"] == 0)
target = {"requests": 99, "bytes_sent": 1}
ss = reg.status(target=target)
check("status memisah lanes dan target", "lanes" in ss and ss["target"] == target)
check("statistik target tidak bercampur", ss["lanes"]["direct"]["requests"] == 0)
check("lane stats punya penanda lane", "kind" in st and "id" in st)
check("transport stats tidak punya penanda lane",
      "kind" not in T.Transport().stats())

print("D. label lane evidence pada respons Transport")
try:
    tr = transport_baru()
    lanes.attach(tr, reg)
    reg.set_mode("direct")
    r = tr.request("GET", "http://contoh.test/")
    check("respons punya label lane", getattr(r, "lane", None) is not None)
    check("label lane direct benar", r.lane["lane_id"] == "direct")
    check("label lane direct egress", r.lane["egress"] == "direct")
    check("counter lane direct bertambah", reg.get("direct").stats()["requests"] == 1)
    reg.set_mode("rotate")
    r2 = tr.request("GET", "http://contoh.test/")
    check("label lane rotate benar", r2.lane["lane_kind"] == "rotate")
    check("label lane rotate egress proxy", r2.lane["egress"] == "proxy")
    check("proxy dipakai di dial", tr._pool.keys[-1][4] == ("127.0.0.1", 8080))
    r3 = tr.request("GET", "http://contoh.test/", proxy=("10.0.0.9", 3128))
    check("proxy ad-hoc dilabeli", r3.lane["lane_kind"] == "adhoc")
    check("proxy ad-hoc egress", r3.lane["egress"] == "proxy")
    r4 = tr.request("GET", "http://contoh.test/", proxy=("10.0.0.9", 3128))
    check("proxy eksplisit menang atas mode lane",
          tr._pool.keys[-1][4] == ("10.0.0.9", 3128))
    tr2 = transport_baru()
    check("transport tanpa registry tidak dilabeli",
          getattr(tr2.request("GET", "http://contoh.test/"), "lane", None) is None)
except Exception as exc:
    check("bagian D tidak meledak", False, "%s: %s" % (type(exc).__name__, exc))

print("E. keep-alive tidak diputus di mode direct")
tr3 = transport_baru()
lanes.attach(tr3, lanes.LaneRegistry())
tr3.request("GET", "http://contoh.test/")
tr3.request("GET", "http://contoh.test/")
check("kunci cache identik di mode direct", tr3._pool.keys[0] == tr3._pool.keys[1])
check("mode direct tanpa proxy", tr3._pool.keys[-1][4] is None)
reg.set_mode("rotate")
tr.request("GET", "http://contoh.test/")
check("mode rotate memakai proxy (kunci beda)",
      tr._pool.keys[-1][4] == ("127.0.0.1", 8080) and tr._pool.keys[-1] != tr._pool.keys[-2])

print("F. jalur ter-wire")
src_t = open(os.path.join(ROOT, "backend", "transport.py")).read()
src_a = open(os.path.join(ROOT, "backend", "api.py")).read()
src_m = open(os.path.join(ROOT, "Makefile")).read()
check("transport punya hook _label_lane", "_label_lane" in src_t)
check("transport punya atribut lanes", "self.lanes" in src_t)
check("api punya endpoint /lanes", 'api_path == "/lanes"' in src_a)
check("api punya endpoint /lanes/mode", 'api_path == "/lanes/mode"' in src_a)
check("api mengimpor modul lane", "import proxy as proxy_lanes" in src_a)
check("Makefile memuat verifier lane", "verify_lane_proxy" in src_m)
check("proxy punya REGISTRY", isinstance(lanes.REGISTRY, lanes.LaneRegistry))
check("proxy punya send() dan attach()", callable(lanes.send) and callable(lanes.attach))
check("status() melaporkan mode", lanes.status()["mode"] in lanes.MODES)

check("Response punya slot lane", "lane" in T.Response.__slots__)

print("")
print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
