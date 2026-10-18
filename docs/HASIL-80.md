# HASIL-80 — Flake verify_knee_probe (E2) + gate mandiri `make gate`

Status: TUTUP.

## Temuan (F-22, lahir dari audit mandiri setelah proyek dinyatakan tutup)
Dua hal, keduanya nyata:
1. `verify_knee_probe.py` FLAKY (~2 dari 13 run): cek E2 "panggilan kedua pakai cache"
   dan "jauh lebih cepat" gagal. Sebab: `_KNEE_CACHE[origin]` hanya terisi bila probe
   menghasilkan `estimate`; di mesin sibuk `measure()` bisa tak menghasilkan sampel ->
   cache kosong -> panggilan kedua mengukur ulang. Ekspektasi E2 benar, tapi tidak
   deterministik.
2. STRUKTURAL: `make test` hanya menjalankan tests/tests_integration.py. Ke-28 verifier
   (rbac, mfa, pg, udp, headers, exttool, dashboard, knee, ...) ada DI LUAR gate,
   sehingga "hijau" hanya berlaku selama orang ingat menjalankannya.

## Perbaikan
- E2 dibuat deterministik: env eksplisit (steps/step_sec/max_sec), cache dibersihkan,
  panggilan pertama diulang sampai cache terisi, lalu cek `cached` + kecepatan relatif
  (`t2 < max(1.0, t1*0.5)`) - bukan ambang absolut.
- Bagian A juga dikeraskan: `measure_retry()` mengulang pengukuran bila tak ada sampel sukses.
- Target baru `make gate`: menjalankan `make test` + SEMUA tools/verify_*.py, mencetak
  ok/GAGAL per verifier dan keluar non-zero bila ada yang gagal.

## Bukti
    verify_knee_probe 12/12 hijau (8 run bersih + 4 run setelah make test)
    make gate rc=0 ; semua verifier "ok" ; make test 79/0
