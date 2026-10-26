# HASIL-191 - prasyarat make hijau di dokumen bukti + penegasan gate tidak cukup

- tanggal: 2026-10-26
- MASALAH: docs/TARGET-BUKTI.md luput dari penggantian massal gate -> hijau, sehingga pembaca baru
  bisa menjalankan make gate dan merasa sudah memverifikasi padahal verifier tidak dijalankan.
- FIX: prasyarat make hijau ditulis sebagai langkah 0 di docs/TARGET-BUKTI.md, plus penegasan di
  kit resume bahwa gate TIDAK cukup (gate = test + step_guard tipis).
- CATATAN: blok STEP-191 sempat ter-Ctrl-C, jadi HASIL-nya baru ditulis di STEP-193.
- angka: lihat HASIL-193.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
