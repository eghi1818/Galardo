# AUDIT DASHBOARD

Status: SELESAI (STEP-56). Peta lengkap: `docs/UI-API-GAP.md` (v4, STEP-45).

## Fakta dasar
- Satu file: `dashboard/index.html` (1205 baris, ~78KB, HTML+CSS+JS inline, tanpa build step).
- Disajikan `backend/api.py` lewat `_static` (`DASH_DIR` baris 30; handler 301-352; traversal diblokir).
- Hanya 1 commit menyentuh folder ini. Tanpa aset eksternal/CDN.

## Permukaan API
- `docs/UI-API-GAP.md` v4: 25 path dipanggil UI, 57 route backend, 23 cocok.
- UI memanggil 2 path tanpa handler backend: `GET /admin/secret`, `GET /healthz`.

## Model keamanan
- Auth: Bearer `DEV_TOKEN` (default `dev-token`, env `GALARDO_DEV_TOKEN`) - `backend/api.py:31`, cek 183-191.
- CORS `*`, mengizinkan header `Authorization` + `Idempotency-Key` (baris 165-167).
- Belum ada `Content-Security-Policy`.
- Banyak `innerHTML`; ada helper `esc()` - kelengkapannya belum diaudit.

## Temuan (belum dikerjakan)
- F-2: UI memanggil `/admin/secret` + `/healthz` yang belum ada handler-nya.
- F-3: tidak ada CSP.
- F-4: CORS `*` digabung Bearer token.
