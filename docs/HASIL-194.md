# HASIL-194 - akar sebenarnya: backtick di heredoc generator kit menjalankan make hijau (rekursi)

- tanggal: 2026-10-26
- GEJALA: generator kit seolah menggantung (timeout 120s di verify_resume_kit, 180s di
  verify_aturan_hijau), make hijau 962 detik, 1591 proses, fork failed, dan
  .out/verifikasi-ringkas.txt hanya 22 baris.
- AKAR: tools/buat_resume_kit.sh menulis TEMPEL-KE-CHAT-BARU.txt lewat heredoc TIDAK dikutip
  (PEOF) dan isinya memakai backtick berisi make hijau. Backtick di heredoc tak dikutip adalah
  PERINTAH, jadi generator menjalankan make hijau penuh. make hijau memanggil verify_resume_kit
  yang memanggil generator lagi -> REKURSI. Dua suite berjalan bersamaan sehingga saling
  make dev-down (verify_headers ConnectionRefused, verify_auth_users rc=1) dan saling menimpa
  .out/verifikasi-ringkas.txt (VERIFIER-COUNT.md jadi merah=tidak ada).
- BUKTI: jejak bash -x menunjukkan + cat / + cat / ++ make hijau; .out/kit-ukur.txt memuat
  make hijau Error 1 dan make test Hangup 1; pgrep generator = 999 proses.
- FIX: escape 4 backtick di heredoc tidak dikutip + exec 0</dev/null di awal generator;
  verify_resume_kit dan verify_aturan_hijau memanggil generator dengan stdin=subprocess.DEVNULL.
- HASIL: generator 16 menit -> 0.22 detik; make hijau 962s -> 162s; verify_headers, auth_users,
  resume_kit, aturan_hijau sembuh; verify_override_wired 433s -> 8s; VERIFIER-COUNT.md jujur lagi.
- KOREKSI: dua tebakan sebelumnya salah - generator lambat (bukan) dan balapan port biasa (bukan akar).
- angka: hijau rc=0, verifier=65, cek=461, merah=tidak ada
