#!/usr/bin/env python3
"""Uji knee_probe + sambungan ke preflight. Ada server lokal + fetcher palsu."""
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import knee          # noqa: E402
import knee_probe    # noqa: E402

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


class S(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


srv = ThreadingHTTPServer(("127.0.0.1", 0), S)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
ORIGIN = "http://127.0.0.1:%d" % port

print("== A. measure ke server hidup ==")
r = knee_probe.measure(ORIGIN, steps=(2, 4, 8), step_seconds=0.6, timeout=2)
check("A 3 sampel", len(r["samples"]) == 3, len(r["samples"]))
check("A rps > 0 di semua langkah", all(s["rps"] > 0 for s in r["samples"]), r["samples"])
check("A ok > 0", all(s["ok"] > 0 for s in r["samples"]), r["samples"])
check("A p95 terisi", all(s["p95_ms"] >= 0 for s in r["samples"]), r["samples"])
check("A url memakai cache-buster", "__gb=" in r["url"], r["url"])
check("A vus menaik", [s["vus"] for s in r["samples"]] == [2, 4, 8], [s["vus"] for s in r["samples"]])
check("A ok_rps terisi dan > 0", all(s.get("ok_rps", 0) > 0 for s in r["samples"]),
      [s.get("ok_rps") for s in r["samples"]])
check("A ok_rps <= rps", all(s["ok_rps"] <= s["rps"] for s in r["samples"]), r["samples"])

print("== B. measure ke port mati ==")
r = knee_probe.measure("http://127.0.0.1:1", steps=(2, 4), step_seconds=0.5, timeout=1)
check("B ok_rps 0 semua (tidak ada yang berhasil)",
      all(s["ok_rps"] == 0 for s in r["samples"]), r["samples"])
check("B ok 0 semua", all(s["ok"] == 0 for s in r["samples"]), r["samples"])
check("B errors > 0", all(s["errors"] > 0 for s in r["samples"]), r["samples"])
check("B rps bisa tetap tinggi walau gagal (cacat yang diperbaiki)",
      any(s["rps"] > 0 for s in r["samples"]), r["samples"])

print("== C. fetcher palsu: saturasi -> knee terdeteksi ==")
t0 = time.time()


def fake(url, timeout=2.0):
    # kontras tajam: 1ms -> 40ms supaya pemicu latensi tidak ambigu
    lat = 0.001 if (time.time() - t0) < 1.0 else 0.04
    time.sleep(lat)
    return 200, None, lat * 1000.0


r = knee_probe.measure(ORIGIN, steps=(4, 8, 16, 32), step_seconds=0.5, fetcher=fake)
est = knee.estimate(r["samples"])
check("C ada pemicu latensi", "latency_bend" in est["triggers"], est["triggers"])
check("C knee ditemukan", est["knee"] is not None, est)
check("C knee muncul SETELAH lonjakan (bukan di langkah awal)",
      est["knee"]["index"] >= 2, est["knee"])
check("C p95 knee jauh di atas baseline", est["knee"]["p95_ms"] >= 30, est["knee"])

print("== D. _knee_stage lewat orchestrator ==")
os.environ["GALARDO_KNEE_STEPS"] = "2,4,8"
os.environ["GALARDO_KNEE_STEP_SEC"] = "0.6"
try:
    import orchestrator as orch
    ok_import = True
except Exception as e:
    ok_import = False
    print("    import orchestrator gagal: %s" % str(e)[:160])
check("D orchestrator terimpor", ok_import is True)
if ok_import:
    check("D _knee_enabled default True", orch._knee_enabled() is True, orch._knee_enabled())
    est2, rec2, raw2 = orch._knee_stage("job-uji", {"canonical_origin": ORIGIN})
    check("D _knee_stage mengembalikan estimate", est2 is not None, est2)
    check("D _knee_stage mengembalikan saran", isinstance(rec2, dict) and "target_vus" in rec2, rec2)
    est3, rec3, raw3 = orch._knee_stage("job-uji", {"canonical_origin": "http://127.0.0.1:1"})
    check("D target mati -> estimate None", est3 is None, (est3, raw3.get("reason")))
    os.environ["GALARDO_KNEE"] = "0"
    check("D GALARDO_KNEE=0 mematikan", orch._knee_enabled() is False, orch._knee_enabled())
    os.environ.pop("GALARDO_KNEE")

    print("== E. pagar anggaran waktu ==")
    os.environ["GALARDO_KNEE_STEPS"] = "2,4,8,16"
    os.environ["GALARDO_KNEE_STEP_SEC"] = "5"
    os.environ["GALARDO_KNEE_MAX_SEC"] = "4"
    t0 = time.time()
    est4, rec4, raw4 = orch._knee_stage("job-uji", {"canonical_origin": ORIGIN})
    el = time.time() - t0
    check("E probe dipangkas di bawah anggaran", el < 6.5, round(el, 2))
    check("E tetap mengembalikan estimate", est4 is not None, est4)
    os.environ["GALARDO_KNEE_MAX_SEC"] = "100"
    t0 = time.time()
    orch._knee_stage("job-uji", {"canonical_origin": ORIGIN})
    check("E anggaran longgar -> probe penuh", (time.time() - t0) > 6.0,
          round(time.time() - t0, 2))
    os.environ.pop("GALARDO_KNEE_MAX_SEC")
    os.environ.pop("GALARDO_KNEE_STEPS")
    os.environ.pop("GALARDO_KNEE_STEP_SEC")

srv.shutdown()

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
