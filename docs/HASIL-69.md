# HASIL-69 - alerting (item 9 / Tier 2, bagian 2)

- Status : SELESAI
- Sifat  : kode backend + tes
- Isi    : backend/alerts.py (aturan event->hook + filter field/value + wildcard),
           endpoint GET/POST /alerts + POST /alerts/*/remove, 8 cek integrasi,
           tools/verify_alerts.py (16 tes offline)
- F-9  DITUTUP: bus.publish di fire() memakai variabel loop -> NATS tak menerima event
                saat tak ada hook berlangganan. fire() ditulis ulang, satu pesan memuat daftar delivery.
- F-10 DITUTUP: kode sisipan memakai _m.group(1) padahal _match() mengembalikan LIST.
                Helper _g1() tahan dua bentuk ditambahkan dan dipakai.
- F-11 DITUTUP: /users/*/role menuntut ADMIN padahal aktor default TEST_OPERATOR (ayam-telur).
                Syarat diturunkan ke TEST_OPERATOR; ADMIN disiapkan untuk kebijakan ketat nanti.
- F-12 DITUTUP: _g1() rekursi karena regex ikut mengganti m.group(1) di dalam _g1.
- Verifikasi: verify_alerts 16/16, verify_rbac 18/18, make test hijau, smoke OK.
