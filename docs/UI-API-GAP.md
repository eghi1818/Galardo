# Peta Celah UI vs API (dibuat oleh STEP-42)

Sumber: `dashboard/index.html` vs `backend/api.py`.
Normalisasi: `${...}`, `<...>`, `{...}`, dan angka diganti `*`.

## Ringkasan

- Endpoint dipanggil UI: **2**
- Route terlihat di backend: **4**
- Dipanggil UI tapi TIDAK ada di backend: **1**
- Ada di backend tapi belum dipakai UI: **3**

## A. Dipanggil UI, belum ada padanannya di backend (PRIORITAS)

| Endpoint |
|---|
| `/api/v*/health` |

## B. Ada di backend, belum dipakai UI

| Endpoint |
|---|
| `/api/error` |
| `/api/heavy` |
| `/api/slow` |

## C. Daftar mentah (untuk verifikasi manual)

### UI
```
/api/v*
/api/v*/health
```

### Backend
```
/api/error
/api/heavy
/api/slow
/api/v*
```

## D. Catatan STEP-42

- Peta ini otomatis; nama endpoint bisa perlu dinormalisasi manual kalau backend memakai pola regex/cabang `if`.
- Belum diverifikasi: apakah buster `__gb` ditempel aman saat path target sudah punya query sendiri.
- V6 (4 `check()` mati di tests_integration.py) masih terbuka.
