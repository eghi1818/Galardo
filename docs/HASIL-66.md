# HASIL-66 - backup otomatis (item 8 / Tier 1, bagian 3)

- Status : SELESAI
- Sifat  : kode alat; tools/backup.py, tools/verify_backup.py, target make
- Isi    : arsip tar.gz berisi data/ + docs/HASIL-*.md + docs/SESSION_STATE.md,
           disertai MANIFEST.json berisi sha256 tiap file; retensi --keep N (bawaan 10);
           mode --restore dengan --force untuk menimpa
- Perintah: make backup | make backup-verify
- Bug yang tertangkap tes sendiri: nama arsip hanya sampai detik sehingga bertabrakan
  dalam detik yang sama; diperbaiki dengan suffix unik. backups/ masuk .gitignore.
- Verifikasi: verify_backup 15/15, make test hijau, smoke OK
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
