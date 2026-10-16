# Peta Celah UI vs API — v2 (STEP-43)

Sumber: `dashboard/index.html` vs tabel dispatch `backend/api.py` (base `/api/v1`).
Normalisasi: `${...}` `<...>` `{...}` dan angka -> `*`.

## Ringkasan

- Literal path di UI: **26**
- Route di dispatch backend: **10**
- UI <-> backend cocok: **7**
- UI memanggil, TIDAK ada di backend (non-static): **19**
- Route backend belum dipakai UI: **3**

## A. UI memanggil, tidak ada padanan backend (PRIORITAS)

| Path |
|---|
| `/admin/secret` |
| `/api/v*/health` |
| `/engagements/*/approve` |
| `/evidence` |
| `/evidence/*/build` |
| `/evidence/*/verify` |
| `/scenarios` |
| `/scenarios/validate` |
| `/scenarios/visual-to-yaml` |
| `/targets/*/verify` |
| `/test-jobs` |
| `/test-jobs/*/abort` |
| `/test-jobs/*/insights` |
| `/test-jobs/*/live` |
| `/test-jobs/*/recovery` |
| `/test-jobs/*/start` |
| `/test-plans` |
| `/test-plans/*/approve` |
| `/workers` |

## B. Route backend belum dipakai UI

| Path |
|---|
| `/api` |
| `/health` |
| `/seed` |

## C. Cocok (UI <-> backend)

| Path |
|---|
| `/` |
| `/api/v*` |
| `/engagements` |
| `/healthz` |
| `/overview` |
| `/policies` |
| `/targets` |

## D. Static/aset (bukan API)

```
```

## E. Daftar mentah backend

```
/
/api
/api/v*
/engagements
/health
/healthz
/overview
/policies
/seed
/targets
```
