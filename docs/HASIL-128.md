# HASIL-128 — tutup klaim palsu HASIL-127 + onboarding + resolver auth

- tanggal: 2026-10-24 07:41
- KOREKSI: HASIL-127 mengklaim 'verify_goal_doctrine rc=0' padahal cek 'doktrin menamai dirinya sendiri' GAGAL 1. Blok 127 juga commit hanya atas dasar make test, bukan rc verifier.
- docs/GOAL-GALARDO.md: ditambah baris 'Berkas ini:' agar doktrin menamai dirinya sendiri
- tools/verify_goal_doctrine.py: diperbaiki (menuntut penamaan diri + menemukan berkas onboarding secara dinamis, bukan daftar path tebak-tebakan)
- tools/verify_auth_users.py: diganti versi RESOLVER (base /api/v1 dideteksi sendiri, tabel diag kalau gagal)
- berkas onboarding: ditanam/dibuat supaya rujukan doktrin benar-benar melekat

## Angka jujur dari blok ini
- verify_goal_doctrine rc=0
- verify_auth_users   rc=1
- make test           rc=0
- make gate           rc=2
