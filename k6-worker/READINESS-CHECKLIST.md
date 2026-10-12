# GALARDO — Production Readiness Checklist
**Program:** Distributed capacity testing (k6 worker cluster) — target skala 10K VU
**Status dokumen:** v1.0 — baseline untuk review sebelum full-scale production run
**Prinsip induk:** Prolog §1 (authorized only), PRD §5.2 (out-of-scope: proxy farms/rotation),
Blueprint §8 (scale-out roadmap, no source concealment)

> ⚠ Keputusan arsitektur yang mengikat: kluster worker = N identitas terdaftar
> (4–8 VPS milik sendiri). **TIDAK ada IP pool sewaan 10.000** — requirement itu
> hanya muncul untuk menembus per-IP rate limiting, yang merupakan concealment
> (dilarang dokumen + hukum), bukan load testing. Dokumen ini disusun untuk
> kluster identitas-resmi.

---

## 1. Prasyarat (Prerequisites Register)

| # | Item | Owner | Bukti wajib | Status |
|---|---|---|---|---|
| P-01 | Izin tertulis pemilik target (scope: host/path/method/window/caps) | Test Owner | Dokumen ttd + SHA-256 di engagement | ✅ (pemilik wecash.ai) |
| P-02 | Jendela uji + kontak on-call kedua pihak | Engagement Manager | Di engagement record | ✅ |
| P-03 | Rate rule Cloudflare DIKECUALIKAN untuk IP generator selama window | Target Owner | Screenshot/rule-id di evidence | ⬜ |
| P-04 | Grafana/monitor origin aktif (p95, upstream conn, DB pool, queue) | Target Owner | Dashboard link | ⬜ |
| P-05 | Rollback plan: abort path teruji + prosedur kill-switch cluster | Safety | Runbook §5 | ✅ (auto-abort + manual) |
| P-06 | Baseline traffic produksi 7 hari (p50/p95/error per jam) | Analyst | CSV di evidence baseline | ⬜ |

## 2. Kluster Worker (per-VM readiness)

| # | Item | Kriteria PASS |
|---|---|---|
| W-01 | k6 pinned version | `k6 version` sama di semua VM |
| W-02 | worker_daemon berjalan sebagai systemd service | restart otomatis, non-root user |
| W-03 | Identitas terdaftar di orchestrator | muncul di `/workers` status IDLE |
| W-04 | Revalidation pass | claim → envelope hash+allowlist+caps OK |
| W-05 | Abort path teruji | ABORT_REQUESTED → k6 mati < 5s (per VM) |
| W-06 | Fail-closed teruji | blokir API port saat RUNNING → k6 mati ≤ 20s |
| W-07 | Egress terbatas | hanya target + orchestrator (NetworkPolicy/security group) |
| W-08 | Resource budget | k6 maxVUs × ~20KB mem; CPU < 70% saat target load |
| W-09 | Clock sync | NTP aktif (telemetry timestamp valid) |
| W-10 | Kapasitas per VM terukur | smoke 2.5k VU lokal dulu sebelum join fleet |

## 3. Orchestrator / Control Plane

| # | Item | Kriteria |
|---|---|---|
| C-01 | Envelope signing (Ed25519) | worker menolak envelope tanpa signature valid |
| C-02 | Single-claim guard | 2 worker claim job sama → hanya 1 dapat envelope |
| C-03 | Single active job per target | preflight check tetap fail-closed |
| C-04 | Heartbeat lease | worker hilang > 20s → job ABORTED + VM QUARANTINED |
| C-05 | Remote dispatch opt-in | `config.remote-dispatch` + plan.remote_dispatch keduanya wajib |
| C-06 | Cap fleet total | jumlah cap per worker ≤ policy cap target |
| C-07 | Audit per transition | semua state punya actor/reason/correlation (sudah ✅) |
| C-08 | Backup state | `data/state.json` + audit.jsonl ke storage kedua sebelum run |

## 4. Matriks Dependensi (dependency matrix, risiko kegagalan)

| Komponen | Bergantung pada | Mode gagal | Mitigasi teruji |
|---|---|---|---|
| worker → orchestrator | HTTP API | claim/abort gagal | fail-closed kill ≤ 20s (W-06) |
| orchestrator → DB state | state.json / Postgres nanti | state corrupt | backup C-08 + append-only audit |
| worker → k6 | binary pinned | versi beda hasil beda | W-01 pin + verifikasi hash |
| worker → target | DNS + edge | DNS shift selama run | probe contract + revalidate (FR-02) |
| orchestrator → dashboard | same origin | UI stale | polling + stale indicator (sudah ✅) |
| fleet → evidence | summary k6 | summary hilang | exit-code non-zero → job FAILED, tidak COMPLETED |

## 5. Runbook Full-Scale 10K

1. **T-24h**: P-03 exception aktif, P-06 baseline fresh, semua W-* hijau.
2. **T-1h**: fleet smoke 30s @ 10 rps (E2E job) — semua worker ACK RECOVERED.
3. **T-0**: step ramp via k6 fleet: 100 → 250 → 500 → 1000 → 2000 rps (2–3 menit/step),
   orchestrator cap = fleet cap; safety threshold policy v3 ditinjau (p95 limit, error %).
4. **During**: probe dashboard Live Execution; abort otomatis aktif; manual abort standby.
5. **Post**: recovery RECOVERED per job, evidence bundle per job, verifikasi hash,
   laporan: saturation curve + failure inventory + origin recommendation.

## 6. Definisi "Ready for Production" (exit criteria)

- [ ] Seluruh item P-*, W-*, C-* PASS dengan bukti tercatat
- [ ] Satu full rehearsal di staging mirror dengan fleet penuh
- [ ] Abort latency terukur < 5s di SEMUA worker (bukan rata-rata)
- [ ] Evidence chain: envelope hash → k6 summary → bundle SHA-256 → audit
- [ ] Sign-off Safety Officer + Target Owner (dokumen ttd)

## 7. Lacunae yang diakui (belum ada di MVP)

- Envelope signing Ed25519 (C-01) — saat ini hash-only, same-host assumption
- NATS transport aktif (nats_client.py tersedia, fleet jalan via HTTP polling — cukup untuk 10 worker)
- Postgres/NATS HA — state JSON cukup untuk 8 worker; wajib Postgres sebelum >10 worker
- Per-worker telemetry merge di dashboard (summary per worker sudah masuk audit)
