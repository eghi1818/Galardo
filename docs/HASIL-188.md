# HASIL-188 - betulkan capacity.py (netssl) + urutan daftar cek -> verifikasi hijau

- tanggal: 2026-10-25
- AKAR MERAH 1: backend/capacity.py (dibuat STEP-159) memakai urlopen TANPA context dan tanpa impor
  netssl; auto-repair STEP-187 melewatinya karena menuntut impor netssl lebih dulu.
  FIX: impor netssl level modul + helper _ctx() + urlopen(..., context=_ctx()).
- AKAR MERAH 2: VERIFIER-COUNT.md diregenerasi SETELAH verifikasi -> pengunci daftar merah karena basi.
  FIX: runner menyegarkan daftar lebih dulu; hitung_verifier mengonfirmasi ulang verifier merah sekali lagi.
- ANGKA KANONIK: verifier=63 | total cek hijau=430 | merah=tidak ada
- angka: verifikasi rc=0 | verifier_count rc=0 | hasil_lengkap rc=0 | test rc=0 | gate rc=0
