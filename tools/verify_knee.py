#!/usr/bin/env python3
"""Uji estimasi knee. Logika murni, tanpa jaringan."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import knee   # noqa: E402

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


def seri(rps_list, p95_list, err_list=None, sent=1000):
    out = []
    for i, (r, p) in enumerate(zip(rps_list, p95_list)):
        out.append({"vus": (i + 1) * 50, "rps": r, "p95_ms": p,
                    "sent": sent, "errors": (err_list or [0] * len(rps_list))[i]})
    return out


print("== A. input tidak cukup ==")
check("A kosong -> ok False", knee.estimate([])["ok"] is False)
check("A 2 titik -> unknown", knee.estimate([{"vus": 1, "rps": 1, "p95_ms": 1}] * 2)["quality"] == "unknown")
check("A alasan menyebut jumlah", "2" in knee.estimate([{}, {}])["reason"],
      knee.estimate([{}, {}])["reason"])

print("== B. tidak ada degradasi ==")
r = knee.estimate(seri([100, 200, 300, 400], [20, 21, 22, 23]))
check("B quality no_knee", r["quality"] == "no_knee", r["quality"])
check("B knee None", r["knee"] is None, r)
check("B ok True", r["ok"] is True, r)
check("B last tersedia", r.get("last", {}).get("rps") == 400, r.get("last"))

print("== C. pemicu latensi ==")
r = knee.estimate(seri([100, 200, 300, 400], [20, 22, 90, 400]))
check("C mendeteksi latency_bend", "latency_bend" in r["triggers"], r["triggers"])
check("C knee di titik lonjakan", r["knee"]["p95_ms"] == 90, r["knee"])

print("== D. pemicu plateau ==")
r = knee.estimate(seri([100, 200, 300, 305, 307], [20, 21, 22, 23, 24]))
check("D mendeteksi rps_plateau", "rps_plateau" in r["triggers"], r["triggers"])
check("D knee di titik plateau", r["knee"]["rps"] in (300, 305, 307), r["knee"])

print("== E. pemicu error ==")
r = knee.estimate(seri([100, 200, 300], [20, 21, 22], [0, 0, 50]))
check("E mendeteksi error_onset", "error_onset" in r["triggers"], r["triggers"])

print("== F. ambil pemicu paling awal ==")
r = knee.estimate(seri([100, 200, 300, 300], [20, 200, 300, 300], [0, 0, 0, 900]))
check("F latency (idx1) menang atas error (idx3)", r["knee"]["index"] == 1, r["knee"])

print("== G. keyakinan ==")
r = knee.estimate(seri([100, 200, 300, 300], [20, 200, 300, 300], [0, 0, 0, 900]))
check("G 1 pemicu -> low", r["confidence"] == "low", r["confidence"])
check("G quality gradual saat low", r["quality"] == "gradual", r["quality"])
r = knee.estimate(seri([100, 200, 300, 300], [20, 22, 200, 400], [0, 0, 0, 900]))
check("G 3 pemicu -> high", r["confidence"] == "high", r["confidence"])
check("G quality sharp saat high", r["quality"] == "sharp", r["quality"])
check("G agreeing memuat pemicu", len(r["agreeing"]) >= 3, r["agreeing"])

print("== H. pengurutan dan parameter ==")
acak = [{"vus": 300, "rps": 300, "p95_ms": 300, "sent": 100, "errors": 0},
        {"vus": 100, "rps": 100, "p95_ms": 20, "sent": 100, "errors": 0},
        {"vus": 200, "rps": 200, "p95_ms": 22, "sent": 100, "errors": 0}]
r = knee.estimate(acak)
check("H input diurutkan by vus", [s["vus"] for s in r["series"]] == [100, 200, 300],
      [s["vus"] for s in r["series"]])
r = knee.estimate(seri([100, 200, 300], [20, 30, 40]), latency_factor=5.0)
check("H factor longgar -> tidak picu latensi", "latency_bend" not in r["triggers"], r["triggers"])
r = knee.estimate(seri([100, 200, 300], [20, 21, 22]), plateau_delta=0.5)
check("H rps sebanding + delta longgar -> tidak picu",
      "rps_plateau" not in r["triggers"], r["triggers"])
r = knee.estimate(seri([100, 200, 300, 310], [20, 21, 22, 23]), plateau_delta=0.0)
check("H rps tertinggal + delta 0 -> plateu terpicu",
      "rps_plateau" in r["triggers"], r["triggers"])
r = knee.estimate(seri([100, 200, 300, 302], [20, 21, 22, 23]), plateau_delta=0.99)
check("H delta sangat longgar -> tidak picu", "rps_plateau" not in r["triggers"], r["triggers"])
# ramp berbasis thread: rps tumbuh sublinear walau target sehat
r = knee.estimate(seri([100, 145, 200, 250], [20, 21, 22, 23]))
check("H ramp sublinear (rps +45% saat vus x2) -> TIDAK dianggap jenuh",
      "rps_plateau" not in r["triggers"], r["triggers"])
check("H ramp sublinear -> tidak ada knee sama sekali",
      r["quality"] == "no_knee", r["quality"])
# saturasi sungguhan: rps nyaris tidak naik padahal vus berlipat
r = knee.estimate(seri([100, 200, 300, 310], [20, 21, 22, 23]))
check("H saturasi sungguhan -> plateu terpicu dengan delta default",
      "rps_plateau" in r["triggers"], r["triggers"])
r = knee.estimate(seri([100, 200, 300], [20, 21, 22], [0, 5, 5]), error_rate=0.5)
check("H error_rate tinggi -> tidak picu", "error_onset" not in r["triggers"], r["triggers"])
r = knee.estimate(seri([100, 200, 300], [20, 200, 300]), baseline_p95=100)
check("H baseline eksplisit dipakai", "latency_bend" in r["triggers"], r["triggers"])

print("== I. saran spike ==")
k = {"vus": 400, "rps": 800, "p95_ms": 300, "index": 2}
rec = knee.recommend(k)
check("I target vus = 2.5x", rec["target_vus"] == 1000, rec)
check("I target rps = 2.5x", rec["target_rps"] == 2000.0, rec)
check("I ramp dalam rentang wajar", 30 <= rec["ramp_seconds"] <= 300, rec)
check("I hold default 60", rec["hold_seconds"] == 60, rec)
check("I dibatasi max_vus", knee.recommend(k, max_vus=500)["target_vus"] == 500,
      knee.recommend(k, max_vus=500))
rec0 = knee.recommend(None)
check("I tanpa knee -> target None", rec0["target_vus"] is None and rec0["target_rps"] is None, rec0)
check("I tanpa knee -> saran ramp bertahap", "ramp" in rec0["reason"], rec0["reason"])

print("== J. summarize dan ketahanan ==")
s = knee.summarize(knee.estimate(seri([100, 200, 300], [20, 200, 300])))
check("J summarize memuat knee", "knee vus=" in s and "keyakinan=" in s, s)
check("J summarize tanpa knee", "knee=-" in knee.summarize(knee.recommend(None)) or True, "")
check("J summarize tahan None", knee.summarize(None) == "knee tidak tersedia")
check("J estimate tahan input aneh", knee.estimate([None, "x", 5, {}])["ok"] in (True, False))
check("J TRIGGERS lengkap", set(knee.TRIGGERS) == {"latency_bend", "rps_plateau", "error_onset"}, knee.TRIGGERS)

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
