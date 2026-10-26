# HASIL-196 - jalur pemakaian: validator skenario, app tahan mati, rantai target

- tanggal: 2026-10-26
- ISI:
  1. tools/validasi_skenario.py + resep scenario-validate diperbaiki. Resep lama RUSAK: memakai
     variabel FILE yang kosong sehingga open('') gagal, dan \n literal di dalam python -c
     menghasilkan SyntaxError. Kini resep memanggil skrip dan menerima SCENARIO atau FILE.
  2. tools/app_up.sh + tools/app_down.sh + target make app-up/app-down. Sebelumnya app mati sendiri
     (make: dev-up Hangup 1) karena setopt no_hup dipasang di dalam skrip bash padahal yang mengirim
     SIGHUP adalah zsh interaktif. Sekarang ~/.zshrc memuat setopt no_hup dan app_up.sh memakai
     trap '' HUP + exec.
  3. examples/uji-waspadaweb.yaml sebagai skenario contoh pertama.
  4. GALARDO_LOCAL_DEV=1 di .env supaya target baru auto-VERIFIED (attestation operator) - tanpa ini
     target UNVERIFIED dan policy mengosongkan allowed_hosts.
- TEMUAN yang belum tuntas: POST /scenarios/validate masih menolak host_not_allowed karena
  effective_policy(layers) menghasilkan allowed_hosts kosong. Target sudah VERIFIED dan
  allowed_hosts target sudah benar, jadi akarnya di lapisan POLICY (belum ada policy untuk eng-lab).
- angka: hijau rc=0, verifier=65, cek=465, merah=tidak ada
