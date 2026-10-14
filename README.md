# GALARDO — Authorized Resilience & Security Testing Platform (MVP)

Testbed Layer-7 stress testing / high-traffic simulation untuk mengukur ketahanan
dan kapasitas beban target **terotorisasi** — dengan safety pipeline penuh:
preflight fail-closed, independent probe, safety auto-abort, recovery
verification, evidence SHA-256, dan audit trail append-only.

> ⚠ Semua pengujian wajib dibatasi pada sistem yang kepemilikan/izinnya telah
> diverifikasi (Prolog §1). Dilarang: proxy rotation, WAF/CAPTCHA bypass,
> unbounded flooding, target eksternal tanpa izin terdokumentasi.

## Status implementasi vs dokumen referensi

| Area | Referensi | Status |
|---|---|---|
| Scenario engine (YAML strict, unknown-field reject, absolute-URL reject, method allowlist) | TD §5 | ✅ |
| Policy intersection Global→Org→Scenario (minimum/intersect, fail-closed) | TD §9 | ✅ |
| Immutable scenario version + SHA-256 canonical JSON | TD §5.1 | ✅ |
| Job state machine + transition guard + audit per transisi | TD §13 | ✅ |
| Idempotent job creation (`Idempotency-Key`) | FR-05 | ✅ |
| Preflight fail-closed (8 checks) | UX §6 | ✅ |
| Bounded load engine (VU pool, ramp, token-bucket RPS, deadline watchdog) | TD §7 | ✅ |
| Independent health probe (no-redirect, consecutive failures, UNKNOWN ≠ HEALTHY) | TD §10 | ✅ |
| Safety controller (probe/5xx/p95/stale/abort, idempotent, persisted) | GOV §4 | ✅ |
| Manual abort dari UI + konfirmasi type-ABORT + ACK semantics | UX §7 | ✅ |
| Recovery via independent probe (HEALTHY ×3, timeout → RECOVERY_FAILED) | FR-08 | ✅ |
| Evidence bundle tar.gz + manifest SHA-256 per-file + bundle hash + verify/tamper | TD §14 | ✅ |
| Audit log append-only (actor/time/reason/correlation) | NFR-06 | ✅ |
| Dashboard 10 halaman dark-console + live telemetry + emergency abort | UX §2–10 | ✅ |
| RBAC multi-user, NATS, Postgres, k6, worker pool terdistribusi, AI advisory | TD §1 | ⏭ fase berikutnya (lihat README §Roadmap) |

## Menjalankan

```bash
cd galardo
make dev-up          # lab target :8095 + API :8090 + dashboard
# buka http://127.0.0.1:8090/
```

Pemilihan port anti-bentrok: API memakai 8090 dan lab target 8095. Jika port
preferred sudah dipakai proses lain (punya Anda atau sistem), runner otomatis
memindai 8090–8099 / 8095–8099 sampai kosong dan mencetak alamat final. Dasbor
juga melakukan auto-discovery: bila dibuka dari origin lain (file viewer/proxy),
ia mem-probe kandidat port dan mencari penanda `galardo-api` di `/health`.

Saat boot, API otomatis men-seed lab: organization, engagement APPROVED,
target `galardo-lab-target` (VERIFIED, window 1 tahun), policy global, scenario
`health-smoke` v1, dan test plan `plan-lab-smoke` (APPROVED) — siap dibuat job.

Kustom origin target:

```bash
GALARDO_TARGET_ORIGIN=http://127.0.0.1:9090 make dev-up
```

Stop: `make dev-down` (atau `pkill -f run_local.py`).

## Alur pakai (end-to-end)

1. **Overview** — cek platform health.
2. **Test Plans** → `Create Job` pada `plan-lab-smoke` (atau buat scenario/plan baru).
3. **Live Execution** → `▶ Start` → preflight 8 check → RUNNING → telemetri live
   (RPS, p50/p95/p99, error %, VUs, probe) → selesai otomatis → recovery otomatis
   (probe HEALTHY ×3) → `🔒 Build evidence bundle` → `Verify hash` → download.
