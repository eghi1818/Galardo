# HASIL-133 — akar masalah auth: bug probe() di verifier, bukan server

- tanggal: 2026-10-24 09:27
- KOREKSI HASIL-132: 'POST /users memutus koneksi' SALAH. Server sehat (balas 201 dua kali).
- AKAR: tools/verify_auth_users.py punya probe(method, path, cookie, body, ...) tapi dipanggil dengan body di posisi cookie -> TypeError -> probe balik 0. Lalu 'if s < 400' menganggap 0 = sukses -> muncul klaim palsu 'diselaraskan'.
- perbaikan: urutan parameter probe dibetulkan, semua cek status jadi '200 <= s < 400', verifier memakai port app MILIKNYA (dibaca dari log sendiri, bukan scan app lain), upsert vfy-admin coba SUPERADMIN lalu ADMIN, reconcile_admin utamakan peran tertinggi.
- perbaikan api.py: seed uid master tanpa kwarg api_access (upsert(**doc) dulu), laporan jujur berhasil/gagal.

## Angka jujur
- auth rc=1 | test rc=0 | gate rc=2
