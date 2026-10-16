# Catatan Run End-to-End Mode Aktif (V4) — STEP-47

Harness: `make demo` -> `tools/galardo_demo.py` (Goal 2 + Goal 3 end-to-end).
Target: lab lokal `tgt-lab` (seed, VERIFIED, probe_contract /healthz).

## Cuplikan output

### /tmp/demo47.log
```
python3 tools/galardo_demo.py
==============================================================
 GALARDO DEMO - GOAL 2 (DOWN + recovery) + GOAL 3 (404/blank)
==============================================================
target http://127.0.0.1:18097 | workers=16 heavy=150ms vus=300 dur=45s
  [target] hidup di http://127.0.0.1:18097
  [baseline] p50 idle 0.84 ms (10 sampel, 0.0s)
  [plafon] workers=16 backlog=0
  [probe] out-of-band jalan (interval 0.4s timeout 1.0s)
    [TRANSISI] UP        -> SUSPECT    fail_streak=3 >= 3 (timeout after 1.00s)
    [TRANSISI] SUSPECT   -> DOWN       sustained failure 4.04s >= 4.00s
  [spike] 4684 req / 46.0s = 102 rps | p50 2915ms p95 2930ms | 4xx 0 5xx 0
    [TRANSISI] DOWN      -> RECOVERING ok_streak=3 >= 3
    [TRANSISI] RECOVERING -> RECOVERED  stable 3.23s
  [verdict] state=RECOVERED down_verified=True ttr=43.676 transisi=4
  [bukti-jenuh] peak_waiting=288 avg_wait_ms=2632.1 saturated=True
  [goal3-404] applied=['T2'] status=404 forced=True
  [goal3-blank] applied=['T2'] status=200 body_len=0 forced=True
  [goal3-revert] reverted=['T2'] / ok
--------------------------------------------------------------
{
  "steps": [
    {
      "step": "target",
      "detail": "hidup di http://127.0.0.1:18097"
    },
    {
      "step": "baseline",
      "detail": "p50 idle 0.84 ms (10 sampel, 0.0s)"
    },
    {
      "step": "plafon",
      "detail": "workers=16 backlog=0"
    },
    {
      "step": "probe",
      "detail": "out-of-band jalan (interval 0.4s timeout 1.0s)"
    },
    {
      "step": "spike",
      "detail": "4684 req / 46.0s = 102 rps | p50 2915ms p95 2930ms | 4xx 0 5xx 0"
    },
    {
      "step": "verdict",
      "detail": "state=RECOVERED down_verified=True ttr=43.676 transisi=4"
    },
    {
      "step": "bukti-jenuh",
      "detail": "peak_waiting=288 avg_wait_ms=2632.1 saturated=True"
    },
    {
      "step": "goal3-404",
      "detail": "applied=['T2'] status=404 forced=True"
    },
    {
      "step": "goal3-blank",
      "detail": "applied=['T2'] status=200 body_len=0 forced=True"
    },
    {
      "step": "goal3-revert",
      "detail": "reverted=['T2'] / ok"
    }
  ],
  "verdict": {
    "state": "RECOVERED",
    "down_verified": true,
    "time_to_recover": 43.676,
    "samples_total": 64,
    "error_ratio_pct": 71.88,
    "transitions": [
      {
        "from": "UP",
        "to": "SUSPECT",
        "reason": "fail_streak=3 >= 3 (timeout after 1.00s)",
        "at": 1792150927.6683478,
        "at_iso": "2026-10-16T11:42:07Z"
      },
      {
        "from": "SUSPECT",
        "to": "DOWN",
        "reason": "sustained failure 4.04s >= 4.00s",
        "at": 1792150931.7086148,
        "at_iso": "2026-10-16T11:42:11Z"
      },
      {
        "from": "DOWN",
        "to": "RECOVERING",
        "reason": "ok_streak=3 >= 3",
        "at": 1792150972.156895,
        "at_iso": "2026-10-16T11:42:52Z"
      },
      {
        "from": "RECOVERING",
        "to": "RECOVERED",
        "reason": "stable 3.23s",
        "at": 1792150975.384247,
        "at_iso": "2026-10-16T11:42:55Z"
      }
    ]
  },
  "gate": {
    "workers": 16,
    "backlog": 0,
    "inflight": 0,
    "waiting": 0,
    "peak_inflight": 16,
    "peak_waiting": 288,
    "served": 5045,
    "shed_503": 0,
    "avg_wait_ms": 2632.1,
    "saturated": true
  },
  "override": {
    "404": {
      "status": 404,
      "override_header": "404",
      "body_len": 0,
      "forced": true,
      "latency_ms": 2.98,
      "url": "http://127.0.0.1:18779/blocked/xyz",
      "matches_spec"
--------------------------------------------------------------
DEMO_OK

```


## Tindak lanjut

- Kalau hijau: ulangi terhadap `koler.space` lewat `make t3` (P1.5).
- Kalau merah: baca lapisan kegagalan (DNS/edge/origin/app) lalu betulkan sebelum menyentuh UI.
