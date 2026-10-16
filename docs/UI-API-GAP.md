# Peta Celah UI vs API — v4 (STEP-45) + Backlog P2

Sumber: `dashboard/index.html` vs SELURUH `_dispatch` (`api.py` baris 348..1308).

## Ringkasan

- Path dipanggil UI: **25**
- Route backend: **57**
- Cocok: **23**
- UI memanggil, backend belum ada: **2**
- Route backend belum tampil di UI: **34**

## A. UI memanggil, backend belum ada

| Path | UI pakai | Status |
|---|---|---|
[DITUTUP STEP-57 - lihat KOREKSI di bawah] | `/admin/secret` | GET | BELUM DIBERESKAN |
[DITUTUP STEP-57 - lihat KOREKSI di bawah] | `/healthz` | GET | BELUM DIBERESKAN |

## B. Backlog P2 — route backend yang belum tampil di UI

Urutan mengikuti tiga goal, bukan kemudahan.

### Goal: buktikan kepemilikan

| Path | Method |
|---|---|
| `/targets/*/challenge` | POST |
| `/targets/*/ownership` | GET |
| `/targets/*/verify/attest` | POST |
| `/targets/*/verify/dns` | POST |
| `/targets/*/verify/echo` | POST |
| `/targets/*/verify/file` | POST |

### Goal: buktikan DOWN + bukti

| Path | Method |
|---|---|
| `/evidence/*/download` | GET |
| `/test-jobs/*/down` | GET |
| `/test-jobs/*/observer` | POST |
| `/test-jobs/*/reconcile` | POST |
| `/test-jobs/*/telemetry` | GET |

### Goal: paksa 404/blank

| Path | Method |
|---|---|
| `/overrides` | GET,POST |
| `/overrides/*` | GET |
| `/overrides/*/probe` | POST |
| `/overrides/*/revert` | POST |
| `/targets/*/probe-contract` | POST |

### P1.3 residential

| Path | Method |
|---|---|
| `/identity-pool` | GET |
| `/sources` | GET,POST |
| `/sources/*` | GET |
| `/sources/*/probe` | POST |
| `/sources/*/remove` | POST |
| `/sources/*/udp` | POST |
| `/sources/matrix` | GET |
| `/sources/pick` | POST |

### Fleet / worker

| Path | Method |
|---|---|
| `/config/remote-dispatch` | GET,POST |
| `/workers/*/ack` | POST |
| `/workers/*/claim` | POST |
| `/workers/*/heartbeat` | POST |

### Notifikasi

| Path | Method |
|---|---|
| `/webhooks` | GET,POST |
| `/webhooks/*` | DELETE |
| `/webhooks/*/test` | POST |
| `/webhooks/deliveries` | GET |

### Lain

| Path | Method |
|---|---|
| `/seed` | POST |
| `/test-jobs/*` | GET |

## C. Cocok (UI <-> backend)

```
/audit
/engagements
/engagements/*/approve
/evidence
/evidence/*/build
/evidence/*/verify
/health
/overview
/policies
/scenarios
/scenarios/validate
/scenarios/visual-to-yaml
/targets
/targets/*/verify
/test-jobs
/test-jobs/*/abort
/test-jobs/*/insights
/test-jobs/*/live
/test-jobs/*/recovery
/test-jobs/*/start
/test-plans
/test-plans/*/approve
/workers
```

## KOREKSI (STEP-57)

Klaim lama: UI memanggil `GET /healthz` dan `GET /admin/secret` yang belum ada handler-nya.

Kenyataan setelah verifikasi per-baris `dashboard/index.html`:
- Keduanya BUKAN panggilan API. Semua panggilan API di UI memakai helper `api()` (baris 232).
- `/healthz` hanya muncul sebagai: teks placeholder form (441), `path:` di YAML skenario (482, 503),
  dan `path:` di objek route JS (558, 685).
- `/admin/secret` hanya `path:` YAML skenario (516) - contoh path yang sengaja di-override jadi 404.
- API Galardo sudah punya health endpoint sendiri: `GET /health` (`backend/api.py:358`).
- 26 panggilan `api('...')` yang nyata: /overview, /test-jobs, /engagements, /targets,
  /scenarios, /scenarios/validate, /scenarios/visual-to-yaml, /policies, /test-plans,
  /workers, /evidence, /audit.

Kesimpulan: F-2 DITUTUP sebagai reklasifikasi. Tidak ada route API yang hilang.
