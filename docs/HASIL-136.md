# HASIL-136 — gate rc=2 dibongkar + isolasi data verifier

- tanggal: 2026-10-24 09:51
- auth rc=0 (20 cek) | test rc=0 | gate rc=2
- gate rc=2 terjadi SEBELUM daftar verifier (grep tidak menemukan baris verifier di log gate)
- dugaan: langkah docker/compose di target gate; daemon OrbStack di mesin ini pernah mati
- perbaikan: verifier memakai GALARDO_DATA_DIR terpisah (.out/vfy-data) kalau app mendukung, sehingga sesi/user tidak saling menimpa antar proses
- diagnosa cookie: 403 pada cookie admin TAPI 200 pada cookie vfy -> masalah sesi, bukan peran; login ulang menyelesaikan
