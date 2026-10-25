# HASIL-174 - verdict kematian berlapis (PROOF-OF-DEATH fase 1)

- tanggal: 2026-10-25
- SUMBER: dokumen PROOF-OF-DEATH + BEDAH BUKTI doku.com (taksonomi 9 mode, 3 saksi, falsifikasi, hash).
- ISI: backend/verdict.py - 10 mode + HIDUP, klasifikasi berlapis (hulu ke hilir), aturan 3 saksi
  3 jaringan, falsifikasi 9 uji, kontradiksi sebagai TEMUAN, belum_konklusif bila saksi < 3,
  dan mode tambahan MATI_OVERRIDE (kita yang matikan) yang dibedakan dari kematian beban.
- VERIFIER: tools/verify_verdict.py (offline, fixture per mode + anti-pola 404 != MODYAR).
- angka: verdict rc=0 | mlw rc=0 | live rc=0 | ch rc=0 | test rc=0 | gate rc=0
