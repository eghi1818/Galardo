
# GALARDO — Distributed Worker (k6 executor) — Deployment Spec

## Arsitektur fase 10K

```
                    ┌────────────────────────┐
                    │  Galardo API/Orchestr.  │  (laptop / VPS Anda)
                    │  :8090  policy+audit   │
                    └───────┬────────────────┘
        signed job envelope │ (NATS/HTTP, TLS)
      ┌──────────┬──────────┼──────────┬──────────┐
      ▼          ▼          ▼          ▼          ▼
 ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
 │ worker-1││ worker-2││ worker-3││ worker-4││ worker-N│   (VPS Anda, same region)
 │ k6 2.5kVU│ k6 2.5kVU│ k6 2.5kVU│ k6 2.5kVU│  ...     │
 └────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘
      └──────────┴─────┬────┴──────────┴──────────┘
                       ▼
              https://wecash.ai  (Cloudflare → origin Anda)
```

## sizing utk 10K concurrent VU (Cloudflare fronted origin)
- 4 × VPS 4 vCPU/8GB (Jakarta/Singapore region dekat origin) ≈ 2.5k VU/VM @ think-time rendah
- k6 budget per VM: ~1.5k–2.5k VU aman dengan 4 vCPU (ukur dulu: k6 --quiet smoke)
- Cloudflare: pastikan rate limiting / bot rules DIKECUALIKAN utk window test (Anda pemilik zone)
- Origin: siapkan monitoring (p95, upstream conn, worker saturation) DURING run

## lifecycle worker (Blueprint §8)
1. register: POST /api/v1/workers {id, capabilities} → status IDLE
2. lease: orchestrator reserve → worker ACK → RUNNING (satu job / worker)
3. envelope: {job_id, scenario(normalized), effective_policy, target_origin, sha256}
   - worker RE-VALIDATE: signature/hash, target dalam allowlist, caps — tolak jika tak cocok
4. execute: k6 run scenario_k6.js (GALARDO_JOB=envelope) — process-group, hard deadline
5. telemetry: k6 → push-gateway/OTel → API (job-scoped)
6. abort: polling ABORT flag 1s + SIGTERM handler → k6 graceful stop → flush → ACK
7. fail-closed: heartbeat lease 15s; kehilangan kontrol → kill k6 (watchdog)

## langkah konkrit implementasi (next sprint)
- [ ] worker daemon (Go atau Python) — contract sudah ada di engine.py
- [ ] NATS JetStream + envelope signing (Ed25519)
- [ ] k6 binary pinned + wrapper: job envelope → env → run → metrics → ACK
- [ ] per-worker VU quota + fleet cap enforcement di orchestrator
- [ ] dashboard: fleet health + per-worker telemetry merge
