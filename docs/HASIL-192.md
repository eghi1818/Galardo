# HASIL-192 - verifikasi sekali jalan + progres (bukan lambat-diam)

- tanggal: 2026-10-26
- MASALAH: runner memanggil hitung_verifier (yang menjalankan SEMUA verifier) lalu menjalankan
  semuanya LAGI -> satu blok 2-4 menit dan layar tampak stuck karena tidak ada progres.
- FIX: hitung_verifier punya mode --daftar / --dari-out / default; runner: tulis daftar dulu,
  jalankan verifier SEKALI dengan progres bertimestamp, lalu tulis angka DARI HASIL itu.
- angka: verifikasi rc=2 | hijau rc=2 | verifier=65 cek=239 merah=tidak ada
