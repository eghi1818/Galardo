# HASIL-134 — verifier v6: identitas yang benar-benar lolos + port sendiri

- tanggal: 2026-10-24 09:35
- TEMUAN: setiap panggilan admin dengan cookie balas 403; viewer login 401. Patch 'port dari log sendiri' sebelumnya MISS (anchor gagal).
- verifier v6: probe(body,cookie) benar, status ketat, port dari log SENDIRI, identitas admin diambil dari yang benar-benar lolos GET /users (cookie), peran tersimpan dicetak, jalur cadangan Bearer dicatat jujur
- cek: 19

## Angka jujur
- auth rc=1 | test rc=0 | gate rc=2
