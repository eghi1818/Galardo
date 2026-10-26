# HASIL-105 — penutupan dokumen STEP-104 + jangkar jalur recovery

STEP: 105.

## Latar
Blok STEP-104 percobaan kedua hanya memuat 2 berkas, sehingga koreksi INVENTARIS V2/V6 dan
baris STEPLOG 104 tertinggal - dan HASIL-104 sempat mengklaim keduanya sudah dilakukan.

## Yang diubah
- docs/INVENTARIS.md: V2 dan V6 dikoreksi (3 check mati, bukan 4; 82/83 nama melapor).
- docs/STEPLOG.md: baris 104 ditambahkan.
- docs/HASIL-104.md: kalimat bentuk data dikoreksi (PASS/FAIL menyimpan tuple, bukan dict).
- tests/tests_integration.py: baris DEBUG dibersihkan setelah bentuk data terkonfirmasi.

## Temuan terbuka
`stt=ABORTED` untuk job_a: jalur recovery monitor (POST /recovery + polling) masih belum
pernah berjalan. Hasil pembacaan fixture di langkah 4 jadi dasar perbaikan berikutnya.

## Bukti
- make test + make gate: .out/HASIL-105-test.txt, .out/HASIL-105-gate.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
