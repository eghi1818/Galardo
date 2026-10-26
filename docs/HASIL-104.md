# HASIL-104 — V6 TUTUP: check() tidak lagi hilang tanpa jejak

STEP: 104 — Item: V6 (docs/INVENTARIS.md).

## Akar masalah
Tiga check() duduk di cabang yang tidak pernah diambil saat suite dijalankan
(`if stt == "COMPLETED"` -> dua check recovery; `else:` -> satu check jalur fallback).
Yang berbahaya: check() di cabang mati TIDAK melapor apa pun - tidak lulus, tidak gagal,
cuma hilang. Terdaftar 82, dilaporkan 79.

## Yang diubah
- tests/tests_integration.py: tambah SKIP + skip(nama, alasan); dua nama recovery dan satu
  nama jalur fallback kini SELALU melapor (lulus atau lewat) di cabang mana pun; baris
  RESULTS menyertakan angka lewat; sisa `if False else` dibersihkan.
- Penjaga baru: suite membandingkan daftar nama check()/skip() di sumbernya sendiri dengan
  nama yang benar-benar melapor. check() baru di cabang mati -> suite GAGAL.
- Ekstraktor nama dibuat toleran bentuk (PASS/FAIL menyimpan tuple (nama, detail), bukan string) setelah
  percobaan pertama kena TypeError: unhashable type: 'dict'.
- docs/INVENTARIS.md: V2 dan V6 dikoreksi (ternyata 3, bukan 4).

## Invarian yang dikunci
Setiap nama check() wajib muncul di keluaran - lulus, gagal, atau lewat.

## Temuan yang belum ditutup (kandidat item berikut)
`stt=ABORTED`: job_a berakhir ABORTED, sehingga jalur recovery monitor (POST /recovery +
10 baris polling) TIDAK PERNAH berjalan - sekarang dilaporkan [SKIP] dengan alasan.
Perlu job tersendiri yang mencapai COMPLETED supaya jalur itu benar-benar teruji, bukan
cuma dilaporkan lewat selamanya.

## Bukti
- make test: .out/HASIL-104-test.txt (memuat baris [SKIP] + DEBUG bentuk)
- make gate: .out/HASIL-104-gate.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
