# HASIL-139 — gate merah = cek TEKS-SUMBER yang rapuh di verify_headers (bukan app, bukan docker, bukan pkill)

- tanggal: 2026-10-24 10:26
- KOREKSI HASIL-138: kesimpulan 'pembungkus BUKAN penyebab' tidak sahih karena skrip eksperimennya rusak (mutasi src dengan offset lama -> 'retun:' -> app gagal start)
- AKAR SEBENARNYA: tools/verify_headers.py baris 59 menguji literal 'def do_OPTIONS(self):' di teks sumber. Pembungkus menamai ulang jadi do_OPTIONS_impl -> literal hilang -> GAGAL, padahal perilakunya BENAR (curl OPTIONS = 204 No Content + header CORS lengkap)
- perbaikan: cek nama fungsi jadi regex toleran lewat helper _hasdef() di semua verifier yang memakai pola rapuh
- hasil: verify_headers rc=1 | auth rc=0 | test rc=0 | gate rc=2
