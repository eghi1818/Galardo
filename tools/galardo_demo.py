#!/usr/bin/env python3
"""GALARDO - one-command end-to-end demo (GOAL 2 + GOAL 3).

Jalankan:  make demo   (atau: python3 tools/galardo_demo.py)

Cerita yang dijalankan, dengan bukti di setiap langkah:
  1. baseline  : probe target saat idle -> p50/p95
  2. plafon    : pasang ceiling 16 worker di lab target
  3. spike     : 300 VU ke /api/heavy -> UP/SUSPECT/DOWN
  4. pulih     : beban stop -> RECOVERING/RECOVERED + time_to_recover
  5. bukti     : gate.stats (peak_waiting, avg_wait_ms, saturated)
  6. goal 3    : paksa 404, probe, paksa blank, probe, revert
  7. ringkasan : JSON
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import engine          # noqa: E402
import scenario as sc  # noqa: E402
import external_probe as ep      # noqa: E402
import routeoverride as ro       # noqa: E402

PORT = int(os.environ.get("GALARDO_DEMO_PORT", "18097"))
BASE = "http://127.0.0.1:%d" % PORT
WORKERS = int(os.environ.get("GALARDO_DEMO_WORKERS", "16"))
HEAVY_MS = int(os.environ.get("GALARDO_DEMO_HEAVY_MS", "150"))
VUS = int(os.environ.get("GALARDO_DEMO_VUS", "300"))
DURATION = int(os.environ.get("GALARDO_DEMO_DURATION", "45"))

REPORT = {"steps": [], "verdict": None, "gate": None, "override": None, "ok": False}


def step(name, detail):
    REPORT["steps"].append({"step": name, "detail": detail})
    print("  [%s] %s" % (name, detail))


def get_json(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=5))


def main():
    print("=" * 62)
    print(" GALARDO DEMO - GOAL 2 (DOWN + recovery) + GOAL 3 (404/blank)")
    print("=" * 62)
    print("target %s | workers=%d heavy=%dms vus=%d dur=%ds"
          % (BASE, WORKERS, HEAVY_MS, VUS, DURATION))

    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "backend", "lab_target.py"),
                             "--port", str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.2)
        step("target", "hidup di %s" % BASE)

        # 1. baseline
        t0 = time.time()
        lats = []
        for _ in range(10):
            s = time.time()
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=3).read()
                lats.append((time.time() - s) * 1000)
            except Exception:
                pass
        step("baseline", "p50 idle %.2f ms (%d sampel, %.1fs)"
             % (sorted(lats)[len(lats) // 2] if lats else -1, len(lats), time.time() - t0))

        # 2. plafon
        g = get_json("/control/capacity?workers=%d&backlog=0" % WORKERS)["gate"]
        get_json("/control/heavy?ms=%d" % HEAVY_MS)
        step("plafon", "workers=%s backlog=%s" % (g["workers"], g["backlog"]))

        # 3-5. spike + recovery
        targets = {"main": {"id": "tgt-demo", "name": "main", "canonical_origin": BASE}}
        y = ("schema_version: \"1.2\"\nname: \"demo\"\ntarget_ref: \"main\"\n"
             "profile:\n  virtual_users: %d\n  duration_seconds: %d\n  max_rps: 5000\n"
             "requests:\n  - name: \"heavy\"\n    method: \"GET\"\n    path: \"/api/heavy\"\n"
             "    weight: 100\n    timeout_ms: 8000\n"
             "think_time_ms:\n  min: 0\n  max: 0\n" % (VUS, DURATION))
        norm = sc.parse_scenario_yaml(y, targets)

        events = []

        def on_trans(ev):
            events.append(ev)
            print("    [TRANSISI] %-9s -> %-10s %s" % (ev["from"], ev["to"], ev["reason"]))

        w = ep.DownWatcher(BASE + "/healthz", interval=0.4, timeout=1.0,
                           failure_threshold=3, min_down_seconds=4.0,
                           recover_threshold=3, recover_seconds=3.0, on_transition=on_trans)
        w.start()
        time.sleep(2)
        step("probe", "out-of-band jalan (interval 0.4s timeout 1.0s)")

        tel = engine.TelemetryRing()
        eng = engine.LoadEngine("job-demo", "run-demo", BASE, norm,
                                {"max_rps": 5000, "max_vus": VUS,
                                 "max_duration_sec": DURATION}, tel, lambda: (False, None))
        t0 = time.time()
        eng.run()
        el = time.time() - t0
        win = tel.window(max(5, int(el)))
        step("spike", "%d req / %.1fs = %.0f rps | p50 %.0fms p95 %.0fms | 4xx %d 5xx %d"
             % (win["requests"], el, win["requests"] / el if el else 0,
                win["p50_ms"] or 0, win["p95_ms"] or 0, win["err_4xx"], win["err_5xx"]))

        deadline = time.time() + 40
        while time.time() < deadline and w.sm.state != "RECOVERED":
            time.sleep(1)
        w.stop()
        v = w.verdict()
        step("verdict", "state=%s down_verified=%s ttr=%s transisi=%d"
             % (v.get("state"), v.get("down_verified"), v.get("time_to_recover"), len(events)))
        REPORT["verdict"] = {k: v.get(k) for k in
                             ("state", "down_verified", "time_to_recover",
                              "samples_total", "error_ratio_pct")}
        REPORT["verdict"]["transitions"] = events

        gs = get_json("/control/stats")["gate"]
        REPORT["gate"] = gs
        step("bukti-jenuh", "peak_waiting=%s avg_wait_ms=%s saturated=%s"
             % (gs["peak_waiting"], gs["avg_wait_ms"], gs["saturated"]))

        # 6. goal 3
        spec = ro.OverrideSpec("demo.test", paths=["/blocked/*"], mode="404")
        ov = ro.RouteOverrider(spec, shim_port=int(os.environ.get("GALARDO_DEMO_SHIM_PORT", "18779")))
        rep = ov.apply(tiers=("T2",))
        p404 = ov.probe(spec.spec_id, "/blocked/xyz")
        step("goal3-404", "applied=%s status=%s forced=%s"
             % (rep.get("applied_tiers"), p404.get("status"), p404.get("forced")))

        spec2 = ro.OverrideSpec("demo.test", paths=["/*"], mode="blank")
        ov2 = ro.RouteOverrider(spec2)
        rep2 = ov2.apply(tiers=("T2",))
        pblank = ov2.probe(spec2.spec_id, "/apa/saja")
        step("goal3-blank", "applied=%s status=%s body_len=%s forced=%s"
             % (rep2.get("applied_tiers"), pblank.get("status"),
                pblank.get("body_len"), pblank.get("forced")))

        rv = ov.revert(spec.spec_id)
        ov2.revert(spec2.spec_id)
        step("goal3-revert", "reverted=%s / %s" % (rv.get("reverted"), "ok"))
        REPORT["override"] = {"404": p404, "blank": pblank, "reverted": rv.get("reverted")}

        ok = (bool(v.get("down_verified")) and v.get("time_to_recover") is not None
              and len(events) >= 4 and p404.get("status") == 404
              and pblank.get("body_len") == 0 and gs.get("saturated"))
        REPORT["ok"] = ok
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print("-" * 62)
    print(json.dumps(REPORT, indent=2, default=str)[:2400])
    print("-" * 62)
    print("DEMO_OK" if REPORT["ok"] else "DEMO_TIDAK_LENGKAP")
    return 0 if REPORT["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