4. **Emergency Abort** — tersedia selama run aktif; ketik `ABORT` untuk konfirmasi.
   Status `ABORT_REQUESTED` tampil berbeda dari stop terkonfirmasi; ACK worker
   dicatat di audit.
5. **Scenarios** — editor YAML + 4 fixture (valid, over-limit, path-escape,
   external-host) untuk melihat validasi menolak dengan field-level error.
6. **Audit Log** — semua mutasi & transisi state dengan actor/reason/correlation.

## Stress testing serius (kapasitas)

Engine stdlib ini nyaman sampai ±200–400 RPS di MacBook. Untuk beban lebih besar:

- naikkan cap `pol-global-v1` melalui proses persetujuan policy (tidak boleh
  dilewati scenario — by design);
- ganti executor worker ke k6 (kontrak worker hanya butuh: envelope tervalidasi,
  telemetry ring, abort flag) — struktur kode sudah memisahkan `engine.py`
  sebagai worker core;
- scale-out worker pool mengikuti Blueprint §8.

## Struktur

```
galardo/
├── backend/
│   ├── api.py            # REST /api/v1 + static dashboard + seed lab
│   ├── orchestrator.py   # state machine, preflight, dispatch, recovery
│   ├── engine.py         # bounded load engine + TelemetryRing
│   ├── safety.py         # HealthProbe + SafetyController
│   ├── policy.py         # policy hierarchy & intersection
│   ├── scenario.py       # YAML parser + immutable versions
│   ├── evidence.py       # bundle/manifest/verify (tar.gz + SHA-256)
│   ├── db.py             # JSON store + append-only audit
│   ├── lab_target.py     # target LAB dengan fixture degradation
│   └── run_local.py      # entrypoint satu perintah
├── dashboard/index.html  # konsol operasional (vanilla JS, no deps)
├── tests/                # 38 integration checks + fixtures
├── Makefile              # dev-up / test / scenario-validate
└── .env.example
```

## Testing

```bash
make test    # 38 checks: validasi scenario, idempotency, preflight,
             # bounded run, recovery, abort idempotent, auto-abort saat
             # degradation, evidence tamper, immutable version, audit
```

## Modifikasi umum

| Ingin mengubah | Lokasi |
|---|---|
| Cap policy (RPS/VU/durasi/p95/error%) | Seed `pol-global-v1` di `backend/api.py` (atau via API policy table) |
| Allowed paths / probe contract target | `backend/api.py` seed `target`, atau tab Targets |
| Threshold safety (stale telemetry, error %, p95) | `backend/safety.py` + field policy `max_error_pct`/`max_p95_ms` |
| Endpoint sintetis target lab | `backend/lab_target.py` |
| Warna/branding konsol | CSS `:root` di `dashboard/index.html` |
| Port | `backend/run_local.py`, atau env `GALARDO_TARGET_ORIGIN` |

## Roadmap (mengikuti dokumen)

1. **Hardening** — RBAC penuh + org scope, MFA/SSO (BLOCKER deployment), backup/restore.
2. **Distributed** — Postgres + NATS JetStream + worker pool terpisah (TD §2), k6 executor.
3. **Telemetry skala** — OpenTelemetry Collector → VictoriaMetrics + Grafana (TD §11).
4. **AI advisory** — HAR import + redaction, scenario draft, analisis pasca-run; semua output
   draft + review manusia (GOV §1–3), tanpa kredensial dispatch.
5. **External authorized testing** — egress allowlist, runbook, on-call, safety review (TD §17).

## Download & Instalasi

```bash
# Clone (butuh akses SSH akun eghi1818):
git clone git@github.com:eghi1818/Galardo.git
cd Galardo

# Jalankan lab (API + dashboard :8090, lab target :8095):
make dev-up
# Dashboard: http://127.0.0.1:8090
```

Alternatif: tombol `<> Code` → `Download ZIP` di halaman repo.
Folder `data/` (state & evidence runtime) tidak ikut ter-download by design —
lihat `.gitignore`. Konfigurasi contoh: `.env.example`.
