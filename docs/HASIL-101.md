# HASIL-101 — rekonsiliasi dokumen + node di CI

STEP: 101.

## Yang diubah
- `docs/KONEKSI-PIHAK-KETIGA.md`: item 3 tidak lagi bilang P2 "belum dibaca"; daftar env
  ditambah `GALARDO_POOL_`; kutipan sumber `proxypool.py` diarahkan ke `POOL_PREFIX`.
- `docs/DEPLOY-VPS.md`: daftar env ditambah `GALARDO_POOL_`.
- `docs/ROADMAP.md`: baris sisa diperbarui (P1-P6 SELESAI, sisa P7 usul + Tier 3-4).
- `docs/EMERGENCY.md`: acuan `make test` 61 -> 79.
- `.github/workflows/gate.yml`: tambah `actions/setup-node@v4` (node 22) supaya
  `node --check` benar-benar berjalan di runner; pola ringkasan ditambah `^  FAIL`
  karena sebelumnya hanya menangkap `GAGAL ` milik gate sendiri.
- `docs/STEPLOG.md`: backfill 81-96 dari jendela commit e067229..3f64fd9.

## Peta backfill (nomor mengikuti urutan commit, bukan klaim)
81=e067229, 82=58d8261, 83=1f68974, 84=752fccf, 85=0dda19b, 86=d3d6d50, 87=a6935fc,
88=3f64fd9. docs/HASIL-85/87/88 jatuh pas di tiga commit terakhir jendela. Baris 89-96
ditandai tanpa jejak (tidak ada commit berlabel STEP maupun docs/HASIL-89..96).

## P1: konfirmasi yang masih menggantung
Kode CI ada sejak commit 58d8261, tetapi run hijau di tab Actions belum pernah dipastikan.
Cara: `brew install gh && gh auth login`, lalu `gh run list -L 8`. Alternatif: buka tab
Actions di repo, jalankan workflow `gate` lewat `workflow_dispatch`, lihat hasilnya.
Risiko yang perlu diawasi: verifier yang melakukan probe jaringan (DNS/NTP/SSDP/UDP) bisa
berperilaku beda di runner dan `timeout-minutes: 20` bisa sempit.

## Bukti
- `make gate` + `make test`: lihat .out/HASIL-101-gate.txt dan .out/HASIL-101-test.txt
