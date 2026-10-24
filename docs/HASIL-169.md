# HASIL-169/170 - wiring multi-lane ke orchestrator (gated env)

- tanggal: 2026-10-24
- KOREKSI: draft HASIL-169 menulis mlw rc=0 padahal saat itu rc=1; anchor salah karena panggilan
  LoadEngine di orchestrator TIDAK memakai verify_tls=. Anchor diperbaiki ke penutup abort_check=...
- ISI: proxy.lanes_aktif() (defensif, cari registry di level modul; REGISTRY ada di proxy.py:195) +
  orchestrator._lanes_aktif() (aktif HANYA bila GALARDO_MULTILANE=1 dan lane terdaftar) +
  LoadEngine(..., lanes=_lanes_aktif()). Tanpa env/lane -> perilaku identik seperti sebelumnya.
- .env: GALARDO_MULTILANE=1.
- VERIFIER: tools/verify_multilane_wired.py (AST + behavioral; 14 cek) - helper ada, lanes= dipakai,
  abort_check & canonical_origin utuh, route /lanes utuh, env mati/hidup, .env memuat env.
- angka: mlw rc=0 | ml rc=0 | knee rc=0 | live rc=0 | ch rc=0 | pages rc=0 | test rc=0 | gate rc=0
