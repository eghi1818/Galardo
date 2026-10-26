# HASIL-119 — pengetatan produksi: auth wajib dinyalakan

- tanggal: 2026-10-22 16:32
- GALARDO_REQUIRE_AUTH=1 disetel di .env; GALARDO_DEV_TOKEN diganti nilai acak 32 hex
- container di-recreate agar env terbaca
- bukti: /api/v1/overview tanpa token vs dengan token (lihat .out)

## Catatan
- Token baru dicetak saat blok dijalankan; simpan untuk dipakai di UI.
- KONEKSI-PIHAK-KETIGA.md: baris Cloudflare dikoreksi (kredensial SUDAH diisi, terbukti STEP-118).
- Sisa: TLS/reverse proxy bila diekspos ke internet; pool proxy opsional.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
