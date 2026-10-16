# Rencana Uji End-to-End Mode Aktif (V4) — STEP-46

Tujuan: membuktikan tiga goal jalan nyata lewat HTTP, bukan hanya unit test.

## Target uji

Target lab lokal dengan `allowed_paths` dan `probe_contract` (lihat `api.py` ~baris 78).

## Urutan yang harus dibuktikan

1. Target dibuat -> `GALARDO_LOCAL_DEV=1` -> otomatis `VERIFIED`
2. Skenario dibuat -> `/scenarios/validate` hijau
3. Plan dibuat -> `/test-plans/*/approve`
4. Job dibuat -> `/test-jobs/*/start` -> poll `/live` sampai selesai
5. `/evidence/*/build` -> `/evidence/*/verify` hijau
6. Paksa 404 via `/overrides` -> `/overrides/*/probe` -> buktikan DOWN
7. `/test-jobs/*/down` -> ringkasan bukti DOWN

## Permukaan run yang ditemukan

### Target Makefile
```
10:.PHONY: help dev-up dev-down seed-lab test test-integration scenario-validate run-local clean
12:help:
20:dev-up:
23:dev-down:
27:seed-lab:
31:test:
34:scenario-validate:
43:try:\n\
54:clean:
58:run-local: dev-up
61:demo:
65:capacity:
73:t3:
77:srccap:
81:udp:
83:udp-spoof:
87:worm:
89:worm-reap:
93:.PHONY: crypto keygen
94:crypto:
96:keygen:
100:.PHONY: trust peer
101:trust:
103:peer:
```

### Entrypoint backend
```
lab_target.py
observer.py
run_local.py
```

### Rujukan healthz
```
tools/galardo_demo.py:71:                urllib.request.urlopen(BASE + "/healthz", timeout=3).read()
tools/galardo_demo.py:98:        w = ep.DownWatcher(BASE + "/healthz", interval=0.4, timeout=1.0,
tools/verify_knee_probe.py:114:                   "probe_contract": {"url": ORIGIN + "/healthz"}})
tools/verify_knee_probe.py:116:    check("E3 url probe memakai path target", "/healthz" in str(raw5.get("url")), raw5.get("url"))
tools/galardo_capacity.py:33:PATH = os.environ.get("GALARDO_CAP_PATH", "/healthz")
tools/verify_buster_unified.py:90:p = ep.ExternalProbe("http://127.0.0.1:%d/healthz" % port, interval=0.25, timeout=2.0)
backend/api.py:78:              "allowed_paths": ["/", "/healthz", "/api/slow", "/api/error", "/api/heavy"],
backend/api.py:79:              "probe_contract": {"url": target_origin + "/healthz", "expected_status": 200,
backend/api.py:90:                  "allowed_paths": ["/", "/healthz", "/api/slow", "/api/error", "/api/heavy"],
backend/api.py:98:                "description": "Low-volume smoke against lab target /healthz",
backend/api.py:118:    path: "/healthz"
backend/api.py:467:                           "url": origin + "/healthz", "expected_status": 200,
backend/orchestrator.py:602:            probe_contract = {"url": target["canonical_origin"] + "/healthz",
backend/scenario.py:294:        routes = [{"path": "/healthz", "weight": 100}]
backend/run_local.py:91:        if wait_http(f"http://127.0.0.1:{target_port}/healthz"):
backend/lab_target.py:21:Backwards compatible: /healthz, /api/slow, /api/error, /api/heavy,
backend/lab_target.py:32:GATED_PATHS = ("/", "/healthz", "/api/slow", "/api/error", "/api/heavy", "/api/cpu")
backend/lab_target.py:203:        if path == "/healthz":
backend/lab_target.py:222:                                "hint": "allowed: /healthz /api/slow /api/error /api/heavy /api/cpu"})
backend/lab_target.py:296:    print("[galardo-target] v2 on http://%s:%d  (/healthz, /api/*, /control/*)" % (host, port))
```

### Handler siklus hidup job
```
825:            if api_path == "/test-jobs" and method == "GET":
827:            if api_path == "/test-jobs" and method == "POST":
```

## Langkah berikut (STEP-47)

- Tulis `tools/e2e_active.sh` mengikuti urutan di atas.
- Jalankan terhadap target lab lokal, cetak status tiap langkah.
- Kalau hijau, ulangi terhadap `koler.space` (P1.5) dengan Worker yang memaksa 404.
