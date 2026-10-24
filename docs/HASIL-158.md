# HASIL-158 - live non-skip untuk /intel/preflight

- tanggal: 2026-10-24
- AKAR MASALAH STEP-157: booter memakai python3 TANPA -u -> stdout ke file ter-buffer, baris
  'listening on http://127.0.0.1:PORT' tidak ter-flush -> deteksi buta; `make run` juga tidak ada
  (target hanya gate/test/ci). Log per-percobaan saling menimpa sehingga bukti hilang.
- PERBAIKAN: pola terbukti dari verify_auth_users.py (sh -c 'cd backend && exec python3 -u run_local.py')
  + varian python3 -u; PYTHONUNBUFFERED=1; log PER-PERCOBAAN .out/intel-live-app-<n>.log; matikan
  percobaan gagal segera + cetak tail lognya; run_local memakai port dari log (bukan GALARDO_PORT).
- angka: pages rc=0 | intel rc=0 | wired rc=0 | live rc=0 | skip=0 | test rc=0 | gate rc=0
