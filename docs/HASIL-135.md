# HASIL-135 — tutup cek terakhir (areq 422) + isolasi app verifier

- tanggal: 2026-10-24 09:41
- BUG: areq hanya menerima 200..399 dari jalur cadangan, sehingga 422 dibuang dan 403 asli dikembalikan
- perbaikan: areq menerima semua status non-403; coba cookie segar dulu, baru Bearer
- perbaikan: verifier mematikan app lain dulu (pkill run_local.py) supaya ia pemilik data/sessions.json — dugaan kuat kenapa cookie 403 (dua proses berbagi file sesi)
- diagnosa: cetak status GET /users dgn cookie admin & cookie vfy

## Angka jujur
- auth rc=0 | test rc=0 | gate rc=2
