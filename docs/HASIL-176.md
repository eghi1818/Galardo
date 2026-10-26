# HASIL-176 - fix tabrakan evidence.py + cap V1.4 + trail bukti 404/t3

- tanggal: 2026-10-25
- MERAH STEP-175: test rc=2 (KeyError 'id' di /evidence/{id}/verify). AKAR: backend/evidence.py SUDAH ADA
  dan ditimpa oleh cat >; route /evidence lama kehilangan API-nya. (kelas kesalahan sama seperti capacity)
- FIX: ledger dipindah ke backend/bukti.py; evidence.py dikembalikan (git checkout); wiring diarahkan
  ke bukti.*; verifier verify_evidence.py -> verify_bukti.py.
- CAP: docs/V1.4.md, docs/TARGET-BUKTI.md (wecash.ai + waspadaweb.com), checklist VPS, banner V1.4
  di SESSION_STATE/HANDOFF/RINGKASAN-AKHIR. Tag v1.4.
- angka: bukti rc=0 | bukti_wired rc=0 | falsify rc=0 | verdict rc=0 | test rc=0 | gate rc=0
