# HASIL-125 — mesin pengguna: sandi, peran, token API opt-in, sesi terpisah

- tanggal: 2026-10-23 22:13
- backend/users.py: pengguna + sandi PBKDF2-SHA256 (200k iterasi + salt) + token per pengguna + saklar akses API
- backend/sessions.py: sesi login terpisah dari token (sid 48 hex, TTL 7 hari, dapat dicabut)
- backend/rbac.py: SUPERADMIN (rank 5) + user_of() jatuh ke penyimpanan kredensial
- api.py: login (username+sandi / token), /logout, endpoint /users lengkap, gerbang peran global
- dashboard: halaman login dua mode, panel Pengguna, redirect ke login, tombol keluar
- default: akses API MATI (least privilege); token dibuat saat dinyalakan

## Bukti
- test rc=0; gate rc=0 dengan 37 verifier hijau, 0 GAGAL
- viewer: GET 200, POST /engagements 403, GET /users 403
- APPROVER: dapat POST; role ngawur 422; cookie setelah logout 401; logout mencabut sesi

## Bug yang dibuka proses ini (8)
1. run_local.py ada di backend/, bukan tools/
2. route API berprefiks /api/v1
3. patch _auth salah anchor -> handler /users lama menang
4. secrets tidak di-import -> NameError mematikan setiap request
5. rbac.ensure mengembalikan tuple, bukan melempar exception
6. cookie berisi token kosong -> sesi dipisah dari token
7. sisipan r[status] memutus pasangan if/else
8. upsert tidak memvalidasi peran di jalur update
