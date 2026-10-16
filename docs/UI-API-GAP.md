# Peta Celah UI vs API — v3 (STEP-44)

Sumber: `dashboard/index.html` vs SELURUH fungsi `_dispatch` di `backend/api.py` (baris 348..1308).
Normalisasi: `${...}` `<...>` `{...}` angka -> `*`; prefix `/api/vN` dibuang.

## Ringkasan

- Path dipanggil UI: **25**
- Route di backend: **57**
- Cocok: **22**
- UI memanggil, TIDAK ada di backend: **3**
- Route backend belum dipakai UI: **35**
- Kemungkinan salah method: **0**

## A. UI memanggil, tidak ada padanan backend (PRIORITAS)

| Path | UI pakai |
|---|---|
| `/admin/secret` | GET |
| `/audit?limit=*` | GET |
| `/healthz` | GET |

## B. Route backend belum dipakai UI

| Path | Method |
|---|---|
| `/audit` | GET |
| `/config/remote-dispatch` | GET,POST |
| `/evidence/*/download` | GET |
| `/identity-pool` | GET |
| `/overrides` | GET,POST |
| `/overrides/*` | GET |
| `/overrides/*/probe` | POST |
| `/overrides/*/revert` | POST |
| `/seed` | POST |
| `/sources` | GET,POST |
| `/sources/*` | GET |
| `/sources/*/probe` | POST |
| `/sources/*/remove` | POST |
| `/sources/*/udp` | POST |
| `/sources/matrix` | GET |
| `/sources/pick` | POST |
| `/targets/*/challenge` | POST |
| `/targets/*/ownership` | GET |
| `/targets/*/probe-contract` | POST |
| `/targets/*/verify/attest` | POST |
| `/targets/*/verify/dns` | POST |
| `/targets/*/verify/echo` | POST |
| `/targets/*/verify/file` | POST |
| `/test-jobs/*` | GET |
| `/test-jobs/*/down` | GET |
| `/test-jobs/*/observer` | POST |
| `/test-jobs/*/reconcile` | POST |
| `/test-jobs/*/telemetry` | GET |
| `/webhooks` | GET,POST |
| `/webhooks/*` | DELETE |
| `/webhooks/*/test` | POST |
| `/webhooks/deliveries` | GET |
| `/workers/*/ack` | POST |
| `/workers/*/claim` | POST |
| `/workers/*/heartbeat` | POST |

## C. Kemungkinan salah method

(tidak ada)

## D. Cocok

```
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

## E. Daftar mentah backend

```
/audit                             GET
/config/remote-dispatch            GET,POST
/engagements                       GET,POST
/engagements/*/approve             POST
/evidence                          GET
/evidence/*/build                  POST
/evidence/*/download               GET
/evidence/*/verify                 POST
/health                            GET
/identity-pool                     GET
/overrides                         GET,POST
/overrides/*                       GET
/overrides/*/probe                 POST
/overrides/*/revert                POST
/overview                          GET
/policies                          GET,POST
/scenarios                         GET,POST
/scenarios/validate                POST
/scenarios/visual-to-yaml          POST
/seed                              POST
/sources                           GET,POST
/sources/*                         GET
/sources/*/probe                   POST
/sources/*/remove                  POST
/sources/*/udp                     POST
/sources/matrix                    GET
/sources/pick                      POST
/targets                           GET,POST
/targets/*/challenge               POST
/targets/*/ownership               GET
/targets/*/probe-contract          POST
/targets/*/verify                  POST
/targets/*/verify/attest           POST
/targets/*/verify/dns              POST
/targets/*/verify/echo             POST
/targets/*/verify/file             POST
/test-jobs                         GET,POST
/test-jobs/*                       GET
/test-jobs/*/abort                 POST
/test-jobs/*/down                  GET
/test-jobs/*/insights              GET
/test-jobs/*/live                  GET
/test-jobs/*/observer              POST
/test-jobs/*/reconcile             POST
/test-jobs/*/recovery              POST
/test-jobs/*/start                 POST
/test-jobs/*/telemetry             GET
/test-plans                        GET,POST
/test-plans/*/approve              POST
/webhooks                          GET,POST
/webhooks/*                        DELETE
/webhooks/*/test                   POST
/webhooks/deliveries               GET
/workers                           GET,POST
/workers/*/ack                     POST
/workers/*/claim                   POST
/workers/*/heartbeat               POST
```
