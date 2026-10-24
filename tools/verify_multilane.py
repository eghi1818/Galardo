#!/usr/bin/env python3
"""Verifier behavioral multi-lane engine. Target: http.server lokal (tanpa jaringan luar).

PELAJARAN STEP-167: TelemetryRing.window(N) dihitung relatif ke jam dinding SAAT DIPANGGIL,
sedangkan run() punya ekor wind-down (duration_actual > durasi uji). Karena ring dibuat per-run,
jendela diperbesar (WINDOW_PENUH) supaya seluruh sampel run terbaca - bukan angka palsu 0.
Cek pelayanan juga diverifikasi lewat log _do_request (tidak bergantung jam).
"""
import inspect
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import engine as E  # noqa: E402

PASS = 0
FAIL = 0
WINDOW_PENUH = 120.0


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


class FakeLane:
    def __init__(self, lid, ep=None):
        self.lane_id = lid
        self._ep = ep

    def endpoint(self):
        return self._ep


class FakeResp:
    status = 200
    error = None
    bytes_sent = 1
    bytes_received = 1
    headers = {}


class FakeTr:
    def __init__(self):
        self.dipanggil = 0

    def request(self, *a, **kw):
        self.dipanggil += 1
        return FakeResp()


def serve():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "127.0.0.1", port


def norm(vus=4, detik=1.5):
    return {"requests": [{"name": "r", "method": "GET", "path": "/", "weight": 1, "timeout_ms": 2000}],
            "total_weight": 1, "profile": {"virtual_users": vus, "duration_seconds": detik},
            "think_time_ms": {"min": 0, "max": 0}, "keep_alive": True, "cache_buster": False}


def jalankan(origin, lanes=None, vus=4, detik=1.5, instrumen=False):
    tel = E.TelemetryRing()
    eng = E.LoadEngine("job-v", "run-v", origin, norm(vus, detik),
                       {"max_vus": vus, "max_rps": None, "max_duration_sec": detik},
                       tel, lambda: (False, ""), lanes=lanes)
    log = []
    if instrumen:
        asli = eng._do_request

        def bungkus(req, tr=None):
            log.append("masuk")
            try:
                r = asli(req, tr)
                log.append("ok")
                return r
            except BaseException as exc:
                log.append("EXC %r" % (exc,))
                raise

        eng._do_request = bungkus
    hasil = eng.run()
    return eng, hasil, tel, log


def ada_pair(obj, pair):
    for v in vars(obj).values():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            try:
                if str(v[0]) == str(pair[0]) and int(v[1]) == int(pair[1]):
                    return True
            except Exception:
                pass
        if isinstance(v, dict) and str(v.get("host")) == str(pair[0]):
            try:
                if int(v.get("port", 0)) == int(pair[1]):
                    return True
            except Exception:
                pass
        if isinstance(v, str) and str(pair[0]) in v and str(pair[1]) in v:
            return True
    return False


def main():
    print("== verify_multilane (behavioral, target lokal) ==")
    cek("LoadEngine.__init__ menerima lanes",
        "lanes" in inspect.signature(E.LoadEngine.__init__).parameters)

    srv, host, port = serve()
    origin = "http://%s:%d" % (host, port)
    try:
        eng0, h0, tel0, _ = jalankan(origin, lanes=None)
        w0 = tel0.window(WINDOW_PENUH)
        cek("tanpa lane: hasil['lanes'] is None", h0.get("lanes") is None, repr(h0.get("lanes")))
        cek("tanpa lane: tidak ada transport lane", len(eng0.vu_transports) == 0, repr(len(eng0.vu_transports)))
        cek("tanpa lane: melayani (window penuh)", w0["requests"] > 0, repr(w0["requests"]))
        cek("tanpa lane: VU tidak mati sunyi", h0.get("vu_errors") == [], repr(h0.get("vu_errors")))

        eng1, h1, tel1, log1 = jalankan(origin, lanes=[FakeLane("L1"), FakeLane("L2")], instrumen=True)
        w1 = tel1.window(WINDOW_PENUH)
        hits = (h1.get("lanes") or {}).get("hits") or {}
        cek("2 lane: hasil melaporkan lanes", h1.get("lanes") is not None)
        cek("2 lane: KEDUA lane kebagian VU (round-robin)", set(hits.keys()) == {"L1", "L2"}, repr(hits))
        cek("2 lane: hits > 0 di kedua lane", all(v > 0 for v in hits.values()), repr(hits))
        cek("2 lane: satu transport per lane", len(eng1.vu_transports) == 2, repr(list(eng1.vu_transports)))
        cek("2 lane: _do_request terpanggil (log)", log1.count("masuk") > 0, repr(log1.count("masuk")))
        cek("2 lane: melayani (window penuh)", w1["requests"] > 0, repr(w1["requests"]))
        cek("2 lane: tanpa exception VU", h1.get("vu_errors") == [] and "EXC" not in log1, repr(h1.get("vu_errors")))
        cek("2 lane: transport lane siap dipakai",
            all(hasattr(t, "request") for t in eng1.vu_transports.values()))

        ep = (host, port)
        eng2, h2, tel2, _ = jalankan(origin, lanes=[FakeLane("P1", ep=ep)])
        w2 = tel2.window(WINDOW_PENUH)
        tr2 = eng2.vu_transports.get("P1")
        cek("lane ber-endpoint: transport lane dibuat", tr2 is not None)
        cek("lane ber-endpoint: set_proxy terbukti dipanggil dgn endpoint lane",
            tr2 is not None and ada_pair(tr2, ep), repr(vars(tr2) if tr2 else None)[:200])
        cek("lane ber-endpoint: melayani", w2["requests"] > 0, repr(w2["requests"]))
        cek("lane ber-endpoint: stats() tetap bisa dipanggil",
            tr2 is not None and callable(getattr(tr2, "stats", None)))

        cek("_lane_endpoint: objek lane", E.LoadEngine._lane_endpoint(FakeLane("x", ep)) == ep)
        cek("_lane_endpoint: dict", E.LoadEngine._lane_endpoint({"host": "h", "port": 9}) == ("h", 9))
        cek("_lane_endpoint: tuple", E.LoadEngine._lane_endpoint(("h2", 8)) == ("h2", 8))
        cek("_lane_endpoint: None -> None", E.LoadEngine._lane_endpoint(None) is None)
        cek("_lane_id: fallback objek tanpa id", E.LoadEngine._lane_id(object(), "lax") == "lax")

        tel = E.TelemetryRing()
        eng3 = E.LoadEngine("job-f", "run-f", origin, norm(), {"max_vus": 1}, tel, lambda: (False, ""))
        tr_asli = FakeTr()
        tr_lane = FakeTr()
        eng3.transport = tr_asli
        eng3._do_request({"name": "r", "method": "GET", "path": "/", "weight": 1, "timeout_ms": 1000}, tr_lane)
        cek("_do_request(req, tr): memakai tr yang diberikan",
            tr_lane.dipanggil == 1 and tr_asli.dipanggil == 0,
            repr((tr_lane.dipanggil, tr_asli.dipanggil)))
    finally:
        srv.shutdown()

    print()
    if FAIL:
        print("  [MERAH] verify_multilane: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_multilane: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
