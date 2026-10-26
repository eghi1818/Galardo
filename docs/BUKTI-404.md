# BUKTI-404 - override edge (Goal 3)

- tanggal dicatat: 2026-10-25 (bukti asli dari sesi lebih awal, screenshot di chat)
- TEMUAN: sebelum ini TIDAK ADA catatan 'Content 404' di docs/ maupun .out/ -> hanya screenshot.

## Mekanismenya (dari repo, bukan ingatan)
- Target make: `make t3` (Makefile baris 76) -> menjalankan `tools/galardo_t3_check.py`.
- Mesin: `backend/routeoverride.py` - docstring: "GOAL 3: force a route to 404/410/503/blank on demand".
- Mode: 404, 410, 503, blank. Tiga tingkat: `LocalShim`, `HostsOverride`, `CloudflareEdgeOverride`.
- Pembedaan: ada HEADER PEMBEDA di halaman override supaya 404 kita TIDAK tertukar dengan 404 asli
  dari upstream (docstring: "a bare 404 from a real upstream is...").
- IP yang dipakai: BUKAN IP egress kita - 404 disajikan di sisi yang di-override
  (proses lokal / /etc/hosts / edge CDN). Ini yang dinamai mode `MATI_OVERRIDE` di verdict.py.

## Bukti (screenshot, sesi lebih awal)
- portalyogya.com -> "Content 404"
- ayobandung.com  -> "Content 404"

## Yang harus dilakukan supaya tidak lagi hanya screenshot
1. Jalankan ulang `make t3` pada target yang sama, rekam: header pembeda, status, body hash.
2. Simpan hasil ke .out/ dan buat entri bukti ber-hash via POST /api/v1/bukti (docs/bukti/ledger.jsonl).
3. Tampilkan di halaman Override dashboard (status override per domain).

## Konfirmasi dari kode (STEP-180)
- `backend/routeoverride.py:38` -> `OVERRIDE_HEADER = "X-Galardo-Override"`.
- Docstring: setiap respons paksa SELALU membawa header `X-Galardo-Override: <mode>`.
- Jadi bukti 404 kita bisa dibedakan tegas dari 404 asli upstream: cukup periksa header itu.
- Panel + endpoint: `GET /api/v1/override/status`, `POST /api/v1/override/terapkan`,
  `POST /api/v1/override/bersihkan`, dan bagian "Edge override (Goal 3)" di halaman Override dashboard.
