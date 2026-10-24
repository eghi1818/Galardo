#!/usr/bin/env python3
"""Verifier behavioral backend/capacity.py - target HTTP dibuat sendiri (tanpa app, tanpa internet)."""
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import capacity as C  # noqa: E402

PASS = 0
FAIL = 0


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
        if self.path.startswith("/slow"):
            import time as _t
            _t.sleep(0.05)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def serve():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, "http://127.0.0.1:%d" % port


def main():
    print("== verify_capacity (behavioral, target lokal) ==")
    srv, base = serve()
    try:
        h = C.run(base + "/", steps=[1, 2, 4], detik=0.6, timeout=3)
        cek("run() mengembalikan 3 step", len(h["steps"]) == 3, repr(len(h["steps"])))
        s0 = h["steps"][0]
        for kunci in ("konkurensi", "total", "ok", "err", "rps", "err_rate", "p50", "p95", "kode"):
            cek("step punya kunci %s" % kunci, kunci in s0, repr(sorted(s0.keys())))
        cek("target lokal terlayani (ok > 0)", s0["ok"] > 0, repr(s0))
        cek("total == ok + err", all(x["total"] == x["ok"] + x["err"] for x in h["steps"]))
        cek("rps > 0 pada step pertama", s0["rps"] > 0, repr(s0["rps"]))
        cek("p95 ada dan >= p50", s0["p95"] is not None and s0["p50"] is not None and s0["p95"] >= s0["p50"],
            repr((s0["p50"], s0["p95"])))
        cek("knee() mengembalikan dict berindex", isinstance(h["knee"].get("index", "x"), (int, type(None))))
        cek("ttr() mengembalikan detik_degradasi", "detik_degradasi" in h["ttr"])
        cek("ringkasan punya max_rps", "max_rps" in h["ringkasan"])
        cek("ringkas_teks memuat kata knee", "knee" in C.ringkas_teks(h))

        hs = C.run(base + "/slow", steps=[2, 4], detik=0.6, timeout=3)
        cek("target lambat tetap terukur (tidak crash)", all(x["total"] > 0 for x in hs["steps"]), repr(hs["steps"]))

        srv2, base2 = serve()
        srv2.shutdown()
        hmati = C.run(base2 + "/", steps=[1], detik=0.4, timeout=1)
        cek("target mati: err_rate = 1.0, tidak crash",
            hmati["steps"][0]["err_rate"] == 1.0 and hmati["steps"][0]["ok"] == 0,
            repr(hmati["steps"][0]))

        cek("describe() menyebut ambang + prinsip", "ambang_p95" in C.describe() and "knee" in C.describe()["prinsip"])
    finally:
        srv.shutdown()

    print()
    if FAIL:
        print("  [MERAH] verify_capacity: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_capacity: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
