#!/usr/bin/env python3
"""GALARDO - capacity discovery: cari titik jenuh (knee) SEBELUM spike.

Jawaban untuk pertanyaan "dari mana kita tahu spec server target?":
jangan menebak. Naikkan beban bertahap, catat di langkah ke berapa
p95 meledak / error muncul / tambahan VU tidak lagi menambah rps.

Itulah knee. Spike yang benar = 1,2-1,5x knee, bukan angka karangan.

Pemakaian:
    make capacity                                  # target lab, workers tak terbatas
    make capacity CAP_STEPS=25,50,100,200 CAP_WORKERS=16
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import engine          # noqa: E402
import scenario as sc  # noqa: E402

PORT = int(os.environ.get("GALARDO_CAP_PORT", "18096"))
BASE = "http://127.0.0.1:%d" % PORT
STEPS = [int(x) for x in os.environ.get("GALARDO_CAP_STEPS", "25,50,100,200,400").split(",")]
SECS = int(os.environ.get("GALARDO_CAP_SECONDS", "8"))
WORKERS = int(os.environ.get("GALARDO_CAP_WORKERS", "0"))
PATH = os.environ.get("GALARDO_CAP_PATH", "/healthz")
START_TARGET = os.environ.get("GALARDO_CAP_START_TARGET", "1") == "1"


def jget(p):
    return json.load(urllib.request.urlopen(BASE + p, timeout=5))


def run_step(vus, secs):
    targets = {"main": {"id": "tgt-cap", "name": "main", "canonical_origin": BASE}}
    y = ("schema_version: \"1.2\"\nname: \"cap\"\ntarget_ref: \"main\"\n"
         "profile:\n  virtual_users: %d\n  duration_seconds: %d\n  max_rps: 50000\n"
         "requests:\n  - name: \"p\"\n    method: \"GET\"\n    path: \"%s\"\n"
         "    weight: 100\n    timeout_ms: 8000\n"
         "think_time_ms:\n  min: 0\n  max: 0\n" % (vus, secs, PATH))
    norm = sc.parse_scenario_yaml(y, targets)
    tel = engine.TelemetryRing()
    eng = engine.LoadEngine("job-cap", "run-cap-%d" % vus, BASE, norm,
                            {"max_rps": 50000, "max_vus": vus, "max_duration_sec": secs},
                            tel, lambda: (False, None))
    t0 = time.time()
    eng.run()
    el = max(0.001, time.time() - t0)
    w = tel.window(max(2, int(el)))
    return {"vus": vus, "seconds": round(el, 1), "requests": w["requests"],
            "rps": round(w["requests"] / el, 1), "p50_ms": w["p50_ms"], "p95_ms": w["p95_ms"],
            "err_4xx": w["err_4xx"], "err_5xx": w["err_5xx"],
            "error_pct": round(w["error_pct"], 3), "conn_errors": w["conn_errors"],
            "timeouts": w["timeouts"]}


def main():
    proc = None
    if START_TARGET:
        proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "backend", "lab_target.py"),
                                 "--port", str(PORT)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
    try:
        print("=" * 68)
        print(" GALARDO CAPACITY DISCOVERY")
        print(" target=%s path=%s steps=%s %ss/step workers=%s"
              % (BASE, PATH, STEPS, SECS, WORKERS or "unlimited"))
        print("=" * 68)
        try:
            jget("/control/capacity?workers=%d&backlog=0" % WORKERS)
            jget("/control/reset") if WORKERS == 0 else None
        except Exception:
            pass

        rows = []
        print("  %-6s %-9s %-9s %-9s %-8s" % ("VUs", "rps", "p50ms", "p95ms", "err%"))
        for v in STEPS:
            r = run_step(v, SECS)
            rows.append(r)
            print("  %-6d %-9.1f %-9s %-9s %-8.2f"
                  % (r["vus"], r["rps"], r["p50_ms"], r["p95_ms"], r["error_pct"]))
            time.sleep(1.0)

        base = rows[0]
        knee = None
        for i in range(1, len(rows)):
            cur, prev = rows[i], rows[i - 1]
            p95_break = cur["p95_ms"] and base["p95_ms"] and cur["p95_ms"] > max(3 * base["p95_ms"], 200)
            err_break = cur["error_pct"] > 1.0 or cur["timeouts"] > 0 or cur["conn_errors"] > 0
            flat = cur["rps"] < prev["rps"] * 1.15
            if p95_break or err_break or flat:
                knee = {"vus": cur["vus"], "rps": cur["rps"], "p95_ms": cur["p95_ms"],
                        "reason": ("p95 meledak" if p95_break else
                                   "error/timeout" if err_break else "rps tidak naik lagi")}
                break

        out = {"target": BASE, "path": PATH, "workers": WORKERS, "steps": rows,
               "baseline": base, "knee": knee}
        if knee:
            out["recommendation"] = {
                "spike_rps": round(knee["rps"] * 1.3, 1),
                "spike_vus": int(knee["vus"] * 1.3),
                "note": "spike 1,2-1,5x knee; kalau tidak DOWN -> naikkan 2x lagi"}

        print("-" * 68)
        if knee:
            print(" KNEE ditemukan di %d VU (%.0f rps) - sebab: %s"
                  % (knee["vus"], knee["rps"], knee["reason"]))
            print(" Rekomendasi spike: %d VU / ~%.0f rps"
                  % (out["recommendation"]["spike_vus"], out["recommendation"]["spike_rps"]))
            if WORKERS == 0:
                print(" CATATAN: workers=0 -> ini plafon GENERATOR, bukan target.")
                print("          ulangi dengan CAP_WORKERS=<n> untuk plafon target.")
        else:
            print(" Tidak ada knee pada rentang ini: coba VU lebih besar")
            print(" (kalau target tanpa plafon, pasang /control/capacity dulu)")
        print("-" * 68)
        print(json.dumps(out, indent=2, default=str)[:1800])
        print("CAPACITY_OK")
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
