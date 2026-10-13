# GALARDO — ROADMAP & Pending Items

Status per 2026-10-13. Semua item di bawah adalah pengembangan yang **sudah
diidentifikasi** dengan fondasi kodenya siap — bukan bug.

## Kondisi saat ini

- 25 test jobs selesai dieksekusi (12 COMPLETED, 10 ABORTED, 2 REJECTED, 1
  housekeeping) · 13 evidence bundles · 5 policy versions · 14 workers terdaftar
- Integration test: **38/38 PASS**
- Stack live: API :8090, lab target :8095

---

## Tier 1 — Hardening (sebelum multi-user / production server)

| Item | Deskripsi | Effort |
|---|---|---|
| **Envelope signing Ed25519** | Worker saat ini memverifikasi hash + allowlist; tambah signature kriptografi per envelope agar worker di VM terpisah bisa mempercayai orchestrator lewat jaringan terbuka | 1–2 hari |
| **Auth production** | API masih dev-token; integrasi RBAC per user + MFA/SSO (BLOCKER deployment, Prolog §6) | 2–3 hari |
| **Backup otomatis Server A** | `state.json` + `audit.jsonl` + `evidence/` → backup terjadwal ke storage kedua (artefak kepatuhan) | 0,5 hari |
| **Docker Compose final** | api + dashboard + worker dalam compose resmi dengan healthcheck; sysctl docs sudah ada di SERVER-SPEC.md | 1 hari |

## Tier 2 — Scale (fleet >10 worker / >2.000 rps)

| Item | Deskripsi | Effort |
|---|---|---|
| **PostgreSQL backend** | Ganti JSON store (koneksi sudah abstrak di `db.py`); wajib sebelum >10 worker | 2–3 hari |
| **NATS aktif** | `nats_client.py` sudah ada; pindahkan dispatch/abort dari HTTP polling ke pub/sub (latensi abort <1s, fanout instan) | 1 hari |
| **Distributed sharding** | Pecah SATU job besar ke N worker (mis. 2000 rps = 4×500 rps) dengan agregasi telemetry per shard — skeleton di WORKER-SPEC.md | 3–4 hari |
| **Per-worker telemetry merge** | Dashboard Live Execution: kurva gabungan + breakdown per worker (summary per worker sudah masuk audit) | 1–2 hari |

## Tier 3 — Observability & Integrasi

| Item | Deskripsi | Effort |
|---|---|---|
| **VictoriaMetrics/OTel pipeline** | Telemetry in-process → OTel Collector → VM untuk retensi panjang + Grafana (spec di SERVER-SPEC.md) | 2–3 hari |
| **Webhook events reserved** | Aktifkan `job.recovery`, `safety.abort` (data sudah tersedia, tinggal fire) | 0,5 hari |
| **Evidence signing** | Tanda tangan manifest evidence dengan managed key (non-repudiation lebih kuat, Governance §7) | 1 hari |
| **Export laporan otomatis** | Laporan markdown/PDF per run dikirim via webhook ke SIEM/email | 1 hari |

## Tier 4 — UX Dashboard

| Item | Deskripsi | Effort |
|---|---|---|
| **Perbandingan run A/B** | Overlay dua run (sebelum/sesudah tuning origin) dalam satu chart — data sudah lengkap di evidence | 1–2 hari |
| **Scheduling job** | Jalankan job otomatis di jendela waktu tertentu (cron-like) | 1–2 hari |
| **Threshold alerting** | Notifikasi (email/Slack via webhook) saat p95/error menembus ambang real-time | 1 hari |

## Run yang menunggu konfirmasi Anda

1. **Run 2b produksi wecash.ai** (ramp setara Run 1) — validasi efek tuning origin secara adil. Menunggu konfirmasi jendela uji.
2. **Collapse test lab >2.000 rps** (policy v6) — mencari titik patah sesungguhnya (ulimit FD/thread-pool).
3. **Keep-alive comparison run waspadaweb** — memisahkan kegagalan koneksi-baru vs kapasitas respons.
