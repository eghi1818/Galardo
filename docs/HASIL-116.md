# HASIL-116 — L1: Galardo Mode Aktif jalan di host nyata

- tanggal: 2026-10-22 14:39
- cara nyala: nohup sh -c 'cd backend && exec python3 -u run_local.py' (setara make dev-up)
- port: 8090 (dibaca dari log run_local, bukan diasumsikan)
- dashboard: http://127.0.0.1:8090/
- API base: http://127.0.0.1:8090/api/v1
- bukti mentah: .out/STEP-116-live.txt

## Catatan koreksi
- Percobaan 1 gagal: tools/run_local.py tidak ada; yang benar backend/run_local.py (Makefile dev-up).
- Route API berprefiks /api/v1; probe ke /health tanpa prefiks memang 404.
- stdout Python ter-buffer saat diarahkan ke file; pakai python3 -u agar log terbaca.
