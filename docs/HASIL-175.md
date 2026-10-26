# HASIL-175 - FASE 2: bukti ber-hash + falsifikasi otomatis

- tanggal: 2026-10-25
- KOREKSI TERARAH: kematian DOKU = oleh Galado (bukan kita); Galardo belum punya bukti beban sendiri.
- ISI: backend/evidence.py (hash chain; ubah 1 entri -> rantai putus) + backend/falsify.py
  (10 uji konsistensi verdict-vs-saksi; uji gagal = TEMUAN; belum_konklusif bila saksi < 3 jaringan)
  + verdict.nilai_dari() jembatan + endpoint POST /verdict /falsify /bukti.
- VERIFIER: verify_evidence (14), verify_falsify (15), verify_bukti_wired (AST, 15) - semua offline.
- angka: ev rc=0 | fa rc=0 | bw rc=0 | verdict rc=0 | live rc=0 | test rc=0 | gate rc=0
